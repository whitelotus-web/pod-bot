"""AI shop branding generator — banner / logo / about / policies / sections.

Etsy doesn't have an API for setting these (most shop-customization fields
are UI-only), but we can pre-generate the assets and copy so the user only
has to upload + paste.

Per shop niche, this generator returns:
- `banner_prompt`: prompt for image-gen model to render a 1200×300 banner
- `logo_prompt`: prompt for a 500×500 vector-style logo
- `about_section`: 600-1000 word shop story (multilingual support TBD)
- `announcement`: weekly rotating one-liner
- `policies`: ship/return/refund template (POD-tuned)
- `shop_sections`: 4-6 collection names that group designs

Two implementations: a deterministic template engine that always works
without AI keys, and an AI-driven path when the seo_writer role has a key.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ShopBrandingPack:
    banner_prompt: str = ""
    logo_prompt: str = ""
    about_section: str = ""
    announcement: str = ""
    policies: str = ""
    shop_sections: list[str] = field(default_factory=list)
    source: str = "template"  # template | ai


def _template_pack(niche: str) -> ShopBrandingPack:
    n = (niche or "design").strip()
    pack = ShopBrandingPack(source="template")
    pack.banner_prompt = (
        f"Etsy shop banner 1200x300, theme '{n}'. Hand-illustrated, warm color palette, "
        "soft texture, minimalist composition with the shop name at left, supporting "
        "imagery at right. Print-quality clean edges, no watermark."
    )
    pack.logo_prompt = (
        f"Boutique POD shop logo for a '{n}' brand. Simple monogram or icon, square "
        "500x500, single-color silhouette + delicate accent, fits a small avatar at "
        "favicon size."
    )
    pack.about_section = (
        f"Welcome to our little corner of Etsy! ✨\n\n"
        f"We started this shop because we believe that the things you wear and the "
        f"things you bring into your home should bring a little more joy into every "
        f"day. Each design here is hand-crafted around the world of {n} — a niche "
        f"that's always meant a lot to us — and printed on demand by trusted partners "
        f"so we can offer comfortable, durable, ethically-produced products without "
        f"the waste of mass production.\n\n"
        f"Every order is printed when you place it, packed with care, and shipped "
        f"directly to you. You're not just buying a t-shirt or a mug — you're "
        f"supporting a tiny independent shop that pours real thought into every "
        f"design.\n\n"
        f"Thank you so much for stopping by. If you have questions, custom requests, "
        f"or just want to say hi, send us a message — we read every one and reply "
        f"within 24 hours.\n\n"
        f"With love,\nThe team behind {n.title()} Studio"
    )
    pack.announcement = (
        f"💌 New {n} designs every week — follow the shop to get notified first!"
    )
    pack.policies = (
        "**Shipping**\n"
        "- Most items print and ship within 3-5 business days.\n"
        "- Tracking is provided as soon as your order leaves the print facility.\n"
        "- US delivery typically takes 5-10 business days; international 10-21.\n\n"
        "**Returns & Exchanges**\n"
        "- Because every item is made-to-order, we don't accept returns for size/"
        "color preference. Please double-check the size chart before ordering.\n"
        "- If your item arrives damaged, defective, or different from the listing, "
        "message us within 30 days with a photo and we'll replace or refund right "
        "away.\n\n"
        "**Refunds**\n"
        "- We process valid refunds within 3 business days of receiving the report.\n"
        "- Refunds reach your card within 5-10 business days of being processed.\n\n"
        "**Custom Requests**\n"
        "- Reply to any of our messages — happy to discuss color/size/text changes "
        "(turnaround usually +3 days).\n"
    )
    pack.shop_sections = [
        f"{n.title()} Apparel",
        f"{n.title()} Accessories",
        "Gift Ideas",
        "New Arrivals",
        "Best Sellers",
    ]
    return pack


_AI_PROMPT = """Generate Etsy shop branding for a print-on-demand store in the niche \"{niche}\".

Output STRICT JSON with these keys (no markdown, no fences):
{{
  "banner_prompt": "concise prompt suitable for AI image gen, 1-2 sentences, hand-illustrated 1200x300 shop banner",
  "logo_prompt": "concise prompt for a square 500x500 minimal logo",
  "about_section": "600-1000 word warm, personal first-person shop story",
  "announcement": "single sentence shop announcement, friendly",
  "policies": "markdown sections: Shipping / Returns / Refunds / Custom Requests, POD-tuned",
  "shop_sections": ["4-6 short collection names"]
}}
"""


def generate(
    niche: str,
    *,
    ai_caller=None,  # callable(prompt: str) -> str
) -> ShopBrandingPack:
    """Generate branding pack via AI if available, else deterministic template."""
    niche = niche.strip()
    if ai_caller is not None:
        try:
            raw = ai_caller(_AI_PROMPT.format(niche=niche))
            text = re.sub(r"^```json\s*|\s*```$", "", (raw or "").strip())
            data = json.loads(text)
            sections = data.get("shop_sections", [])
            if not isinstance(sections, list):
                sections = []
            pack = ShopBrandingPack(
                banner_prompt=str(data.get("banner_prompt", "")),
                logo_prompt=str(data.get("logo_prompt", "")),
                about_section=str(data.get("about_section", "")),
                announcement=str(data.get("announcement", "")),
                policies=str(data.get("policies", "")),
                shop_sections=[str(s) for s in sections][:6],
                source="ai",
            )
            # Lightweight validation — fall back if too thin.
            if len(pack.about_section) >= 400 and pack.banner_prompt and pack.shop_sections:
                return pack
        except Exception as exc:  # noqa: BLE001
            logger.warning("Branding AI generation failed, falling back to template: %s", exc)
    return _template_pack(niche)
