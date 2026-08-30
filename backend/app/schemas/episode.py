# -*- coding: utf-8 -*-
"""Episode / script-segment API schemas."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ScriptSegmentBase(BaseModel):
    pid: str
    title: str
    content_revised: str
    content_original: str
    narrative_function: str
    analysis: str

class ScriptSegmentOut(ScriptSegmentBase):
    id: int
    class Config:
        from_attributes = True

class EpisodeCreate(BaseModel):
    title: str = "Episode 1"
    script_content: Optional[str] = ""
    episode_info: Optional[Dict] = {}
    ai_scene_analysis_result: Optional[str] = None
    ai_scene_analysis_scene_markdown: Optional[str] = None
    ai_entity_design_result: Optional[str] = None
    character_profiles: Optional[List[Dict[str, Any]]] = None
    ai_stage_outputs: Optional[str] = None

class EpisodeUpdate(BaseModel):
    title: Optional[str] = None
    script_content: Optional[str] = None
    episode_info: Optional[Dict] = None
    ai_scene_analysis_result: Optional[str] = None
    ai_scene_analysis_scene_markdown: Optional[str] = None
    ai_scene_analysis_subject_index: Optional[str] = None
    ai_scene_analysis_adaptation: Optional[str] = None
    character_profiles: Optional[List[Dict[str, Any]]] = None
    ai_entity_design_result: Optional[str] = None
    ai_stage_outputs: Optional[str] = None

class EpisodeListOut(BaseModel):
    id: int
    project_id: int
    title: str
    episode_info: Optional[Dict] = {}
    class Config:
        from_attributes = True

class EpisodeOut(BaseModel):
    id: int
    project_id: int
    title: str
    script_content: Optional[str]
    episode_info: Optional[Dict] = {}
    ai_scene_analysis_result: Optional[str] = None
    ai_scene_analysis_scene_markdown: Optional[str] = None
    ai_scene_analysis_subject_index: Optional[str] = None
    ai_scene_analysis_adaptation: Optional[str] = None
    ai_entity_design_result: Optional[str] = None
    ai_stage_outputs: Optional[str] = None
    character_profiles: Optional[List[Dict[str, Any]]] = []
    script_segments: List[ScriptSegmentOut] = []
    class Config:
        from_attributes = True


class ProjectEpisodeScriptsGenerateRequest(BaseModel):
    generator_kind: Optional[str] = None  # promo | story
    episodes_count: Optional[int] = None
    episode_duration_minutes: Optional[int] = None
    episode_id: Optional[int] = None  # Optional. Generate a specific episode only
    episode_number: Optional[int] = None  # Optional alias for single-episode generation
    script_mode: Optional[str] = None
    target_audience: Optional[str] = None
    script_title: Optional[str] = None
    function_name: Optional[str] = None
    system_api_id: Optional[int] = None
    overwrite_existing: bool = True
    retry_failed_only: bool = False
    extra_notes: Optional[str] = None
    episode_generation_guidance: Optional[str] = None
    strict_markdown: bool = True
