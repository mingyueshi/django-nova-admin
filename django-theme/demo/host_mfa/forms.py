from django import forms
from django.conf import settings
from django.contrib.auth.signals import user_logged_in
from django.db import transaction
from django.dispatch import receiver
from django_otp.plugins.otp_static.models import StaticDevice
from django_otp.plugins.otp_totp.models import TOTPDevice

from nova_admin.axes import AxesCaptchaAdminAuthenticationForm


class SecondFactorForm(AxesCaptchaAdminAuthenticationForm):
    factor = forms.ChoiceField(label="验证方式", choices=[("totp", "验证器"), ("backup", "一次性恢复码")])
    otp_token = forms.CharField(label="动态码或恢复码", max_length=32,
                                widget=forms.PasswordInput(attrs={"autocomplete": "one-time-code"}))
    remember = forms.BooleanField(label="记住这次登录", required=False)

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        model = StaticDevice if self.cleaned_data["factor"] == "backup" else TOTPDevice
        # One confirmed device per method in this host example. Fail closed if ambiguous.
        with transaction.atomic():
            devices = list(model.objects.select_for_update().filter(user=user, confirmed=True)[:2])
            verified = len(devices) == 1 and devices[0].verify_token(self.cleaned_data["otp_token"])
        if not verified:
            self._report_login_failure()
            raise self.get_invalid_login_error()
        user.otp_device = devices[0]
        user.demo_session_expiry = settings.MFA_REMEMBER_SECONDS if self.cleaned_data["remember"] else 0


@receiver(user_logged_in, dispatch_uid="host_mfa.session_expiry")
def set_verified_session_expiry(sender, user, request, **kwargs):
    if hasattr(user, "demo_session_expiry"):
        request.session.set_expiry(user.demo_session_expiry)
