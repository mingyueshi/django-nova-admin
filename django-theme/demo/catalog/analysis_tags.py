"""Count distinct visible products for each tag on their product records."""
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


def tag_selection(query):
    modes = query.getlist("chart_tag_mode")
    if not modes:
        key = ranking_selection(query, "chart_tag", UNTAGGED)
        return ([key] if key else []), ""
    values = query.getlist("chart_tag")
    if modes not in (["any"], ["all"]) or not values or not query.get("chart_window"):
        raise Http404
    keys = list(dict.fromkeys(ranking_key(value, UNTAGGED) for value in values))
    return keys, modes[0]


def select_tags(products, tags, keys, mode, period):
    named = [key for key in keys if key != UNTAGGED]
    labels = {}
    if named:
        # Authorize every requested tag, even if their intersection will be empty.
        visible = period.products_in(products, None).order_by().values("pk")
        names = tags.filter(pk__in=named, products__in=visible).order_by().values_list("pk", "name").distinct()
        labels = {str(pk): name for pk, name in names}
        if len(labels) != len(named):
            raise Http404
    if UNTAGGED in keys:
        labels[UNTAGGED] = pgettext("Nova demo", "Untagged (no assigned tags)") if mode else pgettext("Nova demo", "Untagged")
        if not named:
            return products.filter(tags__isnull=True), labels
        if mode == "all":
            return products.none(), labels

    # Group assignments separately from host joins. Each matching product ID
    # contributes once, including when several selected tags occur on one row.
    memberships = Product.tags.through.objects.using(products.db)
    matches = memberships.filter(tag_id__in=named).order_by().values("product_id")
    if mode == "all" and len(named) > 1:
        matches = matches.alias(matched=Count("tag_id", distinct=True)).filter(matched=len(named))
    condition = Q(pk__in=matches)
    if UNTAGGED in keys:
        condition |= ~Exists(memberships.filter(product_id=OuterRef("pk")))
    return products.filter(condition), labels


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
