"""Profit & Loss reporting service.

Aggregates per-user revenue (from Etsy/Printify webhook syncs into
``Product.revenue_usd``) minus costs (AI generation cost on ``Design``,
upscale cost on ``Design`` extension, base wholesale cost on ``Product``)
into time-bucketed and grouping-bucketed P&L summaries.

The dashboard at ``/pnl`` calls into :func:`summary` and the per-grouping
helpers (:func:`by_day`, :func:`by_campaign`, :func:`by_product_type`,
:func:`top_winners`, :func:`top_losers`) which all return plain dicts so
the API layer can serialise them directly.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.campaign import Campaign
from app.models.design import Design
from app.models.platform_account import PlatformAccount
from app.models.product import Product

# --- Cost reference table ---------------------------------------------------

# Per-image cost estimate by AI engine. These values are public list prices
# (USD) at the time of writing. Tweak via env vars in cost_for_engine().
_ENGINE_COST_USD: dict[str, float] = {
    "gemini": 0.000,           # Gemini 2.5 Flash image is free up to quota
    "openai": 0.040,           # DALL-E 3 1024x1024 standard
    "replicate": 0.005,        # SDXL average
}

# Upscale backend per-image cost. Local + LANCZOS are free.
_UPSCALE_COST_USD: dict[str, float] = {
    "replicate": 0.002,
    "real_esrgan_local": 0.000,
    "pil_lanczos": 0.000,
}


def cost_for_engine(engine: str | None) -> float:
    return _ENGINE_COST_USD.get((engine or "").lower(), 0.0)


def cost_for_upscale(backend: str | None) -> float:
    return _UPSCALE_COST_USD.get((backend or "").lower(), 0.0)


@dataclass(frozen=True)
class Bucket:
    label: str  # e.g. "2024-11-01" or "Cat Lover Shop" or "tshirt_unisex"
    revenue_usd: float
    cost_usd: float
    profit_usd: float
    orders: int
    products: int

    def to_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "revenue_usd": round(self.revenue_usd, 2),
            "cost_usd": round(self.cost_usd, 2),
            "profit_usd": round(self.profit_usd, 2),
            "orders": self.orders,
            "products": self.products,
        }


# --- Cost extraction ---------------------------------------------------------


def _design_cost_usd(d: Design | None) -> float:
    """Per-design cost = AI generation cost + upscale cost.

    Stored ``Design.cost_usd`` overrides the heuristic if set (>0). This lets
    callers record the exact billed cost from a webhook later and still keep
    the heuristic for older rows.
    """
    if d is None:
        return 0.0
    if (d.cost_usd or 0) > 0:
        return float(d.cost_usd or 0)
    return cost_for_engine(d.engine) + cost_for_upscale(d.upscale_backend)


def _product_total_cost_usd(p: Product) -> float:
    """Total cost for a single product = design portion + per-product portion.

    Per-product cost (``Product.cost_usd``) is the wholesale base from the
    catalog blueprint (Printify base price). For an order, gross profit is
    ``revenue - (orders * product_cost) - design_cost``. Since design cost
    is per-design (one-shot), we attribute it to the product row that owns
    the design when computing per-product P&L; multiple products from the
    same design will see the design cost split evenly.
    """
    revenue_per_order = float(p.cost_usd or 0)
    orders = int(p.orders_count or 0)
    return orders * revenue_per_order


# --- Aggregations ------------------------------------------------------------


def _query_user_products(db: Session, user_id: int, since: datetime | None):
    q = (
        db.query(Product)
        .join(PlatformAccount, Product.platform_account_id == PlatformAccount.id)
        .filter(PlatformAccount.user_id == user_id)
    )
    if since is not None:
        q = q.filter(Product.created_at >= since)
    return q


def _attribute_design_cost(products: Iterable[Product]) -> dict[int, float]:
    """Spread each design's cost across its products evenly."""
    by_design: dict[int, list[Product]] = defaultdict(list)
    for p in products:
        if p.design_id is not None:
            by_design[p.design_id].append(p)
    out: dict[int, float] = {}
    for _design_id, ps in by_design.items():
        if not ps:
            continue
        cost = _design_cost_usd(ps[0].design) / len(ps)
        for p in ps:
            out[p.id] = cost
    return out


def _bucket_sum(rows: list[tuple[str, Product, float]]) -> list[Bucket]:
    """Group ``(label, product, design_cost_share)`` into ``Bucket`` rows."""
    grouped: dict[str, dict[str, float]] = defaultdict(
        lambda: {"revenue": 0.0, "cost": 0.0, "orders": 0, "products": 0}
    )
    for label, p, design_cost in rows:
        rev = float(p.revenue_usd or 0)
        product_cost = _product_total_cost_usd(p)
        cost = product_cost + design_cost
        bucket = grouped[label]
        bucket["revenue"] += rev
        bucket["cost"] += cost
        bucket["orders"] += int(p.orders_count or 0)
        bucket["products"] += 1
    out = [
        Bucket(
            label=label,
            revenue_usd=v["revenue"],
            cost_usd=v["cost"],
            profit_usd=v["revenue"] - v["cost"],
            orders=int(v["orders"]),
            products=int(v["products"]),
        )
        for label, v in grouped.items()
    ]
    out.sort(key=lambda b: b.profit_usd, reverse=True)
    return out


