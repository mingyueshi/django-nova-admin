"""Behavior tests use Django's real views and an isolated TestCase database."""
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlencode, urlsplit

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ImproperlyConfigured
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import translation

from catalog.models import Category, MemberProfile, NewsItem, Product
from catalog.pagination import BoundedPaginationAdminMixin, PAGE_SIZE_PARAM
from nova_admin.preferences import SESSION_KEY
from tests.pagination_urls import ExistingProjectAdmin, ScopedChangeList, optin_site


class FormParser(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.stack = []
        self.forms = {}
        self.elements = {}
        self.nested = False
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.nested |= bool(self.stack)
            self.stack.append(attrs.get("id"))
            self.forms[attrs.get("id")] = {"attrs": attrs, "hidden": []}
        if tag in ("input", "select", "button"):
            owner = attrs.get("form") or (self.stack[-1] if self.stack else None)
            attrs["owner"] = owner
            if attrs.get("id"):
                self.elements[attrs["id"]] = attrs
            if tag == "input" and attrs.get("type") == "hidden" and owner in self.forms:
                self.forms[owner]["hidden"].append((attrs.get("name"), attrs.get("value", "")))

    def handle_endtag(self, tag):
        if tag == "form" and self.stack:
            self.stack.pop()


@override_settings(ROOT_URLCONF="tests.pagination_urls")
class PaginationExampleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser("paging-admin", "admin@example.invalid", "test-only")
        cls.staff = get_user_model().objects.create_user("paging-staff", is_staff=True)
        cls.category = Category.objects.create(name="Group", slug="group")
        Product.objects.bulk_create([
            Product(name=f"Visible product {i:03}", sku=f"VISIBLE-{i:03}", price=1,
                    category=cls.category, stock=1,
                    status=Product.Status.DRAFT if i % 2 else Product.Status.ACTIVE)
            for i in range(121)
        ] + [
            Product(name="Hidden product", sku="HIDDEN", price=1, stock=1),
            Product(name="Zero stock", sku="ZERO", price=1, stock=0),
        ])

    def setUp(self):
        self.client.force_login(self.user)
        self.url = reverse("pagination_test:catalog_product_changelist")

    def changelist(self, query=None, client=None):
        response = (client or self.client).get(self.url, query or {})
        self.assertEqual(response.status_code, 200)
        return response, response.context["cl"]

    def test_each_finite_size_and_first_page_default(self):
        _, default = self.changelist()
        self.assertEqual((default.list_per_page, len(default.result_list)), (20, 20))
        for size in (10, 20, 50, 100):
            with self.subTest(size=size):
                _, cl = self.changelist({PAGE_SIZE_PARAM: size})
                self.assertEqual(cl.list_per_page, size)
                self.assertEqual(len(cl.result_list), size)
                self.assertEqual(cl.result_count, 121)

    def test_sizes_reject_unbounded_malformed_unicode_and_duplicate_values(self):
        invalid = ("0", "-1", "11", "200", "9999999999999999999999999", "20.0", "2e1", " 20", "２０", "<script>", "9" * 5000, "")
        for value in invalid:
            with self.subTest(value=value[:40]):
                _, cl = self.changelist({PAGE_SIZE_PARAM: value})
                self.assertEqual(cl.list_per_page, 20)
                self.assertEqual(len(cl.result_list), 20)
                self.assertEqual(cl.filter_params[PAGE_SIZE_PARAM], ["20"])
        _, duplicate = self.changelist({PAGE_SIZE_PARAM: ["10", "100"]})
        self.assertEqual(duplicate.list_per_page, 20)

    def test_page_jump_is_one_based_and_last_page_is_partial(self):
        _, second = self.changelist({PAGE_SIZE_PARAM: 10, "p": 2})
        self.assertEqual(second.page_num, 2)
        self.assertEqual(list(second.result_list.values_list("sku", flat=True)), [f"VISIBLE-{i:03}" for i in range(10, 20)])
        _, last = self.changelist({PAGE_SIZE_PARAM: 10, "p": 13})
        self.assertEqual(list(last.result_list.values_list("sku", flat=True)), ["VISIBLE-120"])

    def test_malformed_pages_return_first_and_out_of_range_uses_native_rejection(self):
        for value in ("-3", "0", "nan", "1.2", "1e3", "１２", " 2", "9999999999", "9" * 5000, ["1", "2"]):
            with self.subTest(value=str(value)[:40]):
                _, cl = self.changelist({PAGE_SIZE_PARAM: 10, "p": value})
                self.assertEqual(cl.page_num, 1)
                self.assertEqual(cl.result_list.first().sku, "VISIBLE-000")
        response = self.client.get(self.url, {PAGE_SIZE_PARAM: 10, "p": 14})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.url + "?e=1")

    def test_query_scope_custom_changelist_filter_search_sort_and_repeated_values(self):
        _, cl = self.changelist({PAGE_SIZE_PARAM: 10, "q": "product", "status__exact": "draft", "o": "-2", "p": 2})
        self.assertIsInstance(cl, ScopedChangeList)
        self.assertEqual(cl.result_count, 60)
        self.assertEqual(list(cl.result_list.values_list("sku", flat=True)), [f"VISIBLE-{i:03}" for i in range(99, 79, -2)])
        self.assertNotIn(PAGE_SIZE_PARAM, cl.get_filters_params())
        self.assertNotIn(PAGE_SIZE_PARAM, cl.get_filters_params({PAGE_SIZE_PARAM: ["100"], "status__exact": ["draft"]}))
        _, repeated = self.changelist({PAGE_SIZE_PARAM: 10, "status__exact": ["draft", "active"]})
        self.assertEqual(repeated.result_count, 121)
        self.assertEqual(parse_qs(urlsplit(repeated.get_query_string({"p": 2})).query)["status__exact"], ["draft", "active"])

    def test_unknown_lookup_is_not_silently_allowed(self):
        response = self.client.get(self.url, {PAGE_SIZE_PARAM: 10, "made_up_lookup": "x"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.url + "?e=1")

    def test_native_all_limit_and_return_to_paging(self):
        response, cl = self.changelist({PAGE_SIZE_PARAM: 10, "all": "", "q": "product", "o": "2"})
        self.assertTrue(cl.can_show_all)
        self.assertEqual(len(cl.result_list), 121)
        self.assertContains(response, "返回分页")
        self.assertNotContains(response, 'id="nova-page-jump-form"')
        params = parse_qs(urlsplit(cl.nova_paginated_url).query)
        self.assertNotIn("all", params)
        self.assertEqual(params[PAGE_SIZE_PARAM], ["10"])
        self.assertEqual(params["q"], ["product"])
        Product.objects.bulk_create([Product(name=f"More {i}", sku=f"MORE-{i}", price=1, stock=1) for i in range(100)])
        _, over_limit = self.changelist({PAGE_SIZE_PARAM: 10, "all": ""})
        self.assertFalse(over_limit.can_show_all)
        self.assertEqual(len(over_limit.result_list), 10)

    def test_form_ownership_native_save_csrf_and_multivalue_preservation(self):
        response, _ = self.changelist({PAGE_SIZE_PARAM: 10, "p": 2, "q": "product", "o": "2", "status__exact": ["active", "draft"]})
        parser = FormParser(response.content.decode())
        self.assertFalse(parser.nested)
        self.assertEqual(parser.forms["changelist-form"]["attrs"]["method"], "post")
        for name in ("nova-page-size-form", "nova-page-jump-form"):
            self.assertEqual(parser.forms[name]["attrs"]["method"], "get")
            hidden = parser.forms[name]["hidden"]
            self.assertIn(("q", "product"), hidden)
            self.assertIn(("o", "2"), hidden)
            self.assertIn(("status__exact", "active"), hidden)
            self.assertIn(("status__exact", "draft"), hidden)
            self.assertFalse(any(key in ("p", "csrfmiddlewaretoken", "_selected_action", "select_across", "action") for key, _ in hidden))
        self.assertEqual(parser.elements["nova-page-size"]["owner"], "nova-page-size-form")
        self.assertEqual(parser.elements["nova-page-number"]["owner"], "nova-page-jump-form")
        self.assertEqual(parser.elements["nova-page-number"]["max"], "13")
        self.assertContains(response, 'name="_save"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')

    def test_real_size_form_submission_resets_page_preserves_filters(self):
        response, _ = self.changelist({PAGE_SIZE_PARAM: 10, "p": 3, "q": "product", "o": "2", "status__exact": "draft"})
        parser = FormParser(response.content.decode())
        submitted = parser.forms["nova-page-size-form"]["hidden"] + [(PAGE_SIZE_PARAM, "20")]
        response = self.client.get(self.url + "?" + urlencode(submitted))
        self.assertEqual(response.status_code, 200)
        cl = response.context["cl"]
        self.assertEqual((cl.page_num, cl.list_per_page, cl.result_count), (1, 20, 60))

    def test_request_sizes_do_not_mutate_shared_modeladmin_or_plain_admin(self):
        shared = optin_site._registry[Product]
        request_factory = RequestFactory()
        first = request_factory.get(self.url, {PAGE_SIZE_PARAM: 10})
        second = request_factory.get(self.url, {PAGE_SIZE_PARAM: 100})
        first.user = second.user = self.user
        first_cl = shared.get_changelist_instance(first)
        second_cl = shared.get_changelist_instance(second)
        self.assertEqual((first_cl.list_per_page, second_cl.list_per_page, shared.list_per_page), (10, 100, 20))
        self.assertEqual(first.GET[PAGE_SIZE_PARAM], "10")
        plain = self.client.get(reverse("pagination_plain:catalog_product_changelist"))
        self.assertEqual(plain.context["cl"].list_per_page, 20)
        self.assertNotContains(plain, "nova-pagination-controls")
        self.assertEqual(admin.ModelAdmin.list_per_page, 100)

    def test_staff_permission_checks_and_action_permission_are_native(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.url, {PAGE_SIZE_PARAM: 10}).status_code, 403)
        self.staff.user_permissions.add(Permission.objects.get(codename="view_product"))
        response, _ = self.changelist({PAGE_SIZE_PARAM: 10})
        self.assertNotContains(response, 'value="set_active"')
        self.assertNotContains(response, 'name="_save"')

    def test_action_selected_and_select_across_obey_entire_filtered_queryset(self):
        visible = Product.objects.filter(sku="VISIBLE-001").get()
        url = self.url + "?" + urlencode({PAGE_SIZE_PARAM: 10, "status__exact": "draft"})
        payload = {"action": "set_active", "index": "0", "_selected_action": [visible.pk], "select_across": "0"}
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Product.objects.filter(sku__startswith="VISIBLE", status="draft").count(), 59)
        another = Product.objects.get(sku="VISIBLE-003")
        response = self.client.post(url, {**payload, "_selected_action": [another.pk], "select_across": "1"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Product.objects.filter(sku__startswith="VISIBLE", status="draft").count(), 0)
        self.assertEqual(Product.objects.get(sku="HIDDEN").status, "draft")
        self.assertEqual(Product.objects.get(sku="ZERO").status, "draft")

    def test_csrf_rejects_action_without_token_and_allows_same_action_with_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        visible = Product.objects.get(sku="VISIBLE-001")
        url = self.url + "?" + urlencode({PAGE_SIZE_PARAM: 10})
        payload = {"action": "set_active", "index": "0", "_selected_action": [visible.pk]}
        self.assertEqual(client.post(url, payload).status_code, 403)
        self.changelist({PAGE_SIZE_PARAM: 10}, client=client)
        self.assertEqual(client.post(url, {**payload, "csrfmiddlewaretoken": client.cookies["csrftoken"].value}).status_code, 302)
        visible.refresh_from_db()
        self.assertEqual(visible.status, "active")

    def test_list_editable_save_uses_native_formset_for_chosen_page(self):
        response, cl = self.changelist({PAGE_SIZE_PARAM: 10, "p": 2})
        formset = cl.formset
        self.assertEqual(len(formset.forms), 10)
        data = {"_save": "Save", "form-TOTAL_FORMS": "10", "form-INITIAL_FORMS": "10", "form-MIN_NUM_FORMS": "0", "form-MAX_NUM_FORMS": "1000"}
        expected = set()
        for index, form in enumerate(formset.forms):
            data[f"form-{index}-id"] = str(form.instance.pk)
            if index < 2:
                data[f"form-{index}-featured"] = "on"
                expected.add(form.instance.pk)
        saved = self.client.post(self.url + "?" + urlencode({PAGE_SIZE_PARAM: 10, "p": 2}), data)
        self.assertEqual(saved.status_code, 302)
        self.assertEqual(set(Product.objects.filter(featured=True).values_list("pk", flat=True)), expected)

    def test_empty_and_single_page_hide_jump_but_keep_size_selector(self):
        for query in ("no-matching-product", "VISIBLE-120"):
            with self.subTest(query=query):
                response, cl = self.changelist({PAGE_SIZE_PARAM: 10, "q": query, "p": 999})
                self.assertEqual(cl.page_num, 1)
                self.assertContains(response, 'id="nova-page-size"')
                self.assertNotContains(response, 'id="nova-page-number"')

    def test_presentation_modes_keep_same_behavior(self):
        for mode in ("light", "dark", "native"):
            with self.subTest(mode=mode):
                session = self.client.session
                session[SESSION_KEY] = mode
                session.save()
                response, cl = self.changelist({PAGE_SIZE_PARAM: 10, "p": 2})
                self.assertEqual((len(cl.result_list), cl.page_num), (10, 2))
                self.assertContains(response, 'id="nova-page-size"')

    @override_settings(NOVA_ADMIN_ENABLED=False)
    def test_theme_disabled_retains_host_optin_behavior(self):
        response, cl = self.changelist({PAGE_SIZE_PARAM: 10, "p": 2})
        self.assertEqual((len(cl.result_list), cl.page_num), (10, 2))
        self.assertFalse(FormParser(response.content.decode()).nested)
        self.assertContains(response, 'name="_save"')

    def test_project_control_labels_in_chinese_and_english(self):
        for language, expected in (("zh-hans", "每页"), ("en", "Rows per page")):
            with self.subTest(language=language), translation.override(language):
                response, _ = self.changelist({PAGE_SIZE_PARAM: 10})
                self.assertContains(response, expected)

    def test_invalid_optin_default_requires_explicit_host_configuration(self):
        class InvalidDefault(BoundedPaginationAdminMixin, ExistingProjectAdmin):
            list_per_page = 500
        request = RequestFactory().get(self.url)
        request.user = self.user
        with self.assertRaisesMessage(ImproperlyConfigured, "one of 10, 20, 50, 100"):
            InvalidDefault(Product, optin_site).get_changelist_instance(request)

    def test_only_demo_image_lists_opt_in(self):
        for model in (Product, MemberProfile, NewsItem):
            self.assertIsInstance(admin.site._registry[model], BoundedPaginationAdminMixin)
        self.assertNotIsInstance(admin.site._registry[Category], BoundedPaginationAdminMixin)
