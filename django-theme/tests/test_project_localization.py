"""The demo's explicit project policy, separate from reusable Nova behavior."""
import gettext as stdlib_gettext
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup
import django
from django import forms
from django.conf import settings
from django.contrib import admin
from django.contrib.admin.helpers import AdminReadonlyField
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.template import Context
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils.translation import gettext, override, pgettext

from catalog.admin import VariantInline
from catalog.forms import ProjectAdminFormRenderer
from catalog.models import Product, ProductVariant
from catalog.templatetags.project_admin import project_label_tag, project_nonce
from nova_admin.preferences import SESSION_KEY

PROJECT_LOCALE = Path(__file__).resolve().parents[1] / "demo/locale"


@override_settings(LANGUAGE_CODE="en", LOCALE_PATHS=[PROJECT_LOCALE])
class ProjectCatalogTests(SimpleTestCase):
    def test_compiled_catalog_uses_actual_msgids_context_and_placeholders(self):
        with (PROJECT_LOCALE / "zh_Hans/LC_MESSAGES/django.mo").open("rb") as stream:
            catalog = stdlib_gettext.GNUTranslations(stream)
        self.assertEqual(catalog.gettext("Select %s to change") % "商品", "商品列表")
        self.assertEqual(catalog.gettext("Select %s to view") % "商品", "商品列表")
        self.assertEqual(catalog.gettext("Add %s") % "商品", "新增商品")
        self.assertEqual(catalog.gettext("Add %(name)s") % {"name": "商品"}, "新增商品")
        self.assertEqual(catalog.gettext("group"), "用户组")
        self.assertEqual(catalog.gettext("groups"), "用户组")
        self.assertEqual(catalog.pgettext("Nova Admin", "Site overview"), "工作台")
        self.assertEqual(catalog.gettext("Site overview"), "Site overview")
        self.assertEqual(catalog.info()["plural-forms"], "nplurals=1; plural=0;")

    def test_project_chinese_and_english_fallback_are_independent(self):
        for language, add, heading in (("zh-hans", "新增", "工作台"), ("en", "Add", "Site overview"), ("fr", "Ajouter", "Site overview")):
            with self.subTest(language=language), override(language):
                self.assertEqual(gettext("Add"), add)
                self.assertEqual(pgettext("Nova Admin", "Site overview"), heading)
                self.assertEqual(pgettext("Unrelated application", "Site overview"), "Site overview")

    @override_settings(LOCALE_PATHS=())
    def test_removing_project_catalog_restores_upstream_chinese(self):
        with override("zh-hans"):
            self.assertEqual(gettext("Add"), "增加")
            self.assertEqual(pgettext("Nova Admin", "Site overview"), "站点总览")

    def test_labels_normalize_once_and_preserve_escaping_and_checkbox_semantics(self):
        class ExampleForm(forms.Form):
            required = forms.CharField(label="正常标签")
            colon = forms.CharField(label="已有冒号：")
            ascii_colon = forms.CharField(label="ASCII:")
            escaped = forms.CharField(label='<script>alert("label")</script>')
            enabled = forms.BooleanField(label="启用", required=False)
        for language in ("zh-hans", "en", "fr"):
            with self.subTest(language=language), override(language):
                form = ExampleForm(renderer=ProjectAdminFormRenderer())
                for name in form.fields:
                    label = BeautifulSoup(str(form[name].label_tag()), "html.parser").label
                    self.assertEqual(label["for"], f"id_{name}")
                    if language == "zh-hans" and name != "enabled":
                        self.assertTrue(label.get_text().endswith("："))
                        self.assertNotIn("：：", label.get_text())
                        self.assertNotIn(":：", label.get_text())
                self.assertNotIn("<script>", str(form["escaped"].label_tag()))
                self.assertIn('type="checkbox"', str(form["enabled"]))
                if language != "zh-hans":
                    self.assertNotIn("：", str(form["required"].label_tag()))

    def test_custom_blank_option_label_and_value_are_preserved(self):
        class ExampleForm(forms.Form):
            choices = forms.ChoiceField(choices=[("", "Choose an owner"), ("x", "An owner")])
            legacy = forms.ChoiceField(choices=[("", "---------"), ("x", "Value")])
        with override("zh-hans"):
            form = ExampleForm(renderer=ProjectAdminFormRenderer())
            self.assertIn("Choose an owner", str(form["choices"]))
            self.assertIn('<option value="" selected>请选择</option>', str(form["legacy"]))
            self.assertEqual(form.fields["legacy"].choices[0], ("", "---------"))

    def test_readonly_helper_uses_one_colon_without_mutating_form(self):
        class ProductForm(forms.ModelForm):
            class Meta:
                model = Product
                fields = ["name"]
                labels = {"updated_at": "更新时间："}
        form = ProductForm()
        helper = AdminReadonlyField(form, "updated_at", is_first=False, model_admin=admin.site._registry[Product])
        with override("zh-hans"):
            label = project_label_tag(helper)
            self.assertIn('class="inline"', label)
            self.assertIn("更新时间：</label>", label)
            self.assertNotIn("：：", label)
            self.assertEqual(form.label_suffix, ":")
            self.assertEqual(helper.field["label"], "更新时间：")

    def test_project_template_snapshots_track_installed_native_markup(self):
        # Detect an upstream accessibility/error/formset change before upgrading.
        source = Path(admin.__file__).parent / "templates/admin"
        target = Path(settings.BASE_DIR) / "templates/project_admin"
        suffix = {(5, 2): "52", (6, 0): "60", (6, 1): "61"}[django.VERSION[:2]]
        native = (source / "includes/fieldset.html").read_text()
        expected = "{% load project_admin %}\n" + native.replace("{{ field.label_tag }}", "{% project_label_tag field %}")
        self.assertEqual((target / f"fieldset_{suffix}.html").read_text(), expected)
        native = (source / "edit_inline/tabular.html").read_text()
        expected = native.replace("{% load i18n admin_urls static admin_modify %}", "{% load i18n admin_urls static admin_modify project_admin %}").replace("{{ field.label|capfirst }}", "{{ field.label|capfirst|project_label }}")
        self.assertEqual((target / f"tabular_{'52' if suffix == '52' else '60'}.html").read_text(), expected)

    def test_project_nonce_is_escaped_and_optional(self):
        self.assertEqual(project_nonce(Context({})), "")
        self.assertEqual(project_nonce(Context({"csp_nonce": 'nonce"&<>'})), 'nonce="nonce&quot;&amp;&lt;&gt;"')


