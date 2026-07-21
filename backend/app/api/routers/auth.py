# -*- coding: utf-8 -*-
"""Auth / current-user profile routes (extracted from endpoints megamodule)."""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import (
    cache_user_identity,
    get_current_user,
    invalidate_cached_user_identity,
)
from app.core.config import settings
from app.db.session import get_db
from app.models.all_models import User
from app.schemas.user_auth import (
    USER_ACTIVE_LEVEL_DEFAULT,
    UserOut,
    UserPasswordUpdate,
    UserProfileUpdate,
    normalize_user_active_level,
)
from app.services.auth_security import get_password_hash, verify_password
from app.services.oss_storage_service import oss_storage_service

logger = logging.getLogger("api_logger")
router = APIRouter(tags=["auth"])


def _refresh_user_identity_cache(user, *, old_username=None) -> None:
    if user is None:
        return
    invalidate_cached_user_identity(
        user_id=int(getattr(user, "id", 0) or 0),
        username=str(old_username or "").strip(),
    )
    cache_user_identity(user)


@router.get("/users/me", response_model=UserOut)
def read_users_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current user."""
    uid = int(getattr(current_user, "id", 0) or 0)
    if uid > 0:
        try:
            db_user = db.query(User).filter(User.id == uid).first()
            if db_user is not None:
                return db_user
        except Exception as exc:
            try:
                db.rollback()
            except Exception:
                pass
            logger.warning(
                "read_users_me fallback to principal | user_id=%s error=%s",
                uid,
                type(exc).__name__,
            )

    return {
        "id": uid,
        "username": str(getattr(current_user, "username", "") or "").strip(),
        "email": getattr(current_user, "email", None),
        "full_name": getattr(current_user, "full_name", None),
        "avatar_url": getattr(current_user, "avatar_url", None),
        "is_active": normalize_user_active_level(
            getattr(current_user, "is_active", USER_ACTIVE_LEVEL_DEFAULT),
            USER_ACTIVE_LEVEL_DEFAULT,
        ),
        "account_status": int(getattr(current_user, "account_status", 1) or 1),
        "email_verified": bool(getattr(current_user, "email_verified", False)),
        "is_superuser": bool(getattr(current_user, "is_superuser", False)),
        "is_authorized": bool(getattr(current_user, "is_authorized", False)),
        "is_system": bool(getattr(current_user, "is_system", False)),
        "credits": int(getattr(current_user, "credits", 0) or 0),
    }


@router.put("/users/me/profile", response_model=UserOut)
def update_my_profile(
    payload: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.full_name is not None:
        user.full_name = (payload.full_name or "").strip() or None

    db.commit()
    db.refresh(user)
    _refresh_user_identity_cache(user)
    return user


@router.put("/users/me/password")
def update_my_password(
    payload: UserPasswordUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    new_password = (payload.new_password or "").strip()
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")

    user.hashed_password = get_password_hash(new_password)
    db.commit()
    return {"status": "success", "message": "Password updated"}


@router.post("/users/me/avatar", response_model=UserOut)
async def update_my_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    ext = (Path(file.filename or "").suffix or "").lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise HTTPException(status_code=400, detail="Avatar must be .jpg, .jpeg, .png or .webp")

    max_avatar_bytes = max(int(settings.MAX_AVATAR_UPLOAD_MB or 5), 1) * 1024 * 1024

    upload_root = settings.UPLOAD_DIR
    avatar_dir = os.path.join(upload_root, str(current_user.id), "avatars")
    os.makedirs(avatar_dir, exist_ok=True)

    filename = f"avatar_{uuid.uuid4().hex[:10]}{ext}"
    save_path = os.path.join(avatar_dir, filename)

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty avatar file")
    if len(content) > max_avatar_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Avatar file too large (max {settings.MAX_AVATAR_UPLOAD_MB}MB)",
        )

    oss_url = None
    if oss_storage_service.is_enabled(db):
        try:
            oss_res = oss_storage_service.upload_bytes(
                content,
                user_id=current_user.id,
                filename=filename,
                content_type=file.content_type or f"image/{ext.lstrip('.')}",
                category="avatars",
            )
            if oss_res and oss_res.get("url"):
                oss_url = oss_res.get("url")
        except Exception as e:
            logger.warning("OSS upload failed for avatar: %s", e)

    if oss_url:
        user.avatar_url = oss_url
    else:
        def _write_avatar():
            with open(save_path, "wb") as f:
                f.write(content)

        await asyncio.to_thread(_write_avatar)
        relative_path = os.path.relpath(save_path, upload_root).replace("\\", "/")
        user.avatar_url = f"/uploads/{relative_path}"

    db.commit()
    db.refresh(user)
    _refresh_user_identity_cache(user)
    return user

from app.api.routers.auth_session import router as _auth_session_router
router.include_router(_auth_session_router)
