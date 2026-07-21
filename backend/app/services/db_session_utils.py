# -*- coding: utf-8 -*-
"""DB session / user principal helpers shared across routers."""
from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any, Optional

from sqlalchemy import inspect
from sqlalchemy.orm import Session

logger = logging.getLogger("api_logger")


def _release_db_connection(db: Optional[Session], reason: str = "") -> None:
    if db is None:
        return
    try:
        db.rollback()
    except Exception as exc:
        if reason:
            logger.debug("[db_release] rollback skipped | reason=%s error=%s", reason, exc)
        else:
            logger.debug("[db_release] rollback skipped | error=%s", exc)
    try:
        db.close()
    except Exception as exc:
        if reason:
            logger.debug("[db_release] close skipped | reason=%s error=%s", reason, exc)
        else:
            logger.debug("[db_release] close skipped | error=%s", exc)


def _snapshot_user_principal(user: Any) -> SimpleNamespace:
    """Build a detached-safe user snapshot for long-running/background tasks."""
    def _safe_attr(name: str, default: Any = None) -> Any:
        if user is None:
            return default
        try:
            state = inspect(user)
        except Exception:
            state = None

        if state is not None and hasattr(state, "dict"):
            state_dict = getattr(state, "dict", {}) or {}
            if name in state_dict:
                return state_dict.get(name, default)
            if name == "id":
                identity = getattr(state, "identity", None)
                if identity and len(identity) > 0:
                    return identity[0]
            return default

        if isinstance(user, dict):
            return user.get(name, default)
        user_dict = getattr(user, "__dict__", None)
        if isinstance(user_dict, dict) and name in user_dict:
            return user_dict.get(name, default)
        try:
            return getattr(user, name, default)
        except Exception:
            return default

    return SimpleNamespace(
        id=int(_safe_attr("id", 0) or 0),
        username=str(_safe_attr("username", "") or ""),
        email=str(_safe_attr("email", "") or "") or None,
        full_name=str(_safe_attr("full_name", "") or "") or None,
        avatar_url=str(_safe_attr("avatar_url", "") or "") or None,
        is_active=int(_safe_attr("is_active", 1) or 1),
        is_superuser=bool(_safe_attr("is_superuser", False)),
        is_authorized=bool(_safe_attr("is_authorized", False)),
        is_system=bool(_safe_attr("is_system", False)),
        account_status=int(_safe_attr("account_status", 1) or 1),
        email_verified=bool(_safe_attr("email_verified", False)),
        credits=int(_safe_attr("credits", 0) or 0),
        preferences=_safe_attr("preferences", None),
    )
