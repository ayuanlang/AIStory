# -*- coding: utf-8 -*-
"""Helpers for generation job-pool / batch-job status payloads."""
from __future__ import annotations

import logging
import os
import re
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.time_utils import now_bj_iso
from app.models.all_models import Episode, Project, User
from app.schemas.episode_requests import EPISODE_SCENE_GEN_STATUS_KEY
from app.services.endpoint_misc import _safe_int
from app.services.project_access import (
    _require_project_access,
    _resolve_accessible_project_ids_for_user,
)
from app.services.project_episode_utils import (
    _episode_runtime_info_from_episode,
    _safe_json_dict,
)
from app.services.scene_ai_shots_batch import SCENE_AI_SHOTS_BATCH_STATUS_KEY
from app.services.shot_media_batch_status import SHOT_MEDIA_BATCH_STATUS_KEY
from app.services.soft_delete import _active_episode_clause, _active_project_clause
from app.services.generation_runtime.job_store import (
    EPISODE_SCENE_JOB_THREADS,
    EPISODE_SCENE_JOB_THREADS_LOCK,
    IMAGE_ACTIVE_SCOPE_STORE,
    IMAGE_JOB_LOCK,
    IMAGE_JOB_STORE,
    IMAGE_JOB_TASKS,
    IMAGE_SUBMIT_IDEMPOTENCY_STORE,
    SCENE_AI_SHOTS_BATCH_THREADS,
    SCENE_AI_SHOTS_BATCH_THREADS_LOCK,
    SHOT_MEDIA_BATCH_THREADS,
    SHOT_MEDIA_BATCH_THREADS_LOCK,
    VIDEO_ACTIVE_SCOPE_STORE,
    VIDEO_JOB_LOCK,
    VIDEO_JOB_STORE,
    VIDEO_JOB_TASKS,
    VIDEO_SUBMIT_IDEMPOTENCY_STORE,
    _build_generation_job_pool_cache_key,
    _clear_episode_worker,
    _clear_shot_media_batch_cancel_event,
    _image_job_file_path,
    _is_generation_job_stale,
    _job_sort_key,
    _prune_image_jobs_locked,
    _prune_video_jobs_locked,
    _read_generation_job_pool_cache,
    _read_image_job_file,
    _read_video_job_file,
    _set_image_job,
    _set_shot_media_batch_cancel_requested,
    _set_video_job,
    _video_job_file_path,
    _write_generation_job_pool_cache,
)
from app.services.generation_runtime.queue_worker import (
    _cancel_generation_task_ref,
    _generation_task_is_active,
)

logger = logging.getLogger("api_logger")


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


