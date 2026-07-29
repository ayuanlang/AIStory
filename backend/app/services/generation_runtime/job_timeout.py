# -*- coding: utf-8 -*-
"""Generation job running-timeout / stuck-job finalize helpers."""
from __future__ import annotations

import threading
from typing import Any, Dict, Optional

from app.core.time_utils import now_bj_iso
from app.services.generation_runtime.job_store import (
    IMAGE_JOB_LOCK,
    IMAGE_JOB_STORE,
    VIDEO_JOB_LOCK,
    VIDEO_JOB_STORE,
    _JOB_TIMEOUT_CHECK_STATUSES,
)
from app.services.generation_runtime.callbacks import _normalize_generation_status


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
        if (
            "callback_pending" in upstream_state
            or "callback_wait" in upstream_state
            or "callback_retry" in upstream_state
            or "callback_timeout_poll" in upstream_state
            or not upstream_state
            or upstream_state == "unknown"
        ):
            set_job_func(
                job_id,
                upstream_submit_state="completed",
                callback_submit_retries=0,
                callback_retry_at=None,
                error=None,
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
        # Even in pure-callback mode: force provider poll + download as callback supplement
        # before permanently failing the job.
        try:
            from app.services.generation_runtime.callbacks import _extract_job_provider_task_id
            from app.services.generation_runtime.timeout_poll_recovery import (
                is_timeout_poll_in_progress,
                maybe_start_timeout_poll_recovery,
            )

            if is_timeout_poll_in_progress(kind, job_id, job):
                return job
            if _extract_job_provider_task_id(job) and maybe_start_timeout_poll_recovery(kind, job_id, job):
                store = IMAGE_JOB_STORE if kind == "image" else VIDEO_JOB_STORE
                with lock:
                    updated = dict(store.get(job_id) or {})
                return updated or job
        except Exception:
            import logging

            logging.getLogger("api_logger").exception(
                "[%sJob] timeout poll recovery start failed | job_id=%s",
                "Image" if kind == "image" else "Video",
                job_id,
            )

        timeout_message = (
            f"{kind} job callback wait timed out after {elapsed_seconds}s (limit={timeout_seconds}s)"
        )
        upstream_submit_state = "callback_wait_timeout"
    else:
        # Poll-mode timeout: still try one last provider recovery when we have a task id.
        try:
            from app.services.generation_runtime.callbacks import _extract_job_provider_task_id
            from app.services.generation_runtime.timeout_poll_recovery import (
                is_timeout_poll_in_progress,
                maybe_start_timeout_poll_recovery,
            )

            if is_timeout_poll_in_progress(kind, job_id, job):
                return job
            if _extract_job_provider_task_id(job) and maybe_start_timeout_poll_recovery(kind, job_id, job):
                store = IMAGE_JOB_STORE if kind == "image" else VIDEO_JOB_STORE
                with lock:
                    updated = dict(store.get(job_id) or {})
                return updated or job
        except Exception:
            import logging

            logging.getLogger("api_logger").exception(
                "[%sJob] timeout poll recovery start failed | job_id=%s",
                "Image" if kind == "image" else "Video",
                job_id,
            )
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

