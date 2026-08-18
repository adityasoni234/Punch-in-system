from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.workspace import Workspace


def get_active(db: Session) -> Workspace | None:
    return db.scalar(select(Workspace).where(Workspace.active.is_(True)))


def get_active_for_update(db: Session) -> Workspace | None:
    return db.scalar(
        select(Workspace).where(Workspace.active.is_(True)).with_for_update()
    )