def collect_generation_job_pool(
    *,
    db: Session,
    current_user: User,
    kind: str = "all",
    running_only: bool = False,
    limit: int = 200,
    shot_id: Optional[str] = None,
) -> Dict[str, Any]:
    safe_kind = str(kind or "all").strip().lower()
    allowed_kinds = {
        "all",
        "image",
        "video",
        "episode-scenes",
        "episode-scripts",
        "scene-ai-shots-batch",
        "shot-media-batch",
    }
    if safe_kind not in allowed_kinds:
        raise HTTPException(status_code=400, detail="kind must be one of: all, image, video, episode-scenes, episode-scripts, scene-ai-shots-batch, shot-media-batch")

    safe_limit = max(1, min(int(limit or 200), 500))

    t0 = time.perf_counter()
    t_cache_ms = 0
    t_collect_mem_ms = 0
    t_query_projects_ms = 0
    t_query_owners_ms = 0
    t_query_episodes_ms = 0
    t_filter_sort_ms = 0
    safe_shot_id = str(shot_id or "").strip() if shot_id else None

    cache_key = _build_generation_job_pool_cache_key(
        user_id=int(getattr(current_user, "id", 0) or 0),
        is_superuser=bool(getattr(current_user, "is_superuser", False)),
        kind=f"{safe_kind}_shot_{safe_shot_id}" if safe_shot_id else safe_kind,
        running_only=bool(running_only),
        limit=safe_limit,
    )

    t_cache_start = time.perf_counter()
    cached_payload = _read_generation_job_pool_cache(cache_key)
    t_cache_ms = int((time.perf_counter() - t_cache_start) * 1000)
    if cached_payload is not None:
        logger.debug(
            "jobs.pool.timing user_id=%s kind=%s running_only=%s limit=%s cache_hit=1 total_ms=%s cache_ms=%s mem_ms=%s proj_ms=%s owner_ms=%s ep_ms=%s finalize_ms=%s total=%s",
            getattr(current_user, "id", None),
            safe_kind,
            bool(running_only),
            safe_limit,
            int((time.perf_counter() - t0) * 1000),
            t_cache_ms,
            0,
            0,
            0,
            0,
            0,
            int((cached_payload or {}).get("total") or 0),
        )
        return cached_payload

    items: List[Dict[str, Any]] = []
    final_statuses = {"succeeded", "completed", "failed", "canceled", "cancelled", "error", "stopped", "idle", "partial"}
    now_dt = datetime.utcnow()

    stale_image_job_ids: List[str] = []
    stale_video_job_ids: List[str] = []
    stale_episode_script_project_ids: List[int] = []
    stale_episode_status_updates: Dict[int, Dict[str, Any]] = {}

    t_collect_mem_start = time.perf_counter()
    if safe_kind in {"all", "image"}:
        with IMAGE_JOB_LOCK:
            _prune_image_jobs_locked()
            for job_id, payload in list(IMAGE_JOB_STORE.items()):
                if _is_generation_job_stale(dict(payload or {}), now_dt=now_dt):
                    stale_image_job_ids.append(str(job_id))
                    continue
                item = dict(payload or {})
                item["job_id"] = item.get("job_id") or job_id
                item["kind"] = "image"
                item["has_task"] = _generation_task_is_active(IMAGE_JOB_TASKS.get(job_id) or str(job_id), user_id=item.get("user_id"))
                items.append(item)

            for stale_id in stale_image_job_ids:
                IMAGE_JOB_STORE.pop(stale_id, None)
                IMAGE_JOB_TASKS.pop(stale_id, None)

            if stale_image_job_ids:
                stale_set = set(stale_image_job_ids)
                stale_scope_keys = [k for k, v in IMAGE_ACTIVE_SCOPE_STORE.items() if str(v or "") in stale_set]
                for k in stale_scope_keys:
                    IMAGE_ACTIVE_SCOPE_STORE.pop(k, None)
                stale_idempotency_keys = [k for k, v in IMAGE_SUBMIT_IDEMPOTENCY_STORE.items() if str((v or {}).get("job_id") or "") in stale_set]
                for k in stale_idempotency_keys:
                    IMAGE_SUBMIT_IDEMPOTENCY_STORE.pop(k, None)

    if stale_image_job_ids:
        for stale_id in stale_image_job_ids:
            try:
                stale_path = _image_job_file_path(stale_id)
                if os.path.exists(stale_path):
                    os.remove(stale_path)
            except Exception:
                pass

    if safe_kind in {"all", "video"}:
        with VIDEO_JOB_LOCK:
            _prune_video_jobs_locked()
            for job_id, payload in list(VIDEO_JOB_STORE.items()):
                if _is_generation_job_stale(dict(payload or {}), now_dt=now_dt):
                    stale_video_job_ids.append(str(job_id))
                    continue
                item = dict(payload or {})
                item["job_id"] = item.get("job_id") or job_id
                item["kind"] = "video"
                item["has_task"] = _generation_task_is_active(VIDEO_JOB_TASKS.get(job_id) or str(job_id), user_id=item.get("user_id"))
                items.append(item)

            for stale_id in stale_video_job_ids:
                VIDEO_JOB_STORE.pop(stale_id, None)
                VIDEO_JOB_TASKS.pop(stale_id, None)

            if stale_video_job_ids:
                stale_set = set(stale_video_job_ids)
                stale_scope_keys = [k for k, v in VIDEO_ACTIVE_SCOPE_STORE.items() if str(v or "") in stale_set]
                for k in stale_scope_keys:
                    VIDEO_ACTIVE_SCOPE_STORE.pop(k, None)
                stale_idempotency_keys = [k for k, v in VIDEO_SUBMIT_IDEMPOTENCY_STORE.items() if str((v or {}).get("job_id") or "") in stale_set]
                for k in stale_idempotency_keys:
                    VIDEO_SUBMIT_IDEMPOTENCY_STORE.pop(k, None)

    if stale_video_job_ids:
        for stale_id in stale_video_job_ids:
            try:
                stale_path = _video_job_file_path(stale_id)
                if os.path.exists(stale_path):
                    os.remove(stale_path)
            except Exception:
                pass
    t_collect_mem_ms = int((time.perf_counter() - t_collect_mem_start) * 1000)

    include_batch_kinds = {"episode-scenes", "episode-scripts", "scene-ai-shots-batch", "shot-media-batch"}
    if safe_kind in {"all", *include_batch_kinds}:
        project_rows: List[Tuple[Any, Any, Any]] = []
        t_query_projects_start = time.perf_counter()
        if current_user.is_superuser:
            project_rows = db.query(Project.id, Project.owner_id, Project.global_info).filter(_active_project_clause()).all()
        else:
            accessible_project_ids = _resolve_accessible_project_ids_for_user(db, current_user)
            if not accessible_project_ids:
                project_rows = []
            else:
                project_rows = (
                    db.query(Project.id, Project.owner_id, Project.global_info)
                    .filter(
                        Project.id.in_(accessible_project_ids),
                        _active_project_clause(),
                    )
                    .all()
                )
        t_query_projects_ms = int((time.perf_counter() - t_query_projects_start) * 1000)

        owner_ids = sorted({int(owner_id) for _, owner_id, _ in project_rows if owner_id is not None})
        owners_by_id: Dict[int, str] = {}
        if current_user.is_superuser and owner_ids:
            t_query_owners_start = time.perf_counter()
            owner_rows = db.query(User.id, User.username).filter(User.id.in_(owner_ids)).all()
            owners_by_id = {int(row_id): str(username or "") for row_id, username in owner_rows}
            t_query_owners_ms = int((time.perf_counter() - t_query_owners_start) * 1000)

        project_ids: List[int] = []
        project_owner_by_id: Dict[int, int] = {}
        project_owner_name_by_id: Dict[int, str] = {}
        for pid, owner_id, _ in project_rows:
            if pid is None:
                continue
            project_id_int = int(pid)
            project_ids.append(project_id_int)

            if owner_id is None:
                continue

            owner_id_int = int(owner_id)
            project_owner_by_id[project_id_int] = owner_id_int
            if current_user.is_superuser:
                project_owner_name_by_id[project_id_int] = owners_by_id.get(owner_id_int, "")
            elif owner_id_int == int(current_user.id):
                project_owner_name_by_id[project_id_int] = str(current_user.username or "")

        if safe_kind in {"all", "episode-scripts"}:
            for project_id, owner_id, project_global_info in project_rows:
                payload = None
                try:
                    gi = dict(project_global_info or {})
                    candidate = gi.get("episode_script_generation_status")
                    if isinstance(candidate, dict):
                        payload = dict(candidate)
                except Exception:
                    payload = None
                if not payload:
                    continue

                if _is_generation_job_stale(payload, now_dt=now_dt):
                    stale_episode_script_project_ids.append(int(project_id))
                    continue

                project_id_int = int(project_id)
                owner_id_int = int(owner_id) if owner_id is not None else None

                items.append(
                    _build_batch_job_item(
                        kind="episode-scripts",
                        job_id=f"episode-scripts:{project_id_int}",
                        payload=payload,
                        user_id=project_owner_by_id.get(project_id_int, owner_id_int),
                        username=project_owner_name_by_id.get(project_id_int),
                    )
                )

        if project_ids and safe_kind in {"all", "episode-scenes", "scene-ai-shots-batch", "shot-media-batch"}:
            t_query_episodes_start = time.perf_counter()
            episode_rows = (
                db.query(Episode.id, Episode.project_id, Episode.episode_info)
                .filter(Episode.project_id.in_(project_ids))
                .all()
            )
            t_query_episodes_ms = int((time.perf_counter() - t_query_episodes_start) * 1000)
            for episode_id, episode_project_id, episode_info_raw in episode_rows:
                if episode_id is None or episode_project_id is None:
                    continue
                episode_id_int = int(episode_id)
                episode_project_id_int = int(episode_project_id)
                owner_id = project_owner_by_id.get(episode_project_id_int)
                owner_name = project_owner_name_by_id.get(episode_project_id_int)
                info = _safe_json_dict(episode_info_raw)
                info_changed = False

                if safe_kind in {"all", "episode-scenes"}:
                    payload = info.get(EPISODE_SCENE_GEN_STATUS_KEY)
                    if isinstance(payload, dict):
                        if _is_generation_job_stale(dict(payload), now_dt=now_dt):
                            info.pop(EPISODE_SCENE_GEN_STATUS_KEY, None)
                            info_changed = True
                        else:
                            actor_user_id = payload.get("started_by_user_id") or owner_id
                            actor_username = payload.get("started_by_username") or owner_name
                            items.append(
                                _build_batch_job_item(
                                    kind="episode-scenes",
                                    job_id=f"episode-scenes:{episode_id_int}",
                                    payload=dict(payload),
                                    user_id=actor_user_id,
                                    username=actor_username,
                                )
                            )

                if safe_kind in {"all", "scene-ai-shots-batch"}:
                    payload = info.get(SCENE_AI_SHOTS_BATCH_STATUS_KEY)
                    if isinstance(payload, dict):
                        if _is_generation_job_stale(dict(payload), now_dt=now_dt):
                            info.pop(SCENE_AI_SHOTS_BATCH_STATUS_KEY, None)
                            info_changed = True
                        else:
                            actor_user_id = payload.get("started_by_user_id") or owner_id
                            actor_username = payload.get("started_by_username") or owner_name
                            items.append(
                                _build_batch_job_item(
                                    kind="scene-ai-shots-batch",
                                    job_id=f"scene-ai-shots-batch:{episode_id_int}",
                                    payload=dict(payload),
                                    user_id=actor_user_id,
                                    username=actor_username,
                                )
                            )

                if safe_kind in {"all", "shot-media-batch"}:
                    payload = info.get(SHOT_MEDIA_BATCH_STATUS_KEY)
                    if isinstance(payload, dict):
                        if _is_generation_job_stale(dict(payload), now_dt=now_dt):
                            info.pop(SHOT_MEDIA_BATCH_STATUS_KEY, None)
                            info_changed = True
                        else:
                            actor_user_id = payload.get("started_by_user_id") or owner_id
                            actor_username = payload.get("started_by_username") or owner_name
                            items.append(
                                _build_batch_job_item(
                                    kind="shot-media-batch",
                                    job_id=f"shot-media-batch:{episode_id_int}",
                                    payload=dict(payload),
                                    user_id=actor_user_id,
                                    username=actor_username,
                                )
                            )

                if info_changed:
                    stale_episode_status_updates[episode_id_int] = info

        if stale_episode_script_project_ids:
            stale_project_set = sorted(set(int(v) for v in stale_episode_script_project_ids if int(v) > 0))
            stale_projects = db.query(Project).filter(Project.id.in_(stale_project_set)).all()
            for project in stale_projects:
                gi = dict(project.global_info or {})
                if "episode_script_generation_status" in gi:
                    gi.pop("episode_script_generation_status", None)
                    project.global_info = gi
                    db.add(project)

        if stale_episode_status_updates:
            stale_episode_ids = sorted(stale_episode_status_updates.keys())
            stale_episodes = db.query(Episode).filter(Episode.id.in_(stale_episode_ids)).all()
            for episode in stale_episodes:
                next_info = stale_episode_status_updates.get(int(episode.id))
                if isinstance(next_info, dict):
                    episode.episode_info = next_info
                    db.add(episode)

        if stale_episode_script_project_ids or stale_episode_status_updates:
            try:
                db.commit()
            except Exception:
                db.rollback()

    if not current_user.is_superuser:
        items = [item for item in items if item.get("user_id") == current_user.id]

    if running_only:
        items = [item for item in items if str(item.get("status") or "").lower() not in final_statuses]

    t_filter_sort_start = time.perf_counter()
    if safe_shot_id:
        def _extract_job_shot_id(itm: Dict[str, Any]) -> str:
            if not isinstance(itm, dict):
                return ""
            metadata = itm.get("metadata") if isinstance(itm.get("metadata"), dict) else {}
            payload = itm.get("payload") if isinstance(itm.get("payload"), dict) else {}
            context = itm.get("context") if isinstance(itm.get("context"), dict) else {}
            return str(
                itm.get("shot_id")
                or itm.get("ownerShotId")
                or metadata.get("shot_id")
                or metadata.get("ownerShotId")
                or payload.get("shot_id")
                or payload.get("ownerShotId")
                or context.get("shot_id")
                or context.get("ownerShotId")
                or ""
            ).strip()

        items = [itm for itm in items if _extract_job_shot_id(itm) == safe_shot_id]

    items.sort(key=lambda item: _job_sort_key(item), reverse=True)
    items = items[:safe_limit]

    status_counts: Dict[str, int] = {}
    for item in items:
        status = str(item.get("status") or "unknown").lower()
        status_counts[status] = status_counts.get(status, 0) + 1
    t_filter_sort_ms = int((time.perf_counter() - t_filter_sort_start) * 1000)

    response_payload = {
        "total": len(items),
        "kind": safe_kind,
        "running_only": bool(running_only),
        "status_counts": status_counts,
        "items": [
            {
                k: v for k, v in item.items()
                if k not in {
                    "callback_url",
                    "provider_callback_url",
                    "provider_callback_ticket",
                    "task_scope",
                }
            }
            for item in items
        ],
    }

    _write_generation_job_pool_cache(cache_key, response_payload)

    logger.debug(
        "jobs.pool.timing user_id=%s kind=%s running_only=%s limit=%s cache_hit=0 total_ms=%s cache_ms=%s mem_ms=%s proj_ms=%s owner_ms=%s ep_ms=%s finalize_ms=%s total=%s",
        getattr(current_user, "id", None),
        safe_kind,
        bool(running_only),
        safe_limit,
        int((time.perf_counter() - t0) * 1000),
        t_cache_ms,
        t_collect_mem_ms,
        t_query_projects_ms,
        t_query_owners_ms,
        t_query_episodes_ms,
        t_filter_sort_ms,
        len(items),
    )

    return response_payload


