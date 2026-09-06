# -*- coding: utf-8 -*-
"""Programmatic derived-environment JSON + asset-library ingest (no LLM)."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.entity_token import strip_bilingual_name_aliases
from app.models.all_models import Entity, Episode, ScriptProgressPipelineNode
from app.services.soft_delete import _active_entity_clause, _active_episode_clause

logger = logging.getLogger("api_logger")

DERIVED_ENV_TAG_PATTERN = re.compile(r"\[DERIVED_ENV:([^\]]+)\]")
DERIVED_ENV_EXTRACT_BLOCK_PATTERN = re.compile(
    r"`?\[DERIVED_ENV_EXTRACT_START\]`?(.*?)`?\[DERIVED_ENV_EXTRACT_END\]`?",
    re.IGNORECASE | re.DOTALL,
)
DERIVED_ENV_LINE_PATTERN = re.compile(
    r"^\s*\[DERIVED_ENV\]\s*(.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
DEGREE_NAME_PATTERN = re.compile(
    r"^(\d+)\s*(?:度|deg(?:rees?)?|°)",
    re.IGNORECASE,
)
EVIDENCE_NAME_PATTERN = re.compile(
    r"(?:文戏|Beat|原文)\s*[:：]",
    re.IGNORECASE,
)
FRAMING_ENV_FIELD_PATTERN = re.compile(
    r"【(?:Beat景别构图方案|取景锁定|Beat主体定位|角色道具宫格分布图)】(.*?)(?:"
    r"【(?:景别构图综合|主体定位方案|取景锁定|Beat主体定位|角色道具宫格分布图|实体覆盖)】|"
    r"\[DERIVED_ENV_EXTRACT_START\]|\[BEAT_STREAM_START\])",
    re.IGNORECASE | re.DOTALL,
)
PLAN_ENV_NAME_PATTERN = re.compile(
    r"(?:ENV\s*[:=＝]\s*`?([^｜|\r\n`\[\]]+)`?|`(\d+\s*度[^`]+)`)",
    re.IGNORECASE,
)

GRID_BY_ANGLE = {
    0: "左上0度格",
    90: "右上90度格",
    180: "右下180度格",
    270: "左下270度格",
}

FIRST_CUT_PROMPT = (
    "所属主环境={main}。angle_key={main}|{angle}。"
    "请严格要求按对应主环境「{main}」四向拼图参考图，截取并放大其中对应的明确宫格位置（{grid}），"
    "不要重新描述画面细节，直接作为本镜头的最终画面。"
    "切割衍生环境时均按16:9固定比例，并保证高分辨率。只切割，不要改画。"
    "成稿须为单张完整镜头：禁止保留四向拼图的宫格分割线、宫格边框、格标/角标、十字拼缝或任何拼图装配痕迹。"
)
STATE_CUT_PROMPT = (
    "所属主环境={main}。angle_key={main}|{angle}。"
    "以已切割的同角衍生「{parent}」参考图为本镜头最终画面。16:9，高分辨率。"
    "不要改构图，不要重切宫格，不要描述未改实体。禁止画回宫格分割线、格标或拼缝。"
)
FIRST_CUT_NEGATIVE = (
    "people, person, human, dutch angle, tilted horizon, looking into a room corner, "
    "re-described furniture layout, mirrored room, four-panel grid lines, 2x2 collage seams, "
    "panel borders, quadrant labels, split-screen divider"
)
STATE_CUT_NEGATIVE = (
    "people, person, human, dutch angle, recropped four-panel, wrong camera angle, mirrored room, "
    "four-panel grid lines, 2x2 collage seams, panel borders, quadrant labels, split-screen divider"
)
SPECIAL_CUT_PROMPT = (
    "所属主环境={main}。angle_key={main}|{angle}。"
    "以对应主环境「{main}」四向拼图参考图的{grid}为空间与实体基准，继承该格陈设与材质，禁止另造房间。"
    "禁止只做平视宫格原样切割。"
    "必须按现场编排特别形态改画：特别表述={note}。"
    "成稿为单张16:9完整镜头，高分辨率；机位俯仰与透视服从特别表述；"
    "禁止保留四向拼图的宫格分割线、宫格边框、格标/角标、十字拼缝或任何拼图装配痕迹。"
    "不得另造未声明实体，不得把未改实体写成新陈设。"
)
SPECIAL_STATE_INJECT = "特别表述={note}。按该表述改俯仰或透视；仍以同角切割图为空间基准。"
DEFAULT_LOOK_UP_NOTE = "仰天:机位仰视，画面主体为该宫格已写天空/天花/屋顶，地面仅近端截断"
DEFAULT_WARP_NOTE = "变形:按现场编排特别表述改透视"
SOURCE_FLAG = "programmatic_derived_framing"
SPECIAL_KIND_PREFIXES = ("仰天", "屋顶", "变形")
LOOK_UP_SUFFIXES = {"仰天", "仰视", "屋顶"}
USAGE_MERGE_TOKENS = (
    "反打", "近景", "远景", "特写", "乙侧", "覆盖", "过肩", "空镜",
    "全景", "中景", "大远景", "大特写", "收紧", "再收", "再近", "再远",
    "再广", "再特写", "insert", "ews", "ws", "fs",
    "ms", "mcu", "cu", "ecu",
)
_EMPTY_FIELD_MARKERS = {"", "无", "n/a", "na", "none", "-"}
_INHERIT_FIELD_MARKERS = {"继承项目库", "继承", "同上", "见上", "略"}
_XOR_ANCHOR_PATTERN = re.compile(r"(?:^|[｜|\s])锚\s*=\s*([^｜|\r\n]+)")
_MAIN_ENV_BLOCK_PATTERN = re.compile(
    r"【主环境】\s*(?P<name>[^｜\|\r\n]+).*?(?=【主环境】|【未落清单】|【未落环境实体清单】|────【|$)",
    re.DOTALL,
)
_DEGREE_SLOT_PATTERN = re.compile(
    r"(?:^|[｜|\s;；:：])(?P<angle>0|90|180|270)\s*度(?!轴)\s*[=：]\s*",
)
_DEGREE_SLOT_STOP = re.compile(
    r"[｜|]\s*(?:(?:0|90|180|270)\s*度(?!轴)\s*[=：]|中心\s*[=：]|固定清单|"
    r"0度轴|地面\s*[=：]|空中\s*[=：]|屋顶\s*[=：]|天花\s*[=：]|背景微动件|活动空间)"
)
_SKY_SLOT_PATTERN = re.compile(
    r"(?:空中|屋顶|天花)\s*[=：]\s*([^｜\|\r\n]+)",
)
_ANGLE_CONTRACT_KEYS = {
    "扇型", "开闭", "开向", "门轴", "把手", "通行扇", "材质", "可见面",
    "所属楼层", "左扇开闭", "右扇开闭", "门轴世界", "左扇", "右扇",
}
_TYPED_SUBJECT_PATTERN = re.compile(r"(?:CHAR|PROP)\s*:\s*|\[@", re.IGNORECASE)
_CHAR_TOKEN_NAME_PATTERN = re.compile(
    r"CHAR\s*:\s*\[\s*@?\s*([^\]\r\n]+)\s*\]",
    re.IGNORECASE,
)
_PROP_TOKEN_NAME_PATTERN = re.compile(
    r"PROP\s*:\s*\[\s*([^\]\r\n]+)\s*\]",
    re.IGNORECASE,
)


def _clean(value: Any) -> str:
    return str(value or "").strip().strip("`\"'“”‘’[]")


def collect_subject_names_from_text(text: str) -> Set[str]:
    """CHAR / PROP display names that must never enter derived-env anchors."""
    names: Set[str] = set()
    blob = str(text or "")
    for match in _CHAR_TOKEN_NAME_PATTERN.finditer(blob):
        name = _clean(match.group(1))
        if name:
            names.add(name)
    for match in _PROP_TOKEN_NAME_PATTERN.finditer(blob):
        name = _clean(match.group(1))
        if name:
            names.add(name)
    return names


def _is_env_fixture_name(name: str, forbidden: Optional[Set[str]] = None) -> bool:
    text = _clean(name)
    if not text or text.lower() in _EMPTY_FIELD_MARKERS:
        return False
    if _TYPED_SUBJECT_PATTERN.search(text):
        return False
    for bad in forbidden or ():
        if bad and len(bad) >= 2 and bad in text:
            return False
    return True


def _anchor_slot(value: Any, forbidden: Optional[Set[str]] = None) -> str:
    text = _clean(value)
    if text.lower() in _EMPTY_FIELD_MARKERS:
        return ""
    return text if _is_env_fixture_name(text, forbidden) else ""


def _split_named_objects(*values: Any, forbidden: Optional[Set[str]] = None) -> List[str]:
    names: List[str] = []
    seen: Set[str] = set()
    for raw in values:
        text = _clean(raw)
        if not text or text.lower() in _EMPTY_FIELD_MARKERS:
            continue
        for part in re.split(r"[,，、+/＋]|以及|和", text):
            name = _clean(part)
            if not name or name.lower() in _EMPTY_FIELD_MARKERS:
                continue
            if not _is_env_fixture_name(name, forbidden):
                continue
            if name not in seen:
                seen.add(name)
                names.append(name)
    return names


def collect_reference_objects_from_text(
    text: str,
    forbidden: Optional[Set[str]] = None,
) -> List[str]:
    """Named XOR 参照物 (`锚=`) from framing / 主体定位; fixtures only."""
    blob = str(text or "")
    blocked = set(forbidden or ()) | collect_subject_names_from_text(blob)
    names: List[str] = []
    seen: Set[str] = set()
    for match in _XOR_ANCHOR_PATTERN.finditer(blob):
        for name in _split_named_objects(match.group(1), forbidden=blocked):
            if name not in seen:
                seen.add(name)
                names.append(name)
    return names


def _subjects_from_angle_value(value: Any) -> str:
    """Keep named fixtures from a 四向 slot; drop 开闭/门轴 contracts. Never '无'."""
    text = _clean(value)
    if not text or text.lower() in _EMPTY_FIELD_MARKERS:
        return ""
    if text in _INHERIT_FIELD_MARKERS:
        return ""
    kept: List[str] = []
    for part in re.split(r"[｜|]", text):
        piece = _clean(part)
        if not piece or piece.lower() in _EMPTY_FIELD_MARKERS:
            continue
        if piece in _INHERIT_FIELD_MARKERS:
            continue
        if "=" in piece:
            key = _clean(piece.split("=", 1)[0])
            if (
                key in _ANGLE_CONTRACT_KEYS
                or key.endswith("开闭")
                or key.endswith("门轴")
                or key.endswith("把手")
            ):
                continue
        kept.append(piece)
    return "、".join(kept)


def parse_main_environment_angle_subjects(text: str) -> Dict[str, Dict[str, str]]:
    """主环境名 → {0/90/180/270/空中} 该向已点名主体（逐字，不含合同键）。"""
    source = str(text or "")
    result: Dict[str, Dict[str, str]] = {}
    for match in _MAIN_ENV_BLOCK_PATTERN.finditer(source):
        name = _clean(match.group("name"))
        body = str(match.group(0) or "")
        if not name:
            continue
        slots: Dict[str, str] = {}
        for slot_match in _DEGREE_SLOT_PATTERN.finditer(body):
            try:
                angle = int(slot_match.group("angle"))
            except (TypeError, ValueError):
                continue
            raw = body[slot_match.end():]
            stop = _DEGREE_SLOT_STOP.search("｜" + raw)
            chunk = raw[: stop.start() - 1] if stop else raw
            subjects = _subjects_from_angle_value(chunk.split("\n", 1)[0])
            if subjects:
                slots[str(angle)] = subjects
        sky_match = _SKY_SLOT_PATTERN.search(body)
        if sky_match:
            sky = _subjects_from_angle_value(sky_match.group(1))
            if sky:
                slots["空中"] = sky
        if slots:
            result[name] = slots
    return result


def derived_frame_anchors_from_main(
    main: str,
    angle: int,
    mains: Optional[Dict[str, Dict[str, str]]] = None,
    *,
    look_up: bool = False,
) -> Dict[str, str]:
    """Copy 背景/画左/画右/画外 from the matching main-env sector. No invention, no 无."""
    sectors = (mains or {}).get(_clean(main)) or {}
    if not sectors:
        return {}
    resolved = int(angle) if angle in GRID_BY_ANGLE else 0
    background = ""
    if look_up and sectors.get("空中"):
        background = sectors["空中"]
    else:
        background = sectors.get(str(resolved), "")
    return {
        "background": background,
        "frame_left": sectors.get(str((resolved + 270) % 360), ""),
        "frame_right": sectors.get(str((resolved + 90) % 360), ""),
        "offscreen": sectors.get(str((resolved + 180) % 360), ""),
    }


_OFFSCREEN_MARK = "（不可见）"


def _strip_offscreen_mark(value: Any) -> str:
    text = _clean(value)
    for mark in ("（不可见）", "(不可见)", "｜可见=否", "|可见=否"):
        text = text.replace(mark, "")
    return _clean(text)


def format_offscreen_anchor(value: Any, forbidden: Optional[Set[str]] = None) -> str:
    text = _anchor_slot(_strip_offscreen_mark(value), forbidden)
    if not text:
        return ""
    if "不可见" in text:
        return text
    return f"{text}{_OFFSCREEN_MARK}"


def format_derived_anchor_description(
    *,
    background: str = "",
    frame_left: str = "",
    frame_right: str = "",
    offscreen: str = "",
    references: Optional[Sequence[str]] = None,
    forbidden: Optional[Set[str]] = None,
) -> str:
    """Asset Anchor Description: 背景 / 画左 / 画右 / 画外（不可见）. Never 无."""
    del references
    blob = "｜".join(
        [
            str(background or ""),
            str(frame_left or ""),
            str(frame_right or ""),
            str(offscreen or ""),
        ]
    )
    blocked = set(forbidden or ()) | collect_subject_names_from_text(blob)
    parts: List[str] = []
    bg = _anchor_slot(background, blocked)
    left = _anchor_slot(frame_left, blocked)
    right = _anchor_slot(frame_right, blocked)
    off = format_offscreen_anchor(offscreen, blocked)
    if bg:
        parts.append(f"背景={bg}")
    if left:
        parts.append(f"画左={left}")
    if right:
        parts.append(f"画右={right}")
    if off:
        parts.append(f"画外={off}")
    return "｜".join(parts)


def _parse_field_line(raw: str) -> Dict[str, str]:
    fields: Dict[str, str] = {}
    for part in re.split(r"[｜|]", str(raw or "")):
        piece = part.strip()
        if not piece or "=" not in piece:
            continue
        key, value = piece.split("=", 1)
        fields[_clean(key)] = _clean(value)
    return fields


def _split_degree_prefix(name: str) -> Tuple[Optional[int], str]:
    text = _clean(name)
    match = DEGREE_NAME_PATTERN.match(text)
    if not match:
        return None, text
    try:
        angle = int(match.group(1))
    except (TypeError, ValueError):
        return None, text
    return angle, text[match.end():].strip()


def _angle_from_name(name: str) -> Optional[int]:
    angle, _ = _split_degree_prefix(name)
    return angle


def _is_evidence_or_beat_title(name: str) -> bool:
    return bool(EVIDENCE_NAME_PATTERN.search(_clean(name)))


def _strip_usage_comma_tail(name: str) -> str:
    text = _clean(name)
    if not text:
        return text
    head, *tail = re.split(r"[,，、]", text, maxsplit=1)
    if tail and _is_usage_suffix(tail[0]):
        return head.strip()
    return text


def _normalize_angle(value: Any, name: str = "") -> int:
    text = _clean(value)
    if text.isdigit():
        angle = int(text)
        if angle in GRID_BY_ANGLE:
            return angle
    named = _angle_from_name(name)
    if named in GRID_BY_ANGLE:
        return int(named)
    if named is not None:
        return int(named)
    return 0


def _main_from_name(name: str) -> str:
    angle, rest = _split_degree_prefix(name)
    text = _strip_usage_comma_tail(rest if angle is not None else _clean(name))
    text = strip_bilingual_name_aliases(text)
    if _is_evidence_or_beat_title(text):
        return ""
    if "_" in text:
        text = text.split("_", 1)[0].strip()
    return text


def _state_suffix(name: str, main_name: str) -> str:
    text = _clean(name)
    prefix = f"{_angle_from_name(text) if _angle_from_name(text) is not None else ''}度{main_name}"
    if text.startswith(prefix) and len(text) > len(prefix):
        rest = text[len(prefix):]
        return rest[1:] if rest.startswith("_") else rest.lstrip("_")
    if "_" in text:
        return text.rsplit("_", 1)[-1].strip()
    return ""


def _same_angle_parent(name: str, main_name: str, angle: int) -> str:
    return f"{int(angle)}度{main_name}"


def _row_looks_up(row: Dict[str, Any]) -> bool:
    name = _clean(row.get("name"))
    suffix = _state_suffix(name, _clean(row.get("main") or row.get("所属主环境")))
    kind = _clean(row.get("kind") or row.get("类型") or row.get("special_kind"))
    note = _clean(row.get("special_note") or row.get("特别表述"))
    return (
        suffix in LOOK_UP_SUFFIXES
        or kind in LOOK_UP_SUFFIXES
        or any(token in note for token in LOOK_UP_SUFFIXES)
    )


_TYPED_ENV_NAME_PATTERN = re.compile(
    r"^(?:ENV\s*:\s*)?\[([^\[\]]+)\]$",
    re.IGNORECASE,
)
_TYPED_ENV_NAME_IN_TEXT_PATTERN = re.compile(
    r"ENV\s*:\s*\[([^\[\]]+)\]",
    re.IGNORECASE,
)


def unwrap_typed_environment_name(name: str) -> str:
    text = str(name or "").strip()
    match = _TYPED_ENV_NAME_PATTERN.fullmatch(text)
    if match:
        return str(match.group(1) or "").strip()
    return text


def canonicalize_derived_environment_name(
    name: str,
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    """Merge same-direction usage/shot-size suffixes into `{N}度{主}`.

    Keep look-up specials as `{N}度{主}_仰天`, explicit warp as `_变形`,
    and marked state rows as `{N}度{主}_{状态}`.
    Drop Beat:/文戏:/原文: evidence titles that leaked into ENV names.
    """
    extra = extra or {}
    clean_name = strip_bilingual_name_aliases(unwrap_typed_environment_name(name))
    angle, rest = _split_degree_prefix(clean_name)
    main = strip_bilingual_name_aliases(_clean(extra.get("main") or extra.get("所属主环境")))
    if _is_evidence_or_beat_title(clean_name) or _is_evidence_or_beat_title(rest):
        if not main:
            return ""
        resolved_angle = angle if angle in GRID_BY_ANGLE else 0
        return f"{int(resolved_angle)}度{main}"
    if angle is None:
        return clean_name
    rest = _strip_usage_comma_tail(rest)
    clean_name = f"{int(angle)}度{rest}" if rest else f"{int(angle)}度"
    main = main or _main_from_name(clean_name)
    if not main:
        return clean_name
    suffix = _state_suffix(clean_name, main)
    kind = extra.get("kind") or extra.get("类型") or ""
    special_kind, _ = _parse_special_note(
        extra.get("special_note") or extra.get("特别表述")
    )
    state_delta = _clean(extra.get("state_delta") or extra.get("状态Delta"))
    if suffix in LOOK_UP_SUFFIXES or special_kind in {"仰天", "屋顶"}:
        return f"{int(angle)}度{main}_仰天"
    if suffix == "变形" or special_kind == "变形":
        return f"{int(angle)}度{main}_变形"
    row = {
        **extra,
        "name": clean_name,
        "main": main,
        "kind": kind,
        "state_delta": state_delta,
    }
    if suffix and (
        _is_state_row(row)
        or (state_delta and state_delta.lower() not in _EMPTY_FIELD_MARKERS)
    ):
        return f"{int(angle)}度{main}_{suffix}"
    if not suffix:
        return f"{int(angle)}度{main}"
    kind_text = _clean(kind).lower()
    if _is_usage_suffix(suffix) or kind_text in {"第一刀", "first_cut", "first-cut", "视角衍生"}:
        return f"{int(angle)}度{main}"
    return clean_name


def _is_usage_suffix(suffix: str) -> bool:
    text = _clean(suffix).lower()
    return any(token in text for token in USAGE_MERGE_TOKENS)


def _parse_special_note(raw: Any) -> Tuple[str, str]:
    """Return (kind, sentence). kind ∈ 仰天/屋顶/变形 or empty; sentence is the inject text."""
    text = _clean(raw)
    if text.lower() in _EMPTY_FIELD_MARKERS:
        return "", ""
    for prefix in SPECIAL_KIND_PREFIXES:
        for sep in (":", "："):
            if text.startswith(prefix + sep):
                body = text.split(sep, 1)[1].strip()
                return prefix, (f"{prefix}:{body}" if body else text)
    if any(token in text for token in ("荷兰", "倾斜", "扭曲", "变形", "dutch")):
        return "变形", text
    if any(token in text for token in ("屋顶", "天花", "梁架", "吊顶")):
        return "屋顶", text
    if any(token in text for token in ("仰天", "天空", "看天")):
        return "仰天", text
    return "", text


def _is_special_kind(kind: str) -> bool:
    text = _clean(kind).lower()
    return text in {"特别", "special", "仰天", "屋顶", "变形"}


def _is_special_row(item: Dict[str, Any]) -> bool:
    name = _clean(item.get("name"))
    main = _clean(item.get("main") or item.get("所属主环境"))
    suffix = _state_suffix(name, main)
    row_kind = _clean(item.get("kind") or item.get("类型") or item.get("special_kind"))
    special_kind, _ = _parse_special_note(item.get("special_note") or item.get("特别表述"))
    return (
        suffix in LOOK_UP_SUFFIXES
        or suffix == "变形"
        or _is_special_kind(row_kind)
        or special_kind in {"仰天", "屋顶", "变形"}
        or _row_looks_up(item)
    )


def _infer_special(item: Dict[str, Any], name: str = "", main: str = "") -> Tuple[str, str]:
    special_kind, special_note = _parse_special_note(
        item.get("special_note") or item.get("特别表述")
    )
    suffix = _state_suffix(
        name or _clean(item.get("name")),
        main or _clean(item.get("main") or item.get("所属主环境")),
    )
    if special_kind:
        return special_kind, _expand_special_note(special_kind, special_note)
    if suffix in LOOK_UP_SUFFIXES:
        return "仰天", _expand_special_note("仰天", special_note)
    if suffix == "变形":
        return "变形", _expand_special_note("变形", special_note)
    if _is_special_kind(item.get("kind") or item.get("类型") or ""):
        kind = "仰天" if suffix in LOOK_UP_SUFFIXES else (suffix or "仰天")
        return kind, _expand_special_note(kind, special_note or suffix)
    return "", special_note


def _expand_special_note(kind: str, note: str) -> str:
    text = _clean(note)
    if kind in {"仰天", "屋顶"} and text.lower() in {"", "仰天", "仰视", "屋顶"}:
        return DEFAULT_LOOK_UP_NOTE
    if kind == "变形" and text.lower() in {"", "变形"}:
        return DEFAULT_WARP_NOTE
    return text


def _is_state_row(item: Dict[str, Any]) -> bool:
    if _is_special_row(item):
        return False
    kind = _clean(item.get("kind") or item.get("类型")).lower()
    if _is_special_kind(kind):
        return False
    if kind in {"第一刀", "first_cut", "first-cut", "视角衍生"}:
        return False
    if kind in {"衍生的衍生", "state", "delta"}:
        return True
    parent = _clean(item.get("parent") or item.get("同角切割父"))
    if parent and parent not in {"无", "n/a", "none", "-"}:
        return True
    delta = _clean(item.get("state_delta") or item.get("状态Delta"))
    return bool(delta and delta not in {"无", "n/a", "none", "-"})


def parse_derived_env_extract_items(text: str) -> List[Dict[str, Any]]:
    """Parse [DERIVED_ENV:…] tags and the extract block from framing output."""
    source = str(text or "")
    by_name: Dict[str, Dict[str, Any]] = {}

    def _upsert(name: str, extra: Optional[Dict[str, Any]] = None) -> None:
        fields = extra or {}
        clean_name = canonicalize_derived_environment_name(name, fields)
        if not clean_name or not re.match(r"^\d+\s*度", clean_name):
            return
        row = by_name.get(clean_name) or {"name": clean_name}
        if extra:
            for key, value in extra.items():
                if _clean(value):
                    row[key] = value
        if not _clean(row.get("main") or row.get("所属主环境")):
            row["main"] = _main_from_name(clean_name)
        row["angle"] = _normalize_angle(row.get("angle") or row.get("view_angle_from_main"), clean_name)
        by_name[clean_name] = row

    for match in DERIVED_ENV_EXTRACT_BLOCK_PATTERN.finditer(source):
        block = str(match.group(1) or "")
        for line_match in DERIVED_ENV_LINE_PATTERN.finditer(block):
            fields = _parse_field_line(line_match.group(1))
            name = fields.get("名称") or fields.get("name") or ""
            _upsert(
                name,
                {
                    "main": fields.get("所属主环境") or fields.get("main"),
                    "angle": fields.get("view_angle_from_main") or fields.get("angle"),
                    "kind": fields.get("类型") or fields.get("kind"),
                    "trigger": fields.get("触发") or fields.get("trigger"),
                    "lens_profile": fields.get("lens_profile"),
                    "axis_crossing": fields.get("axis_crossing"),
                    "spatial_axis": fields.get("spatial_axis"),
                    "parent": fields.get("同角切割父") or fields.get("parent"),
                    "state_delta": fields.get("状态Delta") or fields.get("state_delta"),
                    "special_note": fields.get("特别表述") or fields.get("special_note"),
                    "gen_prompt": fields.get("生成提示") or fields.get("gen_prompt"),
                    "empty_view_delta": fields.get("empty_view_delta") or fields.get("空镜差值"),
                    "visible_bound": fields.get("可见边界") or fields.get("visible_bound"),
                    "background": fields.get("背景") or fields.get("background"),
                    "frame_left": fields.get("画左") or fields.get("frame_left"),
                    "frame_right": fields.get("画右") or fields.get("frame_right"),
                    "offscreen": _strip_offscreen_mark(
                        fields.get("画外") or fields.get("offscreen")
                    ),
                    "references": fields.get("参照物") or fields.get("references"),
                },
            )

    for match in DERIVED_ENV_TAG_PATTERN.finditer(source):
        _upsert(match.group(1))

    for plan_match in FRAMING_ENV_FIELD_PATTERN.finditer(source):
        for env_match in PLAN_ENV_NAME_PATTERN.finditer(plan_match.group(1) or ""):
            _upsert(env_match.group(1) or env_match.group(2))

    forbidden = collect_subject_names_from_text(source)
    mains = parse_main_environment_angle_subjects(source)
    for row in by_name.values():
        main = _clean(row.get("main") or row.get("所属主环境")) or _main_from_name(row.get("name") or "")
        angle = _normalize_angle(row.get("angle") or row.get("view_angle_from_main"), row.get("name") or "")
        copied = derived_frame_anchors_from_main(
            main,
            angle,
            mains,
            look_up=_row_looks_up(row),
        )
        if copied:
            if copied.get("background"):
                row["background"] = copied["background"]
            if copied.get("frame_left"):
                row["frame_left"] = copied["frame_left"]
            if copied.get("frame_right"):
                row["frame_right"] = copied["frame_right"]
            if copied.get("offscreen"):
                row["offscreen"] = copied["offscreen"]
            row["references"] = ""
        row["background"] = _anchor_slot(row.get("background"), forbidden)
        row["frame_left"] = _anchor_slot(row.get("frame_left"), forbidden)
        row["frame_right"] = _anchor_slot(row.get("frame_right"), forbidden)
        row["offscreen"] = _strip_offscreen_mark(_anchor_slot(row.get("offscreen"), forbidden))
        if "references" in row:
            row["references"] = ""

    return list(by_name.values())


def build_derived_environment_item(item: Dict[str, Any]) -> Dict[str, Any]:
    raw_item = dict(item or {})
    main = _clean(raw_item.get("main") or raw_item.get("所属主环境"))
    name = canonicalize_derived_environment_name(raw_item.get("name"), {**raw_item, "main": main})
    main = main or _main_from_name(name)
    angle = _normalize_angle(item.get("angle") or item.get("view_angle_from_main"), name)
    grid = GRID_BY_ANGLE.get(angle, "左上0度格")
    resolved = {**raw_item, "name": name, "main": main, "angle": angle}
    is_state = _is_state_row(resolved)
    parent = _clean(item.get("parent") or item.get("同角切割父"))
    if parent in {"无", "n/a", "none", "-", ""}:
        parent = _same_angle_parent(name, main, angle) if is_state else ""
    if is_state and parent == name:
        parent = _same_angle_parent(name, main, angle)
    lens = _clean(item.get("lens_profile")) or ("Wide" if angle == 0 else "Standard")
    axis_crossing = _clean(item.get("axis_crossing")) or "None"
    spatial_axis = _clean(item.get("spatial_axis")) or "继承主环境"
    trigger = _clean(item.get("trigger") or item.get("触发")) or ("Master" if angle == 0 else "复用/剧情覆盖")
    delta = _clean(item.get("state_delta") or item.get("状态Delta"))
    if delta.lower() in _EMPTY_FIELD_MARKERS:
        delta = ""
    special_kind, special_note = _infer_special(resolved, name, main)
    suffix = _state_suffix(name, main)
    name_en = f"{angle}deg {main}" + (f" {suffix}" if suffix else "")
    background = _clean(item.get("background") or item.get("背景"))
    frame_left = _clean(item.get("frame_left") or item.get("画左"))
    frame_right = _clean(item.get("frame_right") or item.get("画右"))
    offscreen = _strip_offscreen_mark(item.get("offscreen") or item.get("画外"))
    forbidden = collect_subject_names_from_text(
        "｜".join(
            [
                background,
                frame_left,
                frame_right,
                offscreen,
                str(item.get("references") or item.get("参照物") or ""),
                str(item.get("name") or ""),
            ]
        )
    )
    background = _anchor_slot(background, forbidden)
    frame_left = _anchor_slot(frame_left, forbidden)
    frame_right = _anchor_slot(frame_right, forbidden)
    offscreen = _strip_offscreen_mark(_anchor_slot(offscreen, forbidden))
    references = _split_named_objects(
        item.get("references") or item.get("参照物"),
        forbidden=forbidden,
    )
    anchor = format_derived_anchor_description(
        background=background,
        frame_left=frame_left,
        frame_right=frame_right,
        offscreen=offscreen,
        references=references,
        forbidden=forbidden,
    )
    if is_state:
        prompt = STATE_CUT_PROMPT.format(main=main, angle=angle, parent=parent or _same_angle_parent(name, main, angle))
        if delta:
            prompt = f"{prompt}在此画面基础上叠加：{delta}。"
        if special_note:
            prompt = f"{prompt}{SPECIAL_STATE_INJECT.format(note=special_note)}"
        logic = (
            f"spatial_axis={spatial_axis}；lens_profile={lens}；axis_crossing={axis_crossing}。"
            f"所属主环境={main}。angle_key={main}|{angle}。同角切割父={parent or _same_angle_parent(name, main, angle)}。"
            f"状态Delta={delta or '无'}。形状Delta=无。未改实体=不写。触发={trigger}。"
        )
        if special_note:
            logic = f"{logic}特别表述={special_note}。"
        deps = [f"ENV:[{parent or _same_angle_parent(name, main, angle)}]"]
        negative = STATE_CUT_NEGATIVE
        atmosphere = f"Same {angle}deg crop with state delta"
        visual_params = f"{lens}/Derived/State"
    elif special_note:
        prompt = SPECIAL_CUT_PROMPT.format(main=main, angle=angle, grid=grid, note=special_note)
        empty_delta = _clean(resolved.get("empty_view_delta") or resolved.get("空镜差值"))
        if empty_delta.lower() not in _EMPTY_FIELD_MARKERS:
            prompt = f"{prompt}空镜差值={empty_delta}。"
        if special_kind in {"仰天", "屋顶"} and background:
            prompt = f"{prompt}画面主体={background}。"
        logic = (
            f"spatial_axis={spatial_axis}；lens_profile={lens}；axis_crossing={axis_crossing}。"
            f"所属主环境={main}。angle_key={main}|{angle}。截取宫格={grid}。触发={trigger}。特别表述={special_note}。"
        )
        deps = [f"ENV:[{main}]"]
        negative = FIRST_CUT_NEGATIVE
        atmosphere = f"Special {special_kind or 'plate'} from {grid}"
        visual_params = f"{lens}/Derived/Special/{special_kind or angle}"
    else:
        prompt = FIRST_CUT_PROMPT.format(main=main, angle=angle, grid=grid)
        logic = (
            f"spatial_axis={spatial_axis}；lens_profile={lens}；axis_crossing={axis_crossing}。"
            f"所属主环境={main}。截取宫格={grid}。触发={trigger}。"
        )
        deps = [f"ENV:[{main}]"]
        negative = FIRST_CUT_NEGATIVE
        atmosphere = f"{'Master' if angle == 0 else 'Angle'} empty plate crop"
        visual_params = f"{lens}/Derived/{angle}"
    gen_hint = _clean(item.get("gen_prompt") or item.get("生成提示"))
    if gen_hint and gen_hint.lower() not in _EMPTY_FIELD_MARKERS and gen_hint not in prompt:
        prompt = f"{prompt}生成提示={gen_hint}。"
    if special_kind == "变形":
        negative = negative.replace("dutch angle, tilted horizon, ", "").replace("dutch angle, ", "")
    return {
        "name": name,
        "name_en": name_en,
        "base_name_en": main,
        "atmosphere": atmosphere,
        "visual_params": visual_params,
        "description_cn": "",
        "generation_prompt_cn": prompt,
        "generation_prompt_en": "",
        "negative_prompt_en": negative,
        "anchor_description": anchor,
        "visual_dependencies": deps,
        "dependency_strategy": {
            "type": "Type A",
            "logic": logic,
        },
        "custom_attributes": {
            "source": SOURCE_FLAG,
            "main_environment": main,
            "view_angle_from_main": angle,
            "grid_cell": grid,
            "derived_kind": (
                "state" if is_state else ("special" if special_note else "first_cut")
            ),
            "special_kind": special_kind,
            "special_note": special_note,
            "negative_prompt_en": negative,
            "background": background,
            "frame_left": frame_left,
            "frame_right": frame_right,
            "offscreen": offscreen,
            "references": "、".join(references),
        },
    }


def group_derived_environment_jsons(items: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One JSON string per main environment, environments[] = derived rows only."""
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for item in items or []:
        payload = build_derived_environment_item(item)
        main = _clean(payload.get("base_name_en")) or _clean((payload.get("custom_attributes") or {}).get("main_environment"))
        if not main or not payload.get("name"):
            continue
        bucket = grouped.setdefault(main, [])
        if any(_clean(existing.get("name")) == _clean(payload.get("name")) for existing in bucket):
            continue
        bucket.append(payload)
    result: List[Dict[str, Any]] = []
    for main, rows in grouped.items():
        rows.sort(key=lambda row: (
            int((row.get("custom_attributes") or {}).get("view_angle_from_main") or 0),
            _clean(row.get("name")),
        ))
        body = {"environments": rows}
        result.append(
            {
                "main_environment": main,
                "count": len(rows),
                "json": json.dumps(body, ensure_ascii=False, indent=2),
                "payload": body,
            }
        )
    return result


