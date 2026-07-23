# -*- coding: utf-8 -*-
"""Generation section routes — symbols pulled from shared module."""
from __future__ import annotations

from app.api.routers.generation import shared as _shared

router = _shared.router
globals().update(
    {
        k: v
        for k, v in vars(_shared).items()
        if k
        not in {
            "__name__",
            "__file__",
            "__package__",
            "__loader__",
            "__spec__",
            "__doc__",
            "__builtins__",
        }
    }
)


from app.services.shot_media_batch_status import (  # noqa: E402,F401
    SHOT_MEDIA_BATCH_STATUS_KEY,
    SHOT_MEDIA_BATCH_DEFAULT_CONCURRENCY,
    SHOT_MEDIA_BATCH_RUNTIME_CACHE,
    SHOT_MEDIA_BATCH_RUNTIME_CACHE_LOCK,
    _cache_shot_media_batch_status,
    _get_cached_shot_media_batch_status,
    _clear_cached_shot_media_batch_status,
    _read_shot_media_batch_status,
    _persist_shot_media_batch_status,
)

from app.services.generation_runtime.video_ref_pipeline import (  # noqa: E402,F401
    DEFAULT_SHOT_VIDEO_MODE,
    _parse_shot_tech,
    _normalize_entity_anchor_token,
    _entity_lookup_alias_keys,
    _build_project_entity_lookup,
    _extract_kling_character_mentions,
    _collect_kling_prompt_alias_maps,
    _build_auto_kling_elements,
    _align_kling_elements_to_prompt_mentions,
    _merge_kling_elements,
    _inject_shot_prompt_anchors,
    _collect_associated_entities_refs,
    _extract_frontend_aligned_entity_raw_names,
    _collect_prompt_entity_ref_images,
    _collect_prompt_entity_ref_images_relaxed,
    _normalize_video_ref_mode,
    _resolve_shot_video_mode,
    _dedupe_media_ref_urls,
    _system_api_supports_last_frame_flag,
    _video_api_supports_last_frame_mode,
    _is_video_reference_image_mode,
    _listify_video_ref_urls,
    _ensure_video_frame_role_instructions,
    _normalize_video_request_refs,
    _limit_keyframes_for_video_mode,
    _collect_video_prompt_entity_refs,
    _is_video_media_ref_url,
    _filter_image_media_ref_urls,
    _resolve_shot_video_panel_image_refs,
    _resolve_default_shot_image_gen_refs,
    _merge_entity_refs_for_video_mode,
    _prepend_keyframe_story_progression_instruction,
    _compute_subject_ref_index_map,
    _normalize_media_ref_key,
    _media_ref_basename,
    _lookup_entity_row_for_token,
    _pick_submitted_ref_for_entity,
    _iter_unique_entity_rows,
    _build_url_to_entity_rows,
    _collect_prompt_entity_mentions_for_mapping,
    _reconcile_video_refs_by_entity_names,
    _sync_request_image_refs_with_aligned,
    _resolve_video_project_id_from_payload,
    _collect_video_flat_refs_from_payload,
    _preprocess_video_submit_payload,
    _append_video_api_ref_mapping,
    _find_previous_shot_end_frame_url,
    _make_public_upload_url_for_provider,
    _find_previous_shot_video_url,
)


from app.services.shot_media_batch_jobs import (  # noqa: E402,F401
    _is_shot_video_batch_eligible,
    _run_shot_media_video_batch_item,
    _run_shot_media_batch_job,
)

