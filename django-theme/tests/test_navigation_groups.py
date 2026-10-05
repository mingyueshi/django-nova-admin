"""Optional section grouping must preserve AdminSite's native permission boundary."""
from copy import deepcopy
from html.parser import HTMLParser
from unittest.mock import patch

from django.apps import apps
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.template import Context
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils.html import escape

from catalog.models import Product
from nova_admin.preferences import SESSION_KEY
from nova_admin.templatetags.nova_tags import nova_navigation_groups
from tests.test_navigation import navigation_markup


GROUPS = [
    {"label": "业务管理", "apps": ["catalog"]},
    {"label": "系统管理", "apps": ["auth"]},
]


class NavigationElements(HTMLParser):
    """Capture real element ancestry rather than only looking for class strings."""

    void_elements = {
        "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr",
    }

    def __init__(self, markup):
        super().__init__()
        self.elements = []
        self.stack = []
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        element = {"tag": tag, "attrs": dict(attrs), "ancestors": tuple(self.stack)}
        self.elements.append(element)
        if tag not in self.void_elements:
            self.stack.append(element)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]["tag"] == tag:
                del self.stack[index:]
                break

    def with_class(self, classname):
        return [element for element in self.elements if self.has_class(element, classname)]

    @staticmethod
    def has_class(element, classname):
        return classname in element["attrs"].get("class", "").split()


def allowed_app(label, model_name):
    """Use the same dictionary shape AdminSite supplies, without a registry lookup."""
    return {
        "app_label": label,
        "app_url": f"/admin/{label}/",
        "name": label.title(),
        "has_module_perms": True,
        "models": [{
            "name": model_name,
            "object_name": model_name,
            "perms": {"view": True, "add": False, "change": False, "delete": False},
            "admin_url": f"/admin/{label}/{model_name.lower()}/",
            "view_only": True,
        }],
    }


def grouped_apps(groups):
    return [app for group in groups for app in group["apps"]]


