from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.models.user import RefreshToken


def create(
    db: Session,
    *,
    user_id: uuid.UUID,
    token_hash: str,
    family_id: uuid.UUID,
    expires_at: datetime,
    user_agent_hash: str | None,
    ip_address: str | None,
) -> RefreshToken:
    token = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        family_id=family_id,
        issued_at=utcnow(),
        expires_at=expires_at,
        user_agent_hash=user_agent_hash,
        ip_address=ip_address,
    )
    db.add(token)
    db.flush()
    return token


def get_by_hash(db: Session, token_hash: str) -> RefreshToken | None:
    return db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))


def revoke(db: Session, token: RefreshToken) -> None:
    token.revoked_at = utcnow()
    db.flush()


def revoke_family(db: Session, family_id: uuid.UUID) -> int:
    """Token reuse detected -> burn the whole rotation family."""
    result = db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )
    return result.rowcount or 0


def revoke_all_for_user(db: Session, user_id: uuid.UUID) -> int:
    result = db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )
    return result.rowcount or 0


def purge_expired(db: Session) -> int:
    from sqlalchemy import delete

    result = db.execute(
        delete(RefreshToken).where(RefreshToken.expires_at < utcnow())
    )
    return result.rowcount or 0
