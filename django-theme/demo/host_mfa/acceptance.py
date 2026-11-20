from base64 import b32decode
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from axes.models import AccessAttempt
from captcha.models import CaptchaStore
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from django_otp.oath import totp
from django_otp.plugins.otp_static.lib import add_static_token
from django_otp.plugins.otp_static.models import StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice

from nova_admin.captcha import _sign_key


class SecondFactorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user("tester", password="demo-secret", is_staff=True)

    def login(self, token, method="totp", **data):
        challenge = CaptchaStore.objects.create(challenge="LOCAL", response="local")
        return self.client.post(reverse("admin:login"), {
            "username": self.user.username, "password": "demo-secret",
            "captcha_0": _sign_key(challenge.hashkey), "captcha_1": challenge.response,
            "otp_token": token, "factor": method, **data,
        })

    def test_password_only_session_cannot_open_dashboard_or_protected_views(self):
        self.client.force_login(self.user, backend="django.contrib.auth.backends.ModelBackend")
        for url in (reverse("admin:index"), reverse("admin:catalog_product_changelist"),
                    reverse("admin:catalog_product_status_board")):
            self.assertEqual(self.client.get(url).status_code, 302)
        self.client.logout()
        self.assertEqual(self.login("").status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_totp_replay_revocation_and_browser_session(self):
        device = TOTPDevice.objects.create(user=self.user, name="primary")
        token = f"{totp(device.bin_key):06d}"
        self.assertEqual(self.login(token).status_code, 302)
        self.assertTrue(self.client.session.get_expire_at_browser_close())
        self.assertEqual(self.client.cookies[settings.SESSION_COOKIE_NAME]["max-age"], "")
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)
        verified_client = self.client
        self.client = Client()
        self.assertEqual(self.login(token).status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
        device.refresh_from_db()
        device.confirmed = False
        device.save(update_fields=["confirmed"])
        self.assertEqual(verified_client.get(reverse("admin:index")).status_code, 302)
        self.assertEqual(self.login(f"{totp(device.bin_key):06d}").status_code, 200)

    def test_lost_device_recovery_single_use_persistent_cookie_and_expiry(self):
        recovery = add_static_token(self.user.username)
        self.assertEqual(self.login(recovery.token, "backup", remember="on").status_code, 302)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)
        self.assertEqual(self.client.session.get_expiry_age(), settings.MFA_REMEMBER_SECONDS)
        self.assertEqual(int(self.client.cookies[settings.SESSION_COOKIE_NAME]["max-age"]), settings.MFA_REMEMBER_SECONDS)
        self.assertFalse(StaticToken.objects.filter(pk=recovery.pk).exists())
        Session.objects.filter(session_key=self.client.session.session_key).update(expire_date=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 302)
        self.assertEqual(self.login(recovery.token, "backup").status_code, 200)

    def test_invalid_factor_counts_once_and_axes_blocks_even_valid_factor(self):
        device = TOTPDevice.objects.create(user=self.user, name="primary")
        for count in range(1, settings.AXES_FAILURE_LIMIT + 1):
            result = self.login("wrong-secret-code")
            self.assertEqual(result.status_code, 429 if count == settings.AXES_FAILURE_LIMIT else 200)
            attempt = AccessAttempt.objects.get()
            self.assertEqual(attempt.failures_since_start, count)
            self.assertNotIn("wrong-secret-code", attempt.post_data)
        self.assertEqual(self.login(f"{totp(device.bin_key):06d}").status_code, 429)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_operator_enrollment_rolls_back_bad_confirmation(self):
        with patch("host_mfa.management.commands.enroll_totp.getpass", return_value="invalid"):
            with self.assertRaises(CommandError):
                call_command("enroll_totp", self.user.username, stdout=StringIO())
        self.assertFalse(TOTPDevice.objects.exists())

    def test_operator_enrolls_only_one_confirmed_authenticator(self):
        output = StringIO()

        def current_code(prompt):
            key = b32decode(output.getvalue().splitlines()[-1])
            return f"{totp(key):06d}"

        with patch("host_mfa.management.commands.enroll_totp.getpass", side_effect=current_code):
            call_command("enroll_totp", self.user.username, stdout=output)
        self.assertTrue(TOTPDevice.objects.get(user=self.user).confirmed)
        with self.assertRaises(CommandError):
            call_command("enroll_totp", self.user.username, stdout=StringIO())
