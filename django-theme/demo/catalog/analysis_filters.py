"""Validate workbench ranking coordinates and scope readable product fields."""
import re

from django.contrib.admin import ModelAdmin
from django.contrib.admin.utils import flatten_fieldsets
from django.core.exceptions import PermissionDenied
from django.http import Http404


def ranking_selection(query, parameter, empty_key, prefix=""):
    values = query.getlist(parameter)
    if not values:
        return ""
    if len(values) != 1 or not query.get("chart_window"):
        raise Http404
    key = values[0]
    if key == empty_key:
        return key
    pk = key.removeprefix(prefix)
    if not re.fullmatch(r"[1-9][0-9]{0,18}", pk) or int(pk) > 2**63 - 1:
        raise Http404
    return key


def _shows_field(request, owner, field, obj=None):
    return (field not in (owner.get_exclude(request, obj) or ())
            and field in flatten_fieldsets(owner.get_fieldsets(request, obj)))


def ranking_field_scope(request, owner, products, field, selected, show_rankings):
    # Exports need only the fields used by their selected filters.
    if not (selected or show_rankings):
        return None
    if not _shows_field(request, owner, field):
        if selected:
            raise PermissionDenied
        return None
    # The demo declares static fieldsets. Custom object-dependent field layouts
    # must also authorize the field on each row before grouping or filtering.
    if owner.fieldsets and all(getattr(getattr(owner, hook), "__func__", None) is getattr(ModelAdmin, hook)
                               for hook in ("get_fieldsets", "get_exclude")):
        return products
    allowed = [obj.pk for obj in products.order_by("pk").distinct().iterator(chunk_size=500)
               if _shows_field(request, owner, field, obj)]
    return products.filter(pk__in=allowed)
