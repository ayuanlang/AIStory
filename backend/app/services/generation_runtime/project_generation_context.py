# -*- coding: utf-8 -*-
"""Project seed / id resolution / negative-prompt defaults for generation."""
from __future__ import annotations

import json
import logging
import os
import random
from typing import Any, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.all_models import Entity, Episode, Project, Scene, Shot, User

logger = logging.getLogger("api_logger")


_DEFAULT_FRAME_INTEGRITY_NEGATIVE_PROMPT = (
    "no split-screen, no multi-panel, no collage, no duplicated subject, "
    "no repeated background blocks, no tiled composition, no comic-strip layout, "
    "no text, no watermark"
)


def _resolve_effective_negative_prompt(
    negative_prompt: Optional[str],
    asset_type: Optional[str],
    media_type: str,
) -> Tuple[str, str]:
    supplied = str(negative_prompt or "").strip()
    if supplied:
        return supplied, "request"

    asset_kind = str(asset_type or "").strip().lower()
    media_kind = str(media_type or "").strip().lower()
    if media_kind == "image" and asset_kind in {"start", "start_frame", "end", "end_frame"}:
        return _DEFAULT_FRAME_INTEGRITY_NEGATIVE_PROMPT, "default_frame_integrity"

    return "", "none"


def _normalize_seed_value(value: Any) -> Optional[int]:
    try:
        seed_num = int(value)
    except Exception:
        return None
    # Keep in common signed 32-bit positive range.
    if seed_num <= 0 or seed_num > 2147483647:
        return None
    return seed_num

def _resolve_project_id_for_generation(req: Any, db: Session) -> Optional[int]:
    direct_project_id = _normalize_seed_value(getattr(req, "project_id", None))
    if direct_project_id:
        return direct_project_id

    episode_id = _normalize_seed_value(getattr(req, "episode_id", None))
    if episode_id:
        ep = db.query(Episode).filter(Episode.id == int(episode_id)).first()
        if ep and ep.project_id:
            return int(ep.project_id)

    shot_id = _normalize_seed_value(getattr(req, "shot_id", None))
    if shot_id:
        shot = db.query(Shot).filter(Shot.id == int(shot_id)).first()
        if shot:
            shot_project_id = _normalize_seed_value(getattr(shot, "project_id", None))
            if shot_project_id:
                return shot_project_id

            if getattr(shot, "scene_id", None):
                scene = db.query(Scene).filter(Scene.id == shot.scene_id).first()
                if scene and scene.episode_id:
                    ep = db.query(Episode).filter(Episode.id == scene.episode_id).first()
                    if ep and ep.project_id:
                        return int(ep.project_id)

    entity_id = _normalize_seed_value(getattr(req, "entity_id", None))
    if entity_id:
        entity = db.query(Entity).filter(Entity.id == int(entity_id)).first()
        if entity and entity.project_id:
            return int(entity.project_id)

    return None


def _should_hit_visual_breakpoint(kind: str, resolved_project_id: Optional[int]) -> bool:
    """Opt-in runtime breakpoint for project visual param debugging.

    Env controls:
    - GENERATION_VISUAL_BREAKPOINT=1
    - GENERATION_VISUAL_BREAKPOINT_KIND=image|video|all (default: all)
    - GENERATION_VISUAL_BREAKPOINT_PROJECT_ID=<int> (optional filter)
    """
    enabled = str(os.getenv("GENERATION_VISUAL_BREAKPOINT", "")).strip().lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return False

    kind_filter = str(os.getenv("GENERATION_VISUAL_BREAKPOINT_KIND", "all") or "all").strip().lower()
    if kind_filter not in {"all", "image", "video"}:
        kind_filter = "all"
    if kind_filter != "all" and kind_filter != str(kind or "").strip().lower():
        return False

    pid_filter_raw = str(os.getenv("GENERATION_VISUAL_BREAKPOINT_PROJECT_ID", "")).strip()
    if pid_filter_raw:
        try:
            pid_filter = int(pid_filter_raw)
        except Exception:
            return False
        try:
            stable_project_id = int(resolved_project_id) if resolved_project_id is not None else None
        except Exception:
            stable_project_id = None
        if stable_project_id != pid_filter:
            return False

    return True


def _ensure_project_generation_seed(db: Session, project_id: Optional[int], current_user: Optional[User] = None) -> Optional[int]:
    stable_project_id = _normalize_seed_value(project_id)
    if not stable_project_id:
        return None

    if current_user:
        from app.api.routers.workspace.shared import _require_project_access
        project = _require_project_access(db, int(stable_project_id), current_user)
    else:
        project = db.query(Project).filter(Project.id == int(stable_project_id)).first()
    if not project:
        return None

    raw_info = project.global_info
    if isinstance(raw_info, dict):
        global_info = dict(raw_info)
    elif isinstance(raw_info, str):
        try:
            parsed = json.loads(raw_info)
            global_info = parsed if isinstance(parsed, dict) else {}
        except Exception:
            global_info = {}
    else:
        global_info = {}

    existing_seed = _normalize_seed_value(
        global_info.get("generation_seed")
        or global_info.get("seed")
        or ((global_info.get("generation") or {}).get("seed") if isinstance(global_info.get("generation"), dict) else None)
    )
    if existing_seed:
        return existing_seed

    new_seed = random.SystemRandom().randint(10000, 2147483647)
    global_info["generation_seed"] = int(new_seed)
    if "seed" not in global_info:
        global_info["seed"] = int(new_seed)

    project.global_info = global_info
    db.add(project)
    db.commit()

    logger.info(
        "[ProjectSeed] initialized | project_id=%s user_id=%s seed=%s",
        stable_project_id,
        getattr(current_user, "id", None),
        new_seed,
    )
    return int(new_seed)

