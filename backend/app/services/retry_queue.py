"""Retry queue for transient publish failures.

When :func:`app.workers.pipeline._publish_one` hits a transient platform
error (HTTP 429 rate limit, network blip, 5xx) we don't want to drop the
listing on the floor — the design has already been generated, quality-gated,
upscaled and SEO'd, all of which cost real money. Instead we mark the
``Product`` row as ``status='pending_retry'``, set ``next_retry_at`` to
``now + backoff(retry_count)``, and let a periodic Celery beat task pick
those rows up and re-attempt the publish.

The classifier here intentionally errs on the side of "transient" — false
positives just mean we retry once or twice (cheap), false negatives mean
we lose the listing (expensive). Hard-failure signatures (auth, validation,
trademark, banned shop) are kept on ``status='failed'`` so they never enter
the retry loop.

Backoff schedule (cumulative): 5min → 15min → 1h → 6h → 24h → terminal.
"""
from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta

logger = logging.getLogger(__name__)

# Stages, in order. Each entry is ``(retry_count_threshold, wait)``.
# ``retry_count_threshold`` is the number of *previous* retries already done.
_BACKOFF_LADDER: tuple[tuple[int, timedelta], ...] = (
    (0, timedelta(minutes=5)),
    (1, timedelta(minutes=15)),
    (2, timedelta(hours=1)),
    (3, timedelta(hours=6)),
    (4, timedelta(hours=24)),
)
MAX_RETRIES = len(_BACKOFF_LADDER)


# Signatures that indicate the failure WILL succeed if retried later.
# Order matters — first match wins.
_TRANSIENT_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\b429\b",
        r"\b5\d\d\b",  # 500/502/503/504
        r"\brate[\s_-]?limit",
        r"\btoo many requests\b",
        r"\btimeout\b",
        r"\bconnection (reset|aborted|refused|timed out)\b",
        r"\btemporarily unavailable\b",
        r"\bservice unavailable\b",
        r"\bgateway (timeout|time-out)\b",
        r"\bbad gateway\b",
        r"\bnetwork (error|unreachable)\b",
        r"\bremote disconnected\b",
        r"\bdns (resolution|lookup) (failed|error)\b",
        r"\bssl[:_-]",
        r"\bhttpx\.(read|connect|pool)",  # httpx network errors
    )
)

# Signatures that are clearly NOT transient — hard failures, do not retry.
# These take precedence over transient matches if both fire.
_HARD_FAIL_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\b401\b|\bunauthori[sz]ed\b",
        r"\b403\b|\bforbidden\b",
        r"\binvalid (api|access)?[\s_-]?(key|token)\b",
        r"\baccount (suspended|banned|restricted)\b",
        r"\b(missing|invalid|malformed)\b.*\b(parameter|field|payload|body)\b",
        r"\btrademark\b",
        r"\bcopyright\b",
        r"\bvalidation (failed|error)\b",
        r"\b400\b.*\bbad request\b",
        r"\bunsupported (file|format|content[\s_-]?type)\b",
    )
)


def is_transient(exc: BaseException | str) -> bool:
    """Return True if the error looks like a transient platform issue.

    Hard-failure signatures (auth, validation, trademark) take precedence
    even when they coincidentally contain a transient substring.
    """
    msg = exc if isinstance(exc, str) else str(exc)
    if not msg:
        return False
    for hp in _HARD_FAIL_PATTERNS:
        if hp.search(msg):
            return False
    for tp in _TRANSIENT_PATTERNS:
        if tp.search(msg):
            return True
    return False


def next_backoff(retry_count: int) -> timedelta | None:
    """Return the wait duration before retry attempt ``retry_count + 1``.

    Returns ``None`` once the ladder is exhausted, signalling the caller
    should mark the product ``status='failed_terminal'``.
    """
    for threshold, wait in _BACKOFF_LADDER:
        if retry_count <= threshold:
            return wait
    return None


def schedule_retry(product, exc: BaseException) -> bool:
    """Attempt to schedule another retry for a failed product publish.

    Mutates ``product`` in place. Returns True if a retry was scheduled,
    False if the ladder is exhausted (caller should mark terminal).

    Caller is responsible for ``db.commit()``.
    """
    retry_count = int(product.retry_count or 0)
    wait = next_backoff(retry_count)
    if wait is None:
        return False

    product.status = "pending_retry"
    product.retry_count = retry_count + 1
    product.next_retry_at = datetime.now(UTC) + wait
    product.last_retry_error = str(exc)[:500]
    return True


def mark_terminal(product, exc: BaseException) -> None:
    """Mark a product as having exhausted retries — no further attempts."""
    product.status = "failed_terminal"
    product.next_retry_at = None
    product.error = (str(exc) or product.error or "exhausted retry ladder")[:500]


def mark_published(product) -> None:
    """Clear retry bookkeeping after a successful publish."""
    product.next_retry_at = None
    # Keep retry_count so the dashboard can show "succeeded after N retries".
