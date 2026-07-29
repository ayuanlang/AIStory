# -*- coding: utf-8 -*-
"""Video job reservation / settle helpers used by callbacks + generate."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.time_utils import now_bj_iso
from app.db.session import SessionLocal
from app.models.all_models import User
from app.services.billing_service import billing_service
from app.services.model_invocation_billing import (  # noqa: F401
    _extract_provider_usage_from_metadata,
    _resolve_usage_token_total,
    _safe_int_token,
)
from app.services.generation_runtime.media_runtime_target import (  # noqa: F401
    _resolve_media_runtime_target,
)
from app.services.media_service import media_service  # noqa: F401
from app.services.generation_runtime.job_store import (
    VIDEO_JOB_LOCK,
    VIDEO_JOB_STORE,
    _compact_job_result,
    _extract_job_result_url,
    _set_video_job,
)
from app.services.generation_runtime.media_persist import _hydrate_video_job_record

logger = logging.getLogger("api_logger")


def _extract_generation_job_id_from_ticket(kind: str, callback_ticket: str) -> str:
    from app.services.generation_runtime import callbacks as _cb
    return _cb._extract_generation_job_id_from_ticket(kind, callback_ticket)


def _reservation_already_closed(db: Session, reservation_tx_id: int) -> bool:
    try:
        from app.models.all_models import TransactionHistory

        tx = db.query(TransactionHistory).filter(TransactionHistory.id == int(reservation_tx_id)).first()
        if not tx:
            return True
        details = dict(tx.details or {}) if isinstance(tx.details, dict) else {}
        status = str(details.get("status") or "").strip().upper()
        return status in {"SETTLED", "CANCELED", "CANCELLED"}
    except Exception:
        return False


def _persist_video_job_billing_reservation(
    *,
    provider_callback_ticket: Optional[str] = None,
    job_id: Optional[str] = None,
    reservation_tx_id: Optional[int],
    billing_context: Optional[Dict[str, Any]] = None,
    user_id: Optional[int] = None,
) -> None:
    """Persist open reservation onto video job + task payload before provider callback can race."""
    try:
        tx_id = int(reservation_tx_id or 0) or None
    except Exception:
        tx_id = None
    if not tx_id:
        return

    stable_job_id = str(job_id or "").strip()
    if not stable_job_id:
        stable_job_id = _extract_generation_job_id_from_ticket("video", str(provider_callback_ticket or ""))
    if not stable_job_id:
        return

    context = dict(billing_context or {}) if isinstance(billing_context, dict) else {}
    fields: Dict[str, Any] = {
        "reservation_tx_id": int(tx_id),
        "billing_pending": True,
        "billing_settled": False,
        "billing_context": context,
    }
    if user_id is not None:
        try:
            fields["user_id"] = int(user_id)
        except Exception:
            pass
    if provider_callback_ticket:
        fields["provider_callback_ticket"] = str(provider_callback_ticket).strip()
    try:
        _set_video_job(stable_job_id, **fields)
    except Exception as exc:
        logger.warning(
            "[VideoJob] persist billing reservation to job failed | job_id=%s reservation_tx_id=%s err=%s",
            stable_job_id,
            tx_id,
            exc,
        )
    try:
        from app.services.generation_task_queue import patch_generation_task_payload

        patch_generation_task_payload(
            stable_job_id,
            {
                "reservation_tx_id": int(tx_id),
                "billing_pending": True,
                "billing_settled": False,
                "billing_context": context,
            },
        )
    except Exception as exc:
        logger.warning(
            "[VideoJob] persist billing reservation to task payload failed | job_id=%s reservation_tx_id=%s err=%s",
            stable_job_id,
            tx_id,
            exc,
        )


def _find_open_video_reservation_tx_id(
    db: Session,
    *,
    user_id: Optional[int] = None,
    shot_id: Optional[int] = None,
    project_id: Optional[int] = None,
    episode_id: Optional[int] = None,
) -> Optional[int]:
    """Recover a still-open video_gen reservation when job lost reservation_tx_id (multi-worker race)."""
    try:
        from app.models.all_models import TransactionHistory

        uid = int(user_id or 0)
        if uid <= 0:
            return None
        rows = (
            db.query(TransactionHistory)
            .filter(
                TransactionHistory.user_id == uid,
                TransactionHistory.amount < 0,
            )
            .order_by(TransactionHistory.id.desc())
            .limit(60)
            .all()
        )
    except Exception:
        return None

    want_shot = int(shot_id or 0) or None
    want_project = int(project_id or 0) or None
    want_episode = int(episode_id or 0) or None
    for row in rows or []:
        details = dict(getattr(row, "details", None) or {}) if isinstance(getattr(row, "details", None), dict) else {}
        status = str(details.get("status") or "").strip().upper()
        if status != "RESERVED":
            continue
        desc = str(getattr(row, "description", "") or "").strip().lower()
        task_hint = str(details.get("task_type") or details.get("description") or desc or "").strip().lower()
        if "video" not in task_hint and desc and "video" not in desc:
            # Prefer video_gen rows; description is usually the task_type.
            if desc not in {"video_gen", "video"}:
                continue
        row_shot = int(details.get("shot_id") or 0) or None
        row_project = int(details.get("project_id") or getattr(row, "project_id", 0) or 0) or None
        row_episode = int(details.get("episode_id") or getattr(row, "episode_id", 0) or 0) or None
        if want_shot and row_shot and row_shot != want_shot:
            continue
        if want_shot and not row_shot:
            continue
        if want_project and row_project and row_project != want_project:
            continue
        if want_episode and row_episode and row_episode != want_episode:
            continue
        if want_shot and row_shot == want_shot:
            return int(row.id)
        if not want_shot and want_project and row_project == want_project:
            return int(row.id)
    return None


def _extract_kie_callback_settle_fields(
    callback_payload: Optional[Dict[str, Any]],
    *,
    result_meta: Optional[Dict[str, Any]] = None,
    usage: Optional[Dict[str, Any]] = None,
    billing_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Pull KIE/Ark/RunningHub callback actuals: credits, tokens, costTime, RH coins/money, duration/ratio/resolution."""
    out: Dict[str, Any] = {}
    callback_payload = callback_payload if isinstance(callback_payload, dict) else {}
    result_meta = result_meta if isinstance(result_meta, dict) else {}
    usage = usage if isinstance(usage, dict) else {}
    billing_context = billing_context if isinstance(billing_context, dict) else {}

    data = callback_payload.get("data") if isinstance(callback_payload.get("data"), dict) else {}
    event_data = callback_payload.get("eventData") if isinstance(callback_payload.get("eventData"), dict) else {}
    event_usage = event_data.get("usage") if isinstance(event_data.get("usage"), dict) else {}
    sources = (usage, result_meta, event_usage, data, event_data, callback_payload)

    kie_credits = 0.0
    try:
        from app.services.billing_pricing import resolve_provider_kie_credits

        for src in sources:
            kie_credits = float(resolve_provider_kie_credits(src) or 0.0)
            if kie_credits > 0:
                break
    except Exception:
        kie_credits = 0.0
    if kie_credits > 0:
        out["kie_credits_consumed"] = kie_credits
        out["credits_consumed"] = kie_credits
        out["creditsConsumed"] = kie_credits
        out["billing_basis"] = "provider_kie_credits"

    # Ark Seedance callback: usage.completion_tokens / total_tokens.
    token_usage = usage if usage else {}
    if not token_usage:
        for src in sources:
            if isinstance(src, dict) and isinstance(src.get("usage"), dict):
                token_usage = dict(src.get("usage") or {})
                break
    actual_tokens = _resolve_usage_token_total(token_usage)
    if actual_tokens > 0:
        out["output_tokens"] = int(actual_tokens)
        out["total_tokens"] = int(actual_tokens)
        out["completion_tokens"] = int(
            _safe_int_token(token_usage.get("completion_tokens") or token_usage.get("output_tokens") or actual_tokens)
        )
        out["token_source"] = "api_usage"
        out.setdefault("billing_basis", "provider_tokens")

    cost_time = None
    for src in sources:
        if not isinstance(src, dict):
            continue
        for key in ("costTime", "cost_time", "taskCostTime", "task_cost_time"):
            if src.get(key) in (None, ""):
                continue
            try:
                cost_time = float(src.get(key))
            except Exception:
                cost_time = None
            if cost_time is not None and cost_time >= 0:
                break
        if cost_time is not None and cost_time >= 0:
            break
    # Ark: wall-clock from created_at → updated_at (unix seconds).
    if cost_time is None:
        try:
            created_at = float(callback_payload.get("created_at") or data.get("created_at") or 0)
            updated_at = float(callback_payload.get("updated_at") or data.get("updated_at") or 0)
            if created_at > 0 and updated_at >= created_at:
                cost_time = updated_at - created_at
        except Exception:
            cost_time = None
    if cost_time is not None and cost_time >= 0:
        out["provider_cost_time_seconds"] = cost_time
        out["cost_time"] = cost_time
        out["taskCostTime"] = cost_time

    # RunningHub usage: platform coins / wallet money / third-party money (audit; not KIE credits).
    for src in sources:
        if not isinstance(src, dict):
            continue
        if out.get("consumeCoins") in (None, "") and src.get("consumeCoins") not in (None, ""):
            try:
                out["consumeCoins"] = float(src.get("consumeCoins"))
            except Exception:
                pass
        if out.get("consumeMoney") in (None, "") and src.get("consumeMoney") not in (None, ""):
            try:
                out["consumeMoney"] = float(src.get("consumeMoney"))
            except Exception:
                pass
        if out.get("thirdPartyConsumeMoney") in (None, "") and src.get("thirdPartyConsumeMoney") not in (None, ""):
            try:
                out["thirdPartyConsumeMoney"] = float(src.get("thirdPartyConsumeMoney"))
            except Exception:
                pass
        if (
            out.get("consumeCoins") not in (None, "")
            and out.get("consumeMoney") not in (None, "")
            and out.get("thirdPartyConsumeMoney") not in (None, "")
        ):
            break

    # Nested KIE param JSON often carries actual duration / aspect / resolution.
    param_obj: Dict[str, Any] = {}
    raw_param = data.get("param") if isinstance(data, dict) else None
    if raw_param is None:
        raw_param = callback_payload.get("param")
    if isinstance(raw_param, str) and raw_param.strip():
        try:
            parsed_param = json.loads(raw_param)
            if isinstance(parsed_param, dict):
                param_obj = parsed_param
                nested_input = parsed_param.get("input")
                if isinstance(nested_input, str) and nested_input.strip():
                    try:
                        nested_parsed = json.loads(nested_input)
                        if isinstance(nested_parsed, dict):
                            param_obj = {**param_obj, **nested_parsed}
                    except Exception:
                        pass
                elif isinstance(nested_input, dict):
                    param_obj = {**param_obj, **nested_input}
        except Exception:
            param_obj = {}
    elif isinstance(raw_param, dict):
        param_obj = dict(raw_param)

    # Ark puts duration/ratio/resolution on the webhook root.
    duration = (
        callback_payload.get("duration")
        or data.get("duration")
        or param_obj.get("duration")
        or result_meta.get("duration")
        or billing_context.get("duration_seconds")
        or billing_context.get("duration")
    )
    if duration not in (None, ""):
        try:
            out["duration"] = float(duration)
            out["duration_seconds"] = float(duration)
        except Exception:
            pass
    aspect_ratio = (
        callback_payload.get("ratio")
        or callback_payload.get("aspect_ratio")
        or data.get("ratio")
        or param_obj.get("aspect_ratio")
        or result_meta.get("aspect_ratio")
        or billing_context.get("aspect_ratio")
    )
    if aspect_ratio not in (None, ""):
        out["aspect_ratio"] = str(aspect_ratio).strip()
    resolution = (
        callback_payload.get("resolution")
        or data.get("resolution")
        or param_obj.get("resolution")
        or result_meta.get("resolution")
        or billing_context.get("resolution")
    )
    if resolution not in (None, ""):
        out["resolution"] = str(resolution).strip()
    fps = (
        callback_payload.get("framespersecond")
        or callback_payload.get("fps")
        or data.get("framespersecond")
        or billing_context.get("fps")
    )
    if fps not in (None, ""):
        try:
            out["fps"] = int(float(fps))
        except Exception:
            pass
    if callback_payload.get("draft") is not None:
        out["draft_mode"] = bool(callback_payload.get("draft"))
        out["draft"] = bool(callback_payload.get("draft"))
    if callback_payload.get("generate_audio") is not None:
        out["has_audio"] = bool(callback_payload.get("generate_audio"))

    for ts_key, out_key in (
        ("createTime", "provider_create_time_ms"),
        ("completeTime", "provider_complete_time_ms"),
        ("updateTime", "provider_update_time_ms"),
        ("created_at", "provider_create_time_s"),
        ("updated_at", "provider_update_time_s"),
    ):
        for src in (data, callback_payload, result_meta):
            if isinstance(src, dict) and src.get(ts_key) not in (None, ""):
                try:
                    out[out_key] = int(src.get(ts_key))
                except Exception:
                    pass
                break

    return out


