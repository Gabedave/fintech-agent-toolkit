"""A rendered playbook must carry the same typed delivery policy as its router.

The independently fixed installed-decision companion remains the behavioral gate;
these static controls detect the conflicting-reference regression before model calls.
"""
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CompanyDeliveryPolicy(unittest.TestCase):
    def test_first_plan_minimum_includes_separate_installation_authority(self):
        required = {
            'edit', 'commit', 'push', 'open-pull-request',
            'merge', 'deploy', 'user-installation',
        }
        for name in ('example', 'gabedave'):
            profile_path = ROOT / 'profiles' / (name + '.json')
            profile = json.loads(profile_path.read_text())
            with self.subTest(default=profile['delivery_default']), tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp).resolve() / 'output'
                result = subprocess.run([
                    sys.executable, '-B', str(ROOT / 'foundation/render.py'),
                    '--profile', str(profile_path), '--output', str(output),
                    '--source-commit', '1234567890abcdef1234567890abcdef12345678',
                ], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                router = output / 'plugins' / profile['plugin_name'] / 'skills' / profile['router'] / 'SKILL.md'
                minimum = next(
                    line.split('at minimum', 1)[0]
                    for line in router.read_text().splitlines()
                    if 'first working plan' in line and 'at minimum' in line
                )
                self.assertLessEqual(required, set(re.findall(r'`([^`]+)`', minimum)))

    def test_active_installation_boundary_preserves_existing_task_authority(self):
        for name in ('example', 'gabedave'):
            profile_path = ROOT / 'profiles' / (name + '.json')
            profile = json.loads(profile_path.read_text())
            with self.subTest(default=profile['delivery_default']), tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp).resolve() / 'output'
                result = subprocess.run([
                    sys.executable, '-B', str(ROOT / 'foundation/render.py'),
                    '--profile', str(profile_path), '--output', str(output),
                    '--source-commit', '1234567890abcdef1234567890abcdef12345678',
                ], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                skill = output / 'plugins' / profile['plugin_name'] / 'skills' / profile['router']
                self.assertIn('references/playbooks.md#delivery-and-authorization', (skill / 'SKILL.md').read_text())
                for relative in ('references/playbooks.md',):
                    text = (skill / relative).read_text()
                    for clause in (
                        'Personal or user-wide active plugin/skill installation changes are a separate authority boundary',
                        'perform them only within applicable explicit task/session authorization',
                        'Honor authorization already granted within its scope, without asking again or extending it',
                        'Authorized product-repository work and owned disposable fixture setup retain their existing task scope',
                        'Merge, deployment, ticket updates, and team messages require separate explicit authorization',
                        'Readiness and green CI never grant merge or deployment authority',
                    ):
                        self.assertIn(clause, text)

    def test_router_and_loaded_playbook_agree_for_both_defaults(self):
        for name in ('example', 'gabedave'):
            profile_path = ROOT / 'profiles' / (name + '.json')
            profile = json.loads(profile_path.read_text())
            with self.subTest(default=profile['delivery_default']), tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp).resolve() / 'output'
                result = subprocess.run([
                    sys.executable, '-B', str(ROOT / 'foundation/render.py'),
                    '--profile', str(profile_path), '--output', str(output),
                    '--source-commit', '1234567890abcdef1234567890abcdef12345678',
                ], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                skill = output / 'plugins' / profile['plugin_name'] / 'skills' / profile['router']
                router = (skill / 'SKILL.md').read_text()
                playbooks = (skill / 'references/playbooks.md').read_text()
                policy = 'Default delivery: ' + profile['delivery_default'] + '.'
                self.assertIn('references/playbooks.md#delivery-and-authorization', router)
                self.assertIn(policy, playbooks)
                self.assertNotIn('pair every non-trivial production repository-editing playbook', playbooks)
                if profile['delivery_default'] == 'local-only':
                    self.assertIn('Only local editing is included by default', playbooks)
                    self.assertIn('additional stages require explicit user authorization', playbooks)
                else:
                    self.assertIn('requested delivery includes edit, commit, push', playbooks)
                    self.assertIn('unless the user or repository narrows those stages', playbooks)
                self.assertIn('when the company policy and user authorize', playbooks)
                ci = (skill.parent / 'ci-babysit/SKILL.md').read_text().split('---', 2)[1]
                self.assertIn('authorized delivery includes CI follow-through', ci)
                self.assertNotIn('Use for the default delivery', ci)


if __name__ == '__main__':
    unittest.main()
