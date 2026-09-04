# -*- coding: utf-8 -*-
"""Script analysis AI diagnosis route (P5)."""
from __future__ import annotations

import logging
import os
import re
import uuid
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.time_utils import BEIJING_TZ, now_bj_iso
from app.db.session import SessionLocal, get_db
from app.models import all_models as models
from app.models.all_models import *

logger = logging.getLogger("api_logger")
router = APIRouter(tags=["script-analysis"])

from app.schemas.system_log import ScriptAnalysisAiDiagnosisRequest, ScriptAnalysisAiDiagnosisOut
from app.services.script_analysis_ai_diagnosis import (
    OPS_SUPPORT_EMAIL, build_diagnosis_messages, build_ops_email_body, normalize_page_scope,
)
from app.services.auth_email import _send_email_via_runtime_smtp


def _bind_endpoint_helpers(*, include_routers: bool = True) -> None:
    from app.api.routers.helper_bind import bind_shared_helpers
    bind_shared_helpers(globals(), __name__, include_routers=include_routers)

_bind_endpoint_helpers(include_routers=False)


class PromptSecurityIncidentIn(BaseModel):
    code: str = ""
    message: str = ""
    source: str = "frontend"
    project_id: Optional[int] = None
    episode_id: Optional[int] = None
    scene_id: Optional[str] = None
    matches: List[Dict[str, str]] = Field(default_factory=list)


class PromptSecurityIncidentOut(BaseModel):
    ok: bool = True
    recorded: bool = True


