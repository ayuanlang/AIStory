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


def _extract_video_job_shot_id(job: Optional[Dict[str, Any]]) -> str:
    if not isinstance(job, dict):
        return ""
    metadata = job.get("metadata") if isinstance(job.get("metadata"), dict) else {}
    payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
    context = job.get("context") if isinstance(job.get("context"), dict) else {}
    request = job.get("request") if isinstance(job.get("request"), dict) else {}
    result = job.get("result") if isinstance(job.get("result"), dict) else {}
    result_meta = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
    return str(
        job.get("shot_id")
        or job.get("ownerShotId")
        or metadata.get("shot_id")
        or metadata.get("ownerShotId")
        or payload.get("shot_id")
        or payload.get("ownerShotId")
        or context.get("shot_id")
        or context.get("ownerShotId")
        or request.get("shot_id")
        or result_meta.get("shot_id")
        or ""
    ).strip()


def _video_job_recency_ts(job: Optional[Dict[str, Any]]) -> float:
    if not isinstance(job, dict):
        return 0.0
    for key in ("finished_at", "started_at", "created_at", "updated_at"):
        raw = job.get(key)
        if raw in (None, ""):
            continue
        try:
            if isinstance(raw, (int, float)):
                return float(raw)
            text = str(raw).strip()
            if not text:
                continue
            # Accept unix seconds / ms and ISO timestamps.
            if text.replace(".", "", 1).isdigit():
                value = float(text)
                return value / 1000.0 if value > 1e12 else value
            return datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()
        except Exception:
            continue
    return 0.0


def _collect_video_jobs_for_shot(shot_id: str) -> List[Dict[str, Any]]:
    safe_shot_id = str(shot_id or "").strip()
    if not safe_shot_id:
        return []

    from app.services.generation_runtime.job_store import VIDEO_JOB_FILE_DIR, _read_video_job_file
    from app.services.generation_task_queue import (
        find_generation_job_states_by_shot_id,
        find_generation_tasks_by_shot_id,
    )

    by_id: Dict[str, Dict[str, Any]] = {}

    def _consider(
        raw_job: Optional[Dict[str, Any]],
        fallback_job_id: str = "",
        *,
        source: str = "",
        prefiltered: bool = False,
    ) -> None:
        if not isinstance(raw_job, dict):
            return
        job = dict(raw_job)
        job_id = str(job.get("job_id") or fallback_job_id or "").strip()
        if not job_id:
            return
        extracted_shot = _extract_video_job_shot_id(job)
        if extracted_shot:
            if extracted_shot != safe_shot_id:
                return
        elif not prefiltered:
            return
        else:
            job["shot_id"] = job.get("shot_id") or safe_shot_id
        job["job_id"] = job_id
        if source and not job.get("_lookup_source"):
            job["_lookup_source"] = source
        prev = by_id.get(job_id)
        if not prev or _video_job_recency_ts(job) >= _video_job_recency_ts(prev):
            by_id[job_id] = job

    with VIDEO_JOB_LOCK:
        for job_id, payload in list(VIDEO_JOB_STORE.items()):
            _consider(payload, str(job_id), source="memory")

    try:
        if os.path.isdir(VIDEO_JOB_FILE_DIR):
            for name in os.listdir(VIDEO_JOB_FILE_DIR):
                if not str(name).endswith(".json"):
                    continue
                job_id = str(name)[:-5].strip()
                if not job_id:
                    continue
                _consider(_read_video_job_file(job_id), job_id, source="file")
    except Exception:
        logger.exception("[VideoJob] scan job files for shot failed | shot_id=%s", safe_shot_id)

    try:
        for state in find_generation_job_states_by_shot_id(kind="video", shot_id=safe_shot_id, limit=50):
            _consider(state, str((state or {}).get("job_id") or ""), source="job_state", prefiltered=True)
    except Exception:
        logger.exception("[VideoJob] scan job_state for shot failed | shot_id=%s", safe_shot_id)

    try:
        for task in find_generation_tasks_by_shot_id(kind="video", shot_id=safe_shot_id, limit=50):
            payload = task.get("payload") if isinstance(task.get("payload"), dict) else {}
            job = dict(payload) if isinstance(payload, dict) else {}
            job_id = str(task.get("job_id") or job.get("job_id") or "").strip()
            if not job_id:
                continue
            job["job_id"] = job_id
            if job.get("user_id") in (None, "") and task.get("user_id") not in (None, ""):
                job["user_id"] = task.get("user_id")
            if task.get("status") not in (None, ""):
                # Prefer queue terminal status when reconstructing from queue-only rows.
                if job.get("status") in (None, "") or str(task.get("status") or "").lower() in {
                    "failed", "error", "canceled", "cancelled", "succeeded", "completed",
                }:
                    job["status"] = task.get("status")
            for ts_key in ("created_at", "started_at", "finished_at"):
                if job.get(ts_key) in (None, "") and task.get(ts_key) not in (None, ""):
                    job[ts_key] = task.get(ts_key)
            if task.get("error") not in (None, "") and job.get("error") in (None, ""):
                job["error"] = task.get("error")
            _consider(job, job_id, source="task_queue", prefiltered=True)
    except Exception:
        logger.exception("[VideoJob] scan task_queue for shot failed | shot_id=%s", safe_shot_id)

    jobs = list(by_id.values())
    jobs.sort(key=_video_job_recency_ts, reverse=True)
    return jobs


