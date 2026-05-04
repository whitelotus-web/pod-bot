"""Account health & warmup status — read-only dashboard endpoint."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import PlatformAccount, User
from app.services.warmup import account_age_days, daily_cap, tier_for_age

router = APIRouter()


@router.get("/accounts")
def accounts_health(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    rows = (
        db.query(PlatformAccount)
        .filter(PlatformAccount.user_id == user.id)
        .order_by(PlatformAccount.id.asc())
        .all()
    )
    out = []
    for r in rows:
        age = account_age_days(r.created_at, r.account_age_days_override)
        tier = tier_for_age(age)
        cap = daily_cap(
            created_at=r.created_at,
            override_days=r.account_age_days_override,
            user_override_cap=r.daily_publish_cap_override,
        )
        out.append(
            {
                "id": r.id,
                "platform": r.platform,
                "label": r.label,
                "shop_id": r.shop_id,
                "is_active": r.is_active,
                "health_status": r.health_status,
                "health_note": r.health_note,
                "paused_until": r.paused_until.isoformat() if r.paused_until else None,
                "age_days": age,
                "tier": tier.name,
                "daily_cap": cap,
                "today_publish_count": r.today_publish_count or 0,
                "today_remaining": max(0, cap - (r.today_publish_count or 0)),
                "last_publish_at": r.last_publish_at.isoformat() if r.last_publish_at else None,
                "proxy_configured": bool(r.proxy_url),
                "now": datetime.now(UTC).isoformat(),
            }
        )
    return out
