from __future__ import annotations

import json
import logging
import re
import threading
import time
from dataclasses import dataclass, replace
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.core.time_utils import now_bj_iso
from app.models import all_models as models

logger = logging.getLogger("api_logger")
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
SCENE_START_PATTERN = re.compile(r"`?\[SCENE_START:([^\s\]]+)\]`?", re.IGNORECASE)
SCENE_END_PATTERN = re.compile(r"`?\[SCENE_END:([^\s\]]+)\]`?", re.IGNORECASE)
BEAT_START_PATTERN = re.compile(r"`?\[BEAT_START(?::([^\s\]]+))?\]`?", re.IGNORECASE)
BEAT_END_PATTERN = re.compile(r"`?\[BEAT_END(?::([^\s\]]+))?\]`?", re.IGNORECASE)
ENV_BLOCK_START_PATTERN = re.compile(r"`?\[ENV_BLOCK_START(?::([^\s\]]+))?\]`?", re.IGNORECASE)
ENV_BLOCK_END_PATTERN = re.compile(r"`?\[ENV_BLOCK_END(?::([^\s\]]+))?\]`?", re.IGNORECASE)
ENTITY_PROFILE_START_TOKEN = "[ENTITY_PROFILE_START]"
ENTITY_PROFILE_END_TOKEN = "[ENTITY_PROFILE_END]"
ENTITY_PROFILE_START_PATTERN = re.compile(
    r"`?\[ENTITY_PROFILE_START(?::([^\s\]]+))?\]`?",
    re.IGNORECASE,
)
ENTITY_PROFILE_END_PATTERN = re.compile(
    r"`?\[ENTITY_PROFILE_END(?::([^\s\]]+))?\]`?",
    re.IGNORECASE,
)
LEGACY_ENTITY_PROFILE_HEADER_PATTERN = re.compile(r"【角色设定】")
LEGACY_BEAT_LINE_PATTERN = re.compile(r"(?m)^\s*-\s*Beat\s+(\d+)\b")
LEGACY_MAIN_ENV_HEADER_PATTERN = re.compile(r"【主环境】")
LEGACY_ENV_BLOCK_END_PATTERN = re.compile(
    r"(?=\[BEAT_START|"
    r"\[SCENE_END|"
    r"【Scene实体覆盖】|"
    r"【观察视角与空间建置】|"
    r"【场景切换|"
    r"【对白拆句)",
    re.IGNORECASE,
)
SCENE_TRANSITION_HEADER_PATTERN = re.compile(r"【场景切换与首节拍转场】")
SCENE_TRANSITION_BLOCK_END_PATTERN = re.compile(
    r"(?=\[BEAT_START|"
    r"\[SCENE_END|"
    r"【对白拆句|"
    r"^\s*-\s*Beat\s+\d+\b)",
    re.IGNORECASE | re.MULTILINE,
)
BLOCK_MARKER_LINE_PATTERN = re.compile(
    r"^\s*`?\[(?:SCENES?_BLOCK_(?:START|END))\]`?\s*$",
    re.IGNORECASE | re.MULTILINE,
)
SCENE_MARKER_LINE_PATTERN = re.compile(
    r"^\s*`?\[SCENE_(?:START|END)(?::[^\]]+)?\]`?\s*$",
    re.IGNORECASE | re.MULTILINE,
)
MIN_SCENE_BEATS_CHARS = 20
SCENE_NAME_HEADER_PATTERN = re.compile(r"【场景名称】\s*[^\n【]+")

ISSUE_SEVERITY_VALUES = {"INFO", "WARNING", "BLOCKER"}


class SceneMarkerParseError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = str(code or "SCENE_MARKER_PARSE_ERROR")


class SceneBeatsTooShortError(ValueError):
    """Raised when extracted Stage 2.2 Beat text is shorter than MIN_SCENE_BEATS_CHARS."""

    def __init__(self, scene_id: str, char_count: int, min_chars: int = MIN_SCENE_BEATS_CHARS):
        self.scene_id = str(scene_id or "unknown").strip() or "unknown"
        self.char_count = int(char_count or 0)
        self.min_chars = int(min_chars or MIN_SCENE_BEATS_CHARS)
        super().__init__(
            f"SCENE_MARKDOWN_BEATS_TOO_SHORT:{self.scene_id}:{self.char_count}<{self.min_chars}"
        )

    @property
    def code(self) -> str:
        return "SCENE_MARKDOWN_BEATS_TOO_SHORT"

    @property
    def detail(self) -> str:
        return (
            f"SCENE_MARKDOWN_BEATS_TOO_SHORT:{self.scene_id}:"
            f"beats_chars={self.char_count}<{self.min_chars}"
        )


class SceneMissingBeat1Error(ValueError):
    """Raised when Stage 2.2 input has no Beat 1 marker — scene is not valid for orchestration."""

    def __init__(self, scene_id: str):
        self.scene_id = str(scene_id or "unknown").strip() or "unknown"
        super().__init__(f"SCENE_MARKDOWN_MISSING_BEAT_1:{self.scene_id}")

    @property
    def code(self) -> str:
        return "SCENE_MARKDOWN_MISSING_BEAT_1"

    @property
    def detail(self) -> str:
        return f"SCENE_MARKDOWN_MISSING_BEAT_1:{self.scene_id}"


# Literal "Beat 1" or structured [BEAT_START:1] — either marks a valid Stage 1 scene body.
_BEAT_1_KEYWORD_RE = re.compile(
    r"(?:\[\s*BEAT_START\s*:\s*1\s*\])|(?:\bBeat\s+1\b)",
    re.IGNORECASE,
)


def scene_text_has_beat_1(text: str) -> bool:
    """Return True when scene orchestration input contains a Beat 1 keyword."""
    return bool(_BEAT_1_KEYWORD_RE.search(str(text or "")))


@dataclass
class ParsedSceneUnit:
    scene_id: str
    scene_order: int
    scene_text: str
    marker_start_token: str
    marker_end_token: str
    scene_markdown: str = ""


def _parse_episode_info_dict(episode: Any) -> Dict[str, Any]:
    raw = getattr(episode, "episode_info", None) if episode is not None else None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _infer_episode_scene_id_prefix_from_text(text: str) -> Optional[str]:
    source = str(text or "")
    if not source.strip():
        return None
    for pattern in (
        r"\b(EP\d+)_SC\d+\b",
        r"\[SCENE_START:(EP\d+)_SC\d+\]",
        r"\|\s*(EP\d+)\s*\|\s*EP\d+_SC\d+\s*\|",
    ):
        match = re.search(pattern, source, flags=re.IGNORECASE)
        if match:
            return str(match.group(1)).strip().upper()
    return None


def resolve_episode_scene_id_prefix(
    episode: Any = None,
    *,
    fallback_number: int = 1,
    script_text: str = "",
) -> str:
    inferred = _infer_episode_scene_id_prefix_from_text(script_text)
    if inferred:
        return inferred

    number: Optional[int] = None
    info = _parse_episode_info_dict(episode)
    for key in ("episode_script_episode_number", "story_dna_episode_number", "episode_number", "index"):
        try:
            candidate = int(info.get(key))
            if candidate > 0:
                number = candidate
                break
        except (TypeError, ValueError):
            continue
    if number is None and episode is not None:
        title = str(getattr(episode, "title", "") or "")
        for pattern in (r"EP\s*(\d+)", r"第\s*(\d+)\s*集", r"^(\d+)\s*[-_.]"):
            match = re.search(pattern, title, flags=re.IGNORECASE)
            if match:
                try:
                    number = int(match.group(1))
                    break
                except (TypeError, ValueError):
                    continue
    if number is None:
        number = max(1, int(fallback_number or 1))
    return f"EP{int(number):02d}"


