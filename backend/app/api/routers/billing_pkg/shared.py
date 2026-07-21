# -*- coding: utf-8 -*-
"""Billing / recharge / credits admin routes (P3)."""
from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.time_utils import now_bj_iso
from app.db.session import get_db
from app.models.all_models import (
    PaymentOrder,
    RechargePlan,
    TransactionHistory,
    User,
    WechatPayConfig,
)
from app.schemas.billing import (
    CreditUpdate,
    DefaultApiPricingOut,
    DefaultApiPricingUpdate,
    FeaturePricingOut,
    FeaturePricingUpdate,
    PaymentOrderOut,
    RechargePlanOut,
    RechargeRequest,
    TransactionOut,
)
from app.services.billing_service import billing_service
from app.services.payment_service import payment_service
from app.services.wechat_pay_config import _get_active_wechat_config, _wechat_config_to_dict

logger = logging.getLogger("api_logger")
router = APIRouter(tags=["billing"])


from app.services.db_session_utils import _release_db_connection  # noqa: E402,F401
from app.services.provider_alias import (  # noqa: E402,F401
    _attach_provider_alias_deep,
    _build_provider_alias_lookup,
    _resolve_provider_alias,
)

# Route bodies (schemas inlined originally — re-declare thin aliases if referenced as local classes)
# Prefer schema imports; body below may still say RechargeRequest which resolves via import.

@router.get("/billing/recharge/plans", response_model=List[RechargePlanOut])
def get_recharge_plans(db: Session = Depends(get_db)):
    return db.query(RechargePlan).filter(RechargePlan.is_active == True).all()

