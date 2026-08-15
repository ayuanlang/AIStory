# -*- coding: utf-8 -*-
"""Shot-generation prompt building, validation, and staging persist helpers."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.entity_token import (
    normalize_entity_token,
    subject_compare_key,
    subject_compare_key_variants,
)
from app.core.prompt_injection import wrap_injection_section
from app.core.prompts.shot_generation_feature_skills import (
    get_shot_generation_feature_catalog,
    render_shot_generation_routed_prompt,
    resolve_shot_generation_feature_bundle,
)
from app.core.time_utils import now_bj_iso
from app.models.all_models import Entity, Episode, Project, Scene
from app.api.settings import get_scene_analysis_system_config
from app.services.llm_markdown_sanitize import (
    sanitize_llm_markdown_output,
    sanitize_subject_index_text,
)
from app.services.prompt_resolve import _resolve_prompt_text
from app.services.scene_no_utils import _scene_no_lookup_keys
from app.services.scene_subject_helpers import _normalize_subject_entity_type
from app.services.shot_markdown import (
    _is_provider_moderation_block_response,
    _pick_shot_cell,
    _validate_shot_rows_for_apply_with_tolerance,
    _validate_shot_rows_or_raise,
    parse_shots_markdown_table,
    sanitize_shots_markdown_table_text,
)
from app.services.soft_delete import _active_episode_clause, _active_entity_clause, _active_scene_clause

logger = logging.getLogger("api_logger")

DEFAULT_MAX_SHOT_SECONDS = 15
MIN_SHOT_DURATION_SECONDS = 4


def _parse_max_shot_seconds(raw: Any) -> int:
    """Resolve 分镜最长秒数; missing/invalid → 15. Floor is 4s (shot minimum)."""
    text = str(raw or "").strip()
    if not text:
        return DEFAULT_MAX_SHOT_SECONDS
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if not match:
        return DEFAULT_MAX_SHOT_SECONDS
    try:
        value = int(round(float(match.group(1))))
    except Exception:
        return DEFAULT_MAX_SHOT_SECONDS
    if value <= 0:
        return DEFAULT_MAX_SHOT_SECONDS
    return max(MIN_SHOT_DURATION_SECONDS, value)


def _strip_ai_shots_reasoning_prefix_lines(response_content: Any, *, context: str) -> str:
    reasoning_prefix_terms = [
        "i will",
        "let me",
        "let's",
        "analysis",
        "reasoning",
        "thought process",
        "分析",
        "思路",
        "推理",
        "我将",
        "我认为",
        "我認為",
    ]
    try:
        escaped_terms = [re.escape(term) for term in reasoning_prefix_terms if str(term or "").strip()]
        reasoning_line_re = re.compile(
            r"^\s*(?:" + "|".join(escaped_terms) + r")\b",
            flags=re.IGNORECASE,
        )
    except re.error as re_err:
        logger.warning("[%s] reasoning regex compile failed, fallback used: %s", context, re_err)
        reasoning_line_re = re.compile(r"^\s*(?:analysis|reasoning)\b", flags=re.IGNORECASE)

    cleaned_lines = []
    for line in str(response_content or "").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("|") and reasoning_line_re.match(stripped):
            continue
        cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()


def _build_ai_shots_response_validator(
    *,
    context: str,
    scene_id: int,
    user_id: int,
    source_label: str,
    strip_reasoning_prefixes: bool = False,
    validate_regenerate_markers: bool = False,
):
    def _validator(response_dict: Dict[str, Any], candidate_config: Dict[str, Any]):
        provider = str((candidate_config or {}).get("provider") or "").strip()
        model = str((candidate_config or {}).get("model") or "").strip()
        response_content_raw = response_dict.get("content", "") if isinstance(response_dict, dict) else ""
        raw_str = str(response_content_raw or "").strip()
        route_label = f"{provider}/{model}" if provider or model else "unknown provider"

        if str(response_content_raw).startswith("Error:"):
            return False, str(response_content_raw), None
        if not raw_str:
            return False, "LLM returned empty response", None

        response_content = sanitize_llm_markdown_output(response_content_raw)
        if _is_provider_moderation_block_response(raw_str, response_content):
            return False, f"Provider moderation blocked {source_label.lower()} (PROHIBITED_CONTENT)", None

        if strip_reasoning_prefixes:
            response_content = _strip_ai_shots_reasoning_prefix_lines(response_content, context=context)

        response_content = sanitize_shots_markdown_table_text(response_content)
        if not response_content:
            return False, "LLM response became empty after sanitize", None

        headers, rows, table_line_count = parse_shots_markdown_table(response_content)
        if not rows:
            raw_preview = response_content.replace("\n", " ")[:300]
            return False, f"{source_label} returned 0 parsed rows; raw preview: {raw_preview}", None
        if table_line_count >= 4 and len(rows) > 0 and (len(rows) * 2) <= table_line_count:
            return False, f"{source_label} output may have lost rows during markdown parsing", None

        # Require at least one structurally applyable row (Video Content present).
        # Without this, Logic-only / column-shifted tables pass parse and only fail
        # later in execute_ai_generate_shots — skipping LLM fallback retries.
        try:
            applyable_rows, apply_skipped = _validate_shot_rows_for_apply_with_tolerance(
                rows,
                source_label=source_label,
                status_code=502,
            )
        except HTTPException as exc:
            return False, str(exc.detail or f"{source_label} failed structural validation"), None
        if apply_skipped:
            logger.warning(
                "[%s] draft structural warnings scene_id=%s skipped=%s details=%s",
                context,
                scene_id,
                len(apply_skipped),
                apply_skipped[:5],
            )
        rows = applyable_rows

        validated_rows = rows
        if validate_regenerate_markers:
            try:
                validated_rows = _validate_shot_rows_or_raise(
                    rows,
                    source_label="Regenerated shot diff table",
                    status_code=502,
                )
            except HTTPException as exc:
                return False, str(exc.detail or "Regenerated shot diff table validation failed"), None

            marker_errors: List[str] = []
            for idx, row in enumerate(validated_rows, start=1):
                shot_id = _pick_shot_cell(row, ["Shot ID", "shot_id", "镜头ID"], "")
                shot_logic = _pick_shot_cell(row, ["Shot Logic (CN)", "shot_logic_cn", "镜头逻辑", "镜头逻辑（中文）"], "")
                marker_mode, _ = _extract_shot_regenerate_marker(shot_logic)
                if marker_mode not in {"update", "add"}:
                    marker_errors.append(f"row {idx} ({shot_id or 'unknown shot'}) missing required Shot Logic marker")
                    continue
                if marker_mode == "add" and not re.search(r"_\d+$", str(shot_id or "")):
                    marker_errors.append(f"row {idx} ({shot_id or 'unknown shot'}) add-shot id must use _1/_2 style suffix")

            if marker_errors:
                detail = "; ".join(marker_errors[:5])
                if len(marker_errors) > 5:
                    detail += f"; and {len(marker_errors) - 5} more rows"
                return False, f"Regenerated shot diff failed marker validation: {detail}", None

        logger.info(
            "[%s] postprocess validation passed scene_id=%s user_id=%s route=%s parsed_rows=%s",
            context,
            scene_id,
            user_id,
            route_label,
            len(validated_rows),
        )
        return True, "", {
            "raw_text_original": str(response_content_raw or ""),
            "response_content": response_content,
            "headers": headers,
            "rows": validated_rows,
            "table_line_count": table_line_count,
        }

    return _validator

def _map_shared_prompt_mode_to_shot_generation_mode(raw_mode: Any) -> Optional[str]:
    normalized = str(raw_mode or "").strip().lower().replace("-", "_")
    aliases = {
        "original": "classic",
        "base": "classic",
        "classic": "classic",
        "routed": "routed",
        "feature_stack": "routed",
        "decision_engine": "routed",
        "decisionengine": "routed",
        "skills": "routed",
        "skill_engine": "routed",
        "skillengine": "routed",
    }
    return aliases.get(normalized)


def _resolve_effective_shot_generation_mode(
    db: Session,
    *,
    requested_mode: Optional[str] = None,
    project_metadata: Optional[Dict[str, Any]] = None,
    log_context: str = "shot-generation",
) -> Optional[str]:
    explicit_mode = _map_shared_prompt_mode_to_shot_generation_mode(requested_mode)
    if explicit_mode:
        return explicit_mode

    try:
        shared_system_mode = _map_shared_prompt_mode_to_shot_generation_mode(
            get_scene_analysis_system_config(db).get("default_mode")
        )
        if shared_system_mode:
            return shared_system_mode
    except Exception as config_err:
        logger.warning("[%s] failed to read shared scene-analysis mode for shot generation: %s", log_context, config_err)

    metadata = project_metadata if isinstance(project_metadata, dict) else {}
    for key in ("shot_generation_mode", "shot_prompt_mode", "prompt_mode", "default_mode"):
        candidate = _map_shared_prompt_mode_to_shot_generation_mode(metadata.get(key))
        if candidate:
            return candidate

    return None


def _build_project_prompt_context(project_info_input: Any) -> Dict[str, Any]:
    project_info = project_info_input or {}
    if isinstance(project_info, str):
        try:
            project_info = json.loads(project_info)
        except Exception:
            project_info = {}
    if not isinstance(project_info, dict):
        project_info = {}

    basic_info_nested = project_info.get("basic_information") if isinstance(project_info.get("basic_information"), dict) else {}
    e_global_info = project_info.get("e_global_info") if isinstance(project_info.get("e_global_info"), dict) else {}
    story_input = project_info.get("story_generator_global_input") if isinstance(project_info.get("story_generator_global_input"), dict) else {}
    context_sources = [project_info, basic_info_nested, e_global_info, story_input]

    def _norm_key(key: Any) -> str:
        return str(key or "").strip().lower().replace("-", "_").replace(" ", "_")

    def _normalize_dict_keys(d: Any) -> Dict[str, Any]:
        if not isinstance(d, dict):
            return {}
        return {_norm_key(k): v for k, v in d.items()}

    context_sources_norm = [_normalize_dict_keys(src) for src in context_sources]

    def _clean_text(value: Any) -> str:
        return str(value or "").strip()

    def get_context_val(keys, allow_structured: bool = False):
        if isinstance(keys, str):
            keys = [keys]
        search_keys = [_norm_key(k) for k in keys]
        for src_norm in context_sources_norm:
            for sk in search_keys:
                if sk not in src_norm:
                    continue
                value = src_norm.get(sk)
                if allow_structured:
                    if isinstance(value, (dict, list)) and value:
                        return value
                    text = _clean_text(value)
                    if text:
                        return value
                else:
                    if isinstance(value, (dict, list)):
                        continue
                    text = _clean_text(value)
                    if text:
                        return text
        return {} if allow_structured else ""

    def get_context_list(keys) -> List[str]:
        value = get_context_val(keys, allow_structured=True)
        if isinstance(value, list):
            return [str(v or "").strip() for v in value if str(v or "").strip()]
        if isinstance(value, str):
            return [p.strip() for p in re.split(r"[,，;；\n]", value) if p and p.strip()]
        return []

    tech_params = get_context_val(["tech_params"], allow_structured=True)
    if not isinstance(tech_params, dict):
        tech_params = {}
    visual_standard = tech_params.get("visual_standard") or tech_params.get("visual standard") or {}
    if not isinstance(visual_standard, dict):
        visual_standard = {}
    visual_standard_norm = _normalize_dict_keys(visual_standard)

    def get_visual_val(keys) -> str:
        if isinstance(keys, str):
            keys = [keys]
        search_keys = [_norm_key(k) for k in keys]
        for sk in search_keys:
            if sk in visual_standard_norm:
                value = visual_standard_norm.get(sk)
                if isinstance(value, (dict, list)):
                    continue
                text = _clean_text(value)
                if text:
                    return text
        return get_context_val(keys)

    global_style = get_context_val(["global_style", "Global_Style", "Global Style", "Style"]) or "Cinematic"
    borrowed_films = get_context_list(["borrowed_films", "borrowedFilms", "reference_films", "referenceFilms"])

    title = get_context_val(["script_title", "title"])
    episode_label = get_context_val(["series_episode", "episode"])
    project_type = get_context_val(["type", "genre", "category", "film_type"])
    base_positioning = get_context_val(["base_positioning"])
    project_language = get_context_val(["language", "project_language", "lang"])
    tone = get_context_val(["tone", "mood", "atmosphere"])
    lighting = get_context_val(["lighting", "light_style", "light"])
    color_spectrum = get_context_val(["color_spectrum", "colorSpectrum", "色系光谱", "color_temperature_direction"])
    character_relationships = get_context_val(["character_relationships"])
    project_notes = get_context_val(["notes"])
    region_culture = get_context_val(["region_culture", "region", "country", "culture", "country_region"])
    era_setting = get_context_val(["era", "era_setting", "period", "time_setting"])
    shot_preference = get_context_val(["shot_preference", "lens_preference", "camera_preference"])
    max_shot_seconds = _parse_max_shot_seconds(get_context_val([
        "分镜最长秒数",
        "max_shot_seconds",
        "max_shot_duration",
        "shot_max_seconds",
        "maxShotSeconds",
        "拍摄最长时间",
        "分镜最长时间",
    ]))
    broadcast_security_level = get_context_val([
        "broadcast_security_level",
        "broadcast_safety_level",
        "safety_broadcast_level",
        "safety_level",
        "broadcast_safety",
        "compliance_level",
    ])
    expected_model_family = get_context_val(["expected_model_family", "expected_model", "target_model", "model_family"])
    generation_workflow = get_context_val(["generation_workflow", "workflow", "pipeline"])
    continuity_priority = get_context_val(["continuity_priority", "continuity", "continuity_mode"])
    prompt_mode = get_context_val(["shot_generation_mode", "shot_prompt_mode", "prompt_mode"])

    field_mappings = {
        "Type": ["Type", "Genre", "Category", "Film Type"],
        "Tone": ["Tone", "Color Tone", "Mood", "Atmosphere"],
        "Language": ["Language", "Lang"],
        "Lighting": ["Lighting", "Light Style"],
        "Quality": ["Quality", "Production Quality"],
    }
    context_lines = []
    for field, keys in field_mappings.items():
        val = get_context_val(keys)
        if val:
            context_lines.append(f"{field}: {val}")
    additional_context = "\n".join(context_lines) if context_lines else ""

    project_context_lines = [
        "# Project Context",
        "Treat this project metadata as first-class constraints when generating outputs.",
        "[Basic Info]",
    ]
    if title:
        project_context_lines.append(f"Title: {title}")
    if episode_label:
        project_context_lines.append(f"Episode: {episode_label}")
    if project_type:
        project_context_lines.append(f"Type: {project_type}")
    if base_positioning:
        project_context_lines.append(f"Base Positioning: {base_positioning}")
    if project_language:
        project_context_lines.append(f"Language: {project_language}")
    else:
        project_context_lines.append("Language: (empty)")
    if global_style:
        project_context_lines.append(f"Global Style: {global_style}")
    if tone:
        project_context_lines.append(f"Tone: {tone}")
    if lighting:
        project_context_lines.append(f"Lighting: {lighting}")
    if color_spectrum:
        project_context_lines.append(f"Color Spectrum: {color_spectrum}")
    if era_setting:
        project_context_lines.append(f"Era / Period (年代): {era_setting}")
    if region_culture:
        project_context_lines.append(f"Region / Country (国家地域): {region_culture}")
    if shot_preference:
        project_context_lines.append(f"Shot / Lens Preference (镜头偏好): {shot_preference}")
    project_context_lines.append(f"Max Shot Seconds (分镜最长秒数): {max_shot_seconds}")
    if broadcast_security_level:
        project_context_lines.append(f"Broadcast Safety Level (播出安全等级): {broadcast_security_level}")
    if borrowed_films:
        project_context_lines.append(f"Borrowed Films: {', '.join(borrowed_films)}")
    if character_relationships:
        project_context_lines.append(f"Character Relationships: {character_relationships}")
    if project_notes:
        project_context_lines.append(f"Project Notes: {project_notes}")

    project_context_lines.append("[Technical & Visual Parameters]")
    aspect_ratio = get_visual_val(["aspect_ratio", "aspectRatio"])
    image_size = get_visual_val(["image_size", "imageSize"])
    horizontal_resolution = get_visual_val(["horizontal_resolution", "horizontalResolution", "h_resolution", "width"])
    vertical_resolution = get_visual_val(["vertical_resolution", "verticalResolution", "v_resolution", "height"])
    frame_rate = get_visual_val(["frame_rate", "frameRate", "fps"])
    quality = get_visual_val(["quality"])

    if aspect_ratio:
        project_context_lines.append(f"Aspect Ratio: {aspect_ratio}")
    if image_size:
        project_context_lines.append(f"Image Size: {image_size}")
    if horizontal_resolution:
        project_context_lines.append(f"Horizontal Resolution: {horizontal_resolution}")
    if vertical_resolution:
        project_context_lines.append(f"Vertical Resolution: {vertical_resolution}")
    if frame_rate:
        project_context_lines.append(f"Frame Rate: {frame_rate}")
    if quality:
        project_context_lines.append(f"Quality: {quality}")
    if expected_model_family:
        project_context_lines.append(f"Expected Model Family: {expected_model_family}")
    if generation_workflow:
        project_context_lines.append(f"Generation Workflow: {generation_workflow}")
    if continuity_priority:
        project_context_lines.append(f"Continuity Priority: {continuity_priority}")

    project_context_lines.append("Use this project context as first-class constraints before analyzing the script.")
    project_context_section = wrap_injection_section("项目信息", "\n".join(project_context_lines))

    metadata = {
        "title": title,
        "episode": episode_label,
        "project_type": project_type,
        "type": project_type,
        "base_positioning": base_positioning,
        "project_language": project_language,
        "language": project_language,
        "global_style": global_style,
        "tone": tone,
        "lighting": lighting,
        "color_spectrum": color_spectrum,
        "region_culture": region_culture,
        "era_setting": era_setting,
        "broadcast_security_level": broadcast_security_level,
        "broadcast_safety_level": broadcast_security_level,
        "safety_broadcast_level": broadcast_security_level,
        "expected_model_family": expected_model_family,
        "generation_workflow": generation_workflow,
        "continuity_priority": continuity_priority,
        "shot_generation_mode": prompt_mode,
        "shot_prompt_mode": prompt_mode,
        "prompt_mode": prompt_mode,
        "max_shot_seconds": max_shot_seconds,
        "分镜最长秒数": max_shot_seconds,
    }

    return {
        "project_info": project_info,
        "global_style": global_style,
        "additional_context": additional_context,
        "project_context_section": project_context_section,
        "borrowed_films": borrowed_films,
        "metadata": metadata,
    }


def _build_shot_generation_project_context(project: Project) -> Dict[str, Any]:
    return _build_project_prompt_context(project.global_info)


def _build_scene_subject_image_prompts_cn_section(
    project_entities: List[Any],
    subject_match_keys: set,
    *,
    scene_id: Optional[int] = None,
) -> str:
    """Inject main-ENV prompts for scene-linked environments.

    A scene may use a view/state derivative, but its optical source is the
    derivative's main environment.  Inject that main ENV prompt and retain the
    selected derivative -> main ENV mapping so the storyboard model knows which
    view/state is actually in use.
    CHAR/PROP image prompts are intentionally excluded from this injection.
    """
    if not subject_match_keys:
        return ""

    def _entity_matches_subject_keys(ent: Any) -> bool:
        aliases = [getattr(ent, "name", None), getattr(ent, "name_en", None)]
        for alias in aliases:
            alias_text = str(alias or "").strip()
            if not alias_text:
                continue
            if subject_compare_key(alias_text) in subject_match_keys:
                return True
            if subject_match_keys.intersection(subject_compare_key_variants(alias_text)):
                return True
        return False

    environment_entities = [
        ent for ent in (project_entities or [])
        if not bool(getattr(ent, "is_deleted", False))
        and _normalize_subject_entity_type(getattr(ent, "type", None)) == "environment"
    ]
    matched_entities = [
        ent for ent in environment_entities
        if _entity_matches_subject_keys(ent)
    ]
    matched_entities.sort(key=lambda ent: int(getattr(ent, "id", 0) or 0))

    def _entity_name_keys(ent: Any) -> set:
        keys: set = set()
        for value in (getattr(ent, "name", None), getattr(ent, "name_en", None)):
            keys.update(subject_compare_key_variants(value))
        return keys

    def _dependency_names(value: Any) -> List[str]:
        """Extract ENV names from stored dependency references without guessing."""
        names: List[str] = []
        if isinstance(value, str):
            cleaned = normalize_entity_token(value)
            if cleaned:
                tagged = re.match(r"(?i)^ENV\s*:\s*\[\s*(.+?)\s*\]$", cleaned)
                names.append((tagged.group(1) if tagged else cleaned).strip())
        elif isinstance(value, dict):
            for key in (
                "name",
                "name_zh",
                "name_en",
                "entity_name",
                "reference_env",
                "base_name",
                "derivative_base_zh",
                "derivative_base_en",
            ):
                if value.get(key):
                    names.extend(_dependency_names(value[key]))
        elif isinstance(value, (list, tuple, set)):
            for item in value:
                names.extend(_dependency_names(item))
        return names

    def _find_main_environment(ent: Any) -> Optional[Any]:
        """Resolve an ENV derivative's declared main ENV from its dependency fields."""
        candidates = _dependency_names(getattr(ent, "visual_dependencies", None))
        candidates.extend(_dependency_names(getattr(ent, "base_name_en", None)))
        strategy = getattr(ent, "dependency_strategy", None)
        candidates.extend(_dependency_names(strategy))
        custom_attributes = getattr(ent, "custom_attributes", None)
        candidates.extend(_dependency_names(custom_attributes))
        for candidate in candidates:
            candidate_keys = subject_compare_key_variants(candidate)
            if not candidate_keys:
                continue
            for possible_main in environment_entities:
                if possible_main is ent:
                    continue
                if candidate_keys.intersection(_entity_name_keys(possible_main)):
                    return possible_main
        return None

    prompt_lines: List[str] = []
    seen_refs: set = set()
    for ent in matched_entities:
        used_env_name = str(getattr(ent, "name", None) or getattr(ent, "name_en", None) or "").strip()
        if not used_env_name:
            continue
        used_env_ref = f"ENV:[{used_env_name}]"
        if used_env_ref in seen_refs:
            continue
        seen_refs.add(used_env_ref)

        main_ent = _find_main_environment(ent)
        main_ent = main_ent or ent
        main_env_name = str(
            getattr(main_ent, "name", None) or getattr(main_ent, "name_en", None) or ""
        ).strip()
        prompt_cn = re.sub(
            r"\s+", " ", str(getattr(main_ent, "generation_prompt_cn", None) or "")
        ).strip()
        if not prompt_cn:
            continue

        if main_ent is ent:
            prompt_lines.append(
                f"- 当前场景环境={used_env_ref}（主环境） | "
                f"主环境 generation_prompt_cn={prompt_cn}"
            )
        else:
            prompt_lines.append(
                f"- 当前场景使用的衍生环境={used_env_ref} | "
                f"对应主环境=ENV:[{main_env_name}] | "
                f"主环境 generation_prompt_cn={prompt_cn}"
            )

    if not prompt_lines:
        logger.info(
            "[_build_shot_prompts] no scene ENV image prompts matched scene_id=%s keys=%s",
            scene_id,
            len(subject_match_keys),
        )
        return ""

    body = (
        "# Scene Subject Image Prompts (CN)\n"
        "Authoritative Chinese image-generation prompts for the MAIN ENVIRONMENT assets that "
        "scene-linked ENVIRONMENT assets depend on (main-ENV generation_prompt_cn for optical anchoring). "
        "Each row explicitly identifies the scene-used ENV derivative and its corresponding main ENV; "
        "preserve that derivative's declared view/state while using only the mapped main ENV prompt as its visual base. "
        "For every shot using a derivative ENV, design lighting direction, light color, color palette, and "
        "background-object micro-motion from that derivative's corresponding directional panel in the mapped "
        "main ENV four-panel reference, together with the derivative's declared visible-content boundary. "
        "Do not invent lights, colors, background objects, or background actions outside those two sources; "
        "background micro-motion must be physically motivated by the visible object's material/state and the "
        "shot's established environment. "
        "Do NOT expect CHAR/PROP prompts here — character/prop appearance is reference-image bound downstream. "
        "Translate ENV optics into dynamic video language; do not paste static framing/canvas instructions verbatim. "
        "Entity naming authority remains Scene Subject Index. "
        "Do not replace the used derivative with its main ENV name in shot output.\n"
        + "\n".join(prompt_lines)
        + "\n"
    )
    logger.info(
        "[_build_shot_prompts] injected scene ENV image prompts scene_id=%s keys=%s rows=%s",
        scene_id,
        len(subject_match_keys),
        len(prompt_lines),
    )
    return wrap_injection_section("实体中文生图提示词", body)


