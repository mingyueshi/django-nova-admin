import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='StockPreview',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('site', models.CharField(max_length=150)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('rows', models.JSONField()),
                ('errors', models.JSONField()),
                ('submitted', models.BooleanField(default=False)),
                ('operator', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'permissions': [('import_stock', '可导入商品库存')],
                'default_permissions': (),
            },
        ),
    ]
