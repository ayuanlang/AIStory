import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings

logger = logging.getLogger(__name__)

_PROMPTS_ROOT = Path(settings.BASE_DIR) / "app" / "core" / "prompts"
_FEATURE_STACK_ROOT = _PROMPTS_ROOT / "skills" / "scene_analysis_feature_stack"
_REGISTRY_PATH = _FEATURE_STACK_ROOT / "registry.json"
_DEFAULT_ROUTED_BASE_PROMPT = "scene_analysis_routed_base.txt"
_COMBO_SLOT_TOKEN = "[[SCENE_ANALYSIS_COMBO_RULES]]"
_PROMPT_FRAGMENT_KEYS = (
    "prompt",
    "global_prompt",
    "environment_prompt",
    "character_prompt",
    "prop_prompt",
    "character_goal_alignment_prompt",
)
_ENVIRONMENT_COMBO_SLOT_TOKEN = "[[SCENE_ANALYSIS_ENVIRONMENT_COMBO_RULES]]"
_CHARACTER_COMBO_SLOT_TOKEN = "[[SCENE_ANALYSIS_CHARACTER_COMBO_RULES]]"
_PROP_COMBO_SLOT_TOKEN = "[[SCENE_ANALYSIS_PROP_COMBO_RULES]]"
_ENVIRONMENT_BASE_POSITIONING_SLOT_TOKEN = "[[SCENE_ANALYSIS_ENVIRONMENT_BASE_POSITIONING_RULES]]"
_CHARACTER_BASE_POSITIONING_SLOT_TOKEN = "[[SCENE_ANALYSIS_CHARACTER_BASE_POSITIONING_RULES]]"
_PROP_BASE_POSITIONING_SLOT_TOKEN = "[[SCENE_ANALYSIS_PROP_BASE_POSITIONING_RULES]]"
_ENVIRONMENT_PROJECT_TYPE_SLOT_TOKEN = "[[SCENE_ANALYSIS_ENVIRONMENT_PROJECT_TYPE_RULES]]"
_ENVIRONMENT_LANGUAGE_CONTEXT_SLOT_TOKEN = "[[SCENE_ANALYSIS_ENVIRONMENT_LANGUAGE_CONTEXT_RULES]]"
_ENVIRONMENT_MODEL_FAMILY_SLOT_TOKEN = "[[SCENE_ANALYSIS_ENVIRONMENT_MODEL_FAMILY_RULES]]"
_ENVIRONMENT_WORKFLOW_SLOT_TOKEN = "[[SCENE_ANALYSIS_ENVIRONMENT_WORKFLOW_RULES]]"
_ENVIRONMENT_CONTINUITY_SLOT_TOKEN = "[[SCENE_ANALYSIS_ENVIRONMENT_CONTINUITY_RULES]]"
_CHARACTER_PROJECT_TYPE_SLOT_TOKEN = "[[SCENE_ANALYSIS_CHARACTER_PROJECT_TYPE_RULES]]"
_CHARACTER_LANGUAGE_CONTEXT_SLOT_TOKEN = "[[SCENE_ANALYSIS_CHARACTER_LANGUAGE_CONTEXT_RULES]]"
_CHARACTER_MODEL_FAMILY_SLOT_TOKEN = "[[SCENE_ANALYSIS_CHARACTER_MODEL_FAMILY_RULES]]"
_CHARACTER_WORKFLOW_SLOT_TOKEN = "[[SCENE_ANALYSIS_CHARACTER_WORKFLOW_RULES]]"
_CHARACTER_CONTINUITY_SLOT_TOKEN = "[[SCENE_ANALYSIS_CHARACTER_CONTINUITY_RULES]]"
_CHARACTER_GOAL_ALIGNMENT_SLOT_TOKEN = "[[SCENE_ANALYSIS_CHARACTER_GOAL_ALIGNMENT_RULES]]"
_PROP_PROJECT_TYPE_SLOT_TOKEN = "[[SCENE_ANALYSIS_PROP_PROJECT_TYPE_RULES]]"
_PROP_LANGUAGE_CONTEXT_SLOT_TOKEN = "[[SCENE_ANALYSIS_PROP_LANGUAGE_CONTEXT_RULES]]"
_PROP_MODEL_FAMILY_SLOT_TOKEN = "[[SCENE_ANALYSIS_PROP_MODEL_FAMILY_RULES]]"
_PROP_WORKFLOW_SLOT_TOKEN = "[[SCENE_ANALYSIS_PROP_WORKFLOW_RULES]]"
_PROP_CONTINUITY_SLOT_TOKEN = "[[SCENE_ANALYSIS_PROP_CONTINUITY_RULES]]"


