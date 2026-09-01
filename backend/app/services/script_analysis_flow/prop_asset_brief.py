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
PROP_ITEM_PATTERN = re.compile(r"^\[PROP\]\s*名称\s*=\s*(\S.+)$", re.MULTILINE | re.IGNORECASE)


def _clean(value: object) -> str:
    return str(value or "").strip()


def extract_prop_extract_blocks(script_text: str) -> str:
    blocks: List[str] = []
    for match in PROP_EXTRACT_BLOCK_PATTERN.finditer(str(script_text or "")):
        block = _clean(match.group(0))
        if block:
            blocks.append(block)
    return "\n\n".join(blocks).strip()


def prop_extract_has_items(script_text: str) -> bool:
    body = extract_prop_extract_blocks(script_text)
    if not body:
        return bool(PROP_ITEM_PATTERN.search(str(script_text or "")))
    if re.search(r"^\s*无\s*$", body.split("]", 1)[-1], re.MULTILINE):
        return bool(PROP_ITEM_PATTERN.search(body))
    return bool(PROP_ITEM_PATTERN.search(body) or PROP_ITEM_PATTERN.search(str(script_text or "")))


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


def first_text_with_prop_extract(*candidates: object) -> str:
    for candidate in candidates:
        text = _clean(candidate)
        if text and prop_extract_has_items(text):
            return text
    return ""


def build_prop_asset_design_brief(adapted_script: str) -> str:
    """Scene-split XOR leftovers that must become independent props."""
    script = _clean(adapted_script)
    if not script or not prop_extract_has_items(script):
        return ""
    body = extract_prop_extract_blocks(script) or script
    preface = (
        "道具资产设计真源。全局统筹已完成独立道具提取："
        "本轮用户侧只注入项目信息 + 本块；禁止把待分析剧本当输入；禁止注入角色提取或角色定妆信息。"
        "已并入角色衣着的配饰不得再画成独立道具；"
        "可归环境陈设的家具装修不得再画成道具；"
        "本块只含过极严门槛、明文全局或载具外部本体的独立道具特征。"
        "禁止重做切场或环境落点；禁止另起同义道具名；定位/作用/外形/尺度/参照主体原样服务四视图。"
        "须承接每条 PROP 的参照主体=名=与长=/高=/宽=及尺度=：有则原样画进第一第二宫；仅空缺才自行补线性图与对参照的长高宽比例。"
        "参照与道具完全隔离、禁止接触。"
        "Subject Index 若仍含 prop 行只作旧稿兼容，不得压过本块。"
    )
    return wrap_injection_section("全局统筹道具提取", f"{preface}\n\n{body}")


def assemble_prop_asset_design_user_content(*parts: object) -> str:
    """Prop extract only. Drop script-to-analyze and any leaked character brief."""
    return assemble_injection_parts(*parts, strip_labels=["待分析剧本", "全局统筹角色提取"])
