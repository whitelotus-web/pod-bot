"""Abstract POD platform adapter."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class PublishResult:
    external_id: str | None = None
    url: str | None = None
    status: str = "published"  # published | draft | failed
    error: str | None = None
    raw: dict | None = None


class PODPlatform(ABC):
    """Each concrete platform subclass handles product creation + publishing."""

    name: str = "base"
    supports_api: bool = True
    requires_oauth: bool = False

    @abstractmethod
    def __init__(self, account):  # account: PlatformAccount ORM
        ...

    @abstractmethod
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
        ...

    def test_connection(self) -> bool:
        """Return True if credentials look valid. Default: True."""
        return True


def get_platform(platform_name: str, account) -> PODPlatform:
    from app.services.platforms.etsy import EtsyPlatform
    from app.services.platforms.gelato import GelatoPlatform
    from app.services.platforms.manual import (
        AmazonMerchPlatform,
        RedBubblePlatform,
        Society6Platform,
        SpreadshirtPlatform,
    )
    from app.services.platforms.printful import PrintfulPlatform
    from app.services.platforms.printify import PrintifyPlatform

    registry: dict[str, type[PODPlatform]] = {
        "printify": PrintifyPlatform,
        "printful": PrintfulPlatform,
        "gelato": GelatoPlatform,
        "etsy": EtsyPlatform,
        "redbubble": RedBubblePlatform,
        "society6": Society6Platform,
        "amazon_merch": AmazonMerchPlatform,
        "spreadshirt": SpreadshirtPlatform,
    }
    cls = registry.get(platform_name)
    if cls is None:
        raise ValueError(
            f"Unknown platform: {platform_name}. "
            f"Supported: {', '.join(sorted(registry))}."
        )
    return cls(account)


# Metadata for the dashboard UI. Only API-backed platforms are listed.
PLATFORM_META = {
    "printify": {
        "label": "Printify",
        "auth": "api_key",
        "tier": "core",
        "supported": True,
        "tagline": "Rẻ nhất, mockup miễn phí, auto-sync sang Etsy.",
        "setup_url": "https://printify.com/app/account/api",
    },
    "printful": {
        "label": "Printful",
        "auth": "api_key",
        "tier": "premium",
        "supported": True,
        "tagline": "Chất lượng cao cấp, fulfillment nhanh.",
        "setup_url": "https://developers.printful.com/",
    },
    "etsy": {
        "label": "Etsy",
        "auth": "oauth2",
        "tier": "marketplace",
        "supported": True,
        "tagline": "Marketplace có sẵn 95M người mua/tháng.",
        "setup_url": "https://www.etsy.com/developers/your-apps",
    },
    "gelato": {
        "label": "Gelato",
        "auth": "api_key",
        "tier": "premium",
        "supported": True,
        "tagline": "Local production tại 32 nước, ship nhanh trong EU/US/AU.",
        "setup_url": "https://dashboard.gelato.com/keys/api",
    },
    "redbubble": {
        "label": "RedBubble",
        "auth": "manual",
        "tier": "manual",
        "supported": True,
        "tagline": "Manual export — bot tạo zip sẵn, anh upload vài phút.",
        "setup_url": "https://www.redbubble.com/upload",
    },
    "society6": {
        "label": "Society6",
        "auth": "manual",
        "tier": "manual",
        "supported": True,
        "tagline": "Manual export — chuyên art print, niche cao cấp.",
        "setup_url": "https://society6.com/studio/uploads",
    },
    "amazon_merch": {
        "label": "Amazon Merch",
        "auth": "manual",
        "tier": "manual",
        "supported": True,
        "tagline": "Manual export — phải apply tier mới upload được.",
        "setup_url": "https://merch.amazon.com/dashboard",
    },
    "spreadshirt": {
        "label": "Spreadshirt",
        "auth": "manual",
        "tier": "manual",
        "supported": True,
        "tagline": "Manual export — mạnh thị trường EU.",
        "setup_url": "https://www.spreadshirt.com/create-your-own",
    },
}
