"""Long-tail keyword expander + seasonal calendar.

Two purposes:

1. **expand_long_tail**: take a seed niche/keyword and emit 15-30 long-tail
   variants that buyers actually search. Long-tails ("vintage cat mom shirt
   for crazy cat lady") convert ~3x better than head terms ("cat shirt").
   Uses the `keyword_expansion` AI role if a key is configured, else a
   deterministic template-based generator that mixes intent modifiers + niche
   tokens.

2. **seasonal_keywords**: surface holidays/seasons relevant to today's date
   so the pipeline can pre-stage product 6-8 weeks before peak demand
   (Etsy ranks listings by sales velocity, so being early matters).

We intentionally don't ping any external scoring API here — the result is
fed into the trademark filter and momentum tracker which do the scoring.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import date

logger = logging.getLogger(__name__)

# Modifiers grouped by buyer intent.
INTENT_MODIFIERS: dict[str, tuple[str, ...]] = {
    "gift": (
        "gift for {n}", "gift for {n} mom", "gift for {n} dad",
        "birthday gift for {n}", "christmas gift for {n}",
        "{n} mothers day gift", "secret santa {n}",
    ),
    "personal": (
        "{n} aesthetic", "minimalist {n}", "vintage {n}",
        "retro {n}", "boho {n}", "kawaii {n}", "cottagecore {n}",
    ),
    "occasion": (
        "{n} wedding", "{n} engagement", "{n} graduation",
        "{n} bachelorette", "{n} new home", "{n} retirement",
    ),
    "audience": (
        "{n} for women", "{n} for men", "{n} for teens",
        "{n} for kids", "plus size {n}", "matching {n} couple",
    ),
    "modifier": (
        "funny {n}", "cute {n}", "sarcastic {n}", "inspirational {n}",
        "motivational {n}", "spiritual {n}",
    ),
}


# Seasonal calendar — anchor date + suggested keyword head terms.
@dataclass(frozen=True)
class SeasonalEvent:
    name: str
    month: int
    day: int
    push_weeks_before: int  # how early to start designing
    seed_keywords: tuple[str, ...]


SEASONAL_EVENTS: tuple[SeasonalEvent, ...] = (
    SeasonalEvent("Valentine's Day", 2, 14, 6, ("valentines day", "love", "couple", "anti valentine")),
    SeasonalEvent("St. Patrick's Day", 3, 17, 4, ("st patricks day", "irish", "shamrock", "lucky")),
    SeasonalEvent("Easter", 4, 1, 4, ("easter", "spring", "bunny", "pastel")),
    SeasonalEvent("Mother's Day (US)", 5, 12, 6, ("mothers day", "mom", "mama", "best mom")),
    SeasonalEvent("Father's Day (US)", 6, 16, 6, ("fathers day", "dad", "papa", "best dad")),
    SeasonalEvent("Pride Month", 6, 1, 4, ("pride", "lgbtq", "rainbow", "love is love")),
    SeasonalEvent("4th of July", 7, 4, 4, ("independence day", "fourth of july", "patriotic", "usa")),
    SeasonalEvent("Back to School", 8, 20, 4, ("back to school", "teacher", "first day", "kindergarten")),
    SeasonalEvent("Halloween", 10, 31, 8, ("halloween", "spooky", "witch", "pumpkin", "horror", "vintage horror")),
    SeasonalEvent("Thanksgiving", 11, 28, 6, ("thanksgiving", "fall", "turkey", "grateful", "autumn")),
    SeasonalEvent("Black Friday", 11, 28, 4, ("black friday", "cyber monday", "sale")),
    SeasonalEvent("Christmas", 12, 25, 8, ("christmas", "ugly sweater", "holiday", "santa", "winter", "xmas")),
    SeasonalEvent("New Year", 1, 1, 4, ("new year", "resolution", "2026 vibes", "january")),
)


@dataclass
class LongTailResult:
    keywords: list[str]
    source: str  # "ai" | "template"


_AI_PROMPT = """Generate {count} Etsy long-tail search keywords for the niche
\"{niche}\" with seed keyword \"{keyword}\".

