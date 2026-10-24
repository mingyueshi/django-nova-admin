#!/usr/bin/env python3
"""Check declared source requirements even when Django is used via PYTHONPATH."""
import argparse
import hashlib
from importlib import metadata, util
import json
from pathlib import Path
import platform
import sys
import tomllib

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import Version


def check_requirements(project, *, lookup=metadata.version, python=None, environment=None):
    python = python or platform.python_version()
    environment = default_environment() if environment is None else environment
    environment = {**environment, 'extra': ''}
    required_python = project['requires-python']
    python_ok = SpecifierSet(required_python).contains(Version(python), prereleases=True)
    rows = []
    for text in project['dependencies']:
        requirement = Requirement(text)
        row = {'requirement': text, 'name': requirement.name}
        if requirement.marker and not requirement.marker.evaluate(environment):
            row['status'] = 'not-applicable'
        elif requirement.url or requirement.extras:
            # Version metadata cannot establish URL provenance or extra deps.
            row['status'] = 'unverified-url-or-extra'
        else:
            try:
                installed = lookup(requirement.name)
            except metadata.PackageNotFoundError:
                row['status'] = 'missing'
            else:
                row['installed_version'] = installed
                row['status'] = ('satisfied' if requirement.specifier.contains(
                    Version(installed), prereleases=True,
                ) else 'version-mismatch')
        rows.append(row)
    return {
        'python': python, 'requires_python': required_python,
        'python_satisfied': python_ok, 'dependencies': rows,
        'requirements_satisfied': python_ok and all(
            row['status'] in {'satisfied', 'not-applicable'} for row in rows
        ),
    }


def inspect_source(source_root):
    source_root = source_root.resolve()
    content = (source_root / 'pyproject.toml').read_bytes()
    project = tomllib.loads(content.decode())['project']
    if project['name'] != 'Django':
        raise ValueError('Expected the official Django source project')
    result = check_requirements(project)
    spec = util.find_spec('django')
    origin = Path(spec.origin).resolve() if spec and spec.origin else None
    expected = source_root / 'django/__init__.py'
    result.update(
        source_root=str(source_root), pyproject_sha256=hashlib.sha256(content).hexdigest(),
        django_import_origin=str(origin) if origin else None,
        source_origin_matches=origin == expected,
    )
    result['status'] = ('satisfied' if result['requirements_satisfied'] and
                        result['source_origin_matches'] else 'unsatisfied')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error('Report already exists; use a new output path')
    try:
        report = inspect_source(args.source_root)
    except (OSError, ValueError, KeyError, TypeError, ImportError) as error:
        report = {'status': 'invalid', 'error': str(error)}
    report.update(schema=1, executable=sys.executable,
                  boundary='Declared base requirements and source origin only; not source regressions or support certification.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report))
    return int(report['status'] != 'satisfied')


if __name__ == '__main__':
    sys.exit(main())
