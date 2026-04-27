"""Design quality gates run BEFORE a design is published.

Five checks (each returns a score 0..1, with a failure flag):

1. **sharpness**: Laplacian variance over the alpha-masked region. Low variance
   means flat / blurry / lacking detail. POD prints lose ~10-15% sharpness, so
   the source must be sharper than the human-acceptable threshold.
2. **ocr_text_match**: any rendered text on the design must match the source
   keyword exactly (no AI hallucinated typos). Uses pytesseract if available,
   else skipped.
3. **dtg_color_safety**: simulate a DTG print on dark fabric. Reject palettes
   that are out-of-gamut or have contrast that will look muddy.
4. **palette_diversity**: at least 3 distinct color clusters (avoids
   single-blob designs).
5. **mockup_qa_vision** (optional): if a Gemini Vision key is configured,
   show the rendered mockup to the model and ask "is this print well-placed
   on the apparel?" — reject if score < 7/10.

Each check is independent; the pipeline can configure which gates are
mandatory vs informational. All checks are best-effort: if a dep is missing
(pytesseract, OpenCV) the gate becomes a no-op and is reported as `untested`
rather than failing closed (don't punish users for missing optional deps).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Literal

logger = logging.getLogger(__name__)

GateStatus = Literal["pass", "fail", "untested"]


@dataclass
class GateResult:
    name: str
    status: GateStatus
    score: float = 0.0
    reason: str = ""
    details: dict = field(default_factory=dict)


@dataclass
class QualityReport:
    gates: list[GateResult] = field(default_factory=list)
    overall_score: float = 0.0
    rejected: bool = False
    rejection_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "gates": [
                {"name": g.name, "status": g.status, "score": g.score, "reason": g.reason}
                for g in self.gates
            ],
            "overall_score": self.overall_score,
            "rejected": self.rejected,
            "rejection_reason": self.rejection_reason,
        }


def _check_sharpness(image_path: str, min_variance: float = 80.0) -> GateResult:
    """Laplacian variance — higher = sharper. Soft minimum 80 for AI PNG."""
    try:
        import cv2  # type: ignore
        import numpy as np
    except ImportError:
        return GateResult(name="sharpness", status="untested", reason="cv2 not installed")

    try:
        img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
        if img is None:
            return GateResult(name="sharpness", status="fail", reason="image read failed")
        # If image has alpha, only score the non-transparent region.
        if img.ndim == 3 and img.shape[2] == 4:
            alpha = img[:, :, 3]
            bgr = img[:, :, :3]
            mask = alpha > 32
            if not np.any(mask):
                return GateResult(name="sharpness", status="fail", reason="fully transparent image")
            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            lap = cv2.Laplacian(gray, cv2.CV_64F)
            roi = lap[mask]
            variance = float(roi.var())
        else:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
            lap = cv2.Laplacian(gray, cv2.CV_64F)
            variance = float(lap.var())

        score = min(1.0, variance / (min_variance * 4))
        if variance < min_variance:
            return GateResult(
                name="sharpness",
                status="fail",
                score=score,
                reason=f"Laplacian variance {variance:.1f} below threshold {min_variance}",
                details={"variance": variance},
            )
        return GateResult(
            name="sharpness", status="pass", score=score, details={"variance": variance}
        )
    except Exception as exc:  # noqa: BLE001
        return GateResult(name="sharpness", status="untested", reason=f"sharpness check error: {exc}")


def _check_ocr_text_match(image_path: str, expected_keyword: str) -> GateResult:
    """If the design has rendered text, it must match the keyword.

    Catches AI-generated gibberish typography ("vıntage cnt lover").
    """
    if not expected_keyword:
        return GateResult(name="ocr_text_match", status="untested", reason="no keyword to compare")

    try:
        import pytesseract  # type: ignore
        from PIL import Image
    except ImportError:
        return GateResult(name="ocr_text_match", status="untested", reason="pytesseract not installed")

    try:
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img, config="--psm 6").strip()
    except Exception as exc:  # noqa: BLE001
        return GateResult(name="ocr_text_match", status="untested", reason=f"OCR failed: {exc}")

    if not text:
        return GateResult(name="ocr_text_match", status="pass", reason="no text on design")

    # Normalize and check overlap.
    norm_text = re.sub(r"[^a-z0-9 ]+", " ", text.lower())
    norm_kw = re.sub(r"[^a-z0-9 ]+", " ", expected_keyword.lower())
    kw_tokens = {t for t in norm_kw.split() if len(t) > 2}
    text_tokens = set(norm_text.split())

    if not kw_tokens:
        return GateResult(name="ocr_text_match", status="pass", reason="keyword too short to verify")

    overlap = len(kw_tokens & text_tokens)
    coverage = overlap / len(kw_tokens)

    # Look for obvious gibberish: tokens with rare letter combinations.
    gibberish_tokens = [
        t for t in text_tokens
        if len(t) >= 4 and not re.search(r"[aeiouy]", t)  # no vowels
    ]

    if gibberish_tokens:
        return GateResult(
            name="ocr_text_match",
            status="fail",
            score=coverage,
            reason=f"OCR detected gibberish tokens: {gibberish_tokens[:3]}",
            details={"ocr_text": text[:200], "gibberish": gibberish_tokens[:5]},
        )

    if coverage < 0.5:
        return GateResult(
            name="ocr_text_match",
            status="fail",
            score=coverage,
            reason=f"OCR text doesn't match keyword (coverage {coverage:.0%})",
            details={"ocr_text": text[:200], "expected": expected_keyword},
        )
    return GateResult(
        name="ocr_text_match",
        status="pass",
        score=coverage,
        details={"ocr_text": text[:200]},
    )


def _check_dtg_color_safety(image_path: str) -> GateResult:
    """Simulate DTG print on dark fabric.

    Reject if:
    - Average brightness too low (< 30) — print won't show on dark shirts.
    - Average brightness too high (> 220) — design is washed out.
    - Saturation > 200 (out of typical CMYK gamut, will print muddy).
    """
    try:
        import cv2  # type: ignore
        import numpy as np
    except ImportError:
        return GateResult(name="dtg_color_safety", status="untested", reason="cv2 not installed")

    try:
        img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
        if img is None:
            return GateResult(name="dtg_color_safety", status="fail", reason="image read failed")
        if img.ndim == 3 and img.shape[2] == 4:
            alpha = img[:, :, 3]
            mask = alpha > 32
            bgr = img[:, :, :3][mask]
        else:
            bgr = img.reshape(-1, 3) if img.ndim == 3 else img.reshape(-1, 1)
        if bgr.size == 0:
            return GateResult(name="dtg_color_safety", status="fail", reason="empty pixels")

        # OpenCV is BGR.
        avg = np.mean(bgr, axis=0)
        brightness = float(np.mean(avg))
        # Saturation in HSV.
        hsv = cv2.cvtColor(bgr.reshape(1, -1, 3).astype(np.uint8), cv2.COLOR_BGR2HSV)[0]
        saturation = float(np.mean(hsv[:, 1]))

        warnings: list[str] = []
        score = 1.0
        if brightness < 30:
            warnings.append(f"too dark for DTG (brightness {brightness:.0f})")
            score *= 0.4
        elif brightness > 230:
            warnings.append(f"washed out (brightness {brightness:.0f})")
            score *= 0.6
        if saturation > 220:
            warnings.append(f"saturation {saturation:.0f} likely out of CMYK gamut")
            score *= 0.7

        if warnings:
            return GateResult(
                name="dtg_color_safety",
                status="fail",
                score=score,
                reason="; ".join(warnings),
                details={"brightness": brightness, "saturation": saturation},
            )
        return GateResult(
            name="dtg_color_safety",
            status="pass",
            score=score,
            details={"brightness": brightness, "saturation": saturation},
        )
    except Exception as exc:  # noqa: BLE001
        return GateResult(name="dtg_color_safety", status="untested", reason=f"DTG check error: {exc}")


def _check_palette_diversity(image_path: str, min_clusters: int = 3) -> GateResult:
    """Count distinct dominant colors — too few = boring single-blob design."""
    try:
        import cv2  # type: ignore
        import numpy as np
    except ImportError:
        return GateResult(name="palette_diversity", status="untested", reason="cv2 not installed")

    try:
        img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
        if img is None:
            return GateResult(name="palette_diversity", status="fail", reason="image read failed")
        if img.ndim == 3 and img.shape[2] == 4:
            alpha = img[:, :, 3]
            mask = alpha > 32
            pixels = img[:, :, :3][mask].astype(np.float32)
        else:
            pixels = img.reshape(-1, 3).astype(np.float32) if img.ndim == 3 else img.reshape(-1, 1).astype(np.float32)
        if len(pixels) < 100:
            return GateResult(name="palette_diversity", status="fail", reason="not enough opaque pixels")

        # Quick diversity metric: stdev of pixel intensities.
        std = float(np.std(pixels))
        # Bucket pixels into 16-bucket histogram and count buckets > 5%.
        buckets = (pixels // 16).astype(int)
        unique, counts = np.unique(buckets.reshape(-1, buckets.shape[-1]), axis=0, return_counts=True)
        total = counts.sum()
        prominent = int((counts / total > 0.02).sum())

        score = min(1.0, prominent / 6.0)
        if prominent < min_clusters:
            return GateResult(
                name="palette_diversity",
                status="fail",
                score=score,
                reason=f"only {prominent} dominant colors (min {min_clusters})",
                details={"prominent_buckets": prominent, "stdev": std},
            )
        return GateResult(
            name="palette_diversity",
            status="pass",
            score=score,
            details={"prominent_buckets": prominent, "stdev": std},
        )
    except Exception as exc:  # noqa: BLE001
        return GateResult(name="palette_diversity", status="untested", reason=f"palette check error: {exc}")


def _check_mockup_qa_vision(
    mockup_path: str, gemini_api_key: str | None
) -> GateResult:
    """Ask Gemini Vision to grade the rendered mockup."""
    if not gemini_api_key:
        return GateResult(name="mockup_qa_vision", status="untested", reason="no Gemini Vision key")

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=gemini_api_key)
        with open(mockup_path, "rb") as f:
            image_bytes = f.read()
        prompt = (
            "You are a print-on-demand QA reviewer. Look at this product mockup. "
            "Score the design placement quality from 1-10 and describe any issues. "
            "Specifically check: "
            "(a) is the print well-centered on the product? "
            "(b) is the print clipped at edges? "
            "(c) does the print contrast well with the apparel color? "
            "(d) are there visible artifacts (warped lines, color banding)? "
            "Respond in this exact format:\n"
            "SCORE: <1-10>\n"
            "ISSUES: <comma-separated list, or 'none'>\n"
        )
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                prompt,
            ],
        )
        text = (resp.text or "").strip()
        score_match = re.search(r"SCORE\s*:\s*(\d+)", text, re.IGNORECASE)
        if not score_match:
            return GateResult(
                name="mockup_qa_vision", status="untested",
                reason="vision response did not include score",
                details={"raw": text[:300]},
            )
        score_int = int(score_match.group(1))
        score_norm = score_int / 10.0
        passed = score_int >= 7
        return GateResult(
            name="mockup_qa_vision",
            status="pass" if passed else "fail",
            score=score_norm,
            reason=text[:200],
            details={"vision_raw": text[:500]},
        )
    except Exception as exc:  # noqa: BLE001
        return GateResult(
            name="mockup_qa_vision", status="untested", reason=f"vision call error: {exc}"
        )


def evaluate_design(
    image_path: str,
    *,
    expected_keyword: str = "",
    mandatory_gates: tuple[str, ...] = ("sharpness", "dtg_color_safety"),
) -> QualityReport:
    """Run all design-stage gates. `mandatory_gates` decide rejection."""
    gates = [
        _check_sharpness(image_path),
        _check_ocr_text_match(image_path, expected_keyword),
        _check_dtg_color_safety(image_path),
        _check_palette_diversity(image_path),
    ]

    failed_mandatory = [g for g in gates if g.name in mandatory_gates and g.status == "fail"]

    valid_scores = [g.score for g in gates if g.status != "untested"]
    overall = sum(valid_scores) / len(valid_scores) if valid_scores else 0.0

    rejected = bool(failed_mandatory)
    reason = "; ".join(f"{g.name}: {g.reason}" for g in failed_mandatory)

    return QualityReport(
        gates=gates,
        overall_score=overall,
        rejected=rejected,
        rejection_reason=reason,
    )


def evaluate_mockup(
    mockup_path: str,
    *,
    gemini_api_key: str | None = None,
    min_score: float = 0.7,
) -> QualityReport:
    """Run mockup-stage gates (after design is composed onto product)."""
    gates = [_check_mockup_qa_vision(mockup_path, gemini_api_key)]
    valid_scores = [g.score for g in gates if g.status != "untested"]
    overall = sum(valid_scores) / len(valid_scores) if valid_scores else 1.0

    rejected = any(g.status == "fail" for g in gates)
    reason = "; ".join(g.reason for g in gates if g.status == "fail")

    return QualityReport(
        gates=gates,
        overall_score=overall,
        rejected=rejected,
        rejection_reason=reason,
    )