def collect_derived_environment_jsons(text: str) -> List[Dict[str, Any]]:
    return group_derived_environment_jsons(parse_derived_env_extract_items(text))


def _angle_text(value: Any) -> str:
    if value is None or value == "":
        return ""
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return str(value).strip()


def format_derived_env_info_line(
    name: str,
    *,
    main: str = "",
    background: str = "",
    frame_left: str = "",
    frame_right: str = "",
    offscreen: str = "",
    view_angle: Any = None,
) -> str:
    """One derived-ENV row: this camera's 背景/画左/画右 + 画外（不可见）."""
    parts = [f"ENV:[{_clean(name)}]"]
    main_name = _clean(main)
    if main_name:
        parts.append(f"所属主环境=ENV:[{main_name}]")
    angle = _angle_text(view_angle)
    if angle:
        parts.append(f"view_angle_from_main={angle}")
    if _clean(background):
        parts.append(f"背景={_clean(background)}")
    if _clean(frame_left):
        parts.append(f"画左={_clean(frame_left)}")
    if _clean(frame_right):
        parts.append(f"画右={_clean(frame_right)}")
    off = format_offscreen_anchor(offscreen)
    if off:
        parts.append(f"画外={off}")
    return "｜".join(parts)


def derived_env_info_fields_from_mapping(item: Dict[str, Any]) -> Dict[str, Any]:
    view_angle = item.get("view_angle_from_main")
    if view_angle is None:
        view_angle = item.get("angle")
    if view_angle is None:
        view_angle = item.get("view_angle")
    return {
        "name": _clean(item.get("name")),
        "main": _clean(item.get("main") or item.get("所属主环境") or item.get("main_environment")),
        "background": _clean(item.get("background") or item.get("背景")),
        "frame_left": _clean(item.get("frame_left") or item.get("画左")),
        "frame_right": _clean(item.get("frame_right") or item.get("画右")),
        "offscreen": _strip_offscreen_mark(item.get("offscreen") or item.get("画外")),
        "view_angle": view_angle,
    }


