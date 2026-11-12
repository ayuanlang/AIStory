# -*- coding: utf-8 -*-
"""Episode number / sort helpers used across workspace and generation."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.models.all_models import Episode


def _to_positive_int_or_none(value: Any) -> Optional[int]:
    try:
        parsed = int(value)
    except Exception:
        return None
    return parsed if parsed > 0 else None


def _safe_json_dict(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return {}
        try:
            import json as _json
            parsed = _json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _episode_runtime_info_from_episode(episode: Optional[Episode]) -> Dict[str, Any]:
    """Read raw episode_info for runtime status keys even when generic reads are disabled."""
    if not episode:
        return {}
    return _safe_json_dict(getattr(episode, "episode_info", None))


def _extract_episode_number_from_title(title: Any) -> Optional[int]:
    value = str(title or "").strip()
    if not value:
        return None

    match = re.search(r"(?:Episode|EP)\s*[-_#]?\s*(\d+)", value, flags=re.IGNORECASE)
    if match:
        return _to_positive_int_or_none(match.group(1))

    match = re.search(r"第\s*(\d+)\s*集", value)
    if match:
        return _to_positive_int_or_none(match.group(1))

    return None


def _resolve_episode_sort_number(episode: Optional[Episode]) -> Optional[int]:
    if not episode:
        return None

    info = _episode_runtime_info_from_episode(episode)
    for key in (
        "episode_script_episode_number",
        "story_dna_episode_number",
        "episode_number",
        "index",
    ):
        parsed = _to_positive_int_or_none(info.get(key) if isinstance(info, dict) else None)
        if parsed:
            return parsed

    return _extract_episode_number_from_title(getattr(episode, "title", None))


def pick_nearest_prior_match(matches: List[Any], host_episode_id: Any, episode_numbers: Dict[int, Optional[int]]) -> Optional[Any]:
    """Pick a dependency row when the host episode has no same-name row.

    ``episode_numbers`` maps each active episode id to its sort number.
    ``None`` means the episode is active but unnumbered.
    An episode id missing from the map is deleted or outside the project and is skipped.
    The nearest earlier episode wins. A later episode never wins.
    If the host number is unknown, the first match is kept.
    """
    rows = list(matches or [])
    if not rows:
        return None

    host_id = _to_positive_int_or_none(host_episode_id)
    host_number = episode_numbers.get(host_id) if host_id is not None else None
    if not host_number:
        return rows[0]

    def _row_id(item: Any) -> int:
        try:
            return int(getattr(item, "id", 0) or 0)
        except Exception:
            return 0

    def _has_image(item: Any) -> int:
        return 1 if str(getattr(item, "image_url", "") or "").strip() else 0

    def _episode_state(item: Any):
        raw = getattr(item, "episode_id", None)
        if raw is None or str(raw).strip() == "":
            return "unnumbered", None
        ep_id = _to_positive_int_or_none(raw)
        if ep_id is None or ep_id not in episode_numbers:
            return "skip", None
        number = episode_numbers.get(ep_id)
        if not number:
            return "unnumbered", None
        return "numbered", int(number)

    best = None
    best_key = None
    unnumbered: List[Any] = []
    for item in rows:
        state, number = _episode_state(item)
        if state == "skip":
            continue
        if state == "unnumbered":
            unnumbered.append(item)
            continue
        if int(number) >= int(host_number):
            continue
        key = (-(int(host_number) - int(number)), _has_image(item), _row_id(item))
        if best is None or key > best_key:
            best = item
            best_key = key
    if best is not None:
        return best
    if not unnumbered:
        return None
    return max(unnumbered, key=lambda item: (_has_image(item), _row_id(item)))


def _sort_project_episodes(episodes: List[Episode]) -> List[Episode]:
    def _sort_key(episode: Episode):
        resolved_number = _resolve_episode_sort_number(episode)
        fallback_id = int(getattr(episode, "id", 0) or 0)
        if resolved_number is not None:
            return (0, int(resolved_number), fallback_id)
        return (1, fallback_id, fallback_id)

    return sorted(list(episodes or []), key=_sort_key)

