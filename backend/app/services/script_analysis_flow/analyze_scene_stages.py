from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models import all_models as models

Episode = models.Episode

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
        entity_profile = _extract_entity_profile_prefix_before_scenes(candidate, start_idx)
        if entity_profile:
            return f"{entity_profile}\n{scenes_block}".strip()
        return scenes_block

    if re.search(r"\[SCENE_START:", candidate, flags=re.IGNORECASE):
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
        if end_marker and end_marker.start() > 0:
            candidate = candidate[: end_marker.start()].strip()
        elif fallback_end_marker and fallback_end_marker.start() > 0:
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
    text = str(stage1_text or "").replace("\r\n", "\n").strip()
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
    adapted_script = extract_stage1_adapted_script_body(raw_text) or raw_text
    visual_backfill_json = _format_project_visual_backfill_json(raw_text)
    # Always overwrite prior Stage 1 artifacts so a successful rerun cannot keep a stale copy.
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

    episode.ai_scene_analysis_subject_index = sanitize_subject_index_text(result_content)
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
    episode.ai_scene_analysis_scene_markdown = result_content
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
    episode.ai_entity_design_result = result_content
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


def extract_scene_markdown_text_from_analyze_result(result: Any) -> str:
    if isinstance(result, str):
        return result
    if not isinstance(result, dict):
        return ""
    for key in ("adapted_script", "scenes_markdown", "content", "result"):
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            return value
    data = result.get("data")
    if isinstance(data, dict):
        for key in ("adapted_script", "scenes_markdown", "content"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return ""


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
