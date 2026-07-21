# -*- coding: utf-8 -*-
"""Generation failure message formatting helpers."""
from __future__ import annotations

from typing import Any


def _is_generic_generation_error_text(value: Any) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return True
    return text in {
        "generation failed",
        "image generation failed",
        "video generation failed",
        "voice generation failed",
        "kie generation failed",
        "vidu generation failed",
    }

def _extract_generation_failure_reason(value: Any, depth: int = 0) -> str:
    if depth > 4 or value is None:
        return ""
    if isinstance(value, dict):
        for key in ("failure_reason", "failedReason", "reason"):
            candidate = str(value.get(key) or "").strip()
            if candidate:
                return candidate
        for key in ("details", "data", "result", "record", "raw"):
            candidate = _extract_generation_failure_reason(value.get(key), depth + 1)
            if candidate:
                return candidate
    elif isinstance(value, list):
        for item in value[:5]:
            candidate = _extract_generation_failure_reason(item, depth + 1)
            if candidate:
                return candidate
    return ""

def _extract_generation_failure_message(value: Any, depth: int = 0) -> str:
    if depth > 4 or value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("error", "message", "msg", "failMsg", "detail"):
            candidate = _extract_generation_failure_message(value.get(key), depth + 1)
            if candidate and candidate.lower() not in {"success", "ok", "true", "0"}:
                return candidate
        for key in ("details", "data", "result", "record", "raw"):
            candidate = _extract_generation_failure_message(value.get(key), depth + 1)
            if candidate and candidate.lower() not in {"success", "ok", "true", "0"}:
                return candidate
    elif isinstance(value, list):
        for item in value[:5]:
            candidate = _extract_generation_failure_message(item, depth + 1)
            if candidate:
                return candidate
    return ""

def _format_generation_failure_detail(result: Any, fallback_error: str = "Generation failed") -> str:
    if isinstance(result, dict):
        base_error = str(result.get("error") or "").strip()
        details = result.get("details")
        detail_message = _extract_generation_failure_message(details)
        failure_reason = (
            str(result.get("failure_reason") or result.get("failedReason") or "").strip()
            or _extract_generation_failure_reason(details)
        )

        if not base_error:
            base_error = detail_message or fallback_error
        elif detail_message and detail_message != base_error and _is_generic_generation_error_text(base_error):
            base_error = detail_message
        elif detail_message and detail_message != base_error and detail_message.lower() not in base_error.lower():
            base_error = f"{base_error}: {detail_message}"

        if failure_reason and failure_reason.lower() not in base_error.lower():
            base_error = f"{base_error} [failure_reason={failure_reason}]"

        return base_error or fallback_error

    text = str(result or "").strip()
    return text or fallback_error

