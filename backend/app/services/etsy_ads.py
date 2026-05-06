"""Etsy Ads spend ingest.

Etsy doesn't expose an Ads-spend webhook. The Stats API endpoint
``/v3/application/shops/{shop_id}/stats`` returns daily spend data
when the seller has Etsy Ads turned on. We poll it nightly and
attribute spend to listings via the per-listing breakdown endpoint
``/v3/application/shops/{shop_id}/listings/{listing_id}/stats``.

The implementation here is a skeleton: the real HTTP calls are wired
once the user supplies a refresh-tokenised Etsy account. For dev /
pre-OAuth runs we no-op gracefully.
"""
from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.models.platform_account import PlatformAccount
from app.models.product import Product

logger = logging.getLogger(__name__)


def _bearer(account: PlatformAccount) -> str | None:
    """Read the access token for an Etsy account, returning None if missing."""
    return (account.access_token or "").strip() or None


def fetch_daily_ads_spend(
    account: PlatformAccount,
    *,
    on: date | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any] | None:
    """Pull yesterday's Etsy Ads spend for ``account``.

    Returns ``{"date": date, "spend_usd": float, "clicks": int}`` or
    ``None`` if the account isn't an Etsy account or has no token.
    """
    if account.platform != "etsy":
        return None
    if on is None:
        on = date.today() - timedelta(days=1)
    token = _bearer(account)
    if token is None:
        return None
    shop_id = account.shop_id
    if not shop_id:
        logger.warning("Etsy account %s has no shop id — skipping ads pull", account.id)
        return None

    api_key = os.getenv("ETSY_API_KEY", "")
    url = f"https://openapi.etsy.com/v3/application/shops/{shop_id}/stats"
    params = {"start_date": on.isoformat(), "end_date": on.isoformat()}
    headers = {"x-api-key": api_key, "Authorization": f"Bearer {token}"}

    own_client = client is None
    if client is None:
        client = httpx.Client(timeout=15.0)
    try:
        resp = client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    except Exception:  # noqa: BLE001
        logger.exception("Failed to fetch Etsy ads stats for account %s", account.id)
        return None
    finally:
        if own_client:
            client.close()

    spend = float(data.get("ads_spend_usd") or 0)
    clicks = int(data.get("ads_clicks") or 0)
    return {"date": on, "spend_usd": spend, "clicks": clicks}


def attribute_to_products(
    db: Session,
    account: PlatformAccount,
    *,
    spend_usd: float,
) -> int:
    """Distribute ``spend_usd`` across active products of an account.

    Simple proportional split by ``orders_count`` so high-traffic listings
    absorb most of the cost — refined attribution can land later via the
    per-listing stats endpoint.
    """
    products = (
        db.query(Product)
        .filter(
            Product.platform_account_id == account.id,
            Product.status == "published",
        )
        .all()
    )
    if not products or spend_usd <= 0:
        return 0
    total_orders = sum(int(p.orders_count or 0) for p in products) or len(products)
    for p in products:
        weight = (int(p.orders_count or 0) or 1) / total_orders
        p.ads_spend_usd = float(p.ads_spend_usd or 0) + spend_usd * weight
    db.commit()
    return len(products)
