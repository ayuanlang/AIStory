# -*- coding: utf-8 -*-
"""Generation task queue worker + callback compensation."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.core.queue_config import DEFAULT_QUEUE_CONFIG, load_queue_config, save_queue_config
from app.core.time_utils import now_bj_iso
from app.db.session import SessionLocal
from app.services.generation_runtime.job_store import (
    IMAGE_JOB_LOCK,
    IMAGE_JOB_STORE,
    IMAGE_JOB_TASKS,
    VIDEO_JOB_LOCK,
    VIDEO_JOB_STORE,
    VIDEO_JOB_TASKS,
    _set_image_job,
    _set_video_job,
    _is_terminal_generation_job_status,
    _job_has_success_result,
    _job_is_callback_waiting,
    _parse_iso_datetime,
    _coerce_naive_utc_datetime,
    _seconds_since_iso_timestamp,
    _job_callback_wait_elapsed_seconds,
    _JOB_TIMEOUT_CHECK_STATUSES,
    IMAGE_JOB_MAX_RUNNING_SECONDS,
    VIDEO_JOB_MAX_RUNNING_SECONDS,
    _prune_image_jobs_locked,
    _prune_video_jobs_locked,
)
from app.services.generation_task_queue import (
    mark_generation_task_status_external,
    patch_generation_task_payload,
    start_generation_task_worker,
)
from app.services.media_service import media_service
from app.services.video_service import create_montage
from app.services.generation_runtime.job_timeout import _maybe_finalize_stuck_job

from app.services.task_manager import (
    get_status as _get_task_status,
    cancel as _cancel_task,
    set_task_status as _set_task_status,
    submit as _submit_task,
    create_task_record as _create_task_record,
)

logger = logging.getLogger("api_logger")
from app.services.generation_runtime.queue_config_runtime import (  # noqa: F401
    _is_pure_callback_mode_enabled,
    _queue_cfg_bool,
    _queue_cfg_int,
    _queue_runtime_config,
)


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
        from app.services.generation_runtime.image_generation_runner import _run_generate_image_job
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
        from app.api.routers.generation.video_jobs import _run_generate_video_job
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

    from app.services.endpoint_misc import _safe_int
    from app.services.generation_runtime.callbacks import (
        _extract_job_provider_callback_ticket,
        _get_generation_callback_payload,
        _maybe_finalize_image_job_from_grsai_callback,
        _maybe_finalize_video_job_from_provider_callback,
        _normalize_generation_status,
    )
    # _maybe_finalize_stuck_job imported from generation_runtime.job_timeout

    pure_callback_mode = _is_pure_callback_mode_enabled()
    safe_batch = _queue_cfg_int("callback_compensation_scan_batch_size", 10, minimum=1, maximum=200)
    image_share_percent = _queue_cfg_int("callback_compensation_image_share_percent", 50, minimum=0, maximum=100)
    retry_enabled = _queue_cfg_bool("callback_loss_retry_enabled", True)
    retry_after_seconds = _queue_cfg_int("callback_loss_retry_after_seconds", 1200, minimum=60, maximum=86400)
    timeout_retry_after_seconds = min(retry_after_seconds, 120)
    max_submit_retries = _queue_cfg_int("callback_loss_max_submit_retries", 1, minimum=0, maximum=5)

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
            upstream_state = str(job.get("upstream_submit_state") or "").strip().lower()
            is_timeout_failed = (
                status == "failed"
                and "timed out" in str(job.get("error") or "").strip().lower()
            )
            error_text = str(job.get("error") or "").strip().lower()
            needs_false_fail_recover = bool(
                status == "failed"
                and ("callback wait exhausted" in error_text or "callback wait timed out" in error_text)
            )
            # Always include terminal jobs that still look desynced so we can heal
            # queue status / stale callback_pending markers.
            needs_terminal_reconcile = bool(
                _is_terminal_generation_job_status(status)
                and (
                    "callback_pending" in upstream_state
                    or not str(job.get("upstream_submit_state") or "").strip()
                    or needs_false_fail_recover
                )
            )
            is_callback_wait = _job_is_callback_waiting(job)
            status_for_timeout = status in {
                "running",
                "submit",
                "waiting_callback",
                "callback_processing",
            }
            # Only compensate true callback-wait jobs. Plain queued/submit/running
            # jobs also carry tickets for tracing; treating them as waiters races
            # the poll worker and exhausts after one requeue using created_at age.
            # Still include non-wait running/submit for timeout sweep + terminal heal.
            if (
                not is_callback_wait
                and not is_timeout_failed
                and not needs_terminal_reconcile
                and not status_for_timeout
                and not needs_false_fail_recover
            ):
                continue
            if is_timeout_failed and "callback" not in str(job.get("error") or "").strip().lower():
                # Generic poll timeouts are not callback-loss; leave them alone.
                if "callback" not in upstream_state:
                    continue
            callback_ticket = _extract_job_provider_callback_ticket(job)
            # Timeout/heal do not require a ticket; compensation requeue does (checked later).
            if (
                not callback_ticket
                and not needs_terminal_reconcile
                and not is_callback_wait
                and not status_for_timeout
                and not needs_false_fail_recover
            ):
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

        # Finalize callback BEFORE timeout/exhaust so successful provider results
        # are not overwritten by false "callback wait exhausted" failures.
        if callback_ticket:
            callback_payload = _get_generation_callback_payload(callback_ticket)
            if callback_payload:
                if kind == "image":
                    job = _maybe_finalize_image_job_from_grsai_callback(job_id, dict(job))
                else:
                    job = _maybe_finalize_video_job_from_provider_callback(job_id, dict(job))

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

        status_after = _normalize_generation_status(job.get("status"))
        if _is_terminal_generation_job_status(status_after):
            # Timeout/heal path already synced queue; never requeue terminal jobs.
            continue

        if _job_has_success_result(job):
            if kind == "image":
                _set_image_job(
                    job_id,
                    status="succeeded",
                    error=None,
                    upstream_submit_state="completed",
                    callback_submit_retries=0,
                    callback_retry_at=None,
                    finished_at=job.get("finished_at") or now_bj_iso(),
                )
            else:
                _set_video_job(
                    job_id,
                    status="succeeded",
                    error=None,
                    upstream_submit_state="completed",
                    callback_submit_retries=0,
                    callback_retry_at=None,
                    finished_at=job.get("finished_at") or now_bj_iso(),
                )
            mark_generation_task_status_external(job_id, status="completed", error=None)
            continue

        # Local / poll mode: still timeout & heal above, but providers cannot reach
        # localhost. Never requeue/exhaust as "callback wait".
        if not pure_callback_mode:
            continue

        if not callback_ticket:
            continue

        if _job_is_callback_waiting(job):
            mark_generation_task_status_external(job_id, status="waiting_callback", error=None)

        if not retry_enabled:
            continue

        status = _normalize_generation_status(job.get("status"))
        is_timeout_failed = (
            status == "failed"
            and "timed out" in str(job.get("error") or "").strip().lower()
        )
        if is_timeout_failed:
            elapsed_seconds = _seconds_since_iso_timestamp(
                job.get("finished_at") or job.get("callback_retry_at") or job.get("started_at")
            )
            if elapsed_seconds is None:
                continue
            elapsed_seconds = int(elapsed_seconds)
            if elapsed_seconds < timeout_retry_after_seconds:
                continue
        else:
            elapsed_seconds = _job_callback_wait_elapsed_seconds(job)
            if elapsed_seconds is None:
                continue
            elapsed_seconds = int(elapsed_seconds)
            if elapsed_seconds < retry_after_seconds:
                continue

        retry_attempts = _safe_int(job.get("callback_submit_retries"), 0)
        if retry_attempts >= max_submit_retries:
            if elapsed_seconds >= retry_after_seconds:
                # Last-chance guard: never exhaust a job that already has output.
                if _job_has_success_result(job):
                    if kind == "image":
                        _set_image_job(
                            job_id,
                            status="succeeded",
                            error=None,
                            upstream_submit_state="completed",
                            finished_at=job.get("finished_at") or now_bj_iso(),
                        )
                    else:
                        _set_video_job(
                            job_id,
                            status="succeeded",
                            error=None,
                            upstream_submit_state="completed",
                            finished_at=job.get("finished_at") or now_bj_iso(),
                        )
                    mark_generation_task_status_external(job_id, status="completed", error=None)
                    continue
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



# pool cache / episode workers -> generation_runtime.job_store

