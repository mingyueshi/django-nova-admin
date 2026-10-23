"""Open-source SVGs retain fixed identifiers, escaping and native permissions."""
from importlib import resources
from django.template import Template, Context
from django.test import SimpleTestCase, override_settings
from nova_admin.icons import icon_names, icon_registry, render_icon
from nova_admin.navigation import extend_navigation


class OpenIconTests(SimpleTestCase):
    def test_all_reviewed_icons_render_with_local_geometry(self):
        self.assertEqual(len(icon_names()), 320)
        for name, entry in icon_registry().items():
            with self.subTest(name=name):
                result = render_icon(name, size=32, label='图标', stroke_width=2.5)
                self.assertIn(entry['body'], result)
                self.assertIn('width="32" height="32"', result)
                self.assertIn('stroke-width="0"' if entry['stroke'] == 'none' else 'stroke-width="2.5"', result)
                self.assertIn('viewBox="' + entry['viewBox'] + '"', result)
                self.assertIn('role="img" aria-label="图标"', result)

    def test_unknown_and_malformed_names_are_ignored(self):
        for value in (None, [], {}, True, '', 'search', '<svg onload=x>', 'lucide:missing'):
            with self.subTest(value=value):
                self.assertEqual(render_icon(value), '')

    def test_labels_are_escaped_and_decorative_icons_are_hidden(self):
        self.assertIn('aria-hidden="true"', render_icon('lucide:search'))
        result = render_icon('lucide:search', label='"><script>x</script>')
        self.assertNotIn('<script>', result)
        self.assertIn('&lt;script&gt;', result)

    def test_invalid_sizes_and_strokes_degrade_to_reviewed_defaults(self):
        for value in (None, True, {}, 'onload=x', -1, 999, float('nan'), float('inf')):
            with self.subTest(value=value):
                result = render_icon('heroicons:home', size=value, stroke_width=value)
                self.assertIn('width="20" height="20"', result)
                self.assertIn('stroke-width="1.5"', result)

    def test_template_tag_matches_public_renderer(self):
        template = Template('{% load nova_tags %}{% nova_icon "tabler:search" size=24 stroke_width=2 label="搜索" %}')
        self.assertEqual(template.render(Context()), render_icon('tabler:search',24,'搜索',2))

    def test_licensed_package_data_is_present(self):
        root = resources.files('nova_admin')
        self.assertTrue(root.joinpath('icons.json').is_file())
        for provider in ('lucide', 'tabler', 'heroicons', 'iconoir', 'bootstrap'):
            text = root.joinpath('licenses', f'{provider}.txt').read_text(encoding='utf-8')
            self.assertIn('Copyright', text)
            self.assertIn('Permission', text)

    @override_settings(NOVA_ADMIN_NAV_ICONS={'catalog':'tabler:folder','catalog.product':'lucide:shopping-bag','hidden.secret':'heroicons:lock-closed'})
    def test_namespaced_navigation_only_decorates_existing_visible_items(self):
        groups = [{'label':None,'apps':[{'app_label':'catalog','name':'Catalog','models':[{'object_name':'Product','name':'Products','admin_url':'/admin/catalog/product/'}]}]}]
        result = extend_navigation(groups)
        app = result['groups'][0]['apps'][0]
        self.assertEqual(app['nova_icon_name'],'tabler:folder')
        self.assertEqual(app['models'][0]['nova_icon_name'],'lucide:shopping-bag')
        self.assertIsNone(app['models'][0]['nova_icon_path'])
        self.assertEqual(len(result['groups'][0]['apps']),1)
        self.assertNotIn('nova_icon_name',groups[0]['apps'][0])

    def test_filled_icons_ignore_outline_stroke_and_retain_native_grid(self):
        template = Template('{% load nova_tags %}{% nova_icon "bootstrap:credit-card" size=16 stroke_width=3 %}')
        result = template.render(Context())
        self.assertIn('viewBox="0 0 16 16" fill="currentColor" stroke="none"', result)
        self.assertIn('stroke-width="0"', result)
        self.assertNotIn('stroke-width="3"', result)
        self.assertIn('stroke-width="1.5"', render_icon('iconoir:search'))
