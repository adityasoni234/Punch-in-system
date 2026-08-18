#!/usr/bin/env python
"""Create or update the active workspace (geofence) configuration.

This is configuration, not fake data: it writes the real coordinates of the
physical workspace. Everything it sets can afterwards be changed by an admin
from the app, with no code change and no redeploy.

    python -m scripts.seed_workspace \
        --name "Head Office" --lat 23.0900259 --lng 72.5343615 \
        --radius 100 --accuracy 50 --timezone Asia/Kolkata
"""

from __future__ import annotations

import argparse
import sys
from datetime import time

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))

from app.core.time import is_valid_timezone  # noqa: E402
from app.db.session import session_scope  # noqa: E402
from app.models.workspace import Workspace  # noqa: E402
from app.repositories import workspace_repo  # noqa: E402

DEFAULTS = {
    "name": "Main Workspace",
    "lat": 23.0900259,
    "lng": 72.5343615,
    "radius": 100,
    "accuracy": 50,
    "timezone": "Asia/Kolkata",
    "start": "09:30",
    "late": 15,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed or update the active workspace")
    parser.add_argument("--name", default=DEFAULTS["name"])
    parser.add_argument("--lat", type=float, default=DEFAULTS["lat"])
    parser.add_argument("--lng", type=float, default=DEFAULTS["lng"])
    parser.add_argument("--radius", type=int, default=DEFAULTS["radius"],
                        help="Geofence radius in metres")
    parser.add_argument("--accuracy", type=int, default=DEFAULTS["accuracy"],
                        help="Maximum acceptable GPS accuracy in metres")
    parser.add_argument("--timezone", default=DEFAULTS["timezone"])
    parser.add_argument("--start", default=DEFAULTS["start"], help="HH:MM")
    parser.add_argument("--late", type=int, default=DEFAULTS["late"],
                        help="Late threshold in minutes after the start time")
    parser.add_argument("--auto-close-hours", type=int, default=16)
    parser.add_argument("--force", action="store_true",
                        help="Overwrite the existing active workspace")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not is_valid_timezone(args.timezone):
        print(f"error: unknown timezone {args.timezone!r}", file=sys.stderr)
        return 2
    hour, _, minute = args.start.partition(":")
    start_time = time(int(hour), int(minute))

    with session_scope() as db:
        existing = workspace_repo.get_active(db)
        if existing and not args.force:
            print(
                f"An active workspace already exists: {existing.name} "
                f"({existing.latitude}, {existing.longitude}) r={existing.radius_meters}m\n"
                "Re-run with --force to overwrite, or edit it from the admin app."
            )
            return 0

        target = existing or Workspace()
        target.name = args.name
        target.latitude = args.lat
        target.longitude = args.lng
        target.radius_meters = args.radius
        target.accuracy_threshold_meters = args.accuracy
        target.timezone = args.timezone
        target.attendance_start_time = start_time
        target.late_threshold_minutes = args.late
        target.auto_close_after_hours = args.auto_close_hours
        target.max_travel_speed_kmh = 300
        target.block_impossible_movement = False
        target.active = True
        if existing is None:
            db.add(target)
        db.flush()
        print(
            "Workspace configured:\n"
            f"  name      {target.name}\n"
            f"  centre    {target.latitude}, {target.longitude}\n"
            f"  radius    {target.radius_meters} m\n"
            f"  accuracy  <= {target.accuracy_threshold_meters} m\n"
            f"  timezone  {target.timezone}\n"
            f"  start     {target.attendance_start_time} (+{target.late_threshold_minutes}m late)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
