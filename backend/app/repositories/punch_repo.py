from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.enums import PunchType, ValidationStatus
from app.models.punch_event import PunchEvent


def add(db: Session, event: PunchEvent) -> PunchEvent:
    db.add(event)
    db.flush()
    return event


def find_by_idempotency_key(
    db: Session, user_id: uuid.UUID, key: str
) -> PunchEvent | None:
    return db.scalar(
        select(PunchEvent).where(
            PunchEvent.user_id == user_id, PunchEvent.idempotency_key == key
        )
    )


def last_accepted_event(db: Session, user_id: uuid.UUID) -> PunchEvent | None:
    """Most recent accepted punch, used for impossible-movement checks."""
    return db.scalar(
        select(PunchEvent)
        .where(
            PunchEvent.user_id == user_id,
            PunchEvent.validation_status == ValidationStatus.ACCEPTED,
            PunchEvent.latitude.is_not(None),
            PunchEvent.location_purged.is_(False),
        )
        .order_by(PunchEvent.server_timestamp.desc())
        .limit(1)
    )


def _query(
    user_id: uuid.UUID | None,
    session_id: uuid.UUID | None,
    validation_status: ValidationStatus | None,
    punch_type: PunchType | None,
    start: datetime | None,
    end: datetime | None,
) -> Select:
    stmt = select(PunchEvent)
    if user_id is not None:
        stmt = stmt.where(PunchEvent.user_id == user_id)
    if session_id is not None:
        stmt = stmt.where(PunchEvent.session_id == session_id)
    if validation_status is not None:
        stmt = stmt.where(PunchEvent.validation_status == validation_status)
    if punch_type is not None:
        stmt = stmt.where(PunchEvent.type == punch_type)
    if start is not None:
        stmt = stmt.where(PunchEvent.server_timestamp >= start)
    if end is not None:
        stmt = stmt.where(PunchEvent.server_timestamp < end)
    return stmt


def list_events(
    db: Session,
    *,
    user_id: uuid.UUID | None = None,
    session_id: uuid.UUID | None = None,
    validation_status: ValidationStatus | None = None,
    punch_type: PunchType | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[PunchEvent], int]:
    stmt = _query(user_id, session_id, validation_status, punch_type, start, end)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(
        db.scalars(
            stmt.order_by(PunchEvent.server_timestamp.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return rows, total
