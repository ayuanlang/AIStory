# -*- coding: utf-8 -*-
"""Workspace section routes — symbols pulled from shared module."""
from __future__ import annotations

from app.api.routers.workspace import shared as _shared

# Attach routes onto the same APIRouter instance and reuse helpers.
router = _shared.router
globals().update({k: v for k, v in vars(_shared).items() if k not in {"__name__", "__file__", "__package__", "__loader__", "__spec__", "__doc__", "__builtins__"}})


# --- Episodes (Script) ---

from app.schemas.episode import (  # noqa: E402,F401
    EpisodeCreate,
    EpisodeListOut,
    EpisodeOut,
    EpisodeUpdate,
    ScriptSegmentBase,
    ScriptSegmentOut,
)


@router.get("/projects/{project_id}/episodes", response_model=List[EpisodeListOut])
def read_episodes(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify access
    _require_project_access(db, project_id, current_user)
    
    from sqlalchemy.orm import selectinload, defer, noload
    episodes = (
        db.query(Episode)
        .options(
            defer(Episode.script_content),
            defer(Episode.ai_scene_analysis_result),
            defer(Episode.ai_scene_analysis_scene_markdown),
            defer(Episode.ai_scene_analysis_subject_index),
            defer(Episode.ai_scene_analysis_adaptation),
            defer(Episode.ai_entity_design_result),
            defer(Episode.ai_stage_outputs),
            defer(Episode.character_profiles),
            noload(Episode.script_segments)
        )
        .filter(
            Episode.project_id == project_id,
            _active_episode_clause(),
        )
        .all()
    )
    return _sort_project_episodes(episodes)

@router.get("/episodes/{episode_id}", response_model=EpisodeOut)
def read_episode(
    episode_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from sqlalchemy.orm import noload
    episode = db.query(Episode).options(noload(Episode.script_segments)).filter(
        Episode.id == episode_id,
        _active_episode_clause(),
    ).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)
    return episode

@router.put("/episodes/{episode_id}/segments", response_model=List[ScriptSegmentOut])
def update_episode_segments(
    episode_id: int,
    segments: List[ScriptSegmentBase],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    episode = db.query(Episode).filter(
        Episode.id == episode_id,
        _active_episode_clause(),
    ).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    
    _require_project_access(db, episode.project_id, current_user)

    # Clear existing
    db.query(ScriptSegment).filter(ScriptSegment.episode_id == episode_id).delete()
    
    # Add new
    new_segments = []
    for s in segments:
        seg = ScriptSegment(
            episode_id=episode_id,
            pid=s.pid,
            title=s.title,
            content_revised=s.content_revised,
            content_original=s.content_original,
            narrative_function=s.narrative_function,
            analysis=s.analysis
        )
        db.add(seg)
        new_segments.append(seg)
    
    db.commit()
    # Refresh logic is tricky for lists, but querying clearly works
    return db.query(ScriptSegment).filter(ScriptSegment.episode_id == episode_id).all()

@router.post("/projects/{project_id}/episodes", response_model=EpisodeOut)
def create_episode(
    project_id: int,
    episode: EpisodeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _require_project_access(db, project_id, current_user)

    existing_episodes = db.query(Episode).filter(
        Episode.project_id == project_id,
        _active_episode_clause(),
    ).all()
    existing_numbers = {
        int(num)
        for num in (_resolve_episode_sort_number(item) for item in existing_episodes)
        if num is not None
    }
    requested_number = _extract_episode_number_from_title(getattr(episode, "title", None))
    if requested_number is not None and requested_number in existing_numbers:
        raise HTTPException(status_code=409, detail=f"episode_number={requested_number} already exists")

    assigned_number = requested_number
    if assigned_number is None:
        assigned_number = max(existing_numbers) + 1 if existing_numbers else 1

    episode_info = {"episode_script_episode_number": int(assigned_number)}
        
    db_episode = Episode(
        project_id=project_id, 
        title=episode.title, 
        script_content=episode.script_content,
        episode_info=episode_info,
        ai_scene_analysis_result=episode.ai_scene_analysis_result,
        ai_scene_analysis_scene_markdown=episode.ai_scene_analysis_scene_markdown,
        character_profiles=episode.character_profiles or []
    )
    db.add(db_episode)
    try:
        _recompute_and_persist_project_cost_estimation(db, int(project_id))
    except Exception as cost_exc:
        logger.warning("create_episode cost recompute skipped | project_id=%s err=%s", project_id, cost_exc)
    db.commit()
    db.refresh(db_episode)
    return db_episode

@router.put("/episodes/{episode_id}", response_model=EpisodeOut)
def update_episode(
    episode_id: int,
    episode_in: EpisodeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    episode = db.query(Episode).filter(
        Episode.id == episode_id,
        _active_episode_clause(),
    ).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    
    # Check access via project
    _require_project_access(db, episode.project_id, current_user)

    if episode_in.title is not None:
        episode.title = episode_in.title
    if episode_in.script_content is not None:
        episode.script_content = episode_in.script_content
    # episode_info is deprecated and intentionally ignored.

    if episode_in.ai_scene_analysis_result is not None:
        episode.ai_scene_analysis_result = episode_in.ai_scene_analysis_result
    if hasattr(episode_in, 'ai_scene_analysis_scene_markdown') and episode_in.ai_scene_analysis_scene_markdown is not None:
        episode.ai_scene_analysis_scene_markdown = episode_in.ai_scene_analysis_scene_markdown
    # Apply stage_outputs BEFORE subject_index heal so intentional clears
    # (empty subject_index + empty stage_outputs in one PUT) do not resurrect
    # the pre-update stage_outputs Subject Index.
    if hasattr(episode_in, 'ai_stage_outputs') and episode_in.ai_stage_outputs is not None:
        episode.ai_stage_outputs = episode_in.ai_stage_outputs
    if hasattr(episode_in, 'ai_scene_analysis_subject_index') and episode_in.ai_scene_analysis_subject_index is not None:
        sanitized_subject_index = sanitize_subject_index_text(episode_in.ai_scene_analysis_subject_index)
        if _subject_index_has_usable_content(sanitized_subject_index):
            episode.ai_scene_analysis_subject_index = sanitized_subject_index
        else:
            # Prefer Stage 2 panel Subject Index over empty/contaminated writes.
            # episode.ai_stage_outputs already reflects this request when provided.
            stage_candidate = _extract_subject_index_from_stage_outputs(episode.ai_stage_outputs)
            if _subject_index_has_usable_content(stage_candidate):
                episode.ai_scene_analysis_subject_index = stage_candidate
                logger.info(
                    "[update_episode] recovered subject index from stage_outputs episode_id=%s chars=%s",
                    episode_id,
                    len(stage_candidate),
                )
            else:
                episode.ai_scene_analysis_subject_index = sanitized_subject_index
    if hasattr(episode_in, 'ai_scene_analysis_adaptation') and episode_in.ai_scene_analysis_adaptation is not None:
        episode.ai_scene_analysis_adaptation = episode_in.ai_scene_analysis_adaptation
    if hasattr(episode_in, 'ai_entity_design_result') and episode_in.ai_entity_design_result is not None:
        episode.ai_entity_design_result = episode_in.ai_entity_design_result
    if episode_in.character_profiles is not None:
        episode.character_profiles = episode_in.character_profiles
    try:
        _recompute_and_persist_project_cost_estimation(db, int(episode.project_id))
    except Exception as cost_exc:
        logger.warning("update_episode cost recompute skipped | project_id=%s err=%s", episode.project_id, cost_exc)
    
    db.commit()
    db.refresh(episode)
    return episode


from app.schemas.episode_requests import (  # noqa: E402,F401
    CharacterProfileGenerateRequest,
    CharacterProfilesUpdateRequest,
    CharacterCanonInputRequest,
    CharacterCanonCategoriesRequest,
    EPISODE_SCENE_GEN_STATUS_KEY,
    StoryGeneratorRequest,
    ScriptScenesGenerateRequest,
)

@router.get("/projects/{project_id}/character_profiles", response_model=List[Dict[str, Any]])
def get_project_character_profiles(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _require_project_access(db, project_id, current_user)
    gi = project.global_info or {}
    if not isinstance(gi, dict):
        return []
    profiles = gi.get("character_profiles")
    return profiles if isinstance(profiles, list) else []


@router.put("/projects/{project_id}/character_profiles", response_model=List[Dict[str, Any]])
def update_project_character_profiles(
    project_id: int,
    req: CharacterProfilesUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _require_project_access(db, project_id, current_user)

    def _render_canon_md(items: List[Dict[str, Any]]) -> str:
        blocks: List[str] = []
        for it in items or []:
            if not isinstance(it, dict):
                continue
            nm = (it.get("name") or "").strip()
            if not nm:
                continue
            md = (it.get("description_md") or "").strip()
            if md:
                blocks.append(md)
            else:
                blocks.append(f"### {nm} (Canonical)\n- Identity: {it.get('identity') or ''}\n")
        return "\n\n".join(blocks).strip()

    gi = dict(project.global_info or {})
    profiles = req.character_profiles or []
    gi["character_profiles"] = profiles
    gi["character_profiles_updated_at"] = now_bj_iso()
    gi["character_canon_md"] = _render_canon_md(profiles)
    project.global_info = gi

    db.add(project)
    db.commit()
    db.refresh(project)

    profiles = gi.get("character_profiles")
    return profiles if isinstance(profiles, list) else []


@router.put("/projects/{project_id}/character_canon/input", response_model=ProjectOut)
def save_project_character_canon_input(
    project_id: int,
    req: CharacterCanonInputRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Persist Project Character Canon draft inputs without calling the LLM."""
    project = _require_project_access(db, project_id, current_user)

    now_iso = now_bj_iso()
    gi = dict(project.global_info or {})
    gi["character_canon_input"] = {
        "name": req.name or "",
        "selected_tag_ids": req.selected_tag_ids or [],
        "selected_identity_ids": req.selected_identity_ids or [],
        "custom_identity": req.custom_identity or "",
        "body_features": req.body_features or "",
        "custom_style_tags": req.custom_style_tags or "",
        "extra_notes": req.extra_notes or "",
    }
    gi["character_canon_input_updated_at"] = now_iso
    project.global_info = gi

    db.add(project)
    db.commit()
    db.refresh(project)

    # Populate response aliases
    try:
        project.cover_image = get_project_cover_image(db, project.id)
    except Exception:
        project.cover_image = None
    try:
        project.aspectRatio = project.global_info.get('aspectRatio') if project.global_info else None
    except Exception:
        project.aspectRatio = None
    return project


@router.put("/projects/{project_id}/character_canon/categories", response_model=ProjectOut)
def save_project_character_canon_categories(
    project_id: int,
    req: CharacterCanonCategoriesRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Persist Project Character Canon tag/identity category configuration."""
    project = _require_project_access(db, project_id, current_user)

    now_iso = now_bj_iso()
    gi = dict(project.global_info or {})
    if req.tag_categories is not None:
        gi["character_canon_tag_categories"] = req.tag_categories
    if req.identity_categories is not None:
        gi["character_canon_identity_categories"] = req.identity_categories
    gi["character_canon_categories_updated_at"] = now_iso
    project.global_info = gi

    db.add(project)
    db.commit()
    db.refresh(project)

    # Populate response aliases
    try:
        project.cover_image = get_project_cover_image(db, project.id)
    except Exception:
        project.cover_image = None
    try:
        project.aspectRatio = project.global_info.get('aspectRatio') if project.global_info else None
    except Exception:
        project.aspectRatio = None
    return project


@router.post("/projects/{project_id}/character_profiles/generate", response_model=ProjectOut)
async def generate_project_character_profile(
    project_id: int,
    req: CharacterProfileGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    if async_mode == "1":
        tid = _submit_async(generate_project_character_profile, user_id=current_user.id,
                            kind="char_profile_project", project_id=project_id, req=req, async_mode="0")
        return JSONResponse({"task_id": tid, "async": True})
    project = _require_project_access(db, project_id, current_user)

    name = (req.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Character name is required")

    tags = [t.strip() for t in (req.style_tags or []) if isinstance(t, str) and t.strip()]
    tags_str = ", ".join(tags)

    sys_prompt = (
        "You are a professional character bible writer for film storyboarding. "
        "Write a CANONICAL character profile that will be treated as the single source of truth for this project. "
        "Return ONLY Markdown (no JSON, no code fences). "
        "Keep it concise but specific. Avoid NSFW/explicit sexual content; if the user requests 'sexy', express it in non-explicit, cinematic terms. "
        "Do not invent backstory not implied by inputs; focus on identity, silhouette/body proportions, face/hair, clothing, signature mannerisms, and on-screen presence."
    )

    user_prompt = (
        f"Character Name: {name}\n"
        f"Identity/Role: {req.identity or ''}\n"
        f"Body Features: {req.body_features or ''}\n"
        f"Style Tags: {tags_str}\n"
        f"Extra Notes: {req.extra_notes or ''}\n\n"
        "Output format (Markdown):\n"
        f"### {name} (Canonical)\n"
        "- Identity: ...\n"
        "- Body & silhouette: ...\n"
        "- Face & hair: ...\n"
        "- Outfit & materials: ...\n"
        "- Screen presence (cinematic, non-explicit): ...\n"
        "- Do/Don't (hard constraints): ...\n"
    )

    function_name = (getattr(req, "function_name", None) if req else None) or "script_analysis"
    system_api_id = getattr(req, "system_api_id", None) if req else None
    llm_config = _resolve_story_generator_script_analysis_llm_config(
        db,
        int(current_user.id),
        function_name=function_name,
        system_api_id=system_api_id,
        context="generate_project_character_profile",
        project_global_info=project.global_info,
    )
    provider = llm_config.get("provider") if llm_config else None
    model = llm_config.get("model") if llm_config else None
    reservation_tx = None
    if billing_service.is_token_pricing(db, "llm_chat", provider, model):
        est = billing_service.estimate_reserve_tokens_from_messages(
            [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        reservation_tx = billing_service.reserve_credits(
            db,
            current_user.id,
            "llm_chat",
            provider,
            model,
            {
                "item": "character_profile_project_generate",
                "estimation_method": "prompt_tokens_ratio",
                "estimated_output_ratio": billing_service.RESERVE_OUTPUT_RATIO,
                "input_tokens": est.get("input_tokens", 0),
                "output_tokens": est.get("output_tokens", 0),
                "total_tokens": est.get("total_tokens", 0),
            },
        )
    else:
        billing_service.check_balance(db, current_user.id, "llm_chat", provider, model)

    try:
        _release_db_connection(db, "character_profile_project_llm_call")
        resp = await llm_service.generate_content_with_fallback(user_prompt, sys_prompt, llm_config)
    except Exception as e:
        if reservation_tx:
            billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), str(e))
        raise

    description_md = (resp.get("content") or "").strip()
    if not description_md:
        if reservation_tx:
            billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), "LLM returned empty content")
        raise HTTPException(status_code=500, detail="LLM returned empty content")

    usage = resp.get("usage") or {}
    if not usage:
        usage = billing_service.estimate_input_output_tokens_from_messages(
            [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": description_md},
            ],
            output_ratio=1.0,
        )
    details = {
        "item": "character_profile_project_generate",
        "prompt_tokens": int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0),
        "completion_tokens": int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0),
        "total_tokens": int(
            usage.get(
                "total_tokens",
                int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0)
                + int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0),
            )
            or 0
        ),
    }
    details["input_tokens"] = details["prompt_tokens"]
    details["output_tokens"] = details["completion_tokens"]
    _apply_llm_routing_to_billing_details(details, resp)
    if reservation_tx:
        billing_service.settle_reservation(db, _reservation_tx_id(reservation_tx), details)
    else:
        billing_service.deduct_credits(db, current_user.id, "llm_chat", provider, model, details)

    now_iso = now_bj_iso()
    gi = dict(project.global_info or {})
    profiles = gi.get("character_profiles")
    profiles = list(profiles) if isinstance(profiles, list) else []

    updated = False
    for p in profiles:
        if isinstance(p, dict) and (p.get("name") == name):
            p.update({
                "name": name,
                "identity": req.identity,
                "body_features": req.body_features,
                "style_tags": tags,
                "extra_notes": req.extra_notes,
                "description_md": description_md,
                "updated_at": now_iso,
            })
            updated = True
            break
    if not updated:
        profiles.append({
            "name": name,
            "identity": req.identity,
            "body_features": req.body_features,
            "style_tags": tags,
            "extra_notes": req.extra_notes,
            "description_md": description_md,
            "updated_at": now_iso,
        })

    def _render_canon_md(items: List[Dict[str, Any]]) -> str:
        blocks = []
        for it in items:
            if not isinstance(it, dict):
                continue
            nm = (it.get("name") or "").strip()
            if not nm:
                continue
            md = (it.get("description_md") or "").strip()
            if md:
                blocks.append(md)
            else:
                blocks.append(f"### {nm} (Canonical)\n- Identity: {it.get('identity') or ''}\n")
        return "\n\n".join(blocks).strip()

    gi["character_profiles"] = profiles
    gi["character_profiles_updated_at"] = now_iso
    gi["character_canon_md"] = _render_canon_md(profiles)
    project.global_info = gi

    db.add(project)
    db.commit()
    db.refresh(project)

    # Populate response aliases
    try:
        project.cover_image = get_project_cover_image(db, project.id)
    except Exception:
        project.cover_image = None
    try:
        project.aspectRatio = project.global_info.get('aspectRatio') if project.global_info else None
    except Exception:
        project.aspectRatio = None
    return project




@router.get("/episodes/{episode_id}/character_profiles", response_model=List[Dict[str, Any]])
def get_episode_character_profiles(
    episode_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)
    return episode.character_profiles or []


@router.put("/episodes/{episode_id}/character_profiles", response_model=List[Dict[str, Any]])
def update_episode_character_profiles(
    episode_id: int,
    req: CharacterProfilesUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)
    episode.character_profiles = req.character_profiles or []
    db.commit()
    db.refresh(episode)
    return episode.character_profiles or []


@router.post("/episodes/{episode_id}/character_profiles/generate", response_model=EpisodeOut)
async def generate_episode_character_profile(
    episode_id: int,
    req: CharacterProfileGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    if async_mode == "1":
        tid = _submit_async(generate_episode_character_profile, user_id=current_user.id,
                            kind="char_profile_episode", episode_id=episode_id, req=req, async_mode="0")
        return JSONResponse({"task_id": tid, "async": True})
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)

    name = (req.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Character name is required")

    # Build a strict, safe prompt: canonical character sheet used as ground truth.
    tags = [t.strip() for t in (req.style_tags or []) if isinstance(t, str) and t.strip()]
    tags_str = ", ".join(tags)

    sys_prompt = (
        "You are a professional character bible writer for film storyboarding. "
        "Write a CANONICAL character profile that will be treated as the single source of truth for this script. "
        "Return ONLY Markdown (no JSON, no code fences). "
        "Keep it concise but specific. Avoid NSFW/explicit sexual content; if the user requests 'sexy', express it in non-explicit, cinematic terms. "
        "Do not invent backstory not implied by inputs; focus on identity, silhouette/body proportions, face/hair, clothing, signature mannerisms, and on-screen presence."
    )

    user_prompt = (
        f"Character Name: {name}\n"
        f"Identity/Role: {req.identity or ''}\n"
        f"Body Features: {req.body_features or ''}\n"
        f"Style Tags: {tags_str}\n"
        f"Extra Notes: {req.extra_notes or ''}\n\n"
        "Output format (Markdown):\n"
        f"### {name} (Canonical)\n"
        "- Identity: ...\n"
        "- Body & silhouette: ...\n"
        "- Face & hair: ...\n"
        "- Outfit & materials: ...\n"
        "- Screen presence (cinematic, non-explicit): ...\n"
        "- Do/Don't (hard constraints): ...\n"
    )

    llm_config = agent_service.get_active_llm_config(current_user.id, function_name=getattr(req, "function_name", None), system_api_id=getattr(req, "system_api_id", None))
    provider = llm_config.get("provider") if llm_config else None
    model = llm_config.get("model") if llm_config else None
    reservation_tx = None
    if billing_service.is_token_pricing(db, "llm_chat", provider, model):
        est = billing_service.estimate_reserve_tokens_from_messages(
            [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        reservation_tx = billing_service.reserve_credits(
            db,
            current_user.id,
            "llm_chat",
            provider,
            model,
            {
                "item": "character_profile_episode_generate",
                "estimation_method": "prompt_tokens_ratio",
                "estimated_output_ratio": billing_service.RESERVE_OUTPUT_RATIO,
                "input_tokens": est.get("input_tokens", 0),
                "output_tokens": est.get("output_tokens", 0),
                "total_tokens": est.get("total_tokens", 0),
            },
        )
    else:
        billing_service.check_balance(db, current_user.id, "llm_chat", provider, model)

    try:
        _release_db_connection(db, "character_profile_episode_llm_call")
        resp = await llm_service.generate_content_with_fallback(user_prompt, sys_prompt, llm_config)
    except Exception as e:
        if reservation_tx:
            billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), str(e))
        raise

    description_md = (resp.get("content") or "").strip()
    if not description_md:
        if reservation_tx:
            billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), "LLM returned empty content")
        raise HTTPException(status_code=500, detail="LLM returned empty content")

    usage = resp.get("usage") or {}
    if not usage:
        usage = billing_service.estimate_input_output_tokens_from_messages(
            [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": description_md},
            ],
            output_ratio=1.0,
        )
    details = {
        "item": "character_profile_episode_generate",
        "prompt_tokens": int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0),
        "completion_tokens": int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0),
        "total_tokens": int(
            usage.get(
                "total_tokens",
                int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0)
                + int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0),
            )
            or 0
        ),
    }
    details["input_tokens"] = details["prompt_tokens"]
    details["output_tokens"] = details["completion_tokens"]
    _apply_llm_routing_to_billing_details(details, resp)
    if reservation_tx:
        billing_service.settle_reservation(db, _reservation_tx_id(reservation_tx), details)
    else:
        billing_service.deduct_credits(db, current_user.id, "llm_chat", provider, model, details)

    now_iso = now_bj_iso()
    profiles = list(episode.character_profiles or [])
    updated = False
    for p in profiles:
        if isinstance(p, dict) and (p.get("name") == name):
            p.update({
                "name": name,
                "identity": req.identity,
                "body_features": req.body_features,
                "style_tags": tags,
                "extra_notes": req.extra_notes,
                "description_md": description_md,
                "updated_at": now_iso,
            })
            updated = True
            break
    if not updated:
        profiles.append({
            "name": name,
            "identity": req.identity,
            "body_features": req.body_features,
            "style_tags": tags,
            "extra_notes": req.extra_notes,
            "description_md": description_md,
            "updated_at": now_iso,
        })

    def _render_canon_md(items: List[Dict[str, Any]]) -> str:
        blocks = []
        for it in items:
            if not isinstance(it, dict):
                continue
            nm = (it.get("name") or "").strip()
            if not nm:
                continue
            md = (it.get("description_md") or "").strip()
            if md:
                blocks.append(md)
            else:
                blocks.append(f"### {nm} (Canonical)\n- Identity: {it.get('identity') or ''}\n")
        return "\n\n".join(blocks).strip()

    canon_body = _render_canon_md(profiles)
    canon_section = (
        "## Character Canon (Authoritative)\n"
        "\n"
        "<!-- CHARACTER_CANON_START -->\n"
        "The following character profiles are AUTHORITATIVE for this script. Scene analysis and downstream generation MUST use these descriptions as ground truth and IGNORE conflicting character info elsewhere in the script.\n\n"
        f"{canon_body}\n"
        "<!-- CHARACTER_CANON_END -->\n"
    )

    script = episode.script_content or ""
    if "<!-- CHARACTER_CANON_START -->" in script and "<!-- CHARACTER_CANON_END -->" in script:
        script = re.sub(
            r"## Character Canon \(Authoritative\)[\s\S]*?<!-- CHARACTER_CANON_END -->\n?",
            canon_section + "\n",
            script,
            count=1,
        )
    else:
        script = canon_section + "\n\n" + script

    episode.character_profiles = profiles
    episode.script_content = script
    db.commit()
    db.refresh(episode)
    return episode


