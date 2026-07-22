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


def _sort_project_episodes(episodes: List[Episode]) -> List[Episode]:
    def _sort_key(episode: Episode):
        resolved_number = _resolve_episode_sort_number(episode)
        fallback_id = int(getattr(episode, "id", 0) or 0)
        if resolved_number is not None:
            return (0, int(resolved_number), fallback_id)
        return (1, fallback_id, fallback_id)

    return sorted(list(episodes or []), key=_sort_key)