def derived_env_info_fields_from_entity(ent: Any, *, fallback_main: str = "") -> Dict[str, Any]:
    attrs = getattr(ent, "custom_attributes", None)
    if not isinstance(attrs, dict):
        attrs = {}
    return {
        "name": _clean(getattr(ent, "name", None) or getattr(ent, "name_en", None)),
        "main": _clean(
            attrs.get("main_environment")
            or attrs.get("所属主环境")
            or getattr(ent, "base_name_en", None)
            or fallback_main
        ),
        "background": _clean(attrs.get("background") or attrs.get("背景")),
        "frame_left": _clean(attrs.get("frame_left") or attrs.get("画左")),
        "frame_right": _clean(attrs.get("frame_right") or attrs.get("画右")),
        "offscreen": _strip_offscreen_mark(attrs.get("offscreen") or attrs.get("画外")),
        "view_angle": attrs.get("view_angle_from_main"),
    }


def build_derived_env_info_block(
    rows: Sequence[Dict[str, Any]],
    *,
    heading: str = "【衍生环境信息】",
) -> str:
    lines: List[str] = []
    seen: Set[str] = set()
    for row in rows:
        fields = derived_env_info_fields_from_mapping(row)
        name = _clean(fields.get("name"))
        if not name or name in seen:
            continue
        main = _clean(fields.get("main"))
        background = _clean(fields.get("background"))
        frame_left = _clean(fields.get("frame_left"))
        frame_right = _clean(fields.get("frame_right"))
        offscreen = _clean(fields.get("offscreen"))
        if not (main or background or frame_left or frame_right or offscreen):
            continue
        seen.add(name)
        lines.append(
            format_derived_env_info_line(
                name,
                main=main,
                background=background,
                frame_left=frame_left,
                frame_right=frame_right,
                offscreen=offscreen,
                view_angle=fields.get("view_angle"),
            )
        )
    if not lines:
        return ""
    return (
        f"{heading}\n"
        "每行=该镜头下的画左/画右对应实体（切角须改查新 ENV，左右会换）。"
        "画外=镜头后对向主体，明确不可见；选角与建置/入戏禁止点名画外主体。"
        "建置仍按相对/绝对/封闭写，只把「画左」「画右」换成该行可见实体，禁止把画外实体写入画面句。"
        "宫格参照=画外时，落位改写为离镜头近处中间主体（优先四周=中）的某侧旁。\n"
        + "\n".join(lines)
    )


