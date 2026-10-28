"""Real auth and shared-cache escalation; no optional CAPTCHA dependency."""
from unittest.mock import patch
from django import forms
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase, override_settings
from nova_admin.captcha_policy import CaptchaPolicyMixin


class PolicyForm(CaptchaPolicyMixin, AdminAuthenticationForm):
    captcha = forms.CharField()

    def clean_captcha(self):
        if self.cleaned_data['captcha'] != 'synthetic-proof':
            raise ValidationError('Invalid synthetic proof')
        return ''


@override_settings(NOVA_ADMIN_CAPTCHA_POLICY='progressive', NOVA_ADMIN_CAPTCHA_FAILURE_LIMIT=2)
class CaptchaPolicyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('policy-staff', password='synthetic-policy-only', is_staff=True)

    def setUp(self):
        cache.clear()

    def form(self, password='wrong', ip='192.0.2.8', **extra):
        request = RequestFactory().post('/admin/login/', REMOTE_ADDR=ip)
        return PolicyForm(request, data={'username': self.user.username, 'password': password, **extra})

    def escalate(self):
        self.assertFalse(self.form().is_valid())
        self.assertFalse(self.form().is_valid())

    def test_normal_login_skips_challenge_and_uses_real_auth(self):
        form = self.form('synthetic-policy-only')
        self.assertNotIn('captcha', form.fields)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.get_user(), self.user)

    def test_second_failure_renders_challenge_in_same_response(self):
        first = self.form()
        self.assertFalse(first.is_valid())
        self.assertNotIn('captcha', first.fields)
        second = self.form()
        self.assertFalse(second.is_valid())
        self.assertIn('captcha', second.fields)
        self.assertNotIn('captcha', second.errors)
        self.assertTrue(second.captcha_required)

    def test_new_session_or_client_flags_cannot_bypass_ip_gate(self):
        self.escalate()
        with patch('django.contrib.auth.forms.authenticate') as auth:
            form = self.form('synthetic-policy-only', captcha_required='false', captcha_policy='never')
            self.assertFalse(form.is_valid())
            self.assertIn('captcha', form.errors)
            auth.assert_not_called()

    def test_invalid_proof_blocks_password_backend(self):
        self.escalate()
        with patch('django.contrib.auth.forms.authenticate') as auth:
            self.assertFalse(self.form('synthetic-policy-only', captcha='bad').is_valid())
            auth.assert_not_called()

    def test_valid_proof_success_clears_risk(self):
        self.escalate()
        self.assertTrue(self.form('synthetic-policy-only', captcha='synthetic-proof').is_valid())
        self.assertNotIn('captcha', self.form().fields)

    def test_correct_proof_wrong_password_retains_gate(self):
        self.escalate()
        self.assertFalse(self.form(captcha='synthetic-proof').is_valid())
        self.assertIn('captcha', self.form().fields)

    def test_other_ip_is_not_gated_and_forwarded_header_does_not_reset(self):
        self.escalate()
        self.assertNotIn('captcha', self.form(ip='192.0.2.9').fields)
        request = RequestFactory().post('/admin/login/', REMOTE_ADDR='192.0.2.8', HTTP_X_FORWARDED_FOR='192.0.2.9')
        self.assertIn('captcha', PolicyForm(request).fields)

    @override_settings(NOVA_ADMIN_CAPTCHA_RISK_CHECK=lambda request: True)
    def test_trusted_risk_hook_escalates_immediately(self):
        self.assertIn('captcha', self.form().fields)

    def test_cache_failure_never_falls_back_to_password_only(self):
        with patch('nova_admin.captcha_policy.caches') as caches, patch('django.contrib.auth.forms.authenticate') as auth:
            caches.__getitem__.return_value.get.side_effect = RuntimeError('unavailable')
            with self.assertRaises(RuntimeError):
                self.form('synthetic-policy-only')
            auth.assert_not_called()

    def test_counter_records_one_failure_per_form(self):
        form = self.form()
        self.assertFalse(form.is_valid())
        self.assertFalse(form.is_valid())
        self.assertNotIn('captcha', self.form().fields)

    @override_settings(NOVA_ADMIN_CAPTCHA_POLICY='always')
    def test_default_compatible_always_mode(self):
        self.assertIn('captcha', self.form().fields)
        with patch('django.contrib.auth.forms.authenticate') as auth:
            self.assertFalse(self.form('synthetic-policy-only').is_valid())
            auth.assert_not_called()

    def test_bad_config_is_explicitly_rejected(self):
        for config in [{'NOVA_ADMIN_CAPTCHA_POLICY': 'never'}, {'NOVA_ADMIN_CAPTCHA_FAILURE_LIMIT': 0}, {'NOVA_ADMIN_CAPTCHA_WINDOW': True}, {'NOVA_ADMIN_CAPTCHA_RISK_CHECK': 'untrusted'}]:
            with self.subTest(config=config), override_settings(**config), self.assertRaises(ImproperlyConfigured):
                self.form()
        with self.assertRaises(ImproperlyConfigured):
            PolicyForm(data={'username': self.user.username, 'password': 'wrong'})

    def test_dirty_counter_is_reset_and_login_still_works(self):
        form = self.form()
        for value in ('dirty', None, -1, True):
            with self.subTest(value=value):
                cache.set(form._nova_key, value)
                self.assertTrue(self.form('synthetic-policy-only').is_valid())

    def test_repeated_counter_expiry_race_escalates_without_500(self):
        form = self.form()
        with patch.object(form._nova_cache, 'add', return_value=False), patch.object(form._nova_cache, 'incr', side_effect=ValueError('expired')):
            self.assertFalse(form.is_valid())
        self.assertIn('captcha', form.fields)
