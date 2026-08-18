"""Time helpers.

Rule: the server clock is the only clock that counts. Client supplied
timestamps are stored for forensics and never used in a calculation.
All stored timestamps are timezone aware UTC; the workspace timezone is
used solely for bucketing days and for display.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

UTC = timezone.utc


def utcnow() -> datetime:
    """Current server time, timezone aware UTC."""
    return datetime.now(UTC)


def get_zone(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError) as exc:  # pragma: no cover - config guard
        raise ValueError(f"Unknown timezone: {tz_name!r}") from exc


def is_valid_timezone(tz_name: str) -> bool:
    try:
        ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        return False
    return True


def to_zone(dt: datetime, tz_name: str) -> datetime:
    """Convert an aware (or naive-UTC) datetime into the workspace timezone."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(get_zone(tz_name))


def local_date(dt: datetime, tz_name: str) -> date:
    """The workspace-local calendar date a UTC instant belongs to."""
    return to_zone(dt, tz_name).date()


def day_bounds_utc(day: date, tz_name: str) -> tuple[datetime, datetime]:
    """[start, end) of a workspace-local day expressed in UTC."""
    zone = get_zone(tz_name)
    start_local = datetime.combine(day, time.min, tzinfo=zone)
    end_local = datetime.combine(day + timedelta(days=1), time.min, tzinfo=zone)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def range_bounds_utc(start: date, end: date, tz_name: str) -> tuple[datetime, datetime]:
    """[start_of_start_day, start_of_day_after_end) in UTC."""
    start_utc, _ = day_bounds_utc(start, tz_name)
    _, end_utc = day_bounds_utc(end, tz_name)
    return start_utc, end_utc


def week_range(today: date) -> tuple[date, date]:
    """Monday..Sunday week containing `today`."""
    start = today - timedelta(days=today.weekday())
    return start, start + timedelta(days=6)


def month_range(today: date) -> tuple[date, date]:
    start = today.replace(day=1)
    if start.month == 12:
        next_month = start.replace(year=start.year + 1, month=1)
    else:
        next_month = start.replace(month=start.month + 1)
    return start, next_month - timedelta(days=1)


def format_duration(total_seconds: int) -> str:
    """Seconds -> 'HHh MMm' as used across the UI and reports."""
    total_seconds = max(0, int(total_seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes = remainder // 60
    return f"{hours:02d}h {minutes:02d}m"


def hours_decimal(total_seconds: int) -> float:
    return round(max(0, int(total_seconds)) / 3600.0, 2)
