# -*- coding: utf-8 -*-
"""Image generation runner + async job wrapper."""
from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time_utils import now_bj_iso
from app.db.session import SessionLocal
from app.models.all_models import Entity, Project, User
from app.schemas.generation import GenerationRequest
from app.services.billing_service import billing_service
from app.services.db_session_utils import _release_db_connection, _snapshot_user_principal
from app.services.generation_runtime.api_capabilities import (
    _limit_media_ref_input,
    _limit_string_list_input,
    _map_resolution_to_allowed,
    _map_text_value_to_allowed,
    _read_api_capability_bool,
    _read_api_capability_int,
    _read_api_capability_list,
    _read_api_capability_number,
)
from app.services.generation_runtime.asset_registration import (
    _bind_generated_media_to_entity,
    _bind_generated_media_to_shot,
    _log_api_switch_regenerate_if_needed,
    _normalize_entity_type,
    _register_asset_helper,
)
from app.services.generation_runtime.callback_http import (
    _dispatch_generation_callback,
    _resolve_callback_url_from_payload,
)
from app.services.generation_runtime.callbacks import (
    _extract_job_provider_task_id,
    _is_ambiguous_image_submit_detail,
    _merge_provider_task_ids_into_settle,
    _normalize_generation_status,
)
from app.services.generation_runtime.generation_errors import _format_generation_failure_detail
from app.services.generation_runtime.generation_filename import _build_generation_filename_base
from app.services.generation_runtime.job_store import (
    IMAGE_JOB_LOCK,
    IMAGE_JOB_STORE,
    IMAGE_JOB_TASKS,
    _extract_job_result_url,
    _set_image_job,
    _set_video_job,
)
from app.services.generation_runtime.media_persist import (
    _is_provider_direct_oss_url,
    _oss_upload_succeeded_for_url,
    _persist_data_uri_image_result,
    _persist_remote_image_result,
    _resolve_media_bind_url,
)
from app.services.generation_runtime.media_runtime_target import _resolve_media_runtime_target
from app.services.generation_runtime.project_generation_context import (
    _ensure_project_generation_seed,
    _resolve_effective_negative_prompt,
    _resolve_project_id_for_generation,
    _should_hit_visual_breakpoint,
    _normalize_seed_value,
)
from app.services.generation_runtime.queue_config_runtime import _is_pure_callback_mode_enabled
from app.services.generation_runtime.voice_planning import _clamp_float
from app.services.model_invocation_billing import (
    _extract_provider_usage_from_metadata,
    _maybe_refresh_kie_credits_from_record_info,
    _resolve_usage_token_total,
)
from app.services.media_service import media_service
from app.services.project_visual_resolution import (
    infer_project_resolution as _infer_project_resolution,
    normalize_project_image_size as _normalize_project_image_size,
    parse_aspect_ratio_pair as _parse_aspect_ratio_pair,
)
from app.services.script_mode_helpers import _log_shot_submit_debug
from app.services.user_model_preferences import _normalize_cfg, _read_user_advanced_model_preferences

logger = logging.getLogger("api_logger")


def _ensure_project_generation_defaults(global_info: Any) -> Dict[str, Any]:
    # Lazy import to avoid circular import with workspace.shared at module load.
    from app.api.routers.workspace.shared import _ensure_project_generation_defaults as _fn
    return _fn(global_info)


