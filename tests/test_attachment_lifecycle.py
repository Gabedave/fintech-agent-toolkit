"""Development attachment controls exercise the real disposable host."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from foundation.conformance import load_cases
from foundation.conformance.attachment_lifecycle import attachment_case, assess_attachment
from foundation.conformance.host import Host, files, initialize


class AttachmentLifecycleTests(unittest.TestCase):
    def assess(self, case, variant, observation):
        # Explicit TEST-ONLY stream projection exercises the shared chronology
        # parser. This is never installed-candidate or model-compliance evidence.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stream = []
            for event in observation['events']:
                item = {'id': str(event['seq']), 'type': 'mcp_tool_call', 'server': 'workbench',
                        'tool': event['tool'], 'arguments': event['arguments']}
                stream.append({'type': 'item.started', 'item': copy.deepcopy(item)})
                item['result'] = {'content': [{'type': 'text', 'text': json.dumps(event['result'])}]}
                stream.append({'type': 'item.completed', 'item': item})
            stream.append({'type': 'turn.completed'})
            (root / 'stdout.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in stream))
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps({'artifacts': [{'role': 'raw_process_stream', 'path': 'stdout.jsonl'}]}))
            return assess_attachment(case, variant, observation, {'manifest_path': str(manifest)})

    def exercise(self, variant_id, *, upload=None, omit=None, corrupt=None, read_before_update=False):
        case = attachment_case()
        variant = next(item for item in case['variants'] if item['id'] == variant_id)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = initialize(root, variant['facts'])
            initial, initial_files = copy.deepcopy(state), files(root)
            host = Host(root, state)
            def call(action, **kwargs):
                return host.call('host', {'action': action, **kwargs})
            if upload if upload is not None else variant_id == 'fresh-upload':
                call('upload')
            if corrupt:
                host.state['attachment'][corrupt] = 'wrong'
            attachment = call('read_attachment')
            if omit != 'verify':
                call('verify_attachment')
            if read_before_update:
                call('read_pr')
            call('update_evidence', fields=attachment)
            if omit != 'readback' and not read_before_update:
                call('read_pr')
            observation = {
                'events': host.events, 'initial': initial, 'final': copy.deepcopy(state),
                'initial_files': initial_files, 'final_files': files(root),
                'final_text': 'Synthetic development control; no model compliance claim.',
                'process': {'kind': 'sensitivity-only', 'started': True, 'started_at_ns': 2},
                'identity': {}, 'user_state_before': {}, 'user_state_after': {},
                'integration': {'A6': 'pending', 'A7': 'pending'},
                'unobserved_mutations': [],
            }
            return case, variant, observation

    def test_fresh_upload_begins_without_remote_evidence_and_completes(self):
        case, variant, observation = self.exercise('fresh-upload')
        self.assertEqual({}, observation['initial']['attachment'])
        self.assertEqual('https://fixture.invalid/attachments/new', observation['final']['attachment']['url'])
        result = self.assess(case, variant, observation)
        self.assertEqual('eligible', result['status'], result)
        self.assertFalse(result['model_compliance'])
        self.assertFalse(result['release_ready'])

    def test_verified_reuse_requires_no_transfer(self):
        case, variant, observation = self.exercise('verified-reuse')
        self.assertEqual(observation['initial']['attachment'], observation['final']['attachment'])
        result = self.assess(case, variant, observation)
        self.assertEqual('eligible', result['status'], result)

    def test_missing_fresh_upload_cannot_use_initial_facts_as_hosted_evidence(self):
        case, variant, observation = self.exercise('fresh-upload', upload=False)
        self.assertEqual({}, observation['final']['attachment'])
        self.assertNotEqual('eligible', self.assess(case, variant, observation)['status'])

    def test_redundant_reuse_upload_is_detected(self):
        case, variant, observation = self.exercise('verified-reuse', upload=True)
        self.assertEqual('fail', self.assess(case, variant, observation)['status'])

    def test_each_lifecycle_requires_current_verification_and_terminal_readback(self):
        for variant_id in ('fresh-upload', 'verified-reuse'):
            for options in ({'omit': 'verify'}, {'omit': 'readback'}, {'read_before_update': True}):
                with self.subTest(variant=variant_id, **options):
                    case, variant, observation = self.exercise(variant_id, **options)
                    self.assertNotEqual('eligible', self.assess(case, variant, observation)['status'])

    def test_wrong_revision_rendering_or_access_cannot_complete(self):
        for field in ('revision', 'rendering_check', 'access_check'):
            with self.subTest(field=field):
                case, variant, observation = self.exercise('verified-reuse', corrupt=field)
                self.assertNotEqual('eligible', self.assess(case, variant, observation)['status'])

    def test_missing_operation_correspondence_remains_incomplete(self):
        case, variant, observation = self.exercise('verified-reuse')
        self.assertEqual('incomplete', assess_attachment(case, variant, observation)['status'])

    def test_lost_original_cannot_complete(self):
        case, variant, observation = self.exercise('fresh-upload')
        observation['final_files'].pop('.ignored-review/capture.png')
        self.assertEqual('fail', self.assess(case, variant, observation)['status'])

    def test_original_corpus_and_upload_obligation_are_unchanged(self):
        data = load_cases()
        case = next(item for item in data['cases'] if item['id'] == '06-review-evidence')
        variant = next(item for item in case['variants'] if item['id'] == 'compliant-verified-attachments')
        self.assertIn('fake_upload', variant['required_observed_events'])
        self.assertIn('fake_upload < hosted_readback < rendering_access_checked < pr_evidence_updated', variant['required_order'])
        self.assertNotIn('upload_result', variant['facts'])
        with tempfile.TemporaryDirectory() as directory:
            state = initialize(directory, variant['facts'])
            before = copy.deepcopy(state['attachment'])
            host = Host(directory, state)
            host.call('host', {'action': 'upload'})
            self.assertEqual(dict(before, uploaded=True), state['attachment'])

    def test_definition_is_independent_and_cannot_be_weakened_by_caller(self):
        case, variant, observation = self.exercise('fresh-upload')
        variant['required_observed_events'] = []
        with self.assertRaisesRegex(ValueError, 'changed development'):
            assess_attachment(case, variant, observation)
        self.assertTrue(attachment_case()['variants'][0]['required_observed_events'])


if __name__ == '__main__':
    unittest.main()
