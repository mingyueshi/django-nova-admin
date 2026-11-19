"""Product status board for the current Demo AdminSite registration."""
from django import forms
from django.contrib.admin.utils import flatten_fieldsets
from django.core.exceptions import PermissionDenied
from django.db import router, transaction
from django.db.models import Prefetch
from django.http import Http404, HttpResponseBadRequest, HttpResponseNotAllowed, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone

from .models import Product, ProductPublicationRequest
from .publication import PublicationConflict, lock_status, review_publication, submit_publication


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


def status_field_editable(request, model_admin, product):
    return (
        "status" not in model_admin.get_readonly_fields(request, product)
        and "status" not in (model_admin.get_exclude(request, product) or ())
        and "status" in flatten_fieldsets(model_admin.get_fieldsets(request, product))
    )


def can_edit_status(request, model_admin, product):
    return model_admin.has_change_permission(request, product) and status_field_editable(request, model_admin, product)


def render_board(request, model_admin, *, conflict=False):
    lanes = {key: {"status": key, "label": label, "cards": []} for key, label in Product.Status.choices}
    editor = model_admin.has_change_permission(request)
    products = model_admin.get_queryset(request).order_by("-updated_at", "-pk").distinct()
    reviewer = model_admin.has_approve_permission(request)
    reviews = ProductPublicationRequest.objects.select_related("submitted_by", "reviewed_by")
    products = products.prefetch_related(Prefetch("publication_requests", queryset=reviews, to_attr="reviews"))
    for product in products:
        if product.status in lanes and model_admin.has_view_or_change_permission(request, product):
            latest = product.reviews[0] if product.reviews else None
            pending = latest and latest.result == ProductPublicationRequest.Result.PENDING
            lanes[product.status]["cards"].append({
                "product": product,
                "latest": latest,
                "editable": not pending and editor and can_edit_status(request, model_admin, product),
                "can_review": pending and reviewer and model_admin.has_approve_permission(request, product)
                              and status_field_editable(request, model_admin, product),
            })
    request.current_app = model_admin.admin_site.name
    context = {
        **model_admin.admin_site.each_context(request),
        "opts": model_admin.opts,
        "title": "商品状态看板",
        "lanes": lanes.values(),
        "empty": not any(lane["cards"] for lane in lanes.values()),
        "transitions": (
            (Product.Status.DRAFT, "转为草稿"), (Product.Status.ARCHIVED, "归档"),
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
    if target == Product.Status.ACTIVE and product.status != target:
        raise PermissionDenied("上架须通过审批。")
    if product.status != target:
        # Compare on write as well: another editor can save after our permission check.
        with transaction.atomic(using=db):
            changed = lock_status(scoped.filter(updated_at=product.updated_at), product.status)
            if changed and product.publication_requests.filter(result=ProductPublicationRequest.Result.PENDING).exists():
                changed = False
            if changed:
                Product.objects.using(db).filter(pk=product.pk).update(status=target, updated_at=timezone.now())
                product.status = target
                model_admin.log_change(request, product, [{"changed": {"fields": ["状态"]}}])
        if not changed:
            return render_board(request, model_admin, conflict=True)
        model_admin.message_user(request, f"已将「{product.name}」的状态切换为{target.label}。")
    return HttpResponseRedirect(request.path)


class PublicationActionForm(forms.Form):
    action = forms.ChoiceField(choices=[("submit", "提交"), ("approve", "通过"), ("reject", "驳回")])
    request_id = forms.IntegerField(min_value=0, max_value=2**63 - 1)


def product_publication(request, model_admin, product_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    if not can_view_board(request, model_admin):
        raise PermissionDenied
    form = PublicationActionForm(request.POST)
    if not form.is_valid():
        return HttpResponseBadRequest("上架申请或审批操作无效。")
    action = form.cleaned_data["action"]
    request_id = form.cleaned_data["request_id"]
    if action == "submit":
        permitted = model_admin.has_change_permission
    else:
        permitted = model_admin.has_approve_permission
    if not permitted(request):
        raise PermissionDenied
    products = model_admin.get_queryset(request).using(router.db_for_write(Product))
    product = products.filter(pk=product_id).first()
    if product is None or not model_admin.has_view_or_change_permission(request, product):
        raise Http404
    if not permitted(request, product) or not status_field_editable(request, model_admin, product):
        raise PermissionDenied

    if action == "submit":
        if not submit_publication(products, product, request.user, site=model_admin.admin_site.name, previous_request=request_id):
            return render_board(request, model_admin, conflict=True)
        message = "已提交上架审批"
    else:
        result = (ProductPublicationRequest.Result.APPROVED if action == "approve"
                  else ProductPublicationRequest.Result.REJECTED)
        try:
            review_publication(products, product, request_id, result, request, model_admin)
        except PublicationConflict:
            return render_board(request, model_admin, conflict=True)
        message = "审批通过，商品已上架" if action == "approve" else "已驳回，商品保留为草稿"
    model_admin.message_user(request, f"「{product.name}」{message}。")
    return HttpResponseRedirect(reverse("admin:catalog_product_status_board", current_app=model_admin.admin_site.name))
