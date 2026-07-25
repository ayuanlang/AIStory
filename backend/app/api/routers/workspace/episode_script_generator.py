# -*- coding: utf-8 -*-
"""Episode/project script-generator workspace section routes."""
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

from app.schemas.episode import (  # noqa: E402,F401
    ProjectEpisodeScriptsGenerateRequest,
)
from app.schemas.episode_requests import (  # noqa: E402,F401
    EPISODE_SCENE_GEN_STATUS_KEY,
    ScriptScenesGenerateRequest,
)

def _read_episode_scene_generation_status(episode: Episode) -> Dict[str, Any]:
    try:
        info = _episode_runtime_info_from_episode(episode)
        payload = info.get(EPISODE_SCENE_GEN_STATUS_KEY)
        if isinstance(payload, dict):
            return dict(payload)
    except Exception:
        pass
    return {
        "running": False,
        "status": "idle",
        "message": "",
        "scenes_created": 0,
        "stop_requested": False,
    }


def _persist_episode_scene_generation_status(db: Session, episode: Episode, status_payload: Dict[str, Any]) -> None:
    latest_episode = (
        db.query(Episode)
        .execution_options(populate_existing=True)
        .filter(Episode.id == int(episode.id))
        .first()
    )
    target_episode = latest_episode or episode

    info = _episode_runtime_info_from_episode(target_episode)
    existing_status = info.get(EPISODE_SCENE_GEN_STATUS_KEY)
    merged_status = dict(status_payload or {})
    has_incoming_force_flag = "force_stopped" in merged_status

    if isinstance(existing_status, dict) and bool(existing_status.get("force_stopped")) and not has_incoming_force_flag:
        merged_status["force_stopped"] = True

    if bool(merged_status.get("force_stopped")):
        now_iso = now_bj_iso()
        merged_status["running"] = False
        merged_status["status"] = "canceled"
        merged_status["stopped_by_user"] = True
        merged_status["finished_at"] = merged_status.get("finished_at") or now_iso
        merged_status["updated_at"] = now_iso

    info[EPISODE_SCENE_GEN_STATUS_KEY] = merged_status
    target_episode.episode_info = info
    db.add(target_episode)
    db.commit()


def _run_episode_scene_generation_job(episode_id: int, req_payload: Dict[str, Any], user_id: int) -> None:
    db = SessionLocal()
    try:
        episode = db.query(Episode).filter(Episode.id == episode_id).first()
        user = db.query(User).filter(User.id == user_id).first()
        if not episode or not user:
            return
        user_principal = _snapshot_user_principal(user)

        job_id = f"episode-scenes:{int(episode_id)}"
        user_name = str(user_principal.username or f"user_{user_id}")

        latest = _read_episode_scene_generation_status(episode)
        if bool(latest.get("stop_requested")):
            latest["running"] = False
            latest["status"] = "stopped"
            latest["message"] = "Stopped before generation started"
            latest["finished_at"] = now_bj_iso()
            latest["updated_at"] = latest["finished_at"]
            _persist_episode_scene_generation_status(db, episode, latest)
            _log_batch_sys_event(
                kind="episode-scenes",
                phase="end",
                user_id=user_id,
                user_name=user_name,
                project_id=episode.project_id,
                episode_id=episode_id,
                job_id=job_id,
                result="canceled",
                message="Stopped before generation started",
            )
            return

        req = ScriptScenesGenerateRequest(**(req_payload or {}))
        _release_db_connection(db, "episode_scene_generation_job")
        result = asyncio.run(
            generate_episode_scenes_from_story(
                episode_id=episode_id,
                req=req,
                db=db,
                current_user=user_principal,
            )
        )

        episode = db.query(Episode).filter(Episode.id == episode_id).first()
        if episode:
            status_payload = _read_episode_scene_generation_status(episode)
            status_payload["running"] = False
            status_payload["status"] = "completed"
            status_payload["message"] = "Scene generation completed"
            status_payload["scenes_created"] = int((result or {}).get("scenes_created") or 0)
            status_payload["result"] = result
            status_payload["updated_at"] = now_bj_iso()
            status_payload["finished_at"] = status_payload["updated_at"]
            _persist_episode_scene_generation_status(db, episode, status_payload)
            _log_batch_sys_event(
                kind="episode-scenes",
                phase="end",
                user_id=user_id,
                user_name=user_name,
                project_id=episode.project_id,
                episode_id=episode_id,
                job_id=job_id,
                result="completed",
                message="Scene generation completed",
                extra={
                    "scenes_created": int(status_payload.get("scenes_created") or 0),
                    "status": status_payload.get("status"),
                },
            )
    except Exception as e:
        try:
            episode = db.query(Episode).filter(Episode.id == episode_id).first()
            if episode:
                status_payload = _read_episode_scene_generation_status(episode)
                status_payload["running"] = False
                status_payload["status"] = "failed"
                status_payload["message"] = str(e)
                status_payload["updated_at"] = now_bj_iso()
                status_payload["finished_at"] = status_payload["updated_at"]
                _persist_episode_scene_generation_status(db, episode, status_payload)
                _log_batch_sys_event(
                    kind="episode-scenes",
                    phase="end",
                    user_id=user_id,
                    user_name=str((user.username if 'user' in locals() and user else "") or f"user_{user_id}"),
                    project_id=episode.project_id,
                    episode_id=episode_id,
                    job_id=f"episode-scenes:{int(episode_id)}",
                    result="failed",
                    message=str(e),
                )
        except Exception:
            pass
    finally:
        _clear_episode_worker(EPISODE_SCENE_JOB_THREADS, EPISODE_SCENE_JOB_THREADS_LOCK, int(episode_id))
        db.close()


