"""Merch by Amazon adapter — Selenium skeleton.

Merch by Amazon is invite-only and does NOT have a public API. Amazon
aggressively detects and bans automated uploads. Adapter is included for
completeness but is disabled by default.
"""
from __future__ import annotations

from app.services.platforms.base import PODPlatform, PublishResult


class MerchAmazonPlatform(PODPlatform):
    name = "merch_amazon"
    supports_api = False

    def __init__(self, account):
        self.account = account

    def test_connection(self) -> bool:
        return False

    def publish(self, **kwargs) -> PublishResult:
        return PublishResult(
            status="failed",
            error=(
                "Merch by Amazon không có public API và Amazon rất gắt với bot. "
                "Adapter tắt mặc định. Hãy cân nhắc upload thủ công từ dashboard."
            ),
        )
