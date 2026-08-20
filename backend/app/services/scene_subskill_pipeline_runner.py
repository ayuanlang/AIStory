# -*- coding: utf-8 -*-
"""Per-scene Stage-1 subskill orchestration."""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, List, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.all_models import Episode, User
from app.schemas.agent import AnalyzeSceneRequest
from app.schemas.user_auth import (
    USER_ACTIVE_LEVEL_DEFAULT,
    resolve_user_batch_parallel_limit,
)
from app.services.db_session_utils import _release_db_connection, _snapshot_user_principal
from app.services.scene_markdown_orchestration import _extract_analysis_text_from_result
from app.services.script_analysis_flow import (
    COMPREHENSIVE_INFO_PATTERN,
    SCENES_BLOCK_END_TOKEN,
    SCENES_BLOCK_START_TOKEN,
    SPECIAL_SCENE_ANALYSIS_PATTERN,
    SceneMarkerParseError,
    build_scene_subskill_task_payloads,
    parse_scene_units_from_markers,
    persist_script_optimization_stage,
    upsert_pipeline_node_status,
)
from app.services.soft_delete import _active_episode_clause

logger = logging.getLogger("api_logger")

DRAMA_PROMPT = "skills/scene_analysis_feature_stack/scene_planning_1_subskill_drama_standardization.md"
VFX_PROMPT = "skills/scene_analysis_feature_stack/scene_planning_1_subskill_vfx.md"
XIAN_PROMPT = "skills/scene_analysis_feature_stack/scene_planning_1_subskill_xian_attack.md"
STAGING_PROMPT = "skills/scene_analysis_feature_stack/scene_planning_1_subskill_staging_env.md"

_SUBSKILL_ACTION_LABELS = {
    DRAMA_PROMPT: "文戏标准化",
    VFX_PROMPT: "特效增强",
    XIAN_PROMPT: "仙攻增强",
    STAGING_PROMPT: "建置与入戏",
}
_SUBSKILL_COMPLETION_MARKERS = {
    DRAMA_PROMPT: "[DRAMA_STANDARDIZATION_OUTPUT_END]",
    VFX_PROMPT: "[VFX_SUBSKILL_OUTPUT_END]",
    XIAN_PROMPT: "[XIAN_ATTACK_OUTPUT_END]",
    STAGING_PROMPT: "[STAGING_ENV_OUTPUT_END]",
}


def _scene_subskill_failure_reason(exc: Exception) -> str:
    text = str(exc or "")
    if "COMPLETION_MARKER_MISSING" in text:
        return "子技能输出不完整，自动重试后仍缺少结束标签"
    if "OUTPUT_PARSE_FAILED" in text:
        return "子技能返回的场景结构无法解析"
    if "OUTPUT_SCENE_MISMATCH" in text:
        return "子技能返回了错误的场景编号"
    if "ROUTING_MISSING" in text:
        return "场景缺少特殊情景路由信息"
    if "NO_SCENES" in text:
        return "未解析到可执行的场景"
    return "逐场子技能执行失败"


def _strip_subskill_completion_marker(text: str, prompt_file: str) -> str:
    marker = _SUBSKILL_COMPLETION_MARKERS[prompt_file]
    source = str(text or "").strip()
    if not source or source.count(marker) != 1:
        return ""
    if source.splitlines()[-1].strip() != marker:
        return ""
    return source[: source.rfind(marker)].rstrip()


def _extract_project_tail(script_text: str) -> str:
    source = str(script_text or "").strip()
    match = re.search(r"`?\[SCENES_BLOCK_END\]`?", source, flags=re.IGNORECASE)
    if not match:
        return ""
    return source[match.end():].strip()


def _wrap_single_scene_input(scene_block: str, comprehensive_info: str, project_tail: str) -> str:
    parts = [SCENES_BLOCK_START_TOKEN]
    if str(comprehensive_info or "").strip():
        parts.append(str(comprehensive_info).strip())
    parts.append(str(scene_block or "").strip())
    parts.append(SCENES_BLOCK_END_TOKEN)
    if str(project_tail or "").strip():
        parts.append(str(project_tail).strip())
    return "\n".join(part for part in parts if part)


def _extract_single_scene_block(result_text: str, scene_id: str, fallback_special: str) -> str:
    text = str(result_text or "").strip()
    # SPECIAL_SCENE_ANALYSIS and COMPREHENSIVE_INFO are authoritative upstream
    # metadata. Subskills occasionally echo or duplicate these read-only blocks;
    # remove every returned copy before parsing, then reattach the original routing
    # block exactly once below.
    sanitized_text = SPECIAL_SCENE_ANALYSIS_PATTERN.sub("", text)
    sanitized_text = COMPREHENSIVE_INFO_PATTERN.sub("", sanitized_text)
    try:
        units = parse_scene_units_from_markers(sanitized_text)
    except SceneMarkerParseError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"SCENE_SUBSKILL_OUTPUT_PARSE_FAILED:{scene_id}:{exc.code}",
        ) from exc
    matches = [unit for unit in units if str(unit.scene_id).lower() == str(scene_id).lower()]
    if len(matches) != 1:
        raise HTTPException(
            status_code=422,
            detail=f"SCENE_SUBSKILL_OUTPUT_SCENE_MISMATCH:{scene_id}",
        )
    unit = matches[0]
    special = str(fallback_special or "").strip()
    return "\n".join(
        part
        for part in (
            special,
            unit.marker_start_token,
            unit.scene_text,
            unit.marker_end_token,
        )
        if str(part or "").strip()
    )


