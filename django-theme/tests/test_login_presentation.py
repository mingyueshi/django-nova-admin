"""Native login semantics remain separate from the optional CAPTCHA extra."""
from unittest.mock import patch
from bs4 import BeautifulSoup
from django import forms
from django.contrib import admin
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import translation
from nova_admin.preferences import SESSION_KEY


class ExtraLoginForm(AdminAuthenticationForm):
    organization = forms.CharField(label='Organization', required=False)
    challenge_context = forms.CharField(widget=forms.HiddenInput, initial='synthetic-context')


class LoginPresentationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user('login-ui-staff', password='synthetic-login-ui-only', is_staff=True)

    def login_page(self, mode='light'):
        session = self.client.session
        session[SESSION_KEY] = mode
        session.save()
        return self.client.get(reverse('admin:login'))

    def test_chinese_brand_fields_and_focused_labels(self):
        with translation.override('zh-hans'):
            response = self.login_page()
        soup = BeautifulSoup(response.content, 'html.parser')
        self.assertEqual(soup.select_one('#nova-login-title').get_text(), '登录')
        self.assertIsNone(soup.select_one('.nova-login-brand'))
        self.assertNotIn('让管理井然有序', soup.get_text())
        self.assertIn('nova-login-visually-hidden', soup.select_one('#nova-login-title')['class'])
        self.assertEqual(soup.select_one('label[for="id_username"]').get_text(), '用户名：')
        self.assertEqual(soup.select_one('label[for="id_password"]').get_text(), '密码：')
        self.assertTrue(soup.select_one('[name="csrfmiddlewaretoken"]'))
        self.assertTrue(soup.select_one('[name="next"]'))
        self.assertEqual(soup.select_one('#id_password')['autocomplete'], 'current-password')
        self.assertEqual(soup.select_one('.nova-login-art')['aria-hidden'], 'true')

    def test_english_is_not_replaced_by_chinese_brand(self):
        with translation.override('en'):
            response = self.login_page()
        self.assertContains(response, '>Log in</h1>')
        self.assertNotContains(response, 'Everything in order.')
        self.assertNotContains(response, '欢迎回来')

    def test_dark_light_auto_load_one_scoped_login_sheet(self):
        for mode in ('dark', 'light', 'auto'):
            with self.subTest(mode=mode):
                response = self.login_page(mode)
                soup = BeautifulSoup(response.content, 'html.parser')
                self.assertIn('nova-mode-' + mode, soup.body['class'])
                self.assertEqual(len(soup.select('link[href$="nova_admin/login.css"]')), 1)
                self.assertEqual(len(soup.select('#login-form')), 1)

    def test_native_appearance_uses_native_content(self):
        response = self.login_page('native')
        self.assertContains(response, 'id="login-form"')
        self.assertNotContains(response, 'nova-login-layout')
        self.assertNotContains(response, 'nova_admin/login.css')

    @override_settings(NOVA_ADMIN_ENABLED=False)
    def test_theme_disabled_uses_native_content(self):
        response = self.login_page()
        self.assertContains(response, 'id="login-form"')
        self.assertNotContains(response, 'nova-login-layout')
        self.assertNotContains(response, 'nova_admin/login.css')

    def test_extra_visible_and_hidden_fields_survive_decorative_layout(self):
        with patch.object(admin.site, 'login_form', ExtraLoginForm):
            response = self.login_page()
        soup = BeautifulSoup(response.content, 'html.parser')
        self.assertTrue(soup.select_one('#login-form [name="organization"]'))
        hidden = soup.select_one('#login-form [name="challenge_context"]')
        self.assertEqual(hidden['type'], 'hidden')
        self.assertEqual(hidden['value'], 'synthetic-context')

    def test_real_native_login_still_requires_csrf_and_authentication(self):
        client = Client(enforce_csrf_checks=True)
        page = client.get(reverse('admin:login'))
        soup = BeautifulSoup(page.content, 'html.parser')
        data = {'username': self.staff.username, 'password': 'synthetic-login-ui-only', 'next': reverse('admin:index')}
        self.assertEqual(client.post(reverse('admin:login'), data).status_code, 403)
        data['csrfmiddlewaretoken'] = soup.select_one('[name="csrfmiddlewaretoken"]')['value']
        response = client.post(reverse('admin:login'), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('admin:index'))
        self.assertEqual(client.get(reverse('admin:index')).status_code, 200)

    def test_wrong_password_renders_native_errors_and_does_not_echo_password(self):
        response = self.client.post(reverse('admin:login'), {'username':self.staff.username, 'password':'wrong-synthetic-value'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertContains(response, 'errornote')
        self.assertNotContains(response, 'wrong-synthetic-value')
        soup = BeautifulSoup(response.content, 'html.parser')
        self.assertEqual(len(soup.select('#login-form')), 1)
        self.assertEqual(soup.select_one('#id_username')['value'], self.staff.username)
