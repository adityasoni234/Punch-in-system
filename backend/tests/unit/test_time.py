from __future__ import annotations

from datetime import date, datetime, timezone

from app.core.time import (
    day_bounds_utc,
    format_duration,
    hours_decimal,
    is_valid_timezone,
    local_date,
    month_range,
    week_range,
)

IST = "Asia/Kolkata"


def test_local_date_crosses_the_utc_boundary_correctly():
    # 19:00 UTC on 18 Aug is already 00:30 IST on 19 Aug.
    instant = datetime(2026, 8, 18, 19, 0, tzinfo=timezone.utc)
    assert local_date(instant, IST) == date(2026, 8, 19)
    assert local_date(instant, "UTC") == date(2026, 8, 18)


def test_day_bounds_are_shifted_by_the_offset():
    start, end = day_bounds_utc(date(2026, 8, 18), IST)
    assert start == datetime(2026, 8, 17, 18, 30, tzinfo=timezone.utc)
    assert end == datetime(2026, 8, 18, 18, 30, tzinfo=timezone.utc)


def test_week_range_is_monday_to_sunday():
    start, end = week_range(date(2026, 8, 18))  # a Tuesday
    assert start == date(2026, 8, 17)
    assert end == date(2026, 8, 23)


def test_month_range():
    assert month_range(date(2026, 8, 18)) == (date(2026, 8, 1), date(2026, 8, 31))
    assert month_range(date(2026, 12, 5)) == (date(2026, 12, 1), date(2026, 12, 31))
    assert month_range(date(2028, 2, 5)) == (date(2028, 2, 1), date(2028, 2, 29))


def test_duration_formatting():
    assert format_duration(0) == "00h 00m"
    assert format_duration(3600) == "01h 00m"
    assert format_duration(27_720) == "07h 42m"
    assert format_duration(-5) == "00h 00m"


def test_hours_decimal():
    assert hours_decimal(3600) == 1.0
    assert hours_decimal(27_720) == 7.7


def test_timezone_validation():
    assert is_valid_timezone(IST)
    assert not is_valid_timezone("Mars/Olympus_Mons")
