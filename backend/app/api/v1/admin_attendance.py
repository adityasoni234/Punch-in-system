from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Query

from app.core.deps import ActiveWorkspace, AdminUser, DbSession
from app.core.errors import AppError, ErrorCode
from app.core.time import local_date, utcnow
from app.models.enums import DayStatus, ValidationStatus
from app.schemas.admin import (
    AdminAttendanceRow,
    AdminDashboardResponse,
    AdminUserAttendance,
    PresenceEntry,
    PunchEventOut,
)
from app.schemas.attendance import DayOut, SessionOut
from app.schemas.auth import UserPublic
from app.schemas.common import Page
from app.services import analytics_service, attendance_service, user_service

router = APIRouter(prefix="/admin", tags=["admin:attendance"])


def _session_out(session) -> SessionOut:
    data = SessionOut.model_validate(session)
    data.is_active = session.punch_out is None
    return data


@router.get(
    "/dashboard",
    response_model=AdminDashboardResponse,
    summary="Live presence overview",
)
def dashboard(
    admin: AdminUser, db: DbSession, workspace: ActiveWorkspace
) -> AdminDashboardResponse:
    snapshot = analytics_service.presence_snapshot(db, workspace)
    return AdminDashboardResponse(
        date=snapshot["date"],
        timezone=snapshot["timezone"],
        server_time=snapshot["server_time"],
        total_users=snapshot["total_users"],
        present_count=snapshot["present_count"],
        absent_count=snapshot["absent_count"],
        checked_out_count=snapshot["checked_out_count"],
        present=[PresenceEntry(**e) for e in snapshot["present"]],
        absent=[PresenceEntry(**e) for e in snapshot["absent"]],
        checked_out=[PresenceEntry(**e) for e in snapshot["checked_out"]],
    )


@router.get(
    "/attendance",
    response_model=list[AdminAttendanceRow],
    summary="Attendance rows across users",
)
def attendance(
    admin: AdminUser,
    db: DbSession,
    workspace: ActiveWorkspace,
    from_date: date | None = None,
    to_date: date | None = None,
    user_id: uuid.UUID | None = None,
    day_status: DayStatus | None = Query(None, alias="status"),
) -> list[AdminAttendanceRow]:
    from app.repositories import attendance_repo

    today = local_date(utcnow(), workspace.timezone)
    start = from_date or today
    end = to_date or today
    if end < start:
        raise AppError("to_date must not be before from_date", code=ErrorCode.VALIDATION_ERROR)

    now = utcnow()
    pairs = attendance_repo.list_days_for_users(
        db, start, end, [user_id] if user_id else None
    )
    rows: list[AdminAttendanceRow] = []
    for day, user in pairs:
        if day_status is not None and day.status != day_status:
            continue
        running = sum(
            attendance_service.elapsed_seconds(s, now)
            for s in day.sessions
            if s.punch_out is None
        )
        rows.append(
            AdminAttendanceRow(
                user_id=user.id,
                name=user.name,
                member_id=user.member_id,
                date=day.work_date,
                status=day.status,
                first_punch_in=day.first_punch_in,
                last_punch_out=day.last_punch_out,
                total_seconds=day.total_seconds + running,
                session_count=len(day.sessions),
                is_late=day.is_late,
            )
        )
    return rows


@router.get(
    "/attendance/{user_id}",
    response_model=AdminUserAttendance,
    summary="One user's attendance detail",
)
def user_attendance(
    user_id: uuid.UUID,
    admin: AdminUser,
    db: DbSession,
    workspace: ActiveWorkspace,
    period: str = Query("month", pattern="^(today|week|month|custom)$"),
    from_date: date | None = None,
    to_date: date | None = None,
) -> AdminUserAttendance:
    user = user_service.get(db, user_id)
    try:
        start, end = analytics_service.resolve_period(
            period, workspace, custom_from=from_date, custom_to=to_date
        )
    except ValueError as exc:
        raise AppError(str(exc), code=ErrorCode.VALIDATION_ERROR) from exc

    data = attendance_service.history(db, user, workspace, start, end)
    return AdminUserAttendance(
        user=UserPublic.model_validate(user),
        from_date=start,
        to_date=end,
        timezone=workspace.timezone,
        total_seconds=data["total_seconds"],
        days=[
            DayOut(**{**d, "sessions": [_session_out(s) for s in d["sessions"]]})
            for d in data["days"]
        ],
    )


@router.get(
    "/punch-events",
    response_model=Page[PunchEventOut],
    summary="Punch verification records (including rejections)",
)
def punch_events(
    admin: AdminUser,
    db: DbSession,
    user_id: uuid.UUID | None = None,
    session_id: uuid.UUID | None = None,
    validation_status: ValidationStatus | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> Page[PunchEventOut]:
    from app.repositories import punch_repo

    rows, total = punch_repo.list_events(
        db,
        user_id=user_id,
        session_id=session_id,
        validation_status=validation_status,
        page=page,
        page_size=page_size,
    )
    return Page[PunchEventOut](
        items=[
            PunchEventOut(
                id=e.id,
                user_id=e.user_id,
                session_id=e.session_id,
                type=e.type,
                server_timestamp=e.server_timestamp,
                client_timestamp=e.client_timestamp,
                latitude=float(e.latitude) if e.latitude is not None else None,
                longitude=float(e.longitude) if e.longitude is not None else None,
                accuracy_meters=(
                    float(e.accuracy_meters) if e.accuracy_meters is not None else None
                ),
                distance_meters=(
                    float(e.distance_meters) if e.distance_meters is not None else None
                ),
                radius_snapshot=e.radius_snapshot,
                accuracy_threshold_snapshot=e.accuracy_threshold_snapshot,
                validation_status=e.validation_status,
                rejection_reason=e.rejection_reason,
                ip_address=e.ip_address,
                location_purged=e.location_purged,
            )
            for e in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
