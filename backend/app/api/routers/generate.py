# -*- coding: utf-8 -*-
"""Generate image/video/voice/jobs routes (P9)."""
from __future__ import annotations

import logging
import os
import re
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

from app.api.deps import get_current_user, list_cached_user_entries
from app.core.config import settings
from app.core.time_utils import BEIJING_TZ, now_bj_iso
from app.db.session import SessionLocal, get_db
from app.models import all_models as models
from app.models.all_models import *
# Star-import must not shadow the datetime class (all_models used to export the module).
from datetime import datetime, timedelta  # noqa: E402

logger = logging.getLogger("api_logger")
router = APIRouter(tags=["generate"])

from app.schemas.user_auth import UserOut, UserPageOut  # noqa: E402


from app.schemas.generation_batch import ShotMediaBatchStartRequest  # noqa: E402


from app.services.billing_service import billing_service
from app.services.media_service import media_service
from app.services.agent_service import agent_service
from app.services.llm_service import llm_service
from app.services.payment_service import payment_service

def _bind_endpoint_helpers() -> None:
    from app.api.routers.helper_bind import bind_shared_helpers
    bind_shared_helpers(globals(), __name__)

_bind_endpoint_helpers()


# --- Generation ---

class GenerationRequest(BaseModel):
    prompt: str
    system_api_id: Optional[int] = None
    function_name: Optional[str] = None
    negative_prompt: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    aspect_ratio: Optional[str] = None
    image_size: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    quality: Optional[str] = None
    output_format: Optional[str] = None
    outputFormat: Optional[str] = None
    response_format: Optional[str] = None
    responseFormat: Optional[str] = None
    output_compression: Optional[str] = None
    outputCompression: Optional[str] = None
    background: Optional[str] = None
    ref_image_url: Optional[Union[str, List[str]]] = None
    image_urls: Optional[List[str]] = None
    imageUrls: Optional[List[str]] = None
    project_id: Optional[int] = None
    episode_id: Optional[int] = None
    scene_id: Optional[int] = None
    shot_id: Optional[int] = None
    shot_number: Optional[str] = None
    shot_name: Optional[str] = None
    entity_id: Optional[int] = None
    entity_name: Optional[str] = None
    subject_name: Optional[str] = None
    subject_type: Optional[str] = None
    entity_type: Optional[str] = None
    asset_type: Optional[str] = None
    callback_url: Optional[str] = None
    callbackUrl: Optional[str] = None
    callBackUrl: Optional[str] = None
    files_url: Optional[List[str]] = None
    filesUrl: Optional[List[str]] = None
    file_url: Optional[str] = None
    fileUrl: Optional[str] = None
    mask_url: Optional[str] = None
    maskUrl: Optional[str] = None
    is_enhance: Optional[bool] = None
    isEnhance: Optional[bool] = None
    upload_cn: Optional[bool] = None
    uploadCn: Optional[bool] = None
    enable_fallback: Optional[bool] = None
    enableFallback: Optional[bool] = None
    fallback_model: Optional[str] = None
    fallbackModel: Optional[str] = None
    seed: Optional[int] = None
    cfg: Optional[float] = None
    mode: Optional[str] = None

class VideoGenerationRequest(BaseModel):
    prompt: str
    function_name: Optional[str] = None
    system_api_id: Optional[int] = None
    negative_prompt: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    quality: Optional[str] = None
    output_format: Optional[str] = None
    outputFormat: Optional[str] = None
    ref_image_url: Optional[Union[str, List[str]]] = None
    ref_video_urls: Optional[List[str]] = None
    image_urls: Optional[List[str]] = None
    audio_ids: Optional[List[str]] = None
    video_list: Optional[List[Dict[str, Any]]] = None
    last_frame_url: Optional[str] = None
    duration: Optional[float] = 5.0
    input_duration: Optional[float] = None
    input_duration_seconds: Optional[float] = None
    aspect_ratio: Optional[str] = None
    mode: Optional[str] = None
    ref_mode: Optional[str] = None
    sound: Optional[bool] = None
    multi_shots: Optional[bool] = None
    multi_prompt: Optional[List[Dict[str, Any]]] = None
    kling_elements: Optional[List[Dict[str, Any]]] = None
    project_id: Optional[int] = None
    episode_id: Optional[int] = None
    scene_id: Optional[int] = None
    shot_id: Optional[int] = None
    draft_mode: Optional[bool] = False
    resolution: Optional[str] = None
    video_resolution: Optional[str] = None
    shot_number: Optional[str] = None
    shot_name: Optional[str] = None
    entity_name: Optional[str] = None
    subject_name: Optional[str] = None
    asset_type: Optional[str] = None
    keyframes: Optional[List[str]] = None
    callback_url: Optional[str] = None
    callbackUrl: Optional[str] = None
    callBackUrl: Optional[str] = None
    video_url: Optional[str] = None
    source_video_url: Optional[str] = None
    upscale_factor: Optional[Union[str, int]] = None
    seed: Optional[int] = None
    use_prev_video: Optional[bool] = False
    has_video_input: Optional[bool] = None


class VoiceGenerationRequest(BaseModel):
    prompt: str
    function_name: Optional[str] = None
    system_api_id: Optional[int] = None
    negative_prompt: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    project_id: Optional[int] = None
    entity_id: Optional[int] = None
    shot_id: Optional[int] = None
    shot_number: Optional[str] = None
    shot_name: Optional[str] = None
    asset_type: Optional[str] = None
    use_llm_param_planning: Optional[bool] = False
    planner_system_prompt: Optional[str] = None
    language_code: Optional[str] = None
    project_language: Optional[str] = None
    seed: Optional[int] = None
    provider_options: Optional[Dict[str, Any]] = None
    # KIE Suno music generation (entity reference audio)
    custom_mode: Optional[bool] = None
    customMode: Optional[bool] = None
    instrumental: Optional[bool] = None
    suno_model: Optional[str] = None
    sunoModel: Optional[str] = None
    suno_style: Optional[str] = None
    sunoStyle: Optional[str] = None
    suno_title: Optional[str] = None
    sunoTitle: Optional[str] = None
    negative_tags: Optional[str] = None
    negativeTags: Optional[str] = None
    vocal_gender: Optional[str] = None
    vocalGender: Optional[str] = None
    style_weight: Optional[float] = None
    styleWeight: Optional[float] = None
    weirdness_constraint: Optional[float] = None
    weirdnessConstraint: Optional[float] = None
    audio_weight: Optional[float] = None
    audioWeight: Optional[float] = None
    persona_id: Optional[str] = None
    personaId: Optional[str] = None
    persona_model: Optional[str] = None
    personaModel: Optional[str] = None


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


def _is_suno_voice_runtime(resolved_model: Optional[str], provider_options: Optional[Dict[str, Any]] = None) -> bool:
    model_text = str(resolved_model or "").strip().lower()
    if "suno" in model_text:
        return True
    opts = provider_options if isinstance(provider_options, dict) else {}
    for key in ("customMode", "custom_mode", "suno_model", "sunoModel", "suno_style", "sunoStyle", "suno_title", "sunoTitle"):
        if opts.get(key) not in (None, ""):
            return True
    return False


def _build_voice_suno_provider_options(req: VoiceGenerationRequest) -> Dict[str, Any]:
    opts: Dict[str, Any] = {}
    raw_provider_options = getattr(req, "provider_options", None)
    if isinstance(raw_provider_options, dict):
        opts.update(raw_provider_options)

    def _set_if_present(target_key: str, *source_keys: str) -> None:
        for source_key in source_keys:
            value = getattr(req, source_key, None)
            if value not in (None, ""):
                opts[target_key] = value
                return

    _set_if_present("customMode", "customMode", "custom_mode")
    _set_if_present("instrumental", "instrumental")
    _set_if_present("suno_model", "suno_model", "sunoModel")
    _set_if_present("suno_style", "suno_style", "sunoStyle")
    _set_if_present("suno_title", "suno_title", "sunoTitle")
    _set_if_present("negativeTags", "negativeTags", "negative_tags")
    _set_if_present("vocalGender", "vocalGender", "vocal_gender")
    _set_if_present("styleWeight", "styleWeight", "style_weight")
    _set_if_present("weirdnessConstraint", "weirdnessConstraint", "weirdness_constraint")
    _set_if_present("audioWeight", "audioWeight", "audio_weight")
    _set_if_present("personaId", "personaId", "persona_id")
    _set_if_present("personaModel", "personaModel", "persona_model")

    entity_id = _normalize_seed_value(getattr(req, "entity_id", None))
    if entity_id:
        opts["entity_id"] = int(entity_id)
        opts["__entity_id"] = int(entity_id)
    return opts


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

def _is_generic_generation_error_text(value: Any) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return True
    return text in {
        "generation failed",
        "image generation failed",
        "video generation failed",
        "voice generation failed",
        "kie generation failed",
        "vidu generation failed",
    }

def _extract_generation_failure_reason(value: Any, depth: int = 0) -> str:
    if depth > 4 or value is None:
        return ""
    if isinstance(value, dict):
        for key in ("failure_reason", "failedReason", "reason"):
            candidate = str(value.get(key) or "").strip()
            if candidate:
                return candidate
        for key in ("details", "data", "result", "record", "raw"):
            candidate = _extract_generation_failure_reason(value.get(key), depth + 1)
            if candidate:
                return candidate
    elif isinstance(value, list):
        for item in value[:5]:
            candidate = _extract_generation_failure_reason(item, depth + 1)
            if candidate:
                return candidate
    return ""

def _extract_generation_failure_message(value: Any, depth: int = 0) -> str:
    if depth > 4 or value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("error", "message", "msg", "failMsg", "detail"):
            candidate = _extract_generation_failure_message(value.get(key), depth + 1)
            if candidate and candidate.lower() not in {"success", "ok", "true", "0"}:
                return candidate
        for key in ("details", "data", "result", "record", "raw"):
            candidate = _extract_generation_failure_message(value.get(key), depth + 1)
            if candidate and candidate.lower() not in {"success", "ok", "true", "0"}:
                return candidate
    elif isinstance(value, list):
        for item in value[:5]:
            candidate = _extract_generation_failure_message(item, depth + 1)
            if candidate:
                return candidate
    return ""

def _format_generation_failure_detail(result: Any, fallback_error: str = "Generation failed") -> str:
    if isinstance(result, dict):
        base_error = str(result.get("error") or "").strip()
        details = result.get("details")
        detail_message = _extract_generation_failure_message(details)
        failure_reason = (
            str(result.get("failure_reason") or result.get("failedReason") or "").strip()
            or _extract_generation_failure_reason(details)
        )

        if not base_error:
            base_error = detail_message or fallback_error
        elif detail_message and detail_message != base_error and _is_generic_generation_error_text(base_error):
            base_error = detail_message
        elif detail_message and detail_message != base_error and detail_message.lower() not in base_error.lower():
            base_error = f"{base_error}: {detail_message}"

        if failure_reason and failure_reason.lower() not in base_error.lower():
            base_error = f"{base_error} [failure_reason={failure_reason}]"

        return base_error or fallback_error

    text = str(result or "").strip()
    return text or fallback_error


def _build_runtime_llm_config(provider: Optional[str], model: Optional[str], media_type: str = "media") -> Optional[Dict[str, str]]:
    provider_text = str(provider or "").strip()
    model_text = str(model or "").strip()
    if provider_text and model_text:
        return {"provider": provider_text, "model": model_text}
    if provider_text and not model_text:
        logger.info(
            "[%s] Ignore provider-only request override, fallback to active user settings | provider=%s",
            str(media_type or "media").capitalize(),
            provider_text,
        )
    elif model_text and not provider_text:
        logger.info(
            "[%s] Ignore model-only request override, fallback to active user settings | model=%s",
            str(media_type or "media").capitalize(),
            model_text,
        )
    return None


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


def _coerce_capability_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return None


