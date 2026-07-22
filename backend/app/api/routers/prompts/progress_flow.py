# -*- coding: utf-8 -*-
"""Prompts/analyze section routes — symbols pulled from shared module."""
from __future__ import annotations

from app.api.routers.prompts import shared as _shared

router = _shared.router
globals().update(
    {
        k: v
        for k, v in vars(_shared).items()
        if k
        not in {
            "__name__",
            "__file__",
            "__package__",
            "__loader__",
            "__spec__",
            "__doc__",
            "__builtins__",
        }
    }
)

from app.services.scene_markdown_orchestration import (  # noqa: E402,F401
    SCENE_MARKDOWN_ORCHESTRATION_BATCH_RETRY_ROUNDS,
    SCENE_MARKDOWN_ORCHESTRATION_MAX_ATTEMPTS,
    SCENE_MARKDOWN_ORCHESTRATION_RETRY_BASE_DELAY_SEC,
)
from app.services.project_access import (  # noqa: E402,F401
    _require_project_access,
)


class ScriptAnalysisFlowRunNodeRequest(BaseModel):
    node_key: str
    project_id: Optional[int] = None
    episode_id: Optional[int] = None
    scene_ids: Optional[List[int]] = None
    analyze_payload: Optional[Dict[str, Any]] = None
    function_name: Optional[str] = None
    system_api_id: Optional[int] = None


class SceneUnitsSyncRequest(BaseModel):
    project_id: int
    episode_id: int
    script_text: str
    script_id: Optional[str] = None
    prefer_markers: Optional[bool] = False
    partial: Optional[bool] = False
    target_scene_id: Optional[str] = None


class SceneOrchestrationResetRequest(BaseModel):
    project_id: int
    episode_id: int
    scene_ids: Optional[List[str]] = None


class ProgressAutoOrchestrateRequest(BaseModel):
    project_id: int
    episode_id: int
    scene_ids: Optional[List[str]] = None
    function_name: Optional[str] = None
    system_api_id: Optional[int] = None
    asset_types: Optional[List[str]] = None


class ProgressIssueResolveRequest(BaseModel):
    issue_id: int


class ProgressReconcileRequest(BaseModel):
    project_id: int
    episode_id: int


def _extract_scene_markdown_text_from_result(result: Any) -> str:
    return extract_scene_markdown_text_from_analyze_result(result)


