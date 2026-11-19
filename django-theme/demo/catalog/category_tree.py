"""Demo category hierarchy, scoped to the current CategoryAdmin registration."""
from collections import defaultdict
from uuid import uuid4

from django import forms
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404, HttpResponseNotAllowed, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse

from .models import Category, CategoryTreeState


def can_view_tree(request, owner):
    return (owner.has_module_permission(request) and owner.has_view_or_change_permission(request)
            and "name" in owner.get_list_display(request))


def visible_categories(request, owner, queryset):
    return (obj for obj in queryset.distinct() if owner.has_view_or_change_permission(request, obj))


class TreeScope:
    def __init__(self, request, owner, queryset):
        visible = list(visible_categories(request, owner, queryset))
        self.nodes = {obj.pk: obj for obj in sorted(visible, key=lambda obj: (obj.tree_position, obj.pk))}
        self.writable = set()
        if owner.has_change_permission(request):
            self.writable = {obj.pk for obj in visible if owner.has_change_permission(request, obj)}

    def can_move(self, obj):
        return obj.pk in self.writable and (obj.parent_id is None or obj.parent_id in self.writable)

    def editable_node(self, pk):
        if pk not in self.nodes:
            raise Http404
        obj = self.nodes[pk]
        if not self.can_move(obj):
            raise PermissionDenied
        return obj

    def rows(self):
        children = defaultdict(list)
        for node in self.nodes.values():
            # A visible child of an invisible parent remains available without exposing the parent.
            parent = node.parent_id if node.parent_id in self.nodes else None
            children[parent].append(node)
        # Emit nested lists iteratively so even deep trees do not recurse in Python or in templates.
        stack = [(root, True) for root in reversed(children[None])]
        while stack:
            node, root = stack.pop()
            if node is None:
                yield None  # close this branch
                continue
            branch = children[node.pk]
            yield {"category": node, "branch": bool(branch), "root": root, "editable": self.can_move(node)}
            if branch:
                stack.append((None, False))
                stack.extend((child, False) for child in reversed(branch))

    def neighbors(self, node):
        siblings = [obj for obj in self.nodes.values() if obj.parent_id == node.parent_id]
        index = siblings.index(node)
        neighbors = {}
        for action, offset in (("up", -1), ("down", 1)):
            at = index + offset
            if 0 <= at < len(siblings) and siblings[at].pk in self.writable:
                neighbors[action] = siblings[at]
        return neighbors


def tree_context(request, owner, title):
    request.current_app = owner.admin_site.name
    return {**owner.admin_site.each_context(request), "opts": owner.opts, "title": title}


def category_tree(request, owner):
    if not can_view_tree(request, owner):
        raise PermissionDenied
    if request.method not in ("GET", "HEAD"):
        return HttpResponseNotAllowed(["GET", "HEAD"])
    scope = TreeScope(request, owner, owner.get_queryset(request))
    context = tree_context(request, owner, "商品分类树")
    context["rows"] = scope.rows()
    return TemplateResponse(request, "admin/catalog/category/tree.html", context)


class MoveForm(forms.Form):
    version = forms.UUIDField()
    action = forms.ChoiceField(choices=[("parent", "调整父分类"), ("up", "上移"), ("down", "下移")])
    parent = forms.IntegerField(required=False, min_value=1, max_value=2**63 - 1)
    neighbor = forms.IntegerField(required=False, min_value=1, max_value=2**63 - 1)


class TreeChanged(Exception):
    pass


