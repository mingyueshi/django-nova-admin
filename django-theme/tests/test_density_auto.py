"""Server/native-workflow and CSS-contract tests; not browser geometry tests."""
import gettext as stdlib_gettext
import re
from copy import deepcopy
from importlib import resources
from pathlib import Path
from types import SimpleNamespace

from django.conf import settings
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.staticfiles import finders
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils.translation import override, pgettext

from catalog.models import Product, ProductVariant
from nova_admin.preferences import SESSION_KEY, selected_mode


class AutoModeSelectionTests(SimpleTestCase):
    @override_settings(NOVA_ADMIN_DEFAULT_MODE="light")
    def test_project_default_does_not_replace_any_explicit_session_choice(self):
        self.assertEqual(selected_mode(SimpleNamespace(session={})), "light")
        for mode in ("dark", "light", "auto", "native"):
            with self.subTest(mode=mode):
                session = {SESSION_KEY: mode}
                self.assertEqual(selected_mode(SimpleNamespace(session=session)), mode)
                self.assertEqual(session, {SESSION_KEY: mode})

    @override_settings(NOVA_ADMIN_DEFAULT_MODE="auto")
    def test_auto_can_be_an_explicit_project_default_without_writing_session(self):
        request = SimpleNamespace(session={})
        self.assertEqual(selected_mode(request), "auto")
        self.assertEqual(request.session, {})

    @override_settings(NOVA_ADMIN_DEFAULT_MODE="invalid")
    def test_invalid_configuration_still_uses_dark_library_fallback(self):
        for value in (None, [], {}, "AUTO", "unsupported"):
            with self.subTest(value=value):
                self.assertEqual(selected_mode(SimpleNamespace(session={SESSION_KEY: value})), "dark")

    @override_settings(NOVA_ADMIN_DEFAULT_MODE="light")
    def test_invalid_session_uses_valid_project_default(self):
        self.assertEqual(selected_mode(SimpleNamespace(session={SESSION_KEY: ["auto"]})), "light")

    @override_settings(LANGUAGE_CODE="en", LOCALE_PATHS=())
    def test_auto_is_contextual_and_compiled_in_chinese(self):
        for language, expected in (("en", "Nova auto"), ("zh-hans", "Nova 自动（跟随系统）")):
            with self.subTest(language=language), override(language):
                self.assertEqual(pgettext("Nova Admin", "Nova auto"), expected)
                self.assertEqual(pgettext("Another app", "Nova auto"), "Nova auto")
        path = resources.files("nova_admin").joinpath("locale", "zh_Hans", "LC_MESSAGES", "django.mo")
        with path.open("rb") as stream:
            catalog = stdlib_gettext.GNUTranslations(stream)
        self.assertEqual(catalog.pgettext("Nova Admin", "Nova auto"), "Nova 自动（跟随系统）")
        self.assertEqual(catalog.gettext("Nova auto"), "Nova auto")


