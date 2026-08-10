# -*- coding: utf-8 -*-
"""Text shaping helpers for analyze_scene stage inputs/outputs."""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from app.core.prompt_injection import unwrap_injection_section, wrap_injection_section
from app.services.llm_markdown_sanitize import sanitize_subject_index_text
from app.services.script_analysis_flow import (
    SCENES_BLOCK_END_TOKEN,
    SCENES_BLOCK_START_TOKEN,
    extract_entity_profile_block_from_adapted,
)

logger = logging.getLogger("api_logger")

def _trim_to_scenes_block(raw_text: Any) -> str:
    """Trim to SCENES_BLOCK, preserving leading `[ENTITY_PROFILE_START]…[ENTITY_PROFILE_END]` when present."""
    text = str(raw_text or "")
    if not text.strip():
        return ""
    start_idx = text.find(SCENES_BLOCK_START_TOKEN)
    if start_idx < 0:
        return text
    end_idx = text.find(SCENES_BLOCK_END_TOKEN, start_idx + len(SCENES_BLOCK_START_TOKEN))
    if end_idx < 0:
        scenes_block = text[start_idx:].lstrip()
    else:
        scenes_block = text[start_idx:end_idx + len(SCENES_BLOCK_END_TOKEN)].strip()
    entity_profile = extract_entity_profile_block_from_adapted(text[:start_idx])
    if entity_profile:
        return f"{entity_profile}\n{scenes_block}".strip()
    return scenes_block

def _normalize_subject_index_entity_type(raw_type: Any) -> str:
    t = str(raw_type or "").strip().lower()
    if t in {"character", "characters", "char", "人物", "角色"}:
        return "character"
    if t in {"prop", "props", "item", "items", "道具", "物件"}:
        return "prop"
    if t in {"environment", "environments", "env", "scene", "scenes", "场景", "环境"}:
        return "environment"
    if t in {"cover", "covers", "poster", "posters", "cover_poster", "封面", "封面海报", "海报"}:
        return "cover"
    return ""

def _normalize_requested_asset_target_type(raw_type: Any) -> str:
    t = str(raw_type or "").strip().lower().replace("-", "_")
    if t in {"character", "characters", "char", "role", "roles", "人物", "角色"}:
        return "character"
    if t in {"prop", "props", "item", "items", "object", "objects", "道具", "物件"}:
        return "prop"
    if t in {"environment", "environments", "env", "scene", "scenes", "场景", "环境"}:
        return "environment"
    if t in {"cover", "covers", "poster", "posters", "cover_poster", "封面", "封面海报", "海报"}:
        return "cover"
    return ""

def _strip_embedded_subject_index_from_stage_text(raw_text: Any) -> str:
    text = str(raw_text or "")
    if not text.strip():
        return ""

    # Frontend Stage 2.2 handoff wrapper (legacy); backend injects Subject Index once from episode data.
    text = re.sub(
        r"(?is)\[Subject Index开始\]\s*.*?\s*\[Subject Index结束\]\s*",
        "",
        text,
    ).strip()
    text = re.sub(
        r"(?is)^\s*\[Stage\s*2[\-_]\s*1\s+Subject\s*Index[^\]]*\].*?```subject_index\s*.*?```\s*",
        "",
        text,
    ).strip()
    text = re.sub(
        r"(?is)```subject_index\s*.*?```\s*",
        "",
        text,
    ).strip()

    marker_patterns = [
        r"(?im)^\s*#{1,6}\s*【上游提取的资产清单\s*Subject\s*Index】\s*$",
        r"(?im)^\s*#{1,6}\s*Subject\s*Index\s*$",
        r"(?im)^\s*#{1,6}\s*【.*Subject\s*Index.*】\s*$",
        r"(?im)^\s*\[Stage\s*2[\-_]\s*1\s+Subject\s*Index[^\]]*\]\s*$",
        r"(?im)^\s*\[Saved Subject Index Injection[^\]]*\]\s*$",
        r"(?im)^\s*\[Upstream Subject Index Injection[^\]]*\]\s*$",
    ]
    cut_positions: List[int] = []
    for pattern in marker_patterns:
        match = re.search(pattern, text)
        if match:
            cut_positions.append(int(match.start()))

    delimiter = "----------------*****--------------"
    delimiter_idx = text.find(delimiter)
    if delimiter_idx >= 0:
        cut_positions.append(int(delimiter_idx))

    if not cut_positions:
        return text.strip()
    return text[:min(cut_positions)].strip()

