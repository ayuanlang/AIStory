from __future__ import annotations

import json
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
SCENES_BLOCK_START_PATTERN = re.compile(r"`?\[SCENES_BLOCK_START\]`?", re.IGNORECASE)
SCENES_BLOCK_END_PATTERN = re.compile(r"`?\[SCENES_BLOCK_END\]`?", re.IGNORECASE)
SCENE_START_PATTERN = re.compile(r"`?\[SCENE_START:([^\]\s]+)\]`?", re.IGNORECASE)
SCENE_END_PATTERN = re.compile(r"`?\[SCENE_END:([^\]\s]+)\]`?", re.IGNORECASE)

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
    scene_markdown: str = ""


def normalize_node_status(value: Optional[str], default: str = "queued") -> str:
    candidate = str(value or "").strip().lower()
    if candidate in NODE_STATUS_VALUES:
        return candidate
    fallback = str(default or "").strip().lower()
    return fallback if fallback in NODE_STATUS_VALUES else "queued"


def _normalize_scene_marker_script_text(script_text: str) -> str:
    text = str(script_text or "").replace("\r\n", "\n")
    if not text.strip():
        return ""
    text = re.sub(
        r"`+(\[(?:SCENES?_BLOCK_(?:START|END)|SCENE_(?:START|END):[^\]]+)\])`+",
        r"\1",
        text,
        flags=re.IGNORECASE,
    )
    return text


def _find_scenes_block_span(text: str) -> tuple[int, int, int, int]:
    normalized = _normalize_scene_marker_script_text(text)
    start_match = SCENES_BLOCK_START_PATTERN.search(normalized)
    if not start_match:
        raise SceneMarkerParseError("SCENE_MARKER_BLOCK_MISSING", "scene block markers missing or invalid order")
    after_start = normalized[start_match.end():]
    end_match = SCENES_BLOCK_END_PATTERN.search(after_start)
    if not end_match:
        raise SceneMarkerParseError("SCENE_MARKER_BLOCK_MISSING", "scene block end marker missing")
    block_start = start_match.end()
    block_end = start_match.end() + end_match.start()
    return start_match.start(), start_match.end(), block_end, start_match.end() + end_match.end()


def parse_scene_units_from_markers(script_text: str) -> List[ParsedSceneUnit]:
    text = _normalize_scene_marker_script_text(script_text)
    if not text.strip():
        raise SceneMarkerParseError("SCENE_MARKER_BLOCK_MISSING", "script text is empty")

    _, block_content_start, block_content_end, _ = _find_scenes_block_span(text)
    block_text = text[block_content_start:block_content_end]
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
        if SCENE_START_PATTERN.search(trailing) or SCENE_END_PATTERN.search(trailing):
            raise SceneMarkerParseError("SCENE_MARKER_TRAILING_CONTENT", "unmatched trailing content after scene markers")
        # Allow non-marker prose between the last scene end and block end.

    return parsed


def load_scene_units_from_progress_rows(
    db: Session,
    *,
    project_id: int,
    episode_id: int,
) -> List[ParsedSceneUnit]:
    if ScriptProgressSceneUnit is None:
        return []
    rows = (
        db.query(ScriptProgressSceneUnit)
        .filter(
            ScriptProgressSceneUnit.project_id == int(project_id),
            ScriptProgressSceneUnit.episode_id == int(episode_id),
        )
        .order_by(ScriptProgressSceneUnit.scene_order.asc(), ScriptProgressSceneUnit.id.asc())
        .all()
    )
    units: List[ParsedSceneUnit] = []
    for row in rows:
        scene_id = str(getattr(row, "scene_id", "") or "").strip()
        scene_text = str(getattr(row, "scene_text", "") or "").strip()
        if not scene_id or not scene_text:
            continue
        start_token = str(getattr(row, "marker_start_token", "") or "").strip() or f"[SCENE_START:{scene_id}]"
        end_token = str(getattr(row, "marker_end_token", "") or "").strip() or f"[SCENE_END:{scene_id}]"
        units.append(
            ParsedSceneUnit(
                scene_id=scene_id,
                scene_order=int(getattr(row, "scene_order", None) or (len(units) + 1)),
                scene_text=scene_text,
                marker_start_token=start_token,
                marker_end_token=end_token,
                scene_markdown=str(getattr(row, "scene_markdown", "") or "").strip(),
            )
        )
    return units


