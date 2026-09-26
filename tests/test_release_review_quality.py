import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import release_smoke


ROOT = Path(__file__).resolve().parents[1]
QUALITY_OUTPUT = "\n".join([
    '{"case":"synthetic/fixed","review":{"verdict":"ready"}}',
    "Review-quality pilot: 4/4 defects reproduced, 4/4 fixed controls accepted, "
    "0 fixed controls with false blockers; 8/8 results; 10.0s",
    "Review-quality pilot passed (8/8 cases); synthetic evidence, not a general "
    "accuracy estimate",
])


class ReleaseReviewQuality(unittest.TestCase):
    def run_release(self, include_quality, changed=False, backend_dirty=False,
                    backend_changed=False, verbose_quality=False,
                    quality_output=QUALITY_OUTPUT, expected_failure=False):
        calls = []
        state = []

        def fake_run(command, env, label, **kwargs):
            state.append(Path(env["CODEX_HOME"]))
            self.assertTrue((state[-1] / "auth.json").is_symlink())
            self.assertEqual(env["PYTHONDONTWRITEBYTECODE"], "1")
            calls.append((command, label))
            self.assertGreater(kwargs.get("timeout_seconds", 0), 0)
            if "evaluate_behavior.py" in " ".join(command):
                scenario_count = len(release_smoke.json.loads(
                    release_smoke.SCENARIOS.read_text()
                )["scenarios"])
                self.assertEqual(
                    kwargs["timeout_seconds"],
                    release_smoke.suite_timeout(
                        scenario_count
                        + release_smoke.MAX_BEHAVIOR_OPERATIONAL_REPLACEMENTS,
                        120,
                    ),
                )
            if "evaluate_review_quality.py" in " ".join(command):
                self.assertTrue(kwargs.get("report_stdout_on_failure"))
                pair_count = len(release_smoke.json.loads(
                    release_smoke.REVIEW_CASES.read_text()
                )["cases"])
                self.assertEqual(
                    kwargs["timeout_seconds"],
                    release_smoke.suite_timeout(
                        2 * pair_count + release_smoke.MAX_REVIEW_OPERATIONAL_REPLACEMENTS,
                        120,
                        120,
                    ),
                )
                return quality_output
            return "passed"

        statuses = iter(["", " M changed"] if changed else ["", ""])
        def fake_git(*args):
            return next(statuses) if args[0] == "status" else "candidate-commit"

        backend_statuses = iter(
            [" M local"] if backend_dirty else
            (["", " M changed"] if backend_changed else ["", ""])
        )
        def fake_backend_git(repo, *args):
            return next(backend_statuses) if args[0] == "status" else "backend-commit"

        with tempfile.TemporaryDirectory() as directory:
            auth = Path(directory) / "synthetic-auth.json"
            auth.write_text("{}")
            argv = ["release_smoke.py", "--repo", directory, "--auth-file", str(auth)]
            if include_quality:
                argv.append("--review-quality")
            if verbose_quality:
                argv.append("--verbose-review-output")
            with mock.patch.object(sys, "argv", argv), mock.patch.object(
                release_smoke, "run", side_effect=fake_run
            ), mock.patch.object(
                release_smoke, "git_output", side_effect=fake_git
            ), mock.patch.object(
                release_smoke, "backend_git_output", side_effect=fake_backend_git
            ):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    if changed or backend_dirty or backend_changed or expected_failure:
                        with self.assertRaises(SystemExit):
                            release_smoke.main()
                    else:
                        release_smoke.main()
            self.assertEqual(auth.read_text(), "{}")
        self.assertTrue(all(not path.exists() for path in state))
        return calls, output.getvalue()

    def test_quality_adds_to_routing_in_same_disposable_installation(self):
        calls, output = self.run_release(True)
        self.assertEqual(len(calls), 4)
        self.assertIn("evaluate_behavior.py", " ".join(calls[2][0]))
        self.assertIn("--timeout-seconds", calls[2][0])
        self.assertIn("evaluate_review_quality.py", " ".join(calls[3][0]))
        self.assertIn("--run", calls[3][0])
        self.assertIn("-B", calls[3][0])
        self.assertIn("--timeout-seconds", calls[3][0])
        self.assertIn("Example backend commit: backend-commit", output)

    def test_default_release_retains_existing_routing_only_scope(self):
        calls, _ = self.run_release(False)
        self.assertEqual(len(calls), 3)

    def test_pr_template_uses_dynamic_review_pair_language(self):
        template = (ROOT / ".github" / "pull_request_template.md").read_text()
        self.assertIn("all configured broken/fixed pairs", template)
        self.assertNotIn("all six cases", template)

    def test_successful_release_prints_review_summary_only_by_default(self):
        _, output = self.run_release(True)
        self.assertIn("Review-quality pilot: 4/4 defects reproduced", output)
        self.assertIn("Review-quality pilot passed (8/8 cases)", output)
        self.assertNotIn('"review"', output)

    def test_verbose_release_can_print_complete_successful_reviews(self):
        _, output = self.run_release(True, verbose_quality=True)
        self.assertIn('"review"', output)

    def test_successful_pilot_without_complete_summary_is_rejected(self):
        with mock.patch.object(release_smoke, "fail", side_effect=SystemExit) as fail:
            with self.assertRaises(SystemExit):
                release_smoke.review_quality_summary(
                    "Review-quality pilot: 4/4 defects reproduced"
                )
        fail.assert_called_once_with(
            "review-quality pilot succeeded without its required summary"
        )

    def test_summary_failure_preserves_complete_pilot_output(self):
        malformed_output = "\n".join([
            '{"case":"synthetic/fixed","review":{"verdict":"ready"}}',
            "Review-quality pilot: 4/4 defects reproduced, 4/4 fixed controls "
            "accepted, 0 fixed controls with false blockers; 8/8 results; 10.0s",
        ])
        _, output = self.run_release(
            True, quality_output=malformed_output, expected_failure=True
        )
        self.assertIn('"review"', output)
        self.assertIn("Review-quality pilot: 4/4 defects reproduced", output)

    def test_verbose_output_requires_review_quality(self):
        with tempfile.TemporaryDirectory() as directory:
            auth = Path(directory) / "synthetic-auth.json"
            auth.write_text("{}")
            argv = [
                "release_smoke.py", "--repo", directory,
                "--auth-file", str(auth), "--verbose-review-output",
            ]
            with mock.patch.object(sys, "argv", argv), self.assertRaises(SystemExit):
                release_smoke.main()

    def test_candidate_drift_invalidates_proof(self):
        self.run_release(True, changed=True)

    def test_dirty_backend_checkout_is_rejected(self):
        self.run_release(True, backend_dirty=True)

    def test_backend_drift_invalidates_proof(self):
        self.run_release(True, backend_changed=True)

    def test_unresponsive_behavior_child_times_out_and_is_stopped(self):
        with tempfile.TemporaryDirectory() as directory:
            pid_file = Path(directory) / "child.pid"
            program = (
                "import os,time; from pathlib import Path; "
                f"Path({str(pid_file)!r}).write_text(str(os.getpid())); "
                "print('RAW_DIAGNOSTIC', flush=True); time.sleep(30)"
            )
            output = io.StringIO()
            errors = io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(
                errors
            ), self.assertRaises(SystemExit):
                release_smoke.run(
                    [sys.executable, "-B", "-c", program],
                    os.environ.copy(),
                    "installed-candidate behavior suite",
                    timeout_seconds=0.5,
                )
            self.assertIn("timed out", errors.getvalue())
            self.assertNotIn("RAW_DIAGNOSTIC", output.getvalue())
            pid = int(pid_file.read_text())
            with self.assertRaises(ProcessLookupError):
                os.kill(pid, 0)

    def test_timed_out_pilot_preserves_completed_reviews_and_counts(self):
        command = [
            sys.executable,
            "-c",
            "import time; print('STRUCTURED_REVIEW', flush=True); "
            "print('PILOT_COUNTS', flush=True); time.sleep(30)",
        ]
        output = io.StringIO()
        errors = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(
            errors
        ), self.assertRaises(SystemExit):
            release_smoke.run(
                command,
                os.environ.copy(),
                "quality pilot",
                timeout_seconds=0.5,
                report_stdout_on_failure=True,
            )
        self.assertIn("STRUCTURED_REVIEW", output.getvalue())
        self.assertIn("PILOT_COUNTS", output.getvalue())
        self.assertIn("timed out", errors.getvalue())

    def test_failed_pilot_preserves_reviews_and_counts_even_with_stderr(self):
        command = [sys.executable, "-c",
                   "import sys; print('STRUCTURED_REVIEW'); print('PILOT_COUNTS'); "
                   "print('ERROR: false blocker', file=sys.stderr); sys.exit(1)"]
        output = io.StringIO()
        errors = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors), self.assertRaises(SystemExit):
            release_smoke.run(command, os.environ.copy(), "quality pilot",
                              report_stdout_on_failure=True)
        self.assertIn("STRUCTURED_REVIEW", output.getvalue())
        self.assertIn("PILOT_COUNTS", output.getvalue())
        self.assertIn("false blocker", errors.getvalue())

    def test_other_commands_do_not_gain_raw_stdout_reporting(self):
        command = [sys.executable, "-c",
                   "import sys; print('RAW_DIAGNOSTIC'); "
                   "print('safe failure', file=sys.stderr); sys.exit(1)"]
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit):
            release_smoke.run(command, os.environ.copy(), "other command")
        self.assertNotIn("RAW_DIAGNOSTIC", output.getvalue())


if __name__ == "__main__":
    unittest.main()
