#!/usr/bin/env python3
"""Small CI adapters. No repository/account configuration or deployment calls."""
import argparse
from email.parser import BytesParser
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = re.compile(r'\d+\.\d+\.\d+\Z')
# Exact success summaries emitted by the npm test suites, in package.json order.
# Keep suite identity/counts, so an omitted suite cannot be hidden by another's total.
FRONTEND_SUMMARIES = {
    'dom': 'TOTAL 31 passed',
    'workflows': 'TOTAL 33 workflow tests passed',
    'controls': 'TOTAL 15 control tests passed',
    'media': 'TOTAL 19 media and news tests passed',
    'recovery': 'TOTAL 36 recovery edge tests passed (Node/jsdom)',
    'enterprise': 'TOTAL 13 enterprise preview tests passed',
    'boundaries': 'TOTAL 68 refactor boundary checks passed (Node/jsdom)',
    'bulk-publish': 'TOTAL 7 catalog bulk publish checks passed (Node/jsdom)',
    'login': 'TOTAL 31 passed, 0 failed (Node/jsdom static login demo)',
    'presentation': 'TOTAL 28 presentation checks passed',
    'pagination': 'TOTAL 254 pagination checks passed (Node/jsdom)',
    'extensions': 'TOTAL 5 extensions guide tests passed',
    'palettes': 'TOTAL 82 palette checks passed',
}
FRONTEND_COUNTS = {name: int(summary.split()[1]) for name, summary in FRONTEND_SUMMARIES.items()}
FRONTEND_TOTAL = sum(FRONTEND_COUNTS.values())

def read(path):
    return json.loads(Path(path).read_text())

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def plan(scope, root=ROOT):
    if scope not in ('quick', 'full'):
        raise ValueError('scope must be quick or full')
    config = read(root / 'ci/matrix.json')
    cells = read(root / 'django-theme/scripts/test-matrix.json')['cells']
    if len({(x['python'], x['django']) for x in cells}) != len(cells):
        raise ValueError('Duplicate Python/Django cells')
    for cell in cells:
        if not all(VERSION.fullmatch(x) for x in cell.values()):
            raise ValueError('Expected exact Python/Django versions')
    allowed = {(x['python'], x['django']) for x in cells}
    quick = config['quick_python']
    if any((x['python'], x['django']) not in allowed or type(x['captcha']) is not bool for x in quick):
        raise ValueError('Quick cells must be an explicit subset of the canonical matrix')
    if len({(x['python'], x['django']) for x in quick}) != len(quick):
        raise ValueError('Duplicate quick cell')
    nodes = config['node']
    if len({x['node'] for x in nodes}) != len(nodes) or any(not VERSION.fullmatch(x['node']) or not VERSION.fullmatch(x['npm']) for x in nodes):
        raise ValueError('Expected unique exact Node/npm versions')
    selected = [x for x in nodes if x['node'] == config['quick_node']]
    if len(selected) != 1:
        raise ValueError('Quick Node must select one full-matrix row')
    return {'scope': scope, 'python': {'include': [dict(x, captcha=True) for x in cells] if scope == 'full' else quick},
            'node': {'include': nodes if scope == 'full' else selected}}

def safe_new_directory(path):
    path = Path(path).resolve()
    path.mkdir(parents=True, exist_ok=False)
    return path

def sidebars(wheelhouse, output):
    config = read(ROOT / 'ci/matrix.json')
    output = safe_new_directory(output)
    rows = []
    for version, expected in config['django_wheels'].items():
        wheel = Path(wheelhouse) / expected['filename']
        if digest(wheel) != expected['sha256']:
            raise ValueError('Django wheel checksum mismatch: ' + version)
        with zipfile.ZipFile(wheel) as archive:
            names = [n for n in archive.namelist() if n.endswith('.dist-info/METADATA')]
            if len(names) != 1 or BytesParser().parsebytes(archive.read(names[0]))['Version'] != version:
                raise ValueError('Django wheel version mismatch')
            content = archive.read('django/contrib/admin/static/admin/js/nav_sidebar.js')
        dest = output / ('django-' + version + '.js')
        dest.write_bytes(content)
        rows.append({'django': version, 'wheel_sha256': digest(wheel), 'file': dest.name, 'sha256': digest(dest)})
    (output / 'provenance.json').write_text(json.dumps(rows, indent=2) + '\n')
    return rows