def build_derived_env_frame_anchor_injection(text: str) -> str:
    """Compact derived-ENV table for staging: 所属主环境 + 背景/画左/画右 + 画外（不可见）."""
    return build_derived_env_info_block(
        parse_derived_env_extract_items(text),
        heading="【衍生环境画幅锚】",
    )


def build_derived_env_info_injection_from_entities(
    entities: Sequence[Any],
    *,
    main_by_name: Optional[Dict[str, str]] = None,
    heading: str = "【衍生环境信息】",
) -> str:
    """Same contract as framing extract, built from persisted ENV entities."""
    rows: List[Dict[str, Any]] = []
    for ent in entities:
        name = _clean(getattr(ent, "name", None) or getattr(ent, "name_en", None))
        fallback = ""
        if main_by_name and name:
            fallback = _clean(main_by_name.get(name))
        rows.append(derived_env_info_fields_from_entity(ent, fallback_main=fallback))
    return build_derived_env_info_block(rows, heading=heading)


_DERIVED_ENV_SECTION_PATTERN = re.compile(
    r"(?:\r?\n)?────【衍生环境】────(?P<body>.*?)(?=(?:\r?\n\[ENV_BLOCK_END)|(?:\r?\n────【)|$)",
    re.DOTALL,
)
_DERIVED_ENV_BACKTICK_NAME_PATTERN = re.compile(r"`([^`\n]+)`")
_DERIVED_ENV_DEGREE_LINE_PATTERN = re.compile(
    r"^\s*[-*]\s*(\d+\s*度[^\s`：:｜|,，]+)",
    re.MULTILINE,
)
_MAIN_ENV_LINE_PATTERN = re.compile(r"(?m)^[ \t]*【主环境】[ \t]*(.+?)\s*$")
_OWNING_MAIN_ENV_PATTERN = re.compile(r"所属主环境\s*=\s*([^\s｜|\r\n]+)")
_DERIVED_ENV_NAME_PATTERN = re.compile(r"^\d+\s*度")
_SCENE_DERIVED_ENV_HEADER_PATTERN = re.compile(
    r"【本场衍生环境名】\s*([^\r\n]+)"
)
_DERIVED_ENV_SIGNAL_PATTERN = re.compile(
    r"\[DERIVED_ENV|【本场衍生环境名】|────【衍生环境】────",
    re.IGNORECASE,
)