def parent_options(scope, node, db):
    # A descendant can be visible even when an intermediate parent is hidden.
    children = defaultdict(list)
    for pk, parent in Category.objects.using(db).order_by().values_list("pk", "parent_id"):
        children[parent].append(pk)
    excluded = set()
    stack = [node.pk]
    while stack:
        pk = stack.pop()
        if pk not in excluded:
            excluded.add(pk)
            stack.extend(children[pk])
    options = []
    for obj in scope.nodes.values():
        if obj.pk in scope.writable and obj.pk not in excluded:
            path = [obj.name]
            parent = scope.nodes.get(obj.parent_id)
            seen = {obj.pk}
            while parent is not None and parent.pk not in seen:
                seen.add(parent.pk)
                path.append(parent.name)
                parent = scope.nodes.get(parent.parent_id)
            options.append({"pk": obj.pk, "label": " / ".join(reversed(path))})
    return options


def apply_move(request, owner, scope, node, data, categories):
    action = data["action"]
    if action == "parent":
        # An omitted field is a malformed request; the explicit empty choice means root.
        if "parent" not in request.POST:
            raise ValidationError("请选择父分类或顶级分类。")
        parent = data["parent"]
        if parent is not None:
            if parent not in scope.nodes:
                raise Http404
            if parent not in scope.writable:
                raise PermissionDenied
        if node.parent_id == parent:
            return False
        node.parent_id = parent
        node.validate_parent(categories.db)
        if not categories.filter(pk=node.pk).update(parent_id=parent):
            raise TreeChanged
        owner.log_change(request, node, [{"changed": {"fields": ["父分类"]}}])
    else:
        peer = scope.neighbors(node).get(action)
        if peer is None or peer.pk != data["neighbor"]:
            raise TreeChanged
        # Exchange exactly two visible, writable siblings' slots; gaps belong to other nodes.
        if not categories.filter(pk=node.pk).update(position=peer.tree_position):
            raise TreeChanged
        if not categories.filter(pk=peer.pk).update(position=node.tree_position):
            raise TreeChanged
        for changed in (node, peer):
            owner.log_change(request, changed, [{"changed": {"fields": ["同级顺序"]}}])
    return True


def edit_category_tree(request, owner, pk):
    if not can_view_tree(request, owner) or not owner.has_change_permission(request):
        raise PermissionDenied
    if request.method not in ("GET", "HEAD", "POST"):
        return HttpResponseNotAllowed(["GET", "HEAD", "POST"])
    # Resolve an explicit admin database or the write router before reading edit state.
    categories = owner.get_queryset(request)
    db = categories.select_for_update().db
    categories = categories.using(db)
    states = CategoryTreeState.objects.using(db)
    error, status = "", 200
    if request.method == "POST":
        form = MoveForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic(using=db):
                    # First statement is a write, including on SQLite. Opposite concurrent
                    # moves cannot both validate against the same old ancestry.
                    if not states.filter(pk=1, version=form.cleaned_data["version"]).update(version=uuid4()):
                        raise TreeChanged
                    scope = TreeScope(request, owner, categories)
                    node = scope.editable_node(pk)
                    changed = apply_move(request, owner, scope, node, form.cleaned_data, categories)
                    if not changed:
                        states.filter(pk=1).update(version=form.cleaned_data["version"])
            except TreeChanged:
                error, status = "分类树已变化，请核对当前位置后重试。", 409
            except ValidationError as exc:
                error, status = " ".join(exc.messages), 400
            else:
                owner.message_user(request, f"已保存「{node.name}」的分类位置。" if changed else f"「{node.name}」已在该位置。")
                url = reverse("admin:catalog_category_tree", current_app=owner.admin_site.name)
                return HttpResponseRedirect(f"{url}#category-{pk}")
        else:
            error, status = "提交的分类位置无效，请重新选择。", 400

    state, _ = states.get_or_create(pk=1)
    scope = TreeScope(request, owner, categories)
    node = scope.editable_node(pk)
    context = tree_context(request, owner, f"调整分类位置 · {node.name}")
    context.update(node=node, version=state.version, parents=parent_options(scope, node, db),
                   neighbors=scope.neighbors(node), error=error)
    return TemplateResponse(request, "admin/catalog/category/tree_edit.html", context, status=status)
