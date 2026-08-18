#!/usr/bin/env python
"""Create the first administrator (or any additional admin).

Credentials are never hardcoded or defaulted: the password is either typed
interactively (hidden) or generated at random and printed once.

    python -m scripts.create_admin --name "Aditya" --email you@example.com \
        --member-id ADM001
"""

from __future__ import annotations

import argparse
import getpass
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from app.core.security import generate_password, hash_password  # noqa: E402
from app.core.time import utcnow  # noqa: E402
from app.db.session import session_scope  # noqa: E402
from app.models.enums import AuditAction, AuditResult, Role, UserStatus  # noqa: E402
from app.models.user import User  # noqa: E402
from app.repositories import audit_repo, user_repo  # noqa: E402

MIN_PASSWORD_LENGTH = 10


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create an administrator account")
    parser.add_argument("--name", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--member-id", required=True)
    parser.add_argument(
        "--generate-password",
        action="store_true",
        help="Generate a random password instead of prompting",
    )
    return parser.parse_args()


def read_password() -> str:
    while True:
        password = getpass.getpass("Password: ")
        if len(password) < MIN_PASSWORD_LENGTH:
            print(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
            continue
        if password != getpass.getpass("Confirm password: "):
            print("Passwords do not match.")
            continue
        return password


def main() -> int:
    args = parse_args()
    email = args.email.strip().lower()

    with session_scope() as db:
        if user_repo.get_by_email(db, email):
            print(f"error: a user with email {email} already exists", file=sys.stderr)
            return 1
        if user_repo.get_by_member_id(db, args.member_id):
            print(
                f"error: a user with member id {args.member_id} already exists",
                file=sys.stderr,
            )
            return 1

        if args.generate_password:
            password = generate_password(16)
            generated = True
        else:
            password = read_password()
            generated = False

        user = User(
            name=args.name.strip(),
            email=email,
            member_id=args.member_id.strip(),
            role=Role.ADMIN,
            status=UserStatus.ACTIVE,
            password_hash=hash_password(password),
            must_change_password=generated,
            password_changed_at=utcnow(),
        )
        db.add(user)
        db.flush()
        audit_repo.add(
            db,
            action=AuditAction.USER_CREATED,
            result=AuditResult.SUCCESS,
            actor_user_id=user.id,
            target_user_id=user.id,
            metadata={"role": "ADMIN", "via": "cli"},
        )
        print(f"Administrator created: {user.email} (member id {user.member_id})")
        if generated:
            print(f"Temporary password: {password}")
            print("This is shown once. The account must change it at first sign-in.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
