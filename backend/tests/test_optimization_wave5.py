"""Wave 5 optimization tests:
- buyer-intent classifier (heuristic)
- retry queue transient/hard classification + backoff ladder
- P&L cost helpers + bucket aggregation
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

# ────────── Buyer-intent classifier ──────────


def test_intent_gift_phrases():
    from app.services.buyer_intent import classify_heuristic

    for p in [
        "best gift for mom on mothers day",
        "birthday gift for dad",
        "valentines present for boyfriend",
        "secret santa funny mug",
    ]:
        out = classify_heuristic(p)
        assert out.intent == "gift", f"{p!r} → {out}"
        assert out.confidence >= 0.6


def test_intent_personal_phrases():
    from app.services.buyer_intent import classify_heuristic

    for p in [
        "cat mom forever shirt",
        "plant lover queen tee",
        "vintage botanical aesthetic vibes",
        "pickleball obsessed dad",
    ]:
        out = classify_heuristic(p)
        assert out.intent in ("personal",), f"{p!r} → {out}"


def test_intent_decorative_phrases():
    from app.services.buyer_intent import classify_heuristic

    for p in [
        "minimalist abstract wall art",
        "geometric monochrome poster",
        "boho earth tones canvas print",
    ]:
        out = classify_heuristic(p)
        assert out.intent == "decorative", f"{p!r} → {out}"


def test_intent_informational_phrases_demoted():
    from app.services.buyer_intent import classify_heuristic

    for p in [
        "how to print on demand",
        "etsy fees calculator",
        "best printify alternatives review",
    ]:
        out = classify_heuristic(p)
        assert out.intent == "informational"
        # Boost factor must demote.
        assert out.boost_factor() < 1.0


def test_intent_boost_factor_ordering():
    from app.services.buyer_intent import IntentResult

    gift = IntentResult(intent="gift", confidence=1.0).boost_factor()
    personal = IntentResult(intent="personal", confidence=1.0).boost_factor()
    decorative = IntentResult(intent="decorative", confidence=1.0).boost_factor()
    info = IntentResult(intent="informational", confidence=1.0).boost_factor()
    assert gift > personal > decorative > info


def test_apply_intent_to_terms_reranks():
    from app.services.buyer_intent import apply_intent_to_terms
    from app.services.keywords.base import TrendingTerm

    terms = [
        TrendingTerm(term="how to use printify", source="x", score=80.0, raw={}),
        TrendingTerm(term="cat mom birthday gift", source="x", score=70.0, raw={}),
        TrendingTerm(term="minimal poster art", source="x", score=70.0, raw={}),
    ]
    out = apply_intent_to_terms(terms, db=None, user_id=None, use_ai=False)
    # The gift phrase must rank ABOVE the originally-higher informational one.
    assert out[0].term == "cat mom birthday gift"
    # Each survivor carries intent metadata.
    for t in out:
        assert "intent" in (t.raw or {})
        assert "intent_score" in (t.raw or {})


# ────────── Retry queue ──────────


def test_retry_transient_signatures():
    from app.services.retry_queue import is_transient

    transient = [
        "HTTP 429 Too Many Requests",
        "Rate-limit exceeded for shop_id=123",
        "Etsy returned 503 service unavailable",
        "Connection reset by peer",
        "Timeout while uploading image",
        "504 gateway timeout",
        "Network unreachable",
        "DNS resolution failed",
    ]
    for msg in transient:
        assert is_transient(msg), msg


def test_retry_hard_failure_signatures_not_transient():
    from app.services.retry_queue import is_transient

    hard = [
        "401 Unauthorized — invalid api key",
        "403 Forbidden",
        "Account suspended",
        "Validation failed: field 'tags' is missing",
        "Trademark hit on phrase",
        "Unsupported file format",
    ]
    for msg in hard:
        assert not is_transient(msg), msg


def test_retry_hard_pattern_takes_precedence():
    """A 429 string that ALSO matches a hard-fail pattern must not retry."""
    from app.services.retry_queue import is_transient

    # "validation failed" overrides the bare 5xx.
    assert not is_transient("503 returned but validation failed: missing payload field")


def test_backoff_ladder_monotone():
    from app.services.retry_queue import MAX_RETRIES, next_backoff

    last = timedelta(0)
    for i in range(MAX_RETRIES):
        b = next_backoff(i)
        assert b is not None and b > last
        last = b
    assert next_backoff(MAX_RETRIES) is None


def test_schedule_retry_mutates_product():
    from app.services.retry_queue import MAX_RETRIES, schedule_retry

    @dataclass
    class FakeProduct:
        retry_count: int = 0
        next_retry_at: datetime | None = None
        status: str = "draft"
        last_retry_error: str | None = None
        error: str | None = None

    p = FakeProduct()
    assert schedule_retry(p, RuntimeError("429 rate limit"))
    assert p.status == "pending_retry"
    assert p.retry_count == 1
    assert p.next_retry_at is not None
    assert p.next_retry_at > datetime.now(UTC)
    assert "429" in (p.last_retry_error or "")

    # Exhaust the ladder.
    p2 = FakeProduct(retry_count=MAX_RETRIES)
    assert not schedule_retry(p2, RuntimeError("still 429"))


# ────────── P&L cost helpers ──────────


def test_cost_for_engine_known_and_unknown():
    from app.services.pnl import cost_for_engine, cost_for_upscale

    assert cost_for_engine("openai") > 0
    assert cost_for_engine("gemini") == 0  # free tier
    assert cost_for_engine(None) == 0  # robust to None
    assert cost_for_engine("totally-fake-engine") == 0
    assert cost_for_upscale("replicate") > 0
    assert cost_for_upscale("pil_lanczos") == 0


def test_pnl_bucket_to_dict():
    from app.services.pnl import Bucket

    b = Bucket(label="2024-11-01", revenue_usd=42.0, cost_usd=10.5, profit_usd=31.5, orders=2, products=1)
    d = b.to_dict()
    assert d["label"] == "2024-11-01"
    assert d["profit_usd"] == 31.5
    assert d["orders"] == 2
