from __future__ import annotations

import json
import logging
import re
import threading
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.prompt_injection import assert_no_prompt_injection
from app.models import all_models as models

Episode = models.Episode


def _assert_safe_persist(
    text: Any,
    *,
    source: str,
    db: Optional[Session] = None,
    episode: Optional[Episode] = None,
    episode_id: Optional[int] = None,
    scene_id: Optional[str] = None,
) -> None:
    assert_no_prompt_injection(
        text,
        source=source,
        db=db,
        episode=episode,
        project_id=getattr(episode, "project_id", None) if episode is not None else None,
        episode_id=episode_id if episode_id is not None else getattr(episode, "id", None),
        scene_id=scene_id,
    )

logger = logging.getLogger(__name__)

STAGE_SCRIPT_OPTIMIZATION = "script_optimization"
STAGE_ASSETS_EXTRACTION = "assets_extraction"
STAGE_SCENE_MARKDOWN = "scene_markdown"
STAGE_ENTITY_DESIGN = "entity_design"
STAGE_GENERIC = "generic"


@dataclass(frozen=True)
class AnalyzeSceneStageContext:
    stage_key: str
    is_script_optimization_stage: bool
    is_subject_index_extraction_stage: bool
    is_scene_beats_stage: bool
    is_entity_design_phase: bool


def resolve_analyze_scene_stage(
    *,
    effective_scene_analysis_mode: Optional[str],
    prompt_file: Any = "",
    function_name: Any = "",
) -> AnalyzeSceneStageContext:
    prompt_file_lower = str(prompt_file or "").strip().lower()
    mode_lower = str(effective_scene_analysis_mode or "").strip().lower()
    function_name_lower = str(function_name or "").strip().lower()

    is_scene_beats_stage = bool(
        function_name_lower in {"script_analysis_stage_2_2_beats"}
        or "scene_planning_2_2" in prompt_file_lower
        or mode_lower in {"beats_generation", "scene_planning_beats", "scene_beats_only"}
    )
    is_subject_index_extraction_stage = bool(
        function_name_lower in {"script_analysis_stage_2_1_assets_extraction", "assets_extraction"}
        or "scene_planning_2_1" in prompt_file_lower
        or mode_lower in {"assets_extraction", "stage2_1", "stage_2_1"}
    )
    is_script_optimization_stage = bool(
        function_name_lower in {"script_analysis_stage_1_script_optimization", "script_optimization"}
        or "scene_planning_1_script_optimization" in prompt_file_lower
        or mode_lower in {"script_optimization", "stage1", "stage_1"}
    )
    is_entity_design_phase = bool(
        mode_lower == "entity_design"
        or mode_lower.startswith("2_pass_generate_assets")
        or "entity_design" in prompt_file_lower
    )

    if is_entity_design_phase:
        stage_key = STAGE_ENTITY_DESIGN
    elif is_scene_beats_stage:
        stage_key = STAGE_SCENE_MARKDOWN
    elif is_subject_index_extraction_stage:
        stage_key = STAGE_ASSETS_EXTRACTION
    elif is_script_optimization_stage:
        stage_key = STAGE_SCRIPT_OPTIMIZATION
    else:
        stage_key = STAGE_GENERIC

    return AnalyzeSceneStageContext(
        stage_key=stage_key,
        is_script_optimization_stage=is_script_optimization_stage,
        is_subject_index_extraction_stage=is_subject_index_extraction_stage,
        is_scene_beats_stage=is_scene_beats_stage,
        is_entity_design_phase=is_entity_design_phase,
    )


def should_require_subject_index(stage_ctx: AnalyzeSceneStageContext) -> bool:
    """Subject Index is not the source of truth for asset design or scene beats."""
    if stage_ctx.is_entity_design_phase or stage_ctx.is_scene_beats_stage:
        return False
    return True


def validate_analyze_scene_llm_finish_reason(
    *,
    finish_reason: Any,
    result_content: str,
    provider: Any = "",
    model: Any = "",
    episode_id: Any = None,
) -> None:
    from fastapi import HTTPException

    if str(finish_reason or "").strip().lower() not in {"incomplete", "error"}:
        return

    logger.error(
        "[analyze_scene.validate] finish_reason=%s episode_id=%s provider=%s model=%s output_chars=%s",
        finish_reason,
        episode_id,
        provider,
        model,
        len(result_content or ""),
    )
    raise HTTPException(
        status_code=502,
        detail=f"LLM connection dropped prematurely (reason: {finish_reason}). Please retry.",
    )


def _read_persisted_chars(episode: Episode, field_name: str) -> int:
    return len(str(getattr(episode, field_name, "") or ""))


