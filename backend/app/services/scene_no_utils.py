# -*- coding: utf-8 -*-
"""Scene number canonicalize / lookup helpers."""
from __future__ import annotations

import re
from typing import Any, List, Optional

from sqlalchemy.orm import Session

from app.models.all_models import Scene
from app.services.soft_delete import _active_scene_clause

def _scene_no_sort_key(scene) -> tuple:
    scene_no = str(getattr(scene, "scene_no", None) or "").strip()
    if not scene_no:
        return (1, (), "", int(getattr(scene, "id", 0) or 0))
    nums = tuple(int(m) for m in re.findall(r"\d+", scene_no))
    return (0, nums, scene_no.lower(), int(getattr(scene, "id", 0) or 0))


def _sort_scenes_by_scene_no(scenes: list) -> list:
    return sorted(scenes, key=_scene_no_sort_key)


def _canonicalize_scene_no(scene_no: Any, *, scene_id: Any = None) -> str:
    """
    Normalize workspace Scene.scene_no so one episode cannot store aliases
    of the same number (EP01_SC03 / 03 / 3 → "3"). Letter-suffix IDs stay intact.
    """
    raw_id = str(scene_id or "").strip()
    raw_no = str(scene_no or "").strip()
    source = raw_id or raw_no
    if not source:
        return ""

    letter_match = re.fullmatch(r"(EP\d+_SC\d+[A-Za-z]+)", source, flags=re.IGNORECASE)
    if letter_match:
        return letter_match.group(1).upper()

    canonical_match = re.fullmatch(r"EP\d+_SC(\d+)", source, flags=re.IGNORECASE)
    if canonical_match:
        return str(int(canonical_match.group(1)))

    sc_match = re.fullmatch(r"SC?(\d+)", source, flags=re.IGNORECASE)
    if sc_match:
        return str(int(sc_match.group(1)))

    if re.fullmatch(r"\d+", source):
        return str(int(source))

    if raw_no and raw_no != source:
        return _canonicalize_scene_no(raw_no)

    return source


def _scene_no_lookup_keys(scene_no: Any, *, scene_id: Any = None) -> List[str]:
    """Alias keys used when matching an existing active scene in one episode."""
    keys: List[str] = []
    canonical = _canonicalize_scene_no(scene_no, scene_id=scene_id)
    for candidate in (scene_no, scene_id, canonical):
        text = str(candidate or "").strip()
        if text:
            keys.append(text)
    if canonical and re.fullmatch(r"\d+", canonical):
        order = int(canonical)
        keys.append(f"{order:02d}")
        keys.append(f"SC{order:02d}")
        keys.append(f"SC{order}")
        ep_match = re.search(r"(EP\d+)_SC", str(scene_id or scene_no or ""), flags=re.IGNORECASE)
        if ep_match:
            prefix = ep_match.group(1).upper()
            keys.append(f"{prefix}_SC{order:02d}")
            keys.append(f"{prefix}_SC{order}")
    # Preserve order while dropping empties/dupes.
    return list(dict.fromkeys(item for item in keys if item))


def canonicalize_progress_scene_marker(
    scene_no: Any,
    *,
    episode_prefix: str = "EP01",
    scene_id: Any = None,
) -> str:
    """Matrix / pipeline scene_id: EP01_SC01. Workspace Scene.scene_no is often \"1\"."""
    raw = str(scene_id or scene_no or "").strip()
    prefix = str(episode_prefix or "EP01").strip().upper() or "EP01"
    if not re.fullmatch(r"EP\d+", prefix):
        prefix = "EP01"
    if not raw:
        return ""
    letter_match = re.fullmatch(r"(EP\d+_SC\d+[A-Za-z]+)", raw, flags=re.IGNORECASE)
    if letter_match:
        return letter_match.group(1).upper()
    source_ep = re.fullmatch(r"(EP\d+)_SC(\d+)", raw, flags=re.IGNORECASE)
    if source_ep:
        return f"{source_ep.group(1).upper()}_SC{int(source_ep.group(2)):02d}"
    canonical = _canonicalize_scene_no(scene_no, scene_id=scene_id)
    if canonical and re.fullmatch(r"\d+", canonical):
        return f"{prefix}_SC{int(canonical):02d}"
    return raw


def _find_active_scene_by_scene_no(
    db: Session,
    *,
    episode_id: int,
    scene_no: Any,
    scene_id: Any = None,
) -> Optional[Any]:
    keys = _scene_no_lookup_keys(scene_no, scene_id=scene_id)
    if not keys:
        return None
    rows = (
        db.query(Scene)
        .filter(
            Scene.episode_id == int(episode_id),
            Scene.scene_no.in_(keys),
            _active_scene_clause(),
        )
        .order_by(Scene.id.desc())
        .all()
    )
    if not rows:
        return None
    canonical = _canonicalize_scene_no(scene_no, scene_id=scene_id)
    for row in rows:
        if _canonicalize_scene_no(getattr(row, "scene_no", None)) == canonical:
            return row
    return rows[0]