def _build_shot_prompts(
    db: Session,
    scene: Scene,
    project: Project,
    *,
    mode: Optional[str] = None,
    explicit_features: Optional[Dict[str, Any]] = None,
):
    # 2. Gather Data
    # Global Style & Context
    project_context = _build_shot_generation_project_context(project)
    effective_mode = _resolve_effective_shot_generation_mode(
        db,
        requested_mode=mode,
        project_metadata=project_context.get("metadata"),
        log_context="_build_shot_prompts",
    )
    project_info = project_context.get("project_info") if isinstance(project_context.get("project_info"), dict) else {}
    global_style = str(project_context.get("global_style") or "Cinematic")
    additional_context = str(project_context.get("additional_context") or "")
    project_context_section = str(project_context.get("project_context_section") or "")

    # Scene Info
    project_entities = (
        db.query(Entity)
        .filter(Entity.project_id == project.id, _active_entity_clause())
        .order_by(Entity.id.asc())
        .all()
    )
    
    def _scene_subject_compare_key(value: Any) -> str:
        return subject_compare_key(value)

    def _scene_subject_compare_keys(value: Any) -> set:
        return subject_compare_key_variants(value)

    # Identify relevant entity names from scene editor fields only:
    # environment anchor + linked characters (comma-separated) + key props.
    relevant_names: set = set()
    relevant_name_keys: set = set()

    def _clean_br(s):
        return normalize_entity_token(s)

    def _split_scene_editor_subjects(raw_value: Any) -> List[str]:
        values: List[str] = []
        for part in re.split(r"[,，、;；\n]+", str(raw_value or "")):
            cleaned = _clean_br(part)
            if not cleaned:
                continue
            values.append(cleaned)
        return values

    def _extract_tagged_scene_subjects(raw_value: Any) -> List[str]:
        """Extract only scene-related CHAR/PROP/ENV tags (never EXTRA/COVER/poster)."""
        values: List[str] = []
        text = str(raw_value or "")
        for match in re.finditer(r"(?i)\b(?:CHAR|PROP|ENV)\s*:\s*\[\s*@?([^\]\n]+?)\s*\]", text):
            cleaned = _clean_br(match.group(1))
            if cleaned:
                values.append(cleaned)
        return values

    def _extract_scene_subjects_from_markdown_rows(raw_value: Any) -> List[str]:
        values: List[str] = []
        text = str(raw_value or "")
        if not text.strip():
            return values
        row_patterns = [
            r"(?im)^\s*\|\s*(?:\*\*)?\s*(?:Environment\s*Anchor|环境锚点|Environment\s*Name|环境名)\s*(?:\*\*)?\s*\|\s*(.*?)\s*\|\s*$",
            r"(?im)^\s*\|\s*(?:\*\*)?\s*(?:Linked\s*Characters|关联角色)\s*(?:\*\*)?\s*\|\s*(.*?)\s*\|\s*$",
            r"(?im)^\s*\|\s*(?:\*\*)?\s*(?:Key\s*Props|关键道具)\s*(?:\*\*)?\s*\|\s*(.*?)\s*\|\s*$",
        ]
        for pattern in row_patterns:
            for match in re.finditer(pattern, text):
                cell_value = str(match.group(1) or "").strip()
                if not cell_value:
                    continue
                values.extend(_split_scene_editor_subjects(cell_value))
                values.extend(_extract_tagged_scene_subjects(cell_value))
        return values

    def _extract_environment_context_from_text(raw_value: Any) -> str:
        text = str(raw_value or "")
        if not text.strip():
            return ""

        row_patterns = [
            r"(?im)^\s*\|\s*(?:\*\*)?\s*(?:Environment\s*Context|环境上下文|环境描述)\s*(?:\*\*)?\s*\|\s*(.*?)\s*\|\s*$",
        ]
        for pattern in row_patterns:
            match = re.search(pattern, text)
            if match:
                cell_value = str(match.group(1) or "").strip()
                if cell_value and cell_value.upper() != "N/A":
                    return cell_value

        block_patterns = [
            r"(?im)\*\*\{Environment\s*Context\}\*\*\s*[:：]\s*(.+?)(?=\n\s*(?:-\s*\*\*\{|\*\*\{|\|))",
            r"(?im)\{Environment\s*Context\}\s*[:：]\s*(.+?)(?=\n\s*(?:-\s*\*\*\{|\*\*\{|\|))",
        ]
        for pattern in block_patterns:
            match = re.search(pattern, text, flags=re.DOTALL)
            if match:
                block_value = str(match.group(1) or "").strip()
                if block_value:
                    return block_value
        return ""

    def _register_scene_subject_candidate(raw_value: Any) -> None:
        text = str(raw_value or "").strip()
        if not text:
            return
        relevant_names.add(text)
        for key in _scene_subject_compare_keys(text):
            if key:
                relevant_name_keys.add(key)

    scene_editor_fields = [scene.environment_name, scene.linked_characters, scene.key_props]
    for raw_field_value in scene_editor_fields:
        for part in _split_scene_editor_subjects(raw_field_value):
            _register_scene_subject_candidate(part)
        for part in _extract_tagged_scene_subjects(raw_field_value):
            _register_scene_subject_candidate(part)
    # Compatibility: if scene content includes markdown rows for these fields,
    # parse them as additional candidates.
    for part in _extract_scene_subjects_from_markdown_rows(scene.core_scene_info):
        _register_scene_subject_candidate(part)
    # Tagged subjects from scene body / original script grounding (CHAR/PROP/ENV only).
    for source_text in (scene.core_scene_info, getattr(scene, "original_script_text", None)):
        for part in _extract_tagged_scene_subjects(source_text):
            _register_scene_subject_candidate(part)

    logger.info(
        "[_build_shot_prompts] scene subject candidates merged scene_id=%s names=%s keys=%s",
        getattr(scene, "id", None),
        len(relevant_names),
        len(relevant_name_keys),
    )

    def _add_scene_subject_candidate(value: Any, target: set) -> None:
        for key in _scene_subject_compare_keys(value):
            if key:
                target.add(key)

    def _extract_scene_subject_candidates() -> set:
        candidates: set = set()
        for value in scene_editor_fields:
            for part in _split_scene_editor_subjects(value):
                _add_scene_subject_candidate(part, candidates)
            for part in _extract_tagged_scene_subjects(value):
                _add_scene_subject_candidate(part, candidates)
        for part in _extract_scene_subjects_from_markdown_rows(scene.core_scene_info):
            _add_scene_subject_candidate(part, candidates)
        for source_text in (scene.core_scene_info, getattr(scene, "original_script_text", None)):
            for part in _extract_tagged_scene_subjects(source_text):
                _add_scene_subject_candidate(part, candidates)
        return candidates

    def _normalize_subject_index_row_type(raw_type: Any) -> str:
        value = str(raw_type or "").strip().lower()
        value = re.sub(r"[\s_\-]+", "", value)
        mapping = {
            "character": "character",
            "characters": "character",
            "角色": "character",
            "char": "character",
            "prop": "prop",
            "props": "prop",
            "道具": "prop",
            "environment": "environment",
            "environments": "environment",
            "env": "environment",
            "场景": "environment",
            "环境": "environment",
            "poster": "poster",
            "posters": "poster",
            "海报": "poster",
            "cover": "cover",
            "covers": "cover",
            "封面": "cover",
            "coverposter": "cover",
            "封面海报": "cover",
        }
        return mapping.get(value, "")

    def _is_subject_index_row(parts: List[str], normalized_line: str) -> bool:
        if len(parts) < 4:
            return False
        if not re.match(r"^S\d+\b", normalized_line, flags=re.IGNORECASE):
            return False
        row_type = _normalize_subject_index_row_type(parts[1] if len(parts) > 1 else "")
        return bool(row_type)

    def _build_filtered_scene_subject_index(scene_subject_keys: set) -> Tuple[str, set]:
        """
        Inject only Subject Index rows that match this scene's related entities
        (environment / linked characters / key props, plus tagged names in Core Scene Info).
        Never inject the full episode Subject Index.
        """
        episode = (
            db.query(Episode)
            .filter(Episode.id == scene.episode_id, _active_episode_clause())
            .first()
        )
        subject_index_text = sanitize_subject_index_text(
            getattr(episode, "ai_scene_analysis_subject_index", None) if episode else ""
        )
        if not subject_index_text:
            return "", set()

        if not scene_subject_keys:
            logger.info(
                "[_build_shot_prompts] skip subject index injection: no scene-linked entity candidates "
                "scene_id=%s env=%s chars=%s props=%s",
                getattr(scene, "id", None),
                bool(str(getattr(scene, "environment_name", "") or "").strip()),
                bool(str(getattr(scene, "linked_characters", "") or "").strip()),
                bool(str(getattr(scene, "key_props", "") or "").strip()),
            )
            return "", set()

        header_lines: List[str] = []
        separator_lines: List[str] = []
        kept_rows: List[str] = []
        seen_rows: set = set()
        index_subject_keys: set = set()
        allowed_row_types = {"character", "prop", "environment"}

        def _row_matches_scene_subjects(parts: List[str]) -> bool:
            # Match by display names only (zh/en). Do not keep rows merely because
            # scene candidates are empty, and do not match on subject_no alone.
            name_cells = []
            if len(parts) > 2:
                name_cells.append(parts[2])
            if len(parts) > 3:
                name_cells.append(parts[3])
            for candidate in name_cells:
                candidate_text = str(candidate or "").strip()
                if not candidate_text:
                    continue
                primary = _scene_subject_compare_key(candidate_text)
                if primary and primary in scene_subject_keys:
                    return True
                variants = _scene_subject_compare_keys(candidate_text)
                if variants and scene_subject_keys.intersection(variants):
                    return True
            return False

        for raw_line in str(subject_index_text).splitlines():
            line = str(raw_line or "")
            stripped = line.strip()
            if not stripped:
                continue

            normalized_line = stripped.strip("|").strip()
            parts = [part.strip() for part in normalized_line.split("|")]
            is_subject_row = _is_subject_index_row(parts, normalized_line)
            if is_subject_row:
                row_type = _normalize_subject_index_row_type(parts[1] if len(parts) > 1 else "")
                if row_type not in allowed_row_types:
                    continue
                if not _row_matches_scene_subjects(parts):
                    continue
                row_key = re.sub(r"\s+", "", stripped).lower()
                if row_key in seen_rows:
                    continue
                kept_rows.append(line)
                seen_rows.add(row_key)
                for candidate in [parts[2] if len(parts) > 2 else "", parts[3] if len(parts) > 3 else ""]:
                    key = _scene_subject_compare_key(candidate)
                    if key:
                        index_subject_keys.add(key)
                continue

            is_table_header = "|" in stripped and re.search(r"(?i)subject_no|subject_type|subject_name|name_zh|name_en", stripped)
            is_table_separator = bool(re.match(r"^\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?$", stripped))
            if is_table_header:
                header_lines = [line]
                continue
            if is_table_separator:
                separator_lines = [line]

        if not kept_rows:
            logger.info(
                "[_build_shot_prompts] filtered scene subject index has no matching rows "
                "(full index will NOT be injected) scene_id=%s candidate_count=%s",
                getattr(scene, "id", None),
                len(scene_subject_keys),
            )
            return "", set()

        lines = [
            "# Scene Subject Index",
            "Authoritative filtered Subject Index for this scene only "
            "(environment / linked characters / key props). "
            "Use subject_no/subject_type/subject_name fields as the sole entity naming source; "
            "do not infer subjects outside this list. "
            "Same-main-environment matching (shot merge): for environment rows, "
            "env_role / reference_env / derivative_base_zh|en / base_name may prove the same main ENV family; "
            "any one conclusive match with ENV name or generation_prompt_cn is sufficient to merge.",
        ]
        lines.extend(header_lines)
        lines.extend(separator_lines if header_lines else [])
        lines.extend(kept_rows)
        logger.info(
            "[_build_shot_prompts] injected filtered scene subject index scene_id=%s candidates=%s rows=%s",
            getattr(scene, "id", None),
            len(scene_subject_keys),
            len(kept_rows),
        )
        return wrap_injection_section("Subject Index", "\n".join(lines).strip() + "\n"), index_subject_keys

    env_narrative = _extract_environment_context_from_text(scene.core_scene_info).strip()
    if env_narrative:
        logger.info(
            "[_build_shot_prompts] using Environment Context from core_scene_info scene_id=%s",
            getattr(scene, "id", None),
        )

    scene_subject_keys = _extract_scene_subject_candidates()
    scene_subject_index_section, index_subject_keys = _build_filtered_scene_subject_index(scene_subject_keys)
    subject_match_keys = set(scene_subject_keys) | set(index_subject_keys)
    scene_subject_image_prompts_section = _build_scene_subject_image_prompts_cn_section(
        project_entities,
        subject_match_keys,
        scene_id=getattr(scene, "id", None),
    )

    # 3. Prepare System Prompt
    system_prompt = ""
    try:
        core_goal_text = scene.core_scene_info or ''
        feature_bundle = resolve_shot_generation_feature_bundle(
            project_metadata=project_context.get("metadata"),
            explicit_features=explicit_features,
            script_text=core_goal_text,
            mode=effective_mode,
        )
        base_prompt_file = str(feature_bundle.get("base_prompt_file") or "skills/shot_generation.md")
        system_prompt = _resolve_prompt_text(base_prompt_file)
        if feature_bundle.get("enabled"):
            system_prompt = render_shot_generation_routed_prompt(system_prompt, feature_bundle)
        max_shot_seconds = _parse_max_shot_seconds(
            (project_context.get("metadata") or {}).get("max_shot_seconds")
        )
        system_prompt = (
            f"【本场时长上限】MaxShotSeconds={max_shot_seconds}"
            f"（# Project Context「分镜最长秒数」；未注入则默认 {DEFAULT_MAX_SHOT_SECONDS}）。"
            f"鼓励合并门槛=MaxShotSeconds-6={max(0, max_shot_seconds - 6)}。"
            f"符合合并逻辑时须一直累计到基准合镜Duration>门槛才封口；"
            f"若基准已>MaxShotSeconds，表列Duration强制=MaxShotSeconds，禁止超时拆镜。"
            f"下文合镜封口、Duration钳制、未继续合并说明一律用该值，禁止回退写死 15（除非本场即默认 15）。\n\n"
            + system_prompt
        )
    except Exception as e:
        logger.error(f"Failed to load shot generation prompt stack: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Shot generation prompt stack could not be loaded: {str(e)}")

    # Environment Context is now a separate field in the table

    core_scene_info_block = wrap_injection_section(
        "Core Scene Info",
        f"""| Field | Value |
| :--- | :--- |
| **Scene No** | {scene.scene_no or ''} |
| **Scene Name** | {scene.scene_name or ''} |
| **Environment Anchor** | {scene.environment_name or ''} |
| **Environment Context** | {env_narrative or 'N/A'} |
| **Linked Characters** | {scene.linked_characters or ''} |
| **Key Props** | {scene.key_props or ''} |
| **Core Goal** | {core_goal_text} |""",
    )

    user_input = f"""{project_context_section}

{core_scene_info_block}

{scene_subject_index_section}
{scene_subject_image_prompts_section}
# Instruction
1. Analyze `# Core Scene Info` Beats and break them down into shots per §二.1.5/§二.1.6.
2. Output exactly one Shot List markdown table. Do not copy prompt example/template rows (e.g. `{{Scene ID}}_SHzz` or a second header).
3. Scene opening / OT- / 吸睛 must be P segments inside the Shot that covers Beat 1 — never an extra Shot outside Beat-Shot mapping.
4. Every Beat must appear in some row's `Beat-Shot映射`; do not invent unmapped opening shots.
"""
    
    return system_prompt, user_input


