"""Explicit opt-in on the existing AdminSite; never create a parallel registry."""
from django.contrib import admin
from django.urls import include, path
from nova_admin.captcha import CaptchaAdminAuthenticationForm, captcha_refresh
from .urls import urlpatterns

admin.site.login_form = CaptchaAdminAuthenticationForm
admin.site.login_template = "nova_admin/captcha_login.html"
urlpatterns = [
    path("admin/_captcha/refresh/", captcha_refresh, name="nova-captcha-refresh"),
    path("admin/_captcha/", include("captcha.urls")),
    *urlpatterns,
]
