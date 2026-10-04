# -*- coding: utf-8 -*-
"""Story-generator LLM helpers (JSON normalize, structure call, episode refs)."""
from __future__ import annotations

import importlib
import json
import logging
import re
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.services.billing_service import billing_service
from app.services.db_session_utils import _release_db_connection
from app.services.llm_service import llm_service
from app.services.model_invocation_billing import (
    _apply_llm_routing_to_billing_details,
    _reservation_tx_id,
)
from app.services.script_analysis_llm_config import (
    _resolve_story_generator_script_analysis_llm_config,
    sanitize_script_generation_llm_config_text_only,
)

logger = logging.getLogger("api_logger")


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

# Save the Cat 15. Legacy I6/I7 buckets are rollups of these beats.
SAVE_THE_CAT_BEATS = [
    ("stc_01_opening_image", "01", "开场画面", "Opening Image", "第一幕"),
    ("stc_02_theme_stated", "02", "主题呈现", "Theme Stated", "第一幕"),
    ("stc_03_setup", "03", "铺垫", "Set-up", "第一幕"),
    ("stc_04_catalyst", "04", "催化剂", "Catalyst", "第一幕"),
    ("stc_05_debate", "05", "争执", "Debate", "第一幕"),
    ("stc_06_break_into_two", "06", "进入第二幕", "Break into Two", "第二幕上"),
    ("stc_07_b_story", "07", "B故事", "B Story", "第二幕上"),
    ("stc_08_fun_and_games", "08", "游戏时间", "Fun and Games", "第二幕上"),
    ("stc_09_midpoint", "09", "中点", "Midpoint", "第二幕下"),
    ("stc_10_bad_guys_close_in", "10", "反派逼近", "Bad Guys Close In", "第二幕下"),
    ("stc_11_all_is_lost", "11", "一无所有", "All Is Lost", "第二幕下"),
    ("stc_12_dark_night", "12", "灵魂黑夜", "Dark Night of the Soul", "第二幕下"),
    ("stc_13_break_into_three", "13", "进入第三幕", "Break into Three", "第三幕"),
    ("stc_14_finale", "14", "终场", "Finale", "第三幕"),
    ("stc_15_final_image", "15", "终场画面", "Final Image", "第三幕"),
]

_SAVE_THE_CAT_BEAT_KEYS = [row[0] for row in SAVE_THE_CAT_BEATS]

_LEGACY_BEAT_GROUPS = {
    "setup": _SAVE_THE_CAT_BEAT_KEYS[0:5],
    "development": _SAVE_THE_CAT_BEAT_KEYS[5:8],
    "turning_points": _SAVE_THE_CAT_BEAT_KEYS[8:12],
    "climax": _SAVE_THE_CAT_BEAT_KEYS[12:14],
    "resolution": _SAVE_THE_CAT_BEAT_KEYS[14:15],
}

_CREATIVE_INPUT_STRUCTURE_KEYS = [
    "logline",
    "theme",
    "core_conflict",
    "three_act",
    "background",
    "characters",
    *_SAVE_THE_CAT_BEAT_KEYS,
    "suspense",
    "foreshadowing",
    "classic_framework",
    "extra_notes",
    "setup",
    "development",
    "turning_points",
    "climax",
    "resolution",
]


def _field_text(source: Any, key: str) -> str:
    if isinstance(source, dict):
        val = source.get(key, "")
    else:
        val = getattr(source, key, "")
    if val is None:
        return ""
    return str(val).strip()


def rollup_save_the_cat(source: Any) -> Dict[str, str]:
    """Fold the 15 beats into the legacy plot buckets. Empty beats keep the old buckets."""
    has_beat = any(_field_text(source, key) for key in _SAVE_THE_CAT_BEAT_KEYS)
    if not has_beat:
        return {name: _field_text(source, name) for name in _LEGACY_BEAT_GROUPS}
    rolled: Dict[str, str] = {}
    for name, keys in _LEGACY_BEAT_GROUPS.items():
        parts = [_field_text(source, key) for key in keys]
        rolled[name] = "\n".join(part for part in parts if part)
    return rolled


