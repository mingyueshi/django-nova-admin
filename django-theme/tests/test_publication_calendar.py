from datetime import datetime
from unittest.mock import patch
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db.models import F
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from catalog.models import Product, ProductPublicationRequest


class PublicationCalendarTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.reader = get_user_model().objects.create_user("calendar-reader", is_staff=True)
        cls.reader.user_permissions.add(Permission.objects.get(codename="view_product"))
        cls.reviewer = get_user_model().objects.create_user("calendar-reviewer", is_staff=True)
        cls.reviewer.user_permissions.add(*Permission.objects.filter(codename__in=["change_product", "approve_product"]))

    def setUp(self):
        self.client.force_login(self.reader)
        self.url = reverse("admin:catalog_product_publication_calendar")
        self.owner = admin.site.get_model_admin(Product)

    def product(self, name, **kwargs):
        return Product.objects.create(name=name, sku=name, price=10, **kwargs)

    def record(self, product, stamp=None, result="approved"):
        return ProductPublicationRequest.objects.create(
            product=product, submitted_by=self.reader, result=result,
            reviewed_at=datetime.fromisoformat(stamp) if stamp else None,
            reviewed_by=self.reviewer if stamp else None,
        )

    def calendar(self, url=None, **params):
        response = self.client.get(url or self.url, params)
        self.assertEqual(response.status_code, 200)
        return BeautifulSoup(response.content, "html.parser").select_one(".publication-calendar")

    def day_link(self, page, day, count):
        link = page.select_one(f'.publication-month time[datetime="{day}"]').parent
        self.assertEqual(link["aria-label"], f"{day}，{count} 件上架商品")
        return urljoin(self.url, link["href"])

    def detail_rows(self, page):
        return [(row.a.text, row.time.get_text(strip=True)) for row in page.select("#publication-day tbody tr")]

    def test_real_approval_and_readonly_list_entry(self):
        lamp = self.product("阅读灯 <A>")
        endpoint = reverse("admin:catalog_product_publication", args=[lamp.pk])
        self.client.force_login(self.reviewer)
        self.assertEqual(self.client.post(endpoint, {"action": "submit", "request_id": 0}).status_code, 302)
        application = lamp.publication_requests.get()
        self.assertEqual(self.client.post(endpoint, {"action": "approve", "request_id": application.pk}).status_code, 302)
        application.refresh_from_db()
        self.client.force_login(self.reader)
        listing = reverse("admin:catalog_product_changelist")
        self.assertContains(self.client.get(listing), f'href="{self.url}"')
        self.assertNotContains(self.client.get(listing, {"_popup": 1}), self.url)
        local = timezone.localtime(application.reviewed_at)
        month = self.calendar(month=local.date().isoformat()[:7])
        detail = self.calendar(self.day_link(month, local.date().isoformat(), 1))
        anchor = detail.select_one("#publication-day tbody a")
        self.assertEqual(anchor.text, lamp.name)
        self.assertEqual(anchor["href"], reverse("admin:catalog_product_change", args=[lamp.pk]))
        self.assertIsNone(detail.select_one("form,button"))
        self.assertNotContains(self.client.get(anchor["href"]), 'name="_save"')

    def test_dates_use_approved_history_and_deduplicate_products_per_day(self):
        lamp = self.product("现已归档", status="archived")
        self.record(lamp, "2026-11-04T10:00:00+00:00")
        self.record(lamp, "2026-11-04T13:00:00+00:00")
        self.record(lamp, "2026-11-05T04:00:00+00:00")
        another = self.product("第二件")
        self.record(another, "2026-11-04T12:00:00+00:00")
        self.product("历史上架但无审批", status="active")
        self.record(self.product("已驳回"), "2026-11-04T09:00:00+00:00", result="rejected")
        self.record(self.product("待审批"), result="pending")
        # Creation, submission and later stock edits have different dates from approval.
        Product.objects.all().update(updated_at=datetime.fromisoformat("2026-11-20T08:00:00+00:00"))
        ProductPublicationRequest.objects.all().update(submitted_at=datetime.fromisoformat("2026-11-01T08:00:00+00:00"))
        with timezone.override(ZoneInfo("Asia/Shanghai")):
            month = self.calendar(month="2026-11")
            for day in ("2026-11-01", "2026-11-20"):
                self.day_link(month, day, 0)
            detail = self.calendar(self.day_link(month, "2026-11-04", 2))
            self.assertEqual(self.detail_rows(detail), [(lamp.name, "21:00:00 +0800"), (another.name, "20:00:00 +0800")])
            self.assertEqual(self.detail_rows(self.calendar(self.day_link(month, "2026-11-05", 1))),
                             [(lamp.name, "12:00:00 +0800")])

    def test_current_timezone_midnight_changes_day_and_month(self):
        events = [("月前", "2026-10-31T15:59:59.999999+00:00"), ("月初", "2026-10-31T16:00:00+00:00"),
                  ("月末", "2026-11-30T15:59:59.999999+00:00"), ("下月", "2026-11-30T16:00:00+00:00")]
        for name, stamp in events:
            self.record(self.product(name), stamp)
        instant = datetime.fromisoformat("2026-10-31T16:00:00+00:00")
        with patch("django.utils.timezone.now", return_value=instant), timezone.override(ZoneInfo("Asia/Shanghai")):
            month = self.calendar()
            self.assertEqual(month.h2.text, "2026年11月")
            self.assertEqual(self.detail_rows(self.calendar(self.day_link(month, "2026-11-01", 1))), [("月初", "00:00:00 +0800")])
            self.assertEqual(self.detail_rows(self.calendar(self.day_link(month, "2026-11-30", 1))), [("月末", "23:59:59 +0800")])
            december = self.calendar(urljoin(self.url, month.select_one('[rel="next"]')["href"]))
            self.day_link(december, "2026-12-01", 1)
        with patch("django.utils.timezone.now", return_value=instant), timezone.override(ZoneInfo("UTC")):
            month = self.calendar()
            self.assertEqual(month.h2.text, "2026年10月")
            self.day_link(month, "2026-10-31", 2)
            self.assertIn("当天暂无可查看的上架商品", self.calendar(day="2026-11-01").get_text())

    def test_dst_short_and_long_days_include_exact_instants(self):
        with timezone.override(ZoneInfo("America/New_York")):
            for day, before, first, last, after in [
                ("2026-03-08", "2026-03-08T04:59:59", "2026-03-08T05:00:00", "2026-03-09T03:59:59", "2026-03-09T04:00:00"),
                ("2026-11-01", "2026-11-01T03:59:59", "2026-11-01T04:00:00", "2026-11-02T04:59:59", "2026-11-02T05:00:00"),
            ]:
                for label, stamp in [("前", before), ("首", first), ("末", last), ("后", after)]:
                    self.record(self.product(day + label), stamp + "+00:00")
                page = self.calendar(day=day)
                self.day_link(page, day, 2)
                self.assertEqual([name for name, _ in self.detail_rows(page)], [day + "末", day + "首"])
            repeat = self.product("回拨两次")
            self.record(repeat, "2026-11-01T05:45:00+00:00")
            self.record(repeat, "2026-11-01T06:15:00+00:00")
            early = self.product("回拨前")
            self.record(early, "2026-11-01T05:45:00+00:00")
            fold = self.calendar(day="2026-11-01")
            self.day_link(fold, "2026-11-01", 4)
            self.assertEqual(self.detail_rows(fold)[1:3], [(repeat.name, "01:15:00 -0500"), (early.name, "01:45:00 -0400")])
            self.assertEqual(fold.select("#publication-day time")[1]["datetime"], "2026-11-01T01:15:00-05:00")

    def test_skipped_civil_date_has_no_approvals(self):
        self.record(self.product("跳日前"), "2011-12-30T09:59:59+00:00")
        self.record(self.product("跳日后"), "2011-12-30T10:00:00+00:00")
        with timezone.override(ZoneInfo("Pacific/Apia")):
            skipped = self.calendar(day="2011-12-30")
            self.day_link(skipped, "2011-12-29", 1)
            self.day_link(skipped, "2011-12-30", 0)
            self.day_link(skipped, "2011-12-31", 1)
            self.assertEqual(self.detail_rows(skipped), [])

    def test_non_hour_fixed_offset(self):
        self.record(self.product("尼泊尔午夜"), "2026-12-31T18:15:00+00:00")
        with timezone.override(timezone.get_fixed_timezone(345)):
            january = self.calendar(day="2027-01-01")
            self.day_link(january, "2027-01-01", 1)
            self.assertEqual(self.detail_rows(january), [("尼泊尔午夜", "00:00:00 +0545")])

    @override_settings(USE_TZ=False, TIME_ZONE="Asia/Shanghai")
    def test_naive_approvals_use_project_wall_time(self):
        self.record(self.product("本地午夜"), "2026-11-01T00:00:00")
        self.record(self.product("本地月前"), "2026-10-31T23:59:59")
        with timezone.override(ZoneInfo("America/New_York")):
            page = self.calendar(day="2026-11-01")
            self.day_link(page, "2026-11-01", 1)
            self.assertEqual(self.detail_rows(page), [("本地午夜", "00:00:00")])
            self.assertIn("Asia/Shanghai", page.get_text())

    def test_scope_object_permissions_and_revocation_on_drilldown(self):
        shown, scoped_out, denied = (self.product(name) for name in ("可见", "其他站点", "其他负责人"))
        for product in (shown, scoped_out, denied):
            self.record(product, "2026-11-04T10:00:00+00:00")
        scoped = Product.objects.exclude(pk=scoped_out.pk).annotate(visible_stock=F("stock"))
        with patch.object(self.owner, "get_queryset", return_value=scoped), patch.object(
            self.owner, "has_view_or_change_permission",
            side_effect=lambda req, obj=None: obj is None or (obj.pk != denied.pk and obj.visible_stock == 0),
        ):
            month = self.calendar(month="2026-11")
            url = self.day_link(month, "2026-11-04", 1)
            detail = self.calendar(url)
            self.assertEqual([name for name, _ in self.detail_rows(detail)], [shown.name])
            for hidden in (scoped_out, denied):
                self.assertNotIn(hidden.name, detail.get_text())
                self.assertIsNone(detail.select_one(f'a[href="{reverse("admin:catalog_product_change", args=[hidden.pk])}"]'))
        with patch.object(self.owner, "has_view_or_change_permission", side_effect=lambda req, obj=None: obj is None):
            detail = self.calendar(url)
            self.day_link(detail, "2026-11-04", 0)
            self.assertIn("本月暂无可查看的上架商品", detail.get_text())
            self.assertIn("当天暂无可查看的上架商品", detail.get_text())
        self.reader.user_permissions.clear()
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_empty_month_day_and_keyboard_links(self):
        month = self.calendar(month="2026-04")
        self.assertIn("本月暂无可查看的上架商品", month.get_text())
        self.assertEqual(len(month.select(".publication-month tbody a")), 30)
        self.assertIsNone(month.select_one("#publication-day"))
        day = self.calendar(self.day_link(month, "2026-04-05", 0))
        self.assertEqual(day.select_one('.publication-month [aria-current="true"] time')["datetime"], "2026-04-05")
        self.assertEqual(day.select_one("#publication-day")["tabindex"], "-1")
        self.assertIn("当天暂无可查看的上架商品", day.get_text())

    def test_month_navigation_year_leap_day_and_grid_alignment(self):
        dec = self.calendar(day="2023-12-31")
        jan = self.calendar(urljoin(self.url, dec.select_one('a[rel="next"]')["href"]))
        self.assertEqual(jan.h2.text, "2024年1月")
        self.assertIsNone(jan.select_one("#publication-day"))
        self.assertEqual(jan.select_one("tbody td time")["datetime"], "2024-01-01")
        self.assertEqual(jan.select_one('a[rel="prev"]')["href"], "?month=2023-12")
        feb = self.calendar(urljoin(self.url, jan.select_one('a[rel="next"]')["href"]))
        first_week = feb.select("tbody tr")[0].find_all("td")
        self.assertTrue(all(cell.a is None for cell in first_week[:3]))
        self.assertEqual(first_week[3].time.text, "1")
        self.assertEqual(len(feb.select("tbody a")), 29)
        self.day_link(feb, "2024-02-29", 0)
        self.assertIsNone(self.calendar(month="0001-01").select_one('[rel="prev"]'))
        self.assertIsNone(self.calendar(month="9999-12").select_one('[rel="next"]'))

    def test_invalid_dates_conflicts_and_duplicate_parameters(self):
        for data in [{"month": "2026-13"}, {"month": ""}, {"month": "2026-1"}, {"month": ["2026-10", "2026-11"]},
                     {"day": "2026-02-29"}, {"day": "20261104"}, {"day": ""}, {"day": ["2026-11-01"] * 2},
                     {"month": "2026-10", "day": "2026-11-01"}]:
            with self.subTest(data=data):
                self.assertEqual(self.client.get(self.url, data).status_code, 404)
        self.assertEqual(self.client.get(self.url, {"month": "2026-11", "day": "2026-11-01"}).status_code, 200)

    def test_view_permission_field_visibility_and_readonly_http_methods(self):
        for method, value in [("has_module_permission", False), ("get_list_display", ["name"])]:
            with patch.object(self.owner, method, return_value=value):
                self.assertEqual(self.client.get(self.url).status_code, 403)
                self.assertNotContains(self.client.get(reverse("admin:catalog_product_changelist")), self.url)
        self.assertEqual(self.client.head(self.url).status_code, 200)
        self.client.force_login(self.reviewer)
        self.assertEqual(self.client.post(self.url, {"action": "approve"}).status_code, 405)
        self.assertEqual(self.client.put(self.url).status_code, 405)
        self.assertFalse(ProductPublicationRequest.objects.exists())
        self.reviewer.user_permissions.set([Permission.objects.get(codename="approve_product")])
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)

    @override_settings(ROOT_URLCONF="tests.multisite_urls")
    def test_calendar_uses_current_site_for_scope_entry_and_product_links(self):
        from tests.multisite_urls import warehouse_site

        self.url = reverse("warehouse:catalog_product_publication_calendar")
        shown, hidden = self.product("仓库"), self.product("其他站点")
        for product in (shown, hidden):
            self.record(product, "2026-11-04T10:00:00+00:00")
        self.assertEqual(self.client.get(reverse("review:catalog_product_publication_calendar")).status_code, 302)
        owner = warehouse_site.get_model_admin(Product)
        with patch.object(owner, "get_queryset", return_value=Product.objects.filter(pk=shown.pk)):
            self.assertContains(self.client.get(reverse("warehouse:catalog_product_changelist")), f'href="{self.url}"')
            month = self.calendar(month="2026-11")
            detail = self.calendar(self.day_link(month, "2026-11-04", 1))
            self.assertEqual([a["href"] for a in detail.select("#publication-day tbody a")],
                             [reverse("warehouse:catalog_product_change", args=[shown.pk])])
