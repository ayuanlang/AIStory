# -*- coding: utf-8 -*-
"""Section routes — symbols pulled from shared module."""
from __future__ import annotations

from app.api.routers.billing_pkg import shared as _shared

router = _shared.router
globals().update(
    {
        k: v
        for k, v in vars(_shared).items()
        if k
        not in {
            "__name__",
            "__file__",
            "__package__",
            "__loader__",
            "__spec__",
            "__doc__",
            "__builtins__",
        }
    }
)


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



