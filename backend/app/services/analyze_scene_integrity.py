# -*- coding: utf-8 -*-
"""Output integrity / token helpers for analyze_scene continuation loops."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

def _is_length_finish_reason(reason: Any) -> bool:
    r = str(reason or "").strip().lower().replace("-", "_")
    return r in {
        "length",
        "max_tokens",
        "max_token",
        "max_output_tokens",
        "output_token_limit",
        "token_limit",
    }

def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    # Heuristic: ~4 bytes per token (good enough for debug)
    return (len(text.encode("utf-8")) + 3) // 4

def _merge_usage(total: Dict[str, Any], part: Dict[str, Any]) -> Dict[str, Any]:
    total = dict(total or {})
    part = dict(part or {})

    def _add(key: str, value: Any):
        if value is None:
            return
        try:
            iv = int(value)
        except Exception:
            return
        total[key] = int(total.get(key) or 0) + iv

    # Common OpenAI-style keys
    _add("prompt_tokens", part.get("prompt_tokens"))
    _add("completion_tokens", part.get("completion_tokens"))
    _add("total_tokens", part.get("total_tokens"))
    # Some providers use input/output naming
    _add("input_tokens", part.get("input_tokens"))
    _add("output_tokens", part.get("output_tokens"))

    # Preserve provider-specific extra usage fields if they are scalar and not already present
    for k, v in part.items():
        if k in total:
            continue
        if isinstance(v, (int, float, str)):
            total[k] = v
    return total

def _detect_scene_output_sections(output_text: str) -> Dict[str, Any]:
    text = str(output_text or "")
    checks = {
        "part_1": re.compile(r"(?im)^\s*(?:#{1,6}\s*)?Part\s*1\b"),
        "subject_index": re.compile(r"(?im)^\s*(?:#{1,6}\s*)?Subject\s*Index\b"),
        "part_2": re.compile(r"(?im)^\s*(?:#{1,6}\s*)?Part\s*2\b"),
        "final_consistency_report": re.compile(r"(?im)^\s*(?:#{1,6}\s*)?Final\s+Consistency\s+Report\b"),
    }
    found_sections: Dict[str, bool] = {k: bool(p.search(text)) for k, p in checks.items()}
    # Disable forced structural continuation to support decoupled Phase 1 / Phase 2 prompts.
    missing_sections = [] 
    return {
        "found_sections": found_sections,
        "missing_sections": missing_sections,
        "structure_incomplete": False,
    }

def _detect_output_integrity(
    output_text: str,
    segments: List[Dict[str, Any]],
    final_finish_reason: Optional[str],
    *,
    is_scene_beats_stage: bool = False,
    is_subject_index_extraction_stage: bool = False,
) -> Dict[str, Any]:
    text = (output_text or "").strip()
    segment_list = segments or []
    had_length_finish = any(_is_length_finish_reason(seg.get("finish_reason")) for seg in segment_list)
    ended_with_length = _is_length_finish_reason(final_finish_reason)
    section_meta = _detect_scene_output_sections(text)
    missing_sections = section_meta.get("missing_sections") or []
    structure_incomplete = bool(section_meta.get("structure_incomplete"))

    json_candidate = ""
    json_expected = False
    explicit_json_response = False
    parseable_json_block_count = 0

    if text.startswith("```"):
        lowered = text.lower()
        if "```json" in lowered or ("```" in lowered and ("{" in text or "[" in text)):
            json_expected = True
            fence_start = text.find("\n")
            fence_end = text.rfind("```")
            if fence_start != -1 and fence_end != -1 and fence_end > fence_start:
                json_candidate = text[fence_start + 1:fence_end].strip()

    if not json_candidate:
        if text.startswith("{") or text.startswith("["):
            json_expected = True
            explicit_json_response = True
            json_candidate = text
        else:
            first_obj = text.find("{")
            last_obj = text.rfind("}")
            first_arr = text.find("[")
            last_arr = text.rfind("]")
            if first_obj != -1 and last_obj > first_obj:
                json_expected = True
                json_candidate = text[first_obj:last_obj + 1].strip()
            elif first_arr != -1 and last_arr > first_arr:
                json_expected = True
                json_candidate = text[first_arr:last_arr + 1].strip()

    # Non-blocking fallback: count parseable fenced JSON blocks in mixed markdown outputs.
    try:
        fence_re = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
        for m in fence_re.finditer(text):
            candidate = str(m.group(1) or "").strip()
            if not candidate:
                continue
            try:
                json.loads(candidate)
                parseable_json_block_count += 1
            except Exception:
                continue
    except Exception:
        parseable_json_block_count = 0

    json_valid = None
    json_error = None
    if json_expected:
        try:
            json.loads(json_candidate)
            json_valid = True
        except Exception as parse_error:
            json_valid = False
            json_error = str(parse_error)

    truncation_suspected = bool(
        ended_with_length
        or (had_length_finish and json_expected and json_valid is False)
        or structure_incomplete
    )

    warning_codes: List[str] = []
    warnings: List[str] = []
    if ended_with_length:
        warning_codes.append("ANALYSIS_OUTPUT_TRUNCATED")
        warnings.append("Analysis output may be incomplete because the response hit a length limit.")
    elif had_length_finish:
        warning_codes.append("ANALYSIS_OUTPUT_CONTINUED")
        warnings.append("Analysis response was split by length limits and auto-continuation was applied.")

    # Only flag JSON invalid for explicit pure-JSON responses.
    # Mixed markdown + partial JSON should stay non-blocking.
    should_flag_json_invalid = bool(json_expected and json_valid is False and explicit_json_response)
    suppress_json_invalid_warning = bool(
        should_flag_json_invalid
        and (
            is_scene_beats_stage
            or is_subject_index_extraction_stage
        )
    )
    if should_flag_json_invalid and not suppress_json_invalid_warning:
        warning_codes.append("ANALYSIS_JSON_INVALID")
        warnings.append("Analysis returned invalid or incomplete JSON. Please review before applying.")

    if structure_incomplete:
        warning_codes.append("ANALYSIS_STRUCTURE_INCOMPLETE")
        warnings.append(
            "Analysis output is missing required sections: "
            + ", ".join([str(x) for x in missing_sections])
            + "."
        )

    return {
        "truncation_detected": had_length_finish,
        "truncation_suspected": truncation_suspected,
        "ended_with_length": ended_with_length,
        "json_expected": json_expected,
        "json_valid": json_valid,
        "json_error": json_error,
        "explicit_json_response": explicit_json_response,
        "parseable_json_block_count": parseable_json_block_count,
        "json_invalid_suppressed": suppress_json_invalid_warning,
        "found_sections": section_meta.get("found_sections") or {},
        "missing_sections": missing_sections,
        "structure_incomplete": structure_incomplete,
        "warning_codes": warning_codes,
        "warnings": warnings,
    }

def _to_int(value: Any) -> int:
    try:
        parsed = int(value)
        return parsed if parsed > 0 else 0
    except Exception:
        return 0

def _dedupe_overlap(existing: str, incoming: str) -> str:
    if not existing or not incoming:
        return incoming
    candidates = [
        existing[-200:],
        existing[-400:],
        existing[-800:],
    ]
    for c in candidates:
        if c and incoming.startswith(c):
            return incoming[len(c):]
    inc_l = incoming.lstrip()
    for c in candidates:
        if c and inc_l.startswith(c):
            return inc_l[len(c):]
    return incoming
