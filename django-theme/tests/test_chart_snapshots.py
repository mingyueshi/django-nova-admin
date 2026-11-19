import json
from copy import deepcopy
from datetime import date, datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import DatabaseError, connection
from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from catalog.models import Product
from nova_admin.charts import validate_daily_snapshot
from nova_admin.preferences import SESSION_KEY


class DailySnapshotTests(SimpleTestCase):
    def setUp(self):
        self.snapshot = {
            "schema_version": 1, "metric": "test.daily", "as_of": "2026-05-02T10:00:00Z",
            "timezone": "Asia/Shanghai", "start": "2026-05-01", "end": "2026-05-04",
            "state": "ready", "points": [
                {"date": "2026-05-01", "value": 0},
                {"date": "2026-05-02", "value": None},
                {"date": "2026-05-03", "value": 1.5},
            ],
        }

    def render(self):
        return BeautifulSoup(render_to_string("nova_admin/daily_chart.html", {
            "chart_title": "A < B", "chart_snapshot": self.snapshot,
        }), "html.parser")

    def test_zero_gap_fraction_and_json_match_the_accessible_table(self):
        card = self.render()
        self.assertEqual(card.h2.get_text(), "A < B")
        self.assertEqual([v.get_text() for v in card.select("td")], ["0", "暂无数据", "1.5"])
        self.assertEqual(json.loads(card.select_one('script[type="application/json"]').string), self.snapshot)
        self.assertTrue(card.details.has_attr("open"))

    def test_ninety_days_of_observed_zeros_are_valid(self):
        start = date.fromisoformat(self.snapshot["start"])
        self.snapshot.update(end=(start + timedelta(days=90)).isoformat(), points=[
            {"date": (start + timedelta(days=i)).isoformat(), "value": 0} for i in range(90)
        ])
        self.assertEqual(len(validate_daily_snapshot(self.snapshot)["points"]), 90)

    def test_empty_error_and_invalid_do_not_load_chart_or_emit_payload(self):
        for state, message in (("empty", "范围内暂无数据"), ("error", "刷新重试"), ("unsupported", "刷新重试")):
            with self.subTest(state=state):
                self.snapshot.update(state=state, points=[])
                card = self.render()
                self.assertIn(message, card.get_text())
                self.assertIsNone(card.script)

    def test_schema_range_timezone_and_numeric_limits(self):
        bad = [
            {"schema_version": True}, {"schema_version": 2}, {"timezone": "../secret"},
            {"timezone": "Unknown/Zone"}, {"as_of": "2026-05-01T00:00:00"},
            {"start": "2026-02-30"}, {"end": "2026-05-01"}, {"end": "2027-05-01"},
            {"metric": "<b>"}, {"points": []}, {"state": "empty"}, {"unknown": "extra"},
            {"points": self.snapshot["points"][::-1]},
        ]
        for bad_value in (True, "5", float("inf"), float("nan"), 2**53):
            points = deepcopy(self.snapshot["points"])
            points[0]["value"] = bad_value
            bad.append({"points": points})
        bad.append({"points": [dict(p, value=None) for p in self.snapshot["points"]]})
        for changes in bad:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_daily_snapshot({**self.snapshot, **changes})


class ProductChartTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.viewer = get_user_model().objects.create_user("chart-viewer", is_staff=True)
        cls.viewer.user_permissions.add(Permission.objects.get(codename="view_product"))
        cls.a = Product.objects.create(name="A", sku="A", price=1)
        cls.b = Product.objects.create(name="B", sku="B", price=1)

    def setUp(self):
        self.client.force_login(self.viewer)
        self.url = reverse("admin:index")
        self.owner = admin.site.get_model_admin(Product)

    def stamp(self, product, instant):
        Product.objects.filter(pk=product.pk).update(updated_at=datetime.fromisoformat(instant))

    def card(self, *, zone="Asia/Shanghai", now="2026-11-19T12:00:00+00:00", url=None):
        with timezone.override(ZoneInfo(zone)), patch(
            "catalog.charts.datetime", wraps=datetime
        ) as clock:
            clock.now.return_value = datetime.fromisoformat(now)
            response = self.client.get(url or self.url)
        self.assertEqual(response.status_code, 200)
        return BeautifulSoup(response.content, "html.parser").select_one(".nova-daily-chart")

    def data(self, **kwargs):
        return json.loads(self.card(**kwargs).select_one('script[type="application/json"]').string)

    def test_periods_use_local_midnight_start_inclusive_end_exclusive(self):
        self.stamp(self.a, "2026-11-12T16:00:00+00:00")
        self.stamp(self.b, "2026-11-19T16:00:00+00:00")
        seven = self.data()
        self.assertEqual((seven["start"], seven["end"], seven["timezone"]), ("2026-11-13", "2026-11-20", "Asia/Shanghai"))
        self.assertEqual([p["value"] for p in seven["points"]], [1, 0, 0, 0, 0, 0, 0])
        thirty = self.data(url=self.url + "?chart_days=30")
        self.assertEqual(len(thirty["points"]), 30)
        self.assertEqual(sum(p["value"] for p in thirty["points"]), 1)
        before_cutoff = self.card(zone="UTC")
        self.assertIn("范围内暂无数据", before_cutoff.get_text())
        utc = self.data(zone="UTC", now="2026-11-19T18:00:00+00:00")
        self.assertEqual(utc["points"][-1]["value"], 1)

    @override_settings(USE_TZ=False, TIME_ZONE="Asia/Shanghai")
    def test_naive_database_uses_project_time_zone(self):
        Product.objects.update(updated_at=datetime(2026, 11, 19, 0, 10))
        # The storage timezone owns naive timestamps, even during a user override.
        data = self.data(zone="America/New_York", now="2026-11-18T17:00:00+00:00")
        self.assertEqual(data["timezone"], "Asia/Shanghai")
        self.assertEqual(data["points"][-1], {"date": "2026-11-19", "value": 2})

    def test_one_grouped_query_for_either_range(self):
        for days in (7, 30):
            with self.subTest(days=days), CaptureQueriesContext(connection) as queries:
                self.card(url=self.url + f"?chart_days={days}")
            grouped = [q for q in queries.captured_queries if "GROUP BY" in q["sql"] and "catalog_product" in q["sql"]]
            self.assertEqual(len(grouped), 1)

    def test_dst_short_and_long_days_count_real_local_dates(self):
        cases = [
            ("2026-03-09", "2026-03-08T05:00:00+00:00", "2026-03-09T03:59:59+00:00", "2026-03-08"),
            ("2026-11-02", "2026-11-01T04:00:00+00:00", "2026-11-02T04:59:59+00:00", "2026-11-01"),
        ]
        for now, first, last, expected in cases:
            with self.subTest(day=expected):
                self.stamp(self.a, first)
                self.stamp(self.b, last)
                points = self.data(zone="America/New_York", now=now + "T15:00:00+00:00")["points"]
                self.assertEqual([p for p in points if p["value"]], [{"date": expected, "value": 2}])

    def test_scope_and_field_permissions_gate_the_card(self):
        self.stamp(self.a, "2026-11-19T09:00:00+00:00")
        self.stamp(self.b, "2026-11-19T09:00:00+00:00")
        with patch.object(self.owner, "get_queryset", return_value=Product.objects.filter(pk=self.a.pk)):
            self.assertEqual(sum(p["value"] for p in self.data()["points"]), 1)
        with patch.object(self.owner, "get_list_display", return_value=["name"]):
            self.assertIsNone(self.card())
        self.viewer.user_permissions.clear()
        self.viewer.user_permissions.add(Permission.objects.get(codename="add_product"))
        with patch.object(self.owner, "get_queryset", side_effect=AssertionError("unauthorized query")):
            self.assertIsNone(self.card())

    @override_settings(ROOT_URLCONF="tests.multisite_urls", NOVA_ADMIN_URL_NAMESPACES={})
    def test_current_site_registration_is_used(self):
        from tests.multisite_urls import warehouse_site

        self.stamp(self.a, "2026-11-19T12:00:00+00:00")
        with patch.object(warehouse_site, "index_template", "project_admin/dashboard.html"), patch.object(
            warehouse_site.get_model_admin(Product), "get_queryset", return_value=Product.objects.none()
        ), patch.object(self.owner, "get_queryset", side_effect=AssertionError("wrong site")):
            card = self.card(url=reverse("warehouse:index"))
            self.assertIn("范围内暂无数据", card.get_text())
            self.assertIsNone(card.script)

    def test_invalid_filter_and_database_error_stay_local_to_card(self):
        for query in ("?chart_days=1", "?chart_days=7&chart_days=30"):
            card = self.card(url=self.url + query)
            self.assertIn("请选择近 7 天", card.get_text())
            self.assertIsNone(card.script)
        with patch.object(self.owner, "get_queryset", side_effect=DatabaseError("PRIVATE")):
            card = self.card()
            self.assertIn("刷新重试", card.get_text())
            self.assertNotIn("PRIVATE", str(card))
            self.assertIsNone(card.script)

    def test_native_mode_and_non_dashboard_do_not_load_module(self):
        listing = self.client.get(reverse("admin:catalog_product_changelist"))
        self.assertNotContains(listing, "daily-chart.js")
        session = self.client.session
        session[SESSION_KEY] = "native"
        session.save()
        self.assertIsNone(self.card())
