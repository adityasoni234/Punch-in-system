"""Per-request context: request id, client IP, user agent digest."""

from __future__ import annotations

import secrets
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings
from app.core.security import hash_user_agent

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_client_ip: ContextVar[str | None] = ContextVar("client_ip", default=None)
_user_agent_hash: ContextVar[str | None] = ContextVar("user_agent_hash", default=None)


def current_request_id() -> str | None:
    return _request_id.get()


def current_client_ip() -> str | None:
    return _client_ip.get()


def current_user_agent_hash() -> str | None:
    return _user_agent_hash.get()


def client_ip_from(request: Request) -> str | None:
    """Resolve the client IP, honouring X-Forwarded-For only when configured.

    Trusting the header unconditionally would let any caller forge the IP that
    the login rate limiter keys on.
    """
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()[:64]
    return request.client.host if request.client else None


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get("x-request-id") or secrets.token_hex(8)
        ip = client_ip_from(request)
        ua_hash = hash_user_agent(request.headers.get("user-agent"))

        tokens = (
            _request_id.set(request_id),
            _client_ip.set(ip),
            _user_agent_hash.set(ua_hash),
        )
        request.state.request_id = request_id
        request.state.client_ip = ip
        request.state.user_agent_hash = ua_hash
        try:
            response = await call_next(request)
        finally:
            _request_id.reset(tokens[0])
            _client_ip.reset(tokens[1])
            _user_agent_hash.reset(tokens[2])
        response.headers["X-Request-ID"] = request_id
        return response
