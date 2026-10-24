"""Opt-in same-AdminSite integration using upstream Axes decorators."""
from axes.decorators import axes_dispatch
from django.contrib import admin
from django.urls import include, path, URLPattern

from nova_admin.axes import AxesCaptchaAdminAuthenticationForm
from nova_admin import captcha_urls as protected_captcha_urls
from nova_admin.captcha import captcha_refresh
from .urls import urlpatterns as project_urls

admin.site.login_form = AxesCaptchaAdminAuthenticationForm
admin.site.login_template = "nova_admin/captcha_login.html"

# Retain protected image/audio URL names and patterns, but do not expose GET
# refresh API: only Nova's signed, consuming, CSRF-protected POST can refresh.
captcha_urls = [
    URLPattern(route.pattern, axes_dispatch(route.callback), route.default_args, route.name)
    for route in protected_captcha_urls.urlpatterns
    if route.name != "captcha-refresh"
]
urlpatterns = [
    # Decorate the existing login view before the site's catch-all route. This
    # also rejects locked-out GETs before generating another challenge.
    path("admin/login/", axes_dispatch(admin.site.login)),
    path("admin/_captcha/refresh/", axes_dispatch(captcha_refresh), name="nova-captcha-refresh"),
    path("admin/_captcha/", include(captcha_urls)),
    *project_urls,
]
