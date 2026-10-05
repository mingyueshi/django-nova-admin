"""Optional presentation URLs must not penalize public or unmounted pages."""
from unittest.mock import patch

from django.contrib import admin
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import get_urlconf, include, path, resolve, reverse, set_urlconf
from django.conf.urls.i18n import i18n_patterns
from django.utils.translation import override

from nova_admin.context_processors import theme
from nova_admin.urls import for_admin
from tests.multisite_urls import urlpatterns as multisite_patterns


def public_view(request):
    return HttpResponse("Public")


class NoThemeUrls:
    urlpatterns = [
        path("public/", public_view),
        path("tools/", include(([path("", public_view, name="home")], "tools"))),
        path("admin/", admin.site.urls),
    ]


class MissingRouteUrls:
    urlpatterns = [
        path("admin/_theme/", include(([path("other/", public_view, name="other")], "nova_admin"))),
        path("admin/", admin.site.urls),
    ]


class NestedUrls:
    urlpatterns = [
        path("east/", include((multisite_patterns, "portal"), namespace="east")),
        path("west/", include((multisite_patterns, "portal"), namespace="west")),
    ]


class TranslatedUrls:
    urlpatterns = i18n_patterns(
        path("admin/_theme/", include(for_admin(admin.site))),
        path("admin/", admin.site.urls),
    )


