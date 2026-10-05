"""Project-owned second site, using explicit native ModelAdmin registrations."""
from django.contrib.admin import AdminSite

from catalog.admin import CategoryAdmin, ProductAdmin, TagAdmin
from catalog.models import Category, Product, Tag


warehouse_site = AdminSite(name="warehouse")
warehouse_site.site_header = "Nova · 仓库示例"
warehouse_site.site_title = "Nova Warehouse"
warehouse_site.index_title = "仓库工作台"
warehouse_site.register(Category, CategoryAdmin)
warehouse_site.register(Tag, TagAdmin)
warehouse_site.register(Product, ProductAdmin)

