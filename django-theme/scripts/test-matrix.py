#!/usr/bin/env python3
"""Serial, exact-version Django matrix. Run with Python 3.11+; stdlib only.

Every invocation owns a NEW explicit run directory. No existing virtualenv,
checkout file, demo database, global package, or interpreter is changed.
"""
import argparse
from datetime import datetime, timezone
from email.parser import BytesParser
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import tomllib
import zipfile

HERE = Path(__file__).resolve().parent
VERSION = re.compile(r"\d+\.\d+\.\d+\Z")
PACKAGE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\Z")
STEPS = ("venv", "install", "pipcheck", "provenance", "check", "migrations", "tests")
PROBE = (
    "import ensurepip,json,platform,sys,venv; "
    "print(json.dumps({'version':platform.python_version(),"
    "'implementation':platform.python_implementation(),'executable':sys.executable}))"
)


def clean_environment():
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("PYTHON", "PIP_", "DJANGO_", "NOVA_CAPTCHA_"))
           and k not in ("VIRTUAL_ENV", "VIRTUAL_ENV_PROMPT")}
    # pip's os.devnull setting disables all global/user/site config loading.
    # All other PIP_* variables were removed; index/cache are explicit arguments.
    env.update(PIP_CONFIG_FILE=os.devnull, PYTHONDONTWRITEBYTECODE="1")
    return env


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def finish_report(report, status, error=None):
    """Finalize only the directory owned by this invocation, including aborts."""
    finished = datetime.now(timezone.utc).isoformat()
    report.update(status=status, finished_at=finished)
    if error:
        report["error"] = error
    for result in report["results"]:
        if result["status"] != "running":
            continue
        result.update(status=status, finished_at=finished, error=error,
                      not_run=[name for name in STEPS if name not in result["steps"]])
        for step in result["steps"].values():
            if step.get("status") == "running":
                # The child may have been interrupted before returning a code.
                step.update(status=status, error=error, exit_code=None)
        try:
            write_json(Path(result["directory"]) / "result.json", result)
        except OSError as write_error:
            # Preserve the failure and partial variant in the aggregate even
            # when the variant directory is the location that became unwritable.
            result["report_write_error"] = str(write_error)
    write_json(Path(report["root"]) / "results.json", report)


def finish_after_abort(report, status, error):
    try:
        finish_report(report, status, error)
    except OSError as write_error:
        print(f"Could not finalize matrix report: {write_error}", file=sys.stderr)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path):
    manifest = read_json(path)
    if manifest.get("schema") != 1 or not manifest.get("cells"):
        raise ValueError("Expected matrix manifest schema 1 with at least one cell")
    ids = []
    for cell in manifest["cells"]:
        if set(cell) != {"python", "django"} or not all(
                isinstance(v, str) and VERSION.fullmatch(v) for v in cell.values()):
            raise ValueError(f"Invalid exact-version cell: {cell!r}")
        ids.append(cell_id(cell))
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate matrix cells")
    for profile in ("core", "captcha", "security", "slider", "upstream"):
        pins = manifest.get(profile)
        if not isinstance(pins, dict) or not pins:
            raise ValueError(f"Missing {profile} dependency pins")
        for name, version in pins.items():
            if not PACKAGE.fullmatch(name) or not isinstance(version, str) or not re.fullmatch(r"\d+(?:\.\d+)+", version):
                raise ValueError(f"Invalid dependency pin: {name!r}={version!r}")
    return manifest


def cell_id(cell):
    return f"{cell['python']}/{cell['django']}"


def parse_mapping(values, file_path=None):
    mapping = json.loads(os.environ.get("NOVA_MATRIX_PYTHONS", "{}"))
    if not isinstance(mapping, dict):
        raise ValueError("NOVA_MATRIX_PYTHONS must be a JSON object")
    if file_path:
        supplied = read_json(file_path)
        if not isinstance(supplied, dict):
            raise ValueError("Interpreter map must be a JSON object")
        mapping.update(supplied)
    for value in values:
        version, separator, executable = value.partition("=")
        if not separator:
            raise ValueError("--python must be EXACT_VERSION=/absolute/path/to/python")
        mapping[version] = executable
    for version, executable in mapping.items():
        if not VERSION.fullmatch(version) or not isinstance(executable, str) or not Path(executable).is_absolute():
            raise ValueError(f"Invalid interpreter mapping: {version!r}={executable!r}")
    return mapping


