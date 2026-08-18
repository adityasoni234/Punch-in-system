"""Password hashing, JWT issuing/verification and token hashing.

Design notes
------------
* Passwords use argon2id (memory-hard) via argon2-cffi.
* Verifying an unknown email still performs a dummy hash so login timing does
  not reveal whether an account exists.
* Access tokens are short lived JWTs held in memory by the SPA. They embed
  `pwd_at` (password_changed_at) so that changing or resetting a password
  invalidates every previously issued access token.
* Refresh tokens are opaque random strings. Only their SHA-256 hash is stored,
  so a database leak cannot be replayed against the API.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import settings
from app.core.errors import TokenExpiredError, TokenInvalidError
from app.core.time import UTC, utcnow

_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)

# Pre-computed hash used to equalise timing when the account does not exist.
_DUMMY_HASH = _hasher.hash("dummy-password-for-constant-time-login")

ACCESS_TOKEN_TYPE = "access"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """Constant-ish time verification that tolerates a missing user."""
    target = password_hash or _DUMMY_HASH
    try:
        _hasher.verify(target, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    return password_hash is not None


def needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:  # pragma: no cover - corrupt hash
        return True


def generate_password(length: int = 14) -> str:
    """Temporary password for user creation / admin reset.

    Never a fixed or predictable value.
    """
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def create_access_token(
    *,
    user_id: uuid.UUID,
    role: str,
    password_changed_at: datetime | None,
) -> tuple[str, datetime]:
    now = utcnow()
    expires_at = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "typ": ACCESS_TOKEN_TYPE,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": secrets.token_urlsafe(12),
        "pwd_at": epoch(password_changed_at),
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)
    return token, expires_at


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub", "typ"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError() from exc
    except jwt.InvalidTokenError as exc:
        raise TokenInvalidError() from exc
    if payload.get("typ") != ACCESS_TOKEN_TYPE:
        raise TokenInvalidError()
    return payload


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def tokens_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)


def hash_user_agent(user_agent: str | None) -> str | None:
    """Store a salted digest rather than the raw UA string (data minimisation)."""
    if not user_agent:
        return None
    digest = hashlib.sha256((settings.secret_key + user_agent).encode("utf-8"))
    return digest.hexdigest()[:32]


def refresh_token_expiry() -> datetime:
    return utcnow() + timedelta(days=settings.refresh_token_expire_days)


def epoch(dt: datetime | None) -> int:
    """Milliseconds since the epoch.

    Millisecond resolution matters: a password reset immediately following
    account creation must produce a different `pwd_at`, otherwise tokens issued
    a fraction of a second earlier would survive the change.
    """
    if dt is None:
        return 0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return int(dt.timestamp() * 1000)
