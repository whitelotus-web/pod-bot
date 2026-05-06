"""Customer review monitor.

Polls Etsy + Printify for new reviews on each published product, stores
them, and pushes a Telegram alert when a 1-2 star review lands so the
seller can respond before it impacts shop reputation.

Implementation here keeps the platform calls behind a thin abstraction so
the unit test can inject a fake fetcher. Real HTTP wiring lives behind
``_fetch_etsy_reviews`` / ``_fetch_printify_reviews``.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.platform_account import PlatformAccount
from app.models.product import Product
from app.models.review import ProductReview

logger = logging.getLogger(__name__)

# Threshold below which we ping the seller via Telegram. 1-2 stars on
# Etsy can cascade into account warnings, so anything ≤ 2 is urgent.
LOW_RATING_THRESHOLD: float = 2.0


@dataclass(frozen=True)
class ReviewPayload:
    external_review_id: str
    rating: float
    title: str | None
    body: str | None
    reviewer_name: str | None
    reviewed_at: datetime | None


def _fetch_etsy_reviews(
    product: Product, account: PlatformAccount
) -> list[ReviewPayload]:
    """Stub — real Etsy ``/v3/application/listings/{id}/reviews`` call goes here."""
    logger.debug(
        "Etsy review fetch not wired yet (account=%s, product=%s)",
        account.id,
        product.id,
    )
    return []


def _fetch_printify_reviews(
    product: Product, account: PlatformAccount
) -> list[ReviewPayload]:
    """Stub — Printify doesn't expose reviews, but Print-on-Demand sellers
    sometimes pull reviews from the connected storefront. We keep this
    here so a follow-up PR can wire Shopify / WooCommerce flows.
    """
    return []


_FETCHERS: dict[str, Callable[[Product, PlatformAccount], list[ReviewPayload]]] = {
    "etsy": _fetch_etsy_reviews,
    "printify": _fetch_printify_reviews,
}


def poll_account(
    db: Session,
    account: PlatformAccount,
    *,
    fetcher: Callable[[Product, PlatformAccount], list[ReviewPayload]] | None = None,
) -> dict[str, Any]:
    """Poll one platform account for new reviews on its published products.

    Returns ``{"new_reviews": int, "low_rating_alerts": int}``.
    """
    if fetcher is None:
        fetcher = _FETCHERS.get(account.platform)
    if fetcher is None:
        return {"new_reviews": 0, "low_rating_alerts": 0}

    products = (
        db.query(Product)
        .filter(
            Product.platform_account_id == account.id,
            Product.status == "published",
        )
        .all()
    )
    new_count = 0
    alerts = 0
    for p in products:
        try:
            payloads = fetcher(p, account)
        except Exception:  # noqa: BLE001
            logger.exception("Review fetch failed for product %s", p.id)
            continue
        for payload in payloads:
            existing = (
                db.query(ProductReview)
                .filter_by(product_id=p.id, external_review_id=payload.external_review_id)
                .first()
            )
            if existing is not None:
                continue
            row = ProductReview(
                product_id=p.id,
                external_review_id=payload.external_review_id,
                rating=payload.rating,
                title=payload.title,
                body=payload.body,
                reviewer_name=payload.reviewer_name,
                reviewed_at=payload.reviewed_at,
            )
            db.add(row)
            new_count += 1
            if payload.rating <= LOW_RATING_THRESHOLD:
                _push_low_rating_alert(db, p, account, row)
                row.alert_sent = 1
                alerts += 1
    if new_count:
        db.commit()
    return {"new_reviews": new_count, "low_rating_alerts": alerts}


def _push_low_rating_alert(
    db: Session,
    product: Product,
    account: PlatformAccount,
    review: ProductReview,
) -> None:
    """Best-effort Telegram + in-app notification."""
    try:
        from app.services.notifications import dispatch

        dispatch(
            db,
            user_id=account.user_id,
            kind="low_rating_review",
            severity="critical",
            title=f"Review {review.rating:.0f}★ trên {product.title[:60]}",
            body=(
                f"{review.reviewer_name or 'Khách'}: "
                f"{(review.body or review.title or '').strip()[:300]}"
            ),
            payload={"product_id": product.id, "url": product.url, "rating": review.rating},
        )
    except Exception:  # noqa: BLE001
        logger.exception("Failed to push low-rating alert for review %s", review.id)
