# -*- coding: utf-8 -*-
"""Image / video / voice generation request schemas."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel


class GenerationRequest(BaseModel):
    prompt: str
    system_api_id: Optional[int] = None
    function_name: Optional[str] = None
    negative_prompt: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    aspect_ratio: Optional[str] = None
    image_size: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    quality: Optional[str] = None
    output_format: Optional[str] = None
    outputFormat: Optional[str] = None
    response_format: Optional[str] = None
    responseFormat: Optional[str] = None
    output_compression: Optional[str] = None
    outputCompression: Optional[str] = None
    background: Optional[str] = None
    ref_image_url: Optional[Union[str, List[str]]] = None
    image_urls: Optional[List[str]] = None
    imageUrls: Optional[List[str]] = None
    project_id: Optional[int] = None
    episode_id: Optional[int] = None
    scene_id: Optional[int] = None
    shot_id: Optional[int] = None
    shot_number: Optional[str] = None
    shot_name: Optional[str] = None
    entity_id: Optional[int] = None
    entity_name: Optional[str] = None
    subject_name: Optional[str] = None
    subject_type: Optional[str] = None
    entity_type: Optional[str] = None
    asset_type: Optional[str] = None
    callback_url: Optional[str] = None
    callbackUrl: Optional[str] = None
    callBackUrl: Optional[str] = None
    files_url: Optional[List[str]] = None
    filesUrl: Optional[List[str]] = None
    file_url: Optional[str] = None
    fileUrl: Optional[str] = None
    mask_url: Optional[str] = None
    maskUrl: Optional[str] = None
    is_enhance: Optional[bool] = None
    isEnhance: Optional[bool] = None
    upload_cn: Optional[bool] = None
    uploadCn: Optional[bool] = None
    enable_fallback: Optional[bool] = None
    enableFallback: Optional[bool] = None
    fallback_model: Optional[str] = None
    fallbackModel: Optional[str] = None
    seed: Optional[int] = None
    cfg: Optional[float] = None
    mode: Optional[str] = None

class VideoGenerationRequest(BaseModel):
    prompt: str
    function_name: Optional[str] = None
    system_api_id: Optional[int] = None
    negative_prompt: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    quality: Optional[str] = None
    output_format: Optional[str] = None
    outputFormat: Optional[str] = None
    ref_image_url: Optional[Union[str, List[str]]] = None
    ref_video_urls: Optional[List[str]] = None
    image_urls: Optional[List[str]] = None
    audio_ids: Optional[List[str]] = None
    video_list: Optional[List[Dict[str, Any]]] = None
    last_frame_url: Optional[str] = None
    duration: Optional[float] = 5.0
    input_duration: Optional[float] = None
    input_duration_seconds: Optional[float] = None
    aspect_ratio: Optional[str] = None
    mode: Optional[str] = None
    ref_mode: Optional[str] = None
    sound: Optional[bool] = None
    multi_shots: Optional[bool] = None
    multi_prompt: Optional[List[Dict[str, Any]]] = None
    kling_elements: Optional[List[Dict[str, Any]]] = None
    project_id: Optional[int] = None
    episode_id: Optional[int] = None
    scene_id: Optional[int] = None
    shot_id: Optional[int] = None
    draft_mode: Optional[bool] = False
    resolution: Optional[str] = None
    video_resolution: Optional[str] = None
    shot_number: Optional[str] = None
    shot_name: Optional[str] = None
    entity_name: Optional[str] = None
    subject_name: Optional[str] = None
    asset_type: Optional[str] = None
    keyframes: Optional[List[str]] = None
    callback_url: Optional[str] = None
    callbackUrl: Optional[str] = None
    callBackUrl: Optional[str] = None
    video_url: Optional[str] = None
    source_video_url: Optional[str] = None
    upscale_factor: Optional[Union[str, int]] = None
    seed: Optional[int] = None
    use_prev_video: Optional[bool] = False
    has_video_input: Optional[bool] = None


class VoiceGenerationRequest(BaseModel):
    prompt: str
    function_name: Optional[str] = None
    system_api_id: Optional[int] = None
    negative_prompt: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    project_id: Optional[int] = None
    entity_id: Optional[int] = None
    shot_id: Optional[int] = None
    shot_number: Optional[str] = None
    shot_name: Optional[str] = None
    asset_type: Optional[str] = None
    use_llm_param_planning: Optional[bool] = False
    planner_system_prompt: Optional[str] = None
    language_code: Optional[str] = None
    project_language: Optional[str] = None
    seed: Optional[int] = None
    provider_options: Optional[Dict[str, Any]] = None
    # KIE Suno music generation (entity reference audio)
    custom_mode: Optional[bool] = None
    customMode: Optional[bool] = None
    instrumental: Optional[bool] = None
    suno_model: Optional[str] = None
    sunoModel: Optional[str] = None
    suno_style: Optional[str] = None
    sunoStyle: Optional[str] = None
    suno_title: Optional[str] = None
    sunoTitle: Optional[str] = None
    negative_tags: Optional[str] = None
    negativeTags: Optional[str] = None
    vocal_gender: Optional[str] = None
    vocalGender: Optional[str] = None
    style_weight: Optional[float] = None
    styleWeight: Optional[float] = None
    weirdness_constraint: Optional[float] = None
    weirdnessConstraint: Optional[float] = None
    audio_weight: Optional[float] = None
    audioWeight: Optional[float] = None
    persona_id: Optional[str] = None
    personaId: Optional[str] = None
    persona_model: Optional[str] = None
    personaModel: Optional[str] = None

