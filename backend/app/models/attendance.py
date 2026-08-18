from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk
from app.models.enums import DayStatus, SessionStatus


def _enum(py_enum: type, name: str) -> Enum:
    return Enum(
        py_enum,
        name=name,
        native_enum=True,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
    )


class AttendanceDay(Base, TimestampMixin):
    """One row per user per workspace-local calendar day.

    `total_seconds` covers CLOSED sessions only. Any currently running session
    is added on read, from server time, so the number can never drift.
    """

    __tablename__ = "attendance_days"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[DayStatus] = mapped_column(
        _enum(DayStatus, "day_status_enum"), nullable=False, default=DayStatus.ABSENT
    )
    total_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_punch_in: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_punch_out: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_late: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    user = relationship("User", back_populates="attendance_days")
    sessions = relationship(
        "AttendanceSession",
        back_populates="day",
        order_by="AttendanceSession.punch_in",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "work_date", name="uq_attendance_day_user_date"),
        Index("ix_attendance_days_date", "work_date"),
        Index("ix_attendance_days_user_date", "user_id", "work_date"),
        CheckConstraint("total_seconds >= 0", name="ck_attendance_day_total"),
    )


class AttendanceSession(Base, TimestampMixin):
    """A single punch-in/punch-out pair. Multiple per day are expected.

    The partial unique index `uq_one_open_session_per_user` is the core
    concurrency guarantee: PostgreSQL itself makes it impossible for a user to
    hold two open sessions, so racing punch-in requests cannot both succeed.
    """

    __tablename__ = "attendance_sessions"

    id: Mapped[uuid.UUID] = uuid_pk()
    attendance_day_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attendance_days.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False
    )
    punch_in: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    punch_out: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[SessionStatus] = mapped_column(
        _enum(SessionStatus, "session_status_enum"),
        nullable=False,
        default=SessionStatus.ACTIVE,
    )
    note: Mapped[str | None] = mapped_column(nullable=True)

    day = relationship("AttendanceDay", back_populates="sessions")

    __table_args__ = (
        # Exactly one open session per user, enforced by the database.
        Index(
            "uq_one_open_session_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("punch_out IS NULL"),
        ),
        Index("ix_sessions_user_punch_in", "user_id", "punch_in"),
        Index("ix_sessions_day", "attendance_day_id"),
        Index(
            "ix_sessions_open",
            "user_id",
            postgresql_where=text("punch_out IS NULL"),
        ),
        CheckConstraint(
            "punch_out IS NULL OR punch_out > punch_in", name="ck_session_order"
        ),
        CheckConstraint(
            "(punch_out IS NULL) = (duration_seconds IS NULL)",
            name="ck_session_duration_pairing",
        ),
        CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="ck_session_duration_positive",
        ),
    )

    @property
    def is_active(self) -> bool:
        return self.punch_out is None
