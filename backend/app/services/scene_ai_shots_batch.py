# -*- coding: utf-8 -*-
"""Episode-scoped scene AI shots batch status + worker helpers."""
from __future__ import annotations

import asyncio
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.time_utils import now_bj_iso
from app.db.session import SessionLocal
from app.models.all_models import Episode, Scene, Shot, User
from app.schemas.user_auth import USER_ACTIVE_LEVEL_DEFAULT, resolve_user_batch_parallel_limit as _resolve_user_batch_parallel_limit
from app.services.db_session_utils import _release_db_connection, _snapshot_user_principal
from app.services.endpoint_misc import _log_batch_sys_event
from app.services.generation_runtime.job_store import (
    SCENE_AI_SHOTS_BATCH_THREADS,
    SCENE_AI_SHOTS_BATCH_THREADS_LOCK,
    _clear_episode_worker,
    _register_episode_worker,
)
from app.services.project_episode_utils import _episode_runtime_info_from_episode
from app.services.scene_no_utils import _sort_scenes_by_scene_no
from app.services.soft_delete import (
    _active_episode_clause,
    _active_scene_clause,
    _active_shot_clause,
)

logger = logging.getLogger("api_logger")

SCENE_AI_SHOTS_BATCH_STATUS_KEY = "scene_ai_shots_batch_status"
SCENE_AI_SHOTS_BATCH_PER_SCENE_TIMEOUT_SEC = 600
SCENE_AI_SHOTS_BATCH_DEFAULT_CONCURRENCY = 3
SCENE_AI_SHOTS_BATCH_STATUS_ERROR_LIMIT = max(5, int(os.getenv("SCENE_AI_SHOTS_BATCH_STATUS_ERROR_LIMIT", "20") or 20))
SCENE_AI_SHOTS_BATCH_STATUS_ERROR_MAX_CHARS = max(80, int(os.getenv("SCENE_AI_SHOTS_BATCH_STATUS_ERROR_MAX_CHARS", "240") or 240))


def _read_scene_ai_shots_batch_status(episode: Episode) -> Dict[str, Any]:
    try:
        info = _episode_runtime_info_from_episode(episode)
        payload = info.get(SCENE_AI_SHOTS_BATCH_STATUS_KEY)
        if isinstance(payload, dict):
            return dict(payload)
    except Exception:
        pass
    return {
        "running": False,
        "total": 0,
        "completed": 0,
        "success": 0,
        "failed": 0,
        "current_scene_id": None,
        "current_scene_label": "",
        "message": "",
        "errors": [],
    }


def _persist_scene_ai_shots_batch_status(db: Session, episode: Episode, status_payload: Dict[str, Any]) -> None:
    latest_episode = (
        db.query(Episode)
        .execution_options(populate_existing=True)
        .filter(Episode.id == int(episode.id))
        .first()
    )
    target_episode = latest_episode or episode

    info = _episode_runtime_info_from_episode(target_episode)
    existing_status = info.get(SCENE_AI_SHOTS_BATCH_STATUS_KEY)
    merged_status = dict(status_payload or {})
    has_incoming_force_flag = "force_stopped" in merged_status

    if isinstance(existing_status, dict) and bool(existing_status.get("force_stopped")) and not has_incoming_force_flag:
        merged_status["force_stopped"] = True

    if bool(merged_status.get("force_stopped")):
        now_iso = now_bj_iso()
        merged_status["running"] = False
        merged_status["status"] = "canceled"
        merged_status["stopped_by_user"] = True
        merged_status["finished_at"] = merged_status.get("finished_at") or now_iso
        merged_status["updated_at"] = now_iso

    info[SCENE_AI_SHOTS_BATCH_STATUS_KEY] = merged_status
    target_episode.episode_info = info
    db.add(target_episode)
    db.commit()


