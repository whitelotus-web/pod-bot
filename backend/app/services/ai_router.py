"""Role-aware AI key router with quota auto-failover.

Use `with_failover()` to wrap any AI call so that 429/quota errors transparently
rotate to the next key (same engine first, then sibling engines for the role).

Key picker order (per role, per user):
  1. is_active=True
  2. ORDER BY priority ASC, quota_failures ASC, id ASC
  3. Falls back to env-var key if no DB rows.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TypeVar

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import decrypt
from app.models import AIKey

logger = logging.getLogger(__name__)

T = TypeVar("T")


# Engines allowed per role. UI / validation should respect this map.
ROLE_ENGINES: dict[str, list[str]] = {
    "image_generation": ["gemini", "openai", "replicate"],
    "seo_writer": ["gemini", "openai"],
    "keyword_expansion": ["gemini", "openai"],
}


@dataclass
class AIKeyCandidate:
    row: AIKey | None  # None = env-var fallback
    engine: str
    api_key: str | None  # None means "use whatever the engine reads from settings"

    @property
    def label(self) -> str:
        if self.row is None:
            return f"env:{self.engine}"
        return f"#{self.row.id} {self.engine} (prio={self.row.priority})"


def _env_key(engine: str) -> str | None:
    if engine == "gemini":
        return settings.gemini_api_key or None
    if engine == "openai":
        return settings.openai_api_key or None
    if engine == "replicate":
        return settings.replicate_api_token or None
    return None


def list_keys(
    db: Session,
    *,
    user_id: int,
    role: str,
    engine: str | None = None,
    exclude_engine: str | None = None,
) -> list[AIKeyCandidate]:
    """Return ordered list of candidate keys to try for (role, engine)."""
    q = (
        db.query(AIKey)
        .filter_by(user_id=user_id, role=role, is_active=True)
        .order_by(AIKey.priority.asc(), AIKey.quota_failures.asc(), AIKey.id.asc())
    )
    if engine:
        q = q.filter(AIKey.engine == engine)
    if exclude_engine:
        q = q.filter(AIKey.engine != exclude_engine)
    rows = q.all()
    out: list[AIKeyCandidate] = []
    for r in rows:
        try:
            out.append(AIKeyCandidate(row=r, engine=r.engine, api_key=decrypt(r.encrypted_key)))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skip key #%s (decrypt failed): %s", r.id, exc)

    # Append env-var keys at the END for every allowed engine, so they act
    # as a last-resort safety net even after the user's own DB keys for the
    # same engine have been exhausted (previously the env fallback was only
    # added when the user had zero DB keys for the engine, which meant
    # admin-configured env keys were unreachable as soon as a user added a
    # single DB key).
    for eng in ROLE_ENGINES.get(role, []):
        if engine and eng != engine:
            continue
        if exclude_engine and eng == exclude_engine:
            continue
        env = _env_key(eng)
        if env:
            out.append(AIKeyCandidate(row=None, engine=eng, api_key=env))
    return out


class AISoftError(Exception):
    """Retriable AI-call failure that is NOT a quota error.

    Raise this from a `with_failover` callback when the engine returned
    unusable output (e.g. unparseable JSON, malformed schema) but the key
    itself is still healthy. `with_failover` will rotate to the next
    candidate the same way it does for quota errors, so a transient model
    glitch on one engine doesn't kill the whole pipeline.
    """


def is_quota_error(exc: BaseException) -> bool:
    """Heuristic detector for quota / rate-limit errors across providers."""
    msg = str(exc).lower()
    triggers = (
        "quota",
        "quota_exceeded",
        "rate limit",
        "rate_limit",
        "ratelimit",
        "429",
        "insufficient_quota",
        "billing",
        "resource_exhausted",
    )
    return any(t in msg for t in triggers)


def _is_retriable(exc: BaseException) -> bool:
    return isinstance(exc, AISoftError) or is_quota_error(exc)


def _bump_failure(db: Session, candidate: AIKeyCandidate) -> None:
    if candidate.row is None:
        return
    candidate.row.quota_failures = (candidate.row.quota_failures or 0) + 1
    candidate.row.last_used_at = datetime.now(UTC)
    db.commit()


def _bump_success(db: Session, candidate: AIKeyCandidate) -> None:
    if candidate.row is None:
        return
    candidate.row.last_used_at = datetime.now(UTC)
    db.commit()


def with_failover(
    db: Session,
    *,
    user_id: int,
    role: str,
    engine: str | None,
    fn: Callable[[AIKeyCandidate], T],
    exclude_engine: str | None = None,
) -> T:
    """Run `fn(candidate)` against each candidate until one succeeds.

    `fn` must raise on quota/429; we rotate to the next key. Other exceptions
    propagate immediately (we don't burn keys for unrelated bugs).
    """
    candidates = list_keys(
        db, user_id=user_id, role=role, engine=engine, exclude_engine=exclude_engine
    )
    if not candidates:
        raise RuntimeError(
            f"Không có AI key nào active cho role={role!r} engine={engine!r}. "
            f"Vào /settings/ai để thêm."
        )

    last_exc: BaseException | None = None
    for cand in candidates:
        try:
            result = fn(cand)
        except Exception as exc:  # noqa: BLE001
            if _is_retriable(exc):
                # Only bump quota_failures for genuine quota errors so a
                # transient parse/soft error doesn't penalize the key.
                if is_quota_error(exc):
                    logger.warning("Key %s hit quota — failing over: %s", cand.label, exc)
                    _bump_failure(db, cand)
                else:
                    logger.warning(
                        "Key %s soft-failed (%s) — failing over to next candidate.",
                        cand.label,
                        exc,
                    )
                last_exc = exc
                continue
            raise
        else:
            _bump_success(db, cand)
            return result

    raise RuntimeError(
        "Đã hết tất cả AI key cho role này (tất cả đều dính quota / 429). "
        f"Lỗi cuối: {last_exc}"
    )


def expand_keywords_with_failover(
    db: Session, *, user_id: int, niche: str, count: int = 10
) -> list[str]:
    """Convenience: ask the AI for long-tail keyword variations from a seed niche."""
    import json
    import re

    def _call(cand: AIKeyCandidate) -> list[str]:
        if cand.engine == "gemini":
            from google import genai

            client = genai.Client(api_key=cand.api_key)
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=(
                    f"Suggest {count} long-tail Etsy search keywords for the niche "
                    f"'{niche}'. Each ≤6 words, lowercase, no special chars. "
                    "Output JSON array of strings only, no code fences."
                ),
            )
            text = re.sub(r"^```json\s*|\s*```$", "", (resp.text or "").strip())
            arr = json.loads(text)
            return [str(t).strip() for t in arr if str(t).strip()][:count]
        if cand.engine == "openai":
            from openai import OpenAI

            client = OpenAI(api_key=cand.api_key)
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Suggest {count} long-tail Etsy search keywords for niche "
                            f"'{niche}'. Output JSON array of strings only."
                        ),
                    }
                ],
            )
            txt = re.sub(r"^```json\s*|\s*```$", "", (resp.choices[0].message.content or "").strip())
            arr = json.loads(txt)
            return [str(t).strip() for t in arr if str(t).strip()][:count]
        raise ValueError(f"keyword_expansion not supported by engine {cand.engine}")

    return with_failover(db, user_id=user_id, role="keyword_expansion", engine=None, fn=_call)


def safe_generate_image(
    db: Session,
    *,
    user_id: int,
    engine_pref: str,
    prompt: str,
    model: str | None = None,
    size: str = "1024x1024",
):
    """Use role=image_generation key with failover to other engines."""
    from app.services.ai import get_engine

    def _call(cand: AIKeyCandidate):
        eng = get_engine(cand.engine, api_key=cand.api_key)
        # ``model`` names are engine-specific (e.g. ``gemini-2.5-flash`` only
        # makes sense for Gemini). When failover rotates to a sibling engine,
        # drop the caller's model so the engine adapter picks its own default
        # — otherwise we hand a Gemini model id to OpenAI and get a hard
        # failure that ``with_failover`` doesn't retry.
        effective_model = model if cand.engine == engine_pref else None
        try:
            return eng.generate(prompt, model=effective_model, size=size)
        except Exception as exc:  # noqa: BLE001
            # Translate provider model-rejection / validation errors into
            # AISoftError so failover can keep going. Keep quota errors as-is.
            if is_quota_error(exc):
                raise
            msg = str(exc).lower()
            if "model" in msg and ("not found" in msg or "invalid" in msg or "unknown" in msg):
                raise AISoftError(f"{cand.engine} rejected model {effective_model!r}: {exc}") from exc
            raise

    # Try preferred engine first; if all preferred-engine keys exhausted, fall through
    # to sibling engines for the role. We pass exclude_engine=engine_pref on the second
    # call so already-tried preferred-engine keys don't get re-counted in quota_failures.
    try:
        return with_failover(db, user_id=user_id, role="image_generation", engine=engine_pref, fn=_call)
    except RuntimeError as exc:
        if "Đã hết tất cả AI key" not in str(exc) and "Không có AI key" not in str(exc):
            raise
        logger.info("Engine %s exhausted — fallback to sibling image engines.", engine_pref)
        return with_failover(
            db,
            user_id=user_id,
            role="image_generation",
            engine=None,
            exclude_engine=engine_pref,
            fn=_call,
        )


def role_engines(role: str) -> Iterable[str]:
    return ROLE_ENGINES.get(role, [])
