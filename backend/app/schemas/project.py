# -*- coding: utf-8 -*-
"""Project / share API schemas."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    title: str
    description: Optional[str] = None
    global_info: dict = {}
    aspectRatio: Optional[str] = None
    share_users: Optional[List[str]] = None
    reviewer_users: Optional[List[str]] = None

class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    global_info: Optional[dict] = None
    aspectRatio: Optional[str] = None
    cover_image: Optional[str] = None
    share_users: Optional[List[str]] = None
    reviewer_users: Optional[List[str]] = None

class ProjectOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    owner_id: int
    global_info: dict
    aspectRatio: Optional[str] = None
    cover_image: Optional[str] = None
    # Per-episode cover poster URLs (ordered by episode_id) for project-card rotation.
    cover_images: Optional[List[str]] = None
    is_owner: Optional[bool] = True
    # Superuser temporary peek (not owner / not shared): view-only card in project list.
    is_temp_view: Optional[bool] = False
    can_edit: Optional[bool] = True
    generation_seed: Optional[int] = None
    seed_initialized: Optional[bool] = False
    missing_basic_fields: Optional[List[str]] = None
    has_missing_basic_info: Optional[bool] = False
    share_count: Optional[int] = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    class Config:
        from_attributes = True


class ProjectShareCreate(BaseModel):
    target_user: str
    role: Optional[str] = "editor"
    permissions: Optional[Dict[str, Any]] = None


class ProjectShareOut(BaseModel):
    id: int
    project_id: int
    user_id: int
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: str = "editor"
    permissions: Dict[str, Any] = {}
    created_at: Optional[str] = None
