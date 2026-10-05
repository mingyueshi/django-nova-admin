"""Native admin controls keep Django's forms, permissions and save semantics.

These are server-side TestClient/DOM regression tests, not browser interaction
or accessibility certification. A switch is only an explicitly styled checkbox;
changing its value is persisted by Django's ordinary Save POST.
"""
import json

from django.contrib import admin
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.forms import CheckboxInput
from django.test import Client, TestCase
from django.urls import reverse
from django.utils.html import escape

from catalog.models import Product, ProductVariant
from nova_admin.preferences import SESSION_KEY
from tests.test_navigation_groups import NavigationElements


MODES = ("dark", "light", "native")
SWITCH_LABEL = "精选推荐（保存后生效）"


class NativeControlWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.superuser = get_user_model().objects.create_superuser(
            username="controls-admin", password=None,
        )
        cls.viewer = get_user_model().objects.create_user(
            username="controls-viewer", password=None, is_staff=True,
        )
        cls.viewer.user_permissions.add(Permission.objects.get(
            content_type__app_label="catalog", codename="view_product",
        ))
        cls.product = Product.objects.create(
            name="Control fixture off", sku="CONTROL-OFF", price="12.50",
            status=Product.Status.DRAFT,
        )
        cls.other = Product.objects.create(
            name="Control fixture on", sku="CONTROL-ON", price="24.00",
            status=Product.Status.ACTIVE, featured=True,
        )
        cls.variant = ProductVariant.objects.create(
            product=cls.product, name="Size", value="Small",
        )
        cls.content_type = ContentType.objects.get_for_model(Product)

    def setUp(self):
        self.client.force_login(self.superuser)
        self.list_url = reverse("admin:catalog_product_changelist")
        self.change_url = reverse("admin:catalog_product_change", args=[self.product.pk])
        self.model_admin = admin.site.get_model_admin(Product)

    def set_mode(self, mode, client=None):
        session = (client or self.client).session
        session[SESSION_KEY] = mode
        session.save()

    def changes(self):
        return LogEntry.objects.filter(content_type=self.content_type, action_flag=CHANGE)

    def list_post(self, response, **featured_by_pk):
        """Build the native management/id payload from the real rendered formset."""
        formset = response.context["cl"].formset
        data = {
            field.html_name: field.value()
            for field in formset.management_form
        }
        data["_save"] = "Save"
        for form in formset:
            data[form["id"].html_name] = str(form.instance.pk)
            checked = featured_by_pk.get(str(form.instance.pk), form.instance.featured)
            if checked:
                data[form["featured"].html_name] = "on"
        return data

    def controls(self, response, *, name=None, element_id=None):
        elements = NavigationElements(response.content.decode()).elements
        return [
            element for element in elements
            if element["tag"] == "input"
            and (name is None or element["attrs"].get("name") == name)
            and (element_id is None or element["attrs"].get("id") == element_id)
        ]

    def assert_real_switch(self, element, *, checked=False):
        attrs = element["attrs"]
        self.assertEqual(attrs.get("type"), "checkbox")
        self.assertTrue(NavigationElements.has_class(element, "nova-switch"))
        self.assertEqual(attrs.get("aria-label"), SWITCH_LABEL)
        self.assertEqual("checked" in attrs, checked)
        self.assertNotIn("disabled", attrs)
        self.assertNotIn("onclick", attrs)
        self.assertNotIn("onchange", attrs)

    def test_featured_is_a_real_nonnullable_boolean_with_false_default(self):
        field = Product._meta.get_field("featured")
        self.assertIsInstance(field, models.BooleanField)
        self.assertIs(field.default, False)
        self.assertFalse(field.null)
        self.assertEqual(field.verbose_name, "精选推荐")
        self.product.refresh_from_db()
        self.assertIs(self.product.featured, False)
        self.assertEqual(self.model_admin.list_editable, ["featured"])

    def test_list_switches_keep_native_formset_ids_names_and_save_control(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                self.set_mode(mode)
                response = self.client.get(self.list_url)
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "admin/change_list.html")
                formset = response.context["cl"].formset
                self.assertEqual(formset.initial_form_count(), 2)
                self.assertContains(response, 'name="form-TOTAL_FORMS"')
                self.assertContains(response, 'name="csrfmiddlewaretoken"')
                self.assertContains(response, 'name="_save"')
                self.assertContains(response, "精选推荐开关仅更改待保存状态，请点击「保存」后生效。")
                for form in formset:
                    self.assertEqual(set(form.fields), {"id", "featured"})
                    self.assertIsInstance(form.fields["featured"].widget, CheckboxInput)
                    controls = self.controls(response, name=form["featured"].html_name)
                    self.assertEqual(len(controls), 1)
                    self.assert_real_switch(controls[0], checked=form.instance.featured)
                    self.assertTrue(any(
                        ancestor["tag"] == "form"
                        and ancestor["attrs"].get("id") == "changelist-form"
                        for ancestor in controls[0]["ancestors"]
                    ))
                self.assertFalse(self.product.featured)
                self.assertFalse(self.changes().exists())

    def test_list_editable_round_trip_saves_boolean_and_native_change_log(self):
        for mode in MODES:
            for checked in (True, False):
                with self.subTest(mode=mode, checked=checked):
                    self.set_mode(mode)
                    before_count = self.changes().count()
                    response = self.client.get(self.list_url)
                    payload = self.list_post(response, **{str(self.product.pk): checked})
                    response = self.client.post(self.list_url, payload)
                    self.assertRedirects(response, self.list_url)
                    self.product.refresh_from_db()
                    self.other.refresh_from_db()
                    self.assertIs(self.product.featured, checked)
                    self.assertIs(self.other.featured, True)
                    self.assertEqual(self.product.status, Product.Status.DRAFT)
                    self.assertEqual(self.changes().count(), before_count + 1)
                    entry = self.changes().latest("id")
                    self.assertEqual(entry.object_id, str(self.product.pk))
                    self.assertEqual(entry.user, self.superuser)
                    self.assertEqual(json.loads(entry.change_message), [
                        {"changed": {"fields": ["精选推荐"]}},
                    ])
                    refreshed = self.client.get(self.list_url)
                    form = next(
                        form for form in refreshed.context["cl"].formset
                        if form.instance.pk == self.product.pk
                    )
                    control = self.controls(refreshed, name=form["featured"].html_name)[0]
                    self.assert_real_switch(control, checked=checked)

    def test_repeated_unchanged_save_does_not_create_spurious_change_logs(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                self.set_mode(mode)
                response = self.client.get(self.list_url)
                payload = self.list_post(response)
                for _ in range(2):
                    self.assertRedirects(self.client.post(self.list_url, payload), self.list_url)
                self.product.refresh_from_db()
                self.other.refresh_from_db()
                self.assertFalse(self.product.featured)
                self.assertTrue(self.other.featured)
                self.assertFalse(self.changes().exists())

    def test_list_save_requires_csrf_and_accepts_valid_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.superuser)
        for mode in MODES:
            with self.subTest(mode=mode):
                self.set_mode(mode, client)
                self.product.refresh_from_db()
                before = self.product.featured
                before_logs = self.changes().count()
                response = client.get(self.list_url)
                payload = self.list_post(response, **{str(self.product.pk): not before})
                self.assertEqual(client.post(self.list_url, payload).status_code, 403)
                self.product.refresh_from_db()
                self.assertIs(self.product.featured, before)
                self.assertEqual(self.changes().count(), before_logs)
                payload["csrfmiddlewaretoken"] = client.cookies["csrftoken"].value
                self.assertRedirects(client.post(self.list_url, payload), self.list_url)
                self.product.refresh_from_db()
                self.assertIs(self.product.featured, not before)
                self.assertEqual(self.changes().count(), before_logs + 1)

    def test_view_only_user_cannot_submit_list_editable_or_change_form(self):
        payload = self.list_post(
            self.client.get(self.list_url), **{str(self.product.pk): True},
        )
        self.client.force_login(self.viewer)
        for mode in MODES:
            with self.subTest(mode=mode):
                self.set_mode(mode)
                response = self.client.get(self.list_url)
                self.assertEqual(response.status_code, 200)
                self.assertIsNone(response.context["cl"].formset)
                self.assertNotContains(response, 'name="_save"')
                self.assertNotContains(response, 'class="nova-switch"')
                self.assertNotContains(response, 'class="nova-list-edit-help"')
                self.assertEqual(self.client.post(self.list_url, payload).status_code, 403)
                self.assertEqual(self.client.post(self.change_url, {
                    "featured": "on", "_save": "Save",
                }).status_code, 403)
                self.product.refresh_from_db()
                self.assertFalse(self.product.featured)
                self.assertFalse(self.changes().exists())

    def test_invalid_formset_preserves_every_row_and_creates_no_log(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                self.set_mode(mode)
                response = self.client.get(self.list_url)
                formset = response.context["cl"].formset
                invalid_form = next(form for form in formset if form.instance.pk == self.other.pk)
                payload = self.list_post(response, **{str(self.product.pk): True})
                payload[invalid_form["id"].html_name] = "not-a-product-id"
                response = self.client.post(self.list_url, payload)
                self.assertEqual(response.status_code, 200)
                bound_formset = response.context["cl"].formset
                self.assertFalse(bound_formset.is_valid())
                self.assertTrue(any("id" in errors for errors in bound_formset.errors))
                # Django exposes the hidden id's validation through its native
                # top-level error note, rather than an inline visible field.
                self.assertContains(response, 'class="errornote"')
                self.product.refresh_from_db()
                self.other.refresh_from_db()
                self.assertFalse(self.product.featured)
                self.assertTrue(self.other.featured)
                self.assertFalse(self.changes().exists())

    def test_missing_management_form_cannot_silently_save_a_boolean(self):
        response = self.client.post(self.list_url, {
            "_save": "Save", "form-0-id": str(self.product.pk), "form-0-featured": "on",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["cl"].formset.non_form_errors())
        self.product.refresh_from_db()
        self.assertFalse(self.product.featured)
        self.assertFalse(self.changes().exists())

    def test_list_editable_does_not_accept_other_posted_business_fields(self):
        response = self.client.get(self.list_url)
        form = next(form for form in response.context["cl"].formset if form.instance.pk == self.product.pk)
        payload = self.list_post(response, **{str(self.product.pk): True})
        payload.update({
            f"{form.prefix}-status": "active",
            f"{form.prefix}-name": "Unexpected rename",
            f"{form.prefix}-price": "0.01",
        })
        self.assertRedirects(self.client.post(self.list_url, payload), self.list_url)
        self.product.refresh_from_db()
        self.assertTrue(self.product.featured)
        self.assertEqual(self.product.status, Product.Status.DRAFT)
        self.assertEqual(self.product.name, "Control fixture off")
        self.assertEqual(str(self.product.price), "12.50")

    def test_change_form_switch_is_an_explicitly_opted_in_labeled_checkbox(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                self.set_mode(mode)
                response = self.client.get(self.change_url)
                form = response.context["adminform"].form
                field = form.fields["featured"]
                self.assertIsInstance(field.widget, CheckboxInput)
                self.assertFalse(field.required)
                self.assertEqual(field.label, "精选推荐")
                self.assertEqual(field.widget.attrs.get("aria-label"), SWITCH_LABEL)
                control = self.controls(response, name="featured")[0]
                self.assert_real_switch(control)
                elements = NavigationElements(response.content.decode()).elements
                self.assertTrue(any(
                    element["tag"] == "label"
                    and element["attrs"].get("for") == control["attrs"]["id"]
                    for element in elements
                ))
                self.assertTrue(any(
                    NavigationElements.has_class(ancestor, "field-featured")
                    for ancestor in control["ancestors"]
                ))

    def test_selection_and_inline_delete_checkboxes_do_not_opt_into_switches(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                self.set_mode(mode)
                response = self.client.get(self.list_url)
                selection = self.controls(response, name="_selected_action")
                self.assertEqual(len(selection), 2)
                for element in selection + self.controls(response, element_id="action-toggle"):
                    self.assertEqual(element["attrs"].get("type"), "checkbox")
                    self.assertFalse(NavigationElements.has_class(element, "nova-switch"))
                response = self.client.get(self.change_url)
                self.assertEqual(len(self.controls(response, name="variants-0-DELETE")), 1)
                for element in self.controls(response):
                    if element["attrs"].get("type") == "checkbox" and element["attrs"].get("name") != "featured":
                        self.assertFalse(NavigationElements.has_class(element, "nova-switch"))

    def test_native_mode_removes_theme_assets_but_keeps_real_editable_checkboxes(self):
        self.set_mode("native")
        for url in (self.list_url, self.change_url):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertNotContains(response, "nova_admin/theme.css")
                self.assertNotContains(response, "nova_admin/navigation.js")
                self.assertNotContains(response, "nova-mode-")
                self.assertContains(response, "admin/css/base.css")
                switches = [
                    element for element in self.controls(response)
                    if NavigationElements.has_class(element, "nova-switch")
                ]
                self.assertTrue(switches)
                for element in switches:
                    self.assertEqual(element["attrs"].get("type"), "checkbox")
                    self.assertTrue(element["attrs"].get("name"))
                    self.assertNotIn("disabled", element["attrs"])
                self.assertContains(response, 'name="_save"')

    def test_view_only_list_preserves_boolean_images_and_accessible_alt_values(self):
        self.client.force_login(self.viewer)
        for mode in MODES:
            with self.subTest(mode=mode):
                self.set_mode(mode)
                response = self.client.get(self.list_url)
                elements = NavigationElements(response.content.decode()).elements
                images = [
                    element for element in elements
                    if element["tag"] == "img" and any(
                        NavigationElements.has_class(ancestor, "field-featured")
                        for ancestor in element["ancestors"]
                    )
                ]
                self.assertEqual(len(images), 2)
                self.assertEqual({image["attrs"].get("alt") for image in images}, {"True", "False"})
                for image in images:
                    expected = "yes" if image["attrs"]["alt"] == "True" else "no"
                    self.assertTrue(image["attrs"]["src"].endswith(f"admin/img/icon-{expected}.svg"))
                    self.assertNotIn("role", image["attrs"])
                    self.assertNotIn("tabindex", image["attrs"])
                self.assertFalse(any(
                    element["tag"] in {"input", "button"} and any(
                        NavigationElements.has_class(ancestor, "field-featured")
                        for ancestor in element["ancestors"]
                    ) for element in elements
                ))

    def test_view_only_change_form_uses_native_readonly_boolean_display(self):
        self.client.force_login(self.viewer)
        for mode in MODES:
            with self.subTest(mode=mode):
                self.set_mode(mode)
                response = self.client.get(self.change_url)
                self.assertEqual(response.status_code, 200)
                self.assertNotIn("featured", response.context["adminform"].form.fields)
                self.assertNotContains(response, 'name="featured"')
                elements = NavigationElements(response.content.decode()).elements
                images = [
                    element for element in elements
                    if element["tag"] == "img" and any(
                        NavigationElements.has_class(ancestor, "field-featured")
                        for ancestor in element["ancestors"]
                    )
                ]
                self.assertEqual(len(images), 1)
                self.assertEqual(images[0]["attrs"].get("alt"), "False")
                self.assertTrue(images[0]["attrs"]["src"].endswith("admin/img/icon-no.svg"))

    def test_status_badge_preserves_text_and_escapes_unknown_values(self):
        badge = self.model_admin.status_badge
        self.assertEqual(badge.short_description, "状态")
        self.assertEqual(badge.admin_order_field, "status")
        for value, label in Product.Status.choices:
            with self.subTest(status=value):
                product = Product(status=value)
                self.assertHTMLEqual(
                    str(badge(product)),
                    f'<span class="nova-status nova-status--{value}">{label}</span>',
                )
        unsafe = '\"><script>alert("status")</script>'
        markup = str(badge(Product(status=unsafe)))
        self.assertIn('class="nova-status nova-status--unknown"', markup)
        self.assertIn(str(escape(unsafe)), markup)
        self.assertNotIn("<script>", markup)

    def test_status_badge_keeps_native_sorting_and_filtering(self):
        archived = Product.objects.create(
            name="Control fixture archived", sku="CONTROL-ARCHIVED", price="9.00",
            status=Product.Status.ARCHIVED,
        )
        for mode in MODES:
            with self.subTest(mode=mode):
                self.set_mode(mode)
                initial = self.client.get(self.list_url)
                index = initial.context["cl"].list_display.index("status_badge")
                ascending = self.client.get(self.list_url, {"o": str(index)})
                self.assertEqual(list(ascending.context["cl"].result_list), [
                    self.other, archived, self.product,
                ])
                descending = self.client.get(self.list_url, {"o": f"-{index}"})
                self.assertEqual(list(descending.context["cl"].result_list), [
                    self.product, archived, self.other,
                ])
                self.assertContains(ascending, "sortable column-status_badge")
                for value, label in Product.Status.choices:
                    self.assertContains(ascending, f'nova-status--{value}')
                    self.assertContains(ascending, label)
                filtered = self.client.get(self.list_url, {"status__exact": "active"})
                self.assertEqual(list(filtered.context["cl"].result_list), [self.other])