def _normalize_env_name_key(value: str) -> str:
    return re.sub(r"[\s_*`'\"“”‘’]+", "", str(value or "")).lower()


def _main_environment_name_keys(text: str) -> Set[str]:
    keys: Set[str] = set()
    for match in _MAIN_ENV_LINE_PATTERN.finditer(text):
        cleaned = _clean(re.split(r"[｜|]", match.group(1) or "", maxsplit=1)[0])
        key = _normalize_env_name_key(cleaned)
        if key:
            keys.add(key)
    for match in _OWNING_MAIN_ENV_PATTERN.finditer(text):
        key = _normalize_env_name_key(match.group(1) or "")
        if key:
            keys.add(key)
    return keys


def extract_derived_environment_names_from_scene_text(scene_text: str) -> str:
    """Collect this scene's derived ENV names only (never bare main-environment names).

    Sources: 【本场衍生环境名】 / [DERIVED_ENV:…] / extract block / 【衍生环境】 bullets.
    Names are joined with Chinese comma `，`.
    """
    text = str(scene_text or "")
    if not text.strip():
        return ""

    names: List[str] = []
    seen: Set[str] = set()
    main_keys = _main_environment_name_keys(text)

    def _add(raw_name: str) -> None:
        cleaned = unwrap_typed_environment_name(raw_name)
        cleaned = re.split(r"[｜|]", cleaned, maxsplit=1)[0].strip()
        cleaned = re.sub(r"^(名称|环境名|环境|ENV)\s*[=：:]\s*", "", cleaned).strip()
        cleaned = strip_bilingual_name_aliases(unwrap_typed_environment_name(cleaned))
        if not cleaned or cleaned.startswith("─") or cleaned.startswith("-"):
            return
        if not _DERIVED_ENV_NAME_PATTERN.match(cleaned):
            return
        cleaned = canonicalize_derived_environment_name(cleaned)
        normalized = _normalize_env_name_key(cleaned)
        if normalized in {"none", "null", "nil", "n/a", "na", "无", "空"}:
            return
        if normalized in main_keys:
            return
        if not cleaned or normalized in seen:
            return
        seen.add(normalized)
        names.append(cleaned)

    for item in parse_derived_env_extract_items(text):
        _add(item.get("name"))

    header_match = _SCENE_DERIVED_ENV_HEADER_PATTERN.search(text)
    if header_match:
        for part in re.split(r"[,，;；、/／]+", header_match.group(1) or ""):
            _add(part)

    section = _DERIVED_ENV_SECTION_PATTERN.search(text)
    if section:
        body = str(section.group("body") or "")
        for match in _DERIVED_ENV_BACKTICK_NAME_PATTERN.finditer(body):
            _add(match.group(1))
        for match in _DERIVED_ENV_DEGREE_LINE_PATTERN.finditer(body):
            _add(match.group(1))

    return "，".join(names)


