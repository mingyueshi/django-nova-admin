"""Useful warnings without requiring Nova's optional preference URL include."""
from copy import deepcopy
from unittest.mock import Mock

from django.conf import settings
from django.core.checks import Tags, run_checks
from django.test import SimpleTestCase, override_settings

from nova_admin.checks import navigation_settings_check, theme_context_check, theme_namespace_check
from tests.test_theme_context import MissingRouteUrls, NestedUrls, NoThemeUrls


class ThemeChecksTests(SimpleTestCase):
    def test_each_django_engine_requires_the_processor(self):
        templates = deepcopy(settings.TEMPLATES)
        other = deepcopy(templates[0])
        other['NAME'] = 'other'
        other['OPTIONS']['context_processors'].remove('nova_admin.context_processors.theme')
        with override_settings(TEMPLATES=[*templates, other]):
            self.assertEqual([message.id for message in theme_context_check(None)], ['nova_admin.W001'])

    def test_default_project_is_clean_and_checks_are_registered(self):
        self.assertEqual(theme_context_check(None), [])
        self.assertEqual(theme_namespace_check(None), [])
        self.assertEqual(navigation_settings_check(None), [])
        templates = deepcopy(settings.TEMPLATES)
        templates[0]["OPTIONS"]["context_processors"].remove("nova_admin.context_processors.theme")
        with override_settings(TEMPLATES=templates):
            messages = [item for item in run_checks(tags=[Tags.templates]) if item.id.startswith("nova_admin.")]
        self.assertEqual([item.id for item in messages], ["nova_admin.W001"])
        self.assertIn("context_processors", messages[0].hint)

    @override_settings(ROOT_URLCONF=NoThemeUrls)
    def test_omitted_optional_endpoint_has_no_warning_unless_explicitly_mapped(self):
        with override_settings():
            if hasattr(settings, "NOVA_ADMIN_URL_NAMESPACES"):
                del settings.NOVA_ADMIN_URL_NAMESPACES
            self.assertEqual(theme_namespace_check(None), [])
        with override_settings(NOVA_ADMIN_URL_NAMESPACES={}):
            self.assertEqual(theme_namespace_check(None), [])
        with override_settings(NOVA_ADMIN_URL_NAMESPACES={"admin": "nova_admin"}):
            self.assertEqual([item.id for item in theme_namespace_check(None)], ["nova_admin.W002"])

    @override_settings(ROOT_URLCONF=MissingRouteUrls, NOVA_ADMIN_URL_NAMESPACES={"admin": "nova_admin"})
    def test_namespace_without_named_preference_route_is_reported(self):
        self.assertEqual([item.id for item in theme_namespace_check(None)], ["nova_admin.W002"])

    def test_valid_default_multisite_and_nested_mappings_are_clean(self):
        for urlconf, mapping in (
            ("config.urls", {"admin": "nova_admin"}),
            ("tests.multisite_urls", {"warehouse": "warehouse_theme", "review": "review_theme"}),
            (NestedUrls, {"east:warehouse": "east:warehouse_theme", "west:review": "west:review_theme"}),
            (NestedUrls, {"warehouse": "portal:warehouse_theme"}),
        ):
            with self.subTest(mapping=mapping), override_settings(ROOT_URLCONF=urlconf, NOVA_ADMIN_URL_NAMESPACES=mapping):
                self.assertEqual(theme_namespace_check(None), [])

    def test_malformed_and_unresolvable_mapping_values_warn_without_crashing(self):
        for mapping in (None, [], "nova_admin", {"admin": None}, {"admin": []}, {None: "nova_admin"},
                        {"admin": "missing"}, {"missing": "nova_admin"}, {"admin": "a::b"}):
            with self.subTest(mapping=mapping), override_settings(NOVA_ADMIN_URL_NAMESPACES=mapping):
                self.assertTrue(theme_namespace_check(None))

    def test_invalid_navigation_settings_warn_and_never_invoke_providers(self):
        for configuration in (
            {"NOVA_ADMIN_NAV_FAVORITES": "true"}, {"NOVA_ADMIN_NAV_COMMON_MODELS": "app.model"},
            {"NOVA_ADMIN_NAV_COMMON_MODELS": [None]}, {"NOVA_ADMIN_NAV_ICONS": {"app.model": []}},
            {"NOVA_ADMIN_NAV_ICONS": {"app.model": "<svg>"}}, {"NOVA_ADMIN_NAV_BADGE_PROVIDER": "missing.provider"},
        ):
            with self.subTest(configuration=configuration), override_settings(**configuration):
                self.assertTrue(navigation_settings_check(None))
        provider = Mock()
        with override_settings(NOVA_ADMIN_NAV_BADGE_PROVIDER=provider, NOVA_ADMIN_NAV_ICON_PROVIDER=provider):
            self.assertEqual(navigation_settings_check(None), [])
        provider.assert_not_called()

    @override_settings(NOVA_ADMIN_ENABLED=False, TEMPLATES=[], NOVA_ADMIN_URL_NAMESPACES=None,
                       NOVA_ADMIN_NAV_FAVORITES="bad")
    def test_disabled_theme_emits_no_nova_warnings(self):
        self.assertEqual(theme_context_check(None), [])
        self.assertEqual(theme_namespace_check(None), [])
        self.assertEqual(navigation_settings_check(None), [])
