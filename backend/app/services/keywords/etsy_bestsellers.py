"""Scrape Etsy best-sellers page for trending listings in a niche.

Note: Scraping Etsy may violate their ToS. Use rate-limiting and only for
personal research. Prefer Etsy's official Taxonomy API once approved.
"""
from __future__ import annotations

import logging
import re
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from app.services.keywords.base import KeywordSource, TrendingTerm

logger = logging.getLogger(__name__)

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


class EtsyBestSellersSource(KeywordSource):
    name = "etsy"

    def fetch(self, seed: str, limit: int = 20) -> list[TrendingTerm]:
        url = f"https://www.etsy.com/search?q={quote_plus(seed)}&ref=pagination&page=1&explicit=1&order=most_sold"
        try:
            r = httpx.get(url, headers={"User-Agent": UA}, timeout=20, follow_redirects=True)
            r.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Etsy fetch failed: %s", exc)
            return []

        soup = BeautifulSoup(r.text, "lxml")
        terms: dict[str, float] = {}
        for a in soup.select("a[href*='/listing/']"):
            title = a.get_text(" ", strip=True)
            if not title or len(title) < 6:
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


_STOPWORDS = {
    "the", "and", "for", "with", "your", "you", "gift", "tshirt", "shirt", "tee",
    "men", "women", "kids", "funny", "cute", "best", "new", "cool", "vintage",
    "retro", "from", "that", "this", "will", "can", "have",
}
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]{2,}")


def _split_tokens(title: str) -> list[str]:
    tokens = [t.lower() for t in _WORD_RE.findall(title)]
    words = [t for t in tokens if t not in _STOPWORDS and len(t) > 3]
    # 2-gram terms
    bigrams = [
        f"{a} {b}"
        for a, b in zip(words, words[1:], strict=False)
        if a not in _STOPWORDS and b not in _STOPWORDS
    ]
    return bigrams or words