@router.post("/episodes/{episode_id}/story_generator", response_model=EpisodeOut)
async def generate_episode_story_dna(
    episode_id: int,
    req: "StoryGeneratorRequest",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    if async_mode == "1":
        tid = _submit_async(generate_episode_story_dna, user_id=current_user.id,
                            kind="story_dna_episode", episode_id=episode_id, req=req, async_mode="0")
        return JSONResponse({"task_id": tid, "async": True})
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    project = _require_project_access(db, episode.project_id, current_user)

    mode = (req.mode or "").strip().lower()
    if mode not in ("global", "episode"):
        raise HTTPException(status_code=400, detail="mode must be 'global' or 'episode'")

    if mode == "global":
        # Backward compatible: allow generating global from any episode, but store to project.global_info
        if not req.episodes_count or int(req.episodes_count) <= 0:
            raise HTTPException(status_code=400, detail="episodes_count is required for global mode")
        generator_kind = _normalize_generator_kind(req.generator_kind) or "story"
        if generator_kind == "promo":
            prompt_filename = "promo_generator_global.txt"
        else:
            prompt_filename = "master_story_architect.md"
    else:
        if not req.episode_number or int(req.episode_number) <= 0:
            raise HTTPException(status_code=400, detail="episode_number is required for episode mode")
        prompt_filename = "story_generator_episode.txt"

    try:
        sys_prompt = _resolve_prompt_text(prompt_filename)
    except FileNotFoundError:
        logger.error("Story generator prompt not found: %s", prompt_filename)
        raise HTTPException(status_code=404, detail=f"Prompt file '{prompt_filename}' not found.")

    user_prompt_body = (
        f"Mode: {mode}\n"
        f"Episodes Count: {req.episodes_count or ''}\n"
        f"Episode Duration (minutes): {_resolve_episode_duration_minutes(getattr(req, 'episode_duration_minutes', None))}\n"
        f"Episode Number: {req.episode_number or ''}\n"
        f"Foreshadowing: {req.foreshadowing or ''}\n"
        f"Background: {req.background or ''}\n"
        f"Setup: {req.setup or ''}\n"
        f"Development: {req.development or ''}\n"
        f"Turning Points: {req.turning_points or ''}\n"
        f"Climax: {req.climax or ''}\n"
        f"Resolution: {req.resolution or ''}\n"
        f"Suspense: {req.suspense or ''}\n"
        f"Extra Notes: {req.extra_notes or ''}\n"
    )
    if mode == "global" and prompt_filename == "master_story_architect.md":
        user_prompt_body += (
            "\nTruncatable markers (hard): wrap Part 1 in [STORY_DNA_THINKING_START]…[STORY_DNA_THINKING_END]; "
            "wrap §0–§9 (including [SCRIPT_TITLE:…]) in [STORY_DNA_OUTPUT_START]…[STORY_DNA_OUTPUT_END]. "
            "Do not echo the INPUT block into OUTPUT.\n"
        )
        user_prompt = wrap_story_dna_input_block(user_prompt_body)
    else:
        user_prompt = user_prompt_body

    llm_config = agent_service.get_active_llm_config(current_user.id, function_name=getattr(req, "function_name", None), system_api_id=getattr(req, "system_api_id", None))
    llm_config = _inject_project_creativity_temperature(
        llm_config,
        project.global_info,
        context="generate_episode_story_dna",
    )
    provider = llm_config.get("provider") if llm_config else None
    model = llm_config.get("model") if llm_config else None
    reservation_tx = None
    item_name = f"story_generator_{mode}"
    if billing_service.is_token_pricing(db, "llm_chat", provider, model):
        est = billing_service.estimate_reserve_tokens_from_messages(
            [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        reservation_tx = billing_service.reserve_credits(
            db,
            current_user.id,
            "llm_chat",
            provider,
            model,
            {
                "item": item_name,
                "estimation_method": "prompt_tokens_ratio",
                "estimated_output_ratio": billing_service.RESERVE_OUTPUT_RATIO,
                "input_tokens": est.get("input_tokens", 0),
                "output_tokens": est.get("output_tokens", 0),
                "total_tokens": est.get("total_tokens", 0),
            },
        )
    else:
        billing_service.check_balance(db, current_user.id, "llm_chat", provider, model)

    _release_db_connection(db, f"generate_episode_story_dna_{mode}_llm_call")

    try:
        generated_payload = await generate_markdown_with_retry(
            user_prompt=user_prompt,
            sys_prompt=sys_prompt,
            llm_config=llm_config,
            strict_markdown=False if (mode == "global" and prompt_filename == "master_story_architect.md") else (req.strict_markdown is not False),
            require_h1=False if (mode == "global" and prompt_filename == "master_story_architect.md") else True,
            return_meta=True,
        )
    except Exception as e:
        if reservation_tx:
            billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), str(e))
        raise

    generated_md = str((generated_payload or {}).get("content") or "").strip()
    if not generated_md:
        raise HTTPException(status_code=500, detail="LLM returned empty content")

    if mode == "global" and prompt_filename == "master_story_architect.md":
        dna_view = extract_story_dna_output_for_validation(generated_md)
        generated_md = normalize_story_dna_markdown_for_persist(generated_md)
        logger.info(
            "[generate_episode_story_dna] story_dna_markers mode=global had_output=%s had_thinking=%s "
            "truncated_thinking=%s persist_len=%s output_len=%s thinking_len=%s",
            bool(dna_view.get("had_output_markers")),
            bool(dna_view.get("had_thinking_markers")),
            bool(dna_view.get("truncated_thinking")),
            len(generated_md),
            len(str(dna_view.get("content") or "")),
            len(str(dna_view.get("thinking") or "")),
        )

    usage = (generated_payload or {}).get("usage") if isinstance(generated_payload, dict) else {}
    if not usage:
        usage = billing_service.estimate_input_output_tokens_from_messages(
            [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": generated_md},
            ],
            output_ratio=1.0,
        )
    billing_details = {
        "item": item_name,
        "prompt_tokens": int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0),
        "completion_tokens": int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0),
        "total_tokens": int(
            usage.get(
                "total_tokens",
                int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0)
                + int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0),
            )
            or 0
        ),
    }
    billing_details["input_tokens"] = billing_details["prompt_tokens"]
    billing_details["output_tokens"] = billing_details["completion_tokens"]
    _apply_llm_routing_to_billing_details(billing_details, generated_payload)

    if reservation_tx:
        billing_service.settle_reservation(db, _reservation_tx_id(reservation_tx), billing_details)
    else:
        billing_service.deduct_credits(db, current_user.id, "llm_chat", provider, model, billing_details)

    # Persist both output and the inputs that produced it.
    try:
        story_input = req.model_dump()
    except AttributeError:
        story_input = req.dict()
    story_input["mode"] = mode
    story_input["generator_kind"] = _normalize_generator_kind(story_input.get("generator_kind") or req.generator_kind) or "story"
    story_input["generator_kind"] = _normalize_generator_kind(story_input.get("generator_kind") or req.generator_kind) or "story"

    now_iso = now_bj_iso()
    if mode == "global":
        project = db.merge(project)
        global_kind = _normalize_generator_kind(story_input.get("generator_kind")) or "story"
        gi = dict(project.global_info or {})
        if global_kind == "promo":
            gi["promo_generator_input"] = story_input
            gi["promo_generator_input_updated_at"] = now_iso
            gi["promo_dna_global_md"] = generated_md
            gi["promo_dna_global_updated_at"] = now_iso
        else:
            gi["story_generator_global_input"] = story_input
            gi["story_dna_global_md"] = generated_md
            gi["story_dna_global_updated_at"] = now_iso
        project.global_info = gi
        db.add(project)
    else:
        episode = db.merge(episode)
        ei = _episode_info_from_episode(episode)
        ei["story_generator_episode_input"] = story_input
        ei["story_generator_episode_input_updated_at"] = now_iso
        ei["story_dna_episode_md"] = generated_md
        ei["story_dna_episode_updated_at"] = now_iso
        # Also store the episode_number used to generate
        ei["story_dna_episode_number"] = int(req.episode_number)
        episode.episode_info = ei
        db.add(episode)

    db.commit()
    db.refresh(episode)
    return episode


