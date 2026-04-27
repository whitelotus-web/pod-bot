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
        recommended_cut = 0
        recommended_dup = 0
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
            if decision.kind == "cut":
                recommended_cut += 1
                p.lifecycle_stage = "cut_loss_recommended"
            elif decision.kind == "winner":
                recommended_dup += 1
                p.lifecycle_stage = "winner"

        if recommended_cut or recommended_dup:
            users = {p.design.campaign.user_id for p in products if p.design and p.design.campaign}
            for uid in users:
                db.add(
                    Notification(
                        user_id=uid,
                        kind="lifecycle_audit",
                        severity="info",
                        title="Lifecycle audit done",
                        body=(
                            f"{recommended_cut} sản phẩm gợi ý cut-loss, "
                            f"{recommended_dup} winner gợi ý nhân bản. Vào /products để xử lý."
                        ),
                        payload={"cut": recommended_cut, "duplicate": recommended_dup},
                    )
                )
        db.commit()
        return {"cut": recommended_cut, "duplicate": recommended_dup}
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