def _extract_entity_profile_prefix_before_scenes(candidate_text: str, scenes_start_idx: int) -> str:
    """Keep Part 2【角色设定】(`[ENTITY_PROFILE_START]…[ENTITY_PROFILE_END]`) before SCENES_BLOCK."""
    if scenes_start_idx <= 0:
        return ""
    preamble = str(candidate_text or "")[:scenes_start_idx]
    if not preamble.strip():
        return ""

    profile_start = re.search(
        r"`?\[ENTITY_PROFILE_START(?::[^\s\]]+)?\]`?",
        preamble,
        flags=re.IGNORECASE,
    )
    if profile_start:
        after_start = preamble[profile_start.start():]
        profile_end = re.search(
            r"`?\[ENTITY_PROFILE_END(?::[^\s\]]+)?\]`?",
            after_start,
            flags=re.IGNORECASE,
        )
        if profile_end:
            return after_start[: profile_end.end()].strip()
        body = after_start.rstrip()
        if body and not re.search(r"`?\[ENTITY_PROFILE_END(?::[^\s\]]+)?\]`?", body, flags=re.IGNORECASE):
            body = f"{body}\n[ENTITY_PROFILE_END]"
        return body.strip()

    legacy = re.search(r"【角色设定】", preamble)
    if not legacy:
        return ""
    body = preamble[legacy.start():].strip()
    if not body:
        return ""
    return f"[ENTITY_PROFILE_START]\n{body}\n[ENTITY_PROFILE_END]"


def _trim_stage1_adapted_script_body(candidate_text: str) -> str:
    candidate = str(candidate_text or "").strip()
    if not candidate:
        return ""

    scenes_start = re.search(r"`?\[SCENES_BLOCK_START\]`?", candidate, flags=re.IGNORECASE)
    if scenes_start:
        start_idx = scenes_start.start()
        after_start = candidate[scenes_start.end():]
        scenes_end = re.search(r"`?\[SCENES_BLOCK_END\]`?", after_start, flags=re.IGNORECASE)
        if scenes_end:
            end_idx_abs = scenes_start.end() + scenes_end.end()
            scenes_block = candidate[start_idx:end_idx_abs].strip()
        else:
            scenes_block = candidate[start_idx:].strip()
        from app.services.script_analysis_flow.character_asset_brief import (
            extract_char_extract_blocks,
            splice_char_extract_into_script,
        )
        from app.services.script_analysis_flow.prop_asset_brief import (
            extract_prop_extract_blocks,
            splice_prop_extract_into_script,
        )

        scenes_block = splice_char_extract_into_script(
            scenes_block,
            extract_char_extract_blocks(candidate),
        )
        scenes_block = splice_prop_extract_into_script(
            scenes_block,
            extract_prop_extract_blocks(candidate),
        )
        entity_profile = _extract_entity_profile_prefix_before_scenes(candidate, start_idx)
        if entity_profile:
            return f"{entity_profile}\n{scenes_block}".strip()
        return scenes_block

    if re.search(r"\[SCENE_START:", candidate, flags=re.IGNORECASE):
        scene_at = re.search(r"\[SCENE_START:", candidate, flags=re.IGNORECASE)
        scene_at_idx = scene_at.start() if scene_at else -1
        end_marker = re.search(
            r"(?:^|\n)\s*(?:###\s*Subject\s*Index|###\s*Part\s*1|###\s*Project\s*Visual\s*Backfill|\[Project Metadata\]|\[Reusable Subject Assets)",
            candidate,
            flags=re.IGNORECASE,
        )
        fallback_end_marker = re.search(
            r"(?:^|\n)\s*(?:###\s*第三部分|##\s*第三部分|第三部分[:：]?\s*Project\s*Visual\s*Backfill|[-]{5,}\s*$|\{\s*\"project_visual_backfill\"\s*:)",
            candidate,
            flags=re.IGNORECASE | re.MULTILINE,
        )
        if end_marker and end_marker.start() > max(0, scene_at_idx):
            candidate = candidate[: end_marker.start()].strip()
        elif fallback_end_marker and fallback_end_marker.start() > max(0, scene_at_idx):
            candidate = candidate[: fallback_end_marker.start()].strip()
        return candidate.strip()

    scene_heading = re.search(
        r"(?:^|\n)\s*(?:\*\*)?\s*(?:【场景\s+(?:\d+|EP\d+_SC\d+)[^】]*】|\*\*【场景\s+(?:\d+|EP\d+_SC\d+)[^】]*】\*\*|Scene\s*\d+\s*[:：]|\[Scene\s*\d+[^\n]*\])",
        candidate,
        flags=re.IGNORECASE,
    )
    if scene_heading and scene_heading.start() >= 0 and scene_heading.start() < 200:
        candidate = candidate[scene_heading.start():].strip()

    end_marker = re.search(
        r"(?:^|\n)\s*(?:###\s*Subject\s*Index|###\s*Part\s*1|###\s*Project\s*Visual\s*Backfill|\[Project Metadata\]|\[Reusable Subject Assets)",
        candidate,
        flags=re.IGNORECASE,
    )
    if end_marker and end_marker.start() > 0:
        candidate = candidate[: end_marker.start()].strip()

    return candidate.strip()


