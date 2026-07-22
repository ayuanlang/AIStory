# -*- coding: utf-8 -*-
"""Shot-list markdown parse / validate / serialize helpers."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.time_utils import now_bj_iso
from app.models.all_models import Scene, Shot
from app.services.llm_markdown_sanitize import sanitize_llm_markdown_output
from app.services.soft_delete import _active_shot_clause

logger = logging.getLogger("api_logger")

def _is_provider_moderation_block_response(raw_text: Any, cleaned_text: Optional[str] = None) -> bool:
    """Treat moderation as a hard block only when the payload reduces to the marker itself."""
    raw = str(raw_text or "")
    cleaned = str(cleaned_text if cleaned_text is not None else sanitize_llm_markdown_output(raw)).strip()

    def _normalize_marker(value: str) -> str:
        text = str(value or "").strip()
        text = re.sub(r"^\s*=+\s*", "", text)
        return text.strip().upper()

    if cleaned and _normalize_marker(cleaned) != "PROHIBITED_CONTENT":
        return False

    raw_lines = [str(line or "").strip() for line in raw.splitlines() if str(line or "").strip()]
    if not raw_lines:
        return False

    non_marker_lines = [line for line in raw_lines if _normalize_marker(line) != "PROHIBITED_CONTENT"]
    return len(non_marker_lines) == 0


def _split_markdown_row_escaped(row_line: str) -> List[str]:
    """Split a markdown table row while respecting escaped pipes (\\|)."""
    if not row_line:
        return []

    s = str(row_line).strip()
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
        # Preserve trailing backslash if it does not escape any character.
        buf.append("\\")
    cells.append("".join(buf).strip())
    return cells


def _is_markdown_table_separator(line: str) -> bool:
    if not line:
        return False
    stripped = str(line).strip()
    if not stripped or "|" not in stripped:
        return False

    cols = _split_markdown_row_escaped(stripped)
    if not cols:
        return False

    for col in cols:
        token = col.replace(" ", "")
        if not token:
            return False
        token = token.strip(":")
        if len(token) < 3 or not all(ch == "-" for ch in token):
            return False
    return True


def _find_shot_pipe_merge_column_indices(headers: List[str]) -> List[int]:
    """Columns whose cell text may contain unescaped pipe separators."""
    indices: List[int] = []
    preferred_aliases = [
        ["shot logic (cn)", "shot_logic_cn", "镜头逻辑", "镜头逻辑（中文）"],
        ["video content (cn)", "video_prompt_cn", "视频内容（中文）"],
        ["start frame (cn)", "start_frame_cn", "起始帧（中文）"],
        ["keyframes (cn)", "keyframes_cn", "关键帧（中文）"],
        ["end frame (cn)", "end_frame_cn", "结束帧（中文）"],
    ]
    normalized_headers = [_normalize_shot_markdown_col_key(h) for h in headers]
    for aliases in preferred_aliases:
        alias_norms = {_normalize_shot_markdown_col_key(a) for a in aliases}
        for idx, normalized_header in enumerate(normalized_headers):
            if normalized_header in alias_norms:
                if idx not in indices:
                    indices.append(idx)
                break
            if any(
                alias and (alias in normalized_header or normalized_header in alias)
                for alias in alias_norms
            ):
                if idx not in indices:
                    indices.append(idx)
                break
    if not indices:
        indices = [3]
    return indices


def _reconcile_shot_markdown_row_cells(
    cells: List[str],
    header_count: int,
    merge_column_indices: Optional[List[int]] = None,
) -> List[str]:
    """Re-align shot markdown row cells when unescaped pipes inflated the column count."""
    vals = [str(c or "").strip() for c in (cells or [])]
    if header_count <= 0:
        return []
    if len(vals) <= header_count:
        while len(vals) < header_count:
            vals.append("")
        return vals[:header_count]

    # Common LLM artifact: an extra empty cell (spurious `|`) immediately before
    # Video Content (CN). Dropping those empties first avoids merging into Shot Logic,
    # which otherwise shifts Duration into Video Content and blanks Duration (s).
    # Only consider empties from the Start Frame (CN) region onward; never the
    # trailing Associated Entities cell.
    cn_region_start = 9 if header_count >= 14 else max(4, header_count - 5)
    while len(vals) > header_count:
        dropped = False
        for idx in range(cn_region_start, len(vals) - 1):
            if not vals[idx] and vals[idx + 1]:
                vals = vals[:idx] + vals[idx + 1 :]
                dropped = True
                break
        if not dropped:
            break

    merge_indices = list(merge_column_indices or [3])
    while len(vals) > header_count:
        overflow = len(vals) - header_count
        merge_idx = merge_indices[0] if merge_indices else header_count - 1
        merge_idx = max(0, min(int(merge_idx), header_count - 1))
        merge_end = min(len(vals), merge_idx + overflow + 1)
        merged = "|".join(vals[merge_idx:merge_end])
        vals = vals[:merge_idx] + [merged] + vals[merge_end:]
        if len(vals) > header_count:
            if len(merge_indices) > 1:
                merge_indices = merge_indices[1:]
                continue
            tail = " | ".join(vals[header_count - 1 :])
            vals = vals[: header_count - 1] + [tail]

    while len(vals) < header_count:
        vals.append("")
    return vals[:header_count]


def _normalize_markdown_table_cells(
    cells: List[str],
    header_count: int,
    *,
    merge_column_indices: Optional[List[int]] = None,
) -> List[str]:
    if header_count <= 0:
        return []
    vals = _reconcile_shot_markdown_row_cells(cells, header_count, merge_column_indices)
    import re
    normalized: List[str] = []
    for c in vals:
        if c:
            c = re.sub(r"(?i)<br\s*/?>", "\n", str(c)).replace("\\n", "\n").strip()
        normalized.append(c or "")
    return normalized


def _looks_like_markdown_table_row_for_shots(line: str) -> bool:
    s = str(line or "").strip()
    if not s:
        return False
    if s.startswith("|"):
        return True
    # Accept markdown rows without leading/trailing pipes.
    return s.count("|") >= 2


def _is_shot_markdown_header_row(line: str) -> bool:
    """True when a table row is a Shot List header (not a data row)."""
    cells = _split_markdown_row_escaped(str(line or "").strip())
    if not cells:
        return False
    first = _normalize_shot_markdown_col_key(cells[0])
    if first in {"shotid", "镜头id"}:
        return True
    normalized_cells = {_normalize_shot_markdown_col_key(cell) for cell in cells}
    return "shotid" in normalized_cells and "sceneid" in normalized_cells


def _is_placeholder_shot_row(row: Dict[str, Any]) -> bool:
    """Reject prompt example / re-emitted header rows mistaken as shot data."""
    if not isinstance(row, dict):
        return True
    shot_id = _pick_shot_cell(row, ["Shot ID", "shot_id", "镜头ID"], "")
    raw_id = str(shot_id or "").strip()
    if not raw_id:
        return True
    if re.fullmatch(r"(shot\s*id|镜头\s*id)", raw_id, flags=re.IGNORECASE):
        return True
    normalized_id = _normalize_shot_business_id(raw_id)
    if not normalized_id:
        return True
    # Header cell "Shot ID" normalizes to "ID" via _normalize_shot_business_id.
    if normalized_id in {"ID", "镜头ID", "{SCENE ID}_SHZZ", "{SCENEID}_SHZZ", "EPXX_SCYY_SHZZ"}:
        return True
    if "{SCENE" in normalized_id or "SHZZ" in normalized_id:
        return True
    if not re.search(r"_SH\d{2}(_\d+)?$", normalized_id, flags=re.IGNORECASE) and (
        "SHZZ" in raw_id.upper() or "{SCENE" in raw_id.upper()
    ):
        return True
    shot_name = _pick_shot_cell(row, ["Shot Name", "shot_name", "镜头名称"], "")
    if shot_name and re.search(r"核心动作简述|^\(正整数", shot_name):
        return True
    scene_id = _pick_shot_cell(
        row,
        ["Scene ID", "scene_id", "Scene Code", "scene_code", "场景ID", "场景编号"],
        "",
    )
    if scene_id and re.search(r"上游\s*Scene\s*ID|原样", scene_id, flags=re.IGNORECASE):
        return True
    return False


_REAL_SHOT_ID_RE = re.compile(
    r"^EP\d{2}_SC\d{2}[A-Za-z]*_SH\d{2}(_\d+)?$",
    re.IGNORECASE,
)


def _shot_id_cell_looks_real(cell: Any) -> bool:
    text = str(cell or "").strip()
    if not text:
        return False
    text = re.sub(r"\*\*", "", text)
    text = re.sub(r"(?i)^shot\s*", "", text).strip()
    return bool(_REAL_SHOT_ID_RE.match(text))


def _extract_shot_markdown_table_blocks(lines: List[str]) -> List[List[str]]:
    """Split LLM output into discrete markdown table blocks (header+sep+data)."""
    blocks: List[List[str]] = []
    i = 0
    total = len(lines)
    while i < total - 1:
        header_line = str(lines[i] or "").strip()
        sep_line = str(lines[i + 1] or "").strip()
        if not (
            _looks_like_markdown_table_row_for_shots(header_line)
            and len(_split_markdown_row_escaped(header_line)) >= 2
            and _is_markdown_table_separator(sep_line)
        ):
            i += 1
            continue

        kept_lines: List[str] = [str(lines[i]), str(lines[i + 1])]
        data_row_count = 0
        j = i + 2
        while j < total:
            stripped = str(lines[j] or "").strip()
            if not stripped:
                if data_row_count > 0:
                    break
                j += 1
                continue
            if stripped.startswith("#"):
                break
            if _looks_like_markdown_table_row_for_shots(stripped):
                if _is_markdown_table_separator(stripped):
                    if data_row_count > 0:
                        break
                    j += 1
                    continue
                if data_row_count > 0 and _is_shot_markdown_header_row(stripped):
                    break
                kept_lines.append(stripped)
                data_row_count += 1
                j += 1
                continue
            if data_row_count > 0:
                break
            j += 1

        if data_row_count > 0:
            blocks.append(kept_lines)
        i = max(j, i + 2)

    return blocks


def _score_shot_markdown_table_block(block_lines: List[str]) -> int:
    """Prefer tables with real EP##_SC##_SH## ids over prompt example tables."""
    real_ids = 0
    for line in block_lines[2:]:
        cells = _split_markdown_row_escaped(str(line or "").strip())
        if not cells:
            continue
        if _is_shot_markdown_header_row(line):
            continue
        if _shot_id_cell_looks_real(cells[0]):
            real_ids += 1
    return real_ids


