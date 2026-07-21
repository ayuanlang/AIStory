# -*- coding: utf-8 -*-
"""Entity CRUD routes (P8)."""
from __future__ import annotations

import logging
import os
import re
import uuid
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
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
router = APIRouter(tags=["entities"])


def _bind_endpoint_helpers() -> None:
    from app.api.routers.helper_bind import bind_shared_helpers
    bind_shared_helpers(globals(), __name__)

_bind_endpoint_helpers()


@router.get("/projects/{project_id}/entities", response_model=List[EntityOut])
def read_entities(
    project_id: int,
    type: Optional[str] = None,
    episode_id: Optional[int] = None,
    include_project_null_episode: Optional[bool] = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = _require_project_access(db, project_id, current_user)

    query = db.query(Entity).filter(Entity.project_id == project_id, _active_entity_clause())
    if type:
        query = query.filter(Entity.type == type)
    if episode_id is not None:
        if bool(include_project_null_episode):
            query = query.filter(or_(Entity.episode_id == episode_id, Entity.episode_id.is_(None)))
        else:
            query = query.filter(Entity.episode_id == episode_id)
    entities = query.all()
    repaired_entities = _repair_entities_image_urls_from_assets(db, current_user, project, entities)

    # Diagnostics for Render image visibility: verify returned URLs and local file presence.
    total = len(repaired_entities or [])
    with_image = 0
    relative_upload = 0
    absolute_upload = 0
    missing_local = 0
    sample_missing: List[Dict[str, Any]] = []
    for ent in repaired_entities or []:
        diag = _diagnose_entity_image_url(getattr(ent, "image_url", None))
        if not diag.get("is_empty"):
            with_image += 1
        if diag.get("is_relative_upload"):
            relative_upload += 1
        if diag.get("is_absolute_upload"):
            absolute_upload += 1
        if diag.get("upload_suffix") and diag.get("local_exists") is False:
            missing_local += 1
            if len(sample_missing) < 5:
                sample_missing.append({
                    "entity_id": getattr(ent, "id", None),
                    "entity_name": getattr(ent, "name", None) or getattr(ent, "name_en", None),
                    "image_url": diag.get("raw"),
                    "upload_suffix": diag.get("upload_suffix"),
                    "local_path": diag.get("local_path"),
                })

    try:
        dumped_missing = json.dumps(sample_missing, ensure_ascii=False)
    except Exception:
        dumped_missing = "[]"

    logger.info(
        "[EntityImageReadDiag] project_id=%s user_id=%s total=%s with_image=%s rel_upload=%s abs_upload=%s missing_local=%s sample_missing=%s",
        project_id,
        getattr(current_user, "id", None),
        total,
        with_image,
        relative_upload,
        absolute_upload,
        missing_local,
        dumped_missing,
    )
    if oss_storage_service.is_enabled(db):
        for ent in repaired_entities or []:
            ent.image_url = _refresh_managed_media_url(getattr(ent, "image_url", None), db)
    return repaired_entities

@router.post("/projects/{project_id}/entities", response_model=EntityOut)
def create_entity(
    project_id: int,
    entity: EntityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    project = _require_project_access(db, project_id, current_user)

    if entity.episode_id is not None:
        episode = db.query(Episode).filter(Episode.id == entity.episode_id).first()
        if not episode or int(getattr(episode, "project_id", 0) or 0) != int(project_id):
            raise HTTPException(status_code=400, detail="episode_id does not belong to this project")

    _assert_allowed_persisted_media_url(entity.image_url, field_label="entity.image_url", db=db)

    normalized_name_candidates = set()
    for raw_name in (entity.name, entity.name_en):
        stable = str(raw_name or "").strip().lower()
        if stable:
            normalized_name_candidates.add(stable)

    if not normalized_name_candidates:
        raise HTTPException(status_code=400, detail="Entity name is required")

    normalized_type = str(entity.type or "").strip().lower()
    entity_name_expr = func.lower(func.trim(func.coalesce(Entity.name, "")))
    entity_name_en_expr = func.lower(func.trim(func.coalesce(Entity.name_en, "")))

    from sqlalchemy import or_
    if entity.episode_id is None:
        episode_scope_filter = Entity.episode_id.is_(None)
    else:
        episode_scope_filter = Entity.episode_id == entity.episode_id

    existing_entity = db.query(Entity).filter(
        Entity.project_id == project_id,
        episode_scope_filter,
        _active_entity_clause(),
        func.lower(func.trim(func.coalesce(Entity.type, ""))) == normalized_type,
        or_(
            entity_name_expr.in_(normalized_name_candidates),
            entity_name_en_expr.in_(normalized_name_candidates),
        ),
    ).first()

    if existing_entity:
        existing_entity.description = entity.description or existing_entity.description
        existing_entity.image_url = entity.image_url or existing_entity.image_url
        existing_entity.video_url = entity.video_url or existing_entity.video_url
        existing_entity.audio_url = entity.audio_url or existing_entity.audio_url
        existing_entity.generation_prompt_en = entity.generation_prompt_en or existing_entity.generation_prompt_en
        existing_entity.generation_prompt_cn = entity.generation_prompt_cn or existing_entity.generation_prompt_cn
        existing_entity.anchor_description = entity.anchor_description or existing_entity.anchor_description
        
        existing_entity.name_en = entity.name_en or existing_entity.name_en
        existing_entity.base_name_en = entity.base_name_en or existing_entity.base_name_en
        existing_entity.gender = entity.gender or existing_entity.gender
        existing_entity.role = entity.role or existing_entity.role
        existing_entity.archetype = entity.archetype or existing_entity.archetype
        existing_entity.appearance_cn = entity.appearance_cn or existing_entity.appearance_cn
        existing_entity.clothing = entity.clothing or existing_entity.clothing
        existing_entity.action_characteristics = entity.action_characteristics or existing_entity.action_characteristics
        
        existing_entity.atmosphere = entity.atmosphere or existing_entity.atmosphere
        existing_entity.visual_params = entity.visual_params or existing_entity.visual_params
        existing_entity.narrative_description = entity.narrative_description or existing_entity.narrative_description

        # Only merge structured lists/dicts if provided
        if entity.visual_dependencies:
            existing_entity.visual_dependencies = entity.visual_dependencies
        if entity.dependency_strategy:
            existing_entity.dependency_strategy = entity.dependency_strategy
        if entity.custom_attributes:
            existing_attr = dict(existing_entity.custom_attributes or {})
            existing_attr.update(entity.custom_attributes)
            existing_entity.custom_attributes = existing_attr

        if entity.episode_id is not None and existing_entity.episode_id is None:
            existing_entity.episode_id = entity.episode_id

        db.commit()
        db.refresh(existing_entity)
        return existing_entity

    # Create a new subject row if no duplicate exists.
    db_entity = Entity(
        project_id=project_id,
        episode_id=entity.episode_id,
        name=entity.name,
        type=entity.type,
        description=entity.description,
        image_url=entity.image_url,
        video_url=entity.video_url,
        audio_url=entity.audio_url,
        generation_prompt_en=entity.generation_prompt_en,
        generation_prompt_cn=entity.generation_prompt_cn,
        anchor_description=entity.anchor_description,
        
        name_en=entity.name_en,
        base_name_en=entity.base_name_en,
        gender=entity.gender,
        role=entity.role,
        archetype=entity.archetype,
        appearance_cn=entity.appearance_cn,
        clothing=entity.clothing,
        action_characteristics=entity.action_characteristics,
        
        atmosphere=entity.atmosphere,
        visual_params=entity.visual_params,
        narrative_description=entity.narrative_description,
        
        visual_dependencies=_coerce_visual_dependencies(entity.visual_dependencies),
        dependency_strategy=entity.dependency_strategy,
        custom_attributes=entity.custom_attributes or {}
    )
    db.add(db_entity)
    db.commit()
    db.refresh(db_entity)
    return db_entity


class EntityCloneWithLLMRequest(BaseModel):
    modification_instruction: str
    new_name_hint: Optional[str] = None
    episode_id: Optional[int] = None


def _extract_first_json_payload(text: str):
    import json
    text = str(text or "")

    # Attempt 1: Parse entire text via json5 (if available) first.
    json5_obj = _loads_json5_if_available(text)
    if isinstance(json5_obj, (dict, list)):
        return json5_obj

    # Attempt 2: Parse entire text with strict json.
    try:
        whole_obj = json.loads(text)
        if isinstance(whole_obj, (dict, list)):
            return whole_obj
    except Exception:
        pass

    # Attempt 3: Extract from first opening bracket to last closing bracket.
    first_idx = -1
    last_idx = -1
    for i, ch in enumerate(text):
        if ch in "{[":
            first_idx = i
            break
    if first_idx >= 0:
        for i in range(len(text) - 1, -1, -1):
            if text[i] in "}]":
                last_idx = i
                break

    if first_idx >= 0 and last_idx >= 0 and first_idx < last_idx:
        sub_text = text[first_idx:last_idx + 1]
        try:
            parsed = _loads_json5_if_available(sub_text)
            if isinstance(parsed, (dict, list)):
                return parsed
            parsed = json.loads(sub_text)
            if isinstance(parsed, (dict, list)):
                return parsed
        except Exception:
            pass

    return None


def _build_unique_entity_name(db: Session, project_id: int, base_name: str, *, field: str = "name") -> str:
    stable_base = str(base_name or "").strip() or "New Subject"
    candidate = stable_base
    idx = 2
    while True:
        query = db.query(Entity).filter(Entity.project_id == project_id, _active_entity_clause())
        if field == "name_en":
            existing = query.filter(Entity.name_en == candidate).first()
        else:
            existing = query.filter(Entity.name == candidate).first()
        if not existing:
            return candidate
        candidate = f"{stable_base}_{idx}"
        idx += 1


def _split_prompt_clauses(text: str) -> List[str]:
    stable = str(text or "").strip()
    if not stable:
        return []
    parts = re.split(r"[\n\r]+|(?<=[。！？.!?；;])", stable)
    return [p.strip() for p in parts if str(p or "").strip()]


def _extract_prompt_labels(text: str) -> List[str]:
    stable = str(text or "")
    labels: List[str] = []
    for match in re.finditer(r"([A-Za-z][A-Za-z0-9 _/\-]{1,50})\s*:|([\u4e00-\u9fff]{1,24})\s*[：:]", stable):
        token = (match.group(1) or match.group(2) or "").strip().lower()
        token = re.sub(r"\s+", " ", token)
        if token:
            labels.append(token)
    return labels


def _prompt_structure_profile(text: str) -> Dict[str, Any]:
    stable = str(text or "")
    clauses = _split_prompt_clauses(stable)
    labels = _extract_prompt_labels(stable)
    return {
        "clause_count": len(clauses),
        "labels": labels,
        "colon_count": stable.count(":") + stable.count("："),
        "semicolon_count": stable.count(";") + stable.count("；"),
        "brace_count": stable.count("{") + stable.count("}"),
        "bracket_count": stable.count("[") + stable.count("]"),
        "paren_count": stable.count("(") + stable.count(")"),
    }


def _validate_prompt_structure(source_prompt: str, candidate_prompt: str) -> Tuple[bool, str]:
    src = _prompt_structure_profile(source_prompt)
    cand = _prompt_structure_profile(candidate_prompt)

    if src["clause_count"] > 0 and cand["clause_count"] != src["clause_count"]:
        return False, f"clause_count mismatch: source={src['clause_count']} candidate={cand['clause_count']}"

    if src["labels"]:
        if cand["labels"] != src["labels"]:
            return False, "label sequence mismatch"

    for key in ("colon_count", "semicolon_count", "brace_count", "bracket_count", "paren_count"):
        if src[key] != cand[key]:
            return False, f"{key} mismatch: source={src[key]} candidate={cand[key]}"

    return True, "ok"


@router.post("/projects/{project_id}/entities/{entity_id}/clone_with_llm", response_model=EntityOut)
async def clone_entity_with_llm(
    project_id: int,
    entity_id: int,
    req: EntityCloneWithLLMRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _require_project_access(db, project_id, current_user)

    source = db.query(Entity).filter(
        Entity.id == entity_id,
        Entity.project_id == project_id,
    ).first()
    if not source:
        raise HTTPException(status_code=404, detail="Entity not found")

    _repair_entity_image_url_from_assets(db, current_user, project, source)

    instruction = str(req.modification_instruction or "").strip()
    if not instruction:
        raise HTTPException(status_code=400, detail="modification_instruction is required")

    cfg = agent_service.get_active_llm_config(current_user.id, category="LLM")
    if not cfg or not cfg.get("api_key"):
        raise HTTPException(status_code=400, detail="Active LLM Settings not found. Please configure and activate an LLM provider.")

    llm_config = {
        "api_key": cfg.get("api_key"),
        "base_url": cfg.get("base_url"),
        "model": cfg.get("model"),
    }

    source_payload = {
        "name": source.name,
        "name_en": source.name_en,
        "type": source.type,
        "description": source.description,
        "anchor_description": source.anchor_description,
        "generation_prompt_cn": source.generation_prompt_cn,
        "generation_prompt_en": source.generation_prompt_en,
        "appearance_cn": source.appearance_cn,
        "clothing": source.clothing,
        "action_characteristics": source.action_characteristics,
        "role": source.role,
        "archetype": source.archetype,
        "gender": source.gender,
        "atmosphere": source.atmosphere,
        "visual_params": source.visual_params,
        "narrative_description": source.narrative_description,
        "visual_dependencies": source.visual_dependencies,
        "dependency_strategy": source.dependency_strategy,
    }

    source_payload_json = json.dumps(source_payload, ensure_ascii=False)
    name_hint = str(req.new_name_hint or "").strip()

    try:
        base_subject_prompt = _resolve_prompt_text("subject_generation.txt")
    except Exception as e:
        logger.error("Failed to load subject_generation.txt for clone mode: %s", e)
        raise HTTPException(status_code=500, detail="Prompt file 'subject_generation.txt' could not be loaded.")

    system_prompt = (
        f"{str(base_subject_prompt or '').strip()}\n\n"
        "[Clone Subject Mode - Mandatory]\n"
        "Given a source subject object and a modification request, generate an updated subject draft. "
        "Return STRICT JSON only with one top-level object key: \"entity\".\n\n"
        "Hard constraints:\n"
        "1) Keep the same subject type as source.\n"
        "2) generation_prompt_en MUST preserve the original prompt's structure and clause order. "
        "Use the source prompt as structural template, and only change content needed by the modification request.\n"
        "3) generation_prompt_cn MUST also follow the same source structure and stay semantically aligned with generation_prompt_en.\n"
        "4) Do not output explanations, markdown, code fences, or reasoning.\n"
        "5) Only include these keys inside entity: "
        "name, name_en, description, anchor_description, generation_prompt_cn, generation_prompt_en, "
        "appearance_cn, clothing, action_characteristics, role, archetype, gender, atmosphere, visual_params, narrative_description, "
        "visual_dependencies, dependency_strategy."
    )

    user_prompt = (
        f"Source subject JSON:\n{source_payload_json}\n\n"
        f"User modification request:\n{instruction}\n\n"
        f"Preferred new name hint (optional): {name_hint or 'None'}\n\n"
        "Now output strict JSON: {\"entity\": {...}}."
    )

    _release_db_connection(db, "clone_entity_with_llm_llm_call")

    async def _request_generated_entity(extra_instruction: str = "") -> Dict[str, Any]:
        req_user_prompt = user_prompt
        if extra_instruction:
            req_user_prompt = f"{user_prompt}\n\nAdditional hard-fix instruction:\n{extra_instruction}\n"

        try:
            llm_response = await llm_service.chat_completion_with_fallback(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": req_user_prompt},
                ],
                llm_config,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"LLM clone failed: {str(e)}")

        raw_content = str((llm_response or {}).get("content", "") or "")
        cleaned = re.sub(r"<think>.*?</think>", "", raw_content, flags=re.DOTALL | re.IGNORECASE).strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned, flags=re.IGNORECASE).strip()

        data = _extract_first_json_payload(cleaned)
        if data is None:
            raise HTTPException(status_code=422, detail="LLM returned non-JSON content for entity clone")

        if isinstance(data, list):
            data = data[0] if data else {}
        if not isinstance(data, dict):
            raise HTTPException(status_code=422, detail="LLM clone payload must be a JSON object")

        generated_obj = data.get("entity") if isinstance(data.get("entity"), dict) else data
        if not isinstance(generated_obj, dict):
            raise HTTPException(status_code=422, detail="LLM clone payload missing entity object")
        return generated_obj

    generated = await _request_generated_entity()

    def _pick_text(*values, fallback=""):
        for value in values:
            text = str(value or "").strip()
            if text:
                return text
        return str(fallback or "")

    candidate_prompt_en = _pick_text(generated.get("generation_prompt_en"), source.generation_prompt_en)
    candidate_prompt_cn = _pick_text(generated.get("generation_prompt_cn"), source.generation_prompt_cn)

    en_ok, en_reason = _validate_prompt_structure(source.generation_prompt_en or "", candidate_prompt_en)
    cn_ok, cn_reason = _validate_prompt_structure(source.generation_prompt_cn or "", candidate_prompt_cn)

    if not (en_ok and cn_ok):
        repair_instruction = (
            "Your previous result failed structural validation. Regenerate entity now and strictly preserve source prompt structure. "
            f"EN check: {en_reason}. CN check: {cn_reason}. "
            "Use exact same structural layout, same label ordering, and same punctuation skeleton as source prompts; only replace content details."
        )
        generated = await _request_generated_entity(repair_instruction)
        candidate_prompt_en = _pick_text(generated.get("generation_prompt_en"), source.generation_prompt_en)
        candidate_prompt_cn = _pick_text(generated.get("generation_prompt_cn"), source.generation_prompt_cn)

        en_ok, en_reason = _validate_prompt_structure(source.generation_prompt_en or "", candidate_prompt_en)
        cn_ok, cn_reason = _validate_prompt_structure(source.generation_prompt_cn or "", candidate_prompt_cn)
        if not (en_ok and cn_ok):
            raise HTTPException(
                status_code=422,
                detail=(
                    "LLM clone failed structure-preservation validation: "
                    f"EN={en_reason}; CN={cn_reason}"
                ),
            )

    cloned_name_base = _pick_text(name_hint, generated.get("name"), f"{source.name}_copy")
    cloned_name = _build_unique_entity_name(db, project_id, cloned_name_base, field="name")

    generated_name_en = _pick_text(generated.get("name_en"), source.name_en, source.name)
    cloned_name_en = _build_unique_entity_name(db, project_id, generated_name_en, field="name_en")

    raw_custom_attrs = source.custom_attributes or {}
    if isinstance(raw_custom_attrs, str):
        try:
            raw_custom_attrs = json.loads(raw_custom_attrs)
        except Exception:
            raw_custom_attrs = {}
    if not isinstance(raw_custom_attrs, dict):
        raw_custom_attrs = {}

    custom_attrs = dict(raw_custom_attrs)
    custom_attrs["cloned_from_entity_id"] = source.id
    custom_attrs["cloned_with_llm"] = {
        "timestamp": now_bj_iso(),
        "instruction": instruction,
    }

    target_episode_id = req.episode_id if req.episode_id is not None else source.episode_id
    if target_episode_id is not None:
        episode = db.query(Episode).filter(Episode.id == int(target_episode_id)).first()
        if not episode or int(getattr(episode, "project_id", 0) or 0) != int(project_id):
            raise HTTPException(status_code=400, detail="episode_id does not belong to this project")
        target_episode_id = int(target_episode_id)

    db_entity = Entity(
        project_id=project_id,
        episode_id=target_episode_id,
        name=cloned_name,
        name_en=cloned_name_en,
        base_name_en=source.base_name_en, # inherited from source
        type=source.type,
        description=_pick_text(generated.get("description"), source.description),
        image_url=source.image_url,
        video_url=source.video_url,
        audio_url=source.audio_url,
        generation_prompt_en=candidate_prompt_en,
        generation_prompt_cn=candidate_prompt_cn,
        anchor_description=_pick_text(generated.get("anchor_description"), source.anchor_description),
        gender=_pick_text(generated.get("gender"), source.gender),
        role=_pick_text(generated.get("role"), source.role),
        archetype=_pick_text(generated.get("archetype"), source.archetype),
        appearance_cn=_pick_text(generated.get("appearance_cn"), source.appearance_cn),
        clothing=_pick_text(generated.get("clothing"), source.clothing),
        action_characteristics=_pick_text(generated.get("action_characteristics"), source.action_characteristics),
        atmosphere=_pick_text(generated.get("atmosphere"), source.atmosphere),
        visual_params=_pick_text(generated.get("visual_params"), source.visual_params),
        narrative_description=_pick_text(generated.get("narrative_description"), source.narrative_description),
        visual_dependencies=_coerce_visual_dependencies(generated.get("visual_dependencies")) or _coerce_visual_dependencies(source.visual_dependencies),
        dependency_strategy=generated.get("dependency_strategy") if isinstance(generated.get("dependency_strategy"), dict) else (source.dependency_strategy or {}),
        custom_attributes=custom_attrs,
    )

    db.add(db_entity)
    db.commit()
    db.refresh(db_entity)
    return db_entity

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
    
    # New Fields
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
    
    class Config:
        extra = "allow"

@router.put("/entities/{entity_id}", response_model=EntityOut)
def update_entity(
    entity_id: int,
    entity_in: EntityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    entity = db.query(Entity).filter(Entity.id == entity_id, _active_entity_clause()).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    
    # Verify ownership via project
    project = _require_project_access(db, entity.project_id, current_user)

    _repair_entity_image_url_from_assets(db, current_user, project, entity)

    update_data = entity_in.dict(exclude_unset=True)
    if "visual_dependencies" in update_data:
        update_data["visual_dependencies"] = _coerce_visual_dependencies(update_data.get("visual_dependencies"))
    if _is_ephemeral_provider_media_url(update_data.get("image_url")):
        resolved_image_url = _resolve_precise_asset_library_url(
            db,
            current_user,
            update_data.get("image_url"),
            project=project,
            entity_id=getattr(entity, "id", None),
            asset_type_aliases={"subject", "character", "char"},
            media_type="image",
        )
        if resolved_image_url:
            update_data["image_url"] = resolved_image_url
    entity_attrs = _asset_meta_to_dict(getattr(entity, "custom_attributes", None))
    proposed_image_url = update_data.get("image_url")
    if "image_url" in update_data and proposed_image_url is not None:
        proposed_raw = str(proposed_image_url or "").strip()
        # Library reuse: if this URL is already a registered asset (or another project entity
        # already points at it), allow the bind even when OSS assert would otherwise reject
        # relative /uploads or cross-entity ephemeral copies.
        reuse_asset = None
        proposed_normalized = _normalize_asset_url_for_dedup(proposed_raw) if proposed_raw else ""
        if proposed_raw:
            reuse_asset = _find_existing_asset_for_registration(
                db,
                current_user.id,
                url=proposed_raw,
                meta_info={"project_id": getattr(project, "id", None)},
            )
            if not reuse_asset and proposed_normalized:
                try:
                    reuse_asset = (
                        db.query(Asset)
                        .filter(
                            Asset.user_id == current_user.id,
                            Asset.url_normalized == proposed_normalized,
                            _active_asset_clause(),
                        )
                        .order_by(Asset.id.desc())
                        .first()
                    )
                except Exception:
                    reuse_asset = (
                        db.query(Asset)
                        .filter(Asset.user_id == current_user.id, Asset.url == proposed_raw)
                        .first()
                    )
        is_shared_project_url = False
        if proposed_raw and not reuse_asset:
            shared_q = db.query(Entity.id).filter(
                Entity.project_id == project.id,
                Entity.id != entity.id,
                _active_entity_clause(),
            )
            # Match either exact signed URL or same normalized base URL.
            shared_hit = shared_q.filter(Entity.image_url == proposed_raw).first()
            if not shared_hit and proposed_normalized:
                siblings = (
                    db.query(Entity)
                    .filter(
                        Entity.project_id == project.id,
                        Entity.id != entity.id,
                        Entity.image_url.isnot(None),
                        _active_entity_clause(),
                    )
                    .limit(500)
                    .all()
                )
                for sibling in siblings:
                    if _normalize_asset_url_for_dedup(getattr(sibling, "image_url", None)) == proposed_normalized:
                        shared_hit = sibling
                        break
            is_shared_project_url = shared_hit is not None
        if reuse_asset or is_shared_project_url:
            if _is_ephemeral_provider_media_url(proposed_raw):
                entity_attrs = {
                    **(entity_attrs if isinstance(entity_attrs, dict) else {}),
                    "ephemeral_binding": True,
                    "needs_persistence_retry": True,
                }
        else:
            try:
                _assert_allowed_persisted_media_url(
                    proposed_raw,
                    field_label="entity.image_url",
                    metadata=entity_attrs,
                    db=db,
                )
            except HTTPException as assert_exc:
                # Last-chance: persist the source into managed OSS, then bind the durable URL.
                detail = str(getattr(assert_exc, "detail", "") or "")
                if proposed_raw and (
                    "persist" in detail.lower()
                    or "temporary" in detail.lower()
                    or "oss" in detail.lower()
                ):
                    persist_result = _persist_entity_image(
                        db,
                        current_user,
                        project,
                        entity,
                        source_url_override=proposed_raw,
                    )
                    durable_url = str(
                        (persist_result or {}).get("persisted_url")
                        or getattr(entity, "image_url", None)
                        or ""
                    ).strip()
                    if not durable_url:
                        raise
                    update_data["image_url"] = durable_url
                    entity_attrs = _asset_meta_to_dict(getattr(entity, "custom_attributes", None))
                else:
                    raise

    # Separate standard columns from custom attributes
    standard_columns = {c.name for c in Entity.__table__.columns}
    
    custom_attrs = {}
    if isinstance(entity.custom_attributes, dict):
        custom_attrs = entity.custom_attributes.copy()
    elif isinstance(entity.custom_attributes, str):
        try:
            custom_attrs = json.loads(entity.custom_attributes)
            if not isinstance(custom_attrs, dict):
                custom_attrs = {}
        except Exception:
            pass
    if isinstance(entity_attrs, dict):
        for meta_key in ("ephemeral_binding", "needs_persistence_retry"):
            if meta_key in entity_attrs:
                custom_attrs[meta_key] = entity_attrs.get(meta_key)
    
    for field, value in update_data.items():
        if field == "image_url" and value != entity.image_url:
             entity.image_url = value
             image_diag = _diagnose_entity_image_url(value)
             logger.info(
                 "[EntityImageUpdateDiag] entity_id=%s project_id=%s user_id=%s image_url=%s rel_upload=%s abs_upload=%s local_exists=%s upload_suffix=%s local_path=%s",
                 getattr(entity, "id", None),
                 getattr(project, "id", None),
                 getattr(current_user, "id", None),
                 image_diag.get("raw"),
                 image_diag.get("is_relative_upload"),
                 image_diag.get("is_absolute_upload"),
                 image_diag.get("local_exists"),
                 image_diag.get("upload_suffix"),
                 image_diag.get("local_path"),
             )
             # Auto-register as Asset if valid URL.
             # Match by url_normalized (ignore signed query tokens); never let asset
             # registration UniqueViolation roll back the entity image bind itself.
             if value:
                 try:
                     with db.begin_nested():
                         existing_asset = _find_existing_asset_for_registration(
                             db,
                             current_user.id,
                             url=value,
                             meta_info={
                                 "project_id": project.id,
                                 "entity_id": entity.id,
                                 "entity_name": entity.name,
                                 "category": entity.type,
                             },
                         )
                         if existing_asset:
                             # Keep newest signed URL on the shared asset row.
                             if str(getattr(existing_asset, "url", "") or "").strip() != str(value).strip():
                                 existing_asset.url = value
                             existing_meta = _asset_meta_to_dict(getattr(existing_asset, "meta_info", None))
                             if entity.id:
                                 existing_meta["entity_id"] = entity.id
                             if entity.name:
                                 existing_meta["entity_name"] = entity.name
                             if entity.type:
                                 existing_meta["category"] = entity.type
                             existing_asset.meta_info = existing_meta
                             db.add(existing_asset)
                         else:
                             # Lightweight insert without _register_asset_helper (that helper
                             # calls db.commit() and can poison this request on conflict).
                             asset = Asset(
                                 user_id=current_user.id,
                                 type="image",
                                 url=value,
                                 url_normalized=_normalize_asset_url_for_dedup(value),
                                 filename=os.path.basename(urllib.parse.urlparse(str(value)).path) or None,
                                 project_id=int(project.id) if getattr(project, "id", None) is not None else None,
                                 episode_id=_asset_optional_int(getattr(entity, "episode_id", None)),
                                 meta_info={
                                     "project_id": project.id,
                                     "entity_id": entity.id,
                                     "entity_name": entity.name,
                                     "category": entity.type,
                                 },
                                 remark=f"Auto-registered from Entity: {entity.name}",
                             )
                             db.add(asset)
                             db.flush()
                 except Exception as reg_exc:
                     logger.warning(
                         "[EntityImageUpdate] asset auto-register skipped | entity_id=%s err=%s",
                         getattr(entity, "id", None),
                         reg_exc,
                     )
        
        elif field in standard_columns:
            setattr(entity, field, value)
        else:
            # Update custom attributes
            if value is None and field in custom_attrs:
                del custom_attrs[field]
            else:
                custom_attrs[field] = value

    entity.custom_attributes = custom_attrs
    
    db.add(entity)
        
    db.commit()
    db.refresh(entity)
    entity.image_url = _refresh_managed_media_url(getattr(entity, "image_url", None), db)
    return entity

class SoraCharacterGenRequest(BaseModel):
    main_image_url: Optional[str] = None
    function_name: Optional[str] = None
    system_api_id: Optional[int] = None
    ref_image_urls: List[str] = []
    ref_video_urls: List[str] = []
    user_prompt: Optional[str] = None

@router.post("/entities/{entity_id}/generate_sora_character")
async def generate_sora_character(
    entity_id: int,
    req: SoraCharacterGenRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    """
    Generate a Sora Character definition/asset based on uploaded images and references.
    """
    if async_mode == "1":
        tid = _submit_async(generate_sora_character, user_id=current_user.id,
                            kind="sora_character", entity_id=entity_id, req=req, async_mode="0")
        return JSONResponse({"task_id": tid, "async": True})
    # 1. Validation
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    
    project = _require_project_access(db, entity.project_id, current_user)

    _repair_entity_image_url_from_assets(db, current_user, project, entity)

    logger.info(f"[sora_char] Generating for entity {entity.name}. MainImg: {req.main_image_url}")

    # 2. Update Entity Data (Save inputs)
    if req.main_image_url:
        if _is_ephemeral_provider_media_url(req.main_image_url):
            resolved_main_image_url = _resolve_precise_asset_library_url(
                db,
                current_user,
                req.main_image_url,
                project=project,
                entity_id=getattr(entity, "id", None),
                asset_type_aliases={"subject", "character", "char"},
                media_type="image",
            )
            if resolved_main_image_url:
                req = req.copy(update={"main_image_url": resolved_main_image_url})
        entity_attrs = _asset_meta_to_dict(getattr(entity, "custom_attributes", None))
        _assert_allowed_persisted_media_url(
            req.main_image_url,
            field_label="entity.image_url",
            metadata=entity_attrs,
            db=db,
        )
        entity.image_url = req.main_image_url
    
    # Merge references into visual_dependencies or custom_attributes
    # Structure: { "sora_refs": { "images": [], "videos": [] } }
    custom_attrs = entity.custom_attributes
    if isinstance(custom_attrs, str):
        try: custom_attrs = json.loads(custom_attrs)
        except: custom_attrs = {}
    elif not isinstance(custom_attrs, dict):
        custom_attrs = {}
    
    custom_attrs['sora_refs'] = {
        "images": req.ref_image_urls,
        "videos": req.ref_video_urls
    }
    entity.custom_attributes = custom_attrs
    db.commit()

    # 3. Prepare Provider
    llm_config = agent_service.get_active_llm_config(current_user.id, category="Video")
    # If generic LLM is returned but we need Video/Sora specific, we might need a better selector.
    # But get_active_llm_config falls back to system defaults.
    
    if not llm_config:
         raise HTTPException(status_code=400, detail="No Video Generation provider configured.")

    # 4. Construct Request (Simulating Sora/Grsai Character Create API)
    # Since we don't have the SDK specs, we'll format a generic request that llm_service *might* handle
    # OR we assume llm_service can handle `generate_content` with images.
    
    # Prompt Construction
    prompt = f"Create a consistent character reference for '{entity.name}'."
    if entity.description:
        prompt += f"\nDescription: {entity.description}"
    if req.user_prompt:
        prompt += f"\nUser Instruction: {req.user_prompt}"
    
    prompt += "\n\nReferences provided via context."

    # Check Balance
    # Assuming cost is high for character training/creation
    reservation_tx = None
    provider = llm_config.get("provider")
    model = llm_config.get("model")
    if billing_service.is_token_pricing(db, "video_gen", provider, model):
        image_count = 0
        if req.main_image_url:
            image_count += 1
        if isinstance(req.ref_image_urls, list):
            image_count += len([u for u in req.ref_image_urls if u])

        video_count = 0
        if isinstance(req.ref_video_urls, list):
            video_count += len([u for u in req.ref_video_urls if u])

        est_messages = [
            {"role": "system", "content": "sora-create-character"},
            {"role": "user", "content": prompt},
        ]
        est = billing_service.estimate_reserve_tokens_from_messages(est_messages)

        estimated_image_tokens = 1000 * image_count
        estimated_video_tokens = 2000 * video_count
        est_input = int(est.get("input_tokens", 0) or 0) + int(estimated_image_tokens) + int(estimated_video_tokens)
        est_output = int(math.ceil(float(est_input) * billing_service.RESERVE_OUTPUT_RATIO)) if est_input > 0 else 0

        reserve_details = {
            "item": "sora_create_character",
            "estimation_method": "prompt_tokens_ratio",
            "estimated_output_ratio": billing_service.RESERVE_OUTPUT_RATIO,
            "estimated_image_tokens": estimated_image_tokens,
            "estimated_video_tokens": estimated_video_tokens,
            "input_tokens": est_input,
            "output_tokens": est_output,
            "total_tokens": int(est_input + est_output),
        }
        reservation_tx = billing_service.reserve_credits(
            db,
            current_user.id,
            "video_gen",
            provider,
            model,
            reserve_details,
        )
    else:
        billing_service.check_balance(db, current_user.id, "video_gen", provider, model)
    
    # Execute
    # We pass the images as "multimodal_context" or similar if the service supports it.
    # Our llm_service.generate_content takes `system_prompt` and `user_prompt`.
    # It doesn't explicitly take image URLs in the signature found in snippets, 
    # but `analyze_multimodal` does.
    # However, "Character Creation" is usually a generation task.
    # Let's try to pass it in the prompt or config.
    
    # Workaround: Pass URLs in the prompt text for the provider to parse if it supports it,
    # or rely on `llm_service` to have been updated to support `images` list.
    # Looking at `endpoints.py`, `llm_service.generate_content` signature is simple.
    # But `analyze_multimodal` returns usage.
    
    # If the user wants "sora-create-character", it might be a specific Function Call?
    # I will assume the `llm_service` can handle a special prompt or valid JSON config.
    
    # For now, we'll log and simulate the call successful return to save the state,
    # assuming the actual Sora integration is via the generic `generate_content` or a future update.
    # But wait, user asked to "Increase functionality". I should try to make it real if possible.
    
    # If using Grsai/Sora, maybe it's `llm_service.generate_video`?
    # Let's check `llm_service` again if `generate_video` exists.
    # I verified `llm_service.py` earlier, it imported `requests` etc.
    
    # Let's assume we call `generate_content` but with a special system prompt that triggers the provider's logic.
    
    try:
        _release_db_connection(db, "sora_create_character_llm_call")
        response = await llm_service.generate_content_with_fallback(
            user_prompt=prompt,
            system_prompt="sora-create-character", # Special flag for the service to recognize?
            config=llm_config,
            image_urls=[req.main_image_url] + req.ref_image_urls if req.main_image_url else req.ref_image_urls,
            video_urls=req.ref_video_urls
        )
        
        # 5. Handle Result
        content = response.get("content", "")
        usage = response.get("usage", {})
        
        # Billing finalize
        if reservation_tx:
            actual_details = {"item": "sora_create_character"}
            if usage:
                actual_details.update(usage)
            _apply_llm_routing_to_billing_details(actual_details, response)
            if "prompt_tokens" in actual_details and "input_tokens" not in actual_details:
                actual_details["input_tokens"] = actual_details.get("prompt_tokens", 0)
            if "completion_tokens" in actual_details and "output_tokens" not in actual_details:
                actual_details["output_tokens"] = actual_details.get("completion_tokens", 0)
            billing_service.settle_reservation(db, _reservation_tx_id(reservation_tx), actual_details)
        else:
            deduct_details = dict(usage or {})
            deduct_details["item"] = "sora_create_character"
            _apply_llm_routing_to_billing_details(deduct_details, response)
            billing_service.deduct_credits(db, current_user.id, "video_gen", provider, model, deduct_details)

        # Save result (maybe a character ID returned in content?)
        # If content is JSON
        try:
            res_json = json.loads(content)
            char_id = res_json.get("id") or res_json.get("character_id")
            if char_id:
                custom_attrs['sora_character_id'] = char_id
                entity.custom_attributes = custom_attrs
                db.commit()
        except:
            pass # Content might be just text description

        return {
            "status": "success",
            "result": content,
            "entity_id": entity.id,
            "sora_refs": custom_attrs['sora_refs']
        }

    except Exception as e:
        logger.error(f"Sora Gen Failed: {e}")
        try:
            if reservation_tx:
                billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), str(e))
        except:
            pass
        billing_service.log_failed_transaction(db, current_user.id, "video_gen", llm_config.get("provider"), llm_config.get("model"), str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/entities/{entity_id}")
def delete_entity(
    entity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    entity = db.query(Entity).filter(Entity.id == entity_id, _active_entity_clause()).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    _require_project_access(db, entity.project_id, current_user, owner_only=True)
    _assert_episode_scoped_delete(entity, label="Entity")

    if _is_soft_deleted(entity):
        return {"status": "success", "batch_id": None}

    batch_id = _start_deletion_batch(
        db,
        user_id=current_user.id,
        project_id=int(entity.project_id),
        episode_id=int(entity.episode_id),
        action_type="entity",
        label=str(entity.name or f"Entity {entity_id}"),
    )
    _soft_delete_entities(db, entity_id=entity_id, batch_id=batch_id)
    _finalize_deletion_batch(db, batch_id)
    db.commit()
    return {"status": "success", "batch_id": batch_id}


@router.delete("/projects/{project_id}/episodes/{episode_id}/entities")
def delete_episode_entities(
    project_id: int,
    episode_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_project_access(db, project_id, current_user, owner_only=True)
    episode = db.query(Episode).filter(
        Episode.id == episode_id,
        Episode.project_id == project_id,
        _active_episode_clause(),
    ).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    batch_id = _start_deletion_batch(
        db,
        user_id=current_user.id,
        project_id=int(project_id),
        episode_id=int(episode_id),
        action_type="episode_entities",
        label=f"{episode.title or f'Episode {episode_id}'} entities",
    )
    deleted_count = _soft_delete_entities(
        db,
        project_id=project_id,
        episode_id=episode_id,
        batch_id=batch_id,
    )
    _finalize_deletion_batch(db, batch_id)
    db.commit()
    return {
        "status": "success",
        "message": "Episode entities deleted",
        "deleted_count": deleted_count,
        "batch_id": batch_id,
    }


@router.delete("/projects/{project_id}/entities")
def delete_project_entities(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _require_project_access(db, project_id, current_user, owner_only=True)
    raise HTTPException(
        status_code=403,
        detail="Deleting all project entities is not allowed. Delete entities per episode instead.",
    )

# --- Users ---
from app.schemas.user_auth import (
    EMAIL_VERIFICATION_TRIAL_CREDITS,
    USER_ACTIVE_LEVEL_DEFAULT,
    USER_ACTIVE_LEVEL_MAX,
    USER_BATCH_PARALLEL_LIMIT_MAX,
    USER_MEDIA_GENERATION_PARALLEL_BONUS,
    USER_MEDIA_GENERATION_PARALLEL_LIMIT_MAX,
    USER_PARALLEL_LIMIT_BONUS,
    USER_PARALLEL_LIMIT_MAX,
    EmailVerificationConfirmRequest,
    EmailVerificationSendRequest,
    ForgotPasswordRequest,
    LoginRequest,
    ResetPasswordRequest,
    Token,
    UserCreate,
    UserOut,
    UserPageOut,
    UserPasswordUpdate,
    UserProfileUpdate,
    UserUpdate,
    is_user_enabled as _is_user_enabled,
    normalize_user_active_level as _normalize_user_active_level,
    resolve_user_active_level as _resolve_user_active_level,
    resolve_user_batch_parallel_limit as _resolve_user_batch_parallel_limit,
    resolve_user_media_generation_parallel_limit as _resolve_user_media_generation_parallel_limit,
)
from app.services.auth_security import (
    create_access_token,
    create_password_reset_token,
    verify_password_reset_token,
)

SCENE_MARKDOWN_ORCHESTRATION_MAX_ATTEMPTS = 3
SCENE_MARKDOWN_ORCHESTRATION_RETRY_BASE_DELAY_SEC = 2.0
SCENE_MARKDOWN_ORCHESTRATION_BATCH_RETRY_ROUNDS = 1


_USER_MEDIA_GENERATION_ACTIVE_STATUSES = frozenset(
    {"queued", "submit", "pending", "running", "waiting_callback", "callback_processing"}
)


def _count_user_active_media_jobs_in_memory(user_id: int) -> int:
    uid = int(user_id or 0)
    if uid <= 0:
        return 0
    active_ids: set[str] = set()
    with IMAGE_JOB_LOCK:
        for job_id, job in IMAGE_JOB_STORE.items():
            if int((job or {}).get("user_id") or 0) != uid:
                continue
            status = str((job or {}).get("status") or "").strip().lower()
            if status in _USER_MEDIA_GENERATION_ACTIVE_STATUSES:
                active_ids.add(str(job_id))
    with VIDEO_JOB_LOCK:
        for job_id, job in VIDEO_JOB_STORE.items():
            if int((job or {}).get("user_id") or 0) != uid:
                continue
            status = str((job or {}).get("status") or "").strip().lower()
            if status in _USER_MEDIA_GENERATION_ACTIVE_STATUSES:
                active_ids.add(str(job_id))
    return len(active_ids)


def _count_user_active_media_generation_jobs(user_id: int) -> int:
    """Active image+video jobs for one user (queue DB + local job stores)."""
    from app.services.generation_task_queue import count_active_generation_tasks_for_user

    db_count = count_active_generation_tasks_for_user(int(user_id), kinds=["image", "video"])
    mem_count = _count_user_active_media_jobs_in_memory(int(user_id))
    # max covers single-process lag before enqueue and multi-worker DB visibility
    return max(int(db_count or 0), int(mem_count or 0))


def _enforce_user_media_generation_parallel_limit(user: "User") -> int:
    """Reject new image/video submits when user is_active+2 parallel slots are full."""
    active_level = _resolve_user_active_level(getattr(user, "is_active", USER_ACTIVE_LEVEL_DEFAULT))
    limit = _resolve_user_media_generation_parallel_limit(getattr(user, "is_active", USER_ACTIVE_LEVEL_DEFAULT))
    active = _count_user_active_media_generation_jobs(int(getattr(user, "id", 0) or 0))
    if active >= limit:
        raise HTTPException(
            status_code=429,
            detail=(
                f"并行图片/视频生成已达上限（当前 {active}/{limit}）。"
                f"启用级别 is_active={active_level}（上限=is_active+2），请等待进行中的任务完成后再提交。"
            ),
        )
    return limit


def _release_media_generation_job_after_limit_race(
    *,
    kind: str,
    job_id: str,
    user: "User",
    limit: int,
) -> None:
    """If a race pushed the user over the parallel limit, cancel the just-queued job."""
    active = _count_user_active_media_generation_jobs(int(getattr(user, "id", 0) or 0))
    if active <= limit:
        return
    active_level = _resolve_user_active_level(getattr(user, "is_active", USER_ACTIVE_LEVEL_DEFAULT))
    reason = (
        f"并行图片/视频生成已达上限（当前 {active}/{limit}）。"
        f"启用级别 is_active={active_level}（上限=is_active+2），请等待进行中的任务完成后再提交。"
    )
    try:
        from app.services.generation_task_queue import cancel_generation_task

        cancel_generation_task(str(job_id), reason=reason)
    except Exception:
        logger.warning(
            "[MediaParallelLimit] cancel after race failed | kind=%s job_id=%s user_id=%s",
            kind,
            job_id,
            getattr(user, "id", None),
            exc_info=True,
        )
    safe_kind = str(kind or "").strip().lower()
    if safe_kind == "image":
        _set_image_job(job_id, status="failed", error=reason, finished_at=now_bj_iso())
        with IMAGE_JOB_LOCK:
            IMAGE_JOB_TASKS.pop(job_id, None)
            scope_key = str((IMAGE_JOB_STORE.get(job_id) or {}).get("task_scope") or "").strip()
            if scope_key and IMAGE_ACTIVE_SCOPE_STORE.get(scope_key) == job_id:
                IMAGE_ACTIVE_SCOPE_STORE.pop(scope_key, None)
    elif safe_kind == "video":
        _set_video_job(job_id, status="failed", error=reason, finished_at=now_bj_iso())
        with VIDEO_JOB_LOCK:
            VIDEO_JOB_TASKS.pop(job_id, None)
            scope_key = str((VIDEO_JOB_STORE.get(job_id) or {}).get("task_scope") or "").strip()
            if scope_key and VIDEO_ACTIVE_SCOPE_STORE.get(scope_key) == job_id:
                VIDEO_ACTIVE_SCOPE_STORE.pop(scope_key, None)
    raise HTTPException(status_code=429, detail=reason)



# Auth email helpers live in app.services.auth_email (shared with admin SMTP sends).
from app.services.auth_email import (
    _generate_email_verification_code,
    _is_valid_email_format,
    _resolve_runtime_smtp_config,
    _send_email_via_runtime_smtp,
    send_email_verification_code,
    send_password_reset_email,
    send_welcome_trial_credits_email,
)

# --- Login ---

# Login helpers live in app.services.auth_login.
from app.services.auth_login import (
    _describe_login_identifier,
    _get_request_client_ip,
    _get_users_is_active_schema_snapshot,
    _is_maintenance_active_for_login,
    _log_login_is_active_diagnostics,
    _log_login_stage,
    _refresh_user_identity_cache,
    _should_block_login_for_maintenance,
    authenticate_user,
)


def _mask_secret_for_log(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if len(raw) <= 8:
        return "*" * len(raw)
    return f"{raw[:4]}***{raw[-4:]}"


def _sanitize_generation_runtime_config_for_log(value: Any) -> Any:
    secret_keys = {
        "api_key",
        "apikey",
        "authorization",
        "x-api-key",
        "access_token",
        "refresh_token",
        "private_key",
    }
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            key_text = str(key or "").strip().lower()
            if key_text in secret_keys:
                sanitized[key] = _mask_secret_for_log(item)
            else:
                sanitized[key] = _sanitize_generation_runtime_config_for_log(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_generation_runtime_config_for_log(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_generation_runtime_config_for_log(item) for item in value)
    return value


from app.models.all_models import SystemLog



# Runtime/storage admin schemas moved to app.schemas.admin_ops
from app.schemas.admin_ops import (  # noqa: E402
    AdminExpiredDeleteRequest,
    AdminExpiredFilesOut,
    AdminExpiredRemindRequest,
    AdminStorageUsageOut,
    AdminStorageUsageUserOut,
    GenericMessageOut,
    RuntimeLogFileOut,
    RuntimeLogViewOut,
)


# admin runtime-logs/storage-usage moved to app.api.routers.admin_ops

# --- entity analyze/history ---
@router.post("/entities/{entity_id}/analyze")
async def analyze_entity_image(
    entity_id: int,
    background_tasks: BackgroundTasks,
    system_api_id: Optional[int] = Query(None),
    feature_name: Optional[str] = Query(None),
    bg: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Analyzes an entity (subject) image using Vision model and updates its attributes based on visual content.
    Returns the updated entity data.
    """
    if not bg:
        return await _execute_analyze_entity_image(entity_id, system_api_id, feature_name, db, current_user)
        
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
        
    # verify access
    project = _require_project_access(db, entity.project_id, current_user)

    if not entity.image_url:
        raise HTTPException(status_code=400, detail="Entity has no image to analyze.")

    async def bg_task(u_id: int):
        from app.db.session import SessionLocal
        with SessionLocal() as bg_db:
            try:
                u = bg_db.query(User).filter(User.id == u_id).first()
                if u:
                    await _execute_analyze_entity_image(entity_id, system_api_id, feature_name, bg_db, u)
            except Exception as e:
                logger.error(f"BG Analyze task failed for entity {entity_id}: {e}")

    background_tasks.add_task(bg_task, current_user.id)
    return entity


def _entity_analysis_parse_jsonish(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    text = str(value or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, (dict, list)) else {}
    except Exception:
        return {}


def _entity_analysis_category(entity_type: Any) -> str:
    raw = str(entity_type or "character").strip().lower()
    if "prop" in raw or "item" in raw or "物件" in raw or "道具" in raw:
        return "prop"
    if "poster" in raw or "cover" in raw or "海报" in raw or "封面" in raw:
        return "poster"
    if "env" in raw or "scene" in raw or "场景" in raw or "环境" in raw:
        return "environment"
    return "character"


def _entity_analysis_is_main_environment(entity: Any) -> bool:
    """Detect Stage-3 main/baseline environment (四向拼图 / 2x2), vs derivative ENV."""
    dep_raw = _entity_analysis_parse_jsonish(getattr(entity, "dependency_strategy", None))
    dep = dep_raw if isinstance(dep_raw, dict) else {}
    dep_type = str(dep.get("type") or "").strip()
    if dep_type == "BaselineDefinition":
        return True

    name = str(getattr(entity, "name", "") or "").strip()
    prompt_cn = str(getattr(entity, "generation_prompt_cn", "") or "")
    desc_cn = str(getattr(entity, "description", "") or getattr(entity, "description_cn", "") or "")
    joined = f"{prompt_cn}\n{desc_cn}"

    # Angle / state derivatives are never main baseline.
    if re.match(r"^\d+\s*度", name) or re.search(r"(^|[_\s])\d+\s*度", name):
        return False
    if any(marker in joined for marker in ("§A", "§B", "§C", "参考图为", "本镜头 Delta", "本镜 Delta")):
        return False
    if any(
        marker in joined
        for marker in (
            "四向拼图",
            "2×2",
            "2x2",
            "四宫格",
            "[0度格",
            "左上=0度",
            "左上＝0度",
            "BaselineDefinition",
        )
    ):
        return True

    deps_raw = _entity_analysis_parse_jsonish(getattr(entity, "visual_dependencies", None))
    deps = deps_raw if isinstance(deps_raw, list) else []
    has_env_dep = any(
        str(item or "").strip().upper().startswith("ENV:")
        or str(item or "").strip().startswith("ENV：[")
        or str(item or "").strip().startswith("ENV:[")
        for item in deps
    )
    if has_env_dep:
        return False
    # No ENV dependency and no derivative markers → treat as main/baseline.
    return dep_type in ("", "Original", "BaselineDefinition")


def _build_entity_analysis_format_contract(entity: Any, category: str) -> str:
    """Output format contract for vision reverse-prompting (env keeps Stage-3; char/prop = image-only)."""
    existing_cn = str(getattr(entity, "generation_prompt_cn", "") or "").strip()
    name_lock = (
        "- 保留 name / name_en 与 CURRENT 完全一致（逐字符，禁止改名）。\n"
        "- 完整生图提示词只写入 generation_prompt_cn（自然中文短段）。\n"
        "- generation_prompt_en 必须固定为空字符串 \"\"。\n"
        "- negative_prompt_en 用简短英文；anchor_description 用 3-5 个英文短语。\n"
    )

    # Character / prop: analyze the uploaded/bound image as-is; do not force Stage-3 sheet rebuild.
    if category == "character":
        return (
            "角色分析硬约束（只按原图分析）：\n"
            f"{name_lock}"
            "- 以提供的图片为唯一视觉权威：appearance_cn / clothing / generation_prompt_cn 必须忠实描述图中可见内容。\n"
            "- 不要为了凑「四宫格/四视图」而臆造图中不存在的视角、面板或构图；图是什么构图就按什么写。\n"
            "- CURRENT 文本仅用于保留身份名与少量非冲突背景；与图片冲突时一律以图片为准。\n"
            "- generation_prompt_cn 写成可直接生图的中文描述（相貌、衣着、材质、姿态、光线、背景以图为准）。"
        )
    if category == "prop":
        return (
            "道具分析硬约束（只按原图分析）：\n"
            f"{name_lock}"
            "- 以提供的图片为唯一视觉权威：description_cn / generation_prompt_cn 必须忠实描述图中可见物体。\n"
            "- 不要为了凑「四宫格/四视图」而臆造图中不存在的视角或面板；图是什么构图就按什么写。\n"
            "- 优先写结构、材质、工艺、磨损、比例与可见细节；无手/无人物除非图中确实出现。\n"
            "- CURRENT 文本仅用于保留名称；与图片冲突时一律以图片为准。"
        )

    preserve_note = (
        "若 CURRENT 已有 generation_prompt_cn：必须保留其原有章节/标签/排版骨架与字段写法，"
        "仅按图片可见证据改写具体视觉内容；禁止改成单视角描述或其它资产类型格式。\n"
        if existing_cn
        else "CURRENT 无既有 generation_prompt_cn 时，严格按下列 Stage 3 原格式新建。\n"
    )
    common = (
        "通用硬约束（资产设计 Stage 3 原格式）：\n"
        f"{name_lock}"
        "- Clean Plate：只写画面可见物理实体；环境禁具名角色/人称。\n"
        f"{preserve_note}"
    )

    if category == "poster":
        return (
            common
            + "海报/封面 generation_prompt_cn 格式（强制）：\n"
            "- 固定 4:3 poster canvas；premium theatrical one-sheet 单张主视觉（非四宫格分镜）。\n"
            "- 写清前中后景、标题安全区与移动端 UI 净空；光学与风格服从图片证据。"
        )

    # environment
    if _entity_analysis_is_main_environment(entity):
        return (
            common
            + "主环境 generation_prompt_cn 格式（强制，四向拼图 2×2 四宫格）：\n"
            "- 首句声明：生成四向拼图基准参考图；16:9 横幅；2×2 四宫格；禁止拉成 1:1；禁止俯拍/鸟瞰。\n"
            "- 格位固定：左上=0度、右上=90度、左下=180度、右下=270度；各格眼高约 50mm；四格共享材质/光源；Clean Plate。\n"
            "- 成稿逐格写 [0度格-左上]/[90度格-右上]/[180度格-左下]/[270度格-右下]，每格按「背景→中景→前景/邻向斜切→天花地面→光照」。\n"
            "- description_cn 写俯视 360 + 0 度轴与固定实体清单；dependency_strategy.type 必须为 BaselineDefinition；visual_dependencies=[]。\n"
            "- 若图片本身已是四宫格，按四格可见内容回写；若图片是单视角，仍须输出完整四向拼图格式（其余格据空间一致性合理补齐，并在 logic 标明推断格）。\n"
            "- 严禁改成单镜头可拍空镜、§A/§B/§C 衍生三段式、或角色/道具白底四视图。"
        )
    return (
        common
        + "衍生环境 generation_prompt_cn 格式（强制，§A/§B/§C 单镜）：\n"
        "- §A：参考主环境四向拼图指定格/半空间（或上一状态空镜）。\n"
        "- §B：与参考图一致的具象清单（地面/家具/门窗/色谱/锚点；前景/中景/背景 + 上中下）。\n"
        "- §C：本镜 Delta（机位、左右重组、背景半空间）；Clean Plate；禁人物。\n"
        "- description_cn 须含本衍生独立四向自然语言；保留既有 visual_dependencies / dependency_strategy 语义。"
    )


def _build_entity_analysis_schema_instruction(entity: Any, category: str) -> str:
    format_contract = _build_entity_analysis_format_contract(entity, category)
    name_lock = str(getattr(entity, "name", "") or "Current Name")
    name_en_lock = str(getattr(entity, "name_en", "") or "")

    if category == "character":
        return f"""
{format_contract}

Output MUST be a valid JSON object matching this structure EXACTLY:
{{
  "characters": [
    {{
      "name": "{name_lock}",
      "name_en": "{name_en_lock or "English Name"}",
      "gender": "M/F",
      "role": "Role",
      "archetype": "Archetype",
      "appearance_cn": "Detailed Chinese Description (Must include height & head-to-body ratio)",
      "clothing": "Detailed Description of clothing (Must include layers, materials, colors, wear)",
      "action_characteristics": "Inferred action traits",
      "generation_prompt_cn": "只按原图可见内容写的中文生图提示词（不强迫四宫格）",
      "generation_prompt_en": "",
      "negative_prompt_en": "short English negatives",
      "anchor_description": "3-5 English anchor phrases",
      "visual_dependencies": [],
      "dependency_strategy": {{
        "type": "Original",
        "logic": "Base Design"
      }}
    }}
  ]
}}
"""
    if category == "prop":
        return f"""
{format_contract}

Output MUST be a valid JSON object matching this structure EXACTLY:
{{
  "props": [
    {{
      "name": "{name_lock}",
      "name_en": "{name_en_lock or "English Name"}",
      "type": "held/static",
      "description_cn": "Chinese Description (Mobility & Mutable States)",
      "generation_prompt_cn": "只按原图可见内容写的中文生图提示词（不强迫四宫格）",
      "generation_prompt_en": "",
      "negative_prompt_en": "short English negatives",
      "anchor_description": "3-5 English anchor phrases",
      "visual_dependencies": [],
      "dependency_strategy": {{
        "type": "Original",
        "logic": "Base Design"
      }}
    }}
  ]
}}
"""
    if category == "poster":
        return f"""
{format_contract}

Output MUST be a valid JSON object matching this structure EXACTLY:
{{
  "posters": [
    {{
      "name": "{name_lock}",
      "name_en": "{name_en_lock or "English Name"}",
      "atmosphere": "Atmosphere",
      "visual_params": "Poster/Cover/4:3",
      "description_cn": "Chinese Description",
      "generation_prompt_cn": "按上方海报 4:3 原格式写满的中文生图提示词",
      "generation_prompt_en": "",
      "negative_prompt_en": "short English negatives",
      "anchor_description": "3-5 English anchor phrases",
      "visual_dependencies": [],
      "dependency_strategy": {{
        "type": "Type A",
        "logic": "Cover poster"
      }}
    }}
  ]
}}
"""

    is_main_env = _entity_analysis_is_main_environment(entity)
    dep_type = "BaselineDefinition" if is_main_env else "Type A"
    dep_logic = (
        "Main environment four-direction reference grid; sole reference for derivative ENV."
        if is_main_env
        else "Derivative environment single-shot prompt with A/B/C sections."
    )
    prompt_placeholder = (
        "按上方主环境四向拼图 2×2 四宫格原格式写满的中文生图提示词"
        if is_main_env
        else "按上方衍生环境 §A/§B/§C 原格式写满的中文生图提示词"
    )
    deps_rule = (
        "visual_dependencies must be []."
        if is_main_env
        else "visual_dependencies must preserve CURRENT.visual_dependencies (do not clear ENV references)."
    )
    return f"""
{format_contract}

{deps_rule}

Output MUST be a valid JSON object matching this structure EXACTLY:
{{
  "environments": [
    {{
      "name": "{name_lock}",
      "name_en": "{name_en_lock or "English Name"}",
      "atmosphere": "Atmosphere",
      "visual_params": "{"Baseline/Interior/Day" if is_main_env else "Wide/Interior/Day"}",
      "description_cn": "Chinese Description",
      "generation_prompt_cn": "{prompt_placeholder}",
      "generation_prompt_en": "",
      "negative_prompt_en": "short English negatives",
      "anchor_description": "3-5 English anchor phrases",
      "visual_dependencies": [],
      "dependency_strategy": {{
        "type": "{dep_type}",
        "logic": "{dep_logic}"
      }}
    }}
  ]
}}
"""


async def _execute_analyze_entity_image(
    entity_id: int,
    system_api_id: Optional[int] = Query(None),
    feature_name: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Analyzes an entity (subject) image using Vision model and updates its attributes based on visual content.
    Returns the updated entity data.
    """
    logger.info(f"analyze_entity_image called for ID {entity_id}")
    
    # 1. Fetch Entity
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
        
    project = _require_project_access(db, entity.project_id, current_user)

    if not entity.image_url:
        raise HTTPException(status_code=400, detail="Entity has no image to analyze.")

    logger.info(f"Entity found: {entity.name}, Image: {entity.image_url}")

    # 2. Resolve LLM from script_analysis function API dropdown (same list as script analysis).
    llm_config, selected_dropdown_id, _, _ = _resolve_script_analysis_dropdown_llm_config(
        db,
        current_user.id,
        "script_analysis",
        system_api_id,
        context="analyze_entity_image",
    )
    api_provider = str(llm_config.get("provider") or "").strip() or None
    api_model = str(llm_config.get("model") or "").strip() or None
    api_api_key = str(llm_config.get("api_key") or "").strip() or None
    api_base_url = str(llm_config.get("base_url") or "").strip() or None
    raw_api_config = llm_config.get("config")
    api_config = dict(raw_api_config) if isinstance(raw_api_config, dict) else {}
    if not api_provider or not api_model:
        raise HTTPException(status_code=400, detail="Script analysis API dropdown has no usable Vision/LLM model. Please configure it in Function APIs.")
    
    reservation_tx = None
    reservation_tx_id: Optional[int] = None
    # Billing Check (token rules will reserve later once we have messages)
    if not billing_service.is_token_pricing(db, "analysis_character", api_provider, api_model):
        cost = billing_service.estimate_cost(db, "analysis_character", api_provider, api_model)
        billing_service.check_can_proceed(current_user, cost)

    llm_config = {
        "provider": api_provider,
        "api_key": api_api_key,
        "base_url": api_base_url,
        "model": api_model,
        "config": {
            **api_config,
            "__selected_system_api_id": selected_dropdown_id,
        },
    }
    logger.info(f"Using Model: {api_model} (script_analysis dropdown id={selected_dropdown_id})")

    def _build_entity_analysis_error_detail(
        code: str,
        message: str,
        stage: str,
        *,
        preview: Optional[str] = None,
        repair_attempted: Optional[bool] = None,
        finish_reason: Optional[Any] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "code": code,
            "message": message,
            "stage": stage,
            "entity_id": entity_id,
            "provider": api_provider,
            "model": api_model,
        }
        if preview:
            payload["preview"] = str(preview or "")[:160]
        if repair_attempted is not None:
            payload["repair_attempted"] = bool(repair_attempted)
        if finish_reason not in (None, ""):
            payload["finish_reason"] = finish_reason
        return payload

    # 3. Construct System Prompt based on Entity Type (Stage-3 original prompt formats)
    entity_type = (entity.type or "character").lower()
    analysis_category = _entity_analysis_category(entity_type)
    is_main_env = analysis_category == "environment" and _entity_analysis_is_main_environment(entity)

    if analysis_category in {"character", "prop"}:
        base_instruction = (
            "You are an expert visual analyst. "
            "Analyze the provided subject image and UPDATE fields from what is visibly present in the image. "
            "For character/prop: image-only reverse prompting — do NOT force Stage-3 four-panel sheet reconstruction; "
            "describe the actual image composition and visible details. Keep name/name_en unchanged; generation_prompt_en=\"\"."
        )
    else:
        base_instruction = (
            "You are an expert visual analyst and Stage-3 asset design specialist. "
            "Analyze the provided subject image and UPDATE the existing subject fields to match visible evidence. "
            "Rewrite generation_prompt_cn in the ORIGINAL Stage-3 asset-design prompt format for this subject type "
            "(main environment 2x2 four-direction grid; derivative ENV A/B/C; poster 4:3). "
            "Do NOT invent a new free-form prompt style."
        )
    schema_instruction = _build_entity_analysis_schema_instruction(entity, analysis_category)

    system_prompt = (
        f"{base_instruction}\n\n{schema_instruction}\n\n"
        "Constraint: Return ONLY the raw JSON object. "
        "The first non-whitespace character of your output MUST be '{' and the last character MUST be '}'. "
        "Do not include markdown formatting (like ```json), no <think> tags, no reasoning process, and no conversational text."
    )
    logger.info(
        "Entity analysis format contract | entity_id=%s type=%s category=%s main_env=%s",
        entity_id,
        entity_type,
        analysis_category,
        is_main_env,
    )

    # 4. Construct Image URL & Current Info
    
    # Prepare Current Info Context
    # Include Project Context for style consistency
    project_context = {}
    if project.global_info:
         project_context = {
             "Global_Style": project.global_info.get("Global_Style"),
             "Tone": project.global_info.get("tone")
         }

    required_prompt_format = (
        "main_environment_2x2_quad"
        if is_main_env
        else {
            "environment": "derivative_environment_abc",
            "character": "image_only_from_source",
            "prop": "image_only_from_source",
            "poster": "poster_4x3",
        }.get(analysis_category, "stage3_original")
    )
    current_info = {
        "name": entity.name,
        "name_en": entity.name_en,
        "type": entity.type,
        "analysis_category": analysis_category,
        "is_main_environment": bool(is_main_env),
        "required_prompt_format": required_prompt_format,
        "description": entity.description,
        "appearance_cn": entity.appearance_cn,
        "clothing": entity.clothing,
        "role": entity.role,
        "atmosphere": getattr(entity, "atmosphere", None),
        "visual_params": getattr(entity, "visual_params", None),
        "generation_prompt_cn": entity.generation_prompt_cn,
        "generation_prompt_en": "",
        "visual_dependencies": getattr(entity, "visual_dependencies", None) or [],
        "dependency_strategy": getattr(entity, "dependency_strategy", None) or {},
        "project_context": project_context,
    }
    
    current_info_str = json.dumps(current_info, ensure_ascii=False)

    try:
        from urllib.parse import urlparse
        import base64
        
        base_url = os.getenv("RENDER_EXTERNAL_URL", "http://localhost:8000").rstrip("/")
        image_url_raw = _refresh_managed_media_url(entity.image_url, db)
        image_url_final = image_url_raw
        
        local_file_path = None
        path_part = None

        if image_url_raw:
            if image_url_raw.startswith("http"):
                parsed_url = urlparse(image_url_raw)
                if parsed_url.hostname in ["localhost", "127.0.0.1", "0.0.0.0"]:
                    path_part = parsed_url.path.lstrip("/")
            else:
                # Relative path (e.g. /uploads/...)
                path_part = image_url_raw.lstrip("/")
        
        if path_part:
            possible_paths = [
                os.path.join(settings.BASE_DIR, "app", path_part),
                os.path.join(settings.BASE_DIR, path_part),
                os.path.join(os.getcwd(), "app", path_part),
                os.path.join(os.getcwd(), path_part),
                # Try finding in uploads dir explicitly if path starts with uploads
                os.path.join(settings.UPLOAD_DIR, path_part.replace("uploads/", "", 1))
            ]
            
            for p in possible_paths:
                # Resolve possible double slashes
                p = os.path.normpath(p)
                if os.path.exists(p) and os.path.isfile(p):
                    local_file_path = p
                    break
        
        if local_file_path:
            try:
                def _read_and_encode_entity():
                    with open(local_file_path, "rb") as image_file:
                        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                    ext = os.path.splitext(local_file_path)[1].lower().replace(".", "")
                    mime = "image/png" if ext == "png" else "image/jpeg"
                    if ext == "jpg": mime = "image/jpeg"
                    if ext == "webp": mime = "image/webp"
                    return f"data:{mime};base64,{encoded_string}"
                image_url_final = await asyncio.to_thread(_read_and_encode_entity)
                logger.info(f"Converted local image {local_file_path} to Base64 (Size: {len(image_url_final)} chars)")
            except Exception as e:
                logger.error(f"Failed to encode local image {local_file_path}: {e}")
                
    except Exception as e:
        logger.warning(f"Error resolving entity image path: {e}")
        # Continue with original URL
        pass

    format_focus = {
        "character": "只按原图可见内容分析（不强迫四宫格）",
        "prop": "只按原图可见内容分析（不强迫四宫格）",
        "poster": "海报 4:3 单张主视觉",
        "environment": (
            "主环境四向拼图 2×2 四宫格（左上0/右上90/左下180/右下270）"
            if is_main_env
            else "衍生环境 §A/§B/§C 单镜格式"
        ),
    }.get(analysis_category, "Stage 3 原提示词格式")

    if analysis_category in {"character", "prop"}:
        user_analysis_text = (
            f"Here is the CURRENT information for subject '{entity.name}':\n{current_info_str}\n\n"
            "Please analyze the image.\n"
            "IMPORTANT:\n"
            f"1) {format_focus} — generation_prompt_cn / appearance / clothing / description must follow the image as authority.\n"
            "2) Do NOT invent missing four-panel views or Stage-3 sheet structure that is not in the image.\n"
            "3) CURRENT text is only for name lock and non-conflicting identity; image wins on conflicts.\n"
            "4) generation_prompt_en MUST be an empty string \"\".\n"
            "5) Keep name/name_en unchanged.\n"
            "Output contract: reply with JSON only, begin immediately with '{', and do not output any explanation or thinking text."
        )
    else:
        user_analysis_text = (
            f"Here is the CURRENT information for subject '{entity.name}':\n{current_info_str}\n\n"
            "Please analyze the image. Fuse the visual details from the image with the current information.\n"
            "IMPORTANT:\n"
            f"1) Rewrite generation_prompt_cn in the ORIGINAL Stage-3 format for this subject: {format_focus}.\n"
            "2) If CURRENT.generation_prompt_cn already exists, preserve its section/tag/layout skeleton and only refresh visual facts from the image.\n"
            "3) generation_prompt_en MUST be an empty string \"\".\n"
            "4) Keep name/name_en unchanged.\n"
            "Output contract: reply with JSON only, begin immediately with '{', and do not output any explanation or thinking text."
        )

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_analysis_text},
                {"type": "image_url", "image_url": {"url": image_url_final}},
            ],
        },
    ]
    
    try:
        logger.info("Sending request to LLM...")

        # Do NOT release DB connection here in background task, otherwise SQLAlchemy detaches models
        # _release_db_connection(db, "analyze_entity_image_llm_call")

        if billing_service.is_token_pricing(db, "analysis_character", api_provider, api_model):
            est = billing_service.estimate_reserve_tokens_from_messages(messages)
            estimated_image_tokens = 1000
            est_input = int(est.get("input_tokens", 0) or 0) + estimated_image_tokens
            est_output = int(math.ceil(float(est_input) * billing_service.RESERVE_OUTPUT_RATIO)) if est_input > 0 else 0
            reserve_details = {
                "item": "entity_image_analysis",
                "estimation_method": "prompt_tokens_ratio",
                "estimated_output_ratio": billing_service.RESERVE_OUTPUT_RATIO,
                "estimated_image_tokens": estimated_image_tokens,
                "input_tokens": est_input,
                "output_tokens": est_output,
                "total_tokens": int(est_input + est_output),
            }
            reservation_tx = billing_service.reserve_credits(
                db,
                current_user.id,
                "analysis_character",
                api_provider,
                api_model,
                reserve_details,
            )
            try:
                reservation_tx_id = int(getattr(reservation_tx, "id", 0) or 0) or None
            except Exception:
                reservation_tx_id = None

        llm_response = await llm_service.chat_completion_with_fallback(messages, llm_config)
        
        result_content = llm_response.get("content", "")
        usage = llm_response.get("usage", {})
        effective_llm_response: Dict[str, Any] = llm_response

        def _merge_usage_metrics(base_usage: Dict[str, Any], delta_usage: Dict[str, Any]) -> Dict[str, Any]:
            merged = dict(base_usage or {})
            if not isinstance(delta_usage, dict):
                return merged
            additive_keys = ("prompt_tokens", "completion_tokens", "total_tokens", "input_tokens", "output_tokens")
            for key in additive_keys:
                if key in delta_usage:
                    try:
                        merged[key] = int(merged.get(key, 0) or 0) + int(delta_usage.get(key, 0) or 0)
                    except Exception:
                        pass
            for key, value in delta_usage.items():
                if key not in merged:
                    merged[key] = value
            return merged
        
        logger.info(f"LLM Reply Length: {len(result_content)}. Usage: {usage}")
        
        # Remove <think> blocks and robustly extract the first valid JSON payload.
        content = re.sub(r"<think>.*?</think>", "", str(result_content or ""), flags=re.DOTALL | re.IGNORECASE).strip()

        if not content:
            raise HTTPException(
                status_code=502,
                detail=_build_entity_analysis_error_detail(
                    "entity_analysis_empty_content",
                    "LLM returned empty content for entity analysis",
                    "initial_response",
                    repair_attempted=False,
                    finish_reason=(llm_response or {}).get("finish_reason"),
                ),
            )

        # Strip fenced code blocks if present.
        content = re.sub(r"^```(?:json)?\s*", "", content, flags=re.IGNORECASE)
        content = re.sub(r"\s*```$", "", content, flags=re.IGNORECASE).strip()

        def _extract_first_json_payload(text: str):
            import json
            text = str(text or "")
            
            has_json5 = False
            json5_obj = _loads_json5_if_available(text)
            if isinstance(json5_obj, (dict, list)):
                return json5_obj
            if json5_obj is not None:
                has_json5 = True

            first_idx = -1
            last_idx = -1
            for i, ch in enumerate(text):
                if ch in "{[":
                    first_idx = i
                    break
            if first_idx >= 0:
                for i in range(len(text) - 1, -1, -1):
                    if text[i] in "}]":
                        last_idx = i
                        break

            if first_idx >= 0 and last_idx >= 0 and first_idx < last_idx:
                sub_text = text[first_idx:last_idx + 1]
                try:
                    if has_json5:
                        res = _loads_json5_if_available(sub_text)
                    else:
                        res = json.loads(sub_text)
                    if isinstance(res, (dict, list)):
                        return res
                except Exception:
                    pass

            decoder = json.JSONDecoder()
            for idx, ch in enumerate(text):
                if ch not in "{[":
                    continue
                try:
                    obj, _end = decoder.raw_decode(text[idx:])
                    if isinstance(obj, (dict, list)):
                        return obj
                except Exception:
                    continue
            return None

        data = _extract_first_json_payload(content)
        if data is None:
            preview = content[:300].replace("\n", " ")
            logger.warning(
                "Entity analysis JSON parse first-pass failed | entity_id=%s provider=%s model=%s finish_reason=%s content_preview=%s",
                entity_id,
                api_provider,
                api_model,
                (llm_response or {}).get("finish_reason"),
                preview,
            )

            # One-shot repair retry: ask the same model to convert output into strict JSON only.
            repair_system = (
                "You are a strict JSON formatter. "
                "Convert the user's text into a valid JSON object only. "
                "The first character must be '{' and the last character must be '}'. "
                "No markdown fences, no explanation, no extra text."
            )
            repair_user = (
                "Convert the following content to a valid JSON object that preserves the original fields as much as possible.\n\n"
                f"{content}"
            )

            try:
                repair_response = await llm_service.chat_completion_with_fallback(
                    [
                        {"role": "system", "content": repair_system},
                        {"role": "user", "content": repair_user},
                    ],
                    llm_config,
                )
                repair_text = re.sub(
                    r"<think>.*?</think>",
                    "",
                    str((repair_response or {}).get("content", "") or ""),
                    flags=re.DOTALL | re.IGNORECASE,
                ).strip()
                repair_text = re.sub(r"^```(?:json)?\s*", "", repair_text, flags=re.IGNORECASE)
                repair_text = re.sub(r"\s*```$", "", repair_text, flags=re.IGNORECASE).strip()

                repaired_data = _extract_first_json_payload(repair_text)
                if repaired_data is not None:
                    data = repaired_data
                    usage = _merge_usage_metrics(usage, (repair_response or {}).get("usage", {}) or {})
                    effective_llm_response = repair_response or effective_llm_response
                    logger.info("Entity analysis JSON parse recovered via repair retry.")
                else:
                    repair_preview = repair_text[:300].replace("\n", " ")
                    logger.error(
                        "Entity analysis JSON parse failed after repair retry | entity_id=%s provider=%s model=%s initial_finish_reason=%s repair_finish_reason=%s content_preview=%s repair_preview=%s",
                        entity_id,
                        api_provider,
                        api_model,
                        (llm_response or {}).get("finish_reason"),
                        (repair_response or {}).get("finish_reason"),
                        preview,
                        repair_preview,
                    )
                    raise HTTPException(
                        status_code=422,
                        detail=_build_entity_analysis_error_detail(
                            "entity_analysis_non_json",
                            "LLM returned non-JSON content for entity analysis",
                            "repair_parse",
                            preview=repair_preview,
                            repair_attempted=True,
                            finish_reason=(repair_response or {}).get("finish_reason") or (llm_response or {}).get("finish_reason"),
                        ),
                    )
            except HTTPException:
                raise
            except Exception as repair_err:
                logger.error(
                    "Entity analysis JSON repair retry failed | entity_id=%s provider=%s model=%s err=%s content_preview=%s",
                    entity_id,
                    api_provider,
                    api_model,
                    str(repair_err),
                    preview,
                )
                raise HTTPException(
                    status_code=422,
                    detail=_build_entity_analysis_error_detail(
                        "entity_analysis_json_repair_failed",
                        "Entity analysis JSON repair retry failed",
                        "repair_request",
                        preview=preview,
                        repair_attempted=True,
                    ),
                )

        if isinstance(data, list):
            data = data[0] if data else {}

        if not isinstance(data, dict):
            raise HTTPException(
                status_code=422,
                detail=_build_entity_analysis_error_detail(
                    "entity_analysis_invalid_json_root",
                    "Entity analysis JSON must be an object",
                    "parsed_payload",
                    repair_attempted=data is not None,
                ),
            )
                  
        # Extract the core object based on type
        updated_info = {}
        if "characters" in data and isinstance(data["characters"], list) and len(data["characters"]) > 0:
            updated_info = data["characters"][0]
        elif "props" in data and isinstance(data["props"], list) and len(data["props"]) > 0:
            updated_info = data["props"][0]
        elif "environments" in data and isinstance(data["environments"], list) and len(data["environments"]) > 0:
            updated_info = data["environments"][0]
        elif "posters" in data and isinstance(data["posters"], list) and len(data["posters"]) > 0:
            updated_info = data["posters"][0]
        else:
            updated_info = data # Fallback if direct object

        if isinstance(updated_info, dict):
            # Stage-3 contract: full prompt lives in CN; EN field stays empty.
            updated_info["generation_prompt_en"] = ""
            # Name lock: never let reverse-prompt rename the subject.
            locked_name = str(getattr(entity, "name", "") or "").strip()
            locked_name_en = str(getattr(entity, "name_en", "") or "").strip()
            if locked_name:
                updated_info["name"] = locked_name
            if locked_name_en:
                updated_info["name_en"] = locked_name_en
            
        logger.info(f"Parsed Updated Info for Entity {entity_id}: {json.dumps(updated_info, ensure_ascii=False)[:300]}...")

        if not updated_info:
             logger.warning("updated_info is empty! LLM response might not match expected JSON schema.")

        # The original ORM instance may be detached after _release_db_connection;
        # reload a session-bound instance before applying updates.
        entity = db.query(Entity).filter(Entity.id == entity_id).first()
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")

        # Update Entity Fields
        if "base_name_en" in updated_info: entity.base_name_en = updated_info["base_name_en"]
        if "description_cn" in updated_info: entity.description = updated_info["description_cn"] # Map description_cn to description
        if "appearance_cn" in updated_info: entity.appearance_cn = updated_info["appearance_cn"]
        if "clothing" in updated_info: entity.clothing = updated_info["clothing"]
        if "action_characteristics" in updated_info: entity.action_characteristics = updated_info["action_characteristics"]
        if "role" in updated_info: entity.role = updated_info["role"]
        if "archetype" in updated_info: entity.archetype = updated_info["archetype"]
        if "gender" in updated_info: entity.gender = updated_info["gender"]
        
        if "atmosphere" in updated_info: entity.atmosphere = updated_info["atmosphere"]
        if "visual_params" in updated_info: entity.visual_params = updated_info["visual_params"]
        
        if "generation_prompt_cn" in updated_info: entity.generation_prompt_cn = updated_info["generation_prompt_cn"]
        entity.generation_prompt_en = ""
        if "negative_prompt_en" in updated_info and hasattr(entity, "negative_prompt_en"):
            entity.negative_prompt_en = updated_info["negative_prompt_en"]
        if "anchor_description" in updated_info: entity.anchor_description = updated_info["anchor_description"]
        
        if "visual_dependencies" in updated_info and isinstance(updated_info["visual_dependencies"], list):
            incoming_deps = updated_info["visual_dependencies"]
            # Derivative ENV reverse-prompt must not wipe existing ENV reference chain.
            if (
                analysis_category == "environment"
                and not is_main_env
                and not incoming_deps
                and getattr(entity, "visual_dependencies", None)
            ):
                updated_info["visual_dependencies"] = entity.visual_dependencies
            else:
                entity.visual_dependencies = incoming_deps
                updated_info["visual_dependencies"] = incoming_deps
        if "dependency_strategy" in updated_info and isinstance(updated_info["dependency_strategy"], dict):
            incoming_dep = updated_info["dependency_strategy"]
            if is_main_env:
                incoming_dep = {
                    **incoming_dep,
                    "type": "BaselineDefinition",
                }
            entity.dependency_strategy = incoming_dep
        elif is_main_env:
            existing_dep = _entity_analysis_parse_jsonish(getattr(entity, "dependency_strategy", None))
            if not isinstance(existing_dep, dict):
                existing_dep = {}
            entity.dependency_strategy = {
                **existing_dep,
                "type": "BaselineDefinition",
                "logic": existing_dep.get("logic")
                or "Main environment four-direction reference grid; sole reference for derivative ENV.",
            }

        # Update Custom Attributes with Analysis Result (Save latest)
        custom_attrs = entity.custom_attributes or {}
        # Ensure dict if it came from DB as string (unlikely with SQLAlchemy JSON type but possible with SQLite text)
        if isinstance(custom_attrs, str):
            try: custom_attrs = json.loads(custom_attrs)
            except: custom_attrs = {}
            
        custom_attrs['analysis_result'] = {
            "timestamp": now_bj_iso(),
            "content": updated_info
        }
        # Re-assign to trigger SQLAlchemy detection of mutation if needed
        entity.custom_attributes = dict(custom_attrs)


        logger.info(
            "Entity Updated. New Prompt CN Length: %s",
            len(entity.generation_prompt_cn) if entity.generation_prompt_cn else 0,
        )

        # Billing finalize (after successful parse/update)
        billing_details = _build_standard_billing_details(
            item="entity_image_analysis",
            usage_payload=usage if isinstance(usage, dict) else None,
            extra_details={
                "entity_id": entity_id,
                "request_scope": "analyze_entity_image",
            },
            routing_payload=effective_llm_response,
        )

        if reservation_tx:
            # If usage seems to miss image tokens, add a conservative estimate to avoid under-charging.
            current_input = billing_details.get("prompt_tokens", billing_details.get("input_tokens", 0))
            if current_input < 200:
                estimated_image_tokens = 1000
                billing_details["input_tokens"] = current_input + estimated_image_tokens
                billing_details["prompt_tokens"] = billing_details["input_tokens"]
                if "total_tokens" in billing_details:
                    billing_details["total_tokens"] += estimated_image_tokens
                else:
                    billing_details["total_tokens"] = billing_details["input_tokens"] + billing_details.get("output_tokens", 0)
            _finalize_model_invocation_billing(
                db=db,
                current_user=current_user,
                task_type="analysis_character",
                provider=api_provider,
                model=api_model,
                reservation_tx=reservation_tx,
                reservation_tx_id=reservation_tx_id,
                item="entity_image_analysis",
                usage_payload=usage if isinstance(usage, dict) else None,
                extra_details=billing_details,
                routing_payload=effective_llm_response,
            )
        else:
            _finalize_model_invocation_billing(
                db=db,
                current_user=current_user,
                task_type="analysis_character",
                provider=api_provider,
                model=api_model,
                reservation_tx=None,
                reservation_tx_id=reservation_tx_id,
                item="entity_image_analysis",
                usage_payload=usage if isinstance(usage, dict) else None,
                extra_details=billing_details,
                routing_payload=effective_llm_response,
            )
        
        # We no longer save the prompt as a separate asset file to avoid clutter.
        # The prompt is already saved in the entity.generation_prompt_en field.

        db.commit()
        db.refresh(entity)
        return entity

    except HTTPException as e:
        logger.error(f"Entity Analysis failed with HTTPException: {str(e.detail)}", exc_info=True)
        _cancel_reservation_quietly(db, reservation_tx_id or reservation_tx, str(e.detail))
        try:
            custom_attrs = entity.custom_attributes or {}
            if isinstance(custom_attrs, str):
                custom_attrs = json.loads(custom_attrs)
            custom_attrs['analysis_result'] = {
                "status": "error",
                "message": str(e.detail)
            }
            entity.custom_attributes = dict(custom_attrs)
            entity.image_url = None
            db.commit()
        except Exception:
            db.rollback()
        raise
    except Exception as e:
        logger.error(f"Entity Analysis failed: {str(e)}", exc_info=True)
        _cancel_reservation_quietly(db, reservation_tx_id or reservation_tx, str(e))
        try:
            custom_attrs = entity.custom_attributes or {}
            if isinstance(custom_attrs, str):
                custom_attrs = json.loads(custom_attrs)
            custom_attrs['analysis_result'] = {
                "status": "error",
                "message": str(e)
            }
            entity.custom_attributes = dict(custom_attrs)
            entity.image_url = None
            db.commit()
        except Exception:
            db.rollback()
        raise HTTPException(status_code=502, detail=f"Analysis failed: {str(e)}")

@router.get("/entities/{entity_id}/latest_analysis")
def get_entity_latest_analysis(
    entity_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    Get the latest saved analysis result for an entity.
    """
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
        
    _require_project_access(db, entity.project_id, current_user)
         
    custom_attrs = entity.custom_attributes or {}
    # Handle DB Storage format (Text vs JSON)
    if isinstance(custom_attrs, str):
        try: custom_attrs = json.loads(custom_attrs)
        except: custom_attrs = {}
        
    result = custom_attrs.get('analysis_result')
    return result or {}

@router.put("/entities/{entity_id}/latest_analysis")
def update_entity_latest_analysis(
    entity_id: int,
    data: AnalysisContent,
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    Update (Save/Edit) the latest analysis result without applying it.
    """
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
        
    _require_project_access(db, entity.project_id, current_user)
         
    custom_attrs = entity.custom_attributes or {}
    if isinstance(custom_attrs, str):
        try: custom_attrs = json.loads(custom_attrs)
        except: custom_attrs = {}
    
    # Update analysis result with timestamp
    result = custom_attrs.get('analysis_result', {})
    if not isinstance(result, dict): result = {}
    
    result['content'] = data.content
    result['timestamp'] = now_bj_iso() # Update timestamp on edit
    
    custom_attrs['analysis_result'] = result
    entity.custom_attributes = custom_attrs  # Reassign for SQLAlchemy detection if Dict
    
    db.commit()
    return custom_attrs['analysis_result']

@router.post("/entities/{entity_id}/apply_analysis")
def apply_entity_analysis(
    entity_id: int,
    data: Optional[AnalysisContent] = None, # Optional payload to override stored
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    Apply the stored (or provided) analysis result to update Entity fields.
    """
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    
    _require_project_access(db, entity.project_id, current_user)
    
    updated_info = {}
    
    # 1. Determine Source
    if data and data.content:
        updated_info = data.content
        # Optionally save this new content as latest too? YES.
        custom_attrs = entity.custom_attributes or {}
        if isinstance(custom_attrs, str):
            try: custom_attrs = json.loads(custom_attrs)
            except: custom_attrs = {}
        
        custom_attrs['analysis_result'] = {
            "timestamp": now_bj_iso(),
            "content": updated_info
        }
        entity.custom_attributes = custom_attrs
    else:
        # Load from stored
        custom_attrs = entity.custom_attributes or {}
        if isinstance(custom_attrs, str):
            try: custom_attrs = json.loads(custom_attrs)
            except: custom_attrs = {}
        
        result = custom_attrs.get('analysis_result', {})
        if isinstance(result, dict):
            updated_info = result.get('content', {})
    
    if not updated_info:
        raise HTTPException(status_code=400, detail="No analysis content provided or found to apply.")

    # 2. Apply Updates (Same logic as analyze_entity_image)
    if "name_en" in updated_info: entity.name_en = updated_info["name_en"]
    if "base_name_en" in updated_info: entity.base_name_en = updated_info["base_name_en"]
    if "description_cn" in updated_info: entity.description = updated_info["description_cn"] 
    if "appearance_cn" in updated_info: entity.appearance_cn = updated_info["appearance_cn"]
    if "clothing" in updated_info: entity.clothing = updated_info["clothing"]
    if "action_characteristics" in updated_info: entity.action_characteristics = updated_info["action_characteristics"]
    if "role" in updated_info: entity.role = updated_info["role"]
    if "archetype" in updated_info: entity.archetype = updated_info["archetype"]
    if "gender" in updated_info: entity.gender = updated_info["gender"]
    
    if "atmosphere" in updated_info: entity.atmosphere = updated_info["atmosphere"]
    if "visual_params" in updated_info: entity.visual_params = updated_info["visual_params"]
    
    if "generation_prompt_cn" in updated_info: entity.generation_prompt_cn = updated_info["generation_prompt_cn"]
    if "generation_prompt_en" in updated_info: entity.generation_prompt_en = updated_info["generation_prompt_en"]
    if "anchor_description" in updated_info: entity.anchor_description = updated_info["anchor_description"]
    
    if "visual_dependencies" in updated_info and isinstance(updated_info["visual_dependencies"], list): 
            entity.visual_dependencies = updated_info["visual_dependencies"]
    if "dependency_strategy" in updated_info and isinstance(updated_info["dependency_strategy"], dict):
            entity.dependency_strategy = updated_info["dependency_strategy"]

    db.commit()
    db.refresh(entity)
    return entity

# --- entity history/sync/llm ---
@router.get("/entities/{entity_id}/history")
def get_entity_history(entity_id: int, db: Session = Depends(get_db)):
    from app.models.all_models import EntityHistory
    history = db.query(EntityHistory).filter(EntityHistory.entity_id == entity_id).order_by(EntityHistory.created_at.desc()).all()
    return history

@router.post("/entities/{entity_id}/save_history")
def save_entity_history(entity_id: int, db: Session = Depends(get_db)):
    from app.models.all_models import Entity, EntityHistory
    import datetime
    entity = db.query(Entity).filter(Entity.id == entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
        
    history = EntityHistory(
        entity_id=entity.id,
        name=entity.name,
        type=entity.type,
        description=entity.description,
        name_en=entity.name_en,
        base_name_en=entity.base_name_en,
        gender=entity.gender,
        role=entity.role,
        archetype=entity.archetype,
        appearance_cn=entity.appearance_cn,
        clothing=entity.clothing,
        action_characteristics=entity.action_characteristics,
        atmosphere=entity.atmosphere,
        visual_params=entity.visual_params,
        narrative_description=entity.narrative_description,
        created_at=datetime.utcnow()
    )
    db.add(history)
    db.commit()
    return {"status": "ok"}

@router.post("/entities/history/{history_id}/restore")
def restore_entity_history(history_id: int, db: Session = Depends(get_db)):
    from app.models.all_models import Entity, EntityHistory
    history = db.query(EntityHistory).filter(EntityHistory.id == history_id).first()
    if not history:
        raise HTTPException(status_code=404, detail="History not found")
        
    entity = db.query(Entity).filter(Entity.id == history.entity_id).first()
    if entity:
        entity.name = history.name
        entity.type = history.type
        entity.description = history.description
        entity.name_en = history.name_en
        entity.base_name_en = history.base_name_en
        entity.gender = history.gender
        entity.role = history.role
        entity.archetype = history.archetype
        entity.appearance_cn = history.appearance_cn
        entity.clothing = history.clothing
        entity.action_characteristics = history.action_characteristics
        entity.atmosphere = history.atmosphere
        entity.visual_params = history.visual_params
        entity.narrative_description = history.narrative_description
        db.commit()
        db.refresh(entity)
    return {"status": "ok"}

@router.post("/entities/sync")
def sync_entity(req: dict, db: Session = Depends(get_db)):
    from app.models.all_models import Entity
    source_id = req.get("source_entity_id")
    target_id = req.get("target_entity_id")
    source = db.query(Entity).filter(Entity.id == source_id).first()
    target = db.query(Entity).filter(Entity.id == target_id).first()
    if not source or not target:
        raise HTTPException(status_code=404, detail="Entity not found")
        
    target.name = source.name
    target.type = source.type
    target.description = source.description
    target.name_en = source.name_en
    target.base_name_en = source.base_name_en
    target.gender = source.gender
    target.role = source.role
    target.archetype = source.archetype
    target.appearance_cn = source.appearance_cn
    target.clothing = source.clothing
    target.action_characteristics = source.action_characteristics
    target.atmosphere = source.atmosphere
    target.visual_params = source.visual_params
    target.narrative_description = source.narrative_description
    db.commit()
    db.refresh(target)
    return {"status": "ok"}


def _extract_first_json_object(raw_text: str) -> Dict[str, Any]:
    text = str(raw_text or "").strip()
    if not text:
        return {}

    fenced = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1).strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    direct_obj = re.search(r"\{[\s\S]*\}", text)
    if direct_obj:
        try:
            parsed = json.loads(direct_obj.group(0))
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return {}


def _resolve_generated_entity_episode_id(
    db: Session,
    project_id: int,
    episode_id: Optional[int],
) -> Optional[int]:
    if episode_id is None:
        return None
    try:
        eid = int(episode_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid episode_id")
    if eid <= 0:
        return None
    episode = db.query(Episode).filter(Episode.id == eid).first()
    if not episode or int(getattr(episode, "project_id", 0) or 0) != int(project_id):
        raise HTTPException(status_code=400, detail="episode_id does not belong to this project")
    return eid


def _create_generated_entity_from_payload(
    db: Session,
    project_id: int,
    payload: Dict[str, Any],
    *,
    fallback_name: str,
    fallback_type: str = "character",
    preferred_name: Optional[str] = None,
    episode_id: Optional[int] = None,
    visual_dependencies: Optional[List[str]] = None,
    dependency_strategy: Optional[Dict[str, Any]] = None,
    custom_attributes: Optional[Dict[str, Any]] = None,
) -> Entity:
    preferred = str(preferred_name or "").strip()
    name = preferred or str(payload.get("name") or fallback_name or "Generated Entity").strip()
    ent_type = str(payload.get("type") or fallback_type or "character").strip().lower()
    if ent_type not in {"character", "environment", "prop", "poster"}:
        ent_type = "character"
    resolved_episode_id = _resolve_generated_entity_episode_id(db, project_id, episode_id)

    deps = visual_dependencies
    if deps is None:
        deps = payload.get("visual_dependencies")
    strategy = dependency_strategy
    if strategy is None and isinstance(payload.get("dependency_strategy"), dict):
        strategy = payload.get("dependency_strategy")

    new_entity = Entity(
        project_id=project_id,
        episode_id=resolved_episode_id,
        name=name,
        type=ent_type,
        name_en=str(payload.get("name_en") or "").strip() or None,
        base_name_en=str(payload.get("base_name_en") or payload.get("name_en") or "").strip() or None,
        description=str(payload.get("description") or payload.get("bio") or "").strip() or None,
        atmosphere=str(payload.get("atmosphere") or payload.get("personality") or "").strip() or None,
        appearance_cn=str(payload.get("appearance_cn") or payload.get("features") or "").strip() or None,
        clothing=str(payload.get("clothing") or "").strip() or None,
        action_characteristics=str(payload.get("action_characteristics") or "").strip() or None,
        gender=str(payload.get("gender") or "").strip() or None,
        role=str(payload.get("role") or "").strip() or None,
        archetype=str(payload.get("archetype") or "").strip() or None,
        visual_params=str(payload.get("visual_params") or "").strip() or None,
        narrative_description=str(payload.get("narrative_description") or payload.get("bio") or "").strip() or None,
        generation_prompt_cn=str(payload.get("generation_prompt_cn") or "").strip() or None,
        generation_prompt_en=str(payload.get("generation_prompt_en") or "").strip() or None,
        anchor_description=str(payload.get("anchor_description") or "").strip() or None,
        visual_dependencies=_coerce_visual_dependencies(deps),
        dependency_strategy=strategy if isinstance(strategy, dict) else {},
        custom_attributes=custom_attributes if isinstance(custom_attributes, dict) else {},
    )
    db.add(new_entity)
    db.commit()
    db.refresh(new_entity)
    return new_entity


@router.post("/projects/{project_id}/entities/llm-text", response_model=EntityOut)
async def api_generate_entity_from_text(
    project_id: int,
    text_desc: str = Form(...),
    entity_name: Optional[str] = Form(None),
    episode_id: Optional[int] = Form(None),
    model: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_project_access(db, project_id, current_user)

    llm_config = agent_service.get_active_llm_config(
        current_user.id,
        category="LLM",
        function_name="script_analysis",
    )
    if not llm_config:
        llm_config = agent_service.get_active_llm_config(current_user.id, category="LLM")
    if not llm_config or not llm_config.get("api_key"):
        raise HTTPException(status_code=400, detail="No active LLM config found")

    if model:
        llm_config = {**llm_config, "model": model}

    preferred_name = str(entity_name or "").strip()
    system_prompt = (
        "You are an entity designer. Return ONLY JSON with fields: "
        "name, name_en, type, description, appearance_cn, atmosphere, narrative_description."
    )
    user_prompt = (
        "根据用户输入生成一个可入库的新实体。\n"
        "要求 type 仅可为 character/environment/prop/poster 之一。\n"
        f"{('实体中文名必须使用：' + preferred_name + chr(10)) if preferred_name else ''}"
        "用户输入：\n"
        f"{text_desc}"
    )

    try:
        resp = await llm_service.generate_content_with_fallback(user_prompt, system_prompt, llm_config)
        payload = _extract_first_json_object(llm_service.sanitize_text_output(str(resp.get("content") or "")))
        return _create_generated_entity_from_payload(
            db,
            project_id,
            payload,
            fallback_name=preferred_name or "文本生成实体",
            preferred_name=preferred_name or None,
            episode_id=episode_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM text generation failed: {e}")


@router.post("/projects/{project_id}/entities/llm-image", response_model=EntityOut)
async def api_generate_entity_from_image(
    project_id: int,
    file: UploadFile = File(...),
    entity_name: Optional[str] = Form(None),
    episode_id: Optional[int] = Form(None),
    model: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_project_access(db, project_id, current_user)

    llm_config = agent_service.get_active_llm_config(
        current_user.id,
        category="LLM",
        function_name="script_analysis",
    )
    if not llm_config:
        llm_config = agent_service.get_active_llm_config(current_user.id, category="LLM")
    if not llm_config or not llm_config.get("api_key"):
        raise HTTPException(status_code=400, detail="No active LLM config found")

    if model:
        llm_config = {**llm_config, "model": model}

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Image file is empty")

    mime = str(file.content_type or "image/png").strip() or "image/png"
    img_b64 = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime};base64,{img_b64}"

    preferred_name = str(entity_name or "").strip()
    system_prompt = (
        "You are a vision entity designer. Return ONLY JSON with fields: "
        "name, name_en, type, description, appearance_cn, atmosphere, narrative_description."
    )
    user_prompt = (
        "请根据图片反推一个可入库的新实体。"
        + (f"\n实体中文名必须使用：{preferred_name}" if preferred_name else "")
    )

    try:
        resp = await llm_service.generate_content_with_fallback(
            user_prompt,
            system_prompt,
            llm_config,
            image_urls=[data_url],
        )
        payload = _extract_first_json_object(llm_service.sanitize_text_output(str(resp.get("content") or "")))
        return _create_generated_entity_from_payload(
            db,
            project_id,
            payload,
            fallback_name=preferred_name or "图片反推实体",
            preferred_name=preferred_name or None,
            episode_id=episode_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM image generation failed: {e}")


@router.post("/projects/{project_id}/entities/llm-derive", response_model=EntityOut)
async def api_generate_entity_from_derive(
    project_id: int,
    base_entity_id: int = Form(...),
    derive_desc: str = Form(""),
    entity_name: Optional[str] = Form(None),
    episode_id: Optional[int] = Form(None),
    model: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_project_access(db, project_id, current_user)

    base_entity = db.query(Entity).filter(Entity.id == base_entity_id, Entity.project_id == project_id).first()
    if not base_entity:
        raise HTTPException(status_code=404, detail="Base entity not found in this project")

    llm_config = agent_service.get_active_llm_config(
        current_user.id,
        category="LLM",
        function_name="script_analysis",
    )
    if not llm_config:
        llm_config = agent_service.get_active_llm_config(current_user.id, category="LLM")
    if not llm_config or not llm_config.get("api_key"):
        raise HTTPException(status_code=400, detail="No active LLM config found")

    if model:
        llm_config = {**llm_config, "model": model}

    preferred_name = str(entity_name or "").strip()
    derive_instruction = str(derive_desc or "").strip() or "在保持主体核心特征下，生成一个合理新变体"
    resolved_episode_id = episode_id if episode_id is not None else getattr(base_entity, "episode_id", None)
    base_type = str(base_entity.type or "character").strip().lower() or "character"
    base_dep_token = str(base_entity.name or base_entity.name_en or "").strip() or f"existing_id:{base_entity.id}"

    source_payload = {
        "name": base_entity.name,
        "name_en": base_entity.name_en,
        "type": base_type,
        "description": base_entity.description,
        "anchor_description": base_entity.anchor_description,
        "generation_prompt_cn": base_entity.generation_prompt_cn,
        "generation_prompt_en": base_entity.generation_prompt_en,
        "appearance_cn": base_entity.appearance_cn,
        "clothing": base_entity.clothing,
        "action_characteristics": base_entity.action_characteristics,
        "role": base_entity.role,
        "archetype": base_entity.archetype,
        "gender": base_entity.gender,
        "atmosphere": base_entity.atmosphere,
        "visual_params": base_entity.visual_params,
        "narrative_description": base_entity.narrative_description,
    }
    source_payload_json = json.dumps(source_payload, ensure_ascii=False)

    system_prompt = (
        "You are an entity variation designer. Return ONLY JSON with one top-level object.\n"
        "Task: derive a NEW entity from the reference entity by rewriting its prompts according to the "
        "additional modification description. Do NOT overwrite the reference entity.\n\n"
        "Hard constraints:\n"
        "1) Keep the same subject type as the reference.\n"
        "2) Treat generation_prompt_cn / generation_prompt_en of the reference as templates. "
        "Preserve their structure and clause order; only change content required by the modification description.\n"
        "3) generation_prompt_cn and generation_prompt_en must stay semantically aligned.\n"
        "4) Update appearance_cn / clothing / description / narrative_description to match the modification.\n"
        "5) Do not invent a new unrelated subject; this must clearly be a variant of the reference.\n"
        "6) Do not output explanations, markdown, or code fences.\n"
        "7) Required JSON keys: name, name_en, type, description, appearance_cn, clothing, "
        "generation_prompt_cn, generation_prompt_en, atmosphere, narrative_description, "
        "gender, role, archetype, action_characteristics, visual_params, anchor_description."
    )
    user_prompt = (
        f"Reference entity JSON:\n{source_payload_json}\n\n"
        f"Additional modification description:\n{derive_instruction}\n\n"
        f"Preferred new Chinese name (must use if provided): {preferred_name or 'None'}\n\n"
        "Rewrite the reference prompts into prompts for the NEW derived entity, applying only the requested changes."
    )

    def _pick_text(*values, fallback=""):
        for value in values:
            text = str(value or "").strip()
            if text:
                return text
        return str(fallback or "")

    try:
        resp = await llm_service.generate_content_with_fallback(user_prompt, system_prompt, llm_config)
        payload = _extract_first_json_object(llm_service.sanitize_text_output(str(resp.get("content") or "")))
        if not isinstance(payload, dict):
            payload = {}

        candidate_prompt_en = _pick_text(payload.get("generation_prompt_en"), base_entity.generation_prompt_en)
        candidate_prompt_cn = _pick_text(payload.get("generation_prompt_cn"), base_entity.generation_prompt_cn)

        source_en = str(base_entity.generation_prompt_en or "").strip()
        source_cn = str(base_entity.generation_prompt_cn or "").strip()
        if source_en or source_cn:
            en_ok, en_reason = _validate_prompt_structure(source_en, candidate_prompt_en) if source_en else (True, "ok")
            cn_ok, cn_reason = _validate_prompt_structure(source_cn, candidate_prompt_cn) if source_cn else (True, "ok")
            if not (en_ok and cn_ok):
                repair_prompt = (
                    f"{user_prompt}\n\n"
                    "Additional hard-fix instruction:\n"
                    "Your previous prompts failed structural validation against the reference prompts. "
                    "Regenerate now and strictly preserve source prompt structure/label order. "
                    f"EN check: {en_reason}. CN check: {cn_reason}. "
                    "Only replace content details required by the modification description."
                )
                repair_resp = await llm_service.generate_content_with_fallback(
                    repair_prompt,
                    system_prompt,
                    llm_config,
                )
                repaired = _extract_first_json_object(
                    llm_service.sanitize_text_output(str(repair_resp.get("content") or ""))
                )
                if isinstance(repaired, dict) and repaired:
                    payload = repaired
                    candidate_prompt_en = _pick_text(payload.get("generation_prompt_en"), candidate_prompt_en, source_en)
                    candidate_prompt_cn = _pick_text(payload.get("generation_prompt_cn"), candidate_prompt_cn, source_cn)

        payload["type"] = base_type
        payload["generation_prompt_en"] = candidate_prompt_en
        payload["generation_prompt_cn"] = candidate_prompt_cn
        payload["description"] = _pick_text(payload.get("description"), base_entity.description)
        payload["appearance_cn"] = _pick_text(payload.get("appearance_cn"), base_entity.appearance_cn)
        payload["clothing"] = _pick_text(payload.get("clothing"), base_entity.clothing)
        payload["atmosphere"] = _pick_text(payload.get("atmosphere"), base_entity.atmosphere)
        payload["narrative_description"] = _pick_text(
            payload.get("narrative_description"),
            base_entity.narrative_description,
            base_entity.description,
        )
        payload["gender"] = _pick_text(payload.get("gender"), base_entity.gender)
        payload["role"] = _pick_text(payload.get("role"), base_entity.role)
        payload["archetype"] = _pick_text(payload.get("archetype"), base_entity.archetype)
        payload["action_characteristics"] = _pick_text(
            payload.get("action_characteristics"),
            base_entity.action_characteristics,
        )
        payload["visual_params"] = _pick_text(payload.get("visual_params"), base_entity.visual_params)
        payload["anchor_description"] = _pick_text(
            payload.get("anchor_description"),
            base_entity.anchor_description,
        )
        if preferred_name:
            payload["name"] = preferred_name
        else:
            payload["name"] = _pick_text(payload.get("name"), f"{base_entity.name}-变体")
        payload["name_en"] = _pick_text(payload.get("name_en"), base_entity.name_en)
        payload["base_name_en"] = _pick_text(
            payload.get("base_name_en"),
            base_entity.base_name_en,
            base_entity.name_en,
        )

        # Always treat the reference entity as a visual dependency of the derived entity.
        derived_deps = _coerce_visual_dependencies(payload.get("visual_dependencies"))
        if base_dep_token and base_dep_token not in derived_deps:
            derived_deps = [base_dep_token, *derived_deps]
        new_name = str(payload.get("name") or "").strip()
        derived_deps = [dep for dep in derived_deps if str(dep or "").strip() and str(dep).strip() != new_name]

        dependency_strategy = {
            "type": "derived_from_reference",
            "logic": (
                f"Derived from reference entity `{base_dep_token}` (id={base_entity.id}). "
                f"Prompts are rewritten from the reference prompts according to: {derive_instruction}"
            ),
            "reference_entity_id": int(base_entity.id),
            "reference_entity_name": base_dep_token,
        }

        return _create_generated_entity_from_payload(
            db,
            project_id,
            payload,
            fallback_name=preferred_name or f"{base_entity.name}-变体",
            fallback_type=base_type,
            preferred_name=preferred_name or None,
            episode_id=resolved_episode_id,
            visual_dependencies=derived_deps,
            dependency_strategy=dependency_strategy,
            custom_attributes={
                "source": "subject_library_ai_derive",
                "derived_from_entity_id": int(base_entity.id),
                "derive_instruction": derive_instruction,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM derive generation failed: {e}")

from app.models.all_models import LLMCallLog


# Refresh cross-router helpers after local definitions are complete.
_bind_endpoint_helpers()

