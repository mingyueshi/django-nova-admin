#!/usr/bin/env python3
"""Measure authored opaque palette roles; this is not a browser/WCAG audit.

The deliberately small resolver supports the root/body selectors, custom properties,
var() fallbacks, and color-scheme media queries used by these stylesheets. It does
not model descendant rules, rendered blending, host overrides, or layout.
"""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PALETTES = ('teal', 'indigo', 'violet', 'terracotta', 'graphite', 'midnight', 'forest', 'amber')
SURFACE_PALETTES = ('graphite', 'midnight', 'forest', 'amber')
SURFACE_NAMES = ('bg', 'sidebar', 'panel', 'panel2', 'text', 'muted', 'medium',
                 'line', 'border', 'tool', 'tool-hover')
DJANGO_SURFACES = {
    '--body-bg': 'bg', '--nova-panel': 'panel', '--darkened-bg': 'sidebar',
    '--nova-neutral-bg': 'panel2', '--secondary': 'panel', '--header-bg': 'panel',
    '--body-fg': 'text', '--body-quiet-color': 'muted', '--body-medium-color': 'medium',
    '--hairline-color': 'line', '--border-color': 'border',
    '--body-loud-color': 'text', '--header-color': 'text', '--header-branding-color': 'text',
    '--breadcrumbs-bg': 'bg', '--breadcrumbs-fg': 'muted',
    '--primary-fg': 'bg', '--button-fg': 'bg', '--object-tools-fg': 'text',
    '--close-button-bg': 'tool', '--close-button-hover-bg': 'tool-hover',
    '--object-tools-bg': 'tool', '--object-tools-hover-bg': 'tool-hover',
}
PREVIEW_SURFACES = {f'--{name}': name for name in
                    ('bg', 'sidebar', 'panel', 'panel2', 'text', 'muted', 'line')}
LOGIN_SURFACES = {name: role for name, role in DJANGO_SURFACES.items() if name in
                  ('--body-bg', '--nova-panel', '--darkened-bg', '--body-fg',
                   '--body-quiet-color', '--body-loud-color', '--hairline-color', '--border-color', '--button-fg')}
ROOT_COLOR_NAMES = set(DJANGO_SURFACES) | set(PREVIEW_SURFACES) | {
    '--link-fg', '--link-hover-color', '--selected-bg', '--selected-row',
    '--button-bg', '--button-hover-bg', '--default-button-bg', '--default-button-hover-bg',
    '--accent', '--accent-bg', '--palette-row', '--palette-hover', '--danger', '--error-fg',
}
SCOPE = ('Authored opaque links, hover links, primary/default/save buttons, brand marks, '
         'selected navigation, body/secondary/row text, errors on row, focus rings, '
         'dark object tools and new dark control boundaries across Django, static preview and static login. '
         'Checks root/body token cascades and Django explicit/auto parity, not runtime '
         'layout or rendered blending. Static auto is resolved to data-theme by JavaScript '
         'and requires browser verification. Host overrides, disabled opacity, chart series, '
         'translucent effects and unchanged semantic status treatments need visual review.')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def ratio(a, b):
    def luminance(color):
        channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in channels]
        return sum(c * weight for c, weight in zip(linear, (.2126, .7152, .0722)))
    x, y = sorted((luminance(a), luminance(b)))
    return (y + .05) / (x + .05)


def split_selectors(value):
    """Split a selector list without splitting :where()/:not() arguments."""
    start = depth = 0
    for index, char in enumerate(value):
        if char in '([':
            depth += 1
        elif char in ')]':
            depth -= 1
        elif char == ',' and depth == 0:
            yield value[start:index].strip()
            start = index + 1
    yield value[start:].strip()


def matching_end(value, start, opening, closing):
    depth = 0
    for index in range(start, len(value)):
        if value[index] == opening:
            depth += 1
        elif value[index] == closing:
            depth -= 1
            if depth == 0:
                return index
    raise ValueError(f'Unclosed {opening} in authored CSS')