@router.post("/episodes/{episode_id}/script_generator/scenes", response_model=Dict[str, Any])
async def generate_episode_scenes_from_story(
    episode_id: int,
    req: ScriptScenesGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    if async_mode == "1":
        tid = _submit_async(generate_episode_scenes_from_story, user_id=current_user.id,
                            kind="episode_scenes", episode_id=episode_id, req=req, async_mode="0")
        return JSONResponse({"task_id": tid, "async": True})
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    project = _require_project_access(db, episode.project_id, current_user)

    try:
        sys_prompt = _resolve_prompt_text("script_generator_scenes.txt")
    except FileNotFoundError:
        logger.error("Script generator prompt not found: script_generator_scenes.txt")
        raise HTTPException(status_code=404, detail="Prompt file 'script_generator_scenes.txt' not found.")

    global_md = ""
    try:
        global_md = (project.global_info or {}).get("story_dna_global_md") or ""
    except Exception:
        global_md = ""
    episode_md = ""
    try:
        episode_md = _episode_info_from_episode(episode).get("story_dna_episode_md") or ""
    except Exception:
        episode_md = ""

    project_title_str = str(project.title or "")
    episode_title_str = str(episode.title or "")

    user_prompt = (
        f"Project Title: {project_title_str}\n"
        f"Episode Title: {episode_title_str}\n"
        f"Scene Count Target: {req.scene_count or ''}\n"
        f"Background: {req.background or ''}\n"
        f"Setup: {req.setup or ''}\n"
        f"Development: {req.development or ''}\n"
        f"Turning Points: {req.turning_points or ''}\n"
        f"Climax: {req.climax or ''}\n"
        f"Resolution: {req.resolution or ''}\n"
        f"Suspense: {req.suspense or ''}\n"
        f"Foreshadowing: {req.foreshadowing or ''}\n"
        f"Extra Notes: {req.extra_notes or ''}\n\n"
        f"Global Story DNA (if any):\n{global_md}\n\n"
        f"Episode Story DNA (if any):\n{episode_md}\n"
    )

    llm_config = agent_service.get_active_llm_config(current_user.id, function_name=getattr(req, "function_name", None), system_api_id=getattr(req, "system_api_id", None))
    llm_config = _inject_project_creativity_temperature(
        llm_config,
        project.global_info,
        context="generate_episode_scenes_from_story",
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
                "item": "script_generator_scenes",
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
        _release_db_connection(db, "generate_episode_scenes_llm_call")
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
        "item": "script_generator_scenes",
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

    # Parse strict JSON (strip fences if model ignored instruction)
    content = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    content = content.replace("```json", "").replace("```", "").strip()
    start_idx = content.find("{")
    end_idx = content.rfind("}")
    if start_idx != -1 and end_idx != -1:
        content = content[start_idx:end_idx + 1]
    try:
        data = json.loads(content)
    except Exception as e:
        logger.error(f"[script_generator] JSON parse failed: {e}. Raw len={len(raw)}")
        raise HTTPException(status_code=500, detail="Failed to parse LLM JSON for scenes")

    scenes = data.get("scenes") if isinstance(data, dict) else None
    if not isinstance(scenes, list) or len(scenes) == 0:
        raise HTTPException(status_code=500, detail="LLM JSON did not include a non-empty 'scenes' list")

    if req.replace_existing_scenes:
        _soft_delete_scenes(db, episode_id=episode_id)

    created = []
    for i, s in enumerate(scenes, start=1):
        if not isinstance(s, dict):
            continue
        scene_no = str(s.get("scene_no") or i)
        original_script_text = str(s.get("original_script_text") or "").strip()
        if not original_script_text:
            continue
        db_scene = Scene(
            episode_id=episode_id,
            scene_no=scene_no,
            scene_name=(s.get("scene_name") or None),
            original_script_text=original_script_text,
            equivalent_duration=(s.get("equivalent_duration") or None),
            core_scene_info=(s.get("core_scene_info") or None),
            environment_name=(s.get("environment_name") or None),
            linked_characters=(s.get("linked_characters") or None),
            key_props=(s.get("key_props") or None),
        )
        db.add(db_scene)
        created.append(db_scene)

    db.commit()
    for sc in created:
        db.refresh(sc)

    # Non-blocking cost recompute after scenes are imported
    try:
        _recompute_and_persist_project_cost_estimation(db, int(episode.project_id))
        db.commit()
    except Exception:
        pass

    return {
        "episode_id": episode_id,
        "scenes_created": len(created),
        "scenes": [
            {
                "id": sc.id,
                "scene_no": sc.scene_no,
                "scene_name": sc.scene_name,
                "original_script_text": sc.original_script_text,
                "equivalent_duration": sc.equivalent_duration,
                "core_scene_info": sc.core_scene_info,
                "environment_name": sc.environment_name,
                "linked_characters": sc.linked_characters,
                "key_props": sc.key_props,
            }
            for sc in created
        ],
    }


@router.post("/episodes/{episode_id}/script_generator/scenes/start", response_model=Dict[str, Any])
def start_episode_scenes_generation_job(
    episode_id: int,
    req: ScriptScenesGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)

    latest = _read_episode_scene_generation_status(episode)
    if bool(latest.get("running")):
        raise HTTPException(status_code=409, detail="Scene generation is already running")

    now_iso = now_bj_iso()
    status_payload = {
        "running": True,
        "status": "running",
        "message": "Scene generation started",
        "episode_id": episode_id,
        "project_id": episode.project_id,
        "request": req.model_dump(),
        "scenes_created": 0,
        "result": None,
        "stop_requested": False,
        "stop_requested_at": None,
        "force_stopped": False,
        "started_at": now_iso,
        "updated_at": now_iso,
        "finished_at": None,
    }
    _persist_episode_scene_generation_status(db, episode, status_payload)
    _log_batch_sys_event(
        kind="episode-scenes",
        phase="start",
        user_id=current_user.id,
        user_name=current_user.username,
        project_id=episode.project_id,
        episode_id=episode_id,
        job_id=f"episode-scenes:{int(episode_id)}",
        result="running",
        message="Batch task started",
        extra={
            "request": req.model_dump(),
        },
    )

    worker = threading.Thread(
        target=_run_episode_scene_generation_job,
        args=(episode_id, req.model_dump(), current_user.id),
        daemon=True,
    )
    worker.start()
    _register_episode_worker(EPISODE_SCENE_JOB_THREADS, EPISODE_SCENE_JOB_THREADS_LOCK, int(episode_id), worker)
    return status_payload


@router.get("/episodes/{episode_id}/script_generator/scenes/status", response_model=Dict[str, Any])
def get_episode_scenes_generation_job_status(
    episode_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)
    status_payload = _read_episode_scene_generation_status(episode)
    if (
        bool(status_payload.get("running"))
        and _is_stale_running_payload(status_payload, stale_minutes=10)
        and not _is_episode_worker_alive(EPISODE_SCENE_JOB_THREADS, EPISODE_SCENE_JOB_THREADS_LOCK, int(episode_id))
    ):
        now_iso = now_bj_iso()
        status_payload["running"] = False
        status_payload["status"] = "canceled"
        status_payload["force_stopped"] = True
        status_payload["stopped_by_user"] = True
        status_payload["updated_at"] = now_iso
        status_payload["finished_at"] = status_payload.get("finished_at") or now_iso
        status_payload["message"] = "Recovered orphaned task state (no active worker)"
        _persist_episode_scene_generation_status(db, episode, status_payload)
    return status_payload


@router.post("/episodes/{episode_id}/script_generator/scenes/stop", response_model=Dict[str, Any])
def stop_episode_scenes_generation_job(
    episode_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)

    status_payload = _read_episode_scene_generation_status(episode)
    removed = False
    info = _episode_runtime_info_from_episode(episode)
    if EPISODE_SCENE_GEN_STATUS_KEY in info:
        info.pop(EPISODE_SCENE_GEN_STATUS_KEY, None)
        episode.episode_info = info
        db.add(episode)
        db.commit()
        removed = True

    _clear_episode_worker(EPISODE_SCENE_JOB_THREADS, EPISODE_SCENE_JOB_THREADS_LOCK, int(episode_id))
    _log_batch_sys_event(
        kind="episode-scenes",
        phase="stop",
        user_id=current_user.id,
        user_name=current_user.username,
        project_id=episode.project_id,
        episode_id=episode_id,
        job_id=f"episode-scenes:{int(episode_id)}",
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


@router.post("/projects/{project_id}/script_generator/episodes/scripts", response_model=Dict[str, Any])
async def generate_project_episode_scripts_from_global_framework(
    project_id: int,
    req: ProjectEpisodeScriptsGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    """Generate per-episode script drafts from Project Overview artifacts.

    Uses:
    - project.global_info.story_dna_global_md (Generated Global Framework)
    - project.global_info.character_canon_md OR project.global_info.character_profiles (Character Canon Project)

    Creates missing episodes up to N and writes each draft into Episode.script_content.
    """
    if async_mode == "1":
        tid = _submit_async(generate_project_episode_scripts_from_global_framework, user_id=current_user.id,
                            kind="episode_scripts", project_id=project_id, req=req, async_mode="0")
        return JSONResponse({"task_id": tid, "async": True})
    started_at = datetime.utcnow()
    started_at_iso = started_at.isoformat()
    call_meta = {
        "project_id": project_id,
        "user_id": current_user.id,
        "generator_kind": req.generator_kind,
        "episodes_count": req.episodes_count,
        "episode_id": req.episode_id,
        "episode_number": req.episode_number,
        "overwrite_existing": req.overwrite_existing,
        "retry_failed_only": req.retry_failed_only,
        "strict_markdown": req.strict_markdown,
        "extra_notes_len": len(req.extra_notes or ""),
        "started_at": started_at_iso,
    }
    logger.info(f"[generate_episode_scripts] START {json.dumps(call_meta, ensure_ascii=False)}")

    try:
        project = _require_project_access(db, project_id, current_user)
    except HTTPException as e:
        logger.warning(f"[generate_episode_scripts] project access denied. project_id={project_id} user_id={current_user.id} detail={e.detail}")
        logger.info(
            f"[generate_episode_scripts] RESPONSE success=False status_code={e.status_code} project_id={project_id} detail={e.detail}"
        )
        raise

    user_id = int(current_user.id)
    user_name = str(current_user.username or "").strip()
    project_global_info = dict(project.global_info or {})
    gi_story_input = project_global_info.get("story_generator_global_input") if isinstance(project_global_info.get("story_generator_global_input"), dict) else {}
    gi_basic_info = project_global_info.get("basic_information") if isinstance(project_global_info.get("basic_information"), dict) else {}
    req_script_title_hint = _strip_stacked_production_title_suffixes(req.script_title)
    project_title = _strip_stacked_production_title_suffixes(
        project_global_info.get("script_title")
        or gi_story_input.get("script_title")
        or gi_basic_info.get("script_title")
        or _extract_script_title_from_story_dna_markdown(project_global_info.get("story_dna_global_md") or "")
        or req_script_title_hint
        or project.title
        or ""
    )
    if req_script_title_hint and _normalize_title_for_compare(project_title) == _normalize_title_for_compare(req_script_title_hint):
        project_title = _build_non_literal_script_title(
            seed_title=project_title,
            project_type=gi_basic_info.get("type") or project_global_info.get("type"),
            global_style=gi_basic_info.get("Global_Style") or project_global_info.get("Global_Style") or project_global_info.get("global_style"),
            base_positioning=gi_basic_info.get("base_positioning") or project_global_info.get("base_positioning"),
        )

    try:
        log_action(
            db,
            user_id=user_id,
            user_name=user_name,
            action="GENERATE_EPISODE_SCRIPTS_START",
            details=json.dumps(call_meta, ensure_ascii=False),
        )
    except Exception as e:
        logger.warning(f"[generate_episode_scripts] failed to write START system log: {e}")

    gi = dict(project_global_info)
    status_key = "episode_script_generation_status"

    def _persist_run_status(status_payload: Dict[str, Any]) -> None:
        status_db = SessionLocal()
        try:
            latest_project = status_db.query(Project).filter(Project.id == project_id).first()
            latest_gi = dict((latest_project.global_info if latest_project else {}) or {})
            existing_status = latest_gi.get(status_key) if isinstance(latest_gi.get(status_key), dict) else {}

            merged_status = dict(status_payload or {})
            has_incoming_force_flag = "force_stopped" in merged_status
            if bool(existing_status.get("force_stopped")) and not has_incoming_force_flag:
                merged_status["force_stopped"] = True

            if bool(existing_status.get("stop_requested")):
                merged_status["stop_requested"] = True
                if existing_status.get("stop_requested_at") and not merged_status.get("stop_requested_at"):
                    merged_status["stop_requested_at"] = existing_status.get("stop_requested_at")
                if not merged_status.get("stopped_by_user"):
                    merged_status["stopped_by_user"] = bool(existing_status.get("stopped_by_user"))

            if bool(merged_status.get("force_stopped")):
                now_iso = now_bj_iso()
                merged_status["running"] = False
                merged_status["status"] = "canceled"
                merged_status["stopped_by_user"] = True
                merged_status["finished_at"] = merged_status.get("finished_at") or now_iso
                merged_status["updated_at"] = now_iso
                if not merged_status.get("message"):
                    merged_status["message"] = "Force stopped"

            latest_gi[status_key] = status_payload
            if latest_project:
                latest_gi[status_key] = merged_status
                merged_results = merged_status.get("results") if isinstance(merged_status, dict) else []
                latest_item = merged_results[-1] if isinstance(merged_results, list) and merged_results else {}
                logger.info(
                    "[generate_episode_scripts] STATUS_PERSIST project_id=%s running=%s processed=%s generated=%s failed=%s skipped=%s results_count=%s latest_episode_id=%r latest_episode_number=%r latest_episode_title=%r latest_project_episode_title=%r latest_llm_episode_title=%r latest_status=%r",
                    project_id,
                    bool(merged_status.get("running")),
                    int(merged_status.get("processed") or 0),
                    int(merged_status.get("generated") or 0),
                    int(merged_status.get("failed") or 0),
                    int(merged_status.get("skipped") or 0),
                    len(merged_results) if isinstance(merged_results, list) else 0,
                    latest_item.get("episode_id") if isinstance(latest_item, dict) else None,
                    latest_item.get("episode_number") if isinstance(latest_item, dict) else None,
                    latest_item.get("episode_title") if isinstance(latest_item, dict) else None,
                    latest_item.get("project_episode_title") if isinstance(latest_item, dict) else None,
                    latest_item.get("llm_episode_title") if isinstance(latest_item, dict) else None,
                    latest_item.get("status") if isinstance(latest_item, dict) else None,
                )
                latest_project.global_info = latest_gi
                status_db.add(latest_project)
                status_db.commit()
        except Exception as e:
            logger.warning(f"[generate_episode_scripts] failed to persist run status: {e}")
        finally:
            status_db.close()

    def _read_run_status() -> Dict[str, Any]:
        status_db = SessionLocal()
        try:
            latest_project = status_db.query(Project).filter(Project.id == project_id).first()
            latest_gi = dict((latest_project.global_info if latest_project else {}) or {})
            latest_status = latest_gi.get(status_key)
            if isinstance(latest_status, dict):
                return dict(latest_status)
        except Exception as e:
            logger.warning(f"[generate_episode_scripts] failed to read run status: {e}")
        finally:
            status_db.close()
        return {}

    def _is_stop_requested() -> bool:
        latest_status = _read_run_status()
        return bool(latest_status.get("stop_requested"))

    generator_kind = _normalize_generator_kind(req.generator_kind) or "story"
    requested_episode_number: Optional[int] = None
    if req.episode_number is not None:
        try:
            requested_episode_number = int(req.episode_number)
        except Exception:
            raise HTTPException(status_code=400, detail="episode_number must be an integer")
        if requested_episode_number <= 0:
            raise HTTPException(status_code=400, detail="episode_number must be greater than 0")

    # Determine target episode count
    target_n: Optional[int] = None
    if req.episodes_count is not None:
        try:
            target_n = int(req.episodes_count)
        except Exception:
            logger.info(
                f"[generate_episode_scripts] RESPONSE success=False status_code=400 project_id={project_id} detail=episodes_count must be an integer"
            )
            raise HTTPException(status_code=400, detail="episodes_count must be an integer")
    else:
        try:
            input_key = "promo_generator_input" if generator_kind == "promo" else "story_generator_global_input"
            saved = (gi.get(input_key) or {}).get("episodes_count")
            if saved is not None:
                target_n = int(saved)
        except Exception:
            target_n = None

    if not target_n or target_n <= 0:
        if req.episode_id:
            target_n = 999  # Dummy fallback if targeting single episode
        elif requested_episode_number:
            target_n = int(requested_episode_number)
        else:
            logger.warning(
                f"[generate_episode_scripts] invalid episodes_count. project_id={project_id} user_id={current_user.id} req={req.episodes_count}"
            )
            try:
                log_action(
                    db,
                    user_id=user_id,
                    user_name=user_name,
                    action="GENERATE_EPISODE_SCRIPTS_FAILED",
                    details=f"project_id={project_id}; reason=invalid_episodes_count; req={req.episodes_count}",
                )
            except Exception as e:
                logger.warning(f"[generate_episode_scripts] failed to write FAILED system log: {e}")
            logger.info(
                f"[generate_episode_scripts] RESPONSE success=False status_code=400 project_id={project_id} detail=episodes_count is required"
            )
            raise HTTPException(status_code=400, detail="episodes_count is required (or generate/save Global Story first)")

    global_md_key = "promo_dna_global_md" if generator_kind == "promo" else "story_dna_global_md"
    global_md = str(gi.get(global_md_key) or "").strip()
    if not global_md:
        logger.warning(
            f"[generate_episode_scripts] missing global framework. project_id={project_id} user_id={current_user.id}"
        )
        try:
            log_action(
                db,
                user_id=user_id,
                user_name=user_name,
                action="GENERATE_EPISODE_SCRIPTS_FAILED",
                details=f"project_id={project_id}; reason=missing_global_framework",
            )
        except Exception as e:
            logger.warning(f"[generate_episode_scripts] failed to write FAILED system log: {e}")
        logger.info(
            f"[generate_episode_scripts] RESPONSE success=False status_code=400 project_id={project_id} detail=Generated Global Framework is empty"
        )
        raise HTTPException(status_code=400, detail=f"Generated Global Framework ({global_md_key}) is empty")

    story_input_key = "promo_generator_input" if generator_kind == "promo" else "story_generator_global_input"
    saved_story_input = gi.get(story_input_key) if isinstance(gi.get(story_input_key), dict) else {}
    episode_script_mode = _pick_first_text(
        req.script_mode,
        saved_story_input.get("script_mode"),
        gi_story_input.get("script_mode"),
    )
    episode_target_audience = _pick_first_text(
        req.target_audience,
        saved_story_input.get("target_audience"),
        gi_story_input.get("target_audience"),
    )
    episode_duration_minutes = _resolve_episode_duration_minutes(
        req.episode_duration_minutes
        if req.episode_duration_minutes is not None
        else saved_story_input.get("episode_duration_minutes")
        if saved_story_input.get("episode_duration_minutes") is not None
        else gi_story_input.get("episode_duration_minutes")
    )
    episode_product_specs_block = _build_episode_script_product_specs_block(
        episodes_count=target_n,
        episode_duration_minutes=episode_duration_minutes,
        script_mode=episode_script_mode,
        target_audience=episode_target_audience,
    )

    character_canon_md = str(gi.get("character_canon_md") or "").strip()
    if not character_canon_md:
        # Best-effort build from profiles
        profiles = gi.get("character_profiles") or []
        blocks: List[str] = []
        if isinstance(profiles, list):
            for p in profiles:
                if not isinstance(p, dict):
                    continue
                name = str(p.get("name") or "").strip()
                md = str(p.get("description_md") or "").strip()
                if name and md:
                    blocks.append(f"## {name}\n\n{md}")
        character_canon_md = "\n\n".join(blocks).strip()

    if not character_canon_md:
        logger.warning(
            f"[generate_episode_scripts] missing character canon (allowed). project_id={project_id} user_id={current_user.id}"
        )

    relationships = str(gi.get("character_relationships") or "").strip()
    has_relationships = bool(relationships)
    constraints_obj: Dict[str, Any] = {}
    constraints_block = ""
    if str(gi.get("character_canon_md") or "").strip():
        character_canon_source = "character_canon_md"
    elif character_canon_md:
        character_canon_source = "character_profiles_fallback"
    else:
        character_canon_source = "empty"

    logger.info(
        "[generate_episode_scripts] INPUT_CONTEXT "
        f"project_id={project_id} user_id={current_user.id} "
        f"has_relationships={has_relationships} global_md_len={len(global_md)} "
        f"character_canon_len={len(character_canon_md)} character_source={character_canon_source} "
        f"script_mode={episode_script_mode!r} target_audience={episode_target_audience!r} "
        f"episodes_count={target_n} episode_duration_minutes={episode_duration_minutes}"
    )

    # Single stable prompt entry for episode script generation.
    prompt_filename = "master_episode_writer.md"
    try:
        sys_prompt = _resolve_prompt_text(prompt_filename)
    except FileNotFoundError:
        logger.error("Episode script generator prompt not found: %s", prompt_filename)
        logger.info(
            f"[generate_episode_scripts] RESPONSE success=False status_code=404 project_id={project_id} detail=Prompt file {prompt_filename} not found"
        )
        raise HTTPException(status_code=404, detail=f"Prompt file '{prompt_filename}' not found.")

    # Ensure episodes exist with stable numeric mapping.
    # Priority: explicit episode_info number -> parse from title -> create missing.
    existing_eps = (
        db.query(Episode)
        .filter(
            Episode.project_id == project_id,
            _active_episode_clause(),
        )
        .order_by(Episode.id.asc())
        .all()
    )

    def _safe_positive_int(value: Any) -> Optional[int]:
        try:
            num = int(value)
            return num if num > 0 else None
        except Exception:
            return None

    def _extract_episode_index(ep: Episode) -> Optional[int]:
        ep_info = _episode_runtime_info_from_episode(ep)
        for key in (
            "episode_script_episode_number",
            "story_dna_episode_number",
            "episode_number",
            "index",
        ):
            num = _safe_positive_int(ep_info.get(key) if isinstance(ep_info, dict) else None)
            if num:
                return num

        title = str(ep.title or "")
        m = re.search(r"(?:Episode|EP)\s*[-_#]?\s*(\d+)", title, flags=re.IGNORECASE)
        if m:
            return _safe_positive_int(m.group(1))

        m = re.search(r"第\s*(\d+)\s*集", title)
        if m:
            return _safe_positive_int(m.group(1))

        return None

    def _is_placeholder_episode_title(title: Any, episode_number: Optional[int] = None) -> bool:
        value = str(title or "").strip()
        if not value:
            return True
        compact = re.sub(r"\s+", "", value).lower()
        if compact in {"untitled", "tbd", "episode", "第集"}:
            return True

        candidates: List[str] = []
        if episode_number and int(episode_number) > 0:
            n = int(episode_number)
            candidates.extend([
                f"episode{n}",
                f"ep{n}",
                f"ep{n:02d}",
                f"第{n}集",
                f"第{n}话",
                f"第{n}章",
                f"第{n}回",
            ])

        if compact in candidates:
            return True

        if re.fullmatch(r"(?:episode|ep)0*\d+", compact):
            return True
        if re.fullmatch(r"第\d+[集话章回]", compact):
            return True
        return False

    by_idx: Dict[int, Episode] = {}
    idx_candidates: Dict[int, List[int]] = {}
    by_title: Dict[str, Episode] = {}
    for ep in existing_eps:
        title_key = str(ep.title or "").strip().lower()
        if title_key and title_key not in by_title:
            by_title[title_key] = ep

        idx_num = _extract_episode_index(ep)
        if idx_num:
            idx_candidates.setdefault(int(idx_num), []).append(int(ep.id))
            if idx_num not in by_idx:
                by_idx[idx_num] = ep

    def _bind_episode_index(ep: Episode, idx_value: int) -> None:
        if not ep or not idx_value:
            return
        info = _episode_runtime_info_from_episode(ep)
        current = _safe_positive_int(info.get("episode_script_episode_number") if isinstance(info, dict) else None)
        if current == int(idx_value):
            return
        info["episode_script_episode_number"] = int(idx_value)
        ep.episode_info = info
        db.add(ep)
        db.commit()
        db.refresh(ep)

    # Fallback mapping for legacy projects: if titles were renamed without numeric prefix,
    # keep existing episode rows and assign missing indexes by stable DB order before creating any new rows.
    mapped_ids = {int(ep.id) for ep in by_idx.values() if ep is not None}
    unmapped_eps = [ep for ep in existing_eps if int(ep.id) not in mapped_ids]
    if unmapped_eps:
        upper_bound = max(int(target_n or 0), len(existing_eps), int(requested_episode_number or 0))
        next_unmapped_idx = 0
        for slot in range(1, upper_bound + 1):
            if slot in by_idx:
                continue
            if next_unmapped_idx >= len(unmapped_eps):
                break
            ep = unmapped_eps[next_unmapped_idx]
            next_unmapped_idx += 1
            _bind_episode_index(ep, slot)
            by_idx[slot] = ep
            idx_candidates.setdefault(int(slot), []).append(int(ep.id))

    logger.info(
        "[generate_episode_scripts] EPISODE_INDEX_MAP project_id=%s existing=%s mapped=%s unmapped_after_fallback=%s target_n=%s requested_episode_number=%r",
        project_id,
        len(existing_eps),
        len(by_idx),
        max(0, len(existing_eps) - len(by_idx)),
        target_n,
        requested_episode_number,
    )

    created_episodes: List[int] = []
    episodes_in_order: List[Episode] = []

    # Strict single-episode mode: never auto-create episodes before target resolution.
    single_episode_mode = bool(requested_episode_number is not None or req.episode_id)
    loop_limit = 0 if single_episode_mode else (target_n if target_n != 999 else 0)
    for i in range(1, loop_limit + 1):
        title = f"Episode {i}"
        ep = by_idx.get(i)
        if not ep:
            ep = by_title.get(title.strip().lower())
        if not ep:
            ep = by_title.get(f"第{i}集")
        if not ep:
            ep = Episode(project_id=project_id, title=title, script_content="")
            ep_info = _episode_runtime_info_from_episode(ep)
            ep_info["episode_script_episode_number"] = int(i)
            ep.episode_info = ep_info
            db.add(ep)
            db.commit()
            db.refresh(ep)
            created_episodes.append(ep.id)
            by_title[title.strip().lower()] = ep
            by_idx[i] = ep
        else:
            ep_info = _episode_runtime_info_from_episode(ep)
            if _safe_positive_int(ep_info.get("episode_script_episode_number") if isinstance(ep_info, dict) else None) is None:
                ep_info["episode_script_episode_number"] = int(i)
                ep.episode_info = ep_info
                db.add(ep)
                db.commit()
                db.refresh(ep)
        episodes_in_order.append(ep)

    previous_status = gi.get(status_key) if isinstance(gi.get(status_key), dict) else {}
    if isinstance(previous_status, dict) and bool(previous_status.get("running")):
        logger.info(
            f"[generate_episode_scripts] RESPONSE success=False status_code=409 project_id={project_id} detail=Episode script generation already running"
        )
        raise HTTPException(status_code=409, detail="Episode script generation is already running")

    failed_episode_ids: set[int] = set()
    previous_results = previous_status.get("results") if isinstance(previous_status, dict) else []
    if isinstance(previous_results, list):
        for item in previous_results:
            if not isinstance(item, dict):
                continue
            if str(item.get("status") or "") != "failed":
                continue
            try:
                ep_id_temp = int(item.get("episode_id"))
                failed_episode_ids.add(ep_id_temp)
            except Exception:
                continue

    episodes_data: List[Dict[str, Any]] = [
        {"idx": n, "id": ep.id, "title": ep.title, "script_content": ep.script_content}
        for n, ep in enumerate(episodes_in_order, start=1)
    ]

    target_episode_id: Optional[int] = None
    target_resolution_source = "none"
    target_episode_id_from_number: Optional[int] = None
    if requested_episode_number:
        candidate_ids = idx_candidates.get(int(requested_episode_number), [])
        if len(candidate_ids) > 1:
            logger.error(
                "[generate_episode_scripts] TARGET_RESOLUTION_AMBIGUOUS project_id=%s requested_episode_number=%s candidate_episode_ids=%s",
                project_id,
                requested_episode_number,
                candidate_ids,
            )
            raise HTTPException(
                status_code=409,
                detail=(
                    f"episode_number={requested_episode_number} is ambiguous; matched multiple episodes: {candidate_ids}. "
                    "Please clean up duplicate numbering before retrying."
                ),
            )
        ep_by_number = by_idx.get(int(requested_episode_number))
        if ep_by_number:
            target_episode_id_from_number = int(ep_by_number.id)
            target_episode_id = target_episode_id_from_number
            target_resolution_source = "episode_number"

    if req.episode_id:
        req_episode_id_int = int(req.episode_id)
        if requested_episode_number and target_episode_id_from_number is None:
            logger.error(
                "[generate_episode_scripts] TARGET_EPISODE_CONFLICT project_id=%s requested_episode_number=%s provided_episode_id=%s decision=reject_reason=episode_number_not_resolved",
                project_id,
                requested_episode_number,
                req_episode_id_int,
            )
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Cannot safely resolve episode_number={requested_episode_number} to a unique episode. "
                    "Refusing provided episode_id to avoid wrong overwrite."
                ),
            )

        if target_episode_id is None:
            target_episode_id = req_episode_id_int
            target_resolution_source = "episode_id"
        elif req_episode_id_int != target_episode_id:
            logger.error(
                "[generate_episode_scripts] TARGET_EPISODE_CONFLICT "
                f"project_id={project_id} requested_episode_number={requested_episode_number} "
                f"resolved_episode_id_by_number={target_episode_id} provided_episode_id={req_episode_id_int} "
                "decision=reject_conflict"
            )
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Conflict between episode_number={requested_episode_number} and episode_id={req_episode_id_int}. "
                    "Refusing to continue to prevent wrong overwrite."
                ),
            )

    call_meta["target_resolution_source"] = target_resolution_source
    call_meta["target_episode_id"] = target_episode_id

    if requested_episode_number and target_episode_id_from_number is None:
        if req.episode_id:
            logger.error(
                "[generate_episode_scripts] TARGET_RESOLUTION_FAILED project_id=%s requested_episode_number=%s provided_episode_id=%r reason=episode_number_not_resolved_refuse_fallback",
                project_id,
                requested_episode_number,
                int(req.episode_id) if req.episode_id else None,
            )
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Cannot safely resolve episode_number={requested_episode_number} to a unique episode. "
                    "Refusing fallback to episode_id to avoid wrong overwrite. "
                    "Please refresh episodes and retry."
                ),
            )

        # Single-episode generation with a non-existing episode number should auto-create that episode.
        create_idx = int(requested_episode_number)
        created_ep = Episode(project_id=project_id, title=f"Episode {create_idx}", script_content="")
        created_info = _episode_runtime_info_from_episode(created_ep)
        created_info["episode_script_episode_number"] = int(create_idx)
        created_ep.episode_info = created_info
        db.add(created_ep)
        db.commit()
        db.refresh(created_ep)

        created_episodes.append(int(created_ep.id))
        by_idx[create_idx] = created_ep
        idx_candidates.setdefault(create_idx, []).append(int(created_ep.id))
        by_title[str(created_ep.title or "").strip().lower()] = created_ep

        target_episode_id_from_number = int(created_ep.id)
        target_episode_id = target_episode_id_from_number
        target_resolution_source = "episode_number_autocreate"
        episodes_data.append({
            "idx": create_idx,
            "id": int(created_ep.id),
            "title": created_ep.title,
            "script_content": created_ep.script_content,
        })
        logger.info(
            "[generate_episode_scripts] TARGET_AUTOCREATED project_id=%s requested_episode_number=%s created_episode_id=%s",
            project_id,
            requested_episode_number,
            int(created_ep.id),
        )

    resolved_target_title = None
    if target_episode_id:
        for _ed in episodes_data:
            if int(_ed.get("id") or 0) == int(target_episode_id):
                resolved_target_title = _ed.get("title")
                break
        if resolved_target_title is None:
            _target_ep_dbg = db.query(Episode).filter(Episode.id == int(target_episode_id)).first()
            if _target_ep_dbg is not None:
                resolved_target_title = _target_ep_dbg.title
    logger.info(
        "[generate_episode_scripts] TARGET_RESOLUTION project_id=%s requested_episode_number=%r provided_episode_id=%r resolved_episode_id=%r source=%s resolved_title=%r",
        project_id,
        requested_episode_number,
        int(req.episode_id) if req.episode_id else None,
        target_episode_id,
        target_resolution_source,
        resolved_target_title,
    )

    if target_episode_id:
        episodes_data = [ed for ed in episodes_data if ed["id"] == target_episode_id]
        if not episodes_data:
            # Maybe the episode is not in the first N episodes but exists in DB
            target_ep = db.query(Episode).filter(Episode.id == target_episode_id, Episode.project_id == project_id).first()
            if target_ep:
                parsed_idx = _extract_episode_index(target_ep)
                fallback_idx = 1
                if isinstance(target_n, int) and target_n != 999:
                    fallback_idx = target_n + 1
                if requested_episode_number:
                    idx = int(requested_episode_number)
                else:
                    idx = int(parsed_idx) if parsed_idx else fallback_idx
                episodes_data = [{"idx": idx, "id": target_ep.id, "title": target_ep.title, "script_content": target_ep.script_content}]
            else:
                raise HTTPException(status_code=404, detail="Target episode not found in this project.")
    elif req.retry_failed_only:
        episodes_data = [ed for ed in episodes_data if ed["id"] in failed_episode_ids]

    # Single-episode generation should always overwrite the target episode,
    # even if a caller accidentally sends overwrite_existing=false.
    effective_overwrite_existing = bool(req.overwrite_existing) or bool(target_episode_id)
    call_meta["overwrite_existing_effective"] = effective_overwrite_existing

    run_status = {
        "project_id": project_id,
        "running": True,
        "prompt_filename": prompt_filename,
        "mode": "retry_failed_only" if req.retry_failed_only else "full",
        "overwrite_existing_effective": effective_overwrite_existing,
        "started_at": started_at_iso,
        "updated_at": started_at_iso,
        "episodes_target": target_n,
        "episodes_in_run": len(episodes_data),
        "processed": 0,
        "generated": 0,
        "failed": 0,
        "skipped": 0,
        "stop_requested": False,
        "stop_requested_at": None,
        "stopped_by_user": False,
        "results": [],
    }

    if req.retry_failed_only and len(episodes_data) == 0:
        run_status["running"] = False
        run_status["finished_at"] = now_bj_iso()
        run_status["message"] = "No failed episodes found from previous run"
        _persist_run_status(run_status)
        return {
            "success": True,
            "generation_success": True,
            "project_id": project_id,
            "episodes_target": target_n,
            "episodes_created": len(created_episodes),
            "created_episode_ids": created_episodes,
            "results": [],
            "errors": [],
            "message": "No failed episodes to retry",
            "debug_context": {
                "retry_failed_only": True,
                "previous_failed_count": len(failed_episode_ids),
            },
        }

    _persist_run_status(run_status)

    llm_config = _resolve_story_generator_script_analysis_llm_config(
        db,
        user_id,
        function_name=(getattr(req, "function_name", None) or "script_analysis"),
        system_api_id=getattr(req, "system_api_id", None),
        context="generate_episode_scripts",
        project_global_info=project_global_info,
        user_name=current_user.username,
        project_id=project_id,
        action_name="生成分集剧本",
    )
    if not llm_config or not (llm_config.get("api_key") or "").strip():
        raise HTTPException(status_code=400, detail="No valid LLM API key configured in active settings")
    provider = llm_config.get("provider") if llm_config else None
    model = llm_config.get("model") if llm_config else None

    results: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    def _safe_log_episode(action: str, payload: Dict[str, Any]) -> None:
        log_db = SessionLocal()
        try:
            log_action(
                log_db,
                user_id=user_id,
                user_name=user_name,
                action=action,
                details=json.dumps(payload, ensure_ascii=False),
            )
        except Exception as e:
            logger.warning(f"[generate_episode_scripts] failed to write {action} system log: {e}")
        finally:
            log_db.close()

    for ep_data in episodes_data:
        idx = ep_data["idx"]
        ep_id = ep_data["id"]
        ep_title = ep_data["title"]
        ep_script_content = ep_data["script_content"]
        if _is_stop_requested():
            stopped_at = now_bj_iso()
            run_status["stop_requested"] = True
            if not run_status.get("stop_requested_at"):
                run_status["stop_requested_at"] = stopped_at
            run_status["stopped_by_user"] = True
            run_status["stopped_at_episode_number"] = idx
            run_status["stop_acknowledged_at"] = stopped_at
            run_status["message"] = "Stopped by user request"

            remaining = [ed for ed in episodes_data if ed["idx"] >= idx]
            for ep_rest in remaining:
                j = ep_rest["idx"]
                results.append({
                    "episode_id": ep_rest["id"],
                    "episode_number": j,
                    "episode_title": ep_rest["title"],
                    "generated": False,
                    "skipped": True,
                    "reason": "stopped by user request",
                })
                run_status["processed"] = int(run_status.get("processed") or 0) + 1
                run_status["skipped"] = int(run_status.get("skipped") or 0) + 1
                run_status["results"].append({
                    "episode_id": ep_rest["id"],
                    "episode_number": j,
                    "episode_title": ep_rest["title"],
                    "status": "skipped",
                    "reason": "stopped by user request",
                })

            run_status["updated_at"] = stopped_at
            _persist_run_status(run_status)
            _safe_log_episode("GENERATE_EPISODE_SCRIPTS_ABORTED", {
                "project_id": project_id,
                "stopped_at_episode_number": idx,
                "reason": "stopped by user request",
            })
            break

        should_write = True
        if not req.retry_failed_only and not effective_overwrite_existing and (ep_script_content or "").strip():
            should_write = False

        if not should_write:
            logger.info(
                f"[generate_episode_scripts] SKIP episode_number={idx} episode_id={ep_id} title={ep_title!r} reason=existing_script"
            )
            logger.info(
                "[generate_episode_scripts] SKIP_DIAGNOSTICS "
                f"episode_number={idx} episode_id={ep_id} "
                f"target_episode_id={target_episode_id} "
                f"retry_failed_only={bool(req.retry_failed_only)} "
                f"overwrite_existing_requested={bool(req.overwrite_existing)} "
                f"overwrite_existing_effective={bool(effective_overwrite_existing)} "
                f"has_existing_script={bool((ep_script_content or '').strip())}"
            )
            _safe_log_episode("GENERATE_EPISODE_SCRIPT_SKIP", {
                "project_id": project_id,
                "episode_number": idx,
                "episode_id": ep_id,
                "episode_title": ep_title,
                "reason": "script_content already exists",
                "target_episode_id": target_episode_id,
                "retry_failed_only": bool(req.retry_failed_only),
                "overwrite_existing_requested": bool(req.overwrite_existing),
                "overwrite_existing_effective": bool(effective_overwrite_existing),
                "has_existing_script": bool((ep_script_content or "").strip()),
            })
            results.append({
                "episode_id": ep_id,
                "episode_number": idx,
                "episode_title": ep_title,
                "generated": False,
                "skipped": True,
                "reason": "script_content already exists",
            })
            run_status["processed"] = int(run_status.get("processed") or 0) + 1
            run_status["skipped"] = int(run_status.get("skipped") or 0) + 1
            run_status["updated_at"] = now_bj_iso()
            run_status["results"].append({
                "episode_id": ep_id,
                "episode_number": idx,
                "episode_title": ep_title,
                "status": "skipped",
                "reason": "script_content already exists",
            })
            _persist_run_status(run_status)
            continue

        reservation_tx = None

        relationships_block = ""
        if relationships:
            relationships_block = f"Character Relationships (Plain Text):\n{relationships}\n\n"

        episode_title_is_placeholder = _is_placeholder_episode_title(ep_title, idx)
        if episode_title_is_placeholder:
            episode_title_policy_block = (
                "Episode Title Policy (Hard Constraint):\n"
                f"- Current DB title is a placeholder: {ep_title}\n"
                "- You MUST create a specific, plot-relevant episode title in the H1 heading.\n"
                "- Do NOT output placeholder titles such as 'Episode N', 'EPN', '第N集', 'Untitled', or 'TBD'.\n\n"
            )
        else:
            episode_title_policy_block = (
                "Episode Title Policy (Hard Constraint):\n"
                f"- Current DB title reference: {ep_title}\n"
                "- Keep or refine this title, but keep it specific and plot-relevant.\n"
                "- Do NOT output placeholder titles such as 'Episode N', 'EPN', '第N集', 'Untitled', or 'TBD'.\n\n"
            )

        generation_scope_block = (
            "Generation Scope (Hard Constraint):\n"
            f"- Requested Episodes Count Input: {target_n}\n"
            f"- Episodes In Current Run: {len(episodes_data)}\n"
            f"- Current Call Episode Number: {idx}\n"
            f"- Current Call Episode Title: {ep_title}\n"
            "- You must generate ONLY the current call episode above.\n"
            "- Do NOT generate content for any other episode number in this response.\n"
            "- Any information about other episodes is reference context only.\n"
            "- Even in batch generation mode, each call must output exactly one episode script (the current episode only).\n\n"
            "Output Format Contract (Hard Constraint):\n"
            f"- The first non-empty line MUST be exactly one H1 heading: # {idx}-{{episode_title}}\n"
            "- Output MUST be pure Markdown text only.\n"
            "- Do NOT output JSON, XML, YAML, code fences, or any wrapper text.\n"
            "- Do NOT output any preface, analysis, explanation, or postscript.\n"
            "- The response MUST contain exactly one episode H1 heading; do NOT include any second episode heading.\n"
            "- Do NOT include headings for other episode numbers (e.g., 第X集 / EPX / Episode X).\n"
            "- Keep all content strictly within the current episode scope.\n\n"
        )

        script_title_policy_block = (
            "Script Title Policy (Hard Constraint):\n"
            f"- Canonical Script Title (fixed for this run): {project_title}\n"
            "- Treat this script title as immutable context for all generated output in this call.\n"
            "- Do NOT replace, rename, or invent another project-level script title.\n\n"
        )

        prev_episode_block = ""
        if idx > 1:
            prev_ep = by_idx.get(idx - 1)
            _prev_ep_db = db.query(Episode).filter(Episode.id == prev_ep.id).first() if prev_ep else None
            if not _prev_ep_db:
                 prev_ep_id_temp = next((ed["id"] for ed in episodes_data if ed.get("idx") == idx - 1), None)
                 if prev_ep_id_temp:
                     _prev_ep_db = db.query(Episode).get(prev_ep_id_temp)
            
            p_text = getattr(_prev_ep_db, "script_content", None) or getattr(prev_ep, "script_content", None)
            if p_text and p_text.strip():
                p_text_clean = p_text.strip()
                last_500 = p_text_clean[-500:]
                prev_episode_block = (
                    "Previous Episode Context (Constraint):\n"
                    f"- The previous episode (Episode {idx - 1}) script ends with the following text.\n"
                    "- You must ensure the opening of the current episode (Episode {idx}) connects logically with this ending.\n"
                    "```markdown\n"
                    f"...{last_500}\n"
                    "```\n\n"
                )

        episode_language = _pick_first_text(
            gi_basic_info.get("language"),
            gi_story_input.get("language"),
            project_global_info.get("language"),
        )
        reference_search_block = await _prepare_episode_script_reference_block(
            user_id=user_id,
            project_global_info=project_global_info,
            llm_config=llm_config,
            global_md=global_md,
            episode_number=idx,
            project_title=project_title,
            language=episode_language,
        )

        user_prompt = (
            f"Project Title: {project_title}\n"
            f"Episode Number: {idx}\n"
            f"Episode Title (current DB value): {ep_title}\n"
            f"Extra Notes: {req.extra_notes or ''}\n\n"
            f"{episode_product_specs_block}"
            f"{script_title_policy_block}"
            f"{generation_scope_block}"
            f"{episode_title_policy_block}"
            f"{prev_episode_block}"
            f"Global Story DNA (Markdown):\n{global_md}\n\n"
            f"Character Canon (Markdown):\n{character_canon_md}\n\n"
            f"{relationships_block}"
        )
        if reference_search_block.strip():
            user_prompt += (
                "Episode Reference Research (MUST consult before writing; localize, do not copy verbatim):\n"
                f"{reference_search_block}\n\n"
            )
        user_prompt += "Write the episode script draft now."

        try:
            sys_prompt_episode = sys_prompt.format(episode_number=idx, episode_title=ep_title)
        except Exception:
            sys_prompt_episode = sys_prompt

        if billing_service.is_token_pricing(db, "llm_chat", provider, model):
            est = billing_service.estimate_reserve_tokens_from_messages(
                [
                    {"role": "system", "content": sys_prompt_episode},
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
                    "item": "generate_episode_script",
                    "episode_id": ep_id,
                    "episode_number": idx,
                    "estimation_method": "prompt_tokens_ratio",
                    "estimated_output_ratio": billing_service.RESERVE_OUTPUT_RATIO,
                    "input_tokens": est.get("input_tokens", 0),
                    "output_tokens": est.get("output_tokens", 0),
                    "total_tokens": est.get("total_tokens", 0),
                },
            )
        else:
            billing_service.check_balance(db, user_id, "llm_chat", provider, model)

        try:
            logger.info(
                f"[generate_episode_scripts] GENERATE episode_number={idx} episode_id={ep_id} title={ep_title!r}"
            )
            logger.info(
                f"[generate_episode_scripts] REQUEST_PAYLOAD episode_number={idx} episode_id={ep_id} "
                f"user_prompt_len={len(user_prompt)} sys_prompt_len={len(sys_prompt_episode)} "
                f"has_constraints_block={bool(constraints_block)} has_relationships_block={bool(relationships_block)} "
                f"has_reference_search_block={bool(reference_search_block)} reference_search_block_len={len(reference_search_block or '')}"
            )
            _release_db_connection(db, f"generate_episode_scripts_episode_{ep_id}_llm_call")
            generated_payload = await generate_markdown_with_retry(
                user_prompt=user_prompt,
                sys_prompt=sys_prompt_episode,
                llm_config=llm_config,
                strict_markdown=(req.strict_markdown is not False),
                require_h1=True,
                return_meta=True,
            )
            content = str((generated_payload or {}).get("content") or "").strip()
            if not content:
                raise RuntimeError("LLM returned empty content")

            content_first_line = ""
            for _line in content.splitlines():
                _candidate = str(_line or "").strip()
                if _candidate:
                    content_first_line = _candidate
                    break
            parsed_heading = _parse_episode_heading_from_markdown(content)
            llm_episode_number = parsed_heading.get("episode_number")
            llm_episode_title = str(parsed_heading.get("episode_title") or ep_title or "").strip()
            llm_heading = str(parsed_heading.get("raw_heading") or "").strip()
            logger.info(
                "[generate_episode_scripts] HEADING_PARSE episode_number=%s episode_id=%s project_episode_title=%r first_line=%r parsed_heading=%s llm_episode_number=%r llm_episode_title=%r used_project_title_fallback=%s",
                idx,
                ep_id,
                ep_title,
                content_first_line,
                json.dumps(parsed_heading, ensure_ascii=False),
                llm_episode_number,
                llm_episode_title,
                not bool(parsed_heading.get("episode_title")),
            )
            title_mismatch = bool(llm_episode_number) and int(llm_episode_number) != int(idx)
            if title_mismatch:
                logger.error(
                    f"[generate_episode_scripts] EPISODE_TITLE_MISMATCH_BLOCKED project_episode_number={idx} llm_episode_number={llm_episode_number} episode_id={ep_id} raw_heading={llm_heading!r}"
                )
                raise RuntimeError(
                    f"LLM episode heading mismatch: expected episode {idx}, got episode {llm_episode_number}. Import blocked."
                )

            usage = (generated_payload or {}).get("usage") if isinstance(generated_payload, dict) else {}
            if not usage:
                usage = billing_service.estimate_input_output_tokens_from_messages(
                    [
                        {"role": "system", "content": sys_prompt_episode},
                        {"role": "user", "content": user_prompt},
                        {"role": "assistant", "content": content},
                    ],
                    output_ratio=1.0,
                )
            billing_details = {
                "item": "generate_episode_script",
                "episode_id": ep_id,
                "episode_number": idx,
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

            persist_db = SessionLocal()
            try:
                if reservation_tx:
                    billing_service.settle_reservation(persist_db, _reservation_tx_id(reservation_tx), billing_details)
                else:
                    billing_service.deduct_credits(persist_db, user_id, "llm_chat", provider, model, billing_details)

                ep_db = persist_db.query(Episode).get(ep_id)
                if not ep_db:
                    raise RuntimeError(f"Episode {ep_id} not found in database for update.")
                previous_title = str(ep_db.title or "")
                ep_db.script_content = content
                if llm_episode_title:
                    ep_db.title = llm_episode_title
                ep_script_content = content
                ei = _episode_runtime_info_from_episode(ep_db)
                ei["episode_script_generated_at"] = now_bj_iso()
                ei["episode_script_episode_number"] = int(idx)
                if llm_episode_title:
                    ei["episode_title"] = llm_episode_title
                if generator_kind == "promo":
                    ei["episode_script_source"] = "promo_global_framework_plus_project_character_canon"
                else:
                    ei["episode_script_source"] = "project_global_framework_plus_project_character_canon"
                ep_db.episode_info = ei
                logger.info(
                    "[generate_episode_scripts] PERSIST_PREPARE episode_number=%s episode_id=%s previous_title=%r next_title=%r episode_info_title=%r script_chars=%s",
                    idx,
                    ep_id,
                    previous_title,
                    str(ep_db.title or ""),
                    str(ei.get("episode_title") or ""),
                    len(content),
                )
                persist_db.add(ep_db)
                persist_db.commit()
                persist_db.refresh(ep_db)

                persisted_episode_info = _episode_runtime_info_from_episode(ep_db)
                logger.info(
                    "[generate_episode_scripts] PERSISTED_READBACK episode_number=%s episode_id=%s db_title=%r episode_info_title=%r script_chars=%s",
                    idx,
                    ep_id,
                    str(ep_db.title or ""),
                    str(persisted_episode_info.get("episode_title") or ""),
                    len(str(ep_db.script_content or "")),
                )
            finally:
                persist_db.close()

            logger.info(
                f"[generate_episode_scripts] SUCCESS episode_number={idx} episode_id={ep_id} output_chars={len(content)}"
            )
            _safe_log_episode("GENERATE_EPISODE_SCRIPT_SUCCESS", {
                "project_id": project_id,
                "episode_number": idx,
                "episode_id": ep_id,
                "episode_title": ep_title,
                "llm_episode_number": llm_episode_number,
                "llm_episode_title": llm_episode_title,
                "title_mismatch": title_mismatch,
                "output_chars": len(content),
            })

            results.append({
                "episode_id": ep_id,
                "episode_number": idx,
                "project_episode_title": ep_title,
                "episode_title": llm_episode_title,
                "llm_episode_number": llm_episode_number,
                "llm_episode_title": llm_episode_title,
                "title_mismatch": title_mismatch,
                "generated": True,
                "skipped": False,
                "output_chars": len(content),
            })
            run_status["processed"] = int(run_status.get("processed") or 0) + 1
            run_status["generated"] = int(run_status.get("generated") or 0) + 1
            run_status["updated_at"] = now_bj_iso()
            run_status["results"].append({
                "episode_id": ep_id,
                "episode_number": idx,
                "project_episode_title": ep_title,
                "episode_title": llm_episode_title,
                "llm_episode_number": llm_episode_number,
                "llm_episode_title": llm_episode_title,
                "title_mismatch": title_mismatch,
                "status": "generated",
                "output_chars": len(content),
            })
            _persist_run_status(run_status)
        except HTTPException:
            if reservation_tx:
                cancel_db = SessionLocal()
                try:
                    billing_service.cancel_reservation(cancel_db, _reservation_tx_id(reservation_tx), "episode generation HTTPException")
                finally:
                    cancel_db.close()
            raise
        except Exception as e:
            if reservation_tx:
                cancel_db = SessionLocal()
                try:
                    billing_service.cancel_reservation(cancel_db, _reservation_tx_id(reservation_tx), str(e))
                finally:
                    cancel_db.close()
            logger.exception(f"[generate_episode_scripts] FAILED episode_number={idx} episode_id={ep_id} error={e}")
            _safe_log_episode("GENERATE_EPISODE_SCRIPT_FAILED", {
                "project_id": project_id,
                "episode_number": idx,
                "episode_id": ep_id,
                "episode_title": ep_title,
                "error": str(e),
            })
            errors.append({
                "episode_number": idx,
                "episode_id": ep_id,
                "episode_title": ep_title,
                "error": str(e),
            })
            results.append({
                "episode_id": ep_id,
                "episode_number": idx,
                "episode_title": ep_title,
                "generated": False,
                "skipped": False,
                "error": str(e),
            })
            run_status["processed"] = int(run_status.get("processed") or 0) + 1
            run_status["failed"] = int(run_status.get("failed") or 0) + 1
            run_status["updated_at"] = now_bj_iso()
            run_status["results"].append({
                "episode_id": ep_id,
                "episode_number": idx,
                "episode_title": ep_title,
                "status": "failed",
                "error": str(e),
            })
            _persist_run_status(run_status)

            if "PROHIBITED_CONTENT" in str(e):
                logger.warning(
                    f"[generate_episode_scripts] ABORT remaining episodes due to provider moderation block at episode_number={idx}"
                )
                _safe_log_episode("GENERATE_EPISODE_SCRIPTS_ABORTED", {
                    "project_id": project_id,
                    "stopped_at_episode_number": idx,
                    "reason": "provider moderation block (PROHIBITED_CONTENT)",
                })
                remaining = [ed for ed in episodes_data if ed["idx"] > idx]
                for ep_rest in remaining:
                    j = ep_rest["idx"]
                    results.append({
                        "episode_id": ep_rest["id"],
                        "episode_number": j,
                        "episode_title": ep_rest["title"],
                        "generated": False,
                        "skipped": True,
                        "reason": "aborted due to provider moderation block",
                    })
                    run_status["processed"] = int(run_status.get("processed") or 0) + 1
                    run_status["skipped"] = int(run_status.get("skipped") or 0) + 1
                    run_status["results"].append({
                        "episode_id": ep_rest["id"],
                        "episode_number": j,
                        "episode_title": ep_rest["title"],
                        "status": "skipped",
                        "reason": "aborted due to provider moderation block",
                    })
                run_status["updated_at"] = now_bj_iso()
                _persist_run_status(run_status)
                break

    duration_ms = int((datetime.utcnow() - started_at).total_seconds() * 1000)
    logger.info(
        f"[generate_episode_scripts] END project_id={project_id} user_id={user_id} "
        f"target={target_n} created={len(created_episodes)} generated={sum(1 for r in results if r.get('generated'))} "
        f"errors={len(errors)} duration_ms={duration_ms}"
    )

    try:
        summary = {
            "project_id": project_id,
            "target": target_n,
            "created": len(created_episodes),
            "generated": sum(1 for r in results if r.get("generated")),
            "errors": len(errors),
            "duration_ms": duration_ms,
        }
        end_log_db = SessionLocal()
        try:
            log_action(
                end_log_db,
                user_id=user_id,
                user_name=user_name,
                action="GENERATE_EPISODE_SCRIPTS_END",
                details=json.dumps(summary, ensure_ascii=False),
            )
        finally:
            end_log_db.close()
    except Exception as e:
        logger.warning(f"[generate_episode_scripts] failed to write END system log: {e}")

    response_payload = {
        "success": True,
        "generation_success": len(errors) == 0,
        "project_id": project_id,
        "episodes_target": target_n,
        "episodes_generated": sum(1 for r in results if r.get("generated")),
        "episodes_created": len(created_episodes),
        "created_episode_ids": created_episodes,
        "results": results,
        "errors": errors,
        "debug_context": {
            "has_character_relationships": has_relationships,
            "has_global_story_dna": bool(global_md),
            "character_canon_source": character_canon_source,
            "global_story_dna_length": len(global_md),
            "character_canon_length": len(character_canon_md),
            "constraints_keys": list(constraints_obj.keys()) if isinstance(constraints_obj, dict) else [],
            "script_mode": episode_script_mode,
            "target_audience": episode_target_audience,
            "episodes_count": target_n,
            "episode_duration_minutes": episode_duration_minutes,
        },
    }

    run_status["running"] = False
    run_status["finished_at"] = now_bj_iso()
    run_status["updated_at"] = run_status["finished_at"]
    run_status["errors"] = errors
    run_status["generation_success"] = len(errors) == 0
    _persist_run_status(run_status)

    logger.info(
        f"[generate_episode_scripts] RESPONSE success=True status_code=200 project_id={project_id} "
        f"generation_success={response_payload.get('generation_success')} errors={len(errors)}"
    )
    return response_payload


@router.get("/projects/{project_id}/script_generator/episodes/scripts/status", response_model=Dict[str, Any])
def get_project_episode_scripts_generation_status(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _require_project_access(db, project_id, current_user)

    gi = dict(project.global_info or {})
    status_payload = gi.get("episode_script_generation_status") if isinstance(gi, dict) else None
    if not isinstance(status_payload, dict):
        return {
            "project_id": project_id,
            "running": False,
            "processed": 0,
            "generated": 0,
            "failed": 0,
            "skipped": 0,
            "stop_requested": False,
            "stopped_by_user": False,
            "episodes_in_run": 0,
            "results": [],
        }
    status_results = status_payload.get("results") if isinstance(status_payload, dict) else []
    status_latest = status_results[-1] if isinstance(status_results, list) and status_results else {}
    logger.info(
        "[generate_episode_scripts] STATUS_READ project_id=%s running=%s processed=%s generated=%s failed=%s skipped=%s results_count=%s latest_episode_id=%r latest_episode_number=%r latest_episode_title=%r latest_project_episode_title=%r latest_llm_episode_title=%r latest_status=%r",
        project_id,
        bool(status_payload.get("running")),
        int(status_payload.get("processed") or 0),
        int(status_payload.get("generated") or 0),
        int(status_payload.get("failed") or 0),
        int(status_payload.get("skipped") or 0),
        len(status_results) if isinstance(status_results, list) else 0,
        status_latest.get("episode_id") if isinstance(status_latest, dict) else None,
        status_latest.get("episode_number") if isinstance(status_latest, dict) else None,
        status_latest.get("episode_title") if isinstance(status_latest, dict) else None,
        status_latest.get("project_episode_title") if isinstance(status_latest, dict) else None,
        status_latest.get("llm_episode_title") if isinstance(status_latest, dict) else None,
        status_latest.get("status") if isinstance(status_latest, dict) else None,
    )
    return status_payload


@router.post("/projects/{project_id}/script_generator/episodes/scripts/stop", response_model=Dict[str, Any])
def stop_project_episode_scripts_generation(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = _require_project_access(db, project_id, current_user)

    gi = dict(project.global_info or {})
    status_key = "episode_script_generation_status"
    removed = status_key in gi
    gi.pop(status_key, None)
    project.global_info = gi
    db.add(project)
    db.commit()
    now_iso = now_bj_iso()

    try:
        log_action(
            db,
            user_id=current_user.id,
            user_name=current_user.username,
            action="GENERATE_EPISODE_SCRIPTS_STOP_REQUESTED",
            details=json.dumps({
                "project_id": project_id,
                "requested_at": now_iso,
            }, ensure_ascii=False),
        )
    except Exception as e:
        logger.warning(f"[generate_episode_scripts] failed to write STOP_REQUESTED system log: {e}")

    return {
        "success": True,
        "project_id": project_id,
        "running": False,
        "status": "canceled",
        "deleted": bool(removed),
        "message": "Force removed",
    }
