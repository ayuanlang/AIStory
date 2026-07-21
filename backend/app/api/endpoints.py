
import os
from typing import Any, Dict
import importlib

from app.core.queue_config import DEFAULT_QUEUE_CONFIG, load_queue_config, save_queue_config

_q_conf = load_queue_config()


def _queue_runtime_config() -> Dict[str, Any]:
    try:
        loaded = load_queue_config()
        if isinstance(loaded, dict):
            return loaded
    except Exception:
        pass
    return dict(_q_conf or {})


def _queue_cfg_bool(key: str, default: bool = False) -> bool:
    cfg = _queue_runtime_config()
    value = cfg.get(key, default)
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _queue_cfg_int(key: str, default: int, minimum: int = 0, maximum: int = 10**9) -> int:
    cfg = _queue_runtime_config()
    try:
        raw = int(cfg.get(key, default))
    except Exception:
        raw = int(default)
    return max(int(minimum), min(int(maximum), int(raw)))


def _is_pure_callback_mode_enabled() -> bool:
    auto_mode = _queue_cfg_bool("pure_callback_mode_auto", True)
    if auto_mode:
        is_public_deploy = bool(
            str(os.getenv("RENDER_EXTERNAL_URL") or "").strip()
            or str(os.getenv("RENDER") or "").strip()
            or str(os.getenv("RAILWAY_STATIC_URL") or "").strip()
            or str(os.getenv("RAILWAY_PUBLIC_DOMAIN") or "").strip()
            or str(os.getenv("VERCEL_URL") or "").strip()
        )
        return is_public_deploy
    return _queue_cfg_bool("pure_callback_mode", False)

from fastapi import APIRouter, Depends, HTTPException, Body, Request, Query, Response
from fastapi.responses import StreamingResponse, FileResponse
from starlette.background import BackgroundTask
import logging
import smtplib
from email.message import EmailMessage
from sqlalchemy.orm import Session, load_only
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.exc import OperationalError, ProgrammingError, TimeoutError as SQLAlchemyTimeoutError, IntegrityError
from sqlalchemy import or_, and_, text, inspect, cast, String, func
from app.db.session import get_db, SessionLocal, DB_POOL_CAPACITY_EFFECTIVE, engine
from app.models import all_models as models
from app.schemas.agent import AgentRequest, AgentResponse, AnalyzeSceneRequest
from app.services.agent_service import agent_service
from app.services.billing_service import billing_service
from app.services.oss_storage_service import oss_storage_service
from app.services.asset_meta_probe import (
    asset_meta_needs_probe,
    enrich_asset_meta_info,
    ensure_resolution_fields,
    probe_media_from_path,
)
from app.services.tool_billing_taxonomy_service import tool_billing_taxonomy_service
from app.services.creative_structure_search_service import (
    build_creative_structure_search_user_prompt,
    collect_creative_structure_search_snippets,
)
from app.services.episode_script_reference_service import (
    build_episode_script_reference_user_prompt,
    collect_episode_script_reference_snippets,
    extract_episode_block_from_global_framework,
    extract_story_dna_output_for_validation,
    is_acceptable_story_dna_markdown,
    normalize_story_dna_markdown_for_persist,
    wrap_story_dna_input_block,
)
from app.services.story_trend_search_service import (
    build_industry_analysis_user_prompt,
    build_trending_ai_short_dramas_user_prompt,
    collect_industry_analysis_search_snippets,
    collect_trending_dramas_search_snippets,
    current_report_month_label,
    current_report_period_label,
)
from app.core.prompts.skills_loader import get_skill_prompt_text, load_skills_registry, get_skill_meta
from app.core.prompts.scene_analysis_feature_skills import (
    get_scene_analysis_feature_catalog,
    render_scene_analysis_routed_prompt,
    resolve_scene_analysis_feature_bundle,
)
from app.core.prompt_injection import unwrap_injection_section, wrap_injection_section
from app.core.prompts.shot_generation_feature_skills import (
    get_shot_generation_feature_catalog,
    render_shot_generation_routed_prompt,
    resolve_shot_generation_feature_bundle,
)
from app.services.llm_service import llm_service
from app.services.payment_service import payment_service
from app.services.task_manager import create_task_record as _create_task_record, submit as _submit_task, get_status as _get_task_status, submit_async_endpoint as _submit_async, cancel as _cancel_task, set_task_status as _set_task_status
from app.services.system_default_api_service import get_task_default_system_setting, list_task_default_system_settings
from app.services.system_api_runtime_cache import resolve_system_api_cached
from app.api.settings import get_scene_analysis_system_config, get_project_cost_estimation_config, get_script_analysis_flow_config
from app.services.script_analysis_flow import (
    build_script_analysis_flow_plan,
    extract_adapted_script_from_beats_user_input,
    expand_scene_ids_for_orchestration_reset,
    extract_scenes_table_markdown_block,
    extract_scene_markdown_text_from_analyze_result,
    import_analyze_scene_stage_result,
    import_scene_markdown_stage,
    merge_scenes_table_markdown_outputs,
    parse_scene_units_from_markers,
    patch_episode_scene_markdown_by_scene,
    persist_analyze_scene_stage_result,
    resolve_scene_units_for_markdown_orchestration,
    resolve_analyze_scene_stage,
    _reconcile_scene_table_row_cells,
    _split_scene_table_cells,
    SCENES_BLOCK_END_TOKEN,
    STAGE_SCENE_MARKDOWN,
    get_script_analysis_flow_registry,
    normalize_node_status,
    raise_progress_issue,
    resolve_progress_issue,
    SCENES_BLOCK_START_TOKEN,
    SceneMarkerParseError,
    sync_scene_units_from_markers,
    sync_scene_units_from_script_text,
    update_scene_unit_orchestration_status,
    upsert_pipeline_node_status,
    validate_analyze_scene_llm_finish_reason,
    validate_single_scene_markdown_for_orchestration,
    patch_single_scene_markdown_for_orchestration,
    sanitize_scene_markdown_llm_output,
    wrap_scene_unit_as_script_block,
    extract_scene_name_value_from_scene_text,
    SceneBeatsTooShortError,
    SceneMissingBeat1Error,
    scene_text_has_beat_1,
    build_assets_extraction_script_from_adapted,
)
from app.services.script_analysis_flow.subject_index_name_align import (
    align_scene_markdown_names_with_subject_index,
    align_subjects_json_names_with_subject_index,
    apply_text_name_replacements,
)
from app.db.init_db import check_and_migrate_tables  # EMERGENCY FIX IMPORT
from app.core.time_utils import BEIJING_TZ, now_bj_iso
import os


from app.services.media_service import MediaGenerationService
from app.services.video_service import create_montage, process_video_cleanup_local
from app.services.project_cost_service import compute_project_cost_estimation
from app.api.deps import get_current_user, cache_user_identity, invalidate_cached_user_identity, list_cached_user_entries  # Import dependency
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any, Union, Tuple, TYPE_CHECKING, Set, Iterable
from pydantic import BaseModel
import bcrypt
import re
import json
import time
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from app.core.config import settings
from app.core.homepage_referral import parse_homepage_referral_token
from app.core.entity_token import (
    entity_subject_keys_match,
    extract_entity_raw_names_from_prompt,
    normalize_entity_token,
    subject_compare_key,
    subject_compare_key_variants,
)
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi import File, UploadFile, Form
import shutil
import os
import uuid
from PIL import Image
import requests
import asyncio
import urllib.parse
import socket
import sys
import time
import math
import io
import zipfile


IMAGE_SYNC_TIMEOUT_SECONDS = min(300, max(55, int(os.getenv("IMAGE_SYNC_TIMEOUT_SECONDS", "180"))))
import html
from pathlib import Path
from collections import deque
import threading
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import hmac
import base64
import random
import copy
from types import SimpleNamespace

# Import limiter from main app state or create a local reference if needed
# We will use the request.app.state.limiter in the endpoints
from slowapi import Limiter
from slowapi.util import get_remote_address

Project = models.Project
ProjectShare = models.ProjectShare
ProjectAssetReviewThread = getattr(models, "ProjectAssetReviewThread", None)
ProjectAssetReviewRound = getattr(models, "ProjectAssetReviewRound", None)
ProjectAssetReviewMessage = getattr(models, "ProjectAssetReviewMessage", None)
User = models.User
Episode = models.Episode
Scene = models.Scene
Shot = models.Shot
Entity = models.Entity
Asset = models.Asset
APISetting = models.APISetting
SystemAPISetting = models.SystemAPISetting
ScriptSegment = models.ScriptSegment
TransactionHistory = models.TransactionHistory
TransactionAction = models.TransactionAction
SMTPSystemConfig = models.SMTPSystemConfig
WechatPayConfig = models.WechatPayConfig
ProviderKeyPool = models.ProviderKeyPool
ScriptProgressSceneUnit = getattr(models, "ScriptProgressSceneUnit", None)
ScriptProgressPipelineNode = getattr(models, "ScriptProgressPipelineNode", None)
ScriptProgressIssue = getattr(models, "ScriptProgressIssue", None)
DeletionBatch = getattr(models, "DeletionBatch", None)
DeletionBatchItem = getattr(models, "DeletionBatchItem", None)
MarketIntelReport = getattr(models, "MarketIntelReport", None)

_REVIEW_MODELS_AVAILABLE = all(
    model is not None
    for model in (ProjectAssetReviewThread, ProjectAssetReviewRound, ProjectAssetReviewMessage)
)

if TYPE_CHECKING:
    from app.models.all_models import (
        ProjectAssetReviewThread as ProjectAssetReviewThreadModel,
        ProjectAssetReviewRound as ProjectAssetReviewRoundModel,
        ProjectAssetReviewMessage as ProjectAssetReviewMessageModel,
    )
else:
    ProjectAssetReviewThreadModel = Any
    ProjectAssetReviewRoundModel = Any
    ProjectAssetReviewMessageModel = Any

# Create a local limiter instance for the router decorators
limiter = Limiter(key_func=get_remote_address)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/login/access-token")


def _require_review_models() -> None:
    if _REVIEW_MODELS_AVAILABLE:
        return
    raise HTTPException(
        status_code=503,
        detail="Project asset review is temporarily unavailable on this deployment",
    )


def _is_schema_compat_error(exc: Exception) -> bool:
    raw = str(getattr(exc, "orig", exc) or exc).strip().lower()
    if not raw:
        return False
    markers = (
        "undefinedcolumn",
        "undefinedtable",
        "does not exist",
        "no such column",
        "no such table",
        "datatype mismatch",
        "type boolean but expression is of type integer",
    )
    return any(marker in raw for marker in markers)


def _run_with_schema_self_heal(db: Session, operation, *, context: str):
    try:
        return operation()
    except (OperationalError, ProgrammingError) as exc:
        if not _is_schema_compat_error(exc):
            raise
        logger.warning("[%s] detected schema mismatch, running migration and retrying once: %s", context, exc)
        try:
            db.rollback()
        except Exception:
            pass
        check_and_migrate_tables()
        return operation()


