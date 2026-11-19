from django.contrib import admin
from django import forms
from django.utils.html import format_html
from django.utils import timezone
from nova_admin.columns import ColumnPreferencesMixin
from .models import Category, MemberProfile, NewsItem, Product, ProductVariant, Tag
from .charts import ProductActivityDayFilter
from .media import DemoMediaAdminMixin
from .pagination import BoundedPaginationAdminMixin
from .product_csv import MAX_EXPORT_ROWS, can_export_product_day, export_product_day


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ["name"]}


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ["name"]}


class VariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1


@admin.register(Product)
class ProductAdmin(ColumnPreferencesMixin, BoundedPaginationAdminMixin, DemoMediaAdminMixin, admin.ModelAdmin):
    nova_preference_columns = ("image_thumbnail", "sku", "price", "stock", "status_badge", "updated_at")
    change_list_template = "admin/catalog/product/change_list.html"
    list_display = ["name", "image_thumbnail", "sku", "price", "stock", "status_badge", "featured", "updated_at"]
    list_editable = ["featured"]
    search_fields = ["name", "sku"]
    search_help_text = "搜索商品名称或 SKU"
    list_filter = [ProductActivityDayFilter, "status"]
    readonly_fields = ["updated_at"]
    autocomplete_fields = ["category"]
    filter_horizontal = ["tags"]
    fieldsets = [
        ("商品信息", {"fields": ["name", "sku", "image_key", "category", "tags"]}),
        ("价格与库存", {"fields": [("price", "stock"), "status", "featured"]}),
        ("维护信息", {"fields": ["updated_at"], "classes": ["collapse"]}),
    ]
    inlines = [VariantInline]
    actions = ["publish_products"]
    list_per_page = 20

    def get_changelist_instance(self, request):
        if ProductActivityDayFilter.parameter_name in request.GET:
            # Native date lookups and pagination counts use Django's active timezone.
            window = ProductActivityDayFilter.signed_window(request)
            with timezone.override(window.zone):
                return super().get_changelist_instance(request)
        return super().get_changelist_instance(request)

    def changelist_view(self, request, extra_context=None):
        if request.method == "POST" and "_export_day_csv" in request.POST:
            return export_product_day(request, self)
        if ProductActivityDayFilter.parameter_name in request.GET and can_export_product_day(request, self):
            extra_context = {**(extra_context or {}), "product_csv_limit": MAX_EXPORT_ROWS}
        return super().changelist_view(request, extra_context)

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        # Demo-only opt-in. The theme never changes a host ModelAdmin's fields.
        # This stays a CheckboxInput and submits through Django's own formset.
        if db_field.name == "featured":
            kwargs["widget"] = forms.CheckboxInput(attrs={
                "class": "nova-switch",
                "aria-label": "精选推荐（保存后生效）",
                "title": "精选推荐：修改后请点击保存",
            })
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    @admin.display(description="状态", ordering="status")
    def status_badge(self, obj):
        # Keep text and native sorting; no clickable or fabricated switch state.
        tone = obj.status if obj.status in Product.Status.values else "unknown"
        return format_html('<span class="nova-status nova-status--{}">{}</span>', tone, obj.get_status_display())

    @admin.action(description="上架所选商品", permissions=["change"])
    def publish_products(self, request, queryset):
        count = queryset.update(status=Product.Status.ACTIVE, updated_at=timezone.now())
        self.message_user(request, f"已上架 {count} 件商品。")


@admin.register(MemberProfile)
class MemberProfileAdmin(ColumnPreferencesMixin, BoundedPaginationAdminMixin, DemoMediaAdminMixin, admin.ModelAdmin):
    nova_preference_columns = ("image_thumbnail", "member_code", "tier", "active", "joined_at")
    media_kind = "avatar"
    media_field = "avatar_key"
    media_column_label = "头像"
    list_display = ["name", "image_thumbnail", "member_code", "tier", "active", "joined_at"]
    search_fields = ["name", "member_code"]
    search_help_text = "搜索会员姓名或会员编号"
    list_filter = ["tier", "active"]
    list_per_page = 20


@admin.register(NewsItem)
class NewsItemAdmin(ColumnPreferencesMixin, BoundedPaginationAdminMixin, DemoMediaAdminMixin, admin.ModelAdmin):
    nova_preference_columns = ("image_thumbnail", "section", "status", "published_on")
    media_kind = "cover"
    media_field = "cover_key"
    media_label_field = "title"
    media_column_label = "封面"
    list_display = ["title", "image_thumbnail", "section", "status", "published_on"]
    search_fields = ["title"]
    search_help_text = "搜索新闻标题"
    list_filter = ["section", "status"]
    list_per_page = 20