def _scene_units_hint_text(units: List[ParsedSceneUnit]) -> str:
    parts: List[str] = []
    for unit in units or []:
        parts.append(str(getattr(unit, "marker_start_token", "") or ""))
        parts.append(str(getattr(unit, "scene_text", "") or ""))
    return "\n".join(part for part in parts if part)


def expand_scene_ids_for_orchestration_reset(scene_ids: List[str]) -> List[str]:
    expanded: Set[str] = set()
    for raw in scene_ids or []:
        sid = str(raw or "").strip()
        if not sid:
            continue
        expanded.add(sid)
        canonical_match = re.fullmatch(r"(EP\d+)_SC(\d+)", sid, flags=re.IGNORECASE)
        if canonical_match:
            expanded.add(str(int(canonical_match.group(2))))
            continue
        if re.fullmatch(r"\d+", sid):
            order = int(sid)
            for existing in list(expanded):
                existing_match = re.fullmatch(r"(EP\d+)_SC(\d+)", existing, flags=re.IGNORECASE)
                if existing_match and int(existing_match.group(2)) == order:
                    expanded.add(existing)
    return sorted(expanded)


def canonicalize_scene_unit_id(scene_id: str, scene_order: int, episode_prefix: str) -> str:
    sid = str(scene_id or "").strip()
    prefix = str(episode_prefix or "EP01").strip().upper()
    order = max(1, int(scene_order or 0))
    if re.match(r"^[A-Za-z]+\d+_SC", sid, flags=re.IGNORECASE):
        return sid
    if re.fullmatch(r"\d+", sid):
        return f"{prefix}_SC{int(sid):02d}"
    match = re.fullmatch(r"SC?(\d+)", sid, flags=re.IGNORECASE)
    if match:
        return f"{prefix}_SC{int(match.group(1)):02d}"
    trailing_digits = re.search(r"(\d+)\s*$", sid)
    if trailing_digits and len(sid) <= 8:
        return f"{prefix}_SC{int(trailing_digits.group(1)):02d}"
    return sid or f"{prefix}_SC{order:02d}"


def apply_canonical_scene_ids_to_units(
    units: List[ParsedSceneUnit],
    episode_prefix: str,
) -> List[ParsedSceneUnit]:
    canonicalized: List[ParsedSceneUnit] = []
    for idx, unit in enumerate(units):
        order = int(getattr(unit, "scene_order", 0) or 0) or (idx + 1)
        new_id = canonicalize_scene_unit_id(unit.scene_id, order, episode_prefix)
        if new_id != unit.scene_id:
            logger.info(
                "[scene_markdown] canonicalized scene_id %s -> %s (order=%s prefix=%s)",
                unit.scene_id,
                new_id,
                order,
                episode_prefix,
            )
            unit = replace(
                unit,
                scene_id=new_id,
                scene_order=order,
                marker_start_token=f"[SCENE_START:{new_id}]",
                marker_end_token=f"[SCENE_END:{new_id}]",
            )
        canonicalized.append(unit)
    return canonicalized


def _finalize_scene_units_for_episode(
    db: Session,
    units: List[ParsedSceneUnit],
    episode_id: int,
    *,
    script_text: str = "",
) -> List[ParsedSceneUnit]:
    if not units:
        return units
    episode_row = None
    eid = int(episode_id or 0)
    if eid > 0:
        episode_row = db.query(models.Episode).filter(models.Episode.id == eid).first()
    hint_text = str(script_text or "").strip() or _scene_units_hint_text(units)
    prefix = resolve_episode_scene_id_prefix(
        episode_row,
        fallback_number=1,
        script_text=hint_text,
    )
    return apply_canonical_scene_ids_to_units(units, prefix)


def _reconcile_legacy_numeric_scene_rows(
    db: Session,
    *,
    existing_by_scene: Dict[str, Any],
    units: List[ParsedSceneUnit],
) -> None:
    canonical_ids = {str(unit.scene_id) for unit in units}
    canonical_by_order = {
        int(getattr(unit, "scene_order", 0) or 0): str(unit.scene_id)
        for unit in units
        if int(getattr(unit, "scene_order", 0) or 0) > 0
    }
    now_iso = now_bj_iso()
    for scene_id, row in existing_by_scene.items():
        if scene_id in canonical_ids:
            continue
        if not re.fullmatch(r"\d+", str(scene_id or "").strip()):
            continue
        order = int(getattr(row, "scene_order", 0) or 0)
        canonical = canonical_by_order.get(order)
        if canonical and canonical != scene_id:
            row.import_status = "skipped"
            row.parse_status = "failed"
            row.parse_error_code = "SCENE_ID_SUPERSEDED_BY_CANONICAL"
            row.updated_at = now_iso


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
        r"`+(\[(?:SCENES?_BLOCK_(?:START|END)|SCENE_(?:START|END)(?::[^\]]+)?)])`+",
        r"\1",
        text,
        flags=re.IGNORECASE,
    )
    return text


def _strip_block_level_markers_from_scene_text(text: str) -> str:
    cleaned = BLOCK_MARKER_LINE_PATTERN.sub("", str(text or ""))
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def _normalize_scene_unit_body_for_measure(text: str) -> str:
    body = _strip_block_level_markers_from_scene_text(text)
    body = SCENE_MARKER_LINE_PATTERN.sub("", body)
    return re.sub(r"\s+", " ", body).strip()


def _scene_unit_body_char_count(text: str) -> int:
    return len(_normalize_scene_unit_body_for_measure(text))


def _find_scenes_block_span(text: str) -> tuple[int, int, int, int]:
    """Return (block_start_token_start, content_start, content_end, block_end_token_end).

    Uses the first SCENES_BLOCK_END after START (strict pair; no last-END soft window).
    """
    normalized = _normalize_scene_marker_script_text(text)
    start_match = SCENES_BLOCK_START_PATTERN.search(normalized)
    if not start_match:
        raise SceneMarkerParseError(
            "SCENE_MARKER_BLOCK_MISSING",
            "scene block markers missing or invalid order",
        )
    after_start = normalized[start_match.end() :]
    end_match = SCENES_BLOCK_END_PATTERN.search(after_start)
    if not end_match:
        raise SceneMarkerParseError("SCENE_MARKER_BLOCK_MISSING", "scene block end marker missing")
    block_start = start_match.end()
    block_end = start_match.end() + end_match.start()
    return start_match.start(), start_match.end(), block_end, start_match.end() + end_match.end()


def parse_scene_units_from_markers(script_text: str) -> List[ParsedSceneUnit]:
    """Strict SCENE_START:ID / SCENE_END:ID pair walker (original split path)."""
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
            raise SceneMarkerParseError(
                "SCENE_MARKER_PAIR_MISMATCH",
                "scene start marker has empty scene_id",
            )
        if scene_id in seen_scene_ids:
            raise SceneMarkerParseError(
                "SCENE_MARKER_DUPLICATE_SCENE_ID",
                f"duplicate scene_id: {scene_id}",
            )
        seen_scene_ids.add(scene_id)

        end_match = SCENE_END_PATTERN.search(block_text, start_match.end())
        if not end_match:
            raise SceneMarkerParseError(
                "SCENE_MARKER_PAIR_MISMATCH",
                f"missing scene end marker for {scene_id}",
            )
        end_scene_id = str(end_match.group(1) or "").strip()
        if end_scene_id != scene_id:
            raise SceneMarkerParseError(
                "SCENE_MARKER_PAIR_MISMATCH",
                f"scene marker mismatch: start={scene_id}, end={end_scene_id}",
            )

        scene_text = block_text[start_match.end() : end_match.start()].strip()
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
        raise SceneMarkerParseError(
            "SCENE_MARKER_NO_SCENES",
            "no scenes found between scene block markers",
        )

    trailing = block_text[cursor:].strip()
    if trailing and (SCENE_START_PATTERN.search(trailing) or SCENE_END_PATTERN.search(trailing)):
        raise SceneMarkerParseError(
            "SCENE_MARKER_TRAILING_CONTENT",
            "unmatched trailing content after scene markers",
        )

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
        ("episode_adaptation", episode_adaptation_text),
    ]
    for source_name, source_text in candidate_sources:
        text = str(source_text or "").strip()
        if not text:
            continue
        try:
            units = parse_scene_units_from_markers(text)
            if units:
                return _finalize_scene_units_for_episode(
                    db,
                    units,
                    episode_id,
                    script_text=text,
                ), source_name
        except SceneMarkerParseError as exc:
            parse_errors.append(f"{source_name}:{exc.code}")

    if int(project_id) > 0 and int(episode_id) > 0:
        units = load_scene_units_from_progress_rows(
            db,
            project_id=int(project_id),
            episode_id=int(episode_id),
        )
        if units:
            return _finalize_scene_units_for_episode(
                db,
                units,
                episode_id,
                script_text=adapted_script_text or episode_adaptation_text,
            ), "progress_db"

    return [], "|".join(parse_errors) if parse_errors else "no_scene_units"


