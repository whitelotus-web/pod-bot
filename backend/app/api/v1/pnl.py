"""P&L dashboard API.

Returns a single bundle with the four summary views the frontend renders:
KPI hero, by-day timeseries, by-campaign / by-product-type breakdown,
and top-N winners + losers.

Querying multiple buckets in a single endpoint avoids N round-trips from
the dashboard and keeps every aggregation pinned to the same point-in-time
(no sub-second skew between cards).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.services import pnl as pnl_service

router = APIRouter()


@router.get("/summary")
def summary(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    return pnl_service.summary(db, user.id, days=days)


@router.get("/by-day")
def by_day(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    return [b.to_dict() for b in pnl_service.by_day(db, user.id, days=days)]


@router.get("/by-campaign")
def by_campaign(
    days: int = Query(90, ge=1, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    return [b.to_dict() for b in pnl_service.by_campaign(db, user.id, days=days)]


@router.get("/by-product-type")
def by_product_type(
    days: int = Query(90, ge=1, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    return [b.to_dict() for b in pnl_service.by_product_type(db, user.id, days=days)]


@router.get("/top-winners")
def top_winners(
    days: int = Query(90, ge=1, le=365),
    n: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    return pnl_service.top_winners(db, user.id, days=days, n=n)


@router.get("/top-losers")
def top_losers(
    days: int = Query(90, ge=1, le=365),
    n: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    return pnl_service.top_losers(db, user.id, days=days, n=n)


@router.get("/dashboard")
def dashboard(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """One-shot bundle for the /pnl frontend page."""
    return {
        "summary": pnl_service.summary(db, user.id, days=days),
        "by_day": [b.to_dict() for b in pnl_service.by_day(db, user.id, days=days)],
        "by_campaign": [
            b.to_dict() for b in pnl_service.by_campaign(db, user.id, days=days)
        ],
        "by_product_type": [
            b.to_dict() for b in pnl_service.by_product_type(db, user.id, days=days)
        ],
        "top_winners": pnl_service.top_winners(db, user.id, days=days, n=10),
        "top_losers": pnl_service.top_losers(db, user.id, days=days, n=10),
    }
