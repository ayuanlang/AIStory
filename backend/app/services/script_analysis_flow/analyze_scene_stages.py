from __future__ import annotations

import logging
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


def persist_script_optimization_stage(
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
        STAGE_SCRIPT_OPTIMIZATION,
        getattr(episode, "id", None),
        len(result_content or ""),
    )
    return {
        "stage_key": STAGE_SCRIPT_OPTIMIZATION,
        "saved_field": "ai_scene_analysis_result",
        "saved_chars_readback": _read_persisted_chars(episode, "ai_scene_analysis_result"),
    }


def persist_assets_extraction_stage(
    *,
    db: Session,
    episode: Episode,
    result_content: str,
) -> Dict[str, Any]:
    from app.api.endpoints import sanitize_subject_index_text

    episode.ai_scene_analysis_result = result_content
    episode.ai_scene_analysis_subject_index = sanitize_subject_index_text(result_content)
    db.commit()
    try:
        db.refresh(episode)
    except Exception:
        pass
    logger.info(
        "[analyze_scene.persist] stage=%s episode_id=%s fields=ai_scene_analysis_result,ai_scene_analysis_subject_index chars=%s subject_index_chars=%s",
        STAGE_ASSETS_EXTRACTION,
        getattr(episode, "id", None),
        len(result_content or ""),
        len(str(getattr(episode, "ai_scene_analysis_subject_index", "") or "")),
    )
    return {
        "stage_key": STAGE_ASSETS_EXTRACTION,
        "saved_field": "ai_scene_analysis_result",
        "saved_subject_index_field": "ai_scene_analysis_subject_index",
        "saved_chars_readback": _read_persisted_chars(episode, "ai_scene_analysis_result"),
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
) -> Dict[str, Any]:
    from app.services.script_analysis_flow import sync_scene_units_from_script_text

    validate_scene_markdown_import_text(script_text)
    sync_result = sync_scene_units_from_script_text(
        db,
        project_id=int(project_id),
        episode_id=int(episode_id),
        script_text=script_text,
        script_id=script_id,
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
