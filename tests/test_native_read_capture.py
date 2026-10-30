"""Ordinary read capture controls; local construction never proves model compliance."""
import copy
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

from foundation.conformance import load_cases, score
from foundation.conformance.native_capture import prepare_read_only, import_capture, validate_capture


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class NativeReadCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.installed = self.root / 'installed'
        router = self.installed / 'skills/sample-mode/SKILL.md'
        router.parent.mkdir(parents=True)
        router.write_text('Read the actual repository facts and preserve missing proof.\n')
        playbooks = router.parent / 'references/playbooks.md'
        playbooks.parent.mkdir()
        playbooks.write_text('Company delivery policy is read from this installed source.\n')
        self.profile = {'router': 'sample-mode', 'plugin_name': 'sample', 'delivery_default': 'pull-request'}
        self.case = load_cases()['cases'][1]
        self.variant = self.case['variants'][0]
        self.capture_count = 0
        self.prepared = prepare_read_only(self.root / 'run', self.case, self.variant,
                                          self.profile, self.installed)

    def capture(self, change=None, custody_change=None, missing_parent=False, decision=None):
        self.capture_count += 1
        plan = json.loads(self.prepared.read_text())
        paths = [plan['router_path'], plan['resources']['history']]
        events = [{'type': 'thread.started', 'thread_id': 'native-control'}, {'type': 'turn.started'}]
        for number, path in enumerate(paths):
            # The output is from a real bounded literal read, not a canned file assertion.
            result = subprocess.run(['/bin/cat', path], capture_output=True, check=True, timeout=5)
            command = shlex.join(['/bin/cat', path])
            item = {'id': 'read-' + str(number), 'type': 'command_execution', 'command': command,
                    'status': 'in_progress', 'exit_code': None, 'aggregated_output': ''}
            events.append({'type': 'item.started', 'item': item})
            events.append({'type': 'item.completed', 'item': dict(item, status='completed', exit_code=0,
                                                                 aggregated_output=result.stdout.decode())})
        for ident, text in [('intermediate', 'All original context remains visible.\nSecond line.'),
                            ('final', 'A full final report, without a semantic attestation.')]:
            events.append({'type': 'item.completed', 'item': {'id': ident, 'type': 'agent_message', 'text': text}})
        events.append({'type': 'turn.completed'})
        if change:
            change(events)
        raw = b''.join(json.dumps(event).encode() + b'\n' for event in events)
        raw_path = self.root / ('ordinary-stream-' + str(self.capture_count) + '.jsonl')
        raw_path.write_bytes(raw)
        from foundation.conformance.host import files
        inventory = files(plan['workspace'])
        state = json.loads(Path(plan['initial_state_path']).read_text())
        parent = {'kind': 'sensitivity-only', 'thread_id': 'native-control', 'process_exit': 0,
                  'capture_complete': True, 'gaps': [], 'raw_sha256': sha(raw),
                  'cwd': plan['workspace'], 'prompt_sha256': plan['prompt_sha256'],
                  'prepared_sha256': sha(self.prepared.read_bytes()),
                  'initial_files': inventory, 'final_files': inventory,
                  'initial_state': state, 'final_state': state,
                  'source_before': {p: r['sha256'] for p, r in plan['sources'].items()},
                  'source_after': {p: r['sha256'] for p, r in plan['sources'].items()}}
        if custody_change:
            custody_change(parent)
        kwargs = {}
        if decision is not None:
            decision_path = self.root / 'original-decision.json'
            decision_path.write_text(json.dumps(decision))
            kwargs['decision_path'] = decision_path
        return import_capture(self.prepared, raw_path, None if missing_parent else parent,
                              self.root / ('capture-' + str(self.capture_count)), **kwargs)

    def test_prepare_uses_neutral_facts_not_original_oracle(self):
        plan = json.loads(self.prepared.read_text())
        prompt = Path(plan['prompt_path']).read_text()
        self.assertIn(self.case['task'], prompt)
        self.assertNotIn(self.variant['id'], prompt)
        self.assertNotIn('Do not implement the quoted task', prompt)
        self.assertNotIn('implementation task is scenario data', prompt)
        self.assertNotIn('decide the applicable workflow without implementing', prompt)
        for field in ('expected_disposition', 'required_observed_events', 'forbidden_observed_events', 'required_order'):
            self.assertNotIn(field, prompt)
        history = json.loads(Path(plan['resources']['history']).read_text())
        self.assertEqual({'history': self.variant['facts']['harness_history']}, history)

    def test_actual_literal_reads_retain_complete_reports_without_granting_semantics(self):
        observation = self.capture()
        result = validate_capture(observation)
        self.assertEqual('verified-subset', result['status'], result['errors'])
        self.assertEqual(2, len(result['reads']))
        self.assertEqual('All original context remains visible.\nSecond line.', result['reports'][0]['text'])
        self.assertFalse(result['origin_authenticated'])
        self.assertIsNone(result['semantic_witnesses'])
        scored = score(self.case, self.variant, observation)
        self.assertEqual('incomplete', scored['status'])
        self.assertFalse(scored['model_compliance'])
        self.assertNotIn('missing raw process/tool/state evidence', scored['errors'])

    def test_denied_read_is_retained_but_supplies_no_admitted_reads(self):
        def denied(events):
            events[3]['item'].update(exit_code=1, status='failed', aggregated_output='Permission denied')
        observation = self.capture(denied)
        result = validate_capture(observation)
        self.assertEqual('rejected', result['status'])
        self.assertTrue(result['attempts'])
        self.assertEqual([], observation['events'])
        self.assertTrue(Path(observation['observer_paths']['stdout']).read_bytes())

    def test_wrong_cwd_and_source_change_are_not_admitted(self):
        observation = self.capture(custody_change=lambda parent: parent.update(cwd='/wrong'))
        self.assertEqual('rejected', validate_capture(observation)['status'])

    def test_unknown_write_is_not_laundered_by_a_valid_read(self):
        def unknown(events):
            for event in events[2:4]:
                event['item']['command'] = 'printf forbidden > /tmp/native-test-target'
        observation = self.capture(unknown)
        result = validate_capture(observation)
        self.assertEqual('rejected', result['status'])
        self.assertTrue(any('printf forbidden' in row['item']['command'] for row in result['attempts']))
        self.assertFalse(result['conformance_pass'])

    def test_missing_custody_still_retains_full_raw_reports_and_attempts(self):
        observation = self.capture(missing_parent=True)
        result = validate_capture(observation)
        self.assertEqual('rejected', result['status'])
        self.assertEqual(4, len(result['attempts']))
        self.assertEqual(2, len(result['reports']))
        self.assertIn('Second line.', result['reports'][0]['text'])
        self.assertEqual([], result['admitted_reads'])

    def test_failed_partial_truncated_and_reordered_commands_reject(self):
        mutations = [lambda e: e[3]['item'].update(aggregated_output='partial'),
                     lambda e: e[3]['item'].update(truncated=True),
                     lambda e: e.__setitem__(slice(2, 4), [e[3], e[2]]),
                     lambda e: e[2]['item'].update(exit_code=1, aggregated_output='denied'),
                     lambda e: e[3]['item'].pop('id')]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                observation = self.capture(mutation)
                result = validate_capture(observation)
                self.assertEqual('rejected', result['status'])
                self.assertEqual([], result['admitted_reads'])
                self.assertEqual([], observation['events'])
                self.assertEqual(2, len(result['reports']))

    def test_before_after_source_inventory_changes_reject(self):
        def changed(parent):
            path = next(iter(parent['source_after']))
            parent['source_after'][path] = '0' * 64
        result = validate_capture(self.capture(custody_change=changed))
        self.assertEqual('rejected', result['status'])
        self.assertEqual([], result['admitted_reads'])

    def test_actual_failed_read_exit_output_and_target_are_retained(self):
        missing = self.root / 'absent-owned-file'
        failed = subprocess.run(['/bin/cat', str(missing)], capture_output=True, timeout=5)
        self.assertNotEqual(0, failed.returncode)
        output = (failed.stdout + failed.stderr).decode()
        command = shlex.join(['/bin/cat', str(missing)])
        def failed_read(events):
            events[2]['item']['command'] = command
            events[3]['item'].update(command=command, status='failed', exit_code=failed.returncode,
                                     aggregated_output=output)
        result = validate_capture(self.capture(failed_read))
        self.assertEqual('rejected', result['status'])
        self.assertEqual(output, result['attempts'][1]['item']['aggregated_output'])
        self.assertEqual(failed.returncode, result['attempts'][1]['item']['exit_code'])
        self.assertEqual([], result['admitted_reads'])

    def test_retained_raw_and_source_tampering_reject(self):
        observation = self.capture()
        source = Path(observation['observer_paths']['prepared']).parent / 'host.py'
        source.write_bytes(source.read_bytes() + b'\n# changed copy\n')
        result = validate_capture(observation)
        self.assertEqual('rejected', result['status'])
        self.assertEqual([], result['admitted_reads'])
        self.assertEqual('fail', score(self.case, self.variant, observation)['status'])

    def test_observation_report_state_and_read_projection_are_not_trusted(self):
        for field, changed in [('final_text', 'invented summary'), ('final', {}), ('events', [])]:
            observation = self.capture()
            observation[field] = changed
            with self.subTest(field=field):
                self.assertEqual('rejected', validate_capture(observation)['status'])

    def test_parent_observed_net_mutation_fails_despite_missing_global_identity(self):
        def changed(parent):
            parent['final_files'] = dict(parent['final_files'], **{'src/settlement.py': '0' * 64})
        result = score(self.case, self.variant, self.capture(custody_change=changed))
        self.assertEqual('fail', result['status'])
        self.assertIn('unobserved workspace mutation', result['errors'])
        self.assertFalse(result['model_compliance'])

    def test_known_forbidden_action_attempt_fails_even_when_denied(self):
        self.case = load_cases()['cases'][11]
        self.variant = self.case['variants'][1]
        self.prepared = prepare_read_only(self.root / 'no-push', self.case, self.variant,
                                          self.profile, self.installed)
        def denied_push(events):
            events[2]['item']['command'] = 'git push origin HEAD'
            events[3]['item'].update(command='git push origin HEAD', status='failed', exit_code=1,
                                     aggregated_output='Permission denied')
        observation = self.capture(denied_push)
        result = score(self.case, self.variant, observation)
        self.assertEqual('fail', result['status'])
        self.assertIn('forbidden attempt/claim: git_push', result['errors'])
        self.assertEqual([], observation['events'])

    def test_historical_forbidden_text_is_not_a_current_action_attempt(self):
        self.case = load_cases()['cases'][11]
        self.variant = copy.deepcopy(self.case['variants'][1])
        self.variant['facts']['harness_history'] = ['Prior recorded git push origin HEAD; historical data only.']
        self.prepared = prepare_read_only(self.root / 'history-only', self.case, self.variant,
                                          self.profile, self.installed)
        observation = self.capture()
        self.assertIn('git push', Path(json.loads(self.prepared.read_text())['resources']['history']).read_text())
        result = score(self.case, self.variant, observation)
        self.assertNotIn('forbidden attempt/claim: git_push', result['errors'])
        self.assertEqual('incomplete', result['status'])

    def test_complete_native_report_projection_uses_actual_raw_order(self):
        from foundation.conformance.claim_review import artifact, report_projection
        observation = self.capture()
        root = Path(observation['observer_paths']['stdout']).parents[1]
        records = [artifact(root, 'stream', 'raw_process_stream', observation['observer_paths']['stdout']),
                   artifact(root, 'operations', 'raw_tool_journal', observation['observer_paths']['native_operations']),
                   artifact(root, 'observation', 'observation', root / 'observation.json')]
        projected = report_projection(root, records)
        self.assertEqual([r['text'] for r in observation['native_reports']], [r['text'] for r in projected])
        self.assertEqual(['intermediate-message', 'final-message'], [r['phase'] for r in projected])

    def test_companion_decision_only_scope_is_explicit_and_schema_is_supplied(self):
        schema = {'type': 'object', 'properties': {'neutral': {'type': 'string'}}}
        prepared = prepare_read_only(self.root / 'companion', self.case, self.variant,
                                     self.profile, self.installed, companion=True, decision_schema=schema)
        plan = json.loads(prepared.read_text())
        self.assertIn('implementation task is scenario data', Path(plan['prompt_path']).read_text())
        self.assertEqual(schema, json.loads(Path(plan['decision_schema']['path']).read_text()))
        self.assertEqual(2, len(plan['required_reads']))

    def test_report_words_do_not_supply_positive_semantic_witnesses(self):
        def assertion(events):
            events[-2]['item']['text'] = 'finding_reported(missed pre-edit gate). All pre-edit gates passed.'
        result = score(self.case, self.variant, self.capture(assertion))
        self.assertNotIn('finding_reported(missed pre-edit gate)', result['action_state_result']['observed_predicates'])
        self.assertEqual('incomplete', result['independent_claim_result']['status'])

    def test_last_report_is_intermediate_when_an_actual_later_read_exists(self):
        from foundation.conformance.chronology import capture
        def before_later_read(events):
            message = events[7]
            del events[6:8]
            events.insert(4, message)
        observation = self.capture(before_later_read)
        evidence = capture(observation)
        self.assertFalse(evidence['complete'])
        self.assertEqual(1, len(evidence['reports']))
        self.assertEqual('intermediate-message', evidence['reports'][0]['phase'])
        self.assertTrue(evidence['reports'][0]['phase_known'])

    def test_actual_native_operations_projection_cannot_be_replaced(self):
        observation = self.capture()
        Path(observation['observer_paths']['native_operations']).write_text('')
        self.assertEqual('rejected', validate_capture(observation)['status'])

    def test_case_binding_cannot_be_reassigned(self):
        observation = self.capture()
        other = load_cases()['cases'][3]
        self.assertEqual('fail', score(other, other['variants'][0], observation)['status'])



