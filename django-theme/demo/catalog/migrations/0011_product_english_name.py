from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0010_product_notifications'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='name_en',
            field=models.CharField(blank=True, default='', max_length=120, verbose_name='英文名称'),
        ),
    ]
