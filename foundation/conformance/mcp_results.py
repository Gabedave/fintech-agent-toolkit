"""Mechanical MCP response decoding, independent of operation success or denial."""
import json


def completion(item):
    """Return decoded Host results and whether a concrete response was returned.

    A returned Host error is still a concrete result that can match its journal.
    A missing response or transport error cannot establish rejection before an
    effect. This decoder provides neither source authentication nor authority.
    """
    value = item.get('result')
    results = []
    if isinstance(value, dict):
        contents = value.get('content', [])
        if not isinstance(contents, list):
            return [], False
        for content in contents:
            if not isinstance(content, dict) or content.get('type') != 'text':
                continue
            try:
                results.append(json.loads(content['text']))
            except (ValueError, KeyError, TypeError):
                continue
    return results, bool(results) and not item.get('error')
