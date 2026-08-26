# -*- coding: utf-8 -*-
"""Execute a single script-analysis flow node (sync path)."""
from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.settings import get_script_analysis_flow_config
from app.models.all_models import Episode, User
from app.schemas.agent import AnalyzeSceneRequest
from app.services.credit_error import (
    INSUFFICIENT_CREDITS_CODE,
    credit_error_code,
    credit_error_user_message,
    http_exception_detail_text,
    is_insufficient_credits_error,
)
from app.services.endpoint_misc import _build_scene_analysis_blocking_failure_detail
from app.services.project_access import _require_project_access
from app.services.scene_ai_shots_batch import _start_scene_ai_shots_batch_for_episode
from app.services.soft_delete import _active_episode_clause
from app.services.scene_markdown_orchestration import (
    _extract_analysis_text_from_result,
)
from app.services.scene_markdown_runner import _run_scene_markdown_node_per_scene
from app.services.scene_subskill_pipeline_runner import run_scene_subskill_pipeline
from app.services.script_analysis_flow import (
    STAGE_SCENE_MARKDOWN,
    coerce_target_scene_ids_for_orchestration,
    get_script_analysis_flow_registry,
    import_analyze_scene_stage_result,
    parse_scene_units_from_markers,
    persist_script_optimization_stage,
    resolve_assets_extraction_source_text,
    upsert_pipeline_node_status,
)
from app.services.script_analysis_flow.environment_reuse import SCENE_ENV_IDENT_PATTERN
from app.services.script_analysis_llm_config import (
    _resolve_script_analysis_dropdown_order,
    _select_script_analysis_api_order,
)
from app.services.subject_index_resolve import (
    _script_optimization_has_project_visual_backfill,
    _subject_index_has_cover_poster,
)

logger = logging.getLogger("api_logger")

_FLOW_NODE_ACTION_LABELS = {
    "script_optimization": "剧本优化（旧版）",
    "scene_split": "全局统筹",
    "environment_plan": "环境规划",
    "scene_subskill_pipeline": "文戏增强/构图/建置",
    "assets_extraction": "资产清单提取",
    "scene_markdown": "场景编排",
    "asset_design_character": "角色资产设计",
    "asset_design_prop": "道具资产设计",
    "asset_design_environment": "环境资产设计",
}
_FLOW_DOWNSTREAM_NODES = {
    "scene_split": [
        "environment_plan",
        "scene_subskill_pipeline",
        "asset_design_character",
        "asset_design_prop",
    ],
    "environment_plan": [
        "asset_design_environment",
        "storyboard_generation",
    ],
    "scene_subskill_pipeline": ["storyboard_generation"],
}

_ENV_SCENE_PATCH_PATTERN = re.compile(
    r"`?\[ENV_SCENE_PATCH_START:([^\s\]]+)\]`?"
    r"(.*?)"
    r"`?\[ENV_SCENE_PATCH_END:([^\s\]]+)\]`?",
    re.IGNORECASE | re.DOTALL,
)
_ENVIRONMENT_COMPLETION_MARKER = "[ENVIRONMENT_PLAN_OUTPUT_END]"
_ENV_BLOCK_WITH_COVERAGE_PATTERN = re.compile(
    r"\s*`?\[ENV_BLOCK_START(?:\:[^\]]+)?\]`?.*?"
    r"`?\[ENV_BLOCK_END(?:\:[^\]]+)?\]`?"
    r"(?:\s*【Beat→衍生ENV剧情覆盖矩阵】.*?【ENV覆盖综合】[^\r\n]*)?",
    re.IGNORECASE | re.DOTALL,
)


def _extract_environment_patches(environment_output: str) -> Dict[str, str]:
    """Return scene-id keyed environment-only payloads from patch or legacy full output."""
    source = str(environment_output or "").strip()
    patches: Dict[str, str] = {}
    for match in _ENV_SCENE_PATCH_PATTERN.finditer(source):
        start_id = str(match.group(1) or "").strip()
        end_id = str(match.group(3) or "").strip()
        if not start_id or start_id.lower() != end_id.lower():
            raise HTTPException(status_code=422, detail=f"ENV_SCENE_PATCH_ID_MISMATCH:{start_id}:{end_id}")
        if start_id in patches:
            raise HTTPException(status_code=422, detail=f"ENV_SCENE_PATCH_DUPLICATE:{start_id}")
        body = str(match.group(2) or "").strip()
        has_env = "[ENV_BLOCK_START" in body.upper() and "[ENV_BLOCK_END" in body.upper()
        has_ident = "[SCENE_ENV_IDENT_START" in body.upper() and "[SCENE_ENV_IDENT_END" in body.upper()
        if not body or not (has_env or has_ident):
            raise HTTPException(status_code=422, detail=f"ENV_SCENE_PATCH_BLOCK_MISSING:{start_id}")
        patches[start_id] = body
    if patches:
        return patches

    # Compatibility: extract only ENV material if an older prompt returns full scenes.
    try:
        units = parse_scene_units_from_markers(source)
    except Exception:
        units = []
    for unit in units:
        block_match = _ENV_BLOCK_WITH_COVERAGE_PATTERN.search(str(unit.scene_text or ""))
        if block_match:
            patches[str(unit.scene_id)] = str(block_match.group(0) or "").strip()
    return patches


