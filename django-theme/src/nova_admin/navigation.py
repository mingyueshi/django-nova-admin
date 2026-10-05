"""Optional metadata for native AdminSite navigation, with no registry or queries."""
from copy import deepcopy
import logging

from django.conf import settings
from django.utils.module_loading import import_string

logger = logging.getLogger(__name__)
MAX_SHORTCUTS = 50
# SVG path data is package-owned. Configuration selects a name, never HTML,
# a remote asset, CSS, a template path, or a URL.
ICON_PATHS = {
    "box": "M3 7 12 3l9 4v10l-9 4-9-4V7Zm0 0 9 4 9-4M12 11v10M7 5l10 4",
    "users": "M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M16 3a4 4 0 0 1 0 8M22 21v-2a4 4 0 0 0-3-3.87M13 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0",
    "tag": "M20 13 13 20a2 2 0 0 1-3 0L2 12V2h10l8 8a2 2 0 0 1 0 3ZM7 7h.01",
    "folder": "M3 7V4h6l2 3h10v13H3V7Z",
    "file": "M14 2H4v20h16V8l-6-6ZM14 2v6h6M8 13h8M8 17h8",
    "chart": "M3 3v18h18M7 16v-5M12 16V7M17 16v-8",
    "home": "m3 10 9-7 9 7v11h-6v-7H9v7H3V10Z",
    "star": "m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.6l6.2-.9L12 3Z",
    "settings": "M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M5 19l2-2M17 7l2-2M18 12a6 6 0 1 1-12 0 6 6 0 0 1 12 0M14 12a2 2 0 1 1-4 0 2 2 0 0 1 4 0",
}


def resolve_provider(value):
    """Resolve an explicit host-project hook without ever calling it here."""
    if isinstance(value, str):
        try:
            value = import_string(value)
        except Exception:
            return None
    return value if callable(value) else None


def _provided(setting, request, available):
    configured = getattr(settings, setting, None)
    if configured is None:
        return {}
    provider = resolve_provider(configured)
    if provider is None:
        return {}
    try:
        # Providers get isolated copies of only the already-visible app list.
        # A hook cannot mutate the native context or another hook's input.
        result = provider(request, deepcopy(available))
        return result if isinstance(result, dict) else {}
    except Exception:
        # Do not log exception text: a project provider could include user data.
        logger.warning("Nova navigation provider failed: %s", setting)
        return {}


def extend_navigation(groups, request=None):
    """Decorate existing links; returned configuration can never add a page."""
    available = [app for group in groups for app in group["apps"]]
    icons = getattr(settings, "NOVA_ADMIN_NAV_ICONS", {})
    icons = icons if isinstance(icons, dict) else {}
    provided_icons = _provided("NOVA_ADMIN_NAV_ICON_PROVIDER", request, available) if available else {}
    badges = _provided("NOVA_ADMIN_NAV_BADGE_PROVIDER", request, available) if available else {}
    favorites = getattr(settings, "NOVA_ADMIN_NAV_FAVORITES", False) is True
    visible = {}
    decorated = []
    for group in groups:
        decorated_apps = []
        for app in group["apps"]:
            app_key = app["app_label"]
            icon = provided_icons.get(app_key, icons.get(app_key))
            copied_app = {**app, "nova_icon_path": ICON_PATHS.get(icon) if isinstance(icon, str) else None}
            copied_models = []
            for model in app["models"]:
                if not isinstance(model, dict):
                    continue
                object_name = model.get("object_name")
                key = f"{app_key}.{object_name.lower()}" if isinstance(object_name, str) else ""
                icon = provided_icons.get(key, icons.get(key))
                badge = badges.get(key)
                copied = {**model, "nova_key": key,
                          "nova_icon_path": ICON_PATHS.get(icon) if isinstance(icon, str) else None,
                          "nova_badge": None}
                # Add-only models have no list destination and gain no count.
                if key and model.get("admin_url"):
                    if type(badge) is int and 0 <= badge <= 2147483647:
                        copied["nova_badge"] = badge
                    visible.setdefault(key, copied)
                copied_models.append(copied)
            copied_app["models"] = copied_models
            decorated_apps.append(copied_app)
        decorated.append({**group, "apps": decorated_apps})
    configured = getattr(settings, "NOVA_ADMIN_NAV_COMMON_MODELS", ())
    common, seen = [], set()
    if isinstance(configured, (list, tuple)):
        for key in configured[:MAX_SHORTCUTS]:
            if isinstance(key, str) and key in visible and key not in seen:
                common.append(visible[key])
                seen.add(key)
    return {"groups": decorated, "common": common, "favorites_enabled": favorites,
            "favorites": list(visible.values()) if favorites else []}
