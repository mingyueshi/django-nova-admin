"""Host-owned metric: count visible products by the date of their latest update."""
from datetime import datetime, time, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.db import DatabaseError
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone

from .navigation import visible_product_admin


def product_activity_chart(request, app_list):
    model_admin = visible_product_admin(request, app_list)
    if model_admin is None or "updated_at" not in model_admin.get_list_display(request):
        return None
    periods = request.GET.getlist("chart_days")
    if periods and periods not in (["7"], ["30"]):
        return {"invalid_range": True}
    days = int(periods[0]) if periods else 7
    zone_name = timezone.get_current_timezone_name() if settings.USE_TZ else settings.TIME_ZONE
    try:
        zone = ZoneInfo(zone_name)
    except (ValueError, ZoneInfoNotFoundError):
        return {"days": days, "snapshot": None}
    now = datetime.now(dt_timezone.utc)
    end = now.astimezone(zone).date() + timedelta(days=1)
    start = end - timedelta(days=days)
    lower = datetime.combine(start, time.min, tzinfo=zone)
    upper = datetime.combine(end, time.min, tzinfo=zone)
    cutoff = now
    if not settings.USE_TZ:
        lower, upper = lower.replace(tzinfo=None), upper.replace(tzinfo=None)
        cutoff = now.astimezone(zone).replace(tzinfo=None)
    snapshot = {
        "schema_version": 1, "metric": "catalog.products_last_updated",
        "as_of": now.isoformat(), "timezone": zone.key,
        "start": start.isoformat(), "end": end.isoformat(), "state": "empty", "points": [],
    }
    try:
        queryset = model_admin.get_queryset(request).filter(
            updated_at__gte=lower, updated_at__lt=upper, updated_at__lte=cutoff,
        )
        buckets = queryset.order_by().values(day=TruncDate("updated_at", tzinfo=zone)).annotate(
            total=Count("pk", distinct=True)
        )
        counts = {row["day"]: row["total"] for row in buckets}
    except DatabaseError:
        snapshot["state"] = "error"
    else:
        if counts:
            dates = (start + timedelta(days=index) for index in range(days))
            snapshot.update(state="ready", points=[
                {"date": day.isoformat(), "value": counts.get(day, 0)} for day in dates
            ])
    return {"days": days, "snapshot": snapshot}
