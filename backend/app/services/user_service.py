"""Administrative user management."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.core.security import generate_password, hash_password
from app.core.time import utcnow
from app.models.enums import AuditAction, Role, UserStatus
from app.models.user import User
from app.repositories import token_repo, user_repo
from app.schemas.admin import UserCreateRequest, UserUpdateRequest
from app.services import audit_service


def _assert_unique(
    db: Session, *, email: str | None, member_id: str | None, exclude: uuid.UUID | None
) -> None:
    if email:
        existing = user_repo.get_by_email(db, email)
        if existing and existing.id != exclude:
            raise ConflictError("A user with this email already exists.")
    if member_id:
        existing = user_repo.get_by_member_id(db, member_id)
        if existing and existing.id != exclude:
            raise ConflictError("A user with this member ID already exists.")


def get(db: Session, user_id: uuid.UUID) -> User:
    user = user_repo.get_by_id(db, user_id)
    if user is None:
        raise NotFoundError("User not found.")
    return user


def create(db: Session, *, actor: User, payload: UserCreateRequest) -> tuple[User, str]:
    _assert_unique(db, email=payload.email, member_id=payload.member_id, exclude=None)
    temporary_password = payload.password or generate_password()
    user = User(
        name=payload.name.strip(),
        email=str(payload.email).lower(),
        member_id=payload.member_id.strip(),
        role=payload.role,
        status=UserStatus.ACTIVE,
        password_hash=hash_password(temporary_password),
        must_change_password=True,
        password_changed_at=utcnow(),
    )
    user_repo.add(db, user)
    audit_service.success(
        db,
        AuditAction.USER_CREATED,
        actor_user_id=actor.id,
        target_user_id=user.id,
        metadata={"role": user.role.value, "member_id": user.member_id},
    )
    db.commit()
    db.refresh(user)
    return user, temporary_password


def update(
    db: Session, *, actor: User, user_id: uuid.UUID, payload: UserUpdateRequest
) -> User:
    user = get(db, user_id)
    data = payload.model_dump(exclude_unset=True)
    _assert_unique(
        db,
        email=str(data["email"]).lower() if data.get("email") else None,
        member_id=data.get("member_id"),
        exclude=user.id,
    )

    changes: dict[str, dict[str, str]] = {}
    role_changed = False
    for field in ("name", "email", "member_id", "role"):
        if field not in data or data[field] is None:
            continue
        new_value = data[field]
        if field == "email":
            new_value = str(new_value).lower()
        old_value = getattr(user, field)
        if str(old_value) != str(new_value):
            if field == "role" and user.id == actor.id:
                raise ForbiddenError("You cannot change your own role.")
            setattr(user, field, new_value)
            changes[field] = {"from": str(old_value), "to": str(new_value)}
            role_changed = role_changed or field == "role"

    if changes:
        audit_service.success(
            db,
            AuditAction.USER_ROLE_CHANGED if role_changed else AuditAction.USER_UPDATED,
            actor_user_id=actor.id,
            target_user_id=user.id,
            metadata={"changes": changes},
        )
    if role_changed:
        # Force a re-login so the new role is reflected in a fresh token.
        token_repo.revoke_all_for_user(db, user.id)
    db.commit()
    db.refresh(user)
    return user


def set_status(
    db: Session, *, actor: User, user_id: uuid.UUID, status: UserStatus
) -> User:
    user = get(db, user_id)
    if user.id == actor.id and status == UserStatus.DISABLED:
        raise ForbiddenError("You cannot disable your own account.")
    if user.status == status:
        return user

    user.status = status
    if status == UserStatus.DISABLED:
        # Immediate lockout: refresh tokens die now, the access token dies
        # within its 15 minute lifetime and is rejected by the auth dependency
        # on the very next request anyway.
        token_repo.revoke_all_for_user(db, user.id)

    audit_service.success(
        db,
        AuditAction.USER_DISABLED
        if status == UserStatus.DISABLED
        else AuditAction.USER_ENABLED,
        actor_user_id=actor.id,
        target_user_id=user.id,
    )
    db.commit()
    db.refresh(user)
    return user


def reset_password(db: Session, *, actor: User, user_id: uuid.UUID) -> tuple[User, str]:
    user = get(db, user_id)
    temporary_password = generate_password()
    user.password_hash = hash_password(temporary_password)
    user.password_changed_at = utcnow()
    user.must_change_password = True
    token_repo.revoke_all_for_user(db, user.id)
    audit_service.success(
        db,
        AuditAction.USER_PASSWORD_RESET,
        actor_user_id=actor.id,
        target_user_id=user.id,
    )
    db.commit()
    db.refresh(user)
    return user, temporary_password