def repair_generation_job_history(
    *,
    db: Session,
    current_user: User,
    kind: str = "all",
    older_than_minutes: int = 120,
    dry_run: bool = True,
) -> Dict[str, Any]:
    safe_kind = str(kind or "all").strip().lower()
    allowed_kinds = {"all", "episode-scenes", "episode-scripts", "scene-ai-shots-batch", "shot-media-batch"}
    if safe_kind not in allowed_kinds:
        raise HTTPException(status_code=400, detail="kind must be one of: all, episode-scenes, episode-scripts, scene-ai-shots-batch, shot-media-batch")

    safe_older_than_minutes = max(10, min(int(older_than_minutes or 120), 60 * 24 * 14))
    cutoff_dt = datetime.utcnow() - timedelta(minutes=safe_older_than_minutes)
    now_iso = now_bj_iso()

    if current_user.is_superuser:
        projects = db.query(Project).filter(_active_project_clause()).all()
    else:
        accessible_project_ids = _resolve_accessible_project_ids_for_user(db, current_user)
        if not accessible_project_ids:
            projects = []
        else:
            projects = db.query(Project).filter(
                Project.id.in_(accessible_project_ids),
                _active_project_clause(),
            ).all()

    project_ids = [int(p.id) for p in projects]
    project_owner_by_id = {int(p.id): int(p.owner_id) for p in projects if p.owner_id is not None}

    def _can_touch_project(project_id: int) -> bool:
        if current_user.is_superuser:
            return True
        owner_id = project_owner_by_id.get(int(project_id))
        return owner_id == current_user.id

    repaired = 0
    scanned = 0
    touched_projects: set[int] = set()
    touched_episodes: set[int] = set()
    samples: List[Dict[str, Any]] = []

    if safe_kind in {"all", "episode-scripts"}:
        for project in projects:
            if not _can_touch_project(int(project.id)):
                continue

            gi = dict(project.global_info or {})
            payload = gi.get("episode_script_generation_status")
            if not isinstance(payload, dict):
                continue

            scanned += 1
            normalized = _normalize_batch_job_status(payload)
            if normalized != "running":
                continue

            anchor_dt = _parse_iso_datetime(payload.get("updated_at") or payload.get("started_at") or payload.get("created_at"))
            should_repair = bool(payload.get("stop_requested")) or (anchor_dt is not None and anchor_dt <= cutoff_dt)
            if not should_repair:
                continue

            if len(samples) < 20:
                samples.append({
                    "kind": "episode-scripts",
                    "job_id": f"episode-scripts:{int(project.id)}",
                    "reason": "stop_requested" if bool(payload.get("stop_requested")) else f"stale>{safe_older_than_minutes}m",
                    "updated_at": payload.get("updated_at"),
                    "started_at": payload.get("started_at"),
                })

            if not dry_run:
                payload["running"] = False
                payload["status"] = "canceled"
                payload["stopped_by_user"] = bool(payload.get("stop_requested") or payload.get("stopped_by_user"))
                payload["finished_at"] = payload.get("finished_at") or now_iso
                payload["updated_at"] = now_iso
                payload["message"] = "Repaired stale historical job"
                gi["episode_script_generation_status"] = payload
                project.global_info = gi
                db.add(project)
                repaired += 1
                touched_projects.add(int(project.id))

    if project_ids and safe_kind in {"all", "episode-scenes", "scene-ai-shots-batch", "shot-media-batch"}:
        episodes = db.query(Episode).filter(
            Episode.project_id.in_(project_ids),
            _active_episode_clause(),
        ).all()

        def _maybe_repair_episode_status(episode: Episode, status_key: str, kind_name: str) -> None:
            nonlocal repaired, scanned
            if not _can_touch_project(int(episode.project_id)):
                return

            info = _episode_runtime_info_from_episode(episode)
            payload = info.get(status_key)
            if not isinstance(payload, dict):
                return

            scanned += 1
            normalized = _normalize_batch_job_status(payload)
            if normalized != "running":
                return

            anchor_dt = _parse_iso_datetime(payload.get("updated_at") or payload.get("started_at") or payload.get("created_at"))
            should_repair = bool(payload.get("stop_requested")) or (anchor_dt is not None and anchor_dt <= cutoff_dt)
            if not should_repair:
                return

            if len(samples) < 20:
                samples.append({
                    "kind": kind_name,
                    "job_id": f"{kind_name}:{int(episode.id)}",
                    "reason": "stop_requested" if bool(payload.get("stop_requested")) else f"stale>{safe_older_than_minutes}m",
                    "updated_at": payload.get("updated_at"),
                    "started_at": payload.get("started_at"),
                })

            if not dry_run:
                payload["running"] = False
                payload["status"] = "canceled"
                payload["stopped_by_user"] = bool(payload.get("stop_requested") or payload.get("stopped_by_user"))
                payload["finished_at"] = payload.get("finished_at") or now_iso
                payload["updated_at"] = now_iso
                payload["message"] = "Repaired stale historical job"
                info[status_key] = payload
                episode.episode_info = info
                db.add(episode)
                repaired += 1
                touched_episodes.add(int(episode.id))

        for episode in episodes:
            if safe_kind in {"all", "episode-scenes"}:
                _maybe_repair_episode_status(episode, EPISODE_SCENE_GEN_STATUS_KEY, "episode-scenes")
            if safe_kind in {"all", "scene-ai-shots-batch"}:
                _maybe_repair_episode_status(episode, SCENE_AI_SHOTS_BATCH_STATUS_KEY, "scene-ai-shots-batch")
            if safe_kind in {"all", "shot-media-batch"}:
                _maybe_repair_episode_status(episode, SHOT_MEDIA_BATCH_STATUS_KEY, "shot-media-batch")

    if not dry_run and (touched_projects or touched_episodes):
        db.commit()

    return {
        "ok": True,
        "dry_run": bool(dry_run),
        "kind": safe_kind,
        "older_than_minutes": safe_older_than_minutes,
        "scanned": scanned,
        "repaired": repaired if not dry_run else len(samples),
        "touched_projects": len(touched_projects),
        "touched_episodes": len(touched_episodes),
        "samples": samples,
    }


