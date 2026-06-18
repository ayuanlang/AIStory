from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.time_utils import now_bj_iso
from app.models import all_models as models
from .analyze_scene_stages import (
    STAGE_ASSETS_EXTRACTION,
    STAGE_ENTITY_DESIGN,
    STAGE_GENERIC,
    STAGE_SCENE_MARKDOWN,
    STAGE_SCRIPT_OPTIMIZATION,
    AnalyzeSceneStageContext,
    extract_scene_markdown_text_from_analyze_result,
    import_analyze_scene_stage_result,
    import_scene_markdown_stage,
    persist_analyze_scene_stage_result,
    persist_assets_extraction_stage,
    persist_entity_design_stage,
    persist_generic_analyze_scene_stage,
    persist_scene_markdown_stage,
    persist_script_optimization_stage,
    resolve_analyze_scene_stage,
    validate_analyze_scene_llm_finish_reason,
    validate_scene_markdown_import_text,
)
from .registry import (
    DEFAULT_STAGE3_AUTO_START,
    SCRIPT_ANALYSIS_FLOW_CONFIG_KEY,
    build_script_analysis_flow_plan,
    get_script_analysis_flow_registry,
    normalize_script_analysis_flow_config,
)

ScriptProgressSceneUnit = models.ScriptProgressSceneUnit
ScriptProgressPipelineNode = models.ScriptProgressPipelineNode
ScriptProgressIssue = getattr(models, "ScriptProgressIssue", None)

NODE_STATUS_VALUES: Set[str] = {
    "queued",
    "running",
    "success",
    "warning",
    "failed",
    "blocked",
    "skipped",
}

SCENES_BLOCK_START_TOKEN = "[SCENES_BLOCK_START]"
SCENES_BLOCK_END_TOKEN = "[SCENES_BLOCK_END]"
SCENE_START_PATTERN = re.compile(r"\[SCENE_START:([^\]\s]+)\]")
SCENE_END_PATTERN = re.compile(r"\[SCENE_END:([^\]\s]+)\]")

ISSUE_SEVERITY_VALUES = {"INFO", "WARNING", "BLOCKER"}


class SceneMarkerParseError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = str(code or "SCENE_MARKER_PARSE_ERROR")


@dataclass
class ParsedSceneUnit:
    scene_id: str
    scene_order: int
    scene_text: str
    marker_start_token: str
    marker_end_token: str


def normalize_node_status(value: Optional[str], default: str = "queued") -> str:
    candidate = str(value or "").strip().lower()
    if candidate in NODE_STATUS_VALUES:
        return candidate
    fallback = str(default or "").strip().lower()
    return fallback if fallback in NODE_STATUS_VALUES else "queued"


