"""Two real, independent sites with distinct authentication/URL scopes for tests."""
from django.contrib.admin import AdminSite
from django.urls import include, path

from catalog.admin import CategoryAdmin, ProductAdmin, TagAdmin
from catalog.models import Category, Product, Tag
from nova_admin.urls import for_admin


class ReviewAdminSite(AdminSite):
    def has_permission(self, request):
        return super().has_permission(request) and request.user.has_perm("catalog.view_category")


warehouse_site = AdminSite(name="warehouse")
review_site = ReviewAdminSite(name="review")
for site in (warehouse_site, review_site):
    site.register(Product, ProductAdmin)
    site.register(Category, CategoryAdmin)
    site.register(Tag, TagAdmin)

urlpatterns = [
    path("warehouse/_theme/", include(for_admin(warehouse_site), namespace="warehouse_theme")),
    path("warehouse/", warehouse_site.urls),
    path("review/_theme/", include(for_admin(review_site), namespace="review_theme")),
    path("review/", review_site.urls),
]
