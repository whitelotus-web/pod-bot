"""Momentum trend prediction for keyword volume.

Goal: detect keywords that are *about* to break out (rising volume) so the
pipeline can design and publish products 1-2 weeks before competitors.

Inputs: a sorted time-series of (date, volume) samples for one keyword,
typically from the last 60-90 days. Output:

- `sma_7`, `sma_30`: simple moving averages
- `rsi_14`: 14-period relative strength index (Wilder's formula)
- `momentum_score`: composite 0-100 score combining:
    * SMA crossover (sma_7 > sma_30 → bullish)
    * RSI in the "breakout" band (50-70 = building strength, >70 = overbought)
    * Recent rate of change vs 30-day average
- `breakout_at`: timestamp of the most recent SMA-7/SMA-30 bullish cross

We deliberately avoid heavyweight stats packages — pure NumPy/list math is
enough for the timescales involved, and keeps the worker image small.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, date, datetime


@dataclass
class MomentumSnapshot:
    sma_7: float | None = None
    sma_30: float | None = None
    rsi_14: float | None = None
    momentum_score: float = 0.0  # 0..100
    breakout_at: datetime | None = None
    label: str = "flat"  # flat | rising | breakout | falling | overbought


def _sma(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return sum(values[-window:]) / window


def _rsi(values: list[float], period: int = 14) -> float | None:
    """Wilder's RSI. Returns 0..100 or None if not enough data."""
    if len(values) < period + 1:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, len(values)):
        diff = values[i] - values[i - 1]
        gains.append(max(0.0, diff))
        losses.append(max(0.0, -diff))

    # Initial averages over first `period` deltas.
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    # Smooth Wilder-style for remaining deltas.
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _detect_breakout(values: list[float], dates: list[date]) -> datetime | None:
    """Find the most recent date where SMA(7) crossed above SMA(30)."""
    if len(values) < 30:
        return None
    last_breakout: datetime | None = None
    prev_above = False
    for i in range(30, len(values) + 1):
        window = values[:i]
        s7 = _sma(window, 7)
        s30 = _sma(window, 30)
        if s7 is None or s30 is None:
            continue
        above = s7 > s30
        if above and not prev_above:
            d = dates[i - 1]
            last_breakout = datetime(d.year, d.month, d.day, tzinfo=UTC)
        prev_above = above
    return last_breakout


def compute(samples: list[tuple[date, float]]) -> MomentumSnapshot:  # noqa: C901
    """Compute momentum from a sorted list of (date, volume) samples.

    samples must be sorted ascending by date. Missing days are tolerated;
    we don't infer values, we just operate on what we have.
    """
    if not samples:
        return MomentumSnapshot()

    samples_sorted = sorted(samples, key=lambda s: s[0])
    dates = [s[0] for s in samples_sorted]
    values = [float(s[1]) for s in samples_sorted]

    snap = MomentumSnapshot()
    snap.sma_7 = _sma(values, 7)
    snap.sma_30 = _sma(values, 30)
    snap.rsi_14 = _rsi(values, 14)
    snap.breakout_at = _detect_breakout(values, dates)

    # Composite score in [0,100].
    score = 50.0
    if snap.sma_7 is not None and snap.sma_30 is not None and snap.sma_30 > 0:
        delta = (snap.sma_7 - snap.sma_30) / snap.sma_30
        # +10% delta → +20 points; cap influence at ±30 points.
        score += max(-30.0, min(30.0, delta * 200))
    if snap.rsi_14 is not None:
        # RSI sweet spot 50-70 — bullish without overbought.
        if 50 <= snap.rsi_14 <= 70:
            score += 15
        elif 70 < snap.rsi_14 <= 85:
            score += 5  # overbought, reward less
        elif 30 <= snap.rsi_14 < 50:
            score -= 5  # weak
        elif snap.rsi_14 < 30:
            score -= 15  # falling
        elif snap.rsi_14 > 85:
            score -= 5  # crashing-soon territory

    # Recent rate of change (last 7 vs prev 7).
    if len(values) >= 14:
        recent = sum(values[-7:]) / 7
        prior = sum(values[-14:-7]) / 7
        if prior > 0:
            roc = (recent - prior) / prior
            score += max(-10.0, min(10.0, roc * 50))

    snap.momentum_score = max(0.0, min(100.0, score))

    # Label: a quick human-readable bucket.
    if snap.momentum_score >= 75 and snap.breakout_at is not None:
        snap.label = "breakout"
    elif snap.momentum_score >= 60:
        snap.label = "rising"
    elif snap.rsi_14 is not None and snap.rsi_14 > 80:
        snap.label = "overbought"
    elif snap.momentum_score <= 35:
        snap.label = "falling"
    else:
        snap.label = "flat"

    return snap


def classify_label(score: float) -> str:
    if score >= 75:
        return "breakout"
    if score >= 60:
        return "rising"
    if score <= 35:
        return "falling"
    return "flat"


def is_recent_breakout(
    snap: MomentumSnapshot, *, max_age_days: int = 14
) -> bool:
    """True if the breakout is recent enough to act on."""
    if snap.breakout_at is None or snap.label not in ("rising", "breakout"):
        return False
    age = datetime.now(UTC) - snap.breakout_at
    return age.days <= max_age_days


# Helper used by tests: synthetic series.
def _synthesize_series(start_volume: float, days: int, daily_growth_pct: float) -> list[tuple[date, float]]:
    """Generate a sample series: useful for tests."""
    from datetime import timedelta as _td

    today = date.today()
    out: list[tuple[date, float]] = []
    v = start_volume
    for i in range(days):
        d = today - _td(days=days - i - 1)
        # tiny noise for realism: alternate +/- 2%
        noise = 1.0 + (0.02 if i % 2 == 0 else -0.02)
        out.append((d, max(0.0, v * noise)))
        v *= 1.0 + daily_growth_pct
    return out


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))
