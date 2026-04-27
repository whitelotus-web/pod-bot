"""Printful adapter.

Docs: https://developers.printful.com/docs/
"""
from __future__ import annotations

import logging
import os

import httpx

from app.services.platforms.base import PODPlatform, PublishResult

logger = logging.getLogger(__name__)

API = "https://api.printful.com"
DEFAULT_VARIANT_ID = 4011  # Bella + Canvas 3001 Unisex Short Sleeve Jersey - White, M


class PrintfulPlatform(PODPlatform):
    name = "printful"

    def __init__(self, account):
        self.account = account
        if not account.api_key:
            raise RuntimeError("Printful account chưa có API key")
        self.client = httpx.Client(
            base_url=API,
            headers={
                "Authorization": f"Bearer {account.api_key}",
                "User-Agent": "POD-Bot/0.1",
            },
            timeout=30,
        )

    def test_connection(self) -> bool:
        try:
            r = self.client.get("/stores")
            return r.status_code == 200
        except Exception as exc:  # noqa: BLE001
            logger.warning("Printful ping failed: %s", exc)
            return False

    def _upload_file(self, design_path: str) -> str:
        with open(design_path, "rb") as f:
            files = {"file": (os.path.basename(design_path), f, "image/png")}
            r = self.client.post("/files", files=files)
            r.raise_for_status()
            return str(r.json()["result"]["id"])

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
            variant_id = int(extra.get("variant_id", DEFAULT_VARIANT_ID))
            file_id = self._upload_file(design_path)

            payload = {
                "sync_product": {"name": title[:140], "thumbnail": ""},
                "sync_variants": [
                    {
                        "variant_id": variant_id,
                        "retail_price": f"{price_usd:.2f}",
                        "files": [{"id": int(file_id)}],
                    }
                ],
            }
            r = self.client.post("/store/products", json=payload)
            r.raise_for_status()
            result = r.json()["result"]

            return PublishResult(
                external_id=str(result.get("id")),
                url=f"https://www.printful.com/dashboard/sync/{result.get('id')}",
                status="published",
                raw=result,
            )
        except httpx.HTTPStatusError as exc:
            return PublishResult(status="failed", error=f"{exc.response.status_code}: {exc.response.text[:500]}")
        except Exception as exc:  # noqa: BLE001
            return PublishResult(status="failed", error=str(exc))
