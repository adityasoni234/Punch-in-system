from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, uuid_pk
from app.models.enums import PunchType, ValidationStatus


def _enum(py_enum: type, name: str) -> Enum:
    return Enum(
        py_enum,
        name=name,
        native_enum=True,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
    )


class PunchEvent(Base):
    """Append-only forensic record of every punch ATTEMPT, accepted or not.

    The radius and accuracy threshold in force at the time are snapshotted so
    that later changes to the workspace configuration never silently rewrite
    the meaning of historical events.

    Coordinates are the only precise location data the system stores and they
    are purged by the retention job after `LOCATION_RETENTION_DAYS`; the
    attendance record itself is retained.
    """

    __tablename__ = "punch_events"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("attendance_sessions.id", ondelete="SET NULL"), nullable=True
    )
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True
    )
    type: Mapped[PunchType] = mapped_column(_enum(PunchType, "punch_type_enum"), nullable=False)

    # Server clock. The authoritative timestamp for all attendance maths.
    server_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Device clock. Stored for forensics only; never used in a calculation.
    client_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    latitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    accuracy_meters: Mapped[float | None] = mapped_column(Numeric(9, 2), nullable=True)
    distance_meters: Mapped[float | None] = mapped_column(Numeric(11, 2), nullable=True)

    radius_snapshot: Mapped[int | None] = mapped_column(Integer, nullable=True)
    accuracy_threshold_snapshot: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    validation_status: Mapped[ValidationStatus] = mapped_column(
        _enum(ValidationStatus, "validation_enum"), nullable=False
    )
    rejection_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)

    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    location_purged: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default="false"
    )

    __table_args__ = (
        # Replay / double-tap protection, scoped per user.
        UniqueConstraint(
            "user_id", "idempotency_key", name="uq_punch_events_user_idempotency"
        ),
        Index("ix_punch_events_user_time", "user_id", "server_timestamp"),
        Index("ix_punch_events_validation", "validation_status"),
        Index("ix_punch_events_session", "session_id"),
    )
