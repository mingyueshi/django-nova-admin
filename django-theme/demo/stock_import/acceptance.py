import csv
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import Product
from .models import StockPreview


class StockImportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.editor = get_user_model().objects.create_user("editor", is_staff=True)
        cls.editor.user_permissions.add(*Permission.objects.filter(codename__in=("change_product", "import_stock")))
        cls.a = Product.objects.create(name="A", sku="A", price=10, stock=3)
        cls.b = Product.objects.create(name="B", sku="B", price=11, stock=4)

    def setUp(self):
        self.client.force_login(self.editor)
        self.start = reverse("admin:catalog_product_import_upload")
        self.owner = admin.site.get_model_admin(Product)

    def upload(self, data=b"sku,stock\nA,9\nB,20\n"):
        return self.client.post(self.start, {"file": SimpleUploadedFile("stock.csv", data)})

    def stage(self, **kwargs):
        result = self.upload(**kwargs)
        self.assertEqual(result.status_code, 302)
        batch = self.client.get(result.url).context["batch"]
        urls = {name: reverse("admin:catalog_product_import_" + name, args=[batch.pk])
                for name in ("preview", "confirm", "validate", "errors", "result")}

        if batch.rows and not batch.errors:
            urls["review"] = self.client.get(urls["preview"]).context["signature"]
        return urls

    def confirm(self, urls, **data):
        return self.client.post(urls["confirm"], {"review": urls.get("review", ""), **data})

    def stocks(self):
        return list(Product.objects.order_by("sku").values_list("stock", flat=True))

    def test_four_steps_real_changes_and_retry(self):
        self.assertContains(self.client.get(reverse("admin:catalog_product_changelist")), self.start)
        self.assertContains(self.client.get(self.start), "multipart/form-data")
        urls = self.stage()
        self.assertContains(self.client.get(urls["validate"]), urls["preview"])
        preview = self.client.get(urls["preview"])
        self.assertContains(preview, urls["confirm"])
        self.assertEqual([(row["old"], row["new"]) for row in preview.context["batch"].rows], [(3, 9), (4, 20)])
        self.assertEqual(self.stocks(), [3, 4])
        self.assertEqual(self.client.get(urls["confirm"]).status_code, 405)
        for _ in range(2):
            result = self.confirm(urls, stock=9999)
            self.assertRedirects(result, urls["result"])
        self.assertEqual(self.stocks(), [9, 20])
        self.assertEqual(LogEntry.objects.filter(user=self.editor).count(), 2)

    def test_invalid_batch_has_line_errors_and_safe_csv(self):
        Product.objects.create(name="valid", sku="B2", stock=5, price=0)
        urls = self.stage(data=b"sku,stock\nA,7\nB,-2\nA,4\nUNKNOWN,1\n=1,2\nB2,0\n")
        self.assertContains(self.client.get(urls["validate"]), "错误 5 条")
        file = self.client.get(urls["errors"])
        rows = list(csv.reader(StringIO(file.content.decode("utf-8-sig"))))
        self.assertEqual([row[:2] for row in rows[1:]], [["2", "A"], ["3", "B"], ["4", "A"], ["5", "UNKNOWN"], ["6", "TEXT: =1"]])
        self.assertEqual(self.confirm(urls).status_code, 400)
        self.assertEqual(self.client.get(urls["preview"]).status_code, 404)
        self.assertEqual(self.stocks(), [3, 4, 5])
        partial = self.client.get(urls["preview"], {"skip": "1"})
        urls["review"] = partial.context["signature"]
        self.assertRedirects(self.confirm(urls), urls["result"])
        self.assertEqual(self.stocks(), [3, 4, 0])

    def test_file_limits_and_exact_columns(self):
        for data in (b"sku,status\nA,1", b"sku,stock,stock\nA,1,1", b"sku,stock\n",
                     b"x" * (256 * 1024 + 1), b"sku,stock\n" + b"A,1\n" * 501, b"sku,stock\n\xff,1"):
            self.assertEqual(self.upload(data).status_code, 400)
        self.assertFalse(StockPreview.objects.exists())

    def test_stale_hidden_recycled_or_expired_preview(self):
        urls = self.stage()
        with patch.object(self.owner, "get_queryset", return_value=Product.objects.exclude(pk=self.b.pk)):
            self.assertEqual(self.client.get(urls["preview"]).status_code, 409)
            self.assertEqual(self.confirm(urls).status_code, 409)
        with patch.object(self.owner, "get_readonly_fields", return_value=("stock",)):
            self.assertEqual(self.confirm(urls).status_code, 409)
        Product.objects.filter(pk=self.b.pk).update(stock=7)
        self.assertEqual(self.confirm(urls).status_code, 409)
        self.assertEqual(self.stocks(), [3, 7])
        self.b.delete()
        self.assertEqual(self.confirm(urls).status_code, 409)
        self.assertContains(self.client.get(self.stage()["validate"]), "找不到可操作的商品")
        StockPreview.objects.update(created_at=timezone.now() - timedelta(hours=1))
        self.assertEqual(self.confirm(urls).status_code, 404)
        self.assertFalse(LogEntry.objects.exists())

    def test_audit_failure_rolls_back_updates_and_claim(self):
        urls = self.stage()
        with patch.object(self.owner, "log_change", side_effect=[None, RuntimeError("audit")]):
            with self.assertRaisesMessage(RuntimeError, "audit"):
                self.confirm(urls)
        self.assertEqual(self.stocks(), [3, 4])
        self.assertFalse(StockPreview.objects.get().submitted)
        self.assertRedirects(self.confirm(urls), urls["result"])

    def test_owner_permissions_and_csrf(self):
        urls = self.stage()
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.editor)
        self.assertEqual(csrf.post(urls["confirm"]).status_code, 403)
        other = get_user_model().objects.create_superuser("another", password="test")
        self.client.force_login(other)
        self.assertEqual(self.client.get(urls["preview"]).status_code, 404)
        self.assertEqual(self.confirm(urls).status_code, 404)
        self.client.force_login(self.editor)
        self.editor.user_permissions.remove(Permission.objects.get(codename="import_stock"))
        self.assertNotContains(self.client.get(reverse("admin:catalog_product_changelist")), self.start)
        self.assertEqual(self.confirm(urls).status_code, 403)
