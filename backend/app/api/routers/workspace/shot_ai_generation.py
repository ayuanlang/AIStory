# -*- coding: utf-8 -*-
"""Shot AI generation / batch / apply workspace section routes."""
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

class AIShotGenRequest(BaseModel):
    user_prompt: Optional[str] = None
    system_prompt: Optional[str] = None
    shot_generation_mode: Optional[str] = None
    shot_generation_features: Optional[Dict[str, Any]] = None
    function_name: Optional[str] = None
    system_api_id: Optional[int] = None


class AIShotRegenerateRequest(BaseModel):
    content: Optional[List[Dict[str, Any]]] = None
    additional_instructions: Optional[str] = None
    prompt_file: Optional[str] = "skills/shot_generation.md"
    shot_generation_mode: Optional[str] = None
    shot_generation_features: Optional[Dict[str, Any]] = None
    function_name: Optional[str] = None
    system_api_id: Optional[int] = None



# Shot generation prompts (canonical: app.services.shot_generation_prompts).
from app.services.shot_generation_prompts import (  # noqa: E402,F401
    _strip_ai_shots_reasoning_prefix_lines,
    _build_ai_shots_response_validator,
    _map_shared_prompt_mode_to_shot_generation_mode,
    _resolve_effective_shot_generation_mode,
    _build_project_prompt_context,
    _build_shot_generation_project_context,
    _build_scene_subject_image_prompts_cn_section,
    _build_shot_prompts,
    _extract_shot_regenerate_marker,
    _build_shot_regenerate_prompts,
    _resolve_scene_for_shot_persist,
    _persist_scene_shot_generation_result,
)

class ShotGenerationRoutePreviewRequest(BaseModel):
    scene_id: int
    shot_generation_mode: Optional[str] = None
    shot_generation_features: Optional[Dict[str, Any]] = None



