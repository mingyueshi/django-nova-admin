"""Small cross-version helpers; never replace Django Admin's own templates."""
import json
import re
from collections import Counter

from django import template
from django.utils.crypto import salted_hmac
from django.utils.html import format_html
from django.utils.translation import pgettext

register = template.Library()


@register.simple_tag
def nova_message_groups(messages):
    """Consume current-response messages once, grouping by the real level only."""
    from django.contrib.messages import constants

    labels = {
        constants.DEBUG: ('debug', pgettext('Nova Admin', 'Debug')),
        constants.INFO: ('info', pgettext('Nova Admin', 'Information')),
        constants.SUCCESS: ('success', pgettext('Nova Admin', 'Success')),
        constants.WARNING: ('warning', pgettext('Nova Admin', 'Warning')),
        constants.ERROR: ('error', pgettext('Nova Admin', 'Error')),
    }
    groups = {}
    if messages is not None:
        for message in messages:
            level = getattr(message, 'level', None)
            key, label = labels.get(level, ('other', pgettext('Nova Admin', 'Message')))
            if key not in groups:
                groups[key] = {'key': key, 'label': label, 'messages': []}
            groups[key]['messages'].append(message)
    return list(groups.values())


@register.simple_tag(takes_context=True)
def nova_brand(context):
    """Resolve this AdminSite's identity without mutating the site instance."""
    from nova_admin.branding import brand_initial, normalize_brand_name
    from django.utils.translation import gettext

    config = context.get("nova_admin_branding") or {}
    name = (normalize_brand_name(config.get("name"))
            or normalize_brand_name(context.get("site_header"))
            or normalize_brand_name(context.get("site_title"))
            or gettext("Django administration"))
    return {"name": name, "initial": brand_initial(name)}


@register.simple_tag
def nova_icon(name, size=20, label='', stroke_width=None):
    """Render a bundled namespaced SVG, with an optional accessible label."""
    from nova_admin.icons import render_icon

    return render_icon(name, size=size, label=label, stroke_width=stroke_width)


@register.simple_tag(takes_context=True)
def nova_navigation_extensions(context):
    """Call optional bulk hooks once for this permission-filtered sidebar."""
    from nova_admin.navigation import extend_navigation

    return extend_navigation(nova_navigation_groups(context), context.get("request"))


@register.simple_tag(takes_context=True)
def nova_navigation_scope(context, site_index):
    """Opaque per-site/user preference scope, never an authorization token."""
    user = context.get("user")
    if not user or not user.is_authenticated or user.pk is None:
        return ""
    payload = json.dumps([str(site_index), user._meta.label_lower, str(user.pk)])
    return salted_hmac("nova_admin.navigation", payload, algorithm="sha256").hexdigest()


@register.simple_tag(takes_context=True)
def nova_nonce(context):
    """Honor Django 6.x CSP context without requiring 6.x tags on Django 5.2."""
    nonce = context.get("csp_nonce")
    return format_html('nonce="{}"', nonce) if nonce is not None else ""


@register.simple_tag(takes_context=True)
def nova_navigation_groups(context):
    """Organize only the AdminSite-provided permission-filtered applications.

    No model/site lookup, extra queries, permission changes or context mutation.
    Unknown/empty groups disappear; each visible app is assigned at most once.
    """
    from django.conf import settings

    available = context.get("available_apps") or []
    apps = []
    seen = set()
    for app in available:
        if not isinstance(app, dict):
            continue
        label = app.get("app_label")
        if isinstance(label, str) and label and app.get("models") and label not in seen:
            apps.append(app)
            seen.add(label)
    config = getattr(settings, "NOVA_ADMIN_NAV_GROUPS", None)
    if not isinstance(config, (list, tuple)) or not config:
        return [{"label": None, "apps": apps}] if apps else []
    by_label = {app["app_label"]: app for app in apps}
    assigned = set()
    groups = []
    # Count before permissions filter groups so a duplicate never changes owner.
    key_counts = Counter(
        group.get("key") for group in config
        if isinstance(group, dict) and isinstance(group.get("key"), str)
    )
    for group in config:
        if not isinstance(group, dict):
            continue
        label = group.get("label")
        members = group.get("apps")
        if not isinstance(label, str) or not label.strip() or not isinstance(members, (list, tuple)):
            continue
        visible = []
        for member in members:
            if isinstance(member, str) and member in by_label and member not in assigned:
                visible.append(by_label[member])
                assigned.add(member)
        if visible:
            result = {"label": label.strip(), "apps": visible}
            key = group.get("key")
            if (isinstance(key, str) and
                    re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}", key) and
                    key_counts[key] == 1):
                result["key"] = key
            groups.append(result)
    remaining = [app for app in apps if app["app_label"] not in assigned]
    if remaining:
        groups.append({"label": pgettext("Nova Admin", "Other apps"), "apps": remaining})
    return groups
