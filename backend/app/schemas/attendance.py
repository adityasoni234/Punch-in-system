from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import DayStatus, SessionStatus
from app.schemas.common import ORMModel


class PunchRequest(BaseModel):
    """Everything the client is allowed to assert about a punch.

    Note what is absent: distance, inside/outside, duration, user id, state.
    All of those are derived by the server. `captured_at` is the device clock
    and is stored for forensics only.
    """

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy: float = Field(gt=0, le=100000, description="GPS accuracy in metres")
    captured_at: datetime | None = None

    @field_validator("latitude", "longitude", "accuracy")
    @classmethod
    def _finite(cls, v: float) -> float:
        if v != v or v in (float("inf"), float("-inf")):
            raise ValueError("must be a finite number")
        return v


class VerificationInfo(BaseModel):
    distance_meters: float
    accuracy_meters: float
    radius_meters: int


class SessionOut(ORMModel):
    id: uuid.UUID
    punch_in: datetime
    punch_out: datetime | None
    duration_seconds: int | None
    status: SessionStatus
    is_active: bool = False
    note: str | None = None


class DayOut(BaseModel):
    date: date
    status: DayStatus
    total_seconds: int
    first_punch_in: datetime | None
    last_punch_out: datetime | None
    is_late: bool
    session_count: int
    sessions: list[SessionOut] = Field(default_factory=list)


class TodayResponse(BaseModel):
    status: DayStatus
    date: date
    timezone: str
    server_time: datetime
    total_seconds: int
    active_session: SessionOut | None = None
    active_elapsed_seconds: int = 0
    sessions: list[SessionOut] = Field(default_factory=list)


class PunchResponse(BaseModel):
    success: bool = True
    status: DayStatus
    session_id: uuid.UUID
    punch_in: datetime
    punch_out: datetime | None = None
    duration_seconds: int | None = None
    today_total_seconds: int
    server_time: datetime
    message: str
    verification: VerificationInfo


class HistoryResponse(BaseModel):
    from_date: date
    to_date: date
    timezone: str
    server_time: datetime
    total_seconds: int
    days: list[DayOut]


class SummaryResponse(BaseModel):
    period: str
    from_date: date
    to_date: date
    timezone: str
    days_present: int
    days_absent: int
    working_days: int
    total_seconds: int
    average_seconds_per_present_day: int
    longest_session_seconds: int
    late_arrivals: int
    average_arrival_minutes: int | None = None
    average_departure_minutes: int | None = None
