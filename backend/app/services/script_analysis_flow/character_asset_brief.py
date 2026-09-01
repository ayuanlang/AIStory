# -*- coding: utf-8 -*-
"""Assemble scene-split CHAR extracts for Stage 3 character design."""
from __future__ import annotations

import re
from typing import Dict, List

from app.core.prompt_injection import assemble_injection_parts, wrap_injection_section

CHAR_EXTRACT_BLOCK_PATTERN = re.compile(
    r"`?\[CHAR_EXTRACT_START(?::([^\s\]]+))?\]`?"
    r"(.*?)"
    r"`?\[CHAR_EXTRACT_END(?::([^\s\]]+))?\]`?",
    re.IGNORECASE | re.DOTALL,
)
CHAR_ITEM_PATTERN = re.compile(r"^\[CHAR\]\s*名称\s*=\s*(\S.+)$", re.MULTILINE | re.IGNORECASE)
CHAR_RECORD_PATTERN = re.compile(r"^\[CHAR\][^\n]*(?:\n(?!\[CHAR\]).*)*", re.MULTILINE | re.IGNORECASE)


def _clean(value: object) -> str:
    return str(value or "").strip()


def _name_from_char_header(header: str) -> str:
    raw = _clean(header).split("｜", 1)[0].split("|", 1)[0].strip()
    return raw if raw and raw != "无" else ""


def extract_char_field(record_text: str, field_name: str) -> str:
    pattern = re.compile(rf"^{re.escape(field_name)}\s*=\s*(.+)$", re.MULTILINE)
    match = pattern.search(str(record_text or ""))
    return _clean(match.group(1)) if match else ""


def current_world_identity(identity: str) -> str:
    """Public current identity; strip trajectory. Nameplates still require a plot-safe occupation/identity."""
    text = _clean(identity)
    if not text or text == "无":
        return ""
    match = re.search(r"现时\s*=\s*([^｜|]+)", text)
    if match:
        return _clean(match.group(1))
    if "轨迹=" in text:
        return _clean(re.split(r"[｜|]\s*轨迹\s*=", text, maxsplit=1)[0])
    return text


def parse_char_extract_records(script_text: str) -> List[Dict[str, str]]:
    """Split `[CHAR]` items; each dict has name + full record text."""
    body = extract_char_extract_blocks(script_text) or _clean(script_text)
    records: List[Dict[str, str]] = []
    seen = set()
    for match in CHAR_RECORD_PATTERN.finditer(body):
        text = _clean(match.group(0))
        header = CHAR_ITEM_PATTERN.search(text)
        name = _name_from_char_header(header.group(1)) if header else ""
        if not name or name in seen:
            continue
        seen.add(name)
        records.append({"name": name, "text": text})
    return records


def extract_char_extract_blocks(script_text: str) -> str:
    blocks: List[str] = []
    for match in CHAR_EXTRACT_BLOCK_PATTERN.finditer(str(script_text or "")):
        block = _clean(match.group(0))
        if block:
            blocks.append(block)
    return "\n\n".join(blocks).strip()


def char_extract_has_items(script_text: str) -> bool:
    body = extract_char_extract_blocks(script_text)
    if not body:
        return bool(CHAR_ITEM_PATTERN.search(str(script_text or "")))
    if re.search(r"^\s*无\s*$", body.split("]", 1)[-1], re.MULTILINE):
        return bool(CHAR_ITEM_PATTERN.search(body))
    return bool(CHAR_ITEM_PATTERN.search(body) or CHAR_ITEM_PATTERN.search(str(script_text or "")))


def splice_char_extract_into_script(script_text: str, char_extract: str) -> str:
    """Keep the episode-level extract inside SCENES_BLOCK so Stage-1 adaptation persist cannot drop it."""
    extract = _clean(char_extract)
    merged = str(script_text or "").rstrip()
    if not extract:
        return merged
    if "[CHAR_EXTRACT_START" in merged.upper():
        return merged
    end_match = re.search(r"`?\[SCENES_BLOCK_END\]`?", merged, flags=re.IGNORECASE)
    if not end_match:
        return f"{merged}\n\n{extract}"
    before = merged[: end_match.start()].rstrip()
    end_token = merged[end_match.start() : end_match.end()]
    after = merged[end_match.end() :]
    return f"{before}\n\n{extract}\n{end_token}{after}"


def first_text_with_char_extract(*candidates: object) -> str:
    for candidate in candidates:
        text = _clean(candidate)
        if text and char_extract_has_items(text):
            return text
    return ""


def build_character_asset_design_brief(adapted_script: str) -> str:
    """Scene-split character extracts that must become independent character assets."""
    script = _clean(adapted_script)
    if not script or not char_extract_has_items(script):
        return ""
    body = extract_char_extract_blocks(script) or script
    preface = (
        "角色资产设计真源。全局统筹已完成角色提取与按场分配："
        "本轮用户侧只注入项目信息 + 本块；禁止把待分析剧本当输入；禁止注入道具提取或道具资产信息。"
        "本块含具名角色/换装衍生/龙套/群演簇特征。"
        "耳环/胸针等已并入衣着的配饰只画进定妆，不得另造道具依赖。"
        "禁止重做切场或环境落点；禁止另起同义角色名；外形/衣着/评价原样服务四视图。"
        "须读各条身份=的现时/轨迹/曾经：原富贵后落寞与一直贫困须在定妆上可目视区分，禁压成现时贫困快照。"
        "对白声线与上屏物理文字标签（含字体/字色）不进生图词。"
        "Subject Index 若仍含 character 行只作旧稿兼容，不得压过本块。"
    )
    return wrap_injection_section("全局统筹角色提取", f"{preface}\n\n{body}")


def assemble_character_asset_design_user_content(*parts: object) -> str:
    """Character extract only. Drop script-to-analyze and any leaked prop brief."""
    return assemble_injection_parts(*parts, strip_labels=["待分析剧本", "全局统筹道具提取"])