def by_day(db: Session, user_id: int, days: int = 30) -> list[Bucket]:
    since = datetime.now(UTC) - timedelta(days=days)
    products = _query_user_products(db, user_id, since).all()
    design_share = _attribute_design_cost(products)
    rows = [
        (
            (p.published_at or p.created_at).date().isoformat(),
            p,
            design_share.get(p.id, 0.0),
        )
        for p in products
    ]
    out = _bucket_sum(rows)
    # Re-sort chronologically for charting.
    out.sort(key=lambda b: b.label)
    return out


def by_campaign(db: Session, user_id: int, days: int = 90) -> list[Bucket]:
    since = datetime.now(UTC) - timedelta(days=days)
    products = _query_user_products(db, user_id, since).all()
    design_share = _attribute_design_cost(products)
    campaigns_by_id: dict[int, str] = {
        c.id: (c.name or f"Campaign #{c.id}")
        for c in db.query(Campaign).filter_by(user_id=user_id).all()
    }
    rows: list[tuple[str, Product, float]] = []
    for p in products:
        d = p.design
        cid = d.campaign_id if d is not None else None
        label = campaigns_by_id.get(cid, "(orphan)") if cid else "(orphan)"
        rows.append((label, p, design_share.get(p.id, 0.0)))
    return _bucket_sum(rows)


def by_product_type(db: Session, user_id: int, days: int = 90) -> list[Bucket]:
    since = datetime.now(UTC) - timedelta(days=days)
    products = _query_user_products(db, user_id, since).all()
    design_share = _attribute_design_cost(products)
    rows = [
        (p.product_type or "unknown", p, design_share.get(p.id, 0.0))
        for p in products
    ]
    return _bucket_sum(rows)


def top_winners(db: Session, user_id: int, days: int = 90, n: int = 10) -> list[dict]:
    since = datetime.now(UTC) - timedelta(days=days)
    products = _query_user_products(db, user_id, since).all()
    design_share = _attribute_design_cost(products)
    out = []
    for p in products:
        rev = float(p.revenue_usd or 0)
        cost = _product_total_cost_usd(p) + design_share.get(p.id, 0.0)
        profit = rev - cost
        out.append(
            {
                "id": p.id,
                "title": p.title,
                "url": p.url,
                "product_type": p.product_type,
                "revenue_usd": round(rev, 2),
                "cost_usd": round(cost, 2),
                "profit_usd": round(profit, 2),
                "orders": int(p.orders_count or 0),
            }
        )
    out.sort(key=lambda x: x["profit_usd"], reverse=True)
    return out[:n]


def top_losers(db: Session, user_id: int, days: int = 90, n: int = 10) -> list[dict]:
    """Worst performing products: highest cost / lowest profit (likely cut-loss candidates)."""
    since = datetime.now(UTC) - timedelta(days=days)
    products = _query_user_products(db, user_id, since).all()
    design_share = _attribute_design_cost(products)
    out = []
    for p in products:
        rev = float(p.revenue_usd or 0)
        cost = _product_total_cost_usd(p) + design_share.get(p.id, 0.0)
        profit = rev - cost
        if cost <= 0 and rev <= 0:
            # Skip rows with no economic activity at all.
            continue
        out.append(
            {
                "id": p.id,
                "title": p.title,
                "url": p.url,
                "product_type": p.product_type,
                "revenue_usd": round(rev, 2),
                "cost_usd": round(cost, 2),
                "profit_usd": round(profit, 2),
                "orders": int(p.orders_count or 0),
                "views": int(p.views_count or 0),
            }
        )
    out.sort(key=lambda x: x["profit_usd"])
    return out[:n]


def summary(db: Session, user_id: int, days: int = 30) -> dict[str, object]:
    """Top-level KPIs for the dashboard hero card."""
    since = datetime.now(UTC) - timedelta(days=days)
    products = _query_user_products(db, user_id, since).all()
    design_share = _attribute_design_cost(products)
    revenue = sum(float(p.revenue_usd or 0) for p in products)
    cost = sum(
        _product_total_cost_usd(p) + design_share.get(p.id, 0.0) for p in products
    )
    profit = revenue - cost
    orders = sum(int(p.orders_count or 0) for p in products)
    margin_pct = (profit / revenue * 100.0) if revenue > 0 else 0.0
    return {
        "days": days,
        "since": since.date().isoformat(),
        "until": date.today().isoformat(),
        "revenue_usd": round(revenue, 2),
        "cost_usd": round(cost, 2),
        "profit_usd": round(profit, 2),
        "margin_pct": round(margin_pct, 1),
        "orders": orders,
        "products": len(products),
    }