def _extract_shot_regenerate_marker(raw_logic: str) -> Tuple[Optional[str], str]:
    text = str(raw_logic or "").strip()
    if not text:
        return None, ""

    if re.search(r"=更新分镜\s*$", text):
        return "update", re.sub(r"\s*=更新分镜\s*$", "", text).strip()
    if re.search(r"=补充分镜\s*$", text):
        return "add", re.sub(r"\s*=补充分镜\s*$", "", text).strip()
    return None, text


def _build_shot_regenerate_prompts(
    db: Session,
    scene: Scene,
    project: Project,
    *,
    staged_markdown: str,
    additional_instructions: str,
    mode: Optional[str],
    explicit_features: Optional[Dict[str, Any]],
) -> Tuple[str, str]:
    system_prompt, base_user_prompt = _build_shot_prompts(
        db,
        scene,
        project,
        mode=mode,
        explicit_features=explicit_features,
    )

    safe_markdown = str(staged_markdown or "").strip()
    safe_instructions = str(additional_instructions or "").strip() or "(none)"

    runtime_rules = (
        "# Runtime Regeneration Rules\n"
        "You are not generating a full fresh shot list. You are producing a selective supplement/update diff against the current staged shot markdown.\n"
        "Return a markdown table only. Do not add prose before or after the table.\n"
        "Only include rows that need to change or be newly inserted. Omit unchanged rows entirely.\n"
        "For an existing shot that should be modified, preserve its existing Shot ID exactly and append '=更新分镜' to the end of 'Shot Logic (CN)'.\n"
        "For a newly inserted shot, create a Shot ID derived from its neighboring base shot using an underscore numeric suffix such as '_1', '_2', and append '=补充分镜' to the end of 'Shot Logic (CN)'.\n"
        "Every returned row must include a valid marker in 'Shot Logic (CN)' so downstream import can distinguish updates from additions.\n"
        "Do not rewrite or renumber unaffected shots.\n"
        "Keep the table schema compatible with the staged shot markdown table.\n"
    )

    user_prompt = (
        "# Scene Context Reference\n"
        "The following block is the authoritative current scene context, including project context, scene text, and subject index.\n\n"
        f"{str(base_user_prompt or '').strip()}\n\n"
        f"{runtime_rules}\n"
        "# Current Staged Shot Markdown (Authoritative Baseline)\n"
        "Use this markdown table as the source of truth for current shot order, existing Shot IDs, and current content.\n\n"
        f"{safe_markdown}\n\n"
        "# User Supplement Instructions\n"
        f"{safe_instructions}\n"
    )
    return system_prompt, user_prompt


