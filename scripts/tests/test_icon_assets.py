"""Offline consistency and importer bounds for licensed SVG sources."""
import importlib.util
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

SPEC = importlib.util.spec_from_file_location('build_icons', Path(__file__).parents[1] / 'build_icons.py')
icons = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(icons)


class IconAssetTests(unittest.TestCase):
    def test_reviewed_sources_and_licenses_match_hashes(self):
        data = icons.payload()
        self.assertEqual(len(data['icons']), 320)
        self.assertEqual({lib['id'] for lib in data['libraries']}, {'lucide','tabler','heroicons','iconoir','bootstrap'})

    def test_non_icon_markup_is_rejected(self):
        for markup in ('<script/>','<foreignObject/>','<image href="https://bad.invalid/"/>','<use href="#anything"/>'):
            with self.subTest(markup=markup), self.assertRaises(ValueError):
                icons.node_markup(ET.fromstring(markup))

    def test_events_and_external_paints_are_rejected(self):
        for markup in ('<path onload="x"/>','<path fill="url(https://bad.invalid/a)"/>','<path stroke="javascript:x"/>'):
            with self.subTest(markup=markup), self.assertRaises(ValueError):
                icons.node_markup(ET.fromstring(markup))

    def test_asset_paths_cannot_escape_bundle(self):
        with self.assertRaises(ValueError):
            icons.asset_path('../outside.svg')

    def test_reviewed_geometry_is_escaped_and_retained(self):
        value = icons.node_markup(ET.fromstring('<path d="M0 0h24" stroke="currentColor"/>'))
        self.assertIn('d="M0 0h24"', value)
        self.assertIn('stroke="currentColor"', value)

    def test_native_outline_and_fill_coordinates_are_preserved(self):
        data = icons.payload()['icons']
        self.assertEqual(data['bootstrap:search']['viewBox'], '0 0 16 16')
        self.assertEqual(data['bootstrap:search']['fill'], 'currentColor')
        self.assertEqual(data['bootstrap:search']['stroke'], 'none')
        self.assertEqual(data['iconoir:search']['strokeWidth'], 1.5)
        self.assertEqual(data['iconoir:search']['viewBox'], '0 0 24 24')
        for markup in ('<svg viewBox="0 0 100 100"/>', '<svg viewBox="0 0 24 24" fill="red"/>',
                       '<svg viewBox="0 0 24 24" stroke="currentColor" stroke-width="nan"/>'):
            with self.subTest(markup=markup), self.assertRaises(ValueError):
                icons.svg_paint(ET.fromstring(markup))
