"""Account health monitor.

Tracks signals per `PlatformAccount` to decide:
- `healthy`: normal operation
- `warn`: error rate elevated; reduce throughput
- `paused`: too many recent errors / API explicitly says shop is under review;
            stop publishing and alert the user
- `banned`: terminal (manual review needed)

This module is **pure logic** — it computes the new status from the inputs
the caller passes (e.g. recent error count from RunLog). The actual
DB-update + notification dispatch is done by the caller.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

HealthStatus = Literal["healthy", "warn", "paused", "banned"]


@dataclass
class HealthInputs:
    recent_errors: int = 0  # last 1 hour
    recent_publish_attempts: int = 0  # last 1 hour
    recent_429s: int = 0  # last 24 hours
    explicit_review_flag: bool = False  # platform API said "shop under review"
    account_age_days: int = 0


@dataclass
class HealthDecision:
    status: HealthStatus
    note: str
    paused_until: datetime | None = None


def evaluate(inputs: HealthInputs) -> HealthDecision:
    """Map signals to a status."""
    if inputs.explicit_review_flag:
        return HealthDecision(
            status="paused",
            note="Platform flagged the shop for review; pausing all publishes for 24h.",
            paused_until=datetime.now(UTC) + timedelta(hours=24),
        )

    if inputs.recent_429s >= 5:
        return HealthDecision(
            status="paused",
            note=f"{inputs.recent_429s} rate-limit hits in 24h; pausing 6h.",
            paused_until=datetime.now(UTC) + timedelta(hours=6),
        )

    if inputs.recent_publish_attempts > 0:
        error_rate = inputs.recent_errors / max(1, inputs.recent_publish_attempts)
        if error_rate >= 0.5 and inputs.recent_errors >= 3:
            return HealthDecision(
                status="paused",
                note=f"{inputs.recent_errors}/{inputs.recent_publish_attempts} publishes failed in last hour; pausing 1h.",
                paused_until=datetime.now(UTC) + timedelta(hours=1),
            )
        if error_rate >= 0.2 and inputs.recent_errors >= 2:
            return HealthDecision(
                status="warn",
                note=f"Elevated error rate ({error_rate:.0%}) in last hour.",
            )

    # Newer accounts get a softer warn band — they're more vulnerable.
    if inputs.account_age_days < 14 and inputs.recent_429s >= 2:
        return HealthDecision(
            status="warn",
            note=f"New account ({inputs.account_age_days}d) hit rate limits — slow down.",
        )

    return HealthDecision(status="healthy", note="OK")


def link_correlation_signal(
    accounts_recent_errors: Iterable[tuple[int, int]],
) -> bool:
    """Detect if multiple accounts are erroring simultaneously — likely an
    Etsy "linked accounts" detection event.

    `accounts_recent_errors`: list of (account_id, recent_errors_in_last_15m).
    Returns True if 2+ accounts are erroring with similar patterns.
    """
    affected = [a for a in accounts_recent_errors if a[1] >= 2]
    return len(affected) >= 2
