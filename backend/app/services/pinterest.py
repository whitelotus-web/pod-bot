"""Pinterest auto-pin — free traffic from POD's #1 source.

After a product is published on Etsy, optionally pin it to a Pinterest board
the user has connected. We use the official Pinterest v5 API.

Two layers of failure tolerance:
1. If credentials aren't configured, return `skipped` and log — never crash
   the publish pipeline.
2. If Pinterest API errors, log and continue. Pinterest pins are nice-to-have,
   not critical-path.
"""
from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class PinResult:
    success: bool
    pin_id: str | None = None
    pin_url: str | None = None
    skipped: bool = False
    error: str = ""


@dataclass
class PinterestConfig:
    access_token: str
    board_id: str
    timeout_s: float = 15.0


def create_pin(
    config: PinterestConfig | None,
    *,
    image_url: str,
    title: str,
    description: str,
    link: str,
    alt_text: str = "",
    tags: Iterable[str] = (),
) -> PinResult:
    """Create a Pinterest pin from a public image URL."""
    if config is None or not config.access_token:
        return PinResult(success=False, skipped=True, error="no Pinterest config")

    payload = {
        "board_id": config.board_id,
        "title": title[:100] if title else "",
        "description": _build_description(description, tags),
        "alt_text": alt_text[:500] if alt_text else title[:500],
        "media_source": {
            "source_type": "image_url",
            "url": image_url,
        },
        "link": link,
    }
    headers = {
        "Authorization": f"Bearer {config.access_token}",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=config.timeout_s) as client:
            resp = client.post(
                "https://api.pinterest.com/v5/pins",
                json=payload,
                headers=headers,
            )
        if resp.status_code in (200, 201):
            data = resp.json()
            return PinResult(
                success=True,
                pin_id=data.get("id"),
                pin_url=f"https://www.pinterest.com/pin/{data.get('id')}/",
            )
        return PinResult(
            success=False,
            error=f"Pinterest API {resp.status_code}: {resp.text[:200]}",
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Pinterest pin failed: %s", exc)
        return PinResult(success=False, error=str(exc))


def _build_description(description: str, tags: Iterable[str]) -> str:
    """Combine description with hashtagged keywords; cap at 500 chars."""
    base = description.strip()
    tag_str = " ".join(f"#{t.replace(' ', '')}" for t in tags if t)[:200]
    out = f"{base}\n\n{tag_str}".strip() if tag_str else base
    return out[:500]