def stop_generation_job(
    *,
    db: Session,
    current_user: User,
    kind: str,
    job_id: str,
    force: bool = False,
) -> Dict[str, Any]:
    safe_kind = str(kind or "").strip().lower()
    if safe_kind not in {"image", "video", "episode-scenes", "episode-scripts", "scene-ai-shots-batch", "shot-media-batch"}:
        raise HTTPException(status_code=400, detail="kind must be one of: image, video, episode-scenes, episode-scripts, scene-ai-shots-batch, shot-media-batch")

    if safe_kind in {"episode-scenes", "scene-ai-shots-batch", "shot-media-batch", "episode-scripts"}:
        target_id = _extract_target_id_from_job_id(job_id)
        if not target_id:
            raise HTTPException(status_code=400, detail="Invalid job_id")

        if safe_kind == "episode-scripts":
            project = db.query(Project).filter(Project.id == target_id).first()
            if not project:
                raise HTTPException(status_code=404, detail="Job not found")
            if not bool(getattr(current_user, "is_superuser", False)):
                _require_project_access(db, int(project.id), current_user)

            gi = dict(project.global_info or {})
            removed = "episode_script_generation_status" in gi
            gi.pop("episode_script_generation_status", None)
            project.global_info = gi
            db.add(project)
            db.commit()

            return {
                "ok": True,
                "kind": safe_kind,
                "job_id": job_id,
                "status": "canceled",
                "deleted": bool(removed),
                "message": "Force removed",
            }

        episode = db.query(Episode).filter(Episode.id == target_id).first()
        if not episode:
            raise HTTPException(status_code=404, detail="Job not found")
        if not bool(getattr(current_user, "is_superuser", False)):
            _require_project_access(db, int(episode.project_id), current_user)

        if safe_kind == "episode-scenes":
            status_key = EPISODE_SCENE_GEN_STATUS_KEY
        elif safe_kind == "scene-ai-shots-batch":
            status_key = SCENE_AI_SHOTS_BATCH_STATUS_KEY
        else:
            status_key = SHOT_MEDIA_BATCH_STATUS_KEY

        info = _episode_runtime_info_from_episode(episode)
        removed = status_key in info
        info.pop(status_key, None)
        episode.episode_info = info
        db.add(episode)
        db.commit()

        if safe_kind == "episode-scenes":
            _clear_episode_worker(EPISODE_SCENE_JOB_THREADS, EPISODE_SCENE_JOB_THREADS_LOCK, int(episode.id))
        elif safe_kind == "scene-ai-shots-batch":
            _clear_episode_worker(SCENE_AI_SHOTS_BATCH_THREADS, SCENE_AI_SHOTS_BATCH_THREADS_LOCK, int(episode.id))
        if safe_kind == "shot-media-batch":
            _set_shot_media_batch_cancel_requested(int(episode.id))
            _clear_episode_worker(SHOT_MEDIA_BATCH_THREADS, SHOT_MEDIA_BATCH_THREADS_LOCK, int(episode.id))
            _clear_shot_media_batch_cancel_event(int(episode.id))

        return {
            "ok": True,
            "kind": safe_kind,
            "job_id": job_id,
            "status": "canceled",
            "deleted": bool(removed),
            "message": "Force removed",
        }

    if safe_kind == "image":
        lock = IMAGE_JOB_LOCK
        store = IMAGE_JOB_STORE
        task_store = IMAGE_JOB_TASKS
        read_file_func = _read_image_job_file
        set_job_func = _set_image_job
    else:
        lock = VIDEO_JOB_LOCK
        store = VIDEO_JOB_STORE
        task_store = VIDEO_JOB_TASKS
        read_file_func = _read_video_job_file
        set_job_func = _set_video_job

    with lock:
        job = dict(store.get(job_id) or {})
        task_ref = task_store.get(job_id)

    if not job:
        file_job = read_file_func(job_id)
        if file_job:
            with lock:
                store[job_id] = dict(file_job)
            job = dict(file_job)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    owner_id = job.get("user_id")
    if not current_user.is_superuser and owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    status = str(job.get("status") or "").lower()
    if not force and status in {"succeeded", "failed", "canceled", "cancelled", "error"}:
        return {
            "ok": True,
            "kind": safe_kind,
            "job_id": job_id,
            "status": status,
            "message": "Job already finished",
        }

    set_job_func(
        job_id,
        status="canceled",
        finished_at=now_bj_iso(),
        error="Force stopped by user" if force else "Cancelled by user",
    )

    _cancel_generation_task_ref(
        task_ref or job_id,
        user_id=owner_id,
        reason="Force stopped by user" if force else "Cancelled by user",
    )

    # Force: also remove task ref from store to prevent further polling
    if force:
        try:
            with lock:
                task_stores_ref = task_store
                if job_id in task_stores_ref:
                    del task_stores_ref[job_id]
        except Exception:
            pass

    return {
        "ok": True,
        "kind": safe_kind,
        "job_id": job_id,
        "status": "canceled",
        "message": "Force stopped" if force else "Stop requested",
    }


