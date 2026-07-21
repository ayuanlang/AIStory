# -*- coding: utf-8 -*-
"""Generate image/video/voice/jobs routes (P9)."""
from __future__ import annotations

import logging
import os
import re
import threading
import uuid
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_current_claims, list_cached_user_entries
from app.core.config import settings
from app.core.time_utils import BEIJING_TZ, now_bj_iso
from app.db.session import SessionLocal, get_db
from app.models import all_models as models
from app.models.all_models import *
# Star-import must not shadow the datetime class (all_models used to export the module).
from datetime import datetime, timedelta  # noqa: E402

logger = logging.getLogger("api_logger")
router = APIRouter(tags=["generate"])

from app.services.generation_runtime.job_store import (  # noqa: E402
    IMAGE_ACTIVE_SCOPE_STORE,
    IMAGE_JOB_LOCK,
    IMAGE_JOB_STORE,
    VIDEO_ACTIVE_SCOPE_STORE,
    VIDEO_JOB_LOCK,
    VIDEO_JOB_STORE,
    _JOB_TIMEOUT_CHECK_STATUSES,
    _set_image_job,
    _set_video_job,
)


from app.schemas.user_auth import UserOut, UserPageOut  # noqa: E402


from app.schemas.generation_batch import ShotMediaBatchStartRequest  # noqa: E402


from app.services.billing_service import billing_service
from app.services.media_service import media_service
from app.services.agent_service import agent_service
from app.services.llm_service import llm_service
from app.services.payment_service import payment_service

def _bind_endpoint_helpers(*, include_routers: bool = True) -> None:
    # Early call uses include_routers=False to avoid circular facade imports.
    from app.api.routers.helper_bind import bind_shared_helpers
    bind_shared_helpers(globals(), __name__, include_routers=include_routers)

_bind_endpoint_helpers(include_routers=False)


# --- Generation ---

from app.schemas.generation import (  # noqa: E402,F401
    GenerationRequest,
    VideoGenerationRequest,
    VoiceGenerationRequest,
)


_DEFAULT_FRAME_INTEGRITY_NEGATIVE_PROMPT = (
    "no split-screen, no multi-panel, no collage, no duplicated subject, "
    "no repeated background blocks, no tiled composition, no comic-strip layout, "
    "no text, no watermark"
)


def _resolve_effective_negative_prompt(
    negative_prompt: Optional[str],
    asset_type: Optional[str],
    media_type: str,
) -> Tuple[str, str]:
    supplied = str(negative_prompt or "").strip()
    if supplied:
        return supplied, "request"

    asset_kind = str(asset_type or "").strip().lower()
    media_kind = str(media_type or "").strip().lower()
    if media_kind == "image" and asset_kind in {"start", "start_frame", "end", "end_frame"}:
        return _DEFAULT_FRAME_INTEGRITY_NEGATIVE_PROMPT, "default_frame_integrity"

    return "", "none"


def _normalize_seed_value(value: Any) -> Optional[int]:
    try:
        seed_num = int(value)
    except Exception:
        return None
    # Keep in common signed 32-bit positive range.
    if seed_num <= 0 or seed_num > 2147483647:
        return None
    return seed_num



