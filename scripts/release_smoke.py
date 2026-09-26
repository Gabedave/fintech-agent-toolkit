#!/usr/bin/env python3

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from process_control import stop_process_group, termination_guard


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "plugins" / "fintech-engineering" / ".codex-plugin" / "plugin.json"
SCENARIOS = ROOT / "tests" / "behavior-scenarios.json"
REVIEW_CASES = ROOT / "tests" / "review-quality" / "cases.json"
DEFAULT_MODEL_TIMEOUT_SECONDS = 120
INSTALL_TIMEOUT_SECONDS = 120
TIMEOUT_BUFFER_SECONDS = 60
MAX_REVIEW_OPERATIONAL_REPLACEMENTS = 1
MAX_BEHAVIOR_OPERATIONAL_REPLACEMENTS = 1


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def run(command: list[str], env: dict[str, str], label: str,
        *, timeout_seconds: float = INSTALL_TIMEOUT_SECONDS,
        report_stdout_on_failure: bool = False) -> str:
    with termination_guard():
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, env=env, start_new_session=True)
        try:
            stdout, stderr = process.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            stdout, _ = stop_process_group(process, grace_seconds=5)
            if report_stdout_on_failure and stdout.strip():
                print(stdout.strip(), flush=True)
            fail(f"{label} timed out after {timeout_seconds:g}s; result is incomplete")
        except BaseException:
            stop_process_group(process, grace_seconds=5)
            raise
    if process.returncode != 0:
        # Opt in only for our quality evaluator's structured synthetic report,
        # never for raw Codex/authentication command output.
        if report_stdout_on_failure and stdout.strip():
            print(stdout.strip(), flush=True)
        detail = stderr.strip() or stdout.strip() or "no command output"
        fail(f"{label} failed ({process.returncode}): {detail}")
    return stdout.strip()


