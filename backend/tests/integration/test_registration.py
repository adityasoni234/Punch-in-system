from __future__ import annotations

from tests.conftest import auth, make_user

from app.models.enums import Role, UserStatus

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"


def signup(client, **overrides):
    payload = {
        "name": "New Member",
        "email": "member@example.com",
        "member_id": "ENR2026001",
        "password": "EnrollPass2026",
    }
    payload.update(overrides)
    return client.post(REGISTER, json=payload)


def test_self_signup_creates_a_member_and_signs_them_in(client, workspace):
    response = signup(client)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["user"]["role"] == "USER"
    assert body["user"]["member_id"] == "ENR2026001"
    assert body["access_token"]
    assert client.get("/api/v1/auth/me", headers=auth(body["access_token"])).status_code == 200


def test_member_signs_in_with_the_enrollment_number(client, workspace):
    signup(client)
    response = client.post(
        LOGIN, json={"identifier": "ENR2026001", "password": "EnrollPass2026"}
    )
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "member@example.com"


def test_enrollment_number_is_case_insensitive(client, workspace):
    signup(client)
    response = client.post(
        LOGIN, json={"identifier": "enr2026001", "password": "EnrollPass2026"}
    )
    assert response.status_code == 200


def test_admin_signs_in_with_their_email(client, db, workspace):
    boss = make_user(db, role=Role.ADMIN, email="boss@example.com")
    response = client.post(
        LOGIN, json={"identifier": "boss@example.com", "password": "CorrectHorse99"}
    )
    assert response.status_code == 200
    assert response.json()["user"]["role"] == "ADMIN"
    assert boss.email == "boss@example.com"


def test_signup_cannot_grant_itself_admin(client, workspace):
    response = client.post(
        REGISTER,
        json={
            "name": "Sneaky",
            "email": "sneaky@example.com",
            "member_id": "ENR999",
            "password": "SneakyPass123",
            "role": "ADMIN",
        },
    )
    assert response.status_code == 201
    assert response.json()["user"]["role"] == "USER"


def test_duplicate_enrollment_number_is_rejected(client, workspace):
    signup(client)
    response = signup(client, email="other@example.com")
    assert response.status_code == 409
    assert "enrollment" in response.json()["message"].lower()


def test_duplicate_email_is_rejected(client, workspace):
    signup(client)
    response = signup(client, member_id="ENR2026002")
    assert response.status_code == 409
    assert "email" in response.json()["message"].lower()


def test_short_password_is_rejected(client, workspace):
    response = signup(client, password="short")
    assert response.status_code == 422


def test_login_without_an_identifier_is_rejected(client, workspace):
    assert client.post(LOGIN, json={"password": "whatever123"}).status_code == 422


def test_disabled_member_cannot_sign_in_with_enrollment(client, db, workspace):
    person = make_user(db, status=UserStatus.DISABLED)
    response = client.post(
        LOGIN, json={"identifier": person.member_id, "password": "CorrectHorse99"}
    )
    assert response.status_code == 403
    assert response.json()["code"] == "USER_DISABLED"


def test_unknown_identifier_gives_the_generic_error(client, workspace):
    response = client.post(
        LOGIN, json={"identifier": "ENR000000", "password": "whatever123"}
    )
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"
