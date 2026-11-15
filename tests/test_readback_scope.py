"""Readback identities describe actual fixture producers, not all test effects."""
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from foundation.conformance import load_cases
from foundation.conformance.host import Host, initialize, files


class ReadbackScopeTests(unittest.TestCase):
    def setup_host(self, facts):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        return root, Host(root, initialize(root, facts))

    def readbacks(self, host):
        return {name: copy.deepcopy(host.call('inspect', {'resource': name}))
                for name in ('history', 'provider', 'resources')}

    def assert_backing_scope(self, root, host, values):
        history_source = 'facts.harness_history' if 'harness_history' in host.state['facts'] else 'default: []'
        self.assertEqual(history_source, values['history']['scope']['source'])
        self.assertEqual('supplied records only', values['history']['scope']['coverage'])
        self.assertEqual('state.debits', values['provider']['scope']['sources']['debits'])
        status_source = ('facts.provider_status_readback' if 'provider_status_readback' in host.state['facts']
                         else 'default: {"status":"unknown"}')
        self.assertEqual(status_source, values['provider']['scope']['sources']['status'])
        self.assertEqual('state.recovery', values['provider']['scope']['sources']['recovery'])
        self.assertEqual('current fixture field values', values['provider']['scope']['coverage'])
        self.assertEqual('current fixture field values', values['resources']['scope']['coverage'])
        for key in ('completed', 'waiting', 'queue', 'ledger', 'recovery'):
            self.assertEqual('state.' + key, values['resources']['scope']['sources'][key])
            path = values['resources']['scope']['mirrors'][key]
            self.assertEqual('stores/' + key + '.json', path)
            self.assertEqual(host.state[key], values['resources'][key])
            self.assertEqual(values['resources'][key], json.loads((root / path).read_text()))

    def test_absent_facts_identify_defaults_not_supplied_observations(self):
        root, host = self.setup_host({})
        result = self.readbacks(host)
        self.assertEqual([], result['history']['history'])
        self.assertEqual('default: []', result['history']['scope']['source'])
        self.assertEqual({'status': 'unknown'}, result['provider']['status'])
        self.assertEqual('default: {"status":"unknown"}', result['provider']['scope']['sources']['status'])
        supplied_root, supplied = self.setup_host({'harness_history': [],
                                                   'provider_status_readback': {'status': 'unknown'}})
        explicit = self.readbacks(supplied)
        self.assertEqual(result['history']['history'], explicit['history']['history'])
        self.assertEqual(result['provider']['status'], explicit['provider']['status'])
        self.assertEqual('facts.harness_history', explicit['history']['scope']['source'])
        self.assertEqual('facts.provider_status_readback', explicit['provider']['scope']['sources']['status'])
        self.assert_backing_scope(root, host, result)
        self.assert_backing_scope(supplied_root, supplied, explicit)

    def test_named_semantic_commits_do_not_become_workbench_counter_or_resource_rows(self):
        facts = copy.deepcopy(load_cases()['cases'][0]['variants'][0]['facts'])
        facts['harness_history'] = [{'event': 'supplied-before-run'}]
        root, host = self.setup_host(facts)
        before = self.readbacks(host)
        result = host.call('probe', {'name': 'semantic'})
        self.assertEqual((2, 1), (result['rows'], result['expected_rows']))
        self.assertEqual('semantic.sqlite', result['scope']['database'])
        with sqlite3.connect(root / result['scope']['database']) as db:
            self.assertEqual(2, db.execute('SELECT COUNT(*) FROM debit').fetchone()[0])
        after = self.readbacks(host)
        self.assertEqual(before, after)
        self.assertEqual(0, after['provider']['debits'])
        self.assertEqual([], after['resources']['ledger'])
        self.assertEqual(facts['harness_history'], after['history']['history'])
        self.assert_backing_scope(root, host, after)

    def test_refactor_controls_observe_in_memory_effects_separate_from_readback_stores(self):
        case = load_cases()['cases'][0]
        facts = next(v['facts'] for v in case['variants'] if v['id'] == 'compliant-refactor-control')
        root, host = self.setup_host(facts)
        before = self.readbacks(host)
        result = host.call('probe', {'name': 'controls'})
        self.assertEqual((5, 5), (result['passing_controls'], result['detected_variants']))
        self.assertEqual(':memory:', result['scope']['database'])
        replay = next(row for row in result['executed_controls'] if row['name'] == 'replay')
        self.assertEqual([['op-1']], replay['control']['effects']['ledger'])
        self.assertEqual(before, self.readbacks(host))
        self.assertEqual([], host.call('inspect', {'resource': 'ownership'})['committed_ledger_rows'])
        self.assert_backing_scope(root, host, self.readbacks(host))

    def test_own_fixture_mutations_are_visible_in_the_named_fields_and_mirrors(self):
        root, host = self.setup_host({'provider_debits': 1, 'recovery': ['pending'],
                                     'capacity': 2, 'incoming': 'next', 'queued': ['first']})
        before = self.readbacks(host)
        # These direct local Host calls exercise each field's actual producer;
        # a test does not grant workflow permission to make a production retry.
        retried = host.call('finance', {'action': 'retry'})
        self.assertEqual(2, retried['debits'])
        self.assertTrue(host.call('resources', {'action': 'enqueue'})['accepted'])
        host.call('finance', {'action': 'delete_recovery'})
        after = self.readbacks(host)
        self.assertEqual((1, 2), (before['provider']['debits'], after['provider']['debits']))
        self.assertEqual(['first', 'next'], after['resources']['queue'])
        self.assertEqual([], after['provider']['recovery'])
        self.assertEqual([], after['resources']['recovery'])
        self.assertEqual(before['history'], after['history'])
        self.assertEqual(after['provider'], host.call('finance', {'action': 'query'}))
        self.assert_backing_scope(root, host, after)

    def test_readbacks_preserve_supplied_history_status_and_all_original_values_without_writes(self):
        history = [{'event': 'old-failure', 'observed_at': 'supplied-time'}]
        status = {'status': 'rejected', 'debits': 0, 'note': 'supplied provider observation'}
        facts = {'harness_history': history, 'provider_debits': 8, 'provider_status_readback': status,
                 'completed_transient': [1], 'waiting': [2], 'queued': [3], 'ledger': [4], 'recovery': [5]}
        root, host = self.setup_host(facts)
        original_files = files(root)
        original_state = copy.deepcopy(host.state)
        values = self.readbacks(host)
        legacy = {name: {key: val for key, val in result.items() if key != 'scope'}
                  for name, result in values.items()}
        self.assertEqual({'history': {'history': history},
                          'provider': {'debits': 0, 'status': status, 'recovery': [5]},
                          'resources': {'completed': [1], 'waiting': [2], 'queue': [3], 'ledger': [4], 'recovery': [5]}}, legacy)
        self.assertEqual(original_state, host.state)
        self.assertEqual(original_files, files(root))
        self.assertTrue(all(event['changed'] == [] for event in host.events))
        self.assert_backing_scope(root, host, values)


if __name__ == '__main__':
    unittest.main()
