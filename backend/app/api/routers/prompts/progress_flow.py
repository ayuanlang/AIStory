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

from app.services.scene_markdown_orchestration import (  # noqa: E402,F401
    _extract_analysis_text_from_result,
    _replace_adapted_script_in_beats_user_input,
    _derive_scene_orchestration_phase,
)
from app.services.project_access import (  # noqa: E402,F401
    _require_project_access,
)


class ScriptAnalysisFlowRunNodeRequest(BaseModel):
    node_key: str
    project_id: Optional[int] = None
    episode_id: Optional[int] = None
    scene_ids: Optional[List[int]] = None
    analyze_payload: Optional[Dict[str, Any]] = None
    function_name: Optional[str] = None
    system_api_id: Optional[int] = None


class SceneUnitsSyncRequest(BaseModel):
    project_id: int
    episode_id: int
    script_text: str
    script_id: Optional[str] = None
    prefer_markers: Optional[bool] = False
    partial: Optional[bool] = False
    target_scene_id: Optional[str] = None


class SceneOrchestrationResetRequest(BaseModel):
    project_id: int
    episode_id: int
    scene_ids: Optional[List[str]] = None


class ProgressAutoOrchestrateRequest(BaseModel):
    project_id: int
    episode_id: int
    scene_ids: Optional[List[str]] = None
    function_name: Optional[str] = None
    system_api_id: Optional[int] = None
    asset_types: Optional[List[str]] = None


class ProgressIssueResolveRequest(BaseModel):
    issue_id: int


class ProgressReconcileRequest(BaseModel):
    project_id: int
    episode_id: int


from app.services.scene_markdown_runner import (  # noqa: E402,F401
    _run_scene_markdown_node_per_scene,
)
from app.services.script_progress_helpers import (  # noqa: E402,F401
    _list_episode_scene_progress_rows,
    _resolve_scene_id_to_db_scene,
    _normalize_asset_types,
    _normalize_scene_marker_id_from_scene,
)

from app.services.subject_index_resolve import (  # noqa: E402,F401
    _subject_index_has_usable_content,
    resolve_usable_episode_subject_index,
    _subject_index_has_cover_poster,
    _script_optimization_has_project_visual_backfill,
)


@router.post("/prompts/scene-analysis/progress/sync-scene-units")
async def sync_scene_units_progress(
    request: SceneUnitsSyncRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == int(request.episode_id)).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)
    if int(request.project_id) != int(episode.project_id):
        raise HTTPException(status_code=400, detail="project_id does not match episode.project_id")

    script_id = request.script_id or f"episode:{int(request.episode_id)}"
    if request.prefer_markers:
        sync_result = sync_scene_units_from_markers(
            db,
            project_id=int(request.project_id),
            episode_id=int(request.episode_id),
            script_text=request.script_text,
            script_id=script_id,
        )
        summary = {
            "stage_key": STAGE_SCENE_MARKDOWN,
            "import_target": "script_progress_scene_units",
            "scene_count": int(sync_result.get("scene_count") or 0),
            "scene_ids": list(sync_result.get("scene_ids") or []),
            "parse_source": sync_result.get("parse_source"),
            "sync_result": sync_result,
        }
    else:
        summary = import_scene_markdown_stage(
            db=db,
            project_id=int(request.project_id),
            episode_id=int(request.episode_id),
            script_text=request.script_text,
            script_id=script_id,
            partial=bool(request.partial),
            target_scene_id=str(request.target_scene_id or "").strip() or None,
        )
    upsert_pipeline_node_status(
        db,
        project_id=int(request.project_id),
        episode_id=int(request.episode_id),
        script_id=script_id,
        node_name="scene_planning",
        status="success",
        progress_percent=100.0,
    )
    db.commit()
    return {"status": "ok", "summary": summary.get("sync_result") or summary}


@router.post("/prompts/scene-analysis/progress/reset-scene-orchestration")
async def reset_scene_orchestration_progress(
    request: SceneOrchestrationResetRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == int(request.episode_id)).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)
    if int(request.project_id) != int(episode.project_id):
        raise HTTPException(status_code=400, detail="project_id does not match episode.project_id")

    requested_scene_ids = expand_scene_ids_for_orchestration_reset([
        str(scene_id or "").strip()
        for scene_id in (request.scene_ids or [])
        if str(scene_id or "").strip()
    ])
    rows = (
        db.query(ScriptProgressSceneUnit)
        .filter(
            ScriptProgressSceneUnit.project_id == int(request.project_id),
            ScriptProgressSceneUnit.episode_id == int(request.episode_id),
        )
        .all()
    )
    reset_scene_ids: List[str] = []
    for row in rows:
        scene_id = str(getattr(row, "scene_id", "") or "").strip()
        if not scene_id:
            continue
        if requested_scene_ids and scene_id not in requested_scene_ids:
            continue
        update_scene_unit_orchestration_status(
            db,
            project_id=int(request.project_id),
            episode_id=int(request.episode_id),
            scene_id=scene_id,
            import_status="queued",
            parse_status="success",
            scene_markdown=None,
            parse_error_code=None,
        )
        reset_scene_ids.append(scene_id)

    script_id = f"episode:{int(request.episode_id)}"
    upsert_pipeline_node_status(
        db,
        project_id=int(request.project_id),
        episode_id=int(request.episode_id),
        script_id=script_id,
        node_name="scene_markdown",
        status="running",
        progress_percent=0.0,
        error_message=f"reset orchestration for {len(reset_scene_ids)} scene(s)",
    )
    db.commit()
    return {
        "status": "ok",
        "reset_scene_ids": reset_scene_ids,
        "reset_count": len(reset_scene_ids),
    }


