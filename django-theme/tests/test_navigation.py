"""Optional navigation must derive from AdminSite's own permission-filtered apps."""
import re

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse

from catalog.models import Product
from nova_admin.preferences import SESSION_KEY


def navigation_markup(response):
    match = re.search(r'<nav\b[^>]*\bnova-navigation\b[^>]*>(.*?)</nav>', response.content.decode(), re.S)
    return match.group(1) if match else ""


@override_settings(NOVA_ADMIN_NAVIGATION=True)
class OptionalNavigationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user(
            username="navigation-staff", password="test-only-NAV3!", is_staff=True,
        )
        cls.staff.user_permissions.add(Permission.objects.get(
            content_type__app_label="catalog", codename="view_product",
        ))
        cls.product = Product.objects.create(name="Navigation product", sku="NAV-1", price=1)

    def setUp(self):
        self.client.force_login(self.staff)
        self.list_url = reverse("admin:catalog_product_changelist")

    def test_optional_navigation_contains_only_permitted_models(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        markup = navigation_markup(response)
        self.assertTrue(markup)
        self.assertIn(self.list_url, markup)
        self.assertNotIn(reverse("admin:catalog_product_add"), markup)
        self.assertNotIn(reverse("admin:catalog_category_changelist"), markup)
        self.assertNotIn(reverse("admin:catalog_tag_changelist"), markup)
        self.assertNotIn(reverse("admin:auth_user_changelist"), markup)
        self.assertIn('aria-current="page"', markup)

    def test_mobile_disclosure_reuses_the_only_permission_filtered_sidebar(self):
        response = self.client.get(self.list_url)
        html = response.content.decode()
        self.assertContains(response, 'id="nova-mobile-nav-toggle"', count=1)
        self.assertContains(response, 'aria-controls="nav-sidebar" aria-expanded="false" hidden')
        self.assertContains(response, 'id="nav-sidebar"', count=1)
        self.assertRegex(html, r'<button\b[^>]*id="nova-mobile-nav-toggle"[^>]*type="button"')
        self.assertNotIn('inert', html)

    def test_add_link_appears_only_with_model_add_permission(self):
        self.staff.user_permissions.add(Permission.objects.get(
            content_type__app_label="catalog", codename="add_product",
        ))
        response = self.client.get(self.list_url)
        self.assertIn(reverse("admin:catalog_product_add"), navigation_markup(response))

    @override_settings(NOVA_ADMIN_NAVIGATION=False)
    def test_navigation_opt_out_retains_native_sidebar(self):
        response = self.client.get(self.list_url)
        self.assertContains(response, 'id="nav-sidebar"')
        self.assertFalse(navigation_markup(response))
        self.assertNotContains(response, "nova-mobile-nav-toggle")
        self.assertContains(response, 'id="nav-filter"')
        self.assertContains(response, self.list_url)

    def test_native_mode_retains_native_sidebar_and_recovery_control(self):
        session = self.client.session
        session[SESSION_KEY] = "native"
        session.save()
        response = self.client.get(self.list_url)
        self.assertContains(response, 'id="nav-sidebar"')
        self.assertFalse(navigation_markup(response))
        self.assertNotContains(response, "nova-mobile-nav-toggle")
        self.assertNotContains(response, "nova_admin/theme.css")
        self.assertContains(response, "nova-theme-switcher")

    @override_settings(NOVA_ADMIN_ENABLED=False)
    def test_global_disable_removes_optional_navigation(self):
        response = self.client.get(self.list_url)
        self.assertContains(response, 'id="nav-sidebar"')
        self.assertFalse(navigation_markup(response))
        self.assertNotContains(response, "nova-theme-switcher")

    def test_popup_and_login_do_not_gain_sidebar(self):
        response = self.client.get(reverse("admin:catalog_product_change", args=[self.product.pk]), {"_popup": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(navigation_markup(response))
        self.assertNotContains(response, 'id="nav-sidebar"')
        self.client.logout()
        response = self.client.get(reverse("admin:login"))
        self.assertFalse(navigation_markup(response))
        self.assertNotContains(response, 'id="nav-sidebar"')
