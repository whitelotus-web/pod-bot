"""Buyer-intent classifier for keyword scoring.

Classifies a keyword phrase into one of four buyer intents:

- ``gift``         — the buyer wants to give the item to someone
                     ("gift for dad", "best friend birthday")
- ``personal``     — the buyer wants the item for themselves and the phrase
                     reveals identity / niche affinity
                     ("cat mom", "vintage botanical lover")
- ``decorative``   — the buyer is shopping for visual appeal but no clear
                     identity / use-case ("aesthetic poster", "minimal art")
- ``informational``— low purchase intent (research / how-to / news)
                     ("how to print on demand", "etsy fees calculator")

Strategy
========
1. **Heuristic pass** (always runs, no AI keys required): regex + token
   matching against curated dictionaries. Returns intent + confidence in
   [0, 1].
2. **Optional AI refinement** (called only when ``user_id`` + ``db`` are
   passed): if the heuristic confidence is low (<0.5), ask an
   ``ai_router``-routed LLM (Gemini → OpenAI fallback) to classify.

The pipeline calls :func:`apply_intent_to_terms` after
:class:`KeywordAggregator.run`, before persisting to the ``keywords`` table.
The intent is then used to:

- **boost** ``score`` for high-buyer-intent terms (gift +25%, personal +15%)
- **demote** ``score`` for informational terms (-50%) so they sink to the
  bottom of the rank but remain queryable for analytics.
- **store** ``intent`` + ``intent_score`` columns for the dashboard.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)

Intent = Literal["gift", "personal", "decorative", "informational"]

# --- Heuristic dictionaries -------------------------------------------------

# Strong "for someone else" signals → gift intent
_GIFT_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bgift(s)?\b",
        r"\bpresent\b",
        r"\bfor (her|him|mom|dad|mother|father|wife|husband|girlfriend|boyfriend|friend|grandma|grandpa|sister|brother|son|daughter|kids?|teens?|coworker|teacher|nurse|doctor)\b",
        r"\b(birthday|wedding|anniversary|christmas|xmas|valentine|valentines|mothers? day|fathers? day|graduation|baby shower|bridal shower|housewarming)\b",
        r"\bthank ?you\b",
        r"\bsecret santa\b",
    )
)

# Self-identification niche markers → personal intent
# (any of these tokens immediately after a niche keyword)
_PERSONAL_TOKENS: frozenset[str] = frozenset(
    {
        "mom", "mama", "mother", "dad", "papa", "father",
        "lover", "addict", "obsessed", "enthusiast", "fan", "fanatic",
        "queen", "king", "princess", "prince", "boss", "girl", "boy",
        "vibes", "energy", "era", "core", "aesthetic",
        "life", "club", "crew", "tribe", "gang", "squad",
        "lady", "guy", "girlie", "bro", "babe",
    }
)

# Decorative / visual-only signals
_DECORATIVE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\b(aesthetic|minimal|minimalist|abstract|geometric|boho|wall art|home decor|poster|print|canvas|painting|illustration|design|art print)\b",
        r"\b(black and white|monochrome|pastel|neutral|earth tones?)\b",
    )
)

# Low-intent / informational
_INFO_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"^\s*(how|what|why|when|where|which|who)\s+",
        r"\b(tutorial|guide|tips?|review|reviews|vs\.?|comparison|calculator|free|download|template|coupon|discount code)\b",
        r"\b(meaning|definition|explained)\b",
    )
)


@dataclass(frozen=True)
class IntentResult:
    intent: Intent
    confidence: float  # 0..1

    def boost_factor(self) -> float:
        """Multiplier applied to a keyword's base score to reflect intent.

        Gift > Personal > Decorative > Informational.
        """
        if self.intent == "gift":
            return 1.0 + 0.25 * self.confidence
        if self.intent == "personal":
            return 1.0 + 0.15 * self.confidence
        if self.intent == "decorative":
            return 1.0
        # informational — demote sharply
        return 1.0 - 0.5 * self.confidence


def classify_heuristic(phrase: str) -> IntentResult:
    """Run the deterministic regex/token classifier.

    Returns the highest-scoring intent. Always returns a result (never None)
    so callers can chain to AI refinement only when confidence is low.
    """
    text = (phrase or "").strip()
    if not text:
        return IntentResult(intent="decorative", confidence=0.0)

    # Score each intent independently then pick the winner.
    info_hits = sum(1 for p in _INFO_PATTERNS if p.search(text))
    if info_hits:
        return IntentResult(intent="informational", confidence=min(1.0, 0.5 + 0.25 * info_hits))

    gift_hits = sum(1 for p in _GIFT_PATTERNS if p.search(text))
    if gift_hits:
        return IntentResult(intent="gift", confidence=min(1.0, 0.6 + 0.2 * gift_hits))

    tokens = re.findall(r"[a-z']+", text.lower())
    personal_hits = sum(1 for t in tokens if t in _PERSONAL_TOKENS)
    if personal_hits:
        return IntentResult(
            intent="personal", confidence=min(1.0, 0.55 + 0.2 * personal_hits)
        )

    decorative_hits = sum(1 for p in _DECORATIVE_PATTERNS if p.search(text))
    if decorative_hits:
        return IntentResult(
            intent="decorative", confidence=min(1.0, 0.4 + 0.2 * decorative_hits)
        )

    # Nothing matched — assume decorative with low confidence.
    return IntentResult(intent="decorative", confidence=0.2)


# --- Optional AI refinement -------------------------------------------------

_AI_PROMPT = (
    "Classify the e-commerce search phrase below into ONE of: "
    "'gift', 'personal', 'decorative', 'informational'.\n\n"
    "Definitions:\n"
    "- gift: shopper buys for someone else (birthday, anniversary, 'for mom', etc.)\n"
    "- personal: shopper buys for themselves and reveals identity/niche affinity\n"
    "- decorative: visual decor, no clear personal/gift signal\n"
    "- informational: research / how-to / not a purchase intent\n\n"
    "Output STRICT JSON: {{\"intent\": \"...\", \"confidence\": 0.0..1.0}}\n"
    "Phrase: {phrase}"
)


def _ai_refine(phrase: str, *, db, user_id: int) -> IntentResult | None:
    """Call the LLM-backed classifier through ``ai_router.with_failover``.

    Returns None (caller falls back to the heuristic) if no key is available
    or every key fails. Quota errors rotate to the next candidate engine
    automatically via ``with_failover``.
    """
    try:
        from app.services.ai_router import AIKeyCandidate, AISoftError, with_failover
    except Exception:  # noqa: BLE001 — import must never crash classify pipeline
        return None

    def _call(cand: AIKeyCandidate) -> IntentResult:
        if not cand.api_key:
            raise AISoftError("missing api key")
        if cand.engine == "gemini":
            return _ai_gemini(phrase, cand.api_key)
        if cand.engine == "openai":
            return _ai_openai(phrase, cand.api_key)
        raise AISoftError(f"buyer_intent unsupported on engine {cand.engine}")

    try:
        return with_failover(
            db, user_id=user_id, role="seo_writer", engine=None, fn=_call
        )
    except Exception as exc:  # noqa: BLE001
        logger.info("buyer_intent AI failover exhausted (%s) — using heuristic.", exc)
        return None


def _parse_ai_json(text: str) -> IntentResult | None:
    text = re.sub(r"^```json\s*|\s*```$", "", (text or "").strip())
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    intent = str(data.get("intent", "")).lower().strip()
    if intent not in ("gift", "personal", "decorative", "informational"):
        return None
    try:
        conf = float(data.get("confidence", 0.5))
    except (TypeError, ValueError):
        conf = 0.5
    return IntentResult(intent=intent, confidence=max(0.0, min(1.0, conf)))


def _ai_gemini(phrase: str, api_key: str) -> IntentResult:
    from google import genai

    client = genai.Client(api_key=api_key)
    resp = client.models.generate_content(
        model="gemini-2.5-flash", contents=_AI_PROMPT.format(phrase=phrase)
    )
    out = _parse_ai_json(resp.text or "")
    if out is None:
        from app.services.ai_router import AISoftError

        raise AISoftError("buyer_intent gemini returned unparseable JSON")
    return out


def _ai_openai(phrase: str, api_key: str) -> IntentResult:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": _AI_PROMPT.format(phrase=phrase)}],
        response_format={"type": "json_object"},
    )
    text = resp.choices[0].message.content or ""
    out = _parse_ai_json(text)
    if out is None:
        from app.services.ai_router import AISoftError

        raise AISoftError("buyer_intent openai returned unparseable JSON")
    return out


# --- Public API -------------------------------------------------------------


def classify(
    phrase: str,
    *,
    db=None,
    user_id: int | None = None,
    use_ai_when_unsure: bool = True,
    confidence_threshold: float = 0.5,
) -> IntentResult:
    """Classify ``phrase`` into a buyer intent.

    Always returns a result. If ``use_ai_when_unsure`` is True and the
    heuristic confidence is below ``confidence_threshold``, attempt to
    refine via the user's role-scoped LLM keys.
    """
    out = classify_heuristic(phrase)
    if (
        use_ai_when_unsure
        and out.confidence < confidence_threshold
        and db is not None
        and user_id is not None
    ):
        refined = _ai_refine(phrase, db=db, user_id=user_id)
        if refined is not None and refined.confidence >= out.confidence:
            return refined
    return out


def apply_intent_to_terms(
    terms,
    *,
    db=None,
    user_id: int | None = None,
    use_ai: bool = False,
):
    """Annotate a list of :class:`TrendingTerm` with buyer intent.

    Mutates each term's ``raw`` dict to include ``intent`` + ``intent_score``
    and rescales ``score`` by :meth:`IntentResult.boost_factor`.

    ``use_ai=False`` by default to keep the scout pipeline fast and quota-cheap;
    pipelines can re-classify the top-N via ``classify()`` if they want
    AI-refined intent on the survivors.
    """
    out = []
    for t in terms:
        result = classify(t.term, db=db, user_id=user_id, use_ai_when_unsure=use_ai)
        new_score = max(0.0, min(100.0, t.score * result.boost_factor()))
        raw = dict(t.raw or {})
        raw.update(intent=result.intent, intent_score=result.confidence)
        # Build a new instance so we don't depend on mutability of TrendingTerm.
        out.append(
            type(t)(term=t.term, source=t.source, score=new_score, raw=raw)
        )
    out.sort(key=lambda x: x.score, reverse=True)
    return out
