# -*- coding: utf-8 -*-
"""Script-analysis / story-generator LLM dropdown resolution."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import all_models as models
from app.services.agent_service import agent_service

logger = logging.getLogger("api_logger")

def _script_analysis_function_api_name(function_name: Any) -> str:
    raw = str(function_name or "").strip()
    if raw.startswith("script_analysis"):
        return "script_analysis"
    return raw or "script_analysis"


def _resolve_script_analysis_dropdown_order(db: Session, function_name: Any) -> List[int]:
    resolved_function_name = _script_analysis_function_api_name(function_name)
    row = db.query(models.FunctionAPIConfig).filter(
        models.FunctionAPIConfig.function_name == resolved_function_name,
    ).first()
    raw_settings = row.api_settings if row and isinstance(row.api_settings, list) else []

    def _priority(item: Dict[str, Any]) -> int:
        try:
            return int(item.get("priority") or 0)
        except Exception:
            return 0

    ordered_ids: List[int] = []
    for item in sorted(
        [entry for entry in raw_settings if isinstance(entry, dict)],
        key=_priority,
        reverse=True,
    ):
        try:
            setting_id = int(item.get("system_api_id") or 0)
        except Exception:
            setting_id = 0
        if setting_id > 0 and setting_id not in ordered_ids:
            ordered_ids.append(setting_id)
    return ordered_ids


def _select_script_analysis_api_order(ordered_ids: List[int], selected_system_api_id: Any) -> Tuple[Optional[int], List[int]]:
    try:
        selected_id = int(selected_system_api_id or 0)
    except Exception:
        selected_id = 0

    if selected_id > 0 and selected_id in ordered_ids:
        primary_id = selected_id
    elif ordered_ids:
        primary_id = ordered_ids[0]
    else:
        primary_id = None

    fallback_ids = [setting_id for setting_id in ordered_ids if setting_id != primary_id]
    return primary_id, fallback_ids


def _resolve_script_analysis_dropdown_llm_config(
    db: Session,
    current_user_id: int,
    function_name: Any,
    system_api_id: Any,
    *,
    context: str,
) -> Tuple[Dict[str, Any], int, List[int], List[int]]:
    dropdown_order_ids = _resolve_script_analysis_dropdown_order(db, function_name)
    selected_dropdown_id, dropdown_fallback_ids = _select_script_analysis_api_order(
        dropdown_order_ids,
        system_api_id,
    )
    if not selected_dropdown_id:
        raise HTTPException(status_code=400, detail="Script analysis API dropdown has no configured LLM API.")

    primary_configs = agent_service.get_fallback_configs_by_ids([selected_dropdown_id])
    config = primary_configs[0] if primary_configs else {}
    if not config or not config.get("api_key"):
        raise HTTPException(status_code=400, detail="Selected script analysis LLM API is unavailable. Please check the API dropdown settings.")

    cfg_for_route = config.get("config") if isinstance(config.get("config"), dict) else {}
    cfg_for_route["__override_fallback_candidates"] = dropdown_fallback_ids
    cfg_for_route["__selection_source"] = "script_analysis_dropdown_priority"
    cfg_for_route["__resolved_user_id"] = current_user_id
    cfg_for_route["__resolved_category"] = "LLM"
    cfg_for_route["__dropdown_order_ids"] = dropdown_order_ids
    cfg_for_route["__active_retry_attempts"] = 1
    config["config"] = cfg_for_route

    logger.info(
        "[%s][routing] source=dropdown_priority function_name=%s requested_system_api_id=%s selected_system_api_id=%s fallback_ids=%s provider=%s model=%s",
        context,
        function_name,
        system_api_id,
        selected_dropdown_id,
        dropdown_fallback_ids,
        (config or {}).get("provider"),
        (config or {}).get("model"),
    )
    return config, selected_dropdown_id, dropdown_fallback_ids, dropdown_order_ids


def _resolve_story_generator_script_analysis_llm_config(
    db: Session,
    user_id: int,
    *,
    function_name: Any = "script_analysis",
    system_api_id: Any = None,
    context: str,
    project_global_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    resolved_fn = _script_analysis_function_api_name(function_name)
    llm_config, _, _, _ = _resolve_script_analysis_dropdown_llm_config(
        db,
        user_id,
        resolved_fn,
        system_api_id,
        context=context,
    )
    if project_global_info is not None:
        llm_config = _inject_project_creativity_temperature(
            llm_config,
            project_global_info,
            context=context,
        )
    return llm_config


