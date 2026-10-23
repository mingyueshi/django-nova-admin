"""Declarative branding security, native rollback, and semantic token contracts."""
import re
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup
from django.conf import settings
from django.contrib.staticfiles import finders
from django.template import engines
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy

from nova_admin.branding import branding, brand_initial, local_static_url
from nova_admin.context_processors import theme
from nova_admin.preferences import SESSION_KEY

BRAND = {"logo": "project/brand.svg", "logo_alt": "Example brand", "favicon": "project/favicon.ico",
         "login_background": "project/login.webp", "footer": "Example staff portal"}


class BrandingBoundaryTests(SimpleTestCase):
    def test_initial_supports_chinese_latin_numbers_and_unicode(self):
        for name, initial in (("星河后台", "星"), (" atlas", "A"), ("-- orbit", "O"),
                              ("2026 Admin", "2"), ("équipe", "É"), ("Ａtlas", "A"),
                              ("𠮷野后台", "𠮷"), ("***", "?"), (None, "?")):
            with self.subTest(name=name):
                self.assertEqual(brand_initial(name), initial)

    def test_name_is_optional_plain_text_without_mutating_settings(self):
        for name, expected in (("  星河管理  ", "星河管理"), (gettext_lazy("Atlas"), "Atlas"),
                               (None, ""), (True, ""), ({"name": "bad"}, "")):
            config = {"name": name}
            with self.subTest(name=name), override_settings(NOVA_ADMIN_BRANDING=config):
                self.assertEqual(branding()["name"], expected)
                self.assertEqual(config, {"name": name})
    @override_settings(STATIC_URL="/static/")
    def test_relative_images_use_django_static_and_manifest_names(self):
        self.assertEqual(local_static_url("project/logo.svg"), "/static/project/logo.svg")
        self.assertEqual(local_static_url("project/favicon.ico", favicon=True), "/static/project/favicon.ico")
        self.assertEqual(local_static_url("project/photo-1.AVIF"), "/static/project/photo-1.AVIF")
        with patch("nova_admin.branding.static", return_value="/assets/brand.a12b3.svg"):
            self.assertEqual(local_static_url("project/logo.svg"), "/assets/brand.a12b3.svg")

    def test_paths_reject_urls_traversal_markup_encoding_and_wrong_types(self):
        invalid = [None, True, [], {}, 123, "", "/brand.svg", "//evil.invalid/logo.svg",
                   "https://evil.invalid/logo.svg", "data:image/svg+xml,<svg/>", "javascript:alert(1)",
                   "file:///tmp/logo.svg", "../logo.svg", "brand/../logo.svg", "brand/./logo.svg",
                   "brand//logo.svg", "brand\\logo.svg", "brand/%2e%2e/logo.svg", "brand/logo.svg?x=1",
                   "brand/logo.svg#fragment", '<img src=x onerror="x">', "brand/logo.svg\n",
                   "brand/logo.svg ", "brand/logo.html", "brand/file.css", "brand/favicon.ico"]
        with patch("nova_admin.branding.static") as resolve_static:
            for value in invalid:
                with self.subTest(value=value):
                    self.assertEqual(local_static_url(value), "")
        resolve_static.assert_not_called()

    def test_storage_cannot_introduce_unsafe_urls_and_missing_manifest_is_inert(self):
        invalid = ["https://cdn.invalid/logo.svg", "//cdn.invalid/logo.svg", "javascript:alert(1)",
                   "/static/logo.svg?signature=secret", "/static/logo.svg#fragment", "/static/../logo.svg",
                   "/static/%2e%2e/logo.svg", "/%2fcdn.invalid/logo.svg", "/static/lo%0ago.svg",
                   "/static/lo%5cgo.svg", "/static/lo\ngo.svg", "/static/lo\tgo.svg",
                   " /static/logo.svg", "relative/logo.svg", None, b"/static/logo.svg"]
        for value in invalid:
            with self.subTest(value=value), patch("nova_admin.branding.static", return_value=value):
                self.assertEqual(local_static_url("project/logo.svg"), "")
        with patch("nova_admin.branding.static", side_effect=ValueError("Missing manifest entry")):
            self.assertEqual(local_static_url("project/logo.svg"), "")

    @override_settings(STATIC_URL="https://cdn.invalid/static/", NOVA_ADMIN_BRANDING=BRAND)
    def test_remote_static_omits_images_and_preserves_plain_footer(self):
        values = branding()
        self.assertEqual(values["footer"], BRAND["footer"])
        for key in ("logo_url", "favicon_url", "login_background_url"):
            self.assertEqual(values[key], "")

    def test_invalid_settings_and_fields_do_not_mutate_configuration(self):
        for value in (None, [], "<script>bad</script>", True):
            with self.subTest(value=value), override_settings(NOVA_ADMIN_BRANDING=value):
                self.assertTrue(all(value == "" for value in branding().values()))
        config = {**BRAND, "logo": "https://remote.invalid/brand.svg", "footer": gettext_lazy("Plain footer")}
        before = deepcopy(config)
        with override_settings(NOVA_ADMIN_BRANDING=config):
            result = branding()
        self.assertEqual(result["logo_url"], "")
        self.assertTrue(result["favicon_url"])
        self.assertEqual(result["footer"], "Plain footer")
        self.assertEqual(config, before)

    def test_native_and_disabled_modes_skip_asset_resolution(self):
        request = RequestFactory().get("/")
        for enabled, mode in ((True, "native"), (False, "light")):
            request.session = {SESSION_KEY: mode}
            with self.subTest(enabled=enabled, mode=mode), override_settings(NOVA_ADMIN_ENABLED=enabled):
                with patch("nova_admin.context_processors.branding") as read_brand:
                    self.assertEqual(theme(request)["nova_admin_branding"], {})
                read_brand.assert_not_called()


