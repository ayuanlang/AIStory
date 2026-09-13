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
_MAIN_ENV_HEADER_LINE_RE = re.compile(r"^[ \t]*【主环境】", re.MULTILINE)
_BARE_MAIN_ENV_SECTION_RE = re.compile(
    r"────【主环境】────.*?"
    r"(?=(?:\r?\n────【衍生环境】)|(?:\r?\n\[ENV_BLOCK_END)|(?:\r?\n\[SCENE_CONTENT)|"
    r"(?:\r?\n\[ENV_SCENE_PATCH_END)|(?:\r?\n\[SCENE_END)|$)",
    re.DOTALL | re.IGNORECASE,
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


def text_has_main_env_skeleton(text: str) -> bool:
    """True when the text still carries a real 【主环境】 skeleton, not IDENT-only."""
    source = str(text or "")
    return "────【主环境】" in source or bool(_MAIN_ENV_HEADER_LINE_RE.search(source))


def _wrap_env_block_markers(body: str) -> str:
    text = _clean(body)
    if not text:
        return ""
    if "[ENV_BLOCK_START" not in text.upper():
        text = f"[ENV_BLOCK_START]\n{text}"
    if "[ENV_BLOCK_END" not in text.upper():
        text = f"{text}\n[ENV_BLOCK_END]"
    return text


_ENV_BLOCK_SPLIT_RE = re.compile(r"(?=`?\[ENV_BLOCK_START)", re.IGNORECASE)
_MAIN_ENV_NAME_LINE_RE = re.compile(r"^[ \t]*【主环境】[ \t]*(.+?)\s*$", re.MULTILINE)
_MAIN_ENV_SECTION_SPLIT_RE = re.compile(r"(?=────【主环境】────)")


def _main_env_name_keys(text: str) -> Tuple[str, ...]:
    names: List[str] = []
    seen: set = set()
    for match in _MAIN_ENV_NAME_LINE_RE.finditer(str(text or "")):
        raw = _clean(match.group(1)).split("｜")[0].split("|")[0]
        key = normalize_environment_name(raw)
        if not key or key in seen:
            continue
        seen.add(key)
        names.append(key)
    return tuple(names)


def _env_piece_score(text: str) -> int:
    source = str(text or "")
    score = len(source)
    if "[ENV_BLOCK_START" in source.upper():
        score += 1000
    if "────【主环境】" in source:
        score += 1000
    return score


def _dedupe_inner_main_env_sections(piece: str) -> str:
    text = _clean(piece)
    if text.count("────【主环境】────") <= 1:
        return text
    prefix_parts: List[str] = []
    sections: List[str] = []
    for part in _MAIN_ENV_SECTION_SPLIT_RE.split(text):
        chunk = str(part or "")
        if not chunk.strip():
            continue
        if chunk.lstrip().startswith("────【主环境】"):
            sections.append(chunk)
        else:
            prefix_parts.append(chunk)
    if not sections:
        return text
    best: Dict[Tuple[str, ...], str] = {}
    order: List[Tuple[str, ...]] = []
    for section in sections:
        key = _main_env_name_keys(section) or (re.sub(r"\s+", "", section),)
        if key not in best:
            order.append(key)
        if key not in best or _env_piece_score(section) > _env_piece_score(best[key]):
            best[key] = section
    return "".join(prefix_parts) + "".join(best[key] for key in order)


def _split_env_blocks(block: str) -> List[str]:
    text = _clean(block)
    if not text:
        return []
    if "[ENV_BLOCK_START" in text.upper():
        parts = [part.strip() for part in _ENV_BLOCK_SPLIT_RE.split(text) if part.strip()]
        return [_wrap_env_block_markers(_dedupe_inner_main_env_sections(part)) for part in parts]
    if text_has_main_env_skeleton(text):
        return [_wrap_env_block_markers(_dedupe_inner_main_env_sections(text))]
    return []


def _merge_unique_env_blocks(*blocks: object) -> str:
    pieces: List[str] = []
    for block in blocks:
        pieces.extend(_split_env_blocks(_clean(block)))
    pieces.sort(key=_env_piece_score, reverse=True)
    kept: List[str] = []
    used_names: set = set()
    seen_anonymous: set = set()
    for piece in pieces:
        names = set(_main_env_name_keys(piece))
        if names and names <= used_names:
            continue
        if not names:
            norm = re.sub(r"\s+", "", piece)
            if not norm or norm in seen_anonymous:
                continue
            seen_anonymous.add(norm)
        kept.append(piece)
        used_names.update(names)
    return "\n\n".join(kept).strip()


def extract_main_environment_block(scene_text: str) -> str:
    """IDENT-adjacent 【主环境】/【未落清单】 only; strip derived-env sections."""
    from app.services.script_analysis_flow import extract_env_block_from_scene_text

    source = str(scene_text or "")
    block = extract_env_block_from_scene_text(source).strip()
    if block:
        cleaned = _DERIVED_ENV_SECTION_PATTERN.sub("", block).strip()
        if text_has_main_env_skeleton(cleaned) and (
            "────【主环境】" in cleaned or "────【主环境】" not in source
        ):
            return _merge_unique_env_blocks(cleaned)
    bare_sections = [
        _DERIVED_ENV_SECTION_PATTERN.sub("", match.group(0)).strip()
        for match in _BARE_MAIN_ENV_SECTION_RE.finditer(source)
    ]
    wrapped = [
        _wrap_env_block_markers(body)
        for body in bare_sections
        if text_has_main_env_skeleton(body)
    ]
    return _merge_unique_env_blocks(*wrapped)


def _scene_brief_parts(scene_id: str, scene_text: str, extra_text: str = "") -> List[str]:
    scene = _clean(scene_text)
    extra = _clean(extra_text)
    parts: List[str] = []
    ident = extract_scene_env_ident_block(scene, scene_id) or extract_scene_env_ident_block(extra, scene_id)
    if ident:
        parts.append(ident)
    env_block = _merge_unique_env_blocks(
        extract_main_environment_block(scene),
        extract_main_environment_block(extra),
    )
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


def _append_scene_brief_chunk(
    scene_chunks: List[str],
    scene_id: str,
    scene_text: str,
    extra_text: str = "",
) -> None:
    parts = _scene_brief_parts(scene_id, scene_text, extra_text)
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

    patches = _iter_env_scene_patches(script)
    patch_by_lower = {scene_id.lower(): body for scene_id, body in patches}
    used_patch_keys: set = set()
    scene_chunks: List[str] = []
    if units:
        for unit in units:
            scene_id = _clean(getattr(unit, "scene_id", "") or "")
            scene_text = str(getattr(unit, "scene_text", "") or "")
            patch_body = patch_by_lower.get(scene_id.lower(), "")
            if scene_id and scene_id.lower() in patch_by_lower:
                used_patch_keys.add(scene_id.lower())
            _append_scene_brief_chunk(scene_chunks, scene_id, scene_text, patch_body)

    # Scene units may only have IDENT (split leftover / pipeline-stripped scenes).
    # Always harvest leftover ENV_SCENE_PATCH blocks for the actual 【主环境】骨架.
    for scene_id, body in patches:
        if scene_id.lower() in used_patch_keys:
            continue
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


def _environment_brief_rank(brief: str) -> int:
    text = str(brief or "")
    if not text:
        return -1
    score = 0
    if "[ENV_BLOCK_START" in text.upper():
        score += 4
    if "────【主环境】" in text:
        score += 4
    if text_has_main_env_skeleton(text):
        score += 2
    if "[SCENE_ENV_IDENT_START" in text.upper():
        score += 1
    return score


def pick_environment_plan_source_and_brief(*sources: object) -> Tuple[str, str]:
    """Prefer the source whose brief still has ENV_BLOCK / 【主环境】, not IDENT-only."""
    fallback = ""
    seen: set = set()
    best_source = ""
    best_brief = ""
    best_rank = -1
    for source in sources:
        cleaned = _clean(source)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        if not fallback:
            fallback = cleaned
        brief = build_environment_asset_design_brief(cleaned)
        if not brief:
            continue
        rank = _environment_brief_rank(brief)
        if rank > best_rank:
            best_source, best_brief, best_rank = cleaned, brief, rank
            if rank >= 8:
                return best_source, best_brief
    return (best_source or fallback), best_brief