@router.get("/prompts/scene-analysis/progress/episodes/{episode_id}")
async def get_episode_progress_snapshot(
    episode_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == int(episode_id)).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)

    scene_units: List[Dict[str, Any]] = []
    if ScriptProgressSceneUnit is not None:
        rows = (
            db.query(ScriptProgressSceneUnit)
            .filter(
                ScriptProgressSceneUnit.project_id == int(episode.project_id),
                ScriptProgressSceneUnit.episode_id == int(episode_id),
            )
            .order_by(ScriptProgressSceneUnit.scene_order.asc(), ScriptProgressSceneUnit.id.asc())
            .all()
        )
        scene_units = [
            {
                "scene_id": row.scene_id,
                "scene_order": row.scene_order,
                "parse_status": row.parse_status,
                "import_status": row.import_status,
                "orchestration_phase": _derive_scene_orchestration_phase(
                    import_status=row.import_status,
                    parse_status=row.parse_status,
                ),
                "parse_error_code": row.parse_error_code,
                "scene_markdown": str(getattr(row, "scene_markdown", "") or "").strip(),
                "updated_at": row.updated_at,
            }
            for row in rows
        ]

    pipeline_nodes: List[Dict[str, Any]] = []
    if ScriptProgressPipelineNode is not None:
        rows = (
            db.query(ScriptProgressPipelineNode)
            .filter(
                ScriptProgressPipelineNode.project_id == int(episode.project_id),
                ScriptProgressPipelineNode.episode_id == int(episode_id),
            )
            .order_by(ScriptProgressPipelineNode.id.asc())
            .all()
        )
        pipeline_nodes = [
            {
                "node_name": row.node_name,
                "scene_id": row.scene_id,
                "asset_type": row.asset_type,
                "status": normalize_node_status(row.status),
                "progress_percent": row.progress_percent,
                "retry_count": row.retry_count,
                "retry_limit": row.retry_limit,
                "runtime_meta": row.runtime_meta if isinstance(row.runtime_meta, dict) else {},
                "last_error_code": row.last_error_code,
                "updated_at": row.updated_at,
            }
            for row in rows
        ]

    asset_matrix: Dict[str, Dict[str, Any]] = {}
    for node in pipeline_nodes:
        if str(node.get("node_name") or "") != "asset_generation":
            continue
        sid = str(node.get("scene_id") or "").strip()
        at = str(node.get("asset_type") or "").strip()
        if not sid or not at:
            continue
        asset_matrix.setdefault(sid, {})[at] = {
            "status": node.get("status"),
            "progress_percent": node.get("progress_percent"),
            "last_error_code": node.get("last_error_code"),
            "updated_at": node.get("updated_at"),
        }

    return {
        "project_id": int(episode.project_id),
        "episode_id": int(episode_id),
        "scene_units": scene_units,
        "pipeline_nodes": pipeline_nodes,
        "asset_matrix": asset_matrix,
    }


