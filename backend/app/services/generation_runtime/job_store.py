# -*- coding: utf-8 -*-
"""In-process image/video job stores, file snapshots, prune, and set_*_job."""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import logging
import os
import re
import threading
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.queue_config import DEFAULT_QUEUE_CONFIG, load_queue_config
from app.core.time_utils import BEIJING_TZ, now_bj_iso
from app.db.session import DB_POOL_CAPACITY_EFFECTIVE

logger = logging.getLogger("api_logger")

__all__ = [
    "ASSET_REGISTRATION_LOCK",
    "EPISODE_SCENE_JOB_THREADS",
    "EPISODE_SCENE_JOB_THREADS_LOCK",
    "GENERATION_CALLBACK_ASYNC_INFLIGHT",
    "GENERATION_CALLBACK_ASYNC_INFLIGHT_LOCK",
    "GENERATION_CALLBACK_ASYNC_INFLIGHT_MAX_ITEMS",
    "GENERATION_CALLBACK_ASYNC_INFLIGHT_TTL_SECONDS",
    "GENERATION_CALLBACK_FILE_DIR",
    "GENERATION_CALLBACK_FINALIZE_MAX_CONCURRENCY",
    "GENERATION_CALLBACK_FINALIZE_SEMAPHORE",
    "GENERATION_CALLBACK_JOB_FILE_SCAN_MAX_FILES",
    "GENERATION_CALLBACK_JOB_MATCH_MAX_ITEMS",
    "GENERATION_CALLBACK_LOCK",
    "GENERATION_CALLBACK_MAX_BYTES",
    "GENERATION_CALLBACK_MAX_ITEMS",
    "GENERATION_CALLBACK_NO_MATCH_LOG_CACHE",
    "GENERATION_CALLBACK_NO_MATCH_LOG_LOCK",
    "GENERATION_CALLBACK_NO_MATCH_LOG_MAX_ITEMS",
    "GENERATION_CALLBACK_NO_MATCH_LOG_THROTTLE_SECONDS",
    "GENERATION_CALLBACK_STORE",
    "GENERATION_CALLBACK_TTL_SECONDS",
    "IMAGE_ACTIVE_SCOPE_STORE",
    "IMAGE_CALLBACK_PERSIST_INFLIGHT",
    "IMAGE_CALLBACK_PERSIST_INFLIGHT_LOCK",
    "IMAGE_CALLBACK_PERSIST_INFLIGHT_MAX_ITEMS",
    "IMAGE_CALLBACK_PERSIST_INFLIGHT_TTL_SECONDS",
    "IMAGE_JOB_FILE_DIR",
    "IMAGE_JOB_LOCK",
    "IMAGE_JOB_MAX_ITEMS",
    "IMAGE_JOB_MAX_RUNNING_SECONDS",
    "IMAGE_JOB_STORE",
    "IMAGE_JOB_TASKS",
    "IMAGE_JOB_TTL_SECONDS",
    "IMAGE_SUBMIT_IDEMPOTENCY_STORE",
    "IMAGE_SUBMIT_IDEMPOTENCY_TTL_SECONDS",
    "SCENE_AI_SHOTS_BATCH_THREADS",
    "SCENE_AI_SHOTS_BATCH_THREADS_LOCK",
    "SHOT_MEDIA_BATCH_CANCEL_EVENTS",
    "SHOT_MEDIA_BATCH_CANCEL_LOCK",
    "SHOT_MEDIA_BATCH_THREADS",
    "SHOT_MEDIA_BATCH_THREADS_LOCK",
    "VIDEO_ACTIVE_SCOPE_STORE",
    "VIDEO_CALLBACK_PERSIST_INFLIGHT",
    "VIDEO_CALLBACK_PERSIST_INFLIGHT_LOCK",
    "VIDEO_CALLBACK_PERSIST_INFLIGHT_MAX_ITEMS",
    "VIDEO_CALLBACK_PERSIST_INFLIGHT_TTL_SECONDS",
    "VIDEO_JOB_FILE_DIR",
    "VIDEO_JOB_LOCK",
    "VIDEO_JOB_MAX_ITEMS",
    "VIDEO_JOB_MAX_RUNNING_SECONDS",
    "VIDEO_JOB_STORE",
    "VIDEO_JOB_TASKS",
    "VIDEO_JOB_TTL_SECONDS",
    "VIDEO_SUBMIT_IDEMPOTENCY_STORE",
    "VIDEO_SUBMIT_IDEMPOTENCY_TTL_SECONDS",
    "WEBHOOK_REPLAY_LOCK",
    "WEBHOOK_REPLAY_MAX_ITEMS",
    "WEBHOOK_REPLAY_STORE",
    "_CALLBACK_FINALIZE_CAP",
    "_CALLBACK_WAIT_STATUSES",
    "_DEFAULT_CALLBACK_THREADS",
    "_GENERATION_JOB_POOL_CACHE",
    "_GENERATION_JOB_POOL_CACHE_LOCK",
    "_GENERATION_JOB_POOL_CACHE_MAX_ITEMS",
    "_GENERATION_JOB_POOL_CACHE_TTL_SECONDS",
    "_GENERATION_JOB_STALE_DELETE_SECONDS",
    "_JOB_RESULT_METADATA_KEYS",
    "_JOB_RESULT_TOP_LEVEL_KEYS",
    "_JOB_TIMEOUT_CHECK_STATUSES",
    "_PER_PROCESS_POOL_BUDGET",
    "_POOL_CAPACITY",
    "_TERMINAL_GENERATION_JOB_STATUSES",
    "_UNSIGNED_WEBHOOK_WARNING_EMITTED",
    "_WEB_CONCURRENCY",
    "_build_generation_job_pool_cache_key",
    "_build_generation_task_scope",
    "_build_image_idempotency_store_key",
    "_build_submit_idempotency_token",
    "_build_video_idempotency_store_key",
    "_clear_episode_worker",
    "_clear_generation_job_pool_cache",
    "_clear_shot_media_batch_cancel_event",
    "_coerce_naive_utc_datetime",
    "_compact_job_result",
    "_drop_image_job_locked",
    "_drop_video_job_locked",
    "_extract_job_result_url",
    "_get_shot_media_batch_cancel_event",
    "_image_job_file_path",
    "_is_episode_worker_alive",
    "_is_generation_job_stale",
    "_is_terminal_generation_job_status",
    "_job_callback_wait_elapsed_seconds",
    "_job_has_success_result",
    "_job_is_callback_waiting",
    "_job_sort_key",
    "_parse_iso_datetime",
    "_prune_generation_job_pool_cache_locked",
    "_prune_image_jobs_locked",
    "_prune_image_submit_idempotency_locked",
    "_prune_video_jobs_locked",
    "_prune_video_submit_idempotency_locked",
    "_read_generation_job_pool_cache",
    "_read_image_job_file",
    "_read_video_job_file",
    "_register_episode_worker",
    "_reset_shot_media_batch_cancel_requested",
    "_seconds_since_iso_timestamp",
    "_set_image_job",
    "_set_shot_media_batch_cancel_requested",
    "_set_video_job",
    "_snapshot_image_job_stats",
    "_unlink_job_snapshot_file",
    "_video_job_file_path",
    "_write_generation_job_pool_cache",
    "_write_image_job_file",
    "_write_video_job_file"
]


