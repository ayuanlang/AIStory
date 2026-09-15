# -*- coding: utf-8 -*-
"""Commercial promo planner pipeline: image analysis + four-dimension scheme."""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from fastapi import HTTPException
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time_utils import now_bj_iso
from app.models.all_models import (
    Episode,
    Project,
    PromoBrand,
    PromoCatalogAsset,
    PromoEnterprise,
    PromoImageAsset,
    PromoPlannerInput,
    PromoPlannerResult,
    PromoProduct,
    PromoProject,
)
from app.services.billing_service import billing_service
from app.services.db_session_utils import _release_db_connection, _snapshot_user_principal
from app.services.generation_runtime.media_persist import _refresh_managed_media_url
from app.services.llm_service import llm_service
from app.services.model_invocation_billing import (
    _apply_llm_routing_to_billing_details,
    _reservation_tx_id,
)
from app.services.episode_script_output import (
    EPISODE_SCRIPT_OUTPUT_END,
    EPISODE_SCRIPT_OUTPUT_START,
    extract_episode_script_output_between_markers,
    extract_official_episode_script,
)
from app.services.markdown_generation import generate_markdown_with_retry
from app.services.project_generation_defaults import _ensure_project_generation_defaults
from app.services.prompt_resolve import _resolve_prompt_text
from app.services.script_analysis_llm_config import (
    _resolve_story_generator_script_analysis_llm_config,
    sanitize_script_generation_llm_config_text_only,
)
from app.services.soft_delete import _active_episode_clause, _active_project_clause

logger = logging.getLogger("api_logger")

PROMO_IMAGE_TYPES = {"product", "character", "scene", "prop"}
PROMO_MEDIA_KINDS = {"image", "video"}
PROMO_OWNER_KINDS = {"enterprise", "brand", "offering"}
MAX_VISION_IMAGES = 12

GOAL_TYPES = (
    "品牌形象片",
    "产品卖点片",
    "引流获客片",
    "招商渠道片",
    "功能演示片",
    "活动节点片",
    "客户案例证言片",
    "企业形象片",
    "新品发布片",
    "电商带货片",
    "门店到店转化片",
    "招聘雇主品牌片",
    "上市融资路演片",
    "公益社会责任片",
    "售后服务口碑片",
    "思想领导力片",
)

NARRATIVE_MODELS = (
    "四段式（钩子-共鸣-价值爆发-收口）",
    "反差对比模型",
    "感受旅程模型",
    "微型人物小传模型",
    "一句话锚定模型",
    "承诺兑现模型",
    "时间切片模型",
    "设问递进模型",
    "权威背书模型",
    "证据递进模型",
    "内心矛盾化解模型",
    "问题解决模型",
    "前后对比蜕变模型",
    "场景代入模型",
    "悬念揭晓模型",
    "清单盘点模型",
)

PRESENTATION_FORMS = (
    "真人口播",
    "实景演绎",
    "纪实跟拍",
    "产品静物实拍",
    "MG动画",
    "三维CG动画",
    "手绘动画",
    "屏幕录屏演示",
    "素材混剪",
    "图文轮播",
    "虚拟数字人口播",
    "航拍大场面",
    "AI生成影像",
)


def _as_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if "\n" in text:
            return [part.strip() for part in text.splitlines() if part.strip()]
        return [part.strip() for part in text.replace("，", ",").split(",") if part.strip()]
    return [value]


def _text(value: Any) -> str:
    return str(value or "").strip()


def normalize_platforms(value: Any) -> List[str]:
    allowed = {"抖音", "小红书", "B站", "视频号", "知乎", "快手"}
    items = _as_list(value)
    out: List[str] = []
    seen = set()
    for item in items:
        name = _text(item)
        if name in allowed and name not in seen:
            seen.add(name)
            out.append(name)
    return out


def normalize_image_type(value: Any) -> str:
    raw = _text(value).lower()
    if raw in PROMO_IMAGE_TYPES:
        return raw
    mapping = {
        "产品": "product",
        "服务": "product",
        "角色": "character",
        "人物": "character",
        "场景": "scene",
        "环境": "scene",
        "道具": "prop",
        "物件": "prop",
    }
    return mapping.get(_text(value), "product")


def normalize_media_kind(value: Any) -> str:
    raw = _text(value).lower()
    if raw in PROMO_MEDIA_KINDS:
        return raw
    if raw in {"mp4", "webm", "mov", "video/mp4", "video/webm", "video/quicktime"}:
        return "video"
    return "image"


def normalize_owner_kind(value: Any) -> str:
    raw = _text(value).lower()
    mapping = {
        "enterprise": "enterprise",
        "company": "enterprise",
        "企业": "enterprise",
        "brand": "brand",
        "品牌": "brand",
        "offering": "offering",
        "product": "offering",
        "service": "offering",
        "产品": "offering",
        "服务": "offering",
        "产品与服务": "offering",
    }
    kind = mapping.get(raw, raw)
    if kind not in PROMO_OWNER_KINDS:
        raise HTTPException(status_code=400, detail="owner_kind must be enterprise, brand or offering")
    return kind


