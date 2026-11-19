"""Validate the bounded, permission-filtered daily series supplied by a host."""
from datetime import date, datetime, timedelta
import math
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


MAX_DAYS = 90
FIELDS = {"schema_version", "metric", "as_of", "timezone", "start", "end", "state", "points"}


def _date(value):
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError("Expected a local ISO date")
    result = date.fromisoformat(value)
    if result.isoformat() != value:
        raise ValueError("Expected a local ISO date")
    return result


def validate_daily_snapshot(snapshot):
    """Return a valid v1 JSON snapshot or raise ValueError; never run a query."""
    if not isinstance(snapshot, dict) or snapshot.keys() != FIELDS:
        raise ValueError("Invalid daily snapshot fields")
    version = snapshot["schema_version"]
    if type(version) is not int or version != 1:
        raise ValueError("Unknown daily snapshot version")
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
    start = _date(snapshot["start"])
    days = (_date(snapshot["end"]) - start).days
    if not 1 <= days <= MAX_DAYS:
        raise ValueError("Invalid date range")
    state, points = snapshot["state"], snapshot["points"]
    if not isinstance(points, list) or state not in ("ready", "empty", "error"):
        raise ValueError("Invalid series state")
    if state != "ready":
        if points:
            raise ValueError("Unexpected observations")
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