def _normalize_scene_table_header(value: Any) -> str:
    return re.sub(r"[\s_\-./()]", "", str(value or "").strip().lower())


def _split_scene_table_cells(line: str) -> List[str]:
    s = str(line or "").strip()
    if not s:
        return []
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]

    cells: List[str] = []
    buf: List[str] = []
    escaped = False
    for ch in s:
        if escaped:
            buf.append(ch)
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == "|":
            cells.append("".join(buf).strip())
            buf = []
            continue
        buf.append(ch)
    if escaped:
        buf.append("\\")
    cells.append("".join(buf).strip())
    return cells


def _reconcile_scene_table_row_cells(cells: List[str], headers: List[str]) -> List[str]:
    header_count = len(headers or [])
    if header_count <= 0:
        return list(cells or [])

    row = list(cells or [])
    while len(row) < header_count:
        row.append("")
    if len(row) == header_count:
        return row[:header_count]

    core_info_idx = -1
    for idx, header in enumerate(headers):
        normalized = _normalize_scene_table_header(header)
        if "coresceneinfo" in normalized or "核心场景信息" in normalized:
            core_info_idx = idx
            break
    merge_start_idx = core_info_idx if core_info_idx >= 0 else min(5, header_count - 1)
    overflow = len(row) - header_count
    merge_end_idx = merge_start_idx + overflow + 1
    merged = (
        row[:merge_start_idx]
        + ["|".join(row[merge_start_idx:merge_end_idx])]
        + row[merge_end_idx:]
    )
    while len(merged) < header_count:
        merged.append("")
    if len(merged) > header_count:
        tail_count = header_count - merge_start_idx - 1
        merged = (
            merged[:merge_start_idx]
            + ["|".join(merged[merge_start_idx : len(merged) - tail_count])]
            + merged[len(merged) - tail_count :]
        )
    return merged[:header_count]


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


_SCENE_TABLE_ANCHOR_RE = re.compile(
    r"(?i)(?:^|\n)\s*(?:#{1,6}\s*)?part\s*1\s*:\s*scenes\s*table",
)
_SCENE_TABLE_HEADER_INLINE_RE = re.compile(
    r"(?i)\|\s*episode\s*id\s*\|\s*scene\s*id",
)
_SCENE_TABLE_DATA_ROW_RE = re.compile(
    r"(?i)\|\s*EP\d+\s*\|\s*EP\d+_SC\d+",
)


def _normalize_scene_table_line(chunk: str) -> str:
    line = str(chunk or "").strip()
    if not line:
        return ""
    if not line.startswith("|"):
        line = f"| {line}"
    if not line.endswith("|"):
        line = f"{line} |"
    return line


def _expand_glued_scene_table_line(line: str) -> List[str]:
    raw = str(line or "").strip()
    if not raw or "|" not in raw:
        return [raw] if raw else []
    if not re.search(r"\|\s*\|\s*(?::?-{3,}|EP\d+_SC|\|\s*EP\d+\s*\|)", raw, flags=re.IGNORECASE):
        return [raw]
    parts = re.split(r"\|\s*\|\s*", raw)
    rows = [_normalize_scene_table_line(part) for part in parts if str(part or "").strip()]
    return rows if len(rows) >= 2 else [raw]


def _looks_like_scenes_table_at(text: str, pos: int) -> bool:
    chunk = str(text or "")[pos:]
    lines = [ln.strip() for ln in chunk.splitlines() if str(ln or "").strip()]
    if len(lines) < 2:
        return False
    first = lines[0]
    if _SCENE_TABLE_HEADER_INLINE_RE.search(first):
        hm = _SCENE_TABLE_HEADER_INLINE_RE.search(first)
        first = first[hm.start():].strip() if hm else first
    if not _SCENE_TABLE_HEADER_INLINE_RE.search(first):
        return False
    second = lines[1]
    if _is_scene_table_separator_line(second):
        return True
    if second.startswith("|") and (
        _SCENE_TABLE_DATA_ROW_RE.search(second)
        or re.search(r"\|\s*EP\d+\s*\|", second, flags=re.IGNORECASE)
    ):
        return True
    return False


def _find_scenes_table_header_pos(text: str) -> int:
    candidates = [match.start() for match in _SCENE_TABLE_HEADER_INLINE_RE.finditer(str(text or ""))]
    if not candidates:
        return -1
    for pos in reversed(candidates):
        if _looks_like_scenes_table_at(text, pos):
            return pos
    return candidates[-1]


