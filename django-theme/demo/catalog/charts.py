"""Host-owned charts and native list drilldowns for visible products."""
import json
from datetime import date, datetime, time, timedelta, timezone as dt_timezone
from typing import NamedTuple
from urllib.parse import urlencode
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.contrib import admin
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.http import Http404
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import pgettext_lazy

from .models import Product
from .navigation import visible_product_admin, visible_products


def _activity_admin(request, app_list):
    owner = visible_product_admin(request, app_list)
    if owner is not None and "updated_at" in owner.get_list_display(request):
        return owner
    return None


def _in_window(queryset, start, end, zone, cutoff):
    lower = datetime.combine(start, time.min, tzinfo=zone)
    upper = datetime.combine(end, time.min, tzinfo=zone)
    if not settings.USE_TZ:
        lower, upper = lower.replace(tzinfo=None), upper.replace(tzinfo=None)
        cutoff = cutoff.astimezone(zone).replace(tzinfo=None)
    return queryset.filter(updated_at__gte=lower, updated_at__lt=upper, updated_at__lte=cutoff)


def _window_signer(request):
    # Bind the signed chart coordinates to the account, site and storage convention.
    # Row visibility always comes from the ModelAdmin handling the new request.
    scope = (
        request.user._meta.label_lower, str(request.user.pk), request.resolver_match.namespace,
        "aware" if settings.USE_TZ else settings.TIME_ZONE,
    )
    return signing.Signer(salt="catalog.product_activity.v1:" + json.dumps(scope))


def _site_url(request, name):
    return reverse(f"{request.resolver_match.namespace}:{name}", urlconf=getattr(request, "urlconf", None))


class ProductDayWindow(NamedTuple):
    day: date
    zone: ZoneInfo
    cutoff: datetime
    days: int


class ProductActivityDayFilter(admin.SimpleListFilter):
    parameter_name = "activity_day"
    title = pgettext_lazy("Nova demo", "Last update date")

    @classmethod
    def signed_window(cls, request):
        values = request.GET.getlist(cls.parameter_name)
        if len(values) != 1:
            raise Http404
        try:
            day_text, token = values[0].split("~", 1)
            stamp, zone_name, days = _window_signer(request).unsign_object(token)
            zone = ZoneInfo(zone_name)
            cutoff = datetime.fromisoformat(stamp)
            day = date.fromisoformat(day_text)
            last = cutoff.astimezone(zone).date()
            if day_text != day.isoformat() or not 0 <= (last - day).days < days:
                raise ValueError("Date outside chart window")
        except (ValueError, signing.BadSignature, ZoneInfoNotFoundError) as exc:
            raise Http404 from exc
        return ProductDayWindow(day, zone, cutoff, days)

    def lookups(self, request, model_admin):
        if self.parameter_name not in request.GET:
            return ()
        if _activity_admin(request, model_admin.admin_site.get_app_list(request)) is not model_admin:
            raise PermissionDenied
        self.day, self.zone, self.cutoff, days = self.signed_window(request)
        self.return_url = _site_url(request, "index") + "?" + urlencode({"chart_days": days}) + "#product-activity-range"
        return [(self.value(), f"{self.day.isoformat()} · {self.zone.key}")]

    def queryset(self, request, queryset):
        return _in_window(queryset, self.day, self.day + timedelta(days=1), self.zone, self.cutoff).distinct()


def product_activity_chart(request, app_list):
    model_admin = _activity_admin(request, app_list)
    if model_admin is None:
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
    snapshot = {
        "schema_version": 1, "metric": "catalog.products_last_updated",
        "as_of": now.isoformat(), "timezone": zone.key,
        "start": start.isoformat(), "end": end.isoformat(), "state": "empty", "points": [],
    }
    try:
        queryset = _in_window(model_admin.get_queryset(request), start, end, zone, now)
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
    activity = {"days": days, "snapshot": snapshot}
    if snapshot["state"] == "ready" and ProductActivityDayFilter in model_admin.get_list_filter(request):
        activity["list_url"] = _site_url(request, "catalog_product_changelist")
        activity["window"] = _window_signer(request).sign_object([snapshot["as_of"], zone.key, days])
    return activity


def can_chart_status(request, owner):
    display = owner.get_list_display(request)
    return (owner.has_module_permission(request) and owner.has_view_or_change_permission(request)
            and ("status" in display or "status_badge" in display)
            and any((spec[0] if isinstance(spec, (tuple, list)) else spec) == "status"
                    for spec in owner.get_list_filter(request)))


def product_status_chart(request, app_list):
    owner = visible_product_admin(request, app_list)
    if owner is None or not can_chart_status(request, owner):
        return None
    snapshot = {
        "schema_version": 1, "metric": "catalog.products_by_status", "dimension": "category",
        "as_of": datetime.now(dt_timezone.utc).isoformat(),
        "timezone": timezone.get_current_timezone_name() if settings.USE_TZ else settings.TIME_ZONE,
        "state": "empty", "points": [],
    }
    try:
        products = visible_products(request, owner, owner.get_queryset(request))
        counts = products.aggregate(**{
            key: Count("pk", filter=Q(status=key), distinct=True) for key in Product.Status.values
        })
    except DatabaseError:
        snapshot["state"] = "error"
    else:
        if any(counts.values()):
            snapshot.update(state="ready", points=[
                {"key": key, "label": str(label), "value": counts[key]} for key, label in Product.Status.choices
            ])
    return {"snapshot": snapshot, "list_url": _site_url(request, "catalog_product_changelist")}
