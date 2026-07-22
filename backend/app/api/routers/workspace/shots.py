# -*- coding: utf-8 -*-
"""Workspace section routes — symbols pulled from shared module."""
from __future__ import annotations

from app.api.routers.workspace import shared as _shared

# Attach routes onto the same APIRouter instance and reuse helpers.
router = _shared.router
globals().update({k: v for k, v in vars(_shared).items() if k not in {"__name__", "__file__", "__package__", "__loader__", "__spec__", "__doc__", "__builtins__"}})


# --- Shots ---

from app.schemas.shot import (  # noqa: E402,F401
    ShotBatchCreateItem,
    ShotBatchCreateRequest,
    ShotCreate,
    ShotOut,
    ShotUpdate,
)

_SHOT_LIST_COMPACT_TECH_KEYS = (
    "end_frame_url",
    "video_prompt_cn",
    "prompt_cn",
    "start_frame_cn",
    "end_frame_cn",
    "keyframes",
    "keyframes_cn",
    "keyframe_images",
    "voiceover_url",
    # Persist storyboard extract / preview media in compact list payloads so
    # reopening a shot can show previously captured frames without waiting on hydrate.
    "prev_shot_frames",
    "prev_shot_frame_images",
    "prev_shot_frame_meta",
    "multi_panel_image_url",
    "multi_panel_image_preset",
    "storyboard_url",
)
def _compact_shot_list_technical_notes(raw_notes: Any) -> Tuple[Optional[str], str, str]:
    notes = _asset_meta_to_dict(raw_notes)
    if not notes:
        return None, "", ""

    compact_notes: Dict[str, Any] = {}
    end_frame_url = str(notes.get("end_frame_url") or "").strip()
    prompt_preview_cn = ""

    for key in _SHOT_LIST_COMPACT_TECH_KEYS:
        if key not in notes:
            continue
        value = notes.get(key)
        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                continue
            if key in {"video_prompt_cn", "prompt_cn", "start_frame_cn", "end_frame_cn"} and not prompt_preview_cn:
                prompt_preview_cn = normalized
            compact_notes[key] = normalized
            continue
        if isinstance(value, list):
            normalized_list = [str(item or "").strip() for item in value if str(item or "").strip()]
            if normalized_list:
                compact_notes[key] = normalized_list
            continue
        if value is not None:
            compact_notes[key] = value

    if end_frame_url and "end_frame_url" not in compact_notes:
        compact_notes["end_frame_url"] = end_frame_url

    compact_payload = json.dumps(compact_notes, ensure_ascii=False) if compact_notes else None
    return compact_payload, end_frame_url, prompt_preview_cn


def _build_compact_shot_payload(row: Any, db: Session) -> Dict[str, Any]:
    compact_notes, end_frame_url, prompt_preview_cn = _compact_shot_list_technical_notes(getattr(row, "technical_notes", None))
    image_url = _refresh_managed_media_url(getattr(row, "image_url", None), db)
    video_url = _refresh_managed_media_url(getattr(row, "video_url", None), db)
    end_frame_url = _refresh_managed_media_url(end_frame_url, db)

    prompt_preview_en = ""
    for candidate in (
        getattr(row, "video_content", None),
        getattr(row, "prompt", None),
        getattr(row, "start_frame", None),
        getattr(row, "end_frame", None),
        prompt_preview_cn,
        getattr(row, "shot_logic_cn", None),
    ):
        normalized = str(candidate or "").strip()
        if normalized:
            prompt_preview_en = normalized
            break

    return {
        "id": getattr(row, "id", None),
        "scene_id": getattr(row, "scene_id", None),
        "project_id": getattr(row, "project_id", None),
        "episode_id": getattr(row, "episode_id", None),
        "shot_id": getattr(row, "shot_id", None),
        "shot_name": getattr(row, "shot_name", None),
        "start_frame": getattr(row, "start_frame", None),
        "end_frame": getattr(row, "end_frame", None),
        "video_content": getattr(row, "video_content", None),
        "duration": getattr(row, "duration", None),
        "associated_entities": getattr(row, "associated_entities", None),
        "shot_logic_cn": getattr(row, "shot_logic_cn", None),
        "keyframes": getattr(row, "keyframes", None),
        "scene_code": getattr(row, "scene_code", None),
        "image_url": image_url or None,
        "video_url": video_url or None,
        "prompt": getattr(row, "prompt", None),
        "technical_notes": compact_notes,
        "end_frame_url": end_frame_url or None,
        "prompt_preview_cn": prompt_preview_cn or None,
        "prompt_preview_en": prompt_preview_en or None,
        "is_compact": True,
    }

@router.get("/episodes/{episode_id}/shots", response_model=List[ShotOut])
def read_episode_shots(
    episode_id: int,
    scene_code: Optional[str] = None,
    shot_id: Optional[str] = None,
    keyword: Optional[str] = None,
    compact: bool = Query(False),
    skip: int = 0,
    limit: int = 300,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
        
    project = _require_project_access(db, episode.project_id, current_user)

    query = db.query(Shot).filter(
        Shot.project_id == project.id,
        Shot.episode_id == episode_id,
        _active_shot_clause(),
    )

    if scene_code:
        normalized = scene_code.strip()
        like_token = f"%{normalized}%"
        query = query.filter(
            or_(
                Shot.scene_code.ilike(like_token),
                Shot.shot_id.ilike(f"{normalized}%"),
            )
        )

    if shot_id:
        like_token = f"%{shot_id.strip()}%"
        query = query.filter(Shot.shot_id.ilike(like_token))

    if keyword:
        like_token = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                Shot.shot_name.ilike(like_token),
                Shot.shot_logic_cn.ilike(like_token),
                Shot.associated_entities.ilike(like_token),
                Shot.video_content.ilike(like_token),
            )
        )

    safe_skip = max(int(skip or 0), 0)
    safe_limit = max(1, min(int(limit or 300), 500))

    if compact:
        compact_query = query.with_entities(
            Shot.id.label("id"),
            Shot.scene_id.label("scene_id"),
            Shot.project_id.label("project_id"),
            Shot.episode_id.label("episode_id"),
            Shot.shot_id.label("shot_id"),
            Shot.shot_name.label("shot_name"),
            Shot.start_frame.label("start_frame"),
            Shot.end_frame.label("end_frame"),
            Shot.video_content.label("video_content"),
            Shot.duration.label("duration"),
            Shot.associated_entities.label("associated_entities"),
            Shot.shot_logic_cn.label("shot_logic_cn"),
            Shot.keyframes.label("keyframes"),
            Shot.scene_code.label("scene_code"),
            Shot.image_url.label("image_url"),
            Shot.video_url.label("video_url"),
            Shot.prompt.label("prompt"),
            Shot.technical_notes.label("technical_notes"),
        )
        rows = compact_query.order_by(Shot.id).offset(safe_skip).limit(safe_limit).all()
        deduped_rows = _dedupe_active_shot_records_for_display(rows)
        return [_build_compact_shot_payload(row, db) for row in deduped_rows]

    shots = query.order_by(Shot.id).offset(safe_skip).limit(safe_limit).all()
    shots = _dedupe_active_shot_records_for_display(shots)
    repaired = _repair_shots_media_urls_from_assets(db, current_user, project, shots)
    return [_refresh_shot_media_urls(shot, db) for shot in repaired]