@override_settings(NOVA_ADMIN_BRANDING=BRAND, STATIC_URL="/static/")
class BrandingRenderingTests(TestCase):
    def test_configured_name_updates_header_title_and_login_decoration(self):
        for name, initial in (("星河后台", "星"), ("Atlas Admin", "A"), ("-- orbit", "O")):
            with self.subTest(name=name), override_settings(NOVA_ADMIN_BRANDING={"name": name}):
                soup = BeautifulSoup(self.page().content, "html.parser")
                self.assertEqual(soup.select_one('.nova-brand-name').get_text(), name)
                self.assertEqual(soup.select_one('.nova-brand-initial').get_text(), initial)
                self.assertEqual(soup.select_one('.nova-brand-initial')['aria-hidden'], 'true')
                self.assertEqual(soup.select_one('.nova-login-glyph').get_text(), initial)
                self.assertTrue(soup.title.get_text().endswith(' | ' + name))
                self.assertEqual(len(soup.select('#site-name')), 1)
                self.assertEqual(len(soup.select('#login-form')), 1)

    @override_settings(NOVA_ADMIN_BRANDING={})
    def test_existing_adminsite_header_drives_initial_without_global_mutation(self):
        from django.contrib import admin
        original = admin.site.site_header
        for name, initial in (("Warehouse", "W"), ("志途谱后台", "志")):
            # Patch the initialized site's actual attributes, not LazyObject's
            # proxy __dict__, so unittest.mock restores instance overrides.
            with self.subTest(name=name), patch.object(admin.site._wrapped, 'site_header', name), patch.object(admin.site._wrapped, 'site_title', 'Different tab title'):
                soup = BeautifulSoup(self.page().content, "html.parser")
                self.assertEqual(soup.select_one('.nova-brand-initial').get_text(), initial)
                self.assertEqual(soup.select_one('.nova-login-glyph').get_text(), initial)
                self.assertEqual(soup.select_one('.nova-brand-name').get_text(), name)
                self.assertIn('Different tab title', soup.title.get_text())
        self.assertEqual(admin.site.site_header, original)

    def test_explicit_picture_logo_takes_precedence_over_generated_initial(self):
        with override_settings(NOVA_ADMIN_BRANDING={**BRAND, 'name': 'Atlas'}):
            soup = BeautifulSoup(self.page().content, 'html.parser')
        self.assertEqual(soup.select_one('.nova-brand-name').get_text(), 'Atlas')
        self.assertEqual(len(soup.select('.nova-brand-logo')), 1)
        self.assertIsNone(soup.select_one('.nova-brand-initial'))

    def test_even_marked_safe_name_cannot_insert_markup(self):
        name = mark_safe('<img src=x onerror="bad()"><script>bad()</script>')
        with override_settings(NOVA_ADMIN_BRANDING={'name': name}):
            soup = BeautifulSoup(self.page().content, 'html.parser')
        self.assertEqual(soup.select_one('.nova-brand-name').get_text(), name)
        self.assertIn(name, soup.title.get_text())
        self.assertIsNone(soup.select_one('.nova-brand-name img, .nova-brand-name script, [onerror]'))

    @override_settings(NOVA_ADMIN_BRANDING={'name': 'Configured brand'})
    def test_native_and_disabled_ignore_name_and_generated_badge(self):
        for enabled, mode in ((True, 'native'), (False, 'dark')):
            with override_settings(NOVA_ADMIN_ENABLED=enabled):
                response = self.page(mode)
                self.assertNotContains(response, 'Configured brand')
                self.assertNotContains(response, 'nova-brand-initial')

    def page(self, mode="light"):
        session = self.client.session
        session[SESSION_KEY] = mode
        session.save()
        return self.client.get(reverse("admin:login"))

    def test_branding_renders_once_without_changing_login_semantics(self):
        for mode in ("light", "dark", "auto"):
            with self.subTest(mode=mode):
                soup = BeautifulSoup(self.page(mode).content, "html.parser")
                self.assertEqual(soup.select_one(".nova-brand-logo")["src"], "/static/project/brand.svg")
                self.assertEqual(soup.select_one(".nova-brand-logo")["alt"], "Example brand")
                self.assertEqual(soup.select_one('link[rel="icon"]')["href"], "/static/project/favicon.ico")
                self.assertEqual(soup.select_one(".nova-login-background")["src"], "/static/project/login.webp")
                self.assertEqual(soup.select_one(".nova-login-background")["alt"], "")
                self.assertEqual(soup.select_one(".nova-brand-footer").get_text(), BRAND["footer"])
                self.assertEqual(len(soup.select("#site-name")), 1)
                self.assertEqual(len(soup.select("#login-form")), 1)
                self.assertIsNotNone(soup.select_one('#login-form [name="csrfmiddlewaretoken"]'))
                self.assertIsNotNone(soup.select_one('#login-form [name="next"]'))

    def test_even_marked_safe_footer_and_alt_are_plain_text(self):
        hostile = mark_safe('<img src=x onerror="alert(1)"><script>bad</script>')
        with override_settings(NOVA_ADMIN_BRANDING={**BRAND, "footer": hostile, "logo_alt": hostile}):
            soup = BeautifulSoup(self.page().content, "html.parser")
        self.assertEqual(soup.select_one(".nova-brand-footer").get_text(), hostile)
        self.assertEqual(soup.select_one(".nova-brand-logo")["alt"], hostile)
        self.assertIsNone(soup.select_one(".nova-brand-footer img, .nova-brand-footer script, [onerror]"))

    @override_settings(NOVA_ADMIN_BRANDING={})
    def test_empty_settings_preserve_header_art_and_empty_footer(self):
        soup = BeautifulSoup(self.page().content, "html.parser")
        self.assertIsNotNone(soup.select_one("#site-name a"))
        self.assertIsNotNone(soup.select_one(".nova-login-glyph"))
        self.assertIsNone(soup.select_one(".nova-brand-logo, .nova-brand-footer"))
        self.assertEqual(soup.select_one("#footer").contents, [])

    def test_native_and_disabled_omit_branding_and_tokens(self):
        for enabled, mode in ((True, "native"), (False, "dark")):
            with self.subTest(enabled=enabled, mode=mode), override_settings(NOVA_ADMIN_ENABLED=enabled):
                response = self.page(mode)
                for fragment in ("nova_admin/tokens.css", "project/brand.svg", "project/favicon.ico", "project/login.webp", BRAND["footer"], "nova-login-art"):
                    self.assertNotContains(response, fragment)
                self.assertContains(response, 'id="login-form"')
                self.assertContains(response, 'id="site-name"')

    def test_omitted_context_processor_keeps_native_header_without_branding(self):
        templates = deepcopy(settings.TEMPLATES)
        templates[0]["OPTIONS"]["context_processors"].remove("nova_admin.context_processors.theme")
        with override_settings(TEMPLATES=templates):
            response = self.page()
        self.assertContains(response, 'id="site-name"')
        self.assertNotContains(response, "nova_admin/tokens.css")
        self.assertNotContains(response, "project/brand.svg")

    def test_tokens_follow_theme_with_csp_nonce_and_no_inline_style(self):
        html = render_to_string("admin/login.html", {"nova_admin_active": True, "nova_admin_mode": "light",
                               "nova_admin_branding": branding(), "csp_nonce": "nonce-value"})
        soup = BeautifulSoup(html, "html.parser")
        self.assertEqual(len(soup.select('link[href$="nova_admin/tokens.css"]')), 1)
        self.assertEqual(soup.select_one('link[href$="nova_admin/tokens.css"]')["nonce"], "nonce-value")
        self.assertLess(html.index("nova_admin/theme.css"), html.index("nova_admin/tokens.css"))
        self.assertIsNone(soup.select_one(".nova-login-art[style], .nova-brand-logo[onload]"))

    def test_deliberate_template_blocks_work_only_inside_active_boundary(self):
        template = engines["django"].from_string(
            '{% extends "admin/base_site.html" %}'
            '{% block nova_branding %}<em id="project-header">Reviewed brand</em>{% endblock %}'
            '{% block nova_footer %}<strong id="project-footer">Reviewed footer</strong>{% endblock %}'
        )
        for active in (True, False):
            with self.subTest(active=active):
                soup = BeautifulSoup(template.render({"nova_admin_active": active}), "html.parser")
                self.assertEqual(soup.select_one("#project-header") is not None, active)
                self.assertEqual(soup.select_one("#project-footer") is not None, active)


