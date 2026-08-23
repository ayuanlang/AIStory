# -*- coding: utf-8 -*-
"""Workspace section routes — symbols pulled from shared module."""
from __future__ import annotations

from app.api.routers.workspace import shared as _shared

# Attach routes onto the same APIRouter instance and reuse helpers.
router = _shared.router
globals().update({k: v for k, v in vars(_shared).items() if k not in {"__name__", "__file__", "__package__", "__loader__", "__spec__", "__doc__", "__builtins__"}})


# --- Scenes ---

from app.schemas.scene import (  # noqa: E402,F401
    SceneBatchUpsertRequest,
    SceneCreate,
    SceneOut,
    ScenePurgeRequest,
    SceneRegenerateRequest,
)


# Scene subject helpers (canonical: app.services.scene_subject_helpers).
from app.services.scene_subject_helpers import (  # noqa: E402,F401
    _build_project_subject_inventory,
    _format_project_subject_inventory_block,
    _PRIOR_ENTITY_DESIGN_TYPES,
    _normalize_prior_entity_design_type,
    _parse_subject_index_entries_for_prior_prompts,
    _build_prior_entity_generation_prompts_block,
    _normalize_scene_header,
    _clean_scene_table_cell,
    _parse_scene_rows_from_markdown,
    _normalize_subject_entity_type,
    _collect_llm_json_text_candidates,
    _extract_subjects_json_from_text,
)


@router.get("/episodes/{episode_id}/scenes", response_model=List[SceneOut])
def read_scenes(
    episode_id: int,
    scene_code: Optional[str] = None,
    keyword: Optional[str] = None,
    skip: int = 0,
    limit: int = 300,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Ownership check
    episode = db.query(Episode).filter(Episode.id == episode_id, _active_episode_clause()).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
        
    _require_project_access(db, episode.project_id, current_user)
        
    query = db.query(Scene).filter(Scene.episode_id == episode_id, _active_scene_clause())
    if scene_code:
        token = f"%{scene_code.strip()}%"
        query = query.filter(Scene.scene_no.ilike(token))
    if keyword:
        token = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                Scene.scene_name.ilike(token),
                Scene.environment_name.ilike(token),
                Scene.linked_characters.ilike(token),
                Scene.key_props.ilike(token),
            )
        )
    safe_skip = max(int(skip or 0), 0)
    safe_limit = max(1, min(int(limit or 300), 500))
    rows = _sort_scenes_by_scene_no(query.all())
    return rows[safe_skip:safe_skip + safe_limit]

