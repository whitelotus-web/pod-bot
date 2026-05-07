"""Lightweight trend predictor for keyword scout.

Why this exists:
- The keyword scout pulls long-tail phrases from external feeds. Some
  phrases have momentum building (early-trend), some are at peak (high
  competition), some are declining. Acting on declining phrases burns
  AI quota for nothing.
- A full ML pipeline (Prophet, ARIMA, learnable embedding) is overkill
  here — Etsy seasonality is highly periodic and 90% of useful signal
  is captured by linear regression over the last N daily samples.

Algorithm:
- Fit a least-squares line over the last ``window`` daily volume
  samples.
- Slope > +threshold = ``rising``
- Slope < -threshold = ``declining``
- Otherwise = ``stable``
- Confidence = R^2 of the fit (0..1).

This module has zero NumPy / pandas dependency by design — we keep the
backend image small. When a user wants smarter forecasting later they
can drop in a Prophet-based ``predict_v2`` and the pipeline will pick
it up via the same dataclass interface.
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import mean


@dataclass(frozen=True)
class TrendForecast:
    direction: str           # rising | stable | declining | unknown
    slope_per_day: float
    r_squared: float
    next_7d_estimate: float | None
    samples: int


_RISING_SLOPE = 0.05  # +5%/day average growth
_DECLINING_SLOPE = -0.05


def predict(samples: list[float], *, window: int = 28) -> TrendForecast:
    """Forecast direction + magnitude from a daily volume series.

    ``samples`` should be in chronological order, oldest first. ``window``
    caps how much history we consider (Etsy's seasonal patterns rarely
    benefit from > 4 weeks for short-horizon forecasting).
    """
    series = [float(x) for x in samples[-window:]]
    n = len(series)
    if n < 4:
        return TrendForecast(
            direction="unknown",
            slope_per_day=0.0,
            r_squared=0.0,
            next_7d_estimate=None,
            samples=n,
        )

    avg = mean(series) or 1e-9  # avoid divide-by-zero in normalisation

    # Least-squares linear regression on (i, value) pairs.
    sx = sum(range(n))
    sy = sum(series)
    sxx = sum(i * i for i in range(n))
    sxy = sum(i * v for i, v in enumerate(series))
    denom = n * sxx - sx * sx
    if denom == 0:
        return TrendForecast(
            direction="unknown",
            slope_per_day=0.0,
            r_squared=0.0,
            next_7d_estimate=None,
            samples=n,
        )
    slope = (n * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / n

    # Coefficient of determination (R²) gives confidence in the fit.
    ss_tot = sum((v - avg) ** 2 for v in series)
    ss_res = sum((v - (intercept + slope * i)) ** 2 for i, v in enumerate(series))
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
    r2 = max(0.0, min(1.0, r2))

    # Normalise slope to a percentage of the mean so thresholds are
    # comparable across keywords with very different absolute volumes.
    slope_pct = slope / avg

    if slope_pct >= _RISING_SLOPE:
        direction = "rising"
    elif slope_pct <= _DECLINING_SLOPE:
        direction = "declining"
    else:
        direction = "stable"

    next_7d = max(0.0, intercept + slope * (n - 1 + 7))

    return TrendForecast(
        direction=direction,
        slope_per_day=slope_pct,
        r_squared=r2,
        next_7d_estimate=next_7d,
        samples=n,
    )


def score_for_scout(samples: list[float]) -> float:
    """Return a multiplier for the keyword scout to use against a base score.

    rising × confident → boost
    declining × confident → penalty
    stable / low-confidence → ~1.0 (no opinion)
    """
    f = predict(samples)
    if f.direction == "rising":
        return 1.0 + 0.5 * f.r_squared
    if f.direction == "declining":
        return max(0.4, 1.0 - 0.6 * f.r_squared)
    return 1.0
