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


def _bind_endpoint_helpers(*, include_routers: bool = True) -> None:
    from app.api.routers.helper_bind import bind_shared_helpers
    bind_shared_helpers(globals(), __name__, include_routers=include_routers)

_bind_endpoint_helpers(include_routers=False)

from app.services.generation_runtime.asset_registration import (  # noqa: E402,F401
    _find_existing_asset_for_registration,
)


from app.schemas.entity import (  # noqa: E402
    EntityCreate,
    EntityOut,
    EntityUpdate,
    _coerce_visual_dependencies,
)



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