class SemanticTokenTests(SimpleTestCase):
    def test_logo_has_definite_height_for_viewbox_only_svg_intrinsic_sizing(self):
        css = Path(finders.find("nova_admin/theme.css")).read_text()
        rule = re.search(r"body\.nova-admin \.nova-brand-logo\s*\{([^}]+)\}", css)[1]
        # max-height alone is not an intrinsic size for an SVG lacking width
        # and height attributes; it can leave the title with the logo's space.
        properties = dict(re.findall(r"([a-z-]+):\s*([^;]+);", rule))
        self.assertEqual(properties["height"], "36px")
        self.assertEqual(properties["width"], "auto")
        self.assertEqual(properties["max-width"], "160px")
        self.assertEqual(properties["object-fit"], "contain")

    def test_login_brand_has_available_width_without_disabling_long_title_wrap(self):
        css = Path(finders.find("nova_admin/login.css")).read_text()

        def declarations(selector):
            return "\n".join(re.findall(re.escape(selector) + r"\s*\{([^}]+)\}", css))

        # The entire shrink-to-fit chain matters: a wide header alone does not
        # prevent its flex child/inline-flex link from sizing to narrow content.
        self.assertIn("width: 100%;", declarations("body.nova-admin.login #header"))
        brand = declarations("body.nova-admin.login #branding")
        for value in ("width: 100%;", "min-width: 0;", "max-width: 100%;"):
            self.assertIn(value, brand)
        anchor = declarations("body.nova-admin.login #site-name.nova-custom-brand a")
        self.assertIn("width: max-content;", anchor)
        self.assertIn("max-width: 100%;", anchor)
        title = declarations("body.nova-admin.login #site-name.nova-custom-brand span")
        for value in ("min-width: 0;", "white-space: normal;", "overflow-wrap: anywhere;"):
            self.assertIn(value, title)
        # Do not fix the short title by clipping or forcing every brand to one line.
        self.assertNotIn("white-space: nowrap", anchor + title)
        self.assertNotIn("overflow: hidden", anchor + title)

    def test_four_colors_reach_native_roles_and_auto_dark_matches(self):
        css = Path(finders.find("nova_admin/tokens.css")).read_text()
        for name in ("--nova-brand-light", "--nova-brand-light-hover", "--nova-brand-dark", "--nova-brand-dark-hover"):
            self.assertIn("var(" + name + ",", css)
        dark = re.search(r"body.nova-admin.nova-mode-dark\s*\{([^}]+)\}", css)[1]
        auto = re.search(r"body.nova-admin.nova-mode-auto\s*\{([^}]+)\}", css.split("@media (prefers-color-scheme: dark)", 1)[1])[1]
        self.assertEqual(re.sub(r"\s+", "", dark), re.sub(r"\s+", "", auto))
        for role in ("--button-bg", "--default-button-bg", "--link-fg", "--accent"):
            self.assertRegex(dark, re.escape(role) + r": var\(--nova-brand-dark,")

    def test_fallback_colors_preserve_existing_roles_exactly(self):
        css = Path(finders.find("nova_admin/tokens.css")).read_text()
        core = Path(finders.find("nova_admin/theme.css")).read_text()
        for mode in ("light", "dark"):
            selector = r"body.nova-admin.nova-mode-" + mode + r"\s*\{([^}]+)\}"
            colors = dict(re.findall(r"(--[a-z-]+): (#[0-9a-f]{6});", re.search(selector, core)[1]))
            for role, fallback in re.findall(r"(--[a-z-]+): var\(--[a-z-]+, (#[0-9a-f]{6})\);", re.search(selector, css)[1]):
                with self.subTest(mode=mode, role=role):
                    self.assertEqual(fallback, colors[role])

    def test_density_spacing_radius_scoped_and_login_geometry_preserved(self):
        css = Path(finders.find("nova_admin/tokens.css")).read_text()
        self.assertTrue(css.split("*/", 1)[1].lstrip().startswith("body.nova-admin {"))
        for token in ("--nova-density", "--nova-spacing", "--nova-control-radius", "--nova-action-radius", "--nova-login-radius"):
            self.assertIn(token, css)
        login = Path(finders.find("nova_admin/login.css")).read_text()
        self.assertIn("min-height: 48px", login)
        self.assertIn(".nova-login-art { display: none; }", login)
        self.assertIn("border: 0; border-radius: 0; background: transparent; box-shadow: none", login)
        self.assertNotIn("var(--nova-density)", login)
