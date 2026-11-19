import json
from datetime import datetime
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from catalog.models import Product
from tests.test_chart_drilldown import ProductDayTestCase
from tests.test_product_csv import ProductCSVAssertions


class LinkedProductChartTests(ProductCSVAssertions, ProductDayTestCase):
    day = "2026-11-01"
    cutoff = "2026-11-01T06:30:00+00:00"
    zone = "America/New_York"

    def dashboard(self, **query):
        response = self.client.get(reverse("admin:index"), query)
        self.assertEqual(response.status_code, 200)
        return BeautifulSoup(response.content, "html.parser")

    def window(self, days=7):
        with timezone.override(ZoneInfo(self.zone)), patch("catalog.charts.datetime", wraps=datetime) as clock:
            clock.now.return_value = datetime.fromisoformat(self.cutoff)
            page = self.dashboard(chart_days=days)
        return {"chart_window": page.select_one('#product-chart-filters [name="chart_window"]')["value"],
                "chart_days": str(days)}

    def result_url(self, page):
        return page.select_one('#product-chart-filters a[href*="activity_day="]')["href"]

    def test_both_directions_match_chart_list_and_csv_through_dst_fallback(self):
        first = self.product("@fold", "2026-11-01T05:30:00+00:00")
        last = self.product("at-cutoff", self.cutoff)
        self.product("previous-date", "2026-11-01T03:59:59+00:00")
        self.product("after-cutoff", "2026-11-01T06:30:00.000001+00:00")
        active = self.product("active", self.cutoff)
        Product.objects.filter(pk=active.pk).update(status="active")
        scoped = self.product("other-tenant", self.cutoff)
        denied = self.product("object-denied", self.cutoff)
        self.product("removed", self.cutoff).delete()
        self.grant_export()
        args = self.window()
        with timezone.override(ZoneInfo("Asia/Tokyo")), patch.object(
            self.owner, "get_queryset", return_value=Product.objects.exclude(pk=scoped.pk)
        ), patch.object(self.owner, "has_view_permission", side_effect=lambda req, obj=None: obj != denied):
            by_day = self.dashboard(**args, chart_day=self.day)
            by_status = self.dashboard(**args, chart_status="draft")
            both = self.dashboard(**args, chart_day=self.day, chart_status="draft")
            daily, status = [json.loads(card.string) for card in both.select(
                '.nova-daily-chart [type="application/json"], .nova-category-chart [type="application/json"]'
            )]
            for snapshot in (daily, status):
                self.assertEqual((snapshot["as_of"], snapshot["timezone"]), (self.cutoff, self.zone))
            self.assertEqual(daily["points"][-2:], [{"date": "2026-10-31", "value": 1}, {"date": self.day, "value": 2}])
            self.assertEqual([point["value"] for point in status["points"]], [2, 1, 0])
            expected = self.result_url(both)
            query = parse_qs(urlsplit(expected).query)
            for link in (by_day.select_one('[data-nova-category="draft"]')["href"],
                         self.link(by_status, self.day, 2),
                         *(a["href"] for a in both.select('a[aria-current="true"][data-nova-category], '
                                                         'a[aria-current="true"][data-nova-chart-day]'))):
                self.assertEqual(parse_qs(urlsplit(link).query), query)
            result = self.listing(expected, [first, last])
            self.assertIsNone(result.context["cl"].formset)
            page = BeautifulSoup(result.content, "html.parser")
            self.assertIn("草稿", page.select_one(".nova-product-day h2").get_text())
            self.assertIn("01:30:00 -0500", page.select_one(".nova-product-day p").get_text())
            restored = self.client.get(page.select_one(".nova-product-day a")["href"])
            restored_html = BeautifulSoup(restored.content, "html.parser")
            self.assertEqual(self.result_url(restored_html), expected)
            self.assertEqual(restored_html.select_one('[name="chart_day"] [selected]')["value"], self.day)
            self.assertEqual(restored_html.select_one('[name="chart_status"] [selected]')["value"], "draft")
            self.assertCountEqual(self.csv_rows(self.download(expected))[1:], [
                ["TEXT: @fold", "TEXT: @fold", "2026-11-01T01:30:00-04:00"],
                [last.sku, last.name, "2026-11-01T01:30:00-05:00"],
            ])
            filtered = expected + "&q=fold&updated_at__date=" + self.day
            form = self.form(self.listing(filtered, [first]))
            rows = self.csv_rows(self.download(urljoin(filtered, form["action"])))
            self.assertEqual(rows, [["SKU", "商品名称", "更新时间 (America/New_York)"],
                                    ["TEXT: @fold", "TEXT: @fold", "2026-11-01T01:30:00-04:00"]])

    def test_empty_combination_export_grants_and_current_object_scope(self):
        args = self.window()
        self.product("denied-later", self.cutoff)
        self.product("also-denied", self.cutoff)
        url = self.result_url(self.dashboard(**args, chart_day=self.day, chart_status="draft"))
        self.assertIsNone(self.form(self.client.get(url)))
        for marker in ("_export_day_csv", "_export_status_csv"):
            denied = self.client.post(url, {marker: "1"})
            self.assertEqual(denied.status_code, 403)
            self.assertNotIn("Content-Disposition", denied)
        self.grant_export()
        with patch.object(self.owner, "get_queryset", return_value=Product.objects.none()):
            empty = self.dashboard(**args, chart_day=self.day, chart_status="draft")
            self.assertIsNone(empty.select_one("a[data-nova-chart-day], a[data-nova-category]"))
            self.assertEqual(self.result_url(empty), url)
            self.assertContains(self.listing(url, []), "当天没有符合当前筛选条件的可见商品")
            self.assertEqual(self.csv_rows(self.download(url)), [["SKU", "商品名称", "更新时间 (America/New_York)"]])
        with patch.object(self.owner, "get_list_display", return_value=["name", "sku", "updated_at"]):
            self.assertEqual(self.download(url).status_code, 403)
            self.assertEqual(self.client.get(reverse("admin:index"), {**args, "chart_status": "draft"}).status_code, 403)
        self.reader.user_permissions.remove(Permission.objects.get(codename="view_product"))
        self.assertEqual(self.download(url).status_code, 403)

    def test_status_across_dates_keeps_old_rows_and_pins_cutoff_and_zone(self):
        old = self.product("old", "2025-01-01T00:00:00+00:00")
        self.product("future", "2026-11-01T06:30:01+00:00")
        self.grant_export()
        args = self.window()
        for selection in ({}, {"chart_status": "draft"}):
            with self.subTest(selection=selection), timezone.override(ZoneInfo("UTC")):
                page = self.dashboard(**args, **selection)
                link = page.select_one('a[data-nova-category="draft"]')
                self.assertEqual(link.find_parent("tr").td.get_text(strip=True), "1")
                url = link["href"]
                self.listing(url, [old])
                response = self.client.post(url, {"_export_status_csv": "1"})
                self.assertEqual(response["Content-Disposition"], 'attachment; filename="products-status-draft.csv"')
                self.assertEqual(self.csv_rows(response), [["SKU", "商品名称", "更新时间 (America/New_York)"],
                                                           ["old", "old", "2024-12-31T19:00:00-05:00"]])
                target = urlsplit(url)
                coordinate = parse_qs(target.query)["activity_day"][0]
                cleared = target.path + "?" + urlencode({"activity_day": coordinate})
                self.listing(cleared, [old])
                self.assertEqual(self.download(cleared).status_code, 404)

    def test_plain_native_status_url_can_still_export_in_current_list_zone(self):
        self.grant_export()
        product = self.product("native", self.cutoff)
        url = reverse("admin:catalog_product_changelist") + "?status__exact=draft"
        with timezone.override(ZoneInfo("UTC")):
            self.listing(url, [product])
            rows = self.csv_rows(self.client.post(url, {"_export_status_csv": "1"}))
        self.assertEqual(rows, [["SKU", "商品名称", "更新时间 (UTC)"], ["native", "native", self.cutoff]])

    def test_clearing_native_date_keeps_status_search_and_signed_window(self):
        self.grant_export()
        today = self.product("match-today", self.cutoff)
        prior = self.product("match-prior", "2026-10-01T12:00:00+00:00")
        self.product("match-late", "2026-11-01T06:30:01+00:00")
        self.product("other-search", self.cutoff)
        active = self.product("match-active", self.cutoff)
        Product.objects.filter(pk=active.pk).update(status="active")
        url = self.result_url(self.dashboard(**self.window(), chart_day=self.day, chart_status="draft"))
        with timezone.override(ZoneInfo("UTC")):
            cl = self.listing(url + "&q=match", [today]).context["cl"]
            choice = next(cl.filter_specs[0].choices(cl))
            all_dates = urljoin(url, choice["query_string"])
            result = self.listing(all_dates, [today, prior])
            self.assertContains(result, self.zone)
            rows = self.csv_rows(self.client.post(all_dates, {"_export_status_csv": "1"}))
            self.assertEqual(rows[0][-1], "更新时间 (America/New_York)")
            self.assertCountEqual([row[0] for row in rows[1:]], [today.sku, prior.sku])

    @override_settings(ROOT_URLCONF="tests.multisite_urls", NOVA_ADMIN_URL_NAMESPACES={})
    def test_another_site_cannot_open_or_export_a_combined_drilldown(self):
        from tests.multisite_urls import warehouse_site, review_site

        self.grant_export()
        self.reader.user_permissions.add(Permission.objects.get(codename="view_category"))
        with patch.object(warehouse_site, "index_template", "project_admin/dashboard.html"), patch.object(
            review_site, "index_template", "project_admin/dashboard.html"
        ):
            page = BeautifulSoup(self.client.get(reverse("warehouse:index")).content, "html.parser")
            token = page.select_one('[name="chart_window"]')["value"]
            date_option = page.select('[name="chart_day"] option')[1]
            query = {"chart_window": token, "chart_day": date_option["value"], "chart_status": "draft"}
            page = self.client.get(reverse("warehouse:index"), query)
            url = self.result_url(BeautifulSoup(page.content, "html.parser"))
            self.assertEqual(self.client.get(reverse("review:index"), query).status_code, 404)
            wrong_site = reverse("review:catalog_product_changelist") + "?" + urlsplit(url).query
            self.assertEqual(self.client.get(wrong_site).status_code, 404)
            response = self.download(wrong_site)
            self.assertEqual(response.status_code, 404)
            self.assertNotIn("Content-Disposition", response)

    def test_invalid_ranges_coordinates_and_cross_account_replay(self):
        args = self.window(30)
        selected = {**args, "chart_day": self.day, "chart_status": "draft"}
        url = self.result_url(self.dashboard(**selected))
        self.grant_export()
        for changes in ({"chart_window": ""}, {"chart_window": "invalid"}, {"chart_status": "unknown"},
                        {"chart_day": [self.day, self.day]}, {"chart_status": ["draft", "active"]}):
            with self.subTest(changes=changes):
                self.assertEqual(self.client.get(reverse("admin:index"), {**selected, **changes}).status_code, 404)
        invalid = self.dashboard(**{**selected, "chart_days": 7, "chart_day": "2026-10-22"})
        self.assertIn("请选择所选范围内的日期", invalid.get_text())
        self.assertIsNone(invalid.select_one('a[href*="activity_day="]'))
        self.assertEqual(self.download(url + "&status__exact=active").status_code, 404)
        other = get_user_model().objects.create_user("other-linked-reader", is_staff=True)
        other.user_permissions.set(self.reader.user_permissions.all())
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse("admin:index"), selected).status_code, 404)
        self.assertEqual(self.download(url).status_code, 404)

    @override_settings(USE_TZ=False, TIME_ZONE="Asia/Shanghai")
    def test_naive_time_uses_the_project_zone_on_all_surfaces(self):
        self.grant_export()
        visible = self.product("midnight", "2026-11-01T00:00:00")
        self.product("late", "2026-11-01T14:30:01")
        page = self.dashboard(**self.window(), chart_day=self.day, chart_status="draft")
        url = self.link(page, self.day, 1)
        self.listing(url, [visible])
        self.assertEqual(self.csv_rows(self.download(url)), [self.headers, ["midnight", "midnight", "2026-11-01T00:00:00"]])
