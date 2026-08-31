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
_TRUE_FACE_HIDDEN_TOKENS = (
    "蒙面",
    "易容",
    "面具",
    "面罩",
    "假面",
    "遮面",
    "面帘",
    "盔面",
    "头套遮",
    "面纱遮",
    "不见真脸",
    "真脸不可见",
    "真容不可见",
)
_UNMASK_TOKENS = (
    "揭面",
    "卸易容",
    "卸下面具",
    "摘下面具",
    "除去面罩",
    "露出真容",
    "现出真容",
    "摘下面罩",
)
_NAMEPLATE_PLOT_LEAK_CN = (
    "落魄",
    "落寞",
    "败落",
    "发迹",
    "贬谪",
    "卧底",
    "伪装",
    "假面",
    "复仇",
    "曾经",
    "前任",
    "女主",
    "男主",
    "反派",
    "配角",
    "主角",
    "龙套",
    "番位",
    "揭穿",
    "真身",
    "即将",
    "隐藏",
)
_NAMEPLATE_PLOT_LEAK_EN = re.compile(
    r"\b(fallen|former|undercover|revenge|hidden|villain|protagonist|"
    r"heroine|male\s+lead|female\s+lead|supporting\s+role)\b",
    re.IGNORECASE,
)


def _clean(value: object) -> str:
    return str(value or "").strip()


def _public_nameplate_label(value: str) -> str:
    """Keep occupation/public identity only; empty if plot or positioning leaks."""
    text = _clean(value)
    if not text or text == "无":
        return "无"
    if any(token in text for token in _NAMEPLATE_PLOT_LEAK_CN):
        return "无"
    if _NAMEPLATE_PLOT_LEAK_EN.search(text):
        return "无"
    return text


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


def _character_tag(record_text: str, base_text: str = "") -> str:
    """Use only an explicit nameplate tag; never summarize from 身份=."""
    tag = _public_nameplate_label(extract_char_field(record_text, "标签"))
    if tag != "无":
        return tag
    if base_text:
        inherited = _public_nameplate_label(extract_char_field(base_text, "标签"))
        if inherited != "无":
            return inherited
    return "无"


def _character_tag_en(record_text: str, base_text: str = "") -> str:
    tag_en = _public_nameplate_label(extract_char_field(record_text, "标签_en"))
    if tag_en != "无":
        return tag_en
    if base_text:
        inherited = _public_nameplate_label(extract_char_field(base_text, "标签_en"))
        if inherited != "无":
            return inherited
    return "无"


def _haystack_true_face(name: str, record_text: str) -> str:
    parts = [
        _clean(name),
        extract_char_field(record_text, "衣着"),
        extract_char_field(record_text, "外形"),
        extract_char_field(record_text, "定位"),
        extract_char_field(record_text, "形态连续"),
        extract_char_field(record_text, "衍生"),
    ]
    return " ".join(part for part in parts if part)


def _looks_true_face_hidden(name: str, record_text: str) -> bool:
    haystack = _haystack_true_face(name, record_text)
    return any(token in haystack for token in _TRUE_FACE_HIDDEN_TOKENS)


def _later_unmasks(record_text: str) -> bool:
    haystack = " ".join(
        [
            extract_char_field(record_text, "形态连续"),
            extract_char_field(record_text, "衍生"),
            extract_char_field(record_text, "名牌"),
        ]
    )
    return any(token in haystack for token in _UNMASK_TOKENS)


def _nameplate_mode(name: str, record_text: str) -> str:
    """可 | 无 | 揭面后. Masked/disguised true-face-hidden forms have no nameplate."""
    explicit = extract_char_field(record_text, "名牌")
    if explicit in {"无", "否", "禁"}:
        return "无"
    if explicit in {"揭面后", "须真脸"}:
        return "揭面后"
    if _looks_true_face_hidden(name, record_text):
        return "揭面后" if _later_unmasks(record_text) else "无"
    return "可"


def _character_label_style(record_text: str, field_name: str, base_text: str = "") -> str:
    value = extract_char_field(record_text, field_name)
    if value and value != "无":
        return value
    if base_text:
        inherited = extract_char_field(base_text, field_name)
        if inherited and inherited != "无":
            return inherited
    return "待补"


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
        "建置须读【本场角色标签】：字幕=待落 且本拍该人首次正面/¾可读时，"
        "按项目语言选一侧字样，紧跟该人【建置】可见面整句写 "
        "画面打出物理文字标签：【{裸名}】{标签}】｜字体={标签字体}｜字色={标签字色}。"
        "一人一句，禁把多名牌攒到建置段末或入戏一起写。"
        "此为片内图形名牌（物理文字），不是对白硬字幕；禁写成画幅底部白字黑边。"
        "剧本或提取块已写的字样/字体/字色原样服从，禁改写。"
        "中文项目用 裸名+标签；英文项目用 裸名_en+标签_en；禁中英并列、禁用错语种上屏。"
        "标签仅剧中明确身份介绍的职业/公开身份，禁推理，禁从身份、称呼、服制或叙述总结；为无则只打裸名，禁臆造。"
        "蒙面/易容/面具/面罩等见不到真脸：字幕必须=无，连裸名也不打，禁为蒙面态补名牌。"
        "名牌条件=须真脸 则等该人真脸正面/¾可读后再挂；全场未见真脸则不写、不标缺口。"
        "字体/字色为无或待补则跟 Global_Style 补一书体+具名色。"
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
        base_name = extract_char_field(text, "基名") or (
            name.split("_", 1)[0] if "_" in name else ""
        )
        base_text = _record_by_name(records, base_name).get("text") or ""
        tag = _character_tag(text, base_text)
        tag_en = _character_tag_en(text, base_text)
        font = _character_label_style(text, "标签字体", base_text)
        color = _character_label_style(text, "标签字色", base_text)
        plot_role = _header_field(text, "番位")
        display_name = _subtitle_display_name(name, text)
        display_name_en = _subtitle_display_name_en(name, text, records)
        nameplate_mode = _nameplate_mode(name, text)
        face_gate = ""
        if plot_role in CROWD_ROLE_TOKENS:
            subtitle = "无"
            font = "无"
            color = "无"
        elif nameplate_mode == "无":
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
            if nameplate_mode == "揭面后":
                face_gate = "｜名牌条件=须真脸"
        tag_rows.append(
            f"CHAR:[@{name}]｜标签={tag}｜标签_en={tag_en}｜"
            f"标签字体={font}｜标签字色={color}｜"
            f"裸名={display_name}｜裸名_en={display_name_en}｜字幕={subtitle}"
            f"{face_gate}"
        )
    if voice_rows:
        body = f"{body}\n\n【本场对白声线】\n" + "\n".join(voice_rows)
    if tag_rows:
        body = f"{body}\n\n【本场角色标签】\n" + "\n".join(tag_rows)
    return wrap_injection_section("本场角色道具白名单", body)
