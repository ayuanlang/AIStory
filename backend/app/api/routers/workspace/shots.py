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


# Compact shot list helpers (canonical: app.services.shot_list_compact).
from app.services.shot_list_compact import (  # noqa: E402,F401
    _SHOT_LIST_COMPACT_TECH_KEYS,
    _compact_shot_list_technical_notes,
    _build_compact_shot_payload,
)

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