def ranged_wheel(output, sdist=None):
    """Build the one official sdist-only dependency; no unpinned build isolation."""
    config = read(ROOT / 'ci/matrix.json')['ranged_response']
    output = safe_new_directory(output)
    source = output / 'django-ranged-response-0.2.0.tar.gz'
    if sdist:
        source.write_bytes(Path(sdist).read_bytes())
        origin = 'local copy, checked against pinned official PyPI digest'
    else:
        with urllib.request.urlopen(config['metadata_url'], timeout=60) as response:
            metadata = json.load(response)
        match = [x for x in metadata['urls'] if x['packagetype'] == 'sdist' and x['digests']['sha256'] == config['sha256']]
        if len(match) != 1 or not match[0]['url'].startswith('https://files.pythonhosted.org/'):
            raise ValueError('Pinned official source was not found')
        origin = match[0]['url']
        with urllib.request.urlopen(origin, timeout=60) as response:
            source.write_bytes(response.read())
    if digest(source) != config['sha256']:
        raise ValueError('ranged-response source checksum mismatch')
    subprocess.run([sys.executable, '-m', 'pip', '--disable-pip-version-check', 'wheel', '--no-index', '--no-deps',
                    '--no-build-isolation', '--wheel-dir', str(output), str(source)], check=True)
    wheels = list(output.glob('*.whl'))
    if len(wheels) != 1:
        raise ValueError('Expected one ranged-response wheel')
    result = {'source': origin, 'source_sha256': config['sha256'], 'wheel': wheels[0].name, 'wheel_sha256': digest(wheels[0])}
    (output / 'provenance.json').write_text(json.dumps(result, indent=2) + '\n')
    return result

def collect_python(run_root, output, commit, cell, captcha):
    """Only reports/logs; never upload venvs, caches, harnesses, or test DBs."""
    report = read(Path(run_root) / 'results.json')
    expected = {f'{cell}/{profile}/{mode}' for profile in (['core', 'captcha'] if captcha else ['core']) for mode in ['source', 'wheel']}
    actual = report['results']
    if report['status'] != 'passed' or len(actual) != len(expected) or {x['id'] for x in actual} != expected or any(x['status'] != 'passed' for x in actual):
        raise ValueError('Matrix evidence is incomplete or failed')
    output = safe_new_directory(output)
    compact = {'kind': 'python', 'commit': commit, 'cell': cell, 'captcha': captcha, 'status': 'passed',
               'wheel_sha256': report['wheel']['sha256'], 'results': []}
    for result in actual:
        entry = {'id': result['id'], 'status': result['status'], 'python': result['actual']['python'], 'django': result['actual']['django'],
                 'profile': result['expected']['profile'], 'mode': result['expected']['mode'], 'steps': {}}
        for name, step in result['steps'].items():
            if step['status'] != 'passed' or step['exit_code'] != 0:
                raise ValueError('Step did not pass')
            entry['steps'][name] = {k: step[k] for k in ['exit_code', 'status', 'tests_run', 'unittest_summary'] if k in step}
            # These allowlisted logs contain synthetic test data only.
            if name in ('tests', 'check', 'migrations', 'pipcheck'):
                target = result['id'].replace('/', '_') + '-' + name + '.log'
                (output / target).write_bytes(Path(step['log']).read_bytes())
        compact['results'].append(entry)
    (output / 'report.json').write_text(json.dumps(compact, indent=2) + '\n')
    return compact

def collect_node(logs, output, commit, node, npm):
    logs = Path(logs)
    expected = next((x for x in read(ROOT / 'ci/matrix.json')['node'] if x['node'] == node), None)
    if expected is None or expected['npm'] != npm:
        raise ValueError('Unknown Node/npm pair')
    version = read(logs / 'runtime.json')
    if version['node'] != 'v' + node or version['npm'] != npm:
        raise ValueError('Actual Node/npm mismatch')
    steps = read(logs / 'steps.json')
    required = {'npm-version','install','dependency-tree','frontend','navigation','enhancements','captcha'}
    if len(steps) != len(required) or {x['name'] for x in steps} != required or any(x['exitCode'] != 0 or x.get('signal') or x.get('error') for x in steps):
        raise ValueError('Incomplete Node commands')
    inputs = read(logs / 'inputs.json')
    if inputs != {name:digest(ROOT / name) for name in ['package.json','package-lock.json']}:
        raise ValueError('Node test inputs differ from checkout')
    for name, pattern, summaries in [
        ('frontend', r'^TOTAL .+$', list(FRONTEND_SUMMARIES.values())),
        ('navigation', r'^\d+ navigation DOM scenarios .+$', ['78 navigation DOM scenarios passed (3 Django script versions).']),
        ('enhancements', r'^TOTAL .+$', ['TOTAL 8 search enhancement tests passed']),
        ('captcha', r'^TOTAL .+$', ['TOTAL 11 CAPTCHA enhancement tests passed']),
    ]:
        content = (logs / (name + '.log')).read_text()
        if re.findall(pattern, content, re.M) != summaries or re.search(r'^(?:FAIL|FAILED|not ok)\b', content, re.M):
            raise ValueError('Missing, duplicate, or failed Node test evidence: ' + name)
    output = safe_new_directory(output)
    for name in ['frontend.log', 'navigation.log', 'enhancements.log', 'captcha.log', 'runtime.json', 'dependency-tree.json']:
        (output / name).write_bytes((logs / name).read_bytes())
    result = {'kind': 'node', 'commit': commit, 'node': node, 'npm': npm, 'status': 'passed', 'frontend': FRONTEND_TOTAL, 'frontend_suites': dict(FRONTEND_COUNTS), 'theme_js': 97,
              'package_lock_sha256': digest(ROOT / 'package-lock.json')}
    (output / 'report.json').write_text(json.dumps(result, indent=2) + '\n')
    return result

