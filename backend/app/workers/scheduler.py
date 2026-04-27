"""Cron-based scheduler: checks every 5 min if any campaign's cron is due."""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from app.core.db import SessionLocal
from app.models import Campaign
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.scheduler.tick")
def tick() -> dict:
    """For each active campaign with a cron, trigger pipeline if due."""
    from croniter import croniter  # lazy import; fallback below if unavailable

    db = SessionLocal()
    try:
        now = datetime.now(UTC)
        due: list[int] = []
        campaigns = (
            db.query(Campaign)
            .filter(Campaign.is_active.is_(True), Campaign.schedule_cron.isnot(None))
            .all()
        )
        for c in campaigns:
            try:
                base = c.last_run_at or (now - timedelta(days=365))
                if base.tzinfo is None:
                    base = base.replace(tzinfo=UTC)
                it = croniter(c.schedule_cron, base)
                next_run = it.get_next(datetime)
                if next_run <= now:
                    due.append(c.id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Cron parse failed for campaign %s: %s", c.id, exc)

        for cid in due:
            celery_app.send_task("app.workers.pipeline.run_campaign", args=[cid])
        return {"scheduled": due}
    finally:
        db.close()
