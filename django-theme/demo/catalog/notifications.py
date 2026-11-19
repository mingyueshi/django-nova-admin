"""Personal product notifications scoped to their source and the current admin site."""
from django import forms
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import router
from django.db.models import Q
from django.http import Http404, HttpResponseBadRequest, HttpResponseNotAllowed, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.utils import timezone

from .models import ProductBatchItem, ProductBatchTask, ProductNotification, ProductPublicationRequest
from .navigation import visible_product_ids
from .product_board import can_view_board


class MarkReadForm(forms.Form):
    notification = forms.IntegerField(min_value=1, max_value=2**63 - 1)


def visible_notifications(request, owner, notifications):
    site = owner.admin_site.name
    db = notifications.db
    reviews = ProductPublicationRequest.objects.using(db).filter(
        submitted_by=request.user, site=site,
        result__in=[ProductPublicationRequest.Result.APPROVED, ProductPublicationRequest.Result.REJECTED],
    )
    tasks = ProductBatchTask.objects.using(db).filter(
        owner=request.user, site=site, operation=ProductBatchTask.Operation.SUBMIT_PUBLICATION,
    )
    candidates = notifications.filter(Q(publication_id__in=reviews.values("pk")) | Q(task_id__in=tasks.values("pk")))
    if not candidates.exists():
        return candidates.none()

    # Use the same scoped products and object permission hooks as the task details.
    review_products = candidates.filter(publication__isnull=False).order_by().values_list("publication__product_id")
    items = ProductBatchItem.objects.using(db).filter(task_id__in=candidates.order_by().values("task_id"))
    product_ids = review_products.union(items.order_by().values_list("product_id"))
    allowed = visible_product_ids(request, owner, product_ids, db)
    return candidates.filter(
        Q(publication__product_id__in=allowed) | Q(task_id__in=items.filter(product_id__in=allowed).values("task_id"))
    )


def product_notifications(request, owner):
    if not can_view_board(request, owner):
        raise PermissionDenied
    if request.method not in ("GET", "HEAD", "POST"):
        return HttpResponseNotAllowed(["GET", "HEAD", "POST"])
    if request.method == "POST":
        form = MarkReadForm(request.POST)
        if not form.is_valid():
            return HttpResponseBadRequest("通知编号无效。")
        notices = ProductNotification.objects.using(router.db_for_write(ProductNotification))
        notice = visible_notifications(request, owner, notices.filter(pk=form.cleaned_data["notification"]))
        changed = notice.filter(read_at__isnull=True).update(read_at=timezone.now())
        if not changed and not notice.exists():
            raise Http404
        return HttpResponseRedirect(request.get_full_path())

    notices = visible_notifications(request, owner, ProductNotification.objects.all())
    page = Paginator(notices.select_related("publication__product"), 25).get_page(request.GET.get("page"))
    request.current_app = owner.admin_site.name
    return TemplateResponse(request, "admin/catalog/product/notifications.html", {
        **owner.admin_site.each_context(request), "opts": owner.opts, "title": "通知中心",
        "page": page, "notification_unread": notices.filter(read_at__isnull=True).count(),
    })
