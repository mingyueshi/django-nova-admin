"""Isolated admin sites used only by the pagination integration tests."""
from django.contrib import admin
from django.contrib.admin.views.main import ChangeList
from django.urls import path

from catalog.models import Product
from catalog.pagination import BoundedPaginationAdminMixin


class ScopedChangeList(ChangeList):
    def get_queryset(self, request, exclude_parameters=None):
        return super().get_queryset(request, exclude_parameters).filter(stock__gt=0)


class ExistingProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "sku", "status", "featured")
    list_editable = ("featured",)
    list_filter = ("status",)
    search_fields = ("name", "sku")
    ordering = ("sku",)
    list_per_page = 20
    list_max_show_all = 200
    actions = ("set_active",)

    def get_queryset(self, request):
        return super().get_queryset(request).exclude(name__startswith="Hidden")

    def get_changelist(self, request, **kwargs):
        return ScopedChangeList

    @admin.action(permissions=("change",))
    def set_active(self, request, queryset):
        queryset.update(status=Product.Status.ACTIVE)


class PagingProductAdmin(BoundedPaginationAdminMixin, ExistingProjectAdmin):
    pass


optin_site = admin.AdminSite(name="pagination_test")
optin_site.register(Product, PagingProductAdmin)
plain_site = admin.AdminSite(name="pagination_plain")
plain_site.register(Product, ExistingProjectAdmin)

urlpatterns = [
    path("optin/", optin_site.urls),
    path("plain/", plain_site.urls),
    path("admin/", admin.site.urls),
]
