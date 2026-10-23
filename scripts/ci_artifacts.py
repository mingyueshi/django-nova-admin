#!/usr/bin/env python3
"""Build and verify local candidate artifacts. Never publish or deploy anything."""
import argparse
import ast
import base64
import csv
from email.parser import BytesParser
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SHA = re.compile(r'[0-9a-f]{40}\Z')
STATIC_MARKER = 'native-admin/.nova-admin-samples'
MARKER_CONTENT = b'Synthetic inert Django Admin samples. Regenerate with scripts/export_admin_samples.py\n'
STATIC_EXTENSIONS = {'.html','.css','.js','.json','.svg','.webp','.png','.jpg','.jpeg','.gif','.ico','.woff','.woff2','.ttf','.md','.txt'}

def digest(data):
    return hashlib.sha256(data).hexdigest()

def safe_name(name):
    path = PurePosixPath(name)
    if name == STATIC_MARKER:
        return path
    if not name or path.is_absolute() or '\\' in name or any(x in ('', '.', '..') or x.startswith('.') for x in name.split('/')):
        raise ValueError('Unsafe artifact path: ' + name)
    return path

def runtime_files(source):
    base = source / 'django-theme/src'
    result = {}
    for path in sorted((base / 'nova_admin').rglob('*')):
        if '__pycache__' in path.parts or path.suffix == '.pyc':
            continue
        if path.is_symlink():
            raise ValueError('Symlink in theme source')
        if path.is_file():
            result[path.relative_to(base).as_posix()] = path.read_bytes()
    return result

def check_metadata(info, project):
    if info['Name'] != project['name'] or info['Version'] != project['version']:
        raise ValueError('Package project/version mismatch')
    if info['Requires-Python'] != project['requires-python'] or info['License-Expression'] != project['license']:
        raise ValueError('Package Python/license metadata mismatch')
    if info.get_all('License-File', []) != ['LICENSE']:
        raise ValueError('Missing project license metadata')
    def requirement(value):
        dependency, _, marker = value.partition(';')
        match = re.fullmatch(r'([A-Za-z0-9_.-]+)(.*)', dependency.replace(' ', ''))
        if not match:
            raise ValueError('Invalid dependency metadata')
        return (match[1].lower().replace('_', '-'), tuple(sorted(match[2].split(','))),
                marker.replace(' ', '').replace("'", '"'))
    extras = project.get('optional-dependencies', {})
    expected = list(project.get('dependencies', []))
    expected += [value + '; extra == "' + extra + '"' for extra, values in extras.items() for value in values]
    if sorted(map(requirement, info.get_all('Requires-Dist', []))) != sorted(map(requirement, expected)):
        raise ValueError('Package dependency metadata mismatch')
    if sorted(info.get_all('Provides-Extra', [])) != sorted(extras):
        raise ValueError('Package extras metadata mismatch')

def wheel_check(wheel, source):
    project = tomllib.loads((source / 'django-theme/pyproject.toml').read_text())['project']
    expected = runtime_files(source)
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate wheel member')
        for item in archive.infolist():
            safe_name(item.filename)
            if stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError('Symlink in wheel')
        metadata = [x for x in names if x.endswith('.dist-info/METADATA')]
        if len(metadata) != 1:
            raise ValueError('Expected one wheel metadata record')
        info = BytesParser().parsebytes(archive.read(metadata[0]))
        check_metadata(info, project)
        theme = {x: archive.read(x) for x in names if x.startswith('nova_admin/')}
        if theme != expected:
            raise ValueError('Wheel runtime files differ from source')
        prefix = metadata[0].rsplit('/', 1)[0] + '/'
        if archive.read(prefix + 'licenses/LICENSE') != (source / 'django-theme/LICENSE').read_bytes():
            raise ValueError('Wheel project license differs from source')
        allowed = {prefix + name for name in ('METADATA', 'WHEEL', 'RECORD', 'top_level.txt', 'licenses/LICENSE')}
        if set(names) != set(expected) | allowed:
            raise ValueError('Unexpected wheel content')
        record_path = prefix + 'RECORD'
        records = list(csv.reader(io.StringIO(archive.read(record_path).decode())))
        if len(records) != len(names) or {x[0] for x in records} != set(names):
            raise ValueError('Incomplete wheel RECORD')
        for name, hash_value, size in records:
            if name == record_path:
                if hash_value or size:
                    raise ValueError('RECORD must not hash itself')
                continue
            content = archive.read(name)
            encoded = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b'=').decode()
            if hash_value != 'sha256=' + encoded or size != str(len(content)):
                raise ValueError('Wheel RECORD digest mismatch')
    return {'name': project['name'], 'version': project['version'], 'runtime_files': len(expected)}

