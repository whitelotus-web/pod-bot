"""Printify adapter — core POD platform.

Docs: https://developers.printify.com/

Why Printify is the recommended core:
  * Free, no monthly fee, no per-product fee
  * Has a built-in **mockup generator** (returns photorealistic shirt images)
  * 800+ blueprints across 90+ print providers — pricing is transparent
  * Auto-syncs created products to connected sales channels (Etsy, Shopify,
    eBay, Walmart, TikTok Shop) so the bot only needs to publish once.

Flow used by the pipeline:
  1. POST /v1/uploads/images.json            → image_id
  2. POST /v1/shops/{shop}/products.json     → product_id (mockups generated)
  3. GET  /v1/shops/{shop}/products/{id}.json → preview images
  4. POST /v1/shops/{shop}/products/{id}/publish.json
"""
from __future__ import annotations

import base64
import logging

import httpx

from app.services.platforms.base import PODPlatform, PublishResult

logger = logging.getLogger(__name__)

API = "https://api.printify.com/v1"

# Default blueprint + provider for an "unisex heavy cotton tee".
# These IDs are stable on Printify but can be overridden per-account via
# PlatformAccount.extra = {"blueprint_id": 5, "print_provider_id": 29, ...}
DEFAULT_TSHIRT_BLUEPRINT = 5    # Gildan 5000 Unisex Heavy Cotton Tee
DEFAULT_PRINT_PROVIDER = 29     # Print Geek


class PrintifyPlatform(PODPlatform):
    name = "printify"

    def __init__(self, account):
        self.account = account
        if not account.api_key:
            raise RuntimeError("Printify account chưa có API key")
        if not account.shop_id:
            raise RuntimeError("Printify account chưa có shop_id")
        self.client = httpx.Client(
            base_url=API,
            headers={
                "Authorization": f"Bearer {account.api_key}",
                "User-Agent": "POD-Bot/0.1",
                "Content-Type": "application/json",
            },
            timeout=30,
        )

    def test_connection(self) -> bool:
        try:
            r = self.client.get("/shops.json")
            return r.status_code == 200
        except Exception as exc:  # noqa: BLE001
            logger.warning("Printify ping failed: %s", exc)
            return False

    def upload_image(self, design_path: str) -> str:
        """Upload a design and return the Printify image ID."""
        with open(design_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
        r = self.client.post(
            "/uploads/images.json",
            json={"file_name": design_path.rsplit("/", 1)[-1], "contents": encoded},
        )
        r.raise_for_status()
        return r.json()["id"]

    def _get_variants(self, blueprint_id: int, provider_id: int, limit: int = 8) -> list[int]:
        r = self.client.get(
            f"/catalog/blueprints/{blueprint_id}/print_providers/{provider_id}/variants.json"
        )
        r.raise_for_status()
        return [v["id"] for v in r.json().get("variants", [])[:limit]]

    def fetch_mockups(self, product_id: str) -> list[str]:
        """Return URLs of Printify-generated mockup images for a product."""
        try:
            r = self.client.get(f"/shops/{self.account.shop_id}/products/{product_id}.json")
            r.raise_for_status()
            return [img["src"] for img in r.json().get("images", [])]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Fetch mockups failed: %s", exc)
            return []

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
            extra = self.account.extra or {}
            blueprint_id = int(extra.get("blueprint_id", DEFAULT_TSHIRT_BLUEPRINT))
            provider_id = int(extra.get("print_provider_id", DEFAULT_PRINT_PROVIDER))

            image_id = self.upload_image(design_path)
            variant_ids = self._get_variants(blueprint_id, provider_id)
            if not variant_ids:
                return PublishResult(status="failed", error="Không tìm thấy variants")

            price_cents = int(price_usd * 100)
            payload = {
                "title": title[:140],
                "description": description[:5000],
                "tags": tags[:13],
                "blueprint_id": blueprint_id,
                "print_provider_id": provider_id,
                "variants": [
                    {"id": vid, "price": price_cents, "is_enabled": True} for vid in variant_ids
                ],
                "print_areas": [
                    {
                        "variant_ids": variant_ids,
                        "placeholders": [
                            {
                                "position": "front",
                                "images": [
                                    {
                                        "id": image_id,
                                        "x": 0.5,
                                        "y": 0.5,
                                        "scale": 1.0,
                                        "angle": 0,
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
            r = self.client.post(f"/shops/{self.account.shop_id}/products.json", json=payload)
            r.raise_for_status()
            product = r.json()
            product_id = product["id"]

            # Publish to all connected sales channels (Etsy, Shopify, etc.)
            self.client.post(
                f"/shops/{self.account.shop_id}/products/{product_id}/publish.json",
                json={
                    "title": True,
                    "description": True,
                    "images": True,
                    "variants": True,
                    "tags": True,
                    "shipping_template": True,
                },
            )

            return PublishResult(
                external_id=str(product_id),
                url=f"https://printify.com/app/products/{product_id}",
                status="published",
                raw=product,
            )
        except httpx.HTTPStatusError as exc:
            return PublishResult(
                status="failed",
                error=f"{exc.response.status_code}: {exc.response.text[:500]}",
            )
        except Exception as exc:  # noqa: BLE001
            return PublishResult(status="failed", error=str(exc))
