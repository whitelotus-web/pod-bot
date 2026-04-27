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
    from app.services.platforms.merch_amazon import MerchAmazonPlatform
    from app.services.platforms.printful import PrintfulPlatform
    from app.services.platforms.printify import PrintifyPlatform
    from app.services.platforms.redbubble import RedbubblePlatform
    from app.services.platforms.teespring import TeespringPlatform

    registry: dict[str, type[PODPlatform]] = {
        "printify": PrintifyPlatform,
        "printful": PrintfulPlatform,
        "etsy": EtsyPlatform,
        "redbubble": RedbubblePlatform,
        "teespring": TeespringPlatform,
        "merch_amazon": MerchAmazonPlatform,
    }
    cls = registry.get(platform_name)
    if cls is None:
        raise ValueError(f"Unknown platform: {platform_name}")
    return cls(account)


PLATFORM_META = {
    "printify": {"label": "Printify", "auth": "api_key", "supported": True},
    "printful": {"label": "Printful", "auth": "api_key", "supported": True},
    "etsy": {"label": "Etsy", "auth": "oauth2", "supported": True},
    "redbubble": {"label": "Redbubble", "auth": "selenium", "supported": False},
    "teespring": {"label": "Teespring / Spring", "auth": "selenium", "supported": False},
    "merch_amazon": {"label": "Merch by Amazon", "auth": "selenium", "supported": False},
}
