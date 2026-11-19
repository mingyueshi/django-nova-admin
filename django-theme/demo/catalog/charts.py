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


def _through_cutoff(queryset, zone, cutoff):
    if not settings.USE_TZ:
        cutoff = cutoff.astimezone(zone).replace(tzinfo=None)
    return queryset.filter(updated_at__lte=cutoff)


def _in_window(queryset, start, end, zone, cutoff):
    lower = datetime.combine(start, time.min, tzinfo=zone)
    upper = datetime.combine(end, time.min, tzinfo=zone)
    if not settings.USE_TZ:
        lower, upper = lower.replace(tzinfo=None), upper.replace(tzinfo=None)
    return _through_cutoff(queryset, zone, cutoff).filter(updated_at__gte=lower, updated_at__lt=upper)


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


class ChartWindow(NamedTuple):
    cutoff: datetime
    zone: ZoneInfo
    days: int

    @property
    def last(self):
        return self.cutoff.astimezone(self.zone).date()

    def parse_day(self, text):
        day = date.fromisoformat(text)
        if day.isoformat() != text or not 0 <= (self.last - day).days < self.days:
            raise ValueError("Date outside chart window")
        return day

    def sign(self, request):
        return _window_signer(request).sign_object([self.cutoff.isoformat(), self.zone.key, self.days])

    @classmethod
    def from_token(cls, request, token):
        try:
            stamp, zone, days = _window_signer(request).unsign_object(token)
            cutoff = datetime.fromisoformat(stamp)
            if cutoff.utcoffset() is None or type(days) is not int or days not in (7, 30):
                raise ValueError("Invalid chart window")
            return cls(cutoff, ZoneInfo(zone), days)
        except (TypeError, ValueError, signing.BadSignature, ZoneInfoNotFoundError) as exc:
            raise Http404 from exc


def _single(query, key):
    values = query.getlist(key)
    if len(values) > 1:
        raise Http404
    return values[0] if values else ""


class ProductDayWindow(NamedTuple):
    day: date | None
    zone: ZoneInfo
    cutoff: datetime
    days: int


class ProductActivityDayFilter(admin.SimpleListFilter):
    parameter_name = "activity_day"
    title = pgettext_lazy("Nova demo", "Last update date")

    @classmethod
    def signed_window(cls, request):
        try:
            day_text, token = _single(request.GET, cls.parameter_name).split("~", 1)
            window = ChartWindow.from_token(request, token)
            # Clearing the native status filter still leaves the signed upper bound in effect.
            day = None if day_text == "all" else window.parse_day(day_text)
        except ValueError as exc:
            raise Http404 from exc
        return ProductDayWindow(day, window.zone, window.cutoff, window.days)

    def lookups(self, request, model_admin):
        if self.parameter_name not in request.GET:
            return ()
        if _activity_admin(request, model_admin.admin_site.get_app_list(request)) is not model_admin:
            raise PermissionDenied
        self.day, self.zone, self.cutoff, days = self.signed_window(request)
        # Django's date filter omits the offset during an ambiguous local hour.
        self.local_cutoff = self.cutoff.astimezone(self.zone).strftime("%Y-%m-%d %H:%M:%S %z")
        params = {"chart_days": days}
        day_text = self.day.isoformat() if self.day else ""
        if can_chart_status(request, model_admin):
            params.update(chart_day=day_text, chart_window=self.value().split("~", 1)[1])
        if "status__exact" in request.GET:
            status = _single(request.GET, "status__exact")
            if status not in Product.Status.values:
                raise Http404
            self.status_label = Product.Status(status).label
            params["chart_status"] = status
        self.return_url = _site_url(request, "index") + "?" + urlencode(params) + "#product-activity-range"
        label = day_text or pgettext_lazy("Nova demo", "All dates")
        return [(self.value(), f"{label} · {self.zone.key}")]

    def choices(self, changelist):
        choices = super().choices(changelist)
        all_dates = next(choices)
        token = self.value().split("~", 1)[1]
        all_dates.update(selected=self.day is None, query_string=changelist.get_query_string(
            {self.parameter_name: "all~" + token}
        ))
        yield all_dates
        if self.day is not None:
            yield from choices

    def queryset(self, request, queryset):
        if self.day is None:
            return _through_cutoff(queryset, self.zone, self.cutoff).distinct()
        return _in_window(queryset, self.day, self.day + timedelta(days=1), self.zone, self.cutoff).distinct()


