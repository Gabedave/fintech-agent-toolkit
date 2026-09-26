import contextlib
import copy
import io
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import evaluate_review_quality as quality


def review_record(required_invariants=("state",), failed=True, snapshot="sha256:synthetic"):
    criterion_status = "failed" if failed else "confirmed"
    first_required = required_invariants[0]
    return {
        "scope": "Synthetic candidate and documented acceptance behavior.",
        "candidate_snapshot": snapshot,
        "final_snapshot": snapshot,
        "risk": "high",
        "risk_rationale": "The candidate changes shared state across a critical boundary.",
        "criteria": [{
            "requirement": "The documented operation reaches its durable outcome.",
            "changed_seam": "flow.py -> support.py",
            "focused_evidence": "observe.py controlled replay",
            "broad_evidence": "python3 -B smoke.py",
            "status": criterion_status,
        }],
        "invariants": [{
            "area": area,
            "invariant": f"The {area} behavior follows the documented flow.",
            "authority": "README.md",
            "changed_seam": "flow.py -> support.py",
            "executable_evidence": "Source trace and bounded local replay.",
            "status": (
                "failed" if failed and area == first_required else
                "confirmed" if area in required_invariants else
                "not-applicable"
            ),
        } for area in sorted(quality.INVARIANT_AREAS)],
        "verification": ["python3 -B smoke.py and observe.py replay"],
        "external_evidence": {"status": "not-required", "sources": []},
        "decision_record": {
            "status": "not-required",
            "reference": "The synthetic fixture explicitly excludes an ADR.",
        },
        "remaining_risks": [],
        "reviewer_attempts": 1,
        "repair_cycles": 0,
        "independence": "performed",
        "consensus": "not-achieved" if failed else "achieved",
    }


