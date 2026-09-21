# -*- coding: utf-8 -*-
"""Commercial promo planner pipeline: image analysis + four-dimension scheme."""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
import subprocess
import tempfile
from contextlib import nullcontext
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from fastapi import HTTPException
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session, object_session
from sqlalchemy.orm.attributes import flag_modified

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
from app.services.promo_context import (
    apply_promo_fields_to_global_info,
    collect_promo_brief,
    compose_flower_text_spec_line,
    enrich_rebuild_analysis,
    filter_analysis_to_selected_assets,
    format_visual_rebuild_lines,
)
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
IMAGE_TYPE_LABELS = {
    "product": "产品",
    "character": "角色",
    "scene": "场景",
    "prop": "道具",
}
MEDIA_KIND_LABELS = {
    "image": "图片",
    "video": "视频",
}
MAX_VISION_IMAGES = 12
MAX_FRAMES_PER_VIDEO = 3
MAX_PARALLEL_ASSET_ANALYSIS = 4
ANALYSIS_STATUS_PENDING = "pending"
ANALYSIS_STATUS_SUCCESS = "success"
ANALYSIS_STATUS_FAILED = "failed"
FAILED_CONTENT_DESC = "识别失败或未返回描述"
_ASSET_PERSIST_LOCKS: Dict[int, asyncio.Lock] = {}
_ASSET_PERSIST_GUARD: Optional[asyncio.Lock] = None


async def _project_asset_persist_lock(project_id: int) -> asyncio.Lock:
    global _ASSET_PERSIST_GUARD
    if _ASSET_PERSIST_GUARD is None:
        _ASSET_PERSIST_GUARD = asyncio.Lock()
    async with _ASSET_PERSIST_GUARD:
        lock = _ASSET_PERSIST_LOCKS.get(project_id)
        if lock is None:
            lock = asyncio.Lock()
            _ASSET_PERSIST_LOCKS[project_id] = lock
        return lock

GOAL_TYPES = (
    "企业品牌宣传（情绪种草）",
    "即时转化（引流获客）",
    "建立信任（权威，客户证言）",
    "产品使用与原理（产品测评，技术科普，使用指南）",
    "招商合作（招商，招聘，年会，加盟）",
)

DURATION_OPTIONS = (
    "15s以内",
    "15-30s",
    "30-60s",
    "60-90s",
    "1-3min",
    "3min以上",
)

UNIFIED_RHYTHM = "吸睛-共鸣-价值-收口"
PROMO_PROJECT_TYPE = "商业宣传片"
_PROMO_EXTRA_META_KEYS = {"linked_story_project_id", "linked_story_episode_id", "global_info"}
STAGE_KEYS = ("hook", "empathy", "value", "close")
STAGE_NAMES = {
    "hook": "吸睛",
    "empathy": "共鸣",
    "value": "价值",
    "close": "收口",
}

LEGACY_GOAL_MAP = {
    "品牌形象片": "企业品牌宣传（情绪种草）",
    "企业形象片": "企业品牌宣传（情绪种草）",
    "公益社会责任片": "企业品牌宣传（情绪种草）",
    "思想领导力片": "企业品牌宣传（情绪种草）",
    "上市融资路演片": "企业品牌宣传（情绪种草）",
    "引流获客片": "即时转化（引流获客）",
    "即使转化": "即时转化（引流获客）",
    "即使转化（引流获客）": "即时转化（引流获客）",
    "电商带货片": "即时转化（引流获客）",
    "门店到店转化片": "即时转化（引流获客）",
    "新品发布片": "即时转化（引流获客）",
    "产品卖点片": "即时转化（引流获客）",
    "活动节点片": "即时转化（引流获客）",
    "客户案例证言片": "建立信任（权威，客户证言）",
    "售后服务口碑片": "建立信任（权威，客户证言）",
    "功能演示片": "产品使用与原理（产品测评，技术科普，使用指南）",
    "招商渠道片": "招商合作（招商，招聘，年会，加盟）",
    "招聘雇主品牌片": "招商合作（招商，招聘，年会，加盟）",
}

NARRATIVE_MODELS = (UNIFIED_RHYTHM,)

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


_FILE_EXT_RE = re.compile(r"\.(jpe?g|png|webp|gif|bmp|heic|heif|mp4|mov|webm|avi|mkv|m4v)$", re.I)
_CAMERA_PREFIX_RE = re.compile(
    r"^(img|dscn?|pxl|mvimg|vid|mov|pict|photo|image|picture|screenshot|screen[ _-]?shot|"
    r"wx_camera|mmexport|export|附件|图片|照片|视频|截图|屏幕截图|微信图片|微信截图)"
    r"([-_ .]|$)",
    re.I,
)
_WECHAT_FILE_RE = re.compile(r"(微信图片|微信截图|屏幕截图|mmexport|wx_camera)", re.I)
_UUID_NAME_RE = re.compile(r"^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$", re.I)
_DIGIT_HEAVY_NAME_RE = re.compile(r"^[a-z]{0,4}[-_]?\d{6,}([-_]\d+)*$", re.I)


def looks_like_source_filename(value: Any) -> bool:
    text = _text(value)
    if not text:
        return False
    if _FILE_EXT_RE.search(text):
        return True
    stem = _FILE_EXT_RE.sub("", text).strip()
    if not stem:
        return False
    compact = re.sub(r"\s+", "", stem)
    if _UUID_NAME_RE.match(compact):
        return True
    if _WECHAT_FILE_RE.search(stem) or _CAMERA_PREFIX_RE.search(stem):
        return True
    if _DIGIT_HEAVY_NAME_RE.match(compact):
        return True
    digits = re.sub(r"\D", "", stem)
    letters = re.sub(r"[^A-Za-z\u4e00-\u9fff]+", "", stem)
    return len(digits) >= 8 and len(letters) <= 3


def is_user_asset_name(value: Any) -> bool:
    text = _text(value)
    return bool(text) and not looks_like_source_filename(text)


def is_short_name_tag(value: Any) -> bool:
    text = _text(value)
    if not text or looks_like_source_filename(text):
        return False
    if len(text) > 16:
        return False
    return not any(mark in text for mark in ("。", "；", ";", "！", "!", "？", "?", "\n"))


def short_content_asset_name(desc: Any) -> str:
    text = _text(desc)
    if not text or text.startswith("识别失败"):
        return ""
    for token in ("用户说明=", "说明="):
        if text.startswith(token):
            text = text[len(token):].strip()
    for sep in ("，", ",", "。", "；", ";", "：", ":", "｜", "|", "、"):
        if sep in text:
            head = text.split(sep, 1)[0].strip()
            if head:
                text = head
                break
    text = re.sub(r"^(一个|一位|一台|一张|一条|一组)", "", text)
    text = text.strip("《》【】（）()“\"' ")
    if len(text) > 12:
        text = text[:12].rstrip()
    if not text or looks_like_source_filename(text) or text in {"无", "未见"}:
        return ""
    return text


def resolve_asset_display_name(asset: Any, parsed: Any = None, fallback_index: Optional[int] = None) -> str:
    item = _as_dict(asset)
    row = _as_dict(parsed)
    remark = _text(item.get("user_remark") or row.get("user_remark"))
    candidates = [
        item.get("object_name"),
        remark if is_short_name_tag(remark) else "",
        row.get("object_name"),
        row.get("reference_name"),
        row.get("name_for_script"),
    ]
    for candidate in candidates:
        if is_user_asset_name(candidate):
            return _text(candidate)
    summary = short_content_asset_name(
        row.get("content_desc")
        or row.get("rebuild_brief")
        or row.get("environment_detail")
        or row.get("character_detail")
        or row.get("prop_detail")
        or row.get("appearance")
    )
    if summary:
        return summary
    label = image_type_label(item.get("image_type") or row.get("image_type") or row.get("kind"))
    if fallback_index:
        return f"{label}{fallback_index}"
    return label


def _unique_asset_name(name: str, used: set) -> str:
    base = _text(name) or "素材"
    if base not in used:
        return base
    index = 2
    while f"{base}{index}" in used:
        index += 1
    return f"{base}{index}"


def assign_asset_display_names(assets: Any, analysis: Any) -> List[Dict[str, Any]]:
    data = analysis if isinstance(analysis, dict) else {}
    image_list = [item for item in (data.get("image_list") or []) if isinstance(item, dict)]
    by_id = {
        _text(item.get("image_id")): item
        for item in image_list
        if _text(item.get("image_id"))
    }
    used: set = set()
    id_to_name: Dict[str, str] = {}
    source = [item for item in assets if isinstance(item, dict)] if isinstance(assets, list) else []
    for idx, asset in enumerate(source, 1):
        parsed = by_id.get(_text(asset.get("image_id"))) or {}
        name = _unique_asset_name(resolve_asset_display_name(asset, parsed, fallback_index=idx), used)
        used.add(name)
        asset["object_name"] = name
        image_id = _text(asset.get("image_id"))
        if image_id:
            id_to_name[image_id] = name
        if parsed:
            parsed["object_name"] = name
            parsed["reference_name"] = name
    for row in image_list:
        image_id = _text(row.get("image_id"))
        if image_id and image_id in id_to_name:
            row["object_name"] = id_to_name[image_id]
            row["reference_name"] = id_to_name[image_id]
            continue
        if is_user_asset_name(row.get("object_name")):
            used.add(_text(row.get("object_name")))
            continue
        name = _unique_asset_name(resolve_asset_display_name({}, row, fallback_index=len(used) + 1), used)
        used.add(name)
        row["object_name"] = name
        row["reference_name"] = name
        if image_id:
            id_to_name[image_id] = name
    subjects = data.get("rebuild_subjects") if isinstance(data.get("rebuild_subjects"), list) else []
    for subject in subjects:
        if not isinstance(subject, dict):
            continue
        sources = subject.get("source_image_ids") if isinstance(subject.get("source_image_ids"), list) else []
        mapped = ""
        for sid in sources:
            mapped = id_to_name.get(_text(sid)) or ""
            if mapped:
                break
        if is_user_asset_name(subject.get("object_name")):
            continue
        name = mapped or _unique_asset_name(
            resolve_asset_display_name({}, subject, fallback_index=len(used) + 1),
            used,
        )
        used.add(name)
        subject["object_name"] = name
        if not is_user_asset_name(subject.get("name_for_script")):
            subject["name_for_script"] = name
    return source


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


def image_type_label(value: Any) -> str:
    return IMAGE_TYPE_LABELS.get(normalize_image_type(value), "产品")


def media_kind_label(value: Any) -> str:
    return MEDIA_KIND_LABELS.get(normalize_media_kind(value), "图片")


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


def normalize_expect_duration(value: Any) -> str:
    raw = _text(value)
    if not raw:
        return "15-30s"
    if raw in DURATION_OPTIONS:
        return raw
    compact = raw.replace(" ", "").replace("秒", "s").replace("分钟", "min").lower()
    mapping = {
        "15s内": "15s以内",
        "<15s": "15s以内",
        "15以内": "15s以内",
        "15s-30s": "15-30s",
        "15~30s": "15-30s",
        "30s": "15-30s",
        "30s-60s": "30-60s",
        "30~60s": "30-60s",
        "60s": "30-60s",
        "60s-90s": "60-90s",
        "60~90s": "60-90s",
        "90s": "60-90s",
        "1-3m": "1-3min",
        "1~3min": "1-3min",
        ">3min": "3min以上",
        "3min+": "3min以上",
    }
    if compact in mapping:
        return mapping[compact]
    return raw


def normalize_goal_type(value: Any) -> str:
    raw = _text(value)
    if not raw:
        return ""
    if raw in GOAL_TYPES:
        return raw
    if raw in LEGACY_GOAL_MAP:
        return LEGACY_GOAL_MAP[raw]
    compact = raw.replace(" ", "")
    if compact in LEGACY_GOAL_MAP:
        return LEGACY_GOAL_MAP[compact]
    if any(token in raw for token in ("即使转化", "即时转化", "引流获客", "带货", "到店", "卖点")):
        return "即时转化（引流获客）"
    if any(token in raw for token in ("证言", "信任", "权威", "口碑")):
        return "建立信任（权威，客户证言）"
    if any(token in raw for token in ("测评", "科普", "使用指南", "功能演示", "原理")):
        return "产品使用与原理（产品测评，技术科普，使用指南）"
    if any(token in raw for token in ("招商", "招聘", "年会", "加盟")):
        return "招商合作（招商，招聘，年会，加盟）"
    if any(token in raw for token in ("品牌宣传", "情绪种草", "企业形象", "品牌形象")):
        return "企业品牌宣传（情绪种草）"
    return raw


def _catalog_asset_id(data: Dict[str, Any]) -> Optional[int]:
    raw = data.get("catalog_asset_id")
    owner_kind = _text(data.get("owner_kind")) or "project"
    if raw in (None, "") and owner_kind in {"enterprise", "brand", "offering"}:
        raw = data.get("id")
    try:
        value = int(raw)
    except Exception:
        return None
    return value or None


def normalize_image_assets(raw_assets: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for item in raw_assets or []:
        data = dump_model(item)
        img_url = _text(data.get("img_url") or data.get("file_url"))
        if not img_url:
            continue
        object_name = _text(data.get("object_name"))
        owner_kind = _text(data.get("owner_kind")) or "project"
        owner_entity_id = data.get("owner_entity_id")
        try:
            owner_entity_id = int(owner_entity_id) if owner_entity_id not in (None, "") else None
        except Exception:
            owner_entity_id = None
        out.append(
            {
                "img_url": img_url,
                "image_id": _text(data.get("image_id")),
                "image_type": normalize_image_type(data.get("image_type") or data.get("asset_type")),
                "media_kind": normalize_media_kind(data.get("media_kind")),
                "owner_kind": owner_kind,
                "owner_entity_id": owner_entity_id,
                "catalog_asset_id": _catalog_asset_id(data),
                "object_name": object_name,
                "user_remark": _text(data.get("user_remark")),
                "analysis_status": _text(data.get("analysis_status")) or ANALYSIS_STATUS_PENDING,
                "analysis_error": _text(data.get("analysis_error")),
            }
        )
    return out


def selected_planner_image_assets(overlay: Any) -> List[Dict[str, Any]]:
    """Project library only: the subset this film selected or uploaded. Never the whole subject catalog."""
    data = dump_model(overlay)
    return normalize_image_assets(data.get("image_assets"))


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
            "user_raw_text": _text(campaign.get("user_raw_text") or campaign.get("basic_intro")),
            "basic_intro": _text(campaign.get("basic_intro") or campaign.get("user_raw_text")),
            "target_audience": _text(campaign.get("target_audience") or enterprise.get("target_user")),
            "market_and_competitors": _text(
                campaign.get("market_and_competitors") or enterprise.get("competitor_problem")
            ),
            "goal_type": normalize_goal_type(campaign.get("goal_type")),
            "narrative_model": UNIFIED_RHYTHM,
            "presentation_form": _text(campaign.get("presentation_form")),
            "platform": normalize_platforms(campaign.get("platform")),
            "expect_duration": normalize_expect_duration(campaign.get("expect_duration")),
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
        "rebuild_subjects": [],
        "analysis_warnings": [],
    }


