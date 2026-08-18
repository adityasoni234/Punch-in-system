"""Geographic distance maths.

Haversine on a sphere of the IUGG mean Earth radius. Compared with a full
WGS-84 geodesic (Vincenty/Karney) the error is under ~0.5 %, i.e. well below
half a metre on a 100 m geofence and far below any consumer GPS noise floor,
so the extra dependency is not justified.
"""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_METERS = 6_371_008.8

MIN_LATITUDE, MAX_LATITUDE = -90.0, 90.0
MIN_LONGITUDE, MAX_LONGITUDE = -180.0, 180.0


def is_valid_latitude(value: float) -> bool:
    return MIN_LATITUDE <= value <= MAX_LATITUDE


def is_valid_longitude(value: float) -> bool:
    return MIN_LONGITUDE <= value <= MAX_LONGITUDE


def is_null_island(latitude: float, longitude: float) -> bool:
    """(0, 0) is in the Gulf of Guinea and is the classic 'no fix' sentinel."""
    return abs(latitude) < 1e-9 and abs(longitude) < 1e-9


def haversine_meters(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Great-circle distance between two WGS-84 points, in metres."""
    phi1, phi2 = radians(lat1), radians(lat2)
    d_phi = radians(lat2 - lat1)
    d_lambda = radians(lon2 - lon1)

    a = sin(d_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(d_lambda / 2) ** 2
    # asin form is numerically stable for the very small distances we deal with.
    return 2 * EARTH_RADIUS_METERS * asin(min(1.0, sqrt(a)))


def speed_kmh(distance_meters: float, seconds: float) -> float:
    """Average speed implied by moving `distance_meters` in `seconds`."""
    if seconds <= 0:
        return float("inf") if distance_meters > 0 else 0.0
    return (distance_meters / seconds) * 3.6


def approximate_distance_text(distance_meters: float) -> str:
    """Coarse, user-facing distance.

    Deliberately bucketed: an ordinary user is told roughly how far away they
    are so they can act on it, without the API becoming a precise
    range-finder to the geofence edge.
    """
    d = max(0.0, distance_meters)
    if d < 25:
        return "less than 25 m"
    if d < 1000:
        return f"approximately {int(round(d / 10.0) * 10)} m"
    return f"approximately {d / 1000:.1f} km"
