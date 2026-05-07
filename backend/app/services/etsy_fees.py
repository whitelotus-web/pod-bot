"""Etsy fee model — applied to every sale to keep P&L honest.

Etsy charges sellers four fees per transaction:

1. **Listing fee**: $0.20 per listing, charged once when the listing
   is published / renewed (renews every 4 months automatically).
2. **Transaction fee**: 6.5% of (item price + shipping + gift wrap),
   excluding tax.
3. **Payment processing**: 3% + $0.25 per order (US rates — varies by
   country, see Etsy seller policy).
4. **Etsy Ads**: only if the seller opted in, charged per click.

The numbers below match the Etsy seller policy as of 2026-04. If Etsy
adjusts pricing later, update :data:`_FEE_TABLE` and re-run a backfill.

Reference: https://www.etsy.com/seller-handbook/article/fees-and-payments
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EtsyFeeBreakdown:
    listing_fee: float
    transaction_fee: float
    payment_fee: float
    total: float

    def to_dict(self) -> dict[str, float]:
        return {
            "listing_fee": round(self.listing_fee, 4),
            "transaction_fee": round(self.transaction_fee, 4),
            "payment_fee": round(self.payment_fee, 4),
            "total": round(self.total, 4),
        }


_FEE_TABLE: dict[str, dict[str, float]] = {
    "etsy": {
        "listing_per_renewal": 0.20,
        "transaction_pct": 0.065,
        "payment_pct": 0.03,
        "payment_flat": 0.25,
    },
}


def listing_fee(platform: str = "etsy") -> float:
    return _FEE_TABLE.get(platform, {}).get("listing_per_renewal", 0.0)


def fees_for_order(
    *,
    platform: str = "etsy",
    item_price_usd: float,
    shipping_usd: float = 0.0,
    listing_renewal_due: bool = False,
) -> EtsyFeeBreakdown:
    """Return the fee breakdown for one order.

    Pass ``listing_renewal_due=True`` only when this order triggers an
    automatic relist (every 4 months or after the previous quantity
    sells out). The default is False to avoid double-counting.
    """
    table = _FEE_TABLE.get(platform, {})
    if not table:
        return EtsyFeeBreakdown(0.0, 0.0, 0.0, 0.0)
    base = max(0.0, item_price_usd) + max(0.0, shipping_usd)
    listing = table.get("listing_per_renewal", 0.0) if listing_renewal_due else 0.0
    transaction = base * table.get("transaction_pct", 0.0)
    payment = base * table.get("payment_pct", 0.0) + table.get("payment_flat", 0.0)
    total = listing + transaction + payment
    return EtsyFeeBreakdown(
        listing_fee=listing,
        transaction_fee=transaction,
        payment_fee=payment,
        total=total,
    )
