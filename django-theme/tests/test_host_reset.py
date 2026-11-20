import re
from unittest.mock import patch
from urllib.parse import urlsplit

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(ROOT_URLCONF="config.reset_urls", LOGIN_URL="admin:login",
                   EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ResetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.staff = User.objects.create_user("staff", "staff@example.invalid", "old-secret", is_staff=True)
        User.objects.create_user("disabled", "inactive@example.invalid", "old-secret", is_active=False)
        User.objects.create_user("sso", "sso@example.invalid", password=None)

    def test_responses_and_complete_login(self):
        url = reverse("admin_password_reset")
        self.assertContains(self.client.get(reverse("admin:login")), url)
        for email in ("missing@example.invalid", "inactive@example.invalid", "sso@example.invalid", self.staff.email):
            response = self.client.post(url, {"email": email}, secure=True)
            self.assertRedirects(response, reverse("password_reset_done"))
            self.assertEqual(len(mail.outbox), int(email == self.staff.email))
        link = re.search(r"https://[^\s]+", mail.outbox[0].body).group()
        self.assertEqual(urlsplit(link).netloc, "testserver")
        token_url = urlsplit(link).path
        form_url = self.client.get(token_url).url
        secret = "New-demo-passphrase-42!"
        result = self.client.post(form_url, {"new_password1": secret, "new_password2": secret}, follow=True)
        self.assertContains(result, reverse("admin:login"))
        self.assertFalse(self.client.get(token_url).context["validlink"])
        self.assertFalse(self.client.login(username="staff", password="old-secret"))
        logged_in = self.client.post(reverse("admin:login"), {"username": "staff", "password": secret})
        self.assertEqual(logged_in.status_code, 302)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)

    @override_settings(PASSWORD_RESET_TIMEOUT=1)
    def test_expired_token(self):
        self.client.post(reverse("admin_password_reset"), {"email": self.staff.email})
        url = urlsplit(re.search(r"http://[^\s]+", mail.outbox[0].body).group()).path
        with patch.object(default_token_generator, "_num_seconds", return_value=2**40):
            self.assertFalse(self.client.get(url).context["validlink"])
