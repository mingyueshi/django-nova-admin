"""Explicit slider opt-in on the existing demo AdminSite."""
from django.contrib import admin
from django.urls import include, path
from nova_admin.slider import SliderCaptchaAdminAuthenticationForm
from .urls import urlpatterns

admin.site.login_form = SliderCaptchaAdminAuthenticationForm
admin.site.login_template = "nova_admin/slider_login.html"
urlpatterns = [
    path("admin/_slider/", include("nova_slider_captcha.urls")),
    *urlpatterns,
]
