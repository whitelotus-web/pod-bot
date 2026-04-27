"""20 art-school prompt templates ("xưởng thiết kế").

Each template encodes a deep visual style with reference artists, era, palette
and composition cues. The pipeline picks one template per design (round-robin
or by tag) and substitutes `{niche}` / `{keyword}` into it. Plus a locked
POD-spec suffix that enforces transparent background, no watermarks, etc.

Goal: differentiate the shop from generic "vintage cat tshirt" AI spam by
giving each design a genuine school-of-design context, which is the moat the
user explicitly asked for.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PromptTemplate:
    id: str
    name: str
    family: str  # cinematic | vintage | cultural | botanical | brutalist
    body: str  # uses {niche} and {keyword}
    palette_hint: str = ""


_POD_SUFFIX = (
    " The composition must be print-ready: centered subject on a transparent "
    "background, no watermark, no signature, no border, no copyright marks, "
    "no text unless explicitly part of the design, sharp clean edges suitable "
    "for DTG printing. Avoid extreme saturation; pick colors that hold up on "
    "both light and dark fabrics. Output a flat illustration suitable for "
    "apparel."
)


TEMPLATES: tuple[PromptTemplate, ...] = (
    # ───────────── Cinematic ─────────────
    PromptTemplate(
        id="cinematic_wes_anderson",
        name="Wes Anderson Symmetry",
        family="cinematic",
        body=(
            "A {niche} scene in the style of Wes Anderson — perfectly symmetrical "
            "composition, pastel mustard / dusty pink / aquamarine palette, "
            "centered framing, Futura-style typographic hints. {keyword} as the "
            "central subject, photographed as if for The Grand Budapest Hotel. "
            "Diorama feel, miniature charm, vintage 1960s European storybook."
        ),
        palette_hint="mustard, dusty pink, aquamarine, cream",
    ),
    PromptTemplate(
        id="cinematic_christopher_doyle",
        name="Christopher Doyle Hong Kong",
        family="cinematic",
        body=(
            "{niche} composition shot in the style of Christopher Doyle's "
            "cinematography for Wong Kar-wai films. Neon green, magenta, "
            "deep teal, rain on glass, motion blur, narrow depth of field. "
            "{keyword} rendered as a moody late-90s Hong Kong nightscape with "
            "saturated reflective surfaces and grainy 35mm texture."
        ),
        palette_hint="neon green, magenta, deep teal",
    ),
    PromptTemplate(
        id="cinematic_deakins_teal_orange",
        name="Roger Deakins Teal & Orange",
        family="cinematic",
        body=(
            "{niche} illustrated like a still from a Roger Deakins film — "
            "Blade Runner 2049 atmosphere, deep teal shadows, orange amber "
            "highlights, vast empty composition with a single subject silhouette. "
            "{keyword} is the lone subject, dwarfed by negative space, painterly "
            "atmospheric haze."
        ),
        palette_hint="teal shadows, amber highlights",
    ),
    PromptTemplate(
        id="cinematic_gordon_willis",
        name="Gordon Willis Low-Key",
        family="cinematic",
        body=(
            "{niche} portrait in Gordon Willis's low-key style — top-light only, "
            "deep umber shadows, single rim of warm highlight, 1970s film grain. "
            "{keyword} emerges from darkness, Godfather-era cinematography mood, "
            "no detail in the shadows, soft focus, sepia warmth."
        ),
        palette_hint="umber shadow, warm rim light, sepia",
    ),
    # ───────────── Vintage ─────────────
    PromptTemplate(
        id="vintage_70s_magazine",
        name="1970s Magazine Spread",
        family="vintage",
        body=(
            "{niche} as a 1970s lifestyle magazine cover illustration — "
            "warm earth tones (avocado, harvest gold, burnt orange), thick "
            "outlined illustration, hand-set serif headline aesthetics. "
            "{keyword} rendered like a Norman Rockwell-meets-Push-Pin Studios "
            "spread, halftone shading, slight off-register print texture."
        ),
        palette_hint="avocado, harvest gold, burnt orange",
    ),
    PromptTemplate(
        id="vintage_50s_travel_poster",
        name="1950s Travel Poster",
        family="vintage",
        body=(
            "{niche} drawn as a 1950s mid-century travel poster (think Pan Am, "
            "TWA, SAS posters by Ivar Husa or David Klein) — bold flat shapes, "
            "simplified geometry, optimistic pastel sky. {keyword} as the hero "
            "subject, hand-lettered destination feel, screen-printed look with "
            "limited 4-color palette."
        ),
        palette_hint="pastel sky blue, soft red, mustard, ivory",
    ),
    PromptTemplate(
        id="vintage_soviet_propaganda",
        name="Soviet Constructivist",
        family="vintage",
        body=(
            "{niche} in the style of Soviet constructivist posters — Aleksandr "
            "Rodchenko, El Lissitzky — diagonal composition, bold primary red "
            "and black, geometric shapes, sans-serif Cyrillic-inspired type. "
            "{keyword} treated as a heroic dynamic figure, screen-print "
            "limitations, rough paper texture."
        ),
        palette_hint="red, black, cream paper",
    ),
    PromptTemplate(
        id="vintage_bauhaus",
        name="Bauhaus Geometry",
        family="vintage",
        body=(
            "{niche} reduced to pure Bauhaus geometry — primary red, blue, yellow, "
            "black on cream — circles, triangles, squares, Herbert Bayer "
            "typography. {keyword} expressed as a 1920s Weimar-era abstract "
            "composition, Kandinsky-meets-Moholy-Nagy, flat shapes with "
            "intentional overlap."
        ),
        palette_hint="primary red, blue, yellow, black, cream",
    ),
    PromptTemplate(
        id="vintage_art_deco",
        name="Art Deco Gatsby",
        family="vintage",
        body=(
            "{niche} as an Art Deco illustration — gold linework on deep navy or "
            "emerald, geometric symmetry, sun-ray patterns, Erté fashion plate "
            "stylization. {keyword} as the centerpiece, 1920s Gatsby luxury "
            "aesthetic, foil-stamp finish suggested by metallic golds."
        ),
        palette_hint="gold, navy, emerald, ivory",
    ),
    PromptTemplate(
        id="vintage_ukiyo_e",
        name="Ukiyo-e Woodblock",
        family="vintage",
        body=(
            "{niche} in the style of Edo-period ukiyo-e woodblock prints — "
            "Hokusai and Hiroshige reference. Flat color planes, hand-drawn "
            "outlines, traditional indigo / vermillion / earth tones. "
            "{keyword} rendered with the dynamic flat composition typical of "
            "Tōkaidō series, including subtle paper texture."
        ),
        palette_hint="indigo, vermillion, ochre, mineral green",
    ),
    # ───────────── Cultural / Architectural ─────────────
    PromptTemplate(
        id="cultural_french_boulangerie",
        name="French Boulangerie",
        family="cultural",
        body=(
            "{niche} illustrated as a charming French boulangerie scene — "
            "Parisian pastel storefront, hand-painted chalkboard typography, "
            "soft watercolor washes. {keyword} as the focus item, cobblestone "
            "warmth, café-de-Flore atmosphere, Eiffel Tower hint in background."
        ),
        palette_hint="pastel blue, butter yellow, terracotta, cream",
    ),
    PromptTemplate(
        id="cultural_tuscany_villa",
        name="Tuscan Villa",
        family="cultural",
        body=(
            "{niche} drawn as a sun-drenched Tuscan villa scene — terracotta "
            "rooftops, cypress trees, warm ochre walls, vineyard grids. "
            "{keyword} situated as if photographed by Slim Aarons in 1965, "
            "Mediterranean light, hand-painted travel-journal feel."
        ),
        palette_hint="terracotta, cypress green, ochre, sun-bleached white",
    ),
    PromptTemplate(
        id="cultural_kyoto_temple",
        name="Kyoto Zen Temple",
        family="cultural",
        body=(
            "{niche} in a Kyoto temple atmosphere — moss garden, wooden "
            "torii gates, raked sand patterns, cherry-blossom petals on still "
            "water. {keyword} integrated into a contemplative zen composition, "
            "muted ink-wash palette, sumi-e brushwork energy."
        ),
        palette_hint="moss green, weathered wood, sakura pink, ink black",
    ),
    PromptTemplate(
        id="cultural_marrakech_medina",
        name="Marrakech Medina",
        family="cultural",
        body=(
            "{niche} amid Marrakech medina textures — geometric Moroccan "
            "zellige tile patterns, brass lanterns, indigo doorways, spice-stall "
            "color burst. {keyword} as the focal point, riad courtyard "
            "atmosphere, hand-rendered with travel-poster style."
        ),
        palette_hint="indigo, saffron, terracotta, brass gold",
    ),
    PromptTemplate(
        id="cultural_havana_facade",
        name="Havana Facade",
        family="cultural",
        body=(
            "{niche} against a peeling Havana facade — pastel teal, salmon and "
            "mustard plaster, wrought-iron balconies, classic 1950s American "
            "car silhouette. {keyword} as the scene's lead, golden hour Cuban "
            "light, hand-illustrated travelogue style."
        ),
        palette_hint="havana teal, salmon, mustard, cream",
    ),
    # ───────────── Botanical / Scientific ─────────────
    PromptTemplate(
        id="botanical_ernst_haeckel",
        name="Ernst Haeckel Plates",
        family="botanical",
        body=(
            "{niche} drawn in the style of Ernst Haeckel's Kunstformen der Natur "
            "lithograph plates — symmetrical specimen layout on aged ivory paper, "
            "fine ink linework, scientific Latin labels suggested but not legible. "
            "{keyword} treated as a 19th-century natural-history specimen, "
            "hand-engraved feel."
        ),
        palette_hint="ink black, sepia, aged ivory",
    ),
    PromptTemplate(
        id="botanical_field_guide",
        name="Vintage Field Guide",
        family="botanical",
        body=(
            "{niche} illustrated as a vintage botanical field guide page — "
            "Pierre-Joseph Redouté or Anne Pratt watercolor reference. Subject "
            "centered with hand-lettered Latin name beneath. {keyword} rendered "
            "with detailed gouache-and-watercolor technique on textured paper."
        ),
        palette_hint="botanical green, terracotta, soft cream",
    ),
    PromptTemplate(
        id="botanical_mycology",
        name="Mycology Field Guide",
        family="botanical",
        body=(
            "{niche} as an antique mycology field-guide plate — multiple mushroom "
            "specimens arranged like a museum display, cross-section diagrams "
            "alongside upright specimens. {keyword} as the headline organism, "
            "pen-and-ink with selective watercolor wash, aged label aesthetics."
        ),
        palette_hint="forest green, deep red cap, ivory paper, brown ink",
    ),
    # ───────────── Brutalist / Modern ─────────────
    PromptTemplate(
        id="brutalist_swiss_grid",
        name="Swiss Grid Brutalist",
        family="brutalist",
        body=(
            "{niche} composed on a strict Swiss grid — Müller-Brockmann reference. "
            "Bold sans-serif (Helvetica/Akzidenz-Grotesk), monochromatic with one "
            "accent color, precise alignment. {keyword} treated as a typographic "
            "hero, no decoration, ruthlessly minimal."
        ),
        palette_hint="black, white, single accent (red or blue)",
    ),
    PromptTemplate(
        id="brutalist_anti_design",
        name="Anti-Design Riso",
        family="brutalist",
        body=(
            "{niche} as a contemporary anti-design / web-brutalist riso print — "
            "intentionally clashing fluorescent pink + electric blue, crooked "
            "monospace typography, photocopy texture, off-register layers. "
            "{keyword} expressed as DIY zine cover, post-internet aesthetic."
        ),
        palette_hint="riso fluorescent pink, electric blue, paper white",
    ),
)


def by_family(family: str) -> list[PromptTemplate]:
    return [t for t in TEMPLATES if t.family == family]


def by_id(template_id: str) -> PromptTemplate | None:
    return next((t for t in TEMPLATES if t.id == template_id), None)


def render(template_id: str, *, niche: str, keyword: str) -> str:
    """Render a template body with substitutions + locked POD suffix."""
    tpl = by_id(template_id)
    if tpl is None:
        raise KeyError(f"Unknown prompt template: {template_id}")
    body = tpl.body.format(niche=niche or "design", keyword=keyword or niche or "subject")
    return body + _POD_SUFFIX


def families() -> list[str]:
    return sorted({t.family for t in TEMPLATES})


def list_all() -> list[dict]:
    return [
        {
            "id": t.id,
            "name": t.name,
            "family": t.family,
            "palette_hint": t.palette_hint,
            "preview": t.body[:120] + ("..." if len(t.body) > 120 else ""),
        }
        for t in TEMPLATES
    ]
