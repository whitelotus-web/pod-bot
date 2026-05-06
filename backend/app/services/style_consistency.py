"""Style consistency tracker.

Goal: detect when an AI-generated design *looks too different* from the
campaign's existing winners. A consistent shop voice is one of the
biggest organic-discovery levers on Etsy + Pinterest, so we want to
flag when a campaign's latest design strays.

Approach (kept dependency-light on purpose):

1. Fingerprint each design with a small **average-hash** (aHash) over a
   downsampled greyscale grid + a coarse colour histogram.
2. Distance between fingerprints = Hamming distance on the aHash plus
   chi-squared on the histogram bins.
3. Track a rolling baseline per campaign (last N approved designs);
   raise a soft warning when a new design's distance to the baseline
   exceeds the configured threshold.

This is intentionally not a CLIP embedding pipeline — we want it to run
in <50ms per design without GPU. CLIP can be plugged in later via the
same ``compute_signature`` interface.
"""
from __future__ import annotations

import io
import logging
import math
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Tunables
HASH_SIZE = 16        # 16x16 = 256-bit aHash
HIST_BINS = 8         # per RGB channel → 24-d histogram
ROLLING_N = 10        # last N approved designs define the baseline
DEFAULT_THRESHOLD = 0.42  # 0..1 normalised distance


@dataclass(frozen=True)
class StyleSignature:
    ahash: str
    histogram: tuple[int, ...]

    def to_payload(self) -> dict:
        return {"ahash": self.ahash, "histogram": list(self.histogram)}

    @classmethod
    def from_payload(cls, payload: dict | None) -> StyleSignature | None:
        if not payload:
            return None
        h = payload.get("ahash")
        hist = payload.get("histogram")
        if not isinstance(h, str) or not isinstance(hist, list):
            return None
        return cls(ahash=h, histogram=tuple(int(x) for x in hist))


def compute_signature(image_bytes: bytes) -> StyleSignature | None:
    """Compute a style fingerprint. Returns None on decode failure."""
    try:
        from PIL import Image
    except ImportError:
        logger.warning("Pillow not available; style consistency disabled")
        return None

    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as exc:  # noqa: BLE001
        logger.warning("style sig: failed to decode image: %s", exc)
        return None

    # 1) aHash on downsampled greyscale.
    grey = img.convert("L").resize((HASH_SIZE, HASH_SIZE), Image.Resampling.LANCZOS)
    pixels = list(grey.getdata())
    avg = sum(pixels) / len(pixels) if pixels else 0
    bits = "".join("1" if p >= avg else "0" for p in pixels)
    ahash_hex = f"{int(bits, 2):0{HASH_SIZE * HASH_SIZE // 4}x}"

    # 2) Coarse RGB histogram.
    small = img.resize((64, 64), Image.Resampling.LANCZOS)
    hist: list[int] = []
    for ch in range(3):
        channel = small.getchannel(("R", "G", "B")[ch])
        # PIL histogram returns 256 bins; collapse to HIST_BINS.
        raw = channel.histogram()
        step = 256 // HIST_BINS
        for i in range(HIST_BINS):
            hist.append(sum(raw[i * step : (i + 1) * step]))

    return StyleSignature(ahash=ahash_hex, histogram=tuple(hist))


def _hamming(a: str, b: str) -> int:
    if len(a) != len(b):
        return max(len(a), len(b)) * 4  # very different
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def _chi_square(a: tuple[int, ...], b: tuple[int, ...]) -> float:
    if len(a) != len(b):
        return 1.0
    sa = sum(a) or 1
    sb = sum(b) or 1
    score = 0.0
    for x, y in zip(a, b, strict=True):
        nx = x / sa
        ny = y / sb
        denom = nx + ny
        if denom > 0:
            score += ((nx - ny) ** 2) / denom
    return score / 2.0  # normalised 0..1


def distance(a: StyleSignature, b: StyleSignature) -> float:
    """Return a 0..1 distance score (0 = identical, 1 = wildly different)."""
    bits = HASH_SIZE * HASH_SIZE
    h_norm = _hamming(a.ahash, b.ahash) / bits
    c_norm = _chi_square(a.histogram, b.histogram)
    # Weighted blend — aHash is structurally significant, histogram is
    # palette significant. Both matter for "does this fit my shop".
    return min(1.0, 0.6 * h_norm + 0.4 * c_norm)


def average_distance(
    candidate: StyleSignature, baseline: list[StyleSignature]
) -> float:
    """Distance from candidate to a baseline set. NaN if baseline empty."""
    if not baseline:
        return math.nan
    return sum(distance(candidate, b) for b in baseline) / len(baseline)


def is_consistent(
    candidate: StyleSignature,
    baseline: list[StyleSignature],
    *,
    threshold: float = DEFAULT_THRESHOLD,
) -> tuple[bool, float]:
    """Return (is_consistent, distance). Empty baseline = always consistent."""
    if not baseline:
        return True, 0.0
    d = average_distance(candidate, baseline)
    return (d <= threshold), d
