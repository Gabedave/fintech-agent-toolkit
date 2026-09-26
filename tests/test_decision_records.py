import copy
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import evaluate_behavior  # noqa: E402


class DecisionRecordEvaluation(unittest.TestCase):
    def setUp(self) -> None:
        suite = evaluate_behavior.load(evaluate_behavior.SCENARIOS)
        self.scenario = copy.deepcopy(next(
            item for item in suite["scenarios"]
            if item["id"] == "cross-repository-contract-change"
        ))
        self.scenario["expected_decision_records"] = {
            "adr_disposition": "required:owning-repository",
            "trail_disposition": "required:local",
        }
        self.result = {
            "playbook": self.scenario["expected_playbook"],
            "additional_playbooks": self.scenario["expected_additional_playbooks"],
            "skills": self.scenario["expected_skills"],
            "repository_verifiers": self.scenario["expected_verifiers"],
            "authorized_actions": self.scenario["expected_actions"],
            "withheld_actions": self.scenario["expected_withheld_actions"],
            "skipped_steps": [{"step": "push", "reason": "not authorized"}],
            "external_actions_performed": [],
            "pull_request_lifecycle": self.scenario[
                "expected_pull_request_lifecycle"
            ],
            "implementation_readiness": self.scenario[
                "expected_implementation_readiness"
            ],
            "decision_records": {
                **self.scenario["expected_decision_records"],
                "reason": "The change establishes a contract shared by backend and mobile.",
            },
        }

    def assert_record_failure(self) -> None:
        failures = evaluate_behavior.validate_result(self.scenario, self.result)
        self.assertTrue(any("decision_records" in failure for failure in failures), failures)

    def test_accepts_repository_adr_and_unpublished_trail(self) -> None:
        self.assertEqual(evaluate_behavior.validate_result(self.scenario, self.result), [])

    def test_rejects_missing_history_check_even_with_valid_adr_assessment(self) -> None:
        self.result["skills"] = [skill for skill in self.result["skills"] if skill != "why"]
        failures = evaluate_behavior.validate_result(self.scenario, self.result)
        self.assertTrue(any("outside the finite allowance" in failure for failure in failures), failures)

    def test_rejects_missing_assessment(self) -> None:
        del self.result["decision_records"]
        self.assert_record_failure()

    def test_rejects_skipping_durable_contract_decision(self) -> None:
        self.result["decision_records"]["adr_disposition"] = "not-required:none"
        self.assert_record_failure()

    def test_rejects_impossible_adr_disposition(self) -> None:
        self.result["decision_records"]["adr_disposition"] = "required:none"
        self.assert_record_failure()

    def test_rejects_unjustified_assessment(self) -> None:
        self.result["decision_records"]["reason"] = " "
        self.assert_record_failure()

    def test_rejects_non_object_assessment(self) -> None:
        for value in (None, [], "required"):
            with self.subTest(value=value):
                self.result["decision_records"] = value
                self.assert_record_failure()

    def test_rejects_unauthorized_trail_publication(self) -> None:
        self.result["decision_records"]["trail_disposition"] = "required:authorized-team-record"
        self.assert_record_failure()

    def test_rejects_omitted_long_running_trail(self) -> None:
        self.result["decision_records"]["trail_disposition"] = "not-required:not-applicable"
        self.assert_record_failure()

    def test_does_not_force_an_adr_for_routine_work(self) -> None:
        records = {
            "adr_disposition": "not-required:none",
            "trail_disposition": "not-required:not-applicable",
        }
        self.scenario["expected_decision_records"] = records
        self.result["decision_records"] = {**records, "reason": "Existing contract unchanged."}
        self.assertEqual(evaluate_behavior.validate_result(self.scenario, self.result), [])
        self.result["decision_records"]["adr_disposition"] = "required:owning-repository"
        self.assert_record_failure()

    def test_rejects_missing_expectation_in_release_fixture(self) -> None:
        suite = {"version": 1, "scenarios": [self.scenario]}
        del self.scenario["expected_decision_records"]
        contract = evaluate_behavior.load(evaluate_behavior.ROUTING_CONTRACT)
        with self.assertRaises(SystemExit):
            evaluate_behavior.validate_suite(suite, contract)

    def test_rejects_impossible_fixture_dispositions(self) -> None:
        for field, value in (
            ("adr_disposition", "required:none"),
            ("trail_disposition", "required:not-applicable"),
        ):
            scenario = copy.deepcopy(self.scenario)
            scenario["expected_decision_records"][field] = value
            with self.subTest(field=field), self.assertRaises(SystemExit):
                evaluate_behavior.validate_suite(
                    {"version": 1, "scenarios": [scenario]},
                    evaluate_behavior.load(evaluate_behavior.ROUTING_CONTRACT),
                )

    def test_rejects_unknown_assessment_values(self) -> None:
        self.result["decision_records"]["adr_disposition"] = "maybe"
        self.assert_record_failure()

    def test_accepts_duplicate_identical_withheld_action(self) -> None:
        self.result["withheld_actions"] = [*self.result["withheld_actions"], "merge"]
        self.assertEqual(evaluate_behavior.validate_result(self.scenario, self.result), [])

    def test_all_release_scenarios_accept_their_expected_assessments(self) -> None:
        suite = evaluate_behavior.load(evaluate_behavior.SCENARIOS)
        for scenario in suite["scenarios"]:
            with self.subTest(scenario=scenario["id"]):
                records = scenario["expected_decision_records"]
                self.assertEqual(evaluate_behavior.decision_record_errors(records, include_reason=False), [])
                result = {
                    "playbook": scenario["expected_playbook"],
                    "additional_playbooks": scenario["expected_additional_playbooks"],
                    "skills": scenario["expected_skills"],
                    "repository_verifiers": scenario["expected_verifiers"],
                    "authorized_actions": scenario["expected_actions"],
                    "withheld_actions": scenario["expected_withheld_actions"],
                    "skipped_steps": [{"step": "deploy", "reason": "not requested"}],
                    "external_actions_performed": [],
                    "pull_request_lifecycle": scenario[
                        "expected_pull_request_lifecycle"
                    ],
                    "decision_records": {**records, "reason": "Fixture acceptance check."},
                }
                if "expected_implementation_readiness" in scenario:
                    result["implementation_readiness"] = scenario[
                        "expected_implementation_readiness"
                    ]
                self.assertEqual(evaluate_behavior.validate_result(scenario, result), [])

    def test_policy_defines_adr_disposition_precedence(self) -> None:
        policy = (
            ROOT
            / "plugins"
            / "fintech-engineering"
            / "skills"
            / "architect"
            / "references"
            / "decision-records.md"
        ).read_text()
        precedence = policy.split("## Classification precedence", 1)[1].split(
            "## Ownership and lifecycle", 1
        )[0]
        dispositions = re.findall(
            r"`((?:not-required:none|required:owning-repository|"
            r"assess-after-discovery:undetermined))`",
            precedence,
        )
        self.assertEqual(
            dispositions,
            [
                "not-required:none",
                "required:owning-repository",
                "assess-after-discovery:undetermined",
            ],
        )
        self.assertIn("read-only investigation", precedence)
        self.assertIn("requested outcome", precedence)
        self.assertIn("historical evidence", precedence)

    def test_shared_policy_and_template_links_resolve(self) -> None:
        plugin = ROOT / "plugins" / "fintech-engineering"
        files = [*plugin.rglob("*.md"), *(ROOT / "docs").rglob("*.md")]
        for path in files:
            for target in re.findall(r"\[[^\]]+\]\(([^)\s]+)\)", path.read_text()):
                if "://" in target or target.startswith("#"):
                    continue
                target_path = (path.parent / target.split("#", 1)[0]).resolve()
                with self.subTest(source=path.relative_to(ROOT), target=target):
                    self.assertTrue(target_path.is_relative_to(ROOT), "Link escapes the repository")
                    self.assertTrue(target_path.exists(), "Missing linked policy or resource")


if __name__ == "__main__":
    unittest.main()
