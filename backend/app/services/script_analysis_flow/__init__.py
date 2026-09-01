from __future__ import annotations

import json
import logging
import re
import threading
import time
from dataclasses import dataclass, replace
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.core.time_utils import now_bj_iso
from app.models import all_models as models
from app.services.soft_delete import _active_episode_clause

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
    load_scene_subskill_results_map,
    load_stage1_output_text,
    lookup_persisted_scene_subskill_steps,
    merge_ai_stage_outputs_preserving_subskills,
    persist_scene_subskill_named_step,
    persist_scene_subskill_step_result,
    persist_script_optimization_stage,
    resolve_analyze_scene_stage,
    should_require_subject_index,
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
from .derived_env_ingest import (
    build_derived_env_frame_anchor_injection,
    build_derived_env_info_injection_from_entities,
    canonicalize_derived_environment_name,
    collect_derived_environment_jsons,
    collect_framing_texts_from_results_map,
    extract_derived_environment_names_from_scene_text,
    ingest_derived_environments_from_framing,
    parse_derived_env_extract_items,
    regen_derived_environments_from_framing,
    rewrite_merged_derived_environment_names,
)
from .environment_reuse import extract_scene_env_ident_block, parse_scene_env_ident_items
from .environment_asset_brief import (
    build_environment_asset_design_brief,
    environment_plan_has_ident,
    pick_environment_plan_source_and_brief,
)
from .character_asset_brief import (
    build_character_asset_design_brief,
    char_extract_has_items,
    current_world_identity,
    extract_char_extract_blocks,
    extract_char_field,
    first_text_with_char_extract,
    parse_char_extract_records,
    splice_char_extract_into_script,
)
from .prop_asset_brief import (
    build_prop_asset_design_brief,
    extract_prop_extract_blocks,
    first_text_with_prop_extract,
    prop_extract_has_items,
    splice_prop_extract_into_script,
)
from .scene_cast import (
    build_scene_entity_token_brief,
    extract_scene_cast_block,
    extract_scene_cast_blocks,
)
from .cover_poster_brief import build_cover_poster_brief
from .workspace_scene_from_staging import (
    build_scene_table_markdown_from_staging,
    build_workspace_scene_payload_from_staging,
    upsert_workspace_scene_from_staging,
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
SCENE_CONTENT_MARKER_LINE_PATTERN = re.compile(
    r"^\s*`?\[SCENE_CONTENT_(?:START|END)(?::[^\]]+)?\]`?\s*$",
    re.IGNORECASE | re.MULTILINE,
)
COMPREHENSIVE_INFO_PATTERN = re.compile(
    r"`?\[COMPREHENSIVE_INFO_START\]`?(.*?)`?\[COMPREHENSIVE_INFO_END\]`?",
    re.IGNORECASE | re.DOTALL,
)
SPECIAL_SCENE_ANALYSIS_PATTERN = re.compile(
    r"`?\[SPECIAL_SCENE_ANALYSIS_START:([^\s\]]+)\]`?"
    r"(.*?)"
    r"`?\[SPECIAL_SCENE_ANALYSIS_END:([^\s\]]+)\]`?",
    re.IGNORECASE | re.DOTALL,
)
SPECIAL_ROUTE_LINE_PATTERN = re.compile(
    r"^\s*\[(VFX|XIAN)\]\s*命中\s*=\s*(是|否)"
    r"(?:\s*[｜|]\s*类型\s*=\s*([^｜|\r\n]+))?"
    r"(?:\s*[｜|]\s*证据\s*=\s*([^\r\n]+))?",
    re.IGNORECASE | re.MULTILINE,
)
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
LEGACY_BEAT_LINE_PATTERN = re.compile(r"(?m)^\s*[-~]\s*Beat\s+(\d+)\b")
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
SCENE_TRANSITION_HEADER_PATTERN = re.compile(r"【(?:场景衔接|场景切换与首节拍转场)】")
SCENE_TRANSITION_BLOCK_END_PATTERN = re.compile(
    r"(?=\[BEAT_START|"
    r"\[SCENE_END|"
    r"【对白拆句|"
    r"^\s*[-~]\s*Beat\s+\d+\b)",
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
_MAIN_ENV_NAME_LINE_PATTERN = re.compile(r"(?m)^[ \t]*【主环境】[ \t]*(.+?)\s*$")
_ENV_BLOCK_LEADING_NAME_PATTERN = re.compile(
    r"\[ENV_BLOCK_START(?::[^\]]+)?\]\s*([^,，\n\]]+)[,，]",
    re.IGNORECASE,
)
_OWNING_MAIN_ENV_PATTERN = re.compile(r"所属主环境\s*=\s*([^\s｜|\r\n]+)")

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
    """Raised when Stage 2.2 input has no Beat marker at all — scene is not valid for orchestration.

    Legacy code name: historically required literal Beat 1. Downstream still matches
    SCENE_MARKDOWN_MISSING_BEAT_1, but the gate now accepts any Beat number
    (cross-scene continued numbering such as Beat 11 in SC03).
    """

    def __init__(self, scene_id: str):
        self.scene_id = str(scene_id or "unknown").strip() or "unknown"
        super().__init__(f"SCENE_MARKDOWN_MISSING_BEAT_1:{self.scene_id}")

    @property
    def code(self) -> str:
        return "SCENE_MARKDOWN_MISSING_BEAT_1"

    @property
    def detail(self) -> str:
        return f"SCENE_MARKDOWN_MISSING_BEAT_1:{self.scene_id}"


# Any Beat marker: [BEAT_START:n], [BEAT_START], "- Beat n" / "~ Beat n", or a line-start "Beat n".
# Do not require n==1 — LLMs sometimes continue numbering across scenes.
_BEAT_MARKER_RE = re.compile(
    r"(?:\[\s*BEAT_START(?:\s*:\s*[^\s\]]+)?\s*\])"
    r"|(?:^[ \t]*[-~]?[ \t]*Beat[ \t]+\d+\b)",
    re.IGNORECASE | re.MULTILINE,
)
_BARE_BEAT_LINE_RE = re.compile(r"(?m)^[ \t]*Beat[ \t]+(\d+)\b", re.IGNORECASE)


def scene_text_has_beat(text: str) -> bool:
    """Return True when scene orchestration input contains any Beat marker."""
    return bool(_BEAT_MARKER_RE.search(str(text or "")))


def scene_text_has_beat_1(text: str) -> bool:
    """Compatibility alias: any Beat marker (not specifically Beat 1)."""
    return scene_text_has_beat(text)


def scene_first_beat_number(text: str) -> str:
    """Return the first Beat id in scene text, or empty string if none."""
    source = str(text or "")
    candidates: List[Tuple[int, str]] = []
    start_match = BEAT_START_PATTERN.search(source)
    if start_match:
        candidates.append((start_match.start(), str(start_match.group(1) or "").strip()))
    legacy_match = LEGACY_BEAT_LINE_PATTERN.search(source)
    if legacy_match:
        candidates.append((legacy_match.start(), str(legacy_match.group(1) or "").strip()))
    if candidates:
        candidates.sort(key=lambda item: item[0])
        return candidates[0][1]
    bare_match = _BARE_BEAT_LINE_RE.search(source)
    if bare_match:
        return str(bare_match.group(1) or "").strip()
    return ""


def is_canonical_first_beat_number(beat_id: str) -> bool:
    raw = str(beat_id or "").strip()
    if not raw:
        return False
    try:
        return int(raw) == 1
    except (TypeError, ValueError):
        return raw in {"1", "01"}


@dataclass
class ParsedSceneUnit:
    scene_id: str
    scene_order: int
    scene_text: str
    marker_start_token: str
    marker_end_token: str
    scene_markdown: str = ""
    special_analysis_text: str = ""
    special_routing: Optional[Dict[str, Dict[str, Any]]] = None
    comprehensive_info: str = ""


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
    match = re.fullmatch(r"([A-Za-z]+)(\d+)_SC(\d+)([A-Za-z]*)", sid, flags=re.IGNORECASE)
    if match:
        head = str(match.group(1) or "").upper()
        sc_num = f"{int(match.group(3)):02d}"
        suffix = str(match.group(4) or "").upper()
        if head == "EP":
            return f"{prefix}_SC{sc_num}{suffix}"
        return f"{head}{int(match.group(2)):02d}_SC{sc_num}{suffix}"
    if re.fullmatch(r"\d+", sid):
        return f"{prefix}_SC{int(sid):02d}"
    sc_match = re.fullmatch(r"SC?(\d+)", sid, flags=re.IGNORECASE)
    if sc_match:
        return f"{prefix}_SC{int(sc_match.group(1)):02d}"
    trailing_digits = re.search(r"(\d+)\s*$", sid)
    if trailing_digits and len(sid) <= 8:
        return f"{prefix}_SC{int(trailing_digits.group(1)):02d}"
    return sid or f"{prefix}_SC{order:02d}"


_SINGLE_SCENE_MODE_ID_RE = re.compile(
    r"本次仅处理\s*Scene\s*ID\s*[`'\"]\s*([A-Za-z0-9_]+)\s*[`'\"]",
    re.IGNORECASE,
)


def coerce_target_scene_ids_for_orchestration(
    raw_payload: Optional[Dict[str, Any]] = None,
    user_text: str = "",
) -> List[str]:
    payload = raw_payload if isinstance(raw_payload, dict) else {}
    collected: List[str] = []
    raw_list = payload.get("target_scene_ids")
    if isinstance(raw_list, str):
        collected.append(raw_list)
    elif isinstance(raw_list, (list, tuple, set)):
        collected.extend(str(item) for item in raw_list)
    single = str(payload.get("target_scene_id") or "").strip()
    if single:
        collected.append(single)
    if not collected:
        match = _SINGLE_SCENE_MODE_ID_RE.search(str(user_text or ""))
        if match:
            collected.append(str(match.group(1) or "").strip())
    seen: Set[str] = set()
    ordered: List[str] = []
    for raw in collected:
        sid = str(raw or "").strip()
        if not sid:
            continue
        key = sid.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(sid)
    return ordered


def filter_scene_units_by_target_ids(
    units: List[ParsedSceneUnit],
    target_ids: List[str],
    *,
    episode_prefix: str = "EP01",
) -> List[ParsedSceneUnit]:
    requested = [str(item or "").strip() for item in (target_ids or []) if str(item or "").strip()]
    if not requested:
        return list(units or [])
    prefix = str(episode_prefix or "EP01").strip().upper() or "EP01"
    matched: List[ParsedSceneUnit] = []
    seen: Set[str] = set()
    for unit in units or []:
        unit_id = str(getattr(unit, "scene_id", "") or "").strip()
        if not unit_id:
            continue
        order = int(getattr(unit, "scene_order", 0) or 0)
        canonical_unit = canonicalize_scene_unit_id(unit_id, order, prefix)
        hit = False
        for raw in requested:
            canonical_target = canonicalize_scene_unit_id(raw, order, prefix)
            if (
                unit_id == raw
                or canonical_unit == raw
                or canonical_unit == canonical_target
                or unit_id.upper() == raw.upper()
            ):
                hit = True
                break
        if not hit:
            continue
        key = canonical_unit.lower()
        if key in seen:
            continue
        seen.add(key)
        matched.append(unit)
    return matched


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
        episode_row = (
            db.query(models.Episode)
            .filter(models.Episode.id == eid, _active_episode_clause())
            .first()
        )
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
    episode_prefix: str = "EP01",
) -> None:
    canonical_ids = {str(unit.scene_id) for unit in units}
    now_iso = now_bj_iso()
    for scene_id, row in existing_by_scene.items():
        if scene_id in canonical_ids:
            continue
        if _scene_id_has_letter_suffix(scene_id):
            continue
        order = int(getattr(row, "scene_order", 0) or 0)
        normalized = canonicalize_scene_unit_id(scene_id, order, episode_prefix)
        if normalized in canonical_ids and normalized != scene_id:
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
        r"`+(\[(?:SCENES?_BLOCK_(?:START|END)|SCENE_(?:CONTENT_)?(?:START|END)(?::[^\]]+)?)])`+",
        r"\1",
        text,
        flags=re.IGNORECASE,
    )
    text = SCENE_CONTENT_MARKER_LINE_PATTERN.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    has_scene_pairs = bool(SCENE_START_PATTERN.search(text) and SCENE_END_PATTERN.search(text))
    if (
        not SCENES_BLOCK_START_PATTERN.search(text)
        and has_scene_pairs
        and SCENES_BLOCK_END_PATTERN.search(text)
    ):
        text = f"{SCENES_BLOCK_START_TOKEN}\n{text}"
    start_match = SCENES_BLOCK_START_PATTERN.search(text)
    if start_match and has_scene_pairs:
        after_start = text[start_match.end():]
        if not SCENES_BLOCK_END_PATTERN.search(after_start):
            text = f"{text.rstrip()}\n{SCENES_BLOCK_END_TOKEN}"
    elif has_scene_pairs and not SCENES_BLOCK_START_PATTERN.search(text):
        text = f"{SCENES_BLOCK_START_TOKEN}\n{text.rstrip()}\n{SCENES_BLOCK_END_TOKEN}"
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


