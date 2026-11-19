from django.contrib import admin
from django import forms
from django.core.exceptions import PermissionDenied
from django.db import router, transaction
from django.http import HttpResponse
from django.urls import path
from django.utils.html import format_html
from django.utils import timezone
from nova_admin.columns import ColumnPreferencesMixin
from .models import Category, MemberProfile, NewsItem, Product, ProductPublicationRequest, ProductVariant, Tag
from .category_tree import can_view_tree, category_tree, edit_category_tree
from .charts import ProductActivityDayFilter
from .media import DemoMediaAdminMixin
from .pagination import BoundedPaginationAdminMixin
from .product_board import can_edit_status, can_view_board, product_publication, product_status_board
from .publication import PublicationConflict, lock_status, submit_publication
from .publication_calendar import publication_calendar
from .product_csv import MAX_EXPORT_ROWS, can_export_product_day, export_product_day


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ["name"]}
    change_list_template = "admin/catalog/category/change_list.html"
    fields = ("name", "slug")

    def get_urls(self):
        def wrap(view):
            wrapped = self.admin_site.admin_view(view)
            wrapped.model_admin = self
            return wrapped

        return [
            path("tree/", wrap(self.tree_view), name="catalog_category_tree"),
            path("tree/<int:pk>/", wrap(self.edit_tree_view), name="catalog_category_tree_edit"),
            *super().get_urls(),
        ]

    def tree_view(self, request):
        return category_tree(request, self)

    def edit_tree_view(self, request, pk):
        return edit_category_tree(request, self, pk)

    def changelist_view(self, request, extra_context=None):
        return super().changelist_view(request, {**(extra_context or {}), "show_category_tree": can_view_tree(request, self)})

    def save_model(self, request, obj, form, change):
        if change:
            # A concurrent tree move must survive an ordinary rename.
            obj.save(update_fields=self.fields)
        else:
            super().save_model(request, obj, form, change)


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
    list_editable = ["stock", "featured"]
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

    def get_urls(self):
        def admin_view(view):
            wrapped = self.admin_site.admin_view(view)
            wrapped.model_admin = self
            return wrapped

        return [
            path("status-board/", admin_view(self.status_board_view), name="catalog_product_status_board"),
            path("publication-calendar/", admin_view(self.publication_calendar_view), name="catalog_product_publication_calendar"),
            path("<int:product_id>/publication/", admin_view(self.publication_view), name="catalog_product_publication"),
            *super().get_urls(),
        ]

    def publication_calendar_view(self, request):
        return publication_calendar(request, self)

    def publication_view(self, request, product_id):
        return product_publication(request, self, product_id)

    def has_approve_permission(self, request, obj=None):
        return request.user.has_perm("catalog.approve_product")

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        status = form.base_fields.get("status")
        if status is not None:
            current = obj.status if obj is not None else Product.Status.DRAFT
            pending = obj is not None and obj.publication_requests.filter(result=ProductPublicationRequest.Result.PENDING).exists()
            status.choices = [(value, label) for value, label in Product.Status.choices
                              if value == current or (not pending and value != Product.Status.ACTIVE)]
            status.show_hidden_initial = True
            status.help_text = "上架请在商品状态看板提交审批。" if not pending else "正在审批上架，商品保留为草稿。"
        return form

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        try:
            return super().changeform_view(request, object_id, form_url, extra_context)
        except PublicationConflict:
            return HttpResponse("商品状态或上架申请已变化，请重新打开商品。", status=409)

    def save_model(self, request, obj, form, change):
        if change and ("status" not in form.changed_data or obj.status == form.initial.get("status")):
            # Stock edits and ordinary saves must not overwrite a concurrent approval.
            fields = [field.name for field in obj._meta.concrete_fields
                      if field.name in form.changed_data and not field.primary_key and field.name != "status"]
            obj.save(update_fields=[*fields, "updated_at"])
            return
        if change:
            products = self.get_queryset(request).using(router.db_for_write(Product)).filter(pk=obj.pk)
            previous = request.POST.get(form.add_initial_prefix("status"), form.initial["status"])
            if (not lock_status(products, previous)
                    or obj.publication_requests.filter(result=ProductPublicationRequest.Result.PENDING).exists()):
                raise PublicationConflict
        super().save_model(request, obj, form, change)

    def status_board_view(self, request):
        return product_status_board(request, self)

    def get_changelist_instance(self, request):
        zone = timezone.get_current_timezone()
        if ProductActivityDayFilter.parameter_name in request.GET:
            zone = ProductActivityDayFilter.signed_window(request).zone
        with timezone.override(zone):
            cl = super().get_changelist_instance(request)
            if request.method == "POST" and "_save" in request.POST and self.has_change_permission(request):
                # Bind the hidden IDs to this site's current filtered page, including its signed day.
                request.product_edit_page_ids = list(cl.result_list.values_list("pk", flat=True))
        return cl

    def get_changelist_formset(self, request, **kwargs):
        owner = self
        displayed = self.get_list_display(request)
        page_ids = getattr(request, "product_edit_page_ids", None)

        class ProductListFormSet(forms.BaseModelFormSet):
            def __init__(self, *args, **options):
                super().__init__(*args, **options)
                if self.is_bound and page_ids is not None:
                    # Narrow Django's submitted-object queryset before it resolves the forms.
                    queryset = self.queryset if self.queryset is not None else owner.get_queryset(request)
                    self.queryset = queryset.filter(pk__in=page_ids)

            def add_fields(self, form, index):
                super().add_fields(form, index)
                if self.is_bound:
                    identity = form.fields[owner.opts.pk.name]
                    identity.queryset = self.get_queryset()
                row_editable = owner.has_change_permission(request, form.instance)
                for name in owner.list_editable:
                    if not row_editable or name not in displayed:
                        if self.is_bound and form.add_prefix(name) in form.data:
                            raise PermissionDenied
                        form.fields.pop(name, None)
                if "stock" in form.fields:
                    form.fields["stock"].widget.attrs["aria-label"] = f"{form.instance.name} 库存"

        return super().get_changelist_formset(request, formset=ProductListFormSet, **kwargs)

    def changelist_view(self, request, extra_context=None):
        if request.method == "POST" and "_export_day_csv" in request.POST:
            return export_product_day(request, self)
        extra_context = {**(extra_context or {}), "show_product_board": can_view_board(request, self)}
        if ProductActivityDayFilter.parameter_name in request.GET and self.has_view_or_change_permission(request):
            if can_export_product_day(request, self):
                extra_context["product_csv_limit"] = MAX_EXPORT_ROWS
            # Django constructs the page formset after creating the changelist.
            with timezone.override(ProductActivityDayFilter.signed_window(request).zone):
                return super().changelist_view(request, extra_context)
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

    @admin.action(description="提交所选草稿上架审批", permissions=["change"])
    def publish_products(self, request, queryset):
        if not can_view_board(request, self) or not self.has_change_permission(request):
            raise PermissionDenied
        db = router.db_for_write(Product)
        drafts = list(queryset.using(db).filter(status=Product.Status.DRAFT).order_by("pk").distinct())
        products = self.get_queryset(request).using(db)
        submitted = 0
        with transaction.atomic(using=db):
            for product in drafts:
                if not self.has_view_or_change_permission(request, product) or not can_edit_status(request, self, product):
                    raise PermissionDenied
                if submit_publication(products, product, request.user):
                    submitted += 1
        self.message_user(request, f"已提交 {submitted} 件草稿商品上架审批。")


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
