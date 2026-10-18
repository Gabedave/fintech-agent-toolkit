"""Sealed evidence and caller-pinned independent review, never self-authentication.

The caller must authenticate the external index from actual platform provenance.
This module checks that trust root's exact bindings; JSON cannot prove authorship.
"""
import hashlib
import json
from pathlib import Path

# Public baseline: this is an opaque compatibility-instance ID, not proof of
# private freeze bytes or task/adopter approval. The public file hashes below
# are reproducible. Actual task acceptance verifies external approval separately.
FREEZE_SHA256 = '818402ebe2bd67a195d2d6366c5e9415cd1e8cef7c8a20cef22922138a102676'
RUBRIC_SHA256 = 'cff0963ebce60a91db4f3e351375fd89d67f17d2567534e0496bd64e4af3fffb'
PROTOCOL_SHA256 = 'e9536918cc013e217341bde7817be11645ce804b2708fdf258228d9661ce13eb'
CONTROLS_SHA256 = 'f2d65b62c9577ca6579596729b6ae0e20bddc90ccdfd0dab5e2a3cf0741bcaa0'


def sha256(value):
    return hashlib.sha256(value).hexdigest()


def read_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON key: ' + key)
            result[key] = value
        return result
    return json.loads(Path(path).read_bytes(), object_pairs_hook=pairs)


def fixed_file(name, expected):
    path = Path(__file__).with_name(name)
    if sha256(path.read_bytes()) != expected:
        raise ValueError('fixed claim-review input changed: ' + name)
    return read_json(path)


def rubric():
    return fixed_file('claim-review-rubric-v1.json', RUBRIC_SHA256)


def protocol():
    return fixed_file('claim-review-protocol-v1.json', PROTOCOL_SHA256)



def observed_binding(metadata, prompt_sha256):
    """Single concrete projection of independently captured observed identity."""
    lock = metadata.get('foundation_lock') or {}
    foundation = lock.get('foundation', {})
    from .evaluator import CASES_SHA256
    return {'candidate_revision': metadata['candidate_revision'],
            'candidate_tree_sha256': metadata['candidate_tree_digest'],
            'generated_tree_sha256': lock.get('generated_tree_digest'),
            'installed_tree_sha256': metadata['installed_tree_digest'],
            'profile_sha256': metadata['profile_sha256'],
            'foundation_version': foundation.get('version'),
            'foundation_revision': foundation.get('commit'),
            'foundation_sha256': foundation.get('digest'),
            'contract_sha256': metadata['contract_sha256'], 'oracle_sha256': metadata['fixture_sha256'],
            'cases_semantic_sha256': CASES_SHA256,
            'harness_revision': metadata['harness_revision'], 'harness_sha256': metadata['harness_digest'],
            'effective_model': metadata['effective_model'], 'environment_sha256': metadata['environment_sha256'],
            'prompt_sha256': prompt_sha256}


def assigned_rows(case_id, variant_id):
    for item in rubric()['variant_coverage']:
        if (item['case_id'], item['variant_id']) == (case_id, variant_id):
            return item['claim_rows']
    raise ValueError('unmapped observed case/variant')


def partitions():
    return {entry['predicate_key']: entry for entry in rubric()['entries']}


def artifact(root, artifact_id, role, path):
    root = Path(root).resolve()
    path = Path(path)
    path = path if path.is_absolute() else root / path
    path = path.resolve()
    if root not in path.parents or path.is_symlink():
        raise ValueError('artifact escapes run directory')
    raw = path.read_bytes()
    return {'artifact_id': artifact_id, 'role': role, 'path': path.relative_to(root).as_posix(),
            'sha256': sha256(raw), 'size_bytes': len(raw)}


def _path(root, relative):
    root = Path(root).resolve()
    relative = Path(relative)
    path = root / relative
    if relative.is_absolute() or '..' in relative.parts or path.is_symlink():
        raise ValueError('unsafe artifact path')
    path = path.resolve()
    if root not in path.parents:
        raise ValueError('artifact outside run')
    return path


