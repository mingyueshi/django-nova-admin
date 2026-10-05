from django.contrib import admin
from django.urls import include, path
from nova_admin.urls import for_admin

# Branding uses Django's supported public attributes. Existing registrations stay intact.
admin.site.site_header = "Nova · 管理中心"
admin.site.site_title = "Nova Admin"
admin.site.index_title = "工作台"

urlpatterns = [
    path("admin/_theme/", include(for_admin(admin.site))),
    path("admin/", admin.site.urls),
]
