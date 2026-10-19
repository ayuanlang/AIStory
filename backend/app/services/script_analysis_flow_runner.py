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
from app.services.scene_subskill_pipeline_runner import (
    describe_scene_subskill_batch_failure,
    run_scene_subskill_pipeline,
)
from app.services.script_analysis_flow import (
    STAGE_SCENE_MARKDOWN,
    coerce_target_scene_ids_for_orchestration,
    get_script_analysis_flow_registry,
    import_analyze_scene_stage_result,
    parse_scene_units_from_markers,
    persist_script_optimization_stage,
    reset_downstream_progress_for_node_rerun,
    resolve_assets_extraction_source_text,
    upsert_pipeline_node_status,
)
from app.services.script_analysis_flow.environment_reuse import SCENE_ENV_IDENT_PATTERN
from app.services.script_analysis_llm_config import (
    _resolve_script_analysis_dropdown_order,
    _select_script_analysis_api_order,
)
from app.services.promo_context import is_promo_project, promo_scene_split_is_valid
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
    "asset_design_environment_quad": "主环境四宫格",
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
    ],
    # The four-grid is started by the frontend after environment design returns.
    # Queuing it here left asset_design_environment_quad queued for the whole
    # design call, and finalize_stale marked it NODE_TIMEOUT after 900s.
    # Storyboard is frontend-owned (per-scene generateSceneShots after staging+ENV).
    # Queuing a backend placeholder here left storyboard_generation stuck in queued
    # until finalize_stale marked it NODE_TIMEOUT after 900s.
}

_REEXTRACT_MARK = re.compile(r"(?im)^[ \t]*\[REEXTRACT:(?:CHAR|PROP)\][ \t]*\r?\n?")
_ENV_SCENE_PATCH_PATTERN = re.compile(
    r"`?\[ENV_SCENE_PATCH_START:([^\s\]]+)\]`?"
    r"(.*?)"
    r"`?\[ENV_SCENE_PATCH_END:([^\s\]]+)\]`?",
    re.IGNORECASE | re.DOTALL,
)
_NESTED_SCENE_MARKER_IN_PATCH_RE = re.compile(
    r"`?\[SCENE_(?:CONTENT_)?(?:START|END):[^\s\]]+\]`?",
    re.IGNORECASE,
)


def _normalize_reextract_target(value: object) -> str:
    target = str(value or "").strip().lower()
    if target in {"char", "character", "characters", "角色"}:
        return "character"
    if target in {"prop", "props", "道具"}:
        return "prop"
    return ""


def _strip_reextract_marker(text: str) -> str:
    return _REEXTRACT_MARK.sub("", str(text or "")).strip()


def _reextract_supplement_brief(target: str) -> str:
    if target == "character":
        return (
            "先通读【原剧本】，再对照【已有全局统筹】里的角色列表，在原列表上补充。"
            "仍符合规则的行保留已登记名称与外形。"
            "只输出已有列表里没有的角色。"
            "要补的是另一可持续状态：换装、缚与解、蒙面与揭面、年龄态、法相、龙、金身。"
            "已登记的名称不要再写。没有可补的，块内只写一行无。"
        )
    return (
        "先通读【原剧本】，再对照【已有全局统筹】里的道具列表。"
        "只输出已有列表里没有的道具。"
        "要补的是：手持或挽着的物件；打破、点燃等前后外形可区分的两条互相依赖状态道具；"
        "看见整机外形却漏掉的整车，以及驾驶舱或舱内做场缺的载具裁定。"
        "正文已经看见整机，必须补整车道具，禁止只留驾驶舱。"
        "只在舱内做场、正文没有整机外形，才写仅内部并留下舱名。"
        "已登记的名称不要再写。没有可补的，块内只写一行无。"
    )


