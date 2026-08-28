# -*- coding: utf-8 -*-
"""Per-scene Stage-1 subskill orchestration."""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.all_models import Episode, ScriptProgressPipelineNode, User
from app.schemas.agent import AnalyzeSceneRequest
from app.schemas.user_auth import (
    USER_ACTIVE_LEVEL_DEFAULT,
    resolve_user_batch_parallel_limit,
)
from app.services.db_session_utils import _release_db_connection, _snapshot_user_principal
from app.services.scene_markdown_orchestration import _extract_analysis_text_from_result
from app.core.prompt_injection import strip_injection_section
from app.services.script_analysis_flow import (
    COMPREHENSIVE_INFO_PATTERN,
    SCENES_BLOCK_END_TOKEN,
    SCENES_BLOCK_START_TOKEN,
    SPECIAL_SCENE_ANALYSIS_PATTERN,
    SceneMarkerParseError,
    build_scene_subskill_task_payloads,
    coerce_target_scene_ids_for_orchestration,
    extract_env_block_from_scene_text,
    parse_scene_units_from_markers,
    parse_special_scene_analysis_blocks,
    load_scene_subskill_results_map,
    lookup_persisted_scene_subskill_steps,
    persist_scene_subskill_named_step,
    persist_script_optimization_stage,
    upsert_pipeline_node_status,
    upsert_workspace_scene_from_staging,
)
from app.services.script_analysis_flow.derived_env_ingest import (
    DERIVED_ENV_EXTRACT_BLOCK_PATTERN,
    DERIVED_ENV_TAG_PATTERN,
    build_derived_env_frame_anchor_injection,
    ingest_derived_environments_from_framing,
    rewrite_merged_derived_environment_names,
)
from app.services.script_analysis_flow.environment_reuse import (
    SCENE_ENV_IDENT_PATTERN,
    build_reused_derived_environment_injection,
    collect_episode_env_blocks_by_name,
    collect_project_main_environment_catalog,
    extract_scene_env_ident_block,
    parse_scene_env_ident_items,
)
from app.services.soft_delete import _active_episode_clause

logger = logging.getLogger("api_logger")

DRAMA_PROMPT = "skills/scene_analysis_feature_stack/scene_planning_1_subskill_drama_standardization.md"
VFX_PROMPT = "skills/scene_analysis_feature_stack/scene_planning_1_subskill_vfx.md"
XIAN_PROMPT = "skills/scene_analysis_feature_stack/scene_planning_1_subskill_xian_attack.md"
FRAMING_PROMPT = "skills/scene_analysis_feature_stack/scene_planning_1_subskill_derived_framing.md"
STAGING_PROMPT = "skills/scene_analysis_feature_stack/scene_planning_1_subskill_staging_env.md"
# Hard contract: after enhance + main-env splice, these LLM steps are serial and complete.
PIPELINE_CONTRACT_VERSION = "framing-before-staging-v3"
SCENE_SUBSKILL_POST_ENV_STEPS: Tuple[Tuple[str, str], ...] = (
    ("derived_framing", FRAMING_PROMPT),
    ("staging", STAGING_PROMPT),
)

_SUBSKILL_ACTION_LABELS = {
    DRAMA_PROMPT: "文戏增强",
    VFX_PROMPT: "特效增强",
    XIAN_PROMPT: "仙攻增强",
    FRAMING_PROMPT: "场景现场编排",
    STAGING_PROMPT: "建置与入戏",
}
_SUBSKILL_FUNCTION_NAMES = {
    DRAMA_PROMPT: "script_analysis_scene_subskill_drama",
    VFX_PROMPT: "script_analysis_scene_subskill_vfx",
    XIAN_PROMPT: "script_analysis_scene_subskill_xian",
    FRAMING_PROMPT: "script_analysis_scene_subskill_derived_framing",
    STAGING_PROMPT: "script_analysis_scene_subskill_staging",
}
_SUBSKILL_STEP_PROGRESS = {
    "drama": 12.0,
    "vfx": 28.0,
    "xian": 40.0,
    "wait_env": 48.0,
    "derived_framing": 58.0,
    "staging": 82.0,
}
_BEAT_FRAMING_PLAN_PATTERN = re.compile(r"【Beat景别构图方案】")
_BEAT_PLACEMENT_PATTERN = re.compile(r"【Beat主体定位】")
_SUBSKILL_COMPLETION_MARKERS = {
    DRAMA_PROMPT: "[DRAMA_STANDARDIZATION_OUTPUT_END]",
    VFX_PROMPT: "[VFX_SUBSKILL_OUTPUT_END]",
    XIAN_PROMPT: "[XIAN_ATTACK_OUTPUT_END]",
    FRAMING_PROMPT: "[DERIVED_FRAMING_OUTPUT_END]",
    STAGING_PROMPT: "[STAGING_ENV_OUTPUT_END]",
}
_ENV_BLOCK_WITH_COVERAGE_PATTERN = re.compile(
    r"\s*`?\[ENV_BLOCK_START(?:\:[^\]]+)?\]`?.*?"
    r"`?\[ENV_BLOCK_END(?:\:[^\]]+)?\]`?"
    r"(?:\s*【Beat→衍生ENV剧情覆盖矩阵】.*?【ENV覆盖综合】[^\r\n]*)?",
    re.IGNORECASE | re.DOTALL,
)
_ENV_PLAN_WAIT_SECONDS = 1200.0
_ENV_PLAN_POLL_SECONDS = 1.5
_SUBSKILL_START_ALIASES = {
    "drama": "drama",
    "drama_opt": "drama",
    "combat": "combat",
    "combat_opt": "combat",
    "vfx": "combat",
    "xian": "combat",
    "framing": "framing",
    "framing_opt": "framing",
    "derived_framing": "framing",
    "wait_env": "framing",
    "staging": "staging",
    "staging_opt": "staging",
    "staging_env": "staging",
}


def _subskill_action_label(prompt_file: str) -> str:
    return _SUBSKILL_ACTION_LABELS.get(prompt_file, "逐场子技能")


def resolve_subskill_start_group(raw_payload: Optional[Dict[str, Any]] = None) -> str:
    payload = raw_payload if isinstance(raw_payload, dict) else {}
    raw = str(
        payload.get("start_from_step")
        or payload.get("target_subskill")
        or payload.get("subskill_group")
        or "drama"
    ).strip().lower()
    return _SUBSKILL_START_ALIASES.get(raw, "drama")


def payload_has_explicit_subskill_start(raw_payload: Optional[Dict[str, Any]] = None) -> bool:
    payload = raw_payload if isinstance(raw_payload, dict) else {}
    return bool(
        str(payload.get("start_from_step") or "").strip()
        or str(payload.get("target_subskill") or "").strip()
        or str(payload.get("subskill_group") or "").strip()
    )


@dataclass(frozen=True)
class SceneSubskillResume:
    start_group: str
    current_block: str
    called: Tuple[str, ...]
    skipped_reason: str = ""


_PERSISTED_STEP_MARKERS = {
    "drama": ("[DRAMA_STANDARDIZATION_OUTPUT_END]",),
    "combat": ("[VFX_SUBSKILL_OUTPUT_END]", "[XIAN_ATTACK_OUTPUT_END]"),
    "framing": ("[DERIVED_FRAMING_OUTPUT_END]",),
    "staging": ("[STAGING_ENV_OUTPUT_END]",),
}


def persisted_subskill_step_usable(step_key: str, text: str) -> bool:
    body = str(text or "").strip()
    if len(body) < 40:
        return False
    key = str(step_key or "").strip()
    markers = _PERSISTED_STEP_MARKERS.get(key)
    if markers and any(marker in body for marker in markers):
        return True
    # persist_scene_subskill_named_step stores the extracted scene block after
    # the completion marker is stripped. Marker-only checks would always miss.
    has_scene = bool(re.search(r"\[SCENE_START", body, re.IGNORECASE))
    if not has_scene:
        return False
    if key == "drama":
        return True
    if key == "combat":
        return True
    if key == "framing":
        return (
            "【Beat主体定位】" in body
            or "【取景锁定】" in body
            or "[DERIVED_ENV" in body
            or "【Beat景别构图方案】" in body
        )
    if key == "staging":
        return (
            "[STAGING_ENV" in body
            or "【入戏】" in body
            or "【建置】" in body
            or "入戏状态" in body
            or "出场状态" in body
            or "ENV氛围微" in body
        )
    return False


