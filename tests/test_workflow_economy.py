"""Instruction reachability/scope guards; these do not prove model compliance."""
from pathlib import Path
import re
import sys
import json
import contextlib
import io
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "foundation/plugin/skills"
ROUTER = SKILLS / "{{ROUTER}}"

class WorkflowEconomy(unittest.TestCase):
    def test_playbook_index_resolves_every_existing_workflow(self):
        index = (ROUTER / "references/playbooks.md").read_text()
        targets = re.findall(r"\]\((playbooks/[^)]+)\)", index)
        self.assertEqual(len(targets), 11)
        self.assertEqual(len(set(targets)), 11)
        for target in targets:
            text = (ROUTER / "references" / target).read_text()
            self.assertIn("../playbooks.md#delivery-and-authorization", text)
            self.assertGreater(len(text.split()), 30)
        # The commonly loaded index contains no unrelated workflow body.
        self.assertNotIn("Capture the exact symptom", index)
        self.assertNotIn("Deliver one thin end-to-end", index)

    def test_status_exemption_keeps_identity_and_diagnosis_boundary(self):
        router = (ROUTER / "SKILL.md").read_text()
        self.assertIn("For status-only checks or monitoring", router)
        self.assertIn("exact subject/revision", router)
        self.assertIn("status alone does not authorize diagnosis or repair", router)
        self.assertIn("Load `$how` only when explaining a cause", router)

    def test_single_authority_record_keeps_structured_output_and_withheld_boundaries(self):
        router = (ROUTER / "SKILL.md").read_text()
        self.assertIn("Reuse this ledger", router)
        self.assertIn("structured report still includes every required field", router)
        self.assertIn("including installation and withheld merge/deploy", router)
        self.assertNotIn("{{DELIVERY_POLICY}}", router)
        self.assertIn("{{DELIVERY_POLICY}}", (ROUTER / "references/playbooks.md").read_text())

    def test_scoped_verifier_audit_expands_when_required(self):
        text = (SKILLS / "maintain-verification/SKILL.md").read_text()
        for clause in ("affected features and dependent proof boundaries", "explicitly requested full audit",
                       "shared verifier changes affecting all features", "evidence of systemic drift",
                       "finish discovery before narrowing", "Retain all repository-required checks and aggregate inputs",
                       "cannot claim whole-repository health"):
            self.assertIn(clause, text)

    def test_merge_result_reuse_is_invalidated_by_changes_or_missing_identity(self):
        text = (ROUTER / "references/implementation-readiness.md").read_text()
        for clause in ("base/head SHAs", "clean working-tree identity", "configuration/environment inputs",
                       "At the push boundary recheck", "Changed or unknown inputs require a fresh check",
                       "failures and incomplete results cannot be reused"):
            self.assertIn(clause, text)

    def test_targeted_smoke_does_not_waive_full_release_or_broad_routing_gate(self):
        entry = (SKILLS / "pre-push-review/SKILL.md").read_text()
        self.assertIn("references/toolkit-verification.md", entry)
        text = (SKILLS / "pre-push-review/references/toolkit-verification.md").read_text()
        for clause in ("development evidence, never full qualification", "Before team-ready or release claims",
                       "run every model-backed scenario", "broad routing changes or uncertain impact",
                       "keep historical failures and repository-required checks"):
            self.assertIn(clause, text)

class StatusOnlyRouting(unittest.TestCase):
    def test_status_skips_source_model_but_diagnosis_keeps_it(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import evaluate
        contract = json.loads((ROUTER / "references/routing-contract.json").read_text())
        case = {"id":"status", "task_kind":"investigation", "nontrivial":True,
                "status_only":True, "signals":["pull_request_followthrough"]}
        result = evaluate.route(contract, case)
        self.assertEqual(result[1], ["ci-babysit"])
        self.assertEqual(result[2], [])
        self.assertIn("merge", result[3])
        case["status_only"] = False
        self.assertIn("how", evaluate.route(contract, case)[1])

    def test_status_marker_cannot_launder_mutation_or_diagnosis(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import evaluate
        contract = json.loads((ROUTER / "references/routing-contract.json").read_text())
        base = {"id":"status", "task_kind":"investigation", "nontrivial":True, "status_only":True}
        for delta in ({"authorized_actions":["edit"]}, {"implementation_delivery":True},
                      {"task_kind":"bug-fix"}, {"signals":["candidate_change"]},
                      {"status_only":"yes"}):
            with self.subTest(delta=delta), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                evaluate.route(contract, dict(base, **delta))

class StatusFixtureConsistency(unittest.TestCase):
    def test_one_status_pass_has_no_monitoring_trail_or_observation_obligation(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import evaluate_behavior
        suite = json.loads((ROOT / "tests/behavior-scenarios.json").read_text())
        case = next(c for c in suite["scenarios"] if c["id"] == "status-only-pr-check")
        self.assertIn("one read-only status pass", case["prompt"])
        self.assertEqual(case["expected_playbook"], "investigation")
        self.assertEqual(case["expected_decision_records"]["trail_disposition"], "not-required:not-applicable")
        self.assertNotIn("how", case["expected_skills"])
        self.assertNotIn("expected_ci_progress", case)
        self.assertEqual(case["expected_actions"], [])
        self.assertEqual(case["routing_allowance"]["required_playbooks"], ["investigation"])
        if hasattr(evaluate_behavior, "ci_progress_errors"):
            self.assertEqual(evaluate_behavior.ci_progress_errors(case, []), [])

    def test_numbered_monitor_keeps_continuity_and_actual_event_requirements(self):
        suite = json.loads((ROOT / "tests/behavior-scenarios.json").read_text())
        cases = [c for c in suite["scenarios"] if c["id"] == "ci-progress-reporting"]
        if not cases:
            return  # Public suite has no company-specific progress scenario.
        case = cases[0]
        self.assertIn("numbered observations", case["prompt"])
        self.assertNotIn("how", case["expected_skills"])
        self.assertIn("work-continuity", case["expected_skills"])
        self.assertEqual(case["expected_decision_records"]["trail_disposition"], "required:local")
        self.assertEqual(case["expected_ci_progress"]["required"], [3, 4, 6, 8])