def _preprocess_scene_markdown_llm_raw(text: Any) -> str:
    raw = str(text or "").replace("\r\n", "\n").strip()
    if not raw:
        return ""
    raw = re.sub(r"<!--\s*script_hash:[^>]+-->\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"<think>[\s\S]*?</think>", "", raw, flags=re.IGNORECASE).strip()
    return raw.replace("```markdown", "").replace("```md", "").replace("```", "").strip()


def _is_scene_table_data_line(line: str) -> bool:
    text = str(line or "").strip()
    if not text.startswith("|"):
        return False
    if _is_scene_table_separator_line(text):
        return False
    if _SCENE_TABLE_HEADER_INLINE_RE.search(text):
        return False
    return bool(
        _SCENE_TABLE_DATA_ROW_RE.search(text)
        or re.search(r"\|\s*EP\d+\s*\|", text, flags=re.IGNORECASE)
    )


def _table_lines_have_data_row(table_lines: List[str]) -> bool:
    return any(_is_scene_table_data_line(line) for line in (table_lines or []))


def _extract_scene_table_lines(text: Any) -> List[str]:
    """Return header/separator/data markdown table lines extracted from LLM output."""
    raw = _preprocess_scene_markdown_llm_raw(text)
    if not raw:
        return []

    pos = _find_scenes_table_header_pos(raw)
    if pos < 0:
        anchor_match = _SCENE_TABLE_ANCHOR_RE.search(raw)
        if anchor_match:
            tail = raw[anchor_match.end():]
            pos = _find_scenes_table_header_pos(tail)
            if pos >= 0:
                raw = tail[pos:].lstrip()
            else:
                return []
        else:
            return []
    else:
        raw = raw[pos:].lstrip()

    table_lines: List[str] = []
    for raw_line in raw.splitlines():
        line = str(raw_line or "").strip()
        if not line:
            if table_lines:
                break
            continue

        if not table_lines:
            header_match = _SCENE_TABLE_HEADER_INLINE_RE.search(line)
            if not header_match:
                continue
            line = line[header_match.start():].strip()

        if not line.startswith("|"):
            if (
                table_lines
                and len(table_lines) >= 2
                and not _is_scene_table_separator_line(table_lines[-1])
            ):
                table_lines[-1] = f"{table_lines[-1]} {line}".strip()
                continue
            if table_lines:
                break
            continue

        expanded_rows = _expand_glued_scene_table_line(line)
        stopped = False
        for row in expanded_rows:
            row_text = str(row or "").strip()
            if not row_text.startswith("|"):
                continue
            if (
                table_lines
                and _SCENE_TABLE_HEADER_INLINE_RE.search(row_text)
                and not _is_scene_table_separator_line(row_text)
                and len(table_lines) >= 2
            ):
                stopped = True
                break
            table_lines.append(row_text)
        if stopped:
            break

    if len(table_lines) < 2 or not _table_lines_have_data_row(table_lines):
        return []
    return table_lines


def extract_scenes_table_markdown_block(text: Any) -> str:
    """Locate and extract the contiguous Scenes Table markdown block from LLM output."""
    table_lines = _extract_scene_table_lines(text)
    if not table_lines:
        return ""
    body = "\n".join(table_lines).strip()
    return f"### Part 1: Scenes Table\n\n{body}".strip()


def sanitize_scene_markdown_llm_output(text: Any) -> str:
    """Strip chain-of-thought leakage and keep only the Scenes Table block."""
    return extract_scenes_table_markdown_block(text)


def _collect_scene_table_blocks(script_text: str) -> List[str]:
    table_lines = _extract_scene_table_lines(script_text)
    if table_lines:
        return ["\n".join(table_lines).strip()]

    sanitized = sanitize_scene_markdown_llm_output(script_text)
    source = sanitized or str(script_text or "")
    expanded_lines: List[str] = []
    for raw_line in source.splitlines():
        line = str(raw_line or "").strip()
        if not line:
            continue
        if line.startswith("|") and "|" in line:
            expanded_lines.extend(_expand_glued_scene_table_line(line))
        elif expanded_lines and not line.startswith("|"):
            expanded_lines[-1] = f"{expanded_lines[-1]} {line}".strip()
        else:
            expanded_lines.append(line)

    blocks: List[List[str]] = []
    current: List[str] = []

    def flush() -> None:
        if len(current) >= 2 and _table_lines_have_data_row(current):
            blocks.append(list(current))
        current.clear()

    for line in expanded_lines:
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


def _is_blank_scene_table_cells(cells: List[str]) -> bool:
    return all(not str(cell or "").strip() for cell in (cells or []))


def _scene_table_row_has_content(
    cells: List[str],
    *,
    core_info_idx: int = -1,
    adapted_idx: int = -1,
    environment_idx: int = -1,
    linked_characters_idx: int = -1,
    key_props_idx: int = -1,
) -> bool:
    content_idxs = [
        idx
        for idx in (
            core_info_idx,
            adapted_idx,
            environment_idx,
            linked_characters_idx,
            key_props_idx,
        )
        if idx >= 0
    ]
    if not content_idxs:
        # No known content columns in this table schema; identity alone is acceptable.
        return True
    return any(_scene_table_cell_value(cells, idx) for idx in content_idxs)


def _scene_table_content_columns_present(
    *,
    core_info_idx: int = -1,
    adapted_idx: int = -1,
    environment_idx: int = -1,
    linked_characters_idx: int = -1,
    key_props_idx: int = -1,
) -> bool:
    return any(
        idx >= 0
        for idx in (
            core_info_idx,
            adapted_idx,
            environment_idx,
            linked_characters_idx,
            key_props_idx,
        )
    )


def _is_incomplete_scene_table_row(
    *,
    raw_cell_count: int,
    header_count: int,
    has_identity: bool,
    has_content: bool,
    content_columns_present: bool,
) -> bool:
    """Return True when a non-empty scene row is structurally/content incomplete."""
    if not has_identity:
        return False
    if content_columns_present and not has_content:
        return True
    # Truncated pipe rows: far fewer cells than headers, with no recoverable content.
    if (
        header_count >= 5
        and raw_cell_count > 0
        and raw_cell_count < max(3, header_count // 2)
        and not has_content
    ):
        return True
    return False


def _scene_table_cell_value(cells: List[str], idx: int) -> str:
    if idx < 0 or idx >= len(cells):
        return ""
    return str(cells[idx] or "").strip()


def _is_blank_or_none_environment_name(value: Any) -> bool:
    """True when Environment Name is empty / None / placeholder — scene must fail validation."""
    text = re.sub(r"<br\s*/?>", " ", str(value or ""), flags=re.IGNORECASE)
    text = text.replace("*", "").strip()
    if not text:
        return True
    normalized = re.sub(r"[\s_*`'\"“”‘’]+", "", text).lower()
    return normalized in {
        "none",
        "null",
        "nil",
        "n/a",
        "na",
        "-",
        "—",
        "－",
        "无",
        "空",
    }


def _scene_id_has_letter_suffix(scene_id: str) -> bool:
    return bool(re.match(r"^EP\d+_SC\d+[A-Za-z]+$", str(scene_id or "").strip(), re.I))


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
    text = sanitize_scene_markdown_llm_output(script_text) or str(script_text or "")
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

            raw_cells = _split_scene_table_cells(line)
            if not raw_cells or _is_blank_scene_table_cells(raw_cells):
                # Empty markdown table rows are skipped.
                continue

            cells = _reconcile_scene_table_row_cells(raw_cells, headers)
            if not cells or _is_blank_scene_table_cells(cells):
                continue

            has_identity = _scene_table_row_has_identity(cells, scene_id_idx, scene_no_idx, scene_name_idx)
            content_columns_present = _scene_table_content_columns_present(
                core_info_idx=core_info_idx,
                adapted_idx=adapted_idx,
                environment_idx=environment_idx,
                linked_characters_idx=linked_characters_idx,
                key_props_idx=key_props_idx,
            )
            has_content = _scene_table_row_has_content(
                cells,
                core_info_idx=core_info_idx,
                adapted_idx=adapted_idx,
                environment_idx=environment_idx,
                linked_characters_idx=linked_characters_idx,
                key_props_idx=key_props_idx,
            )

            if not has_identity:
                # Continuation rows or blank-ish rows without identity are skipped.
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
                continue

            if _is_incomplete_scene_table_row(
                raw_cell_count=len(raw_cells),
                header_count=len(headers),
                has_identity=True,
                has_content=has_content,
                content_columns_present=content_columns_present,
            ):
                scene_hint = (
                    _scene_table_cell_value(cells, scene_id_idx)
                    or _scene_table_cell_value(cells, scene_no_idx)
                    or _scene_table_cell_value(cells, scene_name_idx)
                    or "?"
                )
                raise SceneMarkerParseError(
                    "SCENES_TABLE_INCOMPLETE_ROW",
                    f"incomplete scenes table row for scene_id={scene_hint}",
                )

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

            if environment_idx < 0:
                raise SceneMarkerParseError(
                    "SCENES_TABLE_EMPTY_ENVIRONMENT_NAME",
                    f"missing Environment Name column for scene_id={scene_id}",
                )
            env_name = _scene_table_cell_value(cells, environment_idx)
            if _is_blank_or_none_environment_name(env_name):
                raise SceneMarkerParseError(
                    "SCENES_TABLE_EMPTY_ENVIRONMENT_NAME",
                    f"empty or None Environment Name for scene_id={scene_id}",
                )

            scene_text = _build_scene_text_from_table_row(
                cells,
                core_info_idx=core_info_idx,
                adapted_idx=adapted_idx,
                scene_name_idx=scene_name_idx,
                environment_idx=environment_idx,
                linked_characters_idx=linked_characters_idx,
                key_props_idx=key_props_idx,
            )
            if content_columns_present and not str(scene_text or "").strip():
                raise SceneMarkerParseError(
                    "SCENES_TABLE_INCOMPLETE_ROW",
                    f"incomplete scenes table row with empty content for scene_id={scene_id}",
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

    if not parsed:
        raise SceneMarkerParseError("SCENES_TABLE_NO_SCENES", "no valid scenes found in scenes table")

    return parsed


def extract_legacy_env_block_from_scene_text(scene_text: str) -> str:
    """Extract 【主环境】…【衍生环境】… when ENV_BLOCK markers are absent."""
    text = str(scene_text or "")
    main_match = LEGACY_MAIN_ENV_HEADER_PATTERN.search(text)
    if not main_match:
        return ""
    start = main_match.start()
    end_match = LEGACY_ENV_BLOCK_END_PATTERN.search(text, main_match.end())
    end = end_match.start() if end_match else len(text)
    body = text[start:end].strip()
    if not body:
        return ""
    return f"[ENV_BLOCK_START]\n{body}\n[ENV_BLOCK_END]"


def extract_env_block_from_scene_text(scene_text: str) -> str:
    """
    Extract `[ENV_BLOCK_START]…[ENV_BLOCK_END]` (主环境+衍生环境).
    Falls back to legacy 【主环境】…【衍生环境】 section when markers are missing.
    """
    text = str(scene_text or "")
    if not text.strip():
        return ""

    starts = list(ENV_BLOCK_START_PATTERN.finditer(text))
    if not starts:
        return extract_legacy_env_block_from_scene_text(text)

    blocks: List[str] = []
    for idx, start_match in enumerate(starts):
        next_start = starts[idx + 1].start() if idx + 1 < len(starts) else len(text)
        end_match = ENV_BLOCK_END_PATTERN.search(text, start_match.end())
        if end_match and end_match.start() <= next_start:
            block = text[start_match.start(): end_match.end()].strip()
        else:
            block = text[start_match.start(): next_start].rstrip()
            if block and not ENV_BLOCK_END_PATTERN.search(block):
                block = f"{block}\n[ENV_BLOCK_END]"
        if block:
            blocks.append(block.strip())
    return "\n\n".join(blocks).strip()


def extract_scene_transition_block_from_scene_text(scene_text: str) -> str:
    """
    Extract Stage 1【场景切换与首节拍转场】block (含服化道/换装摘要).
    Required by Stage 2.1 costume-change → derived CHAR rules.
    """
    text = str(scene_text or "")
    header_match = SCENE_TRANSITION_HEADER_PATTERN.search(text)
    if not header_match:
        return ""
    end_match = SCENE_TRANSITION_BLOCK_END_PATTERN.search(text, header_match.end())
    end = end_match.start() if end_match else len(text)
    return text[header_match.start(): end].strip()


def extract_scene_env_and_beats_body(
    scene_text: str,
    scene_id: str = "",
    *,
    min_beats_chars: int = MIN_SCENE_BEATS_CHARS,
) -> Tuple[str, str]:
    """
    Build Stage 2.1 per-scene payload: ENV_BLOCK + transition (服化道) + Beat blocks.
    Returns `(body, source)` where source is `extracted` | `scene_fallback`.
    """
    source_text = _strip_block_level_markers_from_scene_text(scene_text).strip()
    sid = str(scene_id or "unknown").strip() or "unknown"
    if not source_text:
        return "", "scene_fallback"

    env_block = extract_env_block_from_scene_text(source_text).strip()
    transition_block = extract_scene_transition_block_from_scene_text(source_text).strip()
    beats_only = extract_beat_blocks_from_scene_text(source_text).strip()
    beats_chars = len(_strip_beat_boundary_markers(beats_only)) if beats_only else 0
    threshold = int(min_beats_chars or MIN_SCENE_BEATS_CHARS)

    chunks: List[str] = []
    if env_block:
        chunks.append(env_block)
    if transition_block:
        chunks.append(transition_block)
    if beats_only and beats_chars >= threshold:
        chunks.append(beats_only)

    if chunks:
        return "\n\n".join(chunks).strip(), "extracted"

    logger.warning(
        "[assets_extraction] env+beat extract fallback to full scene | scene_id=%s env=%s transition=%s beats_chars=%s",
        sid,
        bool(env_block),
        bool(transition_block),
        beats_chars,
    )
    return source_text, "scene_fallback"


def extract_entity_profile_block_from_adapted(adapted_script: str) -> str:
    """
    Extract Part 2【角色设定】block (`[ENTITY_PROFILE_START]…[ENTITY_PROFILE_END]`)
    from Stage 1 adapted script. Falls back to bare 【角色设定】… before first SCENE_START.
    """
    text = str(adapted_script or "")
    if not text.strip():
        return ""

    start_match = ENTITY_PROFILE_START_PATTERN.search(text)
    if start_match:
        end_match = ENTITY_PROFILE_END_PATTERN.search(text, start_match.end())
        if end_match:
            return text[start_match.start(): end_match.end()].strip()
        # Unclosed marker: take until first SCENE_START
        scene_match = SCENE_START_PATTERN.search(text, start_match.end())
        end = scene_match.start() if scene_match else len(text)
        body = text[start_match.start(): end].rstrip()
        if body and not ENTITY_PROFILE_END_PATTERN.search(body):
            body = f"{body}\n{ENTITY_PROFILE_END_TOKEN}"
        return body.strip()

    header_match = LEGACY_ENTITY_PROFILE_HEADER_PATTERN.search(text)
    if not header_match:
        return ""
    # Only accept legacy header before the first scene (Part 2 preamble)
    first_scene = SCENE_START_PATTERN.search(text)
    if first_scene and header_match.start() >= first_scene.start():
        return ""
    end = first_scene.start() if first_scene else len(text)
    body = text[header_match.start(): end].strip()
    if not body:
        return ""
    return f"{ENTITY_PROFILE_START_TOKEN}\n{body}\n{ENTITY_PROFILE_END_TOKEN}"


def build_assets_extraction_script_from_adapted(adapted_script: str) -> str:
    """
    Rebuild Stage 2.1 script input: optional【角色设定】+ per-scene
    ENV_BLOCK +【场景切换与首节拍转场】(服化道/换装) + Beats
    (replaces full Stage 1 adapted script with slim extraction).
    """
    script = str(adapted_script or "").strip()
    if not script:
        return ""

    entity_profile = extract_entity_profile_block_from_adapted(script)

    try:
        units = parse_scene_units_from_markers(script)
    except Exception as exc:
        logger.warning("[assets_extraction] scene parse failed; using full adapted script | err=%s", exc)
        return script

    if not units:
        return script

    parts: List[str] = []
    if entity_profile:
        parts.append(entity_profile)
    parts.append(SCENES_BLOCK_START_TOKEN)
    fallback_count = 0
    transition_count = 0
    for unit in units:
        scene_id = str(getattr(unit, "scene_id", "") or "").strip()
        marker_start = str(getattr(unit, "marker_start_token", "") or "").strip()
        marker_end = str(getattr(unit, "marker_end_token", "") or "").strip()
        if not marker_start and scene_id:
            marker_start = f"[SCENE_START:{scene_id}]"
        if not marker_end and scene_id:
            marker_end = f"[SCENE_END:{scene_id}]"
        scene_text = getattr(unit, "scene_text", "") or ""
        body, source = extract_scene_env_and_beats_body(
            scene_text,
            scene_id,
        )
        if source == "scene_fallback":
            fallback_count += 1
        if extract_scene_transition_block_from_scene_text(scene_text).strip():
            transition_count += 1
        if marker_start:
            parts.append(marker_start)
        if body:
            parts.append(body)
        if marker_end:
            parts.append(marker_end)
    parts.append(SCENES_BLOCK_END_TOKEN)
    rebuilt = "\n".join(part for part in parts if str(part or "").strip()).strip()
    logger.info(
        "[assets_extraction] rebuilt env+transition+beat script | scenes=%s fallback_scenes=%s "
        "transition_scenes=%s entity_profile=%s chars=%s→%s",
        len(units),
        fallback_count,
        transition_count,
        bool(entity_profile),
        len(script),
        len(rebuilt),
    )
    return rebuilt or script


def extract_legacy_beat_sections_from_scene_text(scene_text: str) -> str:
    """Wrap legacy `- Beat N` sections with BEAT_START/END when markers are absent."""
    text = str(scene_text or "")
    matches = list(LEGACY_BEAT_LINE_PATTERN.finditer(text))
    if not matches:
        return ""
    blocks: List[str] = []
    for idx, match in enumerate(matches):
        beat_n = str(match.group(1) or idx + 1).strip() or str(idx + 1)
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if not body:
            continue
        blocks.append(f"[BEAT_START:{beat_n}]\n{body}\n[BEAT_END:{beat_n}]")
    return "\n\n".join(blocks).strip()


def extract_scene_name_header_from_scene_text(scene_text: str) -> str:
    """
    Extract Stage 1 scene header line `【场景名称】{短名}｜{日·内/外}`.
    Returns the full header line (including the 【场景名称】 prefix), or empty string.
    """
    match = SCENE_NAME_HEADER_PATTERN.search(str(scene_text or ""))
    if not match:
        return ""
    return str(match.group(0) or "").strip()


def extract_scene_name_value_from_scene_text(scene_text: str) -> str:
    """
    Extract Scenes Table `Scene Name` cell value from Stage 1 header:
    `{短名}｜{日·内/外}` (without the 【场景名称】 prefix).
    """
    header = extract_scene_name_header_from_scene_text(scene_text)
    if not header:
        return ""
    return re.sub(r"^【场景名称】\s*", "", header).strip()


def extract_beat_blocks_from_scene_text(scene_text: str) -> str:
    """
    Extract only `[BEAT_START:…]`…`[BEAT_END:…]` blocks from a Stage 1 scene body.
    Falls back to legacy `- Beat N` sections when markers are missing.
    """
    text = str(scene_text or "")
    if not text.strip():
        return ""

    starts = list(BEAT_START_PATTERN.finditer(text))
    if not starts:
        return extract_legacy_beat_sections_from_scene_text(text)

    blocks: List[str] = []
    for idx, start_match in enumerate(starts):
        beat_id = str(start_match.group(1) or idx + 1).strip() or str(idx + 1)
        next_start = starts[idx + 1].start() if idx + 1 < len(starts) else len(text)
        end_match = BEAT_END_PATTERN.search(text, start_match.end())
        if end_match and end_match.start() <= next_start:
            block = text[start_match.start(): end_match.end()].strip()
        else:
            block = text[start_match.start(): next_start].rstrip()
            if block and not BEAT_END_PATTERN.search(block):
                block = f"{block}\n[BEAT_END:{beat_id}]"
        if block:
            blocks.append(block.strip())
    return "\n\n".join(blocks).strip()


def _strip_beat_boundary_markers(beats_text: str) -> str:
    """Remove `[BEAT_START:…]` / `[BEAT_END:…]` tokens so length reflects Beat body content."""
    cleaned = BEAT_START_PATTERN.sub("", str(beats_text or ""))
    cleaned = BEAT_END_PATTERN.sub("", cleaned)
    return cleaned.strip()


def measure_scene_beats_char_count(scene_text: str) -> int:
    """Character count of extracted Beat body content (markers excluded)."""
    return len(_strip_beat_boundary_markers(extract_beat_blocks_from_scene_text(scene_text)))


def resolve_scene_beats_body_for_stage_2_2(
    scene_text: str,
    scene_id: str = "",
    *,
    min_chars: int = MIN_SCENE_BEATS_CHARS,
) -> Tuple[str, bool]:
    """
    Resolve Stage 2.2 Beat body for one scene.

    Prefer `[BEAT_START]/[BEAT_END]` (or legacy `- Beat N`) extraction.
    Fallback: when split fails / body shorter than `min_chars`, use the entire scene text.
    Returns `(body_text, used_scene_fallback)`.
    Raises SceneBeatsTooShortError only when even the full scene body is too short.
    """
    source = str(scene_text or "").strip()
    threshold = int(min_chars or MIN_SCENE_BEATS_CHARS)
    sid = str(scene_id or "unknown").strip() or "unknown"

    beats_only = extract_beat_blocks_from_scene_text(source).strip()
    extracted_chars = len(_strip_beat_boundary_markers(beats_only)) if beats_only else 0
    if beats_only and extracted_chars >= threshold:
        return beats_only, False

    fallback = source
    fallback_chars = len(fallback)
    if fallback_chars >= threshold:
        logger.warning(
            "[scene_markdown] beat split fallback to full scene | scene_id=%s extracted_chars=%s scene_chars=%s min=%s",
            sid,
            extracted_chars,
            fallback_chars,
            threshold,
        )
        return fallback, True

    raise SceneBeatsTooShortError(sid, max(extracted_chars, fallback_chars), threshold)


def validate_scene_beats_min_length(
    scene_text: str,
    scene_id: str = "",
    *,
    min_chars: int = MIN_SCENE_BEATS_CHARS,
) -> str:
    """
    Resolve Beats body with full-scene fallback; enforce min length on the final body.
    Returns the body text on success; raises SceneBeatsTooShortError otherwise.
    """
    body_text, _used_fallback = resolve_scene_beats_body_for_stage_2_2(
        scene_text,
        scene_id,
        min_chars=min_chars,
    )
    return body_text


def wrap_scene_unit_as_script_block(unit: ParsedSceneUnit) -> str:
    """
    Wrap one scene for Stage 2.2 LLM input: Scene markers + 【场景名称】 + Beat blocks.
    Prefer extracted Beats; on split failure / too-short Beats, fall back to full scene body.
    Raises SceneMissingBeat1Error when input has no Beat 1 keyword (invalid scene).
    Raises SceneBeatsTooShortError only when the final body is still shorter than MIN_SCENE_BEATS_CHARS.
    """
    scene_text = _strip_block_level_markers_from_scene_text(getattr(unit, "scene_text", "") or "")
    marker_start = str(getattr(unit, "marker_start_token", "") or "").strip()
    marker_end = str(getattr(unit, "marker_end_token", "") or "").strip()
    scene_id = str(getattr(unit, "scene_id", "") or "").strip()
    if not marker_start and scene_id:
        marker_start = f"[SCENE_START:{scene_id}]"
    if not marker_end and scene_id:
        marker_end = f"[SCENE_END:{scene_id}]"
    if marker_start in {"scenes_table", "scenes_table".lower()}:
        marker_start = f"[SCENE_START:{scene_id}]" if scene_id else ""
    if marker_end in {"scenes_table", "scenes_table".lower()}:
        marker_end = f"[SCENE_END:{scene_id}]" if scene_id else ""
    if not scene_text:
        scene_markdown = str(getattr(unit, "scene_markdown", "") or "").strip()
        if scene_markdown:
            scene_text = scene_markdown
    if not scene_text_has_beat_1(scene_text):
        raise SceneMissingBeat1Error(scene_id or "unknown")
    body_text, used_fallback = resolve_scene_beats_body_for_stage_2_2(scene_text, scene_id)
    # Inject Stage 1 scene header only for beats-only body; full-scene fallback already contains it.
    scene_name_header = (
        ""
        if used_fallback
        else extract_scene_name_header_from_scene_text(scene_text)
    )
    parts = [SCENES_BLOCK_START_TOKEN]
    if marker_start:
        parts.append(marker_start)
    if scene_name_header:
        parts.append(scene_name_header)
    if body_text:
        parts.append(body_text)
    if marker_end:
        parts.append(marker_end)
    parts.append(SCENES_BLOCK_END_TOKEN)
    return "\n".join(part for part in parts if str(part or "").strip()).strip()


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
            scenes_block = normalized[start_match.start(): end_match.end()].strip()
        else:
            scenes_block = normalized[start_match.start():].strip()
        entity_profile = extract_entity_profile_block_from_adapted(normalized[: start_match.start()])
        if entity_profile:
            return f"{entity_profile}\n{scenes_block}".strip()
        return scenes_block
    start_idx = text.find(SCENES_BLOCK_START_TOKEN)
    if start_idx >= 0:
        scenes_block = text[start_idx:].strip()
        entity_profile = extract_entity_profile_block_from_adapted(text[:start_idx])
        if entity_profile:
            return f"{entity_profile}\n{scenes_block}".strip()
        return scenes_block
    return ""


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
                raw_cells = _split_scene_table_cells(line)
                if not raw_cells or _is_blank_scene_table_cells(raw_cells):
                    continue
                cells = _reconcile_scene_table_row_cells(raw_cells, headers)
                if not cells or _is_blank_scene_table_cells(cells):
                    continue
                while len(cells) < len(headers):
                    cells.append("")
                core_info_idx = _find_scene_table_col_idx(normalized_headers, ["coresceneinfo", "核心场景信息"])
                adapted_idx = _find_scene_table_col_idx(
                    normalized_headers,
                    ["adaptedscripttext", "改编剧本文本", "改编剧本", "originalscripttext", "原始剧本文本", "scripttext"],
                )
                environment_idx = _find_scene_table_col_idx(normalized_headers, ["environmentname", "环境名", "环境名称", "环境"])
                linked_characters_idx = _find_scene_table_col_idx(normalized_headers, ["linkedcharacters", "关联角色", "角色", "characters"])
                key_props_idx = _find_scene_table_col_idx(normalized_headers, ["keyprops", "关键道具", "道具", "props"])
                has_identity = _scene_table_row_has_identity(cells, scene_id_idx, scene_no_idx, scene_name_idx)
                if not has_identity:
                    continue
                content_columns_present = _scene_table_content_columns_present(
                    core_info_idx=core_info_idx,
                    adapted_idx=adapted_idx,
                    environment_idx=environment_idx,
                    linked_characters_idx=linked_characters_idx,
                    key_props_idx=key_props_idx,
                )
                has_content = _scene_table_row_has_content(
                    cells,
                    core_info_idx=core_info_idx,
                    adapted_idx=adapted_idx,
                    environment_idx=environment_idx,
                    linked_characters_idx=linked_characters_idx,
                    key_props_idx=key_props_idx,
                )
                if _is_incomplete_scene_table_row(
                    raw_cell_count=len(raw_cells),
                    header_count=len(headers),
                    has_identity=True,
                    has_content=has_content,
                    content_columns_present=content_columns_present,
                ):
                    # Incomplete rows invalidate the whole merge so callers treat it as failure.
                    logger.warning(
                        "[scene_markdown] incomplete row skipped merge | raw_cells=%s headers=%s preview=%s",
                        len(raw_cells),
                        len(headers),
                        line[:160],
                    )
                    return ""
                row = list(cells)
                while len(row) < len(merged_headers):
                    row.append("")
                merged_rows.append(row[: len(merged_headers)])

    if not merged_headers or not merged_rows:
        return ""

    normalized_merged_headers = [_normalize_scene_table_header(header) for header in merged_headers]
    scene_no_idx = _find_scene_table_col_idx(normalized_merged_headers, ["sceneno", "场次序号", "场次"])
    scene_id_idx = _find_scene_table_col_idx(normalized_merged_headers, ["sceneid", "场景id"])
    if scene_no_idx >= 0:
        for idx, row in enumerate(merged_rows):
            while len(row) <= scene_no_idx:
                row.append("")
            scene_id = _scene_table_cell_value(row, scene_id_idx) if scene_id_idx >= 0 else ""
            if _scene_id_has_letter_suffix(scene_id):
                row[scene_no_idx] = str(scene_id).strip()
            else:
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
    episode_row = None
    eid = int(episode_id or 0)
    if eid > 0:
        episode_row = db.query(models.Episode).filter(models.Episode.id == eid).first()
    episode_prefix = resolve_episode_scene_id_prefix(
        episode_row,
        fallback_number=1,
        script_text=script_text,
    )
    units = apply_canonical_scene_ids_to_units(units, episode_prefix)
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

    _reconcile_legacy_numeric_scene_rows(
        db,
        existing_by_scene=existing_by_scene,
        units=units,
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


_EPISODE_SCENE_MARKDOWN_PATCH_LOCKS: Dict[int, threading.Lock] = {}
_EPISODE_SCENE_MARKDOWN_PATCH_LOCKS_GUARD = threading.Lock()


def _get_episode_scene_markdown_patch_lock(episode_id: int) -> threading.Lock:
    eid = int(episode_id)
    with _EPISODE_SCENE_MARKDOWN_PATCH_LOCKS_GUARD:
        lock = _EPISODE_SCENE_MARKDOWN_PATCH_LOCKS.get(eid)
        if lock is None:
            lock = threading.Lock()
            _EPISODE_SCENE_MARKDOWN_PATCH_LOCKS[eid] = lock
        return lock


def _extract_episode_id_from_scene_id(scene_id: str) -> str:
    text = str(scene_id or "").strip()
    if not text:
        return ""
    match = re.match(r"^([A-Za-z]+\d+)[_\-]", text)
    return str(match.group(1) if match else "").strip()


def _scene_markdown_ids_match(expected: str, returned: str, scene_order: Optional[int] = None) -> bool:
    exp = str(expected or "").strip()
    ret = str(returned or "").strip()
    if not exp or not ret:
        return False
    if exp.lower() == ret.lower():
        return True
    exp_norm = re.sub(r"[\s_\-./]+", "", exp.lower())
    ret_norm = re.sub(r"[\s_\-./]+", "", ret.lower())
    if exp_norm == ret_norm:
        return True
    if _scene_id_has_letter_suffix(exp) or _scene_id_has_letter_suffix(ret):
        return False
    if exp_norm.endswith(ret_norm) or ret_norm.endswith(exp_norm):
        return True
    if scene_order is not None and not _scene_id_has_letter_suffix(exp):
        order_text = str(scene_order).strip()
        if ret == order_text or ret_norm == order_text:
            if exp_norm.endswith(f"sc{order_text}") or exp_norm.endswith(order_text):
                return True
    return False


def patch_single_scene_markdown_for_orchestration(
    scene_text: Any,
    expected_scene_id: str,
    *,
    scene_order: Optional[int] = None,
    scene_name: Optional[str] = None,
) -> str:
    text = sanitize_scene_markdown_llm_output(scene_text) or str(scene_text or "").strip()
    expected = str(expected_scene_id or "").strip()
    if not text or not expected:
        return text

    blocks = _collect_scene_table_blocks(text)
    if not blocks:
        return text

    episode_id = _extract_episode_id_from_scene_id(expected)
    preferred_scene_name = str(scene_name or "").strip()

    for block in blocks:
        lines = [line.strip() for line in str(block or "").splitlines() if str(line or "").strip()]
        if len(lines) < 2:
            continue

        headers = _split_scene_table_cells(lines[0])
        if not headers:
            continue
        normalized_headers = [_normalize_scene_table_header(header) for header in headers]
        scene_id_idx = _find_scene_table_col_idx(normalized_headers, ["sceneid", "场景id"])
        scene_no_idx = _find_scene_table_col_idx(normalized_headers, ["sceneno", "场次序号", "场次"])
        scene_name_idx = _find_scene_table_col_idx(normalized_headers, ["scenename", "场景名", "场景名称"])
        episode_id_idx = _find_scene_table_col_idx(normalized_headers, ["episodeid", "剧集id", "分集id"])

        candidate_rows: List[List[str]] = []
        for line in lines[1:]:
            if _is_scene_table_separator_line(line):
                continue
            cells = _reconcile_scene_table_row_cells(_split_scene_table_cells(line), headers)
            if not _scene_table_row_has_identity(cells, scene_id_idx, scene_no_idx, scene_name_idx):
                continue
            candidate_rows.append(list(cells))

        if not candidate_rows:
            continue

        selected_row = candidate_rows[0]
        for cells in candidate_rows:
            row_scene_id = _scene_table_cell_value(cells, scene_id_idx)
            row_scene_no = _scene_table_cell_value(cells, scene_no_idx)
            if _scene_markdown_ids_match(expected, row_scene_id, scene_order):
                selected_row = cells
                break
            if (
                scene_order is not None
                and not _scene_id_has_letter_suffix(expected)
                and str(row_scene_no).strip() == str(scene_order).strip()
            ):
                selected_row = cells
                break

        row = list(selected_row)
        while len(row) < len(headers):
            row.append("")
        if scene_id_idx >= 0:
            row[scene_id_idx] = expected
        has_letter_suffix = _scene_id_has_letter_suffix(expected)
        if scene_no_idx >= 0:
            if has_letter_suffix:
                row[scene_no_idx] = expected
            elif scene_order is not None:
                row[scene_no_idx] = str(scene_order)
        if episode_id and episode_id_idx >= 0:
            row[episode_id_idx] = episode_id
        if preferred_scene_name and scene_name_idx >= 0:
            current_name = _scene_table_cell_value(row, scene_name_idx)
            if not current_name or current_name.lower() in {"none", "null", "n/a", "-"}:
                row[scene_name_idx] = preferred_scene_name
        return _build_scene_markdown_from_table_row(headers, row)

    return text


def validate_single_scene_markdown_for_orchestration(
    scene_text: Any,
    expected_scene_id: str,
    *,
    scene_order: Optional[int] = None,
) -> Optional[str]:
    text = sanitize_scene_markdown_llm_output(scene_text) or str(scene_text or "").strip()
    if not text:
        return "SCENE_MARKDOWN_EMPTY"
    expected = str(expected_scene_id or "").strip()
    if not expected:
        return "SCENE_MARKDOWN_EXPECTED_SCENE_ID_MISSING"
    try:
        units = parse_scene_units_from_scenes_table(text)
    except SceneMarkerParseError as exc:
        code = str(getattr(exc, "code", "") or "SCENE_MARKDOWN_PARSE_FAILED")
        if code == "SCENES_TABLE_INCOMPLETE_ROW":
            return f"SCENE_MARKDOWN_INCOMPLETE_TABLE:{exc}"
        if code == "SCENES_TABLE_EMPTY_ENVIRONMENT_NAME":
            return f"SCENE_MARKDOWN_EMPTY_ENVIRONMENT_NAME:{exc}"
        if code.startswith("SCENES_TABLE_"):
            return f"SCENE_MARKDOWN_PARSE_FAILED:{code}"
        return code
    if not units:
        return "SCENE_MARKDOWN_NO_SCENE_ROW"
    matched_units = [
        unit
        for unit in units
        if _scene_markdown_ids_match(expected, str(unit.scene_id or "").strip(), scene_order)
    ]
    if not matched_units:
        returned_ids = ", ".join(
            dict.fromkeys(str(unit.scene_id or "").strip() for unit in units if str(unit.scene_id or "").strip())
        )
        suffix = f":expected={expected}"
        if returned_ids:
            suffix = f"{suffix},got={returned_ids}"
        return f"SCENE_MARKDOWN_SCENE_ID_MISMATCH{suffix}"
    for unit in matched_units:
        if not str(getattr(unit, "scene_text", "") or "").strip():
            return f"SCENE_MARKDOWN_INCOMPLETE_TABLE:empty_content:{expected}"
    return None


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

    episode_id_int = int(getattr(episode, "id", 0) or 0)
    lock = _get_episode_scene_markdown_patch_lock(episode_id_int) if episode_id_int > 0 else threading.Lock()
    max_attempts = 3
    last_error: Optional[Exception] = None

    with lock:
        for attempt in range(1, max_attempts + 1):
            try:
                if episode_id_int > 0:
                    fresh_episode = db.query(models.Episode).filter(models.Episode.id == episode_id_int).first()
                    if fresh_episode is not None:
                        episode = fresh_episode

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

                ordered_markdowns = [
                    str((item or {}).get("markdown") or "").strip()
                    for _, item in sorted(
                        by_scene_map.items(),
                        key=lambda pair: int((pair[1] or {}).get("scene_order") or 0)
                        if isinstance(pair[1], dict)
                        else 0,
                    )
                    if isinstance(item, dict) and str((item or {}).get("markdown") or "").strip()
                ]
                merged_scene_markdown = merge_scenes_table_markdown_outputs(ordered_markdowns)
                if merged_scene_markdown:
                    episode.ai_scene_analysis_scene_markdown = merged_scene_markdown
                    raw_text_slot = outputs.setdefault(
                        "raw_text",
                        {
                            "key": "raw_text",
                            "kind": "markdown",
                            "title": "场景分析原始输出",
                            "content": "",
                        },
                    )
                    raw_text_slot["content"] = merged_scene_markdown
                    logger.info(
                        "[scene_markdown.patch] episode_id=%s scene_id=%s field=ai_scene_analysis_scene_markdown merged_chars=%s scene_count=%s",
                        episode_id_int,
                        sid,
                        len(merged_scene_markdown),
                        len(by_scene_map),
                    )
                episode.ai_stage_outputs = json.dumps(stage_outputs, ensure_ascii=False, indent=2)
                db.commit()
                try:
                    db.refresh(episode)
                except Exception:
                    pass
                return {"scene_id": sid, "patched": True, "scene_count": len(by_scene_map)}
            except OperationalError as exc:
                last_error = exc
                db.rollback()
                msg = str(exc or "").lower()
                if attempt >= max_attempts or "database is locked" not in msg:
                    raise
                time.sleep(0.15 * attempt)
            except Exception:
                db.rollback()
                raise

    if last_error is not None:
        raise last_error
    return {"scene_id": sid, "patched": False}


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
    "SceneBeatsTooShortError",
    "SceneMissingBeat1Error",
    "MIN_SCENE_BEATS_CHARS",
    "measure_scene_beats_char_count",
    "scene_text_has_beat_1",
    "resolve_scene_beats_body_for_stage_2_2",
    "validate_scene_beats_min_length",
    "build_script_analysis_flow_plan",
    "get_script_analysis_flow_registry",
    "normalize_node_status",
    "normalize_script_analysis_flow_config",
    "expand_scene_ids_for_orchestration_reset",
    "load_scene_units_from_progress_rows",
    "merge_scenes_table_markdown_outputs",
    "canonicalize_scene_unit_id",
    "resolve_episode_scene_id_prefix",
    "apply_canonical_scene_ids_to_units",
    "parse_scene_units_from_markers",
    "parse_scene_units_from_scenes_table",
    "patch_episode_scene_markdown_by_scene",
    "patch_single_scene_markdown_for_orchestration",
    "resolve_scene_units_for_markdown_orchestration",
    "extract_scenes_table_markdown_block",
    "sanitize_scene_markdown_llm_output",
    "wrap_scene_unit_as_script_block",
    "extract_scene_name_header_from_scene_text",
    "extract_scene_name_value_from_scene_text",
    "extract_beat_blocks_from_scene_text",
    "extract_legacy_beat_sections_from_scene_text",
    "extract_env_block_from_scene_text",
    "extract_legacy_env_block_from_scene_text",
    "extract_scene_transition_block_from_scene_text",
    "extract_scene_env_and_beats_body",
    "extract_entity_profile_block_from_adapted",
    "build_assets_extraction_script_from_adapted",
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
    "validate_single_scene_markdown_for_orchestration",
]