def _strip_required_completion_marker(text: str, marker: str) -> str:
    source = str(text or "").strip()
    if not source or source.count(marker) != 1:
        return ""
    lines = source.splitlines()
    if not lines or lines[-1].strip() != marker:
        return ""
    return source[: source.rfind(marker)].rstrip()


def _merge_environment_patches(scene_split_text: str, environment_output: str) -> str:
    """Programmatically insert each environment patch into its authoritative split Scene."""
    source = str(scene_split_text or "").strip()
    units = parse_scene_units_from_markers(source)
    expected_ids = [str(unit.scene_id) for unit in units]
    patches = _extract_environment_patches(environment_output)
    patch_by_lower = {scene_id.lower(): body for scene_id, body in patches.items()}
    missing = [scene_id for scene_id in expected_ids if scene_id.lower() not in patch_by_lower]
    extras = [scene_id for scene_id in patches if scene_id.lower() not in {item.lower() for item in expected_ids}]
    if missing or extras:
        raise HTTPException(
            status_code=422,
            detail=f"ENV_SCENE_PATCH_COVERAGE_MISMATCH:missing={','.join(missing) or '-'};extra={','.join(extras) or '-'}",
        )

    merged = source
    for scene_id in expected_ids:
        scene_pattern = re.compile(
            rf"(`?\[SCENE_START:{re.escape(scene_id)}\]`?)(.*?)(`?\[SCENE_END:[^\s\]]+\]`?)",
            re.IGNORECASE | re.DOTALL,
        )
        scene_match = scene_pattern.search(merged)
        if not scene_match:
            raise HTTPException(status_code=422, detail=f"ENV_SCENE_TARGET_MISSING:{scene_id}")
        scene_body = str(scene_match.group(2) or "")
        scene_body = _ENV_BLOCK_WITH_COVERAGE_PATTERN.sub("", scene_body, count=1)
        scene_body = SCENE_ENV_IDENT_PATTERN.sub("", scene_body)
        content_marker = re.search(
            rf"`?\[SCENE_CONTENT_START:{re.escape(scene_id)}\]`?",
            scene_body,
            flags=re.IGNORECASE,
        )
        if not content_marker:
            raise HTTPException(status_code=422, detail=f"ENV_SCENE_CONTENT_MARKER_MISSING:{scene_id}")
        patch = patch_by_lower[scene_id.lower()].strip()
        scene_body = (
            f"{scene_body[:content_marker.start()].rstrip()}\n"
            f"{patch}\n"
            f"{scene_body[content_marker.start():].lstrip()}"
        )
        merged = f"{merged[:scene_match.start()]}{scene_match.group(1)}{scene_body}{scene_match.group(3)}{merged[scene_match.end():]}"
    return merged.strip()


_FALSE_EPISODE_PERSIST_WARNING = (
    "No episode_id was provided; raw LLM output was returned but not persisted to episode fields."
)
_FALSE_EPISODE_PERSIST_CODE = "ANALYSIS_EPISODE_ID_MISSING_NOT_PERSISTED"


def _mark_analysis_result_persisted(result: Any, episode_id: int) -> Any:
    """Flow nodes often skip analyze_scene persist, then write episode fields themselves."""
    if not isinstance(result, dict):
        return result
    updated = dict(result)
    meta = dict(updated.get("meta") or {})
    meta["saved_to_episode"] = True
    meta["saved_episode_id"] = int(episode_id)
    meta["request_episode_id"] = meta.get("request_episode_id") or int(episode_id)
    updated["meta"] = meta
    warnings = [
        item
        for item in list(updated.get("warnings") or [])
        if _FALSE_EPISODE_PERSIST_WARNING not in str(item)
    ]
    codes = [
        item
        for item in list(updated.get("warning_codes") or [])
        if str(item) != _FALSE_EPISODE_PERSIST_CODE
    ]
    if "warnings" in updated or warnings:
        updated["warnings"] = warnings
    if "warning_codes" in updated or codes:
        updated["warning_codes"] = codes
    return updated


def _replace_analysis_result_text(result: Any, merged_text: str) -> Any:
    if isinstance(result, str):
        return merged_text
    if not isinstance(result, dict):
        return {"content": merged_text, "adapted_script": merged_text}
    updated = dict(result)
    for key in ("result", "content", "adapted_script"):
        if key in updated or key in {"content", "adapted_script"}:
            updated[key] = merged_text
    if isinstance(updated.get("data"), dict):
        data = dict(updated["data"])
        for key in ("result", "content", "adapted_script"):
            if key in data:
                data[key] = merged_text
        updated["data"] = data
    return updated


