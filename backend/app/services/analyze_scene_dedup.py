# -*- coding: utf-8 -*-
"""Analyze-scene async dedup table helpers."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, engine
from app.schemas.agent import AnalyzeSceneRequest
from app.services.task_manager import get_status as _get_task_status

logger = logging.getLogger("api_logger")

_ANALYZE_SCENE_DEDUP_WINDOW_SECONDS = max(15, int(os.getenv("ANALYZE_SCENE_DEDUP_WINDOW_SECONDS", "360")))
_ANALYZE_SCENE_DEDUP_PRUNE_INTERVAL_SECONDS = max(
    30,
    int(os.getenv("ANALYZE_SCENE_DEDUP_PRUNE_INTERVAL_SECONDS", "120") or 120),
)
_ANALYZE_SCENE_SEGMENT_TIMEOUT_SECONDS = max(
    30,
    int(os.getenv("ANALYZE_SCENE_SEGMENT_TIMEOUT_SECONDS", "300") or 300),
)
_ANALYZE_SCENE_CONTINUATION_SEGMENT_HARD_CAP = max(
    2,
    min(32, int(os.getenv("ANALYZE_SCENE_CONTINUATION_SEGMENT_HARD_CAP", "12") or 12)),
)
_ANALYZE_SCENE_OUTPUT_CHAR_HARD_CAP = max(
    20000,
    int(os.getenv("ANALYZE_SCENE_OUTPUT_CHAR_HARD_CAP", "120000") or 120000),
)
_ANALYZE_SCENE_DEDUP_TABLE_READY = False
_ANALYZE_SCENE_DEDUP_TABLE_LOCK = threading.Lock()
_ANALYZE_SCENE_DEDUP_LAST_PRUNE_TS = 0.0
_ANALYZE_SCENE_DEDUP_PRUNE_LOCK = threading.Lock()

def _normalize_analyze_scene_dedup_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(k): _normalize_analyze_scene_dedup_payload(v)
            for k, v in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_normalize_analyze_scene_dedup_payload(v) for v in value]
    if isinstance(value, str):
        return value.strip()
    return value


def _build_analyze_scene_dedup_key(user_id: int, request: AnalyzeSceneRequest) -> str:
    payload = {
        "user_id": int(user_id or 0),
        "analysis_trace_id": getattr(request, "analysis_trace_id", None),
        "project_id": getattr(request, "project_id", None),
        "episode_id": getattr(request, "episode_id", None),
        "text": getattr(request, "text", None),
        "prompt_file": getattr(request, "prompt_file", None),
        "system_prompt": getattr(request, "system_prompt", None),
        "project_metadata": getattr(request, "project_metadata", None),
        "scene_analysis_mode": getattr(request, "scene_analysis_mode", None),
        "scene_analysis_features": getattr(request, "scene_analysis_features", None),
        "analysis_attention_notes": getattr(request, "analysis_attention_notes", None),
        "reuse_subject_assets": getattr(request, "reuse_subject_assets", None),
        "include_negative_prompt": getattr(request, "include_negative_prompt", True),
        "function_name": getattr(request, "function_name", None),
        "system_api_id": getattr(request, "system_api_id", None),
    }
    stable_payload = _normalize_analyze_scene_dedup_payload(payload)
    stable_json = json.dumps(stable_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(stable_json.encode("utf-8", errors="ignore")).hexdigest()


def _ensure_analyze_scene_dedup_table_ready() -> None:
    global _ANALYZE_SCENE_DEDUP_TABLE_READY
    if _ANALYZE_SCENE_DEDUP_TABLE_READY:
        return
    with _ANALYZE_SCENE_DEDUP_TABLE_LOCK:
        if _ANALYZE_SCENE_DEDUP_TABLE_READY:
            return
        ddl = """
        CREATE TABLE IF NOT EXISTS analyze_scene_dedup_tasks (
            dedup_key TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            task_id TEXT NOT NULL,
            updated_at REAL NOT NULL
        )
        """
        index_ddl = """
        CREATE INDEX IF NOT EXISTS idx_analyze_scene_dedup_tasks_updated_at
        ON analyze_scene_dedup_tasks (updated_at)
        """
        with engine.begin() as conn:
            conn.execute(text(ddl))
            conn.execute(text(index_ddl))
        _ANALYZE_SCENE_DEDUP_TABLE_READY = True


def _prune_analyze_scene_dedup_rows(db: Session, now_ts: float) -> None:
    global _ANALYZE_SCENE_DEDUP_LAST_PRUNE_TS
    with _ANALYZE_SCENE_DEDUP_PRUNE_LOCK:
        if (float(now_ts) - float(_ANALYZE_SCENE_DEDUP_LAST_PRUNE_TS)) < float(_ANALYZE_SCENE_DEDUP_PRUNE_INTERVAL_SECONDS):
            return
        _ANALYZE_SCENE_DEDUP_LAST_PRUNE_TS = float(now_ts)

    # Keep rows slightly longer than dedup window to reduce table churn.
    cutoff = float(now_ts) - float(max(_ANALYZE_SCENE_DEDUP_WINDOW_SECONDS * 2, 600))
    result = db.execute(
        text(
            """
            DELETE FROM analyze_scene_dedup_tasks
            WHERE updated_at < :cutoff
            """
        ),
        {"cutoff": cutoff},
    )
    pruned = int(result.rowcount or 0)
    if pruned > 0:
        logger.info(
            "[analyze_scene][dedup] pruned rows=%s cutoff_age_s=%s",
            pruned,
            int(max(_ANALYZE_SCENE_DEDUP_WINDOW_SECONDS * 2, 600)),
        )


def _get_analyze_scene_dedup_row(db: Session, dedup_key: str) -> Optional[Dict[str, Any]]:
    row = db.execute(
        text(
            """
            SELECT dedup_key, user_id, task_id, updated_at
            FROM analyze_scene_dedup_tasks
            WHERE dedup_key = :dedup_key
            """
        ),
        {"dedup_key": str(dedup_key)},
    ).mappings().first()
    return dict(row) if row else None


def _delete_analyze_scene_dedup_row(db: Session, dedup_key: str) -> None:
    db.execute(
        text(
            """
            DELETE FROM analyze_scene_dedup_tasks
            WHERE dedup_key = :dedup_key
            """
        ),
        {"dedup_key": str(dedup_key)},
    )


def _insert_analyze_scene_dedup_row_if_absent(db: Session, *, dedup_key: str, user_id: int, task_id: str, now_ts: float) -> bool:
    result = db.execute(
        text(
            """
            INSERT INTO analyze_scene_dedup_tasks (dedup_key, user_id, task_id, updated_at)
            VALUES (:dedup_key, :user_id, :task_id, :updated_at)
            ON CONFLICT(dedup_key) DO NOTHING
            """
        ),
        {
            "dedup_key": str(dedup_key),
            "user_id": int(user_id),
            "task_id": str(task_id),
            "updated_at": float(now_ts),
        },
    )
    return int(result.rowcount or 0) > 0


def _upsert_analyze_scene_dedup_row(db: Session, *, dedup_key: str, user_id: int, task_id: str, now_ts: float) -> None:
    db.execute(
        text(
            """
            INSERT INTO analyze_scene_dedup_tasks (dedup_key, user_id, task_id, updated_at)
            VALUES (:dedup_key, :user_id, :task_id, :updated_at)
            ON CONFLICT(dedup_key) DO UPDATE SET
                user_id = excluded.user_id,
                task_id = excluded.task_id,
                updated_at = excluded.updated_at
            """
        ),
        {
            "dedup_key": str(dedup_key),
            "user_id": int(user_id),
            "task_id": str(task_id),
            "updated_at": float(now_ts),
        },
    )


def _collect_analyze_scene_dedup_stats(db: Session, now_ts: Optional[float] = None) -> Dict[str, Any]:
    _ensure_analyze_scene_dedup_table_ready()
    ts_now = float(now_ts or time.time())

    total_rows = int(
        (
            db.execute(text("SELECT COUNT(*) AS cnt FROM analyze_scene_dedup_tasks")).mappings().first()
            or {}
        ).get("cnt")
        or 0
    )
    window_cutoff = ts_now - float(_ANALYZE_SCENE_DEDUP_WINDOW_SECONDS)
    window_rows = db.execute(
        text(
            """
            SELECT dedup_key, task_id, updated_at
            FROM analyze_scene_dedup_tasks
            WHERE updated_at >= :window_cutoff
            ORDER BY updated_at DESC
            LIMIT 500
            """
        ),
        {"window_cutoff": float(window_cutoff)},
    ).mappings().all()

    running_like = 0
    terminal_like = 0
    unknown_like = 0
    provisional_rows = 0
    for row in window_rows:
        task_id = str((row or {}).get("task_id") or "").strip()
        if task_id.startswith("pending-"):
            provisional_rows += 1
            continue
        info = _get_task_status(task_id) or {}
        status = str(info.get("status") or "").strip().lower()
        if status in {"pending", "running"}:
            running_like += 1
        elif status in {"completed", "failed", "canceled"}:
            terminal_like += 1
        else:
            unknown_like += 1

    stale_rows = max(0, int(total_rows) - int(len(window_rows)))
    return {
        "rows_total": int(total_rows),
        "rows_in_window": int(len(window_rows)),
        "rows_stale": int(stale_rows),
        "rows_running_like": int(running_like),
        "rows_terminal_like": int(terminal_like),
        "rows_unknown_like": int(unknown_like),
        "rows_provisional": int(provisional_rows),
        "dedup_window_seconds": int(_ANALYZE_SCENE_DEDUP_WINDOW_SECONDS),
        "prune_interval_seconds": int(_ANALYZE_SCENE_DEDUP_PRUNE_INTERVAL_SECONDS),
    }

