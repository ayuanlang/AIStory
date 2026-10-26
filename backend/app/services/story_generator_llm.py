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

# Egri rising-conflict spine for the emotion-driven product format.
EGRI_CONCEPT_KEYS = [
    "egri_premise",
    "egri_pivotal",
    "egri_unity",
    "egri_dimensions",
    "egri_social",
    "egri_transition",
]
EGRI_STEP_KEYS = [
    ("egri_01_attack", "01", "攻击点"),
    ("egri_02_counter", "02", "反攻"),
    ("egri_03_lock", "03", "锁死"),
    ("egri_04_orchestrate", "04", "编排"),
    ("egri_05_transition", "05", "过渡"),
    ("egri_06_crisis", "06", "危机"),
    ("egri_07_proof", "07", "证明"),
    ("egri_08_conclusion", "08", "结局"),
]
_EGRI_ONLY_KEYS = EGRI_CONCEPT_KEYS + [row[0] for row in EGRI_STEP_KEYS]
EMOTION_DRIVEN_STRUCTURE_KEYS = [
    "logline",
    "theme",
    "core_conflict",
    "three_act",
    "background",
    "characters",
    *_EGRI_ONLY_KEYS,
    "story_circle",
    "plot_background",
    "story_lines",
    "time_nodes",
    "professional_domains",
    "places_and_props",
    "suspense",
    "foreshadowing",
    "classic_framework",
    "ai_vfx_strategy",
    "extra_notes",
]

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
    "plot_background",
    "story_lines",
    "time_nodes",
    "professional_domains",
    "places_and_props",
    "suspense",
    "foreshadowing",
    "classic_framework",
    "ai_vfx_strategy",
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


_PREFILL_TEXT_KEYS = (
    "logline",
    "theme",
    "core_conflict",
    "three_act",
    "background",
    "characters",
    "plot_background",
    "story_lines",
    "time_nodes",
    "professional_domains",
    "places_and_props",
    "suspense",
    "foreshadowing",
    "extra_notes",
    "story_circle",
    "classic_framework",
    "ai_vfx_strategy",
    "wild_creative_notes",
    "setup",
    "development",
    "turning_points",
    "climax",
    "resolution",
) + tuple(row[0] for row in SAVE_THE_CAT_BEATS) + tuple(_EGRI_ONLY_KEYS)


def structured_prefill_has_text(source: Any) -> bool:
    return any(_field_text(source, key) for key in _PREFILL_TEXT_KEYS)


def _source_uses_egri(source: Any) -> bool:
    from app.services.script_mode_helpers import is_emotion_driven_script_mode

    if is_emotion_driven_script_mode(_field_text(source, "script_mode")):
        return True
    if _field_text(source, "script_mode"):
        return False
    return any(_field_text(source, key) for key, _num, _zh in EGRI_STEP_KEYS)


