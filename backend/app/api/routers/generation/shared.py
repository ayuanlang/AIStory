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
    IMAGE_JOB_MAX_RUNNING_SECONDS,
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



from app.services.generation_runtime.project_generation_context import (  # noqa: E402,F401
    _DEFAULT_FRAME_INTEGRITY_NEGATIVE_PROMPT,
    _ensure_project_generation_seed,
    _normalize_seed_value,
    _resolve_effective_negative_prompt,
    _resolve_project_id_for_generation,
    _should_hit_visual_breakpoint,
)
from app.services.generation_runtime.video_provider_options import (  # noqa: E402,F401
    _build_video_provider_options,
)
from app.services.generation_runtime.job_timeout import (  # noqa: E402,F401
    _job_is_subject_to_running_timeout,
    _maybe_finalize_stuck_job,
    _reconcile_terminal_job_queue_state,
    _resolve_job_elapsed_seconds,
)
from app.services.generation_runtime.image_generation_runner import (  # noqa: E402,F401
    _run_generate_image,
    _run_generate_image_job,
)
from app.services.user_model_preferences import (  # noqa: E402,F401
    _normalize_cfg,
    _read_user_advanced_model_preferences,
)

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


