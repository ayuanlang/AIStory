# -*- coding: utf-8 -*-
"""Market-intel report persistence and markdown builders."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.time_utils import now_bj_iso
from app.models import all_models as models
from app.models.all_models import Project, User
from app.services.billing_service import billing_service
from app.services.db_session_utils import _release_db_connection
from app.services.llm_service import llm_service
from app.services.model_invocation_billing import (
    _apply_llm_routing_to_billing_details,
    _reservation_tx_id,
)
from app.services.script_analysis_llm_config import _resolve_story_generator_script_analysis_llm_config
from app.services.story_trend_search_service import (
    current_report_month_label,
    current_report_period_label,
)

MarketIntelReport = getattr(models, "MarketIntelReport", None)

def _require_market_intel_model():
    if MarketIntelReport is None:
        raise HTTPException(status_code=503, detail="Market intel persistence is unavailable on this deployment")
    return MarketIntelReport


def _market_intel_report_to_dict(row, *, include_payload: bool = True) -> Dict[str, Any]:
    payload = dict(getattr(row, "payload_json", None) or {}) if include_payload else {}
    base = {
        "id": int(getattr(row, "id", 0) or 0),
        "project_id": int(getattr(row, "project_id", 0) or 0),
        "report_kind": str(getattr(row, "report_kind", "") or "").strip(),
        "report_month": str(getattr(row, "report_month", "") or "").strip(),
        "report_period": str(getattr(row, "report_period", "") or "").strip(),
        "fetched_at": str(getattr(row, "fetched_at", "") or "").strip(),
        "summary": str(getattr(row, "summary", "") or "").strip(),
        "markdown": str(getattr(row, "markdown", "") or "").strip() if include_payload else None,
        "created_at": str(getattr(row, "created_at", "") or "").strip(),
    }
    if include_payload:
        # Prefer full stored snapshot; fall back to row fields.
        merged = {
            **payload,
            **{k: v for k, v in base.items() if v is not None and v != ""},
            "id": base["id"],
            "project_id": base["project_id"],
            "report_kind": base["report_kind"],
            "created_at": base["created_at"],
        }
        if not merged.get("markdown"):
            merged["markdown"] = base.get("markdown") or ""
        if not merged.get("summary"):
            merged["summary"] = base.get("summary") or ""
        return merged
    return {k: v for k, v in base.items() if k != "markdown"}


def _persist_market_intel_report(
    db: Session,
    *,
    project: Project,
    report_kind: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    model = _require_market_intel_model()
    kind = str(report_kind or "").strip()
    report_month = str((payload or {}).get("report_month") or "").strip() or current_report_month_label()
    report_period = str((payload or {}).get("report_period") or "").strip() or current_report_period_label(report_month)
    fetched_at = str((payload or {}).get("fetched_at") or "").strip() or now_bj_iso()
    summary = str((payload or {}).get("summary") or "").strip()
    markdown = str((payload or {}).get("markdown") or "").strip()
    row = model(
        project_id=int(project.id),
        report_kind=kind,
        report_month=report_month,
        report_period=report_period,
        fetched_at=fetched_at,
        summary=summary,
        markdown=markdown,
        payload_json=dict(payload or {}),
        created_at=now_bj_iso(),
    )
    db.add(row)

    # Keep latest snapshot on story_generator_global_input for backward compatibility.
    gi = dict(project.global_info or {})
    draft = dict(gi.get("story_generator_global_input") or {})
    if kind == "industry_analysis":
        draft["ai_short_drama_industry_report"] = dict(payload or {})
    elif kind == "trending_dramas":
        draft["trending_ai_short_dramas_report"] = dict(payload or {})
    gi["story_generator_global_input"] = draft
    gi["story_generator_global_input_updated_at"] = now_bj_iso()
    project.global_info = gi
    flag_modified(project, "global_info")

    db.commit()
    db.refresh(row)
    return _market_intel_report_to_dict(row, include_payload=True)


def _seed_market_intel_from_global_info(db: Session, project: Project) -> int:
    """One-time seed: copy latest global_info reports into history table when empty."""
    model = _require_market_intel_model()
    existing = (
        db.query(model.id)
        .filter(model.project_id == int(project.id))
        .limit(1)
        .first()
    )
    if existing:
        return 0
    gi = dict(project.global_info or {})
    draft = dict(gi.get("story_generator_global_input") or {})
    seeded = 0
    industry = draft.get("ai_short_drama_industry_report")
    if isinstance(industry, dict) and (industry.get("markdown") or industry.get("summary")):
        payload = dict(industry)
        payload.setdefault("report_month", current_report_month_label())
        payload.setdefault("report_period", current_report_period_label(payload["report_month"]))
        payload.setdefault("fetched_at", gi.get("story_generator_global_input_updated_at") or now_bj_iso())
        row = model(
            project_id=int(project.id),
            report_kind="industry_analysis",
            report_month=str(payload.get("report_month") or ""),
            report_period=str(payload.get("report_period") or ""),
            fetched_at=str(payload.get("fetched_at") or ""),
            summary=str(payload.get("summary") or ""),
            markdown=str(payload.get("markdown") or ""),
            payload_json=payload,
            created_at=str(payload.get("fetched_at") or now_bj_iso()),
        )
        db.add(row)
        seeded += 1
    trending = draft.get("trending_ai_short_dramas_report")
    if isinstance(trending, dict) and (trending.get("markdown") or trending.get("summary") or trending.get("dramas")):
        # Skip legacy combined blob that only holds industry_analysis.
        if trending.get("industry_analysis") and not (trending.get("markdown") or trending.get("dramas")):
            pass
        else:
            payload = dict(trending)
            payload.pop("industry_analysis", None)
            payload.setdefault("report_month", current_report_month_label())
            payload.setdefault("report_period", current_report_period_label(payload["report_month"]))
            payload.setdefault("fetched_at", gi.get("story_generator_global_input_updated_at") or now_bj_iso())
            row = model(
                project_id=int(project.id),
                report_kind="trending_dramas",
                report_month=str(payload.get("report_month") or ""),
                report_period=str(payload.get("report_period") or ""),
                fetched_at=str(payload.get("fetched_at") or ""),
                summary=str(payload.get("summary") or ""),
                markdown=str(payload.get("markdown") or ""),
                payload_json=payload,
                created_at=str(payload.get("fetched_at") or now_bj_iso()),
            )
            db.add(row)
            seeded += 1
    if seeded:
        db.commit()
    return seeded


async def _run_ai_short_drama_market_llm(
    *,
    db: Session,
    current_user: User,
    project,
    req: Any,
    sys_prompt: str,
    user_prompt: str,
    billing_item: str,
    llm_context: str,
) -> Dict[str, Any]:
    function_name = (getattr(req, "function_name", None) if req else None) or "script_analysis"
    system_api_id = getattr(req, "system_api_id", None) if req else None
    llm_config = _resolve_story_generator_script_analysis_llm_config(
        db,
        int(current_user.id),
        function_name=function_name,
        system_api_id=system_api_id,
        context=llm_context,
        project_global_info=project.global_info,
    )
    if not llm_config or not (llm_config.get("api_key") or "").strip():
        raise HTTPException(status_code=400, detail="No valid LLM API key configured in active settings")
    cfg = dict(llm_config.get("config") or {})
    cfg.setdefault("response_format", {"type": "json_object"})
    llm_config = {**llm_config, "config": cfg}
    provider = llm_config.get("provider") if llm_config else None
    model = llm_config.get("model") if llm_config else None

    reservation_tx = None
    if billing_service.is_token_pricing(db, "llm_chat", provider, model):
        est = billing_service.estimate_reserve_tokens_from_messages(
            [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        reservation_tx = billing_service.reserve_credits(
            db,
            current_user.id,
            "llm_chat",
            provider,
            model,
            {
                "item": billing_item,
                "estimation_method": "prompt_tokens_ratio",
                "estimated_output_ratio": billing_service.RESERVE_OUTPUT_RATIO,
                "input_tokens": est.get("input_tokens", 0),
                "output_tokens": est.get("output_tokens", 0),
                "total_tokens": est.get("total_tokens", 0),
            },
        )
    else:
        billing_service.check_balance(db, current_user.id, "llm_chat", provider, model)

    try:
        _release_db_connection(db, f"{llm_context}_llm_call")
        resp = await llm_service.generate_content_with_fallback(user_prompt, sys_prompt, llm_config)
    except Exception as e:
        if reservation_tx:
            billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), str(e))
        raise

    raw = (resp.get("content") or "").strip()
    if not raw:
        if reservation_tx:
            billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), "LLM returned empty content")
        raise HTTPException(status_code=500, detail="LLM returned empty content")

    usage = resp.get("usage") or {}
    if not usage:
        usage = billing_service.estimate_input_output_tokens_from_messages(
            [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": raw},
            ],
            output_ratio=1.0,
        )
    billing_details = {
        "item": billing_item,
        "prompt_tokens": int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0),
        "completion_tokens": int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0),
        "total_tokens": int(
            usage.get(
                "total_tokens",
                int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0)
                + int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0),
            )
            or 0
        ),
    }
    billing_details["input_tokens"] = billing_details["prompt_tokens"]
    billing_details["output_tokens"] = billing_details["completion_tokens"]
    _apply_llm_routing_to_billing_details(billing_details, resp)

    if reservation_tx:
        billing_service.settle_reservation(db, _reservation_tx_id(reservation_tx), billing_details)
    else:
        billing_service.deduct_credits(db, current_user.id, "llm_chat", provider, model, billing_details)

    return {"raw": raw, "llm_config": llm_config}


def _industry_analysis_section_map() -> List[Tuple[str, str]]:
    return [
        ("hot_list_overview", "热榜整体变化"),
        ("genre_theme_shifts", "题材变化（核心）"),
        ("rising_genres", "上升/新热题材"),
        ("declining_genres", "降温/退潮题材"),
        ("hook_and_trope_shifts", "钩子与桥段变化"),
        ("platform_hot_list_diff", "平台热榜差异"),
        ("audience_drivers", "受众驱动因素"),
        ("creator_opportunities", "创作者选材建议"),
    ]


def _build_industry_analysis_markdown(report_period: str, summary: str, industry_analysis: Dict[str, Any]) -> str:
    lines = [f"## {report_period} AI短剧热榜与题材变化分析", "", summary.strip(), "", "## 热榜与题材变化", ""]
    for key, title in _industry_analysis_section_map():
        value = str(industry_analysis.get(key) or "").strip()
        if value:
            lines.extend([f"### {title}", value, ""])
    return "\n".join(lines).strip()


def _build_trending_dramas_markdown(report_period: str, summary: str, dramas: List[Dict[str, Any]]) -> str:
    lines = [f"## {report_period} AI短剧热榜", "", summary.strip(), "", "## 热榜作品（高潮与名场面）", ""]
    for item in dramas:
        if not isinstance(item, dict):
            continue
        lines.append(f"### {item.get('rank', '')}. {item.get('title', '')}")
        lines.append(f"- 平台：{item.get('platform', '')}")
        lines.append(f"- 新上榜：{'是' if item.get('is_new_entry') else '否'}")
        lines.append(f"- 热度：{item.get('heat_signal', '')}")
        lines.append(f"- 简介：{item.get('synopsis', '')}")
        climax = str(item.get("climax_iconic_scenes") or "").strip()
        if climax:
            lines.append(f"- 高潮/名场面：{climax}")
        dialogue = str(item.get("classic_dialogue") or "").strip()
        if dialogue:
            lines.append(f"- 经典对白：{dialogue}")
        visual_action = str(item.get("visual_action_beats") or "").strip()
        if visual_action:
            lines.append(f"- 画面/动作：{visual_action}")
        lines.append(f"- 看点：{item.get('hook_points', '')}")
        lines.append("")
    return "\n".join(lines).strip()