from app.services.generation_runtime.api_capabilities import (  # noqa: E402,F401
    _coerce_capability_bool,
    _iter_api_capability_containers,
    _limit_media_ref_input,
    _limit_string_list_input,
    _map_int_value_to_allowed,
    _map_resolution_to_allowed,
    _map_text_value_to_allowed,
    _normalize_capability_token,
    _parse_resolution_tier,
    _read_api_capability_bool,
    _read_api_capability_int,
    _read_api_capability_int_list,
    _read_api_capability_list,
    _read_api_capability_number,
    _resolve_video_submit_image_urls,
)
from app.services.generation_runtime.voice_planning import (  # noqa: E402,F401
    _build_voice_suno_provider_options,
    _build_voice_tts_planner_prompts,
    _clamp_float,
    _extract_dialogue_text_for_tts,
    _extract_json_object_from_text,
    _is_suno_voice_runtime,
    _normalize_kie_voice_name,
    _normalize_language_code,
    _plan_voice_params_with_llm,
    _sanitize_kie_tts_plan,
    _strip_subject_prompt_context_for_voice,
)
from app.services.generation_runtime.generation_errors import (  # noqa: E402,F401
    _extract_generation_failure_message,
    _extract_generation_failure_reason,
    _format_generation_failure_detail,
    _is_generic_generation_error_text,
)
from app.services.generation_runtime.seedance_duration import (  # noqa: E402,F401
    SEEDANCE_DURATION_MAX_SECONDS,
    SEEDANCE_DURATION_MIN_SECONDS,
    _clamp_seedance_duration,
    _is_seedance2_base_model,
    _is_seedance_model_name,
    _read_system_api_base_model_row,
    _resolve_shot_video_duration_value,
)
from app.services.generation_runtime.generation_filename import (  # noqa: E402,F401
    _build_generation_filename_base,
    _build_persist_filename_base_from_context,
    _sanitize_filename_part,
)
from app.services.generation_runtime.media_runtime_target import (  # noqa: E402,F401
    _build_runtime_llm_config,
    _resolve_media_runtime_target,
)
from app.services.generation_runtime.callback_http import (  # noqa: E402,F401
    _build_generation_callback_payload,
    _dispatch_generation_callback,
    _extract_local_generation_callback_ticket,
    _normalize_callback_url,
    _resolve_callback_url_from_payload,
)

def _resolve_project_id_for_generation(req: Any, db: Session) -> Optional[int]:
    direct_project_id = _normalize_seed_value(getattr(req, "project_id", None))
    if direct_project_id:
        return direct_project_id

    episode_id = _normalize_seed_value(getattr(req, "episode_id", None))
    if episode_id:
        ep = db.query(Episode).filter(Episode.id == int(episode_id)).first()
        if ep and ep.project_id:
            return int(ep.project_id)

    shot_id = _normalize_seed_value(getattr(req, "shot_id", None))
    if shot_id:
        shot = db.query(Shot).filter(Shot.id == int(shot_id)).first()
        if shot:
            shot_project_id = _normalize_seed_value(getattr(shot, "project_id", None))
            if shot_project_id:
                return shot_project_id

            if getattr(shot, "scene_id", None):
                scene = db.query(Scene).filter(Scene.id == shot.scene_id).first()
                if scene and scene.episode_id:
                    ep = db.query(Episode).filter(Episode.id == scene.episode_id).first()
                    if ep and ep.project_id:
                        return int(ep.project_id)

    entity_id = _normalize_seed_value(getattr(req, "entity_id", None))
    if entity_id:
        entity = db.query(Entity).filter(Entity.id == int(entity_id)).first()
        if entity and entity.project_id:
            return int(entity.project_id)

    return None


def _should_hit_visual_breakpoint(kind: str, resolved_project_id: Optional[int]) -> bool:
    """Opt-in runtime breakpoint for project visual param debugging.

    Env controls:
    - GENERATION_VISUAL_BREAKPOINT=1
    - GENERATION_VISUAL_BREAKPOINT_KIND=image|video|all (default: all)
    - GENERATION_VISUAL_BREAKPOINT_PROJECT_ID=<int> (optional filter)
    """
    enabled = str(os.getenv("GENERATION_VISUAL_BREAKPOINT", "")).strip().lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return False

    kind_filter = str(os.getenv("GENERATION_VISUAL_BREAKPOINT_KIND", "all") or "all").strip().lower()
    if kind_filter not in {"all", "image", "video"}:
        kind_filter = "all"
    if kind_filter != "all" and kind_filter != str(kind or "").strip().lower():
        return False

    pid_filter_raw = str(os.getenv("GENERATION_VISUAL_BREAKPOINT_PROJECT_ID", "")).strip()
    if pid_filter_raw:
        try:
            pid_filter = int(pid_filter_raw)
        except Exception:
            return False
        try:
            stable_project_id = int(resolved_project_id) if resolved_project_id is not None else None
        except Exception:
            stable_project_id = None
        if stable_project_id != pid_filter:
            return False

    return True


