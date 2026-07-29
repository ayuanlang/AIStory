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


def _has_runninghub_supplier_cost(payload: Dict[str, Any]) -> bool:
    for key in ("consumeMoney", "consumeCoins", "thirdPartyConsumeMoney"):
        if payload.get(key) is not None and str(payload.get(key)).strip() != "":
            return True
    return False


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

    nested_usage = usage.get("provider_usage") if isinstance(usage.get("provider_usage"), dict) else {}
    nested_details = details.get("provider_usage") if isinstance(details.get("provider_usage"), dict) else {}
    # Nested callback/query usage (e.g. Ark Seedance usage.completion_tokens) counts as actual.
    nested_kie = resolve_provider_kie_credits(nested_usage) or resolve_provider_kie_credits(nested_details)
    if nested_kie > 0:
        return True

    token_source = str(usage.get("token_source") or details.get("token_source") or "").strip().lower()
    usage_source = str(usage.get("usage_source") or details.get("usage_source") or "").strip().lower()
    total_tokens = _safe_int_tokens(
        usage.get("total_tokens")
        or usage.get("completion_tokens")
        or usage.get("output_tokens")
        or details.get("actual_total_tokens")
        or details.get("total_tokens")
        or details.get("completion_tokens")
        or nested_usage.get("total_tokens")
        or nested_usage.get("completion_tokens")
        or nested_usage.get("output_tokens")
        or nested_details.get("total_tokens")
        or nested_details.get("completion_tokens")
        or nested_details.get("output_tokens")
    )
    if total_tokens > 0 and token_source != "estimate":
        if token_source == "api_usage":
            return True
        # Callback often stores tokens under provider_usage without token_source stamp.
        if nested_usage or nested_details:
            return True
        if usage_source in {"callback", "provider", "task_query", "reconcile"}:
            return True

    if _has_runninghub_supplier_cost(usage) or _has_runninghub_supplier_cost(details):
        return True
    if _has_runninghub_supplier_cost(nested_usage) or _has_runninghub_supplier_cost(nested_details):
        return True

    if billing_meta.get("reconcile_status") == "ok" and (
        _safe_float(billing_meta.get("reconciled_kie_credits")) > 0
        or _safe_int_tokens(billing_meta.get("reconciled_total_tokens")) > 0
        or _has_runninghub_supplier_cost(billing_meta)
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


def _first_api_key_from_value(value: Any) -> str:
    if isinstance(value, str):
        raw = value.strip()
        return raw.split(",")[0].strip() if raw else ""
    if isinstance(value, dict):
        return _first_api_key_from_value(value.get("api_key") or value.get("key") or "")
    if isinstance(value, list):
        for item in value:
            found = _first_api_key_from_value(item)
            if found:
                return found
    return ""


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
    provider_l = str(provider or "").strip().lower()
    if row is None and provider_l:
        # Exact provider match first (do not limit to recent N rows — older
        # providers like ark-seedance can fall outside a fixed window).
        exact_rows = (
            db.query(SystemAPISetting)
            .filter(SystemAPISetting.provider.isnot(None))
            .order_by(SystemAPISetting.id.desc())
            .all()
        )
        for candidate in exact_rows:
            provider_text = str(getattr(candidate, "provider", "") or "").strip().lower()
            if provider_text == provider_l and _first_api_key_from_value(getattr(candidate, "api_key", None)):
                row = candidate
                break
        if row is None:
            for candidate in exact_rows:
                provider_text = str(getattr(candidate, "provider", "") or "").strip().lower()
                base_url = str(getattr(candidate, "base_url", "") or "").strip().lower()
                if not provider_text and not base_url:
                    continue
                if (
                    provider_text.startswith(provider_l + "/")
                    or provider_l.startswith(provider_text + "/")
                    or provider_l.startswith(provider_text)
                    or ("kie" in provider_l and (provider_text.startswith("kie") or "kie.ai" in base_url))
                    or (
                        ("ark" in provider_l or "seedance" in provider_l)
                        and ("ark" in provider_text or "seedance" in provider_text or "volces.com" in base_url)
                    )
                ):
                    if _first_api_key_from_value(getattr(candidate, "api_key", None)):
                        row = candidate
                        break

    api_key = ""
    query_endpoint = ""
    resolved_id: Optional[int] = None
    if row is not None:
        api_key = _first_api_key_from_value(getattr(row, "api_key", None))
        conf = getattr(row, "config", None)
        if isinstance(conf, dict):
            query_endpoint = str(conf.get("query_endpoint") or "").strip()
        if not query_endpoint:
            query_endpoint = str(getattr(row, "base_url", "") or "").strip()
        resolved_id = int(getattr(row, "id", 0) or 0) or None

    # Fallback: provider key pool (same source used by generation runtime).
    if not api_key and provider_l:
        try:
            from app.models.all_models import ProviderKeyPool

            pool = (
                db.query(ProviderKeyPool)
                .filter(ProviderKeyPool.provider.isnot(None))
                .all()
            )
            for candidate in pool:
                if str(getattr(candidate, "provider", "") or "").strip().lower() != provider_l:
                    continue
                api_key = _first_api_key_from_value(getattr(candidate, "api_keys", None))
                if api_key:
                    break
        except Exception:
            pass

    if not api_key and row is None:
        return "", "", None

    provider_text = str(getattr(row, "provider", None) or provider_l or "").strip().lower()
    base_url = str(getattr(row, "base_url", "") or "").strip().rstrip("/") if row is not None else ""
    if _provider_is_kie(provider_text or provider_l) and not query_endpoint:
        query_endpoint = "https://api.kie.ai/api/v1/jobs/recordInfo"
    if ("runninghub" in provider_text or "runninghub.cn" in base_url.lower()) and not query_endpoint:
        query_endpoint = "https://www.runninghub.cn/openapi/v2/query"
    elif query_endpoint.startswith("/") and ("runninghub" in provider_text or "runninghub" in base_url.lower()):
        query_endpoint = f"{base_url or 'https://www.runninghub.cn'}{query_endpoint}"
    if (
        not query_endpoint
        and ("ark" in provider_text or "seedance" in provider_text or "ark" in provider_l or "seedance" in provider_l)
    ):
        query_endpoint = "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"
    return api_key, query_endpoint, resolved_id


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
    for rh_key in ("consumeMoney", "consumeCoins", "thirdPartyConsumeMoney", "taskCostTime"):
        if rh_key in usage:
            slim_usage[rh_key] = usage.get(rh_key)
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
    for rh_key in ("consumeMoney", "consumeCoins", "thirdPartyConsumeMoney", "taskCostTime"):
        if rh_key in usage:
            billing_meta[rh_key] = usage.get(rh_key)
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
        rh_usage = {
            k: usage.get(k)
            for k in ("consumeMoney", "consumeCoins", "thirdPartyConsumeMoney", "taskCostTime")
            if k in usage
        }
        if rh_usage:
            details["provider_usage"] = rh_usage
            details["usage"] = dict(rh_usage)
            details["usage_source"] = usage_source
            if not details.get("billing_basis"):
                details["billing_basis"] = "provider_runninghub_usage"
        details["reconcile_status"] = "ok"
        details["reconciled_at"] = billing_meta["reconciled_at"]
        history.details = details

    db.add(action)
    if history is not None:
        db.add(history)
    out = {
        "kie_credits": kie,
        "total_tokens": total_tokens,
        "supplier_system_credits": int(kie_credits_to_system_credits(kie)) if kie > 0 else 0,
    }
    for rh_key in ("consumeMoney", "consumeCoins", "thirdPartyConsumeMoney", "taskCostTime"):
        if rh_key in usage:
            out[rh_key] = usage.get(rh_key)
    return out


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

    api_key, resolved_endpoint, resolved_api_id = _resolve_system_api_credentials(
        db, system_api_id=system_api_id, provider=provider
    )
    query_endpoint = query_endpoint or resolved_endpoint
    if _provider_is_kie(provider) and not query_endpoint:
        query_endpoint = "https://api.kie.ai/api/v1/jobs/recordInfo"
    if "runninghub" in str(provider or "").lower() and not query_endpoint:
        query_endpoint = "https://www.runninghub.cn/openapi/v2/query"
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
    has_rh_cost = _has_runninghub_supplier_cost(usage)
    has_rh_usage_block = any(
        k in usage for k in ("consumeMoney", "consumeCoins", "thirdPartyConsumeMoney", "taskCostTime")
    )
    if kie <= 0 and total_tokens <= 0 and not has_rh_cost and not has_rh_usage_block:
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

def summarize_reconcile_candidate(action: TransactionAction, history: Optional[TransactionHistory]) -> Dict[str, Any]:
    details = _as_dict(getattr(history, "details", None)) if history else {}
    usage = _as_dict(getattr(action, "usage_metadata", None))
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
    model = (
        str(getattr(action, "model", None) or details.get("resolved_model") or details.get("model") or "").strip()
        or None
    )
    task_id = _extract_task_id(details, usage, billing_meta)
    missing_reasons = []
    if not resolve_provider_kie_credits(usage) and not resolve_provider_kie_credits(details):
        if str(usage.get("billing_basis") or details.get("billing_basis") or "") != "provider_kie_credits":
            missing_reasons.append("missing_kie_credits")
    token_source = str(usage.get("token_source") or details.get("token_source") or "").strip().lower()
    nested_usage = usage.get("provider_usage") if isinstance(usage.get("provider_usage"), dict) else {}
    nested_details = details.get("provider_usage") if isinstance(details.get("provider_usage"), dict) else {}
    total_tokens = _safe_int_tokens(
        usage.get("total_tokens")
        or details.get("actual_total_tokens")
        or details.get("total_tokens")
        or usage.get("completion_tokens")
        or details.get("completion_tokens")
        or nested_usage.get("total_tokens")
        or nested_usage.get("completion_tokens")
        or nested_details.get("total_tokens")
        or nested_details.get("completion_tokens")
    )
    if token_source == "estimate" or (total_tokens <= 0 and token_source != "api_usage"):
        missing_reasons.append("missing_api_tokens")
    if not _has_runninghub_supplier_cost(usage) and not _has_runninghub_supplier_cost(details):
        nested = details.get("provider_usage") if isinstance(details.get("provider_usage"), dict) else {}
        if not _has_runninghub_supplier_cost(nested):
            missing_reasons.append("missing_runninghub_cost")
    if not missing_reasons:
        missing_reasons.append("missing_supplier_usage")

    return {
        "action_id": int(action.id),
        "transaction_id": int(getattr(history, "id", 0) or 0) or None,
        "user_id": int(getattr(action, "user_id", 0) or 0) or None,
        "stage": str(getattr(action, "stage", "") or ""),
        "task_type": str(getattr(action, "task_type", "") or ""),
        "provider": provider,
        "model": model,
        "system_api_id": getattr(action, "system_api_id", None) or details.get("system_api_id"),
        "created_at": (
            action.created_at.isoformat(timespec="seconds")
            if getattr(action, "created_at", None) is not None and hasattr(action.created_at, "isoformat")
            else (str(getattr(action, "created_at", "") or "") or None)
        ),
        "reserved_cost": int(getattr(action, "reserved_cost", 0) or 0),
        "actual_cost": int(getattr(action, "actual_cost", 0) or 0),
        "billing_basis": str(usage.get("billing_basis") or details.get("billing_basis") or "") or None,
        "token_source": token_source or None,
        "usage_source": str(usage.get("usage_source") or details.get("usage_source") or "") or None,
        "reconcile_status": str(billing_meta.get("reconcile_status") or details.get("reconcile_status") or "") or None,
        "reconcile_attempts": int(billing_meta.get("reconcile_attempts") or 0),
        "task_id": task_id or None,
        "has_task_id": bool(task_id),
        "missing_reasons": missing_reasons,
        "description": str(getattr(history, "description", "") or "") or None,
    }


def list_billing_reconcile_candidates(
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
    with SessionLocal() as db:
        pairs = find_reconcile_candidates(db, lookback_days=days)[: max(1, max_rows)]
        rows = [summarize_reconcile_candidate(action, history) for action, history in pairs]
    return {
        "ok": True,
        "lookback_days": days,
        "cutoff_at": (now_bj() - timedelta(days=days)).isoformat(timespec="seconds"),
        "total_count": len(rows),
        "candidates": rows,
        "created_at": now_bj().isoformat(timespec="seconds"),
    }


def run_billing_reconcile_by_action_ids(
    action_ids: List[int],
    *,
    lookback_days: Optional[int] = None,
) -> Dict[str, Any]:
    """Manual admin reconcile for selected TransactionAction IDs."""
    days = int(
        lookback_days
        if lookback_days is not None
        else getattr(settings, "BILLING_RECONCILE_LOOKBACK_DAYS", 3)
    )
    requested: List[int] = []
    seen = set()
    for raw in action_ids or []:
        try:
            aid = int(raw)
        except Exception:
            continue
        if aid <= 0 or aid in seen:
            continue
        seen.add(aid)
        requested.append(aid)

    process_log: List[Dict[str, Any]] = []
    results: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    def _log(step: str, **extra: Any) -> None:
        process_log.append(
            {
                "ts": now_bj().isoformat(timespec="seconds"),
                "step": step,
                **extra,
            }
        )

    _log("start", requested_count=len(requested), lookback_days=days)

    with SessionLocal() as db:
        stale_pairs = find_reconcile_candidates(db, lookback_days=days)
        stale_ids = {int(action.id) for action, _ in stale_pairs}

    for action_id in requested:
        if action_id not in stale_ids:
            item = {
                "action_id": action_id,
                "status": "skipped_not_candidate",
            }
            results.append(item)
            _log("skip", action_id=action_id, reason="not_in_candidate_list")
            continue
        try:
            with SessionLocal() as row_db:
                row_action = (
                    row_db.query(TransactionAction)
                    .filter(TransactionAction.id == action_id)
                    .first()
                )
                if row_action is None:
                    item = {"action_id": action_id, "status": "skipped_not_found"}
                    results.append(item)
                    _log("skip", action_id=action_id, reason="not_found")
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
                    item = {"action_id": action_id, "status": "skipped_already_has_usage"}
                    results.append(item)
                    _log("skip", action_id=action_id, reason="already_has_usage")
                    continue
                summary = summarize_reconcile_candidate(row_action, row_history)
                _log(
                    "query_start",
                    action_id=action_id,
                    provider=summary.get("provider"),
                    task_id=summary.get("task_id"),
                    transaction_id=summary.get("transaction_id"),
                )
                result = reconcile_one(row_db, row_action, row_history)
            results.append(result)
            _log(
                "query_done",
                action_id=action_id,
                status=result.get("status"),
                provider=result.get("provider"),
                task_id=result.get("task_id"),
                kie_credits=result.get("kie_credits"),
                total_tokens=result.get("total_tokens"),
                consumeMoney=result.get("consumeMoney"),
                consumeCoins=result.get("consumeCoins"),
            )
        except Exception as exc:
            logger.exception("Manual billing reconcile failed | action_id=%s", action_id)
            errors.append({"action_id": action_id, "error": str(exc)})
            _log("error", action_id=action_id, error=str(exc))

    ok_count = sum(1 for row in results if row.get("status") == "ok")
    skipped_count = sum(1 for row in results if str(row.get("status") or "").startswith("skipped"))
    _log(
        "finished",
        reconciled_ok=ok_count,
        skipped_count=skipped_count,
        error_count=len(errors),
    )
    return {
        "ok": len(errors) == 0,
        "lookback_days": days,
        "requested_count": len(requested),
        "reconciled_ok": ok_count,
        "skipped_count": skipped_count,
        "error_count": len(errors),
        "results": results,
        "errors": errors,
        "process_log": process_log,
        "created_at": now_bj().isoformat(timespec="seconds"),
    }




def run_billing_reconcile_single(provider: str, task_id: str) -> Dict[str, Any]:
    """Manual admin reconcile for a single specific provider and task_id."""
    provider = str(provider or "").strip()
    task_id = str(task_id or "").strip()
    if not provider or not task_id:
        return {"ok": False, "error": "provider and task_id are required"}

    with SessionLocal() as db:
        api_key, resolved_endpoint, resolved_api_id = _resolve_system_api_credentials(
            db, system_api_id=None, provider=provider
        )
        query_endpoint = resolved_endpoint
        if _provider_is_kie(provider) and not query_endpoint:
            query_endpoint = "https://api.kie.ai/api/v1/jobs/recordInfo"
        if "runninghub" in provider.lower() and not query_endpoint:
            query_endpoint = "https://www.runninghub.cn/openapi/v2/query"
        if (
            not query_endpoint
            and ("ark" in provider.lower() or "seedance" in provider.lower())
        ):
            query_endpoint = "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks"

        if not api_key:
            return {"ok": False, "error": "No api_key found for provider"}

        fetched = media_service.fetch_provider_task_usage(
            task_id=task_id,
            api_key=api_key,
            query_endpoint=query_endpoint or None,
            provider=provider,
            refresh_if_missing=True,
            include_raw_response=True,
        )
        raw_response = fetched.get("raw_response") if isinstance(fetched, dict) else None
        usage = {
            k: v
            for k, v in (fetched.items() if isinstance(fetched, dict) else [])
            if k != "raw_response"
        }
        if not usage and not (isinstance(raw_response, dict) and raw_response):
            return {
                "ok": False,
                "error": "No usage or task found from provider",
                "provider": provider,
                "task_id": task_id,
                "query_endpoint": query_endpoint or None,
                "system_api_id": resolved_api_id,
            }

        return {
            "ok": True,
            "provider": provider,
            "task_id": task_id,
            "query_endpoint": query_endpoint or None,
            "system_api_id": resolved_api_id,
            "usage": usage or None,
            "raw_response": raw_response if isinstance(raw_response, dict) else None,
        }
