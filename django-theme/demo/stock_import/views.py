import csv
from datetime import timedelta

from django.contrib.admin.utils import flatten_fieldsets
from django.core.exceptions import PermissionDenied
from django.core.signing import Signer
from django.db import transaction
from django.http import Http404, HttpResponse, HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from catalog.product_csv import spreadsheet_text
from .files import parse_upload
from .models import StockPreview


class StockConflict(Exception):
    pass


def can_import(request, admin):
    return (request.user.has_perm("stock_import.import_stock") and admin.has_module_permission(request)
            and admin.has_change_permission(request) and "stock" in admin.list_editable
            and {"sku", "stock"}.issubset(admin.get_list_display(request)))


def editable(request, admin, obj):
    return (obj is not None and admin.has_view_or_change_permission(request, obj)
            and admin.has_change_permission(request, obj)
            and "stock" not in admin.get_readonly_fields(request, obj)
            and "stock" not in (admin.get_exclude(request, obj) or ())
            and "stock" in flatten_fieldsets(admin.get_fieldsets(request, obj)))


def collect_rows(request, admin, items, errors):
    products = admin.get_queryset(request).in_bulk([sku for _, sku, _ in items], field_name="sku")
    rows = []
    for line, sku, stock in items:
        obj = products.get(sku)
        if editable(request, admin, obj):
            rows.append({"line": line, "pk": obj.pk, "sku": sku, "old": obj.stock,
                         "new": stock, "version": obj.updated_at.isoformat()})
        else:
            errors.append([line, sku, "找不到可操作的商品。"])
    return rows


def current_products(request, admin, batch, *, lock=False):
    scoped = admin.get_queryset(request)
    if lock:
        scoped = scoped.select_for_update().order_by("pk")
    products = scoped.in_bulk([row["pk"] for row in batch.rows])
    for row in batch.rows:
        obj = products.get(row["pk"])
        if (not editable(request, admin, obj) or obj.sku != row["sku"] or obj.stock != row["old"]
                or obj.updated_at.isoformat() != row["version"]):
            raise StockConflict
    return scoped, products


@transaction.atomic
def submit(request, admin, batch, cutoff):
    # Claim once, in the same transaction as the product updates and native logs.
    batches = StockPreview.objects.filter(pk=batch.pk, created_at__gt=cutoff)
    if not batches.filter(submitted=False).update(submitted=True):
        if batches.filter(submitted=True).exists():
            return
        raise StockConflict
    scoped, products = current_products(request, admin, batch, lock=True)
    for row in batch.rows:
        if row["old"] == row["new"]:
            continue
        obj = products[row["pk"]]
        written = scoped.filter(pk=obj.pk, sku=obj.sku, stock=row["old"], updated_at=obj.updated_at).update(
            stock=row["new"], updated_at=timezone.now(),
        )
        if not written:
            raise StockConflict
        admin.log_change(request, obj, f"CSV 库存 {row['old']} → {row['new']}（批次 {batch.pk}）")


def errors_csv(batch):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="stock-errors.csv"'
    response.write("\ufeff")
    writer = csv.writer(response, quoting=csv.QUOTE_ALL)
    writer.writerow(("行号", "SKU", "原因"))
    for line, sku, error in batch.errors:
        writer.writerow((line, spreadsheet_text(sku), error))
    return response


def cutoff():
    return timezone.now() - timedelta(minutes=15)


def batch_for(request, batch_id):
    return get_object_or_404(StockPreview, pk=batch_id, operator=request.user,
                             site=request.current_app, created_at__gt=cutoff())


def page(request, admin, step, *, batch=None, error=None, status=200, **context):
    return TemplateResponse(request, "stock_import/wizard.html", {
        **admin.admin_site.each_context(request), "opts": admin.opts, "title": "导入商品库存",
        "step": step, "batch": batch, "error": error, **context,
    }, status=status)


def redirect(request, batch, step):
    return HttpResponseRedirect(reverse(f"admin:catalog_product_import_{step}", args=[batch.pk],
                                        current_app=request.current_app))


@require_http_methods(["GET", "POST"])
def upload(request, admin):
    if request.method == "GET":
        return page(request, admin, "upload")
    try:
        items, errors = parse_upload(request.FILES.get("file"))
    except ValueError as exc:
        return page(request, admin, "upload", error=str(exc), status=400)
    rows = collect_rows(request, admin, items, errors)
    StockPreview.objects.filter(created_at__lte=cutoff()).delete()
    batch = StockPreview.objects.create(operator=request.user, site=request.current_app,
                                       rows=rows, errors=sorted(errors))
    return redirect(request, batch, "validate")


def review_signature(batch):
    policy = "valid-only" if batch.errors else "all"
    return Signer(salt="stock_import.preview").signature(f"{batch.pk}:{policy}")


@require_GET
def review(request, admin, batch_id, step):
    batch = batch_for(request, batch_id)
    if step == "errors":
        return errors_csv(batch)
    if step == "result" and not batch.submitted:
        raise Http404
    if step == "preview":
        if batch.submitted:
            return redirect(request, batch, "result")
        if not batch.rows or (batch.errors and request.GET.get("skip") != "1"):
            raise Http404
        try:
            current_products(request, admin, batch)
        except StockConflict:
            return page(request, admin, step, error="数据或权限已变化，请重新上传。", status=409)
        return page(request, admin, step, batch=batch, signature=review_signature(batch))
    return page(request, admin, step, batch=batch)


@require_POST
def confirm(request, admin, batch_id):
    batch = batch_for(request, batch_id)
    if not batch.rows or not constant_time_compare(request.POST.get("review", ""), review_signature(batch)):
        return HttpResponseBadRequest("请先预览并确认本批差异。")
    try:
        submit(request, admin, batch, cutoff())
    except StockConflict:
        return page(request, admin, "confirm", error="数据或权限已变化，整批未提交。请重新上传。", status=409)
    return redirect(request, batch, "result")


def import_urls(admin):
    def protected(view):
        def scoped_view(request, **kwargs):
            if not can_import(request, admin):
                raise PermissionDenied
            request.current_app = admin.admin_site.name
            return view(request, admin, **kwargs)
        return admin.admin_site.admin_view(scoped_view)

    return [
        path("stock-import/", protected(upload), name="catalog_product_import_upload"),
        path("stock-import/<uuid:batch_id>/confirm/", protected(confirm), name="catalog_product_import_confirm"),
        *[path(f"stock-import/<uuid:batch_id>/{step}/", protected(review), {"step": step},
               name=f"catalog_product_import_{step}") for step in ("validate", "preview", "errors", "result")],
    ]