@router.get("/episodes/{episode_id}/shots/download-zip")
def download_episode_shot_videos_zip(
    episode_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    project = _require_project_access(db, episode.project_id, current_user)
    shots = (
        db.query(Shot)
        .filter(
            Shot.project_id == project.id,
            Shot.episode_id == episode_id,
            Shot.video_url.isnot(None),
            Shot.video_url != "",
            _active_shot_clause(),
        )
        .order_by(Shot.id)
        .all()
    )
    shots = _repair_shots_media_urls_from_assets(db, current_user, project, shots)

    if not shots:
        raise HTTPException(status_code=404, detail="No shot videos available for download")

    archive_dir = os.path.join(settings.UPLOAD_DIR, "_downloads")
    os.makedirs(archive_dir, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    archive_name = f"episode_{episode_id}_shot_videos_{timestamp}.zip"
    archive_path = os.path.join(archive_dir, archive_name)

    success_count = 0
    failure_count = 0
    user_agent = {"User-Agent": "AIStoryShotZip/1.0"}

    try:
        with zipfile.ZipFile(archive_path, mode="w", compression=zipfile.ZIP_STORED) as archive:
            for index, shot in enumerate(shots, start=1):
                refreshed_shot = _refresh_shot_media_urls(shot, db)
                raw_url = str(getattr(refreshed_shot, "video_url", "") or "").strip()
                if not raw_url:
                    continue

                entry_name = _build_shot_video_zip_entry_name(refreshed_shot, index, raw_url)
                local_path = _resolve_local_upload_path_from_media_url(raw_url)

                try:
                    if local_path:
                        archive.write(local_path, arcname=entry_name)
                    else:
                        download_url = raw_url
                        if download_url.startswith("/"):
                            download_url = urllib.parse.urljoin(str(request.base_url), download_url.lstrip("/"))
                        with requests.get(download_url, stream=True, timeout=(15, 180), headers=user_agent) as response:
                            response.raise_for_status()
                            with archive.open(entry_name, mode="w") as zipped_file:
                                for chunk in response.iter_content(chunk_size=1024 * 1024):
                                    if chunk:
                                        zipped_file.write(chunk)
                    success_count += 1
                except Exception as exc:
                    failure_count += 1
                    logger.warning(
                        "Failed to package shot video episode_id=%s shot_id=%s url=%s error=%s",
                        episode_id,
                        getattr(refreshed_shot, "id", None),
                        raw_url,
                        exc,
                    )

        if success_count <= 0:
            _cleanup_temp_download_file(archive_path)
            raise HTTPException(status_code=502, detail="Failed to package shot videos")

        headers = {
            "X-AIStory-Download-Count": str(success_count),
            "X-AIStory-Download-Failures": str(failure_count),
        }
        return FileResponse(
            archive_path,
            media_type="application/zip",
            filename=archive_name,
            headers=headers,
            background=BackgroundTask(_cleanup_temp_download_file, archive_path),
        )
    except HTTPException:
        raise
    except Exception as exc:
        _cleanup_temp_download_file(archive_path)
        logger.error("Failed to build episode shot video zip episode_id=%s error=%s", episode_id, exc)
        raise HTTPException(status_code=500, detail="Failed to create shot video archive")


@router.get("/shots/{shot_id}", response_model=ShotOut)
def read_shot_detail(
    shot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    shot = db.query(Shot).filter(Shot.id == shot_id, _active_shot_clause()).first()
    if not shot:
        raise HTTPException(status_code=404, detail="Shot not found")

    project = _require_project_access(db, shot.project_id, current_user)
    _repair_shot_media_urls_from_assets(db, current_user, project, shot)
    _refresh_shot_media_urls(shot, db)
    return shot

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


SCENE_AI_SHOTS_BATCH_STATUS_KEY = "scene_ai_shots_batch_status"
SCENE_AI_SHOTS_BATCH_PER_SCENE_TIMEOUT_SEC = 600
SCENE_AI_SHOTS_BATCH_DEFAULT_CONCURRENCY = 3
SCENE_AI_SHOTS_BATCH_STATUS_ERROR_LIMIT = max(5, int(os.getenv("SCENE_AI_SHOTS_BATCH_STATUS_ERROR_LIMIT", "20") or 20))
SCENE_AI_SHOTS_BATCH_STATUS_ERROR_MAX_CHARS = max(80, int(os.getenv("SCENE_AI_SHOTS_BATCH_STATUS_ERROR_MAX_CHARS", "240") or 240))


def _read_scene_ai_shots_batch_status(episode: Episode) -> Dict[str, Any]:
    try:
        info = _episode_runtime_info_from_episode(episode)
        payload = info.get(SCENE_AI_SHOTS_BATCH_STATUS_KEY)
        if isinstance(payload, dict):
            return dict(payload)
    except Exception:
        pass
    return {
        "running": False,
        "total": 0,
        "completed": 0,
        "success": 0,
        "failed": 0,
        "current_scene_id": None,
        "current_scene_label": "",
        "message": "",
        "errors": [],
    }


def _persist_scene_ai_shots_batch_status(db: Session, episode: Episode, status_payload: Dict[str, Any]) -> None:
    latest_episode = (
        db.query(Episode)
        .execution_options(populate_existing=True)
        .filter(Episode.id == int(episode.id))
        .first()
    )
    target_episode = latest_episode or episode

    info = _episode_runtime_info_from_episode(target_episode)
    existing_status = info.get(SCENE_AI_SHOTS_BATCH_STATUS_KEY)
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

    info[SCENE_AI_SHOTS_BATCH_STATUS_KEY] = merged_status
    target_episode.episode_info = info
    db.add(target_episode)
    db.commit()


def _build_scene_ai_shots_batch_status_response(status_payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(status_payload or {})
    response_payload: Dict[str, Any] = {
        "running": bool(payload.get("running")),
        "status": str(payload.get("status") or ("running" if payload.get("running") else "idle")).strip().lower(),
        "project_id": payload.get("project_id"),
        "episode_id": payload.get("episode_id"),
        "started_by_user_id": payload.get("started_by_user_id"),
        "started_by_username": payload.get("started_by_username"),
        "max_concurrency": payload.get("max_concurrency"),
        "total": int(payload.get("total") or 0),
        "completed": int(payload.get("completed") or 0),
        "success": int(payload.get("success") or 0),
        "failed": int(payload.get("failed") or 0),
        "current_scene_id": payload.get("current_scene_id"),
        "current_scene_label": str(payload.get("current_scene_label") or "").strip(),
        "message": str(payload.get("message") or "").strip()[:512],
        "stop_requested": bool(payload.get("stop_requested")),
        "force_stopped": bool(payload.get("force_stopped")),
        "stopped_by_user": bool(payload.get("stopped_by_user")),
        "started_at": payload.get("started_at"),
        "updated_at": payload.get("updated_at"),
        "finished_at": payload.get("finished_at"),
    }

    raw_errors = payload.get("errors") or []
    safe_errors: List[str] = []
    for item in (raw_errors if isinstance(raw_errors, list) else []):
        txt = str(item or "").strip()
        if not txt:
            continue
        safe_errors.append(txt[:SCENE_AI_SHOTS_BATCH_STATUS_ERROR_MAX_CHARS])
        if len(safe_errors) >= SCENE_AI_SHOTS_BATCH_STATUS_ERROR_LIMIT:
            break
    response_payload["errors"] = safe_errors
    response_payload["errors_total"] = len(raw_errors) if isinstance(raw_errors, list) else len(safe_errors)
    response_payload["errors_truncated"] = bool(response_payload["errors_total"] > len(safe_errors))
    response_payload["poll_interval_ms"] = 2500
    return response_payload


def _run_scene_ai_shots_batch_item(scene_id: int, episode_id: int, user_id: int, function_name: Optional[str] = None, system_api_id: Optional[int] = None) -> Dict[str, Any]:
    item_db = SessionLocal()
    try:
        scene = item_db.query(Scene).filter(Scene.id == scene_id, Scene.episode_id == episode_id).first()
        user = item_db.query(User).filter(User.id == user_id).first()
        if not scene or not user:
            raise RuntimeError("Scene or user not found")
        user_principal = _snapshot_user_principal(user)

        scene_label = str(scene.scene_no or scene.scene_name or f"#{scene_id}")
        existing_shot_count = (
            item_db.query(Shot)
            .filter(Shot.scene_id == scene_id, _active_shot_clause())
            .count()
        )
        if existing_shot_count > 0:
            logger.info(
                "[scene_ai_shots_batch] abandon scene already has shots | scene_id=%s count=%s",
                scene_id,
                existing_shot_count,
            )
            return {
                "scene_id": int(scene_id),
                "scene_label": scene_label,
                "ok": True,
                "skipped": True,
                "reason": f"scene already has {existing_shot_count} shot(s); import abandoned",
            }
        _release_db_connection(item_db, "scene_ai_shots_batch_item")
        generated = asyncio.run(
            asyncio.wait_for(
                ai_generate_shots(scene_id=scene_id, req=AIShotGenRequest(function_name=function_name, system_api_id=system_api_id), db=item_db, current_user=user_principal),
                timeout=SCENE_AI_SHOTS_BATCH_PER_SCENE_TIMEOUT_SEC,
            )
        )
        generated_rows = generated.get("content") if isinstance(generated, dict) else []
        if not isinstance(generated_rows, list) or len(generated_rows) == 0:
            raise RuntimeError("No parsed rows returned")

        apply_scene_ai_result(
            scene_id=scene_id,
            data=AnalysisContent(content=generated_rows, replace_existing=False),
            db=item_db,
            current_user=user_principal,
        )
        return {
            "scene_id": int(scene_id),
            "scene_label": scene_label,
            "ok": True,
        }
    except asyncio.TimeoutError:
        scene_label = str((scene.scene_no if 'scene' in locals() and scene else None) or (scene.scene_name if 'scene' in locals() and scene else None) or f"#{scene_id}")
        return {
            "scene_id": int(scene_id),
            "scene_label": scene_label,
            "ok": False,
            "error": f"scene processing exceeded {SCENE_AI_SHOTS_BATCH_PER_SCENE_TIMEOUT_SEC}s timeout",
        }
    except Exception as e:
        scene_label = str((scene.scene_no if 'scene' in locals() and scene else None) or (scene.scene_name if 'scene' in locals() and scene else None) or f"#{scene_id}")
        return {
            "scene_id": int(scene_id),
            "scene_label": scene_label,
            "ok": False,
            "error": str(e),
        }
    finally:
        item_db.close()


def _run_scene_ai_shots_batch_job(episode_id: int, scene_ids: List[int], user_id: int, batch_max_concurrency: int, function_name: Optional[str] = None, system_api_id: Optional[int] = None) -> None:
    try:
        with SessionLocal() as init_db:
            episode = init_db.query(Episode).filter(Episode.id == episode_id).first()
            user = init_db.query(User).filter(User.id == user_id).first()
            if not episode or not user:
                return

            user_name = str(user.username or f"user_{user_id}")
            project_id = int(episode.project_id)
            scene_label_map: Dict[int, str] = {}
            for sid in scene_ids:
                sc = init_db.query(Scene).filter(Scene.id == sid, Scene.episode_id == episode_id).first()
                if sc:
                    scene_label_map[sid] = str(sc.scene_no or sc.scene_name or f"#{sid}")

        job_id = f"scene-ai-shots-batch:{int(episode_id)}"

        total = len(scene_ids)
        completed = 0
        success = 0
        failed = 0
        errors: List[str] = []

        def _read_latest_episode(session: Session) -> Optional[Episode]:
            return (
                session.query(Episode)
                .execution_options(populate_existing=True)
                .filter(Episode.id == episode_id)
                .first()
            )

        def _stop_requested() -> bool:
            with SessionLocal() as status_db:
                latest_episode = _read_latest_episode(status_db)
                if not latest_episode:
                    return True
                latest_status = _read_scene_ai_shots_batch_status(latest_episode)
                return bool(latest_status.get("stop_requested") or latest_status.get("force_stopped"))

        effective_batch_max_concurrency = _resolve_user_batch_parallel_limit(
            batch_max_concurrency,
            default=SCENE_AI_SHOTS_BATCH_DEFAULT_CONCURRENCY,
        )
        next_scene_index = 0
        active_future_map: Dict[Any, int] = {}

        def _active_scene_ids() -> List[int]:
            return list(active_future_map.values())

        def _persist_active_scene_status(latest_message: Optional[str] = None) -> None:
            with SessionLocal() as status_db:
                latest_episode = _read_latest_episode(status_db)
                if not latest_episode:
                    return
                latest_status = _read_scene_ai_shots_batch_status(latest_episode)
                active_scene_ids = _active_scene_ids()
                active_scene_labels = [scene_label_map.get(sid) or f"#{sid}" for sid in active_scene_ids]
                latest_status["current_scene_id"] = active_scene_ids[0] if len(active_scene_ids) == 1 else None
                latest_status["current_scene_label"] = " / ".join(active_scene_labels)
                latest_status["current_scene_started_at"] = now_bj_iso() if active_scene_ids else latest_status.get("current_scene_started_at")
                latest_status["updated_at"] = now_bj_iso()
                if latest_message is not None:
                    latest_status["message"] = latest_message
                elif active_scene_labels:
                    latest_status["message"] = (
                        f"Processing scenes {', '.join(active_scene_labels)}..."
                        if len(active_scene_labels) > 1
                        else f"Processing scene {active_scene_labels[0]}..."
                    )
                _persist_scene_ai_shots_batch_status(status_db, latest_episode, latest_status)

        def _submit_next_scene(executor: ThreadPoolExecutor) -> bool:
            nonlocal next_scene_index
            if next_scene_index >= len(scene_ids):
                return False
            sid = scene_ids[next_scene_index]
            next_scene_index += 1
            active_future_map[executor.submit(_run_scene_ai_shots_batch_item, sid, episode_id, user_id, function_name, system_api_id)] = sid
            return True

        max_workers = max(1, min(effective_batch_max_concurrency, total or 1))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            while len(active_future_map) < max_workers and _submit_next_scene(executor):
                pass

            if _stop_requested():
                with SessionLocal() as status_db:
                    episode = _read_latest_episode(status_db)
                    if episode:
                        latest = _read_scene_ai_shots_batch_status(episode)
                        latest["running"] = False
                        latest["completed"] = completed
                        latest["success"] = success
                        latest["failed"] = failed
                        latest["errors"] = errors
                        latest["finished_at"] = now_bj_iso()
                        latest["stopped_by_user"] = True
                        latest["message"] = "Stopped by user request"
                        _persist_scene_ai_shots_batch_status(status_db, episode, latest)
                        _log_batch_sys_event(
                            kind="scene-ai-shots-batch",
                            phase="end",
                            user_id=user_id,
                            user_name=user_name,
                            project_id=project_id,
                            episode_id=episode_id,
                            job_id=job_id,
                            result="canceled",
                            message="Stopped by user request",
                            extra={"completed": completed, "success": success, "failed": failed},
                        )
                return
            _persist_active_scene_status()

            while active_future_map:
                completed_future = next(as_completed(list(active_future_map.keys())))
                sid = active_future_map.pop(completed_future)
                scene_label = scene_label_map.get(sid) or f"#{sid}"
                try:
                    result = completed_future.result()
                except Exception as e:
                    result = {
                        "scene_id": sid,
                        "scene_label": scene_label,
                        "ok": False,
                        "error": str(e),
                    }

                if bool(result.get("ok")):
                    success += 1
                    _log_batch_sys_event(
                        kind="scene-ai-shots-batch",
                        phase="item",
                        user_id=user_id,
                        user_name=user_name,
                        project_id=project_id,
                        episode_id=episode_id,
                        job_id=job_id,
                        item_id=sid,
                        item_label=result.get("scene_label") or scene_label,
                        result="success",
                        message="Scene AI shots generated",
                    )
                else:
                    failed += 1
                    error_message = str(result.get("error") or "Unknown error")
                    errors.append(f"{result.get('scene_label') or scene_label}: {error_message}")
                    _log_batch_sys_event(
                        kind="scene-ai-shots-batch",
                        phase="item",
                        user_id=user_id,
                        user_name=user_name,
                        project_id=project_id,
                        episode_id=episode_id,
                        job_id=job_id,
                        item_id=sid,
                        item_label=result.get("scene_label") or scene_label,
                        result="failed",
                        message=error_message,
                    )

                completed += 1
                with SessionLocal() as progress_db:
                    episode = _read_latest_episode(progress_db)
                    if not episode:
                        break

                    latest = _read_scene_ai_shots_batch_status(episode)
                    latest["completed"] = completed
                    latest["success"] = success
                    latest["failed"] = failed
                    latest["errors"] = errors
                    latest["current_scene_id"] = sid
                    latest["current_scene_label"] = result.get("scene_label") or scene_label
                    latest["updated_at"] = now_bj_iso()
                    latest["message"] = f"Progress {completed}/{total}"
                    _persist_scene_ai_shots_batch_status(progress_db, episode, latest)

                if not _stop_requested():
                    while len(active_future_map) < max_workers and _submit_next_scene(executor):
                        pass

                _persist_active_scene_status()

        if _stop_requested() and next_scene_index < len(scene_ids):
            with SessionLocal() as status_db:
                episode = _read_latest_episode(status_db)
                if episode:
                    latest_after_batch = _read_scene_ai_shots_batch_status(episode)
                    latest_after_batch["running"] = False
                    latest_after_batch["completed"] = completed
                    latest_after_batch["success"] = success
                    latest_after_batch["failed"] = failed
                    latest_after_batch["errors"] = errors
                    latest_after_batch["finished_at"] = now_bj_iso()
                    latest_after_batch["stopped_by_user"] = True
                    latest_after_batch["message"] = "Stopped by user request"
                    _persist_scene_ai_shots_batch_status(status_db, episode, latest_after_batch)
                    _log_batch_sys_event(
                        kind="scene-ai-shots-batch",
                        phase="end",
                        user_id=user_id,
                        user_name=user_name,
                        project_id=project_id,
                        episode_id=episode_id,
                        job_id=job_id,
                        result="canceled",
                        message="Stopped by user request",
                        extra={"completed": completed, "success": success, "failed": failed},
                    )
            return

        with SessionLocal() as final_db:
            episode = final_db.query(Episode).filter(Episode.id == episode_id).first()
            if episode:
                final_status = _read_scene_ai_shots_batch_status(episode)
                final_status["running"] = False
                final_status["completed"] = completed
                final_status["success"] = success
                final_status["failed"] = failed
                final_status["errors"] = errors
                final_status["finished_at"] = now_bj_iso()
                final_status["updated_at"] = final_status["finished_at"]
                final_status["stopped_by_user"] = bool(final_status.get("stop_requested"))
                final_status["message"] = f"Batch done: success {success}, failed {failed}"
                _persist_scene_ai_shots_batch_status(final_db, episode, final_status)
                _log_batch_sys_event(
                    kind="scene-ai-shots-batch",
                    phase="end",
                    user_id=user_id,
                    user_name=user_name,
                    project_id=project_id,
                    episode_id=episode_id,
                    job_id=job_id,
                    result="completed",
                    message=final_status.get("message"),
                    extra={"completed": completed, "success": success, "failed": failed},
                )
    except Exception as e:
        try:
            with SessionLocal() as error_db:
                episode = error_db.query(Episode).filter(Episode.id == episode_id).first()
                if episode:
                    failed_status = _read_scene_ai_shots_batch_status(episode)
                    failed_status["running"] = False
                    failed_status["finished_at"] = now_bj_iso()
                    failed_status["updated_at"] = failed_status["finished_at"]
                    failed_status["message"] = f"Batch failed: {str(e)}"
                    failed_status["errors"] = list(failed_status.get("errors") or []) + [str(e)]
                    _persist_scene_ai_shots_batch_status(error_db, episode, failed_status)
                    _log_batch_sys_event(
                        kind="scene-ai-shots-batch",
                        phase="end",
                        user_id=user_id,
                        user_name=str((user.username if 'user' in locals() and user else "") or f"user_{user_id}"),
                        project_id=int(episode.project_id),
                        episode_id=episode_id,
                        job_id=f"scene-ai-shots-batch:{int(episode_id)}",
                        result="failed",
                        message=str(e),
                    )
        except Exception:
            pass
    finally:
        _clear_episode_worker(SCENE_AI_SHOTS_BATCH_THREADS, SCENE_AI_SHOTS_BATCH_THREADS_LOCK, int(episode_id))


def _start_scene_ai_shots_batch_for_episode(
    db: Session,
    episode: Episode,
    current_user: User,
    scene_ids: Optional[List[int]] = None,
    function_name: Optional[str] = None,
    system_api_id: Optional[int] = None,
) -> Dict[str, Any]:
    episode_id = int(episode.id)
    latest_status = _read_scene_ai_shots_batch_status(episode)
    if bool(latest_status.get("running")):
        raise HTTPException(status_code=409, detail="Scene AI shots batch is already running")

    requested_scene_ids = [int(x) for x in (scene_ids or []) if x]
    scenes_query = db.query(Scene).filter(Scene.episode_id == episode_id, _active_scene_clause())
    if requested_scene_ids:
        scenes_query = scenes_query.filter(Scene.id.in_(requested_scene_ids))
    target_scenes = _sort_scenes_by_scene_no(scenes_query.all())
    scene_ids = [int(s.id) for s in target_scenes]
    if not scene_ids:
        raise HTTPException(status_code=400, detail="No saved scenes found for batch")

    batch_max_concurrency = _resolve_user_batch_parallel_limit(
        getattr(current_user, "is_active", USER_ACTIVE_LEVEL_DEFAULT),
        default=SCENE_AI_SHOTS_BATCH_DEFAULT_CONCURRENCY,
    )

    now_iso = now_bj_iso()
    status_payload = {
        "running": True,
        "project_id": episode.project_id,
        "episode_id": episode_id,
        "started_by_user_id": int(current_user.id),
        "started_by_username": str(current_user.username or ""),
        "scene_ids": scene_ids,
        "max_concurrency": batch_max_concurrency,
        "total": len(scene_ids),
        "completed": 0,
        "success": 0,
        "failed": 0,
        "current_scene_id": None,
        "current_scene_label": "",
        "message": "Batch task started",
        "errors": [],
        "stop_requested": False,
        "stop_requested_at": None,
        "force_stopped": False,
        "stopped_by_user": False,
        "started_at": now_iso,
        "updated_at": now_iso,
        "finished_at": None,
    }
    _persist_scene_ai_shots_batch_status(db, episode, status_payload)
    _log_batch_sys_event(
        kind="scene-ai-shots-batch",
        phase="start",
        user_id=current_user.id,
        user_name=current_user.username,
        project_id=episode.project_id,
        episode_id=episode_id,
        job_id=f"scene-ai-shots-batch:{int(episode_id)}",
        result="running",
        message="Batch task started",
        extra={"scene_ids": scene_ids, "total": len(scene_ids), "max_concurrency": batch_max_concurrency},
    )

    worker = threading.Thread(
        target=_run_scene_ai_shots_batch_job,
        args=(episode_id, scene_ids, current_user.id, batch_max_concurrency, function_name, system_api_id),
        daemon=True,
    )
    worker.start()
    _register_episode_worker(SCENE_AI_SHOTS_BATCH_THREADS, SCENE_AI_SHOTS_BATCH_THREADS_LOCK, int(episode_id), worker)

    return status_payload


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


def _import_scene_shot_rows_to_db(
    *,
    scene_id: int,
    db: Session,
    scene: Scene,
    episode: Episode,
    project: Project,
    shots_data: List[Dict[str, Any]],
    skipped_row_errors: Optional[List[str]] = None,
    replace_existing: bool = False,
) -> List[Shot]:
    """
    Import validated shot rows into Shot table.
    This method is DB-import only and does NOT call LLM or write staged LLM markdown.

    Default policy: if the scene already has active shots, abandon the import
    (unless replace_existing=True for intentional UI replace).
    """
    skipped_row_errors = list(skipped_row_errors or [])

    locked_scene = db.query(Scene).filter(Scene.id == scene_id).with_for_update().first()
    if not locked_scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    existing_shots = db.query(Shot).filter(Shot.scene_id == scene_id, _active_shot_clause()).all()
    existing_count = len(existing_shots or [])
    if existing_count > 0 and not replace_existing:
        logger.info(
            "[apply_scene_ai_result] abandon_import scene already has shots | scene_id=%s count=%s",
            scene_id,
            existing_count,
        )
        raise HTTPException(
            status_code=409,
            detail=(
                f"Scene already has {existing_count} shot(s); import abandoned. "
                "Delete existing shots first, or pass replace_existing=true to overwrite."
            ),
        )

    deduped_shots_data, dedupe_warnings = _dedupe_shot_rows_for_import(
        list(shots_data or []),
        scene_id=scene_id,
    )
    for warning in dedupe_warnings:
        skipped_row_errors.append(f"dedupe: {warning}")
    shots_data = deduped_shots_data

    # Episode-scoped uniqueness: project + episode + Shot ID (active rows only).
    # Blocks duplicate-scene imports from writing the same EP##_SC##_SH## twice.
    conflicting: List[str] = []
    for idx, row in enumerate(shots_data or [], start=1):
        raw_shot_id = _pick_shot_cell(row, ["Shot ID", "shot_id", "镜头ID"], "")
        business_id = _normalize_shot_business_id(raw_shot_id)
        if not business_id:
            continue
        if isinstance(row, dict):
            # Persist normalized business id so unique index compares consistently.
            for key in ("Shot ID", "shot_id", "镜头ID"):
                if key in row:
                    row[key] = business_id
                    break
            else:
                row["Shot ID"] = business_id
        # When replacing, this scene's actives will be soft-deleted first — only other scenes conflict.
        dup = _find_active_shot_by_business_id(
            db,
            project_id=int(project.id),
            episode_id=int(episode.id),
            shot_id=business_id,
            exclude_scene_id=int(scene_id) if replace_existing else None,
        )
        if dup is not None:
            conflicting.append(
                f"{business_id} (existing scene_id={getattr(dup, 'scene_id', None)} db_id={getattr(dup, 'id', None)})"
            )
    if conflicting:
        sample = "; ".join(conflicting[:5])
        more = f"; and {len(conflicting) - 5} more" if len(conflicting) > 5 else ""
        logger.info(
            "[apply_scene_ai_result] abandon_import episode-unique Shot ID conflict | scene_id=%s episode_id=%s conflicts=%s",
            scene_id,
            getattr(episode, "id", None),
            len(conflicting),
        )
        raise HTTPException(
            status_code=409,
            detail=(
                f"Shot ID already exists in this project/episode; import abandoned. "
                f"Conflicts: {sample}{more}"
            ),
        )

    # 1) Extract and normalize associated entities text only (no auto-create).
    try:
        if shots_data:
            existing_entities = db.query(Entity).filter(Entity.project_id == project.id).all()
            entity_map = {e.name: e for e in existing_entities}
            new_entities_buffer = set()

            for s_data in shots_data:
                assoc_str = s_data.get("Associated Entities", "")
                if assoc_str and assoc_str.lower() != "none" and assoc_str.strip():
                    potential_names = [n.strip() for n in re.split(r'[,\uff0c]', assoc_str) if n.strip()]
                    cleaned_names = []
                    for name in potential_names:
                        if name in entity_map:
                            cleaned_names.append(name)
                        elif name in new_entities_buffer:
                            cleaned_names.append(name)
                        else:
                            cleaned_names.append(name)
                    s_data["Associated Entities"] = ", ".join(cleaned_names)
    except Exception as e:
        logger.error(f"[Import] Entity auto-linking failed: {e}")

    # 2) Replace scene shots with imported rows (only when empty or replace_existing).
    old_shot_map = {(str(s.shot_id or "").strip()): s for s in existing_shots if str(s.shot_id or "").strip()}
    _soft_delete_shots(db, scene_id=scene_id)

    def _split_combined_cn_prompt(raw_text: str) -> Tuple[str, str, str, str]:
        text = str(raw_text or "").strip()
        if not text:
            return "", "", "", ""
        lines = [ln.strip() for ln in re.split(r"\n|<br\\s*/?>", text) if ln and ln.strip()]
        start_cn = ""
        video_cn = ""
        keyframes_cn = ""
        end_cn = ""
        for ln in lines:
            lower_ln = ln.lower()
            if (
                lower_ln.startswith("start frame:")
                or lower_ln.startswith("start frame cn:")
                or lower_ln.startswith("start:")
                or ln.startswith("起始帧:")
                or ln.startswith("起始帧：")
            ):
                start_cn = re.sub(r"^(start\s*frame\s*(cn)?\s*:|start\s*:|起始帧\s*[:：])", "", ln, flags=re.IGNORECASE).strip()
                continue
            if lower_ln.startswith("video:") or lower_ln.startswith("video cn:") or ln.startswith("视频:") or ln.startswith("视频提示词:"):
                video_cn = re.sub(r"^(video\s*(cn)?\s*:|视频提示词\s*[:：]|视频\s*[:：])", "", ln, flags=re.IGNORECASE).strip()
                continue
            if (
                lower_ln.startswith("keyframes:")
                or lower_ln.startswith("keyframes cn:")
                or lower_ln.startswith("keyframe:")
                or ln.startswith("关键帧:")
                or ln.startswith("关键帧：")
            ):
                keyframes_cn = re.sub(r"^(key\s*frames?\s*(cn)?\s*:|关键帧\s*[:：])", "", ln, flags=re.IGNORECASE).strip()
                continue
            if (
                lower_ln.startswith("end frame:")
                or lower_ln.startswith("end frame cn:")
                or lower_ln.startswith("end:")
                or ln.startswith("收尾帧:")
                or ln.startswith("收尾帧：")
                or ln.startswith("结束帧:")
                or ln.startswith("结束帧：")
            ):
                end_cn = re.sub(r"^(end\s*frame\s*(cn)?\s*:|end\s*:|收尾帧\s*[:：]|结束帧\s*[:：])", "", ln, flags=re.IGNORECASE).strip()
                continue

        if not start_cn and not video_cn and not keyframes_cn and not end_cn:
            return text, text, text, text
        if not end_cn and start_cn:
            end_cn = start_cn
        return start_cn, video_cn, keyframes_cn, end_cn

    known_col_aliases = [
        "Shot ID", "shot_id", "镜头ID",
        "Shot Name", "shot_name", "镜头名称",
        "Scene ID", "scene_id", "Scene Code", "scene_code", "场景ID", "场次号",
        "Start Frame", "start_frame", "起始帧",
        "End Frame", "end_frame", "结束帧",
        "Video Content", "video_content", "视频内容",
        "Duration (s)", "Duration", "duration", "时长", "时长(s)",
        "Associated Entities", "associated_entities", "关联实体",
        "Shot Logic (CN)", "shot_logic_cn", "镜头逻辑", "镜头逻辑（中文）",
        "Keyframes", "keyframes", "关键帧",
        "Prompt (CN)", "Prompts (CN)", "Prompt CN", "prompt_cn", "提示词（中文）", "中文提示词",
        "Start Frame (CN)", "start_frame_cn", "起始帧（中文）",
        "Video Content (CN)", "video_prompt_cn", "视频内容（中文）",
        "Keyframes (CN)", "keyframes_cn", "关键帧（中文）", "关键帧中文",
        "End Frame (CN)", "end_frame_cn", "结束帧（中文）",
    ]
    known_col_norm_set = {_normalize_shot_markdown_col_key(k) for k in known_col_aliases}

    for idx, s_data in enumerate(shots_data):
        try:
            dur_val = 2.0
            raw_duration = _pick_shot_cell(s_data, ["Duration (s)", "Duration", "duration", "时长", "时长(s)"], "")
            if raw_duration:
                match = re.search(r"[\d\.]+", str(raw_duration))
                dur_val = float(match.group()) if match else 2.0
        except Exception:
            dur_val = 2.0

        start_frame_text = _pick_shot_cell(s_data, ["Start Frame", "start_frame", "起始帧"], "")
        end_frame_text = _pick_shot_cell(s_data, ["End Frame", "end_frame", "结束帧"], "")
        video_content_text = _pick_shot_cell(s_data, ["Video Content", "video_content", "视频内容"], "")
        associated_entities_text = _pick_shot_cell(s_data, ["Associated Entities", "associated_entities", "关联实体"], "")
        shot_logic_cn_text = _pick_shot_cell(s_data, ["Shot Logic (CN)", "shot_logic_cn", "镜头逻辑", "镜头逻辑（中文）"], "")
        keyframes_text = _pick_shot_cell(s_data, ["Keyframes", "keyframes", "关键帧"], "NO")
        scene_code_text = _pick_shot_cell(s_data, ["Scene ID", "scene_id", "Scene Code", "scene_code", "场景ID", "场次号"], scene.scene_no or "")
        shot_id_text = _pick_shot_cell(s_data, ["Shot ID", "shot_id", "镜头ID"], str(idx + 1))
        shot_name_text = _pick_shot_cell(s_data, ["Shot Name", "shot_name", "镜头名称"], "Shot")

        prompt_cn_combined = _pick_shot_cell(
            s_data,
            ["Prompt (CN)", "Prompts (CN)", "Prompt CN", "prompt_cn", "提示词（中文）", "中文提示词"],
            "",
        )
        start_frame_cn_text = _pick_shot_cell(s_data, ["Start Frame (CN)", "start_frame_cn", "起始帧（中文）"], "")
        video_prompt_cn_text = _pick_shot_cell(s_data, ["Video Content (CN)", "video_prompt_cn", "视频内容（中文）"], "")
        keyframes_cn_text = _pick_shot_cell(s_data, ["Keyframes (CN)", "keyframes_cn", "关键帧（中文）", "关键帧中文"], "")
        end_frame_cn_text = _pick_shot_cell(s_data, ["End Frame (CN)", "end_frame_cn", "结束帧（中文）"], "")

        if prompt_cn_combined:
            start_cn_fallback, video_cn_fallback, keyframes_cn_fallback, end_cn_fallback = _split_combined_cn_prompt(prompt_cn_combined)
            if not start_frame_cn_text:
                start_frame_cn_text = start_cn_fallback
            if not end_frame_cn_text:
                end_frame_cn_text = end_cn_fallback
            if not video_prompt_cn_text:
                video_prompt_cn_text = video_cn_fallback
            if not keyframes_cn_text:
                keyframes_cn_text = keyframes_cn_fallback

        technical_notes_payload: Dict[str, Any] = {}
        if start_frame_cn_text:
            technical_notes_payload["start_frame_cn"] = start_frame_cn_text
        if video_prompt_cn_text:
            technical_notes_payload["video_prompt_cn"] = video_prompt_cn_text
        if keyframes_cn_text:
            technical_notes_payload["keyframes_cn"] = keyframes_cn_text
        if end_frame_cn_text:
            technical_notes_payload["end_frame_cn"] = end_frame_cn_text
        if start_frame_cn_text or video_prompt_cn_text or keyframes_cn_text or end_frame_cn_text:
            technical_notes_payload["shot_prompt_cn"] = "<br>".join([
                f"起始帧：{start_frame_cn_text or ''}",
                f"视频：{video_prompt_cn_text or ''}",
                f"关键帧：{keyframes_cn_text or ''}",
                f"收尾帧：{end_frame_cn_text or ''}",
            ])

        extra_columns: Dict[str, str] = {}
        if isinstance(s_data, dict):
            for raw_key, raw_val in s_data.items():
                nk = _normalize_shot_markdown_col_key(raw_key)
                if nk in known_col_norm_set:
                    continue
                val = str(raw_val or "").strip()
                if not val:
                    continue
                rule = SHOT_MARKDOWN_COLUMN_WHITELIST.get(nk)
                if rule and rule.get("target") == "tech_field":
                    tech_key = str(rule.get("field") or "").strip()
                    if tech_key:
                        technical_notes_payload[tech_key] = val
                        continue
                extra_columns[str(raw_key)] = val
        if extra_columns:
            technical_notes_payload["shot_extra_columns"] = extra_columns

        normalized_shot_id = _normalize_shot_business_id(shot_id_text) or str(shot_id_text or "").strip()
        old_shot = old_shot_map.get(normalized_shot_id) or old_shot_map.get(str(shot_id_text).strip())
        preserved_image_url = None
        preserved_video_url = None
        if old_shot:
            preserved_image_url = old_shot.image_url
            preserved_video_url = old_shot.video_url
            try:
                old_tech = json.loads(old_shot.technical_notes) if old_shot.technical_notes else {}
                for k, v in old_tech.items():
                    if k.endswith("_url") or k.endswith("_urls") or k in {"start_frame_supported", "supports_start_frame"}:
                        if k not in technical_notes_payload:
                            technical_notes_payload[k] = v
            except Exception:
                pass

        shot = Shot(
            scene_id=scene_id,
            project_id=project.id,
            episode_id=episode.id,
            shot_id=normalized_shot_id,
            shot_name=shot_name_text,
            scene_code=scene_code_text,
            start_frame=start_frame_text,
            end_frame=end_frame_text,
            video_content=video_content_text,
            duration=str(dur_val),
            associated_entities=associated_entities_text,
            shot_logic_cn=shot_logic_cn_text,
            keyframes=keyframes_text,
            prompt=video_content_text,
            image_url=preserved_image_url,
            video_url=preserved_video_url,
            technical_notes=(json.dumps(technical_notes_payload, ensure_ascii=False) if technical_notes_payload else None),
        )
        db.add(shot)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        logger.warning(
            "[shot_import.apply] unique constraint conflict scene_id=%s episode_id=%s err=%s",
            scene_id,
            getattr(episode, "id", None),
            exc,
        )
        raise HTTPException(
            status_code=409,
            detail=(
                "Shot ID already exists for this project/episode (unique index); import abandoned."
            ),
        ) from exc
    _soft_delete_duplicate_active_shots_in_db(
        db,
        episode_id=int(episode.id),
        project_id=int(project.id),
        scope="episode",
    )
    db.commit()

    applied_shots = db.query(Shot).filter(Shot.scene_id == scene_id, _active_shot_clause()).all()
    applied_shots = _dedupe_active_shot_records_for_display(applied_shots)
    if skipped_row_errors:
        try:
            for shot in applied_shots:
                notes_obj = {}
                if getattr(shot, "technical_notes", None):
                    try:
                        notes_obj = json.loads(shot.technical_notes) if isinstance(shot.technical_notes, str) else {}
                    except Exception:
                        notes_obj = {}
                notes_obj["import_warnings"] = list(
                    dict.fromkeys([str(x or "").strip() for x in skipped_row_errors if str(x or "").strip()])
                )
                shot.technical_notes = json.dumps(notes_obj, ensure_ascii=False)
            db.commit()
            applied_shots = db.query(Shot).filter(Shot.scene_id == scene_id, _active_shot_clause()).all()
        except Exception:
            db.rollback()
            applied_shots = db.query(Shot).filter(Shot.scene_id == scene_id, _active_shot_clause()).all()

    logger.info(
        "[shot_import.apply] applied scene_id=%s episode_id=%s project_id=%s rows=%s skipped=%s",
        scene_id,
        getattr(episode, "id", None),
        getattr(project, "id", None),
        len(applied_shots),
        len(skipped_row_errors),
    )
    return applied_shots

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

@router.get("/scenes/{scene_id}/shots", response_model=List[ShotOut])
def read_shots(
    scene_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    scene = db.query(Scene).filter(Scene.id == scene_id, _active_scene_clause()).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
        
    # Check Project ownership via Episode
    episode = db.query(Episode).filter(Episode.id == scene.episode_id, _active_episode_clause()).first()
    project = _require_project_access(db, episode.project_id, current_user)
        
    # Optimized: Return shots strictly by Scene ID (Physical Association)
    # Removing logical 'scene_code' sync as requested.
    shots = db.query(Shot).filter(
        Shot.project_id == project.id,
        Shot.episode_id == episode.id,
        Shot.scene_id == scene_id,
        _active_shot_clause(),
    ).all()
    shots = _dedupe_active_shot_records_for_display(shots)
    repaired = _repair_shots_media_urls_from_assets(db, current_user, project, shots)
    return [_refresh_shot_media_urls(shot, db) for shot in repaired]

@router.post("/scenes/{scene_id}/shots", response_model=ShotOut)
def create_shot(
    scene_id: int,
    shot: ShotCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    import os
    logger.info(f"[create_shot] START. scene_id={scene_id}")
    logger.info(f"[create_shot] DB URL: {settings.DATABASE_URL}")
    logger.info(f"[create_shot] Payload: shot_id={shot.shot_id}, logic_cn={'YES' if shot.shot_logic_cn else 'NO'}")

    scene = db.query(Scene).filter(Scene.id == scene_id, _active_scene_clause()).first()
    if not scene:
        logger.error(f"[create_shot] Scene {scene_id} not found")
        raise HTTPException(status_code=404, detail="Scene not found")
    
    # Ownership
    episode = db.query(Episode).filter(Episode.id == scene.episode_id, _active_episode_clause()).first()
    if not episode:
        logger.error(f"[create_shot] Scene {scene_id} refers to non-existent episode {scene.episode_id}")
        raise HTTPException(status_code=404, detail="Parent Episode not found")

    try:
        project = _require_project_access(db, episode.project_id, current_user)
    except HTTPException:
         logger.error(f"[create_shot] User {current_user.id} not authorized for Project {episode.project_id}")
         raise
         
    try:
        _assert_allowed_shot_media_payload(shot.dict(exclude_unset=True), db=db)

        business_id = _normalize_shot_business_id(getattr(shot, "shot_id", ""))
        if business_id:
            existing = _find_active_shot_by_business_id(
                db,
                project_id=int(project.id),
                episode_id=int(episode.id),
                shot_id=business_id,
            )
            if existing is not None:
                logger.warning(
                    "[create_shot] abandon duplicate Shot ID | scene_id=%s episode_id=%s shot_id=%s existing_db_id=%s existing_scene_id=%s",
                    scene_id,
                    episode.id,
                    business_id,
                    existing.id,
                    getattr(existing, "scene_id", None),
                )
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Shot ID '{shot.shot_id}' already exists in this project/episode; import abandoned."
                    ),
                )

        db_shot = Shot(
            scene_id=scene_id,
            project_id=project.id,
            episode_id=episode.id,
            shot_id=business_id or shot.shot_id,
            shot_name=shot.shot_name,
            start_frame=shot.start_frame,
            end_frame=shot.end_frame,
            video_content=shot.video_content,
            duration=shot.duration,
            associated_entities=shot.associated_entities,
            shot_logic_cn=shot.shot_logic_cn,
            keyframes=shot.keyframes,
            scene_code=shot.scene_code,
            image_url=shot.image_url,
            video_url=shot.video_url,
            prompt=shot.prompt,
            technical_notes=shot.technical_notes
        )
        db.add(db_shot)
        try:
            _recompute_and_persist_project_cost_estimation(db, int(project.id))
        except Exception as cost_exc:
            logger.warning("create_shot cost recompute skipped | project_id=%s err=%s", project.id, cost_exc)
        db.commit()
        db.refresh(db_shot)
        
        # Verify Write
        logger.info(f"[create_shot] Committed Shot ID: {db_shot.id}. Verifying...")
        verify = db.query(Shot).filter(Shot.id == db_shot.id).first()
        if verify:
             logger.info(f"[create_shot] SUCCESS. Shot {db_shot.id} (Display ID: {db_shot.shot_id}) exists in DB.")
        else:
             logger.error(f"[create_shot] CRITICAL FAILURE. Shot {db_shot.id} not found immediately after commit!")

        return _refresh_shot_media_urls(db_shot, db)
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        logger.error(f"[create_shot] EXCEPTION: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create shot: {str(e)}")

@router.post("/episodes/{episode_id}/shots/batch_create", response_model=Dict[str, Any])
def batch_create_shots(
    episode_id: int,
    request: ShotBatchCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    started_perf = time.perf_counter()
    episode = db.query(Episode).filter(Episode.id == int(episode_id), _active_episode_clause()).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    project = _require_project_access(db, episode.project_id, current_user)

    items = list(request.items or [])
    if not items:
        return {
            "status": "ok",
            "episode_id": int(episode_id),
            "project_id": int(project.id),
            "processed": 0,
            "created": 0,
            "skipped": 0,
            "elapsed_ms": int((time.perf_counter() - started_perf) * 1000),
        }

    scene_ids = sorted({int(item.scene_id) for item in items if int(getattr(item, "scene_id", 0) or 0) > 0})
    scenes = (
        db.query(Scene)
        .filter(
            Scene.id.in_(scene_ids),
            Scene.episode_id == int(episode_id),
            _active_scene_clause(),
        )
        .all()
    ) if scene_ids else []
    scene_by_id = {int(scene.id): scene for scene in scenes}

    skip_existing_scene_shots = bool(getattr(request, "skip_existing_scene_shots", True))
    scenes_with_existing_shots: set = set()
    if skip_existing_scene_shots and scene_ids:
        existing_rows = (
            db.query(Shot.scene_id)
            .filter(
                Shot.scene_id.in_(scene_ids),
                _active_shot_clause(),
            )
            .distinct()
            .all()
        )
        scenes_with_existing_shots = {
            int(row[0]) for row in existing_rows if row and int(row[0] or 0) > 0
        }
        if scenes_with_existing_shots:
            logger.info(
                "[ShotImportAPI] batch_create abandon scenes with existing shots | episode_id=%s scene_ids=%s",
                episode_id,
                sorted(scenes_with_existing_shots),
            )

    # Only clear scenes that are empty (or when skip_existing_scene_shots is off).
    clearable_scene_ids = [
        sid for sid in scene_ids
        if sid in scene_by_id and sid not in scenes_with_existing_shots
    ]
    for scene_id in clearable_scene_ids:
        _soft_delete_shots(db, scene_id=scene_id)

    created = 0
    skipped = 0
    seen_shot_keys: set = set()
    for item in items:
        scene_id = int(getattr(item, "scene_id", 0) or 0)
        shot = item.shot
        if scene_id <= 0 or scene_id not in scene_by_id:
            skipped += 1
            continue
        if scene_id in scenes_with_existing_shots:
            skipped += 1
            continue
        business_id = _normalize_shot_business_id(getattr(shot, "shot_id", ""))
        if business_id:
            # Episode-scoped unique key: project + episode + Shot ID
            dedup_key = f"{int(project.id)}::{int(episode.id)}::{business_id}"
            if dedup_key in seen_shot_keys:
                skipped += 1
                logger.warning(
                    "[ShotImportAPI] batch_create skip duplicate Shot ID | scene_id=%s episode_id=%s shot_id=%s",
                    scene_id,
                    episode.id,
                    business_id,
                )
                continue
            existing = _find_active_shot_by_business_id(
                db,
                project_id=int(project.id),
                episode_id=int(episode.id),
                shot_id=business_id,
                exclude_scene_id=scene_id if scene_id in clearable_scene_ids else None,
            )
            if existing is not None:
                skipped += 1
                logger.warning(
                    "[ShotImportAPI] batch_create skip Shot ID already in episode | scene_id=%s shot_id=%s existing_scene_id=%s",
                    scene_id,
                    business_id,
                    getattr(existing, "scene_id", None),
                )
                continue
            seen_shot_keys.add(dedup_key)
        payload = shot.dict(exclude_unset=True)
        _assert_allowed_shot_media_payload(payload, db=db)

        db_shot = Shot(
            scene_id=scene_id,
            project_id=project.id,
            episode_id=episode.id,
            shot_id=business_id or shot.shot_id,
            shot_name=shot.shot_name,
            start_frame=shot.start_frame,
            end_frame=shot.end_frame,
            video_content=shot.video_content,
            duration=shot.duration,
            associated_entities=shot.associated_entities,
            shot_logic_cn=shot.shot_logic_cn,
            keyframes=shot.keyframes,
            scene_code=shot.scene_code,
            image_url=shot.image_url,
            video_url=shot.video_url,
            prompt=shot.prompt,
            technical_notes=shot.technical_notes,
        )
        db.add(db_shot)
        created += 1

    if bool(request.recompute_cost):
        try:
            _recompute_and_persist_project_cost_estimation(db, int(project.id))
        except Exception as cost_exc:
            logger.warning("batch_create_shots cost recompute skipped | project_id=%s err=%s", project.id, cost_exc)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        logger.warning(
            "[ShotImportAPI] batch_create unique conflict | episode_id=%s err=%s",
            episode_id,
            exc,
        )
        raise HTTPException(
            status_code=409,
            detail="Shot ID already exists for this project/episode; batch import abandoned.",
        ) from exc
    _soft_delete_duplicate_active_shots_in_db(
        db,
        episode_id=int(episode.id),
        project_id=int(project.id),
        scope="episode",
    )
    db.commit()
    elapsed_ms = int((time.perf_counter() - started_perf) * 1000)
    logger.info(
        "[ShotImportAPI] batch_create done | episode_id=%s | project_id=%s | processed=%s | created=%s | skipped=%s | abandoned_scenes=%s | elapsed_ms=%s",
        episode_id,
        project.id,
        len(items),
        created,
        skipped,
        len(scenes_with_existing_shots),
        elapsed_ms,
    )
    return {
        "status": "ok",
        "episode_id": int(episode_id),
        "project_id": int(project.id),
        "processed": int(len(items)),
        "created": int(created),
        "skipped": int(skipped),
        "abandoned_scenes": sorted(scenes_with_existing_shots),
        "elapsed_ms": elapsed_ms,
    }

@router.put("/shots/{shot_id}", response_model=ShotOut)
def update_shot(
    shot_id: int,
    shot_in: ShotUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_shot = db.query(Shot).filter(Shot.id == shot_id).first()
    if not db_shot:
        raise HTTPException(status_code=404, detail="Shot not found")
        
    scene = db.query(Scene).filter(Scene.id == db_shot.scene_id).first()
    episode = db.query(Episode).filter(Episode.id == scene.episode_id).first()
    project = _require_project_access(db, episode.project_id, current_user)

    update_data = shot_in.dict(exclude_unset=True)
    update_data = _replace_legacy_temp_urls_in_shot_payload(db, current_user, project, db_shot, update_data)
    update_data = _normalize_ephemeral_shot_media_update(update_data, existing_shot=db_shot)
    _assert_allowed_shot_media_payload(update_data, db=db, existing_shot=db_shot)

    for key, value in update_data.items():
        setattr(db_shot, key, value)
    try:
        _recompute_and_persist_project_cost_estimation(db, int(project.id))
    except Exception as cost_exc:
        logger.warning("update_shot cost recompute skipped | project_id=%s err=%s", project.id, cost_exc)
        
    db.commit()
    db.refresh(db_shot)
    return _refresh_shot_media_urls(db_shot, db)


@router.post("/shots/{shot_id}/persist-media", response_model=Dict[str, Any])
def persist_shot_media(
    shot_id: int,
    payload: ShotPersistMediaRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_shot = db.query(Shot).filter(Shot.id == shot_id, _active_shot_clause()).first()
    if not db_shot:
        raise HTTPException(status_code=404, detail="Shot not found")

    scene = db.query(Scene).filter(Scene.id == db_shot.scene_id, _active_scene_clause()).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    episode = db.query(Episode).filter(Episode.id == scene.episode_id, _active_episode_clause()).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    project = _require_project_access(db, episode.project_id, current_user)

    _repair_shot_media_urls_from_assets(db, current_user, project, db_shot)

    result = _persist_shot_media_slot(
        db,
        current_user,
        project,
        db_shot,
        slot=str(payload.slot or "video"),
        source_url_override=payload.source_url,
    )
    refreshed = _refresh_shot_media_urls(db_shot, db)
    result["shot"] = {
        "id": refreshed.id,
        "video_url": refreshed.video_url,
        "image_url": refreshed.image_url,
        "technical_notes": refreshed.technical_notes,
    }
    return result


@router.post("/shots/{shot_id}/video-cleanup", response_model=Dict[str, Any])
def cleanup_shot_video_local(
    shot_id: int,
    payload: ShotVideoCleanupRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Local ffmpeg cleanup: remove burned-in/soft subtitles and/or BGM (audio track)."""
    db_shot = db.query(Shot).filter(Shot.id == shot_id, _active_shot_clause()).first()
    if not db_shot:
        raise HTTPException(status_code=404, detail="Shot not found")

    scene = db.query(Scene).filter(Scene.id == db_shot.scene_id, _active_scene_clause()).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    episode = db.query(Episode).filter(Episode.id == scene.episode_id, _active_episode_clause()).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)

    action = str(payload.action or "").strip().lower()
    remove_subtitle = action in {"remove_subtitle", "subtitle", "remove_subtitle_and_bgm", "both"}
    remove_bgm = action in {"remove_bgm", "bgm", "remove_audio", "mute", "remove_subtitle_and_bgm", "both"}
    if not remove_subtitle and not remove_bgm:
        raise HTTPException(
            status_code=400,
            detail="action must be one of: remove_subtitle, remove_bgm, remove_subtitle_and_bgm",
        )

    source_url = str(payload.source_url or getattr(db_shot, "video_url", None) or "").strip()
    if not source_url:
        raise HTTPException(status_code=400, detail="Shot has no video to clean up")

    try:
        result = process_video_cleanup_local(
            source_url,
            remove_subtitle=remove_subtitle,
            remove_bgm=remove_bgm,
            user_id=int(current_user.id or 0),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        detail = str(exc)
        if "busy" in detail.lower():
            raise HTTPException(status_code=429, detail=detail)
        raise HTTPException(status_code=500, detail=detail)
    except Exception as exc:
        logger.error("Shot video cleanup failed shot_id=%s action=%s err=%s", shot_id, action, exc)
        raise HTTPException(status_code=500, detail=f"Video cleanup failed: {exc}")

    new_url = str((result or {}).get("url") or "").strip()
    if not new_url:
        raise HTTPException(status_code=500, detail="Video cleanup returned empty url")

    db_shot.video_url = new_url
    try:
        db.add(db_shot)
        db.commit()
        db.refresh(db_shot)
    except Exception as exc:
        db.rollback()
        logger.error("Failed to persist cleaned video_url shot_id=%s err=%s", shot_id, exc)
        raise HTTPException(status_code=500, detail="Cleanup succeeded but failed to save shot video_url")

    return {
        "url": new_url,
        "action": action,
        "remove_subtitle": bool(remove_subtitle),
        "remove_bgm": bool(remove_bgm),
        "shot": {
            "id": db_shot.id,
            "video_url": db_shot.video_url,
        },
    }


@router.post("/entities/{entity_id}/persist-media", response_model=Dict[str, Any])
def persist_entity_media(
    entity_id: int,
    payload: EntityPersistMediaRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entity = db.query(Entity).filter(Entity.id == entity_id, _active_entity_clause()).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    project = _require_project_access(db, entity.project_id, current_user)
    _repair_entity_image_url_from_assets(db, current_user, project, entity)

    result = _persist_entity_image(
        db,
        current_user,
        project,
        entity,
        source_url_override=payload.source_url,
    )
    result["entity"] = {
        "id": entity.id,
        "image_url": entity.image_url,
        "custom_attributes": entity.custom_attributes,
    }
    return result


@router.get("/storage/oss-active-url-signatures", response_model=Dict[str, Any])
def get_oss_active_url_signatures(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    return oss_storage_service.get_active_url_signatures(db)


@router.get("/storage/media-url-inspect", response_model=Dict[str, Any])
def inspect_storage_media_url(
    url: str = Query("", description="Media URL to inspect against active OSS pool configuration"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    raw = str(url or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="url query parameter is required")
    inspection = oss_storage_service.inspect_media_url(raw, db)
    inspection["durable_persisted"] = _is_durable_persisted_media_url(raw, None, db)
    inspection["oss_upload_succeeded"] = _oss_upload_succeeded_for_url(raw, None, db)
    return inspection


@router.delete("/shots/{shot_id}")
def delete_shot(
    shot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_shot = db.query(Shot).filter(Shot.id == shot_id, _active_shot_clause()).first()
    if not db_shot:
         raise HTTPException(status_code=404, detail="Shot not found")
         
    scene = db.query(Scene).filter(Scene.id == db_shot.scene_id, _active_scene_clause()).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    episode = db.query(Episode).filter(Episode.id == scene.episode_id, _active_episode_clause()).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    project = _require_project_access(db, episode.project_id, current_user, owner_only=True)

    if _is_soft_deleted(db_shot):
        return {"ok": True, "batch_id": None}

    shot_label = str(db_shot.shot_name or db_shot.shot_id or f"Shot {shot_id}")
    batch_id = _start_deletion_batch(
        db,
        user_id=current_user.id,
        project_id=int(project.id),
        episode_id=int(episode.id),
        action_type="shot",
        label=shot_label,
    )
    _soft_delete_shots(db, shot_id=shot_id, batch_id=batch_id)
    _finalize_deletion_batch(db, batch_id)
    try:
        _recompute_and_persist_project_cost_estimation(db, int(project.id))
    except Exception as cost_exc:
        logger.warning("delete_shot cost recompute skipped | project_id=%s err=%s", project.id, cost_exc)
    db.commit()
    return {"ok": True, "batch_id": batch_id}

