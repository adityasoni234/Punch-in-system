from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status

from app.core.config import settings
from app.core.deps import CurrentUser, DbSession, login_rate_limit
from app.core.errors import NotAuthenticatedError
from app.core.time import utcnow
from app.repositories import workspace_repo
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    SessionInfo,
    UserPublic,
    WorkspacePublic,
)
from app.schemas.common import MessageResponse
from app.services import auth_service, rate_limit

router = APIRouter(prefix="/auth", tags=["auth"])


def _workspace_public(db) -> WorkspacePublic | None:
    workspace = workspace_repo.get_active(db)
    if workspace is None:
        return None
    return WorkspacePublic(
        name=workspace.name,
        radius_meters=workspace.radius_meters,
        accuracy_threshold_meters=workspace.accuracy_threshold_meters,
        timezone=workspace.timezone,
    )


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        settings.refresh_cookie_name,
        token,
        max_age=settings.refresh_token_expire_days * 24 * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain,
        path=f"{settings.api_prefix}/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        settings.refresh_cookie_name,
        domain=settings.cookie_domain,
        path=f"{settings.api_prefix}/auth",
    )


@router.post(
    "/login",
    response_model=SessionInfo,
    dependencies=[Depends(login_rate_limit)],
    summary="Authenticate and start a session",
)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: DbSession,
) -> SessionInfo:
    # A second, per-account limit so one attacker cannot spread a password
    # spray for a single account across many source addresses.
    rate_limit.enforce(db, rate_limit.login_policy(), f"email:{payload.email.lower()}")
    db.commit()

    issued = auth_service.login(
        db,
        email=str(payload.email).lower(),
        password=payload.password,
        user_agent=request.headers.get("user-agent"),
        ip_address=getattr(request.state, "client_ip", None),
    )
    _set_refresh_cookie(response, issued.refresh_token)
    return SessionInfo(
        access_token=issued.access_token,
        expires_at=issued.access_expires_at,
        user=UserPublic.model_validate(issued.user),
        workspace=_workspace_public(db),
        server_time=utcnow(),
    )


@router.post("/refresh", response_model=SessionInfo, summary="Rotate the session")
def refresh(request: Request, response: Response, db: DbSession) -> SessionInfo:
    raw = request.cookies.get(settings.refresh_cookie_name)
    if not raw:
        raise NotAuthenticatedError("No active session.")
    issued = auth_service.refresh(
        db,
        raw_refresh_token=raw,
        user_agent=request.headers.get("user-agent"),
        ip_address=getattr(request.state, "client_ip", None),
    )
    _set_refresh_cookie(response, issued.refresh_token)
    return SessionInfo(
        access_token=issued.access_token,
        expires_at=issued.access_expires_at,
        user=UserPublic.model_validate(issued.user),
        workspace=_workspace_public(db),
        server_time=utcnow(),
    )


@router.post("/logout", response_model=MessageResponse, summary="End the session")
def logout(request: Request, response: Response, db: DbSession) -> MessageResponse:
    raw = request.cookies.get(settings.refresh_cookie_name)
    user = None
    try:
        from app.core.deps import get_current_user

        user = get_current_user(request, db)
    except Exception:
        # Logging out with an expired access token must still clear the cookie.
        user = None
    auth_service.logout(db, raw_refresh_token=raw, user=user)
    _clear_refresh_cookie(response)
    return MessageResponse(message="Signed out.")


@router.get("/me", response_model=SessionInfo, summary="Current session context")
def me(user: CurrentUser, request: Request, db: DbSession) -> SessionInfo:
    """Returns the caller plus `server_time`, which the SPA uses to correct for
    device clock skew when rendering the live timer."""
    token = request.headers["authorization"].split(" ", 1)[1]
    from app.core.security import decode_access_token

    payload = decode_access_token(token)
    from datetime import datetime, timezone

    return SessionInfo(
        access_token=token,
        expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
        user=UserPublic.model_validate(user),
        workspace=_workspace_public(db),
        server_time=utcnow(),
    )


@router.post(
    "/change-password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Change your own password",
)
def change_password(
    payload: ChangePasswordRequest,
    user: CurrentUser,
    response: Response,
    db: DbSession,
) -> MessageResponse:
    auth_service.change_password(
        db,
        user=user,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    _clear_refresh_cookie(response)
    return MessageResponse(
        message="Password updated. Please sign in again on your devices."
    )
