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

class RechargePlanOut(BaseModel):
    id: int
    min_amount: int
    max_amount: int
    credit_rate: int
    bonus: int

    class Config:
        from_attributes = True

class PaymentOrderOut(BaseModel):
    order_no: str
    amount: int
    credits: int
    status: str
    pay_url: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


class RechargeRequest(BaseModel):
    amount: int
    group_id: Optional[int] = None

class CreditUpdate(BaseModel):
    amount: int # Absolute value or delta? Let's say absolute set for admin simplicity, or add functionality
    mode: str = "set" # set, add

