"""Amazon Merch BSR scraper (shirts bestseller list).

Amazon aggressively blocks scrapers — use a residential proxy or fallback
to a third-party API (Keepa, Helium10). This implementation is intentionally
polite and best-effort; if it gets blocked it returns [].
"""
from __future__ import annotations

import logging
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from app.services.keywords.base import KeywordSource, TrendingTerm
from app.services.keywords.etsy_bestsellers import _split_tokens

logger = logging.getLogger(__name__)

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


class AmazonMerchBSRSource(KeywordSource):
    name = "amazon"

    def fetch(self, seed: str, limit: int = 20) -> list[TrendingTerm]:
        url = (
            f"https://www.amazon.com/s?k={quote_plus(seed + ' t-shirt')}"
            "&i=fashion&s=exact-aware-popularity-rank&rh=n%3A7141123011"
        )
        try:
            r = httpx.get(
                url,
                headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"},
                timeout=20,
                follow_redirects=True,
            )
            if r.status_code != 200 or "api-services-support" in r.text:
                logger.info("Amazon blocked or empty response")
                return []
        except Exception as exc:  # noqa: BLE001
            logger.warning("Amazon fetch failed: %s", exc)
            return []

        soup = BeautifulSoup(r.text, "lxml")
        terms: dict[str, int] = {}
        for h in soup.select("h2 span"):
            title = h.get_text(" ", strip=True)
            if not title:
                continue
            for kw in _split_tokens(title):
                terms[kw] = terms.get(kw, 0) + 1
        ranked = sorted(terms.items(), key=lambda x: x[1], reverse=True)[:limit]
        if not ranked:
            return []
        max_score = ranked[0][1] or 1
        return [
            TrendingTerm(term=t, source=self.name, score=(c / max_score) * 100, raw={"count": c})
            for t, c in ranked
        ]
