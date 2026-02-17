from typing import Optional, List, Any
from pydantic import BaseModel
from datetime import datetime

class PricingRuleBase(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None
    task_type: str
    cost: int
    cost_input: Optional[int] = 0
    cost_output: Optional[int] = 0
    
    # UI References
    ref_cost_cny: Optional[float] = None
    ref_cost_input_cny: Optional[float] = None
    ref_cost_output_cny: Optional[float] = None
    ref_markup: Optional[float] = 1.5
    ref_exchange_rate: Optional[float] = 10.0

    unit_type: str = "per_call"
    description: Optional[str] = None
    is_active: bool = True


class PricingRuleCreate(PricingRuleBase):
    pass

class PricingRuleUpdate(PricingRuleBase):
    task_type: Optional[str] = None
    cost: Optional[int] = None
    cost_input: Optional[int] = None
    cost_output: Optional[int] = None
    unit_type: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class PricingRuleOut(PricingRuleBase):
    id: int
    
    class Config:
        from_attributes = True

class TransactionOut(BaseModel):
    id: int
    user_id: int
    amount: int
    balance_after: int
    task_type: Optional[str] = None
    provider: Optional[str] = None
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
