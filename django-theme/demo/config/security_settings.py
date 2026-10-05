"""Opt-in local Axes + CAPTCHA demonstration, never production settings."""
from datetime import timedelta

from .captcha_settings import *  # noqa: F403

INSTALLED_APPS = [*INSTALLED_APPS, "axes"]  # noqa: F405
MIDDLEWARE = [*MIDDLEWARE, "axes.middleware.AxesMiddleware"]  # noqa: F405
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]
ROOT_URLCONF = "config.security_urls"
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "security-demo.sqlite3"}}  # noqa: F405

# This local demo trusts only the connection's REMOTE_ADDR, never arbitrary
# X-Forwarded-For headers. Production reverse-proxy trust is project-specific.
AXES_CLIENT_IP_CALLABLE = "config.security_hooks.connection_ip"
AXES_LOCKOUT_PARAMETERS = ["ip_address"]
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=15)
AXES_RESET_ON_SUCCESS = True
AXES_RESET_COOL_OFF_ON_FAILURE_DURING_LOCKOUT = False
AXES_LOCKOUT_CALLABLE = "config.security_hooks.lockout_response"
AXES_SENSITIVE_PARAMETERS = [
    "username", "ip_address", "password", "captcha_0", "captcha_1",
    "csrfmiddlewaretoken", "key",
]
