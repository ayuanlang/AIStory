# -*- coding: utf-8 -*-
"""Shot media batch job workers (keyframes / video)."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from app.core.time_utils import now_bj_iso
from app.db.session import SessionLocal
from app.models.all_models import Episode, Shot, User
from app.schemas.generation import GenerationRequest, VideoGenerationRequest
from app.schemas.user_auth import (
    USER_ACTIVE_LEVEL_DEFAULT,
    resolve_user_batch_parallel_limit as _resolve_user_batch_parallel_limit,
)
from app.services.db_session_utils import _release_db_connection, _snapshot_user_principal
from app.services.endpoint_misc import _log_batch_sys_event
from app.services.generation_runtime.image_generation_runner import _run_generate_image
from app.services.generation_runtime.job_store import (
    SHOT_MEDIA_BATCH_THREADS,
    SHOT_MEDIA_BATCH_THREADS_LOCK,
    _clear_episode_worker,
    _clear_shot_media_batch_cancel_event,
    _get_shot_media_batch_cancel_event,
)
from app.services.generation_runtime.seedance_duration import _resolve_shot_video_duration_value
from app.services.generation_runtime.video_generation_runner import _run_generate_video
from app.services.generation_runtime.video_ref_pipeline import (
    _append_video_api_ref_mapping,
    _build_project_entity_lookup,
    _compute_subject_ref_index_map,
    _ensure_video_frame_role_instructions,
    _find_previous_shot_end_frame_url,
    _inject_shot_prompt_anchors,
    _listify_video_ref_urls,
    _parse_shot_tech,
    _resolve_default_shot_image_gen_refs,
    _resolve_shot_video_panel_image_refs,
    _sync_request_image_refs_with_aligned,
)
from app.services.media_service import media_service
from app.services.project_episode_utils import _episode_runtime_info_from_episode
from app.services.shot_media_batch_status import (
    SHOT_MEDIA_BATCH_DEFAULT_CONCURRENCY,
    _persist_shot_media_batch_status,
    _read_shot_media_batch_status,
)
from app.services.system_api_lookup import get_system_api_setting

logger = logging.getLogger("api_logger")

# Batch video always runs the entity-reference automatic path.
BATCH_SHOT_VIDEO_MODE = "entity_refs"


def _shot_has_video_prompt(shot: Shot) -> bool:
    tech = _parse_shot_tech(shot)
    return bool(
        str(getattr(shot, "video_content", None) or "").strip()
        or str(getattr(shot, "prompt", None) or "").strip()
        or str((tech or {}).get("video_prompt_cn") or "").strip()
    )


def _is_manual_video_ref_override(tech: Dict[str, Any]) -> bool:
    notes = tech if isinstance(tech, dict) else {}
    return bool(notes.get("video_ref_image_urls_manual") or notes.get("video_ref_image_urls_user_edited"))


def _resolve_batch_entity_ref_images(
    shot: Shot,
    tech: Dict[str, Any],
    entity_lookup: Dict[str, Dict[str, Any]],
) -> tuple:
    """Entity-reference images for batch video.

    Auto mode rebuilds from names in the video prompt. A stored
    ``video_ref_image_urls`` list is only honored after an explicit manual edit,
    so stale panel snapshots cannot skip reference-image collection.
    """
    notes = dict(tech) if isinstance(tech, dict) else {}
    manual = _is_manual_video_ref_override(notes)
    forced = dict(notes)
    forced["video_mode_unified"] = BATCH_SHOT_VIDEO_MODE
    forced["video_ref_submit_mode"] = BATCH_SHOT_VIDEO_MODE
    if not manual:
        forced.pop("video_ref_image_urls", None)
        forced["video_ref_image_urls_manual"] = False
        forced["video_ref_image_urls_user_edited"] = False
    refs = _resolve_shot_video_panel_image_refs(shot, forced, entity_lookup)
    return refs, manual


def _apply_entity_ref_prompt(
    prompt_raw: str,
    *,
    entity_lookup: Dict[str, Dict[str, Any]],
    global_style: str,
    ordered_refs: List[str],
    normalized_refs: Optional[List[str]],
    use_prev_video: bool,
    provider: str,
    model: str,
    manual_override: bool,
) -> tuple:
    """Inject entity anchors, then bind those images to @ImageN."""
    source = str(prompt_raw or "").strip()
    if not source:
        return "", list(ordered_refs or []), normalized_refs
    ref_index_map = _compute_subject_ref_index_map(source, entity_lookup)
    anchored = _inject_shot_prompt_anchors(source, entity_lookup, global_style, ref_index_map)
    mapped, aligned_refs = _append_video_api_ref_mapping(
        anchored,
        list(ordered_refs or []),
        normalized_refs,
        None,
        None,
        None,
        entity_lookup=entity_lookup,
        use_prev_video=bool(use_prev_video),
        provider=provider,
        model=model,
        preserve_submitted_refs=bool(manual_override),
    )
    _, synced_refs = _sync_request_image_refs_with_aligned(
        aligned_refs=aligned_refs,
        image_urls=None,
        ref_image_url=normalized_refs,
        last_frame_url=None,
        keyframes=None,
    )
    mapped = _ensure_video_frame_role_instructions(
        mapped,
        ref_mode=BATCH_SHOT_VIDEO_MODE,
        image_urls=_listify_video_ref_urls(synced_refs),
        last_frame_url=None,
        start_frame_url=None,
    )
    return mapped, aligned_refs, synced_refs


def _is_shot_video_batch_eligible(shot: Shot, overwrite_existing: bool = False) -> bool:
    video_url = str(getattr(shot, "video_url", "") or "").strip()
    if not overwrite_existing and video_url:
        return False
    return _shot_has_video_prompt(shot)

def _run_shot_media_video_batch_item(episode_id: int, shot_id: int, user_id: int, overwrite_existing: bool = False, system_api_id: Optional[int] = None, use_prev_video: bool = False) -> Dict[str, Any]:
    item_db = SessionLocal()
    cancel_event = _get_shot_media_batch_cancel_event(int(episode_id), create=True)

    class _BatchStopRequested(Exception):
        pass

    async def _run_cancellable(coro: Any) -> Any:
        task = asyncio.create_task(coro)
        try:
            while True:
                done, _ = await asyncio.wait({task}, timeout=0.5)
                if task in done:
                    return await task
                if cancel_event and cancel_event.is_set():
                    task.cancel()
                    try:
                        await task
                    except BaseException:
                        pass
                    raise _BatchStopRequested("Stop requested")
        finally:
            if not task.done():
                task.cancel()

    async def _run_stage_with_retry(coro_factory: Any, max_attempts: int = 3) -> Any:
        last_error: Optional[Exception] = None
        for attempt in range(1, max(2, max_attempts + 1)):
            if cancel_event and cancel_event.is_set():
                raise _BatchStopRequested("Stop requested")
            try:
                return await _run_cancellable(coro_factory())
            except _BatchStopRequested:
                raise
            except Exception as exc:
                last_error = exc
                try:
                    item_db.rollback()
                except Exception:
                    pass
                if attempt < max_attempts:
                    logger.warning(
                        "[shot_media_batch] video stage retry | shot_id=%s attempt=%s/%s error=%s",
                        shot_id,
                        attempt,
                        max_attempts,
                        exc,
                    )
                    await asyncio.sleep(min(4, attempt))
                    continue
        raise Exception(f"video failed after {max_attempts} attempts: {last_error}")

    try:
        episode = item_db.query(Episode).filter(Episode.id == episode_id).first()
        user = item_db.query(User).filter(User.id == user_id).first()
        shot = item_db.query(Shot).filter(Shot.id == shot_id, Shot.episode_id == episode_id).first()
        if not episode or not user or not shot:
            raise Exception("Shot batch item not found")
        user_principal = _snapshot_user_principal(user)

        shot_label = str(shot.shot_id or shot.shot_name or f"#{shot.id}")
        tech = _parse_shot_tech(shot)
        video_url = str(shot.video_url or "").strip()

        if not overwrite_existing and video_url:
            return {
                "shot_id": int(shot.id),
                "shot_label": shot_label,
                "ok": True,
                "skipped": True,
                "skip_reason": "existing_video",
            }
        if not _shot_has_video_prompt(shot):
            return {
                "shot_id": int(shot.id),
                "shot_label": shot_label,
                "ok": True,
                "skipped": True,
                "skip_reason": "missing_prompt",
            }

        episode_info = _episode_runtime_info_from_episode(episode)
        e_global_info = episode_info.get("e_global_info", {}) if isinstance(episode_info, dict) else {}
        global_style = str((e_global_info or {}).get("Global_Style") or "").strip()
        entity_lookup = _build_project_entity_lookup(
            item_db, int(episode.project_id), episode_id=int(episode_id)
        )

        video_mode = BATCH_SHOT_VIDEO_MODE
        entity_refs, manual_override = _resolve_batch_entity_ref_images(shot, tech, entity_lookup)
        normalized_refs = entity_refs or None

        system_api_id_val = system_api_id
        if not system_api_id_val and getattr(episode, "system_api_id", None):
            system_api_id_val = episode.system_api_id

        is_seedance_batch = False
        pre_api_cfg: Dict[str, Any] = {}
        if system_api_id_val:
            pre_api_row = get_system_api_setting(item_db, setting_id=int(system_api_id_val))
            pre_api_cfg = {
                "provider": str(getattr(pre_api_row, "provider", "") or "").strip(),
                "model": str(getattr(pre_api_row, "model", "") or "").strip(),
            }
            if "seedance" in str(pre_api_cfg.get("provider") or "").lower() or "seedance" in str(pre_api_cfg.get("model") or "").lower():
                is_seedance_batch = True

        provider_name = "seedance" if is_seedance_batch else ""
        model_name = str(pre_api_cfg.get("model") or "")
        ordered_video_refs = _listify_video_ref_urls(normalized_refs)
        video_prompt_raw = str(shot.video_content or shot.prompt or "").strip() or "Video motion"
        video_prompt, ordered_video_refs, normalized_refs = _apply_entity_ref_prompt(
            video_prompt_raw,
            entity_lookup=entity_lookup,
            global_style=global_style,
            ordered_refs=ordered_video_refs,
            normalized_refs=entity_refs,
            use_prev_video=bool(use_prev_video),
            provider=provider_name,
            model=model_name,
            manual_override=manual_override,
        )

        video_prompt_cn_raw = str(tech.get("video_prompt_cn") or "").strip()
        video_prompt_cn = ""
        if video_prompt_cn_raw:
            video_prompt_cn, ordered_video_refs, normalized_refs = _apply_entity_ref_prompt(
                video_prompt_cn_raw,
                entity_lookup=entity_lookup,
                global_style=global_style,
                ordered_refs=ordered_video_refs,
                normalized_refs=_listify_video_ref_urls(normalized_refs) or entity_refs,
                use_prev_video=bool(use_prev_video),
                provider=provider_name,
                model=model_name,
                manual_override=manual_override,
            )
            tech["video_prompt_cn"] = video_prompt_cn
            item_db.query(type(shot)).filter(type(shot).id == shot.id).update({"technical_notes": json.dumps(tech, ensure_ascii=False)})
            item_db.commit()

        logger.info(
            "[shot_media_batch] entity_refs auto execute | shot_id=%s shot_label=%s video_mode=%s refs=%s manual=%s anchor_injected=%s image_tags=%s",
            shot.id,
            shot_label,
            video_mode,
            len(_listify_video_ref_urls(normalized_refs)),
            manual_override,
            video_prompt != video_prompt_raw,
            len(re.findall(r"@Image\d+", str(video_prompt or ""), flags=re.IGNORECASE)),
        )

        batch_status = _read_shot_media_batch_status(episode) if episode else {}
        duration_val = _resolve_shot_video_duration_value(
            shot_duration=shot.duration,
            sd2_auto_duration=bool((batch_status or {}).get("sd2_auto_duration")),
            system_api_id=system_api_id,
            db=item_db,
        )

        multi_prompt_payload = None
        if video_prompt_cn:
            multi_prompt_payload = [
                {"prompt": video_prompt, "type": "en"},
                {"prompt": video_prompt_cn, "type": "zh"}
            ]
        video_req = VideoGenerationRequest(
            draft_mode=bool((batch_status or {}).get("draft_mode")),
            prompt=video_prompt,
            multi_prompt=multi_prompt_payload,
            ref_image_url=normalized_refs,
            last_frame_url=None,
            ref_mode=video_mode,
            keyframes=None,
            duration=duration_val,
            project_id=episode.project_id,
            episode_id=int(episode_id),
            shot_id=shot.id,
            shot_number=shot.shot_id,
            shot_name=shot.shot_name,
            asset_type="video",
            system_api_id=system_api_id,
            use_prev_video=bool(use_prev_video),
        )
        _release_db_connection(item_db, "shot_media_batch_video")
        try:
            callback_ticket_val = f"video-shot-{shot.id}"
            callback_url_val = str(media_service._resolve_provider_callback_url({}, callback_ticket_val) or "").strip()
        except Exception:
            callback_ticket_val = f"video-shot-{shot.id}"
            callback_url_val = ""

        asyncio.run(_run_stage_with_retry(
            lambda: _run_generate_video(
                req=video_req,
                current_user=user_principal,
                db=item_db,
                provider_callback_ticket=callback_ticket_val,
                provider_callback_url=callback_url_val
            ),
        ))

        return {
            "shot_id": int(shot.id),
            "shot_label": shot_label,
            "ok": True,
            "skipped": False,
        }
    finally:
        item_db.close()


def _run_shot_media_batch_job(episode_id: int, request_payload: Dict[str, Any], user_id: int) -> None:
    db = SessionLocal()
    cancel_event = _get_shot_media_batch_cancel_event(int(episode_id), create=True)
    min_prompt_chars = 5

    class _BatchStopRequested(Exception):
        pass

    async def _run_cancellable(coro: Any) -> Any:
        task = asyncio.create_task(coro)
        try:
            while True:
                done, _ = await asyncio.wait({task}, timeout=0.5)
                if task in done:
                    return await task
                if cancel_event and cancel_event.is_set():
                    task.cancel()
                    try:
                        await task
                    except BaseException:
                        pass
                    raise _BatchStopRequested("Stop requested")
        finally:
            if not task.done():
                task.cancel()
    try:
        episode = db.query(Episode).filter(Episode.id == episode_id).first()
        user = db.query(User).filter(User.id == user_id).first()
        if not episode or not user:
            return
        user_principal = _snapshot_user_principal(user)

        user_name = str(user_principal.username or f"user_{user_id}")
        project_id = int(episode.project_id)
        job_id = f"shot-media-batch:{int(episode_id)}"

        episode_info = _episode_runtime_info_from_episode(episode)
        e_global_info = episode_info.get("e_global_info", {}) if isinstance(episode_info, dict) else {}
        global_style = str((e_global_info or {}).get("Global_Style") or "").strip()
        entity_lookup = _build_project_entity_lookup(
            db, int(episode.project_id), episode_id=int(episode.id) if getattr(episode, "id", None) else None
        )

        mode = str((request_payload or {}).get("mode") or "keyframes").strip().lower()
        overwrite_existing = bool((request_payload or {}).get("overwrite_existing"))
        system_api_id = request_payload.get("system_api_id")
        if system_api_id is not None:
            try:
                system_api_id = int(system_api_id)
            except ValueError:
                system_api_id = None
        requested_shot_ids = [int(x) for x in ((request_payload or {}).get("shot_ids") or []) if x]
        batch_max_concurrency = _resolve_user_batch_parallel_limit(
            getattr(user_principal, "is_active", USER_ACTIVE_LEVEL_DEFAULT),
            default=SHOT_MEDIA_BATCH_DEFAULT_CONCURRENCY,
        )

        shots_query = db.query(Shot).filter(Shot.episode_id == episode_id).order_by(Shot.id.asc())
        if requested_shot_ids:
            shots_query = shots_query.filter(Shot.id.in_(requested_shot_ids))
        target_shots = shots_query.all()

        total = len(target_shots)
        completed = 0
        success = 0
        failed = 0
        errors: List[str] = []
        _release_db_connection(db, "shot_media_batch_bootstrap")

        def _read_latest_episode() -> Optional[Episode]:
            db.expire_all()
            return (
                db.query(Episode)
                .execution_options(populate_existing=True)
                .filter(Episode.id == episode_id)
                .first()
            )

        def _persist_stopped_status() -> None:
            latest_episode = _read_latest_episode()
            if not latest_episode:
                return
            latest_status = _read_shot_media_batch_status(latest_episode)
            latest_status["running"] = False
            latest_status["completed"] = completed
            latest_status["success"] = success
            latest_status["failed"] = failed
            latest_status["errors"] = errors
            latest_status["stopped_by_user"] = True
            latest_status["current_asset_type"] = None
            latest_status["current_asset_label"] = ""
            latest_status["message"] = "Stopped by user request"
            latest_status["finished_at"] = now_bj_iso()
            latest_status["updated_at"] = latest_status["finished_at"]
            _persist_shot_media_batch_status(db, latest_episode, latest_status)
            _log_batch_sys_event(
                kind="shot-media-batch",
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
            _release_db_connection(db, "shot_media_batch_stopped_status")

        def _is_stop_requested() -> bool:
            if cancel_event and cancel_event.is_set():
                return True
            latest_episode = _read_latest_episode()
            if not latest_episode:
                return True
            latest_status = _read_shot_media_batch_status(latest_episode)
            _release_db_connection(db, "shot_media_batch_stop_check")
            return bool(latest_status.get("stop_requested") or latest_status.get("force_stopped"))

        async def _run_stage_with_retry(coro_factory: Any, stage_label: str, shot_label: str, max_attempts: int = 3) -> Any:
            last_error: Optional[Exception] = None
            for attempt in range(1, max(2, max_attempts + 1)):
                if _is_stop_requested():
                    raise _BatchStopRequested("Stop requested")

                if attempt > 1:
                    latest_episode = _read_latest_episode()
                    if latest_episode:
                        latest_status = _read_shot_media_batch_status(latest_episode)
                        latest_status["message"] = f"Retrying {stage_label} for shot {shot_label} ({attempt}/{max_attempts})..."
                        latest_status["updated_at"] = now_bj_iso()
                        _persist_shot_media_batch_status(db, latest_episode, latest_status)
                        _release_db_connection(db, "shot_media_batch_retry_status")

                try:
                    return await _run_cancellable(coro_factory())
                except _BatchStopRequested:
                    raise
                except Exception as exc:
                    last_error = exc
                    try:
                        db.rollback()
                    except Exception:
                        pass

                    if attempt < max_attempts:
                        logger.warning(
                            "[shot_media_batch] stage retry | stage=%s shot=%s attempt=%s/%s error=%s",
                            stage_label,
                            shot_label,
                            attempt,
                            max_attempts,
                            exc,
                        )
                        await asyncio.sleep(min(4, attempt))
                        continue

            raise Exception(f"{stage_label} failed after {max_attempts} attempts: {last_error}")

        if mode == "videos":
            shot_label_map = {
                int(shot.id): str(shot.shot_id or shot.shot_name or f"#{shot.id}")
                for shot in target_shots
            }
            next_shot_index = 0
            active_future_map: Dict[Any, int] = {}

            def _active_shot_ids() -> List[int]:
                return list(active_future_map.values())

            def _persist_active_video_status(latest_episode: Optional[Episode], latest_message: Optional[str] = None) -> None:
                if not latest_episode:
                    return
                latest_status = _read_shot_media_batch_status(latest_episode)
                active_shot_ids = _active_shot_ids()
                active_shot_labels = [shot_label_map.get(sid) or f"#{sid}" for sid in active_shot_ids]
                latest_status["current_shot_id"] = active_shot_ids[0] if len(active_shot_ids) == 1 else None
                latest_status["current_shot_label"] = " / ".join(active_shot_labels)
                latest_status["current_asset_type"] = "video" if active_shot_labels else None
                latest_status["current_asset_label"] = "Video" if active_shot_labels else ""
                latest_status["updated_at"] = now_bj_iso()
                if latest_message is not None:
                    latest_status["message"] = latest_message
                elif active_shot_labels:
                    latest_status["message"] = (
                        f"Processing shots {', '.join(active_shot_labels)} · Video..."
                        if len(active_shot_labels) > 1
                        else f"Processing shot {active_shot_labels[0]} · Video..."
                    )
                _persist_shot_media_batch_status(db, latest_episode, latest_status)
                _release_db_connection(db, "shot_media_batch_active_video_status")

            def _submit_next_shot(executor: ThreadPoolExecutor) -> bool:
                nonlocal next_shot_index
                if next_shot_index >= len(target_shots):
                    return False
                shot = target_shots[next_shot_index]
                next_shot_index += 1
                active_future_map[executor.submit(
                    _run_shot_media_video_batch_item,
                    episode_id,
                    int(shot.id),
                    user_id,
                    overwrite_existing,
                    system_api_id,
                    bool((request_payload or {}).get("use_prev_video")),
                )] = int(shot.id)
                return True

            max_workers = max(1, min(batch_max_concurrency, total or 1))
            if bool((request_payload or {}).get("use_prev_video")):
                max_workers = 1
                logger.info(
                    "[shot_media_batch] forcing sequential video batch for previous-video continuation | episode_id=%s total=%s",
                    episode_id,
                    total,
                )
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                while len(active_future_map) < max_workers and _submit_next_shot(executor):
                    pass

                episode = _read_latest_episode()
                if episode and _is_stop_requested():
                    _persist_stopped_status()
                    return
                _persist_active_video_status(episode)

                while active_future_map:
                    completed_future = next(as_completed(list(active_future_map.keys())))
                    sid = active_future_map.pop(completed_future)
                    shot_label = shot_label_map.get(sid) or f"#{sid}"
                    try:
                        result = completed_future.result()
                    except Exception as e:
                        if _is_stop_requested():
                            _persist_stopped_status()
                            return
                        result = {
                            "shot_id": sid,
                            "shot_label": shot_label,
                            "ok": False,
                            "error": str(e),
                        }

                    if bool(result.get("ok")):
                        success += 1
                        _log_batch_sys_event(
                            kind="shot-media-batch",
                            phase="item",
                            user_id=user_id,
                            user_name=user_name,
                            project_id=project_id,
                            episode_id=episode_id,
                            job_id=job_id,
                            item_id=sid,
                            item_label=result.get("shot_label") or shot_label,
                            result="success",
                            message="Shot video generated" if not bool(result.get("skipped")) else "Shot video skipped",
                            extra={
                                "mode": mode,
                                "skipped": bool(result.get("skipped")),
                                "skip_reason": result.get("skip_reason"),
                            },
                        )
                    else:
                        failed += 1
                        error_message = str(result.get("error") or "Unknown error")
                        errors.append(f"{result.get('shot_label') or shot_label}: {error_message}")
                        _log_batch_sys_event(
                            kind="shot-media-batch",
                            phase="item",
                            user_id=user_id,
                            user_name=user_name,
                            project_id=project_id,
                            episode_id=episode_id,
                            job_id=job_id,
                            item_id=sid,
                            item_label=result.get("shot_label") or shot_label,
                            result="failed",
                            message=error_message,
                            extra={"mode": mode},
                        )

                    completed += 1
                    while len(active_future_map) < max_workers and not _is_stop_requested() and _submit_next_shot(executor):
                        pass

                    episode = _read_latest_episode()
                    if not episode:
                        break
                    latest = _read_shot_media_batch_status(episode)
                    latest["completed"] = completed
                    latest["success"] = success
                    latest["failed"] = failed
                    latest["errors"] = errors
                    latest["updated_at"] = now_bj_iso()
                    latest["message"] = f"Progress {completed}/{total}" if bool(result.get("ok")) else f"Progress {completed}/{total} (with errors)"
                    _persist_shot_media_batch_status(db, episode, latest)
                    _release_db_connection(db, "shot_media_batch_video_progress")

                    if _is_stop_requested():
                        _persist_stopped_status()
                        return

                    _persist_active_video_status(episode)

            episode = _read_latest_episode()
            if episode:
                final_status = _read_shot_media_batch_status(episode)
                final_status["running"] = False
                final_status["completed"] = completed
                final_status["success"] = success
                final_status["failed"] = failed
                final_status["errors"] = errors
                final_status["current_asset_type"] = None
                final_status["current_asset_label"] = ""
                final_status["updated_at"] = now_bj_iso()
                final_status["finished_at"] = final_status["updated_at"]
                final_status["message"] = f"Batch done: success {success}, failed {failed}"
                _persist_shot_media_batch_status(db, episode, final_status)
                _log_batch_sys_event(
                    kind="shot-media-batch",
                    phase="end",
                    user_id=user_id,
                    user_name=user_name,
                    project_id=project_id,
                    episode_id=episode_id,
                    job_id=job_id,
                    result="completed",
                    message=final_status.get("message"),
                    extra={
                        "completed": completed,
                        "success": success,
                        "failed": failed,
                        "mode": mode,
                        "max_concurrency": max_workers,
                    },
                )
                _release_db_connection(db, "shot_media_batch_video_final")
            return

        for shot in target_shots:
            episode = _read_latest_episode()
            if not episode:
                break
            latest = _read_shot_media_batch_status(episode)
            if bool(latest.get("stop_requested") or latest.get("force_stopped")):
                _persist_stopped_status()
                return

            shot_label = str(shot.shot_id or shot.shot_name or f"#{shot.id}")
            latest["current_shot_id"] = shot.id
            latest["current_shot_label"] = shot_label
            latest["message"] = f"Processing shot {shot_label}..."
            latest["updated_at"] = now_bj_iso()
            _persist_shot_media_batch_status(db, episode, latest)
            _release_db_connection(db, "shot_media_batch_shot_start")

            shot_ok = True
            try:
                tech = _parse_shot_tech(shot)
                end_frame_url = str(tech.get("end_frame_url") or "").strip()

                need_start = overwrite_existing or not str(shot.image_url or "").strip()
                need_end = overwrite_existing or not end_frame_url

                if _is_stop_requested():
                    _persist_stopped_status()
                    return

                if need_start:
                    start_prompt_raw = str(shot.start_frame or shot.video_content or "").strip()
                    if start_prompt_raw:
                        is_sap_start_prompt = str(start_prompt_raw).strip().upper() == "SAP"
                        prev_end = _find_previous_shot_end_frame_url(db, episode_id, int(shot.id))
                        if is_sap_start_prompt and prev_end:
                            tech = _parse_shot_tech(shot)
                            shot.image_url = prev_end
                            if str(tech.get("start_frame_url") or "").strip() != prev_end:
                                tech["start_frame_url"] = prev_end
                                shot.technical_notes = json.dumps(tech, ensure_ascii=False)
                            db.add(shot)
                            db.commit()
                            db.refresh(shot)
                            logger.info(
                                "[shot_media_batch] SAP start_frame linked from previous end_frame | shot_id=%s shot_label=%s prev_end=%s",
                                shot.id,
                                shot_label,
                                prev_end,
                            )
                        elif len(start_prompt_raw) < min_prompt_chars:
                            logger.info(
                                "[shot_media_batch] skip start_frame due to short prompt | shot_id=%s shot_label=%s prompt_len=%s",
                                shot.id,
                                shot_label,
                                len(start_prompt_raw),
                            )
                        else:
                            latest = _read_shot_media_batch_status(episode)
                            latest["current_shot_id"] = shot.id
                            latest["current_shot_label"] = shot_label
                            latest["current_asset_type"] = "start_frame"
                            latest["current_asset_label"] = "Start Frame"
                            latest["message"] = f"Processing shot {shot_label} · Start Frame..."
                            latest["updated_at"] = now_bj_iso()
                            _persist_shot_media_batch_status(db, episode, latest)
                            _release_db_connection(db, "shot_media_batch_start_status")

                            start_ref_index_map = _compute_subject_ref_index_map(start_prompt_raw, entity_lookup)
                            logger.info(
                                "[shot_media_batch] subject_ref_index_map asset=start_frame shot_id=%s shot_label=%s map=%s",
                                shot.id,
                                shot_label,
                                start_ref_index_map,
                            )
                            start_prompt = _inject_shot_prompt_anchors(start_prompt_raw, entity_lookup, global_style, start_ref_index_map)
                            start_refs = _resolve_default_shot_image_gen_refs(
                                shot, tech, entity_lookup, panel="start"
                            )
                            deleted_refs = {str(x).strip() for x in tech.get("deleted_ref_urls") or [] if str(x).strip()}
                            if is_sap_start_prompt and prev_end and prev_end not in start_refs and prev_end not in deleted_refs:
                                # SAP means reusing previous shot end frame as current start reference.
                                start_refs.insert(0, prev_end)

                            start_refs = [x for x in dict.fromkeys([str(x).strip() for x in start_refs if str(x).strip()]) if x]
                            start_req = GenerationRequest(
                                prompt=start_prompt,
                                ref_image_url=start_refs if start_refs else None,
                                project_id=episode.project_id,
                                shot_id=shot.id,
                                shot_number=shot.shot_id,
                                shot_name=shot.shot_name,
                                asset_type="start_frame",
                            )
                            _release_db_connection(db, "shot_media_batch_start_frame")
                            asyncio.run(_run_stage_with_retry(
                                lambda: _run_generate_image(req=start_req, current_user=user_principal, db=db),
                                "start_frame",
                                shot_label,
                            ))
                            shot = db.query(Shot).filter(Shot.id == shot.id).first() or shot

                if _is_stop_requested():
                    _persist_stopped_status()
                    return

                if need_end:
                    end_prompt_raw = str(shot.end_frame or "").strip()
                    if end_prompt_raw:
                        normalized_end_prompt = end_prompt_raw.strip().upper()
                        should_reuse_start_as_end = normalized_end_prompt in {"NO", "N/A", "NONE", "NULL", "NA"}
                        if should_reuse_start_as_end:
                            start_frame_url = str(shot.image_url or "").strip()
                            if start_frame_url:
                                tech = _parse_shot_tech(shot)
                                prev_end_url = str(tech.get("end_frame_url") or "").strip()
                                if prev_end_url != start_frame_url:
                                    tech["end_frame_url"] = start_frame_url
                                    tech["end_frame_reused_from_start"] = True
                                    shot.technical_notes = json.dumps(tech, ensure_ascii=False)
                                    db.add(shot)
                                    db.commit()
                                    db.refresh(shot)
                                end_frame_url = start_frame_url
                                logger.info(
                                    "[shot_media_batch] end_frame=NO-like, reuse start_frame_url | shot_id=%s shot_label=%s end_frame_url=%s",
                                    shot.id,
                                    shot_label,
                                    start_frame_url,
                                )
                            else:
                                logger.info(
                                    "[shot_media_batch] end_frame=NO-like but start_frame_url missing | shot_id=%s shot_label=%s",
                                    shot.id,
                                    shot_label,
                                )
                        elif len(end_prompt_raw) < min_prompt_chars:
                            logger.info(
                                "[shot_media_batch] skip end_frame due to short prompt | shot_id=%s shot_label=%s prompt_len=%s",
                                shot.id,
                                shot_label,
                                len(end_prompt_raw),
                            )
                        else:
                            latest = _read_shot_media_batch_status(episode)
                            latest["current_shot_id"] = shot.id
                            latest["current_shot_label"] = shot_label
                            latest["current_asset_type"] = "end_frame"
                            latest["current_asset_label"] = "End Frame"
                            latest["message"] = f"Processing shot {shot_label} · End Frame..."
                            latest["updated_at"] = now_bj_iso()
                            _persist_shot_media_batch_status(db, episode, latest)
                            _release_db_connection(db, "shot_media_batch_end_status")

                            end_ref_index_map = _compute_subject_ref_index_map(end_prompt_raw, entity_lookup)
                            logger.info(
                                "[shot_media_batch] subject_ref_index_map asset=end_frame shot_id=%s shot_label=%s map=%s",
                                shot.id,
                                shot_label,
                                end_ref_index_map,
                            )
                            end_prompt = _inject_shot_prompt_anchors(end_prompt_raw, entity_lookup, global_style, end_ref_index_map)
                            refs = _resolve_default_shot_image_gen_refs(
                                shot, tech, entity_lookup, panel="end"
                            )
                            refs = [x for x in dict.fromkeys([str(x).strip() for x in refs if str(x).strip()]) if x]
                            end_req = GenerationRequest(
                                prompt=end_prompt,
                                ref_image_url=refs if refs else None,
                                project_id=episode.project_id,
                                shot_id=shot.id,
                                shot_number=shot.shot_id,
                                shot_name=shot.shot_name,
                                asset_type="end_frame",
                            )
                            _release_db_connection(db, "shot_media_batch_end_frame")
                            asyncio.run(_run_stage_with_retry(
                                lambda: _run_generate_image(req=end_req, current_user=user_principal, db=db),
                                "end_frame",
                                shot_label,
                            ))
                            shot = db.query(Shot).filter(Shot.id == shot.id).first() or shot
                            tech = _parse_shot_tech(shot)
                            end_frame_url = str(tech.get("end_frame_url") or "").strip()

                if _is_stop_requested():
                    _persist_stopped_status()
                    return

                if mode == "videos":
                    need_video = overwrite_existing or not str(shot.video_url or "").strip()
                    if need_video:
                        latest = _read_shot_media_batch_status(episode)
                        latest["current_shot_id"] = shot.id
                        latest["current_shot_label"] = shot_label
                        latest["current_asset_type"] = "video"
                        latest["current_asset_label"] = "Video"
                        latest["message"] = f"Processing shot {shot_label} · Video..."
                        latest["updated_at"] = now_bj_iso()
                        _persist_shot_media_batch_status(db, episode, latest)
                        _release_db_connection(db, "shot_media_batch_video_status")

                        video_mode = BATCH_SHOT_VIDEO_MODE
                        entity_refs, manual_override = _resolve_batch_entity_ref_images(shot, tech, entity_lookup)
                        normalized_refs = entity_refs or None

                        batch_provider = str((request_payload or {}).get("provider") or "").strip()
                        batch_model = str((request_payload or {}).get("model") or "").strip()
                        if system_api_id:
                            try:
                                pre_api_row = get_system_api_setting(db, setting_id=int(system_api_id))
                                batch_provider = batch_provider or str(getattr(pre_api_row, "provider", "") or "").strip()
                                batch_model = batch_model or str(getattr(pre_api_row, "model", "") or "").strip()
                            except Exception:
                                pass
                        is_seedance_batch = (
                            "seedance" in batch_provider.lower() or "seedance" in batch_model.lower()
                        )
                        provider_name = "seedance" if is_seedance_batch else ""
                        use_prev_video = bool((request_payload or {}).get("use_prev_video"))
                        ordered_video_refs = _listify_video_ref_urls(normalized_refs)
                        video_prompt_raw = str(shot.video_content or shot.prompt or "").strip() or "Video motion"
                        video_prompt, ordered_video_refs, normalized_refs = _apply_entity_ref_prompt(
                            video_prompt_raw,
                            entity_lookup=entity_lookup,
                            global_style=global_style,
                            ordered_refs=ordered_video_refs,
                            normalized_refs=entity_refs,
                            use_prev_video=use_prev_video,
                            provider=provider_name,
                            model=batch_model,
                            manual_override=manual_override,
                        )

                        video_prompt_cn_raw = str(tech.get("video_prompt_cn") or "").strip()
                        video_prompt_cn = ""
                        if video_prompt_cn_raw:
                            video_prompt_cn, ordered_video_refs, normalized_refs = _apply_entity_ref_prompt(
                                video_prompt_cn_raw,
                                entity_lookup=entity_lookup,
                                global_style=global_style,
                                ordered_refs=ordered_video_refs,
                                normalized_refs=_listify_video_ref_urls(normalized_refs) or entity_refs,
                                use_prev_video=use_prev_video,
                                provider=provider_name,
                                model=batch_model,
                                manual_override=manual_override,
                            )
                            tech["video_prompt_cn"] = video_prompt_cn
                            db.query(type(shot)).filter(type(shot).id == shot.id).update({"technical_notes": json.dumps(tech, ensure_ascii=False)})
                            db.commit()

                        logger.info(
                            "[shot_media_batch] entity_refs auto execute | shot_id=%s shot_label=%s video_mode=%s refs=%s manual=%s anchor_injected=%s image_tags=%s",
                            shot.id,
                            shot_label,
                            video_mode,
                            len(_listify_video_ref_urls(normalized_refs)),
                            manual_override,
                            video_prompt != video_prompt_raw,
                            len(re.findall(r"@Image\d+", str(video_prompt or ""), flags=re.IGNORECASE)),
                        )

                        batch_status = _read_shot_media_batch_status(episode) if episode else {}
                        duration_val = _resolve_shot_video_duration_value(
                            shot_duration=shot.duration,
                            sd2_auto_duration=bool((batch_status or {}).get("sd2_auto_duration")),
                            system_api_id=system_api_id,
                            db=db,
                        )

                        multi_prompt_payload = None
                        if video_prompt_cn:
                            multi_prompt_payload = [
                                {"prompt": video_prompt, "type": "en"},
                                {"prompt": video_prompt_cn, "type": "zh"}
                            ]
                        video_req = VideoGenerationRequest(
                            draft_mode=bool((batch_status or {}).get("draft_mode")),
                            prompt=video_prompt,
                            multi_prompt=multi_prompt_payload,
                            ref_image_url=normalized_refs,
                            last_frame_url=None,
                            ref_mode=video_mode,
                            keyframes=None,
                            duration=duration_val,
                            project_id=episode.project_id,
                            episode_id=int(episode_id),
                            shot_id=shot.id,
                            shot_number=shot.shot_id,
                            shot_name=shot.shot_name,
                            asset_type="video",
                            system_api_id=system_api_id,
                            use_prev_video=use_prev_video,
                        )
                        _release_db_connection(db, "shot_media_batch_video")
                        try:
                            callback_ticket_val = f"video-shot-{shot.id}"
                            callback_url_val = str(media_service._resolve_provider_callback_url({}, callback_ticket_val) or "").strip()
                        except Exception:
                            callback_ticket_val = f"video-shot-{shot.id}"
                            callback_url_val = ""

                        asyncio.run(_run_stage_with_retry(
                            lambda: _run_generate_video(
                                req=video_req,
                                current_user=user_principal,
                                db=db,
                                provider_callback_ticket=callback_ticket_val,
                                provider_callback_url=callback_url_val
                            ),
                            "video",
                            shot_label,
                        ))

                success += 1
                _log_batch_sys_event(
                    kind="shot-media-batch",
                    phase="item",
                    user_id=user_id,
                    user_name=user_name,
                    project_id=project_id,
                    episode_id=episode_id,
                    job_id=job_id,
                    item_id=int(shot.id),
                    item_label=shot_label,
                    result="success",
                    message="Shot media generated",
                    extra={"mode": mode},
                )
            except _BatchStopRequested:
                _persist_stopped_status()
                return
            except Exception as e:
                try:
                    db.rollback()
                except Exception:
                    pass
                shot_ok = False
                failed += 1
                errors.append(f"{shot_label}: {str(e)}")
                _log_batch_sys_event(
                    kind="shot-media-batch",
                    phase="item",
                    user_id=user_id,
                    user_name=user_name,
                    project_id=project_id,
                    episode_id=episode_id,
                    job_id=job_id,
                    item_id=int(shot.id),
                    item_label=shot_label,
                    result="failed",
                    message=str(e),
                    extra={"mode": mode},
                )

            completed += 1
            episode = _read_latest_episode()
            if not episode:
                break
            latest = _read_shot_media_batch_status(episode)
            latest["completed"] = completed
            latest["success"] = success
            latest["failed"] = failed
            latest["errors"] = errors
            latest["current_asset_type"] = None
            latest["current_asset_label"] = ""
            latest["updated_at"] = now_bj_iso()
            latest["message"] = (
                f"Progress {completed}/{total}" if shot_ok else f"Progress {completed}/{total} (with errors)"
            )
            _persist_shot_media_batch_status(db, episode, latest)
            _release_db_connection(db, "shot_media_batch_progress")

        episode = _read_latest_episode()
        if episode:
            final_status = _read_shot_media_batch_status(episode)
            final_status["running"] = False
            final_status["completed"] = completed
            final_status["success"] = success
            final_status["failed"] = failed
            final_status["errors"] = errors
            final_status["current_asset_type"] = None
            final_status["current_asset_label"] = ""
            final_status["updated_at"] = now_bj_iso()
            final_status["finished_at"] = final_status["updated_at"]
            final_status["message"] = f"Batch done: success {success}, failed {failed}"
            _persist_shot_media_batch_status(db, episode, final_status)
            _log_batch_sys_event(
                kind="shot-media-batch",
                phase="end",
                user_id=user_id,
                user_name=user_name,
                project_id=project_id,
                episode_id=episode_id,
                job_id=job_id,
                result="completed",
                message=final_status.get("message"),
                extra={"completed": completed, "success": success, "failed": failed, "mode": mode},
            )
            _release_db_connection(db, "shot_media_batch_final")
    except Exception as e:
        try:
            db.expire_all()
            episode = (
                db.query(Episode)
                .execution_options(populate_existing=True)
                .filter(Episode.id == episode_id)
                .first()
            )
            if episode:
                status_payload = _read_shot_media_batch_status(episode)
                status_payload["running"] = False
                status_payload["updated_at"] = now_bj_iso()
                status_payload["finished_at"] = status_payload["updated_at"]
                status_payload["message"] = f"Batch failed: {str(e)}"
                status_payload["current_asset_type"] = None
                status_payload["current_asset_label"] = ""
                status_payload["errors"] = list(status_payload.get("errors") or []) + [str(e)]
                _persist_shot_media_batch_status(db, episode, status_payload)
                _log_batch_sys_event(
                    kind="shot-media-batch",
                    phase="end",
                    user_id=user_id,
                    user_name=str((user.username if 'user' in locals() and user else "") or f"user_{user_id}"),
                    project_id=int(episode.project_id),
                    episode_id=episode_id,
                    job_id=f"shot-media-batch:{int(episode_id)}",
                    result="failed",
                    message=str(e),
                )
                _release_db_connection(db, "shot_media_batch_error")
        except Exception:
            pass
    finally:
        _clear_episode_worker(SHOT_MEDIA_BATCH_THREADS, SHOT_MEDIA_BATCH_THREADS_LOCK, int(episode_id))
        _clear_shot_media_batch_cancel_event(int(episode_id))
        db.close()

# --- batch-media (moved from endpoints) ---
