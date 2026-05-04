"""Notification dispatcher.

Funnels structured events into:
1. The `notifications` DB table (always — visible in /dashboard).
2. Telegram (if configured for the user) for severity >= warn.

Used everywhere — quota exhaustion, trademark hits, first sale, design
review (semi-auto), account paused, lifecycle decisions.

Pure function from the caller's perspective: `dispatch(db, user, kind, ...)`.
The DB write is committed inside this function so callers don't need to
worry about transaction boundaries.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.services.telegram_bot import (
    Severity,
    TelegramConfig,
    format_alert_for,
    send_alert,
)

logger = logging.getLogger(__name__)


def dispatch(
    db: Session,
    *,
    user_id: int,
    kind: str,
    payload: dict[str, Any] | None = None,
    title: str | None = None,
    body: str | None = None,
    severity: Severity | None = None,
    telegram_config: TelegramConfig | None = None,
) -> Notification:
    """Persist a notification and (best-effort) push to Telegram.

    `kind` is a short symbolic name used by the dashboard to render an icon
    and route to a relevant page. Common kinds:
      - quota_exhausted, trademark_hit, first_sale, account_paused,
        design_review, lifecycle_cut, lifecycle_winner, pricing_adjusted,
        warmup_capped, daily_summary
    """
    payload = payload or {}
    if title is None or body is None or severity is None:
        auto_title, auto_body, auto_severity = format_alert_for(kind, payload)
        title = title or auto_title
        body = body or auto_body
        severity = severity or auto_severity

    note = Notification(
        user_id=user_id,
        kind=kind,
        severity=severity,
        title=title,
        body=body,
        payload=payload,
    )
    db.add(note)
    db.commit()
    db.refresh(note)

    # Push to Telegram for warn/critical, plus design_review (interactive).
    push_to_tg = severity in {"warn", "critical"} or kind == "design_review"
    if push_to_tg and telegram_config is not None:
        try:
            send_alert(telegram_config, title=title, body=body, severity=severity)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Telegram dispatch failed for note %s: %s", note.id, exc)

    return note


def list_unread(db: Session, user_id: int, limit: int = 50) -> list[Notification]:
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.read_at.is_(None))
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .all()
    )
