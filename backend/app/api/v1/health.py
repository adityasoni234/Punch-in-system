from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.core.deps import DbSession
from app.core.time import utcnow

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness / readiness probe")
def health(db: DbSession) -> dict:
    """Used by the PWA to distinguish 'offline' from 'backend unavailable'."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "server_time": utcnow().isoformat()}