@router.post("/episodes/{episode_id}/shots/batch-media/start", response_model=Dict[str, Any])
def start_shot_media_batch_job(
    episode_id: int,
    req: ShotMediaBatchStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)

    mode = str(req.mode or "keyframes").strip().lower()
    if mode not in {"keyframes", "videos"}:
        raise HTTPException(status_code=400, detail="mode must be 'keyframes' or 'videos'")

    latest = _read_shot_media_batch_status(episode)
    if bool(latest.get("running")):
        raise HTTPException(status_code=409, detail="Shot media batch task is already running")

    shots_query = db.query(Shot).filter(Shot.episode_id == episode_id)
    if req.shot_ids:
        shots_query = shots_query.filter(Shot.id.in_(req.shot_ids))
    target_shots = shots_query.order_by(Shot.id.asc()).all()
    if mode == "videos":
        target_shots = [shot for shot in target_shots if _is_shot_video_batch_eligible(shot, bool(req.overwrite_existing))]
    shot_ids = [int(s.id) for s in target_shots]
    if not shot_ids:
        if mode == "videos":
            raise HTTPException(status_code=400, detail="No eligible shots found for video batch task")
        raise HTTPException(status_code=400, detail="No shots found for batch task")

    batch_max_concurrency = _resolve_user_batch_parallel_limit(
        getattr(current_user, "is_active", USER_ACTIVE_LEVEL_DEFAULT),
        default=SHOT_MEDIA_BATCH_DEFAULT_CONCURRENCY,
    )

    now_iso = now_bj_iso()
    status_payload = {
        "running": True,
        "mode": mode,
        "episode_id": episode_id,
        "project_id": episode.project_id,
        "started_by_user_id": int(current_user.id),
        "started_by_username": str(current_user.username or ""),
        "shot_ids": shot_ids,
        "max_concurrency": batch_max_concurrency,
        "overwrite_existing": bool(req.overwrite_existing),
        "draft_mode": bool(req.draft_mode),
        "sd2_auto_duration": bool(req.sd2_auto_duration),
        "total": len(shot_ids),
        "completed": 0,
        "success": 0,
        "failed": 0,
        "current_shot_id": None,
        "current_shot_label": "",
        "current_asset_type": None,
        "current_asset_label": "",
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
    _persist_shot_media_batch_status(db, episode, status_payload)
    _log_batch_sys_event(
        kind="shot-media-batch",
        phase="start",
        user_id=current_user.id,
        user_name=current_user.username,
        project_id=episode.project_id,
        episode_id=episode_id,
        job_id=f"shot-media-batch:{int(episode_id)}",
        result="running",
        message="Batch task started",
        extra={
            "shot_ids": shot_ids,
            "total": len(shot_ids),
            "mode": mode,
            "max_concurrency": batch_max_concurrency,
            "overwrite_existing": bool(req.overwrite_existing),
        },
    )
    _reset_shot_media_batch_cancel_requested(int(episode_id))

    worker = threading.Thread(
        target=_run_shot_media_batch_job,
        args=(episode_id, req.model_dump(), current_user.id),
        daemon=True,
    )
    worker.start()
    _register_episode_worker(SHOT_MEDIA_BATCH_THREADS, SHOT_MEDIA_BATCH_THREADS_LOCK, int(episode_id), worker)
    return status_payload


@router.get("/episodes/{episode_id}/shots/batch-media/status", response_model=Dict[str, Any])
def get_shot_media_batch_job_status(
    episode_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cached_status = _get_cached_shot_media_batch_status(int(episode_id))
    try:
        project_id = None
        if isinstance(cached_status, dict):
            try:
                project_id = int(cached_status.get("project_id") or 0)
            except Exception:
                project_id = 0

        episode = None
        if project_id and project_id > 0:
            _require_project_access(db, project_id, current_user)
        else:
            episode = db.query(Episode).filter(Episode.id == episode_id).first()
            if not episode:
                raise HTTPException(status_code=404, detail="Episode not found")
            _require_project_access(db, episode.project_id, current_user)

        if episode is None:
            episode = db.query(Episode).filter(Episode.id == episode_id).first()
            if not episode:
                if isinstance(cached_status, dict):
                    return cached_status
                raise HTTPException(status_code=404, detail="Episode not found")

        status_payload = _read_shot_media_batch_status(episode)
        _cache_shot_media_batch_status(int(episode_id), status_payload)
        if (
            bool(status_payload.get("running"))
            and _is_stale_running_payload(status_payload, stale_minutes=10)
            and not _is_episode_worker_alive(SHOT_MEDIA_BATCH_THREADS, SHOT_MEDIA_BATCH_THREADS_LOCK, int(episode_id))
        ):
            now_iso = now_bj_iso()
            status_payload["running"] = False
            status_payload["status"] = "canceled"
            status_payload["force_stopped"] = True
            status_payload["stopped_by_user"] = True
            status_payload["current_shot_id"] = None
            status_payload["current_shot_label"] = ""
            status_payload["current_asset_type"] = None
            status_payload["current_asset_label"] = ""
            status_payload["updated_at"] = now_iso
            status_payload["finished_at"] = status_payload.get("finished_at") or now_iso
            status_payload["message"] = "Recovered orphaned task state (no active worker)"
            _persist_shot_media_batch_status(db, episode, status_payload)
            _cache_shot_media_batch_status(int(episode_id), status_payload)
        return status_payload
    except SQLAlchemyTimeoutError:
        if isinstance(cached_status, dict):
            fallback = dict(cached_status)
            fallback["degraded"] = True
            fallback["message"] = str(fallback.get("message") or "Status temporarily served from cache (database busy)")
            return fallback
        raise HTTPException(
            status_code=503,
            detail="Database connection pool is busy, please retry shortly",
        )


@router.post("/episodes/{episode_id}/shots/batch-media/stop", response_model=Dict[str, Any])
def stop_shot_media_batch_job(
    episode_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)

    latest_status = _read_shot_media_batch_status(episode)
    if not bool(latest_status.get("running")):
        _clear_cached_shot_media_batch_status(int(episode_id))
        return {
            "episode_id": int(episode_id),
            "running": False,
            "status": "idle",
            "deleted": False,
            "message": "No running shot batch task",
        }

    now_iso = now_bj_iso()
    latest_status["stop_requested"] = True
    latest_status["stop_requested_at"] = latest_status.get("stop_requested_at") or now_iso
    latest_status["stopped_by_user"] = True
    latest_status["message"] = "Stop requested by user"
    latest_status["updated_at"] = now_iso
    _persist_shot_media_batch_status(db, episode, latest_status)

    _set_shot_media_batch_cancel_requested(int(episode_id))
    _log_batch_sys_event(
        kind="shot-media-batch",
        phase="stop",
        user_id=current_user.id,
        user_name=current_user.username,
        project_id=episode.project_id,
        episode_id=episode_id,
        job_id=f"shot-media-batch:{int(episode_id)}",
        result="cancel_requested",
        message="Stop requested by user",
    )
    return {
        "episode_id": int(episode_id),
        "running": True,
        "status": "cancel_requested",
        "deleted": False,
        "message": "Stop requested",
    }

