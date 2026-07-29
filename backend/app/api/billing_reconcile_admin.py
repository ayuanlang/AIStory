"""Admin APIs for manual billing usage reconcile."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.jobs.billing_reconcile import (
    list_billing_reconcile_candidates,
    run_billing_reconcile_by_action_ids,
    run_billing_reconcile_single,
)
from app.models.all_models import User
from app.services.system_log_service import log_action

router = APIRouter(tags=["admin-billing-reconcile"])


class BillingReconcileCandidateOut(BaseModel):
    action_id: int
    transaction_id: Optional[int] = None
    user_id: Optional[int] = None
    stage: str = ""
    task_type: str = ""
    provider: Optional[str] = None
    model: Optional[str] = None
    system_api_id: Optional[Any] = None
    created_at: Optional[str] = None
    reserved_cost: int = 0
    actual_cost: int = 0
    billing_basis: Optional[str] = None
    token_source: Optional[str] = None
    usage_source: Optional[str] = None
    reconcile_status: Optional[str] = None
    reconcile_attempts: int = 0
    task_id: Optional[str] = None
    has_task_id: bool = False
    missing_reasons: List[str] = Field(default_factory=list)
    description: Optional[str] = None


class BillingReconcileCandidatesOut(BaseModel):
    ok: bool = True
    lookback_days: int
    cutoff_at: str
    total_count: int
    candidates: List[BillingReconcileCandidateOut]
    created_at: str


class BillingReconcileRunRequest(BaseModel):
    action_ids: List[int] = Field(default_factory=list)
    lookback_days: Optional[int] = None


class BillingReconcileRunOut(BaseModel):
    ok: bool
    lookback_days: int
    requested_count: int
    reconciled_ok: int
    skipped_count: int
    error_count: int
    results: list
    errors: list
    process_log: list
    created_at: str


def _require_superuser(user: User) -> None:
    if not getattr(user, "is_superuser", False):
        raise HTTPException(status_code=403, detail="Only superuser can manage billing reconcile")


@router.get("/admin/billing-reconcile/candidates", response_model=BillingReconcileCandidatesOut)
def get_billing_reconcile_candidates(
    lookback_days: Optional[int] = Query(None, ge=1, le=90),
    limit: Optional[int] = Query(None, ge=1, le=2000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_superuser(current_user)
    _ = db
    days = int(lookback_days if lookback_days is not None else getattr(settings, "BILLING_RECONCILE_LOOKBACK_DAYS", 3))
    payload = list_billing_reconcile_candidates(lookback_days=days, limit=limit)
    return BillingReconcileCandidatesOut(**payload)


@router.post("/admin/billing-reconcile/run", response_model=BillingReconcileRunOut)
def post_billing_reconcile_run(
    req: BillingReconcileRunRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_superuser(current_user)
    _ = db
    action_ids = [int(x) for x in (req.action_ids or []) if str(x).strip()]
    if not action_ids:
        raise HTTPException(status_code=400, detail="action_ids is required")
    if len(action_ids) > 500:
        raise HTTPException(status_code=400, detail="Too many action_ids (max 500 per request)")

    result = run_billing_reconcile_by_action_ids(
        action_ids,
        lookback_days=req.lookback_days,
    )
    return BillingReconcileRunOut(**result)


class BillingReconcileSingleRequest(BaseModel):
    provider: str
    task_id: str

class BillingReconcileSingleOut(BaseModel):
    ok: bool
    error: Optional[str] = None
    provider: Optional[str] = None
    task_id: Optional[str] = None
    query_endpoint: Optional[str] = None
    system_api_id: Optional[int] = None
    usage: Optional[Dict[str, Any]] = None
    raw_response: Optional[Dict[str, Any]] = None

@router.post("/admin/billing-reconcile/single", response_model=BillingReconcileSingleOut)
def post_billing_reconcile_single(
    req: BillingReconcileSingleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_superuser(current_user)
    _ = db
    if not req.provider or not req.task_id:
        raise HTTPException(status_code=400, detail="provider and task_id are required")

    log_action(
        db,
        user_id=current_user.id,
        user_name=current_user.username,
        action="BILLING_RECONCILE_SINGLE",
        details=f"Provider: {req.provider}, TaskID: {req.task_id}"
    )
    result = run_billing_reconcile_single(req.provider, req.task_id)
    return BillingReconcileSingleOut(**result)
