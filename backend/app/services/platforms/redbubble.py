"""Redbubble adapter (Selenium-based).

Redbubble does NOT expose a public API. This adapter provides the skeleton
for a Selenium/Playwright automation that logs in and uploads designs.

⚠️ Redbubble ToS discourages bot uploads; use responsibly and at your own
risk. This implementation intentionally stops at a NotImplementedError
until the user supplies cookies and confirms they accept the risk.

To activate:
  1. pip install playwright && playwright install chromium
  2. Run the Playwright login flow once manually and save cookies to
     PlatformAccount.extra["cookies"].
  3. Replace _upload_design() with your own CSS-selector based flow.
"""
from __future__ import annotations

import logging

from app.services.platforms.base import PODPlatform, PublishResult

logger = logging.getLogger(__name__)


class RedbubblePlatform(PODPlatform):
    name = "redbubble"
    supports_api = False

    def __init__(self, account):
        self.account = account

    def test_connection(self) -> bool:
        extra = self.account.extra or {}
        return bool(extra.get("cookies"))

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
        return PublishResult(
            status="failed",
            error=(
                "Redbubble không có public API. Adapter Selenium đang ở dạng skeleton. "
                "Hãy thay thế _upload_design() với Playwright flow và cookies hợp lệ."
            ),
        )
