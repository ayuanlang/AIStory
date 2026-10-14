# -*- coding: utf-8 -*-
"""Per-node advanced specs saved by the user and injected into that node's user prompt."""
from __future__ import annotations

from typing import Any, Dict

from sqlalchemy.orm import Session

from app.core.prompt_injection import wrap_injection_section

NODE_ADVANCED_SPEC_LABEL = "必须满足的高级规格"

_FLOW_NODE_SPEC_KEYS = {
    "script_optimization": "script_optimization",
    "scene_split": "scene_split",
    "environment_plan": "environment_plan",
    "asset_design_character": "asset_design_character",
    "asset_design_prop": "asset_design_prop",
    "asset_design_environment": "asset_design_environment",
    "asset_design_environment_quad": "asset_design_environment_quad",
}
_PROMPT_STEP_KEYS = {
    "skills/scene_analysis_feature_stack/scene_planning_1_subskill_drama_standardization.md": "drama_opt",
    "skills/scene_analysis_feature_stack/scene_planning_1_subskill_combat.md": "combat_opt",
    "skills/scene_analysis_feature_stack/scene_planning_1_subskill_vfx.md": "combat_opt",
    "skills/scene_analysis_feature_stack/scene_planning_1_subskill_xian_attack.md": "combat_opt",
    "skills/scene_analysis_feature_stack/scene_planning_1_subskill_derived_framing.md": "framing_opt",
    "skills/scene_analysis_feature_stack/scene_planning_1_subskill_staging_env.md": "staging_opt",
}
_REEXTRACT_SPEC_KEYS = {
    "character": "asset_design_character",
    "prop": "asset_design_prop",
}


def read_node_advanced_specs(episode: Any) -> Dict[str, str]:
    info = getattr(episode, "episode_info", None)
    raw = info.get("node_advanced_specs") if isinstance(info, dict) else None
    if not isinstance(raw, dict):
        return {}
    specs: Dict[str, str] = {}
    for key, value in raw.items():
        stable_key = str(key or "").strip()
        text = str(value or "").strip()
        if stable_key and text:
            specs[stable_key] = text
    return specs


def lookup_node_advanced_spec(specs: Dict[str, str], key: str) -> str:
    return str((specs or {}).get(str(key or "").strip()) or "").strip()


def format_node_advanced_spec_block(spec_text: str) -> str:
    body = str(spec_text or "").strip()
    if not body:
        return ""
    return wrap_injection_section(
        NODE_ADVANCED_SPEC_LABEL,
        "以下是用户为本节点写下的高级规格。完成本节点既定输出的同时，必须满足这些规格。\n"
        f"{body}",
    )


def prepend_node_advanced_spec(user_content: str, spec_text: str) -> str:
    block = format_node_advanced_spec_block(spec_text)
    if not block:
        return str(user_content or "")
    base = str(user_content or "").strip()
    if not base:
        return block
    return f"{block}\n\n{base}"


def resolve_flow_node_advanced_spec(episode: Any, *, node_key: str, reextract_target: str = "") -> str:
    specs = read_node_advanced_specs(episode)
    reextract_key = _REEXTRACT_SPEC_KEYS.get(str(reextract_target or "").strip().lower(), "")
    if reextract_key:
        return lookup_node_advanced_spec(specs, reextract_key)
    spec_key = _FLOW_NODE_SPEC_KEYS.get(str(node_key or "").strip(), "")
    if not spec_key:
        return ""
    return lookup_node_advanced_spec(specs, spec_key)


def resolve_subskill_advanced_spec(episode: Any, *, prompt_file: str, scene_id: str) -> str:
    step_key = _PROMPT_STEP_KEYS.get(str(prompt_file or "").replace("\\", "/").strip(), "")
    scene = str(scene_id or "").strip()
    if not step_key or not scene:
        return ""
    return lookup_node_advanced_spec(read_node_advanced_specs(episode), f"{step_key}:{scene}")


def resolve_storyboard_advanced_spec(episode: Any, scene_no: str) -> str:
    scene = str(scene_no or "").strip()
    if not scene:
        return ""
    return lookup_node_advanced_spec(read_node_advanced_specs(episode), f"storyboard:{scene}")


def _load_episode(db: Session, episode_id: Any) -> Any:
    from app.models.all_models import Episode
    from app.services.soft_delete import _active_episode_clause

    try:
        eid = int(episode_id or 0)
    except (TypeError, ValueError):
        return None
    if eid <= 0:
        return None
    return (
        db.query(Episode)
        .filter(Episode.id == eid, _active_episode_clause())
        .first()
    )


def load_subskill_advanced_spec(db: Session, episode_id: Any, prompt_file: str, scene_id: str) -> str:
    episode = _load_episode(db, episode_id)
    if episode is None:
        return ""
    return resolve_subskill_advanced_spec(episode, prompt_file=prompt_file, scene_id=scene_id)


def load_storyboard_advanced_spec(episode: Any, scene_no: str) -> str:
    return resolve_storyboard_advanced_spec(episode, scene_no)
