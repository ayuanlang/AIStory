from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

class InvoiceProfileBase(BaseModel):
    type: str # 'ENTERPRISE' or 'PERSONAL'
    title: str
    tax_number: Optional[str] = None
    email: Optional[EmailStr] = None
    group_id: Optional[int] = None

class InvoiceProfileCreate(InvoiceProfileBase):
    pass

class InvoiceProfileRead(InvoiceProfileBase):
    id: int
    user_id: Optional[int]
    created_at: str

    class Config:
        from_attributes = True


class InvoiceRequest(BaseModel):
    order_id: int
    profile_id: int
    email: Optional[EmailStr] = None


class InvoiceRead(BaseModel):
    id: int
    order_id: int
    amount: int
    title: str
    tax_number: Optional[str]
    email: Optional[str]
    status: str
    wechat_invoice_id: Optional[str]
    pdf_url: Optional[str]
    created_at: str

    class Config:
        from_attributes = True

class InvoiceHistoryResponse(BaseModel):
    invoices: List[InvoiceRead]
    total: int
