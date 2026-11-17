"""Conditional source consistency for freshly executed raw sensitivity traces.

The caller must witness the in-process construction. These records cannot prove
execution origin, authenticate an issuer, or supply model-compliance evidence.
Old raw inputs acquire no proof by copying source beside them.
"""
import copy
import json
from pathlib import Path
import sys
import time
import types

from .claim_review import sha256
from .source_binding import _read, _record


def _same_loaded(actual, expected, owner):
    if isinstance(expected, types.FunctionType) and expected.__module__ == owner:
        if not isinstance(actual, types.FunctionType):
            return False
        # contextlib.contextmanager retains a canonical stdlib wrapper with a
        # closure over the actual owned function. Check that function too.
        expected_globals = expected.__globals__
        defining_globals = (vars(sys.modules[owner]) if expected_globals.get('__name__') == owner
                            else expected_globals)
        actual_cells = actual.__closure__ or ()
        expected_cells = expected.__closure__ or ()
        return (actual.__code__ == expected.__code__ and actual.__globals__ is defining_globals
                and len(actual_cells) == len(expected_cells)
                and all(_same_loaded(left.cell_contents, right.cell_contents, owner)
                        for left, right in zip(actual_cells, expected_cells))
                and actual.__defaults__ == expected.__defaults__
                and actual.__kwdefaults__ == expected.__kwdefaults__)
    if isinstance(expected, type) and expected.__module__ == owner:
        if not isinstance(actual, type) or vars(actual).keys() != vars(expected).keys():
            return False
        for name, value in vars(expected).items():
            if name in {'__dict__', '__weakref__'}:
                continue
            if not _same_loaded(vars(actual)[name], value, owner):
                return False
        return True
    if isinstance(expected, (types.FunctionType, types.ModuleType, type)):
        return actual is expected
    return actual == expected


def loaded_bindings():
    """Check the executed constructor, Host dependencies and helper aliases.

    Fresh canonical namespaces check constants and imported aliases as well as
    code. A stale loaded function or monkeypatch supplies no construction proof.
    This intentionally covers this one constructor, not arbitrary Python code.
    """
    from . import chronology_controls, host, selector, runner, evaluator, source_binding, claim_review
    modules = (chronology_controls, host, selector, source_binding, claim_review, sys.modules[__name__])
    records = {}
    for module in modules:
        raw = Path(module.__file__).read_bytes()
        namespace = {'__name__': module.__name__, '__package__': module.__package__,
                     '__file__': module.__file__}
        exec(compile(raw, module.__file__, 'exec'), namespace)
        for name, expected in namespace.items():
            if name.startswith('__'):
                continue
            if name not in vars(module) or not _same_loaded(vars(module)[name], expected, module.__name__):
                raise ValueError('loaded constructor dependency differs: ' + module.__name__ + '.' + name)
        records[Path(module.__file__).name] = sha256(raw)
    for module, names in ((runner, ('tree_hash', 'digest', 'Path', 'stat', 'hashlib', 'json')),
                          (evaluator, ('load_cases', 'Path', 'hashlib', 'json'))):
        raw = Path(module.__file__).read_bytes()
        namespace = {'__name__': module.__name__, '__package__': module.__package__,
                     '__file__': module.__file__}
        exec(compile(raw, module.__file__, 'exec'), namespace)
        for name in names:
            if not _same_loaded(getattr(module, name), namespace[name], module.__name__):
                raise ValueError('loaded constructor helper differs: ' + name)
        if module is evaluator and any(getattr(module, key) != namespace[key] for key in (
                'FIXTURE_SHA256', 'PUBLIC_FIXTURE_SHA256', 'CASES_SHA256', 'CONTRACT_SHA256')):
            raise ValueError('loaded constructor fixture constants differ')
        records[Path(module.__file__).name] = sha256(raw)
    return records


def begin(root, plan):
    """Retain actual inputs before initialization or any Host operation."""
    from .runner import tree_hash
    root = Path(root)
    source = Path(__file__).parent
    digest, records = tree_hash(source)
    target = root / 'construction-inputs'
    target.mkdir()
    copies = {}
    for name, record in records.items():
        path = target / 'source' / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((source / name).read_bytes())
        path.chmod(int(record['mode'], 8))
        copies[name] = _record(root, path)
    control = target / 'trace.json'
    control.write_text(json.dumps(plan, sort_keys=True) + '\n')
    return {'module': 'foundation.conformance.chronology_controls', 'function': 'fixture',
            'arguments': {'plan': copy.deepcopy(plan), 'root': str(root.parent.resolve())},
            'started_at_ns': time.monotonic_ns(), 'source_digest': digest,
            'sources': copies, 'input': _record(root, control), 'loaded_before': loaded_bindings()}


