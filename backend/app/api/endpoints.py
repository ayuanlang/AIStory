
import os
from typing import Any, Dict
import importlib

from app.core.queue_config import DEFAULT_QUEUE_CONFIG, load_queue_config, save_queue_config

_q_conf = load_queue_config()


# queue cfg -> generation_runtime.queue_worker (early re-export for admin routes)
from app.services.generation_runtime.queue_worker import (  # noqa: E402,F401
    _is_pure_callback_mode_enabled,
    _queue_cfg_bool,
    _queue_cfg_int,
    _queue_runtime_config,
)

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



from app.services.endpoint_misc import (  # noqa: E402
    _is_schema_compat_error,
    _require_review_models,
    _run_with_schema_self_heal,
    _safe_int,
)

from app.api.deps import get_current_claims  # noqa: E402,F401


router = APIRouter()


# admin queue routes -> routers.admin_queue

media_service = MediaGenerationService()
logger = logging.getLogger("api_logger")



# db session utils -> app.services.db_session_utils

from app.services.video_submit_dedup import *  # noqa: F401,F403
from app.services import video_submit_dedup as _vsd
globals().update({k:v for k,v in vars(_vsd).items() if not k.startswith('__')})

from app.services.analyze_scene_dedup import (  # noqa: E402,F401
    _ANALYZE_SCENE_CONTINUATION_SEGMENT_HARD_CAP,
    _ANALYZE_SCENE_DEDUP_LAST_PRUNE_TS,
    _ANALYZE_SCENE_DEDUP_PRUNE_INTERVAL_SECONDS,
    _ANALYZE_SCENE_DEDUP_PRUNE_LOCK,
    _ANALYZE_SCENE_DEDUP_TABLE_LOCK,
    _ANALYZE_SCENE_DEDUP_TABLE_READY,
    _ANALYZE_SCENE_DEDUP_WINDOW_SECONDS,
    _ANALYZE_SCENE_OUTPUT_CHAR_HARD_CAP,
    _ANALYZE_SCENE_SEGMENT_TIMEOUT_SECONDS,
)



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



# script analysis llm config -> app.services.script_analysis_llm_config

# analyze_scene dedup -> app.services.analyze_scene_dedup

# tasks routes -> routers.tasks

# --- generation runtime job store (canonical) ---
from app.services.generation_runtime.job_store import (  # noqa: E402,F401
    ASSET_REGISTRATION_LOCK,
    EPISODE_SCENE_JOB_THREADS,
    EPISODE_SCENE_JOB_THREADS_LOCK,
    GENERATION_CALLBACK_ASYNC_INFLIGHT,
    GENERATION_CALLBACK_ASYNC_INFLIGHT_LOCK,
    GENERATION_CALLBACK_ASYNC_INFLIGHT_MAX_ITEMS,
    GENERATION_CALLBACK_ASYNC_INFLIGHT_TTL_SECONDS,
    GENERATION_CALLBACK_FINALIZE_MAX_CONCURRENCY,
    GENERATION_CALLBACK_FINALIZE_SEMAPHORE,
    GENERATION_CALLBACK_FILE_DIR,
    GENERATION_CALLBACK_JOB_FILE_SCAN_MAX_FILES,
    GENERATION_CALLBACK_JOB_MATCH_MAX_ITEMS,
    GENERATION_CALLBACK_LOCK,
    GENERATION_CALLBACK_MAX_BYTES,
    GENERATION_CALLBACK_MAX_ITEMS,
    GENERATION_CALLBACK_NO_MATCH_LOG_CACHE,
    GENERATION_CALLBACK_NO_MATCH_LOG_LOCK,
    GENERATION_CALLBACK_NO_MATCH_LOG_MAX_ITEMS,
    GENERATION_CALLBACK_NO_MATCH_LOG_THROTTLE_SECONDS,
    GENERATION_CALLBACK_STORE,
    GENERATION_CALLBACK_TTL_SECONDS,
    IMAGE_ACTIVE_SCOPE_STORE,
    IMAGE_CALLBACK_PERSIST_INFLIGHT,
    IMAGE_CALLBACK_PERSIST_INFLIGHT_LOCK,
    IMAGE_CALLBACK_PERSIST_INFLIGHT_MAX_ITEMS,
    IMAGE_CALLBACK_PERSIST_INFLIGHT_TTL_SECONDS,
    IMAGE_JOB_FILE_DIR,
    IMAGE_JOB_LOCK,
    IMAGE_JOB_MAX_ITEMS,
    IMAGE_JOB_MAX_RUNNING_SECONDS,
    IMAGE_JOB_STORE,
    IMAGE_JOB_TASKS,
    IMAGE_JOB_TTL_SECONDS,
    IMAGE_SUBMIT_IDEMPOTENCY_STORE,
    IMAGE_SUBMIT_IDEMPOTENCY_TTL_SECONDS,
    SCENE_AI_SHOTS_BATCH_THREADS,
    SCENE_AI_SHOTS_BATCH_THREADS_LOCK,
    SHOT_MEDIA_BATCH_CANCEL_EVENTS,
    SHOT_MEDIA_BATCH_CANCEL_LOCK,
    SHOT_MEDIA_BATCH_THREADS,
    SHOT_MEDIA_BATCH_THREADS_LOCK,
    VIDEO_ACTIVE_SCOPE_STORE,
    VIDEO_CALLBACK_PERSIST_INFLIGHT,
    VIDEO_CALLBACK_PERSIST_INFLIGHT_LOCK,
    VIDEO_CALLBACK_PERSIST_INFLIGHT_MAX_ITEMS,
    VIDEO_CALLBACK_PERSIST_INFLIGHT_TTL_SECONDS,
    VIDEO_JOB_FILE_DIR,
    VIDEO_JOB_LOCK,
    VIDEO_JOB_MAX_ITEMS,
    VIDEO_JOB_MAX_RUNNING_SECONDS,
    VIDEO_JOB_STORE,
    VIDEO_JOB_TASKS,
    VIDEO_JOB_TTL_SECONDS,
    VIDEO_SUBMIT_IDEMPOTENCY_STORE,
    VIDEO_SUBMIT_IDEMPOTENCY_TTL_SECONDS,
    WEBHOOK_REPLAY_LOCK,
    WEBHOOK_REPLAY_MAX_ITEMS,
    WEBHOOK_REPLAY_STORE,
    _JOB_TIMEOUT_CHECK_STATUSES,
    _build_generation_job_pool_cache_key,
    _build_image_idempotency_store_key,
    _build_submit_idempotency_token,
    _build_generation_task_scope,
    _build_video_idempotency_store_key,
    _clear_episode_worker,
    _clear_generation_job_pool_cache,
    _clear_shot_media_batch_cancel_event,
    _coerce_naive_utc_datetime,
    _compact_job_result,
    _drop_image_job_locked,
    _drop_video_job_locked,
    _extract_job_result_url,
    _get_shot_media_batch_cancel_event,
    _image_job_file_path,
    _is_episode_worker_alive,
    _is_generation_job_stale,
    _is_terminal_generation_job_status,
    _job_sort_key,
    _parse_iso_datetime,
    _prune_generation_job_pool_cache_locked,
    _prune_image_jobs_locked,
    _prune_image_submit_idempotency_locked,
    _prune_video_jobs_locked,
    _prune_video_submit_idempotency_locked,
    _read_generation_job_pool_cache,
    _read_image_job_file,
    _read_video_job_file,
    _register_episode_worker,
    _reset_shot_media_batch_cancel_requested,
    _seconds_since_iso_timestamp,
    _set_image_job,
    _set_shot_media_batch_cancel_requested,
    _set_video_job,
    _snapshot_image_job_stats,
    _unlink_job_snapshot_file,
    _video_job_file_path,
    _write_generation_job_pool_cache,
    _write_image_job_file,
    _write_video_job_file,
)

