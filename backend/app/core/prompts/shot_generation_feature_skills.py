import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings

logger = logging.getLogger(__name__)

_PROMPTS_ROOT = Path(settings.BASE_DIR) / "app" / "core" / "prompts"
_FEATURE_STACK_ROOT = _PROMPTS_ROOT / "skills" / "shot_generation_feature_stack"
_REGISTRY_PATH = _FEATURE_STACK_ROOT / "registry.json"
_DEFAULT_ROUTED_BASE_PROMPT = "skills/shot_generation.md"
_COMBO_SLOT_TOKEN = "[[SHOT_GENERATION_COMBO_RULES]]"


def _norm_text(value: Any) -> str:
    return str(value or "").strip()


def _norm_key(value: Any) -> str:
    return _norm_text(value).lower().replace("-", "_").replace(" ", "_")


def _slot_token_for_dimension(dimension_key: Any) -> str:
    return f"[[SHOT_GENERATION_{_norm_key(dimension_key).upper()}_RULES]]"


def _known_slot_tokens(registry: Optional[Dict[str, Any]] = None) -> List[str]:
    registry = registry if isinstance(registry, dict) else load_shot_generation_feature_registry()
    tokens = [_COMBO_SLOT_TOKEN]
    for dimension in registry.get("dimensions", []):
        if not isinstance(dimension, dict):
            continue
        token = _norm_text(dimension.get("slot_token")) or _slot_token_for_dimension(dimension.get("key"))
        if token:
            tokens.append(token)
    seen = set()
    unique_tokens: List[str] = []
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        unique_tokens.append(token)
    return unique_tokens


def _format_slot_block(skill: Dict[str, Any]) -> str:
    title = _norm_text(skill.get("title") or skill.get("skill_id") or "Routed Rules")
    prompt_text = _norm_text(skill.get("prompt"))
    if not prompt_text:
        return ""
    return f"## {title}\n{prompt_text}".strip()


def render_shot_generation_routed_prompt(base_prompt_text: str, feature_bundle: Optional[Dict[str, Any]] = None) -> str:
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
def load_shot_generation_feature_registry() -> Dict[str, Any]:
    if not _REGISTRY_PATH.exists():
        logger.warning("shot generation feature registry not found: %s", _REGISTRY_PATH)
        return {"version": 1, "default_mode": "classic", "modes": [], "dimensions": [], "combo_rules": []}

    try:
        with _REGISTRY_PATH.open("r", encoding="utf-8") as handle:
            parsed = json.load(handle)
        if isinstance(parsed, dict):
            return parsed
    except Exception as exc:
        logger.error("failed to load shot generation feature registry: %s", exc)

    return {"version": 1, "default_mode": "classic", "modes": [], "dimensions": [], "combo_rules": []}


def get_shot_generation_feature_catalog() -> Dict[str, Any]:
    registry = load_shot_generation_feature_registry()
    return {
        "version": registry.get("version", 1),
        "default_mode": registry.get("default_mode") or "classic",
        "modes": registry.get("modes") or [],
        "dimensions": [
            {
                "key": item.get("key"),
                "title": item.get("title"),
                "source_keys": item.get("source_keys") or [],
                "slot_token": item.get("slot_token") or _slot_token_for_dimension(item.get("key")),
            }
            for item in (registry.get("dimensions") or [])
            if isinstance(item, dict)
        ],
    }


def _normalize_mode_alias(value: Any) -> str:
    normalized = _norm_key(value)
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
    return aliases.get(normalized, normalized)


def _resolve_mode(project_metadata: Optional[Dict[str, Any]], explicit_mode: Optional[str], registry: Dict[str, Any]) -> str:
    explicit_mode = _normalize_mode_alias(explicit_mode)
    if explicit_mode in {"classic", "routed"}:
        return explicit_mode

    project_metadata = project_metadata if isinstance(project_metadata, dict) else {}
    for key in ("shot_generation_mode", "shot_prompt_mode", "prompt_mode", "default_mode"):
        candidate = _normalize_mode_alias(project_metadata.get(key))
        if candidate in {"classic", "routed"}:
            return candidate

    return _normalize_mode_alias(registry.get("default_mode")) or "classic"


def _pick_feature_raw_value(
    dimension: Dict[str, Any],
    project_metadata: Optional[Dict[str, Any]],
    explicit_features: Optional[Dict[str, Any]],
) -> Tuple[str, str]:
    explicit_features = explicit_features if isinstance(explicit_features, dict) else {}
    project_metadata = project_metadata if isinstance(project_metadata, dict) else {}
    explicit_norm = {_norm_key(k): v for k, v in explicit_features.items()}
    project_norm = {_norm_key(k): v for k, v in project_metadata.items()}

    aliases = [_norm_key(dimension.get("key"))] + [_norm_key(alias) for alias in (dimension.get("source_keys") or [])]

    for alias in aliases:
        value = explicit_norm.get(alias)
        if _norm_text(value):
            return _norm_text(value), "explicit"

    for alias in aliases:
        value = project_norm.get(alias)
        if _norm_text(value):
            return _norm_text(value), "project_metadata"

    return "", ""