@router.post("/billing/recharge/create", response_model=PaymentOrderOut)
def create_recharge_order(
    req: RechargeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if req.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")

    setting = _get_active_wechat_config(db)
    if setting:
        cfg = _wechat_config_to_dict(setting)
        logger.info("Loading WeChat config from dedicated table: use_mock=%s", cfg.get("use_mock"))
        payment_service.update_config(cfg)
    else:
        logger.warning("No active WeChat config found in dedicated table. Use mock mode.")
        payment_service.update_config({"use_mock": True})

    # Find applicable plan
    plan = db.query(RechargePlan).filter(
        RechargePlan.min_amount <= req.amount,
        RechargePlan.max_amount >= req.amount,
        RechargePlan.is_active == True
    ).first()
    
    if not plan:
        # Fallback to default (100) if no matching range found? Or error?
        # User requirement implies continuous ranges. 
        # If amount < 1, reject. If > max, check highest. 
        # Let's use a safe default of 100 if inside hole, but ideally there are no holes.
        credit_rate = 100
        bonus = 0
    else:
        credit_rate = plan.credit_rate
        bonus = plan.bonus
        
    total_credits = (req.amount * credit_rate) + bonus
    
    # Generate Order No
    order_no = f"ORD_{uuid.uuid4().hex[:16]}"
    
    # Try Real WeChat Pay
    description = f"Recharge {req.amount} CNY"
    pay_url = payment_service.create_native_order(order_no, req.amount, description)
    
    if not pay_url:
        logger.warning(f"Real WeChat Pay failed for {order_no}. Falling back to mock.")
        # Mock Pay URL (Simulate a WeChat URL)
        # Reverting to the format that looks like a real URL, even if it might fail scanning if not registered with WeChat,
        # as user requested "actual WeChat address" format.
        # But for it to actually WORK, the payment_service MUST be configured correctly.
        pay_url = f"weixin://wxpay/bizpayurl?pr={order_no}"
    
    order = PaymentOrder(
        order_no=order_no,
        user_id=current_user.id,
        amount=req.amount,
        credits=total_credits,
        status="PENDING",
        pay_url=pay_url,
        provider="wechat",
        created_at=now_bj_iso(),
        target_group_id=req.group_id
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    
    return order

@router.get("/billing/recharge/status/{order_no}")
def check_order_status(
    order_no: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    order = db.query(PaymentOrder).filter(PaymentOrder.order_no == order_no).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
        
    if order.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    # Active Query if PENDING (For Real Flow)
    if order.status == "PENDING":
        wx_status = payment_service.query_order(order_no)
        if wx_status == "SUCCESS":
            logger.info(f"Order {order_no} confirmed SUCCESS via Active Query")
            # Update to PAID
            order.status = "PAID"
            order.paid_at = now_bj_iso()
            
            # Add Credits & Transaction
            from app.models.all_models import UserGroup
            if order.target_group_id:
                target_group = db.query(UserGroup).filter(UserGroup.id == order.target_group_id).first()
                if target_group:
                    old_credits = target_group.credits or 0
                    target_group.credits = old_credits + order.credits
                    trans = TransactionHistory(
                        user_id=order.user_id,
                        target_group_id=order.target_group_id,
                        amount=order.credits,
                        balance_after=target_group.credits,
                        description="Group Recharge (Active Query)",
                        details={
                            "task_type": "group_recharge",
                            "provider": "wechat",
                            "model": "cny",
                            "order_no": order_no, 
                            "amount_cny": order.amount, 
                            "method": "active_query"
                        }
                    )
                    db.add(trans)
            else:
                user = db.query(User).filter(User.id == order.user_id).first()
                if user:
                    user.credits = (user.credits or 0) + order.credits
                    
                trans = TransactionHistory(
                    user_id=order.user_id,
                    amount=order.credits,
                    balance_after=user.credits if user else 0,
                    description="recharge",
                    details={
                        "task_type": "recharge",
                        "provider": "wechat",
                        "model": "cny",
                        "order_no": order_no, 
                        "amount_cny": order.amount, 
                        "method": "active_query"
                    }
                )
                db.add(trans)
            db.commit()
            db.refresh(order)

    return {"status": order.status, "paid_at": order.paid_at}

@router.post("/billing/recharge/notify")
async def wechat_notify(request: Request, db: Session = Depends(get_db)):
    """
    WeChat Pay Callback
    """
    try:
        setting = _get_active_wechat_config(db)
        if setting:
            payment_service.update_config(_wechat_config_to_dict(setting))
        else:
            logger.warning("Notification received but no Payment Config found. Assuming Mock or Invalid.")
            # If no config, we can't verify signature.
            raise HTTPException(status_code=500, detail="Configuration Missing")

        _release_db_connection(db, "wechat_notify_wait_body")
        headers = request.headers
        body = await request.body()
        
        # Verify and Parse
        result = payment_service.parse_notify(headers, body)
        
        if result:
            logger.info(f"WeChat Notify Received: {result}")
            # Reference: {"appid": "...", "mchid": "...", "out_trade_no": "...", "transaction_id": "...", "trade_state": "SUCCESS", ...}
            
            # Check trade_state
            trade_state = result.get('trade_state')
            out_trade_no = result.get('out_trade_no')
            
            if trade_state == "SUCCESS" and out_trade_no:
                order = db.query(PaymentOrder).filter(
                    PaymentOrder.order_no == out_trade_no,
                    PaymentOrder.status == "PENDING"
                ).first()
                
                if order:
                    order.status = "PAID"
                    order.paid_at = now_bj_iso()
                    # Store transaction_id from WeChat
                    wx_transaction_id = result.get('transaction_id')
                    
                    from app.models.all_models import UserGroup
                    if order.target_group_id:
                        target_group = db.query(UserGroup).filter(UserGroup.id == order.target_group_id).first()
                        if target_group:
                            old_credits = target_group.credits or 0
                            target_group.credits = old_credits + order.credits
                            trans = TransactionHistory(
                                user_id=order.user_id,
                                target_group_id=order.target_group_id,
                                amount=order.credits,
                                balance_after=target_group.credits,
                                description="Group Recharge (WeChat)",
                                details={
                                    "task_type": "group_recharge", "provider": "wechat", "model": "cny",
                                    "order_no": out_trade_no, 
                                    "method": "notify", 
                                    "wx_transaction_id": wx_transaction_id,
                                    "payer_openid": result.get("payer", {}).get("openid")
                                }
                            )
                            db.add(trans)
                    else:
                        user = db.query(User).filter(User.id == order.user_id).first()
                        if user:
                            user.credits = (user.credits or 0) + order.credits
                            
                        trans = TransactionHistory(
                            user_id=order.user_id,
                            amount=order.credits,
                            balance_after=user.credits if user else 0,
                            description="recharge", 
                            details={
                                "task_type": "recharge", "provider": "wechat", "model": "cny",
                                "order_no": out_trade_no, 
                                "method": "notify", 
                                "wx_transaction_id": wx_transaction_id,
                                "payer_openid": result.get("payer", {}).get("openid"),
                            }
                        )
                        db.add(trans)
                    db.commit()
                    logger.info(f"Order {out_trade_no} confirmed via Notify")
            else:
                logger.warning(f"Notify received but trade_state is {trade_state}")
                    
        return {"code": "SUCCESS", "message": "OK"}
    except Exception as e:
        logger.error(f"Notify Error: {e}")
        # Return generic failure or still success to stop retries if it's a code error?
        # Better to return failure (500) so WeChat retries later if it was a temp DB issue.
        raise HTTPException(status_code=500, detail="Internal Error")

@router.post("/billing/recharge/mock_pay/{order_no}")
def mock_pay_order(
    order_no: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Dev only or check config?
    # For now allow any user to pay their own order for testing
    order = db.query(PaymentOrder).filter(
        PaymentOrder.order_no == order_no,
        PaymentOrder.status == "PENDING"
    ).first()
    
    if not order:
        raise HTTPException(status_code=404, detail="Pending order not found")
        
    if order.user_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    # Process Payment
    order.status = "PAID"
    order.paid_at = now_bj_iso()
    
    # Add Credits
    from app.models.all_models import UserGroup
    if order.target_group_id:
        target_group = db.query(UserGroup).filter(UserGroup.id == order.target_group_id).first()
        if target_group:
            old_credits = target_group.credits or 0
            target_group.credits = old_credits + order.credits
            trans = TransactionHistory(
                user_id=order.user_id,
                target_group_id=order.target_group_id,
                amount=order.credits,
                balance_after=target_group.credits,
                description="Group Recharge (Mock)",
                details={
                    "task_type": "group_recharge", 
                    "provider": "wechat", 
                    "model": "cny", 
                    "order_no": order_no, 
                    "amount_cny": order.amount
                }
            )
            db.add(trans)
            db.commit()
            return {"status": "success", "new_balance": target_group.credits}
    
    user = db.query(User).filter(User.id == order.user_id).first()
    old_credits = user.credits or 0
    user.credits = old_credits + order.credits
    
    # Log Transaction
    trans = TransactionHistory(
        user_id=user.id,
        amount=order.credits,
        balance_after=user.credits,
        description="recharge",
        details={
            "task_type": "recharge", 
            "provider": "wechat", 
            "model": "cny", 
            "order_no": order_no, 
            "amount_cny": order.amount
        }
    )
    db.add(trans)
    
    db.commit()
    
    return {"status": "success", "new_balance": user.credits}


