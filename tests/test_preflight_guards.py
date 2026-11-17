"""Actual pipe capture regressions; synthetic local producers, never model proof."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

from foundation.conformance.runner import (
    require_effective_model, require_tool_isolation, require_tool_availability, safe_env, stream_process,
)


class PreflightGuards(unittest.TestCase):
    def capture(self, stdout='', stderr='', exit_code=0):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            producer = root / 'producer.py'
            producer.write_text(
                'import sys;sys.stdout.write(%r);sys.stderr.write(%r);sys.exit(%r)'
                % (stdout, stderr, exit_code), encoding='utf-8')
            command = [sys.executable, '-B', str(producer)]
            result = stream_process(command, safe_env(root), root, root / 'out', 5)
            diagnostics = json.loads((root / 'out/diagnostics.json').read_text())
            self.assertEqual(exit_code, diagnostics['process_exit'])
            self.assertEqual(result['timed_out'], diagnostics['timed_out'])
            self.assertFalse(diagnostics['raw_stderr_retained'])
            self.assertNotIn('private sentinel', json.dumps(diagnostics))
            return result

    def isolated(self):
        return self.capture('shell_tool stable false\nunified_exec stable false\n')

    def test_complete_false_observations_pass(self):
        result = self.isolated()
        require_tool_isolation(result)
        self.assertEqual(2, len(result['diagnostics']['allowlisted_feature_rows']))

    def test_normal_policy_records_availability_without_claiming_absence(self):
        result = self.capture('shell_tool stable false\nunified_exec stable true\n')
        self.assertEqual({'shell_tool': False, 'unified_exec': True}, require_tool_availability(result))
        with self.assertRaises(RuntimeError):
            require_tool_isolation(result)
        for features in ({'shell_tool': False}, {'shell_tool': False, 'unified_exec': 1}):
            broken = copy.deepcopy(result)
            broken['diagnostics']['tool_features'] = features
            with self.assertRaises(RuntimeError):
                require_tool_availability(broken)
        for key, value in [('exit', 7), ('timed_out', True), ('capture_gaps', ['missing'])]:
            broken = copy.deepcopy(result)
            broken[key] = value
            with self.assertRaises(RuntimeError):
                require_tool_availability(broken)
        result['diagnostics']['feature_conflicts'] = ['unified_exec']
        with self.assertRaises(RuntimeError):
            require_tool_availability(result)

    def test_failed_process_cannot_rescue_false_looking_observations(self):
        result = self.capture('shell_tool stable false\nunified_exec stable false\n',
                              'private sentinel\n', 7)
        with self.assertRaises(RuntimeError):
            require_tool_isolation(result)

    def test_conflict_is_rejected_even_when_last_observation_is_false(self):
        result = self.capture('shell_tool stable false\nunified_exec stable true\n'
                              'unified_exec stable false\n')
        self.assertEqual(['unified_exec'], result['diagnostics']['feature_conflicts'])
        with self.assertRaises(RuntimeError):
            require_tool_isolation(result)

    def test_incomplete_capture_and_missing_completion_fields_fail_closed(self):
        result = self.isolated()
        for key, value in [('timed_out', True), ('parse_errors', ['gap']),
                           ('capture_gaps', [{'kind': 'missing-output'}])]:
            broken = copy.deepcopy(result)
            broken[key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                require_tool_isolation(broken)
        for key in ('exit', 'timed_out', 'parse_errors', 'capture_gaps'):
            broken = copy.deepcopy(result)
            del broken[key]
            with self.subTest(missing=key), self.assertRaises(RuntimeError):
                require_tool_isolation(broken)

    def test_feature_row_overflow_is_incomplete(self):
        result = self.capture('shell_tool stable false\nunified_exec stable false\n' * 5000)
        self.assertEqual(64, len(result['diagnostics']['allowlisted_feature_rows']))
        self.assertEqual([{'kind': 'allowlisted-feature-row-limit'}], result['capture_gaps'])
        self.assertEqual(['allowlisted feature row limit exceeded'], result['parse_errors'])
        with self.assertRaises(RuntimeError):
            require_tool_isolation(result)

    def test_integer_zero_cannot_substitute_for_a_false_observation(self):
        result = self.isolated()
        result['diagnostics']['tool_features'] = {'shell_tool': 0, 'unified_exec': 0}
        with self.assertRaises(RuntimeError):
            require_tool_isolation(result)

    def test_actual_model_identity_requires_successful_complete_process(self):
        good = self.capture(stderr='model: sample-model\n')
        self.assertEqual('sample-model', require_effective_model(good))
        for result in (self.capture(stderr='model: sample-model\n', exit_code=7),
                       self.capture(stderr='model: first\nmodel: second\n'),
                       self.capture(stdout='requested model: sample-model\n')):
            with self.assertRaises(RuntimeError):
                require_effective_model(result)
        for key in ('exit', 'timed_out', 'parse_errors', 'capture_gaps'):
            broken = copy.deepcopy(good)
            del broken[key]
            with self.subTest(missing=key), self.assertRaises(RuntimeError):
                require_effective_model(broken)


if __name__ == '__main__':
    unittest.main()
