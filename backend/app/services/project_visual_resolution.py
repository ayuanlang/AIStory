# -*- coding: utf-8 -*-
"""Lightweight project visual / video resolution helpers.

Kept outside app.api.endpoints so billing estimate and other hot paths do not
pull the megamodule just to resolve aspect / tier / pixel dims.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

PROJECT_IMAGE_SIZE_LONG_EDGE_MAP = {
    "0.5K": 960,
    "1K": 1280,
    "2K": 2560,
    "4K": 3840,
}

PROJECT_IMAGE_SIZE_SQUARE_MAP = {
    "0.5K": 720,
    "1K": 1024,
    "2K": 2048,
    "4K": 4096,
}

PROJECT_RESOLUTION_PRESETS = {
    ("16:9", "0.5K"): (960, 540),
    ("16:9", "1K"): (1280, 720),
    ("16:9", "2K"): (2560, 1440),
    ("16:9", "4K"): (3840, 2160),
    ("9:16", "0.5K"): (540, 960),
    ("9:16", "1K"): (720, 1280),
    ("9:16", "2K"): (1440, 2560),
    ("9:16", "4K"): (2160, 3840),
    ("4:3", "0.5K"): (960, 720),
    ("4:3", "1K"): (1280, 960),
    ("4:3", "2K"): (2048, 1536),
    ("4:3", "4K"): (2880, 2160),
    ("3:4", "0.5K"): (720, 960),
    ("3:4", "1K"): (960, 1280),
    ("3:4", "2K"): (1536, 2048),
    ("3:4", "4K"): (2160, 2880),
    ("21:9", "0.5K"): (960, 411),
    ("21:9", "1K"): (1280, 549),
    ("21:9", "2K"): (2560, 1097),
    ("21:9", "4K"): (3840, 1646),
    ("2.35:1", "0.5K"): (960, 409),
    ("2.35:1", "1K"): (1280, 544),
    ("2.35:1", "2K"): (2560, 1089),
    ("2.35:1", "4K"): (3840, 1634),
    ("1:1", "0.5K"): (720, 720),
    ("1:1", "1K"): (1024, 1024),
    ("1:1", "2K"): (2048, 2048),
    ("1:1", "4K"): (4096, 4096),
}


def normalize_project_image_size(value: Any) -> str:
    raw = str(value or "").strip().upper().replace(" ", "")
    return raw if raw in PROJECT_IMAGE_SIZE_LONG_EDGE_MAP else ""


def normalize_project_video_resolution(value: Any) -> str:
    """Normalize project video short-edge tier to '480' or '720'."""
    raw = str(value or "").strip().lower().replace(" ", "")
    if not raw:
        return ""
    if raw.endswith("p") and raw[:-1].isdigit():
        raw = raw[:-1]
    elif raw.startswith("p") and raw[1:].isdigit():
        raw = raw[1:]
    if raw in {"480", "sd"}:
        return "480"
    if raw in {"720", "hd"}:
        return "720"
    return ""


def project_video_resolution_label(value: Any) -> str:
    tier = normalize_project_video_resolution(value)
    return f"{tier}p" if tier else ""


def parse_aspect_ratio_pair(value: Any) -> Optional[Tuple[float, float]]:
    raw = str(value or "").strip().lower()
    if not raw:
        return None
    if raw == "landscape":
        return (16.0, 9.0)
    if raw == "portrait":
        return (9.0, 16.0)

    match = re.match(r"^\s*(\d+(?:\.\d+)?)\s*[:/]\s*(\d+(?:\.\d+)?)\s*$", raw)
    if not match:
        return None
    try:
        left = float(match.group(1))
        right = float(match.group(2))
    except Exception:
        return None
    if left <= 0 or right <= 0:
        return None
    return (left, right)


def infer_dims_from_video_resolution_tier(
    aspect_ratio: Any,
    video_resolution: Any,
    *,
    provider: Any = None,
    model: Any = None,
) -> Optional[Tuple[int, int]]:
    """Derive WxH from official Seedance pixel tables (fallback: short-edge math)."""
    try:
        from app.services.billing_pricing import resolve_seedance_pixel_dims

        table_dims = resolve_seedance_pixel_dims(
            aspect_ratio=aspect_ratio,
            resolution=video_resolution,
            provider=provider,
            model=model,
        )
        if table_dims:
            return table_dims
    except Exception:
        pass

    tier = normalize_project_video_resolution(video_resolution)
    if not tier:
        # Allow 1080 / 4k labels for table-miss fallback.
        raw = str(video_resolution or "").strip().lower().replace(" ", "")
        if raw in {"1080", "1080p"}:
            tier = "1080"
        elif raw in {"4k", "2160", "2160p"}:
            tier = "2160"
    if not tier:
        return None
    short_edge = int(tier) if str(tier).isdigit() else 720
    ratio_pair = parse_aspect_ratio_pair(aspect_ratio) or (16.0, 9.0)
    rw, rh = ratio_pair
    if rw <= 0 or rh <= 0:
        return None
    if rw >= rh:
        height = short_edge
        width = max(1, int(round(short_edge * rw / rh)))
        return (width, height)
    width = short_edge
    height = max(1, int(round(short_edge * rh / rw)))
    return (width, height)


def infer_project_resolution(aspect_ratio: Any, image_size: Any) -> Optional[Tuple[int, int]]:
    ratio_raw = str(aspect_ratio or "").strip()
    size_norm = normalize_project_image_size(image_size)
    if not ratio_raw or not size_norm:
        return None

    preset = PROJECT_RESOLUTION_PRESETS.get((ratio_raw, size_norm))
    if preset:
        return preset

    ratio_pair = parse_aspect_ratio_pair(ratio_raw)
    if not ratio_pair:
        return None

    rw, rh = ratio_pair
    if abs(rw - rh) < 1e-9:
        side = PROJECT_IMAGE_SIZE_SQUARE_MAP.get(size_norm)
        if side:
            return (int(side), int(side))
        return None

    long_edge = PROJECT_IMAGE_SIZE_LONG_EDGE_MAP.get(size_norm)
    if not long_edge:
        return None

    if rw >= rh:
        width = int(long_edge)
        height = max(1, int(round(width * rh / rw)))
    else:
        height = int(long_edge)
        width = max(1, int(round(height * rw / rh)))
    return (width, height)


def resolve_video_billing_runtime_target(
    *,
    system_api_id: Any = None,
    provider: Any = None,
    model: Any = None,
    category: str = "Video",
) -> Dict[str, Any]:
    """Resolve provider/model for billing without media_service.get_api_config repairs."""
    from app.services.system_api_runtime_cache import resolve_system_api_cached

    resolved_system_api_id = None
    try:
        if system_api_id is not None:
            resolved_system_api_id = int(system_api_id)
            if resolved_system_api_id <= 0:
                resolved_system_api_id = None
    except Exception:
        resolved_system_api_id = None

    row = None
    if resolved_system_api_id is not None:
        row = resolve_system_api_cached(setting_id=resolved_system_api_id)
    if row is None:
        provider_text = str(provider or "").strip() or None
        model_text = str(model or "").strip() or None
        if provider_text or model_text:
            row = resolve_system_api_cached(
                provider=provider_text,
                category=str(category or "Video").strip() or "Video",
                model=model_text,
            )

    resolved_provider = str(getattr(row, "provider", None) or provider or "").strip() or None
    resolved_model = str(getattr(row, "model", None) or model or "").strip() or None
    if row is not None and resolved_system_api_id is None:
        try:
            rid = int(getattr(row, "id", 0) or 0)
            resolved_system_api_id = rid if rid > 0 else None
        except Exception:
            resolved_system_api_id = None

    return {
        "resolved_provider": resolved_provider,
        "resolved_model": resolved_model,
        "resolved_system_api_id": resolved_system_api_id,
        "runtime_llm_config": {
            "provider": resolved_provider,
            "model": resolved_model,
        },
        "pre_api_cfg": {},
        "light_resolve": True,
    }
