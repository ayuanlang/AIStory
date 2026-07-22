# -*- coding: utf-8 -*-
"""Project-level generation defaults / video-sound normalization."""
from __future__ import annotations

from typing import Any, Dict

from app.services.effective_api_setting import _to_bool
from app.services.project_episode_utils import _to_positive_int_or_none
from app.services.project_visual_resolution import (
    infer_project_resolution as _infer_project_resolution,
    normalize_project_image_size as _normalize_project_image_size,
    normalize_project_video_resolution as _normalize_project_video_resolution,
)

_PROJECT_LEVEL_GENERATION_DEFAULT_KEYS = (
    "model",
    "quality",
    "style",
    "safety_tolerance",
    "voice",
    "reasoning_effort",
    "aspect_ratio",
    "resolution",
    "size",
    "image_resolution",
    "image_size",
    "horizontal_resolution",
    "vertical_resolution",
    "upscale_factor",
    "character_orientation",
    "duration",
    "n_frames",
    "num_images",
)

def _resolve_project_video_sound(global_info: Any, *, default: bool = True) -> bool:
    gi = global_info if isinstance(global_info, dict) else {}
    defaults_raw = gi.get("project_generation_defaults")
    defaults = defaults_raw if isinstance(defaults_raw, dict) else {}
    tech_params = gi.get("tech_params") if isinstance(gi.get("tech_params"), dict) else {}
    visual = tech_params.get("visual_standard") if isinstance(tech_params.get("visual_standard"), dict) else {}
    for candidate in (
        gi.get("video_sound"),
        gi.get("sound"),
        defaults.get("sound"),
        visual.get("sound"),
    ):
        if candidate is None:
            continue
        return _to_bool(candidate)
    return default


def _ensure_project_generation_defaults(global_info: Any) -> Dict[str, Any]:
    gi = dict(global_info) if isinstance(global_info, dict) else {}

    defaults_raw = gi.get("project_generation_defaults")
    defaults = dict(defaults_raw) if isinstance(defaults_raw, dict) else {}
    # Read-only normalization: unify alias keys; video_sound defaults to enabled when unset.
    tech_params = gi.get("tech_params") if isinstance(gi.get("tech_params"), dict) else {}
    visual_standard = tech_params.get("visual_standard") if isinstance(tech_params.get("visual_standard"), dict) else {}

    # Precedence: project_generation_defaults / visual_standard > top-level legacy keys.
    aspect_ratio = str(
        defaults.get("aspect_ratio")
        or defaults.get("aspectRatio")
        or visual_standard.get("aspect_ratio")
        or visual_standard.get("aspectRatio")
        or gi.get("aspect_ratio")
        or gi.get("aspectRatio")
        or ""
    ).strip()
    if aspect_ratio:
        defaults["aspect_ratio"] = aspect_ratio
        visual_standard.setdefault("aspect_ratio", aspect_ratio)

    image_size = _normalize_project_image_size(
        defaults.get("image_size")
        or defaults.get("imageSize")
        or defaults.get("image_resolution")
        or defaults.get("imageResolution")
        or visual_standard.get("image_size")
        or visual_standard.get("imageSize")
        or gi.get("image_size")
        or gi.get("imageSize")
    )
    if image_size:
        defaults["image_size"] = image_size
        visual_standard.setdefault("image_size", image_size)

    video_resolution = _normalize_project_video_resolution(
        defaults.get("video_resolution")
        or visual_standard.get("video_resolution")
        or gi.get("video_resolution")
    ) or "720"
    defaults["video_resolution"] = video_resolution
    visual_standard["video_resolution"] = video_resolution

    current_w = (
        _to_positive_int_or_none(defaults.get("horizontal_resolution"))
        or _to_positive_int_or_none(defaults.get("horizontalResolution"))
        or _to_positive_int_or_none(visual_standard.get("horizontal_resolution"))
        or _to_positive_int_or_none(visual_standard.get("horizontalResolution"))
        or _to_positive_int_or_none(visual_standard.get("h_resolution"))
        or _to_positive_int_or_none(visual_standard.get("width"))
        or _to_positive_int_or_none(gi.get("horizontal_resolution"))
        or _to_positive_int_or_none(gi.get("horizontalResolution"))
        or _to_positive_int_or_none(gi.get("width"))
    )
    current_h = (
        _to_positive_int_or_none(defaults.get("vertical_resolution"))
        or _to_positive_int_or_none(defaults.get("verticalResolution"))
        or _to_positive_int_or_none(visual_standard.get("vertical_resolution"))
        or _to_positive_int_or_none(visual_standard.get("verticalResolution"))
        or _to_positive_int_or_none(visual_standard.get("v_resolution"))
        or _to_positive_int_or_none(visual_standard.get("height"))
        or _to_positive_int_or_none(gi.get("vertical_resolution"))
        or _to_positive_int_or_none(gi.get("verticalResolution"))
        or _to_positive_int_or_none(gi.get("height"))
    )

    if current_w and current_h:
        defaults["horizontal_resolution"] = int(current_w)
        defaults["vertical_resolution"] = int(current_h)
        visual_standard.setdefault("horizontal_resolution", int(current_w))
        visual_standard.setdefault("vertical_resolution", int(current_h))

    # If only logical size tier exists, infer concrete dimensions from aspect ratio.
    if (not current_w or not current_h) and aspect_ratio and image_size:
        inferred_dims = _infer_project_resolution(aspect_ratio, image_size)
        if inferred_dims:
            inferred_w, inferred_h = inferred_dims
            if inferred_w and inferred_h:
                defaults["horizontal_resolution"] = int(inferred_w)
                defaults["vertical_resolution"] = int(inferred_h)
                visual_standard.setdefault("horizontal_resolution", int(inferred_w))
                visual_standard.setdefault("vertical_resolution", int(inferred_h))

    quality = str(
        defaults.get("quality")
        or visual_standard.get("quality")
        or gi.get("quality")
        or ""
    ).strip()
    if quality:
        defaults.setdefault("quality", quality)
        visual_standard.setdefault("quality", quality)

    tech_params["visual_standard"] = visual_standard
    gi["tech_params"] = tech_params
    gi["project_generation_defaults"] = defaults

    resolved_sound = _resolve_project_video_sound(gi, default=True)
    gi["video_sound"] = resolved_sound
    defaults["sound"] = resolved_sound
    visual_standard["sound"] = resolved_sound
    tech_params["visual_standard"] = visual_standard
    gi["tech_params"] = tech_params
    gi["project_generation_defaults"] = defaults
    return gi


