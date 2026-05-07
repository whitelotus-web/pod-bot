"""Lightweight Redis cache decorator for hot read paths.

Hot calls (keyword scout, USPTO checks, Etsy bestseller pulls, AI prompt
template render) are good candidates: they're idempotent, slow, and OK
with stale data for a few minutes. Use sparingly — over-caching makes
debugging hard.

Usage::

    from app.core.cache import cached

    @cached(ttl=600, key_prefix="bestsellers")
    def fetch_bestsellers(category: str) -> list[str]:
        ...

The decorator transparently no-ops when Redis is unreachable (failure
mode for local pytest runs).
"""
from __future__ import annotations

import functools
import hashlib
import json
import logging
from collections.abc import Callable
from typing import Any, TypeVar

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")

_redis_client: redis.Redis | None = None


def _client() -> redis.Redis | None:
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = redis.from_url(
                settings.redis_url, socket_timeout=2, socket_connect_timeout=2
            )
            _redis_client.ping()
        except Exception:  # noqa: BLE001
            _redis_client = None
    return _redis_client


def _key_for(prefix: str, args: tuple, kwargs: dict[str, Any]) -> str:
    payload = json.dumps([args, sorted(kwargs.items())], default=str, sort_keys=True)
    digest = hashlib.sha1(payload.encode("utf-8"), usedforsecurity=False).hexdigest()
    return f"podbot:cache:{prefix}:{digest}"


def cached(*, ttl: int = 300, key_prefix: str) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorate a function so its return value is cached in Redis.

    ``ttl`` is in seconds. ``key_prefix`` should be a short stable name
    so cache hits group sensibly when reading via ``redis-cli``.
    """

    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            client = _client()
            if client is None:
                return fn(*args, **kwargs)
            key = _key_for(key_prefix, args, kwargs)
            try:
                hit = client.get(key)
                if hit is not None:
                    return json.loads(hit)
            except Exception:  # noqa: BLE001
                logger.debug("Cache read failed for %s", key, exc_info=True)
            value = fn(*args, **kwargs)
            try:
                client.setex(key, ttl, json.dumps(value, default=str))
            except Exception:  # noqa: BLE001
                logger.debug("Cache write failed for %s", key, exc_info=True)
            return value

        return wrapper

    return decorator


def invalidate_prefix(prefix: str) -> int:
    """Remove every cache entry whose key starts with ``podbot:cache:{prefix}:``.

    Returns the number of removed keys. Best-effort — no-op when Redis is
    unreachable.
    """
    client = _client()
    if client is None:
        return 0
    pattern = f"podbot:cache:{prefix}:*"
    removed = 0
    try:
        for key in client.scan_iter(pattern):
            client.delete(key)
            removed += 1
    except Exception:  # noqa: BLE001
        logger.debug("Cache invalidation failed for %s", pattern, exc_info=True)
    return removed
