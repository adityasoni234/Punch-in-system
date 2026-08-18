from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RateLimitBucket(Base):
    """Fixed-window counter, stored in PostgreSQL.

    Kept in the database rather than in process memory so the limit holds
    across multiple uvicorn workers, and rather than in Redis so the stack
    stays a modular monolith with one datastore.
    """

    __tablename__ = "rate_limit_buckets"

    key: Mapped[str] = mapped_column(String(160), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True
    )
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (Index("ix_rate_limit_expiry", "expires_at"),)
