# -*- coding: utf-8 -*-
"""Shared video-generation billing details for estimate + reserve.

Estimate preview and credit reservation MUST call build_video_generation_billing_details
so duration / draft / continuation / resolution matrices stay identical.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from app.services.billing_service import billing_service
from app.services.project_visual_resolution import (
    infer_dims_from_video_resolution_tier,
    infer_project_resolution,
    normalize_project_image_size,
    normalize_project_video_resolution,
    project_video_resolution_label,
    resolve_video_billing_runtime_target,
)


def is_per_second_video_provider(provider: Any) -> bool:
    provider_lower = str(provider or "").strip().lower()
    if not provider_lower:
        return False
    if provider_lower == "kie" or provider_lower.startswith("kie/") or "kie.ai" in provider_lower:
        return True
    if provider_lower == "runninghub" or provider_lower.startswith("runninghub/") or "runninghub" in provider_lower:
        return True
    return False


def _to_positive_int_or_none(value: Any) -> Optional[int]:
    try:
        parsed = int(value)
    except Exception:
        return None
    return parsed if parsed > 0 else None


def _pick_project_visual(info: Any) -> Dict[str, Any]:
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
        nested_values = _pick_project_visual(nested)
        for key in ("aspect_ratio", "width", "height", "resolution", "video_resolution", "image_size"):
            if not out.get(key) and nested_values.get(key):
                out[key] = nested_values.get(key)
    return out


def _load_project_global_info(db: Session, project_id: Optional[int]) -> Dict[str, Any]:
    if not project_id:
        return {}
    from app.models.all_models import Project

    project = db.query(Project).filter(Project.id == int(project_id)).first()
    if not project:
        return {}
    raw_gi = getattr(project, "global_info", None)
    if isinstance(raw_gi, dict):
        return raw_gi
    if isinstance(raw_gi, str) and raw_gi.strip():
        try:
            parsed = json.loads(raw_gi)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
    return {}


def _client_provides_video_visuals(
    *,
    aspect_ratio: Any = None,
    width: Any = None,
    height: Any = None,
    resolution: Any = None,
    video_resolution: Any = None,
    image_size: Any = None,
    draft_mode: Any = False,
) -> bool:
    """True when request already has enough visual inputs to skip loading project.global_info."""
    has_aspect = bool(str(aspect_ratio or "").strip())
    has_res_hint = bool(str(video_resolution or "").strip() or str(resolution or "").strip())
    has_image_size = bool(str(image_size or "").strip())
    has_dims = bool(_to_positive_int_or_none(width) and _to_positive_int_or_none(height))
    if not has_aspect:
        return False
    if bool(draft_mode):
        return True
    return has_res_hint or has_image_size or has_dims


def build_video_generation_billing_details(
    db: Session,
    *,
    user_id: Any = None,
    user_credits: Any = 0,
    billing_mode: str = "ESTIMATE",
    function_name: str = "generate_videos",
    provider: Any = None,
    model: Any = None,
    system_api_id: Any = None,
    project_id: Any = None,
    episode_id: Any = None,
    shot_id: Any = None,
    duration: Any = None,
    draft_mode: Any = False,
    use_prev_video: Any = False,
    has_video_input: Any = None,
    input_duration: Any = None,
    input_duration_seconds: Any = None,
    aspect_ratio: Any = None,
    width: Any = None,
    height: Any = None,
    resolution: Any = None,
    video_resolution: Any = None,
    image_size: Any = None,
    ref_video_urls: Any = None,
    project_global_info: Optional[Dict[str, Any]] = None,
    runtime_target: Optional[Dict[str, Any]] = None,
    extra_details: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Single source of truth for video_gen estimate + reserve billing payloads.

    Returns:
        details: passed to estimate_cost_breakdown / reserve_credits
        meta: resolved provider/model/system_api_id + flags used by callers
    """
    mode_text = str(billing_mode or "ESTIMATE").strip().upper() or "ESTIMATE"
    fn_name = str(function_name or "generate_videos").strip() or "generate_videos"

    if runtime_target is None:
        # Light resolve via system_api cache — never import endpoints / get_api_config.
        runtime_target = resolve_video_billing_runtime_target(
            system_api_id=system_api_id,
            provider=provider,
            model=model,
            category="Video",
        )
    else:
        runtime_target = dict(runtime_target)

    reserve_provider = runtime_target.get("resolved_provider") or provider
    reserve_model = runtime_target.get("resolved_model") or model
    reserve_system_api_id = runtime_target.get("resolved_system_api_id")
    if system_api_id and not reserve_system_api_id:
        try:
            reserve_system_api_id = int(system_api_id)
        except Exception:
            reserve_system_api_id = None

    resolved_project_id = _to_positive_int_or_none(project_id)
    if project_global_info is None:
        # ESTIMATE UI usually sends aspect/tier/dims; avoid hydrating large global_info blobs.
        if mode_text == "ESTIMATE" and _client_provides_video_visuals(
            aspect_ratio=aspect_ratio,
            width=width,
            height=height,
            resolution=resolution,
            video_resolution=video_resolution,
            image_size=image_size,
            draft_mode=draft_mode,
        ):
            project_global_info = {}
        else:
            project_global_info = _load_project_global_info(db, resolved_project_id)
    project_visual = _pick_project_visual(project_global_info)

    aspect = str(aspect_ratio or "").strip() or str(project_visual.get("aspect_ratio") or "").strip() or "16:9"
    resolved_video_width = _to_positive_int_or_none(width)
    resolved_video_height = _to_positive_int_or_none(height)
    resolved_video_resolution = str(resolution or "").strip() or None
    resolved_video_image_size = str(image_size or project_visual.get("image_size") or "").strip() or None
    if resolved_video_image_size:
        resolved_video_image_size = normalize_project_image_size(resolved_video_image_size) or resolved_video_image_size

    is_draft = bool(draft_mode)
    if is_draft:
        resolved_video_image_size = "0.5K"
        resolved_video_resolution = "480p"
        draft_dims = infer_dims_from_video_resolution_tier(
            aspect,
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
            normalize_project_video_resolution(video_resolution)
            or normalize_project_video_resolution(resolution)
            or normalize_project_video_resolution(project_visual.get("video_resolution"))
            or "720"
        )
        resolved_video_resolution = project_video_resolution_label(video_tier)
        video_dims = infer_dims_from_video_resolution_tier(
            aspect,
            video_tier,
            provider=reserve_provider,
            model=reserve_model,
        )
        if video_dims:
            resolved_video_width, resolved_video_height = video_dims

    if (not resolved_video_width or not resolved_video_height) and resolved_video_image_size and aspect:
        inferred_dims = infer_project_resolution(aspect, resolved_video_image_size)
        if inferred_dims:
            inferred_w, inferred_h = inferred_dims
            if not resolved_video_width and inferred_w:
                resolved_video_width = int(inferred_w)
            if not resolved_video_height and inferred_h:
                resolved_video_height = int(inferred_h)
            if resolved_video_width and resolved_video_height and not resolved_video_resolution:
                resolved_video_resolution = f"{int(resolved_video_width)}x{int(resolved_video_height)}"

    try:
        duration_raw = float(duration) if duration is not None else 5.0
    except Exception:
        duration_raw = 5.0
    est_duration = max(5, int(duration_raw)) if duration_raw > 0 else 5

    if has_video_input is None:
        has_video = bool(
            use_prev_video
            or (isinstance(ref_video_urls, (list, tuple)) and len(ref_video_urls) > 0)
        )
    else:
        has_video = bool(has_video_input)

    in_duration = None
    try:
        raw_in = input_duration_seconds if input_duration_seconds is not None else input_duration
        if raw_in is not None and float(raw_in) > 0:
            in_duration = float(raw_in)
    except Exception:
        in_duration = None

    is_token_billing = (
        (not is_per_second_video_provider(reserve_provider))
        and billing_service.is_token_pricing(db, "video_gen", reserve_provider, reserve_model)
    )

    details: Dict[str, Any] = {
        "billing_mode": mode_text,
        "duration": duration_raw if duration_raw > 0 else est_duration,
        "duration_seconds": est_duration,
        "estimated_duration": est_duration,
        "draft_mode": is_draft,
        "draft": is_draft,
        "use_prev_video": bool(use_prev_video),
        "shot_continuation": bool(use_prev_video),
        "has_video_input": bool(has_video),
        "function_name": fn_name,
        "aspect_ratio": aspect,
    }
    if in_duration is not None:
        details["input_duration_seconds"] = float(in_duration)
        details["input_duration"] = float(in_duration)
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
    if _to_positive_int_or_none(episode_id):
        details["episode_id"] = int(episode_id)
    if _to_positive_int_or_none(shot_id):
        details["shot_id"] = int(shot_id)

    video_token_cfg: Dict[str, Any] = {}
    estimated_tokens = 0
    if is_token_billing:
        video_token_cfg = billing_service.resolve_video_token_config(db, reserve_provider, reserve_model) or {}
        reserve_width = int(resolved_video_width) if resolved_video_width else int(video_token_cfg.get("default_width", 1280))
        reserve_height = int(resolved_video_height) if resolved_video_height else int(video_token_cfg.get("default_height", 720))
        reserve_fps = int(video_token_cfg.get("default_fps", 24))
        draft_coeff = float(video_token_cfg.get("draft_token_coefficient", 1.0) or 1.0)
        if not (0 < draft_coeff):
            draft_coeff = 1.0
        is_seedance_2 = bool(video_token_cfg.get("is_seedance_2")) or billing_service.is_seedance_2_model(
            reserve_provider, reserve_model
        )
        token_estimate = billing_service.estimate_video_token_usage(
            width=reserve_width,
            height=reserve_height,
            fps=reserve_fps,
            output_duration_seconds=est_duration,
            has_video_input=bool(has_video),
            input_duration_seconds=in_duration,
            draft_token_coefficient=draft_coeff,
            method=("seedance2_video_token_formula" if is_seedance_2 else "video_token_formula"),
        )
        estimated_tokens = int(token_estimate.get("tokens") or 0)
        details.update({
            "output_tokens": estimated_tokens,
            "total_tokens": estimated_tokens,
            "estimation_method": token_estimate.get("estimation_method") or "video_token_formula",
            "video_token_branch": "seedance2" if is_seedance_2 else "fallback",
            "video_token_estimate": token_estimate,
            "width": reserve_width,
            "height": reserve_height,
            "fps": reserve_fps,
            "input_duration_seconds": token_estimate.get("input_duration_seconds") or in_duration,
            "is_seedance_2": bool(is_seedance_2),
            "draft_token_coefficient": draft_coeff,
        })

    if isinstance(extra_details, dict) and extra_details:
        for key, value in extra_details.items():
            if value is not None and key not in details:
                details[key] = value
            elif value is not None and key in (
                "has_audio", "mode", "generation_mode", "sound",
            ):
                details[key] = value

    meta: Dict[str, Any] = {
        "resolved_provider": reserve_provider,
        "resolved_model": reserve_model,
        "resolved_system_api_id": reserve_system_api_id,
        "is_token_billing": bool(is_token_billing),
        "aspect_ratio": aspect,
        "width": details.get("width"),
        "height": details.get("height"),
        "resolution": details.get("resolution"),
        "image_size": details.get("image_size"),
        "duration_seconds": est_duration,
        "has_video_input": bool(has_video),
        "input_duration_seconds": details.get("input_duration_seconds"),
        "draft_mode": is_draft,
        "estimated_tokens": int(estimated_tokens or 0),
        "video_token_cfg": video_token_cfg,
        "is_seedance_2": bool(details.get("is_seedance_2")),
        "draft_token_coefficient": details.get("draft_token_coefficient"),
        "runtime_target": runtime_target,
    }
    return details, meta
