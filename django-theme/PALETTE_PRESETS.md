# Independent appearance and palette presets

The appearance form has two independent, translated selects:

- Mode: `dark`, `light`, `auto`, `native` (existing behavior).
- Palette: `default`, `teal` (医疗青), `indigo` (专业靛), `violet` (文教紫), `terracotta` (零售陶), `graphite` (石墨黑), `midnight` (午夜蓝).

These industry-oriented names describe demonstration positioning only, not
industry standards or a requirement for a particular kind of organization.

Graphite black uses neutral charcoal surfaces; Midnight blue uses deep navy
surfaces. Select either palette together with `dark`, or use `auto` to follow
the system. Both also have light accent counterparts: selecting a palette never
changes the appearance preference. Their dark backgrounds cover the workspace,
sidebar, cards, form controls and login page.

`NOVA_ADMIN_DEFAULT_PALETTE = "default"` is optional. A valid saved session
preference (`nova_admin_palette`) overrides it. Unknown settings and malformed
session values fall back safely. The default palette makes no CSS declarations:
the reusable package retains its original purple accents and green Save button;
the demo retains its enterprise blue. Choosing “Project default / 项目默认” restores
that baseline. Palette selection survives switching to native and back.

The existing `for_admin()` POST endpoint accepts `mode` and optional `palette`.
Old mode-only clients keep their palette unchanged. Both supplied values are
validated before either session value is written: an invalid pair returns HTTP
400 without a partial update. CSRF, the exact AdminSite's `admin_view`, POST-only
handling and safe local return-path checks remain unchanged. A palette-only POST
is invalid because `mode` remains required. This endpoint does not alter auth,
permissions, model registration, Django's theme storage, or navigation storage.

## CSS contract and host overrides

Load order is `theme.css` → `tokens.css` → `presets.css` → host CSS. The new file
is package data and included by the existing `nova_styles` block. If a host
replaces that block rather than extending it, include all three files. Native
mode and global disable load none of them, nor demo enterprise styles.

Each non-default body palette class sets the existing four `--nova-brand-*`
variables. It also supplies light/dark selection and row colors; these map to
Django's `--selected-bg`, `--selected-row` and Nova's `--nova-hover`. `auto` follows
the OS with the existing media-query model. Semantic error, warning, success and
destructive-action colors remain unchanged.

Graphite and Midnight additionally define `--nova-surface-dark-*` tokens for
background, sidebar, panel, raised panel, text, secondary text, border and tool
roles. Their mappings apply only in `dark` and `auto` with a dark system
preference. Later host mode rules can override these mappings just like the
existing selection roles. Native mode and global disable omit the preset sheet.

Preset brand declarations use `body.nova-admin:where(.nova-palette-teal)` (and
its sibling names), so a later `body.nova-admin` brand override wins. Selection
role mappings use the same specificity as Nova's existing mode rules. Override
these using a later `body.nova-admin.nova-mode-light` / `nova-mode-dark` /
`nova-mode-auto` rule, including an auto dark media rule when needed. No
`!important` or cascade layer prevents host control.

In the demo, the enterprise brand colors are scoped to the default palette,
while its existing role mappings consume the selected brand variables. Its
selection/hover declarations now use preset variables with exact old values as
fallbacks. This preserves the blue baseline without hiding a chosen preset.

## Validation

The new `tests.test_palette_presets` suite covers every mode/palette pair,
configured and malformed defaults/session values, default restoration,
mode-only compatibility, invalid-pair atomicity, CSRF, safe return paths,
translated labels/errors, CSS order, and native/disabled asset removal. Run
alongside the existing AdminSite, permissions, navigation, login, and native
workflow tests:

```sh
cd django-theme
python -m venv /tmp/nova-palette-venv
/tmp/nova-palette-venv/bin/pip install Django==5.2.17 beautifulsoup4==4.15.0
PYTHONPATH=src:demo:. /tmp/nova-palette-venv/bin/python demo/manage.py test tests --noinput
```

The Chinese `.po` and packaged `.mo` catalog are both updated. To regenerate the
latter without GNU gettext: install `polib==1.2.0`, then use `polib.pofile(path)`
and `save_as_mofile()`; it is a build-time helper, not a runtime dependency.

Verified in isolated Python 3.12.14 environments against Django 5.2.17 and
6.1.1: 327 tests, all passing; two expected skips are the optional CAPTCHA and
Axes integrations. No database persists after the test run. Browser/visual
verification is separate from this server-side suite.