_DERIVED_NAME_TOKEN_PATTERN = re.compile(r"\d+\s*度[^\s`：:｜|,，\[\]\r\n]+")
_ENGLISH_BEAT_ENV_TOKEN_PATTERN = re.compile(
    r"\d+\s*deg(?:rees?)?\s+(?:Beat|文戏|原文)\s*[:：][^`｜|\r\n\[\]]+",
    re.IGNORECASE,
)
_CURRENT_ENV_FIELD_PATTERN = re.compile(r"(当前环境=)([^｜|\r\n]+)")
_PLAN_ENV_FIELD_PATTERN = re.compile(
    r"(?<!选择证据=)(?<!选择证据＝)(\bENV\s*[:：=＝]\s*)([^｜|\r\n`\[\]]+)"
)


_MAIN_ENV_INLINE_PATTERN = re.compile(r"【主环境】[ \t]*([^｜|\r\n─]+)")


def _scene_main_names(text: str) -> List[str]:
    names: List[str] = []
    seen: Set[str] = set()
    for pattern in (_MAIN_ENV_LINE_PATTERN, _MAIN_ENV_INLINE_PATTERN):
        for match in pattern.finditer(text):
            cleaned = _clean(re.split(r"[｜|]", match.group(1) or "", maxsplit=1)[0])
            key = _normalize_env_name_key(cleaned)
            if cleaned and key not in seen:
                seen.add(key)
                names.append(cleaned)
    for match in _OWNING_MAIN_ENV_PATTERN.finditer(text):
        cleaned = _clean(match.group(1) or "")
        key = _normalize_env_name_key(cleaned)
        if cleaned and key not in seen:
            seen.add(key)
            names.append(cleaned)
    return names


def rewrite_merged_derived_environment_names(text: str) -> str:
    """Rewrite usage/shot-size aliases and leaked Beat: titles to `{N}度{主}`."""
    source = str(text or "")
    if not source.strip():
        return source
    default_main = (_scene_main_names(source) or [""])[0]

    def _canon(raw: str, line_main: str = "") -> str:
        extra = {"main": line_main or default_main}
        canonical = canonicalize_derived_environment_name(raw, extra)
        if canonical:
            return canonical
        angle, rest = _split_degree_prefix(raw)
        if (line_main or default_main) and (
            _is_evidence_or_beat_title(raw) or _is_evidence_or_beat_title(rest)
        ):
            resolved = angle if angle in GRID_BY_ANGLE else 0
            return f"{int(resolved)}度{line_main or default_main}"
        return raw

    def _repl_extract_line(match: re.Match) -> str:
        raw_line = match.group(0)
        fields = _parse_field_line(match.group(1))
        name = fields.get("名称") or fields.get("name") or ""
        main = fields.get("所属主环境") or fields.get("main") or default_main
        canon = _canon(name, main)
        if name and canon and canon != name:
            return raw_line.replace(name, canon, 1)
        return raw_line

    source = DERIVED_ENV_LINE_PATTERN.sub(_repl_extract_line, source)
    source = DERIVED_ENV_TAG_PATTERN.sub(
        lambda match: f"[DERIVED_ENV:{_canon(match.group(1))}]",
        source,
    )
    def _repl_current_env(match: re.Match) -> str:
        raw = str(match.group(2) or "").strip()
        wrapped = bool(re.match(r"ENV\s*:\s*\[", raw, re.IGNORECASE))
        canon = _canon(raw)
        if wrapped and canon and not re.match(r"ENV\s*:", canon, re.IGNORECASE):
            return f"{match.group(1)}ENV:[{canon}]"
        return f"{match.group(1)}{canon}"

    source = _CURRENT_ENV_FIELD_PATTERN.sub(_repl_current_env, source)
    source = _PLAN_ENV_FIELD_PATTERN.sub(
        lambda match: f"{match.group(1)}{_canon(match.group(2))}",
        source,
    )
    source = _TYPED_ENV_NAME_IN_TEXT_PATTERN.sub(
        lambda match: f"ENV:[{_canon(match.group(1))}]",
        source,
    )

    replacements: Dict[str, str] = {}
    for pattern in (_DERIVED_NAME_TOKEN_PATTERN, _ENGLISH_BEAT_ENV_TOKEN_PATTERN):
        for match in pattern.finditer(source):
            raw = _clean(match.group(0))
            if not raw:
                continue
            canonical = _canon(raw)
            if canonical and canonical != raw:
                replacements[raw] = canonical
    for raw in sorted(replacements, key=len, reverse=True):
        source = source.replace(raw, replacements[raw])
    return source


