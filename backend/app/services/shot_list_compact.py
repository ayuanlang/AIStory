# -*- coding: utf-8 -*-
"""Compact shot-list payload helpers for episode shot listings."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from app.services.generation_runtime.media_persist import (
    _asset_meta_to_dict,
    _refresh_managed_media_url,
)

_SHOT_LIST_COMPACT_TECH_KEYS = (
    "end_frame_url",
    "video_prompt_cn",
    "prompt_cn",
    "start_frame_cn",
    "end_frame_cn",
    "keyframes",
    "keyframes_cn",
    "keyframe_images",
    "voiceover_url",
    # Persist storyboard extract / preview media in compact list payloads so
    # reopening a shot can show previously captured frames without waiting on hydrate.
    "prev_shot_frames",
    "prev_shot_frame_images",
    "prev_shot_frame_meta",
    "multi_panel_image_url",
    "multi_panel_image_preset",
    "storyboard_url",
)
def _compact_shot_list_technical_notes(raw_notes: Any) -> Tuple[Optional[str], str, str]:
    notes = _asset_meta_to_dict(raw_notes)
    if not notes:
        return None, "", ""

    compact_notes: Dict[str, Any] = {}
    end_frame_url = str(notes.get("end_frame_url") or "").strip()
    prompt_preview_cn = ""

    for key in _SHOT_LIST_COMPACT_TECH_KEYS:
        if key not in notes:
            continue
        value = notes.get(key)
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                continue
            if key in {"video_prompt_cn", "prompt_cn", "start_frame_cn", "end_frame_cn"} and not prompt_preview_cn:
                prompt_preview_cn = normalized
            compact_notes[key] = normalized
            continue
        if isinstance(value, list):
            normalized_list = [str(item or "").strip() for item in value if str(item or "").strip()]
            if normalized_list:
                compact_notes[key] = normalized_list
            continue
        if value is not None:
            compact_notes[key] = value

    if end_frame_url and "end_frame_url" not in compact_notes:
        compact_notes["end_frame_url"] = end_frame_url

    compact_payload = json.dumps(compact_notes, ensure_ascii=False) if compact_notes else None
    return compact_payload, end_frame_url, prompt_preview_cn


def _build_compact_shot_payload(row: Any, db: Session) -> Dict[str, Any]:
    compact_notes, end_frame_url, prompt_preview_cn = _compact_shot_list_technical_notes(getattr(row, "technical_notes", None))
    image_url = _refresh_managed_media_url(getattr(row, "image_url", None), db)
    video_url = _refresh_managed_media_url(getattr(row, "video_url", None), db)
    end_frame_url = _refresh_managed_media_url(end_frame_url, db)

    prompt_preview_en = ""
    for candidate in (
        getattr(row, "video_content", None),
        getattr(row, "prompt", None),
        getattr(row, "start_frame", None),
        getattr(row, "end_frame", None),
        prompt_preview_cn,
        getattr(row, "shot_logic_cn", None),
    ):
        normalized = str(candidate or "").strip()
        if normalized:
            prompt_preview_en = normalized
            break

    return {
        "id": getattr(row, "id", None),
        "scene_id": getattr(row, "scene_id", None),
        "project_id": getattr(row, "project_id", None),
        "episode_id": getattr(row, "episode_id", None),
        "shot_id": getattr(row, "shot_id", None),
        "shot_name": getattr(row, "shot_name", None),
        "start_frame": getattr(row, "start_frame", None),
        "end_frame": getattr(row, "end_frame", None),
        "video_content": getattr(row, "video_content", None),
        "duration": getattr(row, "duration", None),
        "associated_entities": getattr(row, "associated_entities", None),
        "shot_logic_cn": getattr(row, "shot_logic_cn", None),
        "keyframes": getattr(row, "keyframes", None),
        "scene_code": getattr(row, "scene_code", None),
        "image_url": image_url or None,
        "video_url": video_url or None,
        "prompt": getattr(row, "prompt", None),
        "technical_notes": compact_notes,
        "end_frame_url": end_frame_url or None,
        "prompt_preview_cn": prompt_preview_cn or None,
        "prompt_preview_en": prompt_preview_en or None,
        "is_compact": True,
    }
