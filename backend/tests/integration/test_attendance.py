from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from tests.conftest import WORKSPACE_LAT, WORKSPACE_LNG, auth, punch_body

from app.core.time import utcnow
from app.models.attendance import AttendanceDay, AttendanceSession
from app.models.enums import SessionStatus, ValidationStatus
from app.models.punch_event import PunchEvent
from app.repositories import attendance_repo
from app.services import attendance_service

PUNCH_IN = "/api/v1/attendance/punch-in"
PUNCH_OUT = "/api/v1/attendance/punch-out"
TODAY = "/api/v1/attendance/today"


def key() -> dict[str, str]:
    return {"Idempotency-Key": uuid.uuid4().hex}


def outside() -> dict:
    return punch_body(lat=WORKSPACE_LAT + 0.01, lng=WORKSPACE_LNG + 0.01)


def test_day_starts_absent(client, user_token, workspace):
    body = client.get(TODAY, headers=auth(user_token)).json()
    assert body["status"] == "ABSENT"
    assert body["sessions"] == []
    assert body["total_seconds"] == 0


def test_punch_in_inside_the_geofence_succeeds(client, user_token, workspace):
    response = client.post(
        PUNCH_IN, headers={**auth(user_token), **key()}, json=punch_body()
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["status"] == "PRESENT"
    assert body["punch_out"] is None
    assert body["verification"]["distance_meters"] < 1


def test_punch_in_outside_the_geofence_is_rejected(client, user_token, workspace):
    response = client.post(
        PUNCH_IN, headers={**auth(user_token), **key()}, json=outside()
    )
    assert response.status_code == 422
    assert response.json()["code"] == "OUTSIDE_GEOFENCE"


def test_punch_in_with_poor_accuracy_is_rejected(client, user_token, workspace):
    response = client.post(
        PUNCH_IN,
        headers={**auth(user_token), **key()},
        json=punch_body(accuracy=150.0),
    )
    assert response.status_code == 422
    assert response.json()["code"] == "ACCURACY_TOO_LOW"


def test_rejected_punch_creates_no_session_but_is_recorded(
    client, user_token, workspace, db, user
):
    client.post(PUNCH_IN, headers={**auth(user_token), **key()}, json=outside())
    assert attendance_repo.get_open_session(db, user.id) is None
    events = db.query(PunchEvent).filter(PunchEvent.user_id == user.id).all()
    assert len(events) == 1
    assert events[0].validation_status == ValidationStatus.REJECTED
    assert events[0].rejection_reason == "OUTSIDE_GEOFENCE"
    assert events[0].distance_meters > 100


def test_duplicate_punch_in_is_rejected(client, user_token, workspace):
    client.post(PUNCH_IN, headers={**auth(user_token), **key()}, json=punch_body())
    second = client.post(
        PUNCH_IN, headers={**auth(user_token), **key()}, json=punch_body()
    )
    assert second.status_code == 409
    assert second.json()["code"] == "ALREADY_PUNCHED_IN"


def test_punch_out_without_an_active_session_is_rejected(client, user_token, workspace):
    response = client.post(
        PUNCH_OUT, headers={**auth(user_token), **key()}, json=punch_body()
    )
    assert response.status_code == 409
    assert response.json()["code"] == "NO_ACTIVE_SESSION"


def test_punch_out_outside_the_geofence_is_rejected(client, user_token, workspace, db, user):
    client.post(PUNCH_IN, headers={**auth(user_token), **key()}, json=punch_body())
    response = client.post(
        PUNCH_OUT, headers={**auth(user_token), **key()}, json=outside()
    )
    assert response.status_code == 422
    assert response.json()["code"] == "OUTSIDE_GEOFENCE"
    # The session stays open: the user is still on the clock.
    assert attendance_repo.get_open_session(db, user.id) is not None


def test_full_cycle_produces_a_completed_session(client, user_token, workspace, db, user):
    client.post(PUNCH_IN, headers={**auth(user_token), **key()}, json=punch_body())
    response = client.post(
        PUNCH_OUT, headers={**auth(user_token), **key()}, json=punch_body()
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "CHECKED_OUT"
    assert body["duration_seconds"] is not None
    assert body["duration_seconds"] >= 0

    session = db.query(AttendanceSession).filter(AttendanceSession.user_id == user.id).one()
    assert session.status == SessionStatus.COMPLETED
    assert session.punch_out is not None


def test_idempotency_key_replays_the_original_result(client, user_token, workspace, db, user):
    headers = {**auth(user_token), **key()}
    first = client.post(PUNCH_IN, headers=headers, json=punch_body())
    second = client.post(PUNCH_IN, headers=headers, json=punch_body())
    assert first.status_code == second.status_code == 200
    assert first.json()["session_id"] == second.json()["session_id"]
    assert db.query(AttendanceSession).filter(AttendanceSession.user_id == user.id).count() == 1


def test_multiple_sessions_in_one_day_accumulate(client, user_token, workspace, db, user):
    for _ in range(2):
        assert client.post(
            PUNCH_IN, headers={**auth(user_token), **key()}, json=punch_body()
        ).status_code == 200
        assert client.post(
            PUNCH_OUT, headers={**auth(user_token), **key()}, json=punch_body()
        ).status_code == 200

    body = client.get(TODAY, headers=auth(user_token)).json()
    assert len(body["sessions"]) == 2
    assert body["status"] == "CHECKED_OUT"

    day = db.query(AttendanceDay).filter(AttendanceDay.user_id == user.id).one()
    assert day.total_seconds == sum(
        s.duration_seconds for s in day.sessions if s.duration_seconds is not None
    )


def test_day_total_is_the_sum_of_session_durations(db, user, workspace):
    """Durations come from server timestamps only; verify the arithmetic."""
    now = utcnow()
    day = attendance_repo.get_or_create_day(db, user.id, now.date())
    for start, end in ((-8 * 3600, -5 * 3600), (-4 * 3600, -1 * 3600)):
        session = AttendanceSession(
            attendance_day_id=day.id,
            user_id=user.id,
            workspace_id=workspace.id,
            punch_in=now + timedelta(seconds=start),
            punch_out=now + timedelta(seconds=end),
            duration_seconds=end - start,
            status=SessionStatus.COMPLETED,
        )
        db.add(session)
    db.flush()
    attendance_repo.recompute_day_totals(db, day)
    db.commit()
    assert day.total_seconds == 6 * 3600
    assert day.status.value == "CHECKED_OUT"


def test_active_session_elapsed_uses_server_time(db, user, workspace):
    now = utcnow()
    day = attendance_repo.get_or_create_day(db, user.id, now.date())
    session = AttendanceSession(
        attendance_day_id=day.id,
        user_id=user.id,
        workspace_id=workspace.id,
        punch_in=now - timedelta(hours=2, minutes=30),
        status=SessionStatus.ACTIVE,
    )
    db.add(session)
    db.commit()

    state = attendance_service.today_state(db, user, workspace, now)
    assert state["state"].value == "PRESENT"
    assert state["active_elapsed_seconds"] == pytest.approx(9000, abs=2)
    assert state["total_seconds"] == pytest.approx(9000, abs=2)


def test_database_forbids_two_open_sessions(db, user, workspace):
    """The partial unique index is the last line of defence against a race."""
    now = utcnow()
    day = attendance_repo.get_or_create_day(db, user.id, now.date())
    for _ in range(2):
        db.add(
            AttendanceSession(
                attendance_day_id=day.id,
                user_id=user.id,
                workspace_id=workspace.id,
                punch_in=now,
                status=SessionStatus.ACTIVE,
            )
        )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_client_supplied_timestamp_never_drives_the_duration(
    client, user_token, workspace, db, user
):
    """A manipulated device clock must not change the recorded attendance."""
    forged = (utcnow() - timedelta(hours=9)).isoformat()
    client.post(
        PUNCH_IN,
        headers={**auth(user_token), **key()},
        json={**punch_body(), "captured_at": forged},
    )
    response = client.post(
        PUNCH_OUT, headers={**auth(user_token), **key()}, json=punch_body()
    )
    assert response.json()["duration_seconds"] < 60

    event = (
        db.query(PunchEvent)
        .filter(PunchEvent.user_id == user.id)
        .order_by(PunchEvent.server_timestamp.asc())
        .first()
    )
    # Stored for forensics, but far from the authoritative server timestamp.
    assert event.client_timestamp is not None
    assert abs((event.server_timestamp - event.client_timestamp).total_seconds()) > 3000


def test_punch_survives_a_refresh_of_the_dashboard(client, user_token, workspace):
    client.post(PUNCH_IN, headers={**auth(user_token), **key()}, json=punch_body())
    first = client.get(TODAY, headers=auth(user_token)).json()
    second = client.get(TODAY, headers=auth(user_token)).json()
    assert first["active_session"]["id"] == second["active_session"]["id"]
    assert second["status"] == "PRESENT"


def test_history_and_summary_reflect_real_sessions(client, user_token, workspace):
    client.post(PUNCH_IN, headers={**auth(user_token), **key()}, json=punch_body())
    client.post(PUNCH_OUT, headers={**auth(user_token), **key()}, json=punch_body())

    history = client.get(
        "/api/v1/attendance/history?period=month", headers=auth(user_token)
    ).json()
    assert len(history["days"]) == 1
    assert history["days"][0]["session_count"] == 1

    summary = client.get(
        "/api/v1/attendance/summary?period=week", headers=auth(user_token)
    ).json()
    assert summary["days_present"] == 1


def test_empty_history_is_an_empty_list_not_placeholder_data(client, user_token, workspace):
    history = client.get(
        "/api/v1/attendance/history?period=month", headers=auth(user_token)
    ).json()
    assert history["days"] == []
    assert history["total_seconds"] == 0


def test_auto_close_caps_a_forgotten_session(db, user, workspace):
    now = utcnow()
    day = attendance_repo.get_or_create_day(db, user.id, (now - timedelta(days=1)).date())
    db.add(
        AttendanceSession(
            attendance_day_id=day.id,
            user_id=user.id,
            workspace_id=workspace.id,
            punch_in=now - timedelta(hours=30),
            status=SessionStatus.ACTIVE,
        )
    )
    db.commit()

    closed = attendance_service.auto_close_stale_sessions(db, now)
    assert closed == 1
    session = db.query(AttendanceSession).filter(AttendanceSession.user_id == user.id).one()
    assert session.status == SessionStatus.AUTO_CLOSED
    assert session.duration_seconds == workspace.auto_close_after_hours * 3600
    assert attendance_repo.get_open_session(db, user.id) is None
