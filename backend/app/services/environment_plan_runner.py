# -*- coding: utf-8 -*-
"""Whole-episode environment planning: scout shooting envs, then splice reuse/new skeletons."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.all_models import User
from app.schemas.agent import AnalyzeSceneRequest
from app.services.scene_markdown_orchestration import _extract_analysis_text_from_result
from app.services.script_analysis_flow import (
    SceneMarkerParseError,
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
    reused_items_needing_description,
    rewrite_reused_ident_positioning,
    scene_has_new_environments,
    scene_reused_environment_names,
    strip_placeholder_reused_sections,
)

_ENVIRONMENT_COMPLETION_MARKER = "[ENVIRONMENT_PLAN_OUTPUT_END]"
_MARKER_MISS_CODES = {
    "SCENE_MARKER_BLOCK_MISSING",
    "SCENE_MARKER_EMPTY_BLOCK",
    "SCENE_MARKER_NO_SCENES",
}

logger = logging.getLogger("api_logger")


def _marker_diag(text: str) -> str:
    sample = str(text or "")
    head = sample[:80].replace("\n", " ")
    return (
        f"chars={len(sample)} "
        f"block_start={bool(re.search(r'SCENES_BLOCK_START', sample, re.IGNORECASE))} "
        f"scene_start={bool(re.search(r'SCENE_START', sample, re.IGNORECASE))} "
        f"scene_end={bool(re.search(r'SCENE_END', sample, re.IGNORECASE))} "
        f"content_start={bool(re.search(r'SCENE_CONTENT_START', sample, re.IGNORECASE))} "
        f"head={head!r}"
    )


def _parse_scene_units_or_none(text: str):
    try:
        units = parse_scene_units_from_markers(text)
    except SceneMarkerParseError as exc:
        return None, exc
    return units, None


_SCRIPT_HASH_COMMENT_RE = re.compile(r"<!--\s*script_hash:[^>]*-->", re.IGNORECASE)


def _normalize_stage_echo(text: str) -> str:
    return _SCRIPT_HASH_COMMENT_RE.sub("", str(text or "")).strip()


def _scene_ids(units) -> Tuple[str, ...]:
    found: List[str] = []
    for unit in units or ():
        scene_id = str(getattr(unit, "scene_id", "") or "").strip()
        if scene_id:
            found.append(scene_id)
    return tuple(found)


def _ids_disjoint(left: Tuple[str, ...], right: Tuple[str, ...]) -> bool:
    return bool(left) and bool(right) and set(left).isdisjoint(right)


def _stage1_slot_text(outputs: Dict[str, Any], key: str) -> str:
    slot = outputs.get(key)
    if isinstance(slot, dict):
        return str(slot.get("content") or "")
    if isinstance(slot, str):
        return slot
    return ""


def _load_environment_plan_sources(db: Session, episode_id: int) -> Dict[str, Any]:
    """Current script and the latest global-orchestration slot outrank older stage-1 copies."""
    empty = {"scene_split": "", "script_text": "", "stale_texts": []}
    if int(episode_id or 0) <= 0 or db is None:
        return empty
    from app.models.all_models import Episode
    from app.services.soft_delete import _active_episode_clause

    episode = (
        db.query(Episode)
        .filter(Episode.id == int(episode_id), _active_episode_clause())
        .populate_existing()
        .first()
    )
    if episode is None:
        return empty
    split = ""
    stale: List[str] = []
    raw_outputs = str(getattr(episode, "ai_stage_outputs", "") or "").strip()
    if raw_outputs:
        try:
            payload = json.loads(raw_outputs)
            outputs = (((payload.get("stages") or {}).get("stage1") or {}).get("outputs") or {})
            if isinstance(outputs, dict):
                split = _stage1_slot_text(outputs, "scene_split")
                for key in ("raw_text", "adapted_script", "environment_plan"):
                    stale.append(_stage1_slot_text(outputs, key))
        except Exception:
            logger.warning(
                "[environment_plan] stage outputs unreadable episode_id=%s",
                episode_id,
            )
    stale.append(str(getattr(episode, "ai_scene_analysis_adaptation", "") or ""))
    stale.append(str(getattr(episode, "ai_scene_analysis_result", "") or ""))
    return {
        "scene_split": split,
        "script_text": str(getattr(episode, "script_content", "") or ""),
        "stale_texts": stale,
    }


def choose_environment_plan_scene_text(
    payload_text: str,
    *,
    scene_split: str = "",
    script_text: str = "",
    stale_texts: List[str] | None = None,
) -> str:
    """Pick the scene text that belongs to the current script.

    A request that still carries an older stage-1 copy is not reused when the
    saved global orchestration, or the current script, is a different scene set.
    """
    payload = str(payload_text or "").strip()
    split = str(scene_split or "").strip()
    script = str(script_text or "").strip()
    payload_units, payload_exc = _parse_scene_units_or_none(payload)
    split_units, _split_exc = _parse_scene_units_or_none(split)
    script_units, _script_exc = _parse_scene_units_or_none(script)
    payload_ids = _scene_ids(payload_units)
    split_ids = _scene_ids(split_units)
    script_ids = _scene_ids(script_units)
    payload_norm = _normalize_stage_echo(payload)
    split_norm = _normalize_stage_echo(split)
    stale_norms = {
        _normalize_stage_echo(item)
        for item in (stale_texts or [])
        if _normalize_stage_echo(item)
    }

    def finish(chosen: str, reason: str) -> str:
        if reason and _normalize_stage_echo(chosen) != payload_norm:
            chosen_units, _chosen_exc = _parse_scene_units_or_none(chosen)
            logger.warning(
                "[environment_plan] using current scene text reason=%s request_ids=%s chosen_ids=%s chars=%s",
                reason,
                ",".join(payload_ids),
                ",".join(_scene_ids(chosen_units)),
                len(chosen or ""),
            )
        return chosen

    if split_units and script_units and _ids_disjoint(split_ids, script_ids):
        if payload_units and payload_ids == script_ids:
            return finish(payload, "request_matches_current_script")
        return finish(script, "current_script")

    if split_units and payload_norm and payload_norm == split_norm:
        return payload or split
    request_is_stale = bool(payload_norm) and payload_norm in stale_norms and payload_norm != split_norm
    if split_units and request_is_stale:
        return finish(split, "saved_scene_split_over_stale_echo")
    if payload_units and split_units and payload_ids == split_ids:
        return payload
    if payload_units and split_units and payload_ids != split_ids:
        if script_ids and script_ids == payload_ids:
            return finish(payload, "request_matches_current_script")
        if script_ids and script_ids == split_ids:
            return finish(split, "saved_scene_split_matches_script")
        return finish(split, "saved_scene_split")
    if payload_units:
        if script_ids and script_ids != payload_ids and not split_units:
            return finish(script, "current_script")
        return payload
    if split_units:
        return finish(split, "saved_scene_split")
    if script_units:
        return finish(script, "current_script")
    for item in stale_texts or []:
        candidate = str(item or "").strip()
        if not candidate or _normalize_stage_echo(candidate) == payload_norm:
            continue
        candidate_units, _candidate_exc = _parse_scene_units_or_none(candidate)
        if candidate_units:
            return finish(candidate, "saved_stage_text")
    if payload_exc is not None and payload_exc.code not in _MARKER_MISS_CODES:
        raise HTTPException(status_code=422, detail=f"{payload_exc.code}:{payload_exc}") from payload_exc
    logger.error(
        "[environment_plan] scene markers missing payload=%s split=%s script=%s",
        _marker_diag(payload),
        _marker_diag(split),
        _marker_diag(script),
    )
    raise HTTPException(status_code=422, detail="ENVIRONMENT_PLAN_SCENE_MARKERS_MISSING")


def resolve_environment_plan_scene_text(
    db: Session,
    *,
    episode_id: int,
    payload_text: str,
) -> str:
    """Current script and saved global orchestration outrank a stale stage-1 request."""
    sources = _load_environment_plan_sources(db, int(episode_id or 0))
    return choose_environment_plan_scene_text(payload_text, **sources)


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


def _scene_patch_gap(patch_text: str, scene_ids: List[str]) -> str:
    """Empty when every scene has a spliceable patch. A broken envelope is the same gap."""
    wanted = [str(scene_id).strip() for scene_id in scene_ids if str(scene_id).strip()]
    if not wanted:
        return ""
    from app.services.script_analysis_flow_runner import _extract_environment_patches

    try:
        patches = _extract_environment_patches(patch_text)
    except HTTPException as exc:
        detail = str(getattr(exc, "detail", "") or "")
        if detail.startswith("ENV_SCENE_PATCH_"):
            return detail
        raise
    by_lower = {str(key).lower(): value for key, value in patches.items()}
    missing = [
        scene_id
        for scene_id in wanted
        if not str(by_lower.get(scene_id.lower()) or "").strip()
    ]
    if not missing:
        return ""
    return "ENVIRONMENT_PLAN_SCENE_PATCH_MISSING:" + ",".join(missing)


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
    scene_ids: List[str],
) -> str:
    from app.api.routers.prompts.analyze_scene import analyze_scene  # noqa: WPS433
    from app.services.script_analysis_flow_runner import (
        _strip_required_completion_marker,
        build_script_analysis_retry_api_attempts,
        scoped_node_body_usable,
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
        gap = ""
        if scoped_node_body_usable(patch_text):
            gap = _scene_patch_gap(patch_text, scene_ids)
            if not gap:
                return patch_text
        last_error = gap or (
            "ENVIRONMENT_PLAN_OUTPUT_TOO_SHORT"
            if _ENVIRONMENT_COMPLETION_MARKER in str(raw_text or "")
            else "ENVIRONMENT_PLAN_COMPLETION_MARKER_MISSING"
        )
        switched = api_id > 0 and api_id != original_api_id
        logger.warning(
            "[environment_plan] incomplete episode attempt=%s/%s code=%s body_chars=%s expected_marker=%s switched_api=%s",
            attempt,
            max_attempts,
            last_error,
            len(patch_text or ""),
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
                error_message=f"{last_error}; retrying environment plan like global orchestration",
            )
            db.commit()
    if str(last_error).startswith(("ENVIRONMENT_PLAN_SCENE_PATCH_MISSING:", "ENV_SCENE_PATCH_")):
        raise HTTPException(status_code=422, detail=last_error)
    raise HTTPException(status_code=422, detail=f"{last_error}:{_ENVIRONMENT_COMPLETION_MARKER}")


async def run_environment_plan(
    *,
    raw_payload: Dict[str, Any],
    current_user: User,
    db: Session,
    node_project_id: int,
    node_episode_id: int,
) -> Tuple[str, Dict[str, Any]]:
    scene_split_text = resolve_environment_plan_scene_text(
        db,
        episode_id=int(node_episode_id or 0),
        payload_text=str(raw_payload.get("text") or ""),
    )
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
            format_selected_global_environment_injection(
                selected_catalog,
                include_definitions=False,
            ),
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
        scene_ids=[str(unit.scene_id) for unit in units],
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
            planned_patches[scene_id] = _wrap_scene_patch(scene_id, body)
            continue
        ident = rewrite_reused_ident_positioning(
            ident,
            items,
            catalog,
            episode_blocks,
        )
        has_new = scene_has_new_environments(items)
        reused_items = [item for item in items if item.get("reuse")]
        if has_new:
            planned_scene_ids.append(scene_id)
        else:
            reuse_only_ids.append(scene_id)
        needing_description = reused_items_needing_description(body, reused_items)
        reused_patch = (
            build_reused_environment_patch(
                scene_id,
                needing_description,
                catalog,
                episode_env_blocks=episode_blocks,
            )
            if needing_description
            else ""
        )
        body_for_merge = strip_placeholder_reused_sections(body, needing_description)
        env_material = merge_reused_and_new_env_blocks(reused_patch, body_for_merge)
        composed = "\n".join(part for part in (ident, env_material) if str(part or "").strip()) or body
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

    from app.services.script_analysis_flow import (
        extract_prop_extract_blocks,
        splice_prop_extract_into_script,
    )
    from app.services.script_analysis_flow_runner import _merge_environment_patches

    aggregate = "\n\n".join(ordered_patches).strip() + f"\n{_ENVIRONMENT_COMPLETION_MARKER}"
    merged_text = _merge_environment_patches(scene_split_text, aggregate)
    prop_extract = extract_prop_extract_blocks(llm_output)
    merged_text = splice_prop_extract_into_script(merged_text, prop_extract)
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
