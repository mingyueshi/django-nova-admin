from unittest.mock import patch

from bs4 import BeautifulSoup
from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from catalog.models import Product, ProductPublicationRequest


class ProductPublicationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        def staff(name, *codes):
            user = get_user_model().objects.create_user(name, is_staff=True)
            user.user_permissions.add(*Permission.objects.filter(content_type__app_label="catalog", codename__in=codes))
            return user

        cls.reader = staff("product-reader", "view_product")
        cls.editor = staff("draft-editor", "change_product", "add_product")
        cls.reviewer = staff("publication-reviewer", "view_product", "approve_product")
        cls.product = Product.objects.create(name="审批样品", sku="REQ-01", price=20, stock=4)
        cls.other = Product.objects.create(name="其他样品", sku="REQ-02", price=30)

    def setUp(self):
        self.owner = admin.site.get_model_admin(Product)
        self.board_url = reverse("admin:catalog_product_status_board")
        self.url = reverse("admin:catalog_product_publication", args=[self.product.pk])
        self.change_url = reverse("admin:catalog_product_change", args=[self.product.pk])
        self.client.force_login(self.editor)

    def post(self, action, application=0, **extra):
        return self.client.post(self.url, {"action": action, "request_id": application, **extra})

    def submit(self, previous=0):
        self.assertRedirects(self.post("submit", previous), self.board_url, fetch_redirect_response=False)
        return self.product.publication_requests.get(result="pending")

    def card(self):
        page = BeautifulSoup(self.client.get(self.board_url).content, "html.parser")
        return page.find("a", href=self.change_url, class_="product-board-name").parent

    def form_data(self, **overrides):
        return {
            "name": self.product.name, "sku": self.product.sku, "price": 20, "stock": 4,
            "status": "draft", "initial-status": "draft", "_save": "Save",
            "variants-TOTAL_FORMS": "0", "variants-INITIAL_FORMS": "0",
            "variants-MIN_NUM_FORMS": "0", "variants-MAX_NUM_FORMS": "1000", **overrides,
        }

    def test_board_submission_and_decision_use_session_actors_and_record_time(self):
        button = self.card().select_one('button[value="submit"]')
        self.assertEqual(button["formaction"], self.url)
        response = self.post("submit", submitted_by=self.reviewer.pk, result="approved")
        self.assertRedirects(response, self.board_url, fetch_redirect_response=False)
        app = self.product.publication_requests.get()
        self.assertEqual((app.submitted_by, app.result, app.reviewed_by, app.reviewed_at),
                         (self.editor, "pending", None, None))
        self.assertIsNone(self.card().select_one("form"))
        self.client.force_login(self.reviewer)
        form = self.card().form
        self.assertEqual(form["action"], self.url)
        self.assertEqual(form.select_one('[name="request_id"]')["value"], str(app.pk))
        self.assertEqual([b["value"] for b in form.select("button")], ["approve", "reject"])
        self.assertRedirects(self.post("approve", app.pk, reviewed_by=self.editor.pk), self.board_url)
        self.product.refresh_from_db()
        app.refresh_from_db()
        self.assertEqual((app.result, app.reviewed_by, self.product.status), ("approved", self.reviewer, "active"))
        self.assertGreaterEqual(app.reviewed_at, app.submitted_at)
        self.assertEqual(self.product.updated_at, app.reviewed_at)
        self.assertEqual(LogEntry.objects.get(object_id=str(self.product.pk)).user, self.reviewer)
        self.assertIn(self.reviewer.username, self.card().details.get_text())

    def test_rejection_resubmission_and_replay_preserve_each_decision(self):
        stamp = self.product.updated_at
        first = self.submit()
        self.assertEqual(self.post("submit").status_code, 409)
        self.client.force_login(self.reviewer)
        self.assertEqual(self.post("reject", first.pk).status_code, 302)
        self.assertEqual(self.post("approve", first.pk).status_code, 409)
        self.product.refresh_from_db()
        self.assertEqual((self.product.status, self.product.updated_at), ("draft", stamp))
        self.client.force_login(self.editor)
        self.assertEqual(self.post("submit", 0).status_code, 409)
        second = self.submit(first.pk)
        self.client.force_login(self.reviewer)
        self.assertEqual(self.post("approve", first.pk).status_code, 409)
        self.assertEqual(self.post("approve", second.pk).status_code, 302)
        self.assertEqual(self.post("reject", second.pk).status_code, 409)
        self.assertEqual(list(self.product.publication_requests.values_list("pk", "result", "reviewed_by_id")),
                         [(second.pk, "approved", self.reviewer.pk), (first.pk, "rejected", self.reviewer.pk)])
        self.assertEqual(LogEntry.objects.count(), 2)
        self.assertIn("已驳回", self.card().details.get_text())

    def test_readonly_revocation_and_independent_permissions(self):
        app = self.submit()
        self.assertEqual(self.post("approve", app.pk).status_code, 403)
        self.client.force_login(self.reader)
        self.assertIsNone(self.card().form)
        self.assertIn("待审批", self.card().text)
        for action in ("submit", "approve", "reject"):
            self.assertEqual(self.post(action, app.pk).status_code, 403)
        self.client.force_login(self.reviewer)
        self.assertEqual(self.post("submit").status_code, 403)
        self.assertIsNotNone(self.card().form)
        self.reviewer.user_permissions.remove(Permission.objects.get(codename="approve_product"))
        self.assertEqual(self.post("approve", app.pk).status_code, 403)
        self.editor.user_permissions.clear()
        self.client.force_login(self.editor)
        self.assertEqual(self.post("submit").status_code, 403)
        app.refresh_from_db()
        self.assertEqual((app.result, app.reviewed_by), ("pending", None))

    def test_product_and_application_must_both_be_in_scope(self):
        app = self.submit()
        other_url = reverse("admin:catalog_product_publication", args=[self.other.pk])
        self.assertEqual(self.client.post(other_url, {"action": "submit", "request_id": 0}).status_code, 302)
        other_app = self.other.publication_requests.get()
        self.client.force_login(self.reviewer)
        self.assertEqual(self.post("approve", other_app.pk).status_code, 409)
        for method, kwargs, status in [
            ("get_queryset", {"return_value": Product.objects.exclude(pk=self.product.pk)}, 404),
            ("has_view_or_change_permission", {"side_effect": lambda req, obj=None: obj != self.product}, 404),
            ("has_approve_permission", {"side_effect": lambda req, obj=None: obj != self.product}, 403),
            ("get_readonly_fields", {"return_value": ["status"]}, 403),
            ("get_list_display", {"return_value": ["name"]}, 403),
        ]:
            with self.subTest(method=method), patch.object(self.owner, method, **kwargs):
                self.assertEqual(self.post("reject", app.pk).status_code, status)
        self.client.force_login(self.editor)
        with patch.object(self.owner, "has_change_permission", side_effect=lambda req, obj=None: obj != self.product):
            self.assertEqual(self.post("submit").status_code, 403)
        self.assertEqual(ProductPublicationRequest.objects.filter(result="pending").count(), 2)

    def test_only_drafts_can_be_submitted_and_pending_state_is_protected(self):
        for status in ("archived", "active"):
            Product.objects.filter(pk=self.product.pk).update(status=status)
            self.assertEqual(self.post("submit").status_code, 409)
            self.assertIsNone(self.card().select_one('button[value="submit"]'))
        Product.objects.filter(pk=self.product.pk).update(status="draft")
        self.submit()
        self.assertEqual(self.client.post(self.board_url, {"product_id": self.product.pk, "previous_status": "draft",
                                                          "status": "archived"}).status_code, 409)
        response = self.client.post(self.change_url, self.form_data(status="archived"))
        self.assertIn("status", response.context["adminform"].form.errors)
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, "draft")

    def test_publication_cannot_bypass_review_in_board_or_native_forms(self):
        for user in (self.editor, self.reviewer):
            self.client.force_login(user)
            self.assertEqual(self.client.post(self.board_url, {"product_id": self.product.pk, "previous_status": "draft",
                                                               "status": "active"}).status_code, 403)
        self.client.force_login(self.editor)
        for url, sku in [(self.change_url, self.product.sku), (reverse("admin:catalog_product_add"), "NEW")]:
            response = self.client.post(url, self.form_data(status="active", sku=sku))
            self.assertIn("status", response.context["adminform"].form.errors)
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, "draft")
        self.assertFalse(Product.objects.filter(sku="NEW").exists())

    def test_native_product_edits_keep_concurrent_approval(self):
        initial = self.client.get(self.change_url)
        self.assertContains(initial, 'name="initial-status"')
        app = self.submit()
        self.client.force_login(self.reviewer)
        self.assertEqual(self.post("approve", app.pk).status_code, 302)
        self.client.force_login(self.editor)
        response = self.client.post(self.change_url, self.form_data(stock=15))
        self.assertEqual(response.status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual((self.product.stock, self.product.status), (15, "active"))
        # An intentional archive from the old draft form must also be checked.
        response = self.client.post(self.change_url, self.form_data(status="archived"))
        self.assertEqual(response.status_code, 409)
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, "active")

    def test_ordinary_save_cannot_restore_active_status_after_concurrent_archive(self):
        Product.objects.filter(pk=self.product.pk).update(status="active")
        save = self.owner.save_model

        def archive_before_save(request, obj, form, change):
            Product.objects.filter(pk=obj.pk).update(status="archived")
            return save(request, obj, form, change)

        # An older form can lack the hidden initial value and report status as changed.
        data = self.form_data(stock=9, status="active")
        del data["initial-status"]
        with patch.object(self.owner, "save_model", side_effect=archive_before_save):
            self.assertEqual(self.client.post(self.change_url, data).status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual((self.product.stock, self.product.status), (9, "archived"))

    def test_bulk_submission_reuses_permissions_and_deduplicates(self):
        listing = reverse("admin:catalog_product_changelist")
        data = {"action": "publish_products", "_selected_action": [self.product.pk, self.other.pk], "index": "0"}
        with patch.object(self.owner, "has_change_permission", side_effect=lambda req, obj=None: obj != self.other):
            self.assertEqual(self.client.post(listing, data).status_code, 403)
        self.assertFalse(ProductPublicationRequest.objects.exists())
        for _ in range(2):
            self.assertEqual(self.client.post(listing, data).status_code, 302)
        self.assertEqual(ProductPublicationRequest.objects.filter(result="pending", submitted_by=self.editor).count(), 2)
        self.assertFalse(Product.objects.filter(status="active").exists())

    def test_csrf_and_invalid_requests_never_change_approval(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.editor)
        self.assertEqual(client.get(self.url, {"action": "submit", "request_id": 0}).status_code, 405)
        page = BeautifulSoup(client.get(self.board_url).content, "html.parser")
        form = page.select_one(f'button[formaction="{self.url}"]').find_parent("form")
        data = {"action": "submit", "request_id": form.select_one('[name="request_id"]')["value"]}
        self.assertEqual(client.post(self.url, data).status_code, 403)
        data["csrfmiddlewaretoken"] = form.select_one('[name="csrfmiddlewaretoken"]')["value"]
        self.assertEqual(client.post(self.url, data).status_code, 302)
        app = self.product.publication_requests.get()
        client.force_login(self.reviewer)
        self.assertEqual(client.post(self.url, {"action": "approve", "request_id": app.pk}).status_code, 403)
        for action, identifier in [("approve", "bad"), ("approve", -1), ("publish", app.pk)]:
            self.assertEqual(self.post(action, identifier).status_code, 400)
        app.refresh_from_db()
        self.assertEqual(app.result, "pending")

    def test_database_uniqueness_and_rollback_preserve_pending_application(self):
        app = self.submit()
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductPublicationRequest.objects.create(product=self.product, submitted_by=self.editor)
        self.client.force_login(self.reviewer)
        with patch.object(self.owner, "log_change", side_effect=RuntimeError("log failed")):
            with self.assertRaisesMessage(RuntimeError, "log failed"):
                self.post("approve", app.pk)
        self.product.refresh_from_db()
        app.refresh_from_db()
        self.assertEqual((self.product.status, app.result, app.reviewed_at), ("draft", "pending", None))

    @override_settings(ROOT_URLCONF="tests.multisite_urls")
    def test_current_admin_site_scopes_the_endpoint_and_redirect(self):
        from tests.multisite_urls import warehouse_site

        self.url = reverse("warehouse:catalog_product_publication", args=[self.product.pk])
        self.board_url = reverse("warehouse:catalog_product_status_board")
        app = self.submit()
        self.client.force_login(self.reviewer)
        review_url = reverse("review:catalog_product_publication", args=[self.product.pk])
        self.assertRedirects(self.client.post(review_url, {"action": "approve", "request_id": app.pk}),
                             reverse("review:login") + "?next=" + review_url, fetch_redirect_response=False)
        owner = warehouse_site.get_model_admin(Product)
        with patch.object(owner, "get_queryset", return_value=Product.objects.none()):
            self.assertEqual(self.post("approve", app.pk).status_code, 404)
        self.assertRedirects(self.post("approve", app.pk), self.board_url)
