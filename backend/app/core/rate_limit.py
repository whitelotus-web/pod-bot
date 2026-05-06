"""Per-user rate limiter built on slowapi.

Falls back to client IP when the request is unauthenticated. Each
endpoint can layer its own limit on top via ``@limiter.limit(...)``.
The default global limit (200/min) catches the obvious abuse case
without throttling normal browser usage.

Endpoints that hit upstream paid APIs (AI generation, Etsy publish,
USPTO lookups) declare tighter per-route limits in their routers.
"""
from __future__ import annotations

import logging
import os

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

logger = logging.getLogger(__name__)


def _key(request: Request) -> str:
    user = getattr(request.state, "user", None)
    if user is not None and getattr(user, "id", None) is not None:
        return f"user:{user.id}"
    return f"ip:{get_remote_address(request)}"


_storage_uri = os.getenv("RATE_LIMIT_REDIS_URL") or os.getenv("REDIS_URL", "memory://")
# slowapi expects a redis:// URL or "memory://".
if _storage_uri and not _storage_uri.startswith(("redis://", "memory://")):
    _storage_uri = "memory://"

limiter = Limiter(
    key_func=_key,
    default_limits=["200/minute", "5000/hour"],
    storage_uri=_storage_uri,
    headers_enabled=True,
)
