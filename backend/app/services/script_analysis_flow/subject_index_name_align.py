"""Post-LLM Subject Index name alignment for scene orchestration and asset design.

When Environment Name / Linked Characters / Key Props (scenes) or name / name_en
(assets) are not present in the Subject Index whitelist, call the LLM once to
map those names onto Index-canonical values, then apply the replacements.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core.entity_token import subject_compare_key
from app.services.llm_service import llm_service

logger = logging.getLogger("api_logger")

_TYPED_TOKEN_RE = re.compile(
    r"(?P<prefix>CHAR|PROP|ENV)\s*:\s*\[(?P<body>@?[^\]]+)\]",
    flags=re.IGNORECASE,
)
_PLACEHOLDER_KEYS = {
    "",
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


def _normalize_display_name(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"^(?:CHAR|PROP|ENV|VEFX|SFX)\s*:\s*", "", text, flags=re.IGNORECASE).strip()
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1].strip()
    text = text.lstrip("@").strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _is_placeholder_name(value: Any) -> bool:
    text = re.sub(r"<br\s*/?>", " ", str(value or ""), flags=re.IGNORECASE)
    text = text.replace("*", "").strip()
    if not text:
        return True
    key = subject_compare_key(text)
    compact = re.sub(r"[\s_*`'\"“”‘’]+", "", text).lower()
    return (not key) or compact in _PLACEHOLDER_KEYS or key in _PLACEHOLDER_KEYS


def _bucket_from_subject_type(raw_type: Any) -> str:
    text = str(raw_type or "").strip().lower()
    if text in {"character", "characters", "char", "人物", "角色"}:
        return "characters"
    if text in {"prop", "props", "道具", "物件"}:
        return "props"
    if text in {"environment", "environments", "env", "场景", "环境"}:
        return "environments"
    if text in {"cover", "covers", "cover_poster", "poster", "posters", "封面", "封面海报"}:
        return "covers"
    return ""


def parse_subject_index_whitelist(subject_index_text: Any) -> Dict[str, Any]:
    """Parse Subject Index into per-bucket name sets and canonical rows."""
    raw = str(subject_index_text or "").replace("\r\n", "\n")
    by_bucket: Dict[str, Dict[str, str]] = {
        "characters": {},
        "props": {},
        "environments": {},
        "covers": {},
        "posters": {},
    }
    all_keys: Dict[str, str] = {}
    rows: List[Dict[str, str]] = []

    for line in raw.splitlines():
        stripped = str(line or "").replace("\ufeff", "").strip()
        stripped = re.sub(r"^\s*>\s*", "", stripped)
        stripped = re.sub(r"^\s*[-*+]\s+", "", stripped).strip()
        if not stripped:
            continue
        if not re.match(r"^\|?\s*S\d+\s*\|", stripped, flags=re.IGNORECASE):
            continue
        parts = [p.strip() for p in stripped.strip("|").strip().split("|")]
        if len(parts) < 4:
            continue
        bucket = _bucket_from_subject_type(parts[1])
        if not bucket:
            continue
        name_zh = _normalize_display_name(parts[2])
        name_en = _normalize_display_name(parts[3]) if len(parts) > 3 else ""
        if not name_zh and not name_en:
            continue
        row = {
            "subject_no": str(parts[0] or "").strip(),
            "bucket": bucket,
            "name": name_zh,
            "name_en": name_en,
        }
        rows.append(row)
        for candidate in (name_zh, name_en):
            key = subject_compare_key(candidate)
            if not key:
                continue
            by_bucket[bucket][key] = candidate
            all_keys[key] = candidate
            if bucket == "covers":
                by_bucket["posters"][key] = candidate

    return {
        "rows": rows,
        "by_bucket": by_bucket,
        "all_keys": all_keys,
        "compact_table": _format_subject_index_compact(rows),
    }


def _format_subject_index_compact(rows: List[Dict[str, str]]) -> str:
    if not rows:
        return ""
    lines = [
        "| subject_no | subject_type | subject_name_zh | subject_name_en |",
        "|---|---|---|---|",
    ]
    type_label = {
        "characters": "character",
        "props": "prop",
        "environments": "environment",
        "covers": "cover_poster",
        "posters": "cover_poster",
    }
    for row in rows:
        lines.append(
            "| {no} | {typ} | {zh} | {en} |".format(
                no=row.get("subject_no") or "",
                typ=type_label.get(str(row.get("bucket") or ""), str(row.get("bucket") or "")),
                zh=row.get("name") or "",
                en=row.get("name_en") or "",
            )
        )
    return "\n".join(lines)


def _split_cell_tokens(cell_value: Any) -> List[str]:
    text = str(cell_value or "").strip()
    if not text or _is_placeholder_name(text):
        return []

    tokens: List[str] = []
    seen: Set[str] = set()

    for match in _TYPED_TOKEN_RE.finditer(text):
        display = _normalize_display_name(match.group("body"))
        key = subject_compare_key(display)
        if display and key and key not in seen and not _is_placeholder_name(display):
            seen.add(key)
            tokens.append(display)

    # Also accept plain comma/semicolon separated names (without TYPE: wrappers).
    remainder = _TYPED_TOKEN_RE.sub(" ", text)
    for part in re.split(r"[\n,，;；|/]+", remainder):
        display = _normalize_display_name(part)
        key = subject_compare_key(display)
        if display and key and key not in seen and not _is_placeholder_name(display):
            seen.add(key)
            tokens.append(display)
    return tokens


def _name_in_whitelist(
    name: Any,
    *,
    whitelist: Dict[str, Any],
    bucket: Optional[str] = None,
) -> bool:
    key = subject_compare_key(name)
    if not key:
        return True
    if bucket:
        bucket_map = (whitelist.get("by_bucket") or {}).get(bucket) or {}
        if key in bucket_map:
            return True
        # Covers/posters share identity.
        if bucket in {"covers", "posters"}:
            alt = "posters" if bucket == "covers" else "covers"
            if key in ((whitelist.get("by_bucket") or {}).get(alt) or {}):
                return True
        return False
    return key in (whitelist.get("all_keys") or {})


def _normalize_header_key(value: Any) -> str:
    return re.sub(r"[\s_.\-]+", "", str(value or "").strip().lower())


def _find_col_idx(headers: List[str], aliases: List[str]) -> int:
    normalized_headers = [_normalize_header_key(h) for h in headers]
    normalized_aliases = [_normalize_header_key(a) for a in aliases]
    for idx, header in enumerate(normalized_headers):
        for alias in normalized_aliases:
            if alias and (header == alias or alias in header):
                return idx
    return -1


def _split_table_cells(line: str) -> List[str]:
    text = str(line or "").strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|"):
        text = text[:-1]
    return [c.strip() for c in text.split("|")]


def _bucket_from_typed_prefix(prefix: Any) -> str:
    text = str(prefix or "").strip().upper()
    if text == "CHAR":
        return "characters"
    if text == "PROP":
        return "props"
    if text == "ENV":
        return "environments"
    return ""


def collect_typed_token_name_mismatches(
    scene_markdown: Any,
    subject_index_text: Any,
) -> List[Dict[str, str]]:
    """Return CHAR:/ENV:/PROP: bracket names anywhere in scene markdown that are off-Index."""
    whitelist = parse_subject_index_whitelist(subject_index_text)
    if not whitelist.get("rows"):
        return []

    mismatches: List[Dict[str, str]] = []
    seen: Set[str] = set()
    for match in _TYPED_TOKEN_RE.finditer(str(scene_markdown or "")):
        bucket = _bucket_from_typed_prefix(match.group("prefix"))
        display = _normalize_display_name(match.group("body"))
        if not bucket or not display or _is_placeholder_name(display):
            continue
        if _name_in_whitelist(display, whitelist=whitelist, bucket=bucket):
            continue
        dedupe = f"{bucket}|{subject_compare_key(display)}"
        if dedupe in seen:
            continue
        seen.add(dedupe)
        mismatches.append(
            {
                "field": f"{str(match.group('prefix') or '').upper()}:[]",
                "bucket": bucket,
                "name": display,
            }
        )
    return mismatches


def collect_scene_table_name_mismatches(
    scene_markdown: Any,
    subject_index_text: Any,
) -> List[Dict[str, str]]:
    """Return mismatched names from table columns and all typed tokens in Beats/body."""
    whitelist = parse_subject_index_whitelist(subject_index_text)
    if not whitelist.get("rows"):
        return []

    text = str(scene_markdown or "")
    lines = [ln.strip() for ln in text.splitlines() if str(ln or "").strip()]
    mismatches: List[Dict[str, str]] = []
    seen: Set[str] = set()

    field_specs = [
        ("Environment Name", ["environmentname", "环境名称", "环境名", "环境锚点", "环境"], "environments"),
        ("Linked Characters", ["linkedcharacters", "关联角色", "角色", "characters"], "characters"),
        ("Key Props", ["keyprops", "关键道具", "道具", "props"], "props"),
    ]

    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.startswith("|"):
            i += 1
            continue
        headers = _split_table_cells(line)
        if len(headers) < 3:
            i += 1
            continue
        # Skip separator
        j = i + 1
        if j < len(lines) and re.fullmatch(r"[\|\s:\-]+", lines[j] or ""):
            j += 1

        col_map: Dict[str, int] = {}
        for field_name, aliases, _bucket in field_specs:
            col_map[field_name] = _find_col_idx(headers, aliases)

        if all(idx < 0 for idx in col_map.values()):
            i += 1
            continue

        while j < len(lines) and lines[j].startswith("|"):
            if re.fullmatch(r"[\|\s:\-]+", lines[j] or ""):
                j += 1
                continue
            cells = _split_table_cells(lines[j])
            for field_name, _aliases, bucket in field_specs:
                idx = col_map.get(field_name, -1)
                if idx < 0 or idx >= len(cells):
                    continue
                for token in _split_cell_tokens(cells[idx]):
                    if _name_in_whitelist(token, whitelist=whitelist, bucket=bucket):
                        continue
                    dedupe = f"{bucket}|{subject_compare_key(token)}"
                    if dedupe in seen:
                        continue
                    seen.add(dedupe)
                    mismatches.append(
                        {
                            "field": field_name,
                            "bucket": bucket,
                            "name": token,
                        }
                    )
            j += 1
        i = j

    for item in collect_typed_token_name_mismatches(text, subject_index_text):
        dedupe = f"{item.get('bucket')}|{subject_compare_key(item.get('name'))}"
        if dedupe in seen:
            continue
        seen.add(dedupe)
        mismatches.append(item)

    return mismatches


def collect_subjects_json_name_mismatches(
    subjects_json: Any,
    subject_index_text: Any,
) -> List[Dict[str, str]]:
    """Return asset items whose name/name_en are absent from Subject Index."""
    whitelist = parse_subject_index_whitelist(subject_index_text)
    if not whitelist.get("rows"):
        return []

    payload = subjects_json if isinstance(subjects_json, dict) else {}
    mismatches: List[Dict[str, str]] = []
    seen: Set[str] = set()

    for bucket in ("characters", "props", "environments", "covers", "posters"):
        items = payload.get(bucket) or []
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            name = _normalize_display_name(item.get("name"))
            name_en = _normalize_display_name(item.get("name_en"))
            candidates = [c for c in (name, name_en) if c and not _is_placeholder_name(c)]
            if not candidates:
                continue
            if any(_name_in_whitelist(c, whitelist=whitelist, bucket=bucket) for c in candidates):
                continue
            dedupe = f"{bucket}|{subject_compare_key(name)}|{subject_compare_key(name_en)}"
            if dedupe in seen:
                continue
            seen.add(dedupe)
            mismatches.append(
                {
                    "bucket": bucket,
                    "name": name,
                    "name_en": name_en,
                    "subject_no": str(item.get("subject_no") or "").strip(),
                }
            )
    return mismatches


def _extract_json_object(raw: Any) -> Optional[Dict[str, Any]]:
    text = str(raw or "").strip()
    if not text:
        return None
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text, flags=re.IGNORECASE).strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidate = text[start : end + 1]
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return None


async def _call_name_align_llm(
    *,
    llm_config: Dict[str, Any],
    system_prompt: str,
    user_prompt: str,
    context: str,
) -> Optional[Dict[str, Any]]:
    if not llm_config or not str((llm_config.get("api_key") or "")).strip():
        logger.warning("[%s] skip name align: missing llm config/api_key", context)
        return None
    try:
        response = await llm_service.chat_completion_with_fallback(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            llm_config,
        )
        raw = str((response or {}).get("content") or "").strip()
        parsed = _extract_json_object(raw)
        if not isinstance(parsed, dict):
            logger.warning("[%s] name align LLM returned non-JSON | preview=%s", context, raw[:300])
            return None
        return parsed
    except Exception as exc:
        logger.warning("[%s] name align LLM call failed: %s", context, exc, exc_info=exc)
        return None


def _canonical_target_from_whitelist(
    candidate: Any,
    *,
    whitelist: Dict[str, Any],
    bucket: Optional[str] = None,
) -> Tuple[str, str]:
    """Resolve a proposed target to exact Subject Index zh/en pair when possible."""
    key = subject_compare_key(candidate)
    if not key:
        return "", ""
    allowed_buckets: Optional[Set[str]] = None
    if bucket:
        if bucket in {"covers", "posters"}:
            allowed_buckets = {"covers", "posters"}
        else:
            allowed_buckets = {bucket}
    rows = whitelist.get("rows") or []
    for row in rows:
        row_bucket = str(row.get("bucket") or "")
        if allowed_buckets is not None and row_bucket not in allowed_buckets:
            continue
        for field in ("name", "name_en"):
            if subject_compare_key(row.get(field)) == key:
                return str(row.get("name") or "").strip(), str(row.get("name_en") or "").strip()
    display = (whitelist.get("all_keys") or {}).get(key) or ""
    return str(display or "").strip(), ""


def _apply_typed_token_replacements_in_text(
    text: str,
    ordered: List[Tuple[str, str]],
) -> str:
    """Replace off-Index names inside CHAR:/ENV:/PROP: brackets across full text."""
    out = str(text or "")
    if not out or not ordered:
        return out

    def _typed_sub(match: re.Match) -> str:
        prefix = match.group("prefix")
        body = match.group("body") or ""
        at = "@" if body.lstrip().startswith("@") else ""
        inner = body.lstrip("@").strip()
        for src, dst in ordered:
            if inner == src:
                return f"{prefix}:[{at}{dst}]"
        return match.group(0)

    return _TYPED_TOKEN_RE.sub(_typed_sub, out)


def _apply_plain_name_replacements_exact(cell: str, ordered: List[Tuple[str, str]]) -> str:
    """Replace unwrapped names by exact token equality only (no substring replace)."""
    out = str(cell or "")
    if not out or not ordered:
        return out
    # Protect typed tokens from plain remaps, then restore.
    holders: Dict[str, str] = {}

    def _hold(match: re.Match) -> str:
        key = f"__TYPED_TOKEN_{len(holders)}__"
        holders[key] = match.group(0)
        return key

    masked = _TYPED_TOKEN_RE.sub(_hold, out)
    # Split on common separators while keeping separators.
    parts = re.split(r"([,\n，;；|/]+)", masked)
    remap = {src: dst for src, dst in ordered}
    rebuilt: List[str] = []
    for part in parts:
        if not part or re.fullmatch(r"[,\n，;；|/]+", part or ""):
            rebuilt.append(part)
            continue
        display = _normalize_display_name(part)
        if display in remap:
            # Preserve surrounding whitespace from the original segment.
            leading = re.match(r"^\s*", part or "")
            trailing = re.search(r"\s*$", part or "")
            prefix = leading.group(0) if leading else ""
            suffix = trailing.group(0) if trailing else ""
            rebuilt.append(f"{prefix}{remap[display]}{suffix}")
        else:
            rebuilt.append(part)
    restored = "".join(rebuilt)
    for key, original in holders.items():
        restored = restored.replace(key, original)
    return restored


def apply_scene_table_name_replacements(
    scene_markdown: Any,
    replacements: List[Dict[str, str]],
) -> str:
    text = str(scene_markdown or "")
    if not text or not replacements:
        return text

    # Longest-first to avoid partial overlaps.
    ordered = sorted(
        [
            (str(r.get("from") or "").strip(), str(r.get("to") or "").strip())
            for r in replacements
            if str(r.get("from") or "").strip() and str(r.get("to") or "").strip()
            and str(r.get("from") or "").strip() != str(r.get("to") or "").strip()
        ],
        key=lambda pair: len(pair[0]),
        reverse=True,
    )
    if not ordered:
        return text

    def _replace_in_summary_cell(cell: str) -> str:
        # Typed tokens first, then exact unwrapped token remap only.
        out = _apply_typed_token_replacements_in_text(cell, ordered)
        return _apply_plain_name_replacements_exact(out, ordered)

    # First: remap every typed token in the whole document (covers {Beats}/{登场实体}).
    text = _apply_typed_token_replacements_in_text(text, ordered)

    lines = str(text).splitlines()
    out_lines: List[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped.startswith("|"):
            out_lines.append(line)
            i += 1
            continue

        headers = _split_table_cells(stripped)
        env_idx = _find_col_idx(headers, ["Environment Name", "环境名称", "环境名", "环境锚点", "环境"])
        char_idx = _find_col_idx(headers, ["Linked Characters", "关联角色", "角色", "characters"])
        prop_idx = _find_col_idx(headers, ["Key Props", "关键道具", "道具", "props"])
        out_lines.append(line)
        i += 1
        if i < len(lines) and re.fullmatch(r"[\|\s:\-]+", lines[i].strip() or ""):
            out_lines.append(lines[i])
            i += 1
        if env_idx < 0 and char_idx < 0 and prop_idx < 0:
            continue

        while i < len(lines) and lines[i].strip().startswith("|"):
            row_line = lines[i]
            row_stripped = row_line.strip()
            if re.fullmatch(r"[\|\s:\-]+", row_stripped or ""):
                out_lines.append(row_line)
                i += 1
                continue
            cells = _split_table_cells(row_stripped)
            for idx in (env_idx, char_idx, prop_idx):
                if idx >= 0 and idx < len(cells):
                    cells[idx] = _replace_in_summary_cell(cells[idx])
            rebuilt = "| " + " | ".join(cells) + " |"
            # Preserve original indentation if any.
            prefix = row_line[: len(row_line) - len(row_line.lstrip())]
            out_lines.append(prefix + rebuilt)
            i += 1

    return "\n".join(out_lines)


def apply_subjects_json_name_replacements(
    subjects_json: Any,
    replacements: List[Dict[str, str]],
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "characters": [],
        "props": [],
        "environments": [],
        "covers": [],
        "posters": [],
    }
    src = subjects_json if isinstance(subjects_json, dict) else {}
    for bucket in payload:
        items = src.get(bucket) or []
        payload[bucket] = [dict(item) for item in items if isinstance(item, dict)]

    if not replacements:
        return payload

    for rep in replacements:
        bucket = str(rep.get("bucket") or "").strip()
        if bucket not in payload:
            continue
        from_name = _normalize_display_name(rep.get("from_name") or rep.get("from"))
        from_name_en = _normalize_display_name(rep.get("from_name_en") or "")
        to_name = _normalize_display_name(rep.get("to_name") or rep.get("to"))
        to_name_en = _normalize_display_name(rep.get("to_name_en") or "")
        if not to_name and not to_name_en:
            continue
        from_name_key = subject_compare_key(from_name)
        from_name_en_key = subject_compare_key(from_name_en)
        for item in payload[bucket]:
            item_name = _normalize_display_name(item.get("name"))
            item_name_en = _normalize_display_name(item.get("name_en"))
            matched = False
            if from_name_key and subject_compare_key(item_name) == from_name_key:
                matched = True
            if from_name_en_key and subject_compare_key(item_name_en) == from_name_en_key:
                matched = True
            if not matched:
                continue
            if to_name:
                item["name"] = to_name
            if to_name_en:
                item["name_en"] = to_name_en
    return payload


async def align_scene_markdown_names_with_subject_index(
    *,
    scene_markdown: str,
    subject_index_text: str,
    llm_config: Dict[str, Any],
) -> Dict[str, Any]:
    """Check scene table names; if missing from Index, one LLM call to remap."""
    mismatches = collect_scene_table_name_mismatches(scene_markdown, subject_index_text)
    if not mismatches:
        return {
            "text": scene_markdown,
            "changed": False,
            "mismatch_count": 0,
            "applied_count": 0,
            "mismatches": [],
            "replacements": [],
        }

    whitelist = parse_subject_index_whitelist(subject_index_text)
    system_prompt = (
        "You are a strict Subject Index name aligner for film scene tables.\n"
        "Map incorrect entity names onto the authoritative Subject Index whitelist.\n"
        "Return ONE JSON object only. No markdown fences, no explanation.\n"
        "Schema:\n"
        '{"replacements":[{"field":"Environment Name|Linked Characters|Key Props|CHAR:[]|ENV:[]|PROP:[]",'
        '"from":"<exact incorrect name>","to":"<exact Subject Index subject_name_zh>"}]}\n'
        "Rules:\n"
        "- `to` MUST be character-identical to a Subject Index subject_name_zh (preferred) "
        "or subject_name_en when only EN exists.\n"
        "- Prefer the closest semantic match within the correct type "
        "(Environment Name/ENV:[]→environment, Linked Characters/CHAR:[]→character, "
        "Key Props/PROP:[]→prop).\n"
        "- Do not invent names absent from Subject Index.\n"
        "- If no confident Index match exists, omit that item "
        "(off-Index typed tokens will remain for upstream retry).\n"
        "- Remap only entity names; do not rewrite Beat prose wording beyond the name string."
    )
    user_prompt = (
        "# Authoritative Subject Index\n"
        f"{whitelist.get('compact_table') or subject_index_text}\n\n"
        "# Names not found in Subject Index\n"
        f"{json.dumps(mismatches, ensure_ascii=False, indent=2)}\n\n"
        "# Scene table excerpt (context only)\n"
        f"{str(scene_markdown or '')[:12000]}\n\n"
        "Return the replacements JSON now."
    )
    parsed = await _call_name_align_llm(
        llm_config=llm_config,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        context="scene_markdown_name_align",
    )
    raw_reps = list((parsed or {}).get("replacements") or []) if isinstance(parsed, dict) else []
    validated: List[Dict[str, str]] = []
    for rep in raw_reps:
        if not isinstance(rep, dict):
            continue
        src = _normalize_display_name(rep.get("from"))
        dst_raw = _normalize_display_name(rep.get("to"))
        field = str(rep.get("field") or "").strip() or "Unknown"
        field_key = field.upper().replace(" ", "")
        bucket = {
            "Environment Name": "environments",
            "Linked Characters": "characters",
            "Key Props": "props",
            "ENV:[]": "environments",
            "CHAR:[]": "characters",
            "PROP:[]": "props",
        }.get(field)
        if not bucket:
            if "ENV" in field_key:
                bucket = "environments"
            elif "CHAR" in field_key:
                bucket = "characters"
            elif "PROP" in field_key:
                bucket = "props"
            else:
                # Fall back to mismatch list bucket if present.
                for m in mismatches:
                    if _normalize_display_name(m.get("name")) == src:
                        bucket = str(m.get("bucket") or "") or None
                        break
        dst_zh, _dst_en = _canonical_target_from_whitelist(dst_raw, whitelist=whitelist, bucket=bucket)
        dst = dst_zh or dst_raw
        if not src or not dst or src == dst:
            continue
        if not _name_in_whitelist(dst, whitelist=whitelist, bucket=bucket):
            continue
        validated.append({"field": field, "from": src, "to": dst})

    aligned = apply_scene_table_name_replacements(scene_markdown, validated)
    remaining = collect_scene_table_name_mismatches(aligned, subject_index_text)
    logger.info(
        "[subject_index_name_align] scene_markdown mismatches=%s applied=%s remaining=%s",
        len(mismatches),
        len(validated),
        len(remaining),
    )
    return {
        "text": aligned,
        "changed": aligned != str(scene_markdown or ""),
        "mismatch_count": len(mismatches),
        "applied_count": len(validated),
        "mismatches": mismatches,
        "replacements": validated,
        "remaining_mismatches": remaining,
    }


async def align_subjects_json_names_with_subject_index(
    *,
    subjects_json: Dict[str, Any],
    subject_index_text: str,
    llm_config: Dict[str, Any],
) -> Dict[str, Any]:
    """Check asset JSON name/name_en; if missing from Index, one LLM call to remap."""
    mismatches = collect_subjects_json_name_mismatches(subjects_json, subject_index_text)
    if not mismatches:
        return {
            "subjects_json": subjects_json,
            "changed": False,
            "mismatch_count": 0,
            "applied_count": 0,
            "mismatches": [],
            "replacements": [],
        }

    whitelist = parse_subject_index_whitelist(subject_index_text)
    system_prompt = (
        "You are a strict Subject Index name aligner for asset design JSON.\n"
        "Map incorrect entity name/name_en onto the authoritative Subject Index whitelist.\n"
        "Return ONE JSON object only. No markdown fences, no explanation.\n"
        "Schema:\n"
        '{"replacements":[{"bucket":"characters|props|environments|covers|posters",'
        '"from_name":"...","from_name_en":"...","to_name":"<Index subject_name_zh>",'
        '"to_name_en":"<Index subject_name_en>"}]}\n'
        "Rules:\n"
        "- to_name / to_name_en MUST be character-identical to Subject Index values.\n"
        "- Keep bucket type consistent with Subject Index subject_type.\n"
        "- Prefer closest semantic match; do not invent names.\n"
        "- If no confident match, omit that item."
    )
    user_prompt = (
        "# Authoritative Subject Index\n"
        f"{whitelist.get('compact_table') or subject_index_text}\n\n"
        "# Asset names not found in Subject Index\n"
        f"{json.dumps(mismatches, ensure_ascii=False, indent=2)}\n\n"
        "Return the replacements JSON now."
    )
    parsed = await _call_name_align_llm(
        llm_config=llm_config,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        context="subjects_json_name_align",
    )
    raw_reps = list((parsed or {}).get("replacements") or []) if isinstance(parsed, dict) else []
    validated: List[Dict[str, str]] = []
    for rep in raw_reps:
        if not isinstance(rep, dict):
            continue
        bucket = str(rep.get("bucket") or "").strip()
        if bucket not in {"characters", "props", "environments", "covers", "posters"}:
            continue
        from_name = _normalize_display_name(rep.get("from_name") or rep.get("from"))
        from_name_en = _normalize_display_name(rep.get("from_name_en"))
        to_name_raw = _normalize_display_name(rep.get("to_name") or rep.get("to"))
        to_name_en_raw = _normalize_display_name(rep.get("to_name_en"))
        to_name, to_name_en = _canonical_target_from_whitelist(
            to_name_raw or to_name_en_raw,
            whitelist=whitelist,
            bucket=bucket,
        )
        if to_name_en_raw and not to_name_en:
            # If EN was provided and resolves, prefer canonical pair from that key.
            zh2, en2 = _canonical_target_from_whitelist(
                to_name_en_raw, whitelist=whitelist, bucket=bucket
            )
            if zh2 or en2:
                to_name, to_name_en = zh2 or to_name, en2 or to_name_en
        if not to_name and not to_name_en:
            continue
        if to_name and not _name_in_whitelist(to_name, whitelist=whitelist, bucket=bucket):
            continue
        if to_name_en and not _name_in_whitelist(to_name_en, whitelist=whitelist, bucket=bucket):
            # Allow EN-only validation failure when ZH is valid.
            if not to_name:
                continue
            to_name_en = ""
        if not from_name and not from_name_en:
            continue
        validated.append(
            {
                "bucket": bucket,
                "from_name": from_name,
                "from_name_en": from_name_en,
                "to_name": to_name,
                "to_name_en": to_name_en,
            }
        )

    aligned = apply_subjects_json_name_replacements(subjects_json, validated)
    remaining = collect_subjects_json_name_mismatches(aligned, subject_index_text)
    logger.info(
        "[subject_index_name_align] subjects_json mismatches=%s applied=%s remaining=%s",
        len(mismatches),
        len(validated),
        len(remaining),
    )
    return {
        "subjects_json": aligned,
        "changed": bool(validated),
        "mismatch_count": len(mismatches),
        "applied_count": len(validated),
        "mismatches": mismatches,
        "replacements": validated,
        "remaining_mismatches": remaining,
    }


def apply_text_name_replacements(text: Any, replacements: List[Dict[str, str]]) -> str:
    """Best-effort exact string replace of from→to names inside raw LLM text."""
    out = str(text or "")
    pairs: List[Tuple[str, str]] = []
    for rep in replacements or []:
        if not isinstance(rep, dict):
            continue
        for src_key, dst_key in (
            ("from", "to"),
            ("from_name", "to_name"),
            ("from_name_en", "to_name_en"),
        ):
            src = str(rep.get(src_key) or "").strip()
            dst = str(rep.get(dst_key) or "").strip()
            if src and dst and src != dst:
                pairs.append((src, dst))
    pairs = sorted(set(pairs), key=lambda p: len(p[0]), reverse=True)
    for src, dst in pairs:
        if src in out:
            out = out.replace(src, dst)
    return out