def selector_match(selector, element):
    """Return match and specificity for a supported single root/body compound."""
    remaining = selector.strip()
    specificity = 0
    matched = True
    while remaining:
        function = re.match(r':(where|is|not)\(', remaining)
        if function:
            end = matching_end(remaining, function.end() - 1, '(', ')')
            choices = [selector_match(part, element) for part in
                       split_selectors(remaining[function.end():end])]
            has_match = any(match for match, _ in choices)
            matched &= not has_match if function[1] == 'not' else has_match
            if function[1] != 'where':
                specificity += max(score for _, score in choices)
            remaining = remaining[end + 1:]
            continue
        token = re.match(r':root|\.[\w-]+|\[[\w-]+(?:=["\']?[\w-]+["\']?)?\]|[\w-]+', remaining)
        if not token:
            # Descendants, pseudo-elements, and component/state selectors do not
            # select the root/body whose inherited variables are measured here.
            if matched and remaining.startswith(':'):
                raise ValueError(f'Unsupported root/body selector: {selector}')
            return False, 0
        value = token[0]
        if value == ':root':
            matched &= element['tag'] == 'html'
            specificity += 10
        elif value.startswith('.'):
            matched &= value[1:] in element['classes']
            specificity += 10
        elif value.startswith('['):
            attribute, _, expected = value[1:-1].partition('=')
            matched &= attribute in element['attributes']
            if expected:
                matched &= element['attributes'].get(attribute) == expected.strip('"\'')
            specificity += 10
        else:
            matched &= value == element['tag']
            specificity += 1
        remaining = remaining[len(value):]
    return matched, specificity


def has_scoped_colors(css):
    for selector, block in re.findall(r'([^{}]+)\{([^{}]*)\}', css):
        if ':root' not in selector and 'body' not in selector:
            continue
        names = re.findall(r'(--[\w-]+)\s*:', block)
        if any(name in ROOT_COLOR_NAMES or name.startswith(('--nova-brand-', '--nova-surface-',
                                                            '--nova-palette-')) for name in names):
            return True
    return False


def rules(css, dark_os, active=True):
    """Yield declarations in source order, recursing into color-scheme media."""
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    position = 0
    while True:
        start = css.find('{', position)
        if start == -1:
            return
        end = matching_end(css, start, '{', '}')
        selector = css[position:start].strip()
        block = css[start + 1:end]
        if selector.startswith('@media'):
            query = re.fullmatch(r'@media\s*\(prefers-color-scheme:\s*(dark|light)\)', selector)
            if query:
                enabled = dark_os == (query[1] == 'dark')
                yield from rules(block, dark_os, active and enabled)
            elif has_scoped_colors(block):
                raise ValueError(f'Unsupported media query contains root/body color tokens: {selector}')
        elif selector.startswith('@'):
            require(not has_scoped_colors(block),
                    f'Unsupported at-rule contains root/body color tokens: {selector}')
        elif active:
            properties = re.findall(r'(--[\w-]+)\s*:\s*([^;{}]+)', block)
            if properties:
                yield selector, properties
        position = end + 1


def effective_properties(stylesheets, palette, mode, surface, dark_os=False):
    element = dict(tag='body' if surface == 'django' else 'html',
                   classes={'nova-admin', f'nova-mode-{mode}', f'nova-palette-{palette}'},
                   attributes={'data-theme': mode, 'data-palette': palette})
    properties, priority = {}, {}
    for order, (selector_list, values) in enumerate(rules('\n'.join(stylesheets), dark_os)):
        selectors = [selector_match(selector, element) for selector in split_selectors(selector_list)]
        scores = [specificity for matched, specificity in selectors if matched]
        if not scores:
            continue
        for name, value in values:
            important = bool(re.search(r'!\s*important$', value))
            rank = (important, max(scores), order)
            if name not in priority or rank >= priority[name]:
                properties[name] = re.sub(r'!\s*important$', '', value).strip()
                priority[name] = rank
    return properties


