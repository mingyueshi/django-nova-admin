from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("catalog", "0002_category_tag_product_category_product_tags")]

    operations = [
        migrations.AddField(
            model_name="product",
            name="featured",
            field=models.BooleanField(
                default=False,
                help_text="勾选后需保存才会生效。列表中的开关也使用 Django 原生批量保存。",
                verbose_name="精选推荐",
            ),
        ),
    ]