def _extract_embedded_subject_index_from_stage_text(raw_text: Any) -> str:
    text = sanitize_subject_index_text(raw_text)
    if not text:
        return ""
    has_index_markers = bool(
        re.search(r"(?i)\bsubject_no\b", text)
        or re.search(r"(?i)\bsubject_type\b", text)
        or re.search(r"(?im)^\s*\|?\s*S\d{3,}\s*\|", text)
        or re.search(r"(?im)^\s*S\d{3,}\s*\|", text)
    )
    return text if has_index_markers else ""

def _unwrap_script_to_analyze(raw_text: Any) -> str:
    text = str(raw_text or "")
    if not text.strip():
        return ""

    wrapped_script = unwrap_injection_section(text, "待分析剧本")
    if wrapped_script:
        marker = "Script to Analyze:"
        if marker in wrapped_script:
            idx = wrapped_script.rfind(marker)
            if idx >= 0:
                return wrapped_script[idx + len(marker):].strip()
        return wrapped_script.strip()

    marker = "Script to Analyze:"
    if marker not in text:
        return text.strip()
    # Keep the innermost payload when wrappers are nested.
    idx = text.rfind(marker)
    if idx < 0:
        return text.strip()
    return text[idx + len(marker):].strip()

def _collapse_exact_duplicated_text(raw_text: Any) -> str:
    text = str(raw_text or "").strip()
    if not text:
        return ""
    lines = [line.rstrip() for line in text.splitlines()]
    if len(lines) >= 8 and len(lines) % 2 == 0:
        half = len(lines) // 2
        left = "\n".join(lines[:half]).strip()
        right = "\n".join(lines[half:]).strip()
        if left and right and left == right:
            return left
    return text

def _sanitize_scene_beats_stage_text(raw_text: Any) -> str:
    text = str(raw_text or "")
    if not text.strip():
        return ""
    text = _unwrap_script_to_analyze(text)
    text = _strip_embedded_subject_index_from_stage_text(text)
    text = _collapse_exact_duplicated_text(text)
    return text.strip()

def _build_script_to_analyze_block(script_body: Any) -> str:
    text = str(script_body or "").strip()
    if not text:
        return ""
    # Frontend Stage 1 may already wrap project context + script sections.
    if "[待分析剧本开始]" in text:
        return text
    return wrap_injection_section(
        "待分析剧本",
        f"Script to Analyze:\n\n{text}",
    )

def _extract_reuse_assets_from_subject_index(subject_index_text: str) -> List[Dict[str, Any]]:
    assets: List[Dict[str, Any]] = []
    text = sanitize_subject_index_text(subject_index_text)
    if not text:
        return assets
    for raw_line in str(text).splitlines():
        line = str(raw_line or "").replace("\ufeff", "").strip()
        line = re.sub(r"^\s*>\s*", "", line)
        line = re.sub(r"^\s*[-*+]\s+", "", line).strip()
        if not re.match(r"^\|?\s*S\d+\s*\|", line, flags=re.IGNORECASE):
            continue
        normalized_line = line.strip("|").strip()
        parts = [p.strip() for p in normalized_line.split("|")]
        if len(parts) < 4:
            continue
        subject_type = str(parts[1] or "").strip().lower()
        name_zh = str(parts[2] or "").strip()
        name_en = str(parts[3] or "").strip()
        asset_name = name_zh or name_en
        if not asset_name:
            continue
        mapped_type = ""
        if subject_type in {"character", "characters", "char", "人物", "角色"}:
            mapped_type = "character"
        elif subject_type in {"prop", "props", "道具", "物件"}:
            mapped_type = "prop"
        elif subject_type in {"environment", "environments", "env", "场景", "环境"}:
            mapped_type = "environment"
        elif subject_type in {"cover", "covers", "poster", "posters", "cover_poster", "封面", "封面海报"}:
            mapped_type = "cover"
        if not mapped_type:
            continue
        assets.append({
            "name": asset_name,
            "type": mapped_type,
            "description": str(parts[5] or "").strip() if len(parts) > 5 else "",
        })
    return assets