def color(properties, name, stack=()):
    require(name not in stack, f'Cyclic custom property: {name}')
    require(name in properties, f'Missing custom property: {name}')
    value = properties[name].strip().lower()
    variable = re.fullmatch(r'var\((--[\w-]+)(?:,\s*(.+))?\)', value)
    if variable:
        if variable[1] in properties:
            return color(properties, variable[1], stack + (name,))
        require(variable[2] is not None, f'Unresolved custom property: {name} -> {variable[1]}')
        value = variable[2]
    if re.fullmatch(r'#[0-9a-f]{3}', value):
        value = '#' + ''.join(char * 2 for char in value[1:])
    require(re.fullmatch(r'#[0-9a-f]{6}', value), f'{name} is not an opaque hex color: {value}')
    return value


def audit():
    nova = ROOT / 'django-theme/src/nova_admin/static/nova_admin'
    palette_css = (nova / 'presets.css').read_text()
    static_palette_css = (ROOT / 'dist/presets.css').read_text()
    stylesheets = {
        'django': [(nova / filename).read_text() for filename in ('theme.css', 'tokens.css')] + [palette_css],
        'preview': [(ROOT / 'dist/styles.css').read_text(), static_palette_css],
        'login': [(ROOT / 'dist/login-preview.css').read_text(), static_palette_css],
    }
    roles = []
    for key in PALETTES:
        for mode in ('light', 'dark'):
            props = {surface: effective_properties(sheets, key, mode, surface, mode == 'dark')
                     for surface, sheets in stylesheets.items()}
            django, preview, login = (props[surface] for surface in ('django', 'preview', 'login'))
            brand, hover = (color(django, '--nova-brand-' + mode + suffix) for suffix in ('', '-hover'))
            selected, row = (color(django, '--nova-palette-' + name + '-' + mode)
                             for name in ('selected', 'row'))
            expected = {'--nova-brand-' + mode: brand, '--nova-brand-' + mode + '-hover': hover,
                        '--nova-brand-selection-' + mode: selected, '--nova-brand-row-' + mode: row}
            for name, value in expected.items():
                require(color(preview, name) == value, f'{key}/{mode}: Django/static mismatch for {name}')
            # Resolve the public roles too: merely declaring correct palette tokens
            # must not mask a missing mode selector or a stale fallback surface.
            for surface, expected_roles in {
                'django': {'--link-fg': brand, '--link-hover-color': hover,
                           '--button-bg': brand, '--button-hover-bg': hover,
                           '--default-button-bg': brand, '--default-button-hover-bg': hover,
                           '--selected-bg': selected, '--selected-row': row},
                'preview': {'--accent': brand, '--accent-bg': selected, '--palette-row': row,
                            '--palette-hover': hover},
                'login': {'--link-fg': brand, '--button-bg': brand, '--button-hover-bg': hover},
            }.items():
                for name, value in expected_roles.items():
                    require(color(props[surface], name) == value,
                            f'{key}/{mode}/{surface}: {name} does not resolve to its palette token')
            for surface, sheets in stylesheets.items():
                require(props[surface] == effective_properties(sheets, key, mode, surface, mode != 'dark'),
                        f'{key}/{surface}: explicit {mode} changes with the OS theme')
            for dark_os in (False, True):
                automatic = effective_properties(stylesheets['django'], key, 'auto', 'django', dark_os)
                explicit = effective_properties(stylesheets['django'], key,
                                                'dark' if dark_os else 'light', 'django', dark_os)
                require(automatic == explicit,
                        f'{key}: Django auto differs from explicit {"dark" if dark_os else "light"}')
            if key in SURFACE_PALETTES:
                for name in SURFACE_NAMES:
                    token = '--nova-surface-dark-' + name
                    require(color(django, token) == color(preview, token),
                            f'{key}: Django/static mismatch for {token}')
                if mode == 'dark':
                    for surface, mapping in (('django', DJANGO_SURFACES),
                                             ('preview', PREVIEW_SURFACES), ('login', LOGIN_SURFACES)):
                        for name, role in mapping.items():
                            require(color(props[surface], name) == color(props[surface], '--nova-surface-dark-' + role),
                                    f'{key}/{surface}: {name} ignores its dark surface token')
                else:
                    for surface, mapping in (('django', DJANGO_SURFACES),
                                             ('preview', PREVIEW_SURFACES), ('login', LOGIN_SURFACES)):
                        baseline = effective_properties(stylesheets[surface], 'teal', 'light', surface)
                        for name in mapping:
                            require(color(props[surface], name) == color(baseline, name),
                                    f'{key}/{surface}: dark surface override leaks into light mode: {name}')

            def add(role, fg, bg, threshold=4.5):
                value = ratio(fg, bg)
                roles.append(dict(palette=key, mode=mode, role=role, foreground=fg,
                                  background=bg, contrast=round(value, 3), minimum=threshold,
                                  passed=value >= threshold))

            surfaces = {name: color(django, '--' + name)
                        for name in ('body-bg', 'nova-panel', 'darkened-bg', 'nova-neutral-bg')}
            surfaces.update(selected=selected, row=row)
            for name, bg in surfaces.items():
                add('Django link / ' + name, brand, bg)
                add('Django hover link / ' + name, hover, bg)
                add('Django focus ring / ' + name, brand, bg, 3)
                for role in ('body-fg', 'body-quiet-color', 'body-medium-color'):
                    add('Django ' + role + ' / ' + name, color(django, '--' + role), bg)
            for state in ('', '-hover'):
                for kind in ('button', 'default-button'):
                    add('Django ' + kind + state, color(django, '--button-fg'), color(django, '--' + kind + state + '-bg'))
            # Keep prior generic/demo foreground checks: consumers use these
            # existing foregrounds for their opaque buttons and brand marks.
            for fg in (['#ffffff'] if mode == 'light' else ['#0b1020', '#102036', '#191527', '#191525']):
                add('button or brand mark', fg, brand)
                add('button hover', fg, hover)
            static_surfaces = {name: color(preview, '--' + name) for name in ('bg', 'sidebar', 'panel', 'panel2')}
            for name, bg in dict(static_surfaces, selected=selected, row=row).items():
                add('preview active link/icon / ' + name, brand, bg)
                add('preview focus ring / ' + name, brand, bg, 3)
                for role in ('text', 'muted'):
                    add('preview ' + role + ' / ' + name, color(preview, '--' + role), bg)
            add('preview row error', color(preview, '--danger'), row)
            add('Django row error', color(django, '--error-fg'), row)
            for name in ('body-bg', 'nova-panel', 'darkened-bg'):
                bg = color(login, '--' + name)
                for role in ('body-fg', 'body-quiet-color', 'link-fg', 'error-fg'):
                    add('login ' + role + ' / ' + name, color(login, '--' + role), bg)
                add('login focus ring / ' + name, color(login, '--button-bg'), bg, 3)
            add('login button / brand mark', color(login, '--button-fg'), color(login, '--button-bg'))
            add('login button hover', color(login, '--button-fg'), color(login, '--button-hover-bg'))
            if mode == 'dark' and key in SURFACE_PALETTES:
                for name in ('body-bg', 'nova-panel', 'darkened-bg'):
                    add('Django control boundary / ' + name, color(django, '--border-color'),
                        color(django, '--' + name), 3)
                add('preview control boundary', color(preview, '--nova-surface-dark-border'),
                    color(preview, '--panel2'), 3)
                add('login control boundary', color(login, '--border-color'),
                    color(login, '--darkened-bg'), 3)
            if mode == 'dark':
                for state in ('', '-hover'):
                    add('Django object tools' + state, color(django, '--object-tools-fg'),
                        color(django, '--object-tools' + state + '-bg'))
    return {'scope': SCOPE, 'checks': len(roles), 'passed': all(x['passed'] for x in roles),
            'minimum_measured': min(x['contrast'] for x in roles),
            'minimum_text_contrast': min(x['contrast'] for x in roles if x['minimum'] == 4.5),
            'minimum_non_text_contrast': min(x['contrast'] for x in roles if x['minimum'] == 3),
            'roles': roles}


def main():
    try:
        result = audit()
    except ValueError as error:
        result = {'scope': SCOPE, 'passed': False, 'error': str(error)}
    print(json.dumps(result, indent=2))
    return not result['passed']


if __name__ == '__main__':
    raise SystemExit(main())