def _norm_text(value: Any) -> str:
    return str(value or "").strip()


def _norm_key(value: Any) -> str:
    return _norm_text(value).lower().replace("-", "_").replace(" ", "_")


def _tokenize_text(value: Any) -> str:
    return _norm_text(value).lower()


def _slot_token_for_dimension(dimension_key: Any) -> str:
    return f"[[SCENE_ANALYSIS_{_norm_key(dimension_key).upper()}_RULES]]"


def _known_slot_tokens(registry: Optional[Dict[str, Any]] = None) -> List[str]:
    registry = registry if isinstance(registry, dict) else load_scene_analysis_feature_registry()
    tokens: List[str] = []
    for dimension in registry.get("dimensions", []):
        if not isinstance(dimension, dict):
            continue
        tokens.append(_slot_token_for_dimension(dimension.get("key")))
    tokens.extend([
        _ENVIRONMENT_COMBO_SLOT_TOKEN,
        _CHARACTER_COMBO_SLOT_TOKEN,
        _PROP_COMBO_SLOT_TOKEN,
        _ENVIRONMENT_BASE_POSITIONING_SLOT_TOKEN,
        _CHARACTER_BASE_POSITIONING_SLOT_TOKEN,
        _PROP_BASE_POSITIONING_SLOT_TOKEN,
        _ENVIRONMENT_PROJECT_TYPE_SLOT_TOKEN,
        _ENVIRONMENT_LANGUAGE_CONTEXT_SLOT_TOKEN,
        _ENVIRONMENT_MODEL_FAMILY_SLOT_TOKEN,
        _ENVIRONMENT_WORKFLOW_SLOT_TOKEN,
        _ENVIRONMENT_CONTINUITY_SLOT_TOKEN,
        _CHARACTER_PROJECT_TYPE_SLOT_TOKEN,
        _CHARACTER_LANGUAGE_CONTEXT_SLOT_TOKEN,
        _CHARACTER_MODEL_FAMILY_SLOT_TOKEN,
        _CHARACTER_WORKFLOW_SLOT_TOKEN,
        _CHARACTER_CONTINUITY_SLOT_TOKEN,
        _CHARACTER_GOAL_ALIGNMENT_SLOT_TOKEN,
        _PROP_PROJECT_TYPE_SLOT_TOKEN,
        _PROP_LANGUAGE_CONTEXT_SLOT_TOKEN,
        _PROP_MODEL_FAMILY_SLOT_TOKEN,
        _PROP_WORKFLOW_SLOT_TOKEN,
        _PROP_CONTINUITY_SLOT_TOKEN,
    ])
    tokens.append(_COMBO_SLOT_TOKEN)
    seen = set()
    unique_tokens: List[str] = []
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        unique_tokens.append(token)
    return unique_tokens


def _slot_token_for_skill(skill: Dict[str, Any]) -> str:
    slot_token = _norm_text(skill.get("slot_token"))
    if slot_token:
        return slot_token
    if _norm_key(skill.get("dimension")) == "combo":
        return _COMBO_SLOT_TOKEN
    return _slot_token_for_dimension(skill.get("dimension"))


def _format_slot_block(skill: Dict[str, Any]) -> str:
    title = _norm_text(skill.get("title") or skill.get("skill_id") or "Routed Rules")
    prompt_text = _norm_text(skill.get("prompt"))
    if not prompt_text:
        return ""
    return f"## {title}\n{prompt_text}".strip()


def _copy_prompt_fragments(source: Dict[str, Any]) -> Dict[str, Any]:
    fragments: Dict[str, Any] = {}
    for key in _PROMPT_FRAGMENT_KEYS:
        value = _norm_text(source.get(key))
        if value:
            fragments[key] = value
    return fragments