def parse_scene_units_from_markers(script_text: str) -> List[ParsedSceneUnit]:
    text = str(script_text or "")
    if not text.strip():
        raise SceneMarkerParseError("SCENE_MARKER_BLOCK_MISSING", "script text is empty")

    start_idx = text.find(SCENES_BLOCK_START_TOKEN)
    end_idx = text.find(SCENES_BLOCK_END_TOKEN)
    if start_idx < 0 or end_idx < 0 or end_idx <= start_idx:
        raise SceneMarkerParseError("SCENE_MARKER_BLOCK_MISSING", "scene block markers missing or invalid order")

    block_text = text[start_idx + len(SCENES_BLOCK_START_TOKEN):end_idx]
    if not block_text.strip():
        raise SceneMarkerParseError("SCENE_MARKER_EMPTY_BLOCK", "scene block is empty")

    cursor = 0
    seen_scene_ids: Set[str] = set()
    parsed: List[ParsedSceneUnit] = []

    while True:
        start_match = SCENE_START_PATTERN.search(block_text, cursor)
        if not start_match:
            break

        scene_id = str(start_match.group(1) or "").strip()
        if not scene_id:
            raise SceneMarkerParseError("SCENE_MARKER_PAIR_MISMATCH", "scene start marker has empty scene_id")
        if scene_id in seen_scene_ids:
            raise SceneMarkerParseError("SCENE_MARKER_DUPLICATE_SCENE_ID", f"duplicate scene_id: {scene_id}")
        seen_scene_ids.add(scene_id)

        end_match = SCENE_END_PATTERN.search(block_text, start_match.end())
        if not end_match:
            raise SceneMarkerParseError("SCENE_MARKER_PAIR_MISMATCH", f"missing scene end marker for {scene_id}")
        end_scene_id = str(end_match.group(1) or "").strip()
        if end_scene_id != scene_id:
            raise SceneMarkerParseError(
                "SCENE_MARKER_PAIR_MISMATCH",
                f"scene marker mismatch: start={scene_id}, end={end_scene_id}",
            )

        scene_text = block_text[start_match.end():end_match.start()].strip()
        parsed.append(
            ParsedSceneUnit(
                scene_id=scene_id,
                scene_order=len(parsed) + 1,
                scene_text=scene_text,
                marker_start_token=start_match.group(0),
                marker_end_token=end_match.group(0),
            )
        )
        cursor = end_match.end()

    if not parsed:
        raise SceneMarkerParseError("SCENE_MARKER_NO_SCENES", "no scenes found between scene block markers")

    trailing = block_text[cursor:].strip()
    if trailing:
        raise SceneMarkerParseError("SCENE_MARKER_TRAILING_CONTENT", "unmatched trailing content after scene markers")

    return parsed


def _normalize_scene_table_header(value: Any) -> str:
    return re.sub(r"[\s_\-./()]", "", str(value or "").strip().lower())


def _split_scene_table_cells(line: str) -> List[str]:
    cells = [str(cell or "").strip() for cell in str(line or "").split("|")]
    if cells and cells[0] == "":
        cells.pop(0)
    if cells and cells[-1] == "":
        cells.pop()
    return cells


def _is_scene_table_separator_line(line: str) -> bool:
    text = str(line or "").strip()
    if not text:
        return False
    return bool(re.search(r"\|\s*:?-{3,}:?", text)) or bool(re.match(r"^[\s\|:\-]*$", text))


def _find_scene_table_col_idx(normalized_headers: List[str], aliases: List[str]) -> int:
    alias_set = {_normalize_scene_table_header(alias) for alias in aliases}
    for idx, header in enumerate(normalized_headers):
        normalized = _normalize_scene_table_header(header)
        if any(alias in normalized or normalized in alias for alias in alias_set):
            return idx
    return -1


def _collect_scene_table_blocks(script_text: str) -> List[str]:
    lines = str(script_text or "").splitlines()
    blocks: List[List[str]] = []
    current: List[str] = []

    def flush() -> None:
        if len(current) >= 2:
            blocks.append(list(current))
        current.clear()

    for raw_line in lines:
        line = str(raw_line or "").strip()
        if line.startswith("|") and "|" in line:
            current.append(line)
        else:
            flush()
    flush()
    return ["\n".join(block).strip() for block in blocks if block]


def _scene_table_row_has_identity(cells: List[str], scene_id_idx: int, scene_no_idx: int, scene_name_idx: int) -> bool:
    scene_id = str(cells[scene_id_idx] if scene_id_idx >= 0 and scene_id_idx < len(cells) else "").strip()
    scene_no = str(cells[scene_no_idx] if scene_no_idx >= 0 and scene_no_idx < len(cells) else "").strip()
    scene_name = str(cells[scene_name_idx] if scene_name_idx >= 0 and scene_name_idx < len(cells) else "").strip()
    return bool(scene_id or scene_no or scene_name)


def _scene_table_cell_value(cells: List[str], idx: int) -> str:
    if idx < 0 or idx >= len(cells):
        return ""
    return str(cells[idx] or "").strip()