def _infer_subject_index_allowed_types_for_request(
    *,
    request: Any = None,
    mode_lower: str = "",
    prompt_file_lower: str = "",
    scene_analysis_features: Any = None,
) -> set:
    feature_targets: List[Any] = []
    features = scene_analysis_features
    if features is None and request is not None:
        features = getattr(request, "scene_analysis_features", None)
    if isinstance(features, dict):
        raw_targets = (
            features.get("target_entity_types")
            or features.get("targetEntityTypes")
            or features.get("asset_target_types")
            or features.get("assetTargetTypes")
        )
        if isinstance(raw_targets, list):
            feature_targets = raw_targets
        elif isinstance(raw_targets, str):
            feature_targets = [part for part in re.split(r"[,，\s]+", raw_targets) if part]

    if feature_targets:
        normalized_targets = {
            normalized
            for normalized in (_normalize_requested_asset_target_type(item) for item in feature_targets)
            if normalized
        }
        if normalized_targets:
            return normalized_targets

    source = f"{mode_lower} {prompt_file_lower}"
    target_suffix_match = re.search(r"__targets_([a-z0-9_\-]+)", source, flags=re.IGNORECASE)
    if target_suffix_match:
        normalized_targets = {
            normalized
            for normalized in (
                _normalize_requested_asset_target_type(item)
                for item in str(target_suffix_match.group(1) or "").split("_")
            )
            if normalized
        }
        if normalized_targets:
            return normalized_targets

    if "2_pass_generate_assets_characters" in source or "entity_design_character" in source:
        return {"character"}
    if "2_pass_generate_assets_props" in source or "entity_design_prop" in source:
        return {"prop"}
    if (
        "2_pass_generate_assets_environments" in source
        or "entity_design_environment" in source
        or "entity_design_poster" in source
    ):
        return {"environment", "cover"}
    return set()

def _filter_subject_index_text_by_types(
    subject_index_text: Any,
    allowed_types: set,
    *,
    log_mode: Any = None,
    log_prompt_file: Any = None,
) -> str:
    text = sanitize_subject_index_text(subject_index_text)
    if not text or not allowed_types:
        return text

    filtered_lines: List[str] = []
    total_subject_rows = 0
    kept_subject_rows = 0
    for raw_line in str(text).splitlines():
        line = str(raw_line or "")
        stripped = line.strip()
        key_value_type_match = re.search(r"\bsubject_type\s*=\s*([^|`\n]+)", stripped, flags=re.IGNORECASE)
        key_value_subject_match = re.search(r"\bsubject_no\s*=\s*([^|`\n]+)", stripped, flags=re.IGNORECASE)
        if key_value_type_match and (key_value_subject_match or re.search(r"\bsubject_name_(?:zh|en|exact)\s*=", stripped, flags=re.IGNORECASE)):
            total_subject_rows += 1
            normalized_type = _normalize_subject_index_entity_type(key_value_type_match.group(1))
            if normalized_type in allowed_types:
                filtered_lines.append(line)
                kept_subject_rows += 1
            continue

        normalized_line = stripped.replace("\ufeff", "").strip()
        normalized_line = re.sub(r"^\s*>\s*", "", normalized_line)
        normalized_line = re.sub(r"^\s*[-*+]\s+", "", normalized_line).strip()
        normalized_line = normalized_line.strip("|").strip()
        parts = [p.strip() for p in normalized_line.split("|")]
        is_subject_row = bool(re.match(r"^S\d+\b", normalized_line, flags=re.IGNORECASE)) and len(parts) >= 2
        if is_subject_row:
            total_subject_rows += 1
            normalized_type = _normalize_subject_index_entity_type(parts[1] if len(parts) > 1 else "")
            if normalized_type in allowed_types:
                filtered_lines.append(line)
                kept_subject_rows += 1
            continue
        filtered_lines.append(line)

    filtered_text = "\n".join(filtered_lines).strip()
    logger.info(
        "[analyze_scene] filtered subject index for target types types=%s rows=%s kept=%s mode=%s prompt_file=%s",
        sorted(allowed_types),
        total_subject_rows,
        kept_subject_rows,
        log_mode,
        log_prompt_file,
    )
    return filtered_text


def _resolve_scene_beats_adapted_script_text(
    raw_text: Any,
    episode_adaptation_fallback: str = "",
) -> str:
    from app.services.script_analysis_flow import extract_adapted_script_from_beats_user_input

    adapted = extract_adapted_script_from_beats_user_input(
        _sanitize_scene_beats_stage_text(raw_text)
    )
    if adapted:
        return adapted
    if episode_adaptation_fallback:
        return str(episode_adaptation_fallback)
    return ""

