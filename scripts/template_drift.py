#!/usr/bin/env python3
"""Compare local overrides and reviewed upstream templates; never update silently."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / 'ci/template-baselines.json'
WATCHED = {
    'admin/base.html': 'django-theme/src/nova_admin/templates/admin/base.html',
    'admin/index.html': 'django-theme/src/nova_admin/templates/admin/index.html',
    'admin/login.html': 'django-theme/src/nova_admin/templates/admin/login.html',
    'admin/base_site.html': ['django-theme/src/nova_admin/templates/admin/base_site.html', 'django-theme/demo/templates/admin/base_site.html'],
    'admin/actions.html': 'django-theme/demo/templates/admin/actions.html',
    'admin/includes/fieldset.html': 'django-theme/demo/templates/admin/includes/fieldset.html',
    'admin/edit_inline/tabular.html': 'django-theme/demo/templates/admin/edit_inline/tabular.html',
}
BLOCK = re.compile(r'{%\s*block\s+([A-Za-z_][A-Za-z_0-9]*)\s*%}')
EXTENDS = re.compile(r'{%\s*extends\s+[\'"]([^\'"]+)[\'"]\s*%}')


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def read_templates(django_root):
    base = Path(django_root) / 'contrib/admin/templates'
    return {name: (base / name).read_text(encoding='utf-8') for name in WATCHED}


def compare(current, reviewed, overrides):
    rows = []
    for name, local in overrides.items():
        upstream = current.get(name)
        if upstream is None:
            rows.append({'template': name, 'status': 'missing-upstream', 'removed_blocks': []})
            continue
        baseline = reviewed.get(name, '')
        required = set(BLOCK.findall(local))
        # Custom nested Nova blocks are extension points, not upstream contracts.
        inherited = {x for x in required if not x.startswith('nova_')}
        available = set(BLOCK.findall(upstream))
        parent, visited = upstream, {name}
        while match := EXTENDS.search(parent):
            ancestor = match.group(1)
            if ancestor in visited or ancestor not in current:
                break
            visited.add(ancestor)
            parent = current[ancestor]
            available.update(BLOCK.findall(parent))
        removed = sorted(inherited - available)
        changed = upstream != baseline
        rows.append({
            'template': name, 'status': 'review-required' if changed or removed else 'reviewed',
            'upstream_sha256': digest(upstream), 'reviewed_sha256': digest(baseline),
            'override_sha256': digest(local), 'removed_blocks': removed,
            'upstream_changed': changed,
            'upstream_diff': ''.join(difflib.unified_diff(baseline.splitlines(True), upstream.splitlines(True), fromfile='reviewed/' + name, tofile='current/' + name)),
            'override_diff': ''.join(difflib.unified_diff(upstream.splitlines(True), local.splitlines(True), fromfile='upstream/' + name, tofile='nova/' + name)),
        })
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--django-root', type=Path, help='The django/ package inside an installed release or official source checkout')
    parser.add_argument('--label', help='Exact release or main@commit label for an explicit source checkout')
    parser.add_argument('--baseline', type=Path, default=BASELINE)
    parser.add_argument('--reference', default='6.1.1', help='Reviewed release used when the current label is unknown')
    parser.add_argument('--output', type=Path, required=True, help='New report directory, never overwritten')
    parser.add_argument('--record-reviewed', action='store_true', help='Explicit maintainer action after review: replace only this exact release baseline')
    args = parser.parse_args(argv)
    if args.django_root is None:
        import django
        args.django_root = Path(django.__file__).parent
        label = django.get_version()
    else:
        if not args.label:
            parser.error('--label is required with --django-root')
        label = args.label
    if not re.fullmatch(r'[A-Za-z0-9.@_+-]{1,100}', label):
        parser.error('Invalid source label')
    if args.output.exists():
        parser.error('Report directory already exists; choose a new path')
    current = read_templates(args.django_root)
    manifest = json.loads(args.baseline.read_text()) if args.baseline.exists() else {'schema': 1, 'license': 'Django BSD-3-Clause; django-theme/src/nova_admin/LICENSE-DJANGO.txt', 'releases': {}}
    if manifest.get('schema') != 1 or not isinstance(manifest.get('releases'), dict):
        parser.error('Invalid reviewed baseline manifest')
    if args.record_reviewed:
        if not re.fullmatch(r'\d+\.\d+\.\d+', label):
            parser.error('Only exact stable releases may be recorded as reviewed')
        manifest['releases'][label] = current
        args.baseline.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    reference = label if label in manifest['releases'] else args.reference
    if reference not in manifest['releases']:
        parser.error('No reviewed baseline for reference ' + reference)
    rows = []
    for name, paths in WATCHED.items():
        for path in paths if isinstance(paths, list) else [paths]:
            row = compare(current, manifest['releases'][reference], {name: (ROOT / path).read_text()})[0]
            row['override'] = path
            rows.append(row)
    status = 'review-required' if any(row['status'] != 'reviewed' for row in rows) else 'reviewed'
    report = {'schema': 1, 'source': label, 'reference': reference, 'status': status, 'templates': rows,
              'boundary': 'Text and inherited-block drift warning only; not future Django compatibility certification.'}
    args.output.mkdir(parents=True)
    (args.output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    for row in rows:
        stem = row['override'].replace('/', '__')
        (args.output / (stem + '.upstream.diff')).write_text(row.get('upstream_diff', 'Missing upstream template\n'))
        (args.output / (stem + '.override.diff')).write_text(row.get('override_diff', ''))
    print(json.dumps({key: report[key] for key in ('source', 'reference', 'status')}))
    return int(status != 'reviewed')


if __name__ == '__main__':
    sys.exit(main())
