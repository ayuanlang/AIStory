# -*- coding: utf-8 -*-
"""Seedance model identity + duration clamp helpers."""
from __future__ import annotations

import re
from typing import Any, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.all_models import SystemAPISetting


def _read_system_api_base_model_row(row: Any) -> str:
    return str(getattr(row, "base_model", "") or "").strip()


def _is_seedance2_base_model(base_model: Any) -> bool:
    candidate = str(base_model or "").strip().lower()
    if not candidate:
        return False
    if candidate.startswith("doubao-seedance-2"):
        return True
    if candidate.startswith("ep-doubao-seedance-2"):
        return True
    return bool(re.match(r"^seedance[-_]?2(?:$|[-_.])", candidate))


SEEDANCE_DURATION_MIN_SECONDS = 4.0
SEEDANCE_DURATION_MAX_SECONDS = 15.0
SEEDANCE_2_5_DURATION_WARN_SECONDS = 30.0
_SEEDANCE_25_RE = re.compile(
    r"(?:seedance|sd)[-_\s]*2(?:\.|[-_])5(?:$|[-_\s.]|p\b)",
    re.IGNORECASE,
)


def _is_seedance_model_name(*identity_parts: Any) -> bool:
    """True when any identity part contains 'seedance' (case-insensitive)."""
    text = " ".join(str(part or "") for part in identity_parts).lower()
    return "seedance" in text


def _is_seedance25_model_name(*identity_parts: Any) -> bool:
    """True for Seedance 2.5 identities such as seedance-2.5 / sd-2.5-720p."""
    text = " ".join(str(part or "") for part in identity_parts).lower()
    return bool(text and _SEEDANCE_25_RE.search(text))


def _seedance_duration_warn_max_seconds(*identity_parts: Any) -> float:
    """UI confirm threshold only. Seedance 2.5 warns at 30s; others warn at 15s."""
    if _is_seedance25_model_name(*identity_parts):
        return SEEDANCE_2_5_DURATION_WARN_SECONDS
    return SEEDANCE_DURATION_MAX_SECONDS


def _clamp_seedance_duration(duration: Any, *identity_parts: Any) -> Tuple[Optional[float], bool]:
    """Clamp Seedance duration to the 4s minimum only.

    Maximum is not rewritten here. The frontend asks the user to confirm
    when duration exceeds 15s (or 30s for Seedance 2.5). Preserves None
    and <=0 (e.g. -1 auto).
    """
    if duration is None:
        return None, False
    try:
        value = float(duration)
    except Exception:
        return None, False
    if value <= 0:
        return value, False
    clamped = max(SEEDANCE_DURATION_MIN_SECONDS, value)
    return clamped, clamped != value


def _resolve_shot_video_duration_value(
    *,
    shot_duration: Any,
    sd2_auto_duration: bool = False,
    base_model: Optional[str] = None,
    system_api_id: Optional[int] = None,
    db: Optional[Session] = None,
) -> float:
    table_duration = 5.0
    try:
        table_duration = float(str(shot_duration or 5).strip() or 5)
    except Exception:
        table_duration = 5.0

    resolved_base_model = str(base_model or "").strip()
    resolved_api_name = ""
    resolved_api_model = ""
    if system_api_id and db is not None:
        try:
            row = db.query(SystemAPISetting).filter(SystemAPISetting.id == int(system_api_id)).first()
            if row:
                if not resolved_base_model:
                    resolved_base_model = _read_system_api_base_model_row(row)
                resolved_api_name = str(getattr(row, "name", "") or "").strip()
                resolved_api_model = str(getattr(row, "model", "") or "").strip()
        except Exception:
            pass

    if bool(sd2_auto_duration) and _is_seedance2_base_model(resolved_base_model):
        return -1.0

    identity = (resolved_base_model, resolved_api_name, resolved_api_model)
    if _is_seedance_model_name(*identity) or _is_seedance25_model_name(*identity):
        clamped, _ = _clamp_seedance_duration(table_duration, *identity)
        if clamped is not None:
            return float(clamped)
    return table_duration

