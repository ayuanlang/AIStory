# -*- coding: utf-8 -*-
"""Login authentication helpers (no FastAPI router)."""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from fastapi import HTTPException, Request
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.api.deps import cache_user_identity, invalidate_cached_user_identity
from app.models.all_models import User
from app.schemas.user_auth import USER_ACTIVE_LEVEL_DEFAULT, normalize_user_active_level
from app.services.auth_security import verify_password

logger = logging.getLogger("api_logger")


def _get_login_maintenance_status_cached() -> Dict[str, Any]:
    from app.services.maintenance_status import _get_login_maintenance_status_cached as _cached
    return _cached()


def _describe_login_identifier(identifier: str) -> str:
    raw = str(identifier or "").strip()
    if not raw:
        return "empty"
    if "@" in raw:
        local_part, _, domain_part = raw.partition("@")
        masked_local = (local_part[:2] + "***") if local_part else "***"
        return f"email:{masked_local}@{domain_part or 'unknown'}"
    if len(raw) <= 3:
        return f"username:{raw[0]}***"
    return f"username:{raw[:3]}***"


def _get_request_client_ip(request: Optional[Request]) -> Optional[str]:
    if request is None:
        return None
    forwarded_for = str(request.headers.get("x-forwarded-for") or "").strip()
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip() or None
    client = getattr(request, "client", None)
    host = getattr(client, "host", None)
    return str(host).strip() or None if host else None


def _log_login_stage(level: int, message: str, **fields: Any) -> None:
    payload = " ".join(f"{key}={fields[key]}" for key in sorted(fields))
    if payload:
        logger.log(level, "%s | %s", message, payload)
        return
    logger.log(level, "%s", message)


def _refresh_user_identity_cache(user: Optional[User], *, old_username: Optional[str] = None) -> None:
    if user is None:
        return
    invalidate_cached_user_identity(
        user_id=int(getattr(user, "id", 0) or 0),
        username=str(old_username or "").strip(),
    )
    cache_user_identity(user)


def _get_users_is_active_schema_snapshot(db: Session) -> Dict[str, Any]:
    try:
        bind = db.get_bind()
        if bind is None:
            return {"available": False, "reason": "no_bind"}
        columns = {col["name"]: col for col in inspect(bind).get_columns("users")}
        is_active_col = columns.get("is_active") or {}
        return {
            "available": bool(is_active_col),
            "type": str(is_active_col.get("type") or "").lower() or None,
            "nullable": is_active_col.get("nullable"),
            "default": str(is_active_col.get("default") or "") or None,
        }
    except Exception as exc:
        return {
            "available": False,
            "reason": type(exc).__name__,
        }


def _log_login_is_active_diagnostics(db: Session, user: User, identifier: str, stage: str) -> None:
    schema = _get_users_is_active_schema_snapshot(db)
    raw_value = getattr(user, "is_active", None)
    _log_login_stage(
        logging.INFO,
        "[login] is_active diagnostics",
        stage=stage,
        identifier=identifier,
        user_id=getattr(user, "id", None),
        user_is_active_value=repr(raw_value),
        user_is_active_python_type=type(raw_value).__name__,
        normalized_is_active=normalize_user_active_level(raw_value, USER_ACTIVE_LEVEL_DEFAULT),
        account_status=getattr(user, "account_status", None),
        schema_available=schema.get("available"),
        schema_type=schema.get("type"),
        schema_nullable=schema.get("nullable"),
        schema_default=schema.get("default"),
        schema_reason=schema.get("reason"),
    )


def authenticate_user(db: Session, username: str, password: str):
    username = str(username or "").strip()
    login_started_at = time.perf_counter()
    login_identifier = _describe_login_identifier(username)
    _log_login_stage(logging.INFO, "[login] authenticate_user start", identifier=login_identifier)
    try:
        # Try by username
        lookup_started_at = time.perf_counter()
        user = db.query(User).filter(User.username == username).first()
        _log_login_stage(
            logging.INFO,
            "[login] username lookup finished",
            identifier=login_identifier,
            found=bool(user),
            elapsed_ms=int((time.perf_counter() - lookup_started_at) * 1000),
        )
        if not user:
            # Try by email
            email_lookup_started_at = time.perf_counter()
            user = db.query(User).filter(User.email == str(username or "").strip().lower()).first()
            _log_login_stage(
                logging.INFO,
                "[login] email lookup finished",
                identifier=login_identifier,
                found=bool(user),
                elapsed_ms=int((time.perf_counter() - email_lookup_started_at) * 1000),
            )
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        logger.exception(
            "DB lookup failed in authenticate_user | identifier=%s elapsed_ms=%s error=%s",
            login_identifier,
            int((time.perf_counter() - login_started_at) * 1000),
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=503,
            detail="Database temporarily unavailable, please retry",
        )
    
    if not user:
        _log_login_stage(
            logging.WARNING,
            "[login] user not found during authentication",
            identifier=login_identifier,
            elapsed_ms=int((time.perf_counter() - login_started_at) * 1000),
        )
        return None

    verify_started_at = time.perf_counter()
    if not verify_password(password, user.hashed_password):
        _log_login_stage(
            logging.WARNING,
            "[login] password verification failed",
            identifier=login_identifier,
            user_id=getattr(user, "id", None),
            elapsed_ms=int((time.perf_counter() - login_started_at) * 1000),
            verify_elapsed_ms=int((time.perf_counter() - verify_started_at) * 1000),
        )
        return None

    _log_login_stage(
        logging.INFO,
        "[login] authenticate_user success",
        identifier=login_identifier,
        user_id=getattr(user, "id", None),
        is_active=getattr(user, "is_active", None),
        account_status=getattr(user, "account_status", None),
        is_superuser=bool(getattr(user, "is_superuser", False)),
        email_verified=bool(getattr(user, "email_verified", False)),
        elapsed_ms=int((time.perf_counter() - login_started_at) * 1000),
        verify_elapsed_ms=int((time.perf_counter() - verify_started_at) * 1000),
    )
    return user


def _is_maintenance_active_for_login(db: Session) -> bool:
    try:
        status = _get_login_maintenance_status_cached()
        return bool(status.get("is_active", False))
    except Exception:
        return False


def _should_block_login_for_maintenance(
    db: Session,
    user: User,
    *,
    login_identifier: str,
    client_ip: Optional[str],
    request_started_at: float,
    flow_name: str,
) -> bool:
    if bool(getattr(user, "is_superuser", False)):
        _log_login_stage(
            logging.INFO,
            f"[login] {flow_name} maintenance check skipped for superuser",
            identifier=login_identifier,
            client_ip=client_ip,
            user_id=getattr(user, "id", None),
            elapsed_ms=int((time.perf_counter() - request_started_at) * 1000),
        )
        return False

    maintenance_started_at = time.perf_counter()
    _log_login_stage(
        logging.INFO,
        f"[login] {flow_name} maintenance check start",
        identifier=login_identifier,
        client_ip=client_ip,
        user_id=getattr(user, "id", None),
    )
    is_active = _is_maintenance_active_for_login(db)
    _log_login_stage(
        logging.INFO,
        f"[login] {flow_name} maintenance check finished",
        identifier=login_identifier,
        client_ip=client_ip,
        user_id=getattr(user, "id", None),
        is_active=is_active,
        elapsed_ms=int((time.perf_counter() - maintenance_started_at) * 1000),
        request_elapsed_ms=int((time.perf_counter() - request_started_at) * 1000),
    )
    return is_active

