import uuid

from django.conf import settings
from django.db import models


class StockPreview(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    operator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    site = models.CharField(max_length=150)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    rows = models.JSONField()
    errors = models.JSONField()
    submitted = models.BooleanField(default=False)

    class Meta:
        default_permissions = ()
        permissions = [("import_stock", "可导入商品库存")]