def _load_video_job_for_query(job_id: str) -> Dict[str, Any]:
    """Load video job from memory/file/job_state/task queue for provider-task query."""
    stable_job_id = str(job_id or "").strip()
    if not stable_job_id:
        return {}

    with VIDEO_JOB_LOCK:
        job = dict(VIDEO_JOB_STORE.get(stable_job_id) or {})
    if not job:
        file_job = _read_video_job_file(stable_job_id)
        if file_job:
            job = dict(file_job)

    if not job:
        try:
            from app.services.generation_task_queue import get_generation_task_status

            task_row = get_generation_task_status(stable_job_id) or {}
            payload = {}
            raw_json = task_row.get("payload_json")
            if isinstance(raw_json, str) and raw_json.strip():
                try:
                    parsed = json.loads(raw_json)
                    if isinstance(parsed, dict):
                        payload = parsed
                except Exception:
                    payload = {}
            elif isinstance(task_row.get("payload"), dict):
                payload = dict(task_row.get("payload") or {})
            if payload or task_row:
                job = dict(payload)
                job["job_id"] = stable_job_id
                if job.get("user_id") in (None, "") and task_row.get("user_id") not in (None, ""):
                    job["user_id"] = task_row.get("user_id")
                if task_row.get("status") not in (None, ""):
                    job["status"] = task_row.get("status")
                for ts_key in ("created_at", "started_at", "finished_at"):
                    if job.get(ts_key) in (None, "") and task_row.get(ts_key) not in (None, ""):
                        job[ts_key] = task_row.get(ts_key)
                if task_row.get("error") not in (None, "") and job.get("error") in (None, ""):
                    job["error"] = task_row.get("error")
        except Exception:
            logger.exception("[VideoJob] reconstruct from task queue failed | job_id=%s", stable_job_id)

    if job:
        job = _hydrate_video_job_record(stable_job_id, job)
    return job if isinstance(job, dict) else {}