def _resolve_variant_prompt(
    skill: Dict[str, Any],
    explicit_key: str,
    fallback_scope: Optional[str] = None,
    fallback_text: str = "",
) -> str:
    explicit_prompt = _norm_text(skill.get(explicit_key))
    if explicit_prompt:
        return explicit_prompt
    if fallback_scope and fallback_text:
        return _scoped_prompt(fallback_text, fallback_scope)
    return ""


def _scoped_prompt(prompt_text: str, scope: str) -> str:
    prompt_text = _norm_text(prompt_text)
    if not prompt_text:
        return ""
    scope_key = _norm_key(scope)
    if scope_key == "environment":
        return f"{prompt_text} 仅作用于 Environment Prompt Template：把要求落到空间结构、材质、光照、构图层级、可达性、观察方向、Visible/Excluded 集合与 clean plate 约束，禁止扩写人物外形、人物身份或剧情事件。"
    if scope_key == "character":
        return f"{prompt_text} 仅作用于 Character Prompt Template：把要求落到角色外观、体态比例、服装版型、姿态、镜头友好度、身份识别锚点与角色差异化，禁止扩写环境结构或道具空间描述。"
    if scope_key == "prop":
        return f"{prompt_text} 仅作用于 Prop Prompt Template：把要求落到物体结构、材质、磨损、状态版本、识别锚点与四视图资产表达，禁止扩写人物姿态或环境叙事情境。"
    if scope_key == "character_goal_alignment":
        return f"{prompt_text} 仅作用于 Character Prompt Template 中与剧情功能对齐的局部规则：每个主要角色的外形、服装、动作习惯、表情方式与识别锚点，都必须回扣其剧情目标、阻力、关系位置与情绪阶段。"
    return prompt_text


