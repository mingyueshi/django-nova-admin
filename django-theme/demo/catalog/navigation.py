"""Explicit demo-only badge hook; never enabled by the reusable theme."""
from django.contrib.admin import AdminSite
from django.contrib.admin.exceptions import NotRegistered

from .models import Product


def demo_product_badges(request, available_apps):
    """Count only this request's real, permitted ProductAdmin queryset."""
    visible = any(
        app.get("app_label") == "catalog" and any(
            model.get("object_name") == "Product" and model.get("admin_url") and
            (model.get("perms", {}).get("view") or model.get("perms", {}).get("change"))
            for model in app.get("models", ())
        ) for app in available_apps
    )
    if not visible:
        return {}
    view = getattr(getattr(request, "resolver_match", None), "func", None)
    site = getattr(view, "admin_site", None)
    if site is None:
        site = getattr(getattr(view, "model_admin", None), "admin_site", None)
    # Manual renders or unrelated/custom views must not fall back to the
    # default site and accidentally count a broader queryset.
    if not isinstance(site, AdminSite) or not site.has_permission(request):
        return {}
    try:
        model_admin = site.get_model_admin(Product)
    except NotRegistered:
        return {}
    if not model_admin.has_view_or_change_permission(request):
        return {}
    return {"catalog.product": model_admin.get_queryset(request).count()}
