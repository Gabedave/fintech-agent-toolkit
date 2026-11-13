#!/usr/bin/env python3
"""Bounded synthetic review pilot; never execute code supplied by a model."""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import native_evidence
import evaluate_behavior
from process_control import stop_process_group, termination_guard

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from foundation.conformance.policy import safe_env
FIXTURES = ROOT / "tests" / "review-quality"
SUITE = FIXTURES / "cases.json"
SCHEMA = FIXTURES / "result.schema.json"
PUBLIC_FILES = ("README.md", "before.py", "support.py", "smoke.py", "observe.py")
VARIANTS = ("broken", "fixed")
MAX_JSON = 4096
INVARIANT_AREAS = {
    "state", "ownership", "transaction", "external-outcome", "replay", "time",
    "recovery-observability",
}


class EvaluationError(Exception):
    pass


def run_command(command, *, timeout, cwd=None, input_text=None, capture=None):
    # A new process group also bounds Codex's children, not just its CLI parent.
    # Keep runtime/auth discovery, not arbitrary product/provider credentials.
    env = safe_env(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    if capture is not None:
        returncode, stdout, _, timed_out = capture.run(
            command, input_text, timeout, cwd=cwd, env=env)
        if timed_out:
            raise EvaluationError("execution timed out; result is incomplete")
        if returncode:
            raise EvaluationError(f"execution failed (exit {returncode}); result is incomplete")
        return stdout
    with termination_guard():
        process = subprocess.Popen(command, cwd=cwd, env=env, text=True,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, start_new_session=True)
        try:
            stdout, _ = process.communicate(input_text, timeout=timeout)
        except BaseException as error:
            stop_process_group(process)
            if isinstance(error, subprocess.TimeoutExpired):
                raise EvaluationError("execution timed out; result is incomplete") from error
            raise
    if process.returncode:
        # CLI diagnostics may contain auth or provider details. Do not persist them.
        raise EvaluationError(f"execution failed (exit {process.returncode}); result is incomplete")
    return stdout


def materialize(case, variant, destination):
    source = FIXTURES / case["id"]
    for name in PUBLIC_FILES:
        variant_source = source / f"{variant}-{name}"
        selected = variant_source if variant_source.is_file() else source / name
        (destination / name).write_text(selected.read_text())
    (destination / "flow.py").write_text((source / f"{variant}.py").read_text())


def snapshot_identity(workspace):
    digest = hashlib.sha256()
    for name in (*PUBLIC_FILES, "flow.py"):
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update((workspace / name).read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def replay(case, variant, inputs):
    with tempfile.TemporaryDirectory(prefix="fintech-replay-") as directory:
        workspace = Path(directory)
        materialize(case, variant, workspace)
        output = run_command([sys.executable, "-B", "observe.py", json.dumps(inputs)],
                             cwd=workspace, timeout=5)
        try:
            return json.loads(output)
        except json.JSONDecodeError as error:
            raise EvaluationError("fixture replay did not return JSON") from error


def parse_object(value):
    if not isinstance(value, str) or len(value) > MAX_JSON:
        raise ValueError("reproduction must be bounded JSON text")
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("reproduction must be a JSON object")
    return parsed


def result_errors(result):
    if not isinstance(result, dict) or set(result) != {
        "verdict", "review_record", "findings", "limitations"
    }:
        return ["invalid review result shape"]
    if result["verdict"] not in ("ready", "not_ready", "incomplete"):
        return ["invalid verdict"]
    if not isinstance(result["limitations"], list) or any(
        not isinstance(item, str) or not item.strip() for item in result["limitations"]
    ):
        return ["invalid limitations"]
    if not isinstance(result["findings"], list) or len(result["findings"]) > 10:
        return ["invalid findings"]
    record = result["review_record"]
    record_keys = {
        "scope", "candidate_snapshot", "final_snapshot", "risk", "risk_rationale",
        "criteria", "invariants", "verification", "external_evidence",
        "decision_record", "remaining_risks", "reviewer_attempts", "repair_cycles",
        "independence", "consensus",
    }
    if not isinstance(record, dict) or set(record) != record_keys:
        return ["invalid review record shape"]
    for key in ("scope", "candidate_snapshot", "final_snapshot", "risk_rationale"):
        if not isinstance(record[key], str) or not record[key].strip():
            return [f"invalid {key.replace('_', ' ')}"]
    if record["risk"] not in ("low", "medium", "high"):
        return ["invalid risk"]
    if not isinstance(record["criteria"], list) or not 1 <= len(record["criteria"]) <= 20:
        return ["invalid criteria"]
    criterion_keys = {
        "requirement", "changed_seam", "focused_evidence", "broad_evidence", "status"
    }
    for criterion in record["criteria"]:
        if (not isinstance(criterion, dict) or set(criterion) != criterion_keys or
                any(not isinstance(criterion[key], str) or not criterion[key].strip()
                    for key in criterion_keys) or
                criterion["status"] not in ("confirmed", "partial", "unverified", "failed")):
            return ["invalid criterion"]
    if not isinstance(record["invariants"], list) or len(record["invariants"]) != 7:
        return ["invalid invariant register"]
    invariant_keys = {
        "area", "invariant", "authority", "changed_seam", "executable_evidence", "status"
    }
    areas = []
    for invariant in record["invariants"]:
        if (not isinstance(invariant, dict) or set(invariant) != invariant_keys or
                any(not isinstance(invariant[key], str) or not invariant[key].strip()
                    for key in invariant_keys) or
                invariant["status"] not in
                ("confirmed", "not-applicable", "unverified", "failed")):
            return ["invalid invariant"]
        areas.append(invariant["area"])
    if set(areas) != INVARIANT_AREAS or len(areas) != len(set(areas)):
        return ["invariant register must account for every area exactly once"]
    for key in ("verification", "remaining_risks"):
        if (not isinstance(record[key], list) or
                any(not isinstance(item, str) or not item.strip() for item in record[key])):
            return [f"invalid {key.replace('_', ' ')}"]
    if not record["verification"]:
        return ["invalid verification record"]
    external = record["external_evidence"]
    if (not isinstance(external, dict) or set(external) != {"status", "sources"} or
            external.get("status") not in ("not-required", "verified", "unverified") or
            not isinstance(external.get("sources"), list) or len(external["sources"]) > 10 or
            any(not isinstance(item, str) or not item.strip() for item in external["sources"])):
        return ["invalid external evidence"]
    decision = record["decision_record"]
    if (not isinstance(decision, dict) or set(decision) != {"status", "reference"} or
            decision.get("status") not in ("required", "skipped", "not-required", "unverified") or
            not isinstance(decision.get("reference"), str) or not decision["reference"].strip()):
        return ["invalid decision-record assessment"]
    for key in ("reviewer_attempts", "repair_cycles"):
        if type(record[key]) is not int or record[key] < 0:
            return [f"invalid {key.replace('_', ' ')}"]
    if record["reviewer_attempts"] < 1:
        return ["invalid reviewer attempts"]
    if record["independence"] not in ("performed", "not-performed"):
        return ["invalid independence"]
    if record["consensus"] not in (
        "achieved", "not-achieved", "human-decision-required"
    ):
        return ["invalid consensus"]
    keys = {
        "file", "line", "severity", "explanation", "remediation", "reconciliation",
        "input", "observed", "expected",
    }
    for finding in result["findings"]:
        if not isinstance(finding, dict) or set(finding) != keys:
            return ["invalid finding shape"]
        if any(
            not isinstance(finding[key], str) or not finding[key].strip()
            for key in keys - {"line"}
        ):
            return ["invalid finding text"]
        if type(finding["line"]) is not int or finding["line"] < 1:
            return ["invalid finding line"]
        if finding["severity"] not in ("Critical", "Major", "Minor"):
            return ["invalid finding severity or explanation"]
        if finding["reconciliation"] not in (
            "pending", "resolved-by-implementation", "resolved-by-evidence",
            "still-blocking", "downgraded", "human-decision-required",
        ):
            return ["invalid finding reconciliation"]
    return []


def score_review(case, variant, result, expected_snapshot=None,
                 expected_reviewer_attempts=1):
    errors = result_errors(result)
    if errors:
        return errors
    blockers = [finding for finding in result["findings"] if finding["severity"] != "Minor"]
    record = result["review_record"]
    if expected_snapshot and (
        record["candidate_snapshot"] != expected_snapshot or
        record["final_snapshot"] != expected_snapshot
    ):
        errors.append("review record does not identify the exact candidate snapshot")
    if record["risk"] != "high" or not record["risk_rationale"].strip():
        errors.append("synthetic high-risk candidate lacks a risk rationale")
    required_invariants = set(case["required_invariants"])
    by_area = {item["area"]: item for item in record["invariants"]}
    for area in required_invariants:
        if by_area[area]["status"] == "not-applicable":
            errors.append(f"required invariant {area} cannot be not-applicable")
    if all(item["status"] == "not-applicable" for item in record["invariants"]):
        errors.append("required invariant audit cannot be entirely not-applicable")
    external = record["external_evidence"]
    if external != {"status": "not-required", "sources": []}:
        errors.append("stable local fixture should not claim external evidence")
    if record["decision_record"]["status"] != "not-required":
        errors.append("synthetic fixture should not require a decision record")
    if (record["reviewer_attempts"] != expected_reviewer_attempts or
            record["repair_cycles"] != 0):
        errors.append("isolated review has invalid attempt or repair counts")
    if record["independence"] != "performed":
        errors.append("isolated reviewer did not report independence")
    if variant == "fixed":
        if result["verdict"] != "ready" or blockers:
            errors.append("fixed control not accepted")
        if any(item["status"] != "confirmed" for item in record["criteria"]):
            errors.append("ready result contains a failed criterion")
        if any(by_area[area]["status"] != "confirmed" for area in required_invariants):
            errors.append("fixed control required invariant audit is incomplete")
        if any(item["status"] in ("unverified", "failed") for item in record["invariants"]):
            errors.append("ready result contains an unverified or failed invariant")
        if external["status"] == "unverified":
            errors.append("ready result contains unverified external evidence")
        if record["consensus"] != "achieved":
            errors.append("fixed control consensus is inconsistent")
        return errors
    if result["verdict"] != "not_ready" or not blockers:
        errors.append("seeded defect not blocked")
    if not any(item["status"] == "failed" for item in record["criteria"]):
        errors.append("seeded defect is absent from the criteria mapping")
    if not any(by_area[area]["status"] == "failed" for area in required_invariants):
        errors.append("seeded defect is absent from the required invariant audit")
    if record["consensus"] != "not-achieved":
        errors.append("blocking review consensus is inconsistent")
    if any(finding["reconciliation"] != "pending" for finding in blockers):
        errors.append("initial blocking finding has invalid reconciliation")
    changed_boundary_found = False
    for finding in blockers:
        changed_boundary_found |= (
            finding["file"] == "flow.py"
            and case["lines"][0] <= finding["line"] <= case["lines"][1]
        )
        try:
            inputs = parse_object(finding["input"])
            observed = parse_object(finding["observed"])
            expected = parse_object(finding["expected"])
            actual = replay(case, "broken", inputs)
            control = replay(case, "fixed", inputs)
            if observed != actual or expected != control or actual == control:
                errors.append("blocker counterexample does not reproduce against the pair")
        except (ValueError, EvaluationError) as error:
            errors.append(f"invalid counterexample: {error}")
    if not changed_boundary_found:
        errors.append("no blocker identifies the changed faulty boundary")
    return errors


def load_suite():
    suite = json.loads(SUITE.read_text())
    if set(suite) != {"version", "cases"} or suite["version"] != 1 or len(suite["cases"]) != 5:
        raise EvaluationError("pilot must contain exactly five paired cases")
    seen = set()
    for case in suite["cases"]:
        if set(case) != {"id", "lines", "required_invariants", "counterexample", "neutral"}:
            raise EvaluationError("invalid case shape")
        case_id = case["id"]
        if not isinstance(case_id, str) or not re.fullmatch(r"[a-z][a-z0-9-]+", case_id) or case_id in seen:
            raise EvaluationError("invalid or duplicate case ID")
        seen.add(case_id)
        directory = FIXTURES / case_id
        if directory.is_symlink() or not directory.is_dir():
            raise EvaluationError("fixture must be a local directory")
        for name in (*PUBLIC_FILES, "broken.py", "fixed.py"):
            path = directory / name
            if path.is_symlink() or not path.is_file():
                raise EvaluationError("fixture files must be regular local files")
        for variant in VARIANTS:
            for name in PUBLIC_FILES:
                override = directory / f"{variant}-{name}"
                if override.exists() and (override.is_symlink() or not override.is_file()):
                    raise EvaluationError("variant fixture files must be regular local files")
        lines = case["lines"]
        if (not isinstance(lines, list) or len(lines) != 2 or
                any(type(line) is not int for line in lines) or
                not 1 <= lines[0] <= lines[1] <= len((directory / "broken.py").read_text().splitlines())):
            raise EvaluationError("invalid finding line range")
        for kind in ("counterexample", "neutral"):
            example = case[kind]
            if set(example) != {"input", "broken", "fixed"} or any(
                not isinstance(value, dict) for value in example.values()
            ):
                raise EvaluationError("invalid fixture expectation")
        if case["counterexample"]["broken"] == case["counterexample"]["fixed"]:
            raise EvaluationError("counterexample must distinguish the pair")
        if case["neutral"]["broken"] != case["neutral"]["fixed"]:
            raise EvaluationError("neutral case must agree across the pair")
        required_invariants = case["required_invariants"]
        if (not isinstance(required_invariants, list) or not required_invariants or
                len(required_invariants) != len(set(required_invariants)) or
                set(required_invariants) - INVARIANT_AREAS):
            raise EvaluationError("invalid required invariant coverage")
    evaluate_behavior.validate_output_schema(json.loads(SCHEMA.read_text()))
    return suite["cases"]


def check_fixtures(cases):
    for case in cases:
        for variant in VARIANTS:
            with tempfile.TemporaryDirectory(prefix="fintech-fixture-") as directory:
                workspace = Path(directory)
                materialize(case, variant, workspace)
                run_command([sys.executable, "-B", "smoke.py"], cwd=workspace, timeout=5)
            for kind in ("counterexample", "neutral"):
                example = case[kind]
                if replay(case, variant, example["input"]) != example[variant]:
                    raise EvaluationError(f"{case['id']}/{variant}: {kind} expectation failed")


def build_prompt(snapshot, reviewer_attempts=1):
    if reviewer_attempts == 1:
        attempt_context = (
            "You are the context-isolated independent reviewer for this initial pass: report "
            "reviewer_attempts as 1"
        )
    elif reviewer_attempts == 2:
        attempt_context = (
            "You are the sole operational replacement after the first reviewer failed before "
            "producing a usable report. You received no prior findings: report reviewer_attempts "
            "as 2"
        )
    else:
        raise ValueError("reviewer attempts must be 1 or 2")
    return f"""Use the installed fintech pre-push-review skill to review this synthetic candidate.
This is a contained review-quality experiment, not a product repository. Read README.md for
the requirements. Compare before.py with flow.py; support.py is the real local collaborator.
smoke.py contains the existing checks. Inspect source and run safe local checks as needed.
Keep investigation bounded: run smoke.py once, then use only the minimal documented observe.py
cases needed to test distinct requirements or failure seams, with at most six local commands total.
Do not run py_compile, test discovery, exhaustive input grids, or repeat a completed command.
Prioritize returning the complete structured review before the deadline over optional exploration.
Treat this stateful/provider-style fixture as high risk and account for all seven invariant
areas, using not-applicable only with concrete disqualifying evidence. The compound
recovery-observability area is applicable when the fixture has recovery, reconciliation,
observability, or a manual gate; it is not-applicable only when all four are absent. The immutable
candidate and final snapshot identity is {snapshot}. The only permitted reads are this fixture
and the installed skill/references. Do not seek other evaluator files, answer keys, or previous
reviews. {attempt_context}, repair_cycles as 0, and independence as performed. Do not delegate a
replacement reviewer. Do not edit files, install dependencies, access external systems, or
change Git state. No ADR is needed for this fixture.
Use python3 -B for local checks. observe.py accepts the documented JSON input and reports state.
Report concrete Critical/Major/Minor findings, not stylistic preferences. For every blocker
include its file/line, explanation, remediation, pending reconciliation, and a reproducible input
for observe.py. Supply input, observed,
and expected as JSON object strings using the complete observation shape. Do not supply code.
The expected observation must follow README.md, not merely repeat the implementation.
Use ready, not_ready, or incomplete for the verdict. A reproduced Critical/Major blocker or a
failed criterion or invariant takes precedence and means not_ready even when other residual
evidence remains partial or unverified. Use incomplete when no definitive blocker exists but
material evidence remains partial or unverified. On this pass, consensus is achieved only
for a ready result without unresolved blockers, not-achieved for not_ready or incomplete, and
human-decision-required only for an actual product-intent or risk-tolerance dispute. Classify
external evidence from the installed protocol. Report limitations and remaining risks honestly.
Keep confirmed or not-applicable free-text fields to one concise sentence. Expand failed or
unverified evidence and blockers sufficiently to make them reproducible. Keep scope and risk
rationale to one sentence each, verification to at most six concise entries, and omit harmless
environment warnings unless they invalidate evidence. Do not repeat the same explanation across
criteria, invariants, limitations, and remaining risks.
Return the requested structured review only; no external review submission is authorized.
"""


def run_review(case, variant, timeout, model=None, reviewer_attempts=1, *, evidence_dir=None):
    with tempfile.TemporaryDirectory(prefix="fintech-review-") as directory:
        workspace = Path(directory)
        materialize(case, variant, workspace)
        snapshot = snapshot_identity(workspace)
        # No variant labels, expected results, other candidates, or scorer enter this workspace.
        schema = workspace / "response.schema.json"
        schema.write_text(SCHEMA.read_text())
        before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in workspace.iterdir()}
        output = workspace / "review.json"
        command = ["codex", "exec", "--ephemeral", "--json", "--sandbox", "read-only",
                   "--skip-git-repo-check", "--output-schema", str(schema),
                   "--output-last-message", str(output), "--cd", str(workspace)]
        if model:
            command.extend(["--model", model])
        command.append("-")
        prompt = build_prompt(snapshot, reviewer_attempts)
        capture = native_evidence.NativeAttempt(
            evidence_dir, f"review-{case['id']}-{variant}-attempt-{reviewer_attempts}",
            command, prompt, schema, model,
            {"case": case["id"], "variant": variant, "snapshot": snapshot,
             "fixture_hashes": before, "reviewer_attempts": reviewer_attempts}, output,
        ) if evidence_dir is not None else None
        process_error = None
        try:
            run_command(
                command, timeout=timeout, cwd=workspace, input_text=prompt,
                **({"capture": capture} if capture else {}),
            )
        except EvaluationError as error:
            # A complete first result is scored once, even after a late process
            # error. Its unsuccessful process remains a separate evidence fact.
            process_error = error
        finally:
            if capture:
                capture.retain_result()
        after = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in workspace.iterdir() if path.name != "review.json" and path.is_file()}
        if before != after or any(path.is_dir() for path in workspace.iterdir()):
            raise EvaluationError("review changed the fixture; result is incomplete")
        if output.is_symlink() or not output.is_file() or output.stat().st_size > 100_000:
            raise EvaluationError("missing or oversized review result") from process_error
        try:
            result = json.loads(output.read_text())
            if not isinstance(result, dict):
                raise EvaluationError("review result must be a JSON object")
            if capture:
                capture.mark_usable()
            return result, snapshot
        except json.JSONDecodeError as error:
            raise EvaluationError("review result is not JSON") from error


