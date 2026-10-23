"""Optional, server-side CAPTCHA escalation shared by image and slider forms.

This is an escalation policy, not a login rate limiter. Use a shared Django
cache for multiple workers, and keep the project's authentication controls.
"""
from django.conf import settings
from django.core.cache import caches
from django.core.exceptions import ImproperlyConfigured
from django.utils.crypto import salted_hmac


class CaptchaPolicyMixin:
    captcha_field_name = "captcha"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._nova_policy = getattr(settings, "NOVA_ADMIN_CAPTCHA_POLICY", "always")
        if self._nova_policy not in {"always", "progressive"}:
            raise ImproperlyConfigured("NOVA_ADMIN_CAPTCHA_POLICY must be 'always' or 'progressive'.")
        self._nova_captcha_field = self.fields[self.captcha_field_name]
        self._nova_failure_recorded = False
        self.captcha_required = True
        if self._nova_policy == "progressive":
            if self.request is None:
                raise ImproperlyConfigured("Progressive CAPTCHA requires the login request.")
            self._nova_limit = getattr(settings, "NOVA_ADMIN_CAPTCHA_FAILURE_LIMIT", 2)
            self._nova_window = getattr(settings, "NOVA_ADMIN_CAPTCHA_WINDOW", 900)
            if any(type(value) is not int or value < 1 for value in (self._nova_limit, self._nova_window)):
                raise ImproperlyConfigured("CAPTCHA failure limit and window must be positive integers.")
            self._nova_cache = caches[getattr(settings, "NOVA_ADMIN_CAPTCHA_CACHE", "default")]
            # No usernames or raw IP addresses in cache keys. Ignore untrusted
            # forwarded headers; the host must configure its trusted proxy.
            peer = self.request.META.get("REMOTE_ADDR", "unknown")
            self._nova_key = "nova-login-risk:" + salted_hmac("nova_admin.login-risk.v1", peer).hexdigest()
            count = self._nova_cache.get(self._nova_key, 0)
            if type(count) is not int or count < 0:
                raise ImproperlyConfigured("Invalid CAPTCHA risk counter.")
            risk_check = getattr(settings, "NOVA_ADMIN_CAPTCHA_RISK_CHECK", None)
            if risk_check is not None and not callable(risk_check):
                raise ImproperlyConfigured("NOVA_ADMIN_CAPTCHA_RISK_CHECK must be callable.")
            # A trusted server hook can escalate suspicious requests immediately.
            self.captcha_required = count >= self._nova_limit or bool(risk_check and risk_check(self.request))
            if not self.captcha_required:
                self.fields.pop(self.captcha_field_name)

    def clean(self):
        # AuthenticationForm.clean runs even after field errors. Failed CAPTCHA
        # must never reach authentication backends.
        if self.captcha_field_name in self.errors:
            return self.cleaned_data
        return super().clean()

    def full_clean(self):
        super().full_clean()
        if not self.is_bound or self._nova_policy != "progressive":
            return
        if self._errors:
            if not self._nova_failure_recorded:
                self._nova_failure_recorded = True
                if self._nova_cache.add(self._nova_key, 1, timeout=self._nova_window):
                    count = 1
                else:
                    try:
                        count = self._nova_cache.incr(self._nova_key)
                    except ValueError:
                        # Expiry between add/incr. Start a fresh window without
                        # overwriting a counter created by another request.
                        if self._nova_cache.add(self._nova_key, 1, timeout=self._nova_window):
                            count = 1
                        else:
                            count = self._nova_cache.incr(self._nova_key)
                if count >= self._nova_limit:
                    self.captcha_required = True
            if self.captcha_required:
                # Show the challenge in this very failure response, not only
                # after another GET. No validation error until the next submit.
                self.fields[self.captcha_field_name] = self._nova_captcha_field
        else:
            self._nova_cache.delete(self._nova_key)
