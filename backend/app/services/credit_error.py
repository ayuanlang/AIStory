# -*- coding: utf-8 -*-
"""Detect user/vendor credit failures so pipeline nodes can surface them clearly."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException

INSUFFICIENT_CREDITS_CODE = "INSUFFICIENT_CREDITS"
VENDOR_BALANCE_CODE = "VENDOR_BALANCE_INSUFFICIENT"

_USER_CREDIT_NEEDLES = (
    "insufficient personal credits",
    "insufficient credits",
    "insufficient group credits",
    "insufficient balance",
    "积分不足",
    "组积分不足",
    "个人积分不足",
    "余额不足",
    "insufficient_credits",
)
_VENDOR_BALANCE_NEEDLES = (
    "供应商侧余额不足",
    "供应商余额不足",
    "无权调用该模型",
    "vendor balance",
    "provider balance",
)


def _detail_text(detail: Any) -> str:
    if isinstance(detail, dict):
        parts = [
            detail.get("message"),
            detail.get("code"),
            detail.get("error_code"),
            detail.get("error_message"),
        ]
        failed = detail.get("failed_scenes")
        if isinstance(failed, list):
            for item in failed:
                if isinstance(item, dict):
                    parts.append(item.get("error_code"))
                    parts.append(item.get("error_message"))
                elif item:
                    parts.append(item)
        return " ".join(str(part) for part in parts if part)
    if isinstance(detail, (list, tuple)):
        return " ".join(_detail_text(item) for item in detail if item)
    return str(detail or "")


def http_exception_detail_text(exc: Any) -> str:
    if isinstance(exc, HTTPException):
        return _detail_text(getattr(exc, "detail", ""))
    if isinstance(exc, dict):
        return _detail_text(exc)
    return str(exc or "")


def classify_batch_credit_failure(failed_scene_reports: Any) -> Optional[str]:
    """Return a credit error code if any failed scene is a billing/vendor-balance miss."""
    user_credit = False
    for report in failed_scene_reports or []:
        code = ""
        if isinstance(report, dict):
            code = str(report.get("error_code") or report.get("code") or "")
        else:
            code = str(report or "")
        code = code.split(":", 1)[0].strip()
        if code == VENDOR_BALANCE_CODE:
            return VENDOR_BALANCE_CODE
        if code == INSUFFICIENT_CREDITS_CODE:
            user_credit = True
    return INSUFFICIENT_CREDITS_CODE if user_credit else None


def _status_and_text(exc_or_text: Any, status_code: Optional[int] = None) -> tuple[int, str]:
    status = int(status_code or 0)
    if isinstance(exc_or_text, HTTPException):
        status = int(getattr(exc_or_text, "status_code", 0) or status or 0)
        text = http_exception_detail_text(exc_or_text)
    else:
        text = str(exc_or_text or "")
    return status, text


def is_vendor_balance_error(exc_or_text: Any, status_code: Optional[int] = None) -> bool:
    _status, text = _status_and_text(exc_or_text, status_code)
    blob = text.lower()
    if VENDOR_BALANCE_CODE.lower() in blob:
        return True
    return any(needle.lower() in blob for needle in _VENDOR_BALANCE_NEEDLES)


def is_insufficient_credits_error(exc_or_text: Any, status_code: Optional[int] = None) -> bool:
    status, text = _status_and_text(exc_or_text, status_code)
    if is_vendor_balance_error(exc_or_text, status):
        return True
    blob = f"{status} {text}".lower()
    if status == 402:
        return True
    if INSUFFICIENT_CREDITS_CODE.lower() in blob or VENDOR_BALANCE_CODE.lower() in blob:
        return True
    return any(needle.lower() in blob for needle in _USER_CREDIT_NEEDLES)


def credit_error_code(exc_or_text: Any, status_code: Optional[int] = None) -> str:
    if is_vendor_balance_error(exc_or_text, status_code):
        return VENDOR_BALANCE_CODE
    return INSUFFICIENT_CREDITS_CODE


def credit_error_user_message(exc_or_text: Any, status_code: Optional[int] = None) -> str:
    if is_vendor_balance_error(exc_or_text, status_code):
        return "供应商余额不足或无权调用该模型，请更换接口或联系管理员。"
    return "积分不足，请充值后再重跑该节点。"