from app.services.db_session_utils import (  # noqa: E402,F401
    _release_db_connection,
    _snapshot_user_principal,
)
from app.services.script_analysis_llm_config import (  # noqa: E402,F401
    _resolve_script_analysis_dropdown_llm_config,
    _resolve_script_analysis_dropdown_order,
    _resolve_story_generator_script_analysis_llm_config,
    _script_analysis_function_api_name,
    _select_script_analysis_api_order,
)
from app.services.analyze_scene_dedup import (  # noqa: E402,F401
    _build_analyze_scene_dedup_key,
    _collect_analyze_scene_dedup_stats,
    _delete_analyze_scene_dedup_row,
    _ensure_analyze_scene_dedup_table_ready,
    _get_analyze_scene_dedup_row,
    _insert_analyze_scene_dedup_row_if_absent,
    _normalize_analyze_scene_dedup_payload,
    _prune_analyze_scene_dedup_rows,
    _upsert_analyze_scene_dedup_row,
)

# queue worker -> generation_runtime.queue_worker
from app.services.generation_runtime.queue_worker import (  # noqa: E402,F401
    _callback_compensation_thread_main,
    _cancel_generation_task_ref,
    _generation_task_is_active,
    _generation_task_status,
    _is_pure_callback_mode_enabled,
    _process_generation_queue_task,
    _queue_cfg_bool,
    _queue_cfg_int,
    _queue_runtime_config,
    _run_callback_compensation_once,
    _start_callback_compensation_worker,
    _submit_generation_background_task,
    start_generation_queue_worker,
)
globals().update({k: v for k, v in vars(__import__("app.services.generation_runtime.queue_worker", fromlist=["*"])).items() if not k.startswith("__")})

# callbacks -> generation_runtime.callbacks
from app.services.generation_runtime import callbacks as _gen_callbacks  # noqa: E402
globals().update({k: v for k, v in vars(_gen_callbacks).items() if not k.startswith("__")})


from app.services.provider_alias import (  # noqa: E402
    _attach_provider_alias_deep,
    _attach_provider_alias_to_dict,
    _build_provider_alias_lookup,
    _resolve_provider_alias,
)

# drop/prune/stats -> generation_runtime.job_store (re-exported below)

from app.services.endpoint_misc import (  # noqa: E402
    _build_scene_analysis_blocking_failure_detail,
    _can_use_system_settings,
    _log_batch_sys_event,
    _vendor_failed_message,
)

# system_logs routes moved to app.api.routers.admin_ops


# script_analysis_diagnosis routes moved to app.api.routers.script_analysis_diagnosis


# settings/effective -> routers.settings_effective


from app.services.prompt_resolve import (  # noqa: E402
    _PROMPT_SKILL_ALIAS,
    _build_prompt_resolution_debug,
    _resolve_prompt_file_path,
    _resolve_prompt_text,
)

# prompts/analyze_scene moved to app.api.routers.prompts_analyze


from app.services.project_cost_estimation import (  # noqa: E402
    _compute_project_cost_estimation_snapshot,
    _recompute_and_persist_project_cost_estimation,
)

# projects/episodes/scenes/shots workspace moved to app.api.routers.projects_workspace
