"""Passive real local MCP handshake diagnostics; no Codex/model invocation."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from foundation.conformance.host import initialize, files

HOST = Path(__file__).resolve().parents[1] / 'foundation/conformance/host.py'
sha = lambda raw: hashlib.sha256(raw).hexdigest()


class HostHandshakeDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workspace = self.root / 'workspace'
        state = initialize(self.workspace, {})
        self.state = self.root / 'state.json'
        self.state.write_text(json.dumps(state))
        self.journal = self.root / 'journal.jsonl'
        self.journal.touch()
        self.sidecar = self.root / 'handshake-live.jsonl'
        self.config = {'workspace': str(self.workspace), 'state': str(self.state),
                       'journal': str(self.journal), 'run_identity': {'run_dir': str(self.root), 'candidate_revision': 'local-control'},
                       'handshake_diagnostics': {'path': str(self.sidecar), 'command_sha256': 'a' * 64}}
        self.config_path = self.root / 'host-config.json'
        self.before = files(self.workspace)
        self.state_before = self.state.read_bytes()

    def launch(self, requests, *, diagnostics=True):
        config = dict(self.config)
        if not diagnostics:
            config.pop('handshake_diagnostics')
        self.config_path.write_text(json.dumps(config))
        raw = ''.join(json.dumps(row) + '\n' for row in requests)
        return subprocess.run([sys.executable, '-B', str(HOST), str(self.config_path)],
                              input=raw, text=True, capture_output=True, timeout=5)

    def unchanged(self):
        self.assertEqual(self.before, files(self.workspace))
        self.assertEqual(self.state_before, self.state.read_bytes())
        self.assertEqual(b'', self.journal.read_bytes())

    def test_actual_initialize_and_catalog_flush_are_retained_without_tool_calls(self):
        requests = [{'jsonrpc': '2.0', 'id': 'private-request-id', 'method': 'initialize',
                     'params': {'clientInfo': {'secret': 'never-retain-client-secret'}}},
                    {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'}]
        process = self.launch(requests)
        self.assertEqual(0, process.returncode, process.stderr)
        responses = [json.loads(line) for line in process.stdout.splitlines()]
        self.assertEqual(2, len(responses))
        self.assertTrue(self.sidecar.is_file(), 'real host wrote no passive handshake sidecar')
        rows = [json.loads(line) for line in self.sidecar.read_text().splitlines()]
        self.assertEqual(['host_started', 'request_received', 'response_flushed',
                          'request_received', 'response_flushed', 'host_eof'], [r['event'] for r in rows])
        self.assertEqual(sha(self.config_path.read_bytes()), rows[0]['binding']['config_sha256'])
        self.assertEqual(sha(HOST.read_bytes()), rows[0]['binding']['host_source_sha256'])
        self.assertEqual('a' * 64, rows[0]['binding']['configured_command_sha256'])
        catalog = responses[1]['result']['tools']
        self.assertEqual([t['name'] for t in catalog], [t['name'] for t in rows[4]['tools']])
        canonical = lambda value: json.dumps(value, sort_keys=True, separators=(',', ':')).encode()
        self.assertEqual(sha(canonical(catalog)), rows[4]['catalog_sha256'])
        self.assertEqual([sha(canonical(t['inputSchema'])) for t in catalog], [t['input_schema_sha256'] for t in rows[4]['tools']])
        self.assertLessEqual(rows[1]['monotonic_ns'], rows[2]['write_started_ns'])
        self.assertLessEqual(rows[2]['write_started_ns'], rows[2]['monotonic_ns'])
        self.assertNotIn('never-retain-client-secret', self.sidecar.read_text())
        self.assertNotIn('private-request-id', self.sidecar.read_text())
        self.unchanged()

    def test_existing_config_without_diagnostics_has_identical_protocol_response(self):
        requests = [{'id': 1, 'method': 'initialize'}, {'id': 2, 'method': 'tools/list'}]
        old = self.launch(requests, diagnostics=False)
        self.assertFalse(self.sidecar.exists())
        new = self.launch(requests)
        self.assertEqual((old.returncode, old.stdout, old.stderr), (new.returncode, new.stdout, new.stderr))
        self.unchanged()

    def test_clean_host_eof_does_not_invent_an_unrequested_handshake(self):
        process = self.launch([])
        self.assertEqual(0, process.returncode)
        self.assertEqual('', process.stdout)
        from foundation.conformance.handshake_diagnostics import binding, snapshot
        result = snapshot(self.sidecar, self.root / 'retained.jsonl', binding(self.config_path.read_bytes(), HOST.read_bytes()))
        self.assertTrue(result['host_eof_observed'])
        self.assertFalse(result['initialize_response_observed'])
        self.assertFalse(result['tools_list_response_observed'])
        self.assertIn('tools/list response flush not observed', result['gaps'])
        self.assertFalse(result['model_visibility_proved'])
        self.unchanged()

    def test_terminated_actual_host_retains_prefix_without_inventing_catalog_or_eof(self):
        self.config_path.write_text(json.dumps(self.config))
        process = subprocess.Popen([sys.executable, '-B', str(HOST), str(self.config_path)],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: process.poll() is None and process.kill())
        process.stdin.write(json.dumps({'id': 1, 'method': 'initialize'}) + '\n'); process.stdin.flush()
        self.assertEqual('2024-11-05', json.loads(process.stdout.readline())['result']['protocolVersion'])
        process.terminate(); process.communicate(timeout=5)
        rows = [json.loads(line) for line in self.sidecar.read_text().splitlines()]
        self.assertEqual('host_started', rows[0]['event'])
        self.assertFalse(any(row['event'] == 'host_eof' or row.get('method') == 'tools/list' for row in rows))
        from foundation.conformance.handshake_diagnostics import snapshot
        result = snapshot(self.sidecar, self.root / 'retained.jsonl', rows[0]['binding'])
        self.assertIn('host EOF not observed', result['gaps'])
        self.assertFalse(result['model_visibility_proved'])
        self.unchanged()

    def test_diagnostic_write_failure_does_not_change_protocol_or_state(self):
        self.sidecar.mkdir()
        process = self.launch([{'id': 1, 'method': 'initialize'}, {'id': 2, 'method': 'tools/list'}])
        self.assertEqual(0, process.returncode, process.stderr)
        self.assertEqual(2, len(process.stdout.splitlines()))
        from foundation.conformance.handshake_diagnostics import snapshot
        result = snapshot(self.sidecar, self.root / 'retained.jsonl', {})
        self.assertEqual('unavailable', result['status'])
        self.assertTrue(result['gaps'])
        self.assertFalse((self.root / 'retained.jsonl').exists())
        self.unchanged()


    def test_actual_append_failure_and_recovery_are_reported_without_protocol_error(self):
        self.config_path.write_text(json.dumps(self.config))
        process = subprocess.Popen([sys.executable, '-B', str(HOST), str(self.config_path)],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: process.poll() is None and process.kill())
        process.stdin.write(json.dumps({'id': 1, 'method': 'initialize'}) + '\n'); process.stdin.flush()
        self.assertIn('result', json.loads(process.stdout.readline()))
        backup = self.root / 'prefix.jsonl'
        self.sidecar.rename(backup); self.sidecar.mkdir()
        process.stdin.write(json.dumps({'id': 2, 'method': 'tools/list'}) + '\n'); process.stdin.flush()
        self.assertIn('tools', json.loads(process.stdout.readline())['result'])
        self.sidecar.rmdir(); backup.rename(self.sidecar)
        output, error = process.communicate(timeout=5)
        self.assertEqual(0, process.returncode, error)
        self.assertEqual('', output)
        from foundation.conformance.handshake_diagnostics import binding, snapshot
        result = snapshot(self.sidecar, self.root / 'retained.jsonl', binding(self.config_path.read_bytes(), HOST.read_bytes()))
        self.assertIn('host reported diagnostic write failure', result['gaps'])
        self.assertFalse(result['model_visibility_proved'])
        self.unchanged()

    def test_malformed_input_retains_only_safe_error_class_and_incomplete_prefix(self):
        self.config_path.write_text(json.dumps(self.config))
        process = subprocess.run([sys.executable, '-B', str(HOST), str(self.config_path)],
                                 input='{"private-client-secret":', text=True, capture_output=True, timeout=5)
        self.assertNotEqual(0, process.returncode)
        raw = self.sidecar.read_bytes()
        self.assertNotIn(b'private-client-secret', raw)
        from foundation.conformance.handshake_diagnostics import binding, snapshot
        result = snapshot(self.sidecar, self.root / 'retained.jsonl', binding(self.config_path.read_bytes(), HOST.read_bytes()))
        self.assertIn('host reported input/response error', result['gaps'])
        self.assertIn('host EOF not observed', result['gaps'])
        self.unchanged()

    def test_snapshot_binds_one_captured_prefix_and_reports_tampering_or_partial_rows(self):
        from unittest import mock
        from foundation.conformance.handshake_diagnostics import binding, snapshot
        self.launch([{'id': 1, 'method': 'initialize'}, {'id': 2, 'method': 'tools/list'}])
        expected = binding(self.config_path.read_bytes(), HOST.read_bytes())
        original = self.sidecar.read_bytes()
        real_read = Path.read_bytes
        reads = []
        def read_once(path):
            raw = real_read(path)
            if path == self.sidecar:
                reads.append(path)
                path.write_bytes(b'{"later-unrelated-prefix":true}\n')
            return raw
        destination = self.root / 'retained.jsonl'
        with mock.patch.object(Path, 'read_bytes', read_once):
            result = snapshot(self.sidecar, destination, expected)
        self.assertEqual([self.sidecar], reads)
        self.assertEqual(original, destination.read_bytes())
        self.assertEqual(sha(original), result['sha256'])
        self.assertEqual([], result['gaps'])
        self.sidecar.write_bytes(original)
        wrong = dict(expected, host_source_sha256='0' * 64)
        result = snapshot(self.sidecar, self.root / 'wrong.jsonl', wrong)
        self.assertIn('host diagnostic binding mismatch', result['gaps'])
        self.sidecar.write_bytes(original + b'{"partial":')
        result = snapshot(self.sidecar, self.root / 'partial.jsonl', expected)
        self.assertTrue(any('malformed diagnostic row' in gap for gap in result['gaps']))
        self.assertFalse(result['model_visibility_proved'])
        self.sidecar.write_bytes(original.rstrip(b'\n'))
        result = snapshot(self.sidecar, self.root / 'missing-newline.jsonl', expected)
        self.assertIn('unterminated diagnostic row', result['gaps'])
        self.unchanged()

    def test_returned_finance_error_is_concrete_mcp_result_not_client_denial(self):
        from foundation.conformance.mcp_results import completion
        from foundation.conformance.runner import verify_stream
        arguments = {'action': 'validate', 'identity': {'id': 'op-101'}}
        process = self.launch([{'id': 1, 'method': 'tools/call',
                                'params': {'name': 'finance', 'arguments': arguments}}])
        self.assertEqual(0, process.returncode, process.stderr)
        response = json.loads(process.stdout)['result']
        self.assertTrue(response['isError'])
        journal = [json.loads(line) for line in self.journal.read_text().splitlines()]
        self.assertEqual(1, len(journal))
        item = {'type': 'mcp_tool_call', 'server': 'workbench', 'tool': 'finance',
                'arguments': arguments, 'result': response, 'error': None}
        values, returned = completion(item)
        self.assertTrue(returned)
        self.assertEqual([journal[0]['result']], values)
        self.assertTrue(verify_stream(journal, [{'type': 'item.completed', 'item': item}]))
        denied = dict(item, result=None, error={'message': 'client approval denied'})
        self.assertEqual(([], False), completion(denied))
        self.assertFalse(verify_stream(journal, [{'type': 'item.completed', 'item': denied}]))
        self.assertEqual(self.before, files(self.workspace))
        self.assertEqual([], journal[0]['changed'])

    def test_diagnostic_helper_source_substitution_breaks_existing_source_closure(self):
        from foundation.conformance.effect_controls import actual, SPECS
        from foundation.conformance.source_binding import validate
        _, _, _, run, _, _ = actual(SPECS[0], self.root / 'helper-substitution')
        observation = json.loads((run / 'observation.json').read_text())
        metadata_path = run / 'metadata.json'
        metadata = json.loads(metadata_path.read_text())
        launch = json.loads((run / 'observer' / metadata['source_launch']['path']).read_text())
        helper = run / 'observer' / launch['sources']['handshake_diagnostics.py']['path']
        self.assertEqual({'purpose': 'controlled-sensitivity'}, validate(observation))
        original = helper.read_bytes()
        helper.write_bytes(original + b'\n# altered retained helper\n')
        self.assertIsNone(validate(observation))
        helper.write_bytes(original)
        metadata['source_files_after']['handshake'] = '0' * 64
        metadata_path.write_text(json.dumps(metadata))
        observation['process']['metadata_sha256'] = sha(metadata_path.read_bytes())
        self.assertIsNone(validate(observation))

    def test_actual_runner_retains_optional_bound_artifact_without_changing_failure(self):
        from foundation.conformance.effect_controls import actual, PROGRAM, SPECS
        from foundation.conformance.source_binding import validate
        from foundation.conformance.claim_review import validate_manifest
        marker = "cfg = json.loads(pathlib.Path(sys.argv[2]).read_text())\n"
        injection = ("import subprocess\n"
                     "subprocess.run([sys.executable, '-B', str(pathlib.Path(sys.argv[1]) / 'foundation/conformance/host.py'), sys.argv[2]], "
                     "input=''.join(json.dumps({'id': n, 'method': m}) + '\\n' for n,m in enumerate(('initialize','tools/list'),1)), "
                     "text=True, capture_output=True, check=True, timeout=5)\n")
        for enabled in (False, True):
            with self.subTest(actual_handshake=enabled):
                program = PROGRAM.replace(marker, marker + injection) if enabled else PROGRAM
                _, _, result, run, _, _ = actual(SPECS[0], self.root / str(enabled), program=program)
                self.assertEqual('fail', result['status'])
                metadata = json.loads((run / 'metadata.json').read_text())
                diagnostic = metadata['handshake_diagnostics']
                observation = json.loads((run / 'observation.json').read_text())
                self.assertEqual({'purpose': 'controlled-sensitivity'}, validate(observation))
                launch = json.loads((run / 'observer' / metadata['source_launch']['path']).read_text())
                self.assertIn('handshake_diagnostics.py', launch['sources'], 'transitive diagnostic helper bytes were not retained')
                helper = launch['sources']['handshake_diagnostics.py']
                self.assertEqual(HOST.with_name('handshake_diagnostics.py').read_bytes(),
                                 (run / 'observer' / helper['path']).read_bytes())
                self.assertEqual(helper['sha256'], metadata['source_files_after']['handshake'])
                manifest = validate_manifest(run / 'raw-input-manifest.json')
                records = [r for r in manifest['artifacts'] if r['role'] == 'host_handshake_diagnostics']
                if enabled:
                    self.assertEqual('retained', diagnostic['status'])
                    self.assertEqual([], diagnostic['gaps'])
                    self.assertEqual(1, len(records))
                    self.assertEqual(diagnostic['sha256'], records[0]['sha256'])
                    self.assertEqual(diagnostic['size'], records[0]['size_bytes'])
                    self.assertEqual(diagnostic['path'], observation['observer_paths']['host_handshake'])
                else:
                    self.assertEqual('unavailable', diagnostic['status'])
                    self.assertTrue(diagnostic['gaps'])
                    self.assertEqual([], records)
                self.assertFalse(diagnostic['model_visibility_proved'])


if __name__ == '__main__':
    unittest.main()
