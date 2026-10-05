"""Small round-one review fixes; do not change native business semantics."""
from pathlib import Path
import re
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from catalog.models import Product, ProductVariant, MemberProfile, NewsItem


class ReviewDetailTests(SimpleTestCase):
    def test_variant_has_a_readable_name(self):
        self.assertEqual(str(ProductVariant(name="颜色", value="青色")), "颜色: 青色")

    def test_search_help_is_explicit_per_demo_model(self):
        for model, text in ((Product,"SKU"),(MemberProfile,"会员编号"),(NewsItem,"新闻标题")):
            self.assertIn(text, admin.site._registry[model].search_help_text)

    def test_numeric_and_font_styles_are_scoped(self):
        css = Path(finders.find("nova_admin/theme.css")).read_text()
        self.assertIn("body.nova-admin #result_list :is(.field-price, .field-stock, .field-sku, .nova-number)", css)
        self.assertIn("font-variant-numeric: tabular-nums", css)
        for font in ("Hiragino Sans GB", "Noto Sans SC", "HarmonyOS Sans SC"):
            self.assertIn(font, css)

    def test_light_muted_text_meets_aa_for_declared_surfaces(self):
        css = Path(finders.find("nova_admin/theme.css")).read_text()
        light = css.split("body.nova-admin.nova-mode-light {", 1)[1].split("}", 1)[0]
        colors = dict(re.findall(r"(--[a-z-]+): (#[0-9a-f]{6});", light))
        def luminance(value):
            rgb = [int(value[i:i+2], 16) / 255 for i in (1, 3, 5)]
            rgb = [x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4 for x in rgb]
            return sum(x * weight for x, weight in zip(rgb, (.2126, .7152, .0722)))
        text = luminance(colors["--body-quiet-color"])
        for name in ("--body-bg", "--nova-panel", "--darkened-bg", "--selected-bg", "--selected-row"):
            with self.subTest(surface=name):
                high, low = sorted((text, luminance(colors[name])), reverse=True)
                self.assertGreaterEqual((high + .05) / (low + .05), 4.5)


class ReviewRenderedTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser(username="review-demo", password=None)
        cls.product = Product.objects.create(name="Keyboard", sku="REVIEW-1", price="12.50")
        ProductVariant.objects.create(product=cls.product, name="<b>Color</b>", value="<script>unsafe</script>")

    def setUp(self):
        self.client.force_login(self.user)

    def test_inline_description_stays_escaped(self):
        html = self.client.get(reverse("admin:catalog_product_change", args=[self.product.pk])).content.decode()
        self.assertIn("&lt;b&gt;Color&lt;/b&gt;: &lt;script&gt;unsafe&lt;/script&gt;", html)
        self.assertNotIn("ProductVariant object", html)

    def test_model_search_help_renders_with_original_get_form(self):
        html = self.client.get(reverse("admin:catalog_product_changelist"), {"q":"Keyboard"}).content.decode()
        self.assertIn("搜索商品名称或 SKU", html)
        self.assertIn('name="q" value="Keyboard"', html)
        self.assertIn('id="changelist-search" method="get"', html)