def _resolve_scene_for_shot_persist(
    db: Session,
    *,
    scene_id: int,
    episode_id: Optional[int] = None,
    scene_no: Optional[str] = None,
) -> Tuple[Any, Optional[int]]:
    """
    Resolve the workspace scene row to persist shot markdown onto.

    During script-analysis orchestration, a purge+reimport can replace the row
    while ai_generate_shots LLM is in flight. Prefer the original id when still
    active; if missing or soft-deleted, fall back to the active scene in the same
    episode with the same scene_no.
    Returns (scene, remapped_from_scene_id|None).
    """
    from app.services.deletion_ops import _is_soft_deleted

    scene = db.query(Scene).filter(Scene.id == int(scene_id)).first()
    if scene is not None and not _is_soft_deleted(scene):
        return scene, None

    ep_id = int(episode_id or getattr(scene, "episode_id", None) or 0)
    resolve_scene_no = scene_no or (getattr(scene, "scene_no", None) if scene is not None else None)
    keys = [
        str(k or "").strip()
        for k in _scene_no_lookup_keys(resolve_scene_no, scene_id=resolve_scene_no)
        if str(k or "").strip()
    ]
    if ep_id <= 0 or not keys:
        return None, None

    candidates = (
        db.query(Scene)
        .filter(Scene.episode_id == ep_id, _active_scene_clause())
        .order_by(Scene.id.desc())
        .all()
    )
    key_set = {k.upper() for k in keys}
    for row in candidates:
        row_keys = {
            str(k or "").strip().upper()
            for k in _scene_no_lookup_keys(getattr(row, "scene_no", None), scene_id=getattr(row, "scene_no", None))
            if str(k or "").strip()
        }
        if row_keys & key_set:
            return row, int(scene_id)
    return None, None


