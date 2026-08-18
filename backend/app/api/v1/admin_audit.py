from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Query

from app.core.deps import ActiveWorkspace, AdminUser, DbSession
from app.core.time import range_bounds_utc
from app.models.enums import AuditAction, AuditResult
from app.schemas.admin import AuditLogOut
from app.schemas.common import Page
from app.repositories import audit_repo

router = APIRouter(prefix="/admin/audit-logs", tags=["admin:audit"])


@router.get("", response_model=Page[AuditLogOut], summary="Security & attendance audit trail")
def list_audit_logs(
    admin: AdminUser,
    db: DbSession,
    workspace: ActiveWorkspace,
    action: AuditAction | None = None,
    result: AuditResult | None = None,
    user_id: uuid.UUID | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> Page[AuditLogOut]:
    start = end = None
    if from_date and to_date:
        start, end = range_bounds_utc(from_date, to_date, workspace.timezone)

    rows, total = audit_repo.list_logs(
        db,
        action=action,
        result=result,
        user_id=user_id,
        start=start,
        end=end,
        page=page,
        page_size=page_size,
    )
    return Page[AuditLogOut](
        items=[
            AuditLogOut(
                id=log.id,
                actor_user_id=log.actor_user_id,
                actor_name=actor_name,
                target_user_id=log.target_user_id,
                target_name=target_name,
                action=log.action,
                result=log.result,
                timestamp=log.timestamp,
                ip_address=log.ip_address,
                request_id=log.request_id,
                metadata=log.audit_metadata,
            )
            for log, actor_name, target_name in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
