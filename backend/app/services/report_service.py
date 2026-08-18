"""CSV attendance reporting.

Rows are streamed so a wide date range does not materialise in memory. The
row-building step is deliberately separate from the CSV writer, so an
Excel/PDF exporter can reuse `build_rows` unchanged.
"""

from __future__ import annotations

import csv
import io
import uuid
from collections.abc import Iterator
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.core.time import format_duration, hours_decimal, to_zone, utcnow
from app.models.workspace import Workspace
from app.repositories import attendance_repo
from app.services.attendance_service import elapsed_seconds

COLUMNS = [
    "Date",
    "User",
    "Member ID",
    "First Punch In",
    "Last Punch Out",
    "Total Hours",
    "Total Duration",
    "Sessions",
    "Status",
    "Late",
]


def build_rows(
    db: Session,
    workspace: Workspace,
    start: date,
    end: date,
    user_ids: list[uuid.UUID] | None = None,
    now: datetime | None = None,
) -> Iterator[list[str]]:
    now = now or utcnow()
    tz = workspace.timezone
    pairs = attendance_repo.list_days_for_users(db, start, end, user_ids)
    for day, user in pairs:
        running = sum(
            elapsed_seconds(s, now) for s in day.sessions if s.punch_out is None
        )
        total = day.total_seconds + running
        yield [
            day.work_date.isoformat(),
            user.name,
            user.member_id,
            to_zone(day.first_punch_in, tz).strftime("%Y-%m-%d %H:%M:%S")
            if day.first_punch_in
            else "",
            to_zone(day.last_punch_out, tz).strftime("%Y-%m-%d %H:%M:%S")
            if day.last_punch_out
            else "",
            f"{hours_decimal(total):.2f}",
            format_duration(total),
            str(len(day.sessions)),
            day.status.value,
            "YES" if day.is_late else "NO",
        ]


def _sanitise(value: str) -> str:
    """Neutralise spreadsheet formula injection in exported text."""
    if value and value[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def stream_csv(
    db: Session,
    workspace: Workspace,
    start: date,
    end: date,
    user_ids: list[uuid.UUID] | None = None,
) -> Iterator[str]:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")

    def flush() -> str:
        buffer.seek(0)
        chunk = buffer.read()
        buffer.seek(0)
        buffer.truncate(0)
        return chunk

    writer.writerow(COLUMNS)
    yield flush()
    for row in build_rows(db, workspace, start, end, user_ids):
        writer.writerow([_sanitise(cell) for cell in row])
        yield flush()


def filename(start: date, end: date) -> str:
    return f"attendance_{start.isoformat()}_to_{end.isoformat()}.csv"