def extract_stage1_adapted_script_body(stage1_text: str) -> str:
    from app.services.subject_index_resolve import strip_project_visual_backfill_sections

    text = strip_project_visual_backfill_sections(stage1_text).replace("\r\n", "\n").strip()
    if not text:
        return ""

    section_patterns = [
        r"(?is)^.*?(?:###\s*第二部分[:：]?\s*修改后的剧本.*?\n)(.*)$",
        r"(?is)^.*?(?:##\s*第二部分[:：]?\s*修改后的剧本.*?\n)(.*)$",
        r"(?is)^.*?(?:第二部分[:：]?\s*修改后的剧本.*?\n)(.*)$",
        r"(?is)^.*?(?:###\s*Second\s*Part[:：]?\s*Adapted\s*Script.*?\n)(.*)$",
        r"(?is)^.*?(?:##\s*Second\s*Part[:：]?\s*Adapted\s*Script.*?\n)(.*)$",
        r"(?is)^.*?(?:Adapted\s*Script\s*[-(（].*?\n)(.*)$",
    ]
    for pattern in section_patterns:
        match = re.match(pattern, text)
        if not match:
            continue
        extracted = _trim_stage1_adapted_script_body(match.group(1) or "")
        if extracted:
            return extracted
    return _trim_stage1_adapted_script_body(text)


def _format_project_visual_backfill_json(raw_text: str) -> str:
    from app.services.subject_index_resolve import extract_project_visual_backfill_object

    obj = extract_project_visual_backfill_object(raw_text)
    if not obj:
        return ""
    return json.dumps({"project_visual_backfill": obj}, ensure_ascii=False, indent=2)


_STAGE_OUTPUT_PATCH_LOCKS: Dict[int, threading.Lock] = {}
_STAGE_OUTPUT_PATCH_LOCKS_GUARD = threading.Lock()
SCENE_SUBSKILL_RESULTS_OUTPUT_KEY = "scene_subskill_results"
_SUBSKILL_RESULT_STEP_KEYS = {
    "drama": "drama",
    "combat": "combat",
    "vfx": "combat",
    "xian": "combat",
    "derived_framing": "framing",
    "staging": "staging",
}


def _get_stage_output_patch_lock(episode_id: int) -> threading.Lock:
    eid = int(episode_id or 0)
    with _STAGE_OUTPUT_PATCH_LOCKS_GUARD:
        lock = _STAGE_OUTPUT_PATCH_LOCKS.get(eid)
        if lock is None:
            lock = threading.Lock()
            _STAGE_OUTPUT_PATCH_LOCKS[eid] = lock
        return lock


def _load_stage_outputs_obj(episode: Episode) -> Dict[str, Any]:
    raw = str(getattr(episode, "ai_stage_outputs", "") or "").strip()
    try:
        obj = json.loads(raw) if raw else {"version": 1, "stages": {}}
        if not isinstance(obj, dict):
            obj = {"version": 1, "stages": {}}
    except Exception:
        obj = {"version": 1, "stages": {}}
    stages = obj.setdefault("stages", {})
    if not isinstance(stages, dict):
        obj["stages"] = {}
    return obj


def _dump_stage_outputs_obj(episode: Episode, obj: Dict[str, Any]) -> None:
    episode.ai_stage_outputs = json.dumps(obj, ensure_ascii=False, indent=2)


def _ensure_stage_outputs(obj: Dict[str, Any], stage_key: str) -> Dict[str, Any]:
    stages = obj.setdefault("stages", {})
    if not isinstance(stages, dict):
        stages = {}
        obj["stages"] = stages
    stage = stages.setdefault(str(stage_key), {"key": str(stage_key), "outputs": {}})
    if not isinstance(stage, dict):
        stage = {"key": str(stage_key), "outputs": {}}
        stages[str(stage_key)] = stage
    outputs = stage.setdefault("outputs", {})
    if not isinstance(outputs, dict):
        outputs = {}
        stage["outputs"] = outputs
    return outputs


def patch_episode_stage_output_slot(
    episode: Episode,
    *,
    stage_key: str,
    output_key: str,
    content: str,
    kind: str = "markdown",
    title: str = "",
) -> None:
    obj = _load_stage_outputs_obj(episode)
    outputs = _ensure_stage_outputs(obj, stage_key)
    slot = outputs.get(output_key) if isinstance(outputs.get(output_key), dict) else {}
    outputs[str(output_key)] = {
        **slot,
        "key": str(output_key),
        "kind": slot.get("kind") or kind,
        "title": slot.get("title") or title or output_key,
        "content": str(content or ""),
    }
    _dump_stage_outputs_obj(episode, obj)


def _parse_subskill_results_content(raw: Any) -> Dict[str, Dict[str, str]]:
    if isinstance(raw, dict):
        parsed = raw
    else:
        text = str(raw or "").strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
        except Exception:
            return {}
    if not isinstance(parsed, dict):
        return {}
    result: Dict[str, Dict[str, str]] = {}
    for scene_id, steps in parsed.items():
        sid = str(scene_id or "").strip()
        if not sid or not isinstance(steps, dict):
            continue
        result[sid] = {
            str(step_key or "").strip(): str(step_text or "")
            for step_key, step_text in steps.items()
            if str(step_key or "").strip()
        }
    return result


def _stage1_slot_content(obj: Dict[str, Any], output_key: str) -> Any:
    stages = obj.get("stages") if isinstance(obj, dict) else {}
    stage1 = stages.get("stage1") if isinstance(stages, dict) else {}
    outputs = stage1.get("outputs") if isinstance(stage1, dict) else {}
    slot = outputs.get(output_key) if isinstance(outputs, dict) else {}
    if isinstance(slot, dict):
        return slot.get("content")
    return slot