def _build_scene_text_from_table_row(
    cells: List[str],
    *,
    core_info_idx: int,
    adapted_idx: int,
    scene_name_idx: int,
    environment_idx: int,
    linked_characters_idx: int,
    key_props_idx: int,
) -> str:
    parts = [
        _scene_table_cell_value(cells, core_info_idx),
        _scene_table_cell_value(cells, adapted_idx),
        _scene_table_cell_value(cells, environment_idx),
        _scene_table_cell_value(cells, linked_characters_idx),
        _scene_table_cell_value(cells, key_props_idx),
    ]
    if scene_name_idx >= 0:
        scene_name = _scene_table_cell_value(cells, scene_name_idx)
        if scene_name:
            parts.insert(0, f"Scene Name: {scene_name}")
    return "\n\n".join(part for part in parts if part).strip()


def parse_scene_units_from_scenes_table(script_text: str) -> List[ParsedSceneUnit]:
    text = str(script_text or "")
    if not text.strip():
        raise SceneMarkerParseError("SCENES_TABLE_EMPTY", "scenes table text is empty")

    blocks = _collect_scene_table_blocks(text)
    if not blocks:
        raise SceneMarkerParseError("SCENES_TABLE_BLOCK_MISSING", "no markdown scenes table detected")

    parsed: List[ParsedSceneUnit] = []
    seen_scene_ids: Set[str] = set()

    for block in blocks:
        lines = [line.strip() for line in str(block or "").splitlines() if str(line or "").strip()]
        if len(lines) < 2:
            continue

        headers = _split_scene_table_cells(lines[0])
        normalized_headers = [_normalize_scene_table_header(header) for header in headers]
        scene_id_idx = _find_scene_table_col_idx(normalized_headers, ["sceneid", "场景id"])
        scene_no_idx = _find_scene_table_col_idx(normalized_headers, ["sceneno", "场次序号", "场次"])
        scene_name_idx = _find_scene_table_col_idx(normalized_headers, ["scenename", "场景名", "场景名称"])
        core_info_idx = _find_scene_table_col_idx(normalized_headers, ["coresceneinfo", "核心场景信息"])
        adapted_idx = _find_scene_table_col_idx(
            normalized_headers,
            ["adaptedscripttext", "改编剧本文本", "改编剧本", "originalscripttext", "原始剧本文本", "scripttext"],
        )
        environment_idx = _find_scene_table_col_idx(normalized_headers, ["environmentname", "环境名", "环境名称", "环境"])
        linked_characters_idx = _find_scene_table_col_idx(normalized_headers, ["linkedcharacters", "关联角色", "角色", "characters"])
        key_props_idx = _find_scene_table_col_idx(normalized_headers, ["keyprops", "关键道具", "道具", "props"])

        if scene_id_idx < 0 and scene_no_idx < 0 and scene_name_idx < 0:
            continue

        current_unit: Optional[ParsedSceneUnit] = None

        for line in lines[1:]:
            if _is_scene_table_separator_line(line):
                continue

            cells = _split_scene_table_cells(line)
            if not cells:
                continue
            while len(cells) < len(headers):
                cells.append("")

            if _scene_table_row_has_identity(cells, scene_id_idx, scene_no_idx, scene_name_idx):
                scene_id = _scene_table_cell_value(cells, scene_id_idx)
                scene_no = _scene_table_cell_value(cells, scene_no_idx)
                scene_name = _scene_table_cell_value(cells, scene_name_idx)
                if not scene_id:
                    if scene_no:
                        scene_id = scene_no
                    elif scene_name:
                        scene_id = scene_name
                if not scene_id:
                    continue
                if scene_id in seen_scene_ids:
                    raise SceneMarkerParseError("SCENES_TABLE_DUPLICATE_SCENE_ID", f"duplicate scene_id: {scene_id}")
                seen_scene_ids.add(scene_id)

                scene_text = _build_scene_text_from_table_row(
                    cells,
                    core_info_idx=core_info_idx,
                    adapted_idx=adapted_idx,
                    scene_name_idx=scene_name_idx,
                    environment_idx=environment_idx,
                    linked_characters_idx=linked_characters_idx,
                    key_props_idx=key_props_idx,
                )
                current_unit = ParsedSceneUnit(
                    scene_id=scene_id,
                    scene_order=len(parsed) + 1,
                    scene_text=scene_text,
                    marker_start_token="scenes_table",
                    marker_end_token="scenes_table",
                )
                parsed.append(current_unit)
                continue

            if current_unit is None:
                continue

            continuation_parts = [
                _scene_table_cell_value(cells, core_info_idx),
                _scene_table_cell_value(cells, adapted_idx),
                _scene_table_cell_value(cells, environment_idx),
                _scene_table_cell_value(cells, linked_characters_idx),
                _scene_table_cell_value(cells, key_props_idx),
            ]
            continuation_text = "\n\n".join(part for part in continuation_parts if part).strip()
            if not continuation_text:
                continue
            if current_unit.scene_text:
                current_unit.scene_text = f"{current_unit.scene_text}\n\n{continuation_text}".strip()
            else:
                current_unit.scene_text = continuation_text

    if not parsed:
        raise SceneMarkerParseError("SCENES_TABLE_NO_SCENES", "no valid scenes found in scenes table")

    return parsed