def empty_flower_text_spec() -> Dict[str, Any]:
    return {
        "font": "",
        "script": "",
        "emphasis_font": "",
        "weight": "",
        "body_size": "中",
        "emphasis_size": "大",
        "color": "",
        "accent_color": "",
        "stroke": "",
        "body_position": "画面中部",
        "emphasis_position": "画面中部",
        "align": "居中",
        "max_line_chars": "12",
        "en_companion": "重点句可配英文小字",
        "en_size": "小",
        "mid_display": "中部必须艺术化组合设计，不限于印章/古体/英文小字/颜色",
        "product_name_layout": "画右竖排|画左竖排",
        "cut_fusion": "优先段末切镜或段首开镜，不与动作抢镜；可黑屏专镜或字卡专镜；有旁白则无花字",
        "cta_hold": "CTA可较长停留",
        "vo_xor": "有旁白时不出花字，花字低于旁白，禁同步以免分心",
        "glyph_lock": "引号内逐字成形；含「X家」须见家，禁漏家、禁复写邻字、禁何乐乐享；店号/热线不进难认印章",
        "seal_clear": "印=句外旁侧｜压字=禁｜替字=禁｜字印留空，禁止印面盖住任一花字",
        "card_shot": "店号/品牌/热线走字卡专镜：企业场景底+字层先合成一张静帧，本镜Static Hold按静帧原样上屏；禁手写；禁字卡图与场景图当两张参考图分喂；字卡不是CHAR/PROP/ENV，不抽实体；衍生环境不挂字卡",
        "unity": "全片同套字形与字色字重；禁底部避字幕；每段最多一条花字；一个动作最多一条；有旁白时不出花字，花字低于旁白，禁同步；优先段末/段首切镜或黑屏专镜或字卡专镜，不与动作抢镜；CTA可较长停留；中部必须艺术化组合（不限于印章/古体/英文小字/颜色），只改字级、落位与艺术手段",
        "spec_line": "",
    }


def empty_stage_block(name: str) -> Dict[str, Any]:
    return {
        "name": name,
        "duration": "",
        "sensory": "",
        "content": "",
        "copy": "",
        "flower_text": "",
        "cta": "",
        "technique_assoc": "",
    }


def drop_stage_plan_shots(stage_plan: Any) -> Dict[str, Any]:
    cleaned: Dict[str, Any] = {}
    data = _as_dict(stage_plan)
    for key, name in STAGE_NAMES.items():
        row = dict(_as_dict(data.get(key)))
        row.pop("shots", None)
        if not _text(row.get("name")):
            row["name"] = name
        cleaned[key] = row
    return cleaned


def empty_stage_plan() -> Dict[str, Any]:
    return {key: empty_stage_block(name) for key, name in STAGE_NAMES.items()}


def empty_visual_backfill() -> Dict[str, Any]:
    return {
        "Global_Style": "",
        "style_mode": "",
        "style_inheritance": "",
        "borrowed_films": [],
        "borrowed_films_note": "",
        "borrowed_films_scene_refs": [],
        "tone": "",
        "lighting": "",
        "color_palette": "",
        "color_spectrum": "",
        "plot_summary": "",
        "comprehensive_plot": "",
        "comprehensive_assets": "",
        "music_recommendation": "",
        "voiceover_style": "",
        "sfx_style": "",
        "flower_text_spec": empty_flower_text_spec(),
    }


def empty_characteristic_analysis() -> Dict[str, Any]:
    return {
        "enterprise": "",
        "brand": "",
        "product": "",
        "audience_insight": "",
    }