class ReviewQualityScoring(unittest.TestCase):
    def setUp(self):
        self.case = {"id": "sample", "lines": [3, 8], "required_invariants": ["state"]}
        self.result = {
            "verdict": "not_ready",
            "review_record": review_record(),
            "findings": [{
                "file": "flow.py", "line": 5, "severity": "Major",
                "explanation": "The next step consumes an outdated snapshot.",
                "remediation": "Refresh the snapshot before the next step.",
                "reconciliation": "pending",
                "input": '{"enabled": false}',
                "observed": '{"state": "failed"}',
                "expected": '{"state": "active"}',
            }],
            "limitations": [],
        }

    def score(self, variant="broken"):
        def replay(case, selected, inputs):
            return {"state": "failed" if selected == "broken" else "active"}
        with mock.patch.object(quality, "replay", side_effect=replay):
            return quality.score_review(self.case, variant, self.result)

    def test_accepts_executable_counterexample(self):
        self.assertEqual(self.score(), [])

    def test_does_not_grade_explanation_keywords(self):
        self.result["findings"][0]["explanation"] = "This violates the stated completion contract."
        self.assertEqual(self.score(), [])

    def test_rejects_fabricated_observations(self):
        self.result["findings"][0]["observed"] = '{"state": "invented"}'
        self.assertTrue(self.score())

    def test_rejects_invented_expected_behavior(self):
        self.result["findings"][0]["expected"] = '{"state": "invented"}'
        self.assertTrue(self.score())

    def test_rejects_non_counterexample(self):
        with mock.patch.object(quality, "replay", return_value={"state": "active"}):
            self.assertTrue(quality.score_review(self.case, "broken", self.result))

    def test_rejects_wrong_location_and_low_only_findings(self):
        for key, value in (("file", "support.py"), ("line", 20), ("severity", "Minor")):
            original = copy.deepcopy(self.result)
            self.result["findings"][0][key] = value
            self.assertTrue(self.score())
            self.result = original

    def test_rejects_false_blocker_on_fixed_control(self):
        self.assertTrue(self.score("fixed"))

    def test_accepts_ready_fixed_control(self):
        self.result.update(
            verdict="ready", findings=[],
            review_record=review_record(failed=False),
        )
        self.assertEqual(self.score("fixed"), [])
        self.assertTrue(self.score("broken"))

    def test_rejects_incomplete_even_without_findings(self):
        self.result.update(verdict="incomplete", findings=[])
        self.assertTrue(self.score("fixed"))

    def test_rejects_malformed_reproduction_without_executing_it(self):
        for value in ("not json", "[]", "null", "x" * 5000):
            self.result["findings"][0]["input"] = value
            with mock.patch.object(quality, "replay") as replay:
                self.assertTrue(quality.score_review(self.case, "broken", self.result))
                replay.assert_not_called()

    def test_rejects_malformed_model_results(self):
        for result in (None, [], {}, {**self.result, "findings": "bad"},
                       {**self.result, "limitations": [7]},
                       {**self.result, "limitations": [""]},
                       {**self.result, "review_record": {}}):
            self.assertTrue(quality.score_review(self.case, "broken", result))

    def test_rejects_empty_finding_evidence(self):
        for key in ("explanation", "remediation", "input", "observed", "expected"):
            candidate = copy.deepcopy(self.result)
            candidate["findings"][0][key] = ""
            self.assertTrue(quality.score_review(self.case, "broken", candidate))

    def test_requires_every_invariant_area_exactly_once(self):
        missing = copy.deepcopy(self.result)
        missing["review_record"]["invariants"].pop()
        duplicate = copy.deepcopy(self.result)
        duplicate["review_record"]["invariants"][-1]["area"] = (
            duplicate["review_record"]["invariants"][0]["area"]
        )
        for result in (missing, duplicate):
            self.assertTrue(quality.score_review(self.case, "broken", result))

    def test_additional_unreproduced_blocker_fails(self):
        self.result["findings"].append({**self.result["findings"][0], "expected": '{}'})
        self.assertTrue(self.score())

    def test_accepts_additional_reproduced_coverage_blocker(self):
        self.result["findings"].append({
            **self.result["findings"][0],
            "file": "smoke.py",
            "line": 12,
            "explanation": "The existing checks omit the reproduced failure case.",
        })
        self.assertEqual(self.score(), [])

    def test_timeout_is_a_failure(self):
        with self.assertRaises(quality.EvaluationError):
            quality.run_command([sys.executable, "-c", "import time; time.sleep(5)"],
                                timeout=0.05)

    def test_subprocess_errors_do_not_echo_raw_output(self):
        with self.assertRaises(quality.EvaluationError) as failure:
            quality.run_command([sys.executable, "-c",
                                 "import sys; print('PRIVATE'); sys.exit(1)"], timeout=5)
        self.assertNotIn("PRIVATE", str(failure.exception))

    def test_provider_environment_is_not_inherited(self):
        with mock.patch.dict(os.environ, {"QUALITY_FAKE_SECRET": "sentinel"}):
            output = quality.run_command([sys.executable, "-c",
                                          "import os; print(os.getenv('QUALITY_FAKE_SECRET', 'absent'))"],
                                         timeout=5)
        self.assertEqual(output.strip(), "absent")

    def test_timeout_also_terminates_children(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "child-was-not-stopped"
            child = f"import time; from pathlib import Path; time.sleep(.3); Path({str(marker)!r}).touch()"
            parent = f"import subprocess,time; subprocess.Popen([{sys.executable!r}, '-c', {child!r}]); time.sleep(5)"
            with self.assertRaises(quality.EvaluationError):
                quality.run_command([sys.executable, "-c", parent], timeout=.15)
            time.sleep(.4)
            self.assertFalse(marker.exists())


class ReviewQualityFixtures(unittest.TestCase):
    def test_manifest_matches_fixture_authority_and_fault_seam(self):
        cases = {case["id"]: case for case in quality.load_suite()}
        self.assertNotIn("replay", cases["stale-state"]["required_invariants"])
        self.assertNotIn("transaction", cases["stale-state"]["required_invariants"])
        self.assertEqual(cases["concurrent-ownership"]["lines"], [2, 6])

    def test_prompt_declares_harness_owned_review_context(self):
        prompt = " ".join(quality.build_prompt("sha256:synthetic").split())
        self.assertIn("context-isolated independent reviewer", prompt)
        self.assertIn("reviewer_attempts as 1", prompt)
        self.assertIn("repair_cycles as 0", prompt)
        self.assertIn("Do not delegate a replacement reviewer", prompt)
        self.assertIn("takes precedence and means not_ready", prompt)
        self.assertIn("consensus is achieved only", prompt)

    def test_replacement_prompt_reports_second_attempt_without_prior_findings(self):
        prompt = " ".join(
            quality.build_prompt("sha256:synthetic", reviewer_attempts=2).split()
        )
        self.assertIn("sole operational replacement", prompt)
        self.assertIn("reviewer_attempts as 2", prompt)
        self.assertIn("received no prior findings", prompt)

    def test_prompt_defines_compound_invariant_applicability(self):
        prompt = " ".join(quality.build_prompt("sha256:synthetic").split())
        self.assertIn(
            "recovery, reconciliation, observability, or a manual gate", prompt
        )

    def test_prompt_bounds_review_work_and_output(self):
        prompt = " ".join(quality.build_prompt("sha256:synthetic").split())
        self.assertIn("at most six local commands total", prompt)
        self.assertIn("Do not run py_compile", prompt)
        self.assertIn("verification to at most six concise entries", prompt)
        self.assertIn("Do not repeat the same explanation", prompt)

    def test_pause_fixture_names_its_recovery_observability_authority(self):
        authority = (
            quality.FIXTURES / "paused-cleanup" / "README.md"
        ).read_text()
        self.assertIn("retention maintenance is the recovery behavior", authority)
        self.assertIn("complete observable post-state", authority)

    def test_real_fixture_pairs_and_scorer(self):
        cases = quality.load_suite()
        quality.check_fixtures(cases)
        for case in cases:
            example = case["counterexample"]
            review = {
                "verdict": "not_ready",
                "review_record": review_record(case["required_invariants"]),
                "limitations": [],
                "findings": [{
                    "file": "flow.py", "line": case["lines"][0], "severity": "Major",
                    "explanation": "Counterexample violates the stated contract.",
                    "remediation": "Repair the changed boundary and retain this regression.",
                    "reconciliation": "pending",
                    "input": json.dumps(example["input"]),
                    "observed": json.dumps(example["broken"]),
                    "expected": json.dumps(example["fixed"]),
                }],
            }
            with self.subTest(case=case["id"]):
                self.assertEqual(quality.score_review(case, "broken", review), [])
                self.assertTrue(quality.score_review(case, "fixed", review))
                self.assertEqual(quality.score_review(case, "fixed", {
                    "verdict": "ready",
                    "review_record": review_record(
                        case["required_invariants"], failed=False
                    ),
                    "findings": [], "limitations": []}), [])

    def test_replay_rejects_inputs_outside_public_contract(self):
        for case in quality.load_suite():
            with self.subTest(case=case["id"]), self.assertRaises(quality.EvaluationError):
                quality.replay(case, "broken", {"unexpected": "data, never code"})

    def test_only_one_candidate_and_no_answer_keys_reach_model(self):
        case = quality.load_suite()[0]
        visited = []

        def fake_codex(command, **kwargs):
            workspace = Path(kwargs["cwd"])
            visited.append(workspace)
            self.assertEqual(set(path.name for path in workspace.iterdir()),
                             {*quality.PUBLIC_FILES, "flow.py", "response.schema.json"})
            self.assertEqual((workspace / "flow.py").read_text(),
                             (quality.FIXTURES / case["id"] / "broken.py").read_text())
            self.assertIn("read-only", command)
            self.assertIn("--ephemeral", command)
            self.assertEqual(kwargs["timeout"], 60)
            snapshot = quality.snapshot_identity(workspace)
            self.assertIn(snapshot, kwargs["input_text"])
            (workspace / "review.json").write_text(json.dumps({
                "verdict": "not_ready",
                "review_record": review_record(
                    case["required_invariants"], snapshot=snapshot
                ),
                "findings": [], "limitations": []}))
            return ""

        with mock.patch.object(quality, "run_command", side_effect=fake_codex):
            quality.run_review(case, "broken", 60)
        self.assertTrue(visited)
        self.assertFalse(visited[0].exists())

    def test_fixed_control_can_carry_its_regression_test(self):
        case = quality.load_suite()[0]
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            quality.materialize(case, "fixed", workspace)
            smoke = (workspace / "smoke.py").read_text()
        self.assertIn("test_recovered_card_completes_once", smoke)
        self.assertNotIn(
            "test_recovered_card_completes_once",
            (quality.FIXTURES / case["id"] / "smoke.py").read_text(),
        )

    def test_detects_model_fixture_mutation_and_cleans_up(self):
        case = quality.load_suite()[0]
        visited = []

        def fake_codex(command, **kwargs):
            workspace = Path(kwargs["cwd"])
            visited.append(workspace)
            (workspace / "flow.py").write_text("changed")
            (workspace / "review.json").write_text("{}")
            return ""

        with mock.patch.object(quality, "run_command", side_effect=fake_codex):
            with self.assertRaises(quality.EvaluationError):
                quality.run_review(case, "fixed", 60)
        self.assertFalse(visited[0].exists())

    def test_one_operational_replacement_can_supply_a_usable_review(self):
        case = quality.load_suite()[0]
        usable = ({"review_record": {"reviewer_attempts": 2}}, "sha256:fixed")
        with mock.patch.object(
            quality, "run_review",
            side_effect=[quality.EvaluationError("first failed"), usable],
        ) as run_review:
            result = quality.run_review_with_replacement(
                case, "fixed", 60, replacement_available=True
            )
        self.assertEqual(result, (*usable, 2, True, None))
        self.assertEqual(
            [call.kwargs["reviewer_attempts"] for call in run_review.call_args_list],
            [1, 2],
        )

    def test_usable_report_is_never_retried_for_another_verdict(self):
        case = quality.load_suite()[0]
        usable = ({"verdict": "incomplete"}, "sha256:usable")
        with mock.patch.object(quality, "run_review", return_value=usable) as run_review:
            result = quality.run_review_with_replacement(
                case, "fixed", 60, replacement_available=True
            )
        self.assertEqual(result, (*usable, 1, False, None))
        run_review.assert_called_once()

    def test_operational_replacement_is_not_available_after_budget_is_used(self):
        case = quality.load_suite()[0]
        with mock.patch.object(
            quality, "run_review", side_effect=quality.EvaluationError("failed")
        ) as run_review:
            result = quality.run_review_with_replacement(
                case, "fixed", 60, replacement_available=False
            )
        self.assertEqual(result[:4], (None, None, 1, False))
        self.assertIsInstance(result[4], quality.EvaluationError)
        run_review.assert_called_once()

    def test_coordinator_consumes_one_replacement_and_scores_attempt_two(self):
        cases = [
            {"id": "first", "lines": [1, 1], "required_invariants": ["state"]},
            {"id": "second", "lines": [1, 1], "required_invariants": ["state"]},
        ]
        snapshot = "sha256:replacement"
        replacement_record = review_record(
            required_invariants=("state",), failed=False, snapshot=snapshot
        )
        replacement_record["reviewer_attempts"] = 2
        replacement_result = {
            "verdict": "ready",
            "review_record": replacement_record,
            "findings": [],
            "limitations": [],
        }
        outcomes = [
            (replacement_result, snapshot, 2, True, None),
            (None, None, 1, False, quality.EvaluationError("second failed")),
        ]
        version = json.loads(quality.evaluate_behavior.MANIFEST.read_text())["version"]
        output = io.StringIO()
        errors = io.StringIO()
        argv = ["evaluate_review_quality.py", "--run"]
        with mock.patch.object(sys, "argv", argv), mock.patch.object(
            quality, "load_suite", return_value=cases
        ), mock.patch.object(
            quality, "check_fixtures"
        ), mock.patch.object(
            quality.evaluate_behavior, "installed_plugin", return_value={"version": version}
        ), mock.patch.object(
            quality, "VARIANTS", ("fixed",)
        ), mock.patch.object(
            quality, "run_review_with_replacement", side_effect=outcomes
        ) as run_case, mock.patch.object(
            quality, "score_review", wraps=quality.score_review
        ) as score, contextlib.redirect_stdout(output), contextlib.redirect_stderr(
            errors
        ), self.assertRaises(SystemExit):
            quality.main()

        self.assertEqual(
            [call.kwargs["replacement_available"] for call in run_case.call_args_list],
            [True, False],
        )
        self.assertEqual(score.call_args.kwargs["expected_reviewer_attempts"], 2)
        self.assertIn("1/1 operational replacements used", output.getvalue())
        self.assertIn("1/2 results", output.getvalue())
        self.assertIn("second/fixed: second failed", errors.getvalue())

    def test_rejects_traversal_duplicate_and_non_distinguishing_cases(self):
        original = json.loads(quality.SUITE.read_text())
        for mutate in (
            lambda suite: suite["cases"][0].update(id="../escape"),
            lambda suite: suite["cases"][1].update(id=suite["cases"][0]["id"]),
            lambda suite: suite["cases"][0]["counterexample"].update(
                fixed=suite["cases"][0]["counterexample"]["broken"]),
            lambda suite: suite["cases"].pop(),
        ):
            suite = copy.deepcopy(original)
            mutate(suite)
            with tempfile.TemporaryDirectory() as directory:
                manifest = Path(directory) / "cases.json"
                manifest.write_text(json.dumps(suite))
                with mock.patch.object(quality, "SUITE", manifest):
                    with self.assertRaises(quality.EvaluationError):
                        quality.load_suite()


if __name__ == "__main__":
    unittest.main()
