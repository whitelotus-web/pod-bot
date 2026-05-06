"""Inbound webhook handlers (Etsy + Printify) with HMAC verification.

Both endpoints accept the raw body and dispatch to the relevant
service. The signature check is mandatory in production (env
``ENVIRONMENT=production``); in dev we log a warning and accept.

Supported event types:
* Etsy ``transaction_created`` → bumps ``Product.orders_count`` + revenue,
  and pre-aggregates Etsy fees onto ``platform_fees_usd``.
* Etsy ``transaction_refunded`` → bumps ``refunds_count`` + ``refunds_usd``.
* Printify ``order:created`` / ``order:updated`` — wholesale base cost
  is already pre-set on the product row; we update ``orders_count``.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.webhook_signing import verify_etsy_webhook, verify_printify_webhook
from app.models.product import Product
from app.services.etsy_fees import fees_for_order

logger = logging.getLogger(__name__)
router = APIRouter()


def _find_product_by_external(db: Session, external_id: str | int) -> Product | None:
    if external_id is None:
        return None
    return db.query(Product).filter_by(external_id=str(external_id)).first()


@router.post("/etsy")
async def etsy_webhook(
    request: Request,
    x_etsy_signature: str | None = Header(default=None),
) -> dict[str, Any]:
    body = await request.body()
    if not verify_etsy_webhook(body, x_etsy_signature):
        raise HTTPException(status_code=401, detail="Invalid Etsy signature.")
    payload = await request.json()
    event = payload.get("event") or payload.get("type") or ""
    listing_id = payload.get("listing_id") or payload.get("listing", {}).get("id")
    amount = float(payload.get("amount_usd") or payload.get("price") or 0)
    shipping = float(payload.get("shipping_usd") or 0)

    db = SessionLocal()
    try:
        product = _find_product_by_external(db, listing_id)
        if product is None:
            return {"status": "ignored", "reason": "unknown listing"}

        if event in {"transaction_created", "order_created"}:
            fees = fees_for_order(
                platform="etsy",
                item_price_usd=amount,
                shipping_usd=shipping,
                listing_renewal_due=False,
            )
            product.orders_count = int(product.orders_count or 0) + 1
            product.revenue_usd = float(product.revenue_usd or 0) + amount
            product.platform_fees_usd = float(product.platform_fees_usd or 0) + fees.total
            db.commit()
            return {"status": "ok", "fees": fees.to_dict()}

        if event in {"transaction_refunded", "order_refunded"}:
            product.refunds_count = int(product.refunds_count or 0) + 1
            product.refunds_usd = float(product.refunds_usd or 0) + amount
            db.commit()
            return {"status": "ok", "refunded_usd": amount}

        return {"status": "ignored", "reason": f"unhandled event {event}"}
    finally:
        db.close()


@router.post("/printify")
async def printify_webhook(
    request: Request,
    x_pfy_signature: str | None = Header(default=None),
) -> dict[str, Any]:
    body = await request.body()
    if not verify_printify_webhook(body, x_pfy_signature):
        raise HTTPException(status_code=401, detail="Invalid Printify signature.")
    payload = await request.json()
    event = payload.get("type") or ""
    order = payload.get("data", {})
    line_items = order.get("line_items", []) or []

    db = SessionLocal()
    try:
        for item in line_items:
            product_id = item.get("product_id") or item.get("printify_product_id")
            product = _find_product_by_external(db, product_id)
            if product is None:
                continue
            if event in {"order:created", "order:sent-to-production"}:
                qty = int(item.get("quantity") or 1)
                product.orders_count = int(product.orders_count or 0) + qty
                product.revenue_usd = float(product.revenue_usd or 0) + float(
                    item.get("metadata", {}).get("price") or 0
                )
            elif event in {"order:refunded"}:
                product.refunds_count = int(product.refunds_count or 0) + 1
                product.refunds_usd = float(product.refunds_usd or 0) + float(
                    item.get("metadata", {}).get("refund_amount") or 0
                )
        db.commit()
        return {"status": "ok"}
    finally:
        db.close()
