# -*- coding: utf-8 -*-
"""Programmatic cover-poster brief after assets_extraction is retired."""
from __future__ import annotations

import re
from typing import List

from app.core.prompt_injection import wrap_injection_section
from app.services.script_analysis_flow.character_asset_brief import CHAR_ITEM_PATTERN
from app.services.script_analysis_flow.environment_reuse import (
    SCENE_ENV_IDENT_PATTERN,
    parse_scene_env_ident_items,
)
from app.services.subject_index_resolve import extract_project_visual_backfill_object

_MOOD_LINE_PATTERN = re.compile(
    r"情绪表达\s*=\s*([^\r\n]+)",
    re.IGNORECASE,
)
_POSITION_LINE_PATTERN = re.compile(
    r"定位\s*=\s*([^\r\n]+)",
    re.IGNORECASE,
)


def _clean(value: object) -> str:
    return str(value or "").strip()


def _first_nonempty(*values: object) -> str:
    for value in values:
        text = _clean(value)
        if text:
            return text
    return ""


def _char_names(script_text: str, limit: int = 3) -> List[str]:
    names: List[str] = []
    seen = set()
    for match in CHAR_ITEM_PATTERN.finditer(str(script_text or "")):
        raw = _clean(match.group(1)).split("｜", 1)[0].split("|", 1)[0].strip()
        if not raw or raw in seen or raw == "无":
            continue
        seen.add(raw)
        names.append(raw)
        if len(names) >= limit:
            break
    return names


def _env_highlights(script_text: str, limit: int = 2) -> List[str]:
    highlights: List[str] = []
    seen = set()
    for match in SCENE_ENV_IDENT_PATTERN.finditer(str(script_text or "")):
        body = str(match.group(2) or "")
        items = parse_scene_env_ident_items(match.group(0))
        name = _clean((items[0] or {}).get("name")) if items else ""
        mood_match = _MOOD_LINE_PATTERN.search(body)
        pos_match = _POSITION_LINE_PATTERN.search(body)
        mood = _clean(mood_match.group(1) if mood_match else "")
        position = _clean(pos_match.group(1) if pos_match else "")
        if not name and not mood and not position:
            continue
        key = (name, mood, position)
        if key in seen:
            continue
        seen.add(key)
        parts = [part for part in (name, position, mood) if part]
        highlights.append("／".join(parts))
        if len(highlights) >= limit:
            break
    return highlights


def _backfill_line(script_text: str) -> str:
    backfill = extract_project_visual_backfill_object(script_text) or {}
    if not isinstance(backfill, dict):
        return ""
    style = _first_nonempty(backfill.get("Global_Style"), backfill.get("global_style"))
    tone = _clean(backfill.get("tone"))
    lighting = _clean(backfill.get("lighting"))
    plot = _first_nonempty(backfill.get("comprehensive_plot"), backfill.get("plot_summary"))
    assets = _clean(backfill.get("comprehensive_assets"))
    parts = []
    if style:
        parts.append(f"全局风格={style}")
    if tone:
        parts.append(f"影调={tone}")
    if lighting:
        parts.append(f"光线={lighting}")
    if plot:
        parts.append(f"综合剧情={plot}")
    if assets:
        parts.append(f"综合资产={assets}")
    return "；".join(parts)


def build_cover_poster_brief(script_text: str) -> str:
    """Composition brief for posters[]; no LLM Subject Index required."""
    script = _clean(script_text)
    if not script:
        return ""
    chars = _char_names(script)
    envs = _env_highlights(script)
    backfill = _backfill_line(script)
    if not chars and not envs and not backfill:
        return ""
    char_line = "，".join(chars) if chars else "无"
    env_line = "，".join(envs) if envs else "无"
    preface = (
        "封面海报构图简报。环境规划完成后由程序汇总，不再经过资产清单节点。"
        "只服务 `posters[]`：选 1–2 个主环境气质与 1–3 个主角做宣发构图；"
        "禁止另起角色/道具/环境资产行；无简报则 posters=[]。"
    )
    body = (
        f"{preface}\n\n"
        f"主角候选：{char_line}\n"
        f"主环境气质：{env_line}"
    )
    if backfill:
        body = f"{body}\n视觉基线：{backfill}"
    return wrap_injection_section("封面海报简报", body)