@router.get("/prompts/scene-analysis/progress/projects/{project_id}/overview")
async def get_project_progress_overview(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_project_access(db, project_id, current_user)
    episode_ids = [int(e.id) for e in db.query(Episode).filter(
        Episode.project_id == int(project_id),
        _active_episode_clause(),
    ).all()]

    nodes = []
    if ScriptProgressPipelineNode is not None:
        nodes = (
            db.query(ScriptProgressPipelineNode)
            .filter(ScriptProgressPipelineNode.project_id == int(project_id))
            .all()
        )
    issues = []
    if ScriptProgressIssue is not None:
        issues = (
            db.query(ScriptProgressIssue)
            .filter(
                ScriptProgressIssue.project_id == int(project_id),
                ScriptProgressIssue.status != "resolved",
            )
            .all()
        )
    scenes_total = 0
    scenes_done = 0
    if ScriptProgressSceneUnit is not None:
        scene_rows = (
            db.query(ScriptProgressSceneUnit)
            .filter(ScriptProgressSceneUnit.project_id == int(project_id))
            .all()
        )
        scenes_total = len(scene_rows)
        scenes_done = sum(1 for row in scene_rows if str(row.import_status or "").lower() == "success")

    status_counts = {
        "queued": 0,
        "running": 0,
        "success": 0,
        "warning": 0,
        "failed": 0,
        "blocked": 0,
        "skipped": 0,
    }
    for row in nodes:
        status_counts[normalize_node_status(getattr(row, "status", None))] += 1

    total_nodes = len(nodes)
    done_nodes = status_counts["success"] + status_counts["skipped"]
    progress_percent = (float(done_nodes) / float(total_nodes) * 100.0) if total_nodes > 0 else 0.0
    overall_status = "running"
    if status_counts["failed"] > 0 or any(str(getattr(i, "severity", "")).upper() == "BLOCKER" for i in issues):
        overall_status = "failed"
    elif status_counts["blocked"] > 0:
        overall_status = "blocked"
    elif total_nodes > 0 and done_nodes >= total_nodes:
        overall_status = "success"
    elif total_nodes == 0:
        overall_status = "queued"

    issue_blockers = sum(1 for i in issues if str(getattr(i, "severity", "")).upper() == "BLOCKER")
    issue_warnings = sum(1 for i in issues if str(getattr(i, "severity", "")).upper() == "WARNING")
    issue_infos = sum(1 for i in issues if str(getattr(i, "severity", "")).upper() == "INFO")

    return {
        "project_id": int(project_id),
        "episode_ids": episode_ids,
        "overall_status": overall_status,
        "progress_percent": round(progress_percent, 2),
        "counts": {
            "pipeline_nodes_total": total_nodes,
            "pipeline_nodes_done": done_nodes,
            "running": status_counts["running"],
            "failed": status_counts["failed"],
            "blocked": status_counts["blocked"],
            "warning": status_counts["warning"],
            "scenes_total": scenes_total,
            "scenes_imported": scenes_done,
            "issues_open": len(issues),
            "issues_blocker": issue_blockers,
            "issues_warning": issue_warnings,
            "issues_info": issue_infos,
        },
    }


@router.get("/prompts/scene-analysis/progress/projects/{project_id}/issues")
async def get_project_progress_issues(
    project_id: int,
    episode_id: Optional[int] = Query(None),
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_project_access(db, project_id, current_user)
    if ScriptProgressIssue is None:
        return {"project_id": int(project_id), "issues": []}
    query = db.query(ScriptProgressIssue).filter(ScriptProgressIssue.project_id == int(project_id))
    if episode_id is not None:
        query = query.filter(ScriptProgressIssue.episode_id == int(episode_id))
    if severity:
        query = query.filter(ScriptProgressIssue.severity == str(severity).upper())
    if status:
        query = query.filter(ScriptProgressIssue.status == str(status).lower())
    rows = query.order_by(ScriptProgressIssue.updated_at.desc(), ScriptProgressIssue.id.desc()).all()
    return {
        "project_id": int(project_id),
        "issues": [
            {
                "id": int(row.id),
                "episode_id": row.episode_id,
                "script_id": row.script_id,
                "scene_id": row.scene_id,
                "severity": row.severity,
                "status": row.status,
                "issue_code": row.issue_code,
                "title": row.title,
                "details": row.details,
                "owner_domain": row.owner_domain,
                "node_ref": row.node_ref,
                "first_seen_at": row.first_seen_at,
                "last_seen_at": row.last_seen_at,
                "updated_at": row.updated_at,
            }
            for row in rows
        ],
    }


@router.post("/prompts/scene-analysis/progress/issues/resolve")
async def resolve_project_progress_issue(
    request: ProgressIssueResolveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if ScriptProgressIssue is None:
        raise HTTPException(status_code=404, detail="progress issue storage not enabled")
    issue = db.query(ScriptProgressIssue).filter(ScriptProgressIssue.id == int(request.issue_id)).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    _require_project_access(db, int(issue.project_id), current_user)
    ok = resolve_progress_issue(db, issue_id=int(request.issue_id))
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to resolve issue")
    db.commit()
    return {"status": "ok", "issue_id": int(request.issue_id)}


@router.post("/prompts/scene-analysis/progress/auto-orchestrate")
async def auto_orchestrate_scene_progress(
    request: ProgressAutoOrchestrateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == int(request.episode_id)).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)
    if int(request.project_id) != int(episode.project_id):
        raise HTTPException(status_code=400, detail="project_id does not match episode.project_id")

    scene_rows = _list_episode_scene_progress_rows(
        db,
        project_id=int(request.project_id),
        episode_id=int(request.episode_id),
        scene_ids=request.scene_ids,
    )
    if not scene_rows:
        raise HTTPException(status_code=400, detail="No scene progress units available. Sync scene units first.")

    marker_scene_ids = [str(getattr(row, "scene_id", "")).strip() for row in scene_rows if str(getattr(row, "scene_id", "")).strip()]
    db_scene_map: Dict[str, Scene] = {}
    unresolved_scene_ids: List[str] = []
    for marker_scene_id in marker_scene_ids:
        matched = _resolve_scene_id_to_db_scene(db, episode_id=int(request.episode_id), scene_marker_id=marker_scene_id)
        if matched is None:
            unresolved_scene_ids.append(marker_scene_id)
            raise_progress_issue(
                db,
                project_id=int(request.project_id),
                episode_id=int(request.episode_id),
                script_id=f"episode:{int(request.episode_id)}",
                scene_id=marker_scene_id,
                issue_code="SCENE_IMPORT_FAILED",
                title="Scene marker cannot map to saved scene",
                severity="BLOCKER",
                owner_domain="scene-orchestrator",
                node_ref="scene_import",
                details=f"Unable to find scene row for marker scene_id={marker_scene_id}",
            )
            upsert_pipeline_node_status(
                db,
                project_id=int(request.project_id),
                episode_id=int(request.episode_id),
                script_id=f"episode:{int(request.episode_id)}",
                scene_id=marker_scene_id,
                node_name="scene_import",
                status="failed",
                error_code="SCENE_IMPORT_FAILED",
                error_message=f"scene marker not found in db scene table: {marker_scene_id}",
            )
            continue
        db_scene_map[marker_scene_id] = matched

    if unresolved_scene_ids:
        db.commit()
        return {
            "status": "partial_failed",
            "message": "Some marker scene ids are not mapped to scene rows",
            "unresolved_scene_ids": unresolved_scene_ids,
        }

    scene_db_ids = [int(db_scene_map[sid].id) for sid in marker_scene_ids if sid in db_scene_map]
    for sid in marker_scene_ids:
        upsert_pipeline_node_status(
            db,
            project_id=int(request.project_id),
            episode_id=int(request.episode_id),
            script_id=f"episode:{int(request.episode_id)}",
            scene_id=sid,
            node_name="scene_import",
            status="success",
            progress_percent=100.0,
        )
        row = next((r for r in scene_rows if str(getattr(r, "scene_id", "")).strip() == sid), None)
        if row is not None:
            row.import_status = "success"
            row.updated_at = now_bj_iso()

    # Trigger storyboard per selected scenes (batch executor supports scene_ids)
    try:
        upsert_pipeline_node_status(
            db,
            project_id=int(request.project_id),
            episode_id=int(request.episode_id),
            script_id=f"episode:{int(request.episode_id)}",
            node_name="storyboard_generation",
            status="running",
            progress_percent=10.0,
            depends_on=["scene_import"],
            runtime_meta={
                "scene_db_ids": scene_db_ids,
                "scene_marker_ids": marker_scene_ids,
                "batch_type": "scene_ai_shots",
            },
        )
        _start_scene_ai_shots_batch_for_episode(
            db=db,
            episode=episode,
            current_user=current_user,
            scene_ids=scene_db_ids,
            function_name=request.function_name,
            system_api_id=request.system_api_id,
        )
    except Exception as exc:
        upsert_pipeline_node_status(
            db,
            project_id=int(request.project_id),
            episode_id=int(request.episode_id),
            script_id=f"episode:{int(request.episode_id)}",
            node_name="storyboard_generation",
            status="failed",
            error_code="STORYBOARD_JOB_FAILED",
            error_message=str(exc),
        )
        raise_progress_issue(
            db,
            project_id=int(request.project_id),
            episode_id=int(request.episode_id),
            script_id=f"episode:{int(request.episode_id)}",
            issue_code="STORYBOARD_JOB_FAILED",
            title="Storyboard batch start failed",
            severity="BLOCKER",
            owner_domain="storyboard-engine",
            node_ref="storyboard_generation",
            details=str(exc),
        )
        db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to start storyboard generation: {exc}")

    # Trigger per-scene asset generation by type through existing analyze_scene endpoint
    requested_asset_types = _normalize_asset_types(request.asset_types)
    asset_node_by_type = {
        "character": "asset_design_character",
        "prop": "asset_design_prop",
        "environment": "asset_design_environment",
        "poster": "asset_design_environment",
    }
    prompt_by_type = {
        "character": "skills/scene_analysis_feature_stack/entity_design_character.md",
        "prop": "skills/scene_analysis_feature_stack/entity_design_prop.md",
        "environment": "skills/scene_analysis_feature_stack/entity_design_environment_and_poster.md",
        "poster": "skills/scene_analysis_feature_stack/entity_design_environment_and_poster.md",
    }
    assets_dispatched: List[Dict[str, Any]] = []
    for marker_scene_id in marker_scene_ids:
        mapped_scene = db_scene_map.get(marker_scene_id)
        if mapped_scene is None:
            continue
        scene_text = str(getattr(mapped_scene, "original_script_text", "") or "").strip()
        for asset_type in requested_asset_types:
            node_name = asset_node_by_type.get(asset_type, "asset_design_environment")
            prompt_file = prompt_by_type.get(asset_type) or "skills/scene_analysis_feature_stack/entity_design_environment_and_poster.md"
            upsert_pipeline_node_status(
                db,
                project_id=int(request.project_id),
                episode_id=int(request.episode_id),
                script_id=f"episode:{int(request.episode_id)}",
                scene_id=marker_scene_id,
                node_name="asset_generation",
                asset_type=asset_type,
                status="queued",
                progress_percent=0.0,
                depends_on=["scene_import"],
                runtime_meta={"task_id": "", "kind": f"asset_generation_{asset_type}"},
            )
            tid = _submit_async(
                analyze_scene,
                user_id=current_user.id,
                kind=f"asset_generation_{asset_type}",
                req=AnalyzeSceneRequest(
                    text=scene_text or f"Scene {marker_scene_id}",
                    project_id=int(request.project_id),
                    episode_id=int(request.episode_id),
                    prompt_file=prompt_file,
                    function_name=request.function_name or "script_analysis",
                    system_api_id=request.system_api_id,
                ),
                async_mode="0",
            )
            upsert_pipeline_node_status(
                db,
                project_id=int(request.project_id),
                episode_id=int(request.episode_id),
                script_id=f"episode:{int(request.episode_id)}",
                scene_id=marker_scene_id,
                node_name="asset_generation",
                asset_type=asset_type,
                status="running",
                progress_percent=15.0,
                runtime_meta={"task_id": tid, "kind": f"asset_generation_{asset_type}"},
            )
            assets_dispatched.append(
                {
                    "scene_id": marker_scene_id,
                    "asset_type": asset_type,
                    "task_id": tid,
                    "node_name": node_name,
                }
            )

    db.commit()
    return {
        "status": "started",
        "project_id": int(request.project_id),
        "episode_id": int(request.episode_id),
        "scene_ids": marker_scene_ids,
        "scene_db_ids": scene_db_ids,
        "storyboard_started": True,
        "assets_dispatched": assets_dispatched,
    }


@router.post("/prompts/scene-analysis/progress/reconcile")
async def reconcile_progress_status(
    request: ProgressReconcileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == int(request.episode_id)).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)
    if int(request.project_id) != int(episode.project_id):
        raise HTTPException(status_code=400, detail="project_id does not match episode.project_id")

    updated_asset_nodes = 0
    updated_storyboard_nodes = 0

    if ScriptProgressPipelineNode is not None:
        asset_nodes = (
            db.query(ScriptProgressPipelineNode)
            .filter(
                ScriptProgressPipelineNode.project_id == int(request.project_id),
                ScriptProgressPipelineNode.episode_id == int(request.episode_id),
                ScriptProgressPipelineNode.node_name == "asset_generation",
            )
            .all()
        )
        for row in asset_nodes:
            meta = row.runtime_meta if isinstance(row.runtime_meta, dict) else {}
            task_id = str(meta.get("task_id") or "").strip()
            if not task_id:
                continue
            info = _get_task_status(task_id, user_id=current_user.id) or _get_task_status(task_id)
            if not isinstance(info, dict):
                continue
            task_status = str(info.get("status") or "").strip().lower()
            next_status = None
            next_progress = None
            error_code = None
            error_message = None
            if task_status == "completed":
                next_status = "success"
                next_progress = 100.0
            elif task_status == "failed":
                next_status = "failed"
                next_progress = float(row.progress_percent or 0.0)
                error_code = "ASSET_TYPE_JOB_FAILED"
                error_message = str(info.get("error") or "asset task failed")
            elif task_status == "canceled":
                next_status = "blocked"
                error_code = "ASSET_TYPE_JOB_CANCELED"
                error_message = str(info.get("error") or "asset task canceled")
            elif task_status in {"running", "pending"}:
                next_status = "running"
                next_progress = max(float(row.progress_percent or 0.0), 20.0)
            if next_status is None:
                continue

            current_status = normalize_node_status(getattr(row, "status", None))
            if current_status == next_status and (next_progress is None or abs(float(row.progress_percent or 0.0) - float(next_progress)) < 0.001):
                continue
            upsert_pipeline_node_status(
                db,
                project_id=int(request.project_id),
                episode_id=int(request.episode_id),
                script_id=row.script_id,
                scene_id=row.scene_id,
                node_name="asset_generation",
                asset_type=row.asset_type,
                status=next_status,
                progress_percent=(next_progress if next_progress is not None else row.progress_percent),
                runtime_meta=meta,
                error_code=error_code,
                error_message=error_message,
            )
            updated_asset_nodes += 1
            if next_status in {"failed", "blocked"}:
                raise_progress_issue(
                    db,
                    project_id=int(request.project_id),
                    episode_id=int(request.episode_id),
                    script_id=row.script_id,
                    scene_id=row.scene_id,
                    issue_code=error_code or "ASSET_TYPE_JOB_FAILED",
                    title="Asset type job did not complete successfully",
                    severity="WARNING",
                    owner_domain="asset-worker",
                    node_ref="asset_generation",
                    details=error_message,
                )

        storyboard_nodes = (
            db.query(ScriptProgressPipelineNode)
            .filter(
                ScriptProgressPipelineNode.project_id == int(request.project_id),
                ScriptProgressPipelineNode.episode_id == int(request.episode_id),
                ScriptProgressPipelineNode.node_name == "storyboard_generation",
            )
            .all()
        )
        batch_status = _read_scene_ai_shots_batch_status(episode)
        running = bool(batch_status.get("running"))
        failed = int(batch_status.get("failed") or 0)
        total = int(batch_status.get("total") or 0)
        completed = int(batch_status.get("completed") or 0)
        next_storyboard_status = "running" if running else ("failed" if failed > 0 and completed < total else "success")
        next_storyboard_progress = (float(completed) / float(total) * 100.0) if total > 0 else (10.0 if running else 100.0)
        storyboard_error = None
        storyboard_error_message = None
        if next_storyboard_status == "failed":
            storyboard_error = "STORYBOARD_JOB_FAILED"
            storyboard_error_message = str(batch_status.get("message") or "storyboard batch failed")

        for row in storyboard_nodes:
            cur = normalize_node_status(getattr(row, "status", None))
            if cur == next_storyboard_status and abs(float(row.progress_percent or 0.0) - float(next_storyboard_progress)) < 0.001:
                continue
            upsert_pipeline_node_status(
                db,
                project_id=int(request.project_id),
                episode_id=int(request.episode_id),
                script_id=row.script_id,
                scene_id=row.scene_id,
                node_name="storyboard_generation",
                status=next_storyboard_status,
                progress_percent=next_storyboard_progress,
                runtime_meta=row.runtime_meta if isinstance(row.runtime_meta, dict) else {},
                error_code=storyboard_error,
                error_message=storyboard_error_message,
            )
            updated_storyboard_nodes += 1
        if next_storyboard_status == "failed":
            raise_progress_issue(
                db,
                project_id=int(request.project_id),
                episode_id=int(request.episode_id),
                script_id=f"episode:{int(request.episode_id)}",
                issue_code="STORYBOARD_JOB_FAILED",
                title="Storyboard batch failed",
                severity="BLOCKER",
                owner_domain="storyboard-engine",
                node_ref="storyboard_generation",
                details=storyboard_error_message,
            )

        # best-effort mark scene import success for scenes with finished storyboard
        if ScriptProgressSceneUnit is not None and total > 0 and completed > 0:
            db_scenes = db.query(Scene).filter(
                Scene.episode_id == int(request.episode_id),
                _active_scene_clause(),
            ).all()
            scene_ids_done = set()
            if next_storyboard_status == "success":
                scene_ids_done = {_normalize_scene_marker_id_from_scene(s, int(request.episode_id)) for s in db_scenes}
            for row in (
                db.query(ScriptProgressSceneUnit)
                .filter(
                    ScriptProgressSceneUnit.project_id == int(request.project_id),
                    ScriptProgressSceneUnit.episode_id == int(request.episode_id),
                )
                .all()
            ):
                if row.scene_id in scene_ids_done:
                    row.import_status = "success"
                    row.updated_at = now_bj_iso()

    db.commit()
    return {
        "status": "ok",
        "project_id": int(request.project_id),
        "episode_id": int(request.episode_id),
        "updated_asset_nodes": int(updated_asset_nodes),
        "updated_storyboard_nodes": int(updated_storyboard_nodes),
    }


@router.post("/prompts/scene-analysis/flow/run-node")
async def run_scene_analysis_flow_node(
    request: ScriptAnalysisFlowRunNodeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    """Run one workflow node through its existing executor while preserving node-specific injection chains."""
    node_key = str(getattr(request, "node_key", "") or "").strip().lower().replace("-", "_")
    if async_mode == "1":
        tid = _submit_async(
            run_scene_analysis_flow_node,
            user_id=current_user.id,
            kind=f"script_analysis_flow_{node_key or 'unknown'}",
            request=request,
            async_mode="0",
        )
        return JSONResponse({
            "task_id": tid,
            "async": True,
            "node_key": node_key,
        })

    flow_started_perf = time.perf_counter()
    cfg = get_script_analysis_flow_config(db)
    registry = get_script_analysis_flow_registry(cfg)
    nodes = {str(node.get("key") or ""): node for node in (registry.get("nodes") or [])}
    node = nodes.get(node_key)
    if not node:
        raise HTTPException(status_code=404, detail=f"Script analysis flow node '{node_key}' not found")

    analyze_node_keys = {
        "script_optimization",
        "assets_extraction",
        "scene_markdown",
        "asset_design_character",
        "asset_design_prop",
        "asset_design_environment",
    }
    if node_key in analyze_node_keys:
        raw_payload = dict(request.analyze_payload or {})
        if not raw_payload.get("text"):
            raise HTTPException(status_code=400, detail="analyze_payload.text is required for this workflow node")
        raw_payload["prompt_file"] = raw_payload.get("prompt_file") or node.get("prompt_file")
        raw_payload["function_name"] = raw_payload.get("function_name") or request.function_name or "script_analysis"
        raw_payload["system_api_id"] = raw_payload.get("system_api_id") or request.system_api_id
        
        logger.info(
            "[剧本分析流程] 准备执行节点 %s | prompt=%s | function=%s | system_api_id=%s | project_id=%s | episode_id=%s",
            node_key,
            raw_payload.get("prompt_file"),
            raw_payload.get("function_name"),
            raw_payload.get("system_api_id"),
            raw_payload.get("project_id"),
            raw_payload.get("episode_id"),
        )
        
        if request.project_id and not raw_payload.get("project_id"):
            raw_payload["project_id"] = request.project_id
        if request.episode_id and not raw_payload.get("episode_id"):
            raw_payload["episode_id"] = request.episode_id
        if raw_payload.get("episode_id"):
            episode = db.query(Episode).filter(Episode.id == int(raw_payload.get("episode_id"))).first()
            if not episode:
                raise HTTPException(status_code=404, detail="Episode not found")
            if bool(getattr(episode, "is_deleted", False)):
                raise HTTPException(status_code=404, detail="Episode not found or has been deleted")
            _require_project_access(db, episode.project_id, current_user)
            if raw_payload.get("project_id") and int(raw_payload.get("project_id")) != int(episode.project_id):
                raise HTTPException(status_code=400, detail="project_id does not match episode.project_id")
            # Scene orchestration / asset design must not start without a usable Subject Index.
            if node_key in {
                "scene_markdown",
                "asset_design_character",
                "asset_design_prop",
                "asset_design_environment",
            }:
                gate_subject_index = resolve_usable_episode_subject_index(
                    episode,
                    request_text=raw_payload.get("text"),
                    explicit_subject_index=raw_payload.get("subject_index_text"),
                    heal_episode_field=True,
                    db=db,
                )
                if not _subject_index_has_usable_content(gate_subject_index):
                    logger.error(
                        "[剧本分析流程] subject_index_required_blocking node=%s episode_id=%s "
                        "episode_si_chars=%s stage_outputs_chars=%s explicit_si_chars=%s text_chars=%s",
                        node_key,
                        getattr(episode, "id", None),
                        len(str(getattr(episode, "ai_scene_analysis_subject_index", "") or "")),
                        len(str(getattr(episode, "ai_stage_outputs", "") or "")),
                        len(str(raw_payload.get("subject_index_text") or "")),
                        len(str(raw_payload.get("text") or "")),
                    )
                    raise HTTPException(
                        status_code=400,
                        detail=_build_scene_analysis_blocking_failure_detail(
                            ["ANALYSIS_SUBJECT_INDEX_REQUIRED"],
                            [],
                            [
                                "缺少资产清单（Subject Index），无法继续场景编排或资产生成。请先完成第二阶段资产提取后再重试。"
                            ],
                        ),
                    )
        elif raw_payload.get("project_id"):
            _require_project_access(db, int(raw_payload.get("project_id")), current_user)
            
        node_project_id = int(raw_payload.get("project_id") or request.project_id or 0)
        node_episode_id = int(raw_payload.get("episode_id") or request.episode_id or 0)
        if node_project_id > 0 and node_episode_id > 0:
            upsert_pipeline_node_status(
                db,
                project_id=node_project_id,
                episode_id=node_episode_id,
                script_id=f"episode:{node_episode_id}",
                node_name=node_key,
                status="running",
                progress_percent=5.0,
            )
            db.commit()

        llm_started_perf = time.perf_counter()
        logger.info("[剧本分析流程] 开始调用 evaluate_scene 执行节点 %s...", node_key)
        try:
            if node_key == "assets_extraction":
                # Slim Stage 1 script to per-scene ENV_BLOCK + Beats before Subject Index LLM.
                try:
                    original_text = str(raw_payload.get("text") or "")
                    adapted_for_assets = extract_adapted_script_from_beats_user_input(original_text)
                    if not adapted_for_assets.strip():
                        wrapped = unwrap_injection_section(original_text, "优化后剧本")
                        if wrapped:
                            adapted_for_assets = re.sub(
                                r"^\[[^\]]+\]\s*\n?",
                                "",
                                str(wrapped),
                            ).strip()
                    if adapted_for_assets.strip():
                        slim_script = build_assets_extraction_script_from_adapted(adapted_for_assets)
                        if slim_script.strip() and slim_script.strip() != adapted_for_assets.strip():
                            raw_payload["text"] = _replace_adapted_script_in_beats_user_input(
                                original_text,
                                slim_script,
                            )
                            logger.info(
                                "[剧本分析流程] assets_extraction 已替换为角色设定+逐场环境+Beat 输入 | chars=%s→%s",
                                len(adapted_for_assets),
                                len(slim_script),
                            )
                except Exception as slim_exc:
                    logger.warning(
                        "[剧本分析流程] assets_extraction env+beat slim failed; using original text | err=%s",
                        slim_exc,
                    )
                max_attempts = 2
                result = None
                assets_cover_poster_missing_after_retries = False
                for attempt in range(1, max_attempts + 1):
                    result = await analyze_scene(AnalyzeSceneRequest(**raw_payload), current_user=current_user, db=db, async_mode="0")
                    result_text = _extract_analysis_text_from_result(result)
                    has_cover_poster = _subject_index_has_cover_poster(result_text)
                    if has_cover_poster:
                        if attempt > 1:
                            logger.info(
                                "[剧本分析流程] 节点 %s 在重试后通过 cover_poster 校验 | attempt=%s",
                                node_key,
                                attempt,
                            )
                        break
                    logger.warning(
                        "[剧本分析流程] 节点 %s 缺少 cover_poster/poster 条目 | attempt=%s/%s",
                        node_key,
                        attempt,
                        max_attempts,
                    )
                    if attempt >= max_attempts:
                        assets_cover_poster_missing_after_retries = True
                        logger.warning(
                            "[剧本分析流程] 节点 %s 在重试后仍缺少 cover_poster/poster，按非阻断告警继续 | episode_id=%s",
                            node_key,
                            node_episode_id,
                        )
                        break
                    upsert_pipeline_node_status(
                        db,
                        project_id=node_project_id,
                        episode_id=node_episode_id,
                        script_id=f"episode:{node_episode_id}",
                        node_name=node_key,
                        status="running",
                        progress_percent=15.0,
                        error_code="ASSETS_EXTRACTION_COVER_POSTER_MISSING",
                        error_message="cover_poster/poster missing, auto-retrying once",
                    )
                    db.commit()
                if assets_cover_poster_missing_after_retries and node_project_id > 0 and node_episode_id > 0:
                    upsert_pipeline_node_status(
                        db,
                        project_id=node_project_id,
                        episode_id=node_episode_id,
                        script_id=f"episode:{node_episode_id}",
                        node_name=node_key,
                        status="running",
                        progress_percent=85.0,
                        error_code="ASSETS_EXTRACTION_COVER_POSTER_MISSING",
                        error_message="cover_poster/poster missing after retries; continued as non-blocking warning",
                    )
                    db.commit()
            elif node_key == "script_optimization":
                max_attempts = 2
                result = None
                for attempt in range(1, max_attempts + 1):
                    result = await analyze_scene(AnalyzeSceneRequest(**raw_payload), current_user=current_user, db=db, async_mode="0")
                    result_text = _extract_analysis_text_from_result(result)
                    has_visual_backfill = _script_optimization_has_project_visual_backfill(result_text)
                    if has_visual_backfill:
                        if attempt > 1:
                            logger.info(
                                "[剧本分析流程] 节点 %s 在重试后通过 Project Visual Backfill 校验 | attempt=%s",
                                node_key,
                                attempt,
                            )
                        break
                    logger.warning(
                        "[剧本分析流程] 节点 %s 缺少 Project Visual Backfill | attempt=%s/%s",
                        node_key,
                        attempt,
                        max_attempts,
                    )
                    if attempt >= max_attempts:
                        raise HTTPException(
                            status_code=422,
                            detail="SCRIPT_OPTIMIZATION_PROJECT_VISUAL_BACKFILL_MISSING",
                        )
                    upsert_pipeline_node_status(
                        db,
                        project_id=node_project_id,
                        episode_id=node_episode_id,
                        script_id=f"episode:{node_episode_id}",
                        node_name=node_key,
                        status="running",
                        progress_percent=15.0,
                        error_code="SCRIPT_OPTIMIZATION_PROJECT_VISUAL_BACKFILL_MISSING",
                        error_message="project_visual_backfill missing, auto-retrying once",
                    )
                    db.commit()
            elif node_key == "scene_markdown":
                result = await _run_scene_markdown_node_per_scene(
                    raw_payload=raw_payload,
                    current_user=current_user,
                    db=db,
                    node_project_id=node_project_id,
                    node_episode_id=node_episode_id,
                )
            else:
                result = await analyze_scene(AnalyzeSceneRequest(**raw_payload), current_user=current_user, db=db, async_mode="0")
        except Exception as exc:
            if node_project_id > 0 and node_episode_id > 0:
                error_text = str(exc or "")
                if isinstance(exc, HTTPException):
                    error_text = str(getattr(exc, "detail", "") or error_text)
                error_code = (
                    "ASSETS_EXTRACTION_COVER_POSTER_MISSING"
                    if "ASSETS_EXTRACTION_COVER_POSTER_MISSING" in error_text
                    else (
                        "SCRIPT_OPTIMIZATION_PROJECT_VISUAL_BACKFILL_MISSING"
                        if "SCRIPT_OPTIMIZATION_PROJECT_VISUAL_BACKFILL_MISSING" in error_text
                        else "FLOW_RUN_NODE_FAILED"
                    )
                )
                upsert_pipeline_node_status(
                    db,
                    project_id=node_project_id,
                    episode_id=node_episode_id,
                    script_id=f"episode:{node_episode_id}",
                    node_name=node_key,
                    status="failed",
                    error_code=error_code,
                    error_message=str(exc),
                )
                db.commit()
            raise
        llm_elapsed_ms = int((time.perf_counter() - llm_started_perf) * 1000)
        logger.info("[剧本分析流程] 节点 %s 执行完成 | llm_elapsed_ms=%s", node_key, llm_elapsed_ms)

        if node_project_id > 0 and node_episode_id > 0:
            if node_key != "scene_markdown":
                upsert_pipeline_node_status(
                    db,
                    project_id=node_project_id,
                    episode_id=node_episode_id,
                    script_id=f"episode:{node_episode_id}",
                    node_name=node_key,
                    status="success",
                    progress_percent=100.0,
                )

            if node_key == "scene_markdown":
                # Step 4: parallel orchestration imports each scene as soon as LLM returns;
                # only the single-call path needs a bulk import here.
                scene_markdown_started_perf = time.perf_counter()
                per_scene_parallel = isinstance(result, dict) and bool(result.get("per_scene_parallel"))
                try:
                    import_started_perf = time.perf_counter()
                    if per_scene_parallel:
                        per_scene_outputs = (result or {}).get("per_scene_outputs") or []
                        logger.info(
                            "[场景编排2.2] Step 4 skipped bulk import; per-scene imports completed during orchestration | project_id=%s | episode_id=%s | scene_count=%s",
                            node_project_id,
                            node_episode_id,
                            len(per_scene_outputs),
                        )
                        import_result = {
                            "scene_count": len(per_scene_outputs),
                            "scene_ids": [
                                str(item.get("scene_id") or "").strip()
                                for item in per_scene_outputs
                                if str(item.get("scene_id") or "").strip()
                            ],
                            "parse_source": "per_scene_parallel",
                        }
                    else:
                        logger.info(
                            "[场景编排2.2] Step 4 开始导入场景单元 | project_id=%s | episode_id=%s",
                            node_project_id,
                            node_episode_id,
                        )
                        import_result = import_analyze_scene_stage_result(
                            db=db,
                            stage_key=STAGE_SCENE_MARKDOWN,
                            project_id=node_project_id,
                            episode_id=node_episode_id,
                            analyze_result=result,
                            script_id=f"episode:{node_episode_id}",
                        ) or {}
                    import_elapsed_ms = int((time.perf_counter() - import_started_perf) * 1000)
                    logger.info(
                        "[场景编排2.2] Step 4 场景单元导入完成 | project_id=%s | episode_id=%s | scene_count=%s | scene_ids=%s | parse_source=%s | import_elapsed_ms=%s",
                        node_project_id,
                        node_episode_id,
                        int(import_result.get("scene_count") or 0),
                        import_result.get("scene_ids") or [],
                        import_result.get("parse_source") or "unknown",
                        import_elapsed_ms,
                    )
                    upsert_pipeline_node_status(
                        db,
                        project_id=node_project_id,
                        episode_id=node_episode_id,
                        script_id=f"episode:{node_episode_id}",
                        node_name=node_key,
                        status="success",
                        progress_percent=100.0,
                    )
                    upsert_pipeline_node_status(
                        db,
                        project_id=node_project_id,
                        episode_id=node_episode_id,
                        script_id=f"episode:{node_episode_id}",
                        node_name="scene_planning",
                        status="success",
                        progress_percent=100.0,
                    )
                except HTTPException as import_http_exc:
                    import_detail = str(getattr(import_http_exc, "detail", "") or "")
                    if import_detail == "SCENE_MARKDOWN_EMPTY":
                        logger.warning(
                            "[场景编排2.2] scene_markdown 节点返回空文本，跳过 scene_units 同步 | project_id=%s | episode_id=%s",
                            node_project_id,
                            node_episode_id,
                        )
                        upsert_pipeline_node_status(
                            db,
                            project_id=node_project_id,
                            episode_id=node_episode_id,
                            script_id=f"episode:{node_episode_id}",
                            node_name=node_key,
                            status="failed",
                            error_code="SCENE_MARKDOWN_EMPTY",
                            error_message="scene_markdown node returned empty text",
                        )
                        db.commit()
                        raise
                    raise
                except Exception as parse_exc:
                    logger.exception(
                        "[场景编排2.2] 场景解析/同步失败 | project_id=%s | episode_id=%s | error=%s",
                        node_project_id,
                        node_episode_id,
                        parse_exc,
                    )
                    parse_error_code = str(getattr(parse_exc, "code", "") or "SCENE_PARSE_ERROR")
                    upsert_pipeline_node_status(
                        db,
                        project_id=node_project_id,
                        episode_id=node_episode_id,
                        script_id=f"episode:{node_episode_id}",
                        node_name=node_key,
                        status="failed",
                        error_code=parse_error_code,
                        error_message=str(parse_exc),
                    )
                    upsert_pipeline_node_status(
                        db,
                        project_id=node_project_id,
                        episode_id=node_episode_id,
                        script_id=f"episode:{node_episode_id}",
                        node_name="scene_planning",
                        status="failed",
                        error_code=parse_error_code,
                        error_message=str(parse_exc),
                    )
                    db.commit()
                    raise HTTPException(status_code=422, detail=parse_error_code)
                scene_markdown_elapsed_ms = int((time.perf_counter() - scene_markdown_started_perf) * 1000)
                logger.info(
                    "[场景编排2.2] 节点后处理完成 | project_id=%s | episode_id=%s | post_elapsed_ms=%s",
                    node_project_id,
                    node_episode_id,
                    scene_markdown_elapsed_ms,
                )
            db.commit()
            logger.info(
                "[剧本分析流程] 节点状态已提交 | node_key=%s | project_id=%s | episode_id=%s",
                node_key,
                node_project_id,
                node_episode_id,
            )
        flow_elapsed_ms = int((time.perf_counter() - flow_started_perf) * 1000)
        logger.info("[剧本分析流程] 节点完成返回 | node_key=%s | total_elapsed_ms=%s", node_key, flow_elapsed_ms)
        
        return {
            "status": "completed",
            "node_key": node_key,
            "executor": node.get("executor") or "analyze_scene",
            "prompt_file": node.get("prompt_file"),
            "injection_chain": node.get("injection_chain") or [],
            "result": result,
        }

    if node_key == "storyboard_generation":
        episode_id = int(getattr(request, "episode_id", None) or 0)
        if episode_id <= 0:
            raise HTTPException(status_code=400, detail="episode_id is required for storyboard_generation")

        episode = db.query(Episode).filter(Episode.id == episode_id).first()
        if not episode:
            raise HTTPException(status_code=404, detail="Episode not found")
        if bool(getattr(episode, "is_deleted", False)):
            raise HTTPException(status_code=404, detail="Episode not found or has been deleted")
        _require_project_access(db, episode.project_id, current_user)

        if request.project_id and int(request.project_id) != int(episode.project_id):
            logger.warning(f"[剧本分析流程] 校验失败: 节点 {node_key} 请求的 project_id 不匹配")
            raise HTTPException(status_code=400, detail="project_id does not match episode.project_id")

        logger.info(f"[剧本分析流程] 准备委托批量任务执行分镜节点 {node_key} | 目标集: {episode_id} | 指定场景: {request.scene_ids}")
        status_payload = _start_scene_ai_shots_batch_for_episode(
            db=db,
            episode=episode,
            current_user=current_user,
            scene_ids=request.scene_ids or [],
            function_name=request.function_name,
            system_api_id=request.system_api_id,
        )
        return {
            "status": "started",
            "node_key": node_key,
            "executor": node.get("executor") or "shot_generation.batch_per_scene",
            "prompt_file": node.get("prompt_file"),
            "injection_chain": node.get("injection_chain") or [],
            "batch_status": status_payload,
        }

    logger.warning(f"[剧本分析流程] 未知或未绑定的节点: {node_key}。将返回未迁移状态。")
    return {
        "status": "planned_not_migrated",
        "node_key": node_key,
        "node": node,
        "message": "This node is registered and configurable, but no executor has been bound yet.",
    }

