from .security_settings import *  # noqa: F403

INSTALLED_APPS = [
    "host_mfa.site.VerifiedAdminConfig" if app == "django.contrib.admin" else app for app in INSTALLED_APPS
] + ["django_otp", "django_otp.plugins.otp_totp", "django_otp.plugins.otp_static", "host_mfa"]
MIDDLEWARE = [*MIDDLEWARE[:-1], "django_otp.middleware.OTPMiddleware", MIDDLEWARE[-1]]
ROOT_URLCONF = "config.mfa_urls"
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "mfa-demo.sqlite3",
                         "OPTIONS": {"transaction_mode": "IMMEDIATE"}}}
AXES_SENSITIVE_PARAMETERS = [*AXES_SENSITIVE_PARAMETERS, "otp_token"]
OTP_ADMIN_HIDE_SENSITIVE_DATA = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = 8 * 60 * 60
MFA_REMEMBER_SECONDS = 7 * 24 * 60 * 60
