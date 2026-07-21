# -*- coding: utf-8 -*-
"""Login/admin maintenance-mode status cache (shared)."""
from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime
import json
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import all_models as models

logger = logging.getLogger("api_logger")
SystemAPISetting = models.SystemAPISetting

_MAINTENANCE_CATEGORY = "System_Maintenance"
_MAINTENANCE_PROVIDER = "maintenance_mode"
_LOGIN_MAINTENANCE_CACHE_TTL_SECONDS = max(5.0, float(os.getenv("LOGIN_MAINTENANCE_CACHE_TTL_SECONDS", "15") or 15.0))
_LOGIN_MAINTENANCE_FAILURE_COOLDOWN_SECONDS = max(_LOGIN_MAINTENANCE_CACHE_TTL_SECONDS, float(os.getenv("LOGIN_MAINTENANCE_FAILURE_COOLDOWN_SECONDS", "60") or 60.0))
_LOGIN_MAINTENANCE_FAILURE_CIRCUIT_THRESHOLD = max(1, int(os.getenv("LOGIN_MAINTENANCE_FAILURE_CIRCUIT_THRESHOLD", "2") or 2))
_LOGIN_MAINTENANCE_FAILURE_CIRCUIT_OPEN_SECONDS = max(_LOGIN_MAINTENANCE_FAILURE_COOLDOWN_SECONDS, float(os.getenv("LOGIN_MAINTENANCE_FAILURE_CIRCUIT_OPEN_SECONDS", "600") or 600.0))
_LOGIN_MAINTENANCE_CACHE_LOCK = threading.Lock()
_LOGIN_MAINTENANCE_CACHE = {
    "checked_at": 0.0,
    "last_read_failed": False,
    "consecutive_failures": 0,
    "circuit_open_until": 0.0,
    "refresh_in_progress": False,
    "status": {
        "enabled": False,
        "is_active": False,
        "ends_at": None,
        "message": "系统正在维护",
    },
}


def _default_maintenance_status_payload() -> Dict[str, Any]:
    return {
        "enabled": False,
        "is_active": False,
        "ends_at": None,
        "message": "系统正在维护",
    }


def _parse_iso_datetime_safe(value: Any) -> Optional[datetime]:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        normalized = raw.replace("Z", "+00:00") if raw.endswith("Z") else raw
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is not None:
            return dt.astimezone().replace(tzinfo=None)
        return dt
    except Exception:
        return None


def _build_maintenance_status_payload(cfg_raw: Any) -> Dict[str, Any]:
    if isinstance(cfg_raw, dict):
        cfg = dict(cfg_raw)
    elif isinstance(cfg_raw, str) and cfg_raw.strip():
        try:
            parsed = json.loads(cfg_raw)
            cfg = dict(parsed) if isinstance(parsed, dict) else {}
        except Exception:
            cfg = {}
    else:
        cfg = {}

    enabled = bool(cfg.get("enabled", False))
    ends_at_raw = str(cfg.get("ends_at") or "").strip()
    message = str(cfg.get("message") or "").strip()
    if not message:
        message = "系统正在维护"

    ends_at_dt = _parse_iso_datetime_safe(ends_at_raw)
    is_active = bool(enabled and (not ends_at_dt or datetime.utcnow() < ends_at_dt))

    return {
        "enabled": enabled,
        "is_active": is_active,
        "ends_at": ends_at_raw or None,
        "message": message,
    }