def _upsert_scene_unit(
    db: Session,
    *,
    project_id: int,
    episode_id: int,
    script_id: Optional[str],
    unit: ParsedSceneUnit,
) -> None:
    now_iso = now_bj_iso()
    row = (
        db.query(ScriptProgressSceneUnit)
        .filter(
            ScriptProgressSceneUnit.project_id == int(project_id),
            ScriptProgressSceneUnit.episode_id == int(episode_id),
            ScriptProgressSceneUnit.scene_id == str(unit.scene_id),
        )
        .first()
    )
    if row is None:
        db.add(
            ScriptProgressSceneUnit(
                project_id=int(project_id),
                episode_id=int(episode_id),
                script_id=script_id,
                scene_id=unit.scene_id,
                scene_order=unit.scene_order,
                scene_text=unit.scene_text,
                marker_start_token=unit.marker_start_token,
                marker_end_token=unit.marker_end_token,
                parse_status="success",
                import_status="queued",
                parse_error_code=None,
                created_at=now_iso,
                updated_at=now_iso,
            )
        )
        return

    row.script_id = script_id
    row.scene_order = unit.scene_order
    row.scene_text = unit.scene_text
    row.marker_start_token = unit.marker_start_token
    row.marker_end_token = unit.marker_end_token
    row.parse_status = "success"
    row.parse_error_code = None
    row.updated_at = now_iso


def sync_scene_units_from_script_text(
    db: Session,
    *,
    project_id: int,
    episode_id: int,
    script_text: str,
    script_id: Optional[str] = None,
) -> Dict[str, object]:
    parse_source = "scenes_table"
    try:
        # Stage 2.2 output contract is Part 1: Scenes Table only.
        # Parse table first; marker parsing is kept as backward compatibility.
        units = parse_scene_units_from_scenes_table(script_text)
    except SceneMarkerParseError:
        units = parse_scene_units_from_markers(script_text)
        parse_source = "scene_markers"
    now_iso = now_bj_iso()
    existing_rows = (
        db.query(ScriptProgressSceneUnit)
        .filter(
            ScriptProgressSceneUnit.project_id == int(project_id),
            ScriptProgressSceneUnit.episode_id == int(episode_id),
        )
        .all()
    )
    existing_by_scene: Dict[str, ScriptProgressSceneUnit] = {
        str(row.scene_id): row for row in existing_rows if str(getattr(row, "scene_id", "")).strip()
    }

    incoming_scene_ids = {unit.scene_id for unit in units}
    for unit in units:
        _upsert_scene_unit(
            db,
            project_id=project_id,
            episode_id=episode_id,
            script_id=script_id,
            unit=unit,
        )

    for scene_id, row in existing_by_scene.items():
        if scene_id in incoming_scene_ids:
            continue
        row.import_status = "skipped"
        row.parse_status = "failed"
        row.parse_error_code = "SCENE_MARKER_NOT_FOUND_IN_LATEST_SCRIPT"
        row.updated_at = now_iso

    return {
        "project_id": int(project_id),
        "episode_id": int(episode_id),
        "script_id": script_id,
        "scene_count": len(units),
        "scene_ids": [unit.scene_id for unit in units],
        "parse_source": parse_source,
    }


