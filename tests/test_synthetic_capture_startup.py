"""Real synthetic producer startup, missing-operation and cleanup regressions."""
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from foundation.conformance.transition_controls import capture_control, SPECS


class SyntheticCaptureStartupTests(unittest.TestCase):
    def exercise(self, prelude):
        original_write = Path.write_text
        original_popen = subprocess.Popen
        processes = []

        def write(path, text, *args, **kwargs):
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
            with patch.object(Path, 'write_text', write), patch.object(subprocess, 'Popen', popen):
                try:
                    result = capture_control(spec, Path(directory))
                except AssertionError as error:
                    result = {'actual': 'construction-error', 'diagnostics': getattr(error, 'diagnostics', None)}
            # Serialize before deletion, then inspect the retained body afterward.
            retained = json.dumps(result)
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


if __name__ == '__main__':
    unittest.main()