@override_settings(LANGUAGE_CODE="en", LOCALE_PATHS=[PROJECT_LOCALE], NOVA_ADMIN_ENABLED=True, NOVA_ADMIN_NAVIGATION=True)
class ProjectChineseRenderedTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser(username="project-render-test", password=None)
        cls.product = Product.objects.create(name="Synthetic test product", sku="PROJECT-L10N", price="12.50")
        ProductVariant.objects.create(product=cls.product, name="颜色", value="蓝色")

    def setUp(self):
        self.client.force_login(self.user)

    def test_actual_index_app_list_and_model_add_links_use_project_words(self):
        with override("zh-hans"):
            index = self.client.get(reverse("admin:index"))
            for text in ("工作台", "管理内容数据", "退出登录", "用户组", "新增", "搜索菜单…"):
                self.assertContains(index, text)
            app = self.client.get(reverse("admin:app_list", args=["auth"]))
            soup = BeautifulSoup(app.content, "html.parser")
            self.assertEqual(soup.select_one('#content-main a[href="/admin/auth/group/add/"]').get_text(strip=True), "新增")
            changelist = self.client.get(reverse("admin:catalog_product_changelist"))
            self.assertEqual(changelist.context["title"], "商品列表")
            self.assertContains(changelist, "新增商品")
            self.assertContains(changelist, "显示数量")
            self.assertContains(changelist, '<option value="" selected>请选择</option>', html=True)
            add = self.client.get(reverse("admin:catalog_product_add"))
            self.assertEqual(add.context["title"], "新增商品")
            self.assertContains(add, "新增分类")

    def test_change_form_real_labels_readonly_inline_and_checkbox(self):
        with override("zh-hans"):
            response = self.client.get(reverse("admin:catalog_product_change", args=[self.product.pk]))
        soup = BeautifulSoup(response.content, "html.parser")
        for selector, expected in (("label[for=id_name]", "商品名称："), ("label[for=id_featured]", "精选推荐"), (".field-updated_at label", "更新时间："), ("th.column-name", "规格："), ("th.column-value", "规格值：")):
            self.assertEqual(soup.select_one(selector).get_text(strip=True), expected)
        checkbox = soup.select_one("#id_featured")
        self.assertEqual(checkbox["type"], "checkbox")
        self.assertEqual(checkbox["name"], "featured")
        self.assertIn("vCheckboxLabel", soup.select_one("label[for=id_featured]")["class"])
        self.assertLess(str(soup).index('id="id_featured"'), str(soup).index('for="id_featured"'))
        self.assertIsNotNone(soup.select_one('input[name="variants-TOTAL_FORMS"]'))
        self.assertIsNotNone(soup.select_one('input[name="csrfmiddlewaretoken"]'))
        self.assertNotIn("：：", soup.get_text())

    def test_stacked_inline_and_readonly_inline_keep_native_forms(self):
        with override("zh-hans"), patch.object(VariantInline, "template", "admin/edit_inline/stacked.html"), patch.object(VariantInline, "readonly_fields", ["value"]):
            response = self.client.get(reverse("admin:catalog_product_change", args=[self.product.pk]))
        soup = BeautifulSoup(response.content, "html.parser")
        self.assertEqual(soup.select_one('label[for="id_variants-0-name"]').get_text(), "规格：")
        self.assertEqual(soup.select_one("#variants-0 .field-value label").get_text(), "规格值：")
        self.assertIsNotNone(soup.select_one('input[name="variants-0-DELETE"]'))

    def test_login_labels_have_fullwidth_colons_and_csrf(self):
        with override("zh-hans"):
            response = Client().get(reverse("admin:login"))
        soup = BeautifulSoup(response.content, "html.parser")
        self.assertTrue(soup.select_one("label[for=id_username]").get_text().endswith("："))
        self.assertTrue(soup.select_one("label[for=id_password]").get_text().endswith("："))
        self.assertIsNotNone(soup.select_one('input[name="csrfmiddlewaretoken"]'))

    def test_upstream_plural_messages_keep_actual_counts(self):
        for count in (1, 2):
            if count == 2:
                Product.objects.create(name="Second synthetic product", sku="PROJECT-SECOND", price="3.00")
            for language, expected in (("zh-hans", f"选中了 {count} 个"), ("en", "1 selected" if count == 1 else "All 2 selected")):
                with self.subTest(count=count, language=language), override(language):
                    response = self.client.get(reverse("admin:catalog_product_changelist"))
                    self.assertEqual(response.context["selection_note_all"], expected)

    def test_english_and_other_locale_keep_native_labels_and_wording(self):
        for language, expected_add in (("en", "Add"), ("fr", "Ajouter")):
            with self.subTest(language=language), override(language):
                response = self.client.get(reverse("admin:catalog_product_changelist"))
                self.assertContains(response, expected_add)
                self.assertNotContains(response, "新增商品")
                self.assertNotContains(response, "商品列表")
                form = self.client.get(reverse("admin:catalog_product_change", args=[self.product.pk]))
                soup = BeautifulSoup(form.content, "html.parser")
                self.assertEqual(soup.select_one("label[for=id_featured]").get_text(), "精选推荐")
                self.assertFalse(soup.select_one("label[for=id_name]").get_text().endswith("："))

    def test_native_and_disabled_modes_keep_project_language_but_no_brand_css(self):
        for disabled in (False, True):
            with self.subTest(disabled=disabled), override("zh-hans"), override_settings(NOVA_ADMIN_ENABLED=not disabled):
                session = self.client.session
                session[SESSION_KEY] = "native"
                session.save()
                response = self.client.get(reverse("admin:catalog_product_changelist"))
                self.assertContains(response, "商品列表")
                self.assertContains(response, "退出登录")
                self.assertNotContains(response, "catalog/enterprise.css")
                self.assertNotContains(response, "nova_admin/theme.css")

    def test_project_pages_survive_removing_the_theme_app(self):
        apps = [app for app in settings.INSTALLED_APPS if app != "nova_admin"]
        with override_settings(INSTALLED_APPS=apps), override("zh-hans"):
            response = self.client.get(reverse("admin:catalog_product_change", args=[self.product.pk]))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "商品名称：")
            self.assertNotContains(response, "catalog/enterprise.css")
            self.assertNotContains(response, "nova_admin/theme.css")

    def test_project_css_is_after_theme_and_fresh_default_is_light(self):
        response = self.client.get(reverse("admin:index"))
        self.assertContains(response, "nova-mode-light")
        html = response.content.decode()
        self.assertLess(html.index("nova_admin/theme.css"), html.index("catalog/enterprise.css"))
        self.assertNotIn("catalog/enterprise-compact.css", html)

    @override_settings(PROJECT_ADMIN_COMPACT=True)
    def test_compact_preset_loads_after_branding_only_when_active(self):
        response = self.client.get(reverse("admin:index"))
        html = response.content.decode()
        self.assertLess(html.index("catalog/enterprise.css"), html.index("catalog/enterprise-compact.css"))
        session = self.client.session
        session[SESSION_KEY] = "native"
        session.save()
        response = self.client.get(reverse("admin:index"))
        self.assertNotContains(response, "catalog/enterprise-compact.css")

    def test_view_only_title_does_not_grant_add_or_change_access(self):
        viewer = get_user_model().objects.create_user(username="project-viewer", password=None, is_staff=True)
        viewer.user_permissions.add(Permission.objects.get(codename="view_product", content_type__app_label="catalog"))
        self.client.force_login(viewer)
        with override("zh-hans"):
            response = self.client.get(reverse("admin:catalog_product_changelist"))
            self.assertEqual(response.context["title"], "商品列表")
            self.assertNotContains(response, "新增商品")
            self.assertEqual(self.client.get(reverse("admin:catalog_product_add")).status_code, 403)
            csrf_client = Client(enforce_csrf_checks=True)
            csrf_client.force_login(self.user)
            self.assertEqual(csrf_client.post(reverse("admin:catalog_product_add"), {"name": "Invalid"}).status_code, 403)
