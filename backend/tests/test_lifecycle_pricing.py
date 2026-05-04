"""Tests for Wave 2: momentum, lifecycle, pricing, long-tail, pinterest."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

# ─────── Momentum ───────


def test_momentum_rising_series():
    from app.services.momentum import _synthesize_series, compute

    series = _synthesize_series(start_volume=100, days=45, daily_growth_pct=0.03)
    snap = compute(series)

    assert snap.sma_7 is not None and snap.sma_30 is not None
    assert snap.sma_7 > snap.sma_30  # bullish crossover
    assert snap.momentum_score > 60
    assert snap.label in ("rising", "breakout")


def test_momentum_flat_series():
    from app.services.momentum import _synthesize_series, compute

    series = _synthesize_series(start_volume=100, days=45, daily_growth_pct=0.0)
    snap = compute(series)
    # Flat series means SMA 7 ≈ SMA 30
    assert snap.label in ("flat", "rising")


def test_momentum_falling_series():
    from app.services.momentum import _synthesize_series, compute

    series = _synthesize_series(start_volume=100, days=45, daily_growth_pct=-0.02)
    snap = compute(series)
    assert snap.momentum_score < 50
    assert snap.label in ("flat", "falling")


def test_momentum_handles_short_series():
    from app.services.momentum import compute

    snap = compute([(date.today() - timedelta(days=i), 50) for i in range(5)])
    assert snap.sma_30 is None  # not enough data
    assert snap.momentum_score >= 0


def test_momentum_rsi_overbought():
    """Pure straight-line growth → RSI extremely high (overbought)."""
    from app.services.momentum import _rsi

    values = [float(i) for i in range(1, 30)]
    rsi = _rsi(values, 14)
    assert rsi is not None
    assert rsi == 100.0  # all gains, no losses


def test_momentum_is_recent_breakout():
    from app.services.momentum import MomentumSnapshot, is_recent_breakout

    fresh = MomentumSnapshot(
        momentum_score=75,
        breakout_at=datetime.now(UTC) - timedelta(days=3),
        label="breakout",
    )
    stale = MomentumSnapshot(
        momentum_score=75,
        breakout_at=datetime.now(UTC) - timedelta(days=30),
        label="breakout",
    )
    assert is_recent_breakout(fresh)
    assert not is_recent_breakout(stale)


# ─────── Lifecycle ───────


def test_lifecycle_cuts_old_no_orders():
    from app.services.lifecycle import evaluate_product

    decision = evaluate_product(
        published_at=datetime.now(UTC) - timedelta(days=45),
        views=500,
        clicks=2,
        orders=0,
    )
    assert decision.kind == "cut"


def test_lifecycle_winners_get_duplication_count():
    from app.services.lifecycle import evaluate_product

    decision = evaluate_product(
        published_at=datetime.now(UTC) - timedelta(days=20),
        views=1000,
        clicks=50,
        orders=5,
        revenue_usd=120,
    )
    assert decision.kind == "winner"
    assert 5 <= decision.suggested_variants <= 10


def test_lifecycle_neutral_keeps_holding():
    from app.services.lifecycle import evaluate_product

    decision = evaluate_product(
        published_at=datetime.now(UTC) - timedelta(days=10),
        views=20,
        clicks=1,
        orders=0,
    )
    assert decision.kind == "neutral"


def test_lifecycle_winner_low_revenue_5_variants():
    from app.services.lifecycle import evaluate_product

    decision = evaluate_product(
        published_at=datetime.now(UTC) - timedelta(days=20),
        views=200,
        clicks=10,
        orders=1,
        revenue_usd=20,
    )
    assert decision.kind == "winner"
    assert decision.suggested_variants == 5


def test_shop_health_score():
    from app.services.lifecycle import shop_health_score

    # 5 listings: total 1000 views, 50 clicks → 5% CTR, healthy
    healthy = shop_health_score([(200, 10) for _ in range(5)])
    assert healthy[0] == 0.05
    assert "scale" in healthy[1].lower()

    # Same total views, only 2 clicks total → 0.2% CTR, dangerous
    poor = shop_health_score([(500, 1), (500, 1)])
    assert poor[0] == 0.002
    assert "pause" in poor[1].lower()


# ─────── Pricing ───────


def test_pricing_high_momentum_bumps():
    from app.services.pricing import PricingRuleConfig, evaluate_rule

    rule = PricingRuleConfig(
        id=1, name="momentum +1", trigger="high_momentum",
        delta_usd=1.00, min_price_usd=10, max_price_usd=50,
    )
    decision = evaluate_rule(
        rule, current_price=22.99,
        momentum_score=80, ctr=0.05, orders=3,
    )
    assert decision is not None
    assert decision.new_price_usd == 23.99


def test_pricing_high_momentum_silent_when_no_orders():
    from app.services.pricing import PricingRuleConfig, evaluate_rule

    rule = PricingRuleConfig(
        id=1, name="momentum", trigger="high_momentum",
        delta_usd=1.00, min_price_usd=10,
    )
    # high momentum but no orders yet → don't price up
    decision = evaluate_rule(
        rule, current_price=22.99,
        momentum_score=80, ctr=0.05, orders=0,
    )
    assert decision is None


def test_pricing_weekend_flash():
    from app.services.pricing import PricingRuleConfig, evaluate_rule

    rule = PricingRuleConfig(
        id=2, name="flash", trigger="weekend_flash",
        delta_percent=20, min_price_usd=10,
    )
    saturday = datetime(2026, 4, 25, 14, 0, tzinfo=UTC)  # known Saturday
    decision = evaluate_rule(rule, current_price=20.00, now=saturday)
    assert decision is not None
    assert decision.new_price_usd == 16.00
    assert decision.revert_at is not None
    assert decision.revert_at.weekday() == 0  # Monday


def test_pricing_weekend_flash_silent_on_tuesday():
    from app.services.pricing import PricingRuleConfig, evaluate_rule

    rule = PricingRuleConfig(
        id=2, name="flash", trigger="weekend_flash",
        delta_percent=20, min_price_usd=10,
    )
    tuesday = datetime(2026, 4, 28, 14, 0, tzinfo=UTC)
    decision = evaluate_rule(rule, current_price=20.00, now=tuesday)
    assert decision is None


def test_pricing_low_ctr_discount():
    from app.services.pricing import PricingRuleConfig, evaluate_rule

    rule = PricingRuleConfig(
        id=3, name="rescue", trigger="low_ctr_discount",
        delta_percent=15, min_price_usd=10,
    )
    decision = evaluate_rule(
        rule, current_price=25.00,
        ctr=0.005, views=500, orders=0,
    )
    assert decision is not None
    assert decision.new_price_usd == 21.25


def test_pricing_respects_min_price_floor():
    from app.services.pricing import PricingRuleConfig, evaluate_rule

    rule = PricingRuleConfig(
        id=2, name="flash", trigger="weekend_flash",
        delta_percent=80,  # extreme
        min_price_usd=15.00,
    )
    saturday = datetime(2026, 4, 25, 14, 0, tzinfo=UTC)
    decision = evaluate_rule(rule, current_price=20.00, now=saturday)
    assert decision is not None
    # 20 * (1 - 0.80) = 4.00, but floor 15.00
    assert decision.new_price_usd == 15.00


def test_pricing_evaluate_all_first_match_wins():
    from app.services.pricing import PricingRuleConfig, evaluate_all

    rules = [
        PricingRuleConfig(
            id=1, name="winner", trigger="high_momentum",
            delta_usd=2.00, min_price_usd=10,
        ),
        PricingRuleConfig(
            id=2, name="flash", trigger="weekend_flash",
            delta_percent=20, min_price_usd=10,
        ),
    ]
    saturday_winner = datetime(2026, 4, 25, 14, 0, tzinfo=UTC)
    decision = evaluate_all(
        rules, current_price=20.00,
        momentum_score=80, ctr=0.05, orders=3,
        now=saturday_winner,
    )
    # high_momentum wins
    assert decision is not None
    assert decision.rule_id == 1


# ─────── Long-tail ───────


def test_long_tail_template_fallback():
    from app.services.long_tail import expand_long_tail

    result = expand_long_tail("cat lovers", count=15)
    assert result.source == "template"
    assert len(result.keywords) >= 10  # template has plenty
    assert len(set(result.keywords)) == len(result.keywords)  # all unique
    # Contains intent-modified phrases
    assert any("gift" in k for k in result.keywords)
    assert any("vintage" in k or "minimalist" in k for k in result.keywords)


def test_long_tail_word_count_bounds():
    from app.services.long_tail import expand_long_tail

    result = expand_long_tail("crazy cat lady", count=20)
    for k in result.keywords:
        wc = len(k.split())
        assert 2 <= wc <= 8


def test_long_tail_ai_caller_path():
    from app.services.long_tail import expand_long_tail

    def fake_ai(_prompt: str) -> str:
        return (
            '{"keywords": ["vintage cat mom shirt", "funny cat lover gift",'
            ' "crazy cat lady tee", "minimalist cat aesthetic", "kawaii cat lover",'
            ' "boho cat mom mug", "retro cat dad shirt", "cottagecore cat fan",'
            ' "spiritual cat lover gift", "sarcastic cat mom tee"]}'
        )

    result = expand_long_tail("cat lovers", count=10, ai_caller=fake_ai)
    assert result.source == "ai"
    assert len(result.keywords) == 10


def test_long_tail_ai_failure_falls_back():
    from app.services.long_tail import expand_long_tail

    def broken_ai(_prompt: str) -> str:
        return "not json at all!"

    result = expand_long_tail("cat lovers", count=10, ai_caller=broken_ai)
    assert result.source == "template"
    assert len(result.keywords) > 0


# ─────── Seasonal ───────


def test_seasonal_upcoming_includes_far_horizon():
    from app.services.long_tail import upcoming_seasonal_events

    # On April 1 2026, halloween (8 weeks lead) is far away.
    # On Sept 1, halloween should be in the upcoming list.
    events = upcoming_seasonal_events(today=date(2026, 9, 1))
    names = {e.name for e in events}
    assert "Halloween" in names


def test_seasonal_keyword_seeds_returns_pairs():
    from app.services.long_tail import seasonal_keyword_seeds

    seeds = seasonal_keyword_seeds(today=date(2026, 11, 1))
    assert isinstance(seeds, list)
    if seeds:
        assert all(isinstance(s, tuple) and len(s) == 2 for s in seeds)
        # Christmas/Thanksgiving should be in the upcoming horizon
        names = {n for n, _ in seeds}
        assert "Christmas" in names or "Thanksgiving" in names


# ─────── Pinterest ───────


def test_pinterest_skipped_when_no_config():
    from app.services.pinterest import create_pin

    result = create_pin(
        None, image_url="x", title="t", description="d", link="l",
    )
    assert result.skipped
    assert not result.success


def test_pinterest_description_caps_500_chars():
    from app.services.pinterest import _build_description

    long_desc = "x" * 600
    out = _build_description(long_desc, ["tag1", "tag2"])
    assert len(out) <= 500