def format_story_creative_input_block(source: Any) -> str:
    """Creative-input block for the global architect. Beats win; old buckets are the fallback."""
    lines = [
        "[Creative Input — 核心建置（三幕式 + 麦基《故事》）]",
        f"I1 高概念 / 欲望脊柱: {_field_text(source, 'logline')}",
        f"I2 主控思想 Controlling Idea（价值+原因）: {_field_text(source, 'theme')}",
        f"I3 对抗原则 · 否定之否定 · Gap · 危机抉择: {_field_text(source, 'core_conflict')}",
        f"I3b 三幕价值弧: {_field_text(source, 'three_act')}",
        f"I4 故事世界（压力场）: {_field_text(source, 'background')}",
        "",
        "[人物 — 《编剧的艺术》]",
        f"I5 前提 / 三维 / 统一的对立面 / 编排 / 弧光: {_field_text(source, 'characters')}",
        "",
        "[情节 — 救猫咪 15 节拍]",
    ]
    beat_lines = []
    for key, num, zh, en, act in SAVE_THE_CAT_BEATS:
        text = _field_text(source, key)
        if text:
            beat_lines.append(f"节拍{num} {zh} / {en}｜幕={act}: {text}")
    if beat_lines:
        lines.extend(beat_lines)
    else:
        lines.append("（15 节拍为空。下面是旧版情节桶，按幕归位，不是另一套结构。）")
        lines.append(f"旧开局与激励 → 第一幕: {_field_text(source, 'setup')}")
        lines.append(f"旧中段升级 → 第二幕上: {_field_text(source, 'development')}")
        lines.append(f"旧转折与中点 → 第二幕下: {_field_text(source, 'turning_points')}")
        lines.append(f"旧高潮与名场面 → 进入第三幕与终场: {_field_text(source, 'climax')}")
        lines.append(f"旧结局与收尾 → 终场画面: {_field_text(source, 'resolution')}")
    lines.extend([
        "",
        f"I8a 核心悬念: {_field_text(source, 'suspense')}",
        f"I8b 伏笔与必留: {_field_text(source, 'foreshadowing')}",
        f"I9 自由补充: {_field_text(source, 'extra_notes')}",
        f"I10 经典作品框架: {_field_text(source, 'classic_framework')}",
        f"天马行空原文: {_field_text(source, 'wild_creative_notes')}",
    ])
    return "\n".join(lines)


def _sanitize_llm_json_text(raw: str) -> str:
    content = re.sub(r"<think>.*?</think>", "", str(raw or ""), flags=re.DOTALL | re.IGNORECASE).strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content, re.IGNORECASE)
    if fenced:
        content = fenced.group(1).strip()
    content = content.replace("```json", "").replace("```", "").strip()
    # Keep Unicode curly quotes inside JSON string values; converting them to ASCII "
    # breaks valid payloads like: "core_conflict": "隐藏"穿越者"身份".
    content = re.sub(r",\s*}", "}", content)
    content = re.sub(r",\s*]", "]", content)
    return content


def _extract_llm_json_object_from_text(raw: str) -> Optional[Dict[str, Any]]:
    text = _sanitize_llm_json_text(raw)
    if not text:
        return None

    json5_obj = _loads_json5_if_available(text)
    if isinstance(json5_obj, dict):
        return json5_obj

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    start_idx = text.find("{")
    end_idx = text.rfind("}")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        candidate = text[start_idx:end_idx + 1]
        json5_obj = _loads_json5_if_available(candidate)
        if isinstance(json5_obj, dict):
            return json5_obj
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass

    decoder = json.JSONDecoder()
    for idx, ch in enumerate(text):
        if ch != "{":
            continue
        try:
            parsed, _end = decoder.raw_decode(text[idx:])
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            continue
    return None


def _normalize_llm_json_object(raw: str, *, context: str) -> Dict[str, Any]:
    data = _extract_llm_json_object_from_text(raw)
    if not isinstance(data, dict):
        logger.error("[%s] JSON parse failed. Raw len=%s", context, len(raw or ""))
        raise HTTPException(status_code=500, detail=f"Failed to parse LLM JSON for {context}")
    return data


