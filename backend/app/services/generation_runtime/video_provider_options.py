# -*- coding: utf-8 -*-
"""Build provider_options payload for video generation requests."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.schemas.generation import VideoGenerationRequest
from app.services.generation_runtime.api_capabilities import _limit_string_list_input
from app.services.generation_runtime.callback_http import _normalize_callback_url
from app.services.generation_runtime.project_generation_context import _normalize_seed_value
from app.services.generation_runtime.video_ref_pipeline import _normalize_video_ref_mode  # noqa: E402


def _build_video_provider_options(req: VideoGenerationRequest, quality: Optional[str] = None, output_format: Optional[str] = None, mode: Optional[str] = None) -> Dict[str, Any]:
    options: Dict[str, Any] = {}

    explicit_seed = _normalize_seed_value(getattr(req, "seed", None))
    if explicit_seed:
        options["seed"] = int(explicit_seed)
        options["seeds"] = int(explicit_seed)

    callback_candidate = (
        req.callback_url
        or req.callbackUrl
        or req.callBackUrl
    )
    callback_url = _normalize_callback_url(callback_candidate)
    if callback_url:
        # Keep both key styles for downstream provider adapters.
        options["callback_url"] = callback_url
        options["callBackUrl"] = callback_url
        options["webHook"] = callback_url

    if isinstance(req.image_urls, list):
        image_urls = _limit_string_list_input(req.image_urls, None)
        if image_urls:
            options["image_urls"] = image_urls

    if isinstance(req.audio_ids, list):
        audio_ids = _limit_string_list_input(req.audio_ids, None)
        if audio_ids:
            options["audio_ids"] = audio_ids

    if isinstance(req.video_list, list):
        normalized_video_list: List[Dict[str, Any]] = []
        for item in req.video_list:
            if not isinstance(item, dict):
                continue
            video_url = str(item.get("url") or "").strip()
            if not video_url:
                continue
            normalized_item: Dict[str, Any] = {"url": video_url}
            for key in ("start", "end", "ends"):
                raw_val = item.get(key)
                if raw_val is None or str(raw_val).strip() == "":
                    continue
                try:
                    normalized_item[key] = int(float(raw_val))
                except Exception:
                    normalized_item[key] = raw_val
            normalized_video_list.append(normalized_item)
        if normalized_video_list:
            options["video_list"] = normalized_video_list

    if isinstance(req.ref_video_urls, list):
        ref_video_urls = _limit_string_list_input(req.ref_video_urls, None)
        if ref_video_urls:
            options["reference_video_urls"] = ref_video_urls

    source_video_url = str(
        req.video_url
        or req.source_video_url
        or ""
    ).strip()
    if source_video_url:
        options["video_url"] = source_video_url

    upscale_factor_text = str(req.upscale_factor or "").strip()
    if upscale_factor_text:
        options["upscale_factor"] = upscale_factor_text

    normalized_mode = str(mode if mode is not None else (req.mode or "")).strip().lower()
    if normalized_mode:
        options["mode"] = normalized_mode
        options["__mode_source"] = "request"

    normalized_ref_mode = _normalize_video_ref_mode(getattr(req, "ref_mode", None))
    if normalized_ref_mode:
        options["ref_mode"] = normalized_ref_mode
        options["__ref_mode_source"] = "request"

    normalized_quality = str(quality if quality is not None else (req.quality or "")).strip().lower()
    if normalized_quality:
        options["quality"] = normalized_quality

    normalized_output_format = str(output_format if output_format is not None else (req.output_format or req.outputFormat or "")).strip().lower()
    if normalized_output_format:
        options["output_format"] = normalized_output_format

    if req.sound is not None:
        options["sound"] = bool(req.sound)

    if req.multi_shots is not None:
        options["multi_shots"] = bool(req.multi_shots)

    if req.draft_mode is not None:
        options["draft"] = bool(req.draft_mode)

    # Kling 3.0 API requires input.sound=true when multi_shots=true.
    if bool(options.get("multi_shots")):
        options["sound"] = True

    if isinstance(req.multi_prompt, list):
        options["multi_prompt"] = req.multi_prompt

    if isinstance(req.kling_elements, list):
        options["kling_elements"] = req.kling_elements

    return options


from app.services.generation_runtime.asset_registration import (  # noqa: E402,F401
    _asset_meta_matches_registration_context,
    _bind_generated_media_to_entity,
    _bind_generated_media_to_shot,
    _extract_provider_model_from_result,
    _find_existing_asset_for_registration,
    _log_api_switch_regenerate_if_needed,
    _normalize_asset_idempotency_key,
    _normalize_asset_url_for_dedup,
    _normalize_entity_type,
    _register_asset_helper,
    _resolve_latest_asset_provider_model,
    _resolve_subject_dependency_source_asset_url,
    _serialize_asset_row,
)

