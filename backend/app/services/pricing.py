"""Dynamic pricing engine — price isn't a static number.

Three rule families:

1. **high_momentum**: when a design is a confirmed winner (CTR > 3% +
   orders ≥ 1) and momentum is rising, bump price by `delta_usd` /
   `delta_percent` to capture more margin.
2. **weekend_flash**: every weekend (Fri evening → Sun midnight) drop price
   by `delta_percent`, automatically restored on Monday. Creates urgency.
3. **low_ctr_discount**: if a listing has high views but low CTR, try a one-time
   discount to test if price was the friction.

All rules respect `min_price_usd` and `max_price_usd` floors from the rule
config so we never go below margin.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time
from typing import Literal

RuleTrigger = Literal["high_momentum", "weekend_flash", "low_ctr_discount"]


@dataclass
class PricingDecision:
    new_price_usd: float
    rule_id: int | None = None
    rule_name: str = ""
    reason: str = ""
    revert_at: datetime | None = None  # only set for time-bound rules like flash sale


@dataclass
class PricingRuleConfig:
    """In-memory mirror of the DB row (avoids importing models in pure logic)."""

    id: int
    name: str
    trigger: RuleTrigger
    delta_usd: float = 0.0
    delta_percent: float = 0.0
    min_price_usd: float = 0.0
    max_price_usd: float | None = None
    is_active: bool = True


def _is_weekend(now: datetime) -> bool:
    """Friday 18:00 UTC → Monday 04:00 UTC."""
    weekday = now.weekday()  # Mon=0
    if weekday == 4 and now.time() >= time(18, 0):
        return True
    if weekday in (5, 6):
        return True
    if weekday == 0 and now.time() < time(4, 0):
        return True
    return False


def _clamp(value: float, lo: float, hi: float | None) -> float:
    value = max(lo, value)
    if hi is not None:
        value = min(hi, value)
    return value


def _next_monday_4am(now: datetime) -> datetime:
    days = (7 - now.weekday()) % 7
    if days == 0 and now.time() >= time(4, 0):
        days = 7
    target = now.replace(hour=4, minute=0, second=0, microsecond=0)
    from datetime import timedelta as _td

    return target + _td(days=days)


def evaluate_rule(
    rule: PricingRuleConfig,
    *,
    current_price: float,
    momentum_score: float | None = None,
    ctr: float | None = None,
    views: int = 0,
    orders: int = 0,
    now: datetime | None = None,
) -> PricingDecision | None:
    """Apply a single rule. Returns None if rule doesn't trigger."""
    if not rule.is_active:
        return None
    now = now or datetime.now(UTC)

    if rule.trigger == "high_momentum":
        # Trigger when momentum is high AND there's evidence of conversion.
        if (
            momentum_score is not None
            and momentum_score >= 60
            and (ctr or 0) >= 0.03
            and orders >= 1
        ):
            new_price = current_price + rule.delta_usd
            if rule.delta_percent:
                new_price = current_price * (1 + rule.delta_percent / 100)
            new_price = _clamp(new_price, rule.min_price_usd, rule.max_price_usd)
            if abs(new_price - current_price) < 0.01:
                return None
            return PricingDecision(
                new_price_usd=round(new_price, 2),
                rule_id=rule.id,
                rule_name=rule.name,
                reason=(
                    f"high momentum {momentum_score:.0f} + CTR {ctr:.1%} → +${new_price - current_price:.2f}"
                ),
            )
        return None

    if rule.trigger == "weekend_flash":
        if _is_weekend(now):
            discount_pct = abs(rule.delta_percent) or 10.0
            new_price = current_price * (1 - discount_pct / 100)
            new_price = _clamp(new_price, rule.min_price_usd, rule.max_price_usd)
            return PricingDecision(
                new_price_usd=round(new_price, 2),
                rule_id=rule.id,
                rule_name=rule.name,
                reason=f"weekend flash sale -{discount_pct:.0f}%",
                revert_at=_next_monday_4am(now),
            )
        return None

    if rule.trigger == "low_ctr_discount":
        # Apply discount when listing has high views but low CTR.
        if views >= 200 and (ctr or 0) < 0.01 and orders == 0:
            discount_pct = abs(rule.delta_percent) or 15.0
            new_price = current_price * (1 - discount_pct / 100)
            new_price = _clamp(new_price, rule.min_price_usd, rule.max_price_usd)
            return PricingDecision(
                new_price_usd=round(new_price, 2),
                rule_id=rule.id,
                rule_name=rule.name,
                reason=f"high views {views} + CTR {(ctr or 0):.1%} → -{discount_pct:.0f}% test",
            )
        return None

    return None


def evaluate_all(
    rules: list[PricingRuleConfig],
    *,
    current_price: float,
    momentum_score: float | None = None,
    ctr: float | None = None,
    views: int = 0,
    orders: int = 0,
    now: datetime | None = None,
) -> PricingDecision | None:
    """First triggering rule wins (rules should be ordered by priority)."""
    for rule in rules:
        decision = evaluate_rule(
            rule,
            current_price=current_price,
            momentum_score=momentum_score,
            ctr=ctr,
            views=views,
            orders=orders,
            now=now,
        )
        if decision:
            return decision
    return None