def extract_comprehensive_info_block(script_text: str) -> str:
    """Return the single top-level comprehensive-information block, including markers."""
    text = _normalize_scene_marker_script_text(script_text)
    matches = list(COMPREHENSIVE_INFO_PATTERN.finditer(text))
    if len(matches) > 1:
        raise SceneMarkerParseError(
            "COMPREHENSIVE_INFO_DUPLICATE",
            "multiple comprehensive information blocks found",
        )
    if not matches:
        return ""
    match = matches[0]
    return match.group(0).strip()


def parse_special_scene_analysis_blocks(script_text: str) -> Dict[str, Dict[str, Any]]:
    """Parse per-scene VFX/XIAN routing blocks emitted immediately before SCENE_START."""
    text = _normalize_scene_marker_script_text(script_text)
    parsed: Dict[str, Dict[str, Any]] = {}
    for match in SPECIAL_SCENE_ANALYSIS_PATTERN.finditer(text):
        start_id = str(match.group(1) or "").strip()
        end_id = str(match.group(3) or "").strip()
        if not start_id or start_id != end_id:
            raise SceneMarkerParseError(
                "SPECIAL_SCENE_ANALYSIS_ID_MISMATCH",
                f"special scene analysis id mismatch: {start_id or '?'} != {end_id or '?'}",
            )
        if start_id in parsed:
            raise SceneMarkerParseError(
                "SPECIAL_SCENE_ANALYSIS_DUPLICATE",
                f"duplicate special scene analysis block: {start_id}",
            )
        routes: Dict[str, Dict[str, Any]] = {
            "VFX": {"hit": False, "type": "", "evidence": ""},
            "XIAN": {"hit": False, "type": "", "evidence": ""},
        }
        body = str(match.group(2) or "")
        for route_match in SPECIAL_ROUTE_LINE_PATTERN.finditer(body):
            route_key = str(route_match.group(1) or "").strip().upper()
            routes[route_key] = {
                "hit": str(route_match.group(2) or "").strip() == "是",
                "type": str(route_match.group(3) or "").strip(),
                "evidence": str(route_match.group(4) or "").strip(),
            }
        parsed[start_id] = {
            "scene_id": start_id,
            "block_text": match.group(0).strip(),
            "routes": routes,
        }
    return parsed


