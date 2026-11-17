"""Optional passive MCP startup evidence, never model visibility or admission."""
import hashlib
import json
import os
from pathlib import Path
import time

METHODS = ('initialize', 'tools/list')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def binding(config_raw, host_raw):
    config = json.loads(config_raw)
    return {'config_sha256': sha(config_raw), 'host_source_sha256': sha(host_raw),
            'diagnostic_source_sha256': sha(Path(__file__).read_bytes()),
            'run_identity_sha256': sha(canonical(config.get('run_identity'))),
            'configured_command_sha256': config['handshake_diagnostics']['command_sha256']}


def request_token(ident):
    try:
        return sha(canonical(ident))
    except (TypeError, ValueError):
        return None


class HandshakeDiagnostics:
    def __init__(self, config_raw, host_raw):
        config = json.loads(config_raw)
        self.path = Path(config['handshake_diagnostics']['path'])
        self.sequence, self.write_failures = 0, 0
        self.session = str(os.getpid()) + ':' + str(time.monotonic_ns())
        self._append('host_started', pid=os.getpid(), binding=binding(config_raw, host_raw))

    def _append(self, event, **fields):
        self.sequence += 1
        row = dict(schema_version=1, session=self.session, sequence=self.sequence,
                   event=event, monotonic_ns=time.monotonic_ns(),
                   write_failures_before=self.write_failures, **fields)
        try:
            with self.path.open('a', encoding='utf-8') as stream:
                stream.write(canonical(row).decode() + '\n')
                stream.flush()
                os.fsync(stream.fileno())
        except (OSError, ValueError, TypeError):
            # A later successful row reports both the counter and sequence gap.
            # If none follows, the observer retains missing/partial diagnostics.
            self.write_failures += 1

    def request(self, method, ident):
        if method in METHODS:
            self._append('request_received', method=method,
                         request_id_sha256=request_token(ident), response_expected=ident is not None)

    def response(self, method, ident, result, write_started_ns):
        if method not in METHODS:
            return
        fields = {'method': method, 'request_id_sha256': request_token(ident),
                  'write_started_ns': write_started_ns}
        if method == 'initialize':
            fields.update(protocol_version=result['protocolVersion'], capabilities_sha256=sha(canonical(result['capabilities'])))
        else:
            fields.update(catalog_sha256=sha(canonical(result['tools'])),
                          tools=[{'name': tool['name'], 'input_schema_sha256': sha(canonical(tool['inputSchema']))}
                                 for tool in result['tools']])
        self._append('response_flushed', **fields)

    def error(self, method, ident, error):
        if method in METHODS or method is None:
            self._append('input_or_response_error', method=method if method in METHODS else None,
                         request_id_sha256=request_token(ident), error_class=type(error).__name__)

    def finish(self):
        self._append('host_eof')


def snapshot(source, destination, expected_binding):
    """Retain one actual byte prefix; diagnostics never change scoring/retries."""
    result = {'status': 'unavailable', 'model_visibility_proved': False, 'gaps': [],
              'snapshot_started_ns': time.monotonic_ns(), 'host_eof_observed': False,
              'initialize_response_observed': False, 'tools_list_response_observed': False,
              'source_path': str(source), 'expected_binding': expected_binding}
    try:
        raw = Path(source).read_bytes()
        with Path(destination).open('xb') as stream:
            stream.write(raw)
        result.update(status='retained', path=str(destination), sha256=sha(raw), size=len(raw))
    except OSError as error:
        result['gaps'].append('handshake sidecar unavailable: ' + type(error).__name__)
        result['snapshot_finished_ns'] = time.monotonic_ns()
        return result
    sessions = {}
    if raw and not raw.endswith(b'\n'):
        result['gaps'].append('unterminated diagnostic row')
    for number, line in enumerate(raw.splitlines(), 1):
        try:
            row = json.loads(line)
            session, sequence, timestamp = row['session'], row['sequence'], row['monotonic_ns']
            if row['schema_version'] != 1 or type(sequence) is not int or type(timestamp) is not int:
                raise ValueError('unsupported diagnostic row')
            state = sessions.setdefault(session, {'sequence': 0, 'timestamp': 0, 'started': False, 'eof': False, 'pending': []})
            if sequence != state['sequence'] + 1 or timestamp < state['timestamp'] or state['eof']:
                result['gaps'].append('diagnostic sequence/time gap at line ' + str(number))
            state.update(sequence=sequence, timestamp=timestamp)
            if row.get('write_failures_before'):
                result['gaps'].append('host reported diagnostic write failure')
            event = row['event']
            key = (row.get('method'), row.get('request_id_sha256'))
            if event == 'host_started':
                if state['started'] or row.get('binding') != expected_binding:
                    result['gaps'].append('host diagnostic binding mismatch')
                state['started'] = True
            elif not state['started']:
                result['gaps'].append('host start not observed')
            elif event == 'request_received' and row.get('response_expected'):
                state['pending'].append(key)
            elif event == 'response_flushed':
                if key not in state['pending'] or not (type(row.get('write_started_ns')) is int and row['write_started_ns'] <= timestamp):
                    result['gaps'].append('uncorroborated handshake response')
                else:
                    state['pending'].remove(key)
                    if key[0] == 'initialize':
                        result['initialize_response_observed'] = True
                    elif key[0] == 'tools/list':
                        result['tools_list_response_observed'] = True
            elif event == 'input_or_response_error':
                result['gaps'].append('host reported input/response error')
            elif event == 'host_eof':
                state['eof'] = True
        except (ValueError, TypeError, KeyError):
            result['gaps'].append('malformed diagnostic row ' + str(number))
    result['host_eof_observed'] = bool(sessions) and all(s['eof'] for s in sessions.values())
    if not result['host_eof_observed']:
        result['gaps'].append('host EOF not observed')
    if any(s['pending'] for s in sessions.values()):
        result['gaps'].append('handshake response flush not observed')
    for field, method in (('initialize_response_observed', 'initialize'), ('tools_list_response_observed', 'tools/list')):
        if not result[field]:
            result['gaps'].append(method + ' response flush not observed')
    result['gaps'] = sorted(set(result['gaps']))
    result['snapshot_finished_ns'] = time.monotonic_ns()
    return result