def sanitize_shots_markdown_table_text(text: Any) -> str:
    """Keep one Shot List markdown table from LLM output.

    Stops each table at blank lines / re-headers (no cross-table merge).
    If multiple tables exist, prefer the block with the most real Shot IDs
    so prompt example tables do not displace the actual shot list.
    """
    cleaned = sanitize_llm_markdown_output(str(text or ""))
    if not cleaned:
        return ""

    lines = str(cleaned).splitlines()
    if not lines:
        return ""

    blocks = _extract_shot_markdown_table_blocks(lines)
    if not blocks:
        return ""

    best_block = max(
        blocks,
        key=lambda block: (_score_shot_markdown_table_block(block), len(block)),
    )
    if not best_block:
        return ""

    return "\n".join(str(line) for line in best_block).strip()


def parse_shots_markdown_table(markdown_text: str) -> Tuple[List[str], List[Dict[str, str]], int]:
    """Parse a markdown shot table into headers and rows.

    Returns (headers, rows, table_line_count).
    """
    if not markdown_text:
        return [], [], 0

    lines = str(markdown_text).splitlines()
    header_idx = -1
    separator_idx = -1

    for i in range(len(lines) - 1):
        header_line = lines[i].strip()
        sep_line = lines[i + 1].strip()
        if not _looks_like_markdown_table_row_for_shots(header_line):
            continue
        header_cells_raw = _split_markdown_row_escaped(header_line)
        if len(header_cells_raw) < 2:
            continue
        if _is_markdown_table_separator(sep_line):
            header_idx = i
            separator_idx = i + 1
            break

    raw_headers: List[str] = []
    if header_idx >= 0 and separator_idx >= 0:
        raw_headers = _split_markdown_row_escaped(lines[header_idx].strip())

    # Fallback: some providers occasionally return a markdown table where
    # the header row is missing, but separator/data rows still exist.
    if not raw_headers:
        sep_only_idx = -1
        for i, line in enumerate(lines):
            if _is_markdown_table_separator(str(line or "").strip()):
                sep_only_idx = i
                break

        if sep_only_idx >= 0:
            first_data_cells: List[str] = []
            for line in lines[sep_only_idx + 1 :]:
                stripped = str(line or "").strip()
                if not stripped:
                    continue
                if stripped.startswith("#"):
                    break
                if _looks_like_markdown_table_row_for_shots(stripped) and not _is_markdown_table_separator(stripped):
                    first_data_cells = _split_markdown_row_escaped(stripped)
                    break

            if first_data_cells:
                fallback_headers = [
                    "Shot ID",
                    "Shot Name",
                    "Scene ID",
                    "Shot Logic (CN)",
                    "Start Frame",
                    "Video Content",
                    "Duration (s)",
                    "Keyframes",
                    "End Frame",
                    "Start Frame (CN)",
                    "Video Content (CN)",
                    "Keyframes (CN)",
                    "End Frame (CN)",
                    "Associated Entities",
                ]
                needed = len(first_data_cells)
                if needed > len(fallback_headers):
                    fallback_headers.extend([f"Column {idx}" for idx in range(len(fallback_headers) + 1, needed + 1)])
                raw_headers = fallback_headers[:needed]
                separator_idx = sep_only_idx

    if not raw_headers or separator_idx < 0:
        return [], [], 0

    headers = [h.replace("*", "").replace("_", "").strip() for h in raw_headers]
    header_count = len(headers)
    if header_count <= 0:
        return [], [], 0
    merge_column_indices = _find_shot_pipe_merge_column_indices(headers)

    rows: List[Dict[str, str]] = []
    table_line_count = 0
    row_cells: List[str] = []

    def _flush_row() -> None:
        nonlocal row_cells
        if not row_cells:
            return
        if all(not str(c or "").strip() for c in row_cells):
            row_cells = []
            return
        normalized = _normalize_markdown_table_cells(
            row_cells,
            header_count,
            merge_column_indices=merge_column_indices,
        )
        rows.append({headers[i]: normalized[i] for i in range(header_count)})
        row_cells = []

    for line in lines[separator_idx + 1:]:
        stripped = line.strip()
        # Blank line ends the first table (avoid merging a second example/header table).
        if not stripped:
            if rows or row_cells:
                break
            continue

        # A new markdown heading usually means current table section ended.
        if stripped.startswith("#"):
            break

        if _looks_like_markdown_table_row_for_shots(stripped):
            if _is_markdown_table_separator(stripped):
                if rows or row_cells:
                    break
                continue
            if (rows or row_cells) and _is_shot_markdown_header_row(stripped):
                break

            table_line_count += 1
            cells = _split_markdown_row_escaped(stripped)
            if not cells:
                continue

            if not row_cells:
                row_cells = list(cells)
            elif len(row_cells) >= header_count:
                _flush_row()
                row_cells = list(cells)
            else:
                row_cells.extend(cells)

            if len(row_cells) >= header_count:
                _flush_row()
            continue

        # Non-pipe line inside table area: append as continuation into last cell.
        if row_cells:
            row_cells[-1] = (str(row_cells[-1] or "") + "\n" + stripped).strip()

    _flush_row()

    return headers, rows, table_line_count


