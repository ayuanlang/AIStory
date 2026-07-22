# -*- coding: utf-8 -*-
"""Helpers for generation job-pool / batch-job status payloads."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, Optional

from app.core.time_utils import now_bj_iso
from app.services.endpoint_misc import _safe_int

def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is not None:
            return dt.astimezone(tz=None).replace(tzinfo=None)
        return dt
    except Exception:
        return None


def _normalize_batch_job_status(payload: Dict[str, Any]) -> str:
    if bool(payload.get("force_stopped")):
        return "canceled"
    if bool(payload.get("stopped_by_user")) or bool(payload.get("stop_requested")):
        return "canceled"

    status_raw = str(payload.get("status") or "").strip().lower()
    if status_raw in {"running", "queued", "completed", "failed", "stopped", "canceled", "cancelled", "error", "idle", "partial"}:
        return status_raw

    if bool(payload.get("running")):
        return "running"

    failed = _safe_int(payload.get("failed"), 0)
    success = _safe_int(payload.get("success"), 0)
    generated = _safe_int(payload.get("generated"), 0)
    completed = _safe_int(payload.get("completed"), 0)
    total = _safe_int(payload.get("total") or payload.get("episodes_in_run"), 0)

    if failed > 0 and (success > 0 or generated > 0):
        return "partial"
    if failed > 0:
        return "failed"

    if bool(payload.get("generation_success")):
        return "completed"

    if total > 0 and completed >= total:
        return "completed"
    if completed > 0 and total == 0 and failed == 0:
        return "completed"

    return "idle"


def _extract_target_id_from_job_id(job_id: str) -> Optional[int]:
    stable = str(job_id or "").strip()
    if not stable:
        return None
    m = re.search(r"(\d+)$", stable)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def _build_batch_job_item(
    *,
    kind: str,
    job_id: str,
    payload: Dict[str, Any],
    user_id: Optional[int],
    username: Optional[str],
) -> Dict[str, Any]:
    status = _normalize_batch_job_status(payload)
    started_at = payload.get("started_at") or payload.get("created_at")
    finished_at = payload.get("finished_at")
    updated_at = payload.get("updated_at")
    created_at = started_at or updated_at or now_bj_iso()

    error_text = ""
    errors = payload.get("errors")
    if isinstance(errors, list) and errors:
        error_text = str(errors[-1])
    if not error_text:
        error_text = str(payload.get("error") or "").strip()
    if not error_text and status == "partial":
        error_text = "Partially failed"

    return {
        "kind": kind,
        "job_id": job_id,
        "status": status,
        "user_id": user_id,
        "username": username,
        "created_at": created_at,
        "started_at": started_at,
        "finished_at": finished_at,
        "error": error_text,
        "has_task": bool(payload.get("running")),
    }


