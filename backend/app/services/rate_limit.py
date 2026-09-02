"""Fixed-window rate limiting backed by PostgreSQL.

Stored in the database rather than process memory so the limit is shared by
every uvicorn worker, and rather than Redis so the deployment keeps a single
datastore. Each check is one upsert; the window row expires on its own and is
swept by the retention job.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import RateLimitedError
from app.core.time import UTC, utcnow
from app.models.rate_limit import RateLimitBucket


@dataclass(slots=True)
class LimitPolicy:
    name: str
    max_requests: int
    window_seconds: int


def login_policy() -> LimitPolicy:
    """Per-account limit: strict, because this is what stops brute force."""
    return LimitPolicy(
        "login", settings.rate_limit_login_max, settings.rate_limit_login_window_seconds
    )


def login_ip_policy() -> LimitPolicy:
    """Per-network limit: generous, because shared NAT is normal."""
    return LimitPolicy(
        "login_ip",
        settings.rate_limit_login_ip_max,
        settings.rate_limit_login_window_seconds,
    )


def register_policy() -> LimitPolicy:
    return LimitPolicy(
        "register",
        settings.rate_limit_register_max,
        settings.rate_limit_register_window_seconds,
    )


def punch_policy() -> LimitPolicy:
    return LimitPolicy(
        "punch", settings.rate_limit_punch_max, settings.rate_limit_punch_window_seconds
    )


def global_policy() -> LimitPolicy:
    return LimitPolicy(
        "global",
        settings.rate_limit_global_max,
        settings.rate_limit_global_window_seconds,
    )


def _window_start(now: datetime, window_seconds: int) -> datetime:
    epoch_seconds = int(now.timestamp())
    return datetime.fromtimestamp(
        epoch_seconds - (epoch_seconds % window_seconds), tz=UTC
    )


def _key(policy: LimitPolicy, identifier: str) -> str:
    digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()[:48]
    return f"{policy.name}:{digest}"


def hit(db: Session, policy: LimitPolicy, identifier: str) -> tuple[int, int]:
    """Register one request. Returns (count_in_window, seconds_until_reset)."""
    now = utcnow()
    window_start = _window_start(now, policy.window_seconds)
    expires_at = window_start + timedelta(seconds=policy.window_seconds)
    key = _key(policy, identifier)

    stmt = (
        pg_insert(RateLimitBucket)
        .values(key=key, window_start=window_start, count=1, expires_at=expires_at)
        .on_conflict_do_update(
            index_elements=["key", "window_start"],
            set_={"count": RateLimitBucket.count + 1},
        )
        .returning(RateLimitBucket.count)
    )
    count = db.execute(stmt).scalar_one()
    retry_after = max(1, int((expires_at - now).total_seconds()))
    return int(count), retry_after


def enforce(db: Session, policy: LimitPolicy, identifier: str) -> None:
    """Raise 429 when the caller has exceeded the policy."""
    count, retry_after = hit(db, policy, identifier)
    if count > policy.max_requests:
        raise RateLimitedError(
            retry_after,
            "Too many attempts. Please wait "
            f"{retry_after} second{'s' if retry_after != 1 else ''} and try again.",
        )


def assert_within(db: Session, policy: LimitPolicy, identifier: str) -> None:
    """Reject if the window is already exhausted, WITHOUT consuming budget.

    Pair with `record_failure` so only failed attempts count. Charging a
    successful sign-in against the limit is what locks people out of an
    account they can actually log into.
    """
    now = utcnow()
    window_start = _window_start(now, policy.window_seconds)
    count = (
        db.scalar(
            select(RateLimitBucket.count).where(
                RateLimitBucket.key == _key(policy, identifier),
                RateLimitBucket.window_start == window_start,
            )
        )
        or 0
    )
    if count >= policy.max_requests:
        expires_at = window_start + timedelta(seconds=policy.window_seconds)
        retry_after = max(1, int((expires_at - now).total_seconds()))
        raise RateLimitedError(
            retry_after,
            "Too many failed attempts for this account. Please wait "
            f"{retry_after} second{'s' if retry_after != 1 else ''} and try again.",
        )


def record_failure(db: Session, policy: LimitPolicy, identifier: str) -> None:
    hit(db, policy, identifier)


def clear(db: Session, policy: LimitPolicy, identifier: str) -> None:
    """Wipe the window after a success, so a wrong guess then a correct one
    does not leave the account part-way to a lockout."""
    db.execute(
        delete(RateLimitBucket).where(RateLimitBucket.key == _key(policy, identifier))
    )


def peek(db: Session, policy: LimitPolicy, identifier: str) -> int:
    now = utcnow()
    window_start = _window_start(now, policy.window_seconds)
    return (
        db.scalar(
            select(RateLimitBucket.count).where(
                RateLimitBucket.key == _key(policy, identifier),
                RateLimitBucket.window_start == window_start,
            )
        )
        or 0
    )


def purge_expired(db: Session) -> int:
    result = db.execute(
        delete(RateLimitBucket).where(RateLimitBucket.expires_at < utcnow())
    )
    return result.rowcount or 0
