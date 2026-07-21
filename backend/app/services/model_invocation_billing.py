# -*- coding: utf-8 -*-
"""Model-invocation billing helpers (LLM/media settle + reservation)."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.models.all_models import User
from app.services.billing_service import billing_service

logger = logging.getLogger("api_logger")


def _extract_llm_routing_metadata(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}

    routing_meta = payload.get("routing_metadata") if isinstance(payload.get("routing_metadata"), dict) else {}
    smart_meta = payload.get("smart_routing") if isinstance(payload.get("smart_routing"), dict) else {}

    provider = str(
        routing_meta.get("provider")
        or payload.get("provider")
        or ""
    ).strip() or None
    model = str(
        routing_meta.get("model")
        or payload.get("model")
        or ""
    ).strip() or None

    system_api_id_raw = (
        routing_meta.get("system_api_id")
        if routing_meta.get("system_api_id") is not None
        else payload.get("system_api_id")
    )
    if system_api_id_raw is None:
        system_api_id_raw = smart_meta.get("system_api_id")
    try:
        system_api_id = int(system_api_id_raw) if system_api_id_raw is not None else None
    except Exception:
        system_api_id = None

    metadata: Dict[str, Any] = {}
    if provider:
        metadata["provider"] = provider
    if model:
        metadata["model"] = model
    if system_api_id is not None:
        metadata["system_api_id"] = system_api_id
    if smart_meta:
        metadata["smart_routing"] = smart_meta
    return metadata


def _apply_llm_routing_to_billing_details(details: Dict[str, Any], payload: Any) -> None:
    if not isinstance(details, dict):
        return
    routing = _extract_llm_routing_metadata(payload)
    if routing:
        details.update(routing)
    # Prefer provider usage from LLM response payload (Grsai/OpenAI-compatible),
    # same actual-supplier path as Seedance token settles.
    usage = None
    if isinstance(payload, dict):
        nested = payload.get("usage")
        if isinstance(nested, dict) and nested:
            usage = nested
        elif payload.get("token_source") or payload.get("prompt_tokens") is not None or payload.get("completion_tokens") is not None:
            usage = payload
    _attach_llm_provider_usage_to_billing_details(details, usage)


def _attach_llm_provider_usage_to_billing_details(
    details: Dict[str, Any],
    usage: Optional[Dict[str, Any]] = None,
) -> None:
    """Mark settle details with API token usage so 实际供应商价 uses provider tokens."""
    if not isinstance(details, dict):
        return
    usage = usage if isinstance(usage, dict) else {}
    token_source = str(
        usage.get("token_source") or details.get("token_source") or ""
    ).strip().lower()
    total_tokens = _resolve_usage_token_total(details) or _resolve_usage_token_total(usage)
    if token_source == "api_usage" and total_tokens > 0:
        details["token_source"] = "api_usage"
        details.setdefault(
            "billing_basis",
            str(usage.get("billing_basis") or details.get("billing_basis") or "provider_tokens"),
        )
        details.setdefault(
            "usage_source",
            str(usage.get("usage_source") or details.get("usage_source") or "provider").strip() or "provider",
        )
        slim: Dict[str, Any] = {}
        for key in (
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "input_tokens",
            "output_tokens",
        ):
            value = usage.get(key)
            if value in (None, ""):
                value = details.get(key)
            if value not in (None, ""):
                slim[key] = value
        if slim:
            details["provider_usage"] = slim
    elif token_source == "estimate":
        details["token_source"] = "estimate"


def _safe_int_token(value: Any) -> int:
    try:
        parsed = int(value or 0)
        return parsed if parsed > 0 else 0
    except Exception:
        return 0


def _extract_provider_usage_from_metadata(metadata: Any) -> Dict[str, Any]:
    if not isinstance(metadata, dict):
        return {}

    for key in ("provider_usage", "usage"):
        value = metadata.get(key)
        if isinstance(value, dict) and value:
            return dict(value)

    # KIE callback may persist scalar creditsConsumed on metadata root.
    for key in ("kie_credits_consumed", "credits_consumed", "creditsConsumed"):
        if metadata.get(key) not in (None, ""):
            try:
                amount = float(metadata.get(key) or 0)
            except Exception:
                amount = 0.0
            if amount > 0:
                return {
                    "creditsConsumed": amount,
                    "credits_consumed": amount,
                    "kie_credits_consumed": amount,
                    "credits": amount,
                }

    raw_payload = metadata.get("raw")
    if isinstance(raw_payload, dict):
        try:
            from app.services.media_service import _extract_provider_task_usage, _normalize_provider_task_usage

            normalized = _normalize_provider_task_usage(_extract_provider_task_usage(raw_payload))
            if normalized:
                return normalized
        except Exception:
            pass
        raw_usage = raw_payload.get("usage")
        if isinstance(raw_usage, dict) and raw_usage:
            return dict(raw_usage)
        for nested_key in ("data", "output", "result", "content"):
            nested = raw_payload.get(nested_key)
            if isinstance(nested, dict):
                nested_usage = nested.get("usage")
                if isinstance(nested_usage, dict) and nested_usage:
                    return dict(nested_usage)
                for credit_key in ("creditsConsumed", "credits_consumed", "kie_credits_consumed"):
                    if nested.get(credit_key) not in (None, ""):
                        try:
                            amount = float(nested.get(credit_key) or 0)
                        except Exception:
                            amount = 0.0
                        if amount > 0:
                            return {
                                "creditsConsumed": amount,
                                "credits_consumed": amount,
                                "kie_credits_consumed": amount,
                                "credits": amount,
                            }

    return {}


async def _maybe_refresh_kie_credits_from_record_info(
    metadata: Any,
    provider: Optional[str] = None,
) -> float:
    """For KIE non-callback/jobs tasks: GET recordInfo?taskId=... when credits missing."""
    if not isinstance(metadata, dict):
        return 0.0
    provider_l = str(provider or metadata.get("provider") or "").strip().lower()
    if not (provider_l == "kie" or provider_l.startswith("kie/") or "kie.ai" in provider_l):
        return 0.0

    task_id = str(
        metadata.get("task_id")
        or metadata.get("taskId")
        or metadata.get("provider_task_id")
        or ""
    ).strip()
    if not task_id or task_id.lower() in {"undefined", "null", "none"}:
        return 0.0

    query_endpoint = str(
        metadata.get("query_endpoint")
        or metadata.get("queryEndpoint")
        or "https://api.kie.ai/api/v1/jobs/recordInfo"
    ).strip()
    api_key = ""
    try:
        from app.db.session import SessionLocal
        from app.models.all_models import SystemAPISetting

        db = SessionLocal()
        try:
            system_api_id = metadata.get("system_api_id")
            row = None
            try:
                sid = int(system_api_id) if system_api_id is not None else 0
            except Exception:
                sid = 0
            if sid > 0:
                row = db.query(SystemAPISetting).filter(SystemAPISetting.id == sid).first()
            if row is None:
                candidates = (
                    db.query(SystemAPISetting)
                    .filter(SystemAPISetting.provider.isnot(None))
                    .order_by(SystemAPISetting.id.desc())
                    .limit(40)
                    .all()
                )
                for candidate in candidates:
                    provider_text = str(getattr(candidate, "provider", "") or "").strip().lower()
                    base_url = str(getattr(candidate, "base_url", "") or "").strip().lower()
                    if provider_text == "kie" or provider_text.startswith("kie/") or "kie.ai" in base_url:
                        row = candidate
                        break
            if row is not None:
                raw_key = str(getattr(row, "api_key", "") or "").strip()
                api_key = raw_key.split(",")[0].strip() if raw_key else ""
                conf = getattr(row, "config", None)
                if isinstance(conf, dict):
                    query_endpoint = str(conf.get("query_endpoint") or query_endpoint).strip()
        finally:
            db.close()
    except Exception:
        api_key = ""
    if not api_key:
        return 0.0

    try:
        from app.services.media_service import media_service
        from app.services.billing_pricing import resolve_provider_kie_credits

        usage = await asyncio.to_thread(
            media_service.fetch_provider_task_usage,
            task_id=task_id,
            api_key=api_key,
            query_endpoint=query_endpoint,
            provider="kie",
            refresh_if_missing=True,
        )
        credits = float(resolve_provider_kie_credits(usage) or 0.0)
        if credits > 0:
            metadata["provider_usage"] = usage
            metadata["usage_source"] = "kie_recordInfo_settle_refresh"
            metadata["creditsConsumed"] = credits
            metadata["credits_consumed"] = credits
            metadata["kie_credits_consumed"] = credits
            logger.info(
                "[Billing] KIE recordInfo settle refresh | task_id=%s creditsConsumed=%s",
                task_id,
                credits,
            )
        return credits
    except Exception as exc:
        logger.warning(
            "[Billing] KIE recordInfo settle refresh failed | task_id=%s error=%s",
            task_id,
            exc,
        )
        return 0.0


def _resolve_usage_token_total(usage: Any) -> int:
    """Resolve billable token total from provider usage (Ark: total_tokens / completion_tokens)."""
    if not isinstance(usage, dict) or not usage:
        return 0
    total = _safe_int_token(usage.get("total_tokens"))
    if total > 0:
        return total
    output = _safe_int_token(usage.get("output_tokens") or usage.get("completion_tokens"))
    if output > 0:
        prompt = _safe_int_token(usage.get("input_tokens") or usage.get("prompt_tokens"))
        return prompt + output if prompt > 0 else output
    return 0


def _build_standard_billing_details(
    *,
    item: str,
    usage_payload: Optional[Dict[str, Any]] = None,
    extra_details: Optional[Dict[str, Any]] = None,
    routing_payload: Any = None,
) -> Dict[str, Any]:
    details: Dict[str, Any] = {
        "item": str(item or "").strip() or "unknown",
        "billing_mode": "ACTUAL",
        "audit_source": "endpoints",
    }

    usage = usage_payload if isinstance(usage_payload, dict) else {}
    if usage:
        input_tokens = _safe_int_token(usage.get("input_tokens") or usage.get("prompt_tokens"))
        output_tokens = _safe_int_token(usage.get("output_tokens") or usage.get("completion_tokens"))
        total_tokens = _safe_int_token(usage.get("total_tokens"))
        if total_tokens <= 0:
            total_tokens = input_tokens + output_tokens

        details.update({
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
        })
        # Local estimate fallback has no token_source; provider usage is tagged api_usage.
        if str(usage.get("token_source") or "").strip().lower() != "api_usage" and total_tokens > 0:
            details.setdefault("token_source", "estimate")

    if isinstance(extra_details, dict) and extra_details:
        details.update(extra_details)

    _apply_llm_routing_to_billing_details(details, routing_payload)
    _attach_llm_provider_usage_to_billing_details(details, usage)
    return details


def _reservation_tx_id(reservation_tx: Any) -> Optional[int]:
    if reservation_tx is None:
        return None
    try:
        if isinstance(reservation_tx, int):
            parsed = int(reservation_tx)
            return parsed if parsed > 0 else None
    except Exception:
        pass

    try:
        raw_dict = getattr(reservation_tx, "__dict__", None)
        if isinstance(raw_dict, dict):
            raw_id = raw_dict.get("id")
            if raw_id is not None:
                parsed = int(raw_id or 0)
                if parsed > 0:
                    return parsed
    except Exception:
        pass

    try:
        state = inspect(reservation_tx)
        identity = getattr(state, "identity", None)
        if identity and len(identity) > 0:
            parsed = int(identity[0] or 0)
            if parsed > 0:
                return parsed
    except Exception:
        pass

    try:
        parsed = int(getattr(reservation_tx, "id", 0) or 0)
        return parsed if parsed > 0 else None
    except Exception:
        return None


def _finalize_model_invocation_billing(
    *,
    db: Session,
    current_user: User,
    task_type: str,
    provider: Optional[str],
    model: Optional[str],
    reservation_tx: Any,
    reservation_tx_id: Optional[int] = None,
    item: str,
    usage_payload: Optional[Dict[str, Any]] = None,
    extra_details: Optional[Dict[str, Any]] = None,
    routing_payload: Any = None,
    cancel_if_missing_usage: bool = False,
    missing_usage_reason: str = "No usage returned",
) -> Dict[str, Any]:
    details = _build_standard_billing_details(
        item=item,
        usage_payload=usage_payload,
        extra_details=extra_details,
        routing_payload=routing_payload,
    )

    tx_id: Optional[int] = None
    if reservation_tx_id is not None:
        try:
            parsed = int(reservation_tx_id)
            tx_id = parsed if parsed > 0 else None
        except Exception:
            tx_id = None
    if tx_id is None:
        tx_id = _reservation_tx_id(reservation_tx)

    if tx_id is not None:
        if cancel_if_missing_usage and not isinstance(usage_payload, dict):
            billing_service.cancel_reservation(db, tx_id, missing_usage_reason)
            return details
        billing_service.settle_reservation(db, tx_id, details)
        return details

    billing_service.deduct_credits(
        db,
        current_user.id,
        task_type,
        provider,
        model,
        details,
    )
    return details


def _cancel_reservation_quietly(db: Session, reservation_tx: Any, reason: str) -> None:
    if reservation_tx is None:
        return

    tx_id = None
    try:
        if isinstance(reservation_tx, int):
            tx_id = int(reservation_tx)
        else:
            tx_id = int(getattr(reservation_tx, "id", 0) or 0)
    except Exception:
        tx_id = None

    if tx_id is None or tx_id <= 0:
        return

    try:
        billing_service.cancel_reservation(db, tx_id, str(reason or "cancelled"))
    except Exception:
        pass