def upsert_pipeline_node_status(
    db: Session,
    *,
    project_id: int,
    episode_id: int,
    node_name: str,
    status: str,
    script_id: Optional[str] = None,
    scene_id: Optional[str] = None,
    asset_type: Optional[str] = None,
    progress_percent: Optional[float] = None,
    depends_on: Optional[List[str]] = None,
    runtime_meta: Optional[Dict[str, object]] = None,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
) -> ScriptProgressPipelineNode:
    normalized_status = normalize_node_status(status)
    now_iso = now_bj_iso()
    node_name_norm = str(node_name or "").strip()
    scene_id_norm = str(scene_id or "").strip() or None
    asset_type_norm = str(asset_type or "").strip() or None
    script_id_norm = str(script_id or "").strip() or None

    def _query_existing() -> Optional[ScriptProgressPipelineNode]:
        return (
            db.query(ScriptProgressPipelineNode)
            .filter(
                ScriptProgressPipelineNode.project_id == int(project_id),
                ScriptProgressPipelineNode.episode_id == int(episode_id),
                ScriptProgressPipelineNode.node_name == node_name_norm,
                ScriptProgressPipelineNode.scene_id == scene_id_norm,
                ScriptProgressPipelineNode.asset_type == asset_type_norm,
            )
            .first()
        )

    row = _query_existing()
    if row is None:
        row = ScriptProgressPipelineNode(
            project_id=int(project_id),
            episode_id=int(episode_id),
            script_id=script_id_norm,
            scene_id=scene_id_norm,
            node_name=node_name_norm,
            asset_type=asset_type_norm,
            status=normalized_status,
            progress_percent=float(progress_percent if progress_percent is not None else 0.0),
            started_at=now_iso if normalized_status == "running" else None,
            ended_at=now_iso if normalized_status in {"success", "warning", "failed", "blocked", "skipped"} else None,
            depends_on=list(depends_on or []),
            runtime_meta=dict(runtime_meta or {}),
            last_error_code=error_code,
            last_error_message=error_message,
            created_at=now_iso,
            updated_at=now_iso,
        )
        try:
            with db.begin_nested():
                db.add(row)
                db.flush()
            return row
        except IntegrityError:
            # Another concurrent request inserted the same scoped node first.
            row = _query_existing()
            if row is None:
                raise

    previous_started_at = str(getattr(row, "started_at", "") or "").strip()
    row.script_id = script_id_norm
    row.status = normalized_status
    if progress_percent is not None:
        row.progress_percent = float(progress_percent)
    if depends_on is not None:
        row.depends_on = list(depends_on)
    if runtime_meta is not None:
        row.runtime_meta = dict(runtime_meta or {})
    if normalized_status == "running" and not previous_started_at:
        row.started_at = now_iso
    if normalized_status in {"success", "warning", "failed", "blocked", "skipped"}:
        row.ended_at = now_iso
    row.last_error_code = error_code
    row.last_error_message = error_message
    row.updated_at = now_iso
    return row


