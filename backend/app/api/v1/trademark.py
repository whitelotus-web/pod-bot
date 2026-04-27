"""Trademark blacklist — user-managed terms + on-demand check."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import TrademarkTerm, User
from app.services.trademark import check_phrase, filter_keywords

router = APIRouter()


class CheckRequest(BaseModel):
    text: str
    enable_uspto: bool = False


@router.post("/check")
def check(
    payload: CheckRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    user_terms = [
        t.term for t in db.query(TrademarkTerm).filter(TrademarkTerm.user_id == user.id).all()
    ]
    res = check_phrase(
        payload.text,
        user_blacklist=user_terms,
        enable_uspto=payload.enable_uspto,
    )
    return {
        "safe": res.safe,
        "reason": res.reason,
        "matched_phrase": res.matched_phrase,
        "source": res.source,
    }


class FilterRequest(BaseModel):
    keywords: list[str]
    enable_uspto: bool = False


@router.post("/filter")
def filter_kws(
    payload: FilterRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    user_terms = [
        t.term for t in db.query(TrademarkTerm).filter(TrademarkTerm.user_id == user.id).all()
    ]
    safe, rejected = filter_keywords(
        payload.keywords,
        user_blacklist=user_terms,
        enable_uspto=payload.enable_uspto,
    )
    return {
        "safe": safe,
        "rejected": [{"keyword": k, "reason": r} for k, r in rejected],
    }


# ─── User-managed term CRUD ───


class TermIn(BaseModel):
    term: str
    note: str | None = None


@router.get("/terms")
def list_terms(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    rows = (
        db.query(TrademarkTerm)
        .filter(TrademarkTerm.user_id == user.id)
        .order_by(TrademarkTerm.created_at.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "term": r.term,
            "source": r.source,
            "note": r.note,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.post("/terms")
def add_term(
    payload: TermIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    term = payload.term.strip()
    if not term or len(term) > 255:
        raise HTTPException(400, "term không hợp lệ")
    row = TrademarkTerm(user_id=user.id, term=term, note=payload.note, source="user")
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"id": row.id, "term": row.term, "source": row.source}


@router.delete("/terms/{term_id}")
def delete_term(
    term_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    row = db.get(TrademarkTerm, term_id)
    if not row or row.user_id != user.id:
        raise HTTPException(404, "Không tìm thấy")
    db.delete(row)
    db.commit()
    return {"ok": True}
