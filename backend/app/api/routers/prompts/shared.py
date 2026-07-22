# -*- coding: utf-8 -*-
"""Prompts + scene-analysis flow + analyze_scene (P5)."""
from __future__ import annotations

import logging
import os
import re
import uuid
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.time_utils import BEIJING_TZ, now_bj_iso
from app.db.session import SessionLocal, get_db
from app.models import all_models as models
from app.models.all_models import *

logger = logging.getLogger("api_logger")
router = APIRouter(tags=["prompts-analyze"])

from app.schemas.agent import AnalyzeSceneRequest
from app.services.agent_service import agent_service
from app.services.billing_service import billing_service
from app.services.llm_service import llm_service
from app.core.prompts.skills_loader import load_skills_registry, get_skill_meta  # noqa: E402
from app.core.prompts.scene_analysis_feature_skills import (  # noqa: E402
    get_scene_analysis_feature_catalog,
    resolve_scene_analysis_feature_bundle,
)
from app.api.settings import (  # noqa: E402
    get_scene_analysis_system_config,
    get_script_analysis_flow_config,
)
from app.services.script_analysis_flow.registry import (  # noqa: E402
    get_script_analysis_flow_registry,
    build_script_analysis_flow_plan,
)


def _bind_endpoint_helpers(*, include_routers: bool = True) -> None:
    from app.api.routers.helper_bind import bind_shared_helpers
    bind_shared_helpers(globals(), __name__, include_routers=include_routers)

# Early bind removed; __init__ still rebinds for section modules.

from app.services.prompt_resolve import (  # noqa: E402
    _PROMPT_SKILL_ALIAS,
    _build_prompt_resolution_debug,
    _resolve_prompt_file_path,
    _resolve_prompt_text,
)


# _resolve_prompt_text -> prompt_resolve


# _resolve_prompt_file_path -> prompt_resolve


class PromptContentUpdateRequest(BaseModel):
    content: str


@router.get("/prompts/skills")
async def list_prompt_skills(current_user: User = Depends(get_current_user)):
    """List available prompt skills and metadata for frontend/tooling discovery."""
    try:
        registry = load_skills_registry()
        skills = registry.get("skills") if isinstance(registry.get("skills"), list) else []
        return {
            "version": registry.get("version", 1),
            "skills": skills,
        }
    except Exception as exc:
        logger.exception("Failed to load prompt skills registry: %s", exc)
        return {
            "version": 1,
            "skills": [],
            "degraded": True,
        }


@router.get("/prompts/skills/{skill_id}")
async def get_prompt_skill_detail(skill_id: str, current_user: User = Depends(get_current_user)):
    """Get one prompt skill metadata by skill id."""
    normalized_skill_id = str(skill_id or "").strip()
    # Single-segment refs like `skills/shot_generation.md` are routed here before
    # `/prompts/{filename:path}`; delegate to prompt file loading when the segment
    # is clearly a prompt filename rather than a registry skill id.
    if normalized_skill_id.endswith((".md", ".txt", ".json")):
        return await get_prompt_content(f"skills/{normalized_skill_id}", current_user)

    meta = get_skill_meta(normalized_skill_id)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Skill '{normalized_skill_id}' not found.")
    return meta


@router.get("/prompts/scene-analysis/features")
async def get_scene_analysis_feature_options(current_user: User = Depends(get_current_user)):
    """List feature-stack modes and enum dimensions for scene analysis prompt composition."""
    return get_scene_analysis_feature_catalog()


def _scene_analysis_slot_origin(slot_token: Any) -> str:
    token = str(slot_token or "").strip()
    if not token:
        return "unknown"
    if token == "[[SCENE_ANALYSIS_COMBO_RULES]]":
        return "global_combo"
    if token == "[[SCENE_ANALYSIS_CHARACTER_GOAL_ALIGNMENT_RULES]]":
        return "local_character_goal_alignment"
    if token.startswith("[[SCENE_ANALYSIS_ENVIRONMENT_COMBO_") or token == "[[SCENE_ANALYSIS_ENVIRONMENT_COMBO_RULES]]":
        return "local_environment_combo"
    if token.startswith("[[SCENE_ANALYSIS_CHARACTER_COMBO_") or token == "[[SCENE_ANALYSIS_CHARACTER_COMBO_RULES]]":
        return "local_character_combo"
    if token.startswith("[[SCENE_ANALYSIS_PROP_COMBO_") or token == "[[SCENE_ANALYSIS_PROP_COMBO_RULES]]":
        return "local_prop_combo"
    if token.startswith("[[SCENE_ANALYSIS_ENVIRONMENT_"):
        return "local_environment_dimension"
    if token.startswith("[[SCENE_ANALYSIS_CHARACTER_"):
        return "local_character_dimension"
    if token.startswith("[[SCENE_ANALYSIS_PROP_"):
        return "local_prop_dimension"
    if token.startswith("[[SCENE_ANALYSIS_") and token.endswith("_RULES]]"):
        return "global_dimension"
    return "unknown"


