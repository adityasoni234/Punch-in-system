"""Attendance state machine, punch processing and read models.

Invariants enforced here (and, for the critical one, by the database):

* A user has at most one open session at any time. `uq_one_open_session_per_user`
  is a partial unique index, so two racing punch-in requests cannot both create
  a session even if they slip past the application check.
* Every punch mutation runs inside one transaction that begins with a
  `SELECT ... FOR UPDATE` on the user row, serialising that user's punches.
* Durations are computed exclusively from server timestamps.
* Every attempt, accepted or rejected, produces a `punch_events` row and an
  audit entry.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError, ConflictError, ErrorCode, GeofenceError
from app.core.logging import get_logger
from app.core.time import local_date, to_zone, utcnow
from app.middleware.request_context import current_client_ip, current_user_agent_hash
from app.models.attendance import AttendanceDay, AttendanceSession
from app.models.enums import (
    AuditAction,
    DayStatus,
    PunchType,
    SessionStatus,
    UserStatus,
    ValidationStatus,
)
from app.models.punch_event import PunchEvent
from app.models.user import User
from app.models.workspace import Workspace
from app.repositories import attendance_repo, punch_repo, user_repo
from app.schemas.attendance import PunchRequest
from app.services import audit_service, geofence_service, workspace_service

logger = get_logger(__name__)


@dataclass(slots=True)
class PunchOutcome:
    session: AttendanceSession
    state: DayStatus
    today_total_seconds: int
    distance_meters: float
    accuracy_meters: float
    radius_meters: int
    server_time: datetime
    message: str


# --------------------------------------------------------------------------
# Read models
# --------------------------------------------------------------------------


def elapsed_seconds(session: AttendanceSession, now: datetime) -> int:
    if session.punch_out is not None:
        return int(session.duration_seconds or 0)
    return max(0, int((now - session.punch_in).total_seconds()))


def today_state(
    db: Session, user: User, workspace: Workspace, now: datetime | None = None
) -> dict:
    now = now or utcnow()
    tz = workspace.timezone
    today = local_date(now, tz)

    open_session = attendance_repo.get_open_session(db, user.id)
    day = attendance_repo.get_day(db, user.id, today)

    sessions: list[AttendanceSession] = list(day.sessions) if day else []
    total = day.total_seconds if day else 0

    active_elapsed = 0
    if open_session is not None:
        active_elapsed = elapsed_seconds(open_session, now)
        started_today = local_date(open_session.punch_in, tz) == today
        if started_today:
            # Closed sessions are already in day.total_seconds; add the running one.
            total += active_elapsed
            if all(s.id != open_session.id for s in sessions):
                sessions.append(open_session)
        else:
            # A session that began on an earlier day stays attributed to that
            # day; it is still surfaced so the user can punch out.
            sessions.insert(0, open_session)

    if open_session is not None:
        state = DayStatus.PRESENT
    elif day is not None and day.status != DayStatus.ABSENT:
        state = day.status
    else:
        state = DayStatus.ABSENT

    sessions.sort(key=lambda s: s.punch_in)
    return {
        "state": state,
        "date": today,
        "timezone": tz,
        "server_time": now,
        "total_seconds": total,
        "active_session": open_session,
        "active_elapsed_seconds": active_elapsed,
        "sessions": sessions,
    }


def day_payload(day: AttendanceDay, now: datetime) -> dict:
    sessions = sorted(day.sessions, key=lambda s: s.punch_in)
    running = sum(
        elapsed_seconds(s, now) for s in sessions if s.punch_out is None
    )
    return {
        "date": day.work_date,
        "status": day.status,
        "total_seconds": day.total_seconds + running,
        "first_punch_in": day.first_punch_in,
        "last_punch_out": day.last_punch_out,
        "is_late": day.is_late,
        "session_count": len(sessions),
        "sessions": sessions,
    }


def history(
    db: Session,
    user: User,
    workspace: Workspace,
    start: date,
    end: date,
    now: datetime | None = None,
) -> dict:
    now = now or utcnow()
    days = attendance_repo.list_days(db, user.id, start, end)
    payloads = [day_payload(d, now) for d in days]
    return {
        "from_date": start,
        "to_date": end,
        "timezone": workspace.timezone,
        "server_time": now,
        "total_seconds": sum(p["total_seconds"] for p in payloads),
        "days": payloads,
    }


# --------------------------------------------------------------------------
# Punch processing
# --------------------------------------------------------------------------


def _record_event(
    db: Session,
    *,
    user_id: uuid.UUID,
    punch_type: PunchType,
    result: geofence_service.GeofenceResult,
    workspace: Workspace,
    now: datetime,
    client_timestamp: datetime | None,
    idempotency_key: str | None,
    session_id: uuid.UUID | None = None,
) -> PunchEvent:
    event = PunchEvent(
        user_id=user_id,
        session_id=session_id,
        workspace_id=workspace.id,
        type=punch_type,
        server_timestamp=now,
        client_timestamp=client_timestamp,
        latitude=result.latitude,
        longitude=result.longitude,
        accuracy_meters=result.accuracy_meters,
        distance_meters=result.distance_meters,
        radius_snapshot=workspace.radius_meters,
        accuracy_threshold_snapshot=workspace.accuracy_threshold_meters,
        validation_status=(
            ValidationStatus.ACCEPTED if result.accepted else ValidationStatus.REJECTED
        ),
        rejection_reason=result.rejection_code,
        ip_address=current_client_ip(),
        user_agent_hash=current_user_agent_hash(),
        idempotency_key=idempotency_key,
    )
    return punch_repo.add(db, event)


def _audit_metadata(result: geofence_service.GeofenceResult) -> dict:
    data: dict = {
        "accuracy_m": round(result.accuracy_meters, 1),
        "radius_m": result.radius_meters,
        "accuracy_threshold_m": result.accuracy_threshold_meters,
    }
    if result.distance_meters is not None:
        data["distance_m"] = round(result.distance_meters, 1)
    if result.rejection_code:
        data["reason"] = result.rejection_code
    if result.flags:
        data["flags"] = result.flags
    return data


def _reject(
    db: Session,
    *,
    user: User,
    punch_type: PunchType,
    result: geofence_service.GeofenceResult,
    workspace: Workspace,
    now: datetime,
    client_timestamp: datetime | None,
    idempotency_key: str | None,
) -> None:
    _record_event(
        db,
        user_id=user.id,
        punch_type=punch_type,
        result=result,
        workspace=workspace,
        now=now,
        client_timestamp=client_timestamp,
        idempotency_key=idempotency_key,
    )
    audit_service.failure(
        db,
        AuditAction.PUNCH_IN_REJECTED
        if punch_type == PunchType.IN
        else AuditAction.PUNCH_OUT_REJECTED,
        actor_user_id=user.id,
        metadata=_audit_metadata(result),
    )
    db.commit()
    raise GeofenceError(
        result.message or "Location verification failed.",
        code=result.rejection_code or ErrorCode.OUTSIDE_GEOFENCE,
    )


def _duplicate_outcome(
    db: Session, user: User, workspace: Workspace, existing: PunchEvent, now: datetime
) -> PunchOutcome:
    """Replay of an already-processed request: return the original result."""
    if existing.validation_status == ValidationStatus.REJECTED:
        raise GeofenceError(
            "This punch was already rejected. Please try again with a new request.",
            code=existing.rejection_reason or ErrorCode.OUTSIDE_GEOFENCE,
        )
    session = (
        attendance_repo.get_session(db, existing.session_id)
        if existing.session_id
        else None
    )
    if session is None:
        raise ConflictError(
            "This request was already processed.", code=ErrorCode.DUPLICATE_REQUEST
        )
    state = today_state(db, user, workspace, now)
    return PunchOutcome(
        session=session,
        state=state["state"],
        today_total_seconds=state["total_seconds"],
        distance_meters=float(existing.distance_meters or 0.0),
        accuracy_meters=float(existing.accuracy_meters or 0.0),
        radius_meters=int(existing.radius_snapshot or workspace.radius_meters),
        server_time=now,
        message="This punch was already recorded.",
    )


def _assert_active(user: User) -> None:
    if user.status != UserStatus.ACTIVE:
        raise AppError(
            "This account has been disabled. Contact your administrator.",
            code=ErrorCode.USER_DISABLED,
            status_code=403,
        )


def punch_in(
    db: Session,
    *,
    user: User,
    payload: PunchRequest,
    idempotency_key: str | None,
) -> PunchOutcome:
    workspace = workspace_service.get_active(db)
    now = utcnow()

    # Serialise this user's punches for the duration of the transaction.
    locked = user_repo.lock_for_update(db, user.id)
    if locked is None:
        raise ConflictError("User no longer exists.")
    _assert_active(locked)

    if idempotency_key:
        existing = punch_repo.find_by_idempotency_key(db, user.id, idempotency_key)
        if existing is not None:
            return _duplicate_outcome(db, locked, workspace, existing, now)

    if attendance_repo.get_open_session(db, user.id) is not None:
        raise ConflictError(
            "You are already punched in. Punch out before punching in again.",
            code=ErrorCode.ALREADY_PUNCHED_IN,
        )

    result = geofence_service.validate(
        workspace=workspace,
        latitude=payload.latitude,
        longitude=payload.longitude,
        accuracy=payload.accuracy,
        now=now,
        previous_event=punch_repo.last_accepted_event(db, user.id),
    )
    if not result.accepted:
        _reject(
            db,
            user=locked,
            punch_type=PunchType.IN,
            result=result,
            workspace=workspace,
            now=now,
            client_timestamp=payload.captured_at,
            idempotency_key=idempotency_key,
        )

    work_date = local_date(now, workspace.timezone)
    day = attendance_repo.get_or_create_day(db, user.id, work_date)

    session = AttendanceSession(
        attendance_day_id=day.id,
        user_id=user.id,
        workspace_id=workspace.id,
        punch_in=now,
        status=SessionStatus.ACTIVE,
    )
    db.add(session)
    try:
        db.flush()
    except IntegrityError as exc:  # pragma: no cover - defended by the row lock
        db.rollback()
        raise ConflictError(
            "You are already punched in. Punch out before punching in again.",
            code=ErrorCode.ALREADY_PUNCHED_IN,
        ) from exc

    if day.first_punch_in is None:
        day.first_punch_in = now
        day.is_late = _is_late(now, workspace)
    day.status = DayStatus.PRESENT

    _record_event(
        db,
        user_id=user.id,
        punch_type=PunchType.IN,
        result=result,
        workspace=workspace,
        now=now,
        client_timestamp=payload.captured_at,
        idempotency_key=idempotency_key,
        session_id=session.id,
    )
    metadata = _audit_metadata(result)
    metadata["session_id"] = str(session.id)
    audit_service.success(
        db, AuditAction.PUNCH_IN_SUCCESS, actor_user_id=user.id, metadata=metadata
    )
    if result.flags:
        audit_service.failure(
            db,
            AuditAction.SUSPICIOUS_MOVEMENT,
            actor_user_id=user.id,
            metadata=result.flags,
        )
    db.commit()

    state = today_state(db, locked, workspace, now)
    return PunchOutcome(
        session=session,
        state=state["state"],
        today_total_seconds=state["total_seconds"],
        distance_meters=float(result.distance_meters or 0.0),
        accuracy_meters=result.accuracy_meters,
        radius_meters=result.radius_meters,
        server_time=now,
        message="Punch in successful. Workspace verified.",
    )


def punch_out(
    db: Session,
    *,
    user: User,
    payload: PunchRequest,
    idempotency_key: str | None,
) -> PunchOutcome:
    workspace = workspace_service.get_active(db)
    now = utcnow()

    locked = user_repo.lock_for_update(db, user.id)
    if locked is None:
        raise ConflictError("User no longer exists.")
    _assert_active(locked)

    if idempotency_key:
        existing = punch_repo.find_by_idempotency_key(db, user.id, idempotency_key)
        if existing is not None:
            return _duplicate_outcome(db, locked, workspace, existing, now)

    session = attendance_repo.get_open_session_for_update(db, user.id)
    if session is None:
        raise ConflictError(
            "You are not currently punched in.", code=ErrorCode.NO_ACTIVE_SESSION
        )

    result = geofence_service.validate(
        workspace=workspace,
        latitude=payload.latitude,
        longitude=payload.longitude,
        accuracy=payload.accuracy,
        now=now,
        previous_event=punch_repo.last_accepted_event(db, user.id),
    )
    if not result.accepted:
        _reject(
            db,
            user=locked,
            punch_type=PunchType.OUT,
            result=result,
            workspace=workspace,
            now=now,
            client_timestamp=payload.captured_at,
            idempotency_key=idempotency_key,
        )

    if now <= session.punch_in:  # pragma: no cover - server clock is monotonic enough
        raise ConflictError("Invalid punch-out time.")

    session.punch_out = now
    session.duration_seconds = int((now - session.punch_in).total_seconds())
    session.status = SessionStatus.COMPLETED
    db.flush()

    day = db.get(AttendanceDay, session.attendance_day_id)
    assert day is not None
    attendance_repo.recompute_day_totals(db, day)

    _record_event(
        db,
        user_id=user.id,
        punch_type=PunchType.OUT,
        result=result,
        workspace=workspace,
        now=now,
        client_timestamp=payload.captured_at,
        idempotency_key=idempotency_key,
        session_id=session.id,
    )
    metadata = _audit_metadata(result)
    metadata["session_id"] = str(session.id)
    metadata["duration_seconds"] = session.duration_seconds
    audit_service.success(
        db, AuditAction.PUNCH_OUT_SUCCESS, actor_user_id=user.id, metadata=metadata
    )
    if result.flags:
        audit_service.failure(
            db,
            AuditAction.SUSPICIOUS_MOVEMENT,
            actor_user_id=user.id,
            metadata=result.flags,
        )
    db.commit()

    state = today_state(db, locked, workspace, now)
    return PunchOutcome(
        session=session,
        state=state["state"],
        today_total_seconds=state["total_seconds"],
        distance_meters=float(result.distance_meters or 0.0),
        accuracy_meters=result.accuracy_meters,
        radius_meters=result.radius_meters,
        server_time=now,
        message="Punch out successful.",
    )


def _is_late(punch_in_at: datetime, workspace: Workspace) -> bool:
    local = to_zone(punch_in_at, workspace.timezone)
    start = workspace.attendance_start_time
    threshold_minutes = (
        start.hour * 60 + start.minute + workspace.late_threshold_minutes
    )
    return (local.hour * 60 + local.minute) > threshold_minutes


def auto_close_stale_sessions(db: Session, now: datetime | None = None) -> int:
    """Close sessions left open far longer than a plausible working day.

    Covers the "app closed while punched in / user never punched out" case.
    The session is capped at the configured cutoff and flagged AUTO_CLOSED so
    reports never present it as a verified punch-out.
    """
    now = now or utcnow()
    workspace = workspace_service.get_active(db)
    cutoff = now - timedelta(hours=workspace.auto_close_after_hours)
    stale = attendance_repo.stale_open_sessions(db, cutoff)

    for session in stale:
        end = session.punch_in + timedelta(hours=workspace.auto_close_after_hours)
        session.punch_out = end
        session.duration_seconds = int((end - session.punch_in).total_seconds())
        session.status = SessionStatus.AUTO_CLOSED
        session.note = (
            "Automatically closed: no punch out was recorded within "
            f"{workspace.auto_close_after_hours}h."
        )
        db.flush()
        day = db.get(AttendanceDay, session.attendance_day_id)
        if day is not None:
            attendance_repo.recompute_day_totals(db, day)
        audit_service.failure(
            db,
            AuditAction.SESSION_AUTO_CLOSED,
            actor_user_id=session.user_id,
            metadata={
                "session_id": str(session.id),
                "capped_hours": workspace.auto_close_after_hours,
            },
        )
    if stale:
        db.commit()
    return len(stale)