def _expand_skill_variants(skill: Dict[str, Any]) -> List[Dict[str, Any]]:
    base_prompt_text = _norm_text(skill.get("global_prompt") or skill.get("prompt"))

    variants: List[Dict[str, Any]] = []
    if base_prompt_text:
        base_skill = dict(skill)
        base_skill["prompt"] = base_prompt_text
        base_skill["slot_token"] = _slot_token_for_skill(base_skill)
        variants.append(base_skill)

    dimension_key = _norm_key(skill.get("dimension"))
    title = _norm_text(skill.get("title") or skill.get("skill_id") or "Routed Rules")
    source = skill.get("source")

    def add_variant(token: str, title_suffix: str, scoped_text: str) -> None:
        scoped_text = _norm_text(scoped_text)
        if not scoped_text:
            return
        variants.append({
            **skill,
            "skill_id": f"{_norm_text(skill.get('skill_id') or 'skill')}.{_norm_key(title_suffix)}",
            "title": f"{title} / {title_suffix}",
            "prompt": scoped_text,
            "slot_token": token,
            "source": source,
        })

    if dimension_key == "base_positioning":
        add_variant(_ENVIRONMENT_BASE_POSITIONING_SLOT_TOKEN, "Environment Base Positioning", _resolve_variant_prompt(skill, "environment_prompt", "environment", base_prompt_text))
        add_variant(_CHARACTER_BASE_POSITIONING_SLOT_TOKEN, "Character Base Positioning", _resolve_variant_prompt(skill, "character_prompt", "character", base_prompt_text))
        add_variant(_PROP_BASE_POSITIONING_SLOT_TOKEN, "Prop Base Positioning", _resolve_variant_prompt(skill, "prop_prompt", "prop", base_prompt_text))
    elif dimension_key == "project_type":
        add_variant(_ENVIRONMENT_PROJECT_TYPE_SLOT_TOKEN, "Environment", _resolve_variant_prompt(skill, "environment_prompt", "environment", base_prompt_text))
        add_variant(_CHARACTER_PROJECT_TYPE_SLOT_TOKEN, "Character", _resolve_variant_prompt(skill, "character_prompt", "character", base_prompt_text))
        add_variant(_PROP_PROJECT_TYPE_SLOT_TOKEN, "Prop", _resolve_variant_prompt(skill, "prop_prompt", "prop", base_prompt_text))
    elif dimension_key in {"project_language", "region_culture", "era_setting"}:
        add_variant(_ENVIRONMENT_LANGUAGE_CONTEXT_SLOT_TOKEN, "Environment Language", _resolve_variant_prompt(skill, "environment_prompt", "environment", base_prompt_text))
        add_variant(_CHARACTER_LANGUAGE_CONTEXT_SLOT_TOKEN, "Character Language", _resolve_variant_prompt(skill, "character_prompt", "character", base_prompt_text))
        add_variant(_PROP_LANGUAGE_CONTEXT_SLOT_TOKEN, "Prop Language", _resolve_variant_prompt(skill, "prop_prompt", "prop", base_prompt_text))
    elif dimension_key == "expected_model_family":
        add_variant(_ENVIRONMENT_MODEL_FAMILY_SLOT_TOKEN, "Environment Model", _resolve_variant_prompt(skill, "environment_prompt", "environment", base_prompt_text))
        add_variant(_CHARACTER_MODEL_FAMILY_SLOT_TOKEN, "Character Model", _resolve_variant_prompt(skill, "character_prompt", "character", base_prompt_text))
        add_variant(_PROP_MODEL_FAMILY_SLOT_TOKEN, "Prop Model", _resolve_variant_prompt(skill, "prop_prompt", "prop", base_prompt_text))
    elif dimension_key == "generation_workflow":
        add_variant(_ENVIRONMENT_WORKFLOW_SLOT_TOKEN, "Environment Workflow", _resolve_variant_prompt(skill, "environment_prompt", "environment", base_prompt_text))
        add_variant(_CHARACTER_WORKFLOW_SLOT_TOKEN, "Character Workflow", _resolve_variant_prompt(skill, "character_prompt", "character", base_prompt_text))
        add_variant(_PROP_WORKFLOW_SLOT_TOKEN, "Prop Workflow", _resolve_variant_prompt(skill, "prop_prompt", "prop", base_prompt_text))
    elif dimension_key == "continuity_priority":
        add_variant(_ENVIRONMENT_CONTINUITY_SLOT_TOKEN, "Environment Continuity", _resolve_variant_prompt(skill, "environment_prompt", "environment", base_prompt_text))
        add_variant(_CHARACTER_CONTINUITY_SLOT_TOKEN, "Character Continuity", _resolve_variant_prompt(skill, "character_prompt", "character", base_prompt_text))
        add_variant(_PROP_CONTINUITY_SLOT_TOKEN, "Prop Continuity", _resolve_variant_prompt(skill, "prop_prompt", "prop", base_prompt_text))
    elif dimension_key in {"primary_goal", "secondary_goal"}:
        add_variant(_CHARACTER_GOAL_ALIGNMENT_SLOT_TOKEN, "Character Goal Alignment", _resolve_variant_prompt(skill, "character_goal_alignment_prompt", "character_goal_alignment", base_prompt_text))
    elif dimension_key == "combo":
        add_variant(_ENVIRONMENT_COMBO_SLOT_TOKEN, "Environment", _resolve_variant_prompt(skill, "environment_prompt"))
        add_variant(_CHARACTER_COMBO_SLOT_TOKEN, "Character", _resolve_variant_prompt(skill, "character_prompt"))
        add_variant(_PROP_COMBO_SLOT_TOKEN, "Prop", _resolve_variant_prompt(skill, "prop_prompt"))
        add_variant(_CHARACTER_GOAL_ALIGNMENT_SLOT_TOKEN, "Character Goal Alignment", _resolve_variant_prompt(skill, "character_goal_alignment_prompt", "character_goal_alignment", base_prompt_text))

    return variants


def render_scene_analysis_routed_prompt(base_prompt_text: str, feature_bundle: Optional[Dict[str, Any]] = None) -> str:
    feature_bundle = feature_bundle if isinstance(feature_bundle, dict) else {}
    rendered = str(base_prompt_text or "")
    slot_blocks = feature_bundle.get("slot_blocks") if isinstance(feature_bundle.get("slot_blocks"), dict) else {}
    known_tokens = feature_bundle.get("known_slot_tokens") if isinstance(feature_bundle.get("known_slot_tokens"), list) else _known_slot_tokens()

    for token, block in slot_blocks.items():
        rendered = rendered.replace(str(token), _norm_text(block))

    for token in known_tokens:
        rendered = rendered.replace(str(token), "")

    rendered = re.sub(r"\n{3,}", "\n\n", rendered)
    return rendered.strip()


