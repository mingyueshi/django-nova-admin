#!/usr/bin/env python3
"""Focused regression tests for the authored palette token resolver."""
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location('palette_contrast', Path(__file__).parents[1] / 'test_palette_contrast.py')
contrast = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(contrast)
color = contrast.color
effective_properties = contrast.effective_properties
selector_match = contrast.selector_match


class PaletteTokenResolverTests(unittest.TestCase):
    def test_where_is_zero_specificity_and_matches_nested_not(self):
        element = {'tag': 'html', 'classes': set(),
                   'attributes': {'data-palette': 'graphite', 'data-theme': 'dark'}}
        selector = ':root[data-theme="dark"]:where([data-palette]:not([data-palette="default"]))'
        self.assertEqual(selector_match(selector, element), (True, 20))
        element['attributes']['data-palette'] = 'default'
        self.assertEqual(selector_match(selector, element), (False, 20))

    def test_cascade_uses_specificity_then_source_order(self):
        css = '''
            body.nova-admin.nova-mode-dark { --surface: #101010; }
            body.nova-admin:where(.nova-palette-graphite) { --surface: #ffffff; }
            body.nova-admin.nova-mode-dark:where(.nova-palette-graphite, .nova-palette-midnight)
                { --surface: #202020; }
            body.nova-admin .widget { --surface: #ff0000; }
        '''
        actual = effective_properties([css], 'graphite', 'dark', 'django')
        self.assertEqual(color(actual, '--surface'), '#202020')

    def test_auto_media_overrides_only_dark_os(self):
        css = '''
            body.nova-admin.nova-mode-auto, body.nova-admin.nova-mode-light { --surface: #ffffff; }
            body.nova-admin.nova-mode-dark { --surface: #111111; }
            @media (prefers-color-scheme: dark) {
                body.nova-admin.nova-mode-auto { --surface: #111111; }
            }
        '''
        for dark_os, expected in ((False, '#ffffff'), (True, '#111111')):
            props = effective_properties([css], 'graphite', 'auto', 'django', dark_os)
            self.assertEqual(color(props, '--surface'), expected)
            explicit = effective_properties([css], 'graphite', 'light', 'django', dark_os)
            self.assertEqual(color(explicit, '--surface'), '#ffffff')

    def test_resolves_latest_token_and_short_hex_fallback(self):
        props = effective_properties([':root { --surface: var(--palette, #fff); }',
                                      ':root:where([data-palette="graphite"]) { --palette: #abc; }'],
                                     'graphite', 'dark', 'preview')
        self.assertEqual(color(props, '--surface'), '#aabbcc')
        self.assertEqual(color({'--surface': 'var(--absent, #fff)'}, '--surface'), '#ffffff')

    def test_missing_cyclic_and_nonopaque_colors_fail_closed(self):
        for props, name in (({}, '--missing'),
                            ({'--a': 'var(--b)', '--b': 'var(--a)'}, '--a'),
                            ({'--a': 'var(--b)'}, '--a'),
                            ({'--a': '#0004'}, '--a')):
            with self.subTest(properties=props), self.assertRaises(ValueError):
                color(props, name)

    def test_unsupported_conditional_color_rules_fail_closed(self):
        for condition in ('@media (min-width: 900px)', '@supports (color: oklch(0% 0 0))'):
            css = condition + ' { :root { --bg: #111111; } }'
            with self.subTest(condition=condition), self.assertRaisesRegex(ValueError, 'Unsupported'):
                effective_properties([css], 'graphite', 'dark', 'preview')

    def test_unsupported_root_pseudoclass_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'Unsupported root/body selector'):
            effective_properties([':root:has(.active) { --bg: #111111; }'], 'graphite', 'dark', 'preview')

    def test_important_declaration_wins_within_same_rule(self):
        props = effective_properties([':root { --bg: #111111 !important; --bg: #ffffff; }'],
                                     'graphite', 'dark', 'preview')
        self.assertEqual(color(props, '--bg'), '#111111')

    def test_body_root_and_descendant_rules_stay_separate(self):
        css = '''
            :root { --surface: #111111; }
            body.nova-admin { --surface: #222222; }
            :root[data-theme="dark"] :is(input, select, textarea) { --surface: #333333; }
        '''
        self.assertEqual(color(effective_properties([css], 'graphite', 'dark', 'preview'), '--surface'), '#111111')
        self.assertEqual(color(effective_properties([css], 'graphite', 'dark', 'django'), '--surface'), '#222222')


if __name__ == '__main__':
    unittest.main()