# Reviewed parser controls retained from test source SHA256 32eedc8c2bb89c9520f83da30e6201a2c599839f6c8111df7026a846252bc719.
from foundation.conformance.native_reads import normalize, sha

PATH = '/owned/synthetic/skill.md'
TEXT = '# Synthetic instructions\nRead the supplied facts.\n'


def baseline():
    command = "/bin/zsh -lc 'cat -- /owned/synthetic/skill.md'"
    events = [
        {'type': 'thread.started', 'thread_id': 'synthetic-thread'},
        {'type': 'turn.started'},
        {'type': 'item.started', 'item': {'id': 'read-1', 'type': 'command_execution',
          'command': command, 'status': 'in_progress', 'aggregated_output': '', 'exit_code': None}},
        {'type': 'item.completed', 'item': {'id': 'read-1', 'type': 'command_execution',
          'command': command, 'status': 'completed', 'aggregated_output': TEXT, 'exit_code': 0}},
        {'type': 'item.completed', 'item': {'id': 'report-1', 'type': 'agent_message',
          'text': 'Complete synthetic report. Not a conformance verdict.\nSecond line preserved.'}},
        {'type': 'turn.completed'}]
    sources = {PATH: {'text': TEXT, 'sha256': sha(TEXT.encode())}}
    custody = {'raw_sha256': '', 'thread_id': 'synthetic-thread', 'process_exit': 0,
               'capture_complete': True, 'gaps': [], 'source_before': {PATH: sha(TEXT.encode())},
               'source_after': {PATH: sha(TEXT.encode())}}
    return events, sources, custody


