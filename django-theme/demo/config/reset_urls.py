from django.contrib.auth import views
from django.urls import path

from .urls import urlpatterns as admin_urls

urlpatterns = [
    path("admin/password-reset/", views.PasswordResetView.as_view(), name="admin_password_reset"),
    path("admin/password-reset/sent/", views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("admin/reset/<uidb64>/<token>/", views.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("admin/reset/complete/", views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
    *admin_urls,
]