def report_projection(root, artifacts):
    """Losslessly extract all Codex messages and all actual record notes.

    Decision-only adapters may use raw_process_stream containing plain UTF-8
    instead of JSONL, declared by source_format='text'. There is no host claim.
    """
    rows = []
    stream_notes = []
    for source in artifacts:
        if source['role'] == 'raw_process_stream' and source.get('source_format', 'jsonl') == 'jsonl':
            for number, line in enumerate(_path(root, source['path']).read_bytes().splitlines(), 1):
                value = json.loads(line)
                item = value.get('item', {})
                if value.get('type') == 'item.completed' and item.get('type') == 'mcp_tool_call' and item.get('tool') == 'record':
                    arguments = item.get('arguments', {})
                    arguments = json.loads(arguments) if isinstance(arguments, str) else arguments
                    stream_notes.append((number, arguments))
    for source in artifacts:
        role = source['role']
        if role not in {'raw_process_stream', 'raw_tool_journal', 'raw_decision'}:
            continue
        raw = _path(root, source['path']).read_bytes()
        source_format = source.get('source_format', 'jsonl')
        if source_format == 'text':
            rows.append({'text': raw.decode('utf-8'), 'phase': 'final-message', 'event_seq': None,
                         'category': 'message', 'source_artifact_id': source['artifact_id'],
                         'source_line': None, 'source_field': []})
            continue
        if source_format == 'json':
            values = [(None, json.loads(raw))]
        elif source_format == 'jsonl':
            values = [(number, json.loads(line)) for number, line in enumerate(raw.splitlines(), 1)]
        else:
            raise ValueError('unknown report source format')
        message_rows = []
        for line, value in values:
            item = value.get('item', {})
            if role == 'raw_tool_journal' and value.get('tool') == 'record':
                text = value.get('arguments', {}).get('text')
                if not isinstance(text, str):
                    raise ValueError('record text is not UTF-8 text')
                matches = [number for number, args in stream_notes if args == value['arguments']]
                position = matches[0] if matches else 0
                if matches:
                    stream_notes.remove((position, value['arguments']))
                rows.append({'_position': position, 'text': text, 'phase': 'original-note', 'event_seq': value['seq'],
                             'category': value['arguments'].get('category'),
                             'source_artifact_id': source['artifact_id'], 'source_line': line,
                             'source_field': ['arguments', 'text']})
            elif role == 'raw_process_stream' and value.get('type') == 'item.completed' and item.get('type') == 'agent_message':
                text = item.get('text')
                if not isinstance(text, str):
                    raise ValueError('message text is not UTF-8 text')
                row = {'_position': line or 0, 'text': text, 'phase': 'intermediate-message', 'event_seq': None,
                       'category': 'message', 'source_artifact_id': source['artifact_id'],
                       'source_line': line, 'source_field': ['item', 'text']}
                rows.append(row)
                message_rows.append(row)
            elif role == 'raw_process_stream' and value.get('type') == 'item.completed' and item.get('type') == 'mcp_tool_call' and item.get('tool') == 'record' and item.get('error'):
                arguments = item.get('arguments', {})
                encoded_arguments = isinstance(arguments, str)
                arguments = json.loads(arguments) if encoded_arguments else arguments
                if isinstance(arguments.get('text'), str):
                    rows.append({'_position': line or 0, 'text': arguments['text'],
                                 'phase': 'intermediate-message', 'event_seq': None,
                                 'category': 'denied-record-attempt', 'source_artifact_id': source['artifact_id'],
                                 'source_line': line,
                                 'source_field': ['item', 'arguments'] + (['@json'] if encoded_arguments else []) + ['text']})
            elif role == 'raw_decision':
                # Structured decisions are themselves candidate assertions and
                # are reviewed alongside, never instead of, all visible prose.
                rows.append({'text': raw.decode('utf-8') if source_format == 'json' else raw.splitlines()[line - 1].decode('utf-8'),
                             'phase': 'intermediate-message', 'event_seq': None,
                             'category': 'structured-decision', 'source_artifact_id': source['artifact_id'],
                             'source_line': line, 'source_field': []})
        if message_rows:
            message_rows[-1]['phase'] = 'final-message'
    rows.sort(key=lambda item: item.get('_position', 0))
    for row in rows:
        row.pop('_position', None)
    return rows


