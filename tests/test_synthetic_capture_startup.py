"""Real synthetic producer startup, missing-operation and cleanup regressions."""
import json
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from foundation.conformance.transition_controls import capture_control, SPECS
from foundation.conformance import runner


class SyntheticCaptureStartupTests(unittest.TestCase):
    def exercise(self, prelude, after_run_error=None, sink_error=False, corrupt_process=None):
        original_write = Path.write_text
        original_popen = subprocess.Popen
        processes = []
        original_run = runner.run_one
        original_stream = runner.stream_process

        def run(*args, **kwargs):
            result = original_run(*args, **kwargs)
            if after_run_error:
                raise after_run_error('synthetic after-capture error')
            return result

        def stream(*args, **kwargs):
            if sink_error:
                def fail(name, chunk):
                    raise RuntimeError('synthetic sink failure')
                kwargs['synthetic_raw_sink'] = fail
            return original_stream(*args, **kwargs)

        def write(path, text, *args, **kwargs):
            if path.name == 'synthetic-process.json' and corrupt_process is not None:
                original_write(path, corrupt_process, *args, **kwargs)
                raise ValueError('controlled original process-record write failure')
            if path.name == 'producer.py':
                anchor = "_fixture_phase('entered')\n"
                text = text.replace(anchor, anchor + prelude, 1) if anchor in text else prelude + text
            return original_write(path, text, *args, **kwargs)

        def popen(*args, **kwargs):
            child = original_popen(*args, **kwargs)
            processes.append(child)
            return child

        spec = next(row for row in SPECS if row['id'] == 'P-complete-prefix-no-final')
        tick = time.monotonic()
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(Path, 'write_text', write), patch.object(subprocess, 'Popen', popen), patch.object(runner, 'run_one', run), patch.object(runner, 'stream_process', stream):
                try:
                    result = capture_control(spec, Path(directory))
                except AssertionError as error:
                    result = {'actual': 'construction-error', 'error': str(error), 'diagnostics': getattr(error, 'diagnostics', None)}
            if 'construction_diagnostics' in result:
                result['diagnostics'] = result['construction_diagnostics']
            result['owned_processes'] = [{'pid': child.pid, 'reaped_exit': child.poll()} for child in processes]
            # Serialize before deletion, then inspect the retained body afterward.
            retained = json.dumps(result)
            # Existing check runners save stdout. Bodies survive even a later
            # assertion failure, rather than only temporary paths and hashes.
            print('SYNTHETIC_CAPTURE_EVIDENCE=' + retained, flush=True)
        self.assertTrue(processes)
        self.assertTrue(all(child.poll() is not None for child in processes))
        self.assertLess(time.monotonic() - tick, 10)
        return json.loads(retained)

    def test_delayed_start_still_requires_real_host_completion(self):
        result = self.exercise('import time; time.sleep(1)\n')
        self.assertEqual('fail', result['actual'])
        self.assertFalse(result['model_compliance'])

    def test_never_ready_is_construction_error_with_retained_bodies(self):
        result = self.exercise('import time; time.sleep(30)\n')
        self.assertEqual('construction-error', result['actual'])
        detail = result['diagnostics']
        self.assertTrue(detail['process']['timed_out'])
        self.assertIsNotNone(detail['process']['exit'])
        self.assertEqual('', detail['artifacts']['stdout']['text'])
        self.assertEqual('', detail['artifacts']['stderr']['text'])
        self.assertEqual('', detail['artifacts']['journal']['text'])
        self.assertIn('facts', json.loads(detail['artifacts']['state']['text']))
        self.assertEqual(['entered'], [phase['phase'] for phase in detail['phases']])
        process = json.loads(detail['artifacts']['process']['text'])
        for name in ('stdout', 'stderr'):
            self.assertEqual(process['diagnostics']['raw_sha256'][name], detail['artifacts'][name]['sha256'])

    def test_child_failure_retains_raw_stderr_and_cannot_pass(self):
        # Insert failure after the fixture's diagnostic setup but before Host import.
        result = self.exercise("import sys; sys.stderr.write('synthetic startup failure\\n'); sys.exit(7)\n")
        self.assertEqual('construction-error', result['actual'])
        detail = result['diagnostics']
        self.assertFalse(detail['process']['timed_out'])
        self.assertEqual(7, detail['process']['exit'])
        self.assertEqual('synthetic startup failure\n', detail['artifacts']['stderr']['text'])
        self.assertEqual('', detail['artifacts']['stdout']['text'])
        self.assertEqual('', detail['artifacts']['journal']['text'])
        process = json.loads(detail['artifacts']['process']['text'])
        self.assertEqual(process['diagnostics']['raw_sha256']['stderr'], detail['artifacts']['stderr']['sha256'])

    def test_compile_failure_before_child_logging_retains_exact_stderr(self):
        result = self.exercise('this is invalid Python syntax !\n')
        self.assertEqual('construction-error', result['actual'])
        detail = result['diagnostics']
        self.assertEqual(1, detail['process']['exit'])
        self.assertIn('SyntaxError', detail['artifacts']['stderr']['text'])
        self.assertEqual(detail['process']['diagnostics']['raw_sha256']['stderr'], detail['artifacts']['stderr']['sha256'])
        self.assertEqual([], detail['phases'])

    def test_early_run_one_errors_retain_completed_host_bodies(self):
        for error_type in (ValueError, KeyError):
            with self.subTest(error=error_type.__name__):
                result = self.exercise('', after_run_error=error_type)
                self.assertEqual('construction-error', result['actual'])
                detail = result['diagnostics']
                self.assertTrue(detail['artifacts']['journal']['text'])
                self.assertIn('mcp_tool_call', detail['artifacts']['stdout']['text'])
                self.assertEqual(['entered', 'host-imported', 'host-completed', 'host-completed', 'interruption-ready'], [p['phase'] for p in detail['phases']])

    def test_corrupt_auxiliary_cannot_replace_original_construction_error(self):
        for body in ('{', '[]', '{"diagnostics":[]}', '{"diagnostics":{"raw_sha256":[]}}'):
            with self.subTest(body=body):
                result = self.exercise('', corrupt_process=body)
                self.assertEqual('construction-error', result['actual'])
                self.assertIn('controlled original process-record write failure', result['error'])
                detail = result['diagnostics']
                self.assertEqual(body, detail['artifacts']['process']['text'])
                self.assertTrue(detail['auxiliary_errors'])
                self.assertTrue(detail['artifacts']['stdout']['text'])

    def test_sink_error_still_reaps_owned_producer(self):
        result = self.exercise('', sink_error=True)
        self.assertEqual('construction-error', result['actual'])
        self.assertIn('synthetic sink failure', result['error'])
        self.assertIsNotNone(result['diagnostics']['process']['exit'])
        self.assertFalse(result['diagnostics']['artifacts']['stdout']['matches_observed_raw_hash'])

    def test_native_default_does_not_retain_raw_diagnostics(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            command = [sys.executable, '-c', "import sys; sys.stderr.write('synthetic diagnostic\\n'); print('{\"type\":\"thread.started\"}')", '--json']
            result = runner.stream_process(command, runner.safe_env(root), root, root/'out', 2)
            self.assertEqual(0, result['exit'])
            self.assertFalse(result['diagnostics']['raw_stderr_retained'])
            self.assertFalse(result['diagnostics']['non_json_stdout_retained'])
            self.assertNotIn('synthetic_coordination', result)
            self.assertNotIn('synthetic_coordination', result['diagnostics'])
            self.assertEqual(hashlib.sha256(b'synthetic diagnostic\n').hexdigest(), result['diagnostics']['raw_sha256']['stderr'])
            self.assertFalse((root/'out/synthetic-stderr.bin').exists())

    def test_invalid_purpose_command_or_producer_rejected_before_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            producer = root/'producer.py'
            producer.write_text('print("synthetic")\n')
            command = [sys.executable, str(producer)]
            good_hash = hashlib.sha256(producer.read_bytes()).hexdigest()
            record = {'path': 'producer.py', 'sha256':good_hash, 'mode':'0644'}
            for mode in ('purpose', 'command', 'producer'):
                with self.subTest(mode=mode):
                    launch = root/'launch.json'
                    launch.write_text(json.dumps({'purpose':'configured-workbench' if mode=='purpose' else 'controlled-sensitivity',
                        'executed_command':['different'] if mode=='command' else command,
                        'producer_path':str(producer),'producer':record,
                        'expected_producer_sha256':'0'*64 if mode=='producer' else good_hash}))
                    for options in ({'synthetic_raw_sink':lambda name, chunk: None},
                                    {'synthetic_ready':lambda: True}):
                        with patch.object(subprocess, 'Popen') as popen:
                            with self.assertRaises(ValueError):
                                runner.stream_process(command, {}, root, root, 2, source_launch=launch, **options)
                            popen.assert_not_called()


if __name__ == '__main__':
    unittest.main()
