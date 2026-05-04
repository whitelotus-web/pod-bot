from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import Campaign, Keyword, User
from app.schemas.keyword import KeywordRead
from app.services.buyer_intent import apply_intent_to_terms, classify
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
    classify_intent: bool = True,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    agg = KeywordAggregator(source_names=sources)
    terms = agg.run(seed, top=top)
    if classify_intent:
        terms = apply_intent_to_terms(terms, db=db, user_id=user.id, use_ai=False)
    return [
        {
            "term": t.term,
            "source": t.source,
            "score": round(t.score, 1),
            "intent": (t.raw or {}).get("intent"),
            "intent_score": (t.raw or {}).get("intent_score"),
            "raw": t.raw,
        }
        for t in terms
    ]


@router.post("/classify-intent")
def classify_intent(
    phrase: str,
    use_ai: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """Classify a single phrase's buyer intent.

    ``use_ai=True`` calls the user's LLM keys when the heuristic confidence
    is low (<0.5). ``use_ai=False`` runs only the heuristic — fast + free.
    """
    res = classify(
        phrase, db=db, user_id=user.id, use_ai_when_unsure=use_ai
    )
    return {
        "phrase": phrase,
        "intent": res.intent,
        "confidence": round(res.confidence, 3),
        "boost_factor": round(res.boost_factor(), 3),
    }


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
