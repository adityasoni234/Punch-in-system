from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query

from app.core.deps import (
    ActiveWorkspace,
    CurrentUser,
    DbSession,
    IdempotencyKey,
    punch_rate_limit,
)
from app.core.errors import AppError, ErrorCode
from app.core.time import utcnow
from app.schemas.attendance import (
    DayOut,
    HistoryResponse,
    PunchRequest,
    PunchResponse,
    SessionOut,
    SummaryResponse,
    TodayResponse,
    VerificationInfo,
)
from app.services import analytics_service, attendance_service

router = APIRouter(prefix="/attendance", tags=["attendance"])


def _session_out(session) -> SessionOut:
    data = SessionOut.model_validate(session)
    data.is_active = session.punch_out is None
    return data


@router.get("/today", response_model=TodayResponse, summary="Today's attendance state")
def today(user: CurrentUser, db: DbSession, workspace: ActiveWorkspace) -> TodayResponse:
    state = attendance_service.today_state(db, user, workspace)
    return TodayResponse(
        status=state["state"],
        date=state["date"],
        timezone=state["timezone"],
        server_time=state["server_time"],
        total_seconds=state["total_seconds"],
        active_session=(
            _session_out(state["active_session"]) if state["active_session"] else None
        ),
        active_elapsed_seconds=state["active_elapsed_seconds"],
        sessions=[_session_out(s) for s in state["sessions"]],
    )


def _punch_response(outcome: attendance_service.PunchOutcome) -> PunchResponse:
    return PunchResponse(
        status=outcome.state,
        session_id=outcome.session.id,
        punch_in=outcome.session.punch_in,
        punch_out=outcome.session.punch_out,
        duration_seconds=outcome.session.duration_seconds,
        today_total_seconds=outcome.today_total_seconds,
        server_time=outcome.server_time,
        message=outcome.message,
        verification=VerificationInfo(
            distance_meters=round(outcome.distance_meters, 1),
            accuracy_meters=round(outcome.accuracy_meters, 1),
            radius_meters=outcome.radius_meters,
        ),
    )


@router.post(
    "/punch-in",
    response_model=PunchResponse,
    dependencies=[Depends(punch_rate_limit)],
    summary="Punch in (requires a verified location inside the geofence)",
)
def punch_in(
    payload: PunchRequest,
    user: CurrentUser,
    db: DbSession,
    idempotency_key: IdempotencyKey,
) -> PunchResponse:
    outcome = attendance_service.punch_in(
        db, user=user, payload=payload, idempotency_key=idempotency_key
    )
    return _punch_response(outcome)


@router.post(
    "/punch-out",
    response_model=PunchResponse,
    dependencies=[Depends(punch_rate_limit)],
    summary="Punch out (requires a verified location inside the geofence)",
)
def punch_out(
    payload: PunchRequest,
    user: CurrentUser,
    db: DbSession,
    idempotency_key: IdempotencyKey,
) -> PunchResponse:
    outcome = attendance_service.punch_out(
        db, user=user, payload=payload, idempotency_key=idempotency_key
    )
    return _punch_response(outcome)


def _resolve_range(
    workspace, period: str, from_date: date | None, to_date: date | None
) -> tuple[date, date]:
    try:
        return analytics_service.resolve_period(
            period, workspace, custom_from=from_date, custom_to=to_date
        )
    except ValueError as exc:
        raise AppError(str(exc), code=ErrorCode.VALIDATION_ERROR) from exc


@router.get("/history", response_model=HistoryResponse, summary="Attendance history")
def history(
    user: CurrentUser,
    db: DbSession,
    workspace: ActiveWorkspace,
    period: str = Query("month", pattern="^(today|week|month|custom)$"),
    from_date: date | None = None,
    to_date: date | None = None,
) -> HistoryResponse:
    start, end = _resolve_range(workspace, period, from_date, to_date)
    data = attendance_service.history(db, user, workspace, start, end)
    return HistoryResponse(
        from_date=data["from_date"],
        to_date=data["to_date"],
        timezone=data["timezone"],
        server_time=data["server_time"],
        total_seconds=data["total_seconds"],
        days=[
            DayOut(**{**d, "sessions": [_session_out(s) for s in d["sessions"]]})
            for d in data["days"]
        ],
    )


@router.get("/summary", response_model=SummaryResponse, summary="Attendance analytics")
def summary(
    user: CurrentUser,
    db: DbSession,
    workspace: ActiveWorkspace,
    period: str = Query("week", pattern="^(today|week|month|custom)$"),
    from_date: date | None = None,
    to_date: date | None = None,
) -> SummaryResponse:
    start, end = _resolve_range(workspace, period, from_date, to_date)
    data = analytics_service.summary(
        db, user, workspace, start, end, period_label=period, now=utcnow()
    )
    return SummaryResponse(**data)
