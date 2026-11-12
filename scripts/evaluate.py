#!/usr/bin/env python3

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = (
    ROOT
    / "plugins"
    / "fintech-engineering"
    / "skills"
    / "fintech-mode"
    / "references"
    / "routing-contract.json"
)
SCENARIOS = ROOT / "tests" / "routing-scenarios.json"


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def load(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        fail(f"cannot read {path.relative_to(ROOT)}: {error}")


def route(contract: dict, scenario: dict) -> tuple[str, list[str], list[str], list[str]]:
    playbook = scenario["task_kind"]
    skills: set[str] = set()
    status_only = scenario.get("status_only", False)
    if type(status_only) is not bool:
        fail("status_only must be boolean")
    if status_only:
        rule = contract["status_only"]
        if (playbook != rule["playbook"] or scenario.get("implementation_delivery")
                or scenario.get("authorized_actions")
                or set(scenario.get("signals", [])) - set(rule["allowed_signals"])):
            fail("status-only routing cannot include diagnosis, implementation or mutation")
    if scenario.get("nontrivial") and not status_only:
        skills.update(contract["default_for_nontrivial"])
    for signal in scenario.get("signals", []):
        try:
            skills.add(contract["signals"][signal])
        except KeyError:
            fail(f"{scenario['id']} uses unknown routing signal: {signal}")
    requested_actions = set(scenario.get("authorized_actions", []))
    supported_actions = set(contract["authorization"]["explicit_actions"])
    unknown_actions = requested_actions - supported_actions
    if unknown_actions:
        fail(
            f"{scenario['id']} uses unknown authorization: {', '.join(sorted(unknown_actions))}"
        )
    actions = set(contract["authorization"]["implicit_actions"])
    if scenario.get("implementation_delivery"):
        actions.update(contract["authorization"]["implementation_delivery_actions"])
    actions.update(requested_actions)
    withheld_actions = set(contract["authorization"]["plan_ledger_actions"]) - actions
    return playbook, sorted(skills), sorted(actions), sorted(withheld_actions)


def evaluate_suite(contract: dict, suite: dict) -> list[str]:
    failures: list[str] = []

    for scenario in suite.get("scenarios", []):
        scenario_id = scenario.get("id", "<missing-id>")
        playbook, skills, actions, withheld_actions = route(contract, scenario)
        expected_skills = sorted(scenario.get("expected_skills", []))
        if playbook not in contract["playbooks"]:
            failures.append(f"{scenario_id}: unknown playbook {playbook}")
        if playbook != scenario.get("expected_playbook"):
            failures.append(
                f"{scenario_id}: expected playbook {scenario.get('expected_playbook')}, got {playbook}"
            )
        if skills != expected_skills:
            failures.append(
                f"{scenario_id}: expected skills {expected_skills}, got {skills}"
            )
        expected_actions = sorted(scenario.get("expected_actions", []))
        if actions != expected_actions:
            failures.append(
                f"{scenario_id}: expected actions {expected_actions}, got {actions}"
            )
        expected_withheld_actions = sorted(scenario.get("expected_withheld_actions", []))
        if withheld_actions != expected_withheld_actions:
            failures.append(
                f"{scenario_id}: expected withheld actions {expected_withheld_actions}, "
                f"got {withheld_actions}"
            )
        for forbidden in scenario.get("expected_absent", []):
            if forbidden in skills:
                failures.append(f"{scenario_id}: forbidden skill routed: {forbidden}")
        for forbidden in contract.get("forbidden_capabilities", []):
            if forbidden in skills:
                failures.append(f"{scenario_id}: forbidden capability routed: {forbidden}")

    return failures


def main() -> None:
    failures = evaluate_suite(load(CONTRACT), load(SCENARIOS))

    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        raise SystemExit(1)

    scenario_count = len(load(SCENARIOS)["scenarios"])
    print(f"Fintech routing evaluation passed ({scenario_count} scenarios)")


if __name__ == "__main__":
    main()
