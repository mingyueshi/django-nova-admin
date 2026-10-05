"""Native image-column contracts: local sources, auth, native UI and geometry."""
from datetime import date
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.staticfiles import finders
from django.forms import modelform_factory
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from catalog.media import MEDIA_SHEETS, local_media_url, media_thumbnail
from catalog.models import MemberProfile, NewsItem, Product
from tests.test_navigation_groups import NavigationElements


CASES = ((Product, "product", "image_key"), (MemberProfile, "avatar", "avatar_key"), (NewsItem, "cover", "cover_key"))


class LocalMediaContractTests(SimpleTestCase):
    def test_only_six_opaque_keys_are_accepted(self):
        for kind in MEDIA_SHEETS:
            for key in map(str, range(6)):
                with self.subTest(kind=kind, key=key):
                    self.assertEqual(local_media_url(kind, key), "/static/" + MEDIA_SHEETS[kind][0])

    def test_record_input_never_becomes_remote_source_or_path(self):
        for kind in MEDIA_SHEETS:
            for key in ("https://evil.invalid/x.png", "//evil.invalid/x", "../secret", "%2e%2e/secret", "data:image/svg+xml,x", '0" onerror="x', "6", "-1", "00", 0, None, []):
                with self.subTest(kind=kind, key=key):
                    self.assertIsNone(local_media_url(kind, key))
                    markup = str(media_thumbnail(kind, key, "Safe"))
                    self.assertNotIn("<img", markup)
                    self.assertIn("暂无图片", markup)

    def test_unsafe_static_storage_urls_fail_closed(self):
        for url in ("https://cdn.invalid/a.png", "//cdn.invalid/a.png", "/static/../private.png", "/static/%2e%2e/private.png", "/static/evil\\x.png", "/static/x.png?token=x", "/static/x.png#frag", "/static/\nx.png"):
            with self.subTest(url=url), patch("catalog.media.static", return_value=url):
                self.assertIsNone(local_media_url("avatar", "0"))

    def test_unknown_kind_is_rejected(self):
        self.assertIsNone(local_media_url("unsafe", "0"))
        with self.assertRaises(ValueError):
            media_thumbnail('avatar" onload="x', "0", "Safe")

    def test_all_labels_are_escaped_in_alt_and_missing_state(self):
        label = '<script>alert("x")</script> & "person"'
        for key in ("0", ""):
            markup = str(media_thumbnail("avatar", key, label))
            parsed = NavigationElements(markup)
            self.assertFalse(any(item["tag"] == "script" for item in parsed.elements))
            self.assertNotIn("<script>", markup)
            attrs = parsed.elements[2]["attrs"] if key else parsed.elements[0]["attrs"]
            if key:
                image = next(item for item in parsed.elements if item["tag"] == "img")
                self.assertEqual(image["attrs"]["alt"], label)
            else:
                self.assertEqual(attrs["aria-label"], label + "：暂无图片")

    def test_images_are_semantic_lazy_bounded_and_without_event_handlers(self):
        for kind in MEDIA_SHEETS:
            parsed = NavigationElements(str(media_thumbnail(kind, "5", "A fictional demo image")))
            image = next(item for item in parsed.elements if item["tag"] == "img")
            self.assertEqual(image["attrs"]["loading"], "lazy")
            self.assertEqual(image["attrs"]["decoding"], "async")
            self.assertTrue(image["attrs"]["alt"])
            self.assertGreater(int(image["attrs"]["width"]), 0)
            self.assertGreater(int(image["attrs"]["height"]), 0)
            self.assertFalse(any(key.startswith("on") for item in parsed.elements for key in item["attrs"]))
            self.assertTrue(parsed.with_class("nova-media-col-2"))
            self.assertTrue(parsed.with_class("nova-media-row-1"))

    def test_fixed_geometry_and_error_placeholder_do_not_depend_on_javascript(self):
        css = Path(finders.find("catalog/demo-media.css")).read_text()
        for contract in ("width: 44px; height: 44px; border-radius: 50%", "width: 60px; height: 60px", "width: 96px; height: 54px", "aspect-ratio: 16 / 9", "width: 300%; height: 200%", "overflow: hidden", ".nova-media-fallback", "forced-colors"):
            self.assertIn(contract, css)
        self.assertNotIn("url(", css)
        self.assertNotIn("@import", css)
        markup = str(media_thumbnail("cover", "2", "Demo cover"))
        self.assertIn("nova-media-fallback", markup)
        self.assertNotIn("onerror", markup)
        self.assertNotIn("<script", markup)

    def test_all_allowlisted_sheets_exist_and_have_verified_source_dimensions(self):
        import struct
        dimensions = {"avatar": (1536, 1024), "product": (1536, 1024), "cover": (2048, 768)}
        for kind, (relative, _, _) in MEDIA_SHEETS.items():
            path = finders.find(relative)
            self.assertIsNotNone(path)
            raw = Path(path).read_bytes()
            self.assertEqual(raw[:4], b"RIFF")
            self.assertEqual(raw[8:16], b"WEBPVP8 ")
            self.assertEqual(tuple(n & 0x3fff for n in struct.unpack("<HH", raw[26:30])), dimensions[kind])


class NativeMediaWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser(username="media-admin", password=None)
        cls.staff = get_user_model().objects.create_user(username="media-staff", is_staff=True, password=None)
        cls.product = Product.objects.create(name="Keyboard sample", sku="MEDIA-001", price="99", image_key="0")
        cls.member = MemberProfile.objects.create(name="Fictional adult Alpha", member_code="ADULT-001", avatar_key="0", joined_at=date(2026, 9, 1))
        cls.news = NewsItem.objects.create(title="Museum sample", cover_key="0", section="design", status="published", published_on=date(2026, 10, 1))

    def setUp(self):
        self.client.force_login(self.user)

    def list_url(self, model):
        return reverse(f"admin:catalog_{model._meta.model_name}_changelist")

    def change_url(self, obj):
        return reverse(f"admin:catalog_{obj._meta.model_name}_change", args=[obj.pk])

    def set_mode(self, mode):
        session = self.client.session
        session["nova_admin_mode"] = mode
        session.save()

    def test_all_shapes_render_from_real_list_display_in_three_modes(self):
        for mode in ("dark", "light", "native"):
            self.set_mode(mode)
            for model, kind, _ in CASES:
                with self.subTest(mode=mode, model=model):
                    response = self.client.get(self.list_url(model))
                    self.assertEqual(response.status_code, 200)
                    self.assertContains(response, f"nova-media-thumb--{kind}")
                    self.assertContains(response, 'class="field-image_thumbnail"')
                    self.assertContains(response, 'loading="lazy"')
                    self.assertContains(response, "catalog/demo-media.css")
                    self.assertTrue(any(callable(column) and column.__name__ == "image_thumbnail" for column in response.context["cl"].list_display))
                    if mode == "native":
                        self.assertNotContains(response, "nova_admin/theme.css")

    def test_thumbnail_links_use_authorized_change_views_and_preserve_query(self):
        for obj, query in ((self.product, "Keyboard"), (self.member, "Alpha"), (self.news, "Museum")):
            response = self.client.get(self.list_url(type(obj)), {"q": query, "o": "1"})
            parsed = NavigationElements(response.content.decode())
            link = parsed.with_class("nova-media-link")[0]
            parts = urlsplit(link["attrs"]["href"])
            self.assertEqual(parts.path, self.change_url(obj))
            preserved = parse_qs(parse_qs(parts.query)["_changelist_filters"][0])
            self.assertEqual(preserved, {"q": [query], "o": ["1"]})
            self.assertEqual(self.client.get(link["attrs"]["href"]).status_code, 200)

    def test_anonymous_and_nonstaff_cannot_read_lists_or_link_targets(self):
        nonstaff = get_user_model().objects.create_user(username="media-nonstaff", password=None)
        for user in (None, nonstaff):
            client = Client()
            if user:
                client.force_login(user)
            for obj in (self.product, self.member, self.news):
                for url in (self.list_url(type(obj)), self.change_url(obj)):
                    response = client.get(url)
                    self.assertEqual(response.status_code, 302)
                    self.assertIn("/admin/login/", response.url)
                    self.assertNotContains(response, "nova-media-thumb", status_code=302)

    def test_staff_without_model_permission_cannot_read_lists_or_links(self):
        self.client.force_login(self.staff)
        for obj in (self.product, self.member, self.news):
            self.assertEqual(self.client.get(self.list_url(type(obj))).status_code, 403)
            self.assertEqual(self.client.get(self.change_url(obj)).status_code, 403)
        index = self.client.get(reverse("admin:index"))
        self.assertNotContains(index, self.list_url(MemberProfile))
        self.assertNotContains(index, self.list_url(NewsItem))

    def test_view_only_permission_allows_images_but_not_changes(self):
        self.staff.user_permissions.add(*Permission.objects.filter(content_type__app_label="catalog", codename__in=["view_product", "view_memberprofile", "view_newsitem"]))
        self.client.force_login(self.staff)
        for obj in (self.product, self.member, self.news):
            self.assertContains(self.client.get(self.list_url(type(obj))), "nova-media-link")
            change = self.client.get(self.change_url(obj))
            self.assertEqual(change.status_code, 200)
            self.assertNotContains(change, 'name="_save"')
            self.assertEqual(self.client.post(self.change_url(obj), {"_save": "Save"}).status_code, 403)

    def test_hidden_queryset_records_do_not_leak_names_images_or_links(self):
        for obj in (self.product, self.member, self.news):
            model_admin = admin.site.get_model_admin(type(obj))
            with patch.object(model_admin, "get_queryset", return_value=type(obj).objects.none()):
                response = self.client.get(self.list_url(type(obj)))
                self.assertNotContains(response, str(obj))
                self.assertNotContains(response, "nova-media-link")
                self.assertNotContains(response, self.change_url(obj))
                hidden = self.client.get(self.change_url(obj))
                self.assertEqual(hidden.status_code, 302)

    def test_object_permission_hook_removes_thumbnail_and_link(self):
        for obj in (self.product, self.member, self.news):
            model_admin = admin.site.get_model_admin(type(obj))
            original = model_admin.has_view_or_change_permission
            with patch.object(model_admin, "has_view_or_change_permission", side_effect=lambda request, record=None: False if record is not None else original(request)):
                response = self.client.get(self.list_url(type(obj)))
                self.assertNotContains(response, "nova-media-link")
                self.assertNotContains(response, "nova-media-thumb")
                self.assertEqual(self.client.get(self.change_url(obj)).status_code, 403)

    def test_member_search_filter_and_native_sorting_are_preserved(self):
        MemberProfile.objects.create(name="Fictional adult Zeta", member_code="ADULT-002", avatar_key="1", tier="premium", joined_at=date(2026, 9, 2))
        MemberProfile.objects.create(name="Fictional adult Beta", member_code="ADULT-003", avatar_key="2", tier="premium", joined_at=date(2026, 9, 3))
        for mode in ("dark", "light", "native"):
            self.set_mode(mode)
            response = self.client.get(self.list_url(MemberProfile), {"q": "ADULT", "tier__exact": "premium", "o": "1"})
            self.assertEqual([obj.name for obj in response.context["cl"].result_list], ["Fictional adult Beta", "Fictional adult Zeta"])
            self.assertContains(response, "tier__exact=premium")

    def test_news_search_filter_and_native_sorting_are_preserved(self):
        NewsItem.objects.create(title="Design B", cover_key="2", section="design", status="draft")
        NewsItem.objects.create(title="Design A", cover_key="3", section="design", status="draft")
        for mode in ("dark", "light", "native"):
            self.set_mode(mode)
            response = self.client.get(self.list_url(NewsItem), {"q": "Design", "status__exact": "draft", "o": "1"})
            self.assertEqual([obj.title for obj in response.context["cl"].result_list], ["Design A", "Design B"])

    def test_new_lists_paginate_without_losing_search_filter_or_order(self):
        MemberProfile.objects.bulk_create([MemberProfile(name=f"Paged adult {n:02}", member_code=f"PAGE-{n:02}", avatar_key=str(n % 6), tier="premium", joined_at=date(2026, 9, 1)) for n in range(25)])
        params = {"q": "PAGE-", "tier__exact": "premium", "o": "1"}
        first = self.client.get(self.list_url(MemberProfile), params)
        second = self.client.get(self.list_url(MemberProfile), {**params, "p": "2"})
        self.assertEqual(first.context["cl"].result_count, 25)
        self.assertEqual(len(first.context["cl"].result_list), 20)
        self.assertEqual(len(second.context["cl"].result_list), 5)
        self.assertContains(first, "tier__exact=premium")
        self.assertContains(first, "q=PAGE-")

    def test_untrusted_names_and_stored_invalid_media_are_escaped(self):
        for obj, (_, _, field) in zip((self.product, self.member, self.news), CASES):
            name_field = "title" if isinstance(obj, NewsItem) else "name"
            type(obj).objects.filter(pk=obj.pk).update(**{name_field: '<img src=x onerror="alert(1)">', field: 'https://evil.invalid/secret'})
            response = self.client.get(self.list_url(type(obj)))
            parsed = NavigationElements(response.content.decode())
            self.assertNotContains(response, "https://evil.invalid")
            self.assertNotContains(response, '<img src=x')
            self.assertContains(response, "nova-media-thumb--empty")
            self.assertFalse(any(key.startswith("on") for item in parsed.with_class("nova-media-link") for key in item["attrs"]))

    def test_model_forms_reject_external_sources(self):
        for model, _, field in CASES:
            form = modelform_factory(model, fields=[field])(data={field: "https://evil.invalid/x.png"})
            self.assertFalse(form.is_valid())
            self.assertIn(field, form.errors)

    def test_new_models_use_native_add_and_change_forms(self):
        member = self.client.post(reverse("admin:catalog_memberprofile_add"), {"name": "New fictional adult", "member_code": "ADULT-NEW", "avatar_key": "5", "tier": "standard", "active": "on", "joined_at": "2026-10-01", "_save": "Save"})
        self.assertEqual(member.status_code, 302)
        self.assertTrue(MemberProfile.objects.filter(member_code="ADULT-NEW", avatar_key="5").exists())
        news = self.client.post(self.change_url(self.news), {"title": "Native saved cover", "cover_key": "4", "section": "places", "status": "draft", "published_on": "2026-10-01", "_save": "Save"})
        self.assertEqual(news.status_code, 302)
        self.news.refresh_from_db()
        self.assertEqual(self.news.cover_key, "4")
        self.assertEqual(self.news.title, "Native saved cover")

    def test_new_native_forms_retain_csrf_protection(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        for obj in (self.member, self.news):
            self.assertEqual(client.post(self.change_url(obj), {"_save": "Save"}).status_code, 403)

    def test_disabled_theme_and_removed_app_keep_semantic_business_columns(self):
        for override in ({"NOVA_ADMIN_ENABLED": False}, {"INSTALLED_APPS": [app for app in settings.INSTALLED_APPS if app != "nova_admin"]}):
            with override_settings(**override):
                response = self.client.get(self.list_url(MemberProfile))
                self.assertContains(response, 'alt="Fictional adult Alpha"')
                self.assertContains(response, "catalog/demo-media.css")
                self.assertNotContains(response, "nova_admin/theme.css")
                self.assertNotContains(response, "nova-navigation")

    @override_settings(ROOT_URLCONF="tests.multisite_urls")
    def test_thumbnail_uses_its_own_existing_adminsite_namespace(self):
        response = self.client.get("/warehouse/catalog/product/")
        parsed = NavigationElements(response.content.decode())
        href = parsed.with_class("nova-media-link")[0]["attrs"]["href"]
        self.assertEqual(urlsplit(href).path, f"/warehouse/catalog/product/{self.product.pk}/change/")
        self.assertNotIn("/admin/", href)

    def test_no_cross_request_permission_state_is_stored_on_modeladmin(self):
        model_admin = admin.site.get_model_admin(Product)
        factory = RequestFactory()
        super_request = factory.get(self.list_url(Product))
        super_request.user = self.user
        staff_request = factory.get(self.list_url(Product))
        staff_request.user = self.staff
        allowed_column = next(column for column in model_admin.get_list_display(super_request) if callable(column))
        denied_column = next(column for column in model_admin.get_list_display(staff_request) if callable(column))
        self.assertEqual(denied_column(self.product), "—")
        self.assertIn("nova-media-link", allowed_column(self.product))
        self.assertEqual(denied_column(self.product), "—")
