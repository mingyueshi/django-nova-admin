"""Local example: existing default site plus an explicitly separate site."""
from django.conf import settings
from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path
from django.views.decorators.http import require_GET

from nova_admin.urls import for_admin
from .compose_sites import warehouse_site


@require_GET
def health(request):
    # Container readiness, not a database/production monitoring endpoint.
    return HttpResponse("ok", content_type="text/plain")


urlpatterns = [path("_health/", health)]
if settings.NOVA_EXAMPLE_CAPTCHA:
    from nova_admin.captcha import CaptchaAdminAuthenticationForm, captcha_refresh

    # Both existing instances receive the explicit opt-in. One shared upstream
    # CAPTCHA mount avoids global image/audio URL-name collisions.
    for site in (admin.site, warehouse_site):
        site.login_form = CaptchaAdminAuthenticationForm
        site.login_template = "nova_admin/captcha_login.html"
    urlpatterns += [
        path("_captcha/refresh/", captcha_refresh, name="nova-captcha-refresh"),
        path("_captcha/", include("captcha.urls")),
    ]

urlpatterns += [
    path("admin/_theme/", include(for_admin(admin.site), namespace="admin_theme")),
    path("admin/", admin.site.urls),
    path("warehouse/_theme/", include(for_admin(warehouse_site), namespace="warehouse_theme")),
    path("warehouse/", warehouse_site.urls),
]

