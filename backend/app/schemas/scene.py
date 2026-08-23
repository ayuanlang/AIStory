# -*- coding: utf-8 -*-
"""Scene API schemas."""
from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, field_validator


class SceneCreate(BaseModel):
    scene_no: str
    original_script_text: str
    scene_name: Optional[str] = None
    equivalent_duration: Optional[str] = None
    core_scene_info: Optional[str] = None
    environment_name: Optional[str] = None
    linked_characters: Optional[str] = None
    key_props: Optional[str] = None

class SceneBatchUpsertRequest(BaseModel):
    scenes: List[SceneCreate]
    recompute_cost: Optional[bool] = False
    # When True (default), skip rows whose scene_no already exists (do not overwrite).
    # Set False only when an intentional full replace/update is required.
    skip_existing: Optional[bool] = True

class ScenePurgeRequest(BaseModel):
    clear_progress: Optional[bool] = True

class SceneOut(BaseModel):
    id: int
    scene_no: str
    original_script_text: str = ""
    scene_name: Optional[str]
    equivalent_duration: Optional[str]
    core_scene_info: Optional[str]
    environment_name: Optional[str]
    linked_characters: Optional[str]
    key_props: Optional[str]

    @field_validator("original_script_text", mode="before")
    @classmethod
    def coerce_original_script_text(cls, value: Any) -> str:
        return "" if value is None else str(value)

    class Config:
        from_attributes = True


class SceneRegenerateRequest(BaseModel):
    user_requirements: str
    prompt_file: Optional[str] = "scene_regenerate.txt"
    system_prompt: Optional[str] = None
    max_scenes: Optional[int] = 4
    entity_only_mode: Optional[bool] = False