_q_conf = load_queue_config()

# --- stores / constants ---
IMAGE_JOB_STORE: Dict[str, Dict[str, Any]] = {}
IMAGE_JOB_LOCK = threading.Lock()
# Tighter defaults for 4GB-class hosts; override via env if needed.
IMAGE_JOB_TTL_SECONDS = max(120, int(os.getenv("IMAGE_JOB_TTL_SECONDS", "600")))
IMAGE_JOB_MAX_ITEMS = max(20, int(os.getenv("IMAGE_JOB_MAX_ITEMS", "80")))
IMAGE_SUBMIT_IDEMPOTENCY_STORE: Dict[str, Dict[str, Any]] = {}
IMAGE_ACTIVE_SCOPE_STORE: Dict[str, str] = {}
IMAGE_SUBMIT_IDEMPOTENCY_TTL_SECONDS = max(30, int(os.getenv("IMAGE_SUBMIT_IDEMPOTENCY_TTL_SECONDS", "120")))
IMAGE_JOB_FILE_DIR = os.path.join(settings.UPLOAD_DIR, "_image_jobs")
IMAGE_JOB_TASKS: Dict[str, Any] = {}

VIDEO_JOB_STORE: Dict[str, Dict[str, Any]] = {}
VIDEO_JOB_LOCK = threading.Lock()
VIDEO_JOB_TTL_SECONDS = max(120, int(os.getenv("VIDEO_JOB_TTL_SECONDS", "600")))
VIDEO_JOB_MAX_ITEMS = max(20, int(os.getenv("VIDEO_JOB_MAX_ITEMS", "80")))
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
GENERATION_CALLBACK_TTL_SECONDS = max(120, int(os.getenv("GENERATION_CALLBACK_TTL_SECONDS", "1800")))
GENERATION_CALLBACK_MAX_ITEMS = max(50, int(os.getenv("GENERATION_CALLBACK_MAX_ITEMS", "400")))
GENERATION_CALLBACK_FILE_DIR = os.path.join(settings.UPLOAD_DIR, "_generation_callbacks")
GENERATION_CALLBACK_MAX_BYTES = max(4096, int(os.getenv("GENERATION_CALLBACK_MAX_BYTES", "32768")))
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
_GENERATION_JOB_STALE_DELETE_SECONDS = max(300, int(os.getenv("GENERATION_JOB_STALE_DELETE_SECONDS", "7200") or 7200))
# Stuck non-terminal jobs (orphaned waiting_callback / running) must not live forever in RAM.
_GENERATION_JOB_STALE_NON_TERMINAL_SECONDS = max(
    600,
    int(os.getenv("GENERATION_JOB_STALE_NON_TERMINAL_SECONDS", "3600") or 3600),
)
_JOB_PROMPT_KEEP_CHARS = max(64, int(os.getenv("GENERATION_JOB_PROMPT_KEEP_CHARS", "256") or 256))
_GENERATION_JOB_POOL_CACHE_LOCK = threading.Lock()
_GENERATION_JOB_POOL_CACHE: Dict[str, Dict[str, Any]] = {}

