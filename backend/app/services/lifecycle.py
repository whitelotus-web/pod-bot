"""Product lifecycle automation — cut-loss + duplicate winners.

Inputs are Product rows with synced metrics (views, clicks, orders, ctr,
revenue). Decisions:

- **CUT**: 30+ days old, views ≥ threshold, CTR < threshold, no orders
  → recommend delisting. The pipeline can either delist via platform API or
  just mark `lifecycle_stage="archived"` so it doesn't drag down shop SEO.
- **WINNER**: 14+ days old, CTR > threshold AND orders ≥ threshold
  → recommend duplicating: regenerate 5-10 variants of the same prompt with
  color/style tweaks, expand to additional product types.
- **NEUTRAL**: keep monitoring.

The actual "duplicate" action is just pipeline.duplicate_design_variants()
which receives the source design + variant count.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

DecisionKind = Literal["cut", "winner", "neutral"]


@dataclass
class LifecycleThresholds:
    cut_age_days: int = 30
    cut_min_views: int = 200
    cut_max_ctr: float = 0.01  # 1%
    cut_max_orders: int = 0

    winner_age_days: int = 14
    winner_min_ctr: float = 0.03  # 3%
    winner_min_orders: int = 1


@dataclass
class LifecycleDecision:
    kind: DecisionKind
    reason: str = ""
    suggested_variants: int = 0


def _age_days(published_at: datetime | None, now: datetime | None = None) -> int:
    if published_at is None:
        return 0
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=UTC)
    now = now or datetime.now(UTC)
    return max(0, (now - published_at).days)


def evaluate_product(
    *,
    published_at: datetime | None,
    views: int,
    clicks: int,
    orders: int,
    ctr: float | None = None,
    revenue_usd: float = 0.0,
    thresholds: LifecycleThresholds | None = None,
) -> LifecycleDecision:
    """Apply lifecycle rules to a single product's metrics."""
    th = thresholds or LifecycleThresholds()
    age = _age_days(published_at)
    actual_ctr = ctr if ctr is not None else (clicks / views if views else 0.0)

    # Winner rule first — even if listing is old, a winner stays.
    if (
        age >= th.winner_age_days
        and actual_ctr >= th.winner_min_ctr
        and orders >= th.winner_min_orders
    ):
        # Suggested variants scale with revenue.
        if revenue_usd >= 200:
            variants = 10
        elif revenue_usd >= 50:
            variants = 7
        else:
            variants = 5
        return LifecycleDecision(
            kind="winner",
            reason=(
                f"Age {age}d, CTR {actual_ctr:.2%} ≥ {th.winner_min_ctr:.0%}, "
                f"{orders} orders, ${revenue_usd:.0f} revenue."
            ),
            suggested_variants=variants,
        )

    # Cut-loss rule.
    if (
        age >= th.cut_age_days
        and views >= th.cut_min_views
        and actual_ctr <= th.cut_max_ctr
        and orders <= th.cut_max_orders
    ):
        return LifecycleDecision(
            kind="cut",
            reason=(
                f"Age {age}d with {views} views, CTR {actual_ctr:.2%} ≤ "
                f"{th.cut_max_ctr:.0%}, {orders} orders."
            ),
        )

    return LifecycleDecision(kind="neutral", reason=f"Age {age}d, holding.")


def shop_health_score(
    products_metrics: list[tuple[int, int]],
) -> tuple[float, str]:
    """Aggregate avg CTR across the shop.

    products_metrics: list of (views, clicks). Returns (avg_ctr, advisory).
    """
    if not products_metrics:
        return 0.0, "no listings"
    total_views = sum(v for v, _ in products_metrics)
    total_clicks = sum(c for _, c in products_metrics)
    if total_views == 0:
        return 0.0, "no impressions yet"
    ctr = total_clicks / total_views
    if ctr < 0.005:
        return ctr, "shop CTR < 0.5% — pause new listings, consolidate winners"
    if ctr < 0.015:
        return ctr, "shop CTR low — focus on optimizing existing listings"
    if ctr > 0.04:
        return ctr, "excellent shop health — safe to scale"
    return ctr, "healthy"
