"""Etsy account warm-up scheduler.

Etsy flags shops that publish too many listings too fast as new accounts.
We cap daily publishes per-account based on `account_age_days` (computed from
PlatformAccount.created_at, or overridden by the user if they migrated an
existing account).

Schedule (recommended):
  Week 1 (≤ 7d):       3 / day
  Week 2 (8-14d):      5 / day
  Week 3-4 (15-28d):   8 / day
  Month 2+ (29-60d):  12 / day
  Mature (>60d):      18 / day  (still capped to avoid trigger)

The user can override per-account via `daily_publish_cap_override`.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True)
class WarmupTier:
    name: str
    min_age_days: int
    daily_cap: int


WARMUP_LADDER: tuple[WarmupTier, ...] = (
    WarmupTier("week_1", 0, 3),
    WarmupTier("week_2", 8, 5),
    WarmupTier("weeks_3_4", 15, 8),
    WarmupTier("month_2", 29, 12),
    WarmupTier("mature", 61, 18),
)


def tier_for_age(age_days: int) -> WarmupTier:
    """Pick the highest tier whose min_age_days <= age_days."""
    chosen = WARMUP_LADDER[0]
    for tier in WARMUP_LADDER:
        if age_days >= tier.min_age_days:
            chosen = tier
    return chosen


def account_age_days(created_at: datetime | None, override_days: int | None = None) -> int:
    """Compute account age, with user override taking precedence (e.g. for
    accounts that existed before this app)."""
    if override_days is not None and override_days >= 0:
        return override_days
    if created_at is None:
        return 0
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    delta = datetime.now(UTC) - created_at
    return max(0, delta.days)


def daily_cap(
    *,
    created_at: datetime | None,
    override_days: int | None = None,
    user_override_cap: int | None = None,
) -> int:
    """Resolve the publish cap for an account today."""
    if user_override_cap is not None and user_override_cap > 0:
        return user_override_cap
    return tier_for_age(account_age_days(created_at, override_days)).daily_cap


def remaining_quota(
    *,
    cap: int,
    today_published: int,
) -> int:
    return max(0, cap - today_published)


def can_publish_now(
    *,
    last_publish_at: datetime | None,
    min_spacing_seconds: int = 30,
) -> tuple[bool, int]:
    """Enforce a minimum gap between publishes from the same account.

    Returns (allowed, seconds_to_wait).
    """
    if last_publish_at is None:
        return True, 0
    if last_publish_at.tzinfo is None:
        last_publish_at = last_publish_at.replace(tzinfo=UTC)
    elapsed = (datetime.now(UTC) - last_publish_at).total_seconds()
    if elapsed >= min_spacing_seconds:
        return True, 0
    return False, int(min_spacing_seconds - elapsed)


@dataclass
class PublishDecision:
    allowed: bool
    reason: str = ""
    cap: int = 0
    used_today: int = 0
    next_eligible_at: datetime | None = None


def decide_publish(
    *,
    created_at: datetime | None,
    override_age_days: int | None,
    user_override_cap: int | None,
    today_published: int,
    last_publish_at: datetime | None,
    min_spacing_seconds: int = 30,
) -> PublishDecision:
    """Single decision function used by the publish step.

    The pipeline calls this before each publish; if `allowed=False` it can
    either skip the listing for today, requeue to a future day, or sleep
    `next_eligible_at - now` seconds and retry.
    """
    cap = daily_cap(
        created_at=created_at,
        override_days=override_age_days,
        user_override_cap=user_override_cap,
    )
    if today_published >= cap:
        next_day = datetime.now(UTC).replace(hour=0, minute=5, second=0, microsecond=0) + timedelta(days=1)
        return PublishDecision(
            allowed=False,
            reason=f"Daily cap reached ({today_published}/{cap}); resumes tomorrow.",
            cap=cap,
            used_today=today_published,
            next_eligible_at=next_day,
        )

    ok, wait_s = can_publish_now(
        last_publish_at=last_publish_at, min_spacing_seconds=min_spacing_seconds
    )
    if not ok:
        return PublishDecision(
            allowed=False,
            reason=f"Min spacing not elapsed; wait {wait_s}s.",
            cap=cap,
            used_today=today_published,
            next_eligible_at=datetime.now(UTC) + timedelta(seconds=wait_s),
        )

    return PublishDecision(
        allowed=True,
        cap=cap,
        used_today=today_published,
    )
