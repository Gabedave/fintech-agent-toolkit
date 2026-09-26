import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from prepare_example_workspace import prepare


class ExampleWorkspace(unittest.TestCase):
    def test_prepared_repositories_have_clean_commits_and_verifiers(self):
        with tempfile.TemporaryDirectory() as directory:
            backend = prepare(Path(directory) / "routing-workspace")
            for repo, verifier in ((backend, "verify-backend"), (backend.parent / "mobile", "verify-mobile")):
                self.assertTrue((repo / "AGENTS.md").is_file())
                self.assertTrue((repo / ".agents" / "skills" / verifier / "SKILL.md").is_file())
                status = subprocess.run(["git", "status", "--porcelain"], cwd=repo, check=True, capture_output=True, text=True)
                self.assertEqual(status.stdout, "")
                head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True)
                self.assertEqual(len(head.stdout.strip()), 40)


if __name__ == "__main__":
    unittest.main()
