"""Momentum trend endpoint — returns SMA/RSI/score for a keyword."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import Keyword, User
from app.models.keyword import KeywordVolumeHistory
from app.services.momentum import compute, is_recent_breakout

router = APIRouter()


@router.get("/keywords/{keyword_id}")
def for_keyword(
    keyword_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    kw = db.get(Keyword, keyword_id)
    if not kw:
        raise HTTPException(404, "Keyword không tồn tại")
    history = (
        db.query(KeywordVolumeHistory)
        .filter(KeywordVolumeHistory.keyword_id == keyword_id)
        .order_by(KeywordVolumeHistory.date.asc())
        .all()
    )
    samples = [(h.date, float(h.volume)) for h in history]
    snap = compute(samples)
    return {
        "keyword_id": keyword_id,
        "term": kw.term,
        "samples": len(samples),
        "sma_7": snap.sma_7,
        "sma_30": snap.sma_30,
        "rsi_14": snap.rsi_14,
        "momentum_score": snap.momentum_score,
        "label": snap.label,
        "breakout_at": snap.breakout_at.isoformat() if snap.breakout_at else None,
        "recent_breakout": is_recent_breakout(snap),
    }


class IngestRequest(__import__("pydantic").BaseModel):
    keyword_id: int
    date: date
    volume: float
    source: str = "manual"


@router.post("/ingest")
def ingest_volume(
    payload: IngestRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    kw = db.get(Keyword, payload.keyword_id)
    if not kw:
        raise HTTPException(404, "Keyword không tồn tại")
    row = KeywordVolumeHistory(
        keyword_id=payload.keyword_id,
        date=payload.date,
        volume=payload.volume,
        source=payload.source,
    )
    db.add(row)
    db.commit()

    # Recompute snapshot.
    history = (
        db.query(KeywordVolumeHistory)
        .filter(
            KeywordVolumeHistory.keyword_id == payload.keyword_id,
            KeywordVolumeHistory.date >= date.today() - timedelta(days=120),
        )
        .order_by(KeywordVolumeHistory.date.asc())
        .all()
    )
    snap = compute([(h.date, float(h.volume)) for h in history])
    kw.sma_7 = snap.sma_7
    kw.sma_30 = snap.sma_30
    kw.rsi_14 = snap.rsi_14
    kw.momentum_score = snap.momentum_score
    kw.breakout_at = snap.breakout_at
    db.commit()

    return {"ok": True, "samples": len(history), "label": snap.label}
