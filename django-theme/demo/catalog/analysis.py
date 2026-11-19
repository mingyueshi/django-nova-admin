"""Product analysis using the dashboard's signed chart window and visible queryset."""
from django.core.exceptions import PermissionDenied
from django.core.paginator import InvalidPage
from django.db import DatabaseError
from django.http import Http404, HttpResponse
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.translation import pgettext
from django.views.decorators.http import require_http_methods

from .analysis_categories import DIRECT_PREFIX, UNCATEGORIZED, CategoryLevel
from .analysis_filters import ranking_field_scope, ranking_selection
from .analysis_tags import UNTAGGED, readable_tags, select_tag, tag_ranking
from .charts import product_chart_filters
from .product_csv import MAX_EXPORT_ROWS, can_export_products, product_csv_response


TEMPLATE = "admin/catalog/product/analysis.html"


def matching_products(scope, filters):
    products = filters["period"].products_in(scope, filters["detail_dates"])
    if filters["status"]:
        products = products.filter(status=filters["status"])
    return products


def apply_rankings(request, owner, context, *, show_rankings):
    filters = context["filters"]
    base, period = filters["products"], filters["period"]
    category, tag = filters["category"], filters["tag"]
    category_products = ranking_field_scope(request, owner, base, "category", category, show_rankings)
    tag_products = ranking_field_scope(request, owner, base, "tags", tag, show_rankings)

    if category_products is not None:
        level = CategoryLevel(request, owner, category_products, period, category)
        if category:
            category_products = filters["products"] = level.select_products(category_products, period)
            filters["query"]["chart_category"] = category
            context.update(category_path=level.path, category_label=level.path[-1][1], direct_only=level.direct_only)

    if tag_products is not None:
        tags = readable_tags(request, owner, base.db)
        # Tag choices stay switchable within the current category, including direct-only mode.
        rank_scope = tag_products
        if show_rankings and category:
            rank_scope = rank_scope.filter(pk__in=category_products.order_by().values("pk"))
        if tag:
            tagged, context["tag_label"] = select_tag(tag_products, tags, tag, period)
            if category_products is not None:
                category_products = category_products.filter(pk__in=tagged.order_by().values("pk"))
            filters["products"] = category_products if category else tagged
            filters["query"]["chart_tag"] = tag
        if show_rankings:
            context["tag_rows"] = tag_ranking(matching_products(rank_scope, filters), tags)
    if show_rankings and category_products is not None:
        context["category_rows"] = level.ranking(matching_products(category_products, filters))


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
    allowed_filters = {"chart_window", "chart_days", "chart_start", "chart_end", "chart_day", "chart_status",
                       "chart_category", "chart_tag", "page"}
    if set(request.GET) - allowed_filters:
        raise Http404
    category = ranking_selection(request.GET, "chart_category", UNCATEGORIZED, DIRECT_PREFIX)
    tag = ranking_selection(request.GET, "chart_tag", UNTAGGED)
    request.current_app = owner.admin_site.name
    context = owner.admin_site.each_context(request)
    filters = product_chart_filters(request, context["available_apps"], workbench=True)
    filters.update(category=category, tag=tag)
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
            apply_rankings(request, owner, context, show_rankings=not exporting)
            products = matching_products(filters["products"], filters).order_by("-updated_at", "-pk").distinct()
            if exporting:
                date_label = filters["day"]
                if not date_label and filters.get("custom_dates"):
                    date_label = f'{filters["start"]}-{filters["end"]}'
                suffix = "-".join(part for part in ("analysis", date_label, filters["status"]) if part)
                if category:
                    suffix += f"-category-{category}"
                if tag:
                    suffix += f"-tag-{tag}"
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
