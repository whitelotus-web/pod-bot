"""SEO writer — auto-generate Etsy-friendly title, tags, description per product.

Strategy:
1. If user has a Gemini text key, ask Gemini to write SEO copy.
2. Else fall back to a deterministic template that still scores well on Etsy.

Output guarantees:
- title ≤ 140 chars (Etsy max)
- exactly 13 tags, each ≤ 20 chars (Etsy enforces)
- description: 300-600 chars, includes "Gift for X", bullet points, niche keywords.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from app.core.config import settings
from app.services.catalog import ProductBlueprint, get_blueprint

logger = logging.getLogger(__name__)


@dataclass
class SEOContent:
    title: str
    description: str
    tags: list[str]
    source: str  # "ai" | "template"


_TAG_CLEAN = re.compile(r"[^a-zA-Z0-9 ]+")


def _clean_tag(t: str) -> str:
    t = _TAG_CLEAN.sub("", t).strip().lower()
    return t[:20]


def _fallback(keyword: str, niche: str, blueprint: ProductBlueprint) -> SEOContent:
    """Deterministic template that scores OK on Etsy."""
    keyword = keyword.strip() or niche
    niche_clean = niche.strip() or keyword

    product_label = blueprint.label.lower()
    product_short = {
        "tshirt_unisex": "tee",
        "hoodie": "hoodie",
        "sweatshirt": "sweatshirt",
        "mug_11oz": "mug",
        "tote_bag": "tote",
        "phone_case": "case",
        "poster": "poster",
        "sticker": "sticker",
    }.get(blueprint.id, blueprint.id.replace("_", " "))

    title = (
        f"{keyword.title()} {product_short.title()}, "
        f"{niche_clean.title()} Gift, "
        f"Trendy {blueprint.category.title()} Lover Apparel"
    )[:140]

    tags_raw = [
        keyword,
        niche_clean,
        f"{niche_clean} gift",
        f"{niche_clean} lover",
        f"{keyword} {product_short}",
        f"{niche_clean} {product_short}",
        f"trendy {product_short}",
        f"gift for {niche_clean}",
        f"{niche_clean} apparel",
        f"{niche_clean} fan",
        f"cute {niche_clean}",
        f"{keyword} design",
        f"{niche_clean} mom",
    ]
    tags = []
    for t in tags_raw:
        c = _clean_tag(t)
        if c and c not in tags:
            tags.append(c)
    while len(tags) < 13:
        tags.append(_clean_tag(f"{niche_clean} {len(tags)}"))
    tags = tags[:13]

    description = (
        f"⭐ {keyword.title()} {product_label} — perfect gift for {niche_clean} lovers.\n\n"
        f"{blueprint.description}\n\n"
        f"✨ Why you'll love it:\n"
        f"• Premium {blueprint.category} quality, soft & durable\n"
        f"• Original {niche_clean} design printed on demand\n"
        f"• Makes a thoughtful gift for birthdays, holidays, or any special occasion\n"
        f"• Fast shipping worldwide\n\n"
        f"Tags: {keyword}, {niche_clean}, {product_short} gift\n"
    )
    return SEOContent(title=title, description=description, tags=tags, source="template")


def _ai_generate(
    keyword: str, niche: str, blueprint: ProductBlueprint, api_key: str
) -> SEOContent | None:
    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        prompt = f"""Write Etsy listing SEO for a print-on-demand product.

Keyword: {keyword}
Niche: {niche}
Product: {blueprint.label} ({blueprint.category})

Output STRICT JSON with keys:
  "title": string ≤140 chars, mention product type and a buyer use-case (gift, fan, mom...).
  "description": string 300-600 chars. Friendly, scannable, with 4 bullet points.
  "tags": array of EXACTLY 13 short keyword phrases, each ≤20 chars, lowercase, no special chars.

Focus on Etsy long-tail SEO. No markdown, no code fences, only the JSON object.
"""
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        text = (resp.text or "").strip()
        text = re.sub(r"^```json\s*|\s*```$", "", text)
        data = json.loads(text)

        title = str(data.get("title", ""))[:140]
        desc = str(data.get("description", ""))
        tags = [_clean_tag(t) for t in data.get("tags", []) if str(t).strip()]
        tags = [t for t in tags if t][:13]
        if not title or not tags:
            return None
        return SEOContent(title=title, description=desc, tags=tags, source="ai")
    except Exception as exc:  # noqa: BLE001
        logger.warning("SEO AI generate failed: %s", exc)
        return None


def generate_seo(
    *,
    keyword: str,
    niche: str,
    product_id: str,
    user_id: int | None = None,
    db=None,
) -> SEOContent:
    """Generate SEO content for a single (keyword, product) pair."""
    blueprint = get_blueprint(product_id) or get_blueprint("tshirt_unisex")
    assert blueprint is not None

    api_key = None
    if user_id is not None and db is not None:
        from app.core.crypto import decrypt
        from app.models import AIKey

        row = (
            db.query(AIKey)
            .filter_by(user_id=user_id, engine="gemini", is_active=True)
            .order_by(AIKey.id.desc())
            .first()
        )
        if row:
            try:
                api_key = decrypt(row.encrypted_key)
            except Exception:  # noqa: BLE001
                api_key = None
    api_key = api_key or settings.gemini_api_key

    if api_key:
        ai = _ai_generate(keyword, niche, blueprint, api_key)
        if ai is not None:
            return ai
    return _fallback(keyword, niche, blueprint)


def suggest_shop_names(niche: str, count: int = 6, api_key: str | None = None) -> list[str]:
    """Suggest catchy shop names for a niche."""
    api_key = api_key or settings.gemini_api_key
    if not api_key or not niche.strip():
        # Deterministic fallback
        n = niche.strip().title()
        return [
            f"{n} Studio",
            f"{n} Co.",
            f"The {n} Society",
            f"{n} & Co.",
            f"Hello {n}",
            f"{n} Apparel",
        ][:count]
    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        prompt = f"""Suggest {count} catchy, brandable Etsy shop names for the niche "{niche}".
Each name 2-3 words, evocative, memorable, ≤25 chars. No emoji, no quotes.
Output JSON array of strings only."""
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        text = re.sub(r"^```json\s*|\s*```$", "", (resp.text or "").strip())
        names = json.loads(text)
        names = [str(n).strip()[:25] for n in names if str(n).strip()]
        return names[:count] or [f"{niche.title()} Studio"]
    except Exception as exc:  # noqa: BLE001
        logger.warning("Shop name suggest failed: %s", exc)
        return [f"{niche.title()} Studio", f"{niche.title()} Co."]
