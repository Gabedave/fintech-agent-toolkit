#!/usr/bin/env python3
"""Copy the synthetic routing fixture into clean, independent Git checkouts."""

import argparse
import shutil
import subprocess
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "examples" / "routing-workspace"


def prepare(destination: Path) -> Path:
    if destination.exists():
        raise FileExistsError(f"destination already exists: {destination}")
    shutil.copytree(SOURCE, destination)
    for name in ("backend", "mobile"):
        repo = destination / name
        commands = (
            ["git", "init", "-b", "main"],
            ["git", "config", "user.name", "Toolkit Fixture"],
            ["git", "config", "user.email", "fixture@example.invalid"],
            ["git", "add", "-A"],
            ["git", "commit", "-m", "Create synthetic routing fixture"],
        )
        for command in commands:
            subprocess.run(command, cwd=repo, check=True, capture_output=True, text=True)
    return destination / "backend"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path, help="New directory for the disposable example workspace")
    args = parser.parse_args()
    print(prepare(args.destination.resolve()))


if __name__ == "__main__":
    main()
