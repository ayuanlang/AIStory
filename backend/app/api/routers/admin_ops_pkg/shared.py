# -*- coding: utf-8 -*-
"""Admin ops routes extracted from endpoints megamodule (P2)."""
from __future__ import annotations

import logging
import os
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.time_utils import BEIJING_TZ, now_bj_iso
from app.db.session import get_db
from app.models.all_models import SMTPSystemConfig, SystemLog, User
from app.services.wechat_pay_config import _get_active_wechat_config
from app.schemas.admin_ops import (
    AdminExpiredDeleteRequest,
    AdminExpiredFilesOut,
    AdminExpiredRemindRequest,
    AdminStorageUsageOut,
    AdminStorageUsageUserOut,
    GenericMessageOut,
    MaintenanceConfig,
    MaintenanceStatusOut,
    PaymentConfig,
    RuntimeLogFileOut,
    RuntimeLogViewOut,
    SMTPBroadcastRequest,
    SMTPConfig,
    SMTPTestRequest,
)
from app.schemas.system_log import (
    SystemLogCreate,
    SystemLogOut,
    UiSystemLogBatchCreate,
    UiSystemLogBatchOut,
    UiSystemLogListOut,
    UiSystemLogReadEntry,
)
from app.services.auth_email import (
    _is_valid_email_format,
    _send_email_via_runtime_smtp,
)
from app.services.maintenance_status import (
    _MAINTENANCE_CATEGORY,
    _MAINTENANCE_PROVIDER,
    _build_maintenance_status_payload,
    _parse_iso_datetime_safe,
    _resolve_maintenance_config_raw,
    _store_login_maintenance_cache,
)
from app.services.payment_service import payment_service
from app.services.system_log_service import (
    append_ui_system_logs,
    get_ui_system_log_path,
    read_ui_system_logs,
)

logger = logging.getLogger("api_logger")
router = APIRouter(tags=["admin-ops"])

from app.api.routers.assets_pkg.shared import (  # noqa: E402,F401
    _collect_admin_referenced_upload_paths,
    _scan_admin_orphan_files,
)

