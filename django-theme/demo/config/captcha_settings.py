"""Optional local demonstration: synthetic development/test database only."""
from .settings import *  # noqa: F403

INSTALLED_APPS = [*INSTALLED_APPS, "captcha"]  # noqa: F405
ROOT_URLCONF = "config.captcha_urls"
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "captcha-demo.sqlite3"}}  # noqa: F405
CAPTCHA_TEST_MODE = False
CAPTCHA_GET_FROM_POOL = False
NOVA_ADMIN_CAPTCHA_HELP_TEXT = "无法使用图形验证码？请联系本站管理员，使用项目提供的其他登录方式。"
