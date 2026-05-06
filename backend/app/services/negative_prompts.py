"""Curated negative-prompt library for diffusion image models.

Why this exists:
- Stable Diffusion / SDXL benefit massively from a *negative prompt*
  that tells the model what to avoid. The right negative prompt is the
  difference between a clean DTG-printable design and one with rogue
  text, low resolution, or copyrighted style markers.
- Different print products require different exclusions: a t-shirt
  design must avoid backgrounds (DTG works best on transparent), while
  a wall-art print must avoid the *frame* itself appearing in the image.

The library is composable: ``build_negative()`` joins:
  1. The shared "always-avoid" list (watermarks, text, low quality...)
  2. The product-type-specific list (tshirt vs wall_art vs sticker)
  3. The user-provided extras passed through from the campaign config

Callers (replicate_engine, openai_engine, gemini_engine) consume the
output via a single function so we have one place to tweak quality.
"""
from __future__ import annotations

# Shared across every product type — these are baseline "do not produce"
# rules informed by the most common quality-gate rejections we've seen.
_ALWAYS_AVOID: tuple[str, ...] = (
    "watermark",
    "signature",
    "stock photo logo",
    "text",
    "letters",
    "typography",
    "low quality",
    "blurry",
    "out of focus",
    "noisy",
    "jpeg artifacts",
    "compression",
    "low resolution",
    "pixelated",
    "deformed",
    "extra fingers",
    "extra limbs",
    "mutated",
    "disfigured",
    "ugly",
    "bad anatomy",
    "NSFW",
    "violence",
    "trademark",
    "copyrighted character",
    "branded merchandise",
)

# Product-type-specific exclusions. Keys must match the values used in
# ``Campaign.product_type``.
_PER_PRODUCT: dict[str, tuple[str, ...]] = {
    "tshirt": (
        "background",
        "scenery",
        "photographic background",
        "complex shading",
        "gradient that does not print",
        "more than 6 colors",
    ),
    "hoodie": (
        "background",
        "scenery",
        "complex shading",
        "tiny details",
    ),
    "mug": (
        "out-of-bounds composition",
        "elements crossing the curvature seam",
    ),
    "tote": (
        "background",
        "scenery",
        "complex gradient",
    ),
    "sticker": (
        "background",
        "messy outline",
        "no border",
    ),
    "wall_art": (
        "frame",
        "matting",
        "wall behind",
        "interior decoration around the print",
    ),
    "phone_case": (
        "case body",
        "phone outline",
        "lens cutout",
    ),
}


def build_negative(
    *,
    product_type: str = "tshirt",
    extra: list[str] | None = None,
) -> str:
    """Compose the final negative-prompt string for a given product.

    Returns a comma-separated string suitable for SDXL / SD-1.5 /
    DALL-E 3 (DALL-E ignores negative_prompt, but it's safe to pass).
    """
    parts: list[str] = list(_ALWAYS_AVOID)
    parts.extend(_PER_PRODUCT.get(product_type.lower(), ()))
    if extra:
        # Strip whitespace + dedupe while preserving original order.
        seen = {p.lower() for p in parts}
        for term in extra:
            t = term.strip()
            if t and t.lower() not in seen:
                parts.append(t)
                seen.add(t.lower())
    return ", ".join(parts)


def supported_product_types() -> list[str]:
    """Expose the keys for UI dropdowns."""
    return sorted(_PER_PRODUCT.keys())