def git_output(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        fail(f"cannot inspect candidate commit: {result.stderr.strip()}")
    return result.stdout.strip()


def backend_git_output(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        fail(f"cannot inspect example backend checkout: {result.stderr.strip()}")
    return result.stdout.strip()


def suite_timeout(call_count: int, per_call_seconds: int,
                  per_call_overhead_seconds: int = 10) -> int:
    return call_count * (per_call_seconds + per_call_overhead_seconds) + TIMEOUT_BUFFER_SECONDS


def review_quality_summary(output: str) -> str:
    prefixes = ("Review-quality pilot: ", "Review-quality pilot passed ")
    lines = [line for line in output.splitlines() if line.startswith(prefixes)]
    if len(lines) != len(prefixes) or not all(
        any(line.startswith(prefix) for line in lines) for prefix in prefixes
    ):
        fail("review-quality pilot succeeded without its required summary")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Install and smoke-test the exact toolkit candidate in disposable Codex state."
    )
    parser.add_argument(
        "--repo",
        type=Path,
        required=True,
        help="Clean synthetic or adopter-provided backend checkout used for routing scenarios.",
    )
    parser.add_argument(
        "--auth-file",
        type=Path,
        default=Path(os.environ.get("CODEX_RELEASE_AUTH_FILE", "~/.codex/auth.json")),
        help="Existing Codex auth.json to link read-only into disposable state.",
    )
    parser.add_argument("--model", help="Optional Codex model override for the smoke suite.")
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_MODEL_TIMEOUT_SECONDS,
        help="Per-model-call deadline forwarded to routing and review evaluators.",
    )
    parser.add_argument("--review-quality", action="store_true",
                        help="Also run every bounded synthetic review case (review-gate changes).")
    parser.add_argument(
        "--verbose-review-output",
        action="store_true",
        help="Print complete successful synthetic reviews instead of the compact summary.",
    )
    args = parser.parse_args()
    if not 30 <= args.timeout_seconds <= 180:
        parser.error("timeout must be between 30 and 180 seconds per model call")
    if args.verbose_review_output and not args.review_quality:
        parser.error("--verbose-review-output requires --review-quality")

    if git_output("status", "--porcelain"):
        fail("candidate checkout must be clean so the reported commit exactly identifies it")

    backend_repo = args.repo.resolve()
    if backend_git_output(backend_repo, "status", "--porcelain"):
        fail("example backend checkout must be clean so its reported commit exactly identifies it")
    backend_commit = backend_git_output(backend_repo, "rev-parse", "HEAD")

    auth_file = args.auth_file.expanduser().resolve()
    if not auth_file.is_file():
        fail("Codex authentication file is unavailable; authenticate before release testing")

    manifest = json.loads(MANIFEST.read_text())
    scenarios = json.loads(SCENARIOS.read_text()).get("scenarios", [])
    review_pairs = json.loads(REVIEW_CASES.read_text()).get("cases", [])
    commit = git_output("rev-parse", "HEAD")

    with tempfile.TemporaryDirectory(prefix="fintech-release-codex-") as temp_dir:
        codex_home = Path(temp_dir)
        codex_home.chmod(0o700)
        (codex_home / "auth.json").symlink_to(auth_file)
        env = os.environ.copy()
        env["CODEX_HOME"] = str(codex_home)
        env["PYTHONDONTWRITEBYTECODE"] = "1"

        run(
            ["codex", "plugin", "marketplace", "add", str(ROOT)],
            env,
            "candidate marketplace installation",
            timeout_seconds=INSTALL_TIMEOUT_SECONDS,
        )
        run(
            ["codex", "plugin", "add", "fintech-engineering@gabedave"],
            env,
            "candidate plugin installation",
            timeout_seconds=INSTALL_TIMEOUT_SECONDS,
        )
        command = [
            sys.executable,
            str(ROOT / "scripts" / "evaluate_behavior.py"),
            "--repo",
            str(backend_repo),
            "--timeout-seconds",
            str(args.timeout_seconds),
        ]
        if args.model:
            command.extend(["--model", args.model])
        smoke_output = run(
            command,
            env,
            "installed-candidate behavior suite",
            timeout_seconds=suite_timeout(
                len(scenarios) + MAX_BEHAVIOR_OPERATIONAL_REPLACEMENTS,
                args.timeout_seconds,
            ),
        )
        quality_output = ""
        if args.review_quality:
            quality_command = [
                sys.executable,
                "-B",
                str(ROOT / "scripts" / "evaluate_review_quality.py"),
                "--run",
                "--timeout-seconds",
                str(args.timeout_seconds),
            ]
            if args.model:
                quality_command.extend(["--model", args.model])
            quality_output = run(quality_command, env, "installed-candidate review-quality pilot",
                                 timeout_seconds=suite_timeout(
                                     len(review_pairs) * 2 + MAX_REVIEW_OPERATIONAL_REPLACEMENTS,
                                     args.timeout_seconds,
                                     per_call_overhead_seconds=120,
                                 ),
                                 report_stdout_on_failure=True)

        if git_output("status", "--porcelain") or git_output("rev-parse", "HEAD") != commit:
            fail("candidate changed during verification; rerun against a clean frozen commit")
        if (backend_git_output(backend_repo, "status", "--porcelain") or
                backend_git_output(backend_repo, "rev-parse", "HEAD") != backend_commit):
            fail("example backend checkout changed during verification; rerun from a clean frozen commit")

    if smoke_output:
        print(smoke_output)
    if quality_output:
        if args.verbose_review_output:
            print(quality_output)
        else:
            try:
                summary = review_quality_summary(quality_output)
            except SystemExit:
                print(quality_output, flush=True)
                raise
            print(summary)

    print(f"fintech plugin release smoke passed ({len(scenarios)} scenarios)")
    print(f"Candidate version: {manifest['version']}")
    print(f"Candidate commit: {commit}")
    print(f"Example backend commit: {backend_commit}")
    print("Codex state: disposable; authentication linked without copying")


if __name__ == "__main__":
    try:
        with termination_guard():
            main()
    except KeyboardInterrupt:
        print("Release smoke cancelled; no passing result", file=sys.stderr)
        raise SystemExit(130)
