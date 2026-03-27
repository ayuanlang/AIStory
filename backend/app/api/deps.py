from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
import logging
import os
import time
import threading
from types import SimpleNamespace
from app.core.config import settings
from app.db.session import get_db
from app.models.all_models import User

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/login/access-token")

_USER_AUTH_CACHE_TTL_SECONDS = int(os.getenv("USER_AUTH_CACHE_TTL_SECONDS", "45") or 45)
_USER_AUTH_CACHE_STALE_GRACE_SECONDS = int(os.getenv("USER_AUTH_CACHE_STALE_GRACE_SECONDS", "600") or 600)
_USER_AUTH_CACHE_MAX_ENTRIES = int(os.getenv("USER_AUTH_CACHE_MAX_ENTRIES", "2048") or 2048)
_user_auth_cache_lock = threading.Lock()
_user_auth_cache = {
    "by_username": {},
    "by_uid": {},
}


def _normalize_user_active_level(value, default: int = 1) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = int(default)
    return max(0, parsed)


def _is_user_enabled(value) -> bool:
    return _normalize_user_active_level(value, 1) > 0


def _build_cached_principal(user: User) -> dict:
    now = time.time()
    email_value = getattr(user, "email", None)
    if email_value is not None:
        email_value = str(email_value).strip() or None
    full_name_value = getattr(user, "full_name", None)
    if full_name_value is not None:
        full_name_value = str(full_name_value).strip() or None
    avatar_value = getattr(user, "avatar_url", None)
    if avatar_value is not None:
        avatar_value = str(avatar_value).strip() or None
    return {
        "id": int(getattr(user, "id", 0) or 0),
        "username": str(getattr(user, "username", "") or "").strip(),
        "email": email_value,
        "full_name": full_name_value,
        "avatar_url": avatar_value,
        "is_active": _normalize_user_active_level(getattr(user, "is_active", 1), 1),
        "is_superuser": bool(getattr(user, "is_superuser", False)),
        "is_authorized": bool(getattr(user, "is_authorized", False)),
        "is_system": bool(getattr(user, "is_system", False)),
        "account_status": int(getattr(user, "account_status", 1) or 1),
        "email_verified": bool(getattr(user, "email_verified", False)),
        "credits": int(getattr(user, "credits", 0) or 0),
        "cached_at": now,
        "expires_at": now + max(1, _USER_AUTH_CACHE_TTL_SECONDS),
        "stale_until": now + max(1, _USER_AUTH_CACHE_TTL_SECONDS + _USER_AUTH_CACHE_STALE_GRACE_SECONDS),
    }


def _build_cached_principal_from_payload(payload: dict) -> dict:
    now = time.time()
    email_value = payload.get("email")
    if email_value is not None:
        email_value = str(email_value).strip() or None
    full_name_value = payload.get("full_name")
    if full_name_value is not None:
        full_name_value = str(full_name_value).strip() or None
    avatar_value = payload.get("avatar_url")
    if avatar_value is not None:
        avatar_value = str(avatar_value).strip() or None
    return {
        "id": int(payload.get("uid") or payload.get("id") or 0),
        "username": str(payload.get("sub") or payload.get("uname") or "").strip(),
        "email": email_value,
        "full_name": full_name_value,
        "avatar_url": avatar_value,
        "is_active": _normalize_user_active_level(payload.get("is_active", 1), 1),
        "is_superuser": bool(payload.get("is_superuser", False)),
        "is_authorized": bool(payload.get("is_authorized", False)),
        "is_system": bool(payload.get("is_system", False)),
        "account_status": int(payload.get("account_status") or 1),
        "email_verified": bool(payload.get("email_verified", False)),
        "credits": int(payload.get("credits", 0) or 0),
        "cached_at": now,
        "expires_at": now + max(1, _USER_AUTH_CACHE_TTL_SECONDS),
        "stale_until": now + max(1, _USER_AUTH_CACHE_TTL_SECONDS + _USER_AUTH_CACHE_STALE_GRACE_SECONDS),
        "source": "token",
    }


def _cache_user_entry(entry: dict) -> None:
    username = str(entry.get("username") or "").strip()
    uid = int(entry.get("id") or 0)
    if not username or uid <= 0:
        return

    with _user_auth_cache_lock:
        _user_auth_cache["by_username"][username] = entry
        _user_auth_cache["by_uid"][uid] = entry

        # Keep cache bounded.
        by_username = _user_auth_cache["by_username"]
        if len(by_username) > _USER_AUTH_CACHE_MAX_ENTRIES:
            oldest = sorted(
                by_username.items(),
                key=lambda kv: float(kv[1].get("cached_at") or 0.0),
            )[: max(1, len(by_username) - _USER_AUTH_CACHE_MAX_ENTRIES)]
            for key, old_entry in oldest:
                by_username.pop(key, None)
                old_uid = int(old_entry.get("id") or 0)
                if old_uid > 0:
                    _user_auth_cache["by_uid"].pop(old_uid, None)


def cache_user_identity(user: User) -> None:
    """Warm auth cache from a trusted DB user row (e.g., after login)."""
    try:
        _cache_user_entry(_build_cached_principal(user))
    except Exception:
        # Never block auth flow due to cache failure.
        return


