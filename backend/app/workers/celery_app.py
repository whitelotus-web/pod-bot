"""Celery application + beat schedule loader."""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "podbot",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.pipeline", "app.workers.scheduler"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_max_tasks_per_child=50,
    broker_connection_retry_on_startup=True,
)

# Periodic scheduler — see docs/deploy.md for what each job does.
# All times are UTC (Etsy seller dashboards mostly run on UTC).
celery_app.conf.beat_schedule = {
    # Every 5 min: dispatch any user-scheduled campaign whose cron is due.
    "check-scheduled-campaigns": {
        "task": "app.workers.scheduler.tick",
        "schedule": crontab(minute="*/5"),
    },
    # 12:00 UTC daily: lifecycle audit (cut-loss + duplicate-winner recommendations).
    "lifecycle-audit-daily": {
        "task": "app.workers.scheduler.lifecycle_audit",
        "schedule": crontab(hour=12, minute=0),
    },
    # Hourly: sweep paused accounts whose pause window has expired.
    "account-health-sweep-hourly": {
        "task": "app.workers.scheduler.account_health_sweep",
        "schedule": crontab(minute=15),
    },
    # Every 10 min: re-attempt publishes that hit a transient platform error
    # (429 / 5xx / network blip) and were parked in the retry-queue.
    "retry-pending-publishes": {
        "task": "app.workers.scheduler.retry_pending_publishes",
        "schedule": crontab(minute="*/10"),
    },
}
