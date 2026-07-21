# -*- coding: utf-8 -*-
"""Shot-submit debug + promo/script-mode prompt helpers."""
from __future__ import annotations

import logging
import os
import re
import urllib.parse
from typing import Any, Dict, List, Optional

from app.services.llm_service import llm_service

logger = logging.getLogger("api_logger")

def _is_shot_submit_debug_enabled() -> bool:
    return str(os.getenv("SHOT_SUBMIT_DEBUG", "0")).strip().lower() in {"1", "true", "yes", "on"}


def _normalize_ref_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw = value.strip()
        return [raw] if raw else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item or "").strip()]
    return []


def _extract_ref_display_name(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = urllib.parse.urlparse(raw)
        path = urllib.parse.unquote(parsed.path or "")
        base_name = os.path.basename(path.rstrip("/"))
        if base_name:
            return base_name
        if parsed.netloc:
            return parsed.netloc
    except Exception:
        pass
    return raw


def _build_ref_display_names(value: Any, limit: int = 20) -> List[str]:
    refs = _normalize_ref_list(value)
    names: List[str] = []
    seen: set = set()
    for ref in refs:
        name = _extract_ref_display_name(ref)
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
        if len(names) >= limit:
            break
    return names


_PROMO_TYPE_HINTS = (
    "宣传",
    "推广",
    "营销",
    "品牌",
    "campaign",
    "promotion",
    "promotional",
    "advert",
    "advertising",
    "brand",
    "corporate",
    "product",
    "tourism",
    "cta",
    "conversion",
)


def _looks_like_promo_type(value: Any) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return False
    return any(token in text for token in _PROMO_TYPE_HINTS)


def _has_promo_generator_input(global_info: Any) -> bool:
    gi = dict(global_info or {})
    promo_input = gi.get("promo_generator_input")
    if not isinstance(promo_input, dict):
        return False

    for key in (
        "promo_type",
        "campaign_objective",
        "target_audience",
        "key_message",
        "core_highlights",
        "conversion_cta",
    ):
        if str(promo_input.get(key) or "").strip():
            return True
    return False


def _should_use_promo_prompts(global_info: Any, req_type: Any = None, req_extra_notes: Any = None) -> bool:
    gi = dict(global_info or {})

    if _looks_like_promo_type(req_type):
        return True

    if _looks_like_promo_type(req_extra_notes):
        return True

    if _has_promo_generator_input(gi):
        return True

    saved_story_input = gi.get("story_generator_global_input")
    if isinstance(saved_story_input, dict):
        if _looks_like_promo_type(saved_story_input.get("type")):
            return True
        if _looks_like_promo_type(saved_story_input.get("extra_notes")):
            return True

    if _looks_like_promo_type(gi.get("type")):
        return True

    return False


def _normalize_generator_kind(value: Any) -> Optional[str]:
    raw = str(value or "").strip().lower()
    if raw in {"promo", "promotion", "promotional"}:
        return "promo"
    if raw in {"story", "narrative", "film"}:
        return "story"
    return None


def _pick_first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _normalize_script_mode_key(script_mode: Any) -> str:
    raw = str(script_mode or "").strip().lower()
    if "short drama" in raw or "短剧" in raw:
        return "short_drama"
    if "feature film" in raw or "电影" in raw:
        return "feature_film"
    if "action feature" in raw or "动作片" in raw:
        return "action_feature"
    if "romance" in raw or "emotional" in raw or "爱情情感" in raw:
        return "romance_emotional"
    if "mystery" in raw or "thriller" in raw or "悬疑惊悚" in raw:
        return "mystery_thriller"
    if "comedy" in raw or "light" in raw or "喜剧轻快" in raw:
        return "comedy_light"
    if "xianxia" in raw or "fantasy" in raw or "仙侠奇幻" in raw:
        return "xianxia_fantasy"
    if "sci-fi" in raw or "sci fi" in raw or "科幻冒险" in raw:
        return "sci_fi_adventure"
    if "period" in raw or "wuxia" in raw or "古装武侠" in raw:
        return "period_wuxia"
    if "workplace" in raw or "现代职场" in raw:
        return "modern_workplace"
    if "horror" in raw or "恐怖" in raw:
        return "horror"
    if "cyberpunk" in raw or "赛博朋克" in raw:
        return "cyberpunk"
    if "realism" in raw or "现实主义" in raw:
        return "realism"
    if "youth" in raw or "coming-of-age" in raw or "青春成长" in raw:
        return "youth_coming_of_age"
    if "general series" in raw or "通用连续剧" in raw:
        return "general_series"
    return "general_series"


_MANDATORY_WRITING_LOGIC_BY_SCRIPT_MODE: Dict[str, str] = {
    "short_drama": (
        "- 首分钟强钩子；压缩说明；快反转；集末强悬念；短句对白。\n"
        "- 表演主轴=对白+微表情+微动作（每句台词配说话人/听者微表演，禁对白裸奔）。\n"
        "- 减环境与动作变化：1-2 场、同轴近景、少换锚点/少走位/少道具大交互/少环境奇观；反转靠台词与表情落点而非场面调度。\n"
        "- 优先用有趣、机锋、刻薄、挑衅等有记忆点的短句对白推进关键信息，避免大段旁白式说明。"
    ),
    "feature_film": (
        "- 按电影单集/单部节奏组织起承转合；允许更完整的空间建置与动作链，但仍须服务核心冲突。"
    ),
    "action_feature": (
        "- 目标驱动情节；地理清晰；战术逐步升级；动作后果可见。"
    ),
    "romance_emotional": (
        "- 关系张力优先；多利用停顿/潜台词/身体距离；对白承担关系升降与人物塑形。"
    ),
    "mystery_thriller": (
        "- 精确控制线索；转移怀疑对象；压力逐步升级；结局设揭秘或陷阱。"
    ),
    "comedy_light": (
        "- 节奏性反转；误会成组；喜剧因果清晰。"
    ),
    "xianxia_fantasy": (
        "- 命运秩序与阶层奇观；术法/武戏须写可读动作链与特效层级，禁止只写“打起来”。"
    ),
    "sci_fi_adventure": (
        "- 未知探索；科技具象；逻辑破解；设定自洽。"
    ),
    "period_wuxia": (
        "- 江湖规矩；身法兵器；环境破坏；近身/兵器对抗按起势/换招/受力反馈/结果落位拆写。"
    ),
    "modern_workplace": (
        "- 职级权力；信息差；资源争夺；受限公共空间视线拉扯。"
    ),
    "horror": (
        "- 视觉盲区；生理恐惧；铺垫后惊吓释放。"
    ),
    "cyberpunk": (
        "- 阶级反差；技术异化；入侵/追击时写技术后果可视化与实体动作反馈。"
    ),
    "realism": (
        "- 克制；生活细节；困境与解法扎根现实。"
    ),
    "youth_coming_of_age": (
        "- 自我认同；同辈后果；本集一步成长。"
    ),
    "general_series": (
        "- 铺垫、升级、反转、情感释放、后续价值之间保持平衡。"
    ),
}


def _build_mandatory_writing_logic(script_mode: Any) -> str:
    key = _normalize_script_mode_key(script_mode)
    return _MANDATORY_WRITING_LOGIC_BY_SCRIPT_MODE.get(key) or _MANDATORY_WRITING_LOGIC_BY_SCRIPT_MODE["general_series"]


def _resolve_episode_duration_minutes(value: Any, *, default: int = 1) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    return n if n > 0 else default


def _build_episode_script_product_specs_block(
    *,
    episodes_count: Any,
    episode_duration_minutes: Any = 1,
    script_mode: str,
    target_audience: str,
) -> str:
    mode_label = script_mode or "（缺失：按项目全局框架与题材常识保守处理）"
    audience_label = target_audience or "（缺失：按项目全局框架与题材常识保守处理）"
    duration_minutes = _resolve_episode_duration_minutes(episode_duration_minutes)
    mandatory_logic = _build_mandatory_writing_logic(script_mode)
    return (
        "Project Product Specs (Hard Constraint):\n"
        f"- 载体规格 / Episodes Count: {episodes_count}\n"
        f"- 每集时长 / Episode Duration: {duration_minutes} minute(s)\n"
        f"- 产品规格与节奏 / Script Mode (Product Format): {mode_label}\n"
        f"- 受众定位 / Target Audience: {audience_label}\n"
        "\n"
        "Script Mode (Hard Constraint):\n"
        f"- {mode_label}\n"
        "\n"
        "Mandatory Writing Logic (强制写作逻辑, Hard Constraint):\n"
        f"{mandatory_logic}\n"
        "- Script Mode 与 Mandatory Writing Logic 为硬性写作逻辑；与通用默认冲突时，以本节为准。\n"
        "- 受众定位须极化核心看点与关系/情绪张力（男频/女频/全受众差异须体现在冲突选择与表达方式上）。\n"
        "\n"
    )


def _log_shot_submit_debug(kind: str, req: Any, refs: Any = None, extra: Optional[Dict[str, Any]] = None) -> None:
    if not _is_shot_submit_debug_enabled():
        return
    try:
        final_refs = _normalize_ref_list(refs if refs is not None else getattr(req, "ref_image_url", None))
        payload = {
            "kind": kind,
            "project_id": getattr(req, "project_id", None),
            "shot_id": getattr(req, "shot_id", None),
            "shot_number": getattr(req, "shot_number", None),
            "shot_name": getattr(req, "shot_name", None),
            "asset_type": getattr(req, "asset_type", None),
            "provider": getattr(req, "provider", None),
            "model": getattr(req, "model", None),
            "prompt": str(getattr(req, "prompt", "") or ""),
            "prompt_len": len(str(getattr(req, "prompt", "") or "")),
            "ref_count": len(final_refs),
            "refs": final_refs,
            "ref_names": _build_ref_display_names(final_refs),
        }
        if extra:
            payload.update(extra)
        llm_service.log_audit("SHOT_SUBMIT_DEBUG", payload)
    except Exception as exc:
        logger.warning("[ShotSubmitDebug] failed to log payload: %s", exc)



# datetime/compact -> generation_runtime.job_store