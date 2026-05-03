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


_PROMPT_TEMPLATE = """Write Etsy listing SEO for a print-on-demand product.

Keyword: {keyword}
Niche: {niche}
Product: {label} ({category})

Output STRICT JSON with keys:
  "title": string ≤140 chars, mention product type and a buyer use-case (gift, fan, mom...).
  "description": string 300-600 chars. Friendly, scannable, with 4 bullet points.
  "tags": array of EXACTLY 13 short keyword phrases, each ≤20 chars, lowercase, no special chars.

Focus on Etsy long-tail SEO. No markdown, no code fences, only the JSON object.
"""


def _parse_seo_json(text: str) -> SEOContent | None:
    text = re.sub(r"^```json\s*|\s*```$", "", (text or "").strip())
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning("SEO AI returned non-JSON: %s", exc)
        return None
    title = str(data.get("title", ""))[:140]
    desc = str(data.get("description", ""))
    tags = [_clean_tag(t) for t in data.get("tags", []) if str(t).strip()]
    tags = [t for t in tags if t][:13]
    if not title or not tags:
        return None
    return SEOContent(title=title, description=desc, tags=tags, source="ai")


def _ai_generate_gemini(
    keyword: str, niche: str, blueprint: ProductBlueprint, api_key: str
) -> SEOContent | None:
    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=_PROMPT_TEMPLATE.format(
                keyword=keyword, niche=niche, label=blueprint.label, category=blueprint.category
            ),
        )
        return _parse_seo_json(resp.text or "")
    except Exception as exc:  # noqa: BLE001
        if _is_quota(exc):
            raise
        logger.warning("SEO Gemini call failed: %s", exc)
        return None


def _ai_generate_openai(
    keyword: str, niche: str, blueprint: ProductBlueprint, api_key: str
) -> SEOContent | None:
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": _PROMPT_TEMPLATE.format(
                        keyword=keyword,
                        niche=niche,
                        label=blueprint.label,
                        category=blueprint.category,
                    ),
                }
            ],
            response_format={"type": "json_object"},
        )
        return _parse_seo_json(resp.choices[0].message.content or "")
    except Exception as exc:  # noqa: BLE001
        if _is_quota(exc):
            raise
        logger.warning("SEO OpenAI call failed: %s", exc)
        return None


def _is_quota(exc: BaseException) -> bool:
    # Lazy import to avoid circular dependency at module load.
    from app.services.ai_router import is_quota_error

    return is_quota_error(exc)


def generate_seo(
    *,
    keyword: str,
    niche: str,
    product_id: str,
    user_id: int | None = None,
    db=None,
) -> SEOContent:
    """Generate SEO content for a single (keyword, product) pair.

    Routes through `ai_router.with_failover` with role='seo_writer' so the
    user's role-scoped, priority-ordered keys are used and quota errors
    rotate to the next candidate (Gemini -> OpenAI). Falls back to a
    deterministic template when no key is available or all AI keys fail.
    """
    blueprint = get_blueprint(product_id) or get_blueprint("tshirt_unisex")
    assert blueprint is not None

    if user_id is not None and db is not None:
        from app.services.ai_router import AIKeyCandidate, AISoftError, with_failover

        def _call(cand: AIKeyCandidate) -> SEOContent:
            if not cand.api_key:
                raise AISoftError("missing api key")
            if cand.engine == "gemini":
                out = _ai_generate_gemini(keyword, niche, blueprint, cand.api_key)
            elif cand.engine == "openai":
                out = _ai_generate_openai(keyword, niche, blueprint, cand.api_key)
            else:
                raise AISoftError(f"seo_writer not supported by engine {cand.engine}")
            if out is None:
                # Engine returned unparseable JSON or empty output. Raise
                # AISoftError so with_failover rotates to the next candidate
                # (e.g. OpenAI's response_format=json_object often parses where
                # raw Gemini occasionally doesn't) instead of giving up after
                # the first engine.
                raise AISoftError(f"{cand.engine} returned unparseable SEO")
            return out

        try:
            return with_failover(
                db, user_id=user_id, role="seo_writer", engine=None, fn=_call
            )
        except Exception as exc:  # noqa: BLE001
            logger.info("SEO with_failover exhausted (%s) — using template fallback.", exc)

    # No DB context, no keys, or all keys failed — fall through to template.
    if settings.gemini_api_key:
        ai = _ai_generate_gemini(keyword, niche, blueprint, settings.gemini_api_key)
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