def sdist_files(source):
    """The source/documentation contract, independent of setuptools' file list."""
    base = source / 'django-theme'
    files = {p.name: p.read_bytes() for p in base.glob('*.md') if p.is_file() and not p.is_symlink()}
    for name in ('pyproject.toml', 'MANIFEST.in', 'LICENSE', 'requirements-test.txt'):
        files[name] = (base / name).read_bytes()
    suffixes = {'demo': {'.py', '.html', '.css', '.webp', '.svg', '.json', '.po', '.mo', '.txt'},
                'tests': {'.py'}, 'scripts': {'.py', '.sh', '.mjs', '.json'}}
    for folder, allowed in suffixes.items():
        for path in sorted((base / folder).rglob('*')):
            relative = path.relative_to(base)
            if any(part in ('__pycache__', '.venv', 'staticfiles', 'build', 'dist') for part in relative.parts):
                continue
            if path.is_symlink():
                raise ValueError('Symlink in sdist source')
            if path.is_file() and path.suffix in allowed:
                files[relative.as_posix()] = path.read_bytes()
    files.update({'src/' + name: data for name, data in runtime_files(source).items()})
    return files

def sdist_check(sdist, source):
    project = tomllib.loads((source / 'django-theme/pyproject.toml').read_text())['project']
    prefix = project['name'].replace('-', '_') + '-' + project['version'] + '/'
    files, seen = {}, set()
    with tarfile.open(sdist, 'r:gz') as archive:
        for item in archive:
            safe_name(item.name)
            if item.name in seen or not (item.isdir() or item.isfile()):
                raise ValueError('Duplicate or unsafe sdist member')
            seen.add(item.name)
            if item.name != prefix.rstrip('/') and not item.name.startswith(prefix):
                raise ValueError('Unexpected sdist root')
            if item.isfile():
                files[item.name[len(prefix):]] = archive.extractfile(item).read()
    expected = sdist_files(source)
    if any(files.get(name) != data for name, data in expected.items()):
        raise ValueError('Sdist source/documentation differs from source')
    generated = {'PKG-INFO', 'setup.cfg'}
    egg = 'src/' + project['name'].replace('-', '_') + '.egg-info/'
    generated.update(egg + name for name in ('PKG-INFO', 'SOURCES.txt', 'dependency_links.txt', 'requires.txt', 'top_level.txt'))
    if set(files) - set(expected) != generated:
        raise ValueError('Unexpected or missing generated sdist content')
    check_metadata(BytesParser().parsebytes(files['PKG-INFO']), project)
    if files[egg + 'PKG-INFO'] != files['PKG-INFO']:
        raise ValueError('Inconsistent sdist metadata')
    return {'name': project['name'], 'version': project['version'], 'source_files': len(expected)}

# Preserve unchanged upstream notice filenames, only at reviewed vendor paths.
STATIC_VENDOR_NOTICES = frozenset({
    'vendor/charts/echarts/LICENSE', 'vendor/charts/echarts/NOTICE',
    'vendor/charts/echarts/LICENSE-d3', 'vendor/charts/uplot/LICENSE',
})


def static_files(source):
    result = {}
    for path in sorted((source / 'dist').rglob('*')):
        if path.is_symlink():
            raise ValueError('Symlink in static source')
        if not path.is_file():
            continue
        name = path.relative_to(source / 'dist').as_posix()
        safe_name(name)
        if name == STATIC_MARKER and path.read_bytes() != MARKER_CONTENT:
            raise ValueError('Unexpected export marker content')
        if name not in {STATIC_MARKER, *STATIC_VENDOR_NOTICES} and path.suffix.lower() not in STATIC_EXTENSIONS:
            raise ValueError('Unexpected static file type: ' + name)
        result[name] = path.read_bytes()
    if 'index.html' not in result:
        raise ValueError('Missing static index.html')
    return result

def pack_static(files, target, epoch):
    with target.open('wb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=epoch) as gz, tarfile.open(fileobj=gz, mode='w') as archive:
        for name, data in sorted(files.items()):
            safe_name(name)
            item = tarfile.TarInfo(name)
            item.size, item.mtime, item.mode = len(data), epoch, 0o644
            archive.addfile(item, io.BytesIO(data))

def read_static(target):
    result = {}
    with tarfile.open(target, 'r:gz') as archive:
        for item in archive:
            safe_name(item.name)
            if not item.isfile() or item.name in result or (item.name not in {STATIC_MARKER, *STATIC_VENDOR_NOTICES} and PurePosixPath(item.name).suffix.lower() not in STATIC_EXTENSIONS):
                raise ValueError('Unexpected static archive member')
            result[item.name] = archive.extractfile(item).read()
    return result

def source_identity(source, commit):
    if not SHA.fullmatch(commit):
        raise ValueError('Expected full lowercase commit SHA')
    actual = subprocess.check_output(['git','rev-parse','HEAD'], cwd=source, text=True).strip()
    if actual != commit:
        raise ValueError('Checkout does not match expected commit')
    if subprocess.check_output(['git','status','--porcelain','--untracked-files=normal'], cwd=source, text=True).strip():
        raise ValueError('Candidate build requires a clean checkout')
    project = tomllib.loads((source / 'django-theme/pyproject.toml').read_text())['project']
    module = ast.parse((source / 'django-theme/src/nova_admin/__init__.py').read_text())
    versions = [ast.literal_eval(node.value) for node in module.body if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == '__version__' for target in node.targets)]
    if versions != [project['version']]:
        raise ValueError('Runtime version differs from package metadata')
    return int(subprocess.check_output(['git','show','-s','--format=%ct','HEAD'], cwd=source, text=True).strip())

