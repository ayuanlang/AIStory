# -*- coding: utf-8 -*-
"""Sanitize generation runtime config for logs (mask secrets)."""
from __future__ import annotations

from typing import Any


def _mask_secret_for_log(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if len(raw) <= 8:
        return "*" * len(raw)
    return f"{raw[:4]}***{raw[-4:]}"


def _sanitize_generation_runtime_config_for_log(value: Any) -> Any:
    secret_keys = {
        "api_key",
        "apikey",
        "authorization",
        "x-api-key",
        "access_token",
        "refresh_token",
        "private_key",
    }
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            key_text = str(key or "").strip().lower()
            if key_text in secret_keys:
                sanitized[key] = _mask_secret_for_log(item)
            else:
                sanitized[key] = _sanitize_generation_runtime_config_for_log(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_generation_runtime_config_for_log(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_generation_runtime_config_for_log(item) for item in value)
    return value