def probe_interpreters(cells, mapping):
    """Check EVERY needed runtime before creating any venv or run directory."""
    verified = {}
    for version in dict.fromkeys(cell["python"] for cell in cells):
        if version not in mapping:
            raise ValueError(f"Missing Python {version}; pass --python {version}=/absolute/path")
        executable = Path(mapping[version]).expanduser()
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise ValueError(f"Interpreter is not executable: {executable}")
        result = subprocess.run([str(executable), "-I", "-B", "-c", PROBE],
                                env=clean_environment(), text=True, capture_output=True,
                                check=True, timeout=30)
        actual = json.loads(result.stdout)
        if actual.get("version") != version or actual.get("implementation") != "CPython":
            raise ValueError(f"Expected CPython {version} at {executable}, got {actual}")
        verified[version] = {"requested_path": str(executable), **actual}
    return verified


def verify_inputs(source, root, wheel, modes):
    if root.exists():
        raise ValueError(f"Run root already exists; choose a fresh path: {root}")
    if root.is_relative_to(source) or source.is_relative_to(root):
        raise ValueError("Run root and source checkout must be separate directory trees")
    for required in ("pyproject.toml", "src/nova_admin/__init__.py", "demo/config/settings.py", "tests/__init__.py"):
        if not (source / required).is_file():
            raise ValueError(f"Source input is missing: {source / required}")
    project = tomllib.loads((source / "pyproject.toml").read_text())["project"]
    artifact = None
    if "wheel" in modes:
        if not wheel or not wheel.is_file() or wheel.suffix != ".whl":
            raise ValueError("Source + wheel is the default: supply an existing --wheel FILE.whl")
        with zipfile.ZipFile(wheel) as archive:
            paths = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
            if len(paths) != 1:
                raise ValueError("Expected exactly one wheel distribution")
            info = BytesParser().parsebytes(archive.read(paths[0]))
        if info["Name"] != project["name"] or info["Version"] != project["version"]:
            raise ValueError("Wheel name/version do not match source pyproject.toml")
        artifact = {"path": str(wheel), "sha256": sha256(wheel), "version": info["Version"]}
    return project["version"], artifact


def copy_harness(source, target):
    """Preserve tests' ../demo paths; never copy demo databases or old artifacts."""
    ignored = shutil.ignore_patterns("__pycache__", "*.pyc", "*.sqlite3", "*.sqlite3-*", "staticfiles", ".DS_Store")
    for name in ("demo", "tests"):
        shutil.copytree(source / name, target / name, ignore=ignored)


def settings_text(profile, test_db):
    parent = "tests.captcha_settings" if profile == "captcha" else "config.settings"
    database = {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}
    if profile == "captcha":
        database["TEST"] = {"NAME": str(test_db)}
    return f"from {parent} import *\nDATABASES = {{'default': {database!r}}}\n"


def pip_install_command(python, report, pins, args, cache):
    command = [str(python), "-I", "-B", "-m", "pip", "--disable-pip-version-check",
               "install", "--no-input", "--only-binary=:all:", "--no-deps",
               "--report", str(report), "--cache-dir", str(cache)]
    command += ["--no-index"] if args.no_index else ["--index-url", "https://pypi.org/simple"]
    for directory in args.find_links:
        command += ["--find-links", str(directory)]
    return command + pins


def record_step(result, name, command, cwd, env, timeout):
    log_path = Path(result["directory"]) / f"{name}.log"
    started = time.monotonic()
    step = {"command": command, "cwd": str(cwd), "log": str(log_path), "status": "running"}
    # Register before opening the log/launching the child, so the active step
    # and command survive a filesystem error or Ctrl-C.
    result["steps"][name] = step
    with log_path.open("w", encoding="utf-8") as log:
        try:
            process = subprocess.run(command, cwd=cwd, env=env, stdout=log,
                                     stderr=subprocess.STDOUT, timeout=timeout, check=False)
            step["exit_code"] = process.returncode
        except subprocess.TimeoutExpired:
            step.update(exit_code=124, error=f"Timed out after {timeout}s")
        except OSError as error:
            step.update(exit_code=127, error=str(error))
        finally:
            step["seconds"] = round(time.monotonic() - started, 3)
    step["status"] = "passed" if step["exit_code"] == 0 else "failed"
    if name == "tests":
        output = log_path.read_text(encoding="utf-8", errors="replace")
        count = re.search(r"Ran (\d+) tests? in", output)
        if count:
            step["tests_run"] = int(count.group(1))
        summary = re.search(r"^(OK(?: \([^\n]*\))?|FAILED[^\n]*)$", output, re.MULTILINE)
        if summary:
            step["unittest_summary"] = summary.group(1)
    print(f"{result['id']} {name}: {step['exit_code']}", flush=True)
    write_json(Path(result["directory"]) / "result.json", result)
    return step["exit_code"] == 0


