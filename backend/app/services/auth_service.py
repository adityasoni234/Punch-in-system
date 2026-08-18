"""Authentication: login, refresh rotation, logout, password change."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.errors import (
    InvalidCredentialsError,
    TokenExpiredError,
    TokenInvalidError,
    UserDisabledError,
)
from app.core.security import (
    create_access_token,
    epoch,
    generate_refresh_token,
    hash_password,
    hash_token,
    hash_user_agent,
    needs_rehash,
    refresh_token_expiry,
    verify_password,
)
from app.core.time import utcnow
from app.models.enums import AuditAction, AuditResult, UserStatus
from app.models.user import User
from app.repositories import token_repo, user_repo
from app.services import audit_service


@dataclass(slots=True)
class IssuedSession:
    user: User
    access_token: str
    access_expires_at: datetime
    refresh_token: str
    refresh_expires_at: datetime


def _issue(
    db: Session,
    user: User,
    *,
    family_id: uuid.UUID | None = None,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> IssuedSession:
    access_token, access_expires = create_access_token(
        user_id=user.id, role=user.role.value, password_changed_at=user.password_changed_at
    )
    raw_refresh = generate_refresh_token()
    expires_at = refresh_token_expiry()
    token_repo.create(
        db,
        user_id=user.id,
        token_hash=hash_token(raw_refresh),
        family_id=family_id or uuid.uuid4(),
        expires_at=expires_at,
        user_agent_hash=hash_user_agent(user_agent),
        ip_address=ip_address,
    )
    return IssuedSession(
        user=user,
        access_token=access_token,
        access_expires_at=access_expires,
        refresh_token=raw_refresh,
        refresh_expires_at=expires_at,
    )


def login(
    db: Session,
    *,
    email: str,
    password: str,
    user_agent: str | None,
    ip_address: str | None,
) -> IssuedSession:
    user = user_repo.get_by_email(db, email)

    # verify_password hashes a dummy value when the user is missing so that a
    # non-existent account is indistinguishable from a wrong password by timing.
    if not verify_password(password, user.password_hash if user else None):
        audit_service.record(
            db,
            AuditAction.LOGIN_FAILED,
            AuditResult.FAILURE,
            actor_user_id=user.id if user else None,
            metadata={"email": email, "reason": "INVALID_CREDENTIALS"},
        )
        db.commit()
        raise InvalidCredentialsError()

    assert user is not None
    if user.status != UserStatus.ACTIVE:
        audit_service.record(
            db,
            AuditAction.LOGIN_FAILED,
            AuditResult.FAILURE,
            actor_user_id=user.id,
            metadata={"reason": "USER_DISABLED"},
        )
        db.commit()
        raise UserDisabledError()

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)

    user.last_login_at = utcnow()
    issued = _issue(db, user, user_agent=user_agent, ip_address=ip_address)
    audit_service.success(db, AuditAction.LOGIN_SUCCESS, actor_user_id=user.id)
    db.commit()
    return issued


def refresh(
    db: Session,
    *,
    raw_refresh_token: str,
    user_agent: str | None,
    ip_address: str | None,
) -> IssuedSession:
    """Rotate a refresh token.

    A token that has already been rotated away is treated as theft: the whole
    family is revoked so both the attacker and the victim are logged out.
    """
    stored = token_repo.get_by_hash(db, hash_token(raw_refresh_token))
    if stored is None:
        raise TokenInvalidError("Invalid session. Please sign in again.")

    if stored.revoked_at is not None:
        token_repo.revoke_family(db, stored.family_id)
        audit_service.failure(
            db,
            AuditAction.TOKEN_REFRESH_REUSE,
            actor_user_id=stored.user_id,
            metadata={"family_id": str(stored.family_id)},
        )
        db.commit()
        raise TokenInvalidError(
            "Your session was ended for security reasons. Please sign in again."
        )

    if stored.expires_at <= utcnow():
        token_repo.revoke(db, stored)
        db.commit()
        raise TokenExpiredError()

    user = user_repo.get_by_id(db, stored.user_id)
    if user is None:
        token_repo.revoke_family(db, stored.family_id)
        db.commit()
        raise TokenInvalidError()
    if user.status != UserStatus.ACTIVE:
        token_repo.revoke_all_for_user(db, user.id)
        db.commit()
        raise UserDisabledError()

    token_repo.revoke(db, stored)
    issued = _issue(
        db,
        user,
        family_id=stored.family_id,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    db.commit()
    return issued


def logout(db: Session, *, raw_refresh_token: str | None, user: User | None) -> None:
    if raw_refresh_token:
        stored = token_repo.get_by_hash(db, hash_token(raw_refresh_token))
        if stored is not None and stored.revoked_at is None:
            token_repo.revoke(db, stored)
    if user is not None:
        audit_service.success(db, AuditAction.LOGOUT, actor_user_id=user.id)
    db.commit()


def change_password(
    db: Session, *, user: User, current_password: str, new_password: str
) -> None:
    if not verify_password(current_password, user.password_hash):
        audit_service.failure(
            db,
            AuditAction.PASSWORD_CHANGED,
            actor_user_id=user.id,
            metadata={"reason": "INVALID_CURRENT_PASSWORD"},
        )
        db.commit()
        raise InvalidCredentialsError("Your current password is incorrect.")

    user.password_hash = hash_password(new_password)
    user.password_changed_at = utcnow()
    user.must_change_password = False
    # Every previously issued access token embeds the old pwd_at and every
    # refresh token is revoked, so other devices must sign in again.
    token_repo.revoke_all_for_user(db, user.id)
    audit_service.success(db, AuditAction.PASSWORD_CHANGED, actor_user_id=user.id)
    db.commit()


def access_token_still_valid(user: User, payload: dict) -> bool:
    """Reject access tokens issued before the last password change."""
    return int(payload.get("pwd_at", 0)) == epoch(user.password_changed_at)
