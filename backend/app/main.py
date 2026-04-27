"""FastAPI entrypoint."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1 import api_router
from app.core.config import settings
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models import User

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

Path(settings.media_root).mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=settings.media_root), name="media")


@app.get("/health")
def health() -> dict:
    return {"ok": True, "app": settings.app_name}


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
