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
        return [(row.th.get_text(strip=True), int(row.td.string)) for row in page.select("#product-category-ranking tbody tr")]

    def choose(self, page, url, key):
        for link in page.select("#product-category-ranking tbody a"):
            if parse_qs(urlsplit(link["href"]).query)["chart_category"] == [str(key)]:
                return urljoin(url, link["href"])
        self.fail(f"Missing category link for {key}")

    def test_scoped_ranking_drives_both_charts_details_pagination_and_full_csv(self):
        self.grant_export()
        leaf = Category.objects.create(name="阅读灯", slug="reading", parent=self.desks)
        clock = Category.objects.create(name="挂钟", slug="clock")
        first = self.item("@first", leaf, stamp="2026-10-31T04:00:00+00:00")
        self.item("fold", self.desks, stamp="2026-11-01T05:30:00+00:00")
        self.item("cutoff", self.lamps)
        self.item("listed", self.lamps, status="active")
        self.item("clock", clock)
        self.item("loose", None)
        self.item("before", self.lamps, stamp="2026-10-31T03:59:59.999999+00:00")
        self.item("later", self.lamps, stamp="2026-11-01T06:30:00.000001+00:00")
        denied = self.item("denied", leaf)
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
            expected = [("灯具", 3), ("挂钟", 1), ("未分类", 1)]
            self.assertEqual(self.ranking(whole), expected)
            selected = self.choose(whole, url, self.lamps.pk)
            page = self.open_page(selected)
            self.assertEqual(self.ranking(page), [("书桌", 2), ("本级直属商品", 1)])
            self.assertEqual(page.select_one('#product-category-ranking [aria-current="page"]').string, "灯具")
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
            self.assertEqual(self.ranking(drilled), [("书桌", 1)])
            self.assertEqual([a.string for a in drilled.select("#product-details tbody th a")], [first.name])
            listed = self.chart_link(page, selected, 'a[data-nova-category="active"]')
            self.assertEqual(self.ranking(self.open_page(listed)), [("本级直属商品", 1)])
            clear = page.find("a", string="清除分类筛选")["href"]
            self.assertEqual(parse_qs(urlsplit(clear).query), parse_qs(urlsplit(url).query))
            self.assertNotIn("chart_category", parse_qs(urlsplit(page.select_one(".breadcrumbs a")["href"]).query))

            child_url = self.choose(page, selected, self.desks.pk)
            child = self.open_page(child_url)
            self.assertEqual(self.ranking(child), [("本级直属商品", 1), ("阅读灯", 1)])
            self.assertEqual([a.string for a in child.select("#product-details tbody th a")], ["fold", first.name])
            self.assertEqual([r[0] for r in self.csv_rows(self.download(child_url))[1:]], ["fold", "TEXT: @first"])
            leaf_url = self.choose(child, child_url, leaf.pk)
            terminal = self.open_page(leaf_url)
            self.assertEqual(self.ranking(terminal), [("本级直属商品", 1)])
            self.assertEqual([a.string for a in terminal.select("#product-category-ranking tbody a")], ["本级直属商品"])
            self.assertEqual([a.string for a in terminal.select("#product-details tbody th a")], [first.name])
            self.assertEqual([r[0] for r in self.csv_rows(self.download(leaf_url))[1:]], ["TEXT: @first"])
            daily, status = [json.loads(s.string) for s in terminal.select('.product-analysis-charts [type="application/json"]')]
            self.assertEqual([p["value"] for p in daily["points"]], [1, 0])
            self.assertEqual([p["value"] for p in status["points"]], [1, 0, 0])
            links = terminal.select("#product-category-ranking nav a")
            self.assertEqual([a.string for a in links], ["清除分类筛选", "灯具", "书桌"])
            self.assertEqual([parse_qs(urlsplit(a["href"]).query) for a in links],
                             [parse_qs(urlsplit(u).query) for u in (url, selected, child_url)])

    def test_direct_drilldown_shares_dates_status_and_cutoff_across_charts_pages_and_csv(self):
        leaf = Category.objects.create(name="阅读灯", slug="reading", parent=self.desks)
        self.item("ancestor", self.lamps)
        self.item("descendant", leaf)
        self.item("loose", None)
        self.item("@first", self.desks, stamp="2026-10-31T04:00:00+00:00")
        self.item("last", self.desks)
        self.item("listed", self.desks, status="active", stamp="2026-11-01T05:30:00+00:00")
        self.item("before", self.desks, stamp="2026-10-31T03:59:59.999999+00:00")
        self.item("after", self.desks, stamp="2026-11-01T06:30:00.000001+00:00")
        hidden = self.item("restricted", self.desks)
        url = self.entry() + "&chart_start=2026-10-31&chart_end=2026-11-01&chart_status=draft"
        with timezone.override(ZoneInfo("Asia/Tokyo")), patch.object(self.owner, "list_per_page", 1), patch.object(
            self.owner, "has_view_permission", side_effect=lambda request, obj=None: obj != hidden
        ):
            root = self.choose(self.open_page(url), url, self.lamps.pk)
            subtree = self.choose(self.open_page(root), root, self.desks.pk)
            branch = self.open_page(subtree)
            self.assertEqual(self.ranking(branch), [("本级直属商品", 2), ("阅读灯", 1)])
            direct = urljoin(subtree, branch.find("a", string="本级直属商品")["href"])
            page = self.open_page(direct)
            self.assertEqual(self.ranking(page), [("本级直属商品", 2)])
            self.assertIn("书桌 · 本级直属商品", page.select_one('#product-category-ranking [aria-current="page"]').get_text())
            self.assertEqual(page.select_one('#product-chart-filters [name="chart_category"]')["value"],
                             parse_qs(urlsplit(direct).query)["chart_category"][0])
            self.assertIsNone(page.select_one('#product-details form, [name="_save"]'))
            self.assertEqual(self.download(direct).status_code, 403)
            daily, status = [json.loads(s.string) for s in page.select('.product-analysis-charts [type="application/json"]')]
            self.assertTrue(all((s["as_of"], s["timezone"]) == (self.cutoff, self.zone) for s in (daily, status)))
            self.assertEqual([p["value"] for p in daily["points"]], [1, 1])
            self.assertEqual([p["value"] for p in status["points"]], [2, 1, 0])
            self.assertEqual([a.string for a in page.select("#product-details tbody th a")], ["last"])
            day = self.chart_link(page, direct, 'a[data-nova-chart-day="2026-11-01"]')
            listed = self.chart_link(self.open_page(day), day, 'a[data-nova-category="active"]')
            self.assertEqual([a.string for a in self.open_page(listed).select("#product-details tbody th a")], ["listed"])

            self.grant_export()
            next_page = self.chart_link(page, direct, '#product-details a[rel="next"]')
            second = self.open_page(next_page)
            self.assertEqual([a.string for a in second.select("#product-details tbody th a")], ["@first"])
            export = urljoin(next_page, second.select_one("#product-details form")["action"])
            self.assertEqual(self.csv_rows(self.download(export)), [
                ["SKU", "商品名称", "更新时间 (America/New_York)"],
                ["last", "last", "2026-11-01T01:30:00-05:00"],
                ["TEXT: @first", "TEXT: @first", "2026-10-31T00:00:00-04:00"],
            ])
            back = urljoin(next_page, second.find("a", string="返回整棵子树")["href"])
            self.assertEqual(parse_qs(urlsplit(back).query), parse_qs(urlsplit(subtree).query))
            self.assertEqual(self.ranking(self.open_page(back)), self.ranking(branch))
            self.assertEqual([r[0] for r in self.csv_rows(self.download(back))[1:]], ["last", "descendant", "TEXT: @first"])

    def test_empty_direct_selection_returns_to_subtree_with_same_filters_and_rechecks_permissions(self):
        self.grant_export()
        self.reader.user_permissions.add(Permission.objects.get(codename="view_category"))
        direct_item = self.item("direct", self.lamps)
        self.item("child", self.desks, status="archived")
        url = self.entry() + "&chart_start=2026-10-31&chart_end=2026-11-01&chart_day=2026-11-01"
        subtree = self.choose(self.open_page(url), url, self.lamps.pk)
        direct = urljoin(subtree, self.open_page(subtree).find("a", string="本级直属商品")["href"])
        archived = self.chart_link(self.open_page(direct), direct, 'a[data-nova-category="archived"]')
        page = self.open_page(archived)
        self.assertEqual(self.ranking(page), [])
        self.assertIn("没有可查看的商品", page.select_one("#product-details").get_text())
        self.assertEqual(self.csv_rows(self.download(archived)), [["SKU", "商品名称", "更新时间 (America/New_York)"]])
        back = urljoin(archived, page.find("a", string="返回整棵子树")["href"])
        self.assertEqual(parse_qs(urlsplit(back).query), {**parse_qs(urlsplit(subtree).query), "chart_status": ["archived"]})
        self.assertEqual([r[0] for r in self.csv_rows(self.download(back))[1:]], ["child"])

        # This branch remains visible through its child when its only direct item becomes private.
        with patch.object(self.owner, "get_queryset", return_value=Product.objects.exclude(pk=direct_item.pk)):
            self.assertEqual(self.csv_rows(self.download(direct)), [["SKU", "商品名称", "更新时间 (America/New_York)"]])
            self.assertIsNotNone(self.open_page(direct).find("a", string="返回整棵子树"))
        categories = self.owner.admin_site.get_model_admin(Category)
        with patch.object(categories, "get_queryset", return_value=Category.objects.exclude(pk=self.lamps.pk)):
            self.assertEqual(self.client.get(direct).status_code, 404)
            self.assertEqual(self.download(direct).status_code, 404)
        with patch.object(self.owner, "get_exclude", return_value=["category"]):
            self.assertEqual(self.download(direct).status_code, 403)
        self.reader.user_permissions.remove(Permission.objects.get(codename="export_product"))
        denied = self.download(direct)
        self.assertEqual(denied.status_code, 403)
        self.assertNotIn("Content-Disposition", denied)

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

    def test_readonly_tree_access_reveals_empty_ancestors_only_for_authorized_branches(self):
        leaf = Category.objects.create(name="阅读灯", slug="reading", parent=self.desks)
        self.item("leaf", leaf)
        self.item("loose", None)
        url = self.entry()
        parent_url = url + "&chart_category=" + str(self.lamps.pk)
        self.assertEqual(self.ranking(self.open_page(url)), [("阅读灯", 1), ("未分类", 1)])
        self.assertEqual(self.client.get(parent_url).status_code, 404)
        self.reader.user_permissions.add(Permission.objects.get(codename="view_category"))
        root = self.open_page(url)
        self.assertEqual(self.ranking(root), [("灯具", 1), ("未分类", 1)])
        parent = self.open_page(self.choose(root, url, self.lamps.pk))
        self.assertEqual(self.ranking(parent), [("书桌", 1)])
        child_url = self.choose(parent, parent_url, self.desks.pk)
        child = self.open_page(child_url)
        self.assertEqual(self.ranking(child), [("阅读灯", 1)])
        self.assertIsNone(child.select_one('#product-details form, [name="_save"]'))
        self.assertEqual(self.download(parent_url).status_code, 403)
        self.grant_export()
        self.assertEqual([r[0] for r in self.csv_rows(self.download(parent_url))[1:]], ["leaf"])
        categories = self.owner.admin_site.get_model_admin(Category)
        for hide_parent in (
            patch.object(categories, "get_queryset", return_value=Category.objects.exclude(pk=self.desks.pk)),
            patch.object(categories, "has_view_permission", side_effect=lambda request, obj=None: obj != self.desks),
        ):
            with hide_parent:
                root = self.open_page(url)
                self.assertEqual(self.ranking(root), [("阅读灯", 1), ("未分类", 1)])
                for forbidden in (parent_url, child_url):
                    self.assertEqual(self.client.get(forbidden).status_code, 404)
                    self.assertEqual(self.download(forbidden).status_code, 404)
                leaf_page = self.open_page(self.choose(root, url, leaf.pk))
                path = leaf_page.select_one("#product-category-ranking nav").get_text(strip=True)
                self.assertNotIn("书桌", path)
                self.assertNotIn("灯具", path)

    def test_existing_parent_link_rechecks_descendant_access_before_counting_or_export(self):
        self.reader.user_permissions.add(Permission.objects.get(codename="view_category"))
        self.grant_export()
        self.item("parent", self.lamps)
        self.item("child", self.desks)
        url = self.entry() + "&chart_status=draft"
        selected = self.choose(self.open_page(url), url, self.lamps.pk)
        parent = self.open_page(selected)
        child = self.choose(parent, selected, self.desks.pk)
        export = urljoin(selected, parent.select_one("#product-details form")["action"])

        categories = self.owner.admin_site.get_model_admin(Category)
        with patch.object(categories, "get_queryset", return_value=Category.objects.exclude(pk=self.desks.pk)):
            page = self.open_page(selected)
            self.assertEqual(self.ranking(page), [("本级直属商品", 1)])
            self.assertEqual([a.string for a in page.select("#product-details tbody th a")], ["parent"])
            daily, status = [json.loads(s.string) for s in page.select('.product-analysis-charts [type="application/json"]')]
            self.assertEqual(sum(point["value"] for point in daily["points"]), 1)
            self.assertEqual([point["value"] for point in status["points"]], [1, 0, 0])
            self.assertEqual([row[0] for row in self.csv_rows(self.download(export))[1:]], ["parent"])
            denied = self.download(child)
            self.assertEqual(denied.status_code, 404)
            self.assertNotIn("Content-Disposition", denied)

    def test_invalid_duplicate_unsigned_or_foreign_category_never_exports_all_rows(self):
        self.grant_export()
        self.item("loose", None)
        url = self.entry()
        for value in ("", "0", "-1", "01", "１", "9223372036854775808", "uncategorized&chart_category=1",
                      "all", "direct-", "direct-0", "direct-01", "direct-uncategorized", "direct-direct-1",
                      "direct-9223372036854775808", f"direct-{self.desks.pk}", str(self.desks.pk)):
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
            Product(sku=f"lamp-{n}", name="灯", price=1, category=self.lamps) for n in range(MAX_EXPORT_ROWS)
        ])
        Product.objects.update(updated_at=datetime.fromisoformat(self.cutoff))
        self.item("desk", self.desks)
        url = self.entry()
        page = self.open_page(url)
        self.assertEqual(self.ranking(page), [("灯具", MAX_EXPORT_ROWS + 1)])
        lamps = self.choose(page, url, self.lamps.pk)
        overflow = self.download(lamps)
        self.assertEqual(overflow.status_code, 400)
        self.assertNotIn("Content-Disposition", overflow)
        desks = self.choose(self.open_page(lamps), lamps, self.desks.pk)
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
