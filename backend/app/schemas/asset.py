# -*- coding: utf-8 -*-
"""Asset library API schemas."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class AssetCreate(BaseModel):
    url: str
    type: str # image, video
    meta_info: Optional[dict] = {}
    remark: Optional[str] = None

class AssetUpdate(BaseModel):
    remark: Optional[str] = None
    meta_info: Optional[dict] = None

class AssetRebindShotMediaRequest(BaseModel):
    project_id: Optional[int] = None
    episode_id: Optional[int] = None
    scene_id: Optional[int] = None
    shot_id: Optional[int] = None
    limit: int = 2000
    dry_run: bool = False
    include_entities: bool = True
    include_shots: bool = True
    overwrite_existing: bool = True


class AssetBackfillEpisodeMediaRequest(BaseModel):
    project_id: int
    episode_id: int
    dry_run: bool = False
    include_shots: bool = True
    include_entities: bool = True
    limit: int = 10000
    overwrite_existing: bool = True


class AssetBackfillMetadataRequest(BaseModel):
    asset_ids: Optional[List[int]] = None
    project_id: Optional[int] = None
    episode_id: Optional[int] = None
    limit: int = 200
    overwrite_existing: bool = False
    dry_run: bool = False
