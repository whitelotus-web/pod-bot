from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import Campaign, Keyword, User
from app.schemas.keyword import KeywordRead
from app.services.keywords import KeywordAggregator
from app.services.keywords.aggregator import ALL_SOURCES

router = APIRouter()


@router.get("/sources")
def list_sources() -> list[str]:
    return ALL_SOURCES


@router.post("/preview")
def preview(
    seed: str,
    sources: list[str] | None = None,
    top: int = 30,
    user: User = Depends(get_current_user),  # noqa: ARG001
) -> list[dict]:
    agg = KeywordAggregator(source_names=sources)
    terms = agg.run(seed, top=top)
    return [
        {"term": t.term, "source": t.source, "score": round(t.score, 1), "raw": t.raw}
        for t in terms
    ]


@router.get("/{campaign_id}", response_model=list[KeywordRead])
def list_for_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[KeywordRead]:
    # Access check
    db.query(Campaign).filter_by(id=campaign_id, user_id=user.id).first()
    rows = (
        db.query(Keyword)
        .filter_by(campaign_id=campaign_id)
        .order_by(Keyword.rank.asc())
        .limit(200)
        .all()
    )
    return [KeywordRead.model_validate(r) for r in rows]
