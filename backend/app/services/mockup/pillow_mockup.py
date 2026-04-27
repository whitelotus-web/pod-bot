"""Generate mockup images by compositing a design onto a t-shirt template.

We ship a programmatic placeholder t-shirt template (drawn at startup if
missing) so the system works out of the box without bundled photo assets.
Replace `templates/tshirt_white.png` with any real mockup photo and the
pipeline picks it up automatically.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from app.core.config import settings

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(settings.media_root) / "templates"
MOCKUPS_DIR = Path(settings.media_root) / "mockups"

# (template_name, (x, y, w, h) area on a 1200x1200 canvas where design is pasted)
DEFAULT_TEMPLATES: dict[str, dict] = {
    "tshirt_white": {"color": (250, 250, 250), "area": (340, 360, 520, 520)},
    "tshirt_black": {"color": (25, 25, 25), "area": (340, 360, 520, 520)},
    "hoodie_gray": {"color": (130, 130, 130), "area": (360, 400, 480, 480)},
}


def _ensure_templates() -> None:
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    MOCKUPS_DIR.mkdir(parents=True, exist_ok=True)
    for name, cfg in DEFAULT_TEMPLATES.items():
        path = TEMPLATES_DIR / f"{name}.png"
        if path.exists():
            continue
        _draw_placeholder_tshirt(path, cfg["color"])


def _draw_placeholder_tshirt(path: Path, body_color: tuple[int, int, int]) -> None:
    """Draw a simple t-shirt silhouette for out-of-the-box mockup."""
    w, h = 1200, 1200
    img = Image.new("RGBA", (w, h), (245, 245, 245, 255))
    draw = ImageDraw.Draw(img)
    # Body
    body = [
        (260, 320), (420, 240), (520, 280),     # left shoulder
        (600, 260), (680, 280),                  # neck
        (780, 240), (940, 320),                  # right shoulder
        (1020, 420), (940, 500), (880, 460),     # right sleeve
        (880, 1080), (320, 1080), (320, 460),    # bottom
        (260, 500), (180, 420),                  # left sleeve
    ]
    draw.polygon(body, fill=body_color + (255,))
    draw.polygon(body, outline=(50, 50, 50, 200))
    # Neck
    draw.ellipse((540, 240, 680, 320), fill=(245, 245, 245, 255), outline=(50, 50, 50, 200))
    img.save(path, "PNG")


class PillowMockup:
    """Composites a design image onto a t-shirt template using Pillow."""

    def __init__(self):
        _ensure_templates()

    def available_templates(self) -> list[str]:
        _ensure_templates()
        return [p.stem for p in TEMPLATES_DIR.glob("*.png")]

    def render(
        self,
        design_path: str,
        template: str = "tshirt_white",
        output_path: str | None = None,
    ) -> str:
        _ensure_templates()
        tmpl_path = TEMPLATES_DIR / f"{template}.png"
        if not tmpl_path.exists():
            tmpl_path = TEMPLATES_DIR / "tshirt_white.png"
            template = "tshirt_white"

        canvas = Image.open(tmpl_path).convert("RGBA")
        design = Image.open(design_path).convert("RGBA")

        area = DEFAULT_TEMPLATES.get(template, DEFAULT_TEMPLATES["tshirt_white"])["area"]
        x, y, w, h = area

        # Scale design to fit within area, preserve aspect
        ratio = min(w / design.width, h / design.height)
        new_w = int(design.width * ratio * 0.95)
        new_h = int(design.height * ratio * 0.95)
        resized = design.resize((new_w, new_h), Image.LANCZOS)

        # Soft drop shadow
        shadow = Image.new("RGBA", (new_w + 40, new_h + 40), (0, 0, 0, 0))
        shadow.paste(resized, (20, 20), resized)
        shadow = shadow.filter(ImageFilter.GaussianBlur(6))

        offset_x = x + (w - new_w) // 2
        offset_y = y + (h - new_h) // 2
        canvas.alpha_composite(shadow, (offset_x - 20, offset_y - 10))
        canvas.alpha_composite(resized, (offset_x, offset_y))

        if output_path is None:
            base = os.path.basename(design_path).rsplit(".", 1)[0]
            output_path = str(MOCKUPS_DIR / f"{base}__{template}.png")

        canvas.convert("RGB").save(output_path, "JPEG", quality=90)
        return output_path
