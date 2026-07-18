"""Nightly reconcile: query providers for API txs missing actual supplier usage."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time_utils import BEIJING_TZ, now_bj
from app.db.session import SessionLocal
from app.models.all_models import SystemAPISetting, TransactionAction, TransactionHistory
from app.services.billing_pricing import (
    kie_credits_to_system_credits,
    resolve_provider_kie_credits,
)
from app.services.media_service import media_service

logger = logging.getLogger(__name__)

_SKIP_TASK_TYPES = {
    "",
    "recharge",
    "refund_manual",
    "group_credit_allocate",
    "group_credit_allocate_pool",
}


def _parse_iso(value: Any) -> Optional[datetime]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=BEIJING_TZ)
    return dt.astimezone(BEIJING_TZ)


def _as_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _safe_int_tokens(value: Any) -> int:
    try:
        return max(0, int(float(value or 0)))
    except Exception:
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _provider_is_kie(provider: Optional[str]) -> bool:
    text = str(provider or "").strip().lower()
    return text == "kie" or text.startswith("kie/") or "kie.ai" in text


def _has_actual_supplier_usage(
    action: TransactionAction,
    history: Optional[TransactionHistory],
) -> bool:
    usage = _as_dict(getattr(action, "usage_metadata", None))
    details = _as_dict(getattr(history, "details", None)) if history else {}
    billing_meta = _as_dict(getattr(action, "billing_metadata", None))

    kie = resolve_provider_kie_credits(usage) or resolve_provider_kie_credits(details)
    if kie > 0:
        return True
    basis = str(usage.get("billing_basis") or details.get("billing_basis") or "").strip()
    if basis == "provider_kie_credits":
        return True

    token_source = str(usage.get("token_source") or details.get("token_source") or "").strip().lower()
    total_tokens = _safe_int_tokens(
        usage.get("total_tokens")
        or usage.get("completion_tokens")
        or usage.get("output_tokens")
        or details.get("actual_total_tokens")
        or details.get("total_tokens")
    )
    if token_source == "api_usage" and total_tokens > 0:
        return True

    if billing_meta.get("reconcile_status") == "ok" and (
        _safe_float(billing_meta.get("reconciled_kie_credits")) > 0
        or _safe_int_tokens(billing_meta.get("reconciled_total_tokens")) > 0
    ):
        return True
    return False


def _extract_task_id(*payloads: Dict[str, Any]) -> str:
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        for key in ("provider_task_id", "task_id", "taskId", "job_task_id"):
            raw = str(payload.get(key) or "").strip()
            if raw and raw.lower() not in {"undefined", "null", "none"}:
                return raw
        nested = payload.get("provider_usage")
        if isinstance(nested, dict):
            raw_task = nested.get("raw_task") if isinstance(nested.get("raw_task"), dict) else {}
            for key in ("id", "task_id", "taskId"):
                raw = str(raw_task.get(key) or nested.get(key) or "").strip()
                if raw and raw.lower() not in {"undefined", "null", "none"}:
                    return raw
    return ""


def _extract_query_endpoint(*payloads: Dict[str, Any]) -> str:
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        for key in ("query_endpoint", "queryEndpoint"):
            raw = str(payload.get(key) or "").strip()
            if raw:
                return raw
    return ""


def _scan_job_dirs_for_task(reservation_tx_id: Optional[int]) -> Dict[str, Any]:
    if not reservation_tx_id:
        return {}
    roots = [
        Path(settings.UPLOAD_DIR) / "_image_jobs",
        Path(settings.UPLOAD_DIR) / "_video_jobs",
    ]
    target = int(reservation_tx_id)
    for root in roots:
        if not root.exists() or not root.is_dir():
            continue
        try:
            entries = [p for p in root.iterdir() if p.is_file()]
        except Exception:
            continue
        entries.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        for path in entries[:800]:
            if path.suffix.lower() not in {".json", ".txt"}:
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            try:
                rid = int(payload.get("reservation_tx_id") or 0)
            except Exception:
                rid = 0
            if rid != target:
                continue
            result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
            meta = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
            task_id = _extract_task_id(payload, meta, _as_dict(payload.get("billing_context")))
            if not task_id:
                continue
            return {
                "task_id": task_id,
                "provider": payload.get("provider"),
                "model": payload.get("model"),
                "system_api_id": payload.get("system_api_id")
                or _as_dict(payload.get("billing_context")).get("system_api_id"),
                "query_endpoint": _extract_query_endpoint(
                    payload,
                    _as_dict(payload.get("billing_context")),
                    meta,
                ),
                "source": f"job_file:{path.name}",
            }
    return {}


def _resolve_system_api_credentials(
    db: Session,
    *,
    system_api_id: Optional[int],
    provider: Optional[str],
) -> Tuple[str, str, Optional[int]]:
    row = None
    sid = 0
    try:
        sid = int(system_api_id or 0)
    except Exception:
        sid = 0
    if sid > 0:
        row = db.query(SystemAPISetting).filter(SystemAPISetting.id == sid).first()
    if row is None and provider:
        provider_l = str(provider or "").strip().lower()
        candidates = (
            db.query(SystemAPISetting)
            .filter(SystemAPISetting.provider.isnot(None))
            .order_by(SystemAPISetting.id.desc())
            .limit(60)
            .all()
        )
        for candidate in candidates:
            provider_text = str(getattr(candidate, "provider", "") or "").strip().lower()
            base_url = str(getattr(candidate, "base_url", "") or "").strip().lower()
            if not provider_text and not base_url:
                continue
            if provider_l and (
                provider_text == provider_l
                or provider_text.startswith(provider_l + "/")
                or provider_l.startswith(provider_text)
                or ("kie" in provider_l and (provider_text.startswith("kie") or "kie.ai" in base_url))
            ):
                row = candidate
                break
    if row is None:
        return "", "", None
    raw_key = str(getattr(row, "api_key", "") or "").strip()
    api_key = raw_key.split(",")[0].strip() if raw_key else ""
    conf = getattr(row, "config", None)
    query_endpoint = ""
    if isinstance(conf, dict):
        query_endpoint = str(conf.get("query_endpoint") or "").strip()
    if not query_endpoint:
        query_endpoint = str(getattr(row, "base_url", "") or "").strip()
    if _provider_is_kie(getattr(row, "provider", None)) and not query_endpoint:
        query_endpoint = "https://api.kie.ai/api/v1/jobs/recordInfo"
    return api_key, query_endpoint, int(getattr(row, "id", 0) or 0) or None


def find_reconcile_candidates(
    db: Session,
    *,
    lookback_days: int,
) -> List[Tuple[TransactionAction, Optional[TransactionHistory]]]:
    cutoff = now_bj() - timedelta(days=int(lookback_days))
    cutoff_iso = cutoff.isoformat(timespec="seconds")
    actions = (
        db.query(TransactionAction)
        .filter(TransactionAction.stage.in_(["SETTLED", "DEDUCTED", "RESERVED"]))
        .filter(TransactionAction.created_at >= cutoff_iso)
        .order_by(TransactionAction.id.desc())
        .limit(5000)
        .all()
    )
    out: List[Tuple[TransactionAction, Optional[TransactionHistory]]] = []
    for action in actions:
        created = _parse_iso(getattr(action, "created_at", None))
        if created is not None and created < cutoff:
            continue
        history = None
        tx_id = getattr(action, "transaction_id", None) or getattr(action, "reservation_tx_id", None)
        if tx_id:
            history = db.query(TransactionHistory).filter(TransactionHistory.id == int(tx_id)).first()
        task_type = str(getattr(action, "task_type", "") or "").strip().lower()
        if task_type in _SKIP_TASK_TYPES:
            continue
        if not getattr(action, "provider", None) and not getattr(action, "system_api_id", None):
            details = _as_dict(getattr(history, "details", None)) if history else {}
            if not details.get("resolved_provider") and not details.get("system_api_id"):
                continue
        if _has_actual_supplier_usage(action, history):
            continue
        billing_meta = _as_dict(getattr(action, "billing_metadata", None))
        if (
            billing_meta.get("reconcile_status") == "skipped_no_task_id"
            and int(billing_meta.get("reconcile_attempts") or 0) >= 3
        ):
            continue
        out.append((action, history))
    return out


def _apply_usage_to_records(
    db: Session,
    *,
    action: TransactionAction,
    history: Optional[TransactionHistory],
    usage: Dict[str, Any],
    usage_source: str,
) -> Dict[str, Any]:
    usage = dict(usage or {})
    usage.pop("raw_task", None)
    slim_usage = _as_dict(getattr(action, "usage_metadata", None))
    slim_usage.update({k: v for k, v in usage.items() if v not in (None, "")})
    slim_usage["usage_source"] = usage_source

    kie = float(resolve_provider_kie_credits(usage) or 0.0)
    total_tokens = _safe_int_tokens(
        usage.get("total_tokens") or usage.get("completion_tokens") or usage.get("output_tokens")
    )
    if kie > 0:
        slim_usage["kie_credits_consumed"] = kie
        slim_usage["credits_consumed"] = kie
        slim_usage["creditsConsumed"] = kie
        slim_usage["billing_basis"] = "provider_kie_credits"
    if total_tokens > 0:
        slim_usage["total_tokens"] = total_tokens
        if usage.get("completion_tokens") not in (None, ""):
            slim_usage["completion_tokens"] = _safe_int_tokens(usage.get("completion_tokens"))
        if usage.get("output_tokens") not in (None, ""):
            slim_usage["output_tokens"] = _safe_int_tokens(usage.get("output_tokens"))
        if usage.get("input_tokens") not in (None, ""):
            slim_usage["input_tokens"] = _safe_int_tokens(usage.get("input_tokens"))
        slim_usage["token_source"] = "api_usage"

    action.usage_metadata = slim_usage

    billing_meta = _as_dict(getattr(action, "billing_metadata", None))
    billing_meta["reconcile_status"] = "ok"
    billing_meta["reconciled_at"] = now_bj().isoformat(timespec="seconds")
    billing_meta["reconcile_source"] = usage_source
    billing_meta["reconcile_attempts"] = int(billing_meta.get("reconcile_attempts") or 0) + 1
    if kie > 0:
        billing_meta["reconciled_kie_credits"] = kie
        billing_meta["reconciled_supplier_system_credits"] = int(kie_credits_to_system_credits(kie))
    if total_tokens > 0:
        billing_meta["reconciled_total_tokens"] = total_tokens
    action.billing_metadata = billing_meta

    if history is not None:
        details = _as_dict(getattr(history, "details", None))
        if kie > 0:
            details["kie_credits_consumed"] = kie
            details["credits_consumed"] = kie
            details["creditsConsumed"] = kie
            details["billing_basis"] = "provider_kie_credits"
            details["usage_source"] = usage_source
        if total_tokens > 0:
            details["actual_total_tokens"] = total_tokens
            details["total_tokens"] = total_tokens
            details["token_source"] = "api_usage"
            details["usage_source"] = usage_source
        details["reconcile_status"] = "ok"
        details["reconciled_at"] = billing_meta["reconciled_at"]
        history.details = details

    db.add(action)
    if history is not None:
        db.add(history)
    return {
        "kie_credits": kie,
        "total_tokens": total_tokens,
        "supplier_system_credits": int(kie_credits_to_system_credits(kie)) if kie > 0 else 0,
    }


def _mark_reconcile_failure(
    db: Session,
    *,
    action: TransactionAction,
    history: Optional[TransactionHistory],
    reason: str,
) -> None:
    billing_meta = _as_dict(getattr(action, "billing_metadata", None))
    billing_meta["reconcile_status"] = reason
    billing_meta["reconciled_at"] = now_bj().isoformat(timespec="seconds")
    billing_meta["reconcile_attempts"] = int(billing_meta.get("reconcile_attempts") or 0) + 1
    action.billing_metadata = billing_meta
    db.add(action)
    if history is not None:
        details = _as_dict(getattr(history, "details", None))
        details["reconcile_status"] = reason
        details["reconciled_at"] = billing_meta["reconciled_at"]
        history.details = details
        db.add(history)


def reconcile_one(
    db: Session,
    action: TransactionAction,
    history: Optional[TransactionHistory],
) -> Dict[str, Any]:
    details = _as_dict(getattr(history, "details", None)) if history else {}
    usage_meta = _as_dict(getattr(action, "usage_metadata", None))
    billing_meta = _as_dict(getattr(action, "billing_metadata", None))

    provider = (
        str(
            getattr(action, "provider", None)
            or details.get("resolved_provider")
            or details.get("provider")
            or ""
        ).strip()
        or None
    )
    system_api_id = getattr(action, "system_api_id", None) or details.get("system_api_id")
    try:
        system_api_id = int(system_api_id) if system_api_id is not None else None
    except Exception:
        system_api_id = None

    task_id = _extract_task_id(details, usage_meta, billing_meta)
    query_endpoint = _extract_query_endpoint(details, usage_meta, billing_meta)
    task_source = "ledger"

    if not task_id:
        job_hit = _scan_job_dirs_for_task(
            getattr(action, "reservation_tx_id", None) or getattr(action, "transaction_id", None)
        )
        if job_hit:
            task_id = str(job_hit.get("task_id") or "").strip()
            query_endpoint = query_endpoint or str(job_hit.get("query_endpoint") or "").strip()
            provider = provider or (str(job_hit.get("provider") or "").strip() or None)
            if system_api_id is None and job_hit.get("system_api_id") is not None:
                try:
                    system_api_id = int(job_hit.get("system_api_id"))
                except Exception:
                    pass
            task_source = str(job_hit.get("source") or "job_file")

    if not task_id:
        _mark_reconcile_failure(db, action=action, history=history, reason="skipped_no_task_id")
        db.commit()
        return {"action_id": int(action.id), "status": "skipped_no_task_id", "provider": provider}

    if "runninghub" in str(provider or "").lower():
        _mark_reconcile_failure(db, action=action, history=history, reason="skipped_runninghub")
        db.commit()
        return {"action_id": int(action.id), "status": "skipped_runninghub", "provider": provider}

    api_key, resolved_endpoint, resolved_api_id = _resolve_system_api_credentials(
        db, system_api_id=system_api_id, provider=provider
    )
    query_endpoint = query_endpoint or resolved_endpoint
    if _provider_is_kie(provider) and not query_endpoint:
        query_endpoint = "https://api.kie.ai/api/v1/jobs/recordInfo"
    if not api_key:
        _mark_reconcile_failure(db, action=action, history=history, reason="skipped_no_api_key")
        db.commit()
        return {"action_id": int(action.id), "status": "skipped_no_api_key", "provider": provider}

    usage = media_service.fetch_provider_task_usage(
        task_id=task_id,
        api_key=api_key,
        query_endpoint=query_endpoint or None,
        provider=provider,
        refresh_if_missing=True,
    )
    if not usage:
        _mark_reconcile_failure(db, action=action, history=history, reason="query_empty")
        db.commit()
        return {
            "action_id": int(action.id),
            "status": "query_empty",
            "provider": provider,
            "task_id": task_id,
        }

    kie = float(resolve_provider_kie_credits(usage) or 0.0)
    total_tokens = _safe_int_tokens(
        usage.get("total_tokens") or usage.get("completion_tokens") or usage.get("output_tokens")
    )
    if kie <= 0 and total_tokens <= 0:
        _mark_reconcile_failure(db, action=action, history=history, reason="query_no_usage")
        db.commit()
        return {
            "action_id": int(action.id),
            "status": "query_no_usage",
            "provider": provider,
            "task_id": task_id,
        }

    if history is not None:
        details = _as_dict(getattr(history, "details", None))
        details["provider_task_id"] = task_id
        details["task_id"] = task_id
        if query_endpoint:
            details["query_endpoint"] = query_endpoint
        if resolved_api_id:
            details["system_api_id"] = resolved_api_id
        history.details = details

    applied = _apply_usage_to_records(
        db,
        action=action,
        history=history,
        usage=usage,
        usage_source=f"nightly_reconcile:{task_source}",
    )
    db.commit()
    logger.info(
        "Billing reconcile ok | action_id=%s tx=%s provider=%s task_id=%s kie=%s tokens=%s",
        action.id,
        getattr(history, "id", None),
        provider,
        task_id,
        applied.get("kie_credits"),
        applied.get("total_tokens"),
    )
    return {
        "action_id": int(action.id),
        "transaction_id": int(getattr(history, "id", 0) or 0) or None,
        "status": "ok",
        "provider": provider,
        "task_id": task_id,
        "task_source": task_source,
        **applied,
    }


def run_nightly_billing_reconcile(
    *,
    lookback_days: Optional[int] = None,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    days = int(
        lookback_days
        if lookback_days is not None
        else getattr(settings, "BILLING_RECONCILE_LOOKBACK_DAYS", 3)
    )
    max_rows = int(
        limit if limit is not None else getattr(settings, "BILLING_RECONCILE_MAX_ROWS", 500)
    )
    results: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    with SessionLocal() as db:
        candidates = find_reconcile_candidates(db, lookback_days=days)[: max(1, max_rows)]
        logger.info(
            "Billing reconcile scan | lookback_days=%s candidates=%s",
            days,
            len(candidates),
        )
        for action, _history in candidates:
            try:
                with SessionLocal() as row_db:
                    row_action = (
                        row_db.query(TransactionAction)
                        .filter(TransactionAction.id == action.id)
                        .first()
                    )
                    if row_action is None:
                        continue
                    row_history = None
                    tx_id = (
                        getattr(row_action, "transaction_id", None)
                        or getattr(row_action, "reservation_tx_id", None)
                    )
                    if tx_id:
                        row_history = (
                            row_db.query(TransactionHistory)
                            .filter(TransactionHistory.id == int(tx_id))
                            .first()
                        )
                    if _has_actual_supplier_usage(row_action, row_history):
                        continue
                    result = reconcile_one(row_db, row_action, row_history)
                results.append(result)
            except Exception as exc:
                logger.exception(
                    "Billing reconcile failed | action_id=%s",
                    getattr(action, "id", None),
                )
                errors.append({"action_id": getattr(action, "id", None), "error": str(exc)})

    ok_count = sum(1 for row in results if row.get("status") == "ok")
    summary = {
        "ok": len(errors) == 0,
        "lookback_days": days,
        "candidate_count": len(results) + len(errors),
        "reconciled_ok": ok_count,
        "results": results,
        "errors": errors,
        "created_at": now_bj().isoformat(timespec="seconds"),
    }
    logger.info(
        "Billing reconcile complete | ok=%s reconciled=%s errors=%s",
        summary["ok"],
        ok_count,
        len(errors),
    )
    return summary
