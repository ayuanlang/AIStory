# -*- coding: utf-8 -*-
"""Prompts/analyze section routes — symbols pulled from shared module."""
from __future__ import annotations

from app.api.routers.prompts import shared as _shared

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

from app.services.analyze_scene_dedup import (  # noqa: E402,F401
    _ANALYZE_SCENE_DEDUP_WINDOW_SECONDS,
    _await_analyze_scene_segment,
    _build_analyze_scene_dedup_key,
    _delete_analyze_scene_dedup_row,
    _ensure_analyze_scene_dedup_table_ready,
    _get_analyze_scene_dedup_row,
    _insert_analyze_scene_dedup_row_if_absent,
    _prune_analyze_scene_dedup_rows,
    _upsert_analyze_scene_dedup_row,
)
from app.services.analyze_scene_runner import (  # noqa: E402,F401
    execute_analyze_scene,
)
from app.services.db_session_utils import (  # noqa: E402,F401
    _snapshot_user_principal,
)
from app.services.task_manager import (  # noqa: E402,F401
    get_status as _get_task_status,
    submit_async_endpoint as _submit_async,
)


@router.post("/analyze_scene", response_model=Dict[str, Any])
async def analyze_scene(request: AnalyzeSceneRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db), async_mode: str = Query("0")): # user auth optional depending on reqs, kept for safety
    """
    Submits raw script text to LLM for Scene/Beat analysis using a specific prompt template.
    Returns the raw analysis result (Markdown/JSON).
    """
    analysis_trace_id = str(getattr(request, "analysis_trace_id", "") or "").strip()
    logger.info(
        "[DEBUG] /analyze_scene received system_api_id=%s async_mode=%s trace_id=%s",
        getattr(request, "system_api_id", None),
        async_mode,
        analysis_trace_id or "-",
    )
    current_user_snapshot = _snapshot_user_principal(current_user)
    current_user_id = int(getattr(current_user_snapshot, "id", 0) or 0)
    current_user_is_superuser = bool(getattr(current_user_snapshot, "is_superuser", False))
    if async_mode == "1":
        dedup_key = _build_analyze_scene_dedup_key(current_user_id, request)
        now_ts = time.time()
        reused_task_id = ""
        reused_status = ""
        _ensure_analyze_scene_dedup_table_ready()

        _prune_analyze_scene_dedup_rows(db, now_ts)
        existing = _get_analyze_scene_dedup_row(db, dedup_key) or {}
        existing_task_id = str(existing.get("task_id") or "").strip()
        existing_ts = float(existing.get("updated_at") or 0.0)
        if existing_task_id:
            info = _get_task_status(existing_task_id, user_id=current_user_id) or {}
            status = str(info.get("status") or "").strip().lower()
            within_window = (now_ts - existing_ts) <= float(_ANALYZE_SCENE_DEDUP_WINDOW_SECONDS)
            if status in {"pending", "running"} and within_window:
                reused_task_id = existing_task_id
                reused_status = status
            else:
                _delete_analyze_scene_dedup_row(db, dedup_key)
                db.commit()

        if reused_task_id:
            logger.warning(
                "[analyze_scene] deduplicated async submit user_id=%s episode_id=%s task_id=%s status=%s window_s=%s trace_id=%s",
                current_user_id,
                getattr(request, "episode_id", None),
                reused_task_id,
                reused_status,
                _ANALYZE_SCENE_DEDUP_WINDOW_SECONDS,
                analysis_trace_id or "-",
            )
            return JSONResponse({
                "task_id": reused_task_id,
                "async": True,
                "deduplicated": True,
                "status": reused_status,
                "analysis_trace_id": analysis_trace_id,
            })

        provisional_task_id = f"pending-{uuid.uuid4().hex}"
        inserted = _insert_analyze_scene_dedup_row_if_absent(
            db,
            dedup_key=dedup_key,
            user_id=current_user_id,
            task_id=provisional_task_id,
            now_ts=now_ts,
        )
        db.commit()

        if not inserted:
            existing = _get_analyze_scene_dedup_row(db, dedup_key) or {}
            existing_task_id = str(existing.get("task_id") or "").strip()
            existing_ts = float(existing.get("updated_at") or 0.0)
            if existing_task_id:
                info = _get_task_status(existing_task_id, user_id=current_user_id) or {}
                status = str(info.get("status") or "").strip().lower()
                within_window = (now_ts - existing_ts) <= float(_ANALYZE_SCENE_DEDUP_WINDOW_SECONDS)
                if status in {"pending", "running"} and within_window:
                    logger.info(
                        "[analyze_scene][dedup] reused-existing-race user_id=%s episode_id=%s task_id=%s status=%s age_s=%s trace_id=%s",
                        current_user_id,
                        getattr(request, "episode_id", None),
                        existing_task_id,
                        status,
                        int(max(0.0, now_ts - existing_ts)),
                        analysis_trace_id or "-",
                    )
                    return JSONResponse({
                        "task_id": existing_task_id,
                        "async": True,
                        "deduplicated": True,
                        "status": status,
                        "analysis_trace_id": analysis_trace_id,
                    })
                _delete_analyze_scene_dedup_row(db, dedup_key)
                db.commit()

            _insert_analyze_scene_dedup_row_if_absent(
                db,
                dedup_key=dedup_key,
                user_id=current_user_id,
                task_id=provisional_task_id,
                now_ts=now_ts,
            )
            db.commit()

        tid = _submit_async(analyze_scene, user_id=current_user_id, kind="analyze_scene", request=request, async_mode="0")
        _upsert_analyze_scene_dedup_row(
            db,
            dedup_key=dedup_key,
            user_id=current_user_id,
            task_id=tid,
            now_ts=now_ts,
        )
        db.commit()
        logger.info(
            "[analyze_scene][dedup] new-task-claimed user_id=%s episode_id=%s task_id=%s trace_id=%s",
            current_user_id,
            getattr(request, "episode_id", None),
            tid,
            analysis_trace_id or "-",
        )
        return JSONResponse({"task_id": tid, "async": True, "analysis_trace_id": analysis_trace_id})
    return await execute_analyze_scene(
        request=request,
        current_user=current_user,
        db=db,
    )


@router.post("/analyze_scene/stream")
async def stream_analyze_scene_endpoint(request: AnalyzeSceneRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Placeholder for future streaming implementation
    raise HTTPException(status_code=501, detail="Streaming not yet implemented for this endpoint")
