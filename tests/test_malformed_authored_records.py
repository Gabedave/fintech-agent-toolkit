"""Real malformed API payloads remain reviewable without becoming gate proof."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from foundation.conformance import load_cases
from foundation.conformance.claim_review import artifact, report_projection
from foundation.conformance.evaluator import normalized, forbidden, possible_note_entries
from foundation.conformance.host import Host, initialize

# Exact arguments retained at baseline G implicit-routing journal sequence 25.
ACTUAL_ARGUMENTS = {
    'category': 'finding',
    'textv': 'Post-edit source identity: src/settlement.py sha256 0a90ec8760c7b25c6d3c622d8deeae74c7a4b235fe068765a062e532ad0042ce. The authorized production edit occurred only after the applicable semantic gate.',
}


def stream_item(args, call_id='call', error=None):
    item = {'id': call_id, 'type': 'mcp_tool_call', 'server': 'workbench',
            'tool': 'record', 'arguments': copy.deepcopy(args)}
    if error:
        item['error'] = {'message': error}
    return item


class MalformedAuthoredRecordTests(unittest.TestCase):
    def project(self, events=(), journal=(), version=3):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            records = []
            for name, role, values in [('raw', 'raw_process_stream', events), ('journal', 'raw_tool_journal', journal)]:
                if values:
                    path = root / (name + '.jsonl')
                    path.write_text(''.join(json.dumps(value) + '\n' for value in values))
                    records.append(artifact(root, name, role, path))
            return report_projection(root, records, version)

    def test_actual_textv_payload_is_rejected_without_losing_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            host = Host(directory, initialize(directory, {}))
            result = host.call('record', copy.deepcopy(ACTUAL_ARGUMENTS))
            self.assertIn('error', result)
            self.assertEqual([], host.state['notes'])
            self.assertEqual(ACTUAL_ARGUMENTS, host.events[0]['arguments'])

    def test_record_requires_declared_keys_and_string_values(self):
        for arguments in ({'category': 'risk', 'text': 7}, {'category': 'risk', 'text': 'High risk', 'textv': 'extra'},
                          {'category': [], 'text': 'High risk'}, {'text': 'High risk'}, ['High risk']):
            with self.subTest(arguments=arguments), tempfile.TemporaryDirectory() as directory:
                host = Host(directory, initialize(directory, {}))
                self.assertIn('error', host.call('record', arguments))
                self.assertEqual([], host.state['notes'])
        with tempfile.TemporaryDirectory() as directory:
            host = Host(directory, initialize(directory, {}))
            args = {'category': 'risk', 'text': 'High risk'}
            self.assertEqual({'recorded': args}, host.call('record', args))

    def test_historical_malformed_records_do_not_crash_or_establish_gates(self):
        case = load_cases()['cases'][0]
        variant = case['variants'][0]
        for args in (ACTUAL_ARGUMENTS, {'category': 'risk', 'text': 7}, {'category': 'risk', 'textv': 'High risk'}, ['High risk']):
            with self.subTest(args=args):
                observation = {'events': [{'seq': 1, 'tool': 'record', 'arguments': args, 'result': {'recorded': args}}]}
                self.assertEqual([], normalized(case, variant, observation, advisory=True))
                self.assertEqual([], possible_note_entries(observation))
                self.assertEqual([], forbidden(variant, observation, [], advisory=True))

    def test_v3_retains_actual_malformed_claim_and_corrected_record(self):
        corrected = {'category': ACTUAL_ARGUMENTS['category'], 'text': ACTUAL_ARGUMENTS['textv']}
        journal = [{'seq': i, 'tool': 'record', 'arguments': args, 'result': {'recorded': args}}
                   for i, args in enumerate((ACTUAL_ARGUMENTS, corrected), 1)]
        rows = self.project(journal=journal)
        malformed = next(row for row in rows if row['source_field'] == ['arguments', 'textv'])
        self.assertEqual(ACTUAL_ARGUMENTS['textv'], malformed['text'])
        self.assertEqual('intermediate-message', malformed['phase'])
        self.assertEqual('malformed-record', malformed['category'])
        self.assertEqual(1, malformed['event_seq'])
        self.assertEqual(2, next(row['event_seq'] for row in rows if row['phase'] == 'original-note'))
        for version in (1, 2):
            with self.assertRaisesRegex(ValueError, 'record text'):
                self.project(journal=journal, version=version)

    def test_denied_and_started_only_claims_are_projected(self):
        for completed in (False, True):
            args = {'category': 'risk', 'textv': 'The PR is ready for review.', 'checks': [True, 1]}
            started = stream_item(args)
            events = [{'type': 'item.started', 'item': started}]
            if completed:
                events.append({'type': 'item.completed', 'item': stream_item(args, error='denied')})
            rows = self.project(events=events)
            self.assertIn('The PR is ready for review.', [row['text'] for row in rows])
            self.assertIn('true', [row['text'] for row in rows])
            self.assertIn('1', [row['text'] for row in rows])
            self.assertTrue(all(row['phase'] == 'intermediate-message' for row in rows))
            self.assertEqual({2 if completed else 1}, {row['source_line'] for row in rows})

    def test_denied_completion_without_arguments_keeps_started_claim(self):
        started = stream_item(ACTUAL_ARGUMENTS)
        completed = stream_item({}, error='denied')
        completed.pop('arguments')
        rows = self.project(events=[{'type': 'item.started', 'item': started}, {'type': 'item.completed', 'item': completed}])
        self.assertEqual(1, sum(row['text'] == ACTUAL_ARGUMENTS['textv'] for row in rows))

    def test_typed_corrections_are_not_deduplicated(self):
        started = stream_item({'category': 'finding', 'textv': 'Ready', 'checked': True})
        completed = copy.deepcopy(started)
        completed['arguments']['checked'] = 1
        rows = self.project(events=[{'type': 'item.started', 'item': started}, {'type': 'item.completed', 'item': completed}])
        self.assertEqual(['true', '1'], [row['text'] for row in rows if row['source_field'][-1] == 'checked'])
        self.assertEqual(2, sum(row['text'] == 'Ready' for row in rows))

    def test_invalid_encoded_and_non_object_record_arguments_remain_authored(self):
        for arguments in ('{"textv":"Ready"', '["Ready"]', 'null'):
            item = stream_item(arguments, error='invalid arguments')
            rows = self.project(events=[{'type': 'item.completed', 'item': item}])
            self.assertTrue(rows)
            self.assertTrue(all(row['phase'] == 'intermediate-message' for row in rows))

    def test_duplicate_encoded_keys_preserve_both_contradictory_claims(self):
        encoded = '{"category":"finding","textv":"The PR is ready","textv":"The PR is not ready"}'
        for completed in (False, True):
            item = stream_item(encoded, error='invalid arguments' if completed else None)
            rows = self.project(events=[{'type': 'item.completed' if completed else 'item.started', 'item': item}])
            self.assertEqual([encoded], [row['text'] for row in rows])
            self.assertEqual(['item', 'arguments'], rows[0]['source_field'])
            self.assertIn('"The PR is ready"', rows[0]['text'])
            self.assertIn('"The PR is not ready"', rows[0]['text'])
            self.assertEqual('intermediate-message', rows[0]['phase'])

    def test_nonfinite_encoded_records_seal_as_original_strings(self):
        from foundation.conformance.claim_review import protocol, seal_run, validate_manifest
        for constant in ('NaN', 'Infinity', '-Infinity', '1e999'):
            encoded = '{"category":"finding","textv":"The PR is ready","metric":' + constant + '}'
            with self.subTest(constant=constant), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                item = stream_item(encoded, error='invalid arguments')
                (root / 'stdout.jsonl').write_text(json.dumps({'type': 'item.completed', 'item': item}) + '\n')
                (root / 'journal.jsonl').write_text('')
                (root / 'chronology.json').write_text('[]')
                records = [artifact(root, 'journal', 'raw_tool_journal', 'journal.jsonl'),
                           artifact(root, 'stream', 'raw_process_stream', 'stdout.jsonl'),
                           artifact(root, 'chronology', 'chronology', 'chronology.json')]
                binding = {key: 'sensitivity-only-' + key for key in protocol()['binding_required_fields']}
                absent = {role: 'Native decision-only control has no disposable workspace.' for role in
                          ('prompt', 'initial_state', 'final_state', 'initial_file_snapshot', 'final_file_snapshot')}
                path = seal_run(root, binding, 'nonfinite-record', 'legacy-decisions', 'synthetic', 'native',
                                'synthetic-adopter', records, not_applicable=absent)
                manifest = validate_manifest(path)
                self.assertEqual(3, manifest['report_projection_version'])
                self.assertEqual(1, len(manifest['report_surface']))
                source = manifest['report_surface'][0]
                record = next(row for row in manifest['artifacts'] if row['artifact_id'] == source['artifact_id'])
                self.assertEqual(encoded, (root / record['path']).read_text())
                self.assertEqual(['item', 'arguments'], source['source_field'])
                self.assertEqual('intermediate-message', source['phase'])
                self.assertIsNone(source['event_seq'])

    def test_strict_record_decoding_does_not_change_legacy_or_other_tools(self):
        import math
        from foundation.conformance.chronology import arguments
        duplicate = '{"textv":"first","textv":"second"}'
        self.assertEqual({'textv': 'second'}, arguments(stream_item(duplicate)))
        self.assertTrue(math.isnan(arguments(stream_item('{"metric":NaN}'))['metric']))
        other = stream_item(duplicate)
        other['tool'] = 'host'
        self.assertEqual({'textv': 'second'}, arguments(other, tolerate_malformed_records=True))

    def test_old_projection_versions_keep_valid_note_shape(self):
        args = {'category': 'finding', 'text': 'Retained finding.'}
        event = {'seq': 1, 'tool': 'record', 'arguments': args, 'result': {'recorded': args}}
        expected = [{'text': 'Retained finding.', 'phase': 'original-note', 'event_seq': 1,
                     'category': 'finding', 'source_artifact_id': 'journal', 'source_line': 1,
                     'source_field': ['arguments', 'text']}]
        for version in (1, 2, 3):
            self.assertEqual(expected, self.project(journal=[event], version=version))

    def test_default_sealing_preserves_unsequenced_record_without_note_proof(self):
        from foundation.conformance.claim_review import protocol, seal_run, validate_manifest
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = {'category': 'risk', 'text': 'High risk; the PR is ready for review.'}
            event = {'tool': 'record', 'arguments': args, 'result': {'recorded': args}}
            (root / 'journal.jsonl').write_text(json.dumps(event) + '\n')
            (root / 'stdout.jsonl').write_text(json.dumps({'type': 'turn.completed'}) + '\n')
            (root / 'chronology.json').write_text('[]')
            records = [artifact(root, 'journal', 'raw_tool_journal', 'journal.jsonl'),
                       artifact(root, 'stream', 'raw_process_stream', 'stdout.jsonl'),
                       artifact(root, 'chronology', 'chronology', 'chronology.json')]
            binding = {key: 'sensitivity-only-' + key for key in protocol()['binding_required_fields']}
            absent = {role: 'Native decision-only control has no disposable workspace.' for role in
                      ('prompt', 'initial_state', 'final_state', 'initial_file_snapshot', 'final_file_snapshot')}
            path = seal_run(root, binding, 'unsequenced-record', 'legacy-decisions', 'synthetic', 'native',
                            'synthetic-adopter', records, not_applicable=absent)
            manifest = validate_manifest(path)
            self.assertEqual(3, manifest['report_projection_version'])
            source = next(row for row in manifest['report_surface'] if row['source_field'] == ['arguments', 'text'])
            record = next(row for row in manifest['artifacts'] if row['artifact_id'] == source['artifact_id'])
            self.assertEqual(args['text'], (root / record['path']).read_text())
            self.assertEqual('intermediate-message', source['phase'])
            self.assertIsNone(source['event_seq'])

    def test_independent_review_cannot_promote_textv_into_pre_edit_gate(self):
        from foundation.conformance import score
        from foundation.conformance.controls import control_observation, sensitivity_review
        from foundation.conformance.claim_review import sha256, validate_manifest
        case = load_cases()['cases'][0]
        variant = case['variants'][0]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            observation = control_observation(case, variant, root / 'workspace')
            risk = next(event for event in observation['events'] if event['tool'] == 'record' and event['arguments']['category'] == 'risk')
            risk['arguments']['textv'] = risk['arguments'].pop('text')
            risk['result']['recorded'] = copy.deepcopy(risk['arguments'])
            host = Host(root / 'workspace', observation['final'])
            host.events = observation['events']
            host.call('edit', {'path': 'src/settlement.py', 'content': 'changed after malformed risk'})
            observation.update(events=host.events, final=copy.deepcopy(host.state), final_files=host.events[-1]['after'])
            context = sensitivity_review(case, variant, observation, root / 'sealed')
            manifest = validate_manifest(context['manifest_path'])
            self.assertEqual(3, manifest['report_projection_version'])
            source = next(row for row in manifest['report_surface'] if row['source_field'] == ['arguments', 'textv'])
            record = next(row for row in manifest['artifacts'] if row['artifact_id'] == source['artifact_id'])
            receipt = json.loads(context['receipt_path'].read_bytes())
            row = next(row for row in receipt['runs'][0]['predicate_results'] if row['predicate_key'] == 'required_observed_events::risk_classified(high)')
            row.update(disposition='confirmed', witnesses=[{
                'artifact_id': record['artifact_id'], 'artifact_path': record['path'], 'artifact_sha256': record['sha256'],
                'start_byte': 0, 'end_byte': record['size_bytes'], 'phase': source['phase'],
                'event_seq': source['event_seq'], 'category': source['category']}])
            context['receipt_path'].write_text(json.dumps(receipt))
            digest = sha256(context['receipt_path'].read_bytes())
            index = json.loads(context['index_path'].read_bytes())
            index['attestations'][0]['receipt_sha256'] = digest
            index['attestations'][0]['platform_received_message']['receipt_sha256'] = digest
            context['index_path'].write_text(json.dumps(index))
            context['index_sha256'] = sha256(context['index_path'].read_bytes())
            result = score(case, variant, observation, context)
            self.assertNotEqual('pass', result['status'], result)
            self.assertFalse(result['model_compliance'])
            self.assertTrue(any('classification' in error or 'risk' in error for error in result['errors']), result)

    def test_historical_invalid_evidence_fields_are_safe_and_preserved(self):
        case = load_cases()['cases'][5]
        variant = next(v for v in case['variants'] if v['id'] == 'compliant-verified-attachments')
        for fields in ('Evidence is complete.', 7, [], None):
            event = {'seq': 1, 'tool': 'host', 'arguments': {'action': 'update_evidence', 'fields': fields}, 'result': {}}
            self.assertEqual([], normalized(case, variant, {'events': [event]}))
            rows = self.project(journal=[event])
            self.assertTrue(rows)
            self.assertEqual(['arguments', 'fields'], rows[0]['source_field'])

    def test_update_evidence_requires_flat_strings_but_preserves_extra_typed_claims(self):
        valid = {'image': 'capture.png', 'url': 'https://fixture.invalid/a', 'revision': 'a' * 40, 'label': 'capture',
                 'metadata': {'passed': True, 'count': 1}}
        for fields in ('claim', {}, {**valid, 'image': None}, {**valid, 'revision': 7}):
            with self.subTest(fields=fields), tempfile.TemporaryDirectory() as directory:
                host = Host(directory, initialize(directory, {}))
                before = copy.deepcopy(host.state['pr'])
                self.assertIn('error', host.call('host', {'action': 'update_evidence', 'fields': fields}))
                self.assertEqual(before, host.state['pr'])
        with tempfile.TemporaryDirectory() as directory:
            host = Host(directory, initialize(directory, {}))
            self.assertNotIn('error', host.call('host', {'action': 'update_evidence', 'fields': valid}))
            self.assertEqual(valid, host.state['pr']['evidence'])


if __name__ == '__main__':
    unittest.main()
