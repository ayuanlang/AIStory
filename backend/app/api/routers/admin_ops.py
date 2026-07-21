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


@router.get("/admin/storage-usage", response_model=AdminStorageUsageOut)
def get_admin_storage_usage(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only superuser can view storage usage")

    upload_root = Path(settings.UPLOAD_DIR)
    if not upload_root.is_absolute():
        upload_root = (Path(settings.BASE_DIR) / upload_root).resolve()

    if not upload_root.exists() or not upload_root.is_dir():
        return AdminStorageUsageOut(
            upload_root=str(upload_root),
            total_bytes=0,
            total_files=0,
            users=[],
        )

    user_rows = db.query(User.id, User.username, User.email).all()
    user_map = {int(row.id): {"username": row.username, "email": row.email} for row in user_rows}

    usage_by_user: Dict[int, Dict[str, int]] = {}
    total_files = 0
    total_bytes = 0

    for child in upload_root.iterdir():
        if not child.is_dir():
            continue
        try:
            user_id = int(child.name)
        except Exception:
            continue

        file_count = 0
        bytes_used = 0
        for root, _, files in os.walk(child):
            for filename in files:
                path = Path(root) / filename
                try:
                    stat = path.stat()
                except Exception:
                    continue
                file_count += 1
                bytes_used += int(stat.st_size)

        usage_by_user[user_id] = {
            "file_count": file_count,
            "bytes": bytes_used,
        }
        total_files += file_count
        total_bytes += bytes_used

    users_out: List[AdminStorageUsageUserOut] = []
    for uid, stats in usage_by_user.items():
        info = user_map.get(uid) or {}
        users_out.append(
            AdminStorageUsageUserOut(
                user_id=uid,
                username=str(info.get("username") or f"user_{uid}"),
                email=info.get("email"),
                file_count=int(stats.get("file_count") or 0),
                bytes=int(stats.get("bytes") or 0),
            )
        )

    users_out.sort(key=lambda item: item.bytes, reverse=True)

    return AdminStorageUsageOut(
        upload_root=str(upload_root),
        total_bytes=int(total_bytes),
        total_files=int(total_files),
        users=users_out,
    )

@router.get("/admin/storage-usage/expired", response_model=AdminExpiredFilesOut)
def get_admin_expired_files(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only superuser can view storage usage")
    
    upload_root = Path(settings.UPLOAD_DIR)
    if not upload_root.is_absolute():
        upload_root = (Path(settings.BASE_DIR) / upload_root).resolve()
    if not upload_root.exists() or not upload_root.is_dir():
        return AdminExpiredFilesOut(files=[], total_size=0, total_count=0)

    user_rows = db.query(User.id, User.username, User.email).all()
    user_map = {int(row.id): {"username": row.username, "email": row.email} for row in user_rows}
    expired_files = []
    total_size, total_count = 0, 0
    threshold = datetime.now() - timedelta(days=60)
    threshold_ts = threshold.timestamp()

    for child in upload_root.iterdir():
        if not child.is_dir(): continue
        try: user_id = int(child.name)
        except: continue
        
        for root, _, files in os.walk(child):
            for filename in files:
                path = Path(root) / filename
                if path.is_symlink(): continue
                try: stat = path.stat()
                except: continue
                if stat.st_mtime < threshold_ts:
                    info = user_map.get(user_id, {})
                    expired_files.append({
                        "user_id": user_id,
                        "username": str(info.get("username", f"user_{user_id}")),
                        "email": info.get("email"),
                        "filepath": str(path.relative_to(upload_root)),
                        "size": int(stat.st_size),
                        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
                    total_size += stat.st_size
                    total_count += 1
                    
    expired_files.sort(key=lambda x: x["size"], reverse=True)
    return AdminExpiredFilesOut(files=expired_files, total_size=total_size, total_count=total_count)

@router.post("/admin/storage-usage/expired/remind", response_model=GenericMessageOut)
def remind_admin_expired_files(
    req: AdminExpiredRemindRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only superuser can do this")
        
    upload_root = Path(settings.UPLOAD_DIR)
    if not upload_root.is_absolute():
        upload_root = (Path(settings.BASE_DIR) / upload_root).resolve()
    if not upload_root.exists() or not upload_root.is_dir():
        return GenericMessageOut(message="No files found.")

    user_rows = db.query(User.id, User.username, User.email).all()
    user_map = {int(row.id): {"username": row.username, "email": row.email} for row in user_rows}
    threshold = datetime.now() - timedelta(days=60)
    threshold_ts = threshold.timestamp()
    
    users_to_remind = {}
    for child in upload_root.iterdir():
        if not child.is_dir(): continue
        try: user_id = int(child.name)
        except: continue
        if req.user_ids is not None and user_id not in req.user_ids:
            continue
            
        for root, _, files in os.walk(child):
            for filename in files:
                path = Path(root) / filename
                if path.is_symlink(): continue
                try: mtime = path.stat().st_mtime
                except: continue
                
                if mtime < threshold_ts:
                    info = user_map.get(user_id, {})
                    if info.get("email"):
                        if user_id not in users_to_remind:
                            users_to_remind[user_id] = {"count": 0, "size": 0, "email": info["email"]}
                        users_to_remind[user_id]["count"] += 1
                        try:
                            users_to_remind[user_id]["size"] += path.stat().st_size
                        except: pass

    reminded_count = 0
    for u_id, stats in users_to_remind.items():
        mb_size = stats["size"] / (1024*1024)
        msg_content = (
            f"<h1>Storage Lifecycle Exceeded / 超期文件清理通知</h1>"
            f"<p>Dear user / 尊敬的用户,</p>"
            f"<p>You have {stats['count']} file(s) occupying {mb_size:.2f} MB that have exceeded the 60-day storage limit.</p>"
            f"<p>您的账号中有 {stats['count']} 个文件（占用空间 {mb_size:.2f} MB）已超过 60 天存储期限。</p>"
            f"<p>Please back them up. They will be removed within 3 working days.</p>"
            f"<p>请及时备份这些文件。系统将在 3 个工作日内进行清理。</p>"
        )
        try:
            _send_email_via_runtime_smtp(
                stats["email"], 
                "Action Required: Expired Files Deletion / 需要操作：超期文件清理", 
                content="You have files exceeding the 60-day limit. Please back them up. / 您的文件已超过60天存储期限，请及时备份。", 
                html_content=msg_content
            )
            reminded_count += 1
        except Exception as e:
            logger.error(f"Failed to send reminder email to {stats['email']}: {e}")
            
    return GenericMessageOut(message=f"Reminders sent to {reminded_count} users.")

@router.post("/admin/storage-usage/expired/delete", response_model=GenericMessageOut)
def delete_admin_expired_files(
    req: AdminExpiredDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only superuser can do this")
        
    upload_root = Path(settings.UPLOAD_DIR)
    if not upload_root.is_absolute():
        upload_root = (Path(settings.BASE_DIR) / upload_root).resolve()
    if not upload_root.exists() or not upload_root.is_dir():
        return GenericMessageOut(message="No files found.")

    threshold = datetime.now() - timedelta(days=60)
    threshold_ts = threshold.timestamp()
    deleted_count = 0
    deleted_size = 0
    for child in upload_root.iterdir():
        if not child.is_dir(): continue
        try: user_id = int(child.name)
        except: continue
        if req.user_ids is not None and user_id not in (req.user_ids or []):
            continue
            
        for root, _, files in os.walk(child):
            for filename in files:
                path = Path(root) / filename
                if path.is_symlink(): continue
                try: stat = path.stat()
                except: continue
                if stat.st_mtime < threshold_ts:
                    deleted_size += stat.st_size
                    try:
                        os.remove(path)
                        deleted_count += 1
                    except:
                        pass
                        
    return GenericMessageOut(message=f"Deleted {deleted_count} files ({deleted_size / (1024*1024):.2f} MB).")


@router.get("/admin/storage-usage/orphan", response_model=AdminExpiredFilesOut)
def get_admin_orphan_files(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only superuser can view storage usage")

    upload_root = Path(settings.UPLOAD_DIR)
    if not upload_root.is_absolute():
        upload_root = (Path(settings.BASE_DIR) / upload_root).resolve()
    if not upload_root.exists() or not upload_root.is_dir():
        return AdminExpiredFilesOut(files=[], total_size=0, total_count=0)

    user_rows = db.query(User.id, User.username, User.email).all()
    user_map = {int(row.id): {"username": row.username, "email": row.email} for row in user_rows}
    from app.api import endpoints as _ep
    referenced = _ep._collect_admin_referenced_upload_paths(db)
    orphan_files, total_size, total_count = _ep._scan_admin_orphan_files(upload_root, referenced, user_map)
    return AdminExpiredFilesOut(files=orphan_files, total_size=total_size, total_count=total_count)


@router.post("/admin/storage-usage/orphan/delete", response_model=GenericMessageOut)
def delete_admin_orphan_files(
    req: AdminExpiredDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Only superuser can do this")

    upload_root = Path(settings.UPLOAD_DIR)
    if not upload_root.is_absolute():
        upload_root = (Path(settings.BASE_DIR) / upload_root).resolve()
    if not upload_root.exists() or not upload_root.is_dir():
        return GenericMessageOut(message="No files found.")

    user_rows = db.query(User.id, User.username, User.email).all()
    user_map = {int(row.id): {"username": row.username, "email": row.email} for row in user_rows}
    from app.api import endpoints as _ep
    referenced = _ep._collect_admin_referenced_upload_paths(db)
    orphan_files, _, _ = _ep._scan_admin_orphan_files(upload_root, referenced, user_map)

    deleted_count = 0
    deleted_size = 0
    allowed_user_ids = set(req.user_ids or []) if req.user_ids is not None else None
    for item in orphan_files:
        user_id = int(item.get("user_id") or 0)
        if allowed_user_ids is not None and user_id not in allowed_user_ids:
            continue

        rel_path = str(item.get("filepath") or "").strip()
        if not rel_path:
            continue

        file_path = upload_root / rel_path
        try:
            resolved = file_path.resolve()
            if os.path.commonpath([str(upload_root.resolve()), str(resolved)]) != str(upload_root.resolve()):
                continue
        except Exception:
            continue

        if not file_path.is_file() or file_path.is_symlink():
            continue

        try:
            size = int(file_path.stat().st_size)
        except Exception:
            size = 0

        try:
            os.remove(file_path)
            deleted_count += 1
            deleted_size += size
        except Exception:
            pass

    return GenericMessageOut(message=f"Deleted {deleted_count} orphan files ({deleted_size / (1024 * 1024):.2f} MB).")


@router.get("/admin/payment-config", response_model=PaymentConfig)
def get_payment_config(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    setting = _get_active_wechat_config(db)
    if not setting:
        return PaymentConfig()

    return PaymentConfig(
        mchid=str(setting.mchid or ""),
        appid=str(setting.appid or ""),
        api_v3_key=str(setting.api_v3_key or ""),
        cert_serial_no=str(setting.cert_serial_no or ""),
        private_key=str(setting.private_key or ""),
        notify_url=str(setting.notify_url or ""),
        use_mock=bool(setting.use_mock),
    )

@router.post("/admin/payment-config", response_model=PaymentConfig)
def update_payment_config(
    idx: PaymentConfig,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    setting = _get_active_wechat_config(db)
    
    if not setting:
        setting = WechatPayConfig(
            is_active=True,
            created_at=now_bj_iso(),
            updated_at=now_bj_iso(),
        )
        db.add(setting)

    setting.mchid = str(idx.mchid or "").strip()
    setting.appid = str(idx.appid or "").strip()
    setting.api_v3_key = str(idx.api_v3_key or "").strip()
    setting.cert_serial_no = str(idx.cert_serial_no or "").strip()
    setting.private_key = str(idx.private_key or "")
    setting.notify_url = str(idx.notify_url or "").strip()
    setting.use_mock = bool(idx.use_mock)
    setting.updated_at = now_bj_iso()
    
    db.commit()
    db.refresh(setting)
    
    # Update Service Immediately
    payment_service.update_config({
        "mchid": idx.mchid,
        "appid": idx.appid,
        "api_v3_key": idx.api_v3_key,
        "cert_serial_no": idx.cert_serial_no,
        "private_key": idx.private_key,
        "notify_url": idx.notify_url,
        "use_mock": idx.use_mock
    })
    
    return idx


@router.get("/admin/smtp-config", response_model=SMTPConfig)
def get_smtp_config(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")

    if not inspect(db.connection()).has_table("smtp_system_configs"):
        return SMTPConfig(
            host=str(settings.SMTP_HOST or "").strip(),
            port=int(settings.SMTP_PORT or 587),
            username=str(settings.SMTP_USERNAME or "").strip(),
            password="",
            use_ssl=os.getenv("SMTP_USE_SSL", "0") in {"1", "true", "True"},
            use_tls=bool(settings.SMTP_USE_TLS),
            from_email=str(settings.SMTP_FROM_EMAIL or "").strip(),
            frontend_base_url=str(settings.FRONTEND_BASE_URL or "").strip(),
        )

    setting = db.query(SMTPSystemConfig).filter(
        SMTPSystemConfig.is_active == True,
    ).order_by(SMTPSystemConfig.id.desc()).first()

    if not setting:
        return SMTPConfig(
            host=str(settings.SMTP_HOST or "").strip(),
            port=int(settings.SMTP_PORT or 587),
            username=str(settings.SMTP_USERNAME or "").strip(),
            password="",
            use_ssl=os.getenv("SMTP_USE_SSL", "0") in {"1", "true", "True"},
            use_tls=bool(settings.SMTP_USE_TLS),
            from_email=str(settings.SMTP_FROM_EMAIL or "").strip(),
            frontend_base_url=str(settings.FRONTEND_BASE_URL or "").strip(),
        )

    return SMTPConfig(
        host=str(setting.host or "").strip(),
        port=int(setting.port or 587),
        username=str(setting.username or "").strip(),
        password=str(setting.password or ""),
        use_ssl=bool(setting.use_ssl),
        use_tls=bool(setting.use_tls),
        from_email=str(setting.from_email or "").strip(),
        frontend_base_url=str(setting.frontend_base_url or "").strip(),
    )


@router.post("/admin/smtp-config", response_model=SMTPConfig)
def update_smtp_config(
    idx: SMTPConfig,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")

    if not inspect(db.connection()).has_table("smtp_system_configs"):
        SMTPSystemConfig.__table__.create(bind=db.get_bind(), checkfirst=True)

    setting = db.query(SMTPSystemConfig).filter(
        SMTPSystemConfig.is_active == True,
    ).order_by(SMTPSystemConfig.id.desc()).first()

    if not setting:
        setting = SMTPSystemConfig(
            is_active=True,
            created_at=now_bj_iso(),
            updated_at=now_bj_iso(),
        )
        db.add(setting)

    setting.host = str(idx.host or "").strip()
    setting.port = int(idx.port or 587)
    setting.username = str(idx.username or "").strip()
    setting.password = str(idx.password or "")
    setting.use_ssl = bool(idx.use_ssl)
    setting.use_tls = bool(idx.use_tls)
    setting.from_email = str(idx.from_email or "").strip()
    setting.frontend_base_url = str(idx.frontend_base_url or "").strip()
    setting.updated_at = now_bj_iso()

    db.commit()
    db.refresh(setting)
    return idx


@router.post("/admin/smtp-config/test")
def test_smtp_config(
    payload: SMTPTestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")

    del db
    target_email = str(payload.to_email or "").strip()
    if not target_email:
        raise HTTPException(status_code=400, detail="测试邮箱不能为空")

    subject = "AI Story SMTP 测试邮件"
    content = (
        "这是一封来自 AI Story 的 SMTP 测试邮件。\n\n"
        "如果你收到了这封邮件，说明 SMTP 配置可用。"
    )

    try:
        _send_email_via_runtime_smtp(target_email, subject, content, strict=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"发送失败：{exc}")

    return {"success": True, "message": f"测试邮件已发送到 {target_email}"}


@router.post("/admin/smtp-config/broadcast")
def broadcast_email_to_all_users(
    payload: SMTPBroadcastRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")

    if str(payload.confirm_phrase or "").strip() != "SEND_TO_ALL_USERS":
        raise HTTPException(status_code=400, detail="确认口令错误，请输入 SEND_TO_ALL_USERS")

    subject = str(payload.subject or "").strip()
    html_content = str(payload.content_html or "")
    text_content = str(payload.content_text or "").strip()

    if not subject:
        raise HTTPException(status_code=400, detail="邮件主题不能为空")

    if not html_content.strip() and not text_content:
        raise HTTPException(status_code=400, detail="邮件内容不能为空（HTML 或文本至少填写一个）")

    if not text_content:
        text_content = "This email contains HTML content. Please view it in an HTML-compatible email client."

    rows = db.query(User.email).all()
    raw_emails = [str((row[0] or "")).strip().lower() for row in rows]

    recipients = []
    invalid_count = 0
    seen = set()
    for email in raw_emails:
        if not email:
            continue
        if email in seen:
            continue
        seen.add(email)
        if _is_valid_email_format(email):
            recipients.append(email)
        else:
            invalid_count += 1

    if not recipients:
        raise HTTPException(status_code=400, detail="没有可用的收件邮箱")

    sent = 0
    failed = 0
    errors = []
    for email in recipients:
        try:
            _send_email_via_runtime_smtp(
                email,
                subject,
                text_content,
                html_content=html_content,
                strict=True,
            )
            sent += 1
        except Exception as exc:
            failed += 1
            if len(errors) < 10:
                errors.append({"email": email, "error": str(exc)})

    return {
        "success": failed == 0,
        "total": len(recipients),
        "sent": sent,
        "failed": failed,
        "invalid": invalid_count,
        "errors": errors,
    }


@router.get("/admin/maintenance-status", response_model=MaintenanceStatusOut)
def get_maintenance_status(db: Session = Depends(get_db)):
    status = _resolve_maintenance_config_raw(db)
    return MaintenanceStatusOut(**status)


@router.get("/admin/maintenance-config", response_model=MaintenanceConfig)
def get_maintenance_config(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")

    status = _resolve_maintenance_config_raw(db)
    return MaintenanceConfig(
        enabled=bool(status.get("enabled")),
        ends_at=status.get("ends_at"),
        message=status.get("message") or "系统正在维护",
    )


@router.post("/admin/maintenance-config", response_model=MaintenanceConfig)
def update_maintenance_config(
    idx: MaintenanceConfig,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not authorized")

    row = db.execute(text("""
        SELECT id
        FROM system_api_settings
        WHERE category = :category
          AND provider = :provider
        ORDER BY id DESC
        LIMIT 1
    """), {
        "category": _MAINTENANCE_CATEGORY,
        "provider": _MAINTENANCE_PROVIDER,
    }).mappings().first()

    ends_at = str(idx.ends_at or "").strip()
    if ends_at and not _parse_iso_datetime_safe(ends_at):
        raise HTTPException(status_code=400, detail="ends_at must be a valid ISO datetime")

    next_config = {
        "enabled": bool(idx.enabled),
        "ends_at": ends_at or None,
        "message": str(idx.message or "系统正在维护").strip() or "系统正在维护",
    }

    if row and row.get("id") is not None:
        db.execute(text("""
            UPDATE system_api_settings
            SET config = :config
            WHERE id = :id
        """), {
            "id": int(row["id"]),
            "config": next_config,
        })
    else:
        db.execute(text("""
            INSERT INTO system_api_settings (
                category,
                provider,
                name,
                model,
                is_active,
                config
            ) VALUES (
                :category,
                :provider,
                :name,
                :model,
                :is_active,
                :config
            )
        """), {
            "category": _MAINTENANCE_CATEGORY,
            "provider": _MAINTENANCE_PROVIDER,
            "name": "System Maintenance Config",
            "model": "maintenance_mode_config",
            "is_active": True,
            "config": next_config,
        })

    db.commit()
    _store_login_maintenance_cache(
        _build_maintenance_status_payload(next_config),
        read_failed=False,
    )

    return MaintenanceConfig(
        enabled=bool(next_config.get("enabled", False)),
        ends_at=next_config.get("ends_at"),
        message=next_config.get("message") or "系统正在维护",
    )



