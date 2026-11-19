from django.db import migrations, router


OLD_LABEL = "可导出按日期筛选的商品 CSV"
NEW_LABEL = "可导出按日期或状态筛选的商品 CSV"


def rename_permission(apps, schema_editor, old, new):
    permission = apps.get_model("auth", "Permission")
    db = schema_editor.connection.alias
    if router.allow_migrate_model(db, permission):
        permission.objects.using(db).filter(
            content_type__app_label="catalog", content_type__model="product",
            codename="export_product", name=old,
        ).update(name=new)


def forwards(apps, schema_editor):
    rename_permission(apps, schema_editor, OLD_LABEL, NEW_LABEL)


def backwards(apps, schema_editor):
    rename_permission(apps, schema_editor, NEW_LABEL, OLD_LABEL)


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0001_initial'),
        ('catalog', '0011_product_english_name'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='product',
            options={'ordering': ['-updated_at'], 'permissions': [('export_product', NEW_LABEL), ('approve_product', '可审批商品上架'), ('restore_product', '可从回收站还原商品')], 'verbose_name': '商品', 'verbose_name_plural': '商品'},
        ),
        migrations.RunPython(forwards, backwards),
    ]
