#!/usr/bin/env python3
"""Measure opaque palette roles from authored CSS; not a browser/WCAG audit."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

def ratio(a, b):
    def luminance(color):
        channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in channels]
        return sum(c * weight for c, weight in zip(linear, (.2126, .7152, .0722)))
    x, y = sorted((luminance(a), luminance(b)))
    return (y + .05) / (x + .05)


def declarations(block):
    return dict(re.findall(r'(--[\w-]+):\s*(#[0-9a-f]{6})', block))


def main():
    theme = (ROOT / 'django-theme/src/nova_admin/static/nova_admin/theme.css').read_text()
    palettes = (ROOT / 'django-theme/src/nova_admin/static/nova_admin/presets.css').read_text()
    preview = (ROOT / 'dist/presets.css').read_text()
    roles = []
    for key in ('teal', 'indigo', 'violet', 'terracotta'):
        tokens = declarations(re.search(r'body\.nova-admin:where\(\.nova-palette-' + key + r'\)\s*\{([^}]+)', palettes)[1])
        static = declarations(re.search(r':root:where\(\[data-palette="' + key + r'"\]\)\s*\{([^}]+)', preview)[1])
        for mode in ('light', 'dark'):
            base = declarations(re.search(r'body\.nova-admin\.nova-mode-' + mode + r'\s*\{([^}]+)', theme)[1])
            brand, hover = (tokens['--nova-brand-' + mode + suffix] for suffix in ('', '-hover'))
            selected, row = (tokens['--nova-palette-' + name + '-' + mode] for name in ('selected', 'row'))
            assert static['--nova-brand-' + mode] == brand
            assert static['--nova-brand-' + mode + '-hover'] == hover
            assert static['--nova-brand-selection-' + mode] == selected
            assert static['--nova-brand-row-' + mode] == row
            def add(role, fg, bg, threshold=4.5):
                value = ratio(fg, bg)
                roles.append(dict(palette=key, mode=mode, role=role, foreground=fg, background=bg, contrast=round(value, 3), minimum=threshold, passed=value >= threshold))
            surfaces = {name: base['--' + name] for name in ('body-bg', 'nova-panel', 'darkened-bg')}
            surfaces.update(selected=selected, row=row)
            for name, bg in surfaces.items():
                add('Django link / ' + name, brand, bg)
                add('Django hover link / ' + name, hover, bg)
                add('Django focus ring / ' + name, brand, bg, 3)
                for role in ('body-fg', 'body-quiet-color', 'body-medium-color'):
                    add('Django ' + role + ' / ' + name, base['--' + role], bg)
            # Generic and demo use distinct existing dark button foregrounds.
            for fg in (['#ffffff'] if mode == 'light' else ['#0b1020', '#102036', '#191527', '#191525']):
                add('button or brand mark', fg, brand)
                add('button hover', fg, hover)
            static_surfaces = ['#f4f6fa', '#ffffff', '#f7f8fc'] if mode == 'light' else ['#0c101a', '#101520', '#151b28', '#1a2232']
            for bg in static_surfaces + [selected, row]:
                add('preview active link/icon', brand, bg)
                add('preview focus ring', brand, bg, 3)
            # Row hover has real secondary text and status text, unlike selected nav labels.
            for name, fg in ({'text':'#23283a', 'muted':'#5a667c', 'error':'#b1223c'} if mode == 'light' else {'text':'#eef0f6', 'muted':'#9ba8c2', 'error':'#f392a0'}).items():
                add('preview row ' + name, fg, row)
            muted = declarations(re.search(r':root\[data-theme="' + mode + r'"\]:where[^{}]+\{([^}]+)', preview)[1])['--muted']
            for name, bg in dict(selected=selected, row=row, **{str(i): bg for i, bg in enumerate(static_surfaces)}).items():
                add('preview secondary text / command hover / ' + name, muted, bg)
            add('Django row error', base['--error-fg'], row)
    result = {'scope': 'Opaque links, hover links, primary/default/save buttons, brand marks, selected navigation, row text, errors on row, focus rings; no runtime layout or rendered blending certification. Existing disabled-opacity, chart series, translucent effects and unchanged semantic status treatments require visual review.', 'checks': len(roles), 'passed': all(x['passed'] for x in roles), 'minimum_measured': min(x['contrast'] for x in roles), 'roles': roles}
    print(json.dumps(result, indent=2))
    return not result['passed']

if __name__ == '__main__':
    raise SystemExit(main())
