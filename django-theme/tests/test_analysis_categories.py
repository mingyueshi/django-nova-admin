import json
from datetime import datetime
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from catalog.models import Category, Product, Tag
from catalog.product_csv import MAX_EXPORT_ROWS
from tests.test_product_analysis import ProductAnalysisTestCase


class ProductCategoryRankingTests(ProductAnalysisTestCase):
    def setUp(self):
        super().setUp()
        self.lamps = Category.objects.create(name="灯具", slug="lamps")
        self.desks = Category.objects.create(name="书桌", slug="desks", parent=self.lamps)

    def item(self, sku, category, *, status="draft", stamp=None):
        product = self.product(sku, stamp or self.cutoff)
        Product.objects.filter(pk=product.pk).update(category=category, status=status)
        return product

    def ranking(self, page):
        return [(row.a.string, int(row.td.string)) for row in page.select("#product-category-ranking tbody tr")]

    def choose(self, page, url, key):
        for link in page.select("#product-category-ranking tbody a"):
            if parse_qs(urlsplit(link["href"]).query)["chart_category"] == [str(key)]:
                return urljoin(url, link["href"])
        self.fail(f"Missing category link for {key}")

    def test_scoped_ranking_drives_both_charts_details_pagination_and_full_csv(self):
        self.grant_export()
        first = self.item("@first", self.lamps, stamp="2026-10-31T04:00:00+00:00")
        self.item("fold", self.lamps, stamp="2026-11-01T05:30:00+00:00")
        self.item("cutoff", self.lamps)
        self.item("listed", self.lamps, status="active")
        self.item("desk", self.desks)
        self.item("loose", None)
        self.item("before", self.lamps, stamp="2026-10-31T03:59:59.999999+00:00")
        self.item("later", self.lamps, stamp="2026-11-01T06:30:00.000001+00:00")
        denied = self.item("denied", self.lamps)
        self.item("outside-queryset", self.lamps)
        self.item("deleted", self.lamps).delete()
        tags = [Tag.objects.create(name=k, slug=k) for k in ("one", "two")]
        for obj in Product.objects.all():
            obj.tags.add(*tags)
        scope = Product.objects.filter(tags__in=tags).exclude(sku="outside-queryset")
        url = self.entry() + "&chart_start=2026-10-31&chart_end=2026-11-01&chart_status=draft"
        with timezone.override(ZoneInfo("Asia/Tokyo")), patch.object(self.owner, "list_per_page", 2), patch.object(
            self.owner, "get_queryset", return_value=scope
        ), patch.object(self.owner, "has_view_permission", side_effect=lambda req, obj=None: obj != denied):
            whole = self.open_page(url)
            expected = [("灯具", 3), ("书桌", 1), ("未分类", 1)]
            self.assertEqual(self.ranking(whole), expected)
            selected = self.choose(whole, url, self.lamps.pk)
            page = self.open_page(selected)
            self.assertEqual(self.ranking(page), expected)
            self.assertEqual(page.select_one('#product-category-ranking a[aria-current="true"]').string, "灯具")
            self.assertEqual(page.select_one('#product-chart-filters [name="chart_category"]')["value"], str(self.lamps.pk))
            daily, status = [json.loads(s.string) for s in page.select('.product-analysis-charts [type="application/json"]')]
            for snapshot in (daily, status):
                self.assertEqual((snapshot["timezone"], snapshot["as_of"]), (self.zone, self.cutoff))
            self.assertEqual([p["value"] for p in daily["points"]], [1, 2])
            self.assertEqual([p["value"] for p in status["points"]], [3, 1, 0])
            self.assertEqual([a.string for a in page.select("#product-details tbody th a")], ["cutoff", "fold"])
            page_two = self.chart_link(page, selected, '#product-details a[rel="next"]')
            second = self.open_page(page_two)
            self.assertEqual([a.string for a in second.select("#product-details tbody th a")], [first.name])
            export = urljoin(page_two, second.select_one("#product-details form")["action"])
            self.assertEqual(parse_qs(urlsplit(export).query), parse_qs(urlsplit(selected).query))
            self.assertEqual(self.csv_rows(self.download(export)), [
                ["SKU", "商品名称", "更新时间 (America/New_York)"],
                ["cutoff", "cutoff", "2026-11-01T01:30:00-05:00"],
                ["fold", "fold", "2026-11-01T01:30:00-04:00"],
                ["TEXT: @first", "TEXT: @first", "2026-10-31T00:00:00-04:00"],
            ])
            day = self.chart_link(page, selected, 'a[data-nova-chart-day="2026-10-31"]')
            drilled = self.open_page(day)
            self.assertEqual(self.ranking(drilled), [("灯具", 1)])
            self.assertEqual([a.string for a in drilled.select("#product-details tbody th a")], [first.name])
            listed = self.chart_link(page, selected, 'a[data-nova-category="active"]')
            self.assertEqual(self.ranking(self.open_page(listed)), [("灯具", 1)])
            clear = page.find("a", string="清除分类筛选")["href"]
            self.assertEqual(parse_qs(urlsplit(clear).query), parse_qs(urlsplit(url).query))
            self.assertNotIn("chart_category", parse_qs(urlsplit(page.select_one(".breadcrumbs a")["href"]).query))

    def test_readonly_uncategorized_and_same_name_categories_have_distinct_keys(self):
        named = Category.objects.create(name="未分类", slug="named")
        duplicate = Category.objects.create(name="灯具", slug="another-lamp")
        for sku, category in (("loose", None), ("named", named), ("duplicate", duplicate), ("original", self.lamps)):
            self.item(sku, category)
        url = self.entry()
        page = self.open_page(url)
        self.assertEqual(self.ranking(page), [("灯具", 1), ("未分类", 1), ("灯具", 1), ("未分类", 1)])
        for key, sku in (("uncategorized", "loose"), (named.pk, "named"), (duplicate.pk, "duplicate")):
            with self.subTest(key=key):
                choice = self.choose(page, url, key)
                selected = self.open_page(choice)
                self.assertEqual([a.string for a in selected.select("#product-details tbody th a")], [sku])
                self.assertIsNone(selected.select_one('#product-details form, [name="_save"]'))
                rejected = self.download(choice)
                self.assertEqual(rejected.status_code, 403)
                self.assertNotIn("Content-Disposition", rejected)
        self.grant_export()
        loose = self.choose(page, url, "uncategorized")
        self.assertEqual([row[0] for row in self.csv_rows(self.download(loose))[1:]], ["loose"])
        self.reader.user_permissions.remove(Permission.objects.get(codename="export_product"))
        self.assertEqual(self.download(loose).status_code, 403)

    def test_zero_matches_keep_selection_and_only_true_null_is_uncategorized(self):
        self.grant_export()
        self.item("lamp", self.lamps)
        url = self.entry()
        choice = self.choose(self.open_page(url), url, self.lamps.pk)
        archived = self.chart_link(self.open_page(choice), choice, 'a[data-nova-category="archived"]')
        for empty_url in (archived, url + "&chart_category=uncategorized&chart_status=archived"):
            with self.subTest(url=empty_url):
                page = self.open_page(empty_url)
                self.assertIn("没有可排行的商品", page.select_one("#product-category-ranking").get_text())
                self.assertIn("没有可查看的商品", page.select_one("#product-details").get_text())
                self.assertIsNotNone(page.find("a", string="清除分类筛选"))
                self.assertEqual(self.csv_rows(self.download(empty_url)), [["SKU", "商品名称", "更新时间 (America/New_York)"]])
        self.item("archived-desk", self.desks, status="archived")
        self.assertEqual(self.ranking(self.open_page(archived)), [("书桌", 1)])

    def test_hidden_fields_objects_or_scope_cannot_be_used_to_discover_or_export_a_category(self):
        self.grant_export()
        secret = self.item("restricted", self.lamps)
        self.item("desk", self.desks)
        url = self.entry()
        choice = self.choose(self.open_page(url), url, self.lamps.pk)
        layout = self.owner.fieldsets
        hidden = [(None, {"fields": ("name", "status", "updated_at")})]
        with patch.object(self.owner, "get_fieldsets", side_effect=lambda request, obj=None: hidden if obj == secret else layout):
            page = self.open_page(url)
            self.assertEqual(self.ranking(page), [("书桌", 1)])
            self.assertEqual(self.client.get(choice).status_code, 404)
            self.assertEqual(self.download(choice).status_code, 404)
        with patch.object(self.owner, "get_exclude", return_value=["category"]):
            self.assertIsNone(self.open_page(url).select_one("#product-category-ranking"))
            self.assertEqual(self.download(choice).status_code, 403)
            self.assertEqual(self.client.get(url + "&chart_category=uncategorized").status_code, 403)
        with patch.object(self.owner, "get_queryset", return_value=Product.objects.exclude(pk=secret.pk)):
            self.assertEqual(self.download(choice).status_code, 404)
        Product.objects.filter(pk=secret.pk).update(updated_at="2026-11-01T06:30:00.000001+00:00")
        self.assertEqual(self.download(choice).status_code, 404)

    def test_invalid_duplicate_unsigned_or_foreign_category_never_exports_all_rows(self):
        self.grant_export()
        self.item("loose", None)
        url = self.entry()
        for value in ("", "0", "-1", "01", "１", "9223372036854775808", "uncategorized&chart_category=1",
                      "all", str(self.desks.pk)):
            with self.subTest(value=value):
                result = self.download(url + "&chart_category=" + value)
                self.assertEqual(result.status_code, 404)
                self.assertNotIn("Content-Disposition", result)
        unsigned = urlsplit(url).path + "?chart_category=uncategorized"
        self.assertEqual(self.client.get(unsigned).status_code, 404)
        self.assertEqual(self.download(unsigned).status_code, 404)

    def test_export_cap_is_applied_after_selecting_category(self):
        self.grant_export()
        Product.objects.bulk_create([
            Product(sku=f"lamp-{n}", name="灯", price=1, category=self.lamps) for n in range(MAX_EXPORT_ROWS + 1)
        ])
        Product.objects.update(updated_at=datetime.fromisoformat(self.cutoff))
        self.item("desk", self.desks)
        url = self.entry()
        page = self.open_page(url)
        self.assertEqual(self.ranking(page), [("灯具", MAX_EXPORT_ROWS + 1), ("书桌", 1)])
        lamps = self.choose(page, url, self.lamps.pk)
        overflow = self.download(lamps)
        self.assertEqual(overflow.status_code, 400)
        self.assertNotIn("Content-Disposition", overflow)
        desks = self.choose(page, url, self.desks.pk)
        self.assertEqual([r[0] for r in self.csv_rows(self.download(desks))[1:]], ["desk"])

    @override_settings(ROOT_URLCONF="tests.multisite_urls", NOVA_ADMIN_URL_NAMESPACES={})
    def test_same_site_and_account_required_for_rank_and_csv(self):
        from tests.multisite_urls import warehouse_site

        self.grant_export()
        self.reader.user_permissions.add(Permission.objects.get(codename="view_category"))
        self.item("visible", self.lamps)
        other = self.item("other", self.desks)
        owner = warehouse_site.get_model_admin(Product)
        with patch.object(warehouse_site, "index_template", "project_admin/dashboard.html"), patch.object(
            owner, "get_queryset", return_value=Product.objects.exclude(pk=other.pk)
        ):
            url = self.entry("warehouse")
            page = self.open_page(url)
            self.assertEqual(self.ranking(page), [("灯具", 1)])
            choice = self.choose(page, url, self.lamps.pk)
            self.assertEqual(self.download(choice).status_code, 200)
            self.assertEqual(self.download(url + "&" + urlencode({"chart_category": self.desks.pk})).status_code, 404)
        wrong_site = reverse("review:catalog_product_analysis") + "?" + urlsplit(choice).query
        self.assertEqual(self.download(wrong_site).status_code, 404)
        analyst = get_user_model().objects.create_user("other-category-reader", is_staff=True)
        analyst.user_permissions.set(self.reader.user_permissions.all())
        self.client.force_login(analyst)
        self.assertEqual(self.client.get(choice).status_code, 404)
        self.assertEqual(self.download(choice).status_code, 404)
