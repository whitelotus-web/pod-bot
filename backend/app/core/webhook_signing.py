"""Webhook signature verification helpers for Etsy + Printify.

Both platforms sign outgoing webhooks with HMAC-SHA256 over the raw
request body keyed off a shop-secret. Verifying every webhook before
mutating local state prevents an attacker from forging fake order /
refund events that would corrupt P&L.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os

logger = logging.getLogger(__name__)


def _safe_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def verify_etsy_webhook(body: bytes, signature_header: str | None) -> bool:
    """Verify ``X-Etsy-Signature`` HMAC-SHA256 over raw body.

    Etsy delivers the signature in the form ``sha256=<hex>``. If
    ``ETSY_WEBHOOK_SECRET`` env is unset (dev mode), we log a warning
    and accept the request — but in production the secret MUST be set.
    """
    secret = os.getenv("ETSY_WEBHOOK_SECRET", "").strip()
    if not secret:
        if os.getenv("ENVIRONMENT") == "production":
            logger.error("ETSY_WEBHOOK_SECRET not set in production — rejecting")
            return False
        logger.warning("ETSY_WEBHOOK_SECRET unset; accepting webhook in dev mode")
        return True
    if not signature_header:
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    received = signature_header.split("=", 1)[-1].strip().lower()
    return _safe_compare(expected, received)


def verify_printify_webhook(body: bytes, signature_header: str | None) -> bool:
    """Verify ``X-Pfy-Signature`` HMAC-SHA256 over raw body.

    Printify uses a per-shop signing secret you set when creating the
    webhook. Fall-through behaviour mirrors :func:`verify_etsy_webhook`.
    """
    secret = os.getenv("PRINTIFY_WEBHOOK_SECRET", "").strip()
    if not secret:
        if os.getenv("ENVIRONMENT") == "production":
            logger.error("PRINTIFY_WEBHOOK_SECRET not set in production — rejecting")
            return False
        logger.warning("PRINTIFY_WEBHOOK_SECRET unset; accepting webhook in dev mode")
        return True
    if not signature_header:
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    received = signature_header.strip().lower()
    return _safe_compare(expected, received)