def dump_model(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return {}


def normalize_image_assets(raw_assets: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for item in raw_assets or []:
        data = dump_model(item)
        img_url = _text(data.get("img_url"))
        if not img_url:
            continue
        object_name = _text(data.get("object_name"))
        out.append(
            {
                "img_url": img_url,
                "image_id": _text(data.get("image_id")),
                "image_type": normalize_image_type(data.get("image_type") or data.get("asset_type")),
                "media_kind": normalize_media_kind(data.get("media_kind")),
                "owner_kind": _text(data.get("owner_kind")) or "project",
                "object_name": object_name,
                "user_remark": _text(data.get("user_remark")),
            }
        )
    return out


def normalize_planner_input(enterprise_info: Any, campaign_demand: Any) -> Dict[str, Any]:
    enterprise = dump_model(enterprise_info)
    campaign = dump_model(campaign_demand)
    try:
        episodes_count = int(campaign.get("episodes_count") or 1)
    except Exception:
        episodes_count = 1
    if episodes_count <= 0:
        episodes_count = 1
    return {
        "enterprise_info": {
            "enterprise_name": _text(enterprise.get("enterprise_name")),
            "enterprise_intro": _text(enterprise.get("enterprise_intro")),
            "brand_name": _text(enterprise.get("brand_name")),
            "brand_intro": _text(enterprise.get("brand_intro")),
            "product_name": _text(enterprise.get("product_name")),
            "product_info": _text(enterprise.get("product_info")),
            "core_selling_points": [_text(x) for x in _as_list(enterprise.get("core_selling_points")) if _text(x)],
            "differentiation": _text(enterprise.get("differentiation")),
            "target_user": _text(enterprise.get("target_user")),
            "pain_points": [_text(x) for x in _as_list(enterprise.get("pain_points")) if _text(x)],
            "competitor_problem": _text(enterprise.get("competitor_problem")),
            "image_assets": normalize_image_assets(enterprise.get("image_assets")),
        },
        "campaign_demand": {
            "user_raw_text": _text(campaign.get("user_raw_text")),
            "goal_type": _text(campaign.get("goal_type")),
            "narrative_model": _text(campaign.get("narrative_model")),
            "presentation_form": _text(campaign.get("presentation_form")),
            "platform": normalize_platforms(campaign.get("platform")),
            "expect_duration": _text(campaign.get("expect_duration")),
            "existing_material": _text(campaign.get("existing_material")),
            "constraint": _text(campaign.get("constraint")),
            "cta": _text(campaign.get("cta")),
            "episodes_count": episodes_count,
        },
    }


def empty_color_palette() -> Dict[str, Any]:
    return {
        "main_color": "",
        "secondary_colors": [],
        "accent_color": "",
        "color_tone_description": "",
    }


def empty_image_asset_analysis() -> Dict[str, Any]:
    return {
        "global_visual_summary": "",
        "global_color_palette": empty_color_palette(),
        "image_list": [],
        "analysis_warnings": [],
    }


def empty_planner_result() -> Dict[str, Any]:
    return {
        "overall_scheme": {
            "title": "",
            "one_liner": "",
            "combination_mode": "",
            "main_goal_type": "",
            "series_logic": "",
            "success_metric": "",
        },
        "content_mode": {
            "primary_mode": "",
            "mode_definition": "",
            "outline": [],
            "backup_mode": "",
            "backup_reason": "",
        },
        "video_positioning": {
            "goal_type": "",
            "communication_goal": "",
            "platforms": [],
            "duration": "",
            "rationale": "",
        },
        "narrative_plan": {
            "primary_model": "",
            "backup_model": "",
            "adaptation_reason": "",
        },
        "presentation_plan": {
            "primary_form": "",
            "form_definition": "",
            "combo_forms": [],
            "combo_rationale": "",
            "production_advice": "",
        },
        "platform_strategies": [],
        "series_schemes": [],
        "four_dimension_evaluation": {
            "goal_score": 0,
            "narrative_score": 0,
            "presentation_score": 0,
            "platform_score": 0,
            "overall_score": 0,
            "score_note": "",
            "optimization_suggestions": [],
        },
        "benchmark_analysis": {
            "visual_asset_match_level": "无资产",
            "premium_benchmarks": [],
            "viral_benchmarks": [],
            "pitfalls": [],
            "customized_improvement": "",
        },
        "structured_business_info": {
            "brand_intro": "",
            "product_info": "",
            "core_selling_points": {"primary": "", "secondary": []},
            "differentiation": "",
            "target_user": "",
            "pain_points": [],
            "competitor_problem": "",
            "communication_goal": "",
            "suggested_cta": "",
            "image_assets": [],
        },
        "missing_info_diagnosis": {
            "text_gaps": [],
            "visual_gaps": [],
        },
        "image_asset_analysis": empty_image_asset_analysis(),
        "visual_spec": {
            "color_palette": empty_color_palette(),
            "lighting_reference": "",
            "composition_advice": "",
            "color_grading": "",
            "unity_constraints": [],
        },
        "material_list": [],
        "script_preview": {
            "logline": "",
            "beats": [],
        },
        "warnings": [],
    }


def _deep_merge(base: Any, incoming: Any) -> Any:
    if isinstance(base, dict) and isinstance(incoming, dict):
        merged = dict(base)
        for key, value in incoming.items():
            if key in merged:
                merged[key] = _deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged
    if incoming is None:
        return base
    return incoming


def merge_planner_result(parsed: Any) -> Dict[str, Any]:
    return _deep_merge(empty_planner_result(), parsed if isinstance(parsed, dict) else {})


def apply_user_dimension_locks(result: Dict[str, Any], campaign: Dict[str, Any]) -> Dict[str, Any]:
    """Honor user-specified dimensions; backfill unspecified ones from the model output."""
    campaign = dump_model(campaign)
    pos = _as_dict(result.get("video_positioning"))
    narrative = _as_dict(result.get("narrative_plan"))
    presentation = _as_dict(result.get("presentation_plan"))
    goal_type = _text(campaign.get("goal_type"))
    narrative_model = _text(campaign.get("narrative_model"))
    presentation_form = _text(campaign.get("presentation_form"))
    platforms = normalize_platforms(campaign.get("platform"))
    overall = _as_dict(result.get("overall_scheme"))
    content_mode = _as_dict(result.get("content_mode"))
    if goal_type:
        pos["goal_type"] = goal_type
        overall["main_goal_type"] = goal_type
    if narrative_model:
        narrative["primary_model"] = narrative_model
        content_mode["primary_mode"] = narrative_model
    if presentation_form:
        presentation["primary_form"] = presentation_form
    if platforms:
        pos["platforms"] = platforms
    result["overall_scheme"] = overall
    result["content_mode"] = content_mode
    result["video_positioning"] = pos
    result["narrative_plan"] = narrative
    result["presentation_plan"] = presentation
    if not _text(campaign.get("narrative_model")):
        campaign["narrative_model"] = _text(narrative.get("primary_model"))
    if not _text(campaign.get("presentation_form")):
        campaign["presentation_form"] = _text(presentation.get("primary_form"))
    if not platforms:
        campaign["platform"] = pos.get("platforms") if isinstance(pos.get("platforms"), list) else []
    return campaign


def extract_json_object(text: Any) -> Optional[Dict[str, Any]]:
    if isinstance(text, dict):
        return text
    raw = _text(text)
    if not raw:
        return None
    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        raw = "\n".join(lines).strip()
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    start = raw.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape_next = False
    for index in range(start, len(raw)):
        ch = raw[index]
        if escape_next:
            escape_next = False
            continue
        if ch == "\\":
            if in_string:
                escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(raw[start : index + 1])
                    return obj if isinstance(obj, dict) else None
                except json.JSONDecodeError:
                    return None
    return None


def _guess_mime(path: str) -> str:
    ext = os.path.splitext(path)[1].lower().replace(".", "")
    if ext == "png":
        return "image/png"
    if ext == "webp":
        return "image/webp"
    return "image/jpeg"


async def resolve_image_url_for_llm(img_url: str, db: Session) -> str:
    raw = _refresh_managed_media_url(_text(img_url), db)
    if not raw:
        return ""
    path_part = None
    if raw.startswith("http"):
        parsed = urlparse(raw)
        if parsed.hostname in {"localhost", "127.0.0.1", "0.0.0.0"}:
            path_part = parsed.path.lstrip("/")
        else:
            return raw
    else:
        path_part = raw.lstrip("/")
    if not path_part:
        return raw
    candidates = [
        os.path.join(settings.BASE_DIR, "app", path_part),
        os.path.join(settings.BASE_DIR, path_part),
        os.path.join(os.getcwd(), "app", path_part),
        os.path.join(os.getcwd(), path_part),
        os.path.join(settings.UPLOAD_DIR, path_part.replace("uploads/", "", 1)),
    ]
    local_path = None
    for candidate in candidates:
        normalized = os.path.normpath(candidate)
        if os.path.isfile(normalized):
            local_path = normalized
            break
    if not local_path:
        return raw

    def _encode() -> str:
        with open(local_path, "rb") as handle:
            encoded = base64.b64encode(handle.read()).decode("utf-8")
        return f"data:{_guess_mime(local_path)};base64,{encoded}"

    try:
        return await asyncio.to_thread(_encode)
    except Exception as exc:
        logger.warning("promo planner failed to encode local image %s: %s", local_path, exc)
        return raw


def result_to_promo_markdown(result: Dict[str, Any], planner_input: Dict[str, Any]) -> str:
    data = merge_planner_result(result)
    enterprise = _as_dict(planner_input.get("enterprise_info"))
    campaign = _as_dict(planner_input.get("campaign_demand"))
    pos = _as_dict(data.get("video_positioning"))
    overall = _as_dict(data.get("overall_scheme"))
    content_mode = _as_dict(data.get("content_mode"))
    narrative = _as_dict(data.get("narrative_plan"))
    presentation = _as_dict(data.get("presentation_plan"))
    platform_strategies = data.get("platform_strategies") if isinstance(data.get("platform_strategies"), list) else []
    series_schemes = data.get("series_schemes") if isinstance(data.get("series_schemes"), list) else []
    outline = content_mode.get("outline") if isinstance(content_mode.get("outline"), list) else []
    outline_lines = []
    for idx, item in enumerate(outline, 1):
        row = item if isinstance(item, dict) else {"content": str(item)}
        outline_lines.append(
            f"{idx}. {row.get('section') or f'Section {idx}'}（{row.get('duration') or ''}）\n"
            f"   - 目的: {row.get('purpose') or ''}\n"
            f"   - 内容: {row.get('content') or ''}\n"
            f"   - 文案: {row.get('copy_hint') or ''}"
        )
    eval4 = _as_dict(data.get("four_dimension_evaluation"))
    bench = _as_dict(data.get("benchmark_analysis"))
    biz = _as_dict(data.get("structured_business_info"))
    visual = _as_dict(data.get("visual_spec"))
    palette = _as_dict(visual.get("color_palette"))
    analysis = _as_dict(data.get("image_asset_analysis"))
    script = _as_dict(data.get("script_preview"))
    materials = data.get("material_list") if isinstance(data.get("material_list"), list) else []
    beats = script.get("beats") if isinstance(script.get("beats"), list) else []
    platforms = pos.get("platforms") if isinstance(pos.get("platforms"), list) else campaign.get("platform") or []

    def bullets(items: Any) -> str:
        rows = items if isinstance(items, list) else []
        if not rows:
            return "- （空）"
        return "\n".join(f"- {json.dumps(row, ensure_ascii=False) if isinstance(row, dict) else row}" for row in rows)

    beat_lines = []
    for idx, beat in enumerate(beats, 1):
        row = beat if isinstance(beat, dict) else {"shot": str(beat)}
        beat_lines.append(
            f"{idx}. {row.get('name') or f'Beat {idx}'}（{row.get('duration') or ''}）\n"
            f"   - Shot: {row.get('shot') or ''}\n"
            f"   - Copy: {row.get('copy') or ''}\n"
            f"   - CTA: {row.get('cta') or ''}"
        )

    object_names = [
        _text(item.get("object_name"))
        for item in (enterprise.get("image_assets") or [])
        if isinstance(item, dict) and _text(item.get("object_name"))
    ]
    return "\n".join(
        [
            "# 宣传片全局框架（Promo Story DNA）",
            "",
            "## 0) 整体方案",
            f"- 方案名: {overall.get('title') or ''}",
            f"- 一句话策略: {overall.get('one_liner') or ''}",
            f"- 组合模式: {overall.get('combination_mode') or ''}",
            f"- 主片目标类型: {overall.get('main_goal_type') or pos.get('goal_type') or ''}",
            f"- 系列/改编逻辑: {overall.get('series_logic') or ''}",
            f"- 成功标准: {overall.get('success_metric') or ''}",
            "",
            "## 0.5) 内容模式与大纲",
            f"- 主模式: {content_mode.get('primary_mode') or narrative.get('primary_model') or ''}",
            f"- 模式定义: {content_mode.get('mode_definition') or ''}",
            f"- 备选模式: {content_mode.get('backup_mode') or narrative.get('backup_model') or ''}",
            f"- 备选理由: {content_mode.get('backup_reason') or ''}",
            *(outline_lines or ["- （空）"]),
            "",
            "## 0.6) 各平台策略",
            bullets(platform_strategies),
            "",
            "## 0.7) 系列方案组合",
            bullets(series_schemes),
            "",
            "## 0.8) 类型判定",
            f"- Primary Promo Type（主类型）: {pos.get('goal_type') or ''}",
            f"- Strategic Goal（战略目标）: {pos.get('communication_goal') or ''}",
            f"- Type Rationale（判定依据）: {pos.get('rationale') or ''}",
            "",
            "## 1) 项目目标与受众画像",
            f"- Enterprise（企业）: {enterprise.get('enterprise_name') or ''}",
            f"- Brand（品牌）: {enterprise.get('brand_name') or ''}",
            f"- Product / Service（产品与服务）: {enterprise.get('product_name') or ''}",
            f"- Communication Goal（传播目标）: {pos.get('communication_goal') or biz.get('communication_goal') or ''}",
            f"- Core Audience（核心受众）: {biz.get('target_user') or enterprise.get('target_user') or ''}",
            f"- Platforms（投放平台）: {' / '.join(platforms) if isinstance(platforms, list) else platforms}",
            f"- Duration（建议时长）: {pos.get('duration') or campaign.get('expect_duration') or ''}",
            "",
            "## 2) 核心主张与信息架构",
            f"- Core Promise（核心承诺）: {(_as_dict(biz.get('core_selling_points')).get('primary') or '')}",
            f"- Differentiation（差异化）: {biz.get('differentiation') or enterprise.get('differentiation') or ''}",
            f"- Suggested CTA: {biz.get('suggested_cta') or campaign.get('cta') or ''}",
            f"- Pain Points: {', '.join(biz.get('pain_points') or [])}",
            "",
            "## 3) 叙事与表现形式",
            f"- Primary Narrative（首选叙事）: {narrative.get('primary_model') or ''}",
            f"- Backup Narrative（备选叙事）: {narrative.get('backup_model') or ''}",
            f"- Adaptation Reason: {narrative.get('adaptation_reason') or ''}",
            f"- Primary Form（主形式）: {presentation.get('primary_form') or ''}",
            f"- Form Definition: {presentation.get('form_definition') or ''}",
            f"- Combo Forms（组合形式）: {', '.join(presentation.get('combo_forms') or [])}",
            f"- Combo Rationale: {presentation.get('combo_rationale') or ''}",
            f"- Production Advice: {presentation.get('production_advice') or ''}",
            "",
            "## 3.5) 四维适配评估",
            f"- Goal/Narrative/Presentation/Platform: {eval4.get('goal_score')}/{eval4.get('narrative_score')}/{eval4.get('presentation_score')}/{eval4.get('platform_score')}",
            f"- Overall: {eval4.get('overall_score')}",
            f"- Note: {eval4.get('score_note') or ''}",
            bullets(eval4.get("optimization_suggestions")),
            "",
            "## 4) 行业对标",
            f"- Visual Asset Match Level: {bench.get('visual_asset_match_level') or ''}",
            f"- Customized Improvement: {bench.get('customized_improvement') or ''}",
            "### 顶级标杆",
            bullets(bench.get("premium_benchmarks")),
            "### 行业爆款",
            bullets(bench.get("viral_benchmarks")),
            "### 避坑",
            bullets(bench.get("pitfalls")),
            "",
            "## 5) 成片视觉规范",
            f"- Global Summary: {analysis.get('global_visual_summary') or ''}",
            f"- Main Color: {palette.get('main_color') or ''}",
            f"- Tone: {palette.get('color_tone_description') or ''}",
            f"- Lighting: {visual.get('lighting_reference') or ''}",
            f"- Composition: {visual.get('composition_advice') or ''}",
            f"- Color Grading: {visual.get('color_grading') or ''}",
            f"- Unity: {', '.join(visual.get('unity_constraints') or [])}",
            f"- Named Assets: {', '.join(object_names)}",
            "",
            "## 6) 素材采集清单",
            bullets(materials),
            "",
            "## 7) 成片脚本方向预览",
            f"- Logline: {script.get('logline') or ''}",
            *(beat_lines or ["- （空）"]),
            "",
            "## 8) 执行注意事项",
            f"- Constraints: {campaign.get('constraint') or ''}",
            f"- Existing Material: {campaign.get('existing_material') or ''}",
            f"- Warnings: {', '.join(data.get('warnings') or [])}",
        ]
    )


def _legacy_promo_generator_input(planner_input: Dict[str, Any]) -> Dict[str, Any]:
    enterprise = _as_dict(planner_input.get("enterprise_info"))
    campaign = _as_dict(planner_input.get("campaign_demand"))
    platforms = campaign.get("platform") or []
    return {
        "mode": "global",
        "generator_kind": "promo",
        "episodes_count": int(campaign.get("episodes_count") or 1),
        "campaign_objective": _text(campaign.get("user_raw_text")),
        "target_audience": _text(enterprise.get("target_user")),
        "key_message": "；".join(enterprise.get("core_selling_points") or []),
        "core_highlights": _text(enterprise.get("product_info")),
        "credibility_proof": _text(enterprise.get("differentiation")),
        "conversion_cta": _text(campaign.get("cta")),
        "channel_context": " / ".join(platforms) if isinstance(platforms, list) else _text(platforms),
        "constraints": _text(campaign.get("constraint")),
        "promo_planner": True,
    }


def _active_promo_clause():
    return PromoProject.is_deleted.is_(False)


def require_promo_project_access(
    db: Session,
    promo_project_id: int,
    current_user: Any,
    *,
    owner_only: bool = False,
) -> PromoProject:
    from fastapi import HTTPException
    from app.api.deps import is_current_http_mutating

    project = (
        db.query(PromoProject)
        .filter(PromoProject.id == promo_project_id, _active_promo_clause())
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Promo project not found")

    is_owner = project.owner_id == current_user.id
    if is_owner:
        return project

    is_superuser = bool(getattr(current_user, "is_superuser", False))
    is_root = is_superuser and str(getattr(current_user, "username", "")).strip().lower() == "ylsystem"
    if is_root:
        return project
    if owner_only:
        raise HTTPException(status_code=403, detail="This action is restricted to project owner")
    if is_superuser:
        if is_current_http_mutating():
            raise HTTPException(status_code=403, detail="Superuser temporary project view is read-only")
        return project
    raise HTTPException(status_code=403, detail="Not authorized")


def _can_manage_promo_catalog(row: Any, current_user: Any, *, owner_only: bool = False) -> Any:
    from fastapi import HTTPException
    from app.api.deps import is_current_http_mutating

    is_owner = int(getattr(row, "owner_id", 0) or 0) == int(getattr(current_user, "id", 0) or 0)
    if is_owner:
        return row
    is_superuser = bool(getattr(current_user, "is_superuser", False))
    is_root = is_superuser and str(getattr(current_user, "username", "")).strip().lower() == "ylsystem"
    if is_root:
        return row
    if owner_only:
        raise HTTPException(status_code=403, detail="This action is restricted to owner")
    if is_superuser:
        if is_current_http_mutating():
            raise HTTPException(status_code=403, detail="Superuser temporary view is read-only")
        return row
    raise HTTPException(status_code=403, detail="Not authorized")


def require_promo_enterprise_access(
    db: Session,
    enterprise_id: int,
    current_user: Any,
    *,
    owner_only: bool = False,
) -> PromoEnterprise:
    from fastapi import HTTPException

    row = (
        db.query(PromoEnterprise)
        .filter(PromoEnterprise.id == enterprise_id, PromoEnterprise.is_deleted.is_(False))
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Enterprise not found")
    return _can_manage_promo_catalog(row, current_user, owner_only=owner_only)


def require_promo_brand_access(
    db: Session,
    brand_id: int,
    current_user: Any,
    *,
    owner_only: bool = False,
) -> PromoBrand:
    from fastapi import HTTPException

    row = (
        db.query(PromoBrand)
        .filter(PromoBrand.id == brand_id, PromoBrand.is_deleted.is_(False))
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Brand not found")
    return _can_manage_promo_catalog(row, current_user, owner_only=owner_only)


def require_promo_product_access(
    db: Session,
    product_id: int,
    current_user: Any,
    *,
    owner_only: bool = False,
) -> PromoProduct:
    from fastapi import HTTPException

    row = (
        db.query(PromoProduct)
        .filter(PromoProduct.id == product_id, PromoProduct.is_deleted.is_(False))
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    return _can_manage_promo_catalog(row, current_user, owner_only=owner_only)


def serialize_promo_enterprise(db: Session, row: PromoEnterprise) -> Dict[str, Any]:
    brand_count = (
        db.query(PromoBrand)
        .filter(PromoBrand.enterprise_id == row.id, PromoBrand.is_deleted.is_(False))
        .count()
    )
    product_count = (
        db.query(PromoProduct)
        .filter(PromoProduct.enterprise_id == row.id, PromoProduct.is_deleted.is_(False))
        .count()
    )
    return {
        "id": row.id,
        "name": row.name or "",
        "intro": row.intro or "",
        "extra_info": dict(row.extra_info or {}),
        "owner_id": row.owner_id,
        "brand_count": int(brand_count or 0),
        "product_count": int(product_count or 0),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def serialize_promo_brand(db: Session, row: PromoBrand) -> Dict[str, Any]:
    enterprise = getattr(row, "enterprise", None)
    product_count = (
        db.query(PromoProduct)
        .filter(PromoProduct.brand_id == row.id, PromoProduct.is_deleted.is_(False))
        .count()
    )
    return {
        "id": row.id,
        "enterprise_id": row.enterprise_id,
        "enterprise_name": (enterprise.name if enterprise else "") or "",
        "name": row.name or "",
        "intro": row.intro or "",
        "extra_info": dict(row.extra_info or {}),
        "owner_id": row.owner_id,
        "product_count": int(product_count or 0),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def serialize_promo_product(row: PromoProduct) -> Dict[str, Any]:
    enterprise = getattr(row, "enterprise", None)
    brand = getattr(row, "brand", None)
    return {
        "id": row.id,
        "enterprise_id": row.enterprise_id,
        "enterprise_name": (enterprise.name if enterprise else "") or "",
        "brand_id": row.brand_id,
        "brand_name": (brand.name if brand else "") or "",
        "name": row.name or "",
        "product_info": row.product_info or "",
        "core_selling_points": [_text(x) for x in _as_list(row.core_selling_points) if _text(x)],
        "differentiation": row.differentiation or "",
        "target_user": row.target_user or "",
        "pain_points": [_text(x) for x in _as_list(row.pain_points) if _text(x)],
        "competitor_problem": row.competitor_problem or "",
        "extra_info": dict(row.extra_info or {}),
        "owner_id": row.owner_id,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def serialize_promo_catalog_asset(row: PromoCatalogAsset) -> Dict[str, Any]:
    url = _text(row.file_url)
    asset_type = normalize_image_type(row.asset_type)
    return {
        "id": row.id,
        "owner_id": row.owner_id,
        "owner_kind": row.owner_kind,
        "owner_entity_id": row.owner_entity_id,
        "media_kind": normalize_media_kind(row.media_kind),
        "asset_type": asset_type,
        "image_type": asset_type,
        "image_id": row.image_id or "",
        "file_url": url,
        "img_url": url,
        "object_name": row.object_name or "",
        "user_remark": row.user_remark or "",
        "extra_info": dict(row.extra_info or {}),
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def list_catalog_assets(
    db: Session,
    *,
    owner_kind: str,
    owner_entity_id: int,
) -> List[Dict[str, Any]]:
    kind = normalize_owner_kind(owner_kind)
    rows = (
        db.query(PromoCatalogAsset)
        .filter(
            PromoCatalogAsset.is_deleted.is_(False),
            PromoCatalogAsset.owner_kind == kind,
            PromoCatalogAsset.owner_entity_id == int(owner_entity_id),
        )
        .order_by(PromoCatalogAsset.id.desc())
        .all()
    )
    return [serialize_promo_catalog_asset(row) for row in rows]


def collect_catalog_image_assets(
    db: Session,
    *,
    enterprise: Optional[PromoEnterprise] = None,
    brand: Optional[PromoBrand] = None,
    product: Optional[PromoProduct] = None,
) -> List[Dict[str, Any]]:
    pairs = []
    if enterprise is not None:
        pairs.append(("enterprise", enterprise.id))
    if brand is not None:
        pairs.append(("brand", brand.id))
    if product is not None:
        pairs.append(("offering", product.id))
    out: List[Dict[str, Any]] = []
    seen = set()
    for kind, entity_id in pairs:
        for item in list_catalog_assets(db, owner_kind=kind, owner_entity_id=int(entity_id)):
            key = item.get("image_id") or item.get("img_url")
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            out.append(
                {
                    "img_url": item.get("img_url") or "",
                    "image_id": item.get("image_id") or "",
                    "image_type": item.get("image_type") or "product",
                    "media_kind": item.get("media_kind") or "image",
                    "owner_kind": item.get("owner_kind") or kind,
                    "object_name": item.get("object_name") or "",
                    "user_remark": item.get("user_remark") or "",
                }
            )
    return out


def require_catalog_owner(
    db: Session,
    current_user: Any,
    owner_kind: str,
    owner_entity_id: int,
    *,
    owner_only: bool = False,
) -> Any:
    kind = normalize_owner_kind(owner_kind)
    if kind == "enterprise":
        return require_promo_enterprise_access(db, int(owner_entity_id), current_user, owner_only=owner_only)
    if kind == "brand":
        return require_promo_brand_access(db, int(owner_entity_id), current_user, owner_only=owner_only)
    return require_promo_product_access(db, int(owner_entity_id), current_user, owner_only=owner_only)


def snapshot_from_catalog(
    enterprise: Optional[PromoEnterprise],
    product: Optional[PromoProduct],
    *,
    brand: Optional[PromoBrand] = None,
    image_assets: Optional[List[Dict[str, Any]]] = None,
    overlay: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    overlay = overlay or {}
    if brand is None and product is not None:
        brand = getattr(product, "brand", None)
    return {
        "enterprise_name": _text((enterprise.name if enterprise else "") or overlay.get("enterprise_name")),
        "enterprise_intro": _text((enterprise.intro if enterprise else "") or overlay.get("enterprise_intro")),
        "brand_name": _text((brand.name if brand else "") or overlay.get("brand_name")),
        "brand_intro": _text((brand.intro if brand else "") or overlay.get("brand_intro")),
        "product_name": _text((product.name if product else "") or overlay.get("product_name")),
        "product_info": _text((product.product_info if product else "") or overlay.get("product_info")),
        "core_selling_points": (
            [_text(x) for x in _as_list(product.core_selling_points) if _text(x)]
            if product
            else [_text(x) for x in _as_list(overlay.get("core_selling_points")) if _text(x)]
        ),
        "differentiation": _text((product.differentiation if product else "") or overlay.get("differentiation")),
        "target_user": _text((product.target_user if product else "") or overlay.get("target_user")),
        "pain_points": (
            [_text(x) for x in _as_list(product.pain_points) if _text(x)]
            if product
            else [_text(x) for x in _as_list(overlay.get("pain_points")) if _text(x)]
        ),
        "competitor_problem": _text((product.competitor_problem if product else "") or overlay.get("competitor_problem")),
        "image_assets": normalize_image_assets(image_assets if image_assets is not None else overlay.get("image_assets")),
    }


def apply_catalog_overlay(
    enterprise: Optional[PromoEnterprise],
    product: Optional[PromoProduct],
    overlay: Optional[Dict[str, Any]],
) -> None:
    data = dump_model(overlay)
    if not data:
        return
    now_iso = now_bj_iso()
    if product is not None:
        if "product_name" in data and _text(data.get("product_name")):
            product.name = _text(data.get("product_name"))
        if "product_info" in data:
            product.product_info = _text(data.get("product_info")) or None
        if "core_selling_points" in data:
            product.core_selling_points = [_text(x) for x in _as_list(data.get("core_selling_points")) if _text(x)]
        if "differentiation" in data:
            product.differentiation = _text(data.get("differentiation")) or None
        if "target_user" in data:
            product.target_user = _text(data.get("target_user")) or None
        if "pain_points" in data:
            product.pain_points = [_text(x) for x in _as_list(data.get("pain_points")) if _text(x)]
        if "competitor_problem" in data:
            product.competitor_problem = _text(data.get("competitor_problem")) or None
        product.updated_at = now_iso


def bind_promo_catalog(
    db: Session,
    project: PromoProject,
    current_user: Any,
    *,
    enterprise_id: Any = None,
    brand_id: Any = None,
    product_id: Any = None,
    overlay: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[PromoEnterprise], Optional[PromoBrand], Optional[PromoProduct]]:
    from fastapi import HTTPException

    ent_id = int(enterprise_id or 0) or None
    br_id = int(brand_id or 0) or None
    prod_id = int(product_id or 0) or None
    enterprise = require_promo_enterprise_access(db, ent_id, current_user) if ent_id else None
    brand = require_promo_brand_access(db, br_id, current_user) if br_id else None
    product = require_promo_product_access(db, prod_id, current_user) if prod_id else None
    if product and not brand and getattr(product, "brand_id", None):
        brand = require_promo_brand_access(db, int(product.brand_id), current_user)
    if product and not enterprise:
        enterprise = require_promo_enterprise_access(db, int(product.enterprise_id), current_user)
    if brand and not enterprise:
        enterprise = require_promo_enterprise_access(db, int(brand.enterprise_id), current_user)
    if brand and enterprise and int(brand.enterprise_id) != int(enterprise.id):
        raise HTTPException(status_code=400, detail="Brand does not belong to the selected enterprise")
    if product and enterprise and int(product.enterprise_id) != int(enterprise.id):
        raise HTTPException(status_code=400, detail="Product does not belong to the selected enterprise")
    if product and brand and product.brand_id and int(product.brand_id) != int(brand.id):
        raise HTTPException(status_code=400, detail="Product does not belong to the selected brand")
    apply_catalog_overlay(enterprise, product, overlay)
    project.enterprise_id = enterprise.id if enterprise else None
    project.brand_id = brand.id if brand else None
    project.product_id = product.id if product else None
    return enterprise, brand, product


def _get_or_create_input_row(db: Session, promo_project_id: int) -> PromoPlannerInput:
    row = db.query(PromoPlannerInput).filter(PromoPlannerInput.promo_project_id == promo_project_id).first()
    if row:
        return row
    row = PromoPlannerInput(promo_project_id=promo_project_id, enterprise_info={}, campaign_demand={})
    db.add(row)
    db.flush()
    return row


def _get_or_create_result_row(db: Session, promo_project_id: int) -> PromoPlannerResult:
    row = db.query(PromoPlannerResult).filter(PromoPlannerResult.promo_project_id == promo_project_id).first()
    if row:
        return row
    row = PromoPlannerResult(promo_project_id=promo_project_id, result={})
    db.add(row)
    db.flush()
    return row


def sync_promo_image_assets(db: Session, promo_project_id: int, assets: List[Dict[str, Any]]) -> None:
    existing = {
        _text(row.image_id): row
        for row in db.query(PromoImageAsset).filter(PromoImageAsset.promo_project_id == promo_project_id).all()
    }
    seen = set()
    now_iso = now_bj_iso()
    for asset in assets or []:
        owner_kind = _text(asset.get("owner_kind")) or "project"
        if owner_kind and owner_kind != "project":
            continue
        image_id = _text(asset.get("image_id"))
        img_url = _text(asset.get("img_url") or asset.get("file_url"))
        if not image_id or not img_url:
            continue
        seen.add(image_id)
        row = existing.get(image_id)
        if row:
            row.img_url = img_url
            row.image_type = normalize_image_type(asset.get("image_type"))
            row.object_name = _text(asset.get("object_name"))
            row.user_remark = _text(asset.get("user_remark"))
            row.updated_at = now_iso
        else:
            db.add(
                PromoImageAsset(
                    promo_project_id=promo_project_id,
                    image_id=image_id,
                    img_url=img_url,
                    image_type=normalize_image_type(asset.get("image_type")),
                    object_name=_text(asset.get("object_name")),
                    user_remark=_text(asset.get("user_remark")),
                )
            )
    for image_id, row in existing.items():
        if image_id not in seen:
            db.delete(row)


def _promo_project_id(project: Any = None, fallback: Optional[int] = None) -> int:
    try:
        pid = int(fallback or 0)
        if pid:
            return pid
    except Exception:
        pass
    if project is None:
        return 0
    try:
        identity = sa_inspect(project).identity
        if identity and identity[0]:
            return int(identity[0])
    except Exception:
        pass
    try:
        state = getattr(project, "_sa_instance_state", None)
        cached = getattr(state, "dict", None) or {}
        if "id" in cached and cached.get("id"):
            return int(cached["id"])
    except Exception:
        pass
    return 0


def rebind_promo_project(db: Session, project: Any = None, project_id: Optional[int] = None) -> PromoProject:
    """Reload a session-bound PromoProject after LLM releases the DB connection."""
    pid = _promo_project_id(project, project_id)
    if not pid:
        raise HTTPException(status_code=404, detail="Promo project not found")
    row = (
        db.query(PromoProject)
        .filter(PromoProject.id == pid, _active_promo_clause())
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Promo project not found")
    return row


def persist_planner_state(
    db: Session,
    project: Any = None,
    *,
    project_id: Optional[int] = None,
    planner_input: Optional[Dict[str, Any]] = None,
    planner_result: Optional[Dict[str, Any]] = None,
    markdown: Optional[str] = None,
) -> Dict[str, Any]:
    project = rebind_promo_project(db, project, project_id)
    pid = int(project.id)
    now_iso = now_bj_iso()
    if planner_input is not None:
        row = _get_or_create_input_row(db, pid)
        row.enterprise_info = planner_input.get("enterprise_info") or {}
        row.campaign_demand = planner_input.get("campaign_demand") or {}
        row.updated_at = now_iso
        sync_promo_image_assets(db, pid, (row.enterprise_info or {}).get("image_assets") or [])
    if planner_result is not None or markdown is not None:
        result_row = _get_or_create_result_row(db, pid)
        if planner_result is not None:
            result_row.result = planner_result
        if markdown is not None:
            result_row.promo_dna_md = markdown
        result_row.updated_at = now_iso
    project.updated_at = now_iso
    return load_planner_state(db, project)


def load_planner_state(db: Session, project: PromoProject) -> Dict[str, Any]:
    input_row = db.query(PromoPlannerInput).filter(PromoPlannerInput.promo_project_id == project.id).first()
    result_row = db.query(PromoPlannerResult).filter(PromoPlannerResult.promo_project_id == project.id).first()
    planner_input = None
    if input_row:
        planner_input = {
            "enterprise_info": dict(input_row.enterprise_info or {}),
            "campaign_demand": dict(input_row.campaign_demand or {}),
        }
    return {
        "promo_planner_input": planner_input,
        "promo_planner_result": dict(result_row.result or {}) if result_row and result_row.result else None,
        "promo_dna_global_md": (result_row.promo_dna_md or "") if result_row else "",
    }


def serialize_promo_project(db: Session, project: PromoProject, current_user: Any) -> Dict[str, Any]:
    state = load_planner_state(db, project)
    assets = list((state.get("promo_planner_input") or {}).get("enterprise_info", {}).get("image_assets") or [])
    cover = ""
    for item in assets:
        if isinstance(item, dict) and _text(item.get("img_url")):
            cover = _text(item.get("img_url"))
            break
    is_owner = int(getattr(project, "owner_id", 0) or 0) == int(getattr(current_user, "id", 0) or 0)
    is_superuser = bool(getattr(current_user, "is_superuser", False))
    is_root = is_superuser and str(getattr(current_user, "username", "")).strip().lower() == "ylsystem"
    is_temp_view = bool(is_superuser and not is_owner and not is_root)
    script_meta = load_promo_script_meta(db, project)
    enterprise = None
    brand = None
    product = None
    if getattr(project, "enterprise_id", None):
        enterprise = db.query(PromoEnterprise).filter(
            PromoEnterprise.id == project.enterprise_id,
            PromoEnterprise.is_deleted.is_(False),
        ).first()
    if getattr(project, "brand_id", None):
        brand = db.query(PromoBrand).filter(
            PromoBrand.id == project.brand_id,
            PromoBrand.is_deleted.is_(False),
        ).first()
    if getattr(project, "product_id", None):
        product = db.query(PromoProduct).filter(
            PromoProduct.id == project.product_id,
            PromoProduct.is_deleted.is_(False),
        ).first()
    return {
        "id": project.id,
        "title": project.title or "",
        "description": project.description or "",
        "extra_info": dict(project.extra_info or {}),
        "owner_id": project.owner_id,
        "enterprise_id": project.enterprise_id,
        "brand_id": project.brand_id,
        "product_id": project.product_id,
        "enterprise": serialize_promo_enterprise(db, enterprise) if enterprise else None,
        "brand": serialize_promo_brand(db, brand) if brand else None,
        "product": serialize_promo_product(product) if product else None,
        "kind": "promo",
        "cover_image": cover or None,
        "cover_images": [cover] if cover else [],
        "promo_planner_input": state.get("promo_planner_input"),
        "promo_planner_result": state.get("promo_planner_result"),
        "promo_dna_global_md": state.get("promo_dna_global_md") or "",
        "linked_story_project_id": script_meta.get("linked_story_project_id"),
        "script_episode_id": script_meta.get("script_episode_id"),
        "has_script": bool(script_meta.get("has_script")),
        "is_owner": is_owner,
        "is_temp_view": is_temp_view,
        "can_edit": bool(is_owner or is_root),
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }


def _json_llm_config(llm_config: Dict[str, Any]) -> Dict[str, Any]:
    cfg = dict(llm_config.get("config") or {})
    cfg.setdefault("response_format", {"type": "json_object"})
    return {**llm_config, "config": cfg}


async def _run_json_llm(
    db: Session,
    *,
    current_user: Any,
    llm_config: Dict[str, Any],
    system_prompt: str,
    user_prompt: str,
    image_urls: Optional[List[str]] = None,
    billing_item: str,
    release_db: bool = True,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    llm_config = _json_llm_config(llm_config)
    provider = llm_config.get("provider")
    model = llm_config.get("model")
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    reservation_tx = None
    if billing_service.is_token_pricing(db, "llm_chat", provider, model):
        est = billing_service.estimate_reserve_tokens_from_messages(messages)
        extra_image_tokens = 900 * len(image_urls or [])
        est_input = int(est.get("input_tokens", 0) or 0) + extra_image_tokens
        est_output = int(est.get("output_tokens", 0) or 0)
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
                "estimated_image_tokens": extra_image_tokens,
                "input_tokens": est_input,
                "output_tokens": est_output,
                "total_tokens": est_input + est_output,
            },
        )
    else:
        billing_service.check_balance(db, current_user.id, "llm_chat", provider, model)

    if release_db:
        _release_db_connection(db, f"{billing_item}_llm_call")
    try:
        resp = await llm_service.generate_content_with_fallback(
            user_prompt,
            system_prompt,
            llm_config,
            image_urls=image_urls or None,
        )
    except Exception as exc:
        if reservation_tx:
            billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), str(exc))
        raise

    raw = resp.get("content")
    parsed = extract_json_object(raw)
    if not parsed:
        if reservation_tx:
            billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), "LLM returned empty or invalid JSON")
        raise HTTPException(status_code=500, detail="LLM returned empty or invalid JSON")

    usage = resp.get("usage") if isinstance(resp, dict) else {}
    if not usage:
        usage = billing_service.estimate_input_output_tokens_from_messages(
            messages + [{"role": "assistant", "content": json.dumps(parsed, ensure_ascii=False)}],
            output_ratio=1.0,
        )
    settle_details = {
        "item": billing_item,
        "prompt_tokens": int((usage or {}).get("prompt_tokens", (usage or {}).get("input_tokens", 0)) or 0),
        "completion_tokens": int((usage or {}).get("completion_tokens", (usage or {}).get("output_tokens", 0)) or 0),
    }
    settle_details["total_tokens"] = int(
        (usage or {}).get("total_tokens", settle_details["prompt_tokens"] + settle_details["completion_tokens"]) or 0
    )
    settle_details["input_tokens"] = settle_details["prompt_tokens"]
    settle_details["output_tokens"] = settle_details["completion_tokens"]
    _apply_llm_routing_to_billing_details(settle_details, resp)
    if reservation_tx:
        billing_service.settle_reservation(db, _reservation_tx_id(reservation_tx), settle_details)
    else:
        billing_service.deduct_credits(db, current_user.id, "llm_chat", provider, model, settle_details)
    return parsed, resp if isinstance(resp, dict) else {}


def _build_image_analysis_user_prompt(assets: List[Dict[str, Any]]) -> str:
    lines = [
        "请按系统约定解析下列视觉图片资产。图片按顺序附在本消息后。",
        "每张图片的元数据如下：",
    ]
    for idx, asset in enumerate(assets, 1):
        lines.append(
            f"{idx}. image_id={asset.get('image_id') or ''} | image_type={asset.get('image_type') or ''} "
            f"| object_name={asset.get('object_name') or ''} | user_remark={asset.get('user_remark') or ''}"
        )
    lines.append("只输出 JSON。")
    return "\n".join(lines)


def _build_scheme_user_prompt(
    planner_input: Dict[str, Any],
    image_analysis: Dict[str, Any],
    warnings: List[str],
) -> str:
    payload = {
        "enterprise_info": planner_input.get("enterprise_info") or {},
        "campaign_demand": planner_input.get("campaign_demand") or {},
        "image_asset_analysis": image_analysis or empty_image_asset_analysis(),
        "pipeline_warnings": warnings,
        "closed_sets": {
            "goal_types": list(GOAL_TYPES),
            "narrative_models": list(NARRATIVE_MODELS),
            "presentation_forms": list(PRESENTATION_FORMS),
        },
        "user_locks": {
            "goal_type_required": True,
            "goal_type": (planner_input.get("campaign_demand") or {}).get("goal_type") or "",
            "narrative_model": (planner_input.get("campaign_demand") or {}).get("narrative_model") or "",
            "presentation_form": (planner_input.get("campaign_demand") or {}).get("presentation_form") or "",
            "platforms": (planner_input.get("campaign_demand") or {}).get("platform") or [],
        },
    }
    return (
        "请基于以下一次性提交的企业信息、宣传诉求与图片解析结果，作为独立 skill 输出一份完整整体方案 JSON。\n"
        "必须包含：内容模式+内容大纲、视频表现形式、各平台策略、以及系列/组合模式（单片全案|主片+平台改编|系列组合）。\n"
        "宣传目标类型 goal_type 为用户必填锁定项，必须原样写入 video_positioning.goal_type 与 overall_scheme.main_goal_type，不得改判。\n"
        "内容类型 narrative_model、视频表现形式 presentation_form、投放平台 platform 若用户已填则锁定；若为空则由你分析回填，并写回对应输出字段。\n"
        "每个投放平台必须有一条 platform_strategies。未识别字段留空，并写入 missing_info_diagnosis。素材、大纲与脚本必须引用 object_name。\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


async def analyze_promo_images(
    db: Session,
    *,
    current_user: Any,
    llm_config: Dict[str, Any],
    assets: List[Dict[str, Any]],
) -> Tuple[Dict[str, Any], List[str]]:
    warnings: List[str] = []
    if not assets:
        return empty_image_asset_analysis(), warnings

    resolved: List[Tuple[Dict[str, Any], str]] = []
    vision_assets = [
        asset for asset in (assets or [])
        if normalize_media_kind(asset.get("media_kind")) == "image"
    ]
    for asset in vision_assets[:MAX_VISION_IMAGES]:
        try:
            url = await resolve_image_url_for_llm(asset.get("img_url") or "", db)
        except Exception as exc:
            logger.warning("promo image resolve failed: %s", exc)
            url = ""
        if not url:
            warnings.append(f"图片 {asset.get('object_name') or asset.get('image_id') or ''} 无法读取，已跳过视觉解析")
            continue
        resolved.append((asset, url))

    if len(assets) > MAX_VISION_IMAGES:
        warnings.append(f"视觉解析最多处理 {MAX_VISION_IMAGES} 张，其余仅保留文本元数据")

    if not resolved:
        analysis = empty_image_asset_analysis()
        analysis["analysis_warnings"] = warnings or ["全部图片无法送入视觉模型"]
        warnings.append("图片识别失败，已仅使用文本信息继续生成方案")
        return analysis, warnings

    try:
        system_prompt = _resolve_prompt_text("promo_planner_image_analysis.md")
        parsed, _resp = await _run_json_llm(
            db,
            current_user=current_user,
            llm_config=llm_config,
            system_prompt=system_prompt,
            user_prompt=_build_image_analysis_user_prompt([item[0] for item in resolved]),
            image_urls=[item[1] for item in resolved],
            billing_item="promo_planner_image_analysis",
            release_db=False,
        )
    except Exception as exc:
        logger.warning("promo image analysis failed, continue with text only: %s", exc)
        warnings.append("图片识别失败，已仅使用文本信息继续生成方案")
        analysis = empty_image_asset_analysis()
        analysis["analysis_warnings"] = [str(exc)]
        return analysis, warnings

    analysis = _deep_merge(empty_image_asset_analysis(), parsed)
    image_list = analysis.get("image_list") if isinstance(analysis.get("image_list"), list) else []
    by_id = {
        _text(item.get("image_id")): item
        for item in image_list
        if isinstance(item, dict) and _text(item.get("image_id"))
    }
    synced: List[Dict[str, Any]] = []
    for asset in assets:
        row = dict(by_id.get(asset.get("image_id") or "") or {})
        row["image_id"] = asset.get("image_id") or row.get("image_id") or ""
        row["image_type"] = asset.get("image_type") or row.get("image_type") or "product"
        row["object_name"] = asset.get("object_name") or row.get("object_name") or row.get("reference_name") or ""
        row["user_remark"] = asset.get("user_remark") or ""
        row["reference_name"] = row.get("reference_name") or row.get("object_name") or ""
        if not _text(row.get("content_desc")):
            row["content_desc"] = "识别失败或未返回描述"
            row["available_asset_hint"] = row.get("available_asset_hint") or "识别失败，仅作弱参考"
            warnings.append(f"图片 {row['object_name'] or row['image_id']} 识别不完整")
        synced.append(row)
    analysis["image_list"] = synced
    existing_warnings = analysis.get("analysis_warnings") if isinstance(analysis.get("analysis_warnings"), list) else []
    analysis["analysis_warnings"] = [*existing_warnings, *warnings]
    return analysis, warnings


async def generate_promo_planner_scheme(
    db: Session,
    *,
    project: Any,
    current_user: Any,
    req: Any,
) -> Dict[str, Any]:
    project_id = _promo_project_id(project)
    if not project_id:
        raise HTTPException(status_code=404, detail="Promo project not found")
    extra_info = dict(getattr(project, "extra_info", None) or {})
    user_snap = _snapshot_user_principal(current_user)
    overlay = dump_model(getattr(req, "enterprise_info", None))
    enterprise, brand, product = bind_promo_catalog(
        db,
        project,
        current_user,
        enterprise_id=getattr(req, "enterprise_id", None),
        brand_id=getattr(req, "brand_id", None),
        product_id=getattr(req, "product_id", None),
        overlay=overlay,
    )
    merged_assets = normalize_image_assets(overlay.get("image_assets"))
    catalog_assets = collect_catalog_image_assets(db, enterprise=enterprise, brand=brand, product=product)
    seen = {item.get("image_id") or item.get("img_url") for item in merged_assets}
    for item in catalog_assets:
        key = item.get("image_id") or item.get("img_url")
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        merged_assets.append(item)
    planner_input = normalize_planner_input(
        snapshot_from_catalog(enterprise, product, brand=brand, image_assets=merged_assets, overlay=overlay),
        getattr(req, "campaign_demand", None),
    )
    if not _text((planner_input.get("campaign_demand") or {}).get("goal_type")):
        raise HTTPException(status_code=400, detail="宣传目标类型为必填")
    persist_planner_state(db, project_id=project_id, planner_input=planner_input)
    db.commit()

    llm_config = _resolve_story_generator_script_analysis_llm_config(
        db,
        int(user_snap.id),
        function_name=(getattr(req, "function_name", None) or "script_analysis"),
        system_api_id=getattr(req, "system_api_id", None),
        context="generate_promo_planner",
        project_global_info=extra_info,
    )
    if not llm_config or not (llm_config.get("api_key") or "").strip():
        raise HTTPException(status_code=400, detail="No valid LLM API key configured in active settings")

    assets = planner_input["enterprise_info"]["image_assets"]
    image_analysis, warnings = await analyze_promo_images(
        db,
        current_user=user_snap,
        llm_config=llm_config,
        assets=assets,
    )

    system_prompt = _resolve_prompt_text("promo_planner_scheme.md")
    parsed, _resp = await _run_json_llm(
        db,
        current_user=user_snap,
        llm_config=llm_config,
        system_prompt=system_prompt,
        user_prompt=_build_scheme_user_prompt(planner_input, image_analysis, warnings),
        billing_item="promo_planner_scheme",
    )
    result = merge_planner_result(parsed)
    planner_input["campaign_demand"] = apply_user_dimension_locks(result, planner_input.get("campaign_demand") or {})
    result["image_asset_analysis"] = image_analysis
    biz = _as_dict(result.get("structured_business_info"))
    biz["image_assets"] = [
        {
            "image_id": item.get("image_id") or "",
            "image_type": item.get("image_type") or "product",
            "object_name": item.get("object_name") or "",
            "user_remark": item.get("user_remark") or "",
            "img_url": item.get("img_url") or "",
        }
        for item in assets
    ]
    result["structured_business_info"] = biz
    existing_warnings = result.get("warnings") if isinstance(result.get("warnings"), list) else []
    result["warnings"] = [*existing_warnings, *warnings]
    if not assets:
        bench = _as_dict(result.get("benchmark_analysis"))
        if not _text(bench.get("visual_asset_match_level")):
            bench["visual_asset_match_level"] = "无资产"
            result["benchmark_analysis"] = bench

    markdown = result_to_promo_markdown(result, planner_input)
    persist_planner_state(
        db,
        project_id=project_id,
        planner_input=planner_input,
        planner_result=result,
        markdown=markdown,
    )
    db.commit()
    project = rebind_promo_project(db, project_id=project_id)
    return serialize_promo_project(db, project, user_snap)


def backfill_promo_brand_links(db: Session) -> int:
    """Attach existing products/projects to a default brand under each enterprise."""
    changed = 0
    products = (
        db.query(PromoProduct)
        .filter(PromoProduct.is_deleted.is_(False), PromoProduct.brand_id.is_(None))
        .all()
    )
    by_enterprise: Dict[int, List[PromoProduct]] = {}
    for product in products:
        if not product.enterprise_id:
            continue
        by_enterprise.setdefault(int(product.enterprise_id), []).append(product)
    for enterprise_id, rows in by_enterprise.items():
        enterprise = (
            db.query(PromoEnterprise)
            .filter(PromoEnterprise.id == enterprise_id, PromoEnterprise.is_deleted.is_(False))
            .first()
        )
        brand = (
            db.query(PromoBrand)
            .filter(PromoBrand.enterprise_id == enterprise_id, PromoBrand.is_deleted.is_(False))
            .order_by(PromoBrand.id.asc())
            .first()
        )
        if not brand:
            brand = PromoBrand(
                owner_id=(enterprise.owner_id if enterprise else rows[0].owner_id),
                enterprise_id=enterprise_id,
                name=((enterprise.name if enterprise else "") or "默认品牌"),
                intro=(enterprise.intro if enterprise else None),
            )
            db.add(brand)
            db.flush()
            changed += 1
        for product in rows:
            product.brand_id = brand.id
            changed += 1
    projects = (
        db.query(PromoProject)
        .filter(PromoProject.is_deleted.is_(False), PromoProject.brand_id.is_(None))
        .all()
    )
    for project in projects:
        brand = None
        if project.product_id:
            product = db.query(PromoProduct).filter(PromoProduct.id == project.product_id).first()
            if product and product.brand_id:
                brand = db.query(PromoBrand).filter(PromoBrand.id == product.brand_id).first()
        if brand is None and project.enterprise_id:
            brand = (
                db.query(PromoBrand)
                .filter(PromoBrand.enterprise_id == project.enterprise_id, PromoBrand.is_deleted.is_(False))
                .order_by(PromoBrand.id.asc())
                .first()
            )
        if brand is not None:
            project.brand_id = brand.id
            changed += 1
    if changed:
        db.commit()
    return changed


def _positive_int(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return number if number > 0 else 0


def _promo_extra_info(project: PromoProject) -> Dict[str, Any]:
    raw = getattr(project, "extra_info", None)
    return dict(raw) if isinstance(raw, dict) else {}


def load_promo_script_meta(db: Session, project: PromoProject) -> Dict[str, Any]:
    extra = _promo_extra_info(project)
    story_id = _positive_int(extra.get("linked_story_project_id"))
    story = None
    episode = None
    if story_id:
        story = (
            db.query(Project)
            .filter(Project.id == story_id, _active_project_clause())
            .first()
        )
    if story is not None:
        episode = (
            db.query(Episode)
            .filter(Episode.project_id == story.id, _active_episode_clause())
            .order_by(Episode.id.asc())
            .first()
        )
    script_text = ""
    if episode is not None:
        script_text = str(getattr(episode, "script_content", None) or "")
    return {
        "linked_story_project_id": int(story.id) if story is not None else None,
        "script_episode_id": int(episode.id) if episode is not None else None,
        "script_content": script_text,
        "has_script": bool(script_text.strip()),
        "story_project_title": (story.title or "") if story is not None else "",
        "episode_title": (episode.title or "") if episode is not None else "",
    }


def serialize_promo_script(db: Session, project: PromoProject, current_user: Any) -> Dict[str, Any]:
    payload = serialize_promo_project(db, project, current_user)
    payload.update(load_promo_script_meta(db, project))
    return payload


def _soft_delete_story_project(db: Session, story: Project, now: str) -> None:
    if story is None:
        return
    story.is_deleted = True
    story.deleted_at = now
    story.updated_at = now
    db.add(story)
    db.query(Episode).filter(Episode.project_id == story.id, _active_episode_clause()).update(
        {Episode.is_deleted: True, Episode.deleted_at: now},
        synchronize_session=False,
    )


def soft_delete_promo_linked_story(db: Session, project: PromoProject, now: Optional[str] = None) -> None:
    extra = _promo_extra_info(project)
    story_id = _positive_int(extra.get("linked_story_project_id"))
    if not story_id:
        return
    story = db.query(Project).filter(Project.id == story_id, _active_project_clause()).first()
    if story is None:
        return
    _soft_delete_story_project(db, story, now or now_bj_iso())


def _infer_promo_base_positioning(planner_input: Optional[Dict[str, Any]], planner_result: Optional[Dict[str, Any]]) -> str:
    demand = _as_dict((planner_input or {}).get("campaign_demand"))
    presentation = _as_dict((planner_result or {}).get("presentation_plan"))
    positioning = _as_dict((planner_result or {}).get("video_positioning"))
    blob = " ".join(
        [
            _text(presentation.get("primary_form")),
            _text(demand.get("presentation_form")),
            _text(positioning.get("goal_type")),
            _text(demand.get("goal_type")),
            _text(((planner_result or {}).get("overall_scheme") or {}).get("one_liner")),
        ]
    )
    if any(token in blob for token in ("赛博", "Cyber", "霓虹")):
        return "赛博朋克 / Cyberpunk"
    if any(token in blob for token in ("科幻", "近未来", "科技", "CG", "三维")):
        return "近未来科技 / Near-Future Tech"
    return "当代都市 / Contemporary Urban"


def build_linked_story_global_info(
    project: PromoProject,
    *,
    planner_input: Optional[Dict[str, Any]] = None,
    planner_result: Optional[Dict[str, Any]] = None,
    existing: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    title = _text(project.title) or "宣传片成片脚本"
    preview = _as_dict((planner_result or {}).get("script_preview"))
    demand = _as_dict((planner_input or {}).get("campaign_demand"))
    positioning = _as_dict((planner_result or {}).get("video_positioning"))
    current = dict(existing or {})
    style = _text(current.get("base_positioning") or current.get("style_mode")) or _infer_promo_base_positioning(
        planner_input,
        planner_result,
    )
    current.update(
        {
            "script_title": _text(current.get("script_title")) or title,
            "source_promo_project_id": int(project.id),
            "hidden_from_list": True,
            "workflow_stage": _text(current.get("workflow_stage")) or "script",
            "base_positioning": style,
            "style_mode": _text(current.get("style_mode")) or style,
            "notes": _text(current.get("notes")) or _text(preview.get("logline")) or "由商业宣传片成片脚本生成，可走剧本优化 / 资产 / 分镜。",
            "promo_presentation_form": _text(demand.get("presentation_form") or ((planner_result or {}).get("presentation_plan") or {}).get("primary_form")),
            "promo_goal_type": _text(positioning.get("goal_type") or demand.get("goal_type")),
        }
    )
    return _ensure_project_generation_defaults(current)


def ensure_promo_linked_story_project(
    db: Session,
    project: PromoProject,
    *,
    current_user: Any,
    planner_input: Optional[Dict[str, Any]] = None,
    planner_result: Optional[Dict[str, Any]] = None,
) -> Tuple[Project, Episode]:
    extra = _promo_extra_info(project)
    story_id = _positive_int(extra.get("linked_story_project_id"))
    story = None
    if story_id:
        story = (
            db.query(Project)
            .filter(
                Project.id == story_id,
                Project.owner_id == project.owner_id,
                _active_project_clause(),
            )
            .first()
        )
    title = _text(project.title) or "宣传片成片脚本"
    if story is None:
        global_info = build_linked_story_global_info(
            project,
            planner_input=planner_input,
            planner_result=planner_result,
        )
        story = Project(
            title=title,
            owner_id=project.owner_id,
            global_info=global_info,
        )
        db.add(story)
        db.flush()
        extra["linked_story_project_id"] = int(story.id)
        extra["linked_story_episode_id"] = None
        project.extra_info = extra
        db.add(project)
    else:
        story.global_info = build_linked_story_global_info(
            project,
            planner_input=planner_input,
            planner_result=planner_result,
            existing=story.global_info if isinstance(story.global_info, dict) else {},
        )
        if _text(project.title) and story.title != project.title:
            story.title = project.title
        db.add(story)

    episode = (
        db.query(Episode)
        .filter(Episode.project_id == story.id, _active_episode_clause())
        .order_by(Episode.id.asc())
        .first()
    )
    if episode is None:
        episode = Episode(
            project_id=story.id,
            title="Episode 1",
            script_content="",
            episode_info={"episode_script_episode_number": 1},
        )
        db.add(episode)
        db.flush()
    extra["linked_story_project_id"] = int(story.id)
    extra["linked_story_episode_id"] = int(episode.id)
    project.extra_info = extra
    db.add(project)
    return story, episode


def _build_script_user_prompt(
    *,
    title: str,
    planner_input: Dict[str, Any],
    planner_result: Dict[str, Any],
) -> str:
    payload = {
        "project_title": title,
        "enterprise_info": planner_input.get("enterprise_info") or {},
        "campaign_demand": planner_input.get("campaign_demand") or {},
        "overall_scheme": planner_result.get("overall_scheme") or {},
        "content_mode": planner_result.get("content_mode") or {},
        "video_positioning": planner_result.get("video_positioning") or {},
        "narrative_plan": planner_result.get("narrative_plan") or {},
        "presentation_plan": planner_result.get("presentation_plan") or {},
        "visual_spec": planner_result.get("visual_spec") or {},
        "material_list": planner_result.get("material_list") or [],
        "script_preview": planner_result.get("script_preview") or {},
        "structured_business_info": planner_result.get("structured_business_info") or {},
    }
    return (
        "请把下面已锁定的整体方案与成片脚本方向预览，写成一支可进入剧本页的正式成片剧本。\n"
        "必须严格承接 script_preview.beats 与 content_mode.outline，不得另起故事。\n"
        "按时长控制场数与篇幅。只输出带 OUTPUT 标记的 Markdown 剧本。\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def _wrap_official_script(content: str) -> str:
    official = extract_official_episode_script(content) or str(content or "").strip()
    if not official:
        return ""
    if extract_episode_script_output_between_markers(content).get("found"):
        return f"{EPISODE_SCRIPT_OUTPUT_START}\n{official}\n{EPISODE_SCRIPT_OUTPUT_END}"
    return official


async def _run_script_markdown_llm(
    db: Session,
    *,
    current_user: Any,
    llm_config: Dict[str, Any],
    system_prompt: str,
    user_prompt: str,
) -> str:
    llm_config = sanitize_script_generation_llm_config_text_only(llm_config)
    provider = llm_config.get("provider")
    model = llm_config.get("model")
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    reservation_tx = None
    if billing_service.is_token_pricing(db, "llm_chat", provider, model):
        est = billing_service.estimate_reserve_tokens_from_messages(messages)
        reservation_tx = billing_service.reserve_credits(
            db,
            current_user.id,
            "llm_chat",
            provider,
            model,
            {
                "item": "promo_planner_script",
                "estimation_method": "prompt_tokens_ratio",
                "estimated_output_ratio": billing_service.RESERVE_OUTPUT_RATIO,
                "input_tokens": int(est.get("input_tokens", 0) or 0),
                "output_tokens": int(est.get("output_tokens", 0) or 0),
                "total_tokens": int(est.get("total_tokens", 0) or 0),
            },
        )
    else:
        billing_service.check_balance(db, current_user.id, "llm_chat", provider, model)

    _release_db_connection(db, "promo_planner_script_llm_call")
    try:
        generated_payload = await generate_markdown_with_retry(
            user_prompt=user_prompt,
            sys_prompt=system_prompt,
            llm_config=llm_config,
            strict_markdown=True,
            require_h1=True,
            return_meta=True,
        )
    except Exception as exc:
        if reservation_tx:
            billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), str(exc))
        raise

    content = str((generated_payload or {}).get("content") or "").strip()
    if not content:
        if reservation_tx:
            billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), "LLM returned empty content")
        raise HTTPException(status_code=500, detail="LLM returned empty script")

    usage = (generated_payload or {}).get("usage") if isinstance(generated_payload, dict) else {}
    if not usage:
        usage = billing_service.estimate_input_output_tokens_from_messages(
            messages + [{"role": "assistant", "content": content}],
            output_ratio=1.0,
        )
    settle_details = {
        "item": "promo_planner_script",
        "prompt_tokens": int((usage or {}).get("prompt_tokens", (usage or {}).get("input_tokens", 0)) or 0),
        "completion_tokens": int((usage or {}).get("completion_tokens", (usage or {}).get("output_tokens", 0)) or 0),
    }
    settle_details["total_tokens"] = int(
        (usage or {}).get("total_tokens", settle_details["prompt_tokens"] + settle_details["completion_tokens"]) or 0
    )
    settle_details["input_tokens"] = settle_details["prompt_tokens"]
    settle_details["output_tokens"] = settle_details["completion_tokens"]
    _apply_llm_routing_to_billing_details(settle_details, generated_payload)
    if reservation_tx:
        billing_service.settle_reservation(db, _reservation_tx_id(reservation_tx), settle_details)
    else:
        billing_service.deduct_credits(db, current_user.id, "llm_chat", provider, model, settle_details)
    return _wrap_official_script(content)


async def generate_promo_script(
    db: Session,
    *,
    project: Any,
    current_user: Any,
    req: Any,
) -> Dict[str, Any]:
    project_id = _promo_project_id(project)
    if not project_id:
        raise HTTPException(status_code=404, detail="Promo project not found")
    extra_info = dict(getattr(project, "extra_info", None) or {})
    user_snap = _snapshot_user_principal(current_user)
    overwrite = True if getattr(req, "overwrite_existing", None) is None else bool(req.overwrite_existing)

    state = load_planner_state(db, rebind_promo_project(db, project_id=project_id))
    planner_input = state.get("promo_planner_input") or {}
    result_overlay = getattr(req, "promo_planner_result", None)
    if isinstance(result_overlay, dict) and result_overlay:
        planner_result = merge_planner_result(result_overlay)
        markdown = result_to_promo_markdown(planner_result, planner_input)
        persist_planner_state(
            db,
            project_id=project_id,
            planner_result=planner_result,
            markdown=markdown,
        )
        db.commit()
    else:
        planner_result = merge_planner_result(state.get("promo_planner_result") or {})

    preview = planner_result.get("script_preview") if isinstance(planner_result.get("script_preview"), dict) else {}
    beats = preview.get("beats") if isinstance(preview.get("beats"), list) else []
    if not _text(preview.get("logline")) and not beats:
        raise HTTPException(status_code=400, detail="请先生成并保存成片脚本方向预览")

    existing_meta = load_promo_script_meta(db, rebind_promo_project(db, project_id=project_id))
    if existing_meta.get("has_script") and not overwrite:
        raise HTTPException(status_code=409, detail="剧本页已有成片脚本，如需覆盖请确认后重试")

    llm_config = _resolve_story_generator_script_analysis_llm_config(
        db,
        int(user_snap.id),
        function_name=(getattr(req, "function_name", None) or "script_analysis"),
        system_api_id=getattr(req, "system_api_id", None),
        context="generate_promo_script",
        project_global_info=extra_info,
    )
    if not llm_config or not (llm_config.get("api_key") or "").strip():
        raise HTTPException(status_code=400, detail="No valid LLM API key configured in active settings")

    project = rebind_promo_project(db, project_id=project_id)
    system_prompt = _resolve_prompt_text("promo_planner_script.md")
    user_prompt = _build_script_user_prompt(
        title=_text(project.title),
        planner_input=planner_input,
        planner_result=planner_result,
    )
    content = await _run_script_markdown_llm(
        db,
        current_user=user_snap,
        llm_config=llm_config,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )
    if not content.strip():
        raise HTTPException(status_code=500, detail="LLM returned empty script")

    project = rebind_promo_project(db, project_id=project_id)
    story, episode = ensure_promo_linked_story_project(
        db,
        project,
        current_user=user_snap,
        planner_input=planner_input,
        planner_result=planner_result,
    )
    episode.script_content = content
    info = dict(episode.episode_info or {})
    info["episode_script_episode_number"] = 1
    info["episode_script_source"] = "promo_script_preview"
    info["episode_script_generated_at"] = now_bj_iso()
    episode.episode_info = info
    episode.title = _text((planner_result.get("overall_scheme") or {}).get("title")) or episode.title or "Episode 1"
    db.add(episode)
    db.add(story)
    db.add(project)
    db.commit()
    project = rebind_promo_project(db, project_id=project_id)
    return serialize_promo_script(db, project, user_snap)


def save_promo_script_content(
    db: Session,
    *,
    project: PromoProject,
    current_user: Any,
    script_content: str,
) -> Dict[str, Any]:
    state = load_planner_state(db, project)
    story, episode = ensure_promo_linked_story_project(
        db,
        project,
        current_user=current_user,
        planner_input=state.get("promo_planner_input") or {},
        planner_result=state.get("promo_planner_result") or {},
    )
    episode.script_content = str(script_content or "")
    db.add(episode)
    db.add(project)
    db.commit()
    project = rebind_promo_project(db, project_id=int(project.id))
    return serialize_promo_script(db, project, current_user)