def verify_reports(reports, scope, commit, wheel_sha):
    wanted = plan(scope)
    python = {f"{x['python']}/{x['django']}": x for x in wanted['python']['include']}
    nodes = {x['node']: x for x in wanted['node']['include']}
    found_python, found_node = {}, {}
    for path in Path(reports).rglob('report.json'):
        row = read(path)
        if row.get('commit') != commit or row.get('status') != 'passed':
            raise ValueError('Report source/status mismatch')
        if row['kind'] == 'python':
            key = row['cell']
            if key not in python or key in found_python or row['captcha'] != python[key]['captcha'] or row['wheel_sha256'] != wheel_sha:
                raise ValueError('Unexpected, duplicate, or mismatched Python report')
            expected = {f'{key}/{p}/{m}' for p in (['core', 'captcha'] if row['captcha'] else ['core']) for m in ['source', 'wheel']}
            if len(row['results']) != len(expected) or {x['id'] for x in row['results']} != expected or any(x['status'] != 'passed' for x in row['results']):
                raise ValueError('Incomplete Python variants')
            for result in row['results']:
                if result['python'] != python[key]['python'] or result['django'] != python[key]['django'] or result['id'] != f"{key}/{result['profile']}/{result['mode']}":
                    raise ValueError('Actual Python variant identity mismatch')
                tests = result['steps'].get('tests', {})
                if tests.get('tests_run', 0) <= 0 or not tests.get('unittest_summary', '').startswith('OK'):
                    raise ValueError('No successful Python test evidence')
                if set(result['steps']) != {'venv','install','pipcheck','provenance','check','migrations','tests'} or any(x['status'] != 'passed' or x['exit_code'] != 0 for x in result['steps'].values()):
                    raise ValueError('Incomplete Python steps')
            found_python[key] = row
        elif row['kind'] == 'node':
            key = row['node']
            if key not in nodes or key in found_node or row['npm'] != nodes[key]['npm'] or row['frontend'] != FRONTEND_TOTAL or row.get('frontend_suites') != FRONTEND_COUNTS or row['theme_js'] != 97 or row['package_lock_sha256'] != digest(ROOT / 'package-lock.json'):
                raise ValueError('Unexpected, duplicate, or mismatched Node report')
            found_node[key] = row
        else:
            raise ValueError('Unknown report kind')
    if set(found_python) != set(python) or set(found_node) != set(nodes):
        raise ValueError('Missing required matrix reports')
    return {'status': 'passed', 'scope': scope, 'commit': commit, 'python_cells': len(python),
            'python_variants': sum(len(x['results']) for x in found_python.values()), 'node_versions': len(nodes)}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('plan');p.add_argument('--scope', choices=['quick','full'], required=True)
    p = sub.add_parser('sidebars');p.add_argument('--wheelhouse', type=Path, required=True);p.add_argument('--output', type=Path, required=True)
    p = sub.add_parser('ranged-wheel');p.add_argument('--output', type=Path, required=True);p.add_argument('--sdist', type=Path)
    p = sub.add_parser('collect-python');p.add_argument('--run-root', type=Path, required=True);p.add_argument('--output', type=Path, required=True);p.add_argument('--commit', required=True);p.add_argument('--cell', required=True);p.add_argument('--captcha', choices=['true','false'], required=True)
    p = sub.add_parser('collect-node');p.add_argument('--logs', type=Path, required=True);p.add_argument('--output', type=Path, required=True);p.add_argument('--commit', required=True);p.add_argument('--node', required=True);p.add_argument('--npm', required=True)
    p = sub.add_parser('verify-reports');p.add_argument('--reports', type=Path, required=True);p.add_argument('--scope', choices=['quick','full'], required=True);p.add_argument('--commit', required=True);p.add_argument('--wheel', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'plan':
        result = plan(args.scope)
        for k,v in result.items(): print(k+'='+ (v if isinstance(v,str) else json.dumps(v,separators=(',',':'))))
        return
    if args.command == 'sidebars': result = sidebars(args.wheelhouse,args.output)
    elif args.command == 'ranged-wheel': result = ranged_wheel(args.output,args.sdist)
    elif args.command == 'collect-python': result = collect_python(args.run_root,args.output,args.commit,args.cell,args.captcha=='true')
    elif args.command == 'collect-node': result = collect_node(args.logs,args.output,args.commit,args.node,args.npm)
    else: result = verify_reports(args.reports,args.scope,args.commit,digest(args.wheel))
    print(json.dumps(result,indent=2))

if __name__ == '__main__':
    main()
