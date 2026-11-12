"""Source applicability guards; native reporting still needs separate evidence."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "foundation/plugin/skills"


def text(relative):
    path = SKILLS / relative
    content = path.read_text()
    if path.name == "playbooks.md":
        # Follow the disclosed workflow links; preserve the original scope assertions.
        for name in ("none", "investigation"):
            content += "\n## " + (path.parent / "playbooks" / (name + ".md")).read_text()[2:]
    return " ".join(content.split())


class ApplicabilityReporting(unittest.TestCase):
    def test_mechanical_readiness_reporting_is_consistent(self):
        playbooks = text("{{ROUTER}}/references/playbooks.md")
        none = playbooks.split("## None", 1)[1].split("## Investigation", 1)[0]
        self.assertIn("Keep implementation-readiness applicability consistent throughout the working report", none)
        self.assertIn("do not partially activate the non-trivial contract for this path", none)
        self.assertIn("closest direct check", none)

    def test_uncertain_or_nontrivial_work_cannot_inherit_mechanical_exemption(self):
        playbooks = text("{{ROUTER}}/references/playbooks.md")
        self.assertIn("If scope is uncertain, complete discovery", playbooks)
        self.assertIn("reselect the applicable workflow before editing", playbooks)
        router = text("{{ROUTER}}/SKILL.md")
        self.assertIn("Auditing or repairing verifier-owned assets or a proof boundary is not this path", router)
        readiness = text("{{ROUTER}}/references/implementation-readiness.md")
        self.assertIn("before production edits for every non-trivial implementation", readiness)
        self.assertIn("Before expensive verification, run the selected repository verifier's declared capability profile", readiness)

    def test_no_pr_lifecycle_requires_both_absent_pr_and_absent_delivery_outcome(self):
        playbooks = text("{{ROUTER}}/references/playbooks.md")
        for clause in ("no pull request exists or is planned", "requested outcome has no pull-request delivery lifecycle",
                       "there is no such lifecycle to report", "general merge/deployment prohibitions still apply"):
            self.assertIn(clause, playbooks)

    def test_existing_or_planned_pr_retains_merge_authorization_when_execution_inactive(self):
        router = text("{{ROUTER}}/SKILL.md")
        self.assertIn("For any existing or planned pull request, keep merge authorization as an explicit lifecycle boundary even when the user withholds or prohibits merge", router)
        self.assertIn("An inactive merge execution step does not make that authorization boundary inapplicable", router)

    def test_withheld_pr_prerequisites_and_existing_pr_identity_are_preserved(self):
        playbooks = text("{{ROUTER}}/references/playbooks.md")
        self.assertIn("a withheld commit or push also blocks downstream PR delivery", playbooks)
        self.assertIn("Never invent an empty or stale PR", playbooks)
        router = text("{{ROUTER}}/SKILL.md")
        self.assertIn("When the task already names an existing pull request, continue that PR", router)
        self.assertIn("create a duplicate unless the user explicitly asks for another PR", router)

    def test_direct_verification_and_real_preflight_are_not_removed(self):
        router = text("{{ROUTER}}/SKILL.md")
        self.assertIn("Run only the closest direct check", router)
        self.assertIn("Run repository-declared capability preflight before expensive verification", router)
        self.assertIn("never treat a blocked profile as passing or as a waiver for exact-head CI", router)


if __name__ == "__main__":
    unittest.main()
