"""Count distinct visible products for each tag on their product records."""
from django.db.models import Count
from django.http import Http404
from django.utils.translation import pgettext

from .models import Tag
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


def select_tag(products, tags, key, period):
    if key == UNTAGGED:
        return products.filter(tags__isnull=True), pgettext("Nova demo", "Untagged")
    # Verify the label through this account's readable products at the cutoff.
    # Changing a category, date or status can then legitimately yield zero rows.
    visible = period.products_in(products, None).order_by().values("pk")
    label = tags.filter(pk=key, products__in=visible).values_list("name", flat=True).first()
    if label is None:
        raise Http404
    return products.filter(tags=key), label


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
