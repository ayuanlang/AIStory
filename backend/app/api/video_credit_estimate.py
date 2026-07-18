# -*- coding: utf-8 -*-
"""Video generation credit dry-run estimate API."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models import all_models as models
from app.services.billing_service import billing_service
from app.services.video_billing_details import build_video_generation_billing_details

User = models.User
logger = logging.getLogger(__name__)

router = APIRouter(tags=["billing"])


def _log_video_estimate(message: str, *args: Any) -> None:
    """Single-logger estimate diagnostic (no multi-logger fan-out)."""
    try:
        logger.info(message, *args)
    except Exception:
        try:
            logger.info("%s | args=%s", message, args)
        except Exception:
            pass


class VideoCreditEstimateRequest(BaseModel):
    system_api_id: Optional[int] = None
    function_name: Optional[str] = "generate_videos"
    project_id: Optional[int] = None
    episode_id: Optional[int] = None
    shot_id: Optional[int] = None
    duration: Optional[float] = 5.0
    draft_mode: Optional[bool] = False
    use_prev_video: Optional[bool] = False
    has_video_input: Optional[bool] = None
    input_duration_seconds: Optional[float] = None
    aspect_ratio: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    resolution: Optional[str] = None
    video_resolution: Optional[str] = None


def _build_video_credit_estimate_details(
    db: Session,
    current_user: User,
    req: VideoCreditEstimateRequest,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Thin wrapper: estimate + reserve share build_video_generation_billing_details."""
    return build_video_generation_billing_details(
        db,
        user_id=getattr(current_user, "id", None),
        user_credits=(getattr(current_user, "credits", None) or 0),
        billing_mode="ESTIMATE",
        function_name=str(req.function_name or "generate_videos").strip() or "generate_videos",
        system_api_id=req.system_api_id,
        project_id=req.project_id,
        episode_id=req.episode_id,
        shot_id=req.shot_id,
        duration=req.duration,
        draft_mode=bool(req.draft_mode),
        use_prev_video=bool(req.use_prev_video),
        has_video_input=req.has_video_input,
        input_duration_seconds=req.input_duration_seconds,
        aspect_ratio=req.aspect_ratio,
        width=req.width,
        height=req.height,
        resolution=req.resolution,
        video_resolution=req.video_resolution,
    )


@router.post("/billing/estimate/video")
def estimate_video_generation_credits(
    req: VideoCreditEstimateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dry-run estimate of user credits for one video generation (no reserve/deduct)."""
    try:
        details, meta = _build_video_credit_estimate_details(db, current_user, req)
    except Exception as exc:
        _log_video_estimate(
            "[BillingProcess] video_estimate_failed user=%s err=%s",
            getattr(current_user, "id", None),
            exc,
        )
        raise
    details["billing_mode"] = "ESTIMATE_PREVIEW"
    breakdown = billing_service.estimate_cost_breakdown(
        db,
        "video_gen",
        meta.get("resolved_provider"),
        meta.get("resolved_model"),
        details,
        phase="estimate",
    ) or {}
    estimated = int(breakdown.get("total_cost") or 0)
    billing_process = breakdown.get("billing_process") if isinstance(breakdown.get("billing_process"), dict) else {}
    if not billing_process:
        billing_process = billing_service._build_billing_process_snapshot(breakdown, phase="estimate")
    usage_meta = billing_process.get("usage") if isinstance(billing_process.get("usage"), dict) else {}
    logger.debug(
        "[BillingProcess] estimate user=%s credits=%s logic=%s rule=%s unit=%s tier=%s dur=%s %s/%s",
        getattr(current_user, "id", None),
        estimated,
        billing_process.get("logic_branch"),
        billing_process.get("matched_rule_id"),
        billing_process.get("unit_type"),
        usage_meta.get("resolution_tier") or meta.get("resolution"),
        usage_meta.get("duration_seconds") or meta.get("duration_seconds"),
        billing_process.get("provider") or meta.get("resolved_provider"),
        billing_process.get("model") or meta.get("resolved_model"),
    )
    return {
        "ok": True,
        "estimated_credits": estimated,
        "total_cost": estimated,
        "feature_cost": int(breakdown.get("feature_cost") or 0),
        "api_cost": int(breakdown.get("api_cost") or 0),
        "function_billing": breakdown.get("function_billing") or {},
        "matched_rule_id": breakdown.get("matched_rule_id"),
        "matched_rule_name": breakdown.get("matched_rule_name"),
        "system_api_id": breakdown.get("system_api_id") or meta.get("resolved_system_api_id"),
        "provider": breakdown.get("resolved_provider") or meta.get("resolved_provider"),
        "model": breakdown.get("resolved_model") or meta.get("resolved_model"),
        "usage": {
            "duration_seconds": meta.get("duration_seconds"),
            "width": meta.get("width"),
            "height": meta.get("height"),
            "resolution": meta.get("resolution"),
            "aspect_ratio": meta.get("aspect_ratio"),
            "has_video_input": meta.get("has_video_input"),
            "draft_mode": meta.get("draft_mode"),
            "is_token_billing": meta.get("is_token_billing"),
            "input_duration_seconds": details.get("input_duration_seconds"),
            "video_token_estimate": details.get("video_token_estimate"),
            "resolution_tier": (billing_process.get("usage") or {}).get("resolution_tier"),
            "estimation_method": (billing_process.get("usage") or {}).get("estimation_method"),
        },
        "billing_process": billing_process,
        "audit_summary": breakdown.get("audit_summary") or {},
    }
