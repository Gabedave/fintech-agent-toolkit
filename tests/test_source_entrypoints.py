"""Real source-file entrypoints must reject caches before repository imports."""
import importlib.util
import marshal
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINTS = ('release_smoke.py', 'evaluate_behavior.py', 'evaluate_review_quality.py')


class SourceEntrypointTests(unittest.TestCase):
    def copy_candidate(self, directory):
        candidate = Path(directory) / 'candidate'
        shutil.copytree(ROOT, candidate, ignore=shutil.ignore_patterns('.git', '__pycache__', '*.pyc', '*.pyo'))
        return candidate

    def run_entrypoint(self, candidate, entrypoint, *args, disable_writes=True, cache_prefix=None):
        env = dict(os.environ)
        env.pop('PYTHONPATH', None)
        env.pop('PYTHONPYCACHEPREFIX', None)
        env.pop('PYTHONDONTWRITEBYTECODE', None)
        if disable_writes:
            env['PYTHONDONTWRITEBYTECODE'] = '1'
        if cache_prefix is not None:
            env['PYTHONPYCACHEPREFIX'] = str(cache_prefix)
        return subprocess.run([sys.executable, str(candidate / 'scripts' / entrypoint), *args],
                              env=env, capture_output=True, text=True, timeout=30)

    def test_valid_timestamp_cache_never_executes_at_any_frontdoor(self):
        modules = ['scripts/native_evidence.py', 'scripts/native_review_inputs.py', 'scripts/process_control.py',
                   'scripts/argparse.pyc']
        modules.append('foundation/conformance/runner.py' if (ROOT / 'foundation').is_dir()
                       else 'scripts/foundation_source.py')
        for module in modules:
            with self.subTest(module=module), tempfile.TemporaryDirectory() as directory:
                candidate = self.copy_candidate(directory)
                source = candidate / module
                marker = Path(directory) / 'unexpected-cached-execution'
                payload = f'open({str(marker)!r}, "w").write("cached code ran")\n'
                if source.suffix == '.pyc':
                    # A legacy cache can shadow stdlib argparse before repository imports.
                    cache, mtime, size = source, 0, 0
                    payload += 'raise SystemExit(91)\n'
                else:
                    payload += source.read_text()
                    info = source.stat()
                    cache = Path(importlib.util.cache_from_source(str(source)))
                    mtime, size = int(info.st_mtime), info.st_size
                cache.parent.mkdir(exist_ok=True)
                # Timestamp and source-size fields match the untouched real source.
                cache.write_bytes(importlib.util.MAGIC_NUMBER + struct.pack('<III', 0, mtime, size)
                                  + marshal.dumps(compile(payload, str(source), 'exec')))
                for entrypoint in ENTRYPOINTS:
                    with self.subTest(entrypoint=entrypoint):
                        result = self.run_entrypoint(candidate, entrypoint, '--help')
                        self.assertFalse(marker.exists(), 'cached code executed before the source guard')
                        self.assertNotEqual(0, result.returncode)
                        self.assertIn('source-only verification', result.stderr)
                        self.assertIn(str(cache), result.stderr)
                        self.assertTrue(cache.exists(), 'verification must not delete rejected artifacts')

    def test_external_cache_prefix_cannot_bypass_checked_source_trees(self):
        with tempfile.TemporaryDirectory() as directory:
            candidate = self.copy_candidate(directory)
            source = (candidate / 'scripts/native_evidence.py').resolve()
            marker = Path(directory) / 'unexpected-prefix-cache-execution'
            prefix = Path(directory) / 'external-cache'
            with mock.patch.object(sys, 'pycache_prefix', str(prefix)):
                cache = Path(importlib.util.cache_from_source(str(source)))
            cache.parent.mkdir(parents=True)
            info = source.stat()
            payload = f'open({str(marker)!r}, "w").write("cached code ran")\n' + source.read_text()
            cache.write_bytes(importlib.util.MAGIC_NUMBER + struct.pack('<III', 0, int(info.st_mtime), info.st_size)
                              + marshal.dumps(compile(payload, str(source), 'exec')))
            for entrypoint in ENTRYPOINTS:
                with self.subTest(entrypoint=entrypoint):
                    result = self.run_entrypoint(candidate, entrypoint, '--help', cache_prefix=prefix)
                    self.assertFalse(marker.exists(), 'unchecked external bytecode executed')
                    self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                    self.assertTrue(cache.exists())

    def test_clean_standard_launches_succeed_without_creating_bytecode(self):
        with tempfile.TemporaryDirectory() as directory:
            candidate = self.copy_candidate(directory)
            for entrypoint in ENTRYPOINTS:
                with self.subTest(entrypoint=entrypoint):
                    option = '--help' if entrypoint == 'release_smoke.py' else '--check'
                    result = self.run_entrypoint(candidate, entrypoint, option, disable_writes=False)
                    self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                    self.assertEqual([], list(candidate.rglob('*.pyc')))


if __name__ == '__main__':
    unittest.main()
