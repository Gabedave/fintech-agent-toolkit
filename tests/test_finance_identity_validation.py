"""Actual synthetic Host validation/posting; no provider or model calls."""
import copy
from pathlib import Path
import sqlite3
import tempfile
import unittest

from foundation.conformance import load_cases
from foundation.conformance.host import Host, initialize, files, possible_file_effects

CASES = load_cases()['cases']
OWNERSHIP = next(case for case in CASES if case['id'] == '09-ownership-identity')
AUTHORITATIVE = OWNERSHIP['variants'][0]['facts']['authoritative']
REJECTION = next(v['facts'] for case in CASES if case['id'] == '08-provider-ambiguity'
                 for v in case['variants'] if v['id'] == 'compliant-definitive-rejection')


class FinanceIdentityValidationTests(unittest.TestCase):
    def run_call(self, facts, arguments, action, *, malformed_authority=False):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            # Invalid authoritative records are injected into an otherwise real
            # initialized fixture so initialization errors cannot mask validate.
            state = initialize(root, {} if malformed_authority else facts)
            if malformed_authority:
                state['facts'] = copy.deepcopy(facts)
            host = Host(root, state, journal=root.parent / (root.name + '-events.jsonl'))
            self.addCleanup(host.journal.unlink, missing_ok=True)
            before = files(root)
            result = host.call('finance', dict(arguments, action=action))
            with sqlite3.connect(root / 'synthetic.sqlite') as db:
                ledger = db.execute('SELECT operation, amount FROM ledger').fetchall()
            return result, before, files(root), ledger, copy.deepcopy(state), host.events

    def assert_rejected_without_effect(self, facts, arguments, action, **kwargs):
        result, before, after, ledger, state, events = self.run_call(facts, arguments, action, **kwargs)
        self.assertNotEqual({'validated': True}, result, result)
        self.assertTrue(any(key in result for key in ('error', 'rejected_fields', 'rejected_owner')), result)
        self.assertEqual(before, after, result)
        self.assertEqual([], ledger)
        self.assertEqual(0, state['postings'])
        self.assertEqual([], events[0]['changed'])
        self.assertNotIn('synthetic.sqlite', possible_file_effects('finance', dict(arguments, action=action), facts))
        return result

    def test_actual_rejection_fixture_aliases_cannot_validate_or_post_without_authority(self):
        self.assertNotIn('authoritative', REJECTION)
        attempts = [{}, {'identity': {}}] + [{'identity': {alias: 'op-101'}}
                    for alias in ('id', 'operation', 'provider_operation_id', 'key', 'operation_id')]
        for arguments in attempts:
            for action in ('validate', 'post'):
                with self.subTest(arguments=arguments, action=action):
                    self.assert_rejected_without_effect(REJECTION, arguments, action)

    def test_missing_empty_partial_and_malformed_authority_never_matches_itself(self):
        invalid = [None, [], {}, dict.fromkeys(AUTHORITATIVE)]
        for key, value in AUTHORITATIVE.items():
            absent = copy.deepcopy(AUTHORITATIVE); del absent[key]; invalid.append(absent)
            for bad in ([None, '', 1] if isinstance(value, str) else [None, True, float(value), str(value)]):
                malformed = copy.deepcopy(AUTHORITATIVE); malformed[key] = bad; invalid.append(malformed)
        for authority in invalid:
            for action in ('validate', 'post'):
                with self.subTest(authority=authority, action=action):
                    facts = {'authoritative': authority}
                    self.assert_rejected_without_effect(facts, {'identity': copy.deepcopy(authority)}, action,
                                                        malformed_authority=True)

    def test_complete_explicit_identity_validates_without_effect_and_posts_once(self):
        facts = {'authoritative': copy.deepcopy(AUTHORITATIVE)}
        identity = {key: AUTHORITATIVE[key] for key in ('operation_id', 'attempt', 'tenant', 'amount_minor', 'currency')}
        args = {'identity': identity, 'actor': AUTHORITATIVE['owner'], 'fence': AUTHORITATIVE['fence']}
        result, before, after, ledger, state, _ = self.run_call(facts, args, 'validate')
        self.assertEqual({'validated': True}, result)
        self.assertEqual(before, after)
        self.assertEqual([], ledger)
        result, before, after, ledger, state, _ = self.run_call(facts, args, 'post')
        self.assertEqual([(AUTHORITATIVE['operation_id'], AUTHORITATIVE['amount_minor'])], ledger)
        self.assertEqual(1, result['postings'])
        self.assertEqual(1, state['postings'])
        self.assertNotEqual(before['synthetic.sqlite'], after['synthetic.sqlite'])
        self.assertIn('synthetic.sqlite', possible_file_effects('finance', dict(args, action='post'), facts))
        # Preserve the existing default identity/actor/fence behavior when real
        # complete authority exists; no newly invented request fields required.
        self.assertEqual({'validated': True}, self.run_call(facts, {}, 'validate')[0])

    def test_original_seeded_identity_and_owner_mismatches_keep_exact_rejections(self):
        for variant in OWNERSHIP['variants']:
            if 'authoritative' not in variant['facts']:
                continue
            for action in ('validate', 'post'):
                with self.subTest(variant=variant['id'], action=action):
                    result = self.assert_rejected_without_effect(variant['facts'], {}, action)
                    if variant['id'] == 'unsafe-stale-owner':
                        self.assertEqual({'rejected_owner': 'worker-beta'}, result)
                    else:
                        self.assertEqual({'rejected_fields': [variant['id'].removeprefix('unsafe-mismatch-')]}, result)

    def test_empty_alias_and_ill_typed_presented_identity_cannot_match_valid_authority(self):
        facts = {'authoritative': copy.deepcopy(AUTHORITATIVE)}
        inputs = [None, [], {}, {'id': AUTHORITATIVE['operation_id']}]
        for key in ('operation_id', 'attempt', 'tenant', 'amount_minor', 'currency'):
            changed = copy.deepcopy(AUTHORITATIVE)
            changed[key] = float(changed[key]) if type(changed[key]) is int else None
            inputs.append(changed)
        for identity in inputs:
            for action in ('validate', 'post'):
                with self.subTest(identity=identity, action=action):
                    self.assert_rejected_without_effect(facts, {'identity': identity}, action)
        for args in ({'actor': None}, {'actor': ''}, {'actor': 'worker-beta'},
                     {'fence': None}, {'fence': True}, {'fence': float(AUTHORITATIVE['fence'])}, {'fence': 11}):
            for action in ('validate', 'post'):
                with self.subTest(args=args, action=action):
                    self.assert_rejected_without_effect(facts, args, action)


if __name__ == '__main__':
    unittest.main()
