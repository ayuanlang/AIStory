# -*- coding: utf-8 -*-
"""Generation result filename helpers."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.all_models import Shot


def _sanitize_filename_part(value: Optional[str], max_len: int = 48) -> str:
    if not value:
        return ""
    cleaned = re.sub(r'[\\/:*?"<>|]+', ' ', str(value))
    cleaned = re.sub(r'\s+', '_', cleaned).strip('._- ')
    cleaned = re.sub(r'_+', '_', cleaned)
    return cleaned[:max_len]


def _build_generation_filename_base(req: Any, db: Session) -> str:
    parts: List[str] = []

    asset_type = _sanitize_filename_part(getattr(req, "asset_type", None), 24)
    if asset_type:
        parts.append(asset_type)

    # Keep shot number in filename for stable traceability across generations.
    shot_number_label = getattr(req, "shot_number", None)
    shot_name_label = getattr(req, "shot_name", None)
    if (not shot_number_label or not shot_name_label) and getattr(req, "shot_id", None):
        shot_obj = db.query(Shot).filter(Shot.id == req.shot_id).first()
        if shot_obj:
            if not shot_number_label:
                shot_number_label = shot_obj.shot_id
            if not shot_name_label:
                shot_name_label = shot_obj.shot_name

    shot_number_part = _sanitize_filename_part(shot_number_label)
    shot_name_part = _sanitize_filename_part(shot_name_label)
    if shot_number_part and shot_name_part and shot_name_part != shot_number_part:
        shot_part = f"{shot_number_part}_{shot_name_part}"
    else:
        shot_part = shot_number_part or shot_name_part

    if shot_part:
        parts.append(f"shot_{shot_part}")

    subject_label = getattr(req, "subject_name", None) or getattr(req, "entity_name", None)
    subject_part = _sanitize_filename_part(subject_label)
    if subject_part:
        parts.append(f"subject_{subject_part}")

    return "_".join(parts) if parts else "gen"


def _build_persist_filename_base_from_context(req_context: Dict[str, Any], db: Session) -> str:
    class _GenerationFilenameContext:
        def __init__(self, context: Dict[str, Any]):
            self._context = context if isinstance(context, dict) else {}

        def __getattr__(self, name: str) -> Any:
            return self._context.get(name)

    return _build_generation_filename_base(_GenerationFilenameContext(req_context), db)

