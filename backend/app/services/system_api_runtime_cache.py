import os
import time
import threading
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from app.db.session import SessionLocal
from app.models.all_models import SystemAPISetting

_SYSTEM_API_CACHE_TTL_SECONDS = int(os.getenv("SYSTEM_API_CACHE_TTL_SECONDS", "30") or 30)
_SYSTEM_API_CACHE_LOCK = threading.Lock()
_SYSTEM_API_CACHE: Dict[str, Any] = {
    "loaded_at": 0.0,
    "rows": [],
    "by_id": {},
}


def _row_to_dict(row: SystemAPISetting) -> Dict[str, Any]:
    return {
        "id": int(getattr(row, "id", 0) or 0),
        "name": str(getattr(row, "name", "") or ""),
        "category": str(getattr(row, "category", "") or ""),
        "provider": str(getattr(row, "provider", "") or ""),
        "model": str(getattr(row, "model", "") or ""),
        "base_url": str(getattr(row, "base_url", "") or ""),
        "api_key": str(getattr(row, "api_key", "") or ""),
        "deprecated": bool(getattr(row, "deprecated", False)),
        "is_active": bool(getattr(row, "is_active", False)),
        "config": getattr(row, "config", {}) or {},
        "modality": getattr(row, "modality", {}) or {},
        "tags": getattr(row, "tags", []) or [],
    }


def _rows_to_state(rows: List[SystemAPISetting]) -> Dict[str, Any]:
    normalized = [_row_to_dict(r) for r in rows]
    by_id = {int(r["id"]): r for r in normalized if int(r.get("id") or 0) > 0}
    return {
        "loaded_at": time.time(),
        "rows": normalized,
        "by_id": by_id,
    }


def refresh_system_api_cache() -> int:
    session = SessionLocal()
    try:
        rows = (
            session.query(SystemAPISetting)
            .order_by(SystemAPISetting.id.desc())
            .all()
        )
        state = _rows_to_state(rows)
        with _SYSTEM_API_CACHE_LOCK:
            _SYSTEM_API_CACHE.update(state)
        return len(state["rows"])
    finally:
        session.close()


def _cache_is_fresh() -> bool:
    with _SYSTEM_API_CACHE_LOCK:
        loaded_at = float(_SYSTEM_API_CACHE.get("loaded_at") or 0.0)
    return (time.time() - loaded_at) <= max(1, _SYSTEM_API_CACHE_TTL_SECONDS)


def warm_system_api_cache() -> int:
    if _cache_is_fresh():
        with _SYSTEM_API_CACHE_LOCK:
            return len(_SYSTEM_API_CACHE.get("rows") or [])
    try:
        return refresh_system_api_cache()
    except Exception:
        with _SYSTEM_API_CACHE_LOCK:
            return len(_SYSTEM_API_CACHE.get("rows") or [])


def invalidate_system_api_cache(*, refresh: bool = False) -> int:
    with _SYSTEM_API_CACHE_LOCK:
        _SYSTEM_API_CACHE["loaded_at"] = 0.0
        _SYSTEM_API_CACHE["rows"] = []
        _SYSTEM_API_CACHE["by_id"] = {}

    if not refresh:
        return 0

    try:
        return refresh_system_api_cache()
    except Exception:
        return 0


def resolve_system_api_cached(
    *,
    setting_id: Optional[int] = None,
    provider: Optional[str] = None,
    category: Optional[str] = None,
    model: Optional[str] = None,
) -> Optional[SimpleNamespace]:
    warm_system_api_cache()

    with _SYSTEM_API_CACHE_LOCK:
        rows = list(_SYSTEM_API_CACHE.get("rows") or [])
        by_id = dict(_SYSTEM_API_CACHE.get("by_id") or {})

    if setting_id:
        entry = by_id.get(int(setting_id))
        return SimpleNamespace(**entry) if entry else None

    provider = str(provider or "").strip()
    category = str(category or "").strip()
    model = str(model or "").strip()

    for entry in rows:
        if provider and str(entry.get("provider") or "") != provider:
            continue
        if category and str(entry.get("category") or "") != category:
            continue
        if model and str(entry.get("model") or "") != model:
            continue
        return SimpleNamespace(**entry)

    return None
