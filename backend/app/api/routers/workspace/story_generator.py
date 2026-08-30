# -*- coding: utf-8 -*-
"""Story-generator / market-intel workspace section routes."""
from __future__ import annotations

from app.api.routers.workspace import shared as _shared

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

@router.post("/projects/{project_id}/story_generator/global", response_model=ProjectOut)
async def generate_project_story_dna_global(
    project_id: int,
    req: "StoryGeneratorRequest",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    if async_mode == "1":
        tid = _submit_async(generate_project_story_dna_global, user_id=current_user.id,
                            kind="story_dna_global", project_id=project_id, req=req, async_mode="0")
        return JSONResponse({"task_id": tid, "async": True})
    project = _require_project_access(db, project_id, current_user)

    gi_existing = dict(project.global_info or {})

    # Force global mode for this endpoint
    episodes_count = req.episodes_count
    if not episodes_count or int(episodes_count) <= 0:
        raise HTTPException(status_code=400, detail="episodes_count is required")

    # Prefer request payload (latest UI state), fall back to saved global_info.
    script_title = (req.script_title or gi_existing.get("script_title") or "").strip()
    project_type = (getattr(req, "type", None) or gi_existing.get("type") or "").strip()
    language = (req.language or gi_existing.get("language") or "").strip()
    base_positioning = (req.base_positioning or gi_existing.get("base_positioning") or "").strip()
    global_style = (req.Global_Style or gi_existing.get("Global_Style") or gi_existing.get("global_style") or "").strip()
    generator_kind = _normalize_generator_kind(req.generator_kind) or "story"

    if generator_kind == "promo":
        prompt_filename = "promo_generator_global.txt"
    else:
        prompt_filename = "master_story_architect.md"

    try:
        sys_prompt = _resolve_prompt_text(prompt_filename)
    except FileNotFoundError:
        logger.error("Story generator prompt not found: %s", prompt_filename)
        raise HTTPException(status_code=404, detail=f"Prompt file '{prompt_filename}' not found.")

    user_id = int(current_user.id)
    project_title = str(project.title or "").strip()
    literal_input_title = script_title or project_title

    title_policy_block = (
        "Script Title Generation Policy (Hard Constraint):\n"
        f"- Project title (reference only, do NOT copy literally): {project_title}\n"
        f"- Input script title hint (reference only): {script_title or '(empty)'}\n"
        "- You MUST create a story-fitting script title based on genre, conflict, and tone.\n"
        "- The final Script Title MUST NOT be identical to the project title or the input hint above.\n"
        "- Avoid generic placeholders like 'Untitled', 'Project Title', or 'Episode N'.\n"
        "- Inside [STORY_DNA_OUTPUT_START]…[STORY_DNA_OUTPUT_END], output a dedicated machine-parseable line: [SCRIPT_TITLE:{title}]\n"
        "- Then also keep the human label: Script Title:{title} · Type:… · Language:…\n"
        "- Do NOT append production-format words (实拍/真人剧/Live Action/Type labels) to the title.\n"
        "- Truncatable markers (hard): wrap Part 1 in [STORY_DNA_THINKING_START]…[STORY_DNA_THINKING_END]; "
        "wrap §0–§9 formal Story DNA in [STORY_DNA_OUTPUT_START]…[STORY_DNA_OUTPUT_END]. "
        "Do not echo the INPUT block into OUTPUT.\n\n"
    )

    user_prompt = wrap_story_dna_input_block(
        f"Mode: global\n"
        f"Project Title: {project_title}\n"
        f"Note: Project Overview / Basic Information and Character Canon may be empty; do not fail, infer sensible defaults and continue.\n"
        f"\n"
        f"{title_policy_block}"
        f"[Project Overview / Basic Information]\n"
        f"Script Title: {script_title}\n"
        f"Type: {project_type}\n"
        f"Language: {language}\n"
        f"Base Positioning: {base_positioning}\n"
        f"Global Style: {global_style}\n"
        f"\n"
        f"Episodes Count: {int(episodes_count)}\n"
        f"Episode Duration (minutes): {_resolve_episode_duration_minutes(getattr(req, 'episode_duration_minutes', None))}\n"
        f"Script Mode: {(getattr(req, 'script_mode', None) or '').strip()}\n"
        f"Target Audience: {(getattr(req, 'target_audience', None) or '').strip()}\n"
        f"\n"
        f"[Creative Input — Standard Structure (脑洞标准输入)]\n"
        f"I1 Logline / 高概念: {(getattr(req, 'logline', None) or '').strip()}\n"
        f"I2 Theme / 主题与主控思想: {(getattr(req, 'theme', None) or '').strip()}\n"
        f"I3 Core Conflict / 核心矛盾·赌注·Gap: {(getattr(req, 'core_conflict', None) or '').strip()}\n"
        f"I4 World & Background / 世界与背景: {(req.background or '').strip()}\n"
        f"I5 Characters & Relationships / 核心人物: {(getattr(req, 'characters', None) or '').strip()}\n"
        f"I6a Opening & Inciting / 开局与激励: {(req.setup or '').strip()}\n"
        f"I6b Mid Arc Escalation / 中段升级: {(req.development or '').strip()}\n"
        f"I6c Turning Points / 转折与中点: {(req.turning_points or '').strip()}\n"
        f"I7a Climax & Must-Have Scenes / 高潮与名场面: {(req.climax or '').strip()}\n"
        f"I7b Ending & Resolution / 结局与收尾: {(req.resolution or '').strip()}\n"
        f"I8a Core Suspense / 核心悬念: {(req.suspense or '').strip()}\n"
        f"I8b Foreshadowing & Must-Keep / 伏笔与必留元素: {(req.foreshadowing or '').strip()}\n"
        f"I9 Raw Fragments / 自由脑洞补充: {(req.extra_notes or '').strip()}\n"
        f"I10 Classic Framework / 经典作品框架: {(getattr(req, 'classic_framework', None) or '').strip()}\n"
        f"Wild Creative Notes (天马行空原文，保留溯源): {(getattr(req, 'wild_creative_notes', None) or '').strip()}\n"
    )

    llm_config = _resolve_story_generator_script_analysis_llm_config(
        db,
        user_id,
        function_name=(getattr(req, "function_name", None) or "script_analysis"),
        system_api_id=getattr(req, "system_api_id", None),
        context="generate_project_story_dna_global",
        project_global_info=project.global_info,
    )
    if not llm_config or not (llm_config.get("api_key") or "").strip():
        raise HTTPException(status_code=400, detail="No valid LLM API key configured in active settings")
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
            user_id,
            "llm_chat",
            provider,
            model,
            {
                "item": "story_generator_global",
                "estimation_method": "prompt_tokens_ratio",
                "estimated_output_ratio": billing_service.RESERVE_OUTPUT_RATIO,
                "input_tokens": est.get("input_tokens", 0),
                "output_tokens": est.get("output_tokens", 0),
                "total_tokens": est.get("total_tokens", 0),
            },
        )
    else:
        billing_service.check_balance(db, current_user.id, "llm_chat", provider, model)

    _release_db_connection(db, "generate_project_story_dna_global_llm_call")

    try:
        # Story DNA: do not strict-retry on H1/marker shape — recover markers on persist instead.
        generated_payload = await generate_markdown_with_retry(
            user_prompt=user_prompt,
            sys_prompt=sys_prompt,
            llm_config=llm_config,
            strict_markdown=False,
            require_h1=False,
            return_meta=True,
        )
    except Exception as e:
        if reservation_tx:
            billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), str(e))
        raise

    generated_md = str((generated_payload or {}).get("content") or "").strip()
    usage = (generated_payload or {}).get("usage") if isinstance(generated_payload, dict) else {}
    if not generated_md:
        raise HTTPException(status_code=500, detail="LLM returned empty content")

    dna_view = extract_story_dna_output_for_validation(generated_md)
    generated_md = normalize_story_dna_markdown_for_persist(generated_md)
    logger.info(
        "[generate_project_story_dna_global] story_dna_markers had_output=%s had_thinking=%s "
        "truncated_thinking=%s persist_len=%s output_len=%s thinking_len=%s",
        bool(dna_view.get("had_output_markers")),
        bool(dna_view.get("had_thinking_markers")),
        bool(dna_view.get("truncated_thinking")),
        len(generated_md),
        len(str(dna_view.get("content") or "")),
        len(str(dna_view.get("thinking") or "")),
    )

    generated_script_title = _strip_stacked_production_title_suffixes(
        _extract_script_title_from_story_dna_markdown(
            str(dna_view.get("content") or generated_md)
        )
    )
    if not generated_script_title:
        generated_script_title = _build_non_literal_script_title(
            seed_title=literal_input_title,
            project_type=project_type,
            global_style=global_style,
            base_positioning=base_positioning,
        )
    literal_input_title_clean = _strip_stacked_production_title_suffixes(literal_input_title)
    if _normalize_title_for_compare(generated_script_title) == _normalize_title_for_compare(literal_input_title_clean):
        generated_script_title = _build_non_literal_script_title(
            seed_title=generated_script_title,
            project_type=project_type,
            global_style=global_style,
            base_positioning=base_positioning,
        )
    generated_script_title = _strip_stacked_production_title_suffixes(generated_script_title)

    if not usage:
        usage = billing_service.estimate_input_output_tokens_from_messages(
            [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": generated_md},
            ],
            output_ratio=1.0,
        )
    settle_details = {
        "item": "promo_generator_global" if generator_kind == "promo" else "story_generator_global",
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
    settle_details["input_tokens"] = settle_details["prompt_tokens"]
    settle_details["output_tokens"] = settle_details["completion_tokens"]
    _apply_llm_routing_to_billing_details(settle_details, generated_payload)

    if reservation_tx:
        billing_service.settle_reservation(db, _reservation_tx_id(reservation_tx), settle_details)
    else:
        billing_service.deduct_credits(db, current_user.id, "llm_chat", provider, model, settle_details)

    # Persist both output and the inputs that produced it.
    # This ensures a successful generation is durable across refresh even
    # if the user doesn't click the separate "Save Changes" button.
    try:
        story_input = req.model_dump()
    except AttributeError:
        story_input = req.dict()
    story_input["mode"] = "global"
    generator_kind = _normalize_generator_kind(story_input.get("generator_kind") or req.generator_kind) or "story"
    story_input["generator_kind"] = generator_kind
    generator_kind = _normalize_generator_kind(story_input.get("generator_kind") or req.generator_kind) or "story"
    story_input["generator_kind"] = generator_kind
    story_input["generator_kind"] = generator_kind

    now_iso = now_bj_iso()
    project = db.merge(project)
    gi = dict(project.global_info or {})
    if generator_kind == "promo":
        gi["promo_generator_input"] = story_input
        gi["promo_generator_input_updated_at"] = now_iso
        gi["promo_dna_global_md"] = generated_md
        gi["promo_dna_global_updated_at"] = now_iso
    else:
        gi["story_generator_global_input"] = story_input
        gi["story_dna_global_md"] = generated_md
        gi["story_dna_global_updated_at"] = now_iso
    if generated_script_title:
        gi["script_title"] = generated_script_title
        basic_info = gi.get("basic_information") if isinstance(gi.get("basic_information"), dict) else {}
        basic_info = dict(basic_info)
        basic_info["script_title"] = generated_script_title
        gi["basic_information"] = basic_info
    project.global_info = gi

    db.add(project)
    db.commit()
    db.refresh(project)

    # Populate response aliases to match other endpoints
    try:
        project.cover_image = get_project_cover_image(db, project.id)
    except Exception:
        project.cover_image = None
    try:
        project.aspectRatio = project.global_info.get('aspectRatio') if project.global_info else None
    except Exception:
        project.aspectRatio = None
    return project


@router.put("/projects/{project_id}/story_generator/global/input", response_model=ProjectOut)
def save_project_story_generator_global_input(
    project_id: int,
    req: "StoryGeneratorRequest",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Persist Story Generator (Global/Project) draft inputs without calling the LLM."""
    project = _require_project_access(db, project_id, current_user)

    try:
        story_input = req.model_dump()
    except AttributeError:
        story_input = req.dict()
    story_input["mode"] = "global"
    generator_kind = _normalize_generator_kind(story_input.get("generator_kind") or req.generator_kind) or "story"
    story_input["generator_kind"] = generator_kind

    now_iso = now_bj_iso()
    gi = dict(project.global_info or {})
    if generator_kind == "promo":
        gi["promo_generator_input"] = story_input
        gi["promo_generator_input_updated_at"] = now_iso
    else:
        gi["story_generator_global_input"] = story_input
        gi["story_generator_global_input_updated_at"] = now_iso
    project.global_info = gi

    db.add(project)
    db.commit()
    db.refresh(project)

    # Populate response aliases to match other endpoints
    try:
        project.cover_image = get_project_cover_image(db, project.id)
    except Exception:
        project.cover_image = None
    try:
        project.aspectRatio = project.global_info.get('aspectRatio') if project.global_info else None
    except Exception:
        project.aspectRatio = None
    return project


class StoryGeneratorGlobalImportRequest(BaseModel):
    project_overview: Optional[Dict[str, Any]] = None
    basic_information: Optional[Dict[str, Any]] = None
    character_canon_project: Optional[Dict[str, Any]] = None
    story_generator_global_project: Optional[Dict[str, Any]] = None
    story_generator_global_structured: Optional[Dict[str, Any]] = None
    story_generator_global_input: Optional[Dict[str, Any]] = None
    story_dna_global_md: Optional[str] = None


@router.get("/projects/{project_id}/story_generator/global/export", response_model=Dict[str, Any])
def export_project_story_generator_global_package(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _require_project_access(db, project_id, current_user)

    gi = dict(project.global_info or {})
    basic_info_nested = gi.get("basic_information") if isinstance(gi.get("basic_information"), dict) else {}
    e_global_info = gi.get("e_global_info") if isinstance(gi.get("e_global_info"), dict) else {}
    story_input = gi.get("story_generator_global_input") if isinstance(gi.get("story_generator_global_input"), dict) else {}

    def _pick_text(*values):
        for v in values:
            if v is None:
                continue
            s = str(v).strip()
            if s:
                return s
        return ""

    def _pick_dict(*values):
        for v in values:
            if isinstance(v, dict) and len(v) > 0:
                return v
        return {}

    def _pick_list(*values):
        for v in values:
            if isinstance(v, list) and len(v) > 0:
                return v
        return []

    basic_information = {
        "script_title": _pick_text(
            gi.get("script_title"),
            basic_info_nested.get("script_title"),
            e_global_info.get("script_title"),
            story_input.get("script_title"),
            _extract_script_title_from_story_dna_markdown(gi.get("story_dna_global_md") or ""),
        ),
        "series_episode": _pick_text(gi.get("series_episode"), basic_info_nested.get("series_episode"), e_global_info.get("series_episode")),
        "type": _pick_text(gi.get("type"), basic_info_nested.get("type"), e_global_info.get("type"), story_input.get("type")),
        "country_region": _pick_text(gi.get("country_region"), basic_info_nested.get("country_region"), e_global_info.get("country_region"), story_input.get("country_region")),
        "language": _pick_text(gi.get("language"), basic_info_nested.get("language"), e_global_info.get("language"), story_input.get("language")),
        "base_positioning": _pick_text(gi.get("base_positioning"), basic_info_nested.get("base_positioning"), e_global_info.get("base_positioning"), story_input.get("base_positioning")),
        "Global_Style": _pick_text(gi.get("Global_Style"), gi.get("global_style"), basic_info_nested.get("Global_Style"), e_global_info.get("Global_Style"), story_input.get("Global_Style")),
        "tech_params": _pick_dict(gi.get("tech_params"), basic_info_nested.get("tech_params"), e_global_info.get("tech_params")),
        "tone": _pick_text(gi.get("tone"), basic_info_nested.get("tone"), e_global_info.get("tone")),
        "lighting": _pick_text(gi.get("lighting"), basic_info_nested.get("lighting"), e_global_info.get("lighting")),
        "borrowed_films": _pick_list(gi.get("borrowed_films"), basic_info_nested.get("borrowed_films"), e_global_info.get("borrowed_films")),
        "character_relationships": _pick_text(gi.get("character_relationships"), basic_info_nested.get("character_relationships")),
        "notes": _pick_text(gi.get("notes"), basic_info_nested.get("notes"), e_global_info.get("notes")),
    }

    character_canon_project = {
        "character_canon_input": gi.get("character_canon_input") or {},
        "character_canon_md": gi.get("character_canon_md") or "",
        "character_profiles": gi.get("character_profiles") or [],
        "character_canon_tag_categories": gi.get("character_canon_tag_categories") or [],
        "character_canon_identity_categories": gi.get("character_canon_identity_categories") or [],
    }

    def _extract_between(text: str, start_pat: str, end_pat: str) -> str:
        try:
            pattern = rf"{start_pat}(.*?){end_pat}"
            m = re.search(pattern, text, flags=re.S)
            return (m.group(1).strip() if m else "")
        except Exception:
            return ""

    def _extract_story_structured(md: str) -> Dict[str, Any]:
        raw = str(md or "")
        if not raw.strip():
            return {}

        def _first_non_empty(*pairs: tuple[str, str]) -> str:
            for start_pat, end_pat in pairs:
                block = _extract_between(raw, start_pat, end_pat)
                if block:
                    return block
            return ""

        setup_block = _extract_between(raw, r"###\s*A\)", r"###\s*B\)")
        development_block = _first_non_empty(
            (r"###\s*B\)\s*发展", r"###\s*C\)\s*转折"),
            (r"###\s*B\)", r"###\s*C\)"),
        )
        turning_block = _first_non_empty(
            (r"###\s*C\)\s*转折", r"###\s*D\)\s*高潮"),
            (r"###\s*C\)", r"###\s*D\)"),
        )
        climax_block = _first_non_empty(
            (r"###\s*D\)\s*高潮", r"###\s*E\)\s*定局"),
            (r"###\s*D\)", r"###\s*E\)"),
        )
        resolution_block = _first_non_empty(
            (r"###\s*E\)\s*定局", r"##\s*5\)\s*[^\n]*悬念"),
            (r"###\s*E\)", r"##\s*6\)"),
            (r"###\s*E\)", r"##\s*5\)\s*[^\n]*悬念"),
        )
        suspense_block = _first_non_empty(
            (r"##\s*6\)\s*[^\n]*悬念", r"##\s*7\)"),
            (r"##\s*5\)\s*[^\n]*悬念", r"##\s*6\)"),
            (r"##\s*5\)", r"##\s*6\)"),
        )
        foreshadowing_block = _first_non_empty(
            (r"##\s*7\)\s*[^\n]*伏笔", r"##\s*8\)"),
            (r"##\s*6\)\s*[^\n]*伏笔", r"##\s*7\)"),
            (r"##\s*6\)", r"##\s*7\)"),
        )
        background_block = _first_non_empty(
            (r"##\s*2\)\s*[^\n]*核心设定", r"##\s*3\)"),
            (r"##\s*1\)", r"##\s*2\)"),
        )

        hook = ""
        inciting = ""
        point_of_no_return = ""
        hook_keys = ("开场钩子", "开场画面", "Opening Image")
        inciting_keys = ("触发事件", "激励事件", "Inciting Incident", "催化剂", "Catalyst")
        ponr_keys = ("不可回头", "立场选择", "越过边界", "Break into Two")
        for line in (setup_block or "").splitlines():
            s = line.strip()
            if (not hook) and any(k in s for k in hook_keys):
                hook = s
            elif (not inciting) and any(k in s for k in inciting_keys):
                inciting = s
            elif (not point_of_no_return) and any(k in s for k in ponr_keys):
                point_of_no_return = s

        return {
            "script_title": _extract_script_title_from_story_dna_markdown(raw),
            "background": background_block,
            "setup": setup_block,
            "hook": hook,
            "inciting_incident": inciting,
            "point_of_no_return": point_of_no_return,
            "development": development_block,
            "turning_points": turning_block,
            "climax": climax_block,
            "resolution": resolution_block,
            "suspense": suspense_block,
            "foreshadowing": foreshadowing_block,
        }

    story_structured = _extract_story_structured(gi.get("story_dna_global_md") or "")

    def _coalesce_story_input(stored_input: Dict[str, Any], structured: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(stored_input or {})
        for key in ["background", "setup", "development", "turning_points", "climax", "resolution", "suspense", "foreshadowing"]:
            current = str(merged.get(key) or "").strip()
            if not current:
                merged[key] = structured.get(key) or ""
        return merged

    story_input_export = _coalesce_story_input(story_input, story_structured)

    # Export complete Story Generator (Global/Project) related payload,
    # including draft inputs, outputs and metadata timestamps.
    story_generator_global_project = {
        key: value
        for key, value in gi.items()
        if (
            str(key).startswith("story_generator_global")
            or str(key).startswith("story_dna_global")
        )
    }

    return {
        "schema_version": 1,
        "export_type": "story_generator_global_project",
        "exported_at": now_bj_iso(),
        "source_project": {
            "id": project.id,
            "title": project.title,
        },
        "project_overview": {
            "script_title": basic_information.get("script_title") or "",
            "type": basic_information.get("type") or "",
            "language": basic_information.get("language") or "",
            "base_positioning": basic_information.get("base_positioning") or "",
            "Global_Style": basic_information.get("Global_Style") or "",
        },
        "basic_information": basic_information,
        "character_canon_project": character_canon_project,
        "story_generator_global_project": story_generator_global_project,
        "story_generator_global_structured": story_structured,
        "story_generator_global_input": story_input_export,
        "story_dna_global_md": gi.get("story_dna_global_md") or "",
    }


@router.put("/projects/{project_id}/story_generator/global/import", response_model=ProjectOut)
def import_project_story_generator_global_package(
    project_id: int,
    req: StoryGeneratorGlobalImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _require_project_access(db, project_id, current_user)

    now_iso = now_bj_iso()
    gi = dict(project.global_info or {})

    basic_information = req.basic_information or req.project_overview or {}
    if isinstance(basic_information, dict):
        text_fields = [
            "script_title",
            "series_episode",
            "type",
            "language",
            "base_positioning",
            "Global_Style",
            "tone",
            "lighting",
            "character_relationships",
            "notes",
        ]
        for key in text_fields:
            if key in basic_information:
                val = basic_information.get(key)
                gi[key] = "" if val is None else str(val)

        if "tech_params" in basic_information and isinstance(basic_information.get("tech_params"), dict):
            gi["tech_params"] = basic_information.get("tech_params") or {}

        if "borrowed_films" in basic_information:
            borrowed = basic_information.get("borrowed_films")
            gi["borrowed_films"] = borrowed if isinstance(borrowed, list) else []

    canon_payload = req.character_canon_project or {}
    if isinstance(canon_payload, dict):
        if "character_canon_input" in canon_payload and isinstance(canon_payload.get("character_canon_input"), dict):
            gi["character_canon_input"] = canon_payload.get("character_canon_input") or {}
            gi["character_canon_input_updated_at"] = now_iso

        if "character_canon_md" in canon_payload:
            gi["character_canon_md"] = canon_payload.get("character_canon_md") or ""

        if "character_profiles" in canon_payload:
            profiles = canon_payload.get("character_profiles")
            gi["character_profiles"] = profiles if isinstance(profiles, list) else []
            gi["character_profiles_updated_at"] = now_iso

        if "character_canon_tag_categories" in canon_payload:
            tags = canon_payload.get("character_canon_tag_categories")
            gi["character_canon_tag_categories"] = tags if isinstance(tags, list) else []

        if "character_canon_identity_categories" in canon_payload:
            identities = canon_payload.get("character_canon_identity_categories")
            gi["character_canon_identity_categories"] = identities if isinstance(identities, list) else []

    # Full Story Generator (Global/Project) package import (preferred path)
    # Accept all recognized story-global keys and merge into global_info.
    full_story_pkg = req.story_generator_global_project or {}
    if isinstance(full_story_pkg, dict):
        for key, value in full_story_pkg.items():
            k = str(key)
            if (
                k.startswith("story_generator_global")
                or k.startswith("story_dna_global")
            ):
                gi[k] = value

    imported_input = req.story_generator_global_input or {}
    if isinstance(imported_input, dict) and len(imported_input) > 0:
        normalized_input = dict(imported_input)
        normalized_input["mode"] = "global"
        if "episodes_count" in normalized_input:
            try:
                normalized_input["episodes_count"] = int(normalized_input.get("episodes_count") or 0)
            except Exception:
                normalized_input["episodes_count"] = 0
        if "episode_duration_minutes" in normalized_input:
            normalized_input["episode_duration_minutes"] = _resolve_episode_duration_minutes(
                normalized_input.get("episode_duration_minutes")
            )

        structured_input = req.story_generator_global_structured or {}
        if isinstance(structured_input, dict):
            for key in ["background", "setup", "development", "turning_points", "climax", "resolution", "suspense", "foreshadowing"]:
                if not str(normalized_input.get(key) or "").strip() and str(structured_input.get(key) or "").strip():
                    normalized_input[key] = structured_input.get(key)

        gi["story_generator_global_input"] = normalized_input
        gi["story_generator_global_input_updated_at"] = now_iso

    if req.story_dna_global_md is not None:
        gi["story_dna_global_md"] = req.story_dna_global_md or ""
        gi["story_dna_global_updated_at"] = now_iso


    project.global_info = gi
    db.add(project)
    db.commit()
    db.refresh(project)

    # Populate response aliases to match other endpoints
    try:
        project.cover_image = get_project_cover_image(db, project.id)
    except Exception:
        project.cover_image = None
    try:
        project.aspectRatio = project.global_info.get('aspectRatio') if project.global_info else None
    except Exception:
        project.aspectRatio = None
    return project


class AnalyzeNovelRequest(BaseModel):
    novel_text: str
    function_name: Optional[str] = None
    system_api_id: Optional[int] = None


class StructureCreativeInputRequest(BaseModel):
    creative_text: str
    script_mode: Optional[str] = None
    target_audience: Optional[str] = None
    type: Optional[str] = None
    language: Optional[str] = None
    function_name: Optional[str] = None
    system_api_id: Optional[int] = None



# Story-generator LLM helpers (canonical: app.services.story_generator_llm).
from app.services.story_generator_llm import (  # noqa: E402,F401
    _loads_json5_if_available,
    _CREATIVE_INPUT_STRUCTURE_KEYS,
    _sanitize_llm_json_text,
    _extract_llm_json_object_from_text,
    _normalize_llm_json_object,
    _normalize_llm_json_object_with_repair,
    _normalize_story_field_map,
    _run_structure_llm_call,
    _prepare_episode_script_reference_block,
)

@router.post("/projects/{project_id}/story_generator/structure_creative_input", response_model=Dict[str, Any])
async def structure_project_creative_input_to_story_fields(
    project_id: int,
    req: StructureCreativeInputRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    if async_mode == "1":
        tid = _submit_async(
            structure_project_creative_input_to_story_fields,
            user_id=current_user.id,
            kind="structure_creative_input",
            project_id=project_id,
            req=req,
            async_mode="0",
        )
        return JSONResponse({"task_id": tid, "async": True})
    project = _require_project_access(db, project_id, current_user)

    creative_text = (req.creative_text or "").strip()
    if not creative_text:
        raise HTTPException(status_code=400, detail="creative_text is required")

    gi_existing = dict(project.global_info or {})
    user_id = int(current_user.id)
    project_global_info = gi_existing
    project_title_str = str(project.title or "")
    project_type = (getattr(req, "type", None) or gi_existing.get("type") or "").strip()
    language = (getattr(req, "language", None) or gi_existing.get("language") or "").strip()
    script_mode = (getattr(req, "script_mode", None) or "").strip()
    target_audience = (getattr(req, "target_audience", None) or "").strip()

    project_context = (
        f"Project Title: {project_title_str}\n"
        f"Type: {project_type}\n"
        f"Language: {language}\n"
        f"Script Mode: {script_mode}\n"
        f"Target Audience: {target_audience}\n"
    )

    try:
        extract_prompt_template = _resolve_prompt_text("story_generator_structure_extract_key_elements.txt")
    except FileNotFoundError:
        logger.error("Structure extract key elements prompt not found")
        raise HTTPException(
            status_code=404,
            detail="Prompt file 'story_generator_structure_extract_key_elements.txt' not found.",
        )

    try:
        extract_sys_prompt = extract_prompt_template.format(creative_text=creative_text)
    except Exception:
        extract_sys_prompt = extract_prompt_template

    extract_user_prompt = (
        f"{project_context}\n"
        f"Wild Creative Brainstorm:\n{creative_text}\n\n"
        "Extract searchable key elements from the brainstorm, with emphasis on "
        "(1) a MODERN/CONTEMPORARY plot-LOGIC framework (literature / film / TV / game; prefer recent decades, not pre-modern classics as default primary) plus AT LEAST 5 auxiliary works of different dimensions (to avoid copying the primary plot), "
        "and (2) climax moments and iconic scenes."
    )
    extract_raw = await _run_structure_llm_call(
        db=db,
        user_id=user_id,
        project_global_info=project_global_info,
        req=req,
        sys_prompt=extract_sys_prompt,
        user_prompt=extract_user_prompt,
        billing_item="structure_extract_key_elements",
        llm_context="structure_extract_key_elements",
    )
    key_elements = _normalize_llm_json_object(extract_raw, context="structure_extract_key_elements")

    _release_db_connection(db, "structure_creative_input_web_search")
    search_bundle = await collect_creative_structure_search_snippets(key_elements)
    search_context = build_creative_structure_search_user_prompt(
        search_bundle,
        key_elements,
        project_title=project_title_str,
        language=language,
    )

    try:
        sys_prompt_template = _resolve_prompt_text("story_generator_structure_creative_input.txt")
    except FileNotFoundError:
        logger.error("Structure creative input prompt not found: story_generator_structure_creative_input.txt")
        raise HTTPException(
            status_code=404,
            detail="Prompt file 'story_generator_structure_creative_input.txt' not found.",
        )

    try:
        sys_prompt = sys_prompt_template.format(creative_text=creative_text, search_context=search_context)
    except Exception:
        sys_prompt = f"{sys_prompt_template}\n\n{creative_text}\n\n{search_context}"

    user_prompt = (
        f"{project_context}\n"
        f"Wild Creative Brainstorm:\n{creative_text}\n\n"
        "Use the extracted key elements and reference search snippets to structure I1-I10. "
        "I10 must name one primary MODERN/CONTEMPORARY work (literature / film / TV / game; prefer recent decades) as the PLOT-LOGIC framework, "
        "plus AT LEAST 5 auxiliaries (older classics OK only as auxiliaries; each a different dimension) so I6-I8 is not a remake of the primary. "
        "Cross-style transfer is required: keep causal/beat/set-piece logic, "
        "transcode genre/skin (e.g. modern workplace engine → ancient palace drama). Do not default a pre-modern classic as the primary spine. "
        "For each work write reusable logic (core plot, set pieces, VFX function, action, dialogue) and 转译. "
        "Prioritize climax and iconic scenes (I7a) using visual, dialogue, and action reference angles."
    )
    raw = await _run_structure_llm_call(
        db=db,
        user_id=user_id,
        project_global_info=project_global_info,
        req=req,
        sys_prompt=sys_prompt,
        user_prompt=user_prompt,
        billing_item="structure_creative_input",
        llm_context="structure_creative_input",
    )

    structure_llm_config = _resolve_story_generator_script_analysis_llm_config(
        db,
        user_id,
        function_name=(getattr(req, "function_name", None) or "script_analysis"),
        system_api_id=getattr(req, "system_api_id", None),
        context="structure_creative_input",
        project_global_info=project_global_info,
    )
    data = await _normalize_llm_json_object_with_repair(
        raw,
        context="structure_creative_input",
        llm_config=structure_llm_config,
    )
    normalized = _normalize_story_field_map(data, _CREATIVE_INPUT_STRUCTURE_KEYS)
    normalized["prefill_meta"] = {
        "pipeline": "extract_key_elements -> reference_search -> structure_fill",
        "key_elements": key_elements,
        "search_meta": {
            "query_count": len(search_bundle.get("queries") or []),
            "snippet_count": len(search_bundle.get("snippets") or []),
            "instant_note_count": len(search_bundle.get("instant_notes") or []),
            "source_stats": search_bundle.get("source_stats") or {},
        },
    }
    return normalized


class TrendingAiShortDramasRequest(BaseModel):
    month_label: Optional[str] = None
    limit: Optional[int] = 12
    language: Optional[str] = None
    function_name: Optional[str] = None
    system_api_id: Optional[int] = None



# Market intel ops (canonical: app.services.market_intel_ops).
from app.services.market_intel_ops import (  # noqa: E402,F401
    MarketIntelReport,
    _require_market_intel_model,
    _market_intel_report_to_dict,
    _persist_market_intel_report,
    _seed_market_intel_from_global_info,
    _run_ai_short_drama_market_llm,
    _industry_analysis_section_map,
    _build_industry_analysis_markdown,
    _build_trending_dramas_markdown,
)

@router.post("/projects/{project_id}/story_generator/industry_analysis_ai_short_dramas", response_model=Dict[str, Any])
async def fetch_industry_analysis_ai_short_dramas_report(
    project_id: int,
    req: TrendingAiShortDramasRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    if async_mode == "1":
        tid = _submit_async(
            fetch_industry_analysis_ai_short_dramas_report,
            user_id=current_user.id,
            kind="industry_analysis_ai_short_dramas",
            project_id=project_id,
            req=req,
            async_mode="0",
        )
        return JSONResponse({"task_id": tid, "async": True})
    project = _require_project_access(db, project_id, current_user)
    gi_existing = dict(project.global_info or {})
    project_title_str = str(project.title or "")
    language = (req.language or gi_existing.get("language") or "").strip()

    month_label = (req.month_label or current_report_month_label()).strip()
    report_period = current_report_period_label(month_label)

    _release_db_connection(db, "industry_analysis_web_search")
    search_bundle = await collect_industry_analysis_search_snippets(month_label=month_label)
    if not (search_bundle.get("snippets") or search_bundle.get("instant_notes")):
        raise HTTPException(status_code=502, detail="Web search returned no snippets for AI short drama industry analysis")

    try:
        sys_prompt_template = _resolve_prompt_text("story_generator_industry_analysis_ai_short_dramas.txt")
    except FileNotFoundError:
        logger.error("Industry analysis AI short dramas prompt not found")
        raise HTTPException(status_code=404, detail="Prompt file 'story_generator_industry_analysis_ai_short_dramas.txt' not found.")

    search_context = build_industry_analysis_user_prompt(
        search_bundle,
        project_title=project_title_str,
        language=language,
    )
    try:
        sys_prompt = sys_prompt_template.format(search_context=search_context)
    except Exception:
        sys_prompt = f"{sys_prompt_template}\n\n{search_context}"

    user_prompt = (
        f"Compile the {report_period} AI short drama industry analysis from the search snippets below.\n"
        f"Focus on industry-wide trends only; do not rank individual dramas.\n\n"
        f"{search_context}"
    )
    # Reload after web-search release so billing/LLM see an attached project/user.
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    current_user = db.query(User).filter(User.id == int(current_user.id)).first() or current_user

    llm_result = await _run_ai_short_drama_market_llm(
        db=db,
        current_user=current_user,
        project=project,
        req=req,
        sys_prompt=sys_prompt,
        user_prompt=user_prompt,
        billing_item="industry_analysis_ai_short_dramas",
        llm_context="industry_analysis_ai_short_dramas",
    )
    raw = str((llm_result or {}).get("raw") or "").strip()
    _release_db_connection(db, "industry_analysis_json_repair")
    data = await _normalize_llm_json_object_with_repair(
        raw,
        context="industry_analysis_ai_short_dramas",
        llm_config=(llm_result or {}).get("llm_config"),
    )
    industry_analysis = data.get("industry_analysis") if isinstance(data.get("industry_analysis"), dict) else {}
    markdown = str(data.get("markdown") or "").strip()
    summary = str(data.get("summary") or "").strip()
    if not markdown and industry_analysis:
        markdown = _build_industry_analysis_markdown(report_period, summary, industry_analysis)

    result = {
        "report_month": str(data.get("report_month") or month_label),
        "report_period": str(data.get("report_period") or report_period),
        "fetched_at": search_bundle.get("fetched_at"),
        "summary": summary,
        "industry_analysis": industry_analysis,
        "markdown": markdown,
        "disclaimer": str(data.get("disclaimer") or "").strip(),
        "search_meta": {
            "report_kind": "industry_analysis",
            "report_months": search_bundle.get("report_months") or [],
            "query_count": len(search_bundle.get("queries") or []),
            "snippet_count": len(search_bundle.get("snippets") or []),
            "instant_note_count": len(search_bundle.get("instant_notes") or []),
            "source_stats": search_bundle.get("source_stats") or {},
        },
    }
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        return _persist_market_intel_report(
            db,
            project=project,
            report_kind="industry_analysis",
            payload=result,
        )
    except HTTPException:
        raise
    except Exception as persist_err:
        logger.warning("Failed to persist industry analysis report: %s", persist_err)
        return result


@router.post("/projects/{project_id}/story_generator/trending_ai_short_dramas", response_model=Dict[str, Any])
async def fetch_trending_ai_short_dramas_report(
    project_id: int,
    req: TrendingAiShortDramasRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    if async_mode == "1":
        tid = _submit_async(
            fetch_trending_ai_short_dramas_report,
            user_id=current_user.id,
            kind="trending_ai_short_dramas",
            project_id=project_id,
            req=req,
            async_mode="0",
        )
        return JSONResponse({"task_id": tid, "async": True})
    project = _require_project_access(db, project_id, current_user)
    gi_existing = dict(project.global_info or {})
    project_title_str = str(project.title or "")
    language = (req.language or gi_existing.get("language") or "").strip()

    month_label = (req.month_label or current_report_month_label()).strip()
    report_period = current_report_period_label(month_label)
    list_limit = 12
    try:
        list_limit = max(3, min(20, int(req.limit or 12)))
    except Exception:
        list_limit = 12

    _release_db_connection(db, "trending_dramas_web_search")
    search_bundle = await collect_trending_dramas_search_snippets(month_label=month_label)
    if not (search_bundle.get("snippets") or search_bundle.get("instant_notes")):
        raise HTTPException(status_code=502, detail="Web search returned no snippets for trending AI short dramas")

    try:
        sys_prompt_template = _resolve_prompt_text("story_generator_trending_ai_short_dramas.txt")
    except FileNotFoundError:
        logger.error("Trending AI short dramas prompt not found")
        raise HTTPException(status_code=404, detail="Prompt file 'story_generator_trending_ai_short_dramas.txt' not found.")

    search_context = build_trending_ai_short_dramas_user_prompt(
        search_bundle,
        project_title=project_title_str,
        language=language,
        limit=list_limit,
    )
    try:
        sys_prompt = sys_prompt_template.format(search_context=search_context)
    except Exception:
        sys_prompt = f"{sys_prompt_template}\n\n{search_context}"

    user_prompt = (
        f"Compile the {report_period} AI short drama hot-list from the search snippets below.\n"
        f"Return up to {list_limit} hot/new dramas only.\n"
        f"For each drama, analyze climax and iconic scenes from visual, dialogue, and action angles.\n\n"
        f"{search_context}"
    )
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    current_user = db.query(User).filter(User.id == int(current_user.id)).first() or current_user

    llm_result = await _run_ai_short_drama_market_llm(
        db=db,
        current_user=current_user,
        project=project,
        req=req,
        sys_prompt=sys_prompt,
        user_prompt=user_prompt,
        billing_item="trending_ai_short_dramas",
        llm_context="trending_ai_short_dramas",
    )
    raw = str((llm_result or {}).get("raw") or "").strip()
    _release_db_connection(db, "trending_dramas_json_repair")
    data = await _normalize_llm_json_object_with_repair(
        raw,
        context="trending_ai_short_dramas",
        llm_config=(llm_result or {}).get("llm_config"),
    )
    dramas = data.get("dramas") if isinstance(data.get("dramas"), list) else []
    markdown = str(data.get("markdown") or "").strip()
    summary = str(data.get("summary") or "").strip()
    if not markdown and dramas:
        markdown = _build_trending_dramas_markdown(report_period, summary, dramas)

    result = {
        "report_month": str(data.get("report_month") or month_label),
        "report_period": str(data.get("report_period") or report_period),
        "fetched_at": search_bundle.get("fetched_at"),
        "summary": summary,
        "markdown": markdown,
        "dramas": dramas,
        "disclaimer": str(data.get("disclaimer") or "").strip(),
        "search_meta": {
            "report_kind": "trending_dramas",
            "report_months": search_bundle.get("report_months") or [],
            "query_count": len(search_bundle.get("queries") or []),
            "snippet_count": len(search_bundle.get("snippets") or []),
            "instant_note_count": len(search_bundle.get("instant_notes") or []),
            "source_stats": search_bundle.get("source_stats") or {},
        },
    }
    try:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        return _persist_market_intel_report(
            db,
            project=project,
            report_kind="trending_dramas",
            payload=result,
        )
    except HTTPException:
        raise
    except Exception as persist_err:
        logger.warning("Failed to persist trending dramas report: %s", persist_err)
        return result


@router.get("/projects/{project_id}/market_intel/reports", response_model=Dict[str, Any])
async def list_market_intel_reports(
    project_id: int,
    kind: Optional[str] = Query(None, description="industry_analysis | trending_dramas"),
    month: Optional[str] = Query(None, description="YYYY-MM time index"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _require_project_access(db, project_id, current_user)
    model = _require_market_intel_model()
    try:
        _seed_market_intel_from_global_info(db, project)
    except Exception as seed_err:
        logger.warning("market intel seed skipped: %s", seed_err)

    q = db.query(model).filter(model.project_id == int(project_id))
    kind_norm = str(kind or "").strip()
    if kind_norm:
        q = q.filter(model.report_kind == kind_norm)
    month_norm = str(month or "").strip()
    if month_norm:
        q = q.filter(model.report_month == month_norm)
    rows = q.order_by(model.created_at.desc(), model.id.desc()).limit(int(limit)).all()
    items = [_market_intel_report_to_dict(row, include_payload=False) for row in rows]
    return {"items": items, "total": len(items)}


@router.get("/projects/{project_id}/market_intel/reports/{report_id}", response_model=Dict[str, Any])
async def get_market_intel_report(
    project_id: int,
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_project_access(db, project_id, current_user)
    model = _require_market_intel_model()
    row = (
        db.query(model)
        .filter(model.id == int(report_id), model.project_id == int(project_id))
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Market intel report not found")
    return _market_intel_report_to_dict(row, include_payload=True)


@router.post("/projects/{project_id}/story_generator/analyze_novel", response_model=Dict[str, Any])
async def analyze_project_novel_to_story_generator_fields(
    project_id: int,
    req: AnalyzeNovelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    if async_mode == "1":
        tid = _submit_async(analyze_project_novel_to_story_generator_fields, user_id=current_user.id,
                            kind="analyze_novel", project_id=project_id, req=req, async_mode="0")
        return JSONResponse({"task_id": tid, "async": True})
    project = _require_project_access(db, project_id, current_user)

    novel_text = (req.novel_text or "").strip()
    if not novel_text:
        raise HTTPException(status_code=400, detail="novel_text is required")

    try:
        sys_prompt_template = _resolve_prompt_text("story_generator_analyze_novel.txt")
    except FileNotFoundError:
        logger.error("Analyze novel prompt not found: story_generator_analyze_novel.txt")
        raise HTTPException(status_code=404, detail="Prompt file 'story_generator_analyze_novel.txt' not found.")

    project_title_str = str(project.title or "")
    user_prompt = f"Project Title: {project_title_str}\n\nNovel/Script Text:\n{novel_text}"

    function_name = (getattr(req, "function_name", None) if req else None) or "script_analysis"
    system_api_id = getattr(req, "system_api_id", None) if req else None

    llm_config = _resolve_story_generator_script_analysis_llm_config(
        db,
        int(current_user.id),
        function_name=function_name,
        system_api_id=system_api_id,
        context="analyze_project_novel",
        project_global_info=project.global_info,
    )
    if not llm_config or not (llm_config.get("api_key") or "").strip():
        raise HTTPException(status_code=400, detail="No valid LLM API key configured in active settings")
    provider = llm_config.get("provider") if llm_config else None
    model = llm_config.get("model") if llm_config else None
    resolved_id = ((llm_config or {}).get("config") or {}).get("__resolved_setting_id")
    resolved_source = ((llm_config or {}).get("config") or {}).get("__resolved_source")
    logger.info(
        "[analyze_novel] Using LLM config | provider=%s model=%s base_url=%s setting_id=%s source=%s",
        provider,
        model,
        (llm_config or {}).get("base_url"),
        resolved_id,
        resolved_source,
    )
    reservation_tx = None
    if billing_service.is_token_pricing(db, "llm_chat", provider, model):
        est = billing_service.estimate_reserve_tokens_from_messages(
            [
                {"role": "system", "content": sys_prompt_template},
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
                "item": "analyze_novel",
                "estimation_method": "prompt_tokens_ratio",
                "estimated_output_ratio": billing_service.RESERVE_OUTPUT_RATIO,
                "input_tokens": est.get("input_tokens", 0),
                "output_tokens": est.get("output_tokens", 0),
                "total_tokens": est.get("total_tokens", 0),
            },
        )
    else:
        billing_service.check_balance(db, current_user.id, "llm_chat", provider, model)

    # Keep compatibility with prompt template variable while still passing text in user prompt.
    try:
        sys_prompt = sys_prompt_template.format(novel_text=novel_text)
    except Exception:
        sys_prompt = sys_prompt_template

    try:
        _release_db_connection(db, "analyze_novel_llm_call")
        resp = await llm_service.generate_content_with_fallback(user_prompt, sys_prompt, llm_config)
    except Exception as e:
        if reservation_tx:
            billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), str(e))
        raise

    raw = (resp.get("content") or "").strip()
    if not raw:
        if reservation_tx:
            billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), "LLM returned empty content")
        raise HTTPException(status_code=500, detail="LLM returned empty content")

    usage = resp.get("usage") or {}
    if not usage:
        usage = billing_service.estimate_input_output_tokens_from_messages(
            [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": raw},
            ],
            output_ratio=1.0,
        )
    billing_details = {
        "item": "analyze_novel",
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
    _apply_llm_routing_to_billing_details(billing_details, resp)

    if reservation_tx:
        billing_service.settle_reservation(db, _reservation_tx_id(reservation_tx), billing_details)
    else:
        billing_service.deduct_credits(db, current_user.id, "llm_chat", provider, model, billing_details)

    content = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    content = content.replace("```json", "").replace("```", "").strip()
    start_idx = content.find("{")
    end_idx = content.rfind("}")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        content = content[start_idx:end_idx + 1]

    try:
        data = json.loads(content)
    except Exception as e:
        logger.error(f"[analyze_novel] JSON parse failed: {e}. Raw len={len(raw)}")
        raise HTTPException(status_code=500, detail="Failed to parse LLM JSON for novel analysis")

    if not isinstance(data, dict):
        raise HTTPException(status_code=500, detail="LLM JSON must be an object")

    required_keys = [
        "background",
        "setup",
        "development",
        "turning_points",
        "climax",
        "resolution",
        "suspense",
        "foreshadowing",
    ]

    normalized: Dict[str, Any] = {}
    for key in required_keys:
        val = data.get(key, "")
        if val is None:
            normalized[key] = ""
        elif isinstance(val, str):
            normalized[key] = val.strip()
        else:
            normalized[key] = str(val).strip()

    return normalized

