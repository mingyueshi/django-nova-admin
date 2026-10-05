"""Small project policy hooks; counters and lockout remain owned by Axes."""
from django.http import HttpResponse
from django.utils.translation import gettext
from django.views.decorators.cache import never_cache


def connection_ip(request):
    return request.META.get("REMOTE_ADDR")


@never_cache
def lockout_response(request, original_response=None, credentials=None):
    # No submitted username, account status, password, challenge or token is
    # echoed. Projects can replace this with their own accessible support page.
    return HttpResponse(
        gettext("Sign-in temporarily unavailable. Please try again later or contact your administrator."),
        status=429,
        content_type="text/plain; charset=utf-8",
    )
