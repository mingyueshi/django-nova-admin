"""Small package-owned icon catalog; configuration can select names, never SVG."""
import json
from importlib.resources import files
import re
from types import MappingProxyType

from django.utils.html import escape, format_html

_catalog = json.loads(files("nova_admin").joinpath("icons.json").read_text(encoding="utf-8"))
ICON_CATEGORIES = MappingProxyType(_catalog["categories"])
ICON_CATALOG = tuple(MappingProxyType(entry) for entry in _catalog["icons"])
ICON_PATHS = MappingProxyType({entry["name"]: entry["path"] for entry in ICON_CATALOG})
ICON_NAMES = tuple(ICON_PATHS)
_PATH_NAMES = {path: name for name, path in ICON_PATHS.items()}
_CLASS_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_-]{0,63}\Z")


def get_icon_path(name, fallback=None):
    """Exact lowercase catalog names only; unknown names use a known fallback."""
    if isinstance(name, str) and name in ICON_PATHS:
        return ICON_PATHS[name]
    return ICON_PATHS.get(fallback) if isinstance(fallback, str) else None


def _classes(value):
    if not isinstance(value, str) or len(value) > 256:
        return ""
    return " ".join(token for token in value.split() if _CLASS_TOKEN.fullmatch(token))


def render_icon(name, css_class="", label="", size=16, *, fallback="grid", base_class="nova-icon"):
    """Render trusted geometry with a narrow, escaped presentation-only API.

    Icons beside text are decorative by default. Supply a plain-text label for
    a standalone informational icon; label the button/link itself for controls.
    """
    path = get_icon_path(name, fallback)
    if path is None:
        return ""
    size = size if type(size) is int and 12 <= size <= 64 else 16
    classes = " ".join(part for part in (base_class, _classes(css_class)) if part)
    # escape() also escapes SafeString input; project HTML is never trusted here.
    accessibility = (format_html('role="img" aria-label="{}"', escape(label))
                     if isinstance(label, str) and label
                     else format_html('{}="{}"', "aria-hidden", "true"))
    return format_html(
        '<svg class="{}" viewBox="0 0 24 24" width="{}" height="{}" fill="none" '
        'stroke="currentColor" stroke-width="1.65" stroke-linecap="round" '
        'stroke-linejoin="round" focusable="false" {}><path d="{}"></path></svg>',
        classes, size, size, accessibility, path,
    )


def render_navigation_icon(path):
    """Compatibility for existing includes: accept only an exact catalog path."""
    name = _PATH_NAMES.get(path) if isinstance(path, str) else None
    return render_icon(name, fallback=None, base_class="nova-nav-icon")