def _coerce_system_api_id(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _next_script_analysis_fallback_api_id(db: Session, function_name: Any, system_api_id: Any) -> int:
    ordered_ids = _resolve_script_analysis_dropdown_order(db, function_name)
    _, fallback_ids = _select_script_analysis_api_order(ordered_ids, system_api_id)
    if not fallback_ids:
        return 0
    return _coerce_system_api_id(fallback_ids[0])


SCRIPT_ANALYSIS_MAIN_PATH_RETRY_ATTEMPTS = 3


def build_script_analysis_retry_api_attempts(
    db: Session,
    function_name: Any,
    system_api_id: Any,
    *,
    node_key: str = "",
) -> Tuple[int, List[int]]:
    """Scene-split schedule: same API × 2, then one fallback API (or same if none)."""
    original_api_id = _coerce_system_api_id(system_api_id)
    fallback_api_id = 0
    try:
        fallback_api_id = _next_script_analysis_fallback_api_id(
            db,
            function_name or "script_analysis",
            original_api_id or system_api_id,
        )
    except Exception as fallback_exc:
        logger.warning(
            "[剧本分析流程] 节点 %s 无法解析备用 API | err=%s",
            node_key or "main_path",
            fallback_exc,
        )
    api_attempts = [original_api_id, original_api_id]
    if fallback_api_id > 0 and fallback_api_id != original_api_id:
        api_attempts.append(fallback_api_id)
    else:
        api_attempts.append(original_api_id)
        logger.warning(
            "[剧本分析流程] 节点 %s 无可用备用 API，第三次仍使用当前 API | system_api_id=%s",
            node_key or "main_path",
            original_api_id or None,
        )
    return original_api_id, api_attempts


async def execute_scene_analysis_flow_node(
    *,
    request: Any,
    db: Session,
    current_user: User,
) -> Dict[str, Any]:
    """Run one workflow node (non-async). Lazy-imports analyze_scene to avoid cycles."""
    from app.api.routers.prompts.analyze_scene import analyze_scene  # noqa: WPS433

    node_key = str(getattr(request, "node_key", "") or "").strip().lower().replace("-", "_")
    flow_started_perf = time.perf_counter()
    cfg = get_script_analysis_flow_config(db)
    registry = get_script_analysis_flow_registry(cfg)
    nodes = {str(node.get("key") or ""): node for node in (registry.get("nodes") or [])}
    node = nodes.get(node_key)
    if not node:
        raise HTTPException(status_code=404, detail=f"Script analysis flow node '{node_key}' not found")

    analyze_node_keys = {
        "script_optimization",
        "scene_split",
        "environment_plan",
        "scene_subskill_pipeline",
        "assets_extraction",
        "scene_markdown",
        "asset_design_character",
        "asset_design_prop",
        "asset_design_environment",
    }
    if node_key in {"assets_extraction", "scene_markdown"}:
        node_project_id = int(request.project_id or 0)
        node_episode_id = int(request.episode_id or 0)
        logger.info("[剧本分析流程] 节点 %s 已退役，跳过 LLM", node_key)
        if node_project_id > 0 and node_episode_id > 0:
            upsert_pipeline_node_status(
                db,
                project_id=node_project_id,
                episode_id=node_episode_id,
                script_id=f"episode:{node_episode_id}",
                node_name=node_key,
                status="success",
                progress_percent=100.0,
                runtime_meta={"business_event": "retired_skipped"},
            )
            if node_key == "scene_markdown":
                upsert_pipeline_node_status(
                    db,
                    project_id=node_project_id,
                    episode_id=node_episode_id,
                    script_id=f"episode:{node_episode_id}",
                    node_name="scene_planning",
                    status="success",
                    progress_percent=100.0,
                    runtime_meta={"business_event": "imported_from_staging"},
                )
            db.commit()
        return {
            "status": "completed",
            "node_key": node_key,
            "executor": "retired",
            "prompt_file": node.get("prompt_file"),
            "injection_chain": [],
            "result": {"retired": True, "content": ""},
        }

    if node_key in analyze_node_keys:
        raw_payload = dict(request.analyze_payload or {})
        if not raw_payload.get("text"):
            raise HTTPException(status_code=400, detail="analyze_payload.text is required for this workflow node")
        raw_payload["prompt_file"] = raw_payload.get("prompt_file") or node.get("prompt_file")
        raw_payload["function_name"] = raw_payload.get("function_name") or request.function_name or "script_analysis"
        raw_payload["system_api_id"] = raw_payload.get("system_api_id") or request.system_api_id
        target_scene_id = str(raw_payload.get("target_scene_id") or "").strip()
        target_scene_ids = coerce_target_scene_ids_for_orchestration(
            raw_payload,
            str(raw_payload.get("text") or ""),
        )
        scoped_rerun = bool(target_scene_ids)
        start_from_step = str(raw_payload.get("start_from_step") or "").strip()
        if node_key == "scene_markdown" and target_scene_id:
            scoped_action_name = f"场景编排 · {target_scene_id}"
        elif node_key == "scene_subskill_pipeline" and target_scene_id:
            scoped_action_name = (
                f"逐场优化 · {target_scene_id}"
                + (f" · {start_from_step}" if start_from_step else "")
            )
        else:
            scoped_action_name = _FLOW_NODE_ACTION_LABELS.get(node_key)
        raw_payload["action_name"] = (
            str(raw_payload.get("action_name") or "").strip()
            or scoped_action_name
        )
        if node_key in {"scene_split", "environment_plan"}:
            # Scene split returns the authoritative full script. Environment planning is
            # one whole-episode LLM call; code then injects reuse patches per scene.
            raw_payload["scene_analysis_mode"] = "stage1"
            raw_payload["skip_episode_persist"] = node_key == "environment_plan"
        
        logger.info(
            "[剧本分析流程] 准备执行节点 %s | prompt=%s | function=%s | system_api_id=%s | project_id=%s | episode_id=%s",
            node_key,
            raw_payload.get("prompt_file"),
            raw_payload.get("function_name"),
            raw_payload.get("system_api_id"),
            raw_payload.get("project_id"),
            raw_payload.get("episode_id"),
        )
        
        if request.project_id and not raw_payload.get("project_id"):
            raw_payload["project_id"] = request.project_id
        if request.episode_id and not raw_payload.get("episode_id"):
            raw_payload["episode_id"] = request.episode_id
        episode = None
        if raw_payload.get("episode_id"):
            episode = (
                db.query(Episode)
                .filter(
                    Episode.id == int(raw_payload.get("episode_id")),
                    _active_episode_clause(),
                )
                .first()
            )
            if not episode:
                raise HTTPException(status_code=404, detail="Episode not found or has been deleted")
            _require_project_access(db, episode.project_id, current_user)
            if raw_payload.get("project_id") and int(raw_payload.get("project_id")) != int(episode.project_id):
                raise HTTPException(status_code=400, detail="project_id does not match episode.project_id")
            # Scene import now happens from staging output. Subject Index is no longer a gate.
        elif raw_payload.get("project_id"):
            _require_project_access(db, int(raw_payload.get("project_id")), current_user)
            
        node_project_id = int(raw_payload.get("project_id") or request.project_id or 0)
        node_episode_id = int(raw_payload.get("episode_id") or request.episode_id or 0)
        if node_project_id > 0 and node_episode_id > 0:
            upsert_pipeline_node_status(
                db,
                project_id=node_project_id,
                episode_id=node_episode_id,
                script_id=f"episode:{node_episode_id}",
                node_name=node_key,
                status="running",
                progress_percent=5.0,
                retry_count=0,
                runtime_meta={"business_event": "started"},
            )
            if not scoped_rerun:
                for downstream_node in _FLOW_DOWNSTREAM_NODES.get(node_key, []):
                    upsert_pipeline_node_status(
                        db,
                        project_id=node_project_id,
                        episode_id=node_episode_id,
                        script_id=f"episode:{node_episode_id}",
                        node_name=downstream_node,
                        status="queued",
                        progress_percent=0.0,
                    )
            db.commit()

        llm_started_perf = time.perf_counter()
        logger.info("[剧本分析流程] 开始调用 evaluate_scene 执行节点 %s...", node_key)
        try:
            if node_key == "assets_extraction":
                # One whole-episode call: scene-split text + per-scene ENV injections.
                episode_adaptation = str(
                    getattr(episode, "ai_scene_analysis_adaptation", "") or ""
                ).strip() if episode is not None else ""
                resolved_assets_text = resolve_assets_extraction_source_text(
                    str(raw_payload.get("text") or ""),
                    episode_adaptation,
                )
                if resolved_assets_text:
                    raw_payload["text"] = resolved_assets_text
                original_api_id, api_attempts = build_script_analysis_retry_api_attempts(
                    db,
                    raw_payload.get("function_name") or "script_analysis",
                    raw_payload.get("system_api_id"),
                    node_key=node_key,
                )
                result = None
                assets_cover_poster_missing_after_retries = False
                max_attempts = len(api_attempts)
                for attempt, api_id in enumerate(api_attempts, start=1):
                    payload = dict(raw_payload)
                    if api_id > 0:
                        payload["system_api_id"] = api_id
                    switched = api_id > 0 and api_id != original_api_id
                    result = await analyze_scene(AnalyzeSceneRequest(**payload), current_user=current_user, db=db, async_mode="0")
                    result_text = _extract_analysis_text_from_result(result)
                    has_cover_poster = _subject_index_has_cover_poster(result_text)
                    if has_cover_poster:
                        if attempt > 1:
                            logger.info(
                                "[剧本分析流程] 节点 %s 在重试后通过 cover_poster 校验 | attempt=%s switched_api=%s",
                                node_key,
                                attempt,
                                switched,
                            )
                        break
                    logger.warning(
                        "[剧本分析流程] 节点 %s 缺少 cover_poster/poster 条目 | attempt=%s/%s switched_api=%s",
                        node_key,
                        attempt,
                        max_attempts,
                        switched,
                    )
                    if attempt >= max_attempts:
                        assets_cover_poster_missing_after_retries = True
                        logger.warning(
                            "[剧本分析流程] 节点 %s 在重试后仍缺少 cover_poster/poster，按非阻断告警继续 | episode_id=%s",
                            node_key,
                            node_episode_id,
                        )
                        break
                    upsert_pipeline_node_status(
                        db,
                        project_id=node_project_id,
                        episode_id=node_episode_id,
                        script_id=f"episode:{node_episode_id}",
                        node_name=node_key,
                        status="running",
                        progress_percent=15.0,
                        retry_count=attempt,
                        runtime_meta={"business_event": "retry", "business_reason": "资产清单缺少封面项"},
                        error_code="ASSETS_EXTRACTION_COVER_POSTER_MISSING",
                        error_message="cover_poster/poster missing, auto-retrying like scene_split",
                    )
                    db.commit()
                if assets_cover_poster_missing_after_retries and node_project_id > 0 and node_episode_id > 0:
                    upsert_pipeline_node_status(
                        db,
                        project_id=node_project_id,
                        episode_id=node_episode_id,
                        script_id=f"episode:{node_episode_id}",
                        node_name=node_key,
                        status="running",
                        progress_percent=85.0,
                        error_code="ASSETS_EXTRACTION_COVER_POSTER_MISSING",
                        error_message="cover_poster/poster missing after retries; continued as non-blocking warning",
                    )
                    db.commit()
            elif node_key in {"script_optimization", "scene_split"}:
                # Visual backfill JSON is a completeness gate, not a standalone artifact.
                # Incomplete output => full Stage 1 rerun (same API x2, then one switched API).
                original_api_id, api_attempts = build_script_analysis_retry_api_attempts(
                    db,
                    raw_payload.get("function_name") or "script_analysis",
                    raw_payload.get("system_api_id"),
                    node_key=node_key,
                )
                result = None
                max_attempts = len(api_attempts)
                for attempt, api_id in enumerate(api_attempts, start=1):
                    payload = dict(raw_payload)
                    if api_id > 0:
                        payload["system_api_id"] = api_id
                    switched = api_id > 0 and api_id != original_api_id
                    if switched:
                        logger.info(
                            "[剧本分析流程] 节点 %s 换 API 整段重跑 | attempt=%s/%s from=%s to=%s",
                            node_key,
                            attempt,
                            max_attempts,
                            original_api_id,
                            api_id,
                        )
                    result = await analyze_scene(
                        AnalyzeSceneRequest(**payload),
                        current_user=current_user,
                        db=db,
                        async_mode="0",
                    )
                    result_text = _extract_analysis_text_from_result(result)
                    if _script_optimization_has_project_visual_backfill(result_text):
                        if attempt > 1:
                            logger.info(
                                "[剧本分析流程] 节点 %s 整段重跑后通过完整性校验 | attempt=%s switched_api=%s",
                                node_key,
                                attempt,
                                switched,
                            )
                        break
                    logger.warning(
                        "[剧本分析流程] 节点 %s 缺少 Project Visual Backfill（输出不完整） | attempt=%s/%s switched_api=%s",
                        node_key,
                        attempt,
                        max_attempts,
                        switched,
                    )
                    if attempt >= max_attempts:
                        raise HTTPException(
                            status_code=422,
                            detail="SCRIPT_OPTIMIZATION_PROJECT_VISUAL_BACKFILL_MISSING",
                        )
                    upsert_pipeline_node_status(
                        db,
                        project_id=node_project_id,
                        episode_id=node_episode_id,
                        script_id=f"episode:{node_episode_id}",
                        node_name=node_key,
                        status="running",
                        progress_percent=15.0,
                        retry_count=attempt,
                        runtime_meta={"business_event": "retry", "business_reason": "全局统筹结果不完整"},
                        error_code="SCRIPT_OPTIMIZATION_PROJECT_VISUAL_BACKFILL_MISSING",
                        error_message=(
                            "incomplete Stage 1 output, switching API and rerunning"
                            if switched or (attempt + 1) == max_attempts
                            else "incomplete Stage 1 output, auto-retrying full script_optimization"
                        ),
                    )
                    db.commit()
            elif node_key == "environment_plan":
                from app.services.environment_plan_runner import run_environment_plan

                merged_text, plan_meta = await run_environment_plan(
                    raw_payload=raw_payload,
                    current_user=current_user,
                    db=db,
                    node_project_id=node_project_id,
                    node_episode_id=node_episode_id,
                )
                result = _replace_analysis_result_text(
                    {"content": merged_text, "adapted_script": merged_text, **plan_meta},
                    merged_text,
                )
                logger.info(
                    "[剧本分析流程] 环境规划整集完成 | scenes=%s reused=%s planned=%s catalog=%s",
                    plan_meta.get("scene_count"),
                    plan_meta.get("reused_scene_ids"),
                    plan_meta.get("planned_scene_ids"),
                    plan_meta.get("catalog_count"),
                )
                # analyze_scene may release/expire ORM instances while the long LLM call
                # is running. Re-query the Episode before Stage-1 persistence so deferred
                # attributes such as ai_stage_outputs remain session-bound.
                persist_episode = None
                if node_episode_id > 0:
                    persist_episode = (
                        db.query(Episode)
                        .filter(
                            Episode.id == int(node_episode_id),
                            _active_episode_clause(),
                        )
                        .populate_existing()
                        .first()
                    )
                if persist_episode is not None:
                    persist_script_optimization_stage(
                        db=db,
                        episode=persist_episode,
                        result_content=merged_text,
                        node_output_key="environment_plan",
                    )
                    result = _mark_analysis_result_persisted(result, int(node_episode_id))
            elif node_key == "scene_subskill_pipeline":
                result = await run_scene_subskill_pipeline(
                    raw_payload=raw_payload,
                    current_user=current_user,
                    db=db,
                    node_episode_id=node_episode_id,
                )
                if node_episode_id > 0:
                    result = _mark_analysis_result_persisted(result, int(node_episode_id))
            elif node_key == "scene_markdown":
                result = await _run_scene_markdown_node_per_scene(
                    raw_payload=raw_payload,
                    current_user=current_user,
                    db=db,
                    node_project_id=node_project_id,
                    node_episode_id=node_episode_id,
                )
            else:
                result = await analyze_scene(AnalyzeSceneRequest(**raw_payload), current_user=current_user, db=db, async_mode="0")
        except Exception as exc:
            if node_project_id > 0 and node_episode_id > 0:
                error_text = http_exception_detail_text(exc)
                credit_hit = is_insufficient_credits_error(exc)
                if credit_hit:
                    error_code = credit_error_code(exc)
                    error_message = credit_error_user_message(exc)
                elif "ASSETS_EXTRACTION_COVER_POSTER_MISSING" in error_text:
                    error_code = "ASSETS_EXTRACTION_COVER_POSTER_MISSING"
                    error_message = error_text or str(exc)
                elif "SCRIPT_OPTIMIZATION_PROJECT_VISUAL_BACKFILL_MISSING" in error_text:
                    error_code = "SCRIPT_OPTIMIZATION_PROJECT_VISUAL_BACKFILL_MISSING"
                    error_message = error_text or str(exc)
                elif "PROMPT_LEAK_DETECTED" in error_text:
                    error_code = "PROMPT_LEAK_DETECTED"
                    error_message = error_text or str(exc)
                elif "PROMPT_INJECTION_DETECTED" in error_text:
                    error_code = "PROMPT_INJECTION_DETECTED"
                    error_message = error_text or str(exc)
                else:
                    error_code = "FLOW_RUN_NODE_FAILED"
                    error_message = error_text or str(exc)
                upsert_pipeline_node_status(
                    db,
                    project_id=node_project_id,
                    episode_id=node_episode_id,
                    script_id=f"episode:{node_episode_id}",
                    node_name=node_key,
                    status="failed",
                    error_code=error_code,
                    error_message=error_message,
                    runtime_meta={"business_reason": error_message} if credit_hit else None,
                )
                db.commit()
            if (
                is_insufficient_credits_error(exc)
                and credit_error_code(exc) == INSUFFICIENT_CREDITS_CODE
                and not (isinstance(exc, HTTPException) and int(getattr(exc, "status_code", 0) or 0) == 402)
            ):
                raise HTTPException(
                    status_code=402,
                    detail={
                        "code": INSUFFICIENT_CREDITS_CODE,
                        "message": credit_error_user_message(exc),
                    },
                ) from exc
            raise
        llm_elapsed_ms = int((time.perf_counter() - llm_started_perf) * 1000)
        logger.info("[剧本分析流程] 节点 %s 执行完成 | llm_elapsed_ms=%s", node_key, llm_elapsed_ms)

        if node_key == "scene_split" and node_episode_id > 0:
            scene_split_episode = (
                db.query(Episode)
                .filter(Episode.id == int(node_episode_id), _active_episode_clause())
                .populate_existing()
                .first()
            )
            scene_split_text = _extract_analysis_text_from_result(result)
            if scene_split_episode is not None and scene_split_text.strip():
                from app.services.script_analysis_flow import (
                    extract_char_extract_blocks,
                    extract_prop_extract_blocks,
                    splice_char_extract_into_script,
                    splice_prop_extract_into_script,
                )

                scene_split_text = splice_char_extract_into_script(
                    scene_split_text,
                    extract_char_extract_blocks(scene_split_text),
                )
                scene_split_text = splice_prop_extract_into_script(
                    scene_split_text,
                    extract_prop_extract_blocks(scene_split_text),
                )
                result = _replace_analysis_result_text(result, scene_split_text)
                try:
                    persist_script_optimization_stage(
                        db=db,
                        episode=scene_split_episode,
                        result_content=scene_split_text,
                        node_output_key="scene_split",
                    )
                except Exception as persist_exc:
                    error_text = http_exception_detail_text(persist_exc)
                    error_code = (
                        "PROMPT_LEAK_DETECTED"
                        if "PROMPT_LEAK_DETECTED" in error_text
                        else (
                            "PROMPT_INJECTION_DETECTED"
                            if "PROMPT_INJECTION_DETECTED" in error_text
                            else "FLOW_RUN_NODE_FAILED"
                        )
                    )
                    upsert_pipeline_node_status(
                        db,
                        project_id=node_project_id,
                        episode_id=node_episode_id,
                        script_id=f"episode:{node_episode_id}",
                        node_name=node_key,
                        status="failed",
                        error_code=error_code,
                        error_message=error_text or str(persist_exc),
                    )
                    db.commit()
                    raise
                result = _mark_analysis_result_persisted(result, int(node_episode_id))

        if node_project_id > 0 and node_episode_id > 0:
            if node_key != "scene_markdown":
                partial_failure = isinstance(result, dict) and bool(result.get("partial_failure"))
                failed_scene_ids = (
                    list(result.get("failed_scene_ids") or [])
                    if isinstance(result, dict)
                    else []
                )
                upsert_pipeline_node_status(
                    db,
                    project_id=node_project_id,
                    episode_id=node_episode_id,
                    script_id=f"episode:{node_episode_id}",
                    node_name=node_key,
                    status="warning" if partial_failure else "success",
                    progress_percent=100.0,
                    error_code="SCENE_SUBSKILL_PARTIAL_FAILURE" if partial_failure else None,
                    error_message=(
                        f"timed out or failed: {', '.join(failed_scene_ids)}"
                        if partial_failure
                        else None
                    ),
                    runtime_meta=(
                        {"business_event": "partial_failure", "failed_scene_ids": failed_scene_ids}
                        if partial_failure
                        else None
                    ),
                )
            if node_key == "scene_subskill_pipeline" and not (
                isinstance(result, dict) and result.get("partial_failure")
            ):
                upsert_pipeline_node_status(
                    db,
                    project_id=node_project_id,
                    episode_id=node_episode_id,
                    script_id=f"episode:{node_episode_id}",
                    node_name="scene_planning",
                    status="success",
                    progress_percent=100.0,
                    runtime_meta={"business_event": "imported_from_staging"},
                )

            if node_key == "scene_markdown":
                # Step 4: parallel orchestration imports each scene as soon as LLM returns;
                # only the single-call path needs a bulk import here.
                scene_markdown_started_perf = time.perf_counter()
                per_scene_parallel = isinstance(result, dict) and bool(result.get("per_scene_parallel"))
                try:
                    import_started_perf = time.perf_counter()
                    if per_scene_parallel:
                        per_scene_outputs = (result or {}).get("per_scene_outputs") or []
                        logger.info(
                            "[场景编排2.2] Step 4 skipped bulk import; per-scene imports completed during orchestration | project_id=%s | episode_id=%s | scene_count=%s",
                            node_project_id,
                            node_episode_id,
                            len(per_scene_outputs),
                        )
                        import_result = {
                            "scene_count": len(per_scene_outputs),
                            "scene_ids": [
                                str(item.get("scene_id") or "").strip()
                                for item in per_scene_outputs
                                if str(item.get("scene_id") or "").strip()
                            ],
                            "parse_source": "per_scene_parallel",
                        }
                    else:
                        logger.info(
                            "[场景编排2.2] Step 4 开始导入场景单元 | project_id=%s | episode_id=%s",
                            node_project_id,
                            node_episode_id,
                        )
                        import_result = import_analyze_scene_stage_result(
                            db=db,
                            stage_key=STAGE_SCENE_MARKDOWN,
                            project_id=node_project_id,
                            episode_id=node_episode_id,
                            analyze_result=result,
                            script_id=f"episode:{node_episode_id}",
                        ) or {}
                    import_elapsed_ms = int((time.perf_counter() - import_started_perf) * 1000)
                    logger.info(
                        "[场景编排2.2] Step 4 场景单元导入完成 | project_id=%s | episode_id=%s | scene_count=%s | scene_ids=%s | parse_source=%s | import_elapsed_ms=%s",
                        node_project_id,
                        node_episode_id,
                        int(import_result.get("scene_count") or 0),
                        import_result.get("scene_ids") or [],
                        import_result.get("parse_source") or "unknown",
                        import_elapsed_ms,
                    )
                    upsert_pipeline_node_status(
                        db,
                        project_id=node_project_id,
                        episode_id=node_episode_id,
                        script_id=f"episode:{node_episode_id}",
                        node_name=node_key,
                        status="success",
                        progress_percent=100.0,
                    )
                    upsert_pipeline_node_status(
                        db,
                        project_id=node_project_id,
                        episode_id=node_episode_id,
                        script_id=f"episode:{node_episode_id}",
                        node_name="scene_planning",
                        status="success",
                        progress_percent=100.0,
                    )
                except HTTPException as import_http_exc:
                    import_detail = str(getattr(import_http_exc, "detail", "") or "")
                    if import_detail == "SCENE_MARKDOWN_EMPTY":
                        logger.warning(
                            "[场景编排2.2] scene_markdown 节点返回空文本，跳过 scene_units 同步 | project_id=%s | episode_id=%s",
                            node_project_id,
                            node_episode_id,
                        )
                        upsert_pipeline_node_status(
                            db,
                            project_id=node_project_id,
                            episode_id=node_episode_id,
                            script_id=f"episode:{node_episode_id}",
                            node_name=node_key,
                            status="failed",
                            error_code="SCENE_MARKDOWN_EMPTY",
                            error_message="scene_markdown node returned empty text",
                        )
                        db.commit()
                        raise
                    raise
                except Exception as parse_exc:
                    logger.exception(
                        "[场景编排2.2] 场景解析/同步失败 | project_id=%s | episode_id=%s | error=%s",
                        node_project_id,
                        node_episode_id,
                        parse_exc,
                    )
                    parse_error_code = str(getattr(parse_exc, "code", "") or "SCENE_PARSE_ERROR")
                    upsert_pipeline_node_status(
                        db,
                        project_id=node_project_id,
                        episode_id=node_episode_id,
                        script_id=f"episode:{node_episode_id}",
                        node_name=node_key,
                        status="failed",
                        error_code=parse_error_code,
                        error_message=str(parse_exc),
                    )
                    upsert_pipeline_node_status(
                        db,
                        project_id=node_project_id,
                        episode_id=node_episode_id,
                        script_id=f"episode:{node_episode_id}",
                        node_name="scene_planning",
                        status="failed",
                        error_code=parse_error_code,
                        error_message=str(parse_exc),
                    )
                    db.commit()
                    raise HTTPException(status_code=422, detail=parse_error_code) from parse_exc
                scene_markdown_elapsed_ms = int((time.perf_counter() - scene_markdown_started_perf) * 1000)
                logger.info(
                    "[场景编排2.2] 节点后处理完成 | project_id=%s | episode_id=%s | post_elapsed_ms=%s",
                    node_project_id,
                    node_episode_id,
                    scene_markdown_elapsed_ms,
                )
            db.commit()
            logger.info(
                "[剧本分析流程] 节点状态已提交 | node_key=%s | project_id=%s | episode_id=%s",
                node_key,
                node_project_id,
                node_episode_id,
            )
        flow_elapsed_ms = int((time.perf_counter() - flow_started_perf) * 1000)
        logger.info("[剧本分析流程] 节点完成返回 | node_key=%s | total_elapsed_ms=%s", node_key, flow_elapsed_ms)
        
        return {
            "status": "completed",
            "node_key": node_key,
            "executor": node.get("executor") or "analyze_scene",
            "prompt_file": node.get("prompt_file"),
            "injection_chain": node.get("injection_chain") or [],
            "result": result,
        }

    if node_key == "storyboard_generation":
        episode_id = int(getattr(request, "episode_id", None) or 0)
        if episode_id <= 0:
            raise HTTPException(status_code=400, detail="episode_id is required for storyboard_generation")

        episode = (
            db.query(Episode)
            .filter(Episode.id == episode_id, _active_episode_clause())
            .first()
        )
        if not episode:
            raise HTTPException(status_code=404, detail="Episode not found or has been deleted")
        _require_project_access(db, episode.project_id, current_user)

        if request.project_id and int(request.project_id) != int(episode.project_id):
            logger.warning(f"[剧本分析流程] 校验失败: 节点 {node_key} 请求的 project_id 不匹配")
            raise HTTPException(status_code=400, detail="project_id does not match episode.project_id")

        logger.info(f"[剧本分析流程] 准备委托批量任务执行分镜节点 {node_key} | 目标集: {episode_id} | 指定场景: {request.scene_ids}")
        status_payload = _start_scene_ai_shots_batch_for_episode(
            db=db,
            episode=episode,
            current_user=current_user,
            scene_ids=request.scene_ids or [],
            function_name=request.function_name,
            system_api_id=request.system_api_id,
        )
        return {
            "status": "started",
            "node_key": node_key,
            "executor": node.get("executor") or "shot_generation.batch_per_scene",
            "prompt_file": node.get("prompt_file"),
            "injection_chain": node.get("injection_chain") or [],
            "batch_status": status_payload,
        }

    logger.warning(f"[剧本分析流程] 未知或未绑定的节点: {node_key}。将返回未迁移状态。")
    return {
        "status": "planned_not_migrated",
        "node_key": node_key,
        "node": node,
        "message": "This node is registered and configurable, but no executor has been bound yet.",
    }
