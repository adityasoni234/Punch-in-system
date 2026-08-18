"""Stable application error codes and the exception type carrying them.

Error codes are part of the public API contract: the frontend switches on
`code`, never on `message`. Messages are user facing and may change.
"""

from __future__ import annotations

from typing import Any


class ErrorCode:
    # auth
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    USER_DISABLED = "USER_DISABLED"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    TOKEN_INVALID = "TOKEN_INVALID"
    NOT_AUTHENTICATED = "NOT_AUTHENTICATED"
    FORBIDDEN = "FORBIDDEN"
    PASSWORD_CHANGE_REQUIRED = "PASSWORD_CHANGE_REQUIRED"

    # location / geofence
    INVALID_COORDINATES = "INVALID_COORDINATES"
    ACCURACY_TOO_LOW = "ACCURACY_TOO_LOW"
    OUTSIDE_GEOFENCE = "OUTSIDE_GEOFENCE"
    IMPOSSIBLE_MOVEMENT = "IMPOSSIBLE_MOVEMENT"
    WORKSPACE_NOT_CONFIGURED = "WORKSPACE_NOT_CONFIGURED"

    # attendance state machine
    ALREADY_PUNCHED_IN = "ALREADY_PUNCHED_IN"
    NO_ACTIVE_SESSION = "NO_ACTIVE_SESSION"
    DUPLICATE_REQUEST = "DUPLICATE_REQUEST"

    # generic
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    RATE_LIMITED = "RATE_LIMITED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class AppError(Exception):
    """Base class for every error deliberately returned to a client."""

    status_code: int = 400
    code: str = ErrorCode.VALIDATION_ERROR
    message: str = "Request could not be processed."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.status_code = status_code or self.status_code
        self.details = details or {}
        self.headers = headers or {}
        super().__init__(self.message)


class NotAuthenticatedError(AppError):
    status_code = 401
    code = ErrorCode.NOT_AUTHENTICATED
    message = "Authentication required."


class InvalidCredentialsError(AppError):
    status_code = 401
    code = ErrorCode.INVALID_CREDENTIALS
    message = "Incorrect email or password."


class TokenExpiredError(AppError):
    status_code = 401
    code = ErrorCode.TOKEN_EXPIRED
    message = "Your session has expired. Please sign in again."


class TokenInvalidError(AppError):
    status_code = 401
    code = ErrorCode.TOKEN_INVALID
    message = "Invalid authentication token."


class UserDisabledError(AppError):
    status_code = 403
    code = ErrorCode.USER_DISABLED
    message = "This account has been disabled. Contact your administrator."


class ForbiddenError(AppError):
    status_code = 403
    code = ErrorCode.FORBIDDEN
    message = "You do not have permission to perform this action."


class NotFoundError(AppError):
    status_code = 404
    code = ErrorCode.NOT_FOUND
    message = "Resource not found."


class ConflictError(AppError):
    status_code = 409
    code = ErrorCode.CONFLICT
    message = "The request conflicts with the current state."


class RateLimitedError(AppError):
    status_code = 429
    code = ErrorCode.RATE_LIMITED
    message = "Too many requests. Please try again shortly."

    def __init__(self, retry_after: int, message: str | None = None) -> None:
        super().__init__(
            message,
            details={"retry_after_seconds": retry_after},
            headers={"Retry-After": str(retry_after)},
        )


class GeofenceError(AppError):
    """Location was captured successfully but failed server side validation."""

    status_code = 422
    code = ErrorCode.OUTSIDE_GEOFENCE
    message = "You are outside the authorized workspace area."
