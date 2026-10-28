#!/usr/bin/env python3
"""Build the offline JS/Django icon registries from pinned, licensed SVG sources."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'dist/assets/icons'
PACKAGE = ROOT / 'django-theme/src/nova_admin'
TAGS = {'path', 'rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon', 'g'}
ATTRS = {'d', 'x', 'y', 'x1', 'x2', 'y1', 'y2', 'width', 'height', 'rx', 'ry',
         'cx', 'cy', 'r', 'points', 'fill', 'fill-rule', 'clip-rule', 'stroke',
         'stroke-width', 'stroke-miterlimit', 'stroke-linecap', 'stroke-linejoin', 'opacity', 'transform'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def asset_path(relative):
    path = (ASSETS / relative).resolve()
    if not path.is_relative_to(ASSETS.resolve()):
        raise ValueError('Asset escapes the bundled icon directory')
    return path


def node_markup(node):
    tag = node.tag.rsplit('}', 1)[-1]
    if tag not in TAGS or set(node.attrib) - ATTRS:
        raise ValueError(f'Unsupported SVG element/attribute: {tag}')
    if node.text and node.text.strip():
        raise ValueError('Icon paths cannot contain text')
    if any(re.search(r'url\s*\(|javascript:|https?:', value, re.I) for value in node.attrib.values()):
        raise ValueError('Icon paths cannot reference external resources')
    attrs = ''.join(f' {key}="{html.escape(value, quote=True)}"' for key, value in sorted(node.attrib.items()))
    children = ''.join(node_markup(child) for child in node)
    return f'<{tag}{attrs}>{children}</{tag}>'


def svg_paint(node):
    """Preserve reviewed outline or filled geometry without changing its coordinate grid."""
    if node.tag.rsplit('}', 1)[-1] != 'svg' or node.get('viewBox') not in {'0 0 24 24', '0 0 16 16'}:
        raise ValueError('Expected a reviewed 16- or 24-unit SVG')
    fill = node.get('fill', 'none')
    # Iconoir places currentColor strokes on child paths rather than the root.
    stroke = node.get('stroke', 'currentColor' if fill == 'none' else 'none')
    if (fill, stroke) not in {('none', 'currentColor'), ('currentColor', 'none')}:
        raise ValueError('Expected currentColor outline or filled SVG')
    width = float(node.get('stroke-width', '2')) if stroke != 'none' else 0
    if stroke != 'none' and not 1 <= width <= 3:
        raise ValueError('Unexpected source stroke width')
    return dict(viewBox=node.get('viewBox'), fill=fill, stroke=stroke, strokeWidth=width)


def payload():
    manifest = json.loads((ASSETS / 'manifest.json').read_text())
    if manifest['schema'] != 1:
        raise ValueError('Unknown icon manifest')
    libraries = []
    for library in manifest['libraries']:
        license_bytes = asset_path(library['license_path']).read_bytes()
        if digest(license_bytes) != library['license_sha256']:
            raise ValueError('License differs from its recorded upstream source')
        libraries.append({key: library[key] for key in ('id', 'name', 'version', 'license', 'license_label', 'docs', 'repository', 'license_path', 'count', 'description', 'preview')})
    providers = {library['id']: library for library in libraries}
    if len(providers) != len(libraries):
        raise ValueError('Duplicate icon library')
    icons = {}
    for item in manifest['icons']:
        if not re.fullmatch(r'[a-z]+:[a-z0-9-]+', item['id']) or item['id'] in icons:
            raise ValueError('Invalid or duplicate namespaced icon')
        data = asset_path(item['file']).read_bytes()
        if digest(data) != item['sha256']:
            raise ValueError('SVG differs from its recorded upstream source: ' + item['id'])
        node = ET.fromstring(data)
        if item['library'] not in providers or item['id'] != item['library'] + ':' + item['name']:
            raise ValueError('Icon must belong to its declared library')
        paint = svg_paint(node)
        icons[item['id']] = {key: item[key] for key in ('library', 'name', 'label', 'category', 'keywords', 'file')}
        icons[item['id']].update(body=''.join(node_markup(child) for child in node), **paint)
    if len(icons) != manifest['count'] or any(sum(icon['library'] == library['id'] for icon in icons.values()) != library['count'] for library in libraries):
        raise ValueError('Icon counts differ from the reviewed manifest inventory')
    if any(library['preview'] not in icons or icons[library['preview']]['library'] != library['id'] for library in libraries):
        raise ValueError('Library preview must select an icon from that library')
    return {'libraries': libraries, 'icons': icons}


def raw_json_literal(serialized):
    # JSON unicode escapes preserve the data without opening a JS template
    # interpolation or closing its backtick delimiter.
    return serialized.rstrip().replace('`', r'\u0060').replace('${', r'$\u007b')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Validate offline sources and generated outputs without writes')
    args = parser.parse_args()
    data = payload()
    serialized = json.dumps(data, ensure_ascii=False, indent=2) + '\n'
    js = ROOT / 'dist/js/open-icons.js'
    packaged = PACKAGE / 'icons.json'
    if args.check:
        match = re.search(r'String\.raw`([\s\S]*)`\s*\)', js.read_text())
        if not match or json.loads(match[1]) != data or json.loads(packaged.read_text()) != data:
            raise ValueError('Generated JS/Django icon registries are stale')
        for library in data['libraries']:
            source = asset_path(library['license_path']).read_bytes()
            if (PACKAGE / 'licenses' / (library['id'] + '.txt')).read_bytes() != source:
                raise ValueError('Packaged icon license is stale')
    else:
        js.write_text('// Generated by scripts/build_icons.py; source hashes and licenses: assets/icons/manifest.json.\n'
                      + 'export const openIconData = JSON.parse(String.raw`' + raw_json_literal(serialized) + '`);\n')
        packaged.write_text(serialized)
        (PACKAGE / 'licenses').mkdir(exist_ok=True)
        for library in data['libraries']:
            shutil.copyfile(asset_path(library['license_path']), PACKAGE / 'licenses' / (library['id'] + '.txt'))
    print(json.dumps({'status': 'passed', 'icons': len(data['icons']), 'libraries': len(data['libraries']), 'mode': 'check' if args.check else 'build'}))


if __name__ == '__main__':
    main()
