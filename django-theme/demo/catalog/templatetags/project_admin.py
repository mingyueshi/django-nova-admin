"""Explicit demo template integration with Django's native admin helpers."""
from copy import copy

import django
from django import template
from django.utils.html import format_html

from catalog.forms import chinese_admin, chinese_label

register = template.Library()
register.filter("project_label", chinese_label)


@register.simple_tag(takes_context=True)
def project_nonce(context):
    """Preserve CSP without a template-tag dependency on the removable theme."""
    nonce = context.get("csp_nonce")
    return format_html('nonce="{}"', nonce) if nonce is not None else ""


@register.simple_tag
def project_admin_template(kind):
    """Keep each supported Django minor's fieldset markup and accessibility."""
    version = django.VERSION[:2]
    supported = {(5, 2): "52", (6, 0): "60", (6, 1): "61"}
    if version not in supported or kind not in {"fieldset", "tabular"}:
        raise template.TemplateSyntaxError("Unsupported project admin template version or kind")
    suffix = supported[version]
    if kind == "tabular" and suffix == "61":
        suffix = "60"  # The installed 6.0 and 6.1 native templates are identical.
    return f"project_admin/{kind}_{suffix}.html"


@register.simple_tag
def project_label_tag(field):
    if not chinese_admin() or not field.is_readonly:
        return field.label_tag()
    # Readonly fields bypass BoundField and its form renderer. Copy the helper
    # and form so the original object, field data and other labels stay intact.
    localized = copy(field)
    localized.field = {**field.field, "label": chinese_label(field.field["label"])}
    localized.form = copy(field.form)
    localized.form.label_suffix = ""
    return localized.label_tag()
