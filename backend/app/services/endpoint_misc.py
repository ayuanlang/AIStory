# -*- coding: utf-8 -*-
"""Small shared endpoint helpers (schema heal, vendor messages, batch logging)."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.time_utils import now_bj_iso
from app.db.init_db import check_and_migrate_tables
from app.db.session import SessionLocal
from app.models import all_models as models
from app.models.all_models import User
from app.services.system_log_service import log_action

logger = logging.getLogger("api_logger")

ProjectAssetReviewThread = getattr(models, "ProjectAssetReviewThread", None)
ProjectAssetReviewRound = getattr(models, "ProjectAssetReviewRound", None)
ProjectAssetReviewMessage = getattr(models, "ProjectAssetReviewMessage", None)
_REVIEW_MODELS_AVAILABLE = all(
    model is not None
    for model in (ProjectAssetReviewThread, ProjectAssetReviewRound, ProjectAssetReviewMessage)
)


def _require_review_models() -> None:
    if _REVIEW_MODELS_AVAILABLE:
        return
    raise HTTPException(
        status_code=503,
        detail="Project asset review is temporarily unavailable on this deployment",
    )


def _is_schema_compat_error(exc: Exception) -> bool:
    raw = str(getattr(exc, "orig", exc) or exc).strip().lower()
    if not raw:
        return False
    markers = (
        "undefinedcolumn",
        "undefinedtable",
        "does not exist",
        "no such column",
        "no such table",
        "datatype mismatch",
        "type boolean but expression is of type integer",
    )
    return any(marker in raw for marker in markers)


def _run_with_schema_self_heal(db: Session, operation, *, context: str):
    try:
        return operation()
    except (OperationalError, ProgrammingError) as exc:
        if not _is_schema_compat_error(exc):
            raise
        logger.warning("[%s] detected schema mismatch, running migration and retrying once: %s", context, exc)
        try:
            db.rollback()
        except Exception:
            pass
        check_and_migrate_tables()
        return operation()


from app.services.auth_security import get_password_hash, verify_password


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default



def _vendor_failed_message(provider: Optional[str], reason: Any) -> str:
    vendor = str(provider or "").strip() or "unknown"
    detail = str(reason or "unknown error").strip()
    if "供应商调用失败" in detail:
        return detail
    return f"{vendor}供应商调用失败: {detail}"


def _build_scene_analysis_blocking_failure_detail(
    blocking_codes: List[str],
    integrity_warnings: List[str],
    subject_warnings: List[str],
) -> str:
    codes = {str(code or "").strip() for code in (blocking_codes or []) if str(code or "").strip()}
    reasons_cn: List[str] = []

    if "ANALYSIS_STRUCTURE_INCOMPLETE" in codes:
        reasons_cn.append("结果缺少必要结构段，无法形成完整的场景分析")
    if "ANALYSIS_SUBJECTS_UNVERIFIED" in codes:
        reasons_cn.append("角色/环境/道具的一致性校验未完成，当前结果不可靠")
    if "ANALYSIS_SUBJECTS_INCOMPLETE" in codes:
        reasons_cn.append("角色/环境/道具覆盖不完整，当前结果不能继续使用")
    if "ANALYSIS_OUTPUT_TRUNCATED" in codes:
        reasons_cn.append("返回内容疑似被截断，结果不完整")
    if "ANALYSIS_JSON_INVALID" in codes:
        reasons_cn.append("返回内容的结构片段损坏，系统无法安全解析")
    if "ANALYSIS_SUBJECT_INDEX_MISSING" in codes:
        reasons_cn.append("未解析到完整的资产清单（Subject Index）区块")
    if "ANALYSIS_SUBJECT_INDEX_HEADER_ONLY" in codes:
        reasons_cn.append("仅解析到 Subject Index 表头，缺少实体条目")
    if "ANALYSIS_SUBJECT_INDEX_REQUIRED" in codes:
        reasons_cn.append("缺少资产清单（Subject Index），无法继续场景编排或资产生成")

    raw_reasons: List[str] = []
    raw_reasons.extend([str(x or "").strip() for x in (integrity_warnings or []) if str(x or "").strip()])
    raw_reasons.extend([str(x or "").strip() for x in (subject_warnings or []) if str(x or "").strip()])
    raw_reasons = list(dict.fromkeys(raw_reasons))

    detail_parts: List[str] = []
    if reasons_cn:
        detail_parts.append("；".join(reasons_cn[:3]))

    if raw_reasons:
        detail_parts.append("技术明细：" + "；".join(raw_reasons[:3]))

    body = "；".join([part for part in detail_parts if part])
    if body:
        return "场景分析结果不可用：" + body + "。请直接重新执行剧本分析。"
    return "场景分析结果不可用：返回内容结构不完整或校验未通过。请直接重新执行剧本分析。"



# fix-db-schema moved to app.api.routers.admin_ops

from app.services.system_log_service import (
    append_ui_system_logs,
    get_ui_system_log_path,
    log_action,
    read_ui_system_logs,
)
from app.schemas.system_log import (
    SystemLogOut,
    SystemLogCreate,
    UiSystemLogBatchCreate,
    UiSystemLogBatchOut,
    UiSystemLogListOut,
    UiSystemLogReadEntry,
    ScriptAnalysisAiDiagnosisRequest,
    ScriptAnalysisAiDiagnosisOut,
)
from app.services.script_analysis_ai_diagnosis import (
    OPS_SUPPORT_EMAIL,
    build_diagnosis_messages,
    build_ops_email_body,
    normalize_page_scope,
)

def _can_use_system_settings(user: User) -> bool:
    return bool((user.credits or 0) > 0 or user.is_superuser or user.is_system)


def _log_batch_sys_event(
    *,
    kind: str,
    phase: str,
    user_id: int,
    user_name: str,
    project_id: Optional[int] = None,
    episode_id: Optional[int] = None,
    job_id: Optional[str] = None,
    item_id: Optional[int] = None,
    item_label: Optional[str] = None,
    result: Optional[str] = None,
    message: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    action_kind = str(kind or "batch").strip().replace("-", "_").upper()
    action_phase = str(phase or "event").strip().replace("-", "_").upper()
    action = f"BATCH_{action_kind}_{action_phase}"
    details_payload: Dict[str, Any] = {
        "kind": kind,
        "phase": phase,
        "job_id": job_id,
        "project_id": project_id,
        "episode_id": episode_id,
        "item_id": item_id,
        "item_label": item_label,
        "result": result,
        "message": message,
        "timestamp": now_bj_iso(),
    }
    if isinstance(extra, dict) and extra:
        details_payload["extra"] = extra

    log_db = SessionLocal()
    try:
        log_action(
            log_db,
            user_id=int(user_id),
            user_name=str(user_name or f"user_{user_id}"),
            action=action,
            details=json.dumps(details_payload, ensure_ascii=False, default=str),
        )
    except Exception as e:
        logger.warning(
            "[batch_syslog] failed action=%s kind=%s phase=%s job_id=%s err=%s",
            action,
            kind,
            phase,
            job_id,
            e,
        )
    finally:
        log_db.close()



