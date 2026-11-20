from .settings import *  # noqa: F403

INSTALLED_APPS = [*INSTALLED_APPS, "host_audit"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "audit-demo.sqlite3"}}
