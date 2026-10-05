# Native admin density and appearance

Nova 0.3.0 exposes CSS variables on `body.nova-admin`. They change the existing
Django changelist, forms, inline formsets, and controls. No replacement list,
JavaScript density switch, ModelAdmin override, or third-party dependency is
required.

## Load a project preset after Nova

Put the following in your project's own static file, for example
`static/admin/compact.css`. Include it after `nova_admin/theme.css`, and only
when `nova_admin_active` is true. A project template in your configured
`TEMPLATES[0]["DIRS"]` can extend `admin/base.html` and use:

```django
{% extends "admin/base.html" %}
{% load static %}
{% block extrastyle %}
  {{ block.super }}
  {% if nova_admin_active %}
    <link rel="stylesheet" href="{% static 'admin/compact.css' %}">
  {% endif %}
{% endblock %}
```

Use the existing project's nonce policy if it requires a nonce on stylesheet
links. Keep the Nova app before `django.contrib.admin` in `INSTALLED_APPS`.

```css
/* Project compact preset; loaded after Nova and any project palette. */
body.nova-admin {
  --nova-cell-padding: 8px 12px;
  --nova-row-line-height: 1.4;
  --nova-form-row-padding: 12px 14px;
  --nova-control-padding-block: 6px;
  --nova-control-padding-inline: 10px;
  --nova-control-min-height: 34px;
  --nova-action-padding: 8px 12px;
  --nova-section-padding: 10px 14px;
}
```

| Variable | Core default | Affects |
| --- | --- | --- |
| `--nova-cell-padding` | `13px 16px` | Native list and dashboard cells, sortable header text, tabular inline cells |
| `--nova-row-line-height` | `1.5` | Table cell text line height |
| `--nova-form-row-padding` | `18px 16px` | Native form rows, including stacked inlines |
| `--nova-control-padding-block` | `9px` | Native input/select padding and related links |
| `--nova-control-padding-inline` | `11px` | Input/select horizontal padding; dropdown arrow space is retained |
| `--nova-control-min-height` | `40px` | Native single-line controls, Select2 selection, related links, save/actions |
| `--nova-action-padding` | `11px 17px` | Save/delete/cancel buttons and object/action tools |
| `--nova-section-padding` | `14px 16px` | Module headings, action/pagination bands, inline add rows |

Padding accepts normal CSS shorthand. Heights are minima: multi-line labels,
validation text, thumbnails, and widgets can require taller rows. Existing inline
object labels retain Django's reserved top space (`2em`). Multi-select listboxes
retain their native row count. Select2's hidden source select stays untouched.

At widths up to 767px or with a coarse pointer, text/select/save/action controls
have a 44px minimum. Native checkboxes and radios have a 24px minimum; explicit
Nova switches retain their 40×24 horizontal shape. Save, bulk actions, list selection,
inline deletion, related links, and autocomplete options remain operable in a
compact preset. These touch targets are intentionally independent of the
project's smaller density values. Do not override the internal
`--nova-touch-min` token to reduce them. Check long translations, custom widgets,
and your actual mobile layouts when adding a project override.

## Project default versus saved preference

The library still defaults to dark. An enterprise project can start in light:

```python
NOVA_ADMIN_DEFAULT_MODE = "light"
```

Allowed values are `dark`, `light`, `auto`, and `native`. A valid saved session
choice wins over the project default. Applying a choice uses the existing
CSRF-protected POST endpoint guarded by the mounted AdminSite. Return URLs stay
inside that site's admin prefix. Changing this setting does not reset existing
sessions or alter permissions.

Auto is an explicit Nova appearance choice. It uses Nova's light palette by
default and the matching dark palette when `prefers-color-scheme: dark` matches.
The CSS reacts to OS appearance changes without JavaScript. Explicit Nova light
and dark do not react to that query. Nova doesn't rewrite Django's independent
`html[data-theme]` or native localStorage preference. The Auto label is an
English source string with `Nova Admin` translation context and a shipped
Simplified Chinese PO/MO translation.

When adding project colors, cover the same four selectors:

```css
body.nova-admin.nova-mode-light,
body.nova-admin.nova-mode-auto { /* project light tokens */ }
body.nova-admin.nova-mode-dark { /* project dark tokens */ }
@media (prefers-color-scheme: dark) {
  body.nova-admin.nova-mode-auto { /* the same project dark tokens */ }
}
```

Set all changed palette tokens for both appearances. Test contrast for body,
muted, link, and button text against their actual backgrounds. Nova's core light
and dark contrast pairs are covered by tests; custom project palettes need their
own checks.

## Chinese headings and native fallback

Negative letter spacing is removed from the site title and content headings
whose effective language matches `:lang(zh-hans)`. An English heading marked
`lang="en"` keeps English tracking, even on a Chinese page. Translation and label
punctuation remain Django/project responsibilities.

Native appearance loads no Nova stylesheet or script. Global disable, removing
the Nova app, or omitting the context processor also degrades to Django's native
admin. Keep project style links inside the `nova_admin_active` check so your
custom palette/density follows the same reversible boundary.

## Verification

`tests/test_density_auto.py` checks preference precedence, Auto CSRF and site
boundaries, native fallback asset absence, a real list-editable checkbox/save
round trip with the Django audit log, native inline/save controls, compiled
translation, palette contrast, language selectors, and density/touch contracts.
These server-side and source-contract tests do not replace browser geometry and
keyboard QA for project-specific CSS.
