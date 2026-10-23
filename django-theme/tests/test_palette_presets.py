"""Independent palette preferences preserve native Admin boundaries."""
from pathlib import Path
from types import SimpleNamespace

from bs4 import BeautifulSoup
from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils.translation import override

from nova_admin.preferences import (
    MODES, PALETTES, PALETTE_SESSION_KEY, SESSION_KEY, selected_palette,
)


class PaletteSelectionTests(SimpleTestCase):
    def test_invalid_setting_and_session_types_degrade_safely(self):
        for invalid in (None, [], {}, True, "", "blue", '<script>'):
            with self.subTest(value=invalid), override_settings(NOVA_ADMIN_DEFAULT_PALETTE=invalid):
                self.assertEqual(selected_palette(SimpleNamespace()), "default")
            with override_settings(NOVA_ADMIN_DEFAULT_PALETTE="teal"):
                self.assertEqual(selected_palette(SimpleNamespace(session={PALETTE_SESSION_KEY: invalid})), "teal")

    def test_configured_default_and_valid_session(self):
        for palette in PALETTES:
            with override_settings(NOVA_ADMIN_DEFAULT_PALETTE=palette):
                self.assertEqual(selected_palette(SimpleNamespace()), palette)
            self.assertEqual(selected_palette(SimpleNamespace(session={PALETTE_SESSION_KEY: palette})), palette)

    def test_styles_preserve_default_and_host_override_specificity(self):
        css = Path(finders.find("nova_admin/presets.css")).read_text()
        self.assertNotIn(".nova-palette-default", css)
        self.assertNotIn("!important", css)
        for palette in PALETTES - {"default"}:
            self.assertIn(f"body.nova-admin:where(.nova-palette-{palette})", css)
        for token in ("brand-light", "brand-light-hover", "brand-dark", "brand-dark-hover"):
            self.assertEqual(css.count(f"--nova-{token}:"), len(PALETTES) - 1)
        self.assertIn("@media (prefers-color-scheme: dark)", css)
        for forbidden in ("--error-fg:", "--delete-button-bg:", "--nova-success-bg:"):
            self.assertNotIn(forbidden, css)


class PaletteIntegrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser("palette-admin", "palette@example.invalid", "test-only-Palette123!")

    def setUp(self):
        self.client.force_login(self.user)
        self.index = reverse("admin:index")
        self.preference = reverse("nova_admin:preference")

    def test_each_mode_palette_pair_and_default_recovery(self):
        for mode in MODES:
            for palette in PALETTES:
                with self.subTest(mode=mode, palette=palette):
                    self.assertEqual(self.client.post(self.preference, {"mode": mode, "palette": palette}).status_code, 302)
                    self.assertEqual(self.client.session[SESSION_KEY], mode)
                    self.assertEqual(self.client.session[PALETTE_SESSION_KEY], palette)
                    response = self.client.get(self.index)
                    soup = BeautifulSoup(response.content, "html.parser")
                    self.assertEqual(soup.select_one('#nova-admin-palette option[selected]')["value"], palette)
                    if mode == "native":
                        self.assertNotContains(response, "nova_admin/presets.css")
                        self.assertNotContains(response, "nova-palette-")
                    else:
                        self.assertContains(response, f"nova-palette-{palette}")
                        self.assertContains(response, "nova_admin/presets.css")

    def test_anonymous_login_restores_palette_without_enabling_preference_writes(self):
        client = Client()
        login = reverse("admin:login")
        for mode in MODES:
            for palette in PALETTES:
                with self.subTest(mode=mode, palette=palette):
                    session = client.session
                    session[SESSION_KEY] = mode
                    session[PALETTE_SESSION_KEY] = palette
                    session.save()
                    response = client.get(login)
                    if mode == "native":
                        self.assertNotContains(response, "nova_admin/presets.css")
                        self.assertNotContains(response, "nova-palette-")
                    else:
                        self.assertContains(response, f"nova-palette-{palette}")
                        self.assertContains(response, f"nova-mode-{mode}")
                    before = dict(client.session)
                    response = client.post(self.preference, {"mode": "light", "palette": "default"})
                    self.assertEqual(response.status_code, 302)
                    self.assertTrue(response.url.startswith(login + "?"))
                    self.assertEqual(dict(client.session), before)

    def test_invalid_pairs_never_partially_write(self):
        self.client.post(self.preference, {"mode": "dark", "palette": "teal"})
        before = dict(self.client.session)
        for values in ({"mode": "light", "palette": "unknown"}, {"mode": "unknown", "palette": "violet"}, {"palette": "indigo"}, {"mode": "light", "palette": ""}):
            with self.subTest(values=values):
                self.assertEqual(self.client.post(self.preference, values).status_code, 400)
                self.assertEqual(dict(self.client.session), before)

    def test_mode_only_post_keeps_palette_or_unsaved_default(self):
        with override_settings(NOVA_ADMIN_DEFAULT_PALETTE="indigo"):
            self.client.post(self.preference, {"mode": "light"})
            self.assertNotIn(PALETTE_SESSION_KEY, self.client.session)
            self.assertContains(self.client.get(self.index), "nova-palette-indigo")
        for palette in PALETTES:
            with self.subTest(palette=palette):
                self.client.post(self.preference, {"mode": "dark", "palette": palette})
                self.client.post(self.preference, {"mode": "native"})
                self.assertEqual(self.client.session[PALETTE_SESSION_KEY], palette)
                self.client.post(self.preference, {"mode": "auto"})
                self.assertContains(self.client.get(self.index), f"nova-palette-{palette}")

    def test_palette_is_csrf_protected(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(self.preference, {"mode": "dark", "palette": "teal"}).status_code, 403)
        self.assertNotIn(PALETTE_SESSION_KEY, client.session)
        client.get(self.index)
        response = client.post(self.preference, {"mode": "dark", "palette": "teal", "csrfmiddlewaretoken": client.cookies["csrftoken"].value})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(client.session[PALETTE_SESSION_KEY], "teal")

    @override_settings(ROOT_URLCONF="tests.multisite_urls", NOVA_ADMIN_URL_NAMESPACES={"warehouse": "warehouse_theme", "review": "review_theme"})
    def test_palette_obeys_exact_adminsite_permissions_and_return_scope(self):
        for site, other in (("warehouse", "review"), ("review", "warehouse")):
            response = self.client.post(reverse(f"{site}_theme:preference"), {"mode": "light", "palette": "indigo", "next": reverse(f"{other}:index")})
            self.assertEqual(response.url, reverse(f"{site}:index"))
        staff = get_user_model().objects.create_user("palette-staff", is_staff=True)
        self.client.force_login(staff)
        self.client.post(reverse("warehouse_theme:preference"), {"mode": "light", "palette": "teal"})
        before = dict(self.client.session)
        response = self.client.post(reverse("review_theme:preference"), {"mode": "dark", "palette": "violet"})
        self.assertTrue(response.url.startswith(reverse("review:login")))
        self.assertEqual(dict(self.client.session), before)

    def test_palette_does_not_weaken_return_scope(self):
        response = self.client.post(self.preference, {"mode": "light", "palette": "teal", "next": "//evil.invalid/admin/"})
        self.assertEqual(response.url, self.index)
        response = self.client.post(self.preference, {"mode": "light", "palette": "teal", "next": self.index + "?q=test"})
        self.assertEqual(response.url, self.index + "?q=test")

    def test_stylesheet_order_and_localized_labels(self):
        response = self.client.get(self.index)
        html = response.content.decode()
        assets = ["nova_admin/theme.css", "nova_admin/tokens.css", "nova_admin/presets.css", "catalog/enterprise.css"]
        self.assertEqual(sorted(assets, key=html.index), assets)
        for language, labels in (("en", ["Color palette", "Project default", "Healthcare teal", "Professional indigo", "Education violet", "Retail terracotta", "Graphite black", "Midnight blue", "Forest green", "Warm amber", "Deep ocean", "Slate gray", "Dusk plum", "Mocha brown"]), ("zh-hans", ["配色", "项目默认", "医疗青", "专业靛", "文教紫", "零售陶", "石墨黑", "午夜蓝", "松林绿", "暖琥珀", "深海青", "雾岩灰", "暮梅紫", "摩卡棕"])):
            with override(language):
                page = self.client.get(self.index)
                for label in labels:
                    self.assertContains(page, label)
        with override("zh-hans"):
            self.assertContains(self.client.post(self.preference, {"mode": "light", "palette": "bad"}), "未知配色", status_code=400)

    @override_settings(NOVA_ADMIN_ENABLED=False)
    def test_disabled_omits_all_nova_assets_and_controls(self):
        response = self.client.get(self.index)
        for asset in ("nova_admin/", "catalog/enterprise.css", "nova-admin-palette"):
            self.assertNotContains(response, asset)
        self.assertEqual(self.client.post(self.preference, {"mode": "light", "palette": "teal"}).status_code, 404)
