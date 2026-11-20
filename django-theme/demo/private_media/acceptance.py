from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image, PngImagePlugin

from .models import Attachment


class PrivateImageTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        storage_settings = self.settings(MEDIA_ROOT=self.temp.name)
        storage_settings.enable()
        self.addCleanup(storage_settings.disable)
        self.owner = get_user_model().objects.create_user("owner", is_staff=True)
        self.owner.user_permissions.add(*Permission.objects.filter(content_type__app_label="private_media"))
        self.client.force_login(self.owner)
        self.add = reverse("admin:private_media_attachment_add")

    def upload(self, raw):
        return self.client.post(self.add, {"title": "私有测试", "image": SimpleUploadedFile("original.png", raw)})

    def test_upload_reencoding_and_per_request_authorization(self):
        image = BytesIO()
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text("comment", "private-original-metadata")
        Image.new("RGB", (9, 8)).save(image, format="PNG", pnginfo=metadata)
        response = self.upload(image.getvalue() + b"original-trailer")
        self.assertEqual(response.status_code, 302)
        obj = Attachment.objects.get()
        self.assertEqual(obj.owner, self.owner)
        urls = [reverse("admin:private_media_attachment_" + op, args=[obj.pk]) for op in ("preview", "download")]
        detail = self.client.get(reverse("admin:private_media_attachment_change", args=[obj.pk]))
        self.assertNotContains(detail, obj.image.name)
        for url, disposition in zip(urls, ("inline", "attachment")):
            self.assertContains(detail, url)
            response = self.client.get(url)
            self.assertEqual(response["Content-Type"], "image/png")
            self.assertIn("no-store", response["Cache-Control"])
            self.assertTrue(response["Content-Disposition"].startswith(disposition))
            content = b"".join(response.streaming_content)
            self.assertEqual(Image.open(BytesIO(content)).size, (9, 8))
            self.assertNotIn(b"original-", content)
        with self.assertRaises(NotImplementedError):
            _ = obj.image.url
        self.assertEqual(self.client.get("/media/" + obj.image.name).status_code, 404)
        other = get_user_model().objects.create_user("other", is_staff=True)
        other.user_permissions.add(Permission.objects.get(codename="view_attachment"))
        self.client.force_login(other)
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.owner)
        self.owner.user_permissions.remove(Permission.objects.get(codename="view_attachment"))
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 404)

    def test_reject_active_oversized_and_corrupt_inputs_before_storage(self):
        for data in (b"<svg/>", b"<html>test</html>", b"not an image", b"x" * (2 * 1024 * 1024 + 1)):
            result = self.upload(data)
            self.assertTrue(result.context["adminform"].form.errors["image"])
        with patch("private_media.admin.Image.open") as decoder:
            decoder.return_value.__enter__.return_value.width = 4_000_001
            decoder.return_value.__enter__.return_value.height = 1
            self.assertContains(self.upload(b"test"), "400 万像素")
        self.assertFalse(Attachment.objects.exists())
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])

    def test_file_lifecycle_follows_admin_transaction(self):
        raw = BytesIO()
        Image.new("RGB", (2, 2)).save(raw, format="JPEG")
        registration = admin.site.get_model_admin(Attachment)
        with patch.object(registration, "log_addition", side_effect=RuntimeError("audit failed")):
            with self.assertRaisesMessage(RuntimeError, "audit failed"):
                self.upload(raw.getvalue())
        self.assertFalse(Attachment.objects.exists())
        self.assertEqual(list(Path(self.temp.name).iterdir()), [])
        self.assertEqual(self.upload(raw.getvalue()).status_code, 302)
        obj = Attachment.objects.get()
        file = Path(obj.image.path)
        with self.captureOnCommitCallbacks(execute=True):
            deleted = self.client.post(reverse("admin:private_media_attachment_delete", args=[obj.pk]), {"post": "yes"})
            self.assertEqual(deleted.status_code, 302)
            self.assertTrue(file.exists())
        self.assertFalse(file.exists())
