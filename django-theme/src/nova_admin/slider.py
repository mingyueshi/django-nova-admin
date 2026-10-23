"""Explicit opt-in adapter for the separate nova-slider-captcha package.

Import only after installing that package and enabling nova_slider_captcha.
Its database-backed consume() remains the verification authority.
"""
from copy import deepcopy

from django.contrib.admin.forms import AdminAuthenticationForm
from django.core.exceptions import ValidationError
from django.utils.translation import pgettext_lazy
from nova_slider_captcha.forms import SliderAdminAuthenticationForm, SliderCaptchaWidget
from nova_slider_captcha.services import consume

from .captcha_policy import CaptchaPolicyMixin


class NovaSliderWidget(SliderCaptchaWidget):
    template_name = "nova_admin/slider_widget.html"

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        context["widget"]["describedby"] = context["widget"]["attrs"].get("aria-describedby", "")
        context["widget"]["invalid"] = context["widget"]["attrs"].get("aria-invalid")
        return context

    class Media:
        # Loaded once by the login template with Nova's CSP nonce support.
        extend = False
        css = {}
        js = ()


class SliderCaptchaAdminAuthenticationForm(CaptchaPolicyMixin, AdminAuthenticationForm):
    captcha_field_name = "nova_slider_token"
    nova_slider_token = deepcopy(SliderAdminAuthenticationForm.base_fields["nova_slider_token"])
    nova_slider_token.widget = NovaSliderWidget()

    def clean_nova_slider_token(self):
        token = self.cleaned_data["nova_slider_token"]
        if self.request is None or not consume(token, self.request, purpose="login"):
            raise ValidationError(pgettext_lazy("Nova Admin", "Security verification is missing, expired, or already used. Please try again."), code="captcha_invalid")
        # Keep proof out of cleaned_data after one-time consumption.
        return ""
