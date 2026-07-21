# -*- coding: utf-8 -*-
"""Provider callback ingest, finalize, and video/image billing settle."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time_utils import now_bj_iso
from app.db.session import SessionLocal
from app.services.billing_service import billing_service
from app.services.generation_runtime.job_store import *
from app.services.generation_runtime import media_persist as _mp
from app.services.oss_storage_service import oss_storage_service
from app.services.generation_runtime.asset_registration import (  # noqa: F401
    _bind_generated_media_to_entity,
    _bind_generated_media_to_shot,
    _register_asset_helper,
)
from app.services.asset_meta_utils import _asset_optional_int  # noqa: F401

logger = logging.getLogger("api_logger")

# Pull media helpers into this module namespace (callback finalize depends on them).
globals().update({k: v for k, v in vars(_mp).items() if not k.startswith("__")})

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



# shot cancel -> generation_runtime.job_store

# image job file I/O -> generation_runtime.job_store

# media persist -> app.services.generation_runtime.media_persist
from app.services.generation_runtime import media_persist as _media_persist  # noqa: E402
globals().update({k: v for k, v in vars(_media_persist).items() if k == "__all__" or not k.startswith("__")})

# shot/promo/script helpers -> script_mode_helpers
from app.services import script_mode_helpers as _smh  # noqa: E402
globals().update({k: v for k, v in vars(_smh).items() if not k.startswith('__')})


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
        if normalized_status == "succeeded":
            updates["upstream_submit_state"] = "completed"
            updates["callback_submit_retries"] = 0
            updates["callback_retry_at"] = None
        elif normalized_status == "failed":
            updates["upstream_submit_state"] = "callback_failed"
        else:
            updates["upstream_submit_state"] = "canceled"

    if (
        normalized_status == "succeeded"
        and isinstance(updates.get("result"), dict)
        and _extract_job_result_url(updates.get("result"))
        and first_success_finalize
    ):
        early_save: Dict[str, Any] = {
            "status": updates.get("status") or normalized_status,
            "result": updates["result"],
            "upstream_submit_state": "completed",
            "callback_submit_retries": 0,
            "callback_retry_at": None,
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
        if "callback_pending" in str(job.get("upstream_submit_state") or "").strip().lower():
            updates.setdefault("upstream_submit_state", "completed")
            updates.setdefault("callback_submit_retries", 0)
            updates.setdefault("callback_retry_at", None)
        if current_error:
            updates["error"] = None
    elif normalized_status == "succeeded":
        if "callback_pending" in str(job.get("upstream_submit_state") or "").strip().lower():
            updates.setdefault("upstream_submit_state", "completed")
            updates.setdefault("callback_submit_retries", 0)
            updates.setdefault("callback_retry_at", None)
        if current_error:
            updates["error"] = None
    elif normalized_status in {"failed", "canceled"}:
        failure_parts = [str(callback_payload.get("failure_reason") or "").strip(), str(callback_payload.get("error") or "").strip()]
        failure_text = " | ".join([part for part in failure_parts if part])
        if failure_text and failure_text != current_error:
            updates["error"] = failure_text
        if "callback_pending" in str(job.get("upstream_submit_state") or "").strip().lower():
            updates.setdefault(
                "upstream_submit_state",
                "callback_failed" if normalized_status == "failed" else "canceled",
            )

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
        if normalized_status == "succeeded":
            updates["upstream_submit_state"] = "completed"
            updates["callback_submit_retries"] = 0
            updates["callback_retry_at"] = None
        elif normalized_status == "failed":
            updates["upstream_submit_state"] = "callback_failed"
        else:
            updates["upstream_submit_state"] = "canceled"

    if (
        normalized_status == "succeeded"
        and isinstance(updates.get("result"), dict)
        and _extract_job_result_url(updates.get("result"))
        and first_success_finalize
    ):
        early_save: Dict[str, Any] = {
            "status": updates.get("status") or normalized_status,
            "result": updates["result"],
            "upstream_submit_state": "completed",
            "callback_submit_retries": 0,
            "callback_retry_at": None,
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
        if "callback_pending" in str(job.get("upstream_submit_state") or "").strip().lower():
            updates.setdefault("upstream_submit_state", "completed")
            updates.setdefault("callback_submit_retries", 0)
            updates.setdefault("callback_retry_at", None)
        if updates.get("status") == "succeeded":
            updates.setdefault("upstream_submit_state", "completed")
    elif normalized_status in {"failed", "canceled"}:
        failure_parts = [str(callback_payload.get("failure_reason") or "").strip(), str(callback_payload.get("error") or "").strip()]
        failure_text = " | ".join([part for part in failure_parts if part])
        if failure_text and failure_text != current_error:
            updates["error"] = failure_text
        if "callback_pending" in str(job.get("upstream_submit_state") or "").strip().lower():
            updates.setdefault(
                "upstream_submit_state",
                "callback_failed" if normalized_status == "failed" else "canceled",
            )

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


# video billing helpers -> video_job_billing
from app.services.generation_runtime.video_job_billing import (  # noqa: E402
    _cancel_video_job_pending_reservation,
    _extract_kie_callback_settle_fields,
    _find_open_video_reservation_tx_id,
    _persist_video_job_billing_reservation,
    _reservation_already_closed,
    _schedule_video_job_billing_settle,
    _settle_or_cancel_video_job_billing_from_callback,
)


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



