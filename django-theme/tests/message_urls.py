"""Messages-only test fixtures use Django's existing storage and AdminSites."""
from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import path
from django.utils.safestring import mark_safe

from config.urls import urlpatterns as base_urls
from tests.multisite_urls import urlpatterns as multisite_urls, warehouse_site


def add_fixture_messages(request):
    messages.set_level(request, messages.DEBUG)
    messages.debug(request, 'debug fixture')
    messages.info(request, 'info fixture <script>unsafe()</script>', extra_tags='error pretend-warning')
    messages.info(request, mark_safe('<a href="/admin/">safe fixture link</a>'))
    messages.success(request, 'success fixture')
    messages.warning(request, 'warning fixture ' * 20)
    messages.error(request, 'error fixture')
    messages.add_message(request, 35, 'custom fixture', extra_tags='error')


def fixture(request, site=admin.site):
    add_fixture_messages(request)
    return site.index(request, extra_context={'is_popup': request.GET.get('_popup') == '1'})


def redirect_fixture(request):
    add_fixture_messages(request)
    return redirect('admin:index')


urlpatterns = [
    path('message-fixture/', admin.site.admin_view(fixture)),
    path('message-redirect/', admin.site.admin_view(redirect_fixture)),
    path('warehouse-message-fixture/', warehouse_site.admin_view(lambda request: fixture(request, warehouse_site))),
    *base_urls, *multisite_urls,
]
