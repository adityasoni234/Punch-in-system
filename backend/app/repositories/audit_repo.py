from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, aliased

from app.models.audit_log import AuditLog
from app.models.enums import AuditAction, AuditResult
from app.models.user import User


def add(
    db: Session,
    *,
    action: AuditAction,
    result: AuditResult,
    actor_user_id: uuid.UUID | None = None,
    target_user_id: uuid.UUID | None = None,
    ip_address: str | None = None,
    user_agent_hash: str | None = None,
    request_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        action=action,
        result=result,
        actor_user_id=actor_user_id,
        target_user_id=target_user_id,
        ip_address=ip_address,
        user_agent_hash=user_agent_hash,
        request_id=request_id,
        audit_metadata=metadata,
    )
    db.add(entry)
    return entry


def _query(
    action: AuditAction | None,
    result: AuditResult | None,
    user_id: uuid.UUID | None,
    start: datetime | None,
    end: datetime | None,
) -> Select:
    actor = aliased(User)
    target = aliased(User)
    stmt = (
        select(AuditLog, actor.name, target.name)
        .outerjoin(actor, AuditLog.actor_user_id == actor.id)
        .outerjoin(target, AuditLog.target_user_id == target.id)
    )
    if action is not None:
        stmt = stmt.where(AuditLog.action == action)
    if result is not None:
        stmt = stmt.where(AuditLog.result == result)
    if user_id is not None:
        stmt = stmt.where(
            (AuditLog.actor_user_id == user_id) | (AuditLog.target_user_id == user_id)
        )
    if start is not None:
        stmt = stmt.where(AuditLog.timestamp >= start)
    if end is not None:
        stmt = stmt.where(AuditLog.timestamp < end)
    return stmt


def list_logs(
    db: Session,
    *,
    action: AuditAction | None = None,
    result: AuditResult | None = None,
    user_id: uuid.UUID | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[tuple[AuditLog, str | None, str | None]], int]:
    stmt = _query(action, result, user_id, start, end)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(
        stmt.order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return [(r[0], r[1], r[2]) for r in rows], total
