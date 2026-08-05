# -*- coding: utf-8 -*-
"""Shot AI generation / batch / apply workspace section routes."""
from __future__ import annotations

from app.api.routers.workspace import shared as _shared

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

class AIShotGenRequest(BaseModel):
    user_prompt: Optional[str] = None
    system_prompt: Optional[str] = None
    shot_generation_mode: Optional[str] = None
    shot_generation_features: Optional[Dict[str, Any]] = None
    function_name: Optional[str] = None
    system_api_id: Optional[int] = None


class AIShotRegenerateRequest(BaseModel):
    content: Optional[List[Dict[str, Any]]] = None
    additional_instructions: Optional[str] = None
    prompt_file: Optional[str] = "skills/shot_generation.md"
    shot_generation_mode: Optional[str] = None
    shot_generation_features: Optional[Dict[str, Any]] = None
    function_name: Optional[str] = None
    system_api_id: Optional[int] = None



# Shot generation prompts (canonical: app.services.shot_generation_prompts).
from app.services.shot_generation_prompts import (  # noqa: E402,F401
    _strip_ai_shots_reasoning_prefix_lines,
    _build_ai_shots_response_validator,
    _map_shared_prompt_mode_to_shot_generation_mode,
    _resolve_effective_shot_generation_mode,
    _build_project_prompt_context,
    _build_shot_generation_project_context,
    _build_scene_subject_image_prompts_cn_section,
    _build_shot_prompts,
    _extract_shot_regenerate_marker,
    _build_shot_regenerate_prompts,
    _resolve_scene_for_shot_persist,
    _persist_scene_shot_generation_result,
)

class ShotGenerationRoutePreviewRequest(BaseModel):
    scene_id: int
    shot_generation_mode: Optional[str] = None
    shot_generation_features: Optional[Dict[str, Any]] = None



