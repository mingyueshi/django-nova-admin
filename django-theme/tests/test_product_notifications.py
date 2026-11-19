from unittest.mock import patch

from bs4 import BeautifulSoup
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from catalog import batch_tasks
from catalog.models import Product, ProductBatchItem, ProductBatchTask, ProductNotification, ProductPublicationRequest


class ProductNotificationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        def staff(name, *codes):
            user = get_user_model().objects.create_user(name, is_staff=True)
            user.user_permissions.add(*Permission.objects.filter(content_type__app_label="catalog", codename__in=codes))
            return user

        cls.applicant = staff("applicant", "change_product")
        cls.reviewer = staff("reviewer", "view_product", "approve_product")
        cls.other = staff("other", "change_product")
        cls.product = Product.objects.create(name="灯具 <A>", sku="LAMP", price=3)
        cls.second = Product.objects.create(name="第二件商品", sku="SECOND", price=4)

    def setUp(self):
        self.inbox = reverse("admin:catalog_product_notifications")
        self.owner = admin.site.get_model_admin(Product)
        self.client.force_login(self.applicant)

    def publication(self, product, action, record=0, site="admin", **extra):
        url = reverse(f"{site}:catalog_product_publication", args=[product.pk])
        return self.client.post(url, {"action": action, "request_id": record, **extra})

    def submit(self, product, site="admin"):
        self.client.force_login(self.applicant)
        self.assertEqual(self.publication(product, "submit", site=site).status_code, 302)
        return product.publication_requests.get(result="pending")

    def decide(self, product, action="approve", submit_site="admin", review_site="admin"):
        application = self.submit(product, submit_site)
        self.client.force_login(self.reviewer)
        self.assertEqual(self.publication(product, action, application.pk, review_site).status_code, 302)
        self.client.force_login(self.applicant)
        return ProductNotification.objects.get(publication=application)

    def bulk(self, *products, site="admin"):
        listing = reverse(f"{site}:catalog_product_changelist")
        result = self.client.post(listing, {"index": "0", "action": "publish_products",
                                            "_selected_action": [p.pk for p in products]})
        self.assertEqual(result.status_code, 302)
        return result.url

    def check_inbox(self, unread, *notices, site="admin"):
        url = reverse(f"{site}:catalog_product_notifications")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["notification_unread"], unread)
        self.assertEqual([n.pk for n in response.context["page"]], [n.pk for n in notices])
        self.assertContains(response, f"通知中心（{unread} 未读）")
        self.assertContains(response, f"未读通知 {unread} 条")
        return response

    def test_empty_inbox_and_global_link(self):
        response = self.check_inbox(0)
        self.assertContains(response, "暂无可查看的通知。")
        self.assertNotContains(response, "标记已读")
        for name in ("index", "catalog_product_changelist"):
            home = self.client.get(reverse(f"admin:{name}"))
            self.assertContains(home, f'href="{self.inbox}"')
            self.assertContains(home, "通知中心（0 未读）")
        self.assertNotContains(self.client.get(reverse("admin:catalog_product_changelist"), {"_popup": 1}), self.inbox)
        self.assertEqual(self.client.put(self.inbox).status_code, 405)

    def test_real_results_are_for_submitter_and_unread_until_explicit_post(self):
        approved = self.decide(self.product)
        rejected = self.decide(self.second, "reject")
        page = self.check_inbox(2, rejected, approved)
        self.assertContains(page, "上架审批已通过")
        self.assertContains(page, "上架审批已驳回")
        self.assertContains(page, "灯具 &lt;A&gt;")
        self.client.force_login(self.reviewer)
        self.check_inbox(0)
        self.client.force_login(self.applicant)
        self.client.get(self.inbox, {"notification": approved.pk})
        self.assertEqual(self.client.head(self.inbox).status_code, 200)
        approved.refresh_from_db()
        self.assertIsNone(approved.read_at)
        # Read-only product access suffices for your own read state.
        self.applicant.user_permissions.set([Permission.objects.get(codename="view_product")])
        self.assertRedirects(self.client.post(self.inbox, {"notification": approved.pk}), self.inbox)
        approved.refresh_from_db()
        first_read = approved.read_at
        self.assertRedirects(self.client.post(self.inbox, {"notification": approved.pk}), self.inbox)
        approved.refresh_from_db()
        self.assertIsNotNone(first_read)
        self.assertEqual(approved.read_at, first_read)
        page = self.check_inbox(1, rejected, approved)
        self.assertContains(page, "标记已读", count=1)
        self.assertContains(self.client.get(reverse("admin:index")), "通知中心（1 未读）")

    def test_replayed_decision_does_not_duplicate_or_reset_read_state(self):
        notice = self.decide(self.product, "reject")
        self.client.post(self.inbox, {"notification": notice.pk})
        self.client.force_login(self.reviewer)
        self.assertEqual(self.publication(self.product, "reject", notice.publication_id).status_code, 409)
        self.client.force_login(self.applicant)
        self.check_inbox(0, notice)
        # A resubmission and its decision are a new event.
        self.assertEqual(self.publication(self.product, "submit", notice.publication_id).status_code, 302)
        next_request = self.product.publication_requests.get(result="pending")
        self.client.force_login(self.reviewer)
        self.assertEqual(self.publication(self.product, "approve", next_request.pk).status_code, 302)
        self.client.force_login(self.applicant)
        self.check_inbox(1, ProductNotification.objects.get(publication=next_request), notice)

    @patch.object(batch_tasks, "BATCH_SIZE", 1)
    def test_task_notifies_once_only_at_actual_completion_including_partial_failure(self):
        Product.objects.filter(pk=self.second.pk).update(status="archived")
        task_url = self.bulk(self.product, self.second)
        task = ProductBatchTask.objects.get()
        self.check_inbox(0)
        with patch.object(self.owner, "get_queryset", return_value=Product.objects.filter(pk=self.product.pk)):
            counts = self.client.get(task_url).context["counts"]
            self.assertEqual((counts["total"], counts["processed"]), (1, 1))
            self.check_inbox(0)
        data = {"cursor": self.client.get(task_url).context["cursor"]}
        self.assertEqual(self.client.post(task_url, data).status_code, 302)
        notice = ProductNotification.objects.get(task=task)
        self.assertContains(self.check_inbox(1, notice), f'href="{task_url}"')
        self.assertEqual(self.client.post(self.inbox, {"notification": notice.pk}).status_code, 302)
        self.assertEqual(self.client.post(task_url, data).status_code, 302)
        self.check_inbox(0, notice)
        self.assertEqual(task.items.exclude(outcome=ProductBatchItem.Outcome.SUBMITTED).count(), 1)
        self.assertEqual(self.product.publication_requests.get().site, "admin")

    def test_all_failed_task_still_has_one_completion_notice(self):
        Product.objects.update(status="active")
        self.bulk(self.product, self.second)
        notice = ProductNotification.objects.get()
        self.assertIsNotNone(notice.task_id)
        self.check_inbox(1, notice)
        self.assertFalse(ProductPublicationRequest.objects.exists())

    def test_other_accounts_cannot_read_or_mark_even_with_catalog_permissions(self):
        published = self.decide(self.product)
        self.bulk(self.second)
        completed = ProductNotification.objects.get(task__isnull=False)
        self.client.force_login(self.other)
        attempts = {"owner": self.applicant.pk, "recipient": self.applicant.pk, "site": "admin"}
        self.assertContains(self.client.get(self.inbox, attempts), "暂无可查看的通知。")
        for notice in (published, completed):
            self.assertEqual(self.client.post(self.inbox, {"notification": notice.pk, **attempts}).status_code, 404)
        self.assertEqual(self.client.post(self.inbox, {"notification": 999999}).status_code, 404)
        self.assertFalse(ProductNotification.objects.filter(read_at__isnull=False).exists())
        self.client.logout()
        self.assertEqual(self.client.get(self.inbox).status_code, 302)
        self.assertEqual(self.client.post(self.inbox, {"notification": published.pk}).status_code, 302)

    def test_current_scope_controls_header_list_task_link_and_post(self):
        notice = self.decide(self.product)
        task_url = self.bulk(self.product, self.second)
        task = ProductNotification.objects.get(task__isnull=False)
        self.check_inbox(2, task, notice)
        with patch.object(self.owner, "get_queryset", return_value=Product.objects.filter(pk=self.second.pk)):
            response = self.check_inbox(1, task)
            self.assertNotContains(response, "灯具")
            self.assertEqual(self.client.get(task_url).context["counts"]["total"], 1)
            self.assertContains(self.client.get(reverse("admin:index")), "通知中心（1 未读）")
            self.assertEqual(self.client.post(self.inbox, {"notification": notice.pk}).status_code, 404)
        with patch.object(self.owner, "has_view_or_change_permission", side_effect=lambda req, obj=None: obj is None):
            self.assertContains(self.check_inbox(0), "暂无可查看的通知。")
            self.assertEqual(self.client.post(self.inbox, {"notification": task.pk}).status_code, 404)
        Product.objects.all().delete()
        self.check_inbox(0)
        self.assertEqual(self.client.post(self.inbox, {"notification": notice.pk}).status_code, 404)
        self.assertFalse(ProductNotification.objects.filter(read_at__isnull=False).exists())

    def test_mark_read_rechecks_live_scope_at_write_time(self):
        notice = self.decide(self.product)

        def recycle_during_check(request, obj=None):
            if obj is not None:
                obj.delete()
            return True

        with patch.object(self.owner, "has_view_or_change_permission", side_effect=recycle_during_check):
            self.assertEqual(self.client.post(self.inbox, {"notification": notice.pk}).status_code, 404)
        notice.refresh_from_db()
        self.assertIsNone(notice.read_at)

    def test_model_module_and_column_permission_revocation(self):
        notice = self.decide(self.product)
        for hook, value in (("has_module_permission", False), ("get_list_display", ["name"])):
            with patch.object(self.owner, hook, return_value=value):
                self.assertNotContains(self.client.get(reverse("admin:index")), self.inbox)
                self.assertEqual(self.client.get(self.inbox).status_code, 403)
                self.assertEqual(self.client.post(self.inbox, {"notification": notice.pk}).status_code, 403)
        self.applicant.user_permissions.clear()
        self.assertEqual(self.client.get(self.inbox).status_code, 403)
        self.assertEqual(self.client.post(self.inbox, {"notification": notice.pk}).status_code, 403)

    @override_settings(ROOT_URLCONF="tests.multisite_urls")
    def test_result_uses_submission_site_task_uses_its_site_and_links_follow_namespace(self):
        for user in (self.applicant, self.reviewer):
            user.user_permissions.add(Permission.objects.get(codename="view_category"))
        notice = self.decide(self.product, submit_site="warehouse", review_site="review")
        warehouse_task_url = self.bulk(self.second, site="warehouse")
        task = ProductNotification.objects.get(task__isnull=False)
        page = self.check_inbox(2, task, notice, site="warehouse")
        self.assertContains(page, reverse("warehouse:catalog_product_change", args=[self.product.pk]))
        self.assertContains(page, warehouse_task_url)
        self.check_inbox(0, site="review")
        other_inbox = reverse("review:catalog_product_notifications")
        for event in (notice, task):
            self.assertEqual(self.client.post(other_inbox, {"site": "warehouse", "notification": event.pk}).status_code, 404)
        self.assertEqual(self.second.publication_requests.get().site, "warehouse")

    def test_legacy_pending_application_is_attributed_when_decided(self):
        record = ProductPublicationRequest.objects.create(product=self.product, submitted_by=self.applicant)
        self.client.force_login(self.reviewer)
        self.assertEqual(self.publication(self.product, "reject", record.pk).status_code, 302)
        record.refresh_from_db()
        self.assertEqual(record.site, "admin")
        self.client.force_login(self.applicant)
        self.check_inbox(1, ProductNotification.objects.get(publication=record))

    def test_csrf_and_malformed_ids_do_not_mark_notifications(self):
        notice = self.decide(self.product)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.applicant)
        page = BeautifulSoup(client.get(self.inbox).content, "html.parser")
        form = page.select_one('section[aria-label="我的通知"] form')
        token = form.select_one('[name="csrfmiddlewaretoken"]')["value"]
        value = form.select_one('button[name="notification"]')["value"]
        self.assertEqual(client.post(self.inbox, {"notification": value}).status_code, 403)
        for invalid in ("", "bad", -1, 2**64):
            self.assertEqual(client.post(self.inbox, {"csrfmiddlewaretoken": token, "notification": invalid}).status_code, 400)
        self.assertFalse(ProductNotification.objects.filter(read_at__isnull=False).exists())
        self.assertEqual(client.post(self.inbox, {"csrfmiddlewaretoken": token, "notification": value}).status_code, 302)

    def test_database_rejects_duplicate_missing_or_ambiguous_sources(self):
        publication = self.decide(self.product)
        self.bulk(self.second)
        task = ProductNotification.objects.get(task__isnull=False)
        for keys in ({}, {"publication_id": publication.publication_id}, {"task_id": task.task_id},
                     {"publication_id": publication.publication_id, "task_id": task.task_id}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                ProductNotification.objects.create(**keys)
        self.assertEqual(ProductNotification.objects.count(), 2)

    @patch.object(batch_tasks, "BATCH_SIZE", 1)
    def test_delivery_failure_rolls_back_review_and_final_task_item(self):
        record = self.submit(self.product)
        db_manager = type(ProductNotification.objects.all())
        self.client.force_login(self.reviewer)
        with patch.object(db_manager, "get_or_create", side_effect=RuntimeError("notification write")), self.assertRaises(RuntimeError):
            self.publication(self.product, "approve", record.pk)
        record.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual((record.result, self.product.status), ("pending", "draft"))
        self.client.force_login(self.applicant)
        task_url = self.bulk(self.product, self.second)
        data = {"cursor": self.client.get(task_url).context["cursor"]}
        with patch.object(db_manager, "get_or_create", side_effect=RuntimeError("notification write")), self.assertRaises(RuntimeError):
            self.client.post(task_url, data)
        self.assertFalse(self.second.publication_requests.exists())
        self.assertTrue(ProductBatchItem.objects.filter(product=self.second, outcome="pending").exists())
        self.assertFalse(ProductNotification.objects.exists())
        self.assertEqual(self.client.post(task_url, data).status_code, 302)
        self.check_inbox(1, ProductNotification.objects.get(task__isnull=False))
