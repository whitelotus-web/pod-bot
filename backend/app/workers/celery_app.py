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

# Periodic scheduler: every 5 minutes check for campaigns whose cron is due
celery_app.conf.beat_schedule = {
    "check-scheduled-campaigns": {
        "task": "app.workers.scheduler.tick",
        "schedule": crontab(minute="*/5"),
    },
}
