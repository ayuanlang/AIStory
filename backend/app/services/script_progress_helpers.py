# -*- coding: utf-8 -*-
"""Script analysis progress row / scene marker helpers."""
from __future__ import annotations

from typing import Any, List, Optional

from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Session

from app.models.all_models import Scene, ScriptProgressSceneUnit
from app.services.soft_delete import _active_scene_clause


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
    marker = str(scene_marker_id or "").strip()
    if not marker:
        return None
    fallback_no = marker
    if "_SC" in marker:
        try:
            fallback_no = marker.split("_SC", 1)[1]
        except Exception:
            fallback_no = marker
    scene = (
        db.query(Scene)
        .filter(
            Scene.episode_id == int(episode_id),
            or_(Scene.scene_no == marker, Scene.scene_no == fallback_no),
            _active_scene_clause(),
        )
        .first()
    )
    if scene:
        return scene
    try:
        maybe_num = int(fallback_no)
    except Exception:
        maybe_num = None
    if maybe_num is not None:
        return (
            db.query(Scene)
            .filter(
                Scene.episode_id == int(episode_id),
                cast(Scene.scene_no, String) == str(maybe_num),
                _active_scene_clause(),
            )
            .first()
        )
    return None


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


def _normalize_scene_marker_id_from_scene(scene: Scene, episode_id: int) -> str:
    scene_no = str(getattr(scene, "scene_no", "") or "").strip()
    if scene_no:
        if "_SC" in scene_no:
            return scene_no
        return f"EP{int(episode_id):02d}_SC{scene_no}"
    return f"EP{int(episode_id):02d}_SC{int(scene.id)}"


