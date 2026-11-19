"""Validate bounded, permission-filtered chart snapshots supplied by a host."""
from datetime import date, datetime, timedelta
import math
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


MAX_DAYS = 90
COMMON_FIELDS = {"schema_version", "metric", "as_of", "timezone", "state", "points"}


def _date(value):
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError("Expected a local ISO date")
    result = date.fromisoformat(value)
    if result.isoformat() != value:
        raise ValueError("Expected a local ISO date")
    return result


def _validate_header(snapshot, extra_fields):
    if not isinstance(snapshot, dict) or snapshot.keys() != COMMON_FIELDS | extra_fields:
        raise ValueError("Invalid snapshot fields")
    version = snapshot["schema_version"]
    if type(version) is not int or version != 1:
        raise ValueError("Unknown snapshot version")
    metric = snapshot["metric"]
    if not isinstance(metric, str) or not re.fullmatch(r"[a-z][a-z0-9_.]{0,79}", metric):
        raise ValueError("Invalid metric identifier")
    tz = snapshot["timezone"]
    if not isinstance(tz, str) or not tz or len(tz) > 128 or not tz.isascii():
        raise ValueError("Invalid time zone")
    try:
        ZoneInfo(tz)
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise ValueError("Invalid time zone") from exc
    stamp = snapshot["as_of"]
    if not isinstance(stamp, str) or len(stamp) > 40 or "T" not in stamp:
        raise ValueError("Expected an offset-aware timestamp")
    if stamp.endswith("Z"):
        stamp = stamp[:-1] + "+00:00"
    instant = datetime.fromisoformat(stamp)
    if instant.utcoffset() is None:
        raise ValueError("Expected an offset-aware timestamp")
    state, points = snapshot["state"], snapshot["points"]
    if not isinstance(points, list) or state not in ("ready", "empty", "error"):
        raise ValueError("Invalid series state")
    if state != "ready" and points:
        raise ValueError("Unexpected observations")


def validate_daily_snapshot(snapshot):
    """Return a valid v1 JSON snapshot or raise ValueError; never run a query."""
    _validate_header(snapshot, {"start", "end"})
    start = _date(snapshot["start"])
    days = (_date(snapshot["end"]) - start).days
    if not 1 <= days <= MAX_DAYS:
        raise ValueError("Invalid date range")
    points = snapshot["points"]
    if snapshot["state"] != "ready":
        return snapshot
    if len(points) != days:
        raise ValueError("Expected exactly one bucket per local day")
    observed = False
    for index, point in enumerate(points):
        if not isinstance(point, dict) or point.keys() != {"date", "value"}:
            raise ValueError("Invalid daily observation")
        if point["date"] != (start + timedelta(days=index)).isoformat():
            raise ValueError("Unexpected bucket date")
        value = point["value"]
        if value is not None:
            if type(value) not in (int, float) or abs(value) > 2**53 - 1 or not math.isfinite(value):
                raise ValueError("Invalid numeric observation")
            observed = True
    if not observed:
        raise ValueError("Use empty for a series with no observed values")
    return snapshot


def validate_category_snapshot(snapshot):
    """A point-in-time v1 distribution of counts in display order."""
    _validate_header(snapshot, {"dimension"})
    if snapshot["dimension"] != "category":
        raise ValueError("Expected a category snapshot")
    if snapshot["state"] != "ready":
        return snapshot
    points = snapshot["points"]
    if not 1 <= len(points) <= 64:
        raise ValueError("Invalid number of categories")
    keys = set()
    for point in points:
        if not isinstance(point, dict) or point.keys() != {"key", "label", "value"}:
            raise ValueError("Invalid category observation")
        key, label, count = point["key"], point["label"], point["value"]
        if not isinstance(key, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", key) or key in keys:
            raise ValueError("Invalid category key")
        if not isinstance(label, str) or not label.strip() or len(label) > 120:
            raise ValueError("Invalid category label")
        if count is not None and (type(count) is not int or not 0 <= count <= 2**53 - 1):
            raise ValueError("Invalid category count")
        keys.add(key)
    if all(point["value"] is None for point in points):
        raise ValueError("Use empty when there are no observed counts")
    return snapshot