@override_settings(NOVA_ADMIN_DEFAULT_MODE="light")
class AutoNativeAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser(username="auto-admin", password=None)
        cls.viewer = get_user_model().objects.create_user(username="auto-viewer", password=None, is_staff=True)
        cls.viewer.user_permissions.add(Permission.objects.get(content_type__app_label="catalog", codename="view_product"))
        cls.product = Product.objects.create(name="Auto product", sku="AUTO-001", price="12.00")
        cls.variant = ProductVariant.objects.create(product=cls.product, name="Size", value="Small")

    def setUp(self):
        self.client.force_login(self.user)
        self.index = reverse("admin:index")
        self.list_url = reverse("admin:catalog_product_changelist")
        self.change_url = reverse("admin:catalog_product_change", args=[self.product.pk])
        self.preference = reverse("nova_admin:preference")

    def test_auto_post_is_saved_and_get_does_not_rewrite_choice(self):
        self.assertContains(self.client.get(self.index), "nova-mode-light")
        target = self.list_url + "?q=AUTO-001"
        self.assertRedirects(self.client.post(self.preference, {"mode": "auto", "next": target}), target)
        for url in (self.index, target, self.change_url):
            response = self.client.get(url)
            self.assertContains(response, "nova-mode-auto")
            self.assertContains(response, 'value="auto" selected')
            self.assertContains(response, "nova_admin/theme.css")
            self.assertContains(response, "admin/js/theme.js")
            self.assertEqual(self.client.session[SESSION_KEY], "auto")
        self.assertEqual(self.client.get(self.preference, {"mode": "dark"}).status_code, 405)
        self.assertEqual(self.client.session[SESSION_KEY], "auto")

    def test_manual_choices_remain_authoritative_after_auto(self):
        for mode in ("auto", "dark", "light", "auto"):
            self.client.post(self.preference, {"mode": mode})
            response = self.client.get(self.list_url)
            self.assertContains(response, f"nova-mode-{mode}")
            self.assertEqual(response.context["nova_admin_mode"], mode)
            self.assertEqual(self.client.session[SESSION_KEY], mode)

    def test_auto_requires_csrf_and_invalid_posts_preserve_saved_choice(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(self.preference, {"mode": "auto"}).status_code, 403)
        self.assertNotIn(SESSION_KEY, client.session)
        client.get(self.index)
        data = {"mode": "auto", "csrfmiddlewaretoken": client.cookies["csrftoken"].value}
        self.assertRedirects(client.post(self.preference, data), self.index)
        data["mode"] = "AUTO"
        self.assertEqual(client.post(self.preference, data).status_code, 400)
        self.assertEqual(client.session[SESSION_KEY], "auto")

    def assert_native_assets_only(self, response):
        self.assertContains(response, "admin/css/base.css")
        self.assertContains(response, "admin/js/theme.js")
        for asset in ("theme.css", "navigation.js", "enhancements.js"):
            self.assertNotContains(response, f"nova_admin/{asset}")
        self.assertNotContains(response, "nova-mode-")

    def test_native_switch_removes_all_nova_assets_and_can_return_to_auto(self):
        for mode in ("auto", "native"):
            self.client.post(self.preference, {"mode": mode})
        self.assert_native_assets_only(self.client.get(self.list_url))
        self.assertRedirects(self.client.post(self.preference, {"mode": "auto"}), self.index)
        self.assertContains(self.client.get(self.list_url), "nova-mode-auto")

    def test_disable_or_missing_processor_keeps_saved_auto_but_renders_native(self):
        self.client.post(self.preference, {"mode": "auto"})
        with override_settings(NOVA_ADMIN_ENABLED=False):
            self.assert_native_assets_only(self.client.get(self.list_url))
        templates = deepcopy(settings.TEMPLATES)
        templates[0]["OPTIONS"]["context_processors"].remove("nova_admin.context_processors.theme")
        with override_settings(TEMPLATES=templates):
            self.assert_native_assets_only(self.client.get(self.list_url))
        self.assertEqual(self.client.session[SESSION_KEY], "auto")

    @override_settings(ROOT_URLCONF="tests.multisite_urls", NOVA_ADMIN_URL_NAMESPACES={"warehouse": "warehouse_theme", "review": "review_theme"})
    def test_auto_preference_keeps_site_permission_and_redirect_boundaries(self):
        endpoint = reverse("warehouse_theme:preference")
        response = self.client.post(endpoint, {"mode": "auto", "next": reverse("review:index")})
        self.assertEqual(response.url, reverse("warehouse:index"))
        self.assertEqual(self.client.session[SESSION_KEY], "auto")
        self.client.force_login(self.viewer)
        response = self.client.post(reverse("review_theme:preference"), {"mode": "auto"})
        self.assertTrue(response.url.startswith(reverse("review:login")))
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_auto_list_checkbox_changes_only_on_native_save_with_audit_log(self):
        self.client.post(self.preference, {"mode": "auto"})
        response = self.client.get(self.list_url)
        formset = response.context["cl"].formset
        self.assertContains(response, 'name="_selected_action"')
        self.assertContains(response, 'name="_save"')
        self.assertFalse(LogEntry.objects.filter(action_flag=CHANGE).exists())
        payload = {field.html_name: field.value() for field in formset.management_form}
        form = formset.forms[0]
        payload.update({form["id"].html_name: str(self.product.pk), form["featured"].html_name: "on", "_save": "Save"})
        self.assertRedirects(self.client.post(self.list_url, payload), self.list_url)
        self.product.refresh_from_db()
        self.assertTrue(self.product.featured)
        self.assertEqual(LogEntry.objects.filter(action_flag=CHANGE, object_id=str(self.product.pk)).count(), 1)
        # Inline form, management fields, deletion checkbox and native save stay real.
        response = self.client.get(self.change_url)
        for name in ("variants-TOTAL_FORMS", "variants-0-name", "variants-0-DELETE", "_save"):
            self.assertContains(response, f'name="{name}"')
        self.assertContains(response, "admin/js/inlines.js")


