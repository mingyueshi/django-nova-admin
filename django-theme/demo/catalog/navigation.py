"""Shared product visibility checks for the Demo admin."""
from django.contrib.admin import AdminSite
from django.contrib.admin.exceptions import NotRegistered

from .models import Product


def visible_product_admin(request, available_apps):
    """Resolve the currently authorized registration shared by product aggregates."""
    visible = any(
        app.get("app_label") == "catalog" and any(
            model.get("object_name") == "Product" and model.get("admin_url") and
            (model.get("perms", {}).get("view") or model.get("perms", {}).get("change"))
            for model in app.get("models", ())
        ) for app in available_apps
    )
    if not visible:
        return None
    view = getattr(getattr(request, "resolver_match", None), "func", None)
    site = getattr(view, "admin_site", None)
    if site is None:
        site = getattr(getattr(view, "model_admin", None), "admin_site", None)
    # Manual renders or unrelated/custom views must not fall back to the
    # default site and accidentally count a broader queryset.
    if not isinstance(site, AdminSite) or not site.has_permission(request):
        return None
    try:
        model_admin = site.get_model_admin(Product)
    except NotRegistered:
        return None
    if not model_admin.has_view_or_change_permission(request):
        return None
    return model_admin


def demo_product_badges(request, available_apps):
    model_admin = visible_product_admin(request, available_apps)
    if model_admin is None:
        return {}
    return {"catalog.product": model_admin.get_queryset(request).count()}


def visible_product_ids(request, owner, product_ids, db):
    scope = owner.get_queryset(request).using(db)
    candidates = scope.filter(pk__in=product_ids).order_by("pk").distinct()
    allowed = [p.pk for p in candidates.iterator(chunk_size=500) if owner.has_view_or_change_permission(request, p)]
    # Keep the live site scope in the final query, including a read-state UPDATE after the object checks.
    return scope.filter(pk__in=allowed).order_by().values("pk")