_SCENE_START_ID_RE = re.compile(r"\[SCENE_START:([^\]]+)\]", re.IGNORECASE)


def scene_ids_from_split_text(text: Any) -> set[str]:
    """Collect SCENE_START ids from a global-orchestration / scene-split body."""
    return {
        str(match.group(1) or "").strip()
        for match in _SCENE_START_ID_RE.finditer(str(text or ""))
        if str(match.group(1) or "").strip()
    }


def scene_id_alias_set(scene_id: Any) -> set[str]:
    sid = str(scene_id or "").strip()
    if not sid:
        return set()
    aliases = {sid, sid.upper(), sid.lower()}
    match = re.match(r"^(EP\d+)_SC(\d+[A-Z]?)$", sid, flags=re.IGNORECASE)
    if match:
        order = match.group(2)
        digits = re.match(r"^(\d+)", order)
        if digits:
            aliases.add(str(int(digits.group(1))))
            aliases.add(f"SC{int(digits.group(1)):02d}")
            aliases.add(f"sc{int(digits.group(1)):02d}")
        aliases.add(f"SC{order.upper()}")
    elif re.match(r"^SC(\d+)$", sid, flags=re.IGNORECASE):
        aliases.add(str(int(re.match(r"^SC(\d+)$", sid, flags=re.IGNORECASE).group(1))))
    return {item for item in aliases if item}


def prune_subskill_results_map_to_scene_ids(
    result_map: Dict[str, Dict[str, str]],
    keep_scene_ids: Any,
) -> Dict[str, Dict[str, str]]:
    keep_aliases: set[str] = set()
    for raw in keep_scene_ids or []:
        keep_aliases.update(scene_id_alias_set(raw))
    if not keep_aliases:
        return dict(result_map or {})
    return {
        sid: dict(steps)
        for sid, steps in (result_map or {}).items()
        if sid in keep_aliases or (scene_id_alias_set(sid) & keep_aliases)
    }


def prune_stale_scene_subskill_results(episode: Episode, keep_scene_ids: Any) -> int:
    """Drop persisted per-scene subskill rows that are no longer in the latest split."""
    if episode is None:
        return 0
    keep = {str(sid).strip() for sid in (keep_scene_ids or []) if str(sid).strip()}
    if not keep:
        return 0
    obj = _load_stage_outputs_obj(episode)
    outputs = _ensure_stage_outputs(obj, "stage1")
    slot = (
        outputs.get(SCENE_SUBSKILL_RESULTS_OUTPUT_KEY)
        if isinstance(outputs.get(SCENE_SUBSKILL_RESULTS_OUTPUT_KEY), dict)
        else {}
    )
    result_map = _parse_subskill_results_content(slot.get("content"))
    if not result_map:
        return 0
    pruned = prune_subskill_results_map_to_scene_ids(result_map, keep)
    removed = len(result_map) - len(pruned)
    if removed <= 0:
        return 0
    outputs[SCENE_SUBSKILL_RESULTS_OUTPUT_KEY] = {
        **slot,
        "key": SCENE_SUBSKILL_RESULTS_OUTPUT_KEY,
        "kind": "json",
        "title": slot.get("title") or "逐场优化分步结果",
        "content": json.dumps(pruned, ensure_ascii=False, indent=2),
    }
    _dump_stage_outputs_obj(episode, obj)
    return removed


def merge_ai_stage_outputs_preserving_subskills(existing: Any, incoming: Any) -> str:
    """Keep per-scene drama/framing/staging steps when a stale full-document write omits them.

    An explicit empty string is a restart wipe, not an omitted payload. Returning
    ``existing`` here left 全局统筹 / 环境规划 / 分场节点 on screen after 重新分析.

    When incoming includes a new scene_split with SCENE_START markers, drop old
    per-scene rows that are no longer in that split so a shorter rerun cannot
    resurrect SC02 after the script only has SC01.
    """
    incoming_text = incoming if isinstance(incoming, str) else json.dumps(incoming or {}, ensure_ascii=False)
    if not str(incoming_text or "").strip():
        return ""
    try:
        new_obj = json.loads(incoming_text) if isinstance(incoming_text, str) else incoming
        if not isinstance(new_obj, dict):
            return incoming_text
    except Exception:
        return incoming_text
    try:
        old_obj = json.loads(existing) if isinstance(existing, str) else existing
        if not isinstance(old_obj, dict):
            old_obj = {}
    except Exception:
        old_obj = {}
    old_map = _parse_subskill_results_content(_stage1_slot_content(old_obj, SCENE_SUBSKILL_RESULTS_OUTPUT_KEY))
    new_map = _parse_subskill_results_content(_stage1_slot_content(new_obj, SCENE_SUBSKILL_RESULTS_OUTPUT_KEY))
    if not old_map:
        return incoming_text
    merged = {sid: dict(steps) for sid, steps in old_map.items()}
    for sid, steps in new_map.items():
        scene = dict(merged.get(sid) or {})
        for key, value in steps.items():
            if str(value or "").strip():
                scene[key] = value
        merged[sid] = scene
    keep_ids = scene_ids_from_split_text(_stage1_slot_content(new_obj, "scene_split"))
    if keep_ids:
        merged = prune_subskill_results_map_to_scene_ids(merged, keep_ids)
    outputs = _ensure_stage_outputs(new_obj, "stage1")
    slot = outputs.get(SCENE_SUBSKILL_RESULTS_OUTPUT_KEY)
    slot = slot if isinstance(slot, dict) else {}
    outputs[SCENE_SUBSKILL_RESULTS_OUTPUT_KEY] = {
        **slot,
        "key": SCENE_SUBSKILL_RESULTS_OUTPUT_KEY,
        "kind": "json",
        "title": slot.get("title") or "逐场优化分步结果",
        "content": json.dumps(merged, ensure_ascii=False, indent=2),
    }
    return json.dumps(new_obj, ensure_ascii=False, indent=2)


