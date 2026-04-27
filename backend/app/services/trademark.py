"""Trademark / Copyright Shield.

Two layers of protection so the pipeline never publishes a phrase or design
keyword that is likely to get the shop banned:

1. **Blacklist (built-in + user-managed)**: hard-coded list of well-known
   protected brands / phrases (Disney, Star Wars, NBA, etc.) plus a DB-backed
   user blacklist they can extend per-shop.
2. **USPTO TESS check (best-effort)**: HTTPS request to USPTO trademark search
   API. If the API is unreachable or the user hasn't enabled it, this layer is
   skipped and only the blacklist runs (fail-open on infra error, fail-closed
   on confirmed match).

Used at three points in the pipeline:
- before keyword expansion ("input gate")
- before AI design generation
- before publish to platform

If a phrase is flagged, the design / listing is rejected and a `RunLog` entry
is written with the reason. This prevents the "shop bay màu" failure mode
described by the user.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


# Hard-coded high-risk phrases. Curated from public Etsy DMCA takedown data
# and the most-reported brands in the POD community. Lowercase, normalised.
BUILTIN_BLACKLIST: frozenset[str] = frozenset(
    {
        # Disney
        "disney", "mickey", "mickey mouse", "minnie mouse", "donald duck",
        "frozen", "elsa frozen", "anna frozen", "moana", "encanto",
        "pixar", "toy story", "buzz lightyear", "woody",
        "marvel", "spider-man", "spiderman", "iron man", "captain america",
        "thor", "hulk", "black widow", "loki", "thanos", "deadpool",
        "x-men", "wolverine", "wakanda",
        # Star Wars / Lucasfilm
        "star wars", "darth vader", "yoda", "baby yoda", "grogu",
        "mandalorian", "skywalker", "jedi", "sith", "stormtrooper",
        "millennium falcon", "death star", "may the 4th",
        # Warner / DC
        "batman", "superman", "wonder woman", "aquaman", "the flash",
        "joker", "harley quinn", "justice league", "harry potter",
        "hogwarts", "gryffindor", "slytherin", "ravenclaw", "hufflepuff",
        "lord of the rings", "frodo", "gandalf", "middle earth",
        # Sports leagues
        "nba", "nfl", "mlb", "nhl", "ufc", "fifa world cup",
        "lakers", "yankees", "patriots", "warriors",
        # Music / Celebrities (extremely litigious)
        "taylor swift", "beyonce", "rihanna", "kanye west", "drake",
        "elvis presley", "the beatles",
        # Anime / Manga (Toei, Shueisha, etc. file frequent DMCA)
        "naruto", "one piece", "dragon ball", "goku", "vegeta",
        "pokemon", "pikachu", "sailor moon", "studio ghibli", "totoro",
        "demon slayer", "tanjiro", "attack on titan", "jujutsu kaisen",
        # Games
        "minecraft", "fortnite", "call of duty", "grand theft auto",
        "world of warcraft", "league of legends", "valorant", "roblox",
        "nintendo", "mario", "luigi", "zelda", "link zelda",
        "playstation", "xbox",
        # TV
        "stranger things", "game of thrones", "house of dragon",
        "the office", "friends tv", "breaking bad", "the simpsons",
        # Fashion / Brand
        "nike", "adidas", "puma", "supreme",
        "louis vuitton", "gucci", "chanel", "prada", "rolex",
        "starbucks", "coca cola", "mcdonalds", "tesla brand",
        # Olympics / events (USOC very aggressive)
        "olympics", "olympic games", "paris 2024", "paralympics",
        "super bowl", "world cup",
    }
)


# Phrases to never rewrite (substring match, case-insensitive).
# These are fuzzier — match anywhere in the text.
SUBSTRING_BLACKLIST: tuple[str, ...] = (
    "® ", " ®", "™",
    "official", "licensed",
    "copyright ©", "all rights reserved",
)


@dataclass
class TrademarkResult:
    """Outcome of a trademark check.

    `safe`: caller can proceed.
    `reason`: human-readable explanation (always set when not safe).
    `matched_phrase`: which entry in the blacklist matched (if any).
    `source`: which layer flagged it (`builtin` | `user_blacklist` | `uspto`).
    """

    safe: bool
    reason: str = ""
    matched_phrase: str = ""
    source: str = ""


_NORMALIZE = re.compile(r"[^a-z0-9 ]+")


def _normalize(text: str) -> str:
    return _NORMALIZE.sub(" ", (text or "").lower()).strip()


def _check_blacklist(
    text_norm: str, blacklist: Iterable[str], source: str
) -> TrademarkResult | None:
    """Return a hit (TrademarkResult with safe=False) or None."""
    for phrase in blacklist:
        # Normalize the blacklist phrase the same way as the input text so that
        # entries with hyphens / punctuation (e.g. "spider-man", "x-men",
        # "coca-cola") still match user input regardless of separator.
        p = _normalize(phrase)
        if not p:
            continue
        # Whole-phrase or word-boundary match for short phrases (1-2 words).
        if " " in p:
            if p in text_norm:
                return TrademarkResult(
                    safe=False,
                    reason=f"Phrase '{phrase}' is a known protected trademark.",
                    matched_phrase=phrase,
                    source=source,
                )
        else:
            # Word boundary match for single tokens.
            if re.search(rf"\b{re.escape(p)}\b", text_norm):
                return TrademarkResult(
                    safe=False,
                    reason=f"Word '{phrase}' is a known protected trademark.",
                    matched_phrase=phrase,
                    source=source,
                )
    return None


def _check_substring(text: str) -> TrademarkResult | None:
    lower = text.lower()
    for sub in SUBSTRING_BLACKLIST:
        if sub.lower() in lower:
            return TrademarkResult(
                safe=False,
                reason=f"Reserved marker '{sub.strip()}' is not allowed in user-generated listings.",
                matched_phrase=sub.strip(),
                source="builtin",
            )
    return None


def check_phrase(
    text: str,
    *,
    user_blacklist: Iterable[str] = (),
    enable_uspto: bool = False,
    uspto_timeout_s: float = 3.0,
) -> TrademarkResult:
    """Layered trademark check.

    Order: substring markers → builtin blacklist → user blacklist → USPTO TESS.
    First hit wins. If all clean, returns safe=True.

    USPTO is best-effort — if the network call fails, we log and continue
    (fail-open on infra). A confirmed match is fail-closed.
    """
    if not text:
        return TrademarkResult(safe=True)

    if hit := _check_substring(text):
        return hit

    norm = _normalize(text)

    if hit := _check_blacklist(norm, BUILTIN_BLACKLIST, source="builtin"):
        return hit

    if user_blacklist:
        if hit := _check_blacklist(norm, user_blacklist, source="user_blacklist"):
            return hit

    if enable_uspto:
        try:
            return _check_uspto(text, timeout_s=uspto_timeout_s) or TrademarkResult(safe=True)
        except Exception as exc:  # noqa: BLE001
            logger.warning("USPTO TESS check failed (fail-open): %s", exc)

    return TrademarkResult(safe=True)


def _check_uspto(text: str, timeout_s: float = 3.0) -> TrademarkResult | None:
    """Best-effort USPTO TESS API check.

    USPTO doesn't have a free first-party JSON API, so we use the public
    `tsdrapi.uspto.gov` search endpoint. We only consider 'live' marks
    (status code starting with 6) classified as goods/services that overlap
    apparel/printables (classes 16, 18, 21, 25, 28, 35).

    Returns:
      None  → no match found, caller should treat as safe at this layer.
      TrademarkResult(safe=False) → confirmed live trademark match.
    """
    url = "https://tsdrapi.uspto.gov/ts/cd/casestatus/sn"
    params = {"caseSearchString": text[:80]}
    try:
        with httpx.Client(timeout=timeout_s) as client:
            resp = client.get(url, params=params)
            if resp.status_code != 200:
                return None
            data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else None
            if not isinstance(data, list):
                return None
            for entry in data:
                status = str(entry.get("statusCode", "")).strip()
                if status.startswith("6"):  # live
                    cls = str(entry.get("internationalClass", "")).strip()
                    if cls in {"16", "18", "21", "25", "28", "35"}:
                        return TrademarkResult(
                            safe=False,
                            reason=f"USPTO live trademark match (class {cls}).",
                            matched_phrase=str(entry.get("markIdentification", "")),
                            source="uspto",
                        )
    except Exception:  # noqa: BLE001
        return None
    return None


def filter_keywords(
    keywords: list[str],
    *,
    user_blacklist: Iterable[str] = (),
    enable_uspto: bool = False,
) -> tuple[list[str], list[tuple[str, str]]]:
    """Filter a keyword list. Returns (safe_keywords, rejected_with_reason)."""
    safe: list[str] = []
    rejected: list[tuple[str, str]] = []
    for kw in keywords:
        result = check_phrase(kw, user_blacklist=user_blacklist, enable_uspto=enable_uspto)
        if result.safe:
            safe.append(kw)
        else:
            rejected.append((kw, result.reason))
            logger.info("Trademark filter rejected '%s': %s", kw, result.reason)
    return safe, rejected