async def _run_generate_image(
    req: GenerationRequest,
    current_user: User,
    db: Session,
    job_progress_callback: Any = None,
    job_id: Optional[str] = None,
    provider_callback_ticket: Optional[str] = None,
    provider_callback_url: Optional[str] = None,
    force_pure_callback_mode: bool = False,
    provider_payload_callback: Any = None,
):
    reservation_tx = None
    reservation_tx_id: Optional[int] = None
    runtime_target = _resolve_media_runtime_target(
        provider=req.provider,
        model=req.model,
        media_type="image",
        category="Image",
        user_id=current_user.id,
        user_credits=(current_user.credits or 0),
        function_name=getattr(req, "function_name", None),
        system_api_id=getattr(req, "system_api_id", None),
    )
    runtime_llm_config = dict(runtime_target.get("runtime_llm_config") or {})
    pre_api_cfg = runtime_target.get("pre_api_cfg") or {}
    if isinstance(pre_api_cfg, dict) and pre_api_cfg:
        runtime_llm_config["__pre_resolved_api_config"] = dict(pre_api_cfg)
    reserve_provider = runtime_target.get("resolved_provider")
    reserve_model = runtime_target.get("resolved_model")
    reserve_system_api_id = runtime_target.get("resolved_system_api_id")
    image_task_type = "image_gen"
    is_token_billing = billing_service.is_token_pricing(db, image_task_type, reserve_provider, reserve_model)
    estimated_total_tokens = 0

    if is_token_billing:
        est_messages = [{"role": "user", "content": str(req.prompt or "")}]
        est_usage = billing_service.estimate_input_output_tokens_from_messages(est_messages, output_ratio=1.2)
        estimated_total_tokens = int(est_usage.get("total_tokens") or 0)
        reserve_details = {
            "input_tokens": int(est_usage.get("input_tokens") or 0),
            "output_tokens": int(est_usage.get("output_tokens") or 0),
            "total_tokens": estimated_total_tokens,
            "billing_mode": "RESERVE",
            "estimation_method": "image_prompt_tokens",
        }
    else:
        reserve_details = {
            "item": "image",
            "image_count": 1,
            "billing_mode": "RESERVE",
        }

    if reserve_provider:
        reserve_details["provider"] = reserve_provider
        reserve_details["resolved_provider"] = reserve_provider
    if reserve_model:
        reserve_details["model"] = reserve_model
        reserve_details["resolved_model"] = reserve_model
    if reserve_system_api_id is not None:
        reserve_details["system_api_id"] = reserve_system_api_id
        reserve_details["resolved_system_api_id"] = reserve_system_api_id
    if req.project_id:
        reserve_details["project_id"] = int(req.project_id)
    if req.episode_id:
        reserve_details["episode_id"] = int(req.episode_id)

    reservation_tx = billing_service.reserve_credits(
        db,
        current_user.id,
        image_task_type,
        reserve_provider,
        reserve_model,
        reserve_details,
    )
    try:
        reservation_tx_id = int(getattr(reservation_tx, "id", 0) or 0) or None
    except Exception:
        reservation_tx_id = None

    try:
        resolved_project_id = _normalize_seed_value(getattr(req, "project_id", None))
        project_seed = _ensure_project_generation_seed(db, resolved_project_id, current_user)

        # 1. Resolve Context for Resolution/Ratio
        def _safe_json_dict(value: Any) -> Dict[str, Any]:
            if isinstance(value, dict):
                return value
            if isinstance(value, str):
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, dict):
                        return parsed
                except Exception:
                    return {}
            return {}

        def _pick_visual_from_info(info: Dict[str, Any]) -> Dict[str, Any]:
            if not isinstance(info, dict):
                return {}

            defaults = info.get("project_generation_defaults") if isinstance(info.get("project_generation_defaults"), dict) else {}
            tech = info.get("tech_params") if isinstance(info.get("tech_params"), dict) else {}
            vis = tech.get("visual_standard") if isinstance(tech.get("visual_standard"), dict) else {}

            out: Dict[str, Any] = {
                "aspect_ratio": vis.get("aspect_ratio") or vis.get("aspectRatio") or defaults.get("aspect_ratio") or defaults.get("aspectRatio") or info.get("aspect_ratio") or info.get("aspectRatio"),
                "width": vis.get("horizontal_resolution") or vis.get("horizontalResolution") or vis.get("h_resolution") or vis.get("width") or defaults.get("horizontal_resolution") or defaults.get("horizontalResolution") or info.get("horizontal_resolution") or info.get("horizontalResolution") or info.get("h_resolution") or info.get("width"),
                "height": vis.get("vertical_resolution") or vis.get("verticalResolution") or vis.get("v_resolution") or vis.get("height") or defaults.get("vertical_resolution") or defaults.get("verticalResolution") or info.get("vertical_resolution") or info.get("verticalResolution") or info.get("v_resolution") or info.get("height"),
                "image_size": vis.get("image_size") or vis.get("imageSize") or defaults.get("image_size") or defaults.get("imageSize") or defaults.get("image_resolution") or defaults.get("imageResolution") or info.get("image_size") or info.get("imageSize"),
                "resolution": vis.get("resolution") or defaults.get("resolution") or defaults.get("image_resolution") or info.get("resolution"),
                "video_resolution": (
                    vis.get("video_resolution")
                    or defaults.get("video_resolution")
                    or info.get("video_resolution")
                ),
            }

            nested = info.get("e_global_info") if isinstance(info.get("e_global_info"), dict) else None
            if nested:
                nested_values = _pick_visual_from_info(nested)
                for key in ("aspect_ratio", "width", "height", "image_size", "video_resolution"):
                    if not out.get(key) and nested_values.get(key):
                        out[key] = nested_values.get(key)

            return out

        def _parse_resolution_dims(value: Any) -> Tuple[Optional[int], Optional[int]]:
            text = str(value or "").strip().lower().replace(" ", "")
            if not text:
                return (None, None)
            match = re.match(r"^(\d{2,5})[x\*](\d{2,5})$", text)
            if not match:
                return (None, None)
            try:
                w = int(match.group(1))
                h = int(match.group(2))
            except Exception:
                return (None, None)
            if w <= 0 or h <= 0:
                return (None, None)
            return (w, h)

        def _infer_ratio_from_dims(width_value: Any, height_value: Any) -> Optional[str]:
            try:
                w = int(width_value)
                h = int(height_value)
            except Exception:
                return None
            if w <= 0 or h <= 0:
                return None

            target_ratio = float(w) / float(h)
            ratio_candidates = [
                "1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3",
                "5:4", "4:5", "21:9", "9:21", "2:1", "1:2", "3:1", "1:3",
            ]
            best_ratio = None
            best_distance = None
            for candidate in ratio_candidates:
                pair = _parse_aspect_ratio_pair(candidate)
                if not pair:
                    continue
                rw, rh = pair
                if rw <= 0 or rh <= 0:
                    continue
                candidate_ratio = float(rw) / float(rh)
                distance = abs(math.log(target_ratio) - math.log(candidate_ratio))
                if best_distance is None or distance < best_distance:
                    best_distance = distance
                    best_ratio = candidate
            return best_ratio

        def _get_asset_image_ratio_config_local() -> Dict[str, str]:
            default_cfg = {
                "subject_aspect_ratio": "16:9",
                "cover_aspect_ratio": "3:4",
            }
            try:
                row = db.execute(text("""
                    SELECT config
                    FROM system_api_settings
                    WHERE category = :category
                      AND provider = :provider
                      AND model = :model
                    ORDER BY id DESC
                    LIMIT 1
                """), {
                    "category": "System_Payment",
                    "provider": "agent_policy",
                    "model": "tool_acl",
                }).mappings().first()
                raw_config = row.get("config") if row else {}
                top_level = _safe_json_dict(raw_config)
                ratio_cfg = _safe_json_dict(top_level.get("asset_image_ratio_config", {}))
                subject_ratio = str(ratio_cfg.get("subject_aspect_ratio") or "").strip()
                cover_ratio = str(ratio_cfg.get("cover_aspect_ratio") or "").strip()
                if subject_ratio:
                    default_cfg["subject_aspect_ratio"] = subject_ratio
                if cover_ratio:
                    default_cfg["cover_aspect_ratio"] = cover_ratio
            except Exception as exc:
                logger.warning("[GenerateImage] failed to load asset image ratio config: %s", exc)
            return default_cfg

        req_aspect_ratio = str(getattr(req, "aspect_ratio", "") or "").strip() or None
        request_meta = _safe_json_dict(
            getattr(req, "metadata", None)
            or getattr(req, "meta_info", None)
            or getattr(req, "meta", None)
        )
        asset_type = str(getattr(req, "asset_type", "") or "").strip().lower()
        is_subject_generation = asset_type == "subject"
        is_cover_generation = asset_type in {"cover", "poster", "project_cover", "cover_image"}
        resolved_subject_type = _normalize_entity_type(
            getattr(req, "subject_type", None)
            or getattr(req, "entity_type", None)
            or request_meta.get("subject_type")
            or request_meta.get("entity_type")
        )
        aspect_ratio = req_aspect_ratio
        width = None
        height = None
        image_size = _normalize_project_image_size(req.image_size)
        if not image_size:
            image_size = None
        project_global_info: Dict[str, Any] = {}
        asset_ratio_config = _get_asset_image_ratio_config_local()

        if is_subject_generation:
            configured_subject_ratio = str(asset_ratio_config.get("subject_aspect_ratio") or "").strip()
            if configured_subject_ratio:
                aspect_ratio = configured_subject_ratio
        elif is_cover_generation:
            configured_cover_ratio = str(asset_ratio_config.get("cover_aspect_ratio") or "").strip()
            if configured_cover_ratio:
                aspect_ratio = configured_cover_ratio

        # Only read project-level realtime config for visual params.
        if resolved_project_id:
            project = db.query(Project).filter(Project.id == resolved_project_id).first()
            if project:
                project_global_info = _ensure_project_generation_defaults(_safe_json_dict(project.global_info))
                gi_basic_info = project_global_info.get("basic_info") or {}
                project_type = gi_basic_info.get("type") or project_global_info.get("type") or ""
                if project_type:
                    project_type_prefix = f"项目视觉类型：{project_type}"
                    if not req.prompt:
                        req.prompt = project_type_prefix
                    elif project_type_prefix not in req.prompt:
                        req.prompt = f"{project_type_prefix}\n{req.prompt}"

        project_visual = _pick_visual_from_info(project_global_info)

        # Fill remaining blanks with project-level defaults.
        is_keyframe_generation = asset_type in {"keyframe", "shot", "start_frame", "end_frame", "shot_image"}
        if not aspect_ratio and project_visual.get("aspect_ratio"):
            aspect_ratio = str(project_visual.get("aspect_ratio")).strip() or None
        if not image_size:
            raw_size = _normalize_project_image_size(project_visual.get("image_size"))
            if raw_size:
                image_size = raw_size
            
        if not is_keyframe_generation:
            if not width and project_visual.get("width"):
                width = project_visual.get("width")
            if not height and project_visual.get("height"):
                height = project_visual.get("height")

            # Compatibility: support resolution strings like "1920x1080" from project/episode defaults.
            if not width or not height:
                resolution_candidates = [
                    project_visual.get("resolution"),
                    project_global_info.get("resolution"),
                    project_global_info.get("image_resolution"),
                ]
                for candidate in resolution_candidates:
                    parsed_w, parsed_h = _parse_resolution_dims(candidate)
                    if parsed_w and parsed_h:
                        if not width:
                            width = parsed_w
                        if not height:
                            height = parsed_h
                        if not image_size:
                            long_side = max(parsed_w, parsed_h)
                            if long_side >= 3200:
                                image_size = "4K"
                            elif long_side >= 2200:
                                image_size = "2K"
                            elif long_side >= 1200:
                                image_size = "2K"
                            else:
                                image_size = "0.5K"
                        break

        if (not width or not height) and aspect_ratio and image_size:
            inferred_dims = _infer_project_resolution(aspect_ratio, image_size)
            if inferred_dims:
                inferred_w, inferred_h = inferred_dims
                if not width:
                    width = inferred_w
                if not height:
                    height = inferred_h

        # Cast to int for safety, but allow None for keyframes to use API defaults
        try: width = int(width) if width else (None if is_keyframe_generation else 720)
        except: width = None if is_keyframe_generation else 720
        try: height = int(height) if height else (None if is_keyframe_generation else 1080)
        except: height = None if is_keyframe_generation else 1080

        # Keep ratio consistent with resolved dimensions when they exist.
        # This avoids stale/default aspect_ratio (for example subject default 16:9)
        # overriding portrait project resolutions such as 1440x2560.
        if not is_keyframe_generation and not is_subject_generation and width and height:
            inferred_ratio = _infer_ratio_from_dims(width, height)
            if inferred_ratio:
                current_ratio_pair = _parse_aspect_ratio_pair(aspect_ratio) if aspect_ratio else None
                ratio_mismatch = False
                if not current_ratio_pair:
                    ratio_mismatch = True
                else:
                    try:
                        current_ratio_value = float(current_ratio_pair[0]) / float(current_ratio_pair[1])
                        target_ratio_value = float(width) / float(height)
                        ratio_mismatch = abs(math.log(current_ratio_value) - math.log(target_ratio_value)) > 0.08
                    except Exception:
                        ratio_mismatch = True

                if ratio_mismatch:
                    logger.warning(
                        "[GenerateImage] Aspect ratio corrected by dimensions | project_id=%s old_ratio=%s width=%s height=%s new_ratio=%s",
                        resolved_project_id,
                        aspect_ratio,
                        width,
                        height,
                        inferred_ratio,
                    )
                    aspect_ratio = inferred_ratio

        if not image_size and not is_keyframe_generation:
            max_side = max(width or 0, height or 0)
            if max_side >= 3200:
                image_size = "4K"
            elif max_side >= 2200:
                image_size = "2K"
            elif max_side >= 1200:
                image_size = "2K"
            else:
                image_size = "0.5K"

        logger.info(f"[GenerateImage] Context Params - AR: {aspect_ratio}, W: {width}, H: {height}, image_size: {image_size}, project_id: {resolved_project_id}")
        logger.info(
            "[GenerateImage] Project Visual Extract | project_id=%s project_keys=%s picked=%s",
            resolved_project_id,
            sorted(list(project_global_info.keys()))[:30] if isinstance(project_global_info, dict) else [],
            {
                "aspect_ratio": aspect_ratio,
                "width": width,
                "height": height,
                "image_size": image_size,
                "raw_project_visual": project_visual,
            },
        )

        if _should_hit_visual_breakpoint("image", resolved_project_id):
            logger.warning(
                "[GenerateImage] BREAKPOINT hit | project_id=%s aspect_ratio=%s width=%s height=%s image_size=%s raw_project_visual=%s",
                resolved_project_id,
                aspect_ratio,
                width,
                height,
                image_size,
                project_visual,
            )
        _log_shot_submit_debug(
            "image_submit",
            req,
            refs=req.ref_image_url,
            extra={
                "aspect_ratio": aspect_ratio,
                "width": width,
                "height": height,
                "image_size": image_size,
                "resolved_project_id": resolved_project_id,
                "project_seed": project_seed,
                "user_id": current_user.id,
            },
        )

        # Ensure the current DB transaction/connection is fully released before long upstream call.
        _release_db_connection(db, "generate_image_upstream_call")

        image_provider_options: Dict[str, Any] = {}
        explicit_seed = _normalize_seed_value(getattr(req, "seed", None))
        user_advanced = _read_user_advanced_model_preferences(current_user)
        effective_cfg = _normalize_cfg(getattr(req, "cfg", None))
        if effective_cfg is None:
            effective_cfg = _normalize_cfg(user_advanced.get("cfg"))

        cfg_supported = _read_api_capability_bool(
            pre_api_cfg,
            "supports_cfg",
            "cfg_supported",
        )
        if cfg_supported is False:
            effective_cfg = None
        elif effective_cfg is not None:
            cfg_min = _read_api_capability_number(pre_api_cfg, "cfg_min")
            cfg_max = _read_api_capability_number(pre_api_cfg, "cfg_max")
            effective_cfg = _clamp_float(
                effective_cfg,
                float(cfg_min) if cfg_min is not None else 0.0,
                float(cfg_max) if cfg_max is not None else 2.0,
                float(cfg_min) if cfg_min is not None else 1.0,
            )
        if explicit_seed:
            image_provider_options["seed"] = int(explicit_seed)
            image_provider_options["seeds"] = int(explicit_seed)
        elif project_seed:
            image_provider_options["seed"] = int(project_seed)
            image_provider_options["seeds"] = int(project_seed)

        if effective_cfg is not None:
            image_provider_options["cfg"] = float(effective_cfg)
            image_provider_options["cfg_scale"] = float(effective_cfg)

        if req.mode is not None:
            image_mode = str(req.mode).strip().lower()
            if image_mode:
                image_provider_options["mode"] = image_mode

        allowed_image_modes = _read_api_capability_list(
            pre_api_cfg,
            "mode_values",
            "mode",
            "allowed_modes",
            "supported_modes",
        )
        if image_provider_options.get("mode") is not None and allowed_image_modes:
            image_provider_options["mode"] = _map_text_value_to_allowed(
                image_provider_options.get("mode"),
                allowed_image_modes,
            )

        allowed_image_aspect_ratios = _read_api_capability_list(
            pre_api_cfg,
            "aspect_ratio_values",
            "aspect_ratios",
            "aspect_ratio",
            "allowed_aspect_ratios",
            "supported_aspect_ratios",
        )
        if aspect_ratio and allowed_image_aspect_ratios:
            aspect_ratio = _map_text_value_to_allowed(aspect_ratio, allowed_image_aspect_ratios)

        allowed_image_sizes = _read_api_capability_list(
            pre_api_cfg,
            "image_size_values",
            "image_sizes",
            "image_size",
            "allowed_image_sizes",
            "supported_image_sizes",
        )
        if image_size and allowed_image_sizes:
            image_size = _map_text_value_to_allowed(image_size, allowed_image_sizes)

        allowed_image_qualities = _read_api_capability_list(
            pre_api_cfg,
            "quality_values",
            "qualities",
            "quality_levels",
            "allowed_qualities",
            "supported_qualities",
        )
        image_quality = str(req.quality or "").strip().lower() or None
        if image_quality and allowed_image_qualities:
            image_quality = _map_text_value_to_allowed(image_quality, allowed_image_qualities)

        allowed_output_formats = _read_api_capability_list(
            pre_api_cfg,
            "output_format_values",
            "output_formats",
            "allowed_output_formats",
            "supported_output_formats",
        )
        output_format = str(req.output_format or req.outputFormat or "").strip().lower() or None
        if output_format and allowed_output_formats:
            output_format = _map_text_value_to_allowed(output_format, allowed_output_formats)

        allowed_response_formats = _read_api_capability_list(
            pre_api_cfg,
            "response_format_values",
            "response_formats",
            "allowed_response_formats",
            "supported_response_formats",
        )
        response_format = str(req.response_format or req.responseFormat or "").strip().lower() or None
        if response_format and allowed_response_formats:
            response_format = _map_text_value_to_allowed(response_format, allowed_response_formats)

        allowed_output_compressions = _read_api_capability_list(
            pre_api_cfg,
            "output_compression_values",
            "output_compressions",
            "allowed_output_compressions",
            "supported_output_compressions",
        )
        output_compression = str(req.output_compression or req.outputCompression or "").strip().lower() or None
        if output_compression and allowed_output_compressions:
            output_compression = _map_text_value_to_allowed(output_compression, allowed_output_compressions)

        allowed_backgrounds = _read_api_capability_list(
            pre_api_cfg,
            "background_values",
            "backgrounds",
            "allowed_backgrounds",
            "supported_backgrounds",
        )
        image_background = str(req.background or "").strip().lower() or None
        if image_background and allowed_backgrounds:
            image_background = _map_text_value_to_allowed(image_background, allowed_backgrounds)

        allowed_image_resolutions = _read_api_capability_list(
            pre_api_cfg,
            "supported_resolutions",
            "resolution_values",
            "resolution",
            "allowed_resolutions",
        )
        if width and height and allowed_image_resolutions:
            mapped_resolution = _map_resolution_to_allowed(f"{int(width)}x{int(height)}", allowed_image_resolutions)
            parsed_w, parsed_h = _parse_resolution_dims(mapped_resolution)
            if parsed_w and parsed_h:
                width = int(parsed_w)
                height = int(parsed_h)

        image_ref_limit = _read_api_capability_int(
            pre_api_cfg,
            "reference_image_limit",
            "max_reference_images",
            "max_image_refs",
        )
        max_images_per_call = _read_api_capability_int(
            pre_api_cfg,
            "max_images_per_call",
            "max_images",
            "image_num_limit",
        )
        if image_ref_limit is not None:
            req.ref_image_url = _limit_media_ref_input(req.ref_image_url, image_ref_limit)

        if isinstance(req.files_url, list):
            image_provider_options["filesUrl"] = _limit_string_list_input(req.files_url, image_ref_limit)
        elif isinstance(req.filesUrl, list):
            image_provider_options["filesUrl"] = _limit_string_list_input(req.filesUrl, image_ref_limit)

        if isinstance(req.image_urls, list):
            image_provider_options["image_urls"] = _limit_string_list_input(req.image_urls, image_ref_limit)
        elif isinstance(req.imageUrls, list):
            image_provider_options["image_urls"] = _limit_string_list_input(req.imageUrls, image_ref_limit)

        if image_quality:
            image_provider_options["quality"] = image_quality

        if output_format:
            image_provider_options["output_format"] = output_format

        if response_format:
            image_provider_options["response_format"] = response_format

        if output_compression:
            image_provider_options["output_compression"] = output_compression

        if image_background:
            image_provider_options["background"] = image_background

        file_url_candidate = str(req.file_url or req.fileUrl or "").strip()
        if file_url_candidate:
            image_provider_options["fileUrl"] = file_url_candidate

        mask_url_candidate = str(req.mask_url or req.maskUrl or "").strip()
        supports_mask = _read_api_capability_bool(pre_api_cfg, "supports_mask", "mask_supported")
        if mask_url_candidate and supports_mask is not False:
            image_provider_options["maskUrl"] = mask_url_candidate

        if req.is_enhance is not None:
            image_provider_options["isEnhance"] = bool(req.is_enhance)
        elif req.isEnhance is not None:
            image_provider_options["isEnhance"] = bool(req.isEnhance)

        if req.upload_cn is not None:
            image_provider_options["uploadCn"] = bool(req.upload_cn)
        elif req.uploadCn is not None:
            image_provider_options["uploadCn"] = bool(req.uploadCn)

        if callable(job_progress_callback):
            image_provider_options["_grsai_task_id_callback"] = job_progress_callback
            image_provider_options["_provider_task_id_callback"] = job_progress_callback
        if callable(provider_payload_callback):
            image_provider_options["_provider_payload_callback"] = provider_payload_callback
        if provider_callback_ticket:
            image_provider_options["_provider_callback_ticket"] = str(provider_callback_ticket).strip()
        if provider_callback_url:
            image_provider_options["_provider_callback_url"] = str(provider_callback_url).strip()
        if (force_pure_callback_mode or _is_pure_callback_mode_enabled()) and provider_callback_ticket and provider_callback_url:
            image_provider_options["_pure_callback_mode"] = True
        image_provider_options["_request_user_id"] = int(current_user.id)
        if _build_generation_filename_base(req, db):
            image_provider_options["_request_filename_base"] = _build_generation_filename_base(req, db)

        if req.enable_fallback is not None:
            image_provider_options["enableFallback"] = bool(req.enable_fallback)
        elif req.enableFallback is not None:
            image_provider_options["enableFallback"] = bool(req.enableFallback)

        fallback_model_candidate = str(req.fallback_model or req.fallbackModel or "").strip()
        if fallback_model_candidate:
            image_provider_options["fallbackModel"] = fallback_model_candidate

        if is_subject_generation and resolved_subject_type:
            subject_entity = None
            entity_id_hint = getattr(req, "entity_id", None)
            if entity_id_hint not in (None, ""):
                try:
                    subject_entity = db.query(Entity).filter(Entity.id == int(entity_id_hint)).first()
                except Exception:
                    subject_entity = None
            image_provider_options["__subject_type"] = resolved_subject_type
            image_provider_options["__asset_type"] = "subject"
            if getattr(req, "entity_id", None) not in (None, ""):
                image_provider_options["__entity_id"] = getattr(req, "entity_id", None)
            if getattr(req, "project_id", None) not in (None, ""):
                image_provider_options["__project_id"] = getattr(req, "project_id", None)
            if getattr(req, "episode_id", None) not in (None, ""):
                image_provider_options["__episode_id"] = getattr(req, "episode_id", None)
            if getattr(req, "scene_id", None) not in (None, ""):
                image_provider_options["__scene_id"] = getattr(req, "scene_id", None)
            if getattr(req, "shot_id", None) not in (None, ""):
                image_provider_options["__shot_id"] = getattr(req, "shot_id", None)
            subject_name_hint = str(
                getattr(req, "subject_name", None)
                or getattr(req, "entity_name", None)
                or request_meta.get("subject_name")
                or request_meta.get("entity_name")
                or ""
            ).strip()
            if subject_name_hint:
                image_provider_options["__subject_name"] = subject_name_hint
            entity_name_hint = str(
                getattr(req, "entity_name", None)
                or request_meta.get("entity_name")
                or subject_name_hint
                or ""
            ).strip()
            if entity_name_hint:
                image_provider_options["__entity_name"] = entity_name_hint
            entity_type_hint = str(
                getattr(req, "entity_type", None)
                or request_meta.get("entity_type")
                or resolved_subject_type
                or ""
            ).strip()
            if entity_type_hint:
                image_provider_options["__entity_type"] = entity_type_hint
            subject_name_ascii = str(
                getattr(subject_entity, "name_en", None)
                or request_meta.get("subject_name_en")
                or request_meta.get("entity_name_en")
                or ""
            ).strip()
            if subject_name_ascii:
                image_provider_options["__subject_name_ascii"] = subject_name_ascii
            entity_name_ascii = str(
                getattr(subject_entity, "name_en", None)
                or request_meta.get("entity_name_en")
                or request_meta.get("subject_name_en")
                or ""
            ).strip()
            if entity_name_ascii:
                image_provider_options["__entity_name_ascii"] = entity_name_ascii
            logger.info(
                "[GenerateImageSubject] request_context user_id=%s asset_type=%s entity_id=%s entity_name=%s subject_name=%s subject_name_ascii=%s subject_type=%s project_id=%s scene_id=%s shot_id=%s",
                getattr(current_user, "id", None),
                image_provider_options.get("__asset_type"),
                image_provider_options.get("__entity_id"),
                image_provider_options.get("__entity_name"),
                image_provider_options.get("__subject_name"),
                image_provider_options.get("__subject_name_ascii"),
                image_provider_options.get("__subject_type"),
                image_provider_options.get("__project_id"),
                image_provider_options.get("__scene_id"),
                image_provider_options.get("__shot_id"),
            )

        if max_images_per_call is not None:
            files_urls = image_provider_options.get("filesUrl")
            if isinstance(files_urls, list):
                image_provider_options["filesUrl"] = files_urls[:max_images_per_call]
            image_urls = image_provider_options.get("image_urls")
            if isinstance(image_urls, list):
                image_provider_options["image_urls"] = image_urls[:max_images_per_call]

        effective_negative_prompt, negative_prompt_source = _resolve_effective_negative_prompt(
            req.negative_prompt,
            req.asset_type,
            "image",
        )

        # Assuming generate_image returns {"url": "...", ...}
        result = await media_service.generate_image(
            prompt=req.prompt, 
            negative_prompt=effective_negative_prompt,
            llm_config=runtime_llm_config,
            reference_image_url=req.ref_image_url,
            width=width,
            height=height,
            image_size=image_size,
            aspect_ratio=aspect_ratio,
            user_id=current_user.id,
            user_credits=(current_user.credits or 0),
            filename_base=_build_generation_filename_base(req, db),
            asset_type=req.asset_type,
            provider_options=image_provider_options,
            skip_download=False,
        )

        if isinstance(result, dict):
            stable_meta = result.get("metadata")
            if not isinstance(stable_meta, dict):
                stable_meta = {}
            active_seed = explicit_seed or project_seed
            if active_seed:
                stable_meta.setdefault("seed", int(active_seed))
            if effective_negative_prompt:
                stable_meta["negative_prompt_submitted"] = effective_negative_prompt
            stable_meta["negative_prompt_source"] = negative_prompt_source
            result["metadata"] = stable_meta

        result_meta = result.get("metadata") if isinstance(result, dict) else {}
        if not isinstance(result_meta, dict):
            result_meta = {}
        if job_id:
            result_meta["idempotency_key"] = job_id
            if isinstance(result, dict):
                result["metadata"] = result_meta


        if job_id:
            result_meta["idempotency_key"] = job_id
            if isinstance(result, dict):
                result["metadata"] = result_meta

        smart_meta = result_meta.get("smart_routing") if isinstance(result_meta.get("smart_routing"), dict) else {}
        billing_provider = str(
            result_meta.get("provider")
            or smart_meta.get("provider")
            or reserve_provider
            or req.provider
            or ""
        ).strip() or None
        billing_model = str(
            result_meta.get("model")
            or smart_meta.get("model")
            or reserve_model
            or req.model
            or ""
        ).strip() or None
        billing_system_api_id = (
            result_meta.get("system_api_id")
            if result_meta.get("system_api_id") is not None
            else smart_meta.get("system_api_id")
        )
        try:
            billing_system_api_id = int(billing_system_api_id) if billing_system_api_id is not None else None
        except Exception:
            billing_system_api_id = None
        _log_shot_submit_debug(
            "image_submit_result",
            req,
            refs=req.ref_image_url,
            extra={
                "user_id": current_user.id,
                "submitted_provider": result_meta.get("provider"),
                "submitted_model": result_meta.get("model"),
                "submitted_aspect_ratio": result_meta.get("submit_aspect_ratio"),
            },
        )
        if "error" in result:
            detail = _format_generation_failure_detail(result, "Image generation failed")
            ambiguous_submit = bool((result or {}).get("ambiguous_submit"))
            status_code = 502 if ambiguous_submit else 400

            # Log full error for image gen
            logger.error(f"[GenerateImage] Failed: {detail}")
            billing_service.log_failed_transaction(db, current_user.id, "image_gen", billing_provider, billing_model, detail)

            if reservation_tx_id is not None:
                try:
                    billing_service.cancel_reservation(db, reservation_tx_id, detail)
                    reservation_tx = None
                    reservation_tx_id = None
                except Exception:
                    pass

            raise HTTPException(status_code=status_code, detail=detail)

        pending_callback_mode = bool(isinstance(result, dict) and result.get("pending_callback"))
        if pending_callback_mode:
            # Keep reservation open until provider callback finalizes success/failure.
            if reservation_tx_id is not None:
                result = dict(result)
                result["billing_pending"] = True
                result["reservation_tx_id"] = int(reservation_tx_id)
                result["billing_context"] = {
                    "is_token_billing": bool(is_token_billing),
                    "estimated_total_tokens": int(estimated_total_tokens or 0),
                    "width": int(width or 0) or None,
                    "height": int(height or 0) or None,
                    "aspect_ratio": str(aspect_ratio or "").strip() or None,
                    "image_size": str(image_size or "").strip() or None,
                    "provider": billing_provider or reserve_provider or req.provider,
                    "model": billing_model or reserve_model or req.model,
                    "system_api_id": billing_system_api_id if billing_system_api_id is not None else reserve_system_api_id,
                    "project_id": int(req.project_id) if req.project_id else None,
                    "episode_id": int(req.episode_id) if req.episode_id else None,
                    "shot_id": int(getattr(req, "shot_id", 0) or 0) or None,
                    "entity_id": int(getattr(req, "entity_id", 0) or 0) or None,
                    "asset_type": str(getattr(req, "asset_type", "") or "").strip() or None,
                }
                logger.info(
                    "[GenerateImage] callback pending; reservation kept open | reservation_tx_id=%s provider=%s model=%s",
                    reservation_tx_id,
                    billing_provider or reserve_provider,
                    billing_model or reserve_model,
                )
                reservation_tx = None
                reservation_tx_id = None
            return result

        _log_api_switch_regenerate_if_needed(
            db=db,
            current_user=current_user,
            req=req,
            result=result,
            media_type="image",
        )

        if reservation_tx_id is not None:
            if is_token_billing:
                usage = _extract_provider_usage_from_metadata(result_meta if isinstance(result_meta, dict) else {})
                api_tokens = _resolve_usage_token_total(usage)
                actual_total_tokens = api_tokens or int(estimated_total_tokens or 0)
                token_source = "api_usage" if api_tokens > 0 else "estimate"
                settle_details = {
                    "input_tokens": int((usage or {}).get("input_tokens") or (usage or {}).get("prompt_tokens") or 0),
                    "output_tokens": int((usage or {}).get("output_tokens") or (usage or {}).get("completion_tokens") or actual_total_tokens),
                    "total_tokens": actual_total_tokens,
                    "status": "SETTLED",
                    "billing_mode": "ACTUAL",
                    "token_source": token_source,
                }
            else:
                settle_details = {
                    "item": "image",
                    "image_count": 1,
                    "width": int(width or 0),
                    "height": int(height or 0),
                    "status": "SETTLED",
                    "billing_mode": "ACTUAL",
                }

                submitted_ar = str(result_meta.get("submit_aspect_ratio") or aspect_ratio or "").strip()
                if submitted_ar:
                    settle_details["aspect_ratio"] = submitted_ar

                submitted_quality = str(result_meta.get("submit_quality") or "").strip().lower()
                if submitted_quality:
                    settle_details["quality"] = submitted_quality

                submitted_image_count = result_meta.get("submit_image_count")
                try:
                    submitted_image_count = int(submitted_image_count) if submitted_image_count is not None else None
                except Exception:
                    submitted_image_count = None
                if submitted_image_count and submitted_image_count > 0:
                    settle_details["image_count"] = int(submitted_image_count)

            provider_usage = _extract_provider_usage_from_metadata(result_meta)
            if provider_usage:
                settle_details["provider_usage"] = provider_usage
                settle_details["usage_source"] = str(result_meta.get("usage_source") or "provider").strip() or "provider"

            # KIE non-callback: recordInfo data.creditsConsumed → actual supplier credits settle.
            try:
                from app.services.billing_pricing import resolve_provider_kie_credits

                _kie_credits = float(
                    resolve_provider_kie_credits(provider_usage)
                    or resolve_provider_kie_credits(result_meta if isinstance(result_meta, dict) else {})
                    or 0.0
                )
            except Exception:
                _kie_credits = 0.0
            if _kie_credits <= 0 and isinstance(result_meta, dict):
                _kie_credits = await _maybe_refresh_kie_credits_from_record_info(result_meta, billing_provider)
            if _kie_credits > 0:
                settle_details["kie_credits_consumed"] = _kie_credits
                settle_details["credits_consumed"] = _kie_credits
                settle_details["creditsConsumed"] = _kie_credits
                settle_details["billing_basis"] = "provider_kie_credits"
                settle_details.setdefault(
                    "provider_usage",
                    {
                        "creditsConsumed": _kie_credits,
                        "credits_consumed": _kie_credits,
                        "kie_credits_consumed": _kie_credits,
                        "credits": _kie_credits,
                    },
                )

            if billing_provider:
                settle_details["provider"] = billing_provider
            if billing_model:
                settle_details["model"] = billing_model
            if billing_system_api_id is not None:
                settle_details["system_api_id"] = billing_system_api_id
            if req.project_id:
                settle_details["project_id"] = int(req.project_id)
            if req.episode_id:
                settle_details["episode_id"] = int(req.episode_id)

            settle_details = _merge_provider_task_ids_into_settle(
                settle_details,
                result_meta if isinstance(result_meta, dict) else {},
                result if isinstance(result, dict) else {},
            )

            billing_service.settle_reservation(
                db,
                reservation_tx_id,
                settle_details,
            )
            reservation_tx = None
            reservation_tx_id = None
        
        # Register Asset
        if result.get("url"):
            temp_url = result.get("url")
            
            # If it's a base64 image, upload it synchronously first, to avoid sending giant base64 to frontend & db
            if temp_url.startswith("data:image/"):
                norm_url, norm_meta = await asyncio.to_thread(_persist_data_uri_image_result, current_user, temp_url, result.get("metadata"))
                if norm_url and norm_url != temp_url:
                    temp_url = norm_url
                    result["url"] = temp_url
                    if norm_meta is not None:
                        result["metadata"] = norm_meta

            request_mode = str(getattr(req, "mode", "") or "").strip().lower()

            result_meta_for_bind = dict(result.get("metadata") or {})
            skip_remote_localization = _is_provider_direct_oss_url(temp_url, result_meta_for_bind)
            if skip_remote_localization:
                result_meta_for_bind["provider_direct_oss_url"] = True
                result["metadata"] = result_meta_for_bind

            # Trigger background task for OSS upload only when the URL still needs localization.
            if temp_url.startswith("http") and not skip_remote_localization:
                if job_id:
                    _set_image_job(job_id, status="storing_asset")
                async def _bg_upload_and_update(user: User, req_obj: Any, raw_url: str, meta: Optional[dict] = None):
                    bg_db = SessionLocal()
                    try:
                        bg_user = bg_db.query(User).filter(User.id == user.id).first()
                        if not bg_user:
                            if job_id:
                                _set_image_job(job_id, status="succeeded", finished_at=now_bj_iso())
                            return
                        norm_url, norm_meta, oss_uploaded = await asyncio.to_thread(
                            _persist_remote_media_result,
                            bg_user,
                            raw_url,
                            meta,
                            filename_base=_build_generation_filename_base(req_obj, bg_db),
                        )

                        final_url = str(norm_url or raw_url).strip()
                        final_meta = dict(norm_meta if norm_meta is not None else (meta or {}))
                        if job_id:
                            final_meta["idempotency_key"] = job_id

                        bind_url, ephemeral_binding, final_meta = _resolve_media_bind_url(
                            raw_url=raw_url,
                            normalized_url=final_url,
                            normalized_meta=final_meta,
                        )
                        if bind_url:
                            await asyncio.to_thread(
                                _register_asset_helper,
                                bg_db,
                                bg_user.id,
                                bind_url,
                                req_obj,
                                final_meta,
                            )
                            if request_mode != "joint_diptych":
                                await asyncio.to_thread(
                                    _bind_generated_media_to_shot,
                                    bg_db,
                                    bg_user,
                                    req_obj,
                                    bind_url,
                                    bool(oss_uploaded and not ephemeral_binding),
                                    final_meta,
                                )
                                await asyncio.to_thread(
                                    _bind_generated_media_to_entity,
                                    bg_db,
                                    bg_user,
                                    req_obj,
                                    bind_url,
                                    bool(oss_uploaded and not ephemeral_binding),
                                )

                        if job_id and bind_url and bind_url != raw_url:
                            with IMAGE_JOB_LOCK:
                                _job_to_update = dict(IMAGE_JOB_STORE.get(job_id) or {})
                            if _job_to_update:
                                updated_res = dict(_job_to_update.get("result") or result)
                                updated_res["url"] = bind_url
                                if final_meta is not None:
                                    updated_res["metadata"] = final_meta
                                _set_image_job(job_id, result=updated_res, status="succeeded", finished_at=now_bj_iso())
                        elif job_id:
                            _set_image_job(job_id, status="succeeded", finished_at=now_bj_iso())
                    except Exception as e:
                        logger.error(f"[_bg_upload_and_update] failed for user={user.id} url={raw_url}: {e}")
                        if job_id:
                            _set_image_job(job_id, status="failed", error=str(e), finished_at=now_bj_iso())
                    finally:
                        bg_db.close()

                asyncio.create_task(_bg_upload_and_update(current_user, req, temp_url, result.get("metadata")))
            else:
                final_meta_sync = dict(result.get("metadata") or {})
                if job_id:
                    final_meta_sync["idempotency_key"] = job_id
                bind_url, ephemeral_binding, final_meta_sync = _resolve_media_bind_url(
                    raw_url=temp_url,
                    normalized_url=temp_url,
                    normalized_meta=final_meta_sync,
                )
                if bind_url:
                    await asyncio.to_thread(_register_asset_helper, db, current_user.id, bind_url, req, final_meta_sync)
                    if request_mode != "joint_diptych":
                        await asyncio.to_thread(
                            _bind_generated_media_to_shot,
                            db,
                            current_user,
                            req,
                            bind_url,
                            _oss_upload_succeeded_for_url(bind_url, final_meta_sync) and not ephemeral_binding,
                            final_meta_sync,
                        )
                        await asyncio.to_thread(
                            _bind_generated_media_to_entity,
                            db,
                            current_user,
                            req,
                            bind_url,
                            _oss_upload_succeeded_for_url(bind_url, final_meta_sync) and not ephemeral_binding,
                        )
                if job_id:
                    _set_image_job(job_id, status="succeeded", finished_at=now_bj_iso())

        return result
    except asyncio.CancelledError:
        if reservation_tx_id is not None:
            try:
                billing_service.cancel_reservation(db, reservation_tx_id, "image generation cancelled")
                reservation_tx_id = None
            except Exception:
                pass
        raise
    except HTTPException:
        if reservation_tx_id is not None:
            try:
                billing_service.cancel_reservation(db, reservation_tx_id, "image generation http exception")
                reservation_tx_id = None
            except Exception:
                pass
        # Keep an auditable failure record for submit-based async jobs.
        try:
            billing_service.log_failed_transaction(
                db,
                current_user.id,
                "image_gen",
                req.provider,
                req.model,
                "HTTPException in image generation pipeline",
                details={
                    "status": "FAILED",
                    "failure_stage": "image_generate_http_exception",
                },
            )
        except Exception:
            logger.exception("Failed to log image_gen HTTPException transaction")
        raise
    except Exception as e:
        if reservation_tx_id is not None:
            try:
                billing_service.cancel_reservation(db, reservation_tx_id, str(e))
                reservation_tx_id = None
            except Exception:
                pass
        billing_service.log_failed_transaction(db, current_user.id, "image_gen", req.provider, req.model, str(e))
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