def _iter_api_capability_containers(api_config: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    payload = api_config if isinstance(api_config, dict) else {}
    modality = _safe_json_dict(payload.get("modality"))
    containers: List[Dict[str, Any]] = []
    for raw in (
        modality.get("capability_flags"),
        modality.get("image_capabilities"),
        modality.get("video_capabilities"),
        modality.get("text_capabilities"),
        modality.get("digital_human_capabilities"),
        modality.get("voice_capabilities"),
        modality.get("music_capabilities"),
        modality,
    ):
        container = _safe_json_dict(raw)
        if container:
            containers.append(container)
    return containers


def _read_api_capability_bool(api_config: Optional[Dict[str, Any]], *keys: str) -> Optional[bool]:
    normalized_keys = [str(key or "").strip() for key in keys if str(key or "").strip()]
    if not normalized_keys:
        return None
    for container in _iter_api_capability_containers(api_config):
        for key in normalized_keys:
            value = _coerce_capability_bool(container.get(key))
            if value is not None:
                return value
    return None


def _read_api_capability_int(api_config: Optional[Dict[str, Any]], *keys: str) -> Optional[int]:
    normalized_keys = [str(key or "").strip() for key in keys if str(key or "").strip()]
    if not normalized_keys:
        return None
    for container in _iter_api_capability_containers(api_config):
        for key in normalized_keys:
            value = container.get(key)
            if value is None or str(value).strip() == "":
                continue
            try:
                parsed = int(float(value))
            except Exception:
                continue
            if parsed >= 0:
                return parsed
    return None


def _read_api_capability_number(api_config: Optional[Dict[str, Any]], *keys: str) -> Optional[float]:
    normalized_keys = [str(key or "").strip() for key in keys if str(key or "").strip()]
    if not normalized_keys:
        return None
    for container in _iter_api_capability_containers(api_config):
        for key in normalized_keys:
            value = container.get(key)
            if value is None or str(value).strip() == "":
                continue
            try:
                return float(value)
            except Exception:
                continue
    return None


def _read_api_capability_list(api_config: Optional[Dict[str, Any]], *keys: str) -> List[str]:
    normalized_keys = [str(key or "").strip() for key in keys if str(key or "").strip()]
    if not normalized_keys:
        return []
    for container in _iter_api_capability_containers(api_config):
        for key in normalized_keys:
            raw = container.get(key)
            if raw is None:
                continue
            if isinstance(raw, list):
                values = [str(item).strip() for item in raw if str(item).strip()]
            else:
                text = str(raw).strip()
                if not text:
                    values = []
                else:
                    try:
                        parsed = json.loads(text)
                        if isinstance(parsed, list):
                            values = [str(item).strip() for item in parsed if str(item).strip()]
                        else:
                            values = [seg.strip() for seg in text.replace("\n", ",").split(",") if seg.strip()]
                    except Exception:
                        values = [seg.strip() for seg in text.replace("\n", ",").split(",") if seg.strip()]
            if values:
                deduped: List[str] = []
                seen = set()
                for item in values:
                    key_text = item.lower()
                    if key_text in seen:
                        continue
                    seen.add(key_text)
                    deduped.append(item)
                return deduped
    return []


def _read_api_capability_int_list(api_config: Optional[Dict[str, Any]], *keys: str) -> List[int]:
    values: List[int] = []
    seen = set()
    for item in _read_api_capability_list(api_config, *keys):
        try:
            parsed = int(float(item))
        except Exception:
            continue
        if parsed <= 0 or parsed in seen:
            continue
        seen.add(parsed)
        values.append(parsed)
    return sorted(values)


def _normalize_capability_token(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").strip().lower())


def _map_text_value_to_allowed(requested: Any, allowed_values: Any) -> Optional[str]:
    allowed = [str(item).strip() for item in (allowed_values or []) if str(item).strip()]
    if not allowed:
        return None
    req_text = str(requested or "").strip()
    if not req_text:
        return None
    exact_map = {item.lower(): item for item in allowed}
    req_lower = req_text.lower()
    if req_lower in exact_map:
        return exact_map[req_lower]
    req_token = _normalize_capability_token(req_text)
    if req_token:
        token_map = {_normalize_capability_token(item): item for item in allowed}
        mapped = token_map.get(req_token)
        if mapped:
            return mapped
    return allowed[0]


def _map_int_value_to_allowed(requested: Any, allowed_values: Any) -> Optional[int]:
    allowed: List[int] = []
    for item in allowed_values or []:
        try:
            parsed = int(float(item))
        except Exception:
            continue
        if parsed > 0:
            allowed.append(parsed)
    allowed = sorted(set(allowed))
    if not allowed:
        return None
    try:
        target = int(float(requested))
    except Exception:
        return allowed[0]
    return int(min(allowed, key=lambda current: (abs(current - target), current)))


def _parse_resolution_tier(value: Any) -> Optional[int]:
    text = str(value or "").strip().lower().replace(" ", "")
    if not text:
        return None
    match = re.match(r"^(\d+)(?:p)?$", text)
    if match:
        try:
            parsed = int(match.group(1))
        except Exception:
            return None
        return parsed if parsed > 0 else None
    match = re.match(r"^(\d+)[x:](\d+)$", text)
    if match:
        try:
            first = int(match.group(1))
            second = int(match.group(2))
        except Exception:
            return None
        if first > 0 and second > 0:
            return min(first, second)
        return None
    match = re.match(r"^(\d+(?:\.\d+)?)k$", text)
    if match:
        try:
            return int(float(match.group(1)) * 1000)
        except Exception:
            return None
    return None


def _map_resolution_to_allowed(requested: Any, allowed_values: Any) -> Optional[str]:
    allowed = [str(item).strip() for item in (allowed_values or []) if str(item).strip()]
    if not allowed:
        return None
    req_text = str(requested or "").strip()
    if not req_text:
        return None
    exact_map = {item.lower(): item for item in allowed}
    req_lower = req_text.lower()
    if req_lower in exact_map:
        return exact_map[req_lower]
    req_num = _parse_resolution_tier(req_text)
    numeric_allowed: List[Tuple[str, int]] = []
    for item in allowed:
        parsed = _parse_resolution_tier(item)
        if parsed is None:
            continue
        numeric_allowed.append((item, int(parsed)))
    if req_num is None or not numeric_allowed:
        return allowed[0]
    lower_or_equal = [pair for pair in numeric_allowed if pair[1] <= int(req_num)]
    if lower_or_equal:
        best_val = max(pair[1] for pair in lower_or_equal)
        for item, val in lower_or_equal:
            if val == best_val:
                return item
    min_val = min(pair[1] for pair in numeric_allowed)
    for item, val in numeric_allowed:
        if val == min_val:
            return item
    return allowed[0]


def _resolve_video_submit_image_urls(req: Any) -> List[str]:
    if isinstance(getattr(req, "image_urls", None), list):
        urls = [str(x).strip() for x in req.image_urls if str(x).strip()]
        if urls:
            return urls
    ref_value = getattr(req, "ref_image_url", None)
    if isinstance(ref_value, list):
        return [str(x).strip() for x in ref_value if str(x).strip()]
    if isinstance(ref_value, str) and ref_value.strip():
        return [ref_value.strip()]
    return []


def _limit_media_ref_input(value: Any, limit: Optional[int]) -> Any:
    if limit is None:
        return value
    if limit <= 0:
        return [] if isinstance(value, list) else None
    if isinstance(value, list):
        refs = [str(item).strip() for item in value if str(item).strip()]
        return refs[:limit]
    text = str(value or "").strip()
    if not text:
        return value
    return text if limit >= 1 else None


def _limit_string_list_input(value: Any, limit: Optional[int]) -> List[str]:
    if isinstance(value, list):
        values = [str(item).strip() for item in value if str(item).strip()]
    else:
        values = []
    if limit is None:
        return values
    if limit <= 0:
        return []
    return values[:limit]


def _extract_json_object_from_text(raw_text: Any) -> Dict[str, Any]:
    text = str(raw_text or "").strip()
    if not text:
        return {}

    # Prefer fenced JSON blocks when the model wraps output with reasoning text.
    fenced_matches = re.findall(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text, flags=re.IGNORECASE)
    for block in fenced_matches:
        candidate = str(block or "").strip()
        if not candidate:
            continue
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    clean = text
    if clean.startswith("```"):
        lines = clean.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        clean = "\n".join(lines).strip()

    try:
        parsed = json.loads(clean)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    start = clean.find("{")
    end = clean.rfind("}")
    if start >= 0 and end > start:
        candidate = clean[start:end + 1]
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            return {}
    return {}


def _build_voice_tts_planner_prompts(video_prompt: str) -> Tuple[str, str, Dict[str, Any]]:
    prompt_text = str(video_prompt or "").strip()
    supported_voices_hint = (
        "Rachel, Aria, Roger, Sarah, Laura, Charlie, George, Callum, River, Liam, Charlotte, Alice, "
        "Matilda, Will, Jessica, Eric, Chris, Brian, Daniel, Lily, Bill"
    )

    default_system_prompt = (
        "You are a TTS planning engine with two strict phases: "
        "(1) extract spoken dialogue from the video prompt, "
        "(2) infer voice parameters from character traits and scene intent. "
        "Output ONLY one JSON object. Do not include markdown, comments, or extra text."
    )

    default_user_prompt = (
        "Generate TTS planning params from a video prompt.\\n"
        "Core objective: extract dialogue text first; then tune voice parameters by character traits.\\n"
        "Rules:\\n"
        "A. Dialogue extraction (highest priority):\n"
        "1) Extract ONLY explicit spoken lines (quoted lines or speaker: line).\n"
        "2) NEVER convert action/narration/camera description into speech text.\n"
        "3) Keep wording close to original spoken content; do not rewrite plot into dialogue.\n"
        "4) If no explicit spoken dialogue exists, set text to an empty string.\n"
        "B. Parameter inference (secondary):\n"
        "5) Use character context ONLY to infer voice and style-related params: voice, stability, similarity_boost, style, speed, language_code.\n"
        "6) Character traits/context MUST NOT be copied into text.\n"
        "7) If multiple characters are present, choose one coherent voice profile that best matches dominant speaker tone in extracted dialogue.\n"
        "8) Voice must be one of the supported names (or a valid official voice id).\n"
        "9) If uncertain, use conservative defaults: voice=Rachel, stability=0.5, similarity_boost=0.75, style=0, speed=1.0, timestamps=false.\n"
        "10) language_code should be ISO 639-1 (en/zh/ja/ko/es/fr/de/it/pt/ru/ar/hi etc).\n"
        "Supported voice names include:\n"
        f"{supported_voices_hint}\n"
        "Examples:\n"
        "- Input: 伊莎贝拉向后跌倒，老板冲进大楼。 -> text: \"\"\n"
        "- Input: 老板：\"滚出去！\" -> text: \"滚出去！\"\n"
        "- Input includes [Character Context] only -> text must still be \"\" unless explicit dialogue exists.\n"
        "Return JSON schema exactly:\\n"
        "{\\n"
        "  \\\"text\\\": \\\"string\\\",\\n"
        "  \\\"voice\\\": \\\"string\\\",\\n"
        "  \\\"stability\\\": \\\"number 0..1\\\",\\n"
        "  \\\"similarity_boost\\\": \\\"number 0..1\\\",\\n"
        "  \\\"style\\\": \\\"number 0..1\\\",\\n"
        "  \\\"speed\\\": \\\"number 0.7..1.2\\\",\\n"
        "  \\\"timestamps\\\": \\\"boolean\\\",\\n"
        "  \\\"previous_text\\\": \\\"string\\\",\\n"
        "  \\\"next_text\\\": \\\"string\\\",\\n"
        "  \\\"language_code\\\": \\\"ISO 639-1 string, e.g. en zh ja\\\"\\n"
        "}\\n\\n"
        f"Video prompt:\\n{prompt_text}"
    )

    template_source = "defaults"
    try:
        system_template = _resolve_prompt_text("voice_tts_planner_system.txt")
        system_prompt = str(system_template or "").strip() or default_system_prompt
        template_source = "system_file"
    except Exception as e:
        logger.warning("[GenerateVoice] failed to load voice_tts_planner_system.txt: %s", e)
        system_prompt = default_system_prompt

    try:
        user_template = _resolve_prompt_text("voice_tts_planner_user.txt")
        user_prompt = str(user_template or "").strip()
        if user_prompt:
            user_prompt = user_prompt.replace("{{SUPPORTED_VOICES_HINT}}", supported_voices_hint)
            user_prompt = user_prompt.replace("{{VIDEO_PROMPT}}", prompt_text)
            template_source = "both_files" if template_source == "system_file" else "user_file"
        if not user_prompt:
            user_prompt = default_user_prompt
    except Exception as e:
        logger.warning("[GenerateVoice] failed to load voice_tts_planner_user.txt: %s", e)
        user_prompt = default_user_prompt

    meta = {
        "template_source": template_source,
        "system_prompt_len": len(system_prompt or ""),
        "user_prompt_len": len(user_prompt or ""),
    }
    return system_prompt, user_prompt, meta


async def _plan_voice_params_with_llm(
    user_id: int,
    video_prompt: str,
    planner_prompts: Optional[Tuple[str, str]] = None,
) -> Dict[str, Any]:
    prompt_text = str(video_prompt or "").strip()
    if not prompt_text:
        return {}

    # For voice prompt planning, prefer system-default LLM category config
    # instead of user-bound provider/model routing.
    llm_config = agent_service.get_system_default_llm_config(user_id=user_id, category="LLM")
    planning_category = "LLM"

    if not llm_config or not llm_config.get("api_key"):
        llm_config = agent_service.get_active_llm_config(user_id, category="LLM")
        planning_category = "LLM"

    if not llm_config or not llm_config.get("api_key"):
        return {}

    if planner_prompts and isinstance(planner_prompts, tuple) and len(planner_prompts) == 2:
        system_prompt = str(planner_prompts[0] or "").strip()
        user_prompt = str(planner_prompts[1] or "").strip()
    else:
        system_prompt, user_prompt, _ = _build_voice_tts_planner_prompts(prompt_text)

    try:
        cfg = (llm_config or {}).get("config") if isinstance(llm_config, dict) else {}
        logger.info(
            "[GenerateVoice] planning llm config | user_id=%s source=%s setting_id=%s provider=%s model=%s",
            user_id,
            (cfg or {}).get("__selection_source") or (cfg or {}).get("__resolved_source") or "unknown",
            (cfg or {}).get("__resolved_setting_id"),
            llm_config.get("provider") if isinstance(llm_config, dict) else None,
            llm_config.get("model") if isinstance(llm_config, dict) else None,
        )
    except Exception:
        pass

    llm_resp = await llm_service.generate_content_with_fallback(
        user_prompt,
        system_prompt,
        llm_config,
        user_id=user_id,
        category=planning_category,
        modality="text",
    )
    parsed = _extract_json_object_from_text((llm_resp or {}).get("content"))
    if not parsed:
        return {}

    def _pick_text(*keys: str) -> str:
        for key in keys:
            val = parsed.get(key)
            if val is None:
                continue
            text = str(val).strip()
            if text:
                return text
        return ""

    normalized: Dict[str, Any] = {}
    text_value = _pick_text("text", "tts_text", "voice_text", "narration")
    if text_value:
        normalized["text"] = text_value

    voice_value = _pick_text("voice", "voice_id")
    if voice_value:
        normalized["voice"] = voice_value

    language_code_value = _pick_text("language_code", "language", "lang")
    if language_code_value:
        normalized["language_code"] = language_code_value

    for key in ["previous_text", "next_text"]:
        value = _pick_text(key)
        if value:
            normalized[key] = value

    for float_key in ["stability", "similarity_boost", "style", "speed"]:
        raw = parsed.get(float_key)
        if raw is None or str(raw).strip() == "":
            continue
        try:
            normalized[float_key] = float(raw)
        except Exception:
            pass

    timestamps_raw = parsed.get("timestamps")
    if timestamps_raw is not None:
        normalized["timestamps"] = _to_bool(timestamps_raw)

    return normalized


_KIE_TTS_DEFAULT_VOICE = "Rachel"
_KIE_TTS_ALLOWED_VOICES = {
    "Rachel", "Aria", "Roger", "Sarah", "Laura", "Charlie", "George", "Callum", "River", "Liam",
    "Charlotte", "Alice", "Matilda", "Will", "Jessica", "Eric", "Chris", "Brian", "Daniel", "Lily", "Bill",
}


def _normalize_kie_voice_name(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""

    # Accept official custom voice ids (alnum) used by KIE/ElevenLabs voice catalogs.
    if re.fullmatch(r"[A-Za-z0-9]{18,32}", raw):
        return raw

    candidates = [
        raw,
        raw.split(" - ")[0].strip(),
        raw.split("|")[0].strip(),
        raw.split("（")[0].strip(),
        raw.split("(")[0].strip(),
    ]
    for candidate in candidates:
        if candidate in _KIE_TTS_ALLOWED_VOICES:
            return candidate

    return ""


def _normalize_language_code(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    # Keep main ISO 639-1 code to avoid provider errors on unsupported variants.
    base = raw.split("-")[0].strip()
    if re.fullmatch(r"[a-z]{2}", base):
        return base
    return ""


def _clamp_float(value: Any, min_val: float, max_val: float, default: float) -> float:
    try:
        num = float(value)
    except Exception:
        num = float(default)
    return max(min_val, min(max_val, num))


def _extract_dialogue_text_for_tts(value: Any) -> str:
    raw = str(value or "").replace("\r\n", "\n").strip()
    if not raw:
        return ""
    raw_lines = [str(x or "").strip() for x in raw.split("\n") if str(x or "").strip()]

    picked: List[str] = []
    seen = set()

    def _looks_like_non_dialogue_metadata(text_like: Any) -> bool:
        text = str(text_like or "").strip()
        if not text:
            return True

        low = re.sub(r"\s+", " ", text).strip().lower()
        if not low:
            return True

        if re.fullmatch(r"[a-z]{2}", low):
            return True
        if low in {"中文", "chinese", "中文 / chinese", "chinese / 中文"}:
            return True

        metadata_tokens = [
            "prompt en",
            "prompt cn",
            "prompt:",
            "viewpoint",
            "lighting",
            "wardrobe",
            "panel view",
            "panel views",
            "close-up",
            "full-body",
            "subject info",
            "aspect ratio",
            "image",
            "background",
            "no text",
            "pure white",
            "color grade",
            "camera",
            "ref:",
            "style",
            "generation_prompt_cn",
            "generation_prompt_en",
            "subjects_json",
            "existing entity inventory",
            "character context",
            "角色设定",
            "角色信息",
            "角色提示词",
            "人物提示词",
        ]
        if any(token in low for token in metadata_tokens):
            return True

        if "|" in text and ("prompt" in low or "subject" in low):
            return True

        if len(text) > 220:
            return True

        return False

    def _push(text_like: Any) -> None:
        text = str(text_like or "").strip()
        if not text:
            return
        if _looks_like_non_dialogue_metadata(text):
            return
        stable = re.sub(r"\s+", " ", text).strip()
        if not stable:
            return
        key = stable.lower()
        if key in seen:
            return
        seen.add(key)
        picked.append(stable)

    quote_patterns = [
        r'"([^"\n]{1,400})"',
        r'“([^”\n]{1,400})”',
        r'‘([^’\n]{1,400})’',
        r'「([^」\n]{1,400})」',
        r'『([^』\n]{1,400})』',
    ]
    for pattern in quote_patterns:
        for m in re.finditer(pattern, raw):
            _push(m.group(1))

    for line in raw_lines:
        tagged = re.search(r'(?:^|\s)(?:dialogue|line|lines|对白|台词)\s*[:：]\s*(.+)$', line, re.IGNORECASE)
        if tagged and tagged.group(1):
            _push(tagged.group(1))
            continue

        speaker = re.match(r'^([^:：\n|]{1,24})[:：]\s*(.+)$', line)
        if speaker and speaker.group(2):
            speaker_name = str(speaker.group(1) or "").strip().lower()
            if speaker_name and not any(k in speaker_name for k in ["prompt", "style", "view", "subject", "camera", "lighting", "character", "entity"]):
                _push(speaker.group(2))

    # Fallback: when no quoted/speaker dialogue was detected, keep short utterance-like lines only.
    if not picked:
        for line in raw_lines:
            candidate = re.sub(r"^[\-\*\d\.\)\s]+", "", str(line or "").strip())
            if not candidate:
                continue
            if _looks_like_non_dialogue_metadata(candidate):
                continue
            if "|" in candidate:
                continue
            if not re.search(r"[。！？!?]", candidate):
                continue
            if len(candidate) > 120:
                continue
            _push(candidate)

    # Final pass: keep only clean utterance-like lines.
    cleaned_lines = []
    for line in picked:
        stable_line = re.sub(r"\s+", " ", str(line or "")).strip()
        if not stable_line:
            continue
        if _looks_like_non_dialogue_metadata(stable_line):
            continue
        cleaned_lines.append(stable_line)

    return "\n".join(cleaned_lines)


def _strip_subject_prompt_context_for_voice(value: Any) -> str:
    raw = str(value or "").replace("\r\n", "\n").strip()
    if not raw:
        return ""

    lines = raw.split("\n")
    cleaned: List[str] = []

    remove_tokens = [
        "generation_prompt_cn",
        "generation_prompt_en",
        "subjects_json",
        "existing entity inventory",
        "reusable subject assets",
        "subject info",
        "subject prompt",
        "character context",
        "entity context",
        "角色设定",
        "角色信息",
        "角色提示词",
        "人物提示词",
        "prompt en:",
        "prompt cn:",
    ]

    for line in lines:
        text = str(line or "").strip()
        if not text:
            cleaned.append("")
            continue
        low = text.lower()
        if any(token in low for token in remove_tokens):
            continue
        cleaned.append(text)

    compact = "\n".join(cleaned)
    compact = re.sub(r"\n{3,}", "\n\n", compact).strip()
    return compact


def _sanitize_kie_tts_plan(raw_plan: Dict[str, Any], fallback_text: str = "") -> Dict[str, Any]:
    plan = raw_plan if isinstance(raw_plan, dict) else {}
    out: Dict[str, Any] = {}

    fallback_dialogue = _extract_dialogue_text_for_tts(fallback_text) if str(fallback_text or "").strip() else ""
    planned_text_raw = str(plan.get("text") or "").strip()
    planned_dialogue_only = _extract_dialogue_text_for_tts(planned_text_raw)
    text_value = planned_dialogue_only or fallback_dialogue
    if text_value:
        out["text"] = text_value

    voice_value = _normalize_kie_voice_name(plan.get("voice") or plan.get("voice_id"))
    out["voice"] = voice_value or _KIE_TTS_DEFAULT_VOICE

    language_code = _normalize_language_code(plan.get("language_code") or plan.get("language") or plan.get("lang"))
    if language_code:
        out["language_code"] = language_code

    out["stability"] = _clamp_float(plan.get("stability"), 0.0, 1.0, 0.5)
    out["similarity_boost"] = _clamp_float(plan.get("similarity_boost"), 0.0, 1.0, 0.75)
    out["style"] = _clamp_float(plan.get("style"), 0.0, 1.0, 0.0)
    out["speed"] = _clamp_float(plan.get("speed"), 0.7, 1.2, 1.0)

    if plan.get("timestamps") is None:
        out["timestamps"] = False
    else:
        out["timestamps"] = bool(_to_bool(plan.get("timestamps")))

    previous_text = str(plan.get("previous_text") or "").strip()
    next_text = str(plan.get("next_text") or "").strip()
    if previous_text:
        out["previous_text"] = previous_text
    if next_text:
        out["next_text"] = next_text

    return out


# ShotMediaBatchStartRequest -> app.schemas.generation_batch

def _read_system_api_base_model_row(row: Any) -> str:
    return str(getattr(row, "base_model", "") or "").strip()


def _is_seedance2_base_model(base_model: Any) -> bool:
    candidate = str(base_model or "").strip().lower()
    if not candidate:
        return False
    if candidate.startswith("doubao-seedance-2"):
        return True
    if candidate.startswith("ep-doubao-seedance-2"):
        return True
    return bool(re.match(r"^seedance[-_]?2(?:$|[-_.])", candidate))


SEEDANCE_DURATION_MIN_SECONDS = 4.0
SEEDANCE_DURATION_MAX_SECONDS = 15.0


def _is_seedance_model_name(*identity_parts: Any) -> bool:
    """True when any identity part contains 'seedance' (case-insensitive)."""
    text = " ".join(str(part or "") for part in identity_parts).lower()
    return "seedance" in text


def _clamp_seedance_duration(duration: Any) -> Tuple[Optional[float], bool]:
    """Clamp Seedance duration to [4, 15]. Preserves None and <=0 (e.g. -1 auto)."""
    if duration is None:
        return None, False
    try:
        value = float(duration)
    except Exception:
        return None, False
    if value <= 0:
        return value, False
    clamped = max(SEEDANCE_DURATION_MIN_SECONDS, min(SEEDANCE_DURATION_MAX_SECONDS, value))
    return clamped, clamped != value


def _resolve_shot_video_duration_value(
    *,
    shot_duration: Any,
    sd2_auto_duration: bool = False,
    base_model: Optional[str] = None,
    system_api_id: Optional[int] = None,
    db: Optional[Session] = None,
) -> float:
    table_duration = 5.0
    try:
        table_duration = float(str(shot_duration or 5).strip() or 5)
    except Exception:
        table_duration = 5.0

    resolved_base_model = str(base_model or "").strip()
    resolved_api_name = ""
    resolved_api_model = ""
    if system_api_id and db is not None:
        try:
            from backend.app.models.all_models import SystemAPISetting
            row = db.query(SystemAPISetting).filter(SystemAPISetting.id == int(system_api_id)).first()
            if row:
                if not resolved_base_model:
                    resolved_base_model = _read_system_api_base_model_row(row)
                resolved_api_name = str(getattr(row, "name", "") or "").strip()
                resolved_api_model = str(getattr(row, "model", "") or "").strip()
        except Exception:
            pass

    if bool(sd2_auto_duration) and _is_seedance2_base_model(resolved_base_model):
        return -1.0

    if _is_seedance_model_name(resolved_base_model, resolved_api_name, resolved_api_model):
        clamped, _ = _clamp_seedance_duration(table_duration)
        if clamped is not None:
            return float(clamped)
    return table_duration


def _sanitize_filename_part(value: Optional[str], max_len: int = 48) -> str:
    if not value:
        return ""
    cleaned = re.sub(r'[\\/:*?"<>|]+', ' ', str(value))
    cleaned = re.sub(r'\s+', '_', cleaned).strip('._- ')
    cleaned = re.sub(r'_+', '_', cleaned)
    return cleaned[:max_len]


def _build_generation_filename_base(req: Any, db: Session) -> str:
    parts: List[str] = []

    asset_type = _sanitize_filename_part(getattr(req, "asset_type", None), 24)
    if asset_type:
        parts.append(asset_type)

    # Keep shot number in filename for stable traceability across generations.
    shot_number_label = getattr(req, "shot_number", None)
    shot_name_label = getattr(req, "shot_name", None)
    if (not shot_number_label or not shot_name_label) and getattr(req, "shot_id", None):
        shot_obj = db.query(Shot).filter(Shot.id == req.shot_id).first()
        if shot_obj:
            if not shot_number_label:
                shot_number_label = shot_obj.shot_id
            if not shot_name_label:
                shot_name_label = shot_obj.shot_name

    shot_number_part = _sanitize_filename_part(shot_number_label)
    shot_name_part = _sanitize_filename_part(shot_name_label)
    if shot_number_part and shot_name_part and shot_name_part != shot_number_part:
        shot_part = f"{shot_number_part}_{shot_name_part}"
    else:
        shot_part = shot_number_part or shot_name_part

    if shot_part:
        parts.append(f"shot_{shot_part}")

    subject_label = getattr(req, "subject_name", None) or getattr(req, "entity_name", None)
    subject_part = _sanitize_filename_part(subject_label)
    if subject_part:
        parts.append(f"subject_{subject_part}")

    return "_".join(parts) if parts else "gen"


def _build_persist_filename_base_from_context(req_context: Dict[str, Any], db: Session) -> str:
    class _GenerationFilenameContext:
        def __init__(self, context: Dict[str, Any]):
            self._context = context if isinstance(context, dict) else {}

        def __getattr__(self, name: str) -> Any:
            return self._context.get(name)

    return _build_generation_filename_base(_GenerationFilenameContext(req_context), db)


def _normalize_entity_type(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if not text:
        return None
    if text in {"character", "char", "role", "人物", "角色"}:
        return "character"
    if text in {"environment", "env", "scene", "场景", "环境"}:
        return "environment"
    if text in {"prop", "props", "道具", "物件"}:
        return "prop"
    return text


def _serialize_asset_row(asset: Asset, db: Session = None) -> Dict[str, Any]:
    _sync_asset_denormalized_fields(asset)
    meta = _asset_meta_dict(getattr(asset, "meta_info", None))
    return {
        "id": asset.id,
        "type": asset.type,
        "url": oss_storage_service.refresh_url(asset.url) if oss_storage_service.is_enabled(db) else asset.url,
        "filename": asset.filename,
        "project_id": getattr(asset, "project_id", None),
        "episode_id": getattr(asset, "episode_id", None),
        "is_current_project_asset": bool(getattr(asset, "is_current_project_asset", False)),
        "meta_info": meta,
        "remark": asset.remark,
        "created_at": asset.created_at,
    }


def _normalize_asset_idempotency_key(value: Any) -> str:
    return str(value or "").strip()


def _normalize_asset_url_for_dedup(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = urllib.parse.urlparse(raw)
        if str(parsed.scheme or "").lower() in {"http", "https"}:
            # Ignore volatile signed-query parameters when deduplicating assets.
            cleaned = parsed._replace(query="", fragment="")
            return urllib.parse.urlunparse(cleaned).strip().lower()
    except Exception:
        pass
    return raw.lower()


def _asset_meta_matches_registration_context(asset_meta: Any, expected_meta: Any) -> bool:
    asset_meta = _asset_meta_dict(asset_meta)
    expected_meta = _asset_meta_dict(expected_meta)

    compare_keys = [
        "project_id",
        "episode_id",
        "entity_id",
        "shot_id",
        "asset_type",
        "frame_type",
        "source_asset_url",
    ]
    for key in compare_keys:
        expected_value = str(expected_meta.get(key) or "").strip()
        if not expected_value:
            continue
        if key == "source_asset_url":
            if _normalize_asset_url_for_dedup(asset_meta.get(key)) != _normalize_asset_url_for_dedup(expected_value):
                return False
            continue
        if str(asset_meta.get(key) or "").strip() != expected_value:
            return False
    return True


def _find_existing_asset_for_registration(
    db: Session,
    user_id: int,
    *,
    url: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    meta_info: Optional[Dict[str, Any]] = None,
) -> Optional[Asset]:
    normalized_key = _normalize_asset_idempotency_key(idempotency_key)
    normalized_meta = dict(meta_info) if isinstance(meta_info, dict) else {}

    if normalized_key:
        keyed_candidates = (
            db.query(Asset)
            .filter(Asset.user_id == user_id, _active_asset_clause())
            .order_by(Asset.id.desc())
            .limit(500)
            .all()
        )
        for candidate in keyed_candidates:
            candidate_meta = candidate.meta_info if isinstance(candidate.meta_info, dict) else {}
            if _normalize_asset_idempotency_key(candidate_meta.get("idempotency_key")) != normalized_key:
                continue
            return candidate

    normalized_url = str(url or "").strip()
    if not normalized_url:
        return None
    normalized_compare_url = _normalize_asset_url_for_dedup(normalized_url)

    if normalized_compare_url:
        try:
            normalized_candidates = (
                db.query(Asset)
                .filter(
                    Asset.user_id == user_id,
                    Asset.url_normalized == normalized_compare_url,
                    _active_asset_clause(),
                )
                .order_by(Asset.id.desc())
                .limit(120)
                .all()
            )
            for candidate in normalized_candidates:
                if _asset_meta_matches_registration_context(candidate.meta_info, normalized_meta):
                    return candidate
            # Unique constraint is on (user, type, project, episode, url_normalized).
            # Reusing the same image onto another entity must hit this row even when
            # entity_id / shot_id meta differs — otherwise INSERT races into UniqueViolation
            # and poisons the parent Session.
            expected_project_id = _asset_optional_int(normalized_meta.get("project_id"))
            expected_episode_id = _asset_optional_int(normalized_meta.get("episode_id"))
            for candidate in normalized_candidates:
                candidate_project_id = _asset_optional_int(getattr(candidate, "project_id", None))
                candidate_episode_id = _asset_optional_int(getattr(candidate, "episode_id", None))
                if candidate_project_id != expected_project_id:
                    continue
                if candidate_episode_id != expected_episode_id:
                    continue
                return candidate
            if normalized_candidates and expected_project_id is None and expected_episode_id is None:
                return normalized_candidates[0]
        except Exception:
            # Backward-compatible fallback for old schemas before url_normalized exists.
            pass

    url_candidates = (
        db.query(Asset)
        .filter(
            Asset.user_id == user_id,
            Asset.url == normalized_url,
            _active_asset_clause(),
        )
        .order_by(Asset.id.desc())
        .limit(50)
        .all()
    )
    if url_candidates:
        for candidate in url_candidates:
            if _asset_meta_matches_registration_context(candidate.meta_info, normalized_meta):
                return candidate

    # Fallback dedupe for signed URLs where only query token differs.
    if normalized_compare_url:
        recent_candidates = (
            db.query(Asset)
            .filter(Asset.user_id == user_id, _active_asset_clause())
            .order_by(Asset.id.desc())
            .limit(600)
            .all()
        )
        for candidate in recent_candidates:
            if _normalize_asset_url_for_dedup(getattr(candidate, "url", None)) != normalized_compare_url:
                continue
            if _asset_meta_matches_registration_context(candidate.meta_info, normalized_meta):
                return candidate

    return None


def _resolve_subject_dependency_source_asset_url(db: Session, user_id: int, meta_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Auto-pick a prior-episode same-name subject image as source_asset_url.

    Hard rules:
    - same subject name (exact, case-insensitive trim)
    - source episode is not soft-deleted
    - source episode number must be strictly smaller than the current episode
    - asset / linked entity must not be soft-deleted

    Returns provenance dict: url, asset_id, episode_id/title, entity_id/name, subject_type.
    """
    meta = _asset_meta_dict(meta_info)
    project_id = _asset_optional_int(meta.get("project_id"))
    if not project_id:
        return None

    requested_subject_type = _normalize_entity_type(meta.get("subject_type") or meta.get("entity_type"))
    requested_entity_id = _asset_optional_int(meta.get("entity_id"))
    current_episode_id = _asset_optional_int(meta.get("episode_id"))
    requested_name = str(meta.get("subject_name") or "").strip().lower()
    requested_entity_name = str(meta.get("entity_name") or "").strip().lower()
    requested_name_tokens = {token for token in (requested_name, requested_entity_name) if token}

    # Resolve names / episode / type from the active entity row when meta is incomplete.
    if requested_entity_id:
        entity_row = (
            db.query(Entity)
            .filter(Entity.id == int(requested_entity_id), _active_entity_clause())
            .first()
        )
        if entity_row:
            for token in (
                str(getattr(entity_row, "name", None) or "").strip().lower(),
                str(getattr(entity_row, "name_en", None) or "").strip().lower(),
            ):
                if token:
                    requested_name_tokens.add(token)
            if not requested_subject_type:
                requested_subject_type = _normalize_entity_type(getattr(entity_row, "type", None))
            if not current_episode_id:
                current_episode_id = _asset_optional_int(getattr(entity_row, "episode_id", None))
        else:
            # Soft-deleted / missing entity cannot drive cross-episode reuse.
            if not requested_name_tokens:
                return None

    if not requested_name_tokens:
        return None
    # Cross-episode reuse requires knowing the current episode so we can compare episode numbers.
    if not current_episode_id:
        return None

    current_episode_row = (
        db.query(Episode)
        .filter(
            Episode.id == int(current_episode_id),
            Episode.project_id == int(project_id),
            _active_episode_clause(),
        )
        .first()
    )
    if not current_episode_row:
        return None
    current_episode_number = _resolve_episode_sort_number(current_episode_row)
    if not current_episode_number:
        return None

    # Eligible source episodes: active, same project, episode number < current.
    prior_episode_rows = (
        db.query(Episode)
        .filter(
            Episode.project_id == int(project_id),
            _active_episode_clause(),
            Episode.id != int(current_episode_id),
        )
        .all()
    )
    prior_episode_number_map: Dict[int, int] = {}
    for ep_row in prior_episode_rows or []:
        ep_id = _asset_optional_int(getattr(ep_row, "id", None))
        if not ep_id:
            continue
        ep_number = _resolve_episode_sort_number(ep_row)
        if not ep_number or int(ep_number) >= int(current_episode_number):
            continue
        prior_episode_number_map[int(ep_id)] = int(ep_number)
    if not prior_episode_number_map:
        return None

    candidates = (
        db.query(Asset)
        .filter(
            Asset.user_id == user_id,
            Asset.type == "image",
            Asset.project_id == project_id,
            _active_asset_clause(),
        )
        .order_by(Asset.id.desc())
        .limit(5000)
        .all()
    )
    if not candidates:
        return None

    matched: List[Asset] = []
    matched_entity_ids: Set[int] = set()
    for candidate in candidates:
        _sync_asset_denormalized_fields(candidate)
        candidate_meta = _asset_meta_dict(getattr(candidate, "meta_info", None))
        if _asset_optional_int(candidate.project_id or candidate_meta.get("project_id")) != project_id:
            continue

        candidate_episode_id = _asset_optional_int(
            getattr(candidate, "episode_id", None) or candidate_meta.get("episode_id")
        )
        # Must belong to a prior non-deleted episode with a smaller episode number.
        if not candidate_episode_id or int(candidate_episode_id) not in prior_episode_number_map:
            continue

        candidate_subject_type = _normalize_entity_type(
            candidate_meta.get("subject_type") or candidate_meta.get("entity_type")
        )
        # Keep type-consistent dependency reuse except for poster assets.
        if (
            requested_subject_type
            and requested_subject_type != "poster"
            and candidate_subject_type
            and candidate_subject_type != requested_subject_type
        ):
            continue

        candidate_subject_name = str(candidate_meta.get("subject_name") or "").strip().lower()
        candidate_entity_name = str(candidate_meta.get("entity_name") or "").strip().lower()
        candidate_name_tokens = {
            token for token in (candidate_subject_name, candidate_entity_name) if token
        }
        # Same name only — do not reuse by entity_id alone (that hits same-card regenerations).
        if not candidate_name_tokens or not requested_name_tokens.intersection(candidate_name_tokens):
            continue

        matched.append(candidate)
        candidate_entity_id = _asset_optional_int(candidate_meta.get("entity_id"))
        if candidate_entity_id:
            matched_entity_ids.add(int(candidate_entity_id))

    if not matched:
        return None

    active_entity_ids: Set[int] = set()
    if matched_entity_ids:
        active_entity_ids = {
            int(row_id)
            for (row_id,) in db.query(Entity.id)
            .filter(Entity.id.in_(matched_entity_ids), _active_entity_clause())
            .all()
        }

    filtered_matched: List[Asset] = []
    for row in matched:
        row_meta = _asset_meta_dict(getattr(row, "meta_info", None))
        episode_id = _asset_optional_int(getattr(row, "episode_id", None) or row_meta.get("episode_id"))
        if not episode_id or int(episode_id) not in prior_episode_number_map:
            continue
        entity_id = _asset_optional_int(row_meta.get("entity_id"))
        if entity_id and int(entity_id) not in active_entity_ids:
            continue
        filtered_matched.append(row)

    if not filtered_matched:
        return None

    episode_title_map: Dict[int, str] = {
        int(row_id): str(row_title or "")
        for row_id, row_title in db.query(Episode.id, Episode.title)
        .filter(Episode.id.in_(list(prior_episode_number_map.keys())))
        .all()
    }

    def _candidate_rank(asset: Asset) -> Tuple[int, int, str, int]:
        candidate_meta = _asset_meta_dict(getattr(asset, "meta_info", None))
        episode_id = _asset_optional_int(getattr(asset, "episode_id", None) or candidate_meta.get("episode_id"))
        # Prefer the nearest prior episode (largest episode number still < current).
        episode_rank = int(prior_episode_number_map.get(int(episode_id or 0), 0) or 0)
        is_current = 1 if bool(getattr(asset, "is_current_project_asset", False)) else 0
        created_at = str(getattr(asset, "created_at", "") or "")
        return (episode_rank, is_current, created_at, int(getattr(asset, "id", 0) or 0))

    chosen = max(filtered_matched, key=_candidate_rank)
    chosen_url = str(getattr(chosen, "url", "") or "").strip()
    if not chosen_url:
        return None

    chosen_meta = _asset_meta_dict(getattr(chosen, "meta_info", None))
    chosen_episode_id = _asset_optional_int(
        getattr(chosen, "episode_id", None) or chosen_meta.get("episode_id")
    )
    chosen_entity_id = _asset_optional_int(chosen_meta.get("entity_id"))
    chosen_entity_name = str(
        chosen_meta.get("entity_name")
        or chosen_meta.get("subject_name")
        or ""
    ).strip()
    chosen_subject_type = _normalize_entity_type(
        chosen_meta.get("subject_type") or chosen_meta.get("entity_type")
    )
    # Prefer script_title (分集名) over bare Episode.title ("Episode 1").
    chosen_episode_title = str(episode_title_map.get(int(chosen_episode_id or 0), "") or "").strip()
    if chosen_episode_id:
        try:
            ep_row = (
                db.query(Episode)
                .filter(Episode.id == int(chosen_episode_id), _active_episode_clause())
                .first()
            )
            ep_info = getattr(ep_row, "episode_info", None) if ep_row else None
            if isinstance(ep_info, dict):
                script_title = str(
                    ep_info.get("script_title")
                    or ep_info.get("episode_title")
                    or ep_info.get("episode_name")
                    or ""
                ).strip()
                if script_title:
                    chosen_episode_title = script_title
                elif not chosen_episode_title:
                    chosen_episode_title = str(getattr(ep_row, "title", "") or "").strip()
        except Exception:
            pass
    return {
        "url": chosen_url,
        "asset_id": int(getattr(chosen, "id", 0) or 0) or None,
        "episode_id": int(chosen_episode_id) if chosen_episode_id else None,
        "episode_title": chosen_episode_title or None,
        "entity_id": int(chosen_entity_id) if chosen_entity_id else None,
        "entity_name": chosen_entity_name or None,
        "subject_type": chosen_subject_type or None,
    }

def _register_asset_helper(db: Session, user_id: int, url: str, req: Any, source_metadata: Dict = None):
    # Handle dict or object
    def get_attr(obj, key):
        if isinstance(obj, dict): return obj.get(key)
        return getattr(obj, key, None)

    project_id = _asset_optional_int(get_attr(req, "project_id"))
    episode_id_hint = _asset_optional_int(get_attr(req, "episode_id"))
    shot_id_hint = _asset_optional_int(get_attr(req, "shot_id"))

    if not project_id and shot_id_hint:
        try:
            shot_row = db.query(Shot).filter(Shot.id == int(shot_id_hint)).first()
            if shot_row:
                project_id = _asset_optional_int(getattr(shot_row, "project_id", None))
                if not episode_id_hint:
                    episode_id_hint = _asset_optional_int(getattr(shot_row, "episode_id", None))
                if not episode_id_hint and getattr(shot_row, "scene_id", None):
                    scene_row = db.query(Scene).filter(Scene.id == int(shot_row.scene_id)).first()
                    if scene_row:
                        episode_id_hint = _asset_optional_int(getattr(scene_row, "episode_id", None))
        except Exception:
            pass

    if not project_id and episode_id_hint:
        try:
            episode_row = db.query(Episode).filter(Episode.id == int(episode_id_hint)).first()
            if episode_row:
                project_id = _asset_optional_int(getattr(episode_row, "project_id", None))
        except Exception:
            pass

    if not project_id:
        return

    try:
        # Determine paths
        import urllib.parse
        parsed_url_path = urllib.parse.urlparse(url).path
        if parsed_url_path.startswith('/uploads/'):
            rel_path = parsed_url_path[len('/uploads/'):]
            file_path = os.path.join(settings.UPLOAD_DIR, rel_path)
            fname = os.path.basename(parsed_url_path)
        else:
            fname = os.path.basename(parsed_url_path)
            file_path = os.path.join(settings.UPLOAD_DIR, fname)
            
        lower_path = parsed_url_path.lower()
        is_image = lower_path.endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"))
        is_video = lower_path.endswith((".mp4", ".mov", ".m4v", ".webm", ".avi", ".mkv"))
        is_audio = lower_path.endswith((".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"))

        meta = {}
        # Copy known fields
        for field in ["shot_number", "shot_id", "project_id", "episode_id", "asset_type", "entity_id", "entity_name", "subject_name", "subject_type", "entity_type", "source_asset_url", "idempotency_key"]:
            val = get_attr(req, field)
            if val: meta[field] = val

        if not meta.get("project_id") and project_id:
            meta["project_id"] = int(project_id)
        if not meta.get("episode_id") and episode_id_hint:
            meta["episode_id"] = int(episode_id_hint)

        # Map reference URLs to source_asset_url for asset dependency tracking
        if not meta.get("source_asset_url"):
            for ref_field in ["ref_image_url", "ref_video_urls", "last_frame_url", "base_image", "seed_image"]:
                ref_val = get_attr(req, ref_field)
                if ref_val:
                    actual_url = ref_val[0] if isinstance(ref_val, list) and len(ref_val) > 0 else ref_val
                    if isinstance(actual_url, str) and actual_url.startswith("http"):
                        meta["source_asset_url"] = actual_url
                        break

        if get_attr(req, "asset_type"): meta["frame_type"] = get_attr(req, "asset_type")
        if get_attr(req, "category"): meta["category"] = get_attr(req, "category")

        # Merge Source Metadata (Provider, Model, Dimensions, etc.)
        if source_metadata:
            for k in ["provider", "model", "duration", "width", "height", "aspect_ratio", "submit_aspect_ratio", "prompt", "seed", "idempotency_key"]:
                if k in source_metadata:
                    meta[k] = source_metadata[k]
            provider_usage = _extract_provider_usage_from_metadata(source_metadata)
            if provider_usage:
                meta["usage"] = provider_usage
                meta["provider_usage"] = provider_usage
                usage_source = str(source_metadata.get("usage_source") or "").strip()
                if usage_source:
                    meta["usage_source"] = usage_source

        provider_alias_map = _build_provider_alias_lookup(db)
        meta = _attach_provider_alias_to_dict(meta, provider_alias_map)
        ensure_resolution_fields(meta)

        is_subject_generation = str(get_attr(req, "asset_type") or "").strip().lower() == "subject"
        if is_subject_generation:
            resolved_type = _normalize_entity_type(
                get_attr(req, "subject_type")
                or get_attr(req, "entity_type")
                or get_attr(req, "category")
                or meta.get("subject_type")
                or meta.get("entity_type")
            )

            entity_id_val = get_attr(req, "entity_id")
            if not resolved_type and entity_id_val:
                try:
                    e = db.query(Entity).filter(Entity.id == int(entity_id_val)).first()
                    if e:
                        resolved_type = _normalize_entity_type(e.type)
                except Exception:
                    pass

            if not resolved_type and project_id:
                subject_label = str(get_attr(req, "entity_name") or get_attr(req, "subject_name") or "").strip()
                if subject_label:
                    e = db.query(Entity).filter(
                        Entity.project_id == int(project_id),
                        or_(Entity.name == subject_label, Entity.name_en == subject_label)
                    ).first()
                    if e:
                        resolved_type = _normalize_entity_type(e.type)
                        if not meta.get("entity_id"):
                            meta["entity_id"] = e.id

            if resolved_type:
                meta["subject_type"] = resolved_type
                meta["entity_type"] = resolved_type
                if resolved_type == "character":
                    meta["subject_type_cn"] = "角色"
                elif resolved_type == "environment":
                    meta["subject_type_cn"] = "环境"
                elif resolved_type == "prop":
                    meta["subject_type_cn"] = "道具"

        if is_subject_generation and not meta.get("source_asset_url"):
            inferred_source = _resolve_subject_dependency_source_asset_url(db, user_id, meta)
            inferred_source_url = str((inferred_source or {}).get("url") or "").strip()
            if inferred_source_url and inferred_source_url != str(url or "").strip():
                meta["source_asset_url"] = inferred_source_url
                meta["source_asset_auto"] = "same_name_other_episode_active"
                if inferred_source.get("asset_id"):
                    meta["source_asset_id"] = inferred_source["asset_id"]
                if inferred_source.get("episode_id"):
                    meta["source_asset_episode_id"] = inferred_source["episode_id"]
                if inferred_source.get("episode_title"):
                    meta["source_asset_episode_title"] = inferred_source["episode_title"]
                if inferred_source.get("entity_id"):
                    meta["source_asset_entity_id"] = inferred_source["entity_id"]
                if inferred_source.get("entity_name"):
                    meta["source_asset_entity_name"] = inferred_source["entity_name"]
                if inferred_source.get("subject_type"):
                    meta["source_asset_subject_type"] = inferred_source["subject_type"]

        media_kind = "image" if is_image else ("video" if is_video else ("audio" if is_audio else None))
        meta = enrich_asset_meta_info(
            meta,
            url=url,
            media_kind=media_kind,
            local_path=file_path if os.path.isfile(file_path) else None,
        )

        remark = get_attr(req, "remark")
        if not remark:
            provider = meta.get("provider", "Unknown")
            if get_attr(req, "entity_name"):
                 remark = f"Auto-registered from Entity: {get_attr(req, 'entity_name')} ({provider})"
            else:
                 remark = f"Generated {get_attr(req, 'asset_type')} for Shot {get_attr(req, 'shot_number')} by {provider}"

        with ASSET_REGISTRATION_LOCK:
            existing_asset = _find_existing_asset_for_registration(
                db,
                user_id,
                url=url,
                idempotency_key=meta.get("idempotency_key"),
                meta_info=meta,
            )
            if existing_asset:
                normalized_existing_url = _normalize_asset_url_for_dedup(getattr(existing_asset, "url", None))
                if normalized_existing_url and str(getattr(existing_asset, "url_normalized", "") or "").strip() != normalized_existing_url:
                    existing_asset.url_normalized = normalized_existing_url
                enriched_meta = enrich_asset_meta_info(
                    _asset_meta_dict(existing_asset.meta_info),
                    url=str(existing_asset.url or url or ""),
                    media_kind=str(existing_asset.type or media_kind or ""),
                )
                if enriched_meta != _asset_meta_dict(existing_asset.meta_info):
                    existing_asset.meta_info = enriched_meta
                _sync_asset_denormalized_fields(existing_asset)
                if existing_asset.project_id:
                    _mark_asset_as_current_project_asset(db, existing_asset)
                    db.commit()
                return existing_asset

            is_image_inferred = is_image
            is_video_inferred = is_video
            is_audio_inferred = is_audio
            if not is_image and not is_video and not is_audio:
                # Fallback based on metadata provider/model if possible
                provider_str = str(meta.get("provider", "")).lower()
                model_str = str(meta.get("model", "")).lower()
                if "video" in model_str or "video" in provider_str or any(k in provider_str for k in ("luma", "runway", "kling", "minimax")):
                    is_video_inferred = True
                elif "audio" in model_str or "tts" in model_str or "voice" in model_str:
                    is_audio_inferred = True
                else:
                    # Default to image if the extension and metadata are unknown
                    is_image_inferred = True

            asset = Asset(
                user_id=user_id,
                type=("image" if is_image_inferred else ("audio" if is_audio_inferred else "video")),
                url=url,
                url_normalized=_normalize_asset_url_for_dedup(url),
                filename=fname,
                project_id=_asset_optional_int(meta.get("project_id")),
                episode_id=_asset_optional_int(meta.get("episode_id")),
                meta_info=meta,
                remark=remark
            )
            try:
                with db.begin_nested():
                    db.add(asset)
                    db.flush()
            except IntegrityError:
                # Concurrent / signed-URL duplicate of uq_assets_user_type_scope_url_norm.
                existing_after_conflict = _find_existing_asset_for_registration(
                    db,
                    user_id,
                    url=url,
                    idempotency_key=meta.get("idempotency_key"),
                    meta_info=meta,
                )
                if existing_after_conflict:
                    return existing_after_conflict
                raise
            _mark_asset_as_current_project_asset(db, asset)
            db.commit()
            return asset
    except Exception as e:
        logger.warning("[AssetRegister] failed | user_id=%s url=%s err=%s", user_id, str(url or "")[:180], e)
        return None


def _extract_provider_model_from_result(result: Any, req: Any) -> Tuple[Optional[str], Optional[str]]:
    provider = None
    model = None
    if isinstance(result, dict):
        meta = result.get("metadata")
        if isinstance(meta, dict):
            provider = str(meta.get("provider") or "").strip() or None
            model = str(meta.get("model") or "").strip() or None

    if not provider:
        provider = str(getattr(req, "provider", None) or "").strip() or None
    if not model:
        model = str(getattr(req, "model", None) or "").strip() or None
    return provider, model


def _extract_llm_routing_metadata(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}

    routing_meta = payload.get("routing_metadata") if isinstance(payload.get("routing_metadata"), dict) else {}
    smart_meta = payload.get("smart_routing") if isinstance(payload.get("smart_routing"), dict) else {}

    provider = str(
        routing_meta.get("provider")
        or payload.get("provider")
        or ""
    ).strip() or None
    model = str(
        routing_meta.get("model")
        or payload.get("model")
        or ""
    ).strip() or None

    system_api_id_raw = (
        routing_meta.get("system_api_id")
        if routing_meta.get("system_api_id") is not None
        else payload.get("system_api_id")
    )
    if system_api_id_raw is None:
        system_api_id_raw = smart_meta.get("system_api_id")
    try:
        system_api_id = int(system_api_id_raw) if system_api_id_raw is not None else None
    except Exception:
        system_api_id = None

    metadata: Dict[str, Any] = {}
    if provider:
        metadata["provider"] = provider
    if model:
        metadata["model"] = model
    if system_api_id is not None:
        metadata["system_api_id"] = system_api_id
    if smart_meta:
        metadata["smart_routing"] = smart_meta
    return metadata


def _apply_llm_routing_to_billing_details(details: Dict[str, Any], payload: Any) -> None:
    if not isinstance(details, dict):
        return
    routing = _extract_llm_routing_metadata(payload)
    if routing:
        details.update(routing)
    # Prefer provider usage from LLM response payload (Grsai/OpenAI-compatible),
    # same actual-supplier path as Seedance token settles.
    usage = None
    if isinstance(payload, dict):
        nested = payload.get("usage")
        if isinstance(nested, dict) and nested:
            usage = nested
        elif payload.get("token_source") or payload.get("prompt_tokens") is not None or payload.get("completion_tokens") is not None:
            usage = payload
    _attach_llm_provider_usage_to_billing_details(details, usage)


def _attach_llm_provider_usage_to_billing_details(
    details: Dict[str, Any],
    usage: Optional[Dict[str, Any]] = None,
) -> None:
    """Mark settle details with API token usage so 实际供应商价 uses provider tokens."""
    if not isinstance(details, dict):
        return
    usage = usage if isinstance(usage, dict) else {}
    token_source = str(
        usage.get("token_source") or details.get("token_source") or ""
    ).strip().lower()
    total_tokens = _resolve_usage_token_total(details) or _resolve_usage_token_total(usage)
    if token_source == "api_usage" and total_tokens > 0:
        details["token_source"] = "api_usage"
        details.setdefault(
            "billing_basis",
            str(usage.get("billing_basis") or details.get("billing_basis") or "provider_tokens"),
        )
        details.setdefault(
            "usage_source",
            str(usage.get("usage_source") or details.get("usage_source") or "provider").strip() or "provider",
        )
        slim: Dict[str, Any] = {}
        for key in (
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "input_tokens",
            "output_tokens",
        ):
            value = usage.get(key)
            if value in (None, ""):
                value = details.get(key)
            if value not in (None, ""):
                slim[key] = value
        if slim:
            details["provider_usage"] = slim
    elif token_source == "estimate":
        details["token_source"] = "estimate"


def _safe_int_token(value: Any) -> int:
    try:
        parsed = int(value or 0)
        return parsed if parsed > 0 else 0
    except Exception:
        return 0


def _extract_provider_usage_from_metadata(metadata: Any) -> Dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}

    for key in ("provider_usage", "usage"):
        value = metadata.get(key)
        if isinstance(value, dict) and value:
            return dict(value)

    # KIE callback may persist scalar creditsConsumed on metadata root.
    for key in ("kie_credits_consumed", "credits_consumed", "creditsConsumed"):
        if metadata.get(key) not in (None, ""):
            try:
                amount = float(metadata.get(key) or 0)
            except Exception:
                amount = 0.0
            if amount > 0:
                return {
                    "creditsConsumed": amount,
                    "credits_consumed": amount,
                    "kie_credits_consumed": amount,
                    "credits": amount,
                }

    raw_payload = metadata.get("raw")
    if isinstance(raw_payload, dict):
        try:
            from app.services.media_service import _extract_provider_task_usage, _normalize_provider_task_usage

            normalized = _normalize_provider_task_usage(_extract_provider_task_usage(raw_payload))
            if normalized:
                return normalized
        except Exception:
            pass
        raw_usage = raw_payload.get("usage")
        if isinstance(raw_usage, dict) and raw_usage:
            return dict(raw_usage)
        for nested_key in ("data", "output", "result", "content"):
            nested = raw_payload.get(nested_key)
            if isinstance(nested, dict):
                nested_usage = nested.get("usage")
                if isinstance(nested_usage, dict) and nested_usage:
                    return dict(nested_usage)
                for credit_key in ("creditsConsumed", "credits_consumed", "kie_credits_consumed"):
                    if nested.get(credit_key) not in (None, ""):
                        try:
                            amount = float(nested.get(credit_key) or 0)
                        except Exception:
                            amount = 0.0
                        if amount > 0:
                            return {
                                "creditsConsumed": amount,
                                "credits_consumed": amount,
                                "kie_credits_consumed": amount,
                                "credits": amount,
                            }

    return {}


async def _maybe_refresh_kie_credits_from_record_info(
    metadata: Any,
    provider: Optional[str] = None,
) -> float:
    """For KIE non-callback/jobs tasks: GET recordInfo?taskId=... when credits missing."""
    if not isinstance(metadata, dict):
        return 0.0
    provider_l = str(provider or metadata.get("provider") or "").strip().lower()
    if not (provider_l == "kie" or provider_l.startswith("kie/") or "kie.ai" in provider_l):
        return 0.0

    task_id = str(
        metadata.get("task_id")
        or metadata.get("taskId")
        or metadata.get("provider_task_id")
        or ""
    ).strip()
    if not task_id or task_id.lower() in {"undefined", "null", "none"}:
        return 0.0

    query_endpoint = str(
        metadata.get("query_endpoint")
        or metadata.get("queryEndpoint")
        or "https://api.kie.ai/api/v1/jobs/recordInfo"
    ).strip()
    api_key = ""
    try:
        from app.db.session import SessionLocal
        from app.models.all_models import SystemAPISetting

        db = SessionLocal()
        try:
            system_api_id = metadata.get("system_api_id")
            row = None
            try:
                sid = int(system_api_id) if system_api_id is not None else 0
            except Exception:
                sid = 0
            if sid > 0:
                row = db.query(SystemAPISetting).filter(SystemAPISetting.id == sid).first()
            if row is None:
                candidates = (
                    db.query(SystemAPISetting)
                    .filter(SystemAPISetting.provider.isnot(None))
                    .order_by(SystemAPISetting.id.desc())
                    .limit(40)
                    .all()
                )
                for candidate in candidates:
                    provider_text = str(getattr(candidate, "provider", "") or "").strip().lower()
                    base_url = str(getattr(candidate, "base_url", "") or "").strip().lower()
                    if provider_text == "kie" or provider_text.startswith("kie/") or "kie.ai" in base_url:
                        row = candidate
                        break
            if row is not None:
                raw_key = str(getattr(row, "api_key", "") or "").strip()
                api_key = raw_key.split(",")[0].strip() if raw_key else ""
                conf = getattr(row, "config", None)
                if isinstance(conf, dict):
                    query_endpoint = str(conf.get("query_endpoint") or query_endpoint).strip()
        finally:
            db.close()
    except Exception:
        api_key = ""
    if not api_key:
        return 0.0

    try:
        from app.services.media_service import media_service
        from app.services.billing_pricing import resolve_provider_kie_credits

        usage = await asyncio.to_thread(
            media_service.fetch_provider_task_usage,
            task_id=task_id,
            api_key=api_key,
            query_endpoint=query_endpoint,
            provider="kie",
            refresh_if_missing=True,
        )
        credits = float(resolve_provider_kie_credits(usage) or 0.0)
        if credits > 0:
            metadata["provider_usage"] = usage
            metadata["usage_source"] = "kie_recordInfo_settle_refresh"
            metadata["creditsConsumed"] = credits
            metadata["credits_consumed"] = credits
            metadata["kie_credits_consumed"] = credits
            logger.info(
                "[Billing] KIE recordInfo settle refresh | task_id=%s creditsConsumed=%s",
                task_id,
                credits,
            )
        return credits
    except Exception as exc:
        logger.warning(
            "[Billing] KIE recordInfo settle refresh failed | task_id=%s error=%s",
            task_id,
            exc,
        )
        return 0.0


def _resolve_usage_token_total(usage: Any) -> int:
    """Resolve billable token total from provider usage (Ark: total_tokens / completion_tokens)."""
    if not isinstance(usage, dict) or not usage:
        return 0
    total = _safe_int_token(usage.get("total_tokens"))
    if total > 0:
        return total
    output = _safe_int_token(usage.get("output_tokens") or usage.get("completion_tokens"))
    if output > 0:
        prompt = _safe_int_token(usage.get("input_tokens") or usage.get("prompt_tokens"))
        return prompt + output if prompt > 0 else output
    return 0


def _build_standard_billing_details(
    *,
    item: str,
    usage_payload: Optional[Dict[str, Any]] = None,
    extra_details: Optional[Dict[str, Any]] = None,
    routing_payload: Any = None,
) -> Dict[str, Any]:
    details: Dict[str, Any] = {
        "item": str(item or "").strip() or "unknown",
        "billing_mode": "ACTUAL",
        "audit_source": "endpoints",
    }

    usage = usage_payload if isinstance(usage_payload, dict) else {}
    if usage:
        input_tokens = _safe_int_token(usage.get("input_tokens") or usage.get("prompt_tokens"))
        output_tokens = _safe_int_token(usage.get("output_tokens") or usage.get("completion_tokens"))
        total_tokens = _safe_int_token(usage.get("total_tokens"))
        if total_tokens <= 0:
            total_tokens = input_tokens + output_tokens

        details.update({
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
        })
        # Local estimate fallback has no token_source; provider usage is tagged api_usage.
        if str(usage.get("token_source") or "").strip().lower() != "api_usage" and total_tokens > 0:
            details.setdefault("token_source", "estimate")

    if isinstance(extra_details, dict) and extra_details:
        details.update(extra_details)

    _apply_llm_routing_to_billing_details(details, routing_payload)
    _attach_llm_provider_usage_to_billing_details(details, usage)
    return details


def _reservation_tx_id(reservation_tx: Any) -> Optional[int]:
    if reservation_tx is None:
        return None
    try:
        if isinstance(reservation_tx, int):
            parsed = int(reservation_tx)
            return parsed if parsed > 0 else None
    except Exception:
        pass

    try:
        raw_dict = getattr(reservation_tx, "__dict__", None)
        if isinstance(raw_dict, dict):
            raw_id = raw_dict.get("id")
            if raw_id is not None:
                parsed = int(raw_id or 0)
                if parsed > 0:
                    return parsed
    except Exception:
        pass

    try:
        state = inspect(reservation_tx)
        identity = getattr(state, "identity", None)
        if identity and len(identity) > 0:
            parsed = int(identity[0] or 0)
            if parsed > 0:
                return parsed
    except Exception:
        pass

    try:
        parsed = int(getattr(reservation_tx, "id", 0) or 0)
        return parsed if parsed > 0 else None
    except Exception:
        return None


def _finalize_model_invocation_billing(
    *,
    db: Session,
    current_user: User,
    task_type: str,
    provider: Optional[str],
    model: Optional[str],
    reservation_tx: Any,
    reservation_tx_id: Optional[int] = None,
    item: str,
    usage_payload: Optional[Dict[str, Any]] = None,
    extra_details: Optional[Dict[str, Any]] = None,
    routing_payload: Any = None,
    cancel_if_missing_usage: bool = False,
    missing_usage_reason: str = "No usage returned",
) -> Dict[str, Any]:
    details = _build_standard_billing_details(
        item=item,
        usage_payload=usage_payload,
        extra_details=extra_details,
        routing_payload=routing_payload,
    )

    tx_id: Optional[int] = None
    if reservation_tx_id is not None:
        try:
            parsed = int(reservation_tx_id)
            tx_id = parsed if parsed > 0 else None
        except Exception:
            tx_id = None
    if tx_id is None:
        tx_id = _reservation_tx_id(reservation_tx)

    if tx_id is not None:
        if cancel_if_missing_usage and not isinstance(usage_payload, dict):
            billing_service.cancel_reservation(db, tx_id, missing_usage_reason)
            return details
        billing_service.settle_reservation(db, tx_id, details)
        return details

    billing_service.deduct_credits(
        db,
        current_user.id,
        task_type,
        provider,
        model,
        details,
    )
    return details


def _cancel_reservation_quietly(db: Session, reservation_tx: Any, reason: str) -> None:
    if reservation_tx is None:
        return

    tx_id = None
    try:
        if isinstance(reservation_tx, int):
            tx_id = int(reservation_tx)
        else:
            tx_id = int(getattr(reservation_tx, "id", 0) or 0)
    except Exception:
        tx_id = None

    if tx_id is None or tx_id <= 0:
        return

    try:
        billing_service.cancel_reservation(db, tx_id, str(reason or "cancelled"))
    except Exception:
        pass


def _resolve_latest_asset_provider_model(
    db: Session,
    user_id: int,
    shot_id: Optional[int],
    media_type: str,
    asset_type: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    if not shot_id:
        return None, None

    normalized_media_type = str(media_type or "").strip().lower()
    if normalized_media_type not in {"image", "video"}:
        return None, None

    normalized_asset_type = str(asset_type or "").strip().lower() or None

    candidates = (
        db.query(Asset)
        .filter(Asset.user_id == user_id, Asset.type == normalized_media_type)
        .order_by(Asset.id.desc())
        .limit(300)
        .all()
    )

    shot_id_str = str(shot_id)
    for asset in candidates:
        meta = asset.meta_info if isinstance(asset.meta_info, dict) else {}
        if str(meta.get("shot_id") or "").strip() != shot_id_str:
            continue

        previous_asset_type = str(meta.get("asset_type") or meta.get("frame_type") or "").strip().lower() or None
        if normalized_asset_type and previous_asset_type and previous_asset_type != normalized_asset_type:
            continue

        prev_provider = str(meta.get("provider") or "").strip() or None
        prev_model = str(meta.get("model") or "").strip() or None
        return prev_provider, prev_model

    return None, None


def _log_api_switch_regenerate_if_needed(
    db: Session,
    current_user: User,
    req: Any,
    result: Any,
    media_type: str,
) -> None:
    try:
        shot_id_raw = getattr(req, "shot_id", None)
        shot_id = int(shot_id_raw) if shot_id_raw else None
    except Exception:
        return

    if not shot_id:
        return

    current_provider, current_model = _extract_provider_model_from_result(result, req)
    if not current_provider and not current_model:
        return

    req_asset_type = str(getattr(req, "asset_type", None) or "").strip().lower() or None
    prev_provider, prev_model = _resolve_latest_asset_provider_model(
        db=db,
        user_id=current_user.id,
        shot_id=shot_id,
        media_type=media_type,
        asset_type=req_asset_type,
    )

    if not prev_provider and not prev_model:
        return

    if (prev_provider or "") == (current_provider or "") and (prev_model or "") == (current_model or ""):
        return

    action = "SHOT_REGENERATE_IMAGE_API_SWITCH" if str(media_type).lower() == "image" else "SHOT_REGENERATE_VIDEO_API_SWITCH"
    detail_parts = [
        f"shot_id={shot_id}",
        f"asset_type={req_asset_type or 'unknown'}",
        f"from_provider={prev_provider or 'unknown'}",
        f"from_model={prev_model or 'unknown'}",
        f"to_provider={current_provider or 'unknown'}",
        f"to_model={current_model or 'unknown'}",
    ]
    project_id = getattr(req, "project_id", None)
    if project_id is not None:
        detail_parts.append(f"project_id={project_id}")

    log_action(
        db,
        user_id=current_user.id,
        user_name=current_user.username,
        action=action,
        details="; ".join(detail_parts),
    )


def _bind_generated_media_to_shot(
    db: Session,
    current_user: User,
    req: Any,
    media_url: Optional[str],
    oss_uploaded_success: Optional[bool] = None,
    media_metadata: Optional[Dict[str, Any]] = None,
) -> None:
    if not media_url:
        return

    def get_attr(obj, key):
        if isinstance(obj, dict):
            return obj.get(key)
        return getattr(obj, key, None)

    shot_id = get_attr(req, "shot_id")
    if not shot_id:
        return

    try:
        shot_id_int = int(shot_id)
    except Exception:
        return

    shot = db.query(Shot).filter(Shot.id == shot_id_int).first()
    if not shot:
        return

    try:
        project_id = shot.project_id
        if not project_id and shot.scene_id:
            scene = db.query(Scene).filter(Scene.id == shot.scene_id).first()
            if scene and scene.episode_id:
                episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
                if episode:
                    project_id = episode.project_id
        if project_id:
            _require_project_access(db, int(project_id), current_user)
    except Exception:
        return

    asset_type = str(get_attr(req, "asset_type") or "").strip().lower()
    changed = False

    normalized_media_metadata: Optional[Dict[str, Any]] = None
    if isinstance(media_metadata, dict):
        try:
            normalized_media_metadata = json.loads(json.dumps(media_metadata, ensure_ascii=False, default=str))
        except Exception:
            normalized_media_metadata = dict(media_metadata)

    bind_context: Dict[str, Any] = {}
    for bind_key in (
        "provider", "model", "prompt", "negative_prompt", "aspect_ratio", "duration", "seed",
        "width", "height", "resolution", "image_size", "system_api_id", "shot_id", "project_id",
        "episode_id", "scene_id", "shot_number", "shot_name", "asset_type", "job_id", "idempotency_key",
    ):
        bind_value = get_attr(req, bind_key)
        if bind_value not in (None, ""):
            bind_context[bind_key] = bind_value
    if isinstance(normalized_media_metadata, dict):
        normalized_media_metadata = _enrich_media_metadata_from_generation_context(
            normalized_media_metadata,
            bind_context,
        )

    tech = {}
    try:
        tech = json.loads(shot.technical_notes or "{}")
        if not isinstance(tech, dict):
            tech = {}
    except Exception:
        tech = {}

    if asset_type in {"start_frame", "start"}:
        metadata_changed = False
        start_url_changed = shot.image_url != media_url
        if isinstance(normalized_media_metadata, dict):
            previous_meta = tech.get("start_frame_metadata")
            if not isinstance(previous_meta, dict) or previous_meta != normalized_media_metadata:
                tech["start_frame_metadata"] = normalized_media_metadata
                metadata_changed = True
        if start_url_changed:
            start_meta = tech.get("start_frame_metadata") if isinstance(tech.get("start_frame_metadata"), dict) else {}
            tech["start_frame_metadata"] = _ensure_media_bound_at(start_meta, refresh=True)
            metadata_changed = True
        if (
            shot.image_url != media_url
            or (oss_uploaded_success is not None and tech.get("start_frame_oss_uploaded") != oss_uploaded_success)
            or metadata_changed
        ):
            shot.image_url = media_url
            if oss_uploaded_success is not None:
                tech["start_frame_oss_uploaded"] = oss_uploaded_success
            shot.technical_notes = json.dumps(tech, ensure_ascii=False)
            changed = True

    elif asset_type in {"end_frame", "end"}:
        metadata_changed = False
        end_url_changed = tech.get("end_frame_url") != media_url
        if isinstance(normalized_media_metadata, dict):
            previous_meta = tech.get("end_frame_metadata")
            if not isinstance(previous_meta, dict) or previous_meta != normalized_media_metadata:
                tech["end_frame_metadata"] = normalized_media_metadata
                metadata_changed = True
        if end_url_changed:
            end_meta = tech.get("end_frame_metadata") if isinstance(tech.get("end_frame_metadata"), dict) else {}
            tech["end_frame_metadata"] = _ensure_media_bound_at(end_meta, refresh=True)
            metadata_changed = True
        if (
            tech.get("end_frame_url") != media_url
            or (oss_uploaded_success is not None and tech.get("end_frame_oss_uploaded") != oss_uploaded_success)
            or metadata_changed
        ):
            tech["end_frame_url"] = media_url
            if oss_uploaded_success is not None:
                tech["end_frame_oss_uploaded"] = oss_uploaded_success
            shot.technical_notes = json.dumps(tech, ensure_ascii=False)
            changed = True

    elif asset_type == "video":
        metadata_changed = False
        video_url_changed = shot.video_url != media_url
        if isinstance(normalized_media_metadata, dict):
            previous_meta = tech.get("video_metadata")
            if not isinstance(previous_meta, dict) or previous_meta != normalized_media_metadata:
                tech["video_metadata"] = normalized_media_metadata
                metadata_changed = True
        if video_url_changed:
            video_meta = dict(normalized_media_metadata) if isinstance(normalized_media_metadata, dict) else (
                tech.get("video_metadata") if isinstance(tech.get("video_metadata"), dict) else {}
            )
            video_meta = _ensure_media_bound_at(video_meta, refresh=True)
            video_meta = _enrich_media_metadata_from_generation_context(video_meta, bind_context)
            tech["video_metadata"] = video_meta
            metadata_changed = True
        if (
            shot.video_url != media_url
            or (oss_uploaded_success is not None and tech.get("video_oss_uploaded") != oss_uploaded_success)
            or metadata_changed
        ):
            shot.video_url = media_url
            if oss_uploaded_success is not None:
                tech["video_oss_uploaded"] = oss_uploaded_success
            shot.technical_notes = json.dumps(tech, ensure_ascii=False)
            changed = True

    if not changed:
        return

    db.add(shot)
    db.commit()
    logger.info(
        "[ShotMediaBind] shot_id=%s asset_type=%s media_url=%s project_id=%s user_id=%s",
        shot_id_int,
        asset_type or None,
        media_url,
        getattr(shot, "project_id", None),
        getattr(current_user, "id", None),
    )


def _bind_generated_media_to_entity(db: Session, current_user: User, req: Any, media_url: Optional[str], oss_uploaded_success: Optional[bool] = None) -> None:
    if not media_url:
        return

    def get_attr(obj, key):
        if isinstance(obj, dict):
            return obj.get(key)
        return getattr(obj, key, None)

    asset_type = str(get_attr(req, "asset_type") or "").strip().lower()
    if asset_type != "subject":
        logger.info(
            "[SubjectMediaBind] skipped non-subject asset_type=%s media_url=%s user_id=%s",
            asset_type or None,
            media_url,
            getattr(current_user, "id", None),
        )
        return

    entity = None
    project = None
    entity_id_raw = get_attr(req, "entity_id")
    if entity_id_raw is not None:
        try:
            entity = db.query(Entity).filter(Entity.id == int(entity_id_raw)).first()
        except Exception:
            entity = None

    if not entity:
        subject_label = str(get_attr(req, "entity_name") or get_attr(req, "subject_name") or "").strip()
        project_id_raw = get_attr(req, "project_id")
        try:
            project_id = int(project_id_raw) if project_id_raw is not None else None
        except Exception:
            project_id = None
        if subject_label and project_id:
            entity = db.query(Entity).filter(
                Entity.project_id == project_id,
                or_(Entity.name == subject_label, Entity.name_en == subject_label),
            ).order_by(Entity.id.desc()).first()

    if not entity:
        logger.warning(
            "[SubjectMediaBind] entity_not_found entity_id=%s entity_name=%s subject_name=%s project_id=%s media_url=%s user_id=%s",
            entity_id_raw,
            get_attr(req, "entity_name"),
            get_attr(req, "subject_name"),
            get_attr(req, "project_id"),
            media_url,
            getattr(current_user, "id", None),
        )
        return

    try:
        project = _require_project_access(db, int(entity.project_id), current_user)
    except Exception:
        return

    stable_media_url = str(media_url or "").strip()
    if _is_ephemeral_provider_media_url(stable_media_url):
        stable_media_url = _resolve_precise_asset_library_url(
            db,
            current_user,
            stable_media_url,
            project=project,
            entity_id=getattr(entity, "id", None),
            asset_type_aliases={"subject", "character", "char"},
            media_type="image",
        ) or ""
        if not stable_media_url:
            logger.warning(
                "[SubjectMediaBind] skipped temporary media url | entity_id=%s name=%s project_id=%s media_url=%s user_id=%s",
                getattr(entity, "id", None),
                getattr(entity, "name", None) or getattr(entity, "name_en", None),
                getattr(entity, "project_id", None),
                media_url,
                getattr(current_user, "id", None),
            )
            return

    tech_attrs = {}
    try:
        tech_attrs = json.loads(entity.custom_attributes or "{}")
        if not isinstance(tech_attrs, dict): tech_attrs = {}
    except Exception:
        pass

    if str(entity.image_url or "").strip() == stable_media_url and (oss_uploaded_success is None or tech_attrs.get("oss_uploaded_success") == oss_uploaded_success):
        logger.info(
            "[SubjectMediaBind] unchanged | entity_id=%s name=%s project_id=%s media_url=%s user_id=%s",
            getattr(entity, "id", None),
            getattr(entity, "name", None) or getattr(entity, "name_en", None),
            getattr(entity, "project_id", None),
            stable_media_url,
            getattr(current_user, "id", None),
        )
        return

    logger.info(
        "[SubjectMediaBind] update_begin | entity_id=%s name=%s project_id=%s previous_url=%s next_url=%s user_id=%s",
        getattr(entity, "id", None),
        getattr(entity, "name", None) or getattr(entity, "name_en", None),
        getattr(entity, "project_id", None),
        getattr(entity, "image_url", None),
        stable_media_url,
        getattr(current_user, "id", None),
    )
    if oss_uploaded_success is not None:
        tech_attrs["oss_uploaded_success"] = oss_uploaded_success
        entity.custom_attributes = json.dumps(tech_attrs, ensure_ascii=False)
        
    if oss_uploaded_success is not None:
        tech_attrs["oss_uploaded_success"] = oss_uploaded_success
        entity.custom_attributes = json.dumps(tech_attrs, ensure_ascii=False)
        
    entity.image_url = stable_media_url
    db.add(entity)
    db.commit()
    logger.info(
        "[SubjectMediaBind] entity_id=%s name=%s project_id=%s media_url=%s user_id=%s",
        getattr(entity, "id", None),
        getattr(entity, "name", None) or getattr(entity, "name_en", None),
        getattr(entity, "project_id", None),
        stable_media_url,
        getattr(current_user, "id", None),
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

def _resolve_media_runtime_target(
    *,
    provider: Optional[str],
    model: Optional[str],
    media_type: str,
    category: str,
    user_id: int,
    user_credits: int,
    function_name: Optional[str] = None,
    system_api_id: Optional[int] = None,
) -> Dict[str, Any]:
    runtime_llm_config = _build_runtime_llm_config(provider, model, media_type=media_type)
    pre_api_cfg: Dict[str, Any] = {}
    user_explicit_provider = bool(str(provider or "").strip())
    user_explicit_model = bool(str(model or "").strip())
    user_explicit_selection = bool(user_explicit_provider or user_explicit_model)

    try:
        strict_provider = user_explicit_provider
        pre_api_cfg = media_service.get_api_config(
            provider=provider,
            user_id=user_id,
            category=category,
            requested_model=model,
            user_credits=user_credits,
            strict_provider=strict_provider,
            function_name=function_name,
            system_api_id=system_api_id,
        ) or {}

        resolved_provider = str((pre_api_cfg or {}).get("provider") or "").strip()
        resolved_model = str((pre_api_cfg or {}).get("model") or "").strip()
        if resolved_provider and resolved_model:
            runtime_llm_config = {"provider": resolved_provider, "model": resolved_model}
    except Exception:
        pre_api_cfg = pre_api_cfg or {}

    if not isinstance(runtime_llm_config, dict):
        runtime_llm_config = {}
    runtime_llm_config["__user_explicit_provider"] = user_explicit_provider
    runtime_llm_config["__user_explicit_model"] = user_explicit_model
    runtime_llm_config["__user_explicit_selection"] = user_explicit_selection

    resolved_provider = str((runtime_llm_config or {}).get("provider") or provider or "").strip() or None
    resolved_model = str((runtime_llm_config or {}).get("model") or model or "").strip() or None

    resolved_system_api_id = None
    try:
        cfg_payload = (pre_api_cfg or {}).get("config") if isinstance((pre_api_cfg or {}).get("config"), dict) else {}
        raw_id = cfg_payload.get("__resolved_setting_id") if isinstance(cfg_payload, dict) else None
        if raw_id is None:
            raw_id = (pre_api_cfg or {}).get("system_api_id")
        resolved_system_api_id = int(raw_id) if raw_id is not None else None
    except Exception:
        resolved_system_api_id = None

    return {
        "runtime_llm_config": runtime_llm_config or {},
        "pre_api_cfg": pre_api_cfg or {},
        "resolved_provider": resolved_provider,
        "resolved_model": resolved_model,
        "resolved_system_api_id": resolved_system_api_id,
    }


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


def _set_image_job(job_id: str, **fields) -> None:
    with IMAGE_JOB_LOCK:
        _prune_image_jobs_locked()
        current = IMAGE_JOB_STORE.get(job_id, {})
        previous_status = str(current.get("status") or "").strip().lower()
        previous_result_url = _extract_job_result_url(current.get("result"))
        if "result" in fields:
            fields["result"] = _compact_job_result(fields.get("result"))
        current.update(fields)
        current["job_id"] = job_id
        IMAGE_JOB_STORE[job_id] = current

        status = str(current.get("status") or "").strip().lower()
        result_url = _extract_job_result_url(current.get("result"))
        if status != previous_status or (result_url and result_url != previous_result_url):
            logger.info(
                "[ImageJob] state updated | job_id=%s prev_status=%s status=%s has_result_url=%s result_url=%s error=%s",
                job_id,
                previous_status or None,
                status or None,
                bool(result_url),
                result_url or None,
                current.get("error"),
            )
        if status in {"succeeded", "failed", "canceled", "cancelled", "error"}:
            task_scope = str(current.get("task_scope") or "").strip()
            if task_scope and IMAGE_ACTIVE_SCOPE_STORE.get(task_scope) == job_id:
                IMAGE_ACTIVE_SCOPE_STORE.pop(task_scope, None)

        _write_image_job_file(job_id, current)

    _clear_generation_job_pool_cache()


def _normalize_callback_url(raw: Any) -> str:
    url = str(raw or "").strip()
    if not url:
        return ""
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme.lower() not in {"http", "https"}:
            return ""
        if not parsed.netloc:
            return ""
        return url
    except Exception:
        return ""


def _resolve_callback_url_from_payload(payload: Any) -> str:
    if isinstance(payload, dict):
        for key in ("callback_url", "callbackUrl", "callBackUrl"):
            val = payload.get(key)
            normalized = _normalize_callback_url(val)
            if normalized:
                return normalized
        return ""

    for key in ("callback_url", "callbackUrl", "callBackUrl"):
        try:
            val = getattr(payload, key, None)
        except Exception:
            val = None
        normalized = _normalize_callback_url(val)
        if normalized:
            return normalized
    return ""


def _build_generation_callback_payload(kind: str, job: Dict[str, Any]) -> Dict[str, Any]:
    status = str(job.get("status") or "").strip().lower()
    return {
        "event": "generation.completed",
        "kind": kind,
        "job_id": job.get("job_id"),
        "status": status,
        "success": status == "succeeded",
        "user_id": job.get("user_id"),
        "username": job.get("username"),
        "created_at": job.get("created_at"),
        "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"),
        "error": job.get("error"),
        "result": job.get("result"),
    }


def _extract_local_generation_callback_ticket(callback_url: str) -> str:
    stable_url = str(callback_url or "").strip()
    if not stable_url:
        return ""

    try:
        parsed = urllib.parse.urlparse(stable_url)
    except Exception:
        return ""

    path = str(parsed.path or "").strip()
    api_prefix = str(settings.API_V1_STR or "").strip() or "/api/v1"
    callback_prefix = f"{api_prefix}/generate/callback/"
    if not path.startswith(callback_prefix):
        return ""

    expected_hosts: Set[str] = set()
    render_external_url = str(settings.RENDER_EXTERNAL_URL or "").strip()
    if render_external_url:
        try:
            expected_host = str(urllib.parse.urlparse(render_external_url).netloc or "").strip().lower()
            if expected_host:
                expected_hosts.add(expected_host)
        except Exception:
            pass

    expected_hosts.update({
        "localhost",
        "localhost:8000",
        "127.0.0.1",
        "127.0.0.1:8000",
    })

    request_host = str(parsed.netloc or "").strip().lower()
    if request_host and expected_hosts and request_host not in expected_hosts:
        return ""

    ticket = path[len(callback_prefix):].strip().strip("/")
    if not ticket:
        return ""
    try:
        return urllib.parse.unquote(ticket)
    except Exception:
        return ticket


async def _dispatch_generation_callback(kind: str, callback_url: str, job: Dict[str, Any]) -> None:
    if not callback_url:
        return

    callback_payload = _build_generation_callback_payload(kind, job)
    callback_result_url = _extract_job_result_url(callback_payload.get("result"))
    local_ticket = _extract_local_generation_callback_ticket(callback_url)
    if local_ticket:
        await asyncio.to_thread(_set_generation_callback_payload, local_ticket, callback_payload)
        logger.info(
            "[GenerationCallback] dispatched locally kind=%s job_id=%s callback_ticket=%s has_result_url=%s result_url=%s",
            kind,
            job.get("job_id"),
            local_ticket,
            bool(callback_result_url),
            callback_result_url or None,
        )
        return

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "AIStory-Callback/1.0",
        "X-AIStory-Event": "generation.completed",
        "X-AIStory-Job-Kind": kind,
        "X-AIStory-Job-Id": str(job.get("job_id") or ""),
    }

    secret = str(settings.WEBHOOK_HMAC_KEY or "").strip()
    task_id_for_signature = _extract_callback_task_id(callback_payload)
    if secret and task_id_for_signature:
        timestamp_seconds = int(time.time())
        headers["X-Webhook-Timestamp"] = str(timestamp_seconds)
        headers["X-Webhook-Signature"] = _compute_webhook_signature(
            task_id_for_signature,
            timestamp_seconds,
            secret,
        )

    try:
        def _post_callback() -> requests.Response:
            return requests.post(callback_url, json=callback_payload, headers=headers, timeout=15)

        response = await asyncio.to_thread(_post_callback)
        logger.info(
            "[GenerationCallback] dispatched kind=%s job_id=%s callback_url=%s status_code=%s has_result_url=%s result_url=%s",
            kind,
            job.get("job_id"),
            callback_url,
            getattr(response, "status_code", None),
            bool(callback_result_url),
            callback_result_url or None,
        )
    except Exception as e:
        logger.warning(
            "[GenerationCallback] failed kind=%s job_id=%s callback_url=%s error=%s",
            kind,
            job.get("job_id"),
            callback_url,
            e,
        )


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
        _set_image_job(
            job_id,
            status=_status_to_set,
            finished_at=_finished_at_val,
            result=result,
            error=None,
        )
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
    anchor = job.get("started_at")
    anchor_dt = _parse_iso_datetime(anchor)
    if not anchor_dt:
        return None
    return max(0, int((datetime.utcnow() - anchor_dt).total_seconds()))


def _job_is_subject_to_running_timeout(job: Dict[str, Any]) -> bool:
    status = _normalize_generation_status(job.get("status"))
    upstream_state = str(job.get("upstream_submit_state") or "").strip().lower()
    if status == "queued":
        return False
    if status in _JOB_TIMEOUT_CHECK_STATUSES:
        return True
    return "callback_pending" in upstream_state


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
    if not _job_is_subject_to_running_timeout(job):
        return job

    elapsed_seconds = _resolve_job_elapsed_seconds(job)
    if elapsed_seconds is None or elapsed_seconds < timeout_seconds:
        return job

    status = _normalize_generation_status(job.get("status"))
    upstream_state = str(job.get("upstream_submit_state") or "").strip().lower()
    is_callback_wait = (
        status in {"waiting_callback", "callback_processing"}
        or "callback_pending" in upstream_state
    )
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

    from app.services.generation_task_queue import mark_generation_task_status_external

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


# --- User Management ---
# /users/me* routes live in app.api.routers.auth

@router.get("/users", response_model=List[UserOut])
def get_users(
    skip: int = 0, 
    limit: int = 100, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    users = db.query(User).offset(skip).limit(limit).all()
    return users


@router.get("/users/page", response_model=UserPageOut)
def get_users_page(
    page: int = 1,
    page_size: int = 20,
    q: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    safe_page = max(int(page or 1), 1)
    safe_page_size = max(1, min(int(page_size or 20), 200))
    skip = (safe_page - 1) * safe_page_size
    keyword = str(q or "").strip()

    def _cached_entry_matches(entry: dict) -> bool:
        if not keyword:
            return True
        needle = keyword.casefold()
        username = str(entry.get("username") or "").casefold()
        full_name = str(entry.get("full_name") or "").casefold()
        user_id = str(entry.get("id") or "")
        return needle in username or needle in full_name or needle in user_id

    try:
        query = db.query(User)
        if keyword:
            like_pattern = f"%{keyword}%"
            filters = [
                User.username.ilike(like_pattern),
                User.full_name.ilike(like_pattern),
                cast(User.id, String).ilike(like_pattern),
            ]
            if keyword.isdigit():
                filters.append(User.id == int(keyword))
            query = query.filter(or_(*filters))
        total = int(query.count())
        items = (
            query
            .order_by(User.id.asc())
            .offset(skip)
            .limit(safe_page_size)
            .all()
        )
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning("get_users_page fallback to cached principals | user_id=%s error=%s", getattr(current_user, "id", None), type(exc).__name__)
        cached_entries = [entry for entry in list_cached_user_entries() if _cached_entry_matches(entry)]
        total = len(cached_entries)
        window = cached_entries[skip: skip + safe_page_size]
        items = [
            {
                "id": int(entry.get("id") or 0),
                "username": str(entry.get("username") or ""),
                "email": entry.get("email"),
                "full_name": entry.get("full_name"),
                "avatar_url": entry.get("avatar_url"),
                "is_active": _normalize_user_active_level(entry.get("is_active", USER_ACTIVE_LEVEL_DEFAULT), USER_ACTIVE_LEVEL_DEFAULT),
                "account_status": int(entry.get("account_status") or 1),
                "email_verified": bool(entry.get("email_verified", False)),
                "is_superuser": bool(entry.get("is_superuser", False)),
                "is_authorized": bool(entry.get("is_authorized", False)),
                "is_system": bool(entry.get("is_system", False)),
                "credits": int(entry.get("credits", 0) or 0),
            }
            for entry in window
        ]
    return {
        "items": items,
        "total": total,
        "page": safe_page,
        "page_size": safe_page_size,
    }

@router.put("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int, 
    user_in: UserUpdate, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    def _persist_update():
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        old_username = str(getattr(user, "username", "") or "").strip()

        if user_in.username is not None:
            next_username = (user_in.username or "").strip()
            if not next_username:
                raise HTTPException(status_code=400, detail="Username cannot be empty")
            dup = db.query(User).filter(User.username == next_username, User.id != user_id).first()
            if dup:
                raise HTTPException(status_code=400, detail="Username already registered")
            user.username = next_username

        if user_in.email is not None:
            next_email = (user_in.email or "").strip().lower()
            if not _is_valid_email_format(next_email):
                raise HTTPException(status_code=400, detail="Invalid email format")
            dup = db.query(User).filter(User.email == next_email, User.id != user_id).first()
            if dup:
                raise HTTPException(status_code=400, detail="Email already registered")
            user.email = next_email

        if user_in.full_name is not None:
            user.full_name = (user_in.full_name or "").strip() or None

        if user_in.is_active is not None:
            user.is_active = _normalize_user_active_level(user_in.is_active, USER_ACTIVE_LEVEL_DEFAULT)
        if user_in.account_status is not None:
            user.account_status = int(user_in.account_status)
            if user.account_status == -1:
                user.is_active = 0
                user.email_verified = False
        if user_in.email_verified is not None:
            user.email_verified = bool(user_in.email_verified)
            if user.email_verified and user.account_status == -1:
                user.account_status = 1
                if not _is_user_enabled(user.is_active):
                    user.is_active = USER_ACTIVE_LEVEL_DEFAULT
        if user_in.is_authorized is not None:
            user.is_authorized = user_in.is_authorized
        if user_in.is_superuser is not None:
            user.is_superuser = user_in.is_superuser
        if user_in.is_system is not None:
            if user_in.is_system:
                db.query(User).filter(User.id != user_id).update({"is_system": False})
            user.is_system = user_in.is_system

        if user_in.password:
            user.hashed_password = get_password_hash(user_in.password)

        db.commit()
        db.refresh(user)
        _refresh_user_identity_cache(user, old_username=old_username)
        return user

    return _run_with_schema_self_heal(db, _persist_update, context="update_user")


@router.post("/generate/video")
async def generate_video_endpoint(
    req: VideoGenerationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    dedup_key = _build_video_dedup_key(req, current_user.id)
    created_task = False

    async with _VIDEO_DEDUP_LOCK:
        now_ts = time.time()
        _cleanup_video_dedup_cache(now_ts)

        recent = _VIDEO_RECENT_RESULTS_BY_KEY.get(dedup_key)
        if isinstance(recent, dict) and (now_ts - float(recent.get("ts") or 0.0)) <= _VIDEO_DEDUP_WINDOW_SECONDS:
            logger.info(
                "[GenerateVideo] dedup recent-hit | user_id=%s shot_id=%s key=%s age_ms=%s",
                current_user.id,
                req.shot_id,
                dedup_key[:12],
                int((now_ts - float(recent.get("ts") or 0.0)) * 1000),
            )
            return recent.get("result")

        existing_task = _VIDEO_INFLIGHT_BY_KEY.get(dedup_key)
        if existing_task is None:
            _enforce_user_media_generation_parallel_limit(current_user)
            _release_db_connection(db, "generate_video_sync_wait")
            try:
                callback_ticket_val = f"video-shot-{req.shot_id}" if getattr(req, "shot_id", None) else None
                callback_url_val = str(media_service._resolve_provider_callback_url({}, callback_ticket_val) or "").strip() if callback_ticket_val else ""
            except Exception:
                callback_ticket_val = f"video-shot-{req.shot_id}" if getattr(req, "shot_id", None) else None
                callback_url_val = ""
            
            existing_task = asyncio.create_task(_run_generate_video(
                req,
                current_user,
                db,
                provider_callback_ticket=callback_ticket_val,
                provider_callback_url=callback_url_val
            ))
            _VIDEO_INFLIGHT_BY_KEY[dedup_key] = existing_task
            created_task = True
        else:
            logger.info(
                "[GenerateVideo] dedup inflight-hit | user_id=%s shot_id=%s key=%s",
                current_user.id,
                req.shot_id,
                dedup_key[:12],
            )

    try:
        _release_db_connection(db, "generate_video_sync_wait_existing")
        result = await existing_task
    finally:
        if created_task:
            async with _VIDEO_DEDUP_LOCK:
                if _VIDEO_INFLIGHT_BY_KEY.get(dedup_key) is existing_task:
                    _VIDEO_INFLIGHT_BY_KEY.pop(dedup_key, None)

    if created_task:
        async with _VIDEO_DEDUP_LOCK:
            _VIDEO_RECENT_RESULTS_BY_KEY[dedup_key] = {
                "ts": time.time(),
                "result": result,
            }

    return result


@router.post("/generate/voice")
async def generate_voice_endpoint(
    req: VoiceGenerationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reservation_tx = None
    voice_task_type = "voice_gen"
    runtime_target = _resolve_media_runtime_target(
        provider=req.provider,
        model=req.model,
        media_type="voice",
        category="Voice",
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
    is_token_billing = billing_service.is_token_pricing(db, voice_task_type, reserve_provider, reserve_model)

    try:
        stable_prompt_raw = str(req.prompt or "").strip()
        stable_prompt = _strip_subject_prompt_context_for_voice(stable_prompt_raw)
        if not stable_prompt:
            raise HTTPException(status_code=400, detail="Voice prompt is empty")

        # Early resolution of project/episode for billing
        voice_project_id = _normalize_seed_value(getattr(req, "project_id", None))
        voice_episode_id = None
        _voice_shot_id = _normalize_seed_value(getattr(req, "shot_id", None))
        if _voice_shot_id:
            _voice_shot = db.query(Shot).filter(Shot.id == _voice_shot_id).first()
            if _voice_shot and getattr(_voice_shot, "scene_id", None):
                _voice_scene = db.query(Scene).filter(Scene.id == _voice_shot.scene_id).first()
                if _voice_scene and _voice_scene.episode_id:
                    voice_episode_id = int(_voice_scene.episode_id)
                    if not voice_project_id:
                        _voice_ep = db.query(Episode).filter(Episode.id == voice_episode_id).first()
                        if _voice_ep and _voice_ep.project_id:
                            voice_project_id = int(_voice_ep.project_id)

        if is_token_billing:
            est_messages = [{"role": "user", "content": stable_prompt}]
            est_usage = billing_service.estimate_input_output_tokens_from_messages(est_messages, output_ratio=1.2)
            reserve_details = {
                "input_tokens": int(est_usage.get("input_tokens") or 0),
                "output_tokens": int(est_usage.get("output_tokens") or 0),
                "total_tokens": int(est_usage.get("total_tokens") or 0),
                "billing_mode": "RESERVE",
                "estimation_method": "voice_prompt_tokens",
            }
        else:
            reserve_details = {
                "duration": 5,
                "duration_seconds": 5,
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
        if voice_project_id:
            reserve_details["project_id"] = voice_project_id
        if voice_episode_id:
            reserve_details["episode_id"] = voice_episode_id

        reservation_tx = billing_service.reserve_credits(
            db,
            current_user.id,
            voice_task_type,
            reserve_provider,
            reserve_model,
            reserve_details,
        )

        resolved_project_id = _resolve_project_id_for_generation(req, db)
        project_seed = _ensure_project_generation_seed(db, resolved_project_id, current_user)
        explicit_seed = _normalize_seed_value(getattr(req, "seed", None))

        extracted_dialogue = _extract_dialogue_text_for_tts(stable_prompt)
        extracted_dialogue_lines = [line for line in str(extracted_dialogue or "").splitlines() if str(line or "").strip()]
        has_explicit_dialogue = bool(extracted_dialogue_lines)

        provider_options: Dict[str, Any] = _build_voice_suno_provider_options(req)
        planned_payload: Dict[str, Any] = {}
        planner_system_prompt = ""
        planner_user_prompt = ""
        planner_prompt_meta: Dict[str, Any] = {}
        effective_prompt = stable_prompt
        explicit_language_code = _normalize_language_code(req.language_code)
        explicit_project_language = str(req.project_language or "").strip()
        is_suno_voice = _is_suno_voice_runtime(reserve_model, provider_options)

        if bool(req.use_llm_param_planning) and not is_suno_voice:
            # Strict mode: voice TTS input must come from planner-extracted dialogue only.
            effective_prompt = ""
            planner_system_prompt, planner_user_prompt, planner_prompt_meta = _build_voice_tts_planner_prompts(stable_prompt)
            planner_system_prompt_override = str(req.planner_system_prompt or "").strip()
            if planner_system_prompt_override:
                planner_system_prompt = planner_system_prompt_override
                planner_prompt_meta = {
                    **(planner_prompt_meta or {}),
                    "template_source": "superuser_override",
                    "system_prompt_len": len(planner_system_prompt),
                    "user_prompt_len": len(planner_user_prompt or ""),
                }
            logger.info(
                "[GenerateVoice] planner prompts | user_id=%s source=%s system_prompt_len=%s user_prompt_len=%s",
                current_user.id,
                planner_prompt_meta.get("template_source"),
                planner_prompt_meta.get("system_prompt_len"),
                planner_prompt_meta.get("user_prompt_len"),
            )
            try:
                _release_db_connection(db, "generate_voice_planner_llm_call")
                planned_payload = await _plan_voice_params_with_llm(
                    current_user.id,
                    stable_prompt,
                    planner_prompts=(planner_system_prompt, planner_user_prompt),
                )
            except Exception as planning_err:
                logger.warning("[GenerateVoice] LLM planning failed: %s", planning_err)
                planned_payload = {}

            if planned_payload:
                raw_planned_text = str((planned_payload or {}).get("text") or "").strip()
                planned_payload = _sanitize_kie_tts_plan(planned_payload)
                planned_text = str(planned_payload.get("text") or "").strip()
                non_dialogue_text_stripped = bool(raw_planned_text) and (raw_planned_text != planned_text)
                fallback_dialogue_used = False
                logger.warning(
                    "[GenerateVoice] dialogue extraction | user_id=%s prompt_chars=%s has_explicit_dialogue=%s dialogue_line_count=%s dialogue_chars=%s planned_text_chars=%s fallback_dialogue_used=%s non_dialogue_text_stripped=%s",
                    current_user.id,
                    len(stable_prompt),
                    has_explicit_dialogue,
                    len(extracted_dialogue_lines),
                    len(extracted_dialogue),
                    len(planned_text),
                    fallback_dialogue_used,
                    non_dialogue_text_stripped,
                )
                if planned_text:
                    effective_prompt = planned_text
                    effective_prompt = _extract_dialogue_text_for_tts(effective_prompt)
                for key in [
                    "text",
                    "voice",
                    "language_code",
                    "stability",
                    "similarity_boost",
                    "style",
                    "speed",
                    "timestamps",
                    "previous_text",
                    "next_text",
                ]:
                    if planned_payload.get(key) is not None:
                        provider_options[key] = planned_payload.get(key)

                if planned_text:
                    provider_options["text"] = planned_text
                    logger.info(
                        "[GenerateVoice] planner text applied | user_id=%s raw_len=%s sanitized_len=%s preview=%s",
                        current_user.id,
                        len(raw_planned_text),
                        len(planned_text),
                        planned_text[:120],
                    )
            else:
                logger.warning(
                    "[GenerateVoice] dialogue extraction | user_id=%s prompt_chars=%s has_explicit_dialogue=%s dialogue_line_count=%s dialogue_chars=%s planned_text_chars=0 fallback_dialogue_used=%s",
                    current_user.id,
                    len(stable_prompt),
                    has_explicit_dialogue,
                    len(extracted_dialogue_lines),
                    len(extracted_dialogue),
                    False,
                )

            if not str(effective_prompt or "").strip():
                raise HTTPException(
                    status_code=400,
                    detail="No explicit dialogue extracted by LLM planner; voice generation cancelled in strict dialogue mode",
                )

        if explicit_language_code:
            provider_options["language_code"] = explicit_language_code

        if explicit_seed:
            provider_options["seed"] = int(explicit_seed)
            provider_options["seeds"] = int(explicit_seed)
        elif project_seed:
            provider_options["seed"] = int(project_seed)
            provider_options["seeds"] = int(project_seed)

        if explicit_project_language:
            logger.warning(
                "[GenerateVoice] project language hint | user_id=%s project_language=%s language_code=%s",
                current_user.id,
                explicit_project_language,
                provider_options.get("language_code"),
            )

        timestamps_supported = _read_api_capability_bool(
            pre_api_cfg,
            "supports_timestamps",
            "timestamps_supported",
        )
        previous_text_supported = _read_api_capability_bool(
            pre_api_cfg,
            "supports_previous_text",
            "previous_text_supported",
            "supports_context_text",
            "context_text_supported",
        )
        next_text_supported = _read_api_capability_bool(
            pre_api_cfg,
            "supports_next_text",
            "next_text_supported",
            "supports_context_text",
            "context_text_supported",
        )
        if timestamps_supported is False:
            provider_options.pop("timestamps", None)
        if previous_text_supported is False:
            provider_options.pop("previous_text", None)
        if next_text_supported is False:
            provider_options.pop("next_text", None)

        allowed_voice_values = _read_api_capability_list(
            pre_api_cfg,
            "voice_values",
            "voices",
            "allowed_voices",
            "supported_voices",
        )
        allowed_language_values = _read_api_capability_list(
            pre_api_cfg,
            "language_code_values",
            "language_values",
            "languages",
            "allowed_languages",
            "supported_languages",
        )
        mapped_voice = _map_text_value_to_allowed(provider_options.get("voice"), allowed_voice_values)
        if mapped_voice:
            provider_options["voice"] = mapped_voice
        mapped_language = _map_text_value_to_allowed(provider_options.get("language_code"), allowed_language_values)
        if mapped_language:
            provider_options["language_code"] = mapped_language

        voice_numeric_fields = {
            "stability": ("stability_min", "stability_max", 0.0, 1.0),
            "similarity_boost": ("similarity_boost_min", "similarity_boost_max", 0.0, 1.0),
            "style": ("style_min", "style_max", 0.0, 1.0),
            "speed": ("speed_min", "speed_max", 0.7, 1.2),
        }
        for field_name, (min_key, max_key, default_min, default_max) in voice_numeric_fields.items():
            if provider_options.get(field_name) is None:
                continue
            if is_suno_voice and field_name == "style":
                continue
            min_value = _read_api_capability_number(pre_api_cfg, min_key)
            max_value = _read_api_capability_number(pre_api_cfg, max_key)
            effective_min = default_min if min_value is None else float(min_value)
            effective_max = default_max if max_value is None else float(max_value)
            if effective_max < effective_min:
                effective_min, effective_max = effective_max, effective_min
            provider_options[field_name] = _clamp_float(
                provider_options.get(field_name),
                effective_min,
                effective_max,
                effective_min,
            )

        logger.warning(
            "[GenerateVoice] planned params | user_id=%s voice=%s language_code=%s stability=%s similarity_boost=%s style=%s speed=%s timestamps=%s seed=%s",
            current_user.id,
            provider_options.get("voice"),
            provider_options.get("language_code"),
            provider_options.get("stability"),
            provider_options.get("similarity_boost"),
            provider_options.get("style"),
            provider_options.get("speed"),
            provider_options.get("timestamps"),
            provider_options.get("seed") or provider_options.get("seeds"),
        )

        # Final strict gate before provider submission: never send non-dialogue text.
        if not is_suno_voice:
            final_dialogue_prompt = _extract_dialogue_text_for_tts(provider_options.get("text") or effective_prompt)
            if bool(req.use_llm_param_planning) and not str(final_dialogue_prompt or "").strip():
                raise HTTPException(
                    status_code=400,
                    detail="No valid dialogue remained after final sanitization; voice generation cancelled",
                )
            if str(final_dialogue_prompt or "").strip():
                effective_prompt = str(final_dialogue_prompt).strip()
                provider_options["text"] = effective_prompt
                provider_options["prompt"] = effective_prompt
                provider_options["__voice_submit_text"] = effective_prompt
                provider_options["__voice_strict_text_only"] = bool(req.use_llm_param_planning)

        logger.info(
            "[GenerateVoice] final submit text | user_id=%s prompt_len=%s text_len=%s preview=%s",
            current_user.id,
            len(str(effective_prompt or "")),
            len(str(provider_options.get("text") or "")),
            str(effective_prompt or "")[:120],
        )

        effective_negative_prompt, negative_prompt_source = _resolve_effective_negative_prompt(
            req.negative_prompt,
            req.asset_type,
            "voice",
        )

        _release_db_connection(db, "generate_voice_provider_call")

        result = await media_service.generate_voice(
            prompt=effective_prompt,
            negative_prompt=effective_negative_prompt,
            llm_config=runtime_llm_config,
            duration=5,
            provider_options=provider_options,
            user_id=current_user.id,
            user_credits=(current_user.credits or 0),
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

        if "error" in result:
            detail = _format_generation_failure_detail(result, "Voice generation failed")
            if reservation_tx:
                try:
                    billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), detail)
                    reservation_tx = None
                except Exception:
                    pass
            raise HTTPException(status_code=400, detail=detail)

        voice_url = str((result or {}).get("url") or "").strip()
        if not voice_url:
            if reservation_tx:
                try:
                    billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), "Voice generation returned empty URL")
                    reservation_tx = None
                except Exception:
                    pass
            raise HTTPException(status_code=400, detail="Voice generation returned empty URL")

        final_meta = result.get("metadata") if isinstance(result, dict) else {}
        final_meta = final_meta if isinstance(final_meta, dict) else {}
        smart_meta = final_meta.get("smart_routing") if isinstance(final_meta.get("smart_routing"), dict) else {}

        final_provider = str(
            final_meta.get("provider")
            or smart_meta.get("provider")
            or reserve_provider
            or req.provider
            or ""
        ).strip() or None
        final_model = str(
            final_meta.get("model")
            or smart_meta.get("model")
            or reserve_model
            or req.model
            or ""
        ).strip() or None
        final_system_api_id_raw = (
            final_meta.get("system_api_id")
            if final_meta.get("system_api_id") is not None
            else smart_meta.get("system_api_id")
        )
        try:
            final_system_api_id = int(final_system_api_id_raw) if final_system_api_id_raw is not None else None
        except Exception:
            final_system_api_id = None

        if reservation_tx:
            if is_token_billing:
                usage = _extract_provider_usage_from_metadata(final_meta)
                api_tokens = _resolve_usage_token_total(usage)
                settle_details = {
                    "input_tokens": int((usage or {}).get("input_tokens") or (usage or {}).get("prompt_tokens") or 0),
                    "output_tokens": int((usage or {}).get("output_tokens") or (usage or {}).get("completion_tokens") or api_tokens or 0),
                    "total_tokens": api_tokens,
                    "status": "SETTLED",
                    "billing_mode": "ACTUAL",
                    "token_source": "api_usage" if api_tokens > 0 else "estimate",
                }
            else:
                settle_details = {
                    "duration": 5,
                    "duration_seconds": 5,
                    "status": "SETTLED",
                    "billing_mode": "ACTUAL",
                }

            provider_usage = _extract_provider_usage_from_metadata(final_meta)
            if provider_usage:
                settle_details["provider_usage"] = provider_usage
                settle_details["usage_source"] = str(final_meta.get("usage_source") or "provider").strip() or "provider"

            if final_provider:
                settle_details["provider"] = final_provider
            if final_model:
                settle_details["model"] = final_model
            if final_system_api_id is not None:
                settle_details["system_api_id"] = final_system_api_id
            if voice_project_id:
                settle_details["project_id"] = voice_project_id
            if voice_episode_id:
                settle_details["episode_id"] = voice_episode_id

            settle_details = _merge_provider_task_ids_into_settle(
                settle_details,
                final_meta if isinstance(final_meta, dict) else {},
                smart_meta if isinstance(smart_meta, dict) else {},
            )

            billing_service.settle_reservation(
                db,
                _reservation_tx_id(reservation_tx),
                settle_details,
            )
            reservation_tx = None

        if req.shot_id:
            shot = db.query(Shot).filter(Shot.id == int(req.shot_id)).first()
            if shot:
                tech = {}
                try:
                    tech = json.loads(shot.technical_notes or "{}")
                    if not isinstance(tech, dict):
                        tech = {}
                except Exception:
                    tech = {}
                tech["voiceover_url"] = voice_url
                tech["voiceover_prompt"] = effective_prompt
                if bool(req.use_llm_param_planning):
                    tech["voiceover_plan"] = planned_payload
                    tech["voiceover_plan_prompts"] = {
                        "system_prompt": planner_system_prompt,
                        "user_prompt": planner_user_prompt,
                        "template_source": (planner_prompt_meta or {}).get("template_source"),
                    }
                shot.technical_notes = json.dumps(tech, ensure_ascii=False)
                db.add(shot)
                db.commit()

        # Register voice asset so frontend can resolve metadata panels by URL.
        if voice_url:
            if voice_url.startswith("http"):
                async def _bg_upload_and_update_voice(user: User, req_obj: Any, raw_url: str, prompt_text: str, meta: Optional[dict] = None):
                    bg_db = SessionLocal()
                    try:
                        bg_user = bg_db.query(User).filter(User.id == user.id).first()
                        if not bg_user: return
                        norm_url, norm_meta, oss_uploaded = await asyncio.to_thread(
                            _persist_remote_media_result,
                            bg_user,
                            raw_url,
                            meta,
                            filename_base=_build_generation_filename_base(req_obj, bg_db),
                        )
                        final_url = str(norm_url or raw_url).strip()
                        final_meta = dict(norm_meta if norm_meta is not None else (meta or {}))
                        if not str(final_meta.get("idempotency_key") or "").strip() and req_obj.shot_id:
                            final_meta["idempotency_key"] = f"voice-shot-{int(req_obj.shot_id)}"

                        bind_url, ephemeral_binding, final_meta = _resolve_media_bind_url(
                            raw_url=raw_url,
                            normalized_url=final_url,
                            normalized_meta=final_meta,
                        )
                        if bind_url and req_obj.shot_id:
                            bg_shot = bg_db.query(Shot).filter(Shot.id == int(req_obj.shot_id)).first()
                            if bg_shot:
                                bg_tech = {}
                                try:
                                    bg_tech = json.loads(bg_shot.technical_notes or "{}")
                                except Exception:
                                    bg_tech = {}
                                current_voice = str(bg_tech.get("voiceover_url") or "").strip()
                                if current_voice in {raw_url, bind_url}:
                                    bg_tech["voiceover_url"] = bind_url
                                    if ephemeral_binding:
                                        bg_tech["voiceover_ephemeral_binding"] = True
                                    elif oss_uploaded:
                                        bg_tech["voiceover_oss_uploaded"] = True
                                    bg_shot.technical_notes = json.dumps(bg_tech, ensure_ascii=False)
                                    bg_db.add(bg_shot)
                                    bg_db.commit()

                        if bind_url:
                            await asyncio.to_thread(_register_asset_helper, bg_db, bg_user.id, bind_url, req_obj, final_meta)
                    except Exception as e:
                        logger.error(f"[_bg_upload_and_update_voice] failed for user={user.id} url={raw_url}: {e}")
                    finally:
                        bg_db.close()
                asyncio.create_task(_bg_upload_and_update_voice(current_user, req, voice_url, effective_prompt, result.get("metadata")))
            else:
                try:
                    await asyncio.to_thread(
                        _register_asset_helper,
                        db,
                        current_user.id,
                        voice_url,
                        req,
                        (result.get("metadata") if isinstance(result, dict) else None),
                    )
                except Exception as asset_err:
                    logger.warning("[GenerateVoice] asset registration failed: %s", asset_err)

        if isinstance(result, dict):
            result["effective_prompt"] = effective_prompt
            if bool(req.use_llm_param_planning):
                result["voiceover_plan"] = planned_payload if isinstance(planned_payload, dict) else {}
                result["voiceover_plan_prompts"] = {
                    "system_prompt": planner_system_prompt,
                    "user_prompt": planner_user_prompt,
                    "template_source": (planner_prompt_meta or {}).get("template_source"),
                }

        return result
    except HTTPException:
        if reservation_tx:
            try:
                billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), "voice generation http exception")
            except Exception:
                pass
        raise
    except Exception as e:
        if reservation_tx:
            try:
                billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), str(e))
            except Exception:
                pass
        try:
            billing_service.log_failed_transaction(db, current_user.id, voice_task_type, req.provider, req.model, str(e))
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


async def _run_generate_video(
    req: VideoGenerationRequest,
    current_user: User,
    db: Session,
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
        supports_last_frame_mode = _video_api_supports_last_frame_mode(resolved_video_provider, resolved_video_model)
        req.ref_image_url, req.last_frame_url, ref_normalization_info = _normalize_video_request_refs(
            req.ref_image_url,
            req.last_frame_url,
            normalized_ref_mode,
            supports_last_frame_mode=supports_last_frame_mode,
        )
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
        submit_image_urls = _resolve_video_submit_image_urls(req)
        uses_submit_image_urls = bool(submit_image_urls)
        if uses_submit_image_urls:
            if image_ref_limit is not None:
                submit_image_urls = _limit_string_list_input(submit_image_urls, image_ref_limit)
            req.image_urls = submit_image_urls
            req.ref_image_url = None
        elif image_ref_limit is not None:
            req.ref_image_url = _limit_media_ref_input(req.ref_image_url, image_ref_limit)
        if isinstance(req.ref_video_urls, list) and video_ref_limit is not None:
            req.ref_video_urls = _limit_media_ref_input(req.ref_video_urls, video_ref_limit)
        if explicit_first_frame_flag is False:
            req.ref_image_url = [] if isinstance(req.ref_image_url, list) else None
        if explicit_last_frame_flag is False:
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
        is_reference_image_mode = bool(normalized_ref_mode in {"entity_refs", "keyframes_entity_refs"})
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

        auto_entity_refs: List[str] = []
        if is_reference_image_mode and resolved_project_id and not uses_submit_image_urls:
            entity_lookup = _build_project_entity_lookup(
                db, int(resolved_project_id), episode_id=resolved_episode_id
            )
            prompt_candidates: List[str] = [prompt_text]
            shot_for_ref: Optional[Shot] = None
            shot_tech: Dict[str, Any] = {}

            if req.shot_id:
                shot_for_ref = db.query(Shot).filter(Shot.id == int(req.shot_id)).first()
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

            existing_start_refs: List[str] = []
            if isinstance(req.ref_image_url, list):
                existing_start_refs = [str(x).strip() for x in req.ref_image_url if str(x).strip()]
            elif isinstance(req.ref_image_url, str) and req.ref_image_url.strip():
                existing_start_refs = [req.ref_image_url.strip()]

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

        flat_refs: List[str] = []
        if uses_submit_image_urls:
            flat_refs.extend(submit_image_urls)
        elif isinstance(req.ref_image_url, list):
            flat_refs.extend([str(x).strip() for x in req.ref_image_url if str(x).strip()])
        elif isinstance(req.ref_image_url, str) and req.ref_image_url.strip():
            flat_refs.append(req.ref_image_url.strip())

        if isinstance(effective_keyframes, list):
            flat_refs.extend([str(x).strip() for x in effective_keyframes if str(x).strip()])

        if isinstance(req.last_frame_url, str) and req.last_frame_url.strip():
            flat_refs.append(req.last_frame_url.strip())

        flat_refs = [x for x in dict.fromkeys([str(x).strip() for x in flat_refs if str(x).strip()]) if x]
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

        # Only inject the mapping prompt for entity_refs mode
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
        synced_image_urls, synced_ref_image_url = _sync_request_image_refs_with_aligned(
            aligned_refs=flat_refs,
            image_urls=req.image_urls if uses_submit_image_urls else None,
            ref_image_url=None if uses_submit_image_urls else req.ref_image_url,
            last_frame_url=req.last_frame_url,
            keyframes=effective_keyframes,
        )
        if uses_submit_image_urls and isinstance(synced_image_urls, list) and synced_image_urls:
            req.image_urls = synced_image_urls
        elif synced_ref_image_url is not None:
            req.ref_image_url = synced_ref_image_url
            if not uses_submit_image_urls:
                req.image_urls = None
        elif is_reference_image_mode and flat_refs:
            # Trim explicit empty image_urls after entity-only reconcile.
            req.image_urls = flat_refs
            req.ref_image_url = flat_refs if len(flat_refs) != 1 else flat_refs[0]
        if isinstance(req.multi_prompt, list):
            patched_multi_prompt: List[Dict[str, Any]] = []
            for item in req.multi_prompt:
                if not isinstance(item, dict):
                    continue
                patched_item = dict(item)
                item_prompt = str(patched_item.get("prompt") or "").strip()
                if item_prompt:
                    patched_item["prompt"], _ = _append_video_api_ref_mapping(
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
        if (force_pure_callback_mode or _is_pure_callback_mode_enabled()) and provider_callback_ticket and provider_callback_url:
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
        if video_ref_limit is not None:
            ref_video_urls = video_provider_options.get("reference_video_urls")
            if isinstance(ref_video_urls, list):
                video_provider_options["reference_video_urls"] = _limit_string_list_input(ref_video_urls, video_ref_limit)
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
        if result.get("url"):
            temp_url = str(result.get("url") or "").strip()
            if temp_url:
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


def _set_video_job(job_id: str, **fields) -> None:
    with VIDEO_JOB_LOCK:
        _prune_video_jobs_locked()
        current = VIDEO_JOB_STORE.get(job_id, {})
        previous_status = str(current.get("status") or "").strip().lower()
        previous_result_url = _extract_job_result_url(current.get("result"))
        if "result" in fields:
            fields["result"] = _compact_job_result(fields.get("result"))
        current.update(fields)
        current["job_id"] = job_id
        VIDEO_JOB_STORE[job_id] = current

        status = str(current.get("status") or "").strip().lower()
        result_url = _extract_job_result_url(current.get("result"))
        if status != previous_status or (result_url and result_url != previous_result_url):
            logger.info(
                "[VideoJob] state updated | job_id=%s prev_status=%s status=%s has_result_url=%s result_url=%s error=%s",
                job_id,
                previous_status or None,
                status or None,
                bool(result_url),
                result_url or None,
                current.get("error"),
            )
        if status in {"succeeded", "failed", "canceled", "cancelled", "error"}:
            task_scope = str(current.get("task_scope") or "").strip()
            if task_scope and VIDEO_ACTIVE_SCOPE_STORE.get(task_scope) == job_id:
                VIDEO_ACTIVE_SCOPE_STORE.pop(task_scope, None)

        _write_video_job_file(job_id, current)

    _clear_generation_job_pool_cache()


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
            "[VideoJob] final provider payload recorded | job_id=%s provider=%s model=%s",
            job_id,
            req_provider or "unknown",
            req_model or "unknown",
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

            update_fields: Dict[str, Any] = {
                "status": "waiting_callback",
                "error": None,
                "upstream_submit_state": "callback_pending",
                "billing_pending": bool(result.get("billing_pending") and reservation_tx_id_pending),
                "billing_context": billing_context,
            }
            # Do not clobber billing_settled=True from another worker.
            if not already_settled:
                update_fields["billing_settled"] = False
            if reservation_tx_id_pending:
                update_fields["reservation_tx_id"] = int(reservation_tx_id_pending)
            if provider_task_id:
                update_fields["provider_task_id"] = provider_task_id
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
        _set_video_job(
            job_id,
            status="succeeded",
            finished_at=now_bj_iso(),
            result=result,
            error=None,
        )
        mark_generation_task_status_external(job_id, status="completed", error=None)
        return {"defer_completion": False}
    except asyncio.TimeoutError:
        with VIDEO_JOB_LOCK:
            current_job = dict(VIDEO_JOB_STORE.get(job_id) or {})
        current_status = _normalize_generation_status(current_job.get("status"))
        current_result_url = _extract_job_result_url(current_job.get("result"))
        if current_status == "succeeded" and current_result_url:
            logger.info(
                "[VideoJob] timeout ignored after callback finalization | job_id=%s provider_task_id=%s result_url=%s",
                job_id,
                _extract_job_provider_task_id(current_job) or None,
                current_result_url,
            )
            return
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
        if current_status == "succeeded" and current_result_url:
            logger.info(
                "[VideoJob] cancellation ignored after callback finalization | job_id=%s provider_task_id=%s result_url=%s",
                job_id,
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
        if current_status == "succeeded" and current_result_url:
            logger.info(
                "[VideoJob] http error ignored after callback finalization | job_id=%s detail=%s provider_task_id=%s",
                job_id,
                str(e.detail),
                _extract_job_provider_task_id(current_job) or None,
            )
            return
        if _is_ambiguous_image_submit_detail(e.detail):
            _set_video_job(
                job_id,
                status="waiting_callback",
                error=None,
                ambiguous_submit=True,
                ambiguous_submit_at=now_bj_iso(),
                upstream_submit_state="unknown",
            )
            logger.warning(
                "[VideoJob] ambiguous submit retained as running | job_id=%s callback_ticket=%s detail=%s",
                job_id,
                provider_callback_ticket or None,
                str(e.detail),
            )
            mark_generation_task_status_external(job_id, status="waiting_callback", error=None)
            return {"defer_completion": True}
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
        if current_status == "succeeded" and current_result_url:
            logger.info(
                "[VideoJob] exception ignored after callback finalization | job_id=%s error=%s provider_task_id=%s",
                job_id,
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
        await _dispatch_generation_callback("video", callback_url, snapshot)

        with VIDEO_JOB_LOCK:
            VIDEO_JOB_TASKS.pop(job_id, None)
        _release_db_connection(db, "run_video_job")
        _clear_generation_job_pool_cache()


@router.post("/generate/callback/{ticket}")
async def receive_generation_callback(ticket: str, request: Request, response: Response):
    stable_ticket = str(ticket or "").strip()
    if not stable_ticket:
        raise HTTPException(status_code=400, detail="Invalid callback ticket")
    _apply_no_store_headers(response)

    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            payload = {"raw": payload}
    except Exception:
        body_bytes = await request.body()
        payload = {
            "raw": body_bytes.decode("utf-8", errors="ignore") if body_bytes else "",
            "content_type": str(request.headers.get("content-type") or "").strip(),
        }

    import json
    try:
        def _log_chunked_message(prefix: str, text: str, chunk_size: int = 4000) -> None:
            stable_text = str(text or "")
            if not stable_text:
                logger.info("%s <empty>", prefix)
                return
            safe_chunk_size = max(512, int(chunk_size or 4000))
            total_len = len(stable_text)
            total_parts = (total_len + safe_chunk_size - 1) // safe_chunk_size
            for idx in range(total_parts):
                start = idx * safe_chunk_size
                end = min(total_len, (idx + 1) * safe_chunk_size)
                logger.info(
                    "%s part=%s/%s chars=%s-%s %s",
                    prefix,
                    idx + 1,
                    total_parts,
                    start + 1,
                    end,
                    stable_text[start:end],
                )

        dump_str = json.dumps(payload, ensure_ascii=False)
        client_host = getattr(getattr(request, "client", None), "host", "Unknown")
        callback_headers = {
            key: value
            for key, value in request.headers.items()
            if str(key or "").lower() in {
                "content-type",
                "content-length",
                "x-kie-signature",
                "x-kie-timestamp",
                "x-signature",
                "x-timestamp",
                "x-forwarded-for",
                "user-agent",
            }
        }
        body_bytes = await request.body()

        logger.info("=" * 60)
        logger.info("🔔 [WEBHOOK CALLBACK RECEIVED] [%s] Ticket: %s", client_host, stable_ticket)
        logger.info(
            "🔔 [WEBHOOK META] content_type=%s content_length=%s body_bytes=%s top_keys=%s",
            str(request.headers.get("content-type") or "").strip() or None,
            str(request.headers.get("content-length") or "").strip() or None,
            len(body_bytes or b""),
            list(payload.keys()) if isinstance(payload, dict) else None,
        )
        logger.info("🔔 [WEBHOOK HEADERS] %s", json.dumps(callback_headers, ensure_ascii=False))
        _log_chunked_message("🔔 [WEBHOOK PAYLOAD FULL]", dump_str)
        logger.info("=" * 60)
    except Exception as e:
        logger.error(f"Failed to log webhook payload: {e}")

    try:
        _verify_kie_webhook_request(request, payload if isinstance(payload, dict) else {})
        logger.info("[WebhookVerify] accepted | ticket=%s", stable_ticket)
    except HTTPException as verify_exc:
        logger.warning(
            "[WebhookVerify] rejected | ticket=%s detail=%s has_timestamp=%s has_signature=%s",
            stable_ticket,
            getattr(verify_exc, "detail", None),
            bool(
                str(request.headers.get("x-webhook-timestamp") or "").strip()
                or str(request.headers.get("x-kie-timestamp") or "").strip()
                or str(request.headers.get("x-timestamp") or "").strip()
            ),
            bool(
                str(request.headers.get("x-webhook-signature") or "").strip()
                or str(request.headers.get("x-kie-signature") or "").strip()
                or str(request.headers.get("x-signature") or "").strip()
            ),
        )
        raise

    await asyncio.to_thread(_set_generation_callback_payload, stable_ticket, payload)
    normalized_payload = _get_generation_callback_payload(stable_ticket)
    payload_status = _normalize_generation_status(normalized_payload.get("status"))
    payload_result_url = _extract_job_result_url(normalized_payload)
    callback_task_id = _extract_callback_task_id(normalized_payload)
    logger.info(
        "[GenerationCallback] received ticket=%s task_id=%s status=%s has_result_url=%s result_url=%s remote=%s",
        stable_ticket,
        callback_task_id or None,
        payload_status or None,
        bool(payload_result_url),
        payload_result_url or None,
        getattr(getattr(request, "client", None), "host", None),
    )
    if _mark_generation_callback_inflight(stable_ticket):
        asyncio.create_task(_process_generation_callback_async(stable_ticket, payload if isinstance(payload, dict) else {}))
    else:
        logger.info("[GenerationCallback] duplicate callback acknowledged while finalize in-flight | ticket=%s", stable_ticket)
    return {"ok": True, "ticket": stable_ticket, "accepted": True}


@router.get("/generate/callback/{ticket}")
def get_generation_callback_result(ticket: str, response: Response):
    stable_ticket = str(ticket or "").strip()
    if not stable_ticket:
        raise HTTPException(status_code=400, detail="Invalid callback ticket")
    _apply_no_store_headers(response)

    with GENERATION_CALLBACK_LOCK:
        _prune_generation_callback_locked()
        payload = dict(GENERATION_CALLBACK_STORE.get(stable_ticket) or {})

    if not payload:
        file_payload = _read_generation_callback_file(stable_ticket)
        if file_payload:
            payload = dict(file_payload)
            with GENERATION_CALLBACK_LOCK:
                _prune_generation_callback_locked()
                GENERATION_CALLBACK_STORE[stable_ticket] = dict(file_payload)

    if not payload:
        return {
            "ticket": stable_ticket,
            "status": "pending",
            "received": False,
            "received_at": None,
            "payload": None,
        }

    return {
        "ticket": stable_ticket,
        "status": "received",
        "received": True,
        "received_at": payload.get("received_at"),
        "payload": payload.get("payload") if isinstance(payload.get("payload"), dict) else {},
    }


@router.post("/generate/video/submit")
async def submit_generate_video_endpoint(
    req: VideoGenerationRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    callback_url = _resolve_callback_url_from_payload(req)
    explicit_idempotency_key = str(request.headers.get("X-Idempotency-Key") or "").strip()
    req_payload = req.model_dump()

    # Keep queue payload prompt/refs aligned with runtime mapping logic.
    try:
        req_payload = _preprocess_video_submit_payload(
            db,
            req_payload,
            provider=str(req_payload.get("provider") or "").strip(),
            model=str(req_payload.get("model") or "").strip(),
        )
    except Exception as e:
        logger.warning("[VideoSubmit] prompt mapping pre-process skipped: %s", e)
    scope_key = _build_generation_task_scope("video", current_user.id, req_payload)
    fingerprint_token = _build_submit_idempotency_token("video", current_user.id, req_payload)
    idempotency_key = explicit_idempotency_key or fingerprint_token
    job_id = ""
    now = now_bj_iso()
    provider_callback_ticket = ""
    provider_callback_url = ""

    store_keys: List[str] = []
    if idempotency_key:
        store_keys.append(_build_video_idempotency_store_key(current_user.id, idempotency_key))
    store_keys.append(_build_video_idempotency_store_key(current_user.id, fingerprint_token))
    store_keys = list(dict.fromkeys([k for k in store_keys if str(k or "").strip()]))

    def _video_dedup_response_locked() -> Optional[Dict[str, Any]]:
        active_scope_job_id = str(VIDEO_ACTIVE_SCOPE_STORE.get(scope_key) or "").strip()
        if active_scope_job_id:
            active_scope_job = dict(VIDEO_JOB_STORE.get(active_scope_job_id) or {})
            active_status = str(active_scope_job.get("status") or "").strip().lower()
            if active_scope_job and active_status in {"queued", "running"}:
                logger.info(
                    "[VideoSubmit] scope deduplicated | user_id=%s scope=%s job_id=%s status=%s",
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
            VIDEO_ACTIVE_SCOPE_STORE.pop(scope_key, None)

        for store_key in store_keys:
            mapped = VIDEO_SUBMIT_IDEMPOTENCY_STORE.get(store_key) or {}
            existing_job_id = str(mapped.get("job_id") or "").strip()
            if not existing_job_id:
                continue
            existing_job = dict(VIDEO_JOB_STORE.get(existing_job_id) or {})
            existing_status = str(existing_job.get("status") or "").strip().lower()
            if existing_job and existing_status in {"queued", "running"}:
                logger.info(
                    "[VideoSubmit] deduplicated | user_id=%s key=%s job_id=%s status=%s",
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

    with VIDEO_JOB_LOCK:
        _prune_video_jobs_locked()
        deduped = _video_dedup_response_locked()
        if deduped is not None:
            return deduped

    parallel_limit = _enforce_user_media_generation_parallel_limit(current_user)

    with VIDEO_JOB_LOCK:
        deduped = _video_dedup_response_locked()
        if deduped is not None:
            return deduped
        job_id = uuid.uuid4().hex
        for store_key in store_keys:
            VIDEO_SUBMIT_IDEMPOTENCY_STORE[store_key] = {
                "job_id": job_id,
                "created_at": now,
            }
        VIDEO_ACTIVE_SCOPE_STORE[scope_key] = job_id

    if not job_id:
        job_id = uuid.uuid4().hex

    provider_callback_ticket = f"video-job-{job_id}"
    try:
        provider_callback_url = str(media_service._resolve_provider_callback_url({}, provider_callback_ticket) or "").strip()
    except Exception:
        provider_callback_url = ""

    _set_video_job(
        job_id,
        status="queued",
        user_id=current_user.id,
        username=current_user.username,
        callback_url=callback_url,
        task_scope=scope_key,
        project_id=req_payload.get("project_id"),
        episode_id=req_payload.get("episode_id"),
        scene_id=req_payload.get("scene_id"),
        shot_id=req_payload.get("shot_id"),
        shot_number=req_payload.get("shot_number"),
        shot_name=req_payload.get("shot_name"),
        asset_type=req_payload.get("asset_type"),
        provider=req_payload.get("provider"),
        model=req_payload.get("model"),
        prompt=req_payload.get("prompt"),
        duration=req_payload.get("duration"),
        aspect_ratio=req_payload.get("aspect_ratio"),
        provider_callback_ticket=provider_callback_ticket,
        created_at=now,
        started_at=None,
        finished_at=None,
        result=None,
        error=None,
    )

    video_task = _submit_generation_background_task(
        job_id=job_id,
        kind="video",
        user_id=int(current_user.id),
        payload=req_payload,
    )
    with VIDEO_JOB_LOCK:
        VIDEO_JOB_TASKS[job_id] = video_task
    _release_media_generation_job_after_limit_race(
        kind="video",
        job_id=job_id,
        user=current_user,
        limit=parallel_limit,
    )
    return {"job_id": job_id, "status": "queued", "created_at": now}


@router.get("/generate/video/jobs/{job_id}")
def get_generate_video_job_status(
    job_id: str,
    response: Response,
    current_claims: Dict[str, Any] = Depends(get_current_claims),
):
    _apply_no_store_headers(response)
    with VIDEO_JOB_LOCK:
        job = dict(VIDEO_JOB_STORE.get(job_id) or {})

    status = str(job.get("status") or "").strip().lower()
    if not job or status in {"queued", "running"}:
        file_job = _read_video_job_file(job_id)
        if file_job:
            file_status = str(file_job.get("status") or "").strip().lower()
            if not job or file_status != status or ("result" in file_job and "result" not in job):
                with VIDEO_JOB_LOCK:
                    _prune_video_jobs_locked()
                    VIDEO_JOB_STORE[job_id] = dict(file_job)
                job = dict(file_job)
                logger.info(
                    "[VideoJob] synced from shared file store | job_id=%s status=%s user_id=%s",
                    job_id,
                    job.get("status"),
                    job.get("user_id"),
                )

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job = _hydrate_video_job_record(job_id, job)

    if "result" in job:
        compact_result = _compact_job_result(job.get("result"))
        if compact_result != job.get("result"):
            _set_video_job(job_id, result=compact_result)
            job["result"] = compact_result

    job = _maybe_finalize_video_job_from_provider_callback(job_id, job)
    job = _maybe_retry_video_job_result_persistence(job_id, job)
    owner_id = job.get("user_id")
    owner_username = str(job.get("username") or "").strip()
    owner_username_norm = owner_username.lower()

    job = _maybe_finalize_stuck_job(
        kind="video",
        job_id=job_id,
        job=job,
        set_job_func=_set_video_job,
        task_store=VIDEO_JOB_TASKS,
        lock=VIDEO_JOB_LOCK,
        timeout_seconds=VIDEO_JOB_MAX_RUNNING_SECONDS,
    )
    video_status = str(job.get("status") or "").strip().lower()

    current_user_id = current_claims.get("user_id")
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
    if result_url and video_status in {"queued", "running"}:
        logger.warning(
            "[VideoJob] polling anomaly | job_id=%s status=%s result_url=%s user_id=%s",
            job_id,
            video_status,
            result_url,
            owner_id,
        )

    return {
        "job_id": job.get("job_id"),
        "status": job.get("status"),
        "created_at": job.get("created_at"),
        "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"),
        "error": job.get("error"),
        "result": job.get("result"),
    }


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is not None:
            return dt.astimezone(tz=None).replace(tzinfo=None)
        return dt
    except Exception:
        return None


def _normalize_batch_job_status(payload: Dict[str, Any]) -> str:
    if bool(payload.get("force_stopped")):
        return "canceled"
    if bool(payload.get("stopped_by_user")) or bool(payload.get("stop_requested")):
        return "canceled"

    status_raw = str(payload.get("status") or "").strip().lower()
    if status_raw in {"running", "queued", "completed", "failed", "stopped", "canceled", "cancelled", "error", "idle", "partial"}:
        return status_raw

    if bool(payload.get("running")):
        return "running"

    failed = _safe_int(payload.get("failed"), 0)
    success = _safe_int(payload.get("success"), 0)
    generated = _safe_int(payload.get("generated"), 0)
    completed = _safe_int(payload.get("completed"), 0)
    total = _safe_int(payload.get("total") or payload.get("episodes_in_run"), 0)

    if failed > 0 and (success > 0 or generated > 0):
        return "partial"
    if failed > 0:
        return "failed"

    if bool(payload.get("generation_success")):
        return "completed"

    if total > 0 and completed >= total:
        return "completed"
    if completed > 0 and total == 0 and failed == 0:
        return "completed"

    return "idle"


def _extract_target_id_from_job_id(job_id: str) -> Optional[int]:
    stable = str(job_id or "").strip()
    if not stable:
        return None
    m = re.search(r"(\d+)$", stable)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def _build_batch_job_item(
    *,
    kind: str,
    job_id: str,
    payload: Dict[str, Any],
    user_id: Optional[int],
    username: Optional[str],
) -> Dict[str, Any]:
    status = _normalize_batch_job_status(payload)
    started_at = payload.get("started_at") or payload.get("created_at")
    finished_at = payload.get("finished_at")
    updated_at = payload.get("updated_at")
    created_at = started_at or updated_at or now_bj_iso()

    error_text = ""
    errors = payload.get("errors")
    if isinstance(errors, list) and errors:
        error_text = str(errors[-1])
    if not error_text:
        error_text = str(payload.get("error") or "").strip()
    if not error_text and status == "partial":
        error_text = "Partially failed"

    return {
        "kind": kind,
        "job_id": job_id,
        "status": status,
        "user_id": user_id,
        "username": username,
        "created_at": created_at,
        "started_at": started_at,
        "finished_at": finished_at,
        "error": error_text,
        "has_task": bool(payload.get("running")),
    }


@router.get("/generate/jobs/pool")
def get_generation_job_pool(
    kind: str = "all",
    running_only: bool = False,
    limit: int = 200,
    shot_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    safe_kind = str(kind or "all").strip().lower()
    allowed_kinds = {
        "all",
        "image",
        "video",
        "episode-scenes",
        "episode-scripts",
        "scene-ai-shots-batch",
        "shot-media-batch",
    }
    if safe_kind not in allowed_kinds:
        raise HTTPException(status_code=400, detail="kind must be one of: all, image, video, episode-scenes, episode-scripts, scene-ai-shots-batch, shot-media-batch")

    safe_limit = max(1, min(int(limit or 200), 500))

    t0 = time.perf_counter()
    t_cache_ms = 0
    t_collect_mem_ms = 0
    t_query_projects_ms = 0
    t_query_owners_ms = 0
    t_query_episodes_ms = 0
    t_filter_sort_ms = 0
    safe_shot_id = str(shot_id or "").strip() if shot_id else None

    cache_key = _build_generation_job_pool_cache_key(
        user_id=int(getattr(current_user, "id", 0) or 0),
        is_superuser=bool(getattr(current_user, "is_superuser", False)),
        kind=f"{safe_kind}_shot_{safe_shot_id}" if safe_shot_id else safe_kind,
        running_only=bool(running_only),
        limit=safe_limit,
    )

    t_cache_start = time.perf_counter()
    cached_payload = _read_generation_job_pool_cache(cache_key)
    t_cache_ms = int((time.perf_counter() - t_cache_start) * 1000)
    if cached_payload is not None:
        logger.debug(
            "jobs.pool.timing user_id=%s kind=%s running_only=%s limit=%s cache_hit=1 total_ms=%s cache_ms=%s mem_ms=%s proj_ms=%s owner_ms=%s ep_ms=%s finalize_ms=%s total=%s",
            getattr(current_user, "id", None),
            safe_kind,
            bool(running_only),
            safe_limit,
            int((time.perf_counter() - t0) * 1000),
            t_cache_ms,
            0,
            0,
            0,
            0,
            0,
            int((cached_payload or {}).get("total") or 0),
        )
        return cached_payload

    items: List[Dict[str, Any]] = []
    final_statuses = {"succeeded", "completed", "failed", "canceled", "cancelled", "error", "stopped", "idle", "partial"}
    now_dt = datetime.utcnow()

    stale_image_job_ids: List[str] = []
    stale_video_job_ids: List[str] = []
    stale_episode_script_project_ids: List[int] = []
    stale_episode_status_updates: Dict[int, Dict[str, Any]] = {}

    t_collect_mem_start = time.perf_counter()
    if safe_kind in {"all", "image"}:
        with IMAGE_JOB_LOCK:
            _prune_image_jobs_locked()
            for job_id, payload in list(IMAGE_JOB_STORE.items()):
                if _is_generation_job_stale(dict(payload or {}), now_dt=now_dt):
                    stale_image_job_ids.append(str(job_id))
                    continue
                item = dict(payload or {})
                item["job_id"] = item.get("job_id") or job_id
                item["kind"] = "image"
                item["has_task"] = _generation_task_is_active(IMAGE_JOB_TASKS.get(job_id) or str(job_id), user_id=item.get("user_id"))
                items.append(item)

            for stale_id in stale_image_job_ids:
                IMAGE_JOB_STORE.pop(stale_id, None)
                IMAGE_JOB_TASKS.pop(stale_id, None)

            if stale_image_job_ids:
                stale_set = set(stale_image_job_ids)
                stale_scope_keys = [k for k, v in IMAGE_ACTIVE_SCOPE_STORE.items() if str(v or "") in stale_set]
                for k in stale_scope_keys:
                    IMAGE_ACTIVE_SCOPE_STORE.pop(k, None)
                stale_idempotency_keys = [k for k, v in IMAGE_SUBMIT_IDEMPOTENCY_STORE.items() if str((v or {}).get("job_id") or "") in stale_set]
                for k in stale_idempotency_keys:
                    IMAGE_SUBMIT_IDEMPOTENCY_STORE.pop(k, None)

    if stale_image_job_ids:
        for stale_id in stale_image_job_ids:
            try:
                stale_path = _image_job_file_path(stale_id)
                if os.path.exists(stale_path):
                    os.remove(stale_path)
            except Exception:
                pass

    if safe_kind in {"all", "video"}:
        with VIDEO_JOB_LOCK:
            _prune_video_jobs_locked()
            for job_id, payload in list(VIDEO_JOB_STORE.items()):
                if _is_generation_job_stale(dict(payload or {}), now_dt=now_dt):
                    stale_video_job_ids.append(str(job_id))
                    continue
                item = dict(payload or {})
                item["job_id"] = item.get("job_id") or job_id
                item["kind"] = "video"
                item["has_task"] = _generation_task_is_active(VIDEO_JOB_TASKS.get(job_id) or str(job_id), user_id=item.get("user_id"))
                items.append(item)

            for stale_id in stale_video_job_ids:
                VIDEO_JOB_STORE.pop(stale_id, None)
                VIDEO_JOB_TASKS.pop(stale_id, None)

            if stale_video_job_ids:
                stale_set = set(stale_video_job_ids)
                stale_scope_keys = [k for k, v in VIDEO_ACTIVE_SCOPE_STORE.items() if str(v or "") in stale_set]
                for k in stale_scope_keys:
                    VIDEO_ACTIVE_SCOPE_STORE.pop(k, None)
                stale_idempotency_keys = [k for k, v in VIDEO_SUBMIT_IDEMPOTENCY_STORE.items() if str((v or {}).get("job_id") or "") in stale_set]
                for k in stale_idempotency_keys:
                    VIDEO_SUBMIT_IDEMPOTENCY_STORE.pop(k, None)

    if stale_video_job_ids:
        for stale_id in stale_video_job_ids:
            try:
                stale_path = _video_job_file_path(stale_id)
                if os.path.exists(stale_path):
                    os.remove(stale_path)
            except Exception:
                pass
    t_collect_mem_ms = int((time.perf_counter() - t_collect_mem_start) * 1000)

    include_batch_kinds = {"episode-scenes", "episode-scripts", "scene-ai-shots-batch", "shot-media-batch"}
    if safe_kind in {"all", *include_batch_kinds}:
        project_rows: List[Tuple[Any, Any, Any]] = []
        t_query_projects_start = time.perf_counter()
        if current_user.is_superuser:
            project_rows = db.query(Project.id, Project.owner_id, Project.global_info).filter(_active_project_clause()).all()
        else:
            accessible_project_ids = _resolve_accessible_project_ids_for_user(db, current_user)
            if not accessible_project_ids:
                project_rows = []
            else:
                project_rows = (
                    db.query(Project.id, Project.owner_id, Project.global_info)
                    .filter(
                        Project.id.in_(accessible_project_ids),
                        _active_project_clause(),
                    )
                    .all()
                )
        t_query_projects_ms = int((time.perf_counter() - t_query_projects_start) * 1000)

        owner_ids = sorted({int(owner_id) for _, owner_id, _ in project_rows if owner_id is not None})
        owners_by_id: Dict[int, str] = {}
        if current_user.is_superuser and owner_ids:
            t_query_owners_start = time.perf_counter()
            owner_rows = db.query(User.id, User.username).filter(User.id.in_(owner_ids)).all()
            owners_by_id = {int(row_id): str(username or "") for row_id, username in owner_rows}
            t_query_owners_ms = int((time.perf_counter() - t_query_owners_start) * 1000)

        project_ids: List[int] = []
        project_owner_by_id: Dict[int, int] = {}
        project_owner_name_by_id: Dict[int, str] = {}
        for pid, owner_id, _ in project_rows:
            if pid is None:
                continue
            project_id_int = int(pid)
            project_ids.append(project_id_int)

            if owner_id is None:
                continue

            owner_id_int = int(owner_id)
            project_owner_by_id[project_id_int] = owner_id_int
            if current_user.is_superuser:
                project_owner_name_by_id[project_id_int] = owners_by_id.get(owner_id_int, "")
            elif owner_id_int == int(current_user.id):
                project_owner_name_by_id[project_id_int] = str(current_user.username or "")

        if safe_kind in {"all", "episode-scripts"}:
            for project_id, owner_id, project_global_info in project_rows:
                payload = None
                try:
                    gi = dict(project_global_info or {})
                    candidate = gi.get("episode_script_generation_status")
                    if isinstance(candidate, dict):
                        payload = dict(candidate)
                except Exception:
                    payload = None
                if not payload:
                    continue

                if _is_generation_job_stale(payload, now_dt=now_dt):
                    stale_episode_script_project_ids.append(int(project_id))
                    continue

                project_id_int = int(project_id)
                owner_id_int = int(owner_id) if owner_id is not None else None

                items.append(
                    _build_batch_job_item(
                        kind="episode-scripts",
                        job_id=f"episode-scripts:{project_id_int}",
                        payload=payload,
                        user_id=project_owner_by_id.get(project_id_int, owner_id_int),
                        username=project_owner_name_by_id.get(project_id_int),
                    )
                )

        if project_ids and safe_kind in {"all", "episode-scenes", "scene-ai-shots-batch", "shot-media-batch"}:
            t_query_episodes_start = time.perf_counter()
            episode_rows = (
                db.query(Episode.id, Episode.project_id, Episode.episode_info)
                .filter(Episode.project_id.in_(project_ids))
                .all()
            )
            t_query_episodes_ms = int((time.perf_counter() - t_query_episodes_start) * 1000)
            for episode_id, episode_project_id, episode_info_raw in episode_rows:
                if episode_id is None or episode_project_id is None:
                    continue
                episode_id_int = int(episode_id)
                episode_project_id_int = int(episode_project_id)
                owner_id = project_owner_by_id.get(episode_project_id_int)
                owner_name = project_owner_name_by_id.get(episode_project_id_int)
                info = _safe_json_dict(episode_info_raw)
                info_changed = False

                if safe_kind in {"all", "episode-scenes"}:
                    payload = info.get(EPISODE_SCENE_GEN_STATUS_KEY)
                    if isinstance(payload, dict):
                        if _is_generation_job_stale(dict(payload), now_dt=now_dt):
                            info.pop(EPISODE_SCENE_GEN_STATUS_KEY, None)
                            info_changed = True
                        else:
                            actor_user_id = payload.get("started_by_user_id") or owner_id
                            actor_username = payload.get("started_by_username") or owner_name
                            items.append(
                                _build_batch_job_item(
                                    kind="episode-scenes",
                                    job_id=f"episode-scenes:{episode_id_int}",
                                    payload=dict(payload),
                                    user_id=actor_user_id,
                                    username=actor_username,
                                )
                            )

                if safe_kind in {"all", "scene-ai-shots-batch"}:
                    payload = info.get(SCENE_AI_SHOTS_BATCH_STATUS_KEY)
                    if isinstance(payload, dict):
                        if _is_generation_job_stale(dict(payload), now_dt=now_dt):
                            info.pop(SCENE_AI_SHOTS_BATCH_STATUS_KEY, None)
                            info_changed = True
                        else:
                            actor_user_id = payload.get("started_by_user_id") or owner_id
                            actor_username = payload.get("started_by_username") or owner_name
                            items.append(
                                _build_batch_job_item(
                                    kind="scene-ai-shots-batch",
                                    job_id=f"scene-ai-shots-batch:{episode_id_int}",
                                    payload=dict(payload),
                                    user_id=actor_user_id,
                                    username=actor_username,
                                )
                            )

                if safe_kind in {"all", "shot-media-batch"}:
                    payload = info.get(SHOT_MEDIA_BATCH_STATUS_KEY)
                    if isinstance(payload, dict):
                        if _is_generation_job_stale(dict(payload), now_dt=now_dt):
                            info.pop(SHOT_MEDIA_BATCH_STATUS_KEY, None)
                            info_changed = True
                        else:
                            actor_user_id = payload.get("started_by_user_id") or owner_id
                            actor_username = payload.get("started_by_username") or owner_name
                            items.append(
                                _build_batch_job_item(
                                    kind="shot-media-batch",
                                    job_id=f"shot-media-batch:{episode_id_int}",
                                    payload=dict(payload),
                                    user_id=actor_user_id,
                                    username=actor_username,
                                )
                            )

                if info_changed:
                    stale_episode_status_updates[episode_id_int] = info

        if stale_episode_script_project_ids:
            stale_project_set = sorted(set(int(v) for v in stale_episode_script_project_ids if int(v) > 0))
            stale_projects = db.query(Project).filter(Project.id.in_(stale_project_set)).all()
            for project in stale_projects:
                gi = dict(project.global_info or {})
                if "episode_script_generation_status" in gi:
                    gi.pop("episode_script_generation_status", None)
                    project.global_info = gi
                    db.add(project)

        if stale_episode_status_updates:
            stale_episode_ids = sorted(stale_episode_status_updates.keys())
            stale_episodes = db.query(Episode).filter(Episode.id.in_(stale_episode_ids)).all()
            for episode in stale_episodes:
                next_info = stale_episode_status_updates.get(int(episode.id))
                if isinstance(next_info, dict):
                    episode.episode_info = next_info
                    db.add(episode)

        if stale_episode_script_project_ids or stale_episode_status_updates:
            try:
                db.commit()
            except Exception:
                db.rollback()

    if not current_user.is_superuser:
        items = [item for item in items if item.get("user_id") == current_user.id]

    if running_only:
        items = [item for item in items if str(item.get("status") or "").lower() not in final_statuses]

    t_filter_sort_start = time.perf_counter()
    if safe_shot_id:
        def _extract_job_shot_id(itm: Dict[str, Any]) -> str:
            if not isinstance(itm, dict):
                return ""
            metadata = itm.get("metadata") if isinstance(itm.get("metadata"), dict) else {}
            payload = itm.get("payload") if isinstance(itm.get("payload"), dict) else {}
            context = itm.get("context") if isinstance(itm.get("context"), dict) else {}
            return str(
                itm.get("shot_id")
                or itm.get("ownerShotId")
                or metadata.get("shot_id")
                or metadata.get("ownerShotId")
                or payload.get("shot_id")
                or payload.get("ownerShotId")
                or context.get("shot_id")
                or context.get("ownerShotId")
                or ""
            ).strip()

        items = [itm for itm in items if _extract_job_shot_id(itm) == safe_shot_id]

    items.sort(key=lambda item: _job_sort_key(item), reverse=True)
    items = items[:safe_limit]

    status_counts: Dict[str, int] = {}
    for item in items:
        status = str(item.get("status") or "unknown").lower()
        status_counts[status] = status_counts.get(status, 0) + 1
    t_filter_sort_ms = int((time.perf_counter() - t_filter_sort_start) * 1000)

    response_payload = {
        "total": len(items),
        "kind": safe_kind,
        "running_only": bool(running_only),
        "status_counts": status_counts,
        "items": [
            {
                k: v for k, v in item.items()
                if k not in {
                    "callback_url",
                    "provider_callback_url",
                    "provider_callback_ticket",
                    "task_scope",
                }
            }
            for item in items
        ],
    }

    _write_generation_job_pool_cache(cache_key, response_payload)

    logger.debug(
        "jobs.pool.timing user_id=%s kind=%s running_only=%s limit=%s cache_hit=0 total_ms=%s cache_ms=%s mem_ms=%s proj_ms=%s owner_ms=%s ep_ms=%s finalize_ms=%s total=%s",
        getattr(current_user, "id", None),
        safe_kind,
        bool(running_only),
        safe_limit,
        int((time.perf_counter() - t0) * 1000),
        t_cache_ms,
        t_collect_mem_ms,
        t_query_projects_ms,
        t_query_owners_ms,
        t_query_episodes_ms,
        t_filter_sort_ms,
        len(items),
    )

    return response_payload


@router.post("/generate/jobs/repair-history")
def repair_generation_job_history(
    kind: str = "all",
    older_than_minutes: int = 120,
    dry_run: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    safe_kind = str(kind or "all").strip().lower()
    allowed_kinds = {"all", "episode-scenes", "episode-scripts", "scene-ai-shots-batch", "shot-media-batch"}
    if safe_kind not in allowed_kinds:
        raise HTTPException(status_code=400, detail="kind must be one of: all, episode-scenes, episode-scripts, scene-ai-shots-batch, shot-media-batch")

    safe_older_than_minutes = max(10, min(int(older_than_minutes or 120), 60 * 24 * 14))
    cutoff_dt = datetime.utcnow() - timedelta(minutes=safe_older_than_minutes)
    now_iso = now_bj_iso()

    if current_user.is_superuser:
        projects = db.query(Project).filter(_active_project_clause()).all()
    else:
        accessible_project_ids = _resolve_accessible_project_ids_for_user(db, current_user)
        if not accessible_project_ids:
            projects = []
        else:
            projects = db.query(Project).filter(
                Project.id.in_(accessible_project_ids),
                _active_project_clause(),
            ).all()

    project_ids = [int(p.id) for p in projects]
    project_owner_by_id = {int(p.id): int(p.owner_id) for p in projects if p.owner_id is not None}

    def _can_touch_project(project_id: int) -> bool:
        if current_user.is_superuser:
            return True
        owner_id = project_owner_by_id.get(int(project_id))
        return owner_id == current_user.id

    repaired = 0
    scanned = 0
    touched_projects: set[int] = set()
    touched_episodes: set[int] = set()
    samples: List[Dict[str, Any]] = []

    if safe_kind in {"all", "episode-scripts"}:
        for project in projects:
            if not _can_touch_project(int(project.id)):
                continue

            gi = dict(project.global_info or {})
            payload = gi.get("episode_script_generation_status")
            if not isinstance(payload, dict):
                continue

            scanned += 1
            normalized = _normalize_batch_job_status(payload)
            if normalized != "running":
                continue

            anchor_dt = _parse_iso_datetime(payload.get("updated_at") or payload.get("started_at") or payload.get("created_at"))
            should_repair = bool(payload.get("stop_requested")) or (anchor_dt is not None and anchor_dt <= cutoff_dt)
            if not should_repair:
                continue

            if len(samples) < 20:
                samples.append({
                    "kind": "episode-scripts",
                    "job_id": f"episode-scripts:{int(project.id)}",
                    "reason": "stop_requested" if bool(payload.get("stop_requested")) else f"stale>{safe_older_than_minutes}m",
                    "updated_at": payload.get("updated_at"),
                    "started_at": payload.get("started_at"),
                })

            if not dry_run:
                payload["running"] = False
                payload["status"] = "canceled"
                payload["stopped_by_user"] = bool(payload.get("stop_requested") or payload.get("stopped_by_user"))
                payload["finished_at"] = payload.get("finished_at") or now_iso
                payload["updated_at"] = now_iso
                payload["message"] = "Repaired stale historical job"
                gi["episode_script_generation_status"] = payload
                project.global_info = gi
                db.add(project)
                repaired += 1
                touched_projects.add(int(project.id))

    if project_ids and safe_kind in {"all", "episode-scenes", "scene-ai-shots-batch", "shot-media-batch"}:
        episodes = db.query(Episode).filter(
            Episode.project_id.in_(project_ids),
            _active_episode_clause(),
        ).all()

        def _maybe_repair_episode_status(episode: Episode, status_key: str, kind_name: str) -> None:
            nonlocal repaired, scanned
            if not _can_touch_project(int(episode.project_id)):
                return

            info = _episode_runtime_info_from_episode(episode)
            payload = info.get(status_key)
            if not isinstance(payload, dict):
                return

            scanned += 1
            normalized = _normalize_batch_job_status(payload)
            if normalized != "running":
                return

            anchor_dt = _parse_iso_datetime(payload.get("updated_at") or payload.get("started_at") or payload.get("created_at"))
            should_repair = bool(payload.get("stop_requested")) or (anchor_dt is not None and anchor_dt <= cutoff_dt)
            if not should_repair:
                return

            if len(samples) < 20:
                samples.append({
                    "kind": kind_name,
                    "job_id": f"{kind_name}:{int(episode.id)}",
                    "reason": "stop_requested" if bool(payload.get("stop_requested")) else f"stale>{safe_older_than_minutes}m",
                    "updated_at": payload.get("updated_at"),
                    "started_at": payload.get("started_at"),
                })

            if not dry_run:
                payload["running"] = False
                payload["status"] = "canceled"
                payload["stopped_by_user"] = bool(payload.get("stop_requested") or payload.get("stopped_by_user"))
                payload["finished_at"] = payload.get("finished_at") or now_iso
                payload["updated_at"] = now_iso
                payload["message"] = "Repaired stale historical job"
                info[status_key] = payload
                episode.episode_info = info
                db.add(episode)
                repaired += 1
                touched_episodes.add(int(episode.id))

        for episode in episodes:
            if safe_kind in {"all", "episode-scenes"}:
                _maybe_repair_episode_status(episode, EPISODE_SCENE_GEN_STATUS_KEY, "episode-scenes")
            if safe_kind in {"all", "scene-ai-shots-batch"}:
                _maybe_repair_episode_status(episode, SCENE_AI_SHOTS_BATCH_STATUS_KEY, "scene-ai-shots-batch")
            if safe_kind in {"all", "shot-media-batch"}:
                _maybe_repair_episode_status(episode, SHOT_MEDIA_BATCH_STATUS_KEY, "shot-media-batch")

    if not dry_run and (touched_projects or touched_episodes):
        db.commit()

    return {
        "ok": True,
        "dry_run": bool(dry_run),
        "kind": safe_kind,
        "older_than_minutes": safe_older_than_minutes,
        "scanned": scanned,
        "repaired": repaired if not dry_run else len(samples),
        "touched_projects": len(touched_projects),
        "touched_episodes": len(touched_episodes),
        "samples": samples,
    }


@router.post("/generate/jobs/{kind}/{job_id}/stop")
def stop_generation_job(
    kind: str,
    job_id: str,
    force: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    safe_kind = str(kind or "").strip().lower()
    if safe_kind not in {"image", "video", "episode-scenes", "episode-scripts", "scene-ai-shots-batch", "shot-media-batch"}:
        raise HTTPException(status_code=400, detail="kind must be one of: image, video, episode-scenes, episode-scripts, scene-ai-shots-batch, shot-media-batch")

    if safe_kind in {"episode-scenes", "scene-ai-shots-batch", "shot-media-batch", "episode-scripts"}:
        target_id = _extract_target_id_from_job_id(job_id)
        if not target_id:
            raise HTTPException(status_code=400, detail="Invalid job_id")

        if safe_kind == "episode-scripts":
            project = db.query(Project).filter(Project.id == target_id).first()
            if not project:
                raise HTTPException(status_code=404, detail="Job not found")
            if not bool(getattr(current_user, "is_superuser", False)):
                _require_project_access(db, int(project.id), current_user)

            gi = dict(project.global_info or {})
            removed = "episode_script_generation_status" in gi
            gi.pop("episode_script_generation_status", None)
            project.global_info = gi
            db.add(project)
            db.commit()

            return {
                "ok": True,
                "kind": safe_kind,
                "job_id": job_id,
                "status": "canceled",
                "deleted": bool(removed),
                "message": "Force removed",
            }

        episode = db.query(Episode).filter(Episode.id == target_id).first()
        if not episode:
            raise HTTPException(status_code=404, detail="Job not found")
        if not bool(getattr(current_user, "is_superuser", False)):
            _require_project_access(db, int(episode.project_id), current_user)

        if safe_kind == "episode-scenes":
            status_key = EPISODE_SCENE_GEN_STATUS_KEY
        elif safe_kind == "scene-ai-shots-batch":
            status_key = SCENE_AI_SHOTS_BATCH_STATUS_KEY
        else:
            status_key = SHOT_MEDIA_BATCH_STATUS_KEY

        info = _episode_runtime_info_from_episode(episode)
        removed = status_key in info
        info.pop(status_key, None)
        episode.episode_info = info
        db.add(episode)
        db.commit()

        if safe_kind == "episode-scenes":
            _clear_episode_worker(EPISODE_SCENE_JOB_THREADS, EPISODE_SCENE_JOB_THREADS_LOCK, int(episode.id))
        elif safe_kind == "scene-ai-shots-batch":
            _clear_episode_worker(SCENE_AI_SHOTS_BATCH_THREADS, SCENE_AI_SHOTS_BATCH_THREADS_LOCK, int(episode.id))
        if safe_kind == "shot-media-batch":
            _set_shot_media_batch_cancel_requested(int(episode.id))
            _clear_episode_worker(SHOT_MEDIA_BATCH_THREADS, SHOT_MEDIA_BATCH_THREADS_LOCK, int(episode.id))
            _clear_shot_media_batch_cancel_event(int(episode.id))

        return {
            "ok": True,
            "kind": safe_kind,
            "job_id": job_id,
            "status": "canceled",
            "deleted": bool(removed),
            "message": "Force removed",
        }

    if safe_kind == "image":
        lock = IMAGE_JOB_LOCK
        store = IMAGE_JOB_STORE
        task_store = IMAGE_JOB_TASKS
        read_file_func = _read_image_job_file
        set_job_func = _set_image_job
    else:
        lock = VIDEO_JOB_LOCK
        store = VIDEO_JOB_STORE
        task_store = VIDEO_JOB_TASKS
        read_file_func = _read_video_job_file
        set_job_func = _set_video_job

    with lock:
        job = dict(store.get(job_id) or {})
        task_ref = task_store.get(job_id)

    if not job:
        file_job = read_file_func(job_id)
        if file_job:
            with lock:
                store[job_id] = dict(file_job)
            job = dict(file_job)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    owner_id = job.get("user_id")
    if not current_user.is_superuser and owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    status = str(job.get("status") or "").lower()
    if not force and status in {"succeeded", "failed", "canceled", "cancelled", "error"}:
        return {
            "ok": True,
            "kind": safe_kind,
            "job_id": job_id,
            "status": status,
            "message": "Job already finished",
        }

    set_job_func(
        job_id,
        status="canceled",
        finished_at=now_bj_iso(),
        error="Force stopped by user" if force else "Cancelled by user",
    )

    _cancel_generation_task_ref(
        task_ref or job_id,
        user_id=owner_id,
        reason="Force stopped by user" if force else "Cancelled by user",
    )

    # Force: also remove task ref from store to prevent further polling
    if force:
        try:
            with lock:
                task_stores_ref = task_store
                if job_id in task_stores_ref:
                    del task_stores_ref[job_id]
        except Exception:
            pass

    return {
        "ok": True,
        "kind": safe_kind,
        "job_id": job_id,
        "status": "canceled",
        "message": "Force stopped" if force else "Stop requested",
    }


@router.delete("/generate/jobs/{kind}/{job_id}")
def delete_generation_job(
    kind: str,
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    is_superuser = bool(getattr(current_user, "is_superuser", False))

    safe_kind = str(kind or "").strip().lower()
    if safe_kind not in {"image", "video", "episode-scenes", "episode-scripts", "scene-ai-shots-batch", "shot-media-batch"}:
        raise HTTPException(status_code=400, detail="kind must be one of: image, video, episode-scenes, episode-scripts, scene-ai-shots-batch, shot-media-batch")

    target_id = _extract_target_id_from_job_id(job_id)

    if safe_kind in {"episode-scenes", "scene-ai-shots-batch", "shot-media-batch", "episode-scripts"}:
        if not target_id:
            raise HTTPException(status_code=400, detail="Invalid job_id")

        if safe_kind == "episode-scripts":
            project = db.query(Project).filter(Project.id == target_id).first()
            if not project:
                raise HTTPException(status_code=404, detail="Job not found")
            gi = dict(project.global_info or {})
            if "episode_script_generation_status" not in gi:
                raise HTTPException(status_code=404, detail="Job not found")
            payload = gi.get("episode_script_generation_status")
            actor_user_id = None
            if isinstance(payload, dict):
                raw_uid = payload.get("started_by_user_id") or payload.get("user_id") or project.owner_id
                try:
                    actor_user_id = int(raw_uid) if raw_uid is not None else None
                except Exception:
                    actor_user_id = None
            if not is_superuser and actor_user_id != int(current_user.id):
                raise HTTPException(status_code=403, detail="Not authorized to delete this job")
            gi.pop("episode_script_generation_status", None)
            project.global_info = gi
            db.add(project)
            db.commit()
            return {
                "ok": True,
                "kind": safe_kind,
                "job_id": job_id,
                "deleted": True,
                "message": "Deleted from job history",
            }

        episode = db.query(Episode).filter(Episode.id == target_id).first()
        if not episode:
            raise HTTPException(status_code=404, detail="Job not found")

        if safe_kind == "episode-scenes":
            status_key = EPISODE_SCENE_GEN_STATUS_KEY
        elif safe_kind == "scene-ai-shots-batch":
            status_key = SCENE_AI_SHOTS_BATCH_STATUS_KEY
        else:
            status_key = SHOT_MEDIA_BATCH_STATUS_KEY

        info = _episode_runtime_info_from_episode(episode)
        if status_key not in info:
            raise HTTPException(status_code=404, detail="Job not found")

        payload = info.get(status_key)
        actor_user_id = None
        if isinstance(payload, dict):
            raw_uid = payload.get("started_by_user_id") or payload.get("user_id")
            if raw_uid is None:
                try:
                    project = db.query(Project).filter(Project.id == int(episode.project_id)).first()
                    raw_uid = project.owner_id if project else None
                except Exception:
                    raw_uid = None
            try:
                actor_user_id = int(raw_uid) if raw_uid is not None else None
            except Exception:
                actor_user_id = None
        if not is_superuser and actor_user_id != int(current_user.id):
            raise HTTPException(status_code=403, detail="Not authorized to delete this job")

        info.pop(status_key, None)
        episode.episode_info = info
        db.add(episode)
        db.commit()

        if safe_kind == "shot-media-batch":
            _clear_shot_media_batch_cancel_event(int(episode.id))

        return {
            "ok": True,
            "kind": safe_kind,
            "job_id": job_id,
            "deleted": True,
            "message": "Deleted from job history",
        }

    if safe_kind == "image":
        lock = IMAGE_JOB_LOCK
        store = IMAGE_JOB_STORE
        task_store = IMAGE_JOB_TASKS
        active_scope_store = IMAGE_ACTIVE_SCOPE_STORE
        idempotency_store = IMAGE_SUBMIT_IDEMPOTENCY_STORE
        file_path = _image_job_file_path(job_id)
    else:
        lock = VIDEO_JOB_LOCK
        store = VIDEO_JOB_STORE
        task_store = VIDEO_JOB_TASKS
        active_scope_store = VIDEO_ACTIVE_SCOPE_STORE
        idempotency_store = VIDEO_SUBMIT_IDEMPOTENCY_STORE
        file_path = _video_job_file_path(job_id)

    task_ref = None
    file_payload = None
    with lock:
        has_store_item = job_id in store
        if not has_store_item:
            file_payload = _read_image_job_file(job_id) if safe_kind == "image" else _read_video_job_file(job_id)
            if not file_payload:
                raise HTTPException(status_code=404, detail="Job not found")

        live_payload = dict(store.get(job_id) or {})
        owner_raw = live_payload.get("user_id") if live_payload else None
        if owner_raw is None and isinstance(file_payload, dict):
            owner_raw = file_payload.get("user_id")
        try:
            owner_id = int(owner_raw) if owner_raw is not None else None
        except Exception:
            owner_id = None
        if not is_superuser and owner_id != int(current_user.id):
            raise HTTPException(status_code=403, detail="Not authorized to delete this job")

        task_ref = task_store.pop(job_id, None)
        store.pop(job_id, None)

        stale_scope_keys = [key for key, value in active_scope_store.items() if str(value or "") == job_id]
        for key in stale_scope_keys:
            active_scope_store.pop(key, None)

        stale_idempotency_keys = [key for key, value in idempotency_store.items() if str((value or {}).get("job_id") or "") == job_id]
        for key in stale_idempotency_keys:
            idempotency_store.pop(key, None)

    _cancel_generation_task_ref(task_ref or job_id, user_id=owner_id, reason="Deleted from job history")

    try:
        from app.services.generation_task_queue import delete_generation_job_state

        delete_generation_job_state(kind=safe_kind, job_id=job_id)
    except Exception:
        pass

    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception:
        pass

    return {
        "ok": True,
        "kind": safe_kind,
        "job_id": job_id,
        "deleted": True,
        "message": "Deleted from job history",
    }


@router.post("/generate/jobs/stop-all")
def stop_all_generation_jobs(
    kind: str = "all",
    force: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    safe_kind = str(kind or "all").strip().lower()
    allowed_kinds = {"all", "image", "video", "episode-scenes", "episode-scripts", "scene-ai-shots-batch", "shot-media-batch"}
    if safe_kind not in allowed_kinds:
        raise HTTPException(status_code=400, detail="kind must be one of: all, image, video, episode-scenes, episode-scripts, scene-ai-shots-batch, shot-media-batch")

    now_iso = now_bj_iso()
    stopped = 0
    touched: List[str] = []

    def _can_access_project(project_id: int) -> bool:
        if current_user.is_superuser:
            return True
        try:
            _require_project_access(db, int(project_id), current_user)
            return True
        except Exception:
            return False

    if safe_kind in {"all", "image"}:
        with IMAGE_JOB_LOCK:
            _prune_image_jobs_locked()
            if force:
                image_ids = list(IMAGE_JOB_STORE.keys())
            else:
                image_ids = [jid for jid, payload in IMAGE_JOB_STORE.items() if str((payload or {}).get("status") or "").lower() in {"queued", "running"}]
        for jid in image_ids:
            with IMAGE_JOB_LOCK:
                payload = dict(IMAGE_JOB_STORE.get(jid) or {})
                task_ref = IMAGE_JOB_TASKS.get(jid)
            owner_id = payload.get("user_id")
            if not current_user.is_superuser and owner_id != current_user.id:
                continue
            _set_image_job(jid, status="canceled", finished_at=now_iso, error="Cancelled by stop-all")
            _cancel_generation_task_ref(task_ref or jid, user_id=owner_id, reason="Cancelled by stop-all")
            stopped += 1
            touched.append(f"image:{jid}")

    if safe_kind in {"all", "video"}:
        with VIDEO_JOB_LOCK:
            _prune_video_jobs_locked()
            if force:
                video_ids = list(VIDEO_JOB_STORE.keys())
            else:
                video_ids = [jid for jid, payload in VIDEO_JOB_STORE.items() if str((payload or {}).get("status") or "").lower() in {"queued", "running"}]
        for jid in video_ids:
            with VIDEO_JOB_LOCK:
                payload = dict(VIDEO_JOB_STORE.get(jid) or {})
                task_ref = VIDEO_JOB_TASKS.get(jid)
            owner_id = payload.get("user_id")
            if not current_user.is_superuser and owner_id != current_user.id:
                continue
            _set_video_job(jid, status="canceled", finished_at=now_iso, error="Cancelled by stop-all")
            _cancel_generation_task_ref(task_ref or jid, user_id=owner_id, reason="Cancelled by stop-all")
            stopped += 1
            touched.append(f"video:{jid}")

    if safe_kind in {"all", "image", "video"}:
        try:
            from app.services.generation_task_queue import cancel_generation_tasks

            queue_total = 0
            owner_filter = None if current_user.is_superuser else int(current_user.id)
            if safe_kind == "image":
                queue_total += int(
                    cancel_generation_tasks(
                        kind="image",
                        user_id=owner_filter,
                        reason="Cancelled by stop-all",
                    )
                    or 0
                )
            elif safe_kind == "video":
                queue_total += int(
                    cancel_generation_tasks(
                        kind="video",
                        user_id=owner_filter,
                        reason="Cancelled by stop-all",
                    )
                    or 0
                )
            else:
                queue_total += int(
                    cancel_generation_tasks(
                        kind="image",
                        user_id=owner_filter,
                        reason="Cancelled by stop-all",
                    )
                    or 0
                )
                queue_total += int(
                    cancel_generation_tasks(
                        kind="video",
                        user_id=owner_filter,
                        reason="Cancelled by stop-all",
                    )
                    or 0
                )
            if queue_total > 0:
                stopped += queue_total
                touched.append(f"queue:{safe_kind}:{queue_total}")
        except Exception as e:
            logger.warning("stop-all queue cleanup skipped | kind=%s err=%s", safe_kind, e)

    if safe_kind in {"all", "episode-scripts"}:
        projects = db.query(Project).filter(_active_project_clause()).all() if current_user.is_superuser else db.query(Project).filter(
            Project.owner_id == current_user.id,
            _active_project_clause(),
        ).all()
        for project in projects:
            if not _can_access_project(int(project.id)):
                continue
            gi = dict(project.global_info or {})
            payload = gi.get("episode_script_generation_status")
            if not isinstance(payload, dict):
                continue
            if (not force) and str(payload.get("status") or "").lower() in {"succeeded", "completed", "failed", "canceled", "cancelled", "error", "stopped", "idle", "partial"} and not bool(payload.get("running")):
                continue
            gi.pop("episode_script_generation_status", None)
            project.global_info = gi
            db.add(project)
            stopped += 1
            touched.append(f"episode-scripts:{int(project.id)}")

    if safe_kind in {"all", "episode-scenes", "scene-ai-shots-batch", "shot-media-batch"}:
        episodes = db.query(Episode).filter(_active_episode_clause()).all()
        for episode in episodes:
            if not episode.project_id:
                continue
            if not _can_access_project(int(episode.project_id)):
                continue
            info = _episode_runtime_info_from_episode(episode)
            key_pairs = []
            if safe_kind in {"all", "episode-scenes"}:
                key_pairs.append((EPISODE_SCENE_GEN_STATUS_KEY, "episode-scenes"))
            if safe_kind in {"all", "scene-ai-shots-batch"}:
                key_pairs.append((SCENE_AI_SHOTS_BATCH_STATUS_KEY, "scene-ai-shots-batch"))
            if safe_kind in {"all", "shot-media-batch"}:
                key_pairs.append((SHOT_MEDIA_BATCH_STATUS_KEY, "shot-media-batch"))

            changed = False
            for status_key, kind_name in key_pairs:
                payload = info.get(status_key)
                if not isinstance(payload, dict):
                    continue
                if (not force) and str(payload.get("status") or "").lower() in {"succeeded", "completed", "failed", "canceled", "cancelled", "error", "stopped", "idle", "partial"} and not bool(payload.get("running")):
                    continue
                info.pop(status_key, None)
                changed = True
                stopped += 1
                touched.append(f"{kind_name}:{int(episode.id)}")
                if kind_name == "episode-scenes":
                    _clear_episode_worker(EPISODE_SCENE_JOB_THREADS, EPISODE_SCENE_JOB_THREADS_LOCK, int(episode.id))
                elif kind_name == "scene-ai-shots-batch":
                    _clear_episode_worker(SCENE_AI_SHOTS_BATCH_THREADS, SCENE_AI_SHOTS_BATCH_THREADS_LOCK, int(episode.id))
                if kind_name == "shot-media-batch":
                    _set_shot_media_batch_cancel_requested(int(episode.id))
                    _clear_episode_worker(SHOT_MEDIA_BATCH_THREADS, SHOT_MEDIA_BATCH_THREADS_LOCK, int(episode.id))
                    _clear_shot_media_batch_cancel_event(int(episode.id))

            if changed:
                episode.episode_info = info
                db.add(episode)

    db.commit()

    return {
        "ok": True,
        "kind": safe_kind,
        "force": bool(force),
        "stopped": stopped,
        "items": touched[:200],
        "message": "Stop-all requested",
    }


SHOT_MEDIA_BATCH_STATUS_KEY = "shot_media_batch_status"
SHOT_MEDIA_BATCH_DEFAULT_CONCURRENCY = 3
SHOT_MEDIA_BATCH_RUNTIME_CACHE: Dict[int, Dict[str, Any]] = {}
SHOT_MEDIA_BATCH_RUNTIME_CACHE_LOCK = threading.Lock()


def _cache_shot_media_batch_status(episode_id: int, status_payload: Dict[str, Any]) -> None:
    try:
        safe_episode_id = int(episode_id)
    except Exception:
        return
    if safe_episode_id <= 0:
        return
    snapshot = dict(status_payload or {})
    with SHOT_MEDIA_BATCH_RUNTIME_CACHE_LOCK:
        SHOT_MEDIA_BATCH_RUNTIME_CACHE[safe_episode_id] = snapshot


def _get_cached_shot_media_batch_status(episode_id: int) -> Optional[Dict[str, Any]]:
    try:
        safe_episode_id = int(episode_id)
    except Exception:
        return None
    if safe_episode_id <= 0:
        return None
    with SHOT_MEDIA_BATCH_RUNTIME_CACHE_LOCK:
        payload = SHOT_MEDIA_BATCH_RUNTIME_CACHE.get(safe_episode_id)
        if isinstance(payload, dict):
            return dict(payload)
    return None


def _clear_cached_shot_media_batch_status(episode_id: int) -> None:
    try:
        safe_episode_id = int(episode_id)
    except Exception:
        return
    if safe_episode_id <= 0:
        return
    with SHOT_MEDIA_BATCH_RUNTIME_CACHE_LOCK:
        SHOT_MEDIA_BATCH_RUNTIME_CACHE.pop(safe_episode_id, None)


def _read_shot_media_batch_status(episode: Episode) -> Dict[str, Any]:
    try:
        info = _episode_runtime_info_from_episode(episode)
        payload = info.get(SHOT_MEDIA_BATCH_STATUS_KEY)
        if isinstance(payload, dict):
            return dict(payload)
    except Exception:
        pass
    return {
        "running": False,
        "mode": "keyframes",
        "total": 0,
        "completed": 0,
        "success": 0,
        "failed": 0,
        "message": "",
        "errors": [],
        "stop_requested": False,
    }


def _persist_shot_media_batch_status(db: Session, episode: Episode, status_payload: Dict[str, Any]) -> None:
    latest_episode = (
        db.query(Episode)
        .execution_options(populate_existing=True)
        .filter(Episode.id == int(episode.id))
        .first()
    )
    target_episode = latest_episode or episode

    info = _episode_runtime_info_from_episode(target_episode)
    existing_status = info.get(SHOT_MEDIA_BATCH_STATUS_KEY)
    merged_status = dict(status_payload or {})
    has_incoming_force_flag = "force_stopped" in merged_status
    has_incoming_stop_flag = "stop_requested" in merged_status

    if isinstance(existing_status, dict) and bool(existing_status.get("force_stopped")) and not has_incoming_force_flag:
        merged_status["force_stopped"] = True

    if isinstance(existing_status, dict) and bool(existing_status.get("stop_requested")) and not has_incoming_stop_flag:
        merged_status["stop_requested"] = True
        if existing_status.get("stop_requested_at") and not merged_status.get("stop_requested_at"):
            merged_status["stop_requested_at"] = existing_status.get("stop_requested_at")
        if not merged_status.get("stopped_by_user"):
            merged_status["stopped_by_user"] = bool(existing_status.get("stopped_by_user"))

    if bool(merged_status.get("force_stopped")):
        now_iso = now_bj_iso()
        merged_status["running"] = False
        merged_status["status"] = "canceled"
        merged_status["stopped_by_user"] = True
        merged_status["finished_at"] = merged_status.get("finished_at") or now_iso
        merged_status["updated_at"] = now_iso
        merged_status["message"] = merged_status.get("message") or "Force stopped"

    info[SHOT_MEDIA_BATCH_STATUS_KEY] = merged_status
    target_episode.episode_info = info
    db.add(target_episode)
    db.commit()
    _cache_shot_media_batch_status(int(target_episode.id), merged_status)


def _is_shot_video_batch_eligible(shot: Shot, overwrite_existing: bool = False) -> bool:
    tech = _parse_shot_tech(shot)
    start_frame_url = str(getattr(shot, "image_url", "") or "").strip()
    end_frame_url = str(tech.get("end_frame_url") or "").strip()
    video_url = str(getattr(shot, "video_url", "") or "").strip()
    if not overwrite_existing and video_url:
        return False
    return bool(start_frame_url or end_frame_url)


def _parse_shot_tech(shot: Shot) -> Dict[str, Any]:
    try:
        payload = json.loads(shot.technical_notes or "{}")
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass
    return {}


def _normalize_entity_anchor_token(value: Any) -> str:
    return normalize_entity_token(value)


def _entity_lookup_alias_keys(*raw_names: Any) -> set:
    """Build lookup aliases aligned with frontend entityTokenMatchesName."""
    keys: set = set()
    for raw in raw_names:
        text = str(raw or "").strip()
        if not text:
            continue
        normalized = _normalize_entity_anchor_token(text)
        if normalized:
            keys.add(normalized)
            base = normalized.split("(")[0].strip()
            if base:
                keys.add(base)
        for compare_key in subject_compare_key_variants(text):
            if compare_key:
                keys.add(compare_key)
    return {key for key in keys if key}


def _build_project_entity_lookup(
    db: Session,
    project_id: int,
    episode_id: Optional[int] = None,
) -> Dict[str, Dict[str, Any]]:
    """Build name→entity lookup for video/image ref resolution.

    When episode_id is provided, prefer entities from that episode, then project-global
    (episode_id IS NULL), then other episodes. This prevents same-name subjects from
    earlier episodes winning via first-insert setdefault.
    """
    rows = (
        db.query(Entity)
        .filter(Entity.project_id == project_id, _active_entity_clause())
        .all()
    )
    preferred_episode_id = _to_positive_int_or_none(episode_id)

    def _preference_score(row: Entity) -> Tuple[int, int, int]:
        raw_ep = getattr(row, "episode_id", None)
        try:
            ep_id_int = int(raw_ep) if raw_ep is not None else 0
        except Exception:
            ep_id_int = 0
        entity_id = int(getattr(row, "id", 0) or 0)
        if preferred_episode_id:
            if ep_id_int == int(preferred_episode_id):
                return (3, ep_id_int, entity_id)
            if raw_ep is None:
                return (2, 0, entity_id)
            # Other episodes: prefer nearer (higher) episode as weak fallback only.
            return (1, ep_id_int, entity_id)
        if ep_id_int > 0:
            return (2, ep_id_int, entity_id)
        return (1, 0, entity_id)

    # Highest preference first so setdefault keeps the best row per alias.
    ordered_rows = sorted(rows, key=_preference_score, reverse=True)

    lookup: Dict[str, Dict[str, Any]] = {}
    for row in ordered_rows:
        canonical_name = str(row.name or row.name_en or "").strip()
        anchor_description = str(row.anchor_description or "").strip()
        anchor = str(
            row.anchor_description
            or row.narrative_description
            or canonical_name
            or ""
        ).strip()
        image_url = str(row.image_url or "").strip()
        entity_type = str(row.type or "").strip().lower()
        payload = {
            "name": canonical_name,
            "name_en": str(getattr(row, "name_en", None) or "").strip(),
            "anchor_description": anchor_description,
            "anchor": anchor,
            "description": str(row.description or row.narrative_description or anchor or "").strip(),
            "image_url": image_url,
            "entity_id": row.id,
            "entity_type": entity_type,
            "episode_id": getattr(row, "episode_id", None),
        }
        for key in _entity_lookup_alias_keys(row.name, row.name_en, canonical_name):
            # Prefer first writer after preference sort (current episode / best fallback).
            lookup.setdefault(key, payload)
    return lookup


def _extract_kling_character_mentions(prompt: Any) -> List[str]:
    text = str(prompt or "")
    if not text:
        return []

    mentions: List[str] = []
    seen: set[str] = set()
    for match in re.finditer(r"CHAR\s*:\s*\[@([^\]]+)\]", text, flags=re.IGNORECASE):
        raw_name = str(match.group(1) or "").strip()
        normalized = _normalize_entity_anchor_token(raw_name)
        if not raw_name or not normalized or normalized in seen:
            continue
        seen.add(normalized)
        mentions.append(raw_name)
    return mentions


def _collect_kling_prompt_alias_maps(
    prompt_candidates: List[str],
    entity_lookup: Dict[str, Dict[str, Any]],
) -> Tuple[List[str], Dict[str, str], Dict[int, str]]:
    mentions: List[str] = []
    alias_by_norm: Dict[str, str] = {}
    alias_by_entity_id: Dict[int, str] = {}
    seen_mentions: set[str] = set()

    for candidate in prompt_candidates:
        for raw_name in _extract_kling_character_mentions(candidate):
            alias_name = str(raw_name or "").strip().lstrip("@").strip()
            normalized = _normalize_entity_anchor_token(raw_name)
            if not alias_name or not normalized or normalized in seen_mentions:
                continue
            seen_mentions.add(normalized)
            mentions.append(alias_name)
            alias_by_norm[normalized] = alias_name

            row = entity_lookup.get(normalized) or {}
            entity_id = row.get("entity_id")
            if isinstance(entity_id, int) and entity_id not in alias_by_entity_id:
                alias_by_entity_id[entity_id] = alias_name

    return mentions, alias_by_norm, alias_by_entity_id


def _build_auto_kling_elements(
    prompt_candidates: List[str],
    entity_lookup: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    allowed_types = {"subject", "character", "char"}
    mentions, _, _ = _collect_kling_prompt_alias_maps(prompt_candidates, entity_lookup)

    elements: List[Dict[str, Any]] = []
    for raw_name in mentions:
        row = entity_lookup.get(_normalize_entity_anchor_token(raw_name)) or {}
        entity_type = str(row.get("entity_type") or "").strip().lower() if row else ""
        if entity_type not in allowed_types:
            continue

        name = str(raw_name or "").strip().lstrip("@").strip()
        if not name:
            continue

        description = str(row.get("anchor") or row.get("description") or name).strip() or name
        element: Dict[str, Any] = {
            "name": name,
            "description": description,
        }

        image_url = str(row.get("image_url") or "").strip()
        if image_url:
            element["element_input_urls"] = [image_url, image_url]

        elements.append(element)

    return elements


def _align_kling_elements_to_prompt_mentions(
    elements: List[Dict[str, Any]],
    prompt_candidates: List[str],
    entity_lookup: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    _, alias_by_norm, alias_by_entity_id = _collect_kling_prompt_alias_maps(prompt_candidates, entity_lookup)
    if not alias_by_norm and not alias_by_entity_id:
        return elements

    aligned: List[Dict[str, Any]] = []
    for element in elements:
        if not isinstance(element, dict):
            continue

        name = str(element.get("name") or "").strip()
        normalized = _normalize_entity_anchor_token(name)
        if not name or not normalized:
            continue

        row = entity_lookup.get(normalized) or {}
        entity_id = row.get("entity_id")
        alias_name = alias_by_entity_id.get(entity_id) if isinstance(entity_id, int) else None
        if not alias_name:
            alias_name = alias_by_norm.get(normalized)

        if alias_name and alias_name != name:
            updated = dict(element)
            updated["name"] = alias_name
            aligned.append(updated)
        else:
            aligned.append(element)

    return aligned


def _merge_kling_elements(explicit_elements: Any, auto_elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    max_elements = 3
    merged: List[Dict[str, Any]] = []
    seen: set[str] = set()

    def _push(candidate: Any) -> None:
        if len(merged) >= max_elements:
            return
        if not isinstance(candidate, dict):
            return

        name = str(candidate.get("name") or "").strip()
        normalized = _normalize_entity_anchor_token(name)
        description = str(candidate.get("description") or "").strip()
        if not name or not normalized or normalized in seen or not description:
            return

        item: Dict[str, Any] = {
            "name": name,
            "description": description,
        }

        image_inputs = candidate.get("element_input_urls")
        if isinstance(image_inputs, list):
            urls = [str(url).strip() for url in image_inputs if str(url).strip()]
            if urls:
                if len(urls) == 1:
                    urls.append(urls[0])
                elif len(urls) > 4:
                    urls = urls[:4]
                item["element_input_urls"] = urls

        video_inputs = candidate.get("element_input_video_urls")
        if isinstance(video_inputs, list):
            urls = [str(url).strip() for url in video_inputs if str(url).strip()]
            if urls:
                item["element_input_video_urls"] = urls

        seen.add(normalized)
        merged.append(item)

    if isinstance(explicit_elements, list):
        for element in explicit_elements:
            _push(element)
            if len(merged) >= max_elements:
                break

    for element in auto_elements:
        _push(element)
        if len(merged) >= max_elements:
            break

    return merged


def _inject_shot_prompt_anchors(
    prompt: str,
    entity_lookup: Dict[str, Dict[str, Any]],
    global_style: str = "",
    subject_ref_index_map: Optional[Dict[str, int]] = None,
) -> str:
    text = str(prompt or "")
    if not text:
        return text

    regex = re.compile(r"\[[\s\S]+?\]|\{[\s\S]+?\}|【[\s\S]+?】|｛[\s\S]+?｝|(?<=^)@[^\s,，;；\]\[\(\)（）\{\}【】]+|(?<=[\s,，;；])@[^\s,，;；\]\[\(\)（）\{\}【】]+")
    injected_entities: set[str] = set()

    def _replace(match: re.Match) -> str:
        token = str(match.group(0) or "").strip()
        normalized = _normalize_entity_anchor_token(token)
        tail = text[match.end():]
        if re.match(r"^\s*[\(（]", tail):
            return match.group(0)

        if normalized in {"global style", "global_style"} and global_style:
            return f"{match.group(0)}({global_style})"

        row = entity_lookup.get(normalized)
        if row and row.get("anchor"):
            anchor = str(row.get("anchor") or "").strip()
            entity_id = str(row.get("entity_id") or "").strip()
            ref_no = (subject_ref_index_map or {}).get(entity_id)

            if normalized in injected_entities:
                # Duplicate reference: skip anchor description to prevent
                # image models from interpreting repeated descriptions as
                # multiple subjects (二宫格 / split-panel issue).
                if ref_no:
                    logger.info(f"[_inject_shot_prompt_anchors] Re-injected: {normalized} -> ref_image_url: #{ref_no}")
                    return f"{match.group(0)}(ref_image_url: #{ref_no})"
                return match.group(0)

            injected_entities.add(normalized)
            anchor_with_ref = anchor
            if ref_no:
                anchor_with_ref = f"{anchor} | ref_image_url: #{ref_no}"
            
            logger.info(f"[_inject_shot_prompt_anchors] Injected: {normalized} -> {anchor_with_ref}")
            return f"{match.group(0)}({anchor_with_ref})"
        return match.group(0)

    return regex.sub(_replace, text)


def _collect_associated_entities_refs(associated_entities_str: Optional[str], entity_lookup: Dict[str, Dict[str, Any]]) -> List[str]:
    if not isinstance(associated_entities_str, str) or not associated_entities_str.strip():
        return []

    refs: List[str] = []
    names = extract_entity_raw_names_from_prompt(associated_entities_str)
    if not names:
        names = [x.strip() for x in re.split(r"[,，]", associated_entities_str) if x.strip()]

    for name in names:
        norm_name = _normalize_entity_anchor_token(name)
        if not norm_name:
            continue
        row = entity_lookup.get(norm_name)
        if row:
            image_url = str((row or {}).get("image_url") or "").strip()
            if image_url:
                refs.append(image_url)

    return [x for x in dict.fromkeys(refs) if x]


def _extract_frontend_aligned_entity_raw_names(text: str) -> list[str]:
    return extract_entity_raw_names_from_prompt(text)

def _collect_prompt_entity_ref_images(prompt: str, entity_lookup: Dict[str, Dict[str, Any]]) -> List[str]:
    text = str(prompt or "")
    if not text:
        return []

    refs: List[str] = []
    raw_names = _extract_frontend_aligned_entity_raw_names(text)
    for raw_name in raw_names:
        normalized = _normalize_entity_anchor_token(raw_name)
        if not normalized:
            continue
        row = entity_lookup.get(normalized)
        image_url = str((row or {}).get("image_url") or "").strip()
        if image_url:
            refs.append(image_url)
    return [x for x in dict.fromkeys(refs) if x]


def _collect_prompt_entity_ref_images_relaxed(prompt: str, entity_lookup: Dict[str, Dict[str, Any]]) -> List[str]:
    text = str(prompt or "").strip()
    if not text:
        return []

    refs: List[str] = []

    allowed_types = {"subject", "character", "char", "environment", "env", "prop", "props"}

    refs.extend(_collect_prompt_entity_ref_images(text, entity_lookup))

    normalized_text = _normalize_entity_anchor_token(text)
    if not normalized_text:
        return [x for x in dict.fromkeys(refs) if x]

    for key, row in (entity_lookup or {}).items():
        norm_key = str(key or "").strip()
        if not norm_key:
            continue

        entity_type = str((row or {}).get("entity_type") or "").strip().lower()
        if entity_type and entity_type not in allowed_types:
            continue

        image_url = str((row or {}).get("image_url") or "").strip()
        if not image_url:
            continue

        has_ascii = bool(re.search(r"[a-z0-9]", norm_key, flags=re.IGNORECASE))
        if has_ascii:
            pattern = rf"(?<![a-z0-9]){re.escape(norm_key)}(?![a-z0-9])"
            matched = re.search(pattern, normalized_text, flags=re.IGNORECASE) is not None
        else:
            matched = norm_key in normalized_text

        if matched:
            refs.append(image_url)

    return [x for x in dict.fromkeys(refs) if x]


def _normalize_video_ref_mode(value: Any) -> str:
    mode = str(value or "").strip().lower()
    if not mode or mode == "auto":
        return ""
    refs_aliases = {"entity_refs", "entity-refs", "refs_video", "refs-video", "reference", "reference_image", "reference_images"}
    if mode in refs_aliases:
        return "entity_refs"
    if mode in {"keyframes_entity_refs", "keyframe_entity_refs", "keyframes-entity-refs", "keyframe-entity-refs"}:
        return "keyframes_entity_refs"
    if mode in {"entity_refs_start_end", "entity-refs-start-end", "ref_start_end", "ref+start_end"}:
        return "entity_refs_start_end"
    if mode in {"start", "start_only", "start-only", "only_start", "only-start"}:
        return "start"
    if mode in {"start_end", "start-end", "start+end", "both", "both_ends"}:
        return "start_end"
    if mode in {"end", "end_only", "end-only", "only_end", "only-end"}:
        return "end"
    return ""


DEFAULT_SHOT_VIDEO_MODE = "entity_refs"


def _resolve_shot_video_mode(payload: Dict[str, Any]) -> str:
    if not isinstance(payload, dict):
        return DEFAULT_SHOT_VIDEO_MODE

    unified = _normalize_video_ref_mode(payload.get("video_mode_unified"))
    if unified:
        return unified

    ref_submit = str(payload.get("video_ref_submit_mode") or "").strip().lower()
    if ref_submit in {"entity_refs", "refs_video"}:
        return "entity_refs"

    legacy_gen = _normalize_video_ref_mode(payload.get("video_gen_mode"))
    if legacy_gen and ref_submit == "auto":
        return legacy_gen

    return DEFAULT_SHOT_VIDEO_MODE


def _dedupe_media_ref_urls(values: Optional[List[str]]) -> List[str]:
    refs = [str(x).strip() for x in (values or []) if str(x).strip()]
    unique_refs = []
    seen = set()
    for x in refs:
        base = x.split("?")[0]
        if base not in seen:
            seen.add(base)
            unique_refs.append(x)
    return unique_refs


def _system_api_supports_last_frame_flag(provider: Any, model: Any) -> Optional[bool]:
    provider_text = str(provider or "").strip()
    model_text = str(model or "").strip()
    if not provider_text or not model_text:
        return None

    try:
        with SessionLocal() as lookup_db:
            row = get_system_api_setting(
                lookup_db,
                provider=provider_text,
                category="Video",
                model=model_text,
            )
            if row is None:
                return None

            modality = _safe_json_dict(getattr(row, "modality", None))
            capability_flags = _safe_json_dict(modality.get("capability_flags"))
            video_caps = _safe_json_dict(modality.get("video_capabilities"))
            for container in (capability_flags, video_caps):
                for key in ("supports_last_frame", "supports_last_frame_mode", "last_frame_supported"):
                    value = container.get(key)
                    if isinstance(value, bool):
                        return value
                    if value is not None:
                        text = str(value).strip().lower()
                        if text in {"1", "true", "yes", "y", "on"}:
                            return True
                        if text in {"0", "false", "no", "n", "off"}:
                            return False
    except Exception:
        return None

    return None


def _video_api_supports_last_frame_mode(provider: Any, model: Any) -> bool:
    explicit_flag = _system_api_supports_last_frame_flag(provider, model)
    if explicit_flag is not None:
        return explicit_flag

    provider_text = str(provider or "").strip().lower()
    model_text = str(model or "").strip().lower()

    if provider_text == "kie" and model_text in {
        "kling-2.6/image-to-video",
        "sora-2-image-to-video",
        "sora-2-pro-image-to-video",
        "hailuo/2-3-image-to-video-standard",
        "hailuo/2-3-image-to-video-pro",
    }:
        return False

    if provider_text == "wanxiang":
        if "happyhorse" in model_text:
            return False
        if model_text and "kf2v" not in model_text and ("image-to-video" in model_text or model_text.endswith("i2v") or "-i2v" in model_text):
            return False

    if provider_text == "happyhorse":
        return False

    return True


def _normalize_video_request_refs(
    ref_image_url: Optional[Union[str, List[str]]],
    last_frame_url: Optional[str],
    ref_mode: Any,
    *,
    supports_last_frame_mode: bool,
) -> Tuple[Optional[Union[str, List[str]]], Optional[str], Dict[str, Any]]:
    normalized_mode = _normalize_video_ref_mode(ref_mode)
    start_refs = _dedupe_media_ref_urls(
        ref_image_url if isinstance(ref_image_url, list) else ([ref_image_url] if str(ref_image_url or "").strip() else [])
    )
    end_ref = str(last_frame_url or "").strip() or None

    info: Dict[str, Any] = {
        "normalized_mode": normalized_mode,
        "supports_last_frame_mode": supports_last_frame_mode,
        "fallback_to_refs": False,
        "start_count_before": len(start_refs),
        "had_last_frame_before": bool(end_ref),
    }

    if normalized_mode in {"entity_refs", "keyframes_entity_refs"}:
        info["start_count_after"] = len(start_refs)
        info["had_last_frame_after"] = False
        return (start_refs or None), None, info

    if normalized_mode == "end":
        if not end_ref and start_refs:
            end_ref = start_refs[-1]
        start_refs = []
    elif normalized_mode == "start_end":
        if not end_ref and len(start_refs) >= 2:
            end_ref = start_refs[-1]
        start_refs = start_refs[:1]
    elif normalized_mode == "start":
        start_refs = start_refs[:1]
        end_ref = None

    if end_ref and not supports_last_frame_mode:
        merged_refs = list(start_refs)
        if end_ref not in merged_refs:
            merged_refs.append(end_ref)
        start_refs = merged_refs
        end_ref = None
        info["fallback_to_refs"] = True

    normalized_ref_image_url: Optional[Union[str, List[str]]] = None
    if len(start_refs) == 1:
        normalized_ref_image_url = start_refs[0]
    elif start_refs:
        normalized_ref_image_url = start_refs

    info["start_count_after"] = len(start_refs)
    info["had_last_frame_after"] = bool(end_ref)
    return normalized_ref_image_url, end_ref, info


def _limit_keyframes_for_video_mode(keyframes: Optional[List[str]], ref_mode: Any) -> List[str]:
    normalized_mode = _normalize_video_ref_mode(ref_mode)
    normalized_keyframes = _dedupe_media_ref_urls(keyframes if isinstance(keyframes, list) else [])
    if normalized_mode == "keyframes_entity_refs":
        return normalized_keyframes[:1]
    return normalized_keyframes


def _collect_video_prompt_entity_refs(
    prompt_candidates: List[str],
    entity_lookup: Dict[str, Dict[str, Any]],
    *,
    strict: bool = True,
) -> List[str]:
    refs: List[str] = []
    collector = _collect_prompt_entity_ref_images if strict else _collect_prompt_entity_ref_images_relaxed
    for candidate_text in (prompt_candidates or []):
        if not str(candidate_text or "").strip():
            continue
        refs.extend(collector(candidate_text, entity_lookup))
    return _dedupe_media_ref_urls(refs)


def _is_video_media_ref_url(url: Any) -> bool:
    raw = str(url or "").strip()
    if not raw:
        return False
    path = raw.split("?", 1)[0].split("#", 1)[0].lower()
    return bool(re.search(r"\.(mp4|webm|mov|m4v|avi|mkv)$", path))


def _filter_image_media_ref_urls(urls: Optional[List[str]]) -> List[str]:
    return [
        str(url).strip()
        for url in _dedupe_media_ref_urls(urls if isinstance(urls, list) else [])
        if str(url or "").strip() and not _is_video_media_ref_url(url)
    ]


def _resolve_shot_video_panel_image_refs(
    shot: Any,
    tech: Dict[str, Any],
    entity_lookup: Dict[str, Dict[str, Any]],
) -> List[str]:
    """Image refs from the shot video Refs panel (frontend WYSIWYG source of truth)."""
    notes = tech if isinstance(tech, dict) else {}
    deleted = {str(x).strip() for x in (notes.get("deleted_ref_urls") or []) if str(x).strip()}
    video_manual = bool(notes.get("video_ref_image_urls_manual") or notes.get("video_ref_image_urls_user_edited"))

    if video_manual and isinstance(notes.get("video_ref_image_urls"), list):
        refs = [
            str(x).strip()
            for x in (notes.get("video_ref_image_urls") or [])
            if str(x).strip() and str(x).strip() not in deleted
        ]
        # Keep newly matched video-prompt entities unless explicitly deleted (frontend parity).
        prompt_candidates = [
            str(getattr(shot, "video_content", None) or "").strip(),
            str(notes.get("video_prompt_cn") or "").strip(),
            str(getattr(shot, "prompt", None) or "").strip(),
        ]
        for url in _collect_video_prompt_entity_refs(prompt_candidates, entity_lookup):
            if url and url not in deleted and url not in refs:
                refs.append(url)
        return _filter_image_media_ref_urls(refs)

    video_mode = _resolve_shot_video_mode(notes)
    prompt_candidates = [
        str(getattr(shot, "video_content", None) or "").strip(),
        str(notes.get("video_prompt_cn") or "").strip(),
        str(getattr(shot, "prompt", None) or "").strip(),
    ]
    entity_refs = _collect_video_prompt_entity_refs(prompt_candidates, entity_lookup)
    start_ref = str(getattr(shot, "image_url", None) or "").strip()
    end_ref = str(notes.get("end_frame_url") or "").strip()
    keyframes = _limit_keyframes_for_video_mode(notes.get("keyframes"), video_mode)

    if video_mode == "entity_refs":
        refs = list(entity_refs)
    elif video_mode == "entity_refs_start_end":
        refs = list(entity_refs)
        if start_ref:
            refs.append(start_ref)
        if end_ref:
            refs.append(end_ref)
    elif video_mode == "keyframes_entity_refs":
        refs = [*keyframes, *entity_refs]
        if not refs and start_ref:
            refs.append(start_ref)
    elif video_mode == "end":
        refs = [end_ref] if end_ref else []
    elif video_mode == "start_end":
        refs = []
        if start_ref:
            refs.append(start_ref)
        if end_ref:
            refs.append(end_ref)
    else:
        refs = [start_ref] if start_ref else []

    refs = [url for url in refs if url and url not in deleted]
    return _filter_image_media_ref_urls(refs)


def _resolve_default_shot_image_gen_refs(
    shot: Any,
    tech: Dict[str, Any],
    entity_lookup: Dict[str, Dict[str, Any]],
    *,
    panel: str = "start",
) -> List[str]:
    """Default start/end image-gen refs = video panel refs; panel lists only after user edit."""
    notes = tech if isinstance(tech, dict) else {}
    deleted = {str(x).strip() for x in (notes.get("deleted_ref_urls") or []) if str(x).strip()}
    storage_key = "end_ref_image_urls" if panel == "end" else "ref_image_urls"
    user_edited = bool(notes.get(f"{storage_key}_user_edited"))

    if user_edited and isinstance(notes.get(storage_key), list):
        refs = [
            str(x).strip()
            for x in (notes.get(storage_key) or [])
            if str(x).strip() and str(x).strip() not in deleted
        ]
    else:
        refs = _resolve_shot_video_panel_image_refs(shot, notes, entity_lookup)

    if panel == "end" and not user_edited:
        start_image = str(getattr(shot, "image_url", None) or "").strip()
        if start_image and start_image not in deleted and start_image not in refs:
            refs = [start_image, *refs]

    return _filter_image_media_ref_urls(refs)


def _merge_entity_refs_for_video_mode(
    base_refs: List[str],
    *,
    ref_mode: Any,
    prompt_candidates: List[str],
    entity_lookup: Dict[str, Dict[str, Any]],
    manual_override: bool = False,
    associated_entities: Optional[str] = None,
) -> Tuple[List[str], List[str]]:
    normalized_mode = _normalize_video_ref_mode(ref_mode)
    current_refs = _dedupe_media_ref_urls(base_refs)
    if normalized_mode not in {"entity_refs", "keyframes_entity_refs"} or manual_override:
        return current_refs, []

    auto_entity_refs: List[str] = []
    auto_entity_refs.extend(_collect_video_prompt_entity_refs(prompt_candidates, entity_lookup))
    auto_entity_refs = _dedupe_media_ref_urls(auto_entity_refs)

    if not auto_entity_refs:
        return current_refs, []

    if normalized_mode == "keyframes_entity_refs":
        return _dedupe_media_ref_urls([*current_refs, *auto_entity_refs]), auto_entity_refs

    # If entity_refs mode is selected, we ONLY return the entity refs and ignore the base_refs
    # to avoid mixing first frame/last frame/keyframes into the entity reference list sent to the provider.
    return _dedupe_media_ref_urls(auto_entity_refs), auto_entity_refs


def _prepend_keyframe_story_progression_instruction(prompt: Any, keyframe_ref_count: int, *, language: str = "en") -> str:
    base_prompt = str(prompt or "").strip()
    if keyframe_ref_count <= 0:
        return base_prompt

    ref_label = "参考@Image1"
    normalized_language = str(language or "en").strip().lower()
    if normalized_language.startswith("zh") or normalized_language.startswith("cn"):
        prefix = f"{ref_label} 的画面顺序生成视频。"
    else:
        prefix = f"Generate the video following the frame order of {ref_label}."

    if not base_prompt:
        return prefix
    return f"{prefix} {base_prompt}" if not prefix.endswith("。") else f"{prefix}{base_prompt}"

def _compute_subject_ref_index_map(prompt: str, entity_lookup: Dict[str, Dict[str, Any]]) -> Dict[str, int]:
    text = str(prompt or "")
    if not text:
        return {}

    refs: List[str] = []
    index_map: Dict[str, int] = {}
    raw_names = _extract_frontend_aligned_entity_raw_names(text)
    for raw_name in raw_names:
        normalized = _normalize_entity_anchor_token(raw_name)
        if not normalized:
            continue

        row = entity_lookup.get(normalized)
        if not row:
            continue

        entity_type = str(row.get("entity_type") or "").strip().lower() if row else ""
        if entity_type and entity_type not in {
            "subject",
            "character",
            "char",
            "environment",
            "env",
            "prop",
            "props",
        }:
            continue

        image_url = str(row.get("image_url") or "").strip()
        if not image_url:
            continue

        if image_url not in refs:
            refs.append(image_url)

        entity_id = str(row.get("entity_id") or "").strip()
        if entity_id:
            index_map[entity_id] = refs.index(image_url) + 1

    return index_map


def _normalize_media_ref_key(url: Any) -> str:
    text = str(url or "").strip()
    if not text:
        return ""
    return text.split("?")[0].rstrip("/")


def _media_ref_basename(url: Any) -> str:
    key = _normalize_media_ref_key(url)
    if not key:
        return ""
    return key.rsplit("/", 1)[-1].strip().lower()


def _lookup_entity_row_for_token(
    normalized: str,
    entity_lookup: Optional[Dict[str, Dict[str, Any]]],
) -> Optional[Dict[str, Any]]:
    if not normalized or not entity_lookup:
        return None
    for key in _entity_lookup_alias_keys(normalized):
        row = entity_lookup.get(key)
        if row:
            return row

    token_keys = subject_compare_key_variants(normalized)
    if not token_keys:
        return None
    for row in _iter_unique_entity_rows(entity_lookup):
        entity_keys = _entity_lookup_alias_keys(row.get("name"), row.get("name_en"))
        if entity_subject_keys_match(entity_keys, token_keys):
            return row
    return None


def _pick_submitted_ref_for_entity(
    *,
    entity_row: Dict[str, Any],
    available_refs: List[str],
    used_keys: set,
) -> str:
    """Bind a submitted ref URL to an entity by verifying image_url (name→URL audit)."""
    preferred = str((entity_row or {}).get("image_url") or "").strip()
    preferred_key = _normalize_media_ref_key(preferred)
    preferred_base = _media_ref_basename(preferred)
    if not preferred_key and not preferred_base:
        return ""

    for url in available_refs:
        key = _normalize_media_ref_key(url)
        if not key or key in used_keys:
            continue
        if preferred and (url == preferred or key == preferred_key):
            return url
        if preferred_base and _media_ref_basename(url) == preferred_base:
            return url
    return ""


def _iter_unique_entity_rows(
    entity_lookup: Optional[Dict[str, Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    seen_ids: set = set()
    for row in (entity_lookup or {}).values():
        if not isinstance(row, dict):
            continue
        entity_id = row.get("entity_id")
        dedupe_key = f"id:{entity_id}" if entity_id is not None else f"url:{_normalize_media_ref_key(row.get('image_url'))}:{row.get('name')}"
        if dedupe_key in seen_ids:
            continue
        seen_ids.add(dedupe_key)
        rows.append(row)
    return rows


def _build_url_to_entity_rows(
    entity_lookup: Optional[Dict[str, Dict[str, Any]]],
) -> Dict[str, Dict[str, Any]]:
    mapping: Dict[str, Dict[str, Any]] = {}
    for row in _iter_unique_entity_rows(entity_lookup):
        image_url = str(row.get("image_url") or "").strip()
        if not image_url:
            continue
        for key in (
            image_url,
            _normalize_media_ref_key(image_url),
            _media_ref_basename(image_url),
        ):
            if key and key not in mapping:
                mapping[key] = row
    return mapping


def _collect_prompt_entity_mentions_for_mapping(
    prompt: str,
    entity_lookup: Optional[Dict[str, Dict[str, Any]]],
    ordered_refs: Optional[List[str]] = None,
) -> Tuple[List[Tuple[str, str, Dict[str, Any]]], str]:
    """
    Collect (normalized, display_name, row) for @Image mapping.
    Prefer structured CHAR/ENV/PROP tokens; fall back to URL→entity reverse + name appearance.
    """
    allowed_types = {"subject", "character", "char", "environment", "env", "prop", "props"}
    text = str(prompt or "")
    mentions: List[Tuple[str, str, Dict[str, Any]]] = []
    seen_norms: set = set()
    seen_ids: set = set()

    def _append_mention(normalized: str, display_name: str, row: Dict[str, Any]) -> bool:
        if not normalized or not display_name or not isinstance(row, dict):
            return False
        entity_type = str(row.get("entity_type") or "").strip().lower()
        if entity_type and entity_type not in allowed_types:
            return False
        entity_id = row.get("entity_id")
        dedupe_key = f"id:{entity_id}" if entity_id is not None else f"name:{normalized}"
        if dedupe_key in seen_ids or normalized in seen_norms:
            return False
        seen_ids.add(dedupe_key)
        seen_norms.add(normalized)
        mentions.append((normalized, display_name, row))
        return True

    for raw_name in _extract_frontend_aligned_entity_raw_names(text):
        raw_name = str(raw_name or "").strip()
        normalized = _normalize_entity_anchor_token(raw_name)
        if not normalized:
            continue
        row = _lookup_entity_row_for_token(normalized, entity_lookup)
        if not row:
            continue
        display_name = raw_name.lstrip("@").strip() or str(row.get("name") or "").strip()
        _append_mention(normalized, display_name, row)

    mention_source = "structured" if mentions else "none"

    # Even when structured mentions exist, recover entities that the frontend already
    # put into image_urls but whose prompt token failed exact-name lookup.
    if entity_lookup and ordered_refs:
        url_map = _build_url_to_entity_rows(entity_lookup)
        reverse_hits: List[Tuple[int, int, str, str, Dict[str, Any]]] = []
        for ref_idx, url in enumerate(ordered_refs):
            row = (
                url_map.get(str(url or "").strip())
                or url_map.get(_normalize_media_ref_key(url))
                or url_map.get(_media_ref_basename(url))
            )
            if not row:
                continue
            entity_id = row.get("entity_id")
            dedupe_key = f"id:{entity_id}" if entity_id is not None else f"name:{row.get('name')}"
            if dedupe_key in seen_ids:
                continue
            display_name = str(row.get("name") or "").strip()
            normalized = _normalize_entity_anchor_token(display_name)
            if not display_name or not normalized:
                continue
            # Confirm the entity actually appears in the prompt (typed token or plain name).
            prompt_hit = False
            row_keys = _entity_lookup_alias_keys(row.get("name"), row.get("name_en"))
            for raw_name in _extract_frontend_aligned_entity_raw_names(text):
                raw_norm = _normalize_entity_anchor_token(raw_name)
                if not raw_norm:
                    continue
                if entity_subject_keys_match(row_keys, subject_compare_key_variants(raw_norm)) or raw_norm in row_keys:
                    prompt_hit = True
                    # Prefer the prompt-facing token for @Image injection regex.
                    display_name = str(raw_name or "").lstrip("@").strip() or display_name
                    normalized = raw_norm
                    break
            if not prompt_hit:
                if text.find(display_name) < 0 and text.lower().find(normalized) < 0:
                    continue
            pos = text.find(display_name)
            if pos < 0:
                pos = text.lower().find(normalized)
            if pos < 0:
                pos = 10**9 + ref_idx
            reverse_hits.append((pos, ref_idx, normalized, display_name, row))

        reverse_hits.sort(key=lambda item: (item[0], item[1]))
        recovered = 0
        for _pos, _ref_idx, norm, name, row in reverse_hits:
            if _append_mention(norm, name, row):
                recovered += 1
        if recovered:
            mention_source = "structured+url_reverse" if mention_source == "structured" else "url_reverse"

        # Keep prompt appearance order for structured names, then append recovered by prompt pos.
        if mention_source.startswith("structured") and recovered:
            # Re-sort all mentions by earliest prompt appearance for stable @Image indices.
            def _mention_pos(item: Tuple[str, str, Dict[str, Any]]) -> int:
                _norm, name, _row = item
                pos = text.find(name)
                if pos < 0:
                    pos = text.lower().find(_norm)
                return pos if pos >= 0 else 10**9

            mentions.sort(key=_mention_pos)

    return mentions, mention_source


def _reconcile_video_refs_by_entity_names(
    prompt: str,
    ordered_refs: List[str],
    entity_lookup: Optional[Dict[str, Dict[str, Any]]],
    *,
    preserve_submitted_refs: bool = False,
) -> Tuple[List[str], List[Tuple[int, str, str]], List[str]]:
    """
    Align image ref order to prompt entity mentions by entity name.

    Primary contract: @ImageN must refer to the N-th bound entity's image.
    Fallback audit uses entity.name → entity.image_url instead of blind index zip.
    Returns (aligned_refs, pairs[(1-based idx, display_name, anchor)], audit_notes).

    When preserve_submitted_refs=True (explicit UI / image_urls submit):
    - Keep submitted ref order and count as source of truth
    - Keep unpaired / user-added images as additional refs
    - Do not re-inject official entity images the panel omitted
    """
    refs = [str(x).strip() for x in (ordered_refs or []) if str(x).strip()]
    audit: List[str] = []
    if not refs:
        audit.append("skip:no_refs")
        return refs, [], audit
    if not entity_lookup:
        audit.append("skip:no_entity_lookup")
        if preserve_submitted_refs:
            pairs = [
                (idx, f"附加参考{idx}", "")
                for idx, _url in enumerate(refs, start=1)
            ]
            audit.append("preserve_submitted:no_lookup")
            return refs, pairs, audit
        return refs, [], audit

    mentions, mention_source = _collect_prompt_entity_mentions_for_mapping(
        prompt,
        entity_lookup,
        ordered_refs=refs,
    )
    audit.append(f"mention_source={mention_source}")
    audit.append(f"mentions={len(mentions)}")
    if preserve_submitted_refs:
        audit.append("preserve_submitted=1")

    if not mentions and not preserve_submitted_refs:
        sample_keys = list(entity_lookup.keys())[:6]
        audit.append(f"skip:no_mentions lookup_keys_sample={sample_keys}")
        return refs, [], audit

    used_keys: set = set()
    bound: List[Tuple[str, str, str]] = []
    unbound: List[Tuple[str, Dict[str, Any]]] = []
    bound_by_key: Dict[str, Tuple[str, str]] = {}
    for _norm, display_name, row in mentions:
        matched_url = _pick_submitted_ref_for_entity(
            entity_row=row,
            available_refs=refs,
            used_keys=used_keys,
        )
        if not matched_url:
            unbound.append((display_name, row))
            continue
        key = _normalize_media_ref_key(matched_url)
        if not key or key in used_keys:
            unbound.append((display_name, row))
            continue
        used_keys.add(key)
        chosen = matched_url
        for url in refs:
            if _normalize_media_ref_key(url) == key or _media_ref_basename(url) == _media_ref_basename(matched_url):
                chosen = url
                break
        anchor = str(row.get("anchor_description") or "").strip()
        bound.append((chosen, display_name, anchor))
        bound_by_key[key] = (display_name, anchor)

    if preserve_submitted_refs:
        # Panel / explicit image_urls win: never drop extras, never resurrect omitted official refs.
        for display_name, _row in unbound:
            audit.append(f"omitted_by_panel:{display_name}")

        url_map = _build_url_to_entity_rows(entity_lookup)
        pairs: List[Tuple[int, str, str]] = []
        extra_count = 0
        for idx, url in enumerate(refs, start=1):
            key = _normalize_media_ref_key(url)
            if key and key in bound_by_key:
                display_name, anchor = bound_by_key[key]
                pairs.append((idx, display_name, anchor))
                continue
            row = (
                url_map.get(str(url or "").strip())
                or url_map.get(key)
                or url_map.get(_media_ref_basename(url))
            )
            if isinstance(row, dict):
                display_name = str(row.get("name") or row.get("name_en") or "").strip() or f"附加参考{idx}"
                anchor = str(row.get("anchor_description") or "").strip()
                pairs.append((idx, display_name, anchor))
                continue
            extra_count += 1
            pairs.append((idx, f"附加参考{idx}", ""))

        if extra_count:
            audit.append(f"kept_additional_refs={extra_count}")
        audit.append(f"bound={len(bound_by_key)}")
        audit.append(f"preserved_count={len(refs)}")
        return refs, pairs, audit

    # Name fallback: inject official entity image when submitted list missed it.
    # Never blind-zip leftover URLs to leftover names (that caused Image1↔Image3 swaps).
    for display_name, row in unbound:
        preferred = str((row or {}).get("image_url") or "").strip()
        preferred_key = _normalize_media_ref_key(preferred)
        if not preferred or not preferred_key or preferred_key in used_keys:
            audit.append(f"missing_image:{display_name}")
            continue
        used_keys.add(preferred_key)
        anchor = str(row.get("anchor_description") or "").strip()
        bound.append((preferred, display_name, anchor))
        audit.append(f"injected_official_ref:{display_name}")

    aligned = [url for url, _, _ in bound]
    if bound:
        bound_keys = {_normalize_media_ref_key(u) for u in aligned if _normalize_media_ref_key(u)}
        dropped = 0
        for url in refs:
            key = _normalize_media_ref_key(url)
            if key and key not in bound_keys:
                # Keep user-added / unpaired images as trailing additional refs.
                aligned.append(url)
                bound.append((url, f"附加参考{len(bound) + 1}", ""))
                dropped += 1
        if dropped:
            audit.append(f"kept_unpaired_refs={dropped}")
    else:
        aligned = list(refs)

    pairs = [(idx, name, anchor) for idx, (_url, name, anchor) in enumerate(bound, start=1)]
    audit.append(f"bound={len(bound)}")
    if [_normalize_media_ref_key(u) for u in aligned] != [_normalize_media_ref_key(u) for u in refs]:
        after_names = [name for _, name, _ in bound]
        after_preview = ",".join(after_names[:8])
        audit.append(f"reordered:after_names=[{after_preview}]")
    return aligned, pairs, audit


def _sync_request_image_refs_with_aligned(
    *,
    aligned_refs: List[str],
    image_urls: Optional[List[str]],
    ref_image_url: Optional[Union[str, List[str]]],
    last_frame_url: Optional[str],
    keyframes: Optional[List[str]],
) -> Tuple[Optional[List[str]], Optional[Union[str, List[str]]]]:
    """Keep provider image_urls / ref_image_url in the same order as @ImageN tags."""
    exclude_keys = set()
    for url in (keyframes or []):
        key = _normalize_media_ref_key(url)
        if key:
            exclude_keys.add(key)
    last_key = _normalize_media_ref_key(last_frame_url)
    if last_key:
        exclude_keys.add(last_key)

    synced = [
        str(url).strip()
        for url in (aligned_refs or [])
        if str(url).strip() and _normalize_media_ref_key(url) not in exclude_keys
    ]

    if isinstance(image_urls, list) and image_urls:
        return synced, ref_image_url

    if isinstance(ref_image_url, list):
        return image_urls, synced if synced else ref_image_url
    if isinstance(ref_image_url, str) and ref_image_url.strip():
        if not synced:
            return image_urls, None
        if len(synced) == 1:
            return image_urls, synced[0]
        return image_urls, synced
    return image_urls, ref_image_url


def _resolve_video_project_id_from_payload(db: Session, payload: Dict[str, Any]) -> Optional[int]:
    resolved = _to_positive_int_or_none(payload.get("project_id"))
    if resolved:
        return resolved
    shot_id = _to_positive_int_or_none(payload.get("shot_id"))
    if not shot_id:
        return None
    submit_shot = db.query(Shot).filter(Shot.id == int(shot_id)).first()
    if not submit_shot:
        return None
    resolved = _to_positive_int_or_none(getattr(submit_shot, "project_id", None))
    if resolved:
        return resolved
    episode_id = _to_positive_int_or_none(getattr(submit_shot, "episode_id", None))
    if not episode_id:
        return None
    submit_episode = db.query(Episode).filter(Episode.id == int(episode_id)).first()
    if submit_episode:
        return _to_positive_int_or_none(getattr(submit_episode, "project_id", None))
    return None


def _collect_video_flat_refs_from_payload(payload: Dict[str, Any]) -> List[str]:
    refs: List[str] = []
    image_urls = payload.get("image_urls")
    if isinstance(image_urls, list):
        refs.extend([str(x).strip() for x in image_urls if str(x).strip()])
    ref_image_url = payload.get("ref_image_url")
    if isinstance(ref_image_url, list):
        refs.extend([str(x).strip() for x in ref_image_url if str(x).strip()])
    elif isinstance(ref_image_url, str) and ref_image_url.strip():
        refs.append(ref_image_url.strip())
    keyframes = payload.get("keyframes")
    if isinstance(keyframes, list):
        refs.extend([str(x).strip() for x in keyframes if str(x).strip()])
    last_frame_url = payload.get("last_frame_url")
    if isinstance(last_frame_url, str) and last_frame_url.strip():
        refs.append(last_frame_url.strip())
    return [x for x in dict.fromkeys([str(x).strip() for x in refs if str(x).strip()]) if x]


def _preprocess_video_submit_payload(
    db: Session,
    req_payload: Dict[str, Any],
    *,
    provider: str = "",
    model: str = "",
) -> Dict[str, Any]:
    """Align queued video job payload with runtime entity-ref merge + @Image mapping."""
    submit_prompt = str(req_payload.get("prompt") or "").strip()
    if not submit_prompt:
        return req_payload

    normalized_ref_mode = _normalize_video_ref_mode(req_payload.get("ref_mode"))
    is_reference_image_mode = normalized_ref_mode in {"entity_refs", "keyframes_entity_refs"}
    submit_image_urls = _resolve_video_submit_image_urls(SimpleNamespace(**req_payload))
    uses_submit_image_urls = bool(submit_image_urls)

    submit_ref_image_url = req_payload.get("ref_image_url")
    submit_last_frame_url = req_payload.get("last_frame_url")
    submit_keyframes = req_payload.get("keyframes") if isinstance(req_payload.get("keyframes"), list) else None
    submit_ref_video_urls = req_payload.get("ref_video_urls") if isinstance(req_payload.get("ref_video_urls"), list) else None

    flat_refs = _collect_video_flat_refs_from_payload(req_payload)
    resolved_project_id = _resolve_video_project_id_from_payload(db, req_payload)
    entity_lookup: Dict[str, Dict[str, Any]] = {}
    resolved_episode_id = _to_positive_int_or_none(req_payload.get("episode_id"))
    shot_id_for_episode = _to_positive_int_or_none(req_payload.get("shot_id"))
    if not resolved_episode_id and shot_id_for_episode:
        shot_for_episode = db.query(Shot).filter(Shot.id == int(shot_id_for_episode)).first()
        resolved_episode_id = _to_positive_int_or_none(getattr(shot_for_episode, "episode_id", None)) if shot_for_episode else None

    has_explicit_visual_refs = uses_submit_image_urls
    if not has_explicit_visual_refs and isinstance(submit_ref_image_url, list):
        has_explicit_visual_refs = any(str(x).strip() for x in submit_ref_image_url)
    elif not has_explicit_visual_refs and isinstance(submit_ref_image_url, str) and submit_ref_image_url.strip():
        has_explicit_visual_refs = True

    if is_reference_image_mode and resolved_project_id and not uses_submit_image_urls:
        entity_lookup = _build_project_entity_lookup(
            db, int(resolved_project_id), episode_id=resolved_episode_id
        )
        prompt_candidates: List[str] = [submit_prompt]
        shot_for_ref: Optional[Shot] = None
        shot_id = _to_positive_int_or_none(req_payload.get("shot_id"))
        if shot_id:
            shot_for_ref = db.query(Shot).filter(Shot.id == int(shot_id)).first()
        if shot_for_ref:
            prompt_candidates.extend([
                str(shot_for_ref.video_content or "").strip(),
                str(shot_for_ref.prompt or "").strip(),
            ])
            shot_tech = _parse_shot_tech(shot_for_ref)
            if isinstance(shot_tech, dict):
                prompt_candidates.append(str(shot_tech.get("video_prompt_cn") or "").strip())

        existing_start_refs: List[str] = []
        if isinstance(submit_ref_image_url, list):
            existing_start_refs = [str(x).strip() for x in submit_ref_image_url if str(x).strip()]
        elif isinstance(submit_ref_image_url, str) and submit_ref_image_url.strip():
            existing_start_refs = [submit_ref_image_url.strip()]

        merged_refs, auto_entity_refs = _merge_entity_refs_for_video_mode(
            existing_start_refs,
            ref_mode=normalized_ref_mode,
            prompt_candidates=prompt_candidates,
            entity_lookup=entity_lookup,
            manual_override=has_explicit_visual_refs,
            associated_entities=shot_for_ref.associated_entities if shot_for_ref else None,
        )
        if merged_refs:
            flat_refs = merged_refs
            submit_ref_image_url = merged_refs
            req_payload["ref_image_url"] = merged_refs
        if auto_entity_refs:
            logger.info(
                "[VideoSubmit] merged entity refs | shot_id=%s project_id=%s ref_mode=%s explicit_refs=%s detected=%s final_refs=%s",
                req_payload.get("shot_id"),
                resolved_project_id,
                normalized_ref_mode or "list_ref",
                has_explicit_visual_refs,
                len(auto_entity_refs),
                len(merged_refs or []),
            )
    elif is_reference_image_mode and resolved_project_id:
        entity_lookup = _build_project_entity_lookup(
            db, int(resolved_project_id), episode_id=resolved_episode_id
        )

    logger.info(
        "[VideoSubmit] prompt mapping prepare | shot_id=%s ref_mode=%s refs=%s project_id=%s lookup_keys=%s",
        req_payload.get("shot_id"),
        normalized_ref_mode or "<empty>",
        len(flat_refs),
        resolved_project_id,
        len(entity_lookup or {}),
    )

    mapped_prompt, flat_refs = _append_video_api_ref_mapping(
        submit_prompt,
        flat_refs,
        submit_ref_image_url,
        submit_last_frame_url,
        submit_keyframes,
        submit_ref_video_urls,
        entity_lookup=entity_lookup if is_reference_image_mode else None,
        use_prev_video=bool(req_payload.get("use_prev_video")),
        provider=provider,
        model=model,
        preserve_submitted_refs=bool(uses_submit_image_urls or has_explicit_visual_refs),
    )
    req_payload["prompt"] = mapped_prompt

    synced_image_urls, synced_ref_image_url = _sync_request_image_refs_with_aligned(
        aligned_refs=flat_refs,
        image_urls=req_payload.get("image_urls") if uses_submit_image_urls else None,
        ref_image_url=submit_ref_image_url if not uses_submit_image_urls else None,
        last_frame_url=submit_last_frame_url,
        keyframes=submit_keyframes,
    )
    if isinstance(synced_image_urls, list) and synced_image_urls:
        req_payload["image_urls"] = synced_image_urls
    elif synced_ref_image_url is not None:
        req_payload["ref_image_url"] = synced_ref_image_url
        req_payload.pop("image_urls", None)
    elif is_reference_image_mode and flat_refs:
        req_payload["image_urls"] = flat_refs
        req_payload["ref_image_url"] = flat_refs if len(flat_refs) != 1 else flat_refs[0]
    elif not uses_submit_image_urls:
        req_payload.pop("image_urls", None)

    image_tag_count = len(re.findall(r"@Image\d+", str(mapped_prompt or ""), flags=re.IGNORECASE))
    logger.info(
        "[VideoSubmit] prompt mapping done | shot_id=%s ref_mode=%s refs=%s lookup=%s image_tags=%s prompt_len=%s",
        req_payload.get("shot_id"),
        normalized_ref_mode or "<empty>",
        len(flat_refs),
        len(entity_lookup or {}),
        image_tag_count,
        len(str(mapped_prompt or "")),
    )

    if isinstance(req_payload.get("multi_prompt"), list):
        patched_multi_prompt: List[Dict[str, Any]] = []
        for item in req_payload.get("multi_prompt") or []:
            if not isinstance(item, dict):
                continue
            patched_item = dict(item)
            item_prompt = str(patched_item.get("prompt") or "").strip()
            if item_prompt:
                patched_item["prompt"], _ = _append_video_api_ref_mapping(
                    item_prompt,
                    flat_refs,
                    req_payload.get("ref_image_url"),
                    submit_last_frame_url,
                    submit_keyframes,
                    submit_ref_video_urls,
                    entity_lookup=entity_lookup if is_reference_image_mode else None,
                    use_prev_video=bool(req_payload.get("use_prev_video")),
                    provider=provider,
                    model=model,
                    preserve_submitted_refs=bool(uses_submit_image_urls or has_explicit_visual_refs),
                )
            patched_multi_prompt.append(patched_item)
        req_payload["multi_prompt"] = patched_multi_prompt

    return req_payload


def _append_video_api_ref_mapping(
    prompt: str,
    refs: List[str],
    ref_image_url: Optional[Union[str, List[str]]],
    last_frame_url: Optional[str],
    keyframes: Optional[List[str]] = None,
    reference_video_urls: Optional[List[str]] = None,
    entity_lookup: Optional[Dict[str, Dict[str, Any]]] = None,
    use_prev_video: bool = False,
    provider: str = "",
    model: str = "",
    preserve_submitted_refs: bool = False,
) -> Tuple[str, List[str]]:
    is_seedance = "seedance" in str(provider or "").lower() or "seedance" in str(model or "").lower()
    original_use_prev_video = use_prev_video
    if is_seedance:
        use_prev_video = True

    original_text = str(prompt or "").strip()
    ordered_refs = [str(x).strip() for x in (refs or []) if str(x).strip()]
    if not original_text:
        logger.info(
            "[_append_video_api_ref_mapping] skip empty prompt | refs=%s lookup=%s",
            len(ordered_refs),
            len(entity_lookup or {}),
        )
        return original_text, ordered_refs

    # Working copy: strip prior markers only when we successfully rebuild pairs.
    text = original_text
    text = re.sub(r"(?:参考)?@Image\d+\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(
        r"\(\s*ref_image_url\s*:\s*#\d+\s*\)",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\|\s*ref_image_url\s*:\s*#\d+",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"^\s*API\s+ref\s+mapping\s*:\s*.*$",
        "",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    text = re.sub(
        r"^\s*实体参考映射\s*:\s*.*$",
        "",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    text = re.sub(
        r"^\s*实体参考图映射\s*:\s*.*$",
        "",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    if not ordered_refs and not isinstance(reference_video_urls, list):
        logger.info("[_append_video_api_ref_mapping] skip no refs/videos | prompt_len=%s", len(original_text))
        return original_text, ordered_refs

    aligned_refs, pairs, audit_notes = _reconcile_video_refs_by_entity_names(
        text,
        ordered_refs,
        entity_lookup,
        preserve_submitted_refs=preserve_submitted_refs,
    )
    logger.info(
        "[_append_video_api_ref_mapping] reconcile | refs_in=%s refs_out=%s pairs=%s lookup=%s preserve=%s audit=%s",
        len(ordered_refs),
        len(aligned_refs),
        len(pairs),
        len(entity_lookup or {}),
        int(bool(preserve_submitted_refs)),
        "; ".join(audit_notes) if audit_notes else "-",
    )
    ordered_refs = aligned_refs

    def _append_reference_video_instruction(source_text: str) -> str:
        updated_source = str(source_text or "").strip()
        if not updated_source:
            return updated_source
        if not (reference_video_urls and is_seedance):
            return updated_source

        if original_use_prev_video:
            vid_tag = "@Video 1"
            vid_tag_nospace = "@Video1"
            has_continuation_instruction = bool(
                re.search(r"延长\s*@?Video\s*1", updated_source, flags=re.IGNORECASE)
                or re.search(r"延长\s*视频\s*@?Video\s*1", updated_source, flags=re.IGNORECASE)
            )
            if not has_continuation_instruction:
                updated_source = f"延长{vid_tag_nospace}，一镜到底，要参考视频的角色站位建置运镜。\n\n{updated_source.strip()}"

        added_videos = False
        for idx in range(1, len(reference_video_urls) + 1):
            vid_tag = f"@Video {idx}"
            vid_tag_nospace = f"@Video{idx}"
            if vid_tag not in updated_source and vid_tag_nospace not in updated_source:
                if not added_videos:
                    updated_source = f"{updated_source.strip()}，参考视频是 {vid_tag}"
                    added_videos = True
                else:
                    updated_source = f"{updated_source.strip()} {vid_tag}"

        return updated_source

    if not pairs:
        # Critical: do NOT return the stripped working copy — that wiped @Image tags
        # when name reconcile failed (some scenes ended with zero injection).
        logger.warning(
            "[_append_video_api_ref_mapping] no pairs; preserve original prompt markers | refs=%s audit=%s",
            len(ordered_refs),
            "; ".join(audit_notes) if audit_notes else "-",
        )
        return _append_reference_video_instruction(original_text), ordered_refs

    updated_text = text
    injected = 0
    failed_names: List[str] = []
    for mapped_idx, entity_name, anchor_text in pairs:
        prefix = f"参考@Image{mapped_idx} "
        name_candidates: List[str] = []
        for candidate in (
            entity_name,
            str(entity_name or "").split("(")[0].strip(),
            _normalize_entity_anchor_token(entity_name),
        ):
            text_candidate = str(candidate or "").strip().lstrip("@").strip()
            if text_candidate and text_candidate not in name_candidates:
                name_candidates.append(text_candidate)

        replaced = False
        for name_candidate in name_candidates:
            escaped_entity = re.escape(name_candidate)
            anchor_patterns = [
                rf"(?<![a-zA-Z0-9_])(?:(?:参考)?@Image\d+\s*)*(?:(?:CHAR|ENV|PROP)\s*:\s*)?(?:(?:参考)?@Image\d+\s*)*[\[【]\s*@?{escaped_entity}\s*[\]】](?:\([^\)]*\))?",
                rf"(?<![a-zA-Z0-9_])(?:(?:参考)?@Image\d+\s*)*[\[【]\s*(?:CHAR|ENV|PROP)\s*:\s*(?:(?:参考)?@Image\d+\s*)*@?{escaped_entity}\s*[\]】](?:\([^\)]*\))?",
                rf"(?<![a-zA-Z0-9_])(?:(?:参考)?@Image\d+\s*)*[\{{｛]\s*(?:(?:参考)?@Image\d+\s*)*@?{escaped_entity}\s*[\}}｝](?:\([^\)]*\))?",
                rf"(?<![a-zA-Z0-9_])(?:(?:参考)?@Image\d+\s*)*(@{escaped_entity})(?:\([^\)]*\))?",
            ]

            for pattern in anchor_patterns:
                def _prepend_prefix(match: re.Match[str], _prefix=prefix, _anchor=anchor_text) -> str:
                    token = str(match.group(0) or "")
                    base = re.sub(r"(?:参考)?@Image\d+\s*", "", token, flags=re.IGNORECASE)
                    if _anchor:
                        if "(" in base and ")" in base:
                            base = re.sub(r"\([^\)]*\)", f"({_anchor})", base)
                        else:
                            base = f"{base}({_anchor})"
                    else:
                        base = re.sub(r"\([^\)]*\)", "", base)
                    return f"{_prefix}{base}"

                replaced_text, count = re.subn(pattern, _prepend_prefix, updated_text, flags=re.IGNORECASE)
                if count > 0:
                    updated_text = replaced_text
                    replaced = True
                    injected += 1
                    break
            if replaced:
                break

            plain_pattern = rf'(?<![a-zA-Z0-9_])(?:(?:参考)?@Image\d+\s*)*{escaped_entity}(?![a-zA-Z0-9_])'

            def _prepend_marker(match: re.Match[str], _prefix=prefix, _anchor=anchor_text) -> str:
                token = str(match.group(0) or "")
                base = re.sub(r"(?:参考)?@Image\d+\s*", "", token, flags=re.IGNORECASE)
                if _anchor:
                    if "(" in base and ")" in base:
                        base = re.sub(r"\([^\)]*\)", f"({_anchor})", base)
                    else:
                        base = f"{base}({_anchor})"
                else:
                    base = re.sub(r"\([^\)]*\)", "", base)
                return f"{_prefix}{base}"

            replaced_text, count = re.subn(plain_pattern, _prepend_marker, updated_text, flags=re.IGNORECASE)
            if count > 0:
                updated_text = replaced_text
                replaced = True
                injected += 1
                break

        if not replaced:
            failed_names.append(f"{entity_name}->Image{mapped_idx}")

    if failed_names:
        logger.warning(
            "[_append_video_api_ref_mapping] inject pattern miss | failed=%s",
            ",".join(failed_names[:12]),
        )

    # When prompt has no CHAR/ENV/PROP tokens (or names only appear as plain text
    # that regex missed), still emit an explicit ImageN↔name map so the provider
    # can bind refs. Prefer in-prompt injection; mapping line is last resort.
    # Also append for partial misses so a single failed character (e.g. 小宝) is not silently dropped.
    if (injected <= 0 and pairs) or failed_names:
        mapping_pairs = pairs if injected <= 0 else [
            (idx, name, anchor)
            for idx, name, anchor in pairs
            if any(f"{name}->Image{idx}" == failed for failed in failed_names)
        ]
        if mapping_pairs:
            mapping_line = "实体参考图映射: " + "; ".join(
                f"@Image{idx}={name}" for idx, name, _anchor in mapping_pairs
            )
            updated_text = f"{updated_text.strip()}\n\n{mapping_line}".strip()
            if injected <= 0:
                injected = len(pairs)
            else:
                injected += len(mapping_pairs)
            logger.info(
                "[_append_video_api_ref_mapping] appended explicit mapping line | pairs=%s",
                len(mapping_pairs),
            )

    logger.info(
        "[_append_video_api_ref_mapping] injected | pairs=%s applied=%s failed=%s sample=%s",
        len(pairs),
        injected,
        len(failed_names),
        ",".join(f"Image{idx}:{name}" for idx, name, _ in pairs[:6]),
    )

    # If nothing could be written into the prompt, keep original markers.
    if injected <= 0:
        logger.warning(
            "[_append_video_api_ref_mapping] zero applied; preserve original prompt | pairs=%s",
            len(pairs),
        )
        return _append_reference_video_instruction(original_text), ordered_refs

    return _append_reference_video_instruction(updated_text), ordered_refs


def _find_previous_shot_end_frame_url(db: Session, episode_id: int, shot_id: int) -> Optional[str]:
    prev_shot = (
        db.query(Shot)
        .filter(Shot.episode_id == episode_id, Shot.id < shot_id)
        .order_by(Shot.id.desc())
        .first()
    )
    if not prev_shot:
        return None
    prev_tech = _parse_shot_tech(prev_shot)
    prev_end = str(prev_tech.get("end_frame_url") or "").strip()
    return prev_end or None


def _make_public_upload_url_for_provider(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if re.match(r"^https?://", raw, flags=re.IGNORECASE):
        return raw
    upload_suffix = ""
    if raw.startswith("/uploads/"):
        upload_suffix = raw
    elif "/uploads/" in raw:
        upload_suffix = raw[raw.index("/uploads/"):]
    if not upload_suffix:
        return raw
    public_base = str(
        os.getenv("AISTORY_PUBLIC_BASE_URL")
        or os.getenv("PUBLIC_BASE_URL")
        or os.getenv("RENDER_EXTERNAL_URL")
        or getattr(settings, "RENDER_EXTERNAL_URL", "")
        or os.getenv("RAILWAY_STATIC_URL")
        or ""
    ).strip().rstrip("/")
    if not public_base:
        frontend_base = str(
            os.getenv("AISTORY_FRONTEND_BASE_URL")
            or os.getenv("FRONTEND_BASE_URL")
            or getattr(settings, "FRONTEND_BASE_URL", "")
            or ""
        ).strip()
        match = re.match(r"^https?://[^/]+", frontend_base, flags=re.IGNORECASE)
        if match:
            public_base = match.group(0).replace("-frontend.", "-backend.").replace("frontend.onrender.com", "backend.onrender.com")
    if not public_base:
        return raw
    if not re.match(r"^https?://", public_base, flags=re.IGNORECASE):
        public_base = f"https://{public_base}"
    return f"{public_base.rstrip('/')}{upload_suffix}"


def _find_previous_shot_video_url(db: Session, episode_id: int, shot_id: int) -> Optional[str]:
    prev_shot = (
        db.query(Shot)
        .filter(Shot.episode_id == episode_id, Shot.id < shot_id, Shot.video_url.isnot(None), Shot.video_url != "")
        .order_by(Shot.id.desc())
        .first()
    )
    if not prev_shot:
        return None
    prev_video = str(prev_shot.video_url or "").strip()
    return _make_public_upload_url_for_provider(prev_video) or None


def _run_shot_media_video_batch_item(episode_id: int, shot_id: int, user_id: int, overwrite_existing: bool = False, system_api_id: Optional[int] = None, use_prev_video: bool = False) -> Dict[str, Any]:
    item_db = SessionLocal()
    cancel_event = _get_shot_media_batch_cancel_event(int(episode_id), create=True)

    class _BatchStopRequested(Exception):
        pass

    async def _run_cancellable(coro: Any) -> Any:
        task = asyncio.create_task(coro)
        try:
            while True:
                done, _ = await asyncio.wait({task}, timeout=0.5)
                if task in done:
                    return await task
                if cancel_event and cancel_event.is_set():
                    task.cancel()
                    try:
                        await task
                    except BaseException:
                        pass
                    raise _BatchStopRequested("Stop requested")
        finally:
            if not task.done():
                task.cancel()

    async def _run_stage_with_retry(coro_factory: Any, max_attempts: int = 3) -> Any:
        last_error: Optional[Exception] = None
        for attempt in range(1, max(2, max_attempts + 1)):
            if cancel_event and cancel_event.is_set():
                raise _BatchStopRequested("Stop requested")
            try:
                return await _run_cancellable(coro_factory())
            except _BatchStopRequested:
                raise
            except Exception as exc:
                last_error = exc
                try:
                    item_db.rollback()
                except Exception:
                    pass
                if attempt < max_attempts:
                    logger.warning(
                        "[shot_media_batch] video stage retry | shot_id=%s attempt=%s/%s error=%s",
                        shot_id,
                        attempt,
                        max_attempts,
                        exc,
                    )
                    await asyncio.sleep(min(4, attempt))
                    continue
        raise Exception(f"video failed after {max_attempts} attempts: {last_error}")

    try:
        episode = item_db.query(Episode).filter(Episode.id == episode_id).first()
        user = item_db.query(User).filter(User.id == user_id).first()
        shot = item_db.query(Shot).filter(Shot.id == shot_id, Shot.episode_id == episode_id).first()
        if not episode or not user or not shot:
            raise Exception("Shot batch item not found")
        user_principal = _snapshot_user_principal(user)

        shot_label = str(shot.shot_id or shot.shot_name or f"#{shot.id}")
        tech = _parse_shot_tech(shot)
        start_frame_url = str(shot.image_url or "").strip()
        end_frame_url = str(tech.get("end_frame_url") or "").strip()
        video_url = str(shot.video_url or "").strip()

        if not overwrite_existing and video_url:
            return {
                "shot_id": int(shot.id),
                "shot_label": shot_label,
                "ok": True,
                "skipped": True,
                "skip_reason": "existing_video",
            }
        if not start_frame_url and not end_frame_url:
            return {
                "shot_id": int(shot.id),
                "shot_label": shot_label,
                "ok": True,
                "skipped": True,
                "skip_reason": "missing_frames",
            }

        episode_info = _episode_info_from_episode(episode)
        e_global_info = episode_info.get("e_global_info", {}) if isinstance(episode_info, dict) else {}
        global_style = str((e_global_info or {}).get("Global_Style") or "").strip()
        entity_lookup = _build_project_entity_lookup(
            item_db, int(episode.project_id), episode_id=int(episode_id)
        )

        video_prompt_raw = str(shot.video_content or shot.prompt or "").strip() or "Video motion"
        video_ref_index_map = _compute_subject_ref_index_map(video_prompt_raw, entity_lookup)
        logger.info(
            "[shot_media_batch] subject_ref_index_map asset=video shot_id=%s shot_label=%s map=%s",
            shot.id,
            shot_label,
            video_ref_index_map,
        )
        video_prompt = _inject_shot_prompt_anchors(video_prompt_raw, entity_lookup, global_style, video_ref_index_map)

        video_mode = _resolve_shot_video_mode(tech)
        refs: List[str] = []
        explicit_last_frame_url = end_frame_url or None
        video_prompt_candidates: List[str] = [
            str(video_prompt_raw or "").strip(),
            str(tech.get("video_prompt_cn") or "").strip(),
        ]
        if isinstance(tech.get("video_ref_image_urls"), list):
            refs.extend([str(x).strip() for x in tech.get("video_ref_image_urls") or [] if str(x).strip()])
        else:
            shot_mode = str(video_mode or "").strip().lower()
            if not shot_mode:
                shot_mode = DEFAULT_SHOT_VIDEO_MODE

            if shot_mode == "end":
                if end_frame_url:
                    explicit_last_frame_url = end_frame_url
            else:
                if start_frame_url:
                    refs.append(start_frame_url)

                if shot_mode in {"entity_refs", "keyframes_entity_refs"}:
                    keyframes = _limit_keyframes_for_video_mode(tech.get("keyframes"), shot_mode)
                    refs.extend(keyframes)

                if shot_mode == "start_end" and end_frame_url:
                    explicit_last_frame_url = end_frame_url

        preserve_panel_video_refs = isinstance(tech.get("video_ref_image_urls"), list) and bool(tech.get("video_ref_image_urls"))
        refs, auto_entity_refs = _merge_entity_refs_for_video_mode(
            refs,
            ref_mode=video_mode,
            prompt_candidates=video_prompt_candidates,
            entity_lookup=entity_lookup,
            manual_override=preserve_panel_video_refs,
            associated_entities=shot.associated_entities,
        )

        normalized_refs, normalized_last_frame_url, batch_ref_info = _normalize_video_request_refs(
            refs or None,
            explicit_last_frame_url,
            video_mode,
            supports_last_frame_mode=True,
        )

        ordered_video_refs: List[str] = []
        if isinstance(normalized_refs, list):
            ordered_video_refs.extend([str(x).strip() for x in normalized_refs if str(x).strip()])
        elif str(normalized_refs or "").strip():
            ordered_video_refs.append(str(normalized_refs).strip())
        if str(normalized_last_frame_url or "").strip():
            ordered_video_refs.append(str(normalized_last_frame_url).strip())
        ordered_video_refs = [x for x in dict.fromkeys(ordered_video_refs) if x]

        keyframe_priority_refs: List[str] = []
        if video_mode == "keyframes_entity_refs":
            keyframe_priority_refs = _limit_keyframes_for_video_mode(tech.get("keyframes"), video_mode)
            if keyframe_priority_refs:
                ordered_video_refs = [
                    *keyframe_priority_refs,
                    *[ref for ref in ordered_video_refs if ref not in keyframe_priority_refs],
                ]

        system_api_id_val = system_api_id
        if not system_api_id_val and getattr(episode, "system_api_id", None):
            system_api_id_val = episode.system_api_id
            
        is_seedance_batch = False
        if system_api_id_val:
            pre_api_row = get_system_api_setting(item_db, setting_id=int(system_api_id_val))
            pre_api_cfg = {
                "provider": str(getattr(pre_api_row, "provider", "") or "").strip(),
                "model": str(getattr(pre_api_row, "model", "") or "").strip(),
            }
            if "seedance" in str(pre_api_cfg.get("provider") or "").lower() or "seedance" in str(pre_api_cfg.get("model") or "").lower():
                is_seedance_batch = True

        reference_video_urls: List[str] = []
        if use_prev_video:
            prev_video_url = _find_previous_shot_video_url(item_db, episode_id, int(shot.id))
            if prev_video_url:
                reference_video_urls.append(prev_video_url)

        video_prompt, ordered_video_refs = _append_video_api_ref_mapping(
            video_prompt,
            ordered_video_refs,
            normalized_refs,
            normalized_last_frame_url,
            None,
            reference_video_urls,
            provider="seedance" if is_seedance_batch else None,
            model=str(pre_api_cfg.get("model") or "") if getattr(locals(), "pre_api_cfg", None) else "",
            entity_lookup=entity_lookup,
            use_prev_video=bool(use_prev_video),
            preserve_submitted_refs=preserve_panel_video_refs,
        )
        _, normalized_refs = _sync_request_image_refs_with_aligned(
            aligned_refs=ordered_video_refs,
            image_urls=None,
            ref_image_url=normalized_refs,
            last_frame_url=normalized_last_frame_url,
            keyframes=keyframe_priority_refs if video_mode == "keyframes_entity_refs" else None,
        )
        if video_mode == "keyframes_entity_refs":
            keyframe_ref_count = 1 if keyframe_priority_refs else 0
            video_prompt = _prepend_keyframe_story_progression_instruction(video_prompt, keyframe_ref_count, language="en")

        video_prompt_cn_raw = str(tech.get("video_prompt_cn") or "").strip()
        video_prompt_cn = ""
        if video_prompt_cn_raw:
            video_cn_ref_index_map = _compute_subject_ref_index_map(video_prompt_cn_raw, entity_lookup)
            video_prompt_cn = _inject_shot_prompt_anchors(video_prompt_cn_raw, entity_lookup, global_style, video_cn_ref_index_map)
            video_prompt_cn, ordered_video_refs = _append_video_api_ref_mapping(
                video_prompt_cn,
                ordered_video_refs,
                normalized_refs,
                normalized_last_frame_url,
                None,
                reference_video_urls,
                provider="seedance" if getattr(locals(), 'is_seedance_batch', False) else None,
                model=str(pre_api_cfg.get("model") or "") if getattr(locals(), "pre_api_cfg", None) else "",
                entity_lookup=entity_lookup,
                use_prev_video=bool(use_prev_video),
                preserve_submitted_refs=preserve_panel_video_refs,
            )
            _, normalized_refs = _sync_request_image_refs_with_aligned(
                aligned_refs=ordered_video_refs,
                image_urls=None,
                ref_image_url=normalized_refs,
                last_frame_url=normalized_last_frame_url,
                keyframes=keyframe_priority_refs if video_mode == "keyframes_entity_refs" else None,
            )
            if video_mode == "keyframes_entity_refs":
                keyframe_ref_count = 1 if keyframe_priority_refs else 0
                video_prompt_cn = _prepend_keyframe_story_progression_instruction(video_prompt_cn, keyframe_ref_count, language="zh")
            tech["video_prompt_cn"] = video_prompt_cn
            item_db.query(type(shot)).filter(type(shot).id == shot.id).update({"technical_notes": json.dumps(tech, ensure_ascii=False)})
            item_db.commit()

        logger.info(
            "[shot_media_batch] video ref resolution | shot_id=%s shot_label=%s video_mode=%s refs=%s last_frame=%s auto_entity_refs=%s fallback_to_refs=%s",
            shot.id,
            shot_label,
            video_mode,
            len(ordered_video_refs),
            bool(str(normalized_last_frame_url or "").strip()),
            len(auto_entity_refs),
            bool(batch_ref_info.get("fallback_to_refs")),
        )

        batch_status = _read_shot_media_batch_status(episode) if episode else {}
        duration_val = _resolve_shot_video_duration_value(
            shot_duration=shot.duration,
            sd2_auto_duration=bool((batch_status or {}).get("sd2_auto_duration")),
            system_api_id=system_api_id,
            db=item_db,
        )

        multi_prompt_payload = None
        if video_prompt_cn:
            multi_prompt_payload = [
                {"prompt": video_prompt, "type": "en"},
                {"prompt": video_prompt_cn, "type": "zh"}
            ]
        video_req = VideoGenerationRequest(
            draft_mode=bool((batch_status or {}).get("draft_mode")),
            prompt=video_prompt,
            multi_prompt=multi_prompt_payload,
            ref_image_url=normalized_refs,
            last_frame_url=normalized_last_frame_url,
            ref_mode=video_mode,
            keyframes=None,
            duration=duration_val,
            project_id=episode.project_id,
            shot_id=shot.id,
            shot_number=shot.shot_id,
            shot_name=shot.shot_name,
            asset_type="video",
            system_api_id=system_api_id,
            ref_video_urls=reference_video_urls or None,
            use_prev_video=bool(use_prev_video),
        )
        _release_db_connection(item_db, "shot_media_batch_video")
        try:
            callback_ticket_val = f"video-shot-{shot.id}"
            callback_url_val = str(media_service._resolve_provider_callback_url({}, callback_ticket_val) or "").strip()
        except Exception:
            callback_ticket_val = f"video-shot-{shot.id}"
            callback_url_val = ""

        asyncio.run(_run_stage_with_retry(
            lambda: _run_generate_video(
                req=video_req,
                current_user=user_principal,
                db=item_db,
                provider_callback_ticket=callback_ticket_val,
                provider_callback_url=callback_url_val
            ),
        ))

        return {
            "shot_id": int(shot.id),
            "shot_label": shot_label,
            "ok": True,
            "skipped": False,
        }
    finally:
        item_db.close()


def _run_shot_media_batch_job(episode_id: int, request_payload: Dict[str, Any], user_id: int) -> None:
    db = SessionLocal()
    cancel_event = _get_shot_media_batch_cancel_event(int(episode_id), create=True)
    min_prompt_chars = 5

    class _BatchStopRequested(Exception):
        pass

    async def _run_cancellable(coro: Any) -> Any:
        task = asyncio.create_task(coro)
        try:
            while True:
                done, _ = await asyncio.wait({task}, timeout=0.5)
                if task in done:
                    return await task
                if cancel_event and cancel_event.is_set():
                    task.cancel()
                    try:
                        await task
                    except BaseException:
                        pass
                    raise _BatchStopRequested("Stop requested")
        finally:
            if not task.done():
                task.cancel()
    try:
        episode = db.query(Episode).filter(Episode.id == episode_id).first()
        user = db.query(User).filter(User.id == user_id).first()
        if not episode or not user:
            return
        user_principal = _snapshot_user_principal(user)

        user_name = str(user_principal.username or f"user_{user_id}")
        project_id = int(episode.project_id)
        job_id = f"shot-media-batch:{int(episode_id)}"

        episode_info = _episode_info_from_episode(episode)
        e_global_info = episode_info.get("e_global_info", {}) if isinstance(episode_info, dict) else {}
        global_style = str((e_global_info or {}).get("Global_Style") or "").strip()
        entity_lookup = _build_project_entity_lookup(
            db, int(episode.project_id), episode_id=int(episode.id) if getattr(episode, "id", None) else None
        )

        mode = str((request_payload or {}).get("mode") or "keyframes").strip().lower()
        overwrite_existing = bool((request_payload or {}).get("overwrite_existing"))
        system_api_id = request_payload.get("system_api_id")
        if system_api_id is not None:
            try:
                system_api_id = int(system_api_id)
            except ValueError:
                system_api_id = None
        requested_shot_ids = [int(x) for x in ((request_payload or {}).get("shot_ids") or []) if x]
        batch_max_concurrency = _resolve_user_batch_parallel_limit(
            getattr(user_principal, "is_active", USER_ACTIVE_LEVEL_DEFAULT),
            default=SHOT_MEDIA_BATCH_DEFAULT_CONCURRENCY,
        )

        shots_query = db.query(Shot).filter(Shot.episode_id == episode_id).order_by(Shot.id.asc())
        if requested_shot_ids:
            shots_query = shots_query.filter(Shot.id.in_(requested_shot_ids))
        target_shots = shots_query.all()

        total = len(target_shots)
        completed = 0
        success = 0
        failed = 0
        errors: List[str] = []
        _release_db_connection(db, "shot_media_batch_bootstrap")

        def _read_latest_episode() -> Optional[Episode]:
            db.expire_all()
            return (
                db.query(Episode)
                .execution_options(populate_existing=True)
                .filter(Episode.id == episode_id)
                .first()
            )

        def _persist_stopped_status() -> None:
            latest_episode = _read_latest_episode()
            if not latest_episode:
                return
            latest_status = _read_shot_media_batch_status(latest_episode)
            latest_status["running"] = False
            latest_status["completed"] = completed
            latest_status["success"] = success
            latest_status["failed"] = failed
            latest_status["errors"] = errors
            latest_status["stopped_by_user"] = True
            latest_status["current_asset_type"] = None
            latest_status["current_asset_label"] = ""
            latest_status["message"] = "Stopped by user request"
            latest_status["finished_at"] = now_bj_iso()
            latest_status["updated_at"] = latest_status["finished_at"]
            _persist_shot_media_batch_status(db, latest_episode, latest_status)
            _log_batch_sys_event(
                kind="shot-media-batch",
                phase="end",
                user_id=user_id,
                user_name=user_name,
                project_id=project_id,
                episode_id=episode_id,
                job_id=job_id,
                result="canceled",
                message="Stopped by user request",
                extra={"completed": completed, "success": success, "failed": failed},
            )
            _release_db_connection(db, "shot_media_batch_stopped_status")

        def _is_stop_requested() -> bool:
            if cancel_event and cancel_event.is_set():
                return True
            latest_episode = _read_latest_episode()
            if not latest_episode:
                return True
            latest_status = _read_shot_media_batch_status(latest_episode)
            _release_db_connection(db, "shot_media_batch_stop_check")
            return bool(latest_status.get("stop_requested") or latest_status.get("force_stopped"))

        async def _run_stage_with_retry(coro_factory: Any, stage_label: str, shot_label: str, max_attempts: int = 3) -> Any:
            last_error: Optional[Exception] = None
            for attempt in range(1, max(2, max_attempts + 1)):
                if _is_stop_requested():
                    raise _BatchStopRequested("Stop requested")

                if attempt > 1:
                    latest_episode = _read_latest_episode()
                    if latest_episode:
                        latest_status = _read_shot_media_batch_status(latest_episode)
                        latest_status["message"] = f"Retrying {stage_label} for shot {shot_label} ({attempt}/{max_attempts})..."
                        latest_status["updated_at"] = now_bj_iso()
                        _persist_shot_media_batch_status(db, latest_episode, latest_status)
                        _release_db_connection(db, "shot_media_batch_retry_status")

                try:
                    return await _run_cancellable(coro_factory())
                except _BatchStopRequested:
                    raise
                except Exception as exc:
                    last_error = exc
                    try:
                        db.rollback()
                    except Exception:
                        pass

                    if attempt < max_attempts:
                        logger.warning(
                            "[shot_media_batch] stage retry | stage=%s shot=%s attempt=%s/%s error=%s",
                            stage_label,
                            shot_label,
                            attempt,
                            max_attempts,
                            exc,
                        )
                        await asyncio.sleep(min(4, attempt))
                        continue

            raise Exception(f"{stage_label} failed after {max_attempts} attempts: {last_error}")

        if mode == "videos":
            shot_label_map = {
                int(shot.id): str(shot.shot_id or shot.shot_name or f"#{shot.id}")
                for shot in target_shots
            }
            next_shot_index = 0
            active_future_map: Dict[Any, int] = {}

            def _active_shot_ids() -> List[int]:
                return list(active_future_map.values())

            def _persist_active_video_status(latest_episode: Optional[Episode], latest_message: Optional[str] = None) -> None:
                if not latest_episode:
                    return
                latest_status = _read_shot_media_batch_status(latest_episode)
                active_shot_ids = _active_shot_ids()
                active_shot_labels = [shot_label_map.get(sid) or f"#{sid}" for sid in active_shot_ids]
                latest_status["current_shot_id"] = active_shot_ids[0] if len(active_shot_ids) == 1 else None
                latest_status["current_shot_label"] = " / ".join(active_shot_labels)
                latest_status["current_asset_type"] = "video" if active_shot_labels else None
                latest_status["current_asset_label"] = "Video" if active_shot_labels else ""
                latest_status["updated_at"] = now_bj_iso()
                if latest_message is not None:
                    latest_status["message"] = latest_message
                elif active_shot_labels:
                    latest_status["message"] = (
                        f"Processing shots {', '.join(active_shot_labels)} · Video..."
                        if len(active_shot_labels) > 1
                        else f"Processing shot {active_shot_labels[0]} · Video..."
                    )
                _persist_shot_media_batch_status(db, latest_episode, latest_status)
                _release_db_connection(db, "shot_media_batch_active_video_status")

            def _submit_next_shot(executor: ThreadPoolExecutor) -> bool:
                nonlocal next_shot_index
                if next_shot_index >= len(target_shots):
                    return False
                shot = target_shots[next_shot_index]
                next_shot_index += 1
                active_future_map[executor.submit(
                    _run_shot_media_video_batch_item,
                    episode_id,
                    int(shot.id),
                    user_id,
                    overwrite_existing,
                    system_api_id,
                    bool((request_payload or {}).get("use_prev_video")),
                )] = int(shot.id)
                return True

            max_workers = max(1, min(batch_max_concurrency, total or 1))
            if bool((request_payload or {}).get("use_prev_video")):
                max_workers = 1
                logger.info(
                    "[shot_media_batch] forcing sequential video batch for previous-video continuation | episode_id=%s total=%s",
                    episode_id,
                    total,
                )
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                while len(active_future_map) < max_workers and _submit_next_shot(executor):
                    pass

                episode = _read_latest_episode()
                if episode and _is_stop_requested():
                    _persist_stopped_status()
                    return
                _persist_active_video_status(episode)

                while active_future_map:
                    completed_future = next(as_completed(list(active_future_map.keys())))
                    sid = active_future_map.pop(completed_future)
                    shot_label = shot_label_map.get(sid) or f"#{sid}"
                    try:
                        result = completed_future.result()
                    except Exception as e:
                        if _is_stop_requested():
                            _persist_stopped_status()
                            return
                        result = {
                            "shot_id": sid,
                            "shot_label": shot_label,
                            "ok": False,
                            "error": str(e),
                        }

                    if bool(result.get("ok")):
                        success += 1
                        _log_batch_sys_event(
                            kind="shot-media-batch",
                            phase="item",
                            user_id=user_id,
                            user_name=user_name,
                            project_id=project_id,
                            episode_id=episode_id,
                            job_id=job_id,
                            item_id=sid,
                            item_label=result.get("shot_label") or shot_label,
                            result="success",
                            message="Shot video generated" if not bool(result.get("skipped")) else "Shot video skipped",
                            extra={
                                "mode": mode,
                                "skipped": bool(result.get("skipped")),
                                "skip_reason": result.get("skip_reason"),
                            },
                        )
                    else:
                        failed += 1
                        error_message = str(result.get("error") or "Unknown error")
                        errors.append(f"{result.get('shot_label') or shot_label}: {error_message}")
                        _log_batch_sys_event(
                            kind="shot-media-batch",
                            phase="item",
                            user_id=user_id,
                            user_name=user_name,
                            project_id=project_id,
                            episode_id=episode_id,
                            job_id=job_id,
                            item_id=sid,
                            item_label=result.get("shot_label") or shot_label,
                            result="failed",
                            message=error_message,
                            extra={"mode": mode},
                        )

                    completed += 1
                    while len(active_future_map) < max_workers and not _is_stop_requested() and _submit_next_shot(executor):
                        pass

                    episode = _read_latest_episode()
                    if not episode:
                        break
                    latest = _read_shot_media_batch_status(episode)
                    latest["completed"] = completed
                    latest["success"] = success
                    latest["failed"] = failed
                    latest["errors"] = errors
                    latest["updated_at"] = now_bj_iso()
                    latest["message"] = f"Progress {completed}/{total}" if bool(result.get("ok")) else f"Progress {completed}/{total} (with errors)"
                    _persist_shot_media_batch_status(db, episode, latest)
                    _release_db_connection(db, "shot_media_batch_video_progress")

                    if _is_stop_requested():
                        _persist_stopped_status()
                        return

                    _persist_active_video_status(episode)

            episode = _read_latest_episode()
            if episode:
                final_status = _read_shot_media_batch_status(episode)
                final_status["running"] = False
                final_status["completed"] = completed
                final_status["success"] = success
                final_status["failed"] = failed
                final_status["errors"] = errors
                final_status["current_asset_type"] = None
                final_status["current_asset_label"] = ""
                final_status["updated_at"] = now_bj_iso()
                final_status["finished_at"] = final_status["updated_at"]
                final_status["message"] = f"Batch done: success {success}, failed {failed}"
                _persist_shot_media_batch_status(db, episode, final_status)
                _log_batch_sys_event(
                    kind="shot-media-batch",
                    phase="end",
                    user_id=user_id,
                    user_name=user_name,
                    project_id=project_id,
                    episode_id=episode_id,
                    job_id=job_id,
                    result="completed",
                    message=final_status.get("message"),
                    extra={
                        "completed": completed,
                        "success": success,
                        "failed": failed,
                        "mode": mode,
                        "max_concurrency": max_workers,
                    },
                )
                _release_db_connection(db, "shot_media_batch_video_final")
            return

        for shot in target_shots:
            episode = _read_latest_episode()
            if not episode:
                break
            latest = _read_shot_media_batch_status(episode)
            if bool(latest.get("stop_requested") or latest.get("force_stopped")):
                _persist_stopped_status()
                return

            shot_label = str(shot.shot_id or shot.shot_name or f"#{shot.id}")
            latest["current_shot_id"] = shot.id
            latest["current_shot_label"] = shot_label
            latest["message"] = f"Processing shot {shot_label}..."
            latest["updated_at"] = now_bj_iso()
            _persist_shot_media_batch_status(db, episode, latest)
            _release_db_connection(db, "shot_media_batch_shot_start")

            shot_ok = True
            try:
                tech = _parse_shot_tech(shot)
                end_frame_url = str(tech.get("end_frame_url") or "").strip()

                need_start = overwrite_existing or not str(shot.image_url or "").strip()
                need_end = overwrite_existing or not end_frame_url

                if _is_stop_requested():
                    _persist_stopped_status()
                    return

                if need_start:
                    start_prompt_raw = str(shot.start_frame or shot.video_content or "").strip()
                    if start_prompt_raw:
                        is_sap_start_prompt = str(start_prompt_raw).strip().upper() == "SAP"
                        prev_end = _find_previous_shot_end_frame_url(db, episode_id, int(shot.id))
                        if is_sap_start_prompt and prev_end:
                            tech = _parse_shot_tech(shot)
                            shot.image_url = prev_end
                            if str(tech.get("start_frame_url") or "").strip() != prev_end:
                                tech["start_frame_url"] = prev_end
                                shot.technical_notes = json.dumps(tech, ensure_ascii=False)
                            db.add(shot)
                            db.commit()
                            db.refresh(shot)
                            logger.info(
                                "[shot_media_batch] SAP start_frame linked from previous end_frame | shot_id=%s shot_label=%s prev_end=%s",
                                shot.id,
                                shot_label,
                                prev_end,
                            )
                        elif len(start_prompt_raw) < min_prompt_chars:
                            logger.info(
                                "[shot_media_batch] skip start_frame due to short prompt | shot_id=%s shot_label=%s prompt_len=%s",
                                shot.id,
                                shot_label,
                                len(start_prompt_raw),
                            )
                        else:
                            latest = _read_shot_media_batch_status(episode)
                            latest["current_shot_id"] = shot.id
                            latest["current_shot_label"] = shot_label
                            latest["current_asset_type"] = "start_frame"
                            latest["current_asset_label"] = "Start Frame"
                            latest["message"] = f"Processing shot {shot_label} · Start Frame..."
                            latest["updated_at"] = now_bj_iso()
                            _persist_shot_media_batch_status(db, episode, latest)
                            _release_db_connection(db, "shot_media_batch_start_status")

                            start_ref_index_map = _compute_subject_ref_index_map(start_prompt_raw, entity_lookup)
                            logger.info(
                                "[shot_media_batch] subject_ref_index_map asset=start_frame shot_id=%s shot_label=%s map=%s",
                                shot.id,
                                shot_label,
                                start_ref_index_map,
                            )
                            start_prompt = _inject_shot_prompt_anchors(start_prompt_raw, entity_lookup, global_style, start_ref_index_map)
                            start_refs = _resolve_default_shot_image_gen_refs(
                                shot, tech, entity_lookup, panel="start"
                            )
                            deleted_refs = {str(x).strip() for x in tech.get("deleted_ref_urls") or [] if str(x).strip()}
                            if is_sap_start_prompt and prev_end and prev_end not in start_refs and prev_end not in deleted_refs:
                                # SAP means reusing previous shot end frame as current start reference.
                                start_refs.insert(0, prev_end)

                            start_refs = [x for x in dict.fromkeys([str(x).strip() for x in start_refs if str(x).strip()]) if x]
                            start_req = GenerationRequest(
                                prompt=start_prompt,
                                ref_image_url=start_refs if start_refs else None,
                                project_id=episode.project_id,
                                shot_id=shot.id,
                                shot_number=shot.shot_id,
                                shot_name=shot.shot_name,
                                asset_type="start_frame",
                            )
                            _release_db_connection(db, "shot_media_batch_start_frame")
                            asyncio.run(_run_stage_with_retry(
                                lambda: _run_generate_image(req=start_req, current_user=user_principal, db=db),
                                "start_frame",
                                shot_label,
                            ))
                            shot = db.query(Shot).filter(Shot.id == shot.id).first() or shot

                if _is_stop_requested():
                    _persist_stopped_status()
                    return

                if need_end:
                    end_prompt_raw = str(shot.end_frame or "").strip()
                    if end_prompt_raw:
                        normalized_end_prompt = end_prompt_raw.strip().upper()
                        should_reuse_start_as_end = normalized_end_prompt in {"NO", "N/A", "NONE", "NULL", "NA"}
                        if should_reuse_start_as_end:
                            start_frame_url = str(shot.image_url or "").strip()
                            if start_frame_url:
                                tech = _parse_shot_tech(shot)
                                prev_end_url = str(tech.get("end_frame_url") or "").strip()
                                if prev_end_url != start_frame_url:
                                    tech["end_frame_url"] = start_frame_url
                                    tech["end_frame_reused_from_start"] = True
                                    shot.technical_notes = json.dumps(tech, ensure_ascii=False)
                                    db.add(shot)
                                    db.commit()
                                    db.refresh(shot)
                                end_frame_url = start_frame_url
                                logger.info(
                                    "[shot_media_batch] end_frame=NO-like, reuse start_frame_url | shot_id=%s shot_label=%s end_frame_url=%s",
                                    shot.id,
                                    shot_label,
                                    start_frame_url,
                                )
                            else:
                                logger.info(
                                    "[shot_media_batch] end_frame=NO-like but start_frame_url missing | shot_id=%s shot_label=%s",
                                    shot.id,
                                    shot_label,
                                )
                        elif len(end_prompt_raw) < min_prompt_chars:
                            logger.info(
                                "[shot_media_batch] skip end_frame due to short prompt | shot_id=%s shot_label=%s prompt_len=%s",
                                shot.id,
                                shot_label,
                                len(end_prompt_raw),
                            )
                        else:
                            latest = _read_shot_media_batch_status(episode)
                            latest["current_shot_id"] = shot.id
                            latest["current_shot_label"] = shot_label
                            latest["current_asset_type"] = "end_frame"
                            latest["current_asset_label"] = "End Frame"
                            latest["message"] = f"Processing shot {shot_label} · End Frame..."
                            latest["updated_at"] = now_bj_iso()
                            _persist_shot_media_batch_status(db, episode, latest)
                            _release_db_connection(db, "shot_media_batch_end_status")

                            end_ref_index_map = _compute_subject_ref_index_map(end_prompt_raw, entity_lookup)
                            logger.info(
                                "[shot_media_batch] subject_ref_index_map asset=end_frame shot_id=%s shot_label=%s map=%s",
                                shot.id,
                                shot_label,
                                end_ref_index_map,
                            )
                            end_prompt = _inject_shot_prompt_anchors(end_prompt_raw, entity_lookup, global_style, end_ref_index_map)
                            refs = _resolve_default_shot_image_gen_refs(
                                shot, tech, entity_lookup, panel="end"
                            )
                            refs = [x for x in dict.fromkeys([str(x).strip() for x in refs if str(x).strip()]) if x]
                            end_req = GenerationRequest(
                                prompt=end_prompt,
                                ref_image_url=refs if refs else None,
                                project_id=episode.project_id,
                                shot_id=shot.id,
                                shot_number=shot.shot_id,
                                shot_name=shot.shot_name,
                                asset_type="end_frame",
                            )
                            _release_db_connection(db, "shot_media_batch_end_frame")
                            asyncio.run(_run_stage_with_retry(
                                lambda: _run_generate_image(req=end_req, current_user=user_principal, db=db),
                                "end_frame",
                                shot_label,
                            ))
                            shot = db.query(Shot).filter(Shot.id == shot.id).first() or shot
                            tech = _parse_shot_tech(shot)
                            end_frame_url = str(tech.get("end_frame_url") or "").strip()

                if _is_stop_requested():
                    _persist_stopped_status()
                    return

                if mode == "videos":
                    need_video = overwrite_existing or not str(shot.video_url or "").strip()
                    if need_video:
                        latest = _read_shot_media_batch_status(episode)
                        latest["current_shot_id"] = shot.id
                        latest["current_shot_label"] = shot_label
                        latest["current_asset_type"] = "video"
                        latest["current_asset_label"] = "Video"
                        latest["message"] = f"Processing shot {shot_label} · Video..."
                        latest["updated_at"] = now_bj_iso()
                        _persist_shot_media_batch_status(db, episode, latest)
                        _release_db_connection(db, "shot_media_batch_video_status")

                        video_prompt_raw = str(shot.video_content or shot.prompt or "").strip() or "Video motion"
                        video_ref_index_map = _compute_subject_ref_index_map(video_prompt_raw, entity_lookup)
                        logger.info(
                            "[shot_media_batch] subject_ref_index_map asset=video shot_id=%s shot_label=%s map=%s",
                            shot.id,
                            shot_label,
                            video_ref_index_map,
                        )
                        video_prompt = _inject_shot_prompt_anchors(video_prompt_raw, entity_lookup, global_style, video_ref_index_map)

                        video_mode = _resolve_shot_video_mode(tech)
                        refs: List[str] = []
                        explicit_last_frame_url = end_frame_url or None
                        video_prompt_candidates: List[str] = [
                            str(video_prompt_raw or "").strip(),
                            str(tech.get("video_prompt_cn") or "").strip(),
                        ]
                        if isinstance(tech.get("video_ref_image_urls"), list):
                            refs.extend([str(x).strip() for x in tech.get("video_ref_image_urls") or [] if str(x).strip()])
                        else:
                            shot_mode = str(video_mode or "").strip().lower()
                            if not shot_mode:
                                shot_mode = DEFAULT_SHOT_VIDEO_MODE

                            if shot_mode == "end":
                                if end_frame_url:
                                    explicit_last_frame_url = end_frame_url
                            else:
                                if str(shot.image_url or "").strip():
                                    refs.append(str(shot.image_url).strip())

                                if shot_mode in {"entity_refs", "keyframes_entity_refs"}:
                                    keyframes = _limit_keyframes_for_video_mode(tech.get("keyframes"), shot_mode)
                                    refs.extend(keyframes)

                                if shot_mode == "start_end" and end_frame_url:
                                    explicit_last_frame_url = end_frame_url

                        preserve_panel_video_refs = isinstance(tech.get("video_ref_image_urls"), list) and bool(tech.get("video_ref_image_urls"))
                        refs, auto_entity_refs = _merge_entity_refs_for_video_mode(
                            refs,
                            ref_mode=video_mode,
                            prompt_candidates=video_prompt_candidates,
                            entity_lookup=entity_lookup,
                            manual_override=preserve_panel_video_refs,
                            associated_entities=shot.associated_entities,
                        )

                        normalized_refs, normalized_last_frame_url, batch_ref_info = _normalize_video_request_refs(
                            refs or None,
                            explicit_last_frame_url,
                            video_mode,
                            supports_last_frame_mode=True,
                        )

                        ordered_video_refs: List[str] = []
                        if isinstance(normalized_refs, list):
                            ordered_video_refs.extend([str(x).strip() for x in normalized_refs if str(x).strip()])
                        elif str(normalized_refs or "").strip():
                            ordered_video_refs.append(str(normalized_refs).strip())
                        if str(normalized_last_frame_url or "").strip():
                            ordered_video_refs.append(str(normalized_last_frame_url).strip())
                        ordered_video_refs = [x for x in dict.fromkeys(ordered_video_refs) if x]

                        keyframe_priority_refs: List[str] = []
                        if video_mode == "keyframes_entity_refs":
                            keyframe_priority_refs = _limit_keyframes_for_video_mode(tech.get("keyframes"), video_mode)
                            if keyframe_priority_refs:
                                ordered_video_refs = [
                                    *keyframe_priority_refs,
                                    *[ref for ref in ordered_video_refs if ref not in keyframe_priority_refs],
                                ]

                        reference_video_urls: List[str] = []
                        if bool((request_payload or {}).get("use_prev_video")):
                            prev_video_url = _find_previous_shot_video_url(db, episode_id, int(shot.id))
                            if prev_video_url:
                                reference_video_urls.append(prev_video_url)

                        video_prompt, ordered_video_refs = _append_video_api_ref_mapping(
                            video_prompt,
                            ordered_video_refs,
                            normalized_refs,
                            normalized_last_frame_url,
                            None,
                            reference_video_urls,
                            entity_lookup=entity_lookup,
                            use_prev_video=bool((request_payload or {}).get("use_prev_video")),
                            provider="seedance" if getattr(locals(), 'is_seedance_batch', False) else None,
                            preserve_submitted_refs=preserve_panel_video_refs,
                        )
                        _, normalized_refs = _sync_request_image_refs_with_aligned(
                            aligned_refs=ordered_video_refs,
                            image_urls=None,
                            ref_image_url=normalized_refs,
                            last_frame_url=normalized_last_frame_url,
                            keyframes=keyframe_priority_refs if video_mode == "keyframes_entity_refs" else None,
                        )
                        if video_mode == "keyframes_entity_refs":
                            keyframe_ref_count = 1 if keyframe_priority_refs else 0
                            video_prompt = _prepend_keyframe_story_progression_instruction(video_prompt, keyframe_ref_count, language="en")

                        video_prompt_cn_raw = str(tech.get("video_prompt_cn") or "").strip()
                        video_prompt_cn = ""
                        if video_prompt_cn_raw:
                            video_cn_ref_index_map = _compute_subject_ref_index_map(video_prompt_cn_raw, entity_lookup)
                            video_prompt_cn = _inject_shot_prompt_anchors(video_prompt_cn_raw, entity_lookup, global_style, video_cn_ref_index_map)
                            video_prompt_cn, ordered_video_refs = _append_video_api_ref_mapping(
                                video_prompt_cn,
                                ordered_video_refs,
                                normalized_refs,
                                normalized_last_frame_url,
                                None,
                                reference_video_urls,
                                entity_lookup=entity_lookup,
                                use_prev_video=bool((request_payload or {}).get("use_prev_video")),
                                provider="seedance" if getattr(locals(), 'is_seedance_batch', False) else None,
                                preserve_submitted_refs=preserve_panel_video_refs,
                            )
                            _, normalized_refs = _sync_request_image_refs_with_aligned(
                                aligned_refs=ordered_video_refs,
                                image_urls=None,
                                ref_image_url=normalized_refs,
                                last_frame_url=normalized_last_frame_url,
                                keyframes=keyframe_priority_refs if video_mode == "keyframes_entity_refs" else None,
                            )
                            if video_mode == "keyframes_entity_refs":
                                keyframe_ref_count = 1 if keyframe_priority_refs else 0
                                video_prompt_cn = _prepend_keyframe_story_progression_instruction(video_prompt_cn, keyframe_ref_count, language="zh")
                            tech["video_prompt_cn"] = video_prompt_cn
                            db.query(type(shot)).filter(type(shot).id == shot.id).update({"technical_notes": json.dumps(tech, ensure_ascii=False)})
                            db.commit()

                        logger.info(
                            "[shot_media_batch] video ref resolution | shot_id=%s shot_label=%s video_mode=%s refs=%s last_frame=%s auto_entity_refs=%s fallback_to_refs=%s",
                            shot.id,
                            shot_label,
                            video_mode,
                            len(ordered_video_refs),
                            bool(str(normalized_last_frame_url or "").strip()),
                            len(auto_entity_refs),
                            bool(batch_ref_info.get("fallback_to_refs")),
                        )

                        batch_status = _read_shot_media_batch_status(episode) if episode else {}
                        duration_val = _resolve_shot_video_duration_value(
                            shot_duration=shot.duration,
                            sd2_auto_duration=bool((batch_status or {}).get("sd2_auto_duration")),
                            system_api_id=system_api_id,
                            db=db,
                        )

                        multi_prompt_payload = None
                        if video_prompt_cn:
                            multi_prompt_payload = [
                                {"prompt": video_prompt, "type": "en"},
                                {"prompt": video_prompt_cn, "type": "zh"}
                            ]
                        video_req = VideoGenerationRequest(
                            draft_mode=bool((batch_status or {}).get("draft_mode")),
                            prompt=video_prompt,
                            multi_prompt=multi_prompt_payload,
                            ref_image_url=normalized_refs,
                            last_frame_url=normalized_last_frame_url,
                            ref_mode=video_mode,
                            keyframes=None,
                            duration=duration_val,
                            project_id=episode.project_id,
                            shot_id=shot.id,
                            shot_number=shot.shot_id,
                            shot_name=shot.shot_name,
                            asset_type="video",
                            system_api_id=system_api_id,
                            ref_video_urls=reference_video_urls or None,
                            use_prev_video=bool((request_payload or {}).get("use_prev_video")),
                        )
                        _release_db_connection(db, "shot_media_batch_video")
                        try:
                            callback_ticket_val = f"video-shot-{shot.id}"
                            callback_url_val = str(media_service._resolve_provider_callback_url({}, callback_ticket_val) or "").strip()
                        except Exception:
                            callback_ticket_val = f"video-shot-{shot.id}"
                            callback_url_val = ""

                        asyncio.run(_run_stage_with_retry(
                            lambda: _run_generate_video(
                                req=video_req,
                                current_user=user_principal,
                                db=db,
                                provider_callback_ticket=callback_ticket_val,
                                provider_callback_url=callback_url_val
                            ),
                            "video",
                            shot_label,
                        ))

                success += 1
                _log_batch_sys_event(
                    kind="shot-media-batch",
                    phase="item",
                    user_id=user_id,
                    user_name=user_name,
                    project_id=project_id,
                    episode_id=episode_id,
                    job_id=job_id,
                    item_id=int(shot.id),
                    item_label=shot_label,
                    result="success",
                    message="Shot media generated",
                    extra={"mode": mode},
                )
            except _BatchStopRequested:
                _persist_stopped_status()
                return
            except Exception as e:
                try:
                    db.rollback()
                except Exception:
                    pass
                shot_ok = False
                failed += 1
                errors.append(f"{shot_label}: {str(e)}")
                _log_batch_sys_event(
                    kind="shot-media-batch",
                    phase="item",
                    user_id=user_id,
                    user_name=user_name,
                    project_id=project_id,
                    episode_id=episode_id,
                    job_id=job_id,
                    item_id=int(shot.id),
                    item_label=shot_label,
                    result="failed",
                    message=str(e),
                    extra={"mode": mode},
                )

            completed += 1
            episode = _read_latest_episode()
            if not episode:
                break
            latest = _read_shot_media_batch_status(episode)
            latest["completed"] = completed
            latest["success"] = success
            latest["failed"] = failed
            latest["errors"] = errors
            latest["current_asset_type"] = None
            latest["current_asset_label"] = ""
            latest["updated_at"] = now_bj_iso()
            latest["message"] = (
                f"Progress {completed}/{total}" if shot_ok else f"Progress {completed}/{total} (with errors)"
            )
            _persist_shot_media_batch_status(db, episode, latest)
            _release_db_connection(db, "shot_media_batch_progress")

        episode = _read_latest_episode()
        if episode:
            final_status = _read_shot_media_batch_status(episode)
            final_status["running"] = False
            final_status["completed"] = completed
            final_status["success"] = success
            final_status["failed"] = failed
            final_status["errors"] = errors
            final_status["current_asset_type"] = None
            final_status["current_asset_label"] = ""
            final_status["updated_at"] = now_bj_iso()
            final_status["finished_at"] = final_status["updated_at"]
            final_status["message"] = f"Batch done: success {success}, failed {failed}"
            _persist_shot_media_batch_status(db, episode, final_status)
            _log_batch_sys_event(
                kind="shot-media-batch",
                phase="end",
                user_id=user_id,
                user_name=user_name,
                project_id=project_id,
                episode_id=episode_id,
                job_id=job_id,
                result="completed",
                message=final_status.get("message"),
                extra={"completed": completed, "success": success, "failed": failed, "mode": mode},
            )
            _release_db_connection(db, "shot_media_batch_final")
    except Exception as e:
        try:
            db.expire_all()
            episode = (
                db.query(Episode)
                .execution_options(populate_existing=True)
                .filter(Episode.id == episode_id)
                .first()
            )
            if episode:
                status_payload = _read_shot_media_batch_status(episode)
                status_payload["running"] = False
                status_payload["updated_at"] = now_bj_iso()
                status_payload["finished_at"] = status_payload["updated_at"]
                status_payload["message"] = f"Batch failed: {str(e)}"
                status_payload["current_asset_type"] = None
                status_payload["current_asset_label"] = ""
                status_payload["errors"] = list(status_payload.get("errors") or []) + [str(e)]
                _persist_shot_media_batch_status(db, episode, status_payload)
                _log_batch_sys_event(
                    kind="shot-media-batch",
                    phase="end",
                    user_id=user_id,
                    user_name=str((user.username if 'user' in locals() and user else "") or f"user_{user_id}"),
                    project_id=int(episode.project_id),
                    episode_id=episode_id,
                    job_id=f"shot-media-batch:{int(episode_id)}",
                    result="failed",
                    message=str(e),
                )
                _release_db_connection(db, "shot_media_batch_error")
        except Exception:
            pass
    finally:
        _clear_episode_worker(SHOT_MEDIA_BATCH_THREADS, SHOT_MEDIA_BATCH_THREADS_LOCK, int(episode_id))
        _clear_shot_media_batch_cancel_event(int(episode_id))
        db.close()

# --- batch-media (moved from endpoints) ---
@router.post("/episodes/{episode_id}/shots/batch-media/start", response_model=Dict[str, Any])
def start_shot_media_batch_job(
    episode_id: int,
    req: ShotMediaBatchStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)

    mode = str(req.mode or "keyframes").strip().lower()
    if mode not in {"keyframes", "videos"}:
        raise HTTPException(status_code=400, detail="mode must be 'keyframes' or 'videos'")

    latest = _read_shot_media_batch_status(episode)
    if bool(latest.get("running")):
        raise HTTPException(status_code=409, detail="Shot media batch task is already running")

    shots_query = db.query(Shot).filter(Shot.episode_id == episode_id)
    if req.shot_ids:
        shots_query = shots_query.filter(Shot.id.in_(req.shot_ids))
    target_shots = shots_query.order_by(Shot.id.asc()).all()
    if mode == "videos":
        target_shots = [shot for shot in target_shots if _is_shot_video_batch_eligible(shot, bool(req.overwrite_existing))]
    shot_ids = [int(s.id) for s in target_shots]
    if not shot_ids:
        if mode == "videos":
            raise HTTPException(status_code=400, detail="No eligible shots found for video batch task")
        raise HTTPException(status_code=400, detail="No shots found for batch task")

    batch_max_concurrency = _resolve_user_batch_parallel_limit(
        getattr(current_user, "is_active", USER_ACTIVE_LEVEL_DEFAULT),
        default=SHOT_MEDIA_BATCH_DEFAULT_CONCURRENCY,
    )

    now_iso = now_bj_iso()
    status_payload = {
        "running": True,
        "mode": mode,
        "episode_id": episode_id,
        "project_id": episode.project_id,
        "started_by_user_id": int(current_user.id),
        "started_by_username": str(current_user.username or ""),
        "shot_ids": shot_ids,
        "max_concurrency": batch_max_concurrency,
        "overwrite_existing": bool(req.overwrite_existing),
        "draft_mode": bool(req.draft_mode),
        "sd2_auto_duration": bool(req.sd2_auto_duration),
        "total": len(shot_ids),
        "completed": 0,
        "success": 0,
        "failed": 0,
        "current_shot_id": None,
        "current_shot_label": "",
        "current_asset_type": None,
        "current_asset_label": "",
        "message": "Batch task started",
        "errors": [],
        "stop_requested": False,
        "stop_requested_at": None,
        "force_stopped": False,
        "stopped_by_user": False,
        "started_at": now_iso,
        "updated_at": now_iso,
        "finished_at": None,
    }
    _persist_shot_media_batch_status(db, episode, status_payload)
    _log_batch_sys_event(
        kind="shot-media-batch",
        phase="start",
        user_id=current_user.id,
        user_name=current_user.username,
        project_id=episode.project_id,
        episode_id=episode_id,
        job_id=f"shot-media-batch:{int(episode_id)}",
        result="running",
        message="Batch task started",
        extra={
            "shot_ids": shot_ids,
            "total": len(shot_ids),
            "mode": mode,
            "max_concurrency": batch_max_concurrency,
            "overwrite_existing": bool(req.overwrite_existing),
        },
    )
    _reset_shot_media_batch_cancel_requested(int(episode_id))

    worker = threading.Thread(
        target=_run_shot_media_batch_job,
        args=(episode_id, req.model_dump(), current_user.id),
        daemon=True,
    )
    worker.start()
    _register_episode_worker(SHOT_MEDIA_BATCH_THREADS, SHOT_MEDIA_BATCH_THREADS_LOCK, int(episode_id), worker)
    return status_payload


@router.get("/episodes/{episode_id}/shots/batch-media/status", response_model=Dict[str, Any])
def get_shot_media_batch_job_status(
    episode_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cached_status = _get_cached_shot_media_batch_status(int(episode_id))
    try:
        project_id = None
        if isinstance(cached_status, dict):
            try:
                project_id = int(cached_status.get("project_id") or 0)
            except Exception:
                project_id = 0

        episode = None
        if project_id and project_id > 0:
            _require_project_access(db, project_id, current_user)
        else:
            episode = db.query(Episode).filter(Episode.id == episode_id).first()
            if not episode:
                raise HTTPException(status_code=404, detail="Episode not found")
            _require_project_access(db, episode.project_id, current_user)

        if episode is None:
            episode = db.query(Episode).filter(Episode.id == episode_id).first()
            if not episode:
                if isinstance(cached_status, dict):
                    return cached_status
                raise HTTPException(status_code=404, detail="Episode not found")

        status_payload = _read_shot_media_batch_status(episode)
        _cache_shot_media_batch_status(int(episode_id), status_payload)
        if (
            bool(status_payload.get("running"))
            and _is_stale_running_payload(status_payload, stale_minutes=10)
            and not _is_episode_worker_alive(SHOT_MEDIA_BATCH_THREADS, SHOT_MEDIA_BATCH_THREADS_LOCK, int(episode_id))
        ):
            now_iso = now_bj_iso()
            status_payload["running"] = False
            status_payload["status"] = "canceled"
            status_payload["force_stopped"] = True
            status_payload["stopped_by_user"] = True
            status_payload["current_shot_id"] = None
            status_payload["current_shot_label"] = ""
            status_payload["current_asset_type"] = None
            status_payload["current_asset_label"] = ""
            status_payload["updated_at"] = now_iso
            status_payload["finished_at"] = status_payload.get("finished_at") or now_iso
            status_payload["message"] = "Recovered orphaned task state (no active worker)"
            _persist_shot_media_batch_status(db, episode, status_payload)
            _cache_shot_media_batch_status(int(episode_id), status_payload)
        return status_payload
    except SQLAlchemyTimeoutError:
        if isinstance(cached_status, dict):
            fallback = dict(cached_status)
            fallback["degraded"] = True
            fallback["message"] = str(fallback.get("message") or "Status temporarily served from cache (database busy)")
            return fallback
        raise HTTPException(
            status_code=503,
            detail="Database connection pool is busy, please retry shortly",
        )


@router.post("/episodes/{episode_id}/shots/batch-media/stop", response_model=Dict[str, Any])
def stop_shot_media_batch_job(
    episode_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)

    latest_status = _read_shot_media_batch_status(episode)
    if not bool(latest_status.get("running")):
        _clear_cached_shot_media_batch_status(int(episode_id))
        return {
            "episode_id": int(episode_id),
            "running": False,
            "status": "idle",
            "deleted": False,
            "message": "No running shot batch task",
        }

    now_iso = now_bj_iso()
    latest_status["stop_requested"] = True
    latest_status["stop_requested_at"] = latest_status.get("stop_requested_at") or now_iso
    latest_status["stopped_by_user"] = True
    latest_status["message"] = "Stop requested by user"
    latest_status["updated_at"] = now_iso
    _persist_shot_media_batch_status(db, episode, latest_status)

    _set_shot_media_batch_cancel_requested(int(episode_id))
    _log_batch_sys_event(
        kind="shot-media-batch",
        phase="stop",
        user_id=current_user.id,
        user_name=current_user.username,
        project_id=episode.project_id,
        episode_id=episode_id,
        job_id=f"shot-media-batch:{int(episode_id)}",
        result="cancel_requested",
        message="Stop requested by user",
    )
    return {
        "episode_id": int(episode_id),
        "running": True,
        "status": "cancel_requested",
        "deleted": False,
        "message": "Stop requested",
    }

class MontageItem(BaseModel):
    url: str
    speed: float = 1.0
    trim_start: float = 0.0
    trim_end: float = 0.0

class MontageRequest(BaseModel):
    items: List[MontageItem]


class MontageDeleteRequest(BaseModel):
    url: str

# --- montage (moved from endpoints) ---
@router.post("/projects/{project_id}/montage")
async def generate_montage(
    project_id: int,
    request: MontageRequest,
    async_mode: bool = Query(False),
    current_user: User = Depends(get_current_user)
):
    try:
        items_payload = [item.dict() for item in request.items]
        if async_mode:
            task_id = _create_task_record(
                user_id=current_user.id,
                kind="montage",
                status="pending",
            )
            _submit_generation_background_task(
                job_id=task_id,
                kind="montage",
                user_id=current_user.id,
                payload={
                    "project_id": int(project_id),
                    "items": items_payload,
                },
            )
            return {"task_id": task_id, "async": True}

        url = create_montage(project_id, items_payload, user_id=current_user.id)
        return {"url": url}
    except Exception as e:
        logger.error(f"Montage failed: {str(e)}")
        detail = str(e)
        lowered = detail.lower()
        if isinstance(e, ValueError):
            raise HTTPException(status_code=400, detail=detail)
        if "busy" in lowered:
            raise HTTPException(status_code=429, detail=detail)
        raise HTTPException(status_code=500, detail=detail)


@router.delete("/projects/{project_id}/montage")
async def delete_montage(
    project_id: int,
    request: MontageDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_project_access(db, int(project_id), current_user)

    raw_url = str(request.url or "").strip()
    if not raw_url:
        raise HTTPException(status_code=400, detail="Montage url is required")

    if "/uploads/" in raw_url:
        relative_path = raw_url.split("/uploads/", 1)[1]
    else:
        relative_path = os.path.basename(raw_url)

    relative_path = str(relative_path or "").replace("\\", "/").lstrip("/")
    filename = os.path.basename(relative_path)
    expected_prefix = f"montage_{int(project_id)}_"
    if not filename or not filename.startswith(expected_prefix) or not filename.endswith(".mp4"):
        raise HTTPException(status_code=400, detail="Invalid montage file")

    upload_root = os.path.abspath(settings.UPLOAD_DIR)
    file_path = os.path.abspath(os.path.join(upload_root, relative_path))
    if os.path.commonpath([upload_root, file_path]) != upload_root:
        raise HTTPException(status_code=400, detail="Invalid montage path")

    if not os.path.exists(file_path):
        return {"status": "success", "deleted": False, "message": "Montage file not found"}

    try:
        os.remove(file_path)
    except FileNotFoundError:
        return {"status": "success", "deleted": False, "message": "Montage file not found"}
    except Exception as exc:
        logger.warning("Failed to delete montage file project_id=%s path=%s error=%s", project_id, file_path, exc)
        raise HTTPException(status_code=500, detail="Failed to delete montage file")

    return {"status": "success", "deleted": True, "url": raw_url}


class AnalyzeImageRequest(BaseModel):
    asset_id: Optional[int] = None
    image_url: Optional[str] = None
    system_api_id: Optional[int] = None
    function_name: Optional[str] = None



# Refresh cross-router helpers after local definitions are complete.
_bind_endpoint_helpers()