ASSET_REGISTRATION_LOCK = threading.Lock()

_HEAVY_JOB_TEXT_KEYS = (
    "prompt",
    "negative_prompt",
    "raw_prompt",
    "optimized_prompt",
    "system_prompt",
)
_HEAVY_JOB_OBJECT_KEYS = (
    "request_payload",
    "req_payload",
    "combined_payload",
    "provider_raw_response",
    "callback_payload",
    "raw_callback_payload",
)




# --- pool cache + episode workers ---
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




# --- shot-media batch cancel ---
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




# --- image job file I/O ---
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




# --- video job file I/O + submit idempotency ---
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




# --- datetime / compact result ---
def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        normalized = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
        dt = datetime.fromisoformat(normalized)
        # Job/idempotency stores mix now_bj_iso() (aware) with legacy naive writers.
        # Normalize to naive UTC so age math never mixes aware/naive.
        if dt.tzinfo is not None:
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        # Naive timestamps in this codebase are Beijing wall clock. Treating them as
        # UTC against datetime.utcnow() inflates age by ~28800s and false-timeouts jobs.
        return dt.replace(tzinfo=BEIJING_TZ).astimezone(timezone.utc).replace(tzinfo=None)
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
        # Subtract naive-UTC datetimes directly. Never use naive.timestamp():
        # Python treats naive as *local* time, which shifts CST by +8h (~28800s).
        return max(0.0, (_coerce_naive_utc_datetime() - parsed).total_seconds())
    except Exception:
        return None


def _job_callback_wait_elapsed_seconds(job: Dict[str, Any]) -> Optional[float]:
    """Elapsed for callback-loss compensation clocks.

    After a compensation requeue, ``started_at`` is cleared — prefer
    ``callback_retry_at`` so we do not count the entire job lifetime from
    original ``created_at`` and immediately exhaust on the next scan.

    Never fall back to ``created_at`` for exhaust decisions: queue wait + prior
    attempts make that clock far larger than the current callback wait, which
    produced false ``callback wait exhausted after ~28800s`` failures.
    """
    for field in ("callback_retry_at", "started_at"):
        elapsed = _seconds_since_iso_timestamp(job.get(field))
        if elapsed is not None:
            return elapsed
    return None


