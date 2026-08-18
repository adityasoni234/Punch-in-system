from __future__ import annotations

import math

import pytest

from app.utils.geo import (
    approximate_distance_text,
    haversine_meters,
    is_null_island,
    is_valid_latitude,
    is_valid_longitude,
    speed_kmh,
)

WORKSPACE = (23.0900259, 72.5343615)


def test_distance_to_self_is_zero():
    assert haversine_meters(*WORKSPACE, *WORKSPACE) == pytest.approx(0.0, abs=1e-6)


def test_known_short_distance():
    # 0.001 degrees of latitude is ~111.2 m anywhere on Earth.
    d = haversine_meters(23.0900259, 72.5343615, 23.0910259, 72.5343615)
    assert d == pytest.approx(111.2, abs=1.0)


def test_symmetry():
    a = haversine_meters(23.09, 72.53, 23.10, 72.54)
    b = haversine_meters(23.10, 72.54, 23.09, 72.53)
    assert a == pytest.approx(b, abs=1e-9)


def test_known_long_distance_within_half_percent():
    # London -> Paris, true geodesic ~343.5 km.
    d = haversine_meters(51.5074, -0.1278, 48.8566, 2.3522)
    assert abs(d - 343_500) / 343_500 < 0.005


def test_antimeridian_is_handled():
    d = haversine_meters(0.0, 179.999, 0.0, -179.999)
    assert d < 250  # ~222 m across the line, not half the planet


def test_coordinate_validators():
    assert is_valid_latitude(23.09) and is_valid_latitude(-90) and is_valid_latitude(90)
    assert not is_valid_latitude(90.1)
    assert is_valid_longitude(-180) and is_valid_longitude(180)
    assert not is_valid_longitude(180.1)
    assert is_null_island(0.0, 0.0)
    assert not is_null_island(0.0001, 0.0)


def test_speed_calculation():
    assert speed_kmh(1000, 3600) == pytest.approx(1.0)
    assert math.isinf(speed_kmh(10, 0))
    assert speed_kmh(0, 0) == 0.0


def test_distance_text_is_bucketed():
    assert approximate_distance_text(9) == "less than 25 m"
    assert approximate_distance_text(84) == "approximately 80 m"
    assert approximate_distance_text(6800).endswith("km")