# Whitelist mapping for extra shot markdown columns.
# target=shot_field writes into Shot model columns;
# target=tech_field writes into technical_notes JSON keys.
SHOT_MARKDOWN_COLUMN_WHITELIST: Dict[str, Dict[str, str]] = {
    # Camera grammar / cinematography
    "cameraangle": {"target": "tech_field", "field": "camera_angle"},
    "cameramovement": {"target": "tech_field", "field": "camera_movement"},
    "cameralanguage": {"target": "tech_field", "field": "camera_language"},
    "composition": {"target": "tech_field", "field": "composition"},
    "lens": {"target": "tech_field", "field": "lens"},
    "focallength": {"target": "tech_field", "field": "focal_length"},
    "shottype": {"target": "tech_field", "field": "shot_type"},
    "framing": {"target": "tech_field", "field": "framing"},
    # Light / atmosphere / style
    "lighting": {"target": "tech_field", "field": "lighting"},
    "colortone": {"target": "tech_field", "field": "color_tone"},
    "mood": {"target": "tech_field", "field": "mood"},
    "style": {"target": "tech_field", "field": "style"},
    # Audio / performance
    "sounddesign": {"target": "tech_field", "field": "sound_design"},
    "ambientsound": {"target": "tech_field", "field": "ambient_sound"},
    "dialogue": {"target": "tech_field", "field": "dialogue"},
    "voiceover": {"target": "tech_field", "field": "voiceover_text"},
    # Production / edit notes
    "vfxnotes": {"target": "tech_field", "field": "vfx_notes"},
    "reviewnotes": {"target": "tech_field", "field": "review_notes"},
    "editnotes": {"target": "tech_field", "field": "edit_notes"},
    "continuity": {"target": "tech_field", "field": "continuity"},
    "transition": {"target": "tech_field", "field": "transition"},
}


