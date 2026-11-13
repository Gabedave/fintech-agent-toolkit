"""Disposable candidate state with the caller's ordinary security policy intact."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tomllib


SECURITY_KEYS = (
    'approval_policy', 'approvals_reviewer', 'sandbox_mode',
    'sandbox_workspace_write', 'permissions', 'permission_profile',
    'shell_environment_policy', 'projects', 'default_permissions',
)


def safe_env(home):
    allowed = ('PATH', 'HOME', 'TMPDIR', 'LANG', 'LC_ALL', 'SYSTEMROOT',
               'SSL_CERT_FILE', 'CODEX_CA_CERTIFICATE')
    env = {key: os.environ[key] for key in allowed if key in os.environ}
    env.update({key: value for key, value in os.environ.items()
                if key.startswith('CODEX_SANDBOX_')})
    env['CODEX_HOME'] = str(home)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    return env


def _toml(value):
    if isinstance(value, dict):
        return '{' + ', '.join(json.dumps(k) + '=' + _toml(v)
                              for k, v in value.items()) + '}'
    if isinstance(value, list):
        return '[' + ', '.join(_toml(v) for v in value) + ']'
    if type(value) not in (str, bool, int, float):
        raise ValueError('unsupported security policy value')
    return json.dumps(value, allow_nan=False)


def prepare_policy(home, source=None):
    """Copy policy into a fresh owned home; never change the original account.

    Missing approval keys select ordinary interactive/automatic review, not a
    grant. Explicit policies always win. Provider settings and other installed
    plugins are intentionally outside this isolated candidate environment.
    """
    home = Path(home)
    source = Path(source or os.environ.get('CODEX_HOME', Path.home() / '.codex'))
    if home.resolve() == source.resolve() or (home / 'config.toml').exists():
        raise ValueError('policy target must be fresh disposable state')
    config = source / 'config.toml'
    parsed = tomllib.loads(config.read_text()) if config.exists() else {}
    if parsed.get('profile'):
        raise ValueError('selected configuration profile needs explicit policy resolution')
    selected = {key: parsed[key] for key in SECURITY_KEYS if key in parsed}
    defaults = {key: value for key, value in (
        ('approval_policy', 'on-request'), ('approvals_reviewer', 'auto_review'))
        if key not in selected}
    selected.update(defaults)
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (home / 'config.toml').open('x') as handle:
        handle.write('\n'.join(json.dumps(k) + '=' + _toml(v)
                               for k, v in selected.items()) + '\n')
    copied = {}
    if (source / 'rules').is_symlink():
        raise ValueError('symlinked rules directory requires explicit preservation')
    sources = [*sorted((source / 'rules').rglob('*.rules')),
               source / 'AGENTS.md', source / 'AGENTS.override.md']
    for path in sources:
        if path.is_symlink():
            raise ValueError('symlinked policy requires explicit preservation: ' + str(path))
        if not path.exists():
            continue
        relative = path.relative_to(source)
        target = home / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied[str(relative)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        'source_config_sha256': hashlib.sha256(config.read_bytes()).hexdigest() if config.exists() else None,
        'preserved_config_keys': sorted(set(parsed) & set(SECURITY_KEYS)),
        'security_config_sha256': hashlib.sha256(json.dumps(selected, sort_keys=True).encode()).hexdigest(),
        'added_review_defaults': defaults, 'policy_files': copied,
        'home_unchanged': safe_env(home).get('HOME') == os.environ.get('HOME'),
        'permission_grant_proved': False,
    }


def verify_policy(home, receipt):
    home = Path(home)
    parsed = tomllib.loads((home / 'config.toml').read_text())
    security = {key: parsed[key] for key in SECURITY_KEYS if key in parsed}
    if hashlib.sha256(json.dumps(security, sort_keys=True).encode()).hexdigest() != receipt['security_config_sha256']:
        raise ValueError('disposable security configuration changed')
    actual = {}
    for path in [*sorted((home / 'rules').rglob('*.rules')),
                 home / 'AGENTS.md', home / 'AGENTS.override.md']:
        if path.is_symlink():
            raise ValueError('disposable policy became a symbolic link')
        if path.exists():
            actual[str(path.relative_to(home))] = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != receipt['policy_files']:
        raise ValueError('disposable rules or instructions changed')
