# -*- coding: utf-8 -*-
"""Forced provider poll after generation timeout (callback supplement).

Even in pure-callback mode, when an image/video job hits the running timeout
without a usable result, query the provider up to 3 times (30s apart) and
download/persist any ready media URL.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, Optional, Tuple

from app.core.time_utils import now_bj_iso
from app.db.session import SessionLocal
from app.services.generation_runtime.job_store import (
    IMAGE_JOB_LOCK,
    IMAGE_JOB_MAX_RUNNING_SECONDS,
    IMAGE_JOB_STORE,
    VIDEO_JOB_LOCK,
    VIDEO_JOB_MAX_RUNNING_SECONDS,
    VIDEO_JOB_STORE,
    _job_has_success_result,
    _set_image_job,
    _set_video_job,
)
from app.services.generation_runtime.queue_config_runtime import _queue_cfg_int

logger = logging.getLogger("api_logger")

_TIMEOUT_POLL_INFLIGHT: set[str] = set()
_TIMEOUT_POLL_LOCK = threading.Lock()

_TIMEOUT_POLL_UPSTREAM = "callback_timeout_poll"
_TIMEOUT_POLL_EXHAUSTED_UPSTREAM = "callback_timeout_poll_exhausted"
_FOLLOWUP_POLL_UPSTREAM = "callback_followup_poll"


def _timeout_poll_max_attempts() -> int:
    return _queue_cfg_int("timeout_poll_max_attempts", 3, minimum=1, maximum=10)


def _timeout_poll_interval_seconds() -> int:
    return _queue_cfg_int("timeout_poll_interval_seconds", 30, minimum=5, maximum=300)


def _followup_poll_delay_seconds() -> int:
    return _queue_cfg_int("callback_followup_poll_delay_seconds", 90, minimum=15, maximum=600)


def _followup_poll_max_attempts() -> int:
    return _queue_cfg_int("callback_followup_poll_max_attempts", 40, minimum=3, maximum=120)


def _followup_poll_interval_seconds() -> int:
    return _queue_cfg_int("callback_followup_poll_interval_seconds", 30, minimum=10, maximum=120)


def _inflight_key(kind: str, job_id: str) -> str:
    return f"{str(kind or '').strip().lower()}:{str(job_id or '').strip()}"


def _hydrate_job(kind: str, job_id: str) -> Dict[str, Any]:
    store = IMAGE_JOB_STORE if kind == "image" else VIDEO_JOB_STORE
    lock = IMAGE_JOB_LOCK if kind == "image" else VIDEO_JOB_LOCK
    with lock:
        return dict(store.get(job_id) or {})


def _set_job(kind: str, job_id: str, **fields: Any) -> None:
    if kind == "image":
        _set_image_job(job_id, **fields)
    else:
        _set_video_job(job_id, **fields)


def _first_api_key(value: Any) -> str:
    if isinstance(value, str):
        raw = value.strip()
        return raw.split(",")[0].strip() if raw else ""
    if isinstance(value, dict):
        return _first_api_key(value.get("api_key") or value.get("key") or value.get("api_keys") or "")
    if isinstance(value, list):
        for item in value:
            found = _first_api_key(item)
            if found:
                return found
    return ""


def _resolve_poll_credentials(job: Dict[str, Any]) -> Tuple[str, str, str, str]:
    """Return (api_key, query_endpoint, provider, base_url)."""
    from app.models.all_models import ProviderKeyPool, SystemAPISetting

    billing = job.get("billing_context") if isinstance(job.get("billing_context"), dict) else {}
    result = job.get("result") if isinstance(job.get("result"), dict) else {}
    meta = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}

    provider = str(
        billing.get("provider")
        or job.get("provider")
        or meta.get("provider")
        or ""
    ).strip()
    system_api_id = billing.get("system_api_id")
    if system_api_id is None:
        system_api_id = meta.get("system_api_id") or job.get("system_api_id")
    try:
        system_api_id = int(system_api_id) if system_api_id is not None else None
    except Exception:
        system_api_id = None

    query_endpoint = str(
        meta.get("query_endpoint")
        or meta.get("queryEndpoint")
        or billing.get("query_endpoint")
        or job.get("query_endpoint")
        or ""
    ).strip()

    api_key = ""
    base_url = ""
    db = None
    try:
        db = SessionLocal()
        row = None
        if system_api_id:
            row = db.query(SystemAPISetting).filter(SystemAPISetting.id == int(system_api_id)).first()
        provider_l = provider.lower()
        if row is None and provider_l:
            for candidate in (
                db.query(SystemAPISetting)
                .filter(SystemAPISetting.provider.isnot(None))
                .order_by(SystemAPISetting.id.desc())
                .all()
            ):
                candidate_provider = str(getattr(candidate, "provider", "") or "").strip().lower()
                if candidate_provider == provider_l:
                    if _first_api_key(getattr(candidate, "api_key", None)):
                        row = candidate
                        break
                    continue
                # ark and ark-seedance are distinct providers; never cross-match via startswith/"ark" in ...
                ark_aliases = {"ark", "ark-seedance", "ark_seedance"}
                if provider_l in ark_aliases or candidate_provider in ark_aliases:
                    continue
                if provider_l and (
                    candidate_provider.startswith(provider_l)
                    or provider_l.startswith(candidate_provider)
                    or ("kie" in provider_l and "kie" in candidate_provider)
                    or ("grsai" in provider_l and "grsai" in candidate_provider)
                    or ("runninghub" in provider_l and "runninghub" in candidate_provider)
                ):
                    if _first_api_key(getattr(candidate, "api_key", None)):
                        row = candidate
                        break
        if row is not None:
            api_key = _first_api_key(getattr(row, "api_key", None))
            base_url = str(getattr(row, "base_url", "") or "").strip().rstrip("/")
            conf = getattr(row, "config", None)
            if isinstance(conf, dict) and not query_endpoint:
                query_endpoint = str(conf.get("query_endpoint") or "").strip()
            if not provider:
                provider = str(getattr(row, "provider", "") or "").strip()
            if not query_endpoint and base_url:
                query_endpoint = base_url
        if not api_key and provider_l:
            for candidate in db.query(ProviderKeyPool).filter(ProviderKeyPool.provider.isnot(None)).all():
                if str(getattr(candidate, "provider", "") or "").strip().lower() != provider_l:
                    continue
                api_key = _first_api_key(getattr(candidate, "api_keys", None))
                if api_key:
                    break
    except Exception as exc:
        logger.warning("[TimeoutPoll] credential resolve failed | error=%s", exc)
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                pass

    provider_l = provider.lower()
    if "kie" in provider_l and not query_endpoint:
        query_endpoint = "https://api.kie.ai/api/v1/jobs/recordInfo"
    if "runninghub" in provider_l and not query_endpoint:
        query_endpoint = "https://www.runninghub.cn/openapi/v2/query"
    if ("ark" in provider_l or "seedance" in provider_l) and not query_endpoint:
        query_endpoint = "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"
    if "grsai" in provider_l and not query_endpoint:
        root = base_url or "https://grsaiapi.com"
        query_endpoint = f"{root.rstrip('/')}/v1/draw/result"
    if ("nukoai" in provider_l or "nokoai" in provider_l or "nokuai" in provider_l) and not query_endpoint:
        root = base_url or "https://www.nukoai.com/api/ext/v1"
        query_endpoint = f"{root.rstrip('/')}/videos" if not root.rstrip("/").lower().endswith("/videos") else root

    return api_key, query_endpoint, provider, base_url


def _apply_poll_success(kind: str, job_id: str, job: Dict[str, Any], poll_result: Dict[str, Any]) -> bool:
    from app.services.generation_runtime.callbacks import (
        _build_result_from_provider_callback,
        _extract_job_provider_callback_ticket,
        _maybe_finalize_image_job_from_grsai_callback,
        _maybe_finalize_video_job_from_provider_callback,
        _set_generation_callback_payload,
        _settle_or_cancel_image_job_billing_from_callback,
    )
    from app.services.generation_runtime.job_store import _extract_job_result_url
    from app.services.generation_task_queue import mark_generation_task_status_external

    url = str(poll_result.get("url") or "").strip()
    if not url:
        return False

    raw = poll_result.get("raw") if isinstance(poll_result.get("raw"), dict) else {}
    meta = poll_result.get("metadata") if isinstance(poll_result.get("metadata"), dict) else {}
    callback_payload: Dict[str, Any] = {
        "status": "succeeded",
        "task_id": meta.get("task_id") or job.get("provider_task_id"),
        "taskId": meta.get("taskId") or job.get("provider_task_id"),
        "result_url": url,
        "url": url,
        "raw": raw,
        "metadata": meta,
        "timeout_poll_recovery": True,
    }
    if raw:
        # Keep provider fields available to finalize/billing extractors.
        for key in ("data", "eventData", "usage", "creditsConsumed", "resultJson"):
            if key in raw and key not in callback_payload:
                callback_payload[key] = raw.get(key)

    ticket = _extract_job_provider_callback_ticket(job)
    if ticket:
        _set_generation_callback_payload(ticket, callback_payload)

    # Also attach a built result immediately so finalize has a durable URL even
    # when callback ticket matching is delayed.
    built = _build_result_from_provider_callback(
        callback_payload,
        fallback_provider=str(job.get("provider") or "") or None,
        fallback_model=str(job.get("model") or "") or None,
    )
    if built and _extract_job_result_url(built):
        _set_job(
            kind,
            job_id,
            result=built,
            error=None,
            upstream_submit_state=_TIMEOUT_POLL_UPSTREAM,
        )

    live = _hydrate_job(kind, job_id)
    if kind == "image":
        updated = _maybe_finalize_image_job_from_grsai_callback(job_id, live)
        updated = _settle_or_cancel_image_job_billing_from_callback(
            job_id,
            updated,
            callback_payload,
        )
    else:
        updated = _maybe_finalize_video_job_from_provider_callback(job_id, live)
        try:
            from app.services.generation_runtime.video_job_billing import (
                _settle_or_cancel_video_job_billing_from_callback,
            )
            import asyncio

            async def _settle() -> None:
                await _settle_or_cancel_video_job_billing_from_callback(job_id, updated, callback_payload)

            try:
                running_loop = asyncio.get_running_loop()
            except RuntimeError:
                running_loop = None
            if running_loop and running_loop.is_running():
                fut = asyncio.run_coroutine_threadsafe(_settle(), running_loop)
                fut.result(timeout=120)
            else:
                asyncio.run(_settle())
        except Exception:
            logger.exception("[TimeoutPoll] video billing settle failed | job_id=%s", job_id)

    live = _hydrate_job(kind, job_id)
    if _job_has_success_result(live) or _extract_job_result_url(live.get("result")):
        if str(live.get("status") or "").strip().lower() not in {"succeeded", "completed", "done", "storing_asset"}:
            _set_job(
                kind,
                job_id,
                status="succeeded",
                finished_at=live.get("finished_at") or now_bj_iso(),
                error=None,
                upstream_submit_state="completed",
                timeout_poll_attempts=int(live.get("timeout_poll_attempts") or 0),
            )
            mark_generation_task_status_external(job_id, status="completed", error=None)
        else:
            _set_job(
                kind,
                job_id,
                upstream_submit_state="completed",
                error=None,
                callback_submit_retries=0,
                callback_retry_at=None,
            )
            mark_generation_task_status_external(job_id, status="completed", error=None)
        logger.info(
            "[TimeoutPoll] recovered %s job via provider poll | job_id=%s url=%s",
            kind,
            job_id,
            url,
        )
        return True
    return False


def _mark_timeout_failed(kind: str, job_id: str, job: Dict[str, Any], *, attempts: int) -> None:
    from app.services.generation_task_queue import mark_generation_task_status_external

    max_running = VIDEO_JOB_MAX_RUNNING_SECONDS if kind == "video" else IMAGE_JOB_MAX_RUNNING_SECONDS
    timeout_message = (
        f"{kind} job callback wait timed out after poll recovery "
        f"(attempts={attempts}/{_timeout_poll_max_attempts()}, limit={max_running}s)"
    )
    _set_job(
        kind,
        job_id,
        status="failed",
        finished_at=now_bj_iso(),
        error=timeout_message,
        upstream_submit_state=_TIMEOUT_POLL_EXHAUSTED_UPSTREAM,
        timeout_poll_attempts=attempts,
    )
    if kind == "video":
        try:
            from app.services.generation_runtime.video_job_billing import _cancel_video_job_pending_reservation

            live = _hydrate_job(kind, job_id)
            _cancel_video_job_pending_reservation(job_id, live, timeout_message)
        except Exception:
            logger.exception("[TimeoutPoll] cancel video reservation failed | job_id=%s", job_id)
    else:
        try:
            from app.services.billing_service import billing_service

            live = _hydrate_job(kind, job_id)
            reservation_tx_id = live.get("reservation_tx_id")
            if reservation_tx_id and not live.get("billing_settled"):
                db = SessionLocal()
                try:
                    billing_service.cancel_reservation(db, int(reservation_tx_id), timeout_message)
                finally:
                    db.close()
        except Exception:
            logger.exception("[TimeoutPoll] cancel image reservation failed | job_id=%s", job_id)

    mark_generation_task_status_external(job_id, status="failed", error=timeout_message)
    logger.warning(
        "[TimeoutPoll] exhausted %s job poll recovery | job_id=%s attempts=%s",
        kind,
        job_id,
        attempts,
    )


def _recovery_thread_main(
    kind: str,
    job_id: str,
    *,
    mode: str = "timeout",
    initial_delay_seconds: int = 0,
    max_attempts: Optional[int] = None,
    interval_seconds: Optional[int] = None,
) -> None:
    from app.services.generation_runtime.callbacks import _extract_job_provider_task_id
    from app.services.media_service import media_service

    key = _inflight_key(kind, job_id)
    is_followup = str(mode or "").strip().lower() == "followup"
    upstream_label = _FOLLOWUP_POLL_UPSTREAM if is_followup else _TIMEOUT_POLL_UPSTREAM
    resolved_max_attempts = int(
        max_attempts
        if max_attempts is not None
        else (_followup_poll_max_attempts() if is_followup else _timeout_poll_max_attempts())
    )
    resolved_interval = int(
        interval_seconds
        if interval_seconds is not None
        else (_followup_poll_interval_seconds() if is_followup else _timeout_poll_interval_seconds())
    )
    try:
        delay = max(0, int(initial_delay_seconds or 0))
        if delay > 0:
            logger.info(
                "[TimeoutPoll] followup delay before first poll | kind=%s job_id=%s delay_seconds=%s",
                kind,
                job_id,
                delay,
            )
            time.sleep(delay)
            live = _hydrate_job(kind, job_id)
            if not live or _job_has_success_result(live):
                return

        for attempt in range(1, resolved_max_attempts + 1):
            job = _hydrate_job(kind, job_id)
            if not job:
                return
            if _job_has_success_result(job):
                logger.info(
                    "[TimeoutPoll] skip remaining polls; job already succeeded | kind=%s job_id=%s",
                    kind,
                    job_id,
                )
                return

            provider_task_id = _extract_job_provider_task_id(job)
            if not provider_task_id:
                logger.warning(
                    "[TimeoutPoll] missing provider_task_id | kind=%s job_id=%s",
                    kind,
                    job_id,
                )
                if is_followup:
                    _set_job(
                        kind,
                        job_id,
                        status="waiting_callback",
                        upstream_submit_state="callback_pending",
                        error=None,
                    )
                    return
                _mark_timeout_failed(kind, job_id, job, attempts=attempt)
                return

            _set_job(
                kind,
                job_id,
                status="waiting_callback",
                upstream_submit_state=upstream_label,
                timeout_poll_attempts=attempt,
                timeout_poll_at=now_bj_iso(),
                error=None,
            )

            api_key, query_endpoint, provider, base_url = _resolve_poll_credentials(job)
            if not api_key:
                logger.warning(
                    "[TimeoutPoll] missing api key | kind=%s job_id=%s provider=%s attempt=%s/%s",
                    kind,
                    job_id,
                    provider or None,
                    attempt,
                    resolved_max_attempts,
                )
            else:
                logger.info(
                    "[TimeoutPoll] polling provider | kind=%s job_id=%s provider=%s task_id=%s attempt=%s/%s mode=%s",
                    kind,
                    job_id,
                    provider or None,
                    provider_task_id,
                    attempt,
                    resolved_max_attempts,
                    "followup" if is_followup else "timeout",
                )
                poll_result = media_service.fetch_provider_task_result(
                    task_id=provider_task_id,
                    api_key=api_key,
                    query_endpoint=query_endpoint or None,
                    provider=provider or None,
                    kind=kind,
                    base_url=base_url or None,
                )
                if isinstance(poll_result, dict) and poll_result.get("url"):
                    if _apply_poll_success(kind, job_id, job, poll_result):
                        return
                status = str((poll_result or {}).get("status") or "").strip().lower()
                if status in {"failed", "canceled", "cancelled", "expired"}:
                    logger.warning(
                        "[TimeoutPoll] provider reported terminal failure | kind=%s job_id=%s status=%s attempt=%s/%s",
                        kind,
                        job_id,
                        status,
                        attempt,
                        resolved_max_attempts,
                    )
                    # Keep trying remaining attempts in case status/payload is stale.
                elif poll_result and poll_result.get("error"):
                    logger.warning(
                        "[TimeoutPoll] poll error | kind=%s job_id=%s attempt=%s/%s error=%s",
                        kind,
                        job_id,
                        attempt,
                        resolved_max_attempts,
                        poll_result.get("error"),
                    )

            # Late callback may have finalized while we were polling.
            live = _hydrate_job(kind, job_id)
            if _job_has_success_result(live):
                return

            if attempt < resolved_max_attempts:
                time.sleep(resolved_interval)

        job = _hydrate_job(kind, job_id)
        if _job_has_success_result(job):
            return
        if is_followup:
            # Soft stop: keep waiting for late webhook / hard timeout recovery.
            _set_job(
                kind,
                job_id,
                status="waiting_callback",
                upstream_submit_state="callback_pending",
                error=None,
            )
            logger.warning(
                "[TimeoutPoll] followup exhausted without result; leaving job waiting | kind=%s job_id=%s attempts=%s",
                kind,
                job_id,
                resolved_max_attempts,
            )
            return
        _mark_timeout_failed(kind, job_id, job, attempts=resolved_max_attempts)
    except Exception:
        logger.exception("[TimeoutPoll] recovery thread failed | kind=%s job_id=%s mode=%s", kind, job_id, mode)
        try:
            job = _hydrate_job(kind, job_id)
            if job and not _job_has_success_result(job):
                if is_followup:
                    _set_job(
                        kind,
                        job_id,
                        status="waiting_callback",
                        upstream_submit_state="callback_pending",
                        error=None,
                    )
                else:
                    _mark_timeout_failed(kind, job_id, job, attempts=_timeout_poll_max_attempts())
        except Exception:
            pass
    finally:
        with _TIMEOUT_POLL_LOCK:
            _TIMEOUT_POLL_INFLIGHT.discard(key)


def maybe_start_timeout_poll_recovery(kind: str, job_id: str, job: Optional[Dict[str, Any]] = None) -> bool:
    """Start forced timeout poll recovery when possible.

    Returns True when recovery is running / started (caller must NOT mark failed yet).
    Returns False when recovery cannot run (no task id / already exhausted).
    """
    from app.services.generation_runtime.callbacks import _extract_job_provider_task_id

    stable_kind = str(kind or "").strip().lower()
    stable_job_id = str(job_id or "").strip()
    if stable_kind not in {"image", "video"} or not stable_job_id:
        return False

    payload = dict(job or {}) or _hydrate_job(stable_kind, stable_job_id)
    if _job_has_success_result(payload):
        return False

    upstream = str(payload.get("upstream_submit_state") or "").strip().lower()
    if _TIMEOUT_POLL_EXHAUSTED_UPSTREAM in upstream:
        return False

    provider_task_id = _extract_job_provider_task_id(payload)
    if not provider_task_id:
        return False

    attempts = 0
    try:
        attempts = int(payload.get("timeout_poll_attempts") or 0)
    except Exception:
        attempts = 0
    if attempts >= _timeout_poll_max_attempts() and _TIMEOUT_POLL_EXHAUSTED_UPSTREAM in upstream:
        return False

    key = _inflight_key(stable_kind, stable_job_id)
    with _TIMEOUT_POLL_LOCK:
        if key in _TIMEOUT_POLL_INFLIGHT:
            return True
        _TIMEOUT_POLL_INFLIGHT.add(key)

    _set_job(
        stable_kind,
        stable_job_id,
        status="waiting_callback",
        upstream_submit_state=_TIMEOUT_POLL_UPSTREAM,
        error=None,
        finished_at=None,
        timeout_poll_attempts=int(payload.get("timeout_poll_attempts") or 0),
        timeout_poll_started_at=payload.get("timeout_poll_started_at") or now_bj_iso(),
    )

    thread = threading.Thread(
        target=_recovery_thread_main,
        kwargs={
            "kind": stable_kind,
            "job_id": stable_job_id,
            "mode": "timeout",
            "initial_delay_seconds": 0,
        },
        name=f"timeout-poll-{stable_kind}-{stable_job_id[:12]}",
        daemon=True,
    )
    thread.start()
    logger.warning(
        "[TimeoutPoll] started recovery | kind=%s job_id=%s provider_task_id=%s max_attempts=%s interval_seconds=%s",
        stable_kind,
        stable_job_id,
        provider_task_id,
        _timeout_poll_max_attempts(),
        _timeout_poll_interval_seconds(),
    )
    return True


def maybe_start_callback_followup_poll(kind: str, job_id: str, job: Optional[Dict[str, Any]] = None) -> bool:
    """Start early provider polling after an intermediate running webhook.

    Ark/Seedance (and similar) often send running then lose/drop the succeeded webhook.
    Do not wait for the full running-timeout before querying the provider.
    """
    from app.services.generation_runtime.callbacks import _extract_job_provider_task_id

    stable_kind = str(kind or "").strip().lower()
    stable_job_id = str(job_id or "").strip()
    if stable_kind not in {"image", "video"} or not stable_job_id:
        return False

    payload = dict(job or {}) or _hydrate_job(stable_kind, stable_job_id)
    if _job_has_success_result(payload):
        return False

    upstream = str(payload.get("upstream_submit_state") or "").strip().lower()
    if _TIMEOUT_POLL_EXHAUSTED_UPSTREAM in upstream:
        return False

    provider_task_id = _extract_job_provider_task_id(payload)
    if not provider_task_id:
        return False

    key = _inflight_key(stable_kind, stable_job_id)
    with _TIMEOUT_POLL_LOCK:
        if key in _TIMEOUT_POLL_INFLIGHT:
            return True
        _TIMEOUT_POLL_INFLIGHT.add(key)

    delay = _followup_poll_delay_seconds()
    max_attempts = _followup_poll_max_attempts()
    interval = _followup_poll_interval_seconds()
    _set_job(
        stable_kind,
        stable_job_id,
        status="waiting_callback",
        upstream_submit_state=_FOLLOWUP_POLL_UPSTREAM,
        error=None,
        finished_at=None,
        timeout_poll_started_at=payload.get("timeout_poll_started_at") or now_bj_iso(),
        callback_followup_armed_at=now_bj_iso(),
    )

    thread = threading.Thread(
        target=_recovery_thread_main,
        kwargs={
            "kind": stable_kind,
            "job_id": stable_job_id,
            "mode": "followup",
            "initial_delay_seconds": delay,
            "max_attempts": max_attempts,
            "interval_seconds": interval,
        },
        name=f"followup-poll-{stable_kind}-{stable_job_id[:12]}",
        daemon=True,
    )
    thread.start()
    logger.warning(
        "[TimeoutPoll] started followup after running callback | kind=%s job_id=%s provider_task_id=%s delay=%ss attempts=%s interval=%ss",
        stable_kind,
        stable_job_id,
        provider_task_id,
        delay,
        max_attempts,
        interval,
    )
    return True


def is_timeout_poll_in_progress(kind: str, job_id: str, job: Optional[Dict[str, Any]] = None) -> bool:
    key = _inflight_key(kind, job_id)
    with _TIMEOUT_POLL_LOCK:
        if key in _TIMEOUT_POLL_INFLIGHT:
            return True
    payload = job if isinstance(job, dict) else _hydrate_job(str(kind or "").strip().lower(), str(job_id or "").strip())
    upstream = str((payload or {}).get("upstream_submit_state") or "").strip().lower()
    if _TIMEOUT_POLL_EXHAUSTED_UPSTREAM in upstream:
        return False
    return _TIMEOUT_POLL_UPSTREAM in upstream or _FOLLOWUP_POLL_UPSTREAM in upstream
