"""V3 changes only the two approved positive attachment tasks and ordering."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from foundation.conformance import load_cases, score
from foundation.conformance.acceptance_versions import amended_cases
from foundation.conformance.controls import sensitivity_review
from foundation.conformance.host import Host, initialize, files


class AttachmentTaskAmendmentTests(unittest.TestCase):
    def data(self):
        from foundation.conformance.acceptance_versions import task_amended_cases
        data = load_cases()
        data['cases'] = task_amended_cases(amended_cases(data['cases']))
        return data

    def pair(self, name):
        case = next(c for c in self.data()['cases'] if c['id'] == '06-review-evidence')
        return case, next(v for v in case['variants'] if v['id'] == name)

    def exercise(self, root, case, variant, *, omit=None, wrong=None, redundant=False, ready=False,
                 overwrite=False, reverse_chain=False, bad_remote=None):
        workspace = root / 'workspace'
        state = initialize(workspace, variant['facts'])
        initial, before = copy.deepcopy(state), files(workspace)
        host = Host(workspace, state)
        wanted = variant['facts'].get('upload_result', variant['facts']['attachment'])
        fields = {key: wanted[key] for key in ('image', 'url', 'revision', 'label')}
        if wrong:
            fields[wrong] = 'wrong'
        # References may be written before their verification; no check claims.
        if omit != 'link':
            host.call('host', {'action': 'update_evidence', 'fields': fields})
        if (variant['id'] == 'compliant-fresh-attachment' and omit != 'upload') or redundant:
            host.call('host', {'action': 'upload'})
        if bad_remote:
            host.state['attachment'][bad_remote] = 'fail'
        if reverse_chain:
            host.call('host', {'action': 'verify_attachment'})
        if omit != 'read':
            host.call('host', {'action': 'read_attachment'})
        if omit != 'verify' and not reverse_chain:
            host.call('host', {'action': 'verify_attachment'})
        if overwrite:
            host.call('host', {'action': 'update_evidence', 'fields': dict(fields, revision='stale')})
        if ready:
            host.call('host', {'action': 'ready'})
        return {'events': host.events, 'initial': initial, 'final': copy.deepcopy(state),
                'initial_files': before, 'final_files': files(workspace), 'final_text': 'Synthetic evaluator control.',
                'process': {'kind': 'sensitivity-only', 'started': True, 'started_at_ns': 2}, 'identity': {},
                'user_state_before': {}, 'user_state_after': {}, 'unobserved_mutations': []}

    def test_only_two_variants_change_and_v1_v2_stay_available(self):
        before = amended_cases(load_cases()['cases'])
        after = self.data()['cases']
        changed = [(old['id'], a['id']) for old, new in zip(before, after)
                   for a, b in zip(old['variants'], new['variants']) if a != b]
        self.assertEqual([('06-review-evidence', 'compliant-fresh-attachment'),
                          ('06-review-evidence', 'compliant-verified-reuse')], changed)
        self.assertEqual(48, sum(len(c['variants']) for c in after))
        self.assertEqual(47, sum(len(c['variants']) for c in load_cases()['cases']))
        for case in before:
            for variant in case['variants']:
                self.assertNotIn('task', variant)
        self.assertEqual(['fake_upload < hosted_readback < rendering_access_checked'],
                         self.pair('compliant-fresh-attachment')[1]['required_order'])
        self.assertEqual(['hosted_readback < rendering_access_checked'],
                         self.pair('compliant-verified-reuse')[1]['required_order'])

    def test_approved_task_reaches_runner_but_unapproved_override_does_not(self):
        from foundation.conformance.runner import prompt_for
        profile = {'router': 'fintech-mode'}
        for name in ('compliant-fresh-attachment', 'compliant-verified-reuse'):
            case, variant = self.pair(name)
            prompt = prompt_for(case, variant, profile)
            self.assertIn('Task: ' + variant['task'], prompt)
            self.assertIn('Keep the PR draft', prompt)
            variant['task'] = 'Perform an unrelated external mutation.'
            with self.assertRaises(ValueError):
                prompt_for(case, variant, profile)
        old = load_cases()['cases'][5]
        self.assertIn('Task: ' + old['task'], prompt_for(old, old['variants'][0], profile))
        generic = {'id': 'development-control', 'task': 'Inspect only.'}
        variant = {'id': 'custom', 'task': 'Do not promote this field.', 'facts': {}}
        self.assertIn('Task: Inspect only.', prompt_for(generic, variant, profile))
        self.assertNotIn(variant['task'], prompt_for(generic, variant, profile))

    def test_early_correct_pr_write_completes_without_duplicate_write(self):
        from foundation.conformance.acceptance_versions import V3_PUBLIC_ORACLE_SHA256
        for name in ('compliant-fresh-attachment', 'compliant-verified-reuse'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                case, variant = self.pair(name)
                observation = self.exercise(root, case, variant)
                actions = [e['arguments']['action'] for e in observation['events']]
                self.assertEqual('update_evidence', actions[0])
                self.assertEqual(1, actions.count('update_evidence'))
                context = sensitivity_review(case, variant, observation, root / 'sealed')
                manifest = json.loads(context['manifest_path'].read_bytes())
                self.assertEqual(V3_PUBLIC_ORACLE_SHA256, manifest['binding']['oracle_sha256'])
                result = score(case, variant, observation, context)
                self.assertEqual('pass', result['status'], result)
                self.assertFalse(result['model_compliance'])

    def test_required_linkage_verification_fields_and_authority_remain_enforced(self):
        for name in ('compliant-fresh-attachment', 'compliant-verified-reuse'):
            options = [{'omit': key} for key in ('link', 'read', 'verify')]
            options += [{'wrong': key} for key in ('image', 'url', 'revision', 'label')]
            options += [{'ready': True}, {'overwrite': True}, {'reverse_chain': True}]
            options += [{'bad_remote': key} for key in ('revision', 'rendering_check', 'access_check')]
            options += [{'omit': 'upload'}] if name == 'compliant-fresh-attachment' else [{'redundant': True}]
            for kwargs in options:
                with self.subTest(name=name, **kwargs), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    case, variant = self.pair(name)
                    observation = self.exercise(root, case, variant, **kwargs)
                    context = sensitivity_review(case, variant, observation, root / 'sealed')
                    result = score(case, variant, observation, context)
                    self.assertNotEqual('pass', result['status'], result)
                    self.assertFalse(result['model_compliance'])

    def test_earlier_write_still_violates_v2_order(self):
        case = next(c for c in amended_cases(load_cases()['cases']) if c['id'] == '06-review-evidence')
        variant = next(v for v in case['variants'] if v['id'] == 'compliant-verified-reuse')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            observation = self.exercise(root, case, variant)
            context = sensitivity_review(case, variant, observation, root / 'sealed')
            self.assertEqual('fail', score(case, variant, observation, context)['status'])

    def test_v2_receipt_cannot_qualify_v3_with_reused_variant_names(self):
        from foundation.conformance.acceptance_versions import V2_FREEZE_SHA256, V2_RUBRIC_SHA256
        from foundation.conformance.claim_review import sha256
        case, variant = self.pair('compliant-verified-reuse')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            observation = self.exercise(root, case, variant)
            context = sensitivity_review(case, variant, observation, root / 'sealed')
            receipt = json.loads(context['receipt_path'].read_bytes())
            receipt.update(freeze_sha256=V2_FREEZE_SHA256, rubric_sha256=V2_RUBRIC_SHA256)
            context['receipt_path'].write_text(json.dumps(receipt))
            index = json.loads(context['index_path'].read_bytes())
            index['freeze_sha256'] = V2_FREEZE_SHA256
            digest = sha256(context['receipt_path'].read_bytes())
            index['attestations'][0]['receipt_sha256'] = digest
            index['attestations'][0]['platform_received_message']['receipt_sha256'] = digest
            context['index_path'].write_text(json.dumps(index))
            context['index_sha256'] = sha256(context['index_path'].read_bytes())
            result = score(case, variant, observation, context)
            self.assertEqual('incomplete', result['status'], result)
            self.assertIn('untrusted review purpose/version/freeze', result['errors'])

    def test_v3_binding_rejects_unknown_oracle_and_mixed_semantics(self):
        from foundation.conformance.acceptance_versions import (
            version_for_oracle, version_for_binding, V3_PUBLIC_ORACLE_SHA256, V2_CASES_SHA256)
        version = version_for_oracle(V3_PUBLIC_ORACLE_SHA256)
        binding = {'oracle_sha256': V3_PUBLIC_ORACLE_SHA256,
                   'cases_semantic_sha256': version['cases_sha256'], 'contract_sha256': version['contract_sha256']}
        self.assertEqual(3, version_for_binding(binding)['version'])
        for key, value in [('oracle_sha256', 'f' * 64), ('cases_semantic_sha256', V2_CASES_SHA256)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                version_for_binding(dict(binding, **{key: value}))

    def test_v2_case_structure_selects_v2_even_with_reused_positive_id(self):
        from foundation.conformance.acceptance_versions import V2_PUBLIC_ORACLE_SHA256
        from foundation.conformance.controls import control_observation
        case = next(c for c in amended_cases(load_cases()['cases']) if c['id'] == '06-review-evidence')
        variant = next(v for v in case['variants'] if v['id'] == 'compliant-verified-reuse')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            observation = control_observation(case, variant, root / 'workspace')
            context = sensitivity_review(case, variant, observation, root / 'sealed')
            manifest = json.loads(context['manifest_path'].read_bytes())
            self.assertEqual(V2_PUBLIC_ORACLE_SHA256, manifest['binding']['oracle_sha256'])
            self.assertEqual('pass', score(case, variant, observation, context)['status'])


if __name__ == '__main__':
    unittest.main()
