# -*- coding: utf-8 -*-
"""Subject Index usability checks and episode-field resolve/heal."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Iterator, List, Optional, Tuple

from app.services.llm_markdown_sanitize import sanitize_subject_index_text

logger = logging.getLogger("api_logger")

def _subject_index_rows_present(subject_index_text: Any) -> bool:
    """Return True when text contains at least one real entity row (not header-only)."""
    text = str(subject_index_text or "")
    if not text.strip():
        return False
    return bool(
        re.search(r"(?im)^\s*\|\s*S\d{3,}\s*\|", text)
        or re.search(r"(?im)^\s*S\d{3,}\s*\|", text)
        or re.search(
            r"(?im)^\s*S\d{3,}(?:\s+|\t+|\s*\|\s*)[a-z_]+(?:\s+|\t+|\s*\|\s*)",
            text,
        )
        or re.search(r"(?im)^\s*subject_no\s*=\s*[A-Za-z]?\d+\b", text)
        or re.search(
            r"(?im)^\s*\|?\s*[A-Za-z]+\d+\s*\|\s*(?:character|prop|environment|cover_poster|角色|道具|环境|封面)",
            text,
        )
        or re.search(
            r"(?im)^\s*\|?\s*S\d{3,}\s*\|\s*(?:character|prop|environment|cover_poster|角色|道具|环境|封面)",
            text,
        )
    )


def _subject_index_has_usable_content(subject_index_text: Any) -> bool:
    """Return True when Subject Index has at least one real entity row (not header-only)."""
    sanitized = sanitize_subject_index_text(subject_index_text)
    if _subject_index_rows_present(sanitized):
        return True
    # sanitize may be overly strict (e.g. Chinese headers); fall back to raw row detection.
    return _subject_index_rows_present(subject_index_text)


def _coerce_subject_index_candidate(subject_index_text: Any) -> str:
    """Return the best usable Subject Index snippet from raw/sanitized text."""
    raw = str(subject_index_text or "")
    sanitized = sanitize_subject_index_text(raw)
    if _subject_index_rows_present(sanitized):
        return sanitized.strip()
    if _subject_index_rows_present(raw):
        # Keep from the first detectable row/header hint to avoid shipping unrelated prose.
        lines = raw.replace("\r\n", "\n").splitlines()
        start_idx = 0
        header_re = re.compile(
            r"(?i)^\s*(?:#{1,6}\s*)?(?:\*\*)?\s*(?:subject\s*index|subjects\s*index|资产清单|实体清单|设计资产索引)\b"
        )
        hint_re = re.compile(r"(?i)subject_no|subject_type|script_entity_coverage")
        row_re = re.compile(r"(?im)^\s*\|?\s*S\d{3,}\s*\|")
        for idx, line in enumerate(lines):
            stripped = str(line or "").strip()
            if header_re.search(stripped) or hint_re.search(stripped) or row_re.match(stripped):
                start_idx = idx
                break
        return "\n".join(lines[start_idx:]).strip()
    return sanitized.strip()


def _extract_subject_index_from_stage_outputs(stage_outputs_raw: Any) -> str:
    """Pull Subject Index from episode.ai_stage_outputs stage2.subject_index."""
    raw = str(stage_outputs_raw or "").strip()
    if not raw:
        return ""
    try:
        parsed = json.loads(raw)
    except Exception:
        return ""
    if not isinstance(parsed, dict):
        return ""
    stages = parsed.get("stages") if isinstance(parsed.get("stages"), dict) else {}
    stage2 = stages.get("stage2") if isinstance(stages.get("stage2"), dict) else {}
    outputs = stage2.get("outputs") if isinstance(stage2.get("outputs"), dict) else {}
    slot = outputs.get("subject_index") if isinstance(outputs.get("subject_index"), dict) else {}
    return _coerce_subject_index_candidate(slot.get("content"))


def resolve_usable_episode_subject_index(
    episode: Any,
    *,
    request_text: Any = None,
    explicit_subject_index: Any = None,
    heal_episode_field: bool = False,
    db: Any = None,
) -> str:
    """Resolve a usable Subject Index for downstream gates/injection.

    Prefer explicit client-provided Subject Index (what the Stage 2 UI shows), then
    stage_outputs, then episode.ai_scene_analysis_subject_index, then request-embedded
    text. Optionally heal a stale/empty episode field to the chosen source.
    """
    explicit_raw = _coerce_subject_index_candidate(explicit_subject_index)
    episode_field_raw = _coerce_subject_index_candidate(
        getattr(episode, "ai_scene_analysis_subject_index", None) if episode is not None else None
    )
    stage_outputs_raw = _extract_subject_index_from_stage_outputs(
        getattr(episode, "ai_stage_outputs", None) if episode is not None else None
    )
    request_raw = _coerce_subject_index_candidate(request_text)

    candidates: List[Tuple[str, str]] = [
        ("explicit", explicit_raw),
        ("stage_outputs", stage_outputs_raw),
        ("episode_field", episode_field_raw),
        ("request_text", request_raw),
    ]
    resolved_source = ""
    resolved_text = ""
    for source, candidate in candidates:
        if _subject_index_has_usable_content(candidate):
            resolved_source = source
            resolved_text = candidate
            break

    if not resolved_text:
        logger.warning(
            "[subject_index] resolve_miss episode_id=%s explicit_chars=%s episode_chars=%s stage_chars=%s request_chars=%s",
            getattr(episode, "id", None) if episode is not None else None,
            len(str(explicit_subject_index or "")),
            len(str(getattr(episode, "ai_scene_analysis_subject_index", "") or "") if episode is not None else ""),
            len(str(getattr(episode, "ai_stage_outputs", "") or "") if episode is not None else ""),
            len(str(request_text or "")),
        )

    if (
        heal_episode_field
        and resolved_text
        and episode is not None
        and resolved_source in {"explicit", "stage_outputs", "request_text"}
        and str(episode_field_raw or "").strip() != str(resolved_text or "").strip()
    ):
        try:
            episode.ai_scene_analysis_subject_index = resolved_text
            if db is not None:
                db.add(episode)
                db.commit()
            logger.info(
                "[subject_index] healed episode.ai_scene_analysis_subject_index from %s episode_id=%s chars=%s",
                resolved_source,
                getattr(episode, "id", None),
                len(resolved_text),
            )
        except Exception as heal_err:
            logger.warning(
                "[subject_index] failed healing episode subject index from %s episode_id=%s err=%s",
                resolved_source,
                getattr(episode, "id", None),
                heal_err,
            )
            try:
                if db is not None:
                    db.rollback()
            except Exception:
                pass

    return resolved_text


def _subject_index_has_cover_poster(subject_index_text: Any) -> bool:
    text = sanitize_subject_index_text(subject_index_text)
    if not text:
        return False

    if re.search(r"(?i)\bsubject_type\s*=\s*(cover_poster|poster|posters|cover|covers|封面|封面海报|海报)\b", text):
        return True
    if re.search(r"(?im)\b(?:subject_type|type)\b\s*[:=]\s*(cover_poster|poster|posters|cover|covers|封面|封面海报|海报)\b", text):
        return True

    def _normalize_type(value: Any) -> str:
        key = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
        if key in {"cover_poster", "coverposter", "poster", "posters", "cover", "covers", "封面", "封面海报", "海报"}:
            return "cover_poster"
        return key

    for raw_line in str(text).splitlines():
        line = str(raw_line or "").replace("\ufeff", "").strip()
        line = re.sub(r"^\s*>\s*", "", line)
        line = re.sub(r"^\s*[-*+]\s+", "", line).strip()
        if not line:
            continue
        if "|" not in line:
            continue
        normalized_line = line.strip("|").strip()
        parts = [p.strip() for p in normalized_line.split("|")]
        if len(parts) < 2:
            continue
        first_col = str(parts[0] or "").strip().lower()
        if first_col in {"subject_no", "subject_id", "id", "编号"}:
            continue
        if _normalize_type(parts[1]) == "cover_poster":
            return True

    # subject_no-style line fallback, e.g.:
    # subject_no=S001 | subject_type=poster | ...
    for raw_line in str(text).splitlines():
        line = str(raw_line or "").replace("\ufeff", "").strip()
        if not line:
            continue
        if not re.search(r"(?i)\bsubject_(?:no|id)\b", line):
            continue
        matched = re.search(r"(?i)\bsubject_type\s*[:=]\s*([a-zA-Z_\-\u4e00-\u9fff]+)", line)
        if matched and _normalize_type(matched.group(1)) == "cover_poster":
            return True
    return False


_VISUAL_BACKFILL_ROOT_KEYS = (
    "project_visual_backfill",
    "Project_Visual_Backfill",
    "projectVisualBackfill",
)
_VISUAL_BACKFILL_CONTENT_KEYS = (
    "Global_Style",
    "global_style",
    "borrowed_films",
    "tone",
    "lighting",
    "color_spectrum",
    "plot_summary",
    "comprehensive_plot",
    "comprehensive_assets",
    "music_recommendation",
)


def _visual_backfill_global_style(obj: Any) -> str:
    if not isinstance(obj, dict):
        return ""
    return str(obj.get("Global_Style") or obj.get("global_style") or "").strip()


def _coerce_project_visual_backfill_obj(parsed: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(parsed, dict):
        return None
    for key in _VISUAL_BACKFILL_ROOT_KEYS:
        inner = parsed.get(key)
        if isinstance(inner, dict) and inner:
            return inner
    # Unwrapped objects must carry 全局风格. A stray {tone/lighting} blob in
    # scene body or prompt echo must not count as the completeness trailer.
    if _visual_backfill_global_style(parsed):
        return parsed
    return None


def _iter_json_object_candidates(text: str) -> Iterator[str]:
    fence_re = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
    for match in fence_re.finditer(text):
        candidate = str(match.group(1) or "").strip()
        if candidate:
            yield candidate

    stripped = str(text or "").strip()
    if stripped:
        yield stripped

    brace_depth = 0
    start_index = -1
    in_string = False
    escape = False
    for index, char in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char == "{":
            if brace_depth == 0:
                start_index = index
            brace_depth += 1
        elif char == "}":
            if brace_depth <= 0:
                continue
            brace_depth -= 1
            if brace_depth == 0 and start_index >= 0:
                yield text[start_index : index + 1]
                start_index = -1


def extract_project_visual_backfill_object(result_text: Any) -> Optional[Dict[str, Any]]:
    """Return a parseable project_visual_backfill object, or None if missing/truncated."""
    text = str(result_text or "").strip()
    if not text:
        return None

    for candidate in _iter_json_object_candidates(text):
        try:
            parsed = json.loads(candidate)
        except Exception:
            continue
        coerced = _coerce_project_visual_backfill_obj(parsed)
        if coerced:
            return coerced
    return None


def _script_optimization_has_project_visual_backfill(result_text: Any) -> bool:
    """True only when a parseable backfill object has a non-empty Global_Style."""
    obj = extract_project_visual_backfill_object(result_text)
    return bool(_visual_backfill_global_style(obj))


def _first_json_object_span(text: str, start: int = 0) -> Optional[Tuple[int, int]]:
    brace_depth = 0
    start_index = -1
    in_string = False
    escape = False
    source = str(text or "")
    for index in range(max(0, int(start)), len(source)):
        char = source[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char == "{":
            if brace_depth == 0:
                start_index = index
            brace_depth += 1
        elif char == "}":
            if brace_depth <= 0:
                continue
            brace_depth -= 1
            if brace_depth == 0 and start_index >= 0:
                return start_index, index + 1
    return None


def _strip_leading_visual_backfill_block(result_text: Any) -> str:
    source = str(result_text or "").replace("\r\n", "\n")
    stripped = source.lstrip()
    if not stripped:
        return ""
    fence = re.match(r"^```(?:json)?[ \t]*\n", stripped, flags=re.IGNORECASE)
    body_start = fence.end() if fence else 0
    body = stripped[body_start:]
    if not body.lstrip().startswith("{"):
        return source
    span = _first_json_object_span(stripped, body_start)
    if span is None:
        return source
    obj_start, obj_end = span
    try:
        parsed = json.loads(stripped[obj_start:obj_end])
    except Exception:
        return source
    if not _coerce_project_visual_backfill_obj(parsed):
        return source
    after = stripped[obj_end:].lstrip()
    if after.startswith("```"):
        after = after[3:]
        if after.startswith("\n"):
            after = after[1:]
    return after.lstrip()


def strip_trailing_project_visual_backfill_section(result_text: Any) -> str:
    text = str(result_text or "").replace("\r\n", "\n").rstrip()
    if not text:
        return ""

    marker_re = re.compile(
        r"(?im)^(?:#{1,6}\s*)?(?:第三部分[:：]?\s*)?Project\s*Visual\s*Backfill\b"
        r"|^第三部分[:：]?\s*Project\s*Visual\s*Backfill\b"
        r"|^\{\s*\"project_visual_backfill\"\s*:",
    )
    last_idx = -1
    for match in marker_re.finditer(text):
        last_idx = match.start()
    if last_idx >= 0 and last_idx >= int(len(text) * 0.4):
        return text[:last_idx].rstrip()
    return text


def strip_project_visual_backfill_sections(result_text: Any) -> str:
    """Drop echoed visual-backfill JSON; scene_split already owns the canonical copy."""
    return strip_trailing_project_visual_backfill_section(
        _strip_leading_visual_backfill_block(result_text)
    )


def build_project_visual_backfill_readonly_injection(backfill_obj: Any) -> str:
    """Compact read-only context. Downstream LLMs must not rewrite or re-emit the JSON."""
    from app.core.prompt_injection import wrap_injection_section

    obj = _coerce_project_visual_backfill_obj(backfill_obj)
    if not obj and isinstance(backfill_obj, dict):
        obj = backfill_obj
    if not obj:
        return ""
    lines: List[str] = []
    for key in (
        "Global_Style",
        "tone",
        "lighting",
        "music_recommendation",
        "comprehensive_plot",
        "comprehensive_assets",
    ):
        value = obj.get(key)
        if value is None or value == "":
            continue
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False)
        lines.append(f"{key}={value}")
    if not lines:
        return ""
    return wrap_injection_section("项目视觉回填", "\n".join(lines))


def merge_project_visual_backfill_into_result_text(result_text: Any, backfill_obj: Any) -> str:
    payload_obj = _coerce_project_visual_backfill_obj(backfill_obj) or (
        backfill_obj if isinstance(backfill_obj, dict) else None
    )
    if not payload_obj:
        return str(result_text or "")
    payload = {"project_visual_backfill": payload_obj}
    block = (
        "### 第三部分：Project Visual Backfill\n"
        "```json\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
        "```"
    )
    text = strip_trailing_project_visual_backfill_section(result_text)
    if not text:
        return block
    return f"{text}\n\n{block}"