def _normalize_shot_markdown_col_key(key: str) -> str:
    return re.sub(r"[\s_\-./()（）:：]", "", str(key or "").strip().lower())


_SHOT_MARKDOWN_DEFAULT_HEADERS: List[str] = [
    "Shot ID",
    "Shot Name",
    "Scene ID",
    "Shot Logic (CN)",
    "Start Frame",
    "Video Content",
    "Duration (s)",
    "Keyframes",
    "End Frame",
    "Start Frame (CN)",
    "Video Content (CN)",
    "Keyframes (CN)",
    "End Frame (CN)",
    "Associated Entities",
]


_SHOT_REQUIRED_ROW_FIELDS: List[Tuple[str, List[str]]] = [
    ("Shot ID", ["Shot ID", "shot_id", "镜头ID"]),
    ("Shot Name", ["Shot Name", "shot_name", "镜头名称"]),
    ("Scene ID", ["Scene ID", "scene_id", "Scene Code", "scene_code", "场景ID", "场景编号"]),
    ("Shot Logic (CN)", ["Shot Logic (CN)", "shot_logic_cn", "镜头逻辑", "镜头画面逻辑说明"]),
]


def _coerce_shot_row_associated_entities_or_default(row: Dict[str, Any], *, default: str = "none") -> Tuple[bool, Optional[str]]:
    """Normalize Associated Entities in-place when blank (import accepts empty)."""
    if not isinstance(row, dict):
        return False, None
    aliases = ["Associated Entities", "associated_entities", "关联实体"]
    current = _pick_shot_cell(row, aliases, "")
    if current:
        return False, None
    entity_key = "Associated Entities"
    for key in aliases:
        if key in row:
            entity_key = key
            break
    row[entity_key] = default
    return True, f"Associated Entities missing; defaulted to {default}"


_SHOT_REQUIRED_ROW_FIELD_GROUPS: List[Tuple[str, List[str]]] = [
    ("Video Content or Video Content (CN)", [
        "Video Content", "video_content", "视频内容",
        "Video Content (CN)", "video_content_cn", "video_prompt_cn", "视频内容（中文）",
        "中文视频提示词内容", "中文视频提示词", "视频提示词内容", "视频提示词", "中文动态视频提示词",
        "Prompt (CN)", "Prompts (CN)", "Prompt CN", "prompt_cn", "提示词（中文）", "中文提示词",
        "prompt_preview_cn",
    ]),
]


