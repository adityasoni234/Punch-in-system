from __future__ import annotations

import uuid

from tests.conftest import auth, login, make_user, punch_body

from app.models.enums import Role, UserStatus

ADMIN_ENDPOINTS = [
    "/api/v1/admin/dashboard",
    "/api/v1/admin/users",
    "/api/v1/admin/workspace",
    "/api/v1/admin/attendance",
    "/api/v1/admin/audit-logs",
    "/api/v1/admin/punch-events",
]


def test_protected_endpoints_require_authentication(client, workspace):
    for path in [*ADMIN_ENDPOINTS, "/api/v1/attendance/today"]:
        assert client.get(path).status_code == 401, path


def test_ordinary_user_cannot_reach_admin_endpoints(client, user_token, workspace):
    for path in ADMIN_ENDPOINTS:
        response = client.get(path, headers=auth(user_token))
        assert response.status_code == 403, path
        assert response.json()["code"] == "FORBIDDEN"


def test_ordinary_user_cannot_mutate_the_workspace(client, user_token, workspace):
    response = client.patch(
        "/api/v1/admin/workspace", headers=auth(user_token), json={"radius_meters": 5000}
    )
    assert response.status_code == 403


def test_ordinary_user_cannot_create_users(client, user_token, workspace):
    response = client.post(
        "/api/v1/admin/users",
        headers=auth(user_token),
        json={
            "name": "Mallory",
            "email": "mallory@example.com",
            "member_id": "EMP999",
            "role": "ADMIN",
        },
    )
    assert response.status_code == 403


def test_admin_can_reach_admin_endpoints(client, admin_token, workspace):
    for path in ADMIN_ENDPOINTS:
        assert client.get(path, headers=auth(admin_token)).status_code == 200, path


def test_role_in_the_token_is_not_trusted(client, db, workspace):
    """A token minted for a USER stays a USER even if the row later changes back."""
    from app.core.security import create_access_token

    person = make_user(db, role=Role.USER)
    forged, _ = create_access_token(
        user_id=person.id, role="ADMIN", password_changed_at=person.password_changed_at
    )
    response = client.get("/api/v1/admin/dashboard", headers=auth(forged))
    assert response.status_code == 403


def test_disabling_a_user_locks_them_out_immediately(client, db, admin_token, workspace):
    person = make_user(db)
    token = login(client, person.email)
    assert client.get("/api/v1/attendance/today", headers=auth(token)).status_code == 200

    response = client.patch(
        f"/api/v1/admin/users/{person.id}/status",
        headers=auth(admin_token),
        json={"status": "DISABLED"},
    )
    assert response.status_code == 200

    blocked = client.get("/api/v1/attendance/today", headers=auth(token))
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "USER_DISABLED"


def test_disabled_user_cannot_punch(client, db, admin_token, workspace):
    person = make_user(db)
    token = login(client, person.email)
    client.patch(
        f"/api/v1/admin/users/{person.id}/status",
        headers=auth(admin_token),
        json={"status": "DISABLED"},
    )
    response = client.post(
        "/api/v1/attendance/punch-in",
        headers={**auth(token), "Idempotency-Key": uuid.uuid4().hex},
        json=punch_body(),
    )
    assert response.status_code == 403


def test_punching_is_rate_limited(client, user_token, workspace):
    codes = []
    for _ in range(14):
        response = client.post(
            "/api/v1/attendance/punch-in",
            headers={**auth(user_token), "Idempotency-Key": uuid.uuid4().hex},
            json=punch_body(lat=1.0, lng=1.0),
        )
        codes.append(response.status_code)
    assert 429 in codes


def test_invalid_punch_payloads_are_rejected(client, user_token, workspace):
    bad_payloads = [
        {"latitude": 200, "longitude": 0, "accuracy": 5},
        {"latitude": 23.09, "longitude": 500, "accuracy": 5},
        {"latitude": 23.09, "longitude": 72.53, "accuracy": -1},
        {"latitude": "north", "longitude": 72.53, "accuracy": 5},
        {"longitude": 72.53, "accuracy": 5},
    ]
    for payload in bad_payloads:
        response = client.post(
            "/api/v1/attendance/punch-in",
            headers={**auth(user_token), "Idempotency-Key": uuid.uuid4().hex},
            json=payload,
        )
        assert response.status_code == 422, payload
        assert response.json()["code"] in {"VALIDATION_ERROR", "INVALID_COORDINATES"}


def test_client_cannot_assert_identity_or_distance(client, user_token, admin, workspace):
    """Extra fields the client might hope are trusted are ignored outright."""
    response = client.post(
        "/api/v1/attendance/punch-in",
        headers={**auth(user_token), "Idempotency-Key": uuid.uuid4().hex},
        json={
            **punch_body(lat=1.0, lng=1.0),
            "user_id": str(admin.id),
            "distance": 0,
            "inside_geofence": True,
            "duration_seconds": 99999,
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "OUTSIDE_GEOFENCE"


def test_security_headers_are_present(client, workspace):
    response = client.get("/api/v1/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "Content-Security-Policy" in response.headers
    assert response.headers["Referrer-Policy"] == "no-referrer"


def test_admin_cannot_disable_their_own_account(client, admin, admin_token, workspace):
    response = client.patch(
        f"/api/v1/admin/users/{admin.id}/status",
        headers=auth(admin_token),
        json={"status": "DISABLED"},
    )
    assert response.status_code == 403


def test_unknown_user_id_is_a_clean_404(client, admin_token, workspace):
    response = client.get(
        f"/api/v1/admin/users/{uuid.uuid4()}", headers=auth(admin_token)
    )
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"
