from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status

from app.core.deps import AdminUser, DbSession
from app.models.enums import Role, UserStatus
from app.schemas.admin import (
    UserCreateRequest,
    UserCreatedResponse,
    UserStatusRequest,
    UserUpdateRequest,
)
from app.schemas.auth import UserPublic
from app.schemas.common import Page
from app.services import user_service

router = APIRouter(prefix="/admin/users", tags=["admin:users"])


@router.get("", response_model=Page[UserPublic], summary="List users")
def list_users(
    admin: AdminUser,
    db: DbSession,
    search: str | None = None,
    role: Role | None = None,
    user_status: UserStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> Page[UserPublic]:
    from app.repositories import user_repo

    rows, total = user_repo.list_users(
        db,
        search=search,
        role=role,
        status=user_status,
        page=page,
        page_size=page_size,
    )
    return Page[UserPublic](
        items=[UserPublic.model_validate(u) for u in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "",
    response_model=UserCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a user",
)
def create_user(
    payload: UserCreateRequest, admin: AdminUser, db: DbSession
) -> UserCreatedResponse:
    user, temporary_password = user_service.create(db, actor=admin, payload=payload)
    return UserCreatedResponse(
        user=UserPublic.model_validate(user), temporary_password=temporary_password
    )


@router.get("/{user_id}", response_model=UserPublic, summary="Get a user")
def get_user(user_id: uuid.UUID, admin: AdminUser, db: DbSession) -> UserPublic:
    return UserPublic.model_validate(user_service.get(db, user_id))


@router.patch("/{user_id}", response_model=UserPublic, summary="Update a user")
def update_user(
    user_id: uuid.UUID, payload: UserUpdateRequest, admin: AdminUser, db: DbSession
) -> UserPublic:
    user = user_service.update(db, actor=admin, user_id=user_id, payload=payload)
    return UserPublic.model_validate(user)


@router.patch(
    "/{user_id}/status", response_model=UserPublic, summary="Enable or disable a user"
)
def set_status(
    user_id: uuid.UUID, payload: UserStatusRequest, admin: AdminUser, db: DbSession
) -> UserPublic:
    user = user_service.set_status(
        db, actor=admin, user_id=user_id, status=payload.status
    )
    return UserPublic.model_validate(user)


@router.post(
    "/{user_id}/reset-password",
    response_model=UserCreatedResponse,
    summary="Issue a new temporary password",
)
def reset_password(
    user_id: uuid.UUID, admin: AdminUser, db: DbSession
) -> UserCreatedResponse:
    user, temporary_password = user_service.reset_password(
        db, actor=admin, user_id=user_id
    )
    return UserCreatedResponse(
        user=UserPublic.model_validate(user), temporary_password=temporary_password
    )
