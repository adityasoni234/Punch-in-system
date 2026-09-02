from __future__ import annotations

from tests.conftest import auth, login, make_user, punch_body

from app.models.enums import Role, Team


def punch_headers(token: str) -> dict[str, str]:
    import uuid

    return {**auth(token), "Idempotency-Key": uuid.uuid4().hex}


def test_new_accounts_default_to_member(client, workspace):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Fresher",
            "email": "fresher@example.com",
            "member_id": "ENR900",
            "password": "FresherPass2026",
        },
    )
    assert response.status_code == 201
    assert response.json()["user"]["team"] == "MEMBER"


def test_self_signup_cannot_choose_a_team(client, workspace):
    """Nobody promotes themselves into the executive listing."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Ambitious",
            "email": "ambitious@example.com",
            "member_id": "ENR901",
            "password": "AmbitiousPass26",
            "team": "EXECUTIVE",
        },
    )
    assert response.status_code == 201
    assert response.json()["user"]["team"] == "MEMBER"


def test_admin_can_assign_a_team_on_creation(client, admin_token, workspace):
    response = client.post(
        "/api/v1/admin/users",
        headers=auth(admin_token),
        json={
            "name": "Chair",
            "email": "chair@example.com",
            "member_id": "EXE001",
            "role": "USER",
            "team": "EXECUTIVE",
        },
    )
    assert response.status_code == 201
    assert response.json()["user"]["team"] == "EXECUTIVE"


def test_admin_can_move_someone_between_teams(client, admin_token, db, workspace):
    person = make_user(db)
    response = client.patch(
        f"/api/v1/admin/users/{person.id}",
        headers=auth(admin_token),
        json={"team": "CORE"},
    )
    assert response.status_code == 200
    assert response.json()["team"] == "CORE"


def test_users_can_be_filtered_by_team(client, admin_token, db, workspace):
    make_user(db, team=Team.EXECUTIVE, name="Exec One")
    make_user(db, team=Team.CORE, name="Core One")
    make_user(db, team=Team.MEMBER, name="Member One")

    body = client.get("/api/v1/admin/users?team=CORE", headers=auth(admin_token)).json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Core One"


def test_dashboard_breaks_attendance_down_by_team(client, admin_token, db, workspace):
    exec_user = make_user(db, team=Team.EXECUTIVE, name="Exec Present")
    make_user(db, team=Team.EXECUTIVE, name="Exec Absent")
    core_user = make_user(db, team=Team.CORE, name="Core Present")
    make_user(db, team=Team.MEMBER, name="Member Absent")

    for person in (exec_user, core_user):
        token = login(client, person.email)
        assert client.post(
            "/api/v1/attendance/punch-in",
            headers=punch_headers(token),
            json=punch_body(),
        ).status_code == 200

    body = client.get("/api/v1/admin/dashboard", headers=auth(admin_token)).json()
    rows = {row["team"]: row for row in body["breakdown"]}

    # Order matters for the UI: executives, then core, then members.
    assert [row["team"] for row in body["breakdown"]] == ["EXECUTIVE", "CORE", "MEMBER"]

    assert rows["EXECUTIVE"]["total"] == 2
    assert rows["EXECUTIVE"]["present"] == 1
    assert rows["EXECUTIVE"]["absent"] == 1

    assert rows["CORE"]["total"] == 1
    assert rows["CORE"]["present"] == 1

    # The admin fixture itself is a MEMBER by default, alongside Member Absent.
    assert rows["MEMBER"]["total"] == 2
    assert rows["MEMBER"]["present"] == 0

    assert sum(r["total"] for r in body["breakdown"]) == body["total_users"]


def test_presence_entries_carry_their_team(client, admin_token, db, workspace):
    person = make_user(db, team=Team.EXECUTIVE, name="Exec Person")
    token = login(client, person.email)
    client.post("/api/v1/attendance/punch-in", headers=punch_headers(token), json=punch_body())

    body = client.get("/api/v1/admin/dashboard", headers=auth(admin_token)).json()
    assert body["present"][0]["team"] == "EXECUTIVE"


def test_breakdown_is_zeroed_not_missing_when_nobody_has_punched(
    client, admin_token, workspace
):
    body = client.get("/api/v1/admin/dashboard", headers=auth(admin_token)).json()
    assert len(body["breakdown"]) == 3
    assert all(row["present"] == 0 for row in body["breakdown"])
