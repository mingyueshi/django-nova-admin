"""Rank direct product assignments using the category field visible on product records."""
import re

from django.contrib.admin import ModelAdmin
from django.contrib.admin.utils import flatten_fieldsets
from django.core.exceptions import PermissionDenied
from django.db.models import Count, F
from django.http import Http404
from django.utils.translation import pgettext


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


def category_ranking(products):
    groups = products.values_list("category_id", "category__name").annotate(total=Count("pk", distinct=True)).order_by(
        "-total", F("category_id").asc(nulls_last=True),
    )
    rows = []
    for pk, label, total in groups:
        if pk is None:
            rows.append({"key": UNCATEGORIZED, "label": pgettext("Nova demo", "Uncategorized"), "total": total})
        else:
            rows.append({"key": str(pk), "label": label, "total": total})
    return rows


def select_category(scope, key, period):
    if scope is None:
        raise PermissionDenied
    if key == UNCATEGORIZED:
        return scope.filter(category__isnull=True), pgettext("Nova demo", "Uncategorized")
    selected = scope.filter(category_id=int(key))
    # A changed date or status may have zero matches. Resolve the label only
    # through this account's visible products as of the original cutoff.
    label = period.products_in(selected, None).order_by("pk").values_list("category__name", flat=True).first()
    if label is None:
        raise Http404
    return selected, label