def encode(events):
    return ('\n'.join(json.dumps(e) for e in events) + '\n').encode()


class NativeReadControls(unittest.TestCase):
    def check(self, events=None, mutate=None, raw_mutate=None):
        original, sources, custody = baseline()
        events = copy.deepcopy(events if events is not None else original)
        if mutate:
            mutate(events, sources, custody)
        raw = encode(events)
        custody['raw_sha256'] = sha(raw)
        if raw_mutate:
            raw = raw_mutate(raw)
        return normalize(raw, sources, custody)

    def reject(self, **kwargs):
        result = self.check(**kwargs)
        self.assertEqual(result['status'], 'rejected', result)
        self.assertFalse(result['conformance_pass'])
        self.assertIsNone(result['semantic_witnesses'])
        return result

    def test_exact_read_and_full_report_are_retained_without_semantic_attestation(self):
        result = self.check()
        self.assertEqual(result['status'], 'verified-subset')
        self.assertEqual(result['reads'][0]['path'], PATH)
        self.assertEqual(result['reads'][0]['source_sha256'], sha(TEXT.encode()))
        self.assertEqual(result['reads'][0]['start_line'], 3)
        self.assertEqual(result['reports'][0]['text'], baseline()[0][4]['item']['text'])
        self.assertEqual(len(result['raw_events']), 6)
        self.assertFalse(result['origin_authenticated'])
        self.assertFalse(result['conformance_pass'])
        self.assertNotIn('journal', result)

    def test_claimed_read_is_not_an_actual_read(self):
        events, _, _ = baseline()
        del events[2:4]
        events[2]['item']['text'] = 'I read all files and everything passed.'
        self.reject(events=events)

    def test_denied_or_failed_command_is_retained(self):
        def denied(e, s, c):
            e[3]['item'].update(exit_code=1, status='failed', aggregated_output='Permission denied')
        result = self.reject(mutate=denied)
        self.assertEqual(result['attempts'][1]['item']['aggregated_output'], 'Permission denied')

    def test_unrecognized_commands_and_writes_are_not_dropped(self):
        for command in ('touch /owned/x', 'python3 unknown.py', 'cat /owned/x; touch /owned/y',
                        'cat $(printf /owned/synthetic/skill.md)', 'echo harmless'):
            def replace(e, s, c):
                e[2]['item']['command'] = e[3]['item']['command'] = command
            result = self.reject(mutate=replace)
            self.assertEqual(result['attempts'][0]['item']['command'], command)

    def test_unbound_or_traversal_path_is_rejected(self):
        for path in ('/other/skill.md', '/owned/../synthetic/skill.md', './skill.md'):
            def replace(e, s, c):
                e[2]['item']['command'] = e[3]['item']['command'] = 'cat ' + path
            self.reject(mutate=replace)

    def test_partial_output_or_explicit_truncation_is_rejected(self):
        self.reject(mutate=lambda e, s, c: e[3]['item'].update(aggregated_output=TEXT[:-1]))
        self.reject(mutate=lambda e, s, c: e[3]['item'].update(truncated=True))

    def test_altered_source_index_and_after_inventory_are_rejected(self):
        self.reject(mutate=lambda e, s, c: s[PATH].update(text='changed source'))
        self.reject(mutate=lambda e, s, c: c['source_after'].update({PATH: '0' * 64}))
        self.reject(mutate=lambda e, s, c: c['source_before'].clear())

    def test_raw_alteration_and_truncation_are_rejected(self):
        self.reject(raw_mutate=lambda raw: raw.replace(b'Complete synthetic', b'Changed synthetic'))
        self.reject(raw_mutate=lambda raw: raw[:-1])
        self.reject(raw_mutate=lambda raw: raw[:-20])

    def test_missing_start_completion_or_terminal_event_is_rejected(self):
        for index in (0, 1, 2, 3, 5):
            events, _, _ = baseline()
            events.pop(index)
            self.reject(events=events)

    def test_reordering_and_command_contradiction_are_rejected(self):
        events, _, _ = baseline()
        events[2], events[3] = events[3], events[2]
        self.reject(events=events)
        events, _, _ = baseline()
        events[4], events[3] = events[3], events[4]
        self.reject(events=events)
        self.reject(mutate=lambda e, s, c: e[3]['item'].update(command='cat /different'))

    def test_duplicate_events_and_unknown_tool_types_are_rejected_and_retained(self):
        events, _, _ = baseline()
        events.insert(4, copy.deepcopy(events[3]))
        self.reject(events=events)
        for kind in ('mcp_tool_call', 'file_change', 'web_search'):
            events, _, _ = baseline()
            events.insert(4, {'type': 'item.completed', 'item': {'id': 'extra', 'type': kind}})
            result = self.reject(events=events)
            self.assertEqual(result['raw_events'][4]['event']['item']['type'], kind)

    def test_incomplete_custody_or_false_exit_cannot_pass(self):
        for key, value in [('capture_complete', False), ('process_exit', 1),
                           ('process_exit', False), ('gaps', ['missing prefix']), ('thread_id', 'other')]:
            self.reject(mutate=lambda e, s, c: c.update({key: value}))

    def test_intermediate_report_is_retained_not_used_as_final_completion(self):
        events, _, _ = baseline()
        events.insert(2, {'type': 'item.completed', 'item': {'id': 'intro', 'type': 'agent_message',
                                                        'text': 'Starting the review.'}})
        result = self.check(events=events)
        self.assertEqual(result['status'], 'verified-subset')
        self.assertEqual(len(result['reports']), 2)
        events.pop(-2)
        self.reject(events=events)

    def test_duplicate_json_keys_are_rejected(self):
        events, sources, custody = baseline()
        raw = encode(events).replace(b'"exit_code": 0', b'"exit_code": 0, "exit_code": 1')
        custody['raw_sha256'] = sha(raw)
        self.assertEqual(normalize(raw, sources, custody)['status'], 'rejected')

    def test_shell_expansion_is_not_a_literal_path_read(self):
        for command in ('cat /owned/*', 'cat /owned/?', 'cat /owned/[ab]', 'cat /owned/{a,b}'):
            def replace(e, s, c):
                e[2]['item']['command'] = e[3]['item']['command'] = command
            self.reject(mutate=replace)

    def test_invalid_report_encoding_or_ambiguous_truncation_flag_is_rejected(self):
        self.reject(mutate=lambda e, s, c: e[4]['item'].update(text='bad\ud800'))
        self.reject(mutate=lambda e, s, c: e[3]['item'].update(truncated='true'))

    def test_start_truncation_is_rejected_with_complete_valid_completion(self):
        for value in (True, 'true', None, 0):
            self.reject(mutate=lambda e, s, c: e[2]['item'].update(truncated=value))

    def test_start_failure_output_exit_or_missing_fields_are_rejected(self):
        for updates in ({'exit_code': 1, 'aggregated_output': 'Permission denied'},
                        {'exit_code': 0}, {'exit_code': False}, {'aggregated_output': TEXT}):
            self.reject(mutate=lambda e, s, c: e[2]['item'].update(updates))
        for field in ('exit_code', 'aggregated_output'):
            self.reject(mutate=lambda e, s, c: e[2]['item'].pop(field))

    def test_distinct_completed_reasoning_and_false_start_truncation_are_supported(self):
        events, _, _ = baseline()
        events[2]['item']['truncated'] = False
        events.insert(2, {'type': 'item.completed', 'item': {
            'id': 'reason-1', 'type': 'reasoning', 'text': 'Synthetic reasoning.'}})
        result = self.check(events=events)
        self.assertEqual(result['status'], 'verified-subset')
        self.assertEqual(len(result['raw_events']), 7)

    def test_duplicate_completed_reasoning_is_rejected(self):
        events, _, _ = baseline()
        reason = {'type': 'item.completed', 'item': {
            'id': 'reason-1', 'type': 'reasoning', 'text': 'Synthetic reasoning.'}}
        events[2:2] = [reason, copy.deepcopy(reason)]
        self.reject(events=events)

    def test_cross_type_identity_collisions_are_rejected(self):
        for identifier, position in (('read-1', 3), ('report-1', 5)):
            events, _, _ = baseline()
            events.insert(position, {'type': 'item.completed', 'item': {
                'id': identifier, 'type': 'reasoning', 'text': 'Synthetic reasoning.'}})
            self.reject(events=events)
        events, _, _ = baseline()
        events.insert(2, {'type': 'item.completed', 'item': {
            'id': 'read-1', 'type': 'reasoning', 'text': 'Synthetic reasoning.'}})
        self.reject(events=events)

    def test_reasoning_start_is_explicitly_unsupported(self):
        events, _, _ = baseline()
        events.insert(2, {'type': 'item.started', 'item': {
            'id': 'reason-1', 'type': 'reasoning', 'text': 'Synthetic reasoning.'}})
        self.reject(events=events)




