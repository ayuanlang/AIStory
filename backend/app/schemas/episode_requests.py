# -*- coding: utf-8 -*-
"""Episode / character-canon / story-generator request schemas."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class CharacterProfileGenerateRequest(BaseModel):
    name: str
    function_name: Optional[str] = None
    system_api_id: Optional[int] = None
    identity: Optional[str] = None
    body_features: Optional[str] = None
    style_tags: Optional[List[str]] = []
    extra_notes: Optional[str] = None


class CharacterProfilesUpdateRequest(BaseModel):
    character_profiles: List[Dict[str, Any]]


class CharacterCanonInputRequest(BaseModel):
    name: Optional[str] = None
    selected_tag_ids: Optional[List[str]] = None
    selected_identity_ids: Optional[List[str]] = None
    custom_identity: Optional[str] = None
    body_features: Optional[str] = None
    custom_style_tags: Optional[str] = None
    extra_notes: Optional[str] = None


class CharacterCanonCategoriesRequest(BaseModel):
    tag_categories: Optional[List[Dict[str, Any]]] = None
    identity_categories: Optional[List[Dict[str, Any]]] = None


class StoryGeneratorRequest(BaseModel):
    mode: str  # 'global' | 'episode'
    generator_kind: Optional[str] = None  # promo | story
    episodes_count: Optional[int] = None
    episode_duration_minutes: Optional[int] = 1
    episode_number: Optional[int] = None
    script_mode: Optional[str] = None
    target_audience: Optional[str] = None
    # Project Overview / Basic Information (optional but should be forwarded to LLM when provided)
    script_title: Optional[str] = None
    type: Optional[str] = None
    language: Optional[str] = None
    base_positioning: Optional[str] = None
    Global_Style: Optional[str] = None
    foreshadowing: Optional[str] = None
    logline: Optional[str] = None
    theme: Optional[str] = None
    core_conflict: Optional[str] = None
    characters: Optional[str] = None
    background: Optional[str] = None
    setup: Optional[str] = None
    development: Optional[str] = None
    turning_points: Optional[str] = None
    climax: Optional[str] = None
    resolution: Optional[str] = None
    suspense: Optional[str] = None
    classic_framework: Optional[str] = None
    wild_creative_notes: Optional[str] = None
    extra_notes: Optional[str] = None
    episode_generation_guidance: Optional[str] = None
    trending_ai_short_dramas_report: Optional[Dict[str, Any]] = None
    ai_short_drama_industry_report: Optional[Dict[str, Any]] = None
    strict_markdown: bool = True
    function_name: Optional[str] = None
    system_api_id: Optional[int] = None


class ScriptScenesGenerateRequest(BaseModel):
    scene_count: Optional[int] = None
    background: Optional[str] = None
    setup: Optional[str] = None
    development: Optional[str] = None
    turning_points: Optional[str] = None
    climax: Optional[str] = None
    resolution: Optional[str] = None
    suspense: Optional[str] = None
    foreshadowing: Optional[str] = None
    extra_notes: Optional[str] = None
    replace_existing_scenes: Optional[bool] = True


EPISODE_SCENE_GEN_STATUS_KEY = "episode_scene_generation_status"

