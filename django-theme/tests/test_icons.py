"""Public icon APIs, catalog safety, compatibility and zero-query navigation."""
import json
from importlib.resources import files
from xml.etree import ElementTree

from django.template import Context, Template
from django.template.loader import render_to_string
from django.test import SimpleTestCase, override_settings
from django.utils.safestring import mark_safe

from nova_admin.checks import navigation_settings_check
from nova_admin.icons import ICON_CATALOG, ICON_CATEGORIES, ICON_NAMES, ICON_PATHS, get_icon_path, render_icon
from nova_admin.navigation import extend_navigation


class IconCatalogTests(SimpleTestCase):
    def test_catalog_is_packaged_unique_readonly_and_has_business_coverage(self):
        source = json.loads(files("nova_admin").joinpath("icons.json").read_text(encoding="utf-8"))
        self.assertEqual(len(ICON_NAMES), len(source["icons"]))
        self.assertEqual(len(set(ICON_NAMES)), len(ICON_NAMES))
        self.assertGreaterEqual(len(ICON_NAMES), 90)
        self.assertEqual({entry["category"] for entry in ICON_CATALOG}, set(ICON_CATEGORIES))
        for name in ("users", "receipt", "warehouse", "workflow", "database", "image", "upload", "alert-triangle"):
            self.assertIn(name, ICON_NAMES)
        with self.assertRaises(TypeError):
            ICON_PATHS["unsafe"] = "<svg>"
        with self.assertRaises(TypeError):
            ICON_CATALOG[0]["path"] = "<svg>"

    def test_original_navigation_catalog_names_remain_available(self):
        from nova_admin.navigation import ICON_PATHS as compatibility
        self.assertIs(compatibility, ICON_PATHS)
        for name in ("box", "users", "tag", "folder", "file", "chart", "home", "star", "settings"):
            self.assertIn(name, ICON_PATHS)

    def test_every_icon_contains_path_data_only_and_renders_decoratively(self):
        for entry in ICON_CATALOG:
            with self.subTest(name=entry["name"]):
                self.assertRegex(entry["name"], r"\A[a-z][a-z0-9-]*\Z")
                self.assertRegex(entry["path"], r"\A[Mm][MmLlHhVvCcSsQqTtAaZz0-9., +\-]*\Z")
                svg = ElementTree.fromstring(str(render_icon(entry["name"])))
                self.assertEqual(svg.tag, "svg")
                self.assertEqual(svg.get("aria-hidden"), "true")
                self.assertEqual(svg.get("focusable"), "false")
                self.assertEqual(svg.get("viewBox"), "0 0 24 24")
                self.assertEqual([(child.tag, child.attrib) for child in svg], [("path", {"d": entry["path"]})])

    def test_unknown_and_malformed_names_use_only_a_known_fallback(self):
        for value in ("missing", "BOX", "", "<svg onload='x'>", "__proto__", None, [], {}, True):
            with self.subTest(value=value):
                self.assertIsNone(get_icon_path(value))
                self.assertEqual(render_icon(value), render_icon("grid"))
                self.assertEqual(render_icon(value, fallback=None), "")
                self.assertIsNone(get_icon_path(value, fallback="<svg>"))
        self.assertEqual(get_icon_path("box", fallback=[]), ICON_PATHS["box"])

    def test_template_tag_accepts_named_options_and_accessible_plain_text(self):
        result = Template('{% load nova_tags %}{% nova_icon "receipt" css_class="custom-icon small" label=label size=24 %}').render(
            Context({"label": mark_safe('<img onerror="bad"> & "订单"')}))
        svg = ElementTree.fromstring(result)
        self.assertEqual(svg.get("class"), "nova-icon custom-icon small")
        self.assertEqual(svg.get("width"), "24")
        self.assertEqual(svg.get("role"), "img")
        self.assertEqual(svg.get("aria-label"), '<img onerror="bad"> & "订单"')
        self.assertIsNone(svg.get("aria-hidden"))
        self.assertNotIn('<img', result)
        self.assertEqual(len(svg), 1)

    def test_class_and_size_input_cannot_create_attributes_or_invalid_geometry(self):
        for value in ('" onload="bad', '"><script>bad</script>', mark_safe('" onload="bad'), [], None, "a" * 257):
            with self.subTest(value=value):
                svg = ElementTree.fromstring(str(render_icon("box", css_class=value, size=value)))
                self.assertEqual(svg.get("width"), "16")
                self.assertEqual(svg.get("height"), "16")
                self.assertNotIn("onload", svg.attrib)
                self.assertEqual(len(svg), 1)
        for value in (True, 0, 11, 65, "24", float("inf")):
            self.assertEqual(ElementTree.fromstring(str(render_icon("box", size=value))).get("width"), "16")

    def test_navigation_include_rejects_arbitrary_paths_even_marked_safe(self):
        for value in ('M1 1L2 2', mark_safe('"/><script>bad</script><path d="'), '<svg onload="bad">', [], None):
            markup = render_to_string("nova_admin/navigation_icon.html", {"icon_path": value})
            self.assertEqual(markup.strip(), "")
        markup = render_to_string("nova_admin/navigation_icon.html", {"icon_path": ICON_PATHS["receipt"]})
        self.assertEqual(ElementTree.fromstring(markup.strip()).get("class"), "nova-nav-icon")

    def test_chinese_guide_covers_every_configurable_name(self):
        # The guide is part of the sdist, while an installed wheel only needs JSON.
        from pathlib import Path
        guide = Path(__file__).resolve().parents[1] / "ICON_GUIDE.md"
        if not guide.exists():
            self.skipTest("Source guide is not present in a wheel-only test environment")
        text = guide.read_text(encoding="utf-8")
        for name in ICON_NAMES:
            self.assertIn(f"`{name}`", text)


