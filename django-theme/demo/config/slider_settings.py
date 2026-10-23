"""Optional local slider demo; separate database, no preset accounts."""
from .settings import *  # noqa: F403

INSTALLED_APPS = [*INSTALLED_APPS, "nova_slider_captcha"]  # noqa: F405
ROOT_URLCONF = "config.slider_urls"
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "slider-demo.sqlite3"}}  # noqa: F405
NOVA_ADMIN_CAPTCHA_POLICY = "progressive"
NOVA_ADMIN_CAPTCHA_FAILURE_LIMIT = 2
