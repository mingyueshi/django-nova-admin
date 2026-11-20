import json
from itertools import product
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

    def combination(self, page, current, keys, mode, *, excluded=(), exclude_mode=None,
                    minimum=None, maximum=None, exclude_minimum=None, exclude_maximum=None, counts=(), exclude_counts=(),
                    ranges=None, exclude_ranges=None):
        form = page.select_one("#product-tag-ranking form")
        selector = form.select_one('select[name="chart_tag"][multiple]')
        self.assertFalse(selector.has_attr("required"))
        choices = {opt["value"] for opt in selector.select("option")}
        self.assertTrue(set(map(str, keys)) <= choices)
        self.assertIn(mode, [opt["value"] for opt in form.select('[name="chart_tag_mode"] option')])
        params = [(n["name"], n["value"]) for n in form.select('input[type="hidden"]')]
        params.extend((selector["name"], str(key)) for key in keys)
        exclusion = form.select_one('select[name="chart_tag_exclude"][multiple]')
        self.assertFalse(exclusion.has_attr("required"))
        self.assertTrue(set(map(str, excluded)) <= {opt["value"] for opt in exclusion.select("option")})
        params.extend((exclusion["name"], str(key)) for key in excluded)
        if exclude_mode is not None:
            rule = form.select_one('select[name="chart_tag_exclude_mode"]')
            self.assertIn(exclude_mode, [opt["value"] for opt in rule.select("option")])
            params.append((rule["name"], exclude_mode))
        params.append(("chart_tag_mode", mode))
        for parameter, value in (("chart_tag_min", minimum), ("chart_tag_max", maximum),
                                 ("chart_tag_exclude_min", exclude_minimum), ("chart_tag_exclude_max", exclude_maximum)):
            if value is not None:
                field = form.select_one(f'input[name="{parameter}"][type="number"][min="0"]')
                params.append((field["name"], str(value)))
        for parameter, values in (("chart_tag_counts", counts), ("chart_tag_exclude_counts", exclude_counts)):
            if values:
                field = form.select_one(f'select[name="{parameter}"][multiple]')
                self.assertTrue(set(map(str, values)) <= {opt["value"] for opt in field.select("option")})
                params.extend((parameter, str(n)) for n in values)
        for parameter, value in (("chart_tag_ranges", ranges), ("chart_tag_exclude_ranges", exclude_ranges)):
            if value is not None:
                field = form.select_one(f'input[type="text"][name="{parameter}"]')
                params.append((field["name"], value))
        return urlsplit(urljoin(current, form["action"]))._replace(query=urlencode(params)).geturl()

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

    def test_any_all_rank_charts_pagination_and_csv_share_the_scoped_product_ids(self):
        extra = Tag.objects.create(name="手工", slug="handmade")
        self.item("@both", self.popular, self.sale, extra, category=self.root)
        self.item("only-a", self.popular, category=self.root, stamp="2026-10-31T04:00:00+00:00")
        self.item("only-b", self.sale, category=self.root, stamp="2026-11-01T05:30:00+00:00")
        self.item("only-c", extra, category=self.root)
        self.item("listed", self.popular, self.sale, category=self.root, status="active")
        self.item("child", self.popular, self.sale, category=self.child)
        self.item("other", self.popular, self.sale)
        self.item("late", self.popular, self.sale, category=self.root, stamp="2026-11-01T06:30:00.000001+00:00")
        self.item("before", self.popular, self.sale, category=self.root, stamp="2026-10-31T03:59:59.999999+00:00")
        denied = self.item("private", self.popular, self.sale, category=self.root)
        self.item("outside", self.popular, self.sale, category=self.root)
        self.item("deleted", self.popular, self.sale, category=self.root).delete()
        scope = Product.objects.filter(tags__in=[self.popular, self.sale, extra]).exclude(sku="outside")
        url = self.entry() + "&chart_start=2026-10-31&chart_end=2026-11-01&chart_status=draft"
        keys = [str(self.popular.pk), str(self.sale.pk)]
        with timezone.override(ZoneInfo("Asia/Tokyo")), patch.object(self.owner, "list_per_page", 1), patch.object(
            self.owner, "get_queryset", return_value=scope
        ), patch.object(self.owner, "has_view_permission", side_effect=lambda req, obj=None: obj != denied):
            root_url = urljoin(url, self.open_page(url).find("a", string="灯具")["href"])
            direct = urljoin(root_url, self.open_page(root_url).find("a", string="本级直属商品")["href"])
            branch = self.open_page(direct)
            any_url = self.combination(branch, direct, keys, "any")
            page = self.open_page(any_url)
            self.assertIsNone(page.select_one('#product-details form, [name="_save"]'))
            self.assertEqual(self.download(any_url).status_code, 403)
            self.grant_export()
            for mode, expected_rank, daily_counts, draft, skus in (
                ("any", [("人气", 2), ("促销", 2), ("手工", 1)], [1, 2], 3, ["TEXT: @both", "only-b", "only-a"]),
                ("all", [("人气", 1), ("促销", 1), ("手工", 1)], [0, 1], 1, ["TEXT: @both"]),
            ):
                with self.subTest(mode=mode):
                    selected = self.combination(page, any_url, keys, mode)
                    result = self.open_page(selected)
                    self.assertEqual(self.ranking(result), expected_rank)
                    self.assertEqual(result.select_one("#product-category-ranking tbody td").get_text(strip=True), str(draft))
                    self.assertEqual([e["value"] for e in result.select('#product-chart-filters [name="chart_tag"]')], keys)
                    self.assertEqual(result.select_one('#product-chart-filters [name="chart_tag_mode"]')["value"], mode)
                    daily, status = [json.loads(n.string) for n in result.select('.product-analysis-charts [type="application/json"]')]
                    self.assertTrue(all((s["as_of"], s["timezone"]) == (self.cutoff, self.zone) for s in (daily, status)))
                    self.assertEqual([p["value"] for p in daily["points"]], daily_counts)
                    self.assertEqual([p["value"] for p in status["points"]], [draft, 1, 0])
                    self.assertIn(f"({draft})", result.select_one("#product-details-title").get_text())
                    self.assertEqual(result.select_one("#product-details tbody th a").string, "@both")
                    rows = self.csv_rows(self.download(urljoin(selected, result.select_one("#product-details form")["action"])))
                    self.assertEqual(rows[0], ["SKU", "商品名称", "更新时间 (America/New_York)"])
                    self.assertEqual([r[0] for r in rows[1:]], skus)
                    self.assertEqual(rows[1][2], "2026-11-01T01:30:00-05:00")
                    back = urljoin(selected, result.find("a", string="返回整棵子树")["href"])
                    self.assertCountEqual([r[0] for r in self.csv_rows(self.download(back))[1:]], [*skus, "child"])
                    day = self.chart_link(result, selected, 'a[data-nova-chart-day="2026-11-01"]')
                    active = self.chart_link(self.open_page(day), day, 'a[data-nova-category="active"]')
                    self.assertEqual([r[0] for r in self.csv_rows(self.download(active))[1:]], ["listed"])
                    self.assertEqual(parse_qs(urlsplit(active).query)["chart_tag"], keys)
                    clear = urljoin(selected, result.find("a", string="清除标签筛选")["href"])
                    self.assertEqual(parse_qs(urlsplit(clear).query), parse_qs(urlsplit(direct).query))
            second = self.chart_link(page, any_url, '#product-details a[rel="next"]')
            page_two = self.open_page(second)
            self.assertEqual(page_two.select_one("#product-details tbody th a").string, "only-b")
            export = urljoin(second, page_two.select_one("#product-details form")["action"])
            self.assertEqual(parse_qs(urlsplit(export).query), parse_qs(urlsplit(any_url).query))
            self.assertEqual(len(self.csv_rows(self.download(export))), 4)
            duplicate = self.combination(page_two, second, [*keys, keys[0]], "all")
            canonical = self.open_page(duplicate).select_one("#product-details form")["action"]
            self.assertEqual(parse_qs(urlsplit(canonical).query)["chart_tag"], keys)
            self.assertEqual([r[0] for r in self.csv_rows(self.download(duplicate))[1:]], ["TEXT: @both"])

    def test_untagged_union_and_empty_intersections_remain_editable(self):
        self.grant_export()
        named = Tag.objects.create(name="未打标签", slug="named")
        self.item("plain")
        self.item("named", named)
        self.item("sale", self.sale)
        url = self.entry()
        page = self.open_page(url)
        keys = [str(named.pk), "untagged"]
        choices = page.select_one('#product-tag-ranking select[multiple]')
        self.assertNotEqual(choices.find("option", value=str(named.pk)).string, choices.find("option", value="untagged").string)
        combined = self.combination(page, url, keys, "any")
        self.assertCountEqual([r[0] for r in self.csv_rows(self.download(combined))[1:]], ["plain", "named"])
        for selection in (keys, [str(named.pk), str(self.sale.pk)]):
            selected = self.combination(page, url, selection, "all")
            empty = self.open_page(selected)
            self.assertEqual(self.ranking(empty), [])
            self.assertIsNone(empty.select_one('.product-analysis-charts [type="application/json"], #product-details tbody tr'))
            self.assertIn("没有可查看的商品", empty.select_one("#product-details").get_text())
            self.assertEqual(self.csv_rows(self.download(selected)), [["SKU", "商品名称", "更新时间 (America/New_York)"]])
            choices = empty.select('#product-tag-ranking select[multiple] option[selected]')
            self.assertCountEqual([e["value"] for e in choices], selection)
            changed = self.combination(empty, selected, [self.sale.pk], "all")
            self.assertEqual([r[0] for r in self.csv_rows(self.download(changed))[1:]], ["sale"])
        historical = urlsplit(combined)._replace(fragment="").geturl() + "&chart_start=2026-10-01&chart_end=2026-10-01"
        outside = self.open_page(historical)
        self.assertEqual(self.ranking(outside), [])
        self.assertCountEqual([o["value"] for o in outside.select("#product-tag-ranking select[multiple] option[selected]")], keys)

    def test_partial_tag_authorization_and_invalid_modes_never_widen_exports(self):
        self.grant_export()
        shared = self.item("shared", self.popular, self.sale)
        self.item("keep", self.popular)
        url = self.entry()
        page = self.open_page(url)
        any_url = self.combination(page, url, [self.popular.pk, self.sale.pk], "any")
        all_url = self.combination(page, url, [self.popular.pk, self.sale.pk], "all")
        with patch.object(self.owner, "get_queryset", return_value=Product.objects.exclude(pk=shared.pk)):
            for selected in (any_url, all_url):
                self.assertEqual(self.client.get(selected).status_code, 404)
                denied = self.download(selected)
                self.assertEqual(denied.status_code, 404)
                self.assertNotIn("Content-Disposition", denied)
        self.reader.user_permissions.add(Permission.objects.get(codename="view_tag"))
        tag_admin = self.owner.admin_site.get_model_admin(Tag)
        with patch.object(tag_admin, "get_queryset", return_value=Tag.objects.exclude(pk=self.sale.pk)):
            for selected in (any_url, all_url, url + f"&chart_tag_mode=all&chart_tag=untagged&chart_tag={self.sale.pk}"):
                self.assertEqual(self.download(selected).status_code, 404)
        for suffix in ("&chart_tag_mode=all", "&chart_tag_mode=any&chart_tag=", "&chart_tag=1&chart_tag_mode=bad",
                       "&chart_tag=1&chart_tag_mode=any&chart_tag_mode=all", "&chart_tag_mode=any&chart_tag=1&chart_tag=01"):
            rejected = self.download(url + suffix)
            self.assertEqual(rejected.status_code, 404)
            self.assertNotIn("Content-Disposition", rejected)
        unsigned = urlsplit(url).path + f"?chart_tag_mode=any&chart_tag={self.popular.pk}"
        self.assertEqual(self.client.get(unsigned).status_code, 404)
        self.reader.user_permissions.remove(Permission.objects.get(codename="export_product"))
        self.assertEqual(self.download(all_url).status_code, 403)

    def test_exclusions_share_the_direct_scope_cutoff_permissions_and_export_across_pages(self):
        stop = Tag.objects.create(name="停用", slug="stopped")
        hold = Tag.objects.create(name="待定", slug="on-hold")
        self.item("plain", category=self.root, stamp="2026-10-31T04:00:00+00:00")
        self.item("@both", self.popular, self.sale, category=self.root)
        self.item("first", self.popular, category=self.root, stamp="2026-10-31T04:00:00+00:00")
        self.item("stopped", self.popular, self.sale, stop, category=self.root, stamp="2026-10-31T04:00:02+00:00")
        self.item("on-hold", self.sale, hold, category=self.root, stamp="2026-10-31T04:00:01+00:00")
        self.item("double-blocked", self.popular, self.sale, stop, hold, category=self.root)
        self.item("listed", self.popular, self.sale, category=self.root, status="active")
        self.item("blocked-listed", self.popular, self.sale, stop, hold, category=self.root, status="active")
        self.item("child", self.popular, self.sale, category=self.child)
        self.item("other", self.popular, self.sale)
        self.item("past-cutoff", self.popular, self.sale, category=self.root, stamp="2026-11-01T06:30:00.000001+00:00")
        self.item("before-range", self.popular, self.sale, category=self.root, stamp="2026-10-31T03:59:59.999999+00:00")
        private = self.item("private", self.popular, self.sale, category=self.root)
        keys = [self.popular.pk, self.sale.pk]
        excluded = [str(stop.pk), str(hold.pk)]
        url = self.entry() + "&chart_start=2026-10-31&chart_end=2026-11-01&chart_status=draft"
        # The host join duplicates products and omits the excluded tag assignments.
        with timezone.override(ZoneInfo("Asia/Tokyo")), patch.object(self.owner, "list_per_page", 1), patch.object(
            self.owner, "get_queryset", return_value=Product.objects.filter(Q(tags__in=keys) | Q(tags__isnull=True))
        ), patch.object(self.owner, "has_view_permission", side_effect=lambda req, obj=None: obj != private):
            root_url = urljoin(url, self.open_page(url).find("a", string="灯具")["href"])
            direct = urljoin(root_url, self.open_page(root_url).find("a", string="本级直属商品")["href"])
            branch = self.open_page(direct)
            readonly = self.combination(branch, direct, [], "any", excluded=excluded, exclude_mode="range",
                                        exclude_minimum=1, exclude_maximum=1)
            self.assertIsNone(self.open_page(readonly).select_one('#product-details form, [name="_save"]'))
            self.assertEqual(self.download(readonly).status_code, 403)
            self.grant_export()
            for included, mode, exclude_mode, skus, days, ranking in (
                (keys, "any", None, ["TEXT: @both", "first"], [1, 1], [("人气", 2), ("促销", 1)]),
                (keys, "all", "any", ["TEXT: @both"], [0, 1], [("人气", 1), ("促销", 1)]),
                ([], "any", "any", ["TEXT: @both", "first", "plain"], [2, 1], [("人气", 2), ("促销", 1), ("未打标签", 1)]),
                (keys, "all", "all", ["TEXT: @both", "stopped"], [1, 1], [("人气", 2), ("促销", 2), ("停用", 1)]),
                ([*keys, stop.pk, keys[0]], "at_least", "at_least", ["TEXT: @both", "stopped"], [1, 1],
                 [("人气", 2), ("促销", 2), ("停用", 1)]),
                ([*keys, stop.pk, keys[0]], "range", "range", ["TEXT: @both", "first"], [1, 1],
                 [("人气", 2), ("促销", 1)]),
                (keys, "any", "all", ["TEXT: @both", "stopped", "on-hold", "first"], [3, 1],
                 [("人气", 3), ("促销", 3), ("停用", 1), ("待定", 1)]),
                ([], "any", "all", ["TEXT: @both", "stopped", "on-hold", "first", "plain"], [4, 1],
                 [("人气", 3), ("促销", 3), ("停用", 1), ("待定", 1), ("未打标签", 1)]),
            ):
                with self.subTest(included=included, mode=mode, exclude_mode=exclude_mode):
                    bounds = {
                        "at_least": dict(minimum=2, exclude_minimum=2),
                        "range": dict(minimum=1, maximum=2, exclude_minimum=1, exclude_maximum=1),
                    }.get(mode, {})
                    choice = self.combination(branch, direct, included, mode, excluded=[*excluded, excluded[0]],
                                              exclude_mode=exclude_mode, **bounds)
                    page = self.open_page(choice)
                    self.assertEqual(self.ranking(page), ranking)
                    self.assertEqual([e["value"] for e in page.select('#product-chart-filters [name="chart_tag_exclude"]')], excluded)
                    self.assertEqual(page.select_one('#product-chart-filters [name="chart_tag_exclude_mode"]')["value"], exclude_mode or "any")
                    self.assertEqual(page.select_one('#product-tag-ranking [name="chart_tag_exclude_mode"] option[selected]')["value"], exclude_mode or "any")
                    if mode == "at_least":
                        for name in ("chart_tag_min", "chart_tag_exclude_min"):
                            self.assertEqual(page.select_one(f'#product-chart-filters [name="{name}"]')["value"], "2")
                            self.assertEqual(page.select_one(f'#product-tag-ranking [name="{name}"]')["value"], "2")
                        self.assertEqual(len(page.select('#product-chart-filters [name="chart_tag"]')), 3)
                        self.assertIn("至少命中 2 个", page.select_one("#product-details p").get_text())
                    daily, status = [json.loads(n.string) for n in page.select('.product-analysis-charts [type="application/json"]')]
                    self.assertTrue(all((s["timezone"], s["as_of"]) == (self.zone, self.cutoff) for s in (daily, status)))
                    self.assertEqual([p["value"] for p in daily["points"]], days)
                    self.assertEqual([p["value"] for p in status["points"]], [len(skus), 1, 0])
                    self.assertEqual(page.select_one("#product-details tbody th a").string, "@both")
                    self.assertIn(f"({len(skus)})", page.select_one("#product-details-title").get_text())
                    day = self.chart_link(page, choice, 'a[data-nova-chart-day="2026-11-01"]')
                    active = self.chart_link(self.open_page(day), day, 'a[data-nova-category="active"]')
                    self.assertEqual([r[0] for r in self.csv_rows(self.download(active))[1:]], ["listed"])
                    back = urljoin(choice, page.find("a", string="返回整棵子树")["href"])
                    self.assertCountEqual([r[0] for r in self.csv_rows(self.download(back))[1:]], [*skus, "child"])
                    shortcut = self.tag_url(page, choice, self.sale.pk)
                    shortcut_skus = ["TEXT: @both"] if exclude_mode in (None, "any") else ["TEXT: @both", "stopped", "on-hold"]
                    if mode == "range":
                        shortcut_skus = ["double-blocked", "TEXT: @both"]
                        fields = {"chart_tag_min": "1", "chart_tag_max": "2", "chart_tag_exclude_min": "1", "chart_tag_exclude_max": "1"}
                        for name, value in fields.items():
                            self.assertEqual(page.select_one(f'#product-chart-filters [name="{name}"]')["value"], value)
                            self.assertEqual(page.select_one(f'#product-tag-ranking [name="{name}"]')["value"], value)
                            self.assertEqual(parse_qs(urlsplit(active).query)[name], [value])
                        summary = page.select_one("#product-details p").get_text()
                        self.assertIn("命中 1 到 2 个", summary)
                        self.assertIn("排除标签（恰好命中 1 个）", summary)
                    self.assertEqual([r[0] for r in self.csv_rows(self.download(shortcut))[1:]], shortcut_skus)
                    if len(skus) > 1:
                        second = self.chart_link(page, choice, '#product-details a[rel="next"]')
                        page = self.open_page(second)
                        self.assertEqual(page.select_one("#product-details tbody th a").string, skus[1])
                    export = urljoin(choice, page.select_one("#product-details form")["action"])
                    self.assertEqual(parse_qs(urlsplit(export).query)["chart_tag_exclude"], excluded)
                    self.assertEqual(parse_qs(urlsplit(export).query)["chart_tag_exclude_mode"], [exclude_mode or "any"])
                    if mode == "at_least":
                        self.assertEqual(parse_qs(urlsplit(export).query)["chart_tag_min"], ["2"])
                        self.assertEqual(parse_qs(urlsplit(export).query)["chart_tag_exclude_min"], ["2"])
                    rows = self.csv_rows(self.download(export))
                    self.assertEqual(rows[0], ["SKU", "商品名称", "更新时间 (America/New_York)"])
                    self.assertEqual(rows[1][2], "2026-11-01T01:30:00-05:00")
                    self.assertEqual([r[0] for r in rows[1:]], skus)
                    clear = urljoin(choice, page.find("a", string="清除标签筛选" if included else "清除排除条件")["href"])
                    self.assertEqual(parse_qs(urlsplit(clear).query), parse_qs(urlsplit(direct).query))

    def test_overlapping_and_untagged_exclusions_remain_editable_and_can_be_cleared(self):
        self.grant_export()
        named = Tag.objects.create(name="未打标签", slug="named")
        self.item("plain")
        self.item("a", self.popular)
        self.item("b", self.sale)
        self.item("ab", self.popular, self.sale)
        self.item("named", named)
        url = self.entry()
        initial = self.open_page(url)
        a, b = self.popular.pk, self.sale.pk
        for keys, mode, excluded, skus in (
            ([a, b], "any", [a], ["b"]),
            ([a, b], "all", [a], []),
            ([a, "untagged"], "any", [a, b], ["plain"]),
            ([a, "untagged"], "any", ["untagged"], ["a", "ab"]),
            (["untagged", named.pk, b], "any", ["untagged", b], ["named"]),
            (["untagged"], "all", [named.pk], ["plain"]),
            (["untagged"], "any", ["untagged"], []),
        ):
            with self.subTest(keys=keys, mode=mode, excluded=excluded):
                choice = self.combination(initial, url, keys, mode, excluded=excluded)
                page = self.open_page(choice)
                self.assertCountEqual([row.string for row in page.select("#product-details tbody th a")], skus)
                rows = self.csv_rows(self.download(choice))
                self.assertEqual(rows[0], ["SKU", "商品名称", "更新时间 (America/New_York)"])
                self.assertCountEqual([r[0] for r in rows[1:]], skus)
                if not skus:
                    self.assertEqual(self.ranking(page), [])
                    self.assertIsNone(page.select_one('.product-analysis-charts [type="application/json"]'))
                selected = page.select('#product-tag-ranking [name="chart_tag_exclude"] option[selected]')
                self.assertCountEqual([opt["value"] for opt in selected], map(str, excluded))
                cleared = urljoin(choice, page.find("a", string="清除排除条件")["href"])
                applied = self.combination(page, choice, keys, mode)
                expected = self.combination(initial, url, keys, mode)
                for restored in (cleared, applied):
                    self.assertEqual(parse_qs(urlsplit(restored).query), parse_qs(urlsplit(expected).query))
                self.assertTrue(self.open_page(cleared).select("#product-details tbody tr"))

    def test_exclusion_only_can_remove_untagged_or_all_products_and_restore_the_original_scope(self):
        self.grant_export()
        named = Tag.objects.create(name="未打标签", slug="named")
        self.item("plain")
        self.item("named", named)
        self.item("both", named, self.sale)
        url = self.entry() + "&chart_status=draft"
        initial = self.open_page(url)
        for excluded, skus in (
            ([named.pk], ["plain"]),
            (["untagged"], ["named", "both"]),
            (["untagged", self.sale.pk], ["named"]),
            (["untagged", named.pk], []),
        ):
            with self.subTest(excluded=excluded):
                choice = self.combination(initial, url, [], "all", excluded=excluded)
                page = self.open_page(choice)
                self.assertIsNotNone(page.select_one("#product-tag-ranking details[open]"))
                self.assertIsNone(page.select_one('#product-chart-filters [name="chart_tag"], #product-chart-filters [name="chart_tag_mode"]'))
                self.assertCountEqual([row.string for row in page.select("#product-details tbody th a")], skus)
                self.assertIn("排除标签", page.select_one("#product-details p").get_text())
                if not skus:
                    self.assertEqual(self.ranking(page), [])
                    self.assertIsNone(page.select_one('.product-analysis-charts [type="application/json"]'))
                    self.assertIn("没有可查看的商品", page.select_one("#product-details").get_text())
                export = urljoin(choice, page.select_one("#product-details form")["action"])
                expected_query = {**parse_qs(urlsplit(url).query), "chart_tag_exclude": list(map(str, excluded)),
                                  "chart_tag_exclude_mode": ["any"]}
                self.assertEqual(parse_qs(urlsplit(export).query), expected_query)
                rows = self.csv_rows(self.download(export))
                self.assertEqual(rows[0], ["SKU", "商品名称", "更新时间 (America/New_York)"])
                self.assertCountEqual([row[0] for row in rows[1:]], skus)
                cleared = urljoin(choice, page.find("a", string="清除排除条件")["href"])
                self.assertEqual(parse_qs(urlsplit(cleared).query), parse_qs(urlsplit(url).query))
                empty_form = self.combination(page, choice, [], "all")
                restored = self.open_page(empty_form)
                self.assertCountEqual([row.string for row in restored.select("#product-details tbody th a")], ["plain", "named", "both"])
                self.assertEqual(parse_qs(urlsplit(restored.select_one("#product-details form")["action"]).query), parse_qs(urlsplit(url).query))

    def test_switching_exclusion_rules_handles_untagged_overlaps_and_empty_results(self):
        self.grant_export()
        named = Tag.objects.create(name="未打标签", slug="named")
        self.item("plain")
        self.item("named", named)
        self.item("sale", self.sale)
        self.item("both", named, self.sale)
        url = self.entry()
        page = self.open_page(url)
        current = url
        sale = self.sale.pk
        for keys, mode, excluded, rule, expected in (
            ([], "any", ["untagged", sale], "any", ["named"]),
            ([], "any", ["untagged", sale], "all", ["plain", "named", "sale", "both"]),
            ([], "any", [named.pk, sale], "all", ["plain", "named", "sale"]),
            (["untagged", sale], "any", ["untagged"], "all", ["sale", "both"]),
            ([named.pk, sale], "all", [named.pk, sale], "all", []),
        ):
            with self.subTest(keys=keys, rule=rule, excluded=excluded):
                current = self.combination(page, current, keys, mode, excluded=excluded, exclude_mode=rule)
                page = self.open_page(current)
                details = page.select_one("#product-details")
                summary = "排除标签（匹配全部）" if rule == "all" else "排除标签（匹配任一）"
                self.assertIn(summary, details.p.get_text())
                self.assertCountEqual([a.string for a in details.select("tbody th a")], expected)
                rows = self.csv_rows(self.download(urljoin(current, details.form["action"])))
                self.assertEqual(rows[0], ["SKU", "商品名称", "更新时间 (America/New_York)"])
                self.assertCountEqual([row[0] for row in rows[1:]], expected)
                if not expected:
                    self.assertIn("没有可查看的商品", details.get_text())
                    self.assertFalse(self.ranking(page))
                    self.assertIsNone(page.select_one('.product-analysis-charts [type="application/json"]'))
        # A native GET submits both mode controls when the exclusions are cleared.
        applied = self.combination(page, current, [named.pk, sale], "all", exclude_mode="all")
        cleared = urljoin(current, page.find("a", string="清除排除条件")["href"])
        for target in (applied, cleared):
            restored = self.open_page(target)
            export = urljoin(target, restored.select_one("#product-details form")["action"])
            self.assertNotIn("chart_tag_exclude_mode", parse_qs(urlsplit(export).query))
            self.assertEqual([row[0] for row in self.csv_rows(self.download(export))[1:]], ["both"])

    def test_thresholds_count_distinct_selected_tags_and_untagged_on_either_side(self):
        self.grant_export()
        named = Tag.objects.create(name="未打标签", slug="named")
        extra = Tag.objects.create(name="其他", slug="other")
        self.item("plain")
        self.item("one", self.popular, extra)
        self.item("two", self.popular, self.sale, extra)
        self.item("three", self.popular, self.sale, named)
        self.item("other", extra)
        skus = {"plain", "one", "two", "three", "other"}
        url = self.entry() + "&chart_status=draft"
        initial = self.open_page(url)
        keys = [self.popular.pk, self.sale.pk, named.pk, "untagged", self.sale.pk]
        for n, m, matched in (
            (1, None, skus - {"other"}), (2, None, {"two", "three"}), (3, None, {"three"}), (4, None, set()),
            (0, 0, {"other"}), (0, 1, {"plain", "one", "other"}), (0, 2, skus - {"three"}), (0, 4, skus),
            (1, 1, {"plain", "one"}), (1, 2, {"plain", "one", "two"}), (1, 4, skus - {"other"}),
            (2, 2, {"two"}), (2, 3, {"two", "three"}), (4, 4, set()),
        ):
            rule = "at_least" if m is None else "range"
            include = self.combination(initial, url, keys, rule, minimum=n, maximum=m)
            exclude = self.combination(initial, url, [], "any", excluded=keys, exclude_mode=rule, exclude_minimum=n,
                                       exclude_maximum=m)
            selections = [(include, matched), (exclude, skus - matched)]
            if m is not None:
                outside = self.combination(initial, url, keys, "not_range", minimum=n, maximum=m)
                exclude_outside = self.combination(initial, url, [], "any", excluded=keys, exclude_mode="not_range",
                                                   exclude_minimum=n, exclude_maximum=m)
                selections.extend([(outside, skus - matched), (exclude_outside, matched)])
            if n == 0:
                selections.extend([
                    (self.combination(initial, url, keys, "at_most", maximum=m), matched),
                    (self.combination(initial, url, [], "any", excluded=keys, exclude_mode="at_most", exclude_maximum=m),
                     skus - matched),
                ])
            if n == m:
                selections.extend([
                    (self.combination(initial, url, keys, "exact", minimum=n), matched),
                    (self.combination(initial, url, [], "any", excluded=keys, exclude_mode="exact", exclude_minimum=n),
                     skus - matched),
                    (self.combination(initial, url, keys, "not_exact", minimum=n), skus - matched),
                    (self.combination(initial, url, [], "any", excluded=keys, exclude_mode="not_exact", exclude_minimum=n),
                     matched),
                ])
            for selection, expected in selections:
                with self.subTest(n=n, m=m, selection=selection):
                    page = self.open_page(selection)
                    self.assertCountEqual([row.string for row in page.select("#product-details tbody th a")], expected)
                    export = urljoin(selection, page.select_one("#product-details form")["action"])
                    rows = self.csv_rows(self.download(export))
                    self.assertEqual(rows[0], ["SKU", "商品名称", "更新时间 (America/New_York)"])
                    self.assertCountEqual([row[0] for row in rows[1:]], expected)
                    if not expected:
                        self.assertFalse(self.ranking(page))
                        self.assertIsNone(page.select_one('.product-analysis-charts [type="application/json"]'))
                        self.assertIn("没有可查看的商品", page.select_one("#product-details").get_text())

        for selected_keys, zero_hits in (
            ([self.sale.pk], {"plain", "one", "other"}),
            (["untagged"], skus - {"plain"}),
            ([self.sale.pk, "untagged"], {"one", "other"}),
        ):
            with self.subTest(zero_hits=selected_keys):
                include = self.combination(initial, url, selected_keys, "range", minimum=0, maximum=0)
                exclude = self.combination(initial, url, [], "any", excluded=selected_keys, exclude_mode="range",
                                           exclude_minimum=0, exclude_maximum=0)
                for target, expected in ((include, zero_hits), (exclude, skus - zero_hits)):
                    self.assertCountEqual([r[0] for r in self.csv_rows(self.download(target))[1:]], expected)

        empty = self.combination(initial, url, [], "any", excluded=[*keys, extra.pk], exclude_mode="range",
                                 exclude_minimum=1, exclude_maximum=4)
        self.assertFalse(self.ranking(self.open_page(empty)))
        self.assertEqual(self.csv_rows(self.download(empty)), [["SKU", "商品名称", "更新时间 (America/New_York)"]])

        both = self.combination(initial, url, keys, "at_least", minimum=2,
                                excluded=keys, exclude_mode="at_least", exclude_minimum=3)
        result = self.open_page(both)
        self.assertEqual([r[0] for r in self.csv_rows(self.download(both))[1:]], ["two"])
        clear = urljoin(both, result.find("a", string="清除排除条件")["href"])
        self.assertEqual(parse_qs(urlsplit(clear).query)["chart_tag_min"], ["2"])
        self.assertNotIn("chart_tag_exclude_min", parse_qs(urlsplit(clear).query))
        self.assertCountEqual([r[0] for r in self.csv_rows(self.download(clear))[1:]], ["two", "three"])
        # A plain HTML form switching back to "any" still submits its old number fields.
        switched = self.combination(result, both, [named.pk], "any", minimum=2, exclude_mode="any", exclude_minimum=3)
        export = self.open_page(switched).select_one("#product-details form")["action"]
        self.assertNotIn("chart_tag_min", parse_qs(urlsplit(export).query))
        self.assertNotIn("chart_tag_exclude_min", parse_qs(urlsplit(export).query))
        self.assertEqual([r[0] for r in self.csv_rows(self.download(urljoin(switched, export)))[1:]], ["three"])

        combined = self.combination(initial, url, keys, "range", minimum=2, maximum=3,
                                    excluded=keys, exclude_mode="range", exclude_minimum=1, exclude_maximum=2)
        result = self.open_page(combined)
        self.assertEqual([r[0] for r in self.csv_rows(self.download(combined))[1:]], ["three"])
        clear = urljoin(combined, result.find("a", string="清除排除条件")["href"])
        query = parse_qs(urlsplit(clear).query)
        self.assertEqual((query["chart_tag_min"], query["chart_tag_max"]), (["2"], ["3"]))
        self.assertNotIn("chart_tag_exclude_max", query)
        self.assertCountEqual([r[0] for r in self.csv_rows(self.download(clear))[1:]], ["two", "three"])
        # Non-JS form submission can retain both numeric inputs after switching modes.
        changed = self.combination(result, combined, keys, "at_least", minimum=1, maximum=2,
                                   excluded=[named.pk], exclude_mode="any", exclude_minimum=1, exclude_maximum=2)
        export = self.open_page(changed).select_one("#product-details form")["action"]
        query = parse_qs(urlsplit(export).query)
        self.assertEqual(query["chart_tag_min"], ["1"])
        self.assertFalse({"chart_tag_max", "chart_tag_exclude_min", "chart_tag_exclude_max"} & query.keys())
        self.assertCountEqual([r[0] for r in self.csv_rows(self.download(urljoin(changed, export)))[1:]], ["plain", "one", "two"])

    def test_exact_and_not_exact_with_only_named_tags(self):
        self.grant_export()
        extra = Tag.objects.create(name="其他", slug="other")
        self.item("plain")
        self.item("other", extra)
        self.item("one", self.sale, extra)
        self.item("both", self.sale, self.popular, extra)
        url = self.entry()
        page = self.open_page(url)
        keys = [self.sale.pk, self.popular.pk, self.sale.pk]
        for n, included, excluded in (
            (0, ["plain", "other"], ["one", "both"]),
            (2, ["both"], ["plain", "other", "one"]),
        ):
            keep = self.combination(page, url, keys, "exact", minimum=n)
            omit = self.combination(page, url, [], "any", excluded=keys, exclude_mode="exact", exclude_minimum=n)
            keep_others = self.combination(page, url, keys, "not_exact", minimum=n)
            omit_others = self.combination(page, url, [], "any", excluded=keys, exclude_mode="not_exact", exclude_minimum=n)
            for target, expected in ((keep, included), (omit, excluded), (keep_others, excluded), (omit_others, included)):
                with self.subTest(target=target):
                    self.assertCountEqual([r[0] for r in self.csv_rows(self.download(target))[1:]], expected)

    def test_overlapping_not_exact_rules_show_empty_results_and_require_export_permission(self):
        self.item("tagged", self.sale)
        self.item("plain")
        url = self.entry()
        tags = [self.sale.pk]
        target = self.combination(self.open_page(url), url, tags, "not_exact", minimum=0,
                                  excluded=tags, exclude_mode="not_exact", exclude_minimum=0)
        page = self.open_page(target)
        self.assertIn("没有可查看的商品", page.select_one("#product-details").get_text())
        self.assertFalse(self.ranking(page))
        self.assertIsNone(page.select_one('.product-analysis-charts [type="application/json"]'))
        self.assertIsNone(page.select_one("#product-details form"))
        self.assertEqual(self.download(target).status_code, 403)

        self.grant_export()
        export = self.open_page(target).select_one("#product-details form")["action"]
        self.assertEqual(self.csv_rows(self.download(urljoin(target, export))), [["SKU", "商品名称", "更新时间 (America/New_York)"]])
        clear = urljoin(target, page.find("a", string="清除排除条件")["href"])
        self.assertEqual([r[0] for r in self.csv_rows(self.download(clear))[1:]], ["tagged"])

    def test_zero_matches_share_the_signed_window_direct_category_permissions_and_csv(self):
        extra = Tag.objects.create(name="其他", slug="other")
        self.item("plain", category=self.root)
        self.item("sale", self.sale, extra, category=self.root, stamp="2026-10-31T04:00:00+00:00")
        self.item("selected", self.popular, self.sale, category=self.root)
        self.item("other-only", extra, category=self.root)
        self.item("listed", self.sale, category=self.root, status="active")
        self.item("child", self.sale, category=self.child)
        self.item("outside")
        self.item("late", category=self.root, stamp="2026-11-01T06:30:00.000001+00:00")
        self.item("early", category=self.root, stamp="2026-10-31T03:59:59.999999+00:00")
        private = self.item("private", category=self.root)
        url = self.entry() + "&chart_start=2026-10-31&chart_end=2026-11-01&chart_status=draft"
        # This scope can duplicate "sale" and hide "selected"'s popular-tag assignment.
        visible = Product.objects.filter(Q(tags__in=[extra, self.sale]) | Q(tags__isnull=True))
        with timezone.override(ZoneInfo("Asia/Tokyo")), patch.object(self.owner, "list_per_page", 1), patch.object(
            self.owner, "get_queryset", return_value=visible
        ), patch.object(self.owner, "has_view_permission", side_effect=lambda req, obj=None: obj != private):
            subtree = urljoin(url, self.open_page(url).find("a", string="灯具")["href"])
            direct = urljoin(subtree, self.open_page(subtree).find("a", string="本级直属商品")["href"])
            # Neither survivor has the popular tag. Each has either the sale tag or no assignments.
            selected = self.combination(self.open_page(direct), direct, [self.popular.pk], "range", minimum=0, maximum=0,
                                        excluded=[self.sale.pk, "untagged"], exclude_mode="range", exclude_minimum=0, exclude_maximum=0)
            page = self.open_page(selected)
            self.assertEqual(self.ranking(page), [("促销", 1), ("其他", 1), ("未打标签", 1)])
            self.assertEqual(page.select_one("#product-details tbody th a").string, "plain")
            self.assertIsNone(page.select_one('#product-details form, [name="_save"]'))
            self.assertEqual(self.download(selected).status_code, 403)
            fields = ("chart_tag_min", "chart_tag_max", "chart_tag_exclude_min", "chart_tag_exclude_max")
            for name in fields:
                for scope in ("#product-chart-filters", "#product-tag-ranking"):
                    self.assertEqual(page.select_one(f'{scope} input[name="{name}"]')["value"], "0")
            for scope in ("#product-tag-ranking p", "#product-details p"):
                self.assertEqual(page.select_one(scope).get_text().count("恰好命中 0 个"), 2)
            daily, status = [json.loads(n.string) for n in page.select('.product-analysis-charts [type="application/json"]')]
            self.assertTrue(all((s["timezone"], s["as_of"]) == (self.zone, self.cutoff) for s in (daily, status)))
            self.assertEqual([p["value"] for p in daily["points"]], [1, 1])
            self.assertEqual([p["value"] for p in status["points"]], [2, 1, 0])

            self.grant_export()
            second = self.chart_link(page, selected, '#product-details a[rel="next"]')
            next_page = self.open_page(second)
            self.assertEqual(next_page.select_one("#product-details tbody th a").string, "sale")
            export = urljoin(second, next_page.select_one("#product-details form")["action"])
            for name in fields:
                self.assertEqual(parse_qs(urlsplit(export).query)[name], ["0"])
            rows = self.csv_rows(self.download(export))
            self.assertEqual(rows[0], ["SKU", "商品名称", "更新时间 (America/New_York)"])
            self.assertEqual([(r[0], r[2]) for r in rows[1:]], [
                ("plain", "2026-11-01T01:30:00-05:00"), ("sale", "2026-10-31T00:00:00-04:00"),
            ])
            day = self.chart_link(page, selected, 'a[data-nova-chart-day="2026-11-01"]')
            listed = self.chart_link(self.open_page(day), day, 'a[data-nova-category="active"]')
            self.assertEqual([r[0] for r in self.csv_rows(self.download(listed))[1:]], ["listed"])
            back = urljoin(selected, page.find("a", string="返回整棵子树")["href"])
            self.assertCountEqual([r[0] for r in self.csv_rows(self.download(back))[1:]], ["child", "plain", "sale"])
            clear = urljoin(selected, page.find("a", string="清除排除条件")["href"])
            self.assertCountEqual([r[0] for r in self.csv_rows(self.download(clear))[1:]], ["plain", "sale", "other-only"])

    def test_equal_outside_bounds_match_not_exact_and_survive_tag_drilldown(self):
        self.grant_export()
        self.item("plain")
        self.item("sale", self.sale)
        self.item("popular", self.popular)
        self.item("both", self.popular, self.sale)
        url = self.entry()
        initial = self.open_page(url)
        included, excluded = [self.sale.pk, self.popular.pk], [self.sale.pk, "untagged"]
        outside = self.combination(initial, url, included, "not_range", minimum=0, maximum=0,
                                   excluded=excluded, exclude_mode="not_range", exclude_minimum=1, exclude_maximum=1)
        not_exact = self.combination(initial, url, included, "not_exact", minimum=0,
                                     excluded=excluded, exclude_mode="not_exact", exclude_minimum=1)
        rows = self.csv_rows(self.download(outside))
        self.assertCountEqual([row[0] for row in rows[1:]], ["sale", "both"])
        self.assertEqual(rows, self.csv_rows(self.download(not_exact)))
        page = self.open_page(outside)
        self.assertEqual(self.ranking(page), self.ranking(self.open_page(not_exact)))
        summary = page.select_one("#product-details p").get_text()
        self.assertIn("命中标签数不等于 0", summary)
        self.assertIn("排除标签（命中标签数不等于 1）", summary)

        # A ranking link replaces the inclusion and carries both bounds of the exclusion.
        drilled = self.tag_url(page, outside, self.popular.pk)
        query = parse_qs(urlsplit(drilled).query)
        self.assertNotIn("chart_tag_min", query)
        self.assertNotIn("chart_tag_max", query)
        self.assertEqual(query["chart_tag_exclude_mode"], ["not_range"])
        self.assertEqual(query["chart_tag_exclude_min"], ["1"])
        self.assertEqual(query["chart_tag_exclude_max"], ["1"])
        self.assertEqual([row[0] for row in self.csv_rows(self.download(drilled))[1:]], ["both"])

    def test_count_sets_and_their_complements_on_either_side(self):
        self.grant_export()
        third = Tag.objects.create(name="第三", slug="third")
        fourth = Tag.objects.create(name="第四", slug="fourth")
        other = Tag.objects.create(name="其他", slug="other")
        tags = [self.popular, self.sale, third, fourth]
        for n in range(5):
            self.item(f"n{n}", *tags[:n])
        self.item("other", other)
        keys = [tag.pk for tag in tags] + [self.sale.pk]
        all_skus = {"n0", "n1", "n2", "n3", "n4", "other"}
        url = self.entry()
        initial = self.open_page(url)
        for selected, values, matches in (
            (keys, [4, 0, 2, 2], {"n0", "n2", "n4", "other"}),
            (keys, [1, 3], {"n1", "n3"}),
            ([*keys, "untagged"], [4, 0, 2], {"n2", "n4", "other"}),
            ([*keys, "untagged"], [0, 1], {"n0", "n1", "other"}),
            (["untagged"], [1], {"n0"}),
            (["untagged"], [0], all_skus - {"n0"}),
            (["untagged"], [0, 1], all_skus),
            ([*keys, "untagged"], [5], set()),
        ):
            include = self.combination(initial, url, selected, "one_of", counts=values)
            exclude = self.combination(initial, url, [], "any", excluded=selected, exclude_mode="one_of", exclude_counts=values)
            include_others = self.combination(initial, url, selected, "not_one_of", counts=values)
            exclude_others = self.combination(initial, url, [], "any", excluded=selected,
                                              exclude_mode="not_one_of", exclude_counts=values)
            others = all_skus - matches
            for target, expected in ((include, matches), (exclude, others), (include_others, others), (exclude_others, matches)):
                with self.subTest(target=target):
                    page = self.open_page(target)
                    if values == [4, 0, 2, 2]:
                        rank = ({"人气": 2, "促销": 2, "第三": 1, "第四": 1, "其他": 1, "未打标签": 1}
                                if expected == matches else {"人气": 2, "促销": 1, "第三": 1})
                        self.assertEqual(dict(self.ranking(page)), rank)
                        daily, status = [json.loads(n.string) for n in page.select('.product-analysis-charts [type="application/json"]')]
                        self.assertEqual(daily["points"][-1]["value"], len(expected))
                        self.assertEqual([p["value"] for p in status["points"]], [len(expected), 0, 0])
                    self.assertCountEqual([a.string for a in page.select("#product-details tbody th a")], expected)
                    export = urljoin(target, page.select_one("#product-details form")["action"])
                    rows = self.csv_rows(self.download(export))
                    self.assertEqual(rows[0], ["SKU", "商品名称", "更新时间 (America/New_York)"])
                    self.assertCountEqual([row[0] for row in rows[1:]], expected)
                    if not expected:
                        self.assertFalse(self.ranking(page))
                        self.assertIsNone(page.select_one('.product-analysis-charts [type="application/json"]'))
                        self.assertIn("没有可查看的商品", page.select_one("#product-details").get_text())

    def test_range_unions_include_endpoints_preserve_gaps_and_merge_overlaps(self):
        self.grant_export()
        tags = [self.popular, self.sale, Tag.objects.create(name="第三", slug="third"),
                Tag.objects.create(name="第四", slug="fourth")]
        for n in range(5):
            self.item(f"n{n}", *tags[:n])
        self.item("other", Tag.objects.create(name="其他", slug="other"))
        keys = [tag.pk for tag in tags] + [self.sale.pk]
        all_skus = {"n0", "n1", "n2", "n3", "n4", "other"}
        entry = self.entry()
        initial = self.open_page(entry)
        for selected, intervals, canonical, matches in (
            (keys, "3 到 4、0-1，3-3", "0-1, 3-4", all_skus - {"n2"}),
            (keys, "1-2, 3-4, 2-3, 1-2", "1-4", {"n1", "n2", "n3", "n4"}),
            (keys, "0-0, 2-2", "0-0, 2-2", {"n0", "other", "n2"}),
            ([*keys, "untagged"], "0-0, 2-2", "0-0, 2-2", {"other", "n2"}),
            (["untagged"], "1-1", "1-1", {"n0"}),
            (keys, "0-4", "0-4", all_skus),
            ([*keys, "untagged"], "5-5", "5-5", set()),
        ):
            include = self.combination(initial, entry, selected, "any_range", ranges=intervals)
            exclude = self.combination(initial, entry, [], "any", excluded=selected, exclude_mode="any_range", exclude_ranges=intervals)
            include_outside = self.combination(initial, entry, selected, "not_any_range", ranges=intervals)
            exclude_outside = self.combination(initial, entry, [], "any", excluded=selected,
                                               exclude_mode="not_any_range", exclude_ranges=intervals)
            outside = all_skus - matches
            for target, expected, field in (
                (include, matches, "chart_tag_ranges"), (exclude, outside, "chart_tag_exclude_ranges"),
                (include_outside, outside, "chart_tag_ranges"), (exclude_outside, matches, "chart_tag_exclude_ranges"),
            ):
                with self.subTest(target=target):
                    page = self.open_page(target)
                    self.assertCountEqual([a.string for a in page.select("#product-details tbody th a")], expected)
                    export = urljoin(target, page.select_one("#product-details form")["action"])
                    self.assertEqual(parse_qs(urlsplit(export).query)[field], [canonical])
                    rows = self.csv_rows(self.download(export))
                    self.assertEqual(rows[0], ["SKU", "商品名称", "更新时间 (America/New_York)"])
                    self.assertCountEqual([row[0] for row in rows[1:]], expected)
                    if canonical == "0-1, 3-4":
                        rank = ({"人气": 3, "促销": 2, "第三": 2, "第四": 1, "其他": 1, "未打标签": 1}
                                if expected == matches else {"人气": 1, "促销": 1})
                        self.assertEqual(dict(self.ranking(page)), rank)
                        daily, status = [json.loads(n.string) for n in page.select('.product-analysis-charts [type="application/json"]')]
                        self.assertEqual(daily["points"][-1]["value"], len(expected))
                        self.assertEqual([p["value"] for p in status["points"]], [len(expected), 0, 0])
                    if not expected:
                        self.assertFalse(self.ranking(page))
                        self.assertIsNone(page.select_one('.product-analysis-charts [type="application/json"]'))
                        self.assertIn("没有可查看的商品", page.select_one("#product-details").get_text())

    def test_positive_and_negated_ranges_can_be_combined_and_cleared_independently(self):
        self.grant_export()
        self.item("plain")
        self.item("single", self.sale)
        self.item("both", self.sale, self.popular)
        keys = [self.sale.pk, self.popular.pk]
        entry = self.entry()
        initial = self.open_page(entry)
        for inclusion, exclusion, restored in (
            ("any_range", "not_any_range", ["plain", "both"]),
            ("not_any_range", "any_range", ["single"]),
        ):
            with self.subTest(inclusion=inclusion, exclusion=exclusion):
                target = self.combination(initial, entry, keys, inclusion, ranges="0-0,2-2",
                                          excluded=keys, exclude_mode=exclusion, exclude_ranges="1-1")
                page = self.open_page(target)
                self.assertFalse(self.ranking(page))
                self.assertIsNone(page.select_one('#product-details tbody tr, .product-analysis-charts [type="application/json"]'))
                export = urljoin(target, page.select_one("#product-details form")["action"])
                self.assertEqual(self.csv_rows(self.download(export)), [["SKU", "商品名称", "更新时间 (America/New_York)"]])
                clear = urljoin(target, page.find("a", string="清除排除条件")["href"])
                self.assertCountEqual([row[0] for row in self.csv_rows(self.download(clear))[1:]], restored)

    def test_mixed_counts_and_ranges_match_each_product_once(self):
        self.grant_export()
        tags = [Tag.objects.create(name=f"t{i}", slug=f"tag-{i}") for i in range(1, 7)]
        for n in range(7):
            self.item(f"n{n}", *tags[:n])
        self.item("other", Tag.objects.create(name="其他", slug="other"))
        keys = [tag.pk for tag in tags] + [tags[0].pk]
        entry = self.entry()
        initial = self.open_page(entry)
        inside = (["n0", "n2", "n3", "n4", "n6", "other"],
                  {"t1": 4, "t2": 4, "t3": 3, "t4": 2, "t5": 1, "t6": 1, "其他": 1, "未打标签": 1})
        outside = (["n1", "n5"], {"t1": 2, "t2": 1, "t3": 1, "t4": 1, "t5": 1})
        for expression, (mode, include_result, exclude_result) in product(
            ("0、2 到 4、6", "6，3、2-3, 0, 3 到 4, 6-6, 2"),
            (("values_or_ranges", inside, outside), ("not_values_or_ranges", outside, inside)),
        ):
            include = self.combination(initial, entry, keys, mode, ranges=expression)
            exclude = self.combination(initial, entry, [], "any", excluded=keys,
                                       exclude_mode=mode, exclude_ranges=expression)
            for url, side, (expected, ranking) in (
                (include, "chart_tag", include_result), (exclude, "chart_tag_exclude", exclude_result),
            ):
                with self.subTest(side=side, mode=mode, expression=expression):
                    page = self.open_page(url)
                    self.assertEqual(dict(self.ranking(page)), ranking)
                    daily, status = [json.loads(n.string) for n in page.select('.product-analysis-charts [type="application/json"]')]
                    self.assertEqual(daily["points"][-1]["value"], len(expected))
                    self.assertEqual([p["value"] for p in status["points"]], [len(expected), 0, 0])
                    self.assertCountEqual([a.string for a in page.select("#product-details tbody th a")], expected)
                    export = urljoin(url, page.select_one("#product-details form")["action"])
                    query = parse_qs(urlsplit(export).query)
                    self.assertEqual(query[side + "_mode"], [mode])
                    self.assertEqual(query[side + "_ranges"], ["0, 2-4, 6"])
                    self.assertEqual(query[side], [str(tag.pk) for tag in tags])
                    self.assertCountEqual([row[0] for row in self.csv_rows(self.download(export))[1:]], expected)

        # An untagged product hits the explicit untagged choice once. A product with only other tags still hits zero.
        selected = self.combination(initial, entry, [*keys, "untagged"], "values_or_ranges", ranges="0")
        self.assertEqual([row[0] for row in self.csv_rows(self.download(selected))[1:]], ["other"])
        empty = self.combination(initial, entry, keys, "values_or_ranges", ranges="0、2 到 4、6",
                                 excluded=keys, exclude_mode="values_or_ranges", exclude_ranges="0-6")
        page = self.open_page(empty)
        self.assertFalse(self.ranking(page))
        self.assertIsNone(page.select_one('#product-details tbody tr, .product-analysis-charts [type="application/json"]'))
        self.assertIn("没有可查看的商品", page.select_one("#product-details").get_text())
        export = urljoin(empty, page.select_one("#product-details form")["action"])
        self.assertEqual(self.csv_rows(self.download(export)), [["SKU", "商品名称", "更新时间 (America/New_York)"]])

    def test_mixed_ranges_share_results_and_keep_open_ends(self):
        self.grant_export()
        tags = [Tag.objects.create(name=f"t{i}", slug=f"tag-{i}") for i in range(1, 8)]
        for n in range(8):
            self.item(f"n{n}", *tags[:n])
        self.item("other", Tag.objects.create(name="其他", slug="other"))
        keys = [tag.pk for tag in tags]
        entry = self.entry()
        initial = self.open_page(entry)
        all_counts = set(range(8))
        for expression, canonical, hits in (
            ("0、2 到 4、6 及以上", "0, 2-4, >=6", {0, 2, 3, 4, 6, 7}),
            ("至少 6 个、2、至多 1 个、1-3、7 及以上", "<=3, >=6", {0, 1, 2, 3, 6, 7}),
            ("0 及以下、≥7", "<=0, >=7", {0, 7}),
            ("<=4, 4 及以上", ">=0", all_counts),
            ("少于 2 个、3 到 4、多于 5 个", "<2, 3-4, >5", {0, 1, 3, 4, 6, 7}),
            ("至少 6 个、0、至多 1 个、少于3、3 到 4、3、>5", "<3, 3-4, >5", {0, 1, 2, 3, 4, 6, 7}),
            ("<3、>3", "<3, >3", all_counts - {3}),
            ("多于 0 个", ">0", all_counts - {0}),
            ("少于 7 个", "<7", all_counts - {7}),
            ("<0", "<0", set()),
            (">7", ">7", set()),
            ("(2,5)", "(2,5)", {3, 4}),
            ("[2,5)", "[2,5)", {2, 3, 4}),
            ("(2,5]", "(2,5]", {3, 4, 5}),
            ("0、(1,4]，[6,7)", "0, (1,4], [6,7)", {0, 2, 3, 4, 6}),
            ("［0，2）、(1,4],3-5,3,至少 7 个", "[0,2), (1,5], >=7", {0, 1, 2, 3, 4, 5, 7}),
            ("（0，3］、[2,5),2,>5", "(0,5), >5", {1, 2, 3, 4, 6, 7}),
            ("(2,3)", "(2,3)", set()),
            ("(4,4)", "(4,4)", set()),
            ("[0,0)", "[0,0)", set()),
            ("(7,7]", "(7,7]", set()),
            ("[7,7]", "7", {7}),
            ("[2,2), (3,3), 5", "5", {5}),
            ("(,3)", "<3", {0, 1, 2}),
            ("(,3]", "<=3", {0, 1, 2, 3}),
            ("(3,)", ">3", {4, 5, 6, 7}),
            ("[3,)", ">=3", {3, 4, 5, 6, 7}),
            ("(,0)", "<0", set()),
            ("(7,)", ">7", set()),
            ("(,0], [7,)", "<=0, >=7", {0, 7}),
            ("(,7)", "<7", all_counts - {7}),
            ("(0,)", ">0", all_counts - {0}),
            ("(,2),1-3,（，2］、3,［6，）", "<=3, >=6", {0, 1, 2, 3, 6, 7}),
            ("0,(2,4],(3,),[6,)", "0, >2", {0, 3, 4, 5, 6, 7}),
            ("(,4]，[4,)", ">=0", all_counts),
            ("(,)", ">=0", all_counts),
            ("0,(1,4],(,),[6,)", ">=0", all_counts),
            ("（ ， ）、(,0), (7,), (,)", ">=0", all_counts),
        ):
            repeated = [*keys, keys[0]]
            include = self.combination(initial, entry, repeated, "values_or_ranges", ranges=expression)
            exclude = self.combination(initial, entry, [], "any", excluded=repeated,
                                       exclude_mode="values_or_ranges", exclude_ranges=expression)
            for url, side, counts in ((include, "chart_tag", hits), (exclude, "chart_tag_exclude", all_counts - hits)):
                with self.subTest(side=side, expression=expression):
                    page = self.open_page(url)
                    expected = [f"n{n}" for n in counts]
                    # Product nK carries the first K tags. The unrelated tag and untagged product both hit zero.
                    ranking = {tag.name: sum(n >= i for n in counts) for i, tag in enumerate(tags, 1)}
                    if 0 in counts:
                        expected.append("other")
                        ranking.update({"其他": 1, "未打标签": 1})
                    self.assertEqual(dict(self.ranking(page)), {name: total for name, total in ranking.items() if total})
                    self.assertCountEqual([a.string for a in page.select("#product-details tbody th a")], expected)
                    charts = page.select('.product-analysis-charts [type="application/json"]')
                    if expected:
                        daily, status = [json.loads(node.string) for node in charts]
                        self.assertEqual(daily["points"][-1]["value"], len(expected))
                        self.assertEqual([p["value"] for p in status["points"]], [len(expected), 0, 0])
                    else:
                        self.assertFalse(charts)
                        self.assertIn("没有可查看的商品", page.select_one("#product-details").get_text())
                    export = urljoin(url, page.select_one("#product-details form")["action"])
                    query = parse_qs(urlsplit(export).query)
                    self.assertEqual(query[side + "_ranges"], [canonical])
                    self.assertEqual(query[side], list(map(str, keys)))
                    rows = self.csv_rows(self.download(export))
                    self.assertEqual(rows[0], ["SKU", "商品名称", "更新时间 (America/New_York)"])
                    self.assertCountEqual([row[0] for row in rows[1:]], expected)

        # Reapplying a saved lower bound after adding a seventh tag must still include n7.
        six = self.combination(initial, entry, keys[:6], "values_or_ranges", ranges="[6,)")
        page = self.open_page(six)
        saved = page.select_one('#product-tag-ranking input[name="chart_tag_ranges"]')["value"]
        self.assertEqual(saved, ">=6")
        seven = self.combination(page, six, keys, "values_or_ranges", ranges=saved)
        self.assertCountEqual([row[0] for row in self.csv_rows(self.download(seven))[1:]], ["n6", "n7"])
        six = self.combination(initial, entry, keys[:6], "values_or_ranges", ranges="(6,)")
        page = self.open_page(six)
        self.assertIsNone(page.select_one("#product-details tbody tr"))
        saved = page.select_one('#product-tag-ranking input[name="chart_tag_ranges"]')["value"]
        self.assertEqual(saved, ">6")
        seven = self.combination(page, six, keys, "values_or_ranges", ranges=saved)
        self.assertEqual([row[0] for row in self.csv_rows(self.download(seven))[1:]], ["n7"])

    def test_negated_mixed_rules_with_untagged_and_empty_results(self):
        self.grant_export()
        self.item("plain")
        self.item("one", self.sale)
        self.item("two", self.sale, self.popular)
        self.item("other", Tag.objects.create(name="其他", slug="other"))
        keys = [self.popular.pk, self.sale.pk]
        entry = self.entry()
        initial = self.open_page(entry)
        for selected, expression, expected in (
            (keys, "1, 2-2", ["plain", "other"]),
            ([*keys, "untagged"], "1, 2-3", ["other"]),
            ([*keys, "untagged"], "0, 2-3", ["plain", "one"]),
            ([*keys, "untagged"], "≤0、至少 2 个", ["plain", "one"]),
            (keys, "至少 0 个", []),
            (keys, "至多 2 个", []),
            ([*keys, "untagged"], "少于1、多于1", ["plain", "one"]),
            (keys, "<0、>2", ["plain", "one", "two", "other"]),
            ([*keys, "untagged"], "(0,2)", ["other", "two"]),
            (keys, "[0,1)", ["one", "two"]),
            (keys, "(1,1)", ["plain", "one", "two", "other"]),
            ([*keys, "untagged"], "(,0], (1,)", ["plain", "one"]),
            (keys, "(,0), (2,)", ["plain", "one", "two", "other"]),
            ([*keys, "untagged"], "0, (,)", []),
        ):
            with self.subTest(selected=selected, expression=expression):
                url = self.combination(initial, entry, selected, "not_values_or_ranges", ranges=expression)
                self.assertCountEqual([row[0] for row in self.csv_rows(self.download(url))[1:]], expected)

        # Excluding the complement of all counts leaves the inclusion rule in effect.
        url = self.combination(initial, entry, keys, "values_or_ranges", ranges="1",
                               excluded=keys, exclude_mode="not_values_or_ranges", exclude_ranges="(,)")
        self.assertEqual([row[0] for row in self.csv_rows(self.download(url))[1:]], ["one"])

        for include, exclude, restored in (
            ("values_or_ranges", "not_values_or_ranges", ["plain", "other", "two"]),
            ("not_values_or_ranges", "values_or_ranges", ["one"]),
        ):
            with self.subTest(include=include, exclude=exclude):
                url = self.combination(initial, entry, keys, include, ranges="0, 2-2",
                                       excluded=keys, exclude_mode=exclude, exclude_ranges="1")
                page = self.open_page(url)
                self.assertFalse(self.ranking(page))
                self.assertIsNone(page.select_one('#product-details tbody tr, .product-analysis-charts [type="application/json"]'))
                self.assertIn("没有可查看的商品", page.select_one("#product-details").get_text())
                export = urljoin(url, page.select_one("#product-details form")["action"])
                self.assertEqual(self.csv_rows(self.download(export)), [["SKU", "商品名称", "更新时间 (America/New_York)"]])
                clear = urljoin(url, page.find("a", string="清除排除条件")["href"])
                self.assertCountEqual([row[0] for row in self.csv_rows(self.download(clear))[1:]], restored)

    def test_invalid_range_unions_reject_the_entire_view_and_export(self):
        self.grant_export()
        self.item("both", self.popular, self.sale)
        entry = self.entry()
        modes = ("any_range", "not_any_range", "values_or_ranges", "not_values_or_ranges")
        for side, rule in product(("chart_tag", "chart_tag_exclude"), modes):
            field = side + "_ranges"
            tags = [(side, self.popular.pk), (side, self.sale.pk), (side, self.popular.pk)]
            mode = (side + "_mode", rule)
            invalid = [[], [""], ["0-1,2-3"], ["-1-0"], ["2-1"], ["0-1,"], ["00-1"],
                       ["0-0，1.5-2"], ["0-1", "1-2"], ["0-" + "9" * 100],
                       ["0-1,3"], ["0、1 到 3"], ["0,-1"], ["1,01"], ["0,,2"], ["1.5,0-1"],
                       ["至少 0 个、至多 3 个"], ["0,3 及以上"], ["至多 -1 个"], [">=01"], ["1.5 及以下"],
                       ["至少"], ["至多 1 及以上"], [">=1-2"], ["少于"], ["< -1"], ["多于 01 个"],
                       ["≤2, 少于3"], ["0,>3"], ["多于1.5个"], ["<<1"], [">>2"], ["少于 1 及以上"],
                       ["0,[0,3)"], ["(2,1]"], ["(1,2"], ["1,2)"], ["[0,1,2)"], ["[,)"], ["[,]"], ["(,]"],
                       ["(,),3"], ["(3,), (,)"], ["(,),2-1"], ["(,),"], ["(,,)"],
                       ["[,1]"], ["[,1)"], ["(1,]"], ["[1,]"], ["(,3]"], ["[3,)"], ["(,01)"],
                       ["(,-1]"], ["[0,), (1,,)"], ["(,1][2,)"], ["(,0),,"],
                       ["([0,2))"], ["0(1,2]"], ["(0,1][1,2)"], ["(0,2),"], ["[00,1)"], ["(-1,2]"]]
            if rule in ("any_range", "not_any_range"):
                invalid.extend((["1"], ["至少 1 个"], ["1 及以下"], ["<1"], ["多于 1 个"], ["(1,2]"], ["(,1]"], ["(1,)"], ["(,)"]))
            for values in invalid:
                with self.subTest(side=side, rule=rule, values=values):
                    url = entry + "&" + urlencode([*tags, mode, *((field, v) for v in values)])
                    self.assertEqual(self.client.get(url).status_code, 404)
                    response = self.download(url)
                    self.assertEqual(response.status_code, 404)
                    self.assertNotIn("Content-Disposition", response)
            for params in ([mode, (field, "0-0")], [*tags, (field, "0-1")]):
                url = entry + "&" + urlencode(params)
                self.assertEqual(self.client.get(url).status_code, 404)
                self.assertEqual(self.download(url).status_code, 404)
            for params in ([*tags, mode, (field, "0-1"), (side + "_counts", "1")],
                           [*tags, (side + "_mode", "any"), (field, "0-1")]):
                self.assertEqual(self.download(entry + "&" + urlencode(params)).status_code, 404)
            unsigned = urlsplit(entry).path + "?" + urlencode([*tags, mode, (field, "0-1")])
            self.assertEqual(self.download(unsigned).status_code, 404)

    def test_mixed_count_set_modes_can_be_cleared_from_an_empty_result(self):
        self.item("plain")
        self.item("single", self.sale)
        self.item("both", self.sale, self.popular)
        keys = [self.sale.pk, self.popular.pk]
        entry = self.entry()
        target = self.combination(self.open_page(entry), entry, keys, "not_one_of", counts=[2, 0, 2],
                                  excluded=keys, exclude_mode="one_of", exclude_counts=[1])
        page = self.open_page(target)
        self.assertFalse(self.ranking(page))
        self.assertIn("没有可查看的商品", page.select_one("#product-details").get_text())
        self.assertIsNone(page.select_one('#product-details form, .product-analysis-charts [type="application/json"]'))
        self.assertEqual(self.download(target).status_code, 403)
        self.grant_export()
        export = self.open_page(target).select_one("#product-details form")["action"]
        self.assertEqual(self.csv_rows(self.download(urljoin(target, export))), [["SKU", "商品名称", "更新时间 (America/New_York)"]])
        clear = urljoin(target, page.find("a", string="清除排除条件")["href"])
        self.assertEqual([row[0] for row in self.csv_rows(self.download(clear))[1:]], ["single"])

    def test_invalid_count_sets_are_rejected_for_view_and_export(self):
        self.grant_export()
        self.item("both", self.popular, self.sale)
        entry = self.entry()
        for side, rule in product(("chart_tag", "chart_tag_exclude"), ("one_of", "not_one_of")):
            tags = [(side, self.popular.pk), (side, self.sale.pk), (side, self.sale.pk)]
            mode = (side + "_mode", rule)
            counts = side + "_counts"
            for values in ([], [""], ["-1"], ["1.5"], ["０"], ["01"], ["0", "3"], ["9" * 100]):
                with self.subTest(side=side, rule=rule, values=values):
                    target = entry + "&" + urlencode([*tags, mode, *((counts, n) for n in values)])
                    self.assertEqual(self.client.get(target).status_code, 404)
                    response = self.download(target)
                    self.assertEqual(response.status_code, 404)
                    self.assertNotIn("Content-Disposition", response)
            for params in ([mode, (counts, "0")], [*tags, (counts, "1")]):
                target = entry + "&" + urlencode(params)
                self.assertEqual(self.client.get(target).status_code, 404)
                self.assertEqual(self.download(target).status_code, 404)
            for params in ([*tags, mode, (counts, "1"), (side + "_min", "1")],
                           [*tags, (side + "_mode", "any"), (counts, "0")]):
                self.assertEqual(self.download(entry + "&" + urlencode(params)).status_code, 404)
            unsigned = urlsplit(entry).path + "?" + urlencode([*tags, mode, (counts, "2")])
            self.assertEqual(self.download(unsigned).status_code, 404)

    def test_bad_range_bounds_are_rejected_for_view_and_export(self):
        self.grant_export()
        self.item("both", self.popular, self.sale)
        entry = self.entry()
        for side, rule in product(("chart_tag", "chart_tag_exclude"), ("range", "not_range")):
            tags = [(side, self.popular.pk), (side, self.sale.pk), (side, self.sale.pk)]
            lower, upper = side + "_min", side + "_max"
            mode = (side + "_mode", rule)
            for lows, highs in (
                ([], ["2"]), (["1"], []), (["00"], ["2"]), (["-1"], ["0"]), (["1"], ["0"]), (["2"], ["1"]),
                (["0"], []), ([], ["0"]), (["0"], ["00"]), (["0", "0"], ["0"]), (["0"], ["0", "0"]),
                (["1"], ["3"]), (["1"], ["-1"]), (["1"], ["１"]), (["1"], ["1.5"]), (["1"], [""]),
                (["1"], ["02"]), (["1"], ["9" * 100]), (["1", "1"], ["2"]), (["1"], ["2", "2"]),
            ):
                with self.subTest(side=side, rule=rule, lows=lows, highs=highs):
                    bounds = [(lower, n) for n in lows] + [(upper, m) for m in highs]
                    url = entry + "&" + urlencode([*tags, mode, *bounds])
                    self.assertEqual(self.client.get(url).status_code, 404)
                    response = self.download(url)
                    self.assertEqual(response.status_code, 404)
                    self.assertNotIn("Content-Disposition", response)
            for params in ([mode, (lower, 0), (upper, 0)], [mode, (lower, 1), (upper, 1)], [*tags, (upper, 1)],
                           [*tags, (side + "_mode", "at_least"), (lower, 1), (upper, 2)]):
                self.assertEqual(self.download(entry + "&" + urlencode(params)).status_code, 404)
            unsigned = urlsplit(entry).path + "?" + urlencode([*tags, mode, (lower, 1), (upper, 2)])
            self.assertEqual(self.client.get(unsigned).status_code, 404)

    def test_count_rules_share_the_scope_through_charts_paging_and_csv(self):
        self.item("plain", category=self.root)
        self.item("sale", self.sale, category=self.root, stamp="2026-10-31T04:00:00+00:00")
        self.item("both", self.popular, self.sale, category=self.root)
        self.item("popular", self.popular, category=self.root)
        self.item("listed", self.sale, category=self.root, status="active")
        self.item("child", self.sale, category=self.child)
        self.item("outside")
        self.item("late", category=self.root, stamp="2026-11-01T06:30:00.000001+00:00")
        self.item("early", category=self.root, stamp="2026-10-31T03:59:59.999999+00:00")
        private = self.item("private", category=self.root)
        entry = self.entry() + "&chart_start=2026-10-31&chart_end=2026-11-01&chart_status=draft"
        # The host tag join can return two rows for "both".
        included = [self.popular.pk, self.sale.pk, self.sale.pk]
        excluded = [self.sale.pk, "untagged"]
        visible = Product.objects.filter(Q(tags__in=included) | Q(tags__isnull=True))
        with timezone.override(ZoneInfo("Asia/Tokyo")), patch.object(self.owner, "list_per_page", 1), patch.object(
            self.owner, "get_queryset", return_value=visible
        ), patch.object(self.owner, "has_view_permission", side_effect=lambda req, obj=None: obj != private):
            subtree = urljoin(entry, self.open_page(entry).find("a", string="灯具")["href"])
            direct = urljoin(subtree, self.open_page(subtree).find("a", string="本级直属商品")["href"])
            initial = self.open_page(direct)
            # A native form without JS also sends inactive bounds left over from range mode.
            at_most = self.combination(initial, direct, included, "at_most", minimum=2, maximum=1,
                                       excluded=excluded, exclude_mode="at_most", exclude_minimum=1, exclude_maximum=0)
            bounded = self.combination(initial, direct, included, "range", minimum=0, maximum=1,
                                       excluded=excluded, exclude_mode="range", exclude_minimum=0, exclude_maximum=0)
            # Including the untagged option gives "plain" one match, just like "sale".
            exact_keys = [*included, "untagged"]
            exact = self.combination(initial, direct, exact_keys, "exact", minimum=1, maximum=2,
                                     excluded=excluded, exclude_mode="exact", exclude_minimum=0, exclude_maximum=1)
            equal_bounds = self.combination(initial, direct, exact_keys, "range", minimum=1, maximum=1,
                                            excluded=excluded, exclude_mode="range", exclude_minimum=0, exclude_maximum=0)
            # Swapping the two sides and negating both rules gives the same visible products.
            not_exact = self.combination(initial, direct, excluded, "not_exact", minimum=0, maximum=1,
                                         excluded=exact_keys, exclude_mode="not_exact", exclude_minimum=1, exclude_maximum=2)
            # Outside 2..3 drops "both". Excluding outside 1..2 also drops "popular".
            outside = self.combination(initial, direct, exact_keys, "not_range", minimum=2, maximum=3,
                                       excluded=excluded, exclude_mode="not_range", exclude_minimum=1, exclude_maximum=2)
            count_set = self.combination(initial, direct, included, "one_of", counts=[1, 0, 1], minimum=2, maximum=2,
                                         excluded=excluded, exclude_mode="one_of", exclude_counts=[2, 0, 2])
            not_count_set = self.combination(initial, direct, excluded, "not_one_of", counts=[2, 0, 2], minimum=1, maximum=2,
                                             excluded=included, exclude_mode="not_one_of", exclude_counts=[1, 0, 1])
            range_union = self.combination(initial, direct, included, "any_range", ranges="1-1, 0-1", counts=[0], minimum=2,
                                           excluded=excluded, exclude_mode="any_range", exclude_ranges="2-2, 0-0")
            outside_union = self.combination(initial, direct, excluded, "not_any_range", ranges="2-2, 0-0", counts=[1],
                                             excluded=included, exclude_mode="not_any_range", exclude_ranges="1-1, 0-1")
            mixed = self.combination(initial, direct, included, "values_or_ranges", ranges="1, [0,2)", counts=[2], minimum=2,
                                     excluded=excluded, exclude_mode="values_or_ranges", exclude_ranges="(1,2]、0")
            not_mixed = self.combination(initial, direct, excluded, "not_values_or_ranges", ranges="(1,2]、0", counts=[1],
                                         excluded=included, exclude_mode="not_values_or_ranges", exclude_ranges="1, [0,2)")
            unbounded = self.combination(initial, direct, included, "values_or_ranges", ranges="(,2),1",
                                         excluded=excluded, exclude_mode="values_or_ranges", exclude_ranges="(1,),0")
            summaries = {
                at_most: ("最多命中 1 个", "最多命中 0 个", ("_max",)),
                exact: ("恰好命中 1 个", "恰好命中 0 个", ("_min",)),
                not_exact: ("命中标签数不等于 0", "命中标签数不等于 1", ("_min",)),
                outside: ("命中标签数不在 2 到 3 之间", "命中标签数不在 1 到 2 之间", ("_min", "_max")),
                count_set: ("命中标签数为指定值之一（0, 1）", "命中标签数为指定值之一（0, 2）", ()),
                not_count_set: ("命中标签数不在指定值中（0, 2）", "命中标签数不在指定值中（0, 1）", ()),
                range_union: ("命中标签数落在任一指定区间（0-1）", "命中标签数落在任一指定区间（0-0, 2-2）", ()),
                outside_union: ("命中标签数不在任何指定区间（0-0, 2-2）", "命中标签数不在任何指定区间（0-1）", ()),
                mixed: ("命中指定值或范围（[0,2)）", "命中指定值或范围（0, (1,2]）", ()),
                unbounded: ("命中指定值或范围（<2）", "命中指定值或范围（0, >1）", ()),
                not_mixed: ("命中标签数不在指定值或范围中（0, (1,2]）", "命中标签数不在指定值或范围中（[0,2)）", ()),
            }
            for target in summaries:
                self.assertIsNone(self.open_page(target).select_one('#product-details form, [name="_save"]'))
                self.assertEqual(self.download(target).status_code, 403)
            self.grant_export()
            # A universal tag rule must still respect the signed window, hosting admin and direct category.
            all_counts = self.combination(initial, direct, included, "values_or_ranges", ranges="1,(,),[1,2]")
            page = self.open_page(all_counts)
            self.assertEqual(dict(self.ranking(page)), {"促销": 2, "人气": 2, "未打标签": 1})
            daily, status = [json.loads(n.string) for n in page.select('.product-analysis-charts [type="application/json"]')]
            self.assertTrue(all((s["timezone"], s["as_of"]) == (self.zone, self.cutoff) for s in (daily, status)))
            self.assertEqual([p["value"] for p in daily["points"]], [1, 3])
            self.assertEqual([p["value"] for p in status["points"]], [4, 1, 0])
            export = urljoin(all_counts, page.select_one("#product-details form")["action"])
            self.assertCountEqual([row[0] for row in self.csv_rows(self.download(export))[1:]], ["plain", "sale", "both", "popular"])
            for target in (*summaries, bounded, equal_bounds):
                with self.subTest(target=target):
                    page = self.open_page(target)
                    self.assertEqual(self.ranking(page), [("促销", 1), ("未打标签", 1)])
                    daily, status = [json.loads(n.string) for n in page.select('.product-analysis-charts [type="application/json"]')]
                    self.assertTrue(all((s["timezone"], s["as_of"]) == (self.zone, self.cutoff) for s in (daily, status)))
                    self.assertEqual([p["value"] for p in daily["points"]], [1, 1])
                    self.assertEqual([p["value"] for p in status["points"]], [2, 1, 0])
                    self.assertEqual(page.select_one("#product-details tbody th a").string, "plain")
                    next_page = self.open_page(self.chart_link(page, target, '#product-details a[rel="next"]'))
                    self.assertEqual(next_page.select_one("#product-details tbody th a").string, "sale")
                    export = urljoin(target, next_page.select_one("#product-details form")["action"])
                    self.assertEqual(self.csv_rows(self.download(export)), [
                        ["SKU", "商品名称", "更新时间 (America/New_York)"],
                        ["plain", "plain", "2026-11-01T01:30:00-05:00"],
                        ["sale", "sale", "2026-10-31T00:00:00-04:00"],
                    ])
                    day = self.chart_link(page, target, 'a[data-nova-chart-day="2026-11-01"]')
                    active = self.chart_link(self.open_page(day), day, 'a[data-nova-category="active"]')
                    self.assertEqual([r[0] for r in self.csv_rows(self.download(active))[1:]], ["listed"])
                    back = urljoin(target, page.find("a", string="返回整棵子树")["href"])
                    self.assertCountEqual([r[0] for r in self.csv_rows(self.download(back))[1:]], ["plain", "sale", "child"])
                    if target in summaries:
                        submitted = parse_qs(urlsplit(target).query)
                        mode = submitted["chart_tag_mode"][0]
                        inclusion, exclusion, active_bounds = summaries[target]
                        query = parse_qs(urlsplit(export).query)
                        for name in ("chart_tag", "chart_tag_exclude"):
                            self.assertEqual(query[name], list(dict.fromkeys(submitted[name])))
                            for suffix in ("_min", "_max"):
                                field = name + suffix
                                control = page.select_one(f'#product-chart-filters [name="{field}"]')
                                if suffix in active_bounds:
                                    self.assertEqual(query[field], submitted[field])
                                    self.assertEqual(control["value"], submitted[field][0])
                                else:
                                    self.assertNotIn(field, query)
                                    self.assertIsNone(control)
                            self.assertEqual(query[name + "_mode"], [mode])
                            self.assertEqual(page.select_one(f'#product-tag-ranking [name="{name}_mode"] option[selected]')["value"], mode)
                            if mode in ("one_of", "not_one_of"):
                                field = name + "_counts"
                                expected = sorted(set(submitted[field]), key=int)
                                self.assertEqual(query[field], expected)
                                for selector in (f'#product-chart-filters input[name="{field}"]',
                                                 f'#product-tag-ranking [name="{field}"] option[selected]'):
                                    self.assertEqual([n["value"] for n in page.select(selector)], expected)
                            if mode in ("any_range", "not_any_range", "values_or_ranges", "not_values_or_ranges"):
                                field = name + "_ranges"
                                expected = {"1-1, 0-1": "0-1", "2-2, 0-0": "0-0, 2-2",
                                            "1, [0,2)": "[0,2)", "(1,2]、0": "0, (1,2]",
                                            "(,2),1": "<2", "(1,),0": "0, >1"}[submitted[field][0]]
                                self.assertEqual(query[field], [expected])
                                self.assertNotIn(name + "_counts", query)
                                for form in ("#product-chart-filters", "#product-tag-ranking"):
                                    self.assertEqual(page.select_one(f'{form} input[name="{field}"]')["value"], expected)
                        for selector in ("#product-details p", "#product-tag-ranking p"):
                            summary = page.select_one(selector).get_text()
                            self.assertIn(inclusion, summary)
                            self.assertIn(f"排除标签（{exclusion}）", summary)
                        clear = urljoin(target, page.find("a", string="清除排除条件")["href"])
                        restored = "both" if target in (not_exact, not_count_set, outside_union, not_mixed) else "popular"
                        self.assertCountEqual([r[0] for r in self.csv_rows(self.download(clear))[1:]], ["plain", "sale", restored])
                        if target in (count_set, not_count_set, range_union, outside_union, mixed, not_mixed, unbounded):
                            suffix = "_counts" if target in (count_set, not_count_set) else "_ranges"
                            self.assertNotIn("chart_tag_exclude" + suffix, parse_qs(urlsplit(clear).query))
                            drilled = self.tag_url(page, target, self.sale.pk)
                            drill_query = parse_qs(urlsplit(drilled).query)
                            self.assertNotIn("chart_tag" + suffix, drill_query)
                            self.assertEqual(drill_query["chart_tag_exclude_mode"], [mode])
                            self.assertEqual(drill_query["chart_tag_exclude" + suffix], query["chart_tag_exclude" + suffix])
                            remaining = ["sale"] if target in (not_count_set, outside_union, not_mixed) else ["sale", "both"]
                            self.assertCountEqual([r[0] for r in self.csv_rows(self.download(drilled))[1:]], remaining)

    def test_invalid_or_duplicated_thresholds_never_produce_a_download(self):
        self.grant_export()
        self.item("both", self.popular, self.sale)
        url = self.entry()
        for side in ("chart_tag", "chart_tag_exclude"):
            tags = [(side, self.popular.pk), (side, self.sale.pk), (side, self.sale.pk)]
            for rule in ("at_least", "at_most", "exact", "not_exact"):
                count = side + ("_max" if rule == "at_most" else "_min")
                mode = (side + "_mode", rule)
                invalid = [[], [""], ["-1"], ["01"], ["1.5"], ["３"], ["3"], ["9" * 100], ["2", "2"]]
                if rule == "at_least":
                    invalid.append(["0"])
                for values in invalid:
                    with self.subTest(side=side, rule=rule, values=values):
                        selection = url + "&" + urlencode([*tags, mode, *((count, value) for value in values)])
                        self.assertEqual(self.client.get(selection).status_code, 404)
                        response = self.download(selection)
                        self.assertEqual(response.status_code, 404)
                        self.assertNotIn("Content-Disposition", response)
                for params in ([mode, (count, "1")], [*tags, (count, "1")], [*tags, (side + "_mode", "any"), (count, "2")]):
                    self.assertEqual(self.download(url + "&" + urlencode(params)).status_code, 404)
                unsigned = urlsplit(url).path + "?" + urlencode([*tags, mode, (count, "2")])
                self.assertEqual(self.client.get(unsigned).status_code, 404)
            extra_lower = [*tags, (side + "_mode", "at_most"), (side + "_min", "1"), (side + "_max", "2")]
            self.assertEqual(self.download(url + "&" + urlencode(extra_lower)).status_code, 404)
            for rule in ("exact", "not_exact"):
                extra_upper = [*tags, (side + "_mode", rule), (side + "_min", "1"), (side + "_max", "2")]
                self.assertEqual(self.download(url + "&" + urlencode(extra_upper)).status_code, 404)

    def test_unreadable_exclusions_and_malformed_coordinates_never_broaden_an_export(self):
        self.grant_export()
        self.item("visible", self.popular)
        private = self.item("label-source", self.sale)
        self.item("plain")
        url = self.entry()
        branch = self.open_page(url)
        choice = self.combination(branch, url, [self.popular.pk], "any", excluded=[self.sale.pk])
        only_excluded = self.combination(branch, url, [], "any", excluded=[self.sale.pk])
        impossible = self.combination(branch, url, [self.popular.pk, "untagged"], "all", excluded=[self.sale.pk])
        exclude_all = self.combination(branch, url, [], "any", excluded=[self.sale.pk, "untagged"], exclude_mode="all")
        included_threshold = self.combination(branch, url, [self.popular.pk, self.sale.pk], "at_least", minimum=1)
        excluded_threshold = self.combination(branch, url, [], "any", excluded=[self.sale.pk, "untagged"],
                                              exclude_mode="at_least", exclude_minimum=2)
        included_range = self.combination(branch, url, [self.popular.pk, self.sale.pk], "range", minimum=1, maximum=1)
        excluded_range = self.combination(branch, url, [], "any", excluded=[self.sale.pk, "untagged"],
                                          exclude_mode="range", exclude_minimum=2, exclude_maximum=2)
        zero_include = self.combination(branch, url, [self.popular.pk, self.sale.pk], "range", minimum=0, maximum=0)
        zero_exclude = self.combination(branch, url, [], "any", excluded=[self.sale.pk, "untagged"],
                                        exclude_mode="range", exclude_minimum=0, exclude_maximum=2)
        cap_include = self.combination(branch, url, [self.popular.pk, self.sale.pk], "at_most", maximum=2)
        cap_exclude = self.combination(branch, url, [], "any", excluded=[self.sale.pk, "untagged"],
                                       exclude_mode="at_most", exclude_maximum=0)
        exact_include = self.combination(branch, url, [self.popular.pk, self.sale.pk], "exact", minimum=0)
        exact_exclude = self.combination(branch, url, [], "any", excluded=[self.sale.pk], exclude_mode="exact", exclude_minimum=1)
        not_exact_include = self.combination(branch, url, [self.sale.pk], "not_exact", minimum=0)
        not_exact_exclude = self.combination(branch, url, [], "any", excluded=[self.sale.pk], exclude_mode="not_exact", exclude_minimum=1)
        outside_include = self.combination(branch, url, [self.sale.pk, self.popular.pk], "not_range", minimum=0, maximum=1)
        outside_exclude = self.combination(branch, url, [], "any", excluded=[self.sale.pk, "untagged"],
                                           exclude_mode="not_range", exclude_minimum=0, exclude_maximum=1)
        set_include = self.combination(branch, url, [self.sale.pk], "one_of", counts=[0, 1])
        set_exclude = self.combination(branch, url, [], "any", excluded=[self.sale.pk], exclude_mode="one_of", exclude_counts=[0])
        not_set_include = self.combination(branch, url, [self.sale.pk], "not_one_of", counts=[1])
        not_set_exclude = self.combination(branch, url, [], "any", excluded=[self.sale.pk],
                                           exclude_mode="not_one_of", exclude_counts=[0, 1])
        union_include = self.combination(branch, url, [self.sale.pk, self.popular.pk], "any_range", ranges="0-0,2-2")
        union_exclude = self.combination(branch, url, [], "any", excluded=[self.sale.pk, "untagged"],
                                         exclude_mode="any_range", exclude_ranges="0-0,2-2")
        outside_union_include = self.combination(branch, url, [self.sale.pk, self.popular.pk], "not_any_range", ranges="0-0,2-2")
        outside_union_exclude = self.combination(branch, url, [], "any", excluded=[self.sale.pk, "untagged"],
                                                 exclude_mode="not_any_range", exclude_ranges="0-0,2-2")
        mixed_include = self.combination(branch, url, [self.sale.pk, self.popular.pk], "values_or_ranges", ranges="(0,1)")
        mixed_exclude = self.combination(branch, url, [], "any", excluded=[self.sale.pk, "untagged"],
                                         exclude_mode="values_or_ranges", exclude_ranges="[2,2)")
        unbounded_include = self.combination(branch, url, [self.sale.pk], "values_or_ranges", ranges="(1,)")
        unbounded_exclude = self.combination(branch, url, [], "any", excluded=[self.sale.pk],
                                             exclude_mode="values_or_ranges", exclude_ranges="(,0)")
        any_count_include = self.combination(branch, url, [self.sale.pk], "values_or_ranges", ranges="0,(,)")
        any_count_exclude = self.combination(branch, url, [], "any", excluded=[self.sale.pk],
                                             exclude_mode="values_or_ranges", exclude_ranges="(,)")
        not_mixed_include = self.combination(branch, url, [self.sale.pk, self.popular.pk], "not_values_or_ranges", ranges="0,1-2")
        not_mixed_exclude = self.combination(branch, url, [], "any", excluded=[self.sale.pk, "untagged"],
                                             exclude_mode="not_values_or_ranges", exclude_ranges="0,1-2")
        self.assertEqual(self.download(choice).status_code, 200)
        self.reader.user_permissions.add(Permission.objects.get(codename="view_tag"))
        tag_admin = self.owner.admin_site.get_model_admin(Tag)
        for restriction in (
            patch.object(self.owner, "get_queryset", return_value=Product.objects.exclude(pk=private.pk)),
            patch.object(tag_admin, "get_queryset", return_value=Tag.objects.exclude(pk=self.sale.pk)),
        ):
            with restriction:
                for selection in (choice, impossible, only_excluded, exclude_all, included_threshold, excluded_threshold,
                                  included_range, excluded_range, zero_include, zero_exclude, cap_include, cap_exclude,
                                  exact_include, exact_exclude, not_exact_include, not_exact_exclude,
                                  outside_include, outside_exclude, set_include, set_exclude, not_set_include, not_set_exclude,
                                  union_include, union_exclude, outside_union_include, outside_union_exclude,
                                  mixed_include, mixed_exclude, unbounded_include, unbounded_exclude,
                                  any_count_include, any_count_exclude, not_mixed_include, not_mixed_exclude):
                    self.assertEqual(self.client.get(selection).status_code, 404)
                    denied = self.download(selection)
                    self.assertEqual(denied.status_code, 404)
                    self.assertNotIn("Content-Disposition", denied)
        base = urlsplit(choice)._replace(fragment="").geturl()
        for invalid in ("", "0", "01", "unknown", "9223372036854775808"):
            self.assertEqual(self.download(base + "&chart_tag_exclude=" + invalid).status_code, 404)
        for invalid in ("", "other", "all&chart_tag_exclude_mode=any", "all&chart_tag_exclude_mode=all"):
            target = base + "&chart_tag_exclude_mode=" + invalid
            self.assertEqual(self.client.get(target).status_code, 404)
            rejected = self.download(target)
            self.assertEqual(rejected.status_code, 404)
            self.assertNotIn("Content-Disposition", rejected)
        self.assertEqual(self.download(url + "&chart_tag_exclude_mode=all").status_code, 404)
        unsigned = urlsplit(url).path + f"?chart_tag_mode=any&chart_tag={self.popular.pk}&chart_tag_exclude=untagged"
        self.assertEqual(self.client.get(unsigned).status_code, 404)
        with patch.object(self.owner, "get_exclude", return_value=["tags"]):
            self.assertEqual(self.download(choice).status_code, 403)
            self.assertEqual(self.download(only_excluded).status_code, 403)
            self.assertEqual(self.client.get(only_excluded).status_code, 403)
        with patch.object(self.owner, "get_exclude", side_effect=lambda req, obj=None: ["tags"] if obj and obj.sku == "plain" else []):
            self.assertEqual([row[0] for row in self.csv_rows(self.download(only_excluded))[1:]], ["visible"])
            self.assertEqual([row.string for row in self.open_page(only_excluded).select("#product-details tbody th a")], ["visible"])
        self.assertEqual(self.download(urlsplit(url).path + "?chart_tag_exclude=untagged").status_code, 404)
        self.reader.user_permissions.remove(Permission.objects.get(codename="export_product"))
        self.assertEqual(self.download(choice).status_code, 403)
        self.assertEqual(self.download(exclude_all).status_code, 403)
        self.assertEqual(self.download(excluded_threshold).status_code, 403)
        self.assertEqual(self.download(included_range).status_code, 403)
        self.assertEqual(self.download(excluded_range).status_code, 403)
        self.assertEqual(self.download(zero_include).status_code, 403)
        self.assertEqual(self.download(zero_exclude).status_code, 403)
        self.assertEqual(self.download(cap_include).status_code, 403)
        self.assertEqual(self.download(cap_exclude).status_code, 403)
        self.assertEqual(self.download(exact_include).status_code, 403)
        self.assertEqual(self.download(exact_exclude).status_code, 403)
        self.assertEqual(self.download(not_exact_include).status_code, 403)
        self.assertEqual(self.download(not_exact_exclude).status_code, 403)
        self.assertEqual(self.download(outside_include).status_code, 403)
        self.assertEqual(self.download(outside_exclude).status_code, 403)
        self.assertEqual(self.download(set_include).status_code, 403)
        self.assertEqual(self.download(set_exclude).status_code, 403)
        self.assertEqual(self.download(not_set_include).status_code, 403)
        self.assertEqual(self.download(not_set_exclude).status_code, 403)
        self.assertEqual(self.download(union_include).status_code, 403)
        self.assertEqual(self.download(union_exclude).status_code, 403)
        self.assertEqual(self.download(outside_union_include).status_code, 403)
        self.assertEqual(self.download(outside_union_exclude).status_code, 403)
        self.assertEqual(self.download(mixed_include).status_code, 403)
        self.assertEqual(self.download(mixed_exclude).status_code, 403)
        self.assertEqual(self.download(unbounded_include).status_code, 403)
        self.assertEqual(self.download(unbounded_exclude).status_code, 403)
        self.assertEqual(self.download(any_count_include).status_code, 403)
        self.assertEqual(self.download(any_count_exclude).status_code, 403)
        self.assertEqual(self.download(not_mixed_include).status_code, 403)
        self.assertEqual(self.download(not_mixed_exclude).status_code, 403)

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
