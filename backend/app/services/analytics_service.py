"""Attendance analytics derived entirely from stored attendance data.

Nothing here is estimated or synthesised: every figure is computed from
`attendance_days` / `attendance_sessions` rows produced by verified punches.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.time import local_date, month_range, to_zone, utcnow, week_range
from app.models.enums import DayStatus, Team
from app.models.user import User
from app.models.workspace import Workspace
from app.repositories import attendance_repo
from app.services.attendance_service import elapsed_seconds


def resolve_period(
    period: str,
    workspace: Workspace,
    now: datetime | None = None,
    custom_from: date | None = None,
    custom_to: date | None = None,
) -> tuple[date, date]:
    now = now or utcnow()
    today = local_date(now, workspace.timezone)
    if period == "today":
        return today, today
    if period == "week":
        return week_range(today)
    if period == "month":
        return month_range(today)
    if period == "custom":
        if custom_from is None or custom_to is None:
            raise ValueError("custom period requires from_date and to_date")
        if custom_to < custom_from:
            raise ValueError("to_date must not be before from_date")
        return custom_from, custom_to
    raise ValueError(f"Unknown period: {period}")


def _working_days(start: date, end: date, today: date) -> int:
    """Mon-Fri days in the range that have already happened."""
    effective_end = min(end, today)
    if effective_end < start:
        return 0
    count = 0
    cursor = start
    while cursor <= effective_end:
        if cursor.weekday() < 5:
            count += 1
        cursor += timedelta(days=1)
    return count


def summary(
    db: Session,
    user: User,
    workspace: Workspace,
    start: date,
    end: date,
    period_label: str = "custom",
    now: datetime | None = None,
) -> dict:
    now = now or utcnow()
    tz = workspace.timezone
    today = local_date(now, tz)
    days = attendance_repo.list_days(db, user.id, start, end)

    total_seconds = 0
    present_days = 0
    late_arrivals = 0
    longest_session = 0
    arrival_minutes: list[int] = []
    departure_minutes: list[int] = []

    for day in days:
        running = sum(
            elapsed_seconds(s, now) for s in day.sessions if s.punch_out is None
        )
        day_total = day.total_seconds + running
        if not day.sessions:
            continue
        present_days += 1
        total_seconds += day_total
        if day.is_late:
            late_arrivals += 1
        for session in day.sessions:
            longest_session = max(longest_session, elapsed_seconds(session, now))
        if day.first_punch_in:
            local_in = to_zone(day.first_punch_in, tz)
            arrival_minutes.append(local_in.hour * 60 + local_in.minute)
        if day.last_punch_out:
            local_out = to_zone(day.last_punch_out, tz)
            departure_minutes.append(local_out.hour * 60 + local_out.minute)

    working_days = _working_days(start, end, today)
    return {
        "period": period_label,
        "from_date": start,
        "to_date": end,
        "timezone": tz,
        "days_present": present_days,
        "days_absent": max(0, working_days - present_days),
        "working_days": working_days,
        "total_seconds": total_seconds,
        "average_seconds_per_present_day": (
            total_seconds // present_days if present_days else 0
        ),
        "longest_session_seconds": longest_session,
        "late_arrivals": late_arrivals,
        "average_arrival_minutes": (
            sum(arrival_minutes) // len(arrival_minutes) if arrival_minutes else None
        ),
        "average_departure_minutes": (
            sum(departure_minutes) // len(departure_minutes)
            if departure_minutes
            else None
        ),
    }


def presence_snapshot(
    db: Session, workspace: Workspace, now: datetime | None = None
) -> dict:
    """Who is inside right now, who is not, and for how long.

    Presence is derived from open sessions, never from a cached flag, so it is
    always consistent with the attendance tables.
    """
    from app.repositories import user_repo

    now = now or utcnow()
    tz = workspace.timezone
    today = local_date(now, tz)

    users = user_repo.all_active_users(db)
    days = attendance_repo.days_by_date(db, today)

    # Open sessions may have started on an earlier day; look them up per user.
    open_sessions = {}
    for user in users:
        session = attendance_repo.get_open_session(db, user.id)
        if session is not None:
            open_sessions[user.id] = session

    present: list[dict] = []
    absent: list[dict] = []
    checked_out: list[dict] = []

    for user in users:
        day = days.get(user.id)
        session = open_sessions.get(user.id)
        base = {
            "user_id": user.id,
            "name": user.name,
            "member_id": user.member_id,
            "email": user.email,
            "team": user.team,
            "is_late": bool(day.is_late) if day else False,
            "session_count": len(day.sessions) if day else 0,
        }
        if session is not None:
            running = elapsed_seconds(session, now)
            closed = day.total_seconds if day else 0
            present.append(
                {
                    **base,
                    "state": DayStatus.PRESENT,
                    "punch_in": session.punch_in,
                    "elapsed_seconds": running,
                    "total_seconds": closed + running,
                }
            )
        elif day is not None and day.sessions:
            checked_out.append(
                {
                    **base,
                    "state": DayStatus.CHECKED_OUT,
                    "punch_in": day.first_punch_in,
                    "last_punch_out": day.last_punch_out,
                    "elapsed_seconds": 0,
                    "total_seconds": day.total_seconds,
                }
            )
        else:
            absent.append(
                {**base, "state": DayStatus.ABSENT, "elapsed_seconds": 0, "total_seconds": 0}
            )

    present.sort(key=lambda e: e["punch_in"])
    checked_out.sort(key=lambda e: e["name"])
    absent.sort(key=lambda e: e["name"])

    # Bifurcation by team, in organisational order rather than alphabetical.
    breakdown = []
    for team in (Team.EXECUTIVE, Team.CORE, Team.MEMBER):
        breakdown.append(
            {
                "team": team,
                "total": sum(1 for u in users if u.team == team),
                "present": sum(1 for e in present if e["team"] == team),
                "absent": sum(1 for e in absent if e["team"] == team),
                "checked_out": sum(1 for e in checked_out if e["team"] == team),
            }
        )

    return {
        "date": today,
        "timezone": tz,
        "server_time": now,
        "total_users": len(users),
        "breakdown": breakdown,
        "present_count": len(present),
        "absent_count": len(absent),
        "checked_out_count": len(checked_out),
        "present": present,
        "absent": absent,
        "checked_out": checked_out,
    }