def delete_generation_job(
    *,
    db: Session,
    current_user: User,
    kind: str,
    job_id: str,
) -> Dict[str, Any]:
    is_superuser = bool(getattr(current_user, "is_superuser", False))

    safe_kind = str(kind or "").strip().lower()
    if safe_kind not in {"image", "video", "episode-scenes", "episode-scripts", "scene-ai-shots-batch", "shot-media-batch"}:
        raise HTTPException(status_code=400, detail="kind must be one of: image, video, episode-scenes, episode-scripts, scene-ai-shots-batch, shot-media-batch")

    target_id = _extract_target_id_from_job_id(job_id)

    if safe_kind in {"episode-scenes", "scene-ai-shots-batch", "shot-media-batch", "episode-scripts"}:
        if not target_id:
            raise HTTPException(status_code=400, detail="Invalid job_id")

        if safe_kind == "episode-scripts":
            project = db.query(Project).filter(Project.id == target_id).first()
            if not project:
                raise HTTPException(status_code=404, detail="Job not found")
            gi = dict(project.global_info or {})
            if "episode_script_generation_status" not in gi:
                raise HTTPException(status_code=404, detail="Job not found")
            payload = gi.get("episode_script_generation_status")
            actor_user_id = None
            if isinstance(payload, dict):
                raw_uid = payload.get("started_by_user_id") or payload.get("user_id") or project.owner_id
                try:
                    actor_user_id = int(raw_uid) if raw_uid is not None else None
                except Exception:
                    actor_user_id = None
            if not is_superuser and actor_user_id != int(current_user.id):
                raise HTTPException(status_code=403, detail="Not authorized to delete this job")
            gi.pop("episode_script_generation_status", None)
            project.global_info = gi
            db.add(project)
            db.commit()
            return {
                "ok": True,
                "kind": safe_kind,
                "job_id": job_id,
                "deleted": True,
                "message": "Deleted from job history",
            }

        episode = db.query(Episode).filter(Episode.id == target_id).first()
        if not episode:
            raise HTTPException(status_code=404, detail="Job not found")

        if safe_kind == "episode-scenes":
            status_key = EPISODE_SCENE_GEN_STATUS_KEY
        elif safe_kind == "scene-ai-shots-batch":
            status_key = SCENE_AI_SHOTS_BATCH_STATUS_KEY
        else:
            status_key = SHOT_MEDIA_BATCH_STATUS_KEY

        info = _episode_runtime_info_from_episode(episode)
        if status_key not in info:
            raise HTTPException(status_code=404, detail="Job not found")

        payload = info.get(status_key)
        actor_user_id = None
        if isinstance(payload, dict):
            raw_uid = payload.get("started_by_user_id") or payload.get("user_id")
            if raw_uid is None:
                try:
                    project = db.query(Project).filter(Project.id == int(episode.project_id)).first()
                    raw_uid = project.owner_id if project else None
                except Exception:
                    raw_uid = None
            try:
                actor_user_id = int(raw_uid) if raw_uid is not None else None
            except Exception:
                actor_user_id = None
        if not is_superuser and actor_user_id != int(current_user.id):
            raise HTTPException(status_code=403, detail="Not authorized to delete this job")

        info.pop(status_key, None)
        episode.episode_info = info
        db.add(episode)
        db.commit()

        if safe_kind == "shot-media-batch":
            _clear_shot_media_batch_cancel_event(int(episode.id))

        return {
            "ok": True,
            "kind": safe_kind,
            "job_id": job_id,
            "deleted": True,
            "message": "Deleted from job history",
        }

    if safe_kind == "image":
        lock = IMAGE_JOB_LOCK
        store = IMAGE_JOB_STORE
        task_store = IMAGE_JOB_TASKS
        active_scope_store = IMAGE_ACTIVE_SCOPE_STORE
        idempotency_store = IMAGE_SUBMIT_IDEMPOTENCY_STORE
        file_path = _image_job_file_path(job_id)
    else:
        lock = VIDEO_JOB_LOCK
        store = VIDEO_JOB_STORE
        task_store = VIDEO_JOB_TASKS
        active_scope_store = VIDEO_ACTIVE_SCOPE_STORE
        idempotency_store = VIDEO_SUBMIT_IDEMPOTENCY_STORE
        file_path = _video_job_file_path(job_id)

    task_ref = None
    file_payload = None
    with lock:
        has_store_item = job_id in store
        if not has_store_item:
            file_payload = _read_image_job_file(job_id) if safe_kind == "image" else _read_video_job_file(job_id)
            if not file_payload:
                raise HTTPException(status_code=404, detail="Job not found")

        live_payload = dict(store.get(job_id) or {})
        owner_raw = live_payload.get("user_id") if live_payload else None
        if owner_raw is None and isinstance(file_payload, dict):
            owner_raw = file_payload.get("user_id")
        try:
            owner_id = int(owner_raw) if owner_raw is not None else None
        except Exception:
            owner_id = None
        if not is_superuser and owner_id != int(current_user.id):
            raise HTTPException(status_code=403, detail="Not authorized to delete this job")

        task_ref = task_store.pop(job_id, None)
        store.pop(job_id, None)

        stale_scope_keys = [key for key, value in active_scope_store.items() if str(value or "") == job_id]
        for key in stale_scope_keys:
            active_scope_store.pop(key, None)

        stale_idempotency_keys = [key for key, value in idempotency_store.items() if str((value or {}).get("job_id") or "") == job_id]
        for key in stale_idempotency_keys:
            idempotency_store.pop(key, None)

    _cancel_generation_task_ref(task_ref or job_id, user_id=owner_id, reason="Deleted from job history")

    try:
        from app.services.generation_task_queue import delete_generation_job_state

        delete_generation_job_state(kind=safe_kind, job_id=job_id)
    except Exception:
        pass

    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception:
        pass

    return {
        "ok": True,
        "kind": safe_kind,
        "job_id": job_id,
        "deleted": True,
        "message": "Deleted from job history",
    }