def resolve_scene_subskill_resume(
    *,
    scene_id: str,
    steps: Optional[Dict[str, str]] = None,
    pipeline_status: str = "",
    pipeline_scene_block: str = "",
    call_vfx: bool = False,
    call_xian: bool = False,
) -> SceneSubskillResume:
    """Pick the first unfinished step for one scene. Completed LLM steps are reused."""
    sid = str(scene_id or "").strip()
    scene_steps = steps if isinstance(steps, dict) else {}
    drama = str(scene_steps.get("drama") or "").strip()
    combat = str(scene_steps.get("combat") or "").strip()
    framing = str(scene_steps.get("framing") or "").strip()
    staging = str(scene_steps.get("staging") or "").strip()
    status = str(pipeline_status or "").strip().lower()
    node_block = str(pipeline_scene_block or "").strip()

    if status == "success" and (persisted_subskill_step_usable("staging", staging) or len(node_block) >= 40):
        return SceneSubskillResume(
            start_group="done",
            current_block=staging or node_block,
            called=("drama", "derived_framing", "staging"),
            skipped_reason="pipeline_success",
        )
    if persisted_subskill_step_usable("staging", staging):
        return SceneSubskillResume(
            start_group="done",
            current_block=staging,
            called=("drama", "derived_framing", "staging"),
            skipped_reason="staging_persisted",
        )

    framing_ready = persisted_subskill_step_usable("framing", framing)
    if framing_ready:
        try:
            framing = assert_derived_framing_ready_for_staging(framing, sid)
        except Exception:
            framing_ready = False
    if framing_ready:
        return SceneSubskillResume(
            start_group="staging",
            current_block=framing,
            called=("drama", "derived_framing"),
            skipped_reason="resume_staging",
        )

    needs_combat = bool(call_vfx or call_xian)
    combat_ready = persisted_subskill_step_usable("combat", combat)
    drama_ready = persisted_subskill_step_usable("drama", drama)
    if drama_ready and (combat_ready or not needs_combat):
        called = ["drama"]
        if combat_ready:
            called.append("vfx" if call_vfx else "xian")
        return SceneSubskillResume(
            start_group="framing",
            current_block=combat if combat_ready else drama,
            called=tuple(called),
            skipped_reason="resume_framing",
        )
    if drama_ready and needs_combat:
        return SceneSubskillResume(
            start_group="combat",
            current_block=drama,
            called=("drama",),
            skipped_reason="resume_combat",
        )
    return SceneSubskillResume(
        start_group="drama",
        current_block="",
        called=(),
        skipped_reason="start_drama",
    )


def _load_scene_pipeline_rows(
    db: Session,
    *,
    project_id: int,
    episode_id: int,
) -> Dict[str, Dict[str, str]]:
    if int(project_id or 0) <= 0 or int(episode_id or 0) <= 0:
        return {}
    rows = (
        db.query(ScriptProgressPipelineNode)
        .filter(
            ScriptProgressPipelineNode.project_id == int(project_id),
            ScriptProgressPipelineNode.episode_id == int(episode_id),
            ScriptProgressPipelineNode.node_name == "scene_subskill_scene",
        )
        .all()
    )
    out: Dict[str, Dict[str, str]] = {}
    for row in rows:
        sid = str(getattr(row, "scene_id", "") or "").strip()
        if not sid:
            continue
        meta = getattr(row, "runtime_meta", None)
        if not isinstance(meta, dict):
            meta = {}
        out[sid] = {
            "status": str(getattr(row, "status", "") or "").strip().lower(),
            "scene_block": str(meta.get("scene_block") or ""),
        }
        out[sid.lower()] = out[sid]
    return out


def _lookup_scene_pipeline_row(
    rows: Dict[str, Dict[str, str]],
    scene_id: str,
) -> Dict[str, str]:
    sid = str(scene_id or "").strip()
    if not sid:
        return {}
    return rows.get(sid) or rows.get(sid.lower()) or {}


def _task_matches_target_scene(task: Dict[str, Any], target_ids: List[str]) -> bool:
    sid = str(task.get("scene_id") or "").strip().lower()
    if not sid:
        return False
    for raw in target_ids or []:
        wanted = str(raw or "").strip().lower()
        if not wanted:
            continue
        if sid == wanted:
            return True
        if sid.endswith(f"_{wanted}") or wanted.endswith(f"_{sid}"):
            return True
        sid_tail = sid.split("_")[-1]
        wanted_tail = wanted.split("_")[-1]
        if sid_tail and sid_tail == wanted_tail and sid_tail.startswith("sc"):
            return True
    return False


def filter_subskill_tasks_by_target_ids(
    tasks: List[Dict[str, Any]],
    target_ids: List[str],
) -> List[Dict[str, Any]]:
    requested = [str(item or "").strip() for item in (target_ids or []) if str(item or "").strip()]
    if not requested:
        return list(tasks or [])
    matched = [task for task in (tasks or []) if _task_matches_target_scene(task, requested)]
    return matched


def merge_scene_blocks_into_script(
    base_script: str,
    updated_items: List[Dict[str, Any]],
) -> str:
    """Replace matching Scene blocks in an existing Stage-1 script; keep other scenes."""
    updates: Dict[str, Tuple[str, str]] = {}
    for item in updated_items or []:
        sid = str(item.get("scene_id") or "").strip()
        block = str(item.get("scene_block") or "").strip()
        if sid and block:
            updates[sid.lower()] = (sid, block)
    if not updates:
        return str(base_script or "").strip()
    try:
        tasks = build_scene_subskill_task_payloads(base_script) if str(base_script or "").strip() else []
    except Exception:
        tasks = []
    if not tasks:
        parts = [SCENES_BLOCK_START_TOKEN]
        parts.extend(block for _sid, block in updates.values())
        parts.append(SCENES_BLOCK_END_TOKEN)
        return "\n".join(parts)
    comprehensive = str(tasks[0].get("comprehensive_info") or "").strip()
    project_tail = _extract_project_tail(base_script)
    used: set[str] = set()
    parts = [SCENES_BLOCK_START_TOKEN]
    if comprehensive:
        parts.append(comprehensive)
    for task in tasks:
        sid = str(task.get("scene_id") or "").strip()
        key = sid.lower()
        if key in updates:
            parts.append(updates[key][1])
            used.add(key)
        else:
            parts.append(str(task.get("scene_block") or "").strip())
    for key, (_sid, block) in updates.items():
        if key not in used:
            parts.append(block)
    parts.append(SCENES_BLOCK_END_TOKEN)
    if project_tail:
        parts.append(project_tail)
    return "\n".join(part for part in parts if part)


_FRAMING_LOCK_HEADING = "【取景锁定】"
_FRAMING_LOCK_REQUIRED_FIELDS = ("当前环境=", "景别=", "构图=", "镜头角度=")
_FRAMING_EVIDENCE_FIELD = "选择证据="


def _iter_beat_bodies(source: str) -> List[Tuple[str, str]]:
    text = str(source or "")
    starts = list(_BEAT_START_RE.finditer(text))
    bodies: List[Tuple[str, str]] = []
    for idx, start_match in enumerate(starts):
        beat_id = str(start_match.group(1) or idx + 1).strip() or str(idx + 1)
        next_start = starts[idx + 1].start() if idx + 1 < len(starts) else len(text)
        end_match = _BEAT_END_RE.search(text, start_match.end())
        if end_match and end_match.start() <= next_start:
            body = text[start_match.end() : end_match.start()]
        else:
            body = text[start_match.end() : next_start]
        bodies.append((beat_id, body))
    return bodies


def _beat_has_framing_lock(body: str) -> bool:
    text = str(body or "")
    if _FRAMING_LOCK_HEADING not in text:
        return False
    compact = text.replace(" ", "")
    return all(field in compact for field in _FRAMING_LOCK_REQUIRED_FIELDS) and (
        _FRAMING_EVIDENCE_FIELD in compact
    )


