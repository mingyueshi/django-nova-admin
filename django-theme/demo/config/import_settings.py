from .settings import *  # noqa: F403

INSTALLED_APPS = [*INSTALLED_APPS, "stock_import"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "import-demo.sqlite3"}}
