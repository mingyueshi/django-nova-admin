"""Optional integration suite; use --settings=tests.captcha_settings.

Normal Django-only test runs skip this module without importing the extra.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

from bs4 import BeautifulSoup
from captcha.conf import settings as captcha_settings
from captcha.models import CaptchaStore
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import close_old_connections
from django.db.models.query import QuerySet
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from nova_admin.captcha import (
    CaptchaAdminAuthenticationForm, SingleUseCaptchaField, _consume, _read_key, _sign_key,
)
from nova_admin.preferences import SESSION_KEY


def challenge(answer="qwert"):
    row = CaptchaStore.objects.create(challenge=answer.upper(), response=answer)
    return row, _sign_key(row.hashkey)


class CaptchaValidationTests(TestCase):
    def data(self, token, answer):
        return {"username": "synthetic-user", "password": "synthetic-password", "captcha_0": token, "captcha_1": answer}

    def test_wrong_missing_expired_and_tampered_challenges_never_call_authenticate(self):
        row, token = challenge()
        expired, expired_token = challenge()
        CaptchaStore.objects.filter(pk=expired.pk).update(expiration=timezone.now() - timedelta(seconds=1))
        cases = [(token, "wrong"), ("", ""), (expired_token, "qwert"), (token + "x", "qwert")]
        for key, answer in cases:
            with self.subTest(key=key[:10]), patch("django.contrib.auth.forms.authenticate") as authenticate:
                form = CaptchaAdminAuthenticationForm(data=self.data(key, answer))
                self.assertFalse(form.is_valid())
                self.assertIn("captcha", form.errors)
                authenticate.assert_not_called()
        self.assertFalse(CaptchaStore.objects.filter(pk__in=[row.pk, expired.pk]).exists())

    def test_blank_answer_consumes_supplied_key(self):
        row, token = challenge()
        with self.assertRaises(ValidationError):
            SingleUseCaptchaField().clean([token, ""])
        self.assertFalse(CaptchaStore.objects.filter(pk=row.pk).exists())

    def test_correct_answer_is_case_insensitive_and_one_use(self):
        row, token = challenge()
        self.assertEqual(SingleUseCaptchaField().clean([token, " QWERT "]), [token, ""])
        with self.assertRaises(ValidationError):
            SingleUseCaptchaField().clean([token, "qwert"])
        self.assertFalse(CaptchaStore.objects.filter(pk=row.pk).exists())

    def test_wrong_answer_consumes_key_and_cannot_be_retried(self):
        _, token = challenge()
        for answer in ("wrong", "qwert"):
            with self.assertRaises(ValidationError):
                SingleUseCaptchaField().clean([token, answer])

    def test_unsigned_upstream_key_is_rejected(self):
        row, _ = challenge()
        with self.assertRaises(ValidationError):
            SingleUseCaptchaField().clean([row.hashkey, "qwert"])

    def test_test_mode_and_shared_pool_are_refused(self):
        for name in ("CAPTCHA_TEST_MODE", "CAPTCHA_GET_FROM_POOL"):
            with patch.object(captcha_settings, name, True), self.assertRaises(ImproperlyConfigured):
                SingleUseCaptchaField().clean(["anything", "PASSED"])

    def test_expiration_is_rechecked_after_claim(self):
        row, token = challenge()
        row.expiration = timezone.now() - timedelta(seconds=1)
        with patch("nova_admin.captcha._consume", return_value=row), self.assertRaises(ValidationError):
            SingleUseCaptchaField().clean([token, "qwert"])

    def test_delete_loser_is_rejected_even_if_both_requests_read_row(self):
        row, _ = challenge()
        with patch.object(QuerySet, "first", return_value=row):
            self.assertIsNotNone(_consume(row.hashkey))
            self.assertIsNone(_consume(row.hashkey))


@override_settings(ROOT_URLCONF="config.captcha_urls", LANGUAGE_CODE="en")
class CaptchaLoginTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.staff = User.objects.create_user(username="captcha-staff", password="synthetic-test-only", is_staff=True)
        cls.regular = User.objects.create_user(username="captcha-regular", password="synthetic-test-only")
        cls.inactive = User.objects.create_user(username="captcha-inactive", password="synthetic-test-only", is_staff=True, is_active=False)

    def read_form(self, client=None, query=None):
        response = (client or self.client).get(reverse("admin:login"), query or {})
        self.assertEqual(response.status_code, 200)
        soup = BeautifulSoup(response.content, "html.parser")
        token = soup.select_one('[name="captcha_0"]')["value"]
        row = CaptchaStore.objects.get(hashkey=_read_key(token))
        return response, soup, token, row

    def login_data(self, token, answer, username="captcha-staff", **extra):
        return {"username": username, "password": "synthetic-test-only", "captcha_0": token, "captcha_1": answer, **extra}

    def test_real_image_and_accessible_form_without_exposing_answer(self):
        with patch.object(captcha_settings, "CAPTCHA_CHALLENGE_FUNCT", lambda: ("QZXJKV", "qzxjkv")):
            response, soup, token, row = self.read_form()
        self.assertEqual(soup.select_one('label[for="id_captcha_1"]').get_text(strip=True), "Verification code:")
        self.assertEqual(soup.select_one('[name="captcha_1"]').get("autocomplete"), "off")
        self.assertIn("id_captcha_helptext", soup.select_one('[name="captcha_1"]').get("aria-describedby", ""))
        self.assertNotIn(row.response, token.lower())
        self.assertNotIn(row.response, str(soup.select_one('[data-nova-captcha]')).lower())
        self.assertFalse(soup.select('[data-captcha-audio]'))
        self.assertContains(response, settings.NOVA_ADMIN_CAPTCHA_HELP_TEXT)
        help_details = soup.select_one('details.nova-captcha-help')
        self.assertIsNotNone(help_details)
        self.assertFalse(help_details.has_attr('open'))
        self.assertIsNone(soup.select_one('[data-captcha-status]').find_parent('details'))
        self.assertIsNone(soup.select_one('[name="captcha_1"]').find_parent('details'))
        self.assertIsNone(soup.select_one('[data-captcha-refresh]').find_parent('details'))
        image = self.client.get(soup.select_one('[data-captcha-image]')["src"])
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image["Content-Type"], "image/png")
        self.assertTrue(image.content.startswith(b"\x89PNG"))
        self.assertContains(response, "nova_admin/captcha.js")
        self.assertContains(response, "nova_admin/captcha.css")

    def test_captcha_survives_native_and_disabled_theme(self):
        for mode in ("light", "dark", "native"):
            session = self.client.session
            session[SESSION_KEY] = mode
            session.save()
            response, _, _, _ = self.read_form()
            self.assertContains(response, 'name="captcha_1"')
        with override_settings(NOVA_ADMIN_ENABLED=False):
            response, _, _, _ = self.read_form()
            self.assertContains(response, 'name="captcha_1"')
            self.assertNotContains(response, "nova_admin/theme.css")

    def test_login_preserves_native_next_and_session_without_javascript(self):
        _, _, token, row = self.read_form()
        response = self.client.post(reverse("admin:login"), self.login_data(token, row.response, next="/admin/auth/user/"))
        self.assertRedirects(response, "/admin/auth/user/", fetch_redirect_response=False)
        self.assertEqual(self.client.session["_auth_user_id"], str(self.staff.pk))
        self.assertNotIn(row.response, str(dict(self.client.session)))

    def test_external_next_does_not_redirect_outside_site(self):
        _, _, token, row = self.read_form()
        response = self.client.post(reverse("admin:login"), self.login_data(token, row.response, next="https://attacker.invalid/"))
        self.assertRedirects(response, settings.LOGIN_REDIRECT_URL, fetch_redirect_response=False)

    def test_native_staff_inactive_and_wrong_password_checks_remain(self):
        for username, password in ((self.regular.username, "synthetic-test-only"), (self.inactive.username, "synthetic-test-only"), (self.staff.username, "wrong")):
            _, _, token, row = self.read_form()
            data = self.login_data(token, row.response, username=username)
            data["password"] = password
            response = self.client.post(reverse("admin:login"), data)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["form"].non_field_errors())
            self.assertNotIn("_auth_user_id", self.client.session)
            self.assertFalse(CaptchaStore.objects.filter(pk=row.pk).exists())
            fresh_token = BeautifulSoup(response.content, "html.parser").select_one('[name="captcha_0"]')["value"]
            self.assertNotEqual(fresh_token, token)

    def test_invalid_form_rerenders_fresh_token_and_error_relation(self):
        _, _, token, row = self.read_form()
        response = self.client.post(reverse("admin:login"), self.login_data(token, "wrong"))
        soup = BeautifulSoup(response.content, "html.parser")
        answer = soup.select_one('[name="captcha_1"]')
        self.assertEqual(answer.get("aria-invalid"), "true")
        self.assertIn("id_captcha_error", answer.get("aria-describedby", ""))
        self.assertTrue(soup.select_one("#id_captcha_error"))
        self.assertNotEqual(soup.select_one('[name="captcha_0"]')["value"], token)
        self.assertFalse(CaptchaStore.objects.filter(pk=row.pk).exists())

    def test_login_csrf_is_required(self):
        client = Client(enforce_csrf_checks=True)
        _, _, token, row = self.read_form(client)
        self.assertEqual(client.post(reverse("admin:login"), self.login_data(token, row.response)).status_code, 403)
        self.assertTrue(CaptchaStore.objects.filter(pk=row.pk).exists())
        response = client.post(reverse("admin:login"), self.login_data(token, row.response, csrfmiddlewaretoken=client.cookies["csrftoken"].value))
        self.assertEqual(response.status_code, 302)

    def test_refresh_requires_post_csrf_and_consumes_old_challenge_once(self):
        client = Client(enforce_csrf_checks=True)
        _, _, token, row = self.read_form(client)
        url = reverse("nova-captcha-refresh")
        self.assertEqual(client.get(url).status_code, 405)
        self.assertEqual(client.post(url, {"key": token}).status_code, 403)
        params = {"key": token, "csrfmiddlewaretoken": client.cookies["csrftoken"].value}
        response = client.post(url, params)
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        payload = response.json()
        self.assertEqual(set(payload), {"key", "image_url", "audio_url"})
        self.assertFalse(CaptchaStore.objects.filter(pk=row.pk).exists())
        self.assertEqual(client.post(url, params).status_code, 409)
        with self.assertRaises(ValidationError):
            SingleUseCaptchaField().clean([token, row.response])
        self.assertEqual(client.get(payload["image_url"]).status_code, 200)
        new = CaptchaStore.objects.get(hashkey=_read_key(payload["key"]))
        SingleUseCaptchaField().clean([payload["key"], new.response])

    def test_expired_challenge_can_be_refreshed_before_cleanup(self):
        _, _, token, row = self.read_form()
        CaptchaStore.objects.filter(pk=row.pk).update(expiration=timezone.now() - timedelta(days=1))
        self.assertEqual(self.client.post(reverse("nova-captcha-refresh"), {"key": token}).status_code, 200)

    def test_refresh_rejects_tampered_unsigned_or_missing_tokens(self):
        _, _, token, row = self.read_form()
        for value in ("", token + "x", row.hashkey, "x" * 1000):
            self.assertEqual(self.client.post(reverse("nova-captcha-refresh"), {"key": value}).status_code, 409)
        self.assertTrue(CaptchaStore.objects.filter(pk=row.pk).exists())

    def test_project_form_media_and_captcha_asset_nonce_are_preserved(self):
        class ProjectForm(CaptchaAdminAuthenticationForm):
            class Media:
                js = ["project/auth-device.js"]
        html = render_to_string("nova_admin/captcha_login.html", {
            "form": ProjectForm(), "nova_admin_active": False, "csp_nonce": "synthetic-nonce",
        })
        soup = BeautifulSoup(html, "html.parser")
        self.assertTrue(soup.select_one('script[src$="project/auth-device.js"]'))
        for selector in ('script[src$="nova_admin/captcha.js"]', 'link[href$="nova_admin/captcha.css"]'):
            self.assertEqual(soup.select_one(selector).get("nonce"), "synthetic-nonce")

    def test_repeated_login_submission_from_anonymous_client_cannot_reuse_key(self):
        _, _, token, row = self.read_form()
        data = self.login_data(token, row.response)
        self.assertEqual(self.client.post(reverse("admin:login"), data).status_code, 302)
        second = Client()
        with patch("django.contrib.auth.forms.authenticate") as authenticate:
            response = second.post(reverse("admin:login"), data)
            self.assertEqual(response.status_code, 200)
            self.assertIn("captcha", response.context["form"].errors)
            authenticate.assert_not_called()
        self.assertNotIn("_auth_user_id", second.session)

    def test_audio_link_only_when_project_configures_upstream_audio(self):
        with patch.object(captcha_settings, "CAPTCHA_FLITE_PATH", "/project-configured/flite"):
            response, soup, _, _ = self.read_form()
            self.assertTrue(soup.select_one('[data-captcha-audio]'))
            # Link construction only: absent Flite/SoX are not run in this environment.
            self.assertContains(response, "Listen to verification audio")


class CaptchaConcurrencyTests(TransactionTestCase):
    def test_concurrent_readers_have_exactly_one_successful_claim(self):
        row, token = challenge()
        barrier = Barrier(2)
        original_first = QuerySet.first
        def synchronized_first(query):
            result = original_first(query)
            if query.model is CaptchaStore:
                barrier.wait(timeout=10)
            return result
        def attempt():
            close_old_connections()
            try:
                try:
                    SingleUseCaptchaField().clean([token, row.response])
                    return True
                except ValidationError:
                    return False
            finally:
                close_old_connections()
        with patch.object(QuerySet, "first", synchronized_first), ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: attempt(), range(2)))
        self.assertEqual(sorted(results), [False, True])
        self.assertFalse(CaptchaStore.objects.filter(pk=row.pk).exists())
