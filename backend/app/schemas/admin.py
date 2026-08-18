from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import (
    AuditAction,
    AuditResult,
    DayStatus,
    PunchType,
    Role,
    UserStatus,
    ValidationStatus,
)
from app.schemas.attendance import DayOut
from app.schemas.auth import UserPublic


class UserCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    member_id: str = Field(min_length=1, max_length=40)
    role: Role = Role.USER
    password: str | None = Field(
        default=None,
        min_length=10,
        max_length=200,
        description="Optional. A strong random password is generated when omitted.",
    )


class UserUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    email: EmailStr | None = None
    member_id: str | None = Field(default=None, min_length=1, max_length=40)
    role: Role | None = None


class UserStatusRequest(BaseModel):
    status: UserStatus


class UserCreatedResponse(BaseModel):
    user: UserPublic
    temporary_password: str = Field(
        description="Shown exactly once. Not recoverable afterwards."
    )


class PresenceEntry(BaseModel):
    user_id: uuid.UUID
    name: str
    member_id: str
    email: str
    state: DayStatus
    punch_in: datetime | None = None
    last_punch_out: datetime | None = None
    elapsed_seconds: int = 0
    total_seconds: int = 0
    session_count: int = 0
    is_late: bool = False


class AdminDashboardResponse(BaseModel):
    date: date
    timezone: str
    server_time: datetime
    total_users: int
    present_count: int
    absent_count: int
    checked_out_count: int
    present: list[PresenceEntry]
    absent: list[PresenceEntry]
    checked_out: list[PresenceEntry]


class AdminUserAttendance(BaseModel):
    user: UserPublic
    from_date: date
    to_date: date
    timezone: str
    total_seconds: int
    days: list[DayOut]


class AdminAttendanceRow(BaseModel):
    user_id: uuid.UUID
    name: str
    member_id: str
    date: date
    status: DayStatus
    first_punch_in: datetime | None
    last_punch_out: datetime | None
    total_seconds: int
    session_count: int
    is_late: bool


class PunchEventOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    session_id: uuid.UUID | None
    type: PunchType
    server_timestamp: datetime
    client_timestamp: datetime | None
    latitude: float | None
    longitude: float | None
    accuracy_meters: float | None
    distance_meters: float | None
    radius_snapshot: int | None
    accuracy_threshold_snapshot: int | None
    validation_status: ValidationStatus
    rejection_reason: str | None
    ip_address: str | None
    location_purged: bool


class AuditLogOut(BaseModel):
    id: int
    actor_user_id: uuid.UUID | None
    actor_name: str | None = None
    target_user_id: uuid.UUID | None
    target_name: str | None = None
    action: AuditAction
    result: AuditResult
    timestamp: datetime
    ip_address: str | None
    request_id: str | None
    metadata: dict | None = None


class SessionEditRequest(BaseModel):
    """Administrative correction. Always audited; session is flagged MANUAL."""

    punch_in: datetime | None = None
    punch_out: datetime | None = None
    note: str = Field(min_length=3, max_length=500)
