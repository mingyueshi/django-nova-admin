#!/usr/bin/env python3
"""Run example-specific Django integration checks, without Docker/PostgreSQL."""
import argparse
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--captcha", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="nova-compose-tests-") as temporary:
        secret = Path(temporary) / "synthetic-key"
        secret.write_text(secrets.token_urlsafe(48))
        secret.chmod(0o600)
        env = dict(os.environ)
        env.update({
            "NOVA_DJANGO_SECRET_KEY_FILE": str(secret),
            "NOVA_POSTGRES_PASSWORD_FILE": str(secret),
            "NOVA_EXAMPLE_CAPTCHA": "1" if args.captcha else "0",
            "PYTHONPATH": os.pathsep.join(filter(None, (str(root), str(root / "django-theme" / "src"), str(root / "django-theme" / "demo"), env.get("PYTHONPATH")))),
        })
        subprocess.run([
            sys.executable, str(root / "django-theme" / "demo" / "manage.py"),
            "test", "examples.compose.test_django", "--settings=examples.compose.test_settings", "--noinput", "-v", "2",
        ], check=True, env=env, cwd=root)
    print("Passed example Django/SQLite checks. Docker image, Compose runtime and PostgreSQL remain untested by this script.")


if __name__ == "__main__":
    main()
