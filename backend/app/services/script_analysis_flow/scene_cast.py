# -*- coding: utf-8 -*-
"""Per-scene CHAR/PROP assignment tags from scene_split."""
from __future__ import annotations

import re
from typing import Dict, List

from app.core.prompt_injection import wrap_injection_section
from app.services.script_analysis_flow.character_asset_brief import (
    CHAR_ITEM_PATTERN,
    extract_char_extract_blocks,
    extract_char_field,
    parse_char_extract_records,
)
from app.services.script_analysis_flow.prop_asset_brief import (
    PROP_ITEM_PATTERN,
    extract_prop_extract_blocks,
)

SCENE_CAST_BLOCK_PATTERN = re.compile(
    r"`?\[SCENE_CAST_START:([^\s\]]+)\]`?"
    r"(.*?)"
    r"`?\[SCENE_CAST_END:(?:[^\s\]]+)?\]`?",
    re.IGNORECASE | re.DOTALL,
)
SCENE_CHAR_LINE_PATTERN = re.compile(r"^【本场角色】\s*(.+)$", re.MULTILINE)
SCENE_PROP_LINE_PATTERN = re.compile(r"^【本场道具】\s*(.+)$", re.MULTILINE)
TOKEN_NAME_PATTERN = re.compile(
    r"(?:CHAR\s*:\s*\[@([^\]]+)\]|PROP\s*:\s*\[([^\]]+)\])",
    re.IGNORECASE,
)


def _clean(value: object) -> str:
    return str(value or "").strip()


def _names_from_extract_items(block: str, item_pattern: re.Pattern[str]) -> List[str]:
    names: List[str] = []
    seen = set()
    for match in item_pattern.finditer(str(block or "")):
        raw = _clean(match.group(1)).split("｜", 1)[0].split("|", 1)[0].strip()
        if raw and raw not in seen and raw != "无":
            seen.add(raw)
            names.append(raw)
    return names


def extract_scene_cast_blocks(script_text: str) -> Dict[str, str]:
    blocks: Dict[str, str] = {}
    for match in SCENE_CAST_BLOCK_PATTERN.finditer(str(script_text or "")):
        scene_id = _clean(match.group(1))
        block = _clean(match.group(0))
        if scene_id and block:
            blocks[scene_id] = block
    return blocks


def extract_scene_cast_block(script_text: str, scene_id: str) -> str:
    wanted = _clean(scene_id)
    if not wanted:
        return ""
    blocks = extract_scene_cast_blocks(script_text)
    if wanted in blocks:
        return blocks[wanted]
    for key, block in blocks.items():
        if key.lower() == wanted.lower():
            return block
    return ""


def extract_legacy_scene_cast_lines(scene_text: str) -> str:
    source = str(scene_text or "")
    lines: List[str] = []
    char_line = SCENE_CHAR_LINE_PATTERN.search(source)
    prop_line = SCENE_PROP_LINE_PATTERN.search(source)
    if char_line:
        lines.append(f"【本场角色】{_clean(char_line.group(1))}")
    if prop_line:
        lines.append(f"【本场道具】{_clean(prop_line.group(1))}")
    return "\n".join(lines).strip()


def scene_cast_token_names(cast_text: str) -> Dict[str, List[str]]:
    chars: List[str] = []
    props: List[str] = []
    seen_char = set()
    seen_prop = set()
    for match in TOKEN_NAME_PATTERN.finditer(str(cast_text or "")):
        char_name = _clean(match.group(1))
        prop_name = _clean(match.group(2))
        if char_name and char_name not in seen_char:
            seen_char.add(char_name)
            chars.append(char_name)
        if prop_name and prop_name not in seen_prop:
            seen_prop.add(prop_name)
            props.append(prop_name)
    return {"characters": chars, "props": props}


def build_scene_entity_token_brief(full_script: str, scene_id: str, scene_text: str = "") -> str:
    """Whitelist for drama-onward CHAR/PROP standard expression."""
    script = str(full_script or "")
    cast = extract_scene_cast_block(script, scene_id)
    if not cast:
        cast = extract_legacy_scene_cast_lines(scene_text or script)
    char_names = _names_from_extract_items(extract_char_extract_blocks(script), CHAR_ITEM_PATTERN)
    prop_names = _names_from_extract_items(extract_prop_extract_blocks(script), PROP_ITEM_PATTERN)
    cast_names = scene_cast_token_names(cast)
    for name in cast_names.get("characters") or []:
        if name not in char_names:
            char_names.append(name)
    for name in cast_names.get("props") or []:
        if name not in prop_names:
            prop_names.append(name)
    if not char_names and not prop_names and not cast:
        return ""
    char_line = "，".join(char_names) if char_names else "无"
    prop_line = "，".join(prop_names) if prop_names else "无"
    preface = (
        "本场资产标准表达白名单。文戏起叙述层命中下列完整名必须写成 "
        "`CHAR:[@原样]` / `PROP:[原样]`；只换称呼串，不改句。"
        "对白正文与物理字样不换。现场编排确认衍生环境前禁止 `ENV:`。"
        "名单外保持自然语言，禁止另起未列出名。"
        "设置 voice_identity 必须先读【本场对白声线】：有声线则写入该角色 voice_identity；"
        "禁把声线标签写入台词。"
    )
    body = (
        f"{preface}\n\n"
        f"CHAR: {char_line}\n"
        f"PROP: {prop_line}"
    )
    if cast:
        body = f"{body}\n\n{cast}"
    scene_char_names = set(cast_names.get("characters") or [])
    voice_rows = []
    for rec in parse_char_extract_records(script):
        name = rec.get("name") or ""
        if name not in scene_char_names:
            continue
        voice = extract_char_field(rec.get("text") or "", "对白声线") or "无"
        voice_rows.append(f"CHAR:[@{name}]｜对白声线={voice}")
    if voice_rows:
        body = f"{body}\n\n【本场对白声线】\n" + "\n".join(voice_rows)
    return wrap_injection_section("本场角色道具白名单", body)