@lru_cache(maxsize=1)
def load_scene_analysis_feature_registry() -> Dict[str, Any]:
    if not _REGISTRY_PATH.exists():
        logger.warning("scene analysis feature registry not found: %s", _REGISTRY_PATH)
        return {"version": 1, "default_mode": "classic", "modes": [], "dimensions": []}

    try:
        with _REGISTRY_PATH.open("r", encoding="utf-8") as handle:
            parsed = json.load(handle)
        if isinstance(parsed, dict):
            return parsed
    except Exception as exc:
        logger.error("failed to load scene analysis feature registry: %s", exc)

    return {"version": 1, "default_mode": "classic", "modes": [], "dimensions": []}


def _match_dimension_value(dimension: Dict[str, Any], raw_value: Any) -> Optional[Dict[str, Any]]:
    candidate = _norm_text(raw_value)
    if not candidate:
        return None
    candidate_key = _norm_key(candidate)

    for value in dimension.get("values", []):
        aliases = [value.get("id")] + list(value.get("aliases") or []) + [value.get("title")]
        for alias in aliases:
            if _norm_key(alias) == candidate_key:
                return value
    return None


def _pick_feature_raw_value(
    dimension: Dict[str, Any],
    project_metadata: Optional[Dict[str, Any]],
    explicit_features: Optional[Dict[str, Any]],
) -> Tuple[str, str]:
    explicit_features = explicit_features if isinstance(explicit_features, dict) else {}
    project_metadata = project_metadata if isinstance(project_metadata, dict) else {}
    project_meta_norm = {_norm_key(k): v for k, v in project_metadata.items()}
    explicit_norm = {_norm_key(k): v for k, v in explicit_features.items()}

    key = _norm_key(dimension.get("key"))
    aliases = [key] + [_norm_key(alias) for alias in (dimension.get("source_keys") or [])]

    for alias in aliases:
        if alias in explicit_norm:
            value = explicit_norm.get(alias)
            if _norm_text(value):
                return _norm_text(value), "explicit"

    for alias in aliases:
        if alias in project_meta_norm:
            value = project_meta_norm.get(alias)
            if _norm_text(value):
                return _norm_text(value), "project_metadata"

    return "", ""


def _extract_text_candidates(project_metadata: Optional[Dict[str, Any]], script_text: str) -> Dict[str, str]:
    project_metadata = project_metadata if isinstance(project_metadata, dict) else {}
    project_meta_norm = {_norm_key(k): v for k, v in project_metadata.items()}

    parts: List[str] = []
    for key in (
        "title",
        "script_title",
        "type",
        "base_positioning",
        "genre",
        "tone",
        "setting",
        "worldview",
        "language",
        "project_language",
        "expected_model",
        "target_model",
    ):
        value = project_meta_norm.get(_norm_key(key))
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())

    if script_text:
        parts.append(script_text[:6000])

    merged = "\n".join(parts)
    return {
        "merged": merged,
        "lower": _tokenize_text(merged),
    }


def _infer_dimension_value_from_text(dimension: Dict[str, Any], text_bank: Dict[str, str]) -> Tuple[Optional[Dict[str, Any]], List[str], float]:
    haystack = text_bank.get("lower") or ""
    if not haystack:
        return None, [], 0.0

    best_match: Optional[Dict[str, Any]] = None
    best_hits: List[str] = []
    best_score = 0.0

    for value in dimension.get("values", []):
        if not isinstance(value, dict):
            continue
        aliases = [value.get("id")] + list(value.get("aliases") or []) + [value.get("title")]
        hits: List[str] = []
        score = 0.0
        for alias in aliases:
            alias_text = _norm_text(alias)
            if not alias_text:
                continue
            alias_norm = alias_text.lower()
            pattern = rf"(?<![a-z0-9]){re.escape(alias_norm)}(?![a-z0-9])"
            if re.search(pattern, haystack):
                hits.append(alias_text)
                score += 1.0 if alias_norm == _norm_text(value.get("id")).lower() else 0.6

        infer_hints = value.get("infer_hints") if isinstance(value.get("infer_hints"), list) else []
        for hint in infer_hints:
            hint_text = _norm_text(hint)
            if not hint_text:
                continue
            pattern = rf"(?<![a-z0-9]){re.escape(hint_text.lower())}(?![a-z0-9])"
            if re.search(pattern, haystack):
                hits.append(hint_text)
                score += 0.8

        if score > best_score:
            best_match = value
            best_hits = hits
            best_score = score

    confidence = min(1.0, 0.35 + best_score * 0.18) if best_score > 0 else 0.0
    return best_match, best_hits, confidence