@router.post("/script_analysis/prompt_security_incident", response_model=PromptSecurityIncidentOut)
def report_prompt_security_incident(
    payload: PromptSecurityIncidentIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Frontend intercept of prompt leak / injection: persist audit and notify admins."""
    from app.core.prompt_injection import PROMPT_INJECTION_DETECTED, PROMPT_LEAK_DETECTED
    from app.services.prompt_security_incident import record_prompt_security_incident

    raw_code = str(payload.code or "").strip()
    code = raw_code if raw_code in {PROMPT_INJECTION_DETECTED, PROMPT_LEAK_DETECTED} else PROMPT_INJECTION_DETECTED
    safe_matches = []
    for item in list(payload.matches or [])[:8]:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "").strip()[:80]
        snippet = str(item.get("snippet") or "").strip()[:80]
        if not kind and not snippet:
            continue
        safe_matches.append({"kind": kind, "snippet": snippet})
    record_prompt_security_incident(
        code=code,
        message=str(payload.message or "").strip()[:800],
        source=str(payload.source or "frontend").strip()[:120] or "frontend",
        matches=safe_matches,
        db=db,
        user=current_user,
        project_id=payload.project_id,
        episode_id=payload.episode_id,
        scene_id=payload.scene_id,
    )
    return PromptSecurityIncidentOut(ok=True, recorded=True)


@router.post("/script_analysis/ai_diagnosis", response_model=ScriptAnalysisAiDiagnosisOut)
async def run_script_analysis_ai_diagnosis(
    payload: ScriptAnalysisAiDiagnosisRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Diagnose script-analysis or assets page state with agent-style multi-turn LLM chat; optionally email ops."""
    current_user_snapshot = _snapshot_user_principal(current_user)
    current_user_id = int(getattr(current_user_snapshot, "id", 0) or 0)
    if payload.project_id:
        _require_project_access(db, int(payload.project_id), current_user_snapshot)

    page_scope = normalize_page_scope(getattr(payload, "page_scope", None))
    manual_text = str(payload.manual_text or "")
    system_logs = str(payload.system_logs or "")
    workspace_summary = str(payload.workspace_summary or "")
    user_note = str(payload.user_note or "")
    history_payload = list(payload.history or [])
    existing_advice = str(payload.existing_advice or "").strip()
    email_only = bool(payload.send_to_ops) and bool(existing_advice)
    has_history = any(
        str(getattr(item, "content", None) or (item.get("content") if isinstance(item, dict) else "") or "").strip()
        for item in history_payload
    )

    if not any(
        part.strip()
        for part in (manual_text, system_logs, workspace_summary, user_note, existing_advice)
    ) and not has_history:
        raise HTTPException(status_code=400, detail="请至少提供操作手册、系统日志、工作区概况或问题描述中的一项。")

    meta = {
        "ops_email": OPS_SUPPORT_EMAIL,
        "email_only": email_only,
        "agent_mode": True,
        "page_scope": page_scope,
    }
    advice = existing_advice
    selected_dropdown_id = None
    config = None

    if not email_only:
        messages, prompt_meta = build_diagnosis_messages(
            manual_text=manual_text,
            system_logs=system_logs,
            workspace_summary=workspace_summary,
            user_note=user_note,
            history=history_payload,
            project_id=payload.project_id,
            episode_id=payload.episode_id,
            episode_label=str(payload.episode_label or ""),
            page_scope=page_scope,
        )
        meta.update(prompt_meta)

        billing_item = (
            "assets_ai_diagnosis"
            if page_scope == "assets"
            else "script_analysis_ai_diagnosis"
        )
        config, selected_dropdown_id, _, _ = _resolve_script_analysis_dropdown_llm_config(
            db,
            current_user_id,
            payload.function_name or "script_analysis",
            payload.system_api_id,
            context=billing_item,
        )
        if not config or not (config.get("provider") or config.get("api_key") or (config.get("config") or {}).get("api_key")):
            raise HTTPException(status_code=400, detail="未找到可用的剧本分析 AI 接口，请先在设置中配置。")

        config = _inject_user_advanced_llm_preferences(config, current_user_snapshot)
        provider = (config or {}).get("provider")
        model = (config or {}).get("model")
        task_type = "llm_chat"
        reservation_tx = None
        reservation_tx_id = None

        reserve_extra: Dict[str, Any] = {"item": billing_item}
        if payload.project_id:
            reserve_extra["project_id"] = int(payload.project_id)
        if payload.episode_id:
            reserve_extra["episode_id"] = int(payload.episode_id)

        if billing_service.is_token_pricing(db, task_type, provider, model):
            est = billing_service.estimate_reserve_tokens_from_messages(messages)
            reservation_tx = billing_service.reserve_credits(
                db,
                current_user_id,
                task_type,
                provider,
                model,
                {
                    **reserve_extra,
                    "estimation_method": "prompt_tokens_ratio",
                    "estimated_output_ratio": billing_service.RESERVE_OUTPUT_RATIO,
                    "input_tokens": est.get("input_tokens", 0),
                    "output_tokens": est.get("output_tokens", 0),
                    "total_tokens": est.get("total_tokens", 0),
                },
            )
            reservation_tx_id = _reservation_tx_id(reservation_tx)
        else:
            billing_service.check_balance(db, current_user_id, task_type, provider, model)

        _release_db_connection(db, "script_analysis_ai_diagnosis_llm_call")

        try:
            llm_response = await llm_service.chat_completion_with_fallback(
                messages,
                config,
                user_id=current_user_id,
                category="LLM",
            )
            advice = str((llm_response or {}).get("content") or "").strip()
            if not advice:
                raise HTTPException(status_code=422, detail="AI 未返回有效诊断内容，请稍后重试。")
            if advice.startswith("Error:"):
                raise HTTPException(status_code=502, detail=advice)

            usage = (llm_response or {}).get("usage") if isinstance(llm_response, dict) else {}
            if not isinstance(usage, dict) or not usage:
                usage = billing_service.estimate_input_output_tokens_from_messages(
                    list(messages or []) + [{"role": "assistant", "content": advice}],
                    output_ratio=1.0,
                )

            settle_db = SessionLocal()
            try:
                billing_details = _finalize_model_invocation_billing(
                    db=settle_db,
                    current_user=current_user_snapshot,
                    task_type=task_type,
                    provider=provider,
                    model=model,
                    reservation_tx=reservation_tx,
                    reservation_tx_id=reservation_tx_id,
                    item=billing_item,
                    usage_payload=usage,
                    extra_details=reserve_extra,
                    routing_payload=llm_response,
                )
                meta["billing"] = {
                    "task_type": task_type,
                    "item": billing_item,
                    "input_tokens": billing_details.get("input_tokens"),
                    "output_tokens": billing_details.get("output_tokens"),
                    "total_tokens": billing_details.get("total_tokens"),
                }
            finally:
                settle_db.close()
        except HTTPException as exc:
            if reservation_tx_id:
                cancel_db = SessionLocal()
                try:
                    billing_service.cancel_reservation(cancel_db, reservation_tx_id, str(exc.detail))
                    billing_service.log_failed_transaction(
                        cancel_db, current_user_id, task_type, provider, model, str(exc.detail)
                    )
                finally:
                    cancel_db.close()
            raise
        except Exception as exc:
            if reservation_tx_id:
                cancel_db = SessionLocal()
                try:
                    billing_service.cancel_reservation(cancel_db, reservation_tx_id, str(exc))
                    billing_service.log_failed_transaction(
                        cancel_db, current_user_id, task_type, provider, model, str(exc)
                    )
                finally:
                    cancel_db.close()
            raise HTTPException(status_code=500, detail=f"AI 诊断失败：{exc}") from exc

    emailed = False
    email_error = None
    if bool(payload.send_to_ops):
        try:
            subject, content = build_ops_email_body(
                username=str(getattr(current_user_snapshot, "username", "") or ""),
                user_email=str(getattr(current_user_snapshot, "email", "") or ""),
                project_id=payload.project_id,
                episode_id=payload.episode_id,
                episode_label=str(payload.episode_label or ""),
                user_note=user_note,
                advice=advice,
                manual_text=manual_text,
                system_logs=system_logs,
                workspace_summary=workspace_summary,
                history=history_payload,
                page_scope=page_scope,
            )
            _send_email_via_runtime_smtp(OPS_SUPPORT_EMAIL, subject, content, strict=True)
            emailed = True
        except Exception as exc:
            email_error = str(exc)

    return ScriptAnalysisAiDiagnosisOut(
        ok=True,
        advice=advice,
        emailed_to_ops=emailed,
        ops_email=OPS_SUPPORT_EMAIL,
        email_error=email_error,
        meta={
            **meta,
            "system_api_id": selected_dropdown_id,
            "provider": (config or {}).get("provider") if isinstance(config, dict) else None,
            "model": (config or {}).get("model") if isinstance(config, dict) else None,
        },
    )


from app.services.system_api_lookup import get_system_api_setting  # noqa: E402,F401


def _safe_json_dict(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _loads_json5_if_available(text: str) -> Optional[Any]:
    raw = str(text or "")
    if not raw.strip():
        return None
    try:
        json5_mod = importlib.import_module("json5")
    except Exception:
        return None
    try:
        return json5_mod.loads(raw)
    except Exception:
        return None


def _episode_info_read_disabled() -> bool:
    # episode_info is deprecated as a runtime context source.
    # Keep this explicit so future code does not accidentally re-enable reads.
    return True


def _read_episode_info_payload(raw_value: Any) -> Dict[str, Any]:
    if _episode_info_read_disabled():
        return {}
    return _safe_json_dict(raw_value)


def _episode_info_from_episode(episode: Optional[Episode]) -> Dict[str, Any]:
    if not episode:
        return {}
    return _read_episode_info_payload(getattr(episode, "episode_info", None))


def _episode_runtime_info_from_episode(episode: Optional[Episode]) -> Dict[str, Any]:
    """Read raw episode_info for runtime status keys even when generic reads are disabled."""
    if not episode:
        return {}
    return _safe_json_dict(getattr(episode, "episode_info", None))


def _extract_episode_number_from_title(title: Any) -> Optional[int]:
    value = str(title or "").strip()
    if not value:
        return None

    match = re.search(r"(?:Episode|EP)\s*[-_#]?\s*(\d+)", value, flags=re.IGNORECASE)
    if match:
        return _to_positive_int_or_none(match.group(1))

    match = re.search(r"第\s*(\d+)\s*集", value)
    if match:
        return _to_positive_int_or_none(match.group(1))

    return None


def _normalize_title_for_compare(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = re.sub(r"[\s\-_:：,，。.!?！？'\"`“”‘’()（）\[\]【】<>《》]", "", text)
    return text


def _is_placeholder_script_title(title: Any) -> bool:
    value = str(title or "").strip()
    if not value:
        return True
    compact = _normalize_title_for_compare(value)
    if not compact:
        return True
    if compact in {"untitled", "tbd", "project", "title", "script", "scripttitle", "剧名", "片名", "未命名"}:
        return True
    if re.fullmatch(r"(?:episode|ep)0*\d+", compact):
        return True
    if re.fullmatch(r"第\d+[集话章回]", compact):
        return True
    return False


def _strip_wrapping_title_punctuation(value: Any) -> str:
    """Strip only balanced outer wrappers; do not peel unmatched trailing ）/] etc."""
    text = str(value or "").strip()
    pairs = {
        "'": "'",
        '"': '"',
        "`": "`",
        "“": "”",
        "‘": "’",
        "《": "》",
        "【": "】",
        "[": "]",
        "(": ")",
        "（": "）",
        "<": ">",
    }
    while len(text) >= 2:
        left, right = text[0], text[-1]
        if left in pairs and pairs[left] == right:
            text = text[1:-1].strip()
            continue
        break
    return text


_PRODUCTION_FORMAT_MOTIF_RE = re.compile(
    r"(?:"
    r"实拍|真人|真人剧|真人电影|真人剧集|真人短剧|真人写实|"
    r"live\s*action|photoreal|cinematic|电影感|"
    r"三维动画|二维动画|3d\s*animation|2d\s*animation|cgi|"
    r"8k|4k"
    r")",
    re.IGNORECASE,
)

# Stacked production suffixes from older buggy motif appends, e.g. ·实拍（真人剧·实拍（真人剧
_STACKED_PRODUCTION_TITLE_SUFFIX_RE = re.compile(
    r"(?:·\s*实拍\s*（\s*真人剧[^·]*)+$",
    re.IGNORECASE,
)


def _extract_title_motif_token(raw: Any) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    # Bilingual UI values use "中文 / English"; keep the primary side only.
    text = re.split(r"\s+/\s+", text, maxsplit=1)[0].strip()
    text = re.split(r"[，,。.!！？;；|\\\n]", text)[0].strip()
    # Drop parenthetical qualifiers: 实拍（真人剧/电影感8K） → 实拍
    text = re.sub(r"[（(][^）)]*[）)]?", "", text).strip()
    text = re.sub(r"\s+", "", text)
    if len(text) > 12:
        text = text[:12].rstrip("·-—_ ")
    return text


def _is_production_format_motif(token: Any) -> bool:
    compact = _normalize_title_for_compare(token)
    if not compact:
        return True
    if _PRODUCTION_FORMAT_MOTIF_RE.search(str(token or "")):
        # Format labels alone (or almost alone) are not story motifs.
        remainder = _PRODUCTION_FORMAT_MOTIF_RE.sub("", str(token or ""))
        remainder_compact = _normalize_title_for_compare(remainder)
        if not remainder_compact or len(remainder_compact) <= 2:
            return True
    return False


def _strip_stacked_production_title_suffixes(seed_title: Any) -> str:
    seed = str(seed_title or "").strip()
    if not seed:
        return ""
    cleaned = _STACKED_PRODUCTION_TITLE_SUFFIX_RE.sub("", seed).strip()
    # Also collapse any exact repeated ·token suffix: ·暗潮·暗潮 → ·暗潮 (then caller may re-decide)
    cleaned = re.sub(r"(·[^·]{1,20})\1+$", r"\1", cleaned).strip()
    return cleaned or seed


def _clean_extracted_script_title_candidate(raw_candidate: Any) -> str:
    candidate = _strip_wrapping_title_punctuation(raw_candidate)
    # Inline §0 lines often continue: Script Title:xxx · Type:yyy
    candidate = re.split(r"\s*[·•]\s*", candidate, maxsplit=1)[0].strip()
    candidate = re.split(
        r"\s+(?:Type|Language|Base\s*Positioning|Global\s*Style)\s*[：:]",
        candidate,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip()
    return _strip_stacked_production_title_suffixes(candidate)


def _extract_script_title_from_story_dna_markdown(markdown_text: Any) -> str:
    """Parse Script Title from Story DNA markdown into a JSON-ready string.

    Preferred machine marker (prompt contract):
      [SCRIPT_TITLE:{title}]
    Also accepts human-readable / legacy forms:
      Script Title: …
      剧名：…
      ## 0) Script Title:… · Type:…
    """
    raw = str(markdown_text or "")
    if not raw.strip():
        return ""

    patterns = [
        # Preferred machine-parseable marker (exclusive line or inline)
        r"(?im)\[\s*SCRIPT_TITLE\s*[：:]\s*([^\]]+?)\s*\]",
        # Dedicated list/bullet line
        r"(?im)^\s*[-*]?\s*Script\s*Title\s*[：:]\s*(.+?)\s*$",
        r"(?im)^\s*[-*]?\s*(?:剧名|片名)\s*[：:]\s*(.+?)\s*$",
        # Inline in §0 heading or label row
        r"(?im)(?:^|\n)\s*(?:#+\s*\d+\)\s*)?Script\s*Title\s*[：:]\s*(.+?)(?=\s*[·•]\s*(?:Type|Language|Base|Global)|$)",
        r"(?im)(?:^|\n)\s*(?:#+\s*\d+\)\s*)?(?:剧名|片名)\s*[：:]\s*(.+?)(?=\s*[·•]\s*|Type\s*[：:]|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw)
        if not match:
            continue
        candidate = _clean_extracted_script_title_candidate(match.group(1))
        if re.match(r"理据", candidate) or "意象=" in candidate:
            continue
        if not _is_placeholder_script_title(candidate):
            return candidate
    return ""


def _build_non_literal_script_title(
    seed_title: Any,
    project_type: Any,
    global_style: Any,
    base_positioning: Any,
) -> str:
    seed = _strip_stacked_production_title_suffixes(seed_title)
    # Prefer creative fields; project `type` is a production format label and must not become a title motif.
    motif = ""
    for source in (global_style, base_positioning, project_type):
        token = _extract_title_motif_token(source)
        if not token:
            continue
        if _is_production_format_motif(token):
            continue
        motif = token
        break
    if not motif:
        motif = "暗潮"

    if seed:
        seed_norm = _normalize_title_for_compare(seed)
        motif_norm = _normalize_title_for_compare(motif)
        # Already differentiated with this motif (or a previous append of it).
        if motif_norm and seed_norm.endswith(motif_norm):
            return seed
        if motif_norm and f"·{motif}" in seed:
            return seed
        candidate = f"{seed}·{motif}"
        if _normalize_title_for_compare(candidate) != seed_norm:
            return candidate

    return motif or "暗潮"


def _resolve_episode_sort_number(episode: Optional[Episode]) -> Optional[int]:
    if not episode:
        return None

    info = _episode_runtime_info_from_episode(episode)
    for key in (
        "episode_script_episode_number",
        "story_dna_episode_number",
        "episode_number",
        "index",
    ):
        parsed = _to_positive_int_or_none(info.get(key) if isinstance(info, dict) else None)
        if parsed:
            return parsed

    return _extract_episode_number_from_title(getattr(episode, "title", None))


def _sort_project_episodes(episodes: List[Episode]) -> List[Episode]:
    def _sort_key(episode: Episode):
        resolved_number = _resolve_episode_sort_number(episode)
        fallback_id = int(getattr(episode, "id", 0) or 0)
        if resolved_number is not None:
            return (0, int(resolved_number), fallback_id)
        return (1, fallback_id, fallback_id)

    return sorted(list(episodes or []), key=_sort_key)


_ALLOWED_REASONING_EFFORT = {"low", "medium", "high"}


from app.services.user_model_preferences import (  # noqa: E402,F401
    _inject_user_advanced_llm_preferences,
    _normalize_cfg,
    _normalize_positive_seed,
    _normalize_reasoning_effort,
    _normalize_temperature,
    _read_user_advanced_model_preferences,
)


# Creativity → temperature helpers live in script_analysis_llm_config (service layer).
from app.services.script_analysis_llm_config import (  # noqa: E402
    _extract_project_creativity_value,
    _inject_project_creativity_temperature,
    _map_project_creativity_to_temperature,
    _pick_first_non_empty_text,
)


def get_effective_api_setting(db: Session, user: User, provider: str = None, category: str = None) -> Optional[APISetting]:
    """
    Unified runtime API setting resolver.
    Uses the same flow as media generation APIs:
    user active selection -> system category default fallback.
    """
    resolved_category = str(category or "").strip()
    if not resolved_category:
        return None

    runtime_target = _resolve_media_runtime_target(
        provider=provider,
        model=None,
        media_type="runtime",
        category=resolved_category,
        user_id=user.id,
        user_credits=(user.credits or 0),
    )

    pre_api_cfg = runtime_target.get("pre_api_cfg") if isinstance(runtime_target, dict) else {}
    if not isinstance(pre_api_cfg, dict):
        pre_api_cfg = {}

    resolved_provider = str(runtime_target.get("resolved_provider") or "").strip()
    resolved_model = str(runtime_target.get("resolved_model") or "").strip()
    runtime_api_key = str((pre_api_cfg or {}).get("api_key") or "").strip()
    runtime_base_url = str((pre_api_cfg or {}).get("base_url") or "").strip()
    runtime_config = (pre_api_cfg or {}).get("config") if isinstance((pre_api_cfg or {}).get("config"), dict) else {}

    if not resolved_provider or not resolved_model or not runtime_api_key:
        logger.warning(
            "Unified effective API setting resolve failed | user_id=%s category=%s provider=%s model=%s",
            user.id,
            resolved_category,
            resolved_provider,
            resolved_model,
        )
        return None

    setting_id = _safe_int(runtime_config.get("__resolved_setting_id") or (pre_api_cfg or {}).get("system_api_id"), 0)
    if setting_id > 0:
        system_row = db.query(SystemAPISetting).filter(SystemAPISetting.id == setting_id).first()
        if system_row:
            logger.info(
                "Resolved API setting via unified runtime | user_id=%s category=%s source=system_row setting_id=%s provider=%s model=%s",
                user.id,
                resolved_category,
                system_row.id,
                system_row.provider,
                system_row.model,
            )
            return system_row

    class _RuntimeSettingShim:
        pass

    shim = _RuntimeSettingShim()
    shim.id = None
    shim.provider = resolved_provider
    shim.category = resolved_category
    shim.model = resolved_model
    shim.base_url = runtime_base_url
    shim.api_key = runtime_api_key
    shim.config = runtime_config or {}
    logger.info(
        "Resolved API setting via unified runtime | user_id=%s category=%s source=runtime_shim provider=%s model=%s",
        user.id,
        resolved_category,
        resolved_provider,
        resolved_model,
    )
    return shim


def _seed_default_system_settings_for_user(db: Session, user_id: int) -> None:
    existing_row = db.query(APISetting.id).filter(APISetting.user_id == user_id).order_by(APISetting.id.asc()).first()
    if existing_row:
        return

    task_default_rows = list_task_default_system_settings(db)
    if not task_default_rows:
        return

    new_settings: List[APISetting] = []
    seen_categories: set[str] = set()
    for row in task_default_rows.values():
        if _is_system_setting_deprecated(row.config, row.deprecated):
            continue
        category = str(row.category or "").strip()
        if not category or category in seen_categories:
            continue
        seen_categories.add(category)
        new_settings.append(APISetting(
            user_id=user_id,
            category=category,
            system_api_id=int(row.id),
            api_strategy="smart_default",
            mode=None,
        ))

    if new_settings:
        db.add_all(new_settings)




# Refresh cross-router helpers after local definitions are complete.
_bind_endpoint_helpers()

