"""Isolated subprocess entry point for the matrix runner; stdlib until setup."""
import importlib.metadata as metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import sqlite3
import ssl
import sys
import sysconfig


def main():
    context = json.loads(Path(sys.argv[1]).read_text())
    step = sys.argv[2]
    # The parent uses -I: inherited PYTHONPATH, user site, and cwd are excluded.
    # Only this deliberately constructed test harness enters the import path.
    sys.path[:0] = context["import_paths"]
    os.environ["DJANGO_SETTINGS_MODULE"] = "matrix_settings"
    os.environ["NOVA_CAPTCHA_TEST_DB"] = context["test_db"]
    if step == "provenance":
        import django
        import nova_admin
        from django.conf import settings

        module = Path(nova_admin.__file__).resolve()
        expected = (Path(context["source"]) / "src" / "nova_admin" if
                    context["mode"] == "source" else
                    Path(sysconfig.get_path("purelib")) / "nova_admin").resolve()
        actual = {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "system": platform.system(),
            "machine": platform.machine(),
            "gil_enabled": getattr(sys, "_is_gil_enabled", lambda: True)(),
            "free_threaded_build": bool(sysconfig.get_config_var("Py_GIL_DISABLED")),
            "sqlite": sqlite3.sqlite_version,
            "openssl": ssl.OPENSSL_VERSION,
            "executable": sys.executable,
            "prefix": sys.prefix,
            "base_prefix": sys.base_prefix,
            "django": django.get_version(),
            "nova": nova_admin.__version__,
            "nova_module": str(module),
            "packages": dict(sorted((d.metadata["Name"], d.version)
                                    for d in metadata.distributions())),
            "database": settings.DATABASES["default"],
        }
        Path(context["provenance_file"]).write_text(json.dumps(actual, indent=2) + "\n")
        print(json.dumps(actual, indent=2), flush=True)
        assert actual["implementation"] == "CPython", actual
        assert actual["python"] == context["python"], actual
        assert actual["django"] == context["django"], actual
        assert actual["nova"] == context["project_version"], actual
        assert Path(sys.prefix).resolve() == Path(context["venv"]).resolve(), actual
        assert sys.prefix != sys.base_prefix, "Expected a disposable virtualenv"
        assert module.parent == expected, (module, expected)
        assert settings.DATABASES["default"]["NAME"] == ":memory:"
        for name, version in context["dependencies"].items():
            assert metadata.version(name) == version, name
        if context["profile"] == "core":
            assert importlib.util.find_spec("captcha") is None, "CAPTCHA leaked into core"
            assert importlib.util.find_spec("PIL") is None, "Pillow leaked into core"
        else:
            assert settings.DATABASES["default"]["TEST"]["NAME"] == context["test_db"]
            from PIL import features
            actual["pillow_freetype2"] = features.check("freetype2")
            Path(context["provenance_file"]).write_text(json.dumps(actual, indent=2) + "\n")
            assert actual["pillow_freetype2"], "CAPTCHA image generation requires FreeType"
        if context["mode"] == "wheel":
            assert metadata.version("nova-django-admin-theme") == context["project_version"]
            assert str(Path(context["source"]) / "src") not in sys.path, sys.path
        return

    from django.core.management import execute_from_command_line
    arguments = {
        "check": ["check"],
        "migrations": ["makemigrations", "--check", "--dry-run", "--noinput"],
        "tests": ["test", "tests" if context["profile"] == "core" else
                  "tests.test_captcha", "--verbosity", "2", "--noinput"],
    }
    execute_from_command_line(["django", *arguments[step]])


if __name__ == "__main__":
    main()
