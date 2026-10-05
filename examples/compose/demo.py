#!/usr/bin/env python3
"""Standard-library-only launcher. Never print credentials or run a shell."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import stat
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def project_name(directory):
    return "nova-local-" + hashlib.sha256(str(directory.resolve()).encode()).hexdigest()[:12]


def prepare_local(directory):
    local = directory / ".local"
    if local.is_symlink():
        raise ValueError("The local state directory must not be a symlink.")
    local.mkdir(mode=0o700, exist_ok=True)
    if os.name == "posix" and stat.S_IMODE(local.stat().st_mode) & 0o077:
        raise ValueError("The local state directory must be accessible only by its owner (mode 700).")
    for name in ("postgres_password", "django_secret_key"):
        path = local / name
        if path.is_symlink():
            raise ValueError("Secret files must not be symlinks.")
        if not path.exists():
            if (local / "options.json").exists():
                raise ValueError("An initialized example is missing a secret; restore it instead of rotating it implicitly.")
            # O_EXCL prevents overwriting a key or database password on reruns.
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(secrets.token_urlsafe(48) + "\n")
        if not path.is_file() or (os.name == "posix" and stat.S_IMODE(path.stat().st_mode) & 0o077):
            raise ValueError("Secret files must be regular files accessible only by their owner (mode 600).")
        value = path.read_text(encoding="utf-8").strip()
        if len(value) < 32 or "\n" in value or "\r" in value:
            raise ValueError("A secret file is invalid; refusing to replace existing credentials.")
    return local


def compose_environment(captcha, port):
    # Explicit project/file selectors keep unrelated COMPOSE_* state out.
    env = {key: value for key, value in os.environ.items() if not key.startswith("COMPOSE_")}
    env.update({
        "NOVA_EXAMPLE_CAPTCHA": "1" if captcha else "0", "NOVA_LOCAL_PORT": str(port),
        "NOVA_LOCAL_UID": str(os.getuid() if hasattr(os, "getuid") else 1000),
        "NOVA_LOCAL_GID": str(os.getgid() if hasattr(os, "getgid") else 1000),
    })
    return env


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("up", "down", "logs", "status", "config", "createsuperuser", "check"))
    captcha = parser.add_mutually_exclusive_group()
    captcha.add_argument("--captcha", dest="captcha", action="store_true", default=None)
    captcha.add_argument("--no-captcha", dest="captcha", action="store_false")
    parser.add_argument("--port", type=int)
    parser.add_argument("--create-superuser", action="store_true", help="After startup, run Django's interactive account creation")
    args = parser.parse_args(argv)
    if args.action != "up" and (args.captcha is not None or args.port is not None or args.create_superuser):
        parser.error("Startup options apply only to up")
    if args.port is not None and not 1024 <= args.port <= 65535:
        parser.error("--port must be between 1024 and 65535")
    docker = shutil.which("docker")
    if docker is None:
        parser.exit(2, "Docker with Compose v2 is required; no files or containers were created.\n")
    subprocess.run([docker, "compose", "version"], check=True, stdout=subprocess.DEVNULL)
    local = prepare_local(HERE)
    state_file = local / "options.json"
    if state_file.is_symlink():
        raise ValueError("The options file must not be a symlink.")
    state = json.loads(state_file.read_text()) if state_file.exists() else {"captcha": False, "port": 8000}
    if not isinstance(state.get("captcha"), bool) or type(state.get("port")) is not int or not 1024 <= state["port"] <= 65535:
        raise ValueError("Invalid local options file.")
    if args.captcha is not None:
        state["captcha"] = args.captcha
    if args.port is not None:
        state["port"] = args.port
    command = [docker, "compose", "--project-directory", str(HERE), "-p", project_name(HERE), "-f", str(HERE / "compose.yml")]
    actions = {
        "up": ["up", "--build", "--detach", "--wait", "--wait-timeout", "180"],
        "down": ["down"], "logs": ["logs", "--tail", "100"], "status": ["ps"],
        "config": ["config", "--quiet"],
        "createsuperuser": ["exec", "web", "python", "manage.py", "createsuperuser"],
        "check": ["exec", "web", "python", "manage.py", "check", "--database", "default"],
    }
    if args.action == "up":
        # Record intent before starting so logs/down can address a failed start.
        state_file.write_text(json.dumps(state) + "\n", encoding="utf-8")
    subprocess.run(command + actions[args.action], check=True, env=compose_environment(**state))
    if args.action == "up":
        print(f"Local example: http://127.0.0.1:{state['port']}/admin/ and /warehouse/")
        if args.create_superuser:
            subprocess.run(command + actions["createsuperuser"], check=True, env=compose_environment(**state))
        else:
            print("No login account was created. Run: python3 examples/compose/demo.py createsuperuser")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        # Do not include environment or secret-file contents in diagnostics.
        print(f"Local Compose action failed ({type(error).__name__}). Check Docker, file permissions, and the README.", file=sys.stderr)
        sys.exit(1)
