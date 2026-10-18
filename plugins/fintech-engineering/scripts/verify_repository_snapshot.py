#!/usr/bin/env python3

import argparse
import json
import re
import subprocess
from pathlib import Path


COMMIT_SHA = re.compile(r"^[0-9a-fA-F]{40}$")


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


def blocked_report(
    *, repo: Path, base_ref: str, classification: str, authoritative_base_sha: str | None
) -> dict:
    return {
        "version": 1,
        "status": "blocked",
        "classification": classification,
        "repository": {"name": repo.name},
        "head": {"branch": None, "sha": None},
        "worktree": {"clean": None, "changed_entries": None},
        "base": {
            "ref": base_ref,
            "sha": None,
            "authoritative_sha": authoritative_base_sha,
            "authority": "unavailable",
            "ahead": None,
            "behind": None,
        },
        "attention_reasons": [],
        "recommended_source": "unavailable",
    }


def inspect_repository_snapshot(
    *, repo: Path, base_ref: str, authoritative_base_sha: str | None = None
) -> dict:
    requested_repo = repo.resolve()
    root_result = run_git(requested_repo, "rev-parse", "--show-toplevel")
    if root_result.returncode != 0:
        return blocked_report(
            repo=requested_repo,
            base_ref=base_ref,
            classification="repository_unavailable",
            authoritative_base_sha=authoritative_base_sha,
        )

    root = Path(root_result.stdout.strip()).resolve()
    if authoritative_base_sha is not None:
        authoritative_base_sha = authoritative_base_sha.strip().lower()
        if not COMMIT_SHA.fullmatch(authoritative_base_sha):
            return blocked_report(
                repo=root,
                base_ref=base_ref,
                classification="authoritative_sha_invalid",
                authoritative_base_sha=None,
            )

    head_sha = resolve_ref(root, "HEAD")
    base_sha = resolve_ref(root, base_ref)
    if head_sha is None:
        return blocked_report(
            repo=root,
            base_ref=base_ref,
            classification="head_unavailable",
            authoritative_base_sha=authoritative_base_sha,
        )
    if base_sha is None:
        report = blocked_report(
            repo=root,
            base_ref=base_ref,
            classification="base_ref_unavailable",
            authoritative_base_sha=authoritative_base_sha,
        )
        report["head"]["sha"] = head_sha
        return report

    branch_result = run_git(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    branch = branch_result.stdout.strip() if branch_result.returncode == 0 else None

    status_result = run_git(
        root, "status", "--porcelain=v1", "--untracked-files=normal"
    )
    if status_result.returncode != 0:
        return blocked_report(
            repo=root,
            base_ref=base_ref,
            classification="worktree_status_unavailable",
            authoritative_base_sha=authoritative_base_sha,
        )
    changed_entries = len(status_result.stdout.splitlines())

    divergence_result = run_git(
        root, "rev-list", "--left-right", "--count", f"HEAD...{base_ref}"
    )
    if divergence_result.returncode != 0:
        return blocked_report(
            repo=root,
            base_ref=base_ref,
            classification="divergence_unavailable",
            authoritative_base_sha=authoritative_base_sha,
        )
    try:
        ahead, behind = (int(value) for value in divergence_result.stdout.split())
    except ValueError:
        return blocked_report(
            repo=root,
            base_ref=base_ref,
            classification="divergence_unavailable",
            authoritative_base_sha=authoritative_base_sha,
        )

    attention_reasons = []
    if authoritative_base_sha is None:
        authority = "unverified"
        attention_reasons.append("authoritative_base_unverified")
    elif base_sha.lower() == authoritative_base_sha:
        authority = "confirmed"
    else:
        authority = "mismatch"
        attention_reasons.append("base_ref_stale")
    if behind:
        attention_reasons.append("head_behind_base")
    if changed_entries:
        attention_reasons.append("dirty_worktree")

    if not attention_reasons:
        status = "ready"
        classification = "source_snapshot_verified"
        recommended_source = "current-worktree"
    else:
        status = "attention"
        classification = (
            attention_reasons[0]
            if len(attention_reasons) == 1
            else "multiple_attention_signals"
        )
        recommended_source = "authoritative-base"

    return {
        "version": 1,
        "status": status,
        "classification": classification,
        "repository": {"name": root.name},
        "head": {"branch": branch, "sha": head_sha},
        "worktree": {
            "clean": changed_entries == 0,
            "changed_entries": changed_entries,
        },
        "base": {
            "ref": base_ref,
            "sha": base_sha,
            "authoritative_sha": authoritative_base_sha,
            "authority": authority,
            "ahead": ahead,
            "behind": behind,
        },
        "attention_reasons": attention_reasons,
        "recommended_source": recommended_source,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Report repository provenance without fetching, cleaning, checking out, or "
            "otherwise modifying the repository."
        )
    )
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--authoritative-base-sha")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = inspect_repository_snapshot(
        repo=args.repo,
        base_ref=args.base,
        authoritative_base_sha=args.authoritative_base_sha,
    )
    print(json.dumps(report, indent=2))
    if report["status"] == "ready":
        return 0
    if report["status"] == "attention":
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
