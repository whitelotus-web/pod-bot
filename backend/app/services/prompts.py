"""Built-in prompt template library + composer.

Templates are referenced by ID and combined with the user's keyword & niche
to form a final prompt that is sent to the chosen AI engine. Adding a new
template is one entry in `TEMPLATES`; no schema change.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptTemplate:
    id: str
    label: str
    description: str
    style: str  # injected into design_prompt(...)
    sample_prompt: str  # what user sees in preview before keyword substitution


TEMPLATES: list[PromptTemplate] = [
    PromptTemplate(
        id="vintage_retro",
        label="Vintage Retro",
        description="Phong cách 70-80s, palette ấm, distressed texture.",
        style=(
            "vintage retro 1970s illustration, warm earth tones, distressed texture, "
            "bold typography, 4-color palette, sun rays in background"
        ),
        sample_prompt="T-shirt vintage retro về 'cat lovers' — tone ấm, kết cấu sờn cũ, 4 màu",
    ),
    PromptTemplate(
        id="minimal_line",
        label="Minimal Line Art",
        description="Đường nét tối giản, đen trắng, không chữ.",
        style="minimalist single-line art, monochrome black on white, clean lines, no text",
        sample_prompt="T-shirt line-art tối giản về 'mountain hiking' — đen trắng, một nét",
    ),
    PromptTemplate(
        id="kawaii_cute",
        label="Kawaii / Cute",
        description="Phong cách Nhật, dễ thương, pastel.",
        style="kawaii Japanese chibi illustration, pastel colors, big eyes, smiling, sticker style",
        sample_prompt="T-shirt kawaii Nhật về 'coffee lovers' — pastel, mắt to, cute",
    ),
    PromptTemplate(
        id="bold_typography",
        label="Bold Typography",
        description="Câu quote in chữ to, design tập trung vào font.",
        style=(
            "bold sans-serif typography poster, high contrast text on solid background, "
            "centered composition, no illustration"
        ),
        sample_prompt="T-shirt bold typography quote 'Be Brave' — chữ to giữa áo",
    ),
    PromptTemplate(
        id="watercolor",
        label="Watercolor",
        description="Phong cách màu nước, mềm mại, lan toả.",
        style="watercolor painting, soft blended colors, ink splash background, hand-drawn feel",
        sample_prompt="T-shirt watercolor về 'sunset beach' — màu nước lan toả",
    ),
    PromptTemplate(
        id="anime_manga",
        label="Anime / Manga",
        description="Phong cách anime, line đậm, cel-shaded.",
        style="anime manga style, bold ink lines, cel-shaded coloring, dramatic pose, action lines",
        sample_prompt="T-shirt anime về 'dragon warrior' — line đậm, cel-shaded",
    ),
    PromptTemplate(
        id="cyberpunk_neon",
        label="Cyberpunk Neon",
        description="Neon, glitch, futuristic.",
        style=(
            "cyberpunk aesthetic, neon pink and cyan, glitch effect, futuristic typography, "
            "dark background with glowing accents"
        ),
        sample_prompt="T-shirt cyberpunk về 'midnight city' — neon hồng/xanh, glitch",
    ),
    PromptTemplate(
        id="boho_floral",
        label="Boho Floral",
        description="Hoa lá bohemian, mandala, đường viền tỉa.",
        style=(
            "bohemian floral mandala illustration, intricate line work, earthy gold and terracotta, "
            "symmetric layout"
        ),
        sample_prompt="T-shirt boho hoa lá về 'wildflower spirit' — mandala, gold/terracotta",
    ),
    PromptTemplate(
        id="streetwear_graffiti",
        label="Streetwear Graffiti",
        description="Graffiti urban, drip, spray paint.",
        style=(
            "streetwear graffiti illustration, spray paint texture, drip effect, "
            "urban skateboard aesthetic"
        ),
        sample_prompt="T-shirt streetwear graffiti về 'skate or die' — drip, spray paint",
    ),
    PromptTemplate(
        id="cottagecore",
        label="Cottagecore",
        description="Hoa cỏ thôn quê, palette pastel, romantic.",
        style=(
            "cottagecore illustration, pastel pinks and sage greens, vintage botanical drawings, "
            "soft hand-drawn feel"
        ),
        sample_prompt="T-shirt cottagecore về 'mushroom forest' — pastel, hoa cỏ vintage",
    ),
]

TEMPLATES_BY_ID = {t.id: t for t in TEMPLATES}


def compose_preview(keyword: str, niche: str, style: str) -> str:
    """Return the exact prompt that will be sent to the AI for a given input."""
    from app.services.ai.base import AIDesignEngine

    class _P(AIDesignEngine):  # pragma: no cover
        name = "preview"

        def generate(self, *_a, **_kw):  # type: ignore[override]
            raise NotImplementedError

    return _P().design_prompt(keyword.strip() or "your keyword", niche=niche, style=style)