def verify(directory, source, commit):
    directory = Path(directory)
    manifest = json.loads((directory / 'MANIFEST.json').read_text())
    if manifest.get('schema') != 2 or not SHA.fullmatch(commit) or manifest.get('commit') != commit:
        raise ValueError('Artifact source identity mismatch')
    expected_names = {'MANIFEST.json','SHA256SUMS',*manifest['files']}
    actual_names = {p.name for p in directory.iterdir()}
    if actual_names != expected_names or any(not p.is_file() or p.is_symlink() for p in directory.iterdir()):
        raise ValueError('Unexpected or missing candidate files')
    for name, expected in manifest['files'].items():
        if len(safe_name(name).parts) != 1:
            raise ValueError('Expected flat candidate files')
        content = (directory / name).read_bytes()
        if digest(content) != expected['sha256'] or len(content) != expected['size']:
            raise ValueError('Candidate content mismatch: ' + name)
    checksums = ''.join(f"{item['sha256']}  {name}\n" for name,item in sorted(manifest['files'].items()))
    if (directory / 'SHA256SUMS').read_text() != checksums:
        raise ValueError('Checksum list does not match manifest')
    wheel_name = manifest['wheel']
    sdist_name = manifest['sdist']
    if set(manifest['files']) != {wheel_name, sdist_name, 'nova-static.tar.gz'} or not wheel_name.endswith('.whl') or not sdist_name.endswith('.tar.gz'):
        raise ValueError('Expected only theme wheel, sdist and static archive')
    wheel_info = wheel_check(directory / wheel_name, source)
    sdist_check(directory / sdist_name, source)
    if wheel_info['version'] != manifest['theme_version'] or json.loads((source / 'package.json').read_text())['version'] != manifest['preview_version']:
        raise ValueError('Manifest version mismatch')
    static = read_static(directory / 'nova-static.tar.gz')
    if static != static_files(source) or {name:digest(data) for name,data in static.items()} != manifest['static_files']:
        raise ValueError('Static artifact differs from source/manifest')
    source_identity(source, commit)
    if manifest['theme_files'] != {name:digest(data) for name,data in runtime_files(source).items()}:
        raise ValueError('Theme source manifest mismatch')
    if manifest['source_files'] != {name:digest(data) for name,data in sdist_files(source).items()}:
        raise ValueError('Sdist source manifest mismatch')
    return manifest

def build(source, output, commit):
    source, output = source.resolve(), output.resolve()
    if output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError('Artifact directory must be outside the source tree')
    epoch = source_identity(source, commit)
    output.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, SOURCE_DATE_EPOCH=str(epoch))
    with tempfile.TemporaryDirectory(prefix='nova-wheel-build-') as temp:
        stage = Path(temp) / 'theme'
        shutil.copytree(source / 'django-theme', stage, ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.sqlite3','*.sqlite3-*','.venv','build','dist','*.egg-info'))
        # build's default creates an sdist, then builds the wheel FROM that sdist.
        subprocess.run([sys.executable,'-m','build','--no-isolation','--outdir',str(output),str(stage)], check=True, env=env)
    wheels = list(output.glob('*.whl'))
    sdists = list(output.glob('*.tar.gz'))
    if len(wheels) != 1 or len(sdists) != 1:
        raise ValueError('Expected exactly one built wheel and sdist')
    info = wheel_check(wheels[0], source)
    sdist_check(sdists[0], source)
    static = static_files(source)
    pack_static(static, output / 'nova-static.tar.gz', epoch)
    payload = {p.name:{'sha256':digest(p.read_bytes()),'size':p.stat().st_size} for p in sorted(output.iterdir())}
    manifest = {'schema':2,'commit':commit,'source_date_epoch':epoch,'theme_version':info['version'],'preview_version':json.loads((source / 'package.json').read_text())['version'],
                'wheel':wheels[0].name,'sdist':sdists[0].name,'files':payload,'static_files':{k:digest(v) for k,v in static.items()},
                'theme_files':{k:digest(v) for k,v in runtime_files(source).items()},
                'source_files':{k:digest(v) for k,v in sdist_files(source).items()},
                'provenance':'unsigned content hashes; test completion is recorded separately'}
    (output / 'MANIFEST.json').write_text(json.dumps(manifest, indent=2)+'\n')
    (output / 'SHA256SUMS').write_text(''.join(f"{item['sha256']}  {name}\n" for name,item in sorted(payload.items())))
    return verify(output, source, commit)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['build','verify'])
    parser.add_argument('--source', type=Path, default=ROOT)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    args = parser.parse_args()
    result = build(args.source,args.directory,args.commit) if args.command == 'build' else verify(args.directory,args.source,args.commit)
    print(json.dumps({'status':'passed','commit':result['commit'],'theme':result['theme_version'],'preview':result['preview_version'],'files':result['files']},indent=2))

if __name__ == '__main__':
    main()
