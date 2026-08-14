# -*- coding: utf-8 -*-
"""Video generation runner + async job wrapper."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.time_utils import now_bj_iso
from app.db.session import SessionLocal
from app.models.all_models import Episode, Project, Scene, Shot, User
from app.schemas.generation import VideoGenerationRequest
from app.services.billing_service import billing_service
from app.services.db_session_utils import _release_db_connection, _snapshot_user_principal
from app.services.effective_api_setting import _to_bool
from app.services.generation_runtime.api_capabilities import (
    _limit_media_ref_input,
    _limit_string_list_input,
    _map_int_value_to_allowed,
    _map_resolution_to_allowed,
    _map_text_value_to_allowed,
    _read_api_capability_bool,
    _read_api_capability_int,
    _read_api_capability_int_list,
    _read_api_capability_list,
    _resolve_video_submit_image_urls,
)
from app.services.generation_runtime.asset_registration import (
    _bind_generated_media_to_shot,
    _log_api_switch_regenerate_if_needed,
    _register_asset_helper,
)
from app.services.generation_runtime.callback_http import (
    _dispatch_generation_callback,
    _resolve_callback_url_from_payload,
)
from app.services.generation_runtime.callbacks import (
    _build_result_from_provider_callback,
    _extract_job_provider_task_id,
    _get_generation_callback_payload,
    _is_ambiguous_image_submit_detail,
    _merge_provider_task_ids_into_settle,
    _normalize_generation_status,
    _set_generation_callback_payload,
)
from app.services.generation_runtime.generation_errors import _format_generation_failure_detail
from app.services.generation_runtime.generation_filename import _build_generation_filename_base
from app.services.generation_runtime.job_store import (
    VIDEO_JOB_LOCK,
    VIDEO_JOB_MAX_RUNNING_SECONDS,
    VIDEO_JOB_STORE,
    VIDEO_JOB_TASKS,
    _clear_generation_job_pool_cache,
    _extract_job_result_url,
    _set_video_job,
)
from app.services.generation_runtime.log_sanitize import _sanitize_generation_runtime_config_for_log
from app.services.generation_runtime.media_persist import (
    _enrich_media_metadata_from_generation_context,
    _hydrate_video_job_record,
    _is_provider_direct_oss_url,
    _oss_upload_succeeded_for_url,
    _persist_remote_video_result,
    _resolve_video_bind_url,
)
from app.services.generation_runtime.media_runtime_target import _resolve_media_runtime_target
from app.services.generation_runtime.project_generation_context import (
    _ensure_project_generation_seed,
    _normalize_seed_value,
    _resolve_effective_negative_prompt,
    _resolve_project_id_for_generation,
    _should_hit_visual_breakpoint,
)
from app.services.generation_runtime.queue_config_runtime import _is_pure_callback_mode_enabled
from app.services.generation_runtime.seedance_duration import (
    SEEDANCE_DURATION_MAX_SECONDS,
    SEEDANCE_DURATION_MIN_SECONDS,
    _clamp_seedance_duration,
    _is_seedance_model_name,
)
from app.services.generation_runtime.video_job_billing import (
    _cancel_video_job_pending_reservation,
    _persist_video_job_billing_reservation,
    _settle_or_cancel_video_job_billing_from_callback,
)
from app.services.generation_runtime.video_provider_options import _build_video_provider_options
from app.services.generation_runtime.video_ref_pipeline import (
    _align_kling_elements_to_prompt_mentions,
    _append_video_api_ref_mapping,
    _build_auto_kling_elements,
    _build_project_entity_lookup,
    _ensure_video_frame_role_instructions,
    _find_previous_shot_video_url,
    _is_video_reference_image_mode,
    _limit_keyframes_for_video_mode,
    _listify_video_ref_urls,
    _merge_entity_refs_for_video_mode,
    _merge_kling_elements,
    _normalize_video_ref_mode,
    _normalize_video_request_refs,
    _pack_video_ref_urls,
    _parse_shot_tech,
    _sync_request_image_refs_with_aligned,
    _video_api_supports_last_frame_mode,
)
from app.services.media_service import media_service
from app.services.model_invocation_billing import (
    _extract_provider_usage_from_metadata,
    _maybe_refresh_kie_credits_from_record_info,
    _resolve_usage_token_total,
    _safe_int_token,
)
from app.services.project_visual_resolution import (
    infer_dims_from_video_resolution_tier as _infer_dims_from_video_resolution_tier,
    infer_project_resolution as _infer_project_resolution,
    normalize_project_image_size as _normalize_project_image_size,
    normalize_project_video_resolution as _normalize_project_video_resolution,
    project_video_resolution_label as _project_video_resolution_label,
)
from app.services.script_mode_helpers import (
    _build_ref_display_names,
    _log_shot_submit_debug,
)

logger = logging.getLogger("api_logger")


def _to_positive_int_or_none(value: Any) -> Optional[int]:
    from app.api.routers.workspace.shared import _to_positive_int_or_none as _fn
    return _fn(value)


def _publish_provisional_video_success(
    job_id: Optional[str],
    *,
    url: str,
    metadata: Optional[Dict[str, Any]] = None,
    callback_ticket: Optional[str] = None,
    mark_queue_completed: bool = True,
    bind_shot: bool = True,
) -> bool:
    """Publish provider URL immediately so editor/job polls finish before OSS localization."""
    stable_job_id = str(job_id or "").strip()
    stable_url = str(url or "").strip()
    if not stable_job_id or not stable_url:
        return False

    result_payload = {
        "url": stable_url,
        "metadata": dict(metadata) if isinstance(metadata, dict) else {},
    }
    result_payload["metadata"].setdefault("oss_persist_pending", True)
    result_payload["metadata"].setdefault("bg_persist_owned", True)
    provider_task_id = ""
    for key in ("provider_task_id", "task_id", "taskId"):
        provider_task_id = str(result_payload["metadata"].get(key) or "").strip()
        if provider_task_id:
            result_payload["metadata"].setdefault("provider_task_id", provider_task_id)
            result_payload["metadata"].setdefault("task_id", provider_task_id)
            result_payload["metadata"].setdefault("taskId", provider_task_id)
            break

    try:
        from app.services.generation_task_queue import mark_generation_task_status_external

        job_fields = {
            "status": "succeeded",
            "upstream_submit_state": "storing_asset",
            "result": result_payload,
            "error": None,
            "finished_at": now_bj_iso(),
        }
        if provider_task_id:
            job_fields["provider_task_id"] = provider_task_id
            job_fields["task_id"] = provider_task_id
            job_fields["taskId"] = provider_task_id
        _set_video_job(stable_job_id, **job_fields)
        if mark_queue_completed:
            mark_generation_task_status_external(stable_job_id, status="completed", error=None)

        stable_ticket = str(callback_ticket or "").strip()
        if stable_ticket:
            _set_generation_callback_payload(
                stable_ticket,
                {
                    "event": "generation.completed",
                    "kind": "video",
                    "job_id": stable_job_id,
                    "status": "succeeded",
                    "success": True,
                    "error": None,
                    "result": result_payload,
                },
            )

        logger.info(
            "[GenerateVideo] provisional result published | job_id=%s url=%s callback_ticket=%s",
            stable_job_id,
            stable_url.split("?", 1)[0],
            stable_ticket or None,
        )

        if bind_shot:
            _bind_provisional_video_url_to_shot(stable_job_id, stable_url, result_payload.get("metadata"))
        return True
    except Exception:
        logger.exception(
            "[GenerateVideo] failed to publish provisional result | job_id=%s",
            stable_job_id,
        )
        return False


def _bind_provisional_video_url_to_shot(
    job_id: str,
    url: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """Bind provider URL to shot as soon as poll completes (before OSS localization)."""
    stable_job_id = str(job_id or "").strip()
    stable_url = str(url or "").strip()
    if not stable_job_id or not stable_url:
        return False

    db = SessionLocal()
    try:
        with VIDEO_JOB_LOCK:
            job = dict(VIDEO_JOB_STORE.get(stable_job_id) or {})
        if not job:
            from app.services.generation_runtime.job_store import _read_video_job_file

            job = dict(_read_video_job_file(stable_job_id) or {})
        job = _hydrate_video_job_record(stable_job_id, job) or job

        from app.services.generation_runtime.media_persist import (
            _build_generation_job_req_context,
            _resolve_job_owner_user,
            _resolve_video_bind_url,
        )

        current_user = _resolve_job_owner_user(db, job)
        if not current_user:
            logger.warning(
                "[GenerateVideo] provisional shot bind skipped; owner missing | job_id=%s",
                stable_job_id,
            )
            return False

        req_context = _build_generation_job_req_context(job, db)
        req_context["asset_type"] = "video"
        if not req_context.get("shot_id"):
            logger.warning(
                "[GenerateVideo] provisional shot bind skipped; shot_id missing | job_id=%s",
                stable_job_id,
            )
            return False

        bind_meta = dict(metadata) if isinstance(metadata, dict) else {}
        bind_url, ephemeral_binding, bind_meta = _resolve_video_bind_url(
            raw_url=stable_url,
            normalized_url=stable_url,
            normalized_meta=bind_meta,
        )
        if not bind_url:
            logger.warning(
                "[GenerateVideo] provisional shot bind skipped; bind_url empty | job_id=%s",
                stable_job_id,
            )
            return False

        _register_asset_helper(db, current_user.id, bind_url, req_context, bind_meta)
        _bind_generated_media_to_shot(
            db,
            current_user,
            req_context,
            bind_url,
            False,
            bind_meta,
        )
        logger.info(
            "[GenerateVideo] provisional shot bind done | job_id=%s shot_id=%s url=%s ephemeral=%s",
            stable_job_id,
            req_context.get("shot_id"),
            bind_url.split("?", 1)[0],
            bool(ephemeral_binding),
        )
        return True
    except Exception:
        logger.exception(
            "[GenerateVideo] provisional shot bind failed | job_id=%s",
            stable_job_id,
        )
        return False
    finally:
        db.close()



async def _run_generate_video(
    req: VideoGenerationRequest,
    current_user: User,
    db: Session,
    provider_callback_ticket: Optional[str] = None,
    provider_callback_url: Optional[str] = None,
    force_pure_callback_mode: bool = False,
    provider_payload_callback: Any = None,
    provider_task_id_callback: Any = None,
    provider_result_callback: Any = None,
    job_id: Optional[str] = None,
):
    reservation_tx = None
    reservation_tx_id: Optional[int] = None
    runtime_target = _resolve_media_runtime_target(
        provider=req.provider,
        model=req.model,
        media_type="video",
        category="Video",
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

    _provider_lower_for_billing = str(reserve_provider or "").strip().lower()
    _skip_ark_token_formula = (
        _provider_lower_for_billing == "kie"
        or _provider_lower_for_billing.startswith("kie/")
        or "kie.ai" in _provider_lower_for_billing
        or _provider_lower_for_billing == "runninghub"
        or _provider_lower_for_billing.startswith("runninghub/")
        or "runninghub" in _provider_lower_for_billing
    )
    # KIE / RunningHub Seedance bill by resolution-tier CNY (or KIE credits) per second.
    _is_token_billing = (not _skip_ark_token_formula) and billing_service.is_token_pricing(
        db, "video_gen", reserve_provider, reserve_model
    )
    _video_token_cfg = {}
    _estimated_tokens = 0

    try:
        # 1. Resolve Context for Aspect Ratio
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

        def _pick_ratio_from_info(info: Dict[str, Any]) -> Optional[str]:
            if not isinstance(info, dict):
                return None
            tech = info.get("tech_params")
            if isinstance(tech, dict):
                vis = tech.get("visual_standard") or tech.get("visual standard") or {}
                if isinstance(vis, dict):
                    candidate = vis.get("aspect_ratio") or vis.get("aspectRatio")
                    if str(candidate or "").strip():
                        return str(candidate).strip()
            direct = info.get("aspect_ratio") or info.get("aspectRatio")
            if str(direct or "").strip():
                return str(direct).strip()
            nested = info.get("e_global_info")
            if isinstance(nested, dict):
                return _pick_ratio_from_info(nested)
            return None

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
                "resolution": vis.get("resolution") or defaults.get("resolution") or defaults.get("image_resolution") or info.get("resolution"),
                "image_size": vis.get("image_size") or vis.get("imageSize") or defaults.get("image_size") or defaults.get("imageSize") or defaults.get("image_resolution") or defaults.get("imageResolution") or info.get("image_size") or info.get("imageSize"),
                "video_resolution": (
                    vis.get("video_resolution")
                    or defaults.get("video_resolution")
                    or info.get("video_resolution")
                ),
            }

            nested = info.get("e_global_info") if isinstance(info.get("e_global_info"), dict) else None
            if nested:
                nested_values = _pick_visual_from_info(nested)
                for key in ("aspect_ratio", "width", "height", "resolution", "image_size", "video_resolution"):
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

        aspect_ratio = None
        aspect_ratio_source = "fallback"
        project_global_info: Dict[str, Any] = {}
        resolved_project_id = req.project_id
        resolved_episode_id = _to_positive_int_or_none(getattr(req, "episode_id", None))
        resolved_shot_id = _to_positive_int_or_none(getattr(req, "shot_id", None))

        # Billing context fallback: infer missing IDs from shot/episode lineage.
        context_shot: Optional[Shot] = None
        if resolved_shot_id:
            context_shot = db.query(Shot).filter(Shot.id == int(resolved_shot_id)).first()
            if context_shot:
                if not resolved_project_id:
                    shot_project_id = _to_positive_int_or_none(getattr(context_shot, "project_id", None))
                    if shot_project_id:
                        resolved_project_id = int(shot_project_id)

                if not resolved_episode_id:
                    shot_episode_id = _to_positive_int_or_none(getattr(context_shot, "episode_id", None))
                    if shot_episode_id:
                        resolved_episode_id = int(shot_episode_id)

                if not resolved_episode_id and getattr(context_shot, "scene_id", None):
                    context_scene = db.query(Scene).filter(Scene.id == int(context_shot.scene_id)).first()
                    if context_scene and _to_positive_int_or_none(getattr(context_scene, "episode_id", None)):
                        resolved_episode_id = int(context_scene.episode_id)

        if not resolved_project_id:
            resolved_project_id = _resolve_project_id_for_generation(req, db)

        if not resolved_project_id and resolved_episode_id:
            context_episode = db.query(Episode).filter(Episode.id == int(resolved_episode_id)).first()
            if context_episode and _to_positive_int_or_none(getattr(context_episode, "project_id", None)):
                resolved_project_id = int(context_episode.project_id)

        # Only read project-level realtime config for visual params.
        if resolved_project_id:
            project = db.query(Project).filter(Project.id == resolved_project_id).first()
            if project:
                project_global_info = _safe_json_dict(project.global_info)
                gi_basic_info = project_global_info.get("basic_info") or {}
                project_type = gi_basic_info.get("type") or project_global_info.get("type") or ""
                if project_type:
                    project_type_prefix = f"项目视觉类型：{project_type}"
                    if not req.prompt:
                        req.prompt = project_type_prefix
                    elif project_type_prefix not in req.prompt:
                        req.prompt = f"{project_type_prefix}\n{req.prompt}"

        req_ratio = str(req.aspect_ratio or "").strip() or None
        project_ratio = _pick_ratio_from_info(project_global_info)
        project_visual = _pick_visual_from_info(project_global_info)
        resolved_video_width: Optional[int] = None
        resolved_video_height: Optional[int] = None
        resolved_video_resolution: Optional[str] = None
        resolved_video_image_size: Optional[str] = None

        resolved_sound: Optional[bool] = None
        sound_source = "request"
        if req.sound is not None:
            resolved_sound = bool(req.sound)
        else:
            project_defaults = (
                project_global_info.get("project_generation_defaults")
                if isinstance(project_global_info.get("project_generation_defaults"), dict)
                else {}
            )
            sound_candidates = [
                project_defaults.get("sound"),
                project_defaults.get("generate_audio"),
                project_global_info.get("video_sound"),
                project_global_info.get("sound"),
                project_global_info.get("generate_audio"),
            ]
            visual_standard = {}
            tech_params = project_global_info.get("tech_params")
            if isinstance(tech_params, dict):
                visual_standard = (
                    tech_params.get("visual_standard")
                    if isinstance(tech_params.get("visual_standard"), dict)
                    else {}
                )
            sound_candidates.extend([
                visual_standard.get("sound"),
                visual_standard.get("has_audio"),
                visual_standard.get("generate_audio"),
            ])
            for candidate in sound_candidates:
                if candidate is None:
                    continue
                resolved_sound = bool(_to_bool(candidate))
                sound_source = "project_global_info"
                break
            if resolved_sound is None:
                resolved_sound = True
                sound_source = "fallback_default"

        if req_ratio:
            aspect_ratio = req_ratio
            aspect_ratio_source = "request"
        elif project_ratio:
            aspect_ratio = project_ratio
            aspect_ratio_source = "project_global_info"

        sound_capability = _read_api_capability_bool(
            pre_api_cfg,
            "sound_supported",
            "has_audio",
            "audio_supported",
            "supports_audio",
        )
        if sound_capability is False:
            resolved_sound = False
            sound_source = "system_api_capability"

        normalized_mode = str(req.mode or "").strip().lower() or None

        allowed_video_modes = _read_api_capability_list(
            pre_api_cfg,
            "mode_values",
            "mode",
            "allowed_modes",
            "supported_modes",
        )
        if normalized_mode and allowed_video_modes:
            normalized_mode = _map_text_value_to_allowed(normalized_mode, allowed_video_modes)

        allowed_video_aspect_ratios = _read_api_capability_list(
            pre_api_cfg,
            "aspect_ratio_values",
            "aspect_ratios",
            "aspect_ratio",
            "allowed_aspect_ratios",
            "supported_aspect_ratios",
        )
        if aspect_ratio and allowed_video_aspect_ratios:
            aspect_ratio = _map_text_value_to_allowed(aspect_ratio, allowed_video_aspect_ratios)

        allowed_video_durations = _read_api_capability_int_list(
            pre_api_cfg,
            "durations_seconds",
            "duration_values",
            "allowed_durations",
            "supported_durations",
        )
        if req.duration is not None and allowed_video_durations:
            mapped_duration = _map_int_value_to_allowed(req.duration, allowed_video_durations)
            if mapped_duration is not None:
                req.duration = float(mapped_duration)

        allowed_video_qualities = _read_api_capability_list(
            pre_api_cfg,
            "quality_values",
            "qualities",
            "quality_levels",
            "allowed_qualities",
            "supported_qualities",
        )
        video_quality = str(req.quality or "").strip().lower() or None
        if video_quality and allowed_video_qualities:
            video_quality = _map_text_value_to_allowed(video_quality, allowed_video_qualities)

        allowed_video_output_formats = _read_api_capability_list(
            pre_api_cfg,
            "output_format_values",
            "output_formats",
            "allowed_output_formats",
            "supported_output_formats",
        )
        video_output_format = str(req.output_format or req.outputFormat or "").strip().lower() or None
        if video_output_format and allowed_video_output_formats:
            video_output_format = _map_text_value_to_allowed(video_output_format, allowed_video_output_formats)

        max_duration_cap = _read_api_capability_int(
            pre_api_cfg,
            "max_duration",
        )
        if req.duration is not None and max_duration_cap is not None and max_duration_cap > 0:
            req.duration = float(min(float(req.duration), float(max_duration_cap)))

        # Seedance hard range: [4, 15] seconds. Preserve -1 (auto duration).
        pre_cfg_payload = (pre_api_cfg or {}).get("config") if isinstance((pre_api_cfg or {}).get("config"), dict) else {}
        if _is_seedance_model_name(
            reserve_provider,
            reserve_model,
            (pre_api_cfg or {}).get("name"),
            (pre_api_cfg or {}).get("model"),
            (pre_api_cfg or {}).get("base_model"),
            pre_cfg_payload.get("base_model") if isinstance(pre_cfg_payload, dict) else None,
            getattr(req, "model", None),
            getattr(req, "provider", None),
        ):
            clamped_duration, was_clamped = _clamp_seedance_duration(req.duration)
            if was_clamped and clamped_duration is not None:
                logger.info(
                    "[GenerateVideo] Seedance duration clamped | from=%s to=%s provider=%s model=%s "
                    "(min=%.0f max=%.0f)",
                    req.duration,
                    clamped_duration,
                    reserve_provider,
                    reserve_model,
                    SEEDANCE_DURATION_MIN_SECONDS,
                    SEEDANCE_DURATION_MAX_SECONDS,
                )
                req.duration = float(clamped_duration)

        # Inject project visual size defaults for video providers that support/need them.
        width_candidates = [
            project_visual.get("width"),
        ]
        height_candidates = [
            project_visual.get("height"),
        ]
        for candidate in width_candidates:
            parsed = _to_positive_int_or_none(candidate)
            if parsed:
                resolved_video_width = int(parsed)
                break
        for candidate in height_candidates:
            parsed = _to_positive_int_or_none(candidate)
            if parsed:
                resolved_video_height = int(parsed)
                break

        if not resolved_video_width or not resolved_video_height:
            resolution_candidates = [
                project_visual.get("resolution"),
                project_global_info.get("resolution"),
                project_global_info.get("image_resolution"),
            ]
            for candidate in resolution_candidates:
                parsed_w, parsed_h = _parse_resolution_dims(candidate)
                if parsed_w and parsed_h:
                    if not resolved_video_width:
                        resolved_video_width = int(parsed_w)
                    if not resolved_video_height:
                        resolved_video_height = int(parsed_h)
                    break

        if resolved_video_width and resolved_video_height:
            resolved_video_resolution = f"{int(resolved_video_width)}x{int(resolved_video_height)}"

        allowed_video_resolutions = _read_api_capability_list(
            pre_api_cfg,
            "supported_resolutions",
            "resolution_values",
            "resolution",
            "allowed_resolutions",
        )
        if resolved_video_resolution and allowed_video_resolutions:
            mapped_resolution = _map_resolution_to_allowed(resolved_video_resolution, allowed_video_resolutions)
            parsed_w, parsed_h = _parse_resolution_dims(mapped_resolution)
            if parsed_w and parsed_h:
                resolved_video_width = int(parsed_w)
                resolved_video_height = int(parsed_h)
                resolved_video_resolution = f"{int(parsed_w)}x{int(parsed_h)}"

        image_size_candidates = [
            project_visual.get("image_size"),
            project_global_info.get("image_size"),
            project_global_info.get("imageSize"),
        ]
        for candidate in image_size_candidates:
            normalized = _normalize_project_image_size(candidate)
            if normalized:
                resolved_video_image_size = normalized
                break

        allowed_video_image_sizes = _read_api_capability_list(
            pre_api_cfg,
            "image_size_values",
            "image_sizes",
            "image_size",
            "allowed_image_sizes",
            "supported_image_sizes",
        )
        if resolved_video_image_size and allowed_video_image_sizes:
            resolved_video_image_size = _map_text_value_to_allowed(
                resolved_video_image_size,
                allowed_video_image_sizes,
            )

        # If project only provides logical size tier (e.g. 1K) plus aspect ratio,
        # infer concrete dimensions so billing-rule range matching can use width/height.
        if req.draft_mode:
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
            # Prefer explicit request / project video_resolution (480|720) over image pixel size.
            req_video_tier = _normalize_project_video_resolution(
                getattr(req, "video_resolution", None) or getattr(req, "resolution", None)
            )
            project_video_tier = _normalize_project_video_resolution(
                project_visual.get("video_resolution")
                or project_global_info.get("video_resolution")
            ) or "720"
            video_tier = req_video_tier or project_video_tier
            if video_tier:
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

        # DdiMatuo always submits 1080p — override project/request 720p before billing + options.
        try:
            from app.services.media_service import media_service as _ddi_res_svc

            _is_ddimatuo_for_resolution = (
                _ddi_res_svc._normalize_provider_name(reserve_provider or req.provider, "Video")
                == "ddimatuo"
            )
        except Exception:
            _is_ddimatuo_for_resolution = (
                str(reserve_provider or req.provider or "").strip().lower() == "ddimatuo"
            )
        if _is_ddimatuo_for_resolution:
            resolved_video_resolution = "1080P"
            video_quality = None
            ddi_dims = _infer_dims_from_video_resolution_tier(
                aspect_ratio,
                "1080",
                provider=reserve_provider,
                model=reserve_model,
            )
            if ddi_dims:
                resolved_video_width, resolved_video_height = ddi_dims

        # Estimate + reserve share one builder (duration/draft/continuation/resolution).
        from app.services.video_billing_details import build_video_generation_billing_details

        _billing_extra: Dict[str, Any] = {}
        if resolved_sound is not None:
            _billing_extra["has_audio"] = bool(resolved_sound)
        if normalized_mode:
            _billing_extra["mode"] = normalized_mode
            _billing_extra["generation_mode"] = normalized_mode

        reserve_details, _billing_meta = build_video_generation_billing_details(
            db,
            user_id=getattr(current_user, "id", None),
            user_credits=(current_user.credits or 0),
            billing_mode="RESERVE",
            function_name=str(getattr(req, "function_name", None) or "generate_videos").strip() or "generate_videos",
            provider=reserve_provider or req.provider,
            model=reserve_model or req.model,
            system_api_id=reserve_system_api_id or getattr(req, "system_api_id", None),
            project_id=resolved_project_id,
            episode_id=resolved_episode_id,
            shot_id=resolved_shot_id,
            duration=req.duration,
            draft_mode=bool(req.draft_mode),
            use_prev_video=bool(getattr(req, "use_prev_video", False)),
            has_video_input=getattr(req, "has_video_input", None),
            input_duration=getattr(req, "input_duration", None),
            input_duration_seconds=getattr(req, "input_duration_seconds", None),
            aspect_ratio=aspect_ratio,
            width=resolved_video_width,
            height=resolved_video_height,
            resolution=resolved_video_resolution,
            video_resolution=getattr(req, "video_resolution", None) or getattr(req, "resolution", None),
            image_size=resolved_video_image_size,
            ref_video_urls=getattr(req, "ref_video_urls", None),
            project_global_info=project_global_info,
            runtime_target=runtime_target,
            extra_details=_billing_extra,
        )
        _is_token_billing = bool(_billing_meta.get("is_token_billing"))
        _estimated_tokens = int(_billing_meta.get("estimated_tokens") or 0)
        _video_token_cfg = dict(_billing_meta.get("video_token_cfg") or {})
        est_duration = int(_billing_meta.get("duration_seconds") or 5)
        _has_video_input = bool(_billing_meta.get("has_video_input"))
        _input_duration = _billing_meta.get("input_duration_seconds")
        # Prefer billing-resolved dims for reserve consistency / later settle context.
        if _billing_meta.get("width"):
            resolved_video_width = int(_billing_meta.get("width"))
        if _billing_meta.get("height"):
            resolved_video_height = int(_billing_meta.get("height"))
        if _billing_meta.get("resolution"):
            resolved_video_resolution = str(_billing_meta.get("resolution"))
        if _billing_meta.get("image_size"):
            resolved_video_image_size = str(_billing_meta.get("image_size"))
        if _billing_meta.get("resolved_provider"):
            reserve_provider = _billing_meta.get("resolved_provider")
        if _billing_meta.get("resolved_model"):
            reserve_model = _billing_meta.get("resolved_model")
        if _billing_meta.get("resolved_system_api_id") is not None:
            reserve_system_api_id = _billing_meta.get("resolved_system_api_id")

        # Billing matrix only knows 480/720 and rewrites 1080 → 720; restore DdiMatuo hard contract.
        if _is_ddimatuo_for_resolution:
            resolved_video_resolution = "1080P"
            video_quality = None
            ddi_dims = _infer_dims_from_video_resolution_tier(
                aspect_ratio,
                "1080",
                provider=reserve_provider,
                model=reserve_model,
            )
            if ddi_dims:
                resolved_video_width, resolved_video_height = ddi_dims
            if isinstance(reserve_details, dict):
                reserve_details["resolution"] = "1080P"
                if resolved_video_width:
                    reserve_details["width"] = int(resolved_video_width)
                if resolved_video_height:
                    reserve_details["height"] = int(resolved_video_height)
            if isinstance(_billing_meta, dict):
                _billing_meta["resolution"] = "1080P"
                if resolved_video_width:
                    _billing_meta["width"] = int(resolved_video_width)
                if resolved_video_height:
                    _billing_meta["height"] = int(resolved_video_height)

        reserve_provider_arg = reserve_provider or req.provider
        reserve_model_arg = reserve_model or req.model
        reservation_tx = billing_service.reserve_credits(
            db,
            current_user.id,
            "video_gen",
            reserve_provider_arg,
            reserve_model_arg,
            reserve_details,
        )
        try:
            reservation_tx_id = int(getattr(reservation_tx, "id", 0) or 0) or None
        except Exception:
            reservation_tx_id = None

        # Persist reservation onto job/task immediately so multi-worker callbacks can settle.
        if reservation_tx_id and provider_callback_ticket:
            early_billing_context = {
                "is_token_billing": bool(_is_token_billing),
                "estimated_tokens": int(_estimated_tokens or 0),
                "duration": est_duration,
                "duration_seconds": est_duration,
                "aspect_ratio": str(aspect_ratio or "").strip() or None,
                "draft_mode": bool(req.draft_mode),
                "use_prev_video": bool(getattr(req, "use_prev_video", False)),
                "shot_continuation": bool(getattr(req, "use_prev_video", False)),
                "has_video_input": bool(_has_video_input),
                "input_duration_seconds": float(_input_duration) if _input_duration is not None else None,
                "width": int(resolved_video_width) if resolved_video_width else None,
                "height": int(resolved_video_height) if resolved_video_height else None,
                "fps": int((_video_token_cfg or {}).get("default_fps", 24) or 24),
                "resolution": str(resolved_video_resolution or "") or None,
                "provider": reserve_provider or req.provider,
                "model": reserve_model or req.model,
                "system_api_id": reserve_system_api_id,
                "project_id": int(resolved_project_id) if resolved_project_id else None,
                "episode_id": int(resolved_episode_id) if resolved_episode_id else None,
                "shot_id": int(resolved_shot_id) if resolved_shot_id else None,
                "is_seedance_2": bool((_video_token_cfg or {}).get("is_seedance_2"))
                or billing_service.is_seedance_2_model(reserve_provider, reserve_model),
                "draft_token_coefficient": float(
                    (_video_token_cfg or {}).get("draft_token_coefficient", 1.0) or 1.0
                ),
            }
            _persist_video_job_billing_reservation(
                provider_callback_ticket=provider_callback_ticket,
                reservation_tx_id=reservation_tx_id,
                billing_context=early_billing_context,
                user_id=getattr(current_user, "id", None),
            )

        project_seed = _ensure_project_generation_seed(db, resolved_project_id, current_user)
        explicit_seed = _normalize_seed_value(getattr(req, "seed", None))

        logger.info(
            "[GenerateVideo] Resolved aspect ratio=%s source=%s sound=%s sound_source=%s project_id=%s episode_id=%s shot_id=%s width=%s height=%s resolution=%s image_size=%s",
            aspect_ratio,
            aspect_ratio_source,
            resolved_sound,
            sound_source,
            resolved_project_id,
            resolved_episode_id,
            resolved_shot_id,
            resolved_video_width,
            resolved_video_height,
            resolved_video_resolution,
            resolved_video_image_size,
        )
        logger.info(
            "[GenerateVideo] Project Visual Extract | project_id=%s project_keys=%s picked=%s",
            resolved_project_id,
            sorted(list(project_global_info.keys()))[:30] if isinstance(project_global_info, dict) else [],
            {
                "aspect_ratio": aspect_ratio,
                "width": resolved_video_width,
                "height": resolved_video_height,
                "resolution": resolved_video_resolution,
                "image_size": resolved_video_image_size,
                "raw_project_visual": project_visual,
            },
        )

        if _should_hit_visual_breakpoint("video", resolved_project_id):
            logger.warning(
                "[GenerateVideo] BREAKPOINT hit | project_id=%s aspect_ratio=%s width=%s height=%s resolution=%s image_size=%s raw_project_visual=%s",
                resolved_project_id,
                aspect_ratio,
                resolved_video_width,
                resolved_video_height,
                resolved_video_resolution,
                resolved_video_image_size,
                project_visual,
            )
            breakpoint()
        _log_shot_submit_debug(
            "video_submit",
            req,
            refs=req.ref_image_url,
            extra={
                "last_frame_url": req.last_frame_url,
                "duration": req.duration,
                "aspect_ratio": aspect_ratio,
                "aspect_ratio_source": aspect_ratio_source,
                "sound": resolved_sound,
                "sound_source": sound_source,
                "width": resolved_video_width,
                "height": resolved_video_height,
                "resolution": resolved_video_resolution,
                "image_size": resolved_video_image_size,
                "resolved_project_id": resolved_project_id,
                "project_seed": explicit_seed or project_seed,
                "keyframes_count": len(req.keyframes or []),
                "user_id": current_user.id,
            },
        )

        prompt_text = str(req.prompt or "")
        normalized_ref_mode = _normalize_video_ref_mode(getattr(req, "ref_mode", None))
        resolved_video_provider = str(reserve_provider or req.provider or "").strip().lower()
        resolved_video_model = str(reserve_model or req.model or "").strip().lower()
        image_ref_limit = _read_api_capability_int(
            pre_api_cfg,
            "reference_image_limit",
            "max_reference_images",
            "max_image_refs",
        )
        video_ref_limit = _read_api_capability_int(
            pre_api_cfg,
            "reference_video_limit",
            "max_reference_videos",
            "max_video_refs",
        )
        explicit_last_frame_flag = _read_api_capability_bool(
            pre_api_cfg,
            "supports_last_frame",
            "supports_last_frame_mode",
            "last_frame_supported",
        )
        explicit_first_frame_flag = _read_api_capability_bool(
            pre_api_cfg,
            "supports_first_frame",
            "supports_start_frame",
            "first_frame_supported",
            "start_frame_supported",
        )
        supports_keyframes_flag = _read_api_capability_bool(
            pre_api_cfg,
            "supports_keyframes",
            "keyframes_supported",
            "supports_multi_keyframes",
        )
        max_keyframes = _read_api_capability_int(
            pre_api_cfg,
            "max_keyframes",
            "keyframe_limit",
        )
        # Prefer system-api capability flag; fall back to provider/model heuristics.
        supports_last_frame_mode = (
            bool(explicit_last_frame_flag)
            if explicit_last_frame_flag is not None
            else _video_api_supports_last_frame_mode(resolved_video_provider, resolved_video_model)
        )

        submit_image_urls = _resolve_video_submit_image_urls(req)
        uses_submit_image_urls = bool(submit_image_urls)
        if uses_submit_image_urls and image_ref_limit is not None:
            submit_image_urls = _limit_string_list_input(submit_image_urls, image_ref_limit)
        elif image_ref_limit is not None:
            req.ref_image_url = _limit_media_ref_input(req.ref_image_url, image_ref_limit)

        normalize_source = submit_image_urls if uses_submit_image_urls else req.ref_image_url
        normalized_refs, req.last_frame_url, ref_normalization_info = _normalize_video_request_refs(
            normalize_source,
            req.last_frame_url,
            normalized_ref_mode,
            supports_last_frame_mode=supports_last_frame_mode,
        )
        if uses_submit_image_urls:
            submit_image_urls = _listify_video_ref_urls(normalized_refs)
            req.image_urls = submit_image_urls
            req.ref_image_url = None
        else:
            req.ref_image_url = normalized_refs
        if isinstance(req.ref_video_urls, list) and video_ref_limit is not None:
            req.ref_video_urls = _limit_media_ref_input(req.ref_video_urls, video_ref_limit)
        if explicit_first_frame_flag is False:
            req.ref_image_url = [] if isinstance(req.ref_image_url, list) else None
            if uses_submit_image_urls:
                submit_image_urls = []
                req.image_urls = []
        if explicit_last_frame_flag is False and req.last_frame_url:
            # Safety: if a dedicated last-frame slot remains, fold it into image refs.
            merged = _listify_video_ref_urls(
                submit_image_urls if uses_submit_image_urls else req.ref_image_url
            )
            end_ref = str(req.last_frame_url or "").strip()
            if end_ref and end_ref not in merged:
                merged.append(end_ref)
            if uses_submit_image_urls:
                submit_image_urls = merged
                req.image_urls = merged
            else:
                req.ref_image_url = _pack_video_ref_urls(merged)
            req.last_frame_url = None
        if supports_keyframes_flag is False:
            req.keyframes = None
        elif isinstance(req.keyframes, list) and max_keyframes is not None:
            normalized_keyframes = [str(item).strip() for item in req.keyframes if str(item).strip()]
            req.keyframes = normalized_keyframes[:max_keyframes] if max_keyframes > 0 else []
        if normalized_ref_mode == "keyframes_entity_refs" and isinstance(req.keyframes, list):
            req.keyframes = _limit_keyframes_for_video_mode(req.keyframes, normalized_ref_mode)
        normalized_ref_mode = str(ref_normalization_info.get("normalized_mode") or normalized_ref_mode or "")
        logger.info(
            "[GenerateVideo] ref mode normalization | shot_id=%s shot_number=%s ref_mode=%s supports_last_frame=%s fallback_to_refs=%s start_before=%s start_after=%s last_before=%s last_after=%s provider=%s model=%s",
            req.shot_id,
            req.shot_number,
            normalized_ref_mode or "<empty>",
            supports_last_frame_mode,
            bool(ref_normalization_info.get("fallback_to_refs")),
            ref_normalization_info.get("start_count_before"),
            ref_normalization_info.get("start_count_after"),
            ref_normalization_info.get("had_last_frame_before"),
            ref_normalization_info.get("had_last_frame_after"),
            resolved_video_provider or None,
            resolved_video_model or None,
        )
        is_reference_image_mode = _is_video_reference_image_mode(normalized_ref_mode)
        has_explicit_visual_refs = uses_submit_image_urls
        if not has_explicit_visual_refs and isinstance(req.ref_image_url, list):
            has_explicit_visual_refs = any(str(x).strip() for x in req.ref_image_url)
        elif not has_explicit_visual_refs and isinstance(req.ref_image_url, str) and req.ref_image_url.strip():
            has_explicit_visual_refs = True
        elif isinstance(req.ref_video_urls, list) and any(str(x).strip() for x in req.ref_video_urls):
            has_explicit_visual_refs = True

        effective_keyframes = _limit_keyframes_for_video_mode(req.keyframes, normalized_ref_mode)
        if normalized_ref_mode == "keyframes_entity_refs" and effective_keyframes:
            req.keyframes = effective_keyframes

        start_frame_url_for_roles = ""
        shot_for_ref: Optional[Shot] = None
        if req.shot_id:
            shot_for_ref = db.query(Shot).filter(Shot.id == int(req.shot_id)).first()
            if shot_for_ref:
                start_frame_url_for_roles = str(getattr(shot_for_ref, "image_url", None) or "").strip()

        auto_entity_refs: List[str] = []
        if is_reference_image_mode and resolved_project_id and not uses_submit_image_urls:
            entity_lookup = _build_project_entity_lookup(
                db, int(resolved_project_id), episode_id=resolved_episode_id
            )
            prompt_candidates: List[str] = [prompt_text]
            shot_tech: Dict[str, Any] = {}

            if shot_for_ref:
                prompt_candidates.extend([
                    str(shot_for_ref.video_content or "").strip(),
                    str(shot_for_ref.prompt or "").strip(),
                ])
                shot_tech = _parse_shot_tech(shot_for_ref)
                if isinstance(shot_tech, dict):
                    prompt_candidates.extend([
                        str(shot_tech.get("video_prompt_cn") or "").strip(),
                    ])

            existing_start_refs = _listify_video_ref_urls(req.ref_image_url)
            merged_refs, auto_entity_refs = _merge_entity_refs_for_video_mode(
                existing_start_refs,
                ref_mode=normalized_ref_mode,
                prompt_candidates=prompt_candidates,
                entity_lookup=entity_lookup,
                manual_override=has_explicit_visual_refs,
                associated_entities=shot_for_ref.associated_entities if shot_for_ref else None,
            )
            if merged_refs:
                req.ref_image_url = merged_refs
            if image_ref_limit is not None:
                req.ref_image_url = _limit_media_ref_input(req.ref_image_url, image_ref_limit)

            if auto_entity_refs:
                logger.info(
                    "[GenerateVideo] merged entity refs | shot_id=%s project_id=%s ref_mode=%s explicit_refs=%s detected=%s final_refs=%s",
                    req.shot_id,
                    resolved_project_id,
                    normalized_ref_mode or "list_ref",
                    has_explicit_visual_refs,
                    len(auto_entity_refs),
                    len(merged_refs),
                )
            elif has_explicit_visual_refs:
                logger.info(
                    "[GenerateVideo] preserve explicit visual refs | shot_id=%s project_id=%s ref_mode=%s",
                    req.shot_id,
                    resolved_project_id,
                    normalized_ref_mode or "list_ref",
                )
        elif is_reference_image_mode and has_explicit_visual_refs:
            logger.info(
                "[GenerateVideo] preserve explicit visual refs | shot_id=%s project_id=%s ref_mode=%s",
                req.shot_id,
                resolved_project_id,
                normalized_ref_mode or "list_ref",
            )

        if bool(getattr(req, "use_prev_video", False)):
            existing_video_refs = [
                str(x).strip()
                for x in (req.ref_video_urls or [])
                if str(x).strip()
            ] if isinstance(req.ref_video_urls, list) else []
            if not existing_video_refs and _to_positive_int_or_none(getattr(req, "shot_id", None)):
                prev_video_episode_id = _to_positive_int_or_none(getattr(req, "episode_id", None))
                if not prev_video_episode_id:
                    prev_video_shot = db.query(Shot).filter(Shot.id == int(req.shot_id)).first()
                    prev_video_episode_id = _to_positive_int_or_none(getattr(prev_video_shot, "episode_id", None)) if prev_video_shot else None
                if prev_video_episode_id:
                    prev_video_url = _find_previous_shot_video_url(db, int(prev_video_episode_id), int(req.shot_id))
                    if prev_video_url:
                        req.ref_video_urls = [prev_video_url]
                        logger.info(
                            "[GenerateVideo] backfilled previous video ref | shot_id=%s episode_id=%s ref=%s",
                            req.shot_id,
                            prev_video_episode_id,
                            str(prev_video_url or "")[:300],
                        )

        # ImageN numbering source = provider image list only (not last_frame/keyframes slots).
        flat_refs: List[str] = []
        if uses_submit_image_urls:
            flat_refs.extend(submit_image_urls)
        else:
            flat_refs.extend(_listify_video_ref_urls(req.ref_image_url))
        flat_refs = _listify_video_ref_urls(flat_refs)
        ref_names = _build_ref_display_names(flat_refs)
        logger.info(
            "[GenerateVideo] ref resolution | shot_id=%s shot_number=%s ref_mode=%s start_refs=%s last_frame=%s keyframes=%s final_ref_count=%s",
            req.shot_id,
            req.shot_number,
            normalized_ref_mode or "<empty>",
            len(submit_image_urls) if uses_submit_image_urls else (len(req.ref_image_url) if isinstance(req.ref_image_url, list) else (1 if str(req.ref_image_url or "").strip() else 0)),
            bool(str(req.last_frame_url or "").strip()),
            len(effective_keyframes or []) if isinstance(effective_keyframes, list) else 0,
            len(flat_refs),
        )
        logger.info(
            "[GenerateVideo] refs | shot_id=%s shot_number=%s ref_count=%s ref_names=%s",
            req.shot_id,
            req.shot_number,
            len(flat_refs),
            ref_names,
        )
        # Must use resolved_project_id (same as ref merge). req.project_id is often
        # missing on submit; empty lookup → pairs=0 → @Image stripped and never re-injected.
        mapping_project_id = _to_positive_int_or_none(resolved_project_id) or _to_positive_int_or_none(
            getattr(req, "project_id", None)
        )
        entity_lookup = (
            _build_project_entity_lookup(db, int(mapping_project_id), episode_id=resolved_episode_id)
            if mapping_project_id and is_reference_image_mode
            else {}
        )
        logger.info(
            "[GenerateVideo] prompt mapping prepare | shot_id=%s ref_mode=%s refs=%s project_id_req=%s project_id_resolved=%s lookup_keys=%s",
            req.shot_id,
            normalized_ref_mode or "<empty>",
            len(flat_refs),
            getattr(req, "project_id", None),
            mapping_project_id,
            len(entity_lookup or {}),
        )

        prompt_text, flat_refs = _append_video_api_ref_mapping(
            prompt_text,
            flat_refs,
            req.image_urls if uses_submit_image_urls else req.ref_image_url,
            req.last_frame_url,
            effective_keyframes,
            req.ref_video_urls,
            entity_lookup=entity_lookup or None,
            use_prev_video=getattr(req, "use_prev_video", False),
            provider=resolved_video_provider,
            model=resolved_video_model,
            # Frontend Ref panel / explicit image_urls is source of truth.
            preserve_submitted_refs=bool(uses_submit_image_urls or has_explicit_visual_refs),
        )
        synced_image_urls, synced_ref_image_url = _sync_request_image_refs_with_aligned(
            aligned_refs=flat_refs,
            image_urls=req.image_urls if uses_submit_image_urls else None,
            ref_image_url=None if uses_submit_image_urls else req.ref_image_url,
            last_frame_url=req.last_frame_url,
            keyframes=effective_keyframes,
        )
        if uses_submit_image_urls and isinstance(synced_image_urls, list) and synced_image_urls:
            req.image_urls = synced_image_urls
            submit_image_urls = synced_image_urls
        elif synced_ref_image_url is not None:
            req.ref_image_url = synced_ref_image_url
            if not uses_submit_image_urls:
                req.image_urls = None
        elif is_reference_image_mode and flat_refs:
            # Trim explicit empty image_urls after entity-only reconcile.
            req.image_urls = flat_refs
            req.ref_image_url = _pack_video_ref_urls(flat_refs)
            submit_image_urls = list(flat_refs)

        final_image_urls_for_roles = (
            list(submit_image_urls)
            if uses_submit_image_urls and submit_image_urls
            else _listify_video_ref_urls(req.image_urls or req.ref_image_url)
        )
        prompt_text = _ensure_video_frame_role_instructions(
            prompt_text,
            ref_mode=normalized_ref_mode,
            image_urls=final_image_urls_for_roles,
            last_frame_url=req.last_frame_url,
            start_frame_url=start_frame_url_for_roles,
        )
        image_tag_count = len(re.findall(r"@Image\d+", str(prompt_text or ""), flags=re.IGNORECASE))
        logger.info(
            "[GenerateVideo] prompt mapping done | shot_id=%s ref_mode=%s refs=%s lookup=%s image_tags=%s prompt_len=%s",
            req.shot_id,
            normalized_ref_mode or "<empty>",
            len(flat_refs),
            len(entity_lookup or {}),
            image_tag_count,
            len(str(prompt_text or "")),
        )
        if isinstance(req.multi_prompt, list):
            patched_multi_prompt: List[Dict[str, Any]] = []
            for item in req.multi_prompt:
                if not isinstance(item, dict):
                    continue
                patched_item = dict(item)
                item_prompt = str(patched_item.get("prompt") or "").strip()
                if item_prompt:
                    item_mapped, _ = _append_video_api_ref_mapping(
                        item_prompt,
                        flat_refs,
                        req.image_urls if uses_submit_image_urls else req.ref_image_url,
                        req.last_frame_url,
                        effective_keyframes,
                        req.ref_video_urls,
                        entity_lookup=entity_lookup or None,
                        use_prev_video=getattr(req, "use_prev_video", False),
                        provider=resolved_video_provider,
                        model=resolved_video_model,
                        preserve_submitted_refs=bool(uses_submit_image_urls or has_explicit_visual_refs),
                    )
                    patched_item["prompt"] = _ensure_video_frame_role_instructions(
                        item_mapped,
                        ref_mode=normalized_ref_mode,
                        image_urls=final_image_urls_for_roles,
                        last_frame_url=req.last_frame_url,
                        start_frame_url=start_frame_url_for_roles,
                    )
                patched_multi_prompt.append(patched_item)
            req.multi_prompt = patched_multi_prompt
            logger.info(
                "[GenerateVideo] synchronized multi_prompt mapping | shot_id=%s count=%s use_prev_video=%s ref_videos=%s",
                req.shot_id,
                len(patched_multi_prompt),
                bool(getattr(req, "use_prev_video", False)),
                len(req.ref_video_urls or []) if isinstance(req.ref_video_urls, list) else 0,
            )

        try:
            db.rollback()
        except Exception:
            pass

        video_provider_options = _build_video_provider_options(
            req,
            quality=video_quality,
            output_format=video_output_format,
            mode=normalized_mode,
        )
        if provider_callback_ticket:
            video_provider_options["_provider_callback_ticket"] = str(provider_callback_ticket).strip()
        if provider_callback_url:
            video_provider_options["_provider_callback_url"] = str(provider_callback_url).strip()
        if callable(provider_payload_callback):
            video_provider_options["_provider_payload_callback"] = provider_payload_callback
        if callable(provider_task_id_callback):
            video_provider_options["_provider_task_id_callback"] = provider_task_id_callback
        if callable(provider_result_callback):
            video_provider_options["_provider_result_callback"] = provider_result_callback
        if (force_pure_callback_mode or _is_pure_callback_mode_enabled()) and provider_callback_ticket and provider_callback_url:
            # NukoAi is poll-only: no upstream webhook. Never enable pure callback.
            from app.services.media_service import media_service as _media_svc

            if _media_svc._normalize_provider_name(resolved_video_provider, "Video") not in {
                "nukoai",
                "shishikeji",
                "ddimatuo",
                "dubai",
            }:
                video_provider_options["_pure_callback_mode"] = True
        is_kie_kling3_video = bool(
            resolved_video_provider == "kie"
            and resolved_video_model in {"kling-3.0/video", "kling3", "kling-3.0", "kling-3-0"}
        )

        if is_kie_kling3_video and resolved_project_id:
            entity_lookup = _build_project_entity_lookup(
                db, int(resolved_project_id), episode_id=resolved_episode_id
            )
            kling_prompt_candidates: List[str] = [prompt_text]
            if isinstance(req.multi_prompt, list):
                for item in req.multi_prompt:
                    if not isinstance(item, dict):
                        continue
                    shot_prompt = str(item.get("prompt") or "").strip()
                    if shot_prompt:
                        kling_prompt_candidates.append(shot_prompt)

            if context_shot:
                kling_prompt_candidates.extend([
                    str(context_shot.start_frame or "").strip(),
                    str(context_shot.end_frame or "").strip(),
                ])
                shot_tech = _parse_shot_tech(context_shot)
                if isinstance(shot_tech, dict):
                    kling_prompt_candidates.extend([
                        str(shot_tech.get("video_prompt_cn") or "").strip(),
                        str(shot_tech.get("start_frame_cn") or "").strip(),
                        str(shot_tech.get("end_frame_cn") or "").strip(),
                    ])

            auto_kling_elements = _build_auto_kling_elements(kling_prompt_candidates, entity_lookup)
            explicit_kling_count = len(video_provider_options.get("kling_elements") or []) if isinstance(video_provider_options.get("kling_elements"), list) else 0
            merged_kling_elements = _merge_kling_elements(
                video_provider_options.get("kling_elements"),
                auto_kling_elements,
            )
            if merged_kling_elements:
                video_provider_options["kling_elements"] = _align_kling_elements_to_prompt_mentions(
                    merged_kling_elements,
                    kling_prompt_candidates,
                    entity_lookup,
                )

            logger.info(
                "[GenerateVideo] Kling3 elements | shot_id=%s project_id=%s explicit=%s auto=%s merged=%s prompt_at_count=%s",
                req.shot_id,
                resolved_project_id,
                explicit_kling_count,
                len(auto_kling_elements),
                len(merged_kling_elements),
                str(prompt_text or "").count("@"),
            )

        if aspect_ratio and "aspect_ratio" not in video_provider_options:
            video_provider_options["aspect_ratio"] = str(aspect_ratio).strip()
        if resolved_video_width and resolved_video_height:
            video_provider_options["width"] = int(resolved_video_width)
            video_provider_options["height"] = int(resolved_video_height)
        if resolved_video_resolution:
            video_provider_options["resolution"] = resolved_video_resolution
        if resolved_video_image_size:
            video_provider_options["image_size"] = resolved_video_image_size

        # DdiMatuo supplier contract: images/videos/audios + duration + ratio + mode + resolution.
        try:
            from app.services.media_service import media_service as _ddi_media_svc

            is_ddimatuo_provider = (
                _ddi_media_svc._normalize_provider_name(resolved_video_provider, "Video") == "ddimatuo"
            )
        except Exception:
            is_ddimatuo_provider = str(resolved_video_provider or "").strip().lower() == "ddimatuo"
        if is_ddimatuo_provider:
            image_urls_for_ddi = video_provider_options.pop("image_urls", None)
            if not isinstance(image_urls_for_ddi, list) or not image_urls_for_ddi:
                image_urls_for_ddi = video_provider_options.pop("reference_image_urls", None)
            if isinstance(image_urls_for_ddi, list) and image_urls_for_ddi:
                video_provider_options["images"] = list(image_urls_for_ddi)
            ref_videos_for_ddi = video_provider_options.get("videos")
            if not isinstance(ref_videos_for_ddi, list) or not ref_videos_for_ddi:
                ref_videos_for_ddi = video_provider_options.pop("reference_video_urls", None)
            if not isinstance(ref_videos_for_ddi, list) or not ref_videos_for_ddi:
                raw_ref_videos = getattr(req, "ref_video_urls", None)
                if isinstance(raw_ref_videos, list) and raw_ref_videos:
                    ref_videos_for_ddi = [
                        str(item).strip() for item in raw_ref_videos if str(item).strip()
                    ]
            if isinstance(ref_videos_for_ddi, list) and ref_videos_for_ddi:
                video_provider_options["videos"] = list(ref_videos_for_ddi)
            else:
                video_provider_options.setdefault("videos", [])
            if not isinstance(video_provider_options.get("audios"), list):
                legacy_audios = video_provider_options.pop("reference_audio_urls", None)
                video_provider_options["audios"] = (
                    list(legacy_audios) if isinstance(legacy_audios, list) else []
                )
            try:
                video_provider_options["duration"] = int(
                    float(req.duration if req.duration is not None else 5)
                )
            except Exception:
                video_provider_options["duration"] = 5
            video_provider_options["duration"] = max(
                4, min(15, int(video_provider_options["duration"]))
            )
            ratio_text = str(
                video_provider_options.get("ratio")
                or video_provider_options.get("aspect")
                or video_provider_options.get("aspect_ratio")
                or aspect_ratio
                or "16:9"
            ).strip() or "16:9"
            video_provider_options["ratio"] = ratio_text
            # Prefer ref_mode; only honor options.mode when it is a DdiMatuo mode token
            # (ignore unrelated provider modes like kling std/pro).
            _ddi_mode_candidates = [
                getattr(req, "ref_mode", None),
                video_provider_options.get("mode"),
            ]
            raw_ddi_mode = ""
            for _cand in _ddi_mode_candidates:
                _norm = str(_cand or "").strip().lower().replace("-", "_").replace(" ", "_")
                if _norm in {
                    "first_last",
                    "first_last_frame",
                    "firstandlast",
                    "start_end",
                    "startend",
                    "entity_refs_start_end",
                    "flf",
                    "omni_reference",
                    "omni",
                    "native_reference",
                    "native",
                    "entity_refs",
                }:
                    raw_ddi_mode = _norm
                    break
            if raw_ddi_mode in {
                "first_last",
                "first_last_frame",
                "firstandlast",
                "start_end",
                "startend",
                "entity_refs_start_end",
                "flf",
            }:
                video_provider_options["mode"] = "first_last"
                video_provider_options["videos"] = []
                video_provider_options["audios"] = []
            else:
                video_provider_options["mode"] = "omni_reference"
            video_provider_options["resolution"] = "1080P"
            video_provider_options["watermark"] = False
            video_provider_options.pop("width", None)
            video_provider_options.pop("height", None)
            video_provider_options.pop("image_size", None)
            video_provider_options.pop("video_resolution", None)
            video_provider_options.pop("seconds", None)
            video_provider_options.pop("aspect_ratio", None)
            video_provider_options.pop("quality", None)
            video_provider_options.pop("reference_image_urls", None)
            video_provider_options.pop("reference_video_urls", None)
            video_provider_options.pop("reference_audio_urls", None)

        try:
            from app.services.media_service import media_service as _dubai_media_svc

            is_dubai_provider = (
                _dubai_media_svc._normalize_provider_name(resolved_video_provider, "Video") == "dubai"
            )
        except Exception:
            is_dubai_provider = str(resolved_video_provider or "").strip().lower() == "dubai"
        if is_dubai_provider:
            image_urls_for_dubai = video_provider_options.pop("image_urls", None)
            if not isinstance(image_urls_for_dubai, list) or not image_urls_for_dubai:
                image_urls_for_dubai = video_provider_options.pop("reference_image_urls", None)
            if not isinstance(image_urls_for_dubai, list) or not image_urls_for_dubai:
                image_urls_for_dubai = video_provider_options.get("reference_images")
            if isinstance(image_urls_for_dubai, list) and image_urls_for_dubai:
                video_provider_options["reference_images"] = list(image_urls_for_dubai)
            if not isinstance(video_provider_options.get("reference_video_urls"), list):
                raw_ref_videos = getattr(req, "ref_video_urls", None)
                if isinstance(raw_ref_videos, list) and raw_ref_videos:
                    video_provider_options["reference_video_urls"] = [
                        str(item).strip() for item in raw_ref_videos if str(item).strip()
                    ]
            if not isinstance(video_provider_options.get("reference_audio_urls"), list):
                video_provider_options["reference_audio_urls"] = []
            try:
                video_provider_options["duration"] = int(
                    float(req.duration if req.duration is not None else 4)
                )
            except Exception:
                video_provider_options["duration"] = 4
            video_provider_options["duration"] = max(
                1, min(15, int(video_provider_options["duration"]))
            )
            ratio_text = str(
                video_provider_options.get("aspect_ratio") or aspect_ratio or "16:9"
            ).strip() or "16:9"
            if ratio_text not in {"16:9", "9:16", "1:1"}:
                ratio_text = "9:16" if ratio_text in {"3:4", "2:3"} else "16:9"
            video_provider_options["aspect_ratio"] = ratio_text
            res_text = str(
                video_provider_options.get("resolution")
                or video_quality
                or ""
            ).strip().lower()
            if "480" in res_text or bool(req.draft_mode):
                video_provider_options["resolution"] = "480p"
            else:
                video_provider_options["resolution"] = "720p"

        if "sound" not in video_provider_options and resolved_sound is not None:
            video_provider_options["sound"] = bool(resolved_sound)
        if sound_capability is False:
            video_provider_options["sound"] = False
        multi_shots_capability = _read_api_capability_bool(
            pre_api_cfg,
            "multi_shots_supported",
            "supports_multi_shots",
            "supports_multi_shot",
        )
        if multi_shots_capability is False:
            video_provider_options["multi_shots"] = False
            video_provider_options.pop("multi_prompt", None)
        elif is_kie_kling3_video and bool(video_provider_options.get("multi_shots")) and sound_capability is not False:
            video_provider_options["sound"] = True
        if image_ref_limit is not None:
            image_urls = video_provider_options.get("image_urls")
            if isinstance(image_urls, list):
                video_provider_options["image_urls"] = _limit_string_list_input(image_urls, image_ref_limit)
            ref_image_urls = video_provider_options.get("reference_image_urls")
            if isinstance(ref_image_urls, list):
                video_provider_options["reference_image_urls"] = _limit_string_list_input(
                    ref_image_urls, image_ref_limit
                )
            ddi_images = video_provider_options.get("images")
            if isinstance(ddi_images, list):
                video_provider_options["images"] = _limit_string_list_input(ddi_images, image_ref_limit)
            dubai_images = video_provider_options.get("reference_images")
            if isinstance(dubai_images, list):
                video_provider_options["reference_images"] = _limit_string_list_input(
                    dubai_images, image_ref_limit
                )
        if video_ref_limit is not None:
            ref_video_urls = video_provider_options.get("reference_video_urls")
            if isinstance(ref_video_urls, list):
                video_provider_options["reference_video_urls"] = _limit_string_list_input(ref_video_urls, video_ref_limit)
            ddi_videos = video_provider_options.get("videos")
            if isinstance(ddi_videos, list):
                video_provider_options["videos"] = _limit_string_list_input(ddi_videos, video_ref_limit)
        if explicit_seed:
            video_provider_options["seed"] = int(explicit_seed)
            video_provider_options["seeds"] = int(explicit_seed)
        elif project_seed:
            video_provider_options["seed"] = int(project_seed)
            video_provider_options["seeds"] = int(project_seed)

        effective_negative_prompt, negative_prompt_source = _resolve_effective_negative_prompt(
            req.negative_prompt,
            req.asset_type,
            "video",
        )

        # Persist supplier-shaped body into Combined Payload *before* media_service,
        # so QueueAdmin never falls back to internal image_urls/duration fields.
        if is_ddimatuo_provider and callable(provider_payload_callback):
            ddi_ref_images = video_provider_options.get("images") or []
            ddi_ref_videos = video_provider_options.get("videos") or []
            ddi_ref_audios = video_provider_options.get("audios") or []
            if not isinstance(ddi_ref_images, list):
                ddi_ref_images = []
            if not isinstance(ddi_ref_videos, list):
                ddi_ref_videos = []
            if not isinstance(ddi_ref_audios, list):
                ddi_ref_audios = []
            ddi_mode = str(video_provider_options.get("mode") or "omni_reference")
            if ddi_mode == "first_last":
                ddi_ref_videos = []
                ddi_ref_audios = []
            ddi_supplier_body = {
                "model": "SD_2.0",
                "prompt": str(prompt_text or "").strip(),
                "mode": ddi_mode,
                "images": list(ddi_ref_images),
                "videos": list(ddi_ref_videos),
                "audios": list(ddi_ref_audios),
                "ratio": str(video_provider_options.get("ratio") or aspect_ratio or "16:9").strip()
                or "16:9",
                "duration": int(video_provider_options.get("duration") or 5),
                "resolution": "1080P",
                "watermark": False,
                "auto_retry_busy": bool(video_provider_options.get("auto_retry_busy", True)),
            }
            try:
                provider_payload_callback(
                    {
                        **ddi_supplier_body,
                        "provider": "ddimatuo",
                        "type": "video",
                        "method": "POST",
                        "payload": dict(ddi_supplier_body),
                        "final_submit": False,
                        "source": "video_runner_pre_submit",
                    }
                )
            except Exception as ddi_pre_payload_err:
                logger.warning(
                    "[GenerateVideo] ddimatuo pre-submit combined_payload failed | error=%s",
                    ddi_pre_payload_err,
                )

        _release_db_connection(db, "generate_video_upstream_call")

        result = await media_service.generate_video(
            prompt=prompt_text,
            negative_prompt=effective_negative_prompt,
            llm_config=runtime_llm_config,
            reference_image_url=None if uses_submit_image_urls else req.ref_image_url,
            reference_video_urls=req.ref_video_urls,
            last_frame_url=req.last_frame_url,
            duration=req.duration,
            aspect_ratio=aspect_ratio,
            keyframes=req.keyframes,
            provider_options=video_provider_options,
            user_id=current_user.id,
            user_credits=(current_user.credits or 0),
            filename_base=_build_generation_filename_base(req, db),
            # Localize/bind in this runner (early bind + bg OSS). Sync download here
            # blocks shot bind and races VideoJobPersist on the same OSS key.
            skip_download=True,
        )

        if isinstance(result, dict):
            # Promote actual supplier body from media_service even when tool_conf callback was lost.
            provider_request = (
                result.get("provider_request")
                if isinstance(result.get("provider_request"), dict)
                else None
            )
            if (
                is_ddimatuo_provider
                and provider_request
                and callable(provider_payload_callback)
            ):
                try:
                    provider_payload_callback(
                        {
                            **provider_request,
                            "provider": "ddimatuo",
                            "type": "video",
                            "method": "POST",
                            "payload": dict(provider_request),
                            "final_submit": not bool(result.get("submit_failed") or result.get("error")),
                            "submit_failed": bool(result.get("submit_failed") or result.get("error")),
                            "error": result.get("error"),
                            "source": "video_runner_result",
                        }
                    )
                except Exception as ddi_result_payload_err:
                    logger.warning(
                        "[GenerateVideo] ddimatuo result combined_payload failed | error=%s",
                        ddi_result_payload_err,
                    )
            stable_meta = result.get("metadata")
            if not isinstance(stable_meta, dict):
                stable_meta = {}
            active_seed = explicit_seed or project_seed
            if active_seed:
                stable_meta.setdefault("seed", int(active_seed))
            if effective_negative_prompt:
                stable_meta["negative_prompt_submitted"] = effective_negative_prompt
            stable_meta["negative_prompt_source"] = negative_prompt_source
            stable_meta = _enrich_media_metadata_from_generation_context(
                stable_meta,
                {
                    "provider": req.provider,
                    "model": req.model,
                    "prompt": prompt_text,
                    "negative_prompt": effective_negative_prompt,
                    "duration": req.duration,
                    "aspect_ratio": aspect_ratio,
                    "seed": active_seed,
                    "width": resolved_video_width,
                    "height": resolved_video_height,
                    "resolution": resolved_video_resolution,
                    "image_size": resolved_video_image_size,
                    "shot_id": getattr(req, "shot_id", None),
                    "project_id": getattr(req, "project_id", None),
                    "episode_id": getattr(req, "episode_id", None),
                    "scene_id": getattr(req, "scene_id", None),
                    "shot_number": getattr(req, "shot_number", None),
                    "shot_name": getattr(req, "shot_name", None),
                    "asset_type": getattr(req, "asset_type", None) or "video",
                },
            )
            result["metadata"] = stable_meta
        logger.info(
            "[GenerateVideo][Config] req_provider=%s req_model=%s runtime_llm_config=%s",
            req.provider,
            req.model,
            _sanitize_generation_runtime_config_for_log(runtime_llm_config),
        )

        pending_callback_mode = bool(isinstance(result, dict) and result.get("pending_callback"))
        if pending_callback_mode:
            # Keep reservation open until provider callback; settle/cancel with actual usage then.
            if reservation_tx_id is not None:
                settle_has_video_input = bool(
                    getattr(req, "use_prev_video", False)
                    or (
                        isinstance(getattr(req, "ref_video_urls", None), (list, tuple))
                        and len(getattr(req, "ref_video_urls") or []) > 0
                    )
                )
                result = dict(result)
                result["billing_pending"] = True
                result["reservation_tx_id"] = int(reservation_tx_id)
                result["billing_context"] = {
                    "is_token_billing": bool(_is_token_billing),
                    "estimated_tokens": int(_estimated_tokens or 0),
                    "duration": est_duration,
                    "duration_seconds": est_duration,
                    "aspect_ratio": str(aspect_ratio or "").strip() or None,
                    "draft_mode": bool(req.draft_mode),
                    "use_prev_video": bool(getattr(req, "use_prev_video", False)),
                    "shot_continuation": bool(getattr(req, "use_prev_video", False)),
                    "has_video_input": bool(_has_video_input) if "_has_video_input" in locals() else settle_has_video_input,
                    "input_duration_seconds": float(_input_duration) if (_input_duration is not None) else None,
                    "width": int(resolved_video_width) if resolved_video_width else None,
                    "height": int(resolved_video_height) if resolved_video_height else None,
                    "fps": int((_video_token_cfg or {}).get("default_fps", 24) or 24),
                    "resolution": str(resolved_video_resolution or "") or None,
                    "provider": reserve_provider or req.provider,
                    "model": reserve_model or req.model,
                    "system_api_id": reserve_system_api_id,
                    "project_id": int(resolved_project_id) if resolved_project_id else None,
                    "episode_id": int(resolved_episode_id) if resolved_episode_id else None,
                    "shot_id": int(resolved_shot_id) if resolved_shot_id else None,
                    "is_seedance_2": bool((_video_token_cfg or {}).get("is_seedance_2"))
                    or billing_service.is_seedance_2_model(reserve_provider, reserve_model),
                    "draft_token_coefficient": float(
                        (_video_token_cfg or {}).get("draft_token_coefficient", 1.0) or 1.0
                    ),
                }
                logger.info(
                    "[GenerateVideo] callback pending; reservation kept open | reservation_tx_id=%s token_billing=%s estimated_tokens=%s",
                    reservation_tx_id,
                    bool(_is_token_billing),
                    int(_estimated_tokens or 0),
                )
                reservation_tx = None
                reservation_tx_id = None
            return result

        if "error" in result:
             detail = _format_generation_failure_detail(result, "Video generation failed")
             
             # Log the full error detail for debugging
             logger.error(f"[GenerateVideo] Failed: {detail}") 
             billing_service.log_failed_transaction(db, current_user.id, "video_gen", req.provider, req.model, detail)
             
             raise HTTPException(status_code=400, detail=detail)

        if not result.get("url"):
            detail = "Video generation returned no URL"
            if isinstance(result.get("metadata"), dict) and result["metadata"].get("raw"):
                try:
                    raw_status = result["metadata"]["raw"].get("status") or result["metadata"]["raw"].get("state")
                    if raw_status:
                        detail = f"{detail}: upstream status={raw_status}"
                except Exception:
                    pass
            logger.error("[GenerateVideo] Failed: %s | result=%s", detail, result)
            billing_service.log_failed_transaction(db, current_user.id, "video_gen", req.provider, req.model, detail)
            raise HTTPException(status_code=502, detail=detail)

        final_meta = result.get("metadata") if isinstance(result, dict) else {}
        final_meta = final_meta if isinstance(final_meta, dict) else {}
        final_smart_meta = final_meta.get("smart_routing") if isinstance(final_meta.get("smart_routing"), dict) else {}
        logger.info(
            "[GenerateVideo] Success | user_id=%s project_id=%s episode_id=%s shot_id=%s provider=%s model=%s url=%s",
            current_user.id,
            getattr(req, "project_id", None),
            getattr(req, "episode_id", None),
            getattr(req, "shot_id", None),
            final_meta.get("provider") or final_smart_meta.get("provider") or req.provider,
            final_meta.get("model") or final_smart_meta.get("model") or req.model,
            result.get("url"),
        )

        _log_api_switch_regenerate_if_needed(
            db=db,
            current_user=current_user,
            req=req,
            result=result,
            media_type="video",
        )

        # Register asset + bind shot for direct-success providers (callback mode handles this in finalize path).
        # Publish provisional provider URL immediately so frontend job-poll can finish before OSS completes
        # (same pattern as image generation background localization).
        if result.get("url"):
            temp_url = str(result.get("url") or "").strip()
            if temp_url:
                stable_job_id = str(job_id or "").strip()
                provisional_meta = dict(result.get("metadata") or {})
                provisional_meta.setdefault("oss_persist_pending", True)
                _publish_provisional_video_success(
                    stable_job_id,
                    url=temp_url,
                    metadata=provisional_meta,
                    callback_ticket=provider_callback_ticket,
                    mark_queue_completed=True,
                )

                # Backup bind if provisional callback bind missed (e.g. shot_id not hydrated yet).
                try:
                    early_bind_url, early_ephemeral, early_meta = _resolve_video_bind_url(
                        raw_url=temp_url,
                        normalized_url=temp_url,
                        normalized_meta=dict(provisional_meta),
                    )
                    if early_bind_url:
                        early_req = req
                        if not str(getattr(req, "asset_type", None) or "").strip():
                            early_req = req.model_copy(update={"asset_type": "video"}) if hasattr(req, "model_copy") else req
                        await asyncio.to_thread(
                            _register_asset_helper,
                            db,
                            current_user.id,
                            early_bind_url,
                            early_req,
                            early_meta,
                        )
                        await asyncio.to_thread(
                            _bind_generated_media_to_shot,
                            db,
                            current_user,
                            early_req,
                            early_bind_url,
                            False,
                            early_meta,
                        )
                        logger.info(
                            "[GenerateVideo] early shot bind with provider url | job_id=%s url=%s ephemeral=%s",
                            stable_job_id or None,
                            early_bind_url.split("?", 1)[0],
                            bool(early_ephemeral),
                        )
                except Exception:
                    logger.exception(
                        "[GenerateVideo] early shot bind failed | job_id=%s",
                        stable_job_id or None,
                    )

                skip_remote_localization = _is_provider_direct_oss_url(temp_url, provisional_meta)
                needs_remote_localize = (
                    temp_url.lower().startswith(("http://", "https://"))
                    and not skip_remote_localization
                )

                if needs_remote_localize:
                    filename_base = _build_generation_filename_base(req, db)
                    user_id_for_bg = int(getattr(current_user, "id", 0) or 0)

                    async def _bg_video_upload_and_update(
                        *,
                        raw_url: str,
                        meta: Optional[dict],
                        fname_base: Optional[str],
                        req_obj: Any,
                        uid: int,
                        jid: str,
                    ) -> None:
                        user_snapshot = None
                        bg_db = SessionLocal()
                        try:
                            bg_user = bg_db.query(User).filter(User.id == uid).first()
                            if not bg_user:
                                logger.error(
                                    "[GenerateVideo] bg persist skipped; user missing | job_id=%s user_id=%s",
                                    jid or None,
                                    uid,
                                )
                                if jid:
                                    _set_video_job(
                                        jid,
                                        status="succeeded",
                                        finished_at=now_bj_iso(),
                                        upstream_submit_state="completed",
                                        error=None,
                                    )
                                return
                            user_snapshot = _snapshot_user_principal(bg_user)
                        finally:
                            bg_db.close()

                        if user_snapshot is None:
                            return

                        try:
                            logger.info(
                                "[GenerateVideo] bg OSS persist start | job_id=%s user_id=%s url=%s",
                                jid or None,
                                uid,
                                str(raw_url).split("?", 1)[0],
                            )
                            norm_url, norm_meta, oss_uploaded = await asyncio.to_thread(
                                _persist_remote_video_result,
                                user_snapshot,
                                raw_url,
                                meta,
                                filename_base=fname_base,
                                db=None,
                            )
                            final_url = str(norm_url or raw_url).strip()
                            final_meta = dict(norm_meta if norm_meta is not None else (meta or {}))
                            if jid:
                                final_meta["idempotency_key"] = jid
                            final_meta.pop("oss_persist_pending", None)
                        except Exception:
                            logger.exception(
                                "[GenerateVideo] bg OSS persist failed | job_id=%s url=%s",
                                jid or None,
                                str(raw_url).split("?", 1)[0],
                            )
                            if jid:
                                try:
                                    _set_video_job(
                                        jid,
                                        status="succeeded",
                                        finished_at=now_bj_iso(),
                                        upstream_submit_state="completed",
                                        error=None,
                                    )
                                except Exception:
                                    pass
                            return

                        bg_db = SessionLocal()
                        try:
                            bg_user = bg_db.query(User).filter(User.id == uid).first()
                            if not bg_user:
                                if jid:
                                    _set_video_job(
                                        jid,
                                        status="succeeded",
                                        finished_at=now_bj_iso(),
                                        upstream_submit_state="completed",
                                        error=None,
                                    )
                                return

                            bind_url, ephemeral_binding, final_meta = _resolve_video_bind_url(
                                raw_url=raw_url,
                                normalized_url=final_url,
                                normalized_meta=final_meta,
                                oss_uploaded=bool(oss_uploaded),
                                db=bg_db,
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
                                await asyncio.to_thread(
                                    _bind_generated_media_to_shot,
                                    bg_db,
                                    bg_user,
                                    req_obj,
                                    bind_url,
                                    bool(oss_uploaded and not ephemeral_binding),
                                    final_meta,
                                )

                            if jid:
                                with VIDEO_JOB_LOCK:
                                    job_snapshot = dict(VIDEO_JOB_STORE.get(jid) or {})
                                updated_res = dict(job_snapshot.get("result") or {"url": raw_url, "metadata": meta or {}})
                                if bind_url:
                                    updated_res["url"] = bind_url
                                    updated_meta = dict(final_meta)
                                    updated_meta.pop("oss_persist_pending", None)
                                    updated_meta.pop("bg_persist_owned", None)
                                    updated_res["metadata"] = updated_meta
                                _set_video_job(
                                    jid,
                                    result=updated_res,
                                    status="succeeded",
                                    finished_at=now_bj_iso(),
                                    upstream_submit_state="completed",
                                    error=None,
                                )
                                logger.info(
                                    "[GenerateVideo] bg OSS persist done | job_id=%s oss_uploaded=%s bind_url=%s",
                                    jid,
                                    bool(oss_uploaded),
                                    str(bind_url or final_url or raw_url).split("?", 1)[0],
                                )
                        except Exception:
                            logger.exception(
                                "[GenerateVideo] bg OSS bind failed | job_id=%s url=%s",
                                jid or None,
                                str(raw_url).split("?", 1)[0],
                            )
                            # Keep provisional provider URL; do not flip a visible success into failed.
                            if jid:
                                try:
                                    _set_video_job(
                                        jid,
                                        status="succeeded",
                                        finished_at=now_bj_iso(),
                                        upstream_submit_state="completed",
                                        error=None,
                                    )
                                except Exception:
                                    pass
                        finally:
                            bg_db.close()

                    asyncio.create_task(
                        _bg_video_upload_and_update(
                            raw_url=temp_url,
                            meta=provisional_meta,
                            fname_base=filename_base,
                            req_obj=req,
                            uid=user_id_for_bg,
                            jid=stable_job_id,
                        )
                    )
                else:
                    filename_base = _build_generation_filename_base(req, db)
                    if temp_url.lower().startswith(("http://", "https://")):
                        norm_url, norm_meta, oss_uploaded = await asyncio.to_thread(
                            _persist_remote_video_result,
                            current_user,
                            temp_url,
                            result.get("metadata"),
                            filename_base=filename_base,
                        )
                    else:
                        norm_url = temp_url
                        norm_meta = dict(result.get("metadata") or {})
                        oss_uploaded = _oss_upload_succeeded_for_url(norm_url, norm_meta)

                    final_url = str(norm_url or temp_url).strip()
                    final_meta = dict(norm_meta if norm_meta is not None else (result.get("metadata") or {}))

                    if final_url and final_url != temp_url:
                        result["url"] = final_url
                        result["metadata"] = final_meta

                    bind_url, ephemeral_binding, final_meta = _resolve_video_bind_url(
                        raw_url=temp_url,
                        normalized_url=final_url,
                        normalized_meta=final_meta,
                    )
                    if bind_url:
                        if bind_url != temp_url or ephemeral_binding:
                            result["url"] = bind_url
                            result["metadata"] = final_meta
                        await asyncio.to_thread(_register_asset_helper, db, current_user.id, bind_url, req, final_meta)
                        await asyncio.to_thread(
                            _bind_generated_media_to_shot,
                            db,
                            current_user,
                            req,
                            bind_url,
                            bool(oss_uploaded and not ephemeral_binding),
                            final_meta,
                        )

        if reservation_tx_id is not None:
            final_meta = result.get("metadata") if isinstance(result, dict) else {}
            final_meta = final_meta if isinstance(final_meta, dict) else {}
            smart_meta = final_meta.get("smart_routing") if isinstance(final_meta.get("smart_routing"), dict) else {}

            final_provider = str(
                final_meta.get("provider")
                or smart_meta.get("provider")
                or req.provider
                or ""
            ).strip()
            final_model = str(
                final_meta.get("model")
                or smart_meta.get("model")
                or req.model
                or ""
            ).strip()
            final_system_api_id_raw = (
                final_meta.get("system_api_id")
                if final_meta.get("system_api_id") is not None
                else smart_meta.get("system_api_id")
            )
            try:
                final_system_api_id = int(final_system_api_id_raw) if final_system_api_id_raw is not None else None
            except Exception:
                final_system_api_id = None

            if _is_token_billing:
                # Prefer actual usage from provider task query (e.g. Ark Seedance GET /tasks/{id}.usage).
                usage = _extract_provider_usage_from_metadata(final_meta)
                actual_tokens = _resolve_usage_token_total(usage)
                token_source = "api_usage" if actual_tokens > 0 else "estimate"
                settle_has_video_input = bool(
                    getattr(req, "use_prev_video", False)
                    or (isinstance(getattr(req, "ref_video_urls", None), (list, tuple)) and len(getattr(req, "ref_video_urls") or []) > 0)
                )
                settle_details = {
                    "status": "SETTLED",
                    "billing_mode": "ACTUAL",
                    "draft_mode": bool(req.draft_mode),
                    "draft": bool(req.draft_mode),
                    "use_prev_video": bool(getattr(req, "use_prev_video", False)),
                    "shot_continuation": bool(getattr(req, "use_prev_video", False)),
                    "has_video_input": settle_has_video_input,
                    "width": int(resolved_video_width) if resolved_video_width else None,
                    "height": int(resolved_video_height) if resolved_video_height else None,
                    "fps": int((_video_token_cfg or {}).get("default_fps", 24) or 24),
                }
                if actual_tokens <= 0:
                    # Recompute via Seedance 2.0 / video-token fallback formula when provider omits usage.
                    settle_duration = max(5, int(req.duration or 5)) if (req.duration and req.duration > 0) else 5
                    settle_estimate = billing_service.estimate_video_token_usage(
                        width=int(settle_details.get("width") or (_video_token_cfg or {}).get("default_width", 1280) or 1280),
                        height=int(settle_details.get("height") or (_video_token_cfg or {}).get("default_height", 720) or 720),
                        fps=int(settle_details.get("fps") or 24),
                        output_duration_seconds=settle_duration,
                        has_video_input=settle_has_video_input,
                        input_duration_seconds=_input_duration,
                        draft_token_coefficient=float(
                            (_video_token_cfg or {}).get("draft_token_coefficient", 1.0) or 1.0
                        ),
                        method=(
                            "seedance2_video_token_formula"
                            if ((_video_token_cfg or {}).get("is_seedance_2") or billing_service.is_seedance_2_model(final_provider, final_model))
                            else "video_token_formula"
                        ),
                    )
                    actual_tokens = int(settle_estimate.get("tokens") or _estimated_tokens or 0)
                    settle_details["video_token_estimate"] = settle_estimate
                    settle_details["estimation_method"] = settle_estimate.get("estimation_method")
                    settle_details["input_duration_seconds"] = settle_estimate.get("input_duration_seconds")
                else:
                    settle_details["completion_tokens"] = _safe_int_token(
                        usage.get("completion_tokens") or usage.get("output_tokens") or actual_tokens
                    )
                settle_details["output_tokens"] = actual_tokens
                settle_details["total_tokens"] = actual_tokens
                settle_details["token_source"] = token_source
            else:
                settle_details = {
                    "duration": est_duration,
                    "duration_seconds": est_duration,
                    "status": "SETTLED",
                    "billing_mode": "ACTUAL",
                    "draft_mode": bool(req.draft_mode),
                    "draft": bool(req.draft_mode),
                    "use_prev_video": bool(getattr(req, "use_prev_video", False)),
                    "shot_continuation": bool(getattr(req, "use_prev_video", False)),
                    "has_video_input": bool(_has_video_input),
                }
                if _input_duration is not None:
                    settle_details["input_duration_seconds"] = float(_input_duration)
                    settle_details["input_duration"] = float(_input_duration)

                # KIE may return creditsConsumed on poll/callback metadata.
                try:
                    from app.services.billing_pricing import resolve_provider_kie_credits

                    _kie_usage = _extract_provider_usage_from_metadata(final_meta)
                    _kie_credits = float(resolve_provider_kie_credits(_kie_usage) or resolve_provider_kie_credits(final_meta) or 0.0)
                except Exception:
                    _kie_credits = 0.0
                if _kie_credits <= 0:
                    _kie_credits = await _maybe_refresh_kie_credits_from_record_info(final_meta, final_provider)
                if _kie_credits > 0:
                    settle_details["kie_credits_consumed"] = _kie_credits
                    settle_details["credits_consumed"] = _kie_credits
                    settle_details["creditsConsumed"] = _kie_credits
                    settle_details["billing_basis"] = "provider_kie_credits"

                raw_meta = final_meta.get("raw") if isinstance(final_meta.get("raw"), dict) else {}
                raw_payload = raw_meta.get("payload") if isinstance(raw_meta.get("payload"), dict) else {}
                raw_input = raw_payload.get("input") if isinstance(raw_payload.get("input"), dict) else {}

                final_width = (
                    _to_positive_int_or_none(final_meta.get("width"))
                    or _to_positive_int_or_none(final_meta.get("output_width"))
                    or _to_positive_int_or_none(raw_meta.get("width"))
                    or _to_positive_int_or_none(raw_meta.get("output_width"))
                    or _to_positive_int_or_none(raw_input.get("width"))
                    or _to_positive_int_or_none(resolved_video_width)
                )
                final_height = (
                    _to_positive_int_or_none(final_meta.get("height"))
                    or _to_positive_int_or_none(final_meta.get("output_height"))
                    or _to_positive_int_or_none(raw_meta.get("height"))
                    or _to_positive_int_or_none(raw_meta.get("output_height"))
                    or _to_positive_int_or_none(raw_input.get("height"))
                    or _to_positive_int_or_none(resolved_video_height)
                )
                final_resolution = str(
                    final_meta.get("resolution")
                    or raw_meta.get("resolution")
                    or raw_input.get("resolution")
                    or (resolved_video_resolution or "")
                ).strip()
                if (not final_width or not final_height) and final_resolution:
                    parsed_w, parsed_h = _parse_resolution_dims(final_resolution)
                    if parsed_w and not final_width:
                        final_width = int(parsed_w)
                    if parsed_h and not final_height:
                        final_height = int(parsed_h)

                if final_width:
                    settle_details["width"] = int(final_width)
                if final_height:
                    settle_details["height"] = int(final_height)
                if final_resolution:
                    settle_details["resolution"] = final_resolution

                final_has_audio = final_meta.get("has_audio") if isinstance(final_meta, dict) else None
                if final_has_audio is None and resolved_sound is not None:
                    final_has_audio = bool(resolved_sound)
                if final_has_audio is not None:
                    settle_details["has_audio"] = bool(final_has_audio)

            if req.duration is not None:
                settle_details["duration"] = req.duration
                settle_details["duration_seconds"] = req.duration
            if aspect_ratio:
                settle_details["aspect_ratio"] = str(aspect_ratio).strip()
            if normalized_mode:
                settle_details["mode"] = normalized_mode
                settle_details["generation_mode"] = normalized_mode
            if resolved_sound is not None and settle_details.get("has_audio") is None:
                settle_details["has_audio"] = bool(resolved_sound)
            if resolved_project_id:
                settle_details["project_id"] = int(resolved_project_id)
            if resolved_episode_id:
                settle_details["episode_id"] = int(resolved_episode_id)
            if resolved_shot_id:
                settle_details["shot_id"] = int(resolved_shot_id)

            provider_usage = _extract_provider_usage_from_metadata(final_meta)
            if provider_usage:
                settle_details["provider_usage"] = provider_usage
                settle_details["usage_source"] = str(final_meta.get("usage_source") or "provider").strip() or "provider"
                # DdiMatuo / money providers: promote cost_total_cents → audit supplier amount.
                for money_key in (
                    "cost_total_cents",
                    "costTotalCents",
                    "consumeMoney",
                    "consume_money",
                    "currency",
                    "billing_status",
                    "billing_unit",
                ):
                    if settle_details.get(money_key) in (None, "") and provider_usage.get(money_key) not in (None, ""):
                        settle_details[money_key] = provider_usage.get(money_key)
                if settle_details.get("cost_total_cents") not in (None, ""):
                    settle_details.setdefault("billing_basis", "provider_cost_total_cents")
                    if settle_details.get("consumeMoney") in (None, ""):
                        try:
                            settle_details["consumeMoney"] = float(settle_details.get("cost_total_cents") or 0) / 100.0
                        except Exception:
                            pass
                elif final_meta.get("cost_total_cents") not in (None, ""):
                    settle_details["cost_total_cents"] = final_meta.get("cost_total_cents")
                    settle_details.setdefault("billing_basis", "provider_cost_total_cents")
                    if settle_details.get("consumeMoney") in (None, ""):
                        try:
                            settle_details["consumeMoney"] = float(final_meta.get("cost_total_cents") or 0) / 100.0
                        except Exception:
                            pass

            if final_provider:
                settle_details["provider"] = final_provider
            if final_model:
                settle_details["model"] = final_model
            if final_system_api_id is not None:
                settle_details["system_api_id"] = final_system_api_id
            if smart_meta:
                settle_details["smart_routing"] = smart_meta

            settle_details = _merge_provider_task_ids_into_settle(
                settle_details,
                final_meta if isinstance(final_meta, dict) else {},
                smart_meta if isinstance(smart_meta, dict) else {},
                result if isinstance(result, dict) else {},
            )

            billing_service.settle_reservation(
                db,
                reservation_tx_id,
                settle_details,
            )
            reservation_tx = None
            reservation_tx_id = None
            
        # Register last frame as asset if present
        try:
            last_frame_url_val = (final_meta or {}).get("last_frame_url")
            if last_frame_url_val and resolved_shot_id:
                dummy_req = type("DummyReq", (), {
                    "project_id": resolved_project_id,
                    "target_type": "shot_entity",
                     "target_id": resolved_shot_id,
                    "role": "last_frame"
                })()
                
                # Make a distinct identifier
                lf_meta = {"provider": final_provider, "model": final_model, "is_last_frame": True, "source_shot_id": resolved_shot_id}
                
                new_asset_id = _register_asset_helper(db, current_user.id, last_frame_url_val, dummy_req, source_metadata=lf_meta)
                if new_asset_id:
                    logger.info(f"Registered last_frame_url as asset {new_asset_id} for shot {resolved_shot_id}")

                # Propagate to next shot if same environment
                current_shot = db.query(Shot).filter(Shot.id == resolved_shot_id).first()
                if current_shot:
                    from app.models.all_models import Scene
                    next_shot = db.query(Shot).filter(
                        Shot.episode_id == current_shot.episode_id,
                        Shot.id > current_shot.id,
                        Shot.is_deleted == False
                    ).order_by(Shot.id.asc()).first()

                    if next_shot:
                        current_scene = db.query(Scene).filter(Scene.id == current_shot.scene_id).first()
                        next_scene = db.query(Scene).filter(Scene.id == next_shot.scene_id).first()

                        env_current = (current_scene.environment_name or "").strip() if current_scene else ""
                        env_next = (next_scene.environment_name or "").strip() if next_scene else ""

                        is_same_env = False
                        if current_scene and next_scene and current_scene.id == next_scene.id:
                            is_same_env = True
                        elif env_current and env_next and env_current == env_next:
                            # It has environment_name and they exactly match
                            is_same_env = True

                        logger.info(f"[LastFramePropagation] Evaluating propagation. current_shot={current_shot.id}, next_shot={next_shot.id}, is_same_env={is_same_env}, env_current='{env_current}', env_next='{env_next}'")

                        if is_same_env:
                            logger.info(f"[LastFramePropagation] Environment matches. Propagating last_frame_url to shot {next_shot.id} as start frame.")
                            next_shot.image_url = last_frame_url_val
                            db.commit()
                            
                            try:
                                from app.services.system_log_service import log_action
                                username = str(getattr(current_user, "username", ""))
                                log_action(
                                    db, 
                                    current_user.id, 
                                    username, 
                                    "视频尾帧连贯", 
                                    f"识别到镜头 {current_shot.shot_id} 与相邻镜头 {next_shot.shot_id} 共处同一环境「{env_current}」，已自动将镜头 {current_shot.shot_id} 生成的尾帧继承为下一镜头的起始帧。尾帧图片: {last_frame_url_val}"
                                )
                            except Exception as system_log_err:
                                logger.warning(f"Failed to record system log for last frame propagation: {system_log_err}")

        except Exception as lf_err:
             logger.warning(f"Failed to register/propagate last_frame_url as asset: {lf_err}")

        return result
    except asyncio.CancelledError:
        if reservation_tx_id is not None:
            try:
                billing_service.cancel_reservation(db, reservation_tx_id, "video generation cancelled")
                reservation_tx_id = None
            except Exception:
                pass
        raise
    except HTTPException as e:
        if reservation_tx_id is not None:
            try:
                billing_service.cancel_reservation(db, reservation_tx_id, str(e.detail))
                reservation_tx_id = None
            except Exception:
                pass
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        if reservation_tx_id is not None:
            try:
                billing_service.cancel_reservation(db, reservation_tx_id, str(e))
                reservation_tx_id = None
            except Exception:
                pass
        billing_service.log_failed_transaction(db, current_user.id, "video_gen", req.provider, req.model, str(e))
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


# _set_video_job moved to app.services.generation_runtime.job_store


async def _run_generate_video_job(
    job_id: str,
    user_id: int,
    req_payload: Dict[str, Any],
    provider_callback_ticket: Optional[str] = None,
    provider_callback_url: Optional[str] = None,
)-> Dict[str, Any]:
    from app.services.generation_task_queue import mark_generation_task_status_external, patch_generation_task_payload

    db = SessionLocal()
    callback_url = _resolve_callback_url_from_payload(req_payload)
    req_provider = str(req_payload.get("provider") or "").strip() or None
    req_model = str(req_payload.get("model") or "").strip() or None

    def _on_provider_task_id(task_id: str) -> None:
        normalized_task_id = str(task_id or "").strip()
        if not normalized_task_id:
            return
        _set_video_job(
            job_id,
            provider_task_id=normalized_task_id,
            task_id=normalized_task_id,
            taskId=normalized_task_id,
            # Leave "submit" for pure-callback waiters; poll-only providers spend minutes here.
            status="running",
            upstream_submit_state="polling",
            error=None,
        )
        try:
            patch_generation_task_payload(
                job_id,
                {
                    "provider_task_id": normalized_task_id,
                    "task_id": normalized_task_id,
                    "taskId": normalized_task_id,
                },
            )
        except Exception:
            logger.exception(
                "[VideoJob] patch provider taskId into queue payload failed | job_id=%s provider_task_id=%s",
                job_id,
                normalized_task_id,
            )
        try:
            mark_generation_task_status_external(job_id, status="running", error=None)
        except Exception:
            logger.exception(
                "[VideoJob] mark queue running after provider task link failed | job_id=%s",
                job_id,
            )
        try:
            from app.services.generation_runtime.job_store import VIDEO_JOB_LOCK, VIDEO_JOB_STORE

            with VIDEO_JOB_LOCK:
                current = dict(VIDEO_JOB_STORE.get(job_id) or {})
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
                "[VideoJob] persist provider taskId to reservation failed | job_id=%s provider_task_id=%s",
                job_id,
                normalized_task_id,
            )
        logger.info(
            "[VideoJob] provider task linked | job_id=%s provider=%s provider_task_id=%s",
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
        patch_fields = {
            "combined_payload": payload_snapshot,
            "final_provider_payload": payload_snapshot,
            "final_provider_payload_at": now_bj_iso(),
        }
        nested_task_id = str(
            payload_snapshot.get("task_id")
            or payload_snapshot.get("taskId")
            or payload_snapshot.get("provider_task_id")
            or payload_snapshot.get("id")
            or ""
        ).strip()
        if not nested_task_id:
            submit_raw = payload_snapshot.get("submit_raw") if isinstance(payload_snapshot.get("submit_raw"), dict) else {}
            submit_data = submit_raw.get("data") if isinstance(submit_raw.get("data"), dict) else {}
            nested_task_id = str(
                submit_data.get("id")
                or submit_data.get("task_id")
                or submit_raw.get("id")
                or ""
            ).strip()
        if nested_task_id:
            patch_fields["provider_task_id"] = nested_task_id
            patch_fields["task_id"] = nested_task_id
            patch_fields["taskId"] = nested_task_id
            _on_provider_task_id(nested_task_id)
        query_endpoint = str(payload_snapshot.get("query_endpoint") or payload_snapshot.get("queryEndpoint") or "").strip()
        if query_endpoint:
            patch_fields["query_endpoint"] = query_endpoint
        # Persist provider payload markers onto the video job itself (not only the queue row),
        # so re-download can recover provider_task_id after workers restart.
        try:
            job_patch = {
                "final_provider_payload": payload_snapshot,
                "final_provider_payload_at": patch_fields.get("final_provider_payload_at"),
            }
            if nested_task_id:
                job_patch["provider_task_id"] = nested_task_id
                job_patch["task_id"] = nested_task_id
                job_patch["taskId"] = nested_task_id
            if query_endpoint:
                job_patch["query_endpoint"] = query_endpoint
            _set_video_job(job_id, **job_patch)
        except Exception:
            logger.exception(
                "[VideoJob] persist provider payload onto job failed | job_id=%s provider_task_id=%s",
                job_id,
                nested_task_id or None,
            )
        patch_generation_task_payload(job_id, patch_fields)
        logger.info(
            "[VideoJob] final provider payload recorded | job_id=%s provider=%s model=%s provider_task_id=%s",
            job_id,
            req_provider or "unknown",
            req_model or "unknown",
            nested_task_id or None,
        )

    def _on_provider_result(result_snapshot: Any) -> None:
        if not isinstance(result_snapshot, dict):
            return
        result_url = str(result_snapshot.get("url") or "").strip()
        if not result_url:
            return
        result_meta = result_snapshot.get("metadata") if isinstance(result_snapshot.get("metadata"), dict) else {}
        _publish_provisional_video_success(
            job_id,
            url=result_url,
            metadata=result_meta,
            callback_ticket=provider_callback_ticket,
            mark_queue_completed=True,
        )

    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            _set_video_job(
                job_id,
                status="failed",
                finished_at=now_bj_iso(),
                error="User not found",
            )
            mark_generation_task_status_external(job_id, status="failed", error="User not found")
            return {"defer_completion": False}
        user_principal = _snapshot_user_principal(user)

        req_obj = VideoGenerationRequest(**req_payload)
        _set_video_job(
            job_id,
            status="submit",
            started_at=now_bj_iso(),
            provider=req_provider,
            model=req_model,
            prompt=req_payload.get("prompt"),
            duration=req_payload.get("duration"),
            aspect_ratio=req_payload.get("aspect_ratio"),
        )
        logger.info(
            "[VideoJob] started | job_id=%s user_id=%s provider=%s model=%s callback_ticket=%s",
            job_id,
            user_id,
            req_provider,
            req_model,
            provider_callback_ticket or None,
        )
        _release_db_connection(db, "video_job_wait_for_generation")
        result = await asyncio.wait_for(
            _run_generate_video(
                req_obj,
                user_principal,
                db,
                provider_callback_ticket=provider_callback_ticket,
                provider_callback_url=provider_callback_url,
                force_pure_callback_mode=_is_pure_callback_mode_enabled(),
                provider_payload_callback=_on_provider_payload,
                provider_task_id_callback=_on_provider_task_id,
                provider_result_callback=_on_provider_result,
                job_id=job_id,
            ),
            timeout=VIDEO_JOB_MAX_RUNNING_SECONDS,
        )
        if isinstance(result, dict) and result.get("pending_callback"):
            # Hydrate from file/task — multi-worker callbacks may have already succeeded
            # on another instance while this worker still has stale in-memory status.
            current_job = _hydrate_video_job_record(job_id, None)
            current_status = _normalize_generation_status(current_job.get("status"))
            current_result_url = _extract_job_result_url(current_job.get("result"))
            callback_payload = {}
            if provider_callback_ticket:
                callback_payload = _get_generation_callback_payload(provider_callback_ticket) or {}
            # Callback store may prove success even if local job status lagged.
            if (not current_result_url) and callback_payload:
                built = _build_result_from_provider_callback(
                    callback_payload,
                    fallback_provider=req_provider,
                    fallback_model=req_model,
                )
                if built and _extract_job_result_url(built):
                    current_result_url = _extract_job_result_url(built)
                    if current_status not in {"succeeded", "completed", "done"}:
                        current_status = "succeeded"

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

            already_settled = bool(current_job.get("billing_settled"))
            callback_already_done = (
                current_status in {"succeeded", "completed", "done"} and bool(current_result_url)
            ) or bool(callback_payload and _extract_job_result_url(
                _build_result_from_provider_callback(callback_payload) or {}
            ))

            # Callback may finalize before submit returns. Attach reservation then settle.
            # Never downgrade a succeeded job back to waiting_callback (multi-worker race).
            if callback_already_done or already_settled:
                attach_fields: Dict[str, Any] = {
                    "billing_context": billing_context,
                    "upstream_submit_state": "completed",
                    "callback_submit_retries": 0,
                    "callback_retry_at": None,
                }
                if reservation_tx_id_pending:
                    attach_fields["reservation_tx_id"] = int(reservation_tx_id_pending)
                    attach_fields["billing_pending"] = not already_settled
                if provider_task_id and not _extract_job_provider_task_id(current_job):
                    attach_fields["provider_task_id"] = provider_task_id
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
                            "[VideoJob] persist provider taskId to reservation failed | job_id=%s reservation_tx_id=%s provider_task_id=%s",
                            job_id,
                            reservation_tx_id_pending,
                            provider_task_id,
                        )
                if current_status not in {"succeeded", "completed", "done"} and current_result_url:
                    attach_fields["status"] = "succeeded"
                if attach_fields:
                    _set_video_job(job_id, **attach_fields)
                current_job = _hydrate_video_job_record(job_id, None)
                if not already_settled:
                    await _settle_or_cancel_video_job_billing_from_callback(
                        job_id,
                        current_job,
                        callback_payload,
                    )
                logger.info(
                    "[VideoJob] settled reservation after callback-before-return race | job_id=%s reservation_tx_id=%s provider_task_id=%s already_settled=%s",
                    job_id,
                    reservation_tx_id_pending,
                    _extract_job_provider_task_id(current_job) or provider_task_id or None,
                    already_settled,
                )
                return {"defer_completion": False}

            if not provider_task_id:
                detail = "Video submit returned pending_callback without provider task id"
                logger.error("[VideoJob] %s | job_id=%s", detail, job_id)
                _set_video_job(
                    job_id,
                    status="failed",
                    finished_at=now_bj_iso(),
                    error=detail,
                    upstream_submit_state="submit_missing_task_id",
                )
                with VIDEO_JOB_LOCK:
                    current_job = dict(VIDEO_JOB_STORE.get(job_id) or {})
                _cancel_video_job_pending_reservation(job_id, current_job, detail)
                mark_generation_task_status_external(job_id, status="failed", error=detail)
                return {"defer_completion": False}

            update_fields: Dict[str, Any] = {
                "status": "waiting_callback",
                "error": None,
                "upstream_submit_state": "callback_pending",
                "billing_pending": bool(result.get("billing_pending") and reservation_tx_id_pending),
                "billing_context": billing_context,
                "provider_task_id": provider_task_id,
            }
            # Do not clobber billing_settled=True from another worker.
            if not already_settled:
                update_fields["billing_settled"] = False
            if reservation_tx_id_pending:
                update_fields["reservation_tx_id"] = int(reservation_tx_id_pending)
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
                        "[VideoJob] persist provider taskId on waiting_callback failed | job_id=%s reservation_tx_id=%s provider_task_id=%s",
                        job_id,
                        reservation_tx_id_pending,
                        provider_task_id,
                    )
            _set_video_job(job_id, **update_fields)
            mark_generation_task_status_external(job_id, status="waiting_callback", error=None)
            return {"defer_completion": True}
        with VIDEO_JOB_LOCK:
            _current_video_job = dict(VIDEO_JOB_STORE.get(job_id) or {})
        _status_to_set = "storing_asset" if _current_video_job.get("status") == "storing_asset" else "succeeded"
        _finished_at_val = None if _status_to_set == "storing_asset" else now_bj_iso()
        _success_fields: Dict[str, Any] = {
            "status": _status_to_set,
            "finished_at": _finished_at_val,
            "result": result,
            "error": None,
            "callback_submit_retries": 0,
            "callback_retry_at": None,
        }
        if _status_to_set == "succeeded":
            _success_fields["upstream_submit_state"] = "completed"
        _set_video_job(job_id, **_success_fields)
        # Queue completes once provider URL is available; OSS may still finish in background.
        mark_generation_task_status_external(job_id, status="completed", error=None)
        return {"defer_completion": False}
    except asyncio.TimeoutError:
        with VIDEO_JOB_LOCK:
            current_job = dict(VIDEO_JOB_STORE.get(job_id) or {})
        current_status = _normalize_generation_status(current_job.get("status"))
        current_result_url = _extract_job_result_url(current_job.get("result"))
        if current_status in {"succeeded", "storing_asset"} and current_result_url:
            logger.info(
                "[VideoJob] timeout ignored after result finalization | job_id=%s status=%s provider_task_id=%s result_url=%s",
                job_id,
                current_status,
                _extract_job_provider_task_id(current_job) or None,
                current_result_url,
            )
            if current_status == "storing_asset":
                # Provider URL already published; do not fail the job while OSS bg may still run.
                mark_generation_task_status_external(job_id, status="completed", error=None)
            return
        # Forced provider poll supplement (incl. pure callback mode) before permanent fail.
        try:
            from app.services.generation_runtime.timeout_poll_recovery import maybe_start_timeout_poll_recovery

            if _extract_job_provider_task_id(current_job) and maybe_start_timeout_poll_recovery(
                "video", job_id, current_job
            ):
                mark_generation_task_status_external(job_id, status="waiting_callback", error=None)
                return {"defer_completion": True}
        except Exception:
            logger.exception("[VideoJob] timeout poll recovery start failed | job_id=%s", job_id)
        _set_video_job(
            job_id,
            status="failed",
            finished_at=now_bj_iso(),
            error=f"video job timed out after {VIDEO_JOB_MAX_RUNNING_SECONDS}s",
        )
        with VIDEO_JOB_LOCK:
            current_job = dict(VIDEO_JOB_STORE.get(job_id) or {})
        _cancel_video_job_pending_reservation(
            job_id,
            current_job,
            f"video job timed out after {VIDEO_JOB_MAX_RUNNING_SECONDS}s",
        )
        mark_generation_task_status_external(job_id, status="failed", error=f"video job timed out after {VIDEO_JOB_MAX_RUNNING_SECONDS}s")
        return {"defer_completion": False}
    except asyncio.CancelledError:
        with VIDEO_JOB_LOCK:
            current_job = dict(VIDEO_JOB_STORE.get(job_id) or {})
        current_status = _normalize_generation_status(current_job.get("status"))
        current_result_url = _extract_job_result_url(current_job.get("result"))
        if current_status in {"succeeded", "storing_asset"} and current_result_url:
            logger.info(
                "[VideoJob] cancellation ignored after result finalization | job_id=%s status=%s provider_task_id=%s result_url=%s",
                job_id,
                current_status,
                _extract_job_provider_task_id(current_job) or None,
                current_result_url,
            )
            return
        _set_video_job(
            job_id,
            status="canceled",
            finished_at=now_bj_iso(),
            error="Cancelled by user",
        )
        with VIDEO_JOB_LOCK:
            current_job = dict(VIDEO_JOB_STORE.get(job_id) or {})
        _cancel_video_job_pending_reservation(job_id, current_job, "Cancelled by user")
        mark_generation_task_status_external(job_id, status="canceled", error="Cancelled by user")
        raise
    except HTTPException as e:
        with VIDEO_JOB_LOCK:
            current_job = dict(VIDEO_JOB_STORE.get(job_id) or {})
        current_status = _normalize_generation_status(current_job.get("status"))
        current_result_url = _extract_job_result_url(current_job.get("result"))
        if current_status in {"succeeded", "storing_asset"} and current_result_url:
            logger.info(
                "[VideoJob] http error ignored after result finalization | job_id=%s status=%s detail=%s provider_task_id=%s",
                job_id,
                current_status,
                str(e.detail),
                _extract_job_provider_task_id(current_job) or None,
            )
            return
        if _is_ambiguous_image_submit_detail(e.detail):
            detail = str(e.detail)
            _set_video_job(
                job_id,
                status="failed",
                finished_at=now_bj_iso(),
                error=detail,
                ambiguous_submit=True,
                ambiguous_submit_at=now_bj_iso(),
                upstream_submit_state="ambiguous_submit",
            )
            logger.warning(
                "[VideoJob] ambiguous submit failed closed (no task id to wait on) | job_id=%s callback_ticket=%s detail=%s",
                job_id,
                provider_callback_ticket or None,
                detail,
            )
            with VIDEO_JOB_LOCK:
                current_job = dict(VIDEO_JOB_STORE.get(job_id) or {})
            _cancel_video_job_pending_reservation(job_id, current_job, detail)
            mark_generation_task_status_external(job_id, status="failed", error=detail)
            return {"defer_completion": False}
        logger.warning(
            "[VideoJob] failed | job_id=%s user_id=%s detail=%s",
            job_id,
            user_id,
            str(e.detail),
        )
        _set_video_job(
            job_id,
            status="failed",
            finished_at=now_bj_iso(),
            error=str(e.detail),
        )
        with VIDEO_JOB_LOCK:
            current_job = dict(VIDEO_JOB_STORE.get(job_id) or {})
        _cancel_video_job_pending_reservation(job_id, current_job, str(e.detail))
        mark_generation_task_status_external(job_id, status="failed", error=str(e.detail))
        return {"defer_completion": False}
    except Exception as e:
        with VIDEO_JOB_LOCK:
            current_job = dict(VIDEO_JOB_STORE.get(job_id) or {})
        current_status = _normalize_generation_status(current_job.get("status"))
        current_result_url = _extract_job_result_url(current_job.get("result"))
        if current_status in {"succeeded", "storing_asset"} and current_result_url:
            logger.info(
                "[VideoJob] exception ignored after result finalization | job_id=%s status=%s error=%s provider_task_id=%s",
                job_id,
                current_status,
                str(e),
                _extract_job_provider_task_id(current_job) or None,
            )
            return
        logger.exception(
            "[VideoJob] unexpected failure | job_id=%s user_id=%s",
            job_id,
            user_id,
        )
        _set_video_job(
            job_id,
            status="failed",
            finished_at=now_bj_iso(),
            error=str(e),
        )
        with VIDEO_JOB_LOCK:
            current_job = dict(VIDEO_JOB_STORE.get(job_id) or {})
        _cancel_video_job_pending_reservation(job_id, current_job, str(e))
        mark_generation_task_status_external(job_id, status="failed", error=str(e))
        return {"defer_completion": False}
    finally:
        with VIDEO_JOB_LOCK:
            snapshot = dict(VIDEO_JOB_STORE.get(job_id) or {})
        if not callback_url:
            callback_url = _resolve_callback_url_from_payload(snapshot)
        # Resolve via live module attribute — never rely on this function's
        # __globals__ (uvicorn StatReload / daemon queue can keep stale bindings).
        try:
            _dispatch = __import__(
                "app.services.generation_runtime.callback_http",
                fromlist=["_dispatch_generation_callback"],
            )._dispatch_generation_callback
            await _dispatch("video", callback_url, snapshot)
        except Exception as _cb_exc:
            logger.warning(
                "[VideoJob] outbound callback dispatch failed | job_id=%s err=%s",
                job_id,
                _cb_exc,
            )

        with VIDEO_JOB_LOCK:
            VIDEO_JOB_TASKS.pop(job_id, None)
        _release_db_connection(db, "run_video_job")
        _clear_generation_job_pool_cache()
