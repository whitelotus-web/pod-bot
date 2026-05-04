"""Background removal helper.

Strategy:
1. If `rembg` is installed, use the lightweight U2net model.
2. Else fall back to a simple alpha-threshold composite (works for AI-generated
   designs that already have near-white backgrounds).

The pipeline calls this AFTER design generation when the AI engine cannot
guarantee a transparent background (OpenAI / Replicate). Gemini already produces
transparent PNGs when prompted correctly.
"""
from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)


def remove_background(input_path: str | Path, output_path: str | Path | None = None) -> Path:
    """Remove background, write PNG with alpha channel, return output path."""
    input_path = Path(input_path)
    output_path = Path(output_path) if output_path else input_path.with_name(
        input_path.stem + "_nobg.png"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        from rembg import remove  # type: ignore

        with input_path.open("rb") as f:
            data = f.read()
        out = remove(data)
        output_path.write_bytes(out if isinstance(out, (bytes, bytearray)) else bytes(out))
        return output_path
    except ImportError:
        logger.info("rembg not installed — falling back to alpha threshold.")
        return _threshold_fallback(input_path, output_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("rembg failed (%s) — falling back to alpha threshold.", exc)
        return _threshold_fallback(input_path, output_path)


def _threshold_fallback(input_path: Path, output_path: Path, threshold: int = 245) -> Path:
    """Make near-white pixels transparent. Quick & simple, works for clean AI art."""
    img = Image.open(input_path).convert("RGBA")
    pixels = img.load()
    if pixels is None:
        img.save(output_path, "PNG")
        return output_path
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if r >= threshold and g >= threshold and b >= threshold:
                pixels[x, y] = (r, g, b, 0)
    img.save(output_path, "PNG")
    return output_path
