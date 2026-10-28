"""Isolated, loopback-only Compose example. Never use as deployment settings."""
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from .settings import *  # noqa: F403


def _secret_file(variable):
    filename = os.environ.get(variable)
    if not filename:
        raise ImproperlyConfigured(f"{variable} must point to a local secret file.")
    try:
        value = Path(filename).read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError) as error:
        raise ImproperlyConfigured(f"Cannot read {variable}.") from error
    if len(value) < 32 or "\n" in value or "\r" in value:
        raise ImproperlyConfigured(f"{variable} must contain one secret of at least 32 characters.")
    return value


SECRET_KEY = _secret_file("NOVA_DJANGO_SECRET_KEY_FILE")
DEBUG = True  # Required for this development server's local static-file serving.
# Docker's peer is its bridge; compose.yml enforces the loopback-only publish.
NOVA_DEMO_LOOPBACK_ONLY = False
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]
ROOT_URLCONF = "config.compose_urls"
DATABASES = {"default": {
    "ENGINE": "django.db.backends.postgresql",
    "HOST": "db", "PORT": "5432", "NAME": "nova_local", "USER": "nova_local",
    "PASSWORD": _secret_file("NOVA_POSTGRES_PASSWORD_FILE"),
    "CONN_MAX_AGE": 0,
    "OPTIONS": {"connect_timeout": 5},
}}
NOVA_ADMIN_URL_NAMESPACES = {"admin": "admin_theme", "warehouse": "warehouse_theme"}
_captcha = os.environ.get("NOVA_EXAMPLE_CAPTCHA", "0")
if _captcha not in {"0", "1"}:
    raise ImproperlyConfigured("NOVA_EXAMPLE_CAPTCHA must be 0 or 1.")
NOVA_EXAMPLE_CAPTCHA = _captcha == "1"
if NOVA_EXAMPLE_CAPTCHA:
    INSTALLED_APPS = [*INSTALLED_APPS, "captcha"]  # noqa: F405
CAPTCHA_TEST_MODE = False
CAPTCHA_GET_FROM_POOL = False
NOVA_ADMIN_CAPTCHA_HELP_TEXT = "本地示例未提供替代认证；无法使用图形验证码时，请由项目管理员配置可访问的登录流程。"

