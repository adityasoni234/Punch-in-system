from __future__ import annotations

import uuid

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.models.enums import Role, UserStatus
from app.models.user import User


def get_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    return db.get(User, user_id)


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def get_by_member_id(db: Session, member_id: str) -> User | None:
    return db.scalar(select(User).where(User.member_id == member_id))


def lock_for_update(db: Session, user_id: uuid.UUID) -> User | None:
    """Row-level lock. Serialises concurrent punches for the same user."""
    return db.scalar(select(User).where(User.id == user_id).with_for_update())


def _base_query(
    search: str | None, role: Role | None, status: UserStatus | None
) -> Select:
    stmt = select(User)
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                User.name.ilike(pattern),
                User.email.ilike(pattern),
                User.member_id.ilike(pattern),
            )
        )
    if role is not None:
        stmt = stmt.where(User.role == role)
    if status is not None:
        stmt = stmt.where(User.status == status)
    return stmt


def list_users(
    db: Session,
    *,
    search: str | None = None,
    role: Role | None = None,
    status: UserStatus | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[User], int]:
    stmt = _base_query(search, role, status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = list(
        db.scalars(
            stmt.order_by(User.name.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return rows, total


def all_active_users(db: Session) -> list[User]:
    return list(
        db.scalars(
            select(User)
            .where(User.status == UserStatus.ACTIVE)
            .order_by(User.name.asc())
        )
    )


def count_users(db: Session, *, status: UserStatus | None = None) -> int:
    stmt = select(func.count()).select_from(User)
    if status is not None:
        stmt = stmt.where(User.status == status)
    return db.scalar(stmt) or 0


def add(db: Session, user: User) -> User:
    db.add(user)
    db.flush()
    return user
