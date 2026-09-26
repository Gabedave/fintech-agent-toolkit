import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "plugins"
    / "fintech-engineering"
    / "scripts"
    / "verify_merge_candidate.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("verify_merge_candidate", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load merge candidate verifier")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


class MergeCandidateVerifier(unittest.TestCase):
    def make_repo(self) -> tuple[Path, tempfile.TemporaryDirectory]:
        temporary = tempfile.TemporaryDirectory(prefix="fintech-merge-test-")
        repo = Path(temporary.name) / "repo"
        repo.mkdir()
        git(repo, "init", "-b", "main")
        git(repo, "config", "user.name", "fintech Test")
        git(repo, "config", "user.email", "test@fintech.invalid")
        (repo / "shared.txt").write_text("base\n")
        git(repo, "add", "shared.txt")
        git(repo, "commit", "-m", "base")
        return repo, temporary

    def test_runs_check_against_combined_base_and_head(self) -> None:
        verifier = load_module()
        repo, temporary = self.make_repo()
        self.addCleanup(temporary.cleanup)
        git(repo, "checkout", "-b", "feature")
        (repo / "feature.txt").write_text("feature\n")
        git(repo, "add", "feature.txt")
        git(repo, "commit", "-m", "feature")
        git(repo, "checkout", "main")
        (repo / "base.txt").write_text("main moved\n")
        git(repo, "add", "base.txt")
        git(repo, "commit", "-m", "main moved")

        report = verifier.verify_merge_candidate(
            repo=repo,
            base_ref="main",
            head_ref="feature",
            command=[
                "python3",
                "-c",
                "from pathlib import Path; assert Path('base.txt').exists(); assert Path('feature.txt').exists()",
            ],
        )

        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["classification"], "synthetic_merge_verified")
        self.assertEqual(report["check_status"], "passed")

    def test_reports_conflict_without_running_the_check(self) -> None:
        verifier = load_module()
        repo, temporary = self.make_repo()
        self.addCleanup(temporary.cleanup)
        git(repo, "checkout", "-b", "feature")
        (repo / "shared.txt").write_text("feature\n")
        git(repo, "add", "shared.txt")
        git(repo, "commit", "-m", "feature")
        git(repo, "checkout", "main")
        (repo / "shared.txt").write_text("main\n")
        git(repo, "add", "shared.txt")
        git(repo, "commit", "-m", "main")

        report = verifier.verify_merge_candidate(
            repo=repo,
            base_ref="main",
            head_ref="feature",
            command=["python3", "-c", "raise RuntimeError('must not run')"],
        )

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["classification"], "merge_conflict")
        self.assertEqual(report["check_status"], "not_run")

    def test_reports_an_unavailable_verification_command(self) -> None:
        verifier = load_module()
        repo, temporary = self.make_repo()
        self.addCleanup(temporary.cleanup)

        report = verifier.verify_merge_candidate(
            repo=repo,
            base_ref="main",
            command=["definitely-not-an-installed-command"],
        )

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["classification"], "verification_command_unavailable")
        self.assertEqual(report["check_status"], "not_run")


if __name__ == "__main__":
    unittest.main()
