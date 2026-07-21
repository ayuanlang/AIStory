# -*- coding: utf-8 -*-
"""WeChat pay config row helpers (shared by billing + admin_ops)."""
from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.all_models import WechatPayConfig


def _get_active_wechat_config(db: Session) -> Optional[WechatPayConfig]:
    return db.query(WechatPayConfig).filter(
        WechatPayConfig.is_active == True,
    ).order_by(WechatPayConfig.id.desc()).first()


def _wechat_config_to_dict(row: Optional[WechatPayConfig]) -> Dict[str, Any]:
    if not row:
        return {
            "mchid": "",
            "appid": "",
            "api_v3_key": "",
            "cert_serial_no": "",
            "private_key": "",
            "notify_url": "",
            "use_mock": True,
        }
    return {
        "mchid": str(row.mchid or "").strip(),
        "appid": str(row.appid or "").strip(),
        "api_v3_key": str(row.api_v3_key or "").strip(),
        "cert_serial_no": str(row.cert_serial_no or "").strip(),
        "private_key": str(row.private_key or ""),
        "notify_url": str(row.notify_url or "").strip(),
        "use_mock": bool(row.use_mock),
    }


# payment/smtp/maintenance admin routes moved to app.api.routers.admin_ops