def _extract_analysis_text_from_result(result: Any) -> str:
    if isinstance(result, str):
        return result
    if not isinstance(result, dict):
        return ""
    for key in ("result", "content", "adapted_script", "scenes_markdown"):
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            return value
    data = result.get("data")
    if isinstance(data, dict):
        for key in ("result", "content", "adapted_script", "scenes_markdown"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return ""


def _replace_adapted_script_in_beats_user_input(user_text: str, adapted_script_text: str) -> str:
    source = str(user_text or "")
    adapted = str(adapted_script_text or "").strip()
    if not source.strip():
        return adapted
    wrapped_adapted = unwrap_injection_section(source, "优化后剧本")
    if wrapped_adapted is not None:
        return source.replace(
            wrap_injection_section("优化后剧本", wrapped_adapted),
            wrap_injection_section("优化后剧本", adapted),
            1,
        ).strip()
    marker_match = re.search(r"(\[优化后剧本[^\]]*\]\s*\n)([\s\S]*)$", source)
    if marker_match:
        return f"{source[:marker_match.start(2)]}{adapted}".strip()
    if SCENES_BLOCK_START_TOKEN in source:
        start_idx = source.find(SCENES_BLOCK_START_TOKEN)
        return f"{source[:start_idx].rstrip()}\n\n{adapted}".strip()
    return f"{source.rstrip()}\n\n{adapted}".strip()


def _is_retryable_scene_orchestration_error(exc: Exception) -> bool:
    if isinstance(exc, (SceneBeatsTooShortError, SceneMissingBeat1Error)):
        return False
    if isinstance(exc, (OperationalError, SQLAlchemyTimeoutError)):
        return True
    if isinstance(exc, HTTPException):
        status = int(getattr(exc, "status_code", 500) or 500)
        detail = str(getattr(exc, "detail", "") or "")
        # Stage 1 data quality errors; do not retry.
        if detail.startswith("SCENE_MARKDOWN_BEATS_TOO_SHORT"):
            return False
        if detail.startswith("SCENE_MARKDOWN_MISSING_BEAT_1"):
            return False
        if status in (408, 429, 500, 502, 503, 504):
            return True
        if detail.startswith(
            (
                "SCENE_MARKDOWN_EMPTY_FOR_SCENE:",
                "SCENE_MARKDOWN_SCENE_ID_MISMATCH:",
                "SCENE_MARKDOWN_EMPTY",
                "SCENE_MARKDOWN_NO_SCENE_ROW",
                "SCENE_MARKDOWN_PARSE_FAILED",
                "SCENE_MARKDOWN_ORCHESTRATION_FAILED",
            )
        ):
            return True
        if status == 422 and detail.startswith("SCENE_MARKDOWN_"):
            return True
        if "LLM_STREAM" in detail.upper() or "TIMEOUT" in detail.upper():
            return True
        return False
    msg = str(exc or "").lower()
    if "database is locked" in msg or "timeout" in msg or "rate limit" in msg:
        return True
    return False


def _scene_orchestration_error_code(exc: Exception, scene_id: str) -> str:
    if isinstance(exc, (SceneBeatsTooShortError, SceneMissingBeat1Error)):
        return exc.detail
    if isinstance(exc, HTTPException):
        detail = str(getattr(exc, "detail", "") or "")
        if detail.startswith("SCENE_MARKDOWN_SCENE_ID_MISMATCH"):
            return detail if "," in detail or detail.count(":") > 1 else detail
        if detail.startswith("SCENE_MARKDOWN_") or detail.startswith("SCENES_TABLE_"):
            return detail
    exc_type = type(exc).__name__
    msg = str(exc or "").strip().replace("\n", " ")[:240]
    if msg:
        return f"SCENE_MARKDOWN_ORCHESTRATION_FAILED:{scene_id}:{exc_type}:{msg}"
    return f"SCENE_MARKDOWN_ORCHESTRATION_FAILED:{scene_id}"


def _import_scene_markdown_stage_with_retry(
    db: Session,
    *,
    project_id: int,
    episode_id: int,
    script_text: str,
    script_id: Optional[str],
    target_scene_id: str,
    max_attempts: int = 3,
) -> None:
    last_exc: Optional[Exception] = None
    for attempt in range(1, max(1, int(max_attempts)) + 1):
        try:
            import_scene_markdown_stage(
                db=db,
                project_id=int(project_id),
                episode_id=int(episode_id),
                script_text=script_text,
                script_id=script_id,
                partial=True,
                target_scene_id=target_scene_id,
            )
            return
        except OperationalError as exc:
            last_exc = exc
            db.rollback()
            msg = str(exc or "").lower()
            if attempt >= max_attempts or "database is locked" not in msg:
                raise
            time.sleep(0.15 * attempt)
        except Exception:
            db.rollback()
            raise
    if last_exc is not None:
        raise last_exc


def _derive_scene_orchestration_phase(
    *,
    import_status: Any,
    parse_status: Any,
) -> str:
    import_key = str(import_status or "").strip().lower()
    parse_key = str(parse_status or "").strip().lower()
    if import_key in {"success"}:
        return "imported"
    if import_key in {"awaiting_workspace_import"}:
        return "llm_returned"
    if import_key in {"importing"}:
        return "importing"
    if import_key in {"llm_returned"}:
        return "llm_returned"
    if import_key in {"llm_running", "running"}:
        return "llm_submit"
    if import_key in {"failed"} or parse_key in {"failed"}:
        return "failed"
    if import_key in {"queued"}:
        return "queued"
    return import_key or "unknown"


async def _run_scene_markdown_node_per_scene(
    *,
    raw_payload: Dict[str, Any],
    current_user: User,
    db: Session,
    node_project_id: int,
    node_episode_id: int,
) -> Any:
    user_text = str(raw_payload.get("text") or "")
    adapted_script_text = extract_adapted_script_from_beats_user_input(user_text)

    episode_adaptation_text = ""
    if node_episode_id > 0:
        episode_row = db.query(Episode).filter(Episode.id == int(node_episode_id)).first()
        if episode_row is not None:
            episode_adaptation_text = str(getattr(episode_row, "ai_scene_analysis_adaptation", "") or "").strip()

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

    if len(scene_units) == 1:
        unit = scene_units[0]
        try:
            single_scene_block = wrap_scene_unit_as_script_block(unit)
        except SceneMissingBeat1Error as missing_exc:
            logger.error(
                "[scene_markdown] missing Beat 1 | scene_id=%s — skip orchestration (invalid scene)",
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
        single_scene_instruction = (
            f"【单场处理模式】本次仅处理 Scene ID `{unit.scene_id}`（第 1/1 场）。"
            "输入剧本正文含该场 `【场景名称】{短名}｜{日·内/外}` 场景头 + `[BEAT_START:…]`…`[BEAT_END:…]` Beat 块"
            "（不含 Scene 级【主环境】等其它说明块）；"
            "请将 `【场景名称】` 后的 `{短名}｜{日·内/外}` 原样落入 Scene Name 列，并对 Beat 做 Index 化落表，输出该场景对应的一行 Scenes Table，不要处理其他场景。"
            f"Scenes Table 的 Scene ID 列必须精确填写 `{unit.scene_id}`。"
            "禁止输出思考过程、解释、规划说明或任何非表格内容；"
            "直接以 Markdown 表格输出 Part 1: Scenes Table（仅含表头、分隔行与本场一行数据）。"
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
                            single_scene_block = wrap_scene_unit_as_script_block(unit)
                        except SceneMissingBeat1Error as missing_exc:
                            logger.error(
                                "[scene_markdown] missing Beat 1 | scene_id=%s — skip orchestration (invalid scene)",
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
                        single_scene_instruction = (
                            f"【单场处理模式】本次仅处理 Scene ID `{unit.scene_id}`（第 {index}/{total_scenes} 场）。"
                            "输入剧本正文含该场 `【场景名称】{短名}｜{日·内/外}` 场景头 + `[BEAT_START:…]`…`[BEAT_END:…]` Beat 块"
                            "（不含 Scene 级【主环境】等其它说明块）；"
                            "请将 `【场景名称】` 后的 `{短名}｜{日·内/外}` 原样落入 Scene Name 列，并对 Beat 做 Index 化落表，输出该场景对应的一行 Scenes Table，不要处理其他场景。"
                            f"Scenes Table 的 Scene ID 列必须精确填写 `{unit.scene_id}`，"
                            "不得仅填场次序号或其他别名。"
                            "禁止输出思考过程、解释、规划说明或任何非表格内容；"
                            "直接以 Markdown 表格输出 Part 1: Scenes Table（仅含表头、分隔行与本场一行数据）。"
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
                            episode_row = task_db.query(Episode).filter(Episode.id == int(node_episode_id)).first()
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
                                    import_status="success",
                                    parse_status="success",
                                    scene_markdown=scene_text,
                                    parse_error_code=None,
                                )
                                logger.info(
                                    "[场景编排] 进度表已同步 | scene_id=%s scene_order=%s/%s project_id=%s episode_id=%s",
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
                                    import_status="awaiting_workspace_import",
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

    # Preflight: no "Beat 1" / [BEAT_START:1] → skip LLM, mark scene invalid (do not batch-retry).
    for index, unit in indexed_scene_units:
        scene_source = (
            str(getattr(unit, "scene_text", "") or "").strip()
            or str(getattr(unit, "scene_markdown", "") or "").strip()
        )
        if scene_text_has_beat_1(scene_source):
            pending_units.append((index, unit))
            continue
        failure_code = f"SCENE_MARKDOWN_MISSING_BEAT_1:{unit.scene_id}"
        scene_failure_codes[str(unit.scene_id)] = failure_code
        logger.error(
            "[scene_markdown] missing Beat 1 | scene_id=%s scene_order=%s/%s — skip orchestration (invalid scene)",
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
            # Do not re-queue Stage 1 quality failures (missing Beat 1 / beats too short).
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
            },
        )

    per_scene_outputs: List[str] = []
    per_scene_results: List[Dict[str, Any]] = []
    last_result: Any = None
    for index, _unit in indexed_scene_units:
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

    merged_text = merge_scenes_table_markdown_outputs(per_scene_outputs)
    if not merged_text:
        raise HTTPException(status_code=422, detail="SCENE_MARKDOWN_MERGE_FAILED")

    orchestration_meta = {
        "per_scene_retried_scene_ids": sorted(retried_scene_ids),
        "per_scene_retry_attempts_max": SCENE_MARKDOWN_ORCHESTRATION_MAX_ATTEMPTS,
        "per_scene_batch_retry_rounds": SCENE_MARKDOWN_ORCHESTRATION_BATCH_RETRY_ROUNDS,
        "skipped_missing_beat1_scenes": skipped_missing_beat1_reports,
        "skipped_missing_beat1_count": len(skipped_missing_beat1_reports),
    }

    if isinstance(last_result, dict):
        merged_result = dict(last_result)
        merged_result["result"] = merged_text
        merged_result["content"] = merged_text
        merged_result["scenes_markdown"] = merged_text
        merged_result["per_scene_count"] = total_scenes
        merged_result["per_scene_parallel"] = max_concurrency
        merged_result["per_scene_source"] = scene_units_source
        merged_result["per_scene_persist_mode"] = "by_scene"
        merged_result["per_scene_outputs"] = per_scene_results
        merged_result.update(orchestration_meta)
        return merged_result
    return {
        "result": merged_text,
        "content": merged_text,
        "scenes_markdown": merged_text,
        "per_scene_count": total_scenes,
        "per_scene_parallel": max_concurrency,
        "per_scene_source": scene_units_source,
        "per_scene_persist_mode": "by_scene",
        "per_scene_outputs": per_scene_results,
        **orchestration_meta,
    }


def _subject_index_rows_present(subject_index_text: Any) -> bool:
    """Return True when text contains at least one real entity row (not header-only)."""
    text = str(subject_index_text or "")
    if not text.strip():
        return False
    return bool(
        re.search(r"(?im)^\s*\|\s*S\d{3,}\s*\|", text)
        or re.search(r"(?im)^\s*S\d{3,}\s*\|", text)
        or re.search(
            r"(?im)^\s*S\d{3,}(?:\s+|\t+|\s*\|\s*)[a-z_]+(?:\s+|\t+|\s*\|\s*)",
            text,
        )
        or re.search(r"(?im)^\s*subject_no\s*=\s*[A-Za-z]?\d+\b", text)
        or re.search(
            r"(?im)^\s*\|?\s*[A-Za-z]+\d+\s*\|\s*(?:character|prop|environment|cover_poster|角色|道具|环境|封面)",
            text,
        )
        or re.search(
            r"(?im)^\s*\|?\s*S\d{3,}\s*\|\s*(?:character|prop|environment|cover_poster|角色|道具|环境|封面)",
            text,
        )
    )


def _subject_index_has_usable_content(subject_index_text: Any) -> bool:
    """Return True when Subject Index has at least one real entity row (not header-only)."""
    sanitized = sanitize_subject_index_text(subject_index_text)
    if _subject_index_rows_present(sanitized):
        return True
    # sanitize may be overly strict (e.g. Chinese headers); fall back to raw row detection.
    return _subject_index_rows_present(subject_index_text)


def _coerce_subject_index_candidate(subject_index_text: Any) -> str:
    """Return the best usable Subject Index snippet from raw/sanitized text."""
    raw = str(subject_index_text or "")
    sanitized = sanitize_subject_index_text(raw)
    if _subject_index_rows_present(sanitized):
        return sanitized.strip()
    if _subject_index_rows_present(raw):
        # Keep from the first detectable row/header hint to avoid shipping unrelated prose.
        lines = raw.replace("\r\n", "\n").splitlines()
        start_idx = 0
        header_re = re.compile(
            r"(?i)^\s*(?:#{1,6}\s*)?(?:\*\*)?\s*(?:subject\s*index|subjects\s*index|资产清单|实体清单|设计资产索引)\b"
        )
        hint_re = re.compile(r"(?i)subject_no|subject_type|script_entity_coverage")
        row_re = re.compile(r"(?im)^\s*\|?\s*S\d{3,}\s*\|")
        for idx, line in enumerate(lines):
            stripped = str(line or "").strip()
            if header_re.search(stripped) or hint_re.search(stripped) or row_re.match(stripped):
                start_idx = idx
                break
        return "\n".join(lines[start_idx:]).strip()
    return sanitized.strip()


def _extract_subject_index_from_stage_outputs(stage_outputs_raw: Any) -> str:
    """Pull Subject Index from episode.ai_stage_outputs stage2.subject_index."""
    raw = str(stage_outputs_raw or "").strip()
    if not raw:
        return ""
    try:
        parsed = json.loads(raw)
    except Exception:
        return ""
    if not isinstance(parsed, dict):
        return ""
    stages = parsed.get("stages") if isinstance(parsed.get("stages"), dict) else {}
    stage2 = stages.get("stage2") if isinstance(stages.get("stage2"), dict) else {}
    outputs = stage2.get("outputs") if isinstance(stage2.get("outputs"), dict) else {}
    slot = outputs.get("subject_index") if isinstance(outputs.get("subject_index"), dict) else {}
    return _coerce_subject_index_candidate(slot.get("content"))


def resolve_usable_episode_subject_index(
    episode: Any,
    *,
    request_text: Any = None,
    explicit_subject_index: Any = None,
    heal_episode_field: bool = False,
    db: Any = None,
) -> str:
    """Resolve a usable Subject Index for downstream gates/injection.

    Prefer explicit client-provided Subject Index (what the Stage 2 UI shows), then
    episode.ai_scene_analysis_subject_index, then stage_outputs, then request-embedded
    text. Optionally heal a contaminated/empty episode field.
    """
    explicit_raw = _coerce_subject_index_candidate(explicit_subject_index)
    episode_field_raw = _coerce_subject_index_candidate(
        getattr(episode, "ai_scene_analysis_subject_index", None) if episode is not None else None
    )
    stage_outputs_raw = _extract_subject_index_from_stage_outputs(
        getattr(episode, "ai_stage_outputs", None) if episode is not None else None
    )
    request_raw = _coerce_subject_index_candidate(request_text)

    candidates: List[Tuple[str, str]] = [
        ("explicit", explicit_raw),
        ("stage_outputs", stage_outputs_raw),
        ("episode_field", episode_field_raw),
        ("request_text", request_raw),
    ]
    resolved_source = ""
    resolved_text = ""
    for source, candidate in candidates:
        if _subject_index_has_usable_content(candidate):
            resolved_source = source
            resolved_text = candidate
            break

    if not resolved_text:
        logger.warning(
            "[subject_index] resolve_miss episode_id=%s explicit_chars=%s episode_chars=%s stage_chars=%s request_chars=%s",
            getattr(episode, "id", None) if episode is not None else None,
            len(str(explicit_subject_index or "")),
            len(str(getattr(episode, "ai_scene_analysis_subject_index", "") or "") if episode is not None else ""),
            len(str(getattr(episode, "ai_stage_outputs", "") or "") if episode is not None else ""),
            len(str(request_text or "")),
        )

    if (
        heal_episode_field
        and resolved_text
        and episode is not None
        and resolved_source in {"explicit", "stage_outputs", "request_text"}
        and not _subject_index_has_usable_content(episode_field_raw)
    ):
        try:
            episode.ai_scene_analysis_subject_index = resolved_text
            if db is not None:
                db.add(episode)
                db.commit()
            logger.info(
                "[subject_index] healed episode.ai_scene_analysis_subject_index from %s episode_id=%s chars=%s",
                resolved_source,
                getattr(episode, "id", None),
                len(resolved_text),
            )
        except Exception as heal_err:
            logger.warning(
                "[subject_index] failed healing episode subject index from %s episode_id=%s err=%s",
                resolved_source,
                getattr(episode, "id", None),
                heal_err,
            )
            try:
                if db is not None:
                    db.rollback()
            except Exception:
                pass

    return resolved_text


def _subject_index_has_cover_poster(subject_index_text: Any) -> bool:
    text = sanitize_subject_index_text(subject_index_text)
    if not text:
        return False

    if re.search(r"(?i)\bsubject_type\s*=\s*(cover_poster|poster|posters|cover|covers|封面|封面海报|海报)\b", text):
        return True
    if re.search(r"(?im)\b(?:subject_type|type)\b\s*[:=]\s*(cover_poster|poster|posters|cover|covers|封面|封面海报|海报)\b", text):
        return True

    def _normalize_type(value: Any) -> str:
        key = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
        if key in {"cover_poster", "coverposter", "poster", "posters", "cover", "covers", "封面", "封面海报", "海报"}:
            return "cover_poster"
        return key

    for raw_line in str(text).splitlines():
        line = str(raw_line or "").replace("\ufeff", "").strip()
        line = re.sub(r"^\s*>\s*", "", line)
        line = re.sub(r"^\s*[-*+]\s+", "", line).strip()
        if not line:
            continue
        if "|" not in line:
            continue
        normalized_line = line.strip("|").strip()
        parts = [p.strip() for p in normalized_line.split("|")]
        if len(parts) < 2:
            continue
        first_col = str(parts[0] or "").strip().lower()
        if first_col in {"subject_no", "subject_id", "id", "编号"}:
            continue
        if _normalize_type(parts[1]) == "cover_poster":
            return True

    # subject_no-style line fallback, e.g.:
    # subject_no=S001 | subject_type=poster | ...
    for raw_line in str(text).splitlines():
        line = str(raw_line or "").replace("\ufeff", "").strip()
        if not line:
            continue
        if not re.search(r"(?i)\bsubject_(?:no|id)\b", line):
            continue
        matched = re.search(r"(?i)\bsubject_type\s*[:=]\s*([a-zA-Z_\-\u4e00-\u9fff]+)", line)
        if matched and _normalize_type(matched.group(1)) == "cover_poster":
            return True
    return False


def _script_optimization_has_project_visual_backfill(result_text: Any) -> bool:
    text = str(result_text or "").strip()
    if not text:
        return False

    if re.search(r"(?i)\bproject_visual_backfill\b", text):
        return True
    if re.search(r"(?im)^\s*(?:#{1,6}\s*)?Project\s*Visual\s*Backfill\b", text):
        return True

    fence_re = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
    for match in fence_re.finditer(text):
        candidate = str(match.group(1) or "").strip()
        if not candidate:
            continue
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict) and (
                "project_visual_backfill" in obj
                or "Project_Visual_Backfill" in obj
                or "projectVisualBackfill" in obj
            ):
                return True
        except Exception:
            continue

    try:
        maybe_obj = json.loads(text)
        if isinstance(maybe_obj, dict) and (
            "project_visual_backfill" in maybe_obj
            or "Project_Visual_Backfill" in maybe_obj
            or "projectVisualBackfill" in maybe_obj
        ):
            return True
    except Exception:
        pass

    return False


def _list_episode_scene_progress_rows(
    db: Session,
    *,
    project_id: int,
    episode_id: int,
    scene_ids: Optional[List[str]] = None,
) -> List[Any]:
    if ScriptProgressSceneUnit is None:
        return []
    query = (
        db.query(ScriptProgressSceneUnit)
        .filter(
            ScriptProgressSceneUnit.project_id == int(project_id),
            ScriptProgressSceneUnit.episode_id == int(episode_id),
        )
        .order_by(ScriptProgressSceneUnit.scene_order.asc(), ScriptProgressSceneUnit.id.asc())
    )
    if scene_ids:
        normalized = [str(x).strip() for x in scene_ids if str(x).strip()]
        if normalized:
            query = query.filter(ScriptProgressSceneUnit.scene_id.in_(normalized))
    return query.all()


def _resolve_scene_id_to_db_scene(
    db: Session,
    *,
    episode_id: int,
    scene_marker_id: str,
) -> Optional[Scene]:
    marker = str(scene_marker_id or "").strip()
    if not marker:
        return None
    fallback_no = marker
    if "_SC" in marker:
        try:
            fallback_no = marker.split("_SC", 1)[1]
        except Exception:
            fallback_no = marker
    scene = (
        db.query(Scene)
        .filter(
            Scene.episode_id == int(episode_id),
            or_(Scene.scene_no == marker, Scene.scene_no == fallback_no),
            _active_scene_clause(),
        )
        .first()
    )
    if scene:
        return scene
    try:
        maybe_num = int(fallback_no)
    except Exception:
        maybe_num = None
    if maybe_num is not None:
        return (
            db.query(Scene)
            .filter(
                Scene.episode_id == int(episode_id),
                cast(Scene.scene_no, String) == str(maybe_num),
                _active_scene_clause(),
            )
            .first()
        )
    return None


def _normalize_asset_types(values: Optional[List[str]]) -> List[str]:
    default_types = ["character", "prop", "environment", "poster"]
    if not values:
        return default_types
    normalized: List[str] = []
    alias = {
        "characters": "character",
        "props": "prop",
        "environments": "environment",
        "covers": "poster",
        "posters": "poster",
    }
    for item in values:
        key = str(item or "").strip().lower()
        if not key:
            continue
        key = alias.get(key, key)
        if key in {"character", "prop", "environment", "poster"} and key not in normalized:
            normalized.append(key)
    return normalized or default_types


def _normalize_scene_marker_id_from_scene(scene: Scene, episode_id: int) -> str:
    scene_no = str(getattr(scene, "scene_no", "") or "").strip()
    if scene_no:
        if "_SC" in scene_no:
            return scene_no
        return f"EP{int(episode_id):02d}_SC{scene_no}"
    return f"EP{int(episode_id):02d}_SC{int(scene.id)}"


@router.post("/prompts/scene-analysis/progress/sync-scene-units")
async def sync_scene_units_progress(
    request: SceneUnitsSyncRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == int(request.episode_id)).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)
    if int(request.project_id) != int(episode.project_id):
        raise HTTPException(status_code=400, detail="project_id does not match episode.project_id")

    script_id = request.script_id or f"episode:{int(request.episode_id)}"
    if request.prefer_markers:
        sync_result = sync_scene_units_from_markers(
            db,
            project_id=int(request.project_id),
            episode_id=int(request.episode_id),
            script_text=request.script_text,
            script_id=script_id,
        )
        summary = {
            "stage_key": STAGE_SCENE_MARKDOWN,
            "import_target": "script_progress_scene_units",
            "scene_count": int(sync_result.get("scene_count") or 0),
            "scene_ids": list(sync_result.get("scene_ids") or []),
            "parse_source": sync_result.get("parse_source"),
            "sync_result": sync_result,
        }
    else:
        summary = import_scene_markdown_stage(
            db=db,
            project_id=int(request.project_id),
            episode_id=int(request.episode_id),
            script_text=request.script_text,
            script_id=script_id,
            partial=bool(request.partial),
            target_scene_id=str(request.target_scene_id or "").strip() or None,
        )
    upsert_pipeline_node_status(
        db,
        project_id=int(request.project_id),
        episode_id=int(request.episode_id),
        script_id=script_id,
        node_name="scene_planning",
        status="success",
        progress_percent=100.0,
    )
    db.commit()
    return {"status": "ok", "summary": summary.get("sync_result") or summary}


@router.post("/prompts/scene-analysis/progress/reset-scene-orchestration")
async def reset_scene_orchestration_progress(
    request: SceneOrchestrationResetRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == int(request.episode_id)).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)
    if int(request.project_id) != int(episode.project_id):
        raise HTTPException(status_code=400, detail="project_id does not match episode.project_id")

    requested_scene_ids = expand_scene_ids_for_orchestration_reset([
        str(scene_id or "").strip()
        for scene_id in (request.scene_ids or [])
        if str(scene_id or "").strip()
    ])
    rows = (
        db.query(ScriptProgressSceneUnit)
        .filter(
            ScriptProgressSceneUnit.project_id == int(request.project_id),
            ScriptProgressSceneUnit.episode_id == int(request.episode_id),
        )
        .all()
    )
    reset_scene_ids: List[str] = []
    for row in rows:
        scene_id = str(getattr(row, "scene_id", "") or "").strip()
        if not scene_id:
            continue
        if requested_scene_ids and scene_id not in requested_scene_ids:
            continue
        update_scene_unit_orchestration_status(
            db,
            project_id=int(request.project_id),
            episode_id=int(request.episode_id),
            scene_id=scene_id,
            import_status="queued",
            parse_status="success",
            scene_markdown=None,
            parse_error_code=None,
        )
        reset_scene_ids.append(scene_id)

    script_id = f"episode:{int(request.episode_id)}"
    upsert_pipeline_node_status(
        db,
        project_id=int(request.project_id),
        episode_id=int(request.episode_id),
        script_id=script_id,
        node_name="scene_markdown",
        status="running",
        progress_percent=0.0,
        error_message=f"reset orchestration for {len(reset_scene_ids)} scene(s)",
    )
    db.commit()
    return {
        "status": "ok",
        "reset_scene_ids": reset_scene_ids,
        "reset_count": len(reset_scene_ids),
    }


@router.get("/prompts/scene-analysis/progress/episodes/{episode_id}")
async def get_episode_progress_snapshot(
    episode_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == int(episode_id)).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)

    scene_units: List[Dict[str, Any]] = []
    if ScriptProgressSceneUnit is not None:
        rows = (
            db.query(ScriptProgressSceneUnit)
            .filter(
                ScriptProgressSceneUnit.project_id == int(episode.project_id),
                ScriptProgressSceneUnit.episode_id == int(episode_id),
            )
            .order_by(ScriptProgressSceneUnit.scene_order.asc(), ScriptProgressSceneUnit.id.asc())
            .all()
        )
        scene_units = [
            {
                "scene_id": row.scene_id,
                "scene_order": row.scene_order,
                "parse_status": row.parse_status,
                "import_status": row.import_status,
                "orchestration_phase": _derive_scene_orchestration_phase(
                    import_status=row.import_status,
                    parse_status=row.parse_status,
                ),
                "parse_error_code": row.parse_error_code,
                "scene_markdown": str(getattr(row, "scene_markdown", "") or "").strip(),
                "updated_at": row.updated_at,
            }
            for row in rows
        ]

    pipeline_nodes: List[Dict[str, Any]] = []
    if ScriptProgressPipelineNode is not None:
        rows = (
            db.query(ScriptProgressPipelineNode)
            .filter(
                ScriptProgressPipelineNode.project_id == int(episode.project_id),
                ScriptProgressPipelineNode.episode_id == int(episode_id),
            )
            .order_by(ScriptProgressPipelineNode.id.asc())
            .all()
        )
        pipeline_nodes = [
            {
                "node_name": row.node_name,
                "scene_id": row.scene_id,
                "asset_type": row.asset_type,
                "status": normalize_node_status(row.status),
                "progress_percent": row.progress_percent,
                "retry_count": row.retry_count,
                "retry_limit": row.retry_limit,
                "runtime_meta": row.runtime_meta if isinstance(row.runtime_meta, dict) else {},
                "last_error_code": row.last_error_code,
                "updated_at": row.updated_at,
            }
            for row in rows
        ]

    asset_matrix: Dict[str, Dict[str, Any]] = {}
    for node in pipeline_nodes:
        if str(node.get("node_name") or "") != "asset_generation":
            continue
        sid = str(node.get("scene_id") or "").strip()
        at = str(node.get("asset_type") or "").strip()
        if not sid or not at:
            continue
        asset_matrix.setdefault(sid, {})[at] = {
            "status": node.get("status"),
            "progress_percent": node.get("progress_percent"),
            "last_error_code": node.get("last_error_code"),
            "updated_at": node.get("updated_at"),
        }

    return {
        "project_id": int(episode.project_id),
        "episode_id": int(episode_id),
        "scene_units": scene_units,
        "pipeline_nodes": pipeline_nodes,
        "asset_matrix": asset_matrix,
    }