@override_settings(NOVA_ADMIN_NAV_GROUPS=None)
class NavigationGroupTagTests(SimpleTestCase):
    def setUp(self):
        self.catalog = allowed_app("catalog", "Product")
        self.auth = allowed_app("auth", "User")
        self.audit = allowed_app("audit", "Entry")
        self.available_apps = [self.auth, self.catalog, self.audit]

    def groups(self, available_apps=None):
        if available_apps is None:
            available_apps = self.available_apps
        return nova_navigation_groups(Context({"available_apps": available_apps}))

    def test_absent_configuration_retains_two_level_wrapper(self):
        with override_settings():
            if hasattr(settings, "NOVA_ADMIN_NAV_GROUPS"):
                del settings.NOVA_ADMIN_NAV_GROUPS
            self.assertEqual(self.groups(), [{"label": None, "apps": self.available_apps}])

    def test_none_and_empty_configuration_retain_two_level_wrapper(self):
        for configuration in (None, [], ()):
            with self.subTest(configuration=configuration):
                with override_settings(NOVA_ADMIN_NAV_GROUPS=configuration):
                    self.assertEqual(self.groups(), [{"label": None, "apps": self.available_apps}])

    @override_settings(NOVA_ADMIN_NAV_GROUPS=GROUPS)
    def test_configured_sections_contain_original_allowed_app_dictionaries(self):
        result = self.groups([self.auth, self.catalog])
        self.assertEqual([group["label"] for group in result], ["业务管理", "系统管理"])
        self.assertIs(result[0]["apps"][0], self.catalog)
        self.assertIs(result[1]["apps"][0], self.auth)
        self.assertIs(result[0]["apps"][0]["models"], self.catalog["models"])

    @override_settings(NOVA_ADMIN_NAV_GROUPS=[
        {"label": "Unknown", "apps": ["not_installed"]},
        {"label": "Empty", "apps": []},
        {"label": "Invisible", "apps": ["invisible"]},
        {"label": "Allowed", "apps": ["catalog"]},
    ])
    def test_unknown_empty_and_no_visible_model_groups_are_skipped(self):
        invisible = allowed_app("invisible", "Secret")
        invisible["models"] = []
        result = self.groups([invisible, self.catalog])
        self.assertEqual(result, [{"label": "Allowed", "apps": [self.catalog]}])

    @override_settings(NOVA_ADMIN_NAV_GROUPS=[
        {"label": "First", "apps": ["catalog", "catalog"]},
        {"label": "Duplicate only", "apps": ["catalog"]},
        {"label": "Second", "apps": ["catalog", "auth"]},
    ])
    def test_first_membership_wins_and_duplicate_only_group_disappears(self):
        result = self.groups([self.auth, self.catalog])
        self.assertEqual(result, [
            {"label": "First", "apps": [self.catalog]},
            {"label": "Second", "apps": [self.auth]},
        ])

    @override_settings(NOVA_ADMIN_NAV_GROUPS=[{"label": "Business", "apps": ["catalog"]}])
    def test_ungrouped_apps_have_one_fallback_in_native_order(self):
        result = self.groups()
        self.assertEqual(result, [
            {"label": "Business", "apps": [self.catalog]},
            {"label": "其他应用", "apps": [self.auth, self.audit]},
        ])

    @override_settings(NOVA_ADMIN_NAV_GROUPS=GROUPS)
    def test_no_fallback_when_every_allowed_app_is_grouped(self):
        result = self.groups([self.catalog, self.auth])
        self.assertNotIn("其他应用", [group["label"] for group in result])

    @override_settings(NOVA_ADMIN_NAV_GROUPS=GROUPS)
    def test_duplicate_available_apps_keep_only_first_original_dictionary(self):
        duplicate = allowed_app("catalog", "UnexpectedSecondProduct")
        available = [self.catalog, duplicate, self.auth, self.catalog]
        before = deepcopy(available)
        result = self.groups(available)
        self.assertEqual(grouped_apps(result), [self.catalog, self.auth])
        self.assertIs(result[0]["apps"][0], self.catalog)
        self.assertEqual(available, before)

    @override_settings(NOVA_ADMIN_NAV_GROUPS=GROUPS)
    def test_absent_or_empty_available_apps_cannot_create_links(self):
        self.assertEqual(grouped_apps(nova_navigation_groups(Context())), [])
        self.assertEqual(grouped_apps(self.groups([])), [])

    def test_malformed_top_level_configuration_is_safe(self):
        for configuration in (True, 9, "catalog", {"label": "Wrong shape", "apps": ["catalog"]}):
            with self.subTest(configuration=configuration):
                with override_settings(NOVA_ADMIN_NAV_GROUPS=configuration):
                    self.assertEqual(self.groups(), [{"label": None, "apps": self.available_apps}])

    @override_settings(NOVA_ADMIN_NAV_GROUPS=[
        None,
        7,
        "catalog",
        {},
        {"apps": ["catalog"]},
        {"label": "Missing apps"},
        {"label": None, "apps": ["catalog"]},
        {"label": "", "apps": ["catalog"]},
        {"label": 17, "apps": ["catalog"]},
        {"label": "String apps", "apps": "catalog"},
        {"label": "None apps", "apps": None},
        {"label": "Mapping apps", "apps": {"catalog": True}},
        {"label": "Invalid members", "apps": [None, {}, ["catalog"]]},
    ])
    def test_malformed_groups_are_skipped_without_consuming_visible_apps(self):
        self.assertEqual(self.groups(), [{"label": "其他应用", "apps": self.available_apps}])

    @override_settings(NOVA_ADMIN_NAV_GROUPS=[{"label": "Business", "apps": ["catalog"]}])
    def test_available_apps_and_configuration_are_not_mutated(self):
        before_apps = deepcopy(self.available_apps)
        before_configuration = deepcopy(settings.NOVA_ADMIN_NAV_GROUPS)
        first = self.groups()
        second = self.groups()
        self.assertEqual(self.available_apps, before_apps)
        self.assertEqual(settings.NOVA_ADMIN_NAV_GROUPS, before_configuration)
        self.assertEqual(first, second)
        self.assertIs(first[0]["apps"][0], self.catalog)

    @override_settings(NOVA_ADMIN_NAV_GROUPS=GROUPS)
    def test_grouping_does_not_query_or_consult_admin_or_app_registries(self):
        # SimpleTestCase prohibits database access; these mocks prohibit rebuilding apps.
        with (
            patch.object(admin.site, "get_app_list", side_effect=AssertionError("admin lookup")),
            patch.object(apps, "get_app_config", side_effect=AssertionError("app lookup")),
            patch.object(apps, "get_app_configs", side_effect=AssertionError("apps lookup")),
            patch.object(apps, "get_models", side_effect=AssertionError("model lookup")),
        ):
            result = self.groups([self.catalog])
        self.assertEqual(result, [{"label": "业务管理", "apps": [self.catalog]}])


