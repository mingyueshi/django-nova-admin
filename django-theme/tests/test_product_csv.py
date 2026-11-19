import codecs
import csv
from datetime import datetime
from io import StringIO
from unittest.mock import patch
from urllib.parse import parse_qs, urljoin, urlsplit
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, SimpleTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from catalog.models import Product
from catalog.product_csv import MAX_EXPORT_ROWS, spreadsheet_text
from tests.test_chart_drilldown import ProductDayTestCase


class SpreadsheetTextTests(SimpleTestCase):
    def test_formula_and_control_prefixes_are_written_as_visible_text(self):
        for value in ("=1", "+2", "-3", "@name", "  =1", "\tplain", "\rplain", "\nplain",
                      "\u200b\ufeff ＝1", "\x00+2", "－3", "＠name", "＋2", "'=1"):
            with self.subTest(value=value):
                self.assertEqual(spreadsheet_text(value), "TEXT: " + value)
        for value in ("", "  商品", '引号",逗号;分号\n换行', "A-1", "O'Brian"):
            self.assertEqual(spreadsheet_text(value), value)


class ProductCSVAssertions:
    export_action = "_export_day_csv"
    stamp = "2026-11-19T01:00:00+00:00"
    headers = ["SKU", "商品名称", "更新时间 (Asia/Shanghai)"]

    def grant_export(self):
        self.reader.user_permissions.add(Permission.objects.get(codename="export_product", content_type__app_label="catalog"))

    def form(self, result):
        button = BeautifulSoup(result.content, "html.parser").select_one(f'button[name="{self.export_action}"]')
        return button.find_parent("form") if button else None

    def download(self, url, **post):
        return self.client.post(url, {self.export_action: "1", **post})

    def csv_rows(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertTrue(response.content.startswith(codecs.BOM_UTF8))
        self.assertIn("no-store", response["Cache-Control"])
        return list(csv.reader(StringIO(response.content.decode("utf-8-sig"), newline=""), strict=True))


class ProductDayCSVTests(ProductCSVAssertions, ProductDayTestCase):
    def test_view_change_and_export_grants_are_independent_and_rechecked(self):
        self.product("visible", self.stamp)
        url = self.link(self.chart(), "2026-11-19", 1)
        for editing in (False, True):
            if editing:
                self.reader.user_permissions.add(Permission.objects.get(codename="change_product"))
            self.assertIsNone(self.form(self.client.get(url)))
            self.assertEqual(self.download(url).status_code, 403)
        self.reader.user_permissions.clear()
        self.grant_export()
        self.assertEqual(self.download(url).status_code, 403)
        self.reader.user_permissions.add(Permission.objects.get(codename="view_product"))
        listing = self.client.get(url)
        self.assertIsNotNone(self.form(listing))
        self.assertIsNone(listing.context["cl"].formset)
        self.assertEqual(self.csv_rows(self.download(url))[1][0], "visible")
        self.reader.user_permissions.remove(Permission.objects.get(codename="export_product"))
        self.assertEqual(self.download(url).status_code, 403)

    def test_search_filters_sort_and_all_pages_match_the_native_list(self):
        self.grant_export()
        for i in range(12):
            self.product(f"match-{i:02}", self.stamp)
        Product.objects.exclude(sku="match-11").update(status=Product.Status.ACTIVE)
        self.product("unrelated", self.stamp)
        Product.objects.filter(sku="unrelated").update(status=Product.Status.ACTIVE)
        self.product("match-prior-day", "2026-11-18T01:00:00+00:00")
        Product.objects.filter(sku="match-prior-day").update(status=Product.Status.ACTIVE)
        url = self.link(self.chart(), "2026-11-19", 13)
        column = self.client.get(url).context["cl"].list_display.index("sku")
        url += f"&q=match&status__exact=active&o=-{column}&_nova_page_size=10&p=2"
        listing = self.client.get(url)
        self.assertEqual(len(listing.context["cl"].result_list), 1)
        form = self.form(listing)
        self.assertEqual(form["method"], "post")
        self.assertIsNone(form.find_parent("form"))
        target = urljoin(url, form["action"])
        query = parse_qs(urlsplit(target).query)
        self.assertNotIn("p", query)
        self.assertEqual(query["status__exact"], ["active"])
        rows = self.csv_rows(self.download(target, fields="price,stock", limit="1", _selected_action="0"))
        self.assertEqual(rows[0], self.headers)
        self.assertTrue(all(len(row) == 3 for row in rows))
        self.assertEqual([r[0] for r in rows[1:]], [f"match-{i:02}" for i in reversed(range(11))])

    def test_chart_timezone_cutoff_and_current_scope_at_download(self):
        self.grant_export()
        first = self.product("first", "2026-11-01T05:30:00+00:00")
        self.product("at-cutoff", "2026-11-01T06:30:00+00:00")
        self.product("hidden-by-queryset", "2026-11-01T05:30:00+00:00")
        denied = self.product("hidden-by-object", "2026-11-01T05:30:00+00:00")
        self.product("prior", "2026-11-01T03:59:59+00:00")
        url = self.link(self.chart(zone="America/New_York", now="2026-11-01T06:30:00+00:00"), "2026-11-01", 4)
        self.product("later", "2026-11-01T06:30:00.000001+00:00")
        visible = Product.objects.exclude(sku="hidden-by-queryset")
        with timezone.override(ZoneInfo("Europe/London")), patch.object(self.owner, "get_queryset", return_value=visible), patch.object(
            self.owner, "has_view_or_change_permission", side_effect=lambda request, obj=None: obj != denied
        ):
            response = self.download(url)
        self.assertEqual(response["Content-Disposition"], 'attachment; filename="products-2026-11-01.csv"')
        rows = self.csv_rows(response)
        self.assertEqual(rows[0][-1], "更新时间 (America/New_York)")
        self.assertEqual([(r[0], r[2]) for r in rows[1:]], [
            ("at-cutoff", "2026-11-01T01:30:00-05:00"), (first.sku, "2026-11-01T01:30:00-04:00"),
        ])
        with patch.object(self.owner, "get_list_display", return_value=["name", "updated_at"]):
            self.assertIsNone(self.form(self.client.get(url)))
            self.assertEqual(self.download(url).status_code, 403)
        with patch.object(self.owner, "has_module_permission", return_value=False):
            self.assertEqual(self.download(url).status_code, 403)

    def test_native_date_lookup_uses_chart_timezone_for_list_count_and_download(self):
        self.grant_export()
        product = self.product("midnight", "2026-11-18T16:00:00+00:00")
        url = self.link(self.chart(), "2026-11-19", 1) + "&updated_at__date=2026-11-19"
        with timezone.override(ZoneInfo("UTC")):
            page = self.client.get(url)
            self.assertEqual(page.context["cl"].result_count, 1)
            self.assertContains(page, product.sku)
            rows = self.csv_rows(self.download(url))
        self.assertEqual(rows[1:], [[product.sku, product.name, "2026-11-19T00:00:00+08:00"]])

    @override_settings(USE_TZ=False, TIME_ZONE="Asia/Shanghai")
    def test_naive_storage_preserves_local_wall_time(self):
        self.grant_export()
        self.product("local", "2026-11-19T09:30:00")
        self.product("late", "2026-11-19T09:30:01")
        card = self.chart(zone="America/New_York")
        rows = self.csv_rows(self.download(self.link(card, "2026-11-19", 1)))
        self.assertEqual(rows, [self.headers, ["local", "local", "2026-11-19T09:30:00"]])

    def test_empty_day_empty_search_and_currently_hidden_rows_yield_only_headers(self):
        self.grant_export()
        self.product("today", self.stamp)
        card = self.chart()
        url = self.link(card, "2026-11-19", 1)
        for target in (self.link(card, "2026-11-18", 0), url + "&q=absent"):
            self.assertIsNotNone(self.form(self.client.get(target)))
            self.assertEqual(self.csv_rows(self.download(target)), [self.headers])
        with patch.object(self.owner, "get_queryset", return_value=Product.objects.none()):
            self.assertEqual(self.csv_rows(self.download(url)), [self.headers])

    def test_invalid_day_cross_account_and_unfiltered_list_cannot_export(self):
        self.grant_export()
        self.product("visible", self.stamp)
        url = self.link(self.chart(), "2026-11-19", 1)
        ordinary = reverse("admin:catalog_product_changelist")
        self.assertIsNone(self.form(self.client.get(ordinary)))
        for target in (ordinary, url + "x", url + "&activity_day=", url + "&_popup=1"):
            response = self.download(target)
            self.assertEqual(response.status_code, 404)
            self.assertNotIn("Content-Disposition", response)
        invalid = self.download(url + "&unknown_filter=bogus")
        self.assertEqual(invalid.status_code, 400)
        self.assertNotIn("Content-Disposition", invalid)
        other = get_user_model().objects.create_user("another-exporter", is_staff=True)
        other.user_permissions.add(*self.reader.user_permissions.all())
        self.client.force_login(other)
        self.assertEqual(self.download(url).status_code, 404)

    @override_settings(ROOT_URLCONF="tests.multisite_urls", NOVA_ADMIN_URL_NAMESPACES={})
    def test_another_authorized_site_cannot_reuse_the_signed_day(self):
        from tests.multisite_urls import warehouse_site

        self.grant_export()
        self.reader.user_permissions.add(Permission.objects.get(codename="view_category"))
        self.product("warehouse", self.stamp)
        with patch.object(warehouse_site, "index_template", "project_admin/dashboard.html"):
            url = self.link(self.chart(site="warehouse"), "2026-11-19", 1)
        self.assertEqual(self.csv_rows(self.download(url))[1][0], "warehouse")
        other_site = reverse("review:catalog_product_changelist") + "?" + urlsplit(url).query
        self.assertEqual(self.download(other_site).status_code, 404)

    def test_actual_file_escapes_formula_prefixes_quotes_and_record_separators(self):
        self.grant_export()
        product = self.product("  ＝1", self.stamp)
        label = '普通商品,"A";\r\n第二行'
        Product.objects.filter(pk=product.pk).update(name=label)
        other = self.product("plain", self.stamp)
        Product.objects.filter(pk=other.pk).update(name='\t+2')
        url = self.link(self.chart(), "2026-11-19", 2)
        rows = self.csv_rows(self.download(url))
        self.assertCountEqual([r[:2] for r in rows[1:]], [["TEXT:   ＝1", label], ["plain", "TEXT: \t+2"]])

    def test_row_cap_allows_exact_limit_and_rejects_overflow_without_a_partial_download(self):
        self.grant_export()
        Product.objects.bulk_create([Product(sku=f"p{i}", name="match", price=1) for i in range(MAX_EXPORT_ROWS)])
        Product.objects.update(updated_at=datetime.fromisoformat(self.stamp))
        url = self.link(self.chart(), "2026-11-19", MAX_EXPORT_ROWS)
        self.assertEqual(len(self.csv_rows(self.download(url))) - 1, MAX_EXPORT_ROWS)
        self.product("extra", self.stamp)
        listing = self.client.get(url)
        self.assertIsNone(self.form(listing))
        self.assertContains(listing, "请将筛选结果缩小")
        response = self.download(url, limit=str(MAX_EXPORT_ROWS + 1))
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("Content-Disposition", response)
        self.assertEqual(len(self.csv_rows(self.download(url + "&q=extra"))), 2)

    def test_export_form_requires_csrf_and_never_applies_list_edits(self):
        self.grant_export()
        self.reader.user_permissions.add(Permission.objects.get(codename="change_product"))
        product = self.product("untouched", self.stamp)
        url = self.link(self.chart(), "2026-11-19", 1)
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.reader)
        form = self.form(self.client.get(url))
        self.assertEqual(self.download(url).status_code, 403)
        token = form.select_one('input[name="csrfmiddlewaretoken"]')["value"]
        self.csv_rows(self.download(url, csrfmiddlewaretoken=token, _save="1", **{"form-0-featured": "on"}))
        product.refresh_from_db()
        self.assertFalse(product.featured)