@override_settings(NOVA_ADMIN_NAV_ICON_PROVIDER=None, NOVA_ADMIN_NAV_BADGE_PROVIDER=None,
                   NOVA_ADMIN_NAV_COMMON_MODELS=(), NOVA_ADMIN_NAV_FAVORITES=False)
class NavigationIconConfigurationTests(SimpleTestCase):
    def groups(self):
        return [{"label": "Business", "apps": [{"app_label": "sales", "name": "Sales", "models": [
            {"object_name": "Order", "name": "Orders", "admin_url": "/admin/sales/order/"},
        ]}]}]

    @override_settings(NOVA_ADMIN_NAV_ICONS={"sales": "store", "sales.order": "receipt", "secret.model": "lock"})
    def test_app_and_model_configuration_decorates_only_existing_links(self):
        before = self.groups()
        result = extend_navigation(before)
        app = result["groups"][0]["apps"][0]
        self.assertEqual(app["nova_icon_path"], ICON_PATHS["store"])
        self.assertEqual(app["models"][0]["nova_icon_path"], ICON_PATHS["receipt"])
        self.assertEqual(app["models"][0]["admin_url"], "/admin/sales/order/")
        self.assertNotIn("secret", str(result))
        self.assertNotIn("nova_icon_path", before[0]["apps"][0])

    @override_settings(NOVA_ADMIN_NAV_ICONS={"sales.order": "receipt"},
                       NOVA_ADMIN_NAV_ICON_PROVIDER=lambda request, apps: {"sales.order": "check-circle"})
    def test_provider_can_select_the_expanded_catalog_without_queries(self):
        self.assertEqual(extend_navigation(self.groups())["groups"][0]["apps"][0]["models"][0]["nova_icon_path"],
                         ICON_PATHS["check-circle"])

    def test_unknown_or_empty_navigation_icons_remain_omitted_for_compatibility(self):
        for value in ("missing", "", None, [], '<svg onload="bad">'):
            with self.subTest(value=value), override_settings(NOVA_ADMIN_NAV_ICONS={"sales.order": value}):
                self.assertIsNone(extend_navigation(self.groups())["groups"][0]["apps"][0]["models"][0]["nova_icon_path"])

    def test_system_check_accepts_all_names_and_warns_on_bad_keys_and_names(self):
        for name in ICON_NAMES:
            with override_settings(NOVA_ADMIN_NAV_ICONS={"sales.order": name}):
                self.assertEqual(navigation_settings_check(None), [])
        for key, value in (("sales.Order", "receipt"), ("sales.order.more", "receipt"), ("sales/order", "receipt"),
                           ("sales..order", "receipt"), ("", "receipt"), ("sales.order", "missing")):
            with self.subTest(key=key, value=value), override_settings(NOVA_ADMIN_NAV_ICONS={key: value}):
                self.assertTrue(any(item.id == "nova_admin.W003" for item in navigation_settings_check(None)))