def finish(root, invocation):
    """Record completion only after actual raw construction and host effects."""
    from .runner import tree_hash
    root = Path(root)
    result = copy.deepcopy(invocation)
    result['loaded_after'] = loaded_bindings()
    result['source_after'] = tree_hash(Path(__file__).parent)[0]
    result['outputs'] = {name: _record(root, root / name) for name in (
        'stdout.jsonl', 'journal.jsonl', 'final.json', 'initial.json',
        'initial-files.json', 'final-files.json', 'chronology.json', 'prompt.json')}
    result['completed_at_ns'] = time.monotonic_ns()
    return result


def emissions(observation):
    """Return exact source-proved no-Host-call positions, or no proof.

    The canonical generic D branch emits a raw item and continues without
    Host.call. This is a property of executed source/control, not tool names or
    the wording of a transport error. Every other invocation remains unknown.
    """
    from .runner import tree_hash
    from .chronology_controls import emission
    try:
        if observation['process']['kind'] != 'sensitivity-only':
            return None
        paths = observation['observer_paths']
        root = Path(paths['stdout']).resolve().parent
        metadata_path = Path(paths['metadata']).resolve()
        if metadata_path != root / 'metadata.json':
            return None
        raw = metadata_path.read_bytes()
        if sha256(raw) != observation['process']['metadata_sha256']:
            return None
        invocation = json.loads(raw)['construction']
        if (invocation['module'] != 'foundation.conformance.chronology_controls'
                or invocation['function'] != 'fixture'
                or invocation['arguments']['root'] != str(root.parent)
                or invocation['completed_at_ns'] <= invocation['started_at_ns']):
            return None
        digest, sources = tree_hash(Path(__file__).parent)
        if (invocation['source_digest'] != digest or invocation['source_after'] != digest
                or set(invocation['sources']) != set(sources)
                or invocation['loaded_before'] != invocation['loaded_after']
                or invocation['loaded_after'] != loaded_bindings()):
            return None
        for name, record in invocation['sources'].items():
            _read(root, record)
            if {'sha256': record['sha256'], 'mode': record['mode']} != sources[name]:
                return None
        control = json.loads(_read(root, invocation['input']))
        if control != invocation['arguments']['plan']:
            return None
        for record in invocation['outputs'].values():
            _read(root, record)
        for name, field in (('initial.json', 'initial'), ('final.json', 'final'),
                            ('initial-files.json', 'initial_files'), ('final-files.json', 'final_files')):
            if json.loads(_read(root, invocation['outputs'][name])) != observation[field]:
                return None
        if [json.loads(line) for line in _read(root, invocation['outputs']['journal.jsonl']).splitlines()] != observation['events']:
            return None
        if invocation['outputs']['stdout.jsonl']['sha256'] != observation['process']['stdout_sha256']:
            return None
        stream = [json.loads(line) for line in (root / 'stdout.jsonl').read_bytes().splitlines()]
        expected = [emission(token.split(':', 1)[1]) for token in control['trace'] if token.startswith('D:')]
        if not expected:
            return None
        selected = []
        for item in expected:
            matches = [number for number, event in enumerate(stream, 1)
                       if event == {'type': 'item.completed', 'item': item}]
            if len(matches) != 1:
                return None
            selected.append(matches[0])
        if len(set(selected)) != len(selected):
            return None
        return selected
    except (OSError, KeyError, ValueError, TypeError, AttributeError):
        return None


def independent_effect_coverage(observation, auxiliary):
    """Prove zero residual material effects without declaring raw capture whole.

    Only a caller-witnessed canonical construction can prove its emitted items
    never invoked Host. All actual operations must separately corroborate the
    journal, state and measured files. Obligation/meaning/order checks still use
    the original evidence and determine whether these facts are sufficient.
    """
    from .runner import verify_stream, read_host_capture
    try:
        selected = emissions(observation)
        if not selected or auxiliary['contradictions']:
            return False
        paths = observation['observer_paths']
        stream = [json.loads(line) for line in Path(paths['stdout']).read_bytes().splitlines()]
        unresolved = [{'tool': stream[line - 1]['item']['tool'],
                       'args': stream[line - 1]['item']['arguments']} for line in selected]
        if auxiliary['unresolved'] != unresolved:
            return False
        journal, journal_valid = read_host_capture(paths['journal'], lines=True)
        state, state_valid = read_host_capture(paths['state'])
        projection = [event for line, event in enumerate(stream, 1) if line not in selected]
        return bool(journal_valid and state_valid and journal == observation['events']
                    and state == observation['final'] and journal
                    and journal[-1]['after'] == observation['final_files']
                    and verify_stream(journal, projection))
    except (OSError, KeyError, ValueError, TypeError, AttributeError):
        return False
