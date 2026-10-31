# -*- coding: utf-8 -*-
"""Project cost estimation snapshot helpers."""
from __future__ import annotations

import logging
import threading
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

_logger = logging.getLogger(__name__)

# Coalesce burst shot saves (storyboard preview batch) into one trailing recompute.
# Running it on the request session held a pool connection while every parallel
# save re-read the whole project and waited on the same project row lock.
_COST_RECOMPUTE_DELAY_SECONDS = 2.0
_cost_recompute_lock = threading.Lock()
_cost_recompute_state: Dict[int, Dict[str, Any]] = {}

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


def schedule_debounced_project_cost_recompute(project_id: int) -> None:
    """Recompute project cost shortly after the request has released its connection."""
    try:
        pid = int(project_id or 0)
    except Exception:
        return
    if pid <= 0:
        return

    def _fire() -> None:
        from app.db.session import SessionLocal

        follow_up = False
        follow_timer: threading.Timer | None = None
        db = SessionLocal()
        try:
            _recompute_and_persist_project_cost_estimation(db, pid)
            db.commit()
        except Exception as exc:
            try:
                db.rollback()
            except Exception:
                pass
            _logger.warning(
                "debounced project cost recompute failed | project_id=%s err=%s",
                pid,
                exc,
            )
        finally:
            db.close()
        with _cost_recompute_lock:
            state = _cost_recompute_state.get(pid)
            if not state:
                return
            if state.get("pending"):
                state["pending"] = False
                follow_timer = threading.Timer(_COST_RECOMPUTE_DELAY_SECONDS, _fire)
                follow_timer.daemon = True
                state["timer"] = follow_timer
                follow_up = True
            else:
                _cost_recompute_state.pop(pid, None)
        if follow_up and follow_timer is not None:
            follow_timer.start()

    with _cost_recompute_lock:
        state = _cost_recompute_state.get(pid)
        if state is not None and state.get("timer") is not None:
            state["pending"] = True
            return
        timer = threading.Timer(_COST_RECOMPUTE_DELAY_SECONDS, _fire)
        timer.daemon = True
        _cost_recompute_state[pid] = {"timer": timer, "pending": False}
        timer.start()


