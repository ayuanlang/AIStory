# -*- coding: utf-8 -*-
"""Resolve effective API setting metadata (user selection -> system default)."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.all_models import APISetting, SystemAPISetting, User
from app.services.endpoint_misc import _safe_int
from app.services.system_default_api_service import get_task_default_system_setting


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        raw = value.strip().lower()
        if raw in {"1", "true", "yes", "y", "on"}:
            return True
        if raw in {"0", "false", "no", "n", "off", "", "none", "null"}:
            return False
    return bool(value)


def _safe_json_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value.strip())
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _is_system_setting_deprecated(config_value: Any, deprecated_flag: Any = None) -> bool:
    if _to_bool(deprecated_flag):
        return True
    cfg = _safe_json_dict(config_value)
    return bool(
        _to_bool(cfg.get("deprecated"))
        or _to_bool(cfg.get("is_deprecated"))
        or _to_bool(cfg.get("disable_api"))
    )


def _resolve_effective_api_setting_meta(
    db: Session,
    user: User,
    provider: str = None,
    category: str = None,
) -> Tuple[Optional[APISetting], str, Dict[str, Any]]:
    resolved_category = str(category or "").strip()
    if not resolved_category:
        return None, "missing_category", {"active_count": 0}

    user_setting_query = db.query(APISetting).filter(
        APISetting.user_id == user.id,
        APISetting.category == resolved_category,
    )

    active_count = user_setting_query.count()
    setting = user_setting_query.order_by(APISetting.id.desc()).first()
    if not setting:
        system_default = get_task_default_system_setting(db, resolved_category)
        if system_default and not _is_system_setting_deprecated(system_default.config, system_default.deprecated):
            return system_default, "system_category_default", {
                "active_count": active_count,
                "category": resolved_category,
                "category_default_id": int(system_default.id),
            }

        return None, "no_active_user_setting_or_category_default", {
            "active_count": active_count,
            "category": resolved_category,
        }

    selected_system_setting_id = _safe_int(getattr(setting, "system_api_id", None), 0)
    if selected_system_setting_id > 0:
        system_by_id = db.query(SystemAPISetting).filter(SystemAPISetting.id == selected_system_setting_id).first()
        if not system_by_id:
            return None, "system_setting_id_not_found", {
                "active_count": active_count,
                "setting_id": setting.id,
                "category": resolved_category,
                "system_api_id": selected_system_setting_id,
            }
        if str(system_by_id.category or "").strip() != resolved_category:
            return None, "system_setting_id_category_mismatch", {
                "active_count": active_count,
                "setting_id": setting.id,
                "category": resolved_category,
                "system_api_id": selected_system_setting_id,
                "resolved_category": str(system_by_id.category or "").strip(),
            }
        if _is_system_setting_deprecated(system_by_id.config, system_by_id.deprecated):
            return None, "system_setting_deprecated", {
                "active_count": active_count,
                "setting_id": setting.id,
                "category": resolved_category,
                "system_api_id": selected_system_setting_id,
            }
        return system_by_id, "system_by_user_setting_id", {
            "active_count": active_count,
            "setting_id": setting.id,
            "category": resolved_category,
            "system_api_id": selected_system_setting_id,
            "mode": str(getattr(setting, "mode", "") or "").strip() or None,
        }

    return None, "active_user_missing_system_api_id", {
        "active_count": active_count,
        "setting_id": setting.id,
        "category": resolved_category,
    }