@router.get("/prompts/scene-analysis/progress/projects/{project_id}/overview")
async def get_project_progress_overview(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_project_access(db, project_id, current_user)
    episode_ids = [int(e.id) for e in db.query(Episode).filter(
        Episode.project_id == int(project_id),
        _active_episode_clause(),
    ).all()]

    nodes = []
    if ScriptProgressPipelineNode is not None:
        nodes = (
            db.query(ScriptProgressPipelineNode)
            .filter(ScriptProgressPipelineNode.project_id == int(project_id))
            .all()
        )
    issues = []
    if ScriptProgressIssue is not None:
        issues = (
            db.query(ScriptProgressIssue)
            .filter(
                ScriptProgressIssue.project_id == int(project_id),
                ScriptProgressIssue.status != "resolved",
            )
            .all()
        )
    scenes_total = 0
    scenes_done = 0
    if ScriptProgressSceneUnit is not None:
        scene_rows = (
            db.query(ScriptProgressSceneUnit)
            .filter(ScriptProgressSceneUnit.project_id == int(project_id))
            .all()
        )
        scenes_total = len(scene_rows)
        scenes_done = sum(1 for row in scene_rows if str(row.import_status or "").lower() == "success")

    status_counts = {
        "queued": 0,
        "running": 0,
        "success": 0,
        "warning": 0,
        "failed": 0,
        "blocked": 0,
        "skipped": 0,
    }
    for row in nodes:
        status_counts[normalize_node_status(getattr(row, "status", None))] += 1

    total_nodes = len(nodes)
    done_nodes = status_counts["success"] + status_counts["skipped"]
    progress_percent = (float(done_nodes) / float(total_nodes) * 100.0) if total_nodes > 0 else 0.0
    overall_status = "running"
    if status_counts["failed"] > 0 or any(str(getattr(i, "severity", "")).upper() == "BLOCKER" for i in issues):
        overall_status = "failed"
    elif status_counts["blocked"] > 0:
        overall_status = "blocked"
    elif total_nodes > 0 and done_nodes >= total_nodes:
        overall_status = "success"
    elif total_nodes == 0:
        overall_status = "queued"

    issue_blockers = sum(1 for i in issues if str(getattr(i, "severity", "")).upper() == "BLOCKER")
    issue_warnings = sum(1 for i in issues if str(getattr(i, "severity", "")).upper() == "WARNING")
    issue_infos = sum(1 for i in issues if str(getattr(i, "severity", "")).upper() == "INFO")

    return {
        "project_id": int(project_id),
        "episode_ids": episode_ids,
        "overall_status": overall_status,
        "progress_percent": round(progress_percent, 2),
        "counts": {
            "pipeline_nodes_total": total_nodes,
            "pipeline_nodes_done": done_nodes,
            "running": status_counts["running"],
            "failed": status_counts["failed"],
            "blocked": status_counts["blocked"],
            "warning": status_counts["warning"],
            "scenes_total": scenes_total,
            "scenes_imported": scenes_done,
            "issues_open": len(issues),
            "issues_blocker": issue_blockers,
            "issues_warning": issue_warnings,
            "issues_info": issue_infos,
        },
    }


@router.get("/prompts/scene-analysis/progress/projects/{project_id}/issues")
async def get_project_progress_issues(
    project_id: int,
    episode_id: Optional[int] = Query(None),
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_project_access(db, project_id, current_user)
    if ScriptProgressIssue is None:
        return {"project_id": int(project_id), "issues": []}
    query = db.query(ScriptProgressIssue).filter(ScriptProgressIssue.project_id == int(project_id))
    if episode_id is not None:
        query = query.filter(ScriptProgressIssue.episode_id == int(episode_id))
    if severity:
        query = query.filter(ScriptProgressIssue.severity == str(severity).upper())
    if status:
        query = query.filter(ScriptProgressIssue.status == str(status).lower())
    rows = query.order_by(ScriptProgressIssue.updated_at.desc(), ScriptProgressIssue.id.desc()).all()
    return {
        "project_id": int(project_id),
        "issues": [
            {
                "id": int(row.id),
                "episode_id": row.episode_id,
                "script_id": row.script_id,
                "scene_id": row.scene_id,
                "severity": row.severity,
                "status": row.status,
                "issue_code": row.issue_code,
                "title": row.title,
                "details": row.details,
                "owner_domain": row.owner_domain,
                "node_ref": row.node_ref,
                "first_seen_at": row.first_seen_at,
                "last_seen_at": row.last_seen_at,
                "updated_at": row.updated_at,
            }
            for row in rows
        ],
    }


@router.post("/prompts/scene-analysis/progress/issues/resolve")
async def resolve_project_progress_issue(
    request: ProgressIssueResolveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if ScriptProgressIssue is None:
        raise HTTPException(status_code=404, detail="progress issue storage not enabled")
    issue = db.query(ScriptProgressIssue).filter(ScriptProgressIssue.id == int(request.issue_id)).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    _require_project_access(db, int(issue.project_id), current_user)
    ok = resolve_progress_issue(db, issue_id=int(request.issue_id))
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to resolve issue")
    db.commit()
    return {"status": "ok", "issue_id": int(request.issue_id)}


@router.post("/prompts/scene-analysis/progress/auto-orchestrate")
async def auto_orchestrate_scene_progress(
    request: ProgressAutoOrchestrateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == int(request.episode_id)).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)
    if int(request.project_id) != int(episode.project_id):
        raise HTTPException(status_code=400, detail="project_id does not match episode.project_id")

    scene_rows = _list_episode_scene_progress_rows(
        db,
        project_id=int(request.project_id),
        episode_id=int(request.episode_id),
        scene_ids=request.scene_ids,
    )
    if not scene_rows:
        raise HTTPException(status_code=400, detail="No scene progress units available. Sync scene units first.")

    marker_scene_ids = [str(getattr(row, "scene_id", "")).strip() for row in scene_rows if str(getattr(row, "scene_id", "")).strip()]
    db_scene_map: Dict[str, Scene] = {}
    unresolved_scene_ids: List[str] = []
    for marker_scene_id in marker_scene_ids:
        matched = _resolve_scene_id_to_db_scene(db, episode_id=int(request.episode_id), scene_marker_id=marker_scene_id)
        if matched is None:
            unresolved_scene_ids.append(marker_scene_id)
            raise_progress_issue(
                db,
                project_id=int(request.project_id),
                episode_id=int(request.episode_id),
                script_id=f"episode:{int(request.episode_id)}",
                scene_id=marker_scene_id,
                issue_code="SCENE_IMPORT_FAILED",
                title="Scene marker cannot map to saved scene",
                severity="BLOCKER",
                owner_domain="scene-orchestrator",
                node_ref="scene_import",
                details=f"Unable to find scene row for marker scene_id={marker_scene_id}",
            )
            upsert_pipeline_node_status(
                db,
                project_id=int(request.project_id),
                episode_id=int(request.episode_id),
                script_id=f"episode:{int(request.episode_id)}",
                scene_id=marker_scene_id,
                node_name="scene_import",
                status="failed",
                error_code="SCENE_IMPORT_FAILED",
                error_message=f"scene marker not found in db scene table: {marker_scene_id}",
            )
            continue
        db_scene_map[marker_scene_id] = matched

    if unresolved_scene_ids:
        db.commit()
        return {
            "status": "partial_failed",
            "message": "Some marker scene ids are not mapped to scene rows",
            "unresolved_scene_ids": unresolved_scene_ids,
        }

    scene_db_ids = [int(db_scene_map[sid].id) for sid in marker_scene_ids if sid in db_scene_map]
    for sid in marker_scene_ids:
        upsert_pipeline_node_status(
            db,
            project_id=int(request.project_id),
            episode_id=int(request.episode_id),
            script_id=f"episode:{int(request.episode_id)}",
            scene_id=sid,
            node_name="scene_import",
            status="success",
            progress_percent=100.0,
        )
        row = next((r for r in scene_rows if str(getattr(r, "scene_id", "")).strip() == sid), None)
        if row is not None:
            row.import_status = "success"
            row.updated_at = now_bj_iso()

    # Trigger storyboard per selected scenes (batch executor supports scene_ids)
    try:
        upsert_pipeline_node_status(
            db,
            project_id=int(request.project_id),
            episode_id=int(request.episode_id),
            script_id=f"episode:{int(request.episode_id)}",
            node_name="storyboard_generation",
            status="running",
            progress_percent=10.0,
            depends_on=["scene_import"],
            runtime_meta={
                "scene_db_ids": scene_db_ids,
                "scene_marker_ids": marker_scene_ids,
                "batch_type": "scene_ai_shots",
            },
        )
        _start_scene_ai_shots_batch_for_episode(
            db=db,
            episode=episode,
            current_user=current_user,
            scene_ids=scene_db_ids,
            function_name=request.function_name,
            system_api_id=request.system_api_id,
        )
    except Exception as exc:
        upsert_pipeline_node_status(
            db,
            project_id=int(request.project_id),
            episode_id=int(request.episode_id),
            script_id=f"episode:{int(request.episode_id)}",
            node_name="storyboard_generation",
            status="failed",
            error_code="STORYBOARD_JOB_FAILED",
            error_message=str(exc),
        )
        raise_progress_issue(
            db,
            project_id=int(request.project_id),
            episode_id=int(request.episode_id),
            script_id=f"episode:{int(request.episode_id)}",
            issue_code="STORYBOARD_JOB_FAILED",
            title="Storyboard batch start failed",
            severity="BLOCKER",
            owner_domain="storyboard-engine",
            node_ref="storyboard_generation",
            details=str(exc),
        )
        db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to start storyboard generation: {exc}")

    # Trigger per-scene asset generation by type through existing analyze_scene endpoint
    requested_asset_types = _normalize_asset_types(request.asset_types)
    asset_node_by_type = {
        "character": "asset_design_character",
        "prop": "asset_design_prop",
        "environment": "asset_design_environment",
        "poster": "asset_design_environment",
    }
    prompt_by_type = {
        "character": "skills/scene_analysis_feature_stack/entity_design_character.md",
        "prop": "skills/scene_analysis_feature_stack/entity_design_prop.md",
        "environment": "skills/scene_analysis_feature_stack/entity_design_environment_and_poster.md",
        "poster": "skills/scene_analysis_feature_stack/entity_design_environment_and_poster.md",
    }
    assets_dispatched: List[Dict[str, Any]] = []
    for marker_scene_id in marker_scene_ids:
        mapped_scene = db_scene_map.get(marker_scene_id)
        if mapped_scene is None:
            continue
        scene_text = str(getattr(mapped_scene, "original_script_text", "") or "").strip()
        for asset_type in requested_asset_types:
            node_name = asset_node_by_type.get(asset_type, "asset_design_environment")
            prompt_file = prompt_by_type.get(asset_type) or "skills/scene_analysis_feature_stack/entity_design_environment_and_poster.md"
            upsert_pipeline_node_status(
                db,
                project_id=int(request.project_id),
                episode_id=int(request.episode_id),
                script_id=f"episode:{int(request.episode_id)}",
                scene_id=marker_scene_id,
                node_name="asset_generation",
                asset_type=asset_type,
                status="queued",
                progress_percent=0.0,
                depends_on=["scene_import"],
                runtime_meta={"task_id": "", "kind": f"asset_generation_{asset_type}"},
            )
            tid = _submit_async(
                analyze_scene,
                user_id=current_user.id,
                kind=f"asset_generation_{asset_type}",
                req=AnalyzeSceneRequest(
                    text=scene_text or f"Scene {marker_scene_id}",
                    project_id=int(request.project_id),
                    episode_id=int(request.episode_id),
                    prompt_file=prompt_file,
                    function_name=request.function_name or "script_analysis",
                    system_api_id=request.system_api_id,
                ),
                async_mode="0",
            )
            upsert_pipeline_node_status(
                db,
                project_id=int(request.project_id),
                episode_id=int(request.episode_id),
                script_id=f"episode:{int(request.episode_id)}",
                scene_id=marker_scene_id,
                node_name="asset_generation",
                asset_type=asset_type,
                status="running",
                progress_percent=15.0,
                runtime_meta={"task_id": tid, "kind": f"asset_generation_{asset_type}"},
            )
            assets_dispatched.append(
                {
                    "scene_id": marker_scene_id,
                    "asset_type": asset_type,
                    "task_id": tid,
                    "node_name": node_name,
                }
            )

    db.commit()
    return {
        "status": "started",
        "project_id": int(request.project_id),
        "episode_id": int(request.episode_id),
        "scene_ids": marker_scene_ids,
        "scene_db_ids": scene_db_ids,
        "storyboard_started": True,
        "assets_dispatched": assets_dispatched,
    }


@router.post("/prompts/scene-analysis/progress/reconcile")
async def reconcile_progress_status(
    request: ProgressReconcileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == int(request.episode_id)).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)
    if int(request.project_id) != int(episode.project_id):
        raise HTTPException(status_code=400, detail="project_id does not match episode.project_id")

    updated_asset_nodes = 0
    updated_storyboard_nodes = 0

    if ScriptProgressPipelineNode is not None:
        asset_nodes = (
            db.query(ScriptProgressPipelineNode)
            .filter(
                ScriptProgressPipelineNode.project_id == int(request.project_id),
                ScriptProgressPipelineNode.episode_id == int(request.episode_id),
                ScriptProgressPipelineNode.node_name == "asset_generation",
            )
            .all()
        )
        for row in asset_nodes:
            meta = row.runtime_meta if isinstance(row.runtime_meta, dict) else {}
            task_id = str(meta.get("task_id") or "").strip()
            if not task_id:
                continue
            info = _get_task_status(task_id, user_id=current_user.id) or _get_task_status(task_id)
            if not isinstance(info, dict):
                continue
            task_status = str(info.get("status") or "").strip().lower()
            next_status = None
            next_progress = None
            error_code = None
            error_message = None
            if task_status == "completed":
                next_status = "success"
                next_progress = 100.0
            elif task_status == "failed":
                next_status = "failed"
                next_progress = float(row.progress_percent or 0.0)
                error_code = "ASSET_TYPE_JOB_FAILED"
                error_message = str(info.get("error") or "asset task failed")
            elif task_status == "canceled":
                next_status = "blocked"
                error_code = "ASSET_TYPE_JOB_CANCELED"
                error_message = str(info.get("error") or "asset task canceled")
            elif task_status in {"running", "pending"}:
                next_status = "running"
                next_progress = max(float(row.progress_percent or 0.0), 20.0)
            if next_status is None:
                continue

            current_status = normalize_node_status(getattr(row, "status", None))
            if current_status == next_status and (next_progress is None or abs(float(row.progress_percent or 0.0) - float(next_progress)) < 0.001):
                continue
            upsert_pipeline_node_status(
                db,
                project_id=int(request.project_id),
                episode_id=int(request.episode_id),
                script_id=row.script_id,
                scene_id=row.scene_id,
                node_name="asset_generation",
                asset_type=row.asset_type,
                status=next_status,
                progress_percent=(next_progress if next_progress is not None else row.progress_percent),
                runtime_meta=meta,
                error_code=error_code,
                error_message=error_message,
            )
            updated_asset_nodes += 1
            if next_status in {"failed", "blocked"}:
                raise_progress_issue(
                    db,
                    project_id=int(request.project_id),
                    episode_id=int(request.episode_id),
                    script_id=row.script_id,
                    scene_id=row.scene_id,
                    issue_code=error_code or "ASSET_TYPE_JOB_FAILED",
                    title="Asset type job did not complete successfully",
                    severity="WARNING",
                    owner_domain="asset-worker",
                    node_ref="asset_generation",
                    details=error_message,
                )

        storyboard_nodes = (
            db.query(ScriptProgressPipelineNode)
            .filter(
                ScriptProgressPipelineNode.project_id == int(request.project_id),
                ScriptProgressPipelineNode.episode_id == int(request.episode_id),
                ScriptProgressPipelineNode.node_name == "storyboard_generation",
            )
            .all()
        )
        batch_status = _read_scene_ai_shots_batch_status(episode)
        running = bool(batch_status.get("running"))
        failed = int(batch_status.get("failed") or 0)
        total = int(batch_status.get("total") or 0)
        completed = int(batch_status.get("completed") or 0)
        next_storyboard_status = "running" if running else ("failed" if failed > 0 and completed < total else "success")
        next_storyboard_progress = (float(completed) / float(total) * 100.0) if total > 0 else (10.0 if running else 100.0)
        storyboard_error = None
        storyboard_error_message = None
        if next_storyboard_status == "failed":
            storyboard_error = "STORYBOARD_JOB_FAILED"
            storyboard_error_message = str(batch_status.get("message") or "storyboard batch failed")

        for row in storyboard_nodes:
            cur = normalize_node_status(getattr(row, "status", None))
            if cur == next_storyboard_status and abs(float(row.progress_percent or 0.0) - float(next_storyboard_progress)) < 0.001:
                continue
            upsert_pipeline_node_status(
                db,
                project_id=int(request.project_id),
                episode_id=int(request.episode_id),
                script_id=row.script_id,
                scene_id=row.scene_id,
                node_name="storyboard_generation",
                status=next_storyboard_status,
                progress_percent=next_storyboard_progress,
                runtime_meta=row.runtime_meta if isinstance(row.runtime_meta, dict) else {},
                error_code=storyboard_error,
                error_message=storyboard_error_message,
            )
            updated_storyboard_nodes += 1
        if next_storyboard_status == "failed":
            raise_progress_issue(
                db,
                project_id=int(request.project_id),
                episode_id=int(request.episode_id),
                script_id=f"episode:{int(request.episode_id)}",
                issue_code="STORYBOARD_JOB_FAILED",
                title="Storyboard batch failed",
                severity="BLOCKER",
                owner_domain="storyboard-engine",
                node_ref="storyboard_generation",
                details=storyboard_error_message,
            )

        # best-effort mark scene import success for scenes with finished storyboard
        if ScriptProgressSceneUnit is not None and total > 0 and completed > 0:
            db_scenes = db.query(Scene).filter(
                Scene.episode_id == int(request.episode_id),
                _active_scene_clause(),
            ).all()
            scene_ids_done = set()
            if next_storyboard_status == "success":
                scene_ids_done = {_normalize_scene_marker_id_from_scene(s, int(request.episode_id)) for s in db_scenes}
            for row in (
                db.query(ScriptProgressSceneUnit)
                .filter(
                    ScriptProgressSceneUnit.project_id == int(request.project_id),
                    ScriptProgressSceneUnit.episode_id == int(request.episode_id),
                )
                .all()
            ):
                if row.scene_id in scene_ids_done:
                    row.import_status = "success"
                    row.updated_at = now_bj_iso()

    db.commit()
    return {
        "status": "ok",
        "project_id": int(request.project_id),
        "episode_id": int(request.episode_id),
        "updated_asset_nodes": int(updated_asset_nodes),
        "updated_storyboard_nodes": int(updated_storyboard_nodes),
    }


@router.post("/prompts/scene-analysis/flow/run-node")
async def run_scene_analysis_flow_node(
    request: ScriptAnalysisFlowRunNodeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    """Run one workflow node through its existing executor while preserving node-specific injection chains."""
    node_key = str(getattr(request, "node_key", "") or "").strip().lower().replace("-", "_")
    if async_mode == "1":
        tid = _submit_async(
            run_scene_analysis_flow_node,
            user_id=current_user.id,
            kind=f"script_analysis_flow_{node_key or 'unknown'}",
            request=request,
            async_mode="0",
        )
        return JSONResponse({
            "task_id": tid,
            "async": True,
            "node_key": node_key,
        })

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
            episode = db.query(Episode).filter(Episode.id == int(raw_payload.get("episode_id"))).first()
            if not episode:
                raise HTTPException(status_code=404, detail="Episode not found")
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
                # Slim Stage 1 script to per-scene ENV_BLOCK + Beats before Subject Index LLM.
                try:
                    original_text = str(raw_payload.get("text") or "")
                    adapted_for_assets = extract_adapted_script_from_beats_user_input(original_text)
                    if not adapted_for_assets.strip():
                        wrapped = unwrap_injection_section(original_text, "优化后剧本")
                        if wrapped:
                            adapted_for_assets = re.sub(
                                r"^\[[^\]]+\]\s*\n?",
                                "",
                                str(wrapped),
                            ).strip()
                    if adapted_for_assets.strip():
                        slim_script = build_assets_extraction_script_from_adapted(adapted_for_assets)
                        if slim_script.strip() and slim_script.strip() != adapted_for_assets.strip():
                            raw_payload["text"] = _replace_adapted_script_in_beats_user_input(
                                original_text,
                                slim_script,
                            )
                            logger.info(
                                "[剧本分析流程] assets_extraction 已替换为逐场环境+Beat 输入 | chars=%s→%s",
                                len(adapted_for_assets),
                                len(slim_script),
                            )
                except Exception as slim_exc:
                    logger.warning(
                        "[剧本分析流程] assets_extraction env+beat slim failed; using original text | err=%s",
                        slim_exc,
                    )
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
                max_attempts = 2
                result = None
                for attempt in range(1, max_attempts + 1):
                    result = await analyze_scene(AnalyzeSceneRequest(**raw_payload), current_user=current_user, db=db, async_mode="0")
                    result_text = _extract_analysis_text_from_result(result)
                    has_visual_backfill = _script_optimization_has_project_visual_backfill(result_text)
                    if has_visual_backfill:
                        if attempt > 1:
                            logger.info(
                                "[剧本分析流程] 节点 %s 在重试后通过 Project Visual Backfill 校验 | attempt=%s",
                                node_key,
                                attempt,
                            )
                        break
                    logger.warning(
                        "[剧本分析流程] 节点 %s 缺少 Project Visual Backfill | attempt=%s/%s",
                        node_key,
                        attempt,
                        max_attempts,
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
                        error_message="project_visual_backfill missing, auto-retrying once",
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

        episode = db.query(Episode).filter(Episode.id == episode_id).first()
        if not episode:
            raise HTTPException(status_code=404, detail="Episode not found")
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

