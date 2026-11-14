"""Private, append-only evidence for installed-candidate model invocations.

The CLI caller supplies storage outside candidate/fixture trees. This captures
native output, not a reconstructed tool transcript or acceptance attestation.
"""

import hashlib
import json
import os
import selectors
import platform
import re
import subprocess
import sys
import tempfile
import time
import threading
from pathlib import Path

from process_control import stop_process_group, termination_guard


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    path.chmod(0o600)


def git_identity(root):
    identity = {"path": str(Path(root).resolve()), "commit": None, "clean": None}
    try:
        commit = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                                capture_output=True, text=True, timeout=5, check=True)
        status = subprocess.run(["git", "-C", str(root), "status", "--porcelain"],
                                capture_output=True, text=True, timeout=5, check=True)
        identity.update(commit=commit.stdout.strip(), clean=not status.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        pass
    return identity


def create_run(base, kind, bindings):
    base = Path(base).expanduser().resolve()
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    run = Path(tempfile.mkdtemp(prefix=kind + "-", dir=base))
    parent = base / "run.json"
    write_json(run / "run.json", {
        "parent_manifest": {"path": str(parent), "sha256": digest(parent.read_bytes())} if parent.is_file() else None,
        "kind": kind, "bindings": bindings, "python": sys.version,
        "platform": platform.platform(), "created_unix": time.time(),
    })
    return run


def validate_location(base, *protected):
    base = Path(base).expanduser().resolve()
    for path in protected:
        if base.is_relative_to(Path(path).resolve()):
            raise ValueError("evidence directory must be outside candidate and fixture trees")
    return base


class NativeAttempt:
    def __init__(self, root, label, command, prompt, schema, model, bindings, output):
        label = re.sub(r"[^a-zA-Z0-9_.-]", "-", label)
        self.path = Path(tempfile.mkdtemp(prefix=label + "-", dir=root))
        self.output = output
        prompt_bytes = prompt.encode()
        schema_bytes = schema.read_bytes()
        (self.path / "prompt.txt").write_bytes(prompt_bytes)
        (self.path / "schema.json").write_bytes(schema_bytes)
        write_json(self.path / "invocation.json", {
            "command": command, "requested_model": model,
            "model_identity_source": "requested override; observed stderr model header recorded separately when available",
            "prompt_sha256": digest(prompt_bytes), "schema_sha256": digest(schema_bytes),
            "bindings": bindings,
            "run_manifest_sha256": digest((Path(root) / "run.json").read_bytes()),
        })
        write_json(self.path / "process.json", {"status": "not_started"})

    def run(self, command, prompt, timeout, *, cwd=None, env=None):
        # Stream to disk from process start: timeout/cancellation cannot discard
        # the useful prefix. Diagnostics stay private and out of chat output.
        with (self.path / "stdout.jsonl").open("wb") as stdout_file, termination_guard():
            try:
                process = subprocess.Popen(command, stdin=subprocess.PIPE,
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                           text=True, cwd=cwd, env=env, start_new_session=True)
            except OSError as error:
                write_json(self.path / "process.json", {"status": "spawn_failed", "error_type": type(error).__name__})
                raise
            # Drain both streams with bounded cancellation. Only allowlisted
            # model headers escape the diagnostic hash; raw stderr is discarded.
            streams = {"stdout": process.stdout.detach(), "stderr": process.stderr.detach()}
            process.stdout = process.stderr = None
            stderr_digest = hashlib.sha256()
            stream_state = {"stdout_closed": False, "stderr_closed": False,
                            "model": None, "error": False}
            stop_reading = threading.Event()
            def drain_streams():
                header = b""
                with selectors.DefaultSelector() as selector:
                    for name, stream in streams.items():
                        os.set_blocking(stream.fileno(), False)
                        selector.register(stream, selectors.EVENT_READ, name)
                    try:
                        while selector.get_map() and not stop_reading.is_set():
                            for key, _ in selector.select(timeout=.1):
                                chunk = os.read(key.fd, 65536)
                                if not chunk:
                                    stream_state[key.data + "_closed"] = True
                                    selector.unregister(key.fileobj)
                                    continue
                                if key.data == "stdout":
                                    stdout_file.write(chunk)
                                    stdout_file.flush()
                                else:
                                    stderr_digest.update(chunk)
                                    # Keep at most one bounded unfinished line.
                                    lines = (header + chunk).split(b"\n")
                                    header = lines.pop()[-256:]
                                    for line in lines:
                                        match = re.fullmatch(rb"model: ([A-Za-z0-9][A-Za-z0-9_.:/-]{0,127})\r?", line)
                                        if match:
                                            stream_state["model"] = match[1].decode("ascii")
                    except OSError:
                        stream_state["error"] = True
                    finally:
                        for stream in streams.values():
                            stream.close()
            reader = threading.Thread(target=drain_streams, daemon=True)
            reader.start()
            started = time.time()
            write_json(self.path / "process.json", {
                "status": "running", "pid": process.pid, "started_unix": started,
                "timeout_seconds": timeout,
            })
            status = "cancelled"
            timed_out = False
            try:
                process.communicate(prompt, timeout=timeout)
                status = "succeeded" if process.returncode == 0 else "nonzero"
            except subprocess.TimeoutExpired:
                timed_out = True
                status = "timed_out"
                stop_process_group(process)
            except BaseException:
                stop_process_group(process)
                raise
            finally:
                write_json(self.path / "process.json", {
                    "status": status, "returncode": process.returncode,
                    "pid": process.pid, "started_unix": started,
                    "finished_unix": time.time(), "timeout_seconds": timeout,
                })
                # A successful CLI leader can leave children writing. Stop
                # its remaining group before sealing; detached descendants are
                # not claimed as controlled by this group.
                cleanup_required = False
                try:
                    os.killpg(process.pid, 0)
                    cleanup_required = True
                    stop_process_group(process)
                except ProcessLookupError:
                    pass
                reader.join(timeout=1)
                if reader.is_alive():
                    stop_reading.set()
                    reader.join(timeout=1)
                streams_closed = stream_state["stdout_closed"] and stream_state["stderr_closed"]
                stdout_file.flush()
                self.retain_result()
                names = ("stdout.jsonl", "final-result.json")
                write_json(self.path / "capture.json", {
                    "sha256": {name: digest((self.path / name).read_bytes())
                               for name in names if (self.path / name).is_file()},
                    "raw_capture_completeness": "complete" if (status == "succeeded" and streams_closed
                        and not cleanup_required and not stream_state["error"]) else "unverified",
                    "streams_closed": streams_closed,
                    "remaining_group_cleanup_required": cleanup_required,
                    "descendant_scope": "process group only; detached descendants unverified",
                    "observed_model": stream_state["model"],
                    "observed_model_source": "allowlisted stderr header" if stream_state["model"] else None,
                    "process_success": status == "succeeded",
                    "stderr_sha256": stderr_digest.hexdigest(),
                    "stderr_hash_complete": stream_state["stderr_closed"] and not stream_state["error"],
                    "stderr_retained": False,
                })
        return (process.returncode, (self.path / "stdout.jsonl").read_text(),
                "native diagnostics omitted", timed_out)

    def retain_result(self):
        # Do not follow a model-created symlink into unrelated local files.
        if self.output.is_file() and not self.output.is_symlink():
            data = self.output.read_bytes()
            target = self.path / "final-result.json"
            if not target.exists():
                target.write_bytes(data)
                target.chmod(0o600)

    def mark_usable(self):
        write_json(self.path / "result-status.json", {"usable": True})


def unsuccessful_usable_processes(root):
    failures = []
    for marker in Path(root).glob("*/result-status.json"):
        process = json.loads((marker.parent / "process.json").read_text())
        capture = json.loads((marker.parent / "capture.json").read_text())
        if process["status"] != "succeeded" or capture["raw_capture_completeness"] != "complete":
            failures.append(f"{marker.parent.name}: usable result scored, native process {process['status']}")
    return failures
