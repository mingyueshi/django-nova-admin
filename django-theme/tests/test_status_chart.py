import json
from datetime import timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from bs4 import BeautifulSoup
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import DatabaseError
from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from catalog.models import Product, Tag
from nova_admin.charts import validate_category_snapshot, validate_daily_snapshot
from nova_admin.preferences import SESSION_KEY


class CategorySnapshotTests(SimpleTestCase):
    def setUp(self):
        self.point = {"key": "draft", "label": "<草稿>", "value": 0}
        self.snapshot = {
            "schema_version": 1, "metric": "catalog.products_by_status", "dimension": "category",
            "as_of": "2026-11-19T12:00:00Z", "timezone": "Asia/Shanghai", "state": "ready",
            "points": [self.point, {"key": "active", "label": "已上架", "value": None}],
        }

    def test_common_version_and_category_bounds(self):
        self.assertIs(validate_category_snapshot(self.snapshot), self.snapshot)
        with self.assertRaises(ValueError):
            validate_daily_snapshot(self.snapshot)
        invalid = [
            {"schema_version": 2}, {"schema_version": True}, {"dimension": "daily"}, {"timezone": "bad/zone"},
            {"as_of": "2026-11-19"}, {"start": "2026-11-19"}, {"state": "error"}, {"points": []},
            {"points": [self.point] * 2}, {"points": [dict(self.point, key=f"s{i}") for i in range(65)]},
        ]
        for changes in ({"key": "../"}, {"key": []}, {"label": " "}, {"url": "/"},
                        *({"value": v} for v in (True, None, -1, 1.5, 2**53, "1"))):
            invalid.append({"points": [{**self.point, **changes}]})
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_category_snapshot({**self.snapshot, **changes})

    def test_table_handles_missing_counts_and_invalid_versions(self):
        def render(snapshot):
            return BeautifulSoup(render_to_string("project_admin/product_status_chart.html", {
                "chart_title": "状态", "chart_snapshot": snapshot, "status_chart": {"list_url": "/items/"},
            }), "html.parser")

        page = render(self.snapshot)
        self.assertEqual(page.table.a.get_text(), "<草稿>")
        self.assertEqual(len(page.table.select("a")), 1)
        self.assertEqual([cell.get_text(strip=True) for cell in page.select("td")], ["0", "暂无数据"])
        self.assertEqual(json.loads(page.select_one('[type="application/json"]').string), self.snapshot)
        bad = render({**self.snapshot, "schema_version": 2})
        self.assertIn("刷新重试", bad.get_text())
        self.assertIsNone(bad.script)


class ProductStatusChartTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.reader = get_user_model().objects.create_user("status-chart-reader", is_staff=True)
        cls.reader.user_permissions.add(Permission.objects.get(codename="view_product"))
        cls.draft = Product.objects.create(name="草稿样品", sku="D", price=1)
        cls.active = Product.objects.create(name="已上架样品", sku="A", price=2, status="active")
        cls.archived = Product.objects.create(name="已归档样品", sku="Z", price=3, status="archived")

    def setUp(self):
        self.client.force_login(self.reader)
        self.owner = admin.site.get_model_admin(Product)

    def card(self, site="admin", **query):
        response = self.client.get(reverse(f"{site}:index"), query)
        self.assertEqual(response.status_code, 200)
        return BeautifulSoup(response.content, "html.parser").select_one(".nova-category-chart")

    def points(self, card):
        return json.loads(card.select_one('[type="application/json"]').string)["points"]

    def link(self, card, status):
        return card.select_one(f'a[data-nova-category="{status}"]')["href"]

    def test_all_current_states_independent_of_daily_window_and_read_only_links(self):
        Product.objects.update(updated_at=timezone.now() - timedelta(days=80))
        Product.objects.create(name="回收站", sku="trash", price=0, status="active").delete()
        card = self.card(chart_days=7)
        self.assertEqual([(p["key"], p["label"], p["value"]) for p in self.points(card)],
                         [("draft", "草稿", 1), ("active", "已上架", 1), ("archived", "已归档", 1)])
        self.assertEqual(self.points(self.card(chart_days=30)), self.points(card))
        for obj in (self.draft, self.active, self.archived):
            url = self.link(card, obj.status)
            target = urlsplit(url)
            self.assertEqual(target.path, reverse("admin:catalog_product_changelist"))
            query = parse_qs(target.query)
            self.assertEqual(query["status__exact"], [obj.status])
            self.assertTrue(query["activity_day"][0].startswith("all~"))
            page = self.client.get(url)
            self.assertEqual(list(page.context["cl"].result_list), [obj])
            self.assertIsNone(page.context["cl"].formset)
            self.assertEqual(self.client.post(url, {"_save": "1"}).status_code, 403)
        self.assertEqual(self.client.get(self.link(card, "draft") + "&q=absent").context["cl"].result_count, 0)

    def test_queryset_object_scope_deduplication_zero_and_permission_changes(self):
        for name in ("one", "two"):
            self.draft.tags.add(Tag.objects.create(name=name, slug=name))
        self.active.tags.add(Tag.objects.get(slug="one"))
        scope = Product.objects.filter(tags__isnull=False)
        with patch.object(self.owner, "get_queryset", return_value=scope), patch.object(
            self.owner, "has_view_permission", side_effect=lambda request, obj=None: obj != self.active
        ):
            card = self.card()
            self.assertEqual([point["value"] for point in self.points(card)], [1, 0, 0])
            url = self.link(card, "draft")
            cl = self.client.get(url + "&_facets=1").context["cl"]
            self.assertEqual((cl.result_count, cl.full_result_count, list(cl.result_list)), (1, 1, [self.draft]))
            self.assertEqual(self.client.get(self.link(card, "active")).context["cl"].result_count, 0)
        Product.objects.filter(pk=self.draft.pk).update(status="active")
        self.assertEqual(self.client.get(url).context["cl"].result_count, 0)
        with patch.object(self.owner, "get_queryset", return_value=Product.objects.none()):
            self.assertEqual(self.client.get(self.link(card, "active")).context["cl"].result_count, 0)
        self.reader.user_permissions.clear()
        with patch.object(self.owner, "get_queryset", side_effect=AssertionError("unauthorized query")):
            self.assertIsNone(self.card())
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_empty_error_and_hidden_field(self):
        with patch.object(self.owner, "has_view_or_change_permission", side_effect=lambda req, obj=None: obj is None):
            card = self.card()
            self.assertIn("暂无可见商品", card.get_text())
            self.assertIsNone(card.select_one("a, script, canvas"))
        with patch("catalog.charts.visible_products", side_effect=DatabaseError("private error")):
            card = self.card()
            self.assertIn("刷新重试", card.get_text())
            self.assertNotIn("private error", str(card))
            self.assertIsNone(card.script)
        for hook, result in (("get_list_display", ["name"]), ("get_list_filter", []), ("has_module_permission", False)):
            with self.subTest(hook=hook), patch.object(self.owner, hook, return_value=result):
                self.assertIsNone(self.card())
                self.assertEqual(self.client.get(reverse("admin:catalog_product_changelist"), {"status__exact": "draft"}).status_code, 403)

    def test_native_explicit_status_filter_and_non_dashboard_pages(self):
        with patch.object(self.owner, "get_list_filter", return_value=[("status", admin.ChoicesFieldListFilter)]):
            card = self.card()
            response = self.client.get(self.link(card, "draft"))
            self.assertEqual(list(response.context["cl"].result_list), [self.draft])
            self.assertNotContains(response, "category-chart.js")
        session = self.client.session
        session[SESSION_KEY] = "native"
        session.save()
        self.assertIsNone(self.card())

    @override_settings(ROOT_URLCONF="tests.multisite_urls", NOVA_ADMIN_URL_NAMESPACES={})
    def test_drilldown_uses_current_site_registration(self):
        from tests.multisite_urls import warehouse_site

        owner = warehouse_site.get_model_admin(Product)
        with patch.object(warehouse_site, "index_template", "project_admin/dashboard.html"), patch.object(
            owner, "get_queryset", return_value=Product.objects.filter(pk=self.active.pk)
        ), patch.object(self.owner, "get_queryset", side_effect=AssertionError("wrong site")):
            card = self.card("warehouse")
            self.assertEqual([point["value"] for point in self.points(card)], [0, 1, 0])
            url = self.link(card, "active")
            self.assertTrue(url.startswith(reverse("warehouse:catalog_product_changelist") + "?"))
            self.assertEqual(list(self.client.get(url).context["cl"].result_list), [self.active])
