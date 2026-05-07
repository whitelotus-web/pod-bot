"""Smoke tests — verify modules import + basic invariants."""
from __future__ import annotations

import os
import tempfile


def test_settings_loads():
    os.environ.setdefault("MEDIA_ROOT", tempfile.gettempdir())
    from app.core.config import settings

    assert settings.app_name


def test_keyword_aggregator_registry():
    from app.services.keywords.aggregator import ALL_SOURCES, SOURCE_REGISTRY

    for name in ALL_SOURCES:
        assert name in SOURCE_REGISTRY


def test_ai_engine_factory():
    from app.services.ai import get_engine

    for name in ("gemini", "openai", "replicate"):
        eng = get_engine(name)
        assert eng.name in ("gemini", "openai", "replicate")


def test_mockup_templates():
    os.environ.setdefault("MEDIA_ROOT", tempfile.mkdtemp())
    from app.services.mockup import PillowMockup

    templates = PillowMockup().available_templates()
    assert "tshirt_white" in templates
    assert "tshirt_black" in templates


def test_platform_meta_covers_first_class():
    from app.services.platforms import PLATFORM_META

    api_backed = {"printify", "printful", "etsy", "gelato"}
    manual = {"redbubble", "society6", "amazon_merch", "spreadshirt"}
    assert api_backed.issubset(PLATFORM_META.keys())
    assert manual.issubset(PLATFORM_META.keys())
    for meta in PLATFORM_META.values():
        assert meta["supported"] is True


def test_platform_factory_rejects_unknown():
    import pytest

    from app.services.platforms import get_platform

    for unknown in ("teespring", "merch_amazon", "definitely_not_a_platform"):
        with pytest.raises(ValueError, match="Unknown platform"):
            get_platform(unknown, account=None)


def test_celery_tasks_registered():
    from app.workers import pipeline, scheduler  # noqa: F401
    from app.workers.celery_app import celery_app

    assert "app.workers.pipeline.run_campaign" in celery_app.tasks
    assert "app.workers.scheduler.tick" in celery_app.tasks


def test_crypto_roundtrip():
    from app.core.crypto import decrypt, encrypt, mask

    token = encrypt("sk-test-1234567890")
    assert token != "sk-test-1234567890"
    assert decrypt(token) == "sk-test-1234567890"
    assert mask("sk-test-1234567890") == "sk-t••••••7890"


def test_prompt_templates_library():
    from app.services.prompts import TEMPLATES, TEMPLATES_BY_ID, compose_preview

    assert len(TEMPLATES) >= 5
    ids = {t.id for t in TEMPLATES}
    assert len(ids) == len(TEMPLATES)  # unique ids
    assert "vintage_retro" in TEMPLATES_BY_ID
    final = compose_preview("cat lovers", niche="cats", style=TEMPLATES[0].style)
    assert "cat lovers" in final
    assert "vintage" in final.lower()


def test_engine_accepts_override_key():
    from app.services.ai import get_engine

    eng = get_engine("gemini", api_key="fake")
    assert eng.api_key_override == "fake"


def test_catalog_blueprints_and_presets():
    from app.services.catalog import CATALOG, PRESETS, get_blueprint, list_catalog

    assert len(CATALOG) >= 6
    ids = {b.id for b in CATALOG}
    assert {"tshirt_unisex", "hoodie", "mug_11oz", "tote_bag", "poster"} <= ids
    for preset in ("top_sellers", "apparel", "lifestyle", "tshirt_only"):
        assert preset in PRESETS
        # Every id referenced by a preset must exist in catalog
        for pid in PRESETS[preset]["ids"]:
            assert get_blueprint(pid) is not None
    # Listing endpoint serializes correctly
    serialized = list_catalog()
    assert all("id" in p and "label" in p and "platform_blueprint" in p for p in serialized)


def test_seo_fallback_template_shape():
    from app.services.seo import generate_seo

    out = generate_seo(
        keyword="cat",
        niche="cat lovers",
        product_id="tshirt_unisex",
        user_id=None,
        db=None,
    )
    assert out.source in ("template", "ai")
    assert 0 < len(out.title) <= 140
    assert len(out.tags) == 13
    assert all(len(t) <= 20 for t in out.tags)
    assert "cat" in out.description.lower()


def test_ai_router_quota_detection():
    from app.services.ai_router import is_quota_error

    assert is_quota_error(Exception("HTTP 429 too many requests"))
    assert is_quota_error(Exception("Quota exceeded for project"))
    assert is_quota_error(Exception("insufficient_quota: please add billing"))
    assert not is_quota_error(Exception("invalid api key"))
    assert not is_quota_error(Exception("connection refused"))


def test_ai_router_role_engines_disjoint():
    from app.services.ai_router import ROLE_ENGINES

    # Image gen must include the heavy engines; text roles must NOT include replicate
    assert "replicate" in ROLE_ENGINES["image_generation"]
    assert "replicate" not in ROLE_ENGINES["seo_writer"]
    assert "replicate" not in ROLE_ENGINES["keyword_expansion"]


def test_bg_remove_threshold_fallback(tmp_path):
    from PIL import Image

    from app.services.bg_remove import _threshold_fallback

    src = tmp_path / "white_disk.png"
    img = Image.new("RGB", (8, 8), (255, 255, 255))
    img.putpixel((4, 4), (255, 0, 0))
    img.save(src, "PNG")
    out = _threshold_fallback(src, tmp_path / "out.png")
    assert out.exists()
    rgba = Image.open(out).convert("RGBA")
    # White corner is now transparent
    assert rgba.getpixel((0, 0))[3] == 0
    # Red center stays opaque
    assert rgba.getpixel((4, 4))[3] == 255