def _job_has_success_result(job: Optional[Dict[str, Any]]) -> bool:
    """True when the job already carries a usable result URL (do not exhaust/timeout it)."""
    payload = job if isinstance(job, dict) else {}
    status = str(payload.get("status") or "").strip().lower()
    if status in {"succeeded", "completed", "done", "success"}:
        return True
    return bool(_extract_job_result_url(payload.get("result")))


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

    if not compact and "url" not in result:
        return result

    return compact or {"url": result.get("url")}


def _strip_heavy_job_text(value: Any) -> Any:
    text = str(value or "")
    if len(text) <= _JOB_PROMPT_KEEP_CHARS:
        return text
    return f"{text[:_JOB_PROMPT_KEEP_CHARS]}...[stripped:{len(text)}chars]"


def _slim_terminal_job_fields(job: Dict[str, Any]) -> None:
    """Drop large prompt/payload fields once a job is terminal so idle RSS can shrink."""
    if not isinstance(job, dict):
        return
    if not _is_terminal_generation_job_status(job.get("status")):
        return
    for key in _HEAVY_JOB_TEXT_KEYS:
        if key in job and job.get(key) not in (None, ""):
            job[key] = _strip_heavy_job_text(job.get(key))
    for key in _HEAVY_JOB_OBJECT_KEYS:
        if key in job:
            job.pop(key, None)


def _job_age_seconds(job: Dict[str, Any], now: datetime) -> float:
    stamp = (
        _parse_iso_datetime(job.get("finished_at"))
        or _parse_iso_datetime(job.get("updated_at"))
        or _parse_iso_datetime(job.get("started_at"))
        or _parse_iso_datetime(job.get("created_at"))
        or _coerce_naive_utc_datetime(_job_sort_key(job))
    )
    try:
        return max(0.0, (now - stamp).total_seconds())
    except Exception:
        return 0.0


def _delete_generation_job_state_best_effort(*, kind: str, job_id: str) -> None:
    try:
        from app.services.generation_task_queue import delete_generation_job_state

        delete_generation_job_state(kind=kind, job_id=job_id)
    except Exception as exc:
        logger.debug("delete_generation_job_state skipped | kind=%s job_id=%s err=%s", kind, job_id, exc)


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

    event_data = result.get("eventData")
    if isinstance(event_data, dict):
        nested_url = _extract_job_result_url(event_data)
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




# --- drop / prune / stats ---
_TERMINAL_GENERATION_JOB_STATUSES = frozenset(
    {"succeeded", "completed", "done", "success", "failed", "error", "canceled", "cancelled"}
)
_CALLBACK_WAIT_STATUSES = frozenset({"waiting_callback", "callback_processing"})


def _is_terminal_generation_job_status(status: Any) -> bool:
    return str(status or "").strip().lower() in _TERMINAL_GENERATION_JOB_STATUSES


def _job_is_callback_waiting(job: Optional[Dict[str, Any]]) -> bool:
    """True only while a non-terminal job is still waiting on provider callback.

    Stale ``upstream_submit_state=callback_pending`` on a succeeded/failed job must
    NOT keep the job classified as waiting — that desyncs queue UI and can make
    compensation re-mark completed tasks as ``waiting_callback``.
    """
    payload = job if isinstance(job, dict) else {}
    status = str(payload.get("status") or "").strip().lower()
    if _is_terminal_generation_job_status(status):
        return False
    if status in _CALLBACK_WAIT_STATUSES:
        return True
    upstream_state = str(payload.get("upstream_submit_state") or "").strip().lower()
    if "callback_pending" not in upstream_state:
        return False
    # Defensive: submit race may briefly keep running/submit with callback_pending.
    return status in {"running", "submit", "pending", "processing"}


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
    _delete_generation_job_state_best_effort(kind="image", job_id=stable_job_id)


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
    _delete_generation_job_state_best_effort(kind="video", job_id=stable_job_id)