def build_scene_subskill_task_payloads(script_text: str) -> List[Dict[str, Any]]:
    """Programmatically split Stage-1 output into independent per-scene task payloads."""
    comprehensive_info = extract_comprehensive_info_block(script_text)
    units = parse_scene_units_from_markers(script_text)
    tasks: List[Dict[str, Any]] = []
    for unit in units:
        routing = dict(getattr(unit, "special_routing", None) or {})
        special_text = str(getattr(unit, "special_analysis_text", "") or "").strip()
        scene_block = "\n".join(
            part
            for part in (
                special_text,
                str(unit.marker_start_token or f"[SCENE_START:{unit.scene_id}]"),
                str(unit.scene_text or "").strip(),
                str(unit.marker_end_token or f"[SCENE_END:{unit.scene_id}]"),
            )
            if part
        )
        tasks.append(
            {
                "scene_id": unit.scene_id,
                "scene_order": unit.scene_order,
                "scene_text": unit.scene_text,
                "scene_block": scene_block,
                "comprehensive_info": comprehensive_info,
                "entity_token_brief": build_scene_entity_token_brief(
                    script_text,
                    unit.scene_id,
                    unit.scene_text,
                ),
                "special_analysis": special_text,
                "routes": routing,
                "call_vfx": bool((routing.get("VFX") or {}).get("hit")),
                "call_xian": bool((routing.get("XIAN") or {}).get("hit")),
            }
        )
    return tasks


