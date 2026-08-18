from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, selectinload

from app.models.attendance import AttendanceDay, AttendanceSession
from app.models.enums import DayStatus, SessionStatus
from app.models.user import User


def get_open_session(db: Session, user_id: uuid.UUID) -> AttendanceSession | None:
    return db.scalar(
        select(AttendanceSession).where(
            AttendanceSession.user_id == user_id,
            AttendanceSession.punch_out.is_(None),
        )
    )


def get_open_session_for_update(
    db: Session, user_id: uuid.UUID
) -> AttendanceSession | None:
    return db.scalar(
        select(AttendanceSession)
        .where(
            AttendanceSession.user_id == user_id,
            AttendanceSession.punch_out.is_(None),
        )
        .with_for_update()
    )


def get_or_create_day(
    db: Session, user_id: uuid.UUID, work_date: date
) -> AttendanceDay:
    """Upsert on (user_id, work_date). Concurrency-safe via ON CONFLICT."""
    stmt = (
        pg_insert(AttendanceDay)
        .values(
            id=uuid.uuid4(),
            user_id=user_id,
            work_date=work_date,
            status=DayStatus.ABSENT.value,
            total_seconds=0,
            is_late=False,
        )
        .on_conflict_do_nothing(index_elements=["user_id", "work_date"])
    )
    db.execute(stmt)
    day = db.scalar(
        select(AttendanceDay)
        .where(
            AttendanceDay.user_id == user_id,
            AttendanceDay.work_date == work_date,
        )
        .with_for_update()
    )
    assert day is not None  # guaranteed by the upsert above
    return day


def get_day(db: Session, user_id: uuid.UUID, work_date: date) -> AttendanceDay | None:
    return db.scalar(
        select(AttendanceDay)
        .options(selectinload(AttendanceDay.sessions))
        .where(
            AttendanceDay.user_id == user_id,
            AttendanceDay.work_date == work_date,
        )
    )


def list_days(
    db: Session,
    user_id: uuid.UUID,
    start: date,
    end: date,
    *,
    with_sessions: bool = True,
) -> list[AttendanceDay]:
    stmt = (
        select(AttendanceDay)
        .where(
            AttendanceDay.user_id == user_id,
            AttendanceDay.work_date >= start,
            AttendanceDay.work_date <= end,
        )
        .order_by(AttendanceDay.work_date.desc())
    )
    if with_sessions:
        stmt = stmt.options(selectinload(AttendanceDay.sessions))
    return list(db.scalars(stmt))


def list_days_for_users(
    db: Session, start: date, end: date, user_ids: list[uuid.UUID] | None = None
) -> list[tuple[AttendanceDay, User]]:
    stmt = (
        select(AttendanceDay, User)
        .join(User, AttendanceDay.user_id == User.id)
        .where(AttendanceDay.work_date >= start, AttendanceDay.work_date <= end)
        .order_by(AttendanceDay.work_date.desc(), User.name.asc())
    )
    if user_ids:
        stmt = stmt.where(AttendanceDay.user_id.in_(user_ids))
    return [(row[0], row[1]) for row in db.execute(stmt).all()]


def days_by_date(db: Session, work_date: date) -> dict[uuid.UUID, AttendanceDay]:
    rows = db.scalars(
        select(AttendanceDay)
        .options(selectinload(AttendanceDay.sessions))
        .where(AttendanceDay.work_date == work_date)
    )
    return {row.user_id: row for row in rows}


def list_sessions_in_range(
    db: Session, user_id: uuid.UUID, start: datetime, end: datetime
) -> list[AttendanceSession]:
    return list(
        db.scalars(
            select(AttendanceSession)
            .where(
                AttendanceSession.user_id == user_id,
                AttendanceSession.punch_in >= start,
                AttendanceSession.punch_in < end,
            )
            .order_by(AttendanceSession.punch_in.asc())
        )
    )


def get_session(db: Session, session_id: uuid.UUID) -> AttendanceSession | None:
    return db.get(AttendanceSession, session_id)


def recompute_day_totals(db: Session, day: AttendanceDay) -> None:
    """Recompute derived day fields from its sessions. Single source of truth."""
    totals = db.execute(
        select(
            func.coalesce(func.sum(AttendanceSession.duration_seconds), 0),
            func.min(AttendanceSession.punch_in),
            func.max(AttendanceSession.punch_out),
            func.count(AttendanceSession.id).filter(
                AttendanceSession.punch_out.is_(None)
            ),
            func.count(AttendanceSession.id),
        ).where(AttendanceSession.attendance_day_id == day.id)
    ).one()
    total_seconds, first_in, last_out, open_count, session_count = totals

    day.total_seconds = int(total_seconds or 0)
    day.first_punch_in = first_in
    day.last_punch_out = last_out
    if open_count:
        day.status = DayStatus.PRESENT
    elif session_count:
        day.status = DayStatus.CHECKED_OUT
    else:
        day.status = DayStatus.ABSENT
    db.flush()


def stale_open_sessions(db: Session, cutoff: datetime) -> list[AttendanceSession]:
    return list(
        db.scalars(
            select(AttendanceSession).where(
                AttendanceSession.punch_out.is_(None),
                AttendanceSession.punch_in < cutoff,
                AttendanceSession.status == SessionStatus.ACTIVE,
            )
        )
    )
