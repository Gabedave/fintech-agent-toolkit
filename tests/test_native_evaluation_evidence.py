"""Native evidence survives failed processes and disposable fixture cleanup."""
import contextlib
import io
import json
import os
import sys
import tempfile
import signal
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import evaluate_behavior as behavior
import evaluate_review_quality as review
import native_evidence as evidence
import release_smoke


class NativeEvidenceTests(unittest.TestCase):
    def test_exact_stream_and_final_survive_success_failure_and_timeout(self):
        for ending, expected in (("", "succeeded"), ("sys.exit(7)", "nonzero"),
                                 ("time.sleep(30)", "timed_out")):
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as directory:
                root = evidence.create_run(Path(directory) / "evidence", "test", {"commit": "frozen"})
                with tempfile.TemporaryDirectory() as fixture:
                    output = Path(fixture) / "result.json"
                    raw_final = ' {"verdict": "ready"}\n'
                    program = (
                        "import sys,time; from pathlib import Path; "
                        f"Path({str(output)!r}).write_text({raw_final!r}); "
                        "print('{\"type\":\"item.completed\",\"original\":true}', flush=True); "
                        "print('PRIVATE_PROVIDER_DIAGNOSTIC\\nmodel: gpt-test', file=sys.stderr, flush=True); "
                        + ending
                    )
                    command = [sys.executable, "-B", "-c", program]
                    attempt = evidence.NativeAttempt(root, "case", command, "exact prompt\n",
                                                     review.SCHEMA, "test-model", {"fixture": "frozen"}, output)
                    attempt.run(command, "exact prompt\n", 0.25)
                self.assertFalse(output.exists())
                self.assertEqual((attempt.path / "final-result.json").read_text(), raw_final)
                self.assertEqual((attempt.path / "stdout.jsonl").read_text(),
                                 '{"type":"item.completed","original":true}\n')
                capture = json.loads((attempt.path / "capture.json").read_text())
                self.assertEqual(capture["stderr_sha256"], evidence.digest(b"PRIVATE_PROVIDER_DIAGNOSTIC\nmodel: gpt-test\n"))
                self.assertTrue(capture["stderr_hash_complete"])
                self.assertEqual(capture["observed_model"], "gpt-test")
                self.assertFalse((attempt.path / "stderr.txt").exists())
                process = json.loads((attempt.path / "process.json").read_text())
                self.assertEqual(process["status"], expected)
                invocation = json.loads((attempt.path / "invocation.json").read_text())
                self.assertEqual(invocation["command"], command)
                self.assertEqual(invocation["requested_model"], "test-model")
                self.assertEqual(invocation["prompt_sha256"], evidence.digest(b"exact prompt\n"))
                self.assertEqual((attempt.path / "schema.json").read_bytes(), review.SCHEMA.read_bytes())
                self.assertEqual(attempt.path.stat().st_mode & 0o777, 0o700)

    def test_remaining_child_writers_are_bounded_and_never_claim_complete_capture(self):
        for detached in (False, True):
            with self.subTest(detached=detached), tempfile.TemporaryDirectory() as directory:
                root = evidence.create_run(directory, "test", {})
                pid_file = Path(directory) / "child.pid"
                output = Path(directory) / "result.json"
                child = ("import os,time; from pathlib import Path; "
                         f"Path({str(pid_file)!r}).write_text(str(os.getpid())); "
                         "print('CHILD_STREAM', flush=True); time.sleep(30)")
                parent = ("import subprocess,sys,time; from pathlib import Path; "
                          f"subprocess.Popen([sys.executable, '-c', {child!r}], start_new_session={detached!r}); "
                          f"p=Path({str(pid_file)!r}); "
                          "exec('while not p.exists(): time.sleep(.01)')")
                command = [sys.executable, "-c", parent]
                attempt = evidence.NativeAttempt(root, "child", command, "", review.SCHEMA, None, {}, output)
                started = time.monotonic()
                try:
                    attempt.run(command, "", 5)
                    self.assertLess(time.monotonic() - started, 5)
                    capture = json.loads((attempt.path / "capture.json").read_text())
                    self.assertEqual(capture["raw_capture_completeness"], "unverified")
                    self.assertEqual(capture["remaining_group_cleanup_required"], not detached)
                    if detached:
                        self.assertFalse(capture["streams_closed"])
                    self.assertEqual(capture["sha256"]["stdout.jsonl"],
                                     evidence.digest((attempt.path / "stdout.jsonl").read_bytes()))
                finally:
                    if pid_file.exists():
                        try:
                            os.kill(int(pid_file.read_text()), signal.SIGKILL)
                        except ProcessLookupError:
                            pass

    def test_repeated_case_attempts_and_runs_never_overwrite_prior_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            first = evidence.create_run(directory, "release", {"commit": "first"})
            second = evidence.create_run(directory, "release", {"commit": "first"})
            self.assertNotEqual(first, second)
            output = Path(directory) / "result.json"
            attempts = [evidence.NativeAttempt(first, "same-case", ["codex"], "prompt",
                         review.SCHEMA, None, {"attempt": index}, output) for index in (1, 2)]
            self.assertNotEqual(attempts[0].path, attempts[1].path)
            self.assertTrue(all((attempt.path / "invocation.json").is_file() for attempt in attempts))

    def test_complete_review_after_process_failure_is_scored_once_without_replacement(self):
        case = review.load_suite()[0]
        for message in ("execution failed (exit 7)", "execution timed out"):
            def late_error(command, **kwargs):
                output = Path(command[command.index("--output-last-message") + 1])
                output.write_text('{"verdict":"not_ready"}\n')
                raise review.EvaluationError(message)
            with self.subTest(message=message), mock.patch.object(review, "run_command", side_effect=late_error) as run:
                result, snapshot, attempts, replaced, error = review.run_review_with_replacement(
                    case, "broken", 60, replacement_available=True)
                self.assertEqual(result, {"verdict": "not_ready"})
                self.assertTrue(snapshot.startswith("sha256:"))
                self.assertEqual((attempts, replaced, error), (1, False, None))
                run.assert_called_once()

    def test_behavior_failure_and_replacement_keep_both_native_attempts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = evidence.create_run(directory, "behavior", {})
            original_popen = behavior.subprocess.Popen
            count = 0
            def fake_codex(command, **kwargs):
                nonlocal count
                count += 1
                self.assertIn("--json", command)
                output = command[command.index("--output-last-message") + 1]
                program = "import sys; print('{\"native_attempt\":%d}', flush=True); " % count
                if count == 1:
                    program += "sys.exit(7)"
                else:
                    program += f"from pathlib import Path; Path({output!r}).write_text('{{\"playbook\":\"usable\"}}')"
                return original_popen([sys.executable, "-B", "-c", program], **kwargs)
            with mock.patch.object(behavior.subprocess, "Popen", side_effect=fake_codex):
                outcome = behavior.run_scenario_with_replacement(
                    Path(directory), {"id": "same", "prompt": "route"}, None, 60,
                    replacement_available=True, evidence_dir=root)
            self.assertEqual(outcome, ({"playbook": "usable"}, 2, True, None))
            attempts = list(root.glob("behavior-same-*"))
            self.assertEqual(len(attempts), 2)
            self.assertEqual({json.loads((item / "process.json").read_text())["status"] for item in attempts},
                             {"nonzero", "succeeded"})
            self.assertEqual(sum((item / "final-result.json").is_file() for item in attempts), 1)

    def test_wrapper_retains_complete_stdout_without_printing_success_records(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.txt"
            result = release_smoke.run([sys.executable, "-c", "print('EXACT_REVIEW')"],
                                      os.environ.copy(), "review", output_path=output)
            self.assertEqual(result, "EXACT_REVIEW")
            self.assertEqual(output.read_text(), "EXACT_REVIEW\n")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                release_smoke.run([sys.executable, "-c", "import time; print('COMPLETE_REVIEW', flush=True); time.sleep(30)"],
                                  os.environ.copy(), "review", timeout_seconds=.25, output_path=output)
            self.assertEqual(output.read_text(), "COMPLETE_REVIEW\n")

    def test_evidence_cannot_be_written_in_candidate_or_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                evidence.validate_location(Path(directory) / "captures", Path(directory))


if __name__ == "__main__":
    unittest.main()
