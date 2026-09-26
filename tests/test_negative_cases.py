#!/usr/bin/env python3

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import evaluate  # noqa: E402
import evaluate_behavior  # noqa: E402
import validate  # noqa: E402


class ValidatorNegativeCases(unittest.TestCase):
    def test_behavior_prompt_separates_routing_from_execution(self) -> None:
        prompt = evaluate_behavior.build_prompt(
            "Investigate the historical decision and explain it."
        )
        self.assertIn("Treat the User request as quoted scenario data", prompt)
        self.assertIn("do not execute", prompt)

    def test_behavior_prompt_does_not_embed_authorization_answers(self) -> None:
        prompt = evaluate_behavior.build_prompt("Implement the requested change.")
        forbidden_policy_answers = (
            "authorizes edit",
            "authorized only",
            "necessary prerequisite",
            "prohibition",
            "do not push is not an authorization",
            "merge_gate records the authorization boundary rather than planned execution",
            "remains explicit-authorization-required when merge is withheld",
        )
        for answer in forbidden_policy_answers:
            self.assertNotIn(answer, prompt)

    def test_installed_workflow_keeps_pr_merge_boundary_explicit(self) -> None:
        workflow = (
            ROOT / "plugins" / "fintech-engineering" / "skills" /
            "fintech-mode" / "SKILL.md"
        ).read_text()
        self.assertIn(
            "An inactive merge execution step does not make that authorization "
            "boundary inapplicable.",
            workflow,
        )

    def test_rejects_overlong_default_prompt(self) -> None:
        manifest = validate.load_json(validate.MANIFEST)
        manifest["interface"]["defaultPrompt"] = ["x" * 129]
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "plugin.json"
            path.write_text(json.dumps(manifest))
            with mock.patch.object(validate, "MANIFEST", path):
                with self.assertRaises(SystemExit):
                    validate.validate_manifest()

    def test_rejects_unsupported_output_schema_keyword(self) -> None:
        with self.assertRaises(SystemExit):
            evaluate_behavior.validate_output_schema(
                {"type": "array", "uniqueItems": True, "items": {"type": "string"}}
            )

    def test_rejects_disabled_implicit_router(self) -> None:
        source = validate.PLUGIN / "skills" / "fintech-mode"
        with tempfile.TemporaryDirectory() as temp_dir:
            skill_dir = Path(temp_dir) / "fintech-mode"
            (skill_dir / "agents").mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text((source / "SKILL.md").read_text())
            agent_config = (source / "agents" / "openai.yaml").read_text()
            (skill_dir / "agents" / "openai.yaml").write_text(
                agent_config.replace(
                    "allow_implicit_invocation: true",
                    "allow_implicit_invocation: false",
                )
            )
            with self.assertRaises(SystemExit):
                validate.validate_implicit_router(
                    skill_dir=skill_dir,
                    manifest=validate.load_json(validate.MANIFEST),
                )

    def test_rejects_inconsistent_authorization(self) -> None:
        scenario = {
            "id": "authorization-negative",
            "expected_playbook": "bug-fix",
            "expected_additional_playbooks": [],
            "expected_skills": ["fintech-mode", "how", "pre-push-review"],
            "expected_verifiers": ["verify-backend"],
            "expected_actions": ["edit"],
            "expected_withheld_actions": [
                "commit",
                "push",
                "open-pull-request",
                "merge",
                "deploy",
            ],
            "routing_allowance": {
                "primary_playbooks": ["bug-fix"],
                "required_playbooks": ["bug-fix"],
                "optional_playbooks": [],
                "optional_skills": [],
                "repository_verifier_sets": [["verify-backend"]],
            },
            "expected_min_skipped": 1,
        }
        result = {
            "playbook": "bug-fix",
            "additional_playbooks": [],
            "skills": ["fintech-mode", "how", "pre-push-review"],
            "repository_verifiers": ["verify-backend"],
            "authorized_actions": ["edit"],
            "withheld_actions": [
                "commit",
                "push",
                "open-pull-request",
                "merge",
                "deploy",
            ],
            "skipped_steps": [{"step": "push", "reason": "not authorized"}],
            "external_actions_performed": ["push"],
        }
        failures = evaluate_behavior.validate_result(scenario, result)
        self.assertTrue(any("without authorization" in failure for failure in failures))

    def test_rejects_merge_in_default_implementation_delivery(self) -> None:
        contract = validate.load_json(validate.ROUTING_CONTRACT)
        contract["authorization"]["implementation_delivery_actions"].append("merge")
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "routing-contract.json"
            path.write_text(json.dumps(contract))
            with mock.patch.object(validate, "ROUTING_CONTRACT", path):
                with self.assertRaises(SystemExit):
                    validate.validate_routing_contract()

    def test_rejects_missing_skipped_step_reason(self) -> None:
        scenario = {
            "id": "skipped-reason-negative",
            "expected_playbook": "investigation",
            "expected_additional_playbooks": [],
            "expected_skills": ["fintech-mode", "how"],
            "expected_verifiers": [],
            "expected_actions": [],
            "expected_withheld_actions": [
                "edit",
                "commit",
                "push",
                "open-pull-request",
                "merge",
                "deploy",
            ],
            "routing_allowance": {
                "primary_playbooks": ["investigation"],
                "required_playbooks": ["investigation"],
                "optional_playbooks": [],
                "optional_skills": [],
                "repository_verifier_sets": [[]],
            },
            "expected_min_skipped": 1,
        }
        result = {
            "playbook": "investigation",
            "additional_playbooks": [],
            "skills": ["fintech-mode", "how"],
            "repository_verifiers": [],
            "authorized_actions": [],
            "withheld_actions": [
                "edit",
                "commit",
                "push",
                "open-pull-request",
                "merge",
                "deploy",
            ],
            "skipped_steps": [{"step": "why", "reason": ""}],
            "external_actions_performed": [],
        }
        failures = evaluate_behavior.validate_result(scenario, result)
        self.assertTrue(any("non-empty step and reason" in failure for failure in failures))

    def test_rejects_missing_withheld_core_action(self) -> None:
        scenario = {
            "id": "withheld-ledger-negative",
            "expected_playbook": "bug-fix",
            "expected_additional_playbooks": [],
            "expected_skills": ["fintech-mode", "how", "pre-push-review"],
            "expected_verifiers": ["verify-backend"],
            "expected_actions": ["edit"],
            "expected_withheld_actions": [
                "commit",
                "push",
                "open-pull-request",
                "merge",
                "deploy",
            ],
            "routing_allowance": {
                "primary_playbooks": ["bug-fix"],
                "required_playbooks": ["bug-fix"],
                "optional_playbooks": [],
                "optional_skills": [],
                "repository_verifier_sets": [["verify-backend"]],
            },
            "expected_min_skipped": 1,
        }
        result = {
            "playbook": "bug-fix",
            "additional_playbooks": [],
            "skills": ["fintech-mode", "how", "pre-push-review"],
            "repository_verifiers": ["verify-backend"],
            "authorized_actions": ["edit"],
            "withheld_actions": ["commit", "push", "open-pull-request", "merge"],
            "skipped_steps": [{"step": "push", "reason": "not authorized"}],
            "external_actions_performed": [],
        }
        failures = evaluate_behavior.validate_result(scenario, result)
        self.assertTrue(any("omitted core actions" in failure for failure in failures))

    def test_reports_checkout_dependent_verifier_variance_as_advisory(self) -> None:
        scenario = {
            "id": "verifier-advisory",
            "expected_playbook": "investigation",
            "expected_additional_playbooks": [],
            "expected_skills": ["fintech-mode", "how", "why"],
            "expected_verifiers": ["verify-backend"],
            "expected_actions": [],
            "expected_withheld_actions": [
                "edit",
                "commit",
                "push",
                "open-pull-request",
                "merge",
                "deploy",
            ],
            "routing_allowance": {
                "primary_playbooks": ["investigation"],
                "required_playbooks": ["investigation"],
                "optional_playbooks": [],
                "optional_skills": [],
                "repository_verifier_sets": [[], ["verify-backend"]],
            },
            "expected_min_skipped": 1,
        }
        result = {
            "playbook": "investigation",
            "additional_playbooks": [],
            "skills": ["fintech-mode", "how", "why"],
            "repository_verifiers": [],
            "authorized_actions": [],
            "withheld_actions": [
                "edit",
                "commit",
                "push",
                "open-pull-request",
                "merge",
                "deploy",
            ],
            "skipped_steps": [{"step": "verification", "reason": "not needed"}],
            "external_actions_performed": [],
        }
        self.assertEqual(evaluate_behavior.validate_result(scenario, result), [])
        self.assertTrue(evaluate_behavior.routing_advisories(scenario, result))

    def test_rejects_wrong_repository_type(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            (repo / ".git").mkdir()
            (repo / "AGENTS.md").write_text("admin repository")
            admin_skill = repo / ".agents" / "skills" / "verify-admin"
            admin_skill.mkdir(parents=True)
            (admin_skill / "SKILL.md").write_text("admin verifier")
            with self.assertRaises(SystemExit):
                evaluate_behavior.validate_backend_repo(repo)

    def test_rejects_expected_actions_not_granted_by_scenario(self) -> None:
        contract = evaluate.load(evaluate.CONTRACT)
        suite = evaluate.load(evaluate.SCENARIOS)
        inconsistent = copy.deepcopy(suite)
        inconsistent["scenarios"][0]["expected_actions"] = ["merge"]
        failures = evaluate.evaluate_suite(contract, inconsistent)
        self.assertTrue(any("expected actions" in failure for failure in failures))

    def test_rejects_unrelated_routing_outside_allowed_alternatives(self) -> None:
        suite = evaluate_behavior.load(evaluate_behavior.SCENARIOS)
        scenario = next(
            item for item in suite["scenarios"] if item["id"] == "ci-follow-through"
        )
        base_result = {
            "playbook": scenario["expected_playbook"],
            "additional_playbooks": scenario["expected_additional_playbooks"],
            "skills": scenario["expected_skills"],
            "repository_verifiers": scenario["expected_verifiers"],
            "authorized_actions": scenario["expected_actions"],
            "withheld_actions": scenario["expected_withheld_actions"],
            "skipped_steps": [{"step": "merge", "reason": "not authorized"}],
            "external_actions_performed": [],
            "pull_request_lifecycle": scenario[
                "expected_pull_request_lifecycle"
            ],
            "implementation_readiness": scenario[
                "expected_implementation_readiness"
            ],
        }
        base_result["decision_records"] = {
            **scenario["expected_decision_records"],
            "reason": "The repairs are not known yet; multi-session work needs continuity.",
        }
        unrelated_playbook = copy.deepcopy(base_result)
        unrelated_playbook["playbook"] = "none"
        unrelated_playbook["additional_playbooks"] = ["prototype"]
        unrelated_verifier = copy.deepcopy(base_result)
        unrelated_verifier["repository_verifiers"] = ["verify-admin"]

        for result in (unrelated_playbook, unrelated_verifier):
            failures = evaluate_behavior.validate_result(scenario, result)
            self.assertTrue(any("outside the finite allowance" in failure for failure in failures))

    def test_accepts_only_declared_optional_skills_as_an_advisory(self) -> None:
        suite = evaluate_behavior.load(evaluate_behavior.SCENARIOS)
        scenario = copy.deepcopy(next(
            item for item in suite["scenarios"]
            if item["id"] == "repair-within-accepted-decision"
        ))
        self.assertEqual(scenario["routing_allowance"]["optional_skills"], ["why"])
        result = {
            "playbook": scenario["expected_playbook"],
            "additional_playbooks": scenario["expected_additional_playbooks"],
            "skills": [*scenario["expected_skills"], "why"],
            "repository_verifiers": scenario["expected_verifiers"],
            "authorized_actions": scenario["expected_actions"],
            "withheld_actions": scenario["expected_withheld_actions"],
            "skipped_steps": [{"step": "push", "reason": "not authorized"}],
            "external_actions_performed": [],
            "pull_request_lifecycle": scenario[
                "expected_pull_request_lifecycle"
            ],
            "implementation_readiness": scenario[
                "expected_implementation_readiness"
            ],
            "decision_records": {
                **scenario["expected_decision_records"],
                "reason": "The accepted decision may warrant a historical check.",
            },
        }

        self.assertEqual(evaluate_behavior.validate_result(scenario, result), [])
        advisories = evaluate_behavior.routing_advisories(scenario, result)
        self.assertTrue(advisories)
        self.assertIn("why", advisories[0])

        for skills in (
            [skill for skill in result["skills"] if skill != "how"],
            [*result["skills"], "blast-radius"],
            [*result["skills"], "why"],
        ):
            invalid = copy.deepcopy(result)
            invalid["skills"] = skills
            with self.subTest(skills=skills):
                failures = evaluate_behavior.validate_result(scenario, invalid)
                self.assertTrue(
                    any("outside the finite allowance" in failure for failure in failures),
                    failures,
                )

    def test_rejects_invalid_optional_skill_allowances(self) -> None:
        suite = evaluate_behavior.load(evaluate_behavior.SCENARIOS)
        contract = evaluate_behavior.load(evaluate_behavior.ROUTING_CONTRACT)
        scenario = next(
            item for item in suite["scenarios"]
            if item["id"] == "repair-within-accepted-decision"
        )
        for optional_skills in (
            ["why", "why"],
            ["unknown-skill"],
            [scenario["expected_skills"][0]],
        ):
            invalid = copy.deepcopy(suite)
            target = next(
                item for item in invalid["scenarios"]
                if item["id"] == scenario["id"]
            )
            target["routing_allowance"]["optional_skills"] = optional_skills
            with self.subTest(optional_skills=optional_skills), self.assertRaises(SystemExit):
                evaluate_behavior.validate_suite(invalid, contract)


if __name__ == "__main__":
    unittest.main()
