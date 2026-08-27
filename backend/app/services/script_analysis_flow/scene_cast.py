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
APPLICABLE_SCENE_PATTERN = re.compile(r"适用场\s*=\s*([^\n]+)", re.IGNORECASE)
SCENE_ID_TOKEN_PATTERN = re.compile(r"EP\d{2}_SC\d{2}[A-Za-z]*", re.IGNORECASE)
CROWD_ROLE_TOKENS = {"群演簇", "群演"}


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


def _header_field(record_text: str, key: str) -> str:
    first = str(record_text or "").split("\n", 1)[0]
    for part in first.replace("|", "｜").split("｜"):
        item = part.strip()
        prefix = f"{key}="
        if item.startswith(prefix):
            return _clean(item[len(prefix):])
    return extract_char_field(record_text, key)


def _parse_applicable_scenes(record_text: str) -> List[str]:
    match = APPLICABLE_SCENE_PATTERN.search(str(record_text or ""))
    if not match:
        return []
    seen = set()
    scenes: List[str] = []
    for token in SCENE_ID_TOKEN_PATTERN.findall(match.group(1) or ""):
        scene_id = _clean(token)
        key = scene_id.lower()
        if scene_id and key not in seen:
            seen.add(key)
            scenes.append(scene_id)
    return scenes


def _first_cast_scene(script_text: str, char_name: str) -> str:
    wanted = _clean(char_name)
    if not wanted:
        return ""
    for scene_id, block in extract_scene_cast_blocks(script_text).items():
        names = scene_cast_token_names(block).get("characters") or []
        if wanted in names:
            return scene_id
    return ""


def _is_outfit_variant(name: str, record_text: str, all_names: List[str]) -> bool:
    if extract_char_field(record_text, "基名"):
        return True
    raw = _clean(name)
    if "_" not in raw:
        return False
    base = raw.split("_", 1)[0].strip()
    return bool(base and base != raw and base in set(all_names))


def _record_by_name(records: List[Dict[str, str]], name: str) -> Dict[str, str]:
    wanted = _clean(name)
    for rec in records:
        if _clean(rec.get("name") or "") == wanted:
            return rec
    return {}


def _subtitle_display_name(name: str, record_text: str) -> str:
    base = extract_char_field(record_text, "基名")
    if base:
        return base
    raw = _clean(name)
    if "_" in raw:
        return raw.split("_", 1)[0].strip() or raw
    return raw


def _subtitle_display_name_en(
    name: str,
    record_text: str,
    records: List[Dict[str, str]],
) -> str:
    base = extract_char_field(record_text, "基名")
    if not base:
        raw = _clean(name)
        if "_" in raw:
            candidate = raw.split("_", 1)[0].strip()
            if candidate and _record_by_name(records, candidate):
                base = candidate
    if base:
        en = _header_field(_record_by_name(records, base).get("text") or "", "名称_en")
        if en:
            return en
    return _header_field(record_text, "名称_en") or _subtitle_display_name(name, record_text)


def _character_tag(record_text: str) -> str:
    tag = extract_char_field(record_text, "标签")
    if tag and tag != "无":
        return tag
    identity = extract_char_field(record_text, "身份")
    if identity and identity != "无":
        return identity
    return "无"


def _character_tag_en(record_text: str, base_text: str = "") -> str:
    tag_en = extract_char_field(record_text, "标签_en")
    if tag_en and tag_en != "无":
        return tag_en
    if base_text:
        inherited = extract_char_field(base_text, "标签_en")
        if inherited and inherited != "无":
            return inherited
    return "无"


def _same_scene_id(left: str, right: str) -> bool:
    return bool(left) and bool(right) and _clean(left).lower() == _clean(right).lower()


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
        "建置入戏须读【本场角色标签】：字幕=待落 且本拍该人首次正面/¾可读时，"
        "按项目语言选一侧字样写入戏 画面打出字幕：【{裸名}】{标签}】。"
        "中文项目用 裸名+标签；英文项目用 裸名_en+标签_en；禁中英并列、禁用错语种上屏。"
        "字幕=已过|无 则不写。"
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
    tag_rows = []
    records = parse_char_extract_records(script)
    all_record_names = [rec.get("name") or "" for rec in records]
    for rec in records:
        name = rec.get("name") or ""
        if name not in scene_char_names:
            continue
        text = rec.get("text") or ""
        voice = extract_char_field(text, "对白声线") or "无"
        voice_rows.append(f"CHAR:[@{name}]｜对白声线={voice}")
        tag = _character_tag(text)
        base_name = extract_char_field(text, "基名") or (
            name.split("_", 1)[0] if "_" in name else ""
        )
        base_text = _record_by_name(records, base_name).get("text") or ""
        tag_en = _character_tag_en(text, base_text)
        plot_role = _header_field(text, "番位")
        display_name = _subtitle_display_name(name, text)
        display_name_en = _subtitle_display_name_en(name, text, records)
        if plot_role in CROWD_ROLE_TOKENS or tag == "无":
            subtitle = "无"
        elif _is_outfit_variant(name, text, all_record_names):
            subtitle = "无"
        else:
            debut = (_parse_applicable_scenes(text) or [None])[0] or _first_cast_scene(script, name)
            if debut and _same_scene_id(debut, scene_id):
                subtitle = "待落"
            elif debut:
                subtitle = "已过"
            else:
                subtitle = "待落"
        tag_rows.append(
            f"CHAR:[@{name}]｜标签={tag}｜标签_en={tag_en}｜"
            f"裸名={display_name}｜裸名_en={display_name_en}｜字幕={subtitle}"
        )
    if voice_rows:
        body = f"{body}\n\n【本场对白声线】\n" + "\n".join(voice_rows)
    if tag_rows:
        body = f"{body}\n\n【本场角色标签】\n" + "\n".join(tag_rows)
    return wrap_injection_section("本场角色道具白名单", body)
