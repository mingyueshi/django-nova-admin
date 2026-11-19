"""CSV download for the host's signed product-day changelist."""
import csv
import unicodedata

from django.contrib.admin.options import IncorrectLookupParameters
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.utils import timezone
from django.utils.translation import pgettext

from .charts import ProductActivityDayFilter


CSV_FIELDS = ("sku", "name", "updated_at")
MAX_EXPORT_ROWS = 1000


def can_export_product_day(request, model_admin):
    return (
        request.user.has_perm("catalog.export_product")
        and model_admin.has_view_or_change_permission(request)
        and set(CSV_FIELDS).issubset(model_admin.get_list_display(request))
    )


def spreadsheet_text(value):
    # A visible prefix survives spreadsheet programs stripping quotes on re-save.
    # Normalize only for detection, preserving the original text in the download.
    for char in unicodedata.normalize("NFKC", value):
        if char in "=+-@\t\r\n":
            return "TEXT: " + value
        if not (char.isspace() or char in "\"'" or unicodedata.category(char) in {"Cf", "Cc"}):
            break
    return value


def export_product_day(request, model_admin):
    if not can_export_product_day(request, model_admin):
        raise PermissionDenied
    if ProductActivityDayFilter.parameter_name not in request.GET:
        raise Http404
    try:
        cl = model_admin.get_changelist_instance(request)
    except IncorrectLookupParameters:
        return HttpResponseBadRequest()
    day_filter = next((f for f in cl.filter_specs if isinstance(f, ProductActivityDayFilter)), None)
    if day_filter is None or cl.is_popup:
        raise Http404

    # Fetch a single bounded result set before sending any attachment bytes.
    with timezone.override(day_filter.zone):
        products = list(cl.queryset[:MAX_EXPORT_ROWS + 1])
    if len(products) > MAX_EXPORT_ROWS:
        message = pgettext("Nova demo", "Narrow the filters to at most %(limit)s products to export CSV.")
        return HttpResponseBadRequest(message % {"limit": MAX_EXPORT_ROWS}, content_type="text/plain; charset=utf-8")

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="products-{day_filter.day.isoformat()}.csv"'
    response.write("\ufeff")
    writer = csv.writer(response, quoting=csv.QUOTE_ALL)
    sku_label, name_label, updated_label = [model_admin.opts.get_field(field).verbose_name for field in CSV_FIELDS]
    writer.writerow((sku_label, name_label, f"{updated_label} ({day_filter.zone.key})"))
    for product in products:
        if model_admin.has_view_or_change_permission(request, product):
            updated = product.updated_at
            if timezone.is_aware(updated):
                updated = timezone.localtime(updated, day_filter.zone)
            writer.writerow((spreadsheet_text(product.sku), spreadsheet_text(product.name), updated.isoformat()))
    return response
