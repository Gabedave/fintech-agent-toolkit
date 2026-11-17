"""Offline final-response transport controls; no model or scorer-oracle changes."""
import contextlib
import io
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import evaluate_behavior as behavior
import evaluate_review_quality as review
import native_evidence as evidence


class NativeTransportTests(unittest.TestCase):
    def test_native_argv_and_effective_prompt_use_final_only_schema(self):
        def check(command, prompt, schema, prefix):
            self.assertNotIn('--output-schema', command)
            self.assertTrue(prompt.startswith(prefix))
            self.assertIn(schema.read_text(), prompt[len(prefix):])
            self.assertIn('plaintext', prompt[len(prefix):])
            Path(command[command.index('--output-last-message') + 1]).write_text('{}')
        with tempfile.TemporaryDirectory() as temp:
            scenario = {'id': 'transport-only', 'prompt': 'Synthetic request'}
            for kind in ('routing', 'publication') if hasattr(behavior, 'PUBLICATION_SCHEMA') else ('routing',):
                scenario['kind'] = kind
                schema = behavior.PUBLICATION_SCHEMA if kind == 'publication' else behavior.SCHEMA
                builder = behavior.build_publication_prompt if kind == 'publication' else behavior.build_prompt
                def behavior_run(command, prompt, timeout, **kwargs):
                    check(command, prompt, schema, builder(scenario['prompt']))
                    return 0, '', ''
                with mock.patch.object(behavior, 'run_command', side_effect=behavior_run):
                    self.assertEqual({}, behavior.run_scenario(Path(temp), scenario, None, 30))
            def review_run(command, **kwargs):
                snapshot = review.snapshot_identity(Path(kwargs['cwd']))
                check(command, kwargs['input_text'], review.SCHEMA, review.build_prompt(snapshot, 1))
                return ''
            with mock.patch.object(review, 'run_command', side_effect=review_run):
                self.assertEqual({}, review.run_review(review.load_suite()[0], 'broken', 30)[0])

    def test_final_json_rejects_duplicate_decoded_keys_and_nonfinite_constants(self):
        import native_transport as transport
        self.assertEqual({'nested': [{'key': 1}]}, transport.parse_final_result('{"nested":[{"key":1}]}'))
        for raw in (r'{"key":1,"\u006bey":2}', '{"nested":[{"key":1,"key":2}]}',
                    '{"value":NaN}', '{"value":Infinity}', '{"value":-Infinity}'):
            with self.subTest(raw=raw), self.assertRaises(transport.InvalidFinalResult):
                transport.parse_final_result(raw)

    def test_strict_schema_nested_extra_types_enum_and_unsupported_vocabulary(self):
        import native_transport as transport
        schema = {'type': 'object', 'required': ['items', 'enabled'], 'additionalProperties': False,
                  'properties': {'enabled': {'type': 'boolean'}, 'items': {'type': 'array', 'items': {
                      'type': 'object', 'required': ['line', 'state'], 'additionalProperties': False,
                      'properties': {'line': {'type': 'integer'}, 'state': {'type': 'string', 'enum': ['ready', 'blocked']}}}}}}
        valid = {'enabled': True, 'items': [{'line': 4, 'state': 'ready'}]}
        self.assertEqual([], transport.result_errors(valid, schema))
        for value, path in [({'items': []}, '$.enabled'),
                            ({**valid, 'extra': 1}, '$.extra'),
                            ({**valid, 'enabled': 1}, '$.enabled'),
                            ({**valid, 'items': {}}, '$.items'),
                            ({**valid, 'items': [{'line': True, 'state': 'ready'}]}, '$.items[0].line'),
                            ({**valid, 'items': [{'line': 1.5, 'state': 'ready'}]}, '$.items[0].line'),
                            ({**valid, 'items': [{'line': 1, 'state': 'done'}]}, '$.items[0].state'),
                            ({**valid, 'items': [{'line': 1, 'state': 'ready', 'extra': 2}]}, '$.items[0].extra')]:
            with self.subTest(value=value):
                self.assertTrue(any(path in e for e in transport.result_errors(value, schema)))
        for invalid in ({'type': 'string', 'minLength': 1}, {'type': 'nonsense'},
                        {'type': 'object', 'additionalProperties': {}}, {'type': 'array', 'items': []}):
            with self.assertRaises(ValueError):
                transport.result_errors({}, invalid)
        self.assertEqual([], transport.result_errors(1.0, {'type': 'integer', 'enum': [1]}))
        self.assertEqual([], transport.result_errors([1.0], {'type': 'array', 'enum': [[1]]}))
        for invalid_number in (True, float('nan'), float('inf'), -float('inf')):
            self.assertTrue(transport.result_errors(invalid_number, {'type': 'number'}))
        self.assertTrue(transport.result_errors(True, {'type': 'integer', 'enum': [1]}))
        self.assertTrue(transport.result_errors(1, {'type': 'boolean', 'enum': [True]}))

    def test_frozen_schemas_and_new_helper_are_retained_without_change(self):
        import native_transport as transport
        from test_native_review_inputs import NativeReviewInputsTests
        pinned = {'tests/behavior-result.schema.json': 'f7f998eec74ff96ba0264192ab3de407d556cd78f599fb433e0000b12ccb266b', 'tests/review-quality/result.schema.json': '85389d377f4721468703e7fd8d4a176a8f92da335c284c010a997d55b07c3b87'}
        for name, expected in pinned.items():
            raw = (ROOT / name).read_bytes()
            self.assertEqual(expected, hashlib.sha256(raw).hexdigest())
            transport.validate_schema(json.loads(raw))
        with tempfile.TemporaryDirectory() as temp:
            _, release, _, handle, _ = NativeReviewInputsTests().setup_context(Path(temp))
            row = next(r for r in handle.release['source_index']
                       if r['original_path'] == str(ROOT / 'scripts/native_transport.py'))
            self.assertEqual('harness-source', row['role'])
            self.assertEqual((ROOT / 'scripts/native_transport.py').read_bytes(),
                             (release / 'review-inputs' / row['path']).read_bytes())

    def test_valid_schema_object_reaches_unchanged_semantic_scorer(self):
        import native_transport as transport
        scenario = next(s for s in json.loads(behavior.SCENARIOS.read_text())['scenarios']
                        if s['id'] == 'historical-diagnosis')
        result = {'playbook': scenario['expected_playbook'],
                  'additional_playbooks': scenario['expected_additional_playbooks'],
                  'skills': scenario['expected_skills'], 'repository_verifiers': scenario['expected_verifiers'],
                  'authorized_actions': scenario['expected_actions'],
                  'withheld_actions': scenario['expected_withheld_actions'],
                  'decision_records': {**scenario['expected_decision_records'], 'reason': 'Read-only historical investigation.'},
                  'pull_request_lifecycle': scenario['expected_pull_request_lifecycle'],
                  'implementation_readiness': scenario['expected_implementation_readiness'],
                  'external_actions_performed': [],
                  'skipped_steps': [{'step': 'edit', 'reason': 'Read-only request.'}]}
        if 'ci_progress_updates' in json.loads(behavior.SCHEMA.read_text())['properties']:
            result['ci_progress_updates'] = []
        self.assertEqual([], transport.result_errors(result, json.loads(behavior.SCHEMA.read_text())))
        with mock.patch.object(behavior, 'run_scenario', return_value=result), \
                mock.patch.object(behavior, 'validate_result', wraps=behavior.validate_result) as scorer, \
                contextlib.redirect_stdout(io.StringIO()):
            failures, _, replacements, usable = behavior.evaluate_scenarios(ROOT, [scenario], None, 30)
        self.assertEqual([], failures)
        self.assertEqual((0, 1), (replacements, usable))
        scorer.assert_called_once_with(scenario, result)
        from test_review_quality import ReviewQualityScoring
        control = ReviewQualityScoring(); control.setUp()
        self.assertEqual([], transport.result_errors(control.result, json.loads(review.SCHEMA.read_text())))
        self.assertEqual([], control.score())

    @contextlib.contextmanager
    def fake_cli(self, outcome):
        original = subprocess.Popen
        calls = []
        raw = ('{"type":"thread.started","thread_id":"transport-control"}\n'
               '{"type":"item.completed","item":{"type":"agent_message","text":"Loading the installed skill now."}}\n'
               '{"type":"item.completed","item":{"type":"agent_message","text":"{}"}}\n'
               '{"type":"turn.completed"}\n').encode()
        def launch(command, **kwargs):
            if command[0] != 'codex':
                return original(command, **kwargs)
            self.assertNotIn('--output-schema', command)
            calls.append(command)
            output = command[command.index('--output-last-message') + 1]
            code = ('import sys; from pathlib import Path; sys.stdin.read(); '
                    f'Path({output!r}).write_text("{{}}"); sys.stdout.buffer.write({raw!r}); '
                    f'sys.exit({7 if outcome == "nonzero" else 0})')
            process = original([sys.executable, '-B', '-c', code], **kwargs)
            if outcome == 'timeout':
                communicate = process.communicate
                def timed_out(*args, **kw):
                    communicate(*args, **kw)
                    process.communicate = communicate
                    raise subprocess.TimeoutExpired(command, kw.get('timeout'))
                process.communicate = timed_out
            return process
        with mock.patch.object(subprocess, 'Popen', side_effect=launch):
            yield calls, raw

    def test_invalid_shape_is_known_failure_without_replacement_and_raw_commentary_survives(self):
        for kind in ('behavior', 'review'):
            for outcome in ('success', 'nonzero', 'timeout'):
                with self.subTest(kind=kind, outcome=outcome), tempfile.TemporaryDirectory() as temp:
                    directory = Path(temp)
                    run = evidence.create_run(directory / 'evidence', kind, {'synthetic': True})
                    with self.fake_cli(outcome) as (calls, raw), contextlib.redirect_stdout(io.StringIO()):
                        if kind == 'behavior':
                            scenario = json.loads(behavior.SCENARIOS.read_text())['scenarios'][0]
                            with mock.patch.object(behavior, 'validate_result') as scorer:
                                failures, _, replacements, usable = behavior.evaluate_scenarios(
                                    directory, [scenario], None, 30, evidence_dir=run)
                            self.assertTrue(failures)
                            self.assertEqual((0, 1), (replacements, usable))
                            scorer.assert_not_called()
                        else:
                            case = review.load_suite()[0]
                            with mock.patch.object(sys, 'argv', ['evaluate_review_quality.py', '--run', '--evidence-dir', str(run)]), \
                                    mock.patch.object(review, 'load_suite', return_value=[case]), \
                                    mock.patch.object(review, 'check_fixtures'), mock.patch.object(review, 'VARIANTS', ('broken',)), \
                                    mock.patch.object(review.evaluate_behavior, 'installed_plugin', return_value={
                                        'version': json.loads(behavior.MANIFEST.read_text())['version']}), \
                                    mock.patch.object(review, 'score_review') as scorer, contextlib.redirect_stderr(io.StringIO()), \
                                    self.assertRaises(SystemExit) as failure:
                                review.main()
                            self.assertEqual(1, failure.exception.code)
                            scorer.assert_not_called()
                    self.assertEqual(1, len(calls))
                    attempts = list(run.rglob('result-status.json'))
                    self.assertEqual(1, len(attempts))
                    attempt = attempts[0].parent
                    self.assertEqual(raw, (attempt / 'stdout.jsonl').read_bytes())
                    self.assertEqual(b'{}', (attempt / 'final-result.json').read_bytes())
                    self.assertTrue(json.loads(attempts[0].read_text())['usable'])


if __name__ == '__main__':
    unittest.main()
