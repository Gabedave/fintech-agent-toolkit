#!/usr/bin/env python3

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path


def run_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def resolve_ref(repo: Path, ref: str) -> str | None:
    result = run_git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}")
    return result.stdout.strip() if result.returncode == 0 else None


def substitute_paths(command: list[str], *, candidate: Path, source: Path) -> list[str]:
    return [
        part.replace("{candidate}", str(candidate)).replace("{source}", str(source))
        for part in command
    ]


def verify_merge_candidate(
    *, repo: Path, base_ref: str, head_ref: str = "HEAD", command: list[str]
) -> dict:
    repo = repo.resolve()
    base_sha = resolve_ref(repo, base_ref)
    head_sha = resolve_ref(repo, head_ref)
    report = {
        "version": 1,
        "status": "blocked",
        "classification": "ref_unavailable",
        "base": {"ref": base_ref, "sha": base_sha},
        "head": {"ref": head_ref, "sha": head_sha},
        "check_status": "not_run",
    }
    if not base_sha or not head_sha:
        return report
    if not command:
        report["classification"] = "verification_command_required"
        return report

    with tempfile.TemporaryDirectory(prefix="fintech-merge-candidate-") as temp_dir:
        candidate = Path(temp_dir) / "candidate"
        added = run_git(repo, "worktree", "add", "--detach", str(candidate), head_sha)
        if added.returncode != 0:
            report["classification"] = "candidate_worktree_unavailable"
            return report
        try:
            merged = run_git(candidate, "merge", "--no-commit", "--no-ff", base_sha)
            if merged.returncode != 0:
                report["classification"] = "merge_conflict"
                return report

            prepared = substitute_paths(command, candidate=candidate, source=repo)
            try:
                checked = subprocess.run(
                    prepared,
                    cwd=candidate,
                    env={
                        **os.environ,
                        "FINTECH_CANDIDATE_WORKTREE": str(candidate),
                        "FINTECH_SOURCE_WORKTREE": str(repo),
                    },
                    check=False,
                    capture_output=True,
                    text=True,
                )
            except OSError:
                report["classification"] = "verification_command_unavailable"
                return report
            report["check_status"] = "passed" if checked.returncode == 0 else "failed"
            if checked.returncode != 0:
                report["classification"] = "synthetic_merge_check_failed"
                report["check_exit_code"] = checked.returncode
                return report

            report["status"] = "ready"
            report["classification"] = "synthetic_merge_verified"
            return report
        finally:
            run_git(repo, "worktree", "remove", "--force", str(candidate))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify a PR candidate after combining its head with the selected base."
    )
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command[:1] == ["--"]:
        args.command = args.command[1:]
    return args


def main() -> int:
    args = parse_args()
    report = verify_merge_candidate(
        repo=args.repo,
        base_ref=args.base,
        head_ref=args.head,
        command=args.command,
    )
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
