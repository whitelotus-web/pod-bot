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

    # Only the 3 API-backed platforms are supported; Selenium-only platforms
    # (Redbubble / Teespring / Merch by Amazon) are intentionally excluded.
    assert set(PLATFORM_META.keys()) == {"printify", "printful", "etsy"}
    for meta in PLATFORM_META.values():
        assert meta["supported"] is True


def test_platform_factory_rejects_legacy():
    import pytest

    from app.services.platforms import get_platform

    for legacy in ("redbubble", "teespring", "merch_amazon"):
        with pytest.raises(ValueError, match="Unknown platform"):
            get_platform(legacy, account=None)


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
