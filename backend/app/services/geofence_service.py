"""Server-side geofence validation.

This module is the ONLY authority on whether a punch is inside the workspace.
The client sends raw sensor output (latitude, longitude, accuracy) and nothing
else; distance, validity and the applicable policy are all derived here from
the active workspace row.

Validation order (first failure wins):
    1. coordinates well formed and not the (0,0) "no fix" sentinel
    2. reported accuracy within the configured threshold
    3. great-circle distance from the workspace centre within the radius
    4. movement since the previous accepted punch physically plausible

Boundary policy: the comparison is a strict `distance <= radius` against the
workspace centre, with no padding by the accuracy figure. Padding would widen
the effective fence by up to the accuracy threshold in a way that is invisible
in the admin UI; if a site needs more tolerance the radius is the one knob to
turn.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.core.errors import ErrorCode
from app.models.punch_event import PunchEvent
from app.models.workspace import Workspace
from app.utils.geo import (
    approximate_distance_text,
    haversine_meters,
    is_null_island,
    is_valid_latitude,
    is_valid_longitude,
    speed_kmh,
)


@dataclass(slots=True)
class GeofenceResult:
    accepted: bool
    latitude: float
    longitude: float
    accuracy_meters: float
    distance_meters: float | None
    radius_meters: int
    accuracy_threshold_meters: int
    rejection_code: str | None = None
    message: str | None = None
    flags: dict[str, Any] = field(default_factory=dict)

    @property
    def rejection_reason(self) -> str | None:
        return self.rejection_code


def _reject(
    code: str,
    message: str,
    *,
    latitude: float,
    longitude: float,
    accuracy: float,
    workspace: Workspace,
    distance: float | None = None,
    flags: dict[str, Any] | None = None,
) -> GeofenceResult:
    return GeofenceResult(
        accepted=False,
        latitude=latitude,
        longitude=longitude,
        accuracy_meters=accuracy,
        distance_meters=distance,
        radius_meters=workspace.radius_meters,
        accuracy_threshold_meters=workspace.accuracy_threshold_meters,
        rejection_code=code,
        message=message,
        flags=flags or {},
    )


def validate(
    *,
    workspace: Workspace,
    latitude: float,
    longitude: float,
    accuracy: float,
    now: datetime,
    previous_event: PunchEvent | None = None,
) -> GeofenceResult:
    """Validate one location reading against the active workspace policy."""

    # 1. Structural validity ------------------------------------------------
    if not is_valid_latitude(latitude) or not is_valid_longitude(longitude):
        return _reject(
            ErrorCode.INVALID_COORDINATES,
            "The location reported by your device is not valid. Please try again.",
            latitude=latitude,
            longitude=longitude,
            accuracy=accuracy,
            workspace=workspace,
        )
    if is_null_island(latitude, longitude):
        return _reject(
            ErrorCode.INVALID_COORDINATES,
            "Your device did not return a real location fix. Please try again "
            "in an open area.",
            latitude=latitude,
            longitude=longitude,
            accuracy=accuracy,
            workspace=workspace,
        )
    if accuracy <= 0:
        return _reject(
            ErrorCode.INVALID_COORDINATES,
            "The location reported by your device is not valid. Please try again.",
            latitude=latitude,
            longitude=longitude,
            accuracy=accuracy,
            workspace=workspace,
        )

    # 2. Accuracy gate ------------------------------------------------------
    if accuracy > workspace.accuracy_threshold_meters:
        return _reject(
            ErrorCode.ACCURACY_TOO_LOW,
            "Your location accuracy is currently too low "
            f"({accuracy:.0f} m, maximum allowed {workspace.accuracy_threshold_meters} m). "
            "Enable precise location, move to an open area and try again.",
            latitude=latitude,
            longitude=longitude,
            accuracy=accuracy,
            workspace=workspace,
        )

    # 3. Distance gate ------------------------------------------------------
    distance = haversine_meters(
        latitude, longitude, float(workspace.latitude), float(workspace.longitude)
    )
    if distance > workspace.radius_meters:
        return _reject(
            ErrorCode.OUTSIDE_GEOFENCE,
            "You are outside the authorized workspace area. You are "
            f"{approximate_distance_text(distance)} from the workspace; the allowed "
            f"distance is {workspace.radius_meters} m. Move inside the workspace and "
            "try again.",
            latitude=latitude,
            longitude=longitude,
            accuracy=accuracy,
            workspace=workspace,
            distance=distance,
        )

    # 4. Movement plausibility ---------------------------------------------
    flags: dict[str, Any] = {}
    if previous_event is not None and previous_event.latitude is not None:
        elapsed = (now - previous_event.server_timestamp).total_seconds()
        travelled = haversine_meters(
            float(previous_event.latitude),
            float(previous_event.longitude or 0.0),
            latitude,
            longitude,
        )
        implied = speed_kmh(travelled, elapsed)
        if implied > workspace.max_travel_speed_kmh:
            flags = {
                "implied_speed_kmh": round(implied, 1),
                "previous_event_id": str(previous_event.id),
                "elapsed_seconds": round(elapsed, 1),
                "travelled_meters": round(travelled, 1),
            }
            if workspace.block_impossible_movement:
                return _reject(
                    ErrorCode.IMPOSSIBLE_MOVEMENT,
                    "This punch could not be verified because the movement since "
                    "your previous punch is not physically plausible. Please "
                    "contact your administrator.",
                    latitude=latitude,
                    longitude=longitude,
                    accuracy=accuracy,
                    workspace=workspace,
                    distance=distance,
                    flags=flags,
                )

    return GeofenceResult(
        accepted=True,
        latitude=latitude,
        longitude=longitude,
        accuracy_meters=accuracy,
        distance_meters=distance,
        radius_meters=workspace.radius_meters,
        accuracy_threshold_meters=workspace.accuracy_threshold_meters,
        flags=flags,
    )
