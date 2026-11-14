# -*- coding: utf-8 -*-
"""Trim a design opening before it is sent to the four-grid skill.

The stored opening stays complete. The model only needs the keys it rotates:
appearance material, the six-face lock, wall sections, light direction, and
composition method. Place prose, color essays, path lines, and piece counts
stay out.
"""
from __future__ import annotations

import re

_SECTION_RE = re.compile(r"【([^】]+)】")
_DRAFT_RE = re.compile(
    r"【主环境设计稿】([^\n]+)\n(.*?)【/主环境设计稿】",
    re.DOTALL,
)
_DROP_SECTIONS = {"定位", "色彩说明"}
_DROP_KEYS = {
    "动线",
    "交接",
    "件数",
    "面件数",
    "依据",
    "挂靠锚点",
    "锚点落",
    "醒目光",
    "识别",
    "戏用标识",
    "站位承载",
    "参照物",
}
_SHAPE_DROP_KEYS = {"纹样", "颜色"}
_OPTICAL_KEYS = {
    "主光",
    "辅光",
    "点缀",
    "出光口",
    "源形",
    "Key世界向",
    "世界来向",
    "世界射向",
    "光比",
    "色温",
    "柔硬",
    "焦段",
    "景深",
    "半影",
    "材质响应",
}
_SPLIT = re.compile(r"[｜|]")


def _field_key(part: str) -> str:
    head = str(part or "").strip()
    if "=" not in head:
        return ""
    return head.split("=", 1)[0].strip()


def _filter_fields(line: str, *, keep: set | None, drop: set, split_comma: bool = False) -> str:
    parts = re.split(r"[｜|，]", line) if split_comma else _SPLIT.split(line)
    if len(parts) == 1 and not _field_key(parts[0]):
        return "" if keep is not None else line
    kept = []
    for part in parts:
        key = _field_key(part)
        if keep is not None and key and key not in keep:
            continue
        if key in drop:
            continue
        kept.append(part.strip())
    return "｜".join(piece for piece in kept if piece)


def _crop_section(name: str, body: str) -> str:
    title = f"【{name}】"
    lines = []
    for raw in body.split("\n"):
        line = raw.rstrip()
        if not line.strip():
            continue
        if name == "主体外形":
            line = _filter_fields(
                line, keep=None, drop=_DROP_KEYS | _SHAPE_DROP_KEYS, split_comma=True,
            )
        elif name == "光学说明":
            line = _filter_fields(line, keep=_OPTICAL_KEYS, drop=set())
        elif name == "构图":
            if not any(token in line for token in ("构图方法", "构图倾向", "方法=", "倾向=")):
                continue
            line = _filter_fields(line, keep=None, drop=_DROP_KEYS, split_comma=True)
        else:
            line = _filter_fields(line, keep=None, drop=_DROP_KEYS)
        if line.strip():
            lines.append(line)
    if not lines:
        return ""
    return title + "\n" + "\n".join(lines)


def crop_environment_opening_for_quad(opening: str) -> str:
    """Keep rotatable keys. Drop place prose, color essays, and ledger keys."""
    text = str(opening or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return ""
    marks = list(_SECTION_RE.finditer(text))
    if not marks:
        return text
    parts = []
    for index, match in enumerate(marks):
        name = match.group(1).strip()
        start = match.end()
        end = marks[index + 1].start() if index + 1 < len(marks) else len(text)
        if name in _DROP_SECTIONS:
            continue
        if name == "四向拼图":
            continue
        section = _crop_section(name, text[start:end])
        if section:
            parts.append(section)
    return "\n\n".join(parts).strip()


def crop_quad_skill_input(text: str) -> str:
    """Crop design drafts inside the user message. Leave other wrappers in place."""
    raw = str(text or "")
    if not raw.strip():
        return ""

    def _crop_payload(payload: str) -> str:
        if "【主环境设计稿】" not in payload:
            if "【六面一次】" in payload or "【主体外形】" in payload:
                return crop_environment_opening_for_quad(payload)
            return payload
        pieces = []
        cursor = 0
        for match in _DRAFT_RE.finditer(payload):
            pieces.append(payload[cursor:match.start()])
            name = match.group(1).strip()
            body = crop_environment_opening_for_quad(match.group(2))
            pieces.append(f"【主环境设计稿】{name}\n{body}\n【/主环境设计稿】")
            cursor = match.end()
        pieces.append(payload[cursor:])
        return "".join(pieces)

    start = "[待分析剧本开始]"
    end = "[待分析剧本结束]"
    if start in raw and end in raw:
        pre, rest = raw.split(start, 1)
        body, post = rest.split(end, 1)
        return pre + start + _crop_payload(body) + end + post
    return _crop_payload(raw)
