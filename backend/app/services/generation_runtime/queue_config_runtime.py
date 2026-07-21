# -*- coding: utf-8 -*-
"""Queue config accessors + pure-callback mode detection (no worker deps)."""
from __future__ import annotations

import os
from typing import Any, Dict

from app.core.queue_config import load_queue_config

_q_conf = load_queue_config()


def _queue_runtime_config() -> Dict[str, Any]:
    try:
        loaded = load_queue_config()
        if isinstance(loaded, dict):
            return loaded
    except Exception:
        pass
    return dict(_q_conf or {})


def _queue_cfg_bool(key: str, default: bool = False) -> bool:
    cfg = _queue_runtime_config()
    value = cfg.get(key, default)
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _queue_cfg_int(key: str, default: int, minimum: int = 0, maximum: int = 10**9) -> int:
    cfg = _queue_runtime_config()
    try:
        raw = int(cfg.get(key, default))
    except Exception:
        raw = int(default)
    return max(int(minimum), min(int(maximum), int(raw)))


def _is_pure_callback_mode_enabled() -> bool:
    auto_mode = _queue_cfg_bool("pure_callback_mode_auto", True)
    if auto_mode:
        is_public_deploy = bool(
            str(os.getenv("RENDER_EXTERNAL_URL") or "").strip()
            or str(os.getenv("RENDER") or "").strip()
            or str(os.getenv("RAILWAY_STATIC_URL") or "").strip()
            or str(os.getenv("RAILWAY_PUBLIC_DOMAIN") or "").strip()
            or str(os.getenv("VERCEL_URL") or "").strip()
        )
        return is_public_deploy
    return _queue_cfg_bool("pure_callback_mode", False)