@router.get("/scenes/{scene_id}/ai_prompt_preview")
def ai_prompt_preview(
    scene_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
        
    episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
    project = _require_project_access(db, episode.project_id, current_user)
        
    project_context = _build_shot_generation_project_context(project)
    effective_mode = _resolve_effective_shot_generation_mode(
        db,
        project_metadata=project_context.get("metadata"),
        log_context="ai_prompt_preview",
    )
    feature_bundle = resolve_shot_generation_feature_bundle(
        project_metadata=project_context.get("metadata"),
        script_text=scene.core_scene_info or "",
        mode=effective_mode,
    )
    system, user = _build_shot_prompts(db, scene, project)
    return {
        "system_prompt": system,
        "user_prompt": user,
        "shot_generation_mode": feature_bundle.get("mode"),
        "base_prompt_file": feature_bundle.get("base_prompt_file"),
        "selected_skills": [
            {
                "skill_id": item.get("skill_id"),
                "dimension": item.get("dimension"),
                "value": item.get("value"),
                "title": item.get("title"),
                "slot_token": item.get("slot_token"),
            }
            for item in (feature_bundle.get("selected_skills") or [])
        ],
    }


@router.get("/prompts/shot-generation/features")
async def get_shot_generation_feature_options(current_user: User = Depends(get_current_user)):
    return get_shot_generation_feature_catalog()


def _shot_generation_slot_origin(slot_token: Any) -> str:
    token = str(slot_token or "").strip()
    if not token:
        return "unknown"
    if token == "[[SHOT_GENERATION_COMBO_RULES]]":
        return "global_combo"
    if token.startswith("[[SHOT_GENERATION_") and token.endswith("_RULES]]"):
        return "global_dimension"
    return "unknown"


@router.post("/prompts/shot-generation/route-preview")
async def preview_shot_generation_route(
    request: ShotGenerationRoutePreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    scene = db.query(Scene).filter(Scene.id == request.scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    project = _require_project_access(db, episode.project_id, current_user)
    project_context = _build_shot_generation_project_context(project)
    effective_mode = _resolve_effective_shot_generation_mode(
        db,
        requested_mode=request.shot_generation_mode,
        project_metadata=project_context.get("metadata"),
        log_context="shot-generation-route-preview",
    )
    bundle = resolve_shot_generation_feature_bundle(
        project_metadata=project_context.get("metadata"),
        explicit_features=request.shot_generation_features,
        script_text=scene.core_scene_info or "",
        mode=effective_mode,
    )
    return {
        "scene_id": scene.id,
        "requested_mode": request.shot_generation_mode,
        "effective_mode": bundle.get("mode"),
        "enabled": bundle.get("enabled"),
        "base_prompt_file": bundle.get("base_prompt_file"),
        "slot_blocks": bundle.get("slot_blocks") or {},
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
                "slot_origin": _shot_generation_slot_origin(item.get("slot_token")),
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
                "slot_origin": _shot_generation_slot_origin(item.get("slot_token")),
                "slot_has_block": bool((bundle.get("slot_blocks") or {}).get(str(item.get("slot_token") or ""))),
            }
            for item in (bundle.get("combo_matches") or [])
        ],
        "diagnostics": bundle.get("diagnostics") or [],
    }

class AnalysisContent(BaseModel):
    content: Union[Dict[str, Any], List[Any]]
    # When False (default), abandon import if the scene already has active shots.
    # Set True only for intentional replace flows (UI confirm).
    replace_existing: Optional[bool] = False


class SceneAiShotsBatchStartRequest(BaseModel):
    scene_ids: Optional[List[int]] = None
    function_name: Optional[str] = None
    system_api_id: Optional[int] = None


# Scene AI shots batch (canonical: app.services.scene_ai_shots_batch).
from app.services.scene_ai_shots_batch import (  # noqa: E402,F401
    SCENE_AI_SHOTS_BATCH_STATUS_KEY,
    SCENE_AI_SHOTS_BATCH_PER_SCENE_TIMEOUT_SEC,
    SCENE_AI_SHOTS_BATCH_DEFAULT_CONCURRENCY,
    SCENE_AI_SHOTS_BATCH_STATUS_ERROR_LIMIT,
    SCENE_AI_SHOTS_BATCH_STATUS_ERROR_MAX_CHARS,
    _read_scene_ai_shots_batch_status,
    _persist_scene_ai_shots_batch_status,
    _build_scene_ai_shots_batch_status_response,
    _run_scene_ai_shots_batch_item,
    _run_scene_ai_shots_batch_job,
    _start_scene_ai_shots_batch_for_episode,
)


@router.post("/episodes/{episode_id}/scenes/ai_shots/batch/start", response_model=Dict[str, Any])
def start_scene_ai_shots_batch(
    episode_id: int,
    req: SceneAiShotsBatchStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)
    return _start_scene_ai_shots_batch_for_episode(
        db=db,
        episode=episode,
        current_user=current_user,
        scene_ids=req.scene_ids or [],
        function_name=req.function_name,
        system_api_id=req.system_api_id,
    )


@router.get("/episodes/{episode_id}/scenes/ai_shots/batch/status", response_model=Dict[str, Any])
def get_scene_ai_shots_batch_status(
    episode_id: int,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _apply_no_store_headers(response)
    response.headers["X-Poll-Interval-Ms"] = "2500"
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)
    status_payload = _read_scene_ai_shots_batch_status(episode)
    if (
        bool(status_payload.get("running"))
        and _is_stale_running_payload(status_payload, stale_minutes=10)
        and not _is_episode_worker_alive(SCENE_AI_SHOTS_BATCH_THREADS, SCENE_AI_SHOTS_BATCH_THREADS_LOCK, int(episode_id))
    ):
        now_iso = now_bj_iso()
        status_payload["running"] = False
        status_payload["status"] = "canceled"
        status_payload["force_stopped"] = True
        status_payload["stopped_by_user"] = True
        status_payload["current_scene_id"] = None
        status_payload["current_scene_label"] = ""
        status_payload["updated_at"] = now_iso
        status_payload["finished_at"] = status_payload.get("finished_at") or now_iso
        status_payload["message"] = "Recovered orphaned task state (no active worker)"
        _persist_scene_ai_shots_batch_status(db, episode, status_payload)
    return _build_scene_ai_shots_batch_status_response(status_payload)


@router.post("/episodes/{episode_id}/scenes/ai_shots/batch/stop", response_model=Dict[str, Any])
def stop_scene_ai_shots_batch(
    episode_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)

    removed = False
    info = _episode_runtime_info_from_episode(episode)
    if SCENE_AI_SHOTS_BATCH_STATUS_KEY in info:
        info.pop(SCENE_AI_SHOTS_BATCH_STATUS_KEY, None)
        episode.episode_info = info
        db.add(episode)
        db.commit()
        removed = True

    _clear_episode_worker(SCENE_AI_SHOTS_BATCH_THREADS, SCENE_AI_SHOTS_BATCH_THREADS_LOCK, int(episode_id))
    _log_batch_sys_event(
        kind="scene-ai-shots-batch",
        phase="stop",
        user_id=current_user.id,
        user_name=current_user.username,
        project_id=episode.project_id,
        episode_id=episode_id,
        job_id=f"scene-ai-shots-batch:{int(episode_id)}",
        result="canceled",
        message="Force removed by user",
    )
    return {
        "episode_id": int(episode_id),
        "running": False,
        "status": "canceled",
        "deleted": bool(removed),
        "message": "Force removed",
    }

@router.post("/scenes/{scene_id}/ai_generate_shots")
async def ai_generate_shots(
    scene_id: int,
    req: Optional[AIShotGenRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    if async_mode == "1":
        tid = _submit_async(ai_generate_shots, user_id=current_user.id,
                            kind="ai_generate_shots", scene_id=scene_id, req=req, async_mode="0")
        return JSONResponse({"task_id": tid, "async": True})
    current_user_id = int(getattr(current_user, "id", 0) or 0)
    try:
        req_has_custom_user_prompt = bool(req and (req.user_prompt or "").strip())
        req_has_custom_system_prompt = bool(req and (req.system_prompt or "").strip())
        logger.info(
            "[ai_generate_shots] start "
            f"scene_id={scene_id} user_id={current_user_id} "
            f"custom_user_prompt={req_has_custom_user_prompt} custom_system_prompt={req_has_custom_system_prompt}"
        )
        # 1. Fetch Scene and Context
        scene = db.query(Scene).filter(Scene.id == scene_id).first()
        if not scene:
            logger.warning(f"[ai_generate_shots] scene_not_found scene_id={scene_id} user_id={current_user_id}")
            raise HTTPException(status_code=404, detail="Scene not found")
            
        episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
        if not episode:
            logger.warning(
                f"[ai_generate_shots] episode_not_found scene_id={scene_id} episode_id={scene.episode_id} user_id={current_user_id}"
            )
            raise HTTPException(status_code=404, detail="Episode not found")

        try:
            project = _require_project_access(db, episode.project_id, current_user)
        except HTTPException:
            logger.warning(
                f"[ai_generate_shots] unauthorized_or_project_not_found "
                f"scene_id={scene_id} episode_id={episode.id} project_id={episode.project_id} user_id={current_user_id}"
            )
            raise

        # Capture identity before releasing the DB for the long LLM call: orchestration
        # purge+reimport may replace this row while generation is in flight.
        persist_episode_id = int(getattr(episode, "id", 0) or 0) or None
        persist_scene_no = str(getattr(scene, "scene_no", "") or "").strip() or None

        logger.info(
            f"[ai_generate_shots] context scene_id={scene_id} episode_id={episode.id} project_id={project.id} "
            f"scene_no={persist_scene_no or ''}"
        )

        if req and req.user_prompt:
             user_input = req.user_prompt
             system_prompt = req.system_prompt or "You are a Storyboard Master."
             logger.info("[ai_generate_shots] Using custom prompt from request")
        else:
               system_prompt, user_input = _build_shot_prompts(
                  db,
                  scene,
                  project,
                  mode=(req.shot_generation_mode if req else None),
                  explicit_features=(req.shot_generation_features if req else None),
               )

        logger.info(f"[ai_generate_shots] system_prompt_len={len(system_prompt)}")
        logger.info(f"[ai_generate_shots] user_input_len={len(user_input)}")

        # 4. Call LLM
        function_name = (getattr(req, "function_name", None) if req else None) or "script_analysis"
        system_api_id = getattr(req, "system_api_id", None) if req else None

        try:
            db.commit()
        except Exception:
            pass
        try:
            db.commit()
        except Exception:
            pass
        llm_config, selected_dropdown_id, dropdown_fallback_ids, dropdown_order_ids = _resolve_script_analysis_dropdown_llm_config(
            db,
            current_user_id,
            function_name,
            system_api_id,
            context="ai_generate_shots",
        )
            
        llm_config = _inject_user_advanced_llm_preferences(llm_config, current_user)
        llm_config = _inject_project_creativity_temperature(
            llm_config,
            project.global_info,
            context="ai_generate_shots",
        )
        
        # Billing (Reserve for token pricing)
        provider = llm_config.get("provider") 
        model = llm_config.get("model")
        logger.info(
            f"[ai_generate_shots] llm_selection source=dropdown_priority provider={provider} model={model} "
            f"scene_id={scene_id} selected_system_api_id={selected_dropdown_id} fallback_ids={dropdown_fallback_ids}"
        )
        reservation_tx = None
        reservation_tx_id: Optional[int] = None
        if billing_service.is_token_pricing(db, "llm_chat", provider, model):
            messages_est = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ]
            est = billing_service.estimate_reserve_tokens_from_messages(messages_est)
            reserve_details = {
                "item": "generate_shots",
                "estimation_method": "prompt_tokens_ratio",
                "estimated_output_ratio": billing_service.RESERVE_OUTPUT_RATIO,
                "system_prompt_len": len(system_prompt or ""),
                "user_prompt_len": len(user_input or ""),
                "input_tokens": est.get("input_tokens", 0),
                "output_tokens": est.get("output_tokens", 0),
                "total_tokens": est.get("total_tokens", 0),
            }
            reservation_tx = billing_service.reserve_credits(db, current_user_id, "llm_chat", provider, model, reserve_details)
            try:
                reservation_tx_id = int(getattr(reservation_tx, "id", 0) or 0) or None
            except Exception:
                reservation_tx_id = None
            logger.info(
                f"[ai_generate_shots] token_reservation_created reservation_id={reservation_tx_id} "
                f"scene_id={scene_id} est_total_tokens={reserve_details.get('total_tokens', 0)}"
            )
        else:
            # Ensure we have at least a default task type if provider is missing (though check_balance handles None)
            billing_service.check_balance(db, current_user_id, "llm_chat", provider, model)

        _release_db_connection(db, "ai_generate_shots_llm_call")
        response_dict = await llm_service.generate_content_with_fallback(
            user_input,
            system_prompt,
            llm_config,
            response_validator=_build_ai_shots_response_validator(
                context="ai_generate_shots",
                scene_id=scene_id,
                user_id=current_user_id,
                source_label="Generate Shots",
                strip_reasoning_prefixes=True,
            ),
        )
        response_content_raw = response_dict.get("content", "")
        usage = response_dict.get("usage", {})

        logger.info(
            f"[ai_generate_shots] llm_response_received scene_id={scene_id} "
            f"llm_response_len_raw={len(response_content_raw)} usage_keys={list((usage or {}).keys())}"
        )

        if str(response_content_raw).startswith("Error:"):
            if reservation_tx_id is not None:
                billing_service.cancel_reservation(db, reservation_tx_id, str(response_content_raw))
            status_code = 502 if bool(response_dict.get("_postprocess_validation_failed")) else 500
            raise HTTPException(status_code=status_code, detail=str(response_content_raw))

        raw_str = str(response_content_raw or "").strip()
        if not raw_str:
            logger.warning(f"[ai_generate_shots] empty_llm_response scene_id={scene_id} user_id={current_user_id}")
            if reservation_tx_id is not None:
                billing_service.cancel_reservation(db, reservation_tx_id, "empty llm response")
            raise HTTPException(status_code=502, detail="LLM returned empty response")

        # Keep original model output for read-only auditing in UI.
        raw_text_original = str(response_content_raw or "")

        # Force-remove common reasoning leakage (e.g., "analysis", <think> blocks)
        # before moderation classification, parsing, and persistence.
        response_content = sanitize_llm_markdown_output(response_content_raw)

        if _is_provider_moderation_block_response(raw_str, response_content):
            logger.warning(
                f"[ai_generate_shots] prohibited_content_marker_detected scene_id={scene_id} user_id={current_user_id}"
            )
            if reservation_tx_id is not None:
                billing_service.cancel_reservation(db, reservation_tx_id, "provider moderation block")
            raise HTTPException(status_code=502, detail="Provider moderation blocked shot generation (PROHIBITED_CONTENT)")

        reasoning_prefix_terms = [
            "i will",
            "let me",
            "let's",
            "analysis",
            "reasoning",
            "thought process",
            "分析",
            "思路",
            "推理",
            "我将",
            "我认为",
            "我認為",
        ]
        try:
            escaped_terms = [re.escape(term) for term in reasoning_prefix_terms if str(term or "").strip()]
            reasoning_line_re = re.compile(
                r"^\s*(?:" + "|".join(escaped_terms) + r")\b",
                flags=re.IGNORECASE,
            )
        except re.error as re_err:
            logger.warning("[ai_generate_shots] reasoning regex compile failed, fallback used: %s", re_err)
            reasoning_line_re = re.compile(r"^\s*(?:analysis|reasoning)\b", flags=re.IGNORECASE)
        cleaned_lines = []
        for line in str(response_content or "").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("|") and reasoning_line_re.match(stripped):
                continue
            cleaned_lines.append(line)
        response_content = "\n".join(cleaned_lines).strip()

        # Keep only markdown table payload for shot generation flows.
        response_content = sanitize_shots_markdown_table_text(response_content)

        if not response_content:
            logger.warning(
                f"[ai_generate_shots] empty_after_sanitize scene_id={scene_id} user_id={current_user_id} raw_len={len(raw_str)}"
            )
            if reservation_tx_id is not None:
                billing_service.cancel_reservation(db, reservation_tx_id, "empty response after sanitize")
            raise HTTPException(status_code=502, detail="LLM response became empty after sanitize")

        logger.info(
            f"[ai_generate_shots] llm_response_cleaned scene_id={scene_id} llm_response_len_clean={len(response_content)}"
        )

        # Billing finalize
        if reservation_tx_id is not None:
            actual_details = {"item": "generate_shots"}
            if usage:
                actual_details.update(usage)
            _apply_llm_routing_to_billing_details(actual_details, response_dict)
            if "prompt_tokens" in actual_details and "input_tokens" not in actual_details:
                actual_details["input_tokens"] = actual_details.get("prompt_tokens", 0)
            if "completion_tokens" in actual_details and "output_tokens" not in actual_details:
                actual_details["output_tokens"] = actual_details.get("completion_tokens", 0)
            billing_service.settle_reservation(db, reservation_tx_id, actual_details)
            logger.info(
                f"[ai_generate_shots] token_reservation_settled reservation_id={reservation_tx_id} "
                f"scene_id={scene_id} actual_keys={list(actual_details.keys())}"
            )
        else:
            details = {"item": "generate_shots"}
            if usage:
                details.update(usage)
            _apply_llm_routing_to_billing_details(details, response_dict)
            if "prompt_tokens" in details and "input_tokens" not in details:
                details["input_tokens"] = details.get("prompt_tokens", 0)
            if "completion_tokens" in details and "output_tokens" not in details:
                details["output_tokens"] = details.get("completion_tokens", 0)
            billing_service.deduct_credits(db, current_user_id, "llm_chat", provider, model, details)
            logger.info(
                f"[ai_generate_shots] credits_deducted scene_id={scene_id} detail_keys={list(details.keys())}"
            )

        # 5. Parse Table
        headers, shots_data, table_line_count = parse_shots_markdown_table(response_content)
        if headers:
            logger.info(f"[ai_generate_shots] headers detected: {headers}")

        if not shots_data:
             logger.warning(f"DEBUG: No table found using delimiter |. Content snippet: {response_content[:200]}")
             raw_preview = response_content.replace("\n", " ")[:300]
             raise HTTPException(status_code=502, detail=f"Generate Shots returned 0 parsed rows; raw preview: {raw_preview}")
             
        logger.info(
            f"[ai_generate_shots] parsed_result scene_id={scene_id} table_lines={table_line_count} parsed_shots={len(shots_data)}"
        )
        if table_line_count >= 4 and len(shots_data) > 0 and (len(shots_data) * 2) <= table_line_count:
            logger.warning(
                f"[ai_generate_shots] suspicious_row_drop scene_id={scene_id} "
                f"table_lines={table_line_count} parsed_shots={len(shots_data)}"
            )
            raise HTTPException(
                status_code=502,
                detail="Shot generation output may have lost rows during markdown parsing; regenerate before apply.",
            )

        # Reject tables that cannot be applied (same structural rules as apply_ai_result).
        # Use tolerance so a single imperfect row does not discard an otherwise valid table;
        # fail only when zero rows remain applyable.
        try:
            shots_data, generate_skipped = _validate_shot_rows_for_apply_with_tolerance(
                shots_data,
                source_label="Generated shot table",
                status_code=502,
            )
            if generate_skipped:
                logger.warning(
                    "[ai_generate_shots] skipped_invalid_rows scene_id=%s skipped=%s details=%s",
                    scene_id,
                    len(generate_skipped),
                    generate_skipped[:5],
                )
        except HTTPException as exc:
            logger.warning(
                "[ai_generate_shots] structural_validation_failed scene_id=%s detail=%s",
                scene_id,
                str(getattr(exc, "detail", None) or exc)[:800],
            )
            raise

        # 6. Persist staging result only (no DB-shot import here)
        result_wrapper = _persist_scene_shot_generation_result(
            db=db,
            scene_id=scene_id,
            raw_text=raw_text_original,
            markdown_text=response_content,
            rows=shots_data,
            usage=usage,
            episode_id=persist_episode_id,
            scene_no=persist_scene_no,
        )
        if generate_skipped:
            result_wrapper["warnings"] = list(
                dict.fromkeys(
                    [str(w or "").strip() for w in (result_wrapper.get("warnings") or []) if str(w or "").strip()]
                    + [str(w or "").strip() for w in generate_skipped if str(w or "").strip()]
                )
            )

        response_scene_id = int(result_wrapper.get("remapped_scene_id") or scene_id or 0) or scene_id
        logger.info(
            f"[ai_generate_shots] response_ready scene_id={response_scene_id} requested_scene_id={scene_id} "
            f"response_keys={list(result_wrapper.keys())} content_count={len(result_wrapper.get('content') or [])}"
        )
        
        # Return the raw data so frontend can display it in the "Edit" modal
        return result_wrapper

    except HTTPException as e:
        logger.warning(
            f"[ai_generate_shots] http_exception scene_id={scene_id} user_id={current_user_id} "
            f"status_code={e.status_code} detail={e.detail}"
        )
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        logger.exception(f"[ai_generate_shots] unhandled_error scene_id={scene_id} user_id={current_user_id} error={e}")
        # Log failure
        try:
            p_log = locals().get('provider')
            m_log = locals().get('model')
            billing_service.log_failed_transaction(db, current_user_id, "llm_chat", p_log, m_log, str(e))
        except: pass
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scenes/{scene_id}/ai_regenerate_shots")
async def ai_regenerate_shots(
    scene_id: int,
    req: Optional[AIShotRegenerateRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    if async_mode == "1":
        tid = _submit_async(
            ai_regenerate_shots,
            user_id=current_user.id,
            kind="ai_regenerate_shots",
            scene_id=scene_id,
            req=req,
            async_mode="0",
        )
        return JSONResponse({"task_id": tid, "async": True})
    current_user_id = int(getattr(current_user, "id", 0) or 0)

    try:
        scene = db.query(Scene).filter(Scene.id == scene_id).first()
        if not scene:
            raise HTTPException(status_code=404, detail="Scene not found")

        episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
        if not episode:
            raise HTTPException(status_code=404, detail="Episode not found")

        project = _require_project_access(db, episode.project_id, current_user)

        staged_rows = []
        staged_markdown = ""
        if req and isinstance(req.content, list) and req.content:
            staged_rows, staged_markdown = _validate_shot_rows_roundtrip_or_raise(
                req.content,
                source_label="Current staged shot table",
                status_code=400,
            )
        else:
            stored_markdown = str(scene.ai_shots_result or "").strip()
            if not stored_markdown:
                raise HTTPException(
                    status_code=400,
                    detail="No staged AI shot markdown is available for regeneration",
                )
            _, parsed_rows, _ = _parse_shot_markdown_or_raise(
                stored_markdown,
                source_label="Stored staged shot table",
                status_code=400,
            )
            staged_rows, staged_markdown = _validate_shot_rows_roundtrip_or_raise(
                parsed_rows,
                source_label="Stored staged shot table",
                status_code=400,
            )

        prompt_filename = str((req.prompt_file if req else "") or "skills/shot_generation.md").strip() or "skills/shot_generation.md"
        try:
            if prompt_filename != "skills/shot_generation.md":
                system_prompt = _resolve_prompt_text(prompt_filename)
                _, base_user_prompt = _build_shot_prompts(db, scene, project)
                user_input = (
                    f"# Scene Context Reference\n{str(base_user_prompt or '').strip()}\n\n"
                    f"# Current Staged Shot Markdown\n{staged_markdown}\n\n"
                    f"# User Supplement Instructions\n{str((req.additional_instructions if req else '') or '').strip() or '(none)'}\n"
                )
            else:
                system_prompt, user_input = _build_shot_regenerate_prompts(
                    db,
                    scene,
                    project,
                    staged_markdown=staged_markdown,
                    additional_instructions=str((req.additional_instructions if req else "") or "").strip(),
                    mode=(req.shot_generation_mode if req else None),
                    explicit_features=(req.shot_generation_features if req else None),
                )
        except FileNotFoundError:
            raise HTTPException(status_code=500, detail=f"Prompt file '{prompt_filename}' could not be loaded.")

        function_name = (getattr(req, "function_name", None) if req else None) or "script_analysis"
        system_api_id = getattr(req, "system_api_id", None) if req else None

        try:
            db.commit()
        except Exception:
            pass
        try:
            db.commit()
        except Exception:
            pass
        llm_config, selected_dropdown_id, dropdown_fallback_ids, dropdown_order_ids = _resolve_script_analysis_dropdown_llm_config(
            db,
            current_user_id,
            function_name,
            system_api_id,
            context="ai_regenerate_shots",
        )

        llm_config = _inject_user_advanced_llm_preferences(llm_config, current_user)
        llm_config = _inject_project_creativity_temperature(
            llm_config,
            project.global_info,
            context="ai_regenerate_shots",
        )

        provider = llm_config.get("provider")
        model = llm_config.get("model")
        reservation_tx = None
        reservation_tx_id: Optional[int] = None
        if billing_service.is_token_pricing(db, "llm_chat", provider, model):
            messages_est = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ]
            est = billing_service.estimate_reserve_tokens_from_messages(messages_est)
            reserve_details = {
                "item": "regenerate_shots",
                "estimation_method": "prompt_tokens_ratio",
                "estimated_output_ratio": billing_service.RESERVE_OUTPUT_RATIO,
                "system_prompt_len": len(system_prompt or ""),
                "user_prompt_len": len(user_input or ""),
                "input_tokens": est.get("input_tokens", 0),
                "output_tokens": est.get("output_tokens", 0),
                "total_tokens": est.get("total_tokens", 0),
            }
            reservation_tx = billing_service.reserve_credits(db, current_user_id, "llm_chat", provider, model, reserve_details)
            try:
                reservation_tx_id = int(getattr(reservation_tx, "id", 0) or 0) or None
            except Exception:
                reservation_tx_id = None
        else:
            billing_service.check_balance(db, current_user_id, "llm_chat", provider, model)

        _release_db_connection(db, "ai_regenerate_shots_llm_call")
        response_dict = await llm_service.generate_content_with_fallback(
            user_input,
            system_prompt,
            llm_config,
            response_validator=_build_ai_shots_response_validator(
                context="ai_regenerate_shots",
                scene_id=scene_id,
                user_id=current_user_id,
                source_label="Regenerate Shots",
                validate_regenerate_markers=True,
            ),
        )
        response_content_raw = response_dict.get("content", "")
        usage = response_dict.get("usage", {})

        if str(response_content_raw).startswith("Error:"):
            if reservation_tx_id is not None:
                billing_service.cancel_reservation(db, reservation_tx_id, str(response_content_raw))
            status_code = 502 if bool(response_dict.get("_postprocess_validation_failed")) else 500
            raise HTTPException(status_code=status_code, detail=str(response_content_raw))

        raw_str = str(response_content_raw or "").strip()
        if not raw_str:
            if reservation_tx_id is not None:
                billing_service.cancel_reservation(db, reservation_tx_id, "empty llm response")
            raise HTTPException(status_code=502, detail="LLM returned empty response")

        raw_text_original = str(response_content_raw or "")

        response_content = sanitize_llm_markdown_output(response_content_raw)
        if _is_provider_moderation_block_response(raw_str, response_content):
            if reservation_tx_id is not None:
                billing_service.cancel_reservation(db, reservation_tx_id, "provider moderation block")
            raise HTTPException(status_code=502, detail="Provider moderation blocked shot regeneration (PROHIBITED_CONTENT)")

        # Keep only markdown table payload for shot regeneration flows.
        response_content = sanitize_shots_markdown_table_text(response_content)

        if not response_content:
            if reservation_tx_id is not None:
                billing_service.cancel_reservation(db, reservation_tx_id, "empty response after sanitize")
            raise HTTPException(status_code=502, detail="LLM response became empty after sanitize")

        if reservation_tx_id is not None:
            actual_details = {"item": "regenerate_shots"}
            if usage:
                actual_details.update(usage)
            _apply_llm_routing_to_billing_details(actual_details, response_dict)
            if "prompt_tokens" in actual_details and "input_tokens" not in actual_details:
                actual_details["input_tokens"] = actual_details.get("prompt_tokens", 0)
            if "completion_tokens" in actual_details and "output_tokens" not in actual_details:
                actual_details["output_tokens"] = actual_details.get("completion_tokens", 0)
            billing_service.settle_reservation(db, reservation_tx_id, actual_details)
        else:
            details = {"item": "regenerate_shots"}
            if usage:
                details.update(usage)
            _apply_llm_routing_to_billing_details(details, response_dict)
            if "prompt_tokens" in details and "input_tokens" not in details:
                details["input_tokens"] = details.get("prompt_tokens", 0)
            if "completion_tokens" in details and "output_tokens" not in details:
                details["output_tokens"] = details.get("completion_tokens", 0)
            billing_service.deduct_credits(db, current_user_id, "llm_chat", provider, model, details)

        headers, regenerated_rows, table_line_count = parse_shots_markdown_table(response_content)
        if not regenerated_rows:
            raw_preview = response_content.replace("\n", " ")[:300]
            raise HTTPException(status_code=502, detail=f"Regenerate Shots returned 0 parsed rows; raw preview: {raw_preview}")
        if table_line_count >= 4 and len(regenerated_rows) > 0 and (len(regenerated_rows) * 2) <= table_line_count:
            raise HTTPException(
                status_code=502,
                detail="Shot regeneration output may have lost rows during markdown parsing; regenerate before apply.",
            )

        validated_rows = _validate_shot_rows_or_raise(
            regenerated_rows,
            source_label="Regenerated shot diff table",
            status_code=502,
        )

        marker_errors: List[str] = []
        for idx, row in enumerate(validated_rows, start=1):
            shot_id = _pick_shot_cell(row, ["Shot ID", "shot_id", "镜头ID"], "")
            shot_logic = _pick_shot_cell(row, ["Shot Logic (CN)", "shot_logic_cn", "镜头逻辑", "镜头逻辑（中文）"], "")
            marker_mode, _ = _extract_shot_regenerate_marker(shot_logic)
            if marker_mode not in {"update", "add"}:
                marker_errors.append(f"row {idx} ({shot_id or 'unknown shot'}) missing required Shot Logic marker")
                continue
            if marker_mode == "add" and not re.search(r"_\d+$", str(shot_id or "")):
                marker_errors.append(f"row {idx} ({shot_id or 'unknown shot'}) add-shot id must use _1/_2 style suffix")

        if marker_errors:
            detail = "; ".join(marker_errors[:5])
            if len(marker_errors) > 5:
                detail += f"; and {len(marker_errors) - 5} more rows"
            raise HTTPException(status_code=502, detail=f"Regenerated shot diff failed marker validation: {detail}")

        return {
            "timestamp": now_bj_iso(),
            "raw_text": raw_text_original,
            "content": validated_rows,
            "usage": usage,
            "warnings": [],
            "source_row_count": len(staged_rows),
            "result_row_count": len(validated_rows),
            "headers": headers,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "[ai_regenerate_shots] unhandled_error scene_id=%s user_id=%s error=%s",
            scene_id,
            current_user_id,
            e,
        )
        try:
            p_log = locals().get("provider")
            m_log = locals().get("model")
            billing_service.log_failed_transaction(db, current_user_id, "llm_chat", p_log, m_log, str(e))
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/scenes/{scene_id}/latest_ai_result")
def get_scene_latest_ai_result(
    scene_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """Get the latest saved AI shot generation result for a scene.

    Storage (Scheme A): scenes.ai_shots_result is the raw Markdown table text.
    This endpoint returns a structured wrapper for the UI by parsing that Markdown.
    """
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
        
    episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
    _require_project_access(db, episode.project_id, current_user)
         
    raw_value = scene.ai_shots_result
    if not raw_value:
        return {}

    # Backward compat: older versions stored JSON wrapper into scenes.ai_shots_result
    if isinstance(raw_value, str) and raw_value.strip().startswith('{'):
        try:
            legacy = json.loads(raw_value)
            if isinstance(legacy, dict) and ("raw_text" in legacy or "content" in legacy):
                raw_text = legacy.get("raw_text") or ""
                if raw_text:
                    scene.ai_shots_result = raw_text
                    db.commit()
                    raw_value = raw_text
                else:
                    # No raw_text; best effort keep the JSON string as raw.
                    raw_value = scene.ai_shots_result
        except Exception:
            pass

    # Parse markdown table into list-of-dicts for the staging editor
    warnings: List[str] = []
    _, shots_data, table_line_count = parse_shots_markdown_table(raw_value or "")
    if str(raw_value or "").strip() and not shots_data:
        warnings.append("Shot generation output did not produce a parseable markdown table; review the raw markdown before apply.")
    if table_line_count >= 4 and len(shots_data) > 0 and (len(shots_data) * 2) <= table_line_count:
        logger.warning(
            f"[get_scene_latest_ai_result] suspicious_row_drop scene_id={scene_id} "
            f"table_lines={table_line_count} parsed_shots={len(shots_data)}"
        )
        warnings.append("Shot generation output may have lost rows during markdown parsing; review the raw markdown before apply.")

    return {
        "raw_text": raw_value,
        "content": shots_data,
        "warnings": warnings,
    }

@router.put("/scenes/{scene_id}/latest_ai_result")
def update_scene_latest_ai_result(
    scene_id: int,
    data: AnalysisContent, # Reusing this schema: { "content": ... }
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    Update (Save/Edit) the latest shot generation result without applying it.
    Expects data.content to be the list of shot dictionaries.
    """
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
        
    episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
    _require_project_access(db, episode.project_id, current_user)
    
    validated_rows, md = _validate_shot_rows_roundtrip_or_raise(
        data.content,
        source_label="Edited scene shot table",
        status_code=400,
    )

    scene.ai_shots_result = md
    db.commit()

    return {
        "timestamp": now_bj_iso(),
        "raw_text": md,
        "content": validated_rows,
    }



# Shot import ops (canonical: app.services.shot_import_ops).
from app.services.shot_import_ops import (  # noqa: E402,F401
    _import_scene_shot_rows_to_db,
)


@router.post("/scenes/{scene_id}/apply_ai_result")
def apply_scene_ai_result(
    scene_id: int,
    data: Optional[AnalysisContent] = None, # Optional: apply provided content instead of stored
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    Apply the stored (or provided) shot list to the actual Shots table.

    Default: abandon import when the scene already has active shots.
    Pass replace_existing=true only for intentional overwrite (UI confirm).
    Duplicate Shot IDs within the payload are deduped (last row wins).
    """
    scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
        
    episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
    project = _require_project_access(db, episode.project_id, current_user)
         
    shots_data = []
    skipped_row_errors: List[str] = []
    replace_existing = bool(getattr(data, "replace_existing", False)) if data is not None else False
    
    # 1. Determine Source
    provided_content = None
    if data and data.content is not None:
        provided_content = data.content

    if str(getattr(scene, "ai_shots_result", None) or "").strip():
        shots_data, skipped_row_errors = _resolve_shots_data_for_apply(
            scene,
            provided_content,
            source_label="Scene shot table",
            status_code=400,
        )
    elif provided_content is not None:
        shots_data, skipped_row_errors = _validate_shot_rows_for_apply_with_tolerance(
            provided_content,
            source_label="Provided scene shot table",
            status_code=400,
        )
    else:
        shots_data, skipped_row_errors = _resolve_shots_data_for_apply(
            scene,
            None,
            source_label="Stored scene shot table",
            status_code=409,
        )

    if not shots_data:
        logger.warning(
            "[apply_scene_ai_result] empty_shots_data scene_id=%s has_stored=%s provided=%s skipped=%s",
            scene_id,
            bool(str(getattr(scene, "ai_shots_result", None) or "").strip()),
            provided_content is not None,
            skipped_row_errors[:5] if skipped_row_errors else [],
        )
        raise HTTPException(status_code=400, detail="No shot rows provided or available to apply")

    if skipped_row_errors:
        logger.warning(
            "[apply_scene_ai_result] skipped_invalid_rows scene_id=%s skipped=%s details=%s",
            scene_id,
            len(skipped_row_errors),
            skipped_row_errors[:5],
        )
                 
    return _import_scene_shot_rows_to_db(
        scene_id=scene_id,
        db=db,
        scene=scene,
        episode=episode,
        project=project,
        shots_data=shots_data,
        skipped_row_errors=skipped_row_errors,
        replace_existing=replace_existing,
    )