def resolve_scene_units_for_markdown_orchestration(
    db: Session,
    *,
    user_text: str,
    adapted_script_text: str,
    project_id: int = 0,
    episode_id: int = 0,
    episode_adaptation_text: str = "",
) -> tuple[List[ParsedSceneUnit], str]:
    parse_errors: List[str] = []
    candidate_sources = [
        ("adapted_script", adapted_script_text),
        ("user_text", user_text),
        ("episode_adaptation", episode_adaptation_text),
    ]
    for source_name, source_text in candidate_sources:
        text = str(source_text or "").strip()
        if not text:
            continue
        try:
            units = parse_scene_units_from_markers(text)
            if units:
                return units, source_name
        except SceneMarkerParseError as exc:
            parse_errors.append(f"{source_name}:{exc.code}")

    if int(project_id) > 0 and int(episode_id) > 0:
        units = load_scene_units_from_progress_rows(
            db,
            project_id=int(project_id),
            episode_id=int(episode_id),
        )
        if units:
            return units, "progress_db"

    return [], "|".join(parse_errors) if parse_errors else "no_scene_units"


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
                    scene_markdown=_build_scene_markdown_from_table_row(headers, cells),
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


def wrap_scene_unit_as_script_block(unit: ParsedSceneUnit) -> str:
    return "\n".join(
        [
            SCENES_BLOCK_START_TOKEN,
            unit.marker_start_token,
            unit.scene_text,
            unit.marker_end_token,
            SCENES_BLOCK_END_TOKEN,
        ]
    ).strip()


def extract_adapted_script_from_beats_user_input(user_text: str) -> str:
    text = str(user_text or "")
    match = re.search(r"\[优化后剧本[^\]]*\]\s*\n([\s\S]*)$", text)
    if match:
        return str(match.group(1) or "").strip()
    normalized = _normalize_scene_marker_script_text(text)
    start_match = SCENES_BLOCK_START_PATTERN.search(normalized)
    if start_match:
        end_match = SCENES_BLOCK_END_PATTERN.search(normalized, start_match.end())
        if end_match:
            return normalized[start_match.start(): start_match.end() + end_match.end()].strip()
    start_idx = text.find(SCENES_BLOCK_START_TOKEN)
    if start_idx >= 0:
        return text[start_idx:].strip()
    return text.strip()


def merge_scenes_table_markdown_outputs(outputs: List[str]) -> str:
    merged_headers: List[str] = []
    merged_rows: List[List[str]] = []

    for raw in outputs:
        text = str(raw or "").strip()
        if not text:
            continue
        blocks = _collect_scene_table_blocks(text)
        for block in blocks:
            lines = [line.strip() for line in str(block or "").splitlines() if str(line or "").strip()]
            if len(lines) < 2:
                continue
            headers = _split_scene_table_cells(lines[0])
            normalized_headers = [_normalize_scene_table_header(header) for header in headers]
            if not merged_headers:
                merged_headers = headers
            scene_id_idx = _find_scene_table_col_idx(normalized_headers, ["sceneid", "场景id"])
            scene_no_idx = _find_scene_table_col_idx(normalized_headers, ["sceneno", "场次序号", "场次"])
            scene_name_idx = _find_scene_table_col_idx(normalized_headers, ["scenename", "场景名", "场景名称"])
            if scene_id_idx < 0 and scene_no_idx < 0 and scene_name_idx < 0:
                continue
            for line in lines[1:]:
                if _is_scene_table_separator_line(line):
                    continue
                cells = _split_scene_table_cells(line)
                if not cells:
                    continue
                while len(cells) < len(headers):
                    cells.append("")
                if not _scene_table_row_has_identity(cells, scene_id_idx, scene_no_idx, scene_name_idx):
                    continue
                row = list(cells)
                while len(row) < len(merged_headers):
                    row.append("")
                merged_rows.append(row[: len(merged_headers)])

    if not merged_headers or not merged_rows:
        return ""

    normalized_merged_headers = [_normalize_scene_table_header(header) for header in merged_headers]
    scene_no_idx = _find_scene_table_col_idx(normalized_merged_headers, ["sceneno", "场次序号", "场次"])
    if scene_no_idx >= 0:
        for idx, row in enumerate(merged_rows):
            while len(row) <= scene_no_idx:
                row.append("")
            row[scene_no_idx] = str(idx + 1)

    header_line = "| " + " | ".join(merged_headers) + " |"
    separator_line = "| " + " | ".join(":---" for _ in merged_headers) + " |"
    row_lines = ["| " + " | ".join(row) + " |" for row in merged_rows]
    table = "\n".join([header_line, separator_line, *row_lines])
    return f"### Part 1: Scenes Table\n\n{table}".strip()