async def _normalize_llm_json_object_with_repair(
    raw: str,
    *,
    context: str,
    llm_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    data = _extract_llm_json_object_from_text(raw)
    if isinstance(data, dict):
        return data

    content = _sanitize_llm_json_text(raw)
    if not content or not llm_config:
        logger.error("[%s] JSON parse failed and repair unavailable. Raw len=%s", context, len(raw or ""))
        raise HTTPException(status_code=500, detail=f"Failed to parse LLM JSON for {context}")

    repair_system = (
        "You are a strict JSON formatter. "
        "Convert the user's text into one valid JSON object only. "
        "The first character must be '{' and the last character must be '}'. "
        "Escape internal double quotes inside strings as \\\". "
        "No markdown fences, no explanation, no extra text."
    )
    repair_user = (
        "Fix the following content into valid JSON while preserving fields and values as much as possible.\n\n"
        f"{content}"
    )
    try:
        repair_response = await llm_service.chat_completion_with_fallback(
            [
                {"role": "system", "content": repair_system},
                {"role": "user", "content": repair_user},
            ],
            llm_config,
        )
        repair_raw = str((repair_response or {}).get("content") or "").strip()
        repaired = _extract_llm_json_object_from_text(repair_raw)
        if isinstance(repaired, dict):
            logger.warning("[%s] JSON parse recovered via repair pass", context)
            return repaired
    except Exception as exc:
        logger.warning("[%s] JSON repair pass failed: %s", context, exc)

    logger.error("[%s] JSON parse failed after repair. Raw len=%s", context, len(raw or ""))
    raise HTTPException(status_code=500, detail=f"Failed to parse LLM JSON for {context}")


_CLASSIC_FRAMEWORK_ALIASES = (
    "classic_framework",
    "I10",
    "i10",
    "经典作品框架",
)

_CLASSIC_FRAMEWORK_PLACEHOLDERS = frozenset({
    "",
    "无",
    "暂无",
    "空",
    "没有",
    "无内容",
    "无框架",
    "暂缺",
    "待定",
    "待补",
    "待补充",
    "推断",
    "未知",
    "不详",
    "略",
    "省略",
    "不适用",
    "无需",
    "不必",
    "留空",
    "n/a",
    "na",
    "none",
    "null",
    "nil",
    "tbd",
    "todo",
    "undefined",
    "-",
    "—",
    "——",
    "/",
    "／",
    "{}",
    "[]",
})

_CLASSIC_FRAMEWORK_PLACEHOLDER_RE = re.compile(
    r"^(?:"
    r"无|暂无|没有|不详|未知|待定|待补|待补充|省略|略|空|不适用|无需|不必|留空|"
    r"(?:无|暂无|没有|暂缺)(?:相关)?(?:经典)?(?:作品)?(?:框架|参考)?|"
    r"n/?a|none|null|nil|tbd|todo|undefined"
    r")$",
    re.IGNORECASE,
)

# A real I10 names a primary work plus auxiliaries. Shorter than this is a blank or a genre tag.
_CLASSIC_FRAMEWORK_MIN_COMPACT = 20


def _classic_framework_compact(text: str) -> str:
    raw = str(text or "").strip()
    compact = re.sub(r"[\s\u3000]+", "", raw)
    return compact.strip("。．.，,；;：:、\"'`“”‘’【】[]()（）")


def classic_framework_needs_fill(text: str) -> bool:
    """True when I10 is missing, a placeholder, or too short to be a work framework."""
    compact = _classic_framework_compact(text)
    if not compact:
        return True
    lowered = compact.lower()
    if lowered in _CLASSIC_FRAMEWORK_PLACEHOLDERS:
        return True
    if _CLASSIC_FRAMEWORK_PLACEHOLDER_RE.fullmatch(lowered):
        return True
    unlabeled = re.sub(r"(主框架|辅助\d*|经典作品框架|i10|classicframework)", "", lowered)
    unlabeled = unlabeled.strip("：:；;，,。．.、")
    if not unlabeled or unlabeled in _CLASSIC_FRAMEWORK_PLACEHOLDERS:
        return True
    if _CLASSIC_FRAMEWORK_PLACEHOLDER_RE.fullmatch(unlabeled):
        return True
    return len(compact) < _CLASSIC_FRAMEWORK_MIN_COMPACT


def classic_framework_text(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, str):
        return val.strip()
    if isinstance(val, list):
        parts = [classic_framework_text(item) for item in val]
        return "\n".join(part for part in parts if part)
    if isinstance(val, dict):
        for key in _CLASSIC_FRAMEWORK_ALIASES + ("text", "content", "框架"):
            if key in val:
                nested = classic_framework_text(val.get(key))
                if nested:
                    return nested
        if not val:
            return ""
        return json.dumps(val, ensure_ascii=False)
    return str(val).strip()


def apply_classic_framework_from_llm(normalized: Dict[str, str], data: Any) -> Dict[str, str]:
    """Keep a non-empty I10. Salvage it when the model used an alias or a nested value."""
    if isinstance(data, dict):
        for key in _CLASSIC_FRAMEWORK_ALIASES:
            salvaged = classic_framework_text(data.get(key))
            if not classic_framework_needs_fill(salvaged):
                normalized["classic_framework"] = salvaged
                return normalized
    current = classic_framework_text(normalized.get("classic_framework"))
    if not classic_framework_needs_fill(current):
        normalized["classic_framework"] = current
        return normalized
    normalized["classic_framework"] = ""
    return normalized


def _classic_framework_story_context(normalized: Dict[str, str]) -> str:
    lines = []
    for key, label in (
        ("logline", "I1"),
        ("theme", "I2"),
        ("core_conflict", "I3"),
        ("three_act", "I3b"),
        ("background", "I4"),
        ("characters", "I5"),
        ("suspense", "I8a"),
        ("foreshadowing", "I8b"),
    ):
        text = _field_text(normalized, key)
        if text:
            lines.append(f"{label}: {text}")
    for key, num, zh, en, act in SAVE_THE_CAT_BEATS:
        text = _field_text(normalized, key)
        if text:
            lines.append(f"节拍{num} {zh} / {en}｜幕={act}: {text}")
    return "\n".join(lines)


def build_classic_framework_fill_prompts(
    normalized: Dict[str, str],
    *,
    creative_text: str,
    project_context: str,
) -> tuple[str, str]:
    system = (
        "You complete one missing story field. "
        "Output ONLY a JSON object whose single key is classic_framework. "
        "The first character must be '{' and the last character must be '}'. "
        "No markdown fences, no explanation. "
        "classic_framework MUST be a non-empty string. "
        "Forbidden values: empty string, 无, 暂无, N/A, 待定, 推断, 空, none, or a genre label with no titled work. "
        "Name one modern/contemporary primary work (literature, film, TV, or game; recent decades) "
        "as plot-logic spine, plus at least 5 auxiliary works. "
        "Older classics may be auxiliaries only. Each auxiliary contributes a different dimension "
        "(桥段|特效|动作|对白|反转|关系). "
        "For every work write reusable logic, shootable distance/comms/blocking, 转译 into THIS story, and which beats it lands on. "
        "Format: 主框架：《作品》（现代/当代·媒介）— 剧情逻辑：…；可拍逻辑：…；转译：…；落拍：…。"
        "辅助1：《作品》— 贡献维度=…；机制：…；可拍逻辑：…；转译：…；落拍：…。 "
        "Continue through 辅助5 or more. "
        "Write the value in the same language as the story fields. "
        "Do not copy the source work's era, costumes, or locations."
    )
    user = (
        "The structured prefill left I10 classic_framework empty. Fill it now. "
        "It must match this story's causal logic. Do not start a different plot.\n\n"
        f"{project_context}\n"
        f"Wild Creative Brainstorm:\n{creative_text}\n\n"
        "Structured fields already accepted:\n"
        f"{_classic_framework_story_context(normalized)}"
    )
    return system, user


async def ensure_classic_framework_filled(
    *,
    db: Session,
    user_id: int,
    project_global_info: Optional[Dict[str, Any]],
    req: Any,
    normalized: Dict[str, str],
    creative_text: str,
    project_context: str,
    llm_config: Optional[Dict[str, Any]] = None,
    max_attempts: int = 2,
) -> Dict[str, str]:
    """When structured prefill omits I10, call the LLM again until that field is filled."""
    if not classic_framework_needs_fill(normalized.get("classic_framework", "")):
        return normalized

    logger.warning("[structure_creative_input] classic_framework empty; requesting required fill")
    system, user = build_classic_framework_fill_prompts(
        normalized,
        creative_text=creative_text,
        project_context=project_context,
    )
    attempts = max(1, int(max_attempts))
    for attempt in range(1, attempts + 1):
        raw = await _run_structure_llm_call(
            db=db,
            user_id=user_id,
            project_global_info=project_global_info,
            req=req,
            sys_prompt=system,
            user_prompt=user,
            billing_item="structure_creative_input_classic_framework",
            llm_context="structure_creative_input_classic_framework",
        )
        data = await _normalize_llm_json_object_with_repair(
            raw,
            context="structure_creative_input_classic_framework",
            llm_config=llm_config,
        )
        filled = ""
        if isinstance(data, dict):
            for key in _CLASSIC_FRAMEWORK_ALIASES:
                candidate = classic_framework_text(data.get(key))
                if not classic_framework_needs_fill(candidate):
                    filled = candidate
                    break
        if filled:
            normalized["classic_framework"] = filled
            logger.info(
                "[structure_creative_input] classic_framework filled on attempt %s len=%s",
                attempt,
                len(filled),
            )
            return normalized
        logger.warning(
            "[structure_creative_input] classic_framework still empty after fill attempt %s",
            attempt,
        )

    raise HTTPException(
        status_code=500,
        detail="I10 classic_framework remained empty after required completion",
    )


def _normalize_story_field_map(data: Dict[str, Any], keys: List[str]) -> Dict[str, str]:
    normalized: Dict[str, str] = {}
    for key in keys:
        val = data.get(key, "")
        if val is None:
            normalized[key] = ""
        elif isinstance(val, str):
            normalized[key] = val.strip()
        else:
            normalized[key] = str(val).strip()
    return normalized


async def _run_structure_llm_call(
    *,
    db: Session,
    user_id: int,
    project_global_info: Optional[Dict[str, Any]],
    req: Any,
    sys_prompt: str,
    user_prompt: str,
    billing_item: str,
    llm_context: str,
) -> str:
    function_name = (getattr(req, "function_name", None) if req else None) or "script_analysis"
    system_api_id = getattr(req, "system_api_id", None) if req else None
    llm_config = _resolve_story_generator_script_analysis_llm_config(
        db,
        user_id,
        function_name=function_name,
        system_api_id=system_api_id,
        context=llm_context,
        project_global_info=project_global_info,
    )
    if not llm_config or not (llm_config.get("api_key") or "").strip():
        raise HTTPException(status_code=400, detail="No valid LLM API key configured in active settings")
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
            user_id,
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
        billing_service.check_balance(db, user_id, "llm_chat", provider, model)

    try:
        _release_db_connection(db, f"{llm_context}_llm_call")
        # After reference search / structure fill: text evidence only, no images.
        text_only_cfg = sanitize_script_generation_llm_config_text_only(llm_config)
        resp = await llm_service.generate_content_with_fallback(
            user_prompt, sys_prompt, text_only_cfg, image_urls=None, video_urls=None
        )
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
        billing_service.deduct_credits(db, user_id, "llm_chat", provider, model, billing_details)

    return raw


async def _prepare_episode_script_reference_block(
    *,
    user_id: int,
    project_global_info: Optional[Dict[str, Any]],
    llm_config: Dict[str, Any],
    global_md: str,
    episode_number: int,
    project_title: str = "",
    language: str = "",
) -> str:
    """Episode writing no longer runs web search; submit the framework to the LLM directly."""
    logger.info(
        "[generate_episode_scripts] REFERENCE_SEARCH_SKIP episode_number=%s reason=disabled",
        episode_number,
    )
    return ""
