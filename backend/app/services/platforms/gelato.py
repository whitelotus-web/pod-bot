"""Gelato adapter.

Gelato is a global POD network with local production in 32 countries —
useful when you want to ship faster within EU/US/AU without paying
international shipping. Gelato API uses a Bearer API key issued in the
seller dashboard.

Docs: https://developers.gelato.com/docs
"""
from __future__ import annotations

import logging
import os

import httpx

from app.services.platforms.base import PODPlatform, PublishResult

logger = logging.getLogger(__name__)

API = "https://order.gelatoapis.com"
PRODUCT_API = "https://product.gelatoapis.com"


class GelatoPlatform(PODPlatform):
    name = "gelato"

    # Defaults pick a generic 180gsm cotton tee in white, US M. Override
    # via PlatformAccount.extra["product_uid"] for a different blueprint.
    DEFAULT_PRODUCT_UID = "apparel_product_gca_t-shirt_gsc_180-gsm-cotton_gscolor_white_gsize_m"

    def __init__(self, account):
        self.account = account
        if not account.api_key:
            raise RuntimeError("Gelato account chưa có API key")
        self.client = httpx.Client(
            base_url=PRODUCT_API,
            headers={
                "X-API-KEY": account.api_key,
                "User-Agent": "POD-Bot/0.1",
            },
            timeout=30,
        )

    def test_connection(self) -> bool:
        try:
            r = self.client.get("/v3/templates", params={"limit": 1})
            return r.status_code == 200
        except Exception as exc:  # noqa: BLE001
            logger.warning("Gelato ping failed: %s", exc)
            return False

    def _upload_file(self, design_path: str) -> str:
        """Upload a design and return Gelato's hosted file URL.

        Gelato's product creation endpoint takes a public URL for each
        placement file. We re-use the seller's Gelato CDN by POSTing to
        ``/v1/files`` (returns a hosted URL). For self-hosted dev mode
        you'd substitute a presigned S3 URL.
        """
        with open(design_path, "rb") as f:
            files = {"file": (os.path.basename(design_path), f, "image/png")}
            r = self.client.post("/v1/files", files=files)
            r.raise_for_status()
            data = r.json()
            return str(data.get("url") or data.get("downloadUrl"))

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
            product_uid = extra.get("product_uid", self.DEFAULT_PRODUCT_UID)
            file_url = self._upload_file(design_path)

            payload = {
                "title": title[:140],
                "description": description[:1000],
                "productUid": product_uid,
                "variants": [
                    {
                        "variantUid": product_uid,
                        "price": {"amount": f"{price_usd:.2f}", "currency": "USD"},
                        "imagePlaceholders": [
                            {
                                "name": "ImageFront",
                                "fileUrl": file_url,
                                "fitMethod": "slice",
                            }
                        ],
                    }
                ],
                "tags": tags[:13],
            }
            r = self.client.post("/v3/products", json=payload)
            r.raise_for_status()
            result = r.json()
            return PublishResult(
                external_id=str(result.get("productUid") or result.get("id")),
                url=str(result.get("publicUrl") or ""),
                status="published",
                raw=result,
            )
        except httpx.HTTPStatusError as exc:
            return PublishResult(
                status="failed",
                error=f"{exc.response.status_code}: {exc.response.text[:500]}",
            )
        except Exception as exc:  # noqa: BLE001
            return PublishResult(status="failed", error=str(exc))