def run_variant(cell, profile, mode, args, manifest, verified, version, harness, worker, cache, on_start):
    directory = args.root / f"python-{cell['python']}" / f"django-{cell['django']}" / profile / mode
    venv = directory / "venv"
    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    test_db = directory / "captcha-test.sqlite3"
    dependencies = {"Django": cell["django"], **manifest["core"]}
    if profile == "captcha":
        dependencies.update(manifest["captcha"])
    context = {**cell, "profile": profile, "mode": mode, "source": str(args.source),
               "venv": str(venv), "project_version": version, "dependencies": dependencies,
               "test_db": str(test_db), "provenance_file": str(directory / "provenance.json"),
               "import_paths": [str(directory), str(harness / "demo"), str(harness)]}
    if mode == "source":
        context["import_paths"].insert(0, str(args.source / "src"))
    result = {"id": f"{cell_id(cell)}/{profile}/{mode}", "directory": str(directory),
              "expected": context, "status": "running", "steps": {}}
    # The aggregate owns this same mutable object before any variant I/O.
    on_start(result)
    directory.mkdir(parents=True)
    context_file = directory / "context.json"
    write_json(context_file, context)
    (directory / "matrix_settings.py").write_text(settings_text(profile, test_db))
    env = clean_environment()
    target = verified[cell["python"]]["requested_path"]
    if not record_step(result, "venv", [target, "-I", "-B", "-m", "venv", str(venv)], directory, env, args.timeout):
        result["status"] = "failed"
        write_json(directory / "result.json", result)
        return result
    # --no-deps makes the reviewed pin set the entire application dependency set.
    # pip check below reports any incomplete future manifest immediately.
    pins = [f"{name}=={value}" for name, value in dependencies.items()]
    if mode == "wheel":
        pins.append(str(args.wheel))
    command = pip_install_command(python, directory / "pip-install-report.json", pins, args, cache)
    installed = record_step(result, "install", command, directory, env, args.timeout)
    if installed:
        check = [str(python), "-I", "-B", "-m", "pip", "--disable-pip-version-check", "check"]
        coherent = record_step(result, "pipcheck", check, directory, env, args.timeout)
        base = [str(python), "-I", "-B", str(worker), str(context_file)]
        provenance = record_step(result, "provenance", [*base, "provenance"], directory, env, args.timeout)
        if coherent and provenance:
            for step in ("check", "migrations", "tests"):
                record_step(result, step, [*base, step], directory, env, args.timeout)
    result["status"] = "passed" if len(result["steps"]) == 7 and all(
        step["exit_code"] == 0 for step in result["steps"].values()) else "failed"
    provenance_file = directory / "provenance.json"
    if provenance_file.exists():
        result["actual"] = read_json(provenance_file)
    write_json(directory / "result.json", result)
    return result


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--source", type=Path, default=HERE.parent, help="Read-only source checkout")
    result.add_argument("--manifest", type=Path, default=HERE / "test-matrix.json")
    result.add_argument("--root", type=Path, default=os.environ.get("NOVA_MATRIX_ROOT"), help="Required NEW run directory; refuses reuse")
    result.add_argument("--wheel", type=Path, help="Existing wheel; never built by this runner")
    result.add_argument("--python", action="append", default=[], metavar="VERSION=/ABS/PATH")
    result.add_argument("--interpreters", type=Path, help="JSON exact-version-to-absolute-path map")
    result.add_argument("--cell", action="append", default=[], help="Select PYTHON/DJANGO from manifest; repeatable")
    result.add_argument("--mode", choices=("both", "source", "wheel"), default="both")
    result.add_argument("--with-captcha", action="store_true", help="Add separate CAPTCHA source/wheel runs")
    result.add_argument("--find-links", action="append", type=Path, default=[], metavar="DIRECTORY", help="Local wheelhouse; repeatable")
    result.add_argument("--no-index", action="store_true", help="Offline installs from --find-links only")
    result.add_argument("--cache-dir", type=Path, help="Explicit pip cache directory; default ROOT/pip-cache")
    result.add_argument("--timeout", type=int, default=1200, help="Seconds per subprocess (default 1200)")
    result.add_argument("--preflight", action="store_true", help="Validate inputs and runtimes, print plan, create nothing")
    return result


