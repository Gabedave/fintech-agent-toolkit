"""Static instruction-contract guards; native model behavior needs separate runs.

These guard the independently fixed local/hosted and durable-storage requirements.
They do not establish agent compliance, storage execution or product CI coverage.
"""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "foundation/plugin/skills"


class LocalWorkflowContract(unittest.TestCase):
    def test_supplied_source_scope_is_explicit_and_can_proceed_offline(self):
        text = (SKILLS / "how/SKILL.md").read_text()
        self.assertIn("## Choose source scope", text)
        for requirement in ("explicit task/source context", "supplied-source explanation",
                            "host inspection is not a prerequisite", "paths and lines",
                            "canonical currency and production behavior remain unverified"):
            self.assertIn(requirement.casefold(), text.casefold())

    def test_hosted_current_source_keeps_authority_and_read_only_gate(self):
        text = (SKILLS / "how/SKILL.md").read_text()
        for requirement in ("default branch and authoritative base SHA from its host",
                            "snapshot helper", "exact head, divergence, authority state, and dirty state",
                            "must not update or clean the user's checkout"):
            self.assertIn(requirement, text)

    def test_offline_or_missing_remote_does_not_exempt_hosted_claims(self):
        text = (SKILLS / "how/SKILL.md").read_text()
        for requirement in ("missing remote, network restriction or failed host command",
                            "does not change the source scope", "hosted current-source claims remain blocked"):
            self.assertIn(requirement, text)

    def test_explanation_covers_domain_outcome_meaning(self):
        text = (SKILLS / "how/references/explanation.md").read_text()
        self.assertIn("final success, terminal failure, pending work or human review", text)

    def test_storage_plan_pointer_fires_in_planning_only_tasks(self):
        text = (SKILLS / "maintain-verification/SKILL.md").read_text()
        self.assertIn("planning-only", text)
        self.assertIn("storage proof plan", text)
        self.assertIn("references/lifecycle.md", text)

    def test_storage_plan_names_owned_isolation_and_durable_observations(self):
        text = (SKILLS / "maintain-verification/references/lifecycle.md").read_text()
        for requirement in ("## Storage proof plans", "per-test temporary database/file",
                            "backend and adapter", "transaction boundaries", "synthetic rows",
                            "close/reopen", "exactly one committed effect", "separate connection/transaction",
                            "authoritative identity, owner, attempt and fence", "no stale mutation",
                            "current-owner success control", "deterministic coordination",
                            "seeded replay/fencing defect", "cleanup", "not implemented"):
            self.assertIn(requirement, text)

    def test_plan_does_not_replace_collection_ci_or_executed_proof(self):
        text = (SKILLS / "maintain-verification/references/lifecycle.md").read_text()
        for requirement in ("zero missing IDs", "omitted-selector negative control",
                            "same candidate head", "actual product CI", "planned/INCOMPLETE"):
            self.assertIn(requirement, text)


if __name__ == "__main__":
    unittest.main()
