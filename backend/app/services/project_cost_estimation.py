# -*- coding: utf-8 -*-
"""Project cost estimation snapshot helpers."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.settings import get_project_cost_estimation_config
from app.core.time_utils import now_bj_iso
from app.models.all_models import Episode, Project, Scene, Shot
from app.services.project_cost_service import compute_project_cost_estimation
from app.services.soft_delete import (
    _active_episode_clause,
    _active_scene_clause,
    _active_shot_clause,
)

def _compute_project_cost_estimation_snapshot(db: Session, project_id: int) -> Dict[str, Any]:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    episodes = db.query(Episode).filter(
        Episode.project_id == project_id,
        _active_episode_clause(),
    ).all()
    episode_ids = [int(getattr(ep, "id", 0) or 0) for ep in episodes if getattr(ep, "id", None) is not None]
    scenes = db.query(Scene).filter(Scene.episode_id.in_(episode_ids), _active_scene_clause()).all() if episode_ids else []
    scene_ids = [int(getattr(sc, "id", 0) or 0) for sc in scenes if getattr(sc, "id", None) is not None]
    shots = db.query(Shot).filter(Shot.scene_id.in_(scene_ids), _active_shot_clause()).all() if scene_ids else []

    cfg = get_project_cost_estimation_config(db)
    snapshot = compute_project_cost_estimation(
        project_title=getattr(project, "title", "") or "",
        global_info=(project.global_info if isinstance(project.global_info, dict) else {}),
        episodes=episodes,
        scenes=scenes,
        shots=shots,
        config=cfg,
    )
    snapshot["computed_at"] = now_bj_iso()
    snapshot["project_id"] = int(project_id)
    return snapshot


def _recompute_and_persist_project_cost_estimation(db: Session, project_id: int) -> Dict[str, Any]:
    try:
        db.flush()
    except Exception:
        pass

    snapshot = _compute_project_cost_estimation_snapshot(db, project_id)
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    gi = dict(project.global_info) if isinstance(project.global_info, dict) else {}
    gi["cost_estimation"] = snapshot
    project.global_info = gi
    db.add(project)
    return snapshot


