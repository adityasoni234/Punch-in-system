from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.core.deps import ActiveWorkspace, AdminUser, DbSession
from app.core.errors import AppError, ErrorCode
from app.models.enums import AuditAction
from app.services import audit_service, report_service

router = APIRouter(prefix="/admin/reports", tags=["admin:reports"])


@router.get(
    "/attendance.csv",
    summary="Export attendance as CSV",
    response_class=StreamingResponse,
)
def export_attendance_csv(
    admin: AdminUser,
    db: DbSession,
    workspace: ActiveWorkspace,
    from_date: date = Query(...),
    to_date: date = Query(...),
    user_id: uuid.UUID | None = None,
) -> StreamingResponse:
    if to_date < from_date:
        raise AppError(
            "to_date must not be before from_date", code=ErrorCode.VALIDATION_ERROR
        )
    if (to_date - from_date).days > 366:
        raise AppError(
            "Export range is limited to 366 days.", code=ErrorCode.VALIDATION_ERROR
        )

    audit_service.success(
        db,
        AuditAction.REPORT_EXPORTED,
        actor_user_id=admin.id,
        metadata={
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
            "user_id": str(user_id) if user_id else "ALL",
            "format": "csv",
        },
    )
    db.commit()

    stream = report_service.stream_csv(
        db, workspace, from_date, to_date, [user_id] if user_id else None
    )
    return StreamingResponse(
        stream,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{report_service.filename(from_date, to_date)}"'
            )
        },
    )
