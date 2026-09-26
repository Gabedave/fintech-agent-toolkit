import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins" / "fintech-engineering" / "skills" / "pre-push-review"


class ContextEconomy(unittest.TestCase):
    def test_common_review_context_stays_bounded(self):
        entrypoint = (SKILL / "SKILL.md").read_text()
        common = (SKILL / "references" / "review-protocol.md").read_text()

        self.assertLessEqual(len(entrypoint) + len(common), 13_000)
        self.assertNotIn("### High-risk invariant audit", common)
        self.assertNotIn("### External evidence", common)

    def test_conditional_review_guidance_is_separate(self):
        references = SKILL / "references"
        entrypoint = (SKILL / "SKILL.md").read_text()
        for name in ("high-risk-audit.md", "external-evidence.md"):
            with self.subTest(reference=name):
                self.assertTrue((references / name).is_file())
                self.assertIn(f"references/{name}", entrypoint)


if __name__ == "__main__":
    unittest.main()
