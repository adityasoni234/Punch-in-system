from __future__ import annotations

import os
import uuid
from datetime import time

# Must be set before app.core.config is imported anywhere.
os.environ.setdefault("ENVIRONMENT", "test")
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://punchin:punchin@localhost:5432/punchin_test",
)
os.environ["DEBUG"] = "false"
# Pin the cookie settings rather than inheriting whatever profile backend/.env
# currently holds: the deployment profile sets Secure cookies, which the test
# client (plain http://testserver) would silently discard, breaking the refresh
# tests for reasons that have nothing to do with the code under test.
os.environ["COOKIE_SECURE"] = "false"
os.environ["COOKIE_SAMESITE"] = "lax"
os.environ["CORS_ORIGINS"] = ""
os.environ["RUN_MIGRATIONS_ON_START"] = "false"
os.environ["RATE_LIMIT_LOGIN_MAX"] = "5"
os.environ["RATE_LIMIT_LOGIN_WINDOW_SECONDS"] = "900"
os.environ["RATE_LIMIT_PUNCH_MAX"] = "10"
os.environ["RATE_LIMIT_PUNCH_WINDOW_SECONDS"] = "60"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.core.time import utcnow  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.enums import Role, Team, UserStatus  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.workspace import Workspace  # noqa: E402

WORKSPACE_LAT = 23.0900259
WORKSPACE_LNG = 72.5343615

TABLES = [
    "punch_events",
    "attendance_sessions",
    "attendance_days",
    "audit_logs",
    "refresh_tokens",
    "rate_limit_buckets",
    "users",
    "workspaces",
]


@pytest.fixture(scope="session", autouse=True)
def _schema():
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS citext"))
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def _clean_tables():
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def workspace(db) -> Workspace:
    ws = Workspace(
        name="Test Workspace",
        latitude=WORKSPACE_LAT,
        longitude=WORKSPACE_LNG,
        radius_meters=100,
        accuracy_threshold_meters=50,
        timezone="Asia/Kolkata",
        attendance_start_time=time(9, 30),
        late_threshold_minutes=15,
        auto_close_after_hours=16,
        max_travel_speed_kmh=300,
        block_impossible_movement=False,
        active=True,
    )
    db.add(ws)
    db.commit()
    db.refresh(ws)
    return ws


def make_user(
    db,
    *,
    email: str | None = None,
    password: str = "CorrectHorse99",
    role: Role = Role.USER,
    status: UserStatus = UserStatus.ACTIVE,
    team: Team = Team.MEMBER,
    name: str = "Test User",
) -> User:
    suffix = uuid.uuid4().hex[:8]
    user = User(
        name=name,
        email=email or f"user-{suffix}@example.com",
        member_id=f"EMP{suffix.upper()}",
        password_hash=hash_password(password),
        role=role,
        team=team,
        status=status,
        must_change_password=False,
        password_changed_at=utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def user(db):
    return make_user(db)


@pytest.fixture
def admin(db):
    return make_user(db, role=Role.ADMIN, name="Admin User")


def login(client: TestClient, email: str, password: str = "CorrectHorse99") -> str:
    response = client.post(
        "/api/v1/auth/login", json={"identifier": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user_token(client, user) -> str:
    return login(client, user.email)


@pytest.fixture
def admin_token(client, admin) -> str:
    return login(client, admin.email)


def punch_body(
    lat: float = WORKSPACE_LAT, lng: float = WORKSPACE_LNG, accuracy: float = 10.0
) -> dict:
    return {"latitude": lat, "longitude": lng, "accuracy": accuracy}