def persist_scene_subskill_step_result(
    *,
    db: Session,
    episode_id: int,
    scene_id: str,
    step_key: str,
    result_text: str,
) -> Dict[str, Any]:
    from app.services.soft_delete import _active_episode_clause

    eid = int(episode_id or 0)
    sid = str(scene_id or "").strip()
    key = str(step_key or "").strip()
    text = str(result_text or "").strip()
    if eid <= 0 or not sid or not key or not text:
        return {"patched": False, "reason": "invalid_args"}
    _assert_safe_persist(
        text,
        source=f"persist.scene_subskill.{sid}.{key}",
        db=db,
        episode_id=eid,
        scene_id=sid,
    )
    lock = _get_stage_output_patch_lock(eid)
    with lock:
        episode = (
            db.query(Episode)
            .filter(Episode.id == eid, _active_episode_clause())
            .populate_existing()
            .first()
        )
        if episode is None:
            return {"patched": False, "reason": "episode_missing"}
        obj = _load_stage_outputs_obj(episode)
        outputs = _ensure_stage_outputs(obj, "stage1")
        slot = (
            outputs.get(SCENE_SUBSKILL_RESULTS_OUTPUT_KEY)
            if isinstance(outputs.get(SCENE_SUBSKILL_RESULTS_OUTPUT_KEY), dict)
            else {}
        )
        result_map = _parse_subskill_results_content(slot.get("content"))
        scene_map = result_map.get(sid) if isinstance(result_map.get(sid), dict) else {}
        scene_map[key] = text
        result_map[sid] = scene_map
        outputs[SCENE_SUBSKILL_RESULTS_OUTPUT_KEY] = {
            **slot,
            "key": SCENE_SUBSKILL_RESULTS_OUTPUT_KEY,
            "kind": "json",
            "title": slot.get("title") or "逐场优化分步结果",
            "content": json.dumps(result_map, ensure_ascii=False, indent=2),
        }
        _dump_stage_outputs_obj(episode, obj)
        db.commit()
    return {"patched": True, "scene_id": sid, "step_key": key, "chars": len(text)}


def persist_scene_subskill_named_step(
    *,
    db: Session,
    episode_id: int,
    scene_id: str,
    step_name: str,
    result_text: str,
) -> Dict[str, Any]:
    mapped = _SUBSKILL_RESULT_STEP_KEYS.get(str(step_name or "").strip())
    if not mapped:
        return {"patched": False, "reason": "unknown_step"}
    return persist_scene_subskill_step_result(
        db=db,
        episode_id=episode_id,
        scene_id=scene_id,
        step_key=mapped,
        result_text=result_text,
    )


def load_scene_subskill_results_map(db: Session, episode_id: int) -> Dict[str, Dict[str, str]]:
    from app.services.soft_delete import _active_episode_clause

    eid = int(episode_id or 0)
    if eid <= 0:
        return {}
    episode = (
        db.query(Episode)
        .filter(Episode.id == eid, _active_episode_clause())
        .populate_existing()
        .first()
    )
    if episode is None:
        return {}
    obj = _load_stage_outputs_obj(episode)
    outputs = _ensure_stage_outputs(obj, "stage1")
    slot = (
        outputs.get(SCENE_SUBSKILL_RESULTS_OUTPUT_KEY)
        if isinstance(outputs.get(SCENE_SUBSKILL_RESULTS_OUTPUT_KEY), dict)
        else {}
    )
    return _parse_subskill_results_content(slot.get("content"))


def load_stage1_output_text(db: Session, episode_id: int, output_key: str) -> str:
    from app.services.soft_delete import _active_episode_clause

    eid = int(episode_id or 0)
    key = str(output_key or "").strip()
    if eid <= 0 or not key:
        return ""
    episode = (
        db.query(Episode)
        .filter(Episode.id == eid, _active_episode_clause())
        .populate_existing()
        .first()
    )
    if episode is None:
        return ""
    content = _stage1_slot_content(_load_stage_outputs_obj(episode), key)
    if isinstance(content, dict):
        return json.dumps(content, ensure_ascii=False)
    return str(content or "").strip()


def lookup_persisted_scene_subskill_steps(
    result_map: Optional[Dict[str, Any]],
    scene_id: str,
) -> Dict[str, str]:
    sid = str(scene_id or "").strip()
    if not sid or not isinstance(result_map, dict):
        return {}
    direct = result_map.get(sid)
    if isinstance(direct, dict):
        return {str(k): str(v or "") for k, v in direct.items()}
    sid_l = sid.lower()
    for key, value in result_map.items():
        if str(key or "").strip().lower() == sid_l and isinstance(value, dict):
            return {str(k): str(v or "") for k, v in value.items()}
    return {}


def _patch_episode_stage1_outputs(
    episode: Episode,
    *,
    raw_text: str,
    adapted_script: str,
    visual_backfill_json: str = "",
    node_output_key: str = "",
) -> None:
    raw = str(getattr(episode, "ai_stage_outputs", "") or "").strip()
    try:
        obj = json.loads(raw) if raw else {"version": 1, "stages": {}}
        if not isinstance(obj, dict):
            obj = {"version": 1, "stages": {}}
    except Exception:
        obj = {"version": 1, "stages": {}}
    stages = obj.setdefault("stages", {})
    if not isinstance(stages, dict):
        stages = {}
        obj["stages"] = stages
    stage1 = stages.setdefault("stage1", {"key": "stage1", "outputs": {}})
    if not isinstance(stage1, dict):
        stage1 = {"key": "stage1", "outputs": {}}
        stages["stage1"] = stage1
    outputs = stage1.setdefault("outputs", {})
    if not isinstance(outputs, dict):
        outputs = {}
        stage1["outputs"] = outputs
    raw_slot = outputs.get("raw_text") if isinstance(outputs.get("raw_text"), dict) else {}
    outputs["raw_text"] = {
        **raw_slot,
        "key": "raw_text",
        "kind": raw_slot.get("kind") or "text",
        "title": raw_slot.get("title") or "第一阶段完整结果",
        "content": str(raw_text or ""),
    }
    adapted_slot = outputs.get("adapted_script") if isinstance(outputs.get("adapted_script"), dict) else {}
    outputs["adapted_script"] = {
        **adapted_slot,
        "key": "adapted_script",
        "kind": adapted_slot.get("kind") or "markdown",
        "title": adapted_slot.get("title") or "优化后剧本",
        "content": str(adapted_script or ""),
    }
    visual_slot = outputs.get("project_visual_backfill") if isinstance(outputs.get("project_visual_backfill"), dict) else {}
    outputs["project_visual_backfill"] = {
        **visual_slot,
        "key": "project_visual_backfill",
        "kind": visual_slot.get("kind") or "json",
        "title": visual_slot.get("title") or "全局风格",
        "content": str(visual_backfill_json or ""),
    }
    stable_node_key = str(node_output_key or "").strip()
    if stable_node_key:
        node_slot = outputs.get(stable_node_key) if isinstance(outputs.get(stable_node_key), dict) else {}
        outputs[stable_node_key] = {
            **node_slot,
            "key": stable_node_key,
            "kind": node_slot.get("kind") or "markdown",
            "title": node_slot.get("title") or stable_node_key,
            "content": str(raw_text or ""),
        }
    episode.ai_stage_outputs = json.dumps(obj, ensure_ascii=False, indent=2)


def persist_script_optimization_stage(
    *,
    db: Session,
    episode: Episode,
    result_content: str,
    node_output_key: str = "",
) -> Dict[str, Any]:
    raw_text = str(result_content or "").strip()
    _assert_safe_persist(raw_text, source="persist.script_optimization", db=db, episode=episode)
    adapted_script = extract_stage1_adapted_script_body(raw_text) or raw_text
    visual_backfill_json = _format_project_visual_backfill_json(raw_text)
    eid = int(getattr(episode, "id", 0) or 0)
    lock = _get_stage_output_patch_lock(eid) if eid > 0 else threading.Lock()
    with lock:
        query = getattr(db, "query", None)
        if eid > 0 and callable(query):
            from app.services.soft_delete import _active_episode_clause

            fresh = (
                query(Episode)
                .filter(Episode.id == eid, _active_episode_clause())
                .populate_existing()
                .first()
            )
            if fresh is not None:
                episode = fresh
        # Refresh first so a stale request-session copy cannot wipe
        # scene_subskill_results written by a sibling session.
        persist_key = str(node_output_key or "").strip()
        if persist_key in {"scene_subskills", "scene_subskill_results"}:
            from app.services.script_analysis_flow.environment_reuse import (
                script_has_environment_plan_payload,
            )

            existing_adapt = str(getattr(episode, "ai_scene_analysis_adaptation", "") or "")
            if (
                not script_has_environment_plan_payload(adapted_script)
                and script_has_environment_plan_payload(existing_adapt)
            ):
                adapted_script = existing_adapt
            existing_visual = str(
                _stage1_slot_content(_load_stage_outputs_obj(episode), "project_visual_backfill") or ""
            ).strip()
            if not visual_backfill_json and existing_visual:
                visual_backfill_json = existing_visual
        episode.ai_scene_analysis_adaptation = adapted_script
        _patch_episode_stage1_outputs(
            episode,
            raw_text=raw_text,
            adapted_script=adapted_script,
            visual_backfill_json=visual_backfill_json,
            node_output_key=node_output_key,
        )
        db.commit()
    try:
        db.refresh(episode)
    except Exception:
        pass
    logger.info(
        "[analyze_scene.persist] stage=%s episode_id=%s field=ai_scene_analysis_adaptation chars=%s raw_chars=%s visual_backfill_chars=%s",
        STAGE_SCRIPT_OPTIMIZATION,
        getattr(episode, "id", None),
        len(adapted_script or ""),
        len(result_content or ""),
        len(visual_backfill_json or ""),
    )
    return {
        "stage_key": STAGE_SCRIPT_OPTIMIZATION,
        "saved_field": "ai_scene_analysis_adaptation",
        "saved_chars_readback": _read_persisted_chars(episode, "ai_scene_analysis_adaptation"),
        "saved_visual_backfill_chars": len(visual_backfill_json or ""),
    }


