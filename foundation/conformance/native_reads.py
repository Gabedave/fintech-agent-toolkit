"""Strict native read/report evidence subset, not an original-conformance scorer.

Custody and source manifests are supplied by a trusted independent collector.
Hashes detect inconsistency, not fabrication by that collector. This module never
executes commands, consults live paths, creates host journals or judges report meaning.
"""
import hashlib
import json
from pathlib import PurePosixPath
import shlex


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical_path(value):
    return (isinstance(value, str) and value.startswith('/') and not value.startswith('//')
            and '..' not in PurePosixPath(value).parts
            and str(PurePosixPath(value)) == value)


def cat_path(command):
    """Accept a single literal cat invocation; no expansion, chaining or flags."""
    if not isinstance(command, str) or any(c in command for c in '\n\r;$`|&<>()*?[]{}!\\'):
        return None
    try:
        argv = shlex.split(command)
        if len(argv) == 3 and argv[:2] in (['/bin/zsh', '-lc'], ['/bin/sh', '-c']):
            argv = shlex.split(argv[2])
        if argv and argv[0] in ('cat', '/bin/cat', '/usr/bin/cat'):
            args = argv[1:]
            if args[:1] == ['--']:
                args = args[1:]
            if len(args) == 1 and canonical_path(args[0]):
                return args[0]
    except ValueError:
        pass
    return None


