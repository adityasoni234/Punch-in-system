from __future__ import annotations

import uuid

from tests.conftest import auth, login, make_user, punch_body

from app.models.enums import AuditAction
from app.models.audit_log import AuditLog


def punch_headers(token: str) -> dict[str, str]:
    return {**auth(token), "Idempotency-Key": uuid.uuid4().hex}


def test_dashboard_counts_present_absent_and_checked_out(
    client, db, admin, admin_token, workspace
):
    present = make_user(db, name="Present Person")
    checked_out = make_user(db, name="Checked Out Person")
    make_user(db, name="Absent Person")

    token = login(client, present.email)
    client.post("/api/v1/attendance/punch-in", headers=punch_headers(token), json=punch_body())

    token2 = login(client, checked_out.email)
    client.post("/api/v1/attendance/punch-in", headers=punch_headers(token2), json=punch_body())
    client.post("/api/v1/attendance/punch-out", headers=punch_headers(token2), json=punch_body())

    body = client.get("/api/v1/admin/dashboard", headers=auth(admin_token)).json()
    assert body["total_users"] == 4  # admin + 3
    assert body["present_count"] == 1
    assert body["checked_out_count"] == 1
    assert body["absent_count"] == 2  # absent person + the admin
    assert body["present"][0]["name"] == "Present Person"
    assert body["present"][0]["elapsed_seconds"] >= 0
    assert body["present"][0]["punch_in"] is not None


def test_dashboard_is_empty_when_nobody_has_punched(client, admin_token, workspace):
    body = client.get("/api/v1/admin/dashboard", headers=auth(admin_token)).json()
    assert body["present"] == []
    assert body["checked_out"] == []
    assert body["absent_count"] == body["total_users"]


def test_admin_can_create_a_user_and_they_can_log_in(client, admin_token, workspace):
    response = client.post(
        "/api/v1/admin/users",
        headers=auth(admin_token),
        json={
            "name": "New Joiner",
            "email": "new.joiner@example.com",
            "member_id": "EMP1234",
            "role": "USER",
        },
    )
    assert response.status_code == 201
    body = response.json()
    temporary = body["temporary_password"]
    assert len(temporary) >= 12
    assert body["user"]["must_change_password"] is True

    token = login(client, "new.joiner@example.com", temporary)
    assert client.get("/api/v1/auth/me", headers=auth(token)).status_code == 200


def test_duplicate_email_or_member_id_is_rejected(client, admin_token, db, workspace):
    existing = make_user(db)
    response = client.post(
        "/api/v1/admin/users",
        headers=auth(admin_token),
        json={
            "name": "Clone",
            "email": existing.email,
            "member_id": "EMP0001",
            "role": "USER",
        },
    )
    assert response.status_code == 409


def test_admin_can_update_and_toggle_status(client, admin_token, db, workspace):
    person = make_user(db)
    updated = client.patch(
        f"/api/v1/admin/users/{person.id}",
        headers=auth(admin_token),
        json={"name": "Renamed"},
    )
    assert updated.json()["name"] == "Renamed"

    disabled = client.patch(
        f"/api/v1/admin/users/{person.id}/status",
        headers=auth(admin_token),
        json={"status": "DISABLED"},
    )
    assert disabled.json()["status"] == "DISABLED"

    enabled = client.patch(
        f"/api/v1/admin/users/{person.id}/status",
        headers=auth(admin_token),
        json={"status": "ACTIVE"},
    )
    assert enabled.json()["status"] == "ACTIVE"


def test_password_reset_issues_a_working_temporary_password(
    client, admin_token, db, workspace
):
    person = make_user(db)
    response = client.post(
        f"/api/v1/admin/users/{person.id}/reset-password", headers=auth(admin_token)
    )
    assert response.status_code == 200
    temporary = response.json()["temporary_password"]
    assert login(client, person.email, temporary)


def test_workspace_settings_are_configurable_at_runtime(client, admin_token, workspace):
    response = client.patch(
        "/api/v1/admin/workspace",
        headers=auth(admin_token),
        json={"radius_meters": 250, "accuracy_threshold_meters": 75},
    )
    assert response.status_code == 200
    assert response.json()["radius_meters"] == 250

    fetched = client.get("/api/v1/admin/workspace", headers=auth(admin_token)).json()
    assert fetched["radius_meters"] == 250
    assert fetched["accuracy_threshold_meters"] == 75


