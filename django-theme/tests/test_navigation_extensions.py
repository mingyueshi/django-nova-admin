"""Metadata and shortcuts cannot expand native navigation permissions."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.template import Context
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import resolve, reverse
from django.utils.html import escape
from django.utils.translation import override

from nova_admin.navigation import ICON_PATHS
from nova_admin.templatetags.nova_tags import nova_navigation_extensions
from tests.test_navigation import navigation_markup


def app_list():
    return [{"app_label": "catalog", "name": "Catalog", "app_url": "/admin/catalog/", "models": [
        {"object_name": "Product", "name": "Products", "admin_url": "/admin/catalog/product/", "perms": {"view": True}},
        {"object_name": "Draft", "name": "Drafts", "add_url": "/admin/catalog/draft/add/", "perms": {"add": True}},
    ]}]


@override_settings(NOVA_ADMIN_NAV_GROUPS=None, NOVA_ADMIN_NAV_FAVORITES=False,
                   NOVA_ADMIN_NAV_COMMON_MODELS=(), NOVA_ADMIN_NAV_ICONS={},
                   NOVA_ADMIN_NAV_ICON_PROVIDER=None, NOVA_ADMIN_NAV_BADGE_PROVIDER=None)
class NavigationExtensionTests(SimpleTestCase):
    def navigation(self, available=None):
        return nova_navigation_extensions(Context({"available_apps": app_list() if available is None else available}))

    def test_defaults_have_no_shortcuts_badges_icons_or_queries(self):
        result = self.navigation()
        self.assertFalse(result["favorites_enabled"])
        self.assertEqual(result["common"], [])
        self.assertEqual(result["favorites"], [])
        for model in result["groups"][0]["apps"][0]["models"]:
            self.assertIsNone(model["nova_icon_path"])
            self.assertIsNone(model["nova_badge"])

    @override_settings(NOVA_ADMIN_NAV_FAVORITES=True, NOVA_ADMIN_NAV_COMMON_MODELS=[
        "catalog.product", "catalog.draft", "secret.customer", "catalog.product", None, [],
    ])
    def test_shortcuts_only_reuse_distinct_existing_list_destinations(self):
        result = self.navigation()
        self.assertEqual([item["nova_key"] for item in result["common"]], ["catalog.product"])
        self.assertEqual([item["nova_key"] for item in result["favorites"]], ["catalog.product"])
        self.assertEqual(result["common"][0]["admin_url"], "/admin/catalog/product/")

    def test_bulk_providers_receive_only_copied_available_apps_once_and_cannot_mutate_context(self):
        available = app_list()
        original = deepcopy(available)
        def mutating_icons(request, apps):
            apps[0]["models"][0]["admin_url"] = "https://evil.invalid/"
            apps[0]["models"][0]["perms"]["view"] = False
            return {"catalog.product": "box", "secret.customer": "users"}
        icons = Mock(side_effect=mutating_icons)
        badges = Mock(return_value={"catalog.product": 0, "catalog.draft": 7, "secret.customer": 998})
        with override_settings(NOVA_ADMIN_NAV_ICON_PROVIDER=icons, NOVA_ADMIN_NAV_BADGE_PROVIDER=badges):
            result = self.navigation(available)
        icons.assert_called_once()
        badges.assert_called_once()
        self.assertEqual(badges.call_args.args[1], original)
        self.assertEqual(available, original)
        models = result["groups"][0]["apps"][0]["models"]
        self.assertEqual(models[0]["admin_url"], original[0]["models"][0]["admin_url"])
        self.assertEqual(models[0]["nova_icon_path"], ICON_PATHS["box"])
        self.assertEqual(models[0]["nova_badge"], 0)
        self.assertIsNone(models[1]["nova_badge"])
        self.assertNotIn("secret", str(result))

    def test_missing_visible_apps_skip_both_providers(self):
        icons, badges = Mock(), Mock()
        with override_settings(NOVA_ADMIN_NAV_ICON_PROVIDER=icons, NOVA_ADMIN_NAV_BADGE_PROVIDER=badges):
            self.assertEqual(self.navigation([])["groups"], [])
        icons.assert_not_called()
        badges.assert_not_called()

    def test_invalid_and_failed_providers_leave_native_destinations_usable(self):
        for provider in (True, [], "missing.module.function", Mock(return_value=[]), Mock(side_effect=ValueError("secret detail"))):
            with self.subTest(provider=type(provider).__name__), override_settings(
                NOVA_ADMIN_NAV_ICON_PROVIDER=provider, NOVA_ADMIN_NAV_BADGE_PROVIDER=provider,
            ), patch("nova_admin.navigation.logger") as logger:
                result = self.navigation()
                self.assertEqual(result["groups"][0]["apps"][0]["models"][0]["admin_url"], "/admin/catalog/product/")
                self.assertNotIn("secret detail", str(logger.mock_calls))

    def test_only_nonnegative_bounded_integer_badges_are_accepted(self):
        for value in (None, -1, True, 1.5, "12", "<script>alert(1)</script>", {}, [], 2147483648):
            with self.subTest(value=value), override_settings(NOVA_ADMIN_NAV_BADGE_PROVIDER=lambda request, apps: {"catalog.product": value}):
                self.assertIsNone(self.navigation()["groups"][0]["apps"][0]["models"][0]["nova_badge"])

    def test_malformed_favorites_common_and_icon_config_is_safe(self):
        for value in (None, True, 9, "catalog.product", [], {}):
            with self.subTest(value=value), override_settings(
                NOVA_ADMIN_NAV_FAVORITES="true", NOVA_ADMIN_NAV_COMMON_MODELS=value, NOVA_ADMIN_NAV_ICONS=value,
            ):
                result = self.navigation()
                self.assertFalse(result["favorites_enabled"])
                self.assertEqual(result["common"], [])
        with override_settings(NOVA_ADMIN_NAV_ICONS={"catalog.product": '<svg onload="alert(1)">', "catalog": []}):
            self.assertIsNone(self.navigation()["groups"][0]["apps"][0]["models"][0]["nova_icon_path"])

    def test_dotted_hook_and_fixed_icon_mapping_work(self):
        with override_settings(NOVA_ADMIN_NAV_BADGE_PROVIDER="tests.test_navigation_extensions.example_badges",
                               NOVA_ADMIN_NAV_ICONS={"catalog": "folder", "catalog.product": "box"}):
            app = self.navigation()["groups"][0]["apps"][0]
        self.assertEqual(app["nova_icon_path"], ICON_PATHS["folder"])
        self.assertEqual(app["models"][0]["nova_badge"], 12)

    @override_settings(NOVA_ADMIN_NAV_FAVORITES=True, NOVA_ADMIN_NAV_COMMON_MODELS=["catalog.product"])
    def test_model_labels_are_escaped_in_shortcuts_and_favorite_button_attributes(self):
        available = app_list()
        hostile = '<img src=x onerror="alert(1)"> & "label"'
        available[0]["models"][0]["name"] = hostile
        with override("en"):
            markup = render_to_string("nova_admin/navigation.html", {"available_apps": available})
        self.assertIn(str(escape(hostile)), markup)
        self.assertIn(f'aria-label="Favorite {escape(hostile)}"', markup)
        self.assertNotIn(hostile, markup)
        self.assertNotIn("<img", markup)


def example_badges(request, available_apps):
    return {"catalog.product": 12}


@override_settings(NOVA_ADMIN_ENABLED=True, NOVA_ADMIN_NAVIGATION=True,
                   NOVA_ADMIN_NAV_FAVORITES=True,
                   NOVA_ADMIN_NAV_COMMON_MODELS=["catalog.product", "auth.user", "catalog.category"],
                   NOVA_ADMIN_NAV_ICONS={"catalog.product": "box", "auth.user": "users"})
class NavigationExtensionIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.viewer = get_user_model().objects.create_user(username="nav-extension-viewer", is_staff=True)
        cls.viewer.user_permissions.add(Permission.objects.get(content_type__app_label="catalog", codename="view_product"))

    def setUp(self):
        self.client.force_login(self.viewer)

    def test_hooks_and_shortcuts_only_receive_and_render_native_permitted_models(self):
        badges = Mock(return_value={"catalog.product": 12, "auth.user": 93425})
        with override_settings(NOVA_ADMIN_NAV_BADGE_PROVIDER=badges), override("en"):
            response = self.client.get(reverse("admin:catalog_product_changelist"))
        markup = navigation_markup(response)
        badges.assert_called_once()
        self.assertEqual(badges.call_args.args[0].user.pk, self.viewer.pk)
        apps = badges.call_args.args[1]
        self.assertEqual([(app["app_label"], [model["object_name"] for model in app["models"]]) for app in apps], [("catalog", ["Product"])])
        self.assertIn('data-nova-favorite="catalog.product"', markup)
        self.assertIn(f'aria-label="Favorite {escape(apps[0]["models"][0]["name"])}"', markup)
        self.assertIn('data-nova-favorite-shortcut hidden', markup)
        self.assertIn('class="nova-nav-badge"', markup)
        self.assertIn('class="nova-nav-icon"', markup)
        self.assertNotIn("93425", markup)
        self.assertNotIn("auth.user", markup)
        self.assertNotIn(reverse("admin:catalog_category_changelist"), markup)
        self.assertNotIn(reverse("admin:catalog_product_add"), markup)

    def test_provider_failure_does_not_break_real_admin_or_disclose_exception(self):
        with override_settings(NOVA_ADMIN_NAV_BADGE_PROVIDER=Mock(side_effect=RuntimeError("PRIVATE SENTINEL"))), patch("nova_admin.navigation.logger"):
            response = self.client.get(reverse("admin:catalog_product_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "PRIVATE SENTINEL")
        self.assertNotIn('class="nova-nav-badge"', navigation_markup(response))

    def test_hostile_metadata_is_not_rendered_as_html_or_new_destinations(self):
        malicious = '<img src=x onerror="alert(1)">'
        with override_settings(NOVA_ADMIN_NAV_ICONS={"catalog.product": malicious},
                               NOVA_ADMIN_NAV_BADGE_PROVIDER=lambda request, apps: {"catalog.product": malicious, "other.model": 43}):
            markup = navigation_markup(self.client.get(reverse("admin:catalog_product_changelist")))
        self.assertNotIn(malicious, markup)
        self.assertNotIn("other.model", markup)
        self.assertNotIn("<img", markup)

    def test_native_opt_out_and_popup_do_not_invoke_navigation_hooks(self):
        provider = Mock()
        with override_settings(NOVA_ADMIN_NAVIGATION=False, NOVA_ADMIN_NAV_BADGE_PROVIDER=provider):
            response = self.client.get(reverse("admin:catalog_product_changelist"))
            self.assertFalse(navigation_markup(response))
        provider.assert_not_called()

    def test_enabled_empty_sidebar_keeps_pruning_marker_and_disabled_feature_omits_it(self):
        self.viewer.user_permissions.clear()
        response = self.client.get(reverse("admin:index"))
        self.assertContains(response, 'data-nova-favorites-enabled="true"')
        self.assertNotContains(response, 'data-nova-favorite="')
        with override_settings(NOVA_ADMIN_NAV_FAVORITES=False):
            response = self.client.get(reverse("admin:index"))
        self.assertNotContains(response, "data-nova-favorites-enabled")


class DemoBadgeProviderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from catalog.models import Product
        cls.user = get_user_model().objects.create_superuser(username="badge-scope-user", password=None)
        Product.objects.create(name="Visible badge sample", sku="BADGE-VISIBLE", price=1)
        Product.objects.create(name="Hidden badge sample", sku="BADGE-HIDDEN", price=2)

    def request(self, site="admin"):
        request = RequestFactory().get(reverse(f"{site}:catalog_product_changelist"))
        request.resolver_match = resolve(request.path)
        request.user = self.user
        return request

    def test_demo_provider_does_not_query_for_absent_or_add_only_product(self):
        from catalog.navigation import demo_product_badges
        for available in ([], [{"app_label": "catalog", "models": [{"object_name": "Product", "add_url": "/add/", "perms": {"add": True}}]}],
                          [{"app_label": "catalog", "models": [{"object_name": "Product", "admin_url": "/list/", "perms": {}}]}]):
            with self.subTest(available=available), self.assertNumQueries(0):
                self.assertEqual(demo_product_badges(None, available), {})

    def test_demo_provider_uses_one_query_only_for_explicit_visible_product(self):
        from catalog.navigation import demo_product_badges
        request = self.request()
        with self.assertNumQueries(1):
            self.assertEqual(demo_product_badges(request, app_list()), {"catalog.product": 2})

    def test_unresolved_and_unregistered_sites_never_fall_back_to_default_admin(self):
        from django.contrib.admin import AdminSite
        from catalog.navigation import demo_product_badges
        unregistered = self.request()
        unregistered.resolver_match = SimpleNamespace(func=SimpleNamespace(admin_site=AdminSite(name="empty")))
        for request in (None, RequestFactory().get("/manual/"), unregistered):
            with self.subTest(request=request), self.assertNumQueries(0):
                self.assertEqual(demo_product_badges(request, app_list()), {})

    def test_count_respects_current_model_admin_row_scope_and_permission(self):
        from django.contrib import admin
        from catalog.models import Product
        from catalog.navigation import demo_product_badges
        request = self.request()
        model_admin = admin.site.get_model_admin(Product)
        with patch.object(model_admin, "get_queryset", return_value=Product.objects.filter(sku="BADGE-VISIBLE")), self.assertNumQueries(1):
            self.assertEqual(demo_product_badges(request, app_list()), {"catalog.product": 1})
        with patch.object(model_admin, "has_view_or_change_permission", return_value=False), self.assertNumQueries(0):
            self.assertEqual(demo_product_badges(request, app_list()), {})
        with patch.object(admin.site, "has_permission", return_value=False), self.assertNumQueries(0):
            self.assertEqual(demo_product_badges(request, app_list()), {})

    @override_settings(ROOT_URLCONF="tests.multisite_urls")
    def test_multiple_adminsites_keep_their_own_queryset_scope(self):
        from catalog.models import Product
        from catalog.navigation import demo_product_badges
        from tests.multisite_urls import review_site, warehouse_site
        for site, count in ((warehouse_site, 1), (review_site, 0)):
            request = self.request(site.name)
            queryset = Product.objects.filter(sku="BADGE-VISIBLE") if count else Product.objects.none()
            with self.subTest(site=site.name), patch.object(site.get_model_admin(Product), "get_queryset", return_value=queryset), self.assertNumQueries(count):
                self.assertEqual(demo_product_badges(request, app_list()), {"catalog.product": count})

    def test_admin_index_view_site_metadata_is_supported(self):
        from catalog.navigation import demo_product_badges
        request = self.request()
        request.resolver_match = resolve(reverse("admin:index"))
        with self.assertNumQueries(1):
            self.assertEqual(demo_product_badges(request, app_list()), {"catalog.product": 2})
