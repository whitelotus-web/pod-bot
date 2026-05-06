"""Import all models here so Alembic sees them."""
from app.models.ai_key import AIKey
from app.models.audit_log import AuditLog
from app.models.campaign import Campaign
from app.models.design import Design
from app.models.keyword import Keyword, KeywordVolumeHistory
from app.models.mockup import Mockup
from app.models.notification import Notification
from app.models.platform_account import PlatformAccount
from app.models.pricing_rule import PricingRule
from app.models.product import Product
from app.models.review import ProductReview
from app.models.run_log import RunLog
from app.models.trademark_term import TrademarkTerm
from app.models.user import User

__all__ = [
    "User",
    "PlatformAccount",
    "Campaign",
    "Keyword",
    "KeywordVolumeHistory",
    "Design",
    "Mockup",
    "Product",
    "ProductReview",
    "RunLog",
    "AIKey",
    "TrademarkTerm",
    "Notification",
    "PricingRule",
    "AuditLog",
]
__all_models__ = list(__all__)
