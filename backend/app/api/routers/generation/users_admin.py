# -*- coding: utf-8 -*-
"""Generation section routes — symbols pulled from shared module."""
from __future__ import annotations

from app.api.routers.generation import shared as _shared

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


# --- User Management ---
# /users/me* routes live in app.api.routers.auth

@router.get("/users", response_model=List[UserOut])
def get_users(
    skip: int = 0, 
    limit: int = 100, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    users = db.query(User).offset(skip).limit(limit).all()
    return users


@router.get("/users/page", response_model=UserPageOut)
def get_users_page(
    page: int = 1,
    page_size: int = 20,
    q: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    safe_page = max(int(page or 1), 1)
    safe_page_size = max(1, min(int(page_size or 20), 200))
    skip = (safe_page - 1) * safe_page_size
    keyword = str(q or "").strip()

    def _cached_entry_matches(entry: dict) -> bool:
        if not keyword:
            return True
        needle = keyword.casefold()
        username = str(entry.get("username") or "").casefold()
        full_name = str(entry.get("full_name") or "").casefold()
        user_id = str(entry.get("id") or "")
        return needle in username or needle in full_name or needle in user_id

    try:
        query = db.query(User)
        if keyword:
            like_pattern = f"%{keyword}%"
            filters = [
                User.username.ilike(like_pattern),
                User.full_name.ilike(like_pattern),
                cast(User.id, String).ilike(like_pattern),
            ]
            if keyword.isdigit():
                filters.append(User.id == int(keyword))
            query = query.filter(or_(*filters))
        total = int(query.count())
        items = (
            query
            .order_by(User.id.asc())
            .offset(skip)
            .limit(safe_page_size)
            .all()
        )
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        logger.warning("get_users_page fallback to cached principals | user_id=%s error=%s", getattr(current_user, "id", None), type(exc).__name__)
        cached_entries = [entry for entry in list_cached_user_entries() if _cached_entry_matches(entry)]
        total = len(cached_entries)
        window = cached_entries[skip: skip + safe_page_size]
        items = [
            {
                "id": int(entry.get("id") or 0),
                "username": str(entry.get("username") or ""),
                "email": entry.get("email"),
                "full_name": entry.get("full_name"),
                "avatar_url": entry.get("avatar_url"),
                "is_active": _normalize_user_active_level(entry.get("is_active", USER_ACTIVE_LEVEL_DEFAULT), USER_ACTIVE_LEVEL_DEFAULT),
                "account_status": int(entry.get("account_status") or 1),
                "email_verified": bool(entry.get("email_verified", False)),
                "is_superuser": bool(entry.get("is_superuser", False)),
                "is_authorized": bool(entry.get("is_authorized", False)),
                "is_system": bool(entry.get("is_system", False)),
                "credits": int(entry.get("credits", 0) or 0),
            }
            for entry in window
        ]
    return {
        "items": items,
        "total": total,
        "page": safe_page,
        "page_size": safe_page_size,
    }

@router.put("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int, 
    user_in: UserUpdate, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    def _persist_update():
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        old_username = str(getattr(user, "username", "") or "").strip()

        if user_in.username is not None:
            next_username = (user_in.username or "").strip()
            if not next_username:
                raise HTTPException(status_code=400, detail="Username cannot be empty")
            dup = db.query(User).filter(User.username == next_username, User.id != user_id).first()
            if dup:
                raise HTTPException(status_code=400, detail="Username already registered")
            user.username = next_username

        if user_in.email is not None:
            next_email = (user_in.email or "").strip().lower()
            if not _is_valid_email_format(next_email):
                raise HTTPException(status_code=400, detail="Invalid email format")
            dup = db.query(User).filter(User.email == next_email, User.id != user_id).first()
            if dup:
                raise HTTPException(status_code=400, detail="Email already registered")
            user.email = next_email

        if user_in.full_name is not None:
            user.full_name = (user_in.full_name or "").strip() or None

        if user_in.is_active is not None:
            user.is_active = _normalize_user_active_level(user_in.is_active, USER_ACTIVE_LEVEL_DEFAULT)
        if user_in.account_status is not None:
            user.account_status = int(user_in.account_status)
            if user.account_status == -1:
                user.is_active = 0
                user.email_verified = False
        if user_in.email_verified is not None:
            user.email_verified = bool(user_in.email_verified)
            if user.email_verified and user.account_status == -1:
                user.account_status = 1
                if not _is_user_enabled(user.is_active):
                    user.is_active = USER_ACTIVE_LEVEL_DEFAULT
        if user_in.is_authorized is not None:
            user.is_authorized = user_in.is_authorized
        if user_in.is_superuser is not None:
            user.is_superuser = user_in.is_superuser
        if user_in.is_system is not None:
            if user_in.is_system:
                db.query(User).filter(User.id != user_id).update({"is_system": False})
            user.is_system = user_in.is_system

        if user_in.password:
            user.hashed_password = get_password_hash(user_in.password)

        db.commit()
        db.refresh(user)
        _refresh_user_identity_cache(user, old_username=old_username)
        return user

    return _run_with_schema_self_heal(db, _persist_update, context="update_user")


