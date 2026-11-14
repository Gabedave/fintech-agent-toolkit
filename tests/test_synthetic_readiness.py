"""Real-process readiness/interruption contrasts against frozen control outcomes."""
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from foundation.conformance.transition_controls import capture_control, SPECS
from foundation.conformance import runner


class SyntheticReadinessTests(unittest.TestCase):
    def control(self, ident='P-complete-prefix-no-final', barrier=None, mutate=None,
                ready_grace=None, callback_error=False):
        original_write, original_popen = Path.write_text, subprocess.Popen
        original_stream = runner.stream_process
        children, timing = [], {}
        cancel = threading.Event()
        spec = next(row for row in SPECS if row['id'] == ident)
        started = time.monotonic()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)/'fixture'

            def release():
                until = time.monotonic()+6
                while not (root/'barrier').exists() and time.monotonic() < until:
                    if cancel.wait(.005):
                        return
                if not (root/'barrier').exists():
                    return
                timing['blocked_observed_ns'] = time.monotonic_ns()
                if not cancel.wait(2.25):
                    (root/'release').touch()
                    timing['released_ns'] = time.monotonic_ns()

            def write(path, text, *args, **kwargs):
                if path.name == 'producer.py':
                    block = "(_fixture_root/'barrier').write_text('waiting')\nwhile not (_fixture_root/'release').exists(): time.sleep(.005)\n"
                    if barrier == 'before-import':
                        anchor = "_fixture_phase('entered')\n"
                        text = text.replace(anchor, anchor+block, 1)
                    elif barrier == 'inside-host':
                        anchor = "h = Host(cfg['workspace'], json.loads(pathlib.Path(cfg['state']).read_text()), cfg['journal'], cfg['installed'])\n"
                        injected = "_original_host_call = h._call\ndef _blocked_host_call(name, args):\n" + ''.join('    '+line+'\n' for line in block.splitlines()) + "    return _original_host_call(name, args)\nh._call = _blocked_host_call\n"
                        text = text.replace(anchor, anchor+injected, 1)
                    if mutate:
                        text = mutate(text)
                return original_write(path, text, *args, **kwargs)

            def popen(*args, **kwargs):
                child = original_popen(*args, **kwargs)
                children.append(child)
                return child

            def stream(*args, **kwargs):
                if ready_grace is not None:
                    kwargs['synthetic_ready_timeout'] = ready_grace
                if callback_error:
                    def broken():
                        raise RuntimeError('controlled readiness callback failure')
                    kwargs['synthetic_ready'] = broken
                return original_stream(*args, **kwargs)

            worker = threading.Thread(target=release)
            if barrier:
                worker.start()
            try:
                with patch.object(Path, 'write_text', write), patch.object(subprocess, 'Popen', popen), patch.object(runner, 'stream_process', stream):
                    try:
                        result = capture_control(spec, root)
                    except AssertionError as error:
                        result = {'actual':'construction-error','error':str(error),'diagnostics':getattr(error,'diagnostics',None)}
                def read(name):
                    file = root/name
                    return json.loads(file.read_text()) if file.is_file() else None
                phases = (root/'phases.jsonl').read_text().splitlines() if (root/'phases.jsonl').is_file() else []
                record = {'result':result,'process':read('synthetic-process.json'),
                          'public_result':read('actual-run/result.json'),
                          'phases':[json.loads(line) for line in phases],
                          'stdout':(root/'actual-run/observer/stdout.jsonl').read_text() if (root/'actual-run/observer/stdout.jsonl').exists() else '',
                          'timing':timing,'owned_processes':[{'pid':p.pid,'exit':p.poll()} for p in children]}
                print('SYNTHETIC_READINESS_EVIDENCE='+json.dumps(record),flush=True)
            finally:
                cancel.set()
                if barrier:
                    worker.join(1)
        self.assertFalse(worker.is_alive())
        self.assertTrue(children)
        self.assertTrue(all(p.poll() is not None for p in children))
        self.assertLess(time.monotonic()-started,10)
        return record

    def assert_interrupted_after_work(self, record, expected):
        self.assertEqual(expected,record['result']['actual'])
        process = record['process']
        self.assertTrue(process['timed_out'])
        self.assertTrue(process['synthetic_coordination']['ready_observed'])
        completed = [row for row in record['phases'] if row['phase']=='host-completed']
        ready = [row for row in record['phases'] if row['phase']=='interruption-ready']
        self.assertEqual(2,len(completed))
        self.assertEqual(1,len(ready))
        self.assertGreater(ready[0]['ns'],completed[-1]['ns'])
        self.assertNotIn('turn.completed',record['stdout'])

    def test_delayed_import_barrier_survives_original_two_second_limit(self):
        record = self.control(barrier='before-import')
        self.assert_interrupted_after_work(record,'fail')
        self.assertGreaterEqual((record['timing']['released_ns']-record['timing']['blocked_observed_ns'])/1e9,2.2)

    def test_delayed_real_host_operation_reaches_original_hold(self):
        self.assert_interrupted_after_work(self.control(barrier='inside-host'),'fail')

    def test_marker_gap_remains_incomplete(self):
        record = self.control('P-merely-start-marker')
        self.assert_interrupted_after_work(record,'incomplete')
        self.assertTrue(record['process']['capture_gaps'])

    def test_missing_ready_is_construction_error_and_keeps_known_failure(self):
        def omit(text):
            return text.replace("_fixture_phase('interruption-ready')", "# Deliberately never signal the controlled hold")
        record = self.control(mutate=omit)
        self.assertEqual('construction-error',record['result']['actual'])
        self.assertTrue(record['process']['timed_out'])
        self.assertFalse(record['process']['synthetic_coordination']['ready_observed'])
        self.assertEqual('fail',record['public_result']['status'])

    def test_false_ready_does_not_prove_host_work(self):
        def premature(text):
            anchor = "_fixture_phase('entered')\n"
            return text.replace(anchor,anchor+"_fixture_phase('interruption-ready')\ntime.sleep(30)\n",1)
        record = self.control(mutate=premature)
        self.assertEqual('construction-error',record['result']['actual'])
        self.assertTrue(record['process']['synthetic_coordination']['ready_observed'])
        self.assertNotIn('mcp_tool_call',record['stdout'])

    def test_complete_eof_branch_does_not_wait_for_interruption(self):
        ident = 'I-router-never-read-complete'
        record = self.control(ident)
        self.assertEqual(next(row['expected'] for row in SPECS if row['id']==ident),record['result']['actual'])
        self.assertEqual(0,record['process']['exit'])
        self.assertFalse(record['process']['timed_out'])
        self.assertIn('turn.completed',record['stdout'])

    def test_outer_watchdog_clips_a_long_ready_grace(self):
        record = self.control(ready_grace=30)
        self.assert_interrupted_after_work(record,'fail')
        self.assertEqual('outer-watchdog',record['process']['synthetic_coordination']['interruption_trigger'])
        self.assertEqual(record['process']['started_at_ns']+5_000_000_000,
                         record['process']['synthetic_coordination']['outer_deadline_ns'])

    def test_callback_error_reaps_process_and_retains_original_error(self):
        record = self.control(callback_error=True)
        self.assertEqual('construction-error',record['result']['actual'])
        self.assertIn('controlled readiness callback failure',record['result']['error'])
        self.assertIsNotNone(record['result']['diagnostics']['process']['exit'])

    def test_unexpected_eof_after_host_work_does_not_fake_interruption(self):
        def leave(text):
            return text.replace("_fixture_phase('interruption-ready')",'sys.exit(0)')
        record = self.control(mutate=leave)
        self.assertEqual('construction-error',record['result']['actual'])
        self.assertEqual(0,record['process']['exit'])
        self.assertFalse(record['process']['timed_out'])
        self.assertEqual('fail',record['public_result']['status'])

    def test_stale_ready_state_is_rejected_before_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'phases.jsonl').write_text(json.dumps({'phase':'interruption-ready','ns':1})+'\n')
            spec = next(row for row in SPECS if row['id']=='P-complete-prefix-no-final')
            with patch.object(subprocess,'Popen') as popen:
                with self.assertRaisesRegex(AssertionError,'fresh readiness state') as error:
                    capture_control(spec,root)
                popen.assert_not_called()
            print('STALE_READINESS_EVIDENCE='+json.dumps(error.exception.diagnostics),flush=True)


if __name__ == '__main__':
    unittest.main()