def _upsert_environment_entity(
    db: Session,
    *,
    project_id: int,
    episode_id: int,
    payload: Dict[str, Any],
    force_overwrite: bool = False,
) -> Tuple[str, int]:
    name = _clean(payload.get("name"))
    name_en = _clean(payload.get("name_en"))
    candidates = {value.lower() for value in (name, name_en) if value}
    if not candidates:
        return "skipped", 0
    name_expr = func.lower(func.trim(func.coalesce(Entity.name, "")))
    name_en_expr = func.lower(func.trim(func.coalesce(Entity.name_en, "")))
    existing = (
        db.query(Entity)
        .filter(
            Entity.project_id == int(project_id),
            Entity.episode_id == int(episode_id),
            _active_entity_clause(),
            func.lower(func.trim(func.coalesce(Entity.type, ""))) == "environment",
            or_(name_expr.in_(candidates), name_en_expr.in_(candidates)),
        )
        .first()
    )
    attrs = dict(payload.get("custom_attributes") or {})
    prompt = _clean(payload.get("generation_prompt_cn"))
    deps = list(payload.get("visual_dependencies") or [])
    strategy = payload.get("dependency_strategy") or {}
    if existing is None:
        entity = Entity(
            project_id=int(project_id),
            episode_id=int(episode_id),
            name=name,
            type="environment",
            description=prompt,
            generation_prompt_cn=prompt,
            generation_prompt_en=_clean(payload.get("generation_prompt_en")),
            anchor_description=_clean(payload.get("anchor_description")),
            name_en=name_en,
            base_name_en=_clean(payload.get("base_name_en")),
            atmosphere=_clean(payload.get("atmosphere")),
            visual_params=_clean(payload.get("visual_params")),
            narrative_description=prompt,
            visual_dependencies=deps,
            dependency_strategy=strategy,
            custom_attributes=attrs,
        )
        db.add(entity)
        db.flush()
        return "created", int(entity.id)
    existing_attrs = dict(existing.custom_attributes or {}) if isinstance(existing.custom_attributes, dict) else {}
    existing_prompt = _clean(existing.generation_prompt_cn)
    can_overwrite = (
        bool(force_overwrite)
        or (not existing_prompt)
        or existing_attrs.get("source") == SOURCE_FLAG
    )
    if can_overwrite:
        existing.generation_prompt_cn = prompt
        existing.description = prompt or existing.description
        existing.narrative_description = prompt or existing.narrative_description
        existing.generation_prompt_en = _clean(payload.get("generation_prompt_en")) or existing.generation_prompt_en
        existing.anchor_description = _clean(payload.get("anchor_description")) or existing.anchor_description
        existing.name_en = name_en or existing.name_en
        existing.base_name_en = _clean(payload.get("base_name_en")) or existing.base_name_en
        existing.atmosphere = _clean(payload.get("atmosphere")) or existing.atmosphere
        existing.visual_params = _clean(payload.get("visual_params")) or existing.visual_params
        existing.visual_dependencies = deps or existing.visual_dependencies
        existing.dependency_strategy = strategy or existing.dependency_strategy
        existing_attrs.update(attrs)
        existing.custom_attributes = existing_attrs
    return "updated" if can_overwrite else "kept", int(existing.id)


def _environments_from_group(group: Dict[str, Any]) -> List[Dict[str, Any]]:
    payload = group.get("payload")
    if isinstance(payload, dict):
        rows = payload.get("environments")
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    raw_json = group.get("json")
    if isinstance(raw_json, str) and raw_json.strip():
        try:
            parsed = json.loads(raw_json)
        except Exception:
            parsed = None
        if isinstance(parsed, dict):
            rows = parsed.get("environments")
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    return []