def _parse_json_object(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return dict(parsed) if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _extract_provider_task_id_from_mapping(payload: Optional[Dict[str, Any]]) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("provider_task_id", "task_id", "taskId"):
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    billing = payload.get("billing_context") if isinstance(payload.get("billing_context"), dict) else {}
    for key in ("provider_task_id", "task_id", "taskId"):
        value = str(billing.get(key) or "").strip()
        if value:
            return value
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    for key in ("provider_task_id", "task_id", "taskId"):
        value = str(result.get(key) or "").strip()
        if value:
            return value
    meta = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
    for key in ("provider_task_id", "task_id", "taskId"):
        value = str(meta.get(key) or "").strip()
        if value:
            return value
    # NukoAi / poll adapters may only persist task id under provider payload snapshots.
    for nested_key in ("final_provider_payload", "combined_payload", "provider_payload", "submit_raw"):
        nested = payload.get(nested_key)
        if not isinstance(nested, dict):
            continue
        for key in ("provider_task_id", "task_id", "taskId", "id"):
            value = str(nested.get(key) or "").strip()
            if value:
                return value
        data = nested.get("data") if isinstance(nested.get("data"), dict) else {}
        for key in ("provider_task_id", "task_id", "taskId", "id"):
            value = str(data.get(key) or "").strip()
            if value:
                return value
        submit_raw = nested.get("submit_raw") if isinstance(nested.get("submit_raw"), dict) else {}
        submit_data = submit_raw.get("data") if isinstance(submit_raw.get("data"), dict) else {}
        for key in ("provider_task_id", "task_id", "taskId", "id"):
            value = str(submit_data.get(key) or submit_raw.get(key) or "").strip()
            if value:
                return value
    return ""


def _resolve_shot_pk_candidates(db: Session, shot_id: str) -> List[str]:
    safe_shot_id = str(shot_id or "").strip()
    if not safe_shot_id:
        return []
    candidates: List[str] = [safe_shot_id]
    shot = None
    try:
        shot_pk = int(safe_shot_id)
        shot = db.query(models.Shot).filter(models.Shot.id == shot_pk).first()
        candidates.append(str(shot_pk))
    except Exception:
        shot = None
    if shot is None:
        shot = (
            db.query(models.Shot)
            .filter(models.Shot.shot_id == safe_shot_id)
            .order_by(models.Shot.id.desc())
            .first()
        )
    if shot is not None and getattr(shot, "id", None) is not None:
        candidates.append(str(int(shot.id)))
    # Preserve order, unique.
    out: List[str] = []
    seen = set()
    for item in candidates:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _find_latest_video_provider_task_from_audit(
    db: Session,
    shot_id: str,
    *,
    current_user_id: Optional[int] = None,
    is_superuser: bool = False,
) -> Optional[Dict[str, Any]]:
    """Latest video provider_task_id for a shot from billing audit / job snapshots."""
    shot_keys = _resolve_shot_pk_candidates(db, shot_id)
    if not shot_keys:
        return None

    from sqlalchemy import String, cast, or_

    from app.services.generation_task_queue import (
        _shot_id_sql_like_patterns,
        find_generation_job_states_by_shot_id,
        find_generation_tasks_by_shot_id,
    )

    candidates: List[Dict[str, Any]] = []

    like_filters = []
    for key in shot_keys:
        for pattern in _shot_id_sql_like_patterns(key):
            like_filters.append(cast(models.TransactionHistory.details, String).like(pattern))

    if like_filters:
        rows = (
            db.query(models.TransactionHistory)
            .filter(or_(*like_filters))
            .order_by(models.TransactionHistory.id.desc())
            .limit(120)
            .all()
        )
        for row in rows:
            details = _parse_json_object(getattr(row, "details", None))
            detail_shot = str(details.get("shot_id") or "").strip()
            if detail_shot not in set(shot_keys):
                continue
            desc = str(getattr(row, "description", None) or "").strip().lower()
            function_name = str(details.get("function_name") or "").strip().lower()
            is_video = (
                "video" in desc
                or "video" in function_name
                or str(details.get("asset_type") or "").strip().lower() == "video"
                or bool(details.get("duration_seconds") or details.get("duration"))
            )
            if not is_video and desc and "refund" not in desc:
                # Keep rows that explicitly carry video provider tasks even if description is sparse.
                pass
            if "refund" in desc:
                continue
            provider_task_id = _extract_provider_task_id_from_mapping(details)
            if not provider_task_id:
                continue
            owner_id = getattr(row, "user_id", None)
            try:
                safe_oid = int(owner_id) if owner_id is not None else None
            except Exception:
                safe_oid = None
            if (
                not is_superuser
                and current_user_id is not None
                and safe_oid is not None
                and int(current_user_id) != safe_oid
            ):
                continue
            created_at = getattr(row, "created_at", None)
            recency = 0.0
            try:
                if isinstance(created_at, (int, float)):
                    recency = float(created_at)
                elif created_at:
                    recency = datetime.fromisoformat(str(created_at).replace("Z", "+00:00")).timestamp()
            except Exception:
                recency = float(getattr(row, "id", 0) or 0)
            candidates.append(
                {
                    "provider_task_id": provider_task_id,
                    "provider": details.get("resolved_provider") or details.get("provider") or getattr(row, "provider", None),
                    "model": details.get("resolved_model") or details.get("model") or getattr(row, "model", None),
                    "system_api_id": details.get("resolved_system_api_id") or details.get("system_api_id"),
                    "query_endpoint": details.get("query_endpoint") or details.get("queryEndpoint"),
                    "shot_id": detail_shot,
                    "user_id": safe_oid,
                    "job_id": str(details.get("job_id") or "").strip() or None,
                    "transaction_id": int(getattr(row, "id", 0) or 0) or None,
                    "status": details.get("status") or None,
                    "created_at": created_at,
                    "recency_ts": recency,
                    "source": "transaction_history",
                }
            )

    # Job snapshots / queue rows that already carry provider_task_id.
    for key in shot_keys:
        try:
            for state in find_generation_job_states_by_shot_id(kind="video", shot_id=key, limit=40):
                provider_task_id = _extract_provider_task_id_from_mapping(state)
                if not provider_task_id:
                    continue
                owner_id = state.get("user_id")
                try:
                    safe_oid = int(owner_id) if owner_id is not None else None
                except Exception:
                    safe_oid = None
                if (
                    not is_superuser
                    and current_user_id is not None
                    and safe_oid is not None
                    and int(current_user_id) != safe_oid
                ):
                    continue
                candidates.append(
                    {
                        "provider_task_id": provider_task_id,
                        "provider": state.get("provider"),
                        "model": state.get("model"),
                        "system_api_id": state.get("system_api_id"),
                        "query_endpoint": state.get("query_endpoint"),
                        "shot_id": str(state.get("shot_id") or key),
                        "user_id": safe_oid,
                        "job_id": str(state.get("job_id") or "").strip() or None,
                        "transaction_id": None,
                        "status": state.get("status"),
                        "created_at": state.get("finished_at") or state.get("updated_at") or state.get("created_at"),
                        "recency_ts": _video_job_recency_ts(state),
                        "source": "job_state",
                    }
                )
        except Exception:
            logger.exception("[VideoJob] audit job_state lookup failed | shot_id=%s", key)

        try:
            for task in find_generation_tasks_by_shot_id(kind="video", shot_id=key, limit=40):
                payload = task.get("payload") if isinstance(task.get("payload"), dict) else {}
                provider_task_id = _extract_provider_task_id_from_mapping(payload)
                if not provider_task_id:
                    continue
                owner_id = task.get("user_id")
                try:
                    safe_oid = int(owner_id) if owner_id is not None else None
                except Exception:
                    safe_oid = None
                if (
                    not is_superuser
                    and current_user_id is not None
                    and safe_oid is not None
                    and int(current_user_id) != safe_oid
                ):
                    continue
                fake_job = dict(payload)
                fake_job["created_at"] = task.get("created_at")
                fake_job["finished_at"] = task.get("finished_at")
                candidates.append(
                    {
                        "provider_task_id": provider_task_id,
                        "provider": payload.get("provider"),
                        "model": payload.get("model"),
                        "system_api_id": payload.get("system_api_id"),
                        "query_endpoint": payload.get("query_endpoint"),
                        "shot_id": str(payload.get("shot_id") or key),
                        "user_id": safe_oid,
                        "job_id": str(task.get("job_id") or "").strip() or None,
                        "transaction_id": None,
                        "status": task.get("status"),
                        "created_at": task.get("finished_at") or task.get("created_at"),
                        "recency_ts": _video_job_recency_ts(fake_job),
                        "source": "task_queue",
                    }
                )
        except Exception:
            logger.exception("[VideoJob] audit task_queue lookup failed | shot_id=%s", key)

    if not candidates:
        return None

    # Latest provider_task_id only: sort by recency, then transaction/job id.
    candidates.sort(
        key=lambda item: (
            float(item.get("recency_ts") or 0.0),
            int(item.get("transaction_id") or 0),
            str(item.get("created_at") or ""),
        ),
        reverse=True,
    )
    best = dict(candidates[0])
    best.pop("recency_ts", None)
    return best


def _build_synthetic_job_from_provider_task_ref(ref: Dict[str, Any], *, shot_id: str) -> Dict[str, Any]:
    provider_task_id = str((ref or {}).get("provider_task_id") or "").strip()
    job_id = str((ref or {}).get("job_id") or "").strip()
    if not job_id:
        tx_id = (ref or {}).get("transaction_id")
        job_id = f"audit-tx:{tx_id}" if tx_id else f"provider-task:{provider_task_id}"
    system_api_id = (ref or {}).get("system_api_id")
    provider = (ref or {}).get("provider")
    return {
        "job_id": job_id,
        "shot_id": str((ref or {}).get("shot_id") or shot_id),
        "user_id": (ref or {}).get("user_id"),
        "status": (ref or {}).get("status"),
        "provider": provider,
        "model": (ref or {}).get("model"),
        "system_api_id": system_api_id,
        "provider_task_id": provider_task_id,
        "task_id": provider_task_id,
        "taskId": provider_task_id,
        "query_endpoint": (ref or {}).get("query_endpoint"),
        "created_at": (ref or {}).get("created_at"),
        "billing_context": {
            "provider": provider,
            "system_api_id": system_api_id,
            "shot_id": str((ref or {}).get("shot_id") or shot_id),
            "provider_task_id": provider_task_id,
            "query_endpoint": (ref or {}).get("query_endpoint"),
        },
        "_lookup_source": (ref or {}).get("source") or "transaction_history",
        "_audit_transaction_id": (ref or {}).get("transaction_id"),
    }


def _execute_provider_task_query(
    *,
    job: Dict[str, Any],
    apply_recovery: bool = False,
) -> Dict[str, Any]:
    from app.services.generation_runtime.callbacks import _extract_job_provider_task_id
    from app.services.generation_runtime.job_store import _extract_job_result_url
    from app.services.generation_runtime.timeout_poll_recovery import (
        _apply_poll_success,
        _hydrate_job,
        _resolve_poll_credentials,
    )
    from app.services.media_service import media_service

    stable_job_id = str((job or {}).get("job_id") or "").strip()
    provider_task_id = _extract_job_provider_task_id(job) or _extract_provider_task_id_from_mapping(job)
    if not provider_task_id:
        raise HTTPException(
            status_code=400,
            detail="provider_task_id not available yet for this job",
        )

    api_key, query_endpoint, provider, base_url = _resolve_poll_credentials(job)
    if not api_key:
        raise HTTPException(status_code=400, detail=f"No api_key found for provider {provider or '-'}")

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
    success_statuses = {
        "succeeded",
        "success",
        "completed",
        "done",
        "finish",
        "finished",
        "complete",
        "successful",
    }
    # Some providers only return a ready URL without a clear status field.
    provider_ready = bool(result_url) and (
        provider_status_l in success_statuses
        or not provider_status_l
    )
    is_synthetic_job = (
        not stable_job_id
        or str(stable_job_id).startswith("audit-tx:")
        or str(stable_job_id).startswith("provider-task:")
    )
    can_recover = bool(provider_ready)

    recovery_applied = False
    recovery_skipped_reason = None
    if can_recover and apply_recovery:
        try:
            if not is_synthetic_job:
                recovery_applied = bool(_apply_poll_success("video", stable_job_id, job, poll_result))
                if not recovery_applied:
                    recovery_skipped_reason = "recovery_apply_returned_false"
            else:
                recovery_applied = bool(
                    _recover_shot_video_from_provider_url(
                        shot_id=job.get("shot_id"),
                        result_url=result_url,
                        job=job,
                    )
                )
                if not recovery_applied:
                    recovery_skipped_reason = "shot_persist_returned_false"
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

    live = {}
    if stable_job_id and not is_synthetic_job:
        live = _hydrate_job("video", stable_job_id) or {}
    live_result_url = str(
        _extract_job_result_url((live or {}).get("result"))
        or existing_result_url
        or result_url
        or ""
    ).strip() or None

    return {
        "ok": True,
        "job_id": None if is_synthetic_job else (stable_job_id or None),
        "job_status": (live or {}).get("status") or job.get("status"),
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
        "source": job.get("_lookup_source"),
        "transaction_id": job.get("_audit_transaction_id"),
        "shot_id": job.get("shot_id"),
    }


def _recover_shot_video_from_provider_url(
    *,
    shot_id: Any,
    result_url: str,
    job: Optional[Dict[str, Any]] = None,
) -> bool:
    """Persist a provider result URL onto the shot when no recoverable video job exists."""
    from app.db.session import SessionLocal
    from app.models.all_models import Project, Shot, User
    from app.services.generation_runtime.media_persist import _persist_shot_media_slot

    stable_url = str(result_url or "").strip()
    try:
        shot_pk = int(str(shot_id or "").strip())
    except Exception:
        shot_pk = 0
    if not stable_url or shot_pk <= 0:
        return False

    db = SessionLocal()
    try:
        shot = db.query(Shot).filter(Shot.id == shot_pk).first()
        if shot is None:
            return False
        project = None
        if getattr(shot, "project_id", None) is not None:
            project = db.query(Project).filter(Project.id == int(shot.project_id)).first()
        owner = None
        try:
            owner_id = int((job or {}).get("user_id") or 0)
        except Exception:
            owner_id = 0
        if owner_id > 0:
            owner = db.query(User).filter(User.id == owner_id).first()
        if owner is None and project is not None and getattr(project, "owner_id", None) is not None:
            owner = db.query(User).filter(User.id == int(project.owner_id)).first()
        if owner is None or project is None:
            logger.warning(
                "[VideoJob] shot persist recovery missing owner/project | shot_id=%s user_id=%s project_id=%s",
                shot_pk,
                owner_id or None,
                getattr(shot, "project_id", None),
            )
            return False

        result = _persist_shot_media_slot(
            db,
            owner,
            project,
            shot,
            slot="video",
            source_url_override=stable_url,
        )
        ok = bool(result) and (
            bool(result.get("persisted_url"))
            or bool(result.get("oss_uploaded"))
            or bool(getattr(shot, "video_url", None))
        )
        if ok:
            logger.info(
                "[VideoJob] shot video recovered from provider url | shot_id=%s url=%s persisted=%s",
                shot_pk,
                stable_url,
                result.get("persisted_url") if isinstance(result, dict) else None,
            )
        return ok
    finally:
        db.close()


@router.get("/generate/video/shots/{shot_id}/latest-job")
def get_latest_video_job_for_shot(
    shot_id: str,
    response: Response,
    db: Session = Depends(get_db),
    current_claims: Dict[str, Any] = Depends(get_current_claims),
):
    """Resolve the latest provider_task_id for a shot (billing audit preferred)."""
    _apply_no_store_headers(response)
    safe_shot_id = str(shot_id or "").strip()
    if not safe_shot_id:
        raise HTTPException(status_code=400, detail="shot_id is required")

    current_user_id = current_claims.get("user_id")
    is_superuser = bool(current_claims.get("is_superuser"))
    try:
        safe_cid = int(current_user_id) if current_user_id is not None else None
    except Exception:
        safe_cid = None

    latest = _find_latest_video_provider_task_from_audit(
        db,
        safe_shot_id,
        current_user_id=safe_cid,
        is_superuser=is_superuser,
    )
    if not latest or not latest.get("provider_task_id"):
        raise HTTPException(status_code=404, detail="No provider_task_id found for this shot")

    return {
        "ok": True,
        "job_id": latest.get("job_id"),
        "status": latest.get("status"),
        "provider": latest.get("provider"),
        "model": latest.get("model"),
        "system_api_id": latest.get("system_api_id"),
        "provider_task_id": latest.get("provider_task_id"),
        "query_endpoint": latest.get("query_endpoint"),
        "shot_id": str(latest.get("shot_id") or safe_shot_id),
        "created_at": latest.get("created_at"),
        "finished_at": None,
        "transaction_id": latest.get("transaction_id"),
        "source": latest.get("source") or "transaction_history",
    }


@router.post("/generate/video/shots/{shot_id}/query-provider-task")
def query_video_shot_provider_task(
    shot_id: str,
    response: Response,
    req: Optional[VideoJobProviderTaskQueryRequest] = None,
    db: Session = Depends(get_db),
    current_claims: Dict[str, Any] = Depends(get_current_claims),
):
    """Query provider by the latest provider_task_id linked to this shot in audit records."""
    _apply_no_store_headers(response)
    apply_recovery = bool(getattr(req, "apply_recovery", False)) if req is not None else False
    safe_shot_id = str(shot_id or "").strip()
    if not safe_shot_id:
        raise HTTPException(status_code=400, detail="shot_id is required")

    current_user_id = current_claims.get("user_id")
    is_superuser = bool(current_claims.get("is_superuser"))
    try:
        safe_cid = int(current_user_id) if current_user_id is not None else None
    except Exception:
        safe_cid = None

    latest = _find_latest_video_provider_task_from_audit(
        db,
        safe_shot_id,
        current_user_id=safe_cid,
        is_superuser=is_superuser,
    )
    if not latest or not latest.get("provider_task_id"):
        raise HTTPException(status_code=404, detail="No provider_task_id found for this shot")

    job = _build_synthetic_job_from_provider_task_ref(latest, shot_id=safe_shot_id)
    real_job_id = str(latest.get("job_id") or "").strip()
    if real_job_id:
        loaded = _load_video_job_for_query(real_job_id)
        if loaded:
            # Keep audit provider_task_id authoritative when present.
            for key, value in job.items():
                if value in (None, "", {}, []) and loaded.get(key) not in (None, "", {}, []):
                    continue
                if key.startswith("_"):
                    loaded[key] = value
                    continue
                if key in {"provider_task_id", "task_id", "taskId", "system_api_id", "provider", "query_endpoint"}:
                    if value not in (None, ""):
                        loaded[key] = value
                elif loaded.get(key) in (None, ""):
                    loaded[key] = value
            job = loaded
            job["job_id"] = real_job_id

    result = _execute_provider_task_query(job=job, apply_recovery=apply_recovery)
    result["shot_id"] = safe_shot_id
    result["source"] = latest.get("source") or result.get("source")
    result["transaction_id"] = latest.get("transaction_id") or result.get("transaction_id")
    return result


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

    job = _load_video_job_for_query(stable_job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

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

    return _execute_provider_task_query(job=job, apply_recovery=apply_recovery)

