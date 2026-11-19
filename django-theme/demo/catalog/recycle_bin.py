"""Product recycle bin for the current Demo AdminSite registration."""
from copy import copy

from django.core.exceptions import PermissionDenied
from django.db import router, transaction
from django.http import Http404, HttpResponseNotAllowed, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse

from .models import Product, ProductRecycleEntry


def can_view_recycle_bin(request, owner):
    return (owner.has_module_permission(request) and owner.has_view_or_change_permission(request)
            and "name" in owner.get_list_display(request))


def recycled_products(request, owner):
    # Run this site's normal get_queryset overrides. Only this call starts from
    # recycled rows; rendering the surrounding admin still uses live products.
    scope_request = copy(request)
    scope_request.product_recycle_bin = True
    return owner.get_queryset(scope_request).filter(recycle_entry__isnull=False)


def product_recycle_bin(request, owner):
    if not can_view_recycle_bin(request, owner):
        raise PermissionDenied
    if request.method not in ("GET", "HEAD"):
        return HttpResponseNotAllowed(["GET", "HEAD"])
    products = recycled_products(request, owner).select_related("recycle_entry").order_by(
        "-recycle_entry__deleted_at", "-pk",
    ).distinct()
    can_restore = owner.has_restore_permission(request)
    rows = [
        {"product": product, "entry": product.recycle_entry,
         "can_restore": can_restore and owner.has_restore_permission(request, product)}
        for product in products if owner.has_view_or_change_permission(request, product)
    ]
    request.current_app = owner.admin_site.name
    return TemplateResponse(request, "admin/catalog/product/recycle_bin.html", {
        **owner.admin_site.each_context(request), "opts": owner.opts,
        "title": "商品回收站", "rows": rows, "can_restore": can_restore,
    })


def restore_product(request, owner, entry_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    if not can_view_recycle_bin(request, owner) or not owner.has_restore_permission(request):
        raise PermissionDenied
    if entry_id > 2**63 - 1:
        raise Http404
    db = router.db_for_write(Product)
    products = recycled_products(request, owner).using(db).filter(recycle_entry__pk=entry_id)
    product = products.first()
    if product is None or not owner.has_view_or_change_permission(request, product):
        raise Http404
    if not owner.has_restore_permission(request, product):
        raise PermissionDenied
    with transaction.atomic(using=db):
        removed, _ = ProductRecycleEntry.objects.using(db).filter(
            pk=entry_id, product_id__in=products.values("pk"),
        ).delete()
        if not removed:
            raise Http404
        owner.log_change(request, product, "已从回收站还原商品。")
    owner.message_user(request, f"已还原「{product.name}」。")
    return HttpResponseRedirect(reverse("admin:catalog_product_recycle_bin", current_app=owner.admin_site.name))