def _persist_scene_shot_generation_result(
    *,
    db: Session,
    scene_id: int,
    raw_text: str,
    markdown_text: str,
    rows: List[Dict[str, Any]],
    usage: Optional[Dict[str, Any]] = None,
    episode_id: Optional[int] = None,
    scene_no: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Persist LLM shot-generation output to scene staging storage only.
    This method does NOT import into Shot table.
    """
    result_wrapper = {
        "timestamp": now_bj_iso(),
        "raw_text": str(raw_text or ""),
        "content": list(rows or []),
        "usage": usage or {},
        "warnings": [],
    }
    # The original ORM instance may be detached after _release_db_connection;
    # reload a session-bound instance before applying updates.
    scene, remapped_from = _resolve_scene_for_shot_persist(
        db,
        scene_id=int(scene_id),
        episode_id=episode_id,
        scene_no=scene_no,
    )
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    persist_scene_id = int(getattr(scene, "id", 0) or 0)
    if remapped_from is not None:
        warning = (
            f"Original scene_id={remapped_from} was replaced during generation; "
            f"persisted to active scene_id={persist_scene_id} scene_no={getattr(scene, 'scene_no', '')}"
        )
        result_wrapper["warnings"].append(warning)
        result_wrapper["remapped_scene_id"] = persist_scene_id
        result_wrapper["requested_scene_id"] = int(remapped_from)
        logger.warning("[shot_generation.persist] %s", warning)
    scene.ai_shots_result = str(markdown_text or "")
    db.commit()
    logger.info(
        "[shot_generation.persist] saved scene_id=%s markdown_len=%s rows=%s remapped_from=%s",
        persist_scene_id,
        len(scene.ai_shots_result or ""),
        len(result_wrapper.get("content") or []),
        remapped_from,
    )
    return result_wrapper
