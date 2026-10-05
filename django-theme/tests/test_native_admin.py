"""Exercise Django's real admin views, forms and permission checks in every skin.

These tests intentionally use ModelAdmin's public endpoints and POST contracts.
The theme must never replace the native implementation of these workflows.
"""
from decimal import Decimal

from django.contrib import admin
from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.contrib.admin.widgets import AutocompleteSelect, FilteredSelectMultiple
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase
from django.urls import reverse

from catalog.models import Category, Product, ProductVariant, Tag
from nova_admin.preferences import SESSION_KEY


MODES = ("dark", "light", "native")


class NativeAdminWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = get_user_model().objects.create_superuser(
            username="native-workflow-admin", email="admin@example.invalid", password="test-only-2xB!"
        )
        cls.staff = get_user_model().objects.create_user(
            username="native-workflow-staff", password="test-only-4hF!", is_staff=True
        )
        cls.category = Category.objects.create(name="Accessories", slug="accessories")
        cls.second_category = Category.objects.create(name="Furniture", slug="furniture")
        cls.tag = Tag.objects.create(name="Featured", slug="featured")
        cls.second_tag = Tag.objects.create(name="Limited", slug="limited")
        cls.product = Product.objects.create(
            name="Native workflows", sku="WORKFLOW-001", price=Decimal("49.00"),
            stock=8, category=cls.category,
        )
        cls.product.tags.add(cls.tag)
        cls.variant = ProductVariant.objects.create(product=cls.product, name="Color", value="Blue")

    def setUp(self):
        self.client.force_login(self.superuser)
        self.list_url = reverse("admin:catalog_product_changelist")
        self.change_url = reverse("admin:catalog_product_change", args=[self.product.pk])
        self.add_url = reverse("admin:catalog_product_add")

    def set_mode(self, mode):
        session = self.client.session
        session[SESSION_KEY] = mode
        session.save()

    def grant(self, *codenames):
        self.staff.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="catalog", codename__in=codenames,
        ))
        self.client.force_login(self.staff)

    def product_data(self, *, adding=False, **overrides):
        data = {
            "name": "Saved through native admin", "sku": "WORKFLOW-NEW" if adding else self.product.sku,
            "price": "59.50", "stock": "12", "status": "active",
            "category": str(self.second_category.pk), "tags": [str(self.tag.pk), str(self.second_tag.pk)],
            "_save": "Save", "variants-TOTAL_FORMS": "1",
            "variants-INITIAL_FORMS": "0" if adding else "1",
            "variants-MIN_NUM_FORMS": "0", "variants-MAX_NUM_FORMS": "1000",
            "variants-0-name": "Color", "variants-0-value": "Green",
        }
        if not adding:
            data.update({"variants-0-id": str(self.variant.pk), "variants-0-product": str(self.product.pk)})
        data.update(overrides)
        return data

    def test_foreign_key_many_to_many_and_native_widget_assets(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                self.set_mode(mode)
                response = self.client.get(self.change_url)
                self.assertEqual(response.status_code, 200)
                form = response.context["adminform"].form
                self.assertIsInstance(form.fields["category"].widget.widget, AutocompleteSelect)
                self.assertIsInstance(form.fields["tags"].widget.widget, FilteredSelectMultiple)
                self.assertContains(response, 'data-field-name="category"')
                self.assertContains(response, 'name="tags"')
                self.assertContains(response, "admin/js/autocomplete.js")
                self.assertContains(response, "admin/js/SelectFilter2.js")
                self.assertContains(response, "admin/js/vendor/select2/")
                self.assertEqual(form.initial["category"], self.category.pk)
                self.assertEqual(list(form.initial["tags"]), [self.tag])

    def test_fieldsets_readonly_and_tabular_inline_structure(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                self.set_mode(mode)
                response = self.client.get(self.change_url)
                fieldsets = list(response.context["adminform"])
                self.assertEqual([fieldset.name for fieldset in fieldsets], ["商品信息", "价格与库存", "维护信息"])
                self.assertIn("collapse", fieldsets[-1].classes)
                self.assertNotIn("updated_at", response.context["adminform"].form.fields)
                self.assertContains(response, 'class="readonly"')
                self.assertNotContains(response, 'name="updated_at"')
                inline = response.context["inline_admin_formsets"][0]
                self.assertIsInstance(inline.opts, admin.TabularInline)
                self.assertEqual(inline.formset.prefix, "variants")
                self.assertEqual(inline.formset.initial_form_count(), 1)
                self.assertContains(response, "tabular inline-related")
                self.assertContains(response, 'name="variants-0-id"')
                self.assertContains(response, 'name="variants-0-DELETE"')
                self.assertContains(response, "admin/js/inlines.js")

    def test_add_saves_foreign_key_many_to_many_inline_and_audit_log(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                self.set_mode(mode)
                sku = f"CREATED-{mode}"
                response = self.client.post(self.add_url, self.product_data(adding=True, sku=sku))
                self.assertRedirects(response, self.list_url)
                product = Product.objects.get(sku=sku)
                self.assertEqual(product.category, self.second_category)
                self.assertEqual(set(product.tags.all()), {self.tag, self.second_tag})
                self.assertEqual(list(product.variants.values_list("name", "value")), [("Color", "Green")])
                entry = LogEntry.objects.get(object_id=str(product.pk), action_flag=ADDITION)
                self.assertEqual(entry.user, self.superuser)
                self.assertIn("added", entry.change_message)

    def test_change_saves_relations_and_ignores_readonly_post(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                self.set_mode(mode)
                response = self.client.post(self.change_url, self.product_data(
                    name=f"Saved {mode}", updated_at="1900-01-01 00:00:00",
                    **{"variants-0-value": mode},
                ))
                self.assertRedirects(response, self.list_url)
                self.product.refresh_from_db()
                self.variant.refresh_from_db()
                self.assertEqual(self.product.name, f"Saved {mode}")
                self.assertEqual(self.product.category, self.second_category)
                self.assertEqual(set(self.product.tags.all()), {self.tag, self.second_tag})
                self.assertEqual(self.variant.value, mode)
                self.assertGreater(self.product.updated_at.year, 1900)
                self.assertTrue(LogEntry.objects.filter(object_id=str(self.product.pk), action_flag=CHANGE).exists())

    def test_inline_validation_preserves_parent_and_relationships(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                self.set_mode(mode)
                response = self.client.post(self.change_url, self.product_data(**{"variants-0-value": ""}))
                self.assertEqual(response.status_code, 200)
                inline = response.context["inline_admin_formsets"][0]
                self.assertIn("value", inline.formset.forms[0].errors)
                self.assertContains(response, "errorlist")
                self.product.refresh_from_db()
                self.variant.refresh_from_db()
                self.assertEqual(self.product.name, "Native workflows")
                self.assertEqual(self.product.category, self.category)
                self.assertEqual(list(self.product.tags.all()), [self.tag])
                self.assertEqual(self.variant.value, "Blue")
                self.assertFalse(LogEntry.objects.filter(action_flag=CHANGE).exists())

    def test_invalid_added_inline_does_not_create_parent(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                self.set_mode(mode)
                response = self.client.post(self.add_url, self.product_data(
                    adding=True, **{"variants-0-value": ""},
                ))
                self.assertEqual(response.status_code, 200)
                self.assertIn("value", response.context["inline_admin_formsets"][0].formset.forms[0].errors)
                self.assertFalse(Product.objects.filter(sku="WORKFLOW-NEW").exists())

    def test_invalid_related_object_is_rejected(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                self.set_mode(mode)
                response = self.client.post(self.add_url, self.product_data(
                    adding=True, category="999999", tags=["999999"],
                ))
                self.assertEqual(response.status_code, 200)
                errors = response.context["adminform"].form.errors
                self.assertIn("category", errors)
                self.assertIn("tags", errors)
                self.assertFalse(Product.objects.filter(sku="WORKFLOW-NEW").exists())

    def test_inline_delete_and_replacement_follow_native_formset_contract(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                self.set_mode(mode)
                variant = ProductVariant.objects.create(product=self.product, name="Remove", value=mode)
                data = self.product_data(**{
                    "variants-INITIAL_FORMS": "2", "variants-TOTAL_FORMS": "3",
                    "variants-1-id": str(variant.pk), "variants-1-product": str(self.product.pk),
                    "variants-1-name": "Remove", "variants-1-value": mode, "variants-1-DELETE": "on",
                    "variants-2-name": "Replacement", "variants-2-value": mode,
                })
                response = self.client.post(self.change_url, data)
                self.assertRedirects(response, self.list_url)
                self.assertFalse(ProductVariant.objects.filter(pk=variant.pk).exists())
                self.assertTrue(self.product.variants.filter(name="Replacement", value=mode).exists())

    def test_related_links_follow_related_model_permissions(self):
        self.grant("view_product", "change_product")
        for mode in MODES:
            with self.subTest(mode=mode):
                self.set_mode(mode)
                response = self.client.get(self.change_url)
                widget = response.context["adminform"].form.fields["category"].widget
                self.assertFalse(widget.can_add_related)
                self.assertFalse(widget.can_change_related)
                self.assertFalse(widget.can_delete_related)
                self.assertFalse(widget.can_view_related)
                self.assertNotContains(response, 'id="add_id_category"')
                self.assertNotContains(response, 'id="change_id_category"')
                self.assertNotContains(response, 'id="delete_id_category"')
                self.assertEqual(self.client.get(reverse("admin:catalog_category_add")).status_code, 403)
        self.grant("view_category", "add_category", "change_category", "delete_category")
        response = self.client.get(self.change_url)
        widget = response.context["adminform"].form.fields["category"].widget
        self.assertTrue(widget.can_add_related)
        self.assertTrue(widget.can_change_related)
        self.assertTrue(widget.can_delete_related)
        self.assertTrue(widget.can_view_related)
        self.assertContains(response, 'id="add_id_category"')
        self.assertContains(response, 'id="view_id_category"')

    def test_autocomplete_returns_native_json_and_filters_search(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                self.set_mode(mode)
                response = self.client.get(reverse("admin:autocomplete"), {
                    "app_label": "catalog", "model_name": "product", "field_name": "category", "term": "Access",
                })
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {
                    "results": [{"id": str(self.category.pk), "text": "Accessories"}],
                    "pagination": {"more": False},
                })

    def test_autocomplete_pagination_is_native(self):
        Category.objects.bulk_create([Category(name=f"Page category {i:02}", slug=f"page-{i:02}") for i in range(23)])
        params = {"app_label": "catalog", "model_name": "product", "field_name": "category", "term": "Page category"}
        response = self.client.get(reverse("admin:autocomplete"), params)
        self.assertEqual(len(response.json()["results"]), 20)
        self.assertTrue(response.json()["pagination"]["more"])
        second = self.client.get(reverse("admin:autocomplete"), {**params, "page": "2"})
        self.assertEqual(len(second.json()["results"]), 3)
        self.assertFalse(second.json()["pagination"]["more"])
        self.assertTrue(set(row["id"] for row in response.json()["results"]).isdisjoint(
            (row["id"] for row in second.json()["results"]),
        ))

    def test_autocomplete_requires_related_model_view_permission(self):
        self.grant("view_product", "change_product")
        params = {"app_label": "catalog", "model_name": "product", "field_name": "category", "term": "Access"}
        for mode in MODES:
            with self.subTest(mode=mode):
                self.set_mode(mode)
                self.assertEqual(self.client.get(reverse("admin:autocomplete"), params).status_code, 403)
        self.grant("view_category")
        response = self.client.get(reverse("admin:autocomplete"), params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"][0]["id"], str(self.category.pk))

    def test_batch_delete_requires_confirmation_and_deletes_selected_only(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                self.set_mode(mode)
                selected = Product.objects.create(name=f"Delete {mode}", sku=f"DELETE-{mode}", price=1)
                variant = ProductVariant.objects.create(product=selected, name="Size", value="Small")
                data = {"action": "delete_selected", "_selected_action": [str(selected.pk)], "index": "0"}
                response = self.client.post(self.list_url, data)
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "admin/delete_selected_confirmation.html")
                self.assertContains(response, 'name="post"')
                self.assertContains(response, 'name="csrfmiddlewaretoken"')
                self.assertTrue(Product.objects.filter(pk=selected.pk).exists())
                self.assertTrue(ProductVariant.objects.filter(pk=variant.pk).exists())
                response = self.client.post(self.list_url, {**data, "post": "yes"})
                self.assertRedirects(response, self.list_url)
                self.assertFalse(Product.objects.filter(pk=selected.pk).exists())
                self.assertFalse(ProductVariant.objects.filter(pk=variant.pk).exists())
                self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())
                self.assertTrue(LogEntry.objects.filter(object_id=str(selected.pk), action_flag=DELETION).exists())

    def test_batch_delete_is_unavailable_without_delete_permission(self):
        self.grant("view_product", "change_product")
        response = self.client.get(self.list_url)
        self.assertNotContains(response, 'value="delete_selected"')
        response = self.client.post(self.list_url, {
            "action": "delete_selected", "_selected_action": [str(self.product.pk)], "index": "0", "post": "yes",
        })
        self.assertRedirects(response, self.list_url)
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())

    def test_changelist_pagination_preserves_search_and_filter(self):
        Product.objects.bulk_create([
            Product(name=f"Paged item {i:02}", sku=f"PAGED-{i:02}", price=i, status="active")
            for i in range(25)
        ])
        for mode in MODES:
            with self.subTest(mode=mode):
                self.set_mode(mode)
                params = {"q": "PAGED-", "status__exact": "active", "o": "1"}
                first = self.client.get(self.list_url, params)
                self.assertEqual(first.context["cl"].result_count, 25)
                self.assertEqual(len(first.context["cl"].result_list), 20)
                self.assertContains(first, "p=2")
                self.assertContains(first, "q=PAGED-")
                second = self.client.get(self.list_url, {**params, "p": "2"})
                self.assertEqual(second.status_code, 200)
                self.assertEqual(len(second.context["cl"].result_list), 5)
                self.assertEqual(second.context["cl"].page_num, 2)
                self.assertTrue(set(first.context["cl"].result_list).isdisjoint(second.context["cl"].result_list))
                shown = self.client.get(self.list_url, {**params, "all": ""})
                self.assertEqual(len(shown.context["cl"].result_list), 25)

    def test_native_mode_can_reenable_theme_without_losing_filter_or_query(self):
        destination = self.list_url + "?q=WORKFLOW-&status__exact=draft"
        preference = reverse("nova_admin:preference")
        self.set_mode("native")
        response = self.client.get(destination)
        self.assertContains(response, preference)
        self.assertContains(response, 'value="dark"')
        self.assertNotContains(response, "nova_admin/theme.css")
        response = self.client.post(preference, {"mode": "dark", "next": destination}, follow=True)
        self.assertEqual(response.redirect_chain, [(destination, 302)])
        self.assertContains(response, "nova_admin/theme.css")
        self.assertContains(response, "nova-mode-dark")
        self.assertEqual(response.context["cl"].query, "WORKFLOW-")
        self.assertEqual(list(response.context["cl"].queryset), [self.product])

    def test_admin_model_post_still_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.superuser)
        self.assertEqual(client.post(self.add_url, self.product_data(adding=True)).status_code, 403)
        self.assertFalse(Product.objects.filter(sku="WORKFLOW-NEW").exists())
        client.get(self.add_url)
        data = self.product_data(adding=True, csrfmiddlewaretoken=client.cookies["csrftoken"].value)
        self.assertRedirects(client.post(self.add_url, data), self.list_url)

    def test_related_popup_save_returns_native_popup_response(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                self.set_mode(mode)
                response = self.client.post(reverse("admin:catalog_category_add"), {
                    "name": f"Popup {mode}", "slug": f"popup-{mode}", "_popup": "1", "_save": "Save",
                })
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "admin/popup_response.html")
                self.assertContains(response, "admin/js/popup_response.js")
                self.assertTrue(Category.objects.filter(slug=f"popup-{mode}").exists())
                self.assertNotContains(response, "nova-theme-switcher")

    def test_change_form_view_only_permission_cannot_save_or_edit_inlines(self):
        self.grant("view_product", "view_productvariant")
        for mode in MODES:
            with self.subTest(mode=mode):
                self.set_mode(mode)
                response = self.client.get(self.change_url)
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, 'name="_save"')
                self.assertNotContains(response, 'name="variants-0-value"')
                response = self.client.post(self.change_url, self.product_data())
                self.assertEqual(response.status_code, 403)
                self.product.refresh_from_db()
                self.assertEqual(self.product.name, "Native workflows")

    def test_anonymous_cannot_access_autocomplete(self):
        self.client.logout()
        response = self.client.get(reverse("admin:autocomplete"), {
            "app_label": "catalog", "model_name": "product", "field_name": "category", "term": "Access",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("admin:login")))
