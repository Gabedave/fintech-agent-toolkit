"""Actual effect controls must reach their hold before controlled interruption."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from foundation.conformance import effect_controls
from foundation.conformance.source_binding import validate


class EffectControlReadinessTests(unittest.TestCase):
    def control(self, program, *, require_timeout=True):
        children = []
        original_popen = subprocess.Popen

        def popen(*args, **kwargs):
            child = original_popen(*args, **kwargs)
            children.append(child)
            return child

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'effect'
            error = None
            with patch.object(subprocess, 'Popen', popen):
                try:
                    effect_controls.actual(effect_controls.SPECS[0], root,
                                           program=program, require_timeout=require_timeout)
                except AssertionError as failure:
                    error = str(failure)
            run = root / 'actual-run'
            record = {'error': error,
                      'process': json.loads((root / 'raw-process-return.json').read_text()),
                      'result': json.loads((run / 'result.json').read_text()),
                      'stdout': (run / 'observer/stdout.jsonl').read_text(),
                      'observation': json.loads((run / 'observation.json').read_text())}
            record['source_binding'] = validate(record['observation'])
        self.assertTrue(children)
        self.assertTrue(all(child.poll() is not None for child in children))
        return record

    def assert_effect_retained(self, record):
        self.assertEqual('fail', record['result']['status'])
        self.assertTrue(record['result']['known_behavioral_failure'])
        self.assertNotEqual(record['observation']['initial_files'], record['observation']['final_files'])
        self.assertEqual({'purpose': 'controlled-sensitivity'}, record['source_binding'])

    def test_slow_start_reaches_actual_effect_before_interruption(self):
        program = effect_controls.PROGRAM.replace('sys.path.insert(0, sys.argv[1])',
                                                  'time.sleep(1.1)\nsys.path.insert(0, sys.argv[1])', 1)
        record = self.control(program)
        self.assertIsNone(record['error'])
        self.assert_effect_retained(record)
        coordination = record['process']['synthetic_coordination']
        self.assertTrue(coordination['ready_observed'])
        self.assertEqual('ready-window', coordination['interruption_trigger'])
        self.assertGreater(coordination['ready_observed_at_ns'] - record['process']['started_at_ns'], 1_000_000_000)

    def test_slow_actual_host_operation_reaches_original_hold(self):
        program = effect_controls.PROGRAM.replace('    v = h.call(t, a)',
                                                  '    if counter == 1: time.sleep(1.1)\n    v = h.call(t, a)', 1)
        record = self.control(program)
        self.assertIsNone(record['error'])
        self.assert_effect_retained(record)
        self.assertTrue(record['process']['synthetic_coordination']['ready_observed'])

    def test_ready_after_prep_without_actual_effect_is_rejected(self):
        program = effect_controls.PROGRAM.replace('active = True', 'hold()\nactive = True', 1)
        record = self.control(program)
        self.assertIn('No actual file effect', record['error'])
        self.assertTrue(record['process']['synthetic_coordination']['ready_observed'])
        self.assertIn('mcp_tool_call', record['stdout'])
        self.assertFalse(record['result']['known_behavioral_failure'])

    def test_missing_ready_retains_effect_but_rejects_construction(self):
        program = effect_controls.PROGRAM.replace("'phase': 'interruption-ready'", "'phase': 'not-ready'", 1)
        record = self.control(program)
        self.assertIn('readiness', record['error'])
        self.assert_effect_retained(record)
        coordination = record['process']['synthetic_coordination']
        self.assertFalse(coordination['ready_observed'])
        self.assertEqual('outer-watchdog', coordination['interruption_trigger'])
        self.assertEqual(record['process']['started_at_ns'] + 5_000_000_000, coordination['outer_deadline_ns'])

    def test_false_ready_cannot_replace_completed_host_work(self):
        program = effect_controls.PROGRAM.replace("def message(t):", "hold()\n\ndef message(t):", 1)
        record = self.control(program)
        self.assertIn('No completed actual prep event', record['error'])
        self.assertTrue(record['process']['synthetic_coordination']['ready_observed'])
        self.assertNotIn('mcp_tool_call', record['stdout'])
        self.assertFalse(record['result']['known_behavioral_failure'])

    def test_unexpected_eof_cannot_replace_interruption(self):
        program = effect_controls.PROGRAM.replace('    time.sleep(30)', '    return', 1)
        record = self.control(program)
        self.assertIsNotNone(record['error'])
        self.assertFalse(record['process']['timed_out'])
        self.assertEqual(0, record['process']['exit'])
        self.assertNotEqual(record['observation']['initial_files'], record['observation']['final_files'])
        self.assertNotEqual('pass', record['result']['status'])
        self.assertEqual({'purpose': 'controlled-sensitivity'}, record['source_binding'])

    def test_no_interruption_override_keeps_existing_eof_transport(self):
        program = effect_controls.PROGRAM.replace('    time.sleep(30)', '    return', 1)
        record = self.control(program, require_timeout=False)
        self.assertIsNone(record['error'])
        self.assertNotIn('synthetic_coordination', record['process'])
        self.assertFalse(record['process']['timed_out'])
        self.assertNotEqual(record['observation']['initial_files'], record['observation']['final_files'])
        self.assertNotEqual('pass', record['result']['status'])
        self.assertEqual({'purpose': 'controlled-sensitivity'}, record['source_binding'])

    def test_stale_directory_rejected_before_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'interruption-ready.json').write_text('{"phase":"interruption-ready","ns":1}')
            with patch.object(subprocess, 'Popen') as popen:
                with self.assertRaises(FileExistsError):
                    effect_controls.actual(effect_controls.SPECS[0], root)
                popen.assert_not_called()


if __name__ == '__main__':
    unittest.main()
