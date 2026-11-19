"""Transactional publication requests shared by the Demo board and admin actions."""
from django.db import transaction
from django.db.models import Case, F, Value, When
from django.utils import timezone

from .models import Product, ProductNotification, ProductPublicationRequest


class PublicationConflict(Exception):
    """The product or the selected application has already changed."""


def lock_status(products, status):
    # Make the first statement a conditional write. This also serializes writers
    # on SQLite, where select_for_update() has no effect. Keep updated_at intact.
    return products.filter(status=status).update(status=F("status"))


def submit_publication(products, product, user, *, site="", previous_request=None):
    products = products.filter(pk=product.pk)
    with transaction.atomic(using=products.db):
        if not lock_status(products.filter(updated_at=product.updated_at), Product.Status.DRAFT):
            return False
        records = ProductPublicationRequest.objects.using(products.db).filter(product=product)
        latest = records.first()
        if latest and latest.result == ProductPublicationRequest.Result.PENDING:
            return False
        if previous_request is not None and previous_request != (latest.pk if latest else 0):
            return False
        records.create(product=product, submitted_by=user, site=site)
        return True


def review_publication(products, product, request_id, result, request, model_admin):
    products = products.filter(pk=product.pk)
    with transaction.atomic(using=products.db):
        if not lock_status(products.filter(updated_at=product.updated_at), Product.Status.DRAFT):
            raise PublicationConflict
        pending = ProductPublicationRequest.objects.using(products.db).filter(
            pk=request_id, product=product, result=ProductPublicationRequest.Result.PENDING,
        )
        now = timezone.now()
        site = Case(When(site="", then=Value(model_admin.admin_site.name)), default=F("site"))
        if not pending.update(result=result, reviewed_by=request.user, reviewed_at=now, site=site):
            raise PublicationConflict
        if result == ProductPublicationRequest.Result.APPROVED:
            Product.objects.using(products.db).filter(pk=product.pk).update(status=Product.Status.ACTIVE, updated_at=now)
            product.status = Product.Status.ACTIVE
        model_admin.log_change(request, product, f"上架申请 #{request_id}：{result.label}")
        ProductNotification.objects.using(products.db).get_or_create(publication_id=request_id)