def invalidate_cached_user_identity(*, user_id: int = 0, username: str = "") -> None:
    normalized_username = str(username or "").strip()
    normalized_uid = int(user_id or 0)
    with _user_auth_cache_lock:
        if normalized_username:
            entry = _user_auth_cache["by_username"].pop(normalized_username, None)
            if entry is not None and normalized_uid <= 0:
                try:
                    normalized_uid = int(entry.get("id") or 0)
                except Exception:
                    normalized_uid = 0
        if normalized_uid > 0:
            entry = _user_auth_cache["by_uid"].pop(normalized_uid, None)
            if entry is not None and not normalized_username:
                cached_username = str(entry.get("username") or "").strip()
                if cached_username:
                    _user_auth_cache["by_username"].pop(cached_username, None)


def list_cached_user_entries() -> list[dict]:
    now = time.time()
    with _user_auth_cache_lock:
        rows = []
        for entry in _user_auth_cache["by_uid"].values():
            if not entry:
                continue
            if now > float(entry.get("stale_until") or 0.0):
                continue
            rows.append(dict(entry))
    rows.sort(key=lambda item: int(item.get("id") or 0))
    return rows


def _entry_to_principal(entry: dict) -> SimpleNamespace:
    email_value = entry.get("email")
    if email_value is not None:
        email_value = str(email_value).strip() or None
    full_name_value = entry.get("full_name")
    if full_name_value is not None:
        full_name_value = str(full_name_value).strip() or None
    avatar_value = entry.get("avatar_url")
    if avatar_value is not None:
        avatar_value = str(avatar_value).strip() or None
    return SimpleNamespace(
        id=int(entry.get("id") or 0),
        username=str(entry.get("username") or ""),
        email=email_value,
        full_name=full_name_value,
        avatar_url=avatar_value,
        is_active=_normalize_user_active_level(entry.get("is_active", 1), 1),
        is_superuser=bool(entry.get("is_superuser", False)),
        is_authorized=bool(entry.get("is_authorized", False)),
        is_system=bool(entry.get("is_system", False)),
        account_status=int(entry.get("account_status") or 1),
        email_verified=bool(entry.get("email_verified", False)),
        credits=int(entry.get("credits") or 0),
    )


def _read_cached_entry(username: str, uid: int = 0) -> dict:
    now = time.time()
    with _user_auth_cache_lock:
        entry = None
        if uid > 0:
            entry = _user_auth_cache["by_uid"].get(uid)
        if entry is None and username:
            entry = _user_auth_cache["by_username"].get(username)
        if not entry:
            return {}

        # If username changed in token/lookup path, treat as cache miss.
        cached_username = str(entry.get("username") or "").strip()
        if username and cached_username and cached_username != username:
            return {}

        # Hard-expire cache entries outside stale window.
        if now > float(entry.get("stale_until") or 0.0):
            if cached_username:
                _user_auth_cache["by_username"].pop(cached_username, None)
            cached_uid = int(entry.get("id") or 0)
            if cached_uid > 0:
                _user_auth_cache["by_uid"].pop(cached_uid, None)
            return {}

        return dict(entry)


def warm_user_auth_cache_from_db(limit: int = 2000) -> int:
    """Preload active users into in-memory auth cache to reduce cold-start DB bursts."""
    try:
        from app.db.session import SessionLocal
        from app.models.all_models import User as UserModel

        session = SessionLocal()
        try:
            rows = (
                session.query(UserModel)
                .filter(UserModel.is_active > 0)
                .order_by(UserModel.id.desc())
                .limit(max(1, int(limit or 2000)))
                .all()
            )
            count = 0
            for row in rows:
                _cache_user_entry(_build_cached_principal(row))
                count += 1
            return count
        finally:
            session.close()
    except Exception:
        return 0

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        uid_raw = payload.get("uid")
        try:
            token_uid = int(uid_raw) if uid_raw is not None else 0
        except Exception:
            token_uid = 0
    except JWTError:
        raise credentials_exception

    token_principal_entry = {}
    if int(payload.get("pv") or 0) == 1:
        token_principal_entry = _build_cached_principal_from_payload(payload)
        if token_principal_entry.get("username") and int(token_principal_entry.get("id") or 0) > 0:
            _cache_user_entry(token_principal_entry)

    cached_entry = _read_cached_entry(str(username or "").strip(), token_uid)
    if cached_entry and time.time() <= float(cached_entry.get("expires_at") or 0.0):
        return _entry_to_principal(cached_entry)
    
    try:
        user = db.query(User).filter(User.username == username).first()
        if user is not None:
            _cache_user_entry(_build_cached_principal(user))
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        logger.error("DB lookup failed in get_current_user: %s", type(exc).__name__)
        # Fail-open with short-lived stale identity cache when DB is transiently unavailable.
        stale_entry = _read_cached_entry(str(username or "").strip(), token_uid)
        if stale_entry:
            return _entry_to_principal(stale_entry)
        if token_principal_entry:
            return _entry_to_principal(token_principal_entry)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable, please retry",
        )

    if user is None:
        raise credentials_exception
    if (
        getattr(user, "account_status", 1) == -1
        and not _is_user_enabled(getattr(user, "is_active", 1))
        and not bool(getattr(user, "is_superuser", False))
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required",
        )
    if not _is_user_enabled(getattr(user, "is_active", 1)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is disabled",
        )
    principal_entry = _build_cached_principal(user)
    _cache_user_entry(principal_entry)
    return _entry_to_principal(principal_entry)
