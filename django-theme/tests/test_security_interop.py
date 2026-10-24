"""Real optional Axes integration; base Django-only runs deliberately skip."""
from unittest import skip
from unittest.mock import patch

from django.apps import apps
from django.test import SimpleTestCase


if not (apps.is_installed("axes") and apps.is_installed("captcha")):
    @skip("Optional security integration is not enabled")
    class SecurityNotEnabledTests(SimpleTestCase):
        def test_optional_integration(self):
            pass
else:
    from datetime import timedelta
    from inspect import unwrap

    from captcha.conf import settings as captcha_settings
    from axes.models import AccessAttempt
    from bs4 import BeautifulSoup
    from captcha.models import CaptchaStore
    from django.conf import settings
    from django.contrib import admin
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Permission
    from django.db.models import Sum
    from django.test import Client, RequestFactory, TestCase, override_settings
    from django.urls import NoReverseMatch, URLResolver, get_resolver, resolve, reverse
    from django.utils import timezone

    from nova_admin.axes import AxesCaptchaAdminAuthenticationForm
    from nova_admin.captcha import captcha_audio, _read_key, _sign_key


    @override_settings(LANGUAGE_CODE="en")
    class SecurityInteropTests(TestCase):
        @classmethod
        def setUpTestData(cls):
            User = get_user_model()
            cls.staff = User.objects.create_user("security-staff", password="synthetic-password", is_staff=True)
            cls.regular = User.objects.create_user("security-regular", password="synthetic-password")
            cls.inactive = User.objects.create_user("security-inactive", password="synthetic-password", is_staff=True, is_active=False)

        def data(self, username="security-staff", password="synthetic-password", answer=None):
            row = CaptchaStore.objects.create(challenge="ZXQTEST", response="zxqtest")
            return {
                "username": username, "password": password,
                "captcha_0": _sign_key(row.hashkey),
                "captcha_1": row.response if answer is None else answer,
            }

        def failures(self):
            return AccessAttempt.objects.aggregate(total=Sum("failures_since_start"))["total"] or 0

        def post(self, data, **kwargs):
            return self.client.post(reverse("admin:login"), data, **kwargs)

        def test_wrong_captcha_counts_once_without_password_authentication(self):
            data = self.data(answer="wrong-captcha-only")
            with patch("django.contrib.auth.forms.authenticate") as authenticate:
                response = self.post(data)
                authenticate.assert_not_called()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self.failures(), 1)
            self.assertNotIn("_auth_user_id", self.client.session)
            self.assertFalse(CaptchaStore.objects.filter(hashkey=_read_key(data["captcha_0"])).exists())

        def test_revalidating_same_form_does_not_double_count(self):
            data = self.data(answer="wrong")
            request = RequestFactory().post(reverse("admin:login"), data)
            form = AxesCaptchaAdminAuthenticationForm(request, data=data)
            self.assertFalse(form.is_valid())
            self.assertFalse(form.is_valid())
            self.assertEqual(self.failures(), 1)

        def test_password_failure_and_nonstaff_rejection_each_count_once(self):
            for data in (self.data(password="wrong-password"), self.data(username=self.regular.username)):
                before = self.failures()
                response = self.post(data)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.failures(), before + 1)
                self.assertTrue(response.context["form"].non_field_errors())
            self.assertNotIn("_auth_user_id", self.client.session)

        def test_missing_required_fields_are_also_counted(self):
            for data in ({}, self.data(password="")):
                response = self.post(data)
                self.assertEqual(response.status_code, 200)
            self.assertEqual(self.failures(), 2)

        def test_ip_lockout_stops_password_backend_and_challenge_generation(self):
            for index in range(settings.AXES_FAILURE_LIMIT):
                # Vary usernames: the IP-based policy includes unknown accounts.
                response = self.post(self.data(username=f"unknown-{index}", answer="wrong"))
                self.assertEqual(response.status_code, 429 if index == settings.AXES_FAILURE_LIMIT - 1 else 200)
            self.assertEqual(self.failures(), settings.AXES_FAILURE_LIMIT)
            count = CaptchaStore.objects.count()
            locked = self.client.get(reverse("admin:login"))
            self.assertEqual(locked.status_code, 429)
            self.assertIn("no-store", locked["Cache-Control"])
            self.assertEqual(CaptchaStore.objects.count(), count)
            with patch("django.contrib.auth.forms.authenticate") as authenticate:
                blocked = self.post(self.data())
                authenticate.assert_not_called()
            self.assertEqual(blocked.status_code, 429)
            self.assertNotIn("_auth_user_id", self.client.session)
            self.assertEqual(self.failures(), settings.AXES_FAILURE_LIMIT)

        def test_lockout_does_not_extend_fixed_cooloff_and_expiry_recovers(self):
            for _ in range(settings.AXES_FAILURE_LIMIT):
                self.post(self.data(answer="wrong"))
            before = list(AccessAttempt.objects.values_list("attempt_time", flat=True))
            self.assertEqual(self.post(self.data(answer="wrong")).status_code, 429)
            self.assertEqual(list(AccessAttempt.objects.values_list("attempt_time", flat=True)), before)
            AccessAttempt.objects.update(attempt_time=timezone.now() - timedelta(hours=1))
            response = self.post(self.data())
            self.assertEqual(response.status_code, 302)
            self.assertEqual(self.client.session["_auth_user_id"], str(self.staff.pk))
            self.assertEqual(self.failures(), 0)

        def test_form_adapter_preserves_cooloff_without_dispatch_wrapper(self):
            for _ in range(settings.AXES_FAILURE_LIMIT):
                self.post(self.data(answer="wrong"))
            before = list(AccessAttempt.objects.values_list("attempt_time", flat=True))
            data = self.data(answer="wrong")
            request = RequestFactory().post(reverse("admin:login"), data)
            self.assertFalse(AxesCaptchaAdminAuthenticationForm(request, data=data).is_valid())
            self.assertTrue(request.axes_locked_out)
            self.assertEqual(self.failures(), settings.AXES_FAILURE_LIMIT)
            self.assertEqual(list(AccessAttempt.objects.values_list("attempt_time", flat=True)), before)

        def test_success_resets_failures_and_keeps_native_safe_next(self):
            self.post(self.data(password="wrong"))
            data = self.data()
            data["next"] = "https://attacker.invalid/"
            response = self.post(data)
            self.assertRedirects(response, settings.LOGIN_REDIRECT_URL, fetch_redirect_response=False)
            self.assertEqual(self.failures(), 0)
            self.assertEqual(self.client.session["_auth_user_id"], str(self.staff.pk))

        def test_account_rejection_text_and_status_match(self):
            errors = []
            cases = [
                (self.staff.username, "wrong"), ("no-such-account", "synthetic-password"),
                (self.inactive.username, "synthetic-password"), (self.regular.username, "synthetic-password"),
            ]
            for index, (username, password) in enumerate(cases):
                response = self.post(self.data(username=username, password=password), REMOTE_ADDR=f"192.0.2.{index + 1}")
                self.assertEqual(response.status_code, 200)
                errors.append(list(response.context["form"].non_field_errors()))
            self.assertTrue(errors[0])
            self.assertTrue(all(error == errors[0] for error in errors))

        def test_forwarded_header_cannot_change_local_demo_lockout_identity(self):
            for index in range(settings.AXES_FAILURE_LIMIT):
                response = self.post(self.data(answer="wrong"), HTTP_X_FORWARDED_FOR=f"192.0.2.{index + 1}")
            self.assertEqual(response.status_code, 429)
            self.assertEqual(set(AccessAttempt.objects.values_list("ip_address", flat=True)), {"127.0.0.1"})
            response = self.post(self.data(), REMOTE_ADDR="192.0.2.100")
            self.assertEqual(response.status_code, 302)

        def test_sensitive_post_values_are_not_retained_in_axes_payload_logs(self):
            data = self.data(password="unique-password-marker", answer="unique-captcha-marker")
            data["csrfmiddlewaretoken"] = "unique-csrf-marker"
            self.post(data)
            record = AccessAttempt.objects.get()
            for key in ("password", "captcha_0", "captcha_1", "csrfmiddlewaretoken", "username"):
                self.assertNotIn(data[key], record.post_data)
            # Username/IP are deliberate Axes policy/audit fields, not anonymized.
            self.assertEqual(record.username, self.staff.username)
            self.assertEqual(record.ip_address, "127.0.0.1")

        def test_csrf_rejection_never_counts_as_a_credential_attempt(self):
            client = Client(enforce_csrf_checks=True)
            page = client.get(reverse("admin:login"))
            self.assertEqual(client.post(reverse("admin:login"), self.data()).status_code, 403)
            self.assertEqual(self.failures(), 0)
            soup = BeautifulSoup(page.content, "html.parser")
            token = soup.select_one('[name="captcha_0"]')["value"]
            data = self.data()
            data["captcha_0"] = token
            data["captcha_1"] = CaptchaStore.objects.get(hashkey=_read_key(token)).response
            data["csrfmiddlewaretoken"] = client.cookies["csrftoken"].value
            self.assertEqual(client.post(reverse("admin:login"), data).status_code, 302)

        def test_refresh_is_csrf_protected_and_locked_out_images_are_blocked(self):
            data = self.data()
            key = _read_key(data["captcha_0"])
            refresh = reverse("nova-captcha-refresh")
            self.assertEqual(Client(enforce_csrf_checks=True).post(refresh, {"key": data["captcha_0"]}).status_code, 403)
            self.assertEqual(self.client.post(refresh, {"key": data["captcha_0"]}).status_code, 200)
            for _ in range(settings.AXES_FAILURE_LIMIT):
                self.post(self.data(answer="wrong"))
            count = CaptchaStore.objects.count()
            self.assertEqual(self.client.post(refresh, {"key": "unused"}).status_code, 429)
            self.assertEqual(self.client.get(reverse("captcha-image", kwargs={"key": key})).status_code, 429)
            with patch("nova_admin.captcha._generate_audio") as generate:
                self.assertEqual(self.client.get(reverse("captcha-audio", kwargs={"key": key})).status_code, 429)
                generate.assert_not_called()
            self.assertEqual(CaptchaStore.objects.count(), count)

        def test_audio_mount_has_one_guarded_axes_wrapped_route(self):
            url = reverse("captcha-audio", kwargs={"key": "a" * 40})
            callback = resolve(url).func
            self.assertIsNot(callback, captcha_audio)
            self.assertIs(unwrap(callback), unwrap(captcha_audio))
            callbacks = []

            def visit(patterns):
                for pattern in patterns:
                    if isinstance(pattern, URLResolver):
                        visit(pattern.url_patterns)
                    elif pattern.name == "captcha-audio":
                        callbacks.append(pattern.callback)

            visit(get_resolver().url_patterns)
            self.assertEqual(callbacks, [callback])
            with self.assertRaises(NoReverseMatch):
                reverse("captcha-refresh")
            with patch.object(captcha_settings, "CAPTCHA_FLITE_PATH", "/synthetic/flite"), patch("nova_admin.captcha._generate_audio") as generate:
                response = self.client.get(url)
            self.assertEqual(response.status_code, 410)
            self.assertIn("no-store", response["Cache-Control"])
            generate.assert_not_called()

        def test_audit_admin_uses_native_model_permissions(self):
            log_url = reverse("admin:axes_accessattempt_changelist")
            self.client.force_login(self.staff)
            self.assertEqual(self.client.get(log_url).status_code, 403)
            self.staff.user_permissions.add(Permission.objects.get(codename="view_accessattempt"))
            self.assertEqual(self.client.get(log_url).status_code, 200)

        @override_settings(ROOT_URLCONF="tests.security_route_urls")
        def test_separate_decoy_namespace_does_not_replace_real_admin(self):
            # A route-isolation fixture, not proof of third-party compatibility.
            real = reverse("admin:login")
            decoy = reverse("admin_honeypot:login")
            self.assertEqual(real, "/staff-console/admin/login/")
            self.assertEqual(decoy, "/admin/login/")
            self.assertEqual(resolve(decoy).namespace, "admin_honeypot")
            page = self.client.get(real)
            soup = BeautifulSoup(page.content, "html.parser")
            self.assertEqual(soup.select_one("[data-nova-captcha]")["data-refresh-url"], "/staff-console/admin/_captcha/refresh/")
            image = self.client.get(soup.select_one("[data-captcha-image]")["src"])
            self.assertEqual(image.status_code, 200)
            self.assertEqual(image["Content-Type"], "image/png")
            self.assertFalse(soup.select("[data-captcha-audio]"))
            with patch("django.contrib.auth.forms.authenticate") as authenticate:
                response = self.client.post(decoy, self.data())
                authenticate.assert_not_called()
            self.assertContains(response, "routing sentinel")
            self.assertEqual(self.failures(), 0)
            self.assertEqual(self.client.post(real, self.data()).status_code, 302)
            self.assertEqual(admin.site.login_form, AxesCaptchaAdminAuthenticationForm)