def raise_progress_issue(
    db: Session,
    *,
    project_id: int,
    issue_code: str,
    title: str,
    severity: str = "WARNING",
    owner_domain: Optional[str] = None,
    details: Optional[str] = None,
    node_ref: Optional[str] = None,
    episode_id: Optional[int] = None,
    script_id: Optional[str] = None,
    scene_id: Optional[str] = None,
) -> None:
    if ScriptProgressIssue is None:
        return

    sev = str(severity or "WARNING").strip().upper()
    if sev not in ISSUE_SEVERITY_VALUES:
        sev = "WARNING"
    now_iso = now_bj_iso()
    row = (
        db.query(ScriptProgressIssue)
        .filter(
            ScriptProgressIssue.project_id == int(project_id),
            ScriptProgressIssue.episode_id == (int(episode_id) if episode_id is not None else None),
            ScriptProgressIssue.script_id == (str(script_id) if script_id is not None else None),
            ScriptProgressIssue.scene_id == (str(scene_id) if scene_id is not None else None),
            ScriptProgressIssue.issue_code == str(issue_code),
            ScriptProgressIssue.status != "resolved",
        )
        .first()
    )
    if row is None:
        db.add(
            ScriptProgressIssue(
                project_id=int(project_id),
                episode_id=(int(episode_id) if episode_id is not None else None),
                script_id=(str(script_id) if script_id is not None else None),
                scene_id=(str(scene_id) if scene_id is not None else None),
                severity=sev,
                status="open",
                issue_code=str(issue_code),
                title=str(title or issue_code),
                details=(str(details)[:4000] if details else None),
                owner_domain=(str(owner_domain) if owner_domain else None),
                node_ref=(str(node_ref) if node_ref else None),
                first_seen_at=now_iso,
                last_seen_at=now_iso,
                created_at=now_iso,
                updated_at=now_iso,
            )
        )
        return

    row.severity = sev
    row.title = str(title or row.title or issue_code)
    row.details = str(details)[:4000] if details else row.details
    row.owner_domain = str(owner_domain) if owner_domain else row.owner_domain
    row.node_ref = str(node_ref) if node_ref else row.node_ref
    row.last_seen_at = now_iso
    row.updated_at = now_iso


def resolve_progress_issue(
    db: Session,
    *,
    issue_id: int,
) -> bool:
    if ScriptProgressIssue is None:
        return False
    row = db.query(ScriptProgressIssue).filter(ScriptProgressIssue.id == int(issue_id)).first()
    if row is None:
        return False
    now_iso = now_bj_iso()
    row.status = "resolved"
    row.last_seen_at = now_iso
    row.updated_at = now_iso
    return True


__all__ = [
    "AnalyzeSceneStageContext",
    "DEFAULT_STAGE3_AUTO_START",
    "NODE_STATUS_VALUES",
    "SCENES_BLOCK_END_TOKEN",
    "SCENES_BLOCK_START_TOKEN",
    "SCRIPT_ANALYSIS_FLOW_CONFIG_KEY",
    "STAGE_ASSETS_EXTRACTION",
    "STAGE_ENTITY_DESIGN",
    "STAGE_GENERIC",
    "STAGE_SCENE_MARKDOWN",
    "STAGE_SCRIPT_OPTIMIZATION",
    "SceneMarkerParseError",
    "build_script_analysis_flow_plan",
    "get_script_analysis_flow_registry",
    "normalize_node_status",
    "normalize_script_analysis_flow_config",
    "parse_scene_units_from_markers",
    "parse_scene_units_from_scenes_table",
    "extract_scene_markdown_text_from_analyze_result",
    "import_analyze_scene_stage_result",
    "import_scene_markdown_stage",
    "persist_analyze_scene_stage_result",
    "persist_assets_extraction_stage",
    "persist_entity_design_stage",
    "persist_generic_analyze_scene_stage",
    "persist_scene_markdown_stage",
    "persist_script_optimization_stage",
    "raise_progress_issue",
    "resolve_analyze_scene_stage",
    "resolve_progress_issue",
    "sync_scene_units_from_script_text",
    "upsert_pipeline_node_status",
    "validate_analyze_scene_llm_finish_reason",
    "validate_scene_markdown_import_text",
]