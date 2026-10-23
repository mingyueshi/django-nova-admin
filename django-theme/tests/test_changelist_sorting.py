"""Follow real Django changelist URLs; no substitute sort implementation."""
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from bs4 import BeautifulSoup
from django.contrib import admin
from django.contrib.admin.templatetags.admin_list import result_headers
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from catalog.models import Product
from nova_admin.preferences import SESSION_KEY


class ChangelistSortingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser('sorting-review', password='test-only')
        for name, price, status in [('丙', 20, 'active'), ('乙', 10, 'active'), ('甲', 30, 'draft'), ('丁', 40, 'draft')]:
            Product.objects.create(name='排序' + name, sku='SORT-' + name, price=price, status=status)

    def setUp(self):
        self.client.force_login(self.user)
        self.url = reverse('admin:catalog_product_changelist')

    def page(self, query=None):
        response = self.client.get(self.url, query or {})
        self.assertEqual(response.status_code, 200)
        return response, BeautifulSoup(response.content, 'html.parser')

    def follow(self, soup, selector):
        return self.page(self.query(soup.select_one(selector)['href']))

    @staticmethod
    def query(url):
        return parse_qs(urlsplit(url).query, keep_blank_values=True)

    @staticmethod
    def prices(response):
        return [int(row.price) for row in response.context['cl'].result_list]

    def test_price_header_and_direction_toggle_follow_native_links(self):
        _, soup = self.page()
        response, soup = self.follow(soup, '.column-price .text a')
        self.assertEqual(self.prices(response), [10, 20, 30, 40])
        self.assertIn('ascending', soup.select_one('.column-price')['class'])
        response, soup = self.follow(soup, '.column-price .toggle')
        self.assertEqual(self.prices(response), [40, 30, 20, 10])
        self.assertIn('descending', soup.select_one('.column-price')['class'])

    def test_custom_ordering_and_secondary_toggle_keep_priorities(self):
        response, soup = self.page({'o': '6.-4'})
        self.assertEqual(self.prices(response), [20, 10, 40, 30])
        self.assertEqual(soup.select_one('.column-status_badge .sortpriority').text, '1')
        self.assertEqual(soup.select_one('.column-price .sortpriority').text, '2')
        response, soup = self.follow(soup, '.column-price .toggle')
        self.assertEqual(response.context['cl'].params['o'], '6.4')
        self.assertEqual(self.prices(response), [10, 20, 30, 40])
        response, soup = self.follow(soup, '.column-price .text a')
        self.assertEqual(response.context['cl'].params['o'], '-4.6')
        self.assertEqual(self.prices(response), [40, 30, 20, 10])

    def test_remove_primary_secondary_and_last_sort(self):
        _, soup = self.page({'o': '6.-4'})
        response, _ = self.follow(soup, '.column-price .sortremove')
        self.assertEqual(response.context['cl'].params['o'], '6')
        _, soup = self.page({'o': '6.-4'})
        response, soup = self.follow(soup, '.column-status_badge .sortremove')
        self.assertEqual(response.context['cl'].params['o'], '-4')
        self.assertEqual(self.prices(response), [40, 30, 20, 10])
        response, soup = self.follow(soup, '.column-price .sortremove')
        self.assertEqual(response.context['cl'].params['o'], '')
        self.assertFalse(soup.select('#result_list th.sorted'))
        self.assertEqual(response.context['cl'].result_count, 4)

    def test_links_match_upstream_and_keep_query_values_in_all_skins(self):
        for mode in ('light', 'dark', 'native'):
            with self.subTest(mode=mode):
                session = self.client.session
                session[SESSION_KEY] = mode
                session.save()
                response, soup = self.page({'o': '6.-4', 'q': '排序', 'price__gte': ['0', '1'],
                                            'status__exact': 'active', '_nova_page_size': '10', '_facets': '1'})
                headers = list(result_headers(response.context['cl']))
                cells = soup.select('#result_list thead th')
                self.assertEqual(len(headers), len(cells))
                for expected, cell in zip(headers, cells):
                    if not expected['sortable']:
                        self.assertIsNone(cell.select_one('.text a'))
                        self.assertIsNone(cell.select_one('.sortoptions'))
                        continue
                    for key, selector in [('url_primary', '.text a'), ('url_toggle', '.toggle'), ('url_remove', '.sortremove')]:
                        link = cell.select_one(selector)
                        if link:
                            self.assertEqual(link['href'], expected[key])
                            query = self.query(link['href'])
                            for name in ('q', 'price__gte', 'status__exact', '_nova_page_size', '_facets'):
                                self.assertEqual(query[name], response.context['cl'].filter_params[name])
                            followed = self.client.get(self.url + link['href'])
                            self.assertEqual(followed.status_code, 200)
                            self.assertEqual(followed.context['cl'].result_count, 2)
                self.assertEqual(bool(soup.select('script[src$="nova_admin/enhancements.js"]')), mode != 'native')

    def test_non_sortable_image_and_checkbox_have_no_sort_controls(self):
        _, soup = self.page()
        for selector in ('.column-image_thumbnail', '.action-checkbox-column'):
            header = soup.select_one(selector)
            self.assertNotIn('sortable', header['class'])
            self.assertIsNone(header.select_one('a'))
        self.assertIsNotNone(soup.select_one('.column-status_badge.sortable .text a'))

    def test_host_sortable_by_is_respected(self):
        model_admin = admin.site._registry[Product]
        with patch.object(model_admin, 'sortable_by', ('name', 'status_badge')):
            _, soup = self.page()
        self.assertIsNone(soup.select_one('.column-price .text a'))
        self.assertIsNotNone(soup.select_one('.column-status_badge.sortable .text a'))

    @override_settings(NOVA_ADMIN_ENABLED=False)
    def test_theme_disabled_does_not_load_enhancement(self):
        _, soup = self.page({'o': '4'})
        self.assertFalse(soup.select('script[src$="nova_admin/enhancements.js"]'))
        self.assertIsNotNone(soup.select_one('.column-price .toggle'))
