"""Cross-version nonce support without importing Django 6-only template tags."""
import re

from django.template import Context, Template
from django.template.loader import render_to_string
from django.test import SimpleTestCase


class NonceTemplateTests(SimpleTestCase):
    def render_nonce(self, **context):
        return Template("{% load nova_tags %}{% nova_nonce %}").render(Context(context))

    def test_absent_or_none_nonce_renders_no_attribute(self):
        self.assertEqual(self.render_nonce(), "")
        self.assertEqual(self.render_nonce(csp_nonce=None), "")

    def test_nonce_value_is_preserved(self):
        self.assertEqual(self.render_nonce(csp_nonce="CSP-safe-123+/="), 'nonce="CSP-safe-123+/="')

    def test_nonce_escapes_attribute_breaking_characters(self):
        self.assertEqual(
            self.render_nonce(csp_nonce='bad" onload="alert(1)&<>'),
            'nonce="bad&quot; onload=&quot;alert(1)&amp;&lt;&gt;"',
        )

    def test_theme_asset_tags_receive_context_nonce(self):
        html = render_to_string("admin/base.html", {
            "nova_admin_active": True, "nova_admin_navigation": True,
            "nova_admin_mode": "dark", "has_permission": False, "csp_nonce": "asset-nonce-123",
        })
        stylesheet = re.search(r'<link\b[^>]*nova_admin/theme\.css[^>]*>', html)
        script = re.search(r'<script\b[^>]*nova_admin/navigation\.js[^>]*>', html)
        self.assertIsNotNone(stylesheet)
        self.assertIsNotNone(script)
        self.assertIn('nonce="asset-nonce-123"', stylesheet.group())
        self.assertIn('nonce="asset-nonce-123"', script.group())

    def test_native_mode_omits_theme_assets_even_with_nonce_and_navigation_enabled(self):
        html = render_to_string("admin/base.html", {
            "nova_admin_active": False, "nova_admin_navigation": True,
            "nova_admin_mode": "native", "has_permission": False, "csp_nonce": "asset-nonce-123",
        })
        self.assertNotIn("nova_admin/theme.css", html)
        self.assertNotIn("nova_admin/navigation.js", html)
        self.assertIn("admin/css/base.css", html)
