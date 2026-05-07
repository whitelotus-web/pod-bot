"""GDPR-compliant data export + delete endpoints.

A user can:
* ``GET /gdpr/export`` — return a JSON dump of every row owned by them
  across all tables (campaigns, designs, products, ai_keys (masked),
  notifications, audit log entries…).
* ``POST /gdpr/delete`` — hard-delete every row tied to their user id.
  Cascades through the existing FK relations. The user row itself is
  removed last; their session token is invalidated implicitly because
  the user record no longer exists.

We intentionally mask AI keys in the export — the user already has them
in ``/settings/ai`` UI; no need to ship the plaintext to disk.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.crypto import mask
from app.models import (
    AIKey,
    AuditLog,
    Campaign,
    Design,
    Keyword,
    Mockup,
    Notification,
    PlatformAccount,
    PricingRule,
    Product,
    ProductReview,
    RunLog,
    TrademarkTerm,
    User,
)
from app.services.audit import log_action

router = APIRouter()


def _row_to_dict(row) -> dict:
    out: dict = {}
    for col in row.__table__.columns:
        val = getattr(row, col.name)
        out[col.name] = val.isoformat() if hasattr(val, "isoformat") else val
    return out


@router.get("/export")
def export_data(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> dict:
    """Return every row tied to the calling user as a single JSON bundle."""
    accounts = db.query(PlatformAccount).filter_by(user_id=user.id).all()
    account_ids = [a.id for a in accounts]
    campaigns = db.query(Campaign).filter_by(user_id=user.id).all()
    campaign_ids = [c.id for c in campaigns]
    keywords = (
        db.query(Keyword).filter(Keyword.campaign_id.in_(campaign_ids)).all()
        if campaign_ids
        else []
    )
    designs = (
        db.query(Design).filter(Design.campaign_id.in_(campaign_ids)).all()
        if campaign_ids
        else []
    )
    design_ids = [d.id for d in designs]
    products = (
        db.query(Product).filter(Product.platform_account_id.in_(account_ids)).all()
        if account_ids
        else []
    )
    mockups = (
        db.query(Mockup).filter(Mockup.design_id.in_(design_ids)).all() if design_ids else []
    )
    reviews = (
        db.query(ProductReview)
        .filter(ProductReview.product_id.in_([p.id for p in products]))
        .all()
        if products
        else []
    )
    ai_keys = db.query(AIKey).filter_by(user_id=user.id).all()
    runs = (
        db.query(RunLog).filter(RunLog.campaign_id.in_(campaign_ids)).all()
        if campaign_ids
        else []
    )
    notifications = db.query(Notification).filter_by(user_id=user.id).all()
    pricing_rules = db.query(PricingRule).filter_by(user_id=user.id).all()
    trademark_terms = db.query(TrademarkTerm).filter_by(user_id=user.id).all()
    audit = db.query(AuditLog).filter_by(user_id=user.id).all()

    log_action(db, user_id=user.id, action="gdpr.export", target_type="user", target_id=user.id)

    return {
        "exported_at": __import__("datetime").datetime.now(
            __import__("datetime").UTC
        ).isoformat(),
        "user": _row_to_dict(user)
        | {
            "hashed_password": "[REDACTED]",
            "totp_secret_encrypted": "[REDACTED]" if user.totp_secret_encrypted else None,
        },
        "platform_accounts": [
            _row_to_dict(a)
            | {
                "api_key": mask(a.api_key or ""),
                "access_token": mask(a.access_token or ""),
                "refresh_token": mask(a.refresh_token or ""),
                # proxy_url may embed credentials as https://user:pass@host —
                # mask wholesale rather than try to parse.
                "proxy_url": mask(a.proxy_url or "") if a.proxy_url else None,
            }
            for a in accounts
        ],
        "campaigns": [_row_to_dict(c) for c in campaigns],
        "keywords": [_row_to_dict(k) for k in keywords],
        "designs": [_row_to_dict(d) for d in designs],
        "products": [_row_to_dict(p) for p in products],
        "mockups": [_row_to_dict(m) for m in mockups],
        "reviews": [_row_to_dict(r) for r in reviews],
        "ai_keys": [
            _row_to_dict(k) | {"key_encrypted": "[REDACTED]"} for k in ai_keys
        ],
        "runs": [_row_to_dict(r) for r in runs],
        "notifications": [_row_to_dict(n) for n in notifications],
        "pricing_rules": [_row_to_dict(p) for p in pricing_rules],
        "trademark_terms": [_row_to_dict(t) for t in trademark_terms],
        "audit_log": [_row_to_dict(r) for r in audit],
    }


@router.post("/delete")
def delete_data(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> dict:
    """Hard-delete every row tied to this user. Irreversible.

    Order matters — children before parents to avoid FK violations even
    when ``ondelete="CASCADE"`` isn't set on every relation.
    """
    user_id = user.id
    log_action(
        db,
        user_id=user_id,
        action="gdpr.delete_requested",
        target_type="user",
        target_id=user_id,
    )

    accounts = db.query(PlatformAccount).filter_by(user_id=user_id).all()
    account_ids = [a.id for a in accounts]
    campaigns = db.query(Campaign).filter_by(user_id=user_id).all()
    campaign_ids = [c.id for c in campaigns]
    products = (
        db.query(Product)
        .filter(Product.platform_account_id.in_(account_ids) if account_ids else False)
        .all()
    )
    product_ids = [p.id for p in products]
    designs = (
        db.query(Design)
        .filter(Design.campaign_id.in_(campaign_ids) if campaign_ids else False)
        .all()
    )
    design_ids = [d.id for d in designs]

    # Children first.
    if product_ids:
        db.query(ProductReview).filter(
            ProductReview.product_id.in_(product_ids)
        ).delete(synchronize_session=False)
    if design_ids:
        db.query(Mockup).filter(Mockup.design_id.in_(design_ids)).delete(
            synchronize_session=False
        )
    if product_ids:
        db.query(Product).filter(Product.id.in_(product_ids)).delete(
            synchronize_session=False
        )
    if design_ids:
        db.query(Design).filter(Design.id.in_(design_ids)).delete(
            synchronize_session=False
        )
    if campaign_ids:
        db.query(Keyword).filter(Keyword.campaign_id.in_(campaign_ids)).delete(
            synchronize_session=False
        )
        db.query(RunLog).filter(RunLog.campaign_id.in_(campaign_ids)).delete(
            synchronize_session=False
        )
        db.query(Campaign).filter(Campaign.id.in_(campaign_ids)).delete(
            synchronize_session=False
        )
    db.query(PlatformAccount).filter_by(user_id=user_id).delete(synchronize_session=False)
    db.query(AIKey).filter_by(user_id=user_id).delete(synchronize_session=False)
    db.query(Notification).filter_by(user_id=user_id).delete(synchronize_session=False)
    db.query(PricingRule).filter_by(user_id=user_id).delete(synchronize_session=False)
    db.query(TrademarkTerm).filter_by(user_id=user_id).delete(synchronize_session=False)
    # Audit log entries for this user — keep the action row that recorded
    # the delete request, drop everything else.
    db.query(AuditLog).filter(
        AuditLog.user_id == user_id, AuditLog.action != "gdpr.delete_requested"
    ).delete(synchronize_session=False)
    db.query(User).filter_by(id=user_id).delete(synchronize_session=False)
    db.commit()
    return {"deleted": True, "user_id": user_id}
