"""Drill through visible category branches using the workbench product scope."""
import re
from collections import Counter, defaultdict

from django.contrib.admin import ModelAdmin
from django.contrib.admin.utils import flatten_fieldsets
from django.db.models import Count
from django.http import Http404
from django.utils.translation import pgettext

from .category_tree import can_view_tree, visible_categories
from .models import Category


UNCATEGORIZED = "uncategorized"


def category_selection(query):
    values = query.getlist("chart_category")
    if not values:
        return ""
    if len(values) != 1 or not query.get("chart_window"):
        raise Http404
    key = values[0]
    if key == UNCATEGORIZED:
        return key
    if not re.fullmatch(r"[1-9][0-9]{0,18}", key) or int(key) > 2**63 - 1:
        raise Http404
    return key


def _shows_category(request, owner, obj=None):
    return ("category" not in (owner.get_exclude(request, obj) or ())
            and "category" in flatten_fieldsets(owner.get_fieldsets(request, obj)))


def category_field_scope(request, owner, products):
    if not _shows_category(request, owner):
        return None
    # The demo declares static fieldsets. Custom object-dependent field layouts
    # must also authorize the category of each row before grouping or filtering.
    if owner.fieldsets and all(getattr(getattr(owner, hook), "__func__", None) is getattr(ModelAdmin, hook)
                               for hook in ("get_fieldsets", "get_exclude")):
        return products
    allowed = [obj.pk for obj in products.order_by("pk").distinct().iterator(chunk_size=500)
               if _shows_category(request, owner, obj)]
    return products.filter(pk__in=allowed)


def category_nodes(request, owner, products, period):
    # A tree reader may see ancestors with no directly assigned product.
    site = owner.admin_site
    if site.is_registered(Category):
        category_admin = site.get_model_admin(Category)
        if can_view_tree(request, category_admin):
            categories = category_admin.get_queryset(request)
            if categories.db == products.db:
                return visible_categories(request, category_admin, categories)

    # Product-only readers know the category on each readable product. A
    # missing parent breaks the path, just as on the category tree page.
    assigned = period.products_in(products, None).order_by().values("category_id")
    return Category.objects.using(products.db).filter(pk__in=assigned).order_by()


class CategoryLevel:
    def __init__(self, request, owner, scope, period, key):
        self.selected = int(key) if key and key != UNCATEGORIZED else key
        self.path = []
        self.branches = {None: UNCATEGORIZED} if not key or key == UNCATEGORIZED else {}
        self.labels = {UNCATEGORIZED: pgettext("Nova demo", "Uncategorized")}
        if self.selected == UNCATEGORIZED:
            self.path = [(UNCATEGORIZED, self.labels[UNCATEGORIZED])]
            return

        parents = {}
        for node in category_nodes(request, owner, scope, period):
            parents[node.pk] = node.parent_id
            self.labels[node.pk] = node.name
        if key and self.selected not in parents:
            raise Http404

        children = defaultdict(list)
        for pk, parent in parents.items():
            children[parent if parent in parents else None].append(pk)
        parent = self.selected or None
        seen = set()
        while parent in parents:
            if parent in seen:
                raise Http404
            seen.add(parent)
            self.path.append((parent, self.labels[parent]))
            parent = parents[parent]
        self.path.reverse()

        # Map each reachable category to its immediate branch at this level.
        # These same IDs restrict the charts, detail pagination and CSV.
        stack = [(child, child) for child in children[self.selected or None]]
        while stack:
            pk, branch = stack.pop()
            self.branches[pk] = branch
            stack.extend((child, branch) for child in children[pk])
        if key:
            self.branches[self.selected] = self.selected

    def select_products(self, scope, period):
        if self.selected == UNCATEGORIZED:
            return scope.filter(category__isnull=True)
        selected = scope.filter(category_id__in=self.branches)
        # Empty date/status intersections remain navigable, but an arbitrary
        # category without a visible product through the cutoff is not a drilldown.
        if not period.products_in(selected, None).exists():
            raise Http404
        return selected

    def ranking(self, products):
        groups = products.order_by().values_list("category_id").annotate(total=Count("pk", distinct=True))
        totals = Counter()
        for pk, total in groups:
            if pk in self.branches:
                totals[self.branches[pk]] += total

        rows = []
        for key in sorted(totals, key=lambda k: (-totals[k], k == UNCATEGORIZED, k)):
            direct = key == self.selected
            label = self.labels[key]
            if direct and key != UNCATEGORIZED:
                label = pgettext("Nova demo", "Directly assigned products")
            rows.append({"key": key, "label": label, "total": totals[key], "direct": direct})
        return rows
