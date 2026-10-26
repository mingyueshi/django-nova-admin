import json
from datetime import timedelta
from unittest.mock import patch
from bs4 import BeautifulSoup
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import override
from django.utils.safestring import mark_safe
from django.template.loader import render_to_string
from nova_slider_captcha.models import Challenge
from nova_slider_captcha.services import issue, verify
from nova_admin.slider import NovaSliderWidget, SliderCaptchaAdminAuthenticationForm
from nova_admin.preferences import SESSION_KEY


@override_settings(ROOT_URLCONF='config.slider_urls', LANGUAGE_CODE='en')
class SliderLoginTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('slider-staff', password='synthetic-slider-only', is_staff=True)

    def setUp(self):
        cache.clear()

    def page(self, client=None):
        response = (client or self.client).get(reverse('admin:login'))
        self.assertEqual(response.status_code, 200)
        return response, BeautifulSoup(response.content, 'html.parser')

    def proof(self, client=None, purpose='login'):
        client = client or self.client
        init = client.get(reverse('nova_slider_captcha:init'))
        csrf = init.json()['csrfToken']
        issued = client.post(reverse('nova_slider_captcha:challenge'), json.dumps({'purpose': purpose}), content_type='application/json', HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(issued.status_code, 200)
        data = issued.json()
        # Only the isolated test inspects a server-side synthetic answer.
        x = Challenge.objects.get(pk=data['challengeId']).target_x
        solved = client.post(reverse('nova_slider_captcha:verify'), json.dumps({'challengeId': data['challengeId'], 'x': x}), content_type='application/json', HTTP_X_CSRFTOKEN=csrf)
        self.assertTrue(solved.json()['ok'])
        return solved.json()['token'], csrf

    def data(self, token='', **extra):
        return {'username': self.user.username, 'password': 'synthetic-slider-only', 'nova_slider_token': token, **extra}

    def test_component_single_field_native_disabled_and_dark(self):
        for mode in ('light', 'dark', 'native'):
            session = self.client.session
            session[SESSION_KEY] = mode
            session.save()
            response, soup = self.page()
            self.assertEqual(len(soup.select('nova-slider')), 1)
            self.assertEqual(soup.select_one('nova-slider')['purpose'], 'login')
            # Component owns the only hidden field at runtime.
            self.assertFalse(soup.select('input[name="nova_slider_token"]'))
            self.assertContains(response, 'nova_slider_captcha/slider.js')
        with override_settings(NOVA_ADMIN_ENABLED=False):
            self.assertEqual(len(self.page()[1].select('nova-slider')), 1)

    def test_missing_and_invalid_token_never_call_authentication(self):
        for token in ('', 'invalid', 'x' * 43):
            with self.subTest(token=token), patch('django.contrib.auth.forms.authenticate') as auth:
                response = self.client.post(reverse('admin:login'), self.data(token))
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context['form'].errors)
                auth.assert_not_called()

    @override_settings(LOCALE_PATHS=())
    def test_login_widget_renders_localized_accessible_name_and_noscript(self):
        messages = {
            'en': ('Security verification', 'JavaScript is required for this visual challenge.'),
            'zh-hans': ('安全验证', '此图形验证需要启用 JavaScript。'),
            'fr': ('Security verification', 'JavaScript is required for this visual challenge.'),
        }
        for language, (label, notice) in messages.items():
            with self.subTest(language=language), override(language):
                _, soup = self.page()
                self.assertEqual(soup.select_one('nova-slider')['aria-label'], label)
                self.assertIn(notice, soup.select_one('noscript').get_text())

    @override_settings(LOCALE_PATHS=())
    def test_missing_and_expired_proof_render_localized_errors_before_authentication(self):
        for language, message in (
            ('en', 'Security verification is missing, expired, or already used. Please try again.'),
            ('zh-hans', '安全验证缺失、已过期或已使用，请重试。'),
        ):
            with self.subTest(language=language), override(language):
                expired, _ = self.proof()
                Challenge.objects.filter(token_consumed=False).update(token_expires_at=timezone.now() - timedelta(seconds=1))
                for token in ('x' * 43, expired):
                    with self.subTest(expired=token == expired), patch('django.contrib.auth.forms.authenticate') as auth:
                        response = self.client.post(reverse('admin:login'), self.data(token))
                        self.assertContains(response, message)
                        form = response.context['form']
                        self.assertEqual(form.errors.as_data()['nova_slider_token'][0].code, 'captcha_invalid')
                        soup = BeautifulSoup(response.content, 'html.parser')
                        self.assertEqual(soup.select_one('nova-slider')['aria-invalid'], 'true')
                        self.assertEqual(soup.select_one('nova-slider')['aria-describedby'], 'id_nova_slider_token_error')
                        auth.assert_not_called()

    def test_real_solve_login_and_replay_rejection(self):
        token, _ = self.proof()
        result = self.client.post(reverse('admin:login'), self.data(token, next='/admin/auth/user/'))
        self.assertEqual(result.status_code, 302)
        self.assertEqual(result.url, '/admin/auth/user/')
        self.assertEqual(self.client.session['_auth_user_id'], str(self.user.pk))
        with patch('django.contrib.auth.forms.authenticate') as auth:
            self.client.post(reverse('admin:login'), self.data(token))
            auth.assert_not_called()

    def test_wrong_password_consumes_proof_before_retry(self):
        token, _ = self.proof()
        result = self.client.post(reverse('admin:login'), self.data(token, password='wrong'))
        self.assertEqual(result.status_code, 200)
        with patch('django.contrib.auth.forms.authenticate') as auth:
            self.client.post(reverse('admin:login'), self.data(token))
            auth.assert_not_called()

    def test_cross_session_wrong_purpose_and_expired_tokens_rejected(self):
        other = Client()
        for purpose, client in [('login', other), ('demo', self.client), ('login', self.client)]:
            token, _ = self.proof(client, purpose=purpose)
            if client is self.client and purpose == 'login':
                Challenge.objects.filter(token_consumed=False).update(token_expires_at=timezone.now() - timedelta(seconds=1))
            with self.subTest(purpose=purpose, other=client is other), patch('django.contrib.auth.forms.authenticate') as auth:
                response = self.client.post(reverse('admin:login'), self.data(token))
                self.assertEqual(response.status_code, 200)
                auth.assert_not_called()

    def test_login_and_slider_api_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        self.page(client)
        self.assertEqual(client.post(reverse('admin:login'), self.data()).status_code, 403)
        self.assertEqual(client.post(reverse('nova_slider_captcha:challenge'), '{}', content_type='application/json').status_code, 403)
        token, csrf = self.proof(client)
        self.assertEqual(client.post(reverse('admin:login'), self.data(token, csrfmiddlewaretoken=csrf)).status_code, 302)

    @override_settings(NOVA_ADMIN_CAPTCHA_POLICY='progressive')
    def test_progressive_http_flow_cannot_skip_required_slider(self):
        self.assertIsNone(self.page()[1].select_one('nova-slider'))
        for _ in range(2):
            response = self.client.post(reverse('admin:login'), self.data(password='wrong'))
        self.assertIsNotNone(BeautifulSoup(response.content, 'html.parser').select_one('nova-slider'))
        with patch('django.contrib.auth.forms.authenticate') as auth:
            self.client.post(reverse('admin:login'), self.data())
            auth.assert_not_called()
        token, _ = self.proof()
        self.assertEqual(self.client.post(reverse('admin:login'), self.data(token)).status_code, 302)

    def test_nonce_on_assets_and_one_login_form(self):
        form = SliderCaptchaAdminAuthenticationForm()
        html = render_to_string('nova_admin/slider_login.html', {'form': form, 'nova_admin_active': False, 'csp_nonce': 'synthetic-slider-nonce'})
        soup = BeautifulSoup(html, 'html.parser')
        for selector in ('script[src$="nova_slider_captcha/slider.js"]', 'link[href$="nova_slider_captcha/slider.css"]', 'link[href$="nova_admin/slider.css"]'):
            self.assertEqual(soup.select_one(selector).get('nonce'), 'synthetic-slider-nonce')
        self.assertEqual(len(soup.select('#login-form')), 1)
        self.assertEqual(len(soup.select('script[src$="nova_slider_captcha/slider.js"]')), 1)

    def test_prefixed_widget_binds_complete_field_name_and_login_consumes_proof(self):
        class PrefixedLoginForm(SliderCaptchaAdminAuthenticationForm):
            def __init__(self, *args, **kwargs):
                kwargs['prefix'] = 'auth'
                super().__init__(*args, **kwargs)

        self.page()  # Resolve the lazy site and URL configuration before patching.
        with patch.object(admin.site._wrapped, 'login_form', PrefixedLoginForm):
            _, soup = self.page()
            component = soup.select_one('nova-slider')
            self.assertEqual(component['field-name'], 'auth-nova_slider_token')
            self.assertEqual(component['id'], 'id_auth-nova_slider_token')
            self.assertFalse(soup.select('input[name$="nova_slider_token"]'))
            token, _ = self.proof()
            data = {'auth-username': self.user.username, 'auth-password': 'synthetic-slider-only',
                    component['field-name']: token}
            response = self.client.post(reverse('admin:login'), data)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(self.client.session['_auth_user_id'], str(self.user.pk))
            with patch('django.contrib.auth.forms.authenticate') as auth:
                self.client.post(reverse('admin:login'), data)
                auth.assert_not_called()

    def test_prefixed_form_rejects_unprefixed_token_before_authentication(self):
        token, _ = self.proof()
        request = self.client.get(reverse('admin:login')).wsgi_request
        with patch('django.contrib.auth.forms.authenticate') as auth:
            form = SliderCaptchaAdminAuthenticationForm(request=request, prefix='auth', data={
                'auth-username': self.user.username, 'auth-password': 'synthetic-slider-only',
                'nova_slider_token': token,
            })
            self.assertFalse(form.is_valid())
            self.assertIn('nova_slider_token', form.errors)
            auth.assert_not_called()
        self.assertFalse(Challenge.objects.get(token_consumed=False).token_consumed)

    @override_settings(LOCALE_PATHS=())
    def test_configured_alternative_is_outside_component_in_both_languages(self):
        for language, label in (('en', 'Use secure assistance'), ('zh-hans', '使用安全替代验证')):
            with self.subTest(language=language), override(language), override_settings(
                NOVA_SLIDER_ALTERNATIVE_URL='/secure-help/', NOVA_SLIDER_ALTERNATIVE_LABEL=label,
            ):
                _, soup = self.page()
                link = soup.select_one('.nsc-alternative a')
                self.assertEqual(link['href'], '/secure-help/')
                self.assertEqual(link.get_text(), label)
                self.assertIsNone(link.find_parent('nova-slider'))
                self.assertEqual(soup.select_one('nova-slider')['locale'], language)

    @override_settings(NOVA_SLIDER_ALTERNATIVE_URL=None, NOVA_SLIDER_ALTERNATIVE_LABEL=None)
    def test_unconfigured_alternative_stays_absent(self):
        self.assertIsNone(self.page()[1].select_one('.nsc-alternative'))

    def test_alternative_forces_escaping_even_for_safe_strings(self):
        url = mark_safe('/secure?next="\'><svg/onload=alert(1)>&a=1')
        label = mark_safe('<img src=x onerror=alert(1)> & "help"')
        with override_settings(NOVA_SLIDER_ALTERNATIVE_URL=url, NOVA_SLIDER_ALTERNATIVE_LABEL=label):
            _, soup = self.page()
        link = soup.select_one('.nsc-alternative a')
        self.assertEqual(link.attrs, {'href': str(url)})
        self.assertEqual(link.get_text(), str(label))
        self.assertFalse(link.find_all(True))
        self.assertFalse(soup.select('.nova-slider-form-widget svg, .nova-slider-form-widget img'))

    def test_unsafe_alternative_urls_are_omitted_without_removing_verification(self):
        for url in ('javascript:alert(1)', '//evil.invalid/', '/%2fevil.invalid/', '/\\evil.invalid/', '/bad%0apath'):
            with self.subTest(url=url), override_settings(
                NOVA_SLIDER_ALTERNATIVE_URL=url, NOVA_SLIDER_ALTERNATIVE_LABEL='Help',
            ):
                _, soup = self.page()
                self.assertIsNone(soup.select_one('.nsc-alternative'))
                self.assertEqual(soup.select_one('nova-slider')['field-name'], 'nova_slider_token')

    def test_widget_field_name_and_id_are_attribute_escaped(self):
        name = 'auth-\"><script>alert(1)</script>'
        soup = BeautifulSoup(NovaSliderWidget().render(name, None, {'id': name}), 'html.parser')
        component = soup.select_one('nova-slider')
        self.assertEqual(component['field-name'], name)
        self.assertEqual(component['id'], name)
        self.assertFalse(soup.select('script'))
