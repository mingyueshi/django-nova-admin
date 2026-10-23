"""Opt-in real slider integration; core imports no optional provider."""
from unittest import skip
from django.apps import apps
from django.test import SimpleTestCase

if apps.is_installed('nova_slider_captcha'):
    from .slider_cases import SliderLoginTests  # noqa: F401
else:
    @skip('Optional slider CAPTCHA integration is not enabled')
    class SliderNotEnabledTests(SimpleTestCase):
        def test_optional_slider(self):
            pass
