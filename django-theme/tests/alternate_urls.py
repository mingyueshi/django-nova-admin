from django.contrib import admin
from django.urls import include, path
from nova_admin.urls import for_admin

urlpatterns = [
    path("backoffice/_theme/", include(for_admin(admin.site))),
    path("backoffice/", admin.site.urls),
]
