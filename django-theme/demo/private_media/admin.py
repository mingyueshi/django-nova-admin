from io import BytesIO

from django import forms
from django.contrib import admin
from django.core.files.base import ContentFile
from django.http import FileResponse, Http404
from django.urls import path, reverse
from django.utils.html import format_html
from django.views.decorators.http import require_safe
from PIL import Image

from .models import Attachment


class UploadForm(forms.ModelForm):
    # Bound the input before asking any decoder to inspect it.
    image = forms.FileField(label="PNG 或 JPEG 图片", help_text="最多 2 MiB、400 万像素。")

    class Meta:
        model = Attachment
        fields = ("title", "image")

    def clean_image(self):
        upload = self.cleaned_data["image"]
        if upload.size > 2 * 1024 * 1024:
            raise forms.ValidationError("图片超过 2 MiB。")
        try:
            with Image.open(upload, formats=("PNG", "JPEG")) as source:
                if source.width * source.height > 4_000_000 or getattr(source, "is_animated", False):
                    raise forms.ValidationError("仅接受 400 万像素以内的静态图片。")
                pixels = source.convert("RGBA")
                pixels.info.clear()
                output = BytesIO()
                pixels.save(output, format="PNG")
        except (OSError, SyntaxError, ValueError, Image.DecompressionBombError) as exc:
            raise forms.ValidationError("图片无法解码，请上传有效 PNG 或 JPEG。") from exc
        return ContentFile(output.getvalue(), name="image.png")


@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    form = UploadForm
    list_display = ("title", "owner", "file_links")
    readonly_fields = ("owner", "file_links")

    def get_fields(self, request, obj=None):
        return ("title", "owner", "file_links") if obj else ("title", "image")

    def has_view_permission(self, request, obj=None):
        return request.user.has_perm("private_media.view_attachment")

    def has_change_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        rows = super().get_queryset(request).select_related("owner")
        return rows if request.user.is_superuser else rows.filter(owner=request.user)

    def add_view(self, request, form_url="", extra_context=None):
        try:
            return super().add_view(request, form_url, extra_context)
        except Exception:
            # The native admin transaction rolled back; filesystem writes did not.
            obj = getattr(request, "new_private_attachment", None)
            if obj is not None and obj.image._committed and not Attachment.objects.filter(image=obj.image.name).exists():
                obj.image.delete(save=False)
            raise

    def save_model(self, request, obj, form, change):
        request.new_private_attachment = obj
        obj.owner = request.user
        super().save_model(request, obj, form, change)

    def get_urls(self):
        serve = self.admin_site.admin_view(require_safe(self.serve))
        return [
            path("<int:pk>/preview/", serve, name="private_media_attachment_preview"),
            path("<int:pk>/download/", serve, {"download": True}, name="private_media_attachment_download"),
            *super().get_urls(),
        ]

    @admin.display(description="图片")
    def file_links(self, obj):
        links = [reverse(f"admin:private_media_attachment_{action}", args=[obj.pk], current_app=self.admin_site.name)
                 for action in ("preview", "download")]
        return format_html('<a href="{}">预览</a> · <a href="{}">下载</a>', *links)

    def serve(self, request, pk, download=False):
        obj = self.get_object(request, str(pk))
        if obj is None or not self.has_view_permission(request, obj):
            raise Http404
        try:
            stream = obj.image.open("rb")
        except FileNotFoundError as exc:
            raise Http404 from exc
        response = FileResponse(stream, content_type="image/png", as_attachment=download, filename=f"image-{pk}.png")
        response["Cache-Control"] = "private, no-store"
        response["Content-Security-Policy"] = "default-src 'none'; sandbox"
        response["X-Content-Type-Options"] = "nosniff"
        return response