def assert_derived_framing_ready_for_staging(text: str, scene_id: str = "") -> str:
    """Hard gate: staging must not start unless framing output is extractable."""
    source = rewrite_merged_derived_environment_names(str(text or "")).strip()
    sid = str(scene_id or "").strip()
    if not source:
        raise HTTPException(status_code=422, detail=f"STAGING_BLOCKED_FRAMING_EMPTY:{sid}")
    has_plan = bool(
        _BEAT_PLACEMENT_PATTERN.search(source)
        or _FRAMING_LOCK_HEADING in source
        or _BEAT_FRAMING_PLAN_PATTERN.search(source)
    )
    has_extract = bool(
        DERIVED_ENV_EXTRACT_BLOCK_PATTERN.search(source) or DERIVED_ENV_TAG_PATTERN.search(source)
    )
    if not has_plan or not has_extract:
        raise HTTPException(
            status_code=422,
            detail=f"STAGING_BLOCKED_FRAMING_INCOMPLETE:{sid}",
        )
    missing_locks = [
        beat_id
        for beat_id, body in _iter_beat_bodies(source)
        if not _beat_has_framing_lock(body)
    ]
    if missing_locks:
        raise HTTPException(
            status_code=422,
            detail=f"STAGING_BLOCKED_FRAMING_BEAT_LOCK:{sid}:{','.join(missing_locks)}",
        )
    if re.search(
        r"\[DERIVED_ENV:(?:Beat|文戏|原文)\s*[:：]|\[DERIVED_ENV:\d+\s*deg|当前环境=(?:Beat|文戏|原文)\s*[:：]",
        source,
        re.IGNORECASE,
    ):
        raise HTTPException(
            status_code=422,
            detail=f"STAGING_BLOCKED_ILLEGAL_DERIVED_ENV:{sid}",
        )
    return source


def _mark_scene_subskill_step(
    task_db: Session,
    *,
    project_id: int,
    episode_id: int,
    scene_id: str,
    step_name: str,
    step_label: str,
    status: str = "running",
    progress_percent: Optional[float] = None,
    extra_meta: Optional[Dict[str, Any]] = None,
) -> None:
    if int(project_id or 0) <= 0 or int(episode_id or 0) <= 0:
        return
    meta = {
        "business_event": "step",
        "current_step": step_name,
        "current_step_label": step_label,
    }
    if extra_meta:
        meta.update(extra_meta)
    upsert_pipeline_node_status(
        task_db,
        project_id=int(project_id),
        episode_id=int(episode_id),
        script_id=f"episode:{episode_id}",
        node_name="scene_subskill_scene",
        scene_id=str(scene_id or ""),
        status=status,
        progress_percent=float(
            progress_percent
            if progress_percent is not None
            else _SUBSKILL_STEP_PROGRESS.get(step_name, 15.0)
        ),
        runtime_meta=meta,
    )
    task_db.commit()


