"""The appearance disclosure wraps the original, site-scoped POST form."""
from copy import deepcopy

from bs4 import BeautifulSoup
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import translation

from catalog.models import Product
from nova_admin.preferences import MODES, PALETTES, PALETTE_SESSION_KEY, SESSION_KEY


def nonce_context(request):
    return {'csp_nonce':'appearance-test-nonce'}


@override_settings(NOVA_ADMIN_ENABLED=True)
class AppearanceDisclosureTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.viewer=get_user_model().objects.create_user(username='appearance-viewer',is_staff=True)
        cls.viewer.user_permissions.add(Permission.objects.get(content_type__app_label='catalog',codename='view_product'))
        cls.product=Product.objects.create(name='Appearance product',sku='APPEARANCE-1',price=1)

    def setUp(self):
        self.client.force_login(self.viewer)
        self.url=reverse('admin:catalog_product_changelist')

    def page(self,url=None,query=None):
        response=self.client.get(url or self.url,query or {})
        self.assertEqual(response.status_code,200)
        return response,BeautifulSoup(response.content,'html.parser')

    def test_native_disclosure_starts_closed_and_has_one_original_form(self):
        _,soup=self.page()
        details=soup.select_one('details.nova-appearance')
        self.assertNotIn('open',details.attrs)
        self.assertIsNotNone(details.find('summary',recursive=False))
        self.assertEqual(len(details.select('form.nova-theme-switcher')),1)
        form=details.select_one('form')
        self.assertEqual(form['method'],'post')
        self.assertEqual(form['action'],reverse('nova_admin:preference'))
        self.assertIsNone(form.find_parent('form'))
        self.assertEqual({field['name'] for field in form.select('[name]')},{'csrfmiddlewaretoken','next','mode','palette'})
        self.assertEqual(len(form.select('[name="csrfmiddlewaretoken"]')),1)
        self.assertEqual([button.get('type') for button in form.select('button')],['submit'])

    def test_all_existing_modes_and_palettes_keep_original_ids_and_selection(self):
        session=self.client.session;session[SESSION_KEY]='auto';session[PALETTE_SESSION_KEY]='coffee';session.save()
        _,soup=self.page()
        form=soup.select_one('.nova-theme-switcher')
        mode=form.select_one('select#nova-admin-mode[name="mode"]');palette=form.select_one('select#nova-admin-palette[name="palette"]')
        self.assertEqual({item['value'] for item in mode.select('option')},set(MODES))
        self.assertEqual({item['value'] for item in palette.select('option')},set(PALETTES))
        self.assertEqual(mode.select_one('[selected]')['value'],'auto')
        self.assertEqual(palette.select_one('[selected]')['value'],'coffee')
        for element_id in ('nova-admin-mode','nova-admin-palette','nova-appearance-help'):
            self.assertEqual(len(soup.select('#'+element_id)),1)

    def test_safe_current_query_and_only_explicit_post_update_existing_preferences(self):
        destination=self.url+'?q=Appearance&o=3'
        _,soup=self.page(destination)
        form=soup.select_one('.nova-theme-switcher')
        self.assertEqual(form.select_one('[name="next"]')['value'],destination)
        self.assertNotIn(SESSION_KEY,self.client.session)
        self.assertNotIn(PALETTE_SESSION_KEY,self.client.session)
        response=self.client.post(form['action'],{'mode':'dark','palette':'plum','next':destination})
        self.assertEqual(response.status_code,302)
        self.assertEqual(response.url,destination)
        self.assertEqual(self.client.session[SESSION_KEY],'dark')
        self.assertEqual(self.client.session[PALETTE_SESSION_KEY],'plum')

    def test_native_mode_preserves_plain_recovery_form_and_all_choices(self):
        session=self.client.session;session[SESSION_KEY]='native';session.save()
        _,soup=self.page()
        self.assertIsNone(soup.select_one('.nova-appearance'))
        form=soup.select_one('.nova-theme-switcher')
        self.assertIsNotNone(form)
        self.assertEqual(form.select_one('#nova-admin-mode [selected]')['value'],'native')
        self.assertEqual(len(form.select('#nova-admin-palette option')),len(PALETTES))
        self.assertIsNone(soup.select_one('link[href$="nova_admin/appearance.css"]'))

    def test_disabled_missing_route_and_anonymous_have_no_dead_entry(self):
        for config in ({'NOVA_ADMIN_ENABLED':False},{'NOVA_ADMIN_URL_NAMESPACES':{'admin':'unmounted'}}):
            with self.subTest(config=config),override_settings(**config):
                _,soup=self.page()
                self.assertIsNone(soup.select_one('.nova-appearance,.nova-theme-switcher'))
        self.client.logout()
        _,soup=self.page(reverse('admin:login'))
        self.assertIsNone(soup.select_one('.nova-appearance,.nova-theme-switcher'))

    def test_popup_has_no_disclosure_or_appearance_resource(self):
        _,soup=self.page(query={'_popup':'1'})
        self.assertIsNone(soup.select_one('.nova-appearance,.nova-theme-switcher'))
        self.assertIsNone(soup.select_one('link[href$="nova_admin/appearance.css"]'))

    @override_settings(ROOT_URLCONF='tests.multisite_urls',NOVA_ADMIN_URL_NAMESPACES={'warehouse':'warehouse_theme','review':'review_theme'})
    def test_both_adminsites_keep_their_own_form_action_and_next(self):
        self.viewer.user_permissions.add(Permission.objects.get(content_type__app_label='catalog',codename='view_category'))
        for site in ('warehouse','review'):
            with self.subTest(site=site):
                url=reverse(f'{site}:catalog_product_changelist')+'?q=Appearance'
                _,soup=self.page(url)
                form=soup.select_one('.nova-appearance .nova-theme-switcher')
                self.assertEqual(form['action'],reverse(f'{site}_theme:preference'))
                self.assertEqual(form.select_one('[name="next"]')['value'],url)

    def test_disclosure_form_is_separate_from_the_business_edit_form(self):
        self.viewer.user_permissions.add(Permission.objects.get(content_type__app_label='catalog',codename='change_product'))
        _,soup=self.page(reverse('admin:catalog_product_change',args=[self.product.pk]))
        business=soup.select_one('form#product_form');appearance=soup.select_one('.nova-theme-switcher')
        self.assertIsNotNone(business)
        self.assertIsNone(appearance.find_parent('form'))
        self.assertFalse(business.select('.nova-theme-switcher,#nova-admin-mode,#nova-admin-palette'))

    def test_disclosure_and_help_are_localized_without_inline_handlers(self):
        for language,label in [('en','Appearance settings'),('zh-hans','外观设置')]:
            with self.subTest(language=language),translation.override(language):
                _,soup=self.page()
                self.assertIn(label,soup.select_one('.nova-appearance > summary').get_text())
                self.assertEqual(soup.select_one('.nova-theme-switcher')['aria-describedby'],'nova-appearance-help')
                self.assertTrue(soup.select_one('#nova-appearance-help').get_text())
                self.assertFalse(soup.select('.nova-appearance [onclick],.nova-appearance script'))

    def test_disclosure_css_keeps_external_nonce_support(self):
        templates=deepcopy(settings.TEMPLATES);templates[0]['OPTIONS']['context_processors'].append('tests.test_appearance.nonce_context')
        with override_settings(TEMPLATES=templates):
            _,soup=self.page()
        style=soup.select_one('link[href$="nova_admin/appearance.css"]')
        self.assertEqual(style['nonce'],'appearance-test-nonce')
        script=soup.select_one('script[src$="nova_admin/appearance.js"]')
        self.assertEqual(script['nonce'],'appearance-test-nonce')
        self.assertIn('defer',script.attrs)
