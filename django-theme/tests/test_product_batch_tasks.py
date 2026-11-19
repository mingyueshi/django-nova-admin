from unittest.mock import patch
from uuid import uuid4

from bs4 import BeautifulSoup
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from catalog import batch_tasks
from catalog.models import Product, ProductBatchItem, ProductBatchTask, ProductPublicationRequest


class ProductBatchTaskTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.editor = get_user_model().objects.create_user("task-editor", is_staff=True)
        cls.other = get_user_model().objects.create_user("another-editor", is_staff=True)
        cls.change = Permission.objects.get(codename="change_product")
        cls.view = Permission.objects.get(codename="view_product")
        for user in (cls.editor, cls.other):
            user.user_permissions.add(cls.change)

    def setUp(self):
        self.client.force_login(self.editor)
        self.owner = admin.site.get_model_admin(Product)
        self.history = reverse("admin:catalog_product_batch_tasks")

    def product(self, sku, status="draft"):
        return Product.objects.create(sku=sku, name=sku, price=2, status=status)

    def submit(self, *products, site="admin", params="", **extra):
        data = {"action": "publish_products", "index": "0", "_selected_action": [p.pk for p in products], **extra}
        return self.client.post(reverse(f"{site}:catalog_product_changelist") + params, data)

    def counts(self, url, expected):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        counts = response.context["counts"]
        self.assertEqual(tuple(counts[k] for k in ("total", "processed", "succeeded", "failed")), expected)
        soup = BeautifulSoup(response.content, "html.parser")
        self.assertEqual((soup.progress["max"], soup.progress["value"]), tuple(str(n) for n in expected[:2]))
        return response

    def test_empty_history_and_empty_filtered_selection(self):
        self.assertContains(self.client.get(self.history), "暂无可查看的批量任务。")
        self.assertContains(self.client.get(reverse("admin:catalog_product_changelist")), f'href="{self.history}"')
        product = self.product("outside")
        self.assertRedirects(self.submit(product, params="?q=missing"), self.history)
        self.assertFalse(ProductBatchTask.objects.exists())
        self.assertFalse(ProductPublicationRequest.objects.exists())
        self.assertEqual(self.client.post(self.history).status_code, 405)

    def test_mixed_batch_results_match_real_approvals_and_history(self):
        good = self.product("待提交 <A>")
        waiting = self.product("已经待审")
        ProductPublicationRequest.objects.create(product=waiting, submitted_by=self.other)
        archived = self.product("已归档", "archived")
        response = self.submit(good, good, waiting, archived, owner=self.other.pk, site="admin", total=99)
        task = ProductBatchTask.objects.get()
        url = reverse("admin:catalog_product_batch_task", args=[task.pk])
        self.assertRedirects(response, url)
        self.assertEqual((task.owner, task.site), (self.editor, "admin"))
        details = self.counts(url, (3, 3, 1, 2))
        self.assertContains(details, "待提交 &lt;A&gt;")
        self.assertContains(details, "商品不是草稿")
        self.assertContains(details, "已有待审批申请")
        self.assertNotContains(details, 'id="batch-continue"')
        self.assertEqual(good.publication_requests.get().submitted_by, self.editor)
        self.assertEqual(ProductPublicationRequest.objects.count(), 2)
        self.assertFalse(archived.publication_requests.exists())
        self.assertEqual(Product.objects.get(pk=good.pk).status, "draft")
        row = self.client.get(self.history).context["page"][0]
        self.assertEqual((row["task_id"], row["total"], row["succeeded"], row["failed"]), (task.pk, 3, 1, 2))

    @patch.object(batch_tasks, "BATCH_SIZE", 1)
    def test_resume_without_javascript_and_replayed_steps(self):
        products = [self.product(f"batch-{i}") for i in range(3)]
        url = self.submit(*products).url
        first = self.counts(url, (3, 1, 1, 0))
        self.assertEqual(self.client.head(url).status_code, 200)
        self.assertEqual(ProductPublicationRequest.objects.count(), 1)
        self.client.logout()
        self.client.force_login(self.editor)
        self.assertContains(self.client.get(self.history), url)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.editor)
        form = BeautifulSoup(client.get(url).content, "html.parser").select_one("#batch-continue")
        data = {f["name"]: f["value"] for f in form.select("input")}
        self.assertEqual(data["cursor"], str(first.context["cursor"]))
        self.assertEqual(client.post(url, {"cursor": data["cursor"]}).status_code, 403)
        self.assertEqual(client.post(url, data).status_code, 302)
        self.assertEqual(client.post(url, data).status_code, 302)
        second = self.counts(url, (3, 2, 2, 0))
        self.assertEqual(self.client.post(url, {"cursor": second.context["cursor"]}).status_code, 302)
        self.counts(url, (3, 3, 3, 0))
        self.assertEqual(ProductPublicationRequest.objects.count(), 3)

    @override_settings(USE_THOUSAND_SEPARATOR=True, LANGUAGE_CODE="en")
    @patch.object(batch_tasks, "BATCH_SIZE", 1)
    def test_continuation_cursor_is_not_localized(self):
        url = self.submit(self.product("first"), self.product("second")).url
        ProductBatchItem.objects.filter(outcome=ProductBatchItem.Outcome.PENDING).update(id=12345)
        form = BeautifulSoup(self.client.get(url).content, "html.parser").select_one("#batch-continue")
        cursor = form.select_one('[name="cursor"]')["value"]
        self.assertEqual(cursor, "12345")
        self.assertEqual(self.client.post(url, {"cursor": cursor}).status_code, 302)
        self.counts(url, (2, 2, 2, 0))

    def test_account_isolation_on_list_detail_and_step(self):
        product = self.product("owner-only")
        url = self.submit(product).url
        self.client.force_login(self.other)
        self.assertContains(self.client.get(self.history), "暂无可查看的批量任务。")
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {"cursor": 1, "owner": self.editor.pk}).status_code, 404)
        self.assertEqual(self.client.get(reverse("admin:catalog_product_batch_task", args=[uuid4()])).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)

    @patch.object(batch_tasks, "BATCH_SIZE", 1)
    def test_readonly_owner_may_read_but_not_advance_after_permission_change(self):
        url = self.submit(self.product("ready"), self.product("later")).url
        cursor = self.counts(url, (2, 1, 1, 0)).context["cursor"]
        self.editor.user_permissions.set([self.view])
        self.assertContains(self.client.get(self.history), url)
        self.assertNotContains(self.client.get(url), 'id="batch-continue"')
        self.assertEqual(self.client.post(url, {"cursor": cursor}).status_code, 403)
        self.assertEqual(ProductPublicationRequest.objects.count(), 1)
        self.editor.user_permissions.clear()
        self.assertEqual(self.client.get(self.history).status_code, 403)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_counts_names_and_task_existence_follow_current_queryset_and_object_rights(self):
        first, second, third = [self.product(p) for p in ("product-A", "product-B", "product-C")]
        url = self.submit(first, second, third).url
        with patch.object(self.owner, "get_queryset", return_value=Product.objects.exclude(pk=first.pk)), patch.object(
            self.owner, "has_view_or_change_permission", side_effect=lambda req, obj=None: obj != second
        ):
            response = self.counts(url, (1, 1, 1, 0))
            self.assertNotContains(response, first.name)
            self.assertNotContains(response, second.name)
            self.assertEqual(self.client.get(self.history).context["page"][0]["total"], 1)
            third.delete()
            self.assertContains(self.client.get(self.history), "暂无可查看的批量任务。")
            self.assertEqual(self.client.get(url).status_code, 404)
            self.assertEqual(self.client.post(url, {"cursor": "1"}).status_code, 404)

    def test_unauthorized_selection_creates_neither_task_nor_application(self):
        good, hidden = self.product("good"), self.product("hidden")
        with patch.object(self.owner, "has_change_permission", side_effect=lambda req, obj=None: obj != hidden):
            self.assertEqual(self.submit(good, hidden).status_code, 403)
        self.assertFalse(ProductBatchTask.objects.exists())
        self.assertFalse(ProductPublicationRequest.objects.exists())

    @patch.object(batch_tasks, "BATCH_SIZE", 1)
    def test_native_select_across_snapshots_only_matches_at_submission(self):
        first, second = self.product("match-1"), self.product("match-2")
        self.product("unrelated")
        url = self.submit(first, params="?q=match", select_across="1").url
        self.product("match-late")
        page = self.counts(url, (2, 1, 1, 0))
        self.client.post(url, {"cursor": page.context["cursor"]})
        self.counts(url, (2, 2, 2, 0))
        self.assertSetEqual(set(ProductPublicationRequest.objects.values_list("product_id", flat=True)), {first.pk, second.pk})

    @patch.object(batch_tasks, "BATCH_SIZE", 1)
    def test_continuation_rechecks_object_editability_and_product_version(self):
        first, revoked, changed = [self.product(p) for p in ("first", "revoked", "changed")]
        url = self.submit(first, revoked, changed).url
        cursor = self.client.get(url).context["cursor"]
        with patch.object(self.owner, "has_change_permission", side_effect=lambda req, obj=None: obj != revoked):
            self.client.post(url, {"cursor": cursor})
        changed.stock += 1
        changed.save()
        self.client.post(url, {"cursor": self.client.get(url).context["cursor"]})
        self.counts(url, (3, 3, 1, 2))
        self.assertEqual(ProductPublicationRequest.objects.count(), 1)

    @patch.object(batch_tasks, "BATCH_SIZE", 1)
    def test_old_task_does_not_reopen_intervening_review(self):
        first, second = self.product("first"), self.product("second")
        url = self.submit(first, second).url
        ProductPublicationRequest.objects.create(product=second, submitted_by=self.other,
            reviewed_by=self.other, reviewed_at=timezone.now(), result="rejected")
        self.client.post(url, {"cursor": self.client.get(url).context["cursor"]})
        self.counts(url, (2, 2, 1, 1))
        self.assertFalse(second.publication_requests.filter(result="pending").exists())

    def test_one_validation_failure_does_not_rollback_other_approvals(self):
        first, invalid, last = [self.product(p) for p in ("first", "invalid", "last")]
        submit = batch_tasks.submit_publication

        def submit_except_invalid(scope, product, user, **kwargs):
            if product == invalid:
                raise ValidationError("private validation detail")
            return submit(scope, product, user, **kwargs)

        with patch.object(batch_tasks, "submit_publication", side_effect=submit_except_invalid):
            url = self.submit(first, invalid, last).url
        response = self.counts(url, (3, 3, 2, 1))
        self.assertContains(response, "提交校验失败")
        self.assertNotContains(response, "private validation detail")
        self.assertFalse(invalid.publication_requests.exists())

    @patch.object(batch_tasks, "BATCH_SIZE", 1)
    def test_interrupted_result_write_rolls_back_approval_and_task_resumes(self):
        first, second = self.product("first"), self.product("second")
        url = self.submit(first, second).url
        data = {"cursor": self.client.get(url).context["cursor"]}
        query_class = type(ProductBatchItem.objects.all())
        update = query_class.update

        def interrupted(query, **changes):
            if query.model is ProductBatchItem and changes.get("outcome") == ProductBatchItem.Outcome.SUBMITTED:
                raise RuntimeError("interrupted result write")
            return update(query, **changes)

        with patch.object(query_class, "update", interrupted), self.assertRaises(RuntimeError):
            self.client.post(url, data)
        self.counts(url, (2, 1, 1, 0))
        self.assertFalse(second.publication_requests.exists())
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.counts(url, (2, 2, 2, 0))
        self.assertEqual(ProductPublicationRequest.objects.count(), 2)

    @override_settings(ROOT_URLCONF="tests.multisite_urls")
    def test_site_isolation_and_namespaced_links(self):
        product = self.product("warehouse-only")
        self.editor.user_permissions.add(Permission.objects.get(codename="view_category"))
        url = self.submit(product, site="warehouse").url
        task = ProductBatchTask.objects.get()
        self.assertEqual(url, reverse("warehouse:catalog_product_batch_task", args=[task.pk]))
        self.assertContains(self.client.get(reverse("warehouse:catalog_product_batch_tasks")), url)
        self.assertContains(self.client.get(reverse("review:catalog_product_batch_tasks")), "暂无可查看的批量任务。")
        wrong = reverse("review:catalog_product_batch_task", args=[task.pk])
        self.assertEqual(self.client.get(wrong).status_code, 404)
        self.assertEqual(self.client.post(wrong, {"cursor": 1}).status_code, 404)