def _shot_row_technical_notes_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(row, dict):
        return {}
    for key in ("technical_notes", "technicalNotes"):
        raw_notes = row.get(key)
        if isinstance(raw_notes, dict):
            return raw_notes
        if isinstance(raw_notes, str) and raw_notes.strip():
            try:
                parsed = json.loads(raw_notes)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                continue
    return {}


def _pick_shot_cell(row: Dict[str, Any], aliases: List[str], default: str = "") -> str:
    if not isinstance(row, dict):
        return default
    for key in aliases:
        if key in row and row.get(key) is not None:
            return str(row.get(key) or "").strip()
    normalized_aliases = {_normalize_shot_markdown_col_key(key) for key in aliases}
    for raw_key, raw_value in row.items():
        if _normalize_shot_markdown_col_key(raw_key) in normalized_aliases and raw_value is not None:
            return str(raw_value or "").strip()
    notes = _shot_row_technical_notes_dict(row)
    if notes:
        for key in aliases:
            if key in notes and notes.get(key) is not None:
                return str(notes.get(key) or "").strip()
        for raw_key, raw_value in notes.items():
            if _normalize_shot_markdown_col_key(raw_key) in normalized_aliases and raw_value is not None:
                return str(raw_value or "").strip()
    return default


def _pick_shot_video_prompt_cell(row: Dict[str, Any]) -> str:
    direct_value = _pick_shot_cell(row, [
        "Video Content (CN)", "video_content_cn", "video_prompt_cn", "视频内容（中文）",
        "中文视频提示词内容", "中文视频提示词", "视频提示词内容", "视频提示词", "中文动态视频提示词",
        "Prompt (CN)", "Prompts (CN)", "Prompt CN", "prompt_cn", "提示词（中文）", "中文提示词",
        "Video Content", "video_content", "视频内容",
        "prompt_preview_cn",
    ], "")
    if direct_value:
        return direct_value

    for source in (row, _shot_row_technical_notes_dict(row)):
        if not isinstance(source, dict):
            continue
        for raw_key, raw_value in source.items():
            value = str(raw_value or "").strip()
            if not value:
                continue
            key_text = str(raw_key or "").strip().lower()
            normalized_key = _normalize_shot_markdown_col_key(raw_key)
            if (
                ("video" in key_text and "cn" in key_text)
                or "videopromptcn" in normalized_key
                or "videocontentcn" in normalized_key
                or ("视频" in str(raw_key or "") and ("中文" in str(raw_key or "") or "提示词" in str(raw_key or "") or "内容" in str(raw_key or "")))
            ):
                return value
    return ""


def _collect_missing_shot_required_fields(row: Dict[str, Any]) -> List[str]:
    missing_fields: List[str] = []
    for label, aliases in _SHOT_REQUIRED_ROW_FIELDS:
        if not _pick_shot_cell(row, aliases, ""):
            missing_fields.append(label)
    for label, aliases in _SHOT_REQUIRED_ROW_FIELD_GROUPS:
        if label == "Video Content or Video Content (CN)":
            if not _pick_shot_video_prompt_cell(row):
                missing_fields.append(label)
            continue
        if not _pick_shot_cell(row, aliases, ""):
            missing_fields.append(label)
    return missing_fields


def _normalize_shot_business_id(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"\*\*", "", text)
    text = re.sub(r"(?i)^shot\s*", "", text)
    return text.strip().upper()


def _extract_shot_row_business_id(row: Dict[str, Any], *, fallback_index: Optional[int] = None) -> str:
    shot_id = _pick_shot_cell(row, ["Shot ID", "shot_id", "镜头ID"], "")
    normalized = _normalize_shot_business_id(shot_id)
    if normalized:
        return normalized
    if fallback_index is not None:
        return f"__row_{int(fallback_index)}"
    return ""


def _shot_record_db_id(shot: Any) -> int:
    if isinstance(shot, dict):
        try:
            return int(shot.get("id") or 0)
        except Exception:
            return 0
    try:
        return int(getattr(shot, "id", 0) or 0)
    except Exception:
        return 0


def _shot_record_scene_id(shot: Any) -> int:
    if isinstance(shot, dict):
        try:
            return int(shot.get("scene_id") or 0)
        except Exception:
            return 0
    try:
        return int(getattr(shot, "scene_id", 0) or 0)
    except Exception:
        return 0


def _shot_record_business_key(shot: Any) -> str:
    scene_id = _shot_record_scene_id(shot)
    if isinstance(shot, dict):
        business_id = _normalize_shot_business_id(shot.get("shot_id"))
    else:
        business_id = _normalize_shot_business_id(getattr(shot, "shot_id", ""))
    if not business_id:
        return f"{scene_id}::__db_{_shot_record_db_id(shot)}"
    return f"{scene_id}::{business_id}"


