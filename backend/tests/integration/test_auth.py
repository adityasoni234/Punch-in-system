from __future__ import annotations

from tests.conftest import auth, login, make_user

from app.models.enums import Role, UserStatus


def test_login_returns_a_session(client, user):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "CorrectHorse99"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == user.email
    assert body["user"]["role"] == "USER"
    assert body["access_token"]
    assert "server_time" in body
    assert client.cookies.get("punchin_refresh")


def test_login_with_wrong_password_is_rejected(client, user):
    response = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "wrong-password"}
    )
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"


def test_login_for_unknown_email_gives_the_same_error(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@example.com", "password": "whatever123"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"


def test_disabled_user_cannot_log_in(client, db):
    disabled = make_user(db, status=UserStatus.DISABLED)
    response = client.post(
        "/api/v1/auth/login",
        json={"email": disabled.email, "password": "CorrectHorse99"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "USER_DISABLED"


def test_me_requires_a_token(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_returns_the_caller(client, user, user_token):
    response = client.get("/api/v1/auth/me", headers=auth(user_token))
    assert response.status_code == 200
    assert response.json()["user"]["id"] == str(user.id)


def test_invalid_token_is_rejected(client):
    response = client.get("/api/v1/auth/me", headers=auth("not-a-real-token"))
    assert response.status_code == 401
    assert response.json()["code"] == "TOKEN_INVALID"


def test_refresh_rotates_the_cookie(client, user):
    login(client, user.email)
    first = client.cookies.get("punchin_refresh")
    response = client.post("/api/v1/auth/refresh")
    assert response.status_code == 200
    assert client.cookies.get("punchin_refresh") != first


def test_reusing_a_rotated_refresh_token_kills_the_family(client, user):
    login(client, user.email)
    stolen = client.cookies.get("punchin_refresh")
    assert client.post("/api/v1/auth/refresh").status_code == 200

    client.cookies.set("punchin_refresh", stolen)
    replay = client.post("/api/v1/auth/refresh")
    assert replay.status_code == 401

    # The whole family is revoked, so the legitimate current token dies too.
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_login_is_rate_limited(client, db):
    victim = make_user(db)
    codes = []
    for _ in range(8):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": victim.email, "password": "wrong-password"},
        )
        codes.append(response.status_code)
    assert 429 in codes
    limited = next(c for c in codes if c == 429)
    assert limited == 429


def test_rate_limited_response_carries_retry_after(client, db):
    victim = make_user(db)
    last = None
    for _ in range(8):
        last = client.post(
            "/api/v1/auth/login",
            json={"email": victim.email, "password": "wrong-password"},
        )
    assert last.status_code == 429
    assert last.json()["code"] == "RATE_LIMITED"
    assert "Retry-After" in last.headers


def test_password_change_invalidates_existing_tokens(client, db):
    person = make_user(db)
    token = login(client, person.email)
    response = client.post(
        "/api/v1/auth/change-password",
        headers=auth(token),
        json={"current_password": "CorrectHorse99", "new_password": "BrandNewPass77"},
    )
    assert response.status_code == 200
    assert client.get("/api/v1/auth/me", headers=auth(token)).status_code == 401
    assert login(client, person.email, "BrandNewPass77")


def test_admin_role_is_visible_in_the_session(client, db):
    boss = make_user(db, role=Role.ADMIN)
    token = login(client, boss.email)
    body = client.get("/api/v1/auth/me", headers=auth(token)).json()
    assert body["user"]["role"] == "ADMIN"


def test_successful_logins_do_not_consume_the_account_limit(client, db):
    """Signing in correctly must never lock you out of your own account."""
    person = make_user(db)
    for _ in range(8):
        response = client.post(
            "/api/v1/auth/login",
            json={"identifier": person.email, "password": "CorrectHorse99"},
        )
        assert response.status_code == 200, response.text


def test_a_success_clears_earlier_failures(client, db):
    person = make_user(db)
    for _ in range(3):
        client.post(
            "/api/v1/auth/login",
            json={"identifier": person.email, "password": "wrong-password"},
        )
    assert login(client, person.email)  # succeeds, and resets the window
    for _ in range(4):
        response = client.post(
            "/api/v1/auth/login",
            json={"identifier": person.email, "password": "wrong-password"},
        )
    assert response.status_code == 401  # still counting from zero, not locked


def test_one_account_lockout_does_not_block_another_person(client, db):
    """Everyone on a campus network shares one IP; one person exhausting their
    own attempts must not lock out their colleagues."""
    victim = make_user(db)
    bystander = make_user(db)

    for _ in range(7):
        client.post(
            "/api/v1/auth/login",
            json={"identifier": victim.email, "password": "wrong-password"},
        )
    locked = client.post(
        "/api/v1/auth/login",
        json={"identifier": victim.email, "password": "CorrectHorse99"},
    )
    assert locked.status_code == 429

    ok = client.post(
        "/api/v1/auth/login",
        json={"identifier": bystander.email, "password": "CorrectHorse99"},
    )
    assert ok.status_code == 200


def test_many_people_can_register_from_one_network(client, workspace):
    """A whole cohort signing up together on shared WiFi must not be blocked."""
    for index in range(15):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "name": f"Person {index}",
                "email": f"person{index}@example.com",
                "member_id": f"ENR20260{index:03d}",
                "password": "CohortPass2026",
            },
        )
        assert response.status_code == 201, f"blocked at signup {index}: {response.text}"
