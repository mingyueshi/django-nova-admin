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

    def combination(self, page, current, keys, mode, *, excluded=(), exclude_mode=None,
                    minimum=None, maximum=None, exclude_minimum=None, exclude_maximum=None):
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
                field = form.select_one(f'input[name="{parameter}"][type="number"][min="1"]')
                params.append((field["name"], str(value)))
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
            (1, 1, {"plain", "one"}), (1, 2, {"plain", "one", "two"}), (1, 4, skus - {"other"}),
            (2, 2, {"two"}), (2, 3, {"two", "three"}), (4, 4, set()),
        ):
            rule = "at_least" if m is None else "range"
            include = self.combination(initial, url, keys, rule, minimum=n, maximum=m)
            exclude = self.combination(initial, url, [], "any", excluded=keys, exclude_mode=rule, exclude_minimum=n,
                                       exclude_maximum=m)
            for selection, expected in ((include, matched), (exclude, skus - matched)):
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

    def test_bad_range_bounds_are_rejected_for_view_and_export(self):
        self.grant_export()
        self.item("both", self.popular, self.sale)
        entry = self.entry()
        for side in ("chart_tag", "chart_tag_exclude"):
            tags = [(side, self.popular.pk), (side, self.sale.pk), (side, self.sale.pk)]
            lower, upper = side + "_min", side + "_max"
            mode = (side + "_mode", "range")
            for lows, highs in (
                ([], ["2"]), (["1"], []), (["0"], ["2"]), (["1"], ["0"]), (["2"], ["1"]),
                (["1"], ["3"]), (["1"], ["-1"]), (["1"], ["１"]), (["1"], ["1.5"]), (["1"], [""]),
                (["1"], ["02"]), (["1"], ["9" * 100]), (["1", "1"], ["2"]), (["1"], ["2", "2"]),
            ):
                with self.subTest(side=side, lows=lows, highs=highs):
                    bounds = [(lower, n) for n in lows] + [(upper, m) for m in highs]
                    url = entry + "&" + urlencode([*tags, mode, *bounds])
                    self.assertEqual(self.client.get(url).status_code, 404)
                    response = self.download(url)
                    self.assertEqual(response.status_code, 404)
                    self.assertNotIn("Content-Disposition", response)
            for params in ([mode, (lower, 1), (upper, 1)], [*tags, (upper, 1)],
                           [*tags, (side + "_mode", "at_least"), (lower, 1), (upper, 2)]):
                self.assertEqual(self.download(entry + "&" + urlencode(params)).status_code, 404)
            unsigned = urlsplit(entry).path + "?" + urlencode([*tags, mode, (lower, 1), (upper, 2)])
            self.assertEqual(self.client.get(unsigned).status_code, 404)

    def test_invalid_or_duplicated_thresholds_never_produce_a_download(self):
        self.grant_export()
        self.item("both", self.popular, self.sale)
        url = self.entry()
        for side in ("chart_tag", "chart_tag_exclude"):
            count = side + "_min"
            tags = [(side, self.popular.pk), (side, self.sale.pk), (side, self.sale.pk)]
            mode = (side + "_mode", "at_least")
            for values in ([], [""], ["0"], ["-1"], ["01"], ["1.5"], ["３"], ["3"], ["9" * 100], ["2", "2"]):
                with self.subTest(side=side, values=values):
                    selection = url + "&" + urlencode([*tags, mode, *((count, value) for value in values)])
                    self.assertEqual(self.client.get(selection).status_code, 404)
                    response = self.download(selection)
                    self.assertEqual(response.status_code, 404)
                    self.assertNotIn("Content-Disposition", response)
            for params in ([mode, (count, "1")], [*tags, (count, "1")], [*tags, (side + "_mode", "any"), (count, "2")]):
                self.assertEqual(self.download(url + "&" + urlencode(params)).status_code, 404)
            unsigned = urlsplit(url).path + "?" + urlencode([*tags, mode, (count, "2")])
            self.assertEqual(self.client.get(unsigned).status_code, 404)

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
        self.assertEqual(self.download(choice).status_code, 200)
        self.reader.user_permissions.add(Permission.objects.get(codename="view_tag"))
        tag_admin = self.owner.admin_site.get_model_admin(Tag)
        for restriction in (
            patch.object(self.owner, "get_queryset", return_value=Product.objects.exclude(pk=private.pk)),
            patch.object(tag_admin, "get_queryset", return_value=Tag.objects.exclude(pk=self.sale.pk)),
        ):
            with restriction:
                for selection in (choice, impossible, only_excluded, exclude_all, included_threshold, excluded_threshold,
                                  included_range, excluded_range):
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