def _schedule_video_job_billing_settle(
    job_id: str,
    job: Optional[Dict[str, Any]] = None,
    callback_payload: Optional[Dict[str, Any]] = None,
) -> None:
    """Fire-and-forget settle from sync persistence paths (best effort)."""
    stable_job_id = str(job_id or "").strip()
    if not stable_job_id:
        return
    payload = callback_payload if isinstance(callback_payload, dict) else {}
    job_snapshot = dict(job or {})

    async def _runner() -> None:
        try:
            current = _hydrate_video_job_record(stable_job_id, job_snapshot)
            await _settle_or_cancel_video_job_billing_from_callback(stable_job_id, current, payload)
        except Exception as exc:
            logger.warning(
                "[VideoJob] scheduled settle failed | job_id=%s err=%s",
                stable_job_id,
                exc,
            )

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_runner())
    except RuntimeError:
        try:
            asyncio.run(_runner())
        except Exception as exc:
            logger.warning(
                "[VideoJob] scheduled settle (asyncio.run) failed | job_id=%s err=%s",
                stable_job_id,
                exc,
            )


def _cancel_video_job_pending_reservation(
    job_id: str,
    job: Optional[Dict[str, Any]],
    reason: str,
    *,
    usage_metadata: Optional[Dict[str, Any]] = None,
    extra_details: Optional[Dict[str, Any]] = None,
) -> None:
    job = job if isinstance(job, dict) else {}
    if job.get("billing_settled"):
        return
    try:
        reservation_tx_id = int(job.get("reservation_tx_id") or 0) or None
    except Exception:
        reservation_tx_id = None
    if not reservation_tx_id:
        return

    db = SessionLocal()
    try:
        if _reservation_already_closed(db, reservation_tx_id):
            _set_video_job(job_id, billing_settled=True, billing_pending=False, reservation_tx_id=None)
            return
        billing_service.cancel_reservation(
            db,
            reservation_tx_id,
            reason,
            usage_metadata=usage_metadata if isinstance(usage_metadata, dict) else None,
            extra_details=extra_details if isinstance(extra_details, dict) else None,
        )
        _set_video_job(
            job_id,
            billing_settled=True,
            billing_pending=False,
            reservation_tx_id=None,
            billing_cancel_reason=str(reason or "")[:500] or None,
        )
        logger.info(
            "[VideoJob] canceled pending reservation | job_id=%s reservation_tx_id=%s reason=%s",
            job_id,
            reservation_tx_id,
            str(reason or "")[:200],
        )
    except Exception as exc:
        logger.warning(
            "[VideoJob] cancel pending reservation failed | job_id=%s reservation_tx_id=%s error=%s",
            job_id,
            reservation_tx_id,
            exc,
        )
    finally:
        db.close()