def _dedupe_shot_rows_for_import(
    rows: List[Dict[str, Any]],
    *,
    scene_id: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    deduped: List[Dict[str, Any]] = []
    index_by_key: Dict[str, int] = {}
    warnings: List[str] = []
    stable_scene_id = int(scene_id or 0)

    for idx, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            continue
        business_id = _extract_shot_row_business_id(row, fallback_index=idx)
        dedup_key = f"{stable_scene_id}::{business_id}"
        if dedup_key in index_by_key:
            prev_idx = index_by_key[dedup_key]
            warnings.append(
                f"duplicate Shot ID '{business_id}' at rows {prev_idx} and {idx}; kept row {idx}"
            )
            deduped[index_by_key[dedup_key] - 1] = row
            continue
        index_by_key[dedup_key] = len(deduped) + 1
        deduped.append(row)

    return deduped, warnings


def _dedupe_active_shot_records_for_display(shots: List[Any]) -> List[Any]:
    if not shots:
        return []
    ordered_keys: List[str] = []
    best_by_key: Dict[str, Any] = {}
    for shot in shots:
        key = _shot_record_business_key(shot)
        if key not in best_by_key:
            ordered_keys.append(key)
        existing = best_by_key.get(key)
        if existing is None or _shot_record_db_id(shot) >= _shot_record_db_id(existing):
            best_by_key[key] = shot
    return [best_by_key[key] for key in ordered_keys if key in best_by_key]


def _soft_delete_duplicate_active_shots_in_db(
    db: Session,
    *,
    scene_id: Optional[int] = None,
    episode_id: Optional[int] = None,
    project_id: Optional[int] = None,
    scope: str = "scene",
) -> int:
    """Soft-delete duplicate active shots.

    scope=scene: key = scene_id::shot_id (legacy per-scene dedupe)
    scope=episode: key = project_id::episode_id::shot_id (matches unique index)
    """
    filters = [_active_shot_clause()]
    if scene_id is not None:
        filters.append(Shot.scene_id == int(scene_id))
    if episode_id is not None:
        filters.append(Shot.episode_id == int(episode_id))
    if project_id is not None:
        filters.append(Shot.project_id == int(project_id))

    shots = db.query(Shot).filter(*filters).order_by(Shot.id.asc()).all()
    if not shots:
        return 0

    use_episode_scope = str(scope or "scene").strip().lower() == "episode"
    grouped: Dict[str, List[Shot]] = {}
    for shot in shots:
        business_id = _normalize_shot_business_id(getattr(shot, "shot_id", ""))
        if not business_id:
            continue
        if use_episode_scope:
            key = (
                f"{int(getattr(shot, 'project_id', 0) or 0)}::"
                f"{int(getattr(shot, 'episode_id', 0) or 0)}::{business_id}"
            )
        else:
            key = f"{int(getattr(shot, 'scene_id', 0) or 0)}::{business_id}"
        grouped.setdefault(key, []).append(shot)

    duplicate_ids: List[int] = []
    for group in grouped.values():
        if len(group) <= 1:
            continue
        group.sort(key=lambda item: int(getattr(item, "id", 0) or 0))
        duplicate_ids.extend(int(item.id) for item in group[:-1])

    if not duplicate_ids:
        return 0

    now = now_bj_iso()
    db.query(Shot).filter(Shot.id.in_(duplicate_ids)).update(
        {Shot.is_deleted: True, Shot.deleted_at: now},
        synchronize_session=False,
    )
    logger.info(
        "[shot_import.dedup] soft_deleted duplicate active shots count=%s scene_id=%s episode_id=%s project_id=%s scope=%s",
        len(duplicate_ids),
        scene_id,
        episode_id,
        project_id,
        "episode" if use_episode_scope else "scene",
    )
    return len(duplicate_ids)


def _find_active_shot_by_business_id(
    db: Session,
    *,
    project_id: int,
    episode_id: int,
    shot_id: Any,
    exclude_scene_id: Optional[int] = None,
) -> Optional[Shot]:
    business_id = _normalize_shot_business_id(shot_id)
    if not business_id:
        return None
    rows = (
        db.query(Shot)
        .filter(
            Shot.project_id == int(project_id),
            Shot.episode_id == int(episode_id),
            _active_shot_clause(),
        )
        .all()
    )
    for row in rows:
        if exclude_scene_id is not None and int(getattr(row, "scene_id", 0) or 0) == int(exclude_scene_id):
            continue
        if _normalize_shot_business_id(getattr(row, "shot_id", "")) == business_id:
            return row
    return None


def _escape_shot_markdown_cell(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = text.replace("|", "\\|")
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")
    return text


def _collect_shot_markdown_headers(rows: List[Dict[str, Any]]) -> List[str]:
    discovered_headers: List[str] = []
    discovered_set = set()
    for item in rows:
        if not isinstance(item, dict):
            continue
        for key in item.keys():
            normalized_key = str(key or "").strip()
            if not normalized_key or normalized_key in discovered_set:
                continue
            discovered_set.add(normalized_key)
            discovered_headers.append(normalized_key)

    if not discovered_headers:
        return list(_SHOT_MARKDOWN_DEFAULT_HEADERS)

    headers: List[str] = [h for h in _SHOT_MARKDOWN_DEFAULT_HEADERS if h in discovered_set]
    headers.extend([h for h in discovered_headers if h not in headers])
    return headers


def _serialize_shot_rows_to_markdown(rows: List[Dict[str, Any]]) -> str:
    headers = _collect_shot_markdown_headers(rows)
    header_line = "| " + " | ".join(headers) + " |"
    separator_line = "| " + " | ".join([":---"] * len(headers)) + " |"
    body_lines = []
    for item in rows:
        row_values = [_escape_shot_markdown_cell(item.get(header, "")) for header in headers]
        body_lines.append("| " + " | ".join(row_values) + " |")
    return "\n".join([header_line, separator_line] + body_lines)


def _coerce_shot_row_duration_or_default(row: Dict[str, Any], *, default: float = 2.0) -> Tuple[bool, Optional[str]]:
    """Normalize Duration (s) in-place.

    Import already defaults missing/invalid duration to 2.0; validation must match
    that behavior so apply does not reject rows the importer would accept.
    Returns (changed, warning_or_none).
    """
    if not isinstance(row, dict):
        return False, None
    raw_duration = _pick_shot_cell(row, ["Duration (s)", "Duration", "duration", "时长", "时长(s)"], "")
    duration_ok = False
    parsed: Optional[float] = None
    if raw_duration:
        match = re.search(r"[\d\.]+", str(raw_duration))
        if match:
            try:
                parsed = float(match.group())
                duration_ok = parsed > 0
            except Exception:
                duration_ok = False
    if duration_ok and parsed is not None:
        # Keep original cell text when already valid.
        return False, None

    # Prefer writing the canonical English header used by the shot table schema.
    duration_key = "Duration (s)"
    for key in ("Duration (s)", "Duration", "duration", "时长", "时长(s)"):
        if key in row:
            duration_key = key
            break
    row[duration_key] = str(default)
    warning = (
        f"Duration (s) missing/invalid ({raw_duration or 'empty'}); defaulted to {default}"
        if raw_duration
        else f"Duration (s) missing; defaulted to {default}"
    )
    return True, warning


def _validate_shot_rows_or_raise(
    content: Any,
    *,
    source_label: str,
    status_code: int = 400,
) -> List[Dict[str, Any]]:
    if not isinstance(content, list):
        raise HTTPException(status_code=status_code, detail=f"{source_label} must be a non-empty shot row list")

    normalized_rows: List[Dict[str, Any]] = []
    for idx, item in enumerate(content, start=1):
        if not isinstance(item, dict):
            raise HTTPException(status_code=status_code, detail=f"{source_label} row {idx} is not an object")
        if not any(str(val or "").strip() for val in item.values()):
            continue
        normalized_rows.append(item)

    if not normalized_rows:
        raise HTTPException(status_code=status_code, detail=f"{source_label} did not contain any non-empty shot rows")

    row_errors: List[str] = []
    for idx, row in enumerate(normalized_rows, start=1):
        _coerce_shot_row_duration_or_default(row)
        _coerce_shot_row_associated_entities_or_default(row)
        missing_fields = _collect_missing_shot_required_fields(row)

        if missing_fields:
            row_errors.append(f"row {idx} missing/invalid: {', '.join(missing_fields)}")

    if row_errors:
        detail = "; ".join(row_errors[:5])
        if len(row_errors) > 5:
            detail += f"; and {len(row_errors) - 5} more rows"
        raise HTTPException(status_code=status_code, detail=f"{source_label} failed structural validation: {detail}")

    deduped_rows, _ = _dedupe_shot_rows_for_import(normalized_rows)
    return deduped_rows


def _validate_shot_rows_for_apply_with_tolerance(
    content: Any,
    *,
    source_label: str,
    status_code: int = 400,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    if not isinstance(content, list):
        raise HTTPException(status_code=status_code, detail=f"{source_label} must be a non-empty shot row list")

    normalized_rows: List[Dict[str, Any]] = []
    skipped_errors: List[str] = []
    for idx, item in enumerate(content, start=1):
        if not isinstance(item, dict):
            skipped_errors.append(f"row {idx} is not an object")
            continue
        if not any(str(val or "").strip() for val in item.values()):
            continue

        if _is_placeholder_shot_row(item):
            shot_id = _pick_shot_cell(item, ["Shot ID", "shot_id", "镜头ID"], "") or "(blank)"
            skipped_errors.append(
                f"row {idx}: skipped placeholder/template Shot ID '{shot_id}'"
            )
            continue

        _, duration_warning = _coerce_shot_row_duration_or_default(item)
        if duration_warning:
            skipped_errors.append(f"row {idx}: {duration_warning}")
        _, entities_warning = _coerce_shot_row_associated_entities_or_default(item)
        if entities_warning:
            skipped_errors.append(f"row {idx}: {entities_warning}")

        missing_fields = _collect_missing_shot_required_fields(item)

        if missing_fields:
            skipped_errors.append(f"row {idx} missing/invalid: {', '.join(missing_fields)}")
            continue

        normalized_rows.append(item)

    if not normalized_rows:
        detail = "; ".join(skipped_errors[:5]) if skipped_errors else "no non-empty shot rows"
        if len(skipped_errors) > 5:
            detail += f"; and {len(skipped_errors) - 5} more rows"
        raise HTTPException(status_code=status_code, detail=f"{source_label} failed structural validation: {detail}")

    deduped_rows, dedupe_warnings = _dedupe_shot_rows_for_import(normalized_rows)
    for warning in dedupe_warnings:
        skipped_errors.append(f"dedupe: {warning}")

    return deduped_rows, skipped_errors


def _resolve_shots_data_for_apply(
    scene: Scene,
    provided_content: Any,
    *,
    source_label: str,
    status_code: int = 400,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Prefer freshly parsed stored markdown over stale provided staging rows."""
    markdown_rows: List[Dict[str, Any]] = []
    markdown_skipped: List[str] = []
    markdown_error: Optional[str] = None
    raw_value = str(getattr(scene, "ai_shots_result", None) or "").strip()

    if raw_value.startswith("{"):
        try:
            legacy = json.loads(raw_value)
            if isinstance(legacy, dict) and legacy.get("raw_text"):
                raw_value = str(legacy.get("raw_text") or "").strip()
        except Exception:
            pass

    if raw_value:
        try:
            _, parsed_rows, _ = _parse_shot_markdown_or_raise(
                raw_value,
                source_label=f"{source_label} (stored markdown)",
                status_code=status_code,
            )
            markdown_rows, markdown_skipped = _validate_shot_rows_for_apply_with_tolerance(
                parsed_rows,
                source_label=f"{source_label} (stored markdown)",
                status_code=status_code,
            )
        except HTTPException as exc:
            markdown_rows = []
            markdown_skipped = []
            markdown_error = str(getattr(exc, "detail", None) or exc)

    provided_rows: List[Dict[str, Any]] = []
    provided_skipped: List[str] = []
    provided_error: Optional[str] = None
    if provided_content is not None:
        try:
            provided_rows, provided_skipped = _validate_shot_rows_for_apply_with_tolerance(
                provided_content,
                source_label=f"{source_label} (provided content)",
                status_code=status_code,
            )
        except HTTPException as exc:
            provided_rows = []
            provided_skipped = []
            provided_error = str(getattr(exc, "detail", None) or exc)

    if markdown_rows and not provided_rows:
        return markdown_rows, markdown_skipped
    if provided_rows and not markdown_rows:
        return provided_rows, provided_skipped
    if len(markdown_rows) > len(provided_rows):
        logger.info(
            "[apply_scene_ai_result] prefer stored markdown rows over provided content | markdown=%s provided=%s",
            len(markdown_rows),
            len(provided_rows),
        )
        return markdown_rows, markdown_skipped
    if len(provided_rows) > len(markdown_rows):
        return provided_rows, provided_skipped
    if markdown_rows:
        return markdown_rows, markdown_skipped

    # Both sources empty: surface the real structural validation failure instead of
    # collapsing into a generic "No shot rows" message.
    error_parts = [part for part in (markdown_error, provided_error) if part]
    if error_parts:
        detail = " | ".join(dict.fromkeys(error_parts))
        logger.warning(
            "[apply_scene_ai_result] no valid rows after validation | source=%s detail=%s",
            source_label,
            detail[:800],
        )
        raise HTTPException(status_code=status_code, detail=detail)

    return provided_rows, provided_skipped


def _parse_shot_markdown_or_raise(
    markdown_text: str,
    *,
    source_label: str,
    status_code: int = 400,
) -> Tuple[List[str], List[Dict[str, str]], int]:
    headers, rows, table_line_count = parse_shots_markdown_table(markdown_text or "")
    if not rows:
        raise HTTPException(status_code=status_code, detail=f"{source_label} did not produce a parseable markdown table")
    if table_line_count >= 4 and len(rows) > 0 and (len(rows) * 2) <= table_line_count:
        raise HTTPException(
            status_code=status_code,
            detail=f"{source_label} lost rows during markdown parsing; fix the table before continuing",
        )
    return headers, rows, table_line_count


def _validate_shot_rows_roundtrip_or_raise(
    content: Any,
    *,
    source_label: str,
    status_code: int = 400,
) -> Tuple[List[Dict[str, Any]], str]:
    rows = _validate_shot_rows_or_raise(content, source_label=source_label, status_code=status_code)
    markdown_text = _serialize_shot_rows_to_markdown(rows)
    _, reparsed_rows, _ = _parse_shot_markdown_or_raise(markdown_text, source_label=source_label, status_code=status_code)
    if len(reparsed_rows) != len(rows):
        raise HTTPException(
            status_code=status_code,
            detail=(
                f"{source_label} changed row count after markdown round-trip "
                f"({len(rows)} -> {len(reparsed_rows)}); fix pipe escaping or multiline cells before continuing"
            ),
        )
    return rows, markdown_text

