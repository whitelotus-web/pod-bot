"""Teespring / Spring adapter — Selenium skeleton.

Spring.inc (formerly Teespring) closed its public API in 2022. This adapter
is a placeholder; wire in Playwright cookie-based automation similar to
Redbubble when needed.
"""
from __future__ import annotations

from app.services.platforms.base import PODPlatform, PublishResult


class TeespringPlatform(PODPlatform):
    name = "teespring"
    supports_api = False

    def __init__(self, account):
        self.account = account

    def test_connection(self) -> bool:
        return bool((self.account.extra or {}).get("cookies"))

    def publish(self, **kwargs) -> PublishResult:
        return PublishResult(
            status="failed",
            error="Teespring/Spring không có public API. Adapter ở dạng skeleton Selenium.",
        )
