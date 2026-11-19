from unittest.mock import patch

from bs4 import BeautifulSoup
from django.contrib import admin
from django.contrib.admin.models import CHANGE, DELETION, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from catalog.models import Category, Product, ProductPublicationRequest, ProductRecycleEntry, ProductVariant, Tag


class ProductRecycleBinTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        def staff(name, *permissions):
            user = get_user_model().objects.create_user(name, is_staff=True)
            user.user_permissions.add(*Permission.objects.filter(content_type__app_label="catalog", codename__in=permissions))
            return user

        cls.reader = staff("reader", "view_product")
        cls.deleter = staff("deleter", "view_product", "delete_product")
        cls.restorer = staff("restorer", "view_product", "restore_product")
        cls.editor = staff("editor", "change_product")
        cls.product = Product.objects.create(name="收纳盒 <蓝>", sku="BOX", price=12, stock=9,
                                             status=Product.Status.ACTIVE)
        cls.other = Product.objects.create(name="桌面小灯", sku="LIGHT", price=10)

    def setUp(self):
        self.owner = admin.site.get_model_admin(Product)
        self.list_url = reverse("admin:catalog_product_changelist")
        self.bin_url = reverse("admin:catalog_product_recycle_bin")
        self.client.force_login(self.deleter)

    def restore_url(self, product=None, site="admin"):
        entry = ProductRecycleEntry.objects.get(product=product or self.product)
        return reverse(f"{site}:catalog_product_restore", args=[entry.pk])

    def logs(self, flag):
        return LogEntry.objects.filter(action_flag=flag, object_id=str(self.product.pk))

    def test_delete_confirmation_then_restore_preserves_identity_and_relations(self):
        category = Category.objects.create(name="家居", slug="home")
        self.product.category = category
        self.product.save()
        tag = Tag.objects.create(name="新品", slug="new")
        self.product.tags.add(tag)
        variant = ProductVariant.objects.create(product=self.product, name="颜色", value="蓝")
        review = ProductPublicationRequest.objects.create(product=self.product, submitted_by=self.deleter,
            reviewed_by=self.deleter, reviewed_at=timezone.now(), result="approved")
        stamp = self.product.updated_at
        delete_url = reverse("admin:catalog_product_delete", args=[self.product.pk])
        self.assertContains(self.client.get(delete_url), "移入回收站")
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())
        self.assertEqual(self.client.post(delete_url, {"post": "yes"}).status_code, 302)
        self.assertEqual(self.logs(DELETION).count(), 1)
        self.assertEqual(list(Product.objects.all()), [self.other])
        self.assertFalse(category.products.exists())
        self.assertEqual(list(self.client.get(self.list_url).context["cl"].result_list), [self.other])
        # Even a change-form URL saved before deletion cannot open the recycled row.
        self.assertEqual(self.client.get(reverse("admin:catalog_product_change", args=[self.product.pk])).status_code, 302)
        self.client.force_login(self.restorer)
        self.assertRedirects(self.client.post(self.restore_url()), self.bin_url)
        live = Product.objects.get(pk=self.product.pk)
        self.assertEqual((live.sku, live.stock, live.status, live.updated_at), ("BOX", 9, "active", stamp))
        self.assertEqual(category.products.get(), live)
        self.assertEqual(live.tags.get(), tag)
        self.assertEqual(live.variants.get(), variant)
        self.assertEqual(live.publication_requests.get(), review)
        self.assertEqual(self.logs(CHANGE).get().user, self.restorer)
        self.assertContains(self.client.get(self.list_url), "收纳盒 &lt;蓝&gt;")

    def test_readonly_bin_entry_and_empty_state(self):
        self.client.force_login(self.reader)
        self.assertContains(self.client.get(self.bin_url), "回收站中暂无可查看的商品。")
        self.assertContains(self.client.get(self.list_url), f'href="{self.bin_url}"')
        self.assertNotContains(self.client.get(self.list_url, {"_popup": 1}), self.bin_url)
        self.product.delete()
        page = BeautifulSoup(self.client.get(self.bin_url).content, "html.parser")
        table = page.select_one('table[aria-label="回收站商品"]')
        self.assertEqual(table.select_one("tbody th").text, self.product.name)
        self.assertIsNotNone(table.select_one("time[datetime]"))
        self.assertNotIn(self.other.name, table.get_text())
        self.assertIsNone(table.select_one("form,button"))
        for user in (self.reader, self.deleter, self.editor):
            self.client.force_login(user)
            self.assertEqual(self.client.post(self.restore_url()).status_code, 403)
        self.assertFalse(Product.objects.filter(pk=self.product.pk).exists())

    def test_duplicate_restore_and_old_form_after_another_deletion(self):
        self.product.delete()
        self.client.force_login(self.restorer)
        first = self.restore_url()
        self.assertEqual(self.client.post(first).status_code, 302)
        self.assertEqual(self.client.post(first).status_code, 404)
        self.product.delete()
        self.assertNotEqual(first, self.restore_url())
        self.assertEqual(self.client.post(first).status_code, 404)
        self.assertFalse(Product.objects.filter(pk=self.product.pk).exists())
        self.assertEqual(self.logs(CHANGE).count(), 1)

    def test_permission_filtered_rows_and_scope_rechecked_on_restore(self):
        Product.objects.all().delete()
        self.client.force_login(self.restorer)
        queryset = self.owner.get_queryset
        with patch.object(self.owner, "get_queryset", side_effect=lambda request: queryset(request).exclude(pk=self.product.pk)):
            self.assertEqual([r["product"] for r in self.client.get(self.bin_url).context["rows"]], [self.other])
            self.assertEqual(self.client.post(self.restore_url()).status_code, 404)
        with patch.object(self.owner, "has_view_or_change_permission", side_effect=lambda request, obj=None: obj is None):
            self.assertContains(self.client.get(self.bin_url), "回收站中暂无可查看的商品。")
            self.assertEqual(self.client.post(self.restore_url()).status_code, 404)
        with patch.object(self.owner, "has_restore_permission", side_effect=lambda request, obj=None: obj != self.product):
            page = self.client.get(self.bin_url)
            self.assertNotContains(page, self.restore_url())
            self.assertContains(page, self.restore_url(self.other))
            self.assertEqual(self.client.post(self.restore_url()).status_code, 403)
        self.assertFalse(LogEntry.objects.exists())
        self.assertEqual(ProductRecycleEntry.objects.count(), 2)

    def test_module_view_permission_and_revocation(self):
        self.product.delete()
        self.client.force_login(self.restorer)
        url = self.restore_url()
        self.assertContains(self.client.get(self.bin_url), f'action="{url}"')
        self.restorer.user_permissions.remove(Permission.objects.get(codename="view_product"))
        self.assertEqual(self.client.get(self.bin_url).status_code, 403)
        self.assertEqual(self.client.post(url).status_code, 403)
        self.client.force_login(self.deleter)
        with patch.object(self.owner, "has_module_permission", return_value=False):
            self.assertEqual(self.client.get(self.bin_url).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.bin_url).status_code, 302)
        self.assertFalse(Product.objects.filter(pk=self.product.pk).exists())

    def test_restore_form_csrf_and_methods(self):
        self.product.delete()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.restorer)
        page = BeautifulSoup(client.get(self.bin_url).content, "html.parser")
        form = page.select_one('table form[method="post"]')
        url = form["action"]
        self.assertEqual(form.button["aria-label"], f"还原「{self.product.name}」")
        self.assertEqual(client.get(url).status_code, 405)
        self.assertEqual(client.post(url).status_code, 403)
        self.assertEqual(client.post(url, {"csrfmiddlewaretoken": form.select_one("input")["value"]}).status_code, 302)
        self.assertEqual(self.logs(CHANGE).count(), 1)

    def test_audit_failure_rolls_back_restore_and_bulk_deletion(self):
        queryset_delete = type(Product.objects.all()).delete
        def fail_after_write(queryset):
            queryset_delete(queryset)
            raise RuntimeError("failed")

        data = {"action": "delete_selected", "_selected_action": [self.product.pk, self.other.pk], "post": "yes"}
        with patch.object(type(Product.objects.all()), "delete", fail_after_write), self.assertRaises(RuntimeError):
            self.client.post(self.list_url, data)
        self.assertFalse(ProductRecycleEntry.objects.exists())
        self.assertFalse(LogEntry.objects.exists())
        self.product.delete()
        self.client.force_login(self.restorer)
        with patch.object(self.owner, "log_change", side_effect=RuntimeError("audit")), self.assertRaises(RuntimeError):
            self.client.post(self.restore_url())
        self.assertTrue(ProductRecycleEntry.objects.filter(product=self.product).exists())
        self.assertFalse(LogEntry.objects.exists())

    def test_select_across_cannot_recycle_a_newly_matching_product(self):
        log = self.owner.log_deletions

        def audit(request, products):
            log(request, products)
            Product.objects.create(name="刚创建", sku="JUST-ADDED", price=2)

        data = {"action": "delete_selected", "_selected_action": [self.product.pk], "select_across": "1", "post": "yes"}
        with patch.object(self.owner, "log_deletions", side_effect=audit):
            self.assertEqual(self.client.post(self.list_url, data).status_code, 302)
        self.assertEqual(list(Product.objects.values_list("sku", flat=True)), ["JUST-ADDED"])
        self.assertEqual(ProductRecycleEntry.objects.count(), 2)

    def test_full_batch_rejected_if_object_delete_or_view_permission_missing(self):
        data = {"action": "delete_selected", "_selected_action": [self.product.pk, self.other.pk]}
        for hook in ("has_delete_permission", "has_view_or_change_permission"):
            with patch.object(self.owner, hook, side_effect=lambda request, obj=None: obj != self.other):
                self.assertEqual(self.client.post(self.list_url, data).status_code, 403)
                self.assertEqual(self.client.post(self.list_url, {**data, "post": "yes"}).status_code, 403)
        self.assertFalse(LogEntry.objects.exists())
        self.assertFalse(ProductRecycleEntry.objects.exists())

    def test_orm_deletions_idempotent_and_reserved_sku_validated(self):
        stale = Product.objects.get(pk=self.product.pk)
        self.assertEqual(self.product.delete(), (1, {"catalog.Product": 1}))
        entry = ProductRecycleEntry.objects.get(product=self.product)
        self.assertEqual(self.product.delete(), (0, {}))
        stale.save()
        self.assertFalse(Product.objects.filter(pk=self.product.pk).exists())
        self.assertEqual(Product.all_objects.all().delete(), (1, {"catalog.Product": 1}))
        self.assertEqual(ProductRecycleEntry.objects.get(product=self.product).pk, entry.pk)
        with self.assertRaises(ValidationError) as error:
            Product(name="另一个盒子", sku="BOX", price=2).full_clean()
        self.assertIn("sku", error.exception.message_dict)

    def test_other_product_workflows_exclude_recycled_products_until_restore(self):
        day = timezone.localdate().isoformat()
        ProductPublicationRequest.objects.create(product=self.product, submitted_by=self.deleter,
            reviewed_by=self.deleter, reviewed_at=timezone.now(), result="approved")
        self.product.delete()
        self.client.force_login(self.restorer)
        def counts():
            kpi = BeautifulSoup(self.client.get(reverse("admin:index")).content, "html.parser")
            board = self.client.get(reverse("admin:catalog_product_status_board")).context["lanes"]
            daily = self.client.get(reverse("admin:catalog_product_publication_calendar"), {"day": day})
            return (kpi.select_one(".nova-kpis dd").get_text(strip=True),
                    sum(len(lane["cards"]) for lane in board), len(daily.context["details"]))
        self.assertEqual(counts(), ("1", 1, 0))
        self.assertEqual(self.client.post(self.restore_url()).status_code, 302)
        self.assertEqual(counts(), ("2", 2, 1))

    @override_settings(ROOT_URLCONF="tests.multisite_urls")
    def test_urls_and_scopes_belong_to_current_registration(self):
        from tests.multisite_urls import warehouse_site
        self.product.delete()
        self.client.force_login(self.restorer)
        warehouse = reverse("warehouse:catalog_product_recycle_bin")
        url = self.restore_url(site="warehouse")
        self.assertContains(self.client.get(warehouse), f'action="{url}"')
        with patch.object(warehouse_site.get_model_admin(Product), "get_queryset", return_value=Product.all_objects.none()):
            self.assertEqual(self.client.post(url).status_code, 404)
        self.assertEqual(self.client.post(self.restore_url(site="review")).status_code, 302)
        self.assertRedirects(self.client.post(url), warehouse)