@router.post("/fix-db-schema")
def fix_db_schema_endpoint(current_user: User = Depends(get_current_user)):
    """
    Emergency endpoint to trigger DB migration manually.
    Only accessible by authorized users (technically any logged in user for now, assuming admin).
    """
    try:
        if not current_user.is_superuser: # Basic protection if is_superuser exists
             # logger.warning(f"User {current_user.username} tried to fix DB but is not superuser")
             # pass # Loose check for now as we are desperate
             pass

        from app.db.init_db import (
            check_and_migrate_tables,
            _ensure_user_group_schema,
            inspect_user_group_schema,
        )
        from app.db.session import engine as db_engine

        logger.info(f"Manual DB Fix triggered by {current_user.username}")
        check_and_migrate_tables()
        is_postgres = getattr(db_engine.dialect, "name", "") == "postgresql"
        group_ensure = _ensure_user_group_schema(is_postgres=is_postgres)
        group_snapshot = inspect_user_group_schema()
        return {
            "message": "Migration script executed successfully. Check logs for details.",
            "user_group_schema": group_snapshot,
            "user_group_ensure": group_ensure,
        }
    except Exception as e:
        logger.error(f"Manual DB Fix failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))




@router.post("/system_logs/actions", response_model=SystemLogOut)
def create_system_log_action(
    payload: SystemLogCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    action = str(payload.action or "").strip().upper()
    if not action:
        raise HTTPException(status_code=400, detail="action is required")

    details = str(payload.details or "").strip()
    if len(details) > 16000:
        details = details[:16000]

    ip_address = str(payload.ip_address or request.client.host if request.client else "").strip() or None
    user_name = str(current_user.username or payload.user_name or f"user_{current_user.id}").strip() or f"user_{current_user.id}"

    now_iso = now_bj_iso()
    row = SystemLog(
        user_id=current_user.id,
        user_name=user_name,
        action=action,
        details=details or None,
        ip_address=ip_address,
        timestamp=now_iso,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/system_logs/ui", response_model=UiSystemLogListOut)
def list_ui_system_logs(
    limit: int = 100,
    current_user: User = Depends(get_current_user),
):
    """Read persisted frontend「系统日志」entries for the current user (max 100)."""
    safe_limit = max(1, min(int(limit or 100), 100))
    rows = read_ui_system_logs(user_id=int(current_user.id), limit=safe_limit)
    entries: list[UiSystemLogReadEntry] = []
    for row in rows:
        stamp = str(row.get("stamp") or "").strip()
        level = str(row.get("level") or "INFO").strip().upper() or "INFO"
        message = str(row.get("message") or "").strip()
        client_time = str(row.get("client_time") or "").strip() or None
        # Prefer client clock, always render in Beijing time so order matches live UI (local CST).
        display_time = ""
        if client_time:
            try:
                parsed = datetime.fromisoformat(client_time.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=BEIJING_TZ)
                display_time = parsed.astimezone(BEIJING_TZ).strftime("%H:%M:%S")
            except Exception:
                display_time = client_time[11:19] if len(client_time) >= 19 else client_time
        if not display_time and stamp:
            # Server stamp is already written as local wall time (CST).
            display_time = stamp[11:19] if len(stamp) >= 19 else stamp
        display = f"[{display_time or '--:--:--'}] [{level}] {message}".strip()
        entries.append(
            UiSystemLogReadEntry(
                stamp=stamp,
                level=level,
                message=message,
                client_time=client_time,
                display=display,
            )
        )
    return UiSystemLogListOut(
        ok=True,
        entries=entries,
        log_file=str(get_ui_system_log_path()),
    )


@router.post("/system_logs/ui", response_model=UiSystemLogBatchOut)
def persist_ui_system_logs(
    payload: UiSystemLogBatchCreate,
    current_user: User = Depends(get_current_user),
):
    """Persist frontend「系统日志」panel entries to backend/logs/user_system.log (max 100 lines)."""
    entries = list(payload.entries or [])
    if len(entries) > 100:
        entries = entries[-100:]

    user_name = str(current_user.username or f"user_{current_user.id}").strip() or f"user_{current_user.id}"
    written = append_ui_system_logs(
        [entry.model_dump() if hasattr(entry, "model_dump") else entry.dict() for entry in entries],
        user_id=int(current_user.id),
        user_name=user_name,
    )
    return UiSystemLogBatchOut(
        ok=True,
        written=int(written or 0),
        log_file=str(get_ui_system_log_path()),
    )



_RUNTIME_LOG_PREFIXES = ("app_info.log", "user_system.log")


def _is_allowed_runtime_log_filename(name: str) -> bool:
    safe_name = str(name or "").strip()
    if not safe_name or "/" in safe_name or "\\" in safe_name:
        return False
    return any(safe_name == prefix or safe_name.startswith(f"{prefix}.") for prefix in _RUNTIME_LOG_PREFIXES)


@router.get("/admin/runtime-logs/files", response_model=List[RuntimeLogFileOut])
def list_runtime_log_files(
    current_user: User = Depends(get_current_user)
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only superuser can view runtime logs")

    log_dir = Path(settings.BASE_DIR) / "logs"
    if not log_dir.exists() or not log_dir.is_dir():
        return []

    files: List[RuntimeLogFileOut] = []
    seen = set()
    candidates = []
    for prefix in _RUNTIME_LOG_PREFIXES:
        candidates.extend(log_dir.glob(f"{prefix}*"))
    for path in sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True):
        if not path.is_file() or path.name in seen or not _is_allowed_runtime_log_filename(path.name):
            continue
        seen.add(path.name)
        stat = path.stat()
        files.append(
            RuntimeLogFileOut(
                name=path.name,
                size_bytes=int(stat.st_size),
                modified_at=datetime.fromtimestamp(stat.st_mtime).isoformat(),
            )
        )
    return files


@router.get("/admin/runtime-logs/view", response_model=RuntimeLogViewOut)
def view_runtime_log_file(
    filename: str = "app_info.log",
    tail_lines: int = 300,
    user_name: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user)
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only superuser can view runtime logs")

    safe_name = str(filename or "").strip()
    if not safe_name:
        raise HTTPException(status_code=400, detail="filename is required")
    if not _is_allowed_runtime_log_filename(safe_name):
        raise HTTPException(status_code=400, detail="invalid filename")

    capped_tail = max(1, min(int(tail_lines or 300), 5000))
    log_dir = (Path(settings.BASE_DIR) / "logs").resolve()
    target = (log_dir / safe_name).resolve()

    if target.parent != log_dir:
        raise HTTPException(status_code=400, detail="invalid path")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="log file not found")

    user_name_lower = user_name.lower() if user_name else None
    action_lower = action.lower() if action else None

    line_buffer = deque(maxlen=capped_tail)
    with target.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if user_name_lower and user_name_lower not in line.lower():
                continue
            if action_lower and action_lower not in line.lower():
                continue
            if start_time or end_time:
                ts = line[:19]
                if len(ts) == 19 and ts[4] == '-' and ts[7] == '-':
                    if start_time and ts < start_time:
                        continue
                    if end_time and ts > end_time:
                        continue
            line_buffer.append(line)

    stat = target.stat()
    return RuntimeLogViewOut(
        filename=target.name,
        tail_lines=capped_tail,
        size_bytes=int(stat.st_size),
        modified_at=datetime.fromtimestamp(stat.st_mtime).isoformat(),
        content="".join(line_buffer),
    )


