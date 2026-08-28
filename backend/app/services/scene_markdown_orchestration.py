# -*- coding: utf-8 -*-
"""Scene markdown (Stage 2.2) orchestration retry knobs and helpers."""
from __future__ import annotations

import re
import time
from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy.exc import OperationalError, TimeoutError as SQLAlchemyTimeoutError
from sqlalchemy.orm import Session

from app.core.prompt_injection import END, START, unwrap_injection_section, wrap_injection_section
from app.services.script_analysis_flow import (
    SCENES_BLOCK_START_TOKEN,
    SceneBeatsTooShortError,
    SceneMissingBeat1Error,
    strip_beat_transition_notes_from_script,
)
from app.services.credit_error import (
    credit_error_code,
    credit_error_user_message,
    is_insufficient_credits_error,
)
from app.services.script_analysis_flow.analyze_scene_stages import import_scene_markdown_stage

SCENE_MARKDOWN_ORCHESTRATION_MAX_ATTEMPTS = 3
SCENE_MARKDOWN_ORCHESTRATION_RETRY_BASE_DELAY_SEC = 2.0
SCENE_MARKDOWN_ORCHESTRATION_BATCH_RETRY_ROUNDS = 0

def _extract_analysis_text_from_result(result: Any) -> str:
    if isinstance(result, str):
        return result
    if hasattr(result, "model_dump"):
        try:
            result = result.model_dump()
        except Exception:
            result = result
    elif hasattr(result, "dict") and callable(getattr(result, "dict")):
        try:
            result = result.dict()
        except Exception:
            result = result
    if not isinstance(result, dict):
        result = getattr(result, "__dict__", None) or {}
    if not isinstance(result, dict):
        return ""
    for key in ("result", "content", "adapted_script", "scenes_markdown"):
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            return value
    data = result.get("data")
    if isinstance(data, dict):
        for key in ("result", "content", "adapted_script", "scenes_markdown"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return ""


def _replace_adapted_script_in_beats_user_input(user_text: str, adapted_script_text: str) -> str:
    source = str(user_text or "")
    adapted = strip_beat_transition_notes_from_script(adapted_script_text)
    if not source.strip():
        return adapted
    wrapped_adapted = unwrap_injection_section(source, "优化后剧本")
    if wrapped_adapted is not None:
        pattern = rf"\[优化后剧本{re.escape(START)}\]\s*.*?\s*\[优化后剧本{re.escape(END)}\]"
        replaced = re.sub(
            pattern,
            wrap_injection_section("优化后剧本", adapted),
            source,
            count=1,
            flags=re.DOTALL,
        )
        return replaced.strip()
    marker_match = re.search(r"(\[优化后剧本[^\]]*\]\s*\n)([\s\S]*)$", source)
    if marker_match:
        return f"{source[:marker_match.start(2)]}{adapted}".strip()
    if SCENES_BLOCK_START_TOKEN in source:
        start_idx = source.find(SCENES_BLOCK_START_TOKEN)
        return f"{source[:start_idx].rstrip()}\n\n{adapted}".strip()
    return f"{source.rstrip()}\n\n{adapted}".strip()


def _is_retryable_scene_orchestration_error(exc: Exception) -> bool:
    if isinstance(exc, (SceneBeatsTooShortError, SceneMissingBeat1Error)):
        return False
    if isinstance(exc, (OperationalError, SQLAlchemyTimeoutError)):
        return True
    if isinstance(exc, HTTPException):
        status = int(getattr(exc, "status_code", 500) or 500)
        detail = str(getattr(exc, "detail", "") or "")
        # Stage 1 data quality errors; do not retry.
        if detail.startswith("SCENE_MARKDOWN_BEATS_TOO_SHORT"):
            return False
        if detail.startswith("SCENE_MARKDOWN_MISSING_BEAT_1"):
            return False
        if status == 402 or is_insufficient_credits_error(exc):
            return False
        if status in (408, 429, 500, 502, 503, 504):
            return True
        if detail.startswith(
            (
                "SCENE_MARKDOWN_EMPTY_FOR_SCENE:",
                "SCENE_MARKDOWN_SCENE_ID_MISMATCH:",
                "SCENE_MARKDOWN_EMPTY",
                "SCENE_MARKDOWN_NO_SCENE_ROW",
                "SCENE_MARKDOWN_PARSE_FAILED",
                "SCENE_MARKDOWN_ORCHESTRATION_FAILED",
            )
        ):
            return True
        if status == 422 and detail.startswith("SCENE_MARKDOWN_"):
            return True
        if "LLM_STREAM" in detail.upper() or "TIMEOUT" in detail.upper():
            return True
        return False
    msg = str(exc or "").lower()
    if "database is locked" in msg or "timeout" in msg or "rate limit" in msg:
        return True
    return False


def _scene_orchestration_error_code(exc: Exception, scene_id: str) -> str:
    if isinstance(exc, (SceneBeatsTooShortError, SceneMissingBeat1Error)):
        return exc.detail
    if isinstance(exc, HTTPException):
        if is_insufficient_credits_error(exc):
            return f"{credit_error_code(exc)}:{scene_id}"
        detail = str(getattr(exc, "detail", "") or "")
        if detail.startswith("SCENE_MARKDOWN_SCENE_ID_MISMATCH"):
            return detail if "," in detail or detail.count(":") > 1 else detail
        if detail.startswith("SCENE_MARKDOWN_") or detail.startswith("SCENES_TABLE_"):
            return detail
    if is_insufficient_credits_error(exc):
        return f"{credit_error_code(exc)}:{scene_id}:{credit_error_user_message(exc)}"
    exc_type = type(exc).__name__
    msg = str(exc or "").strip().replace("\n", " ")[:240]
    if msg:
        return f"SCENE_MARKDOWN_ORCHESTRATION_FAILED:{scene_id}:{exc_type}:{msg}"
    return f"SCENE_MARKDOWN_ORCHESTRATION_FAILED:{scene_id}"


def _select_workspace_row_from_orchestration_markdown(
    markdown: str,
    *,
    target_scene_id: str,
    scene_order: Optional[int] = None,
) -> Optional[Dict[str, str]]:
    from app.services.scene_no_utils import _canonicalize_scene_no
    from app.services.scene_subject_helpers import _parse_scene_rows_from_markdown

    rows = _parse_scene_rows_from_markdown(markdown)
    if not rows:
        return None
    target = str(target_scene_id or "").strip()
    target_no = _canonicalize_scene_no(None, scene_id=target) or (
        str(int(scene_order)) if scene_order else ""
    )
    for row in rows:
        row_id = str(row.get("scene_id") or "").strip()
        row_no = _canonicalize_scene_no(row.get("scene_no"), scene_id=row_id)
        if target and row_id and target.lower() == row_id.lower():
            return row
        if target_no and row_no and target_no == row_no:
            return row
    if len(rows) == 1:
        return rows[0]
    return None


def upsert_workspace_scene_from_orchestration_markdown(
    db: Session,
    *,
    episode_id: int,
    markdown: str,
    target_scene_id: str,
    scene_order: Optional[int] = None,
) -> Dict[str, Any]:
    """Write the validated Scenes Table row into workspace Scene records."""
    from app.models.all_models import Scene
    from app.services.scene_no_utils import _canonicalize_scene_no, _find_active_scene_by_scene_no

    row = _select_workspace_row_from_orchestration_markdown(
        markdown,
        target_scene_id=target_scene_id,
        scene_order=scene_order,
    )
    if not row:
        return {"ok": False, "reason": "no_importable_row", "created": 0, "updated": 0}

    scene_id = str(row.get("scene_id") or target_scene_id or "").strip()
    scene_no = _canonicalize_scene_no(row.get("scene_no"), scene_id=scene_id)
    if not scene_no and scene_order:
        scene_no = str(int(scene_order))
    if not scene_no:
        return {"ok": False, "reason": "scene_no_required", "created": 0, "updated": 0}

    existing = _find_active_scene_by_scene_no(
        db,
        episode_id=int(episode_id),
        scene_no=scene_no,
        scene_id=scene_id,
    )
    payload = {
        "scene_no": scene_no,
        "scene_name": str(row.get("scene_name") or "").strip() or None,
        "original_script_text": str(row.get("original_script_text") or "").strip(),
        "equivalent_duration": str(row.get("equivalent_duration") or "").strip() or None,
        "core_scene_info": str(row.get("core_scene_info") or "").strip() or None,
        "environment_name": str(row.get("environment_name") or "").strip() or None,
        "linked_characters": str(row.get("linked_characters") or "").strip() or None,
        "key_props": str(row.get("key_props") or "").strip() or None,
    }
    if existing is not None:
        for key, value in payload.items():
            setattr(existing, key, value)
        db.add(existing)
        return {
            "ok": True,
            "reason": "updated",
            "created": 0,
            "updated": 1,
            "scene_no": scene_no,
            "workspace_scene_id": int(getattr(existing, "id", 0) or 0) or None,
        }

    scene = Scene(episode_id=int(episode_id), **payload)
    db.add(scene)
    db.flush()
    return {
        "ok": True,
        "reason": "created",
        "created": 1,
        "updated": 0,
        "scene_no": scene_no,
        "workspace_scene_id": int(getattr(scene, "id", 0) or 0) or None,
    }


def _import_scene_markdown_stage_with_retry(
    db: Session,
    *,
    project_id: int,
    episode_id: int,
    script_text: str,
    script_id: Optional[str],
    target_scene_id: str,
    max_attempts: int = 3,
) -> None:
    last_exc: Optional[Exception] = None
    for attempt in range(1, max(1, int(max_attempts)) + 1):
        try:
            import_scene_markdown_stage(
                db=db,
                project_id=int(project_id),
                episode_id=int(episode_id),
                script_text=script_text,
                script_id=script_id,
                partial=True,
                target_scene_id=target_scene_id,
            )
            return
        except OperationalError as exc:
            last_exc = exc
            db.rollback()
            msg = str(exc or "").lower()
            if attempt >= max_attempts or "database is locked" not in msg:
                raise
            time.sleep(0.15 * attempt)
        except Exception:
            db.rollback()
            raise
    if last_exc is not None:
        raise last_exc


def _derive_scene_orchestration_phase(
    *,
    import_status: Any,
    parse_status: Any,
) -> str:
    import_key = str(import_status or "").strip().lower()
    parse_key = str(parse_status or "").strip().lower()
    if import_key in {"success", "imported"}:
        return "imported"
    if import_key in {"awaiting_workspace_import"}:
        return "llm_returned"
    if import_key in {"importing"}:
        return "importing"
    if import_key in {"llm_returned"}:
        return "llm_returned"
    if import_key in {"llm_running", "running"}:
        return "llm_submit"
    if import_key in {"failed"} or parse_key in {"failed"}:
        return "failed"
    if import_key in {"queued"}:
        return "queued"
    return import_key or "unknown"


