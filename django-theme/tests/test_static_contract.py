"""Targeted CSS contracts for defects found in rendered-sample browser review.

These checks prevent losing the selected safeguards, not browser layout QA.
"""
import re
from pathlib import Path

from django.contrib.staticfiles import finders
from django.test import SimpleTestCase


class StaticLayoutContractTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.css = Path(finders.find("nova_admin/theme.css")).read_text()

    def declarations(self, selector):
        pattern = re.escape(selector) + r"\s*\{([^}]+)\}"
        matches = re.findall(pattern, self.css)
        self.assertTrue(matches, f"Missing safeguard selector: {selector}")
        return matches[-1]

    def test_single_select_height_resets_without_affecting_listboxes_or_select2_source(self):
        rule = self.declarations("body.nova-admin select:not([multiple]):not([size]):not(.select2-hidden-accessible)")
        for declaration in ("box-sizing: border-box", "min-height: 40px", "height: auto", "line-height: 1.35"):
            self.assertIn(declaration, rule)

    def test_related_links_align_with_full_height_inputs(self):
        rule = self.declarations("body.nova-admin .related-widget-wrapper-link")
        for declaration in ("box-sizing: border-box", "height: 40px", "vertical-align: middle"):
            self.assertIn(declaration, rule)

    def test_wide_text_fields_are_scoped_to_main_form_fieldsets(self):
        rule = self.declarations("body.nova-admin.change-form #content-main > [id$='_form'] > div > fieldset.aligned .vTextField")
        self.assertIn("width: min(100%, 36rem)", rule)
        self.assertIn("max-width: 100%", rule)
        self.assertNotRegex(self.css, r"\.inline-group[^{}]*\.vTextField\s*\{[^}]*36rem")
        self.assertNotRegex(self.css, r"\.(?:vDateField|vTimeField)[^{}]*\{[^}]*36rem")

    def test_main_flex_and_fieldsets_can_shrink_without_document_clipping(self):
        rule = self.declarations("body.nova-admin .main > .content")
        self.assertIn("min-width: 0", rule)
        rule = self.declarations("body.nova-admin fieldset.module")
        self.assertIn("min-inline-size: 0", rule)
        self.assertIn("max-width: 100%", rule)
        self.assertNotRegex(self.css, r"body\.nova-admin\s*\{[^}]*overflow(?:-x)?:\s*hidden")

    def test_mobile_field_widths_follow_panel_not_viewport(self):
        rule = self.declarations("body.nova-admin .aligned .form-row > div")
        for declaration in ("width: 100%", "min-width: 0", "max-width: 100%", "box-sizing: border-box"):
            self.assertIn(declaration, rule)
        header = self.declarations("body.nova-admin #header")
        self.assertIn("flex-direction: column", header)
        self.assertIn("align-items: stretch", header)
        self.assertIn("flex-wrap: nowrap", header)
        self.assertIn("height: auto", header)
        self.assertIn("flex-shrink: 0", header)

    def test_inline_table_scroll_is_local_and_header_switcher_can_wrap(self):
        rule = self.declarations("body.nova-admin .inline-related.tabular .wrapper")
        self.assertIn("overflow-x: auto", rule)
        self.assertIn("max-width: 100%", rule)
        switcher = self.declarations("body.nova-admin .nova-theme-switcher")
        self.assertIn("flex-wrap: wrap", switcher)
        self.assertIn("width: 100%", switcher)

    def test_mobile_wide_lists_scroll_locally_without_widening_small_lists(self):
        selector = "body.nova-admin #result_list:has(> thead > tr > th:nth-child(5))"
        rule = self.declarations(selector)
        self.assertIn("min-width: 44rem", rule)
        self.assertNotRegex(self.css, r"#result_list\s*\{[^}]*min-width:")
        viewport = self.declarations("body.nova-admin #changelist-form .results")
        self.assertIn("overflow-x: auto", viewport)
        self.assertIn("max-width: 100%", viewport)
        sku = self.declarations(selector + " .field-sku")
        self.assertIn("white-space: nowrap", sku)
        self.assertNotIn("text-overflow", rule)
        mobile = self.css.rsplit("@media (max-width: 767px)", 1)[-1]
        self.assertIn(selector, mobile)

    def test_eight_column_mobile_lists_grow_inside_the_results_viewport_only(self):
        baseline = "body.nova-admin #result_list:has(> thead > tr > th:nth-child(5))"
        wide = "body.nova-admin #result_list:has(> thead > tr > th:nth-child(8))"
        self.assertIn("min-width: 44rem", self.declarations(baseline))
        self.assertIn("min-width: 54rem", self.declarations(wide))
        self.assertIn("min-width: 140px", self.declarations(wide + " .field-name"))
        self.assertGreater(self.css.index(wide), self.css.index(baseline))
        mobile = self.css.rsplit("@media (max-width: 767px)", 1)[-1]
        self.assertIn(wide, mobile)
        self.assertIn("overflow-x: auto", self.declarations("body.nova-admin #changelist-form .results"))
        self.assertNotRegex(self.css, r"(?:body\.nova-admin|#content)\s*\{[^}]*min-width:\s*(?:54rem|864px)")

    def test_content_canvas_is_fluid_without_fixed_desktop_width_cap(self):
        rules = re.findall(r"body\.nova-admin #content\s*\{([^}]+)\}", self.css)
        self.assertTrue(any("max-width: none" in rule for rule in rules))
        self.assertFalse(any(re.search(r"max-width:\s*\d+(?:px|rem)", rule) for rule in rules))
        self.assertIn("min-width: 0", self.declarations("body.nova-admin .main > .content"))
        # Reading-width limits belong to form fields, not the list/main canvas.
        self.assertIn("width: min(100%, 36rem)", self.declarations("body.nova-admin.change-form #content-main > [id$='_form'] > div > fieldset.aligned .vTextField"))

    def test_mobile_optional_navigation_is_visible_without_javascript(self):
        selector = "body.nova-admin .main > #nav-sidebar.nova-navigation"
        rule = self.declarations(selector)
        for declaration in ("display: block", "visibility: visible", "position: static", "width: 100%", "max-height: none", "margin: 0", "inset: auto"):
            self.assertIn(declaration, rule)
        self.assertIn("display: none", self.declarations(selector + "[hidden]"))
        self.assertIn("flex-direction: column", self.declarations("body.nova-admin .main:has(> #nav-sidebar.nova-navigation)"))

    def test_mobile_navigation_button_is_progressive_and_has_a_touch_target(self):
        selector = "body.nova-admin .nova-mobile-nav-toggle"
        self.assertIn("display: none", self.declarations(selector))
        enabled = self.declarations(selector + ":not([hidden])")
        self.assertIn("min-height: 44px", enabled)
        self.assertIn("width: 100%", enabled)
        self.assertIn("text-align: start", enabled)

    def test_unenhanced_multiselect_has_reading_width_only_in_main_fieldsets(self):
        selector = "body.nova-admin.change-form #content-main > [id$='_form'] > div > fieldset.aligned select[multiple]:not(.select2-hidden-accessible):not(.filtered):not(.selector select)"
        rule = self.declarations(selector)
        for declaration in ("width: min(24rem, 100%)", "min-width: 0", "max-width: 100%", "box-sizing: border-box"):
            self.assertIn(declaration, rule)
        self.assertNotRegex(self.css, r"body\.nova-admin select\[multiple\]\s*\{[^}]*24rem")
        self.assertNotIn("height:", rule)
        wrapper = "body.nova-admin.change-form #content-main > [id$='_form'] > div > fieldset.aligned .related-widget-wrapper:has(> select[multiple]:not(.select2-hidden-accessible):not(.filtered):not(.selector select))"
        wrapper_rule = self.declarations(wrapper)
        for declaration in ("width: min(24rem, 100%)", "min-width: 0", "max-width: 100%", "flex: 0 1 auto", "flex-wrap: nowrap", "gap: 8px"):
            self.assertIn(declaration, wrapper_rule)
        self.assertNotIn("flex: 0 1 24rem", wrapper_rule)
        child = "body.nova-admin.change-form #content-main > [id$='_form'] > div > fieldset.aligned .related-widget-wrapper > select[multiple]:not(.select2-hidden-accessible):not(.filtered):not(.selector select)"
        for declaration in ("flex: 1 1 0", "width: 0", "min-width: 0"):
            self.assertIn(declaration, self.declarations(child))
        self.assertIn("flex: 0 0 34px", self.declarations(wrapper + " > .related-widget-wrapper-link"))


