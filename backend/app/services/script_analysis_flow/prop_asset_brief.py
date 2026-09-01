# -*- coding: utf-8 -*-
"""Assemble scene-split PROP extracts for Stage 3 prop design."""
from __future__ import annotations

import re
from typing import List

from app.core.prompt_injection import assemble_injection_parts, wrap_injection_section

PROP_EXTRACT_BLOCK_PATTERN = re.compile(
    r"`?\[PROP_EXTRACT_START(?::([^\s\]]+))?\]`?"
    r"(.*?)"
    r"`?\[PROP_EXTRACT_END(?::([^\s\]]+))?\]`?",
    re.IGNORECASE | re.DOTALL,
)
PROP_EXTRACT_START_PATTERN = re.compile(r"`?\[PROP_EXTRACT_START(?::[^\s\]]+)?\]`?", re.IGNORECASE)
PROP_EXTRACT_END_PATTERN = re.compile(r"`?\[PROP_EXTRACT_END(?::[^\s\]]+)?\]`?", re.IGNORECASE)
PROP_ITEM_PATTERN = re.compile(r"^\[PROP\]\s*名称\s*[=：:]\s*(\S.+)$", re.MULTILINE | re.IGNORECASE)
PROP_LOOSE_ITEM_PATTERN = re.compile(r"\[PROP\][\s\S]{0,160}名称\s*[=：:]", re.IGNORECASE)
PROP_RECORD_PATTERN = re.compile(r"^\[PROP\][^\n]*(?:\n(?!\[PROP\]).*)*", re.MULTILINE | re.IGNORECASE)


def _clean(value: object) -> str:
    return str(value or "").strip()


def collect_loose_prop_item_blocks(script_text: str) -> List[str]:
    items: List[str] = []
    seen = set()
    for match in PROP_RECORD_PATTERN.finditer(str(script_text or "")):
        block = _clean(match.group(0))
        if not block or block in seen:
            continue
        if re.match(r"^\[PROP\]\s*无\s*$", block, re.IGNORECASE):
            continue
        seen.add(block)
        items.append(block)
    return items


def extract_prop_extract_blocks(script_text: str) -> str:
    text = str(script_text or "")
    blocks: List[str] = []
    for match in PROP_EXTRACT_BLOCK_PATTERN.finditer(text):
        block = _clean(match.group(0))
        if block:
            blocks.append(block)
    if blocks:
        return "\n\n".join(blocks).strip()
    start = PROP_EXTRACT_START_PATTERN.search(text)
    if not start:
        return ""
    rest = text[start.start():]
    end = PROP_EXTRACT_END_PATTERN.search(rest)
    if end:
        return _clean(rest[: end.end()])
    cut = re.search(
        r"`?\[(?:CHAR_EXTRACT_START|SCENES_BLOCK_END)[^\]]*\]`?",
        rest[len(start.group(0)):],
        re.IGNORECASE,
    )
    clipped = rest[: len(start.group(0)) + cut.start()] if cut else rest
    return f"{_clean(clipped)}\n[PROP_EXTRACT_END]".strip()


def ensure_prop_extract_block(script_text: str) -> str:
    existing = extract_prop_extract_blocks(script_text)
    if existing:
        return existing
    items = collect_loose_prop_item_blocks(script_text)
    if not items:
        return ""
    return "[PROP_EXTRACT_START]\n" + "\n\n".join(items) + "\n[PROP_EXTRACT_END]"


def _prop_extract_inner(script_text: str) -> str:
    inners: List[str] = []
    for match in PROP_EXTRACT_BLOCK_PATTERN.finditer(extract_prop_extract_blocks(script_text) or ""):
        inners.append(_clean(match.group(2)))
    return "\n".join(inners).strip()


def prop_extract_has_items(script_text: str) -> bool:
    text = str(script_text or "")
    inner = _prop_extract_inner(text)
    if inner and not re.match(r"^\s*无\s*$", inner):
        return True
    if PROP_EXTRACT_START_PATTERN.search(text) and PROP_LOOSE_ITEM_PATTERN.search(text):
        return True
    if collect_loose_prop_item_blocks(text):
        return True
    return bool(PROP_ITEM_PATTERN.search(text) or PROP_LOOSE_ITEM_PATTERN.search(text))


def splice_prop_extract_into_script(script_text: str, prop_extract: str) -> str:
    """Keep the episode-level extract inside SCENES_BLOCK so Stage-1 adaptation persist cannot drop it."""
    extract = _clean(prop_extract)
    merged = str(script_text or "").rstrip()
    if not extract:
        return merged
    if "[PROP_EXTRACT_START" in merged.upper():
        return merged
    end_match = re.search(r"`?\[SCENES_BLOCK_END\]`?", merged, flags=re.IGNORECASE)
    if not end_match:
        return f"{merged}\n\n{extract}"
    before = merged[: end_match.start()].rstrip()
    end_token = merged[end_match.start() : end_match.end()]
    after = merged[end_match.end() :]
    return f"{before}\n\n{extract}\n{end_token}{after}"


def prop_extract_is_explicit_none(script_text: str) -> bool:
    text = str(script_text or "")
    if not PROP_EXTRACT_START_PATTERN.search(text):
        return False
    inner = _prop_extract_inner(text) or re.sub(
        r"`?\[PROP_EXTRACT_(START|END)(?::[^\s\]]+)?\]`?",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    return bool(re.match(r"^\s*无\s*$", inner or ""))


def _looks_like_prop_extract(script_text: str) -> bool:
    text = _clean(script_text)
    if not text or prop_extract_is_explicit_none(text):
        return False
    if prop_extract_has_items(text):
        return True
    return bool(collect_loose_prop_item_blocks(text))


def first_text_with_prop_extract(*candidates: object) -> str:
    for candidate in candidates:
        text = _clean(candidate)
        if text and PROP_EXTRACT_START_PATTERN.search(text):
            return "" if prop_extract_is_explicit_none(text) else text
        if text and prop_extract_has_items(text):
            return text
    return ""


def build_prop_asset_design_brief(adapted_script: str) -> str:
    """Scene-split XOR leftovers that must become independent props."""
    script = _clean(adapted_script)
    if not script:
        return ""
    body = ensure_prop_extract_block(script) or extract_prop_extract_blocks(script)
    if not body and _looks_like_prop_extract(script):
        body = script
    if not body:
        return ""
    inner = _prop_extract_inner(body) or re.sub(
        r"`?\[PROP_EXTRACT_(START|END)(?::[^\s\]]+)?\]`?",
        "",
        body,
        flags=re.IGNORECASE,
    ).strip()
    if not inner or re.match(r"^\s*无\s*$", inner):
        return ""
    return wrap_injection_section("全局统筹道具提取", body)


def assemble_prop_asset_design_user_content(*parts: object) -> str:
    """Prop extract only. Drop script-to-analyze and any leaked character brief."""
    return assemble_injection_parts(*parts, strip_labels=["待分析剧本", "全局统筹角色提取"])
