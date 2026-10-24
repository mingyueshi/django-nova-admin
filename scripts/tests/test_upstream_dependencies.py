import importlib.util
from importlib import metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).parents[1] / 'upstream_dependencies.py'
SPEC = importlib.util.spec_from_file_location('upstream_dependencies', SCRIPT)
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


class UpstreamDependencyTests(unittest.TestCase):
    def check(self, requirements, versions, *, python='3.12.14', platform='darwin'):
        def lookup(name):
            if name not in versions:
                raise metadata.PackageNotFoundError(name)
            return versions[name]
        return guard.check_requirements(
            {'requires-python': '>=3.12', 'dependencies': requirements},
            lookup=lookup, python=python, environment={'sys_platform': platform},
        )

    def test_declared_minimum_rejects_old_pin(self):
        report = self.check(['asgiref>=3.13'], {'asgiref': '3.12.1'})
        self.assertFalse(report['requirements_satisfied'])
        self.assertEqual(report['dependencies'][0]['status'], 'version-mismatch')

    def test_satisfying_version_passes(self):
        self.assertTrue(self.check(['asgiref>=3.13'], {'asgiref': '3.13.0'})['requirements_satisfied'])

    def test_missing_distribution_does_not_pass(self):
        report = self.check(['asgiref>=3.13'], {})
        self.assertFalse(report['requirements_satisfied'])
        self.assertEqual(report['dependencies'][0]['status'], 'missing')

    def test_python_requirement_is_checked(self):
        report = self.check([], {}, python='3.11.12')
        self.assertFalse(report['python_satisfied'])
        self.assertFalse(report['requirements_satisfied'])

    def test_inactive_marker_is_explicitly_not_applicable(self):
        report = self.check(['tzdata; sys_platform == "win32"'], {})
        self.assertTrue(report['requirements_satisfied'])
        self.assertEqual(report['dependencies'][0]['status'], 'not-applicable')

    def test_active_marker_requires_distribution(self):
        self.assertFalse(self.check(['tzdata; sys_platform == "win32"'], {}, platform='win32')['requirements_satisfied'])

    def test_prerelease_below_minimum_is_rejected(self):
        self.assertFalse(self.check(['asgiref>=3.13'], {'asgiref': '3.13.0rc1'})['requirements_satisfied'])

    def test_upper_bound_is_checked(self):
        self.assertFalse(self.check(['asgiref>=3.13,<4'], {'asgiref': '4.0.0'})['requirements_satisfied'])

    def test_url_or_extras_cannot_pass_from_version_alone(self):
        for requirement in ('asgiref @ https://example.invalid/a.whl', 'asgiref[unknown]>=3.13'):
            report = self.check([requirement], {'asgiref': '3.13.0'})
            self.assertFalse(report['requirements_satisfied'])
            self.assertEqual(report['dependencies'][0]['status'], 'unverified-url-or-extra')

    def test_cli_checks_origin_without_importing_django(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            (source / 'django').mkdir(parents=True)
            # A metadata/source-origin check must not execute this module.
            (source / 'django/__init__.py').write_text('raise AssertionError("do not import")\n')
            (source / 'pyproject.toml').write_text('[project]\nname="Django"\nrequires-python=">=3.12"\ndependencies=[]\n')
            env = {**os.environ, 'PYTHONPATH': str(source), 'PYTHONDONTWRITEBYTECODE': '1'}
            output = root / 'good.json'
            result = subprocess.run([sys.executable, str(SCRIPT), '--source-root', str(source), '--output', str(output)], env=env, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(output.read_text())['source_origin_matches'])
            other = root / 'other'
            (other / 'django').mkdir(parents=True)
            (other / 'django/__init__.py').write_text('raise AssertionError("do not import")\n')
            env['PYTHONPATH'] = str(other)
            output = root / 'wrong.json'
            result = subprocess.run([sys.executable, str(SCRIPT), '--source-root', str(source), '--output', str(output)], env=env, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertFalse(json.loads(output.read_text())['source_origin_matches'])


if __name__ == '__main__':
    unittest.main()
