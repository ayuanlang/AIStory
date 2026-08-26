# -*- coding: utf-8 -*-
"""Assemble environment-plan excerpts for Stage 3 main-environment design."""
from __future__ import annotations

import re
from typing import List

from app.core.prompt_injection import wrap_injection_section
from app.services.script_analysis_flow.environment_reuse import (
    extract_scene_env_ident_block,
    parse_scene_env_ident_items,
)

_DERIVED_ENV_SECTION_PATTERN = re.compile(
    r"(?:\r?\n)?(?:────【衍生环境】────|【衍生环境】).*?"
    r"(?=(?:\r?\n\[ENV_BLOCK_END)|(?:\r?\n────【)|$)",
    re.DOTALL,
)


def _clean(value: object) -> str:
    return str(value or "").strip()


def environment_plan_has_ident(script_text: str) -> bool:
    return bool(parse_scene_env_ident_items(script_text))


def extract_main_environment_block(scene_text: str) -> str:
    """IDENT-adjacent 【主环境】/【未落清单】 only; strip derived-env sections."""
    from app.services.script_analysis_flow import extract_env_block_from_scene_text

    block = extract_env_block_from_scene_text(scene_text).strip()
    if not block:
        return ""
    return _DERIVED_ENV_SECTION_PATTERN.sub("", block).strip()


def _scene_brief_parts(scene_id: str, scene_text: str) -> List[str]:
    parts: List[str] = []
    ident = extract_scene_env_ident_block(scene_text)
    if ident:
        parts.append(ident)
    env_block = extract_main_environment_block(scene_text)
    if env_block:
        parts.append(env_block)
    return parts


def build_environment_asset_design_brief(adapted_script: str) -> str:
    """Per-scene IDENT + 主环境骨架；不含场核、Beat、衍生提取。"""
    script = _clean(adapted_script)
    if not script:
        return ""

    from app.services.script_analysis_flow import parse_scene_units_from_markers

    try:
        units = parse_scene_units_from_markers(script)
    except Exception:
        units = []

    scene_chunks: List[str] = []
    if units:
        for unit in units:
            scene_id = _clean(getattr(unit, "scene_id", "") or "")
            scene_text = str(getattr(unit, "scene_text", "") or "")
            parts = _scene_brief_parts(scene_id, scene_text)
            if not parts:
                continue
            header = f"[ENV_DESIGN_SCENE:{scene_id}]" if scene_id else "[ENV_DESIGN_SCENE]"
            scene_chunks.append("\n".join([header, *parts]))
    else:
        parts = _scene_brief_parts("", script)
        if parts:
            scene_chunks.append("\n".join(parts))

    if not scene_chunks:
        return ""

    body = "\n\n".join(scene_chunks).strip()
    preface = (
        "主环境资产设计真源。按场覆盖 IDENT 已识别主环境 +【主环境】/【未落清单】骨架。"
        "本轮只设计主环境四向拼图；禁止输出视角衍生或状态衍生。"
        "禁止重做场景勘探；禁止另起同义主环境名；定位/目标/情绪表达原样服务四向拼图。"
        "不要等待逐场分析。Subject Index 若仍含 environment 行只作旧稿兼容，不得压过本块。"
    )
    return wrap_injection_section("环境规划", f"{preface}\n\n{body}")
