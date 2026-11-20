from .settings import *  # noqa: F403

ROOT_URLCONF = "config.reset_urls"
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = "nova-demo@localhost"
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "reset-demo.sqlite3"}}
LOGIN_URL = "admin:login"
