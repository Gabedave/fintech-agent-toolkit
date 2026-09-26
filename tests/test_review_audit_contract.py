import copy
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import evaluate_review_quality as quality


INVARIANT_AREAS = (
    "state", "ownership", "transaction", "external-outcome", "replay", "time",
    "recovery-observability",
)


def complete_record(*, failed=False, external_status="not-required"):
    status = "failed" if failed else "confirmed"
    return {
        "scope": "Synthetic candidate and documented acceptance behavior.",
        "candidate_snapshot": "sha256:synthetic",
        "final_snapshot": "sha256:synthetic",
        "risk": "high",
        "risk_rationale": "The candidate changes shared state across a critical boundary.",
        "criteria": [{
            "requirement": "The documented operation reaches its durable outcome.",
            "changed_seam": "flow.py -> support.py",
            "focused_evidence": "observe.py controlled replay",
            "broad_evidence": "python3 -B smoke.py",
            "status": status,
        }],
        "invariants": [{
            "area": area,
            "invariant": f"The {area} behavior remains safe.",
            "authority": "README.md",
            "changed_seam": "flow.py -> support.py",
            "executable_evidence": "observe.py controlled replay",
            "status": status if area == "state" else "not-applicable",
        } for area in INVARIANT_AREAS],
        "verification": ["python3 -B smoke.py"],
        "external_evidence": {"status": external_status, "sources": []},
        "decision_record": {
            "status": "not-required",
            "reference": "The fixture explicitly excludes an ADR.",
        },
        "remaining_risks": [],
        "reviewer_attempts": 1,
        "repair_cycles": 0,
        "independence": "performed",
        "consensus": "not-achieved" if failed else "achieved",
    }


def result(*, failed=False):
    findings = []
    if failed:
        findings.append({
            "file": "flow.py",
            "line": 4,
            "severity": "Major",
            "explanation": "The changed state boundary violates the requirement.",
            "remediation": "Refresh the state before finalizing the operation.",
            "reconciliation": "pending",
            "input": "{}",
            "observed": "{}",
            "expected": "{}",
        })
    return {
        "verdict": "not_ready" if failed else "ready",
        "review_record": complete_record(failed=failed),
        "findings": findings,
        "limitations": [],
    }


class ReviewAuditContract(unittest.TestCase):
    def setUp(self):
        self.case = {
            "id": "synthetic",
            "lines": [3, 8],
            "required_invariants": ["state"],
        }

    def test_complete_fixed_review_record_is_accepted(self):
        self.assertEqual(
            quality.score_review(
                self.case, "fixed", result(), expected_snapshot="sha256:synthetic"
            ),
            [],
        )

    def test_major_severity_is_accepted(self):
        candidate = result(failed=True)
        with mock.patch.object(quality, "replay", side_effect=[{}, {}]):
            errors = quality.score_review(
                self.case, "broken", candidate, expected_snapshot="sha256:synthetic"
            )
        self.assertNotIn("invalid finding severity or explanation", errors)

    def test_rejects_ready_record_with_failed_criteria(self):
        candidate = result()
        candidate["review_record"]["criteria"][0]["status"] = "failed"
        errors = quality.score_review(self.case, "fixed", candidate)
        self.assertTrue(any("failed criterion" in error for error in errors))

    def test_rejects_ready_record_with_unverified_external_evidence(self):
        candidate = result()
        candidate["review_record"]["external_evidence"]["status"] = "unverified"
        errors = quality.score_review(self.case, "fixed", candidate)
        self.assertTrue(any("unverified external evidence" in error for error in errors))

    def test_rejects_ready_record_with_unverified_or_failed_invariant(self):
        for status in ("unverified", "failed"):
            candidate = result()
            candidate["review_record"]["invariants"][1]["status"] = status
            errors = quality.score_review(self.case, "fixed", candidate)
            self.assertTrue(any("unverified or failed invariant" in error for error in errors))

    def test_scoring_same_record_is_repeatable(self):
        candidate = result()
        first = quality.score_review(self.case, "fixed", copy.deepcopy(candidate))
        second = quality.score_review(self.case, "fixed", copy.deepcopy(candidate))
        self.assertEqual(first, second)
        self.assertEqual(first, [])

    def test_all_not_applicable_audit_is_rejected(self):
        candidate = result()
        for invariant in candidate["review_record"]["invariants"]:
            invariant["status"] = "not-applicable"
            invariant["executable_evidence"] = "Generic non-applicability claim."
        errors = quality.score_review(self.case, "fixed", candidate)
        self.assertTrue(any("required invariant" in error for error in errors))

    def test_rejects_broken_candidate_with_ready_record(self):
        candidate = result()
        candidate["findings"] = [{
            **result(failed=True)["findings"][0],
            "severity": "Minor",
        }]
        errors = quality.score_review(self.case, "broken", candidate)
        self.assertTrue(any("seeded defect not blocked" in error for error in errors))

    def test_definitive_rejection_retains_unverified_residual_invariant(self):
        candidate = result(failed=True)
        candidate["review_record"]["invariants"][1]["status"] = "unverified"
        candidate["findings"][0]["expected"] = '{"fixed": true}'
        case = {**self.case, "required_invariants": ["state", "ownership"]}
        with mock.patch.object(quality, "replay", side_effect=[{}, {"fixed": True}]):
            errors = quality.score_review(case, "broken", candidate)
        self.assertEqual(errors, [])

    def test_definitive_rejection_retains_unverified_residual_criterion(self):
        candidate = result(failed=True)
        candidate["findings"][0]["expected"] = '{"fixed": true}'
        candidate["review_record"]["criteria"].append({
            **candidate["review_record"]["criteria"][0],
            "requirement": "A second material requirement is proven.",
            "status": "unverified",
        })
        with mock.patch.object(quality, "replay", side_effect=[{}, {"fixed": True}]):
            errors = quality.score_review(self.case, "broken", candidate)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