def format_egri_creative_input_block(source: Any) -> str:
    """Emotion-driven prefill. The spine is Egri's rising conflict, not Save the Cat."""
    lines = [
        "[情绪驱动预填 — 埃格里《编剧的艺术》]",
        "本预填不是救猫咪，也不是麦基的节拍表。全剧情节只按下面八阶上升。分集用故事环，环步落在某一阶上。",
        f"一句话: {_field_text(source, 'logline')}",
        f"前提: {_field_text(source, 'egri_premise') or _field_text(source, 'theme')}",
        f"关键人物与攻击点: {_field_text(source, 'egri_pivotal')}",
        f"统一的对立面: {_field_text(source, 'egri_unity') or _field_text(source, 'core_conflict')}",
        f"三维与编排: {_field_text(source, 'egri_dimensions') or _field_text(source, 'characters')}",
        f"社会与人性: {_field_text(source, 'egri_social') or _field_text(source, 'background')}",
        f"过渡: {_field_text(source, 'egri_transition')}",
        f"三句落点（攻击点／上升／证明，不是三幕节拍）: {_field_text(source, 'three_act')}",
        "",
        "[上升冲突八阶]",
    ]
    for key, num, zh in EGRI_STEP_KEYS:
        lines.append(f"阶{num} {zh}: {_field_text(source, key)}")
    lines.extend([
        "",
        "[故事环]",
        f"{_field_text(source, 'story_circle')}",
        "",
        f"世界背景: {_field_text(source, 'egri_social') or _field_text(source, 'background')}",
        f"剧情背景: {_field_text(source, 'plot_background')}",
        f"故事线: {_field_text(source, 'story_lines')}",
        f"时间节点: {_field_text(source, 'time_nodes')}",
        f"专业领域: {_field_text(source, 'professional_domains')}",
        f"场景与道具: {_field_text(source, 'places_and_props')}",
        f"悬念: {_field_text(source, 'suspense')}",
        f"伏笔与必留: {_field_text(source, 'foreshadowing')}",
        "[经典借鉴]",
        f"{_field_text(source, 'classic_framework')}",
        f"AI优势应用与劣势回避: {_field_text(source, 'ai_vfx_strategy')}",
        f"自由补充: {_field_text(source, 'extra_notes')}",
        f"天马行空原文: {_field_text(source, 'wild_creative_notes')}",
    ])
    return "\n".join(lines)


def prefill_source_for_outline(req: Any, global_info: Any) -> Dict[str, str]:
    """Outline prompts read the request first, then the saved script framework."""
    saved: Dict[str, Any] = {}
    if isinstance(global_info, dict):
        story = global_info.get("story_generator_global_input")
        if isinstance(story, dict):
            saved = story
    out: Dict[str, str] = {}
    for key in _PREFILL_TEXT_KEYS:
        out[key] = _field_text(req, key) or _field_text(saved, key)
    out["script_mode"] = _field_text(req, "script_mode") or _field_text(saved, "script_mode")
    return out


def format_outline_registry_block(source: Any) -> str:
    """Five locked framework columns. §9 分集规划 reads these lines and does not invent another set."""
    return "\n".join([
        "[剧本框架五栏 — 分集规划输入]",
        "这五栏是写 §9 分集规划的输入，原文已经在剧本框架锁好。时间行的节点、季节、昼夜、气候用时间节点。每一集用空间行写明涉及的地方，至少一处，可以多处，不并成一个名字。名字逐字用场景与道具里的空间名。场景以简单为第一优先：四壁每壁只有封闭面再加一具贴墙、嵌入或悬挂的主体，中部只有一个主体加必须的配套和必要的最少配饰。每一处写主体、负载和复用。首现只锁这个上限。之后先用这些主体，新功能能落在已有主体上就写落在，已有桌面能做全息控制就不另起立式控制台。做不到或超负载就另起一处并标补，不往旧处加主体。非封闭环境的远景不写入主体。专业行的领域只用专业领域里登记的名字。切场的线用故事线。EP01 摘要把剧情背景演成一件看得见的事，不把全文再贴成旁白。五栏有字时，不得另起一套领域或时间节点。空间名先用场景与道具里已有的；只有这一集离了就做不成，或这一处主体超负载，才另起一处并标补。",
        f"剧情背景: {_field_text(source, 'plot_background')}",
        f"故事线: {_field_text(source, 'story_lines')}",
        f"时间节点: {_field_text(source, 'time_nodes')}",
        f"专业领域: {_field_text(source, 'professional_domains')}",
        f"场景与道具: {_field_text(source, 'places_and_props')}",
    ])


def keep_saved_registry_fields(incoming: Dict[str, Any], saved: Any) -> Dict[str, Any]:
    """A blank save must not erase the five framework columns already stored on the project."""
    previous = saved if isinstance(saved, dict) else {}
    out = dict(incoming or {})
    for key in ("plot_background", "story_lines", "time_nodes", "professional_domains", "places_and_props"):
        if _field_text(out, key):
            continue
        kept = _field_text(previous, key)
        if kept:
            out[key] = kept
    return out