def stop_all_generation_jobs(
    *,
    db: Session,
    current_user: User,
    kind: str = "all",
    force: bool = False,
) -> Dict[str, Any]:
    safe_kind = str(kind or "all").strip().lower()
    allowed_kinds = {"all", "image", "video", "episode-scenes", "episode-scripts", "scene-ai-shots-batch", "shot-media-batch"}
    if safe_kind not in allowed_kinds:
        raise HTTPException(status_code=400, detail="kind must be one of: all, image, video, episode-scenes, episode-scripts, scene-ai-shots-batch, shot-media-batch")

    now_iso = now_bj_iso()
    stopped = 0
    touched: List[str] = []

    def _can_access_project(project_id: int) -> bool:
        if current_user.is_superuser:
            return True
        try:
            _require_project_access(db, int(project_id), current_user)
            return True
        except Exception:
            return False

    if safe_kind in {"all", "image"}:
        with IMAGE_JOB_LOCK:
            _prune_image_jobs_locked()
            if force:
                image_ids = list(IMAGE_JOB_STORE.keys())
            else:
                image_ids = [jid for jid, payload in IMAGE_JOB_STORE.items() if str((payload or {}).get("status") or "").lower() in {"queued", "running"}]
        for jid in image_ids:
            with IMAGE_JOB_LOCK:
                payload = dict(IMAGE_JOB_STORE.get(jid) or {})
                task_ref = IMAGE_JOB_TASKS.get(jid)
            owner_id = payload.get("user_id")
            if not current_user.is_superuser and owner_id != current_user.id:
                continue
            _set_image_job(jid, status="canceled", finished_at=now_iso, error="Cancelled by stop-all")
            _cancel_generation_task_ref(task_ref or jid, user_id=owner_id, reason="Cancelled by stop-all")
            stopped += 1
            touched.append(f"image:{jid}")

    if safe_kind in {"all", "video"}:
        with VIDEO_JOB_LOCK:
            _prune_video_jobs_locked()
            if force:
                video_ids = list(VIDEO_JOB_STORE.keys())
            else:
                video_ids = [jid for jid, payload in VIDEO_JOB_STORE.items() if str((payload or {}).get("status") or "").lower() in {"queued", "running"}]
        for jid in video_ids:
            with VIDEO_JOB_LOCK:
                payload = dict(VIDEO_JOB_STORE.get(jid) or {})
                task_ref = VIDEO_JOB_TASKS.get(jid)
            owner_id = payload.get("user_id")
            if not current_user.is_superuser and owner_id != current_user.id:
                continue
            _set_video_job(jid, status="canceled", finished_at=now_iso, error="Cancelled by stop-all")
            _cancel_generation_task_ref(task_ref or jid, user_id=owner_id, reason="Cancelled by stop-all")
            stopped += 1
            touched.append(f"video:{jid}")

    if safe_kind in {"all", "image", "video"}:
        try:
            from app.services.generation_task_queue import cancel_generation_tasks

            queue_total = 0
            owner_filter = None if current_user.is_superuser else int(current_user.id)
            if safe_kind == "image":
                queue_total += int(
                    cancel_generation_tasks(
                        kind="image",
                        user_id=owner_filter,
                        reason="Cancelled by stop-all",
                    )
                    or 0
                )
            elif safe_kind == "video":
                queue_total += int(
                    cancel_generation_tasks(
                        kind="video",
                        user_id=owner_filter,
                        reason="Cancelled by stop-all",
                    )
                    or 0
                )
            else:
                queue_total += int(
                    cancel_generation_tasks(
                        kind="image",
                        user_id=owner_filter,
                        reason="Cancelled by stop-all",
                    )
                    or 0
                )
                queue_total += int(
                    cancel_generation_tasks(
                        kind="video",
                        user_id=owner_filter,
                        reason="Cancelled by stop-all",
                    )
                    or 0
                )
            if queue_total > 0:
                stopped += queue_total
                touched.append(f"queue:{safe_kind}:{queue_total}")
        except Exception as e:
            logger.warning("stop-all queue cleanup skipped | kind=%s err=%s", safe_kind, e)

    if safe_kind in {"all", "episode-scripts"}:
        projects = db.query(Project).filter(_active_project_clause()).all() if current_user.is_superuser else db.query(Project).filter(
            Project.owner_id == current_user.id,
            _active_project_clause(),
        ).all()
        for project in projects:
            if not _can_access_project(int(project.id)):
                continue
            gi = dict(project.global_info or {})
            payload = gi.get("episode_script_generation_status")
            if not isinstance(payload, dict):
                continue
            if (not force) and str(payload.get("status") or "").lower() in {"succeeded", "completed", "failed", "canceled", "cancelled", "error", "stopped", "idle", "partial"} and not bool(payload.get("running")):
                continue
            gi.pop("episode_script_generation_status", None)
            project.global_info = gi
            db.add(project)
            stopped += 1
            touched.append(f"episode-scripts:{int(project.id)}")

    if safe_kind in {"all", "episode-scenes", "scene-ai-shots-batch", "shot-media-batch"}:
        episodes = db.query(Episode).filter(_active_episode_clause()).all()
        for episode in episodes:
            if not episode.project_id:
                continue
            if not _can_access_project(int(episode.project_id)):
                continue
            info = _episode_runtime_info_from_episode(episode)
            key_pairs = []
            if safe_kind in {"all", "episode-scenes"}:
                key_pairs.append((EPISODE_SCENE_GEN_STATUS_KEY, "episode-scenes"))
            if safe_kind in {"all", "scene-ai-shots-batch"}:
                key_pairs.append((SCENE_AI_SHOTS_BATCH_STATUS_KEY, "scene-ai-shots-batch"))
            if safe_kind in {"all", "shot-media-batch"}:
                key_pairs.append((SHOT_MEDIA_BATCH_STATUS_KEY, "shot-media-batch"))

            changed = False
            for status_key, kind_name in key_pairs:
                payload = info.get(status_key)
                if not isinstance(payload, dict):
                    continue
                if (not force) and str(payload.get("status") or "").lower() in {"succeeded", "completed", "failed", "canceled", "cancelled", "error", "stopped", "idle", "partial"} and not bool(payload.get("running")):
                    continue
                info.pop(status_key, None)
                changed = True
                stopped += 1
                touched.append(f"{kind_name}:{int(episode.id)}")
                if kind_name == "episode-scenes":
                    _clear_episode_worker(EPISODE_SCENE_JOB_THREADS, EPISODE_SCENE_JOB_THREADS_LOCK, int(episode.id))
                elif kind_name == "scene-ai-shots-batch":
                    _clear_episode_worker(SCENE_AI_SHOTS_BATCH_THREADS, SCENE_AI_SHOTS_BATCH_THREADS_LOCK, int(episode.id))
                if kind_name == "shot-media-batch":
                    _set_shot_media_batch_cancel_requested(int(episode.id))
                    _clear_episode_worker(SHOT_MEDIA_BATCH_THREADS, SHOT_MEDIA_BATCH_THREADS_LOCK, int(episode.id))
                    _clear_shot_media_batch_cancel_event(int(episode.id))

            if changed:
                episode.episode_info = info
                db.add(episode)

    db.commit()

    return {
        "ok": True,
        "kind": safe_kind,
        "force": bool(force),
        "stopped": stopped,
        "items": touched[:200],
        "message": "Stop-all requested",
    }

