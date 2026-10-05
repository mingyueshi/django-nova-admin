"""Add fictional local-demo records without changing existing records.

Product SKU, member code, category/tag slug and reserved news IDs identify seed
records. News has no unique slug, so IDs 900001..900007 are reserved by this
helper. Existing records at those IDs are preserved, including edited titles.
No authentication users, passwords or permissions are created or changed.
"""
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction

from catalog.models import Category, MemberProfile, NewsItem, Product, ProductVariant, Tag

PRODUCTS = (
    ("KEYBOARD", "Halo 无线键盘", "399.00", "0"),
    ("ORGANIZER", "Grid 桌面收纳盒", "89.00", "1"),
    ("BACKPACK", "Trail 日常双肩包", "329.00", "2"),
    ("MEMO", "Note 桌面便笺", "29.00", "3"),
    ("STAND", "Orbit 折叠支架", "269.00", "4"),
    ("POUCH", "Fold 随行收纳袋", "79.00", "5"),
    ("MISSING", "待补图商品示例", "49.00", ""),
)
MEMBERS = ("林知夏", "周亦辰", "陈安宁", "许景行", "沈若晴", "顾书远", "无头像会员示例")
NEWS = (
    ("光与结构：城市美术馆的新视角", "design"),
    ("让协作自然发生的工作空间", "community"),
    ("山湖之间，寻找日常的留白", "places"),
    ("创作与日常：周末工作坊", "design"),
    ("绿色出行：社区里的慢生活", "places"),
    ("展览现场：灵感在这里发生", "design"),
    ("待补图新闻示例", "design"),
)


class Command(BaseCommand):
    help = "Add fictional adult/product/news data to the local SQLite demo; preserve existing rows."

    def handle(self, *args, **options):
        if not settings.DEBUG or connections["default"].vendor != "sqlite":
            raise CommandError("seed_demo is restricted to the local DEBUG=True SQLite demo.")
        counts = {"categories": 0, "tags": 0, "products": 0, "variants": 0, "members": 0, "news": 0}
        with transaction.atomic():
            category, created = Category.objects.get_or_create(
                slug="nova-demo-design", defaults={"name": "合成示例 · 设计生活"},
            )
            counts["categories"] += created
            tags = []
            for slug, name in (("nova-demo-new", "合成示例 · 新品"), ("nova-demo-featured", "合成示例 · 精选")):
                tag, created = Tag.objects.get_or_create(slug=slug, defaults={"name": name})
                counts["tags"] += created
                tags.append(tag)
            for index, (key, name, price, image_key) in enumerate(PRODUCTS):
                product, created = Product.objects.get_or_create(
                    sku=f"NOVA-DEMO-{key}",
                    defaults={"name": name, "price": Decimal(price), "stock": 0 if index == 6 else 12 * (index + 1),
                              "image_key": image_key, "category": category, "featured": index % 2 == 0,
                              "status": ("active", "draft", "archived")[index % 3]},
                )
                counts["products"] += created
                # Relationships belong to the user as soon as a product exists.
                # Never restore deleted tags/variants or replace edited values.
                if created:
                    product.tags.add(tags[0])
                    if index % 2 == 0:
                        product.tags.add(tags[1])
                    for field, value in (("示例款式", "标准款"), ("演示用途", "本地研究用虚构数据")):
                        _, added = ProductVariant.objects.get_or_create(product=product, name=field, defaults={"value": value})
                        counts["variants"] += added
            for index, name in enumerate(MEMBERS):
                _, created = MemberProfile.objects.get_or_create(
                    member_code=f"NOVA-DEMO-M{index + 1:03}",
                    defaults={"name": name, "avatar_key": str(index) if index < 6 else "",
                              "tier": "premium" if index % 2 == 0 else "standard", "active": index != 4,
                              "joined_at": date(2026, 9, 10 + index)},
                )
                counts["members"] += created
            for index, (title, section) in enumerate(NEWS):
                _, created = NewsItem.objects.get_or_create(
                    pk=900001 + index,
                    defaults={"title": title, "cover_key": str(index) if index < 6 else "", "section": section,
                              "status": "published" if index < 6 else "draft",
                              "published_on": date(2026, 9, 24 + index) if index < 6 else None},
                )
                counts["news"] += created
        self.stdout.write(self.style.SUCCESS("Synthetic local demo records added: " + ", ".join(f"{key}={value}" for key, value in counts.items())))
        self.stdout.write("Existing records preserved. No login account created; use createsuperuser separately.")
