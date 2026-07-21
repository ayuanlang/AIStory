# -*- coding: utf-8 -*-
"""User advanced model preference helpers (temperature/seed/cfg/reasoning)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from app.models.all_models import User
from app.services.effective_api_setting import _safe_json_dict

_ALLOWED_REASONING_EFFORT = {"low", "medium", "high"}


def _normalize_reasoning_effort(value: Any) -> Optional[str]:
    raw = str(value or "").strip().lower()
    return raw if raw in _ALLOWED_REASONING_EFFORT else None


def _normalize_positive_seed(value: Any) -> Optional[int]:
    try:
        parsed = int(value)
    except Exception:
        return None
    return parsed if parsed > 0 else None


def _normalize_temperature(value: Any) -> Optional[float]:
    try:
        parsed = float(value)
    except Exception:
        return None
    if parsed < 0:
        return 0.0
    if parsed > 2:
        return 2.0
    return float(parsed)


def _normalize_cfg(value: Any) -> Optional[float]:
    try:
        parsed = float(value)
    except Exception:
        return None
    return float(parsed) if parsed > 0 else None


def _read_user_advanced_model_preferences(user: Optional[User]) -> Dict[str, Any]:
    if not user:
        return {}
    prefs = _safe_json_dict(getattr(user, "preferences", None))
    advanced = _safe_json_dict(prefs.get("advanced_model"))
    return {
        "temperature": _normalize_temperature(advanced.get("temperature")),
        "seed": _normalize_positive_seed(advanced.get("seed")),
        "cfg": _normalize_cfg(advanced.get("cfg")),
        "reasoning_effort": _normalize_reasoning_effort(advanced.get("reasoning_effort")),
    }


def _inject_user_advanced_llm_preferences(llm_config: Optional[Dict[str, Any]], user: Optional[User]) -> Optional[Dict[str, Any]]:
    if not isinstance(llm_config, dict):
        return llm_config

    advanced = _read_user_advanced_model_preferences(user)
    if not advanced:
        return llm_config

    cfg = llm_config.get("config") if isinstance(llm_config.get("config"), dict) else {}

    if advanced.get("temperature") is not None:
        cfg["temperature"] = float(advanced["temperature"])
    if advanced.get("seed") is not None:
        cfg["seed"] = int(advanced["seed"])
    if advanced.get("reasoning_effort"):
        cfg["reasoning_effort"] = advanced["reasoning_effort"]

    llm_config["config"] = cfg
    return llm_config