def product_chart_filters(request, app_list):
    """Resolve both chart dimensions and their common observation window once per page."""
    owner = visible_product_admin(request, app_list)
    daily = owner is not None and "updated_at" in owner.get_list_display(request)
    status_visible = owner is not None and can_chart_status(request, owner)
    drill_days = daily and ProductActivityDayFilter in owner.get_list_filter(request)
    linked = drill_days and status_visible
    day_text = _single(request.GET, "chart_day")
    status = _single(request.GET, "chart_status")
    token = _single(request.GET, "chart_window")
    if (day_text or status or token) and not linked:
        raise PermissionDenied
    if (day_text or status or "chart_window" in request.GET) and not token:
        raise Http404
    if status and status not in Product.Status.values:
        raise Http404
    periods = request.GET.getlist("chart_days")
    invalid_range = bool(periods and periods not in (["7"], ["30"]))
    days = int(periods[0]) if periods and not invalid_range else 7
    filters = {"daily": daily, "status_visible": status_visible, "drill_days": drill_days,
               "days": days, "invalid_range": invalid_range, "status": status, "day": day_text}
    if not daily and not status_visible:
        return filters
    if token:
        # A range change may resize the period, but keeps the observed instant and zone.
        window = ChartWindow.from_token(request, token)
        if periods:
            window = window._replace(days=days)
        else:
            filters["days"] = days = window.days
    else:
        zone_name = timezone.get_current_timezone_name() if settings.USE_TZ else settings.TIME_ZONE
        try:
            window = ChartWindow(datetime.now(dt_timezone.utc), ZoneInfo(zone_name), days)
        except (ValueError, ZoneInfoNotFoundError):
            return filters
    filters["period"] = window
    filters["list_url"] = _site_url(request, "catalog_product_changelist")
    if drill_days:
        filters["window"] = window.sign(request)
    if linked:
        filters.update(linked=True, dates=[(window.last - timedelta(days=i)).isoformat() for i in range(days)],
                       statuses=Product.Status.choices, status_label=Product.Status(status).label if status else "",
                       reset_url=_site_url(request, "index") if token else "")
    if day_text:
        try:
            day = window.parse_day(day_text)
        except ValueError:
            filters["invalid_day"] = True
            return filters
        filters["selected_day"] = day
    if linked:
        filters["coordinate"] = (day_text or "all") + "~" + filters["window"]
    if (day_text or status) and not invalid_range:
        params = {"activity_day": filters["coordinate"]}
        if status:
            params["status__exact"] = status
        filters["result_url"] = filters["list_url"] + "?" + urlencode(params)
    try:
        filters["products"] = visible_products(request, owner, owner.get_queryset(request))
    except DatabaseError:
        filters["products"] = None
    return filters


def product_activity_chart(request, app_list, filters=None):
    filters = product_chart_filters(request, app_list) if filters is None else filters
    if not filters["daily"]:
        return None
    activity = {"days": filters["days"], "invalid_range": filters["invalid_range"]}
    period = filters.get("period")
    if not period or filters["invalid_range"] or filters.get("invalid_day"):
        return activity
    end = period.last + timedelta(days=1)
    start = end - timedelta(days=period.days)
    snapshot = {
        "schema_version": 1, "metric": "catalog.products_last_updated",
        "as_of": period.cutoff.isoformat(), "timezone": period.zone.key,
        "start": start.isoformat(), "end": end.isoformat(), "state": "empty", "points": [],
    }
    activity["snapshot"] = snapshot
    if filters["products"] is None:
        snapshot["state"] = "error"
        return activity
    try:
        queryset = _in_window(filters["products"], start, end, period.zone, period.cutoff)
        if filters["status"]:
            queryset = queryset.filter(status=filters["status"])
        buckets = queryset.order_by().values(day=TruncDate("updated_at", tzinfo=period.zone)).annotate(
            total=Count("pk", distinct=True)
        )
        counts = {row["day"]: row["total"] for row in buckets}
    except DatabaseError:
        snapshot["state"] = "error"
    else:
        if counts:
            dates = (start + timedelta(days=index) for index in range(period.days))
            snapshot.update(state="ready", points=[
                {"date": day.isoformat(), "value": counts.get(day, 0)} for day in dates
            ])
    if snapshot["state"] == "ready" and filters["drill_days"]:
        activity.update(list_url=filters["list_url"], window=filters["window"])
    return activity


def can_chart_status(request, owner):
    display = owner.get_list_display(request)
    return (owner.has_module_permission(request) and owner.has_view_or_change_permission(request)
            and ("status" in display or "status_badge" in display)
            and any((spec[0] if isinstance(spec, (tuple, list)) else spec) == "status"
                    for spec in owner.get_list_filter(request)))


def product_status_chart(request, app_list, filters=None):
    filters = product_chart_filters(request, app_list) if filters is None else filters
    if not filters["status_visible"]:
        return None
    period = filters.get("period")
    if filters.get("invalid_day") or (filters["invalid_range"] and (filters["status"] or filters["day"])):
        return None  # The daily card already displays the input error.
    if not period:
        return {"snapshot": None}
    snapshot = {
        "schema_version": 1, "metric": "catalog.products_by_status", "dimension": "category",
        "as_of": period.cutoff.isoformat(), "timezone": period.zone.key,
        "state": "empty", "points": [],
    }
    products = filters["products"]
    if products is None:
        snapshot["state"] = "error"
        return {"snapshot": snapshot}
    try:
        day = filters.get("selected_day")
        if day:
            products = _in_window(products, day, day + timedelta(days=1), period.zone, period.cutoff)
        elif filters.get("coordinate"):
            products = _through_cutoff(products, period.zone, period.cutoff)
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
    return {"snapshot": snapshot, "list_url": filters["list_url"]}
