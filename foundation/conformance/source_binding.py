"""Producer-owned launch/source consistency, separate from origin admission.

All consulted copies are linked from capture and metadata. A digest cannot
authenticate a producer. Actual callers still establish firsthand origin; the
explicit local wrapper adapter below supplies only a conditional test premise.
"""
import hashlib
import json
from pathlib import Path
import stat


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _save(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


def _record(root, path):
    return {'path': path.relative_to(root).as_posix(), 'sha256': _sha(path.read_bytes()),
            'mode': f'{stat.S_IMODE(path.stat().st_mode):04o}'}


def _read(root, record):
    relative = Path(record['path'])
    path = root / relative
    if relative.is_absolute() or '..' in relative.parts or path.is_symlink():
        raise ValueError('unsafe source link')
    if root.resolve() not in path.resolve().parents:
        raise ValueError('source link escapes capture')
    raw = path.read_bytes()
    if _sha(raw) != record['sha256'] or f'{stat.S_IMODE(path.stat().st_mode):04o}' != record['mode']:
        raise ValueError('source link changed')
    return raw


def _settings(command):
    if not isinstance(command, list) or any(not isinstance(token, str) for token in command):
        raise ValueError('unsupported command shape')
    return {token.split('=', 1)[0]: json.loads(token.split('=', 1)[1]) for token in command
            if token.startswith('mcp_servers.workbench.') and '=' in token}


def prepare_launch(observer_dir, configured_command, source_root, config_path):
    """Copy actual launch inputs before the model/workbench can execute."""
    from .runner import tree_hash
    root = Path(observer_dir).resolve()
    source_root = Path(source_root).resolve()
    target = root / 'effect-inputs'
    target.mkdir()
    sources = {}
    harness_digest, harness_files = tree_hash(source_root)
    # Host imports only stdlib; selector.py is its one child implementation.
    # The rest of the known harness is pinned by its complete byte/mode map,
    # without duplicating the whole corpus into every operation fixture.
    for name in ('host.py', 'selector.py'):
        source = source_root / name
        relative = source.relative_to(source_root)
        copy = target / 'source' / relative
        copy.parent.mkdir(parents=True, exist_ok=True)
        copy.write_bytes(source.read_bytes())
        copy.chmod(stat.S_IMODE(source.stat().st_mode))
        sources[relative.as_posix()] = _record(root, copy)
    config_copy = target / 'host-config.json'
    config_copy.write_bytes(Path(config_path).read_bytes())
    config = json.loads(config_copy.read_bytes())
    entry_path = Path(_settings(configured_command)['mcp_servers.workbench.args'][0])
    entry = target / 'host-entry.py'
    entry.write_bytes(entry_path.read_bytes())
    entry.chmod(stat.S_IMODE(entry_path.stat().st_mode))
    selector = target / 'selector-entry.py'
    selector_path = entry_path.with_name('selector.py')
    selector.write_bytes(selector_path.read_bytes())
    selector.chmod(stat.S_IMODE(selector_path.stat().st_mode))
    launch = {'version': 1, 'purpose': 'configured-workbench',
              'configured_command': list(configured_command), 'executed_command': list(configured_command),
              'source_root': str(source_root), 'config_path': str(Path(config_path).resolve()),
              'entry_path': str(entry_path), 'entry': _record(root, entry), 'selector': _record(root, selector),
              'config': _record(root, config_copy), 'sources': sources,
              'harness_digest': harness_digest, 'harness_files': harness_files,
              'run_identity': config['run_identity']}
    path = root / 'effect-launch.json'
    _save(path, launch)
    return path


def prepare_sensitivity_launch(observer_dir, executed_command, producer_path,
                               expected_producer_sha256, input_paths=()):
    """Bind a controlled wrapper to the caller's prior exact source pin.

    The caller separately inspects/approves the wrapper's controlled forwarding,
    pauses and negative injections. This is an explicit sensitivity premise, not
    an actual producer attestation or a way to grant model compliance. A changed
    or unsupported producer must not be approved by simply updating its pin.
    """
    root = Path(observer_dir).resolve()
    launch = json.loads((root / 'effect-launch.json').read_bytes())
    # Retain the exact argv spelling, including a legitimate /var alias on
    # macOS. Bytes are read through that path and checked against the prior pin.
    producer = Path(producer_path)
    copy = root / 'effect-inputs' / 'controlled-producer.py'
    copy.write_bytes(producer.read_bytes())
    copy.chmod(stat.S_IMODE(producer.stat().st_mode))
    launch.update(purpose='controlled-sensitivity', executed_command=list(executed_command),
                  producer_path=str(producer), producer=_record(root, copy),
                  expected_producer_sha256=expected_producer_sha256)
    inputs = []
    for input_path in input_paths:
        original = str(Path(input_path))
        positions = [index for index, value in enumerate(executed_command) if value == original]
        if len(positions) != 1:
            raise ValueError('declared input is not one exact command argument')
        index = positions[0]
        target = root / 'effect-inputs' / ('controlled-input-' + str(index))
        target.write_bytes(Path(input_path).read_bytes())
        target.chmod(stat.S_IMODE(Path(input_path).stat().st_mode))
        inputs.append({'argument_index': index, 'original_path': original,
                       'record': _record(root, target)})
    inputs.sort(key=lambda row: row['argument_index'])
    launch['inputs'] = inputs
    # These are producer measurements, not an authorization declaration. The
    # trusted caller still checks the approved wrapper's dependency closure.
    # An existing file argument cannot disappear merely by omitting input_paths.
    launch['file_arguments'] = [
        {'argument_index': index, 'original_path': value}
        for index, value in enumerate(executed_command)
        if index >= 2 and value != launch['config_path'] and Path(value).is_file()
    ]
    path = root / 'sensitivity-effect-launch.json'
    _save(path, launch)
    return path


def launch_reference(observer_dir, path):
    return _record(Path(observer_dir).resolve(), Path(path).resolve())


def postlaunch_sources(observer_dir, reference):
    """Producer measurements; replay consults retained hashes/copies only."""
    if reference is None:
        return {}
    try:
        root = Path(observer_dir).resolve()
        launch = json.loads(_read(root, reference))
        originals = {'entry': Path(launch['entry_path']),
                     'selector': Path(launch['entry_path']).with_name('selector.py'),
                     'config': Path(launch['config_path'])}
        if launch.get('purpose') == 'controlled-sensitivity':
            originals['producer'] = Path(launch['producer_path'])
            originals.update({'input:' + str(row['argument_index']): Path(row['original_path'])
                              for row in launch['inputs']})
        return {name: _sha(path.read_bytes()) for name, path in originals.items()}
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def validate(observation):
    """Revalidate retained closure; unknown linkage supplies no effect proof."""
    if observation.get('transport') == 'ordinary-native-read-only-v1':
        from .native_capture import validate_capture
        result = validate_capture(observation)
        return {'purpose': 'ordinary-native-read-only', 'origin_authenticated': False} if result['status'] == 'verified-subset' else None
    from .runner import tree_hash
    try:
        paths = observation['observer_paths']
        root = Path(paths['capture']).resolve().parent
        metadata_path = Path(paths['metadata']).resolve()
        if metadata_path != root.parent / 'metadata.json':
            return None
        raw = Path(paths['capture']).read_bytes()
        if _sha(raw) != observation['process']['capture_sha256']:
            return None
        capture = json.loads(raw)
        reference = capture['source_launch']
        launch = json.loads(_read(root, reference))
        metadata_raw = metadata_path.read_bytes()
        if _sha(metadata_raw) != observation['process']['metadata_sha256']:
            return None
        metadata = json.loads(metadata_raw)
        if (metadata['source_launch'] != reference
                or metadata['executed_command'] != capture['executed_command']
                or launch['executed_command'] != capture['executed_command']
                or launch['configured_command'] != metadata['command']
                or capture['process_started_at_ns'] != observation['process']['started_at_ns']
                or capture['stdout_sha256'] != observation['process']['stdout_sha256']
                or launch['run_identity']['run_dir'] != capture['producer_run_dir']
                or metadata['producer_run_dir'] != capture['producer_run_dir']):
            return None
        config = json.loads(_read(root, launch['config']))
        required_sources = ['entry', 'selector', 'config']
        if launch.get('purpose') == 'controlled-sensitivity':
            required_sources.append('producer')
        if any(metadata['source_files_after'].get(name) != launch[name]['sha256'] for name in required_sources):
            return None
        identity = launch['run_identity']
        if config['run_identity'] != identity or any(identity[key] != metadata[key] for key in identity if key != 'run_dir'):
            return None
        expected_scope = {'candidate_tree_digest': observation['identity']['candidate_digest'],
                          'installed_tree_digest': observation['identity']['installed_digest']}
        if any(identity[key] != value for key, value in expected_scope.items()):
            return None
        settings = _settings(launch['configured_command'])
        host_args = settings['mcp_servers.workbench.args']
        if (len(host_args) != 2 or host_args[1] != launch['config_path']
                or host_args[0] != launch['entry_path']
                or config['workspace'] != str(Path(identity['run_dir']) / 'workspace')
                or config['journal'] != str(Path(identity['run_dir']) / 'observer/journal.jsonl')
                or config['state'] != str(Path(identity['run_dir']) / 'observer/state.json')):
            return None
        records = {}
        for name, record in launch['sources'].items():
            _read(root, record)
            records[name] = {'sha256': record['sha256'], 'mode': record['mode']}
        encoded = json.dumps(launch['harness_files'], sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
        canonical_digest, canonical_files = tree_hash(Path(__file__).parent)
        if (_sha(_read(root, launch['entry'])) != canonical_files['host.py']['sha256']
                or _sha(_read(root, launch['selector'])) != canonical_files['selector.py']['sha256']):
            return None
        if (_sha(encoded) != launch['harness_digest'] or launch['harness_digest'] != metadata['harness_digest']
                or launch['harness_files'] != canonical_files or canonical_digest != launch['harness_digest']
                or any(records[name] != canonical_files[name] for name in ('host.py', 'selector.py'))):
            return None
        if launch['purpose'] == 'configured-workbench':
            if launch['executed_command'] != launch['configured_command']:
                return None
        elif launch['purpose'] == 'controlled-sensitivity':
            if observation['process']['kind'] != 'sensitivity-only':
                return None
            producer = _read(root, launch['producer'])
            if (_sha(producer) != launch['expected_producer_sha256']
                    or len(launch['executed_command']) < 2
                    or launch['executed_command'][1] != launch['producer_path']):
                return None
            inputs = launch['inputs']
            expected = launch['file_arguments']
            if ([{'argument_index': row['argument_index'], 'original_path': row['original_path']}
                 for row in inputs] != expected):
                return None
            if len({row['argument_index'] for row in inputs}) != len(inputs):
                return None
            for row in inputs:
                index = row['argument_index']
                if (not isinstance(index, int) or index < 2
                        or launch['executed_command'][index] != row['original_path']
                        or _sha(_read(root, row['record'])) != metadata['source_files_after'].get('input:' + str(index))):
                    return None
        else:
            return None
        return {'purpose': launch['purpose']}
    except (OSError, ValueError, KeyError, TypeError, AttributeError, IndexError):
        return None


def artifacts(observer_dir):
    """The existing manifest schema permits these additional raw roles."""
    root = Path(observer_dir)
    paths = [root / 'effect-launch.json', root / 'sensitivity-effect-launch.json']
    paths.extend(sorted((root / 'effect-inputs').rglob('*')))
    return [path for path in paths if path.is_file()]
