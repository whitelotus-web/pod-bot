"""Pinterest Trends — unofficial endpoint.

The official endpoint is https://trends.pinterest.com/ but it requires a
logged-in session. We fall back to the autocomplete endpoint which is
publicly available.
"""
from __future__ import annotations

import logging
from urllib.parse import quote_plus

import httpx

from app.core.config import settings
from app.services.keywords.base import KeywordSource, TrendingTerm

logger = logging.getLogger(__name__)


class PinterestTrendsSource(KeywordSource):
    name = "pinterest"

    def fetch(self, seed: str, limit: int = 20) -> list[TrendingTerm]:
        url = f"https://www.pinterest.com/resource/AdvancedTypeaheadResource/get/?source_url=/search/pins/?q={quote_plus(seed)}&data=%7B%22options%22%3A%7B%22term%22%3A%22{quote_plus(seed)}%22%7D%7D"
        headers = {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"}
        if settings.pinterest_cookie:
            headers["Cookie"] = settings.pinterest_cookie
        try:
            r = httpx.get(url, headers=headers, timeout=15)
            r.raise_for_status()
            data = r.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Pinterest fetch failed: %s", exc)
            return []

        resources = (
            data.get("resource_response", {}).get("data", {}).get("typeahead", [])
            or data.get("resource_response", {}).get("data", [])
        )
        out: list[TrendingTerm] = []
        for i, item in enumerate(resources[:limit]):
            term = (item.get("display") or item.get("term") or "").strip()
            if not term:
                continue
            score = 100 * (1 - i / max(limit, 1))
            out.append(TrendingTerm(term=term, source=self.name, score=score))
        return out