def analyze_scene_dimensions(
    project_metadata: Optional[Dict[str, Any]] = None,
    explicit_features: Optional[Dict[str, Any]] = None,
    script_text: Optional[str] = None,
) -> Dict[str, Any]:
    registry = load_scene_analysis_feature_registry()
    text_bank = _extract_text_candidates(project_metadata, _norm_text(script_text))
    resolved: Dict[str, Dict[str, Any]] = {}
    diagnostics: List[Dict[str, Any]] = []

    for dimension in registry.get("dimensions", []):
        if not isinstance(dimension, dict):
            continue

        dim_key = _norm_key(dimension.get("key"))
        raw_value, source = _pick_feature_raw_value(dimension, project_metadata, explicit_features)
        matched = _match_dimension_value(dimension, raw_value) if raw_value else None
        infer_hits: List[str] = []
        infer_confidence = 0.0

        if not matched:
            matched, infer_hits, infer_confidence = _infer_dimension_value_from_text(dimension, text_bank)
            if matched:
                source = "script_inference"
                raw_value = matched.get("id")

        diagnostics.append({
            "dimension": dimension.get("key"),
            "raw_value": raw_value,
            "source": source,
            "matched": matched.get("id") if matched else None,
            "inference_hits": infer_hits,
            "confidence": infer_confidence if source == "script_inference" else 1.0 if matched else 0.0,
        })

        if matched:
            resolved[dim_key] = {
                "dimension": dimension.get("key"),
                "value": matched.get("id"),
                "title": matched.get("title") or matched.get("id"),
                "source": source or "unknown",
                "confidence": infer_confidence if source == "script_inference" else 1.0,
                "inference_hits": infer_hits,
            }

    return {
        "resolved_dimensions": resolved,
        "diagnostics": diagnostics,
    }


def _combo_rule_matches(rule: Dict[str, Any], resolved_dimensions: Dict[str, Dict[str, Any]]) -> bool:
    when = rule.get("when") if isinstance(rule.get("when"), dict) else {}
    if not when:
        return False
    for key, expected in when.items():
        actual = (resolved_dimensions.get(_norm_key(key)) or {}).get("value")
        if actual != expected:
            return False
    return True


