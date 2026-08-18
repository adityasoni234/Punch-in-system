#!/usr/bin/env python
"""Scheduled maintenance.

Run from cron / a systemd timer, e.g. every 15 minutes:

    python -m app.jobs.maintenance

Tasks
    auto-close   close sessions left open beyond the configured cutoff
    purge        drop stored coordinates past the retention window and sweep
                 expired refresh tokens and rate-limit windows
"""

from __future__ import annotations

import sys
from datetime import timedelta

from sqlalchemy import update

from app.core.config import settings
from app.core.logging import get_logger
from app.core.time import utcnow
from app.db.session import session_scope
from app.models.punch_event import PunchEvent
from app.repositories import token_repo
from app.services import attendance_service, rate_limit

logger = get_logger(__name__)


def purge_location_data() -> int:
    """Erase coordinates older than the retention window.

    The attendance record and the accept/reject verdict are kept forever; only
    the precise latitude/longitude are dropped, which is all that is personally
    sensitive.
    """
    cutoff = utcnow() - timedelta(days=settings.location_retention_days)
    with session_scope() as db:
        result = db.execute(
            update(PunchEvent)
            .where(
                PunchEvent.server_timestamp < cutoff,
                PunchEvent.location_purged.is_(False),
            )
            .values(
                latitude=None,
                longitude=None,
                location_purged=True,
            )
        )
        return result.rowcount or 0


def main() -> int:
    with session_scope() as db:
        closed = attendance_service.auto_close_stale_sessions(db)
    purged = purge_location_data()
    with session_scope() as db:
        tokens = token_repo.purge_expired(db)
        buckets = rate_limit.purge_expired(db)

    logger.info(
        "maintenance: auto_closed=%d locations_purged=%d tokens_purged=%d "
        "rate_buckets_purged=%d",
        closed,
        purged,
        tokens,
        buckets,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
