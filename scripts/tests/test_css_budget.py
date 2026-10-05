import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('css_budget', Path(__file__).parents[1] / 'css_budget.py')
budget = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(budget)


class CSSBudgetTests(unittest.TestCase):
    def test_limits_and_inventory(self):
        base = {'files': {'a.css': {'limits': {'bytes': 20, 'gzip_bytes': 40}}}}
        self.assertEqual(budget.validate({'a.css': {'bytes': 20, 'gzip_bytes': 40}}, base), [])
        self.assertEqual(len(budget.validate({'a.css': {'bytes': 21, 'gzip_bytes': 40}}, base)), 1)
        self.assertTrue(budget.validate({}, base))

    def test_gzip_is_deterministic_without_modifying_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'dist').mkdir()
            path = root / 'dist/style.css'
            path.write_text('body { color: blue; }')
            first = budget.measurements(root)
            self.assertEqual(first, budget.measurements(root))
            self.assertEqual(path.read_text(), 'body { color: blue; }')

    def test_minification_needs_source_map(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'dist').mkdir()
            path = root / 'dist/style.min.css'
            path.write_text('body{color:blue}')
            with self.assertRaisesRegex(ValueError, 'requires a local source map'):
                budget.measurements(root)
            path.write_text('body{color:blue}/*# sourceMappingURL=style.css.map */')
            (path.parent / 'style.css.map').write_text(json.dumps({'version': 3, 'sources': ['style.css'], 'sourcesContent': ['body { color: blue; }'], 'mappings': 'AAAA'}))
            self.assertIn('dist/style.min.css', budget.measurements(root))

    def test_remote_source_map_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'dist').mkdir()
            (root / 'dist/style.min.css').write_text('/*# sourceMappingURL=https://example.invalid/map */')
            with self.assertRaisesRegex(ValueError, 'neighboring'):
                budget.measurements(root)

    def test_nested_authored_css_is_counted_but_generated_copies_are_not(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('django-theme/src/nova_admin/static/nova_admin/new/component.css', 'dist/new/component.css', 'dist/native-admin/static/copy.css', 'dist/navigation-lab/static/copy.css'):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('body { color: blue; }')
            current = budget.measurements(root)
            self.assertEqual(len(current), 2)
            self.assertIn('dist/new/component.css', current)
            self.assertIn('django-theme/src/nova_admin/static/nova_admin/new/component.css', current)


if __name__ == '__main__':
    unittest.main()
