"""Demo-only local synthetic media, never an upload or remote-image pipeline.

Opaque keys map to fixed bundled files. No record value becomes a URL, CSS value,
filesystem path, or network request. These public synthetic images are not a
pattern for serving private uploads; host projects must authorize private media.
"""
from urllib.parse import unquote, urlsplit

from django.contrib import admin
from django.contrib.admin.templatetags.admin_urls import add_preserved_filters
from django.contrib.admin.utils import quote
from django.templatetags.static import static
from django.urls import reverse
from django.utils.html import format_html


MEDIA_CHOICES = [(str(index), f"合成示例 {index + 1}") for index in range(6)]
# The sheet geometry is declared by the asset contract, not record input.
MEDIA_SHEETS = {
    "avatar": ("catalog/demo-media/avatars-sheet.webp", 44, 44),
    "product": ("catalog/demo-media/products-sheet.webp", 60, 60),
    "cover": ("catalog/demo-media/covers-sheet.webp", 96, 54),
}


def local_media_url(kind, key):
    """Fail closed for unknown kinds/keys and nonlocal STATIC_URL backends."""
    if kind not in MEDIA_SHEETS or not isinstance(key, str) or key not in dict(MEDIA_CHOICES):
        return None
    value = static(MEDIA_SHEETS[kind][0])
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if any(ord(char) < 32 for char in value):
        return None
    decoded = unquote(parsed.path)
    if (parsed.scheme or parsed.netloc or parsed.query or parsed.fragment
            or not decoded.startswith("/") or "\\" in decoded or "//" in decoded
            or any(part in {".", ".."} for part in decoded.split("/"))
            or any(ord(char) < 32 for char in decoded)):
        return None
    return value


def media_thumbnail(kind, key, label):
    """Fixed-size semantic image with a static, clipped 3×2 sheet viewport."""
    if kind not in MEDIA_SHEETS:
        raise ValueError("Unknown media shape")
    _, width, height = MEDIA_SHEETS[kind]
    source = local_media_url(kind, key)
    if not source:
        return format_html(
            '<span class="nova-media-thumb nova-media-thumb--{} nova-media-thumb--empty" '
            'role="img" aria-label="{}：暂无图片"><span aria-hidden="true">暂无</span></span>', kind, label,
        )
    index = int(key)  # Converted only after exact, fixed allowlist membership.
    return format_html(
        '<span class="nova-media-thumb nova-media-thumb--{}">'
        '<span class="nova-media-fallback" aria-hidden="true">图片</span>'
        '<span class="nova-media-slice nova-media-col-{} nova-media-row-{}">'
        '<img src="{}" alt="{}" width="{}" height="{}" loading="lazy" decoding="async">'
        '</span></span>',
        kind, index % 3, index // 3, source, label, width * 3, height * 2,
    )


class DemoMediaAdminMixin:
    """Opt-in demo column; every link reuses Django's existing change view.

    Request state stays in a closure, never on the shared ModelAdmin instance.
    Permission hooks are respected; record-level list visibility still belongs
    to the host ModelAdmin's get_queryset, exactly as it does in native Django.
    """
    media_kind = "product"
    media_field = "image_key"
    media_label_field = "name"
    media_column_label = "图片"

    class Media:
        css = {"all": ("catalog/demo-media.css",)}

    @admin.display(description="图片")
    def image_thumbnail(self, obj):
        # Attribute for Django system checks; request rendering uses the closure.
        return media_thumbnail(self.media_kind, getattr(obj, self.media_field), str(getattr(obj, self.media_label_field)))

    def get_list_display(self, request):
        @admin.display(description=self.media_column_label)
        def image_thumbnail(obj):
            if not self.has_view_or_change_permission(request, obj):
                return "—"
            label = str(getattr(obj, self.media_label_field))
            thumbnail = media_thumbnail(self.media_kind, getattr(obj, self.media_field), label)
            url = reverse(
                f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change",
                args=[quote(obj.pk)], current_app=self.admin_site.name,
            )
            url = add_preserved_filters(
                {"preserved_filters": self.get_preserved_filters(request), "opts": self.opts}, url,
            )
            return format_html('<a class="nova-media-link" href="{}" title="查看{}">{}</a>', url, label, thumbnail)
        return [image_thumbnail if column == "image_thumbnail" else column for column in super().get_list_display(request)]
