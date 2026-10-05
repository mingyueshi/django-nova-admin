#!/usr/bin/env python3
"""Run standalone local-package helper checks in a disposable in-memory database.

Usage from the package root: python scripts/test_seed_demo.py
These tests are additional to the unchanged 150-test runtime integration suite.
"""
import io
import os
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "demo"), str(ROOT)]
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
import django
from django.conf import settings
settings.DATABASES["default"]["NAME"] = ":memory:"
django.setup()
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.test.utils import get_runner
from catalog.models import Category, MemberProfile, NewsItem, Product, ProductVariant, Tag

MODELS = (Category, Tag, Product, ProductVariant, MemberProfile, NewsItem, get_user_model())


def seed():
    output = io.StringIO()
    call_command("seed_demo", stdout=output)
    return output.getvalue()


def snapshot():
    data = [list(model.objects.order_by("pk").values()) for model in MODELS]
    data.append(list(Product.tags.through.objects.order_by("pk").values()))
    return data


@override_settings(DEBUG=True)
class SeedDemoTests(TestCase):
    def test_fresh_counts_images_relations_and_no_login_account(self):
        seed()
        self.assertEqual([model.objects.count() for model in MODELS], [1, 2, 7, 14, 7, 7, 0])
        self.assertEqual(set(Product.objects.values_list("image_key", flat=True)), {"", "0", "1", "2", "3", "4", "5"})
        self.assertEqual(set(MemberProfile.objects.values_list("avatar_key", flat=True)), {"", "0", "1", "2", "3", "4", "5"})
        self.assertEqual(set(NewsItem.objects.values_list("cover_key", flat=True)), {"", "0", "1", "2", "3", "4", "5"})
        self.assertEqual(Product.objects.get(sku="NOVA-DEMO-KEYBOARD").image_key, "0")
        self.assertEqual(Product.objects.get(sku="NOVA-DEMO-ORGANIZER").image_key, "1")
        self.assertEqual(Product.objects.get(sku="NOVA-DEMO-BACKPACK").image_key, "2")
        self.assertEqual(Product.objects.get(sku="NOVA-DEMO-MEMO").image_key, "3")
        self.assertEqual(Product.objects.get(sku="NOVA-DEMO-STAND").image_key, "4")
        self.assertEqual(Product.objects.get(sku="NOVA-DEMO-POUCH").image_key, "5")
        for product in Product.objects.all():
            self.assertIsNotNone(product.category_id)
            self.assertTrue(product.tags.exists())
            self.assertEqual(product.variants.count(), 2)

    def test_second_run_is_identical_including_timestamps_and_relationships(self):
        seed()
        before = snapshot()
        output = seed()
        self.assertEqual(snapshot(), before)
        self.assertIn("products=0", output)
        self.assertIn("news=0", output)

    def test_user_edits_and_removed_relationships_are_preserved(self):
        seed()
        product = Product.objects.get(sku="NOVA-DEMO-KEYBOARD")
        product.name = "User edited name"
        product.price = "7.25"
        product.image_key = "5"
        product.category = None
        product.save()
        product.tags.clear()
        variant = product.variants.first()
        variant.value = "User edited variant"
        variant.save()
        product.variants.exclude(pk=variant.pk).delete()
        Category.objects.all().update(name="User category")
        Tag.objects.all().update(name="User tag")
        MemberProfile.objects.all().update(name="User member", avatar_key="")
        NewsItem.objects.all().update(title="User title", cover_key="", status="draft")
        before = snapshot()
        seed()
        self.assertEqual(snapshot(), before)

    def test_existing_key_collisions_and_unrelated_rows_are_untouched(self):
        category = Category.objects.create(slug="nova-demo-design", name="Existing category")
        tag = Tag.objects.create(slug="nova-demo-new", name="Existing tag")
        product = Product.objects.create(sku="NOVA-DEMO-KEYBOARD", name="Existing product", price="1.25")
        member = MemberProfile.objects.create(member_code="NOVA-DEMO-M001", name="Existing member", joined_at="2020-01-01")
        news = NewsItem.objects.create(pk=900001, title="Existing news")
        other = NewsItem.objects.create(pk=100, title="Unrelated news")
        references = [(type(obj), obj.pk, type(obj).objects.filter(pk=obj.pk).values().get()) for obj in (category, tag, product, member, news, other)]
        seed()
        for model, pk, values in references:
            self.assertEqual(model.objects.filter(pk=pk).values().get(), values)
        self.assertFalse(product.tags.exists())
        self.assertFalse(product.variants.exists())
        self.assertEqual(get_user_model().objects.count(), 0)

    def test_disabled_debug_refuses_without_writes(self):
        with override_settings(DEBUG=False), self.assertRaises(CommandError):
            seed()
        self.assertEqual([model.objects.count() for model in MODELS], [0] * len(MODELS))

    def test_non_sqlite_refuses_without_writes(self):
        from django.db import connection
        with patch.object(connection, "vendor", "postgresql"), self.assertRaises(CommandError):
            seed()
        self.assertEqual([model.objects.count() for model in MODELS], [0] * len(MODELS))

    def test_failed_creation_rolls_back_all_seed_changes(self):
        with patch.object(NewsItem.objects, "get_or_create", side_effect=RuntimeError("Synthetic failure")):
            with self.assertRaisesRegex(RuntimeError, "Synthetic failure"):
                seed()
        self.assertEqual([model.objects.count() for model in MODELS], [0] * len(MODELS))


if __name__ == "__main__":
    sys.exit(bool(get_runner(settings)(verbosity=2).run_tests(["__main__"])))
