# -*- coding: utf-8 -*-
"""Resolve provider/model runtime target for media generation."""
from __future__ import annotations

from typing import Any, Dict, Optional

from app.services.media_service import media_service


def _build_runtime_llm_config(provider: Optional[str], model: Optional[str], media_type: str = "media") -> Optional[Dict[str, str]]:
    provider_text = str(provider or "").strip()
    model_text = str(model or "").strip()
    if provider_text and model_text:
        return {"provider": provider_text, "model": model_text}
    if provider_text and not model_text:
        logger.info(
            "[%s] Ignore provider-only request override, fallback to active user settings | provider=%s",
            str(media_type or "media").capitalize(),
            provider_text,
        )
    elif model_text and not provider_text:
        logger.info(
            "[%s] Ignore model-only request override, fallback to active user settings | model=%s",
            str(media_type or "media").capitalize(),
            model_text,
        )
    return None

def _resolve_media_runtime_target(
    *,
    provider: Optional[str],
    model: Optional[str],
    media_type: str,
    category: str,
    user_id: int,
    user_credits: int,
    function_name: Optional[str] = None,
    system_api_id: Optional[int] = None,
) -> Dict[str, Any]:
    runtime_llm_config = _build_runtime_llm_config(provider, model, media_type=media_type)
    pre_api_cfg: Dict[str, Any] = {}
    user_explicit_provider = bool(str(provider or "").strip())
    user_explicit_model = bool(str(model or "").strip())
    user_explicit_selection = bool(user_explicit_provider or user_explicit_model)

    try:
        strict_provider = user_explicit_provider
        pre_api_cfg = media_service.get_api_config(
            provider=provider,
            user_id=user_id,
            category=category,
            requested_model=model,
            user_credits=user_credits,
            strict_provider=strict_provider,
            function_name=function_name,
            system_api_id=system_api_id,
        ) or {}

        resolved_provider = str((pre_api_cfg or {}).get("provider") or "").strip()
        resolved_model = str((pre_api_cfg or {}).get("model") or "").strip()
        if resolved_provider and resolved_model:
            runtime_llm_config = {"provider": resolved_provider, "model": resolved_model}
    except Exception:
        pre_api_cfg = pre_api_cfg or {}

    if not isinstance(runtime_llm_config, dict):
        runtime_llm_config = {}
    runtime_llm_config["__user_explicit_provider"] = user_explicit_provider
    runtime_llm_config["__user_explicit_model"] = user_explicit_model
    runtime_llm_config["__user_explicit_selection"] = user_explicit_selection

    resolved_provider = str((runtime_llm_config or {}).get("provider") or provider or "").strip() or None
    resolved_model = str((runtime_llm_config or {}).get("model") or model or "").strip() or None

    resolved_system_api_id = None
    try:
        cfg_payload = (pre_api_cfg or {}).get("config") if isinstance((pre_api_cfg or {}).get("config"), dict) else {}
        raw_id = cfg_payload.get("__resolved_setting_id") if isinstance(cfg_payload, dict) else None
        if raw_id is None:
            raw_id = (pre_api_cfg or {}).get("system_api_id")
        resolved_system_api_id = int(raw_id) if raw_id is not None else None
    except Exception:
        resolved_system_api_id = None

    return {
        "runtime_llm_config": runtime_llm_config or {},
        "pre_api_cfg": pre_api_cfg or {},
        "resolved_provider": resolved_provider,
        "resolved_model": resolved_model,
        "resolved_system_api_id": resolved_system_api_id,
    }

