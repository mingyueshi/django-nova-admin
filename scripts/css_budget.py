#!/usr/bin/env python3
"""No CSS build step: track authored bytes and deterministic gzip transfer size."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / 'ci/css-budget.json'


def measurements(root):
    paths = sorted((root / 'django-theme/src/nova_admin/static/nova_admin').rglob('*.css'))
    paths += sorted(path for path in (root / 'dist').rglob('*.css')
                    if path.relative_to(root / 'dist').parts[0] not in {'native-admin', 'navigation-lab'})
    results = {}
    for path in paths:
        data = path.read_bytes()
        if path.name.endswith('.min.css'):
            match = re.search(rb'/\*#\s*sourceMappingURL=([^\s*]+)\s*\*/', data)
            if not match:
                raise ValueError('Minified authored CSS requires a local source map: ' + str(path))
            name = match.group(1).decode('utf-8')
            if '/' in name or '\\' in name or not name.endswith('.map') or name.startswith('.'):
                raise ValueError('Source map must be a neighboring ordinary file')
            source_map = json.loads((path.parent / name).read_text())
            if source_map.get('version') != 3 or not source_map.get('sources') or not source_map.get('sourcesContent') or not source_map.get('mappings'):
                raise ValueError('Source map must retain original sources and mappings')
        results[path.relative_to(root).as_posix()] = {
            'bytes': len(data), 'gzip_bytes': len(gzip.compress(data, compresslevel=9, mtime=0)),
            'sha256': hashlib.sha256(data).hexdigest(),
        }
    if not results:
        raise ValueError('No authored stylesheets found')
    return results


def validate(current, baseline):
    errors = []
    if set(current) != set(baseline['files']):
        errors.append('Authored CSS inventory changed; review the budget explicitly')
    for name in current.keys() & baseline['files'].keys():
        previous = baseline['files'][name]
        for metric in ('bytes', 'gzip_bytes'):
            if current[name][metric] > previous['limits'][metric]:
                errors.append(f'{name}: {metric} {current[name][metric]} exceeds {previous["limits"][metric]}')
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, default=BASELINE)
    parser.add_argument('--record', action='store_true', help='Explicitly accept a reviewed baseline with 10 percent size headroom')
    args = parser.parse_args(argv)
    current = measurements(ROOT)
    if args.record:
        data = {'schema': 1, 'policy': 'Hand-written, unminified CSS; no compiler or CSS dependency. Gzip is measurement only. Reviewed 10% size headroom; third-party and generated duplicate CSS excluded.', 'files': {}}
        for name, info in current.items():
            data['files'][name] = {**info, 'limits': {metric: (info[metric] * 110 + 99) // 100 for metric in ('bytes', 'gzip_bytes')}}
        args.baseline.write_text(json.dumps(data, indent=2) + '\n')
    baseline = json.loads(args.baseline.read_text())
    if baseline.get('schema') != 1:
        parser.error('Unsupported CSS budget schema')
    errors = validate(current, baseline)
    print(json.dumps({'status': 'failed' if errors else 'passed', 'files': current, 'errors': errors}, indent=2))
    return bool(errors)


if __name__ == '__main__':
    sys.exit(main())
