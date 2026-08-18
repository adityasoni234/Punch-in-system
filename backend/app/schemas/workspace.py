from __future__ import annotations

import uuid
from datetime import datetime, time

from pydantic import BaseModel, Field, field_validator

from app.core.time import is_valid_timezone
from app.schemas.common import ORMModel


class WorkspaceOut(ORMModel):
    id: uuid.UUID
    name: str
    latitude: float
    longitude: float
    radius_meters: int
    accuracy_threshold_meters: int
    timezone: str
    attendance_start_time: time
    late_threshold_minutes: int
    auto_close_after_hours: int
    max_travel_speed_kmh: int
    block_impossible_movement: bool
    active: bool
    created_at: datetime
    updated_at: datetime


class WorkspaceUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    radius_meters: int | None = Field(default=None, ge=10, le=5000)
    accuracy_threshold_meters: int | None = Field(default=None, ge=5, le=1000)
    timezone: str | None = None
    attendance_start_time: time | None = None
    late_threshold_minutes: int | None = Field(default=None, ge=0, le=480)
    auto_close_after_hours: int | None = Field(default=None, ge=1, le=72)
    max_travel_speed_kmh: int | None = Field(default=None, ge=10, le=5000)
    block_impossible_movement: bool | None = None

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, v: str | None) -> str | None:
        if v is not None and not is_valid_timezone(v):
            raise ValueError("Unknown IANA timezone name")
        return v
