"""Product analysis using the dashboard's signed chart window and visible queryset."""
from django.core.exceptions import PermissionDenied
from django.core.paginator import InvalidPage
from django.db import DatabaseError
from django.http import Http404, HttpResponse
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.translation import pgettext
from django.views.decorators.http import require_http_methods

from .analysis_categories import CategoryLevel, category_field_scope, category_selection
from .charts import product_chart_filters
from .product_csv import MAX_EXPORT_ROWS, can_export_products, product_csv_response


TEMPLATE = "admin/catalog/product/analysis.html"


def matching_products(scope, filters):
    products = filters["period"].products_in(scope, filters["detail_dates"])
    if filters["status"]:
        products = products.filter(status=filters["status"])
    return products


def details_unavailable(request, context):
    message = pgettext("Nova demo", "Product details are temporarily unavailable. Reload to retry.")
    if request.method == "POST":
        return HttpResponse(message, status=503, content_type="text/plain; charset=utf-8")
    return TemplateResponse(request, TEMPLATE, {**context, "detail_error": message}, status=503)


@require_http_methods(["GET", "HEAD", "POST"])
def product_analysis(request, owner):
    if not owner.has_module_permission(request) or not owner.has_view_or_change_permission(request):
        raise PermissionDenied
    exporting = request.method == "POST"
    can_export = can_export_products(request, owner)
    if exporting:
        if not can_export:
            raise PermissionDenied
        if not request.GET.get("chart_window") or request.POST.getlist("_export_csv") != ["1"]:
            raise Http404
        if set(request.POST) - {"_export_csv", "csrfmiddlewaretoken"}:
            raise Http404
    allowed_filters = {"chart_window", "chart_days", "chart_start", "chart_end", "chart_day", "chart_status", "chart_category", "page"}
    if set(request.GET) - allowed_filters:
        raise Http404
    category = category_selection(request.GET)
    request.current_app = owner.admin_site.name
    context = owner.admin_site.each_context(request)
    filters = product_chart_filters(request, context["available_apps"], workbench=True)
    filters["category"] = category
    if not (filters["drill_days"] and filters["status_visible"]):
        raise PermissionDenied
    context.update(opts=owner.opts, title=pgettext("Nova demo", "Linked analysis workbench"),
                   filters=filters, workbench=True, can_export=can_export, export_limit=MAX_EXPORT_ROWS)
    if filters.get("reset_url"):
        filters["reset_url"] = request.path
    if filters.get("invalid_range") or filters.get("invalid_day") or filters.get("dates_error"):
        if exporting:
            raise Http404
        return TemplateResponse(request, TEMPLATE, context, status=400)

    period = filters.get("period")
    if period is None or filters["products"] is None:
        return details_unavailable(request, context)
    try:
        with timezone.override(period.zone):
            if category or not exporting:
                scope = category_field_scope(request, owner, filters["products"])
                if scope is None and category:
                    raise PermissionDenied
                if scope is not None:
                    level = CategoryLevel(request, owner, scope, period, category)
                    if category:
                        scope = filters["products"] = level.select_products(scope, period)
                        filters["query"]["chart_category"] = category
                        context.update(category_path=level.path, category_label=level.path[-1][1])
                    if not exporting:
                        context["category_rows"] = level.ranking(matching_products(scope, filters))
            products = matching_products(filters["products"], filters).order_by("-updated_at", "-pk").distinct()
            if exporting:
                date_label = filters["day"]
                if not date_label and filters.get("custom_dates"):
                    date_label = f'{filters["start"]}-{filters["end"]}'
                suffix = "-".join(part for part in ("analysis", date_label, filters["status"]) if part)
                if category:
                    suffix += f"-category-{category}"
                return product_csv_response(request, owner, products, period.zone, suffix)
            pages = owner.get_paginator(request, products, owner.list_per_page)
            if len(request.GET.getlist("page")) > 1:
                raise Http404
            page = pages.page(request.GET.get("page", 1))
            page.object_list = list(page.object_list)
    except InvalidPage as exc:
        raise Http404 from exc
    except DatabaseError:
        filters["products"] = None
        return details_unavailable(request, context)
    display = owner.get_list_display(request)
    context.update(page=page, show_name="name" in display, show_sku="sku" in display,
                   cutoff=period.cutoff.astimezone(period.zone).strftime("%Y-%m-%d %H:%M:%S %z"))
    return TemplateResponse(request, TEMPLATE, context)
