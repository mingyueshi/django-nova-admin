"""Real named AdminSite instances, not a mock replacement admin registry."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.admin import AdminSite
from django.test import Client, TestCase, override_settings
from django.urls import include, path, reverse

from catalog.admin import ProductAdmin
from catalog.models import Category, Product
from nova_admin.preferences import SESSION_KEY
from tests.multisite_urls import review_site, warehouse_site
from tests.test_navigation import navigation_markup
from nova_admin.urls import for_admin
from tests.test_theme_context import NestedUrls


SITE_NAMESPACES = {"warehouse": "warehouse_theme", "review": "review_theme"}


class RepeatedSiteNames:
    urlpatterns = []
    for side in ('east', 'west'):
        site = AdminSite(name='admin')
        patterns = [path('_theme/', include(for_admin(site), namespace='theme')), path('', site.urls)]
        urlpatterns.append(path(side + '/', include((patterns, 'portal'), namespace=side)))


@override_settings(
    ROOT_URLCONF="tests.multisite_urls",
    NOVA_ADMIN_NAVIGATION=True,
    NOVA_ADMIN_URL_NAMESPACES=SITE_NAMESPACES,
)
class MultipleAdminSiteTests(TestCase):
    def test_nested_instances_keep_their_own_fallback_and_next_boundary(self):
        self.client.force_login(self.superuser)
        for urlconf, site, prefix in ((NestedUrls, 'warehouse', '/{side}/warehouse/'), (RepeatedSiteNames, 'admin', '/{side}/')):
            with override_settings(ROOT_URLCONF=urlconf):
                for side in ('east', 'west'):
                    endpoint = (f'{side}:warehouse_theme:preference' if site == 'warehouse' else f'{side}:theme:preference')
                    index = prefix.format(side=side)
                    for destination in ('', index + '?q=kept', prefix.format(side='west' if side == 'east' else 'east')):
                        with self.subTest(site=site, side=side, destination=destination):
                            response = self.client.post(reverse(endpoint), {'mode': 'dark', 'next': destination})
                            self.assertEqual(response.url, destination if destination.startswith(index) else index)

    @classmethod
    def setUpTestData(cls):
        cls.superuser = get_user_model().objects.create_superuser(
            username="multisite-admin", email="admin@example.invalid", password="test-only-MULTI7!",
        )
        cls.staff = get_user_model().objects.create_user(
            username="warehouse-staff", password="test-only-MULTI8!", is_staff=True,
        )
        cls.staff.user_permissions.add(Permission.objects.get(
            content_type__app_label="catalog", codename="view_product",
        ))
        cls.category = Category.objects.create(name="Site category", slug="site-category")
        cls.product = Product.objects.create(name="Site product", sku="SITE-001", price=1, category=cls.category)

    def setUp(self):
        self.client.force_login(self.superuser)

    def test_existing_site_registrations_remain_native_and_distinct(self):
        self.assertIsInstance(warehouse_site.get_model_admin(Product), ProductAdmin)
        self.assertIsInstance(review_site.get_model_admin(Product), ProductAdmin)
        self.assertIsNot(warehouse_site.get_model_admin(Product), review_site.get_model_admin(Product))
        self.assertIs(warehouse_site.get_model_admin(Product).admin_site, warehouse_site)
        self.assertIs(review_site.get_model_admin(Product).admin_site, review_site)

    def test_each_site_renders_its_own_switcher_and_navigation_urls(self):
        for site in SITE_NAMESPACES:
            with self.subTest(site=site):
                response = self.client.get(reverse(f"{site}:catalog_product_changelist"))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["nova_admin_preference_url"], reverse(f"{SITE_NAMESPACES[site]}:preference"))
                self.assertContains(response, reverse(f"{SITE_NAMESPACES[site]}:preference"))
                markup = navigation_markup(response)
                self.assertIn(reverse(f"{site}:index"), markup)
                self.assertIn(reverse(f"{site}:catalog_product_changelist"), markup)
                other = "review" if site == "warehouse" else "warehouse"
                self.assertNotIn(reverse(f"{other}:index"), markup)
                self.assertNotContains(response, reverse(f"{SITE_NAMESPACES[other]}:preference"))

    def test_preference_return_cannot_cross_site_boundary(self):
        for site in SITE_NAMESPACES:
            with self.subTest(site=site):
                preference = reverse(f"{SITE_NAMESPACES[site]}:preference")
                index = reverse(f"{site}:index")
                destination = reverse(f"{site}:catalog_product_changelist") + "?q=SITE-001"
                response = self.client.post(preference, {"mode": "light", "next": destination})
                self.assertEqual(response.url, destination)
                other = "review" if site == "warehouse" else "warehouse"
                response = self.client.post(preference, {"mode": "dark", "next": reverse(f"{other}:index")})
                self.assertEqual(response.url, index)
                self.assertEqual(self.client.session[SESSION_KEY], "dark")

    def test_preference_uses_exact_site_permission_guard(self):
        self.client.force_login(self.staff)
        response = self.client.post(reverse("warehouse_theme:preference"), {"mode": "light"})
        self.assertRedirects(response, reverse("warehouse:index"))
        response = self.client.post(reverse("review_theme:preference"), {"mode": "dark"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("review:login")))
        self.assertEqual(self.client.session[SESSION_KEY], "light")
        self.assertEqual(self.client.get(reverse("warehouse:catalog_product_changelist")).status_code, 200)
        self.assertEqual(self.client.get(reverse("review:catalog_product_changelist")).status_code, 302)

    def test_anonymous_preferences_redirect_to_matching_site_login(self):
        self.client.logout()
        for site, namespace in SITE_NAMESPACES.items():
            with self.subTest(site=site):
                response = self.client.post(reverse(f"{namespace}:preference"), {"mode": "light"})
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(reverse(f"{site}:login")))
                self.assertNotIn(SESSION_KEY, self.client.session)

    def test_each_site_preference_keeps_csrf_protection(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.superuser)
        for site, namespace in SITE_NAMESPACES.items():
            with self.subTest(site=site):
                preference = reverse(f"{namespace}:preference")
                self.assertEqual(client.post(preference, {"mode": "light"}).status_code, 403)
                client.get(reverse(f"{site}:index"))
                response = client.post(preference, {"mode": "light", "csrfmiddlewaretoken": client.cookies["csrftoken"].value})
                self.assertRedirects(response, reverse(f"{site}:index"))

    def test_foreign_key_autocomplete_urls_use_current_site(self):
        for site in SITE_NAMESPACES:
            with self.subTest(site=site):
                response = self.client.get(reverse(f"{site}:catalog_product_change", args=[self.product.pk]))
                self.assertContains(response, f'data-ajax--url="{reverse(f"{site}:autocomplete")}"')
                self.assertContains(response, reverse(f"{site}:catalog_category_add"))
                response = self.client.get(reverse(f"{site}:autocomplete"), {
                    "app_label": "catalog", "model_name": "product", "field_name": "category", "term": "Site category",
                })
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["results"], [{"id": str(self.category.pk), "text": "Site category"}])

    @override_settings(NOVA_ADMIN_URL_NAMESPACES={"warehouse": "warehouse_theme"})
    def test_unmapped_site_does_not_borrow_other_sites_switcher(self):
        response = self.client.get(reverse("review:catalog_product_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "nova_admin/theme.css")
        self.assertEqual(response.context["nova_admin_preference_url"], "")
        self.assertNotContains(response, "nova-theme-switcher")
        self.assertNotContains(response, reverse("warehouse_theme:preference"))

    @override_settings(NOVA_ADMIN_URL_NAMESPACES={"review": "missing_theme_namespace"})
    def test_missing_mapped_urls_hide_switcher_without_breaking_admin(self):
        response = self.client.get(reverse("review:catalog_product_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "nova-theme-switcher")
        self.assertContains(response, 'id="changelist-form"')

    def test_native_recovery_stays_inside_same_site(self):
        for site, namespace in SITE_NAMESPACES.items():
            with self.subTest(site=site):
                session = self.client.session
                session[SESSION_KEY] = "native"
                session.save()
                destination = reverse(f"{site}:catalog_product_changelist") + "?q=SITE-001"
                response = self.client.get(destination)
                self.assertNotContains(response, "nova_admin/theme.css")
                self.assertContains(response, reverse(f"{namespace}:preference"))
                self.assertFalse(navigation_markup(response))
                response = self.client.post(reverse(f"{namespace}:preference"), {"mode": "dark", "next": destination}, follow=True)
                self.assertEqual(response.redirect_chain, [(destination, 302)])
                self.assertContains(response, "nova-mode-dark")
                self.assertIn(reverse(f"{site}:index"), navigation_markup(response))
