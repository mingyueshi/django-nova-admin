from unittest.mock import patch

from bs4 import BeautifulSoup
from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase
from django.urls import reverse

from catalog.models import Product


class ProductNameCopyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        def staff(name, permission):
            user = get_user_model().objects.create_user(name, is_staff=True)
            user.user_permissions.add(Permission.objects.get(codename=permission))
            return user

        cls.editor = staff("translator", "change_product")
        cls.reader = staff("name-reader", "view_product")
        cls.product = Product.objects.create(name="桌灯", sku="NAME-01", price=10)

    def setUp(self):
        self.client.force_login(self.editor)
        self.url = reverse("admin:catalog_product_change", args=[self.product.pk])
        self.owner = admin.site.get_model_admin(Product)

    def post(self, **updates):
        return self.client.post(self.url, {
            "name": "桌灯", "sku": self.product.sku, "price": "10", "stock": "0", "status": "draft",
            "initial-status": "draft", "_save": "Save", **updates,
        })

    def confirmation(self, response):
        self.assertContains(response, "请核对并确认覆盖")
        page = BeautifulSoup(response.content, "html.parser")
        self.assertTrue(page.select_one('[name="_copy_name"]').has_attr("checked"))
        checkbox = page.select_one('[name="_confirm_name_copy"]')
        self.assertFalse(checkbox.has_attr("checked"))
        return checkbox["value"]

    def assert_names(self, chinese, english):
        self.product.refresh_from_db()
        self.assertEqual((self.product.name, self.product.name_en), (chinese, english))

    def test_empty_target_copies_edited_source_through_native_save(self):
        page = BeautifulSoup(self.client.get(self.url).content, "html.parser")
        self.assertEqual(page.select_one('[name="name_en"]')["maxlength"], "120")
        self.assertFalse(page.select_one('[name="_copy_name"]').has_attr("checked"))
        self.assertEqual(self.post(name="  新桌灯  ", name_en="", _copy_name="1").status_code, 302)
        self.assert_names("新桌灯", "新桌灯")
        self.assertIn("英文名称", LogEntry.objects.get().get_change_message())

    def test_existing_and_unsaved_translations_require_explicit_confirmation(self):
        for stored, typed in [("Desk lamp", "Desk lamp"), ("Desk lamp", ""), ("", "Unsaved translation")]:
            with self.subTest(stored=stored, typed=typed):
                Product.objects.filter(pk=self.product.pk).update(name_en=stored)
                data = {"_copy_name": "1", "name_en": typed, "stock": "3"}
                token = self.confirmation(self.post(**data))
                self.assert_names("桌灯", stored)
                self.assertEqual(self.product.stock, 0)
                self.assertEqual(self.post(**data, _confirm_name_copy=token).status_code, 302)
                self.assert_names("桌灯", "桌灯")
                self.assertEqual(self.product.stock, 3)
                Product.objects.filter(pk=self.product.pk).update(stock=0)

    def test_empty_source_or_invalid_product_never_saves_a_partial_copy(self):
        Product.objects.filter(pk=self.product.pk).update(name_en="Lamp")
        for source in ("", "   ", "灯" * 121):
            with self.subTest(source=source):
                response = self.post(name=source, name_en="Lamp", _copy_name="1")
                self.assertIn("name", response.context["adminform"].form.errors)
                self.assert_names("桌灯", "Lamp")
        token = self.confirmation(self.post(name_en="Lamp", _copy_name="1"))
        response = self.post(name_en="Lamp", _copy_name="1", _confirm_name_copy=token, stock="-1")
        self.assertIn("stock", response.context["adminform"].form.errors)
        page = BeautifulSoup(response.content, "html.parser")
        checkbox = page.select_one('[name="_confirm_name_copy"][checked]')
        self.assertEqual(checkbox["value"], token)
        self.assert_names("桌灯", "Lamp")

    def test_confirmation_is_bound_to_reviewed_record_source_and_targets(self):
        Product.objects.filter(pk=self.product.pk).update(name_en="Lamp")
        data = {"name_en": "Lamp", "_copy_name": "1"}
        token = self.confirmation(self.post(**data))
        for changes in [{"_confirm_name_copy": "1"}, {"name": "新灯"}, {"name_en": "New draft"}]:
            response = self.post(**{**data, "_confirm_name_copy": token, **changes})
            self.confirmation(response)
            self.assert_names("桌灯", "Lamp")
        other = Product.objects.create(name="桌灯", name_en="Lamp", sku="NAME-02", price=10)
        other_post = self.client.post(reverse("admin:catalog_product_change", args=[other.pk]), {
            **data, "sku": other.sku, "name": other.name, "price": 10, "stock": 0, "status": "draft",
            "_confirm_name_copy": token,
        })
        self.confirmation(other_post)
        other.refresh_from_db()
        self.assertEqual(other.name_en, "Lamp")
        Product.objects.filter(pk=self.product.pk).update(name_en="Revised")
        self.confirmation(self.post(**data, _confirm_name_copy=token))
        self.assert_names("桌灯", "Revised")

    def test_cancel_manual_translation_and_older_forms(self):
        Product.objects.filter(pk=self.product.pk).update(name_en="Lamp")
        self.confirmation(self.post(name_en="Lamp", _copy_name="1"))
        self.assertEqual(self.post(name_en="Lamp", _initial_name_en="Lamp", stock="2").status_code, 302)
        self.assert_names("桌灯", "Lamp")
        self.confirmation(self.post(name_en="桌灯"))
        self.assertEqual(self.post(name_en="Desk lamp").status_code, 302)
        self.assert_names("桌灯", "Desk lamp")
        for data in ({}, {"name_en": "Lamp", "_initial_name_en": "Lamp"}):
            self.assertEqual(self.post(stock="4", **data).status_code, 302)
            self.assert_names("桌灯", "Desk lamp")
        self.assertEqual(self.post(name_en="", _initial_name_en="Desk lamp").status_code, 302)
        self.assert_names("桌灯", "")

    def test_read_only_object_permissions_and_scope_on_get_and_post(self):
        Product.objects.filter(pk=self.product.pk).update(name_en="Desk lamp")
        self.client.force_login(self.reader)
        page = BeautifulSoup(self.client.get(self.url).content, "html.parser")
        self.assertEqual(page.select_one(".field-name_en .readonly").get_text(strip=True), "Desk lamp")
        self.assertIsNone(page.select_one('[name="name_en"], [name="_copy_name"], [name="_confirm_name_copy"]'))
        for data in ({"name_en": "forged"}, {"_copy_name": "1", "_confirm_name_copy": "1"}):
            self.assertEqual(self.post(**data).status_code, 403)
        self.client.force_login(self.editor)
        with patch.object(self.owner, "has_change_permission", side_effect=lambda req, obj=None: obj is None):
            self.assertEqual(self.post(_copy_name="1").status_code, 403)
        with patch.object(self.owner, "get_queryset", return_value=Product.objects.none()):
            self.assertNotContains(self.client.get(self.url), "Desk lamp", status_code=302)
            self.assertEqual(self.post(_copy_name="1").status_code, 302)
        for field in ("name", "name_en"):
            with patch.object(self.owner, "get_readonly_fields", return_value=[*self.owner.readonly_fields, field]):
                self.assertNotContains(self.client.get(self.url), 'name="_copy_name"')
                self.assertEqual(self.post(_copy_name="1").status_code, 403)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.editor)
        self.assertEqual(csrf_client.post(self.url, {"_copy_name": "1"}).status_code, 403)
        self.assert_names("桌灯", "Desk lamp")

    def test_translation_changed_during_save_aborts_whole_copy(self):
        save_model = self.owner.save_model

        def translate_before_save(request, obj, form, change):
            Product.objects.filter(pk=obj.pk).update(name_en="Concurrent translation")
            return save_model(request, obj, form, change)

        with patch.object(self.owner, "save_model", side_effect=translate_before_save):
            self.assertEqual(self.post(_copy_name="1", stock=5).status_code, 409)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 0)
        self.assertFalse(LogEntry.objects.exists())