def test_widening_the_radius_changes_punch_outcomes(client, db, admin_token, workspace):
    person = make_user(db)
    token = login(client, person.email)
    far = punch_body(lat=float(workspace.latitude) + 0.0018, lng=float(workspace.longitude))

    rejected = client.post(
        "/api/v1/attendance/punch-in", headers=punch_headers(token), json=far
    )
    assert rejected.json()["code"] == "OUTSIDE_GEOFENCE"

    client.patch(
        "/api/v1/admin/workspace",
        headers=auth(admin_token),
        json={"radius_meters": 500},
    )
    accepted = client.post(
        "/api/v1/attendance/punch-in", headers=punch_headers(token), json=far
    )
    assert accepted.status_code == 200


def test_invalid_workspace_settings_are_rejected(client, admin_token, workspace):
    for payload in (
        {"latitude": 120},
        {"radius_meters": 5},
        {"accuracy_threshold_meters": 0},
        {"timezone": "Mars/Olympus"},
    ):
        response = client.patch(
            "/api/v1/admin/workspace", headers=auth(admin_token), json=payload
        )
        assert response.status_code == 422, payload


def test_csv_export_contains_real_rows_only(client, db, admin_token, workspace):
    from app.core.time import local_date, utcnow

    person = make_user(db, name="Reportee")
    token = login(client, person.email)
    client.post("/api/v1/attendance/punch-in", headers=punch_headers(token), json=punch_body())
    client.post("/api/v1/attendance/punch-out", headers=punch_headers(token), json=punch_body())

    today = local_date(utcnow(), workspace.timezone)
    response = client.get(
        f"/api/v1/admin/reports/attendance.csv?from_date={today}&to_date={today}",
        headers=auth(admin_token),
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    lines = [line for line in response.text.strip().splitlines() if line]
    assert lines[0].startswith("Date,User,Member ID")
    assert len(lines) == 2
    assert "Reportee" in lines[1]


def test_csv_export_of_an_empty_range_has_only_a_header(client, admin_token, workspace):
    response = client.get(
        "/api/v1/admin/reports/attendance.csv?from_date=2020-01-01&to_date=2020-01-31",
        headers=auth(admin_token),
    )
    assert response.text.strip().splitlines() == [
        "Date,User,Member ID,First Punch In,Last Punch Out,Total Hours,"
        "Total Duration,Sessions,Status,Late"
    ]


def test_audit_log_records_punches_and_admin_actions(
    client, db, admin, admin_token, workspace
):
    person = make_user(db)
    token = login(client, person.email)
    client.post("/api/v1/attendance/punch-in", headers=punch_headers(token), json=punch_body())
    client.post(
        "/api/v1/attendance/punch-in",
        headers=punch_headers(token),
        json=punch_body(lat=1.0, lng=1.0),
    )

    actions = {row.action for row in db.query(AuditLog).all()}
    assert AuditAction.LOGIN_SUCCESS in actions
    assert AuditAction.PUNCH_IN_SUCCESS in actions

    body = client.get(
        "/api/v1/admin/audit-logs?action=PUNCH_IN_SUCCESS", headers=auth(admin_token)
    ).json()
    assert body["total"] >= 1
    entry = body["items"][0]
    assert entry["metadata"]["distance_m"] is not None
    assert entry["metadata"]["accuracy_m"] is not None


def test_punch_events_expose_verification_detail_to_admins(
    client, db, admin_token, workspace
):
    person = make_user(db)
    token = login(client, person.email)
    client.post("/api/v1/attendance/punch-in", headers=punch_headers(token), json=punch_body())

    body = client.get(
        f"/api/v1/admin/punch-events?user_id={person.id}", headers=auth(admin_token)
    ).json()
    assert body["total"] == 1
    event = body["items"][0]
    assert event["validation_status"] == "ACCEPTED"
    assert event["radius_snapshot"] == workspace.radius_meters
    assert event["distance_meters"] is not None


def test_radius_snapshot_survives_a_later_workspace_change(
    client, db, admin_token, workspace
):
    person = make_user(db)
    token = login(client, person.email)
    client.post("/api/v1/attendance/punch-in", headers=punch_headers(token), json=punch_body())

    client.patch(
        "/api/v1/admin/workspace", headers=auth(admin_token), json={"radius_meters": 900}
    )
    body = client.get(
        f"/api/v1/admin/punch-events?user_id={person.id}", headers=auth(admin_token)
    ).json()
    assert body["items"][0]["radius_snapshot"] == 100
