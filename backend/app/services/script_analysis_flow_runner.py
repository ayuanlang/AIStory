# -*- coding: utf-8 -*-
"""Execute a single script-analysis flow node (sync path)."""
from __future__ import annotations

import logging
import time
from typing import Any, Dict

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.settings import get_script_analysis_flow_config
from app.models.all_models import Episode, User
from app.schemas.agent import AnalyzeSceneRequest
from app.services.endpoint_misc import _build_scene_analysis_blocking_failure_detail
from app.services.project_access import _require_project_access
from app.services.scene_ai_shots_batch import _start_scene_ai_shots_batch_for_episode
from app.services.soft_delete import _active_episode_clause
from app.services.scene_markdown_orchestration import (
    _extract_analysis_text_from_result,
)
from app.services.scene_markdown_runner import _run_scene_markdown_node_per_scene
from app.services.script_analysis_flow import (
    STAGE_SCENE_MARKDOWN,
    get_script_analysis_flow_registry,
    import_analyze_scene_stage_result,
    upsert_pipeline_node_status,
)
from app.services.script_analysis_llm_config import (
    _resolve_script_analysis_dropdown_order,
    _select_script_analysis_api_order,
)
from app.services.subject_index_resolve import (
    _script_optimization_has_project_visual_backfill,
    _subject_index_has_cover_poster,
    _subject_index_has_usable_content,
    resolve_usable_episode_subject_index,
)

