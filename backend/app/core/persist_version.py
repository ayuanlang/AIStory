# -*- coding: utf-8 -*-
"""Version clock for a node: the time its artifact commit actually succeeded."""
from __future__ import annotations

import logging
from typing import Any

from app.core.time_utils import now_bj_iso

logger = logging.getLogger(__name__)

STORY_FRAMEWORK_PERSISTED_AT = "story_framework_persisted_at"
STORY_OUTLINE_PERSISTED_AT = "story_outline_persisted_at"
EPISODE_SCRIPTS_PERSISTED_AT = "episode_scripts_persisted_at"
EPISODE_SCRIPT_PERSISTED_AT = "episode_script_persisted_at"
SCRIPT_OPTIMIZATION_PERSISTED_AT = "script_optimization_persisted_at"

_SCRIPT_OPTIMIZATION_NODE_NAMES = ("scene_split", "script_optimization")


def new_persisted_at() -> str:
    return now_bj_iso()


def stamp_project_persisted_at(db, project, key: str) -> str:
    """Record the clock after the artifact row is already committed."""
    stamp = new_persisted_at()
    project = db.merge(project)
    gi = dict(getattr(project, "global_info", None) or {})
    gi[str(key)] = stamp
    project.global_info = gi
    db.add(project)
    db.commit()
    try:
        db.refresh(project)
    except Exception:
        pass
    return stamp


def stamp_episode_script_persisted_at(db, episode, *, project_id: int) -> str:
    """Stamp one episode script and the project-level latest, after the script commit."""
    from app.models.all_models import Project

    stamp = new_persisted_at()
    info = getattr(episode, "episode_info", None)
    episode.episode_info = {
        **(info if isinstance(info, dict) else {}),
        EPISODE_SCRIPT_PERSISTED_AT: stamp,
    }
    db.add(episode)
    project = db.query(Project).filter(Project.id == int(project_id)).first()
    if project is not None:
        gi = dict(getattr(project, "global_info", None) or {})
        gi[EPISODE_SCRIPTS_PERSISTED_AT] = stamp
        project.global_info = gi
        db.add(project)
    db.commit()
    try:
        db.refresh(episode)
    except Exception:
        pass
    return stamp


def stamp_script_optimization_persisted_at(db, episode) -> str:
    """Stamp 剧本优化 / 全局统筹 after its manuscript commit succeeded."""
    from app.models.all_models import ScriptProgressPipelineNode

    stamp = new_persisted_at()
    info = getattr(episode, "episode_info", None)
    episode.episode_info = {
        **(info if isinstance(info, dict) else {}),
        SCRIPT_OPTIMIZATION_PERSISTED_AT: stamp,
    }
    db.add(episode)
    episode_id = int(getattr(episode, "id", 0) or 0)
    if episode_id > 0:
        rows = (
            db.query(ScriptProgressPipelineNode)
            .filter(
                ScriptProgressPipelineNode.episode_id == episode_id,
                ScriptProgressPipelineNode.node_name.in_(_SCRIPT_OPTIMIZATION_NODE_NAMES),
            )
            .all()
        )
        for row in rows:
            meta: dict[str, Any] = dict(row.runtime_meta) if isinstance(row.runtime_meta, dict) else {}
            meta["persisted_at"] = stamp
            row.runtime_meta = meta
            db.add(row)
    db.commit()
    try:
        db.refresh(episode)
    except Exception:
        pass
    return stamp


def safe_stamp_project_persisted_at(db, project, key: str) -> str:
    try:
        return stamp_project_persisted_at(db, project, key)
    except Exception:
        logger.warning("[persist_version] project stamp failed key=%s", key, exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass
        return ""


def safe_stamp_script_optimization_persisted_at(db, episode) -> str:
    try:
        return stamp_script_optimization_persisted_at(db, episode)
    except Exception:
        logger.warning("[persist_version] script optimization stamp failed", exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass
        return ""
