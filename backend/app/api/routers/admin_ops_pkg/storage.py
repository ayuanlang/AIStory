# -*- coding: utf-8 -*-
"""Section routes — symbols pulled from shared module."""
from __future__ import annotations

from app.api.routers.admin_ops_pkg import shared as _shared

router = _shared.router
globals().update(
    {
        k: v
        for k, v in vars(_shared).items()
        if k
        not in {
            "__name__",
            "__file__",
            "__package__",
            "__loader__",
            "__spec__",
            "__doc__",
            "__builtins__",
        }
    }
)


# --- admin storage ---
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


