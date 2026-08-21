# -*- coding: utf-8 -*-
"""Stage 2.2 per-scene markdown orchestration runner."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.all_models import Episode, User
from app.services.db_session_utils import _release_db_connection
from app.services.soft_delete import _active_episode_clause
from app.schemas.user_auth import (
    USER_ACTIVE_LEVEL_DEFAULT,
    resolve_user_batch_parallel_limit as _resolve_user_batch_parallel_limit,
)
from app.services.scene_markdown_orchestration import (
    SCENE_MARKDOWN_ORCHESTRATION_BATCH_RETRY_ROUNDS,
    SCENE_MARKDOWN_ORCHESTRATION_MAX_ATTEMPTS,
    SCENE_MARKDOWN_ORCHESTRATION_RETRY_BASE_DELAY_SEC,
    _extract_analysis_text_from_result,
    _import_scene_markdown_stage_with_retry,
    _is_retryable_scene_orchestration_error,
    upsert_workspace_scene_from_orchestration_markdown,
    _replace_adapted_script_in_beats_user_input,
    _scene_orchestration_error_code,
)
from app.services.script_analysis_flow import (
    SceneBeatsTooShortError,
    SceneMarkerParseError,
    SceneMissingBeat1Error,
    coerce_target_scene_ids_for_orchestration,
    extract_scene_markdown_text_from_analyze_result,
    extract_environment_names_from_scene_text,
    extract_scene_name_value_from_scene_text,
    extract_scenes_table_markdown_block,
    filter_scene_units_by_target_ids,
    patch_episode_scene_markdown_by_scene,
    patch_single_scene_markdown_for_orchestration,
    resolve_scene_units_for_markdown_orchestration,
    sanitize_scene_markdown_llm_output,
    scene_text_has_beat,
    scene_first_beat_number,
    is_canonical_first_beat_number,
    sync_scene_units_from_markers,
    update_scene_unit_orchestration_status,
    upsert_pipeline_node_status,
    validate_single_scene_markdown_for_orchestration,
    wrap_scene_unit_as_script_block,
)

logger = logging.getLogger("api_logger")


def _extract_scene_markdown_text_from_result(result: Any) -> str:
    return extract_scene_markdown_text_from_analyze_result(result)


def _scene_orchestration_environment_name(unit: Any) -> str:
    return extract_environment_names_from_scene_text(getattr(unit, "scene_text", "") or "")


def _scene_orchestration_environment_instruction(environment_name: str) -> str:
    env_name = str(environment_name or "").strip()
    if env_name:
        return (
            f" Environment Name 列必须填写 `{env_name}`（本场已锁定主环境），"
            "禁止写 None。"
        )
    return (
        " Environment Name 列必须填写 Subject Index 中本场 environment 行的主环境名，"
        "禁止因 Beat 未写 ENV:[] 而填 None。"
    )


async def _run_scene_markdown_node_per_scene(
    *,
    raw_payload: Dict[str, Any],
    current_user: User,
    db: Session,
    node_project_id: int,
    node_episode_id: int,
) -> Any:
    from app.api.routers.prompts.analyze_scene import (  # noqa: WPS433
        AnalyzeSceneRequest,
        analyze_scene,
    )
    from app.services.analyze_scene_text_ops import _resolve_scene_beats_adapted_script_text

    user_text = str(raw_payload.get("text") or "")

    episode_adaptation_text = ""
    if node_episode_id > 0:
        episode_row = (
            db.query(Episode)
            .filter(Episode.id == int(node_episode_id), _active_episode_clause())
            .first()
        )
        if episode_row is not None:
            episode_adaptation_text = str(getattr(episode_row, "ai_scene_analysis_adaptation", "") or "").strip()

    adapted_script_text = _resolve_scene_beats_adapted_script_text(user_text, episode_adaptation_text)

    scene_units, scene_units_source = resolve_scene_units_for_markdown_orchestration(
        db,
        user_text=user_text,
        adapted_script_text=adapted_script_text,
        project_id=node_project_id,
        episode_id=node_episode_id,
        episode_adaptation_text=episode_adaptation_text,
    )

    if not scene_units:
        raise HTTPException(
            status_code=422,
            detail=f"SCENE_MARKDOWN_UNITS_UNAVAILABLE:{scene_units_source}",
        )

    target_scene_ids = coerce_target_scene_ids_for_orchestration(raw_payload, user_text)
    if target_scene_ids:
        episode_prefix = "EP01"
        if scene_units:
            episode_prefix = str(getattr(scene_units[0], "scene_id", "") or "EP01").split("_SC", 1)[0] or "EP01"
        filtered_units = filter_scene_units_by_target_ids(
            scene_units,
            target_scene_ids,
            episode_prefix=episode_prefix,
        )
        if not filtered_units:
            raise HTTPException(
                status_code=422,
                detail=f"SCENE_MARKDOWN_TARGET_SCENE_NOT_FOUND:{','.join(target_scene_ids)}",
            )
        logger.info(
            "[scene_markdown] target scene filter applied requested=%s matched=%s/%s source=%s project_id=%s episode_id=%s",
            target_scene_ids,
            [unit.scene_id for unit in filtered_units],
            len(scene_units),
            scene_units_source,
            node_project_id,
            node_episode_id,
        )
        scene_units = filtered_units

    if len(scene_units) == 1:
        unit = scene_units[0]
        try:
            single_scene_block = wrap_scene_unit_as_script_block(unit).replace("|", "／")
        except SceneMissingBeat1Error as missing_exc:
            logger.error(
                "[scene_markdown] missing Beat marker | scene_id=%s — skip orchestration (invalid scene)",
                missing_exc.scene_id,
            )
            raise HTTPException(status_code=422, detail=missing_exc.detail) from missing_exc
        except SceneBeatsTooShortError as beats_exc:
            logger.error(
                "[scene_markdown] beats too short | scene_id=%s chars=%s min=%s",
                beats_exc.scene_id,
                beats_exc.char_count,
                beats_exc.min_chars,
            )
            raise HTTPException(status_code=422, detail=beats_exc.detail) from beats_exc
        locked_environment_name = _scene_orchestration_environment_name(unit)
        single_scene_instruction = (
            f"【单场处理模式】本次仅处理 Scene ID `{unit.scene_id}`（第 1/1 场）。"
            "输入剧本正文含该场 `【场景名称】{短名}｜{日·内/外}` 场景头 + `[BEAT_START:…]`…`[BEAT_END:…]` Beat 块"
            "（不含 Scene 级【主环境】等其它说明块）；"
            "请将 `【场景名称】` 后的 `{短名}｜{日·内/外}` 原样落入 Scene Name 列，并对 Beat 做 Index 化落表，输出该场景对应的一行 Scenes Table，不要处理其他场景。"
            f"Scenes Table 的 Scene ID 列必须精确填写 `{unit.scene_id}`。"
            f"{_scene_orchestration_environment_instruction(locked_environment_name)}"
            "禁止输出思考过程、解释、规划说明或任何非表格内容；"
            "直接以 Markdown 表格输出（仅含表头、分隔行与本场一行数据；不要输出 Part 1: Scenes Table 标题）。"
        )
        single_payload = dict(raw_payload)
        single_payload["text"] = _replace_adapted_script_in_beats_user_input(
            f"{single_scene_instruction}\n\n{user_text}",
            single_scene_block,
        )
        return await analyze_scene(
            AnalyzeSceneRequest(**single_payload),
            current_user=current_user,
            db=db,
            async_mode="0",
        )

    script_id = f"episode:{node_episode_id}"
    total_scenes = len(scene_units)
    sync_source_text = adapted_script_text or episode_adaptation_text
    if not sync_source_text:
        raise HTTPException(
            status_code=422,
            detail="SCENE_MARKDOWN_ADAPTED_SCRIPT_MISSING",
        )
    if node_project_id > 0 and node_episode_id > 0:
        try:
            sync_scene_units_from_markers(
                db,
                project_id=node_project_id,
                episode_id=node_episode_id,
                script_text=sync_source_text,
                script_id=script_id,
            )
            upsert_pipeline_node_status(
                db,
                project_id=node_project_id,
                episode_id=node_episode_id,
                script_id=script_id,
                node_name="scene_markdown",
                status="running",
                progress_percent=5.0,
                error_message=f"synced {total_scenes} scene units before parallel orchestration (source={scene_units_source})",
            )
            for unit in scene_units:
                update_scene_unit_orchestration_status(
                    db,
                    project_id=node_project_id,
                    episode_id=node_episode_id,
                    scene_id=unit.scene_id,
                    import_status="queued",
                    parse_status="success",
                    parse_error_code=None,
                )
            db.commit()
        except SceneMarkerParseError as sync_exc:
            logger.warning(
                "[scene_markdown] scene unit sync before orchestration failed | project_id=%s episode_id=%s err=%s",
                node_project_id,
                node_episode_id,
                sync_exc,
            )

    max_concurrency = _resolve_user_batch_parallel_limit(
        getattr(current_user, "is_active", USER_ACTIVE_LEVEL_DEFAULT),
    )
    logger.info(
        "[scene_markdown] parallel orchestration start scenes=%s concurrency=%s source=%s project_id=%s episode_id=%s",
        total_scenes,
        max_concurrency,
        scene_units_source,
        node_project_id,
        node_episode_id,
    )

    progress_lock = asyncio.Lock()
    completed_count = 0
    retried_scene_ids: Set[str] = set()

    async def _mark_scene_orchestration_status(
        task_db: Session,
        *,
        scene_id: str,
        import_status: str,
        parse_status: str,
        scene_markdown: Optional[str] = None,
        parse_error_code: Optional[str] = None,
    ) -> None:
        if node_project_id <= 0 or node_episode_id <= 0:
            return
        update_scene_unit_orchestration_status(
            task_db,
            project_id=node_project_id,
            episode_id=node_episode_id,
            scene_id=scene_id,
            import_status=import_status,
            parse_status=parse_status,
            scene_markdown=scene_markdown,
            parse_error_code=parse_error_code,
        )
        task_db.commit()

    async def _run_one_scene(
        index: int,
        unit: Any,
        *,
        local_semaphore: asyncio.Semaphore,
        max_attempts: int = SCENE_MARKDOWN_ORCHESTRATION_MAX_ATTEMPTS,
    ) -> Tuple[int, str, str, Any, int]:
        nonlocal completed_count
        last_exc: Optional[Exception] = None
        attempts_used = 0

        async with local_semaphore:
            task_db = SessionLocal()
            try:
                for attempt in range(1, max_attempts + 1):
                    attempts_used = attempt
                    try:
                        if node_project_id > 0 and node_episode_id > 0:
                            await _mark_scene_orchestration_status(
                                task_db,
                                scene_id=unit.scene_id,
                                import_status="llm_running",
                                parse_status="success",
                                parse_error_code=None,
                            )
                        logger.info(
                            "[场景编排] LLM 提交 | scene_id=%s scene_order=%s/%s project_id=%s episode_id=%s attempt=%s/%s",
                            unit.scene_id,
                            index,
                            total_scenes,
                            node_project_id,
                            node_episode_id,
                            attempt,
                            max_attempts,
                        )

                        try:
                            single_scene_block = wrap_scene_unit_as_script_block(unit).replace("|", "／")
                        except SceneMissingBeat1Error as missing_exc:
                            logger.error(
                                "[scene_markdown] missing Beat marker | scene_id=%s — skip orchestration (invalid scene)",
                                missing_exc.scene_id,
                            )
                            raise HTTPException(status_code=422, detail=missing_exc.detail) from missing_exc
                        except SceneBeatsTooShortError as beats_exc:
                            logger.error(
                                "[scene_markdown] beats too short | scene_id=%s chars=%s min=%s",
                                beats_exc.scene_id,
                                beats_exc.char_count,
                                beats_exc.min_chars,
                            )
                            raise HTTPException(status_code=422, detail=beats_exc.detail) from beats_exc
                        locked_environment_name = _scene_orchestration_environment_name(unit)
                        single_scene_instruction = (
                            f"【单场处理模式】本次仅处理 Scene ID `{unit.scene_id}`（第 {index}/{total_scenes} 场）。"
                            "输入剧本正文含该场 `【场景名称】{短名}｜{日·内/外}` 场景头 + `[BEAT_START:…]`…`[BEAT_END:…]` Beat 块"
                            "（不含 Scene 级【主环境】等其它说明块）；"
                            "请将 `【场景名称】` 后的 `{短名}｜{日·内/外}` 原样落入 Scene Name 列，并对 Beat 做 Index 化落表，输出该场景对应的一行 Scenes Table，不要处理其他场景。"
                            f"Scenes Table 的 Scene ID 列必须精确填写 `{unit.scene_id}`，"
                            "不得仅填场次序号或其他别名。"
                            f"{_scene_orchestration_environment_instruction(locked_environment_name)}"
                            "禁止输出思考过程、解释、规划说明或任何非表格内容；"
                            "直接以 Markdown 表格输出（仅含表头、分隔行与本场一行数据；不要输出 Part 1: Scenes Table 标题）。"
                        )
                        scene_payload = dict(raw_payload)
                        scene_payload["skip_episode_persist"] = True
                        scene_payload["text"] = _replace_adapted_script_in_beats_user_input(
                            f"{single_scene_instruction}\n\n{user_text}",
                            single_scene_block,
                        )
                        result = await analyze_scene(
                            AnalyzeSceneRequest(**scene_payload),
                            current_user=current_user,
                            db=task_db,
                            async_mode="0",
                        )
                        scene_text = _extract_scene_markdown_text_from_result(result).strip()
                        if not scene_text:
                            scene_text = _extract_analysis_text_from_result(result).strip()
                        if not scene_text:
                            raise HTTPException(status_code=422, detail="SCENE_MARKDOWN_EMPTY")
                        raw_scene_text = scene_text
                        scene_text = extract_scenes_table_markdown_block(scene_text) or sanitize_scene_markdown_llm_output(scene_text) or scene_text
                        scene_text = patch_single_scene_markdown_for_orchestration(
                            scene_text,
                            unit.scene_id,
                            scene_order=index,
                            scene_name=extract_scene_name_value_from_scene_text(
                                getattr(unit, "scene_text", "") or ""
                            ),
                            environment_name=locked_environment_name,
                        )
                        if scene_text != raw_scene_text:
                            logger.info(
                                "[scene_markdown] patched scene table identity | scene_id=%s scene_order=%s/%s",
                                unit.scene_id,
                                index,
                                total_scenes,
                            )
                        validation_error = validate_single_scene_markdown_for_orchestration(
                            scene_text,
                            unit.scene_id,
                            scene_order=index,
                        )
                        if validation_error:
                            logger.warning(
                                "[scene_markdown] validation failed | scene_id=%s scene_order=%s error=%s output_chars=%s output_preview=%s",
                                unit.scene_id,
                                index,
                                validation_error,
                                len(scene_text),
                                scene_text[:500],
                            )
                            raise HTTPException(
                                status_code=422,
                                detail=validation_error,
                            )

                        if node_project_id > 0 and node_episode_id > 0:
                            await _mark_scene_orchestration_status(
                                task_db,
                                scene_id=unit.scene_id,
                                import_status="llm_returned",
                                parse_status="success",
                                scene_markdown=scene_text,
                                parse_error_code=None,
                            )
                        logger.info(
                            "[场景编排] LLM 返回 | scene_id=%s scene_order=%s/%s output_chars=%s project_id=%s episode_id=%s",
                            unit.scene_id,
                            index,
                            total_scenes,
                            len(scene_text),
                            node_project_id,
                            node_episode_id,
                        )

                        if node_episode_id > 0:
                            episode_row = (
                                task_db.query(Episode)
                                .filter(Episode.id == int(node_episode_id), _active_episode_clause())
                                .first()
                            )
                            if episode_row is not None:
                                patch_episode_scene_markdown_by_scene(
                                    task_db,
                                    episode=episode_row,
                                    scene_id=unit.scene_id,
                                    markdown=scene_text,
                                    scene_order=index,
                                )

                        if node_project_id > 0 and node_episode_id > 0:
                            await _mark_scene_orchestration_status(
                                task_db,
                                scene_id=unit.scene_id,
                                import_status="importing",
                                parse_status="success",
                                scene_markdown=scene_text,
                                parse_error_code=None,
                            )
                            workspace_import = {"ok": False, "reason": "not_attempted"}
                            try:
                                workspace_import = upsert_workspace_scene_from_orchestration_markdown(
                                    task_db,
                                    episode_id=node_episode_id,
                                    markdown=scene_text,
                                    target_scene_id=unit.scene_id,
                                    scene_order=index,
                                )
                                task_db.commit()
                                logger.info(
                                    "[场景编排] 工作区已入库 | scene_id=%s scene_order=%s/%s scene_no=%s created=%s updated=%s",
                                    unit.scene_id,
                                    index,
                                    total_scenes,
                                    workspace_import.get("scene_no"),
                                    workspace_import.get("created"),
                                    workspace_import.get("updated"),
                                )
                            except Exception as workspace_exc:
                                task_db.rollback()
                                workspace_import = {
                                    "ok": False,
                                    "reason": str(getattr(workspace_exc, "detail", "") or workspace_exc),
                                }
                                logger.warning(
                                    "[scene_markdown] workspace scene persist failed | scene_id=%s scene_order=%s/%s error=%s",
                                    unit.scene_id,
                                    index,
                                    total_scenes,
                                    workspace_import["reason"],
                                    exc_info=workspace_exc,
                                )
                            logger.info(
                                "[场景编排] 同步进度表 | scene_id=%s scene_order=%s/%s project_id=%s episode_id=%s",
                                unit.scene_id,
                                index,
                                total_scenes,
                                node_project_id,
                                node_episode_id,
                            )
                            try:
                                _import_scene_markdown_stage_with_retry(
                                    task_db,
                                    project_id=node_project_id,
                                    episode_id=node_episode_id,
                                    script_text=scene_text,
                                    script_id=script_id,
                                    target_scene_id=unit.scene_id,
                                )
                                await _mark_scene_orchestration_status(
                                    task_db,
                                    scene_id=unit.scene_id,
                                    import_status=(
                                        "imported"
                                        if workspace_import.get("ok")
                                        else "awaiting_workspace_import"
                                    ),
                                    parse_status="success",
                                    scene_markdown=scene_text,
                                    parse_error_code=None,
                                )
                                logger.info(
                                    "[场景编排] %s | scene_id=%s scene_order=%s/%s project_id=%s episode_id=%s",
                                    "已入库" if workspace_import.get("ok") else "进度表已同步，等待工作区入库",
                                    unit.scene_id,
                                    index,
                                    total_scenes,
                                    node_project_id,
                                    node_episode_id,
                                )
                            except Exception as import_exc:
                                task_db.rollback()
                                logger.warning(
                                    "[scene_markdown] progress import failed after successful LLM | scene_id=%s scene_order=%s/%s project_id=%s episode_id=%s error=%s",
                                    unit.scene_id,
                                    index,
                                    total_scenes,
                                    node_project_id,
                                    node_episode_id,
                                    str(getattr(import_exc, "detail", "") or import_exc),
                                    exc_info=import_exc,
                                )
                                await _mark_scene_orchestration_status(
                                    task_db,
                                    scene_id=unit.scene_id,
                                    import_status=(
                                        "imported"
                                        if workspace_import.get("ok")
                                        else "awaiting_workspace_import"
                                    ),
                                    parse_status="success",
                                    scene_markdown=scene_text,
                                    parse_error_code=None,
                                )

                        if attempt > 1:
                            retried_scene_ids.add(str(unit.scene_id))
                            logger.info(
                                "[scene_markdown] scene orchestration recovered on retry | scene_id=%s attempt=%s/%s project_id=%s episode_id=%s",
                                unit.scene_id,
                                attempt,
                                max_attempts,
                                node_project_id,
                                node_episode_id,
                            )

                        async with progress_lock:
                            completed_count += 1
                            if node_project_id > 0 and node_episode_id > 0:
                                progress = 5.0 + (85.0 * completed_count / max(total_scenes, 1))
                                upsert_pipeline_node_status(
                                    task_db,
                                    project_id=node_project_id,
                                    episode_id=node_episode_id,
                                    script_id=script_id,
                                    node_name="scene_markdown",
                                    status="running",
                                    progress_percent=progress,
                                    error_message=f"completed {completed_count}/{total_scenes}: {unit.scene_id}",
                                )
                                task_db.commit()

                        return index, unit.scene_id, scene_text, result, attempts_used
                    except Exception as scene_exc:
                        last_exc = scene_exc
                        retryable = _is_retryable_scene_orchestration_error(scene_exc)
                        if attempt >= max_attempts or not retryable:
                            error_code = _scene_orchestration_error_code(scene_exc, unit.scene_id)
                            logger.error(
                                "[scene_markdown] scene orchestration failed | scene_id=%s scene_order=%s/%s project_id=%s episode_id=%s attempt=%s/%s error=%s",
                                unit.scene_id,
                                index,
                                total_scenes,
                                node_project_id,
                                node_episode_id,
                                attempt,
                                max_attempts,
                                error_code,
                                exc_info=scene_exc,
                            )
                            try:
                                await _mark_scene_orchestration_status(
                                    task_db,
                                    scene_id=unit.scene_id,
                                    import_status="failed",
                                    parse_status="failed",
                                    parse_error_code=error_code,
                                )
                            except Exception:
                                task_db.rollback()
                            raise

                        retried_scene_ids.add(str(unit.scene_id))
                        logger.warning(
                            "[scene_markdown] scene orchestration attempt failed, retrying | scene_id=%s attempt=%s/%s project_id=%s episode_id=%s error=%s",
                            unit.scene_id,
                            attempt,
                            max_attempts,
                            node_project_id,
                            node_episode_id,
                            _scene_orchestration_error_code(scene_exc, unit.scene_id),
                            exc_info=scene_exc,
                        )
                        try:
                            await _mark_scene_orchestration_status(
                                task_db,
                                scene_id=unit.scene_id,
                                import_status="queued",
                                parse_status="success",
                                parse_error_code=_scene_orchestration_error_code(scene_exc, unit.scene_id),
                            )
                        except Exception:
                            task_db.rollback()
                        # Do not hold a pool connection across retry backoff.
                        _release_db_connection(task_db, "scene_markdown_retry_sleep")
                        await asyncio.sleep(SCENE_MARKDOWN_ORCHESTRATION_RETRY_BASE_DELAY_SEC * attempt)

                if last_exc is not None:
                    raise last_exc
                raise HTTPException(
                    status_code=500,
                    detail=f"SCENE_MARKDOWN_ORCHESTRATION_FAILED:{unit.scene_id}",
                )
            finally:
                task_db.close()

    async def _run_scene_batch(
        indexed_units: List[Tuple[int, Any]],
        *,
        batch_concurrency: int,
        max_attempts: int = SCENE_MARKDOWN_ORCHESTRATION_MAX_ATTEMPTS,
    ) -> List[Any]:
        batch_semaphore = asyncio.Semaphore(max(1, batch_concurrency))
        return await asyncio.gather(
            *[
                _run_one_scene(index, unit, local_semaphore=batch_semaphore, max_attempts=max_attempts)
                for index, unit in indexed_units
            ],
            return_exceptions=True,
        )

    indexed_scene_units = list(enumerate(scene_units, start=1))
    success_by_index: Dict[int, Tuple[int, str, str, Any, int]] = {}
    scene_failure_codes: Dict[str, str] = {}
    pending_units: List[Tuple[int, Any]] = []

    # Preflight: no Beat marker at all → skip LLM, mark scene invalid (do not batch-retry).
    # Cross-scene continued numbering (Beat 11 in SC03) is valid and must still run.
    for index, unit in indexed_scene_units:
        scene_source = (
            str(getattr(unit, "scene_text", "") or "").strip()
            or str(getattr(unit, "scene_markdown", "") or "").strip()
        )
        if scene_text_has_beat(scene_source):
            first_beat = scene_first_beat_number(scene_source)
            if first_beat and not is_canonical_first_beat_number(first_beat):
                logger.warning(
                    "[scene_markdown] cross-scene beat numbering | scene_id=%s first_beat=%s — continue orchestration",
                    unit.scene_id,
                    first_beat,
                )
            pending_units.append((index, unit))
            continue
        failure_code = f"SCENE_MARKDOWN_MISSING_BEAT_1:{unit.scene_id}"
        scene_failure_codes[str(unit.scene_id)] = failure_code
        logger.error(
            "[scene_markdown] missing Beat marker | scene_id=%s scene_order=%s/%s — skip orchestration (invalid scene)",
            unit.scene_id,
            index,
            total_scenes,
        )
        if node_project_id > 0 and node_episode_id > 0:
            try:
                update_scene_unit_orchestration_status(
                    db,
                    project_id=node_project_id,
                    episode_id=node_episode_id,
                    scene_id=unit.scene_id,
                    import_status="failed",
                    parse_status="failed",
                    parse_error_code=failure_code,
                )
                db.commit()
            except Exception:
                db.rollback()

    if not pending_units:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "SCENE_MARKDOWN_MISSING_BEAT_1",
                "failed_count": len(indexed_scene_units),
                "total_count": total_scenes,
                "failed_scenes": [
                    {
                        "scene_id": str(unit.scene_id),
                        "scene_order": int(index),
                        "error_code": "SCENE_MARKDOWN_MISSING_BEAT_1",
                    }
                    for index, unit in indexed_scene_units
                ],
                "succeeded_count": 0,
            },
        )

    for batch_round in range(SCENE_MARKDOWN_ORCHESTRATION_BATCH_RETRY_ROUNDS + 1):
        if not pending_units:
            break
        batch_concurrency = max_concurrency if batch_round == 0 else 1
        if batch_round > 0:
            # Do not re-queue Stage 1 quality failures (missing Beat marker / beats too short).
            pending_units = [
                (index, unit)
                for index, unit in pending_units
                if not str(scene_failure_codes.get(str(unit.scene_id)) or "").startswith(
                    ("SCENE_MARKDOWN_MISSING_BEAT_1", "SCENE_MARKDOWN_BEATS_TOO_SHORT")
                )
            ]
            if not pending_units:
                break
            logger.warning(
                "[scene_markdown] batch retry round %s for %s failed scenes | project_id=%s episode_id=%s scene_ids=%s",
                batch_round,
                len(pending_units),
                node_project_id,
                node_episode_id,
                [unit.scene_id for _, unit in pending_units],
            )
        # Outer request session must not stay checked out across parallel per-scene LLM work.
        _release_db_connection(db, "scene_markdown_parallel_batch")
        round_outcomes = await _run_scene_batch(
            pending_units,
            batch_concurrency=batch_concurrency,
            max_attempts=SCENE_MARKDOWN_ORCHESTRATION_MAX_ATTEMPTS,
        )
        next_pending: List[Tuple[int, Any]] = []
        for (index, unit), outcome in zip(pending_units, round_outcomes):
            if isinstance(outcome, Exception):
                failure_code = _scene_orchestration_error_code(outcome, unit.scene_id)
                scene_failure_codes[str(unit.scene_id)] = failure_code
                logger.error(
                    "[scene_markdown] scene orchestration failed | scene_id=%s scene_order=%s project_id=%s episode_id=%s error=%s",
                    unit.scene_id,
                    index,
                    node_project_id,
                    node_episode_id,
                    str(getattr(outcome, "detail", "") or outcome),
                )
                if _is_retryable_scene_orchestration_error(outcome):
                    next_pending.append((index, unit))
                continue
            success_by_index[int(outcome[0])] = outcome
        pending_units = next_pending

    failed_scene_reports: List[Dict[str, Any]] = []
    skipped_missing_beat1_reports: List[Dict[str, Any]] = []
    for index, unit in indexed_scene_units:
        if index in success_by_index:
            continue
        raw_failure_code = str(
            scene_failure_codes.get(str(unit.scene_id))
            or "SCENE_MARKDOWN_ORCHESTRATION_FAILED"
        ).strip()
        error_code = raw_failure_code.split(":", 1)[0] if raw_failure_code else "SCENE_MARKDOWN_ORCHESTRATION_FAILED"
        report = {
            "scene_id": str(unit.scene_id),
            "scene_order": int(index),
            "error_code": error_code,
        }
        # Missing Beat 1 = invalid scene skipped (not an LLM orchestration failure).
        if error_code == "SCENE_MARKDOWN_MISSING_BEAT_1" or raw_failure_code.startswith(
            "SCENE_MARKDOWN_MISSING_BEAT_1"
        ):
            skipped_missing_beat1_reports.append(report)
            continue
        failed_scene_reports.append(report)

    if failed_scene_reports:
        if node_project_id > 0 and node_episode_id > 0:
            upsert_pipeline_node_status(
                db,
                project_id=node_project_id,
                episode_id=node_episode_id,
                script_id=script_id,
                node_name="scene_markdown",
                status="failed",
                progress_percent=min(95.0, 5.0 + (85.0 * len(success_by_index) / max(total_scenes, 1))),
                error_code="SCENE_MARKDOWN_PARTIAL_FAILURE",
                error_message=(
                    f"failed {len(failed_scene_reports)}/{total_scenes}: "
                    + ", ".join(item["scene_id"] for item in failed_scene_reports)
                ),
            )
            db.commit()
        raise HTTPException(
            status_code=422,
            detail={
                "code": "SCENE_MARKDOWN_PARTIAL_FAILURE",
                "failed_count": len(failed_scene_reports),
                "total_count": total_scenes,
                "failed_scenes": failed_scene_reports,
                "succeeded_count": len(success_by_index),
                "skipped_missing_beat1_scenes": skipped_missing_beat1_reports,
                "skipped_missing_beat1_count": len(skipped_missing_beat1_reports),
            },
        )

    # Missing Beat-marker scenes are intentionally skipped (not hard failures). Merge only
    # orchestrated successes — never assume every indexed unit is in success_by_index.
    if not success_by_index:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "SCENE_MARKDOWN_MISSING_BEAT_1",
                "failed_count": len(skipped_missing_beat1_reports),
                "total_count": total_scenes,
                "failed_scenes": skipped_missing_beat1_reports,
                "succeeded_count": 0,
                "skipped_missing_beat1_scenes": skipped_missing_beat1_reports,
                "skipped_missing_beat1_count": len(skipped_missing_beat1_reports),
            },
        )

    per_scene_outputs: List[str] = []
    per_scene_results: List[Dict[str, Any]] = []
    last_result: Any = None
    for index in sorted(success_by_index):
        outcome = success_by_index[index]
        _index, scene_id, scene_text, result, attempts_used = outcome
        per_scene_outputs.append(scene_text)
        per_scene_results.append(
            {
                "scene_id": str(scene_id),
                "scene_order": int(_index),
                "markdown": scene_text,
                "attempts": int(attempts_used),
            }
        )
        last_result = result

    if not per_scene_results:
        raise HTTPException(status_code=422, detail="SCENE_MARKDOWN_NO_SCENE_OUTPUTS")

    # No episode-level multi-row merge: each scene keeps its own importable table
    # (already patched via patch_episode_scene_markdown_by_scene).
    presence_text = str(per_scene_outputs[-1] or "").strip()

    orchestration_meta = {
        "per_scene_retried_scene_ids": sorted(retried_scene_ids),
        "per_scene_retry_attempts_max": SCENE_MARKDOWN_ORCHESTRATION_MAX_ATTEMPTS,
        "per_scene_batch_retry_rounds": SCENE_MARKDOWN_ORCHESTRATION_BATCH_RETRY_ROUNDS,
        "skipped_missing_beat1_scenes": skipped_missing_beat1_reports,
        "skipped_missing_beat1_count": len(skipped_missing_beat1_reports),
    }

    if isinstance(last_result, dict):
        result_payload = dict(last_result)
        result_payload["result"] = presence_text
        result_payload["content"] = presence_text
        result_payload["scenes_markdown"] = presence_text
        result_payload["per_scene_count"] = total_scenes
        result_payload["per_scene_parallel"] = max_concurrency
        result_payload["per_scene_source"] = scene_units_source
        result_payload["per_scene_persist_mode"] = "by_scene_only"
        result_payload["per_scene_outputs"] = per_scene_results
        result_payload.update(orchestration_meta)
        return result_payload
    return {
        "result": presence_text,
        "content": presence_text,
        "scenes_markdown": presence_text,
        "per_scene_count": total_scenes,
        "per_scene_parallel": max_concurrency,
        "per_scene_source": scene_units_source,
        "per_scene_persist_mode": "by_scene_only",
        "per_scene_outputs": per_scene_results,
        **orchestration_meta,
    }


