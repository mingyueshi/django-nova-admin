"""Read-only calendar of successful publications on the current ProductAdmin."""
import calendar
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone as dt_timezone

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponseNotAllowed
from django.template.response import TemplateResponse
from django.utils import timezone

from .models import ProductPublicationRequest
from .product_board import can_view_board


def calendar_parameter(query, key):
    values = query.getlist(key)
    if not values:
        return None
    if len(values) != 1:
        raise Http404
    text = values[0] + "-01" if key == "month" else values[0]
    try:
        value = date.fromisoformat(text)
    except ValueError as exc:
        raise Http404 from exc
    if value.isoformat() != text:
        raise Http404
    return value


def visible_publications(request, owner, first, last, selected, zone):
    products = owner.get_queryset(request)
    reviews = ProductPublicationRequest.objects.using(products.db).filter(
        product_id__in=products.values("pk"), result=ProductPublicationRequest.Result.APPROVED,
    )
    # Local UTC offsets are less than a day. Bound the SQL scan, then classify each
    # instant in Python: even a repeated or skipped local midnight has one answer.
    margin = 1 if settings.USE_TZ else 0
    storage_zone = dt_timezone.utc if settings.USE_TZ else None
    start = first.toordinal() - margin
    stop = last.toordinal() + 1 + margin
    if start >= date.min.toordinal():
        reviews = reviews.filter(reviewed_at__gte=datetime.combine(date.fromordinal(start), time.min, storage_zone))
    if stop <= date.max.toordinal():
        reviews = reviews.filter(reviewed_at__lt=datetime.combine(date.fromordinal(stop), time.min, storage_zone))

    # Keep the last approval of each product per local day, in chronological order (latest first).
    days = defaultdict(dict)
    events = reviews.order_by("-reviewed_at", "product_id").values_list("product_id", "reviewed_at")
    for pk, stamp in events.iterator():
        local = timezone.localtime(stamp, zone) if timezone.is_aware(stamp) else stamp
        day = local.date()
        if first <= day <= last:
            days[day].setdefault(pk, local)

    product_ids = {pk for daily in days.values() for pk in daily}
    visible = {pk: obj for pk, obj in products.in_bulk(product_ids).items()
               if owner.has_view_or_change_permission(request, obj)}
    counts = {day: sum(pk in visible for pk in daily) for day, daily in days.items()}
    details = [{"product": visible[pk], "approved_at": stamp, "offset": stamp.strftime("%z")}
               for pk, stamp in days.get(selected, {}).items() if pk in visible]
    return counts, details


def publication_calendar(request, owner):
    if not can_view_board(request, owner):
        raise PermissionDenied
    if request.method not in ("GET", "HEAD"):
        return HttpResponseNotAllowed(["GET", "HEAD"])
    zone = timezone.get_current_timezone() if settings.USE_TZ else timezone.get_default_timezone()
    today = timezone.localdate(timezone=zone) if settings.USE_TZ else timezone.now().date()
    selected = calendar_parameter(request.GET, "day")
    month = calendar_parameter(request.GET, "month") or (selected or today).replace(day=1)
    if selected and selected.replace(day=1) != month:
        raise Http404

    grid = calendar.Calendar(firstweekday=calendar.MONDAY).monthdayscalendar(month.year, month.month)
    last = month.replace(day=calendar.monthrange(month.year, month.month)[1])
    counts, details = visible_publications(request, owner, month, last, selected, zone)
    weeks = []
    for week in grid:
        cells = []
        for number in week:
            if number:
                day = month.replace(day=number)
                cells.append({"day": day, "count": counts.get(day, 0)})
            else:
                cells.append(None)
        weeks.append(cells)

    request.current_app = owner.admin_site.name
    context = {
        **owner.admin_site.each_context(request),
        "opts": owner.opts, "title": "商品上架日历",
        "month": month, "weeks": weeks, "today": today, "selected": selected, "details": details,
        "empty_month": not any(counts.values()), "zone_name": str(zone),
        "previous_month": (month - timedelta(days=1)).isoformat()[:7] if month > date.min else None,
        "next_month": (last + timedelta(days=1)).isoformat()[:7] if last < date.max else None,
    }
    return TemplateResponse(request, "admin/catalog/product/publication_calendar.html", context)