# _set_image_job moved to app.services.generation_runtime.job_store


async def _run_generate_image_job(
    job_id: str,
    user_id: int,
    req_payload: Dict[str, Any],
    provider_callback_ticket: Optional[str] = None,
    provider_callback_url: Optional[str] = None,
) -> Dict[str, Any]:
    from app.services.generation_task_queue import mark_generation_task_status_external, patch_generation_task_payload

    db = SessionLocal()
    callback_url = _resolve_callback_url_from_payload(req_payload)
    req_provider = str(req_payload.get("provider") or "").strip() or None
    req_model = str(req_payload.get("model") or "").strip() or None

    def _on_provider_task_id(task_id: str) -> None:
        normalized_task_id = str(task_id or "").strip()
        if not normalized_task_id:
            return
        _set_image_job(job_id, provider_task_id=normalized_task_id)
        try:
            with IMAGE_JOB_LOCK:
                current = dict(IMAGE_JOB_STORE.get(job_id) or {})
            reservation_tx_id_for_task = int(current.get("reservation_tx_id") or 0) or None
            if reservation_tx_id_for_task:
                attach_db = SessionLocal()
                try:
                    billing_service.attach_provider_task_id_to_reservation(
                        attach_db,
                        reservation_tx_id_for_task,
                        normalized_task_id,
                    )
                finally:
                    attach_db.close()
        except Exception:
            logger.exception(
                "[ImageJob] persist provider taskId to reservation failed | job_id=%s provider_task_id=%s",
                job_id,
                normalized_task_id,
            )
        logger.info(
            "[ImageJob] provider task linked | job_id=%s provider=%s provider_task_id=%s",
            job_id,
            req_provider or "unknown",
            normalized_task_id,
        )

    def _on_provider_payload(payload_snapshot: Any) -> None:
        if not isinstance(payload_snapshot, dict):
            return
        try:
            import copy as _copy
            payload_snapshot = _copy.deepcopy(payload_snapshot)
        except Exception:
            payload_snapshot = dict(payload_snapshot)
        patch_generation_task_payload(
            job_id,
            {
                "combined_payload": payload_snapshot,
                "final_provider_payload": payload_snapshot,
                "final_provider_payload_at": now_bj_iso(),
            },
        )
        logger.info(
            "[ImageJob] final provider payload recorded | job_id=%s provider=%s model=%s",
            job_id,
            req_provider or "unknown",
            req_model or "unknown",
        )

    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            _set_image_job(
                job_id,
                status="failed",
                finished_at=now_bj_iso(),
                error="User not found",
            )
            mark_generation_task_status_external(job_id, status="failed", error="User not found")
            return {"defer_completion": False}
        user_principal = _snapshot_user_principal(user)

        req_obj = GenerationRequest(**req_payload)
        _set_image_job(job_id, status="submit", started_at=now_bj_iso())
        logger.info(
            "[ImageJob] started | job_id=%s user_id=%s provider=%s model=%s",
            job_id,
            user_id,
            req_provider,
            req_model,
        )
        _release_db_connection(db, "image_job_wait_for_generation")
        result = await asyncio.wait_for(
            _run_generate_image(
                req_obj,
                user_principal,
                db,
                job_progress_callback=_on_provider_task_id,
                job_id=job_id,
                provider_callback_ticket=provider_callback_ticket,
                provider_callback_url=provider_callback_url,
                force_pure_callback_mode=_is_pure_callback_mode_enabled(),
                provider_payload_callback=_on_provider_payload,
            ),
            timeout=IMAGE_JOB_MAX_RUNNING_SECONDS,
        )
        if isinstance(result, dict):
            result_meta = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
            resolved_provider = str((result_meta or {}).get("provider") or req_provider or "").strip() or None
            resolved_model = str((result_meta or {}).get("model") or req_model or "").strip() or None
            provider_update_fields: Dict[str, Any] = {}
            if resolved_provider:
                provider_update_fields["provider"] = resolved_provider
            if resolved_model:
                provider_update_fields["model"] = resolved_model
            if provider_update_fields:
                _set_video_job(job_id, **provider_update_fields)

        if isinstance(result, dict):
            result_meta = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
            resolved_provider = str((result_meta or {}).get("provider") or req_provider or "").strip() or None
            resolved_model = str((result_meta or {}).get("model") or req_model or "").strip() or None
            provider_update_fields: Dict[str, Any] = {}
            if resolved_provider:
                provider_update_fields["provider"] = resolved_provider
            if resolved_model:
                provider_update_fields["model"] = resolved_model
            if provider_update_fields:
                _set_image_job(job_id, **provider_update_fields)

        if isinstance(result, dict) and result.get("pending_callback"):
            with IMAGE_JOB_LOCK:
                current_job = dict(IMAGE_JOB_STORE.get(job_id) or {})
            metadata = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
            provider_task_id = str(
                (metadata or {}).get("task_id")
                or (metadata or {}).get("taskId")
                or result.get("provider_task_id")
                or ""
            ).strip()
            reservation_tx_id_pending = result.get("reservation_tx_id") or current_job.get("reservation_tx_id")
            try:
                reservation_tx_id_pending = int(reservation_tx_id_pending) if reservation_tx_id_pending is not None else None
            except Exception:
                reservation_tx_id_pending = None
            billing_context = result.get("billing_context") if isinstance(result.get("billing_context"), dict) else {}
            if not billing_context and isinstance(current_job.get("billing_context"), dict):
                billing_context = dict(current_job.get("billing_context") or {})

            update_fields: Dict[str, Any] = {
                "status": "waiting_callback",
                "error": None,
                "upstream_submit_state": "callback_pending",
                "billing_pending": bool(result.get("billing_pending") and reservation_tx_id_pending),
                "billing_settled": False,
            }
            if provider_task_id:
                update_fields["provider_task_id"] = provider_task_id
            if reservation_tx_id_pending:
                update_fields["reservation_tx_id"] = int(reservation_tx_id_pending)
            if billing_context:
                update_fields["billing_context"] = billing_context
            if provider_task_id and reservation_tx_id_pending:
                try:
                    attach_db = SessionLocal()
                    try:
                        billing_service.attach_provider_task_id_to_reservation(
                            attach_db,
                            int(reservation_tx_id_pending),
                            provider_task_id,
                        )
                    finally:
                        attach_db.close()
                except Exception:
                    logger.exception(
                        "[ImageJob] persist provider taskId on waiting_callback failed | job_id=%s reservation_tx_id=%s provider_task_id=%s",
                        job_id,
                        reservation_tx_id_pending,
                        provider_task_id,
                    )
            _set_image_job(job_id, **update_fields)
            mark_generation_task_status_external(job_id, status="waiting_callback", error=None)
            return {"defer_completion": True}

        with IMAGE_JOB_LOCK:
            _current_image_job = dict(IMAGE_JOB_STORE.get(job_id) or {})
        _status_to_set = "storing_asset" if _current_image_job.get("status") == "storing_asset" else "succeeded"
        _finished_at_val = None if _status_to_set == "storing_asset" else now_bj_iso()
        _success_fields = {
            "status": _status_to_set,
            "finished_at": _finished_at_val,
            "result": result,
            "error": None,
            "callback_submit_retries": 0,
            "callback_retry_at": None,
        }
        if _status_to_set == "succeeded":
            _success_fields["upstream_submit_state"] = "completed"
        _set_image_job(job_id, **_success_fields)
        mark_generation_task_status_external(job_id, status="completed", error=None)
        return {"defer_completion": False}
    except asyncio.TimeoutError:
        with IMAGE_JOB_LOCK:
            current_job = dict(IMAGE_JOB_STORE.get(job_id) or {})
        current_status = _normalize_generation_status(current_job.get("status"))
        current_result_url = _extract_job_result_url(current_job.get("result"))
        if current_status == "succeeded" and current_result_url:
            logger.info(
                "[ImageJob] timeout ignored after callback finalization | job_id=%s provider_task_id=%s result_url=%s",
                job_id,
                _extract_job_provider_task_id(current_job) or None,
                current_result_url,
            )
            return
        try:
            billing_service.log_failed_transaction(
                db,
                user_id,
                "image_gen",
                req_provider,
                req_model,
                f"Image job timeout after {IMAGE_JOB_MAX_RUNNING_SECONDS}s",
                details={
                    "status": "FAILED",
                    "failure_stage": "image_job_timeout",
                    "job_id": job_id,
                },
            )
        except Exception:
            logger.exception("Failed to log timed-out image job transaction | job_id=%s user_id=%s", job_id, user_id)
        _set_image_job(
            job_id,
            status="failed",
            finished_at=now_bj_iso(),
            error=f"image job timed out after {IMAGE_JOB_MAX_RUNNING_SECONDS}s",
        )
        mark_generation_task_status_external(job_id, status="failed", error=f"image job timed out after {IMAGE_JOB_MAX_RUNNING_SECONDS}s")
        return {"defer_completion": False}
    except asyncio.CancelledError:
        with IMAGE_JOB_LOCK:
            current_job = dict(IMAGE_JOB_STORE.get(job_id) or {})
        current_status = _normalize_generation_status(current_job.get("status"))
        current_result_url = _extract_job_result_url(current_job.get("result"))
        if current_status == "succeeded" and current_result_url:
            logger.info(
                "[ImageJob] cancellation ignored after callback finalization | job_id=%s provider_task_id=%s result_url=%s",
                job_id,
                _extract_job_provider_task_id(current_job) or None,
                current_result_url,
            )
            return
        try:
            billing_service.log_failed_transaction(
                db,
                user_id,
                "image_gen",
                req_provider,
                req_model,
                "Image job cancelled",
                details={
                    "status": "FAILED",
                    "failure_stage": "image_job_cancelled",
                    "job_id": job_id,
                },
            )
        except Exception:
            logger.exception("Failed to log cancelled image job transaction | job_id=%s user_id=%s", job_id, user_id)
        _set_image_job(
            job_id,
            status="canceled",
            finished_at=now_bj_iso(),
            error="Cancelled by user",
        )
        mark_generation_task_status_external(job_id, status="canceled", error="Cancelled by user")
        raise
    except HTTPException as e:
        with IMAGE_JOB_LOCK:
            current_job = dict(IMAGE_JOB_STORE.get(job_id) or {})
        current_status = _normalize_generation_status(current_job.get("status"))
        current_result_url = _extract_job_result_url(current_job.get("result"))
        if current_status == "succeeded" and current_result_url:
            logger.info(
                "[ImageJob] http error ignored after callback finalization | job_id=%s detail=%s provider_task_id=%s",
                job_id,
                str(e.detail),
                _extract_job_provider_task_id(current_job) or None,
            )
            return
        if _is_ambiguous_image_submit_detail(e.detail):
            _set_image_job(
                job_id,
                status="waiting_callback",
                error=None,
                ambiguous_submit=True,
                ambiguous_submit_at=now_bj_iso(),
                upstream_submit_state="unknown",
            )
            logger.warning(
                "[ImageJob] ambiguous submit retained as running | job_id=%s callback_ticket=%s detail=%s",
                job_id,
                provider_callback_ticket or None,
                str(e.detail),
            )
            mark_generation_task_status_external(job_id, status="waiting_callback", error=None)
            return {"defer_completion": True}
        _set_image_job(
            job_id,
            status="failed",
            finished_at=now_bj_iso(),
            error=str(e.detail),
        )
        mark_generation_task_status_external(job_id, status="failed", error=str(e.detail))
        return {"defer_completion": False}
    except Exception as e:
        with IMAGE_JOB_LOCK:
            current_job = dict(IMAGE_JOB_STORE.get(job_id) or {})
        current_status = _normalize_generation_status(current_job.get("status"))
        current_result_url = _extract_job_result_url(current_job.get("result"))
        if current_status == "succeeded" and current_result_url:
            logger.info(
                "[ImageJob] exception ignored after callback finalization | job_id=%s error=%s provider_task_id=%s",
                job_id,
                str(e),
                _extract_job_provider_task_id(current_job) or None,
            )
            return
        _set_image_job(
            job_id,
            status="failed",
            finished_at=now_bj_iso(),
            error=str(e),
        )
        mark_generation_task_status_external(job_id, status="failed", error=str(e))
        return {"defer_completion": False}
    finally:
        with IMAGE_JOB_LOCK:
            snapshot = dict(IMAGE_JOB_STORE.get(job_id) or {})
        if not callback_url:
            callback_url = _resolve_callback_url_from_payload(snapshot)
        await _dispatch_generation_callback("image", callback_url, snapshot)

        with IMAGE_JOB_LOCK:
            IMAGE_JOB_TASKS.pop(job_id, None)
        db.close()

