"""Optional tests; the default Django-only suite skips without extra imports."""
from unittest import skip
from django.apps import apps
from django.test import SimpleTestCase

if apps.is_installed("captcha"):
    from .captcha_cases import (CaptchaValidationTests, CaptchaLoginTests, CaptchaConcurrencyTests)  # noqa: F401
else:
    @skip("Optional CAPTCHA integration is not enabled")
    class CaptchaNotEnabledTests(SimpleTestCase):
        def test_optional_integration(self):
            pass
