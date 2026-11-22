"""Exercise UTF-8 asset IO even on a developer machine with a UTF-8 locale."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


class Utf8AssetTests(unittest.TestCase):
    def run_cli(self, script, *args):
        result = subprocess.run(
            [sys.executable, '-X', 'warn_default_encoding', '-W', 'error::EncodingWarning', script, *args],
            capture_output=True, timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        return json.loads(result.stdout)

    def test_palette_audit_reads_real_stylesheets_as_utf8(self):
        report = self.run_cli(ROOT / 'scripts/test_palette_contrast.py')
        self.assertTrue(report['passed'])

    def test_icon_build_and_check_round_trip_unicode_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / 'scripts/build_icons.py'
            script.parent.mkdir()
            shutil.copyfile(ROOT / 'scripts/build_icons.py', script)
            shutil.copytree(ROOT / 'dist/assets/icons', root / 'dist/assets/icons')
            (root / 'dist/js').mkdir()
            package = root / 'django-theme/src/nova_admin'
            package.mkdir(parents=True)
            self.run_cli(script)
            self.run_cli(script, '--check')
            for path in [root / 'dist/js/open-icons.js', package / 'icons.json']:
                with self.subTest(path=path):
                    self.assertEqual(path.read_text(encoding='utf-8'),
                                     (ROOT / path.relative_to(root)).read_text(encoding='utf-8'))

    def test_css_budget_records_and_checks_a_utf8_source_map(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / 'scripts/css_budget.py'
            script.parent.mkdir()
            shutil.copyfile(ROOT / 'scripts/css_budget.py', script)
            dist = root / 'dist'
            dist.mkdir()
            (dist / 'site.min.css').write_text('/*# sourceMappingURL=site.map */', encoding='utf-8')
            source_map = {'version': 3, 'sources': ['主题.css'], 'sourcesContent': ['/* 配色 */'],
                          'mappings': 'AAAA'}
            (dist / 'site.map').write_text(json.dumps(source_map, ensure_ascii=False), encoding='utf-8')
            baseline = root / 'budget.json'
            self.run_cli(script, '--record', '--baseline', baseline)
            self.assertEqual(self.run_cli(script, '--baseline', baseline)['status'], 'passed')
