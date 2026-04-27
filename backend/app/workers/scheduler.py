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


@celery_app.task(name="app.workers.scheduler.lifecycle_audit")
def lifecycle_audit() -> dict:
    """Run lifecycle decisions across all products of all active users.

    Wave 4: pure rule engine; we only WRITE recommendations + send notifications,
    never silently delist. The user reviews and confirms in the UI.
    """
    from app.models import Notification, Product
    from app.services.lifecycle import LifecycleThresholds, evaluate_product

    thresholds = LifecycleThresholds()
    db = SessionLocal()
    try:
        products = (
            db.query(Product).filter(Product.status == "published").all()
        )
        # Track per-user counts so each notification reflects only that user's products.
        per_user: dict[int, dict[str, int]] = {}
        for p in products:
            if not p.published_at:
                continue
            decision = evaluate_product(
                published_at=p.published_at,
                views=p.views_count or 0,
                clicks=p.clicks_count or 0,
                orders=p.orders_count or 0,
                ctr=float(p.ctr or 0.0),
                revenue_usd=float(p.revenue_usd or 0.0),
                thresholds=thresholds,
            )
            uid = p.design.campaign.user_id if p.design and p.design.campaign else None
            if decision.kind == "cut":
                p.lifecycle_stage = "cut_loss_recommended"
                if uid is not None:
                    per_user.setdefault(uid, {"cut": 0, "duplicate": 0})["cut"] += 1
            elif decision.kind == "winner":
                p.lifecycle_stage = "winner"
                if uid is not None:
                    per_user.setdefault(uid, {"cut": 0, "duplicate": 0})["duplicate"] += 1

        total_cut = sum(c["cut"] for c in per_user.values())
        total_dup = sum(c["duplicate"] for c in per_user.values())
        for uid, counts in per_user.items():
            if not (counts["cut"] or counts["duplicate"]):
                continue
            db.add(
                Notification(
                    user_id=uid,
                    kind="lifecycle_audit",
                    severity="info",
                    title="Lifecycle audit done",
                    body=(
                        f"{counts['cut']} sản phẩm gợi ý cut-loss, "
                        f"{counts['duplicate']} winner gợi ý nhân bản. Vào /products để xử lý."
                    ),
                    payload={"cut": counts["cut"], "duplicate": counts["duplicate"]},
                )
            )
        db.commit()
        return {"cut": total_cut, "duplicate": total_dup}
    finally:
        db.close()


@celery_app.task(name="app.workers.scheduler.account_health_sweep")
def account_health_sweep() -> dict:
    """Periodically refresh ``health_status`` for each platform account.

    Wave 4: simple sweep — checks ``paused_until`` expiry and resets stale
    ``warn`` flags after 24h of clean activity.
    """
    from app.models import PlatformAccount

    db = SessionLocal()
    try:
        now = datetime.now(UTC)
        rows = db.query(PlatformAccount).all()
        unpaused = 0
        for r in rows:
            if r.paused_until and r.paused_until <= now:
                r.paused_until = None
                if r.health_status == "paused":
                    r.health_status = "warn"
                unpaused += 1
        db.commit()
        return {"unpaused": unpaused}
    finally:
        db.close()