def _store_login_maintenance_cache(status: Dict[str, Any], *, read_failed: bool, checked_at: Optional[float] = None) -> Dict[str, Any]:
    now_ts = float(checked_at or time.time())
    normalized = {
        "enabled": bool(status.get("enabled", False)),
        "is_active": bool(status.get("is_active", False)),
        "ends_at": status.get("ends_at"),
        "message": str(status.get("message") or "系统正在维护").strip() or "系统正在维护",
    }
    with _LOGIN_MAINTENANCE_CACHE_LOCK:
        _LOGIN_MAINTENANCE_CACHE["status"] = normalized
        _LOGIN_MAINTENANCE_CACHE["last_read_failed"] = bool(read_failed)
        if read_failed:
            failures = int(_LOGIN_MAINTENANCE_CACHE.get("consecutive_failures", 0)) + 1
            _LOGIN_MAINTENANCE_CACHE["consecutive_failures"] = failures
            if failures >= _LOGIN_MAINTENANCE_FAILURE_CIRCUIT_THRESHOLD:
                _LOGIN_MAINTENANCE_CACHE["circuit_open_until"] = now_ts + _LOGIN_MAINTENANCE_FAILURE_CIRCUIT_OPEN_SECONDS
        else:
            _LOGIN_MAINTENANCE_CACHE["consecutive_failures"] = 0
            _LOGIN_MAINTENANCE_CACHE["circuit_open_until"] = 0.0
        _LOGIN_MAINTENANCE_CACHE["checked_at"] = now_ts
    return normalized


def _resolve_maintenance_config_raw(db: Session) -> Dict[str, Any]:
    row = db.execute(text("""
        SELECT config
        FROM system_api_settings
        WHERE category = :category
          AND provider = :provider
        ORDER BY id DESC
        LIMIT 1
    """), {
        "category": _MAINTENANCE_CATEGORY,
        "provider": _MAINTENANCE_PROVIDER,
    }).mappings().first()

    return _build_maintenance_status_payload(row.get("config") if row else None)


def _refresh_login_maintenance_cache_sync() -> Dict[str, Any]:
    started_at = time.perf_counter()
    try:
        with SessionLocal() as maintenance_db:
            status = _resolve_maintenance_config_raw(maintenance_db)
        cached = _store_login_maintenance_cache(status, read_failed=False)
        logger.info(
            "[login] maintenance cache refreshed | is_active=%s elapsed_ms=%s",
            bool(cached.get("is_active", False)),
            int((time.perf_counter() - started_at) * 1000),
        )
        return cached
    except Exception as exc:
        cached = _store_login_maintenance_cache(_default_maintenance_status_payload(), read_failed=True)
        logger.warning(
            "[login] maintenance cache refresh failed | elapsed_ms=%s error=%s",
            int((time.perf_counter() - started_at) * 1000),
            exc,
        )
        return cached


def _schedule_login_maintenance_cache_refresh() -> None:
    should_start = False
    with _LOGIN_MAINTENANCE_CACHE_LOCK:
        if not bool(_LOGIN_MAINTENANCE_CACHE.get("refresh_in_progress", False)):
            _LOGIN_MAINTENANCE_CACHE["refresh_in_progress"] = True
            should_start = True
    if not should_start:
        return

    def _runner() -> None:
        try:
            _refresh_login_maintenance_cache_sync()
        finally:
            with _LOGIN_MAINTENANCE_CACHE_LOCK:
                _LOGIN_MAINTENANCE_CACHE["refresh_in_progress"] = False

    refresh_thread = threading.Thread(
        target=_runner,
        name="login-maintenance-cache-refresh",
        daemon=True,
    )
    refresh_thread.start()


def _get_login_maintenance_status_cached() -> Dict[str, Any]:
    now_ts = time.time()
    with _LOGIN_MAINTENANCE_CACHE_LOCK:
        status = dict(_LOGIN_MAINTENANCE_CACHE.get("status") or _default_maintenance_status_payload())
        circuit_open_until = float(_LOGIN_MAINTENANCE_CACHE.get("circuit_open_until", 0.0) or 0.0)
        checked_at = float(_LOGIN_MAINTENANCE_CACHE.get("checked_at", 0.0) or 0.0)
        last_read_failed = bool(_LOGIN_MAINTENANCE_CACHE.get("last_read_failed", False))

    if now_ts >= circuit_open_until:
        cached_ttl = (
            _LOGIN_MAINTENANCE_FAILURE_COOLDOWN_SECONDS
            if last_read_failed
            else _LOGIN_MAINTENANCE_CACHE_TTL_SECONDS
        )
        if (now_ts - checked_at) > cached_ttl:
            _schedule_login_maintenance_cache_refresh()

    return status


