# -*- coding: utf-8 -*-
"""Script progress auto-orchestrate / reconcile helpers."""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.time_utils import now_bj_iso
from app.models.all_models import Episode, Scene, User
from app.schemas.agent import AnalyzeSceneRequest
from app.services.project_access import _require_project_access
from app.services.scene_ai_shots_batch import (
    _read_scene_ai_shots_batch_status,
    _start_scene_ai_shots_batch_for_episode,
)
from app.services.script_analysis_flow import (
    ScriptProgressPipelineNode,
    ScriptProgressSceneUnit,
    normalize_node_status,
    raise_progress_issue,
    upsert_pipeline_node_status,
)
from app.services.script_progress_helpers import (
    _list_episode_scene_progress_rows,
    _normalize_asset_types,
    _normalize_scene_marker_id_from_scene,
    _resolve_scene_id_to_db_scene,
)
from app.services.soft_delete import _active_scene_clause
from app.services.task_manager import (
    get_status as _get_task_status,
    submit_async_endpoint as _submit_async,
)


async def execute_auto_orchestrate_scene_progress(
    *,
    request: Any,
    db: Session,
    current_user: User,
) -> Dict[str, Any]:
    from app.api.routers.prompts.analyze_scene import analyze_scene  # noqa: WPS433

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



async def execute_reconcile_progress_status(
    *,
    request: Any,
    db: Session,
    current_user: User,
) -> Dict[str, Any]:
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
