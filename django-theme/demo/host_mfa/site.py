from django.contrib.admin import AdminSite
from django.contrib.admin.apps import AdminConfig


class VerifiedAdminConfig(AdminConfig):
    default_site = "host_mfa.site.VerifiedAdminSite"


class VerifiedAdminSite(AdminSite):
    def has_permission(self, request):
        return super().has_permission(request) and request.user.is_verified()