Rules:
- Each keyword 3-8 words, lowercase, no special chars or punctuation.
- Mix buyer intents: gift, occasion, audience, aesthetic.
- Avoid trademarked phrases (Disney/Marvel/Pokemon/etc).
- No duplicates; semantically distinct ideas.

Output STRICT JSON: {{"keywords": ["...", "..."]}}
"""


def _normalize(s: str) -> str:
    s = re.sub(r"[^a-z0-9 ]+", " ", s.lower()).strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _template_expand(niche: str, keyword: str, count: int) -> list[str]:
    """Generate long-tails by combining intent modifiers with the niche tokens."""
    n = _normalize(niche or keyword)
    if not n:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for mods in INTENT_MODIFIERS.values():
        for tpl in mods:
            phrase = tpl.format(n=n)
            phrase = _normalize(phrase)
            if phrase and phrase not in seen and len(phrase.split()) <= 8:
                seen.add(phrase)
                out.append(phrase)
            if len(out) >= count:
                return out
    return out


def expand_long_tail(
    niche: str,
    *,
    keyword: str = "",
    count: int = 20,
    ai_caller=None,  # callable: (prompt: str) -> str (raw model response)
) -> LongTailResult:
    """Return long-tail variants. AI caller is optional — fall back to template."""
    keyword = keyword or niche
    if ai_caller is not None:
        try:
            raw = ai_caller(_AI_PROMPT.format(niche=niche, keyword=keyword, count=count))
            text = re.sub(r"^```json\s*|\s*```$", "", (raw or "").strip())
            data = json.loads(text)
            kws = data.get("keywords", []) if isinstance(data, dict) else []
            cleaned: list[str] = []
            seen: set[str] = set()
            for k in kws:
                norm = _normalize(str(k))
                if 2 <= len(norm.split()) <= 8 and norm not in seen:
                    seen.add(norm)
                    cleaned.append(norm)
            if len(cleaned) >= count // 2:
                return LongTailResult(keywords=cleaned[:count], source="ai")
        except Exception as exc:  # noqa: BLE001
            logger.warning("long-tail AI expansion failed, falling back to template: %s", exc)

    return LongTailResult(
        keywords=_template_expand(niche, keyword, count),
        source="template",
    )


def upcoming_seasonal_events(
    today: date | None = None,
    *,
    weeks_ahead: int = 12,
) -> list[SeasonalEvent]:
    """Events whose `push_weeks_before` window includes today + (0..weeks_ahead)."""
    today = today or date.today()
    # Keep the computed evt_date alongside the event so we can sort
    # chronologically — sorting by (month, day) breaks across the year
    # boundary (e.g. on Nov 1, January's New Year would sort before
    # December's Christmas even though Christmas occurs first).
    upcoming: list[tuple[date, SeasonalEvent]] = []
    for evt in SEASONAL_EVENTS:
        year = today.year
        try:
            evt_date = date(year, evt.month, evt.day)
        except ValueError:
            continue
        if evt_date < today:
            try:
                evt_date = date(year + 1, evt.month, evt.day)
            except ValueError:
                continue
        delta_days = (evt_date - today).days
        if delta_days <= evt.push_weeks_before * 7 + weeks_ahead * 7:
            upcoming.append((evt_date, evt))
    upcoming.sort(key=lambda pair: pair[0])
    return [evt for _, evt in upcoming]


def seasonal_keyword_seeds(today: date | None = None) -> list[tuple[str, str]]:
    """Return [(event_name, seed_keyword), ...] for events to push now."""
    today = today or date.today()
    out: list[tuple[str, str]] = []
    for evt in upcoming_seasonal_events(today):
        for seed in evt.seed_keywords:
            out.append((evt.name, seed))
    return out
