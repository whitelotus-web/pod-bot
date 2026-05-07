"""FastAPI entrypoint."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.types import ASGIApp

from app.api.v1 import api_router
from app.core.config import settings
from app.core.db import SessionLocal
from app.core.rate_limit import limiter
from app.core.security import hash_password
from app.core.sentry_init import init_sentry
from app.models import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialise Sentry as early as possible so init failures still surface.
_sentry_active = init_sentry()

app = FastAPI(title=settings.app_name, version="0.2.0")


class AttachUserMiddleware(BaseHTTPMiddleware):
    """Best-effort decode of the bearer token so rate-limit keys can be per-user.

    Implemented as a proper ``BaseHTTPMiddleware`` subclass (rather than the
    ``@app.middleware('http')`` decorator) so it can be registered via
    ``app.add_middleware()`` AFTER ``SlowAPIMiddleware``. In Starlette the
    last-added middleware ends up the outermost layer, so this ordering
    guarantees ``request.state.user`` is set BEFORE SlowAPI reads the
    rate-limit key. Failures here are swallowed so unauthenticated endpoints
    (login, healthcheck) still work — they fall back to IP-based limiting.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        try:
            from app.api.deps import get_user_from_token

            auth = request.headers.get("authorization") or ""
            if auth.lower().startswith("bearer "):
                token = auth.split(" ", 1)[1].strip()
                db = SessionLocal()
                try:
                    user = get_user_from_token(token, db)
                    if user is not None:
                        request.state.user = user
                finally:
                    db.close()
        except Exception:  # noqa: BLE001
            pass
        return await call_next(request)


# Rate limiter — must be installed before any router that uses ``@limiter``.
# Order matters: ``add_middleware`` prepends, so the last-added wraps the
# previously-added ones. We need ``AttachUserMiddleware`` to run BEFORE
# ``SlowAPIMiddleware`` so ``request.state.user`` is populated when slowapi
# computes its key. Therefore SlowAPI is added first, then CORS, then
# AttachUser — making AttachUser the outermost layer.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AttachUserMiddleware)

app.include_router(api_router)

Path(settings.media_root).mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.media_root), name="media")


# --- Health endpoints --------------------------------------------------------
# `/health` is the legacy quick-check kept for backwards compat. New
# operational tooling (Kubernetes, uptime monitors, load balancers) should
# point at `/health/live` and `/health/ready`.


@app.get("/health")
def health() -> dict:
    return {"ok": True, "app": settings.app_name, "sentry": _sentry_active}


@app.get("/health/live")
def health_live() -> dict:
    """Liveness probe: returns 200 as long as the process is up.

    No external dependencies — used by orchestrators to decide whether
    to restart the container.
    """
    return {"status": "live", "app": settings.app_name}


@app.get("/health/ready")
def health_ready() -> JSONResponse:
    """Readiness probe: 200 only if DB + Redis are reachable.

    Used by orchestrators to decide whether to send traffic. Failure
    here means the container is up but can't serve real requests.
    """
    checks: dict[str, str] = {}
    ok = True
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            checks["database"] = "ok"
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001
        checks["database"] = f"fail: {exc!s}"
        ok = False

    try:
        import redis as _redis

        client = _redis.from_url(settings.redis_url, socket_timeout=2)
        client.ping()
        checks["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = f"fail: {exc!s}"
        ok = False

    return JSONResponse(
        {"status": "ready" if ok else "degraded", "checks": checks},
        status_code=200 if ok else 503,
    )


# --- Bootstrap admin --------------------------------------------------------
@app.on_event("startup")
def seed_admin() -> None:
    db = SessionLocal()
    try:
        if not db.query(User).filter_by(email=settings.admin_email).first():
            u = User(
                email=settings.admin_email,
                hashed_password=hash_password(settings.admin_password),
                full_name="Administrator",
                is_active=True,
                is_superuser=True,
            )
            db.add(u)
            db.commit()
            logger.info("Seeded default admin %s", settings.admin_email)
    finally:
        db.close()
