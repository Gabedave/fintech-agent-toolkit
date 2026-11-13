"""The named pre-edit proof executes trusted source and reads durable effects."""
import copy
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from foundation.conformance import load_cases
from foundation.conformance.host import Host, initialize, possible_file_effects


class NamedSemanticBoundaryTests(unittest.TestCase):
    def facts(self):
        return copy.deepcopy(load_cases()['cases'][0]['variants'][0]['facts'])

    def test_named_reproduction_executes_source_timeout_retry_and_durable_readback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = initialize(root, self.facts())
            initial = copy.deepcopy(state)
            host = Host(root, state)
            source = host.call('inspect', {'resource': 'production'})
            self.assertIn('except TimeoutError', source['content'])
            result = host.call('probe', {'name': 'semantic'})
            self.assertEqual('test_unknown_outcome_replay', result['test'])
            self.assertEqual(source['sha256'], result['executed_source_sha256'])
            self.assertEqual((2, 1, 1, True), tuple(result[key] for key in
                             ('rows', 'expected_rows', 'exit', 'semantic_assertion_reached')))
            self.assertTrue(result['scope']['production_code_executed'])
            self.assertTrue(result['scope']['provider_timeout_retry_path_executed'])
            self.assertTrue(result['scope']['synthetic'])
            self.assertEqual(['committed_then_timeout', 'committed_response'],
                             [event['outcome'] for event in result['provider_events']])
            connection = sqlite3.connect('file:' + str(root / result['scope']['database']) + '?mode=ro', uri=True)
            try:
                self.assertEqual([(1, 'op-synthetic'), (2, 'op-synthetic')],
                                 connection.execute('SELECT attempt, operation FROM debit ORDER BY attempt').fetchall())
            finally:
                connection.close()
            self.assertEqual(initial, state)
            self.assertEqual((0, 0), (state['debits'], state['postings']))
            self.assertEqual(source['sha256'], hashlib.sha256((root / 'src/settlement.py').read_bytes()).hexdigest())
            self.assertEqual(result, host.events[-1]['result'])
            footprint = possible_file_effects('probe', {'name': 'semantic'}, self.facts())
            self.assertLessEqual(set(host.events[-1]['changed']), footprint)
            self.assertIn(result['scope']['database'] + '-wal', footprint)
            repeated = host.call('probe', {'name': 'semantic'})
            self.assertEqual(result, repeated)

    def test_changed_source_never_executes_or_changes_existing_probe_database(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            host = Host(root, initialize(root, self.facts()))
            result = host.call('probe', {'name': 'semantic'})
            database = root / result['scope']['database']
            before = database.read_bytes()
            marker = root / 'executed-malicious-source'
            malicious = 'open(' + repr(str(marker)) + ', "w").write("executed")\n'
            host.call('edit', {'path': 'src/settlement.py', 'content': malicious})
            result = host.call('probe', {'name': 'semantic'})
            self.assertFalse(result['semantic_assertion_reached'])
            self.assertEqual('named semantic source changed or unsupported', result['cause'])
            self.assertNotIn('executed_source_sha256', result)
            self.assertFalse(marker.exists())
            self.assertEqual(before, database.read_bytes())
            self.assertEqual([], host.events[-1]['changed'])

    def test_control_removing_retry_from_trusted_fixture_removes_second_effect(self):
        # A deliberate test-only mutation of the trusted fixture distinguishes
        # source execution from a probe that merely manufactures two rows.
        source = b'def debit(provider, operation):\n    return provider(operation)\n'
        with patch('foundation.conformance.host.SEMANTIC_BASELINE', source), tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            host = Host(root, initialize(root, self.facts()))
            result = host.call('probe', {'name': 'semantic'})
            self.assertIn('TimeoutError', result['error'])
            self.assertNotIn('semantic_assertion_reached', result)
            connection = sqlite3.connect('file:' + str(root / 'semantic.sqlite') + '?mode=ro', uri=True)
            try:
                self.assertEqual([(1, 'op-synthetic')],
                                 connection.execute('SELECT attempt, operation FROM debit').fetchall())
            finally:
                connection.close()

    def test_changed_source_without_prior_probe_and_missing_source_have_no_effects(self):
        for content in ('raise RuntimeError("must not execute")\n', None):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                host = Host(root, initialize(root, self.facts()))
                source = root / 'src/settlement.py'
                if content is None:
                    source.unlink()
                else:
                    host.call('edit', {'path': 'src/settlement.py', 'content': content})
                before = set(root.rglob('*'))
                result = host.call('probe', {'name': 'semantic'})
                self.assertFalse(result['semantic_assertion_reached'])
                self.assertEqual(before, set(root.rglob('*')))
                self.assertEqual([], host.events[-1]['changed'])

    def test_infrastructure_unavailable_precedes_source_execution_and_database_creation(self):
        facts = self.facts()
        facts['test_result']['semantic_assertion_reached'] = False
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            host = Host(root, initialize(root, facts))
            before = set(root.rglob('*'))
            result = host.call('probe', {'name': 'semantic'})
            self.assertEqual({'exit': 1, 'cause': 'storage service unavailable',
                              'semantic_assertion_reached': False}, result)
            self.assertEqual(before, set(root.rglob('*')))
            self.assertEqual([], host.events[-1]['changed'])


if __name__ == '__main__':
    unittest.main()
