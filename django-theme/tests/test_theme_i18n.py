"""Nova strings are localized without overriding Django's shared message IDs."""
import gettext as stdlib_gettext
import re
from importlib import resources
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.template import Context
from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import translation
from django.utils.translation import gettext, override, pgettext

from nova_admin import __version__
from nova_admin.preferences import SESSION_KEY
from nova_admin.templatetags.nova_tags import nova_navigation_groups, nova_navigation_scope
from tests.test_navigation import navigation_markup
from tests.test_navigation_groups import allowed_app


@override_settings(LANGUAGE_CODE="en", LOCALE_PATHS=())
class NovaCatalogTests(SimpleTestCase):
    def test_runtime_version_matches_current_release(self):
        self.assertEqual(__version__, "0.6.0")

    def test_compiled_chinese_catalog_contains_only_nova_context(self):
        directory = resources.files("nova_admin").joinpath("locale", "zh_Hans", "LC_MESSAGES")
        self.assertTrue(directory.joinpath("django.po").is_file())
        with directory.joinpath("django.mo").open("rb") as stream:
            catalog = stdlib_gettext.GNUTranslations(stream)
        messages = {key: value for key, value in catalog._catalog.items() if key}
        self.assertGreaterEqual(len(messages), 12)
        self.assertTrue(all(isinstance(key, str) and key.startswith("Nova Admin\x04") for key in messages))
        self.assertEqual(catalog.pgettext("Nova Admin", "Other apps"), "其他应用")
        self.assertEqual(catalog.pgettext("Nova Admin", "Navigation"), "导航菜单")
        self.assertEqual(catalog.gettext("Other apps"), "Other apps")
        self.assertEqual(catalog.gettext("- Select an option -"), "- Select an option -")

    def test_english_and_unprovided_locale_fall_back_to_english_source(self):
        for language in ("en", "fr"):
            with self.subTest(language=language), override(language):
                self.assertEqual(pgettext("Nova Admin", "Site overview"), "Site overview")
                self.assertEqual(pgettext("Nova Admin", "Unknown theme mode"), "Unknown theme mode")

    def test_chinese_translation_does_not_override_same_noncontextual_message(self):
        with override("zh-hans"):
            self.assertEqual(pgettext("Nova Admin", "Site overview"), "站点总览")
            self.assertEqual(gettext("Site overview"), "Site overview")
            self.assertEqual(pgettext("Another application", "Site overview"), "Site overview")

    @override_settings(USE_I18N=False)
    def test_disabled_i18n_uses_english_source(self):
        # Django binds translation functions on first use; reset them only in
        # this test as documented by django.utils.translation.Trans.
        with patch.dict(translation._trans.__dict__, {}, clear=True):
            self.assertEqual(pgettext("Nova Admin", "Other apps"), "Other apps")

    @override_settings(LANGUAGE_CODE="zh-hans", LOCALE_PATHS=())
    def test_missing_locale_respects_host_projects_default_language(self):
        with override("fr"):
            self.assertEqual(pgettext("Nova Admin", "Site overview"), "站点总览")

    @override_settings(NOVA_ADMIN_NAV_GROUPS=[{"label": "Configured label", "apps": ["catalog"]}])
    def test_other_apps_follows_active_language_but_configuration_is_preserved(self):
        context = Context({"available_apps": [allowed_app("catalog", "Product"), allowed_app("audit", "Entry")]})
        for language, expected in (("en", "Other apps"), ("zh-hans", "其他应用"), ("fr", "Other apps")):
            with self.subTest(language=language), override(language):
                groups = nova_navigation_groups(context)
                self.assertEqual(groups[0]["label"], "Configured label")
                self.assertEqual(groups[1]["label"], expected)

    def test_switcher_labels_and_aria_name_are_translated(self):
        for language, labels in (("en", ("Admin appearance", "Appearance", "Nova dark", "Nova light", "Django native", "Apply")), ("zh-hans", ("后台外观", "外观", "Nova 深色", "Nova 浅色", "Django 原生", "应用"))):
            with self.subTest(language=language), override(language):
                html = render_to_string("nova_admin/theme_switcher.html", {"nova_admin_mode": "native", "nova_admin_preference_url": "/admin/_theme/preference/"})
                for label in labels:
                    self.assertIn(label, html)
                self.assertIn('value="native" selected', html)
                self.assertIn('method="post"', html)

    def test_enhancement_script_preserves_nonce_escaping(self):
        html = render_to_string("admin/base.html", {
            "nova_admin_active": True, "nova_admin_mode": "dark",
            "has_permission": False, "csp_nonce": 'nonce"&<>',
        })
        script = re.search(r'<script\b[^>]*nova_admin/enhancements\.js[^>]*>', html)
        self.assertIsNotNone(script)
        self.assertIn('nonce="nonce&quot;&amp;&lt;&gt;"', script.group())
        self.assertIn('data-nova-search-placeholder="Search records…"', script.group())


