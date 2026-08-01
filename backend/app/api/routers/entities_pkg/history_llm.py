# -*- coding: utf-8 -*-
"""Section routes — symbols pulled from shared module."""
from __future__ import annotations

from app.api.routers.entities_pkg import shared as _shared

router = _shared.router
globals().update(
    {
        k: v
        for k, v in vars(_shared).items()
        if k
        not in {
            "__name__",
            "__file__",
            "__package__",
            "__loader__",
            "__spec__",
            "__doc__",
            "__builtins__",
        }
    }
)


from app.services.db_session_utils import _release_db_connection  # noqa: E402


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
        _release_db_connection(db, "entities_llm_text_call")
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
        _release_db_connection(db, "entities_llm_image_call")
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

    # Snapshot reference fields before releasing the request DB session for LLM.
    source_en = str(base_entity.generation_prompt_en or "").strip()
    source_cn = str(base_entity.generation_prompt_cn or "").strip()
    source_description = str(base_entity.description or "").strip()
    source_appearance_cn = str(base_entity.appearance_cn or "").strip()
    source_clothing = str(base_entity.clothing or "").strip()
    source_atmosphere = str(base_entity.atmosphere or "").strip()
    source_narrative = str(base_entity.narrative_description or "").strip()
    source_gender = str(base_entity.gender or "").strip()
    source_role = str(base_entity.role or "").strip()
    source_archetype = str(base_entity.archetype or "").strip()
    source_action = str(base_entity.action_characteristics or "").strip()
    source_visual_params = str(base_entity.visual_params or "").strip()
    source_anchor = str(base_entity.anchor_description or "").strip()
    source_name = str(base_entity.name or "").strip()
    source_name_en = str(base_entity.name_en or "").strip()
    source_base_name_en = str(base_entity.base_name_en or "").strip()
    source_entity_id = int(base_entity.id)

    try:
        _release_db_connection(db, "entities_llm_derive_call")
        resp = await llm_service.generate_content_with_fallback(user_prompt, system_prompt, llm_config)
        payload = _extract_first_json_object(llm_service.sanitize_text_output(str(resp.get("content") or "")))
        if not isinstance(payload, dict):
            payload = {}

        candidate_prompt_en = _pick_text(payload.get("generation_prompt_en"), source_en)
        candidate_prompt_cn = _pick_text(payload.get("generation_prompt_cn"), source_cn)

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
        payload["description"] = _pick_text(payload.get("description"), source_description)
        payload["appearance_cn"] = _pick_text(payload.get("appearance_cn"), source_appearance_cn)
        payload["clothing"] = _pick_text(payload.get("clothing"), source_clothing)
        payload["atmosphere"] = _pick_text(payload.get("atmosphere"), source_atmosphere)
        payload["narrative_description"] = _pick_text(
            payload.get("narrative_description"),
            source_narrative,
            source_description,
        )
        payload["gender"] = _pick_text(payload.get("gender"), source_gender)
        payload["role"] = _pick_text(payload.get("role"), source_role)
        payload["archetype"] = _pick_text(payload.get("archetype"), source_archetype)
        payload["action_characteristics"] = _pick_text(
            payload.get("action_characteristics"),
            source_action,
        )
        payload["visual_params"] = _pick_text(payload.get("visual_params"), source_visual_params)
        payload["anchor_description"] = _pick_text(
            payload.get("anchor_description"),
            source_anchor,
        )
        if preferred_name:
            payload["name"] = preferred_name
        else:
            payload["name"] = _pick_text(payload.get("name"), f"{source_name}-变体")
        payload["name_en"] = _pick_text(payload.get("name_en"), source_name_en)
        payload["base_name_en"] = _pick_text(
            payload.get("base_name_en"),
            source_base_name_en,
            source_name_en,
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
                f"Derived from reference entity `{base_dep_token}` (id={source_entity_id}). "
                f"Prompts are rewritten from the reference prompts according to: {derive_instruction}"
            ),
            "reference_entity_id": source_entity_id,
            "reference_entity_name": base_dep_token,
        }

        return _create_generated_entity_from_payload(
            db,
            project_id,
            payload,
            fallback_name=preferred_name or f"{source_name}-变体",
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


