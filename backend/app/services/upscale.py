"""AI upscaler — bring AI-generated 1024px designs to 4500x5400 print-ready DPI.

Three strategies, picked in this order:

1. **Replicate API** (`real-esrgan` model) — paid, ~$0.002/image, best quality, no GPU needed.
   Enabled when ``REPLICATE_API_TOKEN`` env var is set and ``UPSCALE_BACKEND=replicate``.
2. **Local Real-ESRGAN** — runs the bundled torch model from ``./models/realesr/``.
   Enabled when ``UPSCALE_BACKEND=realesrgan_local`` and the package + weights are
   available on disk. Heavy: needs torch + CUDA for reasonable speed.
3. **PIL LANCZOS fallback** — pure Python upscaling. Always works. Loses some
   detail vs ESRGAN but is 100% free + instant + zero deps.

Printify spec for tshirt DTG: 4500×5400 px @ 300 DPI (15"×18" print area).
This service guarantees the output meets ``min_long_edge`` (default 4500 px)
while preserving aspect ratio. No padding is added — caller can pad if needed.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class UpscaleResult:
    output_path: str
    backend: str  # "replicate" | "realesrgan_local" | "pil_lanczos" | "skipped"
    width: int
    height: int
    elapsed_ms: int
    note: str = ""


def _backend_choice() -> str:
    explicit = (os.getenv("UPSCALE_BACKEND") or "").strip().lower()
    if explicit in {"replicate", "realesrgan_local", "pil_lanczos", "off"}:
        return explicit
    if os.getenv("REPLICATE_API_TOKEN"):
        return "replicate"
    return "pil_lanczos"


def upscale(
    src_path: str | os.PathLike,
    *,
    out_path: str | os.PathLike | None = None,
    min_long_edge: int = 4500,
    backend: str | None = None,
) -> UpscaleResult:
    """Upscale a design until its long edge ≥ ``min_long_edge`` pixels.

    The output is written to ``out_path`` if provided, else to a sibling file
    next to ``src_path`` with ``_x4`` suffix. PNG transparency is preserved.
    """
    src = Path(src_path)
    if not src.exists():
        raise FileNotFoundError(src)
    if out_path is None:
        out = src.with_name(src.stem + "_x4.png")
    else:
        out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    chosen = (backend or _backend_choice()).lower()
    if chosen == "off":
        return UpscaleResult(str(src), "skipped", 0, 0, 0, note="backend=off")

    started = time.time()

    # Read original dimensions cheaply with Pillow.
    from PIL import Image

    with Image.open(src) as im:
        w0, h0 = im.size

    long_edge = max(w0, h0)
    if long_edge >= min_long_edge:
        # Already large enough — copy through to keep call sites uniform.
        with Image.open(src) as im:
            im.save(out)
        elapsed = int((time.time() - started) * 1000)
        return UpscaleResult(
            str(out), "skipped", w0, h0, elapsed,
            note=f"already {w0}x{h0} ≥ {min_long_edge}px",
        )

    if chosen == "replicate":
        try:
            return _upscale_replicate(src, out, min_long_edge=min_long_edge, t0=started)
        except Exception as exc:  # noqa: BLE001
            logger.warning("replicate upscale failed: %s — falling back to LANCZOS", exc)
            chosen = "pil_lanczos"

    if chosen == "realesrgan_local":
        try:
            return _upscale_realesrgan_local(src, out, min_long_edge=min_long_edge, t0=started)
        except Exception as exc:  # noqa: BLE001
            logger.warning("local Real-ESRGAN failed: %s — falling back to LANCZOS", exc)
            chosen = "pil_lanczos"

    return _upscale_lanczos(src, out, min_long_edge=min_long_edge, t0=started)


def _scale_factor(w0: int, h0: int, min_long_edge: int) -> int:
    """Smallest integer scale needed to hit min_long_edge."""
    long_edge = max(w0, h0)
    if long_edge >= min_long_edge:
        return 1
    factor = 2
    while long_edge * factor < min_long_edge:
        factor += 1
    return factor


def _upscale_lanczos(src: Path, out: Path, *, min_long_edge: int, t0: float) -> UpscaleResult:
    from PIL import Image

    with Image.open(src) as im:
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGBA")
        w0, h0 = im.size
        factor = _scale_factor(w0, h0, min_long_edge)
        new_w, new_h = w0 * factor, h0 * factor
        im_up = im.resize((new_w, new_h), resample=Image.Resampling.LANCZOS)
        im_up.save(out, format="PNG", optimize=True)
        w, h = im_up.size
    elapsed = int((time.time() - t0) * 1000)
    return UpscaleResult(
        str(out), "pil_lanczos", w, h, elapsed,
        note=f"x{factor} via LANCZOS",
    )


def _upscale_replicate(src: Path, out: Path, *, min_long_edge: int, t0: float) -> UpscaleResult:
    """Call the Replicate API. Uses ``real-esrgan`` model (4x by default)."""
    import requests

    token = os.environ["REPLICATE_API_TOKEN"]
    model_version = os.getenv(
        "REPLICATE_REALESRGAN_VERSION",
        "350d32041630ffbe63c8352783a26d94126809164e54085352f8326e53999085",
    )
    # Upload the source image to a temporary 0x0.st-style host? Simpler:
    # send as data URI when the file is small enough. Replicate accepts
    # "data:image/png;base64,..." inputs.
    import base64

    raw = src.read_bytes()
    if len(raw) > 5 * 1024 * 1024:
        raise RuntimeError("design too large for inline replicate upload (>5MB)")
    data_uri = "data:image/png;base64," + base64.b64encode(raw).decode("ascii")

    payload = {
        "version": model_version,
        "input": {"image": data_uri, "scale": 4},
    }
    headers = {
        "Authorization": f"Token {token}",
        "Content-Type": "application/json",
    }
    res = requests.post(
        "https://api.replicate.com/v1/predictions", json=payload, headers=headers, timeout=30
    )
    res.raise_for_status()
    pred = res.json()
    poll_url = pred["urls"]["get"]

    # Poll up to 90s — Real-ESRGAN x4 typically finishes in 6-15s.
    output_url = None
    deadline = time.time() + 90
    while time.time() < deadline:
        time.sleep(1.5)
        r = requests.get(poll_url, headers=headers, timeout=15)
        r.raise_for_status()
        body = r.json()
        status = body.get("status")
        if status == "succeeded":
            out_v = body.get("output")
            output_url = out_v[-1] if isinstance(out_v, list) else out_v
            break
        if status in ("failed", "canceled"):
            raise RuntimeError(f"replicate prediction {status}: {body.get('error')}")

    if not output_url:
        raise TimeoutError("replicate prediction timed out after 90s")

    img_resp = requests.get(output_url, timeout=60)
    img_resp.raise_for_status()
    out.write_bytes(img_resp.content)

    from PIL import Image

    with Image.open(out) as im:
        w, h = im.size
    elapsed = int((time.time() - t0) * 1000)

    if max(w, h) < min_long_edge:
        # Replicate returned smaller than expected — pad up via LANCZOS.
        return _upscale_lanczos(out, out, min_long_edge=min_long_edge, t0=t0)

    return UpscaleResult(str(out), "replicate", w, h, elapsed, note="real-esrgan x4")


def _upscale_realesrgan_local(
    src: Path, out: Path, *, min_long_edge: int, t0: float
) -> UpscaleResult:
    """Run a locally-installed realesrgan model. Heavy: needs torch."""
    try:
        from basicsr.archs.rrdbnet_arch import RRDBNet  # type: ignore[import-not-found]
        from realesrgan import RealESRGANer  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("realesrgan not installed in this image") from exc

    weights = Path(os.getenv("REALESRGAN_WEIGHTS", "/opt/realesr/RealESRGAN_x4plus.pth"))
    if not weights.exists():
        raise RuntimeError(f"missing weights at {weights}")

    model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
    upsampler = RealESRGANer(
        scale=4, model_path=str(weights), model=model,
        tile=512, tile_pad=10, pre_pad=0, half=False,
    )

    import cv2

    img = cv2.imread(str(src), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise RuntimeError(f"cv2 could not read {src}")
    output, _ = upsampler.enhance(img, outscale=4)
    cv2.imwrite(str(out), output)

    from PIL import Image

    with Image.open(out) as im:
        w, h = im.size
    elapsed = int((time.time() - t0) * 1000)

    if max(w, h) < min_long_edge:
        return _upscale_lanczos(out, out, min_long_edge=min_long_edge, t0=t0)
    return UpscaleResult(str(out), "realesrgan_local", w, h, elapsed, note="local x4")