@router.post("/episodes/{episode_id}/scenes", response_model=SceneOut)
def create_scene(
    episode_id: int,
    scene: SceneCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    scene_api_started_perf = time.perf_counter()
    episode = db.query(Episode).filter(Episode.id == episode_id, _active_episode_clause()).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
        
    _require_project_access(db, episode.project_id, current_user)

    canonical_scene_no = _canonicalize_scene_no(
        getattr(scene, "scene_no", None),
        scene_id=getattr(scene, "scene_id", None) if hasattr(scene, "scene_id") else None,
    )
    if not canonical_scene_no:
        raise HTTPException(status_code=422, detail="SCENE_NO_REQUIRED")

    existing_scene = _find_active_scene_by_scene_no(
        db,
        episode_id=episode_id,
        scene_no=canonical_scene_no,
    )
    if existing_scene:
        # Import control: scene_no already present — abandon overwrite, return existing.
        # Also heal legacy alias rows (EP01_SC03) onto the canonical number ("3").
        if str(existing_scene.scene_no or "").strip() != canonical_scene_no:
            existing_scene.scene_no = canonical_scene_no
            db.add(existing_scene)
            db.commit()
            db.refresh(existing_scene)
        elapsed_ms = int((time.perf_counter() - scene_api_started_perf) * 1000)
        logger.info(
            "[SceneImportAPI] skip-existing | episode_id=%s | project_id=%s | scene_id=%s | scene_no=%s | elapsed_ms=%s",
            episode_id,
            episode.project_id,
            existing_scene.id,
            str(existing_scene.scene_no or "").strip(),
            elapsed_ms,
        )
        return existing_scene

    logger.info(
        "[SceneImportAPI] create-new start | episode_id=%s | project_id=%s | scene_no=%s | scene_name=%s",
        episode_id,
        episode.project_id,
        canonical_scene_no,
        str(scene.scene_name or "").strip(),
    )
    db_scene = Scene(
        episode_id=episode_id,
        scene_no=canonical_scene_no,
        original_script_text=scene.original_script_text,
        scene_name=scene.scene_name,
        equivalent_duration=scene.equivalent_duration,
        core_scene_info=scene.core_scene_info,
        environment_name=scene.environment_name,
        linked_characters=scene.linked_characters,
        key_props=scene.key_props
    )
    db.add(db_scene)
    try:
        _recompute_and_persist_project_cost_estimation(db, int(episode.project_id))
    except Exception as cost_exc:
        logger.warning("create_scene cost recompute skipped | project_id=%s err=%s", episode.project_id, cost_exc)
    try:
        db.commit()
    except Exception as commit_exc:
        db.rollback()
        raced = _find_active_scene_by_scene_no(
            db,
            episode_id=episode_id,
            scene_no=canonical_scene_no,
        )
        if raced is not None:
            logger.info(
                "[SceneImportAPI] create-new unique-race | episode_id=%s | project_id=%s | scene_id=%s | scene_no=%s | err=%s",
                episode_id,
                episode.project_id,
                raced.id,
                canonical_scene_no,
                commit_exc,
            )
            return raced
        raise
    db.refresh(db_scene)
    elapsed_ms = int((time.perf_counter() - scene_api_started_perf) * 1000)
    logger.info(
        "[SceneImportAPI] create-new done | episode_id=%s | project_id=%s | scene_id=%s | scene_no=%s | elapsed_ms=%s",
        episode_id,
        episode.project_id,
        db_scene.id,
        str(db_scene.scene_no or "").strip(),
        elapsed_ms,
    )
    return db_scene

@router.post("/episodes/{episode_id}/scenes/batch_upsert", response_model=Dict[str, Any])
def batch_upsert_scenes(
    episode_id: int,
    request: SceneBatchUpsertRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    started_perf = time.perf_counter()
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)

    input_scenes = list(request.scenes or [])
    if not input_scenes:
        return {
            "status": "ok",
            "episode_id": int(episode_id),
            "project_id": int(episode.project_id),
            "processed": 0,
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "elapsed_ms": int((time.perf_counter() - started_perf) * 1000),
            "scenes": [],
        }

    # Canonicalize + dedupe scene_no within the same import payload (keep first).
    # EP01_SC03 / 03 / 3 collapse to the same key so one episode cannot create aliases.
    deduped_input: List[Any] = []
    seen_input_scene_nos: set = set()
    for item in input_scenes:
        raw_scene_no = str(getattr(item, "scene_no", "") or "").strip()
        scene_no = _canonicalize_scene_no(raw_scene_no)
        if not scene_no:
            deduped_input.append(item)
            continue
        if hasattr(item, "scene_no"):
            item.scene_no = scene_no
        if scene_no in seen_input_scene_nos:
            logger.warning(
                "[SceneImportAPI] batch_upsert skip duplicate scene_no in payload | episode_id=%s scene_no=%s raw=%s",
                episode_id,
                scene_no,
                raw_scene_no,
            )
            continue
        seen_input_scene_nos.add(scene_no)
        deduped_input.append(item)
    input_scenes = deduped_input

    skip_existing = bool(getattr(request, "skip_existing", True))

    lookup_keys: List[str] = []
    for item in input_scenes:
        lookup_keys.extend(_scene_no_lookup_keys(getattr(item, "scene_no", None)))
    lookup_keys = list(dict.fromkeys(lookup_keys))
    existing_rows = (
        db.query(Scene)
        .filter(
            Scene.episode_id == int(episode_id),
            Scene.scene_no.in_(lookup_keys),
            _active_scene_clause(),
        )
        .all()
    ) if lookup_keys else []
    # Collapse active alias/duplicate rows onto one canonical scene_no; keep newest id.
    existing_by_no: Dict[str, Any] = {}
    duplicate_scene_ids: List[int] = []
    for row in existing_rows:
        canonical = _canonicalize_scene_no(getattr(row, "scene_no", None))
        if not canonical:
            continue
        if str(row.scene_no or "").strip() != canonical:
            row.scene_no = canonical
        prev = existing_by_no.get(canonical)
        if prev is None:
            existing_by_no[canonical] = row
            continue
        keep = row if int(getattr(row, "id", 0) or 0) >= int(getattr(prev, "id", 0) or 0) else prev
        drop = prev if keep is row else row
        existing_by_no[canonical] = keep
        duplicate_scene_ids.append(int(drop.id))
    if duplicate_scene_ids:
        now = now_bj_iso()
        # Cascade soft-delete shots; otherwise orphan active shots keep blocking
        # apply_ai_result while the UI only lists the kept active scene (empty).
        _soft_delete_shots(db, scene_ids=duplicate_scene_ids, now=now)
        db.query(Scene).filter(Scene.id.in_(duplicate_scene_ids)).update(
            {Scene.is_deleted: True, Scene.deleted_at: now},
            synchronize_session=False,
        )
        logger.info(
            "[SceneImportAPI] soft_deleted duplicate active scenes count=%s episode_id=%s",
            len(duplicate_scene_ids),
            episode_id,
        )

    created = 0
    updated = 0
    skipped = 0
    touched_scene_nos: List[str] = []

    for item in input_scenes:
        scene_no = _canonicalize_scene_no(getattr(item, "scene_no", None))
        if not scene_no:
            skipped += 1
            continue
        touched_scene_nos.append(scene_no)
        existing = existing_by_no.get(scene_no)
        if existing is not None:
            if str(existing.scene_no or "").strip() != scene_no:
                existing.scene_no = scene_no
            if skip_existing:
                skipped += 1
                continue
            existing.scene_name = item.scene_name
            existing.original_script_text = item.original_script_text
            existing.equivalent_duration = item.equivalent_duration
            existing.core_scene_info = item.core_scene_info
            existing.environment_name = item.environment_name
            existing.linked_characters = item.linked_characters
            existing.key_props = item.key_props
            updated += 1
            continue

        soft_deleted = (
            db.query(Scene)
            .filter(
                Scene.episode_id == int(episode_id),
                Scene.scene_no.in_(_scene_no_lookup_keys(scene_no)),
                Scene.is_deleted.is_(True),
            )
            .order_by(Scene.id.desc())
            .first()
        )
        if soft_deleted is not None:
            soft_deleted.is_deleted = False
            soft_deleted.deleted_at = None
            soft_deleted.scene_no = scene_no
            soft_deleted.scene_name = item.scene_name
            soft_deleted.original_script_text = item.original_script_text
            soft_deleted.equivalent_duration = item.equivalent_duration
            soft_deleted.core_scene_info = item.core_scene_info
            soft_deleted.environment_name = item.environment_name
            soft_deleted.linked_characters = item.linked_characters
            soft_deleted.key_props = item.key_props
            # Stale shots from a prior life of this row must not block a fresh
            # storyboard apply while looking "empty" after episode-scoped filters.
            _soft_delete_shots(db, scene_id=int(soft_deleted.id))
            soft_deleted.ai_shots_result = None
            existing_by_no[scene_no] = soft_deleted
            updated += 1
            continue

        row = Scene(
            episode_id=int(episode_id),
            scene_no=scene_no,
            original_script_text=item.original_script_text,
            scene_name=item.scene_name,
            equivalent_duration=item.equivalent_duration,
            core_scene_info=item.core_scene_info,
            environment_name=item.environment_name,
            linked_characters=item.linked_characters,
            key_props=item.key_props,
        )
        db.add(row)
        existing_by_no[scene_no] = row
        created += 1

    if bool(request.recompute_cost):
        try:
            _recompute_and_persist_project_cost_estimation(db, int(episode.project_id))
        except Exception as cost_exc:
            logger.warning("batch_upsert_scenes cost recompute skipped | project_id=%s err=%s", episode.project_id, cost_exc)

    try:
        db.commit()
    except Exception as commit_exc:
        db.rollback()
        logger.error(
            "[SceneImportAPI] batch_upsert commit failed | episode_id=%s | project_id=%s | err=%s",
            episode_id,
            episode.project_id,
            commit_exc,
        )
        raise HTTPException(status_code=409, detail="SCENE_NO_UNIQUE_CONFLICT") from commit_exc

    result_scenes: List[Dict[str, Any]] = []
    unique_touched = list(dict.fromkeys([s for s in touched_scene_nos if s]))
    if unique_touched:
        refreshed = (
            db.query(Scene)
            .filter(
                Scene.episode_id == int(episode_id),
                Scene.scene_no.in_(unique_touched),
                _active_scene_clause(),
            )
            .all()
        )
        refreshed_by_no = {str(row.scene_no or "").strip(): row for row in refreshed}
        for scene_no in unique_touched:
            row = refreshed_by_no.get(scene_no)
            if row is None:
                continue
            result_scenes.append({
                "id": int(row.id),
                "scene_no": str(row.scene_no or ""),
                "scene_name": str(row.scene_name or ""),
            })

    elapsed_ms = int((time.perf_counter() - started_perf) * 1000)
    logger.info(
        "[SceneImportAPI] batch_upsert done | episode_id=%s | project_id=%s | processed=%s | created=%s | updated=%s | skipped=%s | elapsed_ms=%s",
        episode_id,
        episode.project_id,
        len(input_scenes),
        created,
        updated,
        skipped,
        elapsed_ms,
    )
    return {
        "status": "ok",
        "episode_id": int(episode_id),
        "project_id": int(episode.project_id),
        "processed": int(len(input_scenes)),
        "created": int(created),
        "updated": int(updated),
        "skipped": int(skipped),
        "elapsed_ms": elapsed_ms,
        "scenes": result_scenes,
    }

@router.put("/scenes/{scene_id}", response_model=SceneOut)
def update_scene(
    scene_id: int,
    scene_in: SceneCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not db_scene:
        raise HTTPException(status_code=404, detail="Scene not found")
        
    # Ownership
    episode = db.query(Episode).filter(Episode.id == db_scene.episode_id).first()
    _require_project_access(db, episode.project_id, current_user)

    update_data = scene_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_scene, field, value)
        
    db.add(db_scene)
    try:
        _recompute_and_persist_project_cost_estimation(db, int(episode.project_id))
    except Exception as cost_exc:
        logger.warning("update_scene cost recompute skipped | project_id=%s err=%s", episode.project_id, cost_exc)
    db.commit()
    db.refresh(db_scene)
    return db_scene


@router.post("/episodes/{episode_id}/scenes/purge", response_model=Dict[str, Any])
def purge_episode_scenes(
    episode_id: int,
    request: ScenePurgeRequest = ScenePurgeRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == int(episode_id), _active_episode_clause()).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user, owner_only=True)

    deleted_scenes = _hard_purge_episode_scenes(db, int(episode_id))
    removed_progress = 0
    if bool(getattr(request, "clear_progress", True)):
        removed_progress = _purge_episode_scene_progress(
            db,
            project_id=int(episode.project_id),
            episode_id=int(episode_id),
        )

    try:
        _recompute_and_persist_project_cost_estimation(db, int(episode.project_id))
    except Exception as cost_exc:
        logger.warning("purge_episode_scenes cost recompute skipped | project_id=%s err=%s", episode.project_id, cost_exc)

    db.commit()
    return {
        "status": "ok",
        "episode_id": int(episode_id),
        "project_id": int(episode.project_id),
        "deleted_scenes": deleted_scenes,
        "removed_progress_units": removed_progress,
    }