def _compose_reextract_user_text(script_text: str, target: str, original_script: str = "") -> str:
    """Original script is the source. The orchestration draft is only the list to supplement."""
    kind = "角色" if target == "character" else "道具"
    tag = "CHAR" if target == "character" else "PROP"
    marker = "[REEXTRACT:CHAR]" if target == "character" else "[REEXTRACT:PROP]"
    orchestration = _strip_reextract_marker(script_text)
    original = str(original_script or "").strip()
    if original:
        original_block = f"【原剧本】\n{original}\n【原剧本结束】"
    else:
        original_block = (
            "【原剧本】\n"
            "（本集原剧本为空。只得按已有全局统筹补，不得另编原文没有的人与物。）\n"
            "【原剧本结束】"
        )
    return (
        f"{marker}\n\n"
        f"{_reextract_supplement_brief(target)}\n"
        "禁止续写，禁止复述，禁止输出镜头、建置、入戏、P1、音效或当前环境。\n\n"
        f"{original_block}\n\n"
        "【已有全局统筹】\n"
        "下面是当前全局统筹成稿，含已登记的提取块和场次。只用来对照已有名单、适用场和场号，不代替原剧本。\n"
        f"{orchestration}\n"
        "【已有全局统筹结束】\n\n"
        f"本轮唯一合法输出是一块{kind}增量："
        f"从 [{tag}_EXTRACT_START] 开始，到 [{tag}_EXTRACT_END] 结束。"
        f"只写已有列表里没有的条目，每一件单独一行 [{tag}]，字段按本技能 §8 模板。"
        "没有可补的，块内只写一行无。"
        "不要在列表前后写任何别的字。"
    )


def _load_reextract_original_script(episode: Any, raw_payload: Dict[str, Any]) -> str:
    """Editor copy wins when present; otherwise use the saved episode script page."""
    from app.services.episode_script_output import extract_official_episode_script

    incoming = str(raw_payload.pop("original_script", "") or "").strip()
    stored = ""
    if episode is not None:
        stored = str(getattr(episode, "script_content", "") or "").strip()
    return extract_official_episode_script(incoming or stored)


def _reextract_system_contract(target: str) -> str:
    kind = "角色" if target == "character" else "道具"
    tag = "CHAR" if target == "character" else "PROP"
    if target == "character":
        focus = "依据是原剧本。只输出已有角色列表里没有的条目，如换装、缚解、蒙面揭面、年龄态、法相金身。程序会把这些新条目追加进原列表。"
    else:
        focus = "依据是原剧本。只输出已有道具列表里没有的条目，如前后状态道具，以及看见整机却漏掉的整车和驾驶舱载具裁定。程序会把这些新条目追加进原列表。"
    return (
        "【重新抽取输出合同】\n"
        f"本轮只输出{kind}增量。{focus}"
        f"唯一合法输出是 [{tag}_EXTRACT_START] 到 [{tag}_EXTRACT_END]。"
        "禁止续写镜头句、建置、入戏、P1、音效、当前环境，禁止输出 Project Visual Backfill。"
    )


def _choose_reextract_base(request_text: str, stored_text: str) -> str:
    request_base = _strip_reextract_marker(request_text)
    stored = str(stored_text or "").strip()
    if stored and "[SCENE_START" in stored.upper() and "[SCENE_START" not in request_base.upper():
        return stored
    return request_base or stored


def _apply_list_reextract(*, llm_text: str, request_text: str, stored_text: str, target: str) -> Tuple[str, str]:
    """Keep registered rows and append only names the increment adds."""
    from app.services.script_analysis_flow.character_asset_brief import (
        char_extract_has_items,
        char_extract_is_explicit_none,
        merge_char_extract_increment,
        pick_refreshed_char_extract_block,
        replace_char_extract_in_script,
    )
    from app.services.script_analysis_flow.prop_asset_brief import (
        merge_prop_extract_increment,
        pick_refreshed_prop_extract_block,
        prop_extract_has_items,
        prop_extract_is_explicit_none,
        replace_prop_extract_in_script,
    )

    base = _choose_reextract_base(request_text, stored_text)
    if not base.strip():
        raise HTTPException(status_code=422, detail="当前没有可更新的全局统筹剧本")
    if target == "character":
        block = pick_refreshed_char_extract_block(llm_text, base)
        if not block or not (char_extract_has_items(block) or char_extract_is_explicit_none(block)):
            raise HTTPException(status_code=422, detail=_reextract_reject_detail("character", llm_text))
        merged_block = merge_char_extract_increment(base, block)
        return replace_char_extract_in_script(base, merged_block), merged_block
    block = pick_refreshed_prop_extract_block(llm_text, base)
    if not block or not (prop_extract_has_items(block) or prop_extract_is_explicit_none(block)):
        raise HTTPException(status_code=422, detail=_reextract_reject_detail("prop", llm_text))
    merged_block = merge_prop_extract_increment(base, block)
    return replace_prop_extract_in_script(base, merged_block), merged_block


