from unittest.mock import patch

from bs4 import BeautifulSoup
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import DatabaseError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from catalog.models import Product
from nova_admin.preferences import SESSION_KEY


class DashboardColumnTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser("dashboard-admin", password=None)
        cls.viewer = get_user_model().objects.create_user("dashboard-reader", is_staff=True)
        cls.viewer.user_permissions.add(Permission.objects.get(codename="view_product"))
        cls.product = Product.objects.create(name="One", sku="VISIBLE", price=5)
        Product.objects.create(name="Two", sku="SECOND", price=7)

    def setUp(self):
        self.client.force_login(self.viewer)
        self.index = reverse("admin:index")
        self.url = reverse("admin:catalog_product_changelist")

    def panel(self, url=None):
        response = self.client.get(url or self.url)
        self.assertEqual(response.status_code, 200)
        return [(col["key"], col["visible"]) for col in response.context["nova_columns"]]

    def save(self, order, visible, url=None):
        return self.client.post(url or self.url, {
            "_nova_columns": "save", "order": order, "visible": visible,
        })

    def metric(self):
        response = self.client.get(self.index)
        self.assertEqual(response.status_code, 200)
        return BeautifulSoup(response.content, "html.parser").select_one(".nova-kpis")

    def test_kpi_counts_only_this_sites_visible_queryset_including_real_zero(self):
        owner = admin.site.get_model_admin(Product)
        with patch.object(owner, "get_queryset", return_value=Product.objects.filter(pk=self.product.pk)):
            self.assertEqual(self.metric().dd.get_text(strip=True), "1")
        with patch.object(owner, "get_queryset", return_value=Product.objects.none()):
            self.assertEqual(self.metric().dd.get_text(strip=True), "0")
        self.assertEqual(self.metric().dd.get_text(strip=True), "2")

    @override_settings(ROOT_URLCONF="tests.multisite_urls", NOVA_ADMIN_URL_NAMESPACES={})
    def test_other_sites_home_uses_its_own_model_registration(self):
        from tests.multisite_urls import warehouse_site

        self.index = reverse("warehouse:index")
        with patch.object(warehouse_site, "index_template", "project_admin/dashboard.html"), patch.object(
            warehouse_site.get_model_admin(Product), "get_queryset", return_value=Product.objects.none()
        ), patch.object(admin.site.get_model_admin(Product), "get_queryset", side_effect=AssertionError("wrong site")):
            self.assertEqual(self.metric().dd.get_text(strip=True), "0")

    def test_kpi_permission_empty_failure_and_native_fallback(self):
        owner = admin.site.get_model_admin(Product)
        with patch.object(owner, "get_queryset", side_effect=DatabaseError("private detail")):
            metric = self.metric()
            self.assertIn("暂时无法加载", metric.get_text())
            self.assertNotIn("private detail", metric.get_text())
        self.viewer.user_permissions.clear()
        self.viewer.user_permissions.add(Permission.objects.get(codename="add_product"))
        with patch.object(owner, "get_queryset", side_effect=AssertionError("unauthorized aggregate")):
            metric = self.metric()
            self.assertIsNone(metric.dt)
            self.assertIn("暂无可展示", metric.get_text())
        with override_settings(NOVA_ADMIN_ENABLED=False):
            self.assertIsNone(self.metric())

    def test_column_save_reset_and_authorized_schema_changes(self):
        defaults = dict(self.panel())
        order = list(reversed(defaults))
        self.assertNotIn("name", order)
        self.assertNotIn("featured", order)
        self.assertNotIn("action_checkbox", order)
        self.assertEqual(self.save(order, ["stock"]).status_code, 200)
        self.assertEqual(self.panel(), [(key, key == "stock") for key in order])
        owner = admin.site.get_model_admin(Product)
        with patch.object(owner, "get_list_display", return_value=["name", "stock", "sku"]):
            self.assertEqual(self.panel(), [("stock", True), ("sku", False)])
            self.assertEqual(self.save(order, ["stock"]).status_code, 400)
        with patch.object(owner, "nova_preference_columns", ("stock", "sku", "name")):
            self.assertEqual(self.save(["name", "stock", "sku"], []).status_code, 400)
        self.assertEqual(self.save(order, ["unlisted"]).status_code, 400)
        self.assertEqual(self.save(order[:-1] + order[:1], []).status_code, 400)
        self.assertEqual(self.panel(), [(key, key == "stock") for key in order])
        self.assertEqual(self.client.post(self.url, {"_nova_columns": "reset"}).status_code, 200)
        self.assertEqual(self.panel(), list(defaults.items()))

    def test_preference_scope_in_same_session_is_per_account_site_and_model(self):
        self.client.force_login(self.admin)
        original = self.panel()
        order = [key for key, _ in original]
        self.assertEqual(self.save(order, []).status_code, 200)
        pref_keys = [k for k in self.client.session.keys() if k.startswith("nova_columns:")]
        self.assertEqual(len(pref_keys), 1)
        key = pref_keys[0]
        saved = self.client.session[key]
        # Force the first account's record into the second account's session.
        self.client.force_login(self.viewer)
        session = self.client.session
        session[key] = saved
        session.save()
        self.assertEqual(self.panel(), original)
        self.client.force_login(self.admin)
        self.assertEqual(self.save(order, []).status_code, 200)
        news = reverse("admin:catalog_newsitem_changelist")
        self.assertTrue(all(visible for _, visible in self.panel(news)))
        self.assertEqual(self.save([name for name, _ in self.panel(news)], [], news).status_code, 200)
        self.client.post(news, {"_nova_columns": "reset"})
        with override_settings(ROOT_URLCONF="tests.multisite_urls", NOVA_ADMIN_URL_NAMESPACES={}):
            warehouse = reverse("warehouse:catalog_product_changelist")
            self.assertEqual(self.panel(warehouse), original)
            self.assertEqual(self.save(order, ["sku"], warehouse).status_code, 200)
            self.assertEqual(self.panel(reverse("review:catalog_product_changelist")), original)
        self.assertEqual(self.panel(), [(name, False) for name in order])

    def test_csrf_permissions_popup_and_native_controls(self):
        order = [key for key, _ in self.panel()]
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.viewer)
        data = {"_nova_columns": "save", "order": order, "visible": ["sku"]}
        self.assertEqual(strict.post(self.url, data).status_code, 403)
        strict.get(self.url)
        data["csrfmiddlewaretoken"] = strict.cookies["csrftoken"].value
        self.assertEqual(strict.post(self.url, data).status_code, 200)
        self.assertEqual(strict.post(self.url, {"_save": "Save", "form-TOTAL_FORMS": 0, "csrfmiddlewaretoken": data["csrfmiddlewaretoken"]}).status_code, 403)
        self.assertNotContains(self.client.get(self.url + "?_popup=1"), "nova_admin/columns.js")
        self.assertEqual(self.save(order, [], self.url + "?_popup=1").status_code, 404)
        session = self.client.session
        session[SESSION_KEY] = "native"
        session.save()
        self.assertNotContains(self.client.get(self.url), "nova_admin/columns.js")
        self.assertEqual(self.save(order, []).status_code, 404)
        self.viewer.user_permissions.clear()
        self.assertEqual(strict.post(self.url, data).status_code, 403)
