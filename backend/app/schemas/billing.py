from typing import Optional, Any
from pydantic import BaseModel

class TransactionOut(BaseModel):
    id: int
    user_id: int
    amount: int
    balance_after: int
    task_type: Optional[str] = None
    provider: Optional[str] = None
    provider_alias: Optional[str] = None
    model: Optional[str] = None
    details: Optional[Any] = None
    created_at: str
    
    class Config:
        from_attributes = True

class CreditCheck(BaseModel):
    can_proceed: bool
    cost: int
    current_balance: int
    message: Optional[str] = None


class FeaturePricingUpdate(BaseModel):
    feature_pricing: dict[str, int] = {}


class FeaturePricingOut(BaseModel):
    feature_pricing: dict[str, int] = {}


class DefaultApiPricingUpdate(BaseModel):
    default_api_pricing: dict[str, dict[str, Any]] = {}
    content_fallback_pricing: Optional[dict[str, Any]] = None


class DefaultApiPricingOut(BaseModel):
    default_api_pricing: dict[str, dict[str, Any]] = {}
    recommended_default_api_pricing: dict[str, dict[str, Any]] = {}
    content_fallback_pricing: dict[str, Any] = {}
