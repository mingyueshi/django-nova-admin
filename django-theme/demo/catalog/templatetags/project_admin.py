"""Explicit demo template integration with Django's native admin helpers."""
from copy import copy
from hashlib import sha256
from importlib.resources import files

from django import template
from django.utils.html import format_html

from catalog.forms import chinese_admin, chinese_label

register = template.Library()
register.filter("project_label", chinese_label)


# Full native-template signatures, reviewed alongside ci/template-baselines.json.
# Versions document provenance only; installed template content selects the adapter.
_REVIEWED_ADMIN_TEMPLATES = {
    "fieldset": ("includes/fieldset.html", {
        # Django 5.2.17, 6.0.8 and 6.1.1 respectively.
        "2d7ffc5f076e04ca370e640db8668ad2da0b328567b0c74c89a64e7c6fb353a9": "project_admin/fieldset_52.html",
        "c38e10942a0c43c967008822d9b2d60dea13ff1eac641dfc26f45045ec7f3fbb": "project_admin/fieldset_60.html",
        "cdcfa96ca6b4672d417f204f48aee1a176bfcf35891f187b7599246162a6f594": "project_admin/fieldset_61.html",
    }),
    "tabular": ("edit_inline/tabular.html", {
        # Django 5.2.17; the reviewed 6.0.8 and 6.1.1 templates are identical.
        "ef1b0d9b50be1e24e18f44c96571af7070202de3816eeb9746318c8aa5d6f1f7": "project_admin/tabular_52.html",
        "c86c726f3adcd10d5fdd82c6612977cf5f06338aecd08b4f7ee132b43b5dbbdc": "project_admin/tabular_60.html",
    }),
}


def _native_admin_template(relative_path):
    # Read the installed Django package directly, not our same-name overrides.
    # Recheck its content so a changed template cannot reuse a stale match.
    source = files("django.contrib.admin").joinpath("templates", "admin", relative_path)
    try:
        return source.read_text(encoding="utf-8"), str(source)
    except (OSError, UnicodeError) as error:
        raise template.TemplateSyntaxError(
            f"Cannot inspect native Django admin template admin/{relative_path} "
            f"at {source}: {error}"
        ) from error


@register.simple_tag(takes_context=True)
def project_nonce(context):
    """Preserve CSP without a template-tag dependency on the removable theme."""
    nonce = context.get("csp_nonce")
    return format_html('nonce="{}"', nonce) if nonce is not None else ""


@register.simple_tag
def project_admin_template(kind):
    """Choose only a reviewed native markup match, independently of its version."""
    if not isinstance(kind, str) or kind not in _REVIEWED_ADMIN_TEMPLATES:
        raise template.TemplateSyntaxError(
            f"Unknown project admin template kind {kind!r}; expected fieldset or tabular"
        )
    relative_path, reviewed = _REVIEWED_ADMIN_TEMPLATES[kind]
    native, origin = _native_admin_template(relative_path)
    signature = sha256(native.encode("utf-8")).hexdigest()
    adapter = reviewed.get(signature)
    if adapter is None:
        raise template.TemplateSyntaxError(
            f"Unreviewed native Django admin template admin/{relative_path} "
            f"at {origin}; sha256={signature}. Review the upstream change and "
            "its project_admin adapter before adding a signature; see UPSTREAM_DRIFT.md."
        )
    return adapter


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