def _build_scene_ai_shots_batch_status_response(status_payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(status_payload or {})
    response_payload: Dict[str, Any] = {
        "running": bool(payload.get("running")),
        "status": str(payload.get("status") or ("running" if payload.get("running") else "idle")).strip().lower(),
        "project_id": payload.get("project_id"),
        "episode_id": payload.get("episode_id"),
        "started_by_user_id": payload.get("started_by_user_id"),
        "started_by_username": payload.get("started_by_username"),
        "max_concurrency": payload.get("max_concurrency"),
        "total": int(payload.get("total") or 0),
        "completed": int(payload.get("completed") or 0),
        "success": int(payload.get("success") or 0),
        "failed": int(payload.get("failed") or 0),
        "current_scene_id": payload.get("current_scene_id"),
        "current_scene_label": str(payload.get("current_scene_label") or "").strip(),
        "message": str(payload.get("message") or "").strip()[:512],
        "stop_requested": bool(payload.get("stop_requested")),
        "force_stopped": bool(payload.get("force_stopped")),
        "stopped_by_user": bool(payload.get("stopped_by_user")),
        "started_at": payload.get("started_at"),
        "updated_at": payload.get("updated_at"),
        "finished_at": payload.get("finished_at"),
    }

    raw_errors = payload.get("errors") or []
    safe_errors: List[str] = []
    for item in (raw_errors if isinstance(raw_errors, list) else []):
        txt = str(item or "").strip()
        if not txt:
            continue
        safe_errors.append(txt[:SCENE_AI_SHOTS_BATCH_STATUS_ERROR_MAX_CHARS])
        if len(safe_errors) >= SCENE_AI_SHOTS_BATCH_STATUS_ERROR_LIMIT:
            break
    response_payload["errors"] = safe_errors
    response_payload["errors_total"] = len(raw_errors) if isinstance(raw_errors, list) else len(safe_errors)
    response_payload["errors_truncated"] = bool(response_payload["errors_total"] > len(safe_errors))
    response_payload["poll_interval_ms"] = 2500
    return response_payload


def _run_scene_ai_shots_batch_item(scene_id: int, episode_id: int, user_id: int, function_name: Optional[str] = None, system_api_id: Optional[int] = None) -> Dict[str, Any]:
    item_db = SessionLocal()
    try:
        scene = (
            item_db.query(Scene)
            .filter(
                Scene.id == scene_id,
                Scene.episode_id == episode_id,
                _active_scene_clause(),
            )
            .first()
        )
        user = item_db.query(User).filter(User.id == user_id).first()
        if not scene or not user:
            raise RuntimeError("Scene or user not found (missing or soft-deleted)")
        user_principal = _snapshot_user_principal(user)

        scene_label = str(scene.scene_no or scene.scene_name or f"#{scene_id}")
        # Match GET /scenes/{id}/shots visibility (episode-scoped); ignore orphans.
        existing_shot_count = (
            item_db.query(Shot)
            .filter(
                Shot.scene_id == scene_id,
                Shot.episode_id == int(episode_id),
                _active_shot_clause(),
            )
            .count()
        )
        if existing_shot_count > 0:
            logger.info(
                "[scene_ai_shots_batch] abandon scene already has shots | scene_id=%s count=%s",
                scene_id,
                existing_shot_count,
            )
            return {
                "scene_id": int(scene_id),
                "scene_label": scene_label,
                "ok": True,
                "skipped": True,
                "reason": f"scene already has {existing_shot_count} shot(s); import abandoned",
            }
        _release_db_connection(item_db, "scene_ai_shots_batch_item")
        # Lazy import avoids circular import with workspace.shot_ai_generation routes.
        from app.api.routers.workspace.shot_ai_generation import (  # noqa: WPS433
            AIShotGenRequest,
            AnalysisContent,
            ai_generate_shots,
            apply_scene_ai_result,
        )
        generated = asyncio.run(
            asyncio.wait_for(
                ai_generate_shots(scene_id=scene_id, req=AIShotGenRequest(function_name=function_name, system_api_id=system_api_id), db=item_db, current_user=user_principal),
                timeout=SCENE_AI_SHOTS_BATCH_PER_SCENE_TIMEOUT_SEC,
            )
        )
        generated_rows = generated.get("content") if isinstance(generated, dict) else []
        if not isinstance(generated_rows, list) or len(generated_rows) == 0:
            raise RuntimeError("No parsed rows returned")

        apply_scene_ai_result(
            scene_id=scene_id,
            data=AnalysisContent(content=generated_rows, replace_existing=False),
            db=item_db,
            current_user=user_principal,
        )
        return {
            "scene_id": int(scene_id),
            "scene_label": scene_label,
            "ok": True,
        }
    except asyncio.TimeoutError:
        scene_label = str((scene.scene_no if 'scene' in locals() and scene else None) or (scene.scene_name if 'scene' in locals() and scene else None) or f"#{scene_id}")
        return {
            "scene_id": int(scene_id),
            "scene_label": scene_label,
            "ok": False,
            "error": f"scene processing exceeded {SCENE_AI_SHOTS_BATCH_PER_SCENE_TIMEOUT_SEC}s timeout",
        }
    except Exception as e:
        scene_label = str((scene.scene_no if 'scene' in locals() and scene else None) or (scene.scene_name if 'scene' in locals() and scene else None) or f"#{scene_id}")
        return {
            "scene_id": int(scene_id),
            "scene_label": scene_label,
            "ok": False,
            "error": str(e),
        }
    finally:
        item_db.close()


def _run_scene_ai_shots_batch_job(episode_id: int, scene_ids: List[int], user_id: int, batch_max_concurrency: int, function_name: Optional[str] = None, system_api_id: Optional[int] = None) -> None:
    try:
        with SessionLocal() as init_db:
            episode = (
                init_db.query(Episode)
                .filter(Episode.id == episode_id, _active_episode_clause())
                .first()
            )
            user = init_db.query(User).filter(User.id == user_id).first()
            if not episode or not user:
                return

            user_name = str(user.username or f"user_{user_id}")
            project_id = int(episode.project_id)
            scene_label_map: Dict[int, str] = {}
            for sid in scene_ids:
                sc = (
                    init_db.query(Scene)
                    .filter(
                        Scene.id == sid,
                        Scene.episode_id == episode_id,
                        _active_scene_clause(),
                    )
                    .first()
                )
                if sc:
                    scene_label_map[sid] = str(sc.scene_no or sc.scene_name or f"#{sid}")

        job_id = f"scene-ai-shots-batch:{int(episode_id)}"

        total = len(scene_ids)
        completed = 0
        success = 0
        failed = 0
        errors: List[str] = []

        def _read_latest_episode(session: Session) -> Optional[Episode]:
            return (
                session.query(Episode)
                .execution_options(populate_existing=True)
                .filter(Episode.id == episode_id, _active_episode_clause())
                .first()
            )

        def _stop_requested() -> bool:
            with SessionLocal() as status_db:
                latest_episode = _read_latest_episode(status_db)
                if not latest_episode:
                    return True
                latest_status = _read_scene_ai_shots_batch_status(latest_episode)
                return bool(latest_status.get("stop_requested") or latest_status.get("force_stopped"))

        effective_batch_max_concurrency = _resolve_user_batch_parallel_limit(
            batch_max_concurrency,
            default=SCENE_AI_SHOTS_BATCH_DEFAULT_CONCURRENCY,
        )
        next_scene_index = 0
        active_future_map: Dict[Any, int] = {}

        def _active_scene_ids() -> List[int]:
            return list(active_future_map.values())

        def _persist_active_scene_status(latest_message: Optional[str] = None) -> None:
            with SessionLocal() as status_db:
                latest_episode = _read_latest_episode(status_db)
                if not latest_episode:
                    return
                latest_status = _read_scene_ai_shots_batch_status(latest_episode)
                active_scene_ids = _active_scene_ids()
                active_scene_labels = [scene_label_map.get(sid) or f"#{sid}" for sid in active_scene_ids]
                latest_status["current_scene_id"] = active_scene_ids[0] if len(active_scene_ids) == 1 else None
                latest_status["current_scene_label"] = " / ".join(active_scene_labels)
                latest_status["current_scene_started_at"] = now_bj_iso() if active_scene_ids else latest_status.get("current_scene_started_at")
                latest_status["updated_at"] = now_bj_iso()
                if latest_message is not None:
                    latest_status["message"] = latest_message
                elif active_scene_labels:
                    latest_status["message"] = (
                        f"Processing scenes {', '.join(active_scene_labels)}..."
                        if len(active_scene_labels) > 1
                        else f"Processing scene {active_scene_labels[0]}..."
                    )
                _persist_scene_ai_shots_batch_status(status_db, latest_episode, latest_status)

        def _submit_next_scene(executor: ThreadPoolExecutor) -> bool:
            nonlocal next_scene_index
            if next_scene_index >= len(scene_ids):
                return False
            sid = scene_ids[next_scene_index]
            next_scene_index += 1
            active_future_map[executor.submit(_run_scene_ai_shots_batch_item, sid, episode_id, user_id, function_name, system_api_id)] = sid
            return True

        max_workers = max(1, min(effective_batch_max_concurrency, total or 1))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            while len(active_future_map) < max_workers and _submit_next_scene(executor):
                pass

            if _stop_requested():
                with SessionLocal() as status_db:
                    episode = _read_latest_episode(status_db)
                    if episode:
                        latest = _read_scene_ai_shots_batch_status(episode)
                        latest["running"] = False
                        latest["completed"] = completed
                        latest["success"] = success
                        latest["failed"] = failed
                        latest["errors"] = errors
                        latest["finished_at"] = now_bj_iso()
                        latest["stopped_by_user"] = True
                        latest["message"] = "Stopped by user request"
                        _persist_scene_ai_shots_batch_status(status_db, episode, latest)
                        _log_batch_sys_event(
                            kind="scene-ai-shots-batch",
                            phase="end",
                            user_id=user_id,
                            user_name=user_name,
                            project_id=project_id,
                            episode_id=episode_id,
                            job_id=job_id,
                            result="canceled",
                            message="Stopped by user request",
                            extra={"completed": completed, "success": success, "failed": failed},
                        )
                return
            _persist_active_scene_status()

            while active_future_map:
                completed_future = next(as_completed(list(active_future_map.keys())))
                sid = active_future_map.pop(completed_future)
                scene_label = scene_label_map.get(sid) or f"#{sid}"
                try:
                    result = completed_future.result()
                except Exception as e:
                    result = {
                        "scene_id": sid,
                        "scene_label": scene_label,
                        "ok": False,
                        "error": str(e),
                    }

                if bool(result.get("ok")):
                    success += 1
                    _log_batch_sys_event(
                        kind="scene-ai-shots-batch",
                        phase="item",
                        user_id=user_id,
                        user_name=user_name,
                        project_id=project_id,
                        episode_id=episode_id,
                        job_id=job_id,
                        item_id=sid,
                        item_label=result.get("scene_label") or scene_label,
                        result="success",
                        message="Scene AI shots generated",
                    )
                else:
                    failed += 1
                    error_message = str(result.get("error") or "Unknown error")
                    errors.append(f"{result.get('scene_label') or scene_label}: {error_message}")
                    _log_batch_sys_event(
                        kind="scene-ai-shots-batch",
                        phase="item",
                        user_id=user_id,
                        user_name=user_name,
                        project_id=project_id,
                        episode_id=episode_id,
                        job_id=job_id,
                        item_id=sid,
                        item_label=result.get("scene_label") or scene_label,
                        result="failed",
                        message=error_message,
                    )

                completed += 1
                with SessionLocal() as progress_db:
                    episode = _read_latest_episode(progress_db)
                    if not episode:
                        break

                    latest = _read_scene_ai_shots_batch_status(episode)
                    latest["completed"] = completed
                    latest["success"] = success
                    latest["failed"] = failed
                    latest["errors"] = errors
                    latest["current_scene_id"] = sid
                    latest["current_scene_label"] = result.get("scene_label") or scene_label
                    latest["updated_at"] = now_bj_iso()
                    latest["message"] = f"Progress {completed}/{total}"
                    _persist_scene_ai_shots_batch_status(progress_db, episode, latest)

                if not _stop_requested():
                    while len(active_future_map) < max_workers and _submit_next_scene(executor):
                        pass

                _persist_active_scene_status()

        if _stop_requested() and next_scene_index < len(scene_ids):
            with SessionLocal() as status_db:
                episode = _read_latest_episode(status_db)
                if episode:
                    latest_after_batch = _read_scene_ai_shots_batch_status(episode)
                    latest_after_batch["running"] = False
                    latest_after_batch["completed"] = completed
                    latest_after_batch["success"] = success
                    latest_after_batch["failed"] = failed
                    latest_after_batch["errors"] = errors
                    latest_after_batch["finished_at"] = now_bj_iso()
                    latest_after_batch["stopped_by_user"] = True
                    latest_after_batch["message"] = "Stopped by user request"
                    _persist_scene_ai_shots_batch_status(status_db, episode, latest_after_batch)
                    _log_batch_sys_event(
                        kind="scene-ai-shots-batch",
                        phase="end",
                        user_id=user_id,
                        user_name=user_name,
                        project_id=project_id,
                        episode_id=episode_id,
                        job_id=job_id,
                        result="canceled",
                        message="Stopped by user request",
                        extra={"completed": completed, "success": success, "failed": failed},
                    )
            return

        with SessionLocal() as final_db:
            episode = final_db.query(Episode).filter(Episode.id == episode_id).first()
            if episode:
                final_status = _read_scene_ai_shots_batch_status(episode)
                final_status["running"] = False
                final_status["completed"] = completed
                final_status["success"] = success
                final_status["failed"] = failed
                final_status["errors"] = errors
                final_status["finished_at"] = now_bj_iso()
                final_status["updated_at"] = final_status["finished_at"]
                final_status["stopped_by_user"] = bool(final_status.get("stop_requested"))
                final_status["message"] = f"Batch done: success {success}, failed {failed}"
                _persist_scene_ai_shots_batch_status(final_db, episode, final_status)
                _log_batch_sys_event(
                    kind="scene-ai-shots-batch",
                    phase="end",
                    user_id=user_id,
                    user_name=user_name,
                    project_id=project_id,
                    episode_id=episode_id,
                    job_id=job_id,
                    result="completed",
                    message=final_status.get("message"),
                    extra={"completed": completed, "success": success, "failed": failed},
                )
    except Exception as e:
        try:
            with SessionLocal() as error_db:
                episode = error_db.query(Episode).filter(Episode.id == episode_id).first()
                if episode:
                    failed_status = _read_scene_ai_shots_batch_status(episode)
                    failed_status["running"] = False
                    failed_status["finished_at"] = now_bj_iso()
                    failed_status["updated_at"] = failed_status["finished_at"]
                    failed_status["message"] = f"Batch failed: {str(e)}"
                    failed_status["errors"] = list(failed_status.get("errors") or []) + [str(e)]
                    _persist_scene_ai_shots_batch_status(error_db, episode, failed_status)
                    _log_batch_sys_event(
                        kind="scene-ai-shots-batch",
                        phase="end",
                        user_id=user_id,
                        user_name=str((user.username if 'user' in locals() and user else "") or f"user_{user_id}"),
                        project_id=int(episode.project_id),
                        episode_id=episode_id,
                        job_id=f"scene-ai-shots-batch:{int(episode_id)}",
                        result="failed",
                        message=str(e),
                    )
        except Exception:
            pass
    finally:
        _clear_episode_worker(SCENE_AI_SHOTS_BATCH_THREADS, SCENE_AI_SHOTS_BATCH_THREADS_LOCK, int(episode_id))


def _start_scene_ai_shots_batch_for_episode(
    db: Session,
    episode: Episode,
    current_user: User,
    scene_ids: Optional[List[int]] = None,
    function_name: Optional[str] = None,
    system_api_id: Optional[int] = None,
) -> Dict[str, Any]:
    episode_id = int(episode.id)
    active_episode = (
        db.query(Episode)
        .filter(Episode.id == episode_id, _active_episode_clause())
        .first()
    )
    if active_episode is None:
        raise HTTPException(status_code=404, detail="Episode not found or has been deleted")
    episode = active_episode
    latest_status = _read_scene_ai_shots_batch_status(episode)
    if bool(latest_status.get("running")):
        raise HTTPException(status_code=409, detail="Scene AI shots batch is already running")

    requested_scene_ids = [int(x) for x in (scene_ids or []) if x]
    scenes_query = db.query(Scene).filter(Scene.episode_id == episode_id, _active_scene_clause())
    if requested_scene_ids:
        scenes_query = scenes_query.filter(Scene.id.in_(requested_scene_ids))
    target_scenes = _sort_scenes_by_scene_no(scenes_query.all())
    scene_ids = [int(s.id) for s in target_scenes]
    if not scene_ids:
        raise HTTPException(status_code=400, detail="No saved scenes found for batch")

    batch_max_concurrency = _resolve_user_batch_parallel_limit(
        getattr(current_user, "is_active", USER_ACTIVE_LEVEL_DEFAULT),
        default=SCENE_AI_SHOTS_BATCH_DEFAULT_CONCURRENCY,
    )

    now_iso = now_bj_iso()
    status_payload = {
        "running": True,
        "project_id": episode.project_id,
        "episode_id": episode_id,
        "started_by_user_id": int(current_user.id),
        "started_by_username": str(current_user.username or ""),
        "scene_ids": scene_ids,
        "max_concurrency": batch_max_concurrency,
        "total": len(scene_ids),
        "completed": 0,
        "success": 0,
        "failed": 0,
        "current_scene_id": None,
        "current_scene_label": "",
        "message": "Batch task started",
        "errors": [],
        "stop_requested": False,
        "stop_requested_at": None,
        "force_stopped": False,
        "stopped_by_user": False,
        "started_at": now_iso,
        "updated_at": now_iso,
        "finished_at": None,
    }
    _persist_scene_ai_shots_batch_status(db, episode, status_payload)
    _log_batch_sys_event(
        kind="scene-ai-shots-batch",
        phase="start",
        user_id=current_user.id,
        user_name=current_user.username,
        project_id=episode.project_id,
        episode_id=episode_id,
        job_id=f"scene-ai-shots-batch:{int(episode_id)}",
        result="running",
        message="Batch task started",
        extra={"scene_ids": scene_ids, "total": len(scene_ids), "max_concurrency": batch_max_concurrency},
    )

    worker = threading.Thread(
        target=_run_scene_ai_shots_batch_job,
        args=(episode_id, scene_ids, current_user.id, batch_max_concurrency, function_name, system_api_id),
        daemon=True,
    )
    worker.start()
    _register_episode_worker(SCENE_AI_SHOTS_BATCH_THREADS, SCENE_AI_SHOTS_BATCH_THREADS_LOCK, int(episode_id), worker)

    return status_payload


