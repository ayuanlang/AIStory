# -*- coding: utf-8 -*-
"""Entity API schemas (shared by workspace + entities routers)."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

import pydantic
from pydantic import BaseModel

from app.core.entity_token import normalize_entity_token


def coerce_visual_dependencies(value: Any) -> List[str]:
    candidates: List[Any] = []
    if isinstance(value, list):
        candidates = value
    elif isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        if (raw.startswith("[") and raw.endswith("]")) or (raw.startswith("{") and raw.endswith("}")):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    candidates = parsed
                elif isinstance(parsed, str):
                    candidates = [parsed]
            except Exception:
                candidates = []
        if not candidates:
            candidates = re.split(r"[\n,，;；|]", raw)
    elif value is not None:
        candidates = [value]

    out: List[str] = []
    seen = set()
    for item in candidates:
        stable = str(item or "").strip()
        if not stable:
            continue
        key = normalize_entity_token(stable)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(stable)
    return out


def coerce_anchor_description(value: Any) -> Optional[str]:
    """Normalize LLM/import payloads: phrase arrays -> comma-separated string."""
    if value is None:
        return None
    if isinstance(value, list):
        parts: List[str] = []
        for item in value:
            if isinstance(item, (list, tuple)):
                for sub in item:
                    text = str(sub or "").strip()
                    if text:
                        parts.append(text)
                continue
            text = str(item or "").strip()
            if text:
                parts.append(text)
        return ", ".join(parts)
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


# Back-compat alias used across routers.
_coerce_visual_dependencies = coerce_visual_dependencies


class EntityCreate(BaseModel):
    name: str
    type: str  # character, environment, prop
    description: str
    episode_id: Optional[int] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    audio_url: Optional[str] = None
    generation_prompt_en: Optional[str] = None
    generation_prompt_cn: Optional[str] = None
    anchor_description: Optional[str] = None

    name_en: Optional[str] = None
    base_name_en: Optional[str] = None
    gender: Optional[str] = None
    role: Optional[str] = None
    archetype: Optional[str] = None
    appearance_cn: Optional[str] = None
    clothing: Optional[str] = None
    action_characteristics: Optional[str] = None

    atmosphere: Optional[str] = None
    visual_params: Optional[str] = None
    narrative_description: Optional[str] = None

    visual_dependencies: Optional[List[str]] = []
    dependency_strategy: Optional[Dict[str, Any]] = {}
    custom_attributes: Optional[Dict[str, Any]] = {}

    @pydantic.field_validator("anchor_description", mode="before")
    @classmethod
    def validate_anchor_description(cls, v: Any) -> Optional[str]:
        return coerce_anchor_description(v)

    @pydantic.field_validator("visual_dependencies", mode="before")
    @classmethod
    def validate_visual_dependencies(cls, v: Any) -> List[str]:
        return coerce_visual_dependencies(v)

    @pydantic.field_validator("dependency_strategy", "custom_attributes", mode="before")
    @classmethod
    def validate_dict_fields(cls, v: Any) -> Dict[str, Any]:
        if isinstance(v, dict):
            return v
        if isinstance(v, str) and v.strip():
            try:
                parsed = json.loads(v.strip())
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                pass
        return {}


class EntityOut(BaseModel):
    id: int
    episode_id: Optional[int] = None
    name: Optional[str] = None
    type: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str]
    video_url: Optional[str] = None
    audio_url: Optional[str] = None
    generation_prompt_en: Optional[str]
    generation_prompt_cn: Optional[str]
    anchor_description: Optional[str]

    name_en: Optional[str] = None
    base_name_en: Optional[str] = None
    gender: Optional[str] = None
    role: Optional[str] = None
    archetype: Optional[str] = None
    appearance_cn: Optional[str] = None
    clothing: Optional[str] = None
    action_characteristics: Optional[str] = None

    atmosphere: Optional[str] = None
    visual_params: Optional[str] = None
    narrative_description: Optional[str] = None

    visual_dependencies: Optional[List[str]] = []
    dependency_strategy: Optional[Dict[str, Any]] = {}
    custom_attributes: Optional[Dict[str, Any]] = {}

    @pydantic.field_validator("anchor_description", mode="before")
    @classmethod
    def validate_anchor_description(cls, v: Any) -> Optional[str]:
        return coerce_anchor_description(v)

    @pydantic.field_validator("visual_dependencies", mode="before")
    @classmethod
    def validate_visual_dependencies(cls, v: Any) -> List[str]:
        return coerce_visual_dependencies(v)

    @pydantic.field_validator("dependency_strategy", "custom_attributes", mode="before")
    @classmethod
    def validate_dict_fields(cls, v: Any) -> Dict[str, Any]:
        if isinstance(v, dict):
            return v
        if isinstance(v, str) and v.strip():
            try:
                parsed = json.loads(v.strip())
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                pass
        return {}

    class Config:
        from_attributes = True


class EntityUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    description: Optional[str] = None
    episode_id: Optional[int] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    audio_url: Optional[str] = None
    generation_prompt_en: Optional[str] = None
    generation_prompt_cn: Optional[str] = None
    anchor_description: Optional[str] = None

    name_en: Optional[str] = None
    base_name_en: Optional[str] = None
    gender: Optional[str] = None
    role: Optional[str] = None
    archetype: Optional[str] = None
    appearance_cn: Optional[str] = None
    clothing: Optional[str] = None
    action_characteristics: Optional[str] = None

    atmosphere: Optional[str] = None
    visual_params: Optional[str] = None
    narrative_description: Optional[str] = None

    visual_dependencies: Optional[List[str]] = None
    dependency_strategy: Optional[Dict[str, Any]] = None

    @pydantic.field_validator("anchor_description", mode="before")
    @classmethod
    def validate_anchor_description(cls, v: Any) -> Optional[str]:
        return coerce_anchor_description(v)

    class Config:
        extra = "allow"