def _ensure_project_generation_seed(db: Session, project_id: Optional[int], current_user: Optional[User] = None) -> Optional[int]:
    stable_project_id = _normalize_seed_value(project_id)
    if not stable_project_id:
        return None

    project = _require_project_access(db, int(stable_project_id), current_user) if current_user else db.query(Project).filter(Project.id == int(stable_project_id)).first()
    if not project:
        return None

    raw_info = project.global_info
    if isinstance(raw_info, dict):
        global_info = dict(raw_info)
    elif isinstance(raw_info, str):
        try:
            parsed = json.loads(raw_info)
            global_info = parsed if isinstance(parsed, dict) else {}
        except Exception:
            global_info = {}
    else:
        global_info = {}

    existing_seed = _normalize_seed_value(
        global_info.get("generation_seed")
        or global_info.get("seed")
        or ((global_info.get("generation") or {}).get("seed") if isinstance(global_info.get("generation"), dict) else None)
    )
    if existing_seed:
        return existing_seed

    new_seed = random.SystemRandom().randint(10000, 2147483647)
    global_info["generation_seed"] = int(new_seed)
    if "seed" not in global_info:
        global_info["seed"] = int(new_seed)

    project.global_info = global_info
    db.add(project)
    db.commit()

    logger.info(
        "[ProjectSeed] initialized | project_id=%s user_id=%s seed=%s",
        stable_project_id,
        getattr(current_user, "id", None),
        new_seed,
    )
    return int(new_seed)

def _build_video_provider_options(req: VideoGenerationRequest, quality: Optional[str] = None, output_format: Optional[str] = None, mode: Optional[str] = None) -> Dict[str, Any]:
    options: Dict[str, Any] = {}

    explicit_seed = _normalize_seed_value(getattr(req, "seed", None))
    if explicit_seed:
        options["seed"] = int(explicit_seed)
        options["seeds"] = int(explicit_seed)

    callback_candidate = (
        req.callback_url
        or req.callbackUrl
        or req.callBackUrl
    )
    callback_url = _normalize_callback_url(callback_candidate)
    if callback_url:
        # Keep both key styles for downstream provider adapters.
        options["callback_url"] = callback_url
        options["callBackUrl"] = callback_url
        options["webHook"] = callback_url

    if isinstance(req.image_urls, list):
        image_urls = _limit_string_list_input(req.image_urls, None)
        if image_urls:
            options["image_urls"] = image_urls

    if isinstance(req.audio_ids, list):
        audio_ids = _limit_string_list_input(req.audio_ids, None)
        if audio_ids:
            options["audio_ids"] = audio_ids

    if isinstance(req.video_list, list):
        normalized_video_list: List[Dict[str, Any]] = []
        for item in req.video_list:
            if not isinstance(item, dict):
                continue
            video_url = str(item.get("url") or "").strip()
            if not video_url:
                continue
            normalized_item: Dict[str, Any] = {"url": video_url}
            for key in ("start", "end", "ends"):
                raw_val = item.get(key)
                if raw_val is None or str(raw_val).strip() == "":
                    continue
                try:
                    normalized_item[key] = int(float(raw_val))
                except Exception:
                    normalized_item[key] = raw_val
            normalized_video_list.append(normalized_item)
        if normalized_video_list:
            options["video_list"] = normalized_video_list

    if isinstance(req.ref_video_urls, list):
        ref_video_urls = _limit_string_list_input(req.ref_video_urls, None)
        if ref_video_urls:
            options["reference_video_urls"] = ref_video_urls

    source_video_url = str(
        req.video_url
        or req.source_video_url
        or ""
    ).strip()
    if source_video_url:
        options["video_url"] = source_video_url

    upscale_factor_text = str(req.upscale_factor or "").strip()
    if upscale_factor_text:
        options["upscale_factor"] = upscale_factor_text

    normalized_mode = str(mode if mode is not None else (req.mode or "")).strip().lower()
    if normalized_mode:
        options["mode"] = normalized_mode
        options["__mode_source"] = "request"

    normalized_ref_mode = _normalize_video_ref_mode(getattr(req, "ref_mode", None))
    if normalized_ref_mode:
        options["ref_mode"] = normalized_ref_mode
        options["__ref_mode_source"] = "request"

    normalized_quality = str(quality if quality is not None else (req.quality or "")).strip().lower()
    if normalized_quality:
        options["quality"] = normalized_quality

    normalized_output_format = str(output_format if output_format is not None else (req.output_format or req.outputFormat or "")).strip().lower()
    if normalized_output_format:
        options["output_format"] = normalized_output_format

    if req.sound is not None:
        options["sound"] = bool(req.sound)

    if req.multi_shots is not None:
        options["multi_shots"] = bool(req.multi_shots)

    if req.draft_mode is not None:
        options["draft"] = bool(req.draft_mode)

    # Kling 3.0 API requires input.sound=true when multi_shots=true.
    if bool(options.get("multi_shots")):
        options["sound"] = True

    if isinstance(req.multi_prompt, list):
        options["multi_prompt"] = req.multi_prompt

    if isinstance(req.kling_elements, list):
        options["kling_elements"] = req.kling_elements

    return options


