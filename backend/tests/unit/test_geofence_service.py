from __future__ import annotations

from datetime import time, timedelta

import pytest

from app.core.errors import ErrorCode
from app.core.time import utcnow
from app.models.punch_event import PunchEvent
from app.models.workspace import Workspace
from app.services import geofence_service
from app.utils.geo import haversine_meters

LAT, LNG = 23.0900259, 72.5343615


def make_workspace(**overrides) -> Workspace:
    defaults = dict(
        name="WS",
        latitude=LAT,
        longitude=LNG,
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
    defaults.update(overrides)
    return Workspace(**defaults)


def offset_lat(meters: float) -> float:
    """A latitude approximately `meters` north of the workspace centre."""
    return LAT + meters / 111_132.0


def lat_at_distance(meters: float) -> float:
    """Latitude whose great-circle distance from the centre is exactly `meters`.

    Bisection rather than the flat-earth approximation, so boundary tests
    exercise the real comparison instead of a fixture rounding error.
    """
    low, high = LAT, LAT + 1.0
    for _ in range(200):
        mid = (low + high) / 2
        if haversine_meters(mid, LNG, LAT, LNG) < meters:
            low = mid
        else:
            high = mid
    return low


def validate(lat, lng, accuracy, workspace=None, previous=None):
    return geofence_service.validate(
        workspace=workspace or make_workspace(),
        latitude=lat,
        longitude=lng,
        accuracy=accuracy,
        now=utcnow(),
        previous_event=previous,
    )


def test_exact_centre_is_accepted():
    result = validate(LAT, LNG, 10.0)
    assert result.accepted
    assert result.distance_meters == pytest.approx(0.0, abs=0.01)


def test_well_inside_is_accepted():
    result = validate(offset_lat(50), LNG, 12.0)
    assert result.accepted
    assert 45 < result.distance_meters < 55


def test_outside_is_rejected():
    result = validate(offset_lat(250), LNG, 10.0)
    assert not result.accepted
    assert result.rejection_code == ErrorCode.OUTSIDE_GEOFENCE
    assert result.distance_meters > 100


def test_boundary_just_inside_is_accepted():
    result = validate(offset_lat(99.0), LNG, 10.0)
    assert result.accepted


def test_boundary_just_outside_is_rejected():
    result = validate(offset_lat(101.0), LNG, 10.0)
    assert not result.accepted
    assert result.rejection_code == ErrorCode.OUTSIDE_GEOFENCE


def test_boundary_exactly_at_radius_is_accepted():
    """Policy is `distance <= radius`, so the fence line itself is inside."""
    lat = lat_at_distance(100.0)
    distance = haversine_meters(lat, LNG, LAT, LNG)
    assert distance <= 100.0 and 100.0 - distance < 1e-6
    assert validate(lat, LNG, 10.0).accepted


def test_one_centimetre_outside_the_radius_is_rejected():
    lat = lat_at_distance(100.01)
    assert not validate(lat, LNG, 10.0).accepted


def test_accuracy_above_threshold_is_rejected_even_at_the_centre():
    result = validate(LAT, LNG, 120.0)
    assert not result.accepted
    assert result.rejection_code == ErrorCode.ACCURACY_TOO_LOW


def test_accuracy_exactly_at_threshold_is_accepted():
    assert validate(LAT, LNG, 50.0).accepted


def test_accuracy_is_checked_before_distance():
    # Poor accuracy AND far away -> the accuracy message is the actionable one.
    result = validate(offset_lat(5000), LNG, 500.0)
    assert result.rejection_code == ErrorCode.ACCURACY_TOO_LOW


def test_null_island_is_rejected():
    result = validate(0.0, 0.0, 5.0)
    assert not result.accepted
    assert result.rejection_code == ErrorCode.INVALID_COORDINATES


def test_out_of_range_coordinates_are_rejected():
    assert validate(95.0, LNG, 5.0).rejection_code == ErrorCode.INVALID_COORDINATES
    assert validate(LAT, 200.0, 5.0).rejection_code == ErrorCode.INVALID_COORDINATES


def test_non_positive_accuracy_is_rejected():
    assert validate(LAT, LNG, 0.0).rejection_code == ErrorCode.INVALID_COORDINATES


def test_configurable_radius_changes_the_verdict():
    far = offset_lat(250)
    assert not validate(far, LNG, 10.0).accepted
    wide = make_workspace(radius_meters=500)
    assert validate(far, LNG, 10.0, workspace=wide).accepted


def test_configurable_accuracy_threshold_changes_the_verdict():
    assert not validate(LAT, LNG, 80.0).accepted
    lenient = make_workspace(accuracy_threshold_meters=100)
    assert validate(LAT, LNG, 80.0, workspace=lenient).accepted


def _previous_event(lat: float, lng: float, seconds_ago: int) -> PunchEvent:
    return PunchEvent(
        latitude=lat,
        longitude=lng,
        server_timestamp=utcnow() - timedelta(seconds=seconds_ago),
    )


def test_impossible_movement_is_flagged_but_not_blocked_by_default():
    previous = _previous_event(19.0760, 72.8777, 60)  # Mumbai, one minute ago
    result = validate(LAT, LNG, 10.0, previous=previous)
    assert result.accepted
    assert result.flags["implied_speed_kmh"] > 300


def test_impossible_movement_blocks_when_configured():
    workspace = make_workspace(block_impossible_movement=True)
    previous = _previous_event(19.0760, 72.8777, 60)
    result = validate(LAT, LNG, 10.0, workspace=workspace, previous=previous)
    assert not result.accepted
    assert result.rejection_code == ErrorCode.IMPOSSIBLE_MOVEMENT


def test_plausible_movement_is_not_flagged():
    previous = _previous_event(LAT, LNG, 3600)
    result = validate(offset_lat(30), LNG, 10.0, previous=previous)
    assert result.accepted
    assert result.flags == {}
