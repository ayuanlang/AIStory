"""In-process Asia/Shanghai 03:00 daily maintenance scheduler."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from app.core.config import settings
from app.core.time_utils import BEIJING_TZ, now_bj
from app.jobs.maintenance import already_ran_today, run_daily_maintenance

logger = logging.getLogger(__name__)

_MAINTENANCE_HOUR = 3
_MAINTENANCE_MINUTE = 0


def seconds_until_next_run(now: Optional[datetime] = None) -> float:
    current = now or now_bj()
    if current.tzinfo is None:
        current = current.replace(tzinfo=BEIJING_TZ)
    else:
        current = current.astimezone(BEIJING_TZ)

    target = current.replace(
        hour=_MAINTENANCE_HOUR,
        minute=_MAINTENANCE_MINUTE,
        second=0,
        microsecond=0,
    )
    if current >= target:
        target = target + timedelta(days=1)
    return max(1.0, (target - current).total_seconds())


def should_catch_up_missed_run(now: Optional[datetime] = None) -> bool:
    """If process starts after 03:00 and today's job has not run, catch up once."""
    current = now or now_bj()
    if current.tzinfo is None:
        current = current.replace(tzinfo=BEIJING_TZ)
    else:
        current = current.astimezone(BEIJING_TZ)
    if already_ran_today():
        return False
    todays_slot = current.replace(
        hour=_MAINTENANCE_HOUR,
        minute=_MAINTENANCE_MINUTE,
        second=0,
        microsecond=0,
    )
    return current >= todays_slot


async def maintenance_scheduler_loop(stop_event: asyncio.Event) -> None:
    logger.info(
        "Maintenance scheduler started | timezone=Asia/Shanghai hour=%02d:%02d backup_keep=%s billing_reconcile_days=%s (project retention is manual)",
        _MAINTENANCE_HOUR,
        _MAINTENANCE_MINUTE,
        settings.DB_BACKUP_KEEP_COUNT,
        getattr(settings, "BILLING_RECONCILE_LOOKBACK_DAYS", 3),
    )
    # Catch up if the web process was down during the 03:00 window.
    if should_catch_up_missed_run():
        logger.info("Maintenance catch-up: running missed daily job for today")
        try:
            await asyncio.to_thread(run_daily_maintenance)
        except Exception:
            logger.exception("Maintenance catch-up failed")

    while not stop_event.is_set():
        delay = seconds_until_next_run()
        logger.info("Maintenance scheduler sleeping %.0fs until next 03:00 Asia/Shanghai", delay)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=delay)
            break
        except asyncio.TimeoutError:
            pass
        if stop_event.is_set():
            break
        try:
            await asyncio.to_thread(run_daily_maintenance)
        except Exception:
            logger.exception("Scheduled daily maintenance failed")
    logger.info("Maintenance scheduler stopped")