async def _call_scene_subskill(
    *,
    task_db: Session,
    current_user: User,
    base_payload: Dict[str, Any],
    prompt_file: str,
    scene_input: str,
    scene_id: str,
) -> str:
    from app.api.routers.prompts.analyze_scene import analyze_scene  # noqa: WPS433

    payload = dict(base_payload)
    payload.update(
        {
            "text": scene_input,
            "prompt_file": prompt_file,
            "system_prompt": None,
            "function_name": "script_analysis_scene_subskill",
            "action_name": f"{_SUBSKILL_ACTION_LABELS.get(prompt_file, '逐场子技能')} · {scene_id}",
            "scene_analysis_mode": None,
            "skip_episode_persist": True,
        }
    )
    completion_marker = _SUBSKILL_COMPLETION_MARKERS[prompt_file]
    max_attempts = 2
    for attempt in range(1, max_attempts + 1):
        result = await analyze_scene(
            AnalyzeSceneRequest(**payload),
            current_user=current_user,
            db=task_db,
            async_mode="0",
        )
        text = _extract_analysis_text_from_result(result).strip()
        if not text:
            failure_code = "SCENE_SUBSKILL_EMPTY_OUTPUT"
        elif not _strip_subskill_completion_marker(text, prompt_file):
            failure_code = "SCENE_SUBSKILL_COMPLETION_MARKER_MISSING"
        else:
            return _strip_subskill_completion_marker(text, prompt_file)
        logger.warning(
            "[scene_subskill_pipeline] incomplete output scene=%s prompt=%s attempt=%s/%s code=%s expected_marker=%s",
            scene_id,
            prompt_file,
            attempt,
            max_attempts,
            failure_code,
            completion_marker,
        )
        project_id = int(base_payload.get("project_id") or 0)
        episode_id = int(base_payload.get("episode_id") or 0)
        if project_id > 0 and episode_id > 0 and attempt < max_attempts:
            upsert_pipeline_node_status(
                task_db,
                project_id=project_id,
                episode_id=episode_id,
                script_id=f"episode:{episode_id}",
                node_name="scene_subskill_pipeline",
                status="running",
                progress_percent=15.0,
                retry_count=attempt,
                runtime_meta={
                    "business_event": "retry",
                    "business_reason": f"{_SUBSKILL_ACTION_LABELS.get(prompt_file, '逐场优化')}返回不完整",
                    "scene_id": scene_id,
                },
                error_code=failure_code,
                error_message=f"{completion_marker} missing; retrying scene subskill",
            )
            task_db.commit()
        if attempt >= max_attempts:
            raise HTTPException(
                status_code=422,
                detail=f"{failure_code}:{scene_id}:{completion_marker}",
            )
    raise HTTPException(status_code=422, detail=f"SCENE_SUBSKILL_OUTPUT_INVALID:{scene_id}")