def merge_derived_environment_groups(
    existing: Sequence[Dict[str, Any]],
    incoming: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Merge by main_environment; same-name rows in a main take the incoming copy."""
    by_main: Dict[str, Dict[str, Dict[str, Any]]] = {}
    order: List[str] = []

    def _absorb(groups: Sequence[Dict[str, Any]]) -> None:
        for group in groups or []:
            if not isinstance(group, dict):
                continue
            main = _clean(group.get("main_environment"))
            if not main:
                continue
            if main not in by_main:
                by_main[main] = {}
                order.append(main)
            bucket = by_main[main]
            for row in _environments_from_group(group):
                name = _clean(row.get("name"))
                if name:
                    bucket[name] = row

    _absorb(existing)
    _absorb(incoming)
    result: List[Dict[str, Any]] = []
    for main in order:
        rows = list(by_main[main].values())
        rows.sort(
            key=lambda row: (
                int((row.get("custom_attributes") or {}).get("view_angle_from_main") or 0),
                _clean(row.get("name")),
            )
        )
        body = {"environments": rows}
        result.append(
            {
                "main_environment": main,
                "count": len(rows),
                "json": json.dumps(body, ensure_ascii=False, indent=2),
                "payload": body,
            }
        )
    return result


def persist_derived_environment_jsons(
    episode: Episode,
    groups: Sequence[Dict[str, Any]],
    *,
    replace_existing: bool = False,
) -> None:
    raw = str(getattr(episode, "ai_stage_outputs", "") or "").strip()
    try:
        obj = json.loads(raw) if raw else {"version": 1, "stages": {}}
        if not isinstance(obj, dict):
            obj = {"version": 1, "stages": {}}
    except Exception:
        obj = {"version": 1, "stages": {}}
    stages = obj.setdefault("stages", {})
    if not isinstance(stages, dict):
        stages = {}
        obj["stages"] = stages
    stage1 = stages.setdefault("stage1", {"key": "stage1", "outputs": {}})
    if not isinstance(stage1, dict):
        stage1 = {"key": "stage1", "outputs": {}}
        stages["stage1"] = stage1
    outputs = stage1.setdefault("outputs", {})
    if not isinstance(outputs, dict):
        outputs = {}
        stage1["outputs"] = outputs
    existing_groups: List[Dict[str, Any]] = []
    existing_blob = outputs.get("derived_environment_jsons")
    if (not replace_existing) and isinstance(existing_blob, dict):
        raw_content = existing_blob.get("content")
        try:
            parsed = (
                json.loads(raw_content)
                if isinstance(raw_content, str) and raw_content.strip()
                else raw_content
            )
        except Exception:
            parsed = []
        if isinstance(parsed, list):
            existing_groups = [item for item in parsed if isinstance(item, dict)]
    merged = merge_derived_environment_groups(existing_groups, groups)
    slim_groups = [
        {
            "main_environment": group.get("main_environment"),
            "count": group.get("count"),
            "json": group.get("json"),
        }
        for group in merged
    ]
    outputs["derived_environment_jsons"] = {
        "key": "derived_environment_jsons",
        "kind": "json",
        "title": "按主环境切割的衍生环境 JSON",
        "content": json.dumps(slim_groups, ensure_ascii=False, indent=2),
    }
    episode.ai_stage_outputs = json.dumps(obj, ensure_ascii=False, indent=2)


def ingest_derived_environments_from_framing(
    *,
    db: Session,
    project_id: int,
    episode_id: int,
    scene_text: str,
    force_overwrite: bool = False,
    replace_existing_groups: bool = False,
    commit: bool = True,
) -> Dict[str, Any]:
    groups = collect_derived_environment_jsons(scene_text)
    created = 0
    updated = 0
    kept = 0
    entity_ids: List[int] = []
    if int(project_id or 0) > 0 and int(episode_id or 0) > 0:
        for group in groups:
            for row in (group.get("payload") or {}).get("environments") or []:
                action, entity_id = _upsert_environment_entity(
                    db,
                    project_id=int(project_id),
                    episode_id=int(episode_id),
                    payload=row,
                    force_overwrite=force_overwrite,
                )
                if entity_id:
                    entity_ids.append(entity_id)
                if action == "created":
                    created += 1
                elif action == "updated":
                    updated += 1
                elif action == "kept":
                    kept += 1
        episode = (
            db.query(Episode)
            .filter(Episode.id == int(episode_id), _active_episode_clause())
            .first()
        )
        if episode is not None:
            persist_derived_environment_jsons(
                episode,
                groups,
                replace_existing=replace_existing_groups,
            )
        if commit:
            db.commit()
    logger.info(
        "[derived_env_ingest] mains=%s created=%s updated=%s kept=%s episode_id=%s",
        len(groups),
        created,
        updated,
        kept,
        episode_id,
    )
    return {
        "group_count": len(groups),
        "created": created,
        "updated": updated,
        "kept": kept,
        "entity_ids": entity_ids,
        "groups": [
            {"main_environment": group.get("main_environment"), "count": group.get("count"), "json": group.get("json")}
            for group in groups
        ],
    }


def has_derived_env_signals(text: str) -> bool:
    return bool(_DERIVED_ENV_SIGNAL_PATTERN.search(str(text or "")))


def load_scene_subskill_results_map(episode: Episode) -> Dict[str, Any]:
    raw = str(getattr(episode, "ai_stage_outputs", "") or "").strip()
    try:
        obj = json.loads(raw) if raw else {}
    except Exception:
        obj = {}
    stages = obj.get("stages") if isinstance(obj, dict) else {}
    stage1 = stages.get("stage1") if isinstance(stages, dict) else {}
    outputs = stage1.get("outputs") if isinstance(stage1, dict) else {}
    slot = outputs.get("scene_subskill_results") if isinstance(outputs, dict) else {}
    content = slot.get("content") if isinstance(slot, dict) else slot
    if isinstance(content, dict):
        return content
    if isinstance(content, str) and content.strip():
        try:
            parsed = json.loads(content)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def collect_framing_texts_from_results_map(
    result_map: Any,
    scene_ids: Optional[Sequence[str]] = None,
) -> List[Dict[str, str]]:
    wanted = {str(item or "").strip() for item in (scene_ids or []) if str(item or "").strip()}
    rows: List[Dict[str, str]] = []
    if not isinstance(result_map, dict):
        return rows
    for scene_id, scene_map in result_map.items():
        sid = str(scene_id or "").strip()
        if not sid or not isinstance(scene_map, dict):
            continue
        if wanted and sid not in wanted:
            continue
        framing = str(scene_map.get("framing") or "").strip()
        staging = str(scene_map.get("staging") or "").strip()
        if framing:
            rows.append({"scene_id": sid, "source": "framing", "text": framing})
        elif has_derived_env_signals(staging):
            rows.append({"scene_id": sid, "source": "staging", "text": staging})
    return rows


def _pipeline_scene_blocks(db: Session, episode_id: int) -> Dict[str, str]:
    rows = (
        db.query(ScriptProgressPipelineNode)
        .filter(
            ScriptProgressPipelineNode.episode_id == int(episode_id),
            ScriptProgressPipelineNode.node_name == "scene_subskill_scene",
        )
        .all()
    )
    result: Dict[str, str] = {}
    for row in rows:
        sid = str(getattr(row, "scene_id", "") or "").strip()
        meta = row.runtime_meta if isinstance(row.runtime_meta, dict) else {}
        block = str(meta.get("scene_block") or "").strip()
        if sid and block:
            result[sid] = block
    return result


def collect_framing_texts_for_episode(
    db: Session,
    episode: Episode,
    scene_ids: Optional[Sequence[str]] = None,
) -> List[Dict[str, str]]:
    wanted = {str(item or "").strip() for item in (scene_ids or []) if str(item or "").strip()}
    sources = collect_framing_texts_from_results_map(
        load_scene_subskill_results_map(episode),
        scene_ids,
    )
    have = {row["scene_id"] for row in sources}
    for sid, block in _pipeline_scene_blocks(db, int(episode.id)).items():
        if wanted and sid not in wanted:
            continue
        if sid in have:
            continue
        if has_derived_env_signals(block):
            sources.append({"scene_id": sid, "source": "pipeline_scene_block", "text": block})
            have.add(sid)
    return sources


def _is_derived_environment_entity(entity: Entity) -> bool:
    if str(getattr(entity, "type", "") or "").strip().lower() != "environment":
        return False
    attrs = getattr(entity, "custom_attributes", None)
    attrs = attrs if isinstance(attrs, dict) else {}
    if attrs.get("source") == SOURCE_FLAG:
        return True
    if attrs.get("derived_kind"):
        return True
    name = str(getattr(entity, "name", "") or "").strip()
    return bool(_DERIVED_ENV_NAME_PATTERN.match(name))


def purge_derived_environment_entities(
    db: Session,
    *,
    project_id: int,
    episode_id: int,
) -> int:
    from app.services.deletion_ops import _soft_delete_entities

    env_rows = (
        db.query(Entity)
        .filter(
            Entity.project_id == int(project_id),
            Entity.episode_id == int(episode_id),
            _active_entity_clause(),
            func.lower(func.trim(func.coalesce(Entity.type, ""))) == "environment",
        )
        .all()
    )
    scoped_ids = [int(row.id) for row in env_rows if _is_derived_environment_entity(row)]
    if not scoped_ids:
        return 0
    return _soft_delete_entities(db, entity_ids=scoped_ids)


def regen_derived_environments_from_framing(
    *,
    db: Session,
    project_id: int,
    episode_id: int,
    scene_ids: Optional[Sequence[str]] = None,
    purge_existing: bool = True,
) -> Dict[str, Any]:
    """Rebuild derived ENV assets from persisted 场景现场编排 output. No LLM."""
    episode = (
        db.query(Episode)
        .filter(
            Episode.id == int(episode_id),
            Episode.project_id == int(project_id),
            _active_episode_clause(),
        )
        .first()
    )
    if episode is None:
        return {
            "ok": False,
            "reason": "episode_missing",
            "scene_count": 0,
            "purged": 0,
            "created": 0,
            "updated": 0,
            "kept": 0,
            "group_count": 0,
            "entity_ids": [],
            "groups": [],
            "scenes": [],
        }
    sources = collect_framing_texts_for_episode(db, episode, scene_ids)
    if not sources:
        return {
            "ok": False,
            "reason": "no_framing_output",
            "scene_count": 0,
            "purged": 0,
            "created": 0,
            "updated": 0,
            "kept": 0,
            "group_count": 0,
            "entity_ids": [],
            "groups": [],
            "scenes": [],
        }
    purged = 0
    if purge_existing:
        purged = purge_derived_environment_entities(
            db,
            project_id=int(project_id),
            episode_id=int(episode_id),
        )
    combined = "\n\n".join(row["text"] for row in sources)
    ingest_meta = ingest_derived_environments_from_framing(
        db=db,
        project_id=int(project_id),
        episode_id=int(episode_id),
        scene_text=combined,
        force_overwrite=True,
        replace_existing_groups=True,
        commit=True,
    )
    logger.info(
        "[derived_env_ingest] regen scenes=%s purged=%s created=%s updated=%s episode_id=%s",
        len(sources),
        purged,
        ingest_meta.get("created"),
        ingest_meta.get("updated"),
        episode_id,
    )
    return {
        "ok": True,
        "reason": "",
        "scene_count": len(sources),
        "purged": purged,
        **ingest_meta,
        "scenes": [
            {"scene_id": row["scene_id"], "source": row["source"]}
            for row in sources
        ],
    }
