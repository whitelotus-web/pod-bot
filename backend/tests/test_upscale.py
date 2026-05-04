from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from app.services.upscale import _scale_factor, upscale


def _make_png(path: Path, w: int, h: int) -> None:
    img = Image.new("RGBA", (w, h), (200, 100, 200, 255))
    img.save(path, format="PNG")


def test_scale_factor_progresses():
    assert _scale_factor(1024, 1024, 4500) == 5
    assert _scale_factor(2048, 2048, 4500) == 3
    assert _scale_factor(4500, 4500, 4500) == 1


def test_upscale_lanczos_meets_min_long_edge(tmp_path):
    src = tmp_path / "in.png"
    _make_png(src, 1024, 1024)
    res = upscale(src, min_long_edge=4500, backend="pil_lanczos")
    assert res.backend == "pil_lanczos"
    assert max(res.width, res.height) >= 4500
    assert Path(res.output_path).exists()


def test_upscale_skips_when_already_large(tmp_path):
    src = tmp_path / "big.png"
    _make_png(src, 6000, 6000)
    res = upscale(src, min_long_edge=4500, backend="pil_lanczos")
    assert res.backend == "skipped"
    assert res.width == 6000
    assert res.height == 6000


def test_upscale_off_backend_short_circuits(tmp_path):
    src = tmp_path / "in.png"
    _make_png(src, 100, 100)
    res = upscale(src, min_long_edge=4500, backend="off")
    assert res.backend == "skipped"


def test_upscale_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        upscale(tmp_path / "nope.png")


def test_upscale_preserves_aspect_ratio(tmp_path):
    src = tmp_path / "rect.png"
    _make_png(src, 1024, 768)
    res = upscale(src, min_long_edge=4500, backend="pil_lanczos")
    # 1024:768 = 4:3 ratio, scaled
    assert res.width / res.height == pytest.approx(1024 / 768, rel=0.01)