def _build_scene_markdown_from_table_row(headers: List[str], cells: List[str]) -> str:
    if not headers or not cells:
        return ""
    normalized_headers = [_normalize_scene_table_header(header) for header in headers]
    scene_id_idx = _find_scene_table_col_idx(normalized_headers, ["sceneid", "场景id"])
    scene_no_idx = _find_scene_table_col_idx(normalized_headers, ["sceneno", "场次序号", "场次"])
    scene_name_idx = _find_scene_table_col_idx(normalized_headers, ["scenename", "场景名", "场景名称"])
    scene_id = _scene_table_cell_value(cells, scene_id_idx)
    scene_no = _scene_table_cell_value(cells, scene_no_idx)
    scene_name = _scene_table_cell_value(cells, scene_name_idx)
    if not scene_id:
        scene_id = scene_no or scene_name
    row = list(cells)
    while len(row) < len(headers):
        row.append("")
    header_line = "| " + " | ".join(headers) + " |"
    separator_line = "| " + " | ".join(":---" for _ in headers) + " |"
    row_line = "| " + " | ".join(row[: len(headers)]) + " |"
    table = "\n".join([header_line, separator_line, row_line])
    title = scene_name or scene_id or "Scene"
    return f"### Part 1: Scenes Table\n\n#### {title}\n\n{table}".strip()


def _upsert_scene_unit(
    db: Session,
    *,
    project_id: int,
    episode_id: int,
    script_id: Optional[str],
    unit: ParsedSceneUnit,
    import_status: Optional[str] = None,
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
                scene_markdown=str(getattr(unit, "scene_markdown", "") or "") or None,
                marker_start_token=unit.marker_start_token,
                marker_end_token=unit.marker_end_token,
                parse_status="success",
                import_status=str(import_status) if import_status is not None else "queued",
                parse_error_code=None,
                created_at=now_iso,
                updated_at=now_iso,
            )
        )
        return

    row.script_id = script_id
    row.scene_order = unit.scene_order
    row.scene_text = unit.scene_text
    row.scene_markdown = str(getattr(unit, "scene_markdown", "") or "") or None
    row.marker_start_token = unit.marker_start_token
    row.marker_end_token = unit.marker_end_token
    row.parse_status = "success"
    row.parse_error_code = None
    if import_status is not None:
        row.import_status = str(import_status)
    row.updated_at = now_iso


def sync_scene_units_from_script_text(
    db: Session,
    *,
    project_id: int,
    episode_id: int,
    script_text: str,
    script_id: Optional[str] = None,
    prefer_markers: bool = False,
    partial: bool = False,
    target_scene_id: Optional[str] = None,
) -> Dict[str, object]:
    parse_source = "scenes_table"
    if prefer_markers:
        units = parse_scene_units_from_markers(script_text)
        parse_source = "scene_markers"
    else:
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
    resolved_target_scene_id = str(target_scene_id or "").strip() or None
    for unit in units:
        if partial and resolved_target_scene_id:
            unit.scene_id = resolved_target_scene_id
            incoming_scene_ids.add(resolved_target_scene_id)
        _upsert_scene_unit(
            db,
            project_id=project_id,
            episode_id=episode_id,
            script_id=script_id,
            unit=unit,
            import_status="success" if partial else None,
        )

    if not partial:
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


def sync_scene_units_from_markers(
    db: Session,
    *,
    project_id: int,
    episode_id: int,
    script_text: str,
    script_id: Optional[str] = None,
) -> Dict[str, object]:
    return sync_scene_units_from_script_text(
        db,
        project_id=project_id,
        episode_id=episode_id,
        script_text=script_text,
        script_id=script_id,
        prefer_markers=True,
    )


