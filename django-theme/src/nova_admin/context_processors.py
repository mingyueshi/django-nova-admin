"""Presentation context only. Permissions and application lists belong to AdminSite."""
from django.conf import settings
from django.urls import NoReverseMatch, get_resolver, get_urlconf, reverse

from .preferences import selected_mode, selected_palette
from .branding import branding


def _has_preference_route(namespace, urlconf, current_app):
    """Check optional routes without raising for a missing namespace or name.

    Follow Django's application/instance namespace selection, including a
    current_app hint. The resolver owns its normal URLconf/language caches;
    Nova keeps no global endpoint cache that can leak between sites or tests.
    """
    resolver = get_resolver(urlconf)
    current_path = current_app.split(":") if current_app else []
    for index, name in enumerate(namespace.split(":")):
        current = current_path[index] if index < len(current_path) else None
        instances = resolver.app_dict.get(name)
        if instances:
            if current in instances:
                name = current
            elif name not in instances:
                name = instances[0]
        if name != current:
            current_path = []
        entry = resolver.namespace_dict.get(name)
        if entry is None:
            return False
        resolver = entry[1]
    return "preference" in resolver.reverse_dict


def _preference_url(request):
    match = getattr(request, "resolver_match", None)
    current_app = getattr(request, "current_app", None)
    # Do not even inspect the URL resolver on ordinary frontend pages. Explicit
    # current_app also supports admin templates rendered without a URL match.
    if not current_app and match is not None and "admin" not in match.app_names:
        return ""
    if match is None and not current_app:
        return ""
    matched_namespace = match.namespace if match is not None else ""
    # AdminSite sets a bare current_app name. Retain surrounding instance
    # namespaces when they describe this same site, e.g. east:warehouse.
    if not current_app or matched_namespace.rsplit(":", 1)[-1] == current_app:
        current_app = matched_namespace or current_app
    site_name = current_app or matched_namespace
    if not site_name:
        return ""
    namespaces = getattr(settings, "NOVA_ADMIN_URL_NAMESPACES", {"admin": "nova_admin"})
    if not isinstance(namespaces, dict):
        return ""
    namespace = namespaces.get(site_name, namespaces.get(site_name.rsplit(":", 1)[-1]))
    if not isinstance(namespace, str) or not namespace:
        return ""
    urlconf = getattr(request, "urlconf", None) or get_urlconf()
    if not _has_preference_route(namespace, urlconf, current_app):
        return ""
    try:
        return reverse(f"{namespace}:preference", urlconf=urlconf, current_app=current_app)
    except NoReverseMatch:
        # A mounted but incompatible custom route (e.g. required URL arguments)
        # must not prevent the native Admin page from rendering.
        return ""


def theme(request):
    enabled = getattr(settings, "NOVA_ADMIN_ENABLED", True)
    mode = selected_mode(request)
    # Each existing AdminSite can opt in to its own mounted preference endpoint.
    # Never guess another site's namespace or invent a duplicate model registry.
    preference_url = _preference_url(request) if enabled else ""
    return {
        "nova_admin_enabled": enabled,
        "nova_admin_active": enabled and mode != "native",
        "nova_admin_mode": mode,
        "nova_admin_palette": selected_palette(request),
        "nova_admin_navigation": bool(getattr(settings, "NOVA_ADMIN_NAVIGATION", False)),
        "nova_admin_preference_url": preference_url,
        "nova_admin_return_path": request.get_full_path(),
        "nova_admin_branding": branding() if enabled and mode != "native" else {},
    }
