# -*- coding: utf-8 -*-
"""Shot API schemas."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class ShotCreate(BaseModel):
    shot_id: str
    shot_name: Optional[str] = None
    start_frame: Optional[str] = None
    end_frame: Optional[str] = None
    video_content: Optional[str] = None
    duration: Optional[str] = None
    associated_entities: Optional[str] = None
    scene_code: Optional[str] = None # 'Scene ID' from header user input
    project_id: Optional[int] = None
    episode_id: Optional[int] = None
    shot_logic_cn: Optional[str] = None
    keyframes: Optional[str] = None
    
    # Optional legacy/AI fields
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    prompt: Optional[str] = None
    technical_notes: Optional[str] = None

class ShotBatchCreateItem(BaseModel):
    scene_id: int
    shot: ShotCreate

class ShotBatchCreateRequest(BaseModel):
    items: List[ShotBatchCreateItem]
    recompute_cost: Optional[bool] = False
    # When True (default), skip entire scene if it already has active shots.
    skip_existing_scene_shots: Optional[bool] = True


class ShotUpdate(BaseModel):
    shot_id: Optional[str] = None
    shot_name: Optional[str] = None
    start_frame: Optional[str] = None
    end_frame: Optional[str] = None
    video_content: Optional[str] = None
    duration: Optional[str] = None
    associated_entities: Optional[str] = None
    scene_code: Optional[str] = None
    project_id: Optional[int] = None
    episode_id: Optional[int] = None
    shot_logic_cn: Optional[str] = None
    keyframes: Optional[str] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    prompt: Optional[str] = None
    technical_notes: Optional[str] = None

class ShotOut(BaseModel):
    id: int
    scene_id: int
    project_id: Optional[int]
    episode_id: Optional[int]
    shot_id: Optional[str]
    shot_name: Optional[str]
    start_frame: Optional[str]
    end_frame: Optional[str]
    video_content: Optional[str]
    duration: Optional[str]
    associated_entities: Optional[str]
    shot_logic_cn: Optional[str]
    keyframes: Optional[str]
    
    scene_code: Optional[str]

    image_url: Optional[str]
    video_url: Optional[str]
    prompt: Optional[str]
    technical_notes: Optional[str]
    end_frame_url: Optional[str] = None
    prompt_preview_cn: Optional[str] = None
    prompt_preview_en: Optional[str] = None
    is_compact: Optional[bool] = None
    
    class Config:
        from_attributes = True
