#!/usr/bin/env python3
"""Check this repository's one generated adapter without fetching or rewriting."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    try:
        lock = json.loads((ROOT / "foundation-lock.json").read_text())
        profiles = [p for p in (ROOT / "profiles").glob("*.json")
                    if json.loads(p.read_text()).get("plugin_name") == lock["plugin_name"]]
        if len(profiles) != 1:
            raise ValueError("exactly one profile must own the locked plugin")
        commit = lock["foundation"]["commit"]
        result = subprocess.run([sys.executable, "-B", str(ROOT / "foundation/render.py"),
                                 "--profile", str(profiles[0]), "--output", str(ROOT),
                                 "--source-commit", commit, "--check"], check=False)
        return result.returncode
    except (OSError, ValueError, KeyError) as error:
        print(f"ERROR: foundation check unavailable: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
