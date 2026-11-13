"""Approved v2 controls exercise the real host and the existing review verifier."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from foundation.conformance import load_cases, score
from foundation.conformance.claim_review import assigned_rows, validate_review, sha256
from foundation.conformance.controls import control_observation, sensitivity_review


class AttachmentAmendmentTests(unittest.TestCase):
    def version(self):
        from foundation.conformance.acceptance_versions import version_for_oracle, V2_PUBLIC_ORACLE_SHA256
        return version_for_oracle(V2_PUBLIC_ORACLE_SHA256)

    def data(self):
        from foundation.conformance.acceptance_versions import amended_cases
        data = load_cases()
        data['cases'] = amended_cases(data['cases'])
        return data

    def case_variant(self, name):
        case = next(c for c in self.data()['cases'] if c['id'] == '06-review-evidence')
        return case, next(v for v in case['variants'] if v['id'] == name)

    def test_v1_unchanged_and_v2_only_replaces_approved_positive(self):
        old, new = load_cases(), self.data()
        self.assertEqual(47, sum(len(c['variants']) for c in old['cases']))
        self.assertEqual(48, sum(len(c['variants']) for c in new['cases']))
        self.assertEqual(12, len(new['cases']))
        self.assertEqual(old['profiles'], new['profiles'])
        for before, after in zip(old['cases'], new['cases']):
            if before['id'] != '06-review-evidence':
                self.assertEqual(before, after)
            else:
                retained = [v for v in before['variants'] if v['id'] != 'compliant-verified-attachments']
                self.assertEqual(retained, [v for v in after['variants'] if v['id'] not in {'compliant-fresh-attachment', 'compliant-verified-reuse'}])
        self.assertEqual(['overall_report_consistency'], assigned_rows('06-review-evidence', 'compliant-verified-attachments'))

    def test_unknown_oracle_is_rejected(self):
        from foundation.conformance.acceptance_versions import version_for_oracle
        with self.assertRaisesRegex(ValueError, 'unknown.*oracle'):
            version_for_oracle('f' * 64)

    def test_new_positives_complete_host_operations_without_model_compliance(self):
        for name in ('compliant-fresh-attachment', 'compliant-verified-reuse'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                case, variant = self.case_variant(name)
                root = Path(directory)
                observation = control_observation(case, variant, root / 'workspace')
                actions = [e['arguments']['action'] for e in observation['events'] if e['tool'] == 'host']
                self.assertEqual(name == 'compliant-fresh-attachment', 'upload' in actions)
                self.assertEqual(name == 'compliant-fresh-attachment', observation['initial']['attachment'] == {})
                context = sensitivity_review(case, variant, observation, root / 'sealed', oracle_sha256=self.version()['public_oracle_sha256'])
                result = score(case, variant, observation, context)
                self.assertEqual('pass', result['status'], result)
                self.assertFalse(result['model_compliance'])
                self.assertEqual(['overall_report_consistency'], [r['predicate_key'] for r in result['independent_claim_result']['rows']])

    def test_redundant_reuse_upload_fails_using_real_host(self):
        from foundation.conformance.host import Host
        case, variant = self.case_variant('compliant-verified-reuse')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            observation = control_observation(case, variant, root / 'workspace')
            host = Host(root / 'workspace', observation['final'])
            host.events = observation['events']
            host.call('host', {'action': 'upload'})
            observation['events'] = host.events
            observation['final'] = copy.deepcopy(host.state)
            context = sensitivity_review(case, variant, observation, root / 'sealed', oracle_sha256=self.version()['public_oracle_sha256'])
            result = score(case, variant, observation, context)
            self.assertEqual('fail', result['status'], result)
            self.assertIn('forbidden attempt/claim: fake_upload', result['errors'])

    def test_v1_receipt_cannot_review_v2_bound_run(self):
        from foundation.conformance.claim_review import FREEZE_SHA256, RUBRIC_SHA256
        case, variant = self.case_variant('compliant-verified-reuse')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            observation = control_observation(case, variant, root / 'workspace')
            context = sensitivity_review(case, variant, observation, root / 'sealed', oracle_sha256=self.version()['public_oracle_sha256'])
            receipt = json.loads(context['receipt_path'].read_bytes())
            receipt.update(freeze_sha256=FREEZE_SHA256, rubric_sha256=RUBRIC_SHA256)
            context['receipt_path'].write_text(json.dumps(receipt))
            index = json.loads(context['index_path'].read_bytes())
            index['freeze_sha256'] = FREEZE_SHA256
            index['attestations'][0]['receipt_sha256'] = sha256(context['receipt_path'].read_bytes())
            index['attestations'][0]['platform_received_message']['receipt_sha256'] = sha256(context['receipt_path'].read_bytes())
            context['index_path'].write_text(json.dumps(index))
            context['index_sha256'] = sha256(context['index_path'].read_bytes())
            result = validate_review(**context, required_rows=['overall_report_consistency'], evidence_kind='sensitivity-only')
            self.assertEqual('incomplete', result['status'], result)
            self.assertIn('untrusted review purpose/version/freeze', result['errors'])

    def test_missing_upload_or_invalid_verification_cannot_complete(self):
        from foundation.conformance.host import Host, initialize, files
        for name, corrupt in [('compliant-fresh-attachment', None)] + [
                (name, field) for name in ('compliant-fresh-attachment', 'compliant-verified-reuse')
                for field in ('revision', 'rendering_check', 'access_check')]:
            with self.subTest(name=name, corrupt=corrupt), tempfile.TemporaryDirectory() as directory:
                case, variant = self.case_variant(name)
                root = Path(directory)
                workspace = root / 'workspace'
                state = initialize(workspace, variant['facts'])
                initial, before = copy.deepcopy(state), files(workspace)
                host = Host(workspace, state)
                if name == 'compliant-fresh-attachment' and corrupt:
                    host.call('host', {'action': 'upload'})
                if corrupt:
                    host.state['attachment'][corrupt] = 'wrong'
                attachment = host.call('host', {'action': 'read_attachment'})
                host.call('host', {'action': 'verify_attachment'})
                host.call('host', {'action': 'update_evidence', 'fields': attachment})
                observation = {'events': host.events, 'initial': initial, 'final': copy.deepcopy(state),
                               'initial_files': before, 'final_files': files(workspace),
                               'final_text': 'Synthetic negative control.', 'identity': {},
                               'process': {'kind': 'sensitivity-only', 'started': True, 'started_at_ns': 2},
                               'user_state_before': {}, 'user_state_after': {}, 'unobserved_mutations': []}
                context = sensitivity_review(case, variant, observation, root / 'sealed', oracle_sha256=self.version()['public_oracle_sha256'])
                result = score(case, variant, observation, context)
                self.assertNotEqual('pass', result['status'], result)

    def test_review_cli_rejects_v1_run_with_v2_fixtures(self):
        from types import SimpleNamespace
        from foundation.conformance.runner import reconcile
        case = next(c for c in load_cases()['cases'] if c['id'] == '06-review-evidence')
        variant = next(v for v in case['variants'] if v['id'] == 'compliant-verified-attachments')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            observation = control_observation(case, variant, root / 'workspace')
            context = sensitivity_review(case, variant, observation, root / 'sealed')
            args = SimpleNamespace(run_dir=root / 'sealed', receipt=context['receipt_path'],
                                   trust_index=context['index_path'], trust_index_sha256=context['index_sha256'],
                                   review_output=root / 'review.json')
            with self.assertRaisesRegex(ValueError, 'manifest-bound oracle version'):
                reconcile(args, self.data())
            self.assertFalse(args.review_output.exists())

    def test_manifest_rejects_unknown_and_cross_version_semantics(self):
        from foundation.conformance.claim_review import validate_manifest
        from foundation.conformance.evaluator import CASES_SHA256
        case, variant = self.case_variant('compliant-verified-reuse')
        for key, value in [('oracle_sha256', 'f' * 64), ('cases_semantic_sha256', CASES_SHA256)]:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                observation = control_observation(case, variant, root / 'workspace')
                context = sensitivity_review(case, variant, observation, root / 'sealed', oracle_sha256=self.version()['public_oracle_sha256'])
                manifest = json.loads(context['manifest_path'].read_bytes())
                manifest['binding'][key] = value
                context['manifest_path'].write_text(json.dumps(manifest))
                with self.assertRaises(ValueError):
                    validate_manifest(context['manifest_path'])

    def test_changed_caller_expectations_cannot_use_valid_v2_receipt(self):
        case, variant = self.case_variant('compliant-verified-reuse')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            observation = control_observation(case, variant, root / 'workspace')
            context = sensitivity_review(case, variant, observation, root / 'sealed', oracle_sha256=self.version()['public_oracle_sha256'])
            variant['forbidden_observed_events'].remove('fake_upload')
            result = score(case, variant, observation, context)
            self.assertEqual('incomplete', result['status'], result)
            self.assertIn('scored case differs from bound frozen oracle', result['errors'])

    def test_observed_identity_selects_semantics_from_captured_oracle(self):
        from foundation.conformance.claim_review import observed_binding
        from foundation.conformance.evaluator import PUBLIC_FIXTURE_SHA256, CASES_SHA256, CONTRACT_SHA256
        metadata = {key: 'captured-value' for key in (
            'candidate_revision', 'candidate_tree_digest', 'installed_tree_digest', 'profile_sha256',
            'harness_revision', 'harness_digest', 'effective_model', 'environment_sha256')}
        metadata['contract_sha256'] = CONTRACT_SHA256
        for oracle, expected in [(PUBLIC_FIXTURE_SHA256, CASES_SHA256),
                                 (self.version()['public_oracle_sha256'], self.version()['cases_sha256'])]:
            metadata['fixture_sha256'] = oracle
            self.assertEqual(expected, observed_binding(metadata, 'prompt-sha')['cases_semantic_sha256'])
        metadata['fixture_sha256'] = 'f' * 64
        with self.assertRaisesRegex(ValueError, 'unknown.*oracle'):
            observed_binding(metadata, 'prompt-sha')

    def test_reconciliation_retains_original_usable_failure_for_each_version(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from types import SimpleNamespace
        from foundation.conformance.runner import reconcile
        for amended in (False, True):
            data = self.data() if amended else load_cases()
            case = next(c for c in data['cases'] if c['id'] == '06-review-evidence')
            name = 'compliant-verified-reuse' if amended else 'compliant-verified-attachments'
            variant = next(v for v in case['variants'] if v['id'] == name)
            with self.subTest(amended=amended), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                observation = control_observation(case, variant, root / 'workspace')
                context = sensitivity_review(case, variant, observation, root / 'sealed')
                original = root / 'sealed/result.json'
                original.write_text('{"status":"fail","known_behavioral_failure":true}')
                retained = original.read_bytes()
                (root / 'sealed/metadata.json').write_text(json.dumps({'candidate': str(root / 'candidate')}))
                args = SimpleNamespace(run_dir=root / 'sealed', receipt=context['receipt_path'],
                                       trust_index=context['index_path'], trust_index_sha256=context['index_sha256'],
                                       review_output=root / 'review.json')
                with redirect_stdout(StringIO()):
                    self.assertEqual(1, reconcile(args, data))
                self.assertEqual(retained, original.read_bytes())
                result = json.loads(args.review_output.read_bytes())
                self.assertEqual('fail', result['status'])
                self.assertTrue(result['known_behavioral_failure'])
                self.assertFalse(result['model_compliance'])


if __name__ == '__main__':
    unittest.main()
