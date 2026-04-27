from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import PlatformAccount, Product, User
from app.schemas.product import ProductRead

router = APIRouter()


@router.get("", response_model=list[ProductRead])
def list_products(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ProductRead]:
    rows = (
        db.query(Product)
        .join(PlatformAccount, Product.platform_account_id == PlatformAccount.id)
        .filter(PlatformAccount.user_id == user.id)
        .order_by(Product.id.desc())
        .limit(500)
        .all()
    )
    return [ProductRead.model_validate(r) for r in rows]
