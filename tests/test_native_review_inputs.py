"""Opt-in release evidence uses canonical callers and actual local byte effects."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import shutil
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


class NativeReviewInputsTests(unittest.TestCase):
    @contextlib.contextmanager
    def local_cli(self, outcome='succeeded', mutate=None, result=True, model_header=True):
        original = subprocess.Popen
        attempts = []
        def launch(command, **kwargs):
            output = Path(command[command.index('--output-last-message') + 1])
            cwd = Path(command[command.index('--cd') + 1])
            attempts.append((output, cwd))
            code = 'import sys; from pathlib import Path; '
            if result:
                code += f'Path({str(output)!r}).write_text(\'{"{"}"verdict":"not_ready","playbook":"retained"{"}"}\'); '
            code += "print('{\"type\":\"thread.started\",\"thread_id\":\"synthetic-control\"}',flush=True); "
            code += "print('{\"type\":\"turn.completed\"}',flush=True); "
            if model_header:
                code += "print('model: synthetic-model',file=sys.stderr,flush=True); "
            if mutate:
                code += mutate(cwd)
            code += 'sys.exit(7)' if outcome == 'nonzero' else 'sys.exit(0)'
            proc = original([sys.executable, '-B', '-c', code], **kwargs)
            if outcome == 'timed_out':
                communicate = proc.communicate
                def timeout(*args, **kw):
                    communicate(*args, **kw)
                    proc.communicate = communicate
                    raise subprocess.TimeoutExpired(command, kw.get('timeout'))
                proc.communicate = timeout
            return proc
        with mock.patch.object(subprocess, 'Popen', side_effect=launch):
            yield attempts

    def setup_context(self, directory):
        import native_review_inputs as inputs
        profile_path = next(path for path in (ROOT / 'profiles').glob('*.json')
                            if json.loads(path.read_text())['plugin_name'] == json.loads(behavior.MANIFEST.read_text())['name'])
        profile = json.loads(profile_path.read_text())
        home = directory / 'owned-home'
        installed = home / 'plugins/cache' / profile['marketplace'] / profile['plugin_name'] / profile['plugin_version']
        shutil.copytree(ROOT / 'plugins' / profile['plugin_name'], installed)
        (home / 'auth.json').write_text('DO_NOT_CAPTURE_AUTH')
        catalog = {'installed': [{'pluginId': profile['plugin_name'] + '@' + profile['marketplace'],
                    'name': profile['plugin_name'], 'marketplaceName': profile['marketplace'],
                    'version': profile['plugin_version'], 'enabled': True, 'installed': True}], 'available': []}
        env = {'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'HOME': str(directory),
               'CODEX_HOME': str(home), 'PYTHONDONTWRITEBYTECODE': '1'}
        release = evidence.create_run(directory / 'evidence', 'release', {'synthetic': True})
        context = inputs.prepare_release_context(release, ROOT, profile_path, home, env,
                                                 json.dumps(catalog).encode(), installed_at_ns=1)
        suite = evidence.create_run(release, 'suite', {'synthetic': True})
        handle = inputs.load_suite_context(context['path'], context['sha256'], suite, env, 'synthetic-control', candidate_root=ROOT)
        return inputs, release, suite, handle, env

    def invoke(self, kind, directory, suite, handle):
        if kind == 'behavior':
            fixture = directory / 'fixture'
            fixture.mkdir(exist_ok=True)
            (fixture / 'AGENTS.md').write_text('synthetic fixture instructions\n')
            return behavior.run_scenario(fixture, {'id': 'synthetic', 'prompt': 'route'}, None, 5,
                                         evidence_dir=suite, review_inputs=handle)
        return review.run_review(review.load_suite()[0], 'broken', 5,
                                 evidence_dir=suite, review_inputs=handle)[0]

    def test_canonical_callers_retain_pre_post_bytes_after_cleanup_for_all_process_outcomes(self):
        for kind in ('behavior', 'review'):
            for outcome in ('succeeded', 'nonzero', 'timed_out'):
                with self.subTest(kind=kind, outcome=outcome), tempfile.TemporaryDirectory() as temp:
                    directory = Path(temp)
                    _, release, suite, handle, env = self.setup_context(directory)
                    with mock.patch.dict(os.environ, env, clear=True), self.local_cli(outcome) as calls:
                        result = self.invoke(kind, directory, suite, handle)
                    self.assertEqual('retained', result['playbook'])
                    attempt = next(suite.glob(kind + '-*/invocation.json')).parent
                    capture = attempt / 'review-inputs'
                    before = json.loads((capture / 'initial-files.json').read_text())
                    after = json.loads((capture / 'final-files.json').read_text())
                    self.assertEqual(before['files'], after['files'])
                    self.assertTrue(before['files'])
                    for name, row in before['files'].items():
                        raw = (capture / 'initial-fixture' / name).read_bytes()
                        self.assertEqual(row['sha256'], evidence.digest(raw))
                        self.assertEqual(row['size_bytes'], len(raw))
                        self.assertEqual(raw, (capture / 'final-fixture' / name).read_bytes())
                    status = json.loads((capture / 'capture-status.json').read_text())
                    self.assertEqual([], status['changed_paths'])
                    self.assertEqual('synthetic-model', status['observed_model'])
                    self.assertLess(status['started_at_ns'], status['finished_at_ns'])
                    self.assertEqual(outcome, json.loads((attempt / 'process.json').read_text())['status'])
                    self.assertFalse(calls[0][0].exists())
                    if kind == 'review':
                        self.assertFalse(calls[0][1].exists())
                    self.assertNotIn('review.json', before['files'])
                    for path in release.rglob('*'):
                        if path.is_file():
                            self.assertNotIn(b'DO_NOT_CAPTURE_AUTH', path.read_bytes())

    def test_mutations_symlinks_special_files_are_gaps_and_not_followed(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            _, _, suite, handle, env = self.setup_context(directory)
            secret = directory / 'private.txt'
            secret.write_text('PRIVATE_OUTSIDE_FIXTURE')
            def mutate(cwd):
                return (f'Path({str(cwd / "AGENTS.md")!r}).write_text("changed"); '
                        f'Path({str(cwd / "link")!r}).symlink_to({str(secret)!r}); '
                        f'import os; os.mkfifo({str(cwd / "fifo")!r}); ')
            with mock.patch.dict(os.environ, env, clear=True), self.local_cli(mutate=mutate):
                result = self.invoke('behavior', directory, suite, handle)
            self.assertEqual('retained', result['playbook'])
            capture = next(suite.glob('behavior-*')) / 'review-inputs'
            status = json.loads((capture / 'capture-status.json').read_text())
            self.assertIn('AGENTS.md', status['changed_paths'])
            self.assertTrue(status['gaps'])
            self.assertFalse((capture / 'final-fixture/link').exists())
            self.assertFalse((capture / 'final-fixture/fifo').exists())
            self.assertTrue((capture.parent / 'result-status.json').is_file())

    def test_context_hash_and_retained_source_tamper_fail_before_invocation(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            inputs, release, suite, handle, env = self.setup_context(directory)
            path = release / 'review-inputs/context.json'
            expected = evidence.digest(path.read_bytes())
            with self.assertRaises(ValueError):
                inputs.load_suite_context(path, '0' * 64, suite / 'other', env, 'synthetic', candidate_root=ROOT)
            with self.assertRaisesRegex(ValueError, 'different candidate'):
                inputs.load_suite_context(path, expected, suite / 'other', env, 'synthetic', candidate_root=directory)
            with self.assertRaisesRegex(ValueError, 'installation home'):
                inputs.load_suite_context(path, expected, suite / 'other', {**env, 'CODEX_HOME': '/different'},
                                          'synthetic', candidate_root=ROOT)
            context = json.loads(path.read_text())
            record = context['source_index'][0]
            (path.parent / record['path']).write_bytes(b'changed retained source')
            with self.assertRaises(ValueError):
                inputs.load_suite_context(path, expected, suite / 'other', env, 'synthetic', candidate_root=ROOT)

    def test_snapshot_missing_input_is_not_fabricated_empty_state(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            inputs, _, suite, handle, env = self.setup_context(directory)
            attempt = suite / 'missing'
            attempt.mkdir()
            capture = handle.begin_attempt(attempt, directory / 'absent', directory / 'output.json', env)
            capture.finish()
            status = json.loads((attempt / 'review-inputs/capture-status.json').read_text())
            initial = json.loads((attempt / 'review-inputs/initial-files.json').read_text())
            self.assertFalse(initial['root_present'])
            self.assertTrue(status['gaps'])

    def test_capture_error_keeps_usable_result_without_consuming_replacement(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            inputs, _, suite, handle, env = self.setup_context(directory)
            fixture = directory / 'fixture'; fixture.mkdir()
            (fixture / 'AGENTS.md').write_text('synthetic')
            with mock.patch.dict(os.environ, env, clear=True), self.local_cli() as calls, mock.patch.object(
                    inputs, 'snapshot', side_effect=PermissionError('synthetic denied capture')):
                outcome = behavior.run_scenario_with_replacement(fixture,
                    {'id': 'capture-error', 'prompt': 'route'}, None, 5,
                    replacement_available=True, evidence_dir=suite, review_inputs=handle)
            self.assertEqual((1, False, None), outcome[1:])
            self.assertEqual(1, len(calls))
            attempt = next(suite.glob('behavior-*/invocation.json')).parent
            gap = json.loads((attempt / 'review-input-gaps.jsonl').read_text())
            self.assertEqual('PermissionError', gap['error_type'])
            self.assertTrue((attempt / 'result-status.json').is_file())

    def test_no_result_preserves_both_captured_attempts_with_one_replacement(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            _, _, suite, handle, env = self.setup_context(directory)
            fixture = directory / 'fixture'; fixture.mkdir()
            (fixture / 'AGENTS.md').write_text('synthetic')
            with mock.patch.dict(os.environ, env, clear=True), self.local_cli(result=False) as calls:
                outcome = behavior.run_scenario_with_replacement(fixture,
                    {'id': 'no-result', 'prompt': 'route'}, None, 5,
                    replacement_available=True, evidence_dir=suite, review_inputs=handle)
            self.assertEqual((None, 2, True), outcome[:3])
            self.assertIsNotNone(outcome[3])
            self.assertEqual(2, len(calls))
            attempts = list(suite.glob('behavior-*/invocation.json'))
            self.assertEqual(2, len(attempts))
            for invocation in attempts:
                self.assertTrue((invocation.parent / 'review-inputs/final-files.json').is_file())
                self.assertFalse((invocation.parent / 'result-status.json').exists())

    def test_live_installed_drift_and_ambiguous_catalog_are_rejected_before_suite(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            inputs, release, suite, handle, env = self.setup_context(directory)
            path = release / 'review-inputs/context.json'
            context = json.loads(path.read_text())
            installed = Path(context['selected_plugin']['cache_path'])
            (installed / 'unexpected.txt').write_text('added installed source')
            with self.assertRaisesRegex(ValueError, 'installed tree changed'):
                inputs.load_suite_context(path, evidence.digest(path.read_bytes()), suite / 'other', env, 'synthetic', candidate_root=ROOT)
            (installed / 'unexpected.txt').unlink()
            catalog = json.loads((path.parent / 'catalog.json').read_text())
            catalog['installed'].append(catalog['installed'][0])
            other = evidence.create_run(directory / 'other', 'release', {})
            profile = next(row['original_path'] for row in context['source_index'] if row['role'] == 'candidate-profile')
            with self.assertRaisesRegex(ValueError, 'exactly one'):
                inputs.prepare_release_context(other, ROOT, profile, directory / 'owned-home', env,
                                               json.dumps(catalog).encode(), installed_at_ns=1)

    def test_missing_observed_model_is_a_gap_not_a_replacement_trigger(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            _, _, suite, handle, env = self.setup_context(directory)
            fixture = directory / 'fixture'; fixture.mkdir()
            with mock.patch.dict(os.environ, env, clear=True), self.local_cli(model_header=False) as calls:
                outcome = behavior.run_scenario_with_replacement(fixture,
                    {'id': 'no-model-header', 'prompt': 'route'}, None, 5,
                    replacement_available=True, evidence_dir=suite, review_inputs=handle)
            self.assertEqual((1, False, None), outcome[1:])
            self.assertEqual(1, len(calls))
            attempt = next(suite.glob('behavior-*/invocation.json')).parent
            status = json.loads((attempt / 'review-inputs/capture-status.json').read_text())
            self.assertIsNone(status['observed_model'])
            self.assertIn('observed model header unavailable', status['gaps'])

    def test_environment_records_actual_digest_without_secret_values(self):
        import native_review_inputs as inputs
        supplied = {'PATH': '/synthetic/bin', 'CODEX_HOME': '/synthetic/owned', 'PROVIDER_TOKEN': 'NEVER_PERSIST'}
        row = inputs.environment(supplied)
        self.assertEqual(evidence.digest(inputs.canonical(supplied)), row['sha256'])
        self.assertEqual(['PROVIDER_TOKEN'], row['unexpected_keys'])
        self.assertNotIn('NEVER_PERSIST', json.dumps(row))

    def test_release_forwards_explicit_context_path_and_hash_to_both_children(self):
        import release_smoke as release
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            _, _, _, _, env = self.setup_context(directory)
            commands = []
            def run(command, runtime_env, label, **kwargs):
                commands.append(command)
                if command[:3] == ['codex', 'plugin', 'list']:
                    raise AssertionError('catalog capture belongs to explicit module call')
                if any('evaluate_review_quality.py' in token for token in command):
                    return 'Review-quality pilot: synthetic\nReview-quality pilot passed synthetic'
                return 'synthetic'
            # The launch seam is checked without a model/installation. Context
            # preparation itself is exercised against actual filesystem bytes above.
            import native_review_inputs as inputs
            sentinel = {'path': str(directory / 'context.json'), 'sha256': 'a' * 64}
            auth = directory / 'auth.json'; auth.write_text('{}')
            with mock.patch.object(sys, 'argv', ['release_smoke.py', '--repo', str(directory / 'backend'),
                    '--auth-file', str(auth), '--evidence-dir', str(directory / 'fresh'),
                    '--review-quality', '--claim-review-inputs']), mock.patch.object(release, 'run', side_effect=run), \
                    mock.patch.object(release, 'git_output', side_effect=lambda *a: '' if a[0]=='status' else 'synthetic'), \
                    mock.patch.object(release, 'backend_git_output', side_effect=lambda _r,*a: '' if a[0]=='status' else 'synthetic'), \
                    mock.patch.object(release, 'prepare_policy', return_value={}), mock.patch.object(release, 'verify_policy'), \
                    mock.patch.object(inputs, 'capture_release_context', return_value=sentinel), contextlib.redirect_stdout(__import__('io').StringIO()):
                release.main()
            children = [c for c in commands if any('evaluate_' in str(t) for t in c)]
            self.assertEqual(2, len(children))
            for command in children:
                self.assertEqual(sentinel['path'], command[command.index('--review-input-context') + 1])
                self.assertEqual(sentinel['sha256'], command[command.index('--review-input-context-sha256') + 1])


if __name__ == '__main__':
    unittest.main()
