"""Audit trail writer.

Records who did what, when, from where and with what result. Location detail
is limited to what is needed to explain an attendance decision (distance and
accuracy), never a movement history.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.middleware.request_context import (
    current_client_ip,
    current_request_id,
    current_user_agent_hash,
)
from app.models.enums import AuditAction, AuditResult
from app.repositories import audit_repo


def record(
    db: Session,
    action: AuditAction,
    result: AuditResult = AuditResult.SUCCESS,
    *,
    actor_user_id: uuid.UUID | None = None,
    target_user_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    audit_repo.add(
        db,
        action=action,
        result=result,
        actor_user_id=actor_user_id,
        target_user_id=target_user_id,
        ip_address=current_client_ip(),
        user_agent_hash=current_user_agent_hash(),
        request_id=current_request_id(),
        metadata=metadata,
    )


def success(
    db: Session,
    action: AuditAction,
    **kwargs: Any,
) -> None:
    record(db, action, AuditResult.SUCCESS, **kwargs)


def failure(
    db: Session,
    action: AuditAction,
    **kwargs: Any,
) -> None:
    record(db, action, AuditResult.FAILURE, **kwargs)