def run_review_with_replacement(case, variant, timeout, model=None,
                                replacement_available=False, *, evidence_dir=None):
    try:
        result, snapshot = run_review(
            case, variant, timeout, model, reviewer_attempts=1, evidence_dir=evidence_dir
        )
        return result, snapshot, 1, False, None
    except (EvaluationError, OSError) as first_error:
        if not replacement_available:
            return None, None, 1, False, first_error
        try:
            result, snapshot = run_review(
                case, variant, timeout, model, reviewer_attempts=2, evidence_dir=evidence_dir
            )
            return result, snapshot, 2, True, None
        except (EvaluationError, OSError) as replacement_error:
            error = EvaluationError(
                f"initial attempt failed: {first_error}; "
                f"operational replacement failed: {replacement_error}"
            )
            return None, None, 2, True, error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Run deterministic fixture checks only.")
    mode.add_argument("--run", action="store_true", help="Review all pairs using the installed candidate.")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--evidence-dir", type=Path, help="Persistent native evidence directory (required for live runs).")
    parser.add_argument("--model", help="Optional explicit model override.")
    args = parser.parse_args()
    if not 30 <= args.timeout_seconds <= 180:
        parser.error("timeout must be between 30 and 180 seconds per review")
    try:
        cases = load_suite()
        check_fixtures(cases)
        if args.check:
            print(f"Review-quality fixtures passed ({len(cases)} pairs; no model invocation)")
            return
        if args.evidence_dir is None:
            parser.error("--evidence-dir is required for live runs")
        evidence_base = native_evidence.validate_location(args.evidence_dir, ROOT)
        evidence_dir = native_evidence.create_run(evidence_base, "review", {
            "model": args.model, "candidate": native_evidence.git_identity(ROOT),
            "evaluator_sha256": native_evidence.digest(Path(__file__).read_bytes()),
            "suite_sha256": native_evidence.digest(SUITE.read_bytes()),
        })
        print(f"Native evidence: {evidence_dir}", flush=True)
        plugin = evaluate_behavior.installed_plugin()
        version = json.loads(evaluate_behavior.MANIFEST.read_text())["version"]
        if plugin.get("version") != version:
            raise EvaluationError("installed plugin version does not match the candidate")
        failures = []
        detected = accepted = false_blockers = completed = replacements = 0
        started = time.monotonic()
        for case in cases:
            for variant in VARIANTS:
                label = f"{case['id']}/{variant}"
                tick = time.monotonic()
                result, snapshot, attempts, replacement_used, error = (
                    run_review_with_replacement(
                        case,
                        variant,
                        args.timeout_seconds,
                        args.model,
                        replacement_available=replacements == 0,
                        evidence_dir=evidence_dir,
                    )
                )
                replacements += int(replacement_used)
                if error is not None:
                    failures.append(f"{label}: {error}")
                    print(f"{label}: incomplete", flush=True)
                    continue
                try:
                    errors = score_review(
                        case,
                        variant,
                        result,
                        expected_snapshot=snapshot,
                        expected_reviewer_attempts=attempts,
                    )
                    completed += 1
                    if not result_errors(result):
                        false_blockers += int(variant == "fixed" and any(
                            item["severity"] != "Minor" for item in result["findings"]))
                    detected += int(variant == "broken" and not errors)
                    accepted += int(variant == "fixed" and not errors)
                    print(json.dumps({"case": label, "review": result,
                                      "seconds": round(time.monotonic() - tick, 1)}), flush=True)
                    failures.extend(f"{label}: {error}" for error in errors)
                except (EvaluationError, OSError) as error:
                    failures.append(f"{label}: {error}")
                    print(f"{label}: incomplete", flush=True)
        pair_count = len(cases)
        result_count = pair_count * len(VARIANTS)
        print(f"Review-quality pilot: {detected}/{pair_count} defects reproduced, "
              f"{accepted}/{pair_count} fixed controls accepted, "
              f"{false_blockers} fixed controls with false blockers; "
              f"{replacements}/1 operational replacements used; "
              f"{completed}/{result_count} results; "
              f"{time.monotonic() - started:.1f}s")
        for process_note in native_evidence.unsuccessful_usable_processes(evidence_dir):
            print(f"Native process: {process_note}; capture completeness unverified")
        if failures:
            raise EvaluationError("; ".join(failures))
        print(f"Review-quality pilot passed ({result_count}/{result_count} cases); "
              "synthetic evidence, not a general accuracy estimate")
    except (EvaluationError, ValueError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    try:
        with termination_guard():
            main()
    except KeyboardInterrupt:
        print("Review-quality pilot cancelled; no passing result", file=sys.stderr)
        raise SystemExit(130)
