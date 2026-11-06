"""NOVA_ADMIN_MARKDOWN stays off unless explicitly enabled by the host."""
from django.contrib.auth import get_user_model
from django.core.checks import Tags, Warning as CheckWarning, register
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from nova_admin.checks import markdown_setting_check


class MarkdownSettingCheckTests(SimpleTestCase):
    def test_non_boolean_setting_warns(self):
        for value in ("yes", 1, [], None):
            with self.subTest(value=value), override_settings(NOVA_ADMIN_MARKDOWN=value):
                warnings = markdown_setting_check(None)
            self.assertEqual(len(warnings), 1)
            self.assertEqual(warnings[0].id, "nova_admin.W004")

    def test_boolean_and_absent_settings_stay_quiet(self):
        self.assertEqual(markdown_setting_check(None), [])
        for value in (False, True):
            with self.subTest(value=value), override_settings(NOVA_ADMIN_MARKDOWN=value):
                self.assertEqual(markdown_setting_check(None), [])


class MarkdownAssetWiringTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser(
            "markdown-admin", "markdown@example.invalid", "test-only-Markdown123!"
        )

    def setUp(self):
        self.client.force_login(self.user)
        self.url = reverse("admin:catalog_product_add")

    def test_enabled_change_form_loads_toolbar_assets(self):
        with override_settings(NOVA_ADMIN_MARKDOWN=True):
            response = self.client.get(self.url)
        self.assertContains(response, "nova_admin/markdown.js")
        self.assertContains(response, "nova_admin/markdown.css")
        self.assertContains(response, 'id="nova-md-labels"')
        self.assertContains(response, "Markdown formatting")

    def test_default_setting_loads_nothing(self):
        response = self.client.get(self.url)
        self.assertNotContains(response, "nova_admin/markdown.js")
        self.assertNotContains(response, "nova-md-labels")

    def test_disabled_theme_and_popups_load_nothing(self):
        with override_settings(NOVA_ADMIN_MARKDOWN=True, NOVA_ADMIN_ENABLED=False):
            self.assertNotContains(self.client.get(self.url), "nova_admin/markdown.js")
        with override_settings(NOVA_ADMIN_MARKDOWN=True):
            self.assertNotContains(self.client.get(self.url + "?_popup=1"), "nova_admin/markdown.js")
