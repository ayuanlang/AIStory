# -*- coding: utf-8 -*-
from fastapi import HTTPException

from app.services.credit_error import (
    INSUFFICIENT_CREDITS_CODE,
    VENDOR_BALANCE_CODE,
    classify_batch_credit_failure,
    credit_error_code,
    credit_error_user_message,
    http_exception_detail_text,
    is_insufficient_credits_error,
    is_vendor_balance_error,
)
from app.services.scene_markdown_orchestration import (
    _is_retryable_scene_orchestration_error,
    _scene_orchestration_error_code,
)


def test_detects_user_402_personal_credits():
    exc = HTTPException(status_code=402, detail="个人积分不足。 / Insufficient personal credits.")
    assert is_insufficient_credits_error(exc) is True
    assert is_vendor_balance_error(exc) is False
    assert credit_error_code(exc) == INSUFFICIENT_CREDITS_CODE
    assert "积分不足" in credit_error_user_message(exc)
    assert _is_retryable_scene_orchestration_error(exc) is False
    assert _scene_orchestration_error_code(exc, "SC01").startswith(f"{INSUFFICIENT_CREDITS_CODE}:SC01")


def test_detects_wrapped_partial_failure_with_credit_scenes():
    exc = HTTPException(
        status_code=422,
        detail={
            "code": "SCENE_MARKDOWN_PARTIAL_FAILURE",
            "failed_scenes": [{"scene_id": "SC01", "error_code": INSUFFICIENT_CREDITS_CODE}],
        },
    )
    blob = http_exception_detail_text(exc)
    assert INSUFFICIENT_CREDITS_CODE in blob
    assert is_insufficient_credits_error(exc) is True
    assert credit_error_code(exc) == INSUFFICIENT_CREDITS_CODE


def test_vendor_balance_is_not_user_recharge():
    exc = HTTPException(status_code=402, detail="供应商侧余额不足，无权调用该模型")
    assert is_vendor_balance_error(exc) is True
    assert is_insufficient_credits_error(exc) is True
    assert credit_error_code(exc) == VENDOR_BALANCE_CODE
    assert "供应商" in credit_error_user_message(exc)
    assert _is_retryable_scene_orchestration_error(exc) is False


def test_classify_batch_credit_failure_prefers_vendor():
    assert (
        classify_batch_credit_failure(
            [
                {"scene_id": "SC01", "error_code": INSUFFICIENT_CREDITS_CODE},
                {"scene_id": "SC02", "error_code": VENDOR_BALANCE_CODE},
            ]
        )
        == VENDOR_BALANCE_CODE
    )
    assert (
        classify_batch_credit_failure([{"error_code": f"{INSUFFICIENT_CREDITS_CODE}:SC01"}])
        == INSUFFICIENT_CREDITS_CODE
    )
    assert classify_batch_credit_failure([{"error_code": "SCENE_MARKDOWN_ORCHESTRATION_FAILED"}]) is None
    assert "积分不足" in credit_error_user_message(INSUFFICIENT_CREDITS_CODE)
    assert "供应商" in credit_error_user_message(VENDOR_BALANCE_CODE)
