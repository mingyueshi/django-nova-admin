import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0009_product_batch_tasks'),
    ]

    operations = [
        migrations.AddField(
            model_name='productpublicationrequest',
            name='site',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.CreateModel(
            name='ProductNotification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('read_at', models.DateTimeField(null=True)),
                ('publication', models.OneToOneField(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to='catalog.productpublicationrequest')),
                ('task', models.OneToOneField(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to='catalog.productbatchtask')),
            ],
            options={
                'ordering': ['-created_at', '-pk'],
                'default_permissions': (),
                'constraints': [models.CheckConstraint(condition=models.Q(models.Q(('publication__isnull', False), ('task__isnull', True)), models.Q(('publication__isnull', True), ('task__isnull', False)), _connector='OR'), name='catalog_notification_one_source')],
            },
        ),
    ]
