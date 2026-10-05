"""Namespace sentinel only: this is NOT the django-admin-honeypot package."""
from django.http import HttpResponse
from django.urls import include, path


def decoy_namespace_sentinel(request):
    return HttpResponse("Third-party namespace routing sentinel")


urlpatterns = [
    path("admin/", include(([path("login/", decoy_namespace_sentinel, name="login")], "admin_honeypot"), namespace="admin_honeypot")),
    path("staff-console/", include("config.security_urls")),
]
