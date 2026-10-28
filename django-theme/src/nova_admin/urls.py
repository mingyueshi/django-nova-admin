"""Mount before the existing site's catch-all; do not create a second AdminSite."""
from django.conf import settings
from django.http import HttpResponseBadRequest, HttpResponseNotFound, HttpResponseRedirect
from django.urls import path, reverse
from django.utils.translation import pgettext
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from .preferences import MODES, PALETTES, PALETTE_SESSION_KEY, SESSION_KEY, safe_admin_return


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
        # Validate the complete supplied pair before mutating either preference.
        # Legacy mode-only callers retain their existing palette, including the
        # configured default when no palette has been saved yet.
        palette = request.POST.get("palette")
        if palette is not None and palette not in PALETTES:
            return HttpResponseBadRequest(pgettext("Nova Admin", "Unknown color palette"))
        request.session[SESSION_KEY] = mode
        if palette is not None:
            request.session[PALETTE_SESSION_KEY] = palette
        match = getattr(request, "resolver_match", None)
        parents = match.namespaces[:-1] if match else []
        current_app = ":".join([*parents, admin_site.name])
        index = reverse(f"{current_app}:index", current_app=current_app,
                        urlconf=getattr(request, "urlconf", None))
        destination = safe_admin_return(request, request.POST.get("next", ""), index)
        return HttpResponseRedirect(destination)

    return ([path("preference/", admin_site.admin_view(preference), name="preference")], "nova_admin")
