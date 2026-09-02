from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, Uuid
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk
from app.models.enums import Role, Team, UserStatus


def _enum(py_enum: type, name: str) -> Enum:
    return Enum(
        py_enum,
        name=name,
        native_enum=True,
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(CITEXT(), nullable=False, unique=True)
    member_id: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(
        _enum(Role, "role_enum"), nullable=False, default=Role.USER
    )
    status: Mapped[UserStatus] = mapped_column(
        _enum(UserStatus, "user_status_enum"), nullable=False, default=UserStatus.ACTIVE
    )
    team: Mapped[Team] = mapped_column(
        _enum(Team, "team_enum"), nullable=False, default=Team.MEMBER,
        server_default=Team.MEMBER.value,
    )
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    attendance_days = relationship("AttendanceDay", back_populates="user")

    __table_args__ = (
        Index("ix_users_status_role", "status", "role"),
        Index("ix_users_team", "team"),
    )

    @property
    def is_admin(self) -> bool:
        return self.role == Role.ADMIN

    @property
    def is_active(self) -> bool:
        return self.status == UserStatus.ACTIVE

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.email} {self.role}>"


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    family_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    user_agent_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        Index("ix_refresh_tokens_user_revoked", "user_id", "revoked_at"),
        Index("ix_refresh_tokens_family", "family_id"),
    )