@router.put("/episodes/{episode_id}/story_generator/input", response_model=EpisodeOut)
def save_episode_story_generator_input(
    episode_id: int,
    req: "StoryGeneratorRequest",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Persist Story Generator draft inputs without calling the LLM.

    This is used to avoid losing in-progress inputs before the user clicks Generate.
    """
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    project = _require_project_access(db, episode.project_id, current_user)

    mode = (req.mode or "").strip().lower()
    if mode not in ("global", "episode"):
        raise HTTPException(status_code=400, detail="mode must be 'global' or 'episode'")

    try:
        story_input = req.model_dump()
    except AttributeError:
        story_input = req.dict()
    story_input["mode"] = mode

    now_iso = now_bj_iso()
    if mode == "global":
        global_kind = _normalize_generator_kind(story_input.get("generator_kind")) or "story"
        gi = dict(project.global_info or {})
        if global_kind == "promo":
            gi["promo_generator_input"] = story_input
            gi["promo_generator_input_updated_at"] = now_iso
        else:
            gi["story_generator_global_input"] = story_input
            gi["story_generator_global_input_updated_at"] = now_iso
        project.global_info = gi
        db.add(project)
    else:
        ei = _episode_info_from_episode(episode)
        ei["story_generator_episode_input"] = story_input
        ei["story_generator_episode_input_updated_at"] = now_iso
        episode.episode_info = ei
        db.add(episode)

    db.commit()
    db.refresh(episode)
    return episode



@router.delete("/episodes/{episode_id}", status_code=200)
def delete_episode(
    episode_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    episode = db.query(Episode).filter(
        Episode.id == episode_id,
        _active_episode_clause(),
    ).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    
    _require_project_access(db, episode.project_id, current_user, owner_only=True)

    if _is_soft_deleted(episode):
        return {"status": "deleted", "batch_id": None}

    now = now_bj_iso()
    batch_id = _start_deletion_batch(
        db,
        user_id=current_user.id,
        project_id=int(episode.project_id),
        episode_id=int(episode.id),
        action_type="episode",
        label=str(episode.title or f"Episode {episode_id}"),
    )
    _track_deletion_batch_items(db, batch_id, "episode", [episode.id])
    episode.is_deleted = True
    episode.deleted_at = now
    _soft_delete_episode_children(db, int(episode.id), now=now, batch_id=batch_id)
    _finalize_deletion_batch(db, batch_id)
    db.add(episode)
    db.commit()
    return {"status": "deleted", "batch_id": batch_id}