def main(argv=None):
    cli = parser()
    args = cli.parse_args(argv)
    owns_root = False
    report = None
    try:
        if not args.root:
            raise ValueError("Supply --root or NOVA_MATRIX_ROOT with a new isolated directory")
        if args.timeout <= 0:
            raise ValueError("--timeout must be positive")
        args.root, args.source = args.root.resolve(), args.source.resolve()
        args.wheel = args.wheel.resolve() if args.wheel else None
        args.find_links = [directory.resolve() for directory in args.find_links]
        if any(not directory.is_dir() for directory in args.find_links):
            raise ValueError("Every --find-links must be an existing local directory")
        if args.no_index and not args.find_links:
            raise ValueError("--no-index requires a local --find-links wheelhouse")
        cache = args.cache_dir.resolve() if args.cache_dir else args.root / "pip-cache"
        if cache.is_relative_to(args.source):
            raise ValueError("pip cache must be outside the source checkout")
        manifest = load_manifest(args.manifest)
        requested = set(args.cell)
        unknown = requested - {cell_id(cell) for cell in manifest["cells"]}
        if unknown:
            raise ValueError(f"Unknown matrix cells: {sorted(unknown)}")
        cells = [cell for cell in manifest["cells"] if not requested or cell_id(cell) in requested]
        modes = ["source", "wheel"] if args.mode == "both" else [args.mode]
        profiles = ["core", "captcha"] if args.with_captcha else ["core"]
        version, artifact = verify_inputs(args.source, args.root, args.wheel, modes)
        verified = probe_interpreters(cells, parse_mapping(args.python, args.interpreters))
        report = {"schema": 1, "status": "preflight", "started_at": datetime.now(timezone.utc).isoformat(),
                  "source": str(args.source), "root": str(args.root), "project_version": version,
                  "wheel": artifact, "manifest": manifest, "interpreters": verified,
                  "selected_cells": cells, "modes": modes, "profiles": profiles,
                  "full_core_matrix": len(cells) == len(manifest["cells"]) and len(modes) == 2,
                  "network": {"index": None if args.no_index else "https://pypi.org/simple",
                              "find_links": [str(directory) for directory in args.find_links]},
                  "results": []}
        if args.preflight:
            print(json.dumps(report, indent=2))
            return 0
        # No directory/env creation occurs before all runtime probes succeed.
        args.root.mkdir(parents=True, exist_ok=False)
        owns_root = True
        report["status"] = "running"
        write_json(args.root / "results.json", report)
        harness = args.root / "harness"
        copy_harness(args.source, harness)
        worker = args.root / "matrix_worker.py"
        shutil.copyfile(HERE / "matrix_worker.py", worker)
        write_json(args.root / "manifest.json", manifest)
        for cell in cells:
            for profile in profiles:
                for mode in modes:
                    run_variant(cell, profile, mode, args, manifest, verified,
                                version, harness, worker, cache, report["results"].append)
                    write_json(args.root / "results.json", report)
        status = "passed" if all(result["status"] == "passed" for result in report["results"]) else "failed"
        finish_report(report, status)
        print(f"Matrix {report['status']}: {len(report['results'])} variants; {args.root / 'results.json'}")
        return 0 if report["status"] == "passed" else 1
    except KeyboardInterrupt:
        if owns_root:
            finish_after_abort(report, "interrupted", "Interrupted by user")
        return 130
    except Exception as error:
        if owns_root:
            finish_after_abort(report, "error", f"{type(error).__name__}: {error}")
        print(f"Matrix error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
