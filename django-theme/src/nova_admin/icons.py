"""Offline, package-owned icon paths. Host input selects identifiers, never markup."""
from functools import lru_cache
from importlib.resources import files
import json

from django.utils.html import format_html
from django.utils.safestring import mark_safe


@lru_cache(maxsize=1)
def icon_registry():
    return json.loads(files('nova_admin').joinpath('icons.json').read_text(encoding='utf-8'))['icons']


@lru_cache(maxsize=1)
def icon_names():
    return frozenset(icon_registry())


def render_icon(name, size=20, label='', stroke_width=None):
    entry = icon_registry().get(name) if isinstance(name, str) else None
    if entry is None:
        return ''
    try:
        size = int(size) if not isinstance(size, bool) else 20
    except (ValueError, TypeError, OverflowError):
        size = 20
    if size not in {16, 20, 24, 32, 48}:
        size = 20
    try:
        stroke = float(stroke_width) if not isinstance(stroke_width, bool) else 0
    except (ValueError, TypeError, OverflowError):
        stroke = 0
    if not 1 <= stroke <= 3:
        stroke = entry['strokeWidth']
    if entry['stroke'] == 'none':
        stroke = 0
    accessibility = format_html('role="img" aria-label="{}"', label) if isinstance(label, str) and label else mark_safe('aria-hidden="true"')
    # Only the build-time validated, packaged registry is trusted. No caller
    # string is ever used as SVG markup; labels are escaped by format_html.
    return format_html(
        '<svg xmlns="http://www.w3.org/2000/svg" class="nova-icon" '
        'width="{}" height="{}" viewBox="{}" fill="{}" stroke="{}" '
        'stroke-width="{}" stroke-linecap="round" stroke-linejoin="round" {} focusable="false">{}</svg>',
        size, size, entry['viewBox'], entry['fill'], entry['stroke'], stroke, accessibility, mark_safe(entry['body']),
    )
