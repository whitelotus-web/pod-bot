"""A/B variant test framework for campaigns.

Caller flow:

1. Pick a parent campaign and call :func:`create_variants` with the
   number of variants and a list of overrides (one dict per variant).
   Each override may tweak ``style_prompt`` / ``ai_engine`` /
   ``prompt_template_ids`` / ``ai_model``.
2. The function clones the parent, attaches a shared
   ``ab_test_group`` UUID, labels each variant ``A``, ``B``, etc., and
   commits.
3. Pipelines treat variants like any other campaign — products
   inherit ``ab_test_group`` + ``ab_variant_label`` so dashboards can
   group performance by variant.
4. After ``min_days_running`` days OR ``min_orders_per_variant``
   orders (whichever comes first), call :func:`pick_winner` to declare
   the highest-profit variant the winner. The other variants are
   paused (``is_active=False``) and the winner inherits their
   schedules.
"""
from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.models.product import Product

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VariantPerformance:
    campaign_id: int
    variant_label: str
    revenue_usd: float
    cost_usd: float
    profit_usd: float
    orders: int
    products: int

    def to_dict(self) -> dict[str, object]:
        return {
            "campaign_id": self.campaign_id,
            "variant_label": self.variant_label,
            "revenue_usd": round(self.revenue_usd, 2),
            "cost_usd": round(self.cost_usd, 2),
            "profit_usd": round(self.profit_usd, 2),
            "orders": self.orders,
            "products": self.products,
        }


def create_variants(
    db: Session,
    parent: Campaign,
    *,
    overrides: Sequence[dict[str, object]],
) -> list[Campaign]:
    """Create ``len(overrides)`` variants of ``parent`` linked by an A/B group.

    Returns the list of newly persisted variant campaigns. The parent
    itself is updated to participate as variant ``A`` if it is not
    already in a group.
    """
    if not overrides:
        return []
    if len(overrides) > 25:
        raise ValueError("A/B test supports at most 25 variants (A..Y)")

    group_id = parent.ab_test_group or uuid.uuid4().hex
    parent.ab_test_group = group_id
    parent.ab_variant_label = parent.ab_variant_label or "A"

    variants: list[Campaign] = []
    for i, override in enumerate(overrides, start=1):
        label = chr(ord("A") + i)
        variant = Campaign(
            user_id=parent.user_id,
            name=f"{parent.name} (variant {label})",
            niche=parent.niche,
            style_prompt=str(override.get("style_prompt", parent.style_prompt)),
            keyword_sources=list(parent.keyword_sources or []),
            ai_engine=str(override.get("ai_engine", parent.ai_engine)),
            ai_model=override.get("ai_model", parent.ai_model),  # type: ignore[arg-type]
            designs_per_keyword=int(
                override.get("designs_per_keyword", parent.designs_per_keyword)
            ),
            product_types=list(parent.product_types or []),
            base_price_usd=float(override.get("base_price_usd", parent.base_price_usd)),
            auto_mode=parent.auto_mode,
            target_platforms=list(parent.target_platforms or []),
            target_account_ids=list(parent.target_account_ids or []),
            seo_auto=parent.seo_auto,
            quality_gates_enabled=parent.quality_gates_enabled,
            vision_qa_enabled=parent.vision_qa_enabled,
            trademark_check_enabled=parent.trademark_check_enabled,
            uspto_check_enabled=parent.uspto_check_enabled,
            upscale_enabled=parent.upscale_enabled,
            upscale_min_long_edge=parent.upscale_min_long_edge,
            prompt_template_ids=list(
                override.get("prompt_template_ids", parent.prompt_template_ids or [])
            ),
            schedule_cron=parent.schedule_cron,
            is_active=True,
            ab_test_group=group_id,
            ab_variant_label=label,
        )
        db.add(variant)
        variants.append(variant)

    db.commit()
    for v in variants:
        db.refresh(v)
    db.refresh(parent)
    return variants


def measure(db: Session, group_id: str) -> list[VariantPerformance]:
    """Return per-variant performance for an active A/B group."""
    out: list[VariantPerformance] = []
    variants = db.query(Campaign).filter_by(ab_test_group=group_id).all()
    for v in variants:
        products = (
            db.query(Product)
            .filter(
                Product.ab_test_group == group_id,
                Product.ab_variant_label == v.ab_variant_label,
            )
            .all()
        )
        revenue = sum(float(p.revenue_usd or 0) - float(p.refunds_usd or 0) for p in products)
        # cost = wholesale * orders + platform_fees + ads + design cost (rough avg).
        cost = sum(
            float(p.cost_usd or 0) * int(p.orders_count or 0)
            + float(p.platform_fees_usd or 0)
            + float(p.ads_spend_usd or 0)
            for p in products
        )
        orders = sum(int(p.orders_count or 0) for p in products)
        out.append(
            VariantPerformance(
                campaign_id=v.id,
                variant_label=v.ab_variant_label or "?",
                revenue_usd=revenue,
                cost_usd=cost,
                profit_usd=revenue - cost,
                orders=orders,
                products=len(products),
            )
        )
    return out


def pick_winner(
    db: Session,
    group_id: str,
    *,
    min_orders_per_variant: int = 5,
) -> VariantPerformance | None:
    """Decide the winning variant; pause losers.

    Returns the winning ``VariantPerformance`` or ``None`` when no variant
    has accumulated enough orders to make a confident decision.
    """
    perfs = measure(db, group_id)
    if not perfs:
        return None
    if any(p.orders < min_orders_per_variant for p in perfs):
        # Not enough signal yet — keep the test running.
        return None

    winner = max(perfs, key=lambda p: p.profit_usd)
    now = datetime.now(UTC)
    for v in db.query(Campaign).filter_by(ab_test_group=group_id).all():
        is_winner = v.id == winner.campaign_id
        v.ab_test_winner = is_winner
        v.ab_test_concluded_at = now
        v.is_active = is_winner
    db.commit()
    logger.info(
        "A/B group %s concluded — winner: %s (profit $%.2f)",
        group_id,
        winner.variant_label,
        winner.profit_usd,
    )
    return winner
