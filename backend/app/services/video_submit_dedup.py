# -*- coding: utf-8 -*-
"""In-flight video submit dedup cache."""
from __future__ import annotations

import asyncio
import hashlib
from typing import Any, Dict

_VIDEO_DEDUP_WINDOW_SECONDS = 20
_VIDEO_DEDUP_MAX_CACHE = 256
_VIDEO_INFLIGHT_BY_KEY: Dict[str, asyncio.Task] = {}
_VIDEO_RECENT_RESULTS_BY_KEY: Dict[str, Dict[str, Any]] = {}
_VIDEO_DEDUP_LOCK = asyncio.Lock()


def _digest_text_for_dedup(value: Any) -> str:
    text = str(value or "")
    if not text:
        return ""
    if len(text) > 200:
        return f"sha1:{hashlib.sha1(text.encode('utf-8', errors='ignore')).hexdigest()}"
    return text


def _compact_for_dedup(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _compact_for_dedup(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, list):
        return [_compact_for_dedup(v) for v in value]
    if isinstance(value, tuple):
        return [_compact_for_dedup(v) for v in value]
    if isinstance(value, str):
        return _digest_text_for_dedup(value)
    return value


def _build_video_dedup_key(req: "VideoGenerationRequest", user_id: int) -> str:
    payload = {
        "user_id": int(user_id or 0),
        "provider": req.provider,
        "model": req.model,
        "prompt": req.prompt,
        "negative_prompt": req.negative_prompt,
        "ref_image_url": req.ref_image_url,
        "ref_video_urls": req.ref_video_urls,
        "image_urls": req.image_urls,
        "last_frame_url": req.last_frame_url,
        "duration": req.duration,
        "aspect_ratio": req.aspect_ratio,
        "mode": req.mode,
        "ref_mode": req.ref_mode,
        "sound": req.sound,
        "multi_shots": req.multi_shots,
        "multi_prompt": req.multi_prompt,
        "kling_elements": req.kling_elements,
        "project_id": req.project_id,
        "shot_id": req.shot_id,
        "shot_number": req.shot_number,
        "shot_name": req.shot_name,
        "entity_name": req.entity_name,
        "subject_name": req.subject_name,
        "asset_type": req.asset_type,
        "keyframes": req.keyframes,
        "seed": req.seed,
    }
    compact = _compact_for_dedup(payload)
    stable = json.dumps(compact, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(stable.encode("utf-8", errors="ignore")).hexdigest()


def _cleanup_video_dedup_cache(now_ts: float) -> None:
    stale_keys = [
        key for key, item in _VIDEO_RECENT_RESULTS_BY_KEY.items()
        if (now_ts - float(item.get("ts") or 0.0)) > _VIDEO_DEDUP_WINDOW_SECONDS
    ]
    for key in stale_keys:
        _VIDEO_RECENT_RESULTS_BY_KEY.pop(key, None)

    if len(_VIDEO_RECENT_RESULTS_BY_KEY) > _VIDEO_DEDUP_MAX_CACHE:
        ordered = sorted(
            _VIDEO_RECENT_RESULTS_BY_KEY.items(),
            key=lambda item: float((item[1] or {}).get("ts") or 0.0),
        )
        overflow = len(_VIDEO_RECENT_RESULTS_BY_KEY) - _VIDEO_DEDUP_MAX_CACHE
        for key, _ in ordered[:overflow]:
            _VIDEO_RECENT_RESULTS_BY_KEY.pop(key, None)

ANALYSIS_PROMPT_TEMPLATE_SYNTAX_RULES: Dict[str, Dict[str, Any]] = {
    "characters": {
        "required_text_fields": [
            "subject_no", "name", "name_en", "base_name_en", "description_cn",
            "gender", "role", "archetype", "appearance_cn", "clothing",
            "action_characteristics", "generation_prompt_cn", "generation_prompt_en",
            "negative_prompt_en", "anchor_description",
        ],
        "required_present_fields": ["visual_dependencies", "dependency_strategy"],
        "dependency_strategy_required_keys": ["type", "logic"],
    },
    "props": {
        "required_text_fields": [
            "subject_no", "name", "name_en", "base_name_en", "type",
            "description_cn", "generation_prompt_cn", "generation_prompt_en",
            "negative_prompt_en", "anchor_description",
        ],
        "required_present_fields": ["visual_dependencies", "dependency_strategy"],
        "dependency_strategy_required_keys": ["type", "logic"],
    },
    "environments": {
        "required_text_fields": [
            "subject_no", "name", "name_en", "base_name_en", "atmosphere",
            "visual_params", "description_cn", "generation_prompt_cn",
            "generation_prompt_en", "negative_prompt_en", "anchor_description",
        ],
        "required_present_fields": ["visual_dependencies", "dependency_strategy"],
        "dependency_strategy_required_keys": ["type", "logic"],
    },
    "posters": {
        "required_text_fields": [
            "subject_no", "name", "name_en", "base_name_en", "atmosphere",
            "visual_params", "description_cn", "generation_prompt_cn",
            "generation_prompt_en", "negative_prompt_en", "anchor_description",
        ],
        "required_present_fields": ["visual_dependencies", "dependency_strategy"],
        "dependency_strategy_required_keys": ["type", "logic"],
    },
}
