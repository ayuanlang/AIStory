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
CHAR_EXTRACT_START_PATTERN = re.compile(r"`?\[CHAR_EXTRACT_START(?::[^\s\]]+)?\]`?", re.IGNORECASE)
CHAR_EXTRACT_END_PATTERN = re.compile(r"`?\[CHAR_EXTRACT_END(?::[^\s\]]+)?\]`?", re.IGNORECASE)
CHAR_ITEM_PATTERN = re.compile(r"^\[CHAR\]\s*名称\s*[=：:]\s*(\S.+)$", re.MULTILINE | re.IGNORECASE)
CHAR_LOOSE_ITEM_PATTERN = re.compile(r"\[CHAR\][\s\S]{0,160}名称\s*[=：:]", re.IGNORECASE)
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


def collect_loose_char_item_blocks(script_text: str) -> List[str]:
    items: List[str] = []
    seen = set()
    for match in CHAR_RECORD_PATTERN.finditer(str(script_text or "")):
        block = _clean(match.group(0))
        if not block or block in seen:
            continue
        if re.match(r"^\[CHAR\]\s*无\s*$", block, re.IGNORECASE):
            continue
        seen.add(block)
        items.append(block)
    return items


def extract_char_extract_blocks(script_text: str) -> str:
    text = str(script_text or "")
    blocks: List[str] = []
    for match in CHAR_EXTRACT_BLOCK_PATTERN.finditer(text):
        block = _clean(match.group(0))
        if block:
            blocks.append(block)
    if blocks:
        return "\n\n".join(blocks).strip()
    start = CHAR_EXTRACT_START_PATTERN.search(text)
    if not start:
        return ""
    rest = text[start.start():]
    end = CHAR_EXTRACT_END_PATTERN.search(rest)
    if end:
        return _clean(rest[: end.end()])
    cut = re.search(
        r"`?\[(?:PROP_EXTRACT_START|SCENES_BLOCK_END)[^\]]*\]`?",
        rest[len(start.group(0)):],
        re.IGNORECASE,
    )
    clipped = rest[: len(start.group(0)) + cut.start()] if cut else rest
    return f"{_clean(clipped)}\n[CHAR_EXTRACT_END]".strip()


def ensure_char_extract_block(script_text: str) -> str:
    existing = extract_char_extract_blocks(script_text)
    if existing:
        return existing
    items = collect_loose_char_item_blocks(script_text)
    if not items:
        return ""
    return "[CHAR_EXTRACT_START]\n" + "\n\n".join(items) + "\n[CHAR_EXTRACT_END]"


def _char_extract_inner(script_text: str) -> str:
    inners: List[str] = []
    for match in CHAR_EXTRACT_BLOCK_PATTERN.finditer(extract_char_extract_blocks(script_text) or ""):
        inners.append(_clean(match.group(2)))
    return "\n".join(inners).strip()


def char_extract_has_items(script_text: str) -> bool:
    text = str(script_text or "")
    inner = _char_extract_inner(text)
    if inner and not re.match(r"^\s*无\s*$", inner):
        return True
    if CHAR_EXTRACT_START_PATTERN.search(text) and CHAR_LOOSE_ITEM_PATTERN.search(text):
        return True
    if collect_loose_char_item_blocks(text):
        return True
    return bool(CHAR_ITEM_PATTERN.search(text) or CHAR_LOOSE_ITEM_PATTERN.search(text))


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


def char_extract_is_explicit_none(script_text: str) -> bool:
    text = str(script_text or "")
    if not CHAR_EXTRACT_START_PATTERN.search(text):
        return False
    inner = _char_extract_inner(text) or re.sub(
        r"`?\[CHAR_EXTRACT_(START|END)(?::[^\s\]]+)?\]`?",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    return bool(re.match(r"^\s*无\s*$", inner or ""))


def _looks_like_char_extract(script_text: str) -> bool:
    text = _clean(script_text)
    if not text or char_extract_is_explicit_none(text):
        return False
    if char_extract_has_items(text):
        return True
    return bool(collect_loose_char_item_blocks(text))


def first_text_with_char_extract(*candidates: object) -> str:
    for candidate in candidates:
        text = _clean(candidate)
        if text and CHAR_EXTRACT_START_PATTERN.search(text):
            return "" if char_extract_is_explicit_none(text) else text
        if text and char_extract_has_items(text):
            return text
    return ""


def build_character_asset_design_brief(adapted_script: str) -> str:
    """Scene-split character extracts that must become independent character assets."""
    script = _clean(adapted_script)
    if not script:
        return ""
    body = ensure_char_extract_block(script) or extract_char_extract_blocks(script)
    if not body and _looks_like_char_extract(script):
        body = script
    if not body:
        return ""
    inner = _char_extract_inner(body) or re.sub(
        r"`?\[CHAR_EXTRACT_(START|END)(?::[^\s\]]+)?\]`?",
        "",
        body,
        flags=re.IGNORECASE,
    ).strip()
    if not inner or re.match(r"^\s*无\s*$", inner):
        return ""
    return wrap_injection_section("全局统筹角色提取", body)


def assemble_character_asset_design_user_content(*parts: object) -> str:
    """Character extract only. Drop script-to-analyze and any leaked prop brief."""
    return assemble_injection_parts(*parts, strip_labels=["待分析剧本", "全局统筹道具提取"])
