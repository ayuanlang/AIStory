# -*- coding: utf-8 -*-
"""Per-scene CHAR/PROP assignment tags from scene_split."""
from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Set

from app.core.prompt_injection import wrap_injection_section
from app.services.subject_index_resolve import extract_project_visual_backfill_object
from app.services.script_analysis_flow.character_asset_brief import (
    CHAR_ITEM_PATTERN,
    _character_name_key,
    extract_char_extract_blocks,
    extract_char_field,
    parse_char_extract_records,
)
from app.services.script_analysis_flow.prop_asset_brief import (
    PROP_ITEM_PATTERN,
    PROP_RECORD_PATTERN,
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
_NAMEPLATE_POSITIONING_CN = (
    "女主",
    "男主",
    "反派",
    "配角",
    "主角",
    "龙套",
    "番位",
)
_NAMEPLATE_PLOT_PEEL_CN = (
    "落魄",
    "落寞",
    "败落",
    "发迹",
    "贬谪",
    "曾经",
    "前任",
    "卧底",
    "伪装",
    "假面",
    "揭穿",
    "真身",
    "隐藏",
    "重生",
    "转世",
    "穿越",
    "回归",
    "救世主",
    "天选",
    "命定",
    "天命",
    "即将",
    "复仇",
    "觉醒",
)
_NAMEPLATE_POSITIONING_EN = re.compile(
    r"\b(villain|protagonist|heroine|male\s+lead|female\s+lead|supporting\s+role)\b",
    re.IGNORECASE,
)
_NAMEPLATE_PLOT_PEEL_EN = re.compile(
    r"\b(fallen|former|undercover|revenge|hidden|reborn|awakened|"
    r"chosen(?:\s+one)?|transmigrat\w*)\b",
    re.IGNORECASE,
)


def _clean(value: object) -> str:
    return str(value or "").strip()


def _public_nameplate_label(value: str) -> str:
    """Keep objective identity; peel plot/circumstance words; reject positioning."""
    text = _clean(value)
    if not text or text == "无":
        return "无"
    if any(token in text for token in _NAMEPLATE_POSITIONING_CN):
        return "无"
    if _NAMEPLATE_POSITIONING_EN.search(text):
        return "无"
    for token in sorted(_NAMEPLATE_PLOT_PEEL_CN, key=len, reverse=True):
        text = text.replace(token, "")
    text = _NAMEPLATE_PLOT_PEEL_EN.sub("", text)
    text = re.sub(r"[\s/·\-—_,，]+", " ", text).strip(" /·-—_,，")
    if not text or text == "无":
        return "无"
    han = re.findall(r"[\u4e00-\u9fff]", text)
    latin = re.findall(r"[A-Za-z]{2,}", text)
    if not han and not latin:
        return "无"
    if len(han) == 1 and not latin:
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


def _field_token(record_text: str, key: str) -> str:
    raw = _header_field(record_text, key)
    return _clean(raw.split("｜", 1)[0].split("|", 1)[0])


def _header_field(record_text: str, key: str) -> str:
    prefix = f"{key}="
    for line in str(record_text or "").splitlines():
        for part in line.replace("|", "｜").split("｜"):
            item = part.strip()
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


def _parse_prop_records(script_text: str) -> List[Dict[str, str]]:
    body = extract_prop_extract_blocks(script_text) or ""
    records: List[Dict[str, str]] = []
    seen = set()
    for match in PROP_RECORD_PATTERN.finditer(body):
        text = _clean(match.group(0))
        header = PROP_ITEM_PATTERN.search(text)
        if not header:
            continue
        name = _clean(header.group(1)).split("｜", 1)[0].split("|", 1)[0].strip()
        if not name or name in seen or name == "无":
            continue
        seen.add(name)
        records.append({"name": name, "text": text})
    return records


def _first_prop_cast_scene(script_text: str, prop_name: str) -> str:
    wanted = _clean(prop_name)
    if not wanted:
        return ""
    for scene_id, block in extract_scene_cast_blocks(script_text).items():
        names = scene_cast_token_names(block).get("props") or []
        if wanted in names:
            return scene_id
    return ""


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
    """Use explicit 标签= (from CHAR|#身份 or intro); never summarize from 身份=."""
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


_NAMEPLATE_STYLE_KEYS = ("字体", "样式", "字色", "字级", "出字")


def _parse_nameplate_style_text(raw: str) -> Dict[str, str]:
    text = _clean(raw)
    if not text or text == "无":
        return {}
    found: Dict[str, str] = {}
    for key in _NAMEPLATE_STYLE_KEYS:
        match = re.search(rf"{key}\s*[=＝:：]\s*([^｜|\n]+)", text)
        if not match:
            continue
        value = _clean(match.group(1))
        if value and value not in {"无", "待补"}:
            found[key] = value
    if "字体" not in found or "字色" not in found:
        return {}
    found.setdefault("样式", "无衬细字")
    found.setdefault("字级", "中")
    mode = found.get("出字") or ""
    found["出字"] = "模型直出" if mode == "模型直出" else "烧制"
    return found


def _project_nameplate_style(script: str) -> Dict[str, str]:
    """One presentation locked in project_visual_backfill.nameplate_style."""
    obj = extract_project_visual_backfill_object(script) or {}
    raw = obj.get("nameplate_style") or obj.get("名牌展现") or ""
    if isinstance(raw, dict):
        parts = []
        for key in _NAMEPLATE_STYLE_KEYS:
            value = _clean(raw.get(key))
            if value:
                parts.append(f"{key}={value}")
        raw = "｜".join(parts)
    return _parse_nameplate_style_text(str(raw or ""))


def _same_scene_id(left: str, right: str) -> bool:
    return bool(left) and bool(right) and _clean(left).lower() == _clean(right).lower()


def _character_marked_reused(
    name: str,
    record_text: str,
    base_name: str,
    reused_character_names: Optional[Iterable[str]],
) -> bool:
    explicit = extract_char_field(record_text, "复用")
    if explicit in {"是", "yes", "y", "true", "复用"}:
        return True
    if not reused_character_names:
        return False
    keys = {_character_name_key(item) for item in reused_character_names}
    for raw in (name, base_name):
        key = _character_name_key(raw)
        if key and key in keys:
            return True
    return False


_MAIN_ENV_HEADER_NAME_PATTERN = re.compile(
    r"(?m)^[ \t]*【主环境】[ \t]*(.+)$"
)
_ENV_NAMEPLATE_META_TAIL = re.compile(
    r"(?:[·・\s/／]+(?:日|夜|晨|昏|昼|晚|内|外|室内|室外|春|夏|秋|冬|晴|雨|雪|阴))+$"
)
_ENV_DEGREE_PREFIX = re.compile(r"^\d+度")
_ENV_TIME_STORY_DAY = re.compile(
    r"(?:重生|穿越|回归|转世)?第[一二三四五六七八九十百千零〇0-9]+[天日]"
)
_ENV_TIME_CLOCK = re.compile(
    r"(?:早上|上午|中午|下午|傍晚|晚上|夜里|夜裡|凌晨|清晨|黄昏)?"
    r"\s*"
    r"(?:"
    r"\d{1,2}\s*[点時时](?:\s*\d{1,2}\s*分)?"
    r"|"
    r"\d{1,2}\s*[:：]\s*\d{2}"
    r"|"
    r"\d{1,2}\s*(?:AM|PM|am|pm)"
    r")"
)
_ENV_TIME_DAY_EN = re.compile(
    r"(?:Rebirth|Transmigrat\w+|Return)?\s*Day\s+\d+",
    re.IGNORECASE,
)
_ENV_TIME_BANNED_ALONE = frozenset(
    {"日", "夜", "晨", "昏", "昼", "晚", "内", "外", "室内", "室外"}
)


def _scene_body_for_nameplate(script: str, scene_id: str, scene_text: str = "") -> str:
    body = str(scene_text or "").strip()
    if body:
        return body
    if not scene_id:
        return str(script or "")
    start = f"[SCENE_START:{scene_id}]"
    end = f"[SCENE_END:{scene_id}]"
    lower = script.lower()
    i = lower.find(start.lower())
    j = lower.find(end.lower())
    if i >= 0 and j > i:
        return script[i:j]
    return str(script or "")


def _env_nameplate_time_label(haystack: str) -> str:
    """Explicit clock / story-day only; never 日夜内外 from scene headings."""
    text = str(haystack or "")
    text = re.sub(r"【场景名称】[^\n]*", " ", text)
    text = re.sub(r"日夜内外\s*[=：:][^\n｜|]*", " ", text)
    story = next((m.group(0).strip() for m in _ENV_TIME_STORY_DAY.finditer(text)), "")
    clock = next((m.group(0).strip() for m in _ENV_TIME_CLOCK.finditer(text)), "")
    day_en = next((m.group(0).strip() for m in _ENV_TIME_DAY_EN.finditer(text)), "")
    parts = [part for part in (story, clock or day_en) if part]
    if not parts:
        return "无"
    label = "".join(parts) if story and clock else (parts[0])
    compact = re.sub(r"\s+", "", label)
    if compact in _ENV_TIME_BANNED_ALONE:
        return "无"
    return label


def _env_nameplate_bare_name(raw: str) -> str:
    name = _clean(raw).strip("`\"'“”‘’[]")
    name = re.sub(r"^(名称|主环境|环境名|环境)\s*[=：:]\s*", "", name).strip()
    name = _ENV_DEGREE_PREFIX.sub("", name).strip()
    name = _ENV_NAMEPLATE_META_TAIL.sub("", name).strip(" ·・")
    if name in {"无", "空", "none", "n/a"}:
        return ""
    if re.fullmatch(r"[─—－\-_=*\s.。·]+", name):
        return ""
    return name


def _nameplate_header_name(raw: str) -> str:
    """First real name on a 【主环境】 line. A rule of dashes is not a name."""
    for segment in re.split(r"[｜|]", str(raw or "")):
        piece = segment.strip()
        if not piece or "=" in piece or "＝" in piece or ":" in piece or "：" in piece:
            continue
        bare = _env_nameplate_bare_name(piece)
        if bare:
            return bare
    return ""


def collect_scene_env_nameplate_names(
    script: str, scene_id: str, scene_text: str = ""
) -> List[str]:
    """New main-env names for this scene only. Reused spaces get no nameplate."""
    from app.services.script_analysis_flow.environment_reuse import (
        parse_scene_env_ident_items,
    )

    already: Set[str] = set()
    names: List[str] = []

    def allow(raw: str) -> None:
        bare = _env_nameplate_bare_name(raw)
        if not bare or bare in already:
            return
        already.add(bare)
        names.append(bare)

    for item in parse_scene_env_ident_items(script):
        bare = _env_nameplate_bare_name(str(item.get("name") or ""))
        matched = _env_nameplate_bare_name(str(item.get("matched_name") or ""))
        keys = [key for key in (bare, matched) if key]
        if item.get("reuse"):
            already.update(keys)
            continue
        if not bare or bare in already:
            continue
        already.add(bare)
        if _same_scene_id(str(item.get("scene_id") or ""), scene_id):
            names.append(bare)
    body = str(scene_text or "").strip()
    if not body and scene_id:
        start = f"[SCENE_START:{scene_id}]"
        end = f"[SCENE_END:{scene_id}]"
        lower = script.lower()
        i = lower.find(start.lower())
        j = lower.find(end.lower())
        if i >= 0 and j > i:
            body = script[i:j]
    if body:
        for item in parse_scene_env_ident_items(body, scene_id):
            bare = _env_nameplate_bare_name(str(item.get("name") or ""))
            matched = _env_nameplate_bare_name(str(item.get("matched_name") or ""))
            if item.get("reuse"):
                blocked = {key for key in (bare, matched) if key}
                already.update(blocked)
                names[:] = [name for name in names if name not in blocked]
                continue
            allow(bare)
        for match in _MAIN_ENV_HEADER_NAME_PATTERN.finditer(body):
            header_name = _nameplate_header_name(match.group(1))
            if header_name:
                allow(header_name)
    return names


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


def build_scene_entity_token_brief(
    full_script: str,
    scene_id: str,
    scene_text: str = "",
    reused_character_names: Optional[Iterable[str]] = None,
    for_framing: bool = False,
) -> str:
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
    if for_framing:
        scene_chars = list(cast_names.get("characters") or [])
        scene_props = list(cast_names.get("props") or [])
        if not scene_chars and not scene_props:
            present = str(scene_text or "")
            scene_chars = [name for name in char_names if name and name in present]
            scene_props = [name for name in prop_names if name and name in present]
        char_names = scene_chars
        prop_names = scene_props
        cast = ""
    if not char_names and not prop_names and not cast:
        return ""
    char_line = "，".join(char_names) if char_names else "无"
    prop_line = "，".join(prop_names) if prop_names else "无"
    if for_framing:
        preface = (
            "本场叙述只使用下列已注册名，写成 `CHAR:[@原样]` / `PROP:[原样]`。"
            "不写声线、名牌、外形。衍生环境确认前不写 `ENV:`。"
            "名单外保持自然语言，禁止另起未列出名。"
        )
        return wrap_injection_section(
            "本场角色道具白名单",
            f"{preface}\n\nCHAR: {char_line}\nPROP: {prop_line}",
        )
    preface = (
        "叙述层命中下列完整名写成 `CHAR:[@原样]` / `PROP:[原样]`。"
        "对白和物理字样不换。衍生环境确认前不写 `ENV:`。"
        "名单外保持自然语言。"
        "声线、标签和名牌行只供本技能抄写，不改这些行的字。"
    )
    body = (
        f"{preface}\n\n"
        f"CHAR: {char_line}\n"
        f"PROP: {prop_line}"
    )
    if cast:
        body = f"{body}\n\n{cast}"
    presentation = _project_nameplate_style(script)
    if presentation:
        body = (
            f"{body}\n\n【名牌展现】"
            f"字体={presentation['字体']}｜样式={presentation['样式']}｜"
            f"字色={presentation['字色']}｜字级={presentation['字级']}｜"
            f"出字={presentation['出字']}"
        )
    output_mode = presentation["出字"] if presentation else "烧制"
    enters_video = "否" if output_mode in {"烧制", "后期烧录"} else "是"
    scene_char_names = set(cast_names.get("characters") or [])
    voice_rows = []
    tag_rows = []
    plate_rows = []
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
        style = _character_label_style(text, "标签样式", base_text)
        if style == "待补":
            style = ""
        plot_role = _header_field(text, "番位")
        display_name = _subtitle_display_name(name, text)
        display_name_en = _subtitle_display_name_en(name, text, records)
        nameplate_mode = _nameplate_mode(name, text)
        face_gate = ""
        if plot_role in CROWD_ROLE_TOKENS:
            subtitle = "无"
            font = "无"
            color = "无"
            style = ""
        elif nameplate_mode == "无":
            subtitle = "无"
        elif _is_outfit_variant(name, text, all_record_names):
            subtitle = "无"
        elif _character_marked_reused(name, text, base_name, reused_character_names):
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
        if presentation and font != "无":
            font = presentation["字体"]
            color = presentation["字色"]
            style = presentation["样式"]
        style_part = f"｜标签样式={style}" if style else ""
        tag_rows.append(
            f"CHAR:[@{name}]｜标签={tag}｜标签_en={tag_en}｜"
            f"标签字体={font}{style_part}｜标签字色={color}｜"
            f"裸名={display_name}｜裸名_en={display_name_en}｜字幕={subtitle}"
            f"{face_gate}｜落位=人物下方｜字级=中｜出字={output_mode}｜名牌种类=角色"
        )
        shown = "待落" if subtitle == "待落" else subtitle
        plate_rows.append(
            f"种类=角色｜对象=CHAR:[@{name}]｜主标={display_name}｜副标={tag}｜"
            f"落位=人物下方｜字体={font}｜样式={style or '无'}｜字色={color}｜"
            f"字级=中｜出字={output_mode}｜上屏={shown}｜进视频={enters_video}"
        )
    if voice_rows:
        body = f"{body}\n\n【本场对白声线】\n" + "\n".join(voice_rows)
    if tag_rows:
        body = f"{body}\n\n【本场角色标签】\n" + "\n".join(tag_rows)
    env_font = "待补"
    env_color = "待补"
    env_style = ""
    if presentation:
        env_font = presentation["字体"]
        env_color = presentation["字色"]
        env_style = presentation["样式"]
    else:
        for rec in records:
            if rec.get("name") not in scene_char_names:
                continue
            text = rec.get("text") or ""
            base_name = extract_char_field(text, "基名") or (
                (rec.get("name") or "").split("_", 1)[0]
                if "_" in (rec.get("name") or "")
                else ""
            )
            base_text = _record_by_name(records, base_name).get("text") or ""
            font = _character_label_style(text, "标签字体", base_text)
            color = _character_label_style(text, "标签字色", base_text)
            plate_style = _character_label_style(text, "标签样式", base_text)
            if font and font not in {"无", "待补"}:
                env_font = font
            if color and color not in {"无", "待补"}:
                env_color = color
            if not env_style and plate_style not in {"", "无", "待补"}:
                env_style = plate_style
            if env_font != "待补" and env_color != "待补":
                break
    env_rows = []
    env_time = _env_nameplate_time_label(
        _scene_body_for_nameplate(script, scene_id, scene_text or "")
    )
    for env_name in collect_scene_env_nameplate_names(
        script, scene_id, scene_text or ""
    ):
        env_rows.append(
            f"ENV:[{env_name}]｜字样=【{env_name}】｜时间={env_time}｜标签={env_time}｜"
            f"落位=顶部中央｜字体={env_font}｜字色={env_color}"
            + (f"｜样式={env_style}" if env_style else "")
            + f"｜字级=中｜出字={output_mode}｜名牌种类=环境"
        )
        plate_rows.append(
            f"种类=环境｜对象=ENV:[{env_name}]｜主标={env_name}｜副标={env_time}｜"
            f"落位=顶部中央｜字体={env_font}｜样式={env_style or '无'}｜字色={env_color}｜"
            f"字级=中｜出字={output_mode}｜上屏=首见｜进视频={enters_video}"
        )
    if env_rows:
        body = f"{body}\n\n【本场环境名牌】\n" + "\n".join(env_rows)
    scene_prop_names = set(cast_names.get("props") or [])
    for rec in _parse_prop_records(script):
        name = rec.get("name") or ""
        if name not in scene_prop_names:
            continue
        text = rec.get("text") or ""
        regularity = _field_token(text, "常规性")
        if regularity not in {"非常规", "产品"}:
            continue
        plate_flag = _field_token(text, "名牌") or "可"
        state = _field_token(text, "状态")
        if plate_flag == "无" or state == "变化后":
            shown = "无"
        else:
            debut = (_parse_applicable_scenes(text) or [None])[0] or _first_prop_cast_scene(
                script, name
            )
            if debut and _same_scene_id(debut, scene_id):
                shown = "待落"
            elif debut:
                shown = "已过"
            else:
                shown = "待落"
        tag = _public_nameplate_label(_field_token(text, "标签"))
        plate_rows.append(
            f"种类=道具｜对象=PROP:[{name}]｜主标={name}｜副标={tag}｜"
            f"落位=道具下方｜字体={env_font}｜样式={env_style or '无'}｜字色={env_color}｜"
            f"字级=中｜出字={output_mode}｜上屏={shown}｜进视频={enters_video}"
        )
    if plate_rows:
        body = f"{body}\n\n【名牌标签】\n" + "\n".join(plate_rows)
    return wrap_injection_section("本场角色道具白名单", body)
