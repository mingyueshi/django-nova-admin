"""Actionable opt-in integration warnings; optional endpoints stay optional."""
from django.conf import settings
from django.core.checks import Tags, Warning, register
from django.urls import NoReverseMatch, get_resolver, reverse

from .navigation import ICON_NAMES, MAX_SHORTCUTS, resolve_provider


def _site_paths(resolver, site, prefix=""):
    for name, (_, child) in resolver.namespace_dict.items():
        path = f"{prefix}:{name}" if prefix else name
        if name == site:
            yield path
        yield from _site_paths(child, site, path)


@register(Tags.templates)
def theme_context_check(app_configs, **kwargs):
    if not getattr(settings, "NOVA_ADMIN_ENABLED", True):
        return []
    engines = [engine for engine in settings.TEMPLATES
               if engine.get("BACKEND") == "django.template.backends.django.DjangoTemplates"]
    if engines and all("nova_admin.context_processors.theme" in engine.get("OPTIONS", {}).get("context_processors", ())
                       for engine in engines):
        return []
    return [Warning(
        "Nova Admin's theme context processor is missing.",
        hint="Add 'nova_admin.context_processors.theme' to the DjangoTemplates context_processors used by admin.",
        id="nova_admin.W001",
    )]


@register(Tags.urls)
def theme_namespace_check(app_configs, **kwargs):
    if not getattr(settings, "NOVA_ADMIN_ENABLED", True) or not hasattr(settings, "NOVA_ADMIN_URL_NAMESPACES"):
        # An unmounted preference endpoint is supported and intentionally quiet.
        return []
    namespaces = settings.NOVA_ADMIN_URL_NAMESPACES
    if not isinstance(namespaces, dict):
        return [Warning(
            "NOVA_ADMIN_URL_NAMESPACES must be a dictionary of AdminSite names to theme URL namespaces.",
            hint="Use {} to omit preference controls, or map each mounted site to its for_admin() include namespace.",
            id="nova_admin.W002",
        )]
    warnings = []
    for site, namespace in namespaces.items():
        valid = all(isinstance(value, str) and value.strip() and all(value.split(":"))
                    for value in (site, namespace))
        if valid:
            # The runtime accepts a bare AdminSite.name inside a surrounding
            # namespace; inspect URL namespaces, never the admin model registry.
            candidates = [site] if ":" in site else [site, *_site_paths(get_resolver(), site)]
            valid = False
            for candidate in candidates:
                try:
                    reverse(f"{candidate}:index", current_app=candidate)
                    reverse(f"{namespace}:preference", current_app=candidate)
                except NoReverseMatch:
                    continue
                valid = True
                break
        if not valid:
            warnings.append(Warning(
                "A NOVA_ADMIN_URL_NAMESPACES entry cannot resolve its AdminSite index and preference endpoint.",
                hint="Check the existing AdminSite.name and include(for_admin(site), namespace=...). Use full nested namespaces when needed; remove intentionally unmounted entries.",
                obj=f"NOVA_ADMIN_URL_NAMESPACES[{site!r}]", id="nova_admin.W002",
            ))
    return warnings


@register(Tags.templates)
def navigation_settings_check(app_configs, **kwargs):
    if not getattr(settings, "NOVA_ADMIN_ENABLED", True):
        return []
    problems = []
    if not isinstance(getattr(settings, "NOVA_ADMIN_NAV_FAVORITES", False), bool):
        problems.append("NOVA_ADMIN_NAV_FAVORITES must be True or False.")
    common = getattr(settings, "NOVA_ADMIN_NAV_COMMON_MODELS", ())
    if (not isinstance(common, (list, tuple)) or len(common) > MAX_SHORTCUTS or
            any(not isinstance(key, str) or len(key.split(".")) != 2 or not all(key.split("."))
                for key in common)):
        problems.append("NOVA_ADMIN_NAV_COMMON_MODELS must contain at most 50 'app_label.model_name' strings.")
    icons = getattr(settings, "NOVA_ADMIN_NAV_ICONS", {})
    if (not isinstance(icons, dict) or any(
            not isinstance(key, str) or not key or not isinstance(icon, str) or icon not in ICON_NAMES
            for key, icon in icons.items())):
        problems.append("NOVA_ADMIN_NAV_ICONS must map app/model keys to a supported built-in or namespaced icon name.")
    for name in ("NOVA_ADMIN_NAV_ICON_PROVIDER", "NOVA_ADMIN_NAV_BADGE_PROVIDER"):
        value = getattr(settings, name, None)
        if value is not None and resolve_provider(value) is None:
            problems.append(f"{name} must be a callable or an importable dotted callable path.")
    return [Warning(problem, hint="See NAVIGATION_EXTENSIONS.md; malformed values are ignored at render time.",
                    id="nova_admin.W003") for problem in problems]