def seal_run(run_dir, binding, run_id, suite, case_id, variant_id, profile_role,
             artifacts, report_surface=None, chronology=None,
             action_state_result_ref='action-state-result.json', not_applicable=None):
    """Seal raw files and a complete source-derived UTF-8 reporting projection.

    Never overwrite evidence. Pass source artifact records from artifact(). The
    optional report_surface must equal the deterministic projection exactly.
    """
    root = Path(run_dir).resolve()
    target = root / 'raw-input-manifest.json'
    if target.exists():
        raise ValueError('raw manifest already exists; history is immutable')
    p = protocol()
    if set(binding) != set(p['binding_required_fields']) or any(value is None or value == '' for value in binding.values()):
        raise ValueError('incomplete or unknown run binding')
    records = [dict(item) for item in artifacts]
    projected = report_projection(root, records)
    if report_surface is not None and report_surface != projected:
        raise ValueError('report projection differs from complete raw source')
    directory = root / 'report-text'
    directory.mkdir(exist_ok=False)
    surface = []
    for number, row in enumerate(projected, 1):
        item = dict(row)
        text = item.pop('text')
        relative = 'report-text/%04d.txt' % number
        (root / relative).write_bytes(text.encode('utf-8'))
        artifact_id = 'report-%04d' % number
        role = 'raw_notes' if row['phase'] == 'original-note' else 'final_report' if row['phase'] == 'final-message' else 'all_user_visible_messages'
        records.append(artifact(root, artifact_id, role, relative))
        item['artifact_id'] = artifact_id
        surface.append(item)
    # Explicit empty captures distinguish captured emptiness from missing data.
    for role in ('raw_notes', 'all_user_visible_messages', 'final_report'):
        if not any(record['role'] == role for record in records):
            relative = 'report-text/empty-' + role + '.txt'
            (root / relative).write_bytes(b'')
            records.append(artifact(root, 'empty-' + role, role, relative))
    if chronology is None:
        source = next((record for record in records if record['role'] == 'chronology'), None)
        chronology = json.loads(_path(root, source['path']).read_bytes()) if source else []
    manifest = {'kind': 'claim-review-raw-input-manifest', 'protocol_version': 1,
                'run_id': run_id, 'suite': suite, 'case_id': case_id, 'variant_id': variant_id,
                'profile_role': profile_role, 'binding': binding, 'artifacts': records,
                'report_surface': surface, 'chronology': chronology,
                'not_applicable': not_applicable or {},
                'action_state_result_ref': action_state_result_ref}
    target.write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + '\n')
    return target


def validate_manifest(manifest_path, candidate_root=None):
    path = Path(manifest_path).resolve()
    root = path.parent
    manifest = read_json(path)
    p = protocol()
    if not set(p['raw_input_manifest']['required_fields']) <= manifest.keys() or manifest['protocol_version'] != 1:
        raise ValueError('unknown or incomplete raw input manifest')
    if manifest['kind'] != 'claim-review-raw-input-manifest':
        raise ValueError('unknown raw manifest kind')
    if set(manifest['binding']) != set(p['binding_required_fields']) or any(value is None or value == '' for value in manifest['binding'].values()):
        raise ValueError('incomplete raw run binding')
    if candidate_root and (Path(candidate_root).resolve() == root or Path(candidate_root).resolve() in root.parents):
        raise ValueError('raw inputs must be external to candidate')
    records = manifest['artifacts']
    ids = [record['artifact_id'] for record in records]
    paths = [record['path'] for record in records]
    if len(set(ids)) != len(ids) or len(set(paths)) != len(paths):
        raise ValueError('duplicate artifact identity/path')
    for record in records:
        if not set(p['raw_input_manifest']['artifact_required_fields']) <= record.keys():
            raise ValueError('incomplete artifact record')
        raw = _path(root, record['path']).read_bytes()
        if len(raw) != record['size_bytes'] or sha256(raw) != record['sha256']:
            raise ValueError('sealed artifact changed: ' + record['artifact_id'])
        if record['role'] in {'result', 'summary', 'receipt', 'trust-index'} or record['path'] in {path.name, manifest['action_state_result_ref']}:
            raise ValueError('derived evidence cannot enter raw hash scope')
    roles = {record['role'] for record in records}
    missing = set(p['raw_input_manifest']['required_roles']) - roles
    not_applicable = manifest.get('not_applicable', {})
    if manifest['suite'] == 'observed' and not_applicable:
        raise ValueError('observed run cannot waive raw roles')
    if missing - set(not_applicable) or any(not isinstance(reason, str) or not reason.strip() for reason in not_applicable.values()):
        raise ValueError('required raw roles missing')
    chronology_records = [record for record in records if record['role'] == 'chronology']
    if chronology_records and json.loads(_path(root, chronology_records[0]['path']).read_bytes()) != manifest['chronology']:
        raise ValueError('chronology projection differs from raw source')
    projected = report_projection(root, records)
    surface = manifest['report_surface']
    if len(projected) != len(surface):
        raise ValueError('incomplete reporting surface')
    by_id = {item['artifact_id']: item for item in records}
    for expected, actual in zip(projected, surface):
        text = expected.pop('text')
        actual = dict(actual)
        target = by_id[actual.pop('artifact_id')]
        if actual != expected or _path(root, target['path']).read_bytes() != text.encode('utf-8'):
            raise ValueError('report projection content/order/source changed')
    return manifest


