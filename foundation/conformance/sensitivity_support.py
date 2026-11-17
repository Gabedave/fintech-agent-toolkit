"""Fixed test expectations and disposable setup, never actual model evidence."""
import json
from types import SimpleNamespace


# Independent expected values, not predictions derived from the evaluator.
# Each case copies its table so mutation cannot change another case's oracle.
REVIEW_INCOMPLETE = {
    'missing': 'incomplete', 'confirmed': 'incomplete', 'uncertain': 'incomplete',
    'violated': 'fail', 'stale-confirmed': 'incomplete',
    'mismatched-confirmed': 'incomplete', 'stale-violated': 'incomplete',
}
REVIEW_FAIL = {
    'missing': 'fail', 'confirmed': 'fail', 'uncertain': 'fail',
    'violated': 'fail', 'stale-confirmed': 'fail',
    'mismatched-confirmed': 'fail', 'stale-violated': 'fail',
}
REVIEW_ELIGIBLE = {
    'missing': 'incomplete', 'confirmed': 'pass', 'uncertain': 'incomplete',
    'violated': 'fail', 'stale-confirmed': 'incomplete',
    'mismatched-confirmed': 'incomplete', 'stale-violated': 'incomplete',
}
KNOWN_FAILURE_FROM_REVIEW = {
    'missing': False, 'confirmed': False, 'uncertain': False,
    'violated': True, 'stale-confirmed': False,
    'mismatched-confirmed': False, 'stale-violated': False,
}
KNOWN_FAILURE_ALREADY_PROVED = {
    'missing': True, 'confirmed': True, 'uncertain': True,
    'violated': True, 'stale-confirmed': True,
    'mismatched-confirmed': True, 'stale-violated': True,
}


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def prepare_candidate(root, spec, skill_text):
    """Build the same synthetic installation for the real-pipe controls."""
    root.mkdir(parents=True)
    profile = {'plugin_name': 'synthetic-workflow', 'router': 'workflow'}
    candidate = root / 'candidate'
    installed = candidate / 'plugins' / profile['plugin_name']
    (installed / 'skills/workflow').mkdir(parents=True)
    (installed / 'skills/workflow/SKILL.md').write_text(skill_text)
    save(candidate / 'foundation-lock.json', {
        'generated_tree_digest': 'synthetic-generated',
        'foundation': {'version': '1', 'commit': 'synthetic-source',
                       'digest': 'synthetic-foundation'},
    })
    save(root / 'profile.json', profile)
    home = root / 'private-home'
    home.mkdir()
    save(root / 'control.json', spec)
    args = SimpleNamespace(
        candidate=str(candidate), profile=str(root / 'profile.json'), model=None,
        timeout_seconds=2, installation_completed_ns=1,
        candidate_revision='synthetic-revision', contract_binding='unverified',
        codex_config_sha256='synthetic-config', effective_model='synthetic-local-producer',
        profile_role='synthetic-adopter', fixtures=None,
    )
    return profile, installed, home, args