def _build_scene_analysis_slot_blocks_summary(bundle: Dict[str, Any]) -> List[Dict[str, Any]]:
    slot_blocks = bundle.get("slot_blocks") if isinstance(bundle.get("slot_blocks"), dict) else {}
    selected_skills = bundle.get("selected_skills") if isinstance(bundle.get("selected_skills"), list) else []
    known_slot_tokens = bundle.get("known_slot_tokens") if isinstance(bundle.get("known_slot_tokens"), list) else []

    bucketed_skills: Dict[str, List[Dict[str, Any]]] = {}
    for item in selected_skills:
        if not isinstance(item, dict):
            continue
        slot_token = str(item.get("slot_token") or "").strip()
        if not slot_token:
            continue
        bucketed_skills.setdefault(slot_token, []).append(item)

    summary_tokens: List[str] = []
    seen_tokens = set()
    for token in list(slot_blocks.keys()) + list(bucketed_skills.keys()) + list(known_slot_tokens):
        token_text = str(token or "").strip()
        if not token_text or token_text in seen_tokens:
            continue
        seen_tokens.add(token_text)
        summary_tokens.append(token_text)

    return [
        {
            "slot_token": token,
            "slot_origin": _scene_analysis_slot_origin(token),
            "has_block": bool(slot_blocks.get(token)),
            "skill_count": len(bucketed_skills.get(token) or []),
            "skill_ids": [item.get("skill_id") for item in (bucketed_skills.get(token) or []) if item.get("skill_id")],
            "titles": [item.get("title") for item in (bucketed_skills.get(token) or []) if item.get("title")],
        }
        for token in summary_tokens
    ]


@router.post("/prompts/scene-analysis/route-preview")
async def preview_scene_analysis_route(
    request: AnalyzeSceneRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Preview the decision-engine routing result for scene analysis without calling the LLM."""
    requested_mode = str(getattr(request, "scene_analysis_mode", "") or "").strip() or None
    effective_mode = requested_mode
    if not effective_mode:
        try:
            effective_mode = str(get_scene_analysis_system_config(db).get("default_mode") or "").strip() or None
        except Exception as config_err:
            logger.warning("[scene-analysis-route-preview] failed to read system default mode: %s", config_err)
    bundle = resolve_scene_analysis_feature_bundle(
        project_metadata=request.project_metadata,
        explicit_features=getattr(request, "scene_analysis_features", None),
        script_text=getattr(request, "text", None),
        mode=effective_mode,
    )
    return {
        "requested_mode": requested_mode,
        "effective_mode": bundle.get("mode"),
        "mode": bundle.get("mode"),
        "enabled": bundle.get("enabled"),
        "base_prompt_file": bundle.get("base_prompt_file"),
        "slot_blocks": bundle.get("slot_blocks") or {},
        "slot_blocks_summary": _build_scene_analysis_slot_blocks_summary(bundle),
        "known_slot_tokens": bundle.get("known_slot_tokens") or [],
        "normalized_features": bundle.get("normalized_features") or {},
        "resolved_dimensions": bundle.get("resolved_dimensions") or {},
        "selected_skills": [
            {
                "skill_id": item.get("skill_id"),
                "dimension": item.get("dimension"),
                "value": item.get("value"),
                "title": item.get("title"),
                "source": item.get("source"),
                "slot_token": item.get("slot_token"),
                "slot_origin": _scene_analysis_slot_origin(item.get("slot_token")),
                "slot_has_block": bool((bundle.get("slot_blocks") or {}).get(str(item.get("slot_token") or ""))),
            }
            for item in (bundle.get("selected_skills") or [])
        ],
        "combo_matches": [
            {
                "skill_id": item.get("skill_id"),
                "title": item.get("title"),
                "when": item.get("when") or {},
                "slot_token": item.get("slot_token"),
                "slot_origin": _scene_analysis_slot_origin(item.get("slot_token")),
                "slot_has_block": bool((bundle.get("slot_blocks") or {}).get(str(item.get("slot_token") or ""))),
            }
            for item in (bundle.get("combo_matches") or [])
        ],
        "diagnostics": bundle.get("diagnostics") or [],
    }


@router.get("/prompts/scene-analysis/flow-registry")
async def get_scene_analysis_flow_registry_preview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Preview the planned script-analysis DAG and stage-3 auto-start switches."""
    _ = current_user
    cfg = get_script_analysis_flow_config(db)
    db.commit()
    return get_script_analysis_flow_registry(cfg)


@router.post("/prompts/scene-analysis/flow-plan")
async def preview_scene_analysis_flow_plan(
    payload: Dict[str, Any] = Body(default_factory=dict),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Preview which script-analysis nodes would auto-run for a requested flow slice."""
    _ = current_user
    cfg = get_script_analysis_flow_config(db)
    db.commit()
    requested_nodes = payload.get("requested_nodes") if isinstance(payload.get("requested_nodes"), list) else None
    start_node = payload.get("start_node")
    return build_script_analysis_flow_plan(
        cfg,
        requested_nodes=requested_nodes,
        start_node=start_node,
    )


