"""Count distinct visible products for each tag on their product records."""
import re
from typing import NamedTuple

from django.db.models import Count, Exists, OuterRef, Q
from django.http import Http404
from django.utils.translation import pgettext

from .analysis_filters import ranking_key, ranking_selection
from .models import Product, Tag
from .navigation import visible_admin_objects


UNTAGGED = "untagged"


def readable_tags(request, owner, db):
    tags = Tag.objects.using(db)
    site = owner.admin_site
    if site.is_registered(Tag):
        tag_admin = site.get_model_admin(Tag)
        if tag_admin.has_module_permission(request) and tag_admin.has_view_or_change_permission(request):
            scope = tag_admin.get_queryset(request)
            if scope.db != db:
                return tags.none()
            allowed = visible_admin_objects(request, tag_admin, scope)
            tags = tags.filter(pk__in=allowed.order_by().values("pk"))
    # Product-only readers can see the tag names on readable product records.
    return tags


class TagRule(NamedTuple):
    keys: list[str]
    mode: str = ""
    minimum: int | None = None

    def add_to_query(self, query, parameter):
        if self.keys:
            query.setlist(parameter, self.keys)
        if self.mode:
            query[parameter + "_mode"] = self.mode
        if self.minimum is not None:
            query[parameter + "_min"] = str(self.minimum)


def _tag_rule(query, parameter, *, exporting):
    keys = list(dict.fromkeys(ranking_key(value, UNTAGGED) for value in query.getlist(parameter)))
    modes = query.getlist(parameter + "_mode")
    counts = query.getlist(parameter + "_min")
    if modes not in ([], ["any"], ["all"], ["at_least"]) or len(counts) > 1:
        raise Http404
    mode = modes[0] if modes else ""
    if mode == "at_least":
        value = counts[0] if counts else ""
        # Bound the input before integer conversion and count distinct selected options.
        if len(value) > len(str(len(keys))) or not re.fullmatch(r"[1-9][0-9]*", value):
            raise Http404
        minimum = int(value)
        if minimum > len(keys):
            raise Http404
        return TagRule(keys, mode, minimum)

    # An unenhanced GET form sends both number inputs even when their rules are
    # inactive. Canonical links and CSV requests carry only active thresholds.
    if counts and (exporting or not mode):
        raise Http404
    if not keys:
        if exporting and mode and parameter == "chart_tag_exclude":
            raise Http404
        return TagRule([])
    if parameter == "chart_tag" and not mode:
        raise Http404
    return TagRule(keys, mode or "any")


def tag_selection(query, *, exporting):
    rule_params = ("chart_tag_mode", "chart_tag_min", "chart_tag_exclude",
                   "chart_tag_exclude_mode", "chart_tag_exclude_min")
    if not any(name in query for name in rule_params):
        key = ranking_selection(query, "chart_tag", UNTAGGED)
        return TagRule([key] if key else []), TagRule([])
    if not query.get("chart_window"):
        raise Http404
    included = _tag_rule(query, "chart_tag", exporting=exporting)
    excluded = _tag_rule(query, "chart_tag_exclude", exporting=exporting)
    if exporting and not (included.keys or excluded.keys):
        raise Http404
    return included, excluded


def _tag_match(memberships, rule):
    required = len(rule.keys) if rule.mode == "all" else (rule.minimum or 1)
    named = [key for key in rule.keys if key != UNTAGGED]
    # Group on the through table so host joins cannot multiply or hide matches.
    matches = memberships.filter(tag_id__in=named).order_by().values("product_id")
    if required > 1:
        matches = matches.alias(matched=Count("tag_id", distinct=True)).filter(matched__gte=required)
    condition = Q(pk__in=matches)
    if required == 1 and UNTAGGED in rule.keys:
        condition |= ~Exists(memberships.filter(product_id=OuterRef("pk")))
    return condition


def select_tags(products, tags, included, excluded, period):
    requested = set(included.keys).union(excluded.keys)
    named = requested - {UNTAGGED}
    labels = {}
    if named:
        # Authorize both sides before evaluating even an empty or overlapping selection.
        visible = period.products_in(products, None).order_by().values("pk")
        names = tags.filter(pk__in=named, products__in=visible).order_by().values_list("pk", "name").distinct()
        labels = {str(pk): name for pk, name in names}
        if len(labels) != len(named):
            raise Http404
    if UNTAGGED in requested:
        labels[UNTAGGED] = pgettext("Nova demo", "Untagged (no assigned tags)") if included.mode or excluded.keys else pgettext("Nova demo", "Untagged")

    memberships = Product.tags.through.objects.using(products.db)
    selected = products.filter(_tag_match(memberships, included)) if included.keys else products
    if excluded.keys:
        selected = selected.exclude(_tag_match(memberships, excluded))
    return selected, labels


def tag_ranking(products, tags):
    # Start from the eligible product IDs so joins in the host queryset can
    # neither duplicate products nor suppress other tags on the same product.
    counts = tags.filter(products__in=products.order_by().values("pk")).values("pk", "name").annotate(
        total=Count("products", distinct=True)
    ).order_by("pk")
    rows = [{"key": str(row["pk"]), "label": row["name"], "total": row["total"]} for row in counts]
    untagged = products.filter(tags__isnull=True).order_by().values("pk").distinct().count()
    if untagged:
        rows.append({"key": UNTAGGED, "label": pgettext("Nova demo", "Untagged"), "total": untagged})
    return sorted(rows, key=lambda row: -row["total"])
