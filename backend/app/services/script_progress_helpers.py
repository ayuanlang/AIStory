# -*- coding: utf-8 -*-
"""Script analysis progress row / scene marker helpers."""
from __future__ import annotations

import re
from typing import Any, List, Optional

from sqlalchemy.orm import Session

from app.models.all_models import Scene, ScriptProgressSceneUnit


def _list_episode_scene_progress_rows(
    db: Session,
    *,
    project_id: int,
    episode_id: int,
    scene_ids: Optional[List[str]] = None,
) -> List[Any]:
    query = (
        db.query(ScriptProgressSceneUnit)
        .filter(
            ScriptProgressSceneUnit.project_id == int(project_id),
            ScriptProgressSceneUnit.episode_id == int(episode_id),
        )
        .order_by(ScriptProgressSceneUnit.scene_order.asc(), ScriptProgressSceneUnit.id.asc())
    )
    if scene_ids:
        normalized = [str(x).strip() for x in scene_ids if str(x).strip()]
        if normalized:
            query = query.filter(ScriptProgressSceneUnit.scene_id.in_(normalized))
    return query.all()


def _resolve_scene_id_to_db_scene(
    db: Session,
    *,
    episode_id: int,
    scene_marker_id: str,
) -> Optional[Scene]:
    from app.services.scene_no_utils import _find_active_scene_by_scene_no

    marker = str(scene_marker_id or "").strip()
    if not marker:
        return None
    return _find_active_scene_by_scene_no(
        db,
        episode_id=int(episode_id),
        scene_no=marker,
        scene_id=marker,
    )


def _normalize_asset_types(values: Optional[List[str]]) -> List[str]:
    default_types = ["character", "prop", "environment", "poster"]
    if not values:
        return default_types
    normalized: List[str] = []
    alias = {
        "characters": "character",
        "props": "prop",
        "environments": "environment",
        "covers": "poster",
        "posters": "poster",
    }
    for item in values:
        key = str(item or "").strip().lower()
        if not key:
            continue
        key = alias.get(key, key)
        if key in {"character", "prop", "environment", "poster"} and key not in normalized:
            normalized.append(key)
    return normalized or default_types


def _normalize_scene_marker_id_from_scene(
    scene: Scene,
    episode_id: int,
    episode: Any = None,
    episode_prefix: str = "",
) -> str:
    from app.services.scene_no_utils import canonicalize_progress_scene_marker

    prefix = str(episode_prefix or "").strip().upper()
    if not prefix and episode is not None:
        try:
            from app.services.script_analysis_flow import resolve_episode_scene_id_prefix
            prefix = resolve_episode_scene_id_prefix(episode, fallback_number=1)
        except Exception:
            prefix = ""
    if not prefix:
        raw_no = str(getattr(scene, "scene_no", "") or "").strip()
        ep_match = re.search(r"(EP\d+)_SC", raw_no, flags=re.IGNORECASE)
        prefix = ep_match.group(1).upper() if ep_match else "EP01"
    return canonicalize_progress_scene_marker(
        getattr(scene, "scene_no", "") or "",
        episode_prefix=prefix,
    )


