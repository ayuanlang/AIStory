from pydantic import BaseModel
from typing import Optional

class SystemLogBase(BaseModel):
    action: str
    details: Optional[str] = None
    ip_address: Optional[str] = None

class SystemLogCreate(SystemLogBase):
    user_id: Optional[int] = None
    user_name: Optional[str] = None

class SystemLogOut(SystemLogBase):
    id: int
    user_id: Optional[int]
    user_name: Optional[str]
    timestamp: str

    class Config:
        from_attributes = True

class LLMCallLogOut(BaseModel):
    id: int
    tag: Optional[str]
    provider: Optional[str]
    model: Optional[str]
    api_url: Optional[str]
    payload_json: Optional[str]
    response_json: Optional[str]
    error_msg: Optional[str]
    latency_ms: Optional[int]
    timestamp: str

    class Config:
        from_attributes = True
