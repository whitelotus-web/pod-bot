"""Helper to record audit log entries.

Call :func:`log_action` after a sensitive mutation succeeds. Failure to
record an audit entry MUST NOT break the request — we swallow exceptions
and log a warning so the user-facing operation still succeeds.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session
from starlette.requests import Request

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


def log_action(
    db: Session,
    *,
    user_id: int | None,
    action: str,
    target_type: str,
    target_id: int | None = None,
    request: Request | None = None,
    payload: dict[str, Any] | None = None,
) -> AuditLog | None:
    try:
        ip = None
        ua = None
        if request is not None:
            ip = request.client.host if request.client else None
            ua = request.headers.get("user-agent")
        row = AuditLog(
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            ip_address=ip,
            user_agent=(ua or "")[:255] or None,
            payload=payload,
        )
        db.add(row)
        db.commit()
        return row
    except Exception:  # noqa: BLE001
        logger.exception("Failed to record audit log %s", action)
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return None
