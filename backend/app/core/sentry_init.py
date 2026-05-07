"""Optional Sentry instrumentation.

Activated only when ``SENTRY_DSN`` env is set. Safe no-op otherwise so
local / docker-compose dev runs don't ship telemetry.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def init_sentry() -> bool:
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    except ImportError:
        logger.warning("sentry-sdk not installed; SENTRY_DSN ignored")
        return False

    env = os.getenv("ENVIRONMENT", "development")
    sentry_sdk.init(
        dsn=dsn,
        environment=env,
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.0")),
        send_default_pii=False,
        integrations=[
            FastApiIntegration(),
            CeleryIntegration(),
            SqlalchemyIntegration(),
        ],
    )
    logger.info("Sentry initialised (env=%s)", env)
    return True