from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from catalog.models import Product
from tests.test_navigation_groups import NavigationElements


class NativeFieldStructureTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser(username="layout-test", password=None)
        cls.product = Product.objects.create(name="Layout fixture", sku="LAYOUT-001", price="10.00")

    def test_real_form_scope_excludes_inline_and_multiselect_widgets(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("admin:catalog_product_change", args=[self.product.pk]))
        self.assertEqual(response.status_code, 200)
        elements = NavigationElements(response.content.decode()).elements
        controls = {item["attrs"].get("name"): item for item in elements if item["tag"] in {"input", "select"}}

        def in_main_fieldset(control):
            ancestors = control["ancestors"]
            form_index = next(index for index, item in enumerate(ancestors) if item["attrs"].get("id") == "product_form")
            children = ancestors[form_index + 1:]
            return len(children) > 1 and children[0]["tag"] == "div" and children[1]["tag"] == "fieldset" and NavigationElements.has_class(children[1], "aligned")

        for name in ("name", "sku"):
            self.assertTrue(in_main_fieldset(controls[name]))
            self.assertTrue(NavigationElements.has_class(controls[name], "vTextField"))
        self.assertFalse(in_main_fieldset(controls["variants-0-name"]))
        self.assertEqual(controls["category"]["tag"], "select")
        self.assertNotIn("multiple", controls["category"]["attrs"])
        self.assertIn("multiple", controls["tags"]["attrs"])


class NativeControlStyleContractTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.css = Path(finders.find("nova_admin/theme.css")).read_text()

    declarations = StaticLayoutContractTests.declarations

    def test_number_controls_keep_native_stepping_and_single_focus_ring(self):
        rule = self.declarations('body.nova-admin input[type=number]')
        self.assertIn('appearance: auto', rule)
        self.assertIn('font-variant-numeric: tabular-nums', rule)
        focus = self.declarations('body.nova-admin input[type=number]:focus-visible')
        self.assertIn('outline: 2px solid', focus)
        self.assertIn('box-shadow: none', focus)
        self.assertNotIn('::-webkit-inner-spin-button', self.css)
        self.assertNotIn('::-webkit-outer-spin-button', self.css)

    def test_select_arrow_excludes_multi_and_hidden_autocomplete(self):
        selector = 'body.nova-admin select:not([multiple]):not([size]):not(.select2-hidden-accessible)'
        matches = re.findall(re.escape(selector) + r'\s*\{([^}]+)\}', self.css)
        regular = next(rule for rule in matches if 'background-position:' in rule)
        for declaration in ('appearance: none', 'padding: 9px 38px 9px 12px', 'linear-gradient', 'background-repeat: no-repeat'):
            self.assertIn(declaration, regular)
        self.assertIn('appearance: auto', self.css.split('@media (forced-colors: active)')[-1])

    def test_select2_dropdown_search_disabled_and_errors_are_scoped(self):
        for selector, declaration in (
            ('body.nova-admin .select2-container--admin-autocomplete .select2-search--dropdown .select2-search__field', 'min-height: 36px'),
            ('body.nova-admin .select2-container--admin-autocomplete .select2-results > .select2-results__options', 'max-height: 240px'),
            ('body.nova-admin .select2-container--admin-autocomplete.select2-container--disabled .select2-selection', 'cursor: not-allowed'),
            ('body.nova-admin select[aria-invalid=true] + .select2-container--admin-autocomplete .select2-selection', 'border-color: var(--error-fg)'),
            ('body.nova-admin .select2-container--admin-autocomplete .select2-search--inline .select2-search__field:focus-visible', 'outline: none'),
        ):
            self.assertIn(declaration, self.declarations(selector))
        self.assertIn('.select2-container--focus .select2-selection', self.css)
        self.assertIn('.select2-results__option[aria-disabled=true]', self.css)

    def test_switches_are_opt_in_and_forced_colors_keeps_native_checkbox(self):
        self.assertIn('body.nova-admin #result_list input[type=checkbox].nova-switch:checked', self.css)
        self.assertIn('body.nova-admin #result_list input[type=checkbox].nova-switch:disabled', self.css)
        matches = re.findall(r'body\.nova-admin #result_list input\[type=checkbox\]\.nova-switch\s*\{([^}]+)\}', self.css)
        self.assertIn('appearance: none', matches[0])
        self.assertIn('appearance: auto', matches[-1])
        self.assertNotRegex(self.css, r'input\[type=checkbox\]\s*\{[^}]*appearance:\s*none')

    def test_status_and_boolean_decorations_do_not_replace_real_text_or_images(self):
        self.assertIn('.nova-status--active', self.css)
        self.assertIn('img[src$="/icon-yes.svg"]', self.css)
        self.assertIn('img[src$="/icon-no.svg"]', self.css)
        self.assertIn('img[src$="/icon-unknown.svg"]', self.css)
        self.assertNotRegex(self.css, r'icon-(?:yes|no|unknown)\.svg[^{}]*\{[^}]*display:\s*none')