def _reextract_reject_detail(target: str, llm_text: str) -> str:
    label = "角色列表" if target == "character" else "道具列表"
    text = str(llm_text or "")
    if re.search(r"镜头在|当前环境\s*=|Bird's-Eye|\bP\d+\s*\d", text, flags=re.IGNORECASE):
        return f"重新抽取未返回{label}。模型续写了镜头句，没有返回提取块。"
    return f"重新抽取未返回{label}"


def _strip_nested_scene_markers_from_patch(body: str) -> str:
    """ENV patches must not introduce extra SCENE_START/END pairs into the split script."""
    cleaned = _NESTED_SCENE_MARKER_IN_PATCH_RE.sub("", str(body or ""))
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()
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
        patches[start_id] = _strip_nested_scene_markers_from_patch(body)
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


MIN_SCOPED_NODE_BODY_CHARS = 100


def scoped_node_body_usable(text: Any, min_chars: int = MIN_SCOPED_NODE_BODY_CHARS) -> bool:
    """True when stripped node body is more than an end marker / empty stub."""
    body = str(text or "").strip()
    return len(body) > int(min_chars or MIN_SCOPED_NODE_BODY_CHARS)


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
        "asset_design_environment_quad",
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
        raw_reextract = str(raw_payload.get("reextract_target") or "").strip()
        reextract_target = _normalize_reextract_target(raw_reextract)
        if node_key == "scene_split" and raw_reextract and not reextract_target:
            raise HTTPException(status_code=400, detail="reextract_target must be character or prop")
        list_reextract = node_key == "scene_split" and bool(reextract_target)
        target_scene_id = str(raw_payload.get("target_scene_id") or "").strip()
        # Scene markdown still reads 「本次仅处理 Scene ID」 from its own user text.
        # A full-episode 逐场优化 continue must not: that line inside an older
        # script echo would scope the whole run to one scene.
        target_source_text = (
            str(raw_payload.get("text") or "")
            if node_key == "scene_markdown"
            else ""
        )
        target_scene_ids = coerce_target_scene_ids_for_orchestration(
            raw_payload,
            target_source_text,
        )
        scoped_rerun = bool(target_scene_ids)
        start_from_step = str(raw_payload.get("start_from_step") or "").strip()
        preserve_per_scene = bool(
            raw_payload.get("preserve_per_scene")
            or raw_payload.get("skip_per_scene_reset")
        )
        if node_key == "scene_markdown" and target_scene_id:
            scoped_action_name = f"场景编排 · {target_scene_id}"
        elif node_key == "scene_subskill_pipeline" and target_scene_id:
            scoped_action_name = (
                f"逐场优化 · {target_scene_id}"
                + (f" · {start_from_step}" if start_from_step else "")
            )
        elif list_reextract:
            scoped_action_name = "重新抽取角色" if reextract_target == "character" else "重新抽取道具"
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
            # Do not persist an incomplete first scene_split attempt. Resume/reuse
            # would otherwise treat that draft as finished and skip the completeness gate.
            raw_payload["skip_episode_persist"] = True
        
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
        if node_project_id > 0 and node_episode_id > 0 and not list_reextract:
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
                downstream_nodes = list(_FLOW_DOWNSTREAM_NODES.get(node_key, []))
                if preserve_per_scene:
                    downstream_nodes = [
                        name
                        for name in downstream_nodes
                        if name not in {"scene_subskill_pipeline", "storyboard_generation"}
                    ]
                for downstream_node in downstream_nodes:
                    upsert_pipeline_node_status(
                        db,
                        project_id=node_project_id,
                        episode_id=node_episode_id,
                        script_id=f"episode:{node_episode_id}",
                        node_name=downstream_node,
                        status="queued",
                        progress_percent=0.0,
                    )
            reset_downstream_progress_for_node_rerun(
                db,
                project_id=node_project_id,
                episode_id=node_episode_id,
                node_key=node_key,
                scoped_scene_ids=target_scene_ids if scoped_rerun else None,
                preserve_per_scene=preserve_per_scene,
            )
            db.commit()

        if episode is not None:
            from app.services.script_analysis_flow.node_advanced_spec import (  # noqa: WPS433
                resolve_flow_node_advanced_spec,
            )

            flow_spec = resolve_flow_node_advanced_spec(
                episode,
                node_key=node_key,
                reextract_target=reextract_target if list_reextract else "",
            )
            if flow_spec:
                raw_payload["node_advanced_spec"] = flow_spec

        reextract_base_text = ""
        if list_reextract:
            reextract_base_text = _strip_reextract_marker(str(raw_payload.get("text") or ""))
            original_script = _load_reextract_original_script(episode, raw_payload)
            raw_payload["text"] = _compose_reextract_user_text(
                reextract_base_text,
                reextract_target,
                original_script,
            )
            contract = _reextract_system_contract(reextract_target)
            system_prompt = str(raw_payload.get("system_prompt") or "")
            if contract not in system_prompt:
                raw_payload["system_prompt"] = f"{system_prompt.rstrip()}\n\n{contract}".strip()

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
                    backfill_ok = list_reextract or _script_optimization_has_project_visual_backfill(result_text)
                    promo_meta = raw_payload.get("project_metadata")
                    promo_ok = (
                        True
                        if list_reextract
                        else (
                            promo_scene_split_is_valid(result_text, promo_meta)
                            if node_key == "scene_split"
                            else True
                        )
                    )
                    if backfill_ok and promo_ok:
                        if attempt > 1:
                            logger.info(
                                "[剧本分析流程] 节点 %s 整段重跑后通过完整性校验 | attempt=%s switched_api=%s",
                                node_key,
                                attempt,
                                switched,
                            )
                        break
                    incomplete_reason = (
                        "商业宣传片拆成多场"
                        if backfill_ok and not promo_ok
                        else "缺少 Project Visual Backfill（输出不完整）"
                    )
                    logger.warning(
                        "[剧本分析流程] 节点 %s %s | attempt=%s/%s switched_api=%s",
                        node_key,
                        incomplete_reason,
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
            if node_project_id > 0 and node_episode_id > 0 and not list_reextract:
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
            if list_reextract:
                if scene_split_episode is None or not str(scene_split_text or "").strip():
                    raise HTTPException(status_code=422, detail="重新抽取未返回列表")
                from app.services.script_analysis_flow import (  # noqa: WPS433
                    load_stage1_output_text,
                    persist_reextracted_list,
                )

                stored_scene_split = load_stage1_output_text(db, node_episode_id, "scene_split")
                merged_text, new_block = _apply_list_reextract(
                    llm_text=scene_split_text,
                    request_text=reextract_base_text or str(raw_payload.get("text") or ""),
                    stored_text=stored_scene_split,
                    target=reextract_target,
                )
                result = _replace_analysis_result_text(result, merged_text)
                persist_reextracted_list(
                    db=db,
                    episode=scene_split_episode,
                    merged_scene_split=merged_text,
                    tag="CHAR" if reextract_target == "character" else "PROP",
                    new_block=new_block,
                )
                result = _mark_analysis_result_persisted(result, int(node_episode_id))
            elif scene_split_episode is not None and scene_split_text.strip():
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

        if node_key == "asset_design_environment_quad" and node_project_id > 0 and node_episode_id > 0:
            from app.services.script_analysis_flow.derived_env_ingest import (  # noqa: WPS433
                DEGREE_NAME_PATTERN,
                apply_main_environment_quad_prompts,
                extract_named_design_openings,
                format_main_environment_quad_apply_failure,
                missing_requested_quad_drafts,
                quad_cells_prompt_ready,
            )

            subjects = {}
            if isinstance(result, dict):
                raw_subjects = result.get("subjects_json")
                if isinstance(raw_subjects, dict):
                    subjects = raw_subjects
            rows = subjects.get("environments") if isinstance(subjects, dict) else None
            named_rows = [
                row for row in (rows or [])
                if isinstance(row, dict) and str(row.get("name") or "").strip()
                and not DEGREE_NAME_PATTERN.match(str(row.get("name") or "").strip())
            ]
            ready_rows = [
                row for row in named_rows
                if quad_cells_prompt_ready(row.get("generation_prompt_cn"))
            ]
            source_text = str(raw_payload.get("text") or "")
            openings = extract_named_design_openings(source_text)
            missing_requested = missing_requested_quad_drafts(source_text, named_rows)
            complete = bool(named_rows) and len(ready_rows) == len(named_rows) and not missing_requested
            # Keep prompts that already have every cell. The failure still names
            # the gaps, and the caller reruns only those environments.
            applied = (
                apply_main_environment_quad_prompts(
                    db,
                    project_id=node_project_id,
                    episode_id=node_episode_id,
                    rows=ready_rows,
                    openings=openings,
                )
                if ready_rows
                else {"updated": [], "missing": [], "skipped": []}
            )
            if (
                not complete
                or len(applied.get("updated") or []) != len(ready_rows)
            ):
                failure_message = format_main_environment_quad_apply_failure(named_rows, applied)
                if missing_requested:
                    shown = missing_requested[:8]
                    tail = f"等{len(missing_requested)}条" if len(missing_requested) > len(shown) else ""
                    failure_message += f"请求里的设计稿未一次写回：{'、'.join(shown)}{tail}。"
                logger.error(
                    "[environment_quad] not applied episode_id=%s project_id=%s %s",
                    node_episode_id,
                    node_project_id,
                    failure_message,
                )
                upsert_pipeline_node_status(
                    db,
                    project_id=node_project_id,
                    episode_id=node_episode_id,
                    script_id=f"episode:{node_episode_id}",
                    node_name=node_key,
                    status="failed",
                    error_code="ENVIRONMENT_QUAD_NOT_APPLIED",
                    error_message=failure_message,
                )
                db.commit()
                raise HTTPException(
                    status_code=422,
                    detail=f"ENVIRONMENT_QUAD_NOT_APPLIED: {failure_message}",
                )

        if node_project_id > 0 and node_episode_id > 0 and not list_reextract:
            if node_key != "scene_markdown":
                partial_failure = isinstance(result, dict) and bool(result.get("partial_failure"))
                failed_scene_ids = (
                    list(result.get("failed_scene_ids") or [])
                    if isinstance(result, dict)
                    else []
                )
                scene_count = int((result or {}).get("scene_count") or 0) if isinstance(result, dict) else 0
                all_failed = bool(
                    failed_scene_ids
                    and (scene_count <= 0 or scene_count <= len(failed_scene_ids))
                )
                batch_failure = (
                    describe_scene_subskill_batch_failure(result)
                    if failed_scene_ids
                    else {}
                )
                failure_code = None
                failure_message = None
                if failed_scene_ids:
                    failure_code = str(batch_failure.get("error_code") or "").strip() or (
                        "SCENE_SUBSKILL_ALL_FAILED"
                        if all_failed
                        else "SCENE_SUBSKILL_PARTIAL_FAILURE"
                    )
                    failure_message = str(batch_failure.get("error_message") or "").strip() or None
                waiting_scene_ids = (
                    [
                        str(item or "").strip()
                        for item in (result.get("waiting_scene_ids") or [])
                        if str(item or "").strip()
                    ]
                    if isinstance(result, dict) and node_key == "scene_subskill_pipeline"
                    else []
                )
                asset_wait_only = bool(waiting_scene_ids) and not failed_scene_ids
                if asset_wait_only:
                    node_status = "running"
                    node_progress = 70.0
                    failure_code = None
                    failure_message = None
                    node_runtime_meta = {
                        "business_event": "waiting",
                        "business_reason": "等待环境资产四宫格",
                        "current_step": "wait_env_asset",
                        "current_step_label": "等待环境资产四宫格",
                        "waiting_scene_ids": waiting_scene_ids,
                    }
                else:
                    node_status = "failed" if all_failed else ("warning" if partial_failure else "success")
                    node_progress = 100.0
                    node_runtime_meta = (
                        {
                            "business_event": "all_failed" if all_failed else "partial_failure",
                            "failed_scene_ids": failed_scene_ids,
                        }
                        if failed_scene_ids
                        else None
                    )
                upsert_pipeline_node_status(
                    db,
                    project_id=node_project_id,
                    episode_id=node_episode_id,
                    script_id=f"episode:{node_episode_id}",
                    node_name=node_key,
                    status=node_status,
                    progress_percent=node_progress,
                    error_code=failure_code,
                    error_message=failure_message,
                    runtime_meta=node_runtime_meta,
                )
            if node_key == "scene_subskill_pipeline" and not (
                isinstance(result, dict) and (
                    result.get("partial_failure") or result.get("waiting_scene_ids")
                )
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
