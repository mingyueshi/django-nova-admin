from datetime import datetime
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlsplit
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.template.loader import render_to_string
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from catalog.models import Product


class ProductDayTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.reader = get_user_model().objects.create_user("day-reader", is_staff=True)
        cls.reader.user_permissions.add(Permission.objects.get(codename="view_product"))

    def setUp(self):
        self.client.force_login(self.reader)
        self.owner = admin.site.get_model_admin(Product)

    def product(self, sku, stamp):
        product = Product.objects.create(sku=sku, name=sku, price=1)
        Product.objects.filter(pk=product.pk).update(updated_at=datetime.fromisoformat(stamp))
        return product

    def chart(self, now="2026-11-19T01:30:00+00:00", zone="Asia/Shanghai", days=7, site="admin"):
        with timezone.override(ZoneInfo(zone)), patch("catalog.charts.datetime", wraps=datetime) as clock:
            clock.now.return_value = datetime.fromisoformat(now)
            result = self.client.get(reverse(f"{site}:index"), {"chart_days": days})
        self.assertEqual(result.status_code, 200)
        return BeautifulSoup(result.content, "html.parser").select_one(".nova-daily-chart")

    def link(self, card, day, count):
        anchor = card.select_one(f'a[data-nova-chart-day="{day}"]')
        self.assertIsNotNone(anchor)
        self.assertIn(day, anchor["aria-label"])
        self.assertEqual(anchor.find_parent("tr").td.get_text(strip=True), str(count))
        return anchor["href"]

    def listing(self, url, products):
        result = self.client.get(url)
        self.assertEqual(result.status_code, 200)
        cl = result.context["cl"]
        self.assertEqual(cl.result_count, len(products))
        self.assertCountEqual([row.pk for row in cl.result_list], [p.pk for p in products])
        return result


