from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import Role, UserStatus
from app.schemas.common import ORMModel


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class UserPublic(ORMModel):
    id: uuid.UUID
    name: str
    email: str
    member_id: str
    role: Role
    status: UserStatus
    must_change_password: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None = None


class WorkspacePublic(BaseModel):
    """Only what a normal user's client legitimately needs.

    Coordinates are intentionally excluded: the client never decides whether a
    punch is inside the fence, so it has no reason to know where the fence is.
    """

    name: str
    radius_meters: int
    accuracy_threshold_meters: int
    timezone: str


class SessionInfo(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserPublic
    workspace: WorkspacePublic | None = None
    server_time: datetime


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=10, max_length=200)
