"""Current response messages keep Django consumption, escaping and fallback."""
from copy import deepcopy

from bs4 import BeautifulSoup
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.messages.storage.base import Message
from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import translation
from django.utils.safestring import mark_safe

from nova_admin.preferences import SESSION_KEY
from nova_admin.templatetags.nova_tags import nova_message_groups


class Once:
    def __init__(self, items):
        self.items=items
        self.iterations=0

    def __iter__(self):
        self.iterations += 1
        if self.iterations > 1:
            raise AssertionError('Messages iterated more than once')
        yield from self.items


class MessageGroupingTests(SimpleTestCase):
    def test_group_by_real_level_and_preserve_first_group_and_message_order(self):
        source=Once([Message(20,'one',extra_tags='error'),Message(40,'two'),Message(20,'three'),Message(35,'custom',extra_tags='error')])
        groups=nova_message_groups(source)
        self.assertEqual(source.iterations,1)
        self.assertEqual([g['key'] for g in groups],['info','error','other'])
        self.assertEqual([str(m) for m in groups[0]['messages']],['one','three'])

    def test_template_consumes_one_shot_iterable_once_and_preserves_safe_data(self):
        source=Once([Message(20,'<script>unsafe()</script>'),Message(25,mark_safe('<a href="/admin/">safe link</a>'))])
        html=render_to_string('admin/base.html',{'nova_admin_active':True,'has_permission':True,'messages':source})
        self.assertEqual(source.iterations,1)
        soup=BeautifulSoup(html,'html.parser')
        contents=soup.select('.nova-message-content')
        self.assertEqual(contents[0].get_text(),'<script>unsafe()</script>')
        self.assertIsNone(contents[0].find('script'))
        self.assertEqual(contents[1].find('a')['href'],'/admin/')

    def test_empty_iterable_does_not_render_shell(self):
        source=Once([])
        html=render_to_string('admin/base.html',{'nova_admin_active':True,'has_permission':True,'messages':source})
        self.assertEqual(source.iterations,1)
        self.assertNotIn('data-nova-messages',html)
        self.assertNotIn('nova-messages-title',html)


def nonce_context(request):
    return {'csp_nonce':'message-test-nonce'}


@override_settings(ROOT_URLCONF='tests.message_urls',NOVA_ADMIN_ENABLED=True)
class MessageResponseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.viewer=get_user_model().objects.create_user(username='message-viewer',is_staff=True)
        cls.viewer.user_permissions.add(Permission.objects.get(content_type__app_label='catalog',codename='view_product'))

    def setUp(self):
        self.client.force_login(self.viewer)

    def page(self,url='/message-fixture/'):
        response=self.client.get(url)
        self.assertEqual(response.status_code,200)
        return response,BeautifulSoup(response.content,'html.parser')

    def test_all_seven_messages_visible_and_controls_initially_hidden(self):
        _,soup=self.page()
        self.assertEqual(len(soup.select('[data-nova-message-item]')),7)
        self.assertEqual(len(soup.select('[data-nova-message-group]')),6)
        for item in soup.select('[data-nova-message-item]'):
            self.assertNotIn('hidden',item.attrs)
            self.assertIn('hidden',item.select_one('[data-nova-message-dismiss]').attrs)
        for toggle in soup.select('[data-nova-message-toggle]'):
            self.assertEqual(toggle['aria-expanded'],'true')
            self.assertIn('hidden',toggle.attrs)
            self.assertIsNotNone(soup.find(id=toggle['aria-controls']))
        self.assertFalse(soup.select('[data-nova-messages] [aria-live], [data-nova-messages] [role="alert"]'))

    def test_extra_tags_do_not_impersonate_error_or_custom_level(self):
        _,soup=self.page()
        info=soup.select_one('[data-nova-message-group="info"]')
        self.assertEqual(len(info.select('.nova-message-item')),2)
        self.assertFalse(info.select('.error,.warning'))
        custom=soup.select_one('[data-nova-message-group="other"]')
        self.assertIsNotNone(custom)
        self.assertFalse(custom.select('.error,.warning'))
        self.assertIn('Custom fixture',custom.get_text())

    def test_native_storage_is_consumed_once_and_not_replayed_on_next_response(self):
        self.page()
        response=self.client.get(reverse('admin:index'))
        self.assertNotContains(response,'data-nova-messages')
        self.assertNotContains(response,'Success fixture')

    def test_redirected_storage_survives_until_destination_then_consumed(self):
        response=self.client.get('/message-redirect/')
        self.assertEqual(response.status_code,302)
        response=self.client.get(response['Location'])
        self.assertContains(response,'Success fixture',count=1)
        self.assertNotContains(self.client.get(reverse('admin:index')),'Success fixture')

    def test_native_disabled_and_popup_preserve_original_message_list(self):
        for mode in ('native','disabled','popup'):
            with self.subTest(mode=mode):
                session=self.client.session;session[SESSION_KEY]='native' if mode=='native' else 'light';session.save()
                with override_settings(NOVA_ADMIN_ENABLED=mode!='disabled'):
                    _,soup=self.page('/message-fixture/?_popup=1' if mode=='popup' else '/message-fixture/')
                self.assertIsNone(soup.select_one('[data-nova-messages]'))
                self.assertEqual(len(soup.select('ul.messagelist > li')),7)
                self.assertIsNotNone(soup.select_one('ul.messagelist a[href="/admin/"]'))
                self.assertFalse(soup.select('script[src$="nova_admin/messages.js"],link[href$="nova_admin/messages.css"]'))

    def test_anonymous_permission_fallback_has_native_text_and_no_controls(self):
        self.client.logout()
        response=self.client.get('/message-fixture/')
        self.assertEqual(response.status_code,302)
        html=render_to_string('admin/base.html',{'nova_admin_active':True,'has_permission':False,'messages':[Message(20,'anonymous notice')]})
        self.assertIn('Anonymous notice',html)
        self.assertNotIn('data-nova-messages',html)
        self.assertNotIn('nova_admin/messages.js',html)

    @override_settings(NOVA_ADMIN_URL_NAMESPACES={'warehouse':'warehouse_theme','review':'review_theme'})
    def test_current_adminsite_not_global_registry_controls_the_response(self):
        _,soup=self.page('/warehouse-message-fixture/')
        self.assertEqual(len(soup.select('[data-nova-message-item]')),7)
        self.assertEqual(soup.select_one('.nova-nav-home')['href'],reverse('warehouse:index'))
        self.assertEqual(soup.select_one('.nova-message-content a')['href'],'/admin/')

    def test_localized_heading_levels_and_controls(self):
        for language,title,label in [('en','Messages on this page','Collapse messages'),('zh-hans','本页消息','折叠消息')]:
            with self.subTest(language=language),translation.override(language):
                _,soup=self.page()
                self.assertEqual(soup.select_one('#nova-messages-title').get_text(),title)
                self.assertEqual(soup.select_one('[data-nova-message-toggle]').get_text(),label)

    def test_assets_use_nonce_and_external_deferred_script(self):
        templates=deepcopy(settings.TEMPLATES);templates[0]['OPTIONS']['context_processors'].append('tests.test_messages.nonce_context')
        with override_settings(TEMPLATES=templates):
            _,soup=self.page()
        script=soup.select_one('script[src$="nova_admin/messages.js"]')
        self.assertEqual(script['nonce'],'message-test-nonce')
        self.assertIn('defer',script.attrs)
        self.assertEqual(soup.select_one('link[href$="nova_admin/messages.css"]')['nonce'],'message-test-nonce')
