"""Observer-owned classifications and authoritative database snapshots."""
from contextlib import closing
import hashlib
import json
import sqlite3
from pathlib import Path


def native_operation_error(item, allowed_tools):
    kind = item.get('type')
    if kind == 'mcp_tool_call':
        if item.get('server') != 'workbench' or item.get('tool') not in allowed_tools:
            return 'unexpected non-workbench tool attempt'
    elif kind and kind not in {'agent_message', 'reasoning', 'error'}:
        return 'unexpected native tool operation: ' + kind
    return None


def authoritative_snapshot(path):
    """Read complete authoritative tables without creating/modifying the database.

    Hashes bracket the read; an unsettled or malformed database is unknown.
    Diagnostic tables are deliberately outside this semantic equality boundary.
    """
    path = Path(path)
    try:
        if any(Path(str(path) + suffix).exists() for suffix in ('-wal', '-journal')):
            return {'complete': False}
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as db:
            db.execute('BEGIN')
            tables = {}
            for name, columns in (('ownership', ['id', 'owner', 'fence']),
                                  ('ledger', ['operation', 'amount'])):
                schema = [list(row) for row in db.execute('PRAGMA table_info(' + name + ')')]
                if [row[1] for row in schema] != columns:
                    raise ValueError('unexpected authoritative schema')
                rows = [list(row) for row in db.execute('SELECT * FROM ' + name)]
                rows.sort(key=lambda row: json.dumps(row, ensure_ascii=False, allow_nan=False))
                definition = [list(row) for row in db.execute(
                    'SELECT type,name,sql FROM sqlite_master WHERE tbl_name=? ORDER BY type,name', (name,))]
                tables[name] = {'schema': schema, 'definition': definition, 'rows': rows}
        after = hashlib.sha256(path.read_bytes()).hexdigest()
        if before != after:
            raise ValueError('database changed during snapshot')
        return {'complete': True, 'database_sha256': before, 'tables': tables}
    except (OSError, sqlite3.Error, ValueError, TypeError):
        return {'complete': False}


def authoritative_unchanged(observation):
    """Tri-state equality; historical identical bytes remain sufficient proof."""
    before = observation.get('initial_files', {}).get('synthetic.sqlite')
    after = observation.get('final_files', {}).get('synthetic.sqlite')
    snapshots = observation.get('authoritative_snapshots')
    if snapshots is None:
        return True if before and before == after else None
    try:
        if observation.get('process', {}).get('kind') == 'actual-codex':
            paths = observation.get('observer_paths', {}).get('authoritative_databases', {})
            if any(authoritative_snapshot(paths[phase]) != snapshots[phase] for phase in ('initial', 'final')):
                return None
        pairs = [(snapshots['initial'], before), (snapshots['final'], after)]
        for snapshot, digest in pairs:
            if snapshot.get('complete') is not True or not digest or snapshot.get('database_sha256') != digest:
                return None
            if set(snapshot['tables']) != {'ownership', 'ledger'}:
                return None
            for name, columns in (('ownership', ['id', 'owner', 'fence']), ('ledger', ['operation', 'amount'])):
                table = snapshot['tables'][name]
                if (not isinstance(table['schema'], list) or
                        [row[1] for row in table['schema']] != columns or
                        any(not isinstance(row, list) or len(row) != 6 for row in table['schema']) or
                        not isinstance(table.get('definition'), list) or not table['definition'] or
                        any(not isinstance(row, list) or len(row) != 3 for row in table['definition']) or
                        not isinstance(table['rows'], list) or
                        any(not isinstance(row, list) or len(row) != len(columns) for row in table['rows'])):
                    return None
        return snapshots['initial']['tables'] == snapshots['final']['tables']
    except (OSError, KeyError, TypeError, IndexError, AttributeError):
        return None
