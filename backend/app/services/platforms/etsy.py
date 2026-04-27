"""Etsy OAuth 2.0 adapter.

Docs: https://developers.etsy.com/documentation/
Requires a verified Etsy developer app + shop.

This adapter assumes you route users through the OAuth flow
(see app/api/v1/platforms.py for callback) and store access/refresh
tokens on the PlatformAccount row. It refreshes on 401 automatically.

Note: Etsy doesn't do the POD printing — pair it with a Printify/Printful
sync shop. This adapter creates a draft physical-product listing which
you then link to your POD provider inside Etsy.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx

from app.core.config import settings
from app.services.platforms.base import PODPlatform, PublishResult

logger = logging.getLogger(__name__)

API = "https://openapi.etsy.com/v3"


class EtsyPlatform(PODPlatform):
    name = "etsy"
    requires_oauth = True

    def __init__(self, account):
        self.account = account
        if not account.access_token:
            raise RuntimeError("Etsy account chưa có access_token — hãy OAuth trước")
        self.client = self._build_client(account.access_token)

    @staticmethod
    def _build_client(access_token: str) -> httpx.Client:
        return httpx.Client(
            base_url=API,
            headers={
                "Authorization": f"Bearer {access_token}",
                "x-api-key": settings.etsy_client_id or "",
                "User-Agent": "POD-Bot/0.1",
            },
            timeout=30,
        )

    def _refresh_if_needed(self):
        if not self.account.refresh_token:
            return
        now = datetime.now(UTC)
        if self.account.token_expires_at and self.account.token_expires_at > now:
            return
        r = httpx.post(
            "https://api.etsy.com/v3/public/oauth/token",
            data={
                "grant_type": "refresh_token",
                "client_id": settings.etsy_client_id,
                "refresh_token": self.account.refresh_token,
            },
            timeout=30,
        )
        r.raise_for_status()
        tok = r.json()
        self.account.access_token = tok["access_token"]
        self.account.refresh_token = tok.get("refresh_token", self.account.refresh_token)
        self.client = self._build_client(self.account.access_token)

    def test_connection(self) -> bool:
        try:
            self._refresh_if_needed()
            r = self.client.get("/application/users/me")
            return r.status_code == 200
        except Exception as exc:  # noqa: BLE001
            logger.warning("Etsy ping failed: %s", exc)
            return False

    def publish(
        self,
        *,
        design_path: str,
        title: str,
        description: str,
        tags: list[str],
        price_usd: float,
        product_type: str = "tshirt",
    ) -> PublishResult:
        try:
            self._refresh_if_needed()
            extra = self.account.extra or {}
            shop_id = extra.get("shop_id") or self.account.shop_id
            if not shop_id:
                return PublishResult(status="failed", error="Etsy shop_id chưa có")

            payload = {
                "quantity": 999,
                "title": title[:140],
                "description": description[:5000],
                "price": f"{price_usd:.2f}",
                "who_made": "i_did",
                "when_made": "made_to_order",
                "taxonomy_id": int(extra.get("taxonomy_id", 2078)),  # Clothing > Tshirts
                "tags": tags[:13],
                "is_supply": False,
                "state": "draft",
            }
            r = self.client.post(
                f"/application/shops/{shop_id}/listings",
                data=payload,
            )
            r.raise_for_status()
            listing = r.json()
            listing_id = listing["listing_id"]

            # Upload image
            with open(design_path, "rb") as f:
                up = self.client.post(
                    f"/application/shops/{shop_id}/listings/{listing_id}/images",
                    files={"image": f},
                    data={"rank": 1},
                )
                up.raise_for_status()

            return PublishResult(
                external_id=str(listing_id),
                url=f"https://www.etsy.com/listing/{listing_id}",
                status="published",
                raw=listing,
            )
        except httpx.HTTPStatusError as exc:
            return PublishResult(status="failed", error=f"{exc.response.status_code}: {exc.response.text[:500]}")
        except Exception as exc:  # noqa: BLE001
            return PublishResult(status="failed", error=str(exc))
