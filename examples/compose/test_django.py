"""Real Django clients/models against SQLite; not container/Postgres coverage."""
import importlib
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.conf import settings
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ImproperlyConfigured
from django.test import Client, SimpleTestCase, TestCase
from django.urls import NoReverseMatch, reverse

from catalog.admin import ProductAdmin
from catalog.models import Category, MemberProfile, NewsItem, Product, Tag
from config.compose_sites import warehouse_site
from config.compose_settings import _secret_file
from nova_admin.preferences import SESSION_KEY
from examples.compose.start import seed


class SecretSettingsTests(SimpleTestCase):
    def test_missing_short_and_multiline_secrets_fail_closed(self):
        with patch.dict("os.environ", {}, clear=True), self.assertRaises(ImproperlyConfigured):
            _secret_file("NOVA_TEST_SECRET_FILE")
        with tempfile.TemporaryDirectory() as temporary:
            secret = Path(temporary) / "key"
            for value in ("too-short", "a" * 32 + "\n" + "b" * 32):
                secret.write_text(value)
                with patch.dict("os.environ", {"NOVA_TEST_SECRET_FILE": str(secret)}), self.assertRaises(ImproperlyConfigured):
                    _secret_file("NOVA_TEST_SECRET_FILE")

    def test_postgres_configuration_is_explicit_but_not_connected(self):
        module = importlib.import_module("config.compose_settings")
        self.assertEqual(module.DATABASES["default"]["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(module.DATABASES["default"]["HOST"], "db")
        self.assertNotIn("*", module.ALLOWED_HOSTS)
        self.assertEqual(module.NOVA_ADMIN_URL_NAMESPACES, {"admin": "admin_theme", "warehouse": "warehouse_theme"})


class ComposeSiteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # A new random test-only password; no published account credential.
        cls.user = get_user_model().objects.create_superuser(username="compose-test", password=None)
        cls.staff = get_user_model().objects.create_user(username="compose-viewer", is_staff=True)
        cls.staff.user_permissions.add(Permission.objects.get(content_type__app_label="catalog", codename="view_product"))
        seed()

    def test_native_registrations_and_independent_model_admin_instances(self):
        self.assertIsInstance(admin.site.get_model_admin(Product), ProductAdmin)
        self.assertIsInstance(warehouse_site.get_model_admin(Product), ProductAdmin)
        self.assertIsNot(admin.site.get_model_admin(Product), warehouse_site.get_model_admin(Product))
        for model in (Product, Category, Tag):
            self.assertTrue(warehouse_site.is_registered(model))
        self.assertFalse(warehouse_site.is_registered(NewsItem))
        self.assertTrue(admin.site.is_registered(NewsItem))
        self.assertTrue(admin.site.is_registered(get_user_model()))

    def test_seed_preserves_edits_relationships_and_authentication_users(self):
        product = Product.objects.get(sku="NOVA-COMPOSE-KEYBOARD")
        product.name = "User edited title"
        product.save()
        product.tags.clear()
        product.variants.all().delete()
        count = get_user_model().objects.count()
        seed()
        product.refresh_from_db()
        self.assertEqual(product.name, "User edited title")
        self.assertFalse(product.tags.exists())
        self.assertFalse(product.variants.exists())
        self.assertEqual(Product.objects.count(), 2)
        self.assertEqual(MemberProfile.objects.count(), 1)
        self.assertEqual(NewsItem.objects.count(), 1)
        self.assertEqual(get_user_model().objects.count(), count)

    def test_both_sites_render_model_pages_and_own_preference_routes(self):
        self.client.force_login(self.user)
        for name in ("admin", "warehouse"):
            response = self.client.get(reverse(f"{name}:catalog_product_changelist"))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["nova_admin_preference_url"], reverse(f"{name}_theme:preference"))
            change = self.client.get(reverse(f"{name}:catalog_product_change", args=[Product.objects.first().pk]))
            self.assertContains(change, f'data-ajax--url="{reverse(f"{name}:autocomplete")}"')

    def test_anonymous_and_limited_staff_keep_native_permissions(self):
        for name in ("admin", "warehouse"):
            self.client.logout()
            response = self.client.get(reverse(f"{name}:catalog_product_changelist"))
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.url.startswith(reverse(f"{name}:login")))
            self.client.force_login(self.staff)
            self.assertEqual(self.client.get(reverse(f"{name}:catalog_product_changelist")).status_code, 200)
            self.assertEqual(self.client.get(reverse(f"{name}:catalog_product_add")).status_code, 403)

    def test_preference_csrf_and_site_return_boundaries(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        for name, other in (("admin", "warehouse"), ("warehouse", "admin")):
            preference = reverse(f"{name}_theme:preference")
            self.assertEqual(client.post(preference, {"mode": "dark"}).status_code, 403)
            client.get(reverse(f"{name}:index"))
            response = client.post(preference, {
                "mode": "native", "next": reverse(f"{other}:index"),
                "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
            })
            self.assertEqual(response.url, reverse(f"{name}:index"))
            self.assertEqual(client.session[SESSION_KEY], "native")

    def test_captcha_opt_in_and_native_mode_on_both_login_pages(self):
        for name in ("admin", "warehouse"):
            session = self.client.session
            session[SESSION_KEY] = "native"
            session.save()
            response = self.client.get(reverse(f"{name}:login"))
            self.assertEqual(response.status_code, 200)
            self.assertEqual("captcha" in response.context["form"].fields, settings.NOVA_EXAMPLE_CAPTCHA)
            if settings.NOVA_EXAMPLE_CAPTCHA:
                self.assertContains(response, reverse("nova-captcha-refresh"))
                with patch("django.contrib.auth.forms.authenticate") as authenticate:
                    self.client.post(reverse(f"{name}:login"), {"username": "compose-test", "password": "irrelevant"})
                authenticate.assert_not_called()
        if not settings.NOVA_EXAMPLE_CAPTCHA:
            with self.assertRaises(NoReverseMatch):
                reverse("nova-captcha-refresh")

