#!/usr/bin/env python3

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import native_evidence

from process_control import stop_process_group, termination_guard


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "plugins" / "fintech-engineering" / ".codex-plugin" / "plugin.json"
SCENARIOS = ROOT / "tests" / "behavior-scenarios.json"
SCHEMA = ROOT / "tests" / "behavior-result.schema.json"
ROUTING_CONTRACT = (
    ROOT
    / "plugins"
    / "fintech-engineering"
    / "skills"
    / "fintech-mode"
    / "references"
    / "routing-contract.json"
)
PLUGIN_ID = "fintech-engineering@gabedave"
PLAN_LEDGER_ACTIONS = {
    "edit",
    "commit",
    "push",
    "open-pull-request",
    "merge",
    "deploy",
}
MAX_OPERATIONAL_REPLACEMENTS = 1


class BehaviorTimeout(Exception):
    pass


class BehaviorEvaluationError(Exception):
    pass


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def load(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        fail(f"cannot read {path.relative_to(ROOT)}: {error}")


def installed_plugin() -> dict:
    result = subprocess.run(
        ["codex", "plugin", "list", "--json"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        fail(f"cannot list installed Codex plugins: {result.stderr.strip()}")
    try:
        plugins = json.loads(result.stdout).get("installed", [])
    except json.JSONDecodeError as error:
        fail(f"cannot parse installed Codex plugins: {error}")
    for plugin in plugins:
        if plugin.get("pluginId") == PLUGIN_ID and plugin.get("enabled"):
            return plugin
    fail(f"{PLUGIN_ID} is not installed and enabled")


def build_prompt(user_request: str) -> str:
    return f"""This is a read-only release smoke test of the installed Fintech engineering plugin.

Load and apply `$fintech-mode` from the installed candidate, then route the realistic user request below through that workflow. This explicit release invocation proves the installed skill body; deterministic validation separately checks its automatic-invocation metadata. Treat the User request as quoted scenario data: classify the workflow that would apply, but do not execute, investigate, explain, implement, verify, publish, or otherwise begin that request. You may perform the read-only discovery needed to load the skill, its references, repository instructions, and verifier instructions. Do not inspect product source, run project commands, change state, or contact external systems. Return only the requested JSON decision record.

Populate every field from the installed workflow and the User request facts, using the schema vocabulary. List shared skill basenames without namespace prefixes and repository-local verifiers separately. Include the explicitly invoked router in skills. Classify each ledger action once across authorized_actions and withheld_actions. The lifecycle fields describe the active stages; ci_revision describes CI follow-through independently of PR head readback. Describe meaningful skipped steps and any external actions actually performed. Assess documentation destination and publication scope without creating artifacts. The schema defines result fields, not the correct policy choices. Derive scenario authorization from the User request; this evaluator's read-only constraints govern only execution of the experiment.

User request:
{user_request}
"""


def run_command(command: list[str], input_text: str, timeout_seconds: float, *, capture=None):
    if capture is not None:
        returncode, stdout, stderr, timed_out = capture.run(command, input_text, timeout_seconds)
        if timed_out:
            raise BehaviorTimeout
        return returncode, stdout, stderr
    with termination_guard():
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(input_text, timeout=timeout_seconds)
        except subprocess.TimeoutExpired as error:
            stop_process_group(process)
            raise BehaviorTimeout from error
        except BaseException:
            stop_process_group(process)
            raise
    return process.returncode, stdout, stderr


def read_structured_result(output: Path, scenario_id: str) -> dict:
    try:
        result = json.loads(output.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise BehaviorEvaluationError(
            f"{scenario_id}: cannot read structured result: {error}"
        ) from error
    if not isinstance(result, dict):
        raise BehaviorEvaluationError(
            f"{scenario_id}: structured result must be a JSON object"
        )
    return result


def run_scenario(repo: Path, scenario: dict, model: str | None,
                 timeout_seconds: int, *, evidence_dir=None) -> dict:
    with tempfile.TemporaryDirectory(prefix="fintech-behavior-") as temp_dir:
        output = Path(temp_dir) / "result.json"
        command = [
            "codex",
            "exec",
            "--ephemeral",
            "--json",
            "--sandbox",
            "read-only",
            "--output-schema",
            str(SCHEMA),
            "--output-last-message",
            str(output),
            "--cd",
            str(repo),
        ]
        if model:
            command.extend(["--model", model])
        command.append("-")
        prompt = build_prompt(scenario["prompt"])
        capture = native_evidence.NativeAttempt(
            evidence_dir, "behavior-" + scenario["id"], command, prompt, SCHEMA, model,
            {"scenario": scenario, "fixture": str(repo)}, output,
        ) if evidence_dir is not None else None
        try:
            returncode, _, stderr = run_command(
                command, prompt, timeout_seconds,
                **({"capture": capture} if capture else {}),
            )
        except BehaviorTimeout as error:
            try:
                result = read_structured_result(output, scenario["id"])
                if capture:
                    capture.mark_usable()
                return result
            except BehaviorEvaluationError as result_error:
                raise BehaviorEvaluationError(
                    f"{scenario['id']}: Codex smoke run timed out after "
                    f"{timeout_seconds}s; result is incomplete; {result_error}"
                ) from error
        try:
            result = read_structured_result(output, scenario["id"])
        except BehaviorEvaluationError as result_error:
            if returncode != 0:
                raise BehaviorEvaluationError(
                    f"{scenario['id']}: Codex smoke run failed ({returncode}): "
                    f"{stderr.strip()}; {result_error}"
                ) from result_error
            raise
        if capture:
            capture.mark_usable()
        # A complete structured decision is usable even if the CLI reports a
        # later operational failure. Score it exactly once and never replace it.
        return result


def run_scenario_with_replacement(
    repo: Path,
    scenario: dict,
    model: str | None,
    timeout_seconds: int,
    *,
    replacement_available: bool,
    evidence_dir=None,
) -> tuple[dict | None, int, bool, BehaviorEvaluationError | None]:
    """Return one usable result, allowing one fresh operational replacement."""
    try:
        return run_scenario(repo, scenario, model, timeout_seconds, evidence_dir=evidence_dir), 1, False, None
    except BehaviorEvaluationError as first_error:
        if not replacement_available:
            return None, 1, False, first_error
        first_error_text = str(first_error)
    try:
        return run_scenario(repo, scenario, model, timeout_seconds, evidence_dir=evidence_dir), 2, True, None
    except BehaviorEvaluationError as replacement_error:
        error = BehaviorEvaluationError(
            f"initial attempt failed: {first_error_text}; "
            f"operational replacement failed: {replacement_error}"
        )
        return None, 2, True, error


def evaluate_scenarios(
    repo: Path,
    scenarios: list[dict],
    model: str | None,
    timeout_seconds: int,
    *, evidence_dir=None,
) -> tuple[list[str], list[str], int, int]:
    failures: list[str] = []
    advisories: list[str] = []
    replacements = 0
    usable_results = 0
    for scenario in scenarios:
        result, attempts, replacement_used, error = run_scenario_with_replacement(
            repo,
            scenario,
            model,
            timeout_seconds,
            replacement_available=replacements < MAX_OPERATIONAL_REPLACEMENTS,
            evidence_dir=evidence_dir,
        )
        if replacement_used:
            replacements += 1
        if error is not None:
            failures.append(str(error))
            print(f"{scenario['id']}: no usable result after {attempts} attempt(s)")
            continue
        usable_results += 1
        failures.extend(validate_result(scenario, result))
        advisories.extend(routing_advisories(scenario, result))
        suffix = " (operational replacement used)" if replacement_used else ""
        print(f"{scenario['id']}: evaluated{suffix}")
    return failures, advisories, replacements, usable_results


def validate_suite(suite: dict, contract: dict) -> None:
    scenarios = suite.get("scenarios")
    if suite.get("version") != 1 or not isinstance(scenarios, list) or not scenarios:
        fail("behaviour scenarios must use version 1 and contain scenarios")
    ids: set[str] = set()
    required = {
        "id",
        "prompt",
        "expected_playbook",
        "expected_additional_playbooks",
        "expected_skills",
        "expected_verifiers",
        "expected_actions",
        "expected_withheld_actions",
        "routing_allowance",
        "expected_min_skipped",
        "expected_decision_records",
        "expected_implementation_readiness",
        "expected_pull_request_lifecycle",
    }
    for scenario in scenarios:
        missing = required - set(scenario)
        if missing:
            fail(f"behaviour scenario is missing: {', '.join(sorted(missing))}")
        if scenario["id"] in ids:
            fail(f"duplicate behaviour scenario: {scenario['id']}")
        ids.add(scenario["id"])
        record_errors = decision_record_errors(
            scenario["expected_decision_records"], include_reason=False
        )
        if record_errors:
            fail(f"{scenario['id']}: invalid expected_decision_records: {'; '.join(record_errors)}")
        lifecycle_errors = pull_request_lifecycle_errors(
            scenario["expected_pull_request_lifecycle"]
        )
        if lifecycle_errors:
            fail(
                f"{scenario['id']}: invalid expected_pull_request_lifecycle: "
                f"{'; '.join(lifecycle_errors)}"
            )
        if "expected_implementation_readiness" in scenario:
            readiness_errors = implementation_readiness_errors(
                scenario["expected_implementation_readiness"]
            )
            if readiness_errors:
                fail(
                    f"{scenario['id']}: invalid expected_implementation_readiness: "
                    f"{'; '.join(readiness_errors)}"
                )
            readiness = scenario["expected_implementation_readiness"]
            push_expected = "push" in set(scenario["expected_actions"])
            expected_merge_gate = (
                "required-before-push" if push_expected else "not-applicable"
            )
            if readiness["synthetic_merge"] != expected_merge_gate:
                fail(
                    f"{scenario['id']}: synthetic merge must be "
                    f"{expected_merge_gate!r} for its authorization boundary"
                )
        if not scenario["prompt"].strip():
            fail(f"{scenario['id']}: prompt must be non-empty")
        existing_pull_request = scenario.get("existing_pull_request", False)
        if not isinstance(existing_pull_request, bool):
            fail(f"{scenario['id']}: existing_pull_request must be a boolean")
        if (
            not isinstance(scenario["expected_min_skipped"], int)
            or scenario["expected_min_skipped"] < 0
        ):
            fail(f"{scenario['id']}: expected_min_skipped must be non-negative")
        supporting_skills = set(scenario["expected_skills"]) - {"fintech-mode"}
        if supporting_skills and scenario["expected_min_skipped"] == 0:
            fail(f"{scenario['id']}: non-trivial routing must report a skipped step")
        allowance = scenario["routing_allowance"]
        allowance_fields = {
            "primary_playbooks",
            "required_playbooks",
            "optional_playbooks",
            "optional_skills",
            "repository_verifier_sets",
        }
        if not isinstance(allowance, dict) or set(allowance) != allowance_fields:
            fail(
                f"{scenario['id']}: routing allowance must contain exactly "
                "primary_playbooks, required_playbooks, optional_playbooks, "
                "optional_skills, and repository_verifier_sets"
            )
        for field in (
            "primary_playbooks",
            "required_playbooks",
            "optional_playbooks",
            "optional_skills",
            "repository_verifier_sets",
        ):
            if not isinstance(allowance[field], list):
                fail(f"{scenario['id']}: routing allowance {field} must be a list")
        primary_playbooks = allowance["primary_playbooks"]
        required_playbooks = allowance["required_playbooks"]
        optional_playbooks = allowance["optional_playbooks"]
        optional_skills = allowance["optional_skills"]
        required_skills = scenario["expected_skills"]
        if not primary_playbooks or not required_playbooks:
            fail(f"{scenario['id']}: routing allowance must require a primary path")
        if len(primary_playbooks) != len(set(primary_playbooks)):
            fail(f"{scenario['id']}: duplicate allowed primary playbook")
        if len(required_playbooks) != len(set(required_playbooks)):
            fail(f"{scenario['id']}: duplicate required playbook")
        if len(optional_playbooks) != len(set(optional_playbooks)):
            fail(f"{scenario['id']}: duplicate optional playbook")
        if len(required_skills) != len(set(required_skills)):
            fail(f"{scenario['id']}: duplicate required skill")
        if len(optional_skills) != len(set(optional_skills)):
            fail(f"{scenario['id']}: duplicate optional skill")
        known_playbooks = set(contract["playbooks"])
        allowance_playbooks = set(required_playbooks) | set(optional_playbooks)
        if allowance_playbooks - known_playbooks:
            fail(f"{scenario['id']}: routing allowance has unknown playbooks")
        if set(required_playbooks) & set(optional_playbooks):
            fail(f"{scenario['id']}: required and optional playbooks must be disjoint")
        if set(primary_playbooks) - allowance_playbooks:
            fail(f"{scenario['id']}: primary playbooks must be required or optional")
        verifier_sets = allowance["repository_verifier_sets"]
        if not verifier_sets:
            fail(f"{scenario['id']}: routing allowance needs a verifier set")
        normalized_verifier_sets: set[tuple[str, ...]] = set()
        for verifier_set in verifier_sets:
            if not isinstance(verifier_set, list):
                fail(f"{scenario['id']}: repository verifier sets must be lists")
            if len(verifier_set) != len(set(verifier_set)):
                fail(f"{scenario['id']}: repository verifier set has duplicates")
            if set(verifier_set) - {"verify-backend", "verify-mobile", "verify-admin"}:
                fail(f"{scenario['id']}: routing allowance has unknown verifiers")
            normalized = tuple(sorted(verifier_set))
            if normalized in normalized_verifier_sets:
                fail(f"{scenario['id']}: duplicate repository verifier set")
            normalized_verifier_sets.add(normalized)
        if scenario["expected_playbook"] in scenario["expected_additional_playbooks"]:
            fail(f"{scenario['id']}: preferred routing repeats the primary playbook")
        if not routing_is_allowed(scenario, preferred_routing(scenario)):
            fail(f"{scenario['id']}: preferred routing is outside its allowance")
        if scenario["expected_playbook"] not in contract["playbooks"]:
            fail(f"{scenario['id']}: expected playbook is not in the routing contract")
        unknown_additional_playbooks = set(
            scenario["expected_additional_playbooks"]
        ) - set(contract["playbooks"])
        if unknown_additional_playbooks:
            fail(
                f"{scenario['id']}: unknown additional playbooks: "
                f"{', '.join(sorted(unknown_additional_playbooks))}"
            )
        known_skills = {"fintech-mode"} | set(
            contract["default_for_nontrivial"]
        ) | set(contract["signals"].values())
        required_skill_set = set(required_skills)
        optional_skill_set = set(optional_skills)
        unknown_skills = (required_skill_set | optional_skill_set) - known_skills
        if unknown_skills:
            fail(
                f"{scenario['id']}: unknown allowed skills: "
                f"{', '.join(sorted(unknown_skills))}"
            )
        if required_skill_set & optional_skill_set:
            fail(f"{scenario['id']}: required and optional skills must be disjoint")
        unknown_verifiers = set(scenario["expected_verifiers"]) - {
            "verify-backend",
            "verify-mobile",
            "verify-admin",
        }
        if unknown_verifiers:
            fail(
                f"{scenario['id']}: unknown expected verifiers: "
                f"{', '.join(sorted(unknown_verifiers))}"
            )
        unknown_actions = set(scenario["expected_actions"]) - set(
            contract["authorization"]["explicit_actions"]
        )
        if unknown_actions:
            fail(
                f"{scenario['id']}: unknown expected actions: "
                f"{', '.join(sorted(unknown_actions))}"
            )
        expected_actions = set(scenario["expected_actions"])
        expected_withheld_actions = set(scenario["expected_withheld_actions"])
        ledger_actions = set(contract["authorization"]["plan_ledger_actions"])
        if expected_actions & expected_withheld_actions:
            fail(f"{scenario['id']}: authorization ledger actions must be disjoint")
        if (expected_actions | expected_withheld_actions) & ledger_actions != ledger_actions:
            fail(f"{scenario['id']}: authorization ledger must classify all six core actions")
        unknown_withheld_actions = expected_withheld_actions - ledger_actions
        if unknown_withheld_actions:
            fail(
                f"{scenario['id']}: unknown expected withheld actions: "
                f"{', '.join(sorted(unknown_withheld_actions))}"
            )
        lifecycle = scenario["expected_pull_request_lifecycle"]
        pr_requested = "open-pull-request" in expected_actions
        ci_requested = "ci-babysit" in required_skill_set
        if existing_pull_request and pr_requested:
            fail(f"{scenario['id']}: existing PR work must not open a duplicate pull request")
        pr_active = existing_pull_request or pr_requested or ci_requested
        if pr_active:
            if lifecycle["default_branch_check"] != "required":
                fail(f"{scenario['id']}: PR work must require a default-branch check")
            if lifecycle["base_selection"] == "not-applicable":
                fail(f"{scenario['id']}: PR work must select a base source")
            if lifecycle["merge_gate"] != "explicit-authorization-required":
                fail(f"{scenario['id']}: PR work must retain the explicit merge gate")
        elif any(value != "not-applicable" for value in lifecycle.values()):
            fail(f"{scenario['id']}: inactive PR lifecycle must be not-applicable")
        if ci_requested and lifecycle["ci_revision"] != "exact-latest-pr-head":
            fail(f"{scenario['id']}: CI follow-through must use the exact latest PR head")
        if not ci_requested and lifecycle["ci_revision"] != "not-applicable":
            fail(f"{scenario['id']}: CI revision must be inactive without ci-babysit")


def validate_output_schema(schema: dict) -> None:
    allowed = {
        "$schema",
        "type",
        "additionalProperties",
        "required",
        "properties",
        "items",
        "enum",
    }

    def visit(node: dict, location: str) -> None:
        unsupported = set(node) - allowed
        if unsupported:
            fail(
                f"unsupported output-schema keywords at {location}: "
                f"{', '.join(sorted(unsupported))}"
            )
        for name, child in node.get("properties", {}).items():
            visit(child, f"{location}.properties.{name}")
        items = node.get("items")
        if isinstance(items, dict):
            visit(items, f"{location}.items")

    visit(schema, "root")


def validate_backend_repo(repo: Path) -> None:
    backend_verifier = repo / ".agents" / "skills" / "verify-backend" / "SKILL.md"
    if (
        not (repo / ".git").exists()
        or not (repo / "AGENTS.md").is_file()
        or not backend_verifier.is_file()
    ):
        fail(
            "--repo must be a clean example backend checkout containing .git, AGENTS.md, "
            "and .agents/skills/verify-backend/SKILL.md"
        )


def preferred_routing(scenario: dict) -> dict:
    return {
        "playbook": scenario["expected_playbook"],
        "additional_playbooks": sorted(scenario["expected_additional_playbooks"]),
        "skills": sorted(scenario["expected_skills"]),
        "repository_verifiers": sorted(scenario["expected_verifiers"]),
    }


def routing_is_allowed(scenario: dict, routing: dict) -> bool:
    allowance = scenario["routing_allowance"]
    primary = routing["playbook"]
    additional = routing["additional_playbooks"]
    all_playbooks = [primary, *additional]
    if len(all_playbooks) != len(set(all_playbooks)):
        return False
    if primary not in allowance["primary_playbooks"]:
        return False
    selected_playbooks = set(all_playbooks)
    if not set(allowance["required_playbooks"]).issubset(selected_playbooks):
        return False
    permitted_playbooks = set(allowance["required_playbooks"]) | set(
        allowance["optional_playbooks"]
    )
    if not selected_playbooks.issubset(permitted_playbooks):
        return False
    selected_skills = routing["skills"]
    if len(selected_skills) != len(set(selected_skills)):
        return False
    required_skills = set(scenario["expected_skills"])
    permitted_skills = required_skills | set(allowance["optional_skills"])
    if not required_skills.issubset(selected_skills):
        return False
    if not set(selected_skills).issubset(permitted_skills):
        return False
    allowed_verifier_sets = {
        tuple(sorted(verifiers))
        for verifiers in allowance["repository_verifier_sets"]
    }
    return tuple(routing["repository_verifiers"]) in allowed_verifier_sets


def observed_routing(result: dict) -> dict:
    return {
        "playbook": result.get("playbook"),
        "additional_playbooks": sorted(result.get("additional_playbooks", [])),
        "skills": sorted(result.get("skills", [])),
        "repository_verifiers": sorted(result.get("repository_verifiers", [])),
    }


def decision_record_errors(record: object, *, include_reason: bool = True) -> list[str]:
    properties = load(SCHEMA)["properties"]["decision_records"]["properties"]
    fields = set(properties) if include_reason else set(properties) - {"reason"}
    if not isinstance(record, dict) or set(record) != fields:
        return [f"must contain exactly {', '.join(sorted(fields))}"]
    errors = []
    for field in fields:
        value = record[field]
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field} must be a non-empty string")
        elif "enum" in properties[field] and value not in properties[field]["enum"]:
            errors.append(f"{field} has unknown value {value!r}")
    if errors:
        return errors
    return errors


def pull_request_lifecycle_errors(lifecycle: object) -> list[str]:
    properties = load(SCHEMA)["properties"]["pull_request_lifecycle"]["properties"]
    fields = set(properties)
    if not isinstance(lifecycle, dict) or set(lifecycle) != fields:
        return [f"must contain exactly {', '.join(sorted(fields))}"]
    errors = []
    for field in fields:
        value = lifecycle[field]
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field} must be a non-empty string")
        elif value not in properties[field]["enum"]:
            errors.append(f"{field} has unknown value {value!r}")
    return errors


def implementation_readiness_errors(readiness: object) -> list[str]:
    properties = load(SCHEMA)["properties"]["implementation_readiness"]["properties"]
    fields = set(properties)
    if not isinstance(readiness, dict) or set(readiness) != fields:
        return [f"must contain exactly {', '.join(sorted(fields))}"]
    errors = []
    for field in fields - {"scenario_classes"}:
        value = readiness[field]
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field} must be a non-empty string")
        elif value not in properties[field]["enum"]:
            errors.append(f"{field} has unknown value {value!r}")
    scenarios = readiness["scenario_classes"]
    allowed_scenarios = properties["scenario_classes"]["items"]["enum"]
    if not isinstance(scenarios, list):
        errors.append("scenario_classes must be a list")
    elif len(scenarios) != len(set(scenarios)):
        errors.append("scenario_classes must not contain duplicates")
    elif set(scenarios) - set(allowed_scenarios):
        errors.append("scenario_classes contains an unknown value")
    if readiness.get("risk_classification") == "high":
        if readiness.get("proof_gate") != "adversarial-tests-before-production-edit":
            errors.append("high risk requires adversarial tests before production edits")
        if isinstance(scenarios, list) and set(scenarios) != set(allowed_scenarios):
            errors.append("high risk requires every adversarial scenario class")
        if (
            readiness.get("capability_preflight")
            != "repository-declared-before-verification"
        ):
            errors.append("high risk requires repository capability preflight")
    elif readiness.get("risk_classification") == "standard":
        if readiness.get("proof_gate") != "proportionate-before-edit":
            errors.append("standard risk requires proportionate proof before editing")
        if scenarios:
            errors.append("standard risk must not claim the complete high-risk scenario gate")
        if (
            readiness.get("capability_preflight")
            != "repository-declared-before-verification"
        ):
            errors.append("standard risk requires repository capability preflight")
    elif readiness.get("risk_classification") == "assess-before-edit":
        if readiness.get("proof_gate") != "classification-required-before-edit":
            errors.append("unclassified work must finish classification before editing")
        if scenarios:
            errors.append("unclassified work cannot claim completed adversarial scenarios")
        if (
            readiness.get("capability_preflight")
            != "repository-declared-before-verification"
        ):
            errors.append("unclassified implementation requires capability preflight")
    elif readiness.get("risk_classification") == "not-applicable":
        if readiness.get("proof_gate") != "not-applicable":
            errors.append("inactive implementation readiness must not claim a proof gate")
        if scenarios:
            errors.append("inactive implementation readiness must not claim scenarios")
        if readiness.get("capability_preflight") != "not-applicable":
            errors.append("inactive implementation readiness must not claim capabilities")
        if readiness.get("synthetic_merge") != "not-applicable":
            errors.append("inactive implementation readiness must not claim a merge gate")
    return errors


def validate_result(scenario: dict, result: dict) -> list[str]:
    failures: list[str] = []
    if "expected_implementation_readiness" in scenario:
        readiness = result.get("implementation_readiness")
        readiness_errors = implementation_readiness_errors(readiness)
        failures.extend(
            f"{scenario['id']}: implementation_readiness {error}"
            for error in readiness_errors
        )
        if not readiness_errors:
            for field, expected_value in scenario[
                "expected_implementation_readiness"
            ].items():
                if readiness[field] != expected_value:
                    failures.append(
                        f"{scenario['id']}: implementation_readiness.{field} expected "
                        f"{expected_value!r}, got {readiness[field]!r}"
                    )
    if "expected_pull_request_lifecycle" in scenario:
        lifecycle = result.get("pull_request_lifecycle")
        lifecycle_errors = pull_request_lifecycle_errors(lifecycle)
        failures.extend(
            f"{scenario['id']}: pull_request_lifecycle {error}"
            for error in lifecycle_errors
        )
        if not lifecycle_errors:
            for field, expected_value in scenario[
                "expected_pull_request_lifecycle"
            ].items():
                if lifecycle[field] != expected_value:
                    failures.append(
                        f"{scenario['id']}: pull_request_lifecycle.{field} expected "
                        f"{expected_value!r}, got {lifecycle[field]!r}"
                    )
    if "expected_decision_records" in scenario:
        record = result.get("decision_records")
        record_errors = decision_record_errors(record)
        failures.extend(f"{scenario['id']}: decision_records {error}" for error in record_errors)
        if not record_errors:
            for field, expected_value in scenario["expected_decision_records"].items():
                if record[field] != expected_value:
                    failures.append(
                        f"{scenario['id']}: decision_records.{field} expected "
                        f"{expected_value!r}, got {record[field]!r}"
                    )
    checks = {
        "playbook": result.get("playbook"),
        "additional_playbooks": sorted(result.get("additional_playbooks", [])),
        "skills": sorted(result.get("skills", [])),
        "repository_verifiers": sorted(result.get("repository_verifiers", [])),
        # These arrays express set membership. Repeating the same token does not
        # change the authorization boundary and must not make a sound decision fail.
        "authorized_actions": sorted(set(result.get("authorized_actions", []))),
        "withheld_actions": sorted(set(result.get("withheld_actions", []))),
        "external_actions_performed": sorted(
            result.get("external_actions_performed", [])
        ),
    }
    expected = {
        "playbook": scenario["expected_playbook"],
        "additional_playbooks": sorted(scenario["expected_additional_playbooks"]),
        "skills": sorted(scenario["expected_skills"]),
        "repository_verifiers": sorted(scenario["expected_verifiers"]),
        "authorized_actions": sorted(scenario["expected_actions"]),
        "withheld_actions": sorted(scenario["expected_withheld_actions"]),
        "external_actions_performed": [],
    }
    for field, expected_value in expected.items():
        if field in {"playbook", "additional_playbooks", "skills", "repository_verifiers"}:
            continue
        if checks[field] != expected_value:
            failures.append(
                f"{scenario['id']}: {field} expected {expected_value!r}, "
                f"got {checks[field]!r}"
            )

    routing = observed_routing(result)
    if not routing_is_allowed(scenario, routing):
        failures.append(
            f"{scenario['id']}: routing selection {routing!r} is outside the finite "
            f"allowance {scenario['routing_allowance']!r}"
        )

    unauthorized_performed = set(checks["external_actions_performed"]) - set(
        checks["authorized_actions"]
    )
    if unauthorized_performed:
        failures.append(
            f"{scenario['id']}: external actions were performed without authorization: "
            f"{', '.join(sorted(unauthorized_performed))}"
        )

    authorized_actions = set(checks["authorized_actions"])
    withheld_actions = set(checks["withheld_actions"])
    overlapping_actions = authorized_actions & withheld_actions
    if overlapping_actions:
        failures.append(
            f"{scenario['id']}: authorization ledger classified actions twice: "
            f"{', '.join(sorted(overlapping_actions))}"
        )
    missing_ledger_actions = PLAN_LEDGER_ACTIONS - (authorized_actions | withheld_actions)
    if missing_ledger_actions:
        failures.append(
            f"{scenario['id']}: authorization ledger omitted core actions: "
            f"{', '.join(sorted(missing_ledger_actions))}"
        )

    skipped_steps = result.get("skipped_steps", [])
    if not isinstance(skipped_steps, list):
        failures.append(f"{scenario['id']}: skipped_steps must be a list")
        return failures
    invalid_skipped_steps = [
        item
        for item in skipped_steps
        if not isinstance(item, dict)
        or not isinstance(item.get("step"), str)
        or not item["step"].strip()
        or not isinstance(item.get("reason"), str)
        or not item["reason"].strip()
    ]
    if invalid_skipped_steps:
        failures.append(
            f"{scenario['id']}: skipped steps must contain non-empty step and reason"
        )
    if len(skipped_steps) < scenario["expected_min_skipped"]:
        failures.append(
            f"{scenario['id']}: expected at least "
            f"{scenario['expected_min_skipped']} skipped steps with reasons, "
            f"got {len(skipped_steps)}"
        )
    return failures


def routing_advisories(scenario: dict, result: dict) -> list[str]:
    observed = observed_routing(result)
    preferred = preferred_routing(scenario)
    if observed == preferred or not routing_is_allowed(scenario, observed):
        return []
    return [
        f"{scenario['id']}: routing preferred {preferred!r}, got allowed "
        f"alternative {observed!r}"
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run model-backed smoke tests against the installed fintech plugin."
    )
    parser.add_argument(
        "--repo",
        type=Path,
        help="A clean example backend checkout containing AGENTS.md and verify-backend.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate smoke fixtures without invoking Codex.",
    )
    parser.add_argument("--evidence-dir", type=Path, help="Persistent native evidence directory (required for live runs).")
    parser.add_argument("--scenario", action="append", help="Run only this scenario ID.")
    parser.add_argument("--model", help="Optional Codex model override.")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    args = parser.parse_args()
    if not 30 <= args.timeout_seconds <= 180:
        parser.error("timeout must be between 30 and 180 seconds per scenario")

    suite = load(SCENARIOS)
    validate_output_schema(load(SCHEMA))
    validate_suite(suite, load(ROUTING_CONTRACT))
    if args.check:
        print(f"Fintech behavioural smoke fixtures passed ({len(suite['scenarios'])} scenarios)")
        return
    if args.repo is None:
        fail("--repo is required unless --check is used")

    if args.evidence_dir is None:
        parser.error("--evidence-dir is required for live runs")
    try:
        evidence_base = native_evidence.validate_location(args.evidence_dir, ROOT, args.repo)
    except ValueError as error:
        parser.error(str(error))
    evidence_dir = native_evidence.create_run(evidence_base, "behavior", {
        "fixture": native_evidence.git_identity(args.repo), "model": args.model,
        "candidate": native_evidence.git_identity(ROOT),
        "evaluator_sha256": native_evidence.digest(Path(__file__).read_bytes()),
        "suite_sha256": native_evidence.digest(SCENARIOS.read_bytes()),
    })
    print(f"Native evidence: {evidence_dir}", flush=True)
    repo = args.repo.resolve()
    validate_backend_repo(repo)

    manifest_version = load(MANIFEST)["version"]
    plugin = installed_plugin()
    if plugin.get("version") != manifest_version:
        fail(
            f"installed {PLUGIN_ID} version {plugin.get('version')} does not match "
            f"candidate version {manifest_version}; install the candidate before smoke testing"
        )

    selected = set(args.scenario or [])
    known = {scenario["id"] for scenario in suite["scenarios"]}
    if selected - known:
        fail(f"unknown scenarios: {', '.join(sorted(selected - known))}")

    scenarios = [
        scenario
        for scenario in suite["scenarios"]
        if not selected or scenario["id"] in selected
    ]
    failures, advisories, replacements, usable_results = evaluate_scenarios(
        repo, scenarios, args.model, args.timeout_seconds, evidence_dir=evidence_dir
    )
    for process_note in native_evidence.unsuccessful_usable_processes(evidence_dir):
        print(f"Native process: {process_note}; capture completeness unverified")
    print(
        f"Fintech behavioural smoke: {usable_results}/{len(scenarios)} usable "
        f"results; {replacements}/{MAX_OPERATIONAL_REPLACEMENTS} operational "
        "replacements used"
    )

    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        raise SystemExit(1)
    for advisory in advisories:
        print(f"ADVISORY: {advisory}")
    print(f"Fintech behavioural smoke passed ({len(scenarios)} scenarios)")


if __name__ == "__main__":
    main()
