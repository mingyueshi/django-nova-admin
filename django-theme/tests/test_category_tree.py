from unittest.mock import patch

from bs4 import BeautifulSoup
from django.contrib import admin
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from catalog.models import Category, CategoryTreeState, Product


class CategoryTreeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.editor = get_user_model().objects.create_user("category-editor", is_staff=True)
        cls.editor.user_permissions.add(Permission.objects.get(codename="change_category"))
        cls.reader = get_user_model().objects.create_user("category-reader", is_staff=True)
        cls.reader.user_permissions.add(Permission.objects.get(codename="view_category"))
        cls.root = Category.objects.create(name="家具", slug="furniture")
        cls.other = Category.objects.create(name="家电", slug="appliances")
        cls.first = Category.objects.create(name="桌子 <A>", slug="desks", parent=cls.root)
        cls.middle = Category.objects.create(name="椅子", slug="chairs", parent=cls.root)
        cls.last = Category.objects.create(name="柜子", slug="cabinets", parent=cls.root)
        cls.leaf = Category.objects.create(name="书桌", slug="study-desks", parent=cls.first)
        cls.product = Product.objects.create(name="样品", sku="TREE-01", price=10, category=cls.first)

    def setUp(self):
        self.client.force_login(self.editor)
        self.tree = reverse("admin:catalog_category_tree")
        self.owner = admin.site.get_model_admin(Category)

    def edit(self, node):
        return reverse("admin:catalog_category_tree_edit", args=[node.pk])

    def token(self, node):
        response = self.client.get(self.edit(node))
        self.assertEqual(response.status_code, 200)
        return str(response.context["version"])

    def move(self, node, *, version=None, **data):
        return self.client.post(self.edit(node), {"version": version or self.token(node), **data})

    def markup(self):
        page = self.client.get(self.tree)
        self.assertEqual(page.status_code, 200)
        return BeautifulSoup(page.content, "html.parser").select_one("ul.category-tree")

    def child_ids(self, node=None):
        tree = self.markup()
        group = tree.select_one(f"#category-{node.pk} > details > ul") if node else tree
        return [item["id"] for item in group.find_all("li", recursive=False)]

    def test_readonly_can_expand_real_tree_without_edit_controls(self):
        self.client.force_login(self.reader)
        listing = reverse("admin:catalog_category_changelist")
        self.assertContains(self.client.get(listing), f'href="{self.tree}"')
        self.assertNotContains(self.client.get(listing, {"_popup": "1"}), self.tree)
        tree = self.markup()
        self.assertEqual([s.text for s in tree.select("summary")], [self.root.name, self.first.name])
        self.assertIsNotNone(tree.select_one(f"#category-{self.first.pk} #category-{self.leaf.pk}"))
        self.assertIsNone(tree.select_one("a,form,button"))
        self.assertEqual(self.client.get(self.edit(self.root)).status_code, 403)
        self.assertEqual(self.client.post(self.edit(self.root), {"action": "parent", "parent": ""}).status_code, 403)
        self.reader.user_permissions.clear()
        self.assertEqual(self.client.get(self.tree).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.tree).status_code, 302)

    def test_hidden_parent_shows_visible_children_without_leaking_parent(self):
        with patch.object(self.owner, "get_queryset", return_value=Category.objects.exclude(pk=self.root.pk)), patch.object(
            self.owner, "has_view_or_change_permission", side_effect=lambda request, obj=None: obj != self.middle
        ):
            tree = self.markup()
            self.assertNotIn(self.root.name, tree.get_text())
            self.assertNotIn(self.middle.name, tree.get_text())
            self.assertIsNone(tree.select_one(f"#category-{self.root.pk}"))
            self.assertEqual(tree.select_one(f"#category-{self.first.pk}").parent, tree)
            self.assertIsNotNone(tree.select_one(f"#category-{self.first.pk} #category-{self.leaf.pk}"))
            self.assertEqual(self.client.get(self.edit(self.first)).status_code, 403)
            choices = self.client.get(self.edit(self.other))
            self.assertNotContains(choices, self.root.name)
            self.assertNotContains(choices, self.middle.name)

    def test_empty_and_fully_hidden_share_empty_state(self):
        with patch.object(self.owner, "get_queryset", return_value=Category.objects.none()):
            self.assertEqual(self.markup().get_text(strip=True), "暂无可查看的分类。")
        with patch.object(self.owner, "has_view_or_change_permission", side_effect=lambda req, obj=None: obj is None):
            self.assertEqual(self.markup().get_text(strip=True), "暂无可查看的分类。")

    def test_reparent_subtree_and_promote_to_root_preserves_product_links(self):
        response = self.move(self.first, action="parent", parent=self.other.pk)
        self.assertRedirects(response, self.tree + f"#category-{self.first.pk}", fetch_redirect_response=False)
        tree = self.markup()
        self.assertIsNotNone(tree.select_one(f"#category-{self.other.pk} #category-{self.first.pk} #category-{self.leaf.pk}"))
        self.assertEqual(self.move(self.first, action="parent", parent="").status_code, 302)
        self.first.refresh_from_db()
        self.leaf.refresh_from_db()
        self.product.refresh_from_db()
        self.assertIsNone(self.first.parent_id)
        self.assertEqual((self.leaf.parent_id, self.product.category_id), (self.first.pk, self.first.pk))
        self.assertEqual(LogEntry.objects.filter(user=self.editor, object_id=str(self.first.pk), action_flag=CHANGE).count(), 2)

    def test_move_up_and_down_within_branch_or_root(self):
        response = self.move(self.middle, action="up", neighbor=self.first.pk)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.child_ids(self.root), [f"category-{n.pk}" for n in (self.middle, self.first, self.last)])
        self.assertEqual(self.move(self.middle, action="down", neighbor=self.first.pk).status_code, 302)
        self.assertEqual(self.child_ids(self.root), [f"category-{n.pk}" for n in (self.first, self.middle, self.last)])
        self.assertEqual(self.move(self.other, action="up", neighbor=self.root.pk).status_code, 302)
        self.assertEqual(self.child_ids(), [f"category-{self.other.pk}", f"category-{self.root.pk}"])
        before = list(Category.objects.values_list("pk", "parent_id", "position"))
        for peer in (self.last, self.other, self.leaf, self.first):
            self.assertEqual(self.move(self.first, action="up", neighbor=peer.pk).status_code, 409)
        self.assertEqual(before, list(Category.objects.values_list("pk", "parent_id", "position")))

    def test_invisible_sibling_slot_is_preserved_and_cannot_be_targeted(self):
        with patch.object(self.owner, "get_queryset", return_value=Category.objects.exclude(pk=self.middle.pk)):
            self.assertEqual(self.move(self.first, action="down", neighbor=self.middle.pk).status_code, 409)
            self.assertEqual(self.move(self.first, action="down", neighbor=self.last.pk).status_code, 302)
        self.middle.refresh_from_db()
        self.assertIsNone(self.middle.position)
        self.assertEqual(self.child_ids(self.root), [f"category-{n.pk}" for n in (self.last, self.middle, self.first)])
        self.assertFalse(LogEntry.objects.filter(object_id=str(self.middle.pk)).exists())

    def test_cycle_checks_include_hidden_intermediate_and_leave_tree_unchanged(self):
        with patch.object(self.owner, "get_queryset", return_value=Category.objects.exclude(pk=self.first.pk)):
            edit = BeautifulSoup(self.client.get(self.edit(self.root)).content, "html.parser")
            targets = [o["value"] for o in edit.select('select[name="parent"] option')]
            self.assertNotIn(str(self.leaf.pk), targets)
            self.assertNotIn(str(self.root.pk), targets)
            version = self.token(self.root)
            for parent in (self.root, self.leaf):
                response = self.move(self.root, action="parent", parent=parent.pk, version=version)
                self.assertContains(response, "分类不能位于自身或其下级分类之下", status_code=400)
        self.root.refresh_from_db()
        self.assertIsNone(self.root.parent_id)
        self.assertFalse(LogEntry.objects.exists())

    def test_model_validates_cycles_and_protects_parents(self):
        self.root.parent = self.leaf
        for operation in (self.root.full_clean, self.root.save):
            with self.assertRaises(ValidationError):
                operation()
        self.root.refresh_from_db()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Category.objects.filter(pk=self.root.pk).update(parent_id=self.root.pk)
        with self.assertRaises(ProtectedError):
            self.root.delete()

    def test_permissions_rechecked_for_source_destination_and_neighbor(self):
        version = self.token(self.first)
        with patch.object(self.owner, "has_change_permission", side_effect=lambda req, obj=None: obj != self.first):
            response = self.move(self.first, action="parent", parent="", version=version)
            self.assertEqual(response.status_code, 403)
        with patch.object(self.owner, "has_change_permission", side_effect=lambda req, obj=None: obj != self.other):
            self.assertEqual(self.move(self.first, action="parent", parent=self.other.pk).status_code, 403)
        with patch.object(self.owner, "get_queryset", return_value=Category.objects.exclude(pk=self.other.pk)):
            self.assertEqual(self.move(self.first, action="parent", parent=self.other.pk).status_code, 404)
            self.assertEqual(self.client.post(self.edit(self.other), {"version": version, "action": "parent", "parent": ""}).status_code, 404)
        with patch.object(self.owner, "has_change_permission", side_effect=lambda req, obj=None: obj != self.middle):
            self.assertEqual(self.move(self.first, action="down", neighbor=self.middle.pk).status_code, 409)
        self.editor.user_permissions.clear()
        self.assertEqual(self.move(self.first, action="parent", parent="", version=version).status_code, 403)
        self.first.refresh_from_db()
        self.assertEqual(self.first.parent_id, self.root.pk)
        self.assertFalse(LogEntry.objects.exists())

    def test_saving_current_parent_preserves_other_edit_forms(self):
        version = self.token(self.first)
        self.assertEqual(self.move(self.first, version=version, action="parent", parent=self.root.pk).status_code, 302)
        self.assertEqual(str(CategoryTreeState.objects.get(pk=1).version), version)
        self.assertFalse(LogEntry.objects.exists())
        self.assertEqual(self.move(self.other, version=version, action="up", neighbor=self.root.pk).status_code, 302)

    def test_stale_or_repeated_move_cannot_apply_to_new_tree(self):
        old = self.token(self.first)
        self.assertEqual(self.move(self.first, version=old, action="down", neighbor=self.middle.pk).status_code, 302)
        response = self.move(self.first, version=old, action="parent", parent=self.other.pk)
        self.assertContains(response, "分类树已变化", status_code=409)
        self.assertNotEqual(str(response.context["version"]), old)
        self.first.refresh_from_db()
        self.assertEqual(self.first.parent_id, self.root.pk)
        self.assertEqual(LogEntry.objects.count(), 2)

    def test_rollback_on_log_failure_and_no_mutations_on_invalid_requests(self):
        before = self.token(self.first)
        with patch.object(self.owner, "log_change", side_effect=RuntimeError("audit unavailable")):
            with self.assertRaises(RuntimeError):
                self.move(self.first, version=before, action="down", neighbor=self.middle.pk)
        self.assertEqual(str(CategoryTreeState.objects.get(pk=1).version), before)
        self.assertEqual(self.client.post(self.tree).status_code, 405)
        self.assertEqual(self.client.put(self.edit(self.first)).status_code, 405)
        for fields in ({"action": "parent"}, {"action": "parent", "parent": "bad"}, {"action": "invalid"}):
            self.assertEqual(self.move(self.first, version=before, **fields).status_code, 400)
        self.assertEqual(self.client.get(self.edit(self.first), {"action": "parent", "parent": ""}).status_code, 200)
        self.first.refresh_from_db()
        self.assertEqual((self.first.parent_id, self.first.position), (self.root.pk, None))
        self.assertFalse(LogEntry.objects.exists())

    def test_native_form_updates_name_only_and_cannot_forge_tree_fields(self):
        self.client.force_login(self.editor)
        url = reverse("admin:catalog_category_change", args=[self.first.pk])
        page = BeautifulSoup(self.client.get(url).content, "html.parser")
        self.assertIsNone(page.select_one('[name="parent"],[name="position"]'))
        self.assertEqual(self.move(self.first, action="parent", parent=self.other.pk).status_code, 302)
        self.assertEqual(self.client.post(url, {"name": "新名称", "slug": self.first.slug, "_save": "保存",
                                               "parent": self.leaf.pk, "position": 12}).status_code, 302)
        self.first.refresh_from_db()
        self.assertEqual((self.first.name, self.first.parent_id, self.first.position), ("新名称", self.other.pk, None))

    def test_forms_are_csrf_protected(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.editor)
        url = self.edit(self.first)
        form = BeautifulSoup(client.get(url).content, "html.parser").find("select", attrs={"name": "parent"}).find_parent("form")
        data = {"action": "parent", "parent": "", "version": form.find("input", attrs={"name": "version"})["value"]}
        self.assertEqual(client.post(url, data).status_code, 403)
        data["csrfmiddlewaretoken"] = form.find("input", attrs={"name": "csrfmiddlewaretoken"})["value"]
        self.assertEqual(client.post(url, data).status_code, 302)

    @override_settings(ROOT_URLCONF="tests.multisite_urls")
    def test_current_site_owns_links_permissions_and_scope(self):
        from tests.multisite_urls import warehouse_site

        self.tree = reverse("warehouse:catalog_category_tree")
        edit = reverse("warehouse:catalog_category_tree_edit", args=[self.first.pk])
        owner = warehouse_site.get_model_admin(Category)
        self.assertContains(self.client.get(reverse("warehouse:catalog_category_changelist")), f'href="{self.tree}"')
        self.assertContains(self.client.get(self.tree), f'href="{edit}"')
        version = self.client.get(edit).context["version"]
        data = {"version": version, "action": "parent", "parent": ""}
        with patch.object(owner, "get_queryset", return_value=Category.objects.exclude(pk=self.first.pk)):
            self.assertEqual(self.client.post(edit, data).status_code, 404)
        self.assertEqual(self.client.get(reverse("review:catalog_category_tree")).status_code, 302)
        self.assertRedirects(self.client.post(edit, data), self.tree + f"#category-{self.first.pk}", fetch_redirect_response=False)
