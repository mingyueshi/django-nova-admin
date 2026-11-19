import json
from datetime import date, datetime
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import DatabaseError
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from catalog.models import Product
from catalog.product_csv import MAX_EXPORT_ROWS
from tests.test_chart_drilldown import ProductDayTestCase
from tests.test_product_csv import ProductCSVAssertions


class ProductAnalysisTests(ProductCSVAssertions, ProductDayTestCase):
    export_action = "_export_csv"
    day = "2026-11-01"
    cutoff = "2026-11-01T06:30:00+00:00"
    zone = "America/New_York"

    def entry(self, site="admin"):
        with timezone.override(ZoneInfo(self.zone)), patch("catalog.charts.datetime", wraps=datetime) as clock:
            clock.now.return_value = datetime.fromisoformat(self.cutoff)
            response = self.client.get(reverse(f"{site}:index"), {"chart_days": 30})
        page = BeautifulSoup(response.content, "html.parser")
        return page.find("a", string="联动分析工作台")["href"]

    def open_page(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        return BeautifulSoup(response.content, "html.parser")

    def chart_link(self, page, current, selector):
        target = urljoin(current, page.select_one(selector)["href"])
        self.assertEqual(urlsplit(target).path, urlsplit(current).path)
        return target

    def test_home_selection_both_chart_directions_details_and_download_through_dst_fold(self):
        self.grant_export()
        first = self.product("@first", "2026-11-01T05:30:00+00:00")
        last = self.product("last", self.cutoff)
        active = self.product("active", self.cutoff)
        Product.objects.filter(pk=active.pk).update(status="active")
        self.product("yesterday", "2026-11-01T03:59:59+00:00")
        self.product("too-late", "2026-11-01T06:30:00.000001+00:00")
        scoped = self.product("other-tenant", self.cutoff)
        denied = self.product("object-denied", self.cutoff)
        self.product("deleted", self.cutoff).delete()
        entry = self.entry()
        with timezone.override(ZoneInfo("Asia/Tokyo")), patch.object(
            self.owner, "get_queryset", return_value=Product.objects.exclude(pk=scoped.pk)
        ), patch.object(self.owner, "has_view_permission", side_effect=lambda request, obj=None: obj != denied):
            home_query = parse_qs(urlsplit(entry).query)
            home_query.update(chart_day=self.day, chart_status="draft")
            home = self.open_page(reverse("admin:index") + "?" + urlencode(home_query, doseq=True))
            selected = home.find("a", string="联动分析工作台")["href"]
            start = self.open_page(entry)
            for first_selector, second_selector in (
                ('a[data-nova-chart-day="2026-11-01"]', 'a[data-nova-category="draft"]'),
                ('a[data-nova-category="draft"]', 'a[data-nova-chart-day="2026-11-01"]'),
            ):
                one = self.chart_link(start, entry, first_selector)
                both = self.chart_link(self.open_page(one), one, second_selector)
                self.assertEqual(parse_qs(urlsplit(both).query), parse_qs(urlsplit(selected).query))
            page = self.open_page(selected)
            snapshots = [json.loads(node.string) for node in page.select('.product-analysis-charts [type="application/json"]')]
            daily, status = snapshots
            self.assertTrue(all((s["as_of"], s["timezone"]) == (self.cutoff, self.zone) for s in snapshots))
            self.assertEqual(daily["points"][-1]["value"], 2)
            self.assertEqual({p["key"]: p["value"] for p in status["points"]}, {"draft": 2, "active": 1, "archived": 0})
            detail = page.select_one("#product-details")
            self.assertIn("01:30:00 -0500", detail.p.get_text())
            self.assertEqual([a.string for a in detail.select("tbody th a")], [last.name, first.name])
            self.assertEqual([a["datetime"] for a in detail.select("time")],
                             ["2026-11-01T01:30:00-05:00", "2026-11-01T01:30:00-04:00"])
            self.assertIsNone(detail.select_one('input[name$="stock"], [name="_save"]'))
            target = urljoin(selected, detail.form["action"])
            self.assertEqual(self.csv_rows(self.download(target)), [
                ["SKU", "商品名称", "更新时间 (America/New_York)"],
                ["last", "last", "2026-11-01T01:30:00-05:00"],
                ["TEXT: @first", "TEXT: @first", "2026-11-01T01:30:00-04:00"],
            ])

    def test_empty_detail_and_header_only_csv_after_scope_narrows(self):
        self.grant_export()
        self.product("initially-visible", self.cutoff)
        url = self.entry() + "&chart_status=draft&chart_day=" + self.day
        page = self.open_page(url)
        target = urljoin(url, page.select_one("#product-details form")["action"])
        with patch.object(self.owner, "has_view_permission", side_effect=lambda request, obj=None: obj is None):
            page = self.open_page(url)
            self.assertIn("当前筛选条件下没有可查看的商品", page.select_one("#product-details").get_text())
            self.assertIsNone(page.select_one('#product-details tbody tr, .product-analysis-charts [type="application/json"]'))
            self.assertEqual(self.csv_rows(self.download(target)), [["SKU", "商品名称", "更新时间 (America/New_York)"]])

    def test_readonly_export_grant_visible_columns_and_denied_model(self):
        item = self.product("private-sku", self.cutoff)
        Product.objects.filter(pk=item.pk).update(name="普通名称")
        url = self.entry()
        self.assertIsNone(self.open_page(url).select_one('#product-details form'))
        self.assertEqual(self.download(url).status_code, 403)
        self.grant_export()
        grant = Permission.objects.get(codename="export_product")
        self.assertIsNotNone(self.open_page(url).select_one('#product-details form'))
        self.reader.user_permissions.remove(grant)
        self.assertEqual(self.download(url).status_code, 403)
        self.grant_export()
        with patch.object(self.owner, "get_list_display", return_value=["name", "status_badge", "updated_at"]):
            page = self.open_page(url)
            self.assertNotIn(item.sku, page.select_one("#product-details").get_text())
            self.assertIsNone(page.select_one('#product-details form'))
            self.assertEqual(self.download(url).status_code, 403)
        with patch.object(self.owner, "get_list_display", return_value=["name", "sku", "updated_at"]):
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.download(url).status_code, 403)
        self.reader.user_permissions.remove(Permission.objects.get(codename="view_product"))
        for response in (self.client.get(url), self.download(url)):
            self.assertEqual(response.status_code, 403)
            self.assertNotIn("Content-Disposition", response)

    def test_unfiltered_pagination_and_export_cap_apply_to_all_matching_pages(self):
        self.grant_export()
        old = datetime.fromisoformat("2025-01-01T00:00:00+00:00")
        Product.objects.bulk_create([Product(sku=f"W{i:04}", name="可见商品", price=1)
                                     for i in range(MAX_EXPORT_ROWS + 1)])
        Product.objects.update(updated_at=old)
        url = self.entry()
        first = self.open_page(url)
        self.assertEqual(len(first.select('#product-details tbody tr')), self.owner.list_per_page)
        next_url = self.chart_link(first, url, '#product-details a[rel="next"]')
        page = self.open_page(next_url)
        self.assertNotEqual(first.select_one("#product-details tbody a")["href"],
                            page.select_one("#product-details tbody a")["href"])
        details = page.select_one("#product-details")
        self.assertIn("1000", details.get_text().replace(",", "").replace("\xa0", ""))
        self.assertIsNone(details.form)
        too_many = self.download(next_url)
        self.assertEqual(too_many.status_code, 400)
        self.assertNotIn("Content-Disposition", too_many)
        Product.objects.filter(sku="W0000").delete()
        current = urljoin(next_url, self.open_page(next_url).select_one("#product-details form")["action"])
        self.assertNotIn("page", parse_qs(urlsplit(current).query))
        rows = self.csv_rows(self.download(current))
        self.assertEqual([r[0] for r in rows[1:]], [f"W{i:04}" for i in range(MAX_EXPORT_ROWS, 0, -1)])

    def test_invalid_or_unsigned_export_cannot_fall_back_to_all_products(self):
        self.grant_export()
        entry = self.entry()
        base = urlsplit(entry).path
        for url in (base, base + "?chart_window=bad", entry + "&chart_status=other",
                    entry + "&chart_days=7", entry + "&chart_day=2001-01-01", entry + "&status__exact=active"):
            with self.subTest(url=url):
                response = self.download(url)
                self.assertEqual(response.status_code, 404)
                self.assertNotIn("Content-Disposition", response)
        bad = self.client.get(entry + "&chart_day=2001-01-01")
        self.assertEqual(bad.status_code, 400)
        self.assertNotContains(bad, 'name="_export_csv"', status_code=400)
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.reader)
        self.assertEqual(self.download(entry).status_code, 403)
        form = self.open_page(entry).select_one("#product-details form")
        token = form.select_one('input[name="csrfmiddlewaretoken"]')["value"]
        self.assertEqual(self.download(entry, csrfmiddlewaretoken=token).status_code, 200)

    @override_settings(ROOT_URLCONF="tests.multisite_urls", NOVA_ADMIN_URL_NAMESPACES={})
    def test_site_and_account_bound_window_and_export(self):
        from tests.multisite_urls import warehouse_site

        self.grant_export()
        self.reader.user_permissions.add(Permission.objects.get(codename="view_category"))
        with patch.object(warehouse_site, "index_template", "project_admin/dashboard.html"):
            url = self.entry(site="warehouse")
        self.assertEqual(urlsplit(url).path, reverse("warehouse:catalog_product_analysis"))
        self.assertEqual(self.download(url).status_code, 200)
        wrong_site = reverse("review:catalog_product_analysis") + "?" + urlsplit(url).query
        self.assertEqual(self.download(wrong_site).status_code, 404)
        other = get_user_model().objects.create_user("other-analyst", is_staff=True)
        other.user_permissions.set(self.reader.user_permissions.all())
        self.client.force_login(other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.download(url).status_code, 404)

    @override_settings(USE_TZ=False, TIME_ZONE="Asia/Shanghai")
    def test_naive_storage_uses_project_zone_even_when_request_zone_changes(self):
        self.grant_export()
        self.product("midnight", "2026-11-01T00:00:00")
        self.product("too-late", "2026-11-01T14:30:01")
        url = self.entry() + "&chart_day=" + self.day
        with timezone.override(ZoneInfo("UTC")):
            page = self.open_page(url)
            self.assertEqual(page.select_one("#product-details time")["datetime"], "2026-11-01T00:00:00")
            self.assertEqual(self.csv_rows(self.download(url)), [self.headers, ["midnight", "midnight", "2026-11-01T00:00:00"]])

    def test_data_failure_has_no_export_or_empty_success_message(self):
        self.grant_export()
        url = self.entry()
        with patch("catalog.charts.visible_products", side_effect=DatabaseError):
            result = self.client.get(url)
            self.assertContains(result, "商品明细暂时不可用", status_code=503)
            self.assertNotContains(result, 'name="_export_csv"', status_code=503)
            result = self.download(url)
            self.assertEqual(result.status_code, 503)
            self.assertNotIn("Content-Disposition", result)

    def test_host_date_lookup_and_object_checks_use_observed_zone(self):
        self.grant_export()
        visible = self.product("local-october-31", "2026-11-01T03:30:00+00:00")
        self.product("local-october-30", "2026-10-31T03:30:00+00:00")
        url = self.entry() + "&chart_status=draft"
        scope = Product.objects.filter(updated_at__date=date(2026, 10, 31))
        with timezone.override(ZoneInfo("Asia/Tokyo")), patch.object(self.owner, "get_queryset", return_value=scope), patch.object(
            self.owner, "has_view_permission", side_effect=lambda req, obj=None: obj is None or timezone.get_current_timezone_name() == self.zone
        ):
            page = self.open_page(url)
            self.assertEqual([a.string for a in page.select("#product-details tbody a")], [visible.name])
            self.assertEqual(page.select_one('a[data-nova-category="draft"]').find_parent("tr").td.string, "1")
            self.assertEqual(page.select_one('a[data-nova-chart-day="2026-10-31"]').find_parent("tr").td.string, "1")
            self.assertEqual([r[0] for r in self.csv_rows(self.download(url))[1:]], [visible.sku])