def update_scene_unit_orchestration_status(
    db: Session,
    *,
    project_id: int,
    episode_id: int,
    scene_id: str,
    import_status: Optional[str] = None,
    parse_status: Optional[str] = None,
    scene_markdown: Optional[str] = None,
    parse_error_code: Optional[str] = None,
) -> None:
    row = (
        db.query(ScriptProgressSceneUnit)
        .filter(
            ScriptProgressSceneUnit.project_id == int(project_id),
            ScriptProgressSceneUnit.episode_id == int(episode_id),
            ScriptProgressSceneUnit.scene_id == str(scene_id),
        )
        .first()
    )
    if row is None:
        return
    now_iso = now_bj_iso()
    if import_status is not None:
        row.import_status = str(import_status)
    if parse_status is not None:
        row.parse_status = str(parse_status)
    if scene_markdown is not None:
        row.scene_markdown = str(scene_markdown or "") or None
    if parse_error_code is not None:
        row.parse_error_code = str(parse_error_code) if parse_error_code else None
    row.updated_at = now_iso


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


def _load_episode_stage_outputs_obj(episode: Any) -> Dict[str, Any]:
    raw = str(getattr(episode, "ai_stage_outputs", "") or "").strip()
    if not raw:
        return {"version": 1, "stages": {}}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {"version": 1, "stages": {}}
    except Exception:
        return {"version": 1, "stages": {}}


def patch_episode_scene_markdown_by_scene(
    db: Session,
    *,
    episode: Any,
    scene_id: str,
    markdown: str,
    scene_order: Optional[int] = None,
    scene_name: Optional[str] = None,
) -> Dict[str, Any]:
    sid = str(scene_id or "").strip()
    md = str(markdown or "").strip()
    if not sid or not md:
        return {"scene_id": sid, "patched": False}

    stage_outputs = _load_episode_stage_outputs_obj(episode)
    stages = stage_outputs.setdefault("stages", {})
    stage2 = stages.setdefault("stage2", {"key": "stage2", "outputs": {}})
    outputs = stage2.setdefault("outputs", {})
    by_scene_slot = outputs.setdefault(
        "scene_markdown_by_scene",
        {
            "key": "scene_markdown_by_scene",
            "kind": "json",
            "title": "场景分析结果（分场景）",
            "content": "{}",
        },
    )
    content_raw = str(by_scene_slot.get("content") or "").strip() or "{}"
    try:
        by_scene_map = json.loads(content_raw)
        if not isinstance(by_scene_map, dict):
            by_scene_map = {}
    except Exception:
        by_scene_map = {}

    entry = dict(by_scene_map.get(sid) or {}) if isinstance(by_scene_map.get(sid), dict) else {}
    entry.update(
        {
            "scene_id": sid,
            "markdown": md,
            "updated_at": now_bj_iso(),
        }
    )
    if scene_order is not None:
        entry["scene_order"] = int(scene_order)
    if scene_name:
        entry["scene_name"] = str(scene_name).strip()
    by_scene_map[sid] = entry
    by_scene_slot["content"] = json.dumps(by_scene_map, ensure_ascii=False, indent=2)
    episode.ai_stage_outputs = json.dumps(stage_outputs, ensure_ascii=False, indent=2)
    db.commit()
    try:
        db.refresh(episode)
    except Exception:
        pass
    return {"scene_id": sid, "patched": True, "scene_count": len(by_scene_map)}


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
    "extract_adapted_script_from_beats_user_input",
    "load_scene_units_from_progress_rows",
    "merge_scenes_table_markdown_outputs",
    "parse_scene_units_from_markers",
    "parse_scene_units_from_scenes_table",
    "patch_episode_scene_markdown_by_scene",
    "resolve_scene_units_for_markdown_orchestration",
    "wrap_scene_unit_as_script_block",
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
    "sync_scene_units_from_markers",
    "sync_scene_units_from_script_text",
    "update_scene_unit_orchestration_status",
    "upsert_pipeline_node_status",
    "validate_analyze_scene_llm_finish_reason",
    "validate_scene_markdown_import_text",
]