def persist_assets_extraction_stage(
    *,
    db: Session,
    episode: Episode,
    result_content: str,
) -> Dict[str, Any]:
    from app.services.llm_markdown_sanitize import sanitize_subject_index_text

    _assert_safe_persist(result_content, source="persist.assets_extraction", db=db, episode=episode)
    sanitized = sanitize_subject_index_text(result_content)
    episode.ai_scene_analysis_subject_index = sanitized
    patch_episode_stage_output_slot(
        episode,
        stage_key="stage2",
        output_key="subject_index",
        content=sanitized,
        kind="markdown",
        title="资产清单",
    )
    patch_episode_stage_output_slot(
        episode,
        stage_key="stage2",
        output_key="assets_extraction",
        content=sanitized,
        kind="markdown",
        title="资产清单",
    )
    db.commit()
    try:
        db.refresh(episode)
    except Exception:
        pass
    logger.info(
        "[analyze_scene.persist] stage=%s episode_id=%s field=ai_scene_analysis_subject_index chars=%s raw_chars=%s",
        STAGE_ASSETS_EXTRACTION,
        getattr(episode, "id", None),
        len(str(getattr(episode, "ai_scene_analysis_subject_index", "") or "")),
        len(result_content or ""),
    )
    return {
        "stage_key": STAGE_ASSETS_EXTRACTION,
        "saved_field": "ai_scene_analysis_subject_index",
        "saved_subject_index_field": "ai_scene_analysis_subject_index",
        "saved_chars_readback": _read_persisted_chars(episode, "ai_scene_analysis_subject_index"),
        "saved_subject_index_chars_readback": _read_persisted_chars(episode, "ai_scene_analysis_subject_index"),
    }


def persist_scene_markdown_stage(
    *,
    db: Session,
    episode: Episode,
    result_content: str,
) -> Dict[str, Any]:
    _assert_safe_persist(result_content, source="persist.scene_markdown", db=db, episode=episode)
    episode.ai_scene_analysis_scene_markdown = result_content
    patch_episode_stage_output_slot(
        episode,
        stage_key="stage2",
        output_key="scene_markdown",
        content=result_content,
        kind="markdown",
        title="场景编排",
    )
    db.commit()
    try:
        db.refresh(episode)
    except Exception:
        pass
    logger.info(
        "[analyze_scene.persist] stage=%s episode_id=%s field=ai_scene_analysis_scene_markdown chars=%s",
        STAGE_SCENE_MARKDOWN,
        getattr(episode, "id", None),
        len(result_content or ""),
    )
    return {
        "stage_key": STAGE_SCENE_MARKDOWN,
        "saved_field": "ai_scene_analysis_scene_markdown",
        "saved_chars_readback": _read_persisted_chars(episode, "ai_scene_analysis_scene_markdown"),
    }


def persist_entity_design_stage(
    *,
    db: Session,
    episode: Episode,
    result_content: str,
) -> Dict[str, Any]:
    _assert_safe_persist(result_content, source="persist.entity_design", db=db, episode=episode)
    episode.ai_entity_design_result = result_content
    patch_episode_stage_output_slot(
        episode,
        stage_key="stage3",
        output_key="asset_design_json",
        content=result_content,
        kind="json",
        title="资产设计",
    )
    patch_episode_stage_output_slot(
        episode,
        stage_key="stage3",
        output_key="raw_text",
        content=result_content,
        kind="text",
        title="第三阶段完整结果",
    )
    db.commit()
    try:
        db.refresh(episode)
    except Exception:
        pass
    logger.info(
        "[analyze_scene.persist] stage=%s episode_id=%s field=ai_entity_design_result chars=%s",
        STAGE_ENTITY_DESIGN,
        getattr(episode, "id", None),
        len(result_content or ""),
    )
    return {
        "stage_key": STAGE_ENTITY_DESIGN,
        "saved_field": "ai_entity_design_result",
        "saved_chars_readback": _read_persisted_chars(episode, "ai_entity_design_result"),
    }


