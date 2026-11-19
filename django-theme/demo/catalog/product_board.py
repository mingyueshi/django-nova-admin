"""Product status board for the current Demo AdminSite registration."""
from django import forms
from django.contrib.admin.utils import flatten_fieldsets
from django.core.exceptions import PermissionDenied
from django.db import router, transaction
from django.http import Http404, HttpResponseBadRequest, HttpResponseNotAllowed, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.utils import timezone

from .models import Product


class StatusTransitionForm(forms.Form):
    product_id = forms.IntegerField(min_value=1, max_value=2**63 - 1)
    previous_status = forms.ChoiceField(choices=Product.Status.choices)
    status = forms.ChoiceField(choices=Product.Status.choices)


def can_view_board(request, model_admin):
    display = model_admin.get_list_display(request)
    return (
        model_admin.has_module_permission(request)
        and model_admin.has_view_or_change_permission(request)
        and "name" in display and ("status_badge" in display or "status" in display)
    )


def can_edit_status(request, model_admin, product):
    return (
        model_admin.has_change_permission(request, product)
        and "status" not in model_admin.get_readonly_fields(request, product)
        and "status" not in (model_admin.get_exclude(request, product) or ())
        and "status" in flatten_fieldsets(model_admin.get_fieldsets(request, product))
    )


def render_board(request, model_admin, *, conflict=False):
    lanes = {key: {"status": key, "label": label, "cards": []} for key, label in Product.Status.choices}
    editor = model_admin.has_change_permission(request)
    products = model_admin.get_queryset(request).order_by("-updated_at", "-pk").distinct()
    for product in products:
        if product.status in lanes and model_admin.has_view_or_change_permission(request, product):
            lanes[product.status]["cards"].append({
                "product": product,
                "editable": editor and can_edit_status(request, model_admin, product),
            })
    request.current_app = model_admin.admin_site.name
    context = {
        **model_admin.admin_site.each_context(request),
        "opts": model_admin.opts,
        "title": "商品状态看板",
        "lanes": lanes.values(),
        "empty": not any(lane["cards"] for lane in lanes.values()),
        "transitions": (
            (Product.Status.DRAFT, "转为草稿"), (Product.Status.ACTIVE, "上架"), (Product.Status.ARCHIVED, "归档"),
        ),
        "show_sku": "sku" in model_admin.get_list_display(request),
        "conflict": conflict,
    }
    return TemplateResponse(request, "admin/catalog/product/status_board.html", context, status=409 if conflict else 200)


def product_status_board(request, model_admin):
    if not can_view_board(request, model_admin):
        raise PermissionDenied
    if request.method in ("GET", "HEAD"):
        return render_board(request, model_admin)
    if request.method != "POST":
        return HttpResponseNotAllowed(["GET", "HEAD", "POST"])
    if not model_admin.has_change_permission(request):
        raise PermissionDenied
    form = StatusTransitionForm(request.POST)
    if not form.is_valid():
        return HttpResponseBadRequest("商品或状态无效。")

    data = form.cleaned_data
    db = router.db_for_write(Product)
    scoped = model_admin.get_queryset(request).using(db).filter(pk=data["product_id"])
    product = scoped.first()
    if product is None or not model_admin.has_view_or_change_permission(request, product):
        raise Http404
    if not can_edit_status(request, model_admin, product):
        raise PermissionDenied
    if product.status != data["previous_status"]:
        return render_board(request, model_admin, conflict=True)

    target = Product.Status(data["status"])
    if product.status != target:
        # Compare on write as well: another editor can save after our permission check.
        with transaction.atomic(using=db):
            changed = scoped.filter(status=product.status, updated_at=product.updated_at).update(
                status=target, updated_at=timezone.now(),
            )
            if changed:
                product.status = target
                model_admin.log_change(request, product, [{"changed": {"fields": ["状态"]}}])
        if not changed:
            return render_board(request, model_admin, conflict=True)
        model_admin.message_user(request, f"已将「{product.name}」的状态切换为{target.label}。")
    return HttpResponseRedirect(request.path)