class ProductDayDrilldownTests(ProductDayTestCase):
    def test_snapshot_cutoff_timezone_and_readonly_native_list(self):
        self.product("before", "2026-11-18T15:59:59+00:00")
        midnight = self.product("midnight", "2026-11-18T16:00:00+00:00")
        latest = self.product("at-cutoff", "2026-11-19T01:30:00+00:00")
        url = self.link(self.chart(days=30), "2026-11-19", 2)
        self.product("after-cutoff", "2026-11-19T01:30:00.000001+00:00")
        with timezone.override(ZoneInfo("America/New_York")):
            response = self.listing(url, [midnight, latest])
        page = BeautifulSoup(response.content, "html.parser")
        day = page.select_one(".nova-product-day")
        self.assertIn("2026-11-19", day.h2.get_text())
        self.assertIn("Asia/Shanghai", day.p.get_text())
        self.assertIn("2026-11-19 09:30:00 +0800", day.p.get_text())
        self.assertEqual(day.a["href"], reverse("admin:index") + "?chart_days=30#product-activity-range")
        self.assertIn("0:00", page.select(".field-updated_at")[-1].get_text())
        self.assertIsNone(response.context["cl"].formset)
        self.assertIsNone(page.select_one('[name="_save"]'))
        self.assertEqual(self.client.post(url, {"_save": "1"}).status_code, 403)

    def test_dst_short_and_long_days_include_both_local_boundaries(self):
        for day, first, last, following in [
            ("2026-03-08", "2026-03-08T05:00:00", "2026-03-09T03:59:59", "2026-03-09T04:00:00"),
            ("2026-11-01", "2026-11-01T04:00:00", "2026-11-02T04:59:59", "2026-11-02T05:00:00"),
        ]:
            with self.subTest(day=day):
                a = self.product(day + "a", first + "+00:00")
                b = self.product(day + "b", last + "+00:00")
                self.product(day + "c", following + "+00:00")
                card = self.chart(now=following + "+00:00", zone="America/New_York")
                self.listing(self.link(card, day, 2), [a, b])

    @override_settings(USE_TZ=False, TIME_ZONE="Asia/Shanghai")
    def test_naive_storage_uses_project_midnight_and_cutoff(self):
        first = self.product("first", "2026-11-19T00:00:00")
        self.product("late", "2026-11-19T09:30:01")
        url = self.link(self.chart(zone="America/New_York"), "2026-11-19", 1)
        response = self.listing(url, [first])
        self.assertContains(response, "2026-11-19 09:30:00 +0800")

    def test_zero_day_empty_range_and_permissions_on_second_request(self):
        self.assertIsNone(self.chart().select_one("[data-nova-chart-day]"))
        a = self.product("shown", "2026-11-19T01:00:00+00:00")
        self.product("hidden", "2026-11-19T01:00:00+00:00")
        with patch.object(self.owner, "get_queryset", return_value=Product.objects.filter(pk=a.pk)):
            card = self.chart()
            url = self.link(card, "2026-11-19", 1)
            self.listing(url, [a])
            response = self.listing(self.link(card, "2026-11-18", 0), [])
            self.assertContains(response, "当天没有符合当前筛选条件的可见商品")
        with patch.object(self.owner, "get_queryset", return_value=Product.objects.none()):
            self.listing(url, [])
        with patch.object(self.owner, "get_list_display", return_value=["name"]):
            self.assertEqual(self.client.get(url).status_code, 403)
        with patch.object(self.owner, "has_module_permission", return_value=False):
            self.assertEqual(self.client.get(url).status_code, 403)
        self.reader.user_permissions.clear()
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_card_without_target_filter_preserves_values_and_omits_links(self):
        self.product("visible", "2026-11-19T01:00:00+00:00")
        with patch.object(self.owner, "get_list_filter", return_value=["status"]):
            card = self.chart()
        self.assertTrue(card.table)
        self.assertIsNone(card.table.a)
        self.assertNotIn("商品明细", card.summary.get_text())

    def test_keyboard_table_links_observed_zero_and_skips_missing_day(self):
        snapshot = {
            "schema_version": 1, "metric": "catalog.products_last_updated", "as_of": "2026-11-19T01:30:00Z",
            "timezone": "Asia/Shanghai", "start": "2026-11-18", "end": "2026-11-20", "state": "ready",
            "points": [{"date": "2026-11-18", "value": None}, {"date": "2026-11-19", "value": 0}],
        }
        html = render_to_string("project_admin/product_activity_chart.html", {
            "chart_snapshot": snapshot, "activity": {"window": "sample", "list_url": "/admin/catalog/product/"},
        })
        details = BeautifulSoup(html, "html.parser").details
        self.assertTrue(details.has_attr("open"))
        self.assertTrue(details.find("summary", recursive=False))
        rows = details.select("tbody tr")
        self.assertIsNone(rows[0].a)
        anchor = rows[1].a
        self.assertEqual(anchor["data-nova-chart-day"], "2026-11-19")
        self.assertTrue(anchor["href"])
        for target in (details.summary, anchor):
            self.assertEqual(target.get("tabindex", "0"), "0")
            self.assertIsNone(target.find_parent(attrs={"hidden": True}))
            self.assertIsNone(target.find_parent(attrs={"inert": True}))
            self.assertIsNone(target.find_parent(attrs={"aria-hidden": "true"}))

    def test_duplicate_invalid_and_out_of_window_coordinates_are_rejected(self):
        self.product("visible", "2026-11-19T01:00:00+00:00")
        url = self.link(self.chart(), "2026-11-19", 1)
        path, query = url.split("?")
        value = parse_qs(query)["activity_day"][0]
        token = value.split("~")[1]
        for values in ([value, value], [""], ["2026-11-12~" + token], ["2026-11-20~" + token],
                       ["2026-11-19~" + token + "x"], ["2026-02-30~" + token], ["20261119~" + token]):
            with self.subTest(values=values):
                self.assertEqual(self.client.get(path, {"activity_day": values}).status_code, 404)

    @override_settings(ROOT_URLCONF="tests.multisite_urls", NOVA_ADMIN_URL_NAMESPACES={})
    def test_same_account_and_site_are_required(self):
        from tests.multisite_urls import warehouse_site

        a = self.product("warehouse", "2026-11-19T01:00:00+00:00")
        self.reader.user_permissions.add(Permission.objects.get(codename="view_category"))
        with patch.object(warehouse_site, "index_template", "project_admin/dashboard.html"):
            url = self.link(self.chart(site="warehouse"), "2026-11-19", 1)
        self.assertEqual(urlsplit(url).path, reverse("warehouse:catalog_product_changelist"))
        self.listing(url, [a])
        self.assertEqual(self.client.get(url.replace("/warehouse/", "/review/")).status_code, 404)
        other = get_user_model().objects.create_user("other-reader", is_staff=True)
        other.user_permissions.add(Permission.objects.get(codename="view_product"))
        self.client.force_login(other)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_inline_stock_save_on_second_page_of_signed_day(self):
        self.reader.user_permissions.add(Permission.objects.get(codename="change_product"))
        for index in range(11):
            self.product(f"day-{index:02}", "2026-11-18T16:05:00+00:00")
        outside = self.product("previous-day", "2026-11-18T15:59:59+00:00")
        day_url = self.link(self.chart(), "2026-11-19", 11)
        page_url = day_url + "&updated_at__date=2026-11-19&_nova_page_size=10&p=2"
        with timezone.override(ZoneInfo("UTC")):
            formset = self.client.get(page_url).context["cl"].formset
            form, = formset.forms
            data = {field.html_name: field.value() for field in formset.management_form}
            data.update({"_save": "Save", form["id"].html_name: form.instance.pk, form["stock"].html_name: "12"})
            response = self.client.post(page_url, data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, page_url)
        self.assertEqual(list(Product.objects.filter(stock=12).values_list("pk", flat=True)), [form.instance.pk])
        outside.refresh_from_db()
        self.assertEqual(outside.stock, 0)

    def test_native_pagination_search_and_edit_permissions_preserve_day_filter(self):
        products = [self.product(f"day-{i:02}", "2026-11-19T01:00:00+00:00") for i in range(11)]
        self.product("other-day", "2026-11-18T01:00:00+00:00")
        self.reader.user_permissions.add(Permission.objects.get(codename="change_product"))
        url = self.link(self.chart(), "2026-11-19", 11)
        page = self.client.get(url + "&_nova_page_size=10&p=2")
        self.assertEqual(page.context["cl"].result_count, 11)
        self.assertEqual(len(page.context["cl"].result_list), 1)
        self.assertIsNotNone(page.context["cl"].formset)
        self.listing(url + "&" + urlencode({"q": "day-01"}), [products[1]])
        self.listing(url + "&q=other-day", [])
