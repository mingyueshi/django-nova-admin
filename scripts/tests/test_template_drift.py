import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location('template_drift', Path(__file__).parents[1] / 'template_drift.py')
drift = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(drift)


class TemplateDriftTests(unittest.TestCase):
    def test_reviewed_upstream_allows_deliberate_override(self):
        text = '{% block content %}Upstream{% endblock %}'
        row = drift.compare({'a': text}, {'a': text}, {'a': '{% block content %}Nova{% endblock %}'})[0]
        self.assertEqual(row['status'], 'reviewed')
        self.assertTrue(row['override_diff'])
        self.assertFalse(row['upstream_diff'])

    def test_text_change_requires_review(self):
        row = drift.compare({'a': 'new'}, {'a': 'old'}, {'a': 'override'})[0]
        self.assertEqual(row['status'], 'review-required')
        self.assertIn('-old', row['upstream_diff'])

    def test_missing_required_block_is_detected(self):
        row = drift.compare({'a': 'same'}, {'a': 'same'}, {'a': '{% block content %}x{% endblock %}'})[0]
        self.assertEqual(row['removed_blocks'], ['content'])
        self.assertEqual(row['status'], 'review-required')

    def test_nova_extension_block_is_not_upstream_requirement(self):
        row = drift.compare({'a': 'same'}, {'a': 'same'}, {'a': '{% block nova_footer %}x{% endblock %}'})[0]
        self.assertEqual(row['status'], 'reviewed')

    def test_blocks_in_upstream_parent_are_valid(self):
        texts = {'a': '{% extends "base" %}', 'base': '{% block content %}x{% endblock %}'}
        row = drift.compare(texts, texts, {'a': '{% block content %}override{% endblock %}'})[0]
        self.assertEqual(row['status'], 'reviewed')

    def test_parent_cycle_terminates(self):
        texts = {'a': '{% extends "base" %}', 'base': '{% extends "a" %}'}
        row = drift.compare(texts, texts, {'a': '{% block content %}override{% endblock %}'})[0]
        self.assertEqual(row['removed_blocks'], ['content'])

    def test_missing_template_is_not_a_pass(self):
        row = drift.compare({}, {'a': 'same'}, {'a': 'override'})[0]
        self.assertEqual(row['status'], 'missing-upstream')

    def test_hash_tracks_unicode_exactly(self):
        self.assertNotEqual(drift.digest('列表：'), drift.digest('列表:'))


if __name__ == '__main__':
    unittest.main()