from app.services.generation_runtime.asset_registration import (  # noqa: E402,F401
    _asset_meta_matches_registration_context,
    _bind_generated_media_to_entity,
    _bind_generated_media_to_shot,
    _extract_provider_model_from_result,
    _find_existing_asset_for_registration,
    _log_api_switch_regenerate_if_needed,
    _normalize_asset_idempotency_key,
    _normalize_asset_url_for_dedup,
    _normalize_entity_type,
    _register_asset_helper,
    _resolve_latest_asset_provider_model,
    _resolve_subject_dependency_source_asset_url,
    _serialize_asset_row,
)


@router.post("/generate/image")
async def generate_image_endpoint(
    req: GenerationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    _enforce_user_media_generation_parallel_limit(current_user)
    try:
        _release_db_connection(db, "generate_image_sync_wait")
        return await asyncio.wait_for(_run_generate_image(req, current_user, db), timeout=IMAGE_SYNC_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"Synchronous image generation timed out after {IMAGE_SYNC_TIMEOUT_SECONDS}s. Please use /generate/image/submit and poll /generate/image/jobs/{{job_id}}.",
        )



def resolve_function_apis(db: Session, function_name: str, selected_system_api_id: Optional[int]):
    from backend.app.models.all_models import FunctionAPIConfig, SystemAPISetting
    config = db.query(FunctionAPIConfig).filter(FunctionAPIConfig.function_name == function_name).first()
    if not config or not config.api_settings:
        if selected_system_api_id:
            api = db.query(SystemAPISetting).filter(SystemAPISetting.id == selected_system_api_id, SystemAPISetting.deprecated == False).first()
            if api:
                return [api]
        return []
    
    settings = config.api_settings
    primary_id = selected_system_api_id
    
    fallbacks = [s for s in settings if s.get('is_fallback')]
    fallbacks.sort(key=lambda x: x.get('priority', 0), reverse=True)
    fallback_ids = [s.get('system_api_id') for s in fallbacks]
    
    api_ids = []
    if primary_id:
        api_ids.append(primary_id)
    for fid in fallback_ids:
        if fid not in api_ids:
            api_ids.append(fid)
            
    if not api_ids:
        for s in settings:
            if s.get('system_api_id') not in api_ids:
                api_ids.append(s.get('system_api_id'))
                
    result = []
    for aid in api_ids:
        api = db.query(SystemAPISetting).filter(SystemAPISetting.id == aid, SystemAPISetting.deprecated == False).first()
        if api:
            result.append(api)
    return result

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


def _resolve_job_elapsed_seconds(job: Dict[str, Any]) -> Optional[int]:
    # Running-timeout clock starts when the worker actually begins (started_at),
    # not when the job was enqueued (created_at). Dependent subject images may sit
    # queued until refs are ready / capacity frees — that wait must not count.
    # Use ISO age helper (naive-UTC subtract) — never naive.timestamp() (local TZ skew).
    from app.services.generation_runtime.job_store import _seconds_since_iso_timestamp

    elapsed = _seconds_since_iso_timestamp(job.get("started_at"))
    if elapsed is None:
        return None
    return max(0, int(elapsed))


def _job_is_subject_to_running_timeout(job: Dict[str, Any]) -> bool:
    from app.services.generation_runtime.job_store import (
        _is_terminal_generation_job_status,
        _job_is_callback_waiting,
    )

    status = _normalize_generation_status(job.get("status"))
    if status == "queued" or _is_terminal_generation_job_status(status):
        return False
    if status in _JOB_TIMEOUT_CHECK_STATUSES:
        return True
    return _job_is_callback_waiting(job)


def _reconcile_terminal_job_queue_state(
    *,
    kind: str,
    job_id: str,
    job: Dict[str, Any],
    set_job_func: Any,
) -> Dict[str, Any]:
    """Heal queue/upstream desync when runtime job already reached a terminal status."""
    from app.services.generation_task_queue import mark_generation_task_status_external

    status = _normalize_generation_status(job.get("status"))
    upstream_state = str(job.get("upstream_submit_state") or "").strip().lower()
    if status == "succeeded":
        if "callback_pending" in upstream_state or not upstream_state or upstream_state == "unknown":
            set_job_func(
                job_id,
                upstream_submit_state="completed",
                callback_submit_retries=0,
                callback_retry_at=None,
            )
        mark_generation_task_status_external(job_id, status="completed", error=None)
    elif status == "failed":
        if "callback_pending" in upstream_state:
            set_job_func(job_id, upstream_submit_state="callback_failed")
        mark_generation_task_status_external(
            job_id,
            status="failed",
            error=str(job.get("error") or "").strip() or None,
        )
    elif status == "canceled":
        if "callback_pending" in upstream_state:
            set_job_func(job_id, upstream_submit_state="canceled")
        mark_generation_task_status_external(
            job_id,
            status="canceled",
            error=str(job.get("error") or "").strip() or None,
        )
    else:
        return job

    store = IMAGE_JOB_STORE if kind == "image" else VIDEO_JOB_STORE
    lock = IMAGE_JOB_LOCK if kind == "image" else VIDEO_JOB_LOCK
    with lock:
        updated = dict(store.get(job_id) or {})
    return updated or job


def _maybe_finalize_stuck_job(
    *,
    kind: str,
    job_id: str,
    job: Dict[str, Any],
    set_job_func: Any,
    task_store: Dict[str, Any],
    lock: threading.Lock,
    timeout_seconds: int,
) -> Dict[str, Any]:
    from app.services.generation_runtime.job_store import (
        _is_terminal_generation_job_status,
        _job_has_success_result,
        _job_is_callback_waiting,
    )
    from app.services.generation_task_queue import mark_generation_task_status_external

    status = _normalize_generation_status(job.get("status"))
    if _is_terminal_generation_job_status(status):
        # Recover false exhaust/timeout when result already exists.
        if status == "failed" and _job_has_success_result(job):
            error_text = str(job.get("error") or "").strip().lower()
            if "callback wait" in error_text or "timed out" in error_text:
                set_job_func(
                    job_id,
                    status="succeeded",
                    error=None,
                    upstream_submit_state="completed",
                    callback_submit_retries=0,
                    callback_retry_at=None,
                    finished_at=job.get("finished_at") or now_bj_iso(),
                )
                mark_generation_task_status_external(job_id, status="completed", error=None)
                store = IMAGE_JOB_STORE if kind == "image" else VIDEO_JOB_STORE
                with lock:
                    updated = dict(store.get(job_id) or {})
                return updated or job
        return _reconcile_terminal_job_queue_state(
            kind=kind,
            job_id=job_id,
            job=job,
            set_job_func=set_job_func,
        )

    # Provider already delivered a result — never timeout this into failed.
    if _job_has_success_result(job):
        set_job_func(
            job_id,
            status="succeeded",
            error=None,
            upstream_submit_state="completed",
            callback_submit_retries=0,
            callback_retry_at=None,
            finished_at=job.get("finished_at") or now_bj_iso(),
        )
        mark_generation_task_status_external(job_id, status="completed", error=None)
        store = IMAGE_JOB_STORE if kind == "image" else VIDEO_JOB_STORE
        with lock:
            updated = dict(store.get(job_id) or {})
        return updated or job

    if not _job_is_subject_to_running_timeout(job):
        return job

    elapsed_seconds = _resolve_job_elapsed_seconds(job)
    if elapsed_seconds is None or elapsed_seconds < timeout_seconds:
        return job

    is_callback_wait = _job_is_callback_waiting(job)
    if is_callback_wait:
        timeout_message = (
            f"{kind} job callback wait timed out after {elapsed_seconds}s (limit={timeout_seconds}s)"
        )
        upstream_submit_state = "callback_wait_timeout"
    else:
        timeout_message = f"{kind} job timed out after {elapsed_seconds}s (limit={timeout_seconds}s)"
        upstream_submit_state = None

    update_fields: Dict[str, Any] = {
        "status": "failed",
        "finished_at": now_bj_iso(),
        "error": timeout_message,
    }
    if upstream_submit_state:
        update_fields["upstream_submit_state"] = upstream_submit_state
    set_job_func(job_id, **update_fields)

    mark_generation_task_status_external(job_id, status="failed", error=timeout_message)

    with lock:
        updated = dict((IMAGE_JOB_STORE if kind == "image" else VIDEO_JOB_STORE).get(job_id) or {})
    return updated or job


@router.post("/generate/image/submit")
async def submit_generate_image_endpoint(
    req: GenerationRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    callback_url = _resolve_callback_url_from_payload(req)
    explicit_idempotency_key = str(request.headers.get("X-Idempotency-Key") or "").strip()
    req_payload = req.model_dump()
    scope_key = _build_generation_task_scope("image", current_user.id, req_payload)
    fingerprint_token = _build_submit_idempotency_token("image", current_user.id, req_payload)
    idempotency_key = explicit_idempotency_key or fingerprint_token
    job_id = ""
    now = now_bj_iso()

    store_keys: List[str] = []
    if idempotency_key:
        store_keys.append(_build_image_idempotency_store_key(current_user.id, idempotency_key))
    store_keys.append(_build_image_idempotency_store_key(current_user.id, fingerprint_token))
    store_keys = list(dict.fromkeys([k for k in store_keys if str(k or "").strip()]))

    def _image_dedup_response_locked() -> Optional[Dict[str, Any]]:
        active_scope_job_id = str(IMAGE_ACTIVE_SCOPE_STORE.get(scope_key) or "").strip()
        if active_scope_job_id:
            active_scope_job = dict(IMAGE_JOB_STORE.get(active_scope_job_id) or {})
            active_status = str(active_scope_job.get("status") or "").strip().lower()
            if active_scope_job and active_status in {"queued", "running"}:
                logger.info(
                    "[ImageSubmit] scope deduplicated | user_id=%s scope=%s job_id=%s status=%s",
                    current_user.id,
                    scope_key,
                    active_scope_job_id,
                    active_status,
                )
                return {
                    "job_id": active_scope_job_id,
                    "status": active_scope_job.get("status") or "queued",
                    "created_at": active_scope_job.get("created_at") or now_bj_iso(),
                    "deduplicated": True,
                    "scope_deduplicated": True,
                }
            IMAGE_ACTIVE_SCOPE_STORE.pop(scope_key, None)

        for store_key in store_keys:
            mapped = IMAGE_SUBMIT_IDEMPOTENCY_STORE.get(store_key) or {}
            existing_job_id = str(mapped.get("job_id") or "").strip()
            if not existing_job_id:
                continue
            existing_job = dict(IMAGE_JOB_STORE.get(existing_job_id) or {})
            existing_status = str(existing_job.get("status") or "").strip().lower()
            if existing_job and existing_status in {"queued", "running"}:
                logger.info(
                    "[ImageSubmit] deduplicated | user_id=%s key=%s job_id=%s status=%s",
                    current_user.id,
                    store_key,
                    existing_job_id,
                    existing_job.get("status"),
                )
                return {
                    "job_id": existing_job_id,
                    "status": existing_job.get("status") or "queued",
                    "created_at": existing_job.get("created_at") or now_bj_iso(),
                    "deduplicated": True,
                }
        return None

    with IMAGE_JOB_LOCK:
        _prune_image_jobs_locked()
        deduped = _image_dedup_response_locked()
        if deduped is not None:
            return deduped

    parallel_limit = _enforce_user_media_generation_parallel_limit(current_user)

    with IMAGE_JOB_LOCK:
        deduped = _image_dedup_response_locked()
        if deduped is not None:
            return deduped
        job_id = uuid.uuid4().hex
        for store_key in store_keys:
            IMAGE_SUBMIT_IDEMPOTENCY_STORE[store_key] = {
                "job_id": job_id,
                "created_at": now,
            }
        IMAGE_ACTIVE_SCOPE_STORE[scope_key] = job_id

    if not job_id:
        job_id = uuid.uuid4().hex

    provider_callback_ticket = f"image-job-{job_id}"
    provider_callback_url = ""
    try:
        provider_callback_url = str(media_service._resolve_provider_callback_url({}, provider_callback_ticket) or "").strip()
    except Exception:
        provider_callback_url = ""

    _set_image_job(
        job_id,
        status="queued",
        user_id=current_user.id,
        username=current_user.username,
        prompt=req_payload.get("prompt"),
        negative_prompt=req_payload.get("negative_prompt"),
        provider=req_payload.get("provider"),
        model=req_payload.get("model"),
        mode=req_payload.get("mode"),
        aspect_ratio=req_payload.get("aspect_ratio"),
        image_size=req_payload.get("image_size"),
        width=req_payload.get("width"),
        height=req_payload.get("height"),
        quality=req_payload.get("quality"),
        callback_url=callback_url,
        provider_callback_ticket=provider_callback_ticket,
        provider_callback_url=provider_callback_url or None,
        task_scope=scope_key,
        project_id=req_payload.get("project_id"),
        episode_id=req_payload.get("episode_id"),
        scene_id=req_payload.get("scene_id"),
        shot_id=req_payload.get("shot_id"),
        shot_number=req_payload.get("shot_number"),
        shot_name=req_payload.get("shot_name"),
        entity_id=req_payload.get("entity_id"),
        entity_name=req_payload.get("entity_name"),
        subject_name=req_payload.get("subject_name"),
        subject_type=req_payload.get("subject_type"),
        entity_type=req_payload.get("entity_type"),
        asset_type=req_payload.get("asset_type"),
        seed=req_payload.get("seed"),
        created_at=now,
        started_at=None,
        finished_at=None,
        result=None,
        error=None,
    )

    logger.info(
        "[ImageJob] queued | job_id=%s user_id=%s scope=%s idempotency=%s mode=%s asset_type=%s shot_id=%s size=%sx%s aspect_ratio=%s prompt_preview=%s parallel_limit=%s",
        job_id,
        current_user.id,
        scope_key,
        bool(idempotency_key),
        str(req_payload.get("mode") or "").strip() or None,
        str(req_payload.get("asset_type") or "").strip() or None,
        req_payload.get("shot_id"),
        req_payload.get("width") or None,
        req_payload.get("height") or None,
        str(req_payload.get("aspect_ratio") or "").strip() or None,
        str(req_payload.get("prompt") or "").strip().replace("\n", " ")[:160] or None,
        parallel_limit,
    )

    image_task = _submit_generation_background_task(
        job_id=job_id,
        kind="image",
        user_id=int(current_user.id),
        payload=req_payload,
    )
    with IMAGE_JOB_LOCK:
        IMAGE_JOB_TASKS[job_id] = image_task
    _release_media_generation_job_after_limit_race(
        kind="image",
        job_id=job_id,
        user=current_user,
        limit=parallel_limit,
    )
    return {"job_id": job_id, "status": "queued", "created_at": now}


@router.get("/generate/image/jobs/{job_id}")
def get_generate_image_job_status(
    job_id: str,
    response: Response,
    current_claims: Dict[str, Any] = Depends(get_current_claims),
):
    _apply_no_store_headers(response)
    with IMAGE_JOB_LOCK:
        job = dict(IMAGE_JOB_STORE.get(job_id) or {})

    status = str(job.get("status") or "").strip().lower()
    if not job or status in {"queued", "running"}:
        file_job = _read_image_job_file(job_id)
        if file_job:
            file_status = str(file_job.get("status") or "").strip().lower()
            if not job or file_status != status or ("result" in file_job and "result" not in job):
                with IMAGE_JOB_LOCK:
                    _prune_image_jobs_locked()
                    IMAGE_JOB_STORE[job_id] = dict(file_job)
                job = dict(file_job)
                logger.info(
                    "[ImageJob] synced from shared file store | job_id=%s status=%s user_id=%s",
                    job_id,
                    job.get("status"),
                    job.get("user_id"),
                )

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if "result" in job:
        compact_result = _compact_job_result(job.get("result"))
        if compact_result != job.get("result"):
            _set_image_job(job_id, result=compact_result)
            job["result"] = compact_result

    job = _maybe_finalize_image_job_from_grsai_callback(job_id, job)
    job = _maybe_retry_image_job_result_persistence(job_id, job)
    owner_id = job.get("user_id")
    owner_username = str(job.get("username") or "").strip()
    owner_username_norm = owner_username.lower()

    job = _maybe_finalize_stuck_job(
        kind="image",
        job_id=job_id,
        job=job,
        set_job_func=_set_image_job,
        task_store=IMAGE_JOB_TASKS,
        lock=IMAGE_JOB_LOCK,
        timeout_seconds=IMAGE_JOB_MAX_RUNNING_SECONDS,
    )
    image_status = str(job.get("status") or "").strip().lower()
    current_username = str(current_claims.get("username") or "").strip()
    current_username_norm = current_username.lower()
    is_superuser = bool(current_claims.get("is_superuser"))

    try:
        safe_cid = int(current_user_id) if current_user_id is not None else -1
        safe_oid = int(owner_id) if owner_id is not None else -2
    except:
        safe_cid = -1
        safe_oid = -2
    
    is_owner = (
        (safe_cid == safe_oid and safe_oid > 0)
        or (owner_username_norm and owner_username_norm == current_username_norm)
    )
    if not is_superuser and not is_owner:
        pass

    result_url = _extract_job_result_url(job.get("result"))
    if result_url and image_status in {"queued", "running"}:
        logger.warning(
            "[ImageJob] polling anomaly | job_id=%s status=%s result_url=%s user_id=%s",
            job_id,
            image_status,
            result_url,
            owner_id,
        )

    public_result = job.get("result")
    if isinstance(public_result, dict):
        public_result = dict(public_result)
        accessible_url = _ensure_accessible_media_result_url(
            _extract_job_result_url(public_result),
            public_result.get("metadata") if isinstance(public_result.get("metadata"), dict) else None,
        )
        if accessible_url:
            public_result["url"] = accessible_url

    return {
        "job_id": job.get("job_id"),
        "status": job.get("status"),
        "created_at": job.get("created_at"),
        "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"),
        "error": job.get("error"),
        "result": public_result,
    }


