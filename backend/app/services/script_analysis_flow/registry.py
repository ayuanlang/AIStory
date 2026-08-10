from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional, Set


SCRIPT_ANALYSIS_FLOW_CONFIG_KEY = "script_analysis_flow_config"

DEFAULT_STAGE3_AUTO_START: Dict[str, bool] = {
    "storyboard_generation": True,
    "asset_design_character": True,
    "asset_design_prop": True,
    "asset_design_environment": True,
}


def _to_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _safe_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _normalize_node_key(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def normalize_script_analysis_flow_config(value: Any) -> Dict[str, Any]:
    payload = _safe_dict(value)
    stage3_raw = _safe_dict(payload.get("stage3_auto_start"))
    node_overrides_raw = _safe_dict(payload.get("node_overrides"))

    stage3_auto_start = dict(DEFAULT_STAGE3_AUTO_START)
    aliases = {
        "characters": "asset_design_character",
        "character": "asset_design_character",
        "asset_design_characters": "asset_design_character",
        "props": "asset_design_prop",
        "prop": "asset_design_prop",
        "asset_design_props": "asset_design_prop",
        "environments": "asset_design_environment",
        "environment": "asset_design_environment",
        "posters": "asset_design_environment",
        "poster": "asset_design_environment",
        "covers": "asset_design_environment",
        "cover": "asset_design_environment",
        "asset_design_environments": "asset_design_environment",
        "storyboard": "storyboard_generation",
        "storyboards": "storyboard_generation",
        "shots": "storyboard_generation",
        "shot_generation": "storyboard_generation",
        "ai_shots": "storyboard_generation",
    }
    for raw_key, raw_value in stage3_raw.items():
        normalized_key = aliases.get(_normalize_node_key(raw_key), _normalize_node_key(raw_key))
        if normalized_key in stage3_auto_start:
            stage3_auto_start[normalized_key] = _to_bool(raw_value, stage3_auto_start[normalized_key])

    node_overrides: Dict[str, Dict[str, Any]] = {}
    for raw_key, raw_override in node_overrides_raw.items():
        node_key = _normalize_node_key(raw_key)
        override = _safe_dict(raw_override)
        if not node_key or not override:
            continue
        normalized_override: Dict[str, Any] = {}
        if "auto_start" in override:
            normalized_override["auto_start"] = _to_bool(override.get("auto_start"), True)
        if "enabled" in override:
            normalized_override["enabled"] = _to_bool(override.get("enabled"), True)
        if normalized_override:
            node_overrides[node_key] = normalized_override

    return {
        "version": 1,
        "enabled": _to_bool(payload.get("enabled"), True),
        "stage3_auto_start": stage3_auto_start,
        "node_overrides": node_overrides,
    }


def _base_node_specs() -> List[Dict[str, Any]]:
    return [
        {
            "key": "script_optimization",
            "phase": 1,
            "title": "剧本优化",
            "prompt_file": "skills/scene_analysis_feature_stack/scene_planning_1_script_optimization.md",
            "depends_on": [],
            "outputs": ["adapted_script", "project_visual_backfill", "raw_text"],
            "persist_targets": ["episode.ai_scene_analysis_adaptation", "episode.ai_stage_outputs.stage1"],
            # Project context: FE may bake [项目信息]; BE injects only when absent.
            # Global assets: FE may bake [可复用Subject资产]; BE injects project-scoped selected IDs when absent.
            "injection_chain": [
                "frontend.stage1_project_context",
                "frontend.reusable_subject_assets",
                "backend.analyze_scene.project_metadata",
                "backend.analyze_scene.reuse_subject_assets",
                "backend.analyze_scene.attention_notes",
            ],
            "auto_start": True,
            "fan_out": None,
            "status": "planned",
        },
        {
            "key": "assets_extraction",
            "phase": 2,
            "title": "资产抽取",
            "prompt_file": "skills/scene_analysis_feature_stack/scene_planning_2_1_assets_extraction.md",
            "depends_on": ["script_optimization"],
            "outputs": ["subject_index"],
            "persist_targets": ["episode.ai_scene_analysis_subject_index", "episode.ai_stage_outputs.stage2_1"],
            "injection_chain": ["frontend.stage1_project_context", "frontend.reusable_subject_assets", "backend.analyze_scene.project_metadata", "backend.analyze_scene.reuse_subject_assets"],
            "auto_start": True,
            # Subject Index is the shared input for scene orchestration and per-category asset design.
            # After this node completes, scene_markdown and asset_design_* should run in parallel.
            "fan_out": ["scene_markdown", "asset_design_character", "asset_design_prop", "asset_design_environment"],
            "fan_out_mode": "parallel_after_complete",
            "status": "planned",
        },
        {
            "key": "scene_markdown",
            "phase": 2,
            "title": "场景编排 Markdown",
            "prompt_file": "skills/scene_analysis_feature_stack/scene_planning_2_2_beats_generation.md",
            "depends_on": ["script_optimization", "assets_extraction"],
            "outputs": ["scenes_markdown"],
            "persist_targets": ["episode.ai_stage_outputs.stage2_2", "scene_rows"],
            "injection_chain": ["frontend.stage1_project_context", "backend.analyze_scene.project_metadata", "backend.analyze_scene.persisted_subject_index"],
            "auto_start": True,
            "fan_out": "per_scene",
            "status": "planned",
        },
        {
            "key": "storyboard_generation",
            "phase": 2,
            "title": "逐场景分镜生成",
            "prompt_file": "skills/shot_generation.md",
            # Per imported scene: scene_markdown (workspace import) + asset_design_environment
            # (environments + posters/covers) must both be ready before shot generation.
            # Character/prop design is intentionally not a dependency.
            "depends_on": ["scene_markdown", "asset_design_environment"],
            "outputs": ["shots_markdown", "shot_rows"],
            "persist_targets": ["scene.ai_shots_result", "shot_rows"],
            "executor": "shot_generation.batch_per_scene",
            # Draft: skills/shot_generation.md via llm_service.
            # Optional post-pass: AgentScope Video CN polish
            # (skills/shot_video_prompt_optimize_agentscope.md).
            "injection_chain": ["backend.shot_generation.project_context", "backend.shot_generation.feature_bundle", "backend.shot_generation.scene_context", "backend.shot_generation.scene_subject_index_only", "backend.shot_generation.scene_subject_image_prompts_cn"],
            "auto_start": True,
            "fan_out": "per_scene",
            "status": "routable_existing_executor",
        },
        {
            "key": "asset_design_character",
            "phase": 3,
            "title": "角色资产实现",
            "prompt_file": "skills/scene_analysis_feature_stack/entity_design_character.md",
            "depends_on": ["assets_extraction"],
            "outputs": ["subjects_json.characters"],
            "persist_targets": ["episode.ai_entity_design_result", "entity_rows.character"],
            "injection_chain": ["frontend.entity_design_common_prompt", "frontend.asset_design_project_context", "frontend.filtered_subject_index", "backend.analyze_scene.project_metadata"],
            "auto_start": True,
            "fan_out": None,
            "status": "planned",
        },
        {
            "key": "asset_design_prop",
            "phase": 3,
            "title": "道具资产实现",
            "prompt_file": "skills/scene_analysis_feature_stack/entity_design_prop.md",
            "depends_on": ["assets_extraction"],
            "outputs": ["subjects_json.props"],
            "persist_targets": ["episode.ai_entity_design_result", "entity_rows.prop"],
            "injection_chain": ["frontend.entity_design_common_prompt", "frontend.asset_design_project_context", "frontend.filtered_subject_index", "backend.analyze_scene.project_metadata"],
            "auto_start": True,
            "fan_out": None,
            "status": "planned",
        },
        {
            "key": "asset_design_environment",
            "phase": 3,
            "title": "场景/海报资产实现",
            "prompt_file": "skills/scene_analysis_feature_stack/entity_design_environment_and_poster.md",
            "depends_on": ["assets_extraction"],
            "outputs": ["subjects_json.environments", "subjects_json.posters", "subjects_json.covers"],
            "persist_targets": ["episode.ai_entity_design_result", "entity_rows.environment", "entity_rows.poster"],
            "injection_chain": ["frontend.entity_design_common_prompt", "frontend.asset_design_project_context", "frontend.filtered_subject_index", "backend.analyze_scene.project_metadata"],
            "auto_start": True,
            "fan_out": None,
            "status": "planned",
        },
    ]


def _apply_config_to_nodes(nodes: List[Dict[str, Any]], config: Dict[str, Any]) -> List[Dict[str, Any]]:
    normalized_config = normalize_script_analysis_flow_config(config)
    stage3_auto_start = normalized_config.get("stage3_auto_start") or {}
    node_overrides = normalized_config.get("node_overrides") or {}

    out: List[Dict[str, Any]] = []
    for node in nodes:
        item = dict(node)
        key = str(item.get("key") or "")
        if key in stage3_auto_start:
            item["auto_start"] = bool(stage3_auto_start.get(key))
        override = node_overrides.get(key) if isinstance(node_overrides.get(key), dict) else {}
        if "auto_start" in override:
            item["auto_start"] = bool(override.get("auto_start"))
        if "enabled" in override:
            item["enabled"] = bool(override.get("enabled"))
        else:
            item.setdefault("enabled", True)
        out.append(item)
    return out


def get_script_analysis_flow_registry(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    normalized_config = normalize_script_analysis_flow_config(config or {})
    nodes = _apply_config_to_nodes(_base_node_specs(), normalized_config)
    return {
        "version": 1,
        "config": normalized_config,
        "nodes": nodes,
        "phase_order": [1, 2, 3],
        "stage3_auto_start": normalized_config.get("stage3_auto_start") or {},
    }


def build_script_analysis_flow_plan(
    config: Optional[Dict[str, Any]] = None,
    requested_nodes: Optional[List[str]] = None,
    start_node: Optional[str] = None,
) -> Dict[str, Any]:
    registry = get_script_analysis_flow_registry(config)
    nodes = [dict(node) for node in (registry.get("nodes") or []) if node.get("enabled", True)]
    requested: Set[str] = {_normalize_node_key(item) for item in (requested_nodes or []) if _normalize_node_key(item)}
    start = _normalize_node_key(start_node)

    if requested:
        keep = set(requested)
        changed = True
        by_key = {str(node.get("key")): node for node in nodes}
        while changed:
            changed = False
            for key in list(keep):
                for dep in by_key.get(key, {}).get("depends_on") or []:
                    if dep not in keep:
                        keep.add(dep)
                        changed = True
        nodes = [node for node in nodes if str(node.get("key")) in keep]
    elif start:
        by_key = {str(node.get("key")): node for node in nodes}
        reachable = {start}
        changed = True
        while changed:
            changed = False
            for node in nodes:
                key = str(node.get("key"))
                deps = set(node.get("depends_on") or [])
                if key not in reachable and deps.intersection(reachable):
                    reachable.add(key)
                    changed = True
        required_deps = set()
        stack = [start]
        while stack:
            current = stack.pop()
            if current in required_deps:
                continue
            required_deps.add(current)
            stack.extend(by_key.get(current, {}).get("depends_on") or [])
        keep = reachable.union(required_deps)
        nodes = [node for node in nodes if str(node.get("key")) in keep]

    runnable = []
    manual = []
    for node in nodes:
        key = str(node.get("key") or "")
        item = {
            "key": key,
            "phase": node.get("phase"),
            "depends_on": node.get("depends_on") or [],
            "auto_start": bool(node.get("auto_start")),
        }
        if item["auto_start"]:
            runnable.append(item)
        else:
            manual.append(item)

    return {
        "version": registry.get("version", 1),
        "enabled": bool((registry.get("config") or {}).get("enabled", True)),
        "nodes": nodes,
        "runnable_nodes": runnable,
        "manual_nodes": manual,
        "stage3_auto_start": deepcopy(registry.get("stage3_auto_start") or {}),
    }