async def run_scene_subskill_pipeline(
    *,
    raw_payload: Dict[str, Any],
    current_user: User,
    db: Session,
    node_episode_id: int,
) -> Dict[str, Any]:
    """Split scenes in code; run each scene chain serially while scenes run concurrently."""
    script_text = str(raw_payload.get("text") or "").strip()
    tasks = build_scene_subskill_task_payloads(script_text)
    if not tasks:
        raise HTTPException(status_code=422, detail="SCENE_SUBSKILL_NO_SCENES")
    missing_routes = [task["scene_id"] for task in tasks if not task.get("special_analysis")]
    if missing_routes:
        raise HTTPException(
            status_code=422,
            detail=f"SCENE_SUBSKILL_ROUTING_MISSING:{','.join(missing_routes)}",
        )

    max_concurrency = resolve_user_batch_parallel_limit(
        getattr(current_user, "is_active", USER_ACTIVE_LEVEL_DEFAULT),
    )
    project_id = int(raw_payload.get("project_id") or 0)
    if project_id > 0 and node_episode_id > 0:
        for task in tasks:
            upsert_pipeline_node_status(
                db,
                project_id=project_id,
                episode_id=node_episode_id,
                script_id=f"episode:{node_episode_id}",
                node_name="scene_subskill_scene",
                scene_id=str(task.get("scene_id") or ""),
                status="queued",
                progress_percent=0.0,
                runtime_meta={"business_event": "queued"},
                error_code=None,
                error_message=None,
            )
        db.commit()
    semaphore = asyncio.Semaphore(max(1, int(max_concurrency or 1)))
    project_tail = _extract_project_tail(script_text)
    user_principal = _snapshot_user_principal(current_user)

    async def _run_one(task: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        async with semaphore:
            task_db = SessionLocal()
            scene_id = str(task.get("scene_id") or "")
            try:
                project_id = int(raw_payload.get("project_id") or 0)
                if project_id > 0 and node_episode_id > 0:
                    upsert_pipeline_node_status(
                        task_db,
                        project_id=project_id,
                        episode_id=node_episode_id,
                        script_id=f"episode:{node_episode_id}",
                        node_name="scene_subskill_scene",
                        scene_id=scene_id,
                        status="running",
                        progress_percent=5.0,
                        runtime_meta={"business_event": "started"},
                    )
                    task_db.commit()
                current_block = str(task.get("scene_block") or "")
                called: List[str] = []
                steps = [(DRAMA_PROMPT, "drama")]
                if task.get("call_vfx"):
                    steps.append((VFX_PROMPT, "vfx"))
                if task.get("call_xian"):
                    steps.append((XIAN_PROMPT, "xian"))
                steps.append((STAGING_PROMPT, "staging"))
                for prompt_file, step_name in steps:
                    scene_input = _wrap_single_scene_input(
                        current_block,
                        str(task.get("comprehensive_info") or ""),
                        project_tail,
                    )
                    result_text = await _call_scene_subskill(
                        task_db=task_db,
                        current_user=user_principal,
                        base_payload=raw_payload,
                        prompt_file=prompt_file,
                        scene_input=scene_input,
                        scene_id=scene_id,
                    )
                    current_block = _extract_single_scene_block(
                        result_text,
                        scene_id,
                        str(task.get("special_analysis") or ""),
                    )
                    called.append(step_name)
                if project_id > 0 and node_episode_id > 0:
                    upsert_pipeline_node_status(
                        task_db,
                        project_id=project_id,
                        episode_id=node_episode_id,
                        script_id=f"episode:{node_episode_id}",
                        node_name="scene_subskill_scene",
                        scene_id=scene_id,
                        status="success",
                        progress_percent=100.0,
                        runtime_meta={
                            "business_event": "completed",
                            "scene_block": current_block,
                            "called_subskills": called,
                            "routes": task.get("routes") or {},
                        },
                    )
                    task_db.commit()
                return int(task.get("scene_order") or 0), {
                    "scene_id": scene_id,
                    "scene_order": int(task.get("scene_order") or 0),
                    "scene_block": current_block,
                    "called_subskills": called,
                    "routes": task.get("routes") or {},
                }
            except Exception as exc:
                project_id = int(raw_payload.get("project_id") or 0)
                if project_id > 0 and node_episode_id > 0:
                    upsert_pipeline_node_status(
                        task_db,
                        project_id=project_id,
                        episode_id=node_episode_id,
                        script_id=f"episode:{node_episode_id}",
                        node_name="scene_subskill_scene",
                        scene_id=scene_id,
                        status="failed",
                        progress_percent=100.0,
                        runtime_meta={
                            "business_event": "failed",
                            "business_reason": _scene_subskill_failure_reason(exc),
                        },
                        error_code="SCENE_SUBSKILL_SCENE_FAILED",
                        error_message=str(exc),
                    )
                    task_db.commit()
                raise
            finally:
                _release_db_connection(task_db)

    results = await asyncio.gather(*(_run_one(task) for task in tasks))
    ordered = [item for _, item in sorted(results, key=lambda pair: pair[0])]
    comprehensive = str(tasks[0].get("comprehensive_info") or "").strip()
    aggregate_parts = [SCENES_BLOCK_START_TOKEN]
    if comprehensive:
        aggregate_parts.append(comprehensive)
    aggregate_parts.extend(str(item.get("scene_block") or "").strip() for item in ordered)
    aggregate_parts.append(SCENES_BLOCK_END_TOKEN)
    if project_tail:
        aggregate_parts.append(project_tail)
    aggregate_text = "\n".join(part for part in aggregate_parts if part)

    if node_episode_id > 0:
        episode = (
            db.query(Episode)
            .filter(Episode.id == int(node_episode_id), _active_episode_clause())
            .first()
        )
        if episode is not None:
            persist_script_optimization_stage(
                db=db,
                episode=episode,
                result_content=aggregate_text,
                node_output_key="scene_subskills",
            )

    logger.info(
        "[scene_subskill_pipeline] completed scenes=%s concurrency=%s episode_id=%s",
        len(ordered),
        max_concurrency,
        node_episode_id,
    )
    return {
        "content": aggregate_text,
        "adapted_script": aggregate_text,
        "per_scene_parallel": True,
        "per_scene_outputs": ordered,
        "scene_count": len(ordered),
    }
