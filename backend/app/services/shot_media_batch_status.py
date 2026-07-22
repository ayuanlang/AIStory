# -*- coding: utf-8 -*-
"""Shot media batch status cache + episode_info persist helpers."""
from __future__ import annotations

import threading
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.time_utils import now_bj_iso
from app.models.all_models import Episode
from app.services.project_episode_utils import _episode_runtime_info_from_episode

SHOT_MEDIA_BATCH_STATUS_KEY = "shot_media_batch_status"
SHOT_MEDIA_BATCH_DEFAULT_CONCURRENCY = 3
SHOT_MEDIA_BATCH_RUNTIME_CACHE: Dict[int, Dict[str, Any]] = {}
SHOT_MEDIA_BATCH_RUNTIME_CACHE_LOCK = threading.Lock()

def _cache_shot_media_batch_status(episode_id: int, status_payload: Dict[str, Any]) -> None:
    try:
        safe_episode_id = int(episode_id)
    except Exception:
        return
    if safe_episode_id <= 0:
        return
    snapshot = dict(status_payload or {})
    with SHOT_MEDIA_BATCH_RUNTIME_CACHE_LOCK:
        SHOT_MEDIA_BATCH_RUNTIME_CACHE[safe_episode_id] = snapshot


def _get_cached_shot_media_batch_status(episode_id: int) -> Optional[Dict[str, Any]]:
    try:
        safe_episode_id = int(episode_id)
    except Exception:
        return None
    if safe_episode_id <= 0:
        return None
    with SHOT_MEDIA_BATCH_RUNTIME_CACHE_LOCK:
        payload = SHOT_MEDIA_BATCH_RUNTIME_CACHE.get(safe_episode_id)
        if isinstance(payload, dict):
            return dict(payload)
    return None


def _clear_cached_shot_media_batch_status(episode_id: int) -> None:
    try:
        safe_episode_id = int(episode_id)
    except Exception:
        return
    if safe_episode_id <= 0:
        return
    with SHOT_MEDIA_BATCH_RUNTIME_CACHE_LOCK:
        SHOT_MEDIA_BATCH_RUNTIME_CACHE.pop(safe_episode_id, None)


def _read_shot_media_batch_status(episode: Episode) -> Dict[str, Any]:
    try:
        info = _episode_runtime_info_from_episode(episode)
        payload = info.get(SHOT_MEDIA_BATCH_STATUS_KEY)
        if isinstance(payload, dict):
            return dict(payload)
    except Exception:
        pass
    return {
        "running": False,
        "mode": "keyframes",
        "total": 0,
        "completed": 0,
        "success": 0,
        "failed": 0,
        "message": "",
        "errors": [],
        "stop_requested": False,
    }


def _persist_shot_media_batch_status(db: Session, episode: Episode, status_payload: Dict[str, Any]) -> None:
    latest_episode = (
        db.query(Episode)
        .execution_options(populate_existing=True)
        .filter(Episode.id == int(episode.id))
        .first()
    )
    target_episode = latest_episode or episode

    info = _episode_runtime_info_from_episode(target_episode)
    existing_status = info.get(SHOT_MEDIA_BATCH_STATUS_KEY)
    merged_status = dict(status_payload or {})
    has_incoming_force_flag = "force_stopped" in merged_status
    has_incoming_stop_flag = "stop_requested" in merged_status

    if isinstance(existing_status, dict) and bool(existing_status.get("force_stopped")) and not has_incoming_force_flag:
        merged_status["force_stopped"] = True

    if isinstance(existing_status, dict) and bool(existing_status.get("stop_requested")) and not has_incoming_stop_flag:
        merged_status["stop_requested"] = True
        if existing_status.get("stop_requested_at") and not merged_status.get("stop_requested_at"):
            merged_status["stop_requested_at"] = existing_status.get("stop_requested_at")
        if not merged_status.get("stopped_by_user"):
            merged_status["stopped_by_user"] = bool(existing_status.get("stopped_by_user"))

    if bool(merged_status.get("force_stopped")):
        now_iso = now_bj_iso()
        merged_status["running"] = False
        merged_status["status"] = "canceled"
        merged_status["stopped_by_user"] = True
        merged_status["finished_at"] = merged_status.get("finished_at") or now_iso
        merged_status["updated_at"] = now_iso
        merged_status["message"] = merged_status.get("message") or "Force stopped"

    info[SHOT_MEDIA_BATCH_STATUS_KEY] = merged_status
    target_episode.episode_info = info
    db.add(target_episode)
    db.commit()
    _cache_shot_media_batch_status(int(target_episode.id), merged_status)


