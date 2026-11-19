import json
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db.models import Q
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from catalog.models import Category, Product, Tag
from tests.test_product_analysis import ProductAnalysisTestCase


class ProductTagRankingTests(ProductAnalysisTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.root = Category.objects.create(name="灯具", slug="lamps")
        cls.child = Category.objects.create(name="台灯", slug="desklamps", parent=cls.root)
        cls.popular = Tag.objects.create(name="人气", slug="popular")
        cls.sale = Tag.objects.create(name="促销", slug="sale")

    def item(self, sku, *tags, category=None, status="draft", stamp=None):
        item = self.product(sku, stamp or self.cutoff)
        Product.objects.filter(pk=item.pk).update(category=category, status=status)
        item.tags.add(*tags)
        return item

    def ranking(self, page):
        return [(row.th.get_text(strip=True), int(row.td.get_text()))
                for row in page.select("#product-tag-ranking tbody tr")]

    def tag_url(self, page, url, key):
        for a in page.select("#product-tag-ranking tbody a"):
            if parse_qs(urlsplit(a["href"]).query)["chart_tag"] == [str(key)]:
                return urljoin(url, a["href"])
        self.fail(f"Missing tag link for {key}")

    def test_multitag_counts_and_drilldown_preserve_direct_scope_window_and_full_csv(self):
        extra = Tag.objects.create(name="手工", slug="handmade")
        self.item("@first", self.popular, self.sale, extra, category=self.root, stamp="2026-10-31T04:00:00+00:00")
        self.item("fold", self.popular, category=self.root, stamp="2026-11-01T05:30:00+00:00")
        self.item("child", self.popular, self.sale, category=self.child)
        self.item("loose", category=self.root)
        self.item("active", self.popular, category=self.root, status="active")
        self.item("other-category", self.sale)
        self.item("after", self.popular, category=self.root, stamp="2026-11-01T06:30:00.000001+00:00")
        self.item("before", self.popular, category=self.root, stamp="2026-10-31T03:59:59.999999+00:00")
        denied = self.item("denied", self.popular, category=self.root)
        self.item("outside", self.popular, category=self.root)
        self.item("deleted", self.popular, category=self.root).delete()

        # This host join duplicates some products and mentions only two of their tags.
        scope = Product.objects.filter(Q(tags__in=[self.popular, self.sale]) | Q(tags__isnull=True)).exclude(sku="outside")
        url = self.entry() + "&chart_start=2026-10-31&chart_end=2026-11-01&chart_status=draft"
        with timezone.override(ZoneInfo("Asia/Tokyo")), patch.object(self.owner, "list_per_page", 1), patch.object(
            self.owner, "get_queryset", return_value=scope
        ), patch.object(self.owner, "has_view_permission", side_effect=lambda req, obj=None: obj != denied):
            whole = self.open_page(url)
            subtree = urljoin(url, whole.select_one("#product-category-ranking").find("a", string="灯具")["href"])
            branch = self.open_page(subtree)
            self.assertEqual(self.ranking(branch), [("人气", 3), ("促销", 2), ("手工", 1), ("未打标签", 1)])
            direct = urljoin(subtree, branch.find("a", string="本级直属商品")["href"])
            direct_page = self.open_page(direct)
            expected = [("人气", 2), ("促销", 1), ("手工", 1), ("未打标签", 1)]
            self.assertEqual(self.ranking(direct_page), expected)
            selected = self.tag_url(direct_page, direct, self.popular.pk)
            page = self.open_page(selected)
            self.assertEqual(self.ranking(page), expected)
            self.assertEqual(page.select_one('#product-tag-ranking [aria-current="true"]').string, "人气")
            self.assertEqual(page.select_one('#product-chart-filters [name=chart_tag]')["value"], str(self.popular.pk))
            self.assertEqual(page.select_one('#product-chart-filters [name=chart_category]')["value"], f"direct-{self.root.pk}")
            daily, status = [json.loads(n.string) for n in page.select('.product-analysis-charts [type="application/json"]')]
            self.assertTrue(all((s["timezone"], s["as_of"]) == (self.zone, self.cutoff) for s in (daily, status)))
            self.assertEqual([p["value"] for p in daily["points"]], [1, 1])
            self.assertEqual([p["value"] for p in status["points"]], [2, 1, 0])
            self.assertEqual(page.select_one("#product-details tbody th a").string, "fold")
            self.assertIsNone(page.select_one('#product-details form, [name="_save"]'))
            self.assertEqual(self.download(selected).status_code, 403)

            self.grant_export()
            next_page = self.chart_link(page, selected, '#product-details a[rel="next"]')
            second = self.open_page(next_page)
            self.assertEqual(second.select_one("#product-details tbody th a").string, "@first")
            export = urljoin(next_page, second.select_one("#product-details form")["action"])
            self.assertEqual(self.csv_rows(self.download(export)), [
                ["SKU", "商品名称", "更新时间 (America/New_York)"],
                ["fold", "fold", "2026-11-01T01:30:00-04:00"],
                ["TEXT: @first", "TEXT: @first", "2026-10-31T00:00:00-04:00"],
            ])
            switched = self.tag_url(second, next_page, self.sale.pk)
            self.assertEqual([r[0] for r in self.csv_rows(self.download(switched))[1:]], ["TEXT: @first"])
            self.assertNotIn("page", parse_qs(urlsplit(switched).query))
            day = self.chart_link(page, selected, 'a[data-nova-chart-day="2026-11-01"]')
            listed = self.chart_link(self.open_page(day), day, 'a[data-nova-category="active"]')
            self.assertEqual([r[0] for r in self.csv_rows(self.download(listed))[1:]], ["active"])
            back = urljoin(selected, page.find("a", string="返回整棵子树")["href"])
            self.assertEqual([r[0] for r in self.csv_rows(self.download(back))[1:]], ["child", "fold", "TEXT: @first"])
            child = urljoin(back, self.open_page(back).find("a", string="台灯")["href"])
            self.assertEqual([r[0] for r in self.csv_rows(self.download(child))[1:]], ["child"])
            clear = urljoin(child, self.open_page(child).find("a", string="清除标签筛选")["href"])
            self.assertEqual(parse_qs(urlsplit(clear).query), {**parse_qs(urlsplit(url).query), "chart_category": [str(self.child.pk)]})
            self.assertNotIn("chart_tag", parse_qs(urlsplit(page.select_one(".breadcrumbs a")["href"]).query))

    def test_untagged_is_distinct_from_a_named_tag_and_empty_export_keeps_headers(self):
        self.grant_export()
        named = Tag.objects.create(name="未打标签", slug="named")
        self.item("plain")
        self.item("named", named)
        self.item("two-tags", named, self.sale)
        url = self.entry()
        initial = self.open_page(url)
        for key, skus in (("untagged", ["plain"]), (named.pk, ["two-tags", "named"])):
            with self.subTest(key=key):
                selected = self.tag_url(initial, url, key)
                self.assertEqual([r[0] for r in self.csv_rows(self.download(selected))[1:]], skus)
                # Both charts have an empty period even though the tag is still readable.
                empty = urlsplit(selected)._replace(fragment="").geturl() + "&chart_start=2026-10-01&chart_end=2026-10-01"
                page = self.open_page(empty)
                self.assertIn("没有可查看的商品", page.select_one("#product-details").get_text())
                self.assertEqual(self.ranking(page), [])
                self.assertIsNone(page.select_one('.product-analysis-charts [type="application/json"]'))
                self.assertIsNotNone(page.find("a", string="清除标签筛选"))
                self.assertEqual(self.csv_rows(self.download(empty)), [["SKU", "商品名称", "更新时间 (America/New_York)"]])

    def test_tag_filter_can_empty_the_direct_scope_and_export_limit_applies_after_filtering(self):
        self.grant_export()
        self.item("direct", self.sale, category=self.root)
        self.item("child", self.popular, self.sale, category=self.child)
        url = self.entry()
        root_url = urljoin(url, self.open_page(url).find("a", string="灯具")["href"])
        branch = self.open_page(root_url)
        direct_url = urljoin(root_url, branch.find("a", string="本级直属商品")["href"])
        selected = self.tag_url(branch, root_url, self.popular.pk)
        with patch("catalog.product_csv.MAX_EXPORT_ROWS", 1):
            self.assertEqual(self.download(root_url).status_code, 400)
            self.assertEqual([r[0] for r in self.csv_rows(self.download(selected))[1:]], ["child"])

        # The bookmarked direct scope now has no item with this tag.
        query = parse_qs(urlsplit(direct_url).query)
        query["chart_tag"] = [str(self.popular.pk)]
        empty = urlsplit(direct_url)._replace(query=urlencode(query, doseq=True), fragment="").geturl()
        page = self.open_page(empty)
        self.assertEqual(self.ranking(page), [("促销", 1)])
        self.assertIsNone(page.select_one("#product-details tbody tr"))
        self.assertEqual(len(self.csv_rows(self.download(empty))), 1)
        back = urljoin(empty, page.find("a", string="返回整棵子树")["href"])
        self.assertEqual(parse_qs(urlsplit(back).query), parse_qs(urlsplit(selected).query))

    def test_visibility_is_rechecked_for_tag_fields_tag_objects_and_stale_links(self):
        self.grant_export()
        private = self.item("private", self.popular)
        self.item("plain")
        url = self.entry()
        selected = self.tag_url(self.open_page(url), url, self.popular.pk)
        layout = self.owner.fieldsets
        hidden = [(None, {"fields": ("name", "status", "updated_at")})]
        with patch.object(self.owner, "get_fieldsets", side_effect=lambda req, obj=None: hidden if obj == private else layout):
            self.assertEqual(self.ranking(self.open_page(url)), [("未打标签", 1)])
            self.assertEqual(self.client.get(selected).status_code, 404)
            self.assertEqual(self.download(selected).status_code, 404)
        with patch.object(self.owner, "get_exclude", return_value=["tags"]):
            self.assertIsNone(self.open_page(url).select_one("#product-tag-ranking"))
            self.assertEqual(self.download(selected).status_code, 403)
            self.assertEqual(self.client.get(url + "&chart_tag=untagged").status_code, 403)
        self.reader.user_permissions.add(Permission.objects.get(codename="view_tag"))
        tag_admin = self.owner.admin_site.get_model_admin(Tag)
        for restriction in (patch.object(tag_admin, "get_queryset", return_value=Tag.objects.exclude(pk=self.popular.pk)),
                            patch.object(tag_admin, "has_view_permission", side_effect=lambda req, obj=None: obj != self.popular)):
            with restriction:
                page = self.open_page(url)
                self.assertEqual(self.ranking(page), [("未打标签", 1)])
                self.assertEqual(self.download(selected).status_code, 404)
                loose = self.tag_url(page, url, "untagged")
                self.assertEqual([r[0] for r in self.csv_rows(self.download(loose))[1:]], ["plain"])
        Product.objects.filter(pk=private.pk).update(updated_at="2026-11-01T06:30:00.000001+00:00")
        self.assertEqual(self.download(selected).status_code, 404)
        self.reader.user_permissions.remove(Permission.objects.get(codename="export_product"))
        self.assertEqual(self.download(url + "&chart_tag=untagged").status_code, 403)

    @override_settings(ROOT_URLCONF="tests.multisite_urls", NOVA_ADMIN_URL_NAMESPACES={})
    def test_tag_coordinates_require_one_valid_value_and_the_same_account_and_site(self):
        from tests.multisite_urls import warehouse_site

        self.grant_export()
        self.reader.user_permissions.add(Permission.objects.get(codename="view_category"))
        self.item("visible", self.popular)
        with patch.object(warehouse_site, "index_template", "project_admin/dashboard.html"):
            url = self.entry("warehouse")
        choice = self.tag_url(self.open_page(url), url, self.popular.pk)
        self.assertEqual(self.download(choice).status_code, 200)
        for value in ("", "0", "01", "-1", "１", "9223372036854775808", "all", str(self.sale.pk),
                      "untagged&chart_tag=1"):
            with self.subTest(value=value):
                result = self.download(url + "&chart_tag=" + value)
                self.assertEqual(result.status_code, 404)
                self.assertNotIn("Content-Disposition", result)
        for invalid in (urlsplit(url).path + "?chart_tag=untagged",
                        reverse("review:catalog_product_analysis") + "?" + urlsplit(choice).query):
            self.assertEqual(self.client.get(invalid).status_code, 404)
            self.assertEqual(self.download(invalid).status_code, 404)
        other = get_user_model().objects.create_user("other-tag-reader", is_staff=True)
        other.user_permissions.set(self.reader.user_permissions.all())
        self.client.force_login(other)
        self.assertEqual(self.download(choice).status_code, 404)
