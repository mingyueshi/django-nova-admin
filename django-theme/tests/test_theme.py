from copy import deepcopy
from decimal import Decimal

from django.conf import settings
from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from catalog.admin import ProductAdmin
from catalog.models import Product
from nova_admin.preferences import SESSION_KEY


class ThemeIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_user = get_user_model().objects.create_superuser(
            username="theme-test-admin", email="admin@example.invalid", password="test-only-random-8s!x"
        )
        cls.staff = get_user_model().objects.create_user(
            username="limited-staff", password="test-only-9f@2", is_staff=True
        )
        cls.product = Product.objects.create(name="测试商品 Alpha", sku="NOVA-001", price=Decimal("199"), stock=4)
        cls.other = Product.objects.create(name="测试商品 Beta", sku="NOVA-002", price=Decimal("299"), stock=8, status="active")

    def setUp(self):
        self.client.force_login(self.admin_user)
        self.index = reverse("admin:index")
        self.list_url = reverse("admin:catalog_product_changelist")
        self.preference = reverse("nova_admin:preference")

    def mode(self, mode):
        session = self.client.session
        session[SESSION_KEY] = mode
        session.save()

    def test_same_admin_registration_is_used(self):
        self.assertIsInstance(admin.site.get_model_admin(Product), ProductAdmin)
        self.assertEqual(admin.site.get_model_admin(Product).search_fields, ["name", "sku"])
        self.assertEqual(admin.site.get_model_admin(Product).list_filter, ["status"])

    @override_settings(NOVA_ADMIN_DEFAULT_MODE="dark")
    def test_dark_default_and_original_assets_remain(self):
        response = self.client.get(self.index)
        self.assertContains(response, "nova_admin/theme.css")
        self.assertContains(response, "nova-mode-dark")
        self.assertContains(response, "admin/css/base.css")
        self.assertContains(response, "admin/js/theme.js")
        self.assertContains(response, 'id="logout-form"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertContains(response, self.preference)

    def test_light_session_selection(self):
        response = self.client.post(self.preference, {"mode": "light", "next": self.list_url})
        self.assertRedirects(response, self.list_url)
        self.assertEqual(self.client.session[SESSION_KEY], "light")
        self.assertContains(self.client.get(self.list_url), "nova-mode-light")

    def test_native_mode_removes_all_theme_css_and_classes(self):
        self.client.post(self.preference, {"mode": "native", "next": self.list_url})
        response = self.client.get(self.list_url)
        self.assertNotContains(response, "nova_admin/theme.css")
        self.assertNotContains(response, "nova-mode-")
        self.assertContains(response, "admin/css/changelists.css")
        self.assertContains(response, "nova-theme-switcher")  # Plain control to re-enable.
        self.assertContains(response, 'id="changelist-form"')

    @override_settings(NOVA_ADMIN_ENABLED=False)
    def test_global_disable_is_fully_native(self):
        response = self.client.get(self.index)
        self.assertNotContains(response, "nova_admin/theme.css")
        self.assertNotContains(response, "nova-theme-switcher")
        self.assertEqual(self.client.post(self.preference, {"mode": "dark"}).status_code, 404)

    def test_removing_opt_in_app_restores_original_templates(self):
        apps = [app for app in settings.INSTALLED_APPS if app != "nova_admin"]
        with override_settings(INSTALLED_APPS=apps):
            response = self.client.get(self.index)
            self.assertContains(response, "admin/css/base.css")
            self.assertNotContains(response, "nova_admin/theme.css")
            self.assertNotContains(response, "nova-theme-switcher")

    def test_missing_processor_degrades_to_native(self):
        templates = deepcopy(settings.TEMPLATES)
        templates[0]["OPTIONS"]["context_processors"].remove("nova_admin.context_processors.theme")
        with override_settings(TEMPLATES=templates):
            response = self.client.get(self.index)
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, "nova_admin/theme.css")

    def test_get_cannot_change_preference(self):
        self.assertEqual(self.client.get(self.preference, {"mode": "native"}).status_code, 405)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_invalid_mode_does_not_mutate_session(self):
        self.assertEqual(self.client.post(self.preference, {"mode": "invalid"}).status_code, 400)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_csrf_is_enforced(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin_user)
        self.assertEqual(client.post(self.preference, {"mode": "native"}).status_code, 403)
        client.get(self.index)
        token = client.cookies["csrftoken"].value
        response = client.post(self.preference, {"mode": "native", "csrfmiddlewaretoken": token})
        self.assertRedirects(response, self.index)

    def test_external_and_traversal_returns_fall_back(self):
        for unsafe in [
            "https://evil.example/", "//evil.example/admin/", "/somewhere/", "/admin-other/",
            "/admin/../outside", "/admin/%2e%2e/outside", "/admin/%5c..%5coutside",
            "https://testserver/admin/", "javascript:alert(1)", "/admin/\n/evil", "/admin/%0aevil",
            "/admin//evil", "\\\\evil.example\\admin\\",
        ]:
            with self.subTest(next=unsafe):
                response = self.client.post(self.preference, {"mode": "dark", "next": unsafe})
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.url, self.index)

    def test_safe_admin_return_preserves_search_query(self):
        destination = self.list_url + "?q=Alpha&status__exact=draft"
        response = self.client.post(self.preference, {"mode": "dark", "next": destination})
        self.assertEqual(response.url, destination)

    def test_anonymous_cannot_change_preferences(self):
        self.client.logout()
        response = self.client.post(self.preference, {"mode": "dark"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("admin:login")))
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_non_staff_cannot_change_preferences(self):
        user = get_user_model().objects.create_user(username="ordinary", password="test-only-3x!3")
        self.client.force_login(user)
        response = self.client.post(self.preference, {"mode": "dark"})
        self.assertEqual(response.status_code, 302)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_inactive_staff_cannot_change_preferences(self):
        self.staff.is_active = False
        self.staff.save()
        self.client.force_login(self.staff)
        self.assertEqual(self.client.post(self.preference, {"mode": "dark"}).status_code, 302)
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_native_search_and_list_filter_in_all_modes(self):
        for mode in ["dark", "light", "native"]:
            with self.subTest(mode=mode):
                self.mode(mode)
                response = self.client.get(self.list_url, {"q": "NOVA-001"})
                self.assertEqual(list(response.context["cl"].queryset), [self.product])
                self.assertContains(response, 'name="q"')
                response = self.client.get(self.list_url, {"status__exact": "active"})
                self.assertEqual(list(response.context["cl"].queryset), [self.other])
                self.assertContains(response, 'id="changelist-filter"')

    def test_native_change_form_and_inline_assets_are_preserved(self):
        response = self.client.get(reverse("admin:catalog_product_change", args=[self.product.pk]))
        self.assertContains(response, 'name="name"')
        self.assertContains(response, 'name="variants-TOTAL_FORMS"')
        self.assertContains(response, "admin/js/inlines.js")
        self.assertContains(response, "admin/css/forms.css")
        self.assertContains(response, 'name="_save"')
        self.assertContains(response, 'id="logout-form"')

    def test_native_form_validation_is_preserved(self):
        data = self.product_form_data(price="-10")
        response = self.client.post(reverse("admin:catalog_product_add"), data)
        self.assertEqual(response.status_code, 200)
        self.assertIn("price", response.context["adminform"].form.errors)
        self.assertFalse(Product.objects.filter(sku="NOVA-003").exists())

    def test_native_add_and_admin_audit_log_work(self):
        response = self.client.post(reverse("admin:catalog_product_add"), self.product_form_data())
        self.assertEqual(response.status_code, 302)
        created = Product.objects.get(sku="NOVA-003")
        self.assertEqual(created.name, "新增商品")
        self.assertTrue(LogEntry.objects.filter(object_id=str(created.pk), action_flag=1).exists())

    def test_native_bulk_action_works(self):
        response = self.client.post(self.list_url, {"action": "publish_products", "_selected_action": [self.product.pk], "index": "0"})
        self.assertEqual(response.status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, Product.Status.ACTIVE)

    def test_permissions_not_bypassed_by_skin(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.list_url).status_code, 403)
        self.assertEqual(self.client.get(reverse("admin:catalog_product_add")).status_code, 403)
        response = self.client.get(self.index)
        self.assertNotContains(response, self.list_url)

    def test_view_only_user_has_no_write_actions(self):
        self.staff.user_permissions.add(Permission.objects.get(codename="view_product"))
        self.client.force_login(self.staff)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'value="publish_products"')
        response = self.client.post(self.list_url, {"action": "publish_products", "_selected_action": [self.product.pk]})
        self.assertEqual(response.status_code, 200)  # Native Admin ignores unavailable actions.
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, Product.Status.DRAFT)

    def test_login_and_logout_remain_native(self):
        self.client.logout()
        response = self.client.get(self.index)
        self.assertEqual(response.status_code, 302)
        response = self.client.get(reverse("admin:login"))
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="password"')
        self.assertNotContains(response, "nova-theme-switcher")
        self.assertTrue(self.client.login(username="theme-test-admin", password="test-only-random-8s!x"))
        self.assertEqual(self.client.get(reverse("admin:logout")).status_code, 405)
        self.assertEqual(self.client.post(reverse("admin:logout")).status_code, 200)

    def test_popup_keeps_native_structure_without_header_controls(self):
        response = self.client.get(reverse("admin:catalog_product_add"), {"_popup": "1"})
        self.assertContains(response, "popup ")
        self.assertNotContains(response, "nova-theme-switcher")
        self.assertContains(response, 'name="_popup"')

    @override_settings(ROOT_URLCONF="tests.alternate_urls")
    def test_non_default_admin_prefix_is_preserved(self):
        preference = reverse("nova_admin:preference")
        index = reverse("admin:index")
        self.assertEqual(index, "/backoffice/")
        response = self.client.post(preference, {"mode": "light", "next": "/backoffice/catalog/product/?q=Alpha"})
        self.assertEqual(response.url, "/backoffice/catalog/product/?q=Alpha")
        response = self.client.post(preference, {"mode": "light", "next": "/admin/"})
        self.assertEqual(response.url, index)

    @override_settings(NOVA_ADMIN_DEFAULT_MODE="native")
    def test_native_can_be_the_default(self):
        self.assertNotContains(self.client.get(self.index), "nova_admin/theme.css")

    @override_settings(NOVA_ADMIN_DEFAULT_MODE="dark")
    def test_malformed_session_preference_degrades_safely(self):
        self.mode(["bad", "value"])
        self.assertContains(self.client.get(self.index), "nova-mode-dark")

    @staticmethod
    def product_form_data(**overrides):
        data = {
            "name": "新增商品", "sku": "NOVA-003", "price": "50.00", "stock": "10", "status": "draft", "_save": "Save",
            "variants-TOTAL_FORMS": "1", "variants-INITIAL_FORMS": "0", "variants-MIN_NUM_FORMS": "0", "variants-MAX_NUM_FORMS": "1000",
            "variants-0-name": "", "variants-0-value": "",
        }
        data.update(overrides)
        return data