def format_story_creative_input_block(source: Any) -> str:
    """Creative-input block for the global architect. Emotion-driven uses Egri; otherwise beats win."""
    if _source_uses_egri(source):
        return format_egri_creative_input_block(source)
    lines = [
        "[Creative Input — 核心建置（三幕式 + 麦基《故事》）]",
        f"I1 高概念 / 欲望脊柱: {_field_text(source, 'logline')}",
        f"I2 主控思想 Controlling Idea（价值+原因）: {_field_text(source, 'theme')}",
        f"I3 对抗原则 · 否定之否定 · Gap · 危机抉择: {_field_text(source, 'core_conflict')}",
        f"I3b 三幕价值弧: {_field_text(source, 'three_act')}",
        f"世界背景: {_field_text(source, 'background')}",
        f"剧情背景: {_field_text(source, 'plot_background')}",
        f"故事线: {_field_text(source, 'story_lines')}",
        f"时间节点: {_field_text(source, 'time_nodes')}",
        f"专业领域: {_field_text(source, 'professional_domains')}",
        f"场景与道具: {_field_text(source, 'places_and_props')}",
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
        f"I11 AI优势应用与劣势回避: {_field_text(source, 'ai_vfx_strategy')}",
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

_AI_VFX_ALIASES = (
    "ai_vfx_strategy",
    "AI优势应用与劣势回避",
    "ai优势应用与劣势回避",
    "I11",
    "i11",
    "AI特效",
    "ai_vfx",
)

_AI_VFX_KEY_HINTS = ("优势应用", "劣势回避", "AI特效", "ai_vfx")

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
    for key, num, zh in EGRI_STEP_KEYS:
        text = _field_text(normalized, key)
        if text:
            lines.append(f"阶{num} {zh}: {text}")
    premise = _field_text(normalized, "egri_premise")
    if premise and premise not in "\n".join(lines):
        lines.append(f"前提: {premise}")
    return "\n".join(lines)


def _context_is_emotion_driven(project_context: str) -> bool:
    raw = str(project_context or "").lower()
    return "情绪驱动" in project_context or "emotion-driven" in raw or "emotion driven" in raw


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
        "This is overall logic for the framework. Referenced plot is allowed when it fits this story's background and theme and is fused into this plot. Do not hard-splice. Do not lock episode dialogue or set pieces. "
        "Do not copy the source work's era, costumes, or locations."
    )
    if _context_is_emotion_driven(project_context):
        system += (
            " This story is emotion-driven and follows Egri, not Save the Cat. "
            "The primary work must prove a premise about society or human nature through character conflict. "
            "Auxiliary dimensions are 对立面|过渡|社会层|对白|关系|代价. "
            "Write 落阶 using 01-08 only. Do not use Opening, Midpoint, Finale, or other Save the Cat beat names."
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
    user_name: Optional[str] = None,
    project_id: Optional[int] = None,
) -> Dict[str, str]:
    """When structured prefill omits I10, call the LLM again until that field is filled."""
    if not classic_framework_needs_fill(normalized.get("classic_framework", "")):
        return normalized

    from app.services.task_manager import abort_if_current_task_canceled

    logger.warning("[structure_creative_input] classic_framework empty; requesting required fill")
    abort_if_current_task_canceled()
    system, user = build_classic_framework_fill_prompts(
        normalized,
        creative_text=creative_text,
        project_context=project_context,
    )
    attempts = max(1, int(max_attempts))
    from app.services.task_manager import abort_if_current_task_canceled

    for attempt in range(1, attempts + 1):
        abort_if_current_task_canceled()
        raw = await _run_structure_llm_call(
            db=db,
            user_id=user_id,
            project_global_info=project_global_info,
            req=req,
            sys_prompt=system,
            user_prompt=user,
            billing_item="structure_creative_input_classic_framework",
            llm_context="structure_creative_input_classic_framework",
            user_name=user_name,
            project_id=project_id,
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


def ai_vfx_needs_fill(text: str) -> bool:
    """True when the AI-advantage field is missing or only a placeholder."""
    compact = _classic_framework_compact(text)
    if not compact:
        return True
    lowered = compact.lower()
    if lowered in _CLASSIC_FRAMEWORK_PLACEHOLDERS:
        return True
    if _CLASSIC_FRAMEWORK_PLACEHOLDER_RE.fullmatch(lowered):
        return True
    return len(compact) < 8


def ai_vfx_text(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, str):
        return val.strip()
    if isinstance(val, list):
        parts = [ai_vfx_text(item) for item in val]
        return "\n".join(part for part in parts if part)
    if isinstance(val, dict):
        for key in ("ai_vfx_strategy", "text", "content", "I11", "i11", "AI优势应用与劣势回避"):
            if key in val:
                nested = ai_vfx_text(val.get(key))
                if not ai_vfx_needs_fill(nested):
                    return nested
        lines = []
        for key, item in val.items():
            piece = ai_vfx_text(item)
            if piece:
                lines.append(f"{key}：{piece}")
        return "\n".join(lines)
    return str(val).strip()


def _ai_vfx_from_payload(data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    for key in _AI_VFX_ALIASES:
        salvaged = ai_vfx_text(data.get(key))
        if not ai_vfx_needs_fill(salvaged):
            return salvaged
    for key, val in data.items():
        name = str(key)
        if any(hint in name for hint in _AI_VFX_KEY_HINTS):
            salvaged = ai_vfx_text(val)
            if not ai_vfx_needs_fill(salvaged):
                return salvaged
    return ""


def apply_ai_vfx_from_llm(normalized: Dict[str, str], data: Any) -> Dict[str, str]:
    """Keep a non-empty AI-advantage field. Salvage Chinese or I11 keys."""
    salvaged = _ai_vfx_from_payload(data)
    if salvaged:
        normalized["ai_vfx_strategy"] = salvaged
        return normalized
    current = ai_vfx_text(normalized.get("ai_vfx_strategy"))
    normalized["ai_vfx_strategy"] = "" if ai_vfx_needs_fill(current) else current
    return normalized


def build_ai_vfx_fill_prompts(
    normalized: Dict[str, str],
    *,
    creative_text: str,
    project_context: str,
) -> tuple[str, str]:
    system = (
        "You complete one missing story field. "
        "Output ONLY a JSON object whose single key is ai_vfx_strategy. "
        "The first character must be '{' and the last character must be '}'. "
        "No markdown fences, no explanation. "
        "ai_vfx_strategy MUST be a non-empty string in the same language as the story fields. "
        "This is 「AI优势应用与劣势回避」: how AI visual effects make THIS story's pictures stronger, "
        "and which actions to rewrite so the picture still reads. Not a second plot. "
        "Advantage: at least two lines. Format: "
        "拍=01|04|14｜特效=具象化形|环境奇观|满幅异象|天气与季节介质|垂直空域|集体动势|物件特写｜"
        "画面增量=the shape, scale, light, or season the audience newly sees｜服务=the choice or hook of that beat. "
        "Write what the effect becomes. Forbidden: 能量爆发, 金光一闪, and glow with no body. "
        "When the project season block says 档=已锁, at least one line uses that season's visible medium. "
        "Avoidance: rewrite sleeve, bosom, pocket, fingertip, three-person fine interaction, "
        "five-person brawl, or dense-furniture chase as 原风险=…｜改写=…｜画面仍保留=…. "
        "Continuous attacks are not avoidance items. If none of these risks exist, write 劣势回避=本脑洞无高风险互动. "
        "Do not write wires, doubles, or green screen."
    )
    if _context_is_emotion_driven(project_context):
        system += (
            " This story is emotion-driven. Write 阶=01|06|07, not 拍=. "
            "01 is 攻击点, 02 反攻, 03 锁死, 04 编排, 05 过渡, 06 危机, 07 证明, 08 结局. "
            "Do not name Save the Cat beats."
        )
    user = (
        "The structured prefill left ai_vfx_strategy empty. Fill it now for this same story.\n\n"
        f"{project_context}\n"
        f"Wild Creative Brainstorm:\n{creative_text}\n\n"
        "Structured fields already accepted:\n"
        f"{_classic_framework_story_context(normalized)}"
    )
    return system, user


async def ensure_ai_vfx_strategy_filled(
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
    user_name: Optional[str] = None,
    project_id: Optional[int] = None,
) -> Dict[str, str]:
    """When structured prefill omits the AI-advantage field, call the LLM again to fill it."""
    if not ai_vfx_needs_fill(normalized.get("ai_vfx_strategy", "")):
        return normalized

    logger.warning("[structure_creative_input] ai_vfx_strategy empty; requesting required fill")
    system, user = build_ai_vfx_fill_prompts(
        normalized,
        creative_text=creative_text,
        project_context=project_context,
    )
    attempts = max(1, int(max_attempts))
    from app.services.task_manager import abort_if_current_task_canceled

    for attempt in range(1, attempts + 1):
        abort_if_current_task_canceled()
        raw = await _run_structure_llm_call(
            db=db,
            user_id=user_id,
            project_global_info=project_global_info,
            req=req,
            sys_prompt=system,
            user_prompt=user,
            billing_item="structure_creative_input_ai_vfx",
            llm_context="structure_creative_input_ai_vfx",
            user_name=user_name,
            project_id=project_id,
        )
        data = await _normalize_llm_json_object_with_repair(
            raw,
            context="structure_creative_input_ai_vfx",
            llm_config=llm_config,
        )
        filled = _ai_vfx_from_payload(data)
        if filled:
            normalized["ai_vfx_strategy"] = filled
            logger.info(
                "[structure_creative_input] ai_vfx_strategy filled on attempt %s len=%s",
                attempt,
                len(filled),
            )
            return normalized
        logger.warning(
            "[structure_creative_input] ai_vfx_strategy still empty after fill attempt %s",
            attempt,
        )
    return normalized


# These five live on the script-framework form. Models often emit the Chinese labels.
_REGISTRY_KEYS = (
    "plot_background",
    "story_lines",
    "time_nodes",
    "professional_domains",
    "places_and_props",
)

_REGISTRY_ALIASES = {
    "plot_background": ("plot_background", "剧情背景", "plot background", "Plot Background"),
    "story_lines": ("story_lines", "故事线", "story lines", "Story Lines"),
    "time_nodes": ("time_nodes", "时间节点", "time nodes", "Time Nodes"),
    "professional_domains": ("professional_domains", "专业领域", "crafts", "Crafts"),
    "places_and_props": (
        "places_and_props",
        "场景与道具",
        "places and props",
        "Places & Props",
        "places_props",
    ),
}

_REGISTRY_LABELS = {
    "plot_background": "剧情背景",
    "story_lines": "故事线",
    "time_nodes": "时间节点",
    "professional_domains": "专业领域",
    "places_and_props": "场景与道具",
}

_REGISTRY_HEADING_TO_KEY = {label: key for key, label in _REGISTRY_LABELS.items()}

_REGISTRY_HEADING_RE = re.compile(
    r"(?:^|\n)\s*(?:[#*]{0,3}\s*)?(剧情背景|故事线|时间节点|专业领域|场景与道具)\s*[:：]\s*"
)


def _registry_blank(text: str) -> bool:
    compact = _classic_framework_compact(text)
    if not compact:
        return True
    lowered = compact.lower()
    if lowered in _CLASSIC_FRAMEWORK_PLACEHOLDERS:
        return True
    return bool(_CLASSIC_FRAMEWORK_PLACEHOLDER_RE.fullmatch(lowered))


def _flatten_generic(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, str):
        return val.strip()
    if isinstance(val, list):
        return "\n".join(part for part in (_flatten_generic(item) for item in val) if part)
    if isinstance(val, dict):
        lines = []
        for key, item in val.items():
            piece = _flatten_generic(item)
            if piece:
                lines.append(f"{key}={piece}")
        return "\n".join(lines)
    return str(val).strip()


def _format_place_item(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()
    if not isinstance(item, dict):
        return _flatten_generic(item)
    name = ""
    for key in ("名", "name", "空间", "地点", "道具", "place"):
        candidate = str(item.get(key) or "").strip()
        if candidate:
            name = candidate
            break
    english = str(item.get("EN") or item.get("en") or item.get("英文") or "").strip()
    label = f"{name} ({english})" if name and english else name
    function = str(item.get("功能") or item.get("function") or "").strip()
    access = str(item.get("准入") or "").strip()
    kind = str(item.get("类型") or item.get("kind") or "").strip()
    named_place = any(str(item.get(key) or "").strip() for key in ("名", "name", "空间", "地点", "place"))
    is_prop = (
        kind == "道具"
        or "道具" in kind
        or bool(str(item.get("道具名") or "").strip())
        or (bool(str(item.get("道具") or "").strip()) and not named_place)
    )
    if is_prop:
        prop_name = str(item.get("道具") or item.get("道具名") or name).strip()
        return "｜".join(part for part in ("道具", prop_name, f"功能={function}" if function else "") if part)
    parts = [label]
    if function:
        parts.append(f"功能={function}")
    if access:
        parts.append(f"准入={access}")
    line = "｜".join(part for part in parts if part)
    return line or _flatten_generic(item)


def _flatten_registry_value(key: str, val: Any) -> str:
    if isinstance(val, list):
        if key == "places_and_props":
            return "\n".join(part for part in (_format_place_item(item) for item in val) if part)
        return "\n".join(part for part in (_flatten_registry_value(key, item) for item in val) if part)
    if not isinstance(val, dict):
        return _flatten_generic(val)
    if key == "plot_background":
        sentence = str(val.get("句子") or "").strip()
        if not sentence:
            bits = [
                str(val.get(part) or "").strip()
                for part in ("公开处境", "关系前史", "此刻为何非做不可", "此刻")
            ]
            sentence = "。".join(bit for bit in bits if bit)
        if sentence:
            means = str(val.get("手段") or "对话").strip() or "对话"
            ban = str(val.get("禁提前") or "结局").strip() or "结局"
            ident = str(val.get("id") or val.get("编号") or "PB01").strip() or "PB01"
            return f"剧情背景: {ident}｜{sentence}｜手段={means}｜禁提前={ban}"
    if key == "story_lines":
        count = str(val.get("线数") or "").strip()
        if count == "1":
            reason = str(val.get("豁免依据") or "单一封闭空间").strip() or "单一封闭空间"
            return f"线数=1｜豁免依据={reason}"
        parts = []
        for line_key in ("线A", "线B", "线C", "线D"):
            piece = str(val.get(line_key) or "").strip()
            if piece:
                parts.append(f"{line_key}={piece}")
        if parts:
            return "｜".join(parts)
    if key == "time_nodes":
        season = str(val.get("季节") or "").strip()
        if season or val.get("昼夜") or val.get("气候"):
            node = str(val.get("节点") or val.get("名") or "开篇").strip() or "开篇"
            return (
                f"{node}｜式={str(val.get('式') or '相对').strip() or '相对'}"
                f"｜季节={season}｜昼夜={str(val.get('昼夜') or '').strip()}"
                f"｜气候={str(val.get('气候') or '').strip()}"
                f"｜说明={str(val.get('说明') or '').strip()}"
            )
    if key == "professional_domains":
        domain = str(val.get("领域") if val.get("领域") is not None else "").strip()
        procedure = str(val.get("规程") or "").strip()
        trigger = str(val.get("触因") or "").strip()
        wrong = str(val.get("错法") or "").strip()
        if domain in ("", "无") and not procedure and not trigger and not wrong:
            reason = str(val.get("依据") or "本剧选择不依赖行业规程").strip() or "本剧选择不依赖行业规程"
            return f"领域=无｜依据={reason}"
        if domain or procedure or trigger or wrong:
            return f"领域={domain}｜触因={trigger}｜规程={procedure}｜错法={wrong}"
    if key == "places_and_props":
        return _format_place_item(val)
    return _flatten_generic(val)


def _split_headed_text(text: str) -> Dict[str, str]:
    matches = list(_REGISTRY_HEADING_RE.finditer(str(text or "")))
    if not matches:
        return {}
    found: Dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        key = _REGISTRY_HEADING_TO_KEY[match.group(1)]
        body = str(text[start:end] or "").strip()
        if body and key not in found:
            found[key] = body
    return found


def _registry_sources(data: Any) -> List[Dict[str, Any]]:
    sources: List[Dict[str, Any]] = []
    if not isinstance(data, dict):
        return sources
    sources.append(data)
    for key, val in data.items():
        name = str(key)
        if isinstance(val, dict) and any(hint in name for hint in ("全局", "登记", "registry", "Registry")):
            sources.append(val)
    return sources


def _salvage_registry_key(data: Any, key: str) -> str:
    aliases = {alias.lower() for alias in _REGISTRY_ALIASES[key]}
    for source in _registry_sources(data):
        for alias in _REGISTRY_ALIASES[key]:
            if alias in source:
                text = _flatten_registry_value(key, source.get(alias))
                if not _registry_blank(text):
                    return text
        for raw_key, val in source.items():
            if str(raw_key).strip().lower() in aliases:
                text = _flatten_registry_value(key, val)
                if not _registry_blank(text):
                    return text
    if isinstance(data, dict):
        for val in data.values():
            if not isinstance(val, str):
                continue
            text = _split_headed_text(val).get(key, "")
            if not _registry_blank(text):
                return text
    return ""


def _is_stringified_structure(text: str) -> bool:
    raw = str(text or "").strip()
    return (raw.startswith("{") and raw.endswith("}")) or (raw.startswith("[") and raw.endswith("]"))


def apply_registry_fields_from_llm(normalized: Dict[str, str], data: Any) -> Dict[str, str]:
    """Copy 剧情背景、故事线、时间节点、专业领域、场景与道具 onto the English form keys."""
    for key in _REGISTRY_KEYS:
        current = _field_text(normalized, key)
        if not _registry_blank(current) and not _is_stringified_structure(current):
            continue
        salvaged = _salvage_registry_key(data, key)
        if not _registry_blank(salvaged):
            normalized[key] = salvaged
    return normalized


def registry_fields_needing_fill(normalized: Dict[str, str]) -> List[str]:
    return [key for key in _REGISTRY_KEYS if _registry_blank(_field_text(normalized, key))]


def build_registry_fill_prompts(
    normalized: Dict[str, str],
    missing: List[str],
    *,
    creative_text: str,
    project_context: str,
) -> tuple[str, str]:
    labels = "、".join(_REGISTRY_LABELS[key] for key in missing)
    key_list = ", ".join(missing)
    system = (
        "You complete missing script-framework fields. "
        f"Output ONLY a JSON object whose keys are exactly: {key_list}. "
        "The first character must be '{' and the last character must be '}'. "
        "No markdown fences, no explanation. Every value is a non-empty string "
        "in the same language as the story fields. Do not invent a second plot. "
        "plot_background: `剧情背景: PB01｜句子｜手段=对话|动作｜禁提前=…`. "
        "The sentence is the public situation, the relationship history, and why this cannot wait. "
        "Not the world rule, and not the ending. "
        "story_lines: at least `线A=…｜线B=…` changing the same conflict, "
        "or `线数=1｜豁免依据=单一封闭空间` only when the whole story is one closed space. Not a scene list. "
        "time_nodes: at least `开篇｜式=绝对|相对｜季节=春|夏|秋|冬｜昼夜=日|夜｜气候=晴|阴|雨|雪|雾|风|霾｜说明`. "
        "A rebirth or return gets its own node. No episode ranges. "
        "professional_domains: `领域=｜触因=｜规程=｜错法=` for a procedure the plot actually needs, "
        "or exactly `领域=无｜依据=本剧选择不依赖行业规程`. No per-episode action. "
        "places_and_props: only spaces and objects the plot fails without. "
        "A space name is a place a person can stand in, such as 办公室、大堂、街道. "
        "One line each: `名 (EN)｜功能=｜准入=开放|受限` or `道具｜名｜功能=`. "
        "The function is a separate sentence. No furnishings or materials. "
        "Do not stack extra subjects into one place. If it cannot hold the next beat, register another place. "
        "Reuse and switching places are planned in the episode outline. "
        "Register every distinct place; one story may need several."
    )
    if _context_is_emotion_driven(project_context):
        system += " This story is emotion-driven. Do not add Save the Cat beat names."
    user = (
        f"The script framework left these fields empty: {labels}. Fill only these keys: {key_list}. "
        "Keep the same story.\n\n"
        f"{project_context}\n"
        f"Wild Creative Brainstorm:\n{creative_text}\n\n"
        "Structured fields already accepted:\n"
        f"{_classic_framework_story_context(normalized)}"
    )
    return system, user


async def ensure_registry_fields_filled(
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
    user_name: Optional[str] = None,
    project_id: Optional[int] = None,
) -> Dict[str, str]:
    """When the script framework omits the five registry fields, fill them before returning."""
    missing = registry_fields_needing_fill(normalized)
    if not missing:
        return normalized

    logger.warning(
        "[structure_creative_input] registry fields empty: %s",
        ",".join(missing),
    )
    attempts = max(1, int(max_attempts))
    from app.services.task_manager import abort_if_current_task_canceled

    for attempt in range(1, attempts + 1):
        abort_if_current_task_canceled()
        missing = registry_fields_needing_fill(normalized)
        if not missing:
            return normalized
        system, user = build_registry_fill_prompts(
            normalized,
            missing,
            creative_text=creative_text,
            project_context=project_context,
        )
        raw = await _run_structure_llm_call(
            db=db,
            user_id=user_id,
            project_global_info=project_global_info,
            req=req,
            sys_prompt=system,
            user_prompt=user,
            billing_item="structure_creative_input_registry",
            llm_context="structure_creative_input_registry",
            user_name=user_name,
            project_id=project_id,
        )
        data = await _normalize_llm_json_object_with_repair(
            raw,
            context="structure_creative_input_registry",
            llm_config=llm_config,
        )
        before = dict(normalized)
        apply_registry_fields_from_llm(normalized, data)
        filled_now = [
            key for key in missing
            if _registry_blank(_field_text(before, key)) and not _registry_blank(_field_text(normalized, key))
        ]
        if filled_now:
            logger.info(
                "[structure_creative_input] registry filled on attempt %s: %s",
                attempt,
                ",".join(filled_now),
            )
        else:
            logger.warning(
                "[structure_creative_input] registry still empty after fill attempt %s: %s",
                attempt,
                ",".join(missing),
            )

    still = registry_fields_needing_fill(normalized)
    if still:
        labels = "、".join(_REGISTRY_LABELS[key] for key in still)
        raise HTTPException(
            status_code=500,
            detail=f"剧本框架未回填：{labels}",
        )
    return normalized


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
    user_name: Optional[str] = None,
    project_id: Optional[int] = None,
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
        user_name=user_name,
        project_id=project_id,
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
