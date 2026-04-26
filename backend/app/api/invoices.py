from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.models.all_models import User, UserGroup, UserGroupMembership, PaymentOrder, InvoiceProfile, Invoice
from app.api.deps import get_current_user
from app.db.session import get_db
from app.schemas.invoice import InvoiceProfileCreate, InvoiceProfileRead, InvoiceRequest, InvoiceRead

router = APIRouter()

@router.get("/profiles", response_model=List[InvoiceProfileRead])
def get_invoice_profiles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Retrieve invoice profiles for the current user and their groups.
    """
    profiles = db.query(InvoiceProfile).filter(
        (InvoiceProfile.user_id == current_user.id) |
        (InvoiceProfile.group_id.in_([m.group_id for m in current_user.groups]))
    ).all()
    return profiles

@router.post("/profiles", response_model=InvoiceProfileRead)
def create_invoice_profile(
    *,
    db: Session = Depends(get_db),
    profile_in: InvoiceProfileCreate,
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Create new invoice profile.
    """
    if profile_in.group_id:
        membership = db.query(UserGroupMembership).filter_by(
            group_id=profile_in.group_id, user_id=current_user.id
        ).first()
        if not membership:
            raise HTTPException(status_code=403, detail="Not a member of the group")

    # If it's enterprise, require tax_number
    if profile_in.type == "ENTERPRISE" and not profile_in.tax_number:
        raise HTTPException(status_code=400, detail="Enterprise profile needs a tax number")

    profile = InvoiceProfile(**profile_in.dict(), user_id=current_user.id)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile

def async_request_wechat_invoice(db: Session, invoice_id: int):
    # Here we would normally communicate with Wechat API or a service provider
    # Since we don't have real implementation, let's simulate an issue
    pass

@router.post("/request", response_model=InvoiceRead)
def request_invoice(
    *,
    db: Session = Depends(get_db),
    req: InvoiceRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Request an invoice for a specific payment order.
    """
    # Check order
    order = db.query(PaymentOrder).filter_by(id=req.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Must be owned by user or user's group
    if order.user_id != current_user.id and (not order.target_group_id or order.target_group_id not in [m.group_id for m in current_user.groups]):
        raise HTTPException(status_code=403, detail="Not authorized to request invoice for this order")

    if order.status != "PAID":
        raise HTTPException(status_code=400, detail="Can only invoice paid orders")

    if order.invoice_status != "UNINVOICED" and order.invoice_status is not None:
        raise HTTPException(status_code=400, detail="Order already invoicing or invoiced")

    # Get profile
    profile = db.query(InvoiceProfile).filter_by(id=req.profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    invoice = Invoice(
        order_id=order.id,
        amount=order.amount,
        title=profile.title,
        tax_number=profile.tax_number,
        email=req.email or profile.email,
        status="PENDING"
    )
    db.add(invoice)
    
    # Mark order as requesting
    order.invoice_status = "REQUESTING"

    db.commit()
    db.refresh(invoice)

    background_tasks.add_task(async_request_wechat_invoice, db, invoice.id)
    return invoice