def _prune_image_jobs_locked() -> None:
    now = _coerce_naive_utc_datetime()
    expired_ids = []
    non_terminal_limit = max(
        float(IMAGE_JOB_MAX_RUNNING_SECONDS) * 2.0,
        float(_GENERATION_JOB_STALE_NON_TERMINAL_SECONDS),
    )

    for job_id, job in IMAGE_JOB_STORE.items():
        age_seconds = _job_age_seconds(job or {}, now)
        if _is_terminal_generation_job_status((job or {}).get("status")):
            if age_seconds > IMAGE_JOB_TTL_SECONDS:
                expired_ids.append(job_id)
            else:
                _slim_terminal_job_fields(job)
            continue
        if age_seconds > non_terminal_limit:
            expired_ids.append(job_id)

    for job_id in expired_ids:
        _drop_image_job_locked(job_id)

    if len(IMAGE_JOB_STORE) > IMAGE_JOB_MAX_ITEMS:
        # Overflow must never evict fresh non-terminal jobs; clients may still be polling them.
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
    non_terminal_limit = max(
        float(VIDEO_JOB_MAX_RUNNING_SECONDS) * 2.0,
        float(_GENERATION_JOB_STALE_NON_TERMINAL_SECONDS),
    )

    for job_id, job in VIDEO_JOB_STORE.items():
        age_seconds = _job_age_seconds(job or {}, now)
        if _is_terminal_generation_job_status((job or {}).get("status")):
            if age_seconds > VIDEO_JOB_TTL_SECONDS:
                expired_ids.append(job_id)
            else:
                _slim_terminal_job_fields(job)
            continue
        if age_seconds > non_terminal_limit:
            expired_ids.append(job_id)

    for job_id in expired_ids:
        _drop_video_job_locked(job_id)

    if len(VIDEO_JOB_STORE) > VIDEO_JOB_MAX_ITEMS:
        # Overflow must never evict fresh non-terminal jobs; clients may still be polling them.
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




# --- mutators (moved from generate router) ---
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

        status = str(current.get("status") or "").strip().lower()
        # Success paths sometimes set status=succeeded without clearing a prior false
        # "callback wait exhausted" marker; heal here so UI/diagnostics stay coherent.
        if status in {"succeeded", "completed", "done", "success"}:
            upstream = str(current.get("upstream_submit_state") or "").strip().lower()
            if (
                "callback_wait" in upstream
                or "callback_pending" in upstream
                or "callback_retry" in upstream
                or not upstream
            ):
                current["upstream_submit_state"] = "completed"
            if "error" not in fields or fields.get("error") in (None, ""):
                err_text = str(current.get("error") or "").strip().lower()
                if (not err_text) or ("callback wait" in err_text) or ("timed out" in err_text):
                    current["error"] = None
            if "callback_submit_retries" not in fields:
                current["callback_submit_retries"] = 0
            if "callback_retry_at" not in fields:
                current["callback_retry_at"] = None

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
            _slim_terminal_job_fields(current)

        IMAGE_JOB_STORE[job_id] = current
        _write_image_job_file(job_id, current)

    _clear_generation_job_pool_cache()


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

        status = str(current.get("status") or "").strip().lower()
        if status in {"succeeded", "completed", "done", "success"}:
            upstream = str(current.get("upstream_submit_state") or "").strip().lower()
            if (
                "callback_wait" in upstream
                or "callback_pending" in upstream
                or "callback_retry" in upstream
                or not upstream
            ):
                current["upstream_submit_state"] = "completed"
            if "error" not in fields or fields.get("error") in (None, ""):
                err_text = str(current.get("error") or "").strip().lower()
                if (not err_text) or ("callback wait" in err_text) or ("timed out" in err_text):
                    current["error"] = None
            if "callback_submit_retries" not in fields:
                current["callback_submit_retries"] = 0
            if "callback_retry_at" not in fields:
                current["callback_retry_at"] = None

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
            _slim_terminal_job_fields(current)

        VIDEO_JOB_STORE[job_id] = current
        _write_video_job_file(job_id, current)

    _clear_generation_job_pool_cache()