@router.delete("/scenes/{scene_id}", status_code=200)
def delete_scene(
    scene_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_scene = db.query(Scene).filter(Scene.id == scene_id, _active_scene_clause()).first()
    if not db_scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    episode = db.query(Episode).filter(Episode.id == db_scene.episode_id, _active_episode_clause()).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    _require_project_access(db, episode.project_id, current_user, owner_only=True)

    if _is_soft_deleted(db_scene):
        return {"status": "deleted", "batch_id": None}

    now = now_bj_iso()
    scene_label = str(db_scene.scene_name or db_scene.scene_no or f"Scene {scene_id}")
    batch_id = _start_deletion_batch(
        db,
        user_id=current_user.id,
        project_id=int(episode.project_id),
        episode_id=int(episode.id),
        action_type="scene",
        label=scene_label,
    )
    _soft_delete_scenes(db, scene_id=scene_id, now=now, batch_id=batch_id)
    _finalize_deletion_batch(db, batch_id)
    try:
        _recompute_and_persist_project_cost_estimation(db, int(episode.project_id))
    except Exception as cost_exc:
        logger.warning("delete_scene cost recompute skipped | project_id=%s err=%s", episode.project_id, cost_exc)
    db.commit()
    return {"status": "deleted", "batch_id": batch_id}


@router.post("/scenes/{scene_id}/regenerate", response_model=Dict[str, Any])
async def regenerate_scene(
    scene_id: int,
    req: SceneRegenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    if async_mode == "1":
        tid = _submit_async(regenerate_scene, user_id=current_user.id,
                            kind="regenerate_scene", scene_id=scene_id, req=req, async_mode="0")
        return JSONResponse({"task_id": tid, "async": True})
    db_scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not db_scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    episode = db.query(Episode).filter(Episode.id == db_scene.episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    project = _require_project_access(db, episode.project_id, current_user, owner_only=True)

    user_requirements = str(req.user_requirements or "").strip()
    if not user_requirements:
        raise HTTPException(status_code=400, detail="user_requirements is required")

    safe_max_scenes = max(1, min(int(req.max_scenes or 4), 8))
    entity_only_mode = bool(req.entity_only_mode)

    system_instruction = ""
    if req.system_prompt:
        system_instruction = str(req.system_prompt)
    else:
        prompt_filename = str(req.prompt_file or "scene_regenerate.txt").strip() or "scene_regenerate.txt"
        try:
            system_instruction = _resolve_prompt_text(prompt_filename)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"Prompt file '{prompt_filename}' not found.")

    project_global_info = project.global_info if isinstance(project.global_info, dict) else {}
    project_title_str = str(project.title or "")
    episode_title_str = str(episode.title or "")

    def _project_info_str(key: str) -> str:
        value = project_global_info.get(key)
        if value is None:
            return ""
        if isinstance(value, list):
            return ", ".join([str(v or "").strip() for v in value if str(v or "").strip()])
        return str(value or "").strip()

    project_context_lines = [
        f"Project Title: {project_title_str}",
        f"Episode Title: {episode_title_str}",
    ]
    for key, label in (
        ("script_title", "Script Title"),
        ("series_episode", "Series Episode"),
        ("type", "Type"),
        ("base_positioning", "Base Positioning"),
        ("language", "Language"),
        ("Global_Style", "Global Style"),
        ("tone", "Tone"),
        ("lighting", "Lighting"),
        ("borrowed_films", "Borrowed Films"),
    ):
        value = _project_info_str(key)
        if value:
            project_context_lines.append(f"{label}: {value}")

    project_context_block = "\n".join(project_context_lines)

    scene_subject_seed_lines = [
        f"Environment Name Seed: {str(db_scene.environment_name or '').strip() or '(empty)'}",
        f"Linked Characters Seed: {str(db_scene.linked_characters or '').strip() or '(empty)'}",
        f"Key Props Seed: {str(db_scene.key_props or '').strip() or '(empty)'}",
    ]
    scene_subject_seeds_block = "\n".join(scene_subject_seed_lines)
    original_script_grounding = str(db_scene.original_script_text or "").strip()
    original_script_grounding_block = original_script_grounding or "(empty)"

    if entity_only_mode:
        regen_injection = (
            "\n\n"
            "[Regeneration Mode Injection]\n"
            "You are in SCENE ENTITY SUPPLEMENT MODE for one existing scene row.\n"
            "Primary objective: supplement the missing entities required by this scene according to [User Requirements] with highest priority.\n"
            "You MUST use project context + existing subject inventory + current scene content + original script grounding together as the extraction and verification basis.\n"
            "You MUST use Original Script Text as the ground-truth reference to verify whether linked characters are missing, and whether core scene information has major omissions or obvious visual-guidance errors.\n"
            "You MAY ignore minor wording differences that do not materially affect story meaning, staging, or visual guidance.\n"
            "If Original Script Text reveals materially missing characters, core actions, location anchors, or visual-guidance facts, you MUST repair the current scene row patch in markdown instead of only patching entity fields.\n"
            "You MUST follow scene_analysis subject extraction principles: reuse existing subjects first, only add truly missing subjects, and keep naming stable.\n"
            "scene_analysis.txt is the final authority for all subject/entity prompt rules. scene_regenerate.txt must be interpreted to stay aligned with scene_analysis.txt, and if any runtime summary conflicts, scene_analysis.txt wins.\n"
            "You MUST follow the full Chinese subject-sync rules defined in scene_regenerate.txt; if any shorter runtime summary conflicts with those file rules, the file rules win.\n"
            "You MUST complete hidden required entities when an action physically depends on a source object, carrier, receiver, or container; for example, pouring implies a source container, and taking a tissue implies a tissue source container.\n"
            "You MUST keep concrete scene-visible object coverage explicit; do not collapse tables, cups, doors, windows, lamps, phones, keyboards, and similar visible objects into vague generic categories.\n"
            "You MUST NOT merge two readable outfits or two readable identity states into one character item; if two states are needed, output two separate character entities with dependency logic.\n"
            "You MUST apply clothing hint recognition: touching, adjusting, lifting, fastening, or straightening a distinctive garment/accessory counts as evidence that the corresponding outfit state already exists and may require a separate character entity.\n"
            "You MUST preserve project language rules from the prompt file: do not force dialogue, visible text, labels, or screen text into English unless the project language actually requires English.\n"
            "Character generation prompts must preserve full-body framing with shoes visible as the asset baseline.\n"
            "Environment generation prompts must remain clean-plate, no-human prompts: no over-shoulder wording, no shoulder silhouettes, no human reflections, no human shadows, no role labels, and no CHAR references inside environment prompts.\n"
            "Output must be import-first and parser-safe: do NOT output explanations, bullets, validation notes, or code fences.\n"
            "The final output must contain exactly 2 parts only: first exactly 1 markdown scene row patch table, then exactly 1 SUBJECTS_JSON object.\n"
            "SUBJECTS_JSON must be exactly one valid JSON object with top-level keys characters, props, environments, covers, and all keys must always exist even when empty.\n"
            "For each entity item, use only the field contract defined by scene_regenerate.txt and scene_analysis.txt; if an identifier is included, only subject_no may appear as an extra import field.\n"
            "Missing optional strings must use empty string, missing arrays must use empty array, and you must not output null, undefined, metadata wrappers, or parser-hint fields.\n"
            "Return exactly 1 scene row patch in markdown table format plus one SUBJECTS_JSON object for missing entities only.\n"
            "Environment Name / Linked Characters / Key Props with two or more names MUST be separated by the Chinese comma ， only; do not use /, ／, |, 、, or ASCII commas.\n"
            "In entity-only mode, scene/shots are not replaced; the row patch may update scene_name / equivalent_duration / core_scene_info / original_script_text / environment_name / linked_characters / key_props when needed to reflect corrected scene grounding and supplemented entities."
        )
    else:
        regen_injection = (
            "\n\n"
            "[Regeneration Mode Injection]\n"
            "You are in FULL SCENE REGENERATION MODE for one existing scene row.\n"
            "Primary objective: regenerate the scene according to [User Requirements] while also supplementing any newly required entities.\n"
            "You MUST use project context + existing subject inventory + current scene content + original script grounding together as the generation basis.\n"
            "You MUST use Original Script Text as the ground-truth reference to verify whether linked characters are missing, and whether core scene information has major omissions or obvious visual-guidance errors.\n"
            "You MAY ignore minor wording differences that do not materially affect story meaning, staging, or visual guidance.\n"
            "You MUST follow scene_analysis subject extraction principles: reuse existing subjects first, only add truly missing subjects, and keep naming stable.\n"
            "scene_analysis.txt is the final authority for all subject/entity prompt rules. scene_regenerate.txt must be interpreted to stay aligned with scene_analysis.txt, and if any runtime summary conflicts, scene_analysis.txt wins.\n"
            "You MUST follow the full Chinese subject-sync rules defined in scene_regenerate.txt; if any shorter runtime summary conflicts with those file rules, the file rules win.\n"
            "You MUST complete hidden required entities when an action physically depends on a source object, carrier, receiver, or container; for example, pouring implies a source container, and taking a tissue implies a tissue source container.\n"
            "You MUST keep concrete scene-visible object coverage explicit; do not collapse tables, cups, doors, windows, lamps, phones, keyboards, and similar visible objects into vague generic categories.\n"
            "You MUST NOT merge two readable outfits or two readable identity states into one character item; if two states are needed, output two separate character entities with dependency logic.\n"
            "You MUST apply clothing hint recognition: touching, adjusting, lifting, fastening, or straightening a distinctive garment/accessory counts as evidence that the corresponding outfit state already exists and may require a separate character entity.\n"
            "You MUST preserve project language rules from the prompt file: do not force dialogue, visible text, labels, or screen text into English unless the project language actually requires English.\n"
            "Character generation prompts must preserve full-body framing with shoes visible as the asset baseline.\n"
            "Environment generation prompts must remain clean-plate, no-human prompts: no over-shoulder wording, no shoulder silhouettes, no human reflections, no human shadows, no role labels, and no CHAR references inside environment prompts.\n"
            "Output must be import-first and parser-safe: do NOT output explanations, bullets, validation notes, or code fences.\n"
            "The final output must contain exactly 2 parts only: markdown scene row patch table(s) first, then exactly 1 SUBJECTS_JSON object.\n"
            "SUBJECTS_JSON must be exactly one valid JSON object with top-level keys characters, props, environments, covers, and all keys must always exist even when empty.\n"
            "For each entity item, use only the field contract defined by scene_regenerate.txt and scene_analysis.txt; if an identifier is included, only subject_no may appear as an extra import field.\n"
            "Missing optional strings must use empty string, missing arrays must use empty array, and you must not output null, undefined, metadata wrappers, or parser-hint fields.\n"
            f"Return 1 to {safe_max_scenes} regenerated scene rows in markdown table format plus one SUBJECTS_JSON object for missing entities only.\n"
            "Environment Name / Linked Characters / Key Props with two or more names MUST be separated by the Chinese comma ， only; do not use /, ／, |, 、, or ASCII commas."
        )
    system_instruction = f"{system_instruction}{regen_injection}"

    scene_snapshot = (
        f"| Episode ID | Scene ID | Scene No. | Scene Name | Equivalent Duration | Core Scene Info | Original Script Text | Environment Name | Linked Characters | Key Props |\n"
        f"| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
        f"| EP{int(episode.id):02d} | EP{int(episode.id):02d}_SCXX | {db_scene.scene_no or ''} | {db_scene.scene_name or ''} | {db_scene.equivalent_duration or ''} | {(db_scene.core_scene_info or '').replace(chr(10), '<br>')} | {(db_scene.original_script_text or '').replace(chr(10), '<br>')} | {db_scene.environment_name or ''} | {db_scene.linked_characters or ''} | {db_scene.key_props or ''} |"
    )

    existing_subject_inventory = _build_project_subject_inventory(
        db,
        int(project.id),
        episode_id=int(episode.id),
    )
    existing_subjects_block = _format_project_subject_inventory_block(existing_subject_inventory)

    existing_subjects_system_guard = (
        "\n\n"
        "[Existing Entity Reuse Guard - High Priority]\n"
        "The following entities already exist in the current episode scope and are dependency baselines.\n"
        "You MUST treat them as immutable references: do NOT rewrite, rename, redefine, or replace these entities.\n"
        "Do NOT output them as newly generated entities in SUBJECTS_JSON.\n"
        "SUBJECTS_JSON must include only truly missing entities.\n"
        f"{existing_subjects_block}"
    )
    system_instruction = f"{system_instruction}{existing_subjects_system_guard}"

    logger.info(
        "[regenerate_scene] entity injection scene_id=%s project_id=%s counts: characters=%s props=%s environments=%s covers=%s",
        scene_id,
        project.id,
        len(existing_subject_inventory.get("characters") or []),
        len(existing_subject_inventory.get("props") or []),
        len(existing_subject_inventory.get("environments") or []),
    )

    mode_specific_task_lines = (
        "- This task is mainly for supplementing missing entities of the current scene, not rewriting the whole scene.\n"
        "- However, you MUST also use Original Script Text to verify missing characters and major core scene info / visual-guidance omissions or obvious errors.\n"
        "- If such omissions or obvious errors exist, repair them in the single current-scene row patch markdown while keeping the scene identity stable.\n"
        "- Return a single current-scene row patch only; do not split into multiple rows in entity supplement mode.\n"
    ) if entity_only_mode else (
        f"- Regenerate this scene into 1 to {safe_max_scenes} scene rows when needed by user requirements.\n"
        "- Use Original Script Text to verify missing characters and major core scene info / visual-guidance omissions or obvious errors before finalizing the regenerated row(s).\n"
        "- Supplement any newly required entities at the same time.\n"
    )

    mode_specific_output_line = (
        "1) One scene markdown table row patch for the current scene (importable by scene parser).\n"
        if entity_only_mode else
        "1) Scene markdown table rows (importable by scene parser).\n"
    )

    current_scene_section = wrap_injection_section(
        "当前场景",
        "Current Scene (Markdown Row):\n" + scene_snapshot,
    )
    original_script_section = wrap_injection_section(
        "原始剧本依据",
        "[Original Script Grounding]\n" + original_script_grounding_block,
    )
    scene_subject_seeds_section = wrap_injection_section(
        "场景Subject种子",
        "[Current Scene Subject Seeds]\n" + scene_subject_seeds_block,
    )
    user_supplement_section = wrap_injection_section(
        "用户补充要求",
        "[User Supplement Requirements]\n" + user_requirements,
    )

    user_prompt = (
        f"{wrap_injection_section('项目信息', project_context_block)}\n\n"
        f"Source Scene Database ID: {db_scene.id}\n\n"
        f"{current_scene_section}\n\n"
        f"{original_script_section}\n\n"
        f"{scene_subject_seeds_section}\n\n"
        f"{existing_subjects_block}\n\n"
        f"{user_supplement_section}\n\n"
        "Task Instructions:\n"
        "- Use Project Context + Current Scene + Original Script Grounding + Current Scene Subject Seeds + System-level Subjects Inventory together.\n"
        "- Original Script Grounding is the primary truth source for checking whether the current scene is missing characters, missing key actions, missing location anchors, or has major core scene info / visual-guidance errors.\n"
        "- You may ignore minor wording differences that do not affect plot understanding or visual staging.\n"
        "- Follow scene_analysis extraction principles for characters / props / environments / covers.\n"
        "- Environment Name / Linked Characters / Key Props with two or more names MUST use the Chinese comma ， only; do not list them with /, ／, |, 、, or ASCII commas.\n"
        "- scene_analysis.txt is the final authority for subject/entity prompt rules; interpret scene_regenerate.txt and runtime instructions so they stay aligned with scene_analysis.txt.\n"
        "- Follow the full Chinese subject-sync rules in scene_regenerate.txt; if this runtime summary is shorter, the file rules still apply in full.\n"
        "- Prioritize User Supplement Requirements over the old scene wording when deciding what is missing.\n"
        f"{mode_specific_task_lines}"
        "- Treat System-level Subjects Inventory as authoritative dependency baselines already available in project DB.\n"
        "- Existing entities are immutable references: MUST NOT be rewritten, renamed, redefined, or replaced.\n"
        "- Reuse subject_ref tokens and keep anchor semantics consistent for recognition continuity.\n"
        "- They can be referenced/reused directly, but MUST NOT be regenerated as new entities.\n"
        "- MUST supplement complete missing subjects required by the current scene from scene content + user requirements, and return JSON with keys: characters, props, environments, covers.\n"
        "- Subject extraction MUST NOT depend on whether the subject already has an image or image_url. Even subjects with no image asset yet MUST still be extracted and returned when they are required by the scene.\n"
        "- Every returned subject item must include import-usable names and prompt: name + name_en + generation_prompt_cn are mandatory content fields; description_cn must be \"\". Missing image assets are allowed; missing names/prompts are not.\n"
        "- Hidden required entities must be completed when the action semantics require them; do not omit source containers, receivers, or scene-required support objects merely because they were implicit in the text.\n"
        "- Keep scene-visible concrete object coverage explicit; if a table, cup, door, window, lamp, phone, keyboard, or similar object matters to the scene, account for it specifically rather than replacing it with a vague category label.\n"
        "- Never combine two readable wardrobe or identity states into one character JSON item.\n"
        "- Clothing hint recognition is mandatory: touching, adjusting, lifting, fastening, or straightening a distinctive garment/accessory counts as evidence for that outfit state and may require a separate character entity.\n"
        "- Preserve the project language rules from the prompt file; do not convert visible language content to English unless the project language actually requires English.\n"
        "- Character prompts must remain full-body with shoes visible.\n"
        "- Environment prompts must stay no-human and clean-plate: no OTS shoulder wording, no human residue, no role labels, and no CHAR references.\n"
        "- SUBJECTS_JSON must contain ONLY missing/new entities that are not already listed in System-level Subjects Inventory.\n"
        "- Keep existing subject names stable; do not duplicate existing names in SUBJECTS_JSON.\n"
        "- If no missing entity exists for a category, return an empty array for that category.\n\n"
        "- Output must be parser-safe and directly importable: no explanations, no bullets outside the requested structure, no code fences, no metadata wrapper objects.\n"
        "- SUBJECTS_JSON top-level keys must be exactly characters, props, environments, covers, and all keys must always exist.\n"
        "- Each entity item may use only the prompt-defined import fields; if an identifier is included, only subject_no may be added as an extra import field.\n"
        "- Missing optional strings must use empty string, missing arrays must use empty array, and null/undefined are forbidden.\n\n"
        "Required Output Format:\n"
        f"{mode_specific_output_line}"
        "2) SUBJECTS_JSON: one valid JSON object only, with complete import-ready fields (same semantics as system subjects import):\n"
        "{\n"
        "  \"characters\": [{\"name\": \"...\", \"name_en\": \"...\", \"description_cn\": \"\", \"gender\": \"...\", \"role\": \"...\", \"archetype\": \"...\", \"appearance_cn\": \"...\", \"clothing\": \"...\", \"action_characteristics\": \"...\", \"generation_prompt_cn\": \"...\", \"generation_prompt_en\": \"...\", \"negative_prompt_en\": \"...\", \"anchor_description\": \"...\", \"visual_dependencies\": [], \"dependency_strategy\": {\"type\": \"...\", \"logic\": \"...\"}}],\n"
        "  \"props\": [{\"name\": \"...\", \"name_en\": \"...\", \"description_cn\": \"\", \"generation_prompt_cn\": \"...\", \"generation_prompt_en\": \"...\", \"negative_prompt_en\": \"...\", \"anchor_description\": \"...\", \"visual_dependencies\": [], \"dependency_strategy\": {\"type\": \"...\", \"logic\": \"...\"}}],\n"
        "  \"environments\": [{\"name\": \"...\", \"name_en\": \"...\", \"atmosphere\": \"...\", \"visual_params\": \"...\", \"description_cn\": \"\", \"generation_prompt_cn\": \"...\", \"generation_prompt_en\": \"...\", \"negative_prompt_en\": \"...\", \"anchor_description\": \"...\", \"visual_dependencies\": [], \"dependency_strategy\": {\"type\": \"...\", \"logic\": \"...\"}}]\n"
        "}\n"
        "Image/image_url fields are NOT required for extraction and may be omitted. Name and generation_prompt_cn are mandatory for each entity item; description_cn must be empty string. Missing other optional fields should use empty string / empty array / empty object.\n"
        "No prose outside these two parts."
    )

    logger.info(
        "[regenerate_scene] prompt injection markers scene_id=%s has_existing_block_in_user_prompt=%s has_existing_guard_in_system_prompt=%s",
        scene_id,
        "System-level Subjects Inventory" in user_prompt,
        "[Existing Entity Reuse Guard - High Priority]" in system_instruction,
    )

    current_user_id = current_user.id
    episode_id = episode.id
    project_id = project.id

    old_scene_no = str(db_scene.scene_no or db_scene.id)
    fallback_original_script = str(db_scene.original_script_text or "").strip()
    fallback_scene_name = db_scene.scene_name
    fallback_duration = db_scene.equivalent_duration
    fallback_core_info = db_scene.core_scene_info
    fallback_env_name = db_scene.environment_name
    fallback_linked_chars = db_scene.linked_characters
    fallback_key_props = db_scene.key_props

    llm_config = agent_service.get_active_llm_config(current_user_id)
    llm_config = _inject_project_creativity_temperature(
        llm_config,
        project.global_info,
        context="regenerate_scene",
    )
    provider = llm_config.get("provider") if llm_config else None
    model = llm_config.get("model") if llm_config else None
    billing_service.check_balance(db, current_user_id, "llm_chat", provider, model)

    _release_db_connection(db, "regenerate_scene_llm_call")
    resp = await llm_service.generate_content_with_fallback(user_prompt, system_instruction, llm_config)
    raw = str((resp or {}).get("content") or "").strip()
    if not raw:
        raise HTTPException(status_code=502, detail="LLM returned empty content")

    cleaned = sanitize_llm_markdown_output(raw)
    parsed_rows = _parse_scene_rows_from_markdown(cleaned)
    if not parsed_rows and not entity_only_mode:
        raise HTTPException(status_code=502, detail="Failed to parse regenerated scene markdown table")

    subjects_json = _extract_subjects_json_from_text(raw)
    if not any(len(subjects_json.get(k) or []) > 0 for k in ("characters", "props", "environments", "covers", "posters")):
        subjects_json = _extract_subjects_json_from_text(cleaned)

    parsed_rows = parsed_rows[:safe_max_scenes]

    created_scenes: List[Scene] = []
    try:
        if entity_only_mode:
            preferred_row = parsed_rows[0] if parsed_rows else {}
            if not isinstance(preferred_row, dict):
                preferred_row = {}

            db_scene = db.query(Scene).filter(Scene.id == scene_id).first()
            if db_scene:
                db_scene.scene_name = str(preferred_row.get("scene_name") or "").strip() or fallback_scene_name
                db_scene.original_script_text = str(preferred_row.get("original_script_text") or "").strip() or fallback_original_script
                db_scene.equivalent_duration = str(preferred_row.get("equivalent_duration") or "").strip() or fallback_duration
                db_scene.core_scene_info = str(preferred_row.get("core_scene_info") or "").strip() or fallback_core_info
                db_scene.environment_name = str(preferred_row.get("environment_name") or "").strip() or fallback_env_name
                db_scene.linked_characters = str(preferred_row.get("linked_characters") or "").strip() or fallback_linked_chars
                db_scene.key_props = str(preferred_row.get("key_props") or "").strip() or fallback_key_props
    
                db.add(db_scene)
                db.commit()
                created_scenes = [db_scene]
        else:
            _soft_delete_scenes(db, scene_id=scene_id)

            total_new = len(parsed_rows)
            for idx, row in enumerate(parsed_rows, start=1):
                if total_new > 1:
                    next_scene_no = f"{old_scene_no}.{idx}"
                else:
                    next_scene_no = str(row.get("scene_no") or "").strip() or old_scene_no

                original_script_text = str(row.get("original_script_text") or "").strip() or fallback_original_script
                if not original_script_text:
                    original_script_text = f"Scene regenerated from {old_scene_no}"

                new_scene = Scene(
                    episode_id=episode_id,
                    scene_no=next_scene_no,
                    scene_name=str(row.get("scene_name") or "").strip() or fallback_scene_name,
                    original_script_text=original_script_text,
                    equivalent_duration=str(row.get("equivalent_duration") or "").strip() or fallback_duration,
                    core_scene_info=str(row.get("core_scene_info") or "").strip() or fallback_core_info,
                    environment_name=str(row.get("environment_name") or "").strip() or fallback_env_name,
                    linked_characters=str(row.get("linked_characters") or "").strip() or fallback_linked_chars,
                    key_props=str(row.get("key_props") or "").strip() or fallback_key_props,
                )
                db.add(new_scene)
                created_scenes.append(new_scene)

            db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to replace scene: {str(e)}")

    for item in created_scenes:
        db.refresh(item)

    usage = (resp or {}).get("usage") if isinstance(resp, dict) else None
    details: Dict[str, Any] = {
        "item": "scene_regenerate",
        "source_scene_id": scene_id,
        "generated_scene_count": len(created_scenes),
    }
    if isinstance(usage, dict):
        details.update(usage)
        if "prompt_tokens" in details and "input_tokens" not in details:
            details["input_tokens"] = details.get("prompt_tokens", 0)
        if "completion_tokens" in details and "output_tokens" not in details:
            details["output_tokens"] = details.get("completion_tokens", 0)
    billing_service.deduct_credits(db, current_user_id, "llm_chat", provider, model, details)

    return {
        "replaced_scene_id": scene_id,
        "episode_id": episode_id,
        "project_id": project_id,
        "entity_only_mode": entity_only_mode,
        "scene_changes_applied": not entity_only_mode,
        "generated_scene_count": len(created_scenes),
        "raw_markdown": cleaned,
        "subjects_json": subjects_json,
        "subjects_json_count": {
            "characters": len(subjects_json.get("characters") or []),
            "props": len(subjects_json.get("props") or []),
            "environments": len(subjects_json.get("environments") or []),
            "covers": len(subjects_json.get("covers") or []),
            "posters": len(subjects_json.get("posters") or []),
        },
        "scenes": [
            {
                "id": s.id,
                "scene_no": s.scene_no,
                "scene_name": s.scene_name,
                "equivalent_duration": s.equivalent_duration,
                "core_scene_info": s.core_scene_info,
                "original_script_text": s.original_script_text,
                "environment_name": s.environment_name,
                "linked_characters": s.linked_characters,
                "key_props": s.key_props,
            }
            for s in created_scenes
        ],
    }