def empty_planner_result() -> Dict[str, Any]:
    return {
        "overall_scheme": {
            "title": "",
            "one_liner": "",
            "combination_mode": "",
            "main_goal_type": "",
            "target_duration": "",
            "duration_budget": "",
            "series_logic": "",
            "success_metric": "",
            "promo_focus": "",
            "selling_points": "",
            "visual_core": "",
        },
        "characteristic_analysis": empty_characteristic_analysis(),
        "benchmark_films": [],
        "stage_plan": empty_stage_plan(),
        "project_visual_backfill": empty_visual_backfill(),
        "supplement_suggestions": [],
        "content_mode": {
            "primary_mode": UNIFIED_RHYTHM,
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


def _stage_has_content(row: Any) -> bool:
    data = _as_dict(row)
    return any(
        _text(data.get(key))
        for key in ("sensory", "content", "copy", "flower_text", "cta", "technique_assoc")
    )


def sync_stage_plan_to_preview(result: Dict[str, Any]) -> Dict[str, Any]:
    """Keep four-stage plan, content outline, and script preview beats on the same spine."""
    stages = _as_dict(result.get("stage_plan"))
    merged_stages = empty_stage_plan()
    for key, name in STAGE_NAMES.items():
        incoming = _as_dict(stages.get(key))
        block = dict(merged_stages[key])
        block.update({k: incoming.get(k, block.get(k)) for k in block})
        if not _text(block.get("name")):
            block["name"] = name
        block.pop("shots", None)
        merged_stages[key] = block
    result["stage_plan"] = drop_stage_plan_shots(merged_stages)

    preview = _as_dict(result.get("script_preview"))
    existing_beats = preview.get("beats") if isinstance(preview.get("beats"), list) else []

    outline = []
    beats = []
    for key, name in STAGE_NAMES.items():
        row = merged_stages[key]
        outline.append(
            {
                "section": _text(row.get("name")) or name,
                "duration": _text(row.get("duration")),
                "purpose": _text(row.get("content")),
                "content": " ".join(part for part in (_text(row.get("sensory")), _text(row.get("content"))) if part),
                "copy_hint": _text(row.get("copy")),
            }
        )
        existing_beat = _as_dict(existing_beats[len(beats)]) if len(existing_beats) > len(beats) else {}
        beats.append(
            {
                "name": _text(row.get("name")) or name,
                "duration": _text(row.get("duration")),
                "shot": _text(row.get("sensory")),
                "copy": _text(row.get("copy")),
                "flower_text": _text(row.get("flower_text")) or _text(existing_beat.get("flower_text")),
                "cta": _text(row.get("cta")),
                "technique": _text(row.get("technique_assoc")),
            }
        )

    content_mode = _as_dict(result.get("content_mode"))
    existing_outline = content_mode.get("outline") if isinstance(content_mode.get("outline"), list) else []
    outline_has_body = any(_text(_as_dict(item).get("content")) for item in existing_outline)
    stages_have_body = any(_stage_has_content(merged_stages[key]) for key in STAGE_KEYS)
    if stages_have_body or not outline_has_body:
        content_mode["outline"] = outline
    content_mode["primary_mode"] = UNIFIED_RHYTHM
    if not _text(content_mode.get("mode_definition")):
        content_mode["mode_definition"] = "统一四段节奏"
    result["content_mode"] = content_mode

    beats_have_body = any(
        _text(_as_dict(item).get("shot")) or _text(_as_dict(item).get("copy")) or _text(_as_dict(item).get("flower_text"))
        for item in existing_beats
    )
    if stages_have_body or not beats_have_body:
        preview["beats"] = beats
    if not _text(preview.get("logline")):
        preview["logline"] = _text(_as_dict(result.get("overall_scheme")).get("one_liner"))
    result["script_preview"] = preview

    narrative = _as_dict(result.get("narrative_plan"))
    narrative["primary_model"] = UNIFIED_RHYTHM
    if not _text(narrative.get("adaptation_reason")):
        narrative["adaptation_reason"] = "全片统一四段节奏"
    result["narrative_plan"] = narrative
    return result


def _default_flower_slot(stage_key: str) -> Tuple[str, str]:
    if stage_key == "close":
        return "中", "大"
    return "中", "中"


_FLOWER_POS_RE = re.compile(r"位置=([^｜]+)")
_FLOWER_QUOTE_RE = re.compile(r"[「\"]([^」\"]+)[」\"]")
_FLOWER_PHONE_RE = re.compile(r"(?:\d{3,4}-?\d{5,8}|热线|电话)")
_FLOWER_SCREEN_RE = re.compile(r"上屏=[^｜]+")
_FLOWER_BOTTOM_TOKENS = {"底", "底部", "底部居中", "屏幕下方", "下方"}
_FLOWER_MID_TOKENS = {"中", "中部", "画面中部", "中屏"}
_FLOWER_SIDE_TOKENS = {"画右", "画左"}


def _lift_spec_position(value: Any, default: str = "画面中部") -> str:
    raw = _text(value)
    if not raw:
        return default
    if "画右" in raw:
        return "画右"
    if "画左" in raw:
        return "画左"
    if any(token in raw for token in _FLOWER_BOTTOM_TOKENS):
        return default
    return raw


def unique_flower_text_slot(text: Any) -> str:
    compact = _text(text)
    if not compact:
        return compact
    compact = compact.replace("正文位=底部居中", "正文位=画面中部").replace("收口位=底部居中", "收口位=画面中部")
    match = _FLOWER_POS_RE.search(compact)
    if not match:
        return compact
    tokens = [part.strip() for part in re.split(r"[/／|,，、]", match.group(1)) if part.strip()]
    sides = [token for token in tokens if token in _FLOWER_SIDE_TOKENS]
    mids = [token for token in tokens if token in _FLOWER_MID_TOKENS]
    bots = [token for token in tokens if token in _FLOWER_BOTTOM_TOKENS]
    if sides and not mids:
        chosen = sides[0]
    elif mids or bots or not tokens:
        chosen = "中"
    else:
        chosen = tokens[0]
        if chosen in _FLOWER_BOTTOM_TOKENS:
            chosen = "中"
    return compact[: match.start()] + f"位置={chosen}" + compact[match.end() :]


def compose_flower_glyph_lock(text: Any) -> str:
    compact = _text(text)
    match = _FLOWER_QUOTE_RE.search(compact)
    if not match:
        return ""
    source = match.group(1).strip()
    glyphs = [ch for ch in source if not ch.isspace()]
    if not glyphs:
        return ""
    joined = "/".join(glyphs)
    if "家" in source:
        return f"{joined}｜禁漏家｜禁复写邻字｜禁何乐乐享｜禁印代字"
    return f"{joined}｜禁漏字｜禁复写邻字"


def _append_flower_glyph_lock(compact: str) -> str:
    text = _text(compact)
    if not text or "逐字=" in text:
        return text
    lock = compose_flower_glyph_lock(text)
    if not lock:
        return text
    return f"{text}｜逐字={lock}"


def _append_flower_seal_clear(compact: str) -> str:
    text = _text(compact)
    if not text or "压字=" in text:
        return text
    return f"{text}｜印=句外旁侧｜压字=禁｜替字=禁"


def flower_needs_title_card(text: Any) -> bool:
    compact = _text(text)
    if not compact:
        return False
    match = _FLOWER_QUOTE_RE.search(compact)
    source = match.group(1).strip() if match else compact
    if _FLOWER_PHONE_RE.search(source) or _FLOWER_PHONE_RE.search(compact):
        return True
    if any(mark in compact for mark in ("店号", "字号", "品牌名", "字卡专镜")):
        return True
    return "家" in source and "万家" not in source


def _lift_flower_title_card(compact: str) -> str:
    text = _text(compact)
    if not text or not flower_needs_title_card(text):
        return text
    if _FLOWER_SCREEN_RE.search(text):
        text = _FLOWER_SCREEN_RE.sub("上屏=字卡专镜", text)
    else:
        text = f"{text}｜上屏=字卡专镜"
    if "字卡=" not in text:
        text = f"{text}｜字卡=场景底+字层"
    if "手写=" not in text:
        text = f"{text}｜手写=禁"
    return text


def _append_flower_video_locks(compact: str) -> str:
    return _append_flower_seal_clear(_append_flower_glyph_lock(_lift_flower_title_card(compact)))


def _compose_stage_flower_text(stage_key: str, row: Dict[str, Any]) -> str:
    existing = _text(row.get("flower_text"))
    position, size = _default_flower_slot(stage_key)
    # Close flower-text is the poetic last line; do not substitute the CTA verb.
    source = _text(row.get("copy")) or (
        _text(row.get("cta")) if stage_key != "close" else ""
    )
    if existing:
        compact = existing
        if "位置=" not in compact:
            compact = f"{compact}｜位置={position}"
        if "字级=" not in compact:
            compact = f"{compact}｜字级={size}"
        if "上屏=" not in compact:
            compact = f"{compact}｜上屏={'字卡专镜' if flower_needs_title_card(compact) else '段末切镜'}"
        if "停留=" not in compact:
            compact = f"{compact}｜停留={'长' if stage_key == 'close' else '短'}"
        if "听=" not in compact:
            compact = f"{compact}｜听=无"
        return _append_flower_video_locks(unique_flower_text_slot(compact))
    if not source:
        return ""
    quote = source.split("｜", 1)[0].strip(" 「」\"'")
    if len(quote) > 16:
        quote = quote[:16]
    hold = "长" if stage_key == "close" else "短"
    screen = "字卡专镜" if flower_needs_title_card(quote) else "段末切镜"
    return _append_flower_video_locks(
        unique_flower_text_slot(
            f"文案=「{quote}」｜位置={position}｜字级={size}｜上屏={screen}｜停留={hold}｜听=无"
        )
    )


def ensure_flower_text_spec(result: Dict[str, Any]) -> Dict[str, Any]:
    """Lock a single on-screen type kit and per-stage flower-text slots."""
    visual = _as_dict(result.get("project_visual_backfill"))
    spec = dict(empty_flower_text_spec())
    incoming = visual.get("flower_text_spec")
    if isinstance(incoming, dict):
        spec.update({key: incoming.get(key, spec.get(key)) for key in spec})
    elif _text(incoming):
        spec["spec_line"] = _text(incoming)
    if not _text(spec.get("body_size")):
        spec["body_size"] = "中"
    if not _text(spec.get("emphasis_size")):
        spec["emphasis_size"] = "大"
    spec["body_position"] = _lift_spec_position(spec.get("body_position"), "画面中部")
    spec["emphasis_position"] = _lift_spec_position(spec.get("emphasis_position"), "画面中部")
    if not _text(spec.get("align")):
        spec["align"] = "居中"
    if not _text(spec.get("max_line_chars")):
        spec["max_line_chars"] = "12"
    if not _text(spec.get("en_size")):
        spec["en_size"] = "小"
    if not _text(spec.get("en_companion")):
        spec["en_companion"] = "重点句可配英文小字"
    if not _text(spec.get("mid_display")):
        spec["mid_display"] = "中部必须艺术化组合设计，不限于印章/古体/英文小字/颜色"
    if not _text(spec.get("product_name_layout")):
        spec["product_name_layout"] = "画右竖排|画左竖排"
    if not _text(spec.get("cut_fusion")):
        spec["cut_fusion"] = "优先段末切镜或段首开镜，不与动作抢镜；可黑屏专镜或字卡专镜；有旁白则无花字"
    if not _text(spec.get("cta_hold")):
        spec["cta_hold"] = "CTA可较长停留"
    if not _text(spec.get("vo_xor")):
        spec["vo_xor"] = "有旁白时不出花字，花字低于旁白，禁同步以免分心"
    if not _text(spec.get("glyph_lock")):
        spec["glyph_lock"] = "引号内逐字成形；含「X家」须见家，禁漏家、禁复写邻字、禁何乐乐享；店号/热线不进难认印章"
    if not _text(spec.get("seal_clear")):
        spec["seal_clear"] = "印=句外旁侧｜压字=禁｜替字=禁｜字印留空，禁止印面盖住任一花字"
    if not _text(spec.get("card_shot")):
        spec["card_shot"] = "店号/品牌/热线走字卡专镜：企业场景底+字层先合成一张静帧，本镜Static Hold按静帧原样上屏；禁手写；禁字卡图与场景图当两张参考图分喂；字卡不是CHAR/PROP/ENV，不抽实体；衍生环境不挂字卡"
    if not _text(spec.get("unity")):
        spec["unity"] = "全片同套字形与字色字重；禁底部避字幕；每段最多一条花字；一个动作最多一条；有旁白时不出花字，花字低于旁白，禁同步；优先段末/段首切镜或黑屏专镜，不与动作抢镜；CTA可较长停留；中部必须艺术化组合（不限于印章/古体/英文小字/颜色），只改字级、落位与艺术手段"
    if _text(spec.get("spec_line")):
        spec["spec_line"] = unique_flower_text_slot(
            spec["spec_line"].replace("正文位=底部居中", "正文位=画面中部").replace("收口位=底部居中", "收口位=画面中部")
        )
    spec["spec_line"] = compose_flower_text_spec_line(spec)
    visual["flower_text_spec"] = spec
    result["project_visual_backfill"] = visual

    stages = _as_dict(result.get("stage_plan"))
    preview = _as_dict(result.get("script_preview"))
    beats = preview.get("beats") if isinstance(preview.get("beats"), list) else []
    for index, key in enumerate(STAGE_KEYS):
        row = _as_dict(stages.get(key))
        filled = _compose_stage_flower_text(key, row)
        if filled:
            row["flower_text"] = filled
            stages[key] = row
        if index < len(beats) and isinstance(beats[index], dict):
            if filled and not _text(beats[index].get("flower_text")):
                beats[index]["flower_text"] = filled
            elif _text(beats[index].get("flower_text")) and not _text(row.get("flower_text")):
                row["flower_text"] = _text(beats[index].get("flower_text"))
                stages[key] = row
    result["stage_plan"] = stages
    if beats:
        preview["beats"] = beats
        result["script_preview"] = preview
    return result


def ensure_promo_music_prominence(result: Dict[str, Any]) -> Dict[str, Any]:
    """Promo scores stay foreground and audible; never default to bed-only."""
    visual = _as_dict(result.get("project_visual_backfill"))
    rec = _text(visual.get("music_recommendation"))
    if not rec:
        rec = "音量=并重｜权重=配乐主轴"
    else:
        if "音量=" not in rec:
            rec = f"{rec}｜音量=并重"
        else:
            rec = re.sub(r"音量=垫底", "音量=并重", rec)
            rec = re.sub(r"音量=弱", "音量=并重", rec)
        if "权重=" not in rec:
            rec = f"{rec}｜权重=配乐主轴"
    visual["music_recommendation"] = rec
    result["project_visual_backfill"] = visual
    return result


def merge_planner_result(parsed: Any) -> Dict[str, Any]:
    result = _deep_merge(empty_planner_result(), parsed if isinstance(parsed, dict) else {})
    films = result.get("benchmark_films")
    if not isinstance(films, list):
        legacy = _as_dict(result.get("benchmark_analysis"))
        films = []
        for key in ("premium_benchmarks", "viral_benchmarks"):
            rows = legacy.get(key) if isinstance(legacy.get(key), list) else []
            for row in rows:
                data = _as_dict(row)
                title = _text(data.get("title") or data.get("name"))
                if title:
                    films.append(
                        {
                            "title": title,
                            "why_picked": _text(data.get("why_picked") or data.get("film_traits")),
                            "techniques": _text(data.get("techniques") or data.get("shot_rules")),
                            "content_borrow": _text(data.get("content_borrow") or data.get("borrow") or data.get("narrative")),
                            "do_not_copy": _text(data.get("do_not_copy")),
                        }
                    )
        result["benchmark_films"] = films
    suggestions = result.get("supplement_suggestions")
    if not isinstance(suggestions, list):
        suggestions = []
    diagnosis = _as_dict(result.get("missing_info_diagnosis"))
    if not suggestions:
        for key in ("text_gaps", "visual_gaps"):
            for row in diagnosis.get(key) or []:
                data = _as_dict(row)
                if _text(data.get("item")):
                    suggestions.append(
                        {
                            "item": _text(data.get("item")),
                            "reason": "信息缺口",
                            "suggestion": _text(data.get("suggestion")),
                        }
                    )
        result["supplement_suggestions"] = suggestions
    return ensure_promo_music_prominence(ensure_flower_text_spec(sync_stage_plan_to_preview(result)))


def apply_user_dimension_locks(result: Dict[str, Any], campaign: Dict[str, Any]) -> Dict[str, Any]:
    """Lock core appeal and the unified four-stage rhythm; never let the model change them."""
    campaign = dump_model(campaign)
    pos = _as_dict(result.get("video_positioning"))
    narrative = _as_dict(result.get("narrative_plan"))
    presentation = _as_dict(result.get("presentation_plan"))
    goal_type = normalize_goal_type(campaign.get("goal_type"))
    presentation_form = _text(campaign.get("presentation_form"))
    platforms = normalize_platforms(campaign.get("platform"))
    overall = _as_dict(result.get("overall_scheme"))
    content_mode = _as_dict(result.get("content_mode"))
    expect_duration = normalize_expect_duration(campaign.get("expect_duration"))
    if goal_type:
        pos["goal_type"] = goal_type
        overall["main_goal_type"] = goal_type
    if expect_duration:
        pos["duration"] = expect_duration
        overall["target_duration"] = expect_duration
        campaign["expect_duration"] = expect_duration
    content_mode["primary_mode"] = UNIFIED_RHYTHM
    narrative["primary_model"] = UNIFIED_RHYTHM
    if presentation_form:
        presentation["primary_form"] = presentation_form
    if platforms:
        pos["platforms"] = platforms
    result["overall_scheme"] = overall
    result["content_mode"] = content_mode
    result["video_positioning"] = pos
    result["narrative_plan"] = narrative
    result["presentation_plan"] = presentation
    campaign["goal_type"] = goal_type
    campaign["narrative_model"] = UNIFIED_RHYTHM
    if not _text(campaign.get("presentation_form")):
        campaign["presentation_form"] = _text(presentation.get("primary_form"))
    if not platforms:
        campaign["platform"] = pos.get("platforms") if isinstance(pos.get("platforms"), list) else []
    ensure_promo_music_prominence(ensure_flower_text_spec(sync_stage_plan_to_preview(result)))
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


def _resolve_media_source(media_url: str, db: Session) -> str:
    raw = _refresh_managed_media_url(_text(media_url), db)
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
    for candidate in candidates:
        normalized = os.path.normpath(candidate)
        if os.path.isfile(normalized):
            return normalized
    return raw


def _extract_video_preview_frames(source: str, max_frames: int = 3) -> List[str]:
    if not source or max_frames <= 0:
        return []
    from app.services.video_service import _resolve_ffmpeg_exe, _resolve_ffprobe_exe, _run_ffmpeg

    ffmpeg = _resolve_ffmpeg_exe()
    probe = _resolve_ffprobe_exe(ffmpeg)
    duration = 0.0
    if probe:
        try:
            completed = subprocess.run(
                [probe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", source],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            duration = float((completed.stdout or "").strip() or 0)
        except Exception as exc:
            logger.warning("promo video probe failed: %s", exc)
    if duration <= 0:
        stamps = [0.4]
    elif duration < 2:
        stamps = [max(0.1, duration * 0.4)]
    else:
        ratios = (0.15, 0.5, 0.85)[:max_frames]
        stamps = [max(0.05, duration * ratio) for ratio in ratios]
    frames: List[str] = []
    with tempfile.TemporaryDirectory(prefix="promo_vid_") as tmp:
        for idx, stamp in enumerate(stamps[:max_frames]):
            out = os.path.join(tmp, f"frame_{idx}.jpg")
            try:
                _run_ffmpeg(
                    [ffmpeg, "-y", "-ss", f"{stamp:.2f}", "-i", source, "-frames:v", "1", "-q:v", "3", out],
                    timeout_seconds=45,
                )
            except Exception as exc:
                logger.warning("promo video frame extract failed t=%s: %s", stamp, exc)
                continue
            if not os.path.isfile(out):
                continue
            try:
                with open(out, "rb") as handle:
                    encoded = base64.b64encode(handle.read()).decode("utf-8")
                frames.append(f"data:image/jpeg;base64,{encoded}")
            except Exception as exc:
                logger.warning("promo video frame encode failed: %s", exc)
    return frames


def _ensure_rebuild_subjects(analysis: Dict[str, Any]) -> Dict[str, Any]:
    enriched = enrich_rebuild_analysis(analysis)
    analysis["rebuild_subjects"] = enriched.get("rebuild_subjects") or []
    if isinstance(enriched.get("image_list"), list):
        analysis["image_list"] = enriched["image_list"]
    return analysis


EXISTING_MATERIAL_ANALYSIS_MARK = "【素材解析】"


def _analysis_identity_set(analysis: Any) -> set:
    keys = set()
    data = _as_dict(analysis)
    for row in list(data.get("image_list") or []) + list(data.get("rebuild_subjects") or []):
        item = _as_dict(row)
        for value in (
            item.get("image_id"),
            item.get("object_name"),
            item.get("reference_name"),
            item.get("name_for_script"),
            item.get("img_url"),
            item.get("file_url"),
        ):
            text = _text(value)
            if text:
                keys.add(text)
        for source_id in item.get("source_image_ids") if isinstance(item.get("source_image_ids"), list) else []:
            text = _text(source_id)
            if text:
                keys.add(text)
    return keys


def _material_row_keys(item: Dict[str, Any]) -> List[str]:
    keys = []
    for value in (
        item.get("image_id"),
        item.get("object_name"),
        item.get("reference_name"),
        item.get("name_for_script"),
        item.get("img_url"),
        item.get("file_url"),
    ):
        text = _text(value)
        if text and text not in keys:
            keys.append(text)
    for source_id in item.get("source_image_ids") if isinstance(item.get("source_image_ids"), list) else []:
        text = _text(source_id)
        if text and text not in keys:
            keys.append(text)
    return keys


def _merge_material_row(target: Dict[str, Any], source: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in source.items():
        if key == "source_image_ids":
            current = target.get("source_image_ids") if isinstance(target.get("source_image_ids"), list) else []
            extra = value if isinstance(value, list) else []
            merged = []
            for item in [*current, *extra]:
                text = _text(item)
                if text and text not in merged:
                    merged.append(text)
            if merged:
                target["source_image_ids"] = merged
            continue
        if _text(target.get(key)):
            continue
        if value not in (None, "", [], {}):
            target[key] = value
    return target


def _unique_material_rows(data: Dict[str, Any], assets: Any = None) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    index_by: Dict[str, int] = {}

    def add(raw: Any) -> None:
        item = _as_dict(raw)
        keys = _material_row_keys(item)
        if not keys:
            return
        hit = next((index_by[key] for key in keys if key in index_by), None)
        if hit is not None:
            _merge_material_row(rows[hit], item)
            for key in keys:
                index_by[key] = hit
            return
        rows.append(dict(item))
        idx = len(rows) - 1
        for key in keys:
            index_by[key] = idx

    if isinstance(assets, list):
        for item in assets:
            add(item)
    for item in data.get("image_list") if isinstance(data.get("image_list"), list) else []:
        add(item)
    for item in data.get("rebuild_subjects") if isinstance(data.get("rebuild_subjects"), list) else []:
        add(item)
    return rows


def _format_one_material_line(item: Dict[str, Any]) -> str:
    name = _text(
        item.get("object_name") or item.get("name_for_script") or item.get("reference_name") or item.get("image_id")
    )
    if not name:
        return ""
    image_type = normalize_image_type(item.get("image_type") or item.get("asset_type") or item.get("kind"))
    kind = _text(item.get("media_kind")) or "image"
    bits = [f"名称={name}｜类型={image_type_label(image_type)}｜媒介={media_kind_label(kind)}"]
    seen_values = {name}
    remark = _text(item.get("user_remark"))
    if remark:
        bits.append(f"说明={remark}")
        seen_values.add(remark)
    field_pairs = [
        ("content_desc", "内容"),
        ("rebuild_brief", "外形"),
        ("appearance", "外形"),
        ("space_layout", "空间"),
        ("environment_detail", "场景"),
        ("clothing_or_material", "材质"),
        ("scale_and_shape", "形态"),
        ("color_and_markings", "标识"),
        ("prop_detail", "道具"),
        ("character_detail", "人物"),
        ("lighting", "光色"),
        ("light_info", "光影"),
        ("video_motion", "视频动作"),
        ("motion_from_video", "视频动作"),
        ("style_desc", "风格"),
    ]
    if image_type == "scene":
        field_pairs = [pair for pair in field_pairs if pair[0] not in {"prop_detail", "character_detail"}]
    used_labels = set()
    for key, label in field_pairs:
        value = _text(item.get(key))
        if not value or value in {"无", "未见"} or value in seen_values or label in used_labels:
            continue
        bits.append(f"{label}={value}")
        seen_values.add(value)
        used_labels.add(label)
    return "；".join(bits)


def format_existing_material_from_analysis(analysis: Any, assets: Any = None) -> str:
    data = _as_dict(analysis)
    if isinstance(assets, list):
        original_keys = _analysis_identity_set(data)
        data = filter_analysis_to_selected_assets(data, assets)
        if original_keys - _analysis_identity_set(data) or not assets:
            data["global_visual_summary"] = ""
    lines: List[str] = []
    summary = _text(data.get("global_visual_summary"))
    if summary:
        lines.append(f"综合视觉={summary}")
    extras = [_format_one_material_line(item) for item in _unique_material_rows(data, assets)]
    extras = [row for row in extras if row]
    if extras:
        lines.extend(f"- {row}" for row in extras)
    return "\n".join(lines).strip()


def existing_material_user_notes(current: Any) -> str:
    current_text = _text(current)
    if EXISTING_MATERIAL_ANALYSIS_MARK in current_text:
        return current_text.split(EXISTING_MATERIAL_ANALYSIS_MARK, 1)[0].strip()
    return current_text


def backfill_existing_material(current: Any, analysis: Any, assets: Any = None) -> str:
    generated = format_existing_material_from_analysis(analysis, assets)
    prefix = existing_material_user_notes(current)
    if not generated:
        return prefix
    block = f"{EXISTING_MATERIAL_ANALYSIS_MARK}\n{generated}"
    if prefix:
        return f"{prefix}\n\n{block}"
    return block


def existing_material_for_prompt(current: Any, analysis: Any, assets: Any) -> str:
    """Inject only 已有素材资源描述, rematched to the project library."""
    return backfill_existing_material(current, analysis, assets if isinstance(assets, list) else [])


def _enterprise_info_for_prompt(enterprise_info: Any) -> Dict[str, Any]:
    data = dict(_as_dict(enterprise_info))
    data.pop("image_assets", None)
    return data


def format_existing_material_prompt_block(existing_material: Any) -> str:
    text = _text(existing_material)
    if not text:
        return "已有素材资源描述：无"
    return f"已有素材资源描述：\n{text}"


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
    films = data.get("benchmark_films") if isinstance(data.get("benchmark_films"), list) else []
    traits = _as_dict(data.get("characteristic_analysis"))
    stages = _as_dict(data.get("stage_plan"))
    visual_backfill = _as_dict(data.get("project_visual_backfill"))
    supplements = data.get("supplement_suggestions") if isinstance(data.get("supplement_suggestions"), list) else []
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
            f"   - 花字: {row.get('flower_text') or ''}\n"
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
            f"- 组合模式: {overall.get('combination_mode') or '单片全案'}",
            f"- 核心诉求: {overall.get('main_goal_type') or pos.get('goal_type') or ''}",
            f"- 统一节奏: {UNIFIED_RHYTHM}",
            f"- 预期时长: {overall.get('target_duration') or campaign.get('expect_duration') or pos.get('duration') or ''}",
            f"- 时长分配: {overall.get('duration_budget') or ''}",
            f"- 成功标准: {overall.get('success_metric') or ''}",
            f"- 宣传要点: {overall.get('promo_focus') or ''}",
            f"- 主要卖点: {overall.get('selling_points') or ''}",
            f"- 画面核: {overall.get('visual_core') or ''}",
            "",
            "## 0.2) 主体特性分析",
            f"- 企业: {traits.get('enterprise') or ''}",
            f"- 品牌: {traits.get('brand') or ''}",
            f"- 产品: {traits.get('product') or ''}",
            f"- 客群洞察: {traits.get('audience_insight') or ''}",
            "",
            "## 0.3) 对标经典片",
            bullets(films),
            "",
            "## 0.4) 四段节奏规划",
            *[
                (
                    f"- {STAGE_NAMES[key]}（{_as_dict(stages.get(key)).get('duration') or ''}）\n"
                    f"   - 感官: {_as_dict(stages.get(key)).get('sensory') or ''}\n"
                    f"   - 内容（编剧逐字核销）: {_as_dict(stages.get(key)).get('content') or ''}\n"
                    f"   - 文案: {_as_dict(stages.get(key)).get('copy') or ''}\n"
                    f"   - 花字: {_as_dict(stages.get(key)).get('flower_text') or ''}\n"
                    f"   - 技法: {_as_dict(stages.get(key)).get('technique_assoc') or ''}\n"
                    f"   - CTA: {_as_dict(stages.get(key)).get('cta') or ''}"
                )
                for key in STAGE_KEYS
            ],
            "",
            "## 0.5) 基调与整体风格（project_visual_backfill）",
            f"- Global_Style: {visual_backfill.get('Global_Style') or ''}",
            f"- style_mode: {visual_backfill.get('style_mode') or ''}",
            f"- tone: {visual_backfill.get('tone') or ''}",
            f"- lighting: {visual_backfill.get('lighting') or ''}",
            f"- color_palette: {visual_backfill.get('color_palette') or ''}",
            f"- color_spectrum: {visual_backfill.get('color_spectrum') or ''}",
            f"- music_recommendation: {visual_backfill.get('music_recommendation') or ''}",
            f"- voiceover_style: {visual_backfill.get('voiceover_style') or ''}",
            f"- sfx_style: {visual_backfill.get('sfx_style') or ''}",
            f"- flower_text_spec: {compose_flower_text_spec_line(visual_backfill.get('flower_text_spec'))}",
            f"- borrowed_films: {', '.join(_text(x) for x in (visual_backfill.get('borrowed_films') or []) if _text(x))}",
            f"- borrowed_films_note: {visual_backfill.get('borrowed_films_note') or ''}",
            "",
            "## 0.6) 建议补充的内容",
            bullets(supplements),
            "",
            "## 0.7) 内容模式与大纲",
            f"- 主模式: {content_mode.get('primary_mode') or UNIFIED_RHYTHM}",
            f"- 模式定义: {content_mode.get('mode_definition') or ''}",
            *(outline_lines or ["- （空）"]),
            "",
            "## 0.8) 各平台策略",
            bullets(platform_strategies),
            "",
            "## 0.9) 系列方案组合",
            bullets(series_schemes),
            "",
            "## 1.0) 类型判定",
            f"- Primary Promo Type（核心诉求）: {pos.get('goal_type') or ''}",
            f"- Strategic Goal（战略目标）: {pos.get('communication_goal') or ''}",
            f"- Type Rationale（判定依据）: {pos.get('rationale') or ''}",
            "",
            "## 1) 项目目标与受众画像",
            f"- Enterprise（企业）: {enterprise.get('enterprise_name') or ''}",
            f"- Brand（品牌）: {enterprise.get('brand_name') or ''}",
            f"- Product / Service（产品与服务）: {enterprise.get('product_name') or '无'}",
            f"- Basic Intro（基本介绍）: {campaign.get('basic_intro') or campaign.get('user_raw_text') or ''}",
            f"- Communication Goal（传播目标）: {pos.get('communication_goal') or biz.get('communication_goal') or ''}",
            f"- Core Audience（核心受众）: {campaign.get('target_audience') or biz.get('target_user') or enterprise.get('target_user') or ''}",
            f"- Market / Competitors（竞品与市场）: {campaign.get('market_and_competitors') or enterprise.get('competitor_problem') or ''}",
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
            f"- Visual Rebuild:\n{format_visual_rebuild_lines(analysis) or '- （无）'}",
            "",
            "## 6) 素材采集清单",
            bullets(materials),
            "",
            "## 7) 各阶段内容规划（成片脚本方向）",
            f"- Logline: {script.get('logline') or ''}",
            *(beat_lines or ["- （空）"]),
            "",
            "## 8) 执行注意事项",
            f"- Constraints: {campaign.get('constraint') or ''}",
            f"- Existing Material: {campaign.get('existing_material') or '无（剧情可新构思，画面后续补充或AI生成）'}",
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
        "campaign_objective": _text(campaign.get("basic_intro") or campaign.get("user_raw_text")),
        "target_audience": _text(campaign.get("target_audience") or enterprise.get("target_user")),
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
        **catalog_preview_fields(db, "enterprise", row.id),
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
        **catalog_preview_fields(db, "brand", row.id),
    }


def serialize_promo_product(row: PromoProduct, db: Optional[Session] = None) -> Dict[str, Any]:
    enterprise = getattr(row, "enterprise", None)
    brand = getattr(row, "brand", None)
    data = {
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
    session = db or object_session(row)
    if session is not None:
        data.update(catalog_preview_fields(session, "offering", row.id))
    else:
        data["asset_count"] = 0
        data["asset_previews"] = []
    return data


def catalog_asset_as_planner_asset(row: Any) -> Dict[str, Any]:
    data = dump_model(row)
    url = _text(data.get("file_url") or data.get("img_url"))
    extra = _as_dict(data.get("extra_info"))
    analysis = _as_dict(extra.get("image_asset_analysis") or data.get("image_asset_analysis"))
    return {
        "image_id": _text(data.get("image_id")),
        "img_url": url,
        "file_url": url,
        "image_type": normalize_image_type(data.get("asset_type") or data.get("image_type")),
        "media_kind": normalize_media_kind(data.get("media_kind")),
        "object_name": _text(data.get("object_name")),
        "user_remark": _text(data.get("user_remark")),
        "owner_kind": _text(data.get("owner_kind")) or "enterprise",
        "owner_entity_id": data.get("owner_entity_id"),
        "catalog_asset_id": data.get("id"),
        "analysis_status": _text(extra.get("analysis_status") or data.get("analysis_status")),
        "analysis_error": _text(extra.get("analysis_error") or data.get("analysis_error")),
        "image_asset_analysis": analysis,
    }


def slice_asset_analysis(analysis: Any, asset: Any) -> Dict[str, Any]:
    data = _as_dict(analysis)
    if not data.get("image_list") and not data.get("rebuild_subjects") and not data.get("global_visual_summary"):
        return {}
    return merge_single_asset_analysis({}, asset, data)


def catalog_analysis_fields(extra: Any, asset: Any = None) -> Dict[str, Any]:
    data = _as_dict(extra)
    analysis = _as_dict(data.get("image_asset_analysis") or data.get("analysis"))
    status = _text(data.get("analysis_status"))
    error = _text(data.get("analysis_error"))
    row = _analysis_row_for(analysis, asset or {"image_id": _text(data.get("image_id"))})
    if not status:
        if image_row_is_success(row):
            status = ANALYSIS_STATUS_SUCCESS
        elif _text(row.get("analysis_status")) == ANALYSIS_STATUS_FAILED or _text(row.get("analysis_error")):
            status = ANALYSIS_STATUS_FAILED
            error = error or _text(row.get("analysis_error"))
        elif analysis:
            status = ANALYSIS_STATUS_PENDING
    return {
        "analysis_status": status or ANALYSIS_STATUS_PENDING,
        "analysis_error": error,
        "image_asset_analysis": analysis,
    }


def merge_catalog_analysis_extra(
    extra: Any,
    asset: Any,
    source_analysis: Any = None,
    *,
    overwrite: bool = False,
) -> Dict[str, Any]:
    current = dict(_as_dict(extra))
    incoming = slice_asset_analysis(source_analysis, asset)
    if not incoming:
        return current
    existing = catalog_analysis_fields(current, asset)
    incoming_row = _analysis_row_for(incoming, asset)
    incoming_ok = image_row_is_success(incoming_row)
    if existing.get("analysis_status") == ANALYSIS_STATUS_SUCCESS and not incoming_ok and not overwrite:
        return current
    current["image_asset_analysis"] = incoming
    current["analysis_status"] = incoming_row.get("analysis_status") or ANALYSIS_STATUS_PENDING
    current["analysis_error"] = _text(incoming_row.get("analysis_error"))
    return current


def write_catalog_analysis(
    row: PromoCatalogAsset,
    analysis: Any,
    *,
    status: str = "",
    error: str = "",
    overwrite: bool = True,
) -> None:
    extra = merge_catalog_analysis_extra(
        row.extra_info,
        catalog_asset_as_planner_asset(row),
        analysis,
        overwrite=overwrite,
    )
    if status:
        extra["analysis_status"] = _text(status)
    if error or status:
        extra["analysis_error"] = _text(error)
    extra["image_asset_analysis"] = _as_dict(analysis) or extra.get("image_asset_analysis") or {}
    row.extra_info = extra
    flag_modified(row, "extra_info")
    row.updated_at = now_bj_iso()


def serialize_promo_catalog_asset(row: PromoCatalogAsset) -> Dict[str, Any]:
    url = _text(row.file_url)
    asset_type = normalize_image_type(row.asset_type)
    extra = dict(row.extra_info or {})
    fields = catalog_analysis_fields(extra, {"image_id": row.image_id or ""})
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
        "extra_info": extra,
        "analysis_status": fields["analysis_status"],
        "analysis_error": fields["analysis_error"],
        "image_asset_analysis": fields["image_asset_analysis"],
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


def catalog_preview_fields(
    db: Session,
    owner_kind: str,
    owner_entity_id: int,
    *,
    limit: int = 6,
) -> Dict[str, Any]:
    rows = list_catalog_assets(db, owner_kind=owner_kind, owner_entity_id=int(owner_entity_id))
    return {
        "asset_count": len(rows),
        "asset_previews": [
            {
                "id": item.get("id"),
                "img_url": item.get("img_url") or "",
                "media_kind": item.get("media_kind") or "image",
                "object_name": item.get("object_name") or "",
            }
            for item in rows[:limit]
        ],
    }


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
                    "owner_entity_id": item.get("owner_entity_id") or entity_id,
                    "catalog_asset_id": item.get("id"),
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
    previous_enterprise_id = getattr(project, "enterprise_id", None)
    previous_brand_id = getattr(project, "brand_id", None)
    previous_product_id = getattr(project, "product_id", None)
    project.enterprise_id = enterprise.id if enterprise else previous_enterprise_id
    project.brand_id = brand.id if brand else previous_brand_id
    project.product_id = product.id if product else previous_product_id
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


def resolve_share_enterprise_id(
    project: Any = None,
    planner_input: Any = None,
    assets: Any = None,
    explicit_id: Any = None,
) -> Optional[int]:
    extra = dict(getattr(project, "extra_info", None) or {}) if project is not None else {}
    planner = _as_dict(planner_input)
    candidates = [
        explicit_id,
        getattr(project, "enterprise_id", None) if project is not None else None,
        planner.get("enterprise_id"),
        extra.get("enterprise_id"),
        _as_dict(extra.get("promo_planner_input")).get("enterprise_id"),
    ]
    for asset in assets or []:
        data = dump_model(asset)
        if _text(data.get("owner_kind") or "project") in {"project", "enterprise"}:
            candidates.append(data.get("owner_entity_id"))
    for raw in candidates:
        try:
            value = int(raw or 0)
        except Exception:
            value = 0
        if value:
            return value
    return None


def _enterprise_name_key(value: Any) -> str:
    return re.sub(r"\s+", "", _text(value)).casefold()


def match_enterprise_id_from_records(
    *,
    project_enterprise_id: Any = None,
    planner_enterprise_id: Any = None,
    enterprise_name: Any = None,
    enterprises: Any = None,
    preferred_enterprise_id: Any = None,
) -> Optional[int]:
    rows = []
    for item in enterprises or []:
        data = dump_model(item)
        try:
            eid = int(data.get("id") or 0)
        except Exception:
            eid = 0
        if not eid:
            continue
        rows.append({"id": eid, "name_key": _enterprise_name_key(data.get("name") or data.get("enterprise_name"))})
    for raw in (project_enterprise_id, planner_enterprise_id):
        try:
            value = int(raw or 0)
        except Exception:
            value = 0
        if value and (not rows or any(item["id"] == value for item in rows)):
            return value
    name_key = _enterprise_name_key(enterprise_name)
    if name_key:
        for item in rows:
            if item["name_key"] == name_key:
                return int(item["id"])
    try:
        preferred = int(preferred_enterprise_id or 0)
    except Exception:
        preferred = 0
    if len(rows) == 1:
        return int(rows[0]["id"])
    return None


def _planner_input_for_project(db: Session, project: PromoProject) -> Dict[str, Any]:
    state = load_planner_state(db, project)
    data = _as_dict(state.get("promo_planner_input"))
    if data.get("enterprise_info") or data.get("enterprise_id"):
        return data
    extra = dict(getattr(project, "extra_info", None) or {})
    fallback = _as_dict(extra.get("promo_planner_input"))
    return fallback or data


def collect_project_shareable_assets(db: Session, project: PromoProject) -> List[Dict[str, Any]]:
    planner = _planner_input_for_project(db, project)
    merged = normalize_image_assets((_as_dict(planner.get("enterprise_info")).get("image_assets")))
    extra = dict(getattr(project, "extra_info", None) or {})
    extra_assets = normalize_image_assets(
        _as_dict(_as_dict(extra.get("promo_planner_input")).get("enterprise_info")).get("image_assets")
    )
    seen = {item.get("image_id") or item.get("img_url") for item in merged if item.get("image_id") or item.get("img_url")}
    for item in extra_assets:
        key = item.get("image_id") or item.get("img_url")
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        merged.append(item)
    rows = db.query(PromoImageAsset).filter(PromoImageAsset.promo_project_id == int(project.id)).all()
    for row in rows:
        image_id = _text(row.image_id)
        url = _text(row.img_url)
        key = image_id or url
        if not url or (key and key in seen):
            continue
        if key:
            seen.add(key)
        merged.append(
            {
                "img_url": url,
                "image_id": image_id,
                "image_type": normalize_image_type(row.image_type),
                "media_kind": "image",
                "owner_kind": "project",
                "object_name": _text(row.object_name),
                "user_remark": _text(row.user_remark),
            }
        )
    return merged


def match_enterprise_for_project(
    db: Session,
    project: PromoProject,
    *,
    owner_id: Any = None,
    preferred_enterprise_id: Any = None,
) -> Optional[int]:
    planner = _planner_input_for_project(db, project)
    enterprise_info = _as_dict(planner.get("enterprise_info"))
    oid = int(owner_id or getattr(project, "owner_id", 0) or 0)
    query = db.query(PromoEnterprise).filter(PromoEnterprise.is_deleted.is_(False))
    if oid:
        query = query.filter(PromoEnterprise.owner_id == oid)
    enterprises = query.all()
    return match_enterprise_id_from_records(
        project_enterprise_id=resolve_share_enterprise_id(project, planner, enterprise_info.get("image_assets")),
        planner_enterprise_id=planner.get("enterprise_id"),
        enterprise_name=enterprise_info.get("enterprise_name"),
        enterprises=[{"id": row.id, "name": row.name} for row in enterprises],
        preferred_enterprise_id=preferred_enterprise_id,
    )


def sync_historical_promo_assets_to_enterprises(
    db: Session,
    *,
    owner_id: Any,
    enterprise_id: Any = None,
) -> List[Dict[str, Any]]:
    """Push historical project uploads into the matching enterprise library."""
    try:
        oid = int(owner_id or 0)
    except Exception:
        oid = 0
    try:
        target_eid = int(enterprise_id or 0) or None
    except Exception:
        target_eid = None
    query = db.query(PromoProject).filter(_active_promo_clause())
    if oid:
        query = query.filter(PromoProject.owner_id == oid)
    for project in query.all():
        assets = collect_project_shareable_assets(db, project)
        if not assets:
            continue
        matched = match_enterprise_for_project(
            db,
            project,
            owner_id=oid or getattr(project, "owner_id", None),
            preferred_enterprise_id=target_eid,
        )
        if not matched:
            continue
        if target_eid and int(matched) != int(target_eid):
            continue
        share_project_assets_to_enterprise_catalog(
            db,
            enterprise_id=matched,
            owner_id=oid or getattr(project, "owner_id", None),
            assets=assets,
            source_project_id=int(project.id),
            source_analysis=_as_dict(
                (_as_dict((load_planner_state(db, project).get("promo_planner_result") or {})).get("image_asset_analysis"))
            ),
        )
        if not getattr(project, "enterprise_id", None):
            project.enterprise_id = matched
    db.flush()
    if target_eid:
        return list_catalog_assets(db, owner_kind="enterprise", owner_entity_id=int(target_eid))
    return []


def backfill_enterprise_catalog_from_projects(
    db: Session,
    *,
    enterprise_id: Any,
    owner_id: Any = None,
) -> List[Dict[str, Any]]:
    return sync_historical_promo_assets_to_enterprises(
        db,
        owner_id=owner_id,
        enterprise_id=enterprise_id,
    )


def share_project_assets_to_enterprise_catalog(
    db: Session,
    *,
    enterprise_id: Any,
    owner_id: Any,
    assets: List[Dict[str, Any]],
    source_project_id: Optional[int] = None,
    source_analysis: Any = None,
) -> List[Dict[str, Any]]:
    """Write this film's uploads into the enterprise library so later projects can pick them."""
    normalized = normalize_image_assets(assets)
    try:
        eid = int(enterprise_id or 0)
        oid = int(owner_id or 0)
    except Exception:
        return normalized
    if eid and not oid:
        enterprise = (
            db.query(PromoEnterprise)
            .filter(PromoEnterprise.id == eid, PromoEnterprise.is_deleted.is_(False))
            .first()
        )
        try:
            oid = int(getattr(enterprise, "owner_id", 0) or 0) if enterprise else 0
        except Exception:
            oid = 0
    if not eid or not oid:
        return normalized

    existing = (
        db.query(PromoCatalogAsset)
        .filter(
            PromoCatalogAsset.is_deleted.is_(False),
            PromoCatalogAsset.owner_kind == "enterprise",
            PromoCatalogAsset.owner_entity_id == eid,
        )
        .all()
    )
    by_id = {int(row.id): row for row in existing}
    by_image_id = {_text(row.image_id): row for row in existing if _text(row.image_id)}
    by_url = {_text(row.file_url): row for row in existing if _text(row.file_url)}
    now_iso = now_bj_iso()
    out: List[Dict[str, Any]] = []
    for asset in normalized:
        url = _text(asset.get("img_url"))
        if not url:
            continue
        owner_kind = _text(asset.get("owner_kind")) or "project"
        catalog_id = asset.get("catalog_asset_id")
        row = by_id.get(int(catalog_id)) if catalog_id else None
        if row is None and _text(asset.get("image_id")):
            row = by_image_id.get(_text(asset.get("image_id")))
        if row is None:
            row = by_url.get(url)
        if owner_kind != "project":
            if row is not None:
                asset["catalog_asset_id"] = row.id
                asset["owner_entity_id"] = asset.get("owner_entity_id") or row.owner_entity_id
            out.append(asset)
            continue
        extra = dict(row.extra_info or {}) if row is not None else {}
        if source_project_id:
            extra["source_promo_project_id"] = int(source_project_id)
        extra = merge_catalog_analysis_extra(extra, asset, source_analysis)
        image_id = _text(asset.get("image_id")) or f"promo-ent-{eid}-{now_iso}"
        asset["image_id"] = image_id
        if row is None:
            row = PromoCatalogAsset(
                owner_id=oid,
                owner_kind="enterprise",
                owner_entity_id=eid,
                media_kind=normalize_media_kind(asset.get("media_kind")),
                asset_type=normalize_image_type(asset.get("image_type")),
                image_id=image_id,
                file_url=url,
                object_name=_text(asset.get("object_name")),
                user_remark=_text(asset.get("user_remark")),
                extra_info=extra,
            )
            db.add(row)
            db.flush()
            by_id[int(row.id)] = row
            by_image_id[_text(row.image_id)] = row
            by_url[_text(row.file_url)] = row
        else:
            row.file_url = url
            row.media_kind = normalize_media_kind(asset.get("media_kind") or row.media_kind)
            row.asset_type = normalize_image_type(asset.get("image_type") or row.asset_type)
            if _text(asset.get("object_name")):
                row.object_name = _text(asset.get("object_name"))
            row.user_remark = _text(asset.get("user_remark"))
            row.extra_info = extra
            row.updated_at = now_iso
        asset["catalog_asset_id"] = row.id
        asset["owner_entity_id"] = eid
        out.append(asset)
    return out


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
        row.enterprise_info = dict(planner_input.get("enterprise_info") or {})
        row.campaign_demand = dict(planner_input.get("campaign_demand") or {})
        flag_modified(row, "enterprise_info")
        flag_modified(row, "campaign_demand")
        row.updated_at = now_iso
        assets = list((row.enterprise_info or {}).get("image_assets") or [])
        sync_promo_image_assets(db, pid, assets)
        shareable = collect_project_shareable_assets(db, project)
        enterprise_id = resolve_share_enterprise_id(
            project,
            planner_input,
            shareable or assets,
        )
        if enterprise_id and not getattr(project, "enterprise_id", None):
            project.enterprise_id = enterprise_id
        if enterprise_id:
            existing_result = _as_dict(
                getattr(
                    db.query(PromoPlannerResult).filter(PromoPlannerResult.promo_project_id == pid).first(),
                    "result",
                    None,
                )
            )
            source_analysis = _as_dict((planner_result or existing_result or {}).get("image_asset_analysis"))
            shared = share_project_assets_to_enterprise_catalog(
                db,
                enterprise_id=enterprise_id,
                owner_id=getattr(project, "owner_id", None),
                assets=shareable or assets,
                source_project_id=pid,
                source_analysis=source_analysis,
            )
            by_key = {
                item.get("image_id") or item.get("img_url"): item
                for item in shared
                if item.get("image_id") or item.get("img_url")
            }
            patched = []
            for asset in assets:
                key = asset.get("image_id") or asset.get("img_url")
                patched.append(by_key.get(key) if key and key in by_key else asset)
            enterprise_info = dict(row.enterprise_info or {})
            enterprise_info["image_assets"] = patched
            row.enterprise_info = enterprise_info
            flag_modified(row, "enterprise_info")
        campaign = dict(row.campaign_demand or {})
        analysis_src = planner_result or _as_dict(
            getattr(
                db.query(PromoPlannerResult).filter(PromoPlannerResult.promo_project_id == pid).first(),
                "result",
                None,
            )
        )
        campaign["existing_material"] = backfill_existing_material(
            campaign.get("existing_material"),
            _as_dict(analysis_src).get("image_asset_analysis"),
            selected_planner_image_assets(row.enterprise_info),
        )
        row.campaign_demand = campaign
        flag_modified(row, "campaign_demand")
        planner_input["campaign_demand"] = campaign
        if isinstance(planner_result, dict):
            planner_result["existing_material"] = campaign["existing_material"]
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
    user = _snapshot_user_principal(current_user)
    is_owner = int(getattr(project, "owner_id", 0) or 0) == int(user.id or 0)
    is_superuser = bool(user.is_superuser)
    is_root = is_superuser and str(user.username or "").strip().lower() == "ylsystem"
    is_temp_view = bool(is_superuser and not is_owner and not is_root)
    script_meta = load_promo_script_meta(db, project)
    global_info = resolve_promo_project_global_info(project)
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
        "extra_info": attach_promo_project_global_info(dict(project.extra_info or {}), global_info),
        "global_info": global_info,
        "owner_id": project.owner_id,
        "enterprise_id": project.enterprise_id,
        "brand_id": project.brand_id,
        "product_id": project.product_id,
        "enterprise": serialize_promo_enterprise(db, enterprise) if enterprise else None,
        "brand": serialize_promo_brand(db, brand) if brand else None,
        "product": serialize_promo_product(product, db) if product else None,
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
    billing_lock: Any = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    llm_config = _json_llm_config(llm_config)
    provider = llm_config.get("provider")
    model = llm_config.get("model")
    user_id = int(getattr(_snapshot_user_principal(current_user), "id", 0) or 0)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    reservation_tx = None
    lock = billing_lock if billing_lock is not None else nullcontext()
    async with lock:
        if billing_service.is_token_pricing(db, "llm_chat", provider, model):
            est = billing_service.estimate_reserve_tokens_from_messages(messages)
            extra_image_tokens = 900 * len(image_urls or [])
            est_input = int(est.get("input_tokens", 0) or 0) + extra_image_tokens
            est_output = int(est.get("output_tokens", 0) or 0)
            reservation_tx = billing_service.reserve_credits(
                db,
                user_id,
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
            billing_service.check_balance(db, user_id, "llm_chat", provider, model)

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
            async with lock:
                billing_service.cancel_reservation(db, _reservation_tx_id(reservation_tx), str(exc))
        raise

    raw = resp.get("content")
    parsed = extract_json_object(raw)
    if not parsed:
        if reservation_tx:
            async with lock:
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
    async with lock:
        if reservation_tx:
            billing_service.settle_reservation(db, _reservation_tx_id(reservation_tx), settle_details)
        else:
            billing_service.deduct_credits(db, user_id, "llm_chat", provider, model, settle_details)
    return parsed, resp if isinstance(resp, dict) else {}


def _planner_image_assets(planner_input: Dict[str, Any]) -> List[Dict[str, Any]]:
    enterprise = _as_dict(planner_input.get("enterprise_info"))
    return selected_planner_image_assets(enterprise)


def build_uploaded_asset_catalog(assets: Any, analysis: Any = None) -> List[Dict[str, Any]]:
    data = _as_dict(analysis)
    by_id: Dict[str, Dict[str, Any]] = {}
    by_name: Dict[str, Dict[str, Any]] = {}
    for row in data.get("image_list") if isinstance(data.get("image_list"), list) else []:
        item = _as_dict(row)
        image_id = _text(item.get("image_id"))
        name = _text(item.get("object_name") or item.get("reference_name"))
        if image_id:
            by_id[image_id] = item
        if name:
            by_name[name] = item
    catalog: List[Dict[str, Any]] = []
    seen_ids = set()
    source = [item for item in assets if isinstance(item, dict)] if isinstance(assets, list) else []
    for index, raw in enumerate(source, 1):
        asset = _as_dict(raw)
        image_id = _text(asset.get("image_id"))
        name = _text(asset.get("object_name"))
        parsed = by_id.get(image_id) or by_name.get(name) or {}
        image_type = normalize_image_type(asset.get("image_type") or parsed.get("image_type") or "product")
        media_kind = normalize_media_kind(asset.get("media_kind") or parsed.get("media_kind"))
        catalog.append(
            {
                "index": index,
                "image_id": image_id,
                "object_name": name or _text(parsed.get("object_name") or parsed.get("reference_name")),
                "image_type": image_type,
                "image_type_label": IMAGE_TYPE_LABELS.get(image_type, "产品"),
                "media_kind": media_kind,
                "media_kind_label": MEDIA_KIND_LABELS.get(media_kind, "图片"),
                "user_remark": _text(asset.get("user_remark") or parsed.get("user_remark")),
                "owner_kind": _text(asset.get("owner_kind")) or "project",
                "img_url": _text(asset.get("img_url") or parsed.get("img_url")),
                "content_desc": _text(parsed.get("content_desc")),
                "rebuild_brief": _text(parsed.get("rebuild_brief")),
                "character_detail": _text(parsed.get("character_detail")),
                "prop_detail": _text(parsed.get("prop_detail")),
                "environment_detail": _text(parsed.get("environment_detail")),
                "video_motion": _text(parsed.get("video_motion")),
                "light_info": _text(parsed.get("light_info")),
            }
        )
        if image_id:
            seen_ids.add(image_id)
    next_index = len(catalog) + 1
    for row in data.get("image_list") if isinstance(data.get("image_list"), list) else []:
        item = _as_dict(row)
        image_id = _text(item.get("image_id"))
        name = _text(item.get("object_name") or item.get("reference_name"))
        if (image_id and image_id in seen_ids) or (not image_id and name and any(r.get("object_name") == name for r in catalog)):
            continue
        image_type = normalize_image_type(item.get("image_type") or "product")
        media_kind = normalize_media_kind(item.get("media_kind"))
        catalog.append(
            {
                "index": next_index,
                "image_id": image_id,
                "object_name": name,
                "image_type": image_type,
                "image_type_label": IMAGE_TYPE_LABELS.get(image_type, "产品"),
                "media_kind": media_kind,
                "media_kind_label": MEDIA_KIND_LABELS.get(media_kind, "图片"),
                "user_remark": _text(item.get("user_remark")),
                "owner_kind": "project",
                "img_url": _text(item.get("img_url")),
                "content_desc": _text(item.get("content_desc")),
                "rebuild_brief": _text(item.get("rebuild_brief")),
                "character_detail": _text(item.get("character_detail")),
                "prop_detail": _text(item.get("prop_detail")),
                "environment_detail": _text(item.get("environment_detail")),
                "video_motion": _text(item.get("video_motion")),
                "light_info": _text(item.get("light_info")),
            }
        )
        next_index += 1
        if image_id:
            seen_ids.add(image_id)
    return catalog


def format_uploaded_asset_catalog_text(catalog: Any) -> str:
    rows = [item for item in catalog if isinstance(item, dict)] if isinstance(catalog, list) else []
    if not rows:
        return "无上传素材。"
    lines = ["# 上传素材台账（名称/类型/说明为用户元数据，禁止改名改类型）"]
    for row in rows:
        name = _text(row.get("object_name")) or "未命名"
        lines.append(
            f"{row.get('index') or ''}. 名称={name}｜类型={_text(row.get('image_type_label')) or image_type_label(row.get('image_type'))}"
            f"（{_text(row.get('image_type')) or 'product'}）"
            f"｜媒介={_text(row.get('media_kind_label')) or media_kind_label(row.get('media_kind'))}"
            f"｜说明={_text(row.get('user_remark')) or '无'}"
            f"｜image_id={_text(row.get('image_id')) or '无'}"
        )
        extras = []
        for key, label in (
            ("content_desc", "解析内容"),
            ("rebuild_brief", "重生外形"),
            ("character_detail", "人物"),
            ("prop_detail", "道具"),
            ("environment_detail", "场景"),
            ("video_motion", "视频动作"),
            ("light_info", "光影"),
        ):
            value = _text(row.get(key))
            if value and value not in {"无", "未见"}:
                extras.append(f"{label}={value}")
        if extras:
            lines.append("   " + "；".join(extras))
    return "\n".join(lines)


def _build_image_analysis_user_prompt(
    vision_items: List[Dict[str, Any]],
    assets: Optional[List[Dict[str, Any]]] = None,
) -> str:
    catalog = build_uploaded_asset_catalog(assets or vision_items)
    lines = [
        "请按系统约定解析下列图片与视频关键帧。本请求通常只有一条素材；视频多帧仍合并为同一 image_id。媒体按顺序附在本消息后。",
        "下列「上传素材台账」是用户权威元数据：名称=object_name、类型=image_type、说明=user_remark、媒介=media_kind。",
        "解析只补画面可见细节；禁止改名、改类型、丢说明。说明未在画面出现也必须原样回传到 user_remark，并在 rebuild_brief 点明「用户说明=…」。",
        "同一 image_id 的多帧属于同一条视频，须合并成一条 image_list 与对应 rebuild_subjects。",
        "必须拆出可重生的场景、道具、产品、人物，写出可核销外形/材质/空间细节。",
        "禁止解析水印：图库/平台/版权/预览水印、半透明斜向字、四角版权行、叠字署名一律当不存在，不得写入任何字段，也不得当作品牌标识。物体本身的印刷/铭刻文字仍须写。",
        "场景图（类型=场景）只重生环境，图内人物/道具/产品不另抽 CHAR/PROP，character_detail 与 prop_detail 写无。",
        "每条 rebuild_brief 与分槽必须写满可见细节：轮廓/形制、材质、主辅色、标识或文字、尺度或体态、光色；人物加骨相五官发型衣着；环境加围合地面天花主陈设。禁止一句空形容。非场景条的同类型同框主体进入 rebuild_subjects。",
        "",
        format_uploaded_asset_catalog_text(catalog),
        "",
        "附后画面与台账对应关系：",
    ]
    for idx, item in enumerate(vision_items, 1):
        name = _text(item.get("object_name")) or _text(item.get("image_id")) or f"第{idx}条"
        lines.append(
            f"附画面{idx} → 名称={name}｜类型={image_type_label(item.get('image_type'))}"
            f"｜媒介={media_kind_label(item.get('media_kind'))}"
            f"｜说明={_text(item.get('user_remark')) or '无'}"
            f"｜帧={item.get('frame_label') or '单张'}"
            f"｜image_id={_text(item.get('image_id')) or '无'}"
        )
    lines.append("只输出 JSON。")
    return "\n".join(lines)


def _promo_skill_system_prompt(prompt_ref: str, project_info: Any = None) -> str:
    body = _resolve_prompt_text(prompt_ref)
    lexicon = _resolve_prompt_text("promo_technique_lexicon.md")
    parts = [body]
    info = _as_dict(project_info)
    if info:
        from app.services.shot_generation_prompts import _build_project_prompt_context

        section = _text(_build_project_prompt_context(info).get("project_context_section"))
        if section:
            parts.append(
                "以下为用户锁定的项目信息，规划与编剧必须继承，禁止另起冲突的类型、语言、风格、画幅或时地。\n"
                + section
            )
    parts.append(lexicon)
    return "\n\n".join(parts)


def _count_named_assets(planner_input: Dict[str, Any]) -> int:
    enterprise = _as_dict(planner_input.get("enterprise_info"))
    assets = enterprise.get("image_assets") if isinstance(enterprise.get("image_assets"), list) else []
    return sum(1 for item in assets if isinstance(item, dict) and (_text(item.get("img_url")) or _text(item.get("object_name"))))


def _build_scheme_user_prompt(
    planner_input: Dict[str, Any],
    image_analysis: Dict[str, Any],
    warnings: List[str],
    project_info: Optional[Dict[str, Any]] = None,
) -> str:
    named_asset_count = _count_named_assets(planner_input)
    has_uploaded_assets = named_asset_count > 0
    assets = _planner_image_assets(planner_input)
    image_analysis = filter_analysis_to_selected_assets(image_analysis, assets)
    existing_material = existing_material_for_prompt(
        _as_dict(planner_input.get("campaign_demand")).get("existing_material"),
        image_analysis,
        assets,
    )
    demand = dict(_as_dict(planner_input.get("campaign_demand")))
    demand["existing_material"] = existing_material
    payload = {
        "project_info": project_info or {},
        "enterprise_info": _enterprise_info_for_prompt(planner_input.get("enterprise_info")),
        "campaign_demand": demand,
        "existing_material": existing_material,
        "pipeline_warnings": warnings,
        "asset_mode": {
            "has_uploaded_assets": has_uploaded_assets,
            "named_asset_count": named_asset_count,
            "plot_rule": (
                "有素材：只消费已有素材资源描述，名称/类型/说明不漏条改名；入镜外形只抄该描述。已有素材不作场面约束；效果优先，须联想宏观大场面与精密拍摄，新场面标AI生成。"
                if has_uploaded_assets
                else "无上传素材：必须新构思完整可拍剧情（人物/情境/空间/动作），禁止空镜头或等素材再写；效果优先，宏观大场面与精密拍摄走AI生成；material_list 每条 source=后续补充或AI生成。"
            ),
        },
        "closed_sets": {
            "goal_types": list(GOAL_TYPES),
            "expect_durations": list(DURATION_OPTIONS),
            "rhythm": UNIFIED_RHYTHM,
            "presentation_forms": list(PRESENTATION_FORMS),
        },
        "user_locks": {
            "goal_type_required": True,
            "goal_type": (planner_input.get("campaign_demand") or {}).get("goal_type") or "",
            "expect_duration_required": True,
            "expect_duration": (planner_input.get("campaign_demand") or {}).get("expect_duration") or "",
            "rhythm": UNIFIED_RHYTHM,
            "product_optional": True,
        },
    }
    material_block = format_existing_material_prompt_block(existing_material)
    return (
        "请基于以下企业/品牌/产品（产品可无）、核心诉求、预期时长与介绍信息，作为独立 skill 输出策划案 JSON。\n"
        "必须先继承系统提示词与 project_info 中的项目信息：制作类型（实拍真人/二维/三维等，禁止用商业宣传片顶替）、语言、国家地域、剧本模式、画幅、时代、季节、光线与基调，禁止另起冲突设定。\n"
        "工作流：读项目信息 → 先锁 basic_intro 本次宣传要点（无则按 goal_type 从主体抽取）并总结卖点 → 分析主体特性 → 素材只读文首「已有素材资源描述」（本项目素材库已选项，禁止另读主体全库/台账/解析原文）→ 选定至少 3 部真实行业经典商业宣传片 → 按吸睛-共鸣-价值-收口写各阶段 content/sensory（禁止输出 shots，镜头不传下游）并充分展现已锁卖点（每段须写 technique_assoc：内容核+感官核+对标转译）→ 给出 project_visual_backfill 基调与风格 → 列出建议补充内容。\n"
        "campaign_demand.goal_type 是用户锁定的核心诉求，必须原样写入 video_positioning.goal_type 与 overall_scheme.main_goal_type，禁止改判。\n"
        "goal_type=企业品牌宣传（情绪种草）时，吸睛/共鸣/价值禁止口播式介绍企业/品牌/产品（我们是/本产品是）；花字可以点产品名、Logo、slogan。口播自我介绍放到收口。其他诉求不套本条。\n"
        "campaign_demand.expect_duration 是用户锁定的预期时长，必须原样写入 overall_scheme.target_duration 与 video_positioning.duration。\n"
        "四段 stage_plan 的 duration、口播字数、花字条数必须合计落入该时长档；禁止输出 shots 字段，禁止写建议镜头或分镜表。禁止把短片写成分钟级讲解，也禁止把长片压成一句口号。\n"
        "必须规划片内图形花字：project_visual_backfill.flower_text_spec 全片统一字体/字色/字重；吸睛/共鸣/价值/收口各段最多一条 flower_text，禁止底部落位以免与字幕重合。旁白优先：花字优先级低于旁白；copy 与 flower_text 可同段规划，但禁止同一拍同步上屏以免转移注意力；flower_text 须写 听=无，落地只挂无声的开镜/段末切镜/黑屏专镜/字卡专镜。花字与切镜融合：优先写 上屏=段末切镜|段首开镜，不与动作抢镜；也可 上屏=黑屏专镜或 上屏=字卡专镜（该拍无旁白，仍算该段唯一一条、场内一拍，不拆场）。店号/品牌/热线必须 上屏=字卡专镜｜字卡=场景底+字层｜手写=禁：企业场景底+字层先合成一张静帧，本镜 Static Hold 按原样上屏，禁止视频手写，禁止把字卡图与场景图当两张参考图分喂；字卡不是 CHAR/PROP/ENV。一般内容位置=中、字级=中、停留=短；收口位置=中、字级=大；CTA 停留=长。close.flower_text 必须是一句有韵味的记忆句，禁止用打开预约等 CTA 动词冒充，CTA 不是第二条花字。中部花字须字数简洁、文化味强、内涵深（宜≤15字），必须单独做艺术化组合设计并写艺术=手段A+手段B+…（并不限于印章、古体字、英文小字、颜色；还可组合书法、烫金、霓虹、水墨、光晕等），禁止说明书或口播整句上中屏。花字不是对白硬字幕。古风/文化/文旅可适当用繁体、古体字体、印章体；品牌注册名、店号（含「X家」）与数字/网址保持原形可扫读，须写 逐字=，禁漏家、禁复写邻字、禁何乐乐享。印章不压字：须写 印=句外旁侧｜压字=禁｜替字=禁，禁止印面盖住任一花字、禁止用印占字格。重点语句可配英文小字（英= + 英级=小），不得盖过中文。有产品名称时通常在画右或画左竖排（位置=画右|画左｜排向=竖），仍算该段唯一一条。\n"
        "必须先完整针对 campaign_demand.basic_intro 的本次宣传要点，写入 overall_scheme.promo_focus（要点=…｜来源=基本介绍|主体抽取）。基本介绍无要点时，按 goal_type 从企业/品牌/产品介绍抽取有用信息，禁止另起无关卖点。再总结 overall_scheme.selling_points（主=美食|美景|美物|美人|工艺|文化|高科技|历史沉淀｜次=…｜展现=哪段怎么拍）。四段必须充分展现每个已锁卖点。再锁 overall_scheme.visual_core 与主卖点同核（核=美食|美景|美人|科技|产品｜加码=充分特写|宏观特效|技术特效）。美食/美人/产品须充分特写，美景须宏观特效，科技须技术特效。有产品必须写特别描述（形制/材质/标识/高光）并给专拍特写，禁止只点品名。有 Logo/slogan 等企业元素必须给标识专拍特写，禁止远处小标一闪而过，禁止自造未提供的标识。主核在吸睛与价值专拍突出，禁止路过远景一带而过。\n"
        "配乐必须更响更重要：music_recommendation 写 音量=并重（收口可压过）与 权重=配乐主轴，禁止垫底几乎听不见。\n"
        "节奏只能是吸睛-共鸣-价值-收口，写入 narrative_plan.primary_model、content_mode.primary_mode、stage_plan 与 script_preview.beats。\n"
        "共鸣可适当融合救猫咪式节拍：看见一次小而可亲的主动作（扶/让/递/停下来帮），加强代入；不是第五段、不另起长剧、不拆场。15s以内只落一个微动作；更长可加主题点题或一瞬犹豫。禁止真救猫当主线（宠物题材除外）。empathy.technique_assoc 可用 内容核=救猫咪。\n"
        "对标片的情节、配色、拍摄与剪辑技巧均可借鉴并转译到本企业；do_not_copy 只写对方商标/Logo/吉祥物/注册口号等易混淆标识，禁止把桥段、配色、镜头技法列为禁项。\n"
        "企业/品牌/产品事实不编造；未提供的奖项/数据/证言留空并写入 supplement_suggestions。\n"
        "无上传素材时必须新构思可拍剧情，stage_plan.content/sensory / script_preview / material_list / comprehensive_assets 不得空；禁止输出 shots。画面标后续补充或由 AI 生成。有已有素材资源描述时只消费该段每一条，外形/材质/空间/说明不得漏条、改名、压成一句空形容。禁止把未写进已有素材资源描述的主体库素材当已有素材。已有素材绝不当场面约束；效果第一，发挥AI视频优势，无传统预算与拍摄风险限制，须充分联想宏观大场面与精密拍摄。\n"
        f"{material_block}\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def image_row_is_success(row: Any) -> bool:
    data = _as_dict(row)
    status = _text(data.get("analysis_status")).lower()
    if status == ANALYSIS_STATUS_SUCCESS:
        return True
    if status in {ANALYSIS_STATUS_FAILED, ANALYSIS_STATUS_PENDING, "analyzing"}:
        return False
    desc = _text(data.get("content_desc"))
    brief = _text(data.get("rebuild_brief"))
    if desc in {FAILED_CONTENT_DESC} or desc.startswith("识别失败"):
        return False
    return bool(brief or (desc and desc not in {"无", "未见"}))


def _analysis_row_for(analysis: Any, asset: Any) -> Dict[str, Any]:
    image_id = _text(_as_dict(asset).get("image_id"))
    for row in _as_dict(analysis).get("image_list") or []:
        item = _as_dict(row)
        if image_id and _text(item.get("image_id")) == image_id:
            return item
    return {}


def assets_needing_analysis(
    assets: Any,
    analysis: Any = None,
    *,
    force_all: bool = False,
    force_ids: Any = None,
) -> List[Dict[str, Any]]:
    force_set = {_text(item) for item in (force_ids or []) if _text(item)}
    rows = [item for item in assets if isinstance(item, dict)] if isinstance(assets, list) else []
    pending: List[Dict[str, Any]] = []
    for asset in rows:
        image_id = _text(asset.get("image_id"))
        if force_all or (image_id and image_id in force_set):
            pending.append(asset)
            continue
        if image_row_is_success(_analysis_row_for(analysis, asset)):
            continue
        pending.append(asset)
    return pending


def apply_analysis_status_to_assets(assets: Any, analysis: Any) -> List[Dict[str, Any]]:
    rows = [dict(item) for item in assets if isinstance(item, dict)] if isinstance(assets, list) else []
    for asset in rows:
        row = _analysis_row_for(analysis, asset)
        if image_row_is_success(row):
            asset["analysis_status"] = ANALYSIS_STATUS_SUCCESS
            asset["analysis_error"] = ""
        elif _text(row.get("analysis_status")) == ANALYSIS_STATUS_FAILED or _text(row.get("analysis_error")):
            asset["analysis_status"] = ANALYSIS_STATUS_FAILED
            asset["analysis_error"] = _text(row.get("analysis_error")) or _text(row.get("content_desc")) or "识别失败"
        elif not _text(asset.get("analysis_status")):
            asset["analysis_status"] = ANALYSIS_STATUS_PENDING
    return rows


def merge_single_asset_analysis(
    base: Any,
    asset: Any,
    parsed: Any = None,
    *,
    error: str = "",
) -> Dict[str, Any]:
    analysis = _deep_merge(empty_image_asset_analysis(), _as_dict(base))
    asset = _as_dict(asset)
    image_id = _text(asset.get("image_id"))
    incoming = _as_dict(parsed)
    kept_rows = [
        dict(row)
        for row in (analysis.get("image_list") or [])
        if isinstance(row, dict) and _text(row.get("image_id")) != image_id
    ]
    kept_subjects: List[Dict[str, Any]] = []
    for raw in analysis.get("rebuild_subjects") or []:
        item = _as_dict(raw)
        ids = [_text(value) for value in (item.get("source_image_ids") or []) if _text(value)]
        if image_id and ids:
            leftover = [value for value in ids if value != image_id]
            if not leftover:
                continue
            item["source_image_ids"] = leftover
        kept_subjects.append(item)

    incoming_list = incoming.get("image_list") if isinstance(incoming.get("image_list"), list) else []
    incoming_row = {}
    for raw in incoming_list:
        row = _as_dict(raw)
        if image_id and _text(row.get("image_id")) == image_id:
            incoming_row = row
            break
        if not incoming_row:
            incoming_row = row
    if not incoming_row and any(_text(incoming.get(key)) for key in ("content_desc", "rebuild_brief")):
        incoming_row = incoming

    row = dict(incoming_row)
    row["image_id"] = image_id or _text(row.get("image_id"))
    row["media_kind"] = normalize_media_kind(asset.get("media_kind") or row.get("media_kind"))
    row["image_type"] = asset.get("image_type") or row.get("image_type") or "product"
    row["object_name"] = asset.get("object_name") or row.get("object_name") or row.get("reference_name") or ""
    row["user_remark"] = asset.get("user_remark") or row.get("user_remark") or ""
    row["reference_name"] = row.get("reference_name") or row.get("object_name") or ""
    fail_text = _text(error)
    if fail_text:
        row["analysis_status"] = ANALYSIS_STATUS_FAILED
        row["analysis_error"] = fail_text
        if not _text(row.get("content_desc")):
            row["content_desc"] = FAILED_CONTENT_DESC
        row["available_asset_hint"] = row.get("available_asset_hint") or "识别失败，仅作弱参考"
    elif image_row_is_success({**row, "analysis_status": ANALYSIS_STATUS_SUCCESS}):
        row["analysis_status"] = ANALYSIS_STATUS_SUCCESS
        row["analysis_error"] = ""
    else:
        row["analysis_status"] = ANALYSIS_STATUS_FAILED
        row["analysis_error"] = _text(row.get("analysis_error")) or "识别不完整"
        if not _text(row.get("content_desc")):
            row["content_desc"] = FAILED_CONTENT_DESC
        row["available_asset_hint"] = row.get("available_asset_hint") or "识别失败，仅作弱参考"
    kept_rows.append(row)

    if row.get("analysis_status") == ANALYSIS_STATUS_SUCCESS:
        for raw in incoming.get("rebuild_subjects") if isinstance(incoming.get("rebuild_subjects"), list) else []:
            item = _as_dict(raw)
            ids = [_text(value) or image_id for value in (item.get("source_image_ids") or [])]
            item["source_image_ids"] = [value for value in ids if value] or ([image_id] if image_id else [])
            kept_subjects.append(item)
        summary = _text(incoming.get("global_visual_summary"))
        previous = _text(analysis.get("global_visual_summary"))
        if summary and summary not in previous:
            analysis["global_visual_summary"] = f"{previous}；{summary}".strip("；") if previous else summary

    analysis["image_list"] = kept_rows
    analysis["rebuild_subjects"] = kept_subjects
    return _ensure_rebuild_subjects(analysis)


async def _resolve_promo_asset_vision(asset: Dict[str, Any], db: Session) -> Tuple[List[Tuple[Dict[str, Any], str]], str]:
    kind = normalize_media_kind(asset.get("media_kind"))
    label = _text(asset.get("object_name") or asset.get("image_id")) or "素材"
    if kind == "video":
        try:
            source = _resolve_media_source(asset.get("img_url") or "", db)
            frames = await asyncio.to_thread(_extract_video_preview_frames, source, MAX_FRAMES_PER_VIDEO) if source else []
        except Exception as exc:
            logger.warning("promo video frame extract failed: %s", exc)
            frames = []
        if not frames:
            return [], f"视频 {label} 无法抽取关键帧"
        total = len(frames)
        resolved = []
        for idx, frame_url in enumerate(frames, 1):
            meta = dict(asset)
            meta["media_kind"] = "video_frame"
            meta["frame_label"] = f"{idx}/{total}"
            resolved.append((meta, frame_url))
        return resolved, ""
    try:
        url = await resolve_image_url_for_llm(asset.get("img_url") or "", db)
    except Exception as exc:
        logger.warning("promo image resolve failed: %s", exc)
        url = ""
    if not url:
        return [], f"图片 {label} 无法读取"
    meta = dict(asset)
    meta["media_kind"] = "image"
    meta["frame_label"] = "单张"
    return [(meta, url)], ""


async def analyze_one_promo_asset(
    db: Session,
    *,
    current_user: Any,
    llm_config: Dict[str, Any],
    asset: Dict[str, Any],
    billing_lock: Any = None,
    release_db: bool = False,
) -> Tuple[Dict[str, Any], List[str]]:
    warnings: List[str] = []
    vision, resolve_error = await _resolve_promo_asset_vision(asset, db)
    if resolve_error:
        warnings.append(resolve_error)
        return merge_single_asset_analysis({}, asset, {}, error=resolve_error), warnings
    try:
        parsed, _resp = await _run_json_llm(
            db,
            current_user=current_user,
            llm_config=llm_config,
            system_prompt=_resolve_prompt_text("promo_planner_image_analysis.md"),
            user_prompt=_build_image_analysis_user_prompt([item[0] for item in vision], assets=[asset]),
            image_urls=[item[1] for item in vision],
            billing_item="promo_planner_image_analysis",
            release_db=release_db,
            billing_lock=billing_lock,
        )
    except Exception as exc:
        logger.warning("promo single-asset analysis failed: %s", exc)
        message = str(exc)
        warnings.append(message)
        return merge_single_asset_analysis({}, asset, {}, error=message), warnings
    merged = merge_single_asset_analysis({}, asset, parsed)
    row = _analysis_row_for(merged, asset)
    if not image_row_is_success(row):
        warnings.append(f"{'视频' if normalize_media_kind(asset.get('media_kind')) == 'video' else '图片'} {_text(asset.get('object_name') or asset.get('image_id'))} 识别不完整")
    return merged, warnings


async def analyze_promo_images(
    db: Session,
    *,
    current_user: Any,
    llm_config: Dict[str, Any],
    assets: List[Dict[str, Any]],
    existing_analysis: Any = None,
    force_all: bool = False,
    force_ids: Any = None,
) -> Tuple[Dict[str, Any], List[str]]:
    warnings: List[str] = []
    analysis = _deep_merge(empty_image_asset_analysis(), _as_dict(existing_analysis))
    rows = [item for item in assets if isinstance(item, dict)] if isinstance(assets, list) else []
    if not rows:
        return analysis, warnings
    pending = assets_needing_analysis(rows, analysis, force_all=force_all, force_ids=force_ids)
    if not pending:
        return _ensure_rebuild_subjects(analysis), warnings

    lock = asyncio.Lock()
    sem = asyncio.Semaphore(MAX_PARALLEL_ASSET_ANALYSIS)

    async def _run(asset: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
        async with sem:
            piece, item_warnings = await analyze_one_promo_asset(
                db,
                current_user=current_user,
                llm_config=llm_config,
                asset=asset,
                billing_lock=lock,
                release_db=False,
            )
            return asset, piece, item_warnings

    gathered = await asyncio.gather(*[_run(asset) for asset in pending], return_exceptions=True)
    for item in gathered:
        if isinstance(item, Exception):
            logger.warning("promo parallel analysis task failed: %s", item)
            warnings.append(str(item))
            continue
        asset, piece, item_warnings = item
        warnings.extend(item_warnings)
        row = _analysis_row_for(piece, asset)
        analysis = merge_single_asset_analysis(
            analysis,
            asset,
            piece,
            error=_text(row.get("analysis_error")) if not image_row_is_success(row) else "",
        )

    for asset in rows:
        if _analysis_row_for(analysis, asset):
            continue
        analysis = merge_single_asset_analysis(analysis, asset, {}, error="")
        row = _analysis_row_for(analysis, asset)
        row["analysis_status"] = ANALYSIS_STATUS_PENDING
        row["analysis_error"] = ""
    existing_warnings = analysis.get("analysis_warnings") if isinstance(analysis.get("analysis_warnings"), list) else []
    analysis["analysis_warnings"] = [*existing_warnings, *warnings]
    return _ensure_rebuild_subjects(analysis), warnings


async def analyze_and_persist_promo_asset(
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
    project_info = resolve_promo_project_global_info(project)
    user_snap = _snapshot_user_principal(current_user)
    asset = dump_model(getattr(req, "asset", None) or req)
    if not _text(asset.get("img_url")):
        raise HTTPException(status_code=400, detail="素材没有可解析的图片或视频地址")
    llm_config = _resolve_story_generator_script_analysis_llm_config(
        db,
        int(user_snap.id),
        function_name=(getattr(req, "function_name", None) or "script_analysis"),
        system_api_id=getattr(req, "system_api_id", None),
        context="analyze_promo_asset",
        project_global_info=project_info or extra_info,
    )
    if not llm_config or not (llm_config.get("api_key") or "").strip():
        raise HTTPException(status_code=400, detail="No valid LLM API key configured in active settings")
    state = load_planner_state(db, project)
    existing = _as_dict(getattr(req, "image_asset_analysis", None)) or _as_dict(
        (state.get("promo_planner_result") or {}).get("image_asset_analysis")
    )
    piece, warnings = await analyze_one_promo_asset(
        db,
        current_user=user_snap,
        llm_config=llm_config,
        asset=asset,
        release_db=True,
    )
    persist_lock = await _project_asset_persist_lock(int(project_id))
    async with persist_lock:
        project = rebind_promo_project(db, project_id=project_id)
        if getattr(req, "enterprise_id", None) or getattr(req, "brand_id", None) or getattr(req, "product_id", None):
            bind_promo_catalog(
                db,
                project,
                current_user,
                enterprise_id=getattr(req, "enterprise_id", None) or project.enterprise_id,
                brand_id=getattr(req, "brand_id", None) or project.brand_id,
                product_id=getattr(req, "product_id", None) or project.product_id,
            )
        state = load_planner_state(db, project)
        existing_db = _as_dict((state.get("promo_planner_result") or {}).get("image_asset_analysis"))
        existing = existing_db if (existing_db.get("image_list") or existing_db.get("rebuild_subjects")) else existing
        row = _analysis_row_for(piece, asset)
        merged = merge_single_asset_analysis(
            existing,
            asset,
            piece,
            error=_text(row.get("analysis_error")) if not image_row_is_success(row) else "",
        )
        result = merge_planner_result(state.get("promo_planner_result") or {})
        result["image_asset_analysis"] = merged
        planner_input = _as_dict(state.get("promo_planner_input"))
        enterprise_info = _as_dict(planner_input.get("enterprise_info"))
        campaign = _as_dict(planner_input.get("campaign_demand"))
        assets = apply_analysis_status_to_assets(enterprise_info.get("image_assets") or [], merged)
        found = False
        for item in assets:
            if _text(item.get("image_id")) == _text(asset.get("image_id")):
                item.update(
                    {
                        "img_url": _text(asset.get("img_url")) or item.get("img_url"),
                        "image_type": asset.get("image_type") or item.get("image_type"),
                        "media_kind": asset.get("media_kind") or item.get("media_kind"),
                        "object_name": asset.get("object_name") or item.get("object_name"),
                        "user_remark": asset.get("user_remark") if asset.get("user_remark") is not None else item.get("user_remark"),
                        "analysis_status": row.get("analysis_status") or ANALYSIS_STATUS_FAILED,
                        "analysis_error": row.get("analysis_error") or "",
                    }
                )
                found = True
                break
        if not found:
            assets.append(
                {
                    **{key: asset.get(key) for key in ("image_id", "img_url", "image_type", "media_kind", "object_name", "user_remark", "owner_kind", "owner_entity_id", "catalog_asset_id")},
                    "analysis_status": row.get("analysis_status") or ANALYSIS_STATUS_FAILED,
                    "analysis_error": row.get("analysis_error") or "",
                }
            )
        assets = selected_planner_image_assets({"image_assets": assets})
        merged = filter_analysis_to_selected_assets(merged, assets)
        result["image_asset_analysis"] = merged
        enterprise_info["image_assets"] = assets
        campaign["existing_material"] = backfill_existing_material(
            campaign.get("existing_material"),
            merged,
            assets,
        )
        planner_input["enterprise_info"] = enterprise_info
        planner_input["campaign_demand"] = campaign
        persist_planner_state(db, project, planner_input=planner_input, planner_result=result)
        db.commit()
        db.refresh(project)
    return {
        "image_id": _text(asset.get("image_id")),
        "analysis_status": row.get("analysis_status") or ANALYSIS_STATUS_FAILED,
        "analysis_error": row.get("analysis_error") or "",
        "image_row": row,
        "rebuild_subjects": [
            item
            for item in (merged.get("rebuild_subjects") or [])
            if _text(asset.get("image_id")) in [_text(value) for value in (_as_dict(item).get("source_image_ids") or [])]
        ],
        "image_asset_analysis": merged,
        "warnings": warnings,
        "project": serialize_promo_project(db, project, user_snap),
    }


async def analyze_and_persist_catalog_asset(
    db: Session,
    *,
    row: PromoCatalogAsset,
    current_user: Any,
    req: Any = None,
) -> Dict[str, Any]:
    asset = catalog_asset_as_planner_asset(row)
    if not _text(asset.get("img_url")):
        raise HTTPException(status_code=400, detail="素材没有可解析的图片或视频地址")
    user_snap = _snapshot_user_principal(current_user)
    llm_config = _resolve_story_generator_script_analysis_llm_config(
        db,
        int(user_snap.id),
        function_name=(getattr(req, "function_name", None) or "script_analysis"),
        system_api_id=getattr(req, "system_api_id", None),
        context="analyze_promo_catalog_asset",
        project_global_info={},
    )
    if not llm_config or not (llm_config.get("api_key") or "").strip():
        raise HTTPException(status_code=400, detail="No valid LLM API key configured in active settings")
    piece, warnings = await analyze_one_promo_asset(
        db,
        current_user=user_snap,
        llm_config=llm_config,
        asset=asset,
        release_db=True,
    )
    row = (
        db.query(PromoCatalogAsset)
        .filter(PromoCatalogAsset.id == int(row.id), PromoCatalogAsset.is_deleted.is_(False))
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Asset not found")
    analysis_row = _analysis_row_for(piece, asset)
    write_catalog_analysis(
        row,
        piece,
        status=analysis_row.get("analysis_status") or ANALYSIS_STATUS_FAILED,
        error=_text(analysis_row.get("analysis_error")),
        overwrite=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    serialized = serialize_promo_catalog_asset(row)
    return {
        **serialized,
        "analysis_status": serialized.get("analysis_status") or ANALYSIS_STATUS_FAILED,
        "analysis_error": serialized.get("analysis_error") or "",
        "image_row": analysis_row,
        "rebuild_subjects": [
            item
            for item in (piece.get("rebuild_subjects") or [])
            if _text(asset.get("image_id")) in [_text(value) for value in (_as_dict(item).get("source_image_ids") or [])]
        ],
        "image_asset_analysis": piece,
        "warnings": warnings,
    }


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
    project_info = resolve_promo_project_global_info(project)
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
    planner_input = normalize_planner_input(
        snapshot_from_catalog(
            enterprise,
            product,
            brand=brand,
            image_assets=selected_planner_image_assets(overlay),
            overlay=overlay,
        ),
        getattr(req, "campaign_demand", None),
    )
    demand = planner_input.get("campaign_demand") or {}
    enterprise_info = planner_input.get("enterprise_info") or {}
    goal_type = normalize_goal_type(demand.get("goal_type"))
    if not goal_type or goal_type not in GOAL_TYPES:
        raise HTTPException(status_code=400, detail="核心诉求为必填，须五选一")
    if not _text(enterprise_info.get("enterprise_name")) and not getattr(req, "enterprise_id", None):
        raise HTTPException(status_code=400, detail="请先选定企业")
    expect_duration = normalize_expect_duration(demand.get("expect_duration"))
    if not expect_duration:
        raise HTTPException(status_code=400, detail="预期时长为必填")
    demand["goal_type"] = goal_type
    demand["expect_duration"] = expect_duration
    demand["existing_material"] = existing_material_user_notes(demand.get("existing_material"))
    planner_input["campaign_demand"] = demand
    persist_planner_state(db, project_id=project_id, planner_input=planner_input)
    db.commit()

    llm_config = _resolve_story_generator_script_analysis_llm_config(
        db,
        int(user_snap.id),
        function_name=(getattr(req, "function_name", None) or "script_analysis"),
        system_api_id=getattr(req, "system_api_id", None),
        context="generate_promo_planner",
        project_global_info=project_info or extra_info,
    )
    if not llm_config or not (llm_config.get("api_key") or "").strip():
        raise HTTPException(status_code=400, detail="No valid LLM API key configured in active settings")

    assets = selected_planner_image_assets(planner_input.get("enterprise_info"))
    planner_input["enterprise_info"]["image_assets"] = assets
    existing_analysis = filter_analysis_to_selected_assets(
        getattr(req, "image_asset_analysis", None)
        or (load_planner_state(db, project).get("promo_planner_result") or {}).get("image_asset_analysis"),
        assets,
    )
    image_analysis, warnings = await analyze_promo_images(
        db,
        current_user=user_snap,
        llm_config=llm_config,
        assets=assets,
        existing_analysis=existing_analysis,
        force_all=bool(getattr(req, "force_reanalyze", False)),
    )
    image_analysis = filter_analysis_to_selected_assets(image_analysis, assets)
    assets = apply_analysis_status_to_assets(assets, image_analysis)
    planner_input["enterprise_info"]["image_assets"] = assets
    demand["existing_material"] = backfill_existing_material(
        demand.get("existing_material"),
        image_analysis,
        assets,
    )
    planner_input["campaign_demand"] = demand

    system_prompt = _promo_skill_system_prompt("promo_planner_scheme.md", project_info)
    parsed, _resp = await _run_json_llm(
        db,
        current_user=user_snap,
        llm_config=llm_config,
        system_prompt=system_prompt,
        user_prompt=_build_scheme_user_prompt(
            planner_input,
            image_analysis,
            warnings,
            project_info=project_info,
        ),
        billing_item="promo_planner_scheme",
    )
    result = merge_planner_result(parsed)
    locked = apply_user_dimension_locks(result, planner_input.get("campaign_demand") or {})
    locked["existing_material"] = backfill_existing_material(
        locked.get("existing_material") or demand.get("existing_material"),
        image_analysis,
        assets,
    )
    planner_input["campaign_demand"] = dict(locked)
    visual = _as_dict(result.get("project_visual_backfill"))
    films = result.get("benchmark_films") if isinstance(result.get("benchmark_films"), list) else []
    if not (isinstance(visual.get("borrowed_films"), list) and visual.get("borrowed_films")):
        visual["borrowed_films"] = [
            _text(_as_dict(item).get("title"))
            for item in films
            if _text(_as_dict(item).get("title"))
        ]
        result["project_visual_backfill"] = visual
    result["image_asset_analysis"] = image_analysis
    result["uploaded_asset_catalog"] = build_uploaded_asset_catalog(assets, image_analysis)
    result["existing_material"] = _text((planner_input.get("campaign_demand") or {}).get("existing_material"))
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
    try:
        if _positive_int(_promo_extra_info(project).get("linked_story_project_id")):
            ensure_promo_linked_story_project(
                db,
                project,
                current_user=user_snap,
                planner_input=planner_input,
                planner_result=result,
            )
            db.commit()
            project = rebind_promo_project(db, project_id=project_id)
    except Exception as exc:
        logger.warning("promo planner failed to refresh linked story material: %s", exc)
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


def normalize_promo_project_global_info(
    raw: Any,
    *,
    title: str = "",
    description: str = "",
) -> Dict[str, Any]:
    extra = _as_dict(raw)
    nested = extra.get("global_info")
    if isinstance(nested, dict) and nested:
        data = dict(nested)
    else:
        data = {key: value for key, value in extra.items() if key not in _PROMO_EXTRA_META_KEYS}
    if _text(data.get("type")) == PROMO_PROJECT_TYPE:
        data["type"] = ""
    data["kind"] = "promo"
    data["promo_single_scene"] = True
    data["script_title"] = _text(data.get("script_title")) or _text(title)
    notes = _text(data.get("notes")) or _text(description)
    if notes:
        data["notes"] = notes
    return _ensure_project_generation_defaults(data)


def resolve_promo_project_global_info(project: Any) -> Dict[str, Any]:
    if isinstance(project, dict):
        extra = _as_dict(project.get("extra_info") or project)
        title = _text(project.get("title") or project.get("script_title"))
        description = _text(project.get("description") or project.get("notes"))
    else:
        extra = _promo_extra_info(project)
        title = _text(getattr(project, "title", None))
        description = _text(getattr(project, "description", None))
    return normalize_promo_project_global_info(extra, title=title, description=description)


def attach_promo_project_global_info(extra: Any, global_info: Any) -> Dict[str, Any]:
    out = dict(extra) if isinstance(extra, dict) else {}
    out["global_info"] = dict(global_info or {})
    return out


_PROMO_LOCKED_GI_KEYS = (
    "type",
    "country_region",
    "language",
    "base_positioning",
    "style_mode",
    "Global_Style",
    "lighting",
    "tone",
    "era",
    "season_occurrence",
    "aspect_ratio",
    "aspectRatio",
    "tech_params",
    "creativity",
    "lens_preference",
    "broadcast_safety_level",
    "expected_duration",
    "max_shot_seconds",
    "notes",
)


def persist_promo_project_extra_info(
    extra: Any,
    *,
    title: str = "",
    description: str = "",
    current: Optional[Dict[str, Any]] = None,
    require_aspect_ratio: bool = False,
    require_type: bool = False,
) -> Dict[str, Any]:
    current = dict(current) if isinstance(current, dict) else {}
    overlay = dict(extra) if isinstance(extra, dict) else {}
    overlay_gi = overlay.pop("global_info", None)
    incoming = dict(current)
    incoming.update(overlay)
    if isinstance(overlay_gi, dict) and overlay_gi:
        incoming["global_info"] = overlay_gi
    elif not _as_dict(incoming.get("global_info")) and _as_dict(current.get("global_info")):
        incoming["global_info"] = current.get("global_info")
    for key in ("linked_story_project_id", "linked_story_episode_id"):
        if incoming.get(key) is None and current.get(key) is not None:
            incoming[key] = current[key]
    gi = normalize_promo_project_global_info(incoming, title=title, description=description)
    if require_type and not _promo_production_type(gi):
        raise HTTPException(status_code=400, detail="类型为必填，请选择实拍真人、二维或三维等")
    if require_aspect_ratio and not _promo_aspect_ratio(gi):
        raise HTTPException(status_code=400, detail="画幅比例为必填")
    return attach_promo_project_global_info(incoming, gi)


def _promo_production_type(global_info: Any) -> str:
    text = _text(_as_dict(global_info).get("type"))
    return "" if text == PROMO_PROJECT_TYPE else text


def _promo_aspect_ratio(global_info: Any) -> str:
    data = _as_dict(global_info)
    visual = _as_dict(_as_dict(data.get("tech_params")).get("visual_standard"))
    return _text(data.get("aspect_ratio") or data.get("aspectRatio") or visual.get("aspect_ratio"))


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
    visual = _as_dict((planner_result or {}).get("project_visual_backfill"))
    style_mode = _text(visual.get("style_mode"))
    if style_mode:
        return style_mode
    blob = " ".join(
        [
            _text(visual.get("Global_Style")),
            _text(visual.get("tone")),
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
    stored = resolve_promo_project_global_info(project)
    current = dict(stored)
    current.update(existing or {})
    for key in _PROMO_LOCKED_GI_KEYS:
        value = stored.get(key)
        if value not in (None, "", {}, []):
            current[key] = value
    current["kind"] = "promo"
    current["promo_single_scene"] = True
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
    brief = collect_promo_brief(
        {
            **current,
            "source_promo_project_id": int(project.id),
        },
        planner_input,
        planner_result,
    )
    current = apply_promo_fields_to_global_info(current, brief)
    current["base_positioning"] = _text(current.get("base_positioning")) or style
    current["style_mode"] = _text(current.get("style_mode")) or style
    analysis = filter_analysis_to_selected_assets(
        (planner_result or {}).get("image_asset_analysis") or brief.get("image_asset_analysis"),
        _planner_image_assets(planner_input or {}),
    )
    if analysis:
        current["image_asset_analysis"] = analysis
    current["promo_existing_material"] = _text(brief.get("promo_existing_material"))
    sources = brief.get("promo_source_images") if isinstance(brief.get("promo_source_images"), list) else []
    if sources:
        current["promo_source_images"] = sources
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
        flag_modified(story, "global_info")
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
    project_info: Optional[Dict[str, Any]] = None,
) -> str:
    named_asset_count = _count_named_assets(planner_input)
    has_uploaded_assets = named_asset_count > 0
    assets = _planner_image_assets(planner_input)
    image_analysis = filter_analysis_to_selected_assets(
        planner_result.get("image_asset_analysis") or empty_image_asset_analysis(),
        assets,
    )
    existing_material = existing_material_for_prompt(
        planner_result.get("existing_material")
        or _as_dict(planner_input.get("campaign_demand")).get("existing_material"),
        image_analysis,
        assets,
    )
    demand = dict(_as_dict(planner_input.get("campaign_demand")))
    demand["existing_material"] = existing_material
    payload = {
        "project_title": title,
        "project_info": project_info or {},
        "enterprise_info": _enterprise_info_for_prompt(planner_input.get("enterprise_info")),
        "campaign_demand": demand,
        "existing_material": existing_material,
        "asset_mode": {
            "has_uploaded_assets": has_uploaded_assets,
            "named_asset_count": named_asset_count,
            "plot_rule": (
                "有素材：只消费已有素材资源描述，名称/类型/说明不漏条；入镜外形只抄该描述。已有素材不作场面约束，效果优先，可写宏观大场面与精密拍摄。"
                if has_uploaded_assets
                else "无上传素材：按策划案新构思写成完整可拍节拍，禁止提纲或待补素材；效果优先，宏观大场面与精密拍摄走AI生成。"
            ),
        },
        "overall_scheme": planner_result.get("overall_scheme") or {},
        "characteristic_analysis": planner_result.get("characteristic_analysis") or {},
        "benchmark_films": planner_result.get("benchmark_films") or [],
        "stage_plan": drop_stage_plan_shots(planner_result.get("stage_plan") or {}),
        "project_visual_backfill": planner_result.get("project_visual_backfill") or {},
        "content_mode": planner_result.get("content_mode") or {},
        "video_positioning": planner_result.get("video_positioning") or {},
        "narrative_plan": planner_result.get("narrative_plan") or {},
        "presentation_plan": planner_result.get("presentation_plan") or {},
        "visual_spec": planner_result.get("visual_spec") or {},
        "material_list": planner_result.get("material_list") or [],
        "script_preview": planner_result.get("script_preview") or {},
        "structured_business_info": planner_result.get("structured_business_info") or {},
    }
    material_block = format_existing_material_prompt_block(existing_material)
    return (
        "请把下面已锁定的策划案与成片脚本方向预览，写成一支可进入剧本页的正式成片剧本。\n"
        "必须先继承系统提示词与 project_info 中的项目信息：制作类型（实拍真人/二维/三维等，禁止用商业宣传片顶替）、语言、国家地域、剧本模式、画幅、时代、季节、光线与基调，禁止另起冲突设定。\n"
        "必须严格承接 吸睛-共鸣-价值-收口：stage_plan 与 script_preview.beats 同核同序，不得另起故事。\n"
        "共鸣可适当融合救猫咪：把可亲主动作写成可见 动作:（手/物/结果），加强代入，禁止只靠口播说我们懂你。不是第五段、不拆场。\n"
        "节拍必须分行：动作: 【可见主体】原位= -> 动作= -> 落位=｜结果= ；口播: 「短句」｜声型=旁白|口播|对白｜身份=｜语气= ；花字单独一行。禁止【旁白】后接风景散文再夹口播。山/雾/鸡/鱼等不同主体须拆拍。无声写 口播: 无。\n"
        "镜头由本技能实现：按四段 content/sensory 拆成可拍节拍。策划不传镜头表，禁止读取或照抄 stage_plan.shots。\n"
        "四段 content 必须逐字核销：写出 ## 策划核销，每段原文=「stage_plan.*.content 整段原文」｜节拍=…｜可见落点=…｜漏项=无。禁止改写成近义或漏信息点。策划的内容必须全部可视化呈现。\n"
        "在策划内容完整落地的前提下，必须认真分析 benchmark_films 全部条目（title/why_picked/techniques/content_borrow）以及 borrowed_films_note / borrowed_films_scene_refs，写出 ## 对标综合：每部片如何转成<本案例>现场、服务哪些 Beat；四段各拍须综合多部对标实现，禁止只点一部、禁止漏片、禁止只抄片名。对标服务于核销，不得另起故事或冲掉策划信息。\n"
        "上游 goal_type=企业品牌宣传（情绪种草）时，前三段禁止口播式介绍企业/品牌/产品；花字可以点产品名、Logo、slogan。口播自我介绍放到收口。\n"
        "全剧恰好一场，四段都写进同一场节拍流，禁止按时长或空间拆成多场。\n"
        "企业/产品事实不编造。无上传素材时仍须写出完整可拍人物、空间与动作，禁止因无 object_name 而省略画面。已有素材不作场面约束；效果第一，发挥AI视频优势，须落地宏观大场面与精密拍摄。\n"
        "素材只消费文首「已有素材资源描述」：名称/类型/说明/外形不得漏条改名；说明写入对应角色/道具介绍。禁止另读主体全库、台账或解析原文。\n"
        "有已有素材资源描述时，写出「## 视觉还原（上传素材，供资产重生）」只准逐行抄该描述，禁止另补未写入的素材。\n"
        "基调与风格服从 project_visual_backfill。必须写出 ## 花字规范（抄 flower_text_spec，含字形/强调体/英配/中屏艺术化组合/产品名画右或画左竖排/禁底部避字幕/切镜融合/旁白优先/逐字锁/印章不压字/字卡专镜）。吸睛/共鸣/价值/收口各段最多一条花字。旁白优先：花字优先级低于旁白；本拍 口播: 非「无」→ 必须 花字: 无，禁止同一拍同步出花字以免转移注意力。花字只挂 口播: 无 的段首开镜、段末切镜、黑屏专镜或字卡专镜，并写 听=无。花字与切镜融合：优先挂在该段段首开镜或段末切镜，不与动作抢镜；也可单独一拍黑屏专镜或字卡专镜（该拍无旁白），仍在同一场。店号/品牌/热线必须 上屏=字卡专镜｜字卡=场景底+字层｜手写=禁，企业场景底+字层先合成一张静帧，本镜 Static Hold 按原样上屏，禁止视频手写，禁止双参考图分喂。其他拍写 花字: 无。一个动作最多一条花字。禁止位置=底/底部居中，以免与字幕重合；只写 位置=中|画右|画左。一般内容位置=中、字级=中、停留=短；收口位置=中、字级=大；CTA 停留=长。CTA 写 CTA= 不是第二条花字。最后一拍必须有一句有韵味的收口花字，禁止用 CTA 动词代替。中部花字须字少味厚、文化味强、内涵深，宜≤15字，必须写 艺术=手段A+手段B+…（并不限于印章、古体字、英文小字、颜色），禁止说明书或口播整句上中屏。古风/文化/文旅花字可繁体、古体或印章体。品牌名、店号（含「X家」）可扫读，须写 逐字=，禁漏家、禁复写邻字、禁何乐乐享。印章不压字：须写 印=句外旁侧｜压字=禁｜替字=禁，禁止印面盖住花字。重点句可加 英=「短译」｜英级=小。有产品名时该条可 位置=画右|画左｜排向=竖，仍算该段唯一一条。必须抄 overall_scheme.promo_focus 与 selling_points 写入 ## 核心重点，节拍充分展现每个已锁卖点（美食/美景/美物/美人/工艺/文化/高科技/历史沉淀），禁止另起无关故事。必须抄 overall_scheme.visual_core 为画面核（与主卖点同核），并把主核加码写满：美食/美人/产品充分特写，美景观宏观特效，科技见技术特效。有产品必须特别描述形制材质标识并给专拍特写。有 Logo/slogan 等企业元素必须给标识特写，禁止远处小标一闪而过。配乐须并重够响（收口可压过），禁止垫底。必须按上游 stage_plan 的 content/sensory/copy/flower_text 拆镜并逐字核销；在此前提下认真分析全部对标内容，结合本案例综合实现各 Beat，写出 ## 对标综合与每拍 对标综合=（多部片名+手法→本案可见结果）。\n"
        "场景可在视觉还原之上加美化光与贴边点缀装饰，不改空间身份、不占舞台净空。禁止照搬对方商标/Logo/吉祥物/注册口号。\n"
        "按时长控制篇幅，不拆场。只输出带 OUTPUT 标记的 Markdown 剧本。\n"
        f"{material_block}\n"
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
    project_info = resolve_promo_project_global_info(project)
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
    stages = _as_dict(planner_result.get("stage_plan"))
    has_stages = any(_stage_has_content(stages.get(key)) for key in STAGE_KEYS)
    if not _text(preview.get("logline")) and not beats and not has_stages:
        raise HTTPException(status_code=400, detail="请先生成并保存策划案与成片脚本方向预览")

    existing_meta = load_promo_script_meta(db, rebind_promo_project(db, project_id=project_id))
    if existing_meta.get("has_script") and not overwrite:
        raise HTTPException(status_code=409, detail="剧本页已有成片脚本，如需覆盖请确认后重试")

    llm_config = _resolve_story_generator_script_analysis_llm_config(
        db,
        int(user_snap.id),
        function_name=(getattr(req, "function_name", None) or "script_analysis"),
        system_api_id=getattr(req, "system_api_id", None),
        context="generate_promo_script",
        project_global_info=project_info or extra_info,
    )
    if not llm_config or not (llm_config.get("api_key") or "").strip():
        raise HTTPException(status_code=400, detail="No valid LLM API key configured in active settings")

    project = rebind_promo_project(db, project_id=project_id)
    project_info = resolve_promo_project_global_info(project)
    system_prompt = _promo_skill_system_prompt("promo_planner_script.md", project_info)
    user_prompt = _build_script_user_prompt(
        title=_text(project.title),
        planner_input=planner_input,
        planner_result=planner_result,
        project_info=project_info,
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
