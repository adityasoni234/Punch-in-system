from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.models.enums import Role, UserStatus
from app.schemas.common import ORMModel


class LoginRequest(BaseModel):
    """Sign in with either an enrollment number or an email address.

    Members are issued an enrollment number and use that; administrators use
    their email. One endpoint serves both so there is a single place where
    credentials are checked, audited and rate limited.
    """

    identifier: str = Field(default="", max_length=254)
    email: EmailStr | None = None  # accepted for backwards compatibility
    password: str = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def _require_identifier(self) -> "LoginRequest":
        if not self.identifier and self.email:
            self.identifier = str(self.email)
        self.identifier = self.identifier.strip()
        if not self.identifier:
            raise ValueError("Enter your enrollment number or email address")
        return self


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    member_id: str = Field(
        min_length=1, max_length=40, description="Enrollment number"
    )
    password: str = Field(min_length=10, max_length=200)


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
