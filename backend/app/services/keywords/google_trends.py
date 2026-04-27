"""Google Trends via pytrends — free, no auth."""
from __future__ import annotations

import logging

from app.services.keywords.base import KeywordSource, TrendingTerm

logger = logging.getLogger(__name__)


class GoogleTrendsSource(KeywordSource):
    name = "google_trends"

    def fetch(self, seed: str, limit: int = 20) -> list[TrendingTerm]:
        try:
            from pytrends.request import TrendReq
        except ImportError:
            logger.warning("pytrends not installed")
            return []

        try:
            pytrends = TrendReq(hl="en-US", tz=360, timeout=(10, 25))
            pytrends.build_payload([seed], timeframe="now 7-d", geo="US")
            related = pytrends.related_queries().get(seed) or {}
            out: list[TrendingTerm] = []
            for bucket in ("rising", "top"):
                df = related.get(bucket)
                if df is None or df.empty:
                    continue
                for _, row in df.head(limit).iterrows():
                    out.append(
                        TrendingTerm(
                            term=str(row["query"]),
                            source=self.name,
                            score=float(row.get("value", 0) or 0),
                            raw={"bucket": bucket},
                        )
                    )
            # Normalise score 0-100
            if out:
                max_score = max(t.score for t in out) or 1.0
                for t in out:
                    t.score = (t.score / max_score) * 100
            return out[:limit]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Google Trends fetch failed: %s", exc)
            return []
