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

    def test_fixture_server_is_required_without_granting_permissions(self):
        flags = workbench_permissions()
        settings = tomllib.loads('\n'.join(
            flags[index + 1] for index, flag in enumerate(flags) if flag == '-c'))
        self.assertIs(True, settings['mcp_servers']['workbench']['required'])
        self.assertEqual({'required', 'enabled_tools'},
                         set(settings['mcp_servers']['workbench']))
        self.assertNotIn('approval_policy', settings)
        self.assertNotIn('sandbox_mode', settings)

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

    def test_nested_rules_directory_symlinks_cannot_drop_caller_restrictions(self):
        for relative in ('team', 'team/project'):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                external = root / 'external'; external.mkdir()
                (external / 'deny.rules').write_text('prefix_rule(pattern=["git", "push"], decision="forbidden")\n')
                source, target = root / 'source', root / 'target'
                link = source / 'rules' / relative; link.parent.mkdir(parents=True)
                link.symlink_to(external, target_is_directory=True)
                with self.assertRaises(ValueError):
                    prepare_policy(target, source)

    def test_verification_rejects_injected_nested_rules_directory_symlinks(self):
        for relative in ('team', 'team/project'):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                target = root / 'target'
                receipt = prepare_policy(target, root / 'source')
                external = root / 'external'; external.mkdir()
                (external / 'deny.rules').write_text('prefix_rule(pattern=["git", "push"], decision="forbidden")\n')
                link = target / 'rules' / relative; link.parent.mkdir(parents=True)
                link.symlink_to(external, target_is_directory=True)
                with self.assertRaises(ValueError):
                    verify_policy(target, receipt)

    def test_regular_nested_rules_and_both_instruction_files_survive(self):
        with tempfile.TemporaryDirectory() as temp:
            source, target = Path(temp) / 'source', Path(temp) / 'target'
            expected = {'rules/z.rules': b'z\n', 'rules/team/project/deny.rules': b'deny\n',
                        'AGENTS.md': b'ordinary\n', 'AGENTS.override.md': b'override\n'}
            for relative, raw in expected.items():
                path = source / relative; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
            receipt = prepare_policy(target, source)
            self.assertEqual(['rules/team/project/deny.rules', 'rules/z.rules', 'AGENTS.md', 'AGENTS.override.md'], list(receipt['policy_files']))
            self.assertEqual(expected, {relative: (target / relative).read_bytes() for relative in receipt['policy_files']})
            verify_policy(target, receipt)
            (target / 'rules/team/project/deny.rules').write_text('allow\n')
            with self.assertRaisesRegex(ValueError, 'rules or instructions changed'):
                verify_policy(target, receipt)

    def test_inaccessible_nested_rules_enumeration_fails_closed(self):
        for phase in ('prepare', 'verify'):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as temp:
                source, target = Path(temp) / 'source', Path(temp) / 'target'
                (source / 'rules/team').mkdir(parents=True)
                (source / 'rules/team/deny.rules').write_text('deny\n')
                receipt = prepare_policy(target, source) if phase == 'verify' else None
                inaccessible = (target if phase == 'verify' else source) / 'rules/team'
                original = os.scandir
                def scandir(path):
                    if Path(path) == inaccessible:
                        raise PermissionError('synthetic inaccessible policy directory')
                    return original(path)
                with patch('os.scandir', side_effect=scandir), self.assertRaises((ValueError, PermissionError)):
                    if phase == 'prepare': prepare_policy(target, source)
                    else: verify_policy(target, receipt)

    def test_rule_file_and_instruction_symlinks_still_fail_closed(self):
        for relative in ('rules/deny.rules', 'AGENTS.md', 'AGENTS.override.md'):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as temp:
                root = Path(temp); source = root / 'source'; source.mkdir()
                external = root / 'external'; external.write_text('deny\n')
                link = source / relative; link.parent.mkdir(parents=True, exist_ok=True); link.symlink_to(external)
                with self.assertRaises(ValueError): prepare_policy(root / 'target', source)


if __name__ == '__main__':
    unittest.main()
