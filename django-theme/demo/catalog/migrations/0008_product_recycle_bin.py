import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0007_category_tree'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='product',
            options={'ordering': ['-updated_at'], 'permissions': [('export_product', '可导出按日期筛选的商品 CSV'), ('approve_product', '可审批商品上架'), ('restore_product', '可从回收站还原商品')], 'verbose_name': '商品', 'verbose_name_plural': '商品'},
        ),
        migrations.CreateModel(
            name='ProductRecycleEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('deleted_at', models.DateTimeField(auto_now_add=True, verbose_name='删除时间')),
                ('product', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='recycle_entry', to='catalog.product')),
            ],
            options={
                'default_permissions': (),
            },
        ),
    ]
