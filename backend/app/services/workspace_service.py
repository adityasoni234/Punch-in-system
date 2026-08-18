"""Workspace / geofence configuration."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import AppError, ErrorCode
from app.models.enums import AuditAction
from app.models.user import User
from app.models.workspace import Workspace
from app.repositories import workspace_repo
from app.schemas.workspace import WorkspaceUpdateRequest
from app.services import audit_service

_CONFIGURABLE = (
    "name",
    "latitude",
    "longitude",
    "radius_meters",
    "accuracy_threshold_meters",
    "timezone",
    "attendance_start_time",
    "late_threshold_minutes",
    "auto_close_after_hours",
    "max_travel_speed_kmh",
    "block_impossible_movement",
)


def get_active(db: Session) -> Workspace:
    workspace = workspace_repo.get_active(db)
    if workspace is None:
        raise AppError(
            "No active workspace is configured. An administrator must configure "
            "the workspace before attendance can be recorded.",
            code=ErrorCode.WORKSPACE_NOT_CONFIGURED,
            status_code=503,
        )
    return workspace


def update(db: Session, *, actor: User, payload: WorkspaceUpdateRequest) -> Workspace:
    workspace = workspace_repo.get_active_for_update(db)
    if workspace is None:
        raise AppError(
            "No active workspace is configured.",
            code=ErrorCode.WORKSPACE_NOT_CONFIGURED,
            status_code=503,
        )

    changes: dict[str, dict[str, Any]] = {}
    data = payload.model_dump(exclude_unset=True)
    for field in _CONFIGURABLE:
        if field not in data or data[field] is None:
            continue
        old = getattr(workspace, field)
        new = data[field]
        if str(old) != str(new):
            setattr(workspace, field, new)
            changes[field] = {"from": str(old), "to": str(new)}

    if changes:
        audit_service.success(
            db,
            AuditAction.WORKSPACE_UPDATED,
            actor_user_id=actor.id,
            metadata={"changes": changes, "workspace_id": str(workspace.id)},
        )
    db.commit()
    db.refresh(workspace)
    return workspace


def configuration_warnings(workspace: Workspace) -> list[str]:
    """Non-blocking sanity checks surfaced in the admin settings screen."""
    warnings: list[str] = []
    if workspace.accuracy_threshold_meters > workspace.radius_meters / 2:
        warnings.append(
            "The GPS accuracy threshold is more than half the geofence radius. "
            "A reading accepted at this accuracy could be outside the fence in "
            "reality. Consider lowering the threshold or widening the radius."
        )
    if workspace.radius_meters < 50:
        warnings.append(
            "Radii below 50 m are difficult to satisfy indoors, where consumer "
            "GPS accuracy is typically 20-100 m."
        )
    return warnings
