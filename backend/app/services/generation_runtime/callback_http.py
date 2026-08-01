# -*- coding: utf-8 -*-
"""Outbound generation callback URL + HTTP dispatch helpers."""
from __future__ import annotations

import asyncio
import logging
import time
import urllib.parse
from typing import Any, Dict, Optional, Set

import requests

from app.core.config import settings
from app.services.generation_runtime.job_store import _extract_job_result_url

logger = logging.getLogger("api_logger")


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
    from app.services.generation_runtime.callbacks import (
        _compute_webhook_signature,
        _extract_callback_task_id,
        _set_generation_callback_payload_for_ack,
    )

    if not callback_url:
        return

    callback_payload = _build_generation_callback_payload(kind, job)
    callback_result_url = _extract_job_result_url(callback_payload.get("result"))
    local_ticket = _extract_local_generation_callback_ticket(callback_url)
    if local_ticket:
        _set_generation_callback_payload_for_ack(local_ticket, callback_payload)
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

