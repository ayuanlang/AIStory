# -*- coding: utf-8 -*-
"""Assemble environment-plan excerpts for Stage 3 main-environment design."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from app.core.prompt_injection import assemble_injection_parts, wrap_injection_section
from app.services.script_analysis_flow.environment_reuse import (
    extract_scene_env_ident_block,
    normalize_environment_name,
    parse_scene_env_ident_items,
)

_DERIVED_ENV_SECTION_PATTERN = re.compile(
    r"(?:\r?\n)?(?:────【衍生环境】────|【衍生环境】).*?"
    r"(?=(?:\r?\n\[ENV_BLOCK_END)|(?:\r?\n────【)|$)",
    re.DOTALL,
)
_ENV_SCENE_PATCH_PATTERN = re.compile(
    r"`?\[ENV_SCENE_PATCH_START:([^\s\]]+)\]`?"
    r"(.*?)"
    r"`?\[ENV_SCENE_PATCH_END:([^\s\]]+)\]`?",
    re.IGNORECASE | re.DOTALL,
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
    ident = extract_scene_env_ident_block(scene_text, scene_id)
    if ident:
        parts.append(ident)
    env_block = extract_main_environment_block(scene_text)
    if env_block:
        parts.append(env_block)
    return parts


def _iter_env_scene_patches(script_text: str) -> List[Tuple[str, str]]:
    """Lenient ENV_SCENE_PATCH walker; skip malformed pairs instead of raising."""
    patches: List[Tuple[str, str]] = []
    seen = set()
    for match in _ENV_SCENE_PATCH_PATTERN.finditer(str(script_text or "")):
        start_id = _clean(match.group(1))
        end_id = _clean(match.group(3))
        body = _clean(match.group(2))
        if not start_id or not body:
            continue
        if end_id and start_id.lower() != end_id.lower():
            continue
        key = start_id.lower()
        if key in seen:
            continue
        seen.add(key)
        patches.append((start_id, body))
    return patches


_DERIVED_ENV_NAME_RE = re.compile(r"^\d+\s*度")


def collect_ident_environment_names(script_text: str) -> List[str]:
    """Unique IDENT names in first-seen exact spelling."""
    names: List[str] = []
    seen: set = set()
    for item in parse_scene_env_ident_items(script_text):
        name = _clean(item.get("name"))
        key = normalize_environment_name(name)
        if not name or key in seen:
            continue
        seen.add(key)
        names.append(name)
    return names


def _is_derived_environment_name(name: str) -> bool:
    return bool(_DERIVED_ENV_NAME_RE.match(_clean(name)))


def _rewrite_environment_item_name(item: Dict[str, Any], old_name: str, new_name: str) -> None:
    item["name"] = new_name
    old = _clean(old_name)
    new = _clean(new_name)
    if not old or old == new:
        return
    deps = item.get("visual_dependencies")
    if isinstance(deps, list):
        item["visual_dependencies"] = [
            dep.replace(f"ENV:[{old}]", f"ENV:[{new}]") if isinstance(dep, str) else dep
            for dep in deps
        ]
    for field in ("generation_prompt_cn", "anchor_description"):
        value = item.get(field)
        if not isinstance(value, str) or old not in value:
            continue
        item[field] = (
            value.replace(f"所属主环境={old}", f"所属主环境={new}")
            .replace(f"「{old}」", f"「{new}」")
        )
    strategy = item.get("dependency_strategy")
    if isinstance(strategy, dict):
        logic = strategy.get("logic")
        if isinstance(logic, str) and old in logic:
            strategy["logic"] = logic.replace(f"所属主环境={old}", f"所属主环境={new}")


def align_environment_json_names_with_ident(
    subjects_json: Dict[str, Any],
    script_text: str,
) -> Dict[str, Any]:
    """Force environments[].name onto IDENT 名称=/name exact spelling."""
    if not isinstance(subjects_json, dict):
        return subjects_json
    ident_names = collect_ident_environment_names(script_text)
    environments = subjects_json.get("environments")
    if not ident_names or not isinstance(environments, list):
        return subjects_json

    ident_by_key = {normalize_environment_name(name): name for name in ident_names}
    used_keys: set = set()
    for item in environments:
        if not isinstance(item, dict):
            continue
        name = _clean(item.get("name"))
        if not name or _is_derived_environment_name(name):
            continue
        key = normalize_environment_name(name)
        canonical = ident_by_key.get(key)
        if not canonical:
            continue
        if name != canonical:
            _rewrite_environment_item_name(item, name, canonical)
        used_keys.add(key)

    leftover = [name for name in ident_names if normalize_environment_name(name) not in used_keys]
    unmatched = []
    for item in environments:
        if not isinstance(item, dict):
            continue
        name = _clean(item.get("name"))
        if not name or _is_derived_environment_name(name):
            continue
        if normalize_environment_name(name) in ident_by_key:
            continue
        unmatched.append(item)
    if len(leftover) == 1 and len(unmatched) == 1:
        old = _clean(unmatched[0].get("name"))
        _rewrite_environment_item_name(unmatched[0], old, leftover[0])
    return subjects_json


def _append_scene_brief_chunk(scene_chunks: List[str], scene_id: str, scene_text: str) -> None:
    parts = _scene_brief_parts(scene_id, scene_text)
    if not parts:
        return
    header = f"[ENV_DESIGN_SCENE:{scene_id}]" if scene_id else "[ENV_DESIGN_SCENE]"
    scene_chunks.append("\n".join([header, *parts]))


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
            _append_scene_brief_chunk(scene_chunks, scene_id, scene_text)

    # Asset rerun concatenates scene_split (SCENE markers, no plan) + environment_plan
    # patches after SCENES_BLOCK_END. Scene units then have no IDENT/【主环境】.
    if not scene_chunks:
        for scene_id, body in _iter_env_scene_patches(script):
            _append_scene_brief_chunk(scene_chunks, scene_id, body)

    if not scene_chunks:
        _append_scene_brief_chunk(scene_chunks, "", script)

    if not scene_chunks:
        return ""

    body = "\n\n".join(scene_chunks).strip()
    preface = (
        "主环境资产设计真源。按场覆盖 IDENT 已识别主环境 +【主环境】/【未落清单】骨架。"
        "本轮用户侧只注入项目信息 + 本块 + 封面海报简报；禁止把待分析剧本当输入。"
        "本轮只设计主环境四向拼图；禁止输出视角衍生或状态衍生。"
        "禁止重做场景勘探；禁止另起同义主环境名；"
        "environments[].name 必须与 IDENT [ENV] 名称= / name 逐字符完全一致；"
        "定位/目标/情绪表达原样服务四向拼图。"
        "严格遵守【主环境】对表演区/活动空间的空间要求：四面只深化规划已列围合；"
        "中区默认空区无障碍，仅规划明文要求桌椅等主体时才落，禁止擅自增加主体。"
        "不要等待逐场分析。Subject Index 若仍含 environment 行只作旧稿兼容，不得压过本块。"
    )
    return wrap_injection_section("环境规划", f"{preface}\n\n{body}")


def assemble_environment_asset_design_user_content(*parts: object) -> str:
    """Cover brief + environment plan only. Strip any leaked script-to-analyze block."""
    return assemble_injection_parts(*parts)


def pick_environment_plan_source_and_brief(*sources: object) -> Tuple[str, str]:
    """Return the first source that yields a main-env brief, plus that brief."""
    fallback = ""
    seen: set = set()
    for source in sources:
        cleaned = _clean(source)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        if not fallback:
            fallback = cleaned
        brief = build_environment_asset_design_brief(cleaned)
        if brief:
            return cleaned, brief
    return fallback, ""