logger = logging.getLogger("api_logger")


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
        "assets_extraction",
        "scene_markdown",
        "asset_design_character",
        "asset_design_prop",
        "asset_design_environment",
    }
    if node_key in analyze_node_keys:
        raw_payload = dict(request.analyze_payload or {})
        if not raw_payload.get("text"):
            raise HTTPException(status_code=400, detail="analyze_payload.text is required for this workflow node")
        raw_payload["prompt_file"] = raw_payload.get("prompt_file") or node.get("prompt_file")
        raw_payload["function_name"] = raw_payload.get("function_name") or request.function_name or "script_analysis"
        raw_payload["system_api_id"] = raw_payload.get("system_api_id") or request.system_api_id
        
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
            # Scene orchestration / asset design must not start without a usable Subject Index.
            if node_key in {
                "scene_markdown",
                "asset_design_character",
                "asset_design_prop",
                "asset_design_environment",
            }:
                gate_subject_index = resolve_usable_episode_subject_index(
                    episode,
                    request_text=raw_payload.get("text"),
                    explicit_subject_index=raw_payload.get("subject_index_text"),
                    heal_episode_field=True,
                    db=db,
                )
                if not _subject_index_has_usable_content(gate_subject_index):
                    logger.error(
                        "[剧本分析流程] subject_index_required_blocking node=%s episode_id=%s "
                        "episode_si_chars=%s stage_outputs_chars=%s explicit_si_chars=%s text_chars=%s",
                        node_key,
                        getattr(episode, "id", None),
                        len(str(getattr(episode, "ai_scene_analysis_subject_index", "") or "")),
                        len(str(getattr(episode, "ai_stage_outputs", "") or "")),
                        len(str(raw_payload.get("subject_index_text") or "")),
                        len(str(raw_payload.get("text") or "")),
                    )
                    raise HTTPException(
                        status_code=400,
                        detail=_build_scene_analysis_blocking_failure_detail(
                            ["ANALYSIS_SUBJECT_INDEX_REQUIRED"],
                            [],
                            [
                                "缺少资产清单（Subject Index），无法继续场景编排或资产生成。请先完成第二阶段资产提取后再重试。"
                            ],
                        ),
                    )
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
            )
            db.commit()

        llm_started_perf = time.perf_counter()
        logger.info("[剧本分析流程] 开始调用 evaluate_scene 执行节点 %s...", node_key)
        try:
            if node_key == "assets_extraction":
                # Pass Stage 1 optimized script as-is (no ENV/Beat slim cut).
                max_attempts = 2
                result = None
                assets_cover_poster_missing_after_retries = False
                for attempt in range(1, max_attempts + 1):
                    result = await analyze_scene(AnalyzeSceneRequest(**raw_payload), current_user=current_user, db=db, async_mode="0")
                    result_text = _extract_analysis_text_from_result(result)
                    has_cover_poster = _subject_index_has_cover_poster(result_text)
                    if has_cover_poster:
                        if attempt > 1:
                            logger.info(
                                "[剧本分析流程] 节点 %s 在重试后通过 cover_poster 校验 | attempt=%s",
                                node_key,
                                attempt,
                            )
                        break
                    logger.warning(
                        "[剧本分析流程] 节点 %s 缺少 cover_poster/poster 条目 | attempt=%s/%s",
                        node_key,
                        attempt,
                        max_attempts,
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
                        error_code="ASSETS_EXTRACTION_COVER_POSTER_MISSING",
                        error_message="cover_poster/poster missing, auto-retrying once",
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
            elif node_key == "script_optimization":
                # Visual backfill JSON is a completeness gate, not a standalone artifact.
                # Incomplete output => full Stage 1 rerun (same API x2, then one switched API).
                original_api_id = _coerce_system_api_id(raw_payload.get("system_api_id"))
                fallback_api_id = 0
                try:
                    fallback_api_id = _next_script_analysis_fallback_api_id(
                        db,
                        raw_payload.get("function_name") or "script_analysis",
                        original_api_id or raw_payload.get("system_api_id"),
                    )
                except Exception as fallback_exc:
                    logger.warning(
                        "[剧本分析流程] 节点 %s 无法解析备用 API | err=%s",
                        node_key,
                        fallback_exc,
                    )
                api_attempts = [original_api_id, original_api_id]
                if fallback_api_id > 0 and fallback_api_id != original_api_id:
                    api_attempts.append(fallback_api_id)
                else:
                    api_attempts.append(original_api_id)
                    logger.warning(
                        "[剧本分析流程] 节点 %s 无可用备用 API，第三次仍使用当前 API | system_api_id=%s",
                        node_key,
                        original_api_id or None,
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
                        error_code="SCRIPT_OPTIMIZATION_PROJECT_VISUAL_BACKFILL_MISSING",
                        error_message=(
                            "incomplete Stage 1 output, switching API and rerunning"
                            if (attempt + 1) == max_attempts and fallback_api_id > 0 and fallback_api_id != original_api_id
                            else "incomplete Stage 1 output, auto-retrying full script_optimization"
                        ),
                    )
                    db.commit()
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
                error_text = str(exc or "")
                if isinstance(exc, HTTPException):
                    error_text = str(getattr(exc, "detail", "") or error_text)
                error_code = (
                    "ASSETS_EXTRACTION_COVER_POSTER_MISSING"
                    if "ASSETS_EXTRACTION_COVER_POSTER_MISSING" in error_text
                    else (
                        "SCRIPT_OPTIMIZATION_PROJECT_VISUAL_BACKFILL_MISSING"
                        if "SCRIPT_OPTIMIZATION_PROJECT_VISUAL_BACKFILL_MISSING" in error_text
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
                    error_message=str(exc),
                )
                db.commit()
            raise
        llm_elapsed_ms = int((time.perf_counter() - llm_started_perf) * 1000)
        logger.info("[剧本分析流程] 节点 %s 执行完成 | llm_elapsed_ms=%s", node_key, llm_elapsed_ms)

        if node_project_id > 0 and node_episode_id > 0:
            if node_key != "scene_markdown":
                upsert_pipeline_node_status(
                    db,
                    project_id=node_project_id,
                    episode_id=node_episode_id,
                    script_id=f"episode:{node_episode_id}",
                    node_name=node_key,
                    status="success",
                    progress_percent=100.0,
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
                    raise HTTPException(status_code=422, detail=parse_error_code)
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
