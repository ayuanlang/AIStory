from typing import Optional, Any
from pydantic import BaseModel

class TransactionOut(BaseModel):
    id: int
    user_id: int
    amount: int
    balance_after: int
    description: Optional[str] = None
    task_type: Optional[str] = None
    provider: Optional[str] = None
    provider_alias: Optional[str] = None
    model: Optional[str] = None
    details: Optional[Any] = None
    project_id: Optional[int] = None
    episode_id: Optional[int] = None
    created_at: str
    reserved_cost: Optional[int] = None
    actual_cost: Optional[int] = None
    personal_balance_after: Optional[int] = None
    group_balance_after: Optional[int] = None

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