@override_settings(
    NOVA_ADMIN_ENABLED=True,
    NOVA_ADMIN_NAVIGATION=True,
    NOVA_ADMIN_NAV_GROUPS=GROUPS,
)
class NavigationGroupIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = get_user_model().objects.create_superuser(
            username="group-navigation-admin", email="group-admin@example.invalid",
            password="test-only-GROUP4!",
        )
        cls.staff = get_user_model().objects.create_user(
            username="group-navigation-viewer", password="test-only-GROUP5!", is_staff=True,
        )
        cls.staff.user_permissions.add(Permission.objects.get(
            content_type__app_label="catalog", codename="view_product",
        ))
        cls.no_permissions = get_user_model().objects.create_user(
            username="group-navigation-empty", password="test-only-GROUP6!", is_staff=True,
        )
        cls.product = Product.objects.create(name="Grouped product", sku="GROUP-001", price=1)

    def setUp(self):
        self.client.force_login(self.superuser)
        self.list_url = reverse("admin:catalog_product_changelist")

    def markup(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        return navigation_markup(response)

    def test_configured_navigation_renders_section_app_model_ancestry(self):
        markup = self.markup()
        elements = NavigationElements(markup)
        sections = elements.with_class("nova-nav-section")
        headings = elements.with_class("nova-nav-section-title")
        self.assertEqual(len(sections), 2)
        self.assertEqual(len(headings), 2)
        self.assertTrue(all(element["tag"] == "summary" for element in headings))
        self.assertIn("业务管理", markup)
        self.assertIn("系统管理", markup)
        app_groups = elements.with_class("nova-nav-group")
        self.assertEqual(len(app_groups), 2)
        for app_group in app_groups:
            self.assertTrue(any(elements.has_class(parent, "nova-nav-section") for parent in app_group["ancestors"]))
        links = [element for element in elements.elements if element["attrs"].get("href") == self.list_url]
        self.assertEqual(len(links), 1)
        self.assertTrue(any(elements.has_class(parent, "nova-nav-group") for parent in links[0]["ancestors"]))
        self.assertTrue(any(elements.has_class(parent, "nova-nav-section") for parent in links[0]["ancestors"]))
        self.assertEqual(links[0]["attrs"].get("aria-current"), "page")

    @override_settings(NOVA_ADMIN_NAV_GROUPS=None)
    def test_no_configuration_keeps_existing_two_level_navigation(self):
        markup = self.markup()
        elements = NavigationElements(markup)
        self.assertTrue(elements.with_class("nova-nav-group"))
        self.assertFalse(elements.with_class("nova-nav-section"))
        self.assertFalse(elements.with_class("nova-nav-section-title"))
        self.assertIn(self.list_url, markup)

    @override_settings(NOVA_ADMIN_NAV_GROUPS=[
        {"label": "Unknown group", "apps": ["missing_app"]},
        {"label": "Empty group", "apps": []},
        *GROUPS,
    ])
    def test_invisible_groups_and_unpermitted_models_never_leak_to_view_only_user(self):
        self.client.force_login(self.staff)
        markup = self.markup()
        self.assertIn("业务管理", markup)
        self.assertNotIn("系统管理", markup)
        self.assertNotIn("Unknown group", markup)
        self.assertNotIn("Empty group", markup)
        self.assertEqual(len(NavigationElements(markup).with_class("nova-nav-section")), 1)
        self.assertIn(self.list_url, markup)
        for name in ("catalog_category", "catalog_tag", "auth_user", "auth_group"):
            self.assertNotIn(reverse(f"admin:{name}_changelist"), markup)
        self.assertNotIn(reverse("admin:catalog_product_add"), markup)
        self.assertNotIn("nova-nav-add", markup)

    def test_staff_without_model_permissions_has_no_group_headings_or_model_links(self):
        self.client.force_login(self.no_permissions)
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["available_apps"], [])
        markup = navigation_markup(response)
        self.assertNotIn("nova-nav-section", markup)
        self.assertNotIn(self.list_url, markup)
        self.assertNotIn("业务管理", markup)
        self.assertNotIn("系统管理", markup)

    @override_settings(NOVA_ADMIN_NAV_GROUPS=[
        {"label": "Business", "apps": ["catalog", "catalog"]},
        {"label": "Repeated", "apps": ["catalog"]},
    ])
    def test_duplicate_apps_render_once_and_ungrouped_apps_get_fallback(self):
        markup = self.markup()
        elements = NavigationElements(markup)
        self.assertEqual(len(elements.with_class("app-catalog")), 1)
        self.assertEqual(len(elements.with_class("app-auth")), 1)
        self.assertEqual(len(elements.with_class("nova-nav-section")), 2)
        self.assertNotIn("Repeated", markup)
        self.assertIn("其他应用", markup)

    def test_native_mode_excludes_grouped_navigation_and_retains_native_sidebar(self):
        session = self.client.session
        session[SESSION_KEY] = "native"
        session.save()
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(navigation_markup(response))
        self.assertContains(response, 'id="nav-sidebar"')
        self.assertNotContains(response, "nova-nav-section")
        self.assertNotContains(response, "nova_admin/navigation.js")

    @override_settings(NOVA_ADMIN_ENABLED=False)
    def test_global_disable_excludes_grouped_navigation(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(navigation_markup(response))
        self.assertContains(response, 'id="nav-sidebar"')
        self.assertNotContains(response, "nova-nav-section")
        self.assertNotContains(response, "nova_admin/navigation.js")

    @override_settings(NOVA_ADMIN_NAVIGATION=False)
    def test_navigation_opt_out_ignores_group_configuration(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(navigation_markup(response))
        self.assertContains(response, 'id="nav-sidebar"')
        self.assertNotContains(response, "nova-nav-section")

    def test_popup_excludes_grouped_navigation(self):
        response = self.client.get(
            reverse("admin:catalog_product_change", args=[self.product.pk]), {"_popup": "1"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(navigation_markup(response))
        self.assertNotContains(response, 'id="nav-sidebar"')
        self.assertNotContains(response, "nova-nav-section")

    def test_site_sidebar_disabled_excludes_grouped_navigation(self):
        with patch.object(admin.site, "enable_nav_sidebar", False):
            response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(navigation_markup(response))
        self.assertNotContains(response, 'id="nav-sidebar"')
        self.assertNotContains(response, "nova-nav-section")

    def test_malicious_group_label_is_escaped(self):
        label = '<img src=x onerror="alert(1)"> & "unsafe"'
        with override_settings(NOVA_ADMIN_NAV_GROUPS=[{"label": label, "apps": ["catalog"]}]):
            markup = self.markup()
        self.assertIn(str(escape(label)), markup)
        self.assertNotIn(label, markup)
        self.assertFalse(any(element["tag"] == "img" for element in NavigationElements(markup).elements))

    @override_settings(NOVA_ADMIN_NAV_GROUPS=[None, {"label": "Bad", "apps": "catalog"}, {}])
    def test_malformed_configuration_does_not_break_real_admin(self):
        markup = self.markup()
        self.assertIn(self.list_url, markup)
        self.assertIn("其他应用", markup)
        self.assertNotIn(">Bad<", markup)