def persist_generic_analyze_scene_stage(
    *,
    db: Session,
    episode: Episode,
    result_content: str,
) -> Dict[str, Any]:
    _assert_safe_persist(result_content, source="persist.generic", db=db, episode=episode)
    episode.ai_scene_analysis_result = result_content
    db.commit()
    try:
        db.refresh(episode)
    except Exception:
        pass
    logger.info(
        "[analyze_scene.persist] stage=%s episode_id=%s field=ai_scene_analysis_result chars=%s",
        STAGE_GENERIC,
        getattr(episode, "id", None),
        len(result_content or ""),
    )
    return {
        "stage_key": STAGE_GENERIC,
        "saved_field": "ai_scene_analysis_result",
        "saved_chars_readback": _read_persisted_chars(episode, "ai_scene_analysis_result"),
    }


def persist_analyze_scene_stage_result(
    *,
    db: Session,
    episode: Optional[Episode],
    result_content: str,
    stage_ctx: AnalyzeSceneStageContext,
) -> Dict[str, Any]:
    if episode is None:
        return {
            "saved_to_episode": False,
            "saved_episode_id": None,
            "saved_field": None,
            "saved_chars_readback": 0,
            "stage_key": stage_ctx.stage_key,
        }

    if stage_ctx.is_entity_design_phase:
        persist_meta = persist_entity_design_stage(db=db, episode=episode, result_content=result_content)
    elif stage_ctx.is_scene_beats_stage:
        persist_meta = persist_scene_markdown_stage(db=db, episode=episode, result_content=result_content)
    elif stage_ctx.is_subject_index_extraction_stage:
        persist_meta = persist_assets_extraction_stage(db=db, episode=episode, result_content=result_content)
    elif stage_ctx.is_script_optimization_stage:
        persist_meta = persist_script_optimization_stage(db=db, episode=episode, result_content=result_content)
    else:
        persist_meta = persist_generic_analyze_scene_stage(db=db, episode=episode, result_content=result_content)

    saved_field = persist_meta.get("saved_field")
    return {
        "saved_to_episode": True,
        "saved_episode_id": getattr(episode, "id", None),
        "saved_field": saved_field,
        "saved_chars_readback": int(persist_meta.get("saved_chars_readback") or 0),
        "stage_key": persist_meta.get("stage_key") or stage_ctx.stage_key,
        "persist_meta": persist_meta,
    }


_SCENE_TABLE_HEADER_HINT_RE = re.compile(r"(?i)\|\s*episode\s*id\s*\|\s*scene\s*id")


def extract_scene_markdown_text_from_analyze_result(result: Any) -> str:
    if isinstance(result, str):
        return result
    if not isinstance(result, dict):
        return ""

    candidates: List[str] = []
    for key in ("scenes_markdown", "result", "content", "adapted_script"):
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            candidates.append(value)
    data = result.get("data")
    if isinstance(data, dict):
        for key in ("scenes_markdown", "result", "content", "adapted_script"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                candidates.append(value)
    for text in candidates:
        if _SCENE_TABLE_HEADER_HINT_RE.search(text):
            return text
    return candidates[0] if candidates else ""


def validate_scene_markdown_import_text(script_text: Any) -> None:
    from fastapi import HTTPException

    if str(script_text or "").strip():
        return
    logger.warning("[analyze_scene.import] scene_markdown empty text, skip progress import")
    raise HTTPException(status_code=422, detail="SCENE_MARKDOWN_EMPTY")


def import_scene_markdown_stage(
    *,
    db: Session,
    project_id: int,
    episode_id: int,
    script_text: str,
    script_id: Optional[str] = None,
    partial: bool = False,
    target_scene_id: Optional[str] = None,
) -> Dict[str, Any]:
    from app.services.script_analysis_flow import sync_scene_units_from_script_text

    validate_scene_markdown_import_text(script_text)
    sync_result = sync_scene_units_from_script_text(
        db,
        project_id=int(project_id),
        episode_id=int(episode_id),
        script_text=script_text,
        script_id=script_id,
        partial=bool(partial),
        target_scene_id=str(target_scene_id or '').strip() or None,
    )
    logger.info(
        "[analyze_scene.import] stage=%s project_id=%s episode_id=%s scene_count=%s parse_source=%s",
        STAGE_SCENE_MARKDOWN,
        project_id,
        episode_id,
        int(sync_result.get("scene_count") or 0),
        sync_result.get("parse_source") or "unknown",
    )
    return {
        "stage_key": STAGE_SCENE_MARKDOWN,
        "import_target": "script_progress_scene_units",
        "scene_count": int(sync_result.get("scene_count") or 0),
        "scene_ids": list(sync_result.get("scene_ids") or []),
        "parse_source": sync_result.get("parse_source"),
        "sync_result": sync_result,
    }


def import_analyze_scene_stage_result(
    *,
    db: Session,
    stage_key: str,
    project_id: int,
    episode_id: int,
    analyze_result: Any,
    script_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    if stage_key != STAGE_SCENE_MARKDOWN:
        return None

    script_text = extract_scene_markdown_text_from_analyze_result(analyze_result)
    return import_scene_markdown_stage(
        db=db,
        project_id=project_id,
        episode_id=episode_id,
        script_text=script_text,
        script_id=script_id,
    )
