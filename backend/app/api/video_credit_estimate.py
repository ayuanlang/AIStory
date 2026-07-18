# -*- coding: utf-8 -*-
"""Video generation credit dry-run estimate API."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional, Tuple

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models import all_models as models
from app.services.billing_service import billing_service

User = models.User
Project = models.Project
logger = logging.getLogger(__name__)
api_logger = logging.getLogger("api_logger")
activity_logger = logging.getLogger("functional_activity")

router = APIRouter(tags=["billing"])


def _log_video_estimate(message: str, *args: Any) -> None:
    """Write estimate diagnostics to app_info.log via shared loggers."""
    try:
        text = message % args if args else str(message)
    except Exception:
        text = f"{message} | args={args!r}"
    # Ensure file handlers exist even if this module loaded before logging bootstrap.
    try:
        from app.core.logging import _ensure_runtime_info_file_logging
        _ensure_runtime_info_file_logging()
    except Exception:
        pass
    for target in (
        api_logger,
        activity_logger,
        logger,
        logging.getLogger(),
    ):
        try:
            target.info("%s", text)
        except Exception:
            pass
    # Force flush so lines appear immediately in app_info.log during local debug.
    try:
        for handler in list(logging.getLogger().handlers):
            try:
                handler.flush()
            except Exception:
                pass
    except Exception:
        pass


def _is_per_second_provider(provider: Any) -> bool:
    provider_lower = str(provider or "").strip().lower()
    if not provider_lower:
        return False
    if provider_lower == "kie" or provider_lower.startswith("kie/") or "kie.ai" in provider_lower:
        return True
    if provider_lower == "runninghub" or provider_lower.startswith("runninghub/") or "runninghub" in provider_lower:
        return True
    return False


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
    video_resolution: Optional[str] = None


def _to_positive_int_or_none(value: Any) -> Optional[int]:
    try:
        parsed = int(value)
    except Exception:
        return None
    return parsed if parsed > 0 else None


def _pick_project_visual_for_estimate(info: Any) -> Dict[str, Any]:
    if not isinstance(info, dict):
        return {}
    defaults = info.get("project_generation_defaults") if isinstance(info.get("project_generation_defaults"), dict) else {}
    tech = info.get("tech_params") if isinstance(info.get("tech_params"), dict) else {}
    vis = tech.get("visual_standard") if isinstance(tech.get("visual_standard"), dict) else {}
    out: Dict[str, Any] = {
        "aspect_ratio": (
            vis.get("aspect_ratio") or vis.get("aspectRatio")
            or defaults.get("aspect_ratio") or defaults.get("aspectRatio")
            or info.get("aspect_ratio") or info.get("aspectRatio")
        ),
        "width": (
            vis.get("horizontal_resolution") or vis.get("width")
            or defaults.get("horizontal_resolution") or info.get("width")
        ),
        "height": (
            vis.get("vertical_resolution") or vis.get("height")
            or defaults.get("vertical_resolution") or info.get("height")
        ),
        "resolution": vis.get("resolution") or defaults.get("resolution") or info.get("resolution"),
        "video_resolution": (
            vis.get("video_resolution")
            or defaults.get("video_resolution")
            or info.get("video_resolution")
        ),
        "image_size": (
            vis.get("image_size") or vis.get("imageSize")
            or defaults.get("image_size") or defaults.get("imageSize")
            or info.get("image_size") or info.get("imageSize")
        ),
    }
    nested = info.get("e_global_info") if isinstance(info.get("e_global_info"), dict) else None
    if nested:
        nested_values = _pick_project_visual_for_estimate(nested)
        for key in ("aspect_ratio", "width", "height", "resolution", "video_resolution", "image_size"):
            if not out.get(key) and nested_values.get(key):
                out[key] = nested_values.get(key)
    return out


def _build_video_credit_estimate_details(
    db: Session,
    current_user: User,
    req: VideoCreditEstimateRequest,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    from app.api.endpoints import (
        _resolve_media_runtime_target,
        _infer_project_resolution,
        _normalize_project_image_size,
        _normalize_project_video_resolution,
        _project_video_resolution_label,
        _infer_dims_from_video_resolution_tier,
    )

    runtime_target = _resolve_media_runtime_target(
        provider=None,
        model=None,
        media_type="video",
        category="Video",
        user_id=current_user.id,
        user_credits=(current_user.credits or 0),
        function_name=str(req.function_name or "generate_videos").strip() or "generate_videos",
        system_api_id=req.system_api_id,
    )
    reserve_provider = runtime_target.get("resolved_provider")
    reserve_model = runtime_target.get("resolved_model")
    reserve_system_api_id = runtime_target.get("resolved_system_api_id")
    if req.system_api_id and not reserve_system_api_id:
        reserve_system_api_id = int(req.system_api_id)

    project_global_info: Dict[str, Any] = {}
    resolved_project_id = _to_positive_int_or_none(req.project_id)
    if resolved_project_id:
        project = db.query(Project).filter(Project.id == int(resolved_project_id)).first()
        if project:
            raw_gi = getattr(project, "global_info", None)
            if isinstance(raw_gi, dict):
                project_global_info = raw_gi
            elif isinstance(raw_gi, str) and raw_gi.strip():
                try:
                    parsed = json.loads(raw_gi)
                    if isinstance(parsed, dict):
                        project_global_info = parsed
                except Exception:
                    project_global_info = {}

    project_visual = _pick_project_visual_for_estimate(project_global_info)
    aspect_ratio = str(req.aspect_ratio or "").strip() or str(project_visual.get("aspect_ratio") or "").strip() or "16:9"

    resolved_video_width = _to_positive_int_or_none(req.width)
    resolved_video_height = _to_positive_int_or_none(req.height)
    resolved_video_resolution = str(req.resolution or "").strip() or None
    resolved_video_image_size = str(project_visual.get("image_size") or "").strip() or None
    if resolved_video_image_size:
        resolved_video_image_size = _normalize_project_image_size(resolved_video_image_size) or resolved_video_image_size

    draft_mode = bool(req.draft_mode)
    if draft_mode:
        # Draft always bills/generates at 480p; ignore client width/height from project 720 prefs.
        resolved_video_image_size = "0.5K"
        resolved_video_resolution = "480p"
        draft_dims = _infer_dims_from_video_resolution_tier(
            aspect_ratio,
            "480",
            provider=reserve_provider,
            model=reserve_model,
        )
        if draft_dims:
            resolved_video_width, resolved_video_height = draft_dims
        else:
            resolved_video_width = None
            resolved_video_height = None
    else:
        video_tier = (
            _normalize_project_video_resolution(req.video_resolution)
            or _normalize_project_video_resolution(req.resolution)
            or _normalize_project_video_resolution(project_visual.get("video_resolution"))
            or "720"
        )
        resolved_video_resolution = _project_video_resolution_label(video_tier)
        video_dims = _infer_dims_from_video_resolution_tier(
            aspect_ratio,
            video_tier,
            provider=reserve_provider,
            model=reserve_model,
        )
        if video_dims:
            resolved_video_width, resolved_video_height = video_dims

    if (not resolved_video_width or not resolved_video_height) and resolved_video_image_size and aspect_ratio:
        inferred_dims = _infer_project_resolution(aspect_ratio, resolved_video_image_size)
        if inferred_dims:
            inferred_w, inferred_h = inferred_dims
            if not resolved_video_width and inferred_w:
                resolved_video_width = int(inferred_w)
            if not resolved_video_height and inferred_h:
                resolved_video_height = int(inferred_h)
            if resolved_video_width and resolved_video_height and not resolved_video_resolution:
                resolved_video_resolution = f"{int(resolved_video_width)}x{int(resolved_video_height)}"

    try:
        duration_raw = float(req.duration) if req.duration is not None else 5.0
    except Exception:
        duration_raw = 5.0
    est_duration = max(5, int(duration_raw)) if duration_raw > 0 else 5

    has_video_input = req.has_video_input
    if has_video_input is None:
        has_video_input = bool(req.use_prev_video)
    has_video_input = bool(has_video_input)

    input_duration = None
    try:
        if req.input_duration_seconds is not None and float(req.input_duration_seconds) > 0:
            input_duration = float(req.input_duration_seconds)
    except Exception:
        input_duration = None

    # KIE / RunningHub Seedance use per-second resolution matrices; never Ark token formula.
    _is_token_billing = (
        (not _is_per_second_provider(reserve_provider))
        and billing_service.is_token_pricing(db, "video_gen", reserve_provider, reserve_model)
    )
    details: Dict[str, Any] = {
        "billing_mode": "ESTIMATE",
        "duration": duration_raw if duration_raw > 0 else est_duration,
        "duration_seconds": est_duration,
        "estimated_duration": est_duration,
        "draft_mode": draft_mode,
        "draft": draft_mode,
        "use_prev_video": bool(req.use_prev_video),
        "shot_continuation": bool(req.use_prev_video),
        "has_video_input": has_video_input,
        "function_name": str(req.function_name or "generate_videos").strip() or "generate_videos",
        "aspect_ratio": aspect_ratio,
    }
    if input_duration is not None:
        details["input_duration_seconds"] = input_duration
    if resolved_video_width:
        details["width"] = int(resolved_video_width)
    if resolved_video_height:
        details["height"] = int(resolved_video_height)
    if resolved_video_resolution:
        details["resolution"] = str(resolved_video_resolution)
    if resolved_video_image_size:
        details["image_size"] = str(resolved_video_image_size)
    if reserve_provider:
        details["provider"] = reserve_provider
        details["resolved_provider"] = reserve_provider
    if reserve_model:
        details["model"] = reserve_model
        details["resolved_model"] = reserve_model
    if reserve_system_api_id is not None:
        details["system_api_id"] = int(reserve_system_api_id)
        details["resolved_system_api_id"] = int(reserve_system_api_id)
    if resolved_project_id:
        details["project_id"] = int(resolved_project_id)
    if _to_positive_int_or_none(req.episode_id):
        details["episode_id"] = int(req.episode_id)
    if _to_positive_int_or_none(req.shot_id):
        details["shot_id"] = int(req.shot_id)

    if _is_token_billing:
        _video_token_cfg = billing_service.resolve_video_token_config(db, reserve_provider, reserve_model)
        reserve_width = int(resolved_video_width) if resolved_video_width else int(_video_token_cfg.get("default_width", 1280))
        reserve_height = int(resolved_video_height) if resolved_video_height else int(_video_token_cfg.get("default_height", 720))
        reserve_fps = int(_video_token_cfg.get("default_fps", 24))
        _draft_coeff = float(_video_token_cfg.get("draft_token_coefficient", 1.0) or 1.0)
        if draft_mode and not (0 < _draft_coeff < 1.0):
            _draft_coeff = float(getattr(billing_service, "DEFAULT_SEEDANCE_DRAFT_PRICE_MULTIPLIER", 0.7) or 0.7)
        _is_seedance_2 = bool(_video_token_cfg.get("is_seedance_2")) or billing_service.is_seedance_2_model(
            reserve_provider, reserve_model
        )
        _token_estimate = billing_service.estimate_video_token_usage(
            width=reserve_width,
            height=reserve_height,
            fps=reserve_fps,
            output_duration_seconds=est_duration,
            has_video_input=has_video_input,
            input_duration_seconds=input_duration,
            draft_token_coefficient=_draft_coeff,
            method=("seedance2_video_token_formula" if _is_seedance_2 else "video_token_formula"),
        )
        _estimated_tokens = int(_token_estimate.get("tokens") or 0)
        details.update({
            "output_tokens": _estimated_tokens,
            "total_tokens": _estimated_tokens,
            "estimation_method": _token_estimate.get("estimation_method") or "video_token_formula",
            "video_token_branch": "seedance2" if _is_seedance_2 else "fallback",
            "video_token_estimate": _token_estimate,
            "width": reserve_width,
            "height": reserve_height,
            "fps": reserve_fps,
            "input_duration_seconds": _token_estimate.get("input_duration_seconds"),
            "is_seedance_2": bool(_is_seedance_2),
            "draft_token_coefficient": _draft_coeff,
        })

    meta = {
        "resolved_provider": reserve_provider,
        "resolved_model": reserve_model,
        "resolved_system_api_id": reserve_system_api_id,
        "is_token_billing": bool(_is_token_billing),
        "aspect_ratio": aspect_ratio,
        "width": details.get("width"),
        "height": details.get("height"),
        "resolution": details.get("resolution"),
        "duration_seconds": est_duration,
        "has_video_input": has_video_input,
        "draft_mode": draft_mode,
    }
    return details, meta


@router.post("/billing/estimate/video")
def estimate_video_generation_credits(
    req: VideoCreditEstimateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dry-run estimate of user credits for one video generation (no reserve/deduct)."""
    _log_video_estimate(
        "[BillingProcess] video_estimate_hit user=%s system_api_id=%s duration=%s draft=%s has_video_input=%s "
        "width=%s height=%s project_id=%s shot_id=%s",
        getattr(current_user, "id", None),
        req.system_api_id,
        req.duration,
        req.draft_mode,
        req.has_video_input if req.has_video_input is not None else req.use_prev_video,
        req.width,
        req.height,
        req.project_id,
        req.shot_id,
    )
    try:
        details, meta = _build_video_credit_estimate_details(db, current_user, req)
    except Exception as exc:
        _log_video_estimate(
            "[BillingProcess] video_estimate_build_failed user=%s err=%s",
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
    _log_video_estimate(
        "[BillingProcess] video_estimate user=%s credits=%s logic=%s new_logic=%s rule=%s "
        "unit=%s tier=%s has_video_input=%s duration=%s source=%s provider=%s model=%s "
        "system_api_id=%s token_billing=%s tokens=%s",
        getattr(current_user, "id", None),
        estimated,
        billing_process.get("logic_branch"),
        billing_process.get("new_logic"),
        billing_process.get("matched_rule_id"),
        billing_process.get("unit_type"),
        usage_meta.get("resolution_tier") or meta.get("resolution"),
        usage_meta.get("has_video_input"),
        usage_meta.get("duration_seconds") or meta.get("duration_seconds"),
        billing_process.get("api_pricing_source") or breakdown.get("api_pricing_source"),
        billing_process.get("provider") or meta.get("resolved_provider"),
        billing_process.get("model") or meta.get("resolved_model"),
        breakdown.get("system_api_id") or meta.get("resolved_system_api_id"),
        meta.get("is_token_billing"),
        (details.get("video_token_estimate") or {}).get("tokens")
        if isinstance(details.get("video_token_estimate"), dict)
        else details.get("output_tokens"),
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
