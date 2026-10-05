"""Mount before the existing site's catch-all; do not create a second AdminSite."""
from django.conf import settings
from django.http import HttpResponseBadRequest, HttpResponseNotFound, HttpResponseRedirect
from django.urls import path, reverse
from django.utils.translation import pgettext
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from .preferences import MODES, SESSION_KEY, safe_admin_return


def for_admin(admin_site):
    """Return include()-ready URLs guarded by this exact site's admin_view."""
    @csrf_protect
    @require_POST
    def preference(request):
        if not getattr(settings, "NOVA_ADMIN_ENABLED", True):
            return HttpResponseNotFound()
        mode = request.POST.get("mode")
        if mode not in MODES:
            return HttpResponseBadRequest(pgettext("Nova Admin", "Unknown theme mode"))
        request.session[SESSION_KEY] = mode
        index = reverse(f"{admin_site.name}:index")
        destination = safe_admin_return(request, request.POST.get("next", ""), index)
        return HttpResponseRedirect(destination)

    return ([path("preference/", admin_site.admin_view(preference), name="preference")], "nova_admin")
