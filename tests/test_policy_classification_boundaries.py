"""Source-contract guards for independently frozen classification boundaries.

These wording guards do not establish native model compliance or rescore failures.
"""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "foundation/plugin/skills"


def instruction(path):
    return " ".join((SKILLS / path).read_text().split())


class PolicyClassificationBoundaries(unittest.TestCase):
    def test_unresolved_discovery_is_distinct_from_established_requirements(self):
        text = instruction("{{ROUTER}}/references/implementation-readiness.md")
        for clause in ("Separate open assessment questions from established obligations",
                       "When resource exposure is unresolved, state what discovery must determine",
                       "do not present material-growth requirements as already applicable",
                       "only after evidence supports a material-growth classification"):
            self.assertIn(clause, text)

    def test_material_growth_still_requires_all_existing_proof_boundaries(self):
        text = instruction("{{ROUTER}}/references/implementation-readiness.md")
        for clause in ("For material growth", "expected and peak workload", "ceiling",
                       "concurrency and replica effects", "cleanup or expiry",
                       "safe behaviour at the ceiling", "repository-owned check",
                       "aggregate production signal", "fix intended to reduce existing growth",
                       "rather than deleting financial truth", "Do not invent universal numerical budgets"):
            self.assertIn(clause, text)

    def test_correctness_risk_and_missing_discovery_do_not_establish_exposure(self):
        text = instruction("{{ROUTER}}/references/implementation-readiness.md")
        self.assertIn("independently of correctness risk", text)
        self.assertIn("does not itself establish a growth exposure", text)
        self.assertIn("not-material` with a concrete reason", text)
        self.assertIn("finish the assessment before changing production code", text)

    def test_external_citations_do_not_hold_local_research_rationale(self):
        text = instruction("pre-push-review/references/review-protocol.md")
        for clause in ("Keep source citations separate from the reason",
                       "Repository files, local checks and the rationale",
                       "belong in local verification or limitations",
                       "without adding local rationale as an external citation"):
            self.assertIn(clause, text)

    def test_external_evidence_requires_actual_consultation_not_live_network(self):
        text = instruction("pre-push-review/references/review-protocol.md")
        for clause in ("externally authored references actually consulted",
                       "supplied or cached official reference", "applicable version and provenance",
                       "mere mention or suggested link is not consultation",
                       "does not require unnecessary browsing"):
            self.assertIn(clause, text)

    def test_essential_unavailable_outside_evidence_remains_unverified(self):
        text = instruction("pre-push-review/references/external-evidence.md")
        self.assertIn("When essential current evidence cannot be verified", text)
        self.assertIn("mark the conclusion `unverified`", text)
        self.assertIn("if it can change the verdict, use `REVIEW INCOMPLETE`", text)


if __name__ == "__main__":
    unittest.main()
