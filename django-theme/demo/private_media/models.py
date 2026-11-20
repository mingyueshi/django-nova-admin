from uuid import uuid4

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import models, transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver


class PrivateStorage(FileSystemStorage):
    def url(self, name):
        raise NotImplementedError("Private images are delivered through the authorized admin view.")


def storage_name(instance, filename):
    return f"{uuid4().hex}.png"


class Attachment(models.Model):
    title = models.CharField("标题", max_length=100)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="上传人")
    image = models.ImageField("图片", storage=PrivateStorage(), upload_to=storage_name)

    class Meta:
        verbose_name = verbose_name_plural = "私有图片"

    def __str__(self):
        return self.title


@receiver(post_delete, sender=Attachment)
def remove_deleted_file(sender, instance, using, **kwargs):
    image = instance.image
    transaction.on_commit(lambda: image.storage.delete(image.name), using=using)