class NavigationPreferenceScopeTests(SimpleTestCase):
    def user(self, pk):
        return SimpleNamespace(pk=pk, is_authenticated=True, _meta=SimpleNamespace(label_lower="auth.user"))

    def scope(self, pk=1, site="/admin/"):
        return nova_navigation_scope(Context({"user": self.user(pk)}), site)

    def test_opaque_scope_is_stable_without_queries(self):
        scope = self.scope()
        self.assertRegex(scope, r"^[a-f0-9]{64}$")
        self.assertEqual(self.scope(), scope)

    def test_different_users_and_sites_get_different_scopes(self):
        self.assertNotEqual(self.scope(), self.scope(pk=2))
        self.assertNotEqual(self.scope(), self.scope(site="/review/"))

    def test_authenticated_model_identity_is_part_of_scope(self):
        user = self.user(1)
        user._meta.label_lower = "accounts.customuser"
        self.assertNotEqual(self.scope(), nova_navigation_scope(Context({"user": user}), "/admin/"))

    def test_no_scope_for_missing_anonymous_or_unsaved_user(self):
        for user in (None, AnonymousUser(), self.user(None)):
            self.assertEqual(nova_navigation_scope(Context({"user": user}), "/admin/"), "")

    def test_scope_uses_secret_to_avoid_predictable_numeric_id_hashes(self):
        original = self.scope()
        with override_settings(SECRET_KEY="different-test-only-secret"):
            self.assertNotEqual(self.scope(), original)


@override_settings(NOVA_ADMIN_NAVIGATION=True, NOVA_ADMIN_ENABLED=True, LANGUAGE_CODE="en", LOCALE_PATHS=())
class NovaTranslationIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser(username="i18n-admin", email="i18n@example.invalid", password="test-only-I18N19!")

    def setUp(self):
        self.client.force_login(self.user)

    def test_index_and_navigation_render_in_english_and_chinese(self):
        for language, heading, workspace, description in (("en", "Site overview", "Workspace", "Manage models and everyday work."), ("zh-hans", "站点总览", "工作空间", "管理模型、处理日常工作。")):
            with self.subTest(language=language), override(language):
                response = self.client.get(reverse("admin:index"))
                self.assertContains(response, f"<h1>{heading}</h1>", html=True)
                self.assertNotContains(response, 'class="nova-eyebrow"')
                self.assertContains(response, description)
                self.assertIn(workspace, navigation_markup(response))
                self.assertNotContains(response, "WORKSPACE /")

    def test_search_placeholder_script_has_localized_attribute(self):
        for language, placeholder in (("en", "Search records…"), ("zh-hans", "搜索记录…")):
            with self.subTest(language=language), override(language):
                response = self.client.get(reverse("admin:index"))
                self.assertContains(response, f'data-nova-search-placeholder="{placeholder}"')
                self.assertContains(response, "nova_admin/enhancements.js")

    def test_mobile_navigation_button_uses_contextual_english_and_chinese(self):
        for language, label in (("en", "Navigation"), ("zh-hans", "导航菜单")):
            with self.subTest(language=language), override(language):
                response = self.client.get(reverse("admin:index"))
                self.assertRegex(response.content.decode(), rf'<button[^>]*id="nova-mobile-nav-toggle"[^>]*>{label}</button>')

    def test_invalid_preference_is_localized_and_does_not_mutate_session(self):
        for language, message in (("en", "Unknown theme mode"), ("zh-hans", "未知外观模式"), ("fr", "Unknown theme mode")):
            with self.subTest(language=language), override(language):
                response = self.client.post(reverse("nova_admin:preference"), {"mode": "invalid"})
                self.assertContains(response, message, status_code=400)
                self.assertNotIn(SESSION_KEY, self.client.session)

    def test_native_recovery_control_is_localized_without_theme_headings_or_scripts(self):
        session = self.client.session
        session[SESSION_KEY] = "native"
        session.save()
        with override("en"):
            response = self.client.get(reverse("admin:index"))
            self.assertContains(response, "Django native")
            self.assertNotContains(response, "nova-page-description")
            self.assertNotContains(response, "nova_admin/enhancements.js")
            self.assertNotContains(response, "nova_admin/navigation.js")
            self.assertFalse(navigation_markup(response))

    @override_settings(NOVA_ADMIN_ENABLED=False)
    def test_global_disable_keeps_native_templates_and_hides_all_nova_controls(self):
        with override("en"):
            response = self.client.get(reverse("admin:index"))
            self.assertNotContains(response, "nova-theme-switcher")
            self.assertNotContains(response, "nova-page-description")
            self.assertNotContains(response, "nova_admin/enhancements.js")