@router.get("/scenes/{scene_id}/ai_prompt_preview")
def ai_prompt_preview(
    scene_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
        
    episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
    project = _require_project_access(db, episode.project_id, current_user)
        
    project_context = _build_shot_generation_project_context(project)
    effective_mode = _resolve_effective_shot_generation_mode(
        db,
        project_metadata=project_context.get("metadata"),
        log_context="ai_prompt_preview",
    )
    feature_bundle = resolve_shot_generation_feature_bundle(
        project_metadata=project_context.get("metadata"),
        script_text=scene.core_scene_info or "",
        mode=effective_mode,
    )
    system, user = _build_shot_prompts(db, scene, project)
    return {
        "system_prompt": system,
        "user_prompt": user,
        "shot_generation_mode": feature_bundle.get("mode"),
        "base_prompt_file": feature_bundle.get("base_prompt_file"),
        "selected_skills": [
            {
                "skill_id": item.get("skill_id"),
                "dimension": item.get("dimension"),
                "value": item.get("value"),
                "title": item.get("title"),
                "slot_token": item.get("slot_token"),
            }
            for item in (feature_bundle.get("selected_skills") or [])
        ],
    }


@router.get("/prompts/shot-generation/features")
async def get_shot_generation_feature_options(current_user: User = Depends(get_current_user)):
    return get_shot_generation_feature_catalog()


def _shot_generation_slot_origin(slot_token: Any) -> str:
    token = str(slot_token or "").strip()
    if not token:
        return "unknown"
    if token == "[[SHOT_GENERATION_COMBO_RULES]]":
        return "global_combo"
    if token.startswith("[[SHOT_GENERATION_") and token.endswith("_RULES]]"):
        return "global_dimension"
    return "unknown"


@router.post("/prompts/shot-generation/route-preview")
async def preview_shot_generation_route(
    request: ShotGenerationRoutePreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    scene = db.query(Scene).filter(Scene.id == request.scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    project = _require_project_access(db, episode.project_id, current_user)
    project_context = _build_shot_generation_project_context(project)
    effective_mode = _resolve_effective_shot_generation_mode(
        db,
        requested_mode=request.shot_generation_mode,
        project_metadata=project_context.get("metadata"),
        log_context="shot-generation-route-preview",
    )
    bundle = resolve_shot_generation_feature_bundle(
        project_metadata=project_context.get("metadata"),
        explicit_features=request.shot_generation_features,
        script_text=scene.core_scene_info or "",
        mode=effective_mode,
    )
    return {
        "scene_id": scene.id,
        "requested_mode": request.shot_generation_mode,
        "effective_mode": bundle.get("mode"),
        "enabled": bundle.get("enabled"),
        "base_prompt_file": bundle.get("base_prompt_file"),
        "slot_blocks": bundle.get("slot_blocks") or {},
        "known_slot_tokens": bundle.get("known_slot_tokens") or [],
        "normalized_features": bundle.get("normalized_features") or {},
        "resolved_dimensions": bundle.get("resolved_dimensions") or {},
        "selected_skills": [
            {
                "skill_id": item.get("skill_id"),
                "dimension": item.get("dimension"),
                "value": item.get("value"),
                "title": item.get("title"),
                "source": item.get("source"),
                "slot_token": item.get("slot_token"),
                "slot_origin": _shot_generation_slot_origin(item.get("slot_token")),
                "slot_has_block": bool((bundle.get("slot_blocks") or {}).get(str(item.get("slot_token") or ""))),
            }
            for item in (bundle.get("selected_skills") or [])
        ],
        "combo_matches": [
            {
                "skill_id": item.get("skill_id"),
                "title": item.get("title"),
                "when": item.get("when") or {},
                "slot_token": item.get("slot_token"),
                "slot_origin": _shot_generation_slot_origin(item.get("slot_token")),
                "slot_has_block": bool((bundle.get("slot_blocks") or {}).get(str(item.get("slot_token") or ""))),
            }
            for item in (bundle.get("combo_matches") or [])
        ],
        "diagnostics": bundle.get("diagnostics") or [],
    }

class AnalysisContent(BaseModel):
    content: Union[Dict[str, Any], List[Any]]
    # When False (default), abandon import if the scene already has active shots.
    # Set True only for intentional replace flows (UI confirm).
    replace_existing: Optional[bool] = False


class SceneAiShotsBatchStartRequest(BaseModel):
    scene_ids: Optional[List[int]] = None
    function_name: Optional[str] = None
    system_api_id: Optional[int] = None


# Scene AI shots batch (canonical: app.services.scene_ai_shots_batch).
from app.services.shot_ai_generation_ops import (  # noqa: E402,F401
    execute_ai_generate_shots,
    execute_ai_regenerate_shots,
)

from app.services.scene_ai_shots_batch import (  # noqa: E402,F401
    SCENE_AI_SHOTS_BATCH_STATUS_KEY,
    SCENE_AI_SHOTS_BATCH_PER_SCENE_TIMEOUT_SEC,
    SCENE_AI_SHOTS_BATCH_DEFAULT_CONCURRENCY,
    SCENE_AI_SHOTS_BATCH_STATUS_ERROR_LIMIT,
    SCENE_AI_SHOTS_BATCH_STATUS_ERROR_MAX_CHARS,
    _read_scene_ai_shots_batch_status,
    _persist_scene_ai_shots_batch_status,
    _build_scene_ai_shots_batch_status_response,
    _run_scene_ai_shots_batch_item,
    _run_scene_ai_shots_batch_job,
    _start_scene_ai_shots_batch_for_episode,
)


@router.post("/episodes/{episode_id}/scenes/ai_shots/batch/start", response_model=Dict[str, Any])
def start_scene_ai_shots_batch(
    episode_id: int,
    req: SceneAiShotsBatchStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)
    return _start_scene_ai_shots_batch_for_episode(
        db=db,
        episode=episode,
        current_user=current_user,
        scene_ids=req.scene_ids or [],
        function_name=req.function_name,
        system_api_id=req.system_api_id,
    )


@router.get("/episodes/{episode_id}/scenes/ai_shots/batch/status", response_model=Dict[str, Any])
def get_scene_ai_shots_batch_status(
    episode_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _apply_no_store_headers(response)
    response.headers["X-Poll-Interval-Ms"] = "2500"
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)
    status_payload = _read_scene_ai_shots_batch_status(episode)
    if (
        bool(status_payload.get("running"))
        and _is_stale_running_payload(status_payload, stale_minutes=10)
        and not _is_episode_worker_alive(SCENE_AI_SHOTS_BATCH_THREADS, SCENE_AI_SHOTS_BATCH_THREADS_LOCK, int(episode_id))
    ):
        now_iso = now_bj_iso()
        status_payload["running"] = False
        status_payload["status"] = "canceled"
        status_payload["force_stopped"] = True
        status_payload["stopped_by_user"] = True
        status_payload["current_scene_id"] = None
        status_payload["current_scene_label"] = ""
        status_payload["updated_at"] = now_iso
        status_payload["finished_at"] = status_payload.get("finished_at") or now_iso
        status_payload["message"] = "Recovered orphaned task state (no active worker)"
        _persist_scene_ai_shots_batch_status(db, episode, status_payload)
    return _build_scene_ai_shots_batch_status_response(status_payload)


@router.post("/episodes/{episode_id}/scenes/ai_shots/batch/stop", response_model=Dict[str, Any])
def stop_scene_ai_shots_batch(
    episode_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)

    removed = False
    info = _episode_runtime_info_from_episode(episode)
    if SCENE_AI_SHOTS_BATCH_STATUS_KEY in info:
        info.pop(SCENE_AI_SHOTS_BATCH_STATUS_KEY, None)
        episode.episode_info = info
        db.add(episode)
        db.commit()
        removed = True

    _clear_episode_worker(SCENE_AI_SHOTS_BATCH_THREADS, SCENE_AI_SHOTS_BATCH_THREADS_LOCK, int(episode_id))
    _log_batch_sys_event(
        kind="scene-ai-shots-batch",
        phase="stop",
        user_id=current_user.id,
        user_name=current_user.username,
        project_id=episode.project_id,
        episode_id=episode_id,
        job_id=f"scene-ai-shots-batch:{int(episode_id)}",
        result="canceled",
        message="Force removed by user",
    )
    return {
        "episode_id": int(episode_id),
        "running": False,
        "status": "canceled",
        "deleted": bool(removed),
        "message": "Force removed",
    }

@router.post("/scenes/{scene_id}/ai_generate_shots")
async def ai_generate_shots(
    scene_id: int,
    req: Optional[AIShotGenRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    if async_mode == "1":
        tid = _submit_async(ai_generate_shots, user_id=current_user.id,
                            kind="ai_generate_shots", scene_id=scene_id, req=req, async_mode="0")
        return JSONResponse({"task_id": tid, "async": True})
    return await execute_ai_generate_shots(
        scene_id=scene_id,
        req=req,
        db=db,
        current_user=current_user,
    )


@router.post("/scenes/{scene_id}/ai_regenerate_shots")
async def ai_regenerate_shots(
    scene_id: int,
    req: AIShotRegenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    if async_mode == "1":
        tid = _submit_async(
            ai_regenerate_shots,
            user_id=current_user.id,
            kind="ai_regenerate_shots",
            scene_id=scene_id,
            req=req,
            async_mode="0",
        )
        return JSONResponse({"task_id": tid, "async": True})
    return await execute_ai_regenerate_shots(
        scene_id=scene_id,
        req=req,
        db=db,
        current_user=current_user,
    )



@router.get("/scenes/{scene_id}/latest_ai_result")
def get_scene_latest_ai_result(
    scene_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """Get the latest saved AI shot generation result for a scene.

    Storage (Scheme A): scenes.ai_shots_result is the raw Markdown table text.
    This endpoint returns a structured wrapper for the UI by parsing that Markdown.
    """
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
        
    episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
    _require_project_access(db, episode.project_id, current_user)
         
    raw_value = scene.ai_shots_result
    if not raw_value:
        return {}

    # Backward compat: older versions stored JSON wrapper into scenes.ai_shots_result
    if isinstance(raw_value, str) and raw_value.strip().startswith('{'):
        try:
            legacy = json.loads(raw_value)
            if isinstance(legacy, dict) and ("raw_text" in legacy or "content" in legacy):
                raw_text = legacy.get("raw_text") or ""
                if raw_text:
                    scene.ai_shots_result = raw_text
                    db.commit()
                    raw_value = raw_text
                else:
                    # No raw_text; best effort keep the JSON string as raw.
                    raw_value = scene.ai_shots_result
        except Exception:
            pass

    # Parse markdown table into list-of-dicts for the staging editor
    warnings: List[str] = []
    _, shots_data, table_line_count = parse_shots_markdown_table(raw_value or "")
    if str(raw_value or "").strip() and not shots_data:
        warnings.append("Shot generation output did not produce a parseable markdown table; review the raw markdown before apply.")
    if table_line_count >= 4 and len(shots_data) > 0 and (len(shots_data) * 2) <= table_line_count:
        logger.warning(
            f"[get_scene_latest_ai_result] suspicious_row_drop scene_id={scene_id} "
            f"table_lines={table_line_count} parsed_shots={len(shots_data)}"
        )
        warnings.append("Shot generation output may have lost rows during markdown parsing; review the raw markdown before apply.")

    return {
        "raw_text": raw_value,
        "content": shots_data,
        "warnings": warnings,
    }

@router.put("/scenes/{scene_id}/latest_ai_result")
def update_scene_latest_ai_result(
    scene_id: int,
    data: AnalysisContent, # Reusing this schema: { "content": ... }
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    Update (Save/Edit) the latest shot generation result without applying it.
    Expects data.content to be the list of shot dictionaries.
    """
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
        
    episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
    _require_project_access(db, episode.project_id, current_user)
    
    validated_rows, md = _validate_shot_rows_roundtrip_or_raise(
        data.content,
        source_label="Edited scene shot table",
        status_code=400,
    )

    scene.ai_shots_result = md
    db.commit()

    return {
        "timestamp": now_bj_iso(),
        "raw_text": md,
        "content": validated_rows,
    }



# Shot import ops (canonical: app.services.shot_import_ops).
from app.services.shot_import_ops import (  # noqa: E402,F401
    _import_scene_shot_rows_to_db,
)


@router.post("/scenes/{scene_id}/apply_ai_result")
def apply_scene_ai_result(
    scene_id: int,
    data: Optional[AnalysisContent] = None, # Optional: apply provided content instead of stored
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    Apply the stored (or provided) shot list to the actual Shots table.

    Default: abandon import when the scene already has active shots.
    Pass replace_existing=true only for intentional overwrite (UI confirm).
    Duplicate Shot IDs within the payload are deduped (last row wins).
    """
    requested_scene_id = int(scene_id)
    scene = db.query(Scene).filter(Scene.id == requested_scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    # Soft-deleted rows are invisible in the workspace scene list; remap to the
    # active successor so generated markdown is not applied onto a ghost scene.
    if _is_soft_deleted(scene):
        remapped, remapped_from = _resolve_scene_for_shot_persist(
            db,
            scene_id=requested_scene_id,
            episode_id=getattr(scene, "episode_id", None),
            scene_no=getattr(scene, "scene_no", None),
        )
        if remapped is None or _is_soft_deleted(remapped):
            raise HTTPException(status_code=404, detail="Scene not found")
        logger.warning(
            "[apply_scene_ai_result] remapped soft-deleted scene_id=%s -> active scene_id=%s",
            remapped_from or requested_scene_id,
            getattr(remapped, "id", None),
        )
        scene = remapped
        scene_id = int(scene.id)

    episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
    project = _require_project_access(db, episode.project_id, current_user)

    shots_data = []
    skipped_row_errors: List[str] = []
    replace_existing = bool(getattr(data, "replace_existing", False)) if data is not None else False

    # 1. Determine Source
    provided_content = None
    if data and data.content is not None:
        provided_content = data.content

    if str(getattr(scene, "ai_shots_result", None) or "").strip():
        shots_data, skipped_row_errors = _resolve_shots_data_for_apply(
            scene,
            provided_content,
            source_label="Scene shot table",
            status_code=400,
        )
    elif provided_content is not None:
        shots_data, skipped_row_errors = _validate_shot_rows_for_apply_with_tolerance(
            provided_content,
            source_label="Provided scene shot table",
            status_code=400,
        )
    else:
        shots_data, skipped_row_errors = _resolve_shots_data_for_apply(
            scene,
            None,
            source_label="Stored scene shot table",
            status_code=409,
        )

    if not shots_data:
        logger.warning(
            "[apply_scene_ai_result] empty_shots_data scene_id=%s has_stored=%s provided=%s skipped=%s",
            scene_id,
            bool(str(getattr(scene, "ai_shots_result", None) or "").strip()),
            provided_content is not None,
            skipped_row_errors[:5] if skipped_row_errors else [],
        )
        raise HTTPException(status_code=400, detail="No shot rows provided or available to apply")

    if skipped_row_errors:
        logger.warning(
            "[apply_scene_ai_result] skipped_invalid_rows scene_id=%s skipped=%s details=%s",
            scene_id,
            len(skipped_row_errors),
            skipped_row_errors[:5],
        )

    return _import_scene_shot_rows_to_db(
        scene_id=scene_id,
        db=db,
        scene=scene,
        episode=episode,
        project=project,
        shots_data=shots_data,
        skipped_row_errors=skipped_row_errors,
        replace_existing=replace_existing,
    )