def resolve_scene_analysis_feature_bundle(
    project_metadata: Optional[Dict[str, Any]] = None,
    explicit_features: Optional[Dict[str, Any]] = None,
    script_text: Optional[str] = None,
    mode: Optional[str] = None,
) -> Dict[str, Any]:
    registry = load_scene_analysis_feature_registry()
    requested_mode = _norm_key(mode or registry.get("default_mode") or "classic")
    available_modes = {_norm_key(item.get("id")): item for item in (registry.get("modes") or []) if isinstance(item, dict)}
    mode_meta = available_modes.get(requested_mode) or available_modes.get(_norm_key(registry.get("default_mode") or "classic"))

    if not mode_meta:
        mode_meta = {"id": "classic", "inject_feature_skills": False}

    inject_feature_skills = bool(mode_meta.get("inject_feature_skills"))
    base_prompt_file = _norm_text(mode_meta.get("base_prompt_file") or registry.get("base_prompt_file") or _DEFAULT_ROUTED_BASE_PROMPT)
    normalized_features: Dict[str, str] = {}
    selected_skills: List[Dict[str, Any]] = []
    dimension_analysis = analyze_scene_dimensions(
        project_metadata=project_metadata,
        explicit_features=explicit_features,
        script_text=script_text,
    )
    resolved_dimensions = dimension_analysis.get("resolved_dimensions") if isinstance(dimension_analysis.get("resolved_dimensions"), dict) else {}
    diagnostics: List[Dict[str, Any]] = list(dimension_analysis.get("diagnostics") or [])

    for dimension in registry.get("dimensions", []):
        if not isinstance(dimension, dict):
            continue
        dim_key = _norm_key(dimension.get("key"))
        resolved = resolved_dimensions.get(dim_key)
        if not resolved:
            continue

        normalized_features[dim_key] = str(resolved.get("value"))
        if inject_feature_skills:
            matched = _match_dimension_value(dimension, resolved.get("value"))
            prompt_text = _norm_text((matched or {}).get("prompt"))
            if prompt_text:
                selected_skills.extend(_expand_skill_variants({
                    "skill_id": f"{dimension.get('key')}.{resolved.get('value')}",
                    "dimension": dimension.get("key"),
                    "value": resolved.get("value"),
                    "title": resolved.get("title") or resolved.get("value"),
                    "prompt": prompt_text,
                    "source": resolved.get("source") or "unknown",
                    **_copy_prompt_fragments(matched or {}),
                }))

    combo_matches: List[Dict[str, Any]] = []
    if inject_feature_skills:
        for rule in registry.get("combo_rules", []):
            if not isinstance(rule, dict):
                continue
            if not _combo_rule_matches(rule, resolved_dimensions):
                continue
            prompt_text = _norm_text(rule.get("prompt"))
            if not prompt_text:
                continue
            combo_matches.append({
                "skill_id": rule.get("id") or "combo.unnamed",
                "dimension": "combo",
                "value": rule.get("id") or "combo",
                "title": rule.get("title") or rule.get("id") or "组合 Skill",
                "prompt": prompt_text,
                "source": "decision_engine_combo",
                "when": rule.get("when") or {},
                **_copy_prompt_fragments(rule),
            })

        expanded_combo_matches: List[Dict[str, Any]] = []
        for combo_skill in combo_matches:
            expanded_combo_matches.extend(_expand_skill_variants(combo_skill))

        combo_matches = expanded_combo_matches
        selected_skills.extend(combo_matches)

    slot_blocks: Dict[str, str] = {}
    if inject_feature_skills and selected_skills:
        slot_fragments: Dict[str, List[str]] = {}
        for skill in selected_skills:
            token = _slot_token_for_skill(skill)
            block = _format_slot_block(skill)
            if not block:
                continue
            slot_fragments.setdefault(token, []).append(block)
        slot_blocks = {
            token: "\n\n".join(parts).strip()
            for token, parts in slot_fragments.items()
            if parts
        }

    system_prompt_block = "\n\n".join(slot_blocks.values()).strip()

    return {
        "version": registry.get("version", 1),
        "mode": mode_meta.get("id") or "classic",
        "enabled": inject_feature_skills,
        "base_prompt_file": base_prompt_file,
        "normalized_features": normalized_features,
        "resolved_dimensions": resolved_dimensions,
        "selected_skills": selected_skills,
        "combo_matches": combo_matches,
        "slot_blocks": slot_blocks,
        "known_slot_tokens": _known_slot_tokens(registry),
        "system_prompt_block": system_prompt_block,
        "diagnostics": diagnostics,
    }


def get_scene_analysis_feature_catalog() -> Dict[str, Any]:
    registry = load_scene_analysis_feature_registry()
    dimensions: List[Dict[str, Any]] = []
    for dimension in registry.get("dimensions", []):
        if not isinstance(dimension, dict):
            continue
        dimensions.append({
            "key": dimension.get("key"),
            "title": dimension.get("title"),
            "description": dimension.get("description"),
            "source_keys": dimension.get("source_keys") or [],
            "values": [
                {
                    "id": item.get("id"),
                    "title": item.get("title"),
                    "description": item.get("description"),
                    "aliases": item.get("aliases") or [],
                }
                for item in (dimension.get("values") or [])
                if isinstance(item, dict)
            ],
        })

    return {
        "version": registry.get("version", 1),
        "default_mode": registry.get("default_mode", "classic"),
        "base_prompt_file": registry.get("base_prompt_file") or _DEFAULT_ROUTED_BASE_PROMPT,
        "modes": registry.get("modes") or [],
        "dimensions": dimensions,
        "combo_rules": [
            {
                "id": item.get("id"),
                "title": item.get("title"),
                "when": item.get("when") or {},
                "description": item.get("description"),
            }
            for item in (registry.get("combo_rules") or [])
            if isinstance(item, dict)
        ],
    }