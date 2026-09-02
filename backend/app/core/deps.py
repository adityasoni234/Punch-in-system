"""FastAPI dependencies: database session, authentication, RBAC, rate limits.

Authorisation is enforced here, on the server. The React router's guards are a
usability affordance only -- every protected endpoint re-derives the caller's
identity and role from the token and the database on every request.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from app.core.errors import (
    ForbiddenError,
    NotAuthenticatedError,
    TokenInvalidError,
    UserDisabledError,
)
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.enums import Role
from app.models.user import User
from app.models.workspace import Workspace
from app.repositories import user_repo
from app.services import auth_service, rate_limit, workspace_service

DbSession = Annotated[Session, Depends(get_db)]


def _bearer_token(request: Request) -> str:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise NotAuthenticatedError()
    return token.strip()


def get_current_user(request: Request, db: DbSession) -> User:
    payload = decode_access_token(_bearer_token(request))
    try:
        user_id = payload["sub"]
    except KeyError as exc:  # pragma: no cover - guarded by decode options
        raise TokenInvalidError() from exc

    user = user_repo.get_by_id(db, user_id)
    if user is None:
        raise TokenInvalidError()
    if not user.is_active:
        raise UserDisabledError()
    # A password change or admin reset invalidates every older access token.
    if not auth_service.access_token_still_valid(user, payload):
        raise TokenInvalidError("Your session is no longer valid. Please sign in again.")
    # The role is re-read from the database; the token's copy is never trusted
    # for authorisation decisions.
    request.state.user_id = str(user.id)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> User:
    if user.role != Role.ADMIN:
        raise ForbiddenError()
    return user


AdminUser = Annotated[User, Depends(require_admin)]


def get_workspace(db: DbSession) -> Workspace:
    return workspace_service.get_active(db)


ActiveWorkspace = Annotated[Workspace, Depends(get_workspace)]


def idempotency_key(
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> str | None:
    if idempotency_key is None:
        return None
    key = idempotency_key.strip()[:80]
    return key or None


IdempotencyKey = Annotated[str | None, Depends(idempotency_key)]


def punch_rate_limit(request: Request, db: DbSession, user: CurrentUser) -> None:
    rate_limit.enforce(db, rate_limit.punch_policy(), f"user:{user.id}")
    db.commit()


def login_rate_limit(request: Request, db: DbSession) -> None:
    """Flood protection for a whole network, not a per-account lockout.

    A campus or office shares one public address, so this deliberately allows
    far more than the per-account limit does.
    """
    ip = getattr(request.state, "client_ip", None) or "unknown"
    rate_limit.enforce(db, rate_limit.login_ip_policy(), f"ip:{ip}")
    db.commit()


def register_rate_limit(request: Request, db: DbSession) -> None:
    ip = getattr(request.state, "client_ip", None) or "unknown"
    rate_limit.enforce(db, rate_limit.register_policy(), f"ip:{ip}")
    db.commit()