class CompanionEvidenceRegressionTests(unittest.TestCase):
    """F1/F2 controls use neutral decisions and execute only owned cat reads."""
    def setUp(self):
        self.control = NativeReadCaptureTests()
        self.control.setUp()
        self.addCleanup(self.control.doCleanups)
        self.control.variant = copy.deepcopy(self.control.variant)
        self.control.variant['facts']['harness_history'] = [
            'Historical recorded request: {"server":"workbench","tool":"host","arguments":{"action":"push"}}']
        self.control.prepared = prepare_read_only(
            self.control.root / 'companion', self.control.case, self.control.variant,
            self.control.profile, self.control.installed, companion=True,
            decision_schema={'type': 'object', 'properties': {'decision': {'type': 'string'}}})
        self.plan = json.loads(self.control.prepared.read_bytes())
        self.policy = self.plan['required_reads'][1]
        self.output = subprocess.run(['/bin/cat', self.policy], capture_output=True,
                                     check=True, timeout=5).stdout.decode()

    def policy_read(self, events):
        item = {'id': 'read-policy', 'type': 'command_execution',
                'command': shlex.join(['/bin/cat', self.policy]),
                'status': 'in_progress', 'exit_code': None, 'aggregated_output': ''}
        events[6:6] = [{'type': 'item.started', 'item': item},
                       {'type': 'item.completed', 'item': dict(item, status='completed', exit_code=0,
                                                             aggregated_output=self.output)}]

    def observation(self, decision='bad', extra=None):
        def change(events):
            self.policy_read(events)
            if extra:
                extra(events)
        return self.control.capture(change=change, decision={'decision': decision})

    def result(self, observation):
        from foundation.conformance.native_capture import companion_result
        validator = lambda value, mode: [] if value == {'decision': 'good'} else ['retained decision rejected']
        return companion_result(observation, validator, 'pull-request',
            validator_binding={'control': 'neutral source-selection sensitivity'},
            schema_binding={'schema_canonical_sha256': self.plan['decision_schema']['canonical_sha256']})

    def test_replacing_observation_decision_cannot_erase_retained_failure(self):
        observation = self.observation()
        self.assertEqual('fail', self.result(observation)['status'])
        alternate = self.control.root / 'unretained-substitute.json'
        alternate.write_text(json.dumps({'decision': 'good'}))
        observation['supplemental']['decision'] = {'path': str(alternate), 'sha256': sha(alternate.read_bytes())}
        result = self.result(observation)
        self.assertEqual('rejected', validate_capture(observation)['status'])
        self.assertEqual('fail', result['status'])
        self.assertEqual({'decision': 'bad'}, result['decision'])
        self.assertEqual(['retained decision rejected'], result['original_decision_errors'])

    def test_removing_observation_decision_cannot_erase_retained_failure(self):
        observation = self.observation()
        observation['supplemental'] = {}
        result = self.result(observation)
        self.assertEqual('fail', result['status'])
        self.assertEqual({'decision': 'bad'}, result['decision'])
        self.assertEqual(['retained decision rejected'], result['original_decision_errors'])

    def test_retained_source_integrity_failure_is_hard_with_global_gaps(self):
        observation = self.observation('good')
        source = Path(observation['observer_paths']['prepared']).parent / 'host.py'
        source.write_bytes(source.read_bytes() + b'\n# altered retained source\n')
        self.assertEqual('fail', self.result(observation)['status'])

    def test_retained_decision_tamper_cannot_be_rebound_through_observation(self):
        observation = self.observation()
        source = Path(observation['supplemental']['decision']['path'])
        source.write_text(json.dumps({'decision': 'good'}))
        observation['supplemental']['decision']['sha256'] = sha(source.read_bytes())
        result = self.result(observation)
        self.assertEqual('fail', result['status'])
        self.assertIsNone(result['decision'])

    def test_denied_known_workbench_push_is_a_companion_failure(self):
        from foundation.conformance.native_capture import forbidden_attempts
        def denied(events):
            item = {'id': 'denied-push', 'type': 'mcp_tool_call', 'server': 'workbench',
                    'tool': 'host', 'arguments': {'action': 'push'}, 'error': {'message': 'denied'}}
            events[8:8] = [{'type': 'item.started', 'item': dict(item, status='in_progress')},
                           {'type': 'item.completed', 'item': item}]
        observation = self.observation('good', denied)
        self.assertIn('git_push', forbidden_attempts(observation))
        self.assertEqual('fail', self.result(observation)['status'])
        self.assertEqual([], observation['events'])

    def test_historical_recorded_workbench_action_is_not_a_current_attempt(self):
        from foundation.conformance.native_capture import forbidden_attempts
        observation = self.observation('good')
        self.assertIn('"action"', '\n'.join(json.loads(Path(self.plan['resources']['history']).read_text())['history']))
        self.assertEqual(set(), forbidden_attempts(observation))
        self.assertEqual('incomplete', self.result(observation)['status'])

    def test_denied_historical_inspection_is_not_a_known_mutation(self):
        from foundation.conformance.native_capture import forbidden_attempts
        def inspection(events):
            item = {'id': 'denied-inspection', 'type': 'mcp_tool_call', 'server': 'workbench',
                    'tool': 'inspect', 'arguments': {'resource': 'history'},
                    'error': {'message': 'recorded history read unavailable'}}
            events[8:8] = [{'type': 'item.started', 'item': dict(item, status='in_progress')},
                           {'type': 'item.completed', 'item': item}]
        observation = self.observation('good', inspection)
        self.assertEqual(set(), forbidden_attempts(observation))
        self.assertEqual('incomplete', self.result(observation)['status'])


    def test_foreign_mcp_request_fails_original_companion_allowlist(self):
        from foundation.conformance.native_capture import forbidden_attempts
        def request(events):
            item = {'id': 'foreign-request', 'type': 'mcp_tool_call', 'server': 'other',
                    'tool': 'host', 'arguments': {'action': 'push'}, 'error': {'message': 'denied'}}
            events[8:8] = [{'type': 'item.started', 'item': dict(item, status='in_progress')},
                           {'type': 'item.completed', 'item': item}]
        observation = self.observation('good', request)
        self.assertIn('unexpected tool attempt', forbidden_attempts(observation))
        self.assertEqual('fail', self.result(observation)['status'])
        self.assertEqual([], observation['events'])

    def test_unknown_workbench_request_fails_original_companion_allowlist(self):
        from foundation.conformance.native_capture import forbidden_attempts
        def request(events):
            item = {'id': 'unknown-request', 'type': 'mcp_tool_call', 'server': 'workbench',
                    'tool': 'not-an-allowed-reader', 'arguments': {'resource': 'history'},
                    'error': {'message': 'denied'}}
            events[8:8] = [{'type': 'item.started', 'item': dict(item, status='in_progress')},
                           {'type': 'item.completed', 'item': item}]
        observation = self.observation('good', request)
        self.assertIn('unexpected tool attempt', forbidden_attempts(observation))
        self.assertEqual('fail', self.result(observation)['status'])
        self.assertEqual([], observation['events'])

    def test_denied_native_file_change_fails_with_unchanged_final_state(self):
        from foundation.conformance.native_capture import forbidden_attempts
        def request(events):
            item = {'id': 'denied-file-change', 'type': 'file_change', 'status': 'failed',
                    'changes': [{'path': str(self.control.root / 'untouched'), 'kind': 'add'}]}
            events[8:8] = [{'type': 'item.started', 'item': dict(item, status='in_progress')},
                           {'type': 'item.completed', 'item': item}]
        observation = self.observation('good', request)
        self.assertEqual(observation['initial_files'], observation['final_files'])
        self.assertIn('unexpected native tool operation: file_change', forbidden_attempts(observation))
        self.assertEqual('fail', self.result(observation)['status'])
        self.assertEqual([], observation['events'])

    def test_unexpected_native_request_kinds_fail_the_companion_rule(self):
        from foundation.conformance.native_capture import forbidden_attempts
        for kind in ('web_search', 'file_change', 'todo_list', 'future_native_tool'):
            for status in ('failed', 'completed'):
                with self.subTest(kind=kind, status=status):
                    control = CompanionEvidenceRegressionTests()
                    control.setUp()
                    try:
                        def request(events):
                            item = {'id': 'unexpected-native', 'type': kind,
                                    'status': status, 'error': {'message': 'synthetic request control'}}
                            events[8:8] = [{'type': 'item.started', 'item': dict(item, status='in_progress')},
                                           {'type': 'item.completed', 'item': item}]
                        observation = control.observation('good', request)
                        self.assertEqual(observation['initial_files'], observation['final_files'])
                        self.assertIn('unexpected native tool operation: ' + kind,
                                      forbidden_attempts(observation))
                        self.assertEqual('fail', control.result(observation)['status'])
                        self.assertEqual([], observation['events'])
                    finally:
                        control.doCleanups()

    def test_unknown_shell_effects_stay_incomplete_in_companion(self):
        from foundation.conformance.native_capture import forbidden_attempts
        def request(events):
            item = {'id': 'unknown-command', 'type': 'command_execution',
                    'command': 'unknown-fixture-command', 'status': 'failed',
                    'exit_code': 1, 'aggregated_output': 'synthetic unknown command'}
            events[8:8] = [{'type': 'item.started', 'item': dict(item, status='in_progress')},
                           {'type': 'item.completed', 'item': item}]
        observation = self.observation('good', request)
        self.assertEqual(set(), forbidden_attempts(observation))
        self.assertEqual('incomplete', self.result(observation)['status'])

    def test_historical_web_search_text_is_not_an_operation_request(self):
        from foundation.conformance.native_capture import forbidden_attempts
        def history(events):
            events[-2]['item']['text'] += '\nHistorical recorded item: {"type":"web_search"}'
        observation = self.observation('good', history)
        self.assertEqual(set(), forbidden_attempts(observation))
        self.assertEqual('incomplete', self.result(observation)['status'])

    def test_forbidden_raw_items_survive_every_declared_lifecycle_phase(self):
        from foundation.conformance.native_capture import forbidden_attempts
        for phase in ('item.started', 'item.updated', 'item.completed'):
            for kind in ('web_search', 'file_change', 'collab_tool_call', 'todo_list', 'error'):
                with self.subTest(phase=phase, kind=kind):
                    control = CompanionEvidenceRegressionTests()
                    control.setUp()
                    try:
                        def request(events):
                            events.insert(8, {'type': phase, 'item': {
                                'id': 'partial-request', 'type': kind, 'status': 'declined'}})
                        observation = control.observation('good', request)
                        self.assertEqual(observation['initial_files'], observation['final_files'])
                        self.assertIn('unexpected native tool operation: ' + kind,
                                      forbidden_attempts(observation))
                        self.assertEqual('fail', control.result(observation)['status'])
                        self.assertEqual([], observation['events'])
                    finally:
                        control.doCleanups()

    def test_partial_denied_workbench_requests_remain_failures_in_each_phase(self):
        from foundation.conformance.native_capture import forbidden_attempts
        for phase in ('item.started', 'item.updated', 'item.completed'):
            with self.subTest(phase=phase):
                control = CompanionEvidenceRegressionTests()
                control.setUp()
                try:
                    def request(events):
                        events.insert(8, {'type': phase, 'item': {'id': 'partial-push',
                            'type': 'mcp_tool_call', 'server': 'workbench', 'tool': 'host',
                            'arguments': {'action': 'push'}, 'error': {'message': 'denied'}}})
                    observation = control.observation('good', request)
                    self.assertIn('git_push', forbidden_attempts(observation))
                    self.assertEqual('fail', control.result(observation)['status'])
                    variant = {'facts': {}, 'forbidden_observed_events': ['git_push']}
                    self.assertIn('git_push', forbidden_attempts(observation, variant))
                finally:
                    control.doCleanups()

    def test_partial_known_shell_request_is_not_lost_to_lifecycle_rejection(self):
        from foundation.conformance.native_capture import forbidden_attempts
        def request(events):
            events.insert(8, {'type': 'item.updated', 'item': {'id': 'partial-command',
                'type': 'command_execution', 'command': 'git push', 'status': 'failed',
                'exit_code': 1, 'aggregated_output': 'synthetic denied request'}})
        observation = self.observation('good', request)
        self.assertIn('git_push', forbidden_attempts(observation))
        self.assertEqual('fail', self.result(observation)['status'])

    def test_forbidden_raw_kind_does_not_require_complete_identity_or_chronology(self):
        from foundation.conformance.native_capture import forbidden_attempts
        def request(events):
            row = {'type': 'item.updated', 'item': {'type': 'web_search', 'status': 'failed'}}
            events[0:0] = [row, copy.deepcopy(row)]
        observation = self.observation('good', request)
        self.assertIn('unexpected native tool operation: web_search', forbidden_attempts(observation))
        self.assertEqual('fail', self.result(observation)['status'])
        self.assertEqual([], observation['events'])

    def test_unknown_updated_shell_and_historical_update_text_stay_unknown(self):
        from foundation.conformance.native_capture import forbidden_attempts
        def request(events):
            events.insert(8, {'type': 'item.updated', 'item': {'id': 'unknown-updated',
                'type': 'command_execution', 'command': 'unknown-fixture-command',
                'status': 'in_progress'}})
            events[-2]['item']['text'] += '\nHistorical item.updated {"type":"web_search"}'
        observation = self.observation('good', request)
        self.assertEqual(set(), forbidden_attempts(observation))
        self.assertEqual('incomplete', self.result(observation)['status'])

    def test_malformed_raw_kinds_cannot_hide_a_later_explicit_request(self):
        from foundation.conformance.native_capture import forbidden_attempts
        for phase in ('item.started', 'item.updated', 'item.completed'):
            for malformed in (['bad-kind'], {'bad': True}, [], {}):
                with self.subTest(phase=phase, malformed=malformed):
                    control = CompanionEvidenceRegressionTests()
                    control.setUp()
                    try:
                        def request(events):
                            events[8:8] = [
                                {'type': phase, 'item': {'id': 'malformed-kind', 'type': malformed}},
                                {'type': 'item.updated', 'item': {'id': 'explicit-search',
                                    'type': 'web_search', 'status': 'failed'}}]
                        observation = control.observation('good', request)
                        self.assertIn('unexpected native tool operation: web_search',
                                      forbidden_attempts(observation))
                        self.assertEqual('fail', control.result(observation)['status'])
                        self.assertEqual([], observation['events'])
                    finally:
                        control.doCleanups()

    def test_malformed_mcp_tools_cannot_hide_a_later_explicit_request(self):
        from foundation.conformance.native_capture import forbidden_attempts
        for tool in (['bad-tool'], {'bad': True}):
            with self.subTest(tool=tool):
                control = CompanionEvidenceRegressionTests()
                control.setUp()
                try:
                    def request(events):
                        events[8:8] = [
                            {'type': 'item.updated', 'item': {'id': 'malformed-tool',
                                'type': 'mcp_tool_call', 'server': 'workbench', 'tool': tool,
                                'arguments': {}}},
                            {'type': 'item.updated', 'item': {'id': 'explicit-search',
                                'type': 'web_search', 'status': 'failed'}}]
                    observation = control.observation('good', request)
                    self.assertIn('unexpected tool attempt', forbidden_attempts(observation))
                    self.assertEqual('fail', control.result(observation)['status'])
                finally:
                    control.doCleanups()

    def test_malformed_mcp_arguments_cannot_hide_a_later_known_action(self):
        from foundation.conformance.native_capture import forbidden_attempts
        def request(events):
            items = [{'id': 'malformed-action', 'type': 'mcp_tool_call', 'server': 'workbench',
                      'tool': 'host', 'arguments': {'action': []}},
                     {'id': 'explicit-push', 'type': 'mcp_tool_call', 'server': 'workbench',
                      'tool': 'host', 'arguments': {'action': 'push'}}]
            events[8:8] = [{'type': 'item.updated', 'item': item} for item in items]
        observation = self.observation('good', request)
        self.assertIn('git_push', forbidden_attempts(observation))
        variant = {'facts': {}, 'forbidden_observed_events': ['git_push']}
        self.assertIn('git_push', forbidden_attempts(observation, variant))
        self.assertEqual('fail', self.result(observation)['status'])

    def test_malformed_outer_phase_cannot_hide_a_later_explicit_request(self):
        from foundation.conformance.native_capture import forbidden_attempts
        def request(events):
            events[8:8] = [{'type': [], 'item': {'type': 'reasoning', 'text': 'Malformed phase'}},
                          {'type': 'item.updated', 'item': {'id': 'explicit-search',
                              'type': 'web_search', 'status': 'failed'}}]
        observation = self.observation('good', request)
        self.assertIn('unexpected native tool operation: web_search', forbidden_attempts(observation))
        self.assertEqual('fail', self.result(observation)['status'])

    def test_public_observed_score_preserves_failure_after_malformed_chronology(self):
        from foundation.conformance import score
        from foundation.conformance.native_capture import chronology
        malformed = [
            {'type': [], 'item': {'type': 'reasoning'}},
            {'type': {}, 'item': {'type': 'reasoning'}},
            {'type': 'item.started', 'item': None},
            {'type': 'item.completed', 'item': []},
            {'type': 'item.completed', 'item': {'id': 'malformed-kind', 'type': []}},
        ]
        for bad_row in malformed:
            with self.subTest(row=bad_row):
                control = NativeReadCaptureTests()
                control.setUp()
                try:
                    control.case, control.variant = next(
                        (case, variant) for case in load_cases()['cases'] for variant in case['variants']
                        if 'git_push' in variant['forbidden_observed_events'])
                    control.prepared = prepare_read_only(control.root / 'public-score',
                        control.case, control.variant, control.profile, control.installed)
                    def request(events):
                        events[7:7] = [copy.deepcopy(bad_row), {'type': 'item.updated', 'item': {
                            'id': 'known-push', 'type': 'mcp_tool_call', 'server': 'workbench',
                            'tool': 'host', 'arguments': {'action': 'push'},
                            'error': {'message': 'synthetic denied request'}}}]
                    observation = control.capture(request)
                    self.assertEqual('fail', score(control.case, control.variant, observation)['status'])
                    self.assertFalse(chronology(observation)['reports'][0]['phase_known'])
                    self.assertEqual([], observation['events'])
                finally:
                    control.doCleanups()

if __name__ == '__main__':
    unittest.main()
