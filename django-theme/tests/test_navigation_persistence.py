"""Real markup contracts for Nova's independently owned navigation enhancement."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse

from catalog.models import Product
from nova_admin.preferences import SESSION_KEY
from tests.test_navigation_groups import NavigationElements


@override_settings(NOVA_ADMIN_ENABLED=True, NOVA_ADMIN_NAVIGATION=True)
class NavigationPersistenceMarkupTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.viewer = get_user_model().objects.create_user(username="nav-state-viewer", is_staff=True)
        cls.viewer.user_permissions.add(Permission.objects.get(
            content_type__app_label="catalog", codename="view_product",
        ))
        cls.product = Product.objects.create(name="Navigation state", sku="NAV-STATE", price=1)

    def setUp(self):
        self.client.force_login(self.viewer)

    def elements(self, response):
        self.assertEqual(response.status_code, 200)
        return NavigationElements(response.content.decode()).elements

    @staticmethod
    def nav(elements):
        return next(item for item in elements if item["attrs"].get("id") == "nav-sidebar")

    def test_filter_remains_one_labelled_search_control_with_native_id(self):
        elements = self.elements(self.client.get(reverse("admin:catalog_product_changelist")))
        filters = [item for item in elements if item["attrs"].get("id") == "nav-filter"]
        self.assertEqual(len(filters), 1)
        self.assertEqual(filters[0]["tag"], "input")
        self.assertEqual(filters[0]["attrs"]["type"], "search")
        self.assertEqual(filters[0]["attrs"]["maxlength"], "200")
        self.assertTrue(filters[0]["attrs"]["aria-label"])
        self.assertNotIn("hidden", filters[0]["attrs"])
        self.assertNotIn("disabled", filters[0]["attrs"])
        self.assertEqual(len([item for item in elements if item["tag"] == "label" and item["attrs"].get("for") == "nav-filter"]), 1)

    def test_only_permission_filtered_nodes_receive_state_identifiers(self):
        elements = self.elements(self.client.get(reverse("admin:catalog_product_changelist")))
        nav = self.nav(elements)
        self.assertRegex(nav["attrs"]["data-nova-nav-scope"], r"^[0-9a-f]{64}$")
        self.assertNotIn("data-user-id", nav["attrs"])
        self.assertNotIn("data-nova-nav-user", nav["attrs"])
        app_keys = [item["attrs"]["data-nova-nav-app"] for item in elements if "data-nova-nav-app" in item["attrs"]]
        model_keys = [item["attrs"]["data-nova-nav-model"] for item in elements if "data-nova-nav-model" in item["attrs"]]
        self.assertEqual(app_keys, ["catalog"])
        self.assertEqual(model_keys, ["product"])

    def test_same_site_scope_is_stable_across_index_list_and_change(self):
        scopes = []
        for url in [reverse("admin:index"), reverse("admin:catalog_product_changelist"),
                    reverse("admin:catalog_product_change", args=[self.product.pk])]:
            scopes.append(self.nav(self.elements(self.client.get(url)))["attrs"]["data-nova-nav-scope"])
        self.assertEqual(len(set(scopes)), 1)

    @override_settings(ROOT_URLCONF="tests.multisite_urls", NOVA_ADMIN_URL_NAMESPACES={
        "warehouse": "warehouse_theme", "review": "review_theme",
    })
    def test_independent_adminsites_get_distinct_preference_scopes(self):
        self.viewer.user_permissions.add(Permission.objects.get(
            content_type__app_label="catalog", codename="view_category",
        ))
        warehouse = self.nav(self.elements(self.client.get(reverse("warehouse:catalog_product_changelist"))))
        review = self.nav(self.elements(self.client.get(reverse("review:catalog_product_changelist"))))
        self.assertNotEqual(warehouse["attrs"]["data-nova-nav-scope"], review["attrs"]["data-nova-nav-scope"])

    def test_django_initializes_before_deferred_nova_filter_owner(self):
        elements = self.elements(self.client.get(reverse("admin:catalog_product_changelist")))
        scripts = [item["attrs"] for item in elements if item["tag"] == "script"]
        upstream = next(index for index, item in enumerate(scripts) if item.get("src", "").endswith("admin/js/nav_sidebar.js"))
        nova = next(index for index, item in enumerate(scripts) if item.get("src", "").endswith("nova_admin/navigation.js"))
        self.assertLess(upstream, nova)
        self.assertIn("defer", scripts[upstream])
        self.assertIn("defer", scripts[nova])

    def test_details_and_summary_keep_native_semantics(self):
        elements = self.elements(self.client.get(reverse("admin:catalog_product_changelist")))
        details = [item for item in elements if item["tag"] == "details" and any(
            name in item["attrs"].get("class", "").split() for name in ["nova-nav-group", "nova-nav-section"]
        )]
        self.assertTrue(details)
        for item in details:
            self.assertNotIn("open", item["attrs"])
            children = [child for child in elements if child["ancestors"] and child["ancestors"][-1] is item]
            self.assertEqual(children[0]["tag"], "summary")
            self.assertNotIn("role", children[0]["attrs"])
            self.assertNotIn("tabindex", children[0]["attrs"])
            self.assertFalse(any(child["tag"] in {"a", "button", "input"} and children[0] in child["ancestors"] for child in elements))
        nav = self.nav(elements)
        current = [item for item in elements if item["attrs"].get("aria-current") == "page" and nav in item["ancestors"]]
        self.assertEqual(len(current), 1)
        self.assertEqual(current[0]["attrs"]["href"], reverse("admin:catalog_product_changelist"))

    @override_settings(NOVA_ADMIN_NAV_GROUPS=[{"key": "business", "label": "Business", "apps": ["catalog"]}])
    def test_both_disclosure_levels_are_closed_even_on_the_current_model(self):
        elements = self.elements(self.client.get(reverse("admin:catalog_product_changelist")))
        details = [item for item in elements if item["tag"] == "details" and any(
            name in item["attrs"].get("class", "").split() for name in ["nova-nav-group", "nova-nav-section"]
        )]
        self.assertEqual(len(details), 2)
        self.assertTrue(all("open" not in item["attrs"] for item in details))
        section = next(item for item in details if "nova-nav-section" in item["attrs"]["class"])
        self.assertEqual(section["attrs"]["data-nova-nav-section"], "business")

    def test_native_mode_has_no_nova_state_attributes_or_script(self):
        session = self.client.session
        session[SESSION_KEY] = "native"
        session.save()
        response = self.client.get(reverse("admin:catalog_product_changelist"))
        elements = self.elements(response)
        self.assertNotIn("data-nova-nav-scope", self.nav(elements)["attrs"])
        self.assertNotContains(response, "data-nova-nav-app")
        self.assertNotContains(response, "nova_admin/navigation.js")
        self.assertContains(response, 'id="nav-filter"')
