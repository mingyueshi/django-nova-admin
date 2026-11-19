"""Durable progress for the Demo product admin's bulk publication action."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, router, transaction
from django.db.models import Count, Min, OuterRef, Q, Subquery
from django.http import Http404, HttpResponseNotAllowed, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse

from .models import Product, ProductBatchItem, ProductBatchTask, ProductPublicationRequest
from .product_board import can_edit_status, can_view_board
from .publication import submit_publication


BATCH_SIZE = 10
Outcome = ProductBatchItem.Outcome


def publication_task_action(request, owner, queryset):
    if not can_view_board(request, owner) or not owner.has_change_permission(request):
        raise PermissionDenied
    db = router.db_for_write(Product)
    scope = owner.get_queryset(request).using(db)
    latest_request = ProductPublicationRequest.objects.filter(product_id=OuterRef("pk")).order_by("-pk")
    selected = scope.filter(pk__in=queryset.using(db).values("pk")).annotate(
        last_request=Subquery(latest_request.values("pk")[:1]),
    ).order_by("pk").distinct()
    task = ProductBatchTask(owner=request.user, site=owner.admin_site.name,
                            operation=ProductBatchTask.Operation.SUBMIT_PUBLICATION)
    items = []
    for product in selected:
        if not owner.has_view_or_change_permission(request, product) or not can_edit_status(request, owner, product):
            raise PermissionDenied
        items.append(ProductBatchItem(task=task, product_id=product.pk, product_updated_at=product.updated_at,
                                      previous_request_id=product.last_request or 0))
    namespace = owner.admin_site.name
    if not items:
        owner.message_user(request, "当前选择中没有可提交的商品。")
        return HttpResponseRedirect(reverse("admin:catalog_product_batch_tasks", current_app=namespace))
    with transaction.atomic(using=db):
        task.save(using=db)
        ProductBatchItem.objects.using(db).bulk_create(items)
    process_batch(request, owner, task.items.using(db).order_by("pk")[:BATCH_SIZE], db)
    return HttpResponseRedirect(reverse("admin:catalog_product_batch_task", args=[task.pk], current_app=namespace))


def submit_item(request, owner, products, item):
    product = products.filter(pk=item.product_id).first()
    if (product is None or not owner.has_view_or_change_permission(request, product)
            or not can_edit_status(request, owner, product)):
        return Outcome.UNAVAILABLE
    if product.status != Product.Status.DRAFT:
        return Outcome.NOT_DRAFT
    if product.updated_at != item.product_updated_at:
        return Outcome.CONFLICT
    try:
        submitted = submit_publication(products, product, request.user, previous_request=item.previous_request_id)
    except (ValidationError, IntegrityError):
        # submit_publication rolls its transaction back before the item is marked failed.
        return Outcome.INVALID
    return Outcome.SUBMITTED if submitted else Outcome.CONFLICT


def process_batch(request, owner, items, db):
    products = owner.get_queryset(request).using(db)
    for item in items:
        row = ProductBatchItem.objects.using(db).filter(pk=item.pk, outcome=Outcome.PENDING)
        with transaction.atomic(using=db):
            # Conditional write also locks on SQLite. A replay cannot submit or count an item twice.
            if row.update(outcome=Outcome.PENDING):
                row.update(outcome=submit_item(request, owner, products, item))


def totals():
    return {
        "total": Count("pk"), "processed": Count("pk", filter=~Q(outcome=Outcome.PENDING)),
        "succeeded": Count("pk", filter=Q(outcome=Outcome.SUBMITTED)),
        "failed": Count("pk", filter=~Q(outcome__in=[Outcome.PENDING, Outcome.SUBMITTED])),
    }


def product_batch_tasks(request, owner, task_id=None):
    if not can_view_board(request, owner):
        raise PermissionDenied
    methods = ["GET", "HEAD", "POST"] if task_id else ["GET", "HEAD"]
    if request.method not in methods:
        return HttpResponseNotAllowed(methods)
    db = router.db_for_write(Product) if request.method == "POST" else owner.get_queryset(request).db
    items = ProductBatchItem.objects.using(db).filter(
        task__owner=request.user, task__site=owner.admin_site.name,
        task__operation=ProductBatchTask.Operation.SUBMIT_PUBLICATION,
    )
    if task_id:
        items = items.filter(task_id=task_id)
    products = owner.get_queryset(request).using(db).filter(pk__in=items.values("product_id")).order_by("pk").distinct()
    visible_ids = [p.pk for p in products.iterator() if owner.has_view_or_change_permission(request, p)]
    items = items.filter(product_id__in=visible_ids)
    request.current_app = owner.admin_site.name
    context = {**owner.admin_site.each_context(request), "opts": owner.opts, "title": "批量任务进度"}
    if not task_id:
        summaries = items.values("task_id", "task__created_at").annotate(**totals()).order_by("-task__created_at", "task_id")
        context["page"] = Paginator(summaries, 25).get_page(request.GET.get("page"))
        return TemplateResponse(request, "admin/catalog/product/batch_tasks.html", context)

    counts = items.aggregate(**totals(), first_pending=Min("pk", filter=Q(outcome=Outcome.PENDING)))
    if not counts["total"]:
        raise Http404
    if request.method == "POST":
        if not owner.has_change_permission(request):
            raise PermissionDenied
        # An old form can only advance its own displayed batch, even after a refresh or double click.
        pending = list(items.filter(outcome=Outcome.PENDING).order_by("pk")[:BATCH_SIZE])
        if pending and request.POST.get("cursor") == str(pending[0].pk):
            process_batch(request, owner, pending, db)
        return HttpResponseRedirect(request.get_full_path())

    context.update(title="批量提交上架审批", counts=counts,
                   cursor=counts["first_pending"] if owner.has_change_permission(request) else None,
                   page=Paginator(items.select_related("product").order_by("pk"), 50).get_page(request.GET.get("page")))
    return TemplateResponse(request, "admin/catalog/product/batch_task.html", context)
