from __future__ import annotations

import uuid
from datetime import time

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Index,
    Integer,
    Numeric,
    String,
    Time,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, uuid_pk


class Workspace(Base, TimestampMixin):
    """Runtime-configurable geofence + attendance policy.

    Nothing in this table is hardcoded in application logic: the geofence
    service reads the active row on every validation, so an administrator can
    move the workspace or widen the radius without a deployment.
    """

    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    latitude: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    longitude: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    radius_meters: Mapped[int] = mapped_column(Integer, nullable=False)
    accuracy_threshold_meters: Mapped[int] = mapped_column(Integer, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    attendance_start_time: Mapped[time] = mapped_column(Time, nullable=False)
    late_threshold_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    auto_close_after_hours: Mapped[int] = mapped_column(
        Integer, nullable=False, default=16
    )
    max_travel_speed_kmh: Mapped[int] = mapped_column(
        Integer, nullable=False, default=300
    )
    block_impossible_movement: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint("latitude >= -90 AND latitude <= 90", name="ck_workspace_lat"),
        CheckConstraint(
            "longitude >= -180 AND longitude <= 180", name="ck_workspace_lng"
        ),
        CheckConstraint(
            "radius_meters >= 10 AND radius_meters <= 5000", name="ck_workspace_radius"
        ),
        CheckConstraint(
            "accuracy_threshold_meters >= 5 AND accuracy_threshold_meters <= 1000",
            name="ck_workspace_accuracy",
        ),
        CheckConstraint(
            "auto_close_after_hours >= 1 AND auto_close_after_hours <= 72",
            name="ck_workspace_autoclose",
        ),
        CheckConstraint(
            "max_travel_speed_kmh >= 10 AND max_travel_speed_kmh <= 5000",
            name="ck_workspace_speed",
        ),
        # At most one active workspace at a time.
        Index(
            "uq_workspaces_single_active",
            "active",
            unique=True,
            postgresql_where=text("active"),
        ),
    )
