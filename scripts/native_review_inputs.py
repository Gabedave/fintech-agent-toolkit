"""Opt-in public inputs for release claim review; no execution or scoring policy.

All source_index paths are relative to the directory containing context.json.
Only the selected plugin cache and explicitly supplied synthetic workspace are
copied. Authentication/configuration homes are never copied.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time

import native_evidence as evidence

MAX_FILES = 10000
MAX_BYTES = 64 * 1024 * 1024
SAFE_ENV = {'PATH', 'HOME', 'TMPDIR', 'LANG', 'LC_ALL', 'LC_CTYPE', 'SYSTEMROOT',
            'SSL_CERT_FILE', 'CODEX_CA_CERTIFICATE', 'CODEX_HOME', 'PYTHONDONTWRITEBYTECODE'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def save(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, ensure_ascii=False)
        stream.write('\n')
    Path(path).chmod(0o600)


def environment(env):
    actual = dict(env)
    safe = {key: value for key, value in actual.items()
            if key in SAFE_ENV or key.startswith('CODEX_SANDBOX_')}
    encoding = actual.get('__CF_USER_TEXT_ENCODING', '')
    if re.fullmatch(r'(?:0x[0-9a-fA-F]{1,16}|[0-9]{1,16})(?::(?:0x[0-9a-fA-F]{1,16}|[0-9]{1,16})){2}', encoding):
        safe['__CF_USER_TEXT_ENCODING'] = encoding
    return {'sha256': evidence.digest(canonical(actual)), 'safe_values': safe,
            'keys': sorted(actual), 'unexpected_keys': sorted(set(actual) - set(safe))}


def environment_transition(before, after):
    """Describe measured stages without normalizing their exact digests."""
    old, new = before['safe_values'], after['safe_values']
    return {'from_sha256': before['sha256'], 'to_sha256': after['sha256'],
            'added_keys': sorted(set(after['keys']) - set(before['keys'])),
            'removed_keys': sorted(set(before['keys']) - set(after['keys'])),
            'changed_safe_values': {key: {'before': old.get(key), 'after': new.get(key)}
                                    for key in sorted(old.keys() | new.keys()) if old.get(key) != new.get(key)},
            'unretained_value_keys': sorted(set(before['unexpected_keys']) | set(after['unexpected_keys']))}


def capture_model_probe(root, env, requested_model, timeout, *, reasoning_effort=None):
    """One non-JSON observation, then explicit model pins on scored JSON calls.

    Use the existing conformance collector's diagnostic privacy and completion
    rules. This observes the shared probe; it is not a per-task model header.
    """
    from foundation.conformance.runner import stream_process, require_effective_model, require_effective_effort, reasoning_effort_args
    output, workspace = root / 'model-probe', root / 'model-probe-workspace'
    output.mkdir(mode=0o700)
    workspace.mkdir(mode=0o700)
    command = ['codex', 'exec', '--ephemeral', '--skip-git-repo-check', '--sandbox', 'read-only',
               '--disable', 'shell_tool', '--disable', 'unified_exec', '--disable', 'tool_suggest',
               '-c', 'web_search="disabled"', '-C', str(workspace)]
    if requested_model:
        command.extend(['--model', requested_model])
    command.extend(reasoning_effort_args(reasoning_effort))
    command.append('-')
    prompt = 'Reply PROBE_READY. Do not invoke tools or access files.'
    save(output / 'request.json', {'command': command, 'prompt': prompt,
         'requested_model': requested_model, 'cwd': str(workspace),
         **({'reasoning_effort': reasoning_effort} if reasoning_effort is not None else {}),
         'environment': environment(env), 'prepared_at_ns': time.monotonic_ns()})
    result = stream_process(command, env, workspace, output, timeout, prompt)
    result['finished_at_ns'] = time.monotonic_ns()
    save(output / 'result.json', result)
    effective = require_effective_model(result)
    require_effective_effort(result, reasoning_effort)
    artifacts = {}
    for role, name in (('request', 'request.json'), ('result', 'result.json'),
                       ('diagnostics', 'diagnostics.json'), ('capture', 'capture.json'), ('stdout', 'stdout.jsonl')):
        path = output / name
        path.chmod(0o600)
        raw, _ = _read(path)
        artifacts[role] = {'path': path.relative_to(root).as_posix(),
                           'sha256': evidence.digest(raw), 'size_bytes': len(raw)}
    return {'kind': 'shared-native-model-probe-v1', 'effective_model': effective, **artifacts,
            **({'reasoning_effort': reasoning_effort} if reasoning_effort is not None else {})}


def validate_model_probe(root, descriptor, release_environment):
    from foundation.conformance.runner import require_effective_model, require_effective_effort
    values = {}
    for role in ('request', 'result', 'diagnostics', 'capture', 'stdout'):
        row = descriptor[role]
        raw, _ = _read_relative(root, row['path'])
        if evidence.digest(raw) != row['sha256'] or len(raw) != row['size_bytes']:
            raise ValueError('retained model probe changed')
        if role != 'stdout':
            values[role] = json.loads(raw)
    request, result = values['request'], values['result']
    effective = require_effective_model(result)
    effort = descriptor.get('reasoning_effort')
    require_effective_effort(result, effort)
    if request.get('reasoning_effort') != effort or not effort_command_matches(request['command'], effort):
        raise ValueError('model probe effort binding is inconsistent')
    command_hash = evidence.digest(json.dumps(request['command'], separators=(',', ':')).encode())
    if (descriptor['kind'] != 'shared-native-model-probe-v1' or descriptor['effective_model'] != effective
            or result['command'] != request['command'] or '--json' in request['command']
            or result['diagnostics'] != values['diagnostics']
            or command_hash != values['diagnostics']['command_sha256']
            or result['capture_sha256'] != descriptor['capture']['sha256']
            or request['environment'] != release_environment
            or not request['prepared_at_ns'] <= result['started_at_ns'] < result['finished_at_ns']):
        raise ValueError('model probe binding is inconsistent')
    return effective


def effort_command_matches(command, effort):
    from foundation.conformance.runner import reasoning_effort_args
    expected = reasoning_effort_args(effort)
    assignments = []
    index = 0
    while index < len(command):
        token = command[index]
        if token == '--':
            break
        value = None
        option_index = index
        if token in ('-c', '--config') and index + 1 < len(command):
            index += 1
            value = command[index]
        elif token.startswith('--config='):
            value = token[len('--config='):]
        elif token.startswith('-c') and token != '-c':
            value = token[2:].removeprefix('=')
        if value is not None and value.partition('=')[0].strip().strip('\"\'') == 'model_reasoning_effort':
            assignments.append(option_index)
        index += 1
    if effort is None:
        return not assignments
    return len(assignments) == 1 and list(command[assignments[0]:assignments[0]+2]) == expected


def _read(name, directory_fd=None):
    fd = os.open(name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=directory_fd)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError('not a regular file')
        if before.st_size > MAX_BYTES:
            raise ValueError('file exceeds capture limit')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(MAX_BYTES + 1)
        after = os.fstat(fd)
        if len(raw) > MAX_BYTES or (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError('file changed during capture or exceeds limit')
        return raw, {'sha256': evidence.digest(raw), 'size_bytes': len(raw),
                     'mode': format(stat.S_IMODE(after.st_mode), '04o')}
    finally:
        os.close(fd)


def snapshot(source, target, output=None):
    """Descriptor-based bounded copy. Gaps never stand in for empty state."""
    source = Path(source).absolute()
    target = Path(target) if target is not None else None
    if target is not None:
        if target.resolve().is_relative_to(source.resolve()):
            raise ValueError('capture output must be outside the measured workspace')
        target.mkdir(mode=0o700)
    excluded = None
    if output is not None:
        try:
            excluded = Path(output).absolute().relative_to(source).as_posix()
        except ValueError:
            pass
    result = {'root': str(source), 'root_present': False, 'measured_at_ns': time.monotonic_ns(),
              'files': {}, 'directories': [], 'entries': {}, 'gaps': [],
              'exclusions': ['.git at any depth', *([excluded] if excluded else [])]}
    total = 0
    root_fd = None
    try:
        root_fd = os.open(source, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        result['root_present'] = True
        def walk_error(error):
            result['gaps'].append('directory enumeration: ' + type(error).__name__)
        for directory, dirs, names, directory_fd in os.fwalk('.', dir_fd=root_fd, follow_symlinks=False,
                                                             onerror=walk_error):
            prefix = Path(directory)
            dirs.sort(); names.sort()
            for name in list(dirs):
                relative = (prefix / name).as_posix()
                if name == '.git':
                    dirs.remove(name)
                    continue
                info = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
                if stat.S_ISLNK(info.st_mode):
                    dirs.remove(name)
                    result['entries'][relative] = {'kind': 'symlink'}
                    result['gaps'].append('symlink directory: ' + relative)
                else:
                    result['directories'].append(relative)
                    if target is not None:
                        (target / relative).mkdir(mode=0o700, parents=True, exist_ok=True)
            for name in names:
                relative = (prefix / name).as_posix()
                if name == '.git' or relative == excluded:
                    continue
                try:
                    if len(result['files']) >= MAX_FILES:
                        raise ValueError('file count exceeds capture limit')
                    raw, row = _read(name, directory_fd)
                    total += len(raw)
                    if total > MAX_BYTES:
                        raise ValueError('tree exceeds capture limit')
                    if target is not None:
                        dest = target / relative
                        dest.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                        with dest.open('xb') as stream:
                            stream.write(raw)
                        dest.chmod(0o600)  # Actual source mode is retained in inventory.
                    result['files'][relative] = row
                except (OSError, ValueError) as error:
                    result['entries'][relative] = {'kind': 'unreadable-or-nonregular', 'error': type(error).__name__}
                    result['gaps'].append('file unavailable: ' + relative + ' (' + type(error).__name__ + ')')
    except (OSError, ValueError) as error:
        result['gaps'].append('workspace capture: ' + type(error).__name__)
    finally:
        if root_fd is not None:
            os.close(root_fd)
    return result


def _tree_digest(files):
    # Same bytes/modes canonicalization as foundation.conformance.runner.tree_hash.
    return evidence.digest(canonical({name: {'sha256': row['sha256'], 'mode': row['mode']}
                                      for name, row in files.items()}))


def prepare_release_context(evidence_dir, candidate, profile_path, home, env, catalog_bytes, *, installed_at_ns,
                            probe_model=False, requested_model=None, timeout=120, reasoning_effort=None):
    candidate, profile_path, home = Path(candidate).resolve(), Path(profile_path).resolve(), Path(home).resolve()
    root = Path(evidence_dir) / 'review-inputs'
    root.mkdir(mode=0o700)
    profile = json.loads(profile_path.read_bytes())
    catalog = json.loads(catalog_bytes)
    plugin_id = profile['plugin_name'] + '@' + profile['marketplace']
    matches = [(i, row) for i, row in enumerate(catalog.get('installed', []))
               if row.get('pluginId') == plugin_id and row.get('enabled') is True and row.get('installed') is True]
    if len(matches) != 1:
        raise ValueError('exactly one enabled selected installed catalog row required')
    index, selected = matches[0]
    if (selected.get('name'), selected.get('marketplaceName'), selected.get('version')) != (
            profile['plugin_name'], profile['marketplace'], profile['plugin_version']):
        raise ValueError('selected installed catalog identity differs from candidate profile')
    # The catalog source.path is a marketplace source, never the selected cache.
    cache = home / 'plugins/cache' / profile['marketplace'] / profile['plugin_name']
    candidates = []
    for manifest in cache.glob('*/.codex-plugin/plugin.json'):
        raw, _ = _read_relative(home, manifest.relative_to(home).as_posix())
        value = json.loads(raw)
        if value.get('name') == selected['name'] and value.get('version') == selected['version']:
            candidates.append(manifest.parent.parent)
    if len(candidates) != 1:
        raise ValueError('selected installed cache is missing or ambiguous')
    installed = candidates[0]
    installed_rows = snapshot(installed, root / 'installed-source')
    generated_rows = snapshot(candidate / 'plugins' / profile['plugin_name'], root / 'candidate-source')
    if installed_rows['gaps'] or generated_rows['gaps']:
        raise ValueError('selected plugin source capture incomplete')
    if installed_rows['files'] != generated_rows['files']:
        raise ValueError('installed bytes or modes differ from generated candidate')
    lock = json.loads((candidate / 'foundation-lock.json').read_bytes())
    tree_digest = _tree_digest(installed_rows['files'])
    if evidence.digest(canonical(lock['files'])) != lock['generated_tree_digest']:
        raise ValueError('generated tree lock digest differs from its file inventory')
    prefix = 'plugins/' + profile['plugin_name'] + '/'
    locked_plugin_files = {name[len(prefix):] for name in lock['files'] if name.startswith(prefix)}
    if set(generated_rows['files']) != locked_plugin_files:
        raise ValueError('generated plugin path inventory differs from foundation lock')
    for name, expected in lock['files'].items():
        _, actual = _read_relative(candidate, name)
        if any(actual[key] != expected[key] for key in ('sha256', 'mode')):
            raise ValueError('generated candidate file differs from foundation lock')
    (root / 'catalog.json').write_bytes(catalog_bytes)
    (root / 'catalog.json').chmod(0o600)
    sources = []
    for role, tree, original, rows in (
        ('installed-source', 'installed-source', installed, installed_rows),
        ('candidate-source', 'candidate-source', candidate / 'plugins' / profile['plugin_name'], generated_rows),
    ):
        for name, row in rows['files'].items():
            sources.append({'role': role, 'original_path': str(original / name), 'path': tree + '/' + name, **row})
    paths = {candidate / 'foundation-lock.json': 'foundation-lock', profile_path: 'candidate-profile',
             candidate / 'foundation/version.json': 'foundation-version',
             candidate / '.agents/plugins/marketplace.json': 'marketplace-source'}
    for folder, role in (('scripts', 'harness-source'), ('foundation/conformance', 'conformance-source'),
                         ('tests/review-quality', 'review-fixture-source')):
        for path in (candidate / folder).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix in {'.py', '.json', '.md'}:
                paths[path] = role
    for name in ('behavior-scenarios.json', 'behavior-result.schema.json', 'publication-result.schema.json'):
        path = candidate / 'tests' / name
        if path.exists():
            paths[path] = 'scenario-suite' if name == 'behavior-scenarios.json' else 'output-schema'
    for original, role in sorted(paths.items()):
        raw, row = _read(original)
        relative = 'sources/' + original.relative_to(candidate).as_posix()
        dest = root / relative
        dest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        dest.write_bytes(raw); dest.chmod(0o600)
        sources.append({'role': role, 'original_path': str(original), 'path': relative, **row})
    model_probe = capture_model_probe(root, env, requested_model, timeout, reasoning_effort=reasoning_effort) if probe_model else None
    value = {'kind': 'native-review-context-v1', 'candidate': evidence.git_identity(candidate),
             'profile': profile, 'foundation_lock': lock, 'installed_at_ns': installed_at_ns,
             'installation_time_semantics': 'catalog readback completed after successful installation and before model attempts',
             'selected_plugin': {'catalog_index': index, 'pluginId': plugin_id, 'cache_path': str(installed),
                 'lookup': 'unique matching name/version manifest under owned cache marketplace/plugin subtree'},
             'catalog': {'path': 'catalog.json', 'sha256': evidence.digest(catalog_bytes), 'size_bytes': len(catalog_bytes)},
             'source_index': sources, 'installed_files': installed_rows['files'],
             'candidate_tree_sha256': tree_digest, 'installed_tree_sha256': tree_digest,
             'environment_stage': 'installation-and-model-probe', 'environment': environment(env),
             'model_probe': model_probe, 'created_at_ns': time.monotonic_ns()}
    save(root / 'context.json', value)
    return {'path': str(root / 'context.json'), 'sha256': evidence.digest((root / 'context.json').read_bytes()),
            'effective_model': model_probe['effective_model'] if model_probe else None}


def capture_release_context(evidence_dir, candidate, profile_path, home, env, *, requested_model=None, timeout=120, reasoning_effort=None):
    result = subprocess.run(['codex', 'plugin', 'list', '--json'], env=env,
                            capture_output=True, timeout=20, check=False)
    if result.returncode:
        raise ValueError('selected plugin catalog readback unavailable')
    return prepare_release_context(evidence_dir, candidate, profile_path, home, env,
                                   result.stdout, installed_at_ns=time.monotonic_ns(),
                                   probe_model=True, requested_model=requested_model, timeout=timeout, reasoning_effort=reasoning_effort)


def _read_relative(root, relative):
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts or not path.parts:
        raise ValueError('source index path escapes context')
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in path.parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return _read(path.parts[-1], fd)
    finally:
        os.close(fd)


def load_suite_context(path, expected_sha256, evidence_dir, env, suite, *, candidate_root):
    path = Path(path).absolute()
    raw, _ = _read(path)
    if evidence.digest(raw) != expected_sha256:
        raise ValueError('review input context hash mismatch')
    value = json.loads(raw)
    if value.get('kind') != 'native-review-context-v1':
        raise ValueError('unsupported review input context')
    if Path(value['candidate']['path']).resolve() != Path(candidate_root).resolve():
        raise ValueError('review input context belongs to a different candidate')
    if env.get('CODEX_HOME') != value['environment']['safe_values'].get('CODEX_HOME'):
        raise ValueError('review input context belongs to a different installation home')
    if value.get('model_probe'):
        validate_model_probe(path.parent, value['model_probe'], value['environment'])
    for row in [*value['source_index'], value['catalog']]:
        retained, _ = _read_relative(path.parent, row['path'])
        if evidence.digest(retained) != row['sha256'] or len(retained) != row['size_bytes']:
            raise ValueError('retained public source changed')
        if 'original_path' in row:
            original_root = Path(value['selected_plugin']['cache_path'] if row['role'] == 'installed-source'
                                 else value['candidate']['path'])
            relative = Path(row['original_path']).relative_to(original_root).as_posix()
            _, actual = _read_relative(original_root, relative)
            if any(actual[key] != row[key] for key in ('sha256', 'size_bytes', 'mode')):
                raise ValueError('live public source differs from captured context')
    installed = snapshot(value['selected_plugin']['cache_path'], None)
    if installed['gaps'] or installed['files'] != value['installed_files']:
        raise ValueError('selected installed tree changed before suite')
    root = Path(evidence_dir) / 'review-inputs'
    root.mkdir(mode=0o700)
    context = {'kind': 'native-review-suite-v1', 'suite': suite,
               'release_context': {'path': str(path), 'sha256': expected_sha256},
               'candidate_path': str(Path(candidate_root).resolve()),
               'environment_stage': 'suite-runtime', 'environment': environment(env),
               'installation_environment_transition': environment_transition(value['environment'], environment(env)),
               'created_at_ns': time.monotonic_ns()}
    save(root / 'context.json', context)
    return ReviewInputs(root / 'context.json', evidence.digest((root / 'context.json').read_bytes()), value, context)


class ReviewInputs:
    def __init__(self, path, sha256, release, context):
        self.path, self.sha256, self.release = path, sha256, release
        self.context = context

    def begin_attempt(self, attempt_dir, workspace, output, env, *, command=(), cwd=None):
        return AttemptInputs(self, attempt_dir, workspace, output, env, command, cwd)


class AttemptInputs:
    def __init__(self, suite, attempt_dir, workspace, output, env, command, cwd):
        self.suite, self.attempt_dir = suite, Path(attempt_dir)
        self.workspace, self.output = Path(workspace), Path(output)
        self.root = self.attempt_dir / 'review-inputs'
        self.root.mkdir(mode=0o700)
        self.started = time.monotonic_ns()
        self.gaps = []
        self.finished = False
        runtime = environment(env)
        if runtime != suite.context['environment']:
            self.gaps.append('attempt environment differs from suite runtime')
        self.model_binding = None
        probe = suite.release.get('model_probe')
        if probe:
            models = [command[i + 1] for i, token in enumerate(command[:-1]) if token == '--model']
            if models == [probe['effective_model']]:
                self.model_binding = {'kind': 'shared-probe-explicit-argv-v1',
                    'effective_model': probe['effective_model'], 'probe_result_sha256': probe['result']['sha256'],
                    'command_sha256': evidence.digest(json.dumps(list(command), separators=(',', ':')).encode())}
            else:
                self.gaps.append('attempt model is not explicitly pinned to observed shared probe')
        self.effort_binding = None
        if probe and probe.get('reasoning_effort') is not None:
            if effort_command_matches(command, probe['reasoning_effort']):
                self.effort_binding = {'kind': 'shared-probe-explicit-argv-v1',
                    'reasoning_effort': probe['reasoning_effort'], 'probe_result_sha256': probe['result']['sha256'],
                    'command_sha256': evidence.digest(json.dumps(list(command), separators=(',', ':')).encode())}
            else:
                self.gaps.append('attempt reasoning effort is not explicitly pinned to observed shared probe')
        context = {'kind': 'native-review-attempt-v1',
                   'suite_context': {'path': str(suite.path), 'sha256': suite.sha256},
                   'environment_stage': 'attempt-runtime', 'environment': runtime,
                   'suite_environment_transition': environment_transition(suite.context['environment'], runtime),
                   **({'effort_binding': self.effort_binding} if probe and probe.get('reasoning_effort') is not None else {}),
                   'model_binding': self.model_binding, 'process_cwd': str(Path(cwd or os.getcwd()).absolute()),
                   'workspace': str(self.workspace.absolute()),
                   'output': str(self.output.absolute()), 'started_at_ns': self.started}
        save(self.root / 'context.json', context)
        self.before = self.capture('initial')

    def capture(self, phase):
        value = snapshot(self.workspace, self.root / (phase + '-fixture'), self.output)
        save(self.root / (phase + '-files.json'), value)
        save(self.root / (phase + '-state.json'), {'kind': 'measured-native-fixture-state',
            'root_present': value['root_present'], 'complete': not value['gaps'],
            'inventory_sha256': evidence.digest((self.root / (phase + '-files.json')).read_bytes()),
            'measured_at_ns': value['measured_at_ns'], 'exclusions': value['exclusions'],
            'domain_host': 'not used; these are synthetic native fixture measurements'})
        self.gaps.extend(phase + ': ' + gap for gap in value['gaps'])
        return value

    def finish(self):
        if self.finished:
            return
        self.finished = True
        after = self.capture('final')
        before_entries = {**self.before['files'], **self.before['entries'],
                          **{p: {'kind': 'directory'} for p in self.before['directories']}}
        after_entries = {**after['files'], **after['entries'],
                         **{p: {'kind': 'directory'} for p in after['directories']}}
        changed = sorted(p for p in before_entries.keys() | after_entries.keys()
                         if before_entries.get(p) != after_entries.get(p))
        if changed:
            self.gaps.append('workspace changed during attempt')
        try:
            capture = json.loads((self.attempt_dir / 'capture.json').read_bytes())
        except (OSError, ValueError):
            capture = {}
            self.gaps.append('native capture metadata unavailable')
        if not capture.get('observed_model') and not self.model_binding:
            self.gaps.append('observed model header unavailable')
        if (self.model_binding and capture.get('observed_model')
                and capture['observed_model'] != self.model_binding['effective_model']):
            self.gaps.append('attempt observed model differs from shared probe')
        if capture.get('raw_capture_completeness') != 'complete':
            self.gaps.append('native raw capture completeness unverified')
        save(self.root / 'capture-status.json', {'kind': 'native-review-attempt-status-v1',
             **({'effort_binding': self.effort_binding} if self.effort_binding is not None else {}),
             'gaps': self.gaps, 'changed_paths': changed, 'observed_model': capture.get('observed_model'),
             'effective_model': self.model_binding['effective_model'] if self.model_binding else capture.get('observed_model'),
             'model_identity_source': 'shared-probe-explicit-argv-v1' if self.model_binding else
                                      ('attempt stderr header' if capture.get('observed_model') else None),
             'started_at_ns': self.started, 'finished_at_ns': time.monotonic_ns(),
             'native_capture_path': '../capture.json', 'process_path': '../process.json',
             'scored_result_path': '../result-status.json', 'qualification': 'pending independent review'})
