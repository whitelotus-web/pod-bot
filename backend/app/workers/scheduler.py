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
        recovered = 0
        for r in rows:
            # 1) Expire paused_until → drop back to warn so the account becomes
            # publishable again, but keep one degree of caution.
            if r.paused_until and r.paused_until <= now:
                r.paused_until = None
                if r.health_status == "paused":
                    r.health_status = "warn"
                unpaused += 1

            # 2) Auto-recover warn → healthy after 24h of clean activity (no
            # publishes have been blocked, no new pause was issued). We use
            # last_publish_at as the activity signal: if the most recent
            # publish succeeded ≥24h ago and the account isn't currently
            # paused, treat the warn flag as stale.
            #
            # NOTE: must be ``elif`` — otherwise an account that was just
            # transitioned paused→warn in step 1 above would immediately match
            # this branch (warn + paused_until=None + last_publish_at typically
            # ≥24h old because the account was paused) and skip the warn
            # cooling-off period entirely.
            elif (
                r.health_status == "warn"
                and (r.paused_until is None or r.paused_until <= now)
                and r.last_publish_at is not None
                and (now - r.last_publish_at).total_seconds() >= 86400
            ):
                r.health_status = "healthy"
                r.health_note = "Auto-recovered after 24h clean"
                recovered += 1
        db.commit()
        return {"unpaused": unpaused, "recovered": recovered}
    finally:
        db.close()


@celery_app.task(name="app.workers.scheduler.retry_pending_publishes")
def retry_pending_publishes(limit: int = 50) -> dict:
    """Re-attempt publishes that were queued by the retry-queue.

    Picks up ``Product`` rows with ``status='pending_retry'`` and
    ``next_retry_at <= now``, in oldest-first order, and re-runs the
    platform publish call. On success, updates the row in place. On a new
    transient failure, schedules the next backoff step. On a hard failure
    (or after exhausting the ladder) marks the row as ``failed_terminal``.
    """
    from app.models import Design, PlatformAccount, Product
    from app.platforms import get_platform
    from app.services.retry_queue import (
        is_transient,
        mark_published,
        mark_terminal,
        schedule_retry,
    )

    db = SessionLocal()
    try:
        now = datetime.now(UTC)
        rows: list[Product] = (
            db.query(Product)
            .filter(
                Product.status == "pending_retry",
                Product.next_retry_at <= now,
            )
            .order_by(Product.next_retry_at.asc())
            .limit(limit)
            .all()
        )
        attempted = 0
        retried = 0
        succeeded = 0
        terminal = 0
        for p in rows:
            attempted += 1
            account = db.query(PlatformAccount).filter_by(id=p.platform_account_id).first()
            design = db.query(Design).filter_by(id=p.design_id).first() if p.design_id else None
            if account is None or design is None:
                mark_terminal(p, RuntimeError("missing account or design"))
                terminal += 1
                continue
            if account.health_status in ("paused", "banned") or (
                account.paused_until is not None and account.paused_until > now
            ):
                # Don't retry into a paused shop — push the next attempt back
                # one full ladder step so we don't busy-loop.
                schedule_retry(p, RuntimeError(f"account {account.id} still paused"))
                continue
            try:
                from pathlib import Path as _Path

                from app.core.config import settings as _settings

                src_rel = design.upscaled_path or design.bg_removed_path or design.file_path
                design_abs = str(_Path(_settings.media_root) / src_rel)
                adapter = get_platform(account.platform, account)
                res = adapter.publish(
                    design_path=design_abs,
                    title=p.title,
                    description=p.description,
                    tags=p.tags or [],
                    price_usd=p.price_usd,
                    product_type=p.product_type,
                )
                if res.status == "published":
                    p.status = "published"
                    p.external_id = res.external_id
                    p.url = res.url
                    p.error = None
                    p.published_at = datetime.now(UTC)
                    mark_published(p)
                    succeeded += 1
                else:
                    p.error = res.error or "non-published response"
                    p.status = "failed_terminal"
                    terminal += 1
            except Exception as exc:  # noqa: BLE001
                if is_transient(exc) and schedule_retry(p, exc):
                    retried += 1
                else:
                    mark_terminal(p, exc)
                    terminal += 1
        db.commit()
        return {
            "attempted": attempted,
            "succeeded": succeeded,
            "retried": retried,
            "terminal": terminal,
        }
    finally:
        db.close()