def parse_scene_units_from_markers(script_text: str) -> List[ParsedSceneUnit]:
    """SCENE_START:ID / SCENE_END pair walker (original split path).

    START id is required. END must exist; if END id differs from START, Scene ID = START.
    """
    text = _normalize_scene_marker_script_text(script_text)
    if not text.strip():
        raise SceneMarkerParseError("SCENE_MARKER_BLOCK_MISSING", "script text is empty")

    _, block_content_start, block_content_end, _ = _find_scenes_block_span(text)
    block_text = text[block_content_start:block_content_end]
    if not block_text.strip():
        raise SceneMarkerParseError("SCENE_MARKER_EMPTY_BLOCK", "scene block is empty")

    cursor = 0
    comprehensive_info = extract_comprehensive_info_block(text)
    special_blocks = parse_special_scene_analysis_blocks(text)
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
        # END id may differ from START; Scene ID stays the START token.

        scene_text = block_text[start_match.end() : end_match.start()].strip()
        special = special_blocks.get(scene_id) or {}
        parsed.append(
            ParsedSceneUnit(
                scene_id=scene_id,
                scene_order=len(parsed) + 1,
                scene_text=scene_text,
                marker_start_token=start_match.group(0),
                marker_end_token=end_match.group(0),
                special_analysis_text=str(special.get("block_text") or ""),
                special_routing=dict(special.get("routes") or {}),
                comprehensive_info=comprehensive_info,
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
        extra_starts = [str(item or "").strip() for item in SCENE_START_PATTERN.findall(trailing) if str(item or "").strip()]
        extra_ends = [str(item or "").strip() for item in SCENE_END_PATTERN.findall(trailing) if str(item or "").strip()]
        # Valid pairs already walked. Leftover markers are usually a duplicate
        # SCENE_END or project_visual_backfill / prompt example pulled into the
        # block. Do not fail the downstream LLM call for that.
        logger.warning(
            "[scene_markers] ignoring unmatched trailing scene markers after %s scene(s): starts=%s ends=%s",
            len(parsed),
            extra_starts[:8],
            extra_ends[:8],
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
    adapted = str(adapted_script_text or "").strip()
    if adapted:
        try:
            units = parse_scene_units_from_markers(adapted)
            if units:
                return _finalize_scene_units_for_episode(
                    db,
                    units,
                    episode_id,
                    script_text=adapted,
                ), "adapted_script"
        except SceneMarkerParseError as exc:
            parse_errors.append(f"adapted_script:{exc.code}")
        # Request already carried an adapted script. Do not silently fall back to a
        # stale episode adaptation / progress_db scene_text from a previous run.
        return [], "|".join(parse_errors) if parse_errors else "adapted_script_unparsed"

    episode_adaptation = str(episode_adaptation_text or "").strip()
    if episode_adaptation:
        try:
            units = parse_scene_units_from_markers(episode_adaptation)
            if units:
                return _finalize_scene_units_for_episode(
                    db,
                    units,
                    episode_id,
                    script_text=episode_adaptation,
                ), "episode_adaptation"
        except SceneMarkerParseError as exc:
            parse_errors.append(f"episode_adaptation:{exc.code}")

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
                script_text=adapted or episode_adaptation,
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

    normalized_headers = [_normalize_scene_table_header(header) for header in headers]
    core_info_idx = _find_scene_table_col_idx(normalized_headers, ["coresceneinfo", "核心场景信息"])
    environment_idx = _find_scene_table_col_idx(
        normalized_headers,
        ["environmentname", "环境名", "环境名称", "环境"],
    )
    pin_left_until = core_info_idx if core_info_idx >= 0 else min(5, header_count - 1)
    pin_right_from = environment_idx if environment_idx > pin_left_until else -1

    # Pin identity on the left and Environment Name…Key Props on the right so
    # unescaped "|" inside Core Scene Info / Adapted Excerpt cannot shift
    # Environment Name onto a None placeholder.
    if pin_right_from > pin_left_until >= 0:
        left = row[:pin_left_until]
        right_count = header_count - pin_right_from
        right = row[-right_count:]
        middle = row[pin_left_until : len(row) - right_count]
        middle_header_count = pin_right_from - pin_left_until
        if middle_header_count <= 0:
            merged_middle = ["|".join(middle)] if middle else []
        elif len(middle) <= middle_header_count:
            merged_middle = list(middle) + [""] * (middle_header_count - len(middle))
        else:
            overflow = len(middle) - middle_header_count
            merged_middle = ["|".join(middle[: overflow + 1])] + list(middle[overflow + 1 :])
        merged = left + merged_middle + right
        while len(merged) < header_count:
            merged.append("")
        return merged[:header_count]

    merge_start_idx = pin_left_until
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
            [
                "adaptedscripttext",
                "adaptedscriptexcerpt",
                "改编剧本文本",
                "改编剧本摘录",
                "改编剧本",
                "originalscripttext",
                "原始剧本文本",
                "scripttext",
            ],
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
    Extract Stage 1【场景衔接】or legacy【场景切换与首节拍转场】block.
    Used by Stage 2.1 as a costume/prop cross-check, not as the sole wardrobe source.
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
        return strip_beat_transition_notes_from_script(script)

    if not units:
        return strip_beat_transition_notes_from_script(script)

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
    return strip_beat_transition_notes_from_script(rebuilt or script)


def resolve_assets_extraction_source_text(
    request_text: str,
    episode_adaptation: str = "",
) -> str:
    """Whole-episode assets extraction: Stage-1 scene text plus per-scene ENV.

    Starts after ``environment_plan`` (main-env splice). Prefer the request if it
    already contains merged ``ENV_BLOCK``s. If a later Stage-1 adaptation has
    derivatives, use that; otherwise keep the environment-plan script.
    """
    incoming = str(request_text or "").strip()
    adaptation = str(episode_adaptation or "").strip()
    incoming_has_env = "[ENV_BLOCK_START]" in incoming
    adaptation_has_env = "[ENV_BLOCK_START]" in adaptation
    incoming_has_derived = "【衍生环境】" in incoming
    adaptation_has_derived = "【衍生环境】" in adaptation
    if incoming_has_env and (incoming_has_derived or not adaptation_has_derived):
        return incoming
    if not adaptation_has_env:
        return incoming
    from app.core.prompt_injection import (
        strip_injection_section,
        unwrap_injection_section,
        wrap_injection_section,
    )

    if unwrap_injection_section(incoming, "优化后剧本") is not None:
        prefix = strip_injection_section(incoming, "优化后剧本")
        replaced = wrap_injection_section(
            "优化后剧本",
            "[优化后剧本 - Stage 2.1权威输入（场景切分+按场环境注入）]\n" + adaptation,
        )
        return f"{prefix}\n\n{replaced}".strip() if prefix else replaced
    return adaptation


def extract_legacy_beat_sections_from_scene_text(scene_text: str) -> str:
    """Wrap legacy `- Beat N` / `~ Beat N` sections with BEAT_START/END when markers are absent."""
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
    `{短名}·{日夜}·{内外}·{可选附加项}` (without the 【场景名称】 prefix).
    Legacy keyed headers are normalized and validation fields are discarded.
    """
    header = extract_scene_name_header_from_scene_text(scene_text)
    if not header:
        return ""
    raw = re.sub(r"^【场景名称】\s*", "", header).strip()
    if not raw:
        return ""

    parts = [part.strip() for part in re.split(r"[|｜]", raw) if part.strip()]
    values: List[str] = []
    allowed_keys = {
        "短名",
        "名称",
        "场景名",
        "日夜",
        "时间",
        "内外",
        "季节",
        "气候",
        "叙事线",
        "叙事",
    }
    excluded_keys = {"校验", "纯地名", "命名校验"}
    for part in parts:
        if "=" in part:
            key, value = part.split("=", 1)
            key = key.strip()
            value = value.strip()
            if key in excluded_keys or not value:
                continue
            if key in allowed_keys:
                values.append(value)
            continue
        values.append(part)

    normalized = "·".join(values) if values else raw
    normalized = re.sub(r"[|｜；]+", "·", normalized)
    normalized = re.sub(r"·{2,}", "·", normalized).strip(" ·")
    return normalized


def extract_environment_names_from_scene_text(scene_text: str) -> str:
    """
    Extract locked main-environment names from Stage 1 ENV_BLOCK / 【主环境】 lines.

    Used by project-library / environment-reuse to collect locked main-environment names.
    Stage 2.2 Environment Name backfill uses derived names only.
    """
    text = str(scene_text or "")
    if not text.strip():
        return ""

    names: List[str] = []
    seen: Set[str] = set()

    def _add(raw_name: str) -> None:
        cleaned = str(raw_name or "").strip().strip("`\"'“”‘’[]")
        cleaned = re.split(r"[｜|]", cleaned, maxsplit=1)[0].strip()
        cleaned = re.sub(r"^(名称|主环境|环境名|环境)\s*[=：:]\s*", "", cleaned).strip()
        if not cleaned:
            return
        if cleaned.startswith("─") or cleaned.startswith("-"):
            return
        normalized = re.sub(r"[\s_*`'\"“”‘’]+", "", cleaned).lower()
        if normalized in {"none", "null", "nil", "n/a", "na", "无", "空"}:
            return
        if cleaned in seen:
            return
        seen.add(cleaned)
        names.append(cleaned)

    for match in _MAIN_ENV_NAME_LINE_PATTERN.finditer(text):
        _add(match.group(1))
    if not names:
        for match in _ENV_BLOCK_LEADING_NAME_PATTERN.finditer(text):
            _add(match.group(1))
    if not names:
        for match in _OWNING_MAIN_ENV_PATTERN.finditer(text):
            _add(match.group(1))
    return "，".join(names)


def extract_beat_blocks_from_scene_text(scene_text: str) -> str:
    """
    Extract only `[BEAT_START:…]`…`[BEAT_END:…]` blocks from a Stage 1 scene body.
    Falls back to legacy `- Beat N` / `~ Beat N` sections when markers are missing.
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


def _paired_beat_notes_re(name: str) -> re.Pattern:
    return re.compile(
        rf"(?:^|\n)[ \t]*(?:─{{2,}}|-{{2,}})?[ \t]*【[ \t]*{name}[ \t]*】[ \t]*(?:─{{2,}}|-{{2,}})?[ \t]*\n"
        rf"[\s\S]*?"
        rf"(?:^|\n)[ \t]*(?:─{{2,}}|-{{2,}})?[ \t]*【[ \t]*{name}结束[ \t]*】[ \t]*(?:─{{2,}}|-{{2,}})?[ \t]*(?=\n|$)",
        re.IGNORECASE,
    )


_BEAT_TRANSITION_NOTES_PAIR_RE = _paired_beat_notes_re(r"Beat[ \t]*切换说明")
_BEAT_ANALYSIS_NOTES_PAIR_RE = _paired_beat_notes_re(r"场记分析")


def strip_beat_transition_notes_from_script(script_text: str) -> str:
    """Remove paired Stage 1 analysis blocks before workspace / Stage 2.x / storyboard.

    Strips both 【场记分析】…【场记分析结束】 (field-level or per-beat)
    and legacy 【Beat切换说明】…【Beat切换说明结束】. Unclosed blocks
    are left untouched (never greedy-eat past SCENE/BEAT markers).
    """
    text = str(script_text or "").replace("\r\n", "\n")
    if not text.strip():
        return ""
    text = _BEAT_ANALYSIS_NOTES_PAIR_RE.sub("\n", text)
    text = _BEAT_TRANSITION_NOTES_PAIR_RE.sub("\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


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

    Prefer `[BEAT_START]/[BEAT_END]` (or legacy `- Beat N` / `~ Beat N`) extraction.
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
    Raises SceneMissingBeat1Error when input has no Beat marker at all (invalid scene).
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
    if not scene_text_has_beat(scene_text):
        raise SceneMissingBeat1Error(scene_id or "unknown")
    body_text, used_fallback = resolve_scene_beats_body_for_stage_2_2(scene_text, scene_id)
    body_text = strip_beat_transition_notes_from_script(body_text)
    # Inject Stage 1 scene header only for beats-only body; full-scene fallback already contains it.
    scene_name_header = (
        ""
        if used_fallback
        else extract_scene_name_header_from_scene_text(scene_text)
    )
    derived_environment_names = extract_derived_environment_names_from_scene_text(scene_text)
    parts = [SCENES_BLOCK_START_TOKEN]
    if marker_start:
        parts.append(marker_start)
    if scene_name_header:
        parts.append(scene_name_header)
    if derived_environment_names:
        parts.append(f"【本场衍生环境名】{derived_environment_names}")
    if body_text:
        parts.append(body_text)
    if marker_end:
        parts.append(marker_end)
    parts.append(SCENES_BLOCK_END_TOKEN)
    return "\n".join(part for part in parts if str(part or "").strip()).strip()


def extract_adapted_script_from_beats_user_input(user_text: str) -> str:
    from app.core.prompt_injection import unwrap_injection_section

    text = str(user_text or "")
    wrapped = unwrap_injection_section(text, "优化后剧本")
    if wrapped:
        inner = re.sub(r"^\[优化后剧本[^\]]*\]\s*\n?", "", str(wrapped).strip()).strip()
        if inner:
            return inner
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


def _sanitize_scene_markdown_cell(value: Any, *, scene_name: bool = False) -> str:
    text = str(value or "").replace("\r\n", "<br>").replace("\r", "<br>").replace("\n", "<br>")
    replacement = "·" if scene_name else "／"
    return text.replace("\\|", replacement).replace("|", replacement).replace("｜", replacement)


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
    row = [
        _sanitize_scene_markdown_cell(
            cell,
            scene_name=(idx == scene_name_idx),
        )
        for idx, cell in enumerate(cells)
    ]
    while len(row) < len(headers):
        row.append("")
    header_line = "| " + " | ".join(headers) + " |"
    separator_line = "| " + " | ".join(":---" for _ in headers) + " |"
    row_line = "| " + " | ".join(row[: len(headers)]) + " |"
    table = "\n".join([header_line, separator_line, row_line])
    title = _sanitize_scene_markdown_cell(scene_name or scene_id or "Scene", scene_name=True)
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
        looks_like_table = _find_scenes_table_header_pos(script_text) >= 0
        try:
            # Stage 2.2 output contract is Scenes Table markdown only (title optional).
            # Parse table first; marker parsing is kept as backward compatibility.
            units = parse_scene_units_from_scenes_table(script_text)
        except SceneMarkerParseError:
            # A Scenes Table must not fall back to SCENE_START parsing — that
            # masks the real table error as SCENE_MARKER_BLOCK_MISSING.
            if looks_like_table:
                raise
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
        episode_prefix=episode_prefix,
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
    retry_count: Optional[int] = None,
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
            retry_count=max(0, int(retry_count or 0)),
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
    if retry_count is not None:
        row.retry_count = max(0, int(retry_count))
    if normalized_status == "running" and not previous_started_at:
        row.started_at = now_iso
    if normalized_status in {"success", "warning", "failed", "blocked", "skipped"}:
        row.ended_at = now_iso
    row.last_error_code = error_code
    row.last_error_message = error_message
    row.updated_at = now_iso
    return row


_COORDINATOR_PIPELINE_NODES = {
    "scene_subskill_pipeline",
    "script_optimization",
    "storyboard_generation",
    "shot_generation",
}
_FRONTEND_OWNED_STORYBOARD_NODES = {
    "storyboard_generation",
    "shot_generation",
}
_WAIT_ENV_STALE_BUDGET_SECONDS = 1200


def _episode_workspace_storyboard_coverage(db: Session, episode_id: int) -> Dict[str, Any]:
    """Count active workspace scenes that already have at least one active shot."""
    from app.models.all_models import Scene, Shot
    from app.services.soft_delete import _active_scene_clause, _active_shot_clause

    eid = int(episode_id or 0)
    if eid <= 0:
        return {"scene_count": 0, "with_shots": 0, "ok": False, "no_scenes": True}
    scene_ids = [
        int(row[0])
        for row in (
            db.query(Scene.id)
            .filter(Scene.episode_id == eid, _active_scene_clause())
            .all()
        )
        if row and row[0]
    ]
    if not scene_ids:
        return {"scene_count": 0, "with_shots": 0, "ok": False, "no_scenes": True}
    with_shots = {
        int(row[0])
        for row in (
            db.query(Shot.scene_id)
            .filter(
                Shot.episode_id == eid,
                Shot.scene_id.in_(scene_ids),
                _active_shot_clause(),
            )
            .distinct()
            .all()
        )
        if row and row[0]
    }
    return {
        "scene_count": len(scene_ids),
        "with_shots": len(with_shots),
        "ok": len(with_shots) >= len(scene_ids),
        "no_scenes": False,
    }


def finalize_stale_pipeline_nodes(
    db: Session,
    *,
    episode_id: int = 0,
    timeout_seconds: Optional[int] = None,
) -> int:
    """Mark running/queued nodes with no progress past the LLM budget as failed."""
    from app.services.llm_service import DEFAULT_LLM_TIMEOUT_SECONDS, is_stale_llm_request_timestamp

    if ScriptProgressPipelineNode is None:
        return 0
    budget = max(30, int(timeout_seconds or DEFAULT_LLM_TIMEOUT_SECONDS))
    query = db.query(ScriptProgressPipelineNode).filter(
        ScriptProgressPipelineNode.status.in_(("running", "queued")),
    )
    if int(episode_id or 0) > 0:
        query = query.filter(ScriptProgressPipelineNode.episode_id == int(episode_id))
    finalized = 0
    now_iso = now_bj_iso()
    rows = list(query.limit(300).all())
    fresh_child_episodes = set()
    for row in rows:
        node_name = str(getattr(row, "node_name", "") or "").strip()
        if node_name in _COORDINATOR_PIPELINE_NODES:
            continue
        stamp = (
            str(getattr(row, "updated_at", "") or "").strip()
            or str(getattr(row, "started_at", "") or "").strip()
            or str(getattr(row, "created_at", "") or "").strip()
        )
        row_episode_id = int(getattr(row, "episode_id", 0) or 0)
        meta = dict(row.runtime_meta or {}) if isinstance(getattr(row, "runtime_meta", None), dict) else {}
        row_budget = (
            _WAIT_ENV_STALE_BUDGET_SECONDS
            if str(meta.get("current_step") or "").strip() == "wait_env"
            else budget
        )
        if row_episode_id > 0 and not is_stale_llm_request_timestamp(stamp, row_budget):
            fresh_child_episodes.add(row_episode_id)
    for row in rows:
        stamp = (
            str(getattr(row, "updated_at", "") or "").strip()
            or str(getattr(row, "started_at", "") or "").strip()
            or str(getattr(row, "created_at", "") or "").strip()
        )
        meta = dict(row.runtime_meta or {}) if isinstance(getattr(row, "runtime_meta", None), dict) else {}
        node_name = str(getattr(row, "node_name", "") or "").strip()
        row_episode_id = int(getattr(row, "episode_id", 0) or 0)
        row_budget = (
            _WAIT_ENV_STALE_BUDGET_SECONDS
            if str(meta.get("current_step") or "").strip() == "wait_env"
            else budget
        )
        if node_name in _COORDINATOR_PIPELINE_NODES and row_episode_id in fresh_child_episodes:
            continue
        if node_name in _FRONTEND_OWNED_STORYBOARD_NODES:
            try:
                coverage = _episode_workspace_storyboard_coverage(db, row_episode_id)
            except Exception:
                coverage = {"scene_count": 0, "with_shots": 0, "ok": False, "no_scenes": True}
            if coverage.get("ok"):
                meta["business_event"] = "reconciled_from_workspace"
                meta["business_reason"] = "工作区分镜已齐套"
                row.status = "success"
                row.last_error_code = None
                row.last_error_message = None
                row.runtime_meta = meta
                row.ended_at = now_iso
                row.updated_at = now_iso
                finalized += 1
                continue
            current_status = str(getattr(row, "status", "") or "").strip().lower()
            # Queued placeholder is not a backend LLM job. Frontend generateSceneShots
            # owns completion; do not NODE_TIMEOUT it just because children finished.
            if current_status == "queued" or coverage.get("no_scenes"):
                continue
        if not is_stale_llm_request_timestamp(stamp, row_budget):
            continue
        meta["business_event"] = "timeout"
        meta["business_reason"] = f"超过 {row_budget}s 无进展，已标记超时"
        row.status = "failed"
        row.last_error_code = "NODE_TIMEOUT"
        row.last_error_message = f"Node timed out after {row_budget}s with no progress"
        row.runtime_meta = meta
        row.ended_at = now_iso
        row.updated_at = now_iso
        finalized += 1
    if finalized:
        db.commit()
        logger.warning(
            "[progress] finalized %s stale pipeline node(s) older than %ss episode_id=%s",
            finalized,
            budget,
            episode_id,
        )
    return finalized


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


def _orchestration_row_match_score(
    cells: List[str],
    *,
    scene_id_idx: int,
    scene_no_idx: int,
    scene_name_idx: int,
    expected_scene_id: str,
    scene_order: Optional[int],
    scene_name: str,
) -> int:
    row_scene_id = _scene_table_cell_value(cells, scene_id_idx)
    row_scene_no = _scene_table_cell_value(cells, scene_no_idx)
    row_scene_name = _scene_table_cell_value(cells, scene_name_idx)
    score = 0
    if _scene_markdown_ids_match(expected_scene_id, row_scene_id, scene_order):
        score += 100
    if (
        scene_order is not None
        and not _scene_id_has_letter_suffix(expected_scene_id)
        and str(row_scene_no).strip() == str(scene_order).strip()
    ):
        score += 50
    preferred_name = str(scene_name or "").strip()
    if preferred_name and row_scene_name:
        left = preferred_name.replace(" ", "")
        right = row_scene_name.replace(" ", "")
        if left == right or left in right or right in left:
            score += 20
    return score


def patch_single_scene_markdown_for_orchestration(
    scene_text: Any,
    expected_scene_id: str,
    *,
    scene_order: Optional[int] = None,
    scene_name: Optional[str] = None,
    environment_name: Optional[str] = None,
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
    preferred_environment_name = str(environment_name or "").strip()

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
        environment_idx = _find_scene_table_col_idx(
            normalized_headers,
            ["environmentname", "环境名", "环境名称", "环境"],
        )

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
        best_score = -1
        for cells in candidate_rows:
            score = _orchestration_row_match_score(
                cells,
                scene_id_idx=scene_id_idx,
                scene_no_idx=scene_no_idx,
                scene_name_idx=scene_name_idx,
                expected_scene_id=expected,
                scene_order=scene_order,
                scene_name=preferred_scene_name,
            )
            if score > best_score:
                best_score = score
                selected_row = cells

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
        if preferred_environment_name and environment_idx >= 0:
            current_env = _scene_table_cell_value(row, environment_idx)
            if (
                _is_blank_or_none_environment_name(current_env)
                or current_env != preferred_environment_name
            ):
                row[environment_idx] = preferred_environment_name
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
                    fresh_episode = (
                        db.query(models.Episode)
                        .filter(models.Episode.id == episode_id_int, _active_episode_clause())
                        .first()
                    )
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

                # Presence marker only: keep the latest single-scene importable table.
                # Do not merge multi-scene rows into ai_scene_analysis_scene_markdown.
                episode.ai_scene_analysis_scene_markdown = md
                scene_markdown_slot = outputs.setdefault(
                    "scene_markdown",
                    {
                        "key": "scene_markdown",
                        "kind": "markdown",
                        "title": "场景分析结果（分场）",
                        "content": "",
                    },
                )
                scene_markdown_slot["content"] = md
                scene_markdown_slot["title"] = "场景分析结果（分场）"
                logger.info(
                    "[scene_markdown.patch] episode_id=%s scene_id=%s field=scene_markdown_by_scene chars=%s scene_count=%s",
                    episode_id_int,
                    sid,
                    len(md),
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
    "scene_text_has_beat",
    "scene_text_has_beat_1",
    "scene_first_beat_number",
    "is_canonical_first_beat_number",
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
    "coerce_target_scene_ids_for_orchestration",
    "filter_scene_units_by_target_ids",
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
    "extract_environment_names_from_scene_text",
    "extract_derived_environment_names_from_scene_text",
    "parse_scene_env_ident_items",
    "extract_scene_env_ident_block",
    "parse_special_scene_analysis_blocks",
    "extract_beat_blocks_from_scene_text",
    "extract_legacy_beat_sections_from_scene_text",
    "extract_env_block_from_scene_text",
    "extract_legacy_env_block_from_scene_text",
    "extract_scene_transition_block_from_scene_text",
    "extract_scene_env_and_beats_body",
    "extract_entity_profile_block_from_adapted",
    "build_assets_extraction_script_from_adapted",
    "resolve_assets_extraction_source_text",
    "build_environment_asset_design_brief",
    "environment_plan_has_ident",
    "pick_environment_plan_source_and_brief",
    "build_character_asset_design_brief",
    "char_extract_has_items",
    "current_world_identity",
    "extract_char_extract_blocks",
    "extract_char_field",
    "first_text_with_char_extract",
    "parse_char_extract_records",
    "splice_char_extract_into_script",
    "build_prop_asset_design_brief",
    "extract_prop_extract_blocks",
    "first_text_with_prop_extract",
    "prop_extract_has_items",
    "splice_prop_extract_into_script",
    "build_scene_entity_token_brief",
    "extract_scene_cast_block",
    "extract_scene_cast_blocks",
    "build_cover_poster_brief",
    "build_scene_table_markdown_from_staging",
    "build_workspace_scene_payload_from_staging",
    "upsert_workspace_scene_from_staging",
    "build_derived_env_frame_anchor_injection",
    "build_derived_env_info_injection_from_entities",
    "canonicalize_derived_environment_name",
    "collect_derived_environment_jsons",
    "collect_framing_texts_from_results_map",
    "ingest_derived_environments_from_framing",
    "parse_derived_env_extract_items",
    "regen_derived_environments_from_framing",
    "rewrite_merged_derived_environment_names",
    "strip_beat_transition_notes_from_script",
    "extract_scene_markdown_text_from_analyze_result",
    "import_analyze_scene_stage_result",
    "import_scene_markdown_stage",
    "persist_analyze_scene_stage_result",
    "persist_assets_extraction_stage",
    "persist_entity_design_stage",
    "persist_generic_analyze_scene_stage",
    "persist_scene_markdown_stage",
    "load_scene_subskill_results_map",
    "load_stage1_output_text",
    "lookup_persisted_scene_subskill_steps",
    "merge_ai_stage_outputs_preserving_subskills",
    "persist_scene_subskill_named_step",
    "persist_scene_subskill_step_result",
    "persist_script_optimization_stage",
    "raise_progress_issue",
    "resolve_analyze_scene_stage",
    "should_require_subject_index",
    "resolve_progress_issue",
    "sync_scene_units_from_markers",
    "sync_scene_units_from_script_text",
    "update_scene_unit_orchestration_status",
    "finalize_stale_pipeline_nodes",
    "upsert_pipeline_node_status",
    "validate_analyze_scene_llm_finish_reason",
    "validate_scene_markdown_import_text",
    "validate_single_scene_markdown_for_orchestration",
]