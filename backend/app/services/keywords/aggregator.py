"""Aggregate multiple KeywordSource outputs into a ranked list."""
from __future__ import annotations

import logging
from collections import defaultdict

from app.services.keywords.amazon_bsr import AmazonMerchBSRSource
from app.services.keywords.base import KeywordSource, TrendingTerm
from app.services.keywords.etsy_bestsellers import EtsyBestSellersSource
from app.services.keywords.google_trends import GoogleTrendsSource
from app.services.keywords.pinterest import PinterestTrendsSource
from app.services.keywords.tiktok import TikTokTrendsSource

logger = logging.getLogger(__name__)

SOURCE_REGISTRY: dict[str, type[KeywordSource]] = {
    "google_trends": GoogleTrendsSource,
    "etsy": EtsyBestSellersSource,
    "amazon": AmazonMerchBSRSource,
    "pinterest": PinterestTrendsSource,
    "tiktok": TikTokTrendsSource,
}

ALL_SOURCES = list(SOURCE_REGISTRY.keys())


class KeywordAggregator:
    """Fetch from multiple sources and merge by term → average score."""

    def __init__(self, source_names: list[str] | None = None):
        names = source_names or ALL_SOURCES
        self.sources: list[KeywordSource] = []
        for name in names:
            cls = SOURCE_REGISTRY.get(name)
            if cls is None:
                logger.warning("Unknown keyword source: %s", name)
                continue
            self.sources.append(cls())

    def run(self, seed: str, limit_per_source: int = 20, top: int = 30) -> list[TrendingTerm]:
        pooled: dict[str, list[TrendingTerm]] = defaultdict(list)
        for src in self.sources:
            try:
                items = src.fetch(seed, limit=limit_per_source)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Source %s failed: %s", src.name, exc)
                items = []
            for it in items:
                key = it.term.strip().lower()
                if key:
                    pooled[key].append(it)

        merged: list[TrendingTerm] = []
        for _key, occs in pooled.items():
            avg = sum(o.score for o in occs) / len(occs)
            # Bonus for appearing in multiple sources
            boost = min(1.0, 0.15 * (len(occs) - 1))
            score = min(100.0, avg * (1 + boost))
            merged.append(
                TrendingTerm(
                    term=occs[0].term,
                    source="+".join(sorted({o.source for o in occs})),
                    score=score,
                    raw={"occurrences": len(occs), "sources": [o.source for o in occs]},
                )
            )

        merged.sort(key=lambda t: t.score, reverse=True)
        return merged[:top]
