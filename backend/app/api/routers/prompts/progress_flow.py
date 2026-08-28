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


class EpisodeProgressResetRequest(BaseModel):
    project_id: int
    episode_id: int


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


class DerivedEnvIngestRequest(BaseModel):
    project_id: int
    episode_id: int
    scene_ids: Optional[List[str]] = None
    purge_existing: Optional[bool] = True


from app.services.script_analysis_flow_runner import (  # noqa: E402,F401
    execute_scene_analysis_flow_node,
)

from app.services.script_progress_orchestration import (  # noqa: E402,F401
    execute_auto_orchestrate_scene_progress,
    execute_reconcile_progress_status,
)
from app.services.deletion_ops import (  # noqa: E402,F401
    clear_episode_analysis_artifacts,
    reset_episode_analysis_progress,
)


@router.post("/prompts/scene-analysis/progress/sync-scene-units")
async def sync_scene_units_progress(
    request: SceneUnitsSyncRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = (
        db.query(Episode)
        .filter(Episode.id == int(request.episode_id), _active_episode_clause())
        .first()
    )
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found or has been deleted")
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
    episode = (
        db.query(Episode)
        .filter(Episode.id == int(request.episode_id), _active_episode_clause())
        .first()
    )
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found or has been deleted")
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
            scene_markdown="",
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


@router.post("/prompts/scene-analysis/progress/reset-episode")
async def reset_episode_progress(
    request: EpisodeProgressResetRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = (
        db.query(Episode)
        .filter(Episode.id == int(request.episode_id), _active_episode_clause())
        .first()
    )
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found or has been deleted")
    _require_project_access(db, episode.project_id, current_user)
    if int(request.project_id) != int(episode.project_id):
        raise HTTPException(status_code=400, detail="project_id does not match episode.project_id")

    summary = reset_episode_analysis_progress(
        db,
        project_id=int(episode.project_id),
        episode_id=int(request.episode_id),
    )
    summary["cleared_artifact_fields"] = clear_episode_analysis_artifacts(episode)
    db.commit()
    return {
        "status": "ok",
        "project_id": int(episode.project_id),
        "episode_id": int(request.episode_id),
        **summary,
    }


@router.get("/prompts/scene-analysis/progress/episodes/{episode_id}")
async def get_episode_progress_snapshot(
    episode_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = (
        db.query(Episode)
        .filter(Episode.id == int(episode_id), _active_episode_clause())
        .first()
    )
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found or has been deleted")
    _require_project_access(db, episode.project_id, current_user)
    from app.services.script_analysis_flow import finalize_stale_pipeline_nodes

    finalize_stale_pipeline_nodes(db, episode_id=int(episode_id))

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
                "last_error_message": row.last_error_message,
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
    return await execute_auto_orchestrate_scene_progress(
        request=request,
        db=db,
        current_user=current_user,
    )


@router.post("/prompts/scene-analysis/progress/reconcile")
async def reconcile_progress_status(
    request: ProgressReconcileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await execute_reconcile_progress_status(
        request=request,
        db=db,
        current_user=current_user,
    )




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
    return await execute_scene_analysis_flow_node(
        request=request,
        db=db,
        current_user=current_user,
    )


@router.post("/prompts/scene-analysis/flow/ingest-derived-environments")
def ingest_derived_environments_from_framing_endpoint(
    request: DerivedEnvIngestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rebuild derived ENV assets from each scene's 场景现场编排 output. No LLM."""
    from app.services.script_analysis_flow.derived_env_ingest import (
        regen_derived_environments_from_framing,
    )
    from app.services.soft_delete import _active_episode_clause

    _require_project_access(db, int(request.project_id), current_user, owner_only=True)
    episode = (
        db.query(Episode)
        .filter(
            Episode.id == int(request.episode_id),
            Episode.project_id == int(request.project_id),
            _active_episode_clause(),
        )
        .first()
    )
    if episode is None:
        raise HTTPException(status_code=404, detail="Episode not found")
    result = regen_derived_environments_from_framing(
        db=db,
        project_id=int(request.project_id),
        episode_id=int(request.episode_id),
        scene_ids=request.scene_ids,
        purge_existing=request.purge_existing is not False,
    )
    if not result.get("ok"):
        reason = str(result.get("reason") or "")
        if reason == "no_framing_output":
            raise HTTPException(
                status_code=422,
                detail="DERIVED_ENV_NO_FRAMING_OUTPUT",
            )
        raise HTTPException(status_code=404, detail="Episode not found")
    return result



