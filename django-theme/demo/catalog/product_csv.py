"""CSV downloads for the host's date and status drilldown changelists."""
import csv
import unicodedata

from django.conf import settings
from django.contrib.admin.options import IncorrectLookupParameters
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.utils import timezone
from django.utils.translation import pgettext

from .charts import ProductActivityDayFilter
from .models import Product


CSV_FIELDS = ("sku", "name", "updated_at")
MAX_EXPORT_ROWS = 1000
DAY_CSV = "_export_day_csv"
STATUS_CSV = "_export_status_csv"
CSV_ACTIONS = {DAY_CSV, STATUS_CSV}


def product_csv_action(query):
    if ProductActivityDayFilter.parameter_name in query:
        return DAY_CSV
    statuses = query.getlist("status__exact")
    if len(statuses) == 1 and statuses[0] in Product.Status.values:
        return STATUS_CSV
    return None


def can_export_products(request, model_admin):
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


def export_products(request, model_admin):
    if not can_export_products(request, model_admin):
        raise PermissionDenied
    action = product_csv_action(request.GET)
    if action is None or CSV_ACTIONS.intersection(request.POST) != {action}:
        raise Http404
    try:
        cl = model_admin.get_changelist_instance(request)
    except IncorrectLookupParameters:
        return HttpResponseBadRequest()
    if cl.is_popup:
        raise Http404
    queryset = cl.queryset
    if action == DAY_CSV:
        day_filter = next((f for f in cl.filter_specs if isinstance(f, ProductActivityDayFilter)), None)
        if day_filter is None:
            raise Http404
        zone = day_filter.zone
        suffix = day_filter.day.isoformat()
    else:
        status = request.GET["status__exact"]
        queryset = queryset.filter(status=status)
        zone = timezone.get_current_timezone() if settings.USE_TZ else timezone.get_default_timezone()
        suffix = f"status-{status}"

    # Fetch a single bounded result set before sending any attachment bytes.
    with timezone.override(zone):
        products = list(queryset[:MAX_EXPORT_ROWS + 1])
        zone_name = timezone.get_current_timezone_name()
    if len(products) > MAX_EXPORT_ROWS:
        message = pgettext("Nova demo", "Narrow the filters to at most %(limit)s products to export CSV.")
        return HttpResponseBadRequest(message % {"limit": MAX_EXPORT_ROWS}, content_type="text/plain; charset=utf-8")

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="products-{suffix}.csv"'
    response.write("\ufeff")
    writer = csv.writer(response, quoting=csv.QUOTE_ALL)
    sku_label, name_label, updated_label = [model_admin.opts.get_field(field).verbose_name for field in CSV_FIELDS]
    writer.writerow((sku_label, name_label, f"{updated_label} ({zone_name})"))
    for product in products:
        if model_admin.has_view_or_change_permission(request, product):
            updated = product.updated_at
            if timezone.is_aware(updated):
                updated = timezone.localtime(updated, zone)
            writer.writerow((spreadsheet_text(product.sku), spreadsheet_text(product.name), updated.isoformat()))
    return response
