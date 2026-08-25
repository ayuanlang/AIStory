# -*- coding: utf-8 -*-
"""Whole-episode environment planning: scout shooting envs, then splice reuse/new skeletons."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.all_models import User
from app.schemas.agent import AnalyzeSceneRequest
from app.services.scene_markdown_orchestration import _extract_analysis_text_from_result
from app.services.script_analysis_flow import (
    parse_scene_units_from_markers,
    upsert_pipeline_node_status,
)
from app.services.script_analysis_flow.environment_reuse import (
    build_reused_environment_patch,
    build_project_main_environment_injection,
    collect_episode_env_blocks_by_name,
    collect_project_main_environment_catalog,
    collect_selected_global_environment_catalog,
    extract_scene_env_ident_block,
    find_catalog_environment,
    format_selected_global_environment_injection,
    merge_reused_and_new_env_blocks,
    parse_scene_env_ident_items,
    scene_has_new_environments,
    scene_reused_environment_names,
)

_ENVIRONMENT_COMPLETION_MARKER = "[ENVIRONMENT_PLAN_OUTPUT_END]"

logger = logging.getLogger("api_logger")


def _patch_body_from_wrapped(patch_text: str, scene_id: str) -> str:
    from app.services.script_analysis_flow_runner import _extract_environment_patches

    patches = _extract_environment_patches(patch_text)
    if not patches:
        return ""
    by_lower = {key.lower(): value for key, value in patches.items()}
    body = by_lower.get(str(scene_id).lower(), "")
    if body:
        return body
    return ""


def _wrap_scene_patch(scene_id: str, body: str) -> str:
    inner = str(body or "").strip()
    if not inner:
        return ""
    if f"[ENV_SCENE_PATCH_START:{scene_id}]" in inner:
        return inner
    return "\n".join(
        (
            f"[ENV_SCENE_PATCH_START:{scene_id}]",
            inner,
            f"[ENV_SCENE_PATCH_END:{scene_id}]",
        )
    )


async def _call_environment_plan_episode(
    *,
    db: Session,
    current_user: User,
    base_payload: Dict[str, Any],
    episode_input: str,
    node_project_id: int,
    node_episode_id: int,
) -> str:
    from app.api.routers.prompts.analyze_scene import analyze_scene  # noqa: WPS433
    from app.services.script_analysis_flow_runner import (
        _strip_required_completion_marker,
        build_script_analysis_retry_api_attempts,
    )

    payload = dict(base_payload)
    payload.update(
        {
            "text": episode_input,
            "prompt_file": payload.get("prompt_file")
            or "skills/scene_analysis_feature_stack/scene_planning_1_subskill_environment.md",
            "system_prompt": None,
            "function_name": payload.get("function_name") or "script_analysis",
            "action_name": payload.get("action_name") or "环境规划",
            "scene_analysis_mode": "stage1",
            "skip_episode_persist": True,
        }
    )
    last_error = "ENVIRONMENT_PLAN_COMPLETION_MARKER_MISSING"
    original_api_id, api_attempts = build_script_analysis_retry_api_attempts(
        db,
        payload.get("function_name") or "script_analysis",
        payload.get("system_api_id"),
        node_key="environment_plan",
    )
    max_attempts = len(api_attempts)
    for attempt, api_id in enumerate(api_attempts, start=1):
        attempt_payload = dict(payload)
        if api_id > 0:
            attempt_payload["system_api_id"] = api_id
        result = await analyze_scene(
            AnalyzeSceneRequest(**attempt_payload),
            current_user=current_user,
            db=db,
            async_mode="0",
        )
        raw_text = _extract_analysis_text_from_result(result)
        patch_text = _strip_required_completion_marker(raw_text, _ENVIRONMENT_COMPLETION_MARKER)
        if patch_text:
            return patch_text
        switched = api_id > 0 and api_id != original_api_id
        logger.warning(
            "[environment_plan] incomplete episode attempt=%s/%s expected_marker=%s switched_api=%s",
            attempt,
            max_attempts,
            _ENVIRONMENT_COMPLETION_MARKER,
            switched,
        )
        if node_project_id > 0 and node_episode_id > 0 and attempt < max_attempts:
            upsert_pipeline_node_status(
                db,
                project_id=node_project_id,
                episode_id=node_episode_id,
                script_id=f"episode:{node_episode_id}",
                node_name="environment_plan",
                status="running",
                progress_percent=15.0,
                retry_count=attempt,
                runtime_meta={"business_event": "retry", "business_reason": "环境规划返回不完整"},
                error_code=last_error,
                error_message="completion marker missing; retrying environment plan like global orchestration",
            )
            db.commit()
    raise HTTPException(status_code=422, detail=f"{last_error}:{_ENVIRONMENT_COMPLETION_MARKER}")


async def run_environment_plan(
    *,
    raw_payload: Dict[str, Any],
    current_user: User,
    db: Session,
    node_project_id: int,
    node_episode_id: int,
) -> Tuple[str, Dict[str, Any]]:
    scene_split_text = str(raw_payload.get("text") or "").strip()
    units = parse_scene_units_from_markers(scene_split_text)
    if not units:
        raise HTTPException(status_code=422, detail="ENVIRONMENT_PLAN_NO_SCENES")

    catalog = []
    selected_catalog = []
    if node_project_id > 0:
        catalog = collect_project_main_environment_catalog(
            db,
            project_id=int(node_project_id),
            current_episode_id=int(node_episode_id or 0),
        )
        selected_catalog = collect_selected_global_environment_catalog(
            db,
            project_id=int(node_project_id),
            episode_id=int(node_episode_id or 0),
            reuse_subject_assets=raw_payload.get("reuse_subject_assets"),
        )
        for item in selected_catalog:
            if not find_catalog_environment(catalog, item.get("name")):
                catalog.append(item)

    instruction = "\n\n".join(
        (
            build_project_main_environment_injection(catalog, for_planning=True),
            format_selected_global_environment_injection(selected_catalog),
        )
    )
    episode_input = f"{instruction}\n\n{scene_split_text}"
    llm_output = await _call_environment_plan_episode(
        db=db,
        current_user=current_user,
        base_payload=raw_payload,
        episode_input=episode_input,
        node_project_id=node_project_id,
        node_episode_id=node_episode_id,
    )

    planned_patches: Dict[str, str] = {}
    reuse_only_ids: List[str] = []
    planned_scene_ids: List[str] = []
    episode_blocks = collect_episode_env_blocks_by_name(scene_split_text)
    episode_blocks.update(collect_episode_env_blocks_by_name(llm_output))

    for unit in units:
        scene_id = str(unit.scene_id)
        body = _patch_body_from_wrapped(llm_output, scene_id)
        if not body:
            raise HTTPException(status_code=422, detail=f"ENVIRONMENT_PLAN_SCENE_PATCH_MISSING:{scene_id}")
        ident = extract_scene_env_ident_block(body, scene_id)
        items = parse_scene_env_ident_items(body, scene_id)
        if not ident or not items:
            raise HTTPException(status_code=422, detail=f"ENVIRONMENT_PLAN_ENV_IDENT_MISSING:{scene_id}")
        has_new = scene_has_new_environments(items)
        reused_items = [item for item in items if item.get("reuse")]
        if has_new:
            planned_scene_ids.append(scene_id)
            if "[ENV_BLOCK_START" not in body.upper():
                raise HTTPException(status_code=422, detail=f"ENVIRONMENT_PLAN_NEW_ENV_BLOCK_MISSING:{scene_id}")
        else:
            reuse_only_ids.append(scene_id)
        reused_patch = (
            build_reused_environment_patch(
                scene_id,
                reused_items,
                catalog,
                episode_env_blocks=episode_blocks,
            )
            if reused_items
            else ""
        )
        if reused_items and not reused_patch:
            raise HTTPException(status_code=422, detail=f"ENVIRONMENT_PLAN_REUSE_BLOCK_MISSING:{scene_id}")
        env_material = merge_reused_and_new_env_blocks(reused_patch, body)
        composed = "\n".join(part for part in (ident, env_material) if str(part or "").strip())
        planned_patches[scene_id] = _wrap_scene_patch(scene_id, composed)
        if reused_items:
            logger.info(
                "[environment_plan] reused library env scene=%s names=%s",
                scene_id,
                scene_reused_environment_names(items),
            )

    ordered_patches = [planned_patches[str(unit.scene_id)] for unit in units if str(unit.scene_id) in planned_patches]
    missing = [str(unit.scene_id) for unit in units if str(unit.scene_id) not in planned_patches]
    if missing:
        raise HTTPException(status_code=422, detail=f"ENVIRONMENT_PLAN_SCENE_PATCH_MISSING:{','.join(missing)}")

    from app.services.script_analysis_flow_runner import _merge_environment_patches

    aggregate = "\n\n".join(ordered_patches).strip() + f"\n{_ENVIRONMENT_COMPLETION_MARKER}"
    merged_text = _merge_environment_patches(scene_split_text, aggregate)
    return merged_text, {
        "scene_count": len(units),
        "reused_scene_ids": reuse_only_ids,
        "planned_scene_ids": planned_scene_ids,
        "catalog_count": len(catalog),
        "whole_episode": True,
    }


async def run_environment_plan_per_scene(**kwargs):
    """Compatibility alias: environment planning is whole-episode."""
    return await run_environment_plan(**kwargs)
