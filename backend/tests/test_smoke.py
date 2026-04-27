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


def test_platform_meta_covers_all():
    from app.services.platforms import PLATFORM_META

    assert set(PLATFORM_META.keys()) >= {
        "printify",
        "printful",
        "etsy",
        "redbubble",
        "teespring",
        "merch_amazon",
    }


def test_celery_tasks_registered():
    from app.workers import pipeline, scheduler  # noqa: F401
    from app.workers.celery_app import celery_app

    assert "app.workers.pipeline.run_campaign" in celery_app.tasks
    assert "app.workers.scheduler.tick" in celery_app.tasks
