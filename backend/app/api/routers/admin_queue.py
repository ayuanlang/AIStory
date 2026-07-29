# -*- coding: utf-8 -*-
"""Admin generation-queue routes."""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.queue_config import DEFAULT_QUEUE_CONFIG
from app.db.session import get_db
from app.models.all_models import User
from app.services.analyze_scene_dedup import _collect_analyze_scene_dedup_stats
from app.services.endpoint_misc import _safe_int
from app.services.generation_runtime.callbacks import (
    _extract_job_provider_callback_ticket,
    _normalize_generation_status,
    _prune_generation_callback_locked,
)
from app.services.generation_runtime.job_store import (
    GENERATION_CALLBACK_ASYNC_INFLIGHT,
    GENERATION_CALLBACK_ASYNC_INFLIGHT_LOCK,
    GENERATION_CALLBACK_FINALIZE_MAX_CONCURRENCY,
    GENERATION_CALLBACK_LOCK,
    GENERATION_CALLBACK_STORE,
    IMAGE_CALLBACK_PERSIST_INFLIGHT,
    IMAGE_CALLBACK_PERSIST_INFLIGHT_LOCK,
    IMAGE_JOB_LOCK,
    IMAGE_JOB_STORE,
    VIDEO_CALLBACK_PERSIST_INFLIGHT,
    VIDEO_CALLBACK_PERSIST_INFLIGHT_LOCK,
    VIDEO_JOB_LOCK,
    VIDEO_JOB_STORE,
    _job_is_callback_waiting,
    _is_terminal_generation_job_status,
    _prune_image_jobs_locked,
    _prune_video_jobs_locked,
    _read_image_job_file,
    _read_video_job_file,
    _set_image_job,
    _set_video_job,
)
from app.services.generation_runtime.queue_worker import (
    _CALLBACK_COMPENSATION_STARTED,
    _is_pure_callback_mode_enabled,
    _queue_cfg_bool,
    _queue_cfg_int,
)
from app.services.generation_task_queue import (
    cancel_generation_task,
    cancel_generation_tasks,
    get_generation_queue_runtime_stats,
    list_generation_tasks,
)

logger = logging.getLogger("api_logger")
router = APIRouter(tags=["admin-queue"])


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
                runtime_status = _normalize_generation_status(runtime_job.get("status"))
                queue_status = str(item.get("status") or "").strip().lower()
                # Heal display/queue desync: runtime already terminal but queue still waiting.
                if runtime_status == "succeeded" and queue_status in {
                    "waiting_callback",
                    "callback_processing",
                    "running",
                    "submit",
                    "pending",
                    "processing",
                }:
                    item["status"] = "completed"
                    try:
                        from app.services.generation_task_queue import mark_generation_task_status_external

                        mark_generation_task_status_external(job_id, status="completed", error=None)
                        if "callback_pending" in str(runtime_job.get("upstream_submit_state") or "").lower():
                            if kind == "video":
                                _set_video_job(
                                    job_id,
                                    upstream_submit_state="completed",
                                    callback_submit_retries=0,
                                    callback_retry_at=None,
                                )
                            else:
                                _set_image_job(
                                    job_id,
                                    upstream_submit_state="completed",
                                    callback_submit_retries=0,
                                    callback_retry_at=None,
                                )
                            runtime_job = dict(runtime_job)
                            runtime_job["upstream_submit_state"] = "completed"
                            item["callback_diag"] = _build_callback_diag(runtime_job)
                    except Exception:
                        logger.exception(
                            "[AdminQueue] failed to heal terminal job queue status | job_id=%s kind=%s",
                            job_id,
                            kind,
                        )
                elif runtime_status == "failed" and queue_status in {
                    "waiting_callback",
                    "callback_processing",
                    "running",
                    "submit",
                }:
                    item["status"] = "failed"
                elif runtime_status == "canceled" and queue_status in {
                    "waiting_callback",
                    "callback_processing",
                    "running",
                    "submit",
                }:
                    item["status"] = "canceled"
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
        retry_count = _safe_int(job.get("callback_submit_retries"), 0)
        has_retry_at = bool(str(job.get("callback_retry_at") or "").strip())
        is_timeout_failed = bool(
            status == "failed"
            and "timed out" in str(job.get("error") or "").strip().lower()
        )

        is_waiting_callback = _job_is_callback_waiting(job)
        # Do not count terminal jobs with stale callback_pending as waiting.
        if _is_terminal_generation_job_status(status):
            is_waiting_callback = False

        if is_waiting_callback and callback_ticket:
            callback_pending_count += 1
        if callback_ticket and is_waiting_callback:
            callback_waiting_count += 1
        if retry_count > 0 or has_retry_at:
            if not _is_terminal_generation_job_status(status):
                callback_retrying_count += 1
        if is_timeout_failed and callback_ticket:
            callback_timeout_failed_count += 1
        if callback_ticket and (
            status in {"queued", "submit", "running", "waiting_callback", "callback_processing"}
            or (is_timeout_failed and "callback" in str(job.get("error") or "").lower())
        ):
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
            "timeout_poll_max_attempts": _queue_cfg_int("timeout_poll_max_attempts", 3, minimum=1, maximum=10),
            "timeout_poll_interval_seconds": _queue_cfg_int("timeout_poll_interval_seconds", 30, minimum=5, maximum=300),
        },
    }