@override_settings(NOVA_ADMIN_ENABLED=True, NOVA_ADMIN_URL_NAMESPACES={"admin": "nova_admin"})
class ThemeContextTests(SimpleTestCase):
    def request(self, path="/admin/", urlconf="config.urls", current_app=None):
        request = RequestFactory().get(path)
        request.resolver_match = resolve(path, urlconf=urlconf)
        if current_app is not None:
            request.current_app = current_app
        return request

    def test_public_request_without_match_skips_all_url_lookup(self):
        request = RequestFactory().get("/")
        with patch("nova_admin.context_processors.get_resolver") as resolver, patch("nova_admin.context_processors.reverse") as reversing:
            self.assertEqual(theme(request)["nova_admin_preference_url"], "")
        resolver.assert_not_called()
        reversing.assert_not_called()

    def test_resolved_public_request_without_current_app_skips_url_lookup(self):
        request = self.request("/public/", NoThemeUrls)
        with patch("nova_admin.context_processors.get_resolver") as resolver, patch("nova_admin.context_processors.reverse") as reversing:
            self.assertEqual(theme(request)["nova_admin_preference_url"], "")
        resolver.assert_not_called()
        reversing.assert_not_called()

    def test_custom_admin_template_view_honors_explicit_mapped_current_app(self):
        request = self.request("/tools/", NoThemeUrls, "admin")
        self.assertEqual(request.resolver_match.namespace, "tools")
        self.assertEqual(theme(request)["nova_admin_preference_url"], "/admin/_theme/preference/")

    def test_unmapped_current_app_skips_resolver_and_reverse(self):
        request = self.request("/public/", NoThemeUrls, "public_application")
        with patch("nova_admin.context_processors.get_resolver") as resolver, patch("nova_admin.context_processors.reverse") as reversing:
            self.assertEqual(theme(request)["nova_admin_preference_url"], "")
        resolver.assert_not_called()
        reversing.assert_not_called()

    @override_settings(ROOT_URLCONF=NoThemeUrls)
    def test_missing_optional_namespace_does_not_call_reverse(self):
        request = self.request(urlconf=NoThemeUrls)
        with patch("nova_admin.context_processors.reverse") as reversing:
            self.assertEqual(theme(request)["nova_admin_preference_url"], "")
            self.assertTrue(theme(request)["nova_admin_active"])
        reversing.assert_not_called()

    @override_settings(ROOT_URLCONF=MissingRouteUrls)
    def test_existing_namespace_without_preference_does_not_call_reverse(self):
        request = self.request(urlconf=MissingRouteUrls)
        with patch("nova_admin.context_processors.reverse") as reversing:
            self.assertEqual(theme(request)["nova_admin_preference_url"], "")
        reversing.assert_not_called()

    def test_default_site_uses_resolver_match_without_current_app(self):
        self.assertEqual(theme(self.request())["nova_admin_preference_url"], reverse("nova_admin:preference"))

    def test_explicit_current_app_supports_manual_admin_template_context(self):
        request = RequestFactory().get("/admin/")
        request.current_app = "admin"
        self.assertEqual(theme(request)["nova_admin_preference_url"], reverse("nova_admin:preference"))

    @override_settings(ROOT_URLCONF="tests.multisite_urls", NOVA_ADMIN_URL_NAMESPACES={"warehouse": "warehouse_theme", "review": "review_theme"})
    def test_current_app_takes_precedence_over_matched_site(self):
        request = self.request("/warehouse/", "tests.multisite_urls", "review")
        self.assertEqual(theme(request)["nova_admin_preference_url"], "/review/_theme/preference/")

    @override_settings(NOVA_ADMIN_URL_NAMESPACES={"warehouse": "warehouse_theme"})
    def test_request_urlconf_is_used_for_lookup_and_reverse(self):
        request = self.request("/warehouse/", "tests.multisite_urls", "warehouse")
        request.urlconf = "tests.multisite_urls"
        self.assertEqual(theme(request)["nova_admin_preference_url"], "/warehouse/_theme/preference/")

    def test_thread_local_urlconf_is_used_when_request_has_none(self):
        previous = get_urlconf()
        try:
            set_urlconf("tests.alternate_urls")
            request = self.request("/backoffice/", "tests.alternate_urls", "admin")
            self.assertEqual(theme(request)["nova_admin_preference_url"], "/backoffice/_theme/preference/")
        finally:
            set_urlconf(previous)

    def test_no_stale_cache_when_optional_endpoint_appears_or_disappears(self):
        for urlconf, expected in ((NoThemeUrls, ""), ("config.urls", "/admin/_theme/preference/"), (NoThemeUrls, "")):
            with self.subTest(urlconf=urlconf), override_settings(ROOT_URLCONF=urlconf):
                self.assertEqual(theme(self.request(urlconf=urlconf))["nova_admin_preference_url"], expected)

    @override_settings(ROOT_URLCONF=NestedUrls, NOVA_ADMIN_URL_NAMESPACES={"warehouse": "portal:warehouse_theme"})
    def test_nested_application_namespace_uses_matched_instance_hint(self):
        for side in ("east", "west"):
            for current_app in (None, "warehouse", f"{side}:warehouse"):
                with self.subTest(side=side, current_app=current_app):
                    request = self.request(f"/{side}/warehouse/", NestedUrls, current_app)
                    self.assertEqual(theme(request)["nova_admin_preference_url"], f"/{side}/warehouse/_theme/preference/")

    @override_settings(ROOT_URLCONF=NestedUrls, NOVA_ADMIN_URL_NAMESPACES={"east:warehouse": "east:warehouse_theme", "west:warehouse": "west:warehouse_theme"})
    def test_fully_qualified_site_mapping_works_with_admin_site_current_app(self):
        for side in ("east", "west"):
            for current_app in (None, "warehouse", f"{side}:warehouse"):
                with self.subTest(side=side, current_app=current_app):
                    request = self.request(f"/{side}/warehouse/", NestedUrls, current_app)
                    self.assertEqual(theme(request)["nova_admin_preference_url"], f"/{side}/warehouse/_theme/preference/")

    @override_settings(ROOT_URLCONF=TranslatedUrls)
    def test_language_specific_routes_do_not_leak_between_requests(self):
        for language in ("en", "zh-hans", "en"):
            with self.subTest(language=language), override(language):
                request = self.request(f"/{language}/admin/", TranslatedUrls)
                self.assertEqual(theme(request)["nova_admin_preference_url"], f"/{language}/admin/_theme/preference/")

    @override_settings(NOVA_ADMIN_ENABLED=False)
    def test_disabled_theme_skips_resolver_and_reverse(self):
        request = self.request()
        with patch("nova_admin.context_processors.get_resolver") as resolver, patch("nova_admin.context_processors.reverse") as reversing:
            result = theme(request)
        self.assertFalse(result["nova_admin_enabled"])
        self.assertEqual(result["nova_admin_preference_url"], "")
        resolver.assert_not_called()
        reversing.assert_not_called()

    def test_native_mode_retains_its_recovery_endpoint(self):
        request = self.request()
        request.session = {"nova_admin_mode": "native"}
        result = theme(request)
        self.assertFalse(result["nova_admin_active"])
        self.assertEqual(result["nova_admin_preference_url"], "/admin/_theme/preference/")

    def test_invalid_namespace_settings_hide_optional_control(self):
        request = self.request()
        for namespaces in (None, [], "nova_admin", {"admin": None}, {"admin": 1}, {"admin": ""}, {"admin": "missing:also_missing"}):
            with self.subTest(namespaces=namespaces), override_settings(NOVA_ADMIN_URL_NAMESPACES=namespaces):
                with patch("nova_admin.context_processors.reverse") as reversing:
                    self.assertEqual(theme(request)["nova_admin_preference_url"], "")
                reversing.assert_not_called()
