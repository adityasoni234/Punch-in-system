from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import AdminUser, DbSession
from app.schemas.workspace import WorkspaceOut, WorkspaceUpdateRequest
from app.services import workspace_service

router = APIRouter(prefix="/admin/workspace", tags=["admin:workspace"])


class WorkspaceEnvelope(WorkspaceOut):
    warnings: list[str] = []


@router.get("", response_model=WorkspaceEnvelope, summary="Get workspace configuration")
def get_workspace(admin: AdminUser, db: DbSession) -> WorkspaceEnvelope:
    workspace = workspace_service.get_active(db)
    return WorkspaceEnvelope(
        **WorkspaceOut.model_validate(workspace).model_dump(),
        warnings=workspace_service.configuration_warnings(workspace),
    )


@router.patch(
    "", response_model=WorkspaceEnvelope, summary="Update workspace configuration"
)
def update_workspace(
    payload: WorkspaceUpdateRequest, admin: AdminUser, db: DbSession
) -> WorkspaceEnvelope:
    workspace = workspace_service.update(db, actor=admin, payload=payload)
    return WorkspaceEnvelope(
        **WorkspaceOut.model_validate(workspace).model_dump(),
        warnings=workspace_service.configuration_warnings(workspace),
    )