class ProductStatusCSVTests(ProductCSVAssertions, ProductDayTestCase):
    export_action = "_export_status_csv"

    def status_url(self, status, site="admin"):
        page = BeautifulSoup(self.client.get(reverse(f"{site}:index")).content, "html.parser")
        return page.select_one(f'.nova-category-chart a[data-nova-category="{status}"]')["href"]

    def test_readonly_exports_current_search_filters_order_and_all_pages(self):
        self.grant_export()
        Product.objects.bulk_create([
            Product(sku=f"match-{i:02}", name="样品", price=10, status="active") for i in range(12)
        ] + [
            Product(sku="match-draft", name="草稿", price=10),
            Product(sku="match-cheap", name="低价", price=1, status="active"),
            Product(sku="unrelated", name="其他", price=10, status="active"),
        ])
        url = self.status_url("active")
        column = self.client.get(url).context["cl"].list_display.index("sku")
        filtered = url + f"&q=match&price__gte=10&o=-{column}&_nova_page_size=10&p=2"
        listing = self.client.get(filtered)
        self.assertIsNone(listing.context["cl"].formset)
        self.assertEqual(len(listing.context["cl"].result_list), 2)
        form = self.form(listing)
        self.assertEqual(form["method"], "post")
        self.assertIsNone(form.find_parent("form"))
        action = urljoin(filtered, form["action"])
        query = parse_qs(urlsplit(action).query)
        self.assertNotIn("p", query)
        self.assertEqual(query["status__exact"], ["active"])
        response = self.download(action, fields="price,stock", status__exact="draft", _selected_action="0")
        self.assertEqual(response["Content-Disposition"], 'attachment; filename="products-status-active.csv"')
        rows = self.csv_rows(response)
        self.assertEqual(rows[0], self.headers)
        self.assertTrue(all(len(row) == 3 for row in rows))
        self.assertEqual([row[0] for row in rows[1:]], [f"match-{i:02}" for i in reversed(range(12))])

    def test_status_and_visibility_rechecked_at_download_and_empty_results_keep_headers(self):
        self.grant_export()
        valid, changed, scoped, denied, removed = [self.product(sku, self.stamp) for sku in
                                                   ("valid", "changed", "scoped", "denied", "removed")]
        url = self.status_url("draft")
        Product.objects.filter(pk=changed.pk).update(status="archived")
        removed.delete()
        with patch.object(self.owner, "get_queryset", return_value=Product.objects.exclude(pk=scoped.pk)), patch.object(
            self.owner, "has_view_or_change_permission", side_effect=lambda req, obj=None: obj != denied
        ):
            self.assertEqual([r[0] for r in self.csv_rows(self.download(url))[1:]], [valid.sku])
            self.assertEqual(self.csv_rows(self.download(url + "&q=denied")), [self.headers])
        empty = self.status_url("active")
        self.assertIsNotNone(self.form(self.client.get(empty)))
        self.assertEqual(self.csv_rows(self.download(empty)), [self.headers])
        with patch.object(self.owner, "get_queryset", return_value=Product.objects.none()):
            self.assertEqual(self.csv_rows(self.download(url)), [self.headers])

    def test_export_permission_columns_and_status_visibility_rechecked(self):
        self.product("sample", self.stamp)
        url = self.status_url("draft")
        for editing in (False, True):
            if editing:
                self.reader.user_permissions.add(Permission.objects.get(codename="change_product"))
            self.assertIsNone(self.form(self.client.get(url)))
            self.assertEqual(self.download(url).status_code, 403)
        self.grant_export()
        self.assertIsNotNone(self.form(self.client.get(url)))
        for display in (["name", "updated_at", "status_badge"], ["sku", "name", "updated_at"]):
            with patch.object(self.owner, "get_list_display", return_value=display):
                self.assertIsNone(self.form(self.client.get(url)))
                self.assertEqual(self.download(url).status_code, 403)
        with patch.object(self.owner, "has_module_permission", return_value=False):
            self.assertEqual(self.download(url).status_code, 403)
        self.reader.user_permissions.clear()
        self.grant_export()
        self.assertEqual(self.download(url).status_code, 403)

    def test_only_a_single_known_status_and_csrf_protected_post_can_download(self):
        self.grant_export()
        self.product("sample", self.stamp)
        base = reverse("admin:catalog_product_changelist")
        url = self.status_url("draft")
        for query in ("", "?status__exact=", "?status__in=draft,active", "?status__exact=other",
                      "?status__exact=draft&status__exact=active", "?status__exact=draft&_popup=1"):
            with self.subTest(query=query):
                response = self.download(base + query, status__exact="draft")
                self.assertEqual(response.status_code, 404)
                self.assertNotIn("Content-Disposition", response)
        self.assertEqual(self.download(url + "&unexpected_filter=1").status_code, 400)
        self.assertEqual(self.download(url, _export_day_csv="1").status_code, 404)
        self.assertEqual(self.download(url + "&activity_day=invalid").status_code, 404)
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.reader)
        form = self.form(self.client.get(url))
        self.assertEqual(self.download(url).status_code, 403)
        token = form.select_one('[name="csrfmiddlewaretoken"]')["value"]
        self.assertEqual(len(self.csv_rows(self.download(url, csrfmiddlewaretoken=token))), 2)

    def test_formula_safety_and_list_timezone_in_actual_file(self):
        self.grant_export()
        product = self.product("  ＝1", self.stamp)
        Product.objects.filter(pk=product.pk).update(name='@商品,"灯"\n第二行')
        with timezone.override(ZoneInfo("America/New_York")):
            url = self.status_url("draft") + "&updated_at__date=2026-11-18"
            self.assertEqual(self.client.get(url).context["cl"].result_count, 1)
            self.assertEqual(self.csv_rows(self.download(url)), [
                ["SKU", "商品名称", "更新时间 (America/New_York)"],
                ["TEXT:   ＝1", 'TEXT: @商品,"灯"\n第二行', "2026-11-18T20:00:00-05:00"],
            ])

    def test_status_row_cap_after_filtering(self):
        self.grant_export()
        Product.objects.bulk_create([Product(sku=f"d{i}", name="样品", price=1) for i in range(MAX_EXPORT_ROWS)])
        other = Product.objects.create(sku="extra", name="上架商品", price=1, status="active")
        url = self.status_url("draft")
        self.assertEqual(len(self.csv_rows(self.download(url))) - 1, MAX_EXPORT_ROWS)
        Product.objects.filter(pk=other.pk).update(status="draft")
        self.assertIsNone(self.form(self.client.get(url)))
        response = self.download(url, limit=MAX_EXPORT_ROWS + 1)
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("Content-Disposition", response)
        self.assertEqual(self.csv_rows(self.download(url + "&q=extra"))[1][0], "extra")

    @override_settings(ROOT_URLCONF="tests.multisite_urls", NOVA_ADMIN_URL_NAMESPACES={})
    def test_target_site_uses_its_own_product_scope(self):
        from tests.multisite_urls import warehouse_site

        self.grant_export()
        visible = self.product("warehouse", self.stamp)
        self.product("another-site", self.stamp)
        with patch.object(warehouse_site, "index_template", "project_admin/dashboard.html"), patch.object(
            warehouse_site.get_model_admin(Product), "get_queryset", return_value=Product.objects.filter(pk=visible.pk)
        ):
            url = self.status_url("draft", "warehouse")
            self.assertEqual([r[0] for r in self.csv_rows(self.download(url))[1:]], ["warehouse"])
