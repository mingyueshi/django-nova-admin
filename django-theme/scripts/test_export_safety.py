#!/usr/bin/env python3
"""Regression tests for semantic-but-inert Django sample forms (no DB needed).

python scripts/test_export_safety.py
python scripts/test_export_safety.py --export-dir /path/to/generated/samples
"""
import argparse
import json
from pathlib import Path
import sys
import unittest

from bs4 import BeautifulSoup
import export_admin_samples as exporter

EXPORT_DIR = None


class InertFormSafetyTests(unittest.TestCase):
    def setUp(self):
        self.html = exporter.sanitize_html(
            '<!doctype html><html lang="zh-hans"><head><title>Test</title>'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '</head><body><form id="product_form" class="module aligned" action="/admin/save/" method="post">'
            '<input type="hidden" name="csrfmiddlewaretoken" value="SECRET">'
            '<input type="password" name="password" value="SECRET">'
            '<input id="id_name" type="text" name="name" value="Synthetic">'
            '<select name="mode"><option value="dark">Dark</option></select>'
            '<textarea name="body">Synthetic</textarea><input type="submit" name="_save" value="Save">'
            '<button name="send" type="submit">Send</button></form></body></html>',
            mode="native", page="changeform", django_version="test", routes={},
        )

    def soup(self):
        return BeautifulSoup(self.html, "html.parser")

    def assertUnsafe(self, soup):
        with self.assertRaises(AssertionError):
            exporter.validate_inert_forms_and_csp(soup, "regression test")

    def test_preserves_original_semantic_form_selectors(self):
        soup = self.soup()
        self.assertEqual(soup.form["id"], "product_form")
        self.assertEqual(soup.form["class"], ["module", "aligned"])
        self.assertEqual(soup.form["data-sample-form"], "inert")
        self.assertEqual(len(soup.select("form .module")), 0)
        self.assertIsNotNone(soup.select_one("form#product_form input#id_name"))
        self.assertEqual(exporter.validate_inert_forms_and_csp(soup), {
            "inert_forms": 1, "functional_forms": 0, "inert_controls": 6,
        })
        self.assertNotIn("SECRET", self.html)
        self.assertIsNone(soup.find("input", attrs={"type": "hidden"}))
        self.assertIsNone(soup.find("input", attrs={"type": "password"}))
        self.assertIsNotNone(soup.find("input", attrs={"type": "submit", "disabled": True}))

    def test_rejects_all_submission_and_association_attributes(self):
        for tag_name in ("form", "input", "button", "select", "textarea"):
            for attribute in exporter.SUBMISSION_ATTRS:
                for value in ("", "product_form", "https://example.invalid"):
                    with self.subTest(tag=tag_name, attribute=attribute, value=value):
                        soup = self.soup()
                        soup.find(tag_name)[attribute] = value
                        self.assertUnsafe(soup)

    def test_rejects_every_enabled_control_inside_or_outside_form(self):
        for tag_name in ("input", "select", "textarea", "button"):
            for outside in (False, True):
                with self.subTest(tag=tag_name, outside=outside):
                    soup = self.soup()
                    control = soup.find(tag_name)
                    del control["disabled"]
                    if outside:
                        soup.body.append(control.extract())
                    self.assertUnsafe(soup)

    def test_rejects_sensitive_control_types(self):
        for kind in ("hidden", "password", "file", "PASSWORD"):
            with self.subTest(kind=kind):
                soup = self.soup()
                soup.input["type"] = kind
                self.assertUnsafe(soup)

    def test_rejects_csp_removal_change_duplication_or_late_placement(self):
        for mutation in ("removed", "weak-form", "weak-script", "weak-connect", "duplicate", "after-resources", "body"):
            with self.subTest(mutation=mutation):
                soup = self.soup()
                csp = soup.find("meta", attrs={"http-equiv": "Content-Security-Policy"})
                if mutation == "removed":
                    csp.decompose()
                elif mutation.startswith("weak-"):
                    directive = {"weak-form": "form-action", "weak-script": "script-src", "weak-connect": "connect-src"}[mutation]
                    csp["content"] = exporter.CSP.replace(directive + " 'none'", directive + " 'self'")
                elif mutation == "duplicate":
                    soup.head.append(soup.new_tag("meta", attrs={"http-equiv": "Content-Security-Policy", "content": exporter.CSP}))
                elif mutation == "body":
                    soup.body.insert(0, csp.extract())
                else:
                    soup.head.append(csp.extract())
                self.assertUnsafe(soup)

    def test_rejects_events_refresh_embeds_and_unmarked_forms(self):
        for mutation in ("onsubmit", "onload", "refresh", "script", "iframe", "object", "unmarked-form", "nested-form"):
            with self.subTest(mutation=mutation):
                soup = self.soup()
                if mutation in {"onsubmit", "onload"}:
                    soup.form[mutation] = "alert(1)"
                elif mutation == "refresh":
                    soup.head.append(soup.new_tag("meta", attrs={"http-equiv": "refresh", "content": "0;url=https://example.invalid"}))
                elif mutation == "unmarked-form":
                    del soup.form["data-sample-form"]
                elif mutation == "nested-form":
                    soup.form.append(soup.new_tag("form", attrs={"data-sample-form": "inert"}))
                else:
                    soup.body.append(soup.new_tag(mutation))
                self.assertUnsafe(soup)

    def test_built_in_sanitizer_adversarial_probes(self):
        exporter.sanitizer_self_test()

    def test_keeps_hidden_presentation_without_retaining_hidden_inputs(self):
        raw = '<html><head><title>Navigation</title></head><body><button id="nova-mobile-nav-toggle" hidden type="button">Navigation</button><input type="hidden" name="csrfmiddlewaretoken" value="SECRET"></body></html>'
        safe = exporter.sanitize_html(raw, mode="dark", page="changelist", django_version="test", routes={})
        soup = BeautifulSoup(safe, "html.parser")
        button = soup.select_one('#nova-mobile-nav-toggle')
        self.assertTrue(button.has_attr('hidden'))
        self.assertTrue(button.has_attr('disabled'))
        self.assertNotIn('SECRET', safe)
        self.assertIsNone(soup.find('input'))
        self.assertEqual(exporter.validate_inert_forms_and_csp(soup)['functional_forms'], 0)

    def test_switch_snapshot_preserves_boolean_state_without_submission(self):
        raw = '<html><head><title>Switch</title></head><body><form action="/admin/catalog/product/" method="post"><input type="checkbox" class="nova-switch" name="form-0-featured" checked aria-label="精选推荐（保存后生效）"><input type="checkbox" class="nova-switch" name="form-1-featured" aria-label="精选推荐（保存后生效）"><span class="nova-status nova-status--active">已上架</span></form></body></html>'
        safe = exporter.sanitize_html(raw, mode="light", page="changelist", django_version="test", routes={})
        soup = BeautifulSoup(safe, "html.parser")
        switches = soup.select("input.nova-switch")
        self.assertEqual(len(switches), 2)
        self.assertTrue(switches[0].has_attr("checked"))
        self.assertFalse(switches[1].has_attr("checked"))
        for switch in switches:
            self.assertEqual(switch["type"], "checkbox")
            self.assertTrue(switch.has_attr("disabled"))
            self.assertFalse(switch.has_attr("name"))
            self.assertTrue(switch["aria-label"])
        self.assertEqual(soup.select_one(".nova-status").get_text(), "已上架")
        self.assertEqual(exporter.validate_inert_forms_and_csp(soup)["functional_forms"], 0)

    def test_generated_boolean_snapshots_have_both_values_and_text_status(self):
        if EXPORT_DIR is None:
            self.skipTest("Pass --export-dir to verify a generated export too")
        for mode in exporter.MODES:
            with self.subTest(mode=mode):
                soup = BeautifulSoup((EXPORT_DIR / mode / "changelist.html").read_text(), "html.parser")
                switches = soup.select("input.nova-switch")
                self.assertEqual(len(switches), 4)
                self.assertEqual(sum(switch.has_attr("checked") for switch in switches), 2)
                self.assertEqual({badge.get_text() for badge in soup.select(".nova-status")}, {"已上架", "草稿", "已归档"})
                self.assertFalse(soup.select('input.nova-switch:not([disabled])'))
                self.assertFalse(soup.select('input.nova-switch[name]'))
                self.assertIn("本页面不能修改或保存", soup.select_one(".nova-list-edit-help").get_text())


    def test_image_snapshot_retains_alt_geometry_and_lazy_loading(self):
        raw = '<html><head><title>Images</title></head><body><span class="nova-media-thumb nova-media-thumb--avatar"><span class="nova-media-slice"><img src="/static/catalog/demo-media/avatars-sheet.webp" alt="Fictional adult &amp; demo" width="132" height="88" loading="lazy" decoding="async"></span></span></body></html>'
        safe = exporter.sanitize_html(raw, mode="native", page="members", django_version="test", routes={})
        image = BeautifulSoup(safe, "html.parser").img
        self.assertEqual(image["src"], "../static/catalog/demo-media/avatars-sheet.webp")
        self.assertEqual(image["alt"], "Fictional adult & demo")
        self.assertEqual((image["width"], image["height"]), ("132", "88"))
        self.assertEqual(image["loading"], "lazy")
        self.assertEqual(image["decoding"], "async")

    def test_image_sources_cannot_introduce_requests_or_error_handlers(self):
        for source in ("https://evil.invalid/x.webp", "//evil.invalid/x.webp", "data:image/svg+xml,evil", "/static/../secret.webp", "/static/catalog/a.webp?token=secret"):
            with self.subTest(source=source):
                raw = f'<html><head><title>Unsafe</title></head><body><img src="{source}" alt="safe" onerror="fetch(1)" srcset="https://evil.invalid/x 2x"></body></html>'
                safe = exporter.sanitize_html(raw, mode="dark", page="members", django_version="test", routes={})
                image = BeautifulSoup(safe, "html.parser").img
                self.assertFalse(image.has_attr("src"))
                self.assertFalse(image.has_attr("srcset"))
                self.assertFalse(image.has_attr("onerror"))

    def test_generated_media_lists_have_three_shapes_and_missing_examples(self):
        if EXPORT_DIR is None:
            self.skipTest("Pass --export-dir to verify a generated export too")
        for mode in exporter.MODES:
            for page, kind, count in (("changelist", "product", 4), ("members", "avatar", 6), ("news", "cover", 4)):
                with self.subTest(mode=mode, page=page):
                    soup = BeautifulSoup((EXPORT_DIR / mode / f"{page}.html").read_text(), "html.parser")
                    self.assertEqual(len(soup.select(f".nova-media-thumb--{kind}")), count)
                    self.assertEqual(len(soup.select(".nova-media-thumb--empty")), 1)
                    for image in soup.select(".nova-media-slice img"):
                        self.assertTrue(image["alt"])
                        self.assertEqual(image["loading"], "lazy")
                        self.assertTrue(image["src"].startswith("../static/catalog/demo-media/"))
                    self.assertFalse(soup.select(".nova-media-link[href*='/admin/']"))
                    self.assertEqual(exporter.validate_inert_forms_and_csp(soup)["functional_forms"], 0)

    def test_export_includes_only_allowlisted_optimized_media_sheets(self):
        if EXPORT_DIR is None:
            self.skipTest("Pass --export-dir to verify a generated export too")
        directory = EXPORT_DIR / "static" / "catalog" / "demo-media"
        self.assertEqual({path.name for path in directory.iterdir()}, {"avatars-sheet.webp", "products-sheet.webp", "covers-sheet.webp"})
        self.assertLess(sum(path.stat().st_size for path in directory.iterdir()), 800_000)
        self.assertFalse(list(EXPORT_DIR.rglob("*-sheet.png")))

    def test_palette_inventory_is_explicit_and_preserves_default_contract(self):
        base = exporter.sample_profiles()
        expanded = exporter.sample_profiles(True)
        self.assertEqual(sum(len(pages) for _, _, _, pages in base) + 1, 57)
        self.assertEqual(expanded[:len(base)], base)
        representatives = expanded[len(base):]
        self.assertEqual(sum(len(pages) for _, _, _, pages in representatives), 72)
        self.assertEqual(sum(len(pages) for _, _, _, pages in expanded) + 1, 129)
        self.assertEqual({palette for _, _, palette, _ in representatives}, set(exporter.PALETTES))
        for directory, mode, palette, pages in representatives:
            self.assertEqual(directory, f"palette-{palette}-{mode}")
            self.assertIn(mode, {"light", "dark"})
            self.assertEqual(pages, ("index", "changelist", "login"))

    def test_palette_navigation_only_targets_supported_representatives(self):
        raw = '<html><head><title>Palette</title></head><body class="nova-admin nova-mode-dark nova-palette-teal"><form action="/admin/_preferences/" method="post"><select name="palette"><option>teal</option></select><button>Save</button></form></body></html>'
        safe = exporter.sanitize_html(raw, mode="dark", page="login", palette="teal", django_version="test", routes={})
        soup = BeautifulSoup(safe, "html.parser")
        self.assertIn("nova-palette-teal", soup.body["class"])
        self.assertEqual(soup.html["data-theme"], "dark")
        self.assertEqual({a["href"] for a in soup.select('.sample-banner a')}, {
            "../index.html", "index.html", "changelist.html", "login.html",
            "../palette-teal-light/login.html", "../palette-teal-dark/login.html",
        })
        self.assertEqual(exporter.validate_inert_forms_and_csp(soup)["functional_forms"], 0)
        self.assertNotIn("/admin/", safe)
        for palette, mode, page in (("unknown", "dark", "login"), ("teal", "native", "login"), ("teal", "auto", "index"), ("teal", "dark", "changeform")):
            with self.subTest(palette=palette, mode=mode, page=page), self.assertRaises(ValueError):
                exporter.sanitize_html(raw, mode=mode, page=page, palette=palette, django_version="test", routes={})

    def test_generated_palette_representatives_match_real_rendered_profiles(self):
        if EXPORT_DIR is None:
            self.skipTest("Pass --export-dir to verify generated profiles")
        manifest = json.loads((EXPORT_DIR / "manifest.json").read_text())
        if not manifest.get("palette_representatives"):
            self.assertFalse(list(EXPORT_DIR.glob("palette-*")))
            return
        records = {record["file"]: record for record in manifest["rendered_pages"]}
        for directory, mode, palette, pages in exporter.sample_profiles(True):
            if palette == "default":
                continue
            for page in pages:
                file = f"{directory}/{page}.html"
                with self.subTest(file=file):
                    soup = BeautifulSoup((EXPORT_DIR / file).read_text(), "html.parser")
                    self.assertIn(f"nova-palette-{palette}", soup.body["class"])
                    self.assertIn(f"nova-mode-{mode}", soup.body["class"])
                    self.assertEqual(soup.html["data-theme"], mode)
                    self.assertTrue(soup.select('link[href$="nova_admin/presets.css"]'))
                    self.assertEqual(records[file]["palette"], palette)
                    self.assertEqual(records[file]["mode"], mode)
                    self.assertEqual(records[file]["render_method"], "GET")
                    if page == "login" and manifest["source"].get("optional_captcha"):
                        image = soup.select_one(".nova-captcha-image")
                        self.assertIsNotNone(image)
                        self.assertEqual(image["src"], f"../static/nova_admin/captcha-login-{directory}.png")
                        self.assertTrue((EXPORT_DIR / "static" / "nova_admin" / f"captcha-login-{directory}.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))
                    self.assertEqual(exporter.validate_inert_forms_and_csp(soup)["functional_forms"], 0)

    def test_generated_extension_profile_is_disclosed_and_preserved(self):
        if EXPORT_DIR is None:
            self.skipTest("Pass --export-dir to verify generated profiles")
        manifest = json.loads((EXPORT_DIR / "manifest.json").read_text())
        if not manifest["source"].get("optional_extensions"):
            return
        for directory, mode, palette, pages in exporter.sample_profiles(manifest.get("palette_representatives", False)):
            for page in pages:
                soup = BeautifulSoup((EXPORT_DIR / directory / f"{page}.html").read_text(), "html.parser")
                if mode == "native":
                    self.assertIsNone(soup.select_one(".nova-brand-footer"))
                else:
                    self.assertIsNotNone(soup.select_one(".nova-brand-footer"))
                    self.assertTrue(soup.select('img[src$="catalog/brand/logo.svg"]'))

    def test_generated_export_contract_and_manifest(self):
        if EXPORT_DIR is None:
            self.skipTest("Pass --export-dir to verify a generated export too")
        result = exporter.validate_export(EXPORT_DIR)
        exporter.verify_manifest(EXPORT_DIR)
        manifest = json.loads((EXPORT_DIR / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["format_version"], 2)
        self.assertEqual(result["functional_forms"], 0)
        self.assertEqual(result["scripts"], 0)
        self.assertEqual(result["live_endpoints"], 0)
        self.assertEqual(result["external_requests"], 0)
        self.assertGreater(result["inert_forms"], 0)
        self.assertEqual(result, manifest["safety_validation"])
        self.assertEqual(sum(page["semantic_forms_preserved"] for page in manifest["rendered_pages"]), result["inert_forms"])

    def test_optional_captcha_snapshot_has_no_live_key_or_submission(self):
        if EXPORT_DIR is None:
            self.skipTest("Pass --export-dir to verify generated profiles")
        manifest = json.loads((EXPORT_DIR / "manifest.json").read_text())
        enabled = manifest["source"].get("optional_captcha")
        for mode in exporter.MODES:
            raw = (EXPORT_DIR / mode / "login.html").read_text()
            soup = BeautifulSoup(raw, "html.parser")
            self.assertNotIn('/admin/_captcha/', raw)
            self.assertFalse(soup.select('input[type="hidden"]'))
            self.assertEqual(exporter.validate_inert_forms_and_csp(soup)['functional_forms'], 0)
            image = soup.select_one('.nova-captcha-image')
            if enabled:
                self.assertIsNotNone(image)
                self.assertEqual(image['src'], '../static/nova_admin/captcha-login-' + mode + '.png')
                data = (EXPORT_DIR / 'static/nova_admin' / ('captcha-login-' + mode + '.png')).read_bytes()
                self.assertTrue(data.startswith(b'\x89PNG\r\n\x1a\n'))
                self.assertIn('静态验证码图片', image['alt'])
            else:
                self.assertIsNone(image)

    def test_login_decoration_is_scoped_and_native_recovery_is_unchanged(self):
        if EXPORT_DIR is None:
            self.skipTest("Pass --export-dir to verify generated profiles")
        for mode in exporter.MODES:
            soup = BeautifulSoup((EXPORT_DIR / mode / 'login.html').read_text(), 'html.parser')
            if mode == 'native':
                self.assertIsNone(soup.select_one('.nova-login-layout'))
                self.assertFalse(soup.select('link[href$="nova_admin/login.css"]'))
            else:
                self.assertEqual(soup.select_one('#nova-login-title').get_text(), '登录')
                self.assertTrue(soup.select('link[href$="nova_admin/login.css"]'))

    def test_project_profiles_keep_ordered_css_and_native_recovery(self):
        if EXPORT_DIR is None:
            self.skipTest("Pass --export-dir to verify generated profiles")
        for mode in exporter.MODES:
            soup = BeautifulSoup((EXPORT_DIR / mode / "changeform.html").read_text(), "html.parser")
            styles = [link["href"] for link in soup.select('link[rel="stylesheet"]')]
            enterprise = '../static/catalog/enterprise.css'
            compact = '../static/catalog/enterprise-compact.css'
            if mode == 'native':
                self.assertNotIn(enterprise, styles)
                self.assertNotIn(compact, styles)
            else:
                self.assertLess(styles.index('../static/nova_admin/theme.css'), styles.index(enterprise))
                self.assertEqual(compact in styles, mode.startswith('compact-'))
                if compact in styles:
                    self.assertLess(styles.index(enterprise), styles.index(compact))
                self.assertIn('nova-mode-' + exporter.theme_mode(mode), soup.body.get('class', []))
                self.assertEqual(soup.html['data-theme'], exporter.theme_mode(mode))

    def test_project_chinese_labels_and_dictionary_survive_export(self):
        if EXPORT_DIR is None:
            self.skipTest("Pass --export-dir to verify generated profiles")
        soup = BeautifulSoup((EXPORT_DIR / 'light' / 'changeform.html').read_text(), 'html.parser')
        self.assertTrue(soup.select_one('label[for="id_name"]').get_text(strip=True).endswith('：'))
        self.assertIn('请选择', soup.get_text())
        listing = BeautifulSoup((EXPORT_DIR / 'light' / 'changelist.html').read_text(), 'html.parser')
        self.assertEqual(listing.select_one('#content h1').get_text(strip=True), '商品列表')
        self.assertIn('显示数量', listing.get_text())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-dir", type=Path)
    known, remaining = parser.parse_known_args()
    EXPORT_DIR = known.export_dir.resolve() if known.export_dir else None
    unittest.main(argv=[sys.argv[0], *remaining], verbosity=2)
