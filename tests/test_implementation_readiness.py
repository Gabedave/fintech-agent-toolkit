import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import evaluate_behavior  # noqa: E402


SCENARIO_CLASSES = [
    "definitive-rejection",
    "ambiguous-outcome",
    "replay-idempotency",
    "concurrent-ownership",
    "state-identity-fencing",
]


class ImplementationReadinessEvaluation(unittest.TestCase):
    def setUp(self) -> None:
        suite = evaluate_behavior.load(evaluate_behavior.SCENARIOS)
        self.scenario = copy.deepcopy(
            next(item for item in suite["scenarios"] if item["id"] == "implementation-pr-ci")
        )
        expected_readiness = {
            "risk_classification": "high",
            "proof_gate": "adversarial-tests-before-production-edit",
            "scenario_classes": SCENARIO_CLASSES,
            "capability_preflight": "repository-declared-before-verification",
            "synthetic_merge": "required-before-push",
        }
        self.assertEqual(
            self.scenario["expected_implementation_readiness"], expected_readiness
        )
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
                "reason": "The change crosses a high-risk payment ownership boundary.",
            },
            "pull_request_lifecycle": self.scenario["expected_pull_request_lifecycle"],
            "implementation_readiness": copy.deepcopy(
                self.scenario["expected_implementation_readiness"]
            ),
            "external_actions_performed": [],
        }

    def assert_readiness_failure(self) -> None:
        failures = evaluate_behavior.validate_result(self.scenario, self.result)
        self.assertTrue(
            any("implementation_readiness" in failure for failure in failures), failures
        )

    def test_accepts_complete_high_risk_gate(self) -> None:
        self.assertEqual(evaluate_behavior.validate_result(self.scenario, self.result), [])

    def test_rejects_missing_adversarial_class(self) -> None:
        self.result["implementation_readiness"]["scenario_classes"].remove(
            "ambiguous-outcome"
        )
        self.assert_readiness_failure()

    def test_rejects_proof_deferred_until_review(self) -> None:
        self.result["implementation_readiness"]["proof_gate"] = "proportionate-before-edit"
        self.assert_readiness_failure()

    def test_rejects_missing_repository_capability_preflight(self) -> None:
        self.result["implementation_readiness"]["capability_preflight"] = "not-applicable"
        self.assert_readiness_failure()

    def test_rejects_branch_only_pull_request_readiness(self) -> None:
        self.result["implementation_readiness"]["synthetic_merge"] = "not-applicable"
        self.assert_readiness_failure()


if __name__ == "__main__":
    unittest.main()