def normalize(raw, sources, custody):
    """Reconcile native capture with a caller-bound full-file index.

    sources[path] = {text, sha256}; custody supplies independently retained raw
    hash/thread/exit/full-capture and source-before/after hashes. A verified subset
    is conditional on authentic complete custody; it grants no origin admission.
    """
    errors, attempts, reads, reports, retained = [], [], [], [], []
    result = {'schema_version': 1, 'kind': 'native-read-report-subset',
              'errors': errors, 'attempts': attempts, 'reads': reads,
              'reports': reports, 'raw_events': retained,
              'conformance_pass': False, 'semantic_witnesses': None,
              'origin_authenticated': False}
    if not isinstance(raw, bytes):
        errors.append('raw capture must be bytes')
        return dict(result, status='rejected')
    result['raw_sha256'] = sha(raw)
    if not isinstance(custody, dict) or not isinstance(sources, dict) or not sources:
        errors.append('missing collector custody/source index')
        return dict(result, status='rejected')
    if (custody.get('raw_sha256') != sha(raw) or custody.get('process_exit') != 0
            or type(custody.get('process_exit')) is not int
            or custody.get('capture_complete') is not True or custody.get('gaps') != []):
        errors.append('capture hash/exit/completeness mismatch')
    expected, safe_sources = {}, {}
    for path, record in sources.items():
        if (not canonical_path(path) or not isinstance(record, dict)
                or not isinstance(record.get('text'), str)):
            errors.append('invalid source index')
            continue
        try:
            source_bytes = record['text'].encode('utf-8')
        except UnicodeError:
            errors.append('invalid source encoding')
            continue
        if record.get('sha256') != sha(source_bytes):
            errors.append('source bytes/hash mismatch: ' + path)
            continue
        expected[path] = record.get('sha256')
        safe_sources[path] = record
    sources = safe_sources
    if custody.get('source_before') != expected or custody.get('source_after') != expected:
        errors.append('source inventory changed or incomplete')
    if not raw.endswith(b'\n'):
        errors.append('unterminated raw capture')
    pending, seen, lifecycle, thread, phase, offset = {}, set(), {}, None, 'before-thread', 0
    for line_number, line in enumerate(raw.splitlines(keepends=True), 1):
        span = {'line': line_number, 'byte_start': offset, 'byte_end': offset + len(line)}
        offset += len(line)
        try:
            event = json.loads(line.decode('utf-8'), object_pairs_hook=_unique)
            if not isinstance(event, dict):
                raise ValueError('event is not an object')
        except (ValueError, UnicodeError):
            errors.append('malformed raw event at line ' + str(line_number))
            retained.append(dict(span, malformed_utf8_hex=line.hex()))
            continue
        retained.append(dict(span, event=event))
        kind = event.get('type')
        if kind == 'thread.started':
            if phase != 'before-thread' or event.get('thread_id') != custody.get('thread_id'):
                errors.append('thread identity/order mismatch')
            thread, phase = event.get('thread_id'), 'before-turn'
        elif kind == 'turn.started':
            if phase != 'before-turn':
                errors.append('turn start order mismatch')
            phase = 'turn'
        elif kind == 'turn.completed':
            if phase != 'turn' or pending:
                errors.append('turn completed with missing/out-of-order operations')
            phase = 'complete'
        elif kind in ('item.started', 'item.completed'):
            if phase != 'turn':
                errors.append('item outside active turn')
            item = event.get('item')
            if not isinstance(item, dict):
                errors.append('malformed item')
                continue
            ident, typ = item.get('id'), item.get('type')
            if not isinstance(ident, str) or not ident:
                errors.append('missing item identity')
                continue
            previous = lifecycle.get(ident)
            if kind == 'item.started':
                if typ != 'command_execution':
                    errors.append('unsupported item start: ' + ident)
                if previous is not None:
                    errors.append('duplicate/reused item start: ' + ident)
                lifecycle[ident] = (typ, 'started')
            else:
                if ((typ == 'command_execution' and previous != (typ, 'started'))
                        or (typ != 'command_execution' and previous is not None)):
                    errors.append('duplicate/cross-type item completion: ' + ident)
                lifecycle[ident] = (typ, 'completed')
            if typ == 'command_execution':
                attempt = dict(span, phase=kind, item=item)
                attempts.append(attempt)  # ID-bearing attempts; unusable IDs remain in raw_events.
                path = cat_path(item.get('command'))
                if path is None or path not in sources:
                    errors.append('unsupported/unbound command: ' + ident)
                if kind == 'item.started':
                    if ident in pending or ident in seen or pending:
                        errors.append('duplicate/concurrent command chronology')
                    if (item.get('status') != 'in_progress'
                            or 'exit_code' not in item or item['exit_code'] is not None
                            or item.get('aggregated_output') != ''
                            or ('truncated' in item and item['truncated'] is not False)):
                        errors.append('invalid/contradictory/truncated command start: ' + ident)
                    pending[ident] = (item.get('command'), line_number)
                else:
                    started = pending.pop(ident, None)
                    if (started is None or started[0] != item.get('command') or ident in seen):
                        errors.append('missing/mismatched command start: ' + ident)
                    seen.add(ident)
                    if (item.get('status') != 'completed' or type(item.get('exit_code')) is not int
                            or item.get('exit_code') != 0
                            or ('truncated' in item and item['truncated'] is not False)):
                        errors.append('denied/failed/truncated command: ' + ident)
                    elif path in sources and item.get('aggregated_output') == sources[path].get('text'):
                        reads.append(dict(span, item_id=ident, path=path,
                                          source_sha256=sources[path]['sha256'],
                                          start_line=started[1] if started else None, exit_code=0))
                    else:
                        errors.append('partial/mismatched file output: ' + ident)
            elif typ == 'agent_message' and kind == 'item.completed':
                if ident in seen or not isinstance(item.get('text'), str) or pending:
                    errors.append('invalid/overlapping report: ' + ident)
                seen.add(ident)
                text = item.get('text')
                if isinstance(text, str):
                    try:
                        text_hash = sha(text.encode('utf-8'))
                    except UnicodeError:
                        text_hash = None
                        errors.append('invalid report encoding: ' + ident)
                    reports.append(dict(span, item_id=ident, text=text,
                                        text_sha256=text_hash))
            elif typ != 'reasoning':
                errors.append('unsupported native item: ' + str(typ))
        else:
            errors.append('unexpected native event: ' + str(kind))
    if phase != 'complete' or not thread or pending:
        errors.append('incomplete turn/capture chronology')
    if set(r['path'] for r in reads) != set(sources):
        errors.append('required source read missing')
    if not reports:
        errors.append('full user report missing')
    elif reports[-1]['line'] < max((a['line'] for a in attempts), default=0):
        errors.append('final user report precedes read completion')
    # No report claims are converted to operations or semantic witnesses.
    result['unresolved_original_gates'] = [
        'trusted collector/process origin and complete startup capture',
        'launch argv/prompt/candidate/profile/installed closure',
        'qualified selected catalog and one-plugin/disposable installation',
        'independent full-report semantic witnesses and original predicate scoring',
        'parent-owned fixture/state inventories and mutation coverage',
        'effective per-task model binding']
    return dict(result, status='rejected' if errors else 'verified-subset')


def _unique(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('duplicate JSON key')
        value[key] = item
    return value
