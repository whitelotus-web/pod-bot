"""TikTok Creative Center — unofficial endpoint for trending keywords.

The endpoint format may change; treat failures as non-fatal.
"""
from __future__ import annotations

import logging

import httpx

from app.core.config import settings
from app.services.keywords.base import KeywordSource, TrendingTerm

logger = logging.getLogger(__name__)

API = "https://ads.tiktok.com/business/creativecenter/inspiration/popular/hashtag/pc/en"


class TikTokTrendsSource(KeywordSource):
    name = "tiktok"

    def fetch(self, seed: str, limit: int = 20) -> list[TrendingTerm]:
        url = (
            "https://ads.tiktok.com/creative_radar_api/v1/popular_trend/hashtag/list"
            f"?period=7&page=1&limit={limit}&country_code=US"
        )
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": API,
            "Accept": "application/json",
        }
        if settings.tiktok_cookie:
            headers["Cookie"] = settings.tiktok_cookie
        try:
            r = httpx.get(url, headers=headers, timeout=15)
            r.raise_for_status()
            data = r.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("TikTok fetch failed: %s", exc)
            return []

        items = data.get("data", {}).get("list", [])
        out: list[TrendingTerm] = []
        for i, item in enumerate(items[:limit]):
            term = (item.get("hashtag_name") or "").strip()
            if not term:
                continue
            rank = item.get("rank") or i + 1
            score = 100 * (1 - (rank - 1) / max(limit, 1))
            out.append(
                TrendingTerm(
                    term=term,
                    source=self.name,
                    score=score,
                    raw={"publish_cnt": item.get("publish_cnt"), "rank": rank},
                )
            )
        # Crude seed-relevance filter
        if seed:
            seed_l = seed.lower()
            out = [t for t in out if any(tok in t.term.lower() for tok in seed_l.split())] or out
        return out
