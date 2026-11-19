import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0008_product_recycle_bin'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ProductBatchTask',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('site', models.CharField(max_length=100)),
                ('operation', models.CharField(choices=[('submit_publication', '批量提交上架审批')], max_length=32)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'default_permissions': (),
            },
        ),
        migrations.CreateModel(
            name='ProductBatchItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('product_updated_at', models.DateTimeField()),
                ('previous_request_id', models.PositiveBigIntegerField(default=0)),
                ('outcome', models.CharField(choices=[('pending', '待处理'), ('submitted', '已提交上架审批'), ('not_draft', '商品不是草稿'), ('conflict', '已有待审批申请，或商品、审批记录已变化'), ('unavailable', '商品不可用或修改权限已变化'), ('invalid', '提交校验失败')], default='pending', max_length=16)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='+', to='catalog.product')),
                ('task', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='catalog.productbatchtask')),
            ],
            options={
                'default_permissions': (),
            },
        ),
        migrations.AddIndex(
            model_name='productbatchtask',
            index=models.Index(fields=['owner', 'site', '-created_at'], name='catalog_batch_owner_site'),
        ),
        migrations.AddIndex(
            model_name='productbatchitem',
            index=models.Index(fields=['task', 'outcome', 'id'], name='catalog_batch_pending'),
        ),
        migrations.AddConstraint(
            model_name='productbatchitem',
            constraint=models.UniqueConstraint(fields=('task', 'product'), name='catalog_batch_unique_product'),
        ),
    ]
