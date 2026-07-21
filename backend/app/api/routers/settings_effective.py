# -*- coding: utf-8 -*-
"""Effective API setting snapshot route."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.all_models import User
from app.services.effective_api_setting import _resolve_effective_api_setting_meta

logger = logging.getLogger("api_logger")
router = APIRouter(tags=["settings-effective"])


@router.get("/settings/effective")
def get_effective_setting_snapshot(
    category: str = "LLM",
    provider: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resolved_setting, source, meta = _resolve_effective_api_setting_meta(
        db,
        current_user,
        provider=provider,
        category=category,
    )

    if not resolved_setting:
        return {
            "found": False,
            "category": category,
            "provider": provider,
            "source": source,
            "meta": meta,
        }

    api_key = (resolved_setting.api_key or "").strip()
    masked = ""
    if api_key:
        masked = api_key[:4] + "***" + api_key[-4:] if len(api_key) > 8 else ("*" * len(api_key))

    return {
        "found": True,
        "source": source,
        "selection_source": "system_only",
        "setting_id": resolved_setting.id,
        "owner_user_id": getattr(resolved_setting, "user_id", None),
        "category": resolved_setting.category,
        "provider": resolved_setting.provider,
        "model": resolved_setting.model,
        "endpoint": resolved_setting.base_url,
        "webhook": (resolved_setting.config or {}).get("webHook"),
        "has_api_key": bool(api_key),
        "api_key_masked": masked,
        "meta": meta,
    }
