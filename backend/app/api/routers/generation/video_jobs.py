# -*- coding: utf-8 -*-
"""Generation section routes — symbols pulled from shared module."""
from __future__ import annotations

from app.api.routers.generation import shared as _shared

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


@router.post("/generate/video")
async def generate_video_endpoint(
    req: VideoGenerationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    dedup_key = _build_video_dedup_key(req, current_user.id)
    created_task = False

    async with _VIDEO_DEDUP_LOCK:
        now_ts = time.time()
        _cleanup_video_dedup_cache(now_ts)

        recent = _VIDEO_RECENT_RESULTS_BY_KEY.get(dedup_key)
        if isinstance(recent, dict) and (now_ts - float(recent.get("ts") or 0.0)) <= _VIDEO_DEDUP_WINDOW_SECONDS:
            logger.info(
                "[GenerateVideo] dedup recent-hit | user_id=%s shot_id=%s key=%s age_ms=%s",
                current_user.id,
                req.shot_id,
                dedup_key[:12],
                int((now_ts - float(recent.get("ts") or 0.0)) * 1000),
            )
            return recent.get("result")

        existing_task = _VIDEO_INFLIGHT_BY_KEY.get(dedup_key)
        if existing_task is None:
            _enforce_user_media_generation_parallel_limit(current_user)
            _release_db_connection(db, "generate_video_sync_wait")
            try:
                callback_ticket_val = f"video-shot-{req.shot_id}" if getattr(req, "shot_id", None) else None
                callback_url_val = str(media_service._resolve_provider_callback_url({}, callback_ticket_val) or "").strip() if callback_ticket_val else ""
            except Exception:
                callback_ticket_val = f"video-shot-{req.shot_id}" if getattr(req, "shot_id", None) else None
                callback_url_val = ""
            
            existing_task = asyncio.create_task(_run_generate_video(
                req,
                current_user,
                db,
                provider_callback_ticket=callback_ticket_val,
                provider_callback_url=callback_url_val
            ))
            _VIDEO_INFLIGHT_BY_KEY[dedup_key] = existing_task
            created_task = True
        else:
            logger.info(
                "[GenerateVideo] dedup inflight-hit | user_id=%s shot_id=%s key=%s",
                current_user.id,
                req.shot_id,
                dedup_key[:12],
            )

    try:
        _release_db_connection(db, "generate_video_sync_wait_existing")
        result = await existing_task
    finally:
        if created_task:
            async with _VIDEO_DEDUP_LOCK:
                if _VIDEO_INFLIGHT_BY_KEY.get(dedup_key) is existing_task:
                    _VIDEO_INFLIGHT_BY_KEY.pop(dedup_key, None)

    if created_task:
        async with _VIDEO_DEDUP_LOCK:
            _VIDEO_RECENT_RESULTS_BY_KEY[dedup_key] = {
                "ts": time.time(),
                "result": result,
            }

    return result


@router.post("/generate/voice")
async def generate_voice_endpoint(
    req: VoiceGenerationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return await _run_generate_voice(req, current_user, db)


from app.services.generation_runtime.voice_generation_runner import (  # noqa: E402,F401
    _run_generate_voice,
)




from app.services.generation_runtime.video_generation_runner import (  # noqa: E402,F401
    _run_generate_video,
)

@router.post("/generate/callback/{ticket}")
async def receive_generation_callback(ticket: str, request: Request, response: Response):
    stable_ticket = str(ticket or "").strip()
    if not stable_ticket:
        raise HTTPException(status_code=400, detail="Invalid callback ticket")
    _apply_no_store_headers(response)

    try:
        payload = await request.json()
        if not isinstance(payload, dict):
            payload = {"raw": payload}
    except Exception:
        body_bytes = await request.body()
        payload = {
            "raw": body_bytes.decode("utf-8", errors="ignore") if body_bytes else "",
            "content_type": str(request.headers.get("content-type") or "").strip(),
        }

    import json
    try:
        def _log_chunked_message(prefix: str, text: str, chunk_size: int = 4000) -> None:
            stable_text = str(text or "")
            if not stable_text:
                logger.info("%s <empty>", prefix)
                return
            safe_chunk_size = max(512, int(chunk_size or 4000))
            total_len = len(stable_text)
            total_parts = (total_len + safe_chunk_size - 1) // safe_chunk_size
            for idx in range(total_parts):
                start = idx * safe_chunk_size
                end = min(total_len, (idx + 1) * safe_chunk_size)
                logger.info(
                    "%s part=%s/%s chars=%s-%s %s",
                    prefix,
                    idx + 1,
                    total_parts,
                    start + 1,
                    end,
                    stable_text[start:end],
                )

        dump_str = json.dumps(payload, ensure_ascii=False)
        client_host = getattr(getattr(request, "client", None), "host", "Unknown")
        callback_headers = {
            key: value
            for key, value in request.headers.items()
            if str(key or "").lower() in {
                "content-type",
                "content-length",
                "x-kie-signature",
                "x-kie-timestamp",
                "x-signature",
                "x-timestamp",
                "x-forwarded-for",
                "user-agent",
            }
        }
        body_bytes = await request.body()

        logger.info("=" * 60)
        logger.info("🔔 [WEBHOOK CALLBACK RECEIVED] [%s] Ticket: %s", client_host, stable_ticket)
        logger.info(
            "🔔 [WEBHOOK META] content_type=%s content_length=%s body_bytes=%s top_keys=%s",
            str(request.headers.get("content-type") or "").strip() or None,
            str(request.headers.get("content-length") or "").strip() or None,
            len(body_bytes or b""),
            list(payload.keys()) if isinstance(payload, dict) else None,
        )
        logger.info("🔔 [WEBHOOK HEADERS] %s", json.dumps(callback_headers, ensure_ascii=False))
        _log_chunked_message("🔔 [WEBHOOK PAYLOAD FULL]", dump_str)
        logger.info("=" * 60)
    except Exception as e:
        logger.error(f"Failed to log webhook payload: {e}")

    try:
        _verify_kie_webhook_request(request, payload if isinstance(payload, dict) else {})
        logger.info("[WebhookVerify] accepted | ticket=%s", stable_ticket)
    except HTTPException as verify_exc:
        logger.warning(
            "[WebhookVerify] rejected | ticket=%s detail=%s has_timestamp=%s has_signature=%s",
            stable_ticket,
            getattr(verify_exc, "detail", None),
            bool(
                str(request.headers.get("x-webhook-timestamp") or "").strip()
                or str(request.headers.get("x-kie-timestamp") or "").strip()
                or str(request.headers.get("x-timestamp") or "").strip()
            ),
            bool(
                str(request.headers.get("x-webhook-signature") or "").strip()
                or str(request.headers.get("x-kie-signature") or "").strip()
                or str(request.headers.get("x-signature") or "").strip()
            ),
        )
        raise

    await asyncio.to_thread(_set_generation_callback_payload, stable_ticket, payload)
    normalized_payload = _get_generation_callback_payload(stable_ticket)
    payload_status = _normalize_generation_status(normalized_payload.get("status"))
    payload_result_url = _extract_job_result_url(normalized_payload)
    callback_task_id = _extract_callback_task_id(normalized_payload)
    logger.info(
        "[GenerationCallback] received ticket=%s task_id=%s status=%s has_result_url=%s result_url=%s remote=%s",
        stable_ticket,
        callback_task_id or None,
        payload_status or None,
        bool(payload_result_url),
        payload_result_url or None,
        getattr(getattr(request, "client", None), "host", None),
    )
    # Progress-only callbacks (running/queued/...) have nothing to finalize and must not
    # hold the per-ticket inflight lock — otherwise a later succeeded callback can be
    # ACK'd, stored, then never finalized (or overwritten by the stale running snapshot).
    is_progress_only = payload_status == "running" and not payload_result_url
    if is_progress_only:
        logger.info(
            "[GenerationCallback] intermediate status stored without finalize | ticket=%s status=%s task_id=%s",
            stable_ticket,
            payload_status or None,
            callback_task_id or None,
        )
        return {"ok": True, "ticket": stable_ticket, "accepted": True}

    if _mark_generation_callback_inflight(stable_ticket):
        asyncio.create_task(_process_generation_callback_async(stable_ticket, payload if isinstance(payload, dict) else {}))
    else:
        _mark_generation_callback_reprocess(stable_ticket)
        logger.info(
            "[GenerationCallback] duplicate callback queued for reprocess while finalize in-flight | ticket=%s status=%s",
            stable_ticket,
            payload_status or None,
        )
    return {"ok": True, "ticket": stable_ticket, "accepted": True}


@router.get("/generate/callback/{ticket}")
def get_generation_callback_result(ticket: str, response: Response):
    stable_ticket = str(ticket or "").strip()
    if not stable_ticket:
        raise HTTPException(status_code=400, detail="Invalid callback ticket")
    _apply_no_store_headers(response)

    with GENERATION_CALLBACK_LOCK:
        _prune_generation_callback_locked()
        payload = dict(GENERATION_CALLBACK_STORE.get(stable_ticket) or {})

    if not payload:
        file_payload = _read_generation_callback_file(stable_ticket)
        if file_payload:
            payload = dict(file_payload)
            with GENERATION_CALLBACK_LOCK:
                _prune_generation_callback_locked()
                GENERATION_CALLBACK_STORE[stable_ticket] = dict(file_payload)

    if not payload:
        return {
            "ticket": stable_ticket,
            "status": "pending",
            "received": False,
            "received_at": None,
            "payload": None,
        }

    return {
        "ticket": stable_ticket,
        "status": "received",
        "received": True,
        "received_at": payload.get("received_at"),
        "payload": payload.get("payload") if isinstance(payload.get("payload"), dict) else {},
    }


@router.post("/generate/video/submit")
async def submit_generate_video_endpoint(
    req: VideoGenerationRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    callback_url = _resolve_callback_url_from_payload(req)
    explicit_idempotency_key = str(request.headers.get("X-Idempotency-Key") or "").strip()
    req_payload = req.model_dump()

    # Keep queue payload prompt/refs aligned with runtime mapping logic.
    try:
        req_payload = _preprocess_video_submit_payload(
            db,
            req_payload,
            provider=str(req_payload.get("provider") or "").strip(),
            model=str(req_payload.get("model") or "").strip(),
        )
    except Exception as e:
        logger.warning("[VideoSubmit] prompt mapping pre-process skipped: %s", e)
    scope_key = _build_generation_task_scope("video", current_user.id, req_payload)
    fingerprint_token = _build_submit_idempotency_token("video", current_user.id, req_payload)
    idempotency_key = explicit_idempotency_key or fingerprint_token
    job_id = ""
    now = now_bj_iso()
    provider_callback_ticket = ""
    provider_callback_url = ""

    store_keys: List[str] = []
    if idempotency_key:
        store_keys.append(_build_video_idempotency_store_key(current_user.id, idempotency_key))
    store_keys.append(_build_video_idempotency_store_key(current_user.id, fingerprint_token))
    store_keys = list(dict.fromkeys([k for k in store_keys if str(k or "").strip()]))

    def _video_dedup_response_locked() -> Optional[Dict[str, Any]]:
        active_scope_job_id = str(VIDEO_ACTIVE_SCOPE_STORE.get(scope_key) or "").strip()
        if active_scope_job_id:
            active_scope_job = dict(VIDEO_JOB_STORE.get(active_scope_job_id) or {})
            active_status = str(active_scope_job.get("status") or "").strip().lower()
            if active_scope_job and active_status in {"queued", "running"}:
                logger.info(
                    "[VideoSubmit] scope deduplicated | user_id=%s scope=%s job_id=%s status=%s",
                    current_user.id,
                    scope_key,
                    active_scope_job_id,
                    active_status,
                )
                return {
                    "job_id": active_scope_job_id,
                    "status": active_scope_job.get("status") or "queued",
                    "created_at": active_scope_job.get("created_at") or now_bj_iso(),
                    "deduplicated": True,
                    "scope_deduplicated": True,
                }
            VIDEO_ACTIVE_SCOPE_STORE.pop(scope_key, None)

        for store_key in store_keys:
            mapped = VIDEO_SUBMIT_IDEMPOTENCY_STORE.get(store_key) or {}
            existing_job_id = str(mapped.get("job_id") or "").strip()
            if not existing_job_id:
                continue
            existing_job = dict(VIDEO_JOB_STORE.get(existing_job_id) or {})
            existing_status = str(existing_job.get("status") or "").strip().lower()
            if existing_job and existing_status in {"queued", "running"}:
                logger.info(
                    "[VideoSubmit] deduplicated | user_id=%s key=%s job_id=%s status=%s",
                    current_user.id,
                    store_key,
                    existing_job_id,
                    existing_job.get("status"),
                )
                return {
                    "job_id": existing_job_id,
                    "status": existing_job.get("status") or "queued",
                    "created_at": existing_job.get("created_at") or now_bj_iso(),
                    "deduplicated": True,
                }
        return None

    with VIDEO_JOB_LOCK:
        _prune_video_jobs_locked()
        deduped = _video_dedup_response_locked()
        if deduped is not None:
            return deduped

    parallel_limit = _enforce_user_media_generation_parallel_limit(current_user)

    with VIDEO_JOB_LOCK:
        deduped = _video_dedup_response_locked()
        if deduped is not None:
            return deduped
        job_id = uuid.uuid4().hex
        for store_key in store_keys:
            VIDEO_SUBMIT_IDEMPOTENCY_STORE[store_key] = {
                "job_id": job_id,
                "created_at": now,
            }
        VIDEO_ACTIVE_SCOPE_STORE[scope_key] = job_id

    if not job_id:
        job_id = uuid.uuid4().hex

    provider_callback_ticket = f"video-job-{job_id}"
    try:
        provider_callback_url = str(media_service._resolve_provider_callback_url({}, provider_callback_ticket) or "").strip()
    except Exception:
        provider_callback_url = ""

    _set_video_job(
        job_id,
        status="queued",
        user_id=current_user.id,
        username=current_user.username,
        callback_url=callback_url,
        task_scope=scope_key,
        project_id=req_payload.get("project_id"),
        episode_id=req_payload.get("episode_id"),
        scene_id=req_payload.get("scene_id"),
        shot_id=req_payload.get("shot_id"),
        shot_number=req_payload.get("shot_number"),
        shot_name=req_payload.get("shot_name"),
        asset_type=req_payload.get("asset_type"),
        provider=req_payload.get("provider"),
        model=req_payload.get("model"),
        prompt=req_payload.get("prompt"),
        duration=req_payload.get("duration"),
        aspect_ratio=req_payload.get("aspect_ratio"),
        provider_callback_ticket=provider_callback_ticket,
        created_at=now,
        started_at=None,
        finished_at=None,
        result=None,
        error=None,
    )

    video_task = _submit_generation_background_task(
        job_id=job_id,
        kind="video",
        user_id=int(current_user.id),
        payload=req_payload,
    )
    with VIDEO_JOB_LOCK:
        VIDEO_JOB_TASKS[job_id] = video_task
    _release_media_generation_job_after_limit_race(
        kind="video",
        job_id=job_id,
        user=current_user,
        limit=parallel_limit,
    )
    return {"job_id": job_id, "status": "queued", "created_at": now}


@router.get("/generate/video/jobs/{job_id}")
def get_generate_video_job_status(
    job_id: str,
    response: Response,
    current_claims: Dict[str, Any] = Depends(get_current_claims),
):
    _apply_no_store_headers(response)
    with VIDEO_JOB_LOCK:
        job = dict(VIDEO_JOB_STORE.get(job_id) or {})

    status = str(job.get("status") or "").strip().lower()
    if not job or status in {"queued", "running"}:
        file_job = _read_video_job_file(job_id)
        if file_job:
            file_status = str(file_job.get("status") or "").strip().lower()
            if not job or file_status != status or ("result" in file_job and "result" not in job):
                with VIDEO_JOB_LOCK:
                    _prune_video_jobs_locked()
                    VIDEO_JOB_STORE[job_id] = dict(file_job)
                job = dict(file_job)
                logger.info(
                    "[VideoJob] synced from shared file store | job_id=%s status=%s user_id=%s",
                    job_id,
                    job.get("status"),
                    job.get("user_id"),
                )

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job = _hydrate_video_job_record(job_id, job)

    if "result" in job:
        compact_result = _compact_job_result(job.get("result"))
        if compact_result != job.get("result"):
            _set_video_job(job_id, result=compact_result)
            job["result"] = compact_result

    job = _maybe_finalize_video_job_from_provider_callback(job_id, job)
    job = _maybe_retry_video_job_result_persistence(job_id, job)
    owner_id = job.get("user_id")
    owner_username = str(job.get("username") or "").strip()
    owner_username_norm = owner_username.lower()

    job = _maybe_finalize_stuck_job(
        kind="video",
        job_id=job_id,
        job=job,
        set_job_func=_set_video_job,
        task_store=VIDEO_JOB_TASKS,
        lock=VIDEO_JOB_LOCK,
        timeout_seconds=VIDEO_JOB_MAX_RUNNING_SECONDS,
    )
    video_status = str(job.get("status") or "").strip().lower()

    current_user_id = current_claims.get("user_id")
    current_username = str(current_claims.get("username") or "").strip()
    current_username_norm = current_username.lower()
    is_superuser = bool(current_claims.get("is_superuser"))

    try:
        safe_cid = int(current_user_id) if current_user_id is not None else -1
        safe_oid = int(owner_id) if owner_id is not None else -2
    except:
        safe_cid = -1
        safe_oid = -2
    
    is_owner = (
        (safe_cid == safe_oid and safe_oid > 0)
        or (owner_username_norm and owner_username_norm == current_username_norm)
    )
    if not is_superuser and not is_owner:
        pass

    result_url = _extract_job_result_url(job.get("result"))
    if result_url and video_status in {"queued", "running"}:
        logger.warning(
            "[VideoJob] polling anomaly | job_id=%s status=%s result_url=%s user_id=%s",
            job_id,
            video_status,
            result_url,
            owner_id,
        )

    return {
        "job_id": job.get("job_id"),
        "status": job.get("status"),
        "created_at": job.get("created_at"),
        "started_at": job.get("started_at"),
        "finished_at": job.get("finished_at"),
        "error": job.get("error"),
        "result": job.get("result"),
    }


class VideoJobProviderTaskQueryRequest(BaseModel):
    apply_recovery: bool = False


@router.post("/generate/video/jobs/{job_id}/query-provider-task")
def query_video_job_provider_task(
    job_id: str,
    response: Response,
    req: Optional[VideoJobProviderTaskQueryRequest] = None,
    current_claims: Dict[str, Any] = Depends(get_current_claims),
):
    """Query upstream provider task API for a video job.

    When apply_recovery=true and the provider task already succeeded, reuse the
    timeout-poll recovery path to download the file and persist to OSS / bind shot.
    """
    _apply_no_store_headers(response)
    apply_recovery = bool(getattr(req, "apply_recovery", False)) if req is not None else False
    stable_job_id = str(job_id or "").strip()
    if not stable_job_id:
        raise HTTPException(status_code=400, detail="job_id is required")

    with VIDEO_JOB_LOCK:
        job = dict(VIDEO_JOB_STORE.get(stable_job_id) or {})
    if not job:
        file_job = _read_video_job_file(stable_job_id)
        if file_job:
            job = dict(file_job)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job = _hydrate_video_job_record(stable_job_id, job)

    owner_id = job.get("user_id")
    owner_username = str(job.get("username") or "").strip().lower()
    current_user_id = current_claims.get("user_id")
    current_username = str(current_claims.get("username") or "").strip().lower()
    is_superuser = bool(current_claims.get("is_superuser"))
    try:
        safe_cid = int(current_user_id) if current_user_id is not None else -1
        safe_oid = int(owner_id) if owner_id is not None else -2
    except Exception:
        safe_cid = -1
        safe_oid = -2
    is_owner = (safe_cid == safe_oid and safe_oid > 0) or (owner_username and owner_username == current_username)
    if not is_superuser and not is_owner:
        raise HTTPException(status_code=403, detail="Not allowed to query this job")

    from app.services.generation_runtime.callbacks import _extract_job_provider_task_id
    from app.services.generation_runtime.job_store import _extract_job_result_url
    from app.services.generation_runtime.timeout_poll_recovery import (
        _apply_poll_success,
        _hydrate_job,
        _resolve_poll_credentials,
    )
    from app.services.media_service import media_service

    provider_task_id = _extract_job_provider_task_id(job)
    if not provider_task_id:
        raise HTTPException(
            status_code=400,
            detail="provider_task_id not available yet for this job",
        )

    api_key, query_endpoint, provider, base_url = _resolve_poll_credentials(job)
    if not api_key:
        raise HTTPException(status_code=400, detail=f"No api_key found for provider {provider or '-'}")

    # Usage + full raw payload for admin/debug display.
    fetched = media_service.fetch_provider_task_usage(
        task_id=provider_task_id,
        api_key=api_key,
        query_endpoint=query_endpoint or None,
        provider=provider or None,
        refresh_if_missing=True,
        include_raw_response=True,
    )
    raw_response = fetched.get("raw_response") if isinstance(fetched, dict) else None
    usage = {
        k: v
        for k, v in (fetched.items() if isinstance(fetched, dict) else [])
        if k != "raw_response"
    }

    # Result URL / status for download+OSS recovery (same path as timeout poll).
    poll_result = media_service.fetch_provider_task_result(
        task_id=provider_task_id,
        api_key=api_key,
        query_endpoint=query_endpoint or None,
        provider=provider or None,
        kind="video",
        base_url=base_url or None,
    )
    if not isinstance(poll_result, dict):
        poll_result = {}
    if not (isinstance(raw_response, dict) and raw_response) and isinstance(poll_result.get("raw"), dict):
        raw_response = poll_result.get("raw")

    if not usage and not (isinstance(raw_response, dict) and raw_response) and not poll_result.get("url"):
        raise HTTPException(status_code=404, detail="No response from provider task query")

    provider_status = str(poll_result.get("status") or "").strip() or None
    if not provider_status and isinstance(raw_response, dict):
        data_obj = raw_response.get("data") if isinstance(raw_response.get("data"), dict) else {}
        provider_status = (
            raw_response.get("status")
            or raw_response.get("state")
            or data_obj.get("state")
            or data_obj.get("status")
        )
    provider_status_l = str(provider_status or "").strip().lower()
    result_url = str(poll_result.get("url") or "").strip()
    existing_result_url = str(_extract_job_result_url(job.get("result")) or "").strip()
    can_recover = bool(
        result_url
        and provider_status_l in {
            "succeeded",
            "success",
            "completed",
            "done",
            "finish",
            "finished",
            "complete",
        }
    )

    recovery_applied = False
    recovery_skipped_reason = None
    if can_recover and apply_recovery:
        # Reuse timeout-poll success path: download remote file → OSS → bind shot.
        try:
            recovery_applied = bool(_apply_poll_success("video", stable_job_id, job, poll_result))
            if not recovery_applied:
                recovery_skipped_reason = "recovery_apply_returned_false"
        except Exception as exc:
            logger.exception(
                "[VideoJob] query-provider-task recovery failed | job_id=%s task_id=%s error=%s",
                stable_job_id,
                provider_task_id,
                exc,
            )
            recovery_skipped_reason = str(exc)
    elif can_recover and not apply_recovery:
        recovery_skipped_reason = "awaiting_client_confirm"
    elif provider_status_l in {"failed", "error", "canceled", "cancelled"}:
        recovery_skipped_reason = f"provider_terminal_{provider_status_l}"
    elif not result_url:
        recovery_skipped_reason = "no_result_url"
    else:
        recovery_skipped_reason = "provider_not_succeeded"

    live = _hydrate_job("video", stable_job_id) or job
    live_result_url = str(_extract_job_result_url(live.get("result")) or existing_result_url or result_url or "").strip() or None

    return {
        "ok": True,
        "job_id": stable_job_id,
        "job_status": live.get("status") or job.get("status"),
        "provider": provider or job.get("provider"),
        "provider_task_id": provider_task_id,
        "query_endpoint": query_endpoint or None,
        "provider_status": provider_status,
        "result_url": live_result_url,
        "can_recover": can_recover,
        "recovery_applied": recovery_applied,
        "recovery_skipped_reason": recovery_skipped_reason,
        "usage": usage or None,
        "raw_response": raw_response if isinstance(raw_response, dict) else None,
    }