from app.services.auth_security import get_password_hash, verify_password


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def get_current_claims(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise credentials_exception

    username = str(payload.get("sub") or payload.get("uname") or "").strip()
    if not username:
        raise credentials_exception

    uid_raw = payload.get("uid")
    try:
        user_id = int(uid_raw) if uid_raw is not None else None
    except Exception:
        user_id = None

    is_superuser = bool(payload.get("is_superuser") or payload.get("superuser"))
    return {
        "username": username,
        "user_id": user_id,
        "is_superuser": is_superuser,
    }

router = APIRouter()

@router.get("/admin/queue/tasks")
def admin_list_queue_tasks(limit: int = 100, offset: int = 0, current_user: "User" = Depends(get_current_user)):
    if not getattr(current_user, "is_superuser", False):
        raise HTTPException(status_code=403, detail="Superuser required")
    from app.services.generation_task_queue import list_generation_tasks
    tasks = list_generation_tasks(limit=limit, offset=offset)

    def _build_callback_diag(runtime_job: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "job_status": _normalize_generation_status(runtime_job.get("status")),
            "upstream_submit_state": str(runtime_job.get("upstream_submit_state") or "").strip() or None,
            "provider_task_id": str(runtime_job.get("provider_task_id") or "").strip() or None,
            "provider_callback_ticket": str(runtime_job.get("provider_callback_ticket") or "").strip() or None,
            "provider": str(runtime_job.get("provider") or "").strip() or None,
            "provider_alias": str(runtime_job.get("provider_alias") or "").strip() or None,
            "model": str(runtime_job.get("model") or "").strip() or None,
            "callback_submit_retries": _safe_int(runtime_job.get("callback_submit_retries"), 0),
            "callback_retry_at": runtime_job.get("callback_retry_at"),
            "started_at": runtime_job.get("started_at"),
            "finished_at": runtime_job.get("finished_at"),
            "error": str(runtime_job.get("error") or "").strip() or None,
        }

    enriched: List[Dict[str, Any]] = []
    for task in tasks:
        item = dict(task or {})
        kind = str(item.get("kind") or "").strip().lower()
        job_id = str(item.get("job_id") or "").strip()
        if kind in {"video", "image"} and job_id:
            runtime_job: Optional[Dict[str, Any]] = None
            try:
                runtime_job = _read_video_job_file(job_id) if kind == "video" else _read_image_job_file(job_id)
            except Exception:
                runtime_job = None
            if isinstance(runtime_job, dict) and runtime_job:
                item["job_runtime"] = runtime_job
                item["callback_diag"] = _build_callback_diag(runtime_job)
        enriched.append(item)

    return {"tasks": enriched}

@router.post("/admin/queue/tasks/{job_id}/cancel")
def admin_cancel_queue_task(job_id: str, current_user: "User" = Depends(get_current_user)):
    if not getattr(current_user, "is_superuser", False):
        raise HTTPException(status_code=403, detail="Superuser required")
    from app.services.generation_task_queue import cancel_generation_task
    task = cancel_generation_task(job_id, reason="Canceled by Admin")
    if isinstance(task, dict) and task:
        kind = str(task.get("kind") or "").strip().lower()
        now_iso = datetime.now(timezone.utc).isoformat()
        if kind == "image":
            _set_image_job(
                job_id,
                status="canceled",
                finished_at=now_iso,
                error="Canceled by Admin",
            )
        elif kind == "video":
            _set_video_job(
                job_id,
                status="canceled",
                finished_at=now_iso,
                error="Canceled by Admin",
            )
    return {"status": "ok", "task": task}

@router.post("/admin/queue/tasks/cancel-queued")
def admin_cancel_all_queued(current_user: "User" = Depends(get_current_user)):
    if not getattr(current_user, "is_superuser", False):
        raise HTTPException(status_code=403, detail="Superuser required")
    from app.services.generation_task_queue import cancel_generation_tasks
    count = cancel_generation_tasks(reason="Cleared queued by Admin")
    return {"status": "ok", "canceled_count": count}


@router.get("/admin/queue/stats")
def admin_get_queue_stats(
    current_user: "User" = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not getattr(current_user, "is_superuser", False):
        raise HTTPException(status_code=403, detail="Superuser required")

    from app.services.generation_task_queue import get_generation_queue_runtime_stats

    runtime_stats = get_generation_queue_runtime_stats()

    with GENERATION_CALLBACK_LOCK:
        _prune_generation_callback_locked()
        callback_store_count = len(GENERATION_CALLBACK_STORE)

    with GENERATION_CALLBACK_ASYNC_INFLIGHT_LOCK:
        callback_async_inflight = len(GENERATION_CALLBACK_ASYNC_INFLIGHT)
    with IMAGE_CALLBACK_PERSIST_INFLIGHT_LOCK:
        image_callback_persist_inflight = len(IMAGE_CALLBACK_PERSIST_INFLIGHT)
    with VIDEO_CALLBACK_PERSIST_INFLIGHT_LOCK:
        video_callback_persist_inflight = len(VIDEO_CALLBACK_PERSIST_INFLIGHT)

    with IMAGE_JOB_LOCK:
        _prune_image_jobs_locked()
        image_jobs = [dict(job or {}) for job in IMAGE_JOB_STORE.values()]
    with VIDEO_JOB_LOCK:
        _prune_video_jobs_locked()
        video_jobs = [dict(job or {}) for job in VIDEO_JOB_STORE.values()]

    active_statuses = {"queued", "submit", "running", "processing", "pending", "storing_asset", "waiting_callback", "callback_processing"}
    callback_pending_count = 0
    callback_waiting_count = 0
    callback_retrying_count = 0
    callback_timeout_failed_count = 0
    compensation_candidate_count = 0
    active_polling_like_count = 0

    pure_callback_mode_auto = _queue_cfg_bool("pure_callback_mode_auto", True)
    pure_callback_mode_manual = _queue_cfg_bool("pure_callback_mode", False)
    pure_callback_mode_startup_public_deploy = bool(
        str(os.getenv("RENDER_EXTERNAL_URL") or "").strip()
        or str(os.getenv("RENDER") or "").strip()
        or str(os.getenv("RAILWAY_STATIC_URL") or "").strip()
        or str(os.getenv("RAILWAY_PUBLIC_DOMAIN") or "").strip()
        or str(os.getenv("VERCEL_URL") or "").strip()
    )
    pure_callback_mode_effective = bool(_is_pure_callback_mode_enabled())

    for job in image_jobs + video_jobs:
        status = _normalize_generation_status(job.get("status"))
        callback_ticket = _extract_job_provider_callback_ticket(job)
        upstream_state = str(job.get("upstream_submit_state") or "").strip().lower()
        retry_count = _safe_int(job.get("callback_submit_retries"), 0)
        has_retry_at = bool(str(job.get("callback_retry_at") or "").strip())
        is_timeout_failed = bool(
            status == "failed"
            and "timed out" in str(job.get("error") or "").strip().lower()
        )

        is_waiting_callback = bool(status == "waiting_callback" or ("callback_pending" in upstream_state))

        if is_waiting_callback and callback_ticket:
            callback_pending_count += 1
        if callback_ticket and is_waiting_callback:
            callback_waiting_count += 1
        if retry_count > 0 or has_retry_at:
            callback_retrying_count += 1
        if is_timeout_failed and callback_ticket:
            callback_timeout_failed_count += 1
        if callback_ticket and (status in {"queued", "submit", "running", "waiting_callback", "callback_processing"} or is_timeout_failed):
            compensation_candidate_count += 1

        if status in active_statuses and (not pure_callback_mode_effective):
            active_polling_like_count += 1

    retry_enabled = _queue_cfg_bool("callback_loss_retry_enabled", True)
    retry_after_seconds = _queue_cfg_int("callback_loss_retry_after_seconds", 1200, minimum=60, maximum=86400)
    max_submit_retries = _queue_cfg_int("callback_loss_max_submit_retries", 1, minimum=0, maximum=5)
    callback_slots_total = int(GENERATION_CALLBACK_FINALIZE_MAX_CONCURRENCY)
    callback_slots_in_use = max(0, min(callback_slots_total, int(callback_async_inflight)))
    callback_slots_available = max(0, callback_slots_total - callback_slots_in_use)

    retry_worker_slots_total = 1
    retry_worker_slots_in_use = 1 if bool(_CALLBACK_COMPENSATION_STARTED) else 0
    retry_worker_slots_available = max(0, retry_worker_slots_total - retry_worker_slots_in_use)
    retry_scan_batch_total = _queue_cfg_int("callback_compensation_scan_batch_size", 10, minimum=1, maximum=200)
    image_share_percent = _queue_cfg_int("callback_compensation_image_share_percent", 50, minimum=0, maximum=100)
    retry_scan_batch_in_use = max(0, min(int(retry_scan_batch_total), int(compensation_candidate_count)))
    retry_scan_batch_available = max(0, int(retry_scan_batch_total) - int(retry_scan_batch_in_use))
    analyze_scene_dedup = _collect_analyze_scene_dedup_stats(db)

    return {
        "runtime": runtime_stats,
        "analyze_scene_dedup": analyze_scene_dedup,
        "callback": {
            "store_count": callback_store_count,
            "async_inflight": callback_async_inflight,
            "image_persist_inflight": image_callback_persist_inflight,
            "video_persist_inflight": video_callback_persist_inflight,
            "requested_threads": _queue_cfg_int(
                "callback_threads",
                int(DEFAULT_QUEUE_CONFIG["callback_threads"]),
                minimum=1,
                maximum=1000,
            ),
            "effective_threads": int(GENERATION_CALLBACK_FINALIZE_MAX_CONCURRENCY),
            "slots_total": callback_slots_total,
            "slots_in_use": callback_slots_in_use,
            "slots_available": callback_slots_available,
            "pending_jobs": callback_pending_count,
            "waiting_finalize_jobs": callback_waiting_count,
        },
        "polling": {
            "pure_callback_mode_effective": pure_callback_mode_effective,
            "pure_callback_mode_auto": bool(pure_callback_mode_auto),
            "pure_callback_mode_manual": bool(pure_callback_mode_manual),
            "startup_public_deploy_detected": bool(pure_callback_mode_startup_public_deploy),
            "startup_mode": "auto_public" if pure_callback_mode_auto and pure_callback_mode_startup_public_deploy else ("auto_local" if pure_callback_mode_auto else ("manual_on" if pure_callback_mode_manual else "manual_off")),
            "active_polling_like_jobs": active_polling_like_count,
            "queue_poll_seconds": float(runtime_stats.get("workers", {}).get("queue_poll_seconds") or 0.0),
        },
        "callback_loss_retry": {
            "enabled": retry_enabled,
            "retry_after_seconds": retry_after_seconds,
            "max_submit_retries": max_submit_retries,
            "retrying_jobs": callback_retrying_count,
            "timeout_failed_jobs": callback_timeout_failed_count,
            "compensation_candidate_jobs": compensation_candidate_count,
            "scan_enabled": _queue_cfg_bool("callback_compensation_scan_enabled", True),
            "scan_interval_seconds": _queue_cfg_int("callback_compensation_scan_interval_seconds", 60, minimum=10, maximum=600),
            "scan_batch_size": retry_scan_batch_total,
            "scan_image_share_percent": image_share_percent,
            "scan_batch_in_use": retry_scan_batch_in_use,
            "scan_batch_available": retry_scan_batch_available,
            "worker_started": bool(_CALLBACK_COMPENSATION_STARTED),
            "worker_slots_total": retry_worker_slots_total,
            "worker_slots_in_use": retry_worker_slots_in_use,
            "worker_slots_available": retry_worker_slots_available,
        },
    }

media_service = MediaGenerationService()
logger = logging.getLogger("api_logger")


def _release_db_connection(db: Optional[Session], reason: str = "") -> None:
    if db is None:
        return
    try:
        db.rollback()
    except Exception as exc:
        if reason:
            logger.debug("[db_release] rollback skipped | reason=%s error=%s", reason, exc)
        else:
            logger.debug("[db_release] rollback skipped | error=%s", exc)
    try:
        db.close()
    except Exception as exc:
        if reason:
            logger.debug("[db_release] close skipped | reason=%s error=%s", reason, exc)
        else:
            logger.debug("[db_release] close skipped | error=%s", exc)


def _snapshot_user_principal(user: Any) -> SimpleNamespace:
    """Build a detached-safe user snapshot for long-running/background tasks."""
    def _safe_attr(name: str, default: Any = None) -> Any:
        if user is None:
            return default
        try:
            state = inspect(user)
        except Exception:
            state = None

        if state is not None and hasattr(state, "dict"):
            state_dict = getattr(state, "dict", {}) or {}
            if name in state_dict:
                return state_dict.get(name, default)
            if name == "id":
                identity = getattr(state, "identity", None)
                if identity and len(identity) > 0:
                    return identity[0]
            # Detached/expired ORM attrs must not trigger DB refresh here.
            return default

        if isinstance(user, dict):
            return user.get(name, default)
        user_dict = getattr(user, "__dict__", None)
        if isinstance(user_dict, dict) and name in user_dict:
            return user_dict.get(name, default)
        try:
            return getattr(user, name, default)
        except Exception:
            return default

    return SimpleNamespace(
        id=int(_safe_attr("id", 0) or 0),
        username=str(_safe_attr("username", "") or ""),
        email=str(_safe_attr("email", "") or "") or None,
        full_name=str(_safe_attr("full_name", "") or "") or None,
        avatar_url=str(_safe_attr("avatar_url", "") or "") or None,
        is_active=int(_safe_attr("is_active", 1) or 1),
        is_superuser=bool(_safe_attr("is_superuser", False)),
        is_authorized=bool(_safe_attr("is_authorized", False)),
        is_system=bool(_safe_attr("is_system", False)),
        account_status=int(_safe_attr("account_status", 1) or 1),
        email_verified=bool(_safe_attr("email_verified", False)),
        credits=int(_safe_attr("credits", 0) or 0),
        preferences=_safe_attr("preferences", None),
    )

_VIDEO_DEDUP_WINDOW_SECONDS = 20
_VIDEO_DEDUP_MAX_CACHE = 256
_VIDEO_INFLIGHT_BY_KEY: Dict[str, asyncio.Task] = {}
_VIDEO_RECENT_RESULTS_BY_KEY: Dict[str, Dict[str, Any]] = {}
_VIDEO_DEDUP_LOCK = asyncio.Lock()


def _digest_text_for_dedup(value: Any) -> str:
    text = str(value or "")
    if not text:
        return ""
    if len(text) > 200:
        return f"sha1:{hashlib.sha1(text.encode('utf-8', errors='ignore')).hexdigest()}"
    return text


def _compact_for_dedup(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _compact_for_dedup(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, list):
        return [_compact_for_dedup(v) for v in value]
    if isinstance(value, tuple):
        return [_compact_for_dedup(v) for v in value]
    if isinstance(value, str):
        return _digest_text_for_dedup(value)
    return value


def _build_video_dedup_key(req: "VideoGenerationRequest", user_id: int) -> str:
    payload = {
        "user_id": int(user_id or 0),
        "provider": req.provider,
        "model": req.model,
        "prompt": req.prompt,
        "negative_prompt": req.negative_prompt,
        "ref_image_url": req.ref_image_url,
        "ref_video_urls": req.ref_video_urls,
        "image_urls": req.image_urls,
        "last_frame_url": req.last_frame_url,
        "duration": req.duration,
        "aspect_ratio": req.aspect_ratio,
        "mode": req.mode,
        "ref_mode": req.ref_mode,
        "sound": req.sound,
        "multi_shots": req.multi_shots,
        "multi_prompt": req.multi_prompt,
        "kling_elements": req.kling_elements,
        "project_id": req.project_id,
        "shot_id": req.shot_id,
        "shot_number": req.shot_number,
        "shot_name": req.shot_name,
        "entity_name": req.entity_name,
        "subject_name": req.subject_name,
        "asset_type": req.asset_type,
        "keyframes": req.keyframes,
        "seed": req.seed,
    }
    compact = _compact_for_dedup(payload)
    stable = json.dumps(compact, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(stable.encode("utf-8", errors="ignore")).hexdigest()


def _cleanup_video_dedup_cache(now_ts: float) -> None:
    stale_keys = [
        key for key, item in _VIDEO_RECENT_RESULTS_BY_KEY.items()
        if (now_ts - float(item.get("ts") or 0.0)) > _VIDEO_DEDUP_WINDOW_SECONDS
    ]
    for key in stale_keys:
        _VIDEO_RECENT_RESULTS_BY_KEY.pop(key, None)

    if len(_VIDEO_RECENT_RESULTS_BY_KEY) > _VIDEO_DEDUP_MAX_CACHE:
        ordered = sorted(
            _VIDEO_RECENT_RESULTS_BY_KEY.items(),
            key=lambda item: float((item[1] or {}).get("ts") or 0.0),
        )
        overflow = len(_VIDEO_RECENT_RESULTS_BY_KEY) - _VIDEO_DEDUP_MAX_CACHE
        for key, _ in ordered[:overflow]:
            _VIDEO_RECENT_RESULTS_BY_KEY.pop(key, None)

ANALYSIS_PROMPT_TEMPLATE_SYNTAX_RULES: Dict[str, Dict[str, Any]] = {
    "characters": {
        "required_text_fields": [
            "subject_no", "name", "name_en", "base_name_en", "description_cn",
            "gender", "role", "archetype", "appearance_cn", "clothing",
            "action_characteristics", "generation_prompt_cn", "generation_prompt_en",
            "negative_prompt_en", "anchor_description",
        ],
        "required_present_fields": ["visual_dependencies", "dependency_strategy"],
        "dependency_strategy_required_keys": ["type", "logic"],
    },
    "props": {
        "required_text_fields": [
            "subject_no", "name", "name_en", "base_name_en", "type",
            "description_cn", "generation_prompt_cn", "generation_prompt_en",
            "negative_prompt_en", "anchor_description",
        ],
        "required_present_fields": ["visual_dependencies", "dependency_strategy"],
        "dependency_strategy_required_keys": ["type", "logic"],
    },
    "environments": {
        "required_text_fields": [
            "subject_no", "name", "name_en", "base_name_en", "atmosphere",
            "visual_params", "description_cn", "generation_prompt_cn",
            "generation_prompt_en", "negative_prompt_en", "anchor_description",
        ],
        "required_present_fields": ["visual_dependencies", "dependency_strategy"],
        "dependency_strategy_required_keys": ["type", "logic"],
    },
    "posters": {
        "required_text_fields": [
            "subject_no", "name", "name_en", "base_name_en", "atmosphere",
            "visual_params", "description_cn", "generation_prompt_cn",
            "generation_prompt_en", "negative_prompt_en", "anchor_description",
        ],
        "required_present_fields": ["visual_dependencies", "dependency_strategy"],
        "dependency_strategy_required_keys": ["type", "logic"],
    },
}

_ANALYZE_SCENE_DEDUP_WINDOW_SECONDS = max(15, int(os.getenv("ANALYZE_SCENE_DEDUP_WINDOW_SECONDS", "360")))
_ANALYZE_SCENE_DEDUP_PRUNE_INTERVAL_SECONDS = max(
    30,
    int(os.getenv("ANALYZE_SCENE_DEDUP_PRUNE_INTERVAL_SECONDS", "120") or 120),
)
_ANALYZE_SCENE_SEGMENT_TIMEOUT_SECONDS = max(30, int(os.getenv("ANALYZE_SCENE_SEGMENT_TIMEOUT_SECONDS", "900") or 900))
_ANALYZE_SCENE_CONTINUATION_SEGMENT_HARD_CAP = max(2, min(32, int(os.getenv("ANALYZE_SCENE_CONTINUATION_SEGMENT_HARD_CAP", "12") or 12)))
_ANALYZE_SCENE_OUTPUT_CHAR_HARD_CAP = max(20000, int(os.getenv("ANALYZE_SCENE_OUTPUT_CHAR_HARD_CAP", "120000") or 120000))
_ANALYZE_SCENE_DEDUP_TABLE_READY = False
_ANALYZE_SCENE_DEDUP_TABLE_LOCK = threading.Lock()
_ANALYZE_SCENE_DEDUP_LAST_PRUNE_TS = 0.0
_ANALYZE_SCENE_DEDUP_PRUNE_LOCK = threading.Lock()


async def _await_analyze_scene_segment(messages: List[Dict[str, Any]], config: Dict[str, Any]) -> Dict[str, Any]:
    started_at = time.monotonic()
    llm_task = asyncio.create_task(llm_service.chat_completion_with_fallback(messages, config))
    try:
        return await asyncio.wait_for(asyncio.shield(llm_task), timeout=_ANALYZE_SCENE_SEGMENT_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        logger.warning(
            "[analyze_scene] segment_soft_timeout episode_provider=%s model=%s timeout=%ss elapsed=%.2fs; continuing to wait for provider result",
            (config or {}).get("provider"),
            (config or {}).get("model"),
            _ANALYZE_SCENE_SEGMENT_TIMEOUT_SECONDS,
            time.monotonic() - started_at,
        )
        return await llm_task


def _script_analysis_function_api_name(function_name: Any) -> str:
    raw = str(function_name or "").strip()
    if raw.startswith("script_analysis"):
        return "script_analysis"
    return raw or "script_analysis"


def _resolve_script_analysis_dropdown_order(db: Session, function_name: Any) -> List[int]:
    resolved_function_name = _script_analysis_function_api_name(function_name)
    row = db.query(models.FunctionAPIConfig).filter(
        models.FunctionAPIConfig.function_name == resolved_function_name,
    ).first()
    raw_settings = row.api_settings if row and isinstance(row.api_settings, list) else []

    def _priority(item: Dict[str, Any]) -> int:
        try:
            return int(item.get("priority") or 0)
        except Exception:
            return 0

    ordered_ids: List[int] = []
    for item in sorted(
        [entry for entry in raw_settings if isinstance(entry, dict)],
        key=_priority,
        reverse=True,
    ):
        try:
            setting_id = int(item.get("system_api_id") or 0)
        except Exception:
            setting_id = 0
        if setting_id > 0 and setting_id not in ordered_ids:
            ordered_ids.append(setting_id)
    return ordered_ids


def _select_script_analysis_api_order(ordered_ids: List[int], selected_system_api_id: Any) -> Tuple[Optional[int], List[int]]:
    try:
        selected_id = int(selected_system_api_id or 0)
    except Exception:
        selected_id = 0

    if selected_id > 0 and selected_id in ordered_ids:
        primary_id = selected_id
    elif ordered_ids:
        primary_id = ordered_ids[0]
    else:
        primary_id = None

    fallback_ids = [setting_id for setting_id in ordered_ids if setting_id != primary_id]
    return primary_id, fallback_ids


def _resolve_script_analysis_dropdown_llm_config(
    db: Session,
    current_user_id: int,
    function_name: Any,
    system_api_id: Any,
    *,
    context: str,
) -> Tuple[Dict[str, Any], int, List[int], List[int]]:
    dropdown_order_ids = _resolve_script_analysis_dropdown_order(db, function_name)
    selected_dropdown_id, dropdown_fallback_ids = _select_script_analysis_api_order(
        dropdown_order_ids,
        system_api_id,
    )
    if not selected_dropdown_id:
        raise HTTPException(status_code=400, detail="Script analysis API dropdown has no configured LLM API.")

    primary_configs = agent_service.get_fallback_configs_by_ids([selected_dropdown_id])
    config = primary_configs[0] if primary_configs else {}
    if not config or not config.get("api_key"):
        raise HTTPException(status_code=400, detail="Selected script analysis LLM API is unavailable. Please check the API dropdown settings.")

    cfg_for_route = config.get("config") if isinstance(config.get("config"), dict) else {}
    cfg_for_route["__override_fallback_candidates"] = dropdown_fallback_ids
    cfg_for_route["__selection_source"] = "script_analysis_dropdown_priority"
    cfg_for_route["__resolved_user_id"] = current_user_id
    cfg_for_route["__resolved_category"] = "LLM"
    cfg_for_route["__dropdown_order_ids"] = dropdown_order_ids
    cfg_for_route["__active_retry_attempts"] = 1
    config["config"] = cfg_for_route

    logger.info(
        "[%s][routing] source=dropdown_priority function_name=%s requested_system_api_id=%s selected_system_api_id=%s fallback_ids=%s provider=%s model=%s",
        context,
        function_name,
        system_api_id,
        selected_dropdown_id,
        dropdown_fallback_ids,
        (config or {}).get("provider"),
        (config or {}).get("model"),
    )
    return config, selected_dropdown_id, dropdown_fallback_ids, dropdown_order_ids


def _resolve_story_generator_script_analysis_llm_config(
    db: Session,
    user_id: int,
    *,
    function_name: Any = "script_analysis",
    system_api_id: Any = None,
    context: str,
    project_global_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    resolved_fn = _script_analysis_function_api_name(function_name)
    llm_config, _, _, _ = _resolve_script_analysis_dropdown_llm_config(
        db,
        user_id,
        resolved_fn,
        system_api_id,
        context=context,
    )
    if project_global_info is not None:
        llm_config = _inject_project_creativity_temperature(
            llm_config,
            project_global_info,
            context=context,
        )
    return llm_config


def _normalize_analyze_scene_dedup_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(k): _normalize_analyze_scene_dedup_payload(v)
            for k, v in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_normalize_analyze_scene_dedup_payload(v) for v in value]
    if isinstance(value, str):
        return value.strip()
    return value


def _build_analyze_scene_dedup_key(user_id: int, request: AnalyzeSceneRequest) -> str:
    payload = {
        "user_id": int(user_id or 0),
        "analysis_trace_id": getattr(request, "analysis_trace_id", None),
        "project_id": getattr(request, "project_id", None),
        "episode_id": getattr(request, "episode_id", None),
        "text": getattr(request, "text", None),
        "prompt_file": getattr(request, "prompt_file", None),
        "system_prompt": getattr(request, "system_prompt", None),
        "project_metadata": getattr(request, "project_metadata", None),
        "scene_analysis_mode": getattr(request, "scene_analysis_mode", None),
        "scene_analysis_features": getattr(request, "scene_analysis_features", None),
        "analysis_attention_notes": getattr(request, "analysis_attention_notes", None),
        "reuse_subject_assets": getattr(request, "reuse_subject_assets", None),
        "include_negative_prompt": getattr(request, "include_negative_prompt", True),
        "function_name": getattr(request, "function_name", None),
        "system_api_id": getattr(request, "system_api_id", None),
    }
    stable_payload = _normalize_analyze_scene_dedup_payload(payload)
    stable_json = json.dumps(stable_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(stable_json.encode("utf-8", errors="ignore")).hexdigest()


def _ensure_analyze_scene_dedup_table_ready() -> None:
    global _ANALYZE_SCENE_DEDUP_TABLE_READY
    if _ANALYZE_SCENE_DEDUP_TABLE_READY:
        return
    with _ANALYZE_SCENE_DEDUP_TABLE_LOCK:
        if _ANALYZE_SCENE_DEDUP_TABLE_READY:
            return
        ddl = """
        CREATE TABLE IF NOT EXISTS analyze_scene_dedup_tasks (
            dedup_key TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            task_id TEXT NOT NULL,
            updated_at REAL NOT NULL
        )
        """
        index_ddl = """
        CREATE INDEX IF NOT EXISTS idx_analyze_scene_dedup_tasks_updated_at
        ON analyze_scene_dedup_tasks (updated_at)
        """
        with engine.begin() as conn:
            conn.execute(text(ddl))
            conn.execute(text(index_ddl))
        _ANALYZE_SCENE_DEDUP_TABLE_READY = True


def _prune_analyze_scene_dedup_rows(db: Session, now_ts: float) -> None:
    global _ANALYZE_SCENE_DEDUP_LAST_PRUNE_TS
    with _ANALYZE_SCENE_DEDUP_PRUNE_LOCK:
        if (float(now_ts) - float(_ANALYZE_SCENE_DEDUP_LAST_PRUNE_TS)) < float(_ANALYZE_SCENE_DEDUP_PRUNE_INTERVAL_SECONDS):
            return
        _ANALYZE_SCENE_DEDUP_LAST_PRUNE_TS = float(now_ts)

    # Keep rows slightly longer than dedup window to reduce table churn.
    cutoff = float(now_ts) - float(max(_ANALYZE_SCENE_DEDUP_WINDOW_SECONDS * 2, 600))
    result = db.execute(
        text(
            """
            DELETE FROM analyze_scene_dedup_tasks
            WHERE updated_at < :cutoff
            """
        ),
        {"cutoff": cutoff},
    )
    pruned = int(result.rowcount or 0)
    if pruned > 0:
        logger.info(
            "[analyze_scene][dedup] pruned rows=%s cutoff_age_s=%s",
            pruned,
            int(max(_ANALYZE_SCENE_DEDUP_WINDOW_SECONDS * 2, 600)),
        )


def _get_analyze_scene_dedup_row(db: Session, dedup_key: str) -> Optional[Dict[str, Any]]:
    row = db.execute(
        text(
            """
            SELECT dedup_key, user_id, task_id, updated_at
            FROM analyze_scene_dedup_tasks
            WHERE dedup_key = :dedup_key
            """
        ),
        {"dedup_key": str(dedup_key)},
    ).mappings().first()
    return dict(row) if row else None


def _delete_analyze_scene_dedup_row(db: Session, dedup_key: str) -> None:
    db.execute(
        text(
            """
            DELETE FROM analyze_scene_dedup_tasks
            WHERE dedup_key = :dedup_key
            """
        ),
        {"dedup_key": str(dedup_key)},
    )


def _insert_analyze_scene_dedup_row_if_absent(db: Session, *, dedup_key: str, user_id: int, task_id: str, now_ts: float) -> bool:
    result = db.execute(
        text(
            """
            INSERT INTO analyze_scene_dedup_tasks (dedup_key, user_id, task_id, updated_at)
            VALUES (:dedup_key, :user_id, :task_id, :updated_at)
            ON CONFLICT(dedup_key) DO NOTHING
            """
        ),
        {
            "dedup_key": str(dedup_key),
            "user_id": int(user_id),
            "task_id": str(task_id),
            "updated_at": float(now_ts),
        },
    )
    return int(result.rowcount or 0) > 0


def _upsert_analyze_scene_dedup_row(db: Session, *, dedup_key: str, user_id: int, task_id: str, now_ts: float) -> None:
    db.execute(
        text(
            """
            INSERT INTO analyze_scene_dedup_tasks (dedup_key, user_id, task_id, updated_at)
            VALUES (:dedup_key, :user_id, :task_id, :updated_at)
            ON CONFLICT(dedup_key) DO UPDATE SET
                user_id = excluded.user_id,
                task_id = excluded.task_id,
                updated_at = excluded.updated_at
            """
        ),
        {
            "dedup_key": str(dedup_key),
            "user_id": int(user_id),
            "task_id": str(task_id),
            "updated_at": float(now_ts),
        },
    )


def _collect_analyze_scene_dedup_stats(db: Session, now_ts: Optional[float] = None) -> Dict[str, Any]:
    _ensure_analyze_scene_dedup_table_ready()
    ts_now = float(now_ts or time.time())

    total_rows = int(
        (
            db.execute(text("SELECT COUNT(*) AS cnt FROM analyze_scene_dedup_tasks")).mappings().first()
            or {}
        ).get("cnt")
        or 0
    )
    window_cutoff = ts_now - float(_ANALYZE_SCENE_DEDUP_WINDOW_SECONDS)
    window_rows = db.execute(
        text(
            """
            SELECT dedup_key, task_id, updated_at
            FROM analyze_scene_dedup_tasks
            WHERE updated_at >= :window_cutoff
            ORDER BY updated_at DESC
            LIMIT 500
            """
        ),
        {"window_cutoff": float(window_cutoff)},
    ).mappings().all()

    running_like = 0
    terminal_like = 0
    unknown_like = 0
    provisional_rows = 0
    for row in window_rows:
        task_id = str((row or {}).get("task_id") or "").strip()
        if task_id.startswith("pending-"):
            provisional_rows += 1
            continue
        info = _get_task_status(task_id) or {}
        status = str(info.get("status") or "").strip().lower()
        if status in {"pending", "running"}:
            running_like += 1
        elif status in {"completed", "failed", "canceled"}:
            terminal_like += 1
        else:
            unknown_like += 1

    stale_rows = max(0, int(total_rows) - int(len(window_rows)))
    return {
        "rows_total": int(total_rows),
        "rows_in_window": int(len(window_rows)),
        "rows_stale": int(stale_rows),
        "rows_running_like": int(running_like),
        "rows_terminal_like": int(terminal_like),
        "rows_unknown_like": int(unknown_like),
        "rows_provisional": int(provisional_rows),
        "dedup_window_seconds": int(_ANALYZE_SCENE_DEDUP_WINDOW_SECONDS),
        "prune_interval_seconds": int(_ANALYZE_SCENE_DEDUP_PRUNE_INTERVAL_SECONDS),
    }

# ── Generic async-task polling endpoint ──────────────────────────────────
@router.get("/tasks/{task_id}")
def poll_task(task_id: str, current_user: User = Depends(get_current_user)):
    info = _get_task_status(task_id, user_id=current_user.id)
    if info is None:
        info = _generation_task_status(task_id, user_id=current_user.id)
    if info is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return info


@router.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: str, current_user: User = Depends(get_current_user)):
    _cancel_generation_task_ref(task_id, user_id=current_user.id, reason="Task canceled by user request")
    info = _cancel_task(task_id, user_id=current_user.id, reason="Task canceled by user request")
    if info is None:
        info = _generation_task_status(task_id, user_id=current_user.id)
    if info is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return info

IMAGE_JOB_STORE: Dict[str, Dict[str, Any]] = {}
IMAGE_JOB_LOCK = threading.Lock()
# Tighter defaults for 4GB-class hosts; override via env if needed.
IMAGE_JOB_TTL_SECONDS = max(300, int(os.getenv("IMAGE_JOB_TTL_SECONDS", "1800")))
IMAGE_JOB_MAX_ITEMS = max(50, int(os.getenv("IMAGE_JOB_MAX_ITEMS", "200")))
IMAGE_SUBMIT_IDEMPOTENCY_STORE: Dict[str, Dict[str, Any]] = {}
IMAGE_ACTIVE_SCOPE_STORE: Dict[str, str] = {}
IMAGE_SUBMIT_IDEMPOTENCY_TTL_SECONDS = max(30, int(os.getenv("IMAGE_SUBMIT_IDEMPOTENCY_TTL_SECONDS", "120")))
IMAGE_JOB_FILE_DIR = os.path.join(settings.UPLOAD_DIR, "_image_jobs")
IMAGE_JOB_TASKS: Dict[str, Any] = {}

VIDEO_JOB_STORE: Dict[str, Dict[str, Any]] = {}
VIDEO_JOB_LOCK = threading.Lock()
VIDEO_JOB_TTL_SECONDS = max(300, int(os.getenv("VIDEO_JOB_TTL_SECONDS", "1800")))
VIDEO_JOB_MAX_ITEMS = max(50, int(os.getenv("VIDEO_JOB_MAX_ITEMS", "200")))
VIDEO_SUBMIT_IDEMPOTENCY_STORE: Dict[str, Dict[str, Any]] = {}
VIDEO_ACTIVE_SCOPE_STORE: Dict[str, str] = {}
VIDEO_SUBMIT_IDEMPOTENCY_TTL_SECONDS = max(30, int(os.getenv("VIDEO_SUBMIT_IDEMPOTENCY_TTL_SECONDS", "120")))
VIDEO_JOB_FILE_DIR = os.path.join(settings.UPLOAD_DIR, "_video_jobs")
VIDEO_JOB_TASKS: Dict[str, Any] = {}

IMAGE_JOB_MAX_RUNNING_SECONDS = max(120, int(os.getenv("IMAGE_JOB_MAX_RUNNING_SECONDS", "900")))
VIDEO_JOB_MAX_RUNNING_SECONDS = max(120, int(os.getenv("VIDEO_JOB_MAX_RUNNING_SECONDS", "1200")))
# Running-timeout only after the worker has claimed the job (started_at set).
# "queued" waits for capacity / prior dependency work and must not burn this budget;
# abandoned queue age is handled separately by the generation task queue sweeper.
_JOB_TIMEOUT_CHECK_STATUSES = frozenset({"running", "submit", "waiting_callback", "callback_processing"})

GENERATION_CALLBACK_STORE: Dict[str, Dict[str, Any]] = {}
GENERATION_CALLBACK_LOCK = threading.Lock()
GENERATION_CALLBACK_TTL_SECONDS = max(300, int(os.getenv("GENERATION_CALLBACK_TTL_SECONDS", "3600")))
GENERATION_CALLBACK_MAX_ITEMS = max(200, int(os.getenv("GENERATION_CALLBACK_MAX_ITEMS", "1500")))
GENERATION_CALLBACK_FILE_DIR = os.path.join(settings.UPLOAD_DIR, "_generation_callbacks")
GENERATION_CALLBACK_MAX_BYTES = max(4096, int(os.getenv("GENERATION_CALLBACK_MAX_BYTES", "65536")))
GENERATION_CALLBACK_NO_MATCH_LOG_THROTTLE_SECONDS = max(5, int(os.getenv("GENERATION_CALLBACK_NO_MATCH_LOG_THROTTLE_SECONDS", "30")))
GENERATION_CALLBACK_NO_MATCH_LOG_MAX_ITEMS = max(200, int(os.getenv("GENERATION_CALLBACK_NO_MATCH_LOG_MAX_ITEMS", "2000")))
GENERATION_CALLBACK_NO_MATCH_LOG_CACHE: Dict[str, float] = {}
GENERATION_CALLBACK_NO_MATCH_LOG_LOCK = threading.Lock()
_POOL_CAPACITY = max(1, int(DB_POOL_CAPACITY_EFFECTIVE or 0))
_WEB_CONCURRENCY = max(1, int(os.getenv("WEB_CONCURRENCY", "1") or 1))
_PER_PROCESS_POOL_BUDGET = max(1, _POOL_CAPACITY // _WEB_CONCURRENCY)
_CALLBACK_FINALIZE_CAP = max(1, min(10, _PER_PROCESS_POOL_BUDGET // 4))
_DEFAULT_CALLBACK_THREADS = int(DEFAULT_QUEUE_CONFIG["callback_threads"])
GENERATION_CALLBACK_FINALIZE_MAX_CONCURRENCY = max(
    1,
    min(int(_q_conf.get("callback_threads", _DEFAULT_CALLBACK_THREADS)), _CALLBACK_FINALIZE_CAP),
)
GENERATION_CALLBACK_FINALIZE_SEMAPHORE = asyncio.Semaphore(GENERATION_CALLBACK_FINALIZE_MAX_CONCURRENCY)
GENERATION_CALLBACK_ASYNC_INFLIGHT_TTL_SECONDS = max(10, int(os.getenv("GENERATION_CALLBACK_ASYNC_INFLIGHT_TTL_SECONDS", "120") or 120))
GENERATION_CALLBACK_ASYNC_INFLIGHT_MAX_ITEMS = max(200, int(os.getenv("GENERATION_CALLBACK_ASYNC_INFLIGHT_MAX_ITEMS", "4000") or 4000))
GENERATION_CALLBACK_ASYNC_INFLIGHT: Dict[str, float] = {}
GENERATION_CALLBACK_ASYNC_INFLIGHT_LOCK = threading.Lock()
IMAGE_CALLBACK_PERSIST_INFLIGHT_TTL_SECONDS = max(30, int(os.getenv("IMAGE_CALLBACK_PERSIST_INFLIGHT_TTL_SECONDS", "600") or 600))
IMAGE_CALLBACK_PERSIST_INFLIGHT_MAX_ITEMS = max(200, int(os.getenv("IMAGE_CALLBACK_PERSIST_INFLIGHT_MAX_ITEMS", "8000") or 8000))
IMAGE_CALLBACK_PERSIST_INFLIGHT: Dict[str, float] = {}
IMAGE_CALLBACK_PERSIST_INFLIGHT_LOCK = threading.Lock()
VIDEO_CALLBACK_PERSIST_INFLIGHT_TTL_SECONDS = max(30, int(os.getenv("VIDEO_CALLBACK_PERSIST_INFLIGHT_TTL_SECONDS", "600") or 600))
VIDEO_CALLBACK_PERSIST_INFLIGHT_MAX_ITEMS = max(200, int(os.getenv("VIDEO_CALLBACK_PERSIST_INFLIGHT_MAX_ITEMS", "8000") or 8000))
VIDEO_CALLBACK_PERSIST_INFLIGHT: Dict[str, float] = {}
VIDEO_CALLBACK_PERSIST_INFLIGHT_LOCK = threading.Lock()
GENERATION_CALLBACK_JOB_FILE_SCAN_MAX_FILES = max(200, int(os.getenv("GENERATION_CALLBACK_JOB_FILE_SCAN_MAX_FILES", "2000") or 2000))
GENERATION_CALLBACK_JOB_MATCH_MAX_ITEMS = max(1, int(os.getenv("GENERATION_CALLBACK_JOB_MATCH_MAX_ITEMS", "8") or 8))
WEBHOOK_REPLAY_MAX_ITEMS = max(500, int(os.getenv("WEBHOOK_REPLAY_MAX_ITEMS", "6000")))
WEBHOOK_REPLAY_STORE: Dict[str, float] = {}
WEBHOOK_REPLAY_LOCK = threading.Lock()
_UNSIGNED_WEBHOOK_WARNING_EMITTED = False

if int(_q_conf.get("callback_threads", _DEFAULT_CALLBACK_THREADS)) > GENERATION_CALLBACK_FINALIZE_MAX_CONCURRENCY:
    logger.warning(
        "generation callback finalize concurrency capped | requested=%s capped=%s pool_capacity=%s web_concurrency=%s per_process_pool_budget=%s",
        int(_q_conf.get("callback_threads", _DEFAULT_CALLBACK_THREADS)),
        GENERATION_CALLBACK_FINALIZE_MAX_CONCURRENCY,
        _POOL_CAPACITY,
        _WEB_CONCURRENCY,
        _PER_PROCESS_POOL_BUDGET,
    )

SHOT_MEDIA_BATCH_CANCEL_EVENTS: Dict[int, threading.Event] = {}
SHOT_MEDIA_BATCH_CANCEL_LOCK = threading.Lock()
EPISODE_SCENE_JOB_THREADS: Dict[int, threading.Thread] = {}
SCENE_AI_SHOTS_BATCH_THREADS: Dict[int, threading.Thread] = {}
SHOT_MEDIA_BATCH_THREADS: Dict[int, threading.Thread] = {}
EPISODE_SCENE_JOB_THREADS_LOCK = threading.Lock()
SCENE_AI_SHOTS_BATCH_THREADS_LOCK = threading.Lock()
SHOT_MEDIA_BATCH_THREADS_LOCK = threading.Lock()

_GENERATION_JOB_POOL_CACHE_TTL_SECONDS = max(1.0, float(os.getenv("GENERATION_JOB_POOL_CACHE_TTL_SECONDS", "3") or 3.0))
_GENERATION_JOB_POOL_CACHE_MAX_ITEMS = max(32, int(os.getenv("GENERATION_JOB_POOL_CACHE_MAX_ITEMS", "256") or 256))
_GENERATION_JOB_STALE_DELETE_SECONDS = max(300, int(os.getenv("GENERATION_JOB_STALE_DELETE_SECONDS", "172800") or 172800))
_GENERATION_JOB_POOL_CACHE_LOCK = threading.Lock()
_GENERATION_JOB_POOL_CACHE: Dict[str, Dict[str, Any]] = {}

ASSET_REGISTRATION_LOCK = threading.Lock()


def _generation_task_status(task_ref: Any, *, user_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    if isinstance(task_ref, str):
        try:
            from app.services.generation_task_queue import get_generation_task_status

            queue_info = get_generation_task_status(task_ref)
            if queue_info is not None:
                return queue_info
        except Exception:
            pass
        return _get_task_status(task_ref, user_id=user_id)
    if isinstance(task_ref, asyncio.Task):
        return {"status": "running" if not task_ref.done() else "completed"}
    return None


def _generation_task_is_active(task_ref: Any, *, user_id: Optional[int] = None) -> bool:
    info = _generation_task_status(task_ref, user_id=user_id)
    return str((info or {}).get("status") or "").strip().lower() in {"queued", "submit", "pending", "running", "waiting_callback", "callback_processing"}


def _cancel_generation_task_ref(task_ref: Any, *, user_id: Optional[int] = None, reason: str = "Task canceled by user") -> None:
    if isinstance(task_ref, str):
        try:
            from app.services.generation_task_queue import cancel_generation_task

            cancel_generation_task(task_ref, reason=reason)
        except Exception:
            pass
        try:
            _cancel_task(task_ref, user_id=user_id, reason=reason)
        except Exception:
            pass
        return
    if isinstance(task_ref, asyncio.Task):
        try:
            task_ref.cancel()
        except Exception:
            pass


def _submit_generation_background_task(
    *,
    job_id: str,
    kind: str,
    user_id: int,
    payload: Dict[str, Any],
) -> str:
    from app.services.generation_task_queue import enqueue_generation_task

    return enqueue_generation_task(job_id=job_id, kind=kind, user_id=user_id, payload=payload)


async def _process_generation_queue_task(kind: str, job_id: str, user_id: int, payload: Dict[str, Any]) -> None:
    """Async processor - does NOT block while awaiting API responses.
    
    KEY CHANGE: Now uses await instead of asyncio.run()
    This allows the event loop to handle other tasks while waiting for generation.
    """
    safe_kind = str(kind or "").strip().lower()
    req_payload = dict(payload or {})
    if safe_kind == "montage":
        _set_task_status(job_id, status="running")
        project_id = int(req_payload.get("project_id") or 0)
        items_payload = req_payload.get("items") or []
        if project_id <= 0:
            raise ValueError("Montage task missing project_id")
        if not isinstance(items_payload, list) or not items_payload:
            raise ValueError("Montage task missing items")
        try:
            url = create_montage(project_id, items_payload, user_id=user_id)
        except Exception as exc:
            _set_task_status(job_id, status="failed", error=str(exc), error_code=500)
            raise
        _set_task_status(job_id, status="completed", result={"url": url})
        return
    if safe_kind == "image":
        provider_callback_ticket = f"image-job-{job_id}"
        provider_callback_url = ""
        try:
            provider_callback_url = str(media_service._resolve_provider_callback_url({}, provider_callback_ticket) or "").strip()
        except Exception:
            provider_callback_url = ""
        return await _run_generate_image_job(
            job_id,
            int(user_id),
            req_payload,
            provider_callback_ticket=provider_callback_ticket,
            provider_callback_url=provider_callback_url,
        )
    if safe_kind == "video":
        provider_callback_ticket = f"video-job-{job_id}"
        provider_callback_url = ""
        try:
            provider_callback_url = str(media_service._resolve_provider_callback_url({}, provider_callback_ticket) or "").strip()
        except Exception:
            provider_callback_url = ""
        return await _run_generate_video_job(
            job_id,
            int(user_id),
            req_payload,
            provider_callback_ticket=provider_callback_ticket,
            provider_callback_url=provider_callback_url,
        )
    raise ValueError(f"Unsupported generation queue task kind: {kind}")


def start_generation_queue_worker() -> None:
    from app.services.generation_task_queue import start_generation_task_worker

    logger.info(
        "generation callback mode at startup | pure_callback_mode=%s auto=%s",
        _is_pure_callback_mode_enabled(),
        _queue_cfg_bool("pure_callback_mode_auto", True),
    )
    start_generation_task_worker(_process_generation_queue_task)
    _start_callback_compensation_worker()


_CALLBACK_COMPENSATION_STARTED = False
_CALLBACK_COMPENSATION_LOCK = threading.Lock()


def _run_callback_compensation_once() -> None:
    if not _queue_cfg_bool("callback_compensation_scan_enabled", True):
        return

    safe_batch = _queue_cfg_int("callback_compensation_scan_batch_size", 10, minimum=1, maximum=200)
    image_share_percent = _queue_cfg_int("callback_compensation_image_share_percent", 50, minimum=0, maximum=100)
    retry_enabled = _queue_cfg_bool("callback_loss_retry_enabled", True)
    retry_after_seconds = _queue_cfg_int("callback_loss_retry_after_seconds", 1200, minimum=60, maximum=86400)
    timeout_retry_after_seconds = min(retry_after_seconds, 120)
    max_submit_retries = _queue_cfg_int("callback_loss_max_submit_retries", 1, minimum=0, maximum=5)

    now_ts = time.time()
    candidates: List[Tuple[str, str, Dict[str, Any]]] = []
    image_candidates: List[Tuple[str, Dict[str, Any]]] = []
    video_candidates: List[Tuple[str, Dict[str, Any]]] = []

    def _collect_callback_candidates(
        store_items: List[Tuple[str, Dict[str, Any]]],
    ) -> List[Tuple[str, Dict[str, Any]]]:
        collected: List[Tuple[str, Dict[str, Any]]] = []
        for job_id, payload in store_items:
            job = dict(payload or {})
            status = _normalize_generation_status(job.get("status"))
            is_timeout_failed = (
                status == "failed"
                and "timed out" in str(job.get("error") or "").strip().lower()
            )
            if status not in {"queued", "submit", "running", "waiting_callback", "callback_processing"} and not is_timeout_failed:
                continue
            callback_ticket = _extract_job_provider_callback_ticket(job)
            if not callback_ticket:
                continue
            collected.append((str(job_id), job))
        return collected

    with IMAGE_JOB_LOCK:
        _prune_image_jobs_locked()
        image_items = [(job_id, dict(payload or {})) for job_id, payload in IMAGE_JOB_STORE.items()]
    with VIDEO_JOB_LOCK:
        _prune_video_jobs_locked()
        video_items = [(job_id, dict(payload or {})) for job_id, payload in VIDEO_JOB_STORE.items()]

    image_candidates = _collect_callback_candidates(image_items)
    video_candidates = _collect_callback_candidates(video_items)

    configured_image_quota = int(round((safe_batch * image_share_percent) / 100.0))
    configured_image_quota = max(0, min(safe_batch, configured_image_quota))
    configured_video_quota = max(0, safe_batch - configured_image_quota)
    image_quota = min(configured_image_quota, len(image_candidates))
    video_quota = min(configured_video_quota, len(video_candidates))
    selected_count = image_quota + video_quota
    remaining_quota = max(0, safe_batch - selected_count)

    image_remaining = max(0, len(image_candidates) - image_quota)
    video_remaining = max(0, len(video_candidates) - video_quota)
    if remaining_quota > 0:
        if image_remaining >= video_remaining and image_remaining > 0:
            image_extra = min(remaining_quota, image_remaining)
            image_quota += image_extra
            remaining_quota -= image_extra
        if remaining_quota > 0 and video_remaining > 0:
            video_extra = min(remaining_quota, video_remaining)
            video_quota += video_extra
            remaining_quota -= video_extra
        if remaining_quota > 0 and image_remaining > 0:
            image_extra = min(remaining_quota, len(image_candidates) - image_quota)
            image_quota += image_extra

    candidates.extend([("image", job_id, job) for job_id, job in image_candidates[:image_quota]])
    candidates.extend([("video", job_id, job) for job_id, job in video_candidates[:video_quota]])

    if not candidates:
        return

    from app.services.generation_task_queue import get_generation_task_status, mark_generation_task_status_external, requeue_generation_task

    for kind, job_id, job in candidates:
        callback_ticket = _extract_job_provider_callback_ticket(job)
        if not callback_ticket:
            continue

        if kind == "image":
            job = _maybe_finalize_stuck_job(
                kind="image",
                job_id=job_id,
                job=job,
                set_job_func=_set_image_job,
                task_store=IMAGE_JOB_TASKS,
                lock=IMAGE_JOB_LOCK,
                timeout_seconds=IMAGE_JOB_MAX_RUNNING_SECONDS,
            )
        else:
            job = _maybe_finalize_stuck_job(
                kind="video",
                job_id=job_id,
                job=job,
                set_job_func=_set_video_job,
                task_store=VIDEO_JOB_TASKS,
                lock=VIDEO_JOB_LOCK,
                timeout_seconds=VIDEO_JOB_MAX_RUNNING_SECONDS,
            )
        if _normalize_generation_status(job.get("status")) == "failed":
            continue

        upstream_state = str(job.get("upstream_submit_state") or "").strip().lower()
        if "callback_pending" in upstream_state:
            mark_generation_task_status_external(job_id, status="waiting_callback", error=None)

        callback_payload = _get_generation_callback_payload(callback_ticket)
        if callback_payload:
            if kind == "image":
                _maybe_finalize_image_job_from_grsai_callback(job_id, dict(job))
            else:
                _maybe_finalize_video_job_from_provider_callback(job_id, dict(job))
            continue

        if not retry_enabled:
            continue

        status = _normalize_generation_status(job.get("status"))
        is_timeout_failed = (
            status == "failed"
            and "timed out" in str(job.get("error") or "").strip().lower()
        )
        if is_timeout_failed:
            timeout_base_dt = _parse_iso_datetime(job.get("finished_at") or job.get("started_at") or job.get("created_at"))
            if not timeout_base_dt:
                continue
            elapsed_seconds = max(0, int(now_ts - timeout_base_dt.timestamp()))
            if elapsed_seconds < timeout_retry_after_seconds:
                continue
        else:
            started_dt = _parse_iso_datetime(job.get("started_at") or job.get("created_at"))
            if not started_dt:
                continue
            elapsed_seconds = max(0, int(now_ts - started_dt.timestamp()))
            if elapsed_seconds < retry_after_seconds:
                continue

        retry_attempts = _safe_int(job.get("callback_submit_retries"), 0)
        if retry_attempts >= max_submit_retries:
            if elapsed_seconds >= retry_after_seconds:
                max_running_seconds = (
                    VIDEO_JOB_MAX_RUNNING_SECONDS if kind == "video" else IMAGE_JOB_MAX_RUNNING_SECONDS
                )
                timeout_message = (
                    f"{kind} job callback wait exhausted after {elapsed_seconds}s "
                    f"(retries={retry_attempts}/{max_submit_retries}, limit={max_running_seconds}s)"
                )
                if kind == "image":
                    _set_image_job(
                        job_id,
                        status="failed",
                        finished_at=now_bj_iso(),
                        error=timeout_message,
                        upstream_submit_state="callback_wait_exhausted",
                    )
                else:
                    _set_video_job(
                        job_id,
                        status="failed",
                        finished_at=now_bj_iso(),
                        error=timeout_message,
                        upstream_submit_state="callback_wait_exhausted",
                    )
                mark_generation_task_status_external(job_id, status="failed", error=timeout_message)
                logger.warning(
                    "[%sJob] callback wait exhausted | job_id=%s callback_ticket=%s elapsed_seconds=%s retries=%s/%s",
                    "Image" if kind == "image" else "Video",
                    job_id,
                    callback_ticket,
                    elapsed_seconds,
                    retry_attempts,
                    max_submit_retries,
                )
            continue

        queue_row = get_generation_task_status(job_id) or {}
        payload_json = str(queue_row.get("payload_json") or "{}").strip() or "{}"
        try:
            payload = json.loads(payload_json)
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}

        try:
            requeue_generation_task(job_id, reason=None)
            if kind == "image":
                _set_image_job(
                    job_id,
                    status="queued",
                    started_at=None,
                    finished_at=None,
                    error=None,
                    upstream_submit_state="callback_timeout_retry_requeued" if is_timeout_failed else "callback_retry_requeued",
                    callback_submit_retries=retry_attempts + 1,
                    callback_retry_at=now_bj_iso(),
                )
                logger.warning(
                    "[ImageJob] callback compensation requeued | job_id=%s callback_ticket=%s elapsed_seconds=%s retry=%s/%s timeout_failed=%s",
                    job_id,
                    callback_ticket,
                    elapsed_seconds,
                    retry_attempts + 1,
                    max_submit_retries,
                    is_timeout_failed,
                )
            else:
                _set_video_job(
                    job_id,
                    status="queued",
                    started_at=None,
                    finished_at=None,
                    error=None,
                    upstream_submit_state="callback_timeout_retry_requeued" if is_timeout_failed else "callback_retry_requeued",
                    callback_submit_retries=retry_attempts + 1,
                    callback_retry_at=now_bj_iso(),
                )
                logger.warning(
                    "[VideoJob] callback compensation requeued | job_id=%s callback_ticket=%s elapsed_seconds=%s retry=%s/%s timeout_failed=%s",
                    job_id,
                    callback_ticket,
                    elapsed_seconds,
                    retry_attempts + 1,
                    max_submit_retries,
                    is_timeout_failed,
                )
        except Exception as exc:
            logger.warning(
                "[%sJob] callback compensation requeue failed | job_id=%s callback_ticket=%s error=%s",
                "Image" if kind == "image" else "Video",
                job_id,
                callback_ticket,
                exc,
            )


def _callback_compensation_thread_main() -> None:
    while True:
        try:
            _run_callback_compensation_once()
        except Exception:
            logger.exception("[CallbackCompensation] worker loop failed")
        interval_seconds = _queue_cfg_int("callback_compensation_scan_interval_seconds", 60, minimum=10, maximum=600)
        time.sleep(interval_seconds)


def _start_callback_compensation_worker() -> None:
    global _CALLBACK_COMPENSATION_STARTED
    if _CALLBACK_COMPENSATION_STARTED:
        return
    with _CALLBACK_COMPENSATION_LOCK:
        if _CALLBACK_COMPENSATION_STARTED:
            return
        thread = threading.Thread(
            target=_callback_compensation_thread_main,
            daemon=True,
            name="generation-callback-compensation",
        )
        thread.start()
        _CALLBACK_COMPENSATION_STARTED = True
        logger.info("[CallbackCompensation] worker started")


def _prune_generation_job_pool_cache_locked(now_ts: float) -> None:
    stale_keys = [
        key
        for key, payload in _GENERATION_JOB_POOL_CACHE.items()
        if (now_ts - float((payload or {}).get("ts") or 0.0)) > _GENERATION_JOB_POOL_CACHE_TTL_SECONDS
    ]
    for key in stale_keys:
        _GENERATION_JOB_POOL_CACHE.pop(key, None)

    if len(_GENERATION_JOB_POOL_CACHE) > _GENERATION_JOB_POOL_CACHE_MAX_ITEMS:
        ordered = sorted(
            _GENERATION_JOB_POOL_CACHE.items(),
            key=lambda item: float(((item[1] or {}).get("ts") or 0.0)),
        )
        overflow = len(_GENERATION_JOB_POOL_CACHE) - _GENERATION_JOB_POOL_CACHE_MAX_ITEMS
        for key, _ in ordered[:overflow]:
            _GENERATION_JOB_POOL_CACHE.pop(key, None)


def _build_generation_job_pool_cache_key(
    *,
    user_id: int,
    is_superuser: bool,
    kind: str,
    running_only: bool,
    limit: int,
) -> str:
    return f"{int(user_id)}|{1 if is_superuser else 0}|{kind}|{1 if running_only else 0}|{int(limit)}"


def _read_generation_job_pool_cache(key: str) -> Optional[Dict[str, Any]]:
    now_ts = time.time()
    with _GENERATION_JOB_POOL_CACHE_LOCK:
        _prune_generation_job_pool_cache_locked(now_ts)
        hit = _GENERATION_JOB_POOL_CACHE.get(str(key))
        if not hit:
            return None
        return copy.deepcopy(hit.get("payload"))


def _write_generation_job_pool_cache(key: str, payload: Dict[str, Any]) -> None:
    now_ts = time.time()
    with _GENERATION_JOB_POOL_CACHE_LOCK:
        _prune_generation_job_pool_cache_locked(now_ts)
        _GENERATION_JOB_POOL_CACHE[str(key)] = {
            "ts": now_ts,
            "payload": copy.deepcopy(payload),
        }


def _clear_generation_job_pool_cache() -> None:
    with _GENERATION_JOB_POOL_CACHE_LOCK:
        _GENERATION_JOB_POOL_CACHE.clear()


def _is_generation_job_stale(payload: Dict[str, Any], *, now_dt: Optional[datetime] = None) -> bool:
    anchor = (
        _parse_iso_datetime(payload.get("updated_at"))
        or _parse_iso_datetime(payload.get("started_at"))
        or _parse_iso_datetime(payload.get("created_at"))
        or _parse_iso_datetime(payload.get("finished_at"))
    )
    if not anchor:
        return False
    baseline = now_dt or datetime.utcnow()
    return (baseline - anchor).total_seconds() > _GENERATION_JOB_STALE_DELETE_SECONDS


def _register_episode_worker(store: Dict[int, threading.Thread], lock: threading.Lock, episode_id: int, worker: threading.Thread) -> None:
    with lock:
        store[int(episode_id)] = worker


def _clear_episode_worker(store: Dict[int, threading.Thread], lock: threading.Lock, episode_id: int) -> None:
    with lock:
        store.pop(int(episode_id), None)


def _is_episode_worker_alive(store: Dict[int, threading.Thread], lock: threading.Lock, episode_id: int) -> bool:
    with lock:
        worker = store.get(int(episode_id))
        if not worker:
            return False
        alive = bool(worker.is_alive())
        if not alive:
            store.pop(int(episode_id), None)
        return alive


def _prune_generation_callback_locked() -> None:
    now = time.time()
    stale_keys: List[str] = []
    for ticket, payload in GENERATION_CALLBACK_STORE.items():
        created_at_raw = payload.get("received_ts")
        try:
            created_ts = float(created_at_raw)
        except Exception:
            created_ts = 0.0
        if not created_ts or (now - created_ts) > GENERATION_CALLBACK_TTL_SECONDS:
            stale_keys.append(ticket)

    for ticket in stale_keys:
        GENERATION_CALLBACK_STORE.pop(ticket, None)

    if len(GENERATION_CALLBACK_STORE) > GENERATION_CALLBACK_MAX_ITEMS:
        ordered = sorted(
            GENERATION_CALLBACK_STORE.items(),
            key=lambda item: float((item[1] or {}).get("received_ts") or 0.0),
        )
        overflow = len(GENERATION_CALLBACK_STORE) - GENERATION_CALLBACK_MAX_ITEMS
        for ticket, _ in ordered[:overflow]:
            GENERATION_CALLBACK_STORE.pop(ticket, None)


def _set_generation_callback_payload(ticket: str, payload: Dict[str, Any]) -> None:
    stable_ticket = str(ticket or "").strip()
    if not stable_ticket:
        return

    normalized_payload = _compact_generation_callback_payload(payload)

    callback_record = {
        "ticket": stable_ticket,
        "received_ts": time.time(),
        "received_at": now_bj_iso(),
        "payload": normalized_payload,
    }

    with GENERATION_CALLBACK_LOCK:
        _prune_generation_callback_locked()
        GENERATION_CALLBACK_STORE[stable_ticket] = dict(callback_record)

    _write_generation_callback_file(stable_ticket, callback_record)


def _generation_callback_file_path(ticket: str) -> str:
    safe_ticket = re.sub(r"[^a-zA-Z0-9_-]", "", str(ticket or "").strip())
    return os.path.join(GENERATION_CALLBACK_FILE_DIR, f"{safe_ticket}.json")


def _write_generation_callback_file(ticket: str, payload: Dict[str, Any]) -> None:
    try:
        os.makedirs(GENERATION_CALLBACK_FILE_DIR, exist_ok=True)
        path = _generation_callback_file_path(ticket)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
    except Exception as e:
        logger.warning("failed to persist generation callback file ticket=%s err=%s", ticket, e)


def _read_generation_callback_file(ticket: str) -> Optional[Dict[str, Any]]:
    try:
        path = _generation_callback_file_path(ticket)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data["ticket"] = data.get("ticket") or str(ticket)
            return data
    except Exception as e:
        logger.warning("failed to read generation callback file ticket=%s err=%s", ticket, e)
    return None


def _extract_callback_task_id(payload: Dict[str, Any]) -> str:
    if not isinstance(payload, dict):
        return ""

    direct_candidates = (
        payload.get("id"),
        payload.get("task_id"),
        payload.get("taskId"),
        payload.get("job_id"),
        payload.get("jobId"),
    )
    for value in direct_candidates:
        normalized = str(value or "").strip()
        if normalized:
            return normalized

    data = payload.get("data")
    if isinstance(data, dict):
        nested_candidates = (
            data.get("id"),
            data.get("task_id"),
            data.get("taskId"),
            data.get("job_id"),
            data.get("jobId"),
        )
        for value in nested_candidates:
            normalized = str(value or "").strip()
            if normalized:
                return normalized

        for block_key in ("output", "result"):
            block = data.get(block_key)
            if isinstance(block, dict):
                for value in (
                    block.get("id"),
                    block.get("task_id"),
                    block.get("taskId"),
                    block.get("job_id"),
                    block.get("jobId"),
                ):
                    normalized = str(value or "").strip()
                    if normalized:
                        return normalized

    return ""


def _extract_callback_status(payload: Dict[str, Any]) -> str:
    if not isinstance(payload, dict):
        return ""

    def _first_status(source: Dict[str, Any], path_prefix: str, log_matches: bool = True) -> str:
        if not isinstance(source, dict):
            return ""
        for key in ("status", "state", "task_status", "taskStatus", "job_status", "jobStatus", "phase"):
            value = str(source.get(key) or "").strip()
            if value:
                if log_matches:
                    logger.debug(f"[DEBUG-CB-STATUS] Found status '{value}' at {path_prefix}.{key}")
                return value
        return ""

    # Check exactly root.status first without triggering nested matches yet, 
    # to prioritize authoritative top-level success/running over nested failure indicators.
    root_val = _first_status(payload, "root", log_matches=True)
    if root_val and root_val.lower() in {"success", "succeeded", "completed", "done", "running", "queued", "pending", "in_progress", "in-progress", "storing_asset"}:
        return root_val

    for candidate, path in (
        (root_val, "root"),
        (_first_status(payload.get("eventData") if isinstance(payload.get("eventData"), dict) else {}, "eventData", log_matches=True), "eventData"),
        (_first_status(payload.get("data") if isinstance(payload.get("data"), dict) else {}, "data", log_matches=True), "data"),
    ):
        if candidate:
            return candidate

    data = payload.get("data")
    if isinstance(data, dict):
        for block_key in ("output", "result"):
            block = data.get(block_key)
            candidate = _first_status(block if isinstance(block, dict) else {}, f"data.{block_key}", log_matches=True)
            if candidate:
                return candidate

    # Some providers serialize nested payload blocks as JSON strings.
    for json_like_key in ("eventData", "data", "resultJson", "responseJson", "payload", "param"):
        raw_block = payload.get(json_like_key)
        if not isinstance(raw_block, str):
            continue
        text = raw_block.strip()
        if not text or text[0] not in "[{":
            continue
        try:
            parsed_block = json.loads(text)
        except Exception:
            continue
        if isinstance(parsed_block, dict):
            candidate = _first_status(parsed_block, f"{json_like_key}<json>", log_matches=True)
            if candidate:
                return candidate
            nested_data = parsed_block.get("data")
            if isinstance(nested_data, dict):
                candidate = _first_status(nested_data, f"{json_like_key}<json>.data", log_matches=True)
                if candidate:
                    return candidate
                
    logger.debug("[DEBUG-CB-STATUS] Could not extract status from payload")
    return ""


def _extract_generation_job_id_from_ticket(kind: str, callback_ticket: str) -> str:
    stable_kind = str(kind or "").strip().lower()
    stable_ticket = str(callback_ticket or "").strip()
    if not stable_ticket:
        return ""

    if stable_kind == "image":
        prefix = "image-job-"
    elif stable_kind == "video":
        prefix = "video-job-"
    else:
        return ""

    if not stable_ticket.startswith(prefix):
        return ""

    job_id = stable_ticket[len(prefix):].strip()
    if re.fullmatch(r"[0-9a-fA-F]{32}", job_id):
        return job_id.lower()
    return ""


def _should_log_callback_no_match(kind: str, callback_ticket: str) -> bool:
    stable_key = f"{str(kind or '').strip().lower()}:{str(callback_ticket or '').strip()}"
    if not stable_key.strip(":"):
        return False

    now_ts = time.time()
    with GENERATION_CALLBACK_NO_MATCH_LOG_LOCK:
        stale_keys = [
            key
            for key, seen_ts in GENERATION_CALLBACK_NO_MATCH_LOG_CACHE.items()
            if (now_ts - float(seen_ts or 0.0)) > GENERATION_CALLBACK_NO_MATCH_LOG_THROTTLE_SECONDS
        ]
        for key in stale_keys:
            GENERATION_CALLBACK_NO_MATCH_LOG_CACHE.pop(key, None)

        if len(GENERATION_CALLBACK_NO_MATCH_LOG_CACHE) > GENERATION_CALLBACK_NO_MATCH_LOG_MAX_ITEMS:
            ordered = sorted(
                GENERATION_CALLBACK_NO_MATCH_LOG_CACHE.items(),
                key=lambda item: float(item[1] or 0.0),
            )
            overflow = len(GENERATION_CALLBACK_NO_MATCH_LOG_CACHE) - GENERATION_CALLBACK_NO_MATCH_LOG_MAX_ITEMS
            for key, _ in ordered[:overflow]:
                GENERATION_CALLBACK_NO_MATCH_LOG_CACHE.pop(key, None)

        previous_seen = float(GENERATION_CALLBACK_NO_MATCH_LOG_CACHE.get(stable_key) or 0.0)
        if previous_seen and (now_ts - previous_seen) < GENERATION_CALLBACK_NO_MATCH_LOG_THROTTLE_SECONDS:
            return False

        GENERATION_CALLBACK_NO_MATCH_LOG_CACHE[stable_key] = now_ts
        return True


def _should_log_callback_missing_ticket(job_id: str) -> bool:
    stable_job_id = str(job_id or "").strip()
    if not stable_job_id:
        return False

    now_ts = time.time()
    stable_key = f"missing-ticket:{stable_job_id}"
    with GENERATION_CALLBACK_NO_MATCH_LOG_LOCK:
        previous_seen = float(GENERATION_CALLBACK_NO_MATCH_LOG_CACHE.get(stable_key) or 0.0)
        if previous_seen and (now_ts - previous_seen) < GENERATION_CALLBACK_NO_MATCH_LOG_THROTTLE_SECONDS:
            return False

        GENERATION_CALLBACK_NO_MATCH_LOG_CACHE[stable_key] = now_ts
        return True


def _compact_generation_callback_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}

    try:
        stable_json = json.dumps(payload, ensure_ascii=False, default=str, separators=(",", ":"))
    except Exception:
        stable_json = ""

    if stable_json and len(stable_json.encode("utf-8", errors="ignore")) <= GENERATION_CALLBACK_MAX_BYTES:
        return dict(payload)

    callback_task_id = _extract_callback_task_id(payload)
    callback_status_raw = _extract_callback_status(payload)
    callback_status = _normalize_generation_status(callback_status_raw)
    callback_result_url = _extract_job_result_url(payload)

    if not callback_status and callback_result_url:
        callback_status = "succeeded"

    compact: Dict[str, Any] = {
        "status": callback_status or callback_status_raw or None,
        "task_id": callback_task_id or None,
        "taskId": callback_task_id or None,
        "result_url": callback_result_url or None,
        "error": str(payload.get("error") or "").strip() or None,
        "failure_reason": str(payload.get("failure_reason") or "").strip() or None,
        "payload_truncated": True,
    }

    # Preserve compact usage / KIE creditsConsumed for callback-time billing when truncated.
    try:
        from app.services.media_service import _extract_provider_task_usage, _normalize_provider_task_usage

        compact_usage = _normalize_provider_task_usage(_extract_provider_task_usage(payload))
        if compact_usage:
            # Drop bulky nested audit blobs if present.
            compact["usage"] = {
                k: v
                for k, v in compact_usage.items()
                if k not in {"raw_task"} and not isinstance(v, (dict, list))
            } or compact_usage
            kie_credits = compact_usage.get("kie_credits_consumed") or compact_usage.get("creditsConsumed")
            if kie_credits not in (None, ""):
                compact["creditsConsumed"] = kie_credits
                compact["credits_consumed"] = kie_credits
                compact["kie_credits_consumed"] = kie_credits
    except Exception:
        pass

    data_block = payload.get("data")
    if isinstance(data_block, dict):
        data_status_raw = _extract_callback_status(data_block)
        data_status = _normalize_generation_status(data_status_raw) or data_status_raw
        compact_data = {
            "id": str(data_block.get("id") or data_block.get("task_id") or data_block.get("taskId") or "").strip() or None,
            "status": data_status or None,
            "result_url": _extract_job_result_url(data_block) or None,
            "error": str(data_block.get("error") or data_block.get("message") or "").strip() or None,
        }
        nested_usage = data_block.get("usage")
        if isinstance(nested_usage, dict) and nested_usage:
            compact_data["usage"] = nested_usage
            if not compact.get("usage"):
                compact["usage"] = nested_usage
        for credit_key in ("creditsConsumed", "credits_consumed", "kie_credits_consumed"):
            if data_block.get(credit_key) not in (None, ""):
                compact_data[credit_key] = data_block.get(credit_key)
                compact.setdefault(credit_key, data_block.get(credit_key))
        compact["data"] = compact_data

    # RunningHub TASK_END: usage lives under eventData.usage (and status/error already flattened).
    event_data = payload.get("eventData")
    if isinstance(event_data, dict):
        event_usage = event_data.get("usage")
        compact_event: Dict[str, Any] = {
            "status": str(event_data.get("status") or "").strip() or None,
            "errorCode": str(event_data.get("errorCode") or "").strip() or None,
            "errorMessage": str(event_data.get("errorMessage") or "").strip() or None,
            "taskId": str(event_data.get("taskId") or event_data.get("task_id") or "").strip() or None,
        }
        if isinstance(event_usage, dict) and event_usage:
            compact_event["usage"] = event_usage
            if not compact.get("usage"):
                compact["usage"] = event_usage
        compact["eventData"] = {k: v for k, v in compact_event.items() if v not in (None, "", [])}

    if stable_json:
        compact["payload_size_bytes"] = len(stable_json.encode("utf-8", errors="ignore"))
        compact["payload_excerpt"] = stable_json[:4096]

    return {k: v for k, v in compact.items() if v not in (None, "", [])}


def _prune_webhook_replay_locked() -> None:
    now = time.time()
    ttl_seconds = max(60, int(settings.WEBHOOK_TIMESTAMP_MAX_SKEW_SECONDS) * 2)
    stale_keys: List[str] = []
    for replay_key, seen_at in WEBHOOK_REPLAY_STORE.items():
        try:
            seen_ts = float(seen_at)
        except Exception:
            seen_ts = 0.0
        if not seen_ts or (now - seen_ts) > ttl_seconds:
            stale_keys.append(replay_key)

    for replay_key in stale_keys:
        WEBHOOK_REPLAY_STORE.pop(replay_key, None)

    if len(WEBHOOK_REPLAY_STORE) > WEBHOOK_REPLAY_MAX_ITEMS:
        ordered = sorted(
            WEBHOOK_REPLAY_STORE.items(),
            key=lambda item: float(item[1] or 0.0),
        )
        overflow = len(WEBHOOK_REPLAY_STORE) - WEBHOOK_REPLAY_MAX_ITEMS
        for replay_key, _ in ordered[:overflow]:
            WEBHOOK_REPLAY_STORE.pop(replay_key, None)


def _compute_webhook_signature(task_id: str, timestamp_seconds: int, secret: str) -> str:
    message = f"{task_id}.{timestamp_seconds}"
    digest = hmac.new(
        str(secret).encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode("utf-8")


def _normalize_webhook_signature_header(raw_signature: Any) -> str:
    signature = str(raw_signature or "").strip()
    if not signature:
        return ""
    # Be tolerant of prefixed forms like: sha256=<base64>
    lower_sig = signature.lower()
    if lower_sig.startswith("sha256="):
        signature = signature.split("=", 1)[1].strip()
    return signature


def _verify_kie_webhook_request(request: Request, payload: Dict[str, Any]) -> None:
    global _UNSIGNED_WEBHOOK_WARNING_EMITTED
    secret = str(getattr(settings, "KIE_WEBHOOK_HMAC_KEY", "") or settings.WEBHOOK_HMAC_KEY or "").strip()
    
    timestamp_raw = ""
    for header_name in ("x-webhook-timestamp", "x-kie-timestamp", "x-timestamp"):
        candidate = str(request.headers.get(header_name) or "").strip()
        if candidate:
            timestamp_raw = candidate
            break

    received_signature = ""
    for header_name in ("x-webhook-signature", "x-kie-signature", "x-signature"):
        candidate = _normalize_webhook_signature_header(request.headers.get(header_name))
        if candidate:
            received_signature = candidate
            break

    # KIE does not provide webhook signature headers. Bypass.
    if not timestamp_raw or not received_signature:
        logger.warning("[WebhookVerify] Missing webhook signature headers for payload. Bypassing check for KIE compatibility.")
        return

    if not secret:
        if settings.WEBHOOK_HMAC_ALLOW_UNSIGNED:
            if not _UNSIGNED_WEBHOOK_WARNING_EMITTED:
                logger.warning("[WebhookVerify] WEBHOOK_HMAC_KEY missing; accepting unsigned callback")
                _UNSIGNED_WEBHOOK_WARNING_EMITTED = True
            return
        raise HTTPException(status_code=503, detail="Webhook signature key not configured")


    try:
        timestamp_seconds = int(timestamp_raw)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid webhook timestamp")

    now_seconds = int(time.time())
    max_skew = max(30, int(settings.WEBHOOK_TIMESTAMP_MAX_SKEW_SECONDS))
    if timestamp_seconds <= 0 or abs(now_seconds - timestamp_seconds) > max_skew:
        raise HTTPException(status_code=401, detail="Webhook timestamp expired")

    task_id = _extract_callback_task_id(payload)
    if not task_id:
        raise HTTPException(status_code=400, detail="Missing task_id in callback payload")

    expected_signature = _compute_webhook_signature(task_id, timestamp_seconds, secret)
    if len(expected_signature) != len(received_signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    if not hmac.compare_digest(expected_signature, received_signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    replay_key = f"{task_id}:{timestamp_seconds}:{received_signature}"
    with WEBHOOK_REPLAY_LOCK:
        _prune_webhook_replay_locked()
        if replay_key in WEBHOOK_REPLAY_STORE:
            raise HTTPException(status_code=401, detail="Replay webhook request rejected")
        WEBHOOK_REPLAY_STORE[replay_key] = time.time()


def _is_stale_running_payload(payload: Dict[str, Any], stale_minutes: int = 10) -> bool:
    if not isinstance(payload, dict):
        return False
    anchor = payload.get("updated_at") or payload.get("started_at") or payload.get("created_at")
    anchor_dt = _parse_iso_datetime(anchor)
    if not anchor_dt:
        return False
    return anchor_dt <= (datetime.utcnow() - timedelta(minutes=max(1, int(stale_minutes))))


def _get_shot_media_batch_cancel_event(episode_id: int, create: bool = True) -> Optional[threading.Event]:
    eid = int(episode_id)
    with SHOT_MEDIA_BATCH_CANCEL_LOCK:
        event = SHOT_MEDIA_BATCH_CANCEL_EVENTS.get(eid)
        if not event and create:
            event = threading.Event()
            SHOT_MEDIA_BATCH_CANCEL_EVENTS[eid] = event
        return event


def _set_shot_media_batch_cancel_requested(episode_id: int) -> None:
    event = _get_shot_media_batch_cancel_event(episode_id, create=True)
    if event:
        event.set()


def _reset_shot_media_batch_cancel_requested(episode_id: int) -> None:
    event = _get_shot_media_batch_cancel_event(episode_id, create=True)
    if event:
        event.clear()


def _clear_shot_media_batch_cancel_event(episode_id: int) -> None:
    eid = int(episode_id)
    with SHOT_MEDIA_BATCH_CANCEL_LOCK:
        SHOT_MEDIA_BATCH_CANCEL_EVENTS.pop(eid, None)


def _image_job_file_path(job_id: str) -> str:
    safe_job_id = re.sub(r"[^a-zA-Z0-9_-]", "", str(job_id or "").strip())
    return os.path.join(IMAGE_JOB_FILE_DIR, f"{safe_job_id}.json")


def _write_image_job_file(job_id: str, payload: Dict[str, Any]) -> None:
    try:
        from app.services.generation_task_queue import upsert_generation_job_state

        upsert_generation_job_state(kind="image", job_id=job_id, payload=payload)
    except Exception as e:
        logger.warning("failed to persist image job state in db job_id=%s err=%s", job_id, e)
    try:
        os.makedirs(IMAGE_JOB_FILE_DIR, exist_ok=True)
        path = _image_job_file_path(job_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
    except Exception as e:
        logger.warning("failed to persist image job file job_id=%s err=%s", job_id, e)


def _read_image_job_file(job_id: str) -> Optional[Dict[str, Any]]:
    try:
        from app.services.generation_task_queue import get_generation_job_state

        db_state = get_generation_job_state(kind="image", job_id=job_id)
        if isinstance(db_state, dict):
            db_state["job_id"] = db_state.get("job_id") or str(job_id)
            if "result" in db_state:
                db_state["result"] = _compact_job_result(db_state.get("result"))
            return db_state
    except Exception as e:
        logger.warning("failed to read image job state from db job_id=%s err=%s", job_id, e)
    try:
        path = _image_job_file_path(job_id)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data["job_id"] = data.get("job_id") or str(job_id)
            if "result" in data:
                data["result"] = _compact_job_result(data.get("result"))
            return data
    except Exception as e:
        logger.warning("failed to read image job file job_id=%s err=%s", job_id, e)
    return None


def _persist_data_uri_image_result(
    current_user: User,
    media_url: Optional[str],
    metadata: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    raw = str(media_url or "").strip()
    if not raw.startswith("data:image/"):
        return media_url, metadata

    marker = ";base64,"
    marker_idx = raw.find(marker)
    if marker_idx <= 5:
        raise ValueError("invalid image data URI: missing base64 marker")

    mime = raw[5:marker_idx].strip().lower()
    b64_part = raw[marker_idx + len(marker):].strip()
    if not b64_part:
        raise ValueError("invalid image data URI: empty payload")

    extension_map = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "image/bmp": ".bmp",
    }
    file_ext = extension_map.get(mime)
    if not file_ext:
        subtype = mime.split("/", 1)[1] if "/" in mime else "png"
        subtype = re.sub(r"[^a-z0-9]+", "", subtype.lower()) or "png"
        file_ext = f".{subtype}"

    binary = base64.b64decode(b64_part)
    filename = f"provider_result_{uuid.uuid4().hex[:16]}{file_ext}"

    updated_metadata = dict(metadata) if isinstance(metadata, dict) else {}
    updated_metadata["stored_from_data_uri"] = True
    updated_metadata["stored_from_data_uri_mime"] = mime
    updated_metadata["stored_from_data_uri_bytes"] = len(binary)

    uploaded = oss_storage_service.upload_bytes(
        binary,
        user_id=int(getattr(current_user, "id", 0) or 0),
        filename=filename,
        content_type=mime,
        category="generated",
        cache_control="public, max-age=31536000",
    )
    if uploaded and uploaded.get("url"):
        updated_metadata["oss"] = {
            "provider": uploaded.get("provider"),
            "bucket": uploaded.get("bucket"),
            "key": uploaded.get("key"),
            "endpoint": uploaded.get("endpoint"),
        }
        try:
            with Image.open(io.BytesIO(binary)) as img:
                updated_metadata["width"] = int(img.width)
                updated_metadata["height"] = int(img.height)
                if img.format:
                    updated_metadata["format"] = str(img.format)
        except Exception as exc:
            logger.warning("data-uri image metadata probe failed in-memory err=%s", exc)
        logger.info(
            "[ImageResultNormalize] stored provider data URI in OSS | user_id=%s bytes=%s mime=%s url=%s",
            getattr(current_user, "id", None),
            len(binary),
            mime,
            uploaded["url"],
        )
        return str(uploaded["url"]), updated_metadata

    upload_root = settings.UPLOAD_DIR
    if not os.path.isabs(upload_root):
        upload_root = os.path.abspath(upload_root)

    user_dir = os.path.join(upload_root, str(getattr(current_user, "id", "unknown")), "generated")
    os.makedirs(user_dir, exist_ok=True)
    save_path = os.path.join(user_dir, filename)
    with open(save_path, "wb") as f:
        f.write(binary)

    try:
        with Image.open(save_path) as img:
            updated_metadata["width"] = int(img.width)
            updated_metadata["height"] = int(img.height)
            if img.format:
                updated_metadata["format"] = str(img.format)
    except Exception as exc:
        logger.warning("data-uri image metadata probe failed path=%s err=%s", save_path, exc)

    relative_path = os.path.relpath(save_path, upload_root).replace("\\", "/")
    normalized_url = f"/uploads/{relative_path}"
    logger.info(
        "[ImageResultNormalize] stored provider data URI | user_id=%s bytes=%s mime=%s url=%s",
        getattr(current_user, "id", None),
        len(binary),
        mime,
        normalized_url,
    )
    return normalized_url, updated_metadata


_KIE_GENERATED_MEDIA_HOST_PATTERNS = [
    re.compile(r"(^|\.)aiquickdraw\.com$", re.IGNORECASE),
    re.compile(r"(^|\.)kie\.ai$", re.IGNORECASE),
]


def _looks_like_kie_generated_media_url(value: Any) -> bool:
    raw = str(value or "").strip()
    if not raw.lower().startswith(("http://", "https://")):
        return False
    try:
        parsed = urllib.parse.urlparse(raw)
    except Exception:
        return False
    hostname = str(parsed.hostname or "").strip().lower()
    if not hostname:
        return False
    for pattern in _KIE_GENERATED_MEDIA_HOST_PATTERNS:
        if pattern.search(hostname):
            return True
    return False


def _resolve_kie_download_api_key() -> str:
    candidates = [
        getattr(settings, "KIE_API_KEY", ""),
        os.getenv("KIE_API_KEY", ""),
        os.getenv("KIE_DOWNLOAD_API_KEY", ""),
    ]
    for candidate in candidates:
        key = str(candidate or "").strip()
        if key:
            return key
    return ""


def _resolve_kie_downloadable_url(source_url: Any) -> str:
    raw_url = str(source_url or "").strip()
    if not raw_url or not _looks_like_kie_generated_media_url(raw_url):
        return ""

    api_key = _resolve_kie_download_api_key()
    if not api_key:
        return ""

    endpoint = str(os.getenv("KIE_DOWNLOAD_URL_ENDPOINT") or "https://api.kie.ai/api/v1/common/download-url").strip()
    if not endpoint:
        return ""

    try:
        resp = requests.post(
            endpoint,
            json={"url": raw_url},
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "AIStory/1.0",
            },
            timeout=(10, 30),
        )
        if resp.status_code != 200:
            logger.info(
                "[ImageResultNormalize] KIE download-url non-200 | status=%s source_url=%s",
                resp.status_code,
                raw_url,
            )
            return ""

        data = resp.json() if resp.content else {}
        code = data.get("code") if isinstance(data, dict) else None
        candidate = str(data.get("data") or "").strip() if isinstance(data, dict) else ""
        if code in (200, "200") and candidate.lower().startswith(("http://", "https://")):
            return candidate
        return ""
    except Exception as exc:
        logger.info(
            "[ImageResultNormalize] KIE download-url resolve failed | source_url=%s err=%s",
            raw_url,
            exc,
        )
        return ""


def _persist_remote_image_result(
    current_user: User,
    media_url: Optional[str],
    metadata: Optional[Dict[str, Any]] = None,
    *,
    db: Optional[Session] = None,
) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    raw = str(media_url or "").strip()
    if not raw:
        return media_url, metadata
    if raw.startswith("/"):
        return media_url, metadata
    if not raw.lower().startswith(("http://", "https://")):
        return media_url, metadata

    try:
        parsed = urllib.parse.urlparse(raw)
    except Exception:
        return media_url, metadata

    hostname = str(parsed.hostname or "").strip().lower()
    if hostname in {"localhost", "127.0.0.1"}:
        return media_url, metadata
    if oss_storage_service.is_active_managed_url(raw, db):
        logger.info(
            "[ImageResultNormalize] skip remote localization for managed oss url | user_id=%s url=%s",
            getattr(current_user, "id", None),
            raw,
        )
        return media_url, metadata
    updated_metadata = dict(metadata) if isinstance(metadata, dict) else {}
    if _is_provider_direct_oss_url(raw, updated_metadata, db):
        updated_metadata["provider_direct_oss_url"] = True
        logger.info(
            "[ImageResultNormalize] skip localization for provider direct oss url | user_id=%s provider=%s url=%s",
            getattr(current_user, "id", None),
            str(updated_metadata.get("provider") or "").strip() or None,
            raw,
        )
        return raw, updated_metadata

    source_url = raw
    temp_filename = _extract_media_filename_from_url(raw)
    resolved_kie_download_url = _resolve_kie_downloadable_url(source_url)
    if resolved_kie_download_url and resolved_kie_download_url != raw:
        raw = resolved_kie_download_url
        try:
            parsed = urllib.parse.urlparse(raw)
        except Exception:
            parsed = urllib.parse.urlparse(source_url)
        if not temp_filename:
            temp_filename = _extract_media_filename_from_url(raw)

    max_remote_image_bytes = max(1, int(os.getenv("REMOTE_IMAGE_LOCALIZE_MAX_MB", "25"))) * 1024 * 1024

    try:
        response = requests.get(
            raw,
            stream=False,
            timeout=120,
            allow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
    except Exception as exc:
        logger.warning(
            "[ImageResultNormalize] remote image download failed | user_id=%s url=%s temp_filename=%s err=%s",
            getattr(current_user, "id", None),
            raw,
            temp_filename,
            exc,
        )
        updated_metadata = dict(metadata) if isinstance(metadata, dict) else {}
        updated_metadata["remote_localization_failed"] = True
        updated_metadata["remote_localization_error"] = str(exc)
        updated_metadata["remote_localization_source_url"] = raw
        if temp_filename:
            updated_metadata["temporary_source_filename"] = temp_filename
        return media_url, updated_metadata

    content_type = str(response.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
    if content_type and not (content_type.startswith("image/") or content_type.startswith("video/") or content_type.startswith("audio/")):
        logger.warning(
            "[ImageResultNormalize] remote media skipped non-media content | user_id=%s url=%s content_type=%s",
            getattr(current_user, "id", None),
            raw,
            content_type,
        )
        return media_url, metadata

    extension_map = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "image/bmp": ".bmp",
        "video/mp4": ".mp4",
        "video/quicktime": ".mov",
        "video/webm": ".webm",
        "video/x-msvideo": ".avi",
        "video/x-matroska": ".mkv",
        "audio/mpeg": ".mp3",
        "audio/mp3": ".mp3",
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/mp4": ".m4a",
        "audio/aac": ".aac",
        "audio/flac": ".flac",
        "audio/ogg": ".ogg",
        "audio/opus": ".opus",
    }
    file_ext = extension_map.get(content_type)
    if not file_ext:
        path_ext = os.path.splitext(parsed.path or "")[1].lower()
        if path_ext in extension_map.values():
            file_ext = ".jpg" if path_ext == ".jpeg" else path_ext
        else:
            if content_type.startswith("video/"):
                file_ext = ".mp4"
            elif content_type.startswith("audio/"):
                file_ext = ".mp3"
            else:
                file_ext = ".png"

    filename = f"provider_result_{uuid.uuid4().hex[:16]}{file_ext}"
    chunks: List[bytes] = []
    bytes_written = 0
    try:
        for chunk in response.iter_content(chunk_size=1024 * 256):
            if not chunk:
                continue
            bytes_written += len(chunk)
            if bytes_written > max_remote_image_bytes:
                raise ValueError(f"remote image too large: {bytes_written} > {max_remote_image_bytes}")
            chunks.append(chunk)
    except Exception as exc:
        logger.warning(
            "[ImageResultNormalize] remote image persistence failed | user_id=%s url=%s err=%s",
            getattr(current_user, "id", None),
            raw,
            exc,
        )
        updated_metadata = dict(metadata) if isinstance(metadata, dict) else {}
        updated_metadata["remote_localization_failed"] = True
        updated_metadata["remote_localization_error"] = str(exc)
        updated_metadata["remote_localization_source_url"] = raw
        return media_url, updated_metadata
    finally:
        try:
            response.close()
        except Exception:
            pass

    if bytes_written <= 0:
        return media_url, metadata

    binary = b"".join(chunks)

    updated_metadata = dict(metadata) if isinstance(metadata, dict) else {}
    updated_metadata["stored_from_remote_url"] = raw
    if temp_filename:
        updated_metadata["temporary_source_filename"] = temp_filename
    if resolved_kie_download_url:
        updated_metadata["stored_from_remote_url_source"] = source_url
        updated_metadata["stored_from_remote_url_resolved_via"] = "kie_download_url"
    updated_metadata["stored_from_remote_url_bytes"] = bytes_written
    if content_type:
        updated_metadata["stored_from_remote_url_content_type"] = content_type

    uploaded = oss_storage_service.upload_bytes(
        binary,
        user_id=int(getattr(current_user, "id", 0) or 0),
        filename=filename,
        content_type=content_type or f"image/{file_ext.lstrip('.')}",
        category="generated",
        cache_control="public, max-age=31536000",
    )
    if uploaded and uploaded.get("url"):
        updated_metadata["oss"] = {
            "provider": uploaded.get("provider"),
            "bucket": uploaded.get("bucket"),
            "key": uploaded.get("key"),
            "endpoint": uploaded.get("endpoint"),
        }
        try:
            with Image.open(io.BytesIO(binary)) as img:
                updated_metadata["width"] = int(img.width)
                updated_metadata["height"] = int(img.height)
                if img.format:
                    updated_metadata["format"] = str(img.format)
        except Exception as exc:
            logger.warning("remote image metadata probe failed in-memory err=%s", exc)
        logger.info(
            "[ImageResultNormalize] stored remote image in OSS | user_id=%s source_url=%s normalized_url=%s bytes=%s",
            getattr(current_user, "id", None),
            raw,
            uploaded["url"],
            bytes_written,
        )
        return str(uploaded["url"]), updated_metadata

    upload_root = settings.UPLOAD_DIR
    if not os.path.isabs(upload_root):
        upload_root = os.path.abspath(upload_root)

    user_dir = os.path.join(upload_root, str(getattr(current_user, "id", "unknown")), "generated")
    os.makedirs(user_dir, exist_ok=True)
    save_path = os.path.join(user_dir, filename)
    with open(save_path, "wb") as f:
        f.write(binary)

    try:
        with Image.open(save_path) as img:
            updated_metadata["width"] = int(img.width)
            updated_metadata["height"] = int(img.height)
            if img.format:
                updated_metadata["format"] = str(img.format)
    except Exception as exc:
        logger.warning("remote image metadata probe failed path=%s err=%s", save_path, exc)

    relative_path = os.path.relpath(save_path, upload_root).replace("\\", "/")
    normalized_url = f"/uploads/{relative_path}"
    logger.info(
        "[ImageResultNormalize] stored remote image | user_id=%s source_url=%s normalized_url=%s bytes=%s",
        getattr(current_user, "id", None),
        raw,
        normalized_url,
        bytes_written,
    )
    return normalized_url, updated_metadata


def _attach_oss_metadata_from_managed_url(metadata: Dict[str, Any], url: str) -> Dict[str, Any]:
    updated = dict(metadata)
    if isinstance(updated.get("oss"), dict):
        return updated
    pool, key = oss_storage_service._extract_managed_target(str(url or ""))
    if pool and key:
        updated["oss"] = {
            "provider": getattr(pool, "provider", None),
            "bucket": getattr(pool, "bucket", None),
            "key": key,
            "endpoint": getattr(pool, "endpoint", None),
        }
    return updated


def _oss_upload_succeeded_for_url(url: Optional[str], metadata: Optional[Dict[str, Any]] = None, db: Optional[Session] = None) -> bool:
    if isinstance(metadata, dict) and isinstance(metadata.get("oss"), dict):
        oss_meta = metadata.get("oss") or {}
        if oss_meta.get("key") and _url_matches_configured_oss(str(url or ""), metadata, db):
            return True
    if _url_matches_configured_oss(str(url or ""), metadata, db):
        return True
    return False


def _url_matches_configured_oss(
    url: Optional[str],
    metadata: Optional[Dict[str, Any]] = None,
    db: Optional[Session] = None,
) -> bool:
    raw = str(url or "").strip()
    if not raw or _is_ephemeral_provider_media_url(raw):
        return False
    if oss_storage_service.is_active_managed_url(raw, db):
        return True

    meta = metadata if isinstance(metadata, dict) else {}
    oss_meta = meta.get("oss") if isinstance(meta.get("oss"), dict) else {}
    if oss_meta.get("key"):
        pool, key = oss_storage_service.match_active_pool(raw, db)
        if pool and key and str(oss_meta.get("key") or "").strip() == str(key).strip():
            return True

    if not raw.lower().startswith(("http://", "https://")):
        return False

    signatures = oss_storage_service.get_active_url_signatures(db)
    if not signatures.get("oss_enabled"):
        return False

    try:
        parsed = urllib.parse.urlparse(raw)
        hostname = str(parsed.hostname or "").strip().lower()
    except Exception:
        return False
    if not hostname:
        return False

    allowed_hosts = set(signatures.get("hostnames") or [])
    if hostname in allowed_hosts:
        return True

    for base in signatures.get("public_base_urls") or []:
        normalized_base = str(base or "").strip().rstrip("/")
        if normalized_base and (raw.startswith(f"{normalized_base}/") or raw == normalized_base):
            return True

    if bool(meta.get("provider_direct_oss_url")):
        provider = str(meta.get("provider") or "").strip().lower()
        configured_providers = {str(item or "").strip().lower() for item in (signatures.get("providers") or [])}
        if provider and provider in configured_providers:
            return True

    return False


def _is_provider_direct_oss_url(
    url: Optional[str],
    metadata: Optional[Dict[str, Any]] = None,
    db: Optional[Session] = None,
) -> bool:
    raw = str(url or "").strip()
    if not raw.lower().startswith(("http://", "https://")):
        return False
    if _is_ephemeral_provider_media_url(raw):
        return False
    meta = metadata if isinstance(metadata, dict) else {}
    if bool(meta.get("provider_direct_oss_url")):
        return True
    provider = str(meta.get("provider") or "").strip().lower()
    if provider != "grsai":
        return False
    if _url_matches_configured_oss(raw, metadata, db):
        return True
    try:
        parsed = urllib.parse.urlparse(raw)
        hostname = str(parsed.hostname or "").strip().lower()
    except Exception:
        return False
    if not hostname:
        return False
    return bool(
        re.match(r"(^|.+\.)clouddn\.com$", hostname, re.IGNORECASE)
        or re.match(r"(^|.+\.)qiniucs\.com$", hostname, re.IGNORECASE)
        or re.match(r"(^|.+\.)woola\.fun$", hostname, re.IGNORECASE)
        or ".bkt." in hostname
        or "backblaze" in hostname
    )


def _persist_remote_video_result(
    current_user: User,
    media_url: Optional[str],
    metadata: Optional[Dict[str, Any]] = None,
    *,
    filename_base: Optional[str] = None,
    db: Optional[Session] = None,
) -> Tuple[Optional[str], Optional[Dict[str, Any]], bool]:
    raw = str(media_url or "").strip()
    updated_metadata = dict(metadata) if isinstance(metadata, dict) else {}
    if not raw:
        return media_url, updated_metadata or metadata, False

    if raw.startswith("/"):
        return raw, updated_metadata, _oss_upload_succeeded_for_url(raw, updated_metadata, db)

    if not raw.lower().startswith(("http://", "https://")):
        return media_url, updated_metadata or metadata, False

    if oss_storage_service.is_active_managed_url(raw, db):
        updated_metadata = _attach_oss_metadata_from_managed_url(updated_metadata, raw)
        logger.info(
            "[VideoResultNormalize] skip remote localization for managed oss url | user_id=%s url=%s",
            getattr(current_user, "id", None),
            raw,
        )
        return raw, updated_metadata, True
    if _is_provider_direct_oss_url(raw, updated_metadata, db):
        updated_metadata["provider_direct_oss_url"] = True
        logger.info(
            "[VideoResultNormalize] skip localization for provider direct oss url | user_id=%s provider=%s url=%s",
            getattr(current_user, "id", None),
            str(updated_metadata.get("provider") or "").strip() or None,
            raw,
        )
        return raw, updated_metadata, True

    temp_filename = _extract_media_filename_from_url(raw)
    source_url = raw
    resolved_kie_download_url = _resolve_kie_downloadable_url(source_url)
    if resolved_kie_download_url and resolved_kie_download_url != raw:
        raw = resolved_kie_download_url
        if not temp_filename:
            temp_filename = _extract_media_filename_from_url(raw)

    user_id = int(getattr(current_user, "id", 0) or 0)
    max_attempts = max(1, int(os.getenv("REMOTE_VIDEO_LOCALIZE_MAX_ATTEMPTS", "3")))
    retry_backoff_seconds = max(0.5, float(os.getenv("REMOTE_VIDEO_LOCALIZE_RETRY_BACKOFF_SECONDS", "2")))
    persisted_url = ""
    last_exc: Optional[Exception] = None

    for attempt in range(1, max_attempts + 1):
        try:
            candidate_url = media_service._download_and_save(
                raw,
                filename_base=filename_base,
                user_id=user_id,
            )
            candidate_url = str(candidate_url or "").strip() or raw
            if candidate_url != source_url or _is_durable_persisted_media_url(candidate_url):
                persisted_url = candidate_url
                last_exc = None
                break
            persisted_url = candidate_url
            last_exc = ValueError("download_and_save returned original provider url")
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "[VideoResultNormalize] remote video download/save attempt failed | user_id=%s url=%s attempt=%s/%s err=%s",
                user_id,
                raw,
                attempt,
                max_attempts,
                exc,
            )
        if attempt < max_attempts:
            time.sleep(retry_backoff_seconds * attempt)

    if last_exc is not None and not persisted_url:
        updated_metadata["remote_localization_failed"] = True
        updated_metadata["remote_localization_error"] = str(last_exc)
        updated_metadata["remote_localization_source_url"] = raw
        updated_metadata["persist_attempts"] = max_attempts
        if temp_filename:
            updated_metadata["temporary_source_filename"] = temp_filename
        return media_url, updated_metadata, False

    persisted_url = str(persisted_url or "").strip() or raw
    oss_ok = _oss_upload_succeeded_for_url(persisted_url, updated_metadata, db)

    if persisted_url != source_url:
        updated_metadata["stored_from_remote_url"] = raw
        updated_metadata["remote_localization_failed"] = False
        updated_metadata.pop("remote_localization_error", None)
        if temp_filename:
            updated_metadata["temporary_source_filename"] = temp_filename
        if resolved_kie_download_url:
            updated_metadata["stored_from_remote_url_source"] = source_url
            updated_metadata["stored_from_remote_url_resolved_via"] = "kie_download_url"

    if oss_ok:
        updated_metadata = _attach_oss_metadata_from_managed_url(updated_metadata, persisted_url)
    elif persisted_url.startswith("/uploads/"):
        updated_metadata["stored_locally"] = True

    localized_success = _is_persisted_media_localization_success(
        persisted_url,
        source_url=source_url,
        metadata=updated_metadata,
        db=db,
        oss_uploaded=oss_ok,
    )
    if localized_success:
        updated_metadata = _clear_ephemeral_persist_flags(updated_metadata)
        updated_metadata["stored_from_remote_url"] = raw
        updated_metadata["remote_localization_failed"] = False
        updated_metadata.pop("remote_localization_error", None)
        if temp_filename:
            updated_metadata["temporary_source_filename"] = temp_filename
        if resolved_kie_download_url:
            updated_metadata["stored_from_remote_url_source"] = source_url
            updated_metadata["stored_from_remote_url_resolved_via"] = "kie_download_url"
        if oss_ok:
            updated_metadata["oss_uploaded_success"] = True
        logger.info(
            "[VideoResultNormalize] stored remote video | user_id=%s source_url=%s normalized_url=%s oss=%s",
            user_id,
            source_url,
            persisted_url,
            oss_ok,
        )
        return persisted_url, updated_metadata, oss_ok

    if not _is_durable_persisted_media_url(persisted_url, updated_metadata, db):
        updated_metadata["remote_localization_failed"] = True
        updated_metadata.setdefault(
            "remote_localization_error",
            "download_and_save returned original provider url",
        )
        updated_metadata["remote_localization_source_url"] = source_url
        updated_metadata["needs_persistence_retry"] = True
        logger.warning(
            "[VideoResultNormalize] remote video persisted without durable storage | user_id=%s url=%s",
            user_id,
            source_url,
        )
        return persisted_url, updated_metadata, False

    logger.info(
        "[VideoResultNormalize] stored remote video | user_id=%s source_url=%s normalized_url=%s oss=%s",
        user_id,
        source_url,
        persisted_url,
        oss_ok,
    )
    return persisted_url, updated_metadata, oss_ok


def _persist_remote_media_result(
    current_user: User,
    media_url: Optional[str],
    metadata: Optional[Dict[str, Any]] = None,
    *,
    filename_base: Optional[str] = None,
) -> Tuple[Optional[str], Optional[Dict[str, Any]], bool]:
    """Stream-download remote media and persist to OSS/local (video/audio/large files)."""
    return _persist_remote_video_result(
        current_user,
        media_url,
        metadata,
        filename_base=filename_base,
    )


def _resolve_media_bind_url(
    *,
    raw_url: str,
    normalized_url: Optional[str],
    normalized_meta: Dict[str, Any],
    oss_uploaded: bool = False,
    db: Optional[Session] = None,
) -> Tuple[Optional[str], bool, Dict[str, Any]]:
    return _resolve_video_bind_url(
        raw_url=raw_url,
        normalized_url=normalized_url,
        normalized_meta=normalized_meta,
        oss_uploaded=oss_uploaded,
        db=db,
    )


def _resolve_media_persistence_source_url(result: Dict[str, Any]) -> str:
    return _resolve_video_persistence_source_url(result)


def _media_result_needs_persistence_retry(result: Any) -> bool:
    return _video_result_needs_persistence_retry(result)


_EPHEMERAL_PROVIDER_MEDIA_HOST_PATTERNS = [
    re.compile(r"^file\d*\.aitohumanize\.com$", re.IGNORECASE),
    re.compile(r"(^|.+\.)aiquickdraw\.com$", re.IGNORECASE),
    re.compile(r"(^|.+\.)tempfile\.aiquickdraw\.com$", re.IGNORECASE),
    # Volcengine Ark / Seedance temporary TOS delivery URLs (must be localized to OSS).
    re.compile(r"(^|.+\.)volces\.com$", re.IGNORECASE),
]

_EPHEMERAL_PROVIDER_MEDIA_QUERY_MARKERS = (
    "x-tos-algorithm",
    "x-tos-signature",
    "x-tos-credential",
    "x-amz-algorithm",
    "x-amz-signature",
    "x-amz-credential",
)


def _is_ephemeral_provider_media_url(value: Any) -> bool:
    raw = str(value or "").strip()
    if not raw or raw.startswith("/") or raw.startswith("data:"):
        return False

    try:
        parsed = urllib.parse.urlparse(raw)
    except Exception:
        return False

    if str(parsed.scheme or "").lower() not in {"http", "https"}:
        return False

    hostname = str(parsed.hostname or "").strip().lower()
    if not hostname:
        return False

    for pattern in _EPHEMERAL_PROVIDER_MEDIA_HOST_PATTERNS:
        if pattern.match(hostname):
            return True

    query_lower = str(parsed.query or "").strip().lower()
    if query_lower and any(marker in query_lower for marker in _EPHEMERAL_PROVIDER_MEDIA_QUERY_MARKERS):
        return True
    return False


def _job_has_durable_result_url(job: Dict[str, Any]) -> bool:
    if not isinstance(job, dict):
        return False
    result = job.get("result")
    current_url = _extract_job_result_url(result)
    if not current_url:
        return False
    meta: Dict[str, Any] = {}
    if isinstance(result, dict) and isinstance(result.get("metadata"), dict):
        meta = dict(result.get("metadata") or {})
    return _is_durable_persisted_media_url(current_url, meta)


def _is_durable_persisted_media_url(
    value: Any,
    metadata: Optional[Dict[str, Any]] = None,
    db: Optional[Session] = None,
) -> bool:
    raw = str(value or "").strip()
    if not raw:
        return False
    if _is_ephemeral_provider_media_url(raw):
        return False

    oss_enabled = oss_storage_service.is_enabled(db)
    if raw.startswith("/uploads/") or (raw.startswith("/") and not raw.startswith("//")):
        if oss_enabled:
            return False
        return True

    if _url_matches_configured_oss(raw, metadata, db):
        return True
    if _is_provider_direct_oss_url(raw, metadata, db):
        return True
    return False


def _resolve_video_persistence_source_url(result: Dict[str, Any]) -> str:
    meta = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
    for key in ("remote_localization_source_url", "stored_from_remote_url", "pending_source_url"):
        candidate = str(meta.get(key) or "").strip()
        if candidate:
            return candidate
    direct = str(result.get("url") or "").strip()
    if direct:
        return direct
    return _extract_job_result_url(result)


def _video_result_needs_persistence_retry(result: Any, db: Optional[Session] = None) -> bool:
    if not isinstance(result, dict):
        return False
    meta = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
    current = str(result.get("url") or "").strip() or _extract_job_result_url(result)
    source = _resolve_video_persistence_source_url(result)
    if current and _is_persisted_media_localization_success(
        current,
        source_url=source,
        metadata=meta,
        db=db,
    ):
        return False
    if meta.get("persistence_gave_up") is True:
        return False
    if not source:
        return False
    if meta.get("remote_localization_failed") or meta.get("needs_persistence_retry") or meta.get("ephemeral_binding"):
        return True
    if _is_ephemeral_provider_media_url(current) or _is_ephemeral_provider_media_url(source):
        return True
    if current.lower().startswith(("http://", "https://")) and not _url_matches_configured_oss(current, meta, db):
        return True
    return False


def _clear_ephemeral_persist_flags(meta: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    cleaned = dict(meta or {})
    for key in (
        "ephemeral_binding",
        "needs_persistence_retry",
        "remote_localization_failed",
        "remote_localization_error",
        "pending_source_url",
        "persistence_retry_count",
        "persistence_retry_at",
    ):
        cleaned.pop(key, None)
    cleaned["remote_localization_failed"] = False
    return cleaned


def _ensure_media_bound_at(meta: Optional[Dict[str, Any]], *, refresh: bool = False) -> Dict[str, Any]:
    stamped = dict(meta or {})
    if refresh or not stamped.get("media_bound_at"):
        stamped["media_bound_at"] = now_bj_iso()
    return stamped


def _is_persisted_media_localization_success(
    url: Any,
    *,
    source_url: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    db: Optional[Session] = None,
    oss_uploaded: bool = False,
) -> bool:
    raw = str(url or "").strip()
    if not raw or _is_ephemeral_provider_media_url(raw):
        return False
    if oss_uploaded or _oss_upload_succeeded_for_url(raw, metadata, db):
        return True
    if _is_durable_persisted_media_url(raw, metadata, db):
        return True
    source = str(source_url or "").strip()
    if source and raw != source and raw.lower().startswith(("http://", "https://")):
        return True
    return False


def _resolve_video_bind_url(
    *,
    raw_url: str,
    normalized_url: Optional[str],
    normalized_meta: Dict[str, Any],
    oss_uploaded: bool = False,
    db: Optional[Session] = None,
) -> Tuple[Optional[str], bool, Dict[str, Any]]:
    meta = dict(normalized_meta or {})
    durable = str(normalized_url or "").strip()
    if durable and _is_persisted_media_localization_success(
        durable,
        source_url=raw_url,
        metadata=meta,
        db=db,
        oss_uploaded=oss_uploaded,
    ):
        meta = _clear_ephemeral_persist_flags(meta)
        if oss_uploaded:
            meta["oss_uploaded_success"] = True
        return durable, False, meta

    source = str(raw_url or "").strip()
    if not source:
        return None, False, meta

    if _is_provider_direct_oss_url(source, meta, db):
        # Provider-side direct OSS links are durable object keys, but often private.
        # Return a freshly signed URL so bind/proxy/clients can fetch immediately.
        meta["provider_direct_oss_url"] = True
        accessible = _ensure_accessible_media_result_url(source, meta)
        return accessible or source, False, meta

    if source.lower().startswith(("http://", "https://")) or _is_ephemeral_provider_media_url(source):
        meta["ephemeral_binding"] = True
        meta["needs_persistence_retry"] = True
        meta.setdefault("pending_source_url", source)
        return source, True, meta

    return None, False, meta


def _build_ephemeral_media_metadata(
    raw_url: str,
    base_meta: Optional[Dict[str, Any]] = None,
    *,
    temp_filename: Optional[str] = None,
) -> Dict[str, Any]:
    meta = dict(base_meta or {})
    meta["ephemeral_binding"] = True
    meta["needs_persistence_retry"] = True
    meta.setdefault("pending_source_url", raw_url)
    meta.setdefault("remote_localization_source_url", raw_url)
    meta["remote_localization_failed"] = True
    if temp_filename:
        meta.setdefault("temporary_source_filename", temp_filename)
    return _ensure_media_bound_at(meta, refresh=True)


def _build_generation_job_req_context(job: Dict[str, Any], db: Optional[Session] = None) -> Dict[str, Any]:
    req_context: Dict[str, Any] = {}
    for key in (
        "prompt", "negative_prompt", "provider", "model", "aspect_ratio",
        "duration", "project_id", "episode_id", "scene_id", "shot_id",
        "shot_number", "shot_name", "asset_type", "seed", "subject_id",
        "entity_id", "entity_name", "entity_type", "subject_name", "subject_type", "mode",
    ):
        value = job.get(key)
        if value is not None and value != "":
            req_context[key] = value

    if db is not None and not req_context.get("project_id") and req_context.get("shot_id"):
        try:
            shot_row = db.query(Shot).filter(Shot.id == int(req_context.get("shot_id"))).first()
            if shot_row:
                if getattr(shot_row, "project_id", None):
                    req_context["project_id"] = int(shot_row.project_id)
                if getattr(shot_row, "episode_id", None):
                    req_context["episode_id"] = int(shot_row.episode_id)
                if getattr(shot_row, "shot_id", None) and not req_context.get("shot_number"):
                    req_context["shot_number"] = shot_row.shot_id
                if getattr(shot_row, "shot_name", None) and not req_context.get("shot_name"):
                    req_context["shot_name"] = shot_row.shot_name
        except Exception:
            pass
    return req_context


def _enrich_media_metadata_from_generation_context(
    meta: Optional[Dict[str, Any]],
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Fill provider/model and generation params into media metadata without overwriting existing values."""
    enriched = dict(meta or {})
    ctx = context if isinstance(context, dict) else {}

    for key in (
        "provider",
        "model",
        "prompt",
        "negative_prompt",
        "aspect_ratio",
        "submit_aspect_ratio",
        "duration",
        "seed",
        "width",
        "height",
        "resolution",
        "image_size",
        "system_api_id",
        "shot_id",
        "project_id",
        "episode_id",
        "scene_id",
        "shot_number",
        "shot_name",
        "asset_type",
        "job_id",
        "idempotency_key",
    ):
        if enriched.get(key) not in (None, ""):
            continue
        value = ctx.get(key)
        if value not in (None, ""):
            enriched[key] = value

    smart_meta = enriched.get("smart_routing") if isinstance(enriched.get("smart_routing"), dict) else {}
    if not smart_meta and isinstance(ctx.get("smart_routing"), dict):
        smart_meta = ctx.get("smart_routing") or {}
    if not enriched.get("provider") and smart_meta.get("provider"):
        enriched["provider"] = smart_meta.get("provider")
    if not enriched.get("model") and smart_meta.get("model"):
        enriched["model"] = smart_meta.get("model")
    if enriched.get("system_api_id") is None and smart_meta.get("system_api_id") is not None:
        enriched["system_api_id"] = smart_meta.get("system_api_id")

    return enriched


def _hydrate_video_job_record(job_id: str, job: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    stable_job_id = str(job_id or (job or {}).get("job_id") or "").strip()
    merged = dict(job or {})
    if stable_job_id:
        merged["job_id"] = stable_job_id

    with VIDEO_JOB_LOCK:
        live = dict(VIDEO_JOB_STORE.get(stable_job_id) or {})
    if live:
        for key, value in live.items():
            if value in (None, ""):
                continue
            if merged.get(key) in (None, ""):
                merged[key] = value

    if stable_job_id:
        file_job = _read_video_job_file(stable_job_id)
        if isinstance(file_job, dict):
            for key, value in file_job.items():
                if value in (None, ""):
                    continue
                if merged.get(key) in (None, ""):
                    merged[key] = value

        try:
            from app.services.generation_task_queue import get_generation_task_status

            task_row = get_generation_task_status(stable_job_id) or {}
            task_user_id = task_row.get("user_id")
            if task_user_id not in (None, "") and merged.get("user_id") in (None, ""):
                merged["user_id"] = int(task_user_id)
            task_payload = _parse_generation_task_payload(task_row)
            recovered_fields: Dict[str, Any] = {}
            for key in (
                "shot_id", "project_id", "episode_id", "scene_id", "shot_number", "shot_name",
                "asset_type", "provider", "model", "prompt", "username",
                "reservation_tx_id", "billing_pending", "billing_settled", "billing_context",
            ):
                if task_payload.get(key) in (None, "", {}, []):
                    continue
                if merged.get(key) in (None, "", {}, []):
                    merged[key] = task_payload.get(key)
                    recovered_fields[key] = task_payload.get(key)
            if recovered_fields:
                logger.info(
                    "[VideoJob] hydrated missing fields from task payload | job_id=%s fields=%s",
                    stable_job_id,
                    sorted(list(recovered_fields.keys())),
                )
                _set_video_job(stable_job_id, **recovered_fields)
        except Exception:
            pass

    return merged


def _parse_generation_task_payload(task_row: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(task_row, dict):
        return {}
    payload = task_row.get("payload")
    if isinstance(payload, dict):
        return dict(payload)
    raw_json = task_row.get("payload_json")
    if isinstance(raw_json, dict):
        return dict(raw_json)
    if isinstance(raw_json, str) and raw_json.strip():
        try:
            parsed = json.loads(raw_json)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _resolve_job_owner_user(db: Session, job: Dict[str, Any]) -> Optional[Any]:
    from app.models.all_models import User

    try:
        user_id = int(job.get("user_id") or 0)
    except Exception:
        user_id = 0
    if user_id > 0:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            return user

    username = str(job.get("username") or "").strip()
    if username:
        user = db.query(User).filter(User.username == username).first()
        if user:
            return user

    shot_id = job.get("shot_id")
    if shot_id:
        try:
            shot = db.query(Shot).filter(Shot.id == int(shot_id)).first()
        except Exception:
            shot = None
        if shot:
            project_id = getattr(shot, "project_id", None)
            if not project_id and getattr(shot, "scene_id", None):
                scene = db.query(Scene).filter(Scene.id == int(shot.scene_id)).first()
                if scene and getattr(scene, "episode_id", None):
                    episode = db.query(Episode).filter(Episode.id == int(scene.episode_id)).first()
                    if episode:
                        project_id = getattr(episode, "project_id", None)
            if project_id:
                project = db.query(Project).filter(Project.id == int(project_id)).first()
                owner_id = int(getattr(project, "owner_id", 0) or 0) if project else 0
                if owner_id > 0:
                    user = db.query(User).filter(User.id == owner_id).first()
                    if user:
                        job.setdefault("user_id", owner_id)
                        job.setdefault("project_id", int(project_id))
                        return user
    return None


def _stage_ephemeral_media_job_result(
    job_id: str,
    job: Dict[str, Any],
    result: Dict[str, Any],
    *,
    media_kind: str = "video",
) -> Dict[str, Any]:
    """Save ephemeral provider URL to job metadata and bind shot/entity before OSS download."""
    if not isinstance(result, dict):
        return result

    raw_url = _extract_job_result_url(result)
    if not raw_url or not _is_ephemeral_provider_media_url(raw_url):
        return result

    existing_meta = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
    if _is_durable_persisted_media_url(raw_url, existing_meta):
        return result
    if existing_meta.get("ephemeral_binding") and existing_meta.get("needs_persistence_retry"):
        return result

    temp_filename = _extract_media_filename_from_url(raw_url)
    staged_meta = _build_ephemeral_media_metadata(
        raw_url,
        existing_meta,
        temp_filename=temp_filename or None,
    )
    staged_result = dict(result)
    staged_result["url"] = raw_url

    temp_label = f" temp_filename={temp_filename}" if temp_filename else ""
    log_prefix = "VideoJobPersist" if media_kind == "video" else "ImageJobPersist"

    if media_kind == "video":
        job = _hydrate_video_job_record(job_id, job)

    try:
        user_id = int(job.get("user_id") or 0)
    except Exception:
        user_id = 0

    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        current_user = _resolve_job_owner_user(db, job)
        req_context = _build_generation_job_req_context(job, db)
        staged_meta = _enrich_media_metadata_from_generation_context(staged_meta, job)
        staged_meta = _enrich_media_metadata_from_generation_context(staged_meta, req_context)
        staged_meta["job_id"] = job_id
        staged_result["metadata"] = staged_meta
        if media_kind == "video" and not str(req_context.get("asset_type") or "").strip():
            req_context["asset_type"] = "video"

        if not current_user:
            logger.warning(
                "[%s] staged ephemeral provider url without owner user | job_id=%s shot_id=%s user_id=%s%s url=%s",
                log_prefix,
                job_id,
                req_context.get("shot_id"),
                user_id or None,
                temp_label,
                raw_url,
            )
            return staged_result

        logger.warning(
            "[%s] staged ephemeral provider url | job_id=%s shot_id=%s user_id=%s%s url=%s",
            log_prefix,
            job_id,
            req_context.get("shot_id"),
            getattr(current_user, "id", None),
            temp_label,
            raw_url,
        )

        if req_context.get("shot_id"):
            _bind_generated_media_to_shot(
                db,
                current_user,
                req_context,
                raw_url,
                oss_uploaded_success=False,
                media_metadata=staged_meta,
            )
        elif media_kind == "video":
            logger.warning(
                "[VideoJobPersist] ephemeral url saved to job but shot_id missing | job_id=%s url=%s",
                job_id,
                raw_url,
            )

        request_mode = str(req_context.get("mode") or "").strip().lower()
        if media_kind == "image" and request_mode != "joint_diptych":
            _bind_generated_media_to_entity(
                db,
                current_user,
                req_context,
                raw_url,
                oss_uploaded_success=False,
            )
    except Exception as exc:
        logger.warning(
            "[EphemeralStage] bind failed | job_id=%s media_kind=%s error=%s",
            job_id,
            media_kind,
            exc,
        )
    finally:
        db.close()

    return staged_result


def _extract_media_filename_from_url(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = urllib.parse.urlparse(raw)
    except Exception:
        return ""

    pathname = str(parsed.path or "").strip()
    if not pathname:
        return ""

    try:
        return os.path.basename(pathname).strip()
    except Exception:
        return ""


def _assert_allowed_persisted_media_url(
    value: Any,
    *,
    field_label: str,
    metadata: Optional[Dict[str, Any]] = None,
    db: Optional[Session] = None,
    existing_value: Any = None,
) -> None:
    raw = str(value or "").strip()
    if not raw:
        return
    if _is_ephemeral_provider_media_url(raw):
        meta = metadata if isinstance(metadata, dict) else {}
        if meta.get("ephemeral_binding") or meta.get("needs_persistence_retry"):
            return
        if existing_value is not None and str(existing_value or "").strip() == raw:
            return
        raise HTTPException(
            status_code=400,
            detail=f"{field_label} cannot use a temporary provider URL; persist to OSS first",
        )
    if oss_storage_service.is_enabled(db) and not _is_durable_persisted_media_url(raw, metadata, db):
        raise HTTPException(
            status_code=400,
            detail=f"{field_label} must use configured OSS storage URL; run persist-media first",
        )


def _normalize_ephemeral_shot_media_update(
    update_data: Dict[str, Any],
    *,
    existing_shot: Optional[Shot] = None,
) -> Dict[str, Any]:
    patched = dict(update_data or {})

    def _ensure_ephemeral_notes(
        url_value: Any,
        *,
        meta_key: str,
        oss_flag_key: str,
    ) -> None:
        url = str(url_value or "").strip()
        if not url or not _is_ephemeral_provider_media_url(url):
            return

        raw_notes = patched.get("technical_notes")
        if raw_notes is None and existing_shot is not None:
            notes = _asset_meta_to_dict(getattr(existing_shot, "technical_notes", None))
        elif isinstance(raw_notes, dict):
            notes = dict(raw_notes)
        elif isinstance(raw_notes, str):
            notes = _asset_meta_to_dict(raw_notes)
        else:
            notes = {}

        slot_meta = dict(notes.get(meta_key) or {}) if isinstance(notes.get(meta_key), dict) else {}
        if slot_meta.get("ephemeral_binding") and slot_meta.get("needs_persistence_retry"):
            return

        notes[meta_key] = _build_ephemeral_media_metadata(url, slot_meta)
        notes[oss_flag_key] = False
        if isinstance(raw_notes, dict):
            patched["technical_notes"] = notes
        else:
            patched["technical_notes"] = json.dumps(notes, ensure_ascii=False)

    if "video_url" in patched:
        _ensure_ephemeral_notes(patched.get("video_url"), meta_key="video_metadata", oss_flag_key="video_oss_uploaded")
    if "image_url" in patched:
        _ensure_ephemeral_notes(patched.get("image_url"), meta_key="start_frame_metadata", oss_flag_key="start_frame_oss_uploaded")

    raw_notes = patched.get("technical_notes")
    notes_dict: Optional[Dict[str, Any]] = None
    if isinstance(raw_notes, dict):
        notes_dict = dict(raw_notes)
    elif isinstance(raw_notes, str):
        notes_dict = _asset_meta_to_dict(raw_notes)
    if isinstance(notes_dict, dict) and notes_dict.get("end_frame_url"):
        end_url = str(notes_dict.get("end_frame_url") or "").strip()
        if end_url and _is_ephemeral_provider_media_url(end_url):
            end_meta = dict(notes_dict.get("end_frame_metadata") or {}) if isinstance(notes_dict.get("end_frame_metadata"), dict) else {}
            if not (end_meta.get("ephemeral_binding") and end_meta.get("needs_persistence_retry")):
                notes_dict["end_frame_metadata"] = _build_ephemeral_media_metadata(end_url, end_meta)
                notes_dict["end_frame_oss_uploaded"] = False
                patched["technical_notes"] = notes_dict if isinstance(raw_notes, dict) else json.dumps(notes_dict, ensure_ascii=False)

    return patched


def _assert_allowed_shot_media_payload(
    update_data: Dict[str, Any],
    db: Optional[Session] = None,
    existing_shot: Optional[Shot] = None,
) -> None:
    if not isinstance(update_data, dict):
        return

    notes: Optional[Dict[str, Any]] = None
    raw_technical_notes = update_data.get("technical_notes")
    if isinstance(raw_technical_notes, dict):
        notes = raw_technical_notes
    elif isinstance(raw_technical_notes, str):
        try:
            parsed = json.loads(raw_technical_notes)
            notes = parsed if isinstance(parsed, dict) else None
        except Exception:
            notes = None

    start_meta = (
        dict(notes.get("start_frame_metadata") or {})
        if isinstance(notes, dict) and isinstance(notes.get("start_frame_metadata"), dict)
        else {}
    )
    video_meta = (
        dict(notes.get("video_metadata") or {})
        if isinstance(notes, dict) and isinstance(notes.get("video_metadata"), dict)
        else {}
    )
    end_meta = (
        dict(notes.get("end_frame_metadata") or {})
        if isinstance(notes, dict) and isinstance(notes.get("end_frame_metadata"), dict)
        else {}
    )

    _assert_allowed_persisted_media_url(
        update_data.get("image_url"),
        field_label="shot.image_url",
        metadata=start_meta,
        db=db,
        existing_value=getattr(existing_shot, "image_url", None) if existing_shot is not None else None,
    )
    _assert_allowed_persisted_media_url(
        update_data.get("video_url"),
        field_label="shot.video_url",
        metadata=video_meta,
        db=db,
        existing_value=getattr(existing_shot, "video_url", None) if existing_shot is not None else None,
    )

    if isinstance(notes, dict):
        existing_notes: Dict[str, Any] = {}
        if existing_shot is not None:
            existing_notes = _asset_meta_to_dict(getattr(existing_shot, "technical_notes", None))
        _assert_allowed_persisted_media_url(
            notes.get("end_frame_url"),
            field_label="shot.technical_notes.end_frame_url",
            metadata=end_meta,
            db=db,
            existing_value=existing_notes.get("end_frame_url") if isinstance(existing_notes, dict) else None,
        )


def _asset_meta_to_dict(raw_meta: Any) -> Dict[str, Any]:
    if isinstance(raw_meta, dict):
        return raw_meta
    if isinstance(raw_meta, str):
        try:
            parsed = json.loads(raw_meta)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _visible_asset_owner_ids_for_project(project: Optional[Project], current_user: User) -> List[int]:
    owner_ids = {int(current_user.id)}
    try:
        if project and getattr(project, "owner_id", None) is not None:
            owner_ids.add(int(project.owner_id))
    except Exception:
        pass
    return sorted(owner_ids)


def _resolve_precise_asset_library_url(
    db: Session,
    current_user: User,
    legacy_url: Any,
    *,
    project: Optional[Project],
    entity_id: Optional[int] = None,
    shot_id: Optional[int] = None,
    asset_type_aliases: Optional[set] = None,
    media_type: Optional[str] = None,
    limit: int = 256,
) -> Optional[str]:
    raw_legacy_url = str(legacy_url or "").strip()
    if not _is_ephemeral_provider_media_url(raw_legacy_url):
        return None

    project_id = getattr(project, "id", None)
    if not project_id:
        return None
    if entity_id is None and shot_id is None:
        return None

    owner_ids = _visible_asset_owner_ids_for_project(project, current_user)
    query = db.query(Asset).filter(Asset.user_id.in_(owner_ids))
    if media_type:
        query = query.filter(Asset.type == str(media_type).strip().lower())

    meta_text = cast(Asset.meta_info, String)
    query = query.filter(meta_text.contains(raw_legacy_url))
    query = query.filter(meta_text.contains(str(project_id)))
    if entity_id is not None:
        query = query.filter(meta_text.contains(str(entity_id)))
    if shot_id is not None:
        query = query.filter(meta_text.contains(str(shot_id)))
    if asset_type_aliases:
        alias_filters = [meta_text.contains(alias) for alias in sorted(asset_type_aliases) if str(alias or "").strip()]
        if alias_filters:
            query = query.filter(or_(*alias_filters))

    matched_urls: List[str] = []
    candidates = query.order_by(Asset.id.desc()).limit(max(int(limit or 0), 1)).all()
    for asset in candidates:
        meta = _asset_meta_to_dict(asset.meta_info)
        if str(meta.get("source_asset_url") or "").strip() != raw_legacy_url:
            continue
        if str(meta.get("project_id") or "").strip() != str(project_id):
            continue
        if entity_id is not None and str(meta.get("entity_id") or "").strip() != str(entity_id):
            continue
        if shot_id is not None and str(meta.get("shot_id") or "").strip() != str(shot_id):
            continue

        candidate_asset_type = str(meta.get("asset_type") or meta.get("frame_type") or "").strip().lower()
        if asset_type_aliases and candidate_asset_type not in asset_type_aliases:
            continue

        stable_url = str(asset.url or "").strip()
        if not stable_url or stable_url == raw_legacy_url or _is_ephemeral_provider_media_url(stable_url):
            continue

        matched_urls.append(stable_url)

    unique_urls = sorted(set(matched_urls))
    if len(unique_urls) != 1:
        return None
    return unique_urls[0]


def _repair_entity_image_url_from_assets(
    db: Session,
    current_user: User,
    project: Optional[Project],
    entity: Optional[Entity],
) -> bool:
    if not entity:
        return False

    legacy_url = str(getattr(entity, "image_url", None) or "").strip()
    if not _is_ephemeral_provider_media_url(legacy_url):
        return False

    resolved_url = _resolve_precise_asset_library_url(
        db,
        current_user,
        legacy_url,
        project=project,
        entity_id=getattr(entity, "id", None),
        asset_type_aliases={"subject", "character", "char"},
        media_type="image",
    )
    if not resolved_url:
        return False

    entity.image_url = resolved_url
    db.add(entity)
    logger.info(
        "[LegacyAssetRepair] entity_id=%s project_id=%s legacy_url=%s repaired_url=%s",
        getattr(entity, "id", None),
        getattr(entity, "project_id", None),
        legacy_url,
        resolved_url,
    )
    return True


def _repair_shot_media_urls_from_assets(
    db: Session,
    current_user: User,
    project: Optional[Project],
    shot: Optional[Shot],
) -> bool:
    if not shot:
        return False

    changed = False
    legacy_image_url = str(getattr(shot, "image_url", None) or "").strip()
    if _is_ephemeral_provider_media_url(legacy_image_url):
        resolved_image_url = _resolve_precise_asset_library_url(
            db,
            current_user,
            legacy_image_url,
            project=project,
            shot_id=getattr(shot, "id", None),
            asset_type_aliases={"start_frame", "start"},
            media_type="image",
        )
        if resolved_image_url:
            shot.image_url = resolved_image_url
            db.add(shot)
            changed = True
            logger.info(
                "[LegacyAssetRepair] shot_id=%s slot=start project_id=%s legacy_url=%s repaired_url=%s",
                getattr(shot, "id", None),
                getattr(shot, "project_id", None),
                legacy_image_url,
                resolved_image_url,
            )

    notes_changed = False
    notes = _asset_meta_to_dict(getattr(shot, "technical_notes", None))
    legacy_end_frame_url = str(notes.get("end_frame_url") or "").strip()
    if _is_ephemeral_provider_media_url(legacy_end_frame_url):
        resolved_end_frame_url = _resolve_precise_asset_library_url(
            db,
            current_user,
            legacy_end_frame_url,
            project=project,
            shot_id=getattr(shot, "id", None),
            asset_type_aliases={"end_frame", "end"},
            media_type="image",
        )
        if resolved_end_frame_url:
            notes["end_frame_url"] = resolved_end_frame_url
            notes_changed = True
            logger.info(
                "[LegacyAssetRepair] shot_id=%s slot=end project_id=%s legacy_url=%s repaired_url=%s",
                getattr(shot, "id", None),
                getattr(shot, "project_id", None),
                legacy_end_frame_url,
                resolved_end_frame_url,
            )

    legacy_video_url = str(getattr(shot, "video_url", None) or "").strip()
    if _is_ephemeral_provider_media_url(legacy_video_url):
        resolved_video_url = _resolve_precise_asset_library_url(
            db,
            current_user,
            legacy_video_url,
            project=project,
            shot_id=getattr(shot, "id", None),
            asset_type_aliases={"video"},
            media_type="video",
        )
        if resolved_video_url:
            shot.video_url = resolved_video_url
            video_meta = notes.get("video_metadata") if isinstance(notes.get("video_metadata"), dict) else {}
            video_meta = dict(video_meta or {})
            video_meta.pop("needs_persistence_retry", None)
            video_meta.pop("ephemeral_binding", None)
            video_meta["remote_localization_failed"] = False
            notes["video_metadata"] = video_meta
            notes["video_oss_uploaded"] = True
            notes_changed = True
            db.add(shot)
            changed = True
            logger.info(
                "[LegacyAssetRepair] shot_id=%s slot=video project_id=%s legacy_url=%s repaired_url=%s",
                getattr(shot, "id", None),
                getattr(shot, "project_id", None),
                legacy_video_url,
                resolved_video_url,
            )

    if notes_changed:
        shot.technical_notes = json.dumps(notes, ensure_ascii=False)
        db.add(shot)
        changed = True

    return changed


def _repair_entities_image_urls_from_assets(
    db: Session,
    current_user: User,
    project: Optional[Project],
    entities: List[Entity],
) -> List[Entity]:
    changed = False
    for entity in entities or []:
        if _repair_entity_image_url_from_assets(db, current_user, project, entity):
            changed = True
    if changed:
        db.commit()
    return entities


def _diagnose_entity_image_url(image_url: Any) -> Dict[str, Any]:
    raw = str(image_url or "").strip()
    info: Dict[str, Any] = {
        "raw": raw,
        "is_empty": not bool(raw),
        "is_relative_upload": False,
        "is_absolute_upload": False,
        "upload_suffix": "",
        "local_path": "",
        "local_exists": None,
    }
    if not raw:
        return info

    upload_suffix = ""
    if raw.startswith("/uploads/"):
        info["is_relative_upload"] = True
        upload_suffix = raw[len("/uploads/"):].lstrip("/")
    else:
        try:
            parsed = urllib.parse.urlparse(raw)
            if parsed.path.startswith("/uploads/"):
                info["is_absolute_upload"] = True
                upload_suffix = parsed.path[len("/uploads/"):].lstrip("/")
        except Exception:
            upload_suffix = ""

    info["upload_suffix"] = upload_suffix
    if upload_suffix:
        local_path = os.path.normpath(os.path.join(settings.UPLOAD_DIR, upload_suffix))
        info["local_path"] = local_path
        info["local_exists"] = bool(os.path.exists(local_path))
    return info


def _repair_shots_media_urls_from_assets(
    db: Session,
    current_user: User,
    project: Optional[Project],
    shots: List[Shot],
) -> List[Shot]:
    changed = False
    for shot in shots or []:
        if _repair_shot_media_urls_from_assets(db, current_user, project, shot):
            changed = True
    if changed:
        db.commit()
    return shots


def _refresh_managed_media_url(url: Any, db: Session) -> str:
    raw = str(url or "").strip()
    if not raw:
        return raw
    if not oss_storage_service.is_enabled(db):
        return raw
    try:
        return str(oss_storage_service.refresh_url(raw) or raw)
    except Exception:
        return raw


def _repair_stale_ephemeral_shot_media_notes(shot: Shot, db: Optional[Session] = None) -> bool:
    """Clear ephemeral persist flags when the stored URL is already on managed OSS."""
    if not shot:
        return False

    changed = False
    notes = _asset_meta_to_dict(getattr(shot, "technical_notes", None))
    if not isinstance(notes, dict):
        notes = {}

    def _repair_slot(
        media_url: str,
        meta_key: str,
        oss_flag_key: str,
    ) -> None:
        nonlocal changed
        url = str(media_url or "").strip()
        if not url:
            return
        slot_meta = dict(notes.get(meta_key) or {}) if isinstance(notes.get(meta_key), dict) else {}
        has_stale_flags = bool(
            slot_meta.get("ephemeral_binding")
            or slot_meta.get("needs_persistence_retry")
            or slot_meta.get("remote_localization_failed")
            or notes.get(oss_flag_key) is False
        )
        if not has_stale_flags:
            return
        if not (
            _is_persisted_media_localization_success(
                url,
                source_url=str(
                    slot_meta.get("remote_localization_source_url")
                    or slot_meta.get("pending_source_url")
                    or ""
                ).strip()
                or None,
                metadata=slot_meta,
                db=db,
            )
            or _is_durable_persisted_media_url(url, slot_meta, db)
        ):
            return
        notes[meta_key] = _clear_ephemeral_persist_flags(slot_meta)
        notes[oss_flag_key] = True
        changed = True

    _repair_slot(str(getattr(shot, "video_url", None) or "").strip(), "video_metadata", "video_oss_uploaded")
    _repair_slot(str(getattr(shot, "image_url", None) or "").strip(), "start_frame_metadata", "start_frame_oss_uploaded")
    _repair_slot(str(notes.get("end_frame_url") or "").strip(), "end_frame_metadata", "end_frame_oss_uploaded")

    if changed:
        if isinstance(getattr(shot, "technical_notes", None), dict):
            shot.technical_notes = notes
        else:
            shot.technical_notes = json.dumps(notes, ensure_ascii=False)
    return changed


def _refresh_shot_media_urls(shot: Shot, db: Session) -> Shot:
    if not shot:
        return shot

    shot.image_url = _refresh_managed_media_url(getattr(shot, "image_url", None), db)
    shot.video_url = _refresh_managed_media_url(getattr(shot, "video_url", None), db)

    notes = _asset_meta_to_dict(getattr(shot, "technical_notes", None))
    if notes:
        end_frame_url = str(notes.get("end_frame_url") or "").strip()
        refreshed_end = _refresh_managed_media_url(end_frame_url, db)
        if refreshed_end and refreshed_end != end_frame_url:
            notes["end_frame_url"] = refreshed_end
            if isinstance(shot.technical_notes, dict):
                shot.technical_notes = notes
            else:
                shot.technical_notes = json.dumps(notes, ensure_ascii=False)

    if _repair_stale_ephemeral_shot_media_notes(shot, db):
        try:
            db.add(shot)
            db.commit()
            db.refresh(shot)
        except Exception as exc:
            logger.warning(
                "[ShotMediaRepair] failed to persist stale ephemeral note cleanup | shot_id=%s err=%s",
                getattr(shot, "id", None),
                exc,
            )
            try:
                db.rollback()
            except Exception:
                pass
    return shot


def _resolve_local_upload_path_from_media_url(url: Any) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""

    upload_suffix = ""
    if raw.startswith("/uploads/"):
        upload_suffix = raw[len("/uploads/"):].lstrip("/")
    else:
        try:
            parsed = urllib.parse.urlparse(raw)
            if parsed.path.startswith("/uploads/"):
                upload_suffix = parsed.path[len("/uploads/"):].lstrip("/")
        except Exception:
            upload_suffix = ""

    if not upload_suffix:
        return ""

    upload_root = os.path.abspath(settings.UPLOAD_DIR)
    file_path = os.path.abspath(os.path.join(upload_root, upload_suffix))
    try:
        if os.path.commonpath([upload_root, file_path]) != upload_root:
            return ""
    except ValueError:
        return ""
    return file_path if os.path.exists(file_path) else ""


def _sanitize_zip_entry_token(value: Any, fallback: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z._-]+", "_", str(value or "").strip()).strip("._-")
    return normalized or fallback


def _build_shot_video_zip_entry_name(shot: Shot, index: int, video_url: str) -> str:
    scene_token = _sanitize_zip_entry_token(getattr(shot, "scene_code", None) or f"scene_{getattr(shot, 'scene_id', index) or index}", f"scene_{index}")
    shot_token = _sanitize_zip_entry_token(getattr(shot, "shot_id", None) or getattr(shot, "shot_name", None) or f"shot_{index}", f"shot_{index}")
    ext = ".mp4"
    try:
        parsed = urllib.parse.urlparse(str(video_url or "").strip())
        candidate = os.path.splitext(parsed.path or "")[1].strip().lower()
        if candidate and len(candidate) <= 8:
            ext = candidate
    except Exception:
        ext = ".mp4"
    return f"{index:03d}_{scene_token}_{shot_token}{ext}"


def _cleanup_temp_download_file(file_path: str) -> None:
    stable_path = str(file_path or "").strip()
    if not stable_path:
        return
    try:
        if os.path.exists(stable_path):
            os.remove(stable_path)
    except Exception as exc:
        logger.warning("Failed to cleanup temporary download file path=%s error=%s", stable_path, exc)


def _replace_legacy_temp_urls_in_shot_payload(
    db: Session,
    current_user: User,
    project: Optional[Project],
    shot: Shot,
    update_data: Dict[str, Any],
) -> Dict[str, Any]:
    patched = dict(update_data or {})

    image_url = patched.get("image_url")
    if _is_ephemeral_provider_media_url(image_url):
        resolved_image_url = _resolve_precise_asset_library_url(
            db,
            current_user,
            image_url,
            project=project,
            shot_id=getattr(shot, "id", None),
            asset_type_aliases={"start_frame", "start"},
            media_type="image",
        )
        if resolved_image_url:
            patched["image_url"] = resolved_image_url

    raw_technical_notes = patched.get("technical_notes")
    if raw_technical_notes is not None:
        notes = _asset_meta_to_dict(raw_technical_notes)
        end_frame_url = notes.get("end_frame_url")
        if _is_ephemeral_provider_media_url(end_frame_url):
            resolved_end_frame_url = _resolve_precise_asset_library_url(
                db,
                current_user,
                end_frame_url,
                project=project,
                shot_id=getattr(shot, "id", None),
                asset_type_aliases={"end_frame", "end"},
                media_type="image",
            )
            if resolved_end_frame_url:
                notes["end_frame_url"] = resolved_end_frame_url
                patched["technical_notes"] = notes if isinstance(raw_technical_notes, dict) else json.dumps(notes, ensure_ascii=False)

    video_url = patched.get("video_url")
    if _is_ephemeral_provider_media_url(video_url):
        resolved_video_url = _resolve_precise_asset_library_url(
            db,
            current_user,
            video_url,
            project=project,
            shot_id=getattr(shot, "id", None),
            asset_type_aliases={"video"},
            media_type="video",
        )
        if resolved_video_url:
            patched["video_url"] = resolved_video_url

    return patched


class ShotPersistMediaRequest(BaseModel):
    slot: str = "video"
    source_url: Optional[str] = None


class ShotVideoCleanupRequest(BaseModel):
    action: str  # remove_subtitle | remove_bgm | remove_subtitle_and_bgm
    source_url: Optional[str] = None


def _resolve_shot_media_slot_url(shot: Shot, slot: str) -> Tuple[str, str, Dict[str, Any], Dict[str, Any]]:
    normalized_slot = str(slot or "video").strip().lower()
    notes = _asset_meta_to_dict(getattr(shot, "technical_notes", None))

    if normalized_slot in {"start", "start_frame"}:
        return (
            str(getattr(shot, "image_url", None) or "").strip(),
            "start_frame",
            notes,
            dict(notes.get("start_frame_metadata") or {}) if isinstance(notes.get("start_frame_metadata"), dict) else {},
        )
    if normalized_slot in {"end", "end_frame"}:
        return (
            str(notes.get("end_frame_url") or "").strip(),
            "end_frame",
            notes,
            dict(notes.get("end_frame_metadata") or {}) if isinstance(notes.get("end_frame_metadata"), dict) else {},
        )
    if normalized_slot == "video":
        return (
            str(getattr(shot, "video_url", None) or "").strip(),
            "video",
            notes,
            dict(notes.get("video_metadata") or {}) if isinstance(notes.get("video_metadata"), dict) else {},
        )
    raise HTTPException(status_code=400, detail=f"Unsupported media slot: {slot}")


def _persist_shot_media_slot(
    db: Session,
    current_user: User,
    project: Project,
    shot: Shot,
    *,
    slot: str = "video",
    source_url_override: Optional[str] = None,
) -> Dict[str, Any]:
    source_url, asset_type, notes, slot_meta = _resolve_shot_media_slot_url(shot, slot)
    if source_url_override:
        source_url = str(source_url_override or "").strip()

    if not source_url:
        raise HTTPException(status_code=400, detail=f"Shot has no URL for slot={slot}")

    if _is_persisted_media_localization_success(
        source_url,
        source_url=source_url,
        metadata=slot_meta,
        db=db,
    ) or _is_durable_persisted_media_url(source_url, slot_meta, db):
        oss_ok = _oss_upload_succeeded_for_url(source_url, slot_meta, db) or _is_persisted_media_localization_success(
            source_url,
            source_url=source_url,
            metadata=slot_meta,
            db=db,
        )
        if oss_ok and asset_type == "video":
            clean_meta = _clear_ephemeral_persist_flags(dict(slot_meta or {}))
            clean_meta["oss_uploaded_success"] = True
            _bind_generated_media_to_shot(
                db,
                current_user,
                {
                    "shot_id": int(shot.id),
                    "project_id": int(getattr(shot, "project_id", None) or getattr(project, "id", None) or 0) or None,
                    "episode_id": getattr(shot, "episode_id", None),
                    "shot_number": getattr(shot, "shot_id", None),
                    "shot_name": getattr(shot, "shot_name", None),
                    "asset_type": asset_type,
                },
                source_url,
                True,
                clean_meta,
            )
            db.refresh(shot)
        return {
            "shot_id": int(shot.id),
            "slot": asset_type,
            "source_url": source_url,
            "persisted_url": source_url,
            "oss_uploaded": oss_ok,
            "already_persisted": True,
            "metadata": slot_meta or None,
        }

    req_context: Dict[str, Any] = {
        "shot_id": int(shot.id),
        "project_id": int(getattr(shot, "project_id", None) or getattr(project, "id", None) or 0) or None,
        "episode_id": getattr(shot, "episode_id", None),
        "shot_number": getattr(shot, "shot_id", None),
        "shot_name": getattr(shot, "shot_name", None),
        "asset_type": asset_type,
    }
    filename_base = _build_persist_filename_base_from_context(req_context, db)

    if asset_type == "video":
        normalized_url, normalized_meta, oss_uploaded = _persist_remote_video_result(
            current_user,
            source_url,
            slot_meta,
            filename_base=filename_base,
            db=db,
        )
    else:
        normalized_url, normalized_meta = _persist_remote_image_result(
            current_user,
            source_url,
            slot_meta,
            db=db,
        )
        normalized_meta = dict(normalized_meta or {})
        oss_uploaded = _oss_upload_succeeded_for_url(normalized_url, normalized_meta, db)

    normalized_url = str(normalized_url or "").strip() or source_url
    normalized_meta = dict(normalized_meta or {})

    bind_url, ephemeral_binding, normalized_meta = _resolve_video_bind_url(
        raw_url=source_url,
        normalized_url=normalized_url,
        normalized_meta=normalized_meta,
        oss_uploaded=oss_uploaded,
        db=db,
    )

    localization_ok = _is_persisted_media_localization_success(
        normalized_url,
        source_url=source_url,
        metadata=normalized_meta,
        db=db,
        oss_uploaded=oss_uploaded,
    )
    if localization_ok:
        final_url = normalized_url
        normalized_meta = _clear_ephemeral_persist_flags(normalized_meta)
        ephemeral_binding = False
    elif bind_url and _is_persisted_media_localization_success(
        bind_url,
        source_url=source_url,
        metadata=normalized_meta,
        db=db,
        oss_uploaded=oss_uploaded,
    ):
        final_url = bind_url
        ephemeral_binding = False
    elif bind_url:
        final_url = bind_url
    else:
        final_url = normalized_url or source_url

    if not _is_persisted_media_localization_success(
        final_url,
        source_url=source_url,
        metadata=normalized_meta,
        db=db,
        oss_uploaded=oss_uploaded,
    ):
        error_detail = str(
            normalized_meta.get("remote_localization_error")
            or "Failed to persist media to durable storage (OSS/local)"
        ).strip()
        raise HTTPException(
            status_code=502,
            detail=error_detail,
        )

    bind_oss_flag = bool(
        (oss_uploaded or _oss_upload_succeeded_for_url(final_url, normalized_meta, db))
        and not ephemeral_binding
        and not _is_ephemeral_provider_media_url(final_url)
    )
    if bind_oss_flag:
        normalized_meta = _clear_ephemeral_persist_flags(normalized_meta)
        normalized_meta["oss_uploaded_success"] = True

    try:
        _register_asset_helper(db, current_user.id, final_url, req_context, normalized_meta)
    except Exception as reg_exc:
        logger.warning("[ShotMediaPersist] register asset failed | shot_id=%s slot=%s err=%s", shot.id, asset_type, reg_exc)

    _bind_generated_media_to_shot(
        db,
        current_user,
        req_context,
        final_url,
        bind_oss_flag,
        normalized_meta,
    )

    db.refresh(shot)
    return {
        "shot_id": int(shot.id),
        "slot": asset_type,
        "source_url": source_url,
        "persisted_url": final_url,
        "oss_uploaded": bind_oss_flag,
        "already_persisted": False,
        "metadata": normalized_meta or None,
    }


class EntityPersistMediaRequest(BaseModel):
    source_url: Optional[str] = None


def _persist_entity_image(
    db: Session,
    current_user: User,
    project: Project,
    entity: Entity,
    *,
    source_url_override: Optional[str] = None,
) -> Dict[str, Any]:
    source_url = str(source_url_override or getattr(entity, "image_url", None) or "").strip()
    if not source_url:
        raise HTTPException(status_code=400, detail="Entity has no image URL")

    attrs = _asset_meta_to_dict(getattr(entity, "custom_attributes", None))
    slot_meta = dict(attrs or {})

    if _is_durable_persisted_media_url(source_url, slot_meta, db):
        return {
            "entity_id": int(entity.id),
            "source_url": source_url,
            "persisted_url": source_url,
            "oss_uploaded": _oss_upload_succeeded_for_url(source_url, slot_meta, db),
            "already_persisted": True,
            "metadata": slot_meta or None,
        }

    entity_type = str(getattr(entity, "type", None) or "subject").strip().lower()
    req_context: Dict[str, Any] = {
        "entity_id": int(entity.id),
        "project_id": int(getattr(project, "id", None) or getattr(entity, "project_id", None) or 0) or None,
        "entity_name": getattr(entity, "name", None),
        "subject_name": getattr(entity, "name", None),
        "entity_type": entity_type,
        "asset_type": "subject",
        "category": entity_type,
    }

    normalized_url, normalized_meta = _persist_remote_image_result(
        current_user,
        source_url,
        slot_meta,
        db=db,
    )
    normalized_meta = dict(normalized_meta or {})
    oss_uploaded = _oss_upload_succeeded_for_url(normalized_url, normalized_meta, db)

    bind_url, ephemeral_binding, normalized_meta = _resolve_video_bind_url(
        raw_url=source_url,
        normalized_url=str(normalized_url or "").strip() or None,
        normalized_meta=normalized_meta,
    )

    final_url = str(normalized_url or "").strip()
    if final_url and _is_durable_persisted_media_url(final_url, normalized_meta, db):
        bind_url = final_url
        ephemeral_binding = False
    elif bind_url and _is_durable_persisted_media_url(bind_url, normalized_meta, db):
        final_url = bind_url
        ephemeral_binding = False
    elif bind_url:
        final_url = bind_url
    else:
        final_url = normalized_url or source_url

    if not _is_durable_persisted_media_url(final_url, normalized_meta, db):
        error_detail = str(
            normalized_meta.get("remote_localization_error")
            or "Failed to persist entity image to durable storage (OSS/local)"
        ).strip()
        raise HTTPException(status_code=502, detail=error_detail)

    try:
        _register_asset_helper(db, current_user.id, final_url, req_context, normalized_meta)
    except Exception as reg_exc:
        logger.warning("[EntityMediaPersist] register asset failed | entity_id=%s err=%s", entity.id, reg_exc)

    _bind_generated_media_to_entity(
        db,
        current_user,
        req_context,
        final_url,
        bool(oss_uploaded and not ephemeral_binding),
    )

    db.refresh(entity)
    return {
        "entity_id": int(entity.id),
        "source_url": source_url,
        "persisted_url": final_url,
        "oss_uploaded": bool(oss_uploaded and not ephemeral_binding),
        "already_persisted": False,
        "metadata": normalized_meta or None,
    }


def _video_job_file_path(job_id: str) -> str:
    safe_job_id = re.sub(r"[^a-zA-Z0-9_-]", "", str(job_id or "").strip())
    return os.path.join(VIDEO_JOB_FILE_DIR, f"{safe_job_id}.json")


def _write_video_job_file(job_id: str, payload: Dict[str, Any]) -> None:
    try:
        from app.services.generation_task_queue import upsert_generation_job_state

        upsert_generation_job_state(kind="video", job_id=job_id, payload=payload)
    except Exception as e:
        logger.warning("failed to persist video job state in db job_id=%s err=%s", job_id, e)
    try:
        os.makedirs(VIDEO_JOB_FILE_DIR, exist_ok=True)
        path = _video_job_file_path(job_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
    except Exception as e:
        logger.warning("failed to persist video job file job_id=%s err=%s", job_id, e)


def _read_video_job_file(job_id: str) -> Optional[Dict[str, Any]]:
    try:
        from app.services.generation_task_queue import get_generation_job_state

        db_state = get_generation_job_state(kind="video", job_id=job_id)
        if isinstance(db_state, dict):
            db_state["job_id"] = db_state.get("job_id") or str(job_id)
            if "result" in db_state:
                db_state["result"] = _compact_job_result(db_state.get("result"))
            return db_state
    except Exception as e:
        logger.warning("failed to read video job state from db job_id=%s err=%s", job_id, e)
    try:
        path = _video_job_file_path(job_id)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data["job_id"] = data.get("job_id") or str(job_id)
            if "result" in data:
                data["result"] = _compact_job_result(data.get("result"))
            return data
    except Exception as e:
        logger.warning("failed to read video job file job_id=%s err=%s", job_id, e)
    return None


def _build_image_idempotency_store_key(user_id: int, idempotency_key: str) -> str:
    return f"{int(user_id)}::{idempotency_key.strip()}"


def _build_video_idempotency_store_key(user_id: int, idempotency_key: str) -> str:
    return f"{int(user_id)}::{idempotency_key.strip()}"


def _build_submit_idempotency_token(kind: str, user_id: int, payload: Dict[str, Any]) -> str:
    normalized_payload = dict(payload or {})
    normalized_payload.pop("callback_url", None)
    normalized_payload.pop("callbackUrl", None)
    normalized_payload.pop("callBackUrl", None)

    raw = json.dumps(normalized_payload, ensure_ascii=False, sort_keys=True, default=str)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"auto:{kind}:{int(user_id)}:{digest}"


def _build_generation_task_scope(kind: str, user_id: int, payload: Dict[str, Any]) -> str:
    stable_payload = dict(payload or {})
    scope_core = {
        "kind": str(kind or "").strip().lower(),
        "user_id": int(user_id),
        "project_id": stable_payload.get("project_id"),
        "episode_id": stable_payload.get("episode_id"),
        "scene_id": stable_payload.get("scene_id"),
        "shot_id": stable_payload.get("shot_id"),
        "asset_type": str(stable_payload.get("asset_type") or "").strip().lower(),
        "mode": str(stable_payload.get("mode") or "").strip().lower(),
        "entity_id": stable_payload.get("entity_id"),
        "subject_name": str(stable_payload.get("subject_name") or "").strip().lower(),
    }
    raw = json.dumps(scope_core, ensure_ascii=False, sort_keys=True, default=str)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"scope:{scope_core['kind']}:{scope_core['user_id']}:{digest}"


def _prune_image_submit_idempotency_locked(now: Optional[datetime] = None) -> None:
    now_dt = _coerce_naive_utc_datetime(now)
    expired_keys: List[str] = []

    for store_key, record in IMAGE_SUBMIT_IDEMPOTENCY_STORE.items():
        created_at = _parse_iso_datetime(record.get("created_at"))
        if not created_at:
            expired_keys.append(store_key)
            continue

        if (now_dt - created_at).total_seconds() > IMAGE_SUBMIT_IDEMPOTENCY_TTL_SECONDS:
            expired_keys.append(store_key)
            continue

        job_id = str(record.get("job_id") or "").strip()
        if not job_id or job_id not in IMAGE_JOB_STORE:
            expired_keys.append(store_key)

    for store_key in expired_keys:
        IMAGE_SUBMIT_IDEMPOTENCY_STORE.pop(store_key, None)


def _prune_video_submit_idempotency_locked(now: Optional[datetime] = None) -> None:
    now_dt = _coerce_naive_utc_datetime(now)
    expired_keys: List[str] = []

    for store_key, record in VIDEO_SUBMIT_IDEMPOTENCY_STORE.items():
        created_at = _parse_iso_datetime(record.get("created_at"))
        if not created_at:
            expired_keys.append(store_key)
            continue

        if (now_dt - created_at).total_seconds() > VIDEO_SUBMIT_IDEMPOTENCY_TTL_SECONDS:
            expired_keys.append(store_key)
            continue

        job_id = str(record.get("job_id") or "").strip()
        if not job_id or job_id not in VIDEO_JOB_STORE:
            expired_keys.append(store_key)

    for store_key in expired_keys:
        VIDEO_SUBMIT_IDEMPOTENCY_STORE.pop(store_key, None)


def _is_shot_submit_debug_enabled() -> bool:
    return str(os.getenv("SHOT_SUBMIT_DEBUG", "0")).strip().lower() in {"1", "true", "yes", "on"}


def _normalize_ref_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw = value.strip()
        return [raw] if raw else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item or "").strip()]
    return []


def _extract_ref_display_name(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = urllib.parse.urlparse(raw)
        path = urllib.parse.unquote(parsed.path or "")
        base_name = os.path.basename(path.rstrip("/"))
        if base_name:
            return base_name
        if parsed.netloc:
            return parsed.netloc
    except Exception:
        pass
    return raw


def _build_ref_display_names(value: Any, limit: int = 20) -> List[str]:
    refs = _normalize_ref_list(value)
    names: List[str] = []
    seen: set = set()
    for ref in refs:
        name = _extract_ref_display_name(ref)
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
        if len(names) >= limit:
            break
    return names


_PROMO_TYPE_HINTS = (
    "宣传",
    "推广",
    "营销",
    "品牌",
    "campaign",
    "promotion",
    "promotional",
    "advert",
    "advertising",
    "brand",
    "corporate",
    "product",
    "tourism",
    "cta",
    "conversion",
)


def _looks_like_promo_type(value: Any) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return False
    return any(token in text for token in _PROMO_TYPE_HINTS)


def _has_promo_generator_input(global_info: Any) -> bool:
    gi = dict(global_info or {})
    promo_input = gi.get("promo_generator_input")
    if not isinstance(promo_input, dict):
        return False

    for key in (
        "promo_type",
        "campaign_objective",
        "target_audience",
        "key_message",
        "core_highlights",
        "conversion_cta",
    ):
        if str(promo_input.get(key) or "").strip():
            return True
    return False


def _should_use_promo_prompts(global_info: Any, req_type: Any = None, req_extra_notes: Any = None) -> bool:
    gi = dict(global_info or {})

    if _looks_like_promo_type(req_type):
        return True

    if _looks_like_promo_type(req_extra_notes):
        return True

    if _has_promo_generator_input(gi):
        return True

    saved_story_input = gi.get("story_generator_global_input")
    if isinstance(saved_story_input, dict):
        if _looks_like_promo_type(saved_story_input.get("type")):
            return True
        if _looks_like_promo_type(saved_story_input.get("extra_notes")):
            return True

    if _looks_like_promo_type(gi.get("type")):
        return True

    return False


def _normalize_generator_kind(value: Any) -> Optional[str]:
    raw = str(value or "").strip().lower()
    if raw in {"promo", "promotion", "promotional"}:
        return "promo"
    if raw in {"story", "narrative", "film"}:
        return "story"
    return None


def _pick_first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _normalize_script_mode_key(script_mode: Any) -> str:
    raw = str(script_mode or "").strip().lower()
    if "short drama" in raw or "短剧" in raw:
        return "short_drama"
    if "feature film" in raw or "电影" in raw:
        return "feature_film"
    if "action feature" in raw or "动作片" in raw:
        return "action_feature"
    if "romance" in raw or "emotional" in raw or "爱情情感" in raw:
        return "romance_emotional"
    if "mystery" in raw or "thriller" in raw or "悬疑惊悚" in raw:
        return "mystery_thriller"
    if "comedy" in raw or "light" in raw or "喜剧轻快" in raw:
        return "comedy_light"
    if "xianxia" in raw or "fantasy" in raw or "仙侠奇幻" in raw:
        return "xianxia_fantasy"
    if "sci-fi" in raw or "sci fi" in raw or "科幻冒险" in raw:
        return "sci_fi_adventure"
    if "period" in raw or "wuxia" in raw or "古装武侠" in raw:
        return "period_wuxia"
    if "workplace" in raw or "现代职场" in raw:
        return "modern_workplace"
    if "horror" in raw or "恐怖" in raw:
        return "horror"
    if "cyberpunk" in raw or "赛博朋克" in raw:
        return "cyberpunk"
    if "realism" in raw or "现实主义" in raw:
        return "realism"
    if "youth" in raw or "coming-of-age" in raw or "青春成长" in raw:
        return "youth_coming_of_age"
    if "general series" in raw or "通用连续剧" in raw:
        return "general_series"
    return "general_series"


_MANDATORY_WRITING_LOGIC_BY_SCRIPT_MODE: Dict[str, str] = {
    "short_drama": (
        "- 首分钟强钩子；压缩说明；快反转；集末强悬念；短句对白。\n"
        "- 表演主轴=对白+微表情+微动作（每句台词配说话人/听者微表演，禁对白裸奔）。\n"
        "- 减环境与动作变化：1-2 场、同轴近景、少换锚点/少走位/少道具大交互/少环境奇观；反转靠台词与表情落点而非场面调度。\n"
        "- 优先用有趣、机锋、刻薄、挑衅等有记忆点的短句对白推进关键信息，避免大段旁白式说明。"
    ),
    "feature_film": (
        "- 按电影单集/单部节奏组织起承转合；允许更完整的空间建置与动作链，但仍须服务核心冲突。"
    ),
    "action_feature": (
        "- 目标驱动情节；地理清晰；战术逐步升级；动作后果可见。"
    ),
    "romance_emotional": (
        "- 关系张力优先；多利用停顿/潜台词/身体距离；对白承担关系升降与人物塑形。"
    ),
    "mystery_thriller": (
        "- 精确控制线索；转移怀疑对象；压力逐步升级；结局设揭秘或陷阱。"
    ),
    "comedy_light": (
        "- 节奏性反转；误会成组；喜剧因果清晰。"
    ),
    "xianxia_fantasy": (
        "- 命运秩序与阶层奇观；术法/武戏须写可读动作链与特效层级，禁止只写“打起来”。"
    ),
    "sci_fi_adventure": (
        "- 未知探索；科技具象；逻辑破解；设定自洽。"
    ),
    "period_wuxia": (
        "- 江湖规矩；身法兵器；环境破坏；近身/兵器对抗按起势/换招/受力反馈/结果落位拆写。"
    ),
    "modern_workplace": (
        "- 职级权力；信息差；资源争夺；受限公共空间视线拉扯。"
    ),
    "horror": (
        "- 视觉盲区；生理恐惧；铺垫后惊吓释放。"
    ),
    "cyberpunk": (
        "- 阶级反差；技术异化；入侵/追击时写技术后果可视化与实体动作反馈。"
    ),
    "realism": (
        "- 克制；生活细节；困境与解法扎根现实。"
    ),
    "youth_coming_of_age": (
        "- 自我认同；同辈后果；本集一步成长。"
    ),
    "general_series": (
        "- 铺垫、升级、反转、情感释放、后续价值之间保持平衡。"
    ),
}


def _build_mandatory_writing_logic(script_mode: Any) -> str:
    key = _normalize_script_mode_key(script_mode)
    return _MANDATORY_WRITING_LOGIC_BY_SCRIPT_MODE.get(key) or _MANDATORY_WRITING_LOGIC_BY_SCRIPT_MODE["general_series"]


def _resolve_episode_duration_minutes(value: Any, *, default: int = 1) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return n if n > 0 else default


def _build_episode_script_product_specs_block(
    *,
    episodes_count: Any,
    episode_duration_minutes: Any = 1,
    script_mode: str,
    target_audience: str,
) -> str:
    mode_label = script_mode or "（缺失：按项目全局框架与题材常识保守处理）"
    audience_label = target_audience or "（缺失：按项目全局框架与题材常识保守处理）"
    duration_minutes = _resolve_episode_duration_minutes(episode_duration_minutes)
    mandatory_logic = _build_mandatory_writing_logic(script_mode)
    return (
        "Project Product Specs (Hard Constraint):\n"
        f"- 载体规格 / Episodes Count: {episodes_count}\n"
        f"- 每集时长 / Episode Duration: {duration_minutes} minute(s)\n"
        f"- 产品规格与节奏 / Script Mode (Product Format): {mode_label}\n"
        f"- 受众定位 / Target Audience: {audience_label}\n"
        "\n"
        "Script Mode (Hard Constraint):\n"
        f"- {mode_label}\n"
        "\n"
        "Mandatory Writing Logic (强制写作逻辑, Hard Constraint):\n"
        f"{mandatory_logic}\n"
        "- Script Mode 与 Mandatory Writing Logic 为硬性写作逻辑；与通用默认冲突时，以本节为准。\n"
        "- 受众定位须极化核心看点与关系/情绪张力（男频/女频/全受众差异须体现在冲突选择与表达方式上）。\n"
        "\n"
    )


def _log_shot_submit_debug(kind: str, req: Any, refs: Any = None, extra: Optional[Dict[str, Any]] = None) -> None:
    if not _is_shot_submit_debug_enabled():
        return
    try:
        final_refs = _normalize_ref_list(refs if refs is not None else getattr(req, "ref_image_url", None))
        payload = {
            "kind": kind,
            "project_id": getattr(req, "project_id", None),
            "shot_id": getattr(req, "shot_id", None),
            "shot_number": getattr(req, "shot_number", None),
            "shot_name": getattr(req, "shot_name", None),
            "asset_type": getattr(req, "asset_type", None),
            "provider": getattr(req, "provider", None),
            "model": getattr(req, "model", None),
            "prompt": str(getattr(req, "prompt", "") or ""),
            "prompt_len": len(str(getattr(req, "prompt", "") or "")),
            "ref_count": len(final_refs),
            "refs": final_refs,
            "ref_names": _build_ref_display_names(final_refs),
        }
        if extra:
            payload.update(extra)
        llm_service.log_audit("SHOT_SUBMIT_DEBUG", payload)
    except Exception as exc:
        logger.warning("[ShotSubmitDebug] failed to log payload: %s", exc)


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
        dt = datetime.fromisoformat(normalized)
        # Job/idempotency stores mix now_bj_iso() (aware) with utcnow() (naive).
        # Normalize to naive UTC so age math never mixes aware/naive.
        if dt.tzinfo is not None:
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:
        return None


def _coerce_naive_utc_datetime(value: Optional[datetime] = None) -> datetime:
    dt = value or datetime.utcnow()
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _seconds_since_iso_timestamp(value: Any) -> Optional[float]:
    parsed = _parse_iso_datetime(value)
    if not parsed:
        return None
    try:
        return max(0.0, (_coerce_naive_utc_datetime() - parsed).total_seconds())
    except Exception:
        return None


def _job_sort_key(item: Dict[str, Any]) -> datetime:
    for field in ("created_at", "started_at", "finished_at"):
        parsed = _parse_iso_datetime(item.get(field))
        if parsed:
            return parsed
    return datetime.utcnow()


_JOB_RESULT_TOP_LEVEL_KEYS = ("url", "type", "provider", "model", "error")
_JOB_RESULT_METADATA_KEYS = (
    "provider",
    "model",
    "task_id",
    "job_id",
    "status",
    "persistence_retry_count",
    "persistence_retry_at",
    "needs_persistence_retry",
    "persistence_gave_up",
    "remote_localization_failed",
    "remote_localization_error",
    "remote_localization_source_url",
    "oss_uploaded_success",
    "stored_from_remote_url",
    "stored_from_remote_url_source",
    "stored_from_remote_url_resolved_via",
    "pending_source_url",
    "ephemeral_binding",
    "provider_direct_oss_url",
    "stored_locally",
    "temporary_source_filename",
    "persist_attempts",
    "idempotency_key",
)


def _compact_job_result(result: Any) -> Any:
    if not isinstance(result, dict):
        return result

    compact: Dict[str, Any] = {}
    for key in _JOB_RESULT_TOP_LEVEL_KEYS:
        if key in result:
            compact[key] = result.get(key)

    metadata = result.get("metadata")
    if isinstance(metadata, dict):
        compact_meta = {}
        for key in _JOB_RESULT_METADATA_KEYS:
            if key in metadata:
                compact_meta[key] = metadata.get(key)
        oss_meta = metadata.get("oss")
        if isinstance(oss_meta, dict) and oss_meta:
            compact_meta["oss"] = dict(oss_meta)
        if compact_meta:
            compact["metadata"] = compact_meta

    return compact or {"url": result.get("url")}


def _extract_job_result_url(result: Any) -> str:
    def _normalize_candidate_url(raw_value: Any) -> str:
        value = str(raw_value or "").strip()
        if not value:
            return ""
        if value.lower().startswith("data:"):
            return ""
        if len(value) > 4096:
            return ""
        if value.startswith("/uploads/"):
            return value
        try:
            parsed = urllib.parse.urlparse(value)
            if parsed.scheme.lower() not in {"http", "https", "oss", "s3", "cos"}:
                return ""
            if not parsed.netloc and parsed.scheme.lower() not in {"oss", "s3", "cos"}:
                return ""
        except Exception:
            return ""
        return value

    if isinstance(result, str):
        # Some providers embed result payload as JSON string (e.g. resultJson).
        text = str(result or "").strip()
        if not text:
            return ""
        value = _normalize_candidate_url(text)
        if value:
            return value
        if (text.startswith("{") and text.endswith("}")) or (text.startswith("[") and text.endswith("]")):
            try:
                parsed = json.loads(text)
            except Exception:
                parsed = None
            if isinstance(parsed, dict):
                return _extract_job_result_url(parsed)
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict):
                        nested_url = _extract_job_result_url(item)
                        if nested_url:
                            return nested_url
                    else:
                        parsed_value = _normalize_candidate_url(item)
                        if parsed_value:
                            return parsed_value
        return ""

    if not isinstance(result, dict):
        return ""

    direct_url_keys = (
        "url",
        "result_url",
        "resultUrl",
        "image_url",
        "imageUrl",
        "video_url",
        "videoUrl",
        "media_url",
        "mediaUrl",
        "generated_url",
        "generatedUrl",
        "output_url",
        "outputUrl",
        "file_url",
        "fileUrl",
        "download_url",
        "downloadUrl",
        "resource_url",
        "resourceUrl",
    )
    for key in direct_url_keys:
        value = _normalize_candidate_url(result.get(key))
        if value:
            return value

    direct_url_list_keys = (
        "urls",
        "result_urls",
        "resultUrls",
        "image_urls",
        "imageUrls",
        "video_urls",
        "videoUrls",
        "media_urls",
        "mediaUrls",
        "output_urls",
        "outputUrls",
        "resultUrlsList",
    )
    for key in direct_url_list_keys:
        items = result.get(key)
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    nested_url = _extract_job_result_url(item)
                    if nested_url:
                        return nested_url
                else:
                    value = _normalize_candidate_url(item)
                    if value:
                        return value

    results = result.get("results")
    if isinstance(results, list):
        for item in results:
            if isinstance(item, dict):
                nested_url = _extract_job_result_url(item)
                if nested_url:
                    return nested_url
            else:
                value = _normalize_candidate_url(item)
                if value:
                    return value

    nested_data = result.get("data")
    if isinstance(nested_data, dict):
        nested_url = _extract_job_result_url(nested_data)
        if nested_url:
            return nested_url

    nested_content = result.get("content")
    if isinstance(nested_content, dict):
        nested_url = _extract_job_result_url(nested_content)
        if nested_url:
            return nested_url

    nested_output = result.get("output")
    if isinstance(nested_output, dict):
        nested_url = _extract_job_result_url(nested_output)
        if nested_url:
            return nested_url

    nested_response = result.get("response")
    if isinstance(nested_response, dict):
        nested_url = _extract_job_result_url(nested_response)
        if nested_url:
            return nested_url

    for json_key in ("resultJson", "result_json", "responseJson", "response_json"):
        nested_json = result.get(json_key)
        nested_url = _extract_job_result_url(nested_json)
        if nested_url:
            return nested_url

    nested = result.get("result")
    if isinstance(nested, dict):
        return _extract_job_result_url(nested)
    if isinstance(nested, list):
        for item in nested:
            if isinstance(item, dict):
                nested_url = _extract_job_result_url(item)
                if nested_url:
                    return nested_url
            else:
                value = _normalize_candidate_url(item)
                if value:
                    return value

    return ""


def _merge_provider_task_ids_into_settle(settle_details: Dict[str, Any], *sources: Any) -> Dict[str, Any]:
    """Copy provider taskId / query_endpoint from result metadata into settle details."""
    payload = settle_details if isinstance(settle_details, dict) else {}
    merged = dict(payload)
    for src in sources:
        if not isinstance(src, dict):
            continue
        for key in ("provider_task_id", "task_id", "taskId", "query_endpoint", "queryEndpoint"):
            val = src.get(key)
            if val not in (None, "") and merged.get(key) in (None, ""):
                merged[key] = val
        nested = src.get("provider_usage") if isinstance(src.get("provider_usage"), dict) else None
        if nested:
            for key in ("provider_task_id", "task_id", "taskId", "query_endpoint", "queryEndpoint"):
                val = nested.get(key)
                if val not in (None, "") and merged.get(key) in (None, ""):
                    merged[key] = val
        for nest_key in ("raw", "submit_raw", "metadata", "data", "output"):
            nested2 = src.get(nest_key)
            if isinstance(nested2, dict):
                for key in ("provider_task_id", "task_id", "taskId", "query_endpoint", "queryEndpoint"):
                    val = nested2.get(key)
                    if val not in (None, "") and merged.get(key) in (None, ""):
                        merged[key] = val
    try:
        from app.services.billing_service import BillingService
        return BillingService.ensure_provider_task_ids(merged)
    except Exception:
        return merged


def _extract_job_provider_task_id(job: Dict[str, Any]) -> str:
    if not isinstance(job, dict):
        return ""

    for value in (job.get("provider_task_id"), job.get("task_id"), job.get("taskId")):
        normalized = str(value or "").strip()
        if normalized:
            return normalized

    result = job.get("result")
    if isinstance(result, dict):
        metadata = result.get("metadata")
        if isinstance(metadata, dict):
            for key in ("task_id", "taskId", "job_id", "jobId"):
                normalized = str(metadata.get(key) or "").strip()
                if normalized:
                    return normalized

    return ""


def _extract_job_provider_callback_ticket(job: Dict[str, Any]) -> str:
    if not isinstance(job, dict):
        return ""

    for value in (job.get("provider_callback_ticket"), job.get("callback_ticket")):
        normalized = str(value or "").strip()
        if normalized:
            return normalized

    return ""


def _is_ambiguous_image_submit_detail(detail: Any) -> bool:
    text = str(detail or "").strip().lower()
    if not text:
        return False
    return "ambiguous_submit_transport" in text or "provider may have accepted the request" in text


def _normalize_generation_status(value: Any) -> str:
    status = str(value or "").strip().lower()
    if status in {"success", "succeeded", "completed", "done"}:
        return "succeeded"
    if status in {"failed", "error"}:
        return "failed"
    if status in {"canceled", "cancelled"}:
        return "canceled"
    if status in {"queued", "pending", "running", "processing", "in_progress", "in-progress"}:
        return "running"
    return status


def _ensure_accessible_media_result_url(url: Any, metadata: Optional[Dict[str, Any]] = None) -> str:
    """Sign managed / provider-direct private OSS URLs so clients and /assets/proxy can fetch them."""
    raw = str(url or "").strip()
    if not raw.lower().startswith(("http://", "https://")):
        return raw
    try:
        if oss_storage_service.is_managed_url(raw) or _is_provider_direct_oss_url(raw, metadata):
            refreshed = str(oss_storage_service.refresh_url(raw) or "").strip()
            if refreshed:
                return refreshed
    except Exception as exc:
        logger.warning(
            "[MediaUrlAccess] refresh failed | url=%s err=%s",
            raw.split("?", 1)[0],
            exc,
        )
    return raw


def _build_result_from_provider_callback(
    payload: Dict[str, Any],
    *,
    fallback_provider: Optional[str] = None,
    fallback_model: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    if not isinstance(payload, dict):
        return None

    result_url = _extract_job_result_url(payload)
    if not result_url:
        return None

    # Grsai writes directly to private Qiniu; callback URLs are often unsigned (401 without token).
    result_url = _ensure_accessible_media_result_url(
        result_url,
        {"provider": str(payload.get("provider") or fallback_provider or "").strip() or None},
    )
    result: Dict[str, Any] = {"url": result_url}
    results = payload.get("results")
    first_result = results[0] if isinstance(results, list) and results else None
    if isinstance(first_result, dict):
        for key in ("width", "height", "content"):
            if first_result.get(key) not in (None, ""):
                result[key] = first_result.get(key)

    for key in ("width", "height", "content"):
        if key not in result and payload.get(key) not in (None, ""):
            result[key] = payload.get(key)

    callback_task_id = _extract_callback_task_id(payload)
    callback_payload_size = 0
    try:
        callback_payload_size = len(json.dumps(payload, ensure_ascii=False, default=str, separators=(",", ":")).encode("utf-8", errors="ignore"))
    except Exception:
        callback_payload_size = 0
    provider_candidates: List[str] = []
    for candidate in (
        payload.get("provider"),
        payload.get("provider_name"),
        payload.get("providerName"),
        payload.get("vendor"),
        payload.get("source"),
        fallback_provider,
    ):
        text = str(candidate or "").strip()
        if text:
            provider_candidates.append(text)
    resolved_provider = provider_candidates[0] if provider_candidates else ""

    model_candidates: List[str] = []
    for candidate in (
        payload.get("model"),
        payload.get("model_name"),
        payload.get("modelName"),
        fallback_model,
    ):
        text = str(candidate or "").strip()
        if text:
            model_candidates.append(text)
    resolved_model = model_candidates[0] if model_candidates else ""

    metadata: Dict[str, Any] = {
        "provider": resolved_provider,
        "status": _normalize_generation_status(payload.get("status")),
        "payload_truncated": bool(payload.get("payload_truncated")),
    }
    if resolved_model:
        metadata["model"] = resolved_model
    if callback_payload_size > 0:
        metadata["callback_payload_size_bytes"] = callback_payload_size
    callback_result_url = _extract_job_result_url(payload)
    if callback_result_url:
        metadata["callback_result_url"] = callback_result_url
    if callback_task_id:
        metadata["task_id"] = callback_task_id
        metadata["taskId"] = callback_task_id
    if payload.get("failure_reason") not in (None, ""):
        metadata["failure_reason"] = payload.get("failure_reason")
    if payload.get("error") not in (None, ""):
        metadata["error"] = payload.get("error")
    if isinstance(payload.get("metadata"), dict):
        payload_meta = payload.get("metadata") or {}
        for key in (
            "provider",
            "model",
            "provider_direct_oss_url",
            "system_api_id",
        ):
            if payload_meta.get(key) not in (None, ""):
                metadata[key] = payload_meta.get(key)
    try:
        from app.services.media_service import (
            _attach_provider_usage_metadata,
            _extract_provider_task_usage,
            _normalize_provider_task_usage,
        )

        callback_usage = _normalize_provider_task_usage(_extract_provider_task_usage(payload))
        if callback_usage:
            metadata = _attach_provider_usage_metadata(
                metadata,
                usage=callback_usage,
                source=str(resolved_provider or "callback").strip() or "callback",
                task_payload=payload,
            )
            kie_credits = callback_usage.get("kie_credits_consumed") or callback_usage.get("creditsConsumed")
            if kie_credits not in (None, ""):
                metadata["creditsConsumed"] = kie_credits
                metadata["credits_consumed"] = kie_credits
                metadata["kie_credits_consumed"] = kie_credits
            for rh_key in ("consumeCoins", "consumeMoney", "thirdPartyConsumeMoney"):
                if callback_usage.get(rh_key) not in (None, ""):
                    metadata[rh_key] = callback_usage.get(rh_key)
            data_obj = payload.get("data") if isinstance(payload.get("data"), dict) else {}
            event_obj = payload.get("eventData") if isinstance(payload.get("eventData"), dict) else {}
            event_usage = event_obj.get("usage") if isinstance(event_obj.get("usage"), dict) else {}
            for cost_key in ("costTime", "cost_time", "taskCostTime"):
                cost_val = callback_usage.get(cost_key)
                if cost_val in (None, ""):
                    cost_val = event_usage.get(cost_key)
                if cost_val in (None, ""):
                    cost_val = data_obj.get(cost_key) if data_obj.get(cost_key) not in (None, "") else payload.get(cost_key)
                if cost_val in (None, ""):
                    continue
                try:
                    metadata["taskCostTime"] = float(cost_val)
                    metadata["provider_cost_time_seconds"] = float(cost_val)
                    metadata["cost_time"] = float(cost_val)
                except Exception:
                    pass
                break
            # Ark Seedance callback fields on webhook root.
            if payload.get("duration") not in (None, ""):
                metadata["duration"] = payload.get("duration")
            if payload.get("ratio") not in (None, ""):
                metadata["aspect_ratio"] = payload.get("ratio")
            if payload.get("resolution") not in (None, ""):
                metadata["resolution"] = payload.get("resolution")
            if payload.get("framespersecond") not in (None, ""):
                metadata["fps"] = payload.get("framespersecond")
            if metadata.get("taskCostTime") is None:
                try:
                    created_at = float(payload.get("created_at") or 0)
                    updated_at = float(payload.get("updated_at") or 0)
                    if created_at > 0 and updated_at >= created_at:
                        metadata["taskCostTime"] = updated_at - created_at
                        metadata["provider_cost_time_seconds"] = updated_at - created_at
                        metadata["cost_time"] = updated_at - created_at
                except Exception:
                    pass
            metadata["raw"] = {
                "id": callback_task_id,
                "status": metadata.get("status"),
                "usage": callback_usage,
                "model": resolved_model or None,
                "creditsConsumed": kie_credits,
                "costTime": metadata.get("taskCostTime"),
                "duration": payload.get("duration"),
                "ratio": payload.get("ratio"),
                "resolution": payload.get("resolution"),
            }
    except Exception:
        pass
    result["metadata"] = metadata
    return result


def _get_generation_callback_payload(ticket: str) -> Dict[str, Any]:
    stable_ticket = str(ticket or "").strip()
    if not stable_ticket:
        return {}

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

    raw_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else {}
    normalized = dict(raw_payload or {})
    
    event_data = normalized.get("eventData")
    if isinstance(event_data, dict):
        if "status" not in normalized and "status" in event_data:
            normalized["status"] = event_data["status"]
        if "error" not in normalized:
            error_val = event_data.get("errorMessage") or event_data.get("failedReason") or event_data.get("errorCode")
            if error_val:
                normalized["error"] = str(error_val)

    callback_status_raw = _extract_callback_status(normalized)
    callback_status = _normalize_generation_status(callback_status_raw)
    if callback_status:
        normalized["status"] = callback_status
    elif callback_status_raw and "status" not in normalized:
        normalized["status"] = callback_status_raw

    callback_task_id = _extract_callback_task_id(normalized)
    if callback_task_id:
        normalized.setdefault("task_id", callback_task_id)
        normalized.setdefault("taskId", callback_task_id)

    callback_result_url = _extract_job_result_url(normalized)
    if callback_result_url:
        normalized.setdefault("result_url", callback_result_url)
        if not str(normalized.get("status") or "").strip():
            normalized["status"] = "succeeded"
                
    return normalized


def _finalize_image_job_result_persistence(job_id: str, job: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(result, dict):
        return result

    result = _stage_ephemeral_media_job_result(job_id, job, result, media_kind="image")
    raw_url = _extract_job_result_url(result)
    if not raw_url:
        return result
    raw_temp_filename = _extract_media_filename_from_url(raw_url)

    try:
        user_id = int(job.get("user_id") or 0)
    except Exception:
        user_id = 0
    if user_id <= 0:
        return result

    db = SessionLocal()
    try:
        current_user = db.query(User).filter(User.id == user_id).first()
        if not current_user:
            return result

        req_context: Dict[str, Any] = {}
        for key in (
            "prompt",
            "negative_prompt",
            "provider",
            "model",
            "aspect_ratio",
            "image_size",
            "width",
            "height",
            "quality",
            "output_format",
            "background",
            "project_id",
            "episode_id",
            "scene_id",
            "shot_id",
            "shot_number",
            "shot_name",
            "entity_id",
            "entity_name",
            "subject_name",
            "subject_type",
            "entity_type",
            "asset_type",
            "seed",
            "mode",
        ):
            value = job.get(key)
            if value not in (None, ""):
                req_context[key] = value

        metadata = result.get("metadata") if isinstance(result.get("metadata"), dict) else None
        logger.info(
            "[ImageJobPersist] start | job_id=%s user_id=%s entity_id=%s entity_name=%s shot_id=%s raw_url=%s temp_filename=%s metadata_keys=%s",
            job_id,
            getattr(current_user, "id", None),
            req_context.get("entity_id"),
            req_context.get("entity_name") or req_context.get("subject_name"),
            req_context.get("shot_id"),
            raw_url,
            raw_temp_filename,
            sorted(list(metadata.keys())) if isinstance(metadata, dict) else [],
        )
        normalized_url, normalized_meta = _persist_data_uri_image_result(current_user, raw_url, metadata)
        if str(normalized_url or "").strip().lower().startswith(("http://", "https://")):
            filename_base = _build_persist_filename_base_from_context(req_context, db)
            normalized_url, normalized_meta, oss_uploaded = _persist_remote_media_result(
                current_user,
                normalized_url,
                normalized_meta,
                filename_base=filename_base,
            )
        else:
            oss_uploaded = _oss_upload_succeeded_for_url(normalized_url, normalized_meta)
        logger.info(
            "[ImageJobPersist] normalized | job_id=%s user_id=%s entity_id=%s shot_id=%s normalized_url=%s oss=%s",
            job_id,
            getattr(current_user, "id", None),
            req_context.get("entity_id"),
            req_context.get("shot_id"),
            normalized_url,
            oss_uploaded,
        )
        if normalized_meta is None:
            normalized_meta = {}
        normalized_meta["idempotency_key"] = job_id

        bind_url, ephemeral_binding, normalized_meta = _resolve_media_bind_url(
            raw_url=raw_url,
            normalized_url=str(normalized_url or "").strip() or None,
            normalized_meta=normalized_meta,
        )

        finalized_result = dict(result)
        display_url = str(normalized_url or "").strip()
        if display_url and _is_durable_persisted_media_url(display_url):
            finalized_result["url"] = display_url
        elif bind_url:
            finalized_result["url"] = bind_url
        elif display_url:
            finalized_result["url"] = display_url
        if normalized_meta is not None:
            finalized_result["metadata"] = normalized_meta

        request_mode = str(req_context.get("mode") or "").strip().lower()
        if bind_url:
            bind_oss_flag = bool(oss_uploaded and not ephemeral_binding)
            _register_asset_helper(db, current_user.id, bind_url, req_context, normalized_meta)
            if request_mode != "joint_diptych":
                _bind_generated_media_to_shot(
                    db,
                    current_user,
                    req_context,
                    bind_url,
                    oss_uploaded_success=bind_oss_flag,
                    media_metadata=normalized_meta,
                )
                _bind_generated_media_to_entity(
                    db,
                    current_user,
                    req_context,
                    bind_url,
                    oss_uploaded_success=bind_oss_flag,
                )
        elif normalized_url:
            if request_mode != "joint_diptych":
                logger.warning(
                    "[ImageJob] skipped asset registration/bind because no durable or fallback url | job_id=%s user_id=%s url=%s temp_filename=%s entity_id=%s shot_id=%s",
                    job_id,
                    getattr(current_user, "id", None),
                    normalized_url,
                    _extract_media_filename_from_url(normalized_url),
                    req_context.get("entity_id"),
                    req_context.get("shot_id"),
                )

        return finalized_result
    except Exception as exc:
        logger.warning("[ImageJob] callback persistence finalize failed | job_id=%s error=%s", job_id, exc)
        return result
    finally:
        db.close()


def _maybe_finalize_image_job_from_grsai_callback(job_id: str, job: Dict[str, Any]) -> Dict[str, Any]:
    provider_task_id = _extract_job_provider_task_id(job)
    callback_ticket = _extract_job_provider_callback_ticket(job)
    if not callback_ticket:
        return job
    callback_payload = _get_generation_callback_payload(callback_ticket)
    if not callback_payload:
        return job

    callback_task_id = _extract_callback_task_id(callback_payload)
    if provider_task_id and callback_task_id and callback_task_id != provider_task_id:
        return job

    normalized_status = _normalize_generation_status(callback_payload.get("status"))
    current_status = _normalize_generation_status(job.get("status"))
    result = _build_result_from_provider_callback(
        callback_payload,
        fallback_provider=str(job.get("provider") or "").strip() or None,
        fallback_model=str(job.get("model") or "").strip() or None,
    )
    current_result_url = _extract_job_result_url(job.get("result"))
    callback_result_url = _extract_job_result_url(result or {})
    current_error = str(job.get("error") or "").strip()
    current_has_stable_result = _job_has_durable_result_url(job)
    callback_has_ephemeral_result = bool(callback_result_url) and _is_ephemeral_provider_media_url(callback_result_url)

    updates: Dict[str, Any] = {}
    first_success_finalize = current_status not in {"succeeded", "completed", "done"}
    if callback_result_url and callback_result_url != current_result_url and not current_has_stable_result:
        if _is_ephemeral_provider_media_url(callback_result_url) and isinstance(result, dict):
            effective_job = dict(job)
            effective_job.update(updates)
            updates["result"] = _stage_ephemeral_media_job_result(
                job_id,
                effective_job,
                dict(result),
                media_kind="image",
            )
        else:
            updates["result"] = result
    elif callback_result_url and current_has_stable_result:
        logger.info(
            "[ImageJob] ignored callback result url because stable result already exists | job_id=%s callback_ticket=%s current_result_url=%s callback_result_url=%s",
            job_id,
            callback_ticket,
            current_result_url,
            callback_result_url,
        )

    if normalized_status in {"succeeded", "failed", "canceled"} and normalized_status != current_status:
        updates["status"] = normalized_status
        if not job.get("finished_at"):
            updates["finished_at"] = now_bj_iso()

    if (
        normalized_status == "succeeded"
        and isinstance(updates.get("result"), dict)
        and _extract_job_result_url(updates.get("result"))
        and first_success_finalize
    ):
        early_save: Dict[str, Any] = {
            "status": updates.get("status") or normalized_status,
            "result": updates["result"],
        }
        if updates.get("finished_at"):
            early_save["finished_at"] = updates["finished_at"]
        if provider_task_id:
            early_save["provider_task_id"] = provider_task_id
        _set_image_job(job_id, **early_save)
        with IMAGE_JOB_LOCK:
            job = dict(IMAGE_JOB_STORE.get(job_id) or job)

    if normalized_status == "succeeded" and (not current_has_stable_result or "result" in updates):
        candidate_result = updates.get("result") if isinstance(updates.get("result"), dict) else (
            result if isinstance(result, dict) else (job.get("result") if isinstance(job.get("result"), dict) else None)
        )
        if candidate_result:
            if _mark_image_callback_persist_inflight(job_id):
                try:
                    effective_job = dict(job)
                    effective_job.update(updates)
                    persisted_result = _finalize_image_job_result_persistence(job_id, effective_job, dict(candidate_result))
                    persisted_result_url = _extract_job_result_url(persisted_result)
                    if not persisted_result_url and isinstance(persisted_result, dict):
                        persisted_result_url = str(persisted_result.get("url") or "").strip()
                    effective_current_result = updates.get("result") if "result" in updates else job.get("result")
                    effective_current_result_url = _extract_job_result_url(effective_current_result)
                    if persisted_result_url and (
                        persisted_result_url != effective_current_result_url or persisted_result != effective_current_result
                    ):
                        updates["result"] = persisted_result
                        callback_result_url = persisted_result_url
                finally:
                    _clear_image_callback_persist_inflight(job_id)
            else:
                logger.info(
                    "[ImageJob] skip duplicate callback persistence while in-flight | job_id=%s callback_ticket=%s",
                    job_id,
                    callback_ticket,
                )
                return job
        if current_error:
            updates["error"] = None
    elif normalized_status in {"failed", "canceled"}:
        failure_parts = [str(callback_payload.get("failure_reason") or "").strip(), str(callback_payload.get("error") or "").strip()]
        failure_text = " | ".join([part for part in failure_parts if part])
        if failure_text and failure_text != current_error:
            updates["error"] = failure_text

    if not updates:
        return _maybe_retry_image_job_result_persistence(job_id, job)

    if provider_task_id:
        updates.setdefault("provider_task_id", provider_task_id)
    _set_image_job(job_id, **updates)
    with IMAGE_JOB_LOCK:
        updated = dict(IMAGE_JOB_STORE.get(job_id) or {})
    logger.info(
        "[ImageJob] finalized from grsai callback | job_id=%s callback_ticket=%s provider_task_id=%s status=%s has_result_url=%s result_url=%s",
        job_id,
        callback_ticket,
        provider_task_id,
        updates.get("status") or current_status or None,
        bool(callback_result_url),
        callback_result_url or None,
    )
    return _maybe_retry_image_job_result_persistence(job_id, updated or job)


def _settle_or_cancel_image_job_billing_from_callback(
    job_id: str,
    job: Dict[str, Any],
    callback_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Settle/cancel open image reservation after provider callback."""
    if not isinstance(job, dict):
        return job or {}
    if job.get("billing_settled"):
        return job

    status = _normalize_generation_status(job.get("status"))
    billing_context = job.get("billing_context") if isinstance(job.get("billing_context"), dict) else {}
    callback_payload = callback_payload if isinstance(callback_payload, dict) else {}

    try:
        reservation_tx_id = int(job.get("reservation_tx_id") or 0) or None
    except Exception:
        reservation_tx_id = None
    if not reservation_tx_id:
        return job

    if status in {"failed", "error", "canceled", "cancelled"}:
        db = SessionLocal()
        try:
            if _reservation_already_closed(db, reservation_tx_id):
                _set_image_job(job_id, billing_settled=True, billing_pending=False, reservation_tx_id=None)
                with IMAGE_JOB_LOCK:
                    return dict(IMAGE_JOB_STORE.get(job_id) or job)
            reason = str(
                job.get("error")
                or callback_payload.get("failure_reason")
                or callback_payload.get("error")
                or status
            )
            billing_service.cancel_reservation(db, reservation_tx_id, reason)
            _set_image_job(job_id, billing_settled=True, billing_pending=False, reservation_tx_id=None)
            logger.info(
                "[ImageJob] canceled pending reservation | job_id=%s reservation_tx_id=%s reason=%s",
                job_id,
                reservation_tx_id,
                reason,
            )
        except Exception:
            logger.exception(
                "[ImageJob] cancel pending reservation failed | job_id=%s reservation_tx_id=%s",
                job_id,
                reservation_tx_id,
            )
        finally:
            db.close()
        with IMAGE_JOB_LOCK:
            return dict(IMAGE_JOB_STORE.get(job_id) or job)

    if status not in {"succeeded", "completed", "done"}:
        return job

    db = SessionLocal()
    try:
        if _reservation_already_closed(db, reservation_tx_id):
            _set_image_job(job_id, billing_settled=True, billing_pending=False, reservation_tx_id=None)
            with IMAGE_JOB_LOCK:
                return dict(IMAGE_JOB_STORE.get(job_id) or job)

        is_token_billing = bool(billing_context.get("is_token_billing"))
        provider = str(
            job.get("provider")
            or billing_context.get("provider")
            or ""
        ).strip() or None
        model = str(
            job.get("model")
            or billing_context.get("model")
            or ""
        ).strip() or None
        if is_token_billing:
            settle_details = {
                "input_tokens": int(billing_context.get("input_tokens") or 0),
                "output_tokens": int(billing_context.get("output_tokens") or billing_context.get("estimated_total_tokens") or 0),
                "total_tokens": int(billing_context.get("estimated_total_tokens") or 0),
                "status": "SETTLED",
                "billing_mode": "ACTUAL",
                "token_source": "estimate",
            }
        else:
            settle_details = {
                "item": "image",
                "image_count": 1,
                "width": int(billing_context.get("width") or job.get("width") or 0),
                "height": int(billing_context.get("height") or job.get("height") or 0),
                "status": "SETTLED",
                "billing_mode": "ACTUAL",
            }
            ar = str(billing_context.get("aspect_ratio") or job.get("aspect_ratio") or "").strip()
            if ar:
                settle_details["aspect_ratio"] = ar
        if provider:
            settle_details["provider"] = provider
        if model:
            settle_details["model"] = model
        system_api_id = billing_context.get("system_api_id")
        if system_api_id is not None:
            settle_details["system_api_id"] = system_api_id
        for key in ("project_id", "episode_id", "shot_id", "entity_id"):
            val = billing_context.get(key) or job.get(key)
            if val not in (None, ""):
                try:
                    settle_details[key] = int(val)
                except Exception:
                    pass
        provider_task_id = _extract_job_provider_task_id(job)
        if provider_task_id:
            settle_details["provider_task_id"] = provider_task_id
            settle_details["task_id"] = provider_task_id

        billing_service.settle_reservation(db, reservation_tx_id, settle_details)
        _set_image_job(job_id, billing_settled=True, billing_pending=False, reservation_tx_id=None)
        logger.info(
            "[ImageJob] settled pending reservation from callback | job_id=%s reservation_tx_id=%s provider=%s model=%s",
            job_id,
            reservation_tx_id,
            provider,
            model,
        )
    except Exception:
        logger.exception(
            "[ImageJob] settle pending reservation failed | job_id=%s reservation_tx_id=%s",
            job_id,
            reservation_tx_id,
        )
    finally:
        db.close()
    with IMAGE_JOB_LOCK:
        return dict(IMAGE_JOB_STORE.get(job_id) or job)


def _find_image_jobs_by_provider_callback_ticket(callback_ticket: str) -> List[Tuple[str, Dict[str, Any]]]:
    stable_ticket = str(callback_ticket or "").strip()
    if not stable_ticket:
        return []

    matches: List[Tuple[str, Dict[str, Any]]] = []
    seen_job_ids: Set[str] = set()

    direct_job_id = _extract_generation_job_id_from_ticket("image", stable_ticket)
    if direct_job_id:
        with IMAGE_JOB_LOCK:
            direct_live = dict(IMAGE_JOB_STORE.get(direct_job_id) or {})
        if direct_live:
            if not direct_live.get("provider_callback_ticket"):
                direct_live["provider_callback_ticket"] = stable_ticket
                _set_image_job(direct_job_id, provider_callback_ticket=stable_ticket)
                with IMAGE_JOB_LOCK:
                    direct_live = dict(IMAGE_JOB_STORE.get(direct_job_id) or direct_live)
            if _extract_job_provider_callback_ticket(direct_live) in {"", stable_ticket}:
                return [(direct_job_id, direct_live)]

        direct_db = _read_image_job_file(direct_job_id)
        if isinstance(direct_db, dict):
            if not direct_db.get("provider_callback_ticket"):
                _set_image_job(direct_job_id, provider_callback_ticket=stable_ticket)
                with IMAGE_JOB_LOCK:
                    hydrated = dict(IMAGE_JOB_STORE.get(direct_job_id) or {})
                if hydrated:
                    direct_db = hydrated
            if _extract_job_provider_callback_ticket(direct_db) in {"", stable_ticket}:
                with IMAGE_JOB_LOCK:
                    IMAGE_JOB_STORE[direct_job_id] = dict(direct_db)
                return [(direct_job_id, dict(direct_db))]

    with IMAGE_JOB_LOCK:
        live_jobs = [(job_id, dict(job or {})) for job_id, job in IMAGE_JOB_STORE.items()]

    for job_id, job in live_jobs:
        if _extract_job_provider_callback_ticket(job) != stable_ticket:
            continue
        matches.append((job_id, job))
        seen_job_ids.add(job_id)
        if len(matches) >= GENERATION_CALLBACK_JOB_MATCH_MAX_ITEMS:
            return matches

    try:
        from app.services.generation_task_queue import find_generation_job_states_by_callback_ticket

        db_jobs = find_generation_job_states_by_callback_ticket(kind="image", callback_ticket=stable_ticket, limit=50)
        for db_job in db_jobs:
            if not isinstance(db_job, dict):
                continue
            job_id = str(db_job.get("job_id") or "").strip()
            if not job_id or job_id in seen_job_ids:
                continue
            with IMAGE_JOB_LOCK:
                IMAGE_JOB_STORE[job_id] = dict(db_job)
            matches.append((job_id, dict(db_job)))
            seen_job_ids.add(job_id)
            if len(matches) >= GENERATION_CALLBACK_JOB_MATCH_MAX_ITEMS:
                return matches
    except Exception as exc:
        logger.warning("[ImageJob] failed to scan db callback ticket matches | callback_ticket=%s error=%s", stable_ticket, exc)

    try:
        if os.path.isdir(IMAGE_JOB_FILE_DIR):
            scanned_files = 0
            for entry in os.listdir(IMAGE_JOB_FILE_DIR):
                if not entry.endswith(".json"):
                    continue
                scanned_files += 1
                if scanned_files > GENERATION_CALLBACK_JOB_FILE_SCAN_MAX_FILES:
                    logger.info(
                        "[ImageJob] callback ticket file scan reached cap | callback_ticket=%s scanned=%s cap=%s",
                        stable_ticket,
                        scanned_files,
                        GENERATION_CALLBACK_JOB_FILE_SCAN_MAX_FILES,
                    )
                    break
                job_id = entry[:-5].strip()
                if not job_id or job_id in seen_job_ids:
                    continue
                file_job = _read_image_job_file(job_id)
                if not isinstance(file_job, dict):
                    continue
                if _extract_job_provider_callback_ticket(file_job) != stable_ticket:
                    continue
                with IMAGE_JOB_LOCK:
                    IMAGE_JOB_STORE[job_id] = dict(file_job)
                matches.append((job_id, dict(file_job)))
                seen_job_ids.add(job_id)
                if len(matches) >= GENERATION_CALLBACK_JOB_MATCH_MAX_ITEMS:
                    break
    except Exception as exc:
        logger.warning("[ImageJob] failed to scan callback ticket matches | callback_ticket=%s error=%s", stable_ticket, exc)

    return matches


async def _finalize_image_jobs_from_provider_callback(callback_ticket: str) -> None:
    from app.services.generation_task_queue import mark_generation_task_status_external

    stable_ticket = str(callback_ticket or "").strip()
    if not stable_ticket:
        return

    matched_jobs = _find_image_jobs_by_provider_callback_ticket(stable_ticket)
    if not matched_jobs:
        if _should_log_callback_no_match("image", stable_ticket):
            logger.info("[ImageJob] provider callback received with no matching image job | callback_ticket=%s", stable_ticket)
        return

    for job_id, job in matched_jobs:
        callback_payload = _get_generation_callback_payload(stable_ticket) or {}
        callback_status = _normalize_generation_status(
            callback_payload.get("status") or _extract_callback_status(callback_payload)
        )
        callback_is_terminal = callback_status in {"succeeded", "failed", "canceled"}
        if callback_is_terminal:
            mark_generation_task_status_external(job_id, status="callback_processing", error=None)

        previous_status = _normalize_generation_status(job.get("status"))
        previous_result_url = _extract_job_result_url(job.get("result"))
        try:
            updated_job = _maybe_finalize_image_job_from_grsai_callback(job_id, job)
            if callback_is_terminal:
                updated_job = _settle_or_cancel_image_job_billing_from_callback(
                    job_id,
                    updated_job,
                    callback_payload,
                )
        except Exception as exc:
            logger.exception("[ImageJob] callback processing failed | job_id=%s callback_ticket=%s", job_id, stable_ticket)
            if callback_is_terminal:
                mark_generation_task_status_external(job_id, status="waiting_callback", error=str(exc))
            continue
        updated_status = _normalize_generation_status(updated_job.get("status"))
        updated_result_url = _extract_job_result_url(updated_job.get("result"))

        if updated_status in {"succeeded", "completed", "done"}:
            mark_generation_task_status_external(job_id, status="completed", error=None)
        elif updated_status in {"failed", "error"}:
            mark_generation_task_status_external(job_id, status="failed", error=str(updated_job.get("error") or "callback finalized failed") or None)
        elif updated_status in {"canceled", "cancelled"}:
            mark_generation_task_status_external(job_id, status="canceled", error=str(updated_job.get("error") or "Cancelled") or None)
        elif callback_is_terminal:
            mark_generation_task_status_external(job_id, status="waiting_callback", error=None)

        if updated_status == previous_status and updated_result_url == previous_result_url:
            continue

        callback_url = _resolve_callback_url_from_payload(updated_job)
        if not callback_url:
            continue
        await _dispatch_generation_callback("image", callback_url, updated_job)



def _maybe_retry_video_job_result_persistence(job_id: str, job: Dict[str, Any]) -> Dict[str, Any]:
    job = _hydrate_video_job_record(job_id, job)
    status = _normalize_generation_status(job.get("status"))
    if status not in {"succeeded", "completed", "done", "waiting_callback"}:
        return job

    result = job.get("result")
    if not isinstance(result, dict) or not _video_result_needs_persistence_retry(result):
        return job

    meta = dict(result.get("metadata") or {})
    retry_count = int(meta.get("persistence_retry_count") or 0)
    max_retries = _media_persistence_poll_max_retries()
    if retry_count >= max_retries:
        if not meta.get("persistence_gave_up"):
            meta["persistence_gave_up"] = True
            meta["needs_persistence_retry"] = False
            retry_result = dict(result)
            retry_result["metadata"] = meta
            _set_video_job(job_id, result=retry_result)
            logger.error(
                "[VideoJobPersist] gave up persistence retries | job_id=%s retries=%s source_url=%s",
                job_id,
                retry_count,
                _resolve_video_persistence_source_url(result),
            )
            with VIDEO_JOB_LOCK:
                return dict(VIDEO_JOB_STORE.get(job_id) or job)
        return job

    min_interval = _media_persistence_retry_interval_seconds()
    elapsed_since_retry = _seconds_since_iso_timestamp(meta.get("persistence_retry_at"))
    if elapsed_since_retry is not None and elapsed_since_retry < min_interval:
        return job

    source_url = _resolve_video_persistence_source_url(result)
    if not source_url:
        return job

    if not _mark_video_callback_persist_inflight(job_id):
        logger.debug("[VideoJobPersist] skip retry persistence while in-flight | job_id=%s", job_id)
        return job

    try:
        retry_input = dict(result)
        retry_input["url"] = source_url
        meta["persistence_retry_count"] = retry_count + 1
        meta["persistence_retry_at"] = now_bj_iso()
        meta["needs_persistence_retry"] = True
        retry_input["metadata"] = meta

        reserved_result = dict(result)
        reserved_result["metadata"] = dict(meta)
        _set_video_job(job_id, result=reserved_result)

        logger.info(
            "[VideoJobPersist] retry persistence | job_id=%s attempt=%s/%s source_url=%s",
            job_id,
            retry_count + 1,
            max_retries,
            source_url,
        )
        persisted = _finalize_video_job_result_persistence(job_id, job, retry_input)
        persisted_url = str(persisted.get("url") or "").strip() if isinstance(persisted, dict) else ""
        persisted_meta = persisted.get("metadata") if isinstance(persisted, dict) and isinstance(persisted.get("metadata"), dict) else {}
        source_before = _resolve_video_persistence_source_url(result)
        if persisted_url and _is_persisted_media_localization_success(
            persisted_url,
            source_url=source_before,
            metadata=persisted_meta,
            oss_uploaded=bool(persisted_meta.get("oss_uploaded_success")),
        ):
            _set_video_job(job_id, result=persisted, status="succeeded", finished_at=now_bj_iso())
            with VIDEO_JOB_LOCK:
                updated = dict(VIDEO_JOB_STORE.get(job_id) or job)
            logger.info(
                "[VideoJobPersist] retry persistence succeeded | job_id=%s persisted_url=%s",
                job_id,
                persisted_url,
            )
            # Persistence may finish after the first settle attempt raced/missed reservation.
            if not updated.get("billing_settled"):
                ticket = _extract_job_provider_callback_ticket(updated)
                _schedule_video_job_billing_settle(
                    job_id,
                    updated,
                    _get_generation_callback_payload(ticket) if ticket else {},
                )
            return updated

        if isinstance(persisted, dict) and persisted != result:
            _set_video_job(job_id, result=persisted)
            with VIDEO_JOB_LOCK:
                return dict(VIDEO_JOB_STORE.get(job_id) or job)
        return job
    finally:
        _clear_video_callback_persist_inflight(job_id)


def _media_persistence_poll_max_retries() -> int:
    return max(1, int(os.getenv("MEDIA_PERSISTENCE_POLL_MAX_RETRIES", os.getenv("VIDEO_PERSISTENCE_POLL_MAX_RETRIES", "12"))))


def _media_persistence_retry_interval_seconds() -> int:
    return max(5, int(os.getenv("MEDIA_PERSISTENCE_RETRY_INTERVAL_SECONDS", os.getenv("VIDEO_PERSISTENCE_RETRY_INTERVAL_SECONDS", "20"))))


def _maybe_retry_image_job_result_persistence(job_id: str, job: Dict[str, Any]) -> Dict[str, Any]:
    status = _normalize_generation_status(job.get("status"))
    if status not in {"succeeded", "completed", "done", "waiting_callback", "storing_asset"}:
        return job

    result = job.get("result")
    if not isinstance(result, dict) or not _media_result_needs_persistence_retry(result):
        return job

    meta = dict(result.get("metadata") or {})
    retry_count = int(meta.get("persistence_retry_count") or 0)
    max_retries = _media_persistence_poll_max_retries()
    if retry_count >= max_retries:
        if not meta.get("persistence_gave_up"):
            meta["persistence_gave_up"] = True
            meta["needs_persistence_retry"] = False
            retry_result = dict(result)
            retry_result["metadata"] = meta
            _set_image_job(job_id, result=retry_result)
            logger.error(
                "[ImageJobPersist] gave up persistence retries | job_id=%s retries=%s source_url=%s",
                job_id,
                retry_count,
                _resolve_media_persistence_source_url(result),
            )
            with IMAGE_JOB_LOCK:
                return dict(IMAGE_JOB_STORE.get(job_id) or job)
        return job

    min_interval = _media_persistence_retry_interval_seconds()
    elapsed_since_retry = _seconds_since_iso_timestamp(meta.get("persistence_retry_at"))
    if elapsed_since_retry is not None and elapsed_since_retry < min_interval:
        return job

    source_url = _resolve_media_persistence_source_url(result)
    if not source_url:
        return job

    if not _mark_image_callback_persist_inflight(job_id):
        logger.debug("[ImageJobPersist] skip retry persistence while in-flight | job_id=%s", job_id)
        return job

    try:
        retry_input = dict(result)
        retry_input["url"] = source_url
        meta["persistence_retry_count"] = retry_count + 1
        meta["persistence_retry_at"] = now_bj_iso()
        meta["needs_persistence_retry"] = True
        retry_input["metadata"] = meta

        reserved_result = dict(result)
        reserved_result["metadata"] = dict(meta)
        _set_image_job(job_id, result=reserved_result)

        logger.info(
            "[ImageJobPersist] retry persistence | job_id=%s attempt=%s/%s source_url=%s",
            job_id,
            retry_count + 1,
            max_retries,
            source_url,
        )
        persisted = _finalize_image_job_result_persistence(job_id, job, retry_input)
        persisted_url = str(persisted.get("url") or "").strip() if isinstance(persisted, dict) else ""
        if not persisted_url and isinstance(persisted, dict):
            persisted_url = _extract_job_result_url(persisted)
        if persisted_url and _is_durable_persisted_media_url(persisted_url):
            _set_image_job(job_id, result=persisted, status="succeeded", finished_at=now_bj_iso())
            with IMAGE_JOB_LOCK:
                updated = dict(IMAGE_JOB_STORE.get(job_id) or job)
            logger.info(
                "[ImageJobPersist] retry persistence succeeded | job_id=%s persisted_url=%s",
                job_id,
                persisted_url,
            )
            return updated

        if isinstance(persisted, dict) and persisted != result:
            _set_image_job(job_id, result=persisted)
            with IMAGE_JOB_LOCK:
                return dict(IMAGE_JOB_STORE.get(job_id) or job)
        return job
    finally:
        _clear_image_callback_persist_inflight(job_id)


def _video_callback_result_needs_oss_persist(
    candidate_result: Any,
    db: Optional[Session] = None,
) -> bool:
    if not isinstance(candidate_result, dict):
        return False
    current_url = _extract_job_result_url(candidate_result)
    if not current_url:
        return False
    meta = candidate_result.get("metadata") if isinstance(candidate_result.get("metadata"), dict) else {}
    if _is_persisted_media_localization_success(
        current_url,
        source_url=current_url,
        metadata=meta,
        db=db,
        oss_uploaded=bool(meta.get("oss_uploaded_success")),
    ):
        return False
    if _video_result_needs_persistence_retry(candidate_result, db):
        return True
    return _is_ephemeral_provider_media_url(current_url)


def _finalize_video_job_result_persistence(job_id: str, job: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(result, dict):
        return result

    job = _hydrate_video_job_record(job_id, job)
    raw_url = _extract_job_result_url(result)
    if not raw_url:
        return result

    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        current_user = _resolve_job_owner_user(db, job)
        if not current_user:
            logger.warning(
                "[VideoJobPersist] skipped oss persistence because owner user unresolved | job_id=%s shot_id=%s url=%s",
                job_id,
                job.get("shot_id"),
                raw_url,
            )
            return result

        req_context = _build_generation_job_req_context(job, db)
        if not str(req_context.get("asset_type") or "").strip():
            req_context["asset_type"] = "video"

        metadata = result.get("metadata") if isinstance(result.get("metadata"), dict) else None
        metadata = _enrich_media_metadata_from_generation_context(metadata, job)
        metadata = _enrich_media_metadata_from_generation_context(metadata, req_context)
        for dim_key in ("width", "height"):
            if result.get(dim_key) not in (None, "") and metadata.get(dim_key) in (None, ""):
                metadata[dim_key] = result.get(dim_key)
        metadata["job_id"] = job_id
        logger.info(
            "[VideoJobPersist] start | job_id=%s user_id=%s shot_id=%s raw_url=%s metadata_keys=%s",
            job_id,
            getattr(current_user, "id", None),
            req_context.get("shot_id"),
            raw_url,
            sorted(list(metadata.keys())) if isinstance(metadata, dict) else [],
        )

        filename_base = _build_persist_filename_base_from_context(req_context, db)
        normalized_url, normalized_meta, oss_uploaded = _persist_remote_video_result(
            current_user,
            raw_url,
            metadata,
            filename_base=filename_base,
            db=db,
        )
        logger.info(
            "[VideoJobPersist] normalized | job_id=%s user_id=%s shot_id=%s normalized_url=%s oss=%s",
            job_id,
            getattr(current_user, "id", None),
            req_context.get("shot_id"),
            normalized_url,
            oss_uploaded,
        )

        if normalized_meta is None:
            normalized_meta = {}
        normalized_meta["idempotency_key"] = job_id
        normalized_meta = _enrich_media_metadata_from_generation_context(normalized_meta, metadata)
        normalized_meta = _enrich_media_metadata_from_generation_context(normalized_meta, job)
        normalized_meta = _enrich_media_metadata_from_generation_context(normalized_meta, req_context)

        bind_url, ephemeral_binding, normalized_meta = _resolve_video_bind_url(
            raw_url=raw_url,
            normalized_url=str(normalized_url or "").strip() or None,
            normalized_meta=normalized_meta,
            oss_uploaded=oss_uploaded,
            db=db,
        )

        finalized_result = dict(result)
        display_url = str(normalized_url or "").strip()
        bind_oss_flag = False
        if display_url and (
            oss_uploaded
            or _oss_upload_succeeded_for_url(display_url, normalized_meta, db)
            or _is_persisted_media_localization_success(
                display_url,
                source_url=raw_url,
                metadata=normalized_meta,
                db=db,
                oss_uploaded=oss_uploaded,
            )
        ):
            finalized_result["url"] = display_url
            finalized_result["metadata"] = _clear_ephemeral_persist_flags(normalized_meta)
            if oss_uploaded or _oss_upload_succeeded_for_url(display_url, normalized_meta, db):
                finalized_result["metadata"]["oss_uploaded_success"] = True
            bind_oss_flag = bool(
                not _is_ephemeral_provider_media_url(display_url)
                and (
                    oss_uploaded
                    or _oss_upload_succeeded_for_url(display_url, finalized_result["metadata"], db)
                )
            )
        elif bind_url:
            finalized_result["url"] = bind_url
            finalized_result["metadata"] = normalized_meta
        elif display_url:
            finalized_result["url"] = display_url
            finalized_result["metadata"] = normalized_meta

        shot_bind_url = str(finalized_result.get("url") or bind_url or "").strip()
        if shot_bind_url:
            bind_meta = finalized_result.get("metadata") if isinstance(finalized_result.get("metadata"), dict) else normalized_meta
            bind_oss_flag = bool(
                (oss_uploaded or _oss_upload_succeeded_for_url(shot_bind_url, bind_meta, db))
                and not ephemeral_binding
                and not _is_ephemeral_provider_media_url(shot_bind_url)
            )
            if bind_oss_flag and isinstance(bind_meta, dict):
                bind_meta = _clear_ephemeral_persist_flags(dict(bind_meta))
                bind_meta["oss_uploaded_success"] = True
                finalized_result["metadata"] = bind_meta
            try:
                _register_asset_helper(db, current_user.id, shot_bind_url, req_context, bind_meta)
            except Exception as reg_exc:
                logger.warning(f"[_finalize_video_job_result_persistence] _register_asset_helper failed: {reg_exc}")

            try:
                _bind_generated_media_to_shot(
                    db,
                    current_user,
                    req_context,
                    shot_bind_url,
                    oss_uploaded_success=bind_oss_flag,
                    media_metadata=bind_meta,
                )
                logger.info(
                    "[VideoJobPersist] shot bound | job_id=%s shot_id=%s media_url=%s oss=%s",
                    job_id,
                    req_context.get("shot_id"),
                    shot_bind_url,
                    bind_oss_flag,
                )
            except Exception as bind_exc:
                logger.warning(f"[_finalize_video_job_result_persistence] _bind_generated_media_to_shot failed: {bind_exc}")

        if shot_bind_url and _is_persisted_media_localization_success(
            shot_bind_url,
            source_url=raw_url,
            metadata=finalized_result.get("metadata") if isinstance(finalized_result.get("metadata"), dict) else normalized_meta,
            db=db,
            oss_uploaded=bind_oss_flag if shot_bind_url else False,
        ):
            _set_video_job(job_id, result=finalized_result, status="succeeded")

        return finalized_result
    except Exception as exc:
        logger.warning("[VideoJob] callback persistence finalize failed | job_id=%s error=%s", job_id, exc)
        return result
    finally:
        db.close()

def _maybe_finalize_video_job_from_provider_callback(job_id: str, job: Dict[str, Any]) -> Dict[str, Any]:
    job = _hydrate_video_job_record(job_id, job)
    provider_task_id = _extract_job_provider_task_id(job)
    callback_ticket = _extract_job_provider_callback_ticket(job)
    if not callback_ticket:
        if _should_log_callback_missing_ticket(job_id):
            logger.info("[DEBUG-CB] job_id=%s has no callback_ticket recorded", job_id)
        return job
    callback_payload = _get_generation_callback_payload(callback_ticket)
    if not callback_payload:
        logger.debug("[DEBUG-CB] job_id=%s callback_payload not found for ticket=%s", job_id, callback_ticket)
        return job

    callback_task_id = _extract_callback_task_id(callback_payload)
    if provider_task_id and callback_task_id and callback_task_id != provider_task_id:
        logger.debug("[DEBUG-CB] job_id=%s task_id mismatch! provider_task_id=%s callback_task_id=%s", job_id, provider_task_id, callback_task_id)
        return job

    result = _build_result_from_provider_callback(
        callback_payload,
        fallback_provider=str(job.get("provider") or "").strip() or None,
        fallback_model=str(job.get("model") or "").strip() or None,
    )
    current_result_url = _extract_job_result_url(job.get("result"))
    callback_result_url = _extract_job_result_url(result or {})
    logger.debug("[DEBUG-CB] job_id=%s callback_payload=%s", job_id, repr(callback_payload))
    logger.debug("[DEBUG-CB] result=%s current_result_url=%s callback_result_url=%s", repr(result), current_result_url, callback_result_url)
    callback_status_raw = str(callback_payload.get("status") or "").strip() or _extract_callback_status(callback_payload)
    normalized_status = _normalize_generation_status(callback_status_raw)
    if not normalized_status and callback_result_url:
        normalized_status = "succeeded"
    logger.debug("[DEBUG-CB] callback_status_raw=%s normalized_status=%s", callback_status_raw, normalized_status)

    current_status = _normalize_generation_status(job.get("status"))
    current_error = str(job.get("error") or "").strip()
    current_has_stable_result = _job_has_durable_result_url(job)
    callback_has_ephemeral_result = bool(callback_result_url) and _is_ephemeral_provider_media_url(callback_result_url)

    updates: Dict[str, Any] = {}
    first_success_finalize = current_status not in {"succeeded", "completed", "done"}
    if callback_result_url and not current_has_stable_result:
        if _is_ephemeral_provider_media_url(callback_result_url) and isinstance(result, dict):
            existing_result = job.get("result") if isinstance(job.get("result"), dict) else None
            existing_url = _extract_job_result_url(existing_result)
            if existing_url == callback_result_url and isinstance(existing_result, dict):
                updates["result"] = dict(existing_result)
            else:
                effective_job = dict(job)
                effective_job.update(updates)
                updates["result"] = _stage_ephemeral_media_job_result(
                    job_id,
                    effective_job,
                    dict(result),
                    media_kind="video",
                )
            callback_result_url = _extract_job_result_url(updates["result"])
        elif callback_result_url != current_result_url:
            updates["result"] = result
    elif callback_result_url and current_has_stable_result:
        logger.info(
            "[VideoJob] ignored callback result url because stable result already exists | job_id=%s callback_ticket=%s current_result_url=%s callback_result_url=%s",
            job_id,
            callback_ticket,
            current_result_url,
            callback_result_url,
        )

    if normalized_status in {"succeeded", "failed", "canceled"} and normalized_status != current_status:
        updates["status"] = normalized_status
        if not job.get("finished_at"):
            updates["finished_at"] = now_bj_iso()

    if (
        normalized_status == "succeeded"
        and isinstance(updates.get("result"), dict)
        and _extract_job_result_url(updates.get("result"))
        and first_success_finalize
    ):
        early_save: Dict[str, Any] = {
            "status": updates.get("status") or normalized_status,
            "result": updates["result"],
        }
        if updates.get("finished_at"):
            early_save["finished_at"] = updates["finished_at"]
        if provider_task_id:
            early_save["provider_task_id"] = provider_task_id
        _set_video_job(job_id, **early_save)
        with VIDEO_JOB_LOCK:
            job = dict(VIDEO_JOB_STORE.get(job_id) or job)

    if normalized_status == "succeeded":
        candidate_result = updates.get("result") if isinstance(updates.get("result"), dict) else (
            result if isinstance(result, dict) else (job.get("result") if isinstance(job.get("result"), dict) else None)
        )
        current_result = job.get("result") if isinstance(job.get("result"), dict) else None
        should_persist_on_callback = _video_callback_result_needs_oss_persist(candidate_result)
        if candidate_result and should_persist_on_callback:
            if _mark_video_callback_persist_inflight(job_id):
                try:
                    effective_job = dict(job)
                    effective_job.update(updates)
                    persisted_result = _finalize_video_job_result_persistence(job_id, effective_job, dict(candidate_result))
                    persisted_result_url = _extract_job_result_url(persisted_result)
                    if not persisted_result_url and isinstance(persisted_result, dict):
                        persisted_result_url = str(persisted_result.get("url") or "").strip()
                    persisted_meta = persisted_result.get("metadata") if isinstance(persisted_result, dict) and isinstance(persisted_result.get("metadata"), dict) else {}
                    persist_source_url = _resolve_video_persistence_source_url(candidate_result)
                    if persisted_result_url:
                        updates["result"] = persisted_result
                        callback_result_url = persisted_result_url
                        if _is_persisted_media_localization_success(
                            persisted_result_url,
                            source_url=persist_source_url,
                            metadata=persisted_meta,
                            oss_uploaded=bool(persisted_meta.get("oss_uploaded_success")),
                        ):
                            updates["status"] = "succeeded"
                finally:
                    _clear_video_callback_persist_inflight(job_id)
            else:
                logger.info(
                    "[VideoJob] skip duplicate callback persistence while in-flight | job_id=%s callback_ticket=%s",
                    job_id,
                    callback_ticket,
                )
                return _maybe_retry_video_job_result_persistence(job_id, job)

        if current_error:
            updates["error"] = None
    elif normalized_status in {"failed", "canceled"}:
        failure_parts = [str(callback_payload.get("failure_reason") or "").strip(), str(callback_payload.get("error") or "").strip()]
        failure_text = " | ".join([part for part in failure_parts if part])
        if failure_text and failure_text != current_error:
            updates["error"] = failure_text

    if not updates:
        return _maybe_retry_video_job_result_persistence(job_id, job)

    if provider_task_id:
        updates.setdefault("provider_task_id", provider_task_id)
    _set_video_job(job_id, **updates)
    with VIDEO_JOB_LOCK:
        updated = dict(VIDEO_JOB_STORE.get(job_id) or {})
    logger.info(
        "[VideoJob] finalized from provider callback | job_id=%s callback_ticket=%s provider_task_id=%s status=%s has_result_url=%s result_url=%s",
        job_id,
        callback_ticket,
        provider_task_id,
        updates.get("status") or current_status or None,
        bool(callback_result_url),
        callback_result_url or None,
    )
    return _maybe_retry_video_job_result_persistence(job_id, updated or job)


def _find_video_jobs_by_provider_callback_ticket(callback_ticket: str) -> List[Tuple[str, Dict[str, Any]]]:
    stable_ticket = str(callback_ticket or "").strip()
    if not stable_ticket:
        return []

    matches: List[Tuple[str, Dict[str, Any]]] = []
    seen_job_ids: Set[str] = set()

    direct_job_id = _extract_generation_job_id_from_ticket("video", stable_ticket)
    if direct_job_id:
        with VIDEO_JOB_LOCK:
            direct_live = dict(VIDEO_JOB_STORE.get(direct_job_id) or {})
        if direct_live:
            if not direct_live.get("provider_callback_ticket"):
                direct_live["provider_callback_ticket"] = stable_ticket
                _set_video_job(direct_job_id, provider_callback_ticket=stable_ticket)
                with VIDEO_JOB_LOCK:
                    direct_live = dict(VIDEO_JOB_STORE.get(direct_job_id) or direct_live)
            if _extract_job_provider_callback_ticket(direct_live) in {"", stable_ticket}:
                return [(direct_job_id, _hydrate_video_job_record(direct_job_id, direct_live))]

        direct_db = _read_video_job_file(direct_job_id)
        if isinstance(direct_db, dict):
            if not direct_db.get("provider_callback_ticket"):
                _set_video_job(direct_job_id, provider_callback_ticket=stable_ticket)
                with VIDEO_JOB_LOCK:
                    hydrated = dict(VIDEO_JOB_STORE.get(direct_job_id) or {})
                if hydrated:
                    direct_db = hydrated
            if _extract_job_provider_callback_ticket(direct_db) in {"", stable_ticket}:
                with VIDEO_JOB_LOCK:
                    VIDEO_JOB_STORE[direct_job_id] = dict(direct_db)
                return [(direct_job_id, _hydrate_video_job_record(direct_job_id, dict(direct_db)))]

    with VIDEO_JOB_LOCK:
        live_jobs = [(job_id, dict(job or {})) for job_id, job in VIDEO_JOB_STORE.items()]

    for job_id, job in live_jobs:
        if _extract_job_provider_callback_ticket(job) != stable_ticket:
            continue
        matches.append((job_id, _hydrate_video_job_record(job_id, job)))
        seen_job_ids.add(job_id)
        if len(matches) >= GENERATION_CALLBACK_JOB_MATCH_MAX_ITEMS:
            return matches

    try:
        from app.services.generation_task_queue import find_generation_job_states_by_callback_ticket

        db_jobs = find_generation_job_states_by_callback_ticket(kind="video", callback_ticket=stable_ticket, limit=50)
        for db_job in db_jobs:
            if not isinstance(db_job, dict):
                continue
            job_id = str(db_job.get("job_id") or "").strip()
            if not job_id or job_id in seen_job_ids:
                continue
            with VIDEO_JOB_LOCK:
                VIDEO_JOB_STORE[job_id] = dict(db_job)
            matches.append((job_id, _hydrate_video_job_record(job_id, dict(db_job))))
            seen_job_ids.add(job_id)
            if len(matches) >= GENERATION_CALLBACK_JOB_MATCH_MAX_ITEMS:
                return matches
    except Exception as exc:
        logger.warning("[VideoJob] failed to scan db callback ticket matches | callback_ticket=%s error=%s", stable_ticket, exc)

    try:
        if os.path.isdir(VIDEO_JOB_FILE_DIR):
            scanned_files = 0
            for entry in os.listdir(VIDEO_JOB_FILE_DIR):
                if not entry.endswith(".json"):
                    continue
                scanned_files += 1
                if scanned_files > GENERATION_CALLBACK_JOB_FILE_SCAN_MAX_FILES:
                    logger.info(
                        "[VideoJob] callback ticket file scan reached cap | callback_ticket=%s scanned=%s cap=%s",
                        stable_ticket,
                        scanned_files,
                        GENERATION_CALLBACK_JOB_FILE_SCAN_MAX_FILES,
                    )
                    break
                job_id = entry[:-5].strip()
                if not job_id or job_id in seen_job_ids:
                    continue
                file_job = _read_video_job_file(job_id)
                if not isinstance(file_job, dict):
                    continue
                if _extract_job_provider_callback_ticket(file_job) != stable_ticket:
                    continue
                with VIDEO_JOB_LOCK:
                    VIDEO_JOB_STORE[job_id] = dict(file_job)
                matches.append((job_id, _hydrate_video_job_record(job_id, dict(file_job))))
                seen_job_ids.add(job_id)
                if len(matches) >= GENERATION_CALLBACK_JOB_MATCH_MAX_ITEMS:
                    break
    except Exception as exc:
        logger.warning("[VideoJob] failed to scan callback ticket matches | callback_ticket=%s error=%s", stable_ticket, exc)

    return matches


def _reservation_already_closed(db: Session, reservation_tx_id: int) -> bool:
    try:
        from app.models.all_models import TransactionHistory

        tx = db.query(TransactionHistory).filter(TransactionHistory.id == int(reservation_tx_id)).first()
        if not tx:
            return True
        details = dict(tx.details or {}) if isinstance(tx.details, dict) else {}
        status = str(details.get("status") or "").strip().upper()
        return status in {"SETTLED", "CANCELED", "CANCELLED"}
    except Exception:
        return False


def _persist_video_job_billing_reservation(
    *,
    provider_callback_ticket: Optional[str] = None,
    job_id: Optional[str] = None,
    reservation_tx_id: Optional[int],
    billing_context: Optional[Dict[str, Any]] = None,
    user_id: Optional[int] = None,
) -> None:
    """Persist open reservation onto video job + task payload before provider callback can race."""
    try:
        tx_id = int(reservation_tx_id or 0) or None
    except Exception:
        tx_id = None
    if not tx_id:
        return

    stable_job_id = str(job_id or "").strip()
    if not stable_job_id:
        stable_job_id = _extract_generation_job_id_from_ticket("video", str(provider_callback_ticket or ""))
    if not stable_job_id:
        return

    context = dict(billing_context or {}) if isinstance(billing_context, dict) else {}
    fields: Dict[str, Any] = {
        "reservation_tx_id": int(tx_id),
        "billing_pending": True,
        "billing_settled": False,
        "billing_context": context,
    }
    if user_id is not None:
        try:
            fields["user_id"] = int(user_id)
        except Exception:
            pass
    if provider_callback_ticket:
        fields["provider_callback_ticket"] = str(provider_callback_ticket).strip()
    try:
        _set_video_job(stable_job_id, **fields)
    except Exception as exc:
        logger.warning(
            "[VideoJob] persist billing reservation to job failed | job_id=%s reservation_tx_id=%s err=%s",
            stable_job_id,
            tx_id,
            exc,
        )
    try:
        from app.services.generation_task_queue import patch_generation_task_payload

        patch_generation_task_payload(
            stable_job_id,
            {
                "reservation_tx_id": int(tx_id),
                "billing_pending": True,
                "billing_settled": False,
                "billing_context": context,
            },
        )
    except Exception as exc:
        logger.warning(
            "[VideoJob] persist billing reservation to task payload failed | job_id=%s reservation_tx_id=%s err=%s",
            stable_job_id,
            tx_id,
            exc,
        )


def _find_open_video_reservation_tx_id(
    db: Session,
    *,
    user_id: Optional[int] = None,
    shot_id: Optional[int] = None,
    project_id: Optional[int] = None,
    episode_id: Optional[int] = None,
) -> Optional[int]:
    """Recover a still-open video_gen reservation when job lost reservation_tx_id (multi-worker race)."""
    try:
        from app.models.all_models import TransactionHistory

        uid = int(user_id or 0)
        if uid <= 0:
            return None
        rows = (
            db.query(TransactionHistory)
            .filter(
                TransactionHistory.user_id == uid,
                TransactionHistory.amount < 0,
            )
            .order_by(TransactionHistory.id.desc())
            .limit(60)
            .all()
        )
    except Exception:
        return None

    want_shot = int(shot_id or 0) or None
    want_project = int(project_id or 0) or None
    want_episode = int(episode_id or 0) or None
    for row in rows or []:
        details = dict(getattr(row, "details", None) or {}) if isinstance(getattr(row, "details", None), dict) else {}
        status = str(details.get("status") or "").strip().upper()
        if status != "RESERVED":
            continue
        desc = str(getattr(row, "description", "") or "").strip().lower()
        task_hint = str(details.get("task_type") or details.get("description") or desc or "").strip().lower()
        if "video" not in task_hint and desc and "video" not in desc:
            # Prefer video_gen rows; description is usually the task_type.
            if desc not in {"video_gen", "video"}:
                continue
        row_shot = int(details.get("shot_id") or 0) or None
        row_project = int(details.get("project_id") or getattr(row, "project_id", 0) or 0) or None
        row_episode = int(details.get("episode_id") or getattr(row, "episode_id", 0) or 0) or None
        if want_shot and row_shot and row_shot != want_shot:
            continue
        if want_shot and not row_shot:
            continue
        if want_project and row_project and row_project != want_project:
            continue
        if want_episode and row_episode and row_episode != want_episode:
            continue
        if want_shot and row_shot == want_shot:
            return int(row.id)
        if not want_shot and want_project and row_project == want_project:
            return int(row.id)
    return None


def _extract_kie_callback_settle_fields(
    callback_payload: Optional[Dict[str, Any]],
    *,
    result_meta: Optional[Dict[str, Any]] = None,
    usage: Optional[Dict[str, Any]] = None,
    billing_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Pull KIE/Ark/RunningHub callback actuals: credits, tokens, costTime, RH coins/money, duration/ratio/resolution."""
    out: Dict[str, Any] = {}
    callback_payload = callback_payload if isinstance(callback_payload, dict) else {}
    result_meta = result_meta if isinstance(result_meta, dict) else {}
    usage = usage if isinstance(usage, dict) else {}
    billing_context = billing_context if isinstance(billing_context, dict) else {}

    data = callback_payload.get("data") if isinstance(callback_payload.get("data"), dict) else {}
    event_data = callback_payload.get("eventData") if isinstance(callback_payload.get("eventData"), dict) else {}
    event_usage = event_data.get("usage") if isinstance(event_data.get("usage"), dict) else {}
    sources = (usage, result_meta, event_usage, data, event_data, callback_payload)

    kie_credits = 0.0
    try:
        from app.services.billing_pricing import resolve_provider_kie_credits

        for src in sources:
            kie_credits = float(resolve_provider_kie_credits(src) or 0.0)
            if kie_credits > 0:
                break
    except Exception:
        kie_credits = 0.0
    if kie_credits > 0:
        out["kie_credits_consumed"] = kie_credits
        out["credits_consumed"] = kie_credits
        out["creditsConsumed"] = kie_credits
        out["billing_basis"] = "provider_kie_credits"

    # Ark Seedance callback: usage.completion_tokens / total_tokens.
    token_usage = usage if usage else {}
    if not token_usage:
        for src in sources:
            if isinstance(src, dict) and isinstance(src.get("usage"), dict):
                token_usage = dict(src.get("usage") or {})
                break
    actual_tokens = _resolve_usage_token_total(token_usage)
    if actual_tokens > 0:
        out["output_tokens"] = int(actual_tokens)
        out["total_tokens"] = int(actual_tokens)
        out["completion_tokens"] = int(
            _safe_int_token(token_usage.get("completion_tokens") or token_usage.get("output_tokens") or actual_tokens)
        )
        out["token_source"] = "api_usage"
        out.setdefault("billing_basis", "provider_tokens")

    cost_time = None
    for src in sources:
        if not isinstance(src, dict):
            continue
        for key in ("costTime", "cost_time", "taskCostTime", "task_cost_time"):
            if src.get(key) in (None, ""):
                continue
            try:
                cost_time = float(src.get(key))
            except Exception:
                cost_time = None
            if cost_time is not None and cost_time >= 0:
                break
        if cost_time is not None and cost_time >= 0:
            break
    # Ark: wall-clock from created_at → updated_at (unix seconds).
    if cost_time is None:
        try:
            created_at = float(callback_payload.get("created_at") or data.get("created_at") or 0)
            updated_at = float(callback_payload.get("updated_at") or data.get("updated_at") or 0)
            if created_at > 0 and updated_at >= created_at:
                cost_time = updated_at - created_at
        except Exception:
            cost_time = None
    if cost_time is not None and cost_time >= 0:
        out["provider_cost_time_seconds"] = cost_time
        out["cost_time"] = cost_time
        out["taskCostTime"] = cost_time

    # RunningHub usage: platform coins / wallet money / third-party money (audit; not KIE credits).
    for src in sources:
        if not isinstance(src, dict):
            continue
        if out.get("consumeCoins") in (None, "") and src.get("consumeCoins") not in (None, ""):
            try:
                out["consumeCoins"] = float(src.get("consumeCoins"))
            except Exception:
                pass
        if out.get("consumeMoney") in (None, "") and src.get("consumeMoney") not in (None, ""):
            try:
                out["consumeMoney"] = float(src.get("consumeMoney"))
            except Exception:
                pass
        if out.get("thirdPartyConsumeMoney") in (None, "") and src.get("thirdPartyConsumeMoney") not in (None, ""):
            try:
                out["thirdPartyConsumeMoney"] = float(src.get("thirdPartyConsumeMoney"))
            except Exception:
                pass
        if (
            out.get("consumeCoins") not in (None, "")
            and out.get("consumeMoney") not in (None, "")
            and out.get("thirdPartyConsumeMoney") not in (None, "")
        ):
            break

    # Nested KIE param JSON often carries actual duration / aspect / resolution.
    param_obj: Dict[str, Any] = {}
    raw_param = data.get("param") if isinstance(data, dict) else None
    if raw_param is None:
        raw_param = callback_payload.get("param")
    if isinstance(raw_param, str) and raw_param.strip():
        try:
            parsed_param = json.loads(raw_param)
            if isinstance(parsed_param, dict):
                param_obj = parsed_param
                nested_input = parsed_param.get("input")
                if isinstance(nested_input, str) and nested_input.strip():
                    try:
                        nested_parsed = json.loads(nested_input)
                        if isinstance(nested_parsed, dict):
                            param_obj = {**param_obj, **nested_parsed}
                    except Exception:
                        pass
                elif isinstance(nested_input, dict):
                    param_obj = {**param_obj, **nested_input}
        except Exception:
            param_obj = {}
    elif isinstance(raw_param, dict):
        param_obj = dict(raw_param)

    # Ark puts duration/ratio/resolution on the webhook root.
    duration = (
        callback_payload.get("duration")
        or data.get("duration")
        or param_obj.get("duration")
        or result_meta.get("duration")
        or billing_context.get("duration_seconds")
        or billing_context.get("duration")
    )
    if duration not in (None, ""):
        try:
            out["duration"] = float(duration)
            out["duration_seconds"] = float(duration)
        except Exception:
            pass
    aspect_ratio = (
        callback_payload.get("ratio")
        or callback_payload.get("aspect_ratio")
        or data.get("ratio")
        or param_obj.get("aspect_ratio")
        or result_meta.get("aspect_ratio")
        or billing_context.get("aspect_ratio")
    )
    if aspect_ratio not in (None, ""):
        out["aspect_ratio"] = str(aspect_ratio).strip()
    resolution = (
        callback_payload.get("resolution")
        or data.get("resolution")
        or param_obj.get("resolution")
        or result_meta.get("resolution")
        or billing_context.get("resolution")
    )
    if resolution not in (None, ""):
        out["resolution"] = str(resolution).strip()
    fps = (
        callback_payload.get("framespersecond")
        or callback_payload.get("fps")
        or data.get("framespersecond")
        or billing_context.get("fps")
    )
    if fps not in (None, ""):
        try:
            out["fps"] = int(float(fps))
        except Exception:
            pass
    if callback_payload.get("draft") is not None:
        out["draft_mode"] = bool(callback_payload.get("draft"))
        out["draft"] = bool(callback_payload.get("draft"))
    if callback_payload.get("generate_audio") is not None:
        out["has_audio"] = bool(callback_payload.get("generate_audio"))

    for ts_key, out_key in (
        ("createTime", "provider_create_time_ms"),
        ("completeTime", "provider_complete_time_ms"),
        ("updateTime", "provider_update_time_ms"),
        ("created_at", "provider_create_time_s"),
        ("updated_at", "provider_update_time_s"),
    ):
        for src in (data, callback_payload, result_meta):
            if isinstance(src, dict) and src.get(ts_key) not in (None, ""):
                try:
                    out[out_key] = int(src.get(ts_key))
                except Exception:
                    pass
                break

    return out


def _schedule_video_job_billing_settle(
    job_id: str,
    job: Optional[Dict[str, Any]] = None,
    callback_payload: Optional[Dict[str, Any]] = None,
) -> None:
    """Fire-and-forget settle from sync persistence paths (best effort)."""
    stable_job_id = str(job_id or "").strip()
    if not stable_job_id:
        return
    payload = callback_payload if isinstance(callback_payload, dict) else {}
    job_snapshot = dict(job or {})

    async def _runner() -> None:
        try:
            current = _hydrate_video_job_record(stable_job_id, job_snapshot)
            await _settle_or_cancel_video_job_billing_from_callback(stable_job_id, current, payload)
        except Exception as exc:
            logger.warning(
                "[VideoJob] scheduled settle failed | job_id=%s err=%s",
                stable_job_id,
                exc,
            )

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_runner())
    except RuntimeError:
        try:
            asyncio.run(_runner())
        except Exception as exc:
            logger.warning(
                "[VideoJob] scheduled settle (asyncio.run) failed | job_id=%s err=%s",
                stable_job_id,
                exc,
            )


def _cancel_video_job_pending_reservation(
    job_id: str,
    job: Optional[Dict[str, Any]],
    reason: str,
    *,
    usage_metadata: Optional[Dict[str, Any]] = None,
    extra_details: Optional[Dict[str, Any]] = None,
) -> None:
    job = job if isinstance(job, dict) else {}
    if job.get("billing_settled"):
        return
    try:
        reservation_tx_id = int(job.get("reservation_tx_id") or 0) or None
    except Exception:
        reservation_tx_id = None
    if not reservation_tx_id:
        return

    db = SessionLocal()
    try:
        if _reservation_already_closed(db, reservation_tx_id):
            _set_video_job(job_id, billing_settled=True, billing_pending=False, reservation_tx_id=None)
            return
        billing_service.cancel_reservation(
            db,
            reservation_tx_id,
            reason,
            usage_metadata=usage_metadata if isinstance(usage_metadata, dict) else None,
            extra_details=extra_details if isinstance(extra_details, dict) else None,
        )
        _set_video_job(
            job_id,
            billing_settled=True,
            billing_pending=False,
            reservation_tx_id=None,
            billing_cancel_reason=str(reason or "")[:500] or None,
        )
        logger.info(
            "[VideoJob] canceled pending reservation | job_id=%s reservation_tx_id=%s reason=%s",
            job_id,
            reservation_tx_id,
            str(reason or "")[:200],
        )
    except Exception as exc:
        logger.warning(
            "[VideoJob] cancel pending reservation failed | job_id=%s reservation_tx_id=%s error=%s",
            job_id,
            reservation_tx_id,
            exc,
        )
    finally:
        db.close()


async def _settle_or_cancel_video_job_billing_from_callback(
    job_id: str,
    job: Dict[str, Any],
    callback_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Settle/cancel open video reservation after provider callback using actual usage when possible."""
    job = _hydrate_video_job_record(job_id, job) if job_id else (job or {})
    if not isinstance(job, dict):
        return job or {}
    if job.get("billing_settled"):
        return job

    status = _normalize_generation_status(job.get("status"))
    billing_context = job.get("billing_context") if isinstance(job.get("billing_context"), dict) else {}
    callback_payload = callback_payload if isinstance(callback_payload, dict) else {}

    try:
        reservation_tx_id = int(job.get("reservation_tx_id") or 0) or None
    except Exception:
        reservation_tx_id = None

    if status in {"failed", "error", "canceled", "cancelled"}:
        if not reservation_tx_id:
            # Best-effort recover reservation before cancel.
            db_probe = SessionLocal()
            try:
                reservation_tx_id = _find_open_video_reservation_tx_id(
                    db_probe,
                    user_id=job.get("user_id"),
                    shot_id=job.get("shot_id") or billing_context.get("shot_id"),
                    project_id=job.get("project_id") or billing_context.get("project_id"),
                    episode_id=job.get("episode_id") or billing_context.get("episode_id"),
                )
                if reservation_tx_id:
                    job = dict(job)
                    job["reservation_tx_id"] = reservation_tx_id
            finally:
                db_probe.close()
        reason = str(job.get("error") or callback_payload.get("failure_reason") or callback_payload.get("error") or status)
        cancel_usage: Dict[str, Any] = {}
        cancel_extra: Dict[str, Any] = {}
        try:
            from app.services.media_service import _extract_provider_task_usage, _normalize_provider_task_usage

            cancel_usage = _normalize_provider_task_usage(_extract_provider_task_usage(callback_payload))
        except Exception:
            cancel_usage = {}
        try:
            cancel_extra = _extract_kie_callback_settle_fields(
                callback_payload,
                usage=cancel_usage,
                billing_context=billing_context,
            )
        except Exception:
            cancel_extra = {}
        if cancel_usage:
            cancel_extra.setdefault("usage_source", "callback")
            cancel_extra.setdefault("provider_usage", cancel_usage)
        _cancel_video_job_pending_reservation(
            job_id,
            job,
            reason,
            usage_metadata=cancel_usage or None,
            extra_details=cancel_extra or None,
        )
        with VIDEO_JOB_LOCK:
            return dict(VIDEO_JOB_STORE.get(job_id) or job)

    if status not in {"succeeded", "completed", "done"}:
        return job

    db = SessionLocal()
    try:
        if not reservation_tx_id:
            reservation_tx_id = _find_open_video_reservation_tx_id(
                db,
                user_id=job.get("user_id"),
                shot_id=job.get("shot_id") or billing_context.get("shot_id"),
                project_id=job.get("project_id") or billing_context.get("project_id"),
                episode_id=job.get("episode_id") or billing_context.get("episode_id"),
            )
            if reservation_tx_id:
                _set_video_job(
                    job_id,
                    reservation_tx_id=int(reservation_tx_id),
                    billing_pending=True,
                    billing_context=billing_context,
                )
                job = dict(job)
                job["reservation_tx_id"] = int(reservation_tx_id)
                job["billing_pending"] = True
                logger.info(
                    "[VideoJob] recovered open reservation for settle | job_id=%s reservation_tx_id=%s shot_id=%s",
                    job_id,
                    reservation_tx_id,
                    job.get("shot_id") or billing_context.get("shot_id"),
                )
        if not reservation_tx_id:
            logger.warning(
                "[VideoJob] skip settle: no reservation_tx_id | job_id=%s shot_id=%s user_id=%s",
                job_id,
                job.get("shot_id") or billing_context.get("shot_id"),
                job.get("user_id"),
            )
            return job

        # Allow settle even when billing_pending was not set yet (callback-before-return race).
        if not job.get("billing_pending"):
            _set_video_job(job_id, billing_pending=True)
            job = dict(job)
            job["billing_pending"] = True

        if _reservation_already_closed(db, reservation_tx_id):
            _set_video_job(job_id, billing_settled=True, billing_pending=False, reservation_tx_id=None)
            with VIDEO_JOB_LOCK:
                return dict(VIDEO_JOB_STORE.get(job_id) or job)

        is_token_billing = bool(billing_context.get("is_token_billing"))
        provider = str(
            job.get("provider")
            or billing_context.get("provider")
            or ""
        ).strip() or None
        model = str(
            job.get("model")
            or billing_context.get("model")
            or ""
        ).strip() or None
        provider_lower = str(provider or "").strip().lower()
        is_kie_provider = (
            provider_lower == "kie"
            or provider_lower.startswith("kie/")
            or "kie.ai" in provider_lower
        )
        provider_task_id = _extract_job_provider_task_id(job) or _extract_callback_task_id(callback_payload)

        usage: Dict[str, Any] = {}
        result_meta = {}
        result_obj = job.get("result") if isinstance(job.get("result"), dict) else {}
        if isinstance(result_obj.get("metadata"), dict):
            result_meta = result_obj.get("metadata") or {}
            usage = _extract_provider_usage_from_metadata(result_meta)
        if not usage and callback_payload:
            try:
                from app.services.media_service import _extract_provider_task_usage, _normalize_provider_task_usage

                usage = _normalize_provider_task_usage(_extract_provider_task_usage(callback_payload))
            except Exception:
                usage = {}

        usage_source = str(result_meta.get("usage_source") or "").strip() or ("callback" if usage else "")
        # Prefer raw callback usage (Ark tokens / RunningHub coins+money+taskCostTime) over sparse metadata.
        if callback_payload and (
            _resolve_usage_token_total(usage) <= 0
            or not usage
            or (
                usage.get("consumeCoins") in (None, "")
                and usage.get("consumeMoney") in (None, "")
                and usage.get("taskCostTime") in (None, "")
            )
        ):
            try:
                from app.services.media_service import _extract_provider_task_usage, _normalize_provider_task_usage

                callback_usage = _normalize_provider_task_usage(_extract_provider_task_usage(callback_payload))
                if _resolve_usage_token_total(callback_usage) > 0:
                    usage = callback_usage
                    usage_source = "callback"
                elif callback_usage and (
                    not usage
                    or callback_usage.get("consumeCoins") not in (None, "")
                    or callback_usage.get("consumeMoney") not in (None, "")
                    or callback_usage.get("thirdPartyConsumeMoney") not in (None, "")
                    or callback_usage.get("taskCostTime") not in (None, "")
                ):
                    merged_usage = dict(usage or {})
                    merged_usage.update(callback_usage)
                    usage = merged_usage
                    usage_source = usage_source or "callback"
            except Exception:
                pass

        kie_fields = _extract_kie_callback_settle_fields(
            callback_payload,
            result_meta=result_meta,
            usage=usage,
            billing_context=billing_context,
        )
        # KIE credits → non-token settle; Ark callback tokens → token settle.
        if kie_fields.get("kie_credits_consumed"):
            is_token_billing = False
        elif (
            kie_fields.get("total_tokens")
            or kie_fields.get("completion_tokens")
            or _resolve_usage_token_total(usage) > 0
        ):
            is_token_billing = True
        elif is_kie_provider and not is_token_billing:
            pass

        # Re-query provider task for Ark/ZLHub-style token usage when callback omits it.
        if is_token_billing and _resolve_usage_token_total(usage) <= 0 and provider_task_id:
            try:
                user_id = int(job.get("user_id") or 0)
                user = db.query(User).filter(User.id == user_id).first() if user_id else None
                runtime = _resolve_media_runtime_target(
                    provider=provider,
                    model=model,
                    media_type="video",
                    category="Video",
                    user_id=user_id,
                    user_credits=int(getattr(user, "credits", 0) or 0) if user else 0,
                    system_api_id=billing_context.get("system_api_id"),
                )
                pre_api_cfg = runtime.get("pre_api_cfg") if isinstance(runtime.get("pre_api_cfg"), dict) else {}
                cfg_payload = pre_api_cfg.get("config") if isinstance(pre_api_cfg.get("config"), dict) else {}
                api_key = media_service._pick_runtime_api_key(
                    cfg_payload or pre_api_cfg,
                    pre_api_cfg.get("api_key"),
                    session=db,
                    provider_name=str(runtime.get("resolved_provider") or provider or ""),
                )
                query_endpoint = (
                    cfg_payload.get("query_endpoint")
                    or cfg_payload.get("base_url")
                    or cfg_payload.get("endpoint")
                    or pre_api_cfg.get("base_url")
                    or pre_api_cfg.get("endpoint")
                )
                fetched = await asyncio.to_thread(
                    media_service.fetch_provider_task_usage,
                    task_id=str(provider_task_id),
                    api_key=str(api_key or ""),
                    query_endpoint=str(query_endpoint or "") or None,
                    provider=str(runtime.get("resolved_provider") or provider or ""),
                    refresh_if_missing=True,
                )
                if isinstance(fetched, dict) and fetched:
                    usage = {k: v for k, v in fetched.items() if k != "raw_task"}
                    usage_source = "task_query"
                    provider = str(runtime.get("resolved_provider") or provider or "").strip() or provider
                    model = str(runtime.get("resolved_model") or model or "").strip() or model
            except Exception as usage_err:
                logger.warning(
                    "[VideoJob] callback task usage query failed | job_id=%s task_id=%s error=%s",
                    job_id,
                    provider_task_id,
                    usage_err,
                )

        if is_token_billing:
            actual_tokens = _resolve_usage_token_total(usage)
            token_source = "api_usage" if actual_tokens > 0 else "estimate"
            settle_details: Dict[str, Any] = {
                "status": "SETTLED",
                "billing_mode": "ACTUAL",
                "draft_mode": bool(billing_context.get("draft_mode")),
                "draft": bool(billing_context.get("draft_mode")),
                "use_prev_video": bool(billing_context.get("use_prev_video")),
                "shot_continuation": bool(billing_context.get("shot_continuation")),
                "has_video_input": bool(billing_context.get("has_video_input")),
                "width": billing_context.get("width"),
                "height": billing_context.get("height"),
                "fps": billing_context.get("fps") or 24,
            }
            if billing_context.get("aspect_ratio"):
                settle_details["aspect_ratio"] = billing_context.get("aspect_ratio")
            if billing_context.get("resolution"):
                settle_details["resolution"] = billing_context.get("resolution")
            if billing_context.get("duration_seconds") or billing_context.get("duration"):
                settle_details["duration"] = billing_context.get("duration_seconds") or billing_context.get("duration")
                settle_details["duration_seconds"] = settle_details["duration"]
            if actual_tokens <= 0:
                settle_duration = max(5, int(billing_context.get("duration_seconds") or billing_context.get("duration") or 5))
                draft_mode = bool(billing_context.get("draft_mode"))
                draft_coeff = float(billing_context.get("draft_token_coefficient") or 1.0)
                if not (0 < draft_coeff):
                    draft_coeff = 1.0
                settle_estimate = billing_service.estimate_video_token_usage(
                    width=int(billing_context.get("width") or 1280),
                    height=int(billing_context.get("height") or 720),
                    fps=int(billing_context.get("fps") or 24),
                    output_duration_seconds=settle_duration,
                    has_video_input=bool(billing_context.get("has_video_input")),
                    input_duration_seconds=(
                        billing_context.get("input_duration_seconds")
                        or billing_context.get("input_duration")
                    ),
                    draft_token_coefficient=draft_coeff,
                    method=(
                        "seedance2_video_token_formula"
                        if billing_context.get("is_seedance_2") or billing_service.is_seedance_2_model(provider, model)
                        else "video_token_formula"
                    ),
                )
                actual_tokens = int(settle_estimate.get("tokens") or billing_context.get("estimated_tokens") or 0)
                settle_details["video_token_estimate"] = settle_estimate
                settle_details["estimation_method"] = settle_estimate.get("estimation_method")
            else:
                settle_details["completion_tokens"] = _safe_int_token(
                    usage.get("completion_tokens") or usage.get("output_tokens") or actual_tokens
                )
            settle_details["output_tokens"] = int(max(0, actual_tokens))
            settle_details["total_tokens"] = int(max(0, actual_tokens))
            settle_details["token_source"] = token_source
        else:
            settle_details = {
                "duration": billing_context.get("duration"),
                "duration_seconds": billing_context.get("duration_seconds") or billing_context.get("duration"),
                "status": "SETTLED",
                "billing_mode": "ACTUAL",
                "draft_mode": bool(billing_context.get("draft_mode")),
                "draft": bool(billing_context.get("draft_mode")),
                "use_prev_video": bool(billing_context.get("use_prev_video")),
                "shot_continuation": bool(billing_context.get("shot_continuation")),
                "has_video_input": bool(billing_context.get("has_video_input")),
            }
            if billing_context.get("input_duration_seconds") is not None:
                settle_details["input_duration_seconds"] = billing_context.get("input_duration_seconds")
            elif billing_context.get("input_duration") is not None:
                settle_details["input_duration_seconds"] = billing_context.get("input_duration")
            if billing_context.get("width"):
                settle_details["width"] = billing_context.get("width")
            if billing_context.get("height"):
                settle_details["height"] = billing_context.get("height")
            if billing_context.get("resolution"):
                settle_details["resolution"] = billing_context.get("resolution")
            if billing_context.get("aspect_ratio"):
                settle_details["aspect_ratio"] = billing_context.get("aspect_ratio")

        # Overlay callback actuals (KIE credits / Ark tokens / costTime / duration).
        if kie_fields:
            for key, value in kie_fields.items():
                if value not in (None, ""):
                    settle_details[key] = value
            if kie_fields.get("kie_credits_consumed"):
                settle_details["usage_source"] = usage_source or "callback"
                if not usage:
                    usage = {
                        "creditsConsumed": kie_fields.get("kie_credits_consumed"),
                        "credits_consumed": kie_fields.get("kie_credits_consumed"),
                        "kie_credits_consumed": kie_fields.get("kie_credits_consumed"),
                        "credits": kie_fields.get("kie_credits_consumed"),
                    }
                    usage_source = settle_details["usage_source"]
            elif kie_fields.get("total_tokens") or kie_fields.get("completion_tokens"):
                settle_details["usage_source"] = usage_source or "callback"
                settle_details["token_source"] = settle_details.get("token_source") or "api_usage"
                if _resolve_usage_token_total(usage) <= 0:
                    usage = {
                        "completion_tokens": kie_fields.get("completion_tokens"),
                        "output_tokens": kie_fields.get("output_tokens") or kie_fields.get("total_tokens"),
                        "total_tokens": kie_fields.get("total_tokens"),
                    }

        if usage:
            settle_details["provider_usage"] = usage
            settle_details["usage_source"] = usage_source or settle_details.get("usage_source") or "provider"
        if provider:
            settle_details["provider"] = provider
        if model:
            settle_details["model"] = model
        if billing_context.get("system_api_id") is not None:
            settle_details["system_api_id"] = billing_context.get("system_api_id")
        if billing_context.get("project_id"):
            settle_details["project_id"] = billing_context.get("project_id")
        if billing_context.get("episode_id"):
            settle_details["episode_id"] = billing_context.get("episode_id")
        if billing_context.get("shot_id"):
            settle_details["shot_id"] = billing_context.get("shot_id")
        elif job.get("shot_id"):
            settle_details["shot_id"] = job.get("shot_id")
        if provider_task_id:
            settle_details["provider_task_id"] = provider_task_id
            settle_details["task_id"] = provider_task_id
            settle_details["taskId"] = provider_task_id
        settle_details = _merge_provider_task_ids_into_settle(
            settle_details,
            callback_payload if isinstance(callback_payload, dict) else {},
            job if isinstance(job, dict) else {},
            billing_context if isinstance(billing_context, dict) else {},
        )

        billing_service.settle_reservation(db, reservation_tx_id, settle_details)
        _set_video_job(
            job_id,
            billing_settled=True,
            billing_pending=False,
            reservation_tx_id=None,
            billing_settle_token_source=settle_details.get("token_source"),
            billing_settle_usage_source=settle_details.get("usage_source"),
            billing_settle_kie_credits=settle_details.get("kie_credits_consumed"),
            billing_basis=settle_details.get("billing_basis"),
            billing_settle_cost_time=settle_details.get("provider_cost_time_seconds"),
        )
        logger.info(
            "[VideoJob] settled pending reservation from callback | job_id=%s reservation_tx_id=%s "
            "token_source=%s usage_source=%s total_tokens=%s kie_credits=%s cost_time=%s billing_basis=%s "
            "actual_cost_basis=supplier×multiplier",
            job_id,
            reservation_tx_id,
            settle_details.get("token_source"),
            settle_details.get("usage_source"),
            settle_details.get("total_tokens"),
            settle_details.get("kie_credits_consumed"),
            settle_details.get("provider_cost_time_seconds"),
            settle_details.get("billing_basis"),
        )
    except Exception as exc:
        logger.warning(
            "[VideoJob] settle pending reservation failed | job_id=%s reservation_tx_id=%s error=%s",
            job_id,
            reservation_tx_id,
            exc,
        )
    finally:
        db.close()

    with VIDEO_JOB_LOCK:
        return dict(VIDEO_JOB_STORE.get(job_id) or job)


async def _finalize_video_jobs_from_provider_callback(callback_ticket: str) -> None:
    from app.services.generation_task_queue import mark_generation_task_status_external

    stable_ticket = str(callback_ticket or "").strip()
    if not stable_ticket:
        return

    matched_jobs = _find_video_jobs_by_provider_callback_ticket(stable_ticket)
    if not matched_jobs:
        if _finalize_video_shot_callback_without_job(stable_ticket):
            return
        if _should_log_callback_no_match("video", stable_ticket):
            logger.info("[VideoJob] provider callback received with no matching video job | callback_ticket=%s", stable_ticket)
        return

    for job_id, job in matched_jobs:
        callback_payload = _get_generation_callback_payload(stable_ticket) or {}
        callback_status = _normalize_generation_status(
            callback_payload.get("status") or _extract_callback_status(callback_payload)
        )
        if not callback_status and _extract_job_result_url(
            _build_result_from_provider_callback(
                callback_payload,
                fallback_provider=str(job.get("provider") or "").strip() or None,
            ) or {}
        ):
            callback_status = "succeeded"
        callback_is_terminal = callback_status in {"succeeded", "failed", "canceled"}
        if callback_is_terminal:
            mark_generation_task_status_external(job_id, status="callback_processing", error=None)

        previous_status = _normalize_generation_status(job.get("status"))
        previous_result_url = _extract_job_result_url(job.get("result"))
        try:
            updated_job = _maybe_finalize_video_job_from_provider_callback(job_id, job)
            updated_job = await _settle_or_cancel_video_job_billing_from_callback(
                job_id,
                updated_job,
                callback_payload,
            )
        except Exception as exc:
            logger.exception("[VideoJob] callback processing failed | job_id=%s callback_ticket=%s", job_id, stable_ticket)
            if callback_is_terminal:
                mark_generation_task_status_external(job_id, status="waiting_callback", error=str(exc))
            continue
        updated_status = _normalize_generation_status(updated_job.get("status"))
        updated_result_url = _extract_job_result_url(updated_job.get("result"))

        if updated_status in {"succeeded", "completed", "done"}:
            mark_generation_task_status_external(job_id, status="completed", error=None)
        elif updated_status in {"failed", "error"}:
            mark_generation_task_status_external(job_id, status="failed", error=str(updated_job.get("error") or "callback finalized failed") or None)
        elif updated_status in {"canceled", "cancelled"}:
            mark_generation_task_status_external(job_id, status="canceled", error=str(updated_job.get("error") or "Cancelled") or None)
        elif callback_is_terminal:
            mark_generation_task_status_external(job_id, status="waiting_callback", error=None)

        if updated_status == previous_status and updated_result_url == previous_result_url:
            continue

        callback_url = _resolve_callback_url_from_payload(updated_job)
        if not callback_url:
            continue
        await _dispatch_generation_callback("video", callback_url, updated_job)


def _finalize_video_shot_callback_without_job(callback_ticket: str) -> bool:
    """Finalize callback persistence for synchronous shot-level video tickets (video-shot-<shot_id>)."""
    stable_ticket = str(callback_ticket or "").strip()
    match = re.fullmatch(r"video-shot-(\d+)", stable_ticket)
    if not match:
        return False

    shot_id = int(match.group(1))
    callback_payload = _get_generation_callback_payload(stable_ticket)
    if not callback_payload:
        return False

    result = _build_result_from_provider_callback(callback_payload)
    result_url = _extract_job_result_url(result or {})
    callback_status_raw = str(callback_payload.get("status") or "").strip() or _extract_callback_status(callback_payload)
    normalized_status = _normalize_generation_status(callback_status_raw)
    if not normalized_status and result_url:
        normalized_status = "succeeded"

    if normalized_status != "succeeded" or not result_url:
        return False

    db = SessionLocal()
    try:
        shot = db.query(Shot).filter(Shot.id == int(shot_id)).first()
        if not shot:
            logger.warning("[VideoShotCallback] shot not found | callback_ticket=%s shot_id=%s", stable_ticket, shot_id)
            return False

        project_id = _asset_optional_int(getattr(shot, "project_id", None))
        episode_id = _asset_optional_int(getattr(shot, "episode_id", None))
        if not episode_id and getattr(shot, "scene_id", None):
            scene = db.query(Scene).filter(Scene.id == int(shot.scene_id)).first()
            if scene:
                episode_id = _asset_optional_int(getattr(scene, "episode_id", None))
        if not project_id and episode_id:
            episode = db.query(Episode).filter(Episode.id == int(episode_id)).first()
            if episode:
                project_id = _asset_optional_int(getattr(episode, "project_id", None))

        user_id = 0
        if project_id:
            project_row = db.query(Project).filter(Project.id == int(project_id)).first()
            if project_row:
                user_id = int(getattr(project_row, "owner_id", 0) or 0)

        if user_id <= 0:
            logger.warning(
                "[VideoShotCallback] project owner missing, cannot finalize asset registration | callback_ticket=%s shot_id=%s project_id=%s",
                stable_ticket,
                shot_id,
                project_id,
            )
            return False

        pseudo_job = {
            "user_id": int(user_id),
            "shot_id": int(shot_id),
            "project_id": int(project_id) if project_id else None,
            "episode_id": int(episode_id) if episode_id else None,
            "shot_number": getattr(shot, "shot_id", None),
            "shot_name": getattr(shot, "shot_name", None),
            "asset_type": "video",
            "provider_callback_ticket": stable_ticket,
        }

        persisted = _finalize_video_job_result_persistence(stable_ticket, pseudo_job, result)
        persisted_url = _extract_job_result_url(persisted or {})
        if persisted_url:
            logger.info(
                "[VideoShotCallback] finalized without job record | callback_ticket=%s shot_id=%s persisted_url=%s",
                stable_ticket,
                shot_id,
                persisted_url,
            )
            return True
        return False
    except Exception as exc:
        logger.warning("[VideoShotCallback] finalize failed | callback_ticket=%s shot_id=%s err=%s", stable_ticket, shot_id, exc)
        return False
    finally:
        db.close()


def _apply_no_store_headers(response: Response) -> None:
    response.headers["Cache-Control"] = "no-cache, no-store, max-age=0, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"


def _mark_generation_callback_inflight(ticket: str) -> bool:
    stable_ticket = str(ticket or "").strip()
    if not stable_ticket:
        return False
    now_ts = time.time()
    with GENERATION_CALLBACK_ASYNC_INFLIGHT_LOCK:
        stale = [
            key
            for key, ts in GENERATION_CALLBACK_ASYNC_INFLIGHT.items()
            if (now_ts - float(ts or 0.0)) > GENERATION_CALLBACK_ASYNC_INFLIGHT_TTL_SECONDS
        ]
        for key in stale:
            GENERATION_CALLBACK_ASYNC_INFLIGHT.pop(key, None)
        if len(GENERATION_CALLBACK_ASYNC_INFLIGHT) > GENERATION_CALLBACK_ASYNC_INFLIGHT_MAX_ITEMS:
            ordered = sorted(
                GENERATION_CALLBACK_ASYNC_INFLIGHT.items(),
                key=lambda item: float(item[1] or 0.0),
            )
            overflow = len(GENERATION_CALLBACK_ASYNC_INFLIGHT) - GENERATION_CALLBACK_ASYNC_INFLIGHT_MAX_ITEMS
            for key, _ in ordered[:overflow]:
                GENERATION_CALLBACK_ASYNC_INFLIGHT.pop(key, None)
        if stable_ticket in GENERATION_CALLBACK_ASYNC_INFLIGHT:
            return False
        GENERATION_CALLBACK_ASYNC_INFLIGHT[stable_ticket] = now_ts
    return True


def _clear_generation_callback_inflight(ticket: str) -> None:
    stable_ticket = str(ticket or "").strip()
    if not stable_ticket:
        return
    with GENERATION_CALLBACK_ASYNC_INFLIGHT_LOCK:
        GENERATION_CALLBACK_ASYNC_INFLIGHT.pop(stable_ticket, None)


def _mark_image_callback_persist_inflight(job_id: str) -> bool:
    stable_job_id = str(job_id or "").strip()
    if not stable_job_id:
        return False

    now_ts = time.time()
    with IMAGE_CALLBACK_PERSIST_INFLIGHT_LOCK:
        stale = [
            key
            for key, ts in IMAGE_CALLBACK_PERSIST_INFLIGHT.items()
            if (now_ts - float(ts or 0.0)) > IMAGE_CALLBACK_PERSIST_INFLIGHT_TTL_SECONDS
        ]
        for key in stale:
            IMAGE_CALLBACK_PERSIST_INFLIGHT.pop(key, None)

        if len(IMAGE_CALLBACK_PERSIST_INFLIGHT) > IMAGE_CALLBACK_PERSIST_INFLIGHT_MAX_ITEMS:
            ordered = sorted(
                IMAGE_CALLBACK_PERSIST_INFLIGHT.items(),
                key=lambda item: float(item[1] or 0.0),
            )
            overflow = len(IMAGE_CALLBACK_PERSIST_INFLIGHT) - IMAGE_CALLBACK_PERSIST_INFLIGHT_MAX_ITEMS
            for key, _ in ordered[:overflow]:
                IMAGE_CALLBACK_PERSIST_INFLIGHT.pop(key, None)

        if stable_job_id in IMAGE_CALLBACK_PERSIST_INFLIGHT:
            return False

        IMAGE_CALLBACK_PERSIST_INFLIGHT[stable_job_id] = now_ts
    return True


def _clear_image_callback_persist_inflight(job_id: str) -> None:
    stable_job_id = str(job_id or "").strip()
    if not stable_job_id:
        return
    with IMAGE_CALLBACK_PERSIST_INFLIGHT_LOCK:
        IMAGE_CALLBACK_PERSIST_INFLIGHT.pop(stable_job_id, None)


def _mark_video_callback_persist_inflight(job_id: str) -> bool:
    stable_job_id = str(job_id or "").strip()
    if not stable_job_id:
        return False

    now_ts = time.time()
    with VIDEO_CALLBACK_PERSIST_INFLIGHT_LOCK:
        stale_keys = [
            key
            for key, ts in VIDEO_CALLBACK_PERSIST_INFLIGHT.items()
            if (now_ts - float(ts or 0.0)) > VIDEO_CALLBACK_PERSIST_INFLIGHT_TTL_SECONDS
        ]
        for key in stale_keys:
            VIDEO_CALLBACK_PERSIST_INFLIGHT.pop(key, None)

        if len(VIDEO_CALLBACK_PERSIST_INFLIGHT) > VIDEO_CALLBACK_PERSIST_INFLIGHT_MAX_ITEMS:
            ordered = sorted(
                VIDEO_CALLBACK_PERSIST_INFLIGHT.items(),
                key=lambda item: float(item[1] or 0.0),
            )
            overflow = len(VIDEO_CALLBACK_PERSIST_INFLIGHT) - VIDEO_CALLBACK_PERSIST_INFLIGHT_MAX_ITEMS
            for key, _ in ordered[:overflow]:
                VIDEO_CALLBACK_PERSIST_INFLIGHT.pop(key, None)

        if stable_job_id in VIDEO_CALLBACK_PERSIST_INFLIGHT:
            return False

        VIDEO_CALLBACK_PERSIST_INFLIGHT[stable_job_id] = now_ts
    return True


def _clear_video_callback_persist_inflight(job_id: str) -> None:
    stable_job_id = str(job_id or "").strip()
    if not stable_job_id:
        return
    with VIDEO_CALLBACK_PERSIST_INFLIGHT_LOCK:
        VIDEO_CALLBACK_PERSIST_INFLIGHT.pop(stable_job_id, None)


async def _process_generation_callback_async(ticket: str, payload: Dict[str, Any]) -> None:
    stable_ticket = str(ticket or "").strip()
    if not stable_ticket:
        return

    def _run_callback_finalizers() -> None:
        if stable_ticket.startswith("image-job-"):
            asyncio.run(_finalize_image_jobs_from_provider_callback(stable_ticket))
        elif stable_ticket.startswith("video-job-"):
            asyncio.run(_finalize_video_jobs_from_provider_callback(stable_ticket))
        else:
            asyncio.run(_finalize_image_jobs_from_provider_callback(stable_ticket))
            asyncio.run(_finalize_video_jobs_from_provider_callback(stable_ticket))

    try:
        async with GENERATION_CALLBACK_FINALIZE_SEMAPHORE:
            await asyncio.to_thread(_set_generation_callback_payload, stable_ticket, payload)
            await asyncio.to_thread(_run_callback_finalizers)
    except Exception:
        logger.exception("[GenerationCallback] async finalize failed | ticket=%s", stable_ticket)
    finally:
        _clear_generation_callback_inflight(stable_ticket)


def _build_provider_alias_lookup(db: Session) -> Dict[str, str]:
    rows = db.query(ProviderKeyPool.provider, ProviderKeyPool.provider_alias).all()
    alias_map: Dict[str, str] = {}
    for row in rows:
        provider_key = str(getattr(row, "provider", "") or "").strip().lower()
        alias_text = str(getattr(row, "provider_alias", "") or "").strip()
        if provider_key and alias_text:
            alias_map[provider_key] = alias_text
    return alias_map


def _resolve_provider_alias(alias_map: Dict[str, str], provider: Any) -> Optional[str]:
    provider_key = str(provider or "").strip().lower()
    if not provider_key:
        return None
    alias_text = str((alias_map or {}).get(provider_key) or "").strip()
    return alias_text or None


def _attach_provider_alias_to_dict(meta: Any, alias_map: Dict[str, str]) -> Any:
    if not isinstance(meta, dict):
        return meta
    out = dict(meta)
    provider_text = str(out.get("provider") or "").strip()
    if provider_text and not str(out.get("provider_alias") or "").strip():
        alias_text = _resolve_provider_alias(alias_map, provider_text)
        if alias_text:
            out["provider_alias"] = alias_text
    return out


def _attach_provider_alias_deep(payload: Any, alias_map: Dict[str, str]) -> Any:
    if isinstance(payload, dict):
        out = {k: _attach_provider_alias_deep(v, alias_map) for k, v in payload.items()}
        provider_text = str(out.get("provider") or "").strip()
        if provider_text and not str(out.get("provider_alias") or "").strip():
            alias_text = _resolve_provider_alias(alias_map, provider_text)
            if alias_text:
                out["provider_alias"] = alias_text
        return out
    if isinstance(payload, list):
        return [_attach_provider_alias_deep(item, alias_map) for item in payload]
    return payload


_TERMINAL_GENERATION_JOB_STATUSES = frozenset({"succeeded", "failed", "canceled", "cancelled", "error"})


def _is_terminal_generation_job_status(status: Any) -> bool:
    return str(status or "").strip().lower() in _TERMINAL_GENERATION_JOB_STATUSES


def _unlink_job_snapshot_file(path_func, job_id: str) -> None:
    try:
        path = path_func(job_id)
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def _drop_image_job_locked(job_id: str, *, unlink_file: bool = True) -> None:
    stable_job_id = str(job_id or "").strip()
    if not stable_job_id:
        return
    job = IMAGE_JOB_STORE.pop(stable_job_id, None) or {}
    IMAGE_JOB_TASKS.pop(stable_job_id, None)
    task_scope = str(job.get("task_scope") or "").strip()
    if task_scope and IMAGE_ACTIVE_SCOPE_STORE.get(task_scope) == stable_job_id:
        IMAGE_ACTIVE_SCOPE_STORE.pop(task_scope, None)
    stale_idempotency_keys = [
        key
        for key, value in IMAGE_SUBMIT_IDEMPOTENCY_STORE.items()
        if str((value or {}).get("job_id") or "") == stable_job_id
    ]
    for key in stale_idempotency_keys:
        IMAGE_SUBMIT_IDEMPOTENCY_STORE.pop(key, None)
    if unlink_file:
        _unlink_job_snapshot_file(_image_job_file_path, stable_job_id)


def _drop_video_job_locked(job_id: str, *, unlink_file: bool = True) -> None:
    stable_job_id = str(job_id or "").strip()
    if not stable_job_id:
        return
    job = VIDEO_JOB_STORE.pop(stable_job_id, None) or {}
    VIDEO_JOB_TASKS.pop(stable_job_id, None)
    task_scope = str(job.get("task_scope") or "").strip()
    if task_scope and VIDEO_ACTIVE_SCOPE_STORE.get(task_scope) == stable_job_id:
        VIDEO_ACTIVE_SCOPE_STORE.pop(task_scope, None)
    stale_idempotency_keys = [
        key
        for key, value in VIDEO_SUBMIT_IDEMPOTENCY_STORE.items()
        if str((value or {}).get("job_id") or "") == stable_job_id
    ]
    for key in stale_idempotency_keys:
        VIDEO_SUBMIT_IDEMPOTENCY_STORE.pop(key, None)
    if unlink_file:
        _unlink_job_snapshot_file(_video_job_file_path, stable_job_id)


def _prune_image_jobs_locked() -> None:
    now = _coerce_naive_utc_datetime()
    expired_ids = []

    for job_id, job in IMAGE_JOB_STORE.items():
        if not _is_terminal_generation_job_status(job.get("status")):
            continue

        finished_at = _parse_iso_datetime(job.get("finished_at")) or _coerce_naive_utc_datetime(_job_sort_key(job))
        age_seconds = (now - finished_at).total_seconds()
        if age_seconds > IMAGE_JOB_TTL_SECONDS:
            expired_ids.append(job_id)

    for job_id in expired_ids:
        _drop_image_job_locked(job_id)

    if len(IMAGE_JOB_STORE) > IMAGE_JOB_MAX_ITEMS:
        # Overflow must never evict non-terminal jobs; clients may still be polling them.
        terminal_ordered = sorted(
            (
                (job_id, job)
                for job_id, job in IMAGE_JOB_STORE.items()
                if _is_terminal_generation_job_status((job or {}).get("status"))
            ),
            key=lambda pair: _job_sort_key(pair[1]),
        )
        overflow_count = len(IMAGE_JOB_STORE) - IMAGE_JOB_MAX_ITEMS
        for job_id, _ in terminal_ordered[:overflow_count]:
            _drop_image_job_locked(job_id)
        if len(IMAGE_JOB_STORE) > IMAGE_JOB_MAX_ITEMS:
            logger.warning(
                "image job store over capacity with active jobs retained | size=%s max=%s",
                len(IMAGE_JOB_STORE),
                IMAGE_JOB_MAX_ITEMS,
            )

    _prune_image_submit_idempotency_locked(now)


def _prune_video_jobs_locked() -> None:
    now = _coerce_naive_utc_datetime()
    expired_ids = []

    for job_id, job in VIDEO_JOB_STORE.items():
        if not _is_terminal_generation_job_status(job.get("status")):
            continue

        finished_at = _parse_iso_datetime(job.get("finished_at")) or _coerce_naive_utc_datetime(_job_sort_key(job))
        age_seconds = (now - finished_at).total_seconds()
        if age_seconds > VIDEO_JOB_TTL_SECONDS:
            expired_ids.append(job_id)

    for job_id in expired_ids:
        _drop_video_job_locked(job_id)

    if len(VIDEO_JOB_STORE) > VIDEO_JOB_MAX_ITEMS:
        # Overflow must never evict non-terminal jobs; clients may still be polling them.
        terminal_ordered = sorted(
            (
                (job_id, job)
                for job_id, job in VIDEO_JOB_STORE.items()
                if _is_terminal_generation_job_status((job or {}).get("status"))
            ),
            key=lambda pair: _job_sort_key(pair[1]),
        )
        overflow_count = len(VIDEO_JOB_STORE) - VIDEO_JOB_MAX_ITEMS
        for job_id, _ in terminal_ordered[:overflow_count]:
            _drop_video_job_locked(job_id)
        if len(VIDEO_JOB_STORE) > VIDEO_JOB_MAX_ITEMS:
            logger.warning(
                "video job store over capacity with active jobs retained | size=%s max=%s",
                len(VIDEO_JOB_STORE),
                VIDEO_JOB_MAX_ITEMS,
            )

    _prune_video_submit_idempotency_locked(now)


def _snapshot_image_job_stats() -> Dict[str, Any]:
    with IMAGE_JOB_LOCK:
        _prune_image_jobs_locked()
        jobs = list(IMAGE_JOB_STORE.values())

    status_counts: Dict[str, int] = {}
    created_times: List[datetime] = []
    approx_bytes = 0

    for job in jobs:
        status = str(job.get("status") or "unknown").lower()
        status_counts[status] = status_counts.get(status, 0) + 1

        created_at = _parse_iso_datetime(job.get("created_at"))
        if created_at:
            created_times.append(created_at)

        try:
            approx_bytes += len(json.dumps(job, ensure_ascii=False, default=str))
        except Exception:
            approx_bytes += 0

    oldest_created_at = min(created_times).isoformat() if created_times else None
    newest_created_at = max(created_times).isoformat() if created_times else None

    return {
        "store_items": len(jobs),
        "status_counts": status_counts,
        "oldest_created_at": oldest_created_at,
        "newest_created_at": newest_created_at,
        "approx_store_bytes": approx_bytes,
        "approx_store_mb": round(approx_bytes / (1024 * 1024), 3),
        "ttl_seconds": IMAGE_JOB_TTL_SECONDS,
        "max_items": IMAGE_JOB_MAX_ITEMS,
    }


def _vendor_failed_message(provider: Optional[str], reason: Any) -> str:
    vendor = str(provider or "").strip() or "unknown"
    detail = str(reason or "unknown error").strip()
    if "供应商调用失败" in detail:
        return detail
    return f"{vendor}供应商调用失败: {detail}"


def _build_scene_analysis_blocking_failure_detail(
    blocking_codes: List[str],
    integrity_warnings: List[str],
    subject_warnings: List[str],
) -> str:
    codes = {str(code or "").strip() for code in (blocking_codes or []) if str(code or "").strip()}
    reasons_cn: List[str] = []

    if "ANALYSIS_STRUCTURE_INCOMPLETE" in codes:
        reasons_cn.append("结果缺少必要结构段，无法形成完整的场景分析")
    if "ANALYSIS_SUBJECTS_UNVERIFIED" in codes:
        reasons_cn.append("角色/环境/道具的一致性校验未完成，当前结果不可靠")
    if "ANALYSIS_SUBJECTS_INCOMPLETE" in codes:
        reasons_cn.append("角色/环境/道具覆盖不完整，当前结果不能继续使用")
    if "ANALYSIS_OUTPUT_TRUNCATED" in codes:
        reasons_cn.append("返回内容疑似被截断，结果不完整")
    if "ANALYSIS_JSON_INVALID" in codes:
        reasons_cn.append("返回内容的结构片段损坏，系统无法安全解析")
    if "ANALYSIS_SUBJECT_INDEX_MISSING" in codes:
        reasons_cn.append("未解析到完整的资产清单（Subject Index）区块")
    if "ANALYSIS_SUBJECT_INDEX_HEADER_ONLY" in codes:
        reasons_cn.append("仅解析到 Subject Index 表头，缺少实体条目")
    if "ANALYSIS_SUBJECT_INDEX_REQUIRED" in codes:
        reasons_cn.append("缺少资产清单（Subject Index），无法继续场景编排或资产生成")

    raw_reasons: List[str] = []
    raw_reasons.extend([str(x or "").strip() for x in (integrity_warnings or []) if str(x or "").strip()])
    raw_reasons.extend([str(x or "").strip() for x in (subject_warnings or []) if str(x or "").strip()])
    raw_reasons = list(dict.fromkeys(raw_reasons))

    detail_parts: List[str] = []
    if reasons_cn:
        detail_parts.append("；".join(reasons_cn[:3]))

    if raw_reasons:
        detail_parts.append("技术明细：" + "；".join(raw_reasons[:3]))

    body = "；".join([part for part in detail_parts if part])
    if body:
        return "场景分析结果不可用：" + body + "。请直接重新执行剧本分析。"
    return "场景分析结果不可用：返回内容结构不完整或校验未通过。请直接重新执行剧本分析。"



# fix-db-schema moved to app.api.routers.admin_ops

from app.services.system_log_service import (
    append_ui_system_logs,
    get_ui_system_log_path,
    log_action,
    read_ui_system_logs,
)
from app.schemas.system_log import (
    SystemLogOut,
    SystemLogCreate,
    UiSystemLogBatchCreate,
    UiSystemLogBatchOut,
    UiSystemLogListOut,
    UiSystemLogReadEntry,
    ScriptAnalysisAiDiagnosisRequest,
    ScriptAnalysisAiDiagnosisOut,
)
from app.services.script_analysis_ai_diagnosis import (
    OPS_SUPPORT_EMAIL,
    build_diagnosis_messages,
    build_ops_email_body,
    normalize_page_scope,
)

def _can_use_system_settings(user: User) -> bool:
    return bool((user.credits or 0) > 0 or user.is_superuser or user.is_system)


def _log_batch_sys_event(
    *,
    kind: str,
    phase: str,
    user_id: int,
    user_name: str,
    project_id: Optional[int] = None,
    episode_id: Optional[int] = None,
    job_id: Optional[str] = None,
    item_id: Optional[int] = None,
    item_label: Optional[str] = None,
    result: Optional[str] = None,
    message: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    action_kind = str(kind or "batch").strip().replace("-", "_").upper()
    action_phase = str(phase or "event").strip().replace("-", "_").upper()
    action = f"BATCH_{action_kind}_{action_phase}"
    details_payload: Dict[str, Any] = {
        "kind": kind,
        "phase": phase,
        "job_id": job_id,
        "project_id": project_id,
        "episode_id": episode_id,
        "item_id": item_id,
        "item_label": item_label,
        "result": result,
        "message": message,
        "timestamp": now_bj_iso(),
    }
    if isinstance(extra, dict) and extra:
        details_payload["extra"] = extra

    log_db = SessionLocal()
    try:
        log_action(
            log_db,
            user_id=int(user_id),
            user_name=str(user_name or f"user_{user_id}"),
            action=action,
            details=json.dumps(details_payload, ensure_ascii=False, default=str),
        )
    except Exception as e:
        logger.warning(
            "[batch_syslog] failed action=%s kind=%s phase=%s job_id=%s err=%s",
            action,
            kind,
            phase,
            job_id,
            e,
        )
    finally:
        log_db.close()



# system_logs routes moved to app.api.routers.admin_ops


# script_analysis_diagnosis routes moved to app.api.routers.script_analysis_diagnosis

@router.get("/settings/effective")
def get_effective_setting_snapshot(
    category: str = "LLM",
    provider: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resolved_setting, source, meta = _resolve_effective_api_setting_meta(
        db,
        current_user,
        provider=provider,
        category=category,
    )

    if not resolved_setting:
        return {
            "found": False,
            "category": category,
            "provider": provider,
            "source": source,
            "meta": meta,
        }

    api_key = (resolved_setting.api_key or "").strip()
    masked = ""
    if api_key:
        masked = api_key[:4] + "***" + api_key[-4:] if len(api_key) > 8 else ("*" * len(api_key))

    return {
        "found": True,
        "source": source,
        "selection_source": "system_only",
        "setting_id": resolved_setting.id,
        "owner_user_id": getattr(resolved_setting, "user_id", None),
        "category": resolved_setting.category,
        "provider": resolved_setting.provider,
        "model": resolved_setting.model,
        "endpoint": resolved_setting.base_url,
        "webhook": (resolved_setting.config or {}).get("webHook"),
        "has_api_key": bool(api_key),
        "api_key_masked": masked,
        "meta": meta,
    }

_PROMPT_SKILL_ALIAS = {
    "scene_analysis.txt": "skill:scene_analysis/scene_analysis.txt",
    "subject_generation.txt": "subject_generation.txt",
    "story_generator_global.txt": "skill:story_generation/story_generator_global.txt",
    "story_generator_episode.txt": "skill:story_generation/story_generator_episode.txt",
    "story_generator_analyze_novel.txt": "skill:story_generation/story_generator_analyze_novel.txt",
    "story_generator_structure_creative_input.txt": "skill:story_generation/story_generator_structure_creative_input.txt",
    "story_generator_structure_extract_key_elements.txt": "skill:story_generation/story_generator_structure_extract_key_elements.txt",
    "story_generator_trending_ai_short_dramas.txt": "skill:story_generation/story_generator_trending_ai_short_dramas.txt",
    "story_generator_industry_analysis_ai_short_dramas.txt": "skill:story_generation/story_generator_industry_analysis_ai_short_dramas.txt",
    "script_generator_scenes.txt": "skill:script_generation/script_generator_scenes.txt",
    "script_generator_episode_script.txt": "master_episode_writer.md",
    "scene_regenerate.txt": "skill:script_generation/scene_regenerate.txt",
    "shot_generator.txt": "skills/shot_generation.md",
    "shot_regenerate.txt": "shot_regenerate.txt",
    "promo_generator_global.txt": "skill:promo_generation/promo_generator_global.txt",
    "promo_generator_episode_script.txt": "master_episode_writer.md",
    "image_style_extractor.txt": "skill:image_style_extraction/image_style_extractor.txt",
    "voice_tts_planner_system.txt": "voice_tts_planner_system.txt",
    "voice_tts_planner_user.txt": "voice_tts_planner_user.txt",
}


def _build_prompt_resolution_debug(prompt_ref: str) -> Dict[str, Any]:
    ref = str(prompt_ref or "").strip()
    alias = _PROMPT_SKILL_ALIAS.get(ref)
    prompt_dir = os.path.join(str(settings.BASE_DIR), "app", "core", "prompts")
    skill_root = os.path.join(prompt_dir, "skills")

    candidates: List[str] = []
    for item in [ref, alias]:
        item_text = str(item or "").strip()
        if item_text and item_text not in candidates:
            candidates.append(item_text)

    out: Dict[str, Any] = {
        "prompt_ref": ref,
        "alias": alias,
        "prompt_dir": prompt_dir,
        "candidates": [],
    }

    for item_text in candidates:
        candidate_info: Dict[str, Any] = {"ref": item_text}
        if item_text.startswith("skill:"):
            raw = item_text[len("skill:"):]
            parts = [piece for piece in raw.split("/") if piece]
            skill_id = parts[0] if parts else ""
            prompt_name = parts[1] if len(parts) > 1 else "system_prompt.txt"
            skill_file = os.path.join(skill_root, skill_id, prompt_name)
            meta = get_skill_meta(skill_id)
            prompt_refs = meta.get("prompts") if isinstance(meta, dict) and isinstance(meta.get("prompts"), list) else []

            fallback_candidates = []
            for fallback_ref in prompt_refs:
                fallback_text = str(fallback_ref or "").strip()
                if not fallback_text:
                    continue
                fallback_path = os.path.join(prompt_dir, fallback_text)
                fallback_candidates.append({
                    "ref": fallback_text,
                    "path": fallback_path,
                    "exists": os.path.isfile(fallback_path),
                })

            candidate_info.update({
                "type": "skill",
                "skill_id": skill_id,
                "prompt_name": prompt_name,
                "direct_path": skill_file,
                "direct_exists": os.path.isfile(skill_file),
                "registry_skill_found": bool(meta),
                "registry_prompt_refs": prompt_refs,
                "fallback_candidates": fallback_candidates,
            })
        else:
            prompt_path = os.path.join(prompt_dir, item_text)
            candidate_info.update({
                "type": "file",
                "path": prompt_path,
                "exists": os.path.isfile(prompt_path),
            })
        out["candidates"].append(candidate_info)

    return out



# prompts/analyze_scene moved to app.api.routers.prompts_analyze

def _compute_project_cost_estimation_snapshot(db: Session, project_id: int) -> Dict[str, Any]:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    episodes = db.query(Episode).filter(
        Episode.project_id == project_id,
        _active_episode_clause(),
    ).all()
    episode_ids = [int(getattr(ep, "id", 0) or 0) for ep in episodes if getattr(ep, "id", None) is not None]
    scenes = db.query(Scene).filter(Scene.episode_id.in_(episode_ids), _active_scene_clause()).all() if episode_ids else []
    scene_ids = [int(getattr(sc, "id", 0) or 0) for sc in scenes if getattr(sc, "id", None) is not None]
    shots = db.query(Shot).filter(Shot.scene_id.in_(scene_ids), _active_shot_clause()).all() if scene_ids else []

    cfg = get_project_cost_estimation_config(db)
    snapshot = compute_project_cost_estimation(
        project_title=getattr(project, "title", "") or "",
        global_info=(project.global_info if isinstance(project.global_info, dict) else {}),
        episodes=episodes,
        scenes=scenes,
        shots=shots,
        config=cfg,
    )
    snapshot["computed_at"] = now_bj_iso()
    snapshot["project_id"] = int(project_id)
    return snapshot


def _recompute_and_persist_project_cost_estimation(db: Session, project_id: int) -> Dict[str, Any]:
    try:
        db.flush()
    except Exception:
        pass

    snapshot = _compute_project_cost_estimation_snapshot(db, project_id)
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    gi = dict(project.global_info) if isinstance(project.global_info, dict) else {}
    gi["cost_estimation"] = snapshot
    project.global_info = gi
    db.add(project)
    return snapshot



# projects/episodes/scenes/shots workspace moved to app.api.routers.projects_workspace
