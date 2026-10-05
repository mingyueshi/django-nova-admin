"""Container startup: local migrations, bounded synthetic data, dev server."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "django-theme" / "demo"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.compose_settings")


def seed():
    """Add four fictional records; never alter existing records or auth users."""
    from datetime import date
    from django.db import transaction
    from catalog.models import Category, MemberProfile, NewsItem, Product, ProductVariant, Tag

    with transaction.atomic():
        category, _ = Category.objects.get_or_create(
            slug="nova-compose-local", defaults={"name": "Compose 合成示例"},
        )
        tag, _ = Tag.objects.get_or_create(slug="nova-compose-local", defaults={"name": "本地演示"})
        for index, (sku, name, image) in enumerate((
            ("NOVA-COMPOSE-KEYBOARD", "本地示例 · 无线键盘", "0"),
            ("NOVA-COMPOSE-ORGANIZER", "本地示例 · 桌面收纳", "1"),
        )):
            product, created = Product.objects.get_or_create(sku=sku, defaults={
                "name": name, "price": "99.00", "stock": 12 + index,
                "category": category, "image_key": image, "status": "draft",
            })
            if created:
                product.tags.add(tag)
                ProductVariant.objects.create(product=product, name="示例规格", value="标准款")
        MemberProfile.objects.get_or_create(member_code="NOVA-COMPOSE-M001", defaults={
            "name": "合成成年会员", "avatar_key": "0", "joined_at": date(2026, 10, 1),
        })
        # Reserved synthetic ID, only within this example's dedicated database.
        NewsItem.objects.get_or_create(pk=910001, defaults={
            "title": "本地合成新闻示例", "cover_key": "0", "section": "design",
        })


def main():
    import django
    django.setup()
    from django.conf import settings
    from django.core.management import call_command
    from django.db import connection

    config = settings.DATABASES["default"]
    if not settings.DEBUG or connection.vendor != "postgresql" or any(
        config[key] != value for key, value in {"HOST": "db", "NAME": "nova_local", "USER": "nova_local"}.items()
    ):
        raise RuntimeError("This initializer only supports the isolated Compose database.")
    call_command("check")
    call_command("migrate", interactive=False)
    seed()
    # No implicit account creation, password changes, or permission grants.
    os.execv(sys.executable, [sys.executable, "manage.py", "runserver", "0.0.0.0:8000", "--noreload"])


if __name__ == "__main__":
    main()

