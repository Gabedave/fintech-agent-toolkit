"""Frozen observed-action evaluator controls; no canned trace is model compliance."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from foundation.conformance import load_cases, score, sensitivity
from foundation.conformance.controls import control_observation
from foundation.conformance.evaluator import CASES_SHA256, FORBIDDEN_MUTATIONS, STATE_MUTATIONS
from foundation.conformance.host import Host, initialize, files, executable_controls
from foundation.conformance.runner import prompt_for, safe_env, verify_stream, stream_process

ROOT = Path(__file__).resolve().parents[1]


class ObservedConformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_cases()

    def pair(self, case=0, variant=0):
        c = self.data['cases'][case]
        return (c, c['variants'][variant])

    def control(self, tmp, case=0, variant=0):
        c, v = self.pair(case, variant)
        return (c, v, control_observation(c, v, Path(tmp)))

    def test_corpus_is_exact_frozen_twelve_families_47_variants(self):
        self.assertEqual(12, len(self.data['cases']))
        self.assertEqual(47, sum((len(c['variants']) for c in self.data['cases'])))
        self.assertEqual(3, len(self.data['profiles']))
        actual = hashlib.sha256(json.dumps(self.data['cases'], sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
        self.assertEqual(CASES_SHA256, actual)

    def test_host_controls_do_not_mutate_the_frozen_oracle(self):
        original = copy.deepcopy(self.data)
        for c in self.data['cases']:
            for v in c['variants']:
                with tempfile.TemporaryDirectory() as tmp:
                    control_observation(c, v, Path(tmp))
        self.assertEqual(original, self.data)

    def test_installed_fresh_task_readback_order_is_measured(self):
        with tempfile.TemporaryDirectory() as tmp:
            c, v, o = self.control(tmp, 4, 1)
            o['identity']['installed_at_ns'] = o['process']['started_at_ns'] + 1
            result = score(c, v, o)
            self.assertIn(
                'invalid chronology: isolated_plugin_installed < new_task_started < loaded_identity_readback',
                result['errors']
            )

    def test_fixture_change_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'cases.json'
            p.write_text(json.dumps(self.data) + ' ')
            with self.assertRaisesRegex(ValueError, 'fixture bytes'):
                load_cases(p)

    def test_claims_without_operations_never_pass(self):
        for c in self.data['cases']:
            for v in c['variants']:
                with self.subTest(case=c['id'], variant=v['id']):
                    r = score(
                        c,
                        v,
                        {
                            'events': [],
                            'final_text': '\n'.join(v['required_observed_events']),
                            'initial': {},
                            'final': {}
                        }
                    )
                    self.assertNotEqual('pass', r['status'])
                    self.assertFalse(r['model_compliance'])

    def test_sensitivity_accepts_controls_rejects_every_required_forbidden_order_state(self):
        r = sensitivity(self.data)
        self.assertEqual('pass', r['status'], r['failures'])
        self.assertEqual(47, r['variants'])
        self.assertFalse(r['model_compliance'])
        self.assertEqual(
            set((p for c in self.data['cases'] for v in c['variants'] for p in v['forbidden_observed_events'])),
            set(FORBIDDEN_MUTATIONS)
        )
        self.assertEqual(
            set((p for c in self.data['cases'] for v in c['variants'] for p in v['final_state_assertions'])),
            set(STATE_MUTATIONS)
        )

    def test_all_profiles_use_the_same_complete_corpus(self):
        for profile in self.data['profiles']:
            with self.subTest(profile=profile):
                count = 0
                for c in self.data['cases']:
                    for v in c['variants']:
                        with tempfile.TemporaryDirectory() as tmp:
                            o = control_observation(c, v, Path(tmp))
                            r = score(c, v, o)
                            self.assertEqual('pass', r['status'], r)
                            self.assertFalse(r['model_compliance'])
                            count += 1
                self.assertEqual(47, count)

    def test_prompts_exclude_answer_labels_and_oracle_predicates(self):
        profile = {'router': 'sample-mode'}
        for c in self.data['cases']:
            for v in c['variants']:
                p = prompt_for(c, v, profile)
                self.assertNotIn(v['id'], p)
                if v['expected_disposition'] not in json.dumps(v['facts']) + c['task']:
                    self.assertNotIn(v['expected_disposition'], p)
                for key in (
                    'expected_disposition',
                    'required_observed_events',
                    'forbidden_observed_events',
                    'final_state_assertions',
                    'required_order',
                    """independent_invariant"""
                ):
                    self.assertNotIn(key, p)

    def test_implicit_prompt_does_not_name_router_or_skill_path(self):
        c, v = self.pair()
        p = prompt_for(c, v, {'router': 'unique-router-name'}, True)
        self.assertNotIn('unique-router-name', p)
        self.assertNotIn('SKILL.md', p)

    def test_disposable_environment_does_not_inherit_provider_keys_or_real_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            e = safe_env(Path(tmp))
            self.assertEqual(tmp, e['HOME'])
            self.assertEqual(tmp, e['CODEX_HOME'])
            self.assertEqual({'PATH', 'HOME', 'CODEX_HOME', 'TMPDIR', 'LANG', 'PYTHONDONTWRITEBYTECODE'}, set(e))

    def test_mcp_reader_limits_to_installed_candidate_and_reads_real_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            installed = root / 'installed'
            installed.mkdir()
            (installed / 'SKILL.md').write_text('native skill body')
            state = initialize(root / 'workspace', {}, {'router_path': 'SKILL.md'})
            h = Host(root / 'workspace', state, installed=installed)
            read = h.call('candidate_read', {'path': 'SKILL.md'})
            self.assertEqual('native skill body', read['content'])
            self.assertEqual(hashlib.sha256(b'native skill body').hexdigest(), read['sha256'])
            self.assertTrue(read['loaded_router'])
            (root / 'outside').write_text('observer private')
            (installed / 'escape').symlink_to(root / 'outside')
            self.assertIn('error', h.call('candidate_read', {'path': '../outside'}))
            self.assertIn('error', h.call('candidate_read', {'path': 'escape'}))

    def test_mcp_process_records_actual_tool_and_file_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / 'workspace'
            state = initialize(workspace, {})
            sp = root / 'state.json'
            sp.write_text(json.dumps(state))
            jp = root / 'journal.jsonl'
            cp = root / 'config.json'
            cp.write_text(json.dumps({'workspace': str(workspace), 'state': str(sp), 'journal': str(jp)}))
            calls=[{'jsonrpc':'2.0','id':1,'method':'initialize'}, {'jsonrpc':'2.0','id':2,'method':'tools/list'},
                   {
                       'jsonrpc':'2.0',
                       'id':3,
                       'method':'tools/call',
                       'params':{
                           'name':'edit',
                           'arguments':{'path':'src/settlement.py','content':'changed actual bytes'}
                       }
                   }]
            p = subprocess.run(
                [sys.executable, str(ROOT / 'foundation/conformance/host.py'), str(cp)],
                input='\n'.join((json.dumps(c) for c in calls)) + '\n',
                text=True,
                capture_output=True,
                timeout = 10
            )
            self.assertEqual(0, p.returncode, p.stderr)
            result = [json.loads(line) for line in p.stdout.splitlines()]
            self.assertEqual(3, len(result))
            event = json.loads(jp.read_text())
            self.assertEqual(['src/settlement.py'], event['changed'])
            self.assertEqual('changed actual bytes', (workspace / 'src/settlement.py').read_text())

    def test_actual_provenance_cannot_be_forged_by_setting_a_boolean(self):
        with tempfile.TemporaryDirectory() as tmp:
            c, v, o = self.control(tmp)
            o['process'] = {'kind': 'actual-codex', 'started': True, 'tool_stream_verified': True}
            r = score(c, v, o)
            self.assertEqual('fail', r['status'])
            self.assertIn('missing raw process/tool/state evidence', r['errors'])

    def test_raw_tool_stream_corroboration_rejects_tampered_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            c, v, o = self.control(tmp)
            stream = [{'type': 'item.completed', 'item': {'type': 'mcp_tool_call', 'tool': e['tool'], 'arguments': e['arguments'], 'result': {'content': [{'type': 'text', 'text': json.dumps(e['result'])}]}}} for e in o['events']]
            self.assertTrue(verify_stream(o['events'], stream))
            bad = copy.deepcopy(o['events'])
            bad[0]['result'] = {'invented': 'result'}
            self.assertFalse(verify_stream(bad, stream))
            self.assertFalse(verify_stream(o['events'], []))

    def test_unobserved_file_change_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            c, v, o = self.control(tmp)
            o['final_files']['src/settlement.py'] = 'changed out of band'
            self.assertEqual('fail', score(c, v, o)['status'])

    def test_disk_sqlite_detects_duplicate_defect_and_not_success_stub(self):
        with tempfile.TemporaryDirectory() as tmp:
            c, v, o = self.control(tmp, 2, 1)
            e = next((e for e in o['events'] if e['arguments'].get('name') == 'storage'))
            self.assertEqual(1, e['result']['rows'])
            self.assertEqual(2, e['result']['seeded_rows'])
            self.assertTrue(e['result']['seeded_detected'])
            self.assertTrue((Path(tmp) / 'storage.sqlite').is_file())
            e['result'] = {'exit': 0, 'stub': 'success'}
            self.assertEqual('fail', score(c, v, o)['status'])

    def test_five_independent_sql_controls_and_broken_variants(self):
        r = executable_controls()
        self.assertEqual(5, r['passing_controls'])
        self.assertEqual(5, r['detected_variants'])
        self.assertEqual(
            {'rejection', 'ambiguity', 'replay', 'ownership', 'identity'},
            {r['name'] for r in r['executed_controls']}
        )
        for row in r['executed_controls']:
            self.assertTrue(row['control']['passes'])
            self.assertFalse(row['seeded']['passes'])

    def test_two_competing_transactions_have_one_owner_and_no_losing_partial_effect(self):
        with tempfile.TemporaryDirectory() as tmp:
            c, v, o = self.control(tmp, 8, 5)
            r = o['events'][-1]['result']
            self.assertEqual([None, None], r['initial_reads'])
            self.assertEqual([['worker-alpha', 1], ['worker-beta', 0]], r['claims'])
            self.assertEqual([], r['losing_partial_rows'])
            self.assertEqual(1, len(r['ledger']))

    def test_unknown_retry_is_observed_even_when_other_evidence_is_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            c, v, o = self.control(tmp, 7, 0)
            h = Host(Path(tmp), o['final'])
            e = h.call('finance', {'action': 'retry'})
            event = h.events[0]
            event['seq'] = len(o['events']) + 1
            o['events'].append(event)
            o['final'] = h.state
            o['final_files'] = files(Path(tmp))
            r = score(c, v, o)
            self.assertEqual('fail', r['status'])
            self.assertIn('forbidden attempt/claim: provider_debit_created(new key)', r['errors'])

    def test_unavailable_storage_is_not_semantic_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            c, v, o = self.control(tmp, 0, 2)
            self.assertFalse(o['events'][0]['result']['semantic_assertion_reached'])
            self.assertEqual('pass', score(c, v, o)['status'])
            o['final_text'] = 'A semantic failure occurred.'
            self.assertEqual('fail', score(c, v, o)['status'])

    def test_grounded_reporting_accepts_paraphrases(self):
        variants=[(0,2,'blocker','Database is down; semantic evidence is not available yet.'),
                  (3,0,'blocker','The required aggregate result is absent.'),
                  (3,5,'blocker','The results refer to an outdated revision.'),
                  (5,3,'finding','The attachment has no screenshot; other required fields are present.'),
                  (5,4,'finding','The attachment lacks a hosted link.'),
                  (5,5,'finding','The attachment has no commit identifier.'),
                  (5,6,'finding','The attachment lacks a descriptive caption.'),
                  (5,7,'finding','No visual rendering verification is available.'),
                  (5,8,'finding','The attachment has no access verification.')]
        for ci, vi, kind, text in variants:
            with self.subTest(case=ci, variant=vi), tempfile.TemporaryDirectory() as tmp:
                c, v, o = self.control(tmp, ci, vi)
                notes = [e for e in o['events'] if e['tool'] == 'record' and e['arguments']['category'] == kind]
                self.assertTrue(notes)
                notes[-1]['arguments']['text'] = text
                notes[-1]['result']['recorded']['text'] = text
                self.assertEqual('pass', score(c, v, o)['status'], score(c, v, o))

    def test_final_user_report_can_satisfy_reporting_only_when_grounded_by_real_reads(self):
        with tempfile.TemporaryDirectory() as tmp:
            c, v, o = self.control(tmp, 3, 0)
            o['events'] = o['events'][:1]
            o['final_text'] = 'The aggregate result is absent; this blocks readiness.'
            o['final_files'] = o['events'][-1]['after']
            self.assertEqual('pass', score(c, v, o)['status'], score(c, v, o))
            o['events'] = []
            self.assertEqual('fail', score(c, v, o)['status'])

    def test_raw_stderr_is_omitted_and_safely_classified(self):
        with tempfile.TemporaryDirectory() as tmp:
            command = [
                sys.executable,
                '-c',
                """import sys; print("token-secret-auth",file=sys.stderr); print("model: sample-model",file=sys.stderr)"""
            ]
            result = stream_process(command, safe_env(Path(tmp)), tmp, Path(tmp) / 'out', 5)
            self.assertEqual(['model: sample-model'], result['diagnostics']['allowlisted_headers'])
            for p in (Path(tmp) / 'out').rglob('*'):
                if p.is_file():
                    self.assertNotIn('token-secret-auth', p.read_text())
            self.assertFalse((Path(tmp) / 'out/stderr.log').exists())


if __name__ == '__main__':
    unittest.main()
