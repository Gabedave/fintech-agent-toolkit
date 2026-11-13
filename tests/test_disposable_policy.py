import os
from pathlib import Path
import tempfile
import tomllib
import unittest
from unittest.mock import patch

from foundation.conformance.policy import prepare_policy, safe_env, verify_policy
from foundation.conformance.runner import workbench_permissions


class DisposablePolicyTests(unittest.TestCase):
    def test_explicit_restrictions_and_rules_survive_install_configuration(self):
        with tempfile.TemporaryDirectory() as temp:
            source, target = Path(temp) / 'source', Path(temp) / 'target'
            (source / 'rules').mkdir(parents=True)
            (source / 'config.toml').write_text('approval_policy="never"\napprovals_reviewer="user"\n'
                'sandbox_mode="read-only"\n[permissions.restricted]\nnetwork_access=false\n')
            (source / 'rules/default.rules').write_text('prefix_rule(pattern=["git", "push"], decision="forbidden")\n')
            (source / 'AGENTS.md').write_text('Keep this instruction.\n')
            receipt = prepare_policy(target, source)
            self.assertEqual({}, receipt['added_review_defaults'])
            with (target / 'config.toml').open('a') as handle:
                handle.write('\n[plugins."fixture@test"]\nenabled=true\n')
            verify_policy(target, receipt)
            parsed = tomllib.loads((target / 'config.toml').read_text())
            self.assertEqual('never', parsed['approval_policy'])
            self.assertFalse(parsed['permissions']['restricted']['network_access'])
            (target / 'rules/default.rules').write_text('')
            with self.assertRaisesRegex(ValueError, 'rules or instructions changed'):
                verify_policy(target, receipt)

    def test_absent_defaults_request_review_and_do_not_grant_tools(self):
        with tempfile.TemporaryDirectory() as temp:
            receipt = prepare_policy(Path(temp) / 'target', Path(temp) / 'missing')
            self.assertEqual({'approval_policy': 'on-request', 'approvals_reviewer': 'auto_review'},
                             receipt['added_review_defaults'])
            self.assertFalse(receipt['permission_grant_proved'])
        flags = ' '.join(workbench_permissions())
        self.assertNotIn('approval_mode', flags)
        self.assertNotIn('ignore-rules', flags)

    def test_policy_mutation_is_detected_and_target_cannot_be_reused(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp) / 'home'
            receipt = prepare_policy(home, Path(temp) / 'missing')
            with self.assertRaises(ValueError):
                prepare_policy(home, Path(temp) / 'missing')
            (home / 'config.toml').write_text('approval_policy="never"\n')
            with self.assertRaisesRegex(ValueError, 'security configuration changed'):
                verify_policy(home, receipt)

    def test_environment_preserves_home_and_sandbox_but_excludes_provider_secrets(self):
        with patch.dict(os.environ, {'HOME': '/ordinary/home', 'PATH': '/bin',
                                     'OPENAI_API_KEY': 'not-for-inheritance',
                                     'CODEX_SANDBOX_NETWORK_DISABLED': '1'}, clear=True):
            env = safe_env(Path('/disposable'))
            self.assertEqual('/ordinary/home', env['HOME'])
            self.assertEqual('/disposable', env['CODEX_HOME'])
            self.assertEqual('1', env['CODEX_SANDBOX_NETWORK_DISABLED'])
            self.assertNotIn('OPENAI_API_KEY', env)

    def test_symlinked_policy_is_not_silently_omitted(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'source'
            source.mkdir()
            (Path(temp) / 'rules').mkdir()
            (source / 'rules').symlink_to(Path(temp) / 'rules', target_is_directory=True)
            with self.assertRaises(ValueError):
                prepare_policy(Path(temp) / 'target', source)


if __name__ == '__main__':
    unittest.main()
