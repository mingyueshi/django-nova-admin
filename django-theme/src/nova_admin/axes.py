"""Explicit django-axes 8.3.1 bridge; never imported by the core theme.

Axes owns counters, storage, policy, backend blocking, and lockout responses.
This form only reports failures that Django's authenticate() cannot observe.
"""
from axes.conf import settings as axes_settings
from axes.handlers.proxy import AxesProxyHandler
from axes.helpers import get_credentials
from django.contrib.auth.signals import user_login_failed
from django.core.exceptions import ImproperlyConfigured, ValidationError

from .captcha import CaptchaAdminAuthenticationForm


class AxesCaptchaAdminAuthenticationForm(CaptchaAdminAuthenticationForm):
    """Preserve CAPTCHA-first validation and native admin authentication.

    Requires AxesStandaloneBackend first and AxesMiddleware last. Do not add
    another signal hook for the same failures: that would count them twice.
    """

    def _report_login_failure(self):
        if self.request is None:
            raise ImproperlyConfigured("The Axes CAPTCHA form requires a request.")
        credentials = get_credentials(username=self.cleaned_data.get("username"))
        # Mirror Axes' pre-existing-lockout handling without running any password
        # backend. Otherwise invalid CAPTCHA attempts could prolong a fixed
        # cooloff period even when the project has disabled that behavior.
        if (
            not AxesProxyHandler.is_allowed(self.request, credentials)
            and not axes_settings.AXES_RESET_COOL_OFF_ON_FAILURE_DURING_LOCKOUT
        ):
            self.request.axes_locked_out = True
        user_login_failed.send(
            sender=__name__, credentials=credentials, request=self.request,
        )

    def clean(self):
        if self.errors:
            # CAPTCHA/required-field rejection never reaches authenticate(), so
            # report exactly once here. Normal password failures are already
            # reported by Django and must not be reported a second time.
            self._report_login_failure()
            return self.cleaned_data
        return super().clean()

    def confirm_login_allowed(self, user):
        try:
            return super().confirm_login_allowed(user)
        except ValidationError:
            # Valid credentials for a nonstaff account also stop before login(),
            # after authenticate() succeeded. Keep the native generic error.
            self._report_login_failure()
            raise