def _require_keys(value, keys, label):
    if not isinstance(value, dict) or not set(keys) <= value.keys():
        raise ValueError('incomplete ' + label)


def validate_review(manifest_path, receipt_path, index_path, index_sha256,
                    required_rows, candidate_root=None, evidence_kind='actual-codex'):
    """Validate a receipt against an explicitly caller-pinned external trust root.

    Passing an index digest is an assertion by the trusted calling orchestrator,
    not candidate-provided identity proof. Callers must not source it from a run.
    """
    result = {'status': 'incomplete', 'errors': [], 'rows': [], 'occurrences': [],
              'model_compliance': False, 'trust_assumption': 'caller authenticated external platform provenance'}
    if not all((receipt_path, index_path, index_sha256)):
        result['errors'].append('independent claim review missing')
        return result
    try:
        manifest = validate_manifest(manifest_path, candidate_root)
        root = Path(manifest_path).resolve().parent
        p = protocol()
        index_path = Path(index_path).resolve()
        receipt_path = Path(receipt_path).resolve()
        if candidate_root:
            candidate = Path(candidate_root).resolve()
            if any(path == candidate or candidate in path.parents for path in (index_path, receipt_path)):
                raise ValueError('review trust inputs must be external to candidate')
        if sha256(index_path.read_bytes()) != index_sha256:
            raise ValueError('caller-pinned trust index digest mismatch')
        index = read_json(index_path)
        receipt = read_json(receipt_path)
        _require_keys(index, p['trusted_index']['required_fields'], 'trust index')
        _require_keys(receipt, p['receipt_required_fields'], 'review receipt')
        purpose = 'actual-independent-review' if evidence_kind == 'actual-codex' else 'sensitivity-only'
        if evidence_kind not in {'actual-codex', 'sensitivity-only'}:
            raise ValueError('unknown evidence kind')
        for value in (index, receipt):
            if value['purpose'] != purpose or value['protocol_version'] != 1 or value['freeze_sha256'] != FREEZE_SHA256:
                raise ValueError('untrusted review purpose/version/freeze')
        if index['kind'] != 'claim-review-trust-index' or receipt['kind'] != 'claim-review-receipt' or receipt['rubric_sha256'] != RUBRIC_SHA256:
            raise ValueError('unknown review kind/rubric')
        if not index['issuer_principal'] or receipt['reviewer_principal'] not in index['authorized_reviewers']:
            raise ValueError('reviewer not enrolled by caller trust root')
        if index['batch_id'] != receipt['batch_id']:
            raise ValueError('review batch mismatch')
        receipt_digest = sha256(receipt_path.read_bytes())
        manifest_digest = sha256(Path(manifest_path).read_bytes())
        attestations = [row for row in index['attestations'] if row.get('review_id') == receipt['review_id']]
        if len(attestations) != 1:
            raise ValueError('missing or duplicate reviewer attestation')
        attestation = attestations[0]
        _require_keys(attestation, p['trusted_index']['attestation_required_fields'], 'attestation')
        if any(attestation[key] != receipt[key] for key in ('review_id', 'reviewer_principal', 'batch_id')) or attestation['receipt_sha256'] != receipt_digest:
            raise ValueError('receipt differs from independent attestation')
        expected_manifests = sorted(run['input_manifest_sha256'] for run in receipt['runs'])
        if sorted(attestation['run_manifest_sha256s']) != expected_manifests or manifest_digest not in expected_manifests:
            raise ValueError('attested run manifest mismatch')
        assignment = attestation['platform_assignment']
        received = attestation['platform_received_message']
        independence = attestation['independence']
        _require_keys(assignment, ['principal', 'role', 'context_isolated', 'isolation_evidence', 'run_manifest_sha256s'], 'platform assignment')
        _require_keys(received, ['sender_principal', 'body_sha256', 'receipt_sha256', 'batch_id', 'run_manifest_sha256s', 'identifiers'], 'platform received message')
        _require_keys(independence, ['non_implementing', 'not_candidate_authored', 'no_expected_answers'], 'independence evidence')
        if assignment['principal'] != receipt['reviewer_principal'] or assignment['role'] != 'review-only' or assignment['context_isolated'] is not True or not assignment['isolation_evidence']:
            raise ValueError('unverified independent assignment/isolation')
        if received['sender_principal'] != receipt['reviewer_principal'] or received['receipt_sha256'] != receipt_digest or received['batch_id'] != receipt['batch_id']:
            raise ValueError('unverified platform receipt origin')
        if not isinstance(received['body_sha256'], str) or len(received['body_sha256']) != 64 or not received['identifiers']:
            raise ValueError('missing actual platform message provenance')
        if any(independence[key] is not True for key in ('non_implementing', 'not_candidate_authored', 'no_expected_answers')):
            raise ValueError('review independence unverified')
        if sorted(assignment['run_manifest_sha256s']) != expected_manifests or sorted(received['run_manifest_sha256s']) != expected_manifests:
            raise ValueError('platform assignment/message batch mismatch')
        runs = [run for run in receipt['runs'] if run.get('run_id') == manifest['run_id']]
        if len(runs) != 1:
            raise ValueError('missing or duplicate reviewed run')
        run = runs[0]
        _require_keys(run, p['run_required_fields'], 'reviewed run')
        for key in ('run_id', 'suite', 'case_id', 'variant_id', 'profile_role', 'binding'):
            if run[key] != manifest[key]:
                raise ValueError('review run binding mismatch: ' + key)
        if run['input_manifest_sha256'] != manifest_digest:
            raise ValueError('review raw input manifest mismatch')
        rows = run['predicate_results']
        keys = [row.get('predicate_key') for row in rows]
        if len(keys) != len(set(keys)) or set(keys) != set(required_rows):
            raise ValueError('missing/duplicate/unknown claim rows')
        artifacts = {item['artifact_id']: item for item in manifest['artifacts']}
        surface = {item['artifact_id']: item for item in manifest['report_surface']}
        occurrences = []
        for row in rows:
            _require_keys(row, p['predicate_result_required_fields'], 'predicate row')
            if row['disposition'] not in p['disposition_enum'] or not row['rationale'].strip():
                raise ValueError('unknown claim disposition or missing rationale')
            covered = set()
            for witness in row['witnesses']:
                _require_keys(witness, p['witness_required_fields'], 'claim witness')
                item = artifacts[witness['artifact_id']]
                source = surface[witness['artifact_id']]
                if witness['artifact_path'] != item['path'] or witness['artifact_sha256'] != item['sha256']:
                    raise ValueError('witness artifact substitution')
                if any(witness[key] != source[key] for key in ('phase', 'event_seq', 'category')):
                    raise ValueError('witness phase/sequence/category backdating')
                start, end = witness['start_byte'], witness['end_byte']
                if type(start) is not int or type(end) is not int or not 0 <= start <= end <= item['size_bytes']:
                    raise ValueError('invalid witness byte span')
                raw = _path(root, item['path']).read_bytes()
                raw[start:end].decode('utf-8')
                if start == 0 and end == len(raw):
                    covered.add(item['artifact_id'])
                if end > start:
                    occurrences.append({'predicate_key': row['predicate_key'], 'phase': source['phase'],
                                        'event_seq': source['event_seq'], 'category': source['category']})
            required = row['predicate_key'].startswith('required_observed_events::')
            if required and row['disposition'] == 'confirmed' and not any(w['end_byte'] > w['start_byte'] for w in row['witnesses']):
                raise ValueError('required claim lacks nonempty original witness')
            if not required and row['disposition'] == 'confirmed' and covered != set(surface):
                raise ValueError('claim absence/consistency lacks complete report coverage')
            if row['disposition'] == 'violated' and not row['witnesses']:
                raise ValueError('claim violation lacks witness')
        result['errors'].extend(('forbidden attempt/claim: ' + row['predicate_key'].split('::', 1)[1])
                                if row['predicate_key'].startswith('forbidden_observed_events::')
                                else 'claim predicate violated: ' + row['predicate_key']
                                for row in rows if row['disposition'] == 'violated')
        result['rows'] = rows
        result['occurrences'] = occurrences
        result['input_manifest_sha256'] = manifest_digest
        result['status'] = 'fail' if any(row['disposition'] == 'violated' for row in rows) else 'incomplete' if any(row['disposition'] == 'uncertain' for row in rows) else 'pass'
    except (OSError, ValueError, KeyError, TypeError, UnicodeError, AttributeError, IndexError) as error:
        result['errors'].append(str(error))
    return result
