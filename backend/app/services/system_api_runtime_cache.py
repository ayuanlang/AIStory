import os
import time
import threading
import json
import logging
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from app.db.session import SessionLocal
from app.models.all_models import SystemAPISetting

logger = logging.getLogger(__name__)

_SYSTEM_API_CACHE_TTL_SECONDS = int(os.getenv("SYSTEM_API_CACHE_TTL_SECONDS", "30") or 30)
_SYSTEM_API_CACHE_MAX_ROW_BYTES = max(
    4096,
    int(os.getenv("SYSTEM_API_CACHE_MAX_ROW_BYTES", str(64 * 1024)) or (64 * 1024)),
)
_SYSTEM_API_CACHE_LOCK = threading.Lock()
_SYSTEM_API_CACHE: Dict[str, Any] = {
    "loaded_at": 0.0,
    "rows": [],
    "by_id": {},
    "source_row_count": 0,
    "skipped_rows": 0,
}


def _estimate_payload_bytes(value: Any) -> int:
    try:
        payload = json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        payload = str(value)
    return len(payload.encode("utf-8", errors="ignore"))


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
    normalized: List[Dict[str, Any]] = []
    skipped_rows = 0
    source_row_count = len(rows)

    for row in rows:
        normalized_row = _row_to_dict(row)
        if _estimate_payload_bytes(normalized_row) > _SYSTEM_API_CACHE_MAX_ROW_BYTES:
            skipped_rows += 1
            continue
        normalized.append(normalized_row)

    by_id = {int(r["id"]): r for r in normalized if int(r.get("id") or 0) > 0}
    return {
        "loaded_at": time.time(),
        "rows": normalized,
        "by_id": by_id,
        "source_row_count": source_row_count,
        "skipped_rows": skipped_rows,
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
        skipped = int(state.get("skipped_rows") or 0)
        if skipped > 0:
            logger.warning(
                "system api runtime cache skipped oversized rows | skipped=%s total=%s max_row_bytes=%s",
                skipped,
                int(state.get("source_row_count") or len(rows)),
                _SYSTEM_API_CACHE_MAX_ROW_BYTES,
            )
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
        _SYSTEM_API_CACHE["source_row_count"] = 0
        _SYSTEM_API_CACHE["skipped_rows"] = 0

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
