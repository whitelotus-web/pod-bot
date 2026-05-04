"""Catalog of POD product blueprints per platform.

This is the curated whitelist that the bot can place a design onto.
Real Printify catalog has 800+ blueprints; here we expose the 10 best-sellers
that account for ~80% of POD revenue, plus presets for one-click selection.

If you need more blueprints, append entries below — no other changes required.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ProductBlueprint:
    id: str  # canonical id used in Campaign.product_types
    label: str
    category: str  # apparel | drinkware | accessory | wallart | sticker
    platform_blueprint: dict[str, int | str]  # per-platform native id
    base_price_usd: float  # rough wholesale base
    suggested_retail_usd: float
    description: str

    def to_dict(self) -> dict:
        return asdict(self)


# Top 10 best-sellers (Printify revenue 2024 stats reference)
CATALOG: list[ProductBlueprint] = [
    ProductBlueprint(
        id="tshirt_unisex",
        label="Áo thun unisex",
        category="apparel",
        platform_blueprint={"printify": 5, "printful": 71},
        base_price_usd=8.0,
        suggested_retail_usd=19.99,
        description="Bella+Canvas 3001 — best-seller toàn cầu, 100% cotton, unisex.",
    ),
    ProductBlueprint(
        id="hoodie",
        label="Hoodie",
        category="apparel",
        platform_blueprint={"printify": 49, "printful": 162},
        base_price_usd=22.0,
        suggested_retail_usd=42.99,
        description="Áo hoodie Gildan 18500 — bán chạy mùa thu/đông.",
    ),
    ProductBlueprint(
        id="sweatshirt",
        label="Sweatshirt",
        category="apparel",
        platform_blueprint={"printify": 36, "printful": 145},
        base_price_usd=18.0,
        suggested_retail_usd=34.99,
        description="Áo sweatshirt Gildan 18000 — không mũ, cổ tròn.",
    ),
    ProductBlueprint(
        id="tank_top",
        label="Áo tank top",
        category="apparel",
        platform_blueprint={"printify": 80, "printful": 175},
        base_price_usd=10.0,
        suggested_retail_usd=22.99,
        description="Tank top mùa hè, fitness niche bán cực mạnh.",
    ),
    ProductBlueprint(
        id="kids_tshirt",
        label="Áo trẻ em",
        category="apparel",
        platform_blueprint={"printify": 157, "printful": 96},
        base_price_usd=10.0,
        suggested_retail_usd=21.99,
        description="Áo thun trẻ em — niche family/parents rất hợp.",
    ),
    ProductBlueprint(
        id="mug_11oz",
        label="Mug 11oz",
        category="drinkware",
        platform_blueprint={"printify": 9, "printful": 19},
        base_price_usd=6.0,
        suggested_retail_usd=14.99,
        description="Cốc sứ 11oz — nhanh ship, lợi nhuận tốt, gift bestseller.",
    ),
    ProductBlueprint(
        id="tote_bag",
        label="Túi tote",
        category="accessory",
        platform_blueprint={"printify": 19, "printful": 105},
        base_price_usd=9.0,
        suggested_retail_usd=21.99,
        description="Túi vải canvas in cả 2 mặt, niche eco-friendly mạnh.",
    ),
    ProductBlueprint(
        id="phone_case",
        label="Ốp điện thoại",
        category="accessory",
        platform_blueprint={"printify": 29, "printful": 181},
        base_price_usd=12.0,
        suggested_retail_usd=24.99,
        description="iPhone/Samsung — gen-Z mua nhiều, in nét cao.",
    ),
    ProductBlueprint(
        id="poster",
        label="Poster (wall art)",
        category="wallart",
        platform_blueprint={"printify": 97, "printful": 1},
        base_price_usd=11.0,
        suggested_retail_usd=29.99,
        description="Poster matte — niche home decor, lợi nhuận cao.",
    ),
    ProductBlueprint(
        id="sticker",
        label="Sticker",
        category="sticker",
        platform_blueprint={"printify": 145, "printful": 358},
        base_price_usd=2.0,
        suggested_retail_usd=4.99,
        description="Sticker die-cut, impulse buy, volume cao.",
    ),
]


PRESETS: dict[str, dict] = {
    "top_sellers": {
        "label": "Top sellers (khuyến nghị)",
        "description": "6 sản phẩm bán chạy nhất, coverage ~80% doanh thu POD.",
        "ids": ["tshirt_unisex", "hoodie", "sweatshirt", "mug_11oz", "tote_bag", "poster"],
    },
    "apparel": {
        "label": "Chỉ áo",
        "description": "Áo thun + hoodie + sweatshirt + tank top + áo trẻ em.",
        "ids": ["tshirt_unisex", "hoodie", "sweatshirt", "tank_top", "kids_tshirt"],
    },
    "lifestyle": {
        "label": "Lifestyle bundle",
        "description": "10 loại đa dạng: áo + drinkware + accessory + wallart + sticker.",
        "ids": [b.id for b in CATALOG],
    },
    "tshirt_only": {
        "label": "Chỉ áo thun",
        "description": "Tối giản — đăng đúng 1 áo thun unisex/design.",
        "ids": ["tshirt_unisex"],
    },
}


def get_blueprint(product_id: str) -> ProductBlueprint | None:
    return next((b for b in CATALOG if b.id == product_id), None)


def list_catalog() -> list[dict]:
    return [b.to_dict() for b in CATALOG]


def list_presets() -> dict[str, dict]:
    return PRESETS