def _slim_derived_env_ingest_meta(ingest_meta: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not ingest_meta:
        return None
    return {
        "group_count": ingest_meta.get("group_count"),
        "created": ingest_meta.get("created"),
        "updated": ingest_meta.get("updated"),
        "kept": ingest_meta.get("kept"),
        "entity_ids": list(ingest_meta.get("entity_ids") or []),
    }


def _ingest_derived_environments_after_framing(
    db: Session,
    *,
    project_id: int,
    episode_id: int,
    scene_text: str,
    scene_id: str = "",
    phase: str = "after_framing",
) -> Optional[Dict[str, Any]]:
    """Extract derived ENV + write crop prompts into the asset library as soon as framing is valid."""
    if int(project_id or 0) <= 0 or int(episode_id or 0) <= 0:
        return None
    try:
        ingest_meta = ingest_derived_environments_from_framing(
            db=db,
            project_id=int(project_id),
            episode_id=int(episode_id),
            scene_text=scene_text,
        )
        logger.info(
            "[scene_subskill_pipeline] derived env ingest phase=%s scene=%s mains=%s created=%s updated=%s episode_id=%s",
            phase,
            scene_id or "-",
            ingest_meta.get("group_count"),
            ingest_meta.get("created"),
            ingest_meta.get("updated"),
            episode_id,
        )
        return ingest_meta
    except Exception as ingest_exc:
        logger.warning(
            "[scene_subskill_pipeline] derived env ingest failed phase=%s scene=%s episode_id=%s err=%s",
            phase,
            scene_id or "-",
            episode_id,
            ingest_exc,
        )
        return None


def is_timeout_like_error(exc: Any) -> bool:
    if isinstance(exc, TimeoutError):
        return True
    text = str(exc or "").lower()
    return (
        "timed out" in text
        or "timeout" in text
        or "read timeout" in text
        or "wall-clock" in text
    )


def _scene_subskill_failure_reason(exc: Exception) -> str:
    text = str(exc or "")
    if is_timeout_like_error(exc):
        return "节点超时，已标记失败并将自动补跑"
    if "COMPLETION_MARKER_MISSING" in text:
        return "子技能输出不完整，自动重试后仍缺少结束标签"
    if "OUTPUT_PARSE_FAILED" in text:
        if "SCENE_MARKER_BLOCK_MISSING" in text:
            return "子技能只返回了环境矩阵等片段，缺少场景分割符"
        return "子技能返回的场景结构无法解析"
    if "OUTPUT_SCENE_MISMATCH" in text:
        return "子技能返回了错误的场景编号"
    if "STAGING_BLOCKED_FRAMING" in text:
        return "场景现场编排未完成，不能进入建置与入戏"
    if "ROUTING_MISSING" in text:
        return "文戏增强未产出特效宽松评估"
    if "NO_SCENES" in text:
        return "未解析到可执行的场景"
    return "逐场子技能执行失败"


def _completion_marker_pattern(marker: str):
    return re.compile(rf"`?{re.escape(marker)}`?", re.IGNORECASE)


def _strip_subskill_completion_marker(text: str, prompt_file: str) -> str:
    marker = _SUBSKILL_COMPLETION_MARKERS[prompt_file]
    source = str(text or "").replace("\r\n", "\n").strip()
    if not source:
        return ""
    matches = list(_completion_marker_pattern(marker).finditer(source))
    if not matches:
        return ""
    return source[: matches[-1].start()].rstrip()


def _try_extract_subskill_scene_block(
    result_text: str,
    scene_id: str,
    fallback_special: str,
    previous_block: str = "",
) -> str:
    try:
        return _extract_single_scene_block(
            result_text,
            scene_id,
            fallback_special,
            previous_block=previous_block,
        )
    except HTTPException:
        return ""


def _extract_project_tail(script_text: str) -> str:
    source = str(script_text or "").strip()
    match = re.search(r"`?\[SCENES_BLOCK_END\]`?", source, flags=re.IGNORECASE)
    if not match:
        return ""
    return source[match.end():].strip()


def _wrap_single_scene_input(
    scene_block: str,
    comprehensive_info: str,
    project_tail: str,
    entity_token_brief: str = "",
) -> str:
    parts = [SCENES_BLOCK_START_TOKEN]
    if str(entity_token_brief or "").strip():
        parts.append(str(entity_token_brief).strip())
    if str(comprehensive_info or "").strip():
        parts.append(str(comprehensive_info).strip())
    parts.append(str(scene_block or "").strip())
    parts.append(SCENES_BLOCK_END_TOKEN)
    if str(project_tail or "").strip():
        parts.append(str(project_tail).strip())
    return "\n".join(part for part in parts if part)


def _with_derived_env_frame_anchors(scene_input: str, scene_block: str) -> str:
    anchor_block = build_derived_env_frame_anchor_injection(scene_block)
    if not anchor_block:
        return scene_input
    return f"{anchor_block}\n\n{scene_input}"


_BEAT_STREAM_START_RE = re.compile(r"`?\[BEAT_STREAM_START\]`?", re.IGNORECASE)
_BEAT_STREAM_END_RE = re.compile(r"`?\[BEAT_STREAM_END\]`?", re.IGNORECASE)
_BEAT_START_RE = re.compile(r"`?\[BEAT_START:([^\s\]]+)\]`?", re.IGNORECASE)
_BEAT_END_RE = re.compile(r"`?\[BEAT_END:([^\s\]]+)\]`?", re.IGNORECASE)
_STAGING_SECTION_HEADINGS = (
    "【实体覆盖】",
    "【位置规划综合】",
    "【角色位置】",
    "【未落实体位置】",
    "【观察视角与空间建置】",
    "【动作空间综合】",
    "【露脸冲突】",
)


def _has_recoverable_beat_body(text: str) -> bool:
    source = str(text or "")
    if _BEAT_STREAM_START_RE.search(source) and _BEAT_STREAM_END_RE.search(source):
        return bool(_BEAT_START_RE.search(source))
    return bool(_BEAT_START_RE.search(source) and _BEAT_END_RE.search(source))


def _split_header_and_beats(text: str) -> tuple[str, str]:
    source = str(text or "").replace("\r\n", "\n")
    stream = _BEAT_STREAM_START_RE.search(source)
    if stream:
        return source[: stream.start()].rstrip(), source[stream.start() :].strip()
    beat = _BEAT_START_RE.search(source)
    if beat:
        return source[: beat.start()].rstrip(), source[beat.start() :].strip()
    return source.strip(), ""


def _is_staging_section_heading(line: str) -> bool:
    stripped = str(line or "").strip()
    return any(stripped == heading or stripped.startswith(heading) for heading in _STAGING_SECTION_HEADINGS)


def _strip_staging_sections(header: str) -> str:
    kept: List[str] = []
    skipping = False
    for line in str(header or "").replace("\r\n", "\n").splitlines():
        stripped = line.strip()
        if _is_staging_section_heading(stripped):
            skipping = True
            continue
        if skipping:
            if stripped.startswith("[") or (
                stripped.startswith("【") and not _is_staging_section_heading(stripped)
            ):
                skipping = False
                kept.append(line)
            continue
        kept.append(line)
    return "\n".join(kept).strip()


def _wrap_recovered_scene(scene_id: str, scene_text: str) -> str:
    return "\n".join(
        (
            SCENES_BLOCK_START_TOKEN,
            f"[SCENE_START:{scene_id}]",
            str(scene_text or "").strip(),
            f"[SCENE_END:{scene_id}]",
            SCENES_BLOCK_END_TOKEN,
        )
    )


def _previous_scene_text(previous_block: str, scene_id: str) -> str:
    source = str(previous_block or "").strip()
    if not source:
        return ""
    sanitized = SPECIAL_SCENE_ANALYSIS_PATTERN.sub("", source)
    sanitized = COMPREHENSIVE_INFO_PATTERN.sub("", sanitized).strip()
    if not sanitized:
        return ""
    try:
        units = parse_scene_units_from_markers(sanitized)
    except SceneMarkerParseError:
        return ""
    matches = [unit for unit in units if str(unit.scene_id).lower() == str(scene_id).lower()]
    if len(matches) != 1:
        return ""
    return str(matches[0].scene_text or "").strip()


def _recover_markerless_scene_fragment(
    fragment: str,
    scene_id: str,
    previous_block: str,
) -> str:
    source = str(fragment or "").strip()
    if not _has_recoverable_beat_body(source):
        return ""
    new_header, new_beats = _split_header_and_beats(source)
    if not new_beats:
        return ""
    previous_scene_text = _previous_scene_text(previous_block, scene_id)
    if previous_scene_text:
        old_header, _old_beats = _split_header_and_beats(previous_scene_text)
        merged = "\n\n".join(
            part
            for part in (
                _strip_staging_sections(old_header),
                new_header,
                new_beats,
            )
            if str(part or "").strip()
        )
        logger.info(
            "[scene_subskill_pipeline] recovered markerless scene=%s via previous header",
            scene_id,
        )
        return _wrap_recovered_scene(scene_id, merged)
    logger.info(
        "[scene_subskill_pipeline] recovered markerless scene=%s via wrap",
        scene_id,
    )
    return _wrap_recovered_scene(scene_id, source)


def _special_block_from_text(text: str, scene_id: str) -> str:
    try:
        parsed = parse_special_scene_analysis_blocks(text)
    except SceneMarkerParseError:
        return ""
    sid = str(scene_id or "").strip().lower()
    for key, value in parsed.items():
        if str(key).strip().lower() == sid:
            return str(value.get("block_text") or "").strip()
    return ""


def _routes_from_special_text(special: str, scene_id: str) -> Tuple[bool, bool]:
    try:
        parsed = parse_special_scene_analysis_blocks(special)
    except SceneMarkerParseError:
        return False, False
    sid = str(scene_id or "").strip().lower()
    routes: Dict[str, Any] = {}
    for key, value in parsed.items():
        if str(key).strip().lower() == sid:
            routes = dict(value.get("routes") or {})
            break
    if not routes and parsed:
        routes = dict(next(iter(parsed.values())).get("routes") or {})
    return bool((routes.get("VFX") or {}).get("hit")), bool((routes.get("XIAN") or {}).get("hit"))


def _extract_single_scene_block(
    result_text: str,
    scene_id: str,
    fallback_special: str,
    previous_block: str = "",
) -> str:
    text = str(result_text or "").strip()
    # COMPREHENSIVE_INFO is read-only global metadata and must not stay in the
    # per-scene block. SPECIAL_SCENE_ANALYSIS is authoritative from fallback
    # (VFX/XIAN after 文戏增强) or, when fallback is empty, from this output
    # (文戏增强 newly wrote the loose VFX/XIAN routing).
    sanitized_text = SPECIAL_SCENE_ANALYSIS_PATTERN.sub("", text)
    sanitized_text = COMPREHENSIVE_INFO_PATTERN.sub("", sanitized_text)
    sanitized_text = strip_injection_section(sanitized_text, "本场角色道具白名单")
    try:
        units = parse_scene_units_from_markers(sanitized_text)
    except SceneMarkerParseError as exc:
        recovered = _recover_markerless_scene_fragment(
            sanitized_text,
            scene_id,
            previous_block,
        )
        if not recovered:
            raise HTTPException(
                status_code=422,
                detail=f"SCENE_SUBSKILL_OUTPUT_PARSE_FAILED:{scene_id}:{exc.code}",
            ) from exc
        try:
            units = parse_scene_units_from_markers(recovered)
        except SceneMarkerParseError as recover_exc:
            raise HTTPException(
                status_code=422,
                detail=f"SCENE_SUBSKILL_OUTPUT_PARSE_FAILED:{scene_id}:{recover_exc.code}",
            ) from recover_exc
    matches = [unit for unit in units if str(unit.scene_id).lower() == str(scene_id).lower()]
    if len(matches) != 1:
        raise HTTPException(
            status_code=422,
            detail=f"SCENE_SUBSKILL_OUTPUT_SCENE_MISMATCH:{scene_id}",
        )
    unit = matches[0]
    special = str(fallback_special or "").strip() or _special_block_from_text(text, scene_id)
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


def script_has_environment_blocks(script_text: str) -> bool:
    return "[ENV_BLOCK_START]" in str(script_text or "").upper()


def environment_plan_ready_for_framing(status: str, persisted_text: str) -> bool:
    """Framing may start only after this run's environment_plan node succeeded."""
    return str(status or "").strip().lower() in {"success", "warning"} and script_has_environment_blocks(
        persisted_text
    )


def extract_environment_planning_sections(scene_text: str) -> str:
    source = str(scene_text or "")
    ident = extract_scene_env_ident_block(source)
    match = _ENV_BLOCK_WITH_COVERAGE_PATTERN.search(source)
    env = str(match.group(0) or "").strip() if match else extract_env_block_from_scene_text(source).strip()
    return "\n".join(part for part in (ident, env) if str(part or "").strip())


def strip_environment_planning_sections(scene_text: str) -> str:
    stripped = SCENE_ENV_IDENT_PATTERN.sub("", str(scene_text or ""))
    stripped = _ENV_BLOCK_WITH_COVERAGE_PATTERN.sub("", stripped)
    stripped = re.sub(
        r"`?\[ENV_BLOCK_START(?:\:[^\]]+)?\]`?.*?"
        r"`?\[ENV_BLOCK_END(?:\:[^\]]+)?\]`?",
        "",
        stripped,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return re.sub(r"\n{3,}", "\n\n", stripped).strip()


def splice_environment_and_enhance_scene(
    scene_id: str,
    env_scene_block: str,
    enhance_scene_block: str,
    special_analysis: str = "",
) -> str:
    """Join env-plan main-env sections with drama/VFX/Xian output for framing."""
    sid = str(scene_id or "").strip()
    env_sections = extract_environment_planning_sections(env_scene_block)
    if not env_sections:
        raise HTTPException(status_code=422, detail=f"STAGING_ENV_SCENE_MISSING:{sid}")
    enhance = strip_environment_planning_sections(enhance_scene_block)
    if not enhance:
        raise HTTPException(status_code=422, detail=f"STAGING_ENHANCE_SCENE_MISSING:{sid}")

    content_marker = re.search(
        rf"`?\[SCENE_CONTENT_START:{re.escape(sid)}\]`?",
        enhance,
        flags=re.IGNORECASE,
    )
    ident_end = re.search(
        rf"`?\[SCENE_ENV_IDENT_END:{re.escape(sid)}\]`?",
        enhance,
        flags=re.IGNORECASE,
    )
    name_line = re.search(r"^【场景名称】[^\n]*\n?", enhance, flags=re.MULTILINE)
    scene_start = re.search(
        rf"`?\[SCENE_START:{re.escape(sid)}\]`?",
        enhance,
        flags=re.IGNORECASE,
    )
    if content_marker:
        spliced = (
            f"{enhance[:content_marker.start()].rstrip()}\n"
            f"{env_sections}\n"
            f"{enhance[content_marker.start():].lstrip()}"
        )
    elif ident_end:
        spliced = (
            f"{enhance[:ident_end.end()]}\n"
            f"{env_sections}\n"
            f"{enhance[ident_end.end():].lstrip()}"
        )
    elif name_line:
        spliced = (
            f"{enhance[:name_line.end()].rstrip()}\n"
            f"{env_sections}\n"
            f"{enhance[name_line.end():].lstrip()}"
        )
    elif scene_start:
        spliced = (
            f"{enhance[:scene_start.end()]}\n"
            f"{env_sections}\n"
            f"{enhance[scene_start.end():].lstrip()}"
        )
    else:
        spliced = f"{env_sections}\n\n{enhance}"

    special = str(special_analysis or "").strip()
    if special and special not in spliced:
        spliced = f"{special}\n{spliced}"
    return spliced.strip()


def _scene_block_from_script(script_text: str, scene_id: str) -> str:
    sid = str(scene_id or "").strip().lower()
    if not sid:
        return ""
    try:
        for task in build_scene_subskill_task_payloads(script_text):
            if str(task.get("scene_id") or "").strip().lower() == sid:
                return str(task.get("scene_block") or "").strip()
    except Exception:
        return ""
    return ""


def load_environment_planned_script(db: Session, episode_id: int) -> str:
    if int(episode_id or 0) <= 0:
        return ""
    episode = (
        db.query(Episode)
        .filter(Episode.id == int(episode_id), _active_episode_clause())
        .first()
    )
    if episode is None:
        return ""
    raw = str(getattr(episode, "ai_stage_outputs", "") or "").strip()
    try:
        obj = json.loads(raw) if raw else {}
        node = (
            ((obj.get("stages") or {}).get("stage1") or {}).get("outputs") or {}
        ).get("environment_plan")
        content = str((node or {}).get("content") or "") if isinstance(node, dict) else ""
        if script_has_environment_blocks(content):
            return content.strip()
    except Exception:
        pass
    adaptation = str(getattr(episode, "ai_scene_analysis_adaptation", "") or "")
    if script_has_environment_blocks(adaptation):
        return adaptation.strip()
    return ""


def _environment_plan_node_status(db: Session, episode_id: int) -> str:
    from app.models.all_models import ScriptProgressPipelineNode

    row = (
        db.query(ScriptProgressPipelineNode)
        .filter(
            ScriptProgressPipelineNode.episode_id == int(episode_id),
            ScriptProgressPipelineNode.node_name == "environment_plan",
            ScriptProgressPipelineNode.scene_id.is_(None),
        )
        .first()
    )
    return str(getattr(row, "status", "") or "").strip().lower()


async def await_environment_planned_script(
    *,
    episode_id: int,
    explicit_text: str = "",
    fallback_text: str = "",
    timeout_seconds: float = _ENV_PLAN_WAIT_SECONDS,
) -> str:
    """Wait for the environment_plan node of this episode, then return its merged script.

    Scene-split leftovers and previous-run adaptation must not unlock framing.
    ``fallback_text`` is ignored for readiness; it is kept only for call-site compat.
    """
    del fallback_text
    explicit = str(explicit_text or "").strip()
    if int(episode_id or 0) <= 0:
        if script_has_environment_blocks(explicit):
            return explicit
        raise HTTPException(status_code=422, detail="STAGING_ENVIRONMENT_PLAN_MISSING")

    deadline = time.monotonic() + float(timeout_seconds)
    last_status = ""
    logger.info(
        "[scene_subskill_pipeline] waiting for environment_plan before framing episode_id=%s",
        episode_id,
    )
    while time.monotonic() < deadline:
        poll_db = SessionLocal()
        try:
            last_status = _environment_plan_node_status(poll_db, int(episode_id))
            if last_status in {"failed", "blocked"}:
                raise HTTPException(
                    status_code=422,
                    detail=f"STAGING_ENVIRONMENT_PLAN_FAILED:{last_status}",
                )
            persisted = load_environment_planned_script(poll_db, int(episode_id))
            if last_status in {"success", "warning"} and script_has_environment_blocks(explicit):
                logger.info(
                    "[scene_subskill_pipeline] environment_plan ready via explicit text episode_id=%s status=%s",
                    episode_id,
                    last_status,
                )
                return explicit
            if environment_plan_ready_for_framing(last_status, persisted):
                logger.info(
                    "[scene_subskill_pipeline] environment_plan ready for framing episode_id=%s status=%s",
                    episode_id,
                    last_status,
                )
                return persisted
        finally:
            _release_db_connection(poll_db)
        await asyncio.sleep(_ENV_PLAN_POLL_SECONDS)
    raise HTTPException(
        status_code=422,
        detail=f"STAGING_ENVIRONMENT_PLAN_TIMEOUT:{last_status or 'pending'}",
    )


def _subskill_parse_failure_code(exc: HTTPException) -> str:
    detail = str(getattr(exc, "detail", "") or "")
    if "OUTPUT_PARSE_FAILED" in detail or "OUTPUT_SCENE_MISMATCH" in detail:
        return detail.split(":", 1)[0]
    return ""


def _clean_subskill_llm_config(raw: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    cleaned = dict(raw)
    cfg = dict(cleaned.get("config") or {}) if isinstance(cleaned.get("config"), dict) else {}
    cfg.pop("__resolved_action", None)
    cleaned["config"] = cfg
    return cleaned


def _build_subskill_request(
    base_payload: Dict[str, Any],
    *,
    prompt_file: str,
    scene_input: str,
    scene_id: str,
    system_api_id: Any = None,
) -> AnalyzeSceneRequest:
    """Build a fresh request so parent node prompt/action cannot leak into this step."""
    action_name = f"{_subskill_action_label(prompt_file)} · {scene_id}"
    return AnalyzeSceneRequest(
        text=scene_input,
        project_id=base_payload.get("project_id"),
        episode_id=base_payload.get("episode_id"),
        llm_config=_clean_subskill_llm_config(base_payload.get("llm_config")),
        prompt_file=prompt_file,
        system_prompt=None,
        project_metadata=base_payload.get("project_metadata"),
        scene_analysis_mode="classic",
        scene_analysis_features=None,
        analysis_attention_notes=base_payload.get("analysis_attention_notes"),
        reuse_subject_assets=base_payload.get("reuse_subject_assets"),
        include_negative_prompt=True,
        function_name=_SUBSKILL_FUNCTION_NAMES.get(prompt_file, "script_analysis_scene_subskill"),
        system_api_id=system_api_id if system_api_id is not None else base_payload.get("system_api_id"),
        action_name=action_name,
        analysis_trace_id=base_payload.get("analysis_trace_id"),
        skip_episode_persist=True,
        subject_index_text=base_payload.get("subject_index_text"),
    )


async def _call_scene_subskill(
    *,
    task_db: Session,
    current_user: User,
    base_payload: Dict[str, Any],
    prompt_file: str,
    scene_input: str,
    scene_id: str,
    fallback_special: str = "",
    previous_block: str = "",
) -> str:
    from app.api.routers.prompts.analyze_scene import analyze_scene  # noqa: WPS433
    from app.services.script_analysis_flow_runner import build_script_analysis_retry_api_attempts

    _original_api_id, api_attempts = build_script_analysis_retry_api_attempts(
        task_db,
        base_payload.get("function_name") or "script_analysis",
        base_payload.get("system_api_id"),
        node_key="scene_subskill",
    )
    completion_marker = _SUBSKILL_COMPLETION_MARKERS[prompt_file]
    max_attempts = len(api_attempts)
    logger.info(
        "[scene_subskill_pipeline] llm_step contract=%s prompt=%s scene=%s attempts=%s",
        PIPELINE_CONTRACT_VERSION,
        prompt_file,
        scene_id,
        max_attempts,
    )
    for attempt, api_id in enumerate(api_attempts, start=1):
        request = _build_subskill_request(
            base_payload,
            prompt_file=prompt_file,
            scene_input=scene_input,
            scene_id=scene_id,
            system_api_id=api_id or base_payload.get("system_api_id"),
        )
        try:
            result = await analyze_scene(
                request,
                current_user=current_user,
                db=task_db,
                async_mode="0",
            )
        except Exception as call_exc:
            if is_timeout_like_error(call_exc) and attempt < max_attempts:
                logger.warning(
                    "[scene_subskill_pipeline] timeout retry scene=%s prompt=%s attempt=%s/%s err=%s",
                    scene_id,
                    prompt_file,
                    attempt,
                    max_attempts,
                    call_exc,
                )
                project_id = int(base_payload.get("project_id") or 0)
                episode_id = int(base_payload.get("episode_id") or 0)
                if project_id > 0 and episode_id > 0:
                    upsert_pipeline_node_status(
                        task_db,
                        project_id=project_id,
                        episode_id=episode_id,
                        script_id=f"episode:{episode_id}",
                        node_name="scene_subskill_scene",
                        scene_id=scene_id,
                        status="running",
                        progress_percent=15.0,
                        retry_count=attempt,
                        runtime_meta={
                            "business_event": "retry",
                            "business_reason": f"{_subskill_action_label(prompt_file)}超时，正在重试",
                            "current_step_label": _subskill_action_label(prompt_file),
                        },
                        error_code="SCENE_SUBSKILL_TIMEOUT",
                        error_message=str(call_exc),
                    )
                    task_db.commit()
                continue
            raise
        text = _extract_analysis_text_from_result(result).strip()
        stripped = _strip_subskill_completion_marker(text, prompt_file) if text else ""
        candidate = stripped or text
        extracted = (
            _try_extract_subskill_scene_block(
                candidate,
                scene_id,
                fallback_special,
                previous_block=previous_block,
            )
            if candidate
            else ""
        )
        require_marker = prompt_file in {FRAMING_PROMPT, STAGING_PROMPT}
        if extracted and (stripped or not require_marker):
            if not stripped:
                logger.warning(
                    "[scene_subskill_pipeline] accepted complete scene without end marker scene=%s prompt=%s",
                    scene_id,
                    prompt_file,
                )
            return extracted
        if not text:
            failure_code = "SCENE_SUBSKILL_EMPTY_OUTPUT"
        elif not stripped:
            failure_code = "SCENE_SUBSKILL_COMPLETION_MARKER_MISSING"
        else:
            try:
                _extract_single_scene_block(
                    stripped,
                    scene_id,
                    fallback_special,
                    previous_block=previous_block,
                )
            except HTTPException as parse_exc:
                failure_code = _subskill_parse_failure_code(parse_exc)
                if not failure_code:
                    raise
            else:
                failure_code = "SCENE_SUBSKILL_OUTPUT_INVALID"
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
                    "business_reason": f"{_subskill_action_label(prompt_file)}返回不完整",
                    "scene_id": scene_id,
                },
                error_code=failure_code,
                error_message=f"{completion_marker} missing; retrying scene subskill",
            )
            task_db.commit()
        if attempt >= max_attempts:
            if previous_block and prompt_file == STAGING_PROMPT:
                try:
                    assert_derived_framing_ready_for_staging(previous_block, scene_id)
                except HTTPException:
                    logger.warning(
                        "[scene_subskill_pipeline] refused staging fallback without framing scene=%s code=%s",
                        scene_id,
                        failure_code,
                    )
                else:
                    fallback = _try_extract_subskill_scene_block(
                        previous_block,
                        scene_id,
                        fallback_special,
                        previous_block=previous_block,
                    )
                    if fallback:
                        logger.warning(
                            "[scene_subskill_pipeline] staging fell back to previous scene block scene=%s code=%s",
                            scene_id,
                            failure_code,
                        )
                        return fallback
            raise HTTPException(
                status_code=422,
                detail=f"{failure_code}:{scene_id}:{completion_marker}",
            )
    raise HTTPException(status_code=422, detail=f"SCENE_SUBSKILL_OUTPUT_INVALID:{scene_id}")


async def _run_derived_framing_then_staging(
    *,
    task_db: Session,
    user_principal: User,
    raw_payload: Dict[str, Any],
    project_id: int,
    episode_id: int,
    scene_id: str,
    special: str,
    comprehensive_info: str,
    project_tail: str,
    env_script: str,
    env_scene: str,
    enhance_block: str,
    env_catalog: List[Dict[str, Any]],
    called: List[str],
    skip_framing: bool = False,
    entity_token_brief: str = "",
) -> str:
    """Framing LLM must succeed before staging LLM is allowed to start."""
    if skip_framing:
        current_block = assert_derived_framing_ready_for_staging(enhance_block, scene_id)
        if "derived_framing" not in called:
            called.append("derived_framing")
        current_input = _with_derived_env_frame_anchors(
            _wrap_single_scene_input(
                current_block,
                comprehensive_info,
                project_tail,
                entity_token_brief,
            ),
            current_block,
        )
        prompt_file = STAGING_PROMPT
        _mark_scene_subskill_step(
            task_db,
            project_id=project_id,
            episode_id=episode_id,
            scene_id=scene_id,
            step_name="staging",
            step_label=_subskill_action_label(prompt_file),
        )
        logger.info(
            "[scene_subskill_pipeline] start staging scene=%s contract=%s skip_framing=1",
            scene_id,
            PIPELINE_CONTRACT_VERSION,
        )
        current_block = await _call_scene_subskill(
            task_db=task_db,
            current_user=user_principal,
            base_payload=raw_payload,
            prompt_file=prompt_file,
            scene_input=current_input,
            scene_id=scene_id,
            fallback_special=special,
            previous_block=current_block,
        )
        called.append("staging")
        persist_scene_subskill_named_step(
            db=task_db,
            episode_id=episode_id,
            scene_id=scene_id,
            step_name="staging",
            result_text=current_block,
        )
        return current_block

    framing_block = splice_environment_and_enhance_scene(
        scene_id,
        env_scene,
        enhance_block,
        special,
    )
    episode_env_blocks = collect_episode_env_blocks_by_name(env_script)
    ident_items = parse_scene_env_ident_items(env_scene or framing_block, scene_id)
    derived_block = build_reused_derived_environment_injection(
        ident_items,
        env_catalog,
        episode_env_blocks=episode_env_blocks,
    )
    framing_input = _wrap_single_scene_input(
        framing_block,
        comprehensive_info,
        project_tail,
        entity_token_brief,
    )
    if derived_block:
        framing_input = f"{derived_block}\n\n{framing_input}"
    first_step, first_prompt = SCENE_SUBSKILL_POST_ENV_STEPS[0]
    if first_step != "derived_framing" or first_prompt != FRAMING_PROMPT:
        raise HTTPException(status_code=500, detail="SCENE_SUBSKILL_CONTRACT_INVALID")
    current_block = framing_block
    current_input = framing_input
    for step_name, prompt_file in SCENE_SUBSKILL_POST_ENV_STEPS:
        if step_name == "staging" and "derived_framing" not in called:
            raise HTTPException(
                status_code=422,
                detail=f"STAGING_BLOCKED_FRAMING_NOT_CALLED:{scene_id}",
            )
        if step_name == "staging":
            current_block = assert_derived_framing_ready_for_staging(current_block, scene_id)
            current_input = _with_derived_env_frame_anchors(
                _wrap_single_scene_input(
                    current_block,
                    comprehensive_info,
                    project_tail,
                    entity_token_brief,
                ),
                current_block,
            )
        _mark_scene_subskill_step(
            task_db,
            project_id=project_id,
            episode_id=episode_id,
            scene_id=scene_id,
            step_name=step_name,
            step_label=_subskill_action_label(prompt_file),
        )
        logger.info(
            "[scene_subskill_pipeline] start %s scene=%s contract=%s",
            step_name,
            scene_id,
            PIPELINE_CONTRACT_VERSION,
        )
        current_block = await _call_scene_subskill(
            task_db=task_db,
            current_user=user_principal,
            base_payload=raw_payload,
            prompt_file=prompt_file,
            scene_input=current_input,
            scene_id=scene_id,
            fallback_special=special,
            previous_block=current_block,
        )
        persist_scene_subskill_named_step(
            db=task_db,
            episode_id=episode_id,
            scene_id=scene_id,
            step_name=step_name,
            result_text=current_block,
        )
        if step_name == "derived_framing":
            current_block = assert_derived_framing_ready_for_staging(current_block, scene_id)
            ingest_meta = _ingest_derived_environments_after_framing(
                task_db,
                project_id=project_id,
                episode_id=episode_id,
                scene_text=current_block,
                scene_id=scene_id,
            )
            if ingest_meta:
                _mark_scene_subskill_step(
                    task_db,
                    project_id=project_id,
                    episode_id=episode_id,
                    scene_id=scene_id,
                    step_name=step_name,
                    step_label=_subskill_action_label(FRAMING_PROMPT),
                    extra_meta={"derived_env_ingest": _slim_derived_env_ingest_meta(ingest_meta)},
                )
            current_input = _with_derived_env_frame_anchors(
                _wrap_single_scene_input(
                    current_block,
                    comprehensive_info,
                    project_tail,
                    entity_token_brief,
                ),
                current_block,
            )
        called.append(step_name)
    return current_block


async def run_scene_subskill_pipeline(
    *,
    raw_payload: Dict[str, Any],
    current_user: User,
    db: Session,
    node_episode_id: int,
) -> Dict[str, Any]:
    """Drama/VFX/Xian from scene-split; framing then staging after main-env splice."""
    script_text = str(raw_payload.get("text") or "").strip()
    start_group = resolve_subskill_start_group(raw_payload)
    explicit_start = payload_has_explicit_subskill_start(raw_payload)
    target_scene_ids = coerce_target_scene_ids_for_orchestration(raw_payload, script_text)
    logger.warning(
        "[scene_subskill_pipeline] start contract=%s post_env_steps=%s start_from=%s explicit=%s targets=%s",
        PIPELINE_CONTRACT_VERSION,
        [step for step, _ in SCENE_SUBSKILL_POST_ENV_STEPS],
        start_group,
        explicit_start,
        target_scene_ids,
    )
    tasks = build_scene_subskill_task_payloads(script_text)
    if not tasks:
        raise HTTPException(status_code=422, detail="SCENE_SUBSKILL_NO_SCENES")
    if target_scene_ids:
        tasks = filter_subskill_tasks_by_target_ids(tasks, target_scene_ids)
        if not tasks:
            raise HTTPException(
                status_code=422,
                detail=f"SCENE_SUBSKILL_TARGET_SCENE_NOT_FOUND:{','.join(target_scene_ids)}",
            )
    max_concurrency = resolve_user_batch_parallel_limit(
        getattr(current_user, "is_active", USER_ACTIVE_LEVEL_DEFAULT),
    )
    project_id = int(raw_payload.get("project_id") or 0)
    persist_map: Dict[str, Dict[str, str]] = {}
    pipeline_rows: Dict[str, Dict[str, str]] = {}
    if not explicit_start and node_episode_id > 0:
        persist_map = load_scene_subskill_results_map(db, node_episode_id)
        pipeline_rows = _load_scene_pipeline_rows(
            db,
            project_id=project_id,
            episode_id=node_episode_id,
        )
    resume_plans: Dict[str, SceneSubskillResume] = {}
    if not explicit_start:
        for task in tasks:
            scene_id = str(task.get("scene_id") or "").strip()
            node_row = _lookup_scene_pipeline_row(pipeline_rows, scene_id)
            plan = resolve_scene_subskill_resume(
                scene_id=scene_id,
                steps=lookup_persisted_scene_subskill_steps(persist_map, scene_id),
                pipeline_status=str(node_row.get("status") or ""),
                pipeline_scene_block=str(node_row.get("scene_block") or ""),
                call_vfx=bool(task.get("call_vfx")),
                call_xian=bool(task.get("call_xian")),
            )
            resume_plans[scene_id] = plan
            resume_plans[scene_id.lower()] = plan
            logger.info(
                "[scene_subskill_pipeline] resume scene=%s from=%s reason=%s",
                scene_id,
                plan.start_group,
                plan.skipped_reason,
            )
    if project_id > 0 and node_episode_id > 0:
        for task in tasks:
            scene_id = str(task.get("scene_id") or "").strip()
            plan = resume_plans.get(scene_id)
            if plan and plan.start_group == "done":
                continue
            upsert_pipeline_node_status(
                db,
                project_id=project_id,
                episode_id=node_episode_id,
                script_id=f"episode:{node_episode_id}",
                node_name="scene_subskill_scene",
                scene_id=scene_id,
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
    env_catalog = []
    if project_id > 0:
        try:
            env_catalog = collect_project_main_environment_catalog(
                db,
                project_id=int(project_id),
                current_episode_id=int(node_episode_id or 0),
            )
        except Exception as catalog_exc:
            logger.warning("[scene_subskill_pipeline] failed to load env catalog: %s", catalog_exc)
    env_plan_task = asyncio.create_task(
        await_environment_planned_script(
            episode_id=int(node_episode_id or 0),
            explicit_text=str(raw_payload.get("environment_planned_text") or ""),
        )
    )

    async def _run_one(task: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        async with semaphore:
            scene_id = str(task.get("scene_id") or "")
            scene_resume = resume_plans.get(scene_id) or resume_plans.get(scene_id.lower())
            scene_start = scene_resume.start_group if scene_resume else start_group
            if scene_start == "done":
                return int(task.get("scene_order") or 0), {
                    "scene_id": scene_id,
                    "scene_order": int(task.get("scene_order") or 0),
                    "scene_block": str(scene_resume.current_block if scene_resume else task.get("scene_block") or ""),
                    "called_subskills": list(scene_resume.called) if scene_resume else [],
                    "routes": task.get("routes") or {},
                    "skipped": True,
                    "resume_from": "done",
                }
            task_db = SessionLocal()
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
                special = str(task.get("special_analysis") or "")
                raw_scene_block = str(task.get("scene_block") or "")
                resume_block = str(scene_resume.current_block or "").strip() if scene_resume else ""
                if resume_block:
                    current_block = resume_block
                elif scene_start == "staging":
                    current_block = raw_scene_block.strip()
                else:
                    current_block = strip_environment_planning_sections(raw_scene_block)
                if special and special not in current_block:
                    current_block = "\n".join(part for part in (special, current_block) if part)
                called: List[str] = list(scene_resume.called) if scene_resume else []
                call_vfx = bool(task.get("call_vfx"))
                call_xian = bool(task.get("call_xian"))

                async def _run_enhance_step(prompt_file: str, step_name: str) -> None:
                    nonlocal current_block
                    _mark_scene_subskill_step(
                        task_db,
                        project_id=project_id,
                        episode_id=node_episode_id,
                        scene_id=scene_id,
                        step_name=step_name,
                        step_label=_subskill_action_label(prompt_file),
                    )
                    scene_input = _wrap_single_scene_input(
                        current_block,
                        str(task.get("comprehensive_info") or ""),
                        project_tail,
                        str(task.get("entity_token_brief") or ""),
                    )
                    current_block = await _call_scene_subskill(
                        task_db=task_db,
                        current_user=user_principal,
                        base_payload=raw_payload,
                        prompt_file=prompt_file,
                        scene_input=scene_input,
                        scene_id=scene_id,
                        fallback_special=special,
                        previous_block=current_block,
                    )
                    called.append(step_name)
                    persist_scene_subskill_named_step(
                        db=task_db,
                        episode_id=node_episode_id,
                        scene_id=scene_id,
                        step_name=step_name,
                        result_text=current_block,
                    )

                if scene_start not in {"combat", "framing", "staging"}:
                    await _run_enhance_step(DRAMA_PROMPT, "drama")
                    special = _special_block_from_text(current_block, scene_id) or special
                    call_vfx, call_xian = _routes_from_special_text(special, scene_id)
                    task["special_analysis"] = special
                    task["call_vfx"] = call_vfx
                    task["call_xian"] = call_xian
                    if special:
                        try:
                            parsed_routes = parse_special_scene_analysis_blocks(special)
                            for key, value in parsed_routes.items():
                                if str(key).strip().lower() == scene_id.lower():
                                    task["routes"] = value.get("routes") or {}
                                    break
                        except SceneMarkerParseError:
                            pass
                    if not special:
                        raise HTTPException(
                            status_code=422,
                            detail=f"SCENE_SUBSKILL_ROUTING_MISSING:{scene_id}",
                        )
                else:
                    special = special or _special_block_from_text(current_block, scene_id)
                    routed_vfx, routed_xian = _routes_from_special_text(special, scene_id)
                    if routed_vfx or routed_xian:
                        call_vfx, call_xian = routed_vfx, routed_xian
                if scene_start == "combat":
                    special = special or _special_block_from_text(current_block, scene_id)
                    call_vfx, call_xian = _routes_from_special_text(special, scene_id)
                    if not call_vfx and not call_xian:
                        raise HTTPException(
                            status_code=422,
                            detail=f"SCENE_SUBSKILL_COMBAT_NOT_ROUTED:{scene_id}",
                        )
                if scene_start not in {"framing", "staging"}:
                    if call_vfx:
                        await _run_enhance_step(VFX_PROMPT, "vfx")
                    if call_xian:
                        await _run_enhance_step(XIAN_PROMPT, "xian")

                env_script = ""
                env_scene = ""
                if scene_start != "staging":
                    _mark_scene_subskill_step(
                        task_db,
                        project_id=project_id,
                        episode_id=node_episode_id,
                        scene_id=scene_id,
                        step_name="wait_env",
                        step_label="等待主环境注入",
                    )
                    env_script = await env_plan_task
                    env_scene = _scene_block_from_script(env_script, scene_id)
                    if not env_scene:
                        raise HTTPException(
                            status_code=422,
                            detail=f"STAGING_ENV_SCENE_MISSING:{scene_id}",
                        )
                current_block = await _run_derived_framing_then_staging(
                    task_db=task_db,
                    user_principal=user_principal,
                    raw_payload=raw_payload,
                    project_id=project_id,
                    episode_id=node_episode_id,
                    scene_id=scene_id,
                    special=special,
                    comprehensive_info=str(task.get("comprehensive_info") or ""),
                    project_tail=project_tail,
                    env_script=env_script,
                    env_scene=env_scene,
                    enhance_block=current_block,
                    env_catalog=env_catalog,
                    called=called,
                    skip_framing=scene_start == "staging",
                    entity_token_brief=str(task.get("entity_token_brief") or ""),
                )
                if project_id > 0 and node_episode_id > 0:
                    workspace_import = {}
                    try:
                        workspace_import = upsert_workspace_scene_from_staging(
                            task_db,
                            episode_id=node_episode_id,
                            scene_id=scene_id,
                            staging_text=current_block,
                            scene_order=int(task.get("scene_order") or 0) or None,
                        )
                    except Exception as import_exc:
                        logger.warning(
                            "[scene_subskill] workspace scene import failed scene_id=%s err=%s",
                            scene_id,
                            import_exc,
                        )
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
                            "workspace_import": workspace_import,
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
            except asyncio.CancelledError:
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
                            "business_event": "cancelled",
                            "business_reason": "任务被取消，已退出进行中状态",
                        },
                        error_code="SCENE_SUBSKILL_CANCELLED",
                        error_message="scene subskill cancelled",
                    )
                    task_db.commit()
                raise
            except Exception as exc:
                project_id = int(raw_payload.get("project_id") or 0)
                timed_out = is_timeout_like_error(exc)
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
                            "business_event": "timeout" if timed_out else "failed",
                            "business_reason": _scene_subskill_failure_reason(exc),
                        },
                        error_code="SCENE_SUBSKILL_TIMEOUT" if timed_out else "SCENE_SUBSKILL_SCENE_FAILED",
                        error_message=str(exc),
                    )
                    task_db.commit()
                return int(task.get("scene_order") or 0), {
                    "scene_id": scene_id,
                    "scene_order": int(task.get("scene_order") or 0),
                    "scene_block": str(locals().get("current_block") or task.get("scene_block") or ""),
                    "called_subskills": locals().get("called") if isinstance(locals().get("called"), list) else [],
                    "routes": task.get("routes") or {},
                    "failed": True,
                    "timed_out": timed_out,
                    "error": str(exc),
                }
            finally:
                _release_db_connection(task_db)

    try:
        results = list(await asyncio.gather(*(_run_one(task) for task in tasks)))
        timeout_retry_tasks = [
            task for task, (_order, item) in zip(tasks, results)
            if isinstance(item, dict) and item.get("timed_out")
        ]
        if timeout_retry_tasks:
            logger.warning(
                "[scene_subskill_pipeline] retrying timed-out scenes once count=%s ids=%s",
                len(timeout_retry_tasks),
                [str(task.get("scene_id") or "") for task in timeout_retry_tasks],
            )
            refresh_db = SessionLocal()
            try:
                persist_map = load_scene_subskill_results_map(refresh_db, node_episode_id)
                pipeline_rows = _load_scene_pipeline_rows(
                    refresh_db,
                    project_id=project_id,
                    episode_id=node_episode_id,
                )
            finally:
                _release_db_connection(refresh_db)
            for task in timeout_retry_tasks:
                scene_id = str(task.get("scene_id") or "").strip()
                node_row = _lookup_scene_pipeline_row(pipeline_rows, scene_id)
                plan = resolve_scene_subskill_resume(
                    scene_id=scene_id,
                    steps=lookup_persisted_scene_subskill_steps(persist_map, scene_id),
                    pipeline_status=str(node_row.get("status") or ""),
                    pipeline_scene_block=str(node_row.get("scene_block") or ""),
                    call_vfx=bool(task.get("call_vfx")),
                    call_xian=bool(task.get("call_xian")),
                )
                resume_plans[scene_id] = plan
                resume_plans[scene_id.lower()] = plan
            retry_results = await asyncio.gather(*(_run_one(task) for task in timeout_retry_tasks))
            retry_by_id = {
                str(item.get("scene_id") or "").strip().lower(): (order, item)
                for order, item in retry_results
                if isinstance(item, dict)
            }
            next_results = []
            for task, pair in zip(tasks, results):
                sid = str(task.get("scene_id") or "").strip().lower()
                next_results.append(retry_by_id.get(sid) or pair)
            results = next_results
    finally:
        if not env_plan_task.done():
            env_plan_task.cancel()
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
            persist_text = aggregate_text
            if target_scene_ids:
                base_script = str(getattr(episode, "ai_scene_analysis_adaptation", "") or "").strip()
                if not base_script:
                    base_script = load_environment_planned_script(db, int(node_episode_id)) or script_text
                persist_text = merge_scene_blocks_into_script(base_script, ordered)
            persist_script_optimization_stage(
                db=db,
                episode=episode,
                result_content=persist_text,
                node_output_key="scene_subskills",
            )
            _ingest_derived_environments_after_framing(
                db,
                project_id=int(raw_payload.get("project_id") or 0),
                episode_id=int(node_episode_id),
                scene_text=persist_text,
                phase="after_all_scenes",
            )
            aggregate_text = persist_text

    failed_ids = [
        str(item.get("scene_id") or "").strip()
        for item in ordered
        if item.get("failed") and str(item.get("scene_id") or "").strip()
    ]
    logger.info(
        "[scene_subskill_pipeline] completed scenes=%s failed=%s concurrency=%s episode_id=%s",
        len(ordered),
        failed_ids,
        max_concurrency,
        node_episode_id,
    )
    return {
        "content": aggregate_text,
        "adapted_script": aggregate_text,
        "per_scene_parallel": True,
        "per_scene_outputs": ordered,
        "scene_count": len(ordered),
        "partial_failure": bool(failed_ids),
        "failed_scene_ids": failed_ids,
    }
