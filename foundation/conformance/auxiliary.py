"""Separate auxiliary syntax from coverage through actual workbench effects.

An invocation can have changed files before Host.call appends its event, and an
appended event precedes the state save and raw acknowledgment. None of those
prefixes is a terminal coverage attestation. This module derives knowledge from
the retained sources; observation flags and a timeout alone grant no knowledge.
"""
import json


def assess(observation, stream=None, chronology=None):
    from .chronology import arguments, capture, read_stream
    from .mcp_results import completion
    from .runner import read_host_capture

    paths = observation.get('observer_paths', {})
    if not paths:
        # Original bounded, explicitly constructed sensitivity fixtures have no
        # actual observer transport. Actual runs never receive this fallback.
        complete = observation.get('process', {}).get('kind') == 'sensitivity-only'
        return {'effects_complete': complete, 'state_covered': complete,
                'contradictions': [], 'pending': not complete, 'legacy_fixture': complete,
                'source_supported': False, 'primary_complete': False, 'unresolved': []}
    try:
        journal, journal_valid = read_host_capture(paths['journal'], lines=True)
        _, state_valid = read_host_capture(paths['state'])
        process = observation.get('process', {})
        interrupted = bool(process.get('timed_out') or process.get('operational_error'))
        if stream is None:
            stream = read_stream(paths['stdout'], interrupted)
        evidence = chronology if chronology is not None else capture(observation)
    except (OSError, KeyError, ValueError, TypeError):
        return {'effects_complete': False, 'state_covered': False,
                'contradictions': [], 'pending': True, 'legacy_fixture': False,
                'source_supported': False, 'primary_complete': False, 'unresolved': []}

    coverage = evidence.get('coverage', {})
    primary_complete = bool(coverage) and all(
        value.get('from_process_start') is True and not value.get('gaps')
        and evidence.get('startup', {}).get(source)
        for source, value in coverage.items())
    # Old sensitivity-only fixtures have a separately fixed full-source
    # construction. A real capture always needs the producer sidecar above.
    if not coverage and not paths.get('capture') and not evidence.get('strict_capture'):
        primary_complete = bool(evidence.get('complete') and evidence.get('available'))
        if primary_complete and not interrupted and journal_valid and state_valid:
            from .runner import verify_stream
            if verify_stream(journal, stream):
                # Retain the old, explicitly complete sensitivity construction,
                # whose report IDs can describe visibility rather than RPC IDs.
                # No actual run receives this no-sidecar construction premise.
                return {'effects_complete': True, 'state_covered': True,
                        'contradictions': [], 'pending': False, 'legacy_fixture': True,
                        'source_supported': False, 'primary_complete': True, 'unresolved': []}

    starts = []
    completed = []
    unconfirmed = []
    ambiguous = False
    for number, event in enumerate(stream, 1):
        item = event.get('item', {})
        if item.get('type') != 'mcp_tool_call' or item.get('server') != 'workbench':
            continue
        kind = event.get('type')
        if kind not in {'item.started', 'item.completed'}:
            continue
        args = arguments(item)
        identity = (item.get('id'), item.get('tool'), json.dumps(args, sort_keys=True))
        if kind == 'item.started':
            starts.append({'identity': identity, 'tool': item.get('tool'),
                           'args': args, 'line': number, 'used': False})
            continue
        possible = [start for start in starts if not start['used'] and start['identity'] == identity]
        if len(possible) == 1:
            possible[0]['used'] = True
        if len(possible) != 1:
            ambiguous = True
        results, returned = completion(item)
        if not returned:
            # Completion of the transport request does not confirm its effect.
            # Keep the actual argument-specific scope even on a normal CLI exit.
            unconfirmed.append({'tool': item.get('tool'), 'args': args})
            continue
        completed.append({'tool': item.get('tool'), 'args': args,
                          'results': results, 'used': False})

    pending = [start for start in starts if not start['used']] + unconfirmed
    contradictions = []
    missing = False
    for event in journal:
        matches = [call for call in completed if not call['used']
                   and call['tool'] == event.get('tool') and call['args'] == event.get('arguments')
                   and event.get('result') in call['results']]
        if matches:
            matches[0]['used'] = True
            continue
        possible = [start for start in pending if start['tool'] == event.get('tool')
                    and start['args'] == event.get('arguments')]
        if possible or not primary_complete:
            missing = True
        else:
            # A complete, source-corroborated invocation/result cannot be
            # replaced by a contradictory complete journal event.
            contradictions.append('MCP journal not corroborated by Codex tool stream')
    if any(not call['used'] for call in completed):
        if journal_valid and not interrupted and primary_complete:
            contradictions.append('MCP journal not corroborated by Codex tool stream')
        else:
            missing = True
    complete = bool(primary_complete and journal_valid
                    and not pending and not ambiguous and not missing and not contradictions)
    from .source_binding import validate
    source_supported = validate(observation) is not None
    unresolved = pending + [call for call in completed if not call['used']]
    return {'effects_complete': complete, 'state_covered': complete and state_valid,
            'contradictions': sorted(set(contradictions)),
            'pending': not complete or not state_valid,
            'legacy_fixture': False, 'source_supported': source_supported,
            'primary_complete': primary_complete, 'unresolved': unresolved}


def mutations(observation, coverage):
    """Classify each delta against the actual unresolved operation effects."""
    events = observation.get('events', [])
    latest = events[-1]['after'] if events else observation.get('initial_files', {})
    final = observation.get('final_files', {})
    changed = sorted(name for name in latest.keys() | final.keys()
                     if latest.get(name) != final.get(name))
    if coverage.get('legacy_fixture'):
        return (changed, []) if coverage['effects_complete'] else ([], changed)
    if not coverage.get('source_supported') or not coverage.get('primary_complete'):
        return [], changed
    from .host import possible_file_effects
    facts = observation.get('initial', {}).get('facts', {})
    possible = set()
    for call in coverage.get('unresolved', []):
        scope = possible_file_effects(call['tool'], call['args'], facts)
        if scope is None:
            return [], changed
        possible.update(scope)
    return ([name for name in changed if name not in possible],
            [name for name in changed if name in possible])
