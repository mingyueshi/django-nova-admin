from unittest.mock import patch

from bs4 import BeautifulSoup
from django.contrib import admin
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from catalog.models import Product


class ProductBoardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.reader = get_user_model().objects.create_user("board-reader", is_staff=True)
        cls.reader.user_permissions.add(Permission.objects.get(codename="view_product"))
        cls.editor = get_user_model().objects.create_user("board-editor", is_staff=True)
        cls.editor.user_permissions.add(Permission.objects.get(codename="change_product"))
        cls.draft = Product.objects.create(name="样品 <A>", sku="D-01", price=1, stock=7)
        cls.active = Product.objects.create(name="上架样品", sku="A-01", price=2, status=Product.Status.ACTIVE)

    def setUp(self):
        self.url = reverse("admin:catalog_product_status_board")
        self.owner = admin.site.get_model_admin(Product)
        self.client.force_login(self.editor)

    def transition(self, **updates):
        return {"product_id": self.draft.pk, "previous_status": "draft", "status": "archived", **updates}

    def board(self, url=None):
        response = self.client.get(url or self.url)
        self.assertEqual(response.status_code, 200)
        return BeautifulSoup(response.content, "html.parser").select_one(".product-board")

    def test_read_only_list_entry_cards_and_empty_lane(self):
        self.client.force_login(self.reader)
        listing = reverse("admin:catalog_product_changelist")
        self.assertContains(self.client.get(listing), f'href="{self.url}"')
        self.assertNotContains(self.client.get(listing, {"_popup": "1"}), self.url)
        board = self.board()
        self.assertEqual([h.get_text(strip=True) for h in board.select("h2")], ["草稿1 件", "已上架1 件", "已归档0 件"])
        self.assertEqual([a.text for a in board.select("li a")], [self.draft.name, self.active.name])
        self.assertEqual(board.select_one("li a")["href"], reverse("admin:catalog_product_change", args=[self.draft.pk]))
        self.assertEqual(board.select_one(".product-board-empty").text, "此状态下暂无商品。")
        self.assertIsNone(board.select_one("form,select,button"))
        self.assertEqual(self.client.post(self.url, self.transition()).status_code, 403)

    def test_state_changes_move_one_card_and_log_only_real_changes(self):
        for source, target in [("draft", "archived"), ("archived", "draft")]:
            with self.subTest(source=source, target=target):
                data = self.transition(previous_status=source, status=target, stock=0)
                before = self.draft.updated_at
                response = self.client.post(self.url, data, follow=True)
                self.assertEqual(response.redirect_chain, [(self.url, 302)])
                self.draft.refresh_from_db()
                self.assertEqual((self.draft.status, self.draft.stock), (target, 7))
                self.assertGreater(self.draft.updated_at, before)
                soup = BeautifulSoup(response.content, "html.parser")
                cards = soup.select(f'section[aria-labelledby="lane-{target}"] li a')
                self.assertIn(self.draft.name, [card.text for card in cards])
                detail = reverse("admin:catalog_product_change", args=[self.draft.pk])
                self.assertEqual(len(soup.select(f'.product-board a[href="{detail}"]')), 1)
        logs = LogEntry.objects.filter(user=self.editor, object_id=str(self.draft.pk), action_flag=CHANGE)
        self.assertEqual(logs.count(), 2)
        self.assertIn("状态", logs.first().get_change_message())
        stamp = self.draft.updated_at
        self.assertEqual(self.client.post(self.url, self.transition(status="draft")).status_code, 302)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.updated_at, stamp)
        self.assertEqual(logs.count(), 2)

    def test_queryset_and_object_visibility_filter_cards_counts_and_submissions(self):
        archived = Product.objects.create(name="不可见商品", sku="PRIVATE", price=1, status=Product.Status.ARCHIVED)
        with patch.object(self.owner, "get_queryset", return_value=Product.objects.exclude(pk=self.draft.pk)), patch.object(
            self.owner, "has_view_or_change_permission", side_effect=lambda request, obj=None: obj != archived
        ):
            board = self.board()
            self.assertEqual([h.small.text for h in board.select("h2")], ["0 件", "1 件", "0 件"])
            for hidden in (self.draft, archived):
                self.assertNotIn(hidden.name, board.get_text())
                self.assertNotIn(hidden.sku, board.get_text())
                response = self.client.post(self.url, self.transition(product_id=hidden.pk))
                self.assertEqual(response.status_code, 404)
        self.assertFalse(LogEntry.objects.exists())
        self.draft.refresh_from_db()
        archived.refresh_from_db()
        self.assertEqual((self.draft.status, archived.status), ("draft", "archived"))

    def test_all_hidden_has_same_empty_board_as_empty_database(self):
        with patch.object(self.owner, "has_view_or_change_permission", side_effect=lambda request, obj=None: obj is None):
            hidden = self.client.get(self.url)
        Product.objects.all().delete()
        empty = self.client.get(self.url)
        for response in (hidden, empty):
            self.assertContains(response, "暂无可查看的商品。")
            board = BeautifulSoup(response.content, "html.parser").select_one(".product-board")
            self.assertEqual([h.small.text for h in board.select("h2")], ["0 件"] * 3)
            self.assertIsNone(board.select_one("li,form"))

    def test_object_and_field_editability_rechecked_after_opening_board(self):
        self.assertEqual(len(self.board().select("form")), 2)
        with patch.object(self.owner, "has_change_permission", side_effect=lambda request, obj=None: obj != self.draft):
            board = self.board()
            self.assertIn(self.draft.name, board.get_text())
            self.assertIsNone(board.select_one('section[aria-labelledby="lane-draft"] form'))
            self.assertIsNotNone(board.select_one('section[aria-labelledby="lane-active"] form'))
            self.assertEqual(self.client.post(self.url, self.transition()).status_code, 403)
        with patch.object(self.owner, "get_readonly_fields", return_value=["status"]):
            self.assertIsNone(self.board().select_one("form"))
            self.assertEqual(self.client.post(self.url, self.transition()).status_code, 403)
        self.editor.user_permissions.set(self.reader.user_permissions.all())
        self.assertEqual(self.client.post(self.url, self.transition()).status_code, 403)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, "draft")
        self.assertFalse(LogEntry.objects.exists())

    def test_model_module_and_column_visibility(self):
        with patch.object(self.owner, "get_list_display", return_value=["name", "status_badge"]):
            self.assertIsNone(self.board().select_one(".product-board-sku"))
        for method, value in [("has_module_permission", False), ("get_list_display", ["name"])]:
            with self.subTest(method=method), patch.object(self.owner, method, return_value=value):
                self.assertEqual(self.client.get(self.url).status_code, 403)
                self.assertEqual(self.client.post(self.url, self.transition()).status_code, 403)
        self.editor.user_permissions.clear()
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, self.transition()).status_code, 403)
        self.client.logout()
        self.assertRedirects(self.client.get(self.url), reverse("admin:login") + "?next=" + self.url)

    def test_invalid_transitions_get_and_unsupported_method_do_not_write(self):
        self.assertEqual(self.client.get(self.url, self.transition()).status_code, 200)
        self.assertEqual(self.client.put(self.url, self.transition()).status_code, 405)
        for data in ({}, self.transition(status="unknown"), self.transition(previous_status="unknown"),
                     self.transition(product_id="invalid"), self.transition(product_id=2**64)):
            self.assertEqual(self.client.post(self.url, data).status_code, 400)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, "draft")
        self.assertFalse(LogEntry.objects.exists())

    def test_stale_submission_shows_current_lane_without_overwriting(self):
        self.assertEqual(self.client.post(self.url, self.transition(status="archived")).status_code, 302)
        response = self.client.post(self.url, self.transition())
        self.assertContains(response, "请核对最新状态", status_code=409)
        soup = BeautifulSoup(response.content, "html.parser")
        self.assertEqual(soup.select_one('section[aria-labelledby="lane-archived"] li a').text, self.draft.name)
        self.assertEqual(LogEntry.objects.count(), 1)

    def test_concurrent_change_after_permission_check_preserves_new_status(self):
        def finish_other_edit(request, obj):
            if obj.pk == self.draft.pk and obj.status == "draft":
                Product.objects.filter(pk=obj.pk).update(status="archived")
            return []

        with patch.object(self.owner, "get_readonly_fields", side_effect=finish_other_edit):
            response = self.client.post(self.url, self.transition())
        self.assertEqual(response.status_code, 409)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, "archived")
        self.assertFalse(LogEntry.objects.exists())

    def test_audit_failure_rolls_back_status_and_timestamp(self):
        with patch.object(self.owner, "log_change", side_effect=RuntimeError("audit failed")):
            with self.assertRaisesMessage(RuntimeError, "audit failed"):
                self.client.post(self.url, self.transition())
        stamp = self.draft.updated_at
        self.draft.refresh_from_db()
        self.assertEqual((self.draft.status, self.draft.updated_at), ("draft", stamp))

    def test_csrf_protection_and_post_from_rendered_form(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.editor)
        page = BeautifulSoup(client.get(self.url).content, "html.parser")
        form = page.select_one('section[aria-labelledby="lane-draft"] form')
        self.assertEqual(form["method"], "post")
        buttons = form.select('button[type="submit"][name="status"]')
        self.assertEqual([button["value"] for button in buttons], ["archived"])
        archive = buttons[0]
        self.assertEqual(archive["aria-label"], f"归档「{self.draft.name}」")
        data = {field["name"]: field["value"] for field in form.select("input")}
        token = data.pop("csrfmiddlewaretoken")
        data[archive["name"]] = archive["value"]
        self.assertEqual(client.post(self.url, data).status_code, 403)
        self.assertEqual(client.post(self.url, {**data, "csrfmiddlewaretoken": token}).status_code, 302)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, "archived")

    @override_settings(ROOT_URLCONF="tests.multisite_urls")
    def test_site_registration_controls_data_links_and_writes(self):
        from tests.multisite_urls import warehouse_site

        warehouse = reverse("warehouse:catalog_product_status_board")
        review = reverse("review:catalog_product_status_board")
        owner = warehouse_site.get_model_admin(Product)
        with patch.object(owner, "get_queryset", return_value=Product.objects.filter(pk=self.active.pk)):
            self.assertContains(self.client.get(reverse("warehouse:catalog_product_changelist")), f'href="{warehouse}"')
            board = self.board(warehouse)
            self.assertEqual([a["href"] for a in board.select("li a")], [
                reverse("warehouse:catalog_product_change", args=[self.active.pk])
            ])
            self.assertEqual(self.client.post(warehouse, self.transition()).status_code, 404)
        self.assertEqual(self.client.get(review).status_code, 302)
        self.assertEqual(self.client.post(review, self.transition()).status_code, 302)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.status, "draft")
