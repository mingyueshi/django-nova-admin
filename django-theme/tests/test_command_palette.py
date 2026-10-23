"""Command palette markup is gated by the current real AdminSite response."""
from copy import deepcopy
from pathlib import Path

from bs4 import BeautifulSoup
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.staticfiles import finders
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import translation

from catalog.models import Product
from nova_admin.preferences import SESSION_KEY


def nonce_context(request):
    return {'csp_nonce': 'command-test-nonce'}


@override_settings(NOVA_ADMIN_ENABLED=True, NOVA_ADMIN_NAVIGATION=True)
class CommandPaletteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.viewer = get_user_model().objects.create_user(username="command-viewer", is_staff=True)
        cls.viewer.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="catalog", codename__in=["view_product", "add_tag"],
        ))
        cls.product = Product.objects.create(name="Command product", sku="COMMAND-1", price=1)

    def setUp(self):
        self.client.force_login(self.viewer)
        self.url = reverse("admin:catalog_product_changelist")

    def soup(self, url=None):
        response = self.client.get(url or self.url)
        self.assertEqual(response.status_code, 200)
        return BeautifulSoup(response.content, "html.parser")

    def assert_absent(self, response):
        self.assertNotContains(response, "nova-command-palette")
        self.assertNotContains(response, "nova_admin/command-palette.js")
        self.assertNotContains(response, "nova_admin/command-palette.css")

    def test_single_hidden_entry_and_labelled_dialog_with_no_copied_menu(self):
        soup = self.soup()
        self.assertEqual(len(soup.select('[data-nova-command-open][hidden]')), 1)
        dialog = soup.select_one('dialog#nova-command-palette[hidden]')
        self.assertIsNotNone(dialog)
        self.assertIsNotNone(soup.find(id=dialog['aria-labelledby']))
        self.assertEqual(soup.select_one('[data-nova-command-open]')['aria-controls'], dialog['id'])
        query = dialog.select_one('input[type="search"]')
        self.assertIsNotNone(dialog.find('label', attrs={'for': query['id']}))
        self.assertEqual(query['maxlength'], '200')
        self.assertIsNotNone(dialog.select_one('[role="status"][aria-live="polite"]'))
        self.assertFalse(dialog.select('a,form'))
        ids = [element['id'] for element in soup.select('[id]')]
        self.assertEqual(len(ids), len(set(ids)))

    def test_source_is_current_permission_filtered_navigation_including_add_only(self):
        soup = self.soup()
        nav = soup.select_one('.nova-navigation')
        self.assertEqual(nav.select_one('.nova-nav-home')['href'], reverse('admin:index'))
        self.assertEqual([a['href'] for a in nav.select('th[scope="row"] a')], [self.url])
        tag_row = nav.select_one('[data-nova-nav-model="tag"]')
        self.assertIsNotNone(tag_row)
        self.assertIsNone(tag_row.select_one('th a'))
        self.assertEqual(tag_row.select_one('.nova-nav-add')['href'], reverse('admin:catalog_tag_add'))
        self.assertNotIn(reverse('admin:catalog_category_changelist'), str(nav))

    @override_settings(ROOT_URLCONF="tests.multisite_urls", NOVA_ADMIN_URL_NAMESPACES={
        "warehouse": "warehouse_theme", "review": "review_theme",
    })
    def test_multiple_sites_supply_only_their_own_home_and_destinations(self):
        self.viewer.user_permissions.add(Permission.objects.get(content_type__app_label='catalog', codename='view_category'))
        for site in ('warehouse', 'review'):
            with self.subTest(site=site):
                soup = self.soup(reverse(f'{site}:catalog_product_changelist'))
                nav = soup.select_one('.nova-navigation')
                self.assertEqual(nav.select_one('.nova-nav-home')['href'], reverse(f'{site}:index'))
                self.assertTrue(all(a['href'].startswith(f'/{site}/') for a in nav.select('a[href]')))
                self.assertIsNotNone(soup.select_one('[data-nova-command-open]'))

    @override_settings(ROOT_URLCONF="tests.multisite_urls", NOVA_ADMIN_URL_NAMESPACES={
        "warehouse": "warehouse_theme", "review": "review_theme",
    })
    def test_site_level_permission_denial_has_no_palette(self):
        response = self.client.get(reverse('review:login'))
        self.assertEqual(response.status_code, 200)
        self.assert_absent(response)

    def test_native_disabled_and_navigation_opt_out_have_no_palette(self):
        for setting in ({'NOVA_ADMIN_ENABLED': False}, {'NOVA_ADMIN_NAVIGATION': False}):
            with self.subTest(setting=setting), override_settings(**setting):
                response = self.client.get(self.url)
                self.assert_absent(response)
                self.assertContains(response, 'id="nav-filter"')
        session = self.client.session
        session[SESSION_KEY] = 'native'
        session.save()
        self.assert_absent(self.client.get(self.url))

    def test_anonymous_non_staff_and_popup_have_no_palette(self):
        self.assert_absent(self.client.get(reverse('admin:catalog_product_change', args=[self.product.pk]) + '?_popup=1'))
        self.client.logout()
        self.assert_absent(self.client.get(reverse('admin:login')))
        user = get_user_model().objects.create_user(username='command-nonstaff')
        self.client.force_login(user)
        self.assert_absent(self.client.get(reverse('admin:login')))

    def test_empty_permission_navigation_retains_home_without_invented_models(self):
        self.viewer.user_permissions.clear()
        soup = self.soup(reverse('admin:index'))
        self.assertIsNotNone(soup.select_one('[data-nova-command-open]'))
        self.assertIsNotNone(soup.select_one('.nova-nav-home'))
        self.assertFalse(soup.select('.nova-navigation th a'))

    def test_localization_is_server_rendered_for_both_languages(self):
        for lang, label, empty in [('en', 'Search navigation', 'No matching navigation items.'),
                                   ('zh-hans', '搜索导航', '没有匹配的导航项。')]:
            with self.subTest(lang=lang), translation.override(lang):
                soup = self.soup()
                self.assertEqual(soup.select_one('#nova-command-title').get_text(strip=True), label)
                self.assertEqual(soup.select_one('[data-nova-command-empty]').get_text(strip=True), empty)

    def test_deferred_external_assets_retain_csp_nonce_and_script_order(self):
        templates = deepcopy(settings.TEMPLATES)
        templates[0]['OPTIONS']['context_processors'].append('tests.test_command_palette.nonce_context')
        with override_settings(TEMPLATES=templates):
            soup = self.soup()
        scripts = soup.select('script[src]')
        nav = next(i for i, item in enumerate(scripts) if item['src'].endswith('nova_admin/navigation.js'))
        command = next(i for i, item in enumerate(scripts) if item['src'].endswith('nova_admin/command-palette.js'))
        self.assertGreater(command, nav)
        self.assertIn('defer', scripts[command].attrs)
        self.assertEqual(scripts[command]['nonce'], 'command-test-nonce')
        self.assertEqual(soup.select_one('link[href$="nova_admin/command-palette.css"]')['nonce'], 'command-test-nonce')

    def test_shipped_resources_are_discoverable_and_use_no_remote_data_or_storage(self):
        for name in ('command-palette.js', 'command-palette.css'):
            path = finders.find('nova_admin/' + name)
            self.assertTrue(path)
            self.assertTrue(Path(path).is_file())
        source = Path(finders.find('nova_admin/command-palette.js')).read_text()
        for forbidden in ('innerHTML', 'localStorage', 'sessionStorage', 'fetch(', 'XMLHttpRequest'):
            self.assertNotIn(forbidden, source)
