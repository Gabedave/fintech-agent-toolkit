"""Explicit settings exercised through actual local pipe and native caller seams."""
import json
import contextlib
import io
import subprocess
from types import SimpleNamespace
from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest import mock

from foundation.conformance import runner
import test_preflight_guards as preflight
import test_native_review_inputs as native_tests
from test_native_review_inputs import behavior, review, evidence


class ExecutionSettingsTests(unittest.TestCase):
    def test_effort_binding_uses_config_assignments_not_path_or_prompt_text(self):
        import native_review_inputs as inputs
        base = ['codex', 'exec', '-C', '/tmp/model_reasoning_effort-regression',
                '-c', 'unrelated="model_reasoning_effort"']
        prompt = 'Explain model_reasoning_effort without changing it.'
        self.assertTrue(inputs.effort_command_matches(base + [prompt], None))
        self.assertTrue(inputs.effort_command_matches(
            base + ['-c', 'model_reasoning_effort="high"', prompt], 'high'))
        self.assertFalse(inputs.effort_command_matches(base + [prompt], 'high'))
        for override in [
            ['-c', 'model_reasoning_effort="low"'],
            ['--config', 'model_reasoning_effort="low"'],
            ['--config=model_reasoning_effort="low"'],
            ['-cmodel_reasoning_effort="low"'],
            ['-c=model_reasoning_effort="low"'],
        ]:
            with self.subTest(override=override):
                self.assertFalse(inputs.effort_command_matches(base + override + [prompt], None))
                self.assertFalse(inputs.effort_command_matches(base + override + [prompt], 'high'))
                self.assertFalse(inputs.effort_command_matches(
                    base + ['-c', 'model_reasoning_effort="high"'] + override + [prompt], 'high'))
        self.assertTrue(inputs.effort_command_matches(base + ['--', '--config=model_reasoning_effort="high"'], None))

    def test_effort_capture_is_allowlisted_and_requires_complete_unique_match(self):
        helper = preflight.PreflightGuards()
        good = helper.capture(stderr='model: actual\nreasoning effort: high\nprivate sentinel\n')
        self.assertIn('reasoning effort: high', good['diagnostics']['allowlisted_headers'])
        self.assertEqual('high', runner.require_effective_effort(good, 'high'))
        for text, code in [('reasoning effort: low\n', 0), ('', 0),
                           ('reasoning effort: high\nreasoning effort: low\n', 0),
                           ('reasoning effort: high\n', 7),
                           ('reasoning effort: private sentinel\n', 0)]:
            with self.subTest(text=text, code=code), self.assertRaises(RuntimeError):
                runner.require_effective_effort(helper.capture(stderr=text, exit_code=code), 'high')
        for key, value in [('timed_out', True), ('parse_errors', ['gap']), ('capture_gaps', ['gap'])]:
            broken = dict(good, **{key: value})
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                runner.require_effective_effort(broken, 'high')

    def test_native_callers_pin_effort_and_retain_usable_results_all_outcomes(self):
        helper = native_tests.NativeReviewInputsTests()
        for kind in ('behavior', 'review'):
            for outcome in ('succeeded', 'nonzero', 'timed_out'):
                with self.subTest(kind=kind, outcome=outcome), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    suite = evidence.create_run(root / 'evidence', 'synthetic', {})
                    with helper.local_cli(outcome):
                        if kind == 'behavior':
                            result = behavior.run_scenario(root, {'id': 'settings', 'prompt': 'route'},
                                'resolved', 5, evidence_dir=suite, reasoning_effort='high')
                        else:
                            result = review.run_review(review.load_suite()[0], 'broken', 5, model='resolved',
                                evidence_dir=suite, reasoning_effort='high')[0]
                    self.assertEqual('retained', result['playbook'])
                    invocation = json.loads(next(suite.glob('*/invocation.json')).read_text())
                    self.assertEqual(1, invocation['command'].count('model_reasoning_effort="high"'))
                    self.assertEqual('resolved', invocation['command'][invocation['command'].index('--model') + 1])

    def test_native_single_probe_preserves_alias_and_binds_effort(self):
        import native_review_inputs as inputs
        helper = native_tests.NativeReviewInputsTests()
        original = runner.stream_process
        with tempfile.TemporaryDirectory(prefix="model_reasoning_effort-") as tmp:
            root = Path(tmp)
            commands = []
            def local(command, env, cwd, output, timeout, prompt):
                commands.append(command)
                code = 'import sys; sys.stdin.read(); print("model: resolved",file=sys.stderr); print("reasoning effort: high",file=sys.stderr)'
                # Keep the actual collector; only substitute its local child.
                popen = __import__('subprocess').Popen
                with mock.patch('subprocess.Popen', side_effect=lambda _cmd, **kw: popen([sys.executable, '-B', '-c', code], **kw)):
                    return original(command, env, cwd, output, timeout, prompt)
            with mock.patch.object(runner, 'stream_process', side_effect=local):
                descriptor = inputs.capture_model_probe(root, {'PATH': os.environ['PATH']}, 'requested-alias', 5,
                                                        reasoning_effort='high')
            self.assertEqual(1, len(commands))
            self.assertIn('model_reasoning_effort="high"', commands[0])
            self.assertEqual('resolved', descriptor['effective_model'])
            self.assertEqual('high', descriptor['reasoning_effort'])
            self.assertEqual('resolved', inputs.validate_model_probe(root, descriptor, inputs.environment({'PATH': os.environ['PATH']})))
            descriptor['reasoning_effort'] = 'low'
            with self.assertRaises((RuntimeError, ValueError)):
                inputs.validate_model_probe(root, descriptor, inputs.environment({'PATH': os.environ['PATH']}))

    def test_observed_main_admits_one_complete_probe_before_tasks(self):
        from foundation.conformance import policy
        root = Path(__file__).resolve().parents[1]
        profile_path = root / 'profiles' / 'gabedave.json'
        profile = json.loads(profile_path.read_text())
        data = runner.load_cases()
        selected = data['cases'][0]['id'] + '/' + data['cases'][0]['variants'][0]['id']
        for effort, headers, code, tasks_expected in [
            ('high', ['reasoning effort: high'], 0, 2),
            (None, [], 0, 2), ('high', [], 0, 0),
            ('high', ['reasoning effort: low'], 0, 0),
            ('high', ['reasoning effort: high', 'reasoning effort: low'], 0, 0),
            ('high', ['reasoning effort: high'], 7, 0),
        ]:
            with self.subTest(effort=effort, headers=headers, code=code), tempfile.TemporaryDirectory() as tmp:
                tmp = Path(tmp)
                fixture = tmp / 'cases.json'
                fixture.write_bytes((root / 'foundation/conformance/cases.json').read_bytes())
                fixture.chmod(0o444)
                auth = tmp / 'auth.json'; auth.write_text('{}')
                argv = ['runner', '--run', '--fixtures', str(fixture), '--profile', str(profile_path),
                        '--candidate', str(root), '--profile-role', 'public-adopter', '--output', str(tmp/'out'),
                        '--auth-file', str(auth), '--model', 'alias', '--development', '--case', selected]
                if effort: argv += ['--reasoning-effort', effort]
                probes, tasks = [], []
                def stream(command, env, cwd, output, timeout, prompt=None):
                    result = {'exit': 0, 'timed_out': False, 'parse_errors': [], 'capture_gaps': [],
                              'diagnostics': {'allowlisted_headers': [], 'feature_conflicts': []}}
                    config = Path(env['CODEX_HOME']) / 'config.toml'
                    if command[1:4] == ['plugin','marketplace','add']:
                        with config.open('a') as f:
                            f.write('\nmarketplaces=' + policy._toml({profile['marketplace']: {'source_type':'local','source':str(root)}}) + '\n')
                    elif command[1:3] == ['plugin','add']:
                        with config.open('a') as f: f.write('\nplugins=' + policy._toml({command[3]: {'enabled': True}}) + '\n')
                    elif 'features' in command:
                        result['diagnostics']['tool_features'] = {'shell_tool': False, 'unified_exec': False}
                    elif command[1] == 'exec':
                        probes.append(command)
                        result['exit'] = code
                        result['diagnostics']['allowlisted_headers'] = ['model: resolved', *headers]
                    else: self.fail(command)
                    return result
                def task(case, variant, profile, installed, home, output, args, implicit=False):
                    tasks.append((args.model, args.reasoning_effort))
                    return {'case':case['id'], 'variant':variant['id'], 'status':'incomplete'}
                actual_run, actual_output = subprocess.run, subprocess.check_output
                def git_run(command, **kw):
                    if command[:3] == ['git', '-C', str(root)] and command[3] == 'status':
                        return subprocess.CompletedProcess(command, 0, '', '')
                    return actual_run(command, **kw)
                def git_output(command, **kw):
                    if command[:3] == ['git', '-C', str(root)] and command[3] == 'status': return ''
                    return actual_output(command, **kw)
                original_prepare = runner.prepare_policy
                with mock.patch.object(sys, 'argv', argv), mock.patch.object(runner, 'stream_process', stream), \
                        mock.patch.object(runner, 'prepare_policy', lambda home: original_prepare(home, tmp/'absent')) , \
                        mock.patch.object(runner, 'installed_plugin', lambda *_: root/'plugins'/profile['plugin_name']), \
                        mock.patch.object(runner, 'run_one', task), mock.patch.object(subprocess, 'run', git_run), \
                        mock.patch.object(subprocess, 'check_output', git_output), contextlib.redirect_stdout(io.StringIO()):
                    if tasks_expected: runner.main()
                    else:
                        with self.assertRaises(RuntimeError): runner.main()
                self.assertEqual(1, len(probes))
                self.assertEqual([('resolved', effort)] * tasks_expected, tasks)
                self.assertEqual(effort is not None, 'model_reasoning_effort="high"' in probes[0])

    def test_observed_task_pin_precedes_source_and_handshake_binding(self):
        root = Path(__file__).resolve().parents[1]
        profile_path = root / 'profiles' / 'gabedave.json'
        profile = json.loads(profile_path.read_text())
        case = runner.load_cases()['cases'][0]
        class StopBeforeModel(Exception): pass
        for effort in (None, 'high'):
            with self.subTest(effort=effort), tempfile.TemporaryDirectory() as tmp:
                tmp = Path(tmp)
                args = SimpleNamespace(candidate=root, profile=profile_path, profile_role='public-adopter',
                                       model='resolved', reasoning_effort=effort, timeout_seconds=180)
                captured = []
                def stop(command, env, cwd, output, timeout, prompt):
                    captured.append(command)
                    self.assertEqual(180, timeout)
                    launch = json.loads((output/'effect-launch.json').read_text())
                    self.assertEqual(command, launch['executed_command'])
                    from foundation.conformance.handshake_diagnostics import sha, canonical
                    config = json.loads((output/'host-config.json').read_text())
                    self.assertEqual(sha(canonical(command)), config['handshake_diagnostics']['command_sha256'])
                    raise StopBeforeModel()
                with mock.patch.object(runner, 'stream_process', stop), mock.patch.object(Path, 'home', return_value=tmp), \
                        self.assertRaises(StopBeforeModel):
                    runner.run_one(case, case['variants'][0], profile, root/'plugins'/profile['plugin_name'], tmp/'home', tmp/'output', args)
                self.assertEqual(1, len(captured))
                self.assertEqual(effort is not None, 'model_reasoning_effort="high"' in captured[0])

    def test_shared_effort_chain_survives_native_cleanup_and_process_outcomes(self):
        import native_review_inputs as inputs
        helper = native_tests.NativeReviewInputsTests()
        original_probe = inputs.capture_model_probe
        original_popen = subprocess.Popen
        for kind in ('behavior', 'review'):
            for outcome in ('succeeded', 'nonzero', 'timed_out'):
                with self.subTest(kind=kind, outcome=outcome), tempfile.TemporaryDirectory() as tmp:
                    tmp = Path(tmp)
                    probes = []
                    def launch(command, **kwargs):
                        if command[0] != 'codex': return original_popen(command, **kwargs)
                        probes.append(command)
                        code = 'import sys; sys.stdin.read(); print("model: synthetic-model",file=sys.stderr); print("reasoning effort: high",file=sys.stderr)'
                        return original_popen([sys.executable, '-B', '-c', code], **kwargs)
                    with mock.patch.object(subprocess, 'Popen', launch), \
                            mock.patch.object(inputs, 'capture_model_probe', side_effect=lambda root, env, model, timeout, **kw:
                                              original_probe(root, env, model, timeout, reasoning_effort='high')):
                        _, _, suite, handle, env = helper.setup_context(tmp, probe=True)
                    self.assertEqual(1, len(probes))
                    with mock.patch.dict(os.environ, env, clear=True), helper.local_cli(outcome, model_header=False) as calls:
                        if kind == 'behavior':
                            workspace = tmp/'fixture'; workspace.mkdir()
                            result, attempts, replacement, error = behavior.run_scenario_with_replacement(
                                workspace, {'id':'settings', 'prompt':'route'}, 'synthetic-model', 5,
                                evidence_dir=suite, review_inputs=handle, reasoning_effort='high', replacement_available=True)
                        else:
                            result, _, attempts, replacement, error = review.run_review_with_replacement(
                                review.load_suite()[0], 'broken', 5, model='synthetic-model',
                                evidence_dir=suite, review_inputs=handle, reasoning_effort='high', replacement_available=True)
                    self.assertEqual((1, False, None), (attempts, replacement, error))
                    self.assertEqual('retained', result['playbook'])
                    self.assertEqual(1, len(calls))
                    self.assertFalse(calls[0][0].exists())
                    status = json.loads(next(suite.glob(kind+'-*/review-inputs/capture-status.json')).read_text())
                    self.assertIsNone(status['observed_model'])
                    self.assertEqual('high', status['effort_binding']['reasoning_effort'])
                    self.assertEqual(handle.release['model_probe']['result']['sha256'], status['effort_binding']['probe_result_sha256'])
                    self.assertEqual([] if outcome=='succeeded' else ['native raw capture completeness unverified'], status['gaps'])

    def test_native_attempt_effort_pin_missing_wrong_or_duplicate_is_gap_not_retry(self):
        import native_review_inputs as inputs
        helper = native_tests.NativeReviewInputsTests()
        for settings, valid in [(['-c', 'model_reasoning_effort="high"'], True), ([], False),
                                (['-c', 'model_reasoning_effort="low"'], False),
                                (['-c', 'model_reasoning_effort="high"']*2, False),
                                (['--config=model_reasoning_effort="high"'], False)]:
            with self.subTest(settings=settings), tempfile.TemporaryDirectory() as tmp:
                tmp = Path(tmp)
                with helper.local_probe():
                    _, _, suite, handle, env = helper.setup_context(tmp, probe=True)
                # The actual probe binding verifier is tested separately; isolate
                # the attempt admission boundary with an explicit shared identity.
                handle.release['model_probe']['reasoning_effort'] = 'high'
                command = ['codex','exec','--json','--model','synthetic-model', *settings]
                attempt = suite/'attempt'; attempt.mkdir()
                workspace = tmp/'fixture'; workspace.mkdir()
                bound = handle.begin_attempt(attempt, workspace, workspace/'output.json', env, command=command)
                self.assertEqual(valid, bound.effort_binding is not None)
                self.assertEqual([] if valid else ['attempt reasoning effort is not explicitly pinned to observed shared probe'], bound.gaps)

    def test_release_forwards_effort_to_probe_and_both_children(self):
        import native_review_inputs as inputs
        import release_smoke as release
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp); auth = tmp/'auth.json'; auth.write_text('{}')
            sentinel = {'path':str(tmp/'context.json'), 'sha256':'a'*64, 'effective_model':'resolved'}
            commands = []
            def run(command, env, label, **kw):
                commands.append(command)
                return 'Review-quality pilot: synthetic\nReview-quality pilot passed synthetic'
            with mock.patch.object(sys, 'argv', ['release', '--repo', str(tmp/'backend'), '--auth-file', str(auth),
                    '--evidence-dir', str(tmp/'fresh'), '--review-quality', '--claim-review-inputs',
                    '--model', 'alias', '--reasoning-effort', 'high']), \
                    mock.patch.object(release, 'run', run), \
                    mock.patch.object(release, 'git_output', side_effect=lambda *a: '' if a[0]=='status' else 'synthetic'), \
                    mock.patch.object(release, 'backend_git_output', side_effect=lambda _r,*a: '' if a[0]=='status' else 'synthetic'), \
                    mock.patch.object(release, 'prepare_policy', return_value={}), mock.patch.object(release, 'verify_policy'), \
                    mock.patch.object(inputs, 'capture_release_context', return_value=sentinel) as capture, \
                    contextlib.redirect_stdout(io.StringIO()):
                release.main()
            self.assertEqual('high', capture.call_args.kwargs['reasoning_effort'])
            self.assertEqual('alias', capture.call_args.kwargs['requested_model'])
            children = [c for c in commands if any('evaluate_' in token for token in c)]
            self.assertEqual(2, len(children))
            for command in children:
                self.assertEqual('high', command[command.index('--reasoning-effort')+1])
                self.assertEqual('resolved', command[command.index('--model')+1])


if __name__ == '__main__':
    unittest.main()