def _render_template(template: str, value: str) -> str:
    if not template:
        return ""
    return str(template).replace("{value}", value).strip()


def _match_when_clause(actual_value: str, expected_values: Any) -> bool:
    actual_norm = _norm_key(actual_value)
    if not actual_norm:
        return False
    for expected in (expected_values or []):
        if _norm_key(expected) == actual_norm:
            return True
    return False


def resolve_shot_generation_feature_bundle(
    *,
    project_metadata: Optional[Dict[str, Any]] = None,
    explicit_features: Optional[Dict[str, Any]] = None,
    script_text: Optional[str] = None,
    mode: Optional[str] = None,
) -> Dict[str, Any]:
    registry = load_shot_generation_feature_registry()
    resolved_mode = _resolve_mode(project_metadata, mode, registry)
    known_slot_tokens = _known_slot_tokens(registry)
    diagnostics: List[str] = []
    normalized_features: Dict[str, str] = {}
    resolved_dimensions: Dict[str, Dict[str, Any]] = {}
    selected_skills: List[Dict[str, Any]] = []

    if resolved_mode != "routed":
        return {
            "mode": "classic",
            "enabled": False,
            "base_prompt_file": "skills/shot_generation.md",
            "known_slot_tokens": known_slot_tokens,
            "slot_blocks": {},
            "normalized_features": {},
            "resolved_dimensions": {},
            "selected_skills": [],
            "combo_matches": [],
            "diagnostics": diagnostics,
            "script_text_len": len(_norm_text(script_text)),
        }

    for dimension in registry.get("dimensions", []):
        if not isinstance(dimension, dict):
            continue
        raw_value, source = _pick_feature_raw_value(dimension, project_metadata, explicit_features)
        dimension_key = _norm_key(dimension.get("key"))
        slot_token = _norm_text(dimension.get("slot_token")) or _slot_token_for_dimension(dimension_key)
        normalized_features[dimension_key] = raw_value
        resolved_dimensions[dimension_key] = {
            "value": raw_value,
            "source": source,
            "slot_token": slot_token,
        }
        if not raw_value:
            diagnostics.append(f"dimension:{dimension_key}:missing")
            continue

        prompt_text = _render_template(_norm_text(dimension.get("prompt_template")), raw_value)
        if not prompt_text:
            diagnostics.append(f"dimension:{dimension_key}:empty_prompt")
            continue

        selected_skills.append({
            "skill_id": f"{dimension_key}.{_norm_key(raw_value)}",
            "dimension": dimension_key,
            "value": raw_value,
            "title": _norm_text(dimension.get("title") or dimension_key),
            "prompt": prompt_text,
            "slot_token": slot_token,
            "source": source,
        })

    combo_matches: List[Dict[str, Any]] = []
    for combo in registry.get("combo_rules", []):
        if not isinstance(combo, dict):
            continue
        when = combo.get("when") if isinstance(combo.get("when"), dict) else {}
        matched = True
        for key, expected_values in when.items():
            actual_value = normalized_features.get(_norm_key(key), "")
            if not _match_when_clause(actual_value, expected_values):
                matched = False
                break
        if not matched:
            continue
        combo_skill = {
            "skill_id": _norm_text(combo.get("skill_id") or "combo"),
            "dimension": "combo",
            "value": "combo",
            "title": _norm_text(combo.get("title") or combo.get("skill_id") or "Combo Rules"),
            "prompt": _norm_text(combo.get("prompt")),
            "slot_token": _norm_text(combo.get("slot_token")) or _COMBO_SLOT_TOKEN,
            "source": "combo_rule",
            "when": when,
        }
        if combo_skill["prompt"]:
            combo_matches.append(combo_skill)
            selected_skills.append(combo_skill)

    slot_blocks: Dict[str, str] = {}
    for skill in selected_skills:
        slot_token = _norm_text(skill.get("slot_token"))
        if not slot_token:
            continue
        block = _format_slot_block(skill)
        if not block:
            continue
        slot_blocks.setdefault(slot_token, [])
        slot_blocks[slot_token].append(block)

    slot_blocks_rendered = {
        token: "\n\n".join(blocks).strip()
        for token, blocks in slot_blocks.items()
        if isinstance(blocks, list) and blocks
    }

    return {
        "mode": "routed",
        "enabled": True,
        "base_prompt_file": _DEFAULT_ROUTED_BASE_PROMPT,
        "known_slot_tokens": known_slot_tokens,
        "slot_blocks": slot_blocks_rendered,
        "normalized_features": normalized_features,
        "resolved_dimensions": resolved_dimensions,
        "selected_skills": selected_skills,
        "combo_matches": combo_matches,
        "diagnostics": diagnostics,
        "script_text_len": len(_norm_text(script_text)),
    }