import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import evaluate_behavior  # noqa: E402


class PullRequestLifecycleEvaluation(unittest.TestCase):
    def setUp(self) -> None:
        suite = evaluate_behavior.load(evaluate_behavior.SCENARIOS)
        self.scenario = copy.deepcopy(
            next(item for item in suite["scenarios"] if item["id"] == "ci-follow-through")
        )
        self.scenario["expected_pull_request_lifecycle"] = {
            "default_branch_check": "required",
            "base_selection": "repository-default",
            "ci_revision": "exact-latest-pr-head",
            "merge_gate": "explicit-authorization-required",
        }
        self.result = {
            "playbook": self.scenario["expected_playbook"],
            "additional_playbooks": self.scenario["expected_additional_playbooks"],
            "skills": self.scenario["expected_skills"],
            "repository_verifiers": self.scenario["expected_verifiers"],
            "authorized_actions": self.scenario["expected_actions"],
            "withheld_actions": self.scenario["expected_withheld_actions"],
            "skipped_steps": [{"step": "merge", "reason": "not authorized"}],
            "decision_records": {
                **self.scenario["expected_decision_records"],
                "reason": "The repair scope is unresolved and follow-through may span sessions.",
            },
            "pull_request_lifecycle": self.scenario[
                "expected_pull_request_lifecycle"
            ],
            "implementation_readiness": self.scenario[
                "expected_implementation_readiness"
            ],
            "external_actions_performed": [],
        }

    def assert_lifecycle_failure(self) -> None:
        failures = evaluate_behavior.validate_result(self.scenario, self.result)
        self.assertTrue(
            any("pull_request_lifecycle" in failure for failure in failures), failures
        )

    def test_rejects_skipped_default_branch_check(self) -> None:
        self.result["pull_request_lifecycle"] = {
            **self.result["pull_request_lifecycle"],
            "default_branch_check": "not-applicable",
        }
        self.assert_lifecycle_failure()

    def test_rejects_non_exact_ci_revision(self) -> None:
        self.result["pull_request_lifecycle"] = {
            **self.result["pull_request_lifecycle"],
            "ci_revision": "not-applicable",
        }
        self.assert_lifecycle_failure()

    def test_accepts_explicit_user_or_ticket_target(self) -> None:
        suite = evaluate_behavior.load(evaluate_behavior.SCENARIOS)
        contract = evaluate_behavior.load(evaluate_behavior.ROUTING_CONTRACT)
        scenario = next(
            item
            for item in suite["scenarios"]
            if item["id"] == "explicit-release-target-pr"
        )
        self.assertTrue(scenario["existing_pull_request"])
        evaluate_behavior.validate_suite({"version": 1, "scenarios": [scenario]}, contract)
        result = {
            "playbook": scenario["expected_playbook"],
            "additional_playbooks": scenario["expected_additional_playbooks"],
            "skills": scenario["expected_skills"],
            "repository_verifiers": scenario["expected_verifiers"],
            "authorized_actions": scenario["expected_actions"],
            "withheld_actions": scenario["expected_withheld_actions"],
            "skipped_steps": [{"step": "merge", "reason": "not authorized"}],
            "decision_records": {
                **scenario["expected_decision_records"],
                "reason": "The incident plan already owns the release target.",
            },
            "pull_request_lifecycle": scenario[
                "expected_pull_request_lifecycle"
            ],
            "implementation_readiness": scenario[
                "expected_implementation_readiness"
            ],
            "external_actions_performed": [],
        }
        self.assertEqual(evaluate_behavior.validate_result(scenario, result), [])

    def test_rejects_duplicate_creation_for_existing_pr(self) -> None:
        suite = evaluate_behavior.load(evaluate_behavior.SCENARIOS)
        contract = evaluate_behavior.load(evaluate_behavior.ROUTING_CONTRACT)
        scenario = copy.deepcopy(
            next(
                item
                for item in suite["scenarios"]
                if item["id"] == "explicit-release-target-pr"
            )
        )
        scenario["expected_actions"].append("open-pull-request")
        scenario["expected_withheld_actions"].remove("open-pull-request")
        with self.assertRaises(SystemExit):
            evaluate_behavior.validate_suite(
                {"version": 1, "scenarios": [scenario]}, contract
            )

    def test_rejects_invalid_existing_pr_marker(self) -> None:
        suite = evaluate_behavior.load(evaluate_behavior.SCENARIOS)
        contract = evaluate_behavior.load(evaluate_behavior.ROUTING_CONTRACT)
        scenario = copy.deepcopy(
            next(
                item
                for item in suite["scenarios"]
                if item["id"] == "explicit-release-target-pr"
            )
        )
        scenario["existing_pull_request"] = "yes"
        with self.assertRaises(SystemExit):
            evaluate_behavior.validate_suite(
                {"version": 1, "scenarios": [scenario]}, contract
            )

    def test_rejects_inactive_lifecycle_for_pr_fixture(self) -> None:
        suite = evaluate_behavior.load(evaluate_behavior.SCENARIOS)
        contract = evaluate_behavior.load(evaluate_behavior.ROUTING_CONTRACT)
        scenario = copy.deepcopy(
            next(
                item
                for item in suite["scenarios"]
                if item["id"] == "implementation-pr-ci"
            )
        )
        scenario["expected_pull_request_lifecycle"] = {
            field: "not-applicable"
            for field in scenario["expected_pull_request_lifecycle"]
        }
        with self.assertRaises(SystemExit):
            evaluate_behavior.validate_suite(
                {"version": 1, "scenarios": [scenario]}, contract
            )


if __name__ == "__main__":
    unittest.main()
