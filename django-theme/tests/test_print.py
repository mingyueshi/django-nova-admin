"""Print enhancement follows the real changelist permission and pagination flow."""
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
    return {'csp_nonce': 'print-test-nonce'}


@override_settings(NOVA_ADMIN_ENABLED=True)
class PrintMarkupTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.viewer = get_user_model().objects.create_user(username='print-viewer', is_staff=True)
        cls.viewer.user_permissions.add(Permission.objects.get(content_type__app_label='catalog', codename='view_product'))
        Product.objects.bulk_create([Product(name=f'PUBLIC-{i:03}', sku=f'PUBLIC-{i:03}', price=1, stock=1) for i in range(1, 26)])

    def setUp(self):
        self.client.force_login(self.viewer)
        self.url = reverse('admin:catalog_product_changelist')

    def page(self, url=None, query=None):
        response = self.client.get(url or self.url, query or {})
        self.assertEqual(response.status_code, 200)
        return response, BeautifulSoup(response.content, 'html.parser')

    def assert_absent(self, response):
        self.assertNotContains(response, 'data-nova-print-tool')
        self.assertNotContains(response, 'nova_admin/print.js')
        self.assertNotContains(response, 'nova_admin/print.css')

    def test_readonly_staff_gets_hidden_non_submit_tool_outside_forms(self):
        _, soup = self.page()
        tool = soup.select_one('[data-nova-print-tool][hidden]')
        button = tool.select_one('button[data-nova-print]')
        self.assertEqual(button['type'], 'button')
        self.assertIn('hidden', button.attrs)
        self.assertIsNone(button.find_parent('form'))
        self.assertFalse(button.has_attr('form'))
        self.assertEqual(button['data-editable'], '')
        self.assertFalse(soup.select('.nova-print-sheet'))
        self.assertTrue(soup.select('form#changelist-form input[name=csrfmiddlewaretoken]'))
        self.assertNotIn(reverse('admin:catalog_product_add'), str(soup.select('.object-tools')))

    def test_editable_table_has_unsaved_notice_and_original_csrf_form(self):
        self.viewer.user_permissions.add(Permission.objects.get(content_type__app_label='catalog', codename='change_product'))
        _, soup = self.page()
        self.assertEqual(soup.select_one('[data-nova-print]')['data-editable'], 'true')
        self.assertTrue(soup.select_one('[data-nova-print]')['data-unsaved'])
        self.assertIsNotNone(soup.select_one('#changelist-form input[name="form-TOTAL_FORMS"]'))
        self.assertIsNotNone(soup.select_one('#changelist-form input[name="_save"]'))

    @override_settings(ROOT_URLCONF='tests.pagination_urls')
    def test_current_page_is_original_scoped_filtered_sorted_result_only(self):
        Product.objects.create(name='Hidden private product', sku='PRIVATE-001', price=1, stock=1)
        response, soup = self.page(reverse('pagination_test:catalog_product_changelist'), {'p':2, '_nova_page_size':10, 'o':'2'})
        cl = response.context['cl']
        self.assertEqual(cl.page_num, 2)
        self.assertEqual(len(cl.result_list), 10)
        self.assertEqual(list(cl.result_list.values_list('sku',flat=True)), [f'PUBLIC-{i:03}' for i in range(11,21)])
        self.assertEqual(soup.select_one('[data-nova-print]')['data-page'], '2')
        self.assertNotIn('PRIVATE-001', soup.select_one('#result_list').get_text())
        self.assertEqual(len(soup.select('#result_list tbody tr')), 10)

    @override_settings(ROOT_URLCONF='tests.multisite_urls', NOVA_ADMIN_URL_NAMESPACES={'warehouse':'warehouse_theme','review':'review_theme'})
    def test_multiple_adminsites_keep_current_site_urls_and_permissions(self):
        for site in ('warehouse','review'):
            if site == 'review':
                response = self.client.get(reverse('review:login'))
                self.assert_absent(response)
                self.viewer.user_permissions.add(Permission.objects.get(content_type__app_label='catalog', codename='view_category'))
            _, soup = self.page(reverse(f'{site}:catalog_product_changelist'))
            self.assertIsNotNone(soup.select_one('[data-nova-print]'))
            self.assertTrue(all(a['href'].startswith(f'/{site}/') for a in soup.select('#result_list tbody th a')))

    def test_native_and_global_disable_omit_print_assets_and_tool(self):
        with override_settings(NOVA_ADMIN_ENABLED=False):
            self.assert_absent(self.page()[0])
        session=self.client.session;session[SESSION_KEY]='native';session.save()
        self.assert_absent(self.page()[0])

    def test_popup_anonymous_and_non_list_have_no_print_tool(self):
        self.assert_absent(self.page(query={'_popup':'1'})[0])
        self.assert_absent(self.page(reverse('admin:index'))[0])
        product=Product.objects.first()
        self.assert_absent(self.page(reverse('admin:catalog_product_change',args=[product.pk]))[0])
        self.client.logout()
        self.assert_absent(self.page(reverse('admin:login'))[0])

    def test_empty_list_retains_hidden_print_tool_without_invented_rows(self):
        _, soup = self.page(query={'q':'NO_MATCH_AT_ALL'})
        self.assertIsNotNone(soup.select_one('[data-nova-print-tool][hidden]'))
        self.assertIsNone(soup.select_one('#result_list'))
        self.assertTrue(soup.select_one('[data-nova-print]')['data-empty'])

    def test_localized_labels_and_scope(self):
        for language, label, scope in [('en','Print current page','Other pages are not included.'),('zh-hans','打印当前页','不包含其他页面')]:
            with self.subTest(language=language), translation.override(language):
                _, soup = self.page()
                button = soup.select_one('[data-nova-print]')
                self.assertEqual(button.get_text(strip=True),label)
                self.assertIn(scope, button['data-scope'])

    def test_assets_discoverable_deferred_and_nonce_preserved(self):
        templates=deepcopy(settings.TEMPLATES)
        templates[0]['OPTIONS']['context_processors'].append('tests.test_print.nonce_context')
        with override_settings(TEMPLATES=templates):
            _, soup = self.page()
        script=soup.select_one('script[src$="nova_admin/print.js"]')
        self.assertEqual(script['nonce'],'print-test-nonce')
        self.assertIn('defer',script.attrs)
        self.assertEqual(soup.select_one('link[href$="nova_admin/print.css"]')['nonce'],'print-test-nonce')
        for name in ('print.js','print.css'):
            self.assertTrue(Path(finders.find('nova_admin/'+name)).is_file())

    def test_navigation_optout_does_not_disable_independent_print_tool(self):
        with override_settings(NOVA_ADMIN_NAVIGATION=False):
            _,soup=self.page()
        self.assertIsNotNone(soup.select_one('[data-nova-print]'))
        self.assertIsNone(soup.select_one('.nova-navigation'))
