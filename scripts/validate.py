#!/usr/bin/env python3

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "fintech-engineering"
MANIFEST = PLUGIN / ".codex-plugin" / "plugin.json"
MARKETPLACE = ROOT / ".agents" / "plugins" / "marketplace.json"
SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")
PINNED_USE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[^@\s]+)?@[0-9a-f]{40}(?:\s+#.+)?$")
ROUTING_CONTRACT = (
    PLUGIN / "skills" / "fintech-mode" / "references" / "routing-contract.json"
)


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        fail(f"cannot read {path.relative_to(ROOT)}: {error}")


def validate_manifest() -> None:
    manifest = load_json(MANIFEST)
    if manifest.get("name") != PLUGIN.name:
        fail("plugin folder and manifest name must match")
    if not SEMVER.fullmatch(str(manifest.get("version", ""))):
        fail("plugin version must be semantic versioning")
    for key in ("description", "skills"):
        if not manifest.get(key):
            fail(f"plugin manifest is missing {key}")
    if not manifest.get("author", {}).get("name"):
        fail("plugin manifest is missing author.name")
    interface = manifest.get("interface", {})
    for key in (
        "displayName",
        "shortDescription",
        "longDescription",
        "developerName",
        "category",
        "capabilities",
        "defaultPrompt",
    ):
        if not interface.get(key):
            fail(f"plugin interface is missing {key}")
    default_prompts = interface["defaultPrompt"]
    if not isinstance(default_prompts, list) or any(
        not isinstance(prompt, str) or not prompt.strip() for prompt in default_prompts
    ):
        fail("plugin interface.defaultPrompt must be a non-empty string list")
    if any(len(prompt) > 128 for prompt in default_prompts):
        fail("plugin interface.defaultPrompt entries must be at most 128 characters")


def parse_frontmatter(path: Path) -> dict[str, str]:
    lines = path.read_text().splitlines()
    if not lines or lines[0] != "---":
        fail(f"{path.relative_to(ROOT)} has no YAML frontmatter")
    try:
        end = lines.index("---", 1)
    except ValueError:
        fail(f"{path.relative_to(ROOT)} has unterminated YAML frontmatter")
    fields: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip().strip('"')
    return fields


def validate_skills() -> None:
    skill_dirs = sorted(path for path in (PLUGIN / "skills").iterdir() if path.is_dir())
    if not skill_dirs:
        fail("plugin has no skills")
    for skill_dir in skill_dirs:
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            fail(f"{skill_dir.name} has no SKILL.md")
        text = skill_file.read_text()
        fields = parse_frontmatter(skill_file)
        if fields.get("name") != skill_dir.name:
            fail(f"{skill_dir.name} folder and skill name must match")
        if not fields.get("description"):
            fail(f"{skill_dir.name} has no description")
        if "TODO" in text:
            fail(f"{skill_dir.name} contains an unfinished TODO")
        agent_config = skill_dir / "agents" / "openai.yaml"
        if not agent_config.exists():
            fail(f"{skill_dir.name} has no agents/openai.yaml")
        if f"${skill_dir.name}" not in agent_config.read_text():
            fail(f"{skill_dir.name} default prompt must mention ${skill_dir.name}")


def validate_implicit_router(
    skill_dir: Path | None = None, manifest: dict | None = None
) -> None:
    skill_dir = skill_dir or PLUGIN / "skills" / "fintech-mode"
    fields = parse_frontmatter(skill_dir / "SKILL.md")
    description = fields.get("description", "")
    for required_scope in (
        "any task in a fintech product repository",
        "small mechanical edit",
    ):
        if required_scope not in description:
            fail(f"fintech-mode implicit description must cover {required_scope}")
    agent_config = (skill_dir / "agents" / "openai.yaml").read_text()
    if "allow_implicit_invocation: true" not in agent_config:
        fail("fintech-mode must allow implicit invocation")
    manifest = manifest or load_json(MANIFEST)
    prompts = manifest.get("interface", {}).get("defaultPrompt", [])
    if not any("$fintech-mode automatically" in prompt for prompt in prompts):
        fail("plugin default prompt must enable automatic fintech-mode routing")


def validate_routing_contract() -> None:
    contract = load_json(ROUTING_CONTRACT)
    if contract.get("version") != 1:
        fail("routing contract version must be 1")
    known_skills = {
        path.name for path in (PLUGIN / "skills").iterdir() if path.is_dir()
    }
    routed_skills = set(contract.get("default_for_nontrivial", [])) | set(
        contract.get("signals", {}).values()
    )
    unknown_skills = sorted(routed_skills - known_skills)
    if unknown_skills:
        fail(f"routing contract references unknown skills: {', '.join(unknown_skills)}")
    forbidden_present = sorted(
        set(contract.get("forbidden_capabilities", [])) & known_skills
    )
    if forbidden_present:
        fail(f"forbidden skills are present: {', '.join(forbidden_present)}")
    if not contract.get("playbooks"):
        fail("routing contract has no playbooks")
    authorization = contract.get("authorization", {})
    if authorization.get("implicit_actions"):
        fail("routing contract must not grant implicit external actions")
    if set(authorization.get("implementation_delivery_actions", [])) != {
        "edit",
        "commit",
        "push",
        "open-pull-request",
    }:
        fail(
            "routing contract implementation delivery must include only edit, commit, "
            "push, and open-pull-request"
        )
    if not authorization.get("explicit_actions"):
        fail("routing contract must declare explicit authorization actions")
    ledger_actions = authorization.get("plan_ledger_actions", [])
    if len(ledger_actions) != len(set(ledger_actions)):
        fail("routing contract authorization ledger actions must be unique")
    if set(ledger_actions) - set(authorization["explicit_actions"]):
        fail("routing contract authorization ledger contains unsupported actions")
    if set(ledger_actions) != {
        "edit",
        "commit",
        "push",
        "open-pull-request",
        "merge",
        "deploy",
    }:
        fail("routing contract authorization ledger must classify the six core actions")


def validate_marketplace() -> None:
    marketplace = load_json(MARKETPLACE)
    if marketplace.get("name") != "gabedave":
        fail("marketplace name must be gabedave")
    entries = {entry.get("name"): entry for entry in marketplace.get("plugins", [])}
    entry = entries.get(PLUGIN.name)
    if not entry:
        fail("marketplace is missing fintech-engineering")
    if entry.get("source", {}).get("path") != "./plugins/fintech-engineering":
        fail("marketplace plugin path is incorrect")
    policy = entry.get("policy", {})
    if not policy.get("installation") or not policy.get("authentication"):
        fail("marketplace plugin policy is incomplete")


def validate_workflows() -> None:
    for path in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        for line in path.read_text().splitlines():
            stripped = line.strip()
            if not stripped.startswith("- uses:"):
                continue
            target = stripped.removeprefix("- uses:").strip()
            if target.startswith("./"):
                continue
            if not PINNED_USE.fullmatch(target):
                fail(f"{path.relative_to(ROOT)} has an unpinned action: {target}")


def main() -> None:
    validate_manifest()
    validate_skills()
    validate_implicit_router()
    validate_routing_contract()
    validate_marketplace()
    validate_workflows()
    print("Fintech engineering plugin validation passed")


if __name__ == "__main__":
    main()