async def _settle_or_cancel_video_job_billing_from_callback(
    job_id: str,
    job: Dict[str, Any],
    callback_payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Settle/cancel open video reservation after provider callback using actual usage when possible."""
    # Lazy: callbacks imports this module at bottom of callbacks.py.
    from app.services.generation_runtime.callbacks import (
        _extract_callback_task_id,
        _extract_job_provider_task_id,
        _merge_provider_task_ids_into_settle,
        _normalize_generation_status,
    )

    job = _hydrate_video_job_record(job_id, job) if job_id else (job or {})
    if not isinstance(job, dict):
        return job or {}
    if job.get("billing_settled"):
        return job

    status = _normalize_generation_status(job.get("status"))
    billing_context = job.get("billing_context") if isinstance(job.get("billing_context"), dict) else {}
    callback_payload = callback_payload if isinstance(callback_payload, dict) else {}

    try:
        reservation_tx_id = int(job.get("reservation_tx_id") or 0) or None
    except Exception:
        reservation_tx_id = None

    if status in {"failed", "error", "canceled", "cancelled"}:
        if not reservation_tx_id:
            # Best-effort recover reservation before cancel.
            db_probe = SessionLocal()
            try:
                reservation_tx_id = _find_open_video_reservation_tx_id(
                    db_probe,
                    user_id=job.get("user_id"),
                    shot_id=job.get("shot_id") or billing_context.get("shot_id"),
                    project_id=job.get("project_id") or billing_context.get("project_id"),
                    episode_id=job.get("episode_id") or billing_context.get("episode_id"),
                )
                if reservation_tx_id:
                    job = dict(job)
                    job["reservation_tx_id"] = reservation_tx_id
            finally:
                db_probe.close()
        reason = str(job.get("error") or callback_payload.get("failure_reason") or callback_payload.get("error") or status)
        cancel_usage: Dict[str, Any] = {}
        cancel_extra: Dict[str, Any] = {}
        try:
            from app.services.media_service import _extract_provider_task_usage, _normalize_provider_task_usage

            cancel_usage = _normalize_provider_task_usage(_extract_provider_task_usage(callback_payload))
        except Exception:
            cancel_usage = {}
        try:
            cancel_extra = _extract_kie_callback_settle_fields(
                callback_payload,
                usage=cancel_usage,
                billing_context=billing_context,
            )
        except Exception:
            cancel_extra = {}
        if cancel_usage:
            cancel_extra.setdefault("usage_source", "callback")
            cancel_extra.setdefault("provider_usage", cancel_usage)
        _cancel_video_job_pending_reservation(
            job_id,
            job,
            reason,
            usage_metadata=cancel_usage or None,
            extra_details=cancel_extra or None,
        )
        with VIDEO_JOB_LOCK:
            return dict(VIDEO_JOB_STORE.get(job_id) or job)

    if status not in {"succeeded", "completed", "done"}:
        return job

    db = SessionLocal()
    try:
        if not reservation_tx_id:
            reservation_tx_id = _find_open_video_reservation_tx_id(
                db,
                user_id=job.get("user_id"),
                shot_id=job.get("shot_id") or billing_context.get("shot_id"),
                project_id=job.get("project_id") or billing_context.get("project_id"),
                episode_id=job.get("episode_id") or billing_context.get("episode_id"),
            )
            if reservation_tx_id:
                _set_video_job(
                    job_id,
                    reservation_tx_id=int(reservation_tx_id),
                    billing_pending=True,
                    billing_context=billing_context,
                )
                job = dict(job)
                job["reservation_tx_id"] = int(reservation_tx_id)
                job["billing_pending"] = True
                logger.info(
                    "[VideoJob] recovered open reservation for settle | job_id=%s reservation_tx_id=%s shot_id=%s",
                    job_id,
                    reservation_tx_id,
                    job.get("shot_id") or billing_context.get("shot_id"),
                )
        if not reservation_tx_id:
            logger.warning(
                "[VideoJob] skip settle: no reservation_tx_id | job_id=%s shot_id=%s user_id=%s",
                job_id,
                job.get("shot_id") or billing_context.get("shot_id"),
                job.get("user_id"),
            )
            return job

        # Allow settle even when billing_pending was not set yet (callback-before-return race).
        if not job.get("billing_pending"):
            _set_video_job(job_id, billing_pending=True)
            job = dict(job)
            job["billing_pending"] = True

        if _reservation_already_closed(db, reservation_tx_id):
            _set_video_job(job_id, billing_settled=True, billing_pending=False, reservation_tx_id=None)
            with VIDEO_JOB_LOCK:
                return dict(VIDEO_JOB_STORE.get(job_id) or job)

        is_token_billing = bool(billing_context.get("is_token_billing"))
        provider = str(
            job.get("provider")
            or billing_context.get("provider")
            or ""
        ).strip() or None
        model = str(
            job.get("model")
            or billing_context.get("model")
            or ""
        ).strip() or None
        provider_lower = str(provider or "").strip().lower()
        is_kie_provider = (
            provider_lower == "kie"
            or provider_lower.startswith("kie/")
            or "kie.ai" in provider_lower
        )
        provider_task_id = _extract_job_provider_task_id(job) or _extract_callback_task_id(callback_payload)

        usage: Dict[str, Any] = {}
        result_meta = {}
        result_obj = job.get("result") if isinstance(job.get("result"), dict) else {}
        if isinstance(result_obj.get("metadata"), dict):
            result_meta = result_obj.get("metadata") or {}
            usage = _extract_provider_usage_from_metadata(result_meta)
        if not usage and callback_payload:
            try:
                from app.services.media_service import _extract_provider_task_usage, _normalize_provider_task_usage

                usage = _normalize_provider_task_usage(_extract_provider_task_usage(callback_payload))
            except Exception:
                usage = {}

        usage_source = str(result_meta.get("usage_source") or "").strip() or ("callback" if usage else "")
        # Prefer raw callback usage (Ark tokens / RunningHub coins+money+taskCostTime) over sparse metadata.
        if callback_payload and (
            _resolve_usage_token_total(usage) <= 0
            or not usage
            or (
                usage.get("consumeCoins") in (None, "")
                and usage.get("consumeMoney") in (None, "")
                and usage.get("taskCostTime") in (None, "")
            )
        ):
            try:
                from app.services.media_service import _extract_provider_task_usage, _normalize_provider_task_usage

                callback_usage = _normalize_provider_task_usage(_extract_provider_task_usage(callback_payload))
                if _resolve_usage_token_total(callback_usage) > 0:
                    usage = callback_usage
                    usage_source = "callback"
                elif callback_usage and (
                    not usage
                    or callback_usage.get("consumeCoins") not in (None, "")
                    or callback_usage.get("consumeMoney") not in (None, "")
                    or callback_usage.get("thirdPartyConsumeMoney") not in (None, "")
                    or callback_usage.get("taskCostTime") not in (None, "")
                ):
                    merged_usage = dict(usage or {})
                    merged_usage.update(callback_usage)
                    usage = merged_usage
                    usage_source = usage_source or "callback"
            except Exception:
                pass

        kie_fields = _extract_kie_callback_settle_fields(
            callback_payload,
            result_meta=result_meta,
            usage=usage,
            billing_context=billing_context,
        )
        # KIE credits → non-token settle; Ark callback tokens → token settle.
        if kie_fields.get("kie_credits_consumed"):
            is_token_billing = False
        elif (
            kie_fields.get("total_tokens")
            or kie_fields.get("completion_tokens")
            or _resolve_usage_token_total(usage) > 0
        ):
            is_token_billing = True
        elif is_kie_provider and not is_token_billing:
            pass

        # Re-query provider task for Ark/ZLHub-style token usage when callback omits it.
        if is_token_billing and _resolve_usage_token_total(usage) <= 0 and provider_task_id:
            try:
                user_id = int(job.get("user_id") or 0)
                user = db.query(User).filter(User.id == user_id).first() if user_id else None
                runtime = _resolve_media_runtime_target(
                    provider=provider,
                    model=model,
                    media_type="video",
                    category="Video",
                    user_id=user_id,
                    user_credits=int(getattr(user, "credits", 0) or 0) if user else 0,
                    system_api_id=billing_context.get("system_api_id"),
                )
                pre_api_cfg = runtime.get("pre_api_cfg") if isinstance(runtime.get("pre_api_cfg"), dict) else {}
                cfg_payload = pre_api_cfg.get("config") if isinstance(pre_api_cfg.get("config"), dict) else {}
                api_key = media_service._pick_runtime_api_key(
                    cfg_payload or pre_api_cfg,
                    pre_api_cfg.get("api_key"),
                    session=db,
                    provider_name=str(runtime.get("resolved_provider") or provider or ""),
                )
                query_endpoint = (
                    cfg_payload.get("query_endpoint")
                    or cfg_payload.get("base_url")
                    or cfg_payload.get("endpoint")
                    or pre_api_cfg.get("base_url")
                    or pre_api_cfg.get("endpoint")
                )
                fetched = await asyncio.to_thread(
                    media_service.fetch_provider_task_usage,
                    task_id=str(provider_task_id),
                    api_key=str(api_key or ""),
                    query_endpoint=str(query_endpoint or "") or None,
                    provider=str(runtime.get("resolved_provider") or provider or ""),
                    refresh_if_missing=True,
                )
                if isinstance(fetched, dict) and fetched:
                    usage = {k: v for k, v in fetched.items() if k != "raw_task"}
                    usage_source = "task_query"
                    provider = str(runtime.get("resolved_provider") or provider or "").strip() or provider
                    model = str(runtime.get("resolved_model") or model or "").strip() or model
            except Exception as usage_err:
                logger.warning(
                    "[VideoJob] callback task usage query failed | job_id=%s task_id=%s error=%s",
                    job_id,
                    provider_task_id,
                    usage_err,
                )

        if is_token_billing:
            actual_tokens = _resolve_usage_token_total(usage)
            token_source = "api_usage" if actual_tokens > 0 else "estimate"
            settle_details: Dict[str, Any] = {
                "status": "SETTLED",
                "billing_mode": "ACTUAL",
                "draft_mode": bool(billing_context.get("draft_mode")),
                "draft": bool(billing_context.get("draft_mode")),
                "use_prev_video": bool(billing_context.get("use_prev_video")),
                "shot_continuation": bool(billing_context.get("shot_continuation")),
                "has_video_input": bool(billing_context.get("has_video_input")),
                "width": billing_context.get("width"),
                "height": billing_context.get("height"),
                "fps": billing_context.get("fps") or 24,
            }
            if billing_context.get("aspect_ratio"):
                settle_details["aspect_ratio"] = billing_context.get("aspect_ratio")
            if billing_context.get("resolution"):
                settle_details["resolution"] = billing_context.get("resolution")
            if billing_context.get("duration_seconds") or billing_context.get("duration"):
                settle_details["duration"] = billing_context.get("duration_seconds") or billing_context.get("duration")
                settle_details["duration_seconds"] = settle_details["duration"]
            if actual_tokens <= 0:
                settle_duration = max(5, int(billing_context.get("duration_seconds") or billing_context.get("duration") or 5))
                draft_mode = bool(billing_context.get("draft_mode"))
                draft_coeff = float(billing_context.get("draft_token_coefficient") or 1.0)
                if not (0 < draft_coeff):
                    draft_coeff = 1.0
                settle_estimate = billing_service.estimate_video_token_usage(
                    width=int(billing_context.get("width") or 1280),
                    height=int(billing_context.get("height") or 720),
                    fps=int(billing_context.get("fps") or 24),
                    output_duration_seconds=settle_duration,
                    has_video_input=bool(billing_context.get("has_video_input")),
                    input_duration_seconds=(
                        billing_context.get("input_duration_seconds")
                        or billing_context.get("input_duration")
                    ),
                    draft_token_coefficient=draft_coeff,
                    method=(
                        "seedance2_video_token_formula"
                        if billing_context.get("is_seedance_2") or billing_service.is_seedance_2_model(provider, model)
                        else "video_token_formula"
                    ),
                )
                actual_tokens = int(settle_estimate.get("tokens") or billing_context.get("estimated_tokens") or 0)
                settle_details["video_token_estimate"] = settle_estimate
                settle_details["estimation_method"] = settle_estimate.get("estimation_method")
            else:
                settle_details["completion_tokens"] = _safe_int_token(
                    usage.get("completion_tokens") or usage.get("output_tokens") or actual_tokens
                )
            settle_details["output_tokens"] = int(max(0, actual_tokens))
            settle_details["total_tokens"] = int(max(0, actual_tokens))
            settle_details["token_source"] = token_source
        else:
            settle_details = {
                "duration": billing_context.get("duration"),
                "duration_seconds": billing_context.get("duration_seconds") or billing_context.get("duration"),
                "status": "SETTLED",
                "billing_mode": "ACTUAL",
                "draft_mode": bool(billing_context.get("draft_mode")),
                "draft": bool(billing_context.get("draft_mode")),
                "use_prev_video": bool(billing_context.get("use_prev_video")),
                "shot_continuation": bool(billing_context.get("shot_continuation")),
                "has_video_input": bool(billing_context.get("has_video_input")),
            }
            if billing_context.get("input_duration_seconds") is not None:
                settle_details["input_duration_seconds"] = billing_context.get("input_duration_seconds")
            elif billing_context.get("input_duration") is not None:
                settle_details["input_duration_seconds"] = billing_context.get("input_duration")
            if billing_context.get("width"):
                settle_details["width"] = billing_context.get("width")
            if billing_context.get("height"):
                settle_details["height"] = billing_context.get("height")
            if billing_context.get("resolution"):
                settle_details["resolution"] = billing_context.get("resolution")
            if billing_context.get("aspect_ratio"):
                settle_details["aspect_ratio"] = billing_context.get("aspect_ratio")

        # Overlay callback actuals (KIE credits / Ark tokens / costTime / duration).
        if kie_fields:
            for key, value in kie_fields.items():
                if value not in (None, ""):
                    settle_details[key] = value
            if kie_fields.get("kie_credits_consumed"):
                settle_details["usage_source"] = usage_source or "callback"
                if not usage:
                    usage = {
                        "creditsConsumed": kie_fields.get("kie_credits_consumed"),
                        "credits_consumed": kie_fields.get("kie_credits_consumed"),
                        "kie_credits_consumed": kie_fields.get("kie_credits_consumed"),
                        "credits": kie_fields.get("kie_credits_consumed"),
                    }
                    usage_source = settle_details["usage_source"]
            elif kie_fields.get("total_tokens") or kie_fields.get("completion_tokens"):
                settle_details["usage_source"] = usage_source or "callback"
                settle_details["token_source"] = settle_details.get("token_source") or "api_usage"
                if _resolve_usage_token_total(usage) <= 0:
                    usage = {
                        "completion_tokens": kie_fields.get("completion_tokens"),
                        "output_tokens": kie_fields.get("output_tokens") or kie_fields.get("total_tokens"),
                        "total_tokens": kie_fields.get("total_tokens"),
                    }

        if usage:
            settle_details["provider_usage"] = usage
            settle_details["usage_source"] = usage_source or settle_details.get("usage_source") or "provider"
            # Always promote callback/query tokens onto settle details (Ark Seedance usage.*).
            actual_from_usage = _resolve_usage_token_total(usage)
            if actual_from_usage > 0:
                settle_details["total_tokens"] = int(actual_from_usage)
                settle_details["output_tokens"] = int(
                    max(
                        0,
                        _safe_int_token(
                            usage.get("completion_tokens")
                            or usage.get("output_tokens")
                            or actual_from_usage
                        ),
                    )
                )
                settle_details["completion_tokens"] = int(
                    max(
                        0,
                        _safe_int_token(
                            usage.get("completion_tokens")
                            or usage.get("output_tokens")
                            or actual_from_usage
                        ),
                    )
                )
                if settle_details.get("token_source") in (None, "", "estimate"):
                    settle_details["token_source"] = "api_usage"
                settle_details.setdefault("billing_basis", "provider_tokens")
            elif settle_details.get("token_source") in (None, ""):
                # Explicitly mark missing supplier usage so reconcile can pick it up.
                settle_details["token_source"] = "estimate"
                settle_details.setdefault("usage_source", usage_source or "callback_no_usage")
        elif settle_details.get("token_source") in (None, "") and is_token_billing:
            # Token-billed job finished without supplier usage → keep estimate + reconcile later.
            settle_details["token_source"] = "estimate"
            settle_details.setdefault("usage_source", "callback_no_usage")
        if provider:
            settle_details["provider"] = provider
        if model:
            settle_details["model"] = model
        if billing_context.get("system_api_id") is not None:
            settle_details["system_api_id"] = billing_context.get("system_api_id")
        if billing_context.get("project_id"):
            settle_details["project_id"] = billing_context.get("project_id")
        if billing_context.get("episode_id"):
            settle_details["episode_id"] = billing_context.get("episode_id")
        if billing_context.get("shot_id"):
            settle_details["shot_id"] = billing_context.get("shot_id")
        elif job.get("shot_id"):
            settle_details["shot_id"] = job.get("shot_id")
        if provider_task_id:
            settle_details["provider_task_id"] = provider_task_id
            settle_details["task_id"] = provider_task_id
            settle_details["taskId"] = provider_task_id
        settle_details = _merge_provider_task_ids_into_settle(
            settle_details,
            callback_payload if isinstance(callback_payload, dict) else {},
            job if isinstance(job, dict) else {},
            billing_context if isinstance(billing_context, dict) else {},
        )

        billing_service.settle_reservation(db, reservation_tx_id, settle_details)
        _set_video_job(
            job_id,
            billing_settled=True,
            billing_pending=False,
            reservation_tx_id=None,
            billing_settle_token_source=settle_details.get("token_source"),
            billing_settle_usage_source=settle_details.get("usage_source"),
            billing_settle_kie_credits=settle_details.get("kie_credits_consumed"),
            billing_basis=settle_details.get("billing_basis"),
            billing_settle_cost_time=settle_details.get("provider_cost_time_seconds"),
        )
        logger.info(
            "[VideoJob] settled pending reservation from callback | job_id=%s reservation_tx_id=%s "
            "token_source=%s usage_source=%s total_tokens=%s kie_credits=%s cost_time=%s billing_basis=%s "
            "actual_cost_basis=supplier×multiplier",
            job_id,
            reservation_tx_id,
            settle_details.get("token_source"),
            settle_details.get("usage_source"),
            settle_details.get("total_tokens"),
            settle_details.get("kie_credits_consumed"),
            settle_details.get("provider_cost_time_seconds"),
            settle_details.get("billing_basis"),
        )
    except Exception as exc:
        logger.warning(
            "[VideoJob] settle pending reservation failed | job_id=%s reservation_tx_id=%s error=%s",
            job_id,
            reservation_tx_id,
            exc,
        )
    finally:
        db.close()

    with VIDEO_JOB_LOCK:
        return dict(VIDEO_JOB_STORE.get(job_id) or job)

