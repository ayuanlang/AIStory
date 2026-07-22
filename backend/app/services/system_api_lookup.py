# -*- coding: utf-8 -*-
"""System API setting lookup helpers."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models.all_models import SystemAPISetting
from app.services.system_api_runtime_cache import resolve_system_api_cached


def get_system_api_setting(
    db: Session,
    provider: str = None,
    category: str = None,
    model: str = None,
    setting_id: int = None,
) -> Optional[SystemAPISetting]:
    """Helper to find a system-level API configuration by exact filters."""
    cached = resolve_system_api_cached(
        setting_id=setting_id,
        provider=provider,
        category=category,
        model=model,
    )
    if cached is not None:
        return cached

    query = db.query(SystemAPISetting)
    if setting_id:
        query = query.filter(SystemAPISetting.id == setting_id)
    if provider:
        query = query.filter(SystemAPISetting.provider == provider)
    if category:
        query = query.filter(SystemAPISetting.category == category)
    if model:
        query = query.filter(SystemAPISetting.model == model)
    return query.order_by(SystemAPISetting.id.desc()).first()


