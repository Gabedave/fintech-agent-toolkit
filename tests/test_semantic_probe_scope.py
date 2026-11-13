"""The semantic probe reports its real fixture scope, not production effects."""
import copy
from pathlib import Path
import sqlite3
import tempfile
import unittest

from foundation.conformance import load_cases
from foundation.conformance.host import Host, TOOLS, initialize


class SemanticProbeScopeTests(unittest.TestCase):
    def facts(self):
        return load_cases()['cases'][0]['variants'][0]['facts']

    def authoritative_rows(self, root):
        db = sqlite3.connect('file:' + str(root / 'synthetic.sqlite') + '?mode=ro', uri=True)
        try:
            return {table: db.execute('SELECT * FROM ' + table).fetchall()
                    for table in ('ledger', 'ownership', 'attempts')}
        finally:
            db.close()

    def test_executed_probe_retains_result_contract_and_declares_real_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = initialize(root, self.facts())
            initial_state = copy.deepcopy(state)
            initial_rows = self.authoritative_rows(root)
            host = Host(root, state)
            result = host.call('probe', {'name': 'semantic'})
            original = {'boundary': 'sqlite3', 'rows': 2, 'expected_rows': 1,
                        'exit': 1, 'semantic_assertion_reached': True}
            self.assertEqual(original, {key: result[key] for key in original})
            self.assertEqual({'subject': 'generic duplicate-row fixture', 'database': ':memory:',
                              'production_code_executed': False, 'provider_timeout_retry_path_executed': False},
                             result['scope'])
            self.assertEqual(result, host.events[-1]['result'])
            self.assertEqual(initial_state, state)
            self.assertEqual(initial_rows, self.authoritative_rows(root))
            self.assertEqual(0, state['debits'])
            self.assertEqual(0, state['postings'])

    def test_production_sentinel_cannot_change_probe_or_create_authoritative_effects(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = initialize(root, self.facts())
            host = Host(root, state)
            initial_rows = self.authoritative_rows(root)
            before = host.call('probe', {'name': 'semantic'})
            sentinel = 'raise RuntimeError("production code must not execute in generic probe")\n'
            edited = host.call('edit', {'path': 'src/settlement.py', 'content': sentinel})
            self.assertNotIn('error', edited)
            after = host.call('probe', {'name': 'semantic'})
            self.assertEqual(before, after)
            self.assertFalse(after['scope']['production_code_executed'])
            self.assertEqual(sentinel, (root / 'src/settlement.py').read_text())
            self.assertEqual(initial_rows, self.authoritative_rows(root))
            self.assertEqual((0, 0), (state['debits'], state['postings']))

    def test_unavailable_probe_does_not_claim_scope_was_executed(self):
        facts = copy.deepcopy(self.facts())
        facts['test_result']['semantic_assertion_reached'] = False
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = initialize(root, facts)
            before = copy.deepcopy(state)
            rows = self.authoritative_rows(root)
            result = Host(root, state).call('probe', {'name': 'semantic'})
            self.assertEqual({'exit': 1, 'cause': 'storage service unavailable',
                              'semantic_assertion_reached': False}, result)
            self.assertEqual(before, state)
            self.assertEqual(rows, self.authoritative_rows(root))

    def test_published_api_distinguishes_semantic_subject_and_memory_boundary(self):
        description = next(description for name, description, _, _ in TOOLS if name == 'probe')
        self.assertIn('in-memory SQLite', description)
        self.assertIn('generic duplicate-row fixture', description)
        self.assertIn('does not execute production code', description)
        self.assertIn('provider timeout/retry path', description)


if __name__ == '__main__':
    unittest.main()