class DensityAndPaletteContracts(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.css = Path(finders.find("nova_admin/theme.css")).read_text()

    def declarations(self, selector):
        matches = re.findall(re.escape(selector) + r"\s*\{([^}]+)\}", self.css)
        self.assertTrue(matches, selector)
        return "\n".join(matches)

    @staticmethod
    def colors(rule):
        return dict(re.findall(r"(--[a-z-]+): (#[0-9a-f]{6});", rule))

    def test_auto_reuses_same_complete_palettes_without_changing_manual_selectors(self):
        dark = self.declarations("body.nova-admin.nova-mode-dark")
        light = self.declarations("body.nova-admin.nova-mode-light")
        auto_dark = self.declarations("body.nova-admin.nova-mode-auto")
        self.assertEqual(self.colors(dark), self.colors(auto_dark))
        self.assertIn("body.nova-admin.nova-mode-auto,\nbody.nova-admin.nova-mode-light {", self.css)
        media = self.css.split("@media (prefers-color-scheme: dark)", 1)[1].split("body.nova-admin #header", 1)[0]
        self.assertIn("nova-mode-auto", media)
        self.assertNotIn("nova-mode-light", media)
        self.assertNotIn("nova-mode-dark", media)
        self.assertIn("color-scheme: light", light)
        self.assertIn("color-scheme: dark", auto_dark)

    def test_both_palettes_have_aa_body_muted_link_and_button_text(self):
        def luminance(value):
            rgb = [int(value[i:i+2], 16) / 255 for i in (1, 3, 5)]
            rgb = [x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4 for x in rgb]
            return sum(x * weight for x, weight in zip(rgb, (.2126, .7152, .0722)))
        pairs = [(fg, bg) for fg in ("--body-fg", "--body-quiet-color", "--link-fg") for bg in ("--body-bg", "--nova-panel", "--darkened-bg", "--selected-row")]
        pairs += [("--button-fg", bg) for bg in ("--button-bg", "--button-hover-bg", "--default-button-bg", "--default-button-hover-bg")]
        for mode in ("light", "dark"):
            colors = self.colors(self.declarations(f"body.nova-admin.nova-mode-{mode}"))
            for foreground, background in pairs:
                with self.subTest(mode=mode, foreground=foreground, background=background):
                    high, low = sorted((luminance(colors[foreground]), luminance(colors[background])), reverse=True)
                    self.assertGreaterEqual((high + .05) / (low + .05), 4.5)

    def test_density_variables_drive_native_table_form_and_action_rules(self):
        checks = (
            ("body.nova-admin th, body.nova-admin td", "padding: var(--nova-cell-padding)"),
            ("body.nova-admin #result_list thead th .text span", "padding: var(--nova-cell-padding)"),
            ("body.nova-admin .inline-group .tabular :is(th, td):not(.original)", "padding: var(--nova-cell-padding)"),
            ("body.nova-admin .inline-group .tabular tr.add-row td", "padding: var(--nova-section-padding)"),
            ("body.nova-admin #toolbar #searchbar", "padding: var(--nova-control-padding-block) var(--nova-control-padding-inline)"),
            ("body.nova-admin #toolbar form input[type=submit]", "padding: var(--nova-action-padding)"),
        )
        for selector, declaration in checks:
            with self.subTest(selector=selector):
                property_name, expected = declaration.split(": ", 1)
                values = re.findall(r"(?<![-\w])" + re.escape(property_name) + r":\s*([^;]+);", self.declarations(selector))
                self.assertTrue(values, selector)
                self.assertEqual(values[-1], expected)
        form_rules = re.findall(r"body\.nova-admin \.form-row\s*\{([^}]+)\}", self.css)
        self.assertTrue(any("padding: var(--nova-form-row-padding)" in rule for rule in form_rules))
        select = self.declarations("body.nova-admin select:not([multiple]):not([size]):not(.select2-hidden-accessible)")
        self.assertIn("var(--nova-control-padding-block)", select)
        self.assertIn("var(--nova-control-padding-inline)", select)
        self.assertIn("max(var(--nova-control-min-height), var(--nova-touch-min))", select)
        self.assertIn("var(--nova-action-padding)", self.declarations("body.nova-admin .submit-row a.deletelink"))
        self.assertIn("padding-top: 2em", self.declarations("body.nova-admin .inline-group .tabular tr.has_original td:not(.original)"))

    def test_density_defaults_are_concrete_without_custom_property_cycles(self):
        defaults = dict(re.findall(r"(--nova-[a-z-]+):\s*([^;]+);", self.css.split("}\n", 1)[0]))
        for name, expected in {
            "--nova-cell-padding": "13px 16px",
            "--nova-form-row-padding": "18px 16px",
            "--nova-control-min-height": "40px",
            "--nova-action-padding": "11px 17px",
            "--nova-section-padding": "14px 16px",
        }.items():
            self.assertEqual(defaults[name], expected)
        for name, value in re.findall(r"(--[a-z-]+):\s*([^;]+);", self.css):
            self.assertNotIn(f"var({name})", value)

    def test_touch_floor_covers_real_checkboxes_and_save_controls(self):
        touch = self.css.split("@media (pointer: coarse), (max-width: 767px)", 1)[1]
        for token in ("min-height: max(44px, var(--nova-control-min-height))", "input[type=submit]", ".submit-row a", ".select2-selection", "#result_list input[type=checkbox]:not(.nova-switch)", "input[type=radio]):not(.nova-switch)", "min-width: 24px", "min-height: 24px"):
            self.assertIn(token, touch)
        switch = self.declarations('body.nova-admin #result_list input[type=checkbox].nova-switch')
        self.assertIn('width: 40px', switch)
        self.assertIn('height: 24px', switch)
        self.assertNotRegex(self.css, r'input\[type=checkbox\]\s*\{[^}]*appearance:\s*none')

    def test_chinese_tracking_is_language_scoped(self):
        for selector in ("body.nova-admin #site-name:lang(zh-hans)", "body.nova-admin #content :is(h1, h2, h3, h4, h5, h6):lang(zh-hans)"):
            self.assertIn(selector, self.css)
        self.assertIn("letter-spacing: normal", self.declarations("body.nova-admin #content :is(h1, h2, h3, h4, h5, h6):lang(zh-hans)"))
        self.assertIn("letter-spacing: -.03em", self.css)
