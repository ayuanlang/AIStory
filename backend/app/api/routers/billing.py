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


def _bind_endpoint_helpers() -> None:
    from app.api.routers.helper_bind import bind_shared_helpers
    bind_shared_helpers(globals(), __name__)

_bind_endpoint_helpers()


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


# --- Billing Management ---


@router.get("/billing/options")
def get_billing_options(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Return provider/model dropdown options for Pricing Rules.

    Options are derived from *system* APISettings so Pricing Rules stay consistent
    with Settings (provider/model identifiers).
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")

    source_categories_by_task_type = tool_billing_taxonomy_service.get_billable_source_categories_by_task_type()
    feature_pricing = billing_service.get_feature_pricing_map(db)
    if not source_categories_by_task_type:
        source_categories_by_task_type = {
            "llm_chat": ["LLM"],
            "analysis": ["LLM", "Vision"],
            "analysis_character": ["LLM", "Vision"],
            "image_gen": ["Image"],
            "video_gen": ["Video"],
        }

    all_settings = db.query(SystemAPISetting).all()
    if not all_settings:
        return {
            "taskTypes": sorted(list(source_categories_by_task_type.keys())),
            "sourceCategoriesByTaskType": source_categories_by_task_type,
            "providersByTaskType": {k: [] for k in source_categories_by_task_type.keys()},
            "modelsByProvider": {},
            "featurePricing": feature_pricing,
        }

    # Build category -> providers/models
    providers_by_category = {}
    models_by_provider = {}

    for s in all_settings:
        category = s.category or "LLM"
        providers_by_category.setdefault(category, set()).add(s.provider)
        if s.provider not in models_by_provider:
            models_by_provider[s.provider] = set()
        if s.model:
            models_by_provider[s.provider].add(s.model)

    def _union_categories(*cats: str):
        out = set()
        for c in cats:
            out |= providers_by_category.get(c, set())
        return out

    providers_by_task_type = {
        task_type: _union_categories(*cats)
        for task_type, cats in source_categories_by_task_type.items()
    }

    return {
        "taskTypes": sorted(list(providers_by_task_type.keys())),
        "sourceCategoriesByTaskType": source_categories_by_task_type,
        "providersByTaskType": {k: sorted(list(v)) for k, v in providers_by_task_type.items()},
        "modelsByProvider": {k: sorted(list(v)) for k, v in models_by_provider.items()},
        "featurePricing": feature_pricing,
    }


@router.get("/billing/feature-pricing", response_model=FeaturePricingOut)
def get_billing_feature_pricing(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")

    return FeaturePricingOut(feature_pricing=billing_service.get_feature_pricing_map(db))


@router.put("/billing/feature-pricing", response_model=FeaturePricingOut)
def update_billing_feature_pricing(
    payload: FeaturePricingUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")

    saved = billing_service.set_feature_pricing_map(db, payload.feature_pricing or {})
    return FeaturePricingOut(feature_pricing=saved)


@router.get("/billing/default-api-pricing", response_model=DefaultApiPricingOut)
def get_billing_default_api_pricing(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")

    return DefaultApiPricingOut(
        default_api_pricing=billing_service.get_default_api_pricing_map(db),
        recommended_default_api_pricing=billing_service.get_recommended_default_api_pricing_map(),
        content_fallback_pricing=billing_service.get_content_fallback_pricing(db),
    )


@router.put("/billing/default-api-pricing", response_model=DefaultApiPricingOut)
def update_billing_default_api_pricing(
    payload: DefaultApiPricingUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")

    saved = billing_service.set_default_api_pricing_map(db, payload.default_api_pricing or {})
    if payload.content_fallback_pricing is None:
        fallback_saved = billing_service.get_content_fallback_pricing(db)
    else:
        fallback_saved = billing_service.set_content_fallback_pricing(db, payload.content_fallback_pricing or {})
    return DefaultApiPricingOut(
        default_api_pricing=saved,
        recommended_default_api_pricing=billing_service.get_recommended_default_api_pricing_map(),
        content_fallback_pricing=fallback_saved,
    )


@router.get("/billing/taxonomy/preview")
def get_billing_taxonomy_preview(
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")

    entries = tool_billing_taxonomy_service.get_entries()
    source_categories_by_task_type = tool_billing_taxonomy_service.get_billable_source_categories_by_task_type()

    task_types_by_source_category: Dict[str, List[str]] = {}
    category_set = set()
    for categories in source_categories_by_task_type.values():
        for category in categories:
            category_text = str(category or "").strip()
            if category_text:
                category_set.add(category_text)

    for category in sorted(list(category_set)):
        task_types_by_source_category[category] = tool_billing_taxonomy_service.get_billable_task_types_for_source_category(category)

    return {
        "entryCount": len(entries),
        "entries": entries,
        "taskTypes": sorted(list(source_categories_by_task_type.keys())),
        "sourceCategoriesByTaskType": source_categories_by_task_type,
        "taskTypesBySourceCategory": task_types_by_source_category,
    }


@router.get("/billing/project/{project_id}/stats")
def get_project_billing_stats(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return credit consumption stats for a project.

    Returns:
        user_cost  – credits consumed by the current user in this project (negative amount = cost)
        total_cost – credits consumed by all users in this project
    """
    # Verify the requesting user has access to the project
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not current_user.is_superuser and project.owner_id != current_user.id:
        # Check shares
        share = db.query(ProjectShare).filter(
            ProjectShare.project_id == project_id,
            ProjectShare.user_id == current_user.id,
        ).first()
        if not share:
            raise HTTPException(status_code=403, detail="Not authorized")

    from sqlalchemy import func as sa_func

    # Total cost (all users): sum of negative amounts on transaction_history for this project
    total_row = (
        db.query(sa_func.coalesce(sa_func.sum(TransactionHistory.amount), 0))
        .filter(
            TransactionHistory.project_id == project_id,
            TransactionHistory.amount < 0,
        )
        .scalar()
    )
    total_cost = abs(int(total_row or 0))

    # Current user's cost in this project
    user_row = (
        db.query(sa_func.coalesce(sa_func.sum(TransactionHistory.amount), 0))
        .filter(
            TransactionHistory.project_id == project_id,
            TransactionHistory.user_id == current_user.id,
            TransactionHistory.amount < 0,
        )
        .scalar()
    )
    user_cost = abs(int(user_row or 0))

    return {
        "project_id": project_id,
        "user_cost": user_cost,
        "total_cost": total_cost,
    }


@router.get("/billing/transactions", response_model=List[TransactionOut])
def get_transactions(
    user_id: Optional[int] = None,
    task_type: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_superuser and (user_id and user_id != current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized")

    query = db.query(TransactionHistory)

    if task_type:
        query = query.filter(TransactionHistory.action_audit.has(task_type=task_type))
    if provider:
        query = query.filter(TransactionHistory.action_audit.has(provider=provider))
    if model:
        query = query.filter(TransactionHistory.action_audit.has(model=model))

    from sqlalchemy.orm import joinedload
    query = query.options(joinedload(TransactionHistory.action_audit))

    # Non-superusers can only see their own
    target_id = user_id if user_id else (None if current_user.is_superuser else current_user.id)

    if target_id:
        query = query.filter(TransactionHistory.user_id == target_id)

    rows = query.order_by(TransactionHistory.id.desc()).limit(limit).all()
    alias_map = _build_provider_alias_lookup(db)
    results: List[Dict[str, Any]] = []
    for row in rows:
        # Action audit holds provider, model, task_type, etc.
        action = row.action_audit
        provider_text = str(getattr(action, "provider", "") or "").strip() or None if action else None
        model_text = action.model if action else None
        task_text = action.task_type if action else None
        project_id = (action.project_id if action else None) or getattr(row, "project_id", None)
        episode_id = (action.episode_id if action else None) or getattr(row, "episode_id", None)
        
        provider_alias = _resolve_provider_alias(alias_map, provider_text)
        details_payload = _attach_provider_alias_deep(getattr(row, "details", None), alias_map)
        
        # Support fallback description
        display_description = row.description
        if not display_description and task_text:
            display_description = task_text
            
        details_dict = details_payload if isinstance(details_payload, dict) else {}
        reserved_cost = None
        actual_cost = None
        if action is not None:
            try:
                reserved_cost = int(getattr(action, "reserved_cost", 0) or 0)
            except Exception:
                reserved_cost = None
            try:
                actual_cost = int(getattr(action, "actual_cost", 0) or 0)
            except Exception:
                actual_cost = None
        if reserved_cost in (None, 0) and details_dict.get("reserved_cost") is not None:
            try:
                reserved_cost = int(details_dict.get("reserved_cost") or 0)
            except Exception:
                pass
        if actual_cost in (None, 0) and details_dict.get("actual_cost") is not None:
            try:
                actual_cost = int(details_dict.get("actual_cost") or 0)
            except Exception:
                pass

        personal_balance_after = details_dict.get("personal_balance_after")
        if personal_balance_after is None:
            personal_balance_after = row.balance_after
        group_balance_after = details_dict.get("group_balance_after")

        payload = {
            "id": row.id,
            "user_id": row.user_id,
            "amount": row.amount,
            "balance_after": row.balance_after,
            "description": display_description,
            "task_type": task_text,
            "provider": provider_text,
            "model": model_text,
            "details": details_payload,
            "project_id": project_id,
            "episode_id": episode_id,
            "created_at": row.created_at,
            "reserved_cost": reserved_cost,
            "actual_cost": actual_cost,
            "personal_balance_after": personal_balance_after,
            "group_balance_after": group_balance_after,
        }
        if provider_alias:
            payload["provider_alias"] = provider_alias
        results.append(payload)

    return results

@router.post("/billing/users/{user_id}/credits")
def update_user_credits(
    user_id: int,
    credit_update: CreditUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    old_credits = user.credits or 0
    if credit_update.mode == "add":
        user.credits = old_credits + credit_update.amount
    else:
        user.credits = credit_update.amount
        
    # Log administrative transaction
    trans = TransactionHistory(
        user_id=user_id,
        amount=user.credits - old_credits,
        balance_after=user.credits,
        description="admin_adjustment",
        details={
            "task_type": "admin_adjustment",
            "admin_id": current_user.id, 
            "reason": "Manual Update"
        }
    )
    db.add(trans)
    
    db.commit()
    return {"credits": user.credits}



# Refresh cross-router helpers after local definitions are complete.
_bind_endpoint_helpers()

