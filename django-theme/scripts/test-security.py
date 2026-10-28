#!/usr/bin/env python3
"""Offline wheel-only Axes and Slider interoperability with import provenance.

Example (run from django-theme):
  python scripts/test-security.py --wheel dist/nova_django_admin_theme-0.6.0-py3-none-any.whl \
    --python /path/to/python3.12 --root /tmp/nova-security-new \
    --wheelhouse /path/to/core-wheels --wheelhouse /path/to/axes-wheels

Only reviewed local wheels are installed, into newly created test environments.
The demo and tests are copied without databases; Nova must import from the wheel.
"""
import argparse
from email.parser import BytesParser
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import sysconfig
import tomllib
import zipfile


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def worker(context_path, step):
    context = json.loads(Path(context_path).read_text())
    # -I ignores PYTHONPATH, cwd and user-site packages. Add only the copied
    # test/demo harness: never the checkout's src directory.
    sys.path[:0] = context["import_paths"]
    os.environ["DJANGO_SETTINGS_MODULE"] = "security_matrix_settings"
    import django
    import nova_admin
    from django.conf import settings
    from django.core.management import call_command

    expected = Path(sysconfig.get_path("purelib")) / "nova_admin"
    module = Path(nova_admin.__file__).resolve()
    provenance = {
        "python": platform.python_version(), "django": django.get_version(),
        "nova": importlib.metadata.version("nova-django-admin-theme"),
        "nova_module": str(module), "wheel_sha256": context["wheel_sha256"],
        "dependencies": {name: importlib.metadata.version(name) for name in context["dependencies"]},
        "source_imports_allowed": False,
    }
    write_json(Path(context["directory"]) / "provenance.json", provenance)
    assert module.parent == expected.resolve(), (module, expected)
    assert Path(sys.prefix).resolve() == Path(context["venv"]).resolve()
    assert sys.prefix != sys.base_prefix
    assert provenance["python"] == context["python"]
    assert platform.python_implementation() == "CPython"
    assert provenance["django"] == context["django"]
    assert provenance["nova"] == context["version"]
    assert provenance["dependencies"] == context["dependencies"]
    assert settings.DATABASES["default"]["NAME"] == ":memory:"
    assert settings.DATABASES["default"]["TEST"]["NAME"] == context["test_db"]
    django.setup()
    from django.apps import apps
    if context['profile'] == 'slider':
        assert apps.is_installed('nova_slider_captcha'), 'Slider provider must be enabled'
    if step == "check":
        call_command("check")
    elif step == "migrations":
        call_command("makemigrations", check=True, dry_run=True, interactive=False)
    elif step == "tests":
        labels = (["tests.test_slider", "tests.test_captcha_policy"] if context['profile'] == 'slider'
                  else ["tests.test_security_interop"])
        call_command("test", *labels, verbosity=2, interactive=False)
    else:
        raise ValueError(step)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--expected-python", default="3.12.15", help="Exact CPython version required (default: 3.12.15)")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--wheelhouse", type=Path, action="append", required=True)
    parser.add_argument("--django", nargs="+", default=["5.2.17", "6.0.8", "6.1.1"])
    parser.add_argument("--profile", nargs="+", choices=["security", "slider"], default=["security", "slider"])
    args = parser.parse_args()
    if len(args.django) != len(set(args.django)):
        parser.error("--django must not contain duplicate version cells")
    source = Path(__file__).resolve().parent.parent
    args.root = args.root.resolve()
    args.wheel = args.wheel.resolve()
    args.python = args.python.resolve()
    if args.root.exists():
        parser.error("--root must be a new directory, so old evidence is never overwritten")
    if args.root.is_relative_to(source) or source.is_relative_to(args.root):
        parser.error("--root and the source checkout must be separate directory trees")
    if not args.wheel.is_file() or args.wheel.suffix != ".whl":
        parser.error("--wheel must identify an existing wheel")
    manifest = json.loads((source / "scripts/test-matrix.json").read_text())
    supported = {cell["django"] for cell in manifest["cells"]}
    if not set(args.django) <= supported:
        parser.error("Use exact Django versions from scripts/test-matrix.json")
    probe = subprocess.run(
        [str(args.python), "-I", "-c", "import json,platform;print(json.dumps([platform.python_implementation(),platform.python_version()]))"],
        capture_output=True, text=True, timeout=30,
    )
    if probe.returncode or json.loads(probe.stdout) != ["CPython", args.expected_python]:
        parser.error(f"--python must provide CPython {args.expected_python}")
    project = tomllib.loads((source / "pyproject.toml").read_text())["project"]
    with zipfile.ZipFile(args.wheel) as archive:
        entries = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(entries) != 1:
            parser.error("Expected one wheel distribution")
        metadata = BytesParser().parsebytes(archive.read(entries[0]))
    if (metadata["Name"], metadata["Version"]) != (project["name"], project["version"]):
        parser.error("Wheel name/version must match the source harness")
    wheel_hash = hashlib.sha256(args.wheel.read_bytes()).hexdigest()
    args.root.mkdir(parents=True)
    harness = args.root / "harness"
    ignored = shutil.ignore_patterns("__pycache__", "*.pyc", "*.sqlite3", "*.sqlite3-*", "staticfiles")
    for name in ("demo", "tests"):
        shutil.copytree(source / name, harness / name, ignore=ignored)
    script = args.root / "security_worker.py"
    shutil.copy2(__file__, script)
    env = {key: value for key, value in os.environ.items() if not key.startswith(("PYTHON", "DJANGO", "NOVA_", "PIP_"))}
    results = []
    for profile, version in ((profile, version) for profile in args.profile for version in args.django):
        directory = args.root / f'{profile}-{version}'
        directory.mkdir()
        venv = directory / "venv"
        python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        deps = {"Django": version, **manifest["core"],
                **(manifest['captcha'] if profile == 'security' else {}), **manifest[profile]}
        context = {
            "python": args.expected_python, "django": version, "profile": profile, "version": project["version"], "wheel_sha256": wheel_hash,
            "venv": str(venv), "directory": str(directory), "dependencies": deps,
            "test_db": str(directory / "security-test.sqlite3"),
            "import_paths": [str(directory), str(harness), str(harness / "demo")],
        }
        write_json(directory / "context.json", context)
        database = {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:", "TEST": {"NAME": context["test_db"]}}
        (directory / "security_matrix_settings.py").write_text(
            f"from {'config.security_settings' if profile == 'security' else 'tests.slider_settings'} import *\n"
            f"DATABASES = {{'default': {database!r}}}\nNOVA_DEMO_LOOPBACK_ONLY = False\n"
        )
        install = [str(python), "-I", "-m", "pip", "--disable-pip-version-check", "install", "--no-index", "--no-deps", "--only-binary=:all:"]
        for wheelhouse in args.wheelhouse:
            install.extend(["--find-links", str(wheelhouse.resolve())])
        install.extend([*[f"{name}=={value}" for name, value in deps.items()], str(args.wheel)])
        commands = {
            "venv": [str(args.python), "-I", "-m", "venv", str(venv)],
            "install": install,
            "pipcheck": [str(python), "-I", "-m", "pip", "check"],
        }
        # Separate processes prevent a prior management command's in-memory
        # SQLite connection from being reused by file-backed test DB setup.
        for step in ("check", "migrations", "tests"):
            commands[step] = [str(python), "-I", str(script), "--worker", str(directory / "context.json"), step]
        row = {"django": version, "profile": profile, "status": "running", "steps": {}}
        results.append(row)
        for name, command in commands.items():
            with (directory / f"{name}.log").open("w") as log:
                try:
                    result = subprocess.run(command, cwd=directory, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=180)
                    code = result.returncode
                except subprocess.TimeoutExpired:
                    code = 124
                except OSError as error:
                    log.write(str(error))
                    code = 127
            row["steps"][name] = {"exit_code": code, "command": command}
            if name == "tests":
                content = (directory / "tests.log").read_text()
                match = re.search(r"Ran (\d+) tests? in", content)
                row["steps"][name]["tests_run"] = int(match[1]) if match else None
                if not match or int(match[1]) == 0 or "\nOK\n" not in content or re.search(r'\bskipped\b', content):
                    code = code or 1
                    row["steps"][name]["exit_code"] = code
            if code:
                row["status"] = "failed"
                break
        else:
            row["status"] = "passed"
        write_json(args.root / "results.json", {"wheel": str(args.wheel), "wheel_sha256": wheel_hash, "results": results})
        print(f"{profile} / Django {version}: {row['status']}", flush=True)
    return int(any(row["status"] != "passed" for row in results))


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--worker":
        worker(sys.argv[2], sys.argv[3])
    else:
        raise SystemExit(main())
