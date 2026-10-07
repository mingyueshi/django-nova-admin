"""Optional metadata for native AdminSite navigation, with no registry or queries."""
from copy import deepcopy
import logging

from django.conf import settings
from django.utils.module_loading import import_string

# Retained public import for projects using the original navigation catalog.
from .icons import ICON_PATHS, get_icon_path

logger = logging.getLogger(__name__)
MAX_SHORTCUTS = 50


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
            copied_app = {**app, "nova_icon_path": get_icon_path(icon)}
            copied_models = []
            for model in app["models"]:
                if not isinstance(model, dict):
                    continue
                object_name = model.get("object_name")
                key = f"{app_key}.{object_name.lower()}" if isinstance(object_name, str) else ""
                icon = provided_icons.get(key, icons.get(key))
                badge = badges.get(key)
                copied = {**model, "nova_key": key,
                          "nova_icon_path": get_icon_path(icon),
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
