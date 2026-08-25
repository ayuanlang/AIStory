"""Post-LLM name alignment for scene orchestration and asset design.

CHAR/PROP first check Subject Index. Names still missing after that (the delta),
especially derived ENV (`{N}度…`), are resolved against the asset library.
Subject Index no longer lists derived environments, so Environment Name / ENV:[]
must never be remapped onto a bare main-environment Index name.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.entity_token import subject_compare_key
from app.models.all_models import Entity
from app.services.llm_service import llm_service
from app.services.soft_delete import _active_entity_clause

logger = logging.getLogger("api_logger")

_TYPED_TOKEN_RE = re.compile(
    r"(?P<prefix>CHAR|PROP|ENV)\s*:\s*\[(?P<body>@?[^\]]+)\]",
    flags=re.IGNORECASE,
)
# Canonical writer uses Chinese comma ； readers must also accept slash/pipe/顿号/etc.
_SCENE_SUBJECT_SEPARATOR_RE = re.compile(r"[\n,，;；、/／|｜+＆&]+")
_SCENE_SUBJECT_SEPARATOR_KEEP_RE = re.compile(r"([\n,，;；、/／|｜+＆&]+)")
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
_DERIVED_ENV_NAME_RE = re.compile(r"^\d+\s*度")
_DERIVED_ENV_NAME_EN_RE = re.compile(r"^\d+\s*deg(?:rees?)?(?:\s|_)", flags=re.IGNORECASE)
_FORM_CONTINUITY_HEADER_ALIASES = {
    "form_continuity",
    "formcontinuity",
    "costume_prop_continuity",
    "costumecontinuity",
    "服化道连续性",
    "形态变化",
    "形态连续性",
}
_FORM_CONTINUITY_ATTR_RE = re.compile(
    r"(?:^|[；;])\s*form_continuity\s*[：:]\s*([^；;]+)",
    flags=re.IGNORECASE,
)
_EMPTY_CONTINUITY_VALUES = {
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


def _normalize_continuity_header_key(value: Any) -> str:
    return re.sub(r"[\s_.\-]+", "", str(value or "").strip().lower())


def _extract_form_continuity_from_attributes(attrs: Any) -> str:
    text = str(attrs or "").strip()
    if not text:
        return ""
    match = _FORM_CONTINUITY_ATTR_RE.search(text)
    if not match:
        return ""
    return str(match.group(1) or "").strip()


def _is_empty_form_continuity(value: Any) -> bool:
    text = re.sub(r"<br\s*/?>", " ", str(value or ""), flags=re.IGNORECASE).strip()
    compact = re.sub(r"[\s_*`'\"“”‘’]+", "", text).lower()
    return (not text) or compact in _EMPTY_CONTINUITY_VALUES


def _detect_subject_index_header_indexes(lines: List[str]) -> Dict[str, int]:
    """Return column indexes from the first Subject Index header row, if any."""
    indexes: Dict[str, int] = {}
    for raw_line in lines:
        stripped = str(raw_line or "").replace("\ufeff", "").strip()
        stripped = re.sub(r"^\s*>\s*", "", stripped).strip()
        if not stripped or not stripped.startswith("|"):
            continue
        if re.match(r"^\|?\s*S\d+\s*\|", stripped, flags=re.IGNORECASE):
            break
        parts = [p.strip() for p in stripped.strip("|").strip().split("|")]
        normalized = [_normalize_continuity_header_key(part) for part in parts]
        if "subjectno" not in normalized and "subject_no" not in {str(p or "").strip().lower() for p in parts}:
            if not any("subject" in key and "no" in key for key in normalized):
                continue
        for idx, key in enumerate(normalized):
            if key in {"subjectno", "subject_id", "id", "编号"} or (key.startswith("subject") and key.endswith("no")):
                indexes.setdefault("subject_no", idx)
            elif key in {"subjecttype", "type", "类型", "类别"}:
                indexes.setdefault("subject_type", idx)
            elif key in {"subjectnamezh", "subjectnameexact", "subjectname", "name", "名称", "名字"}:
                indexes.setdefault("name", idx)
            elif key in {"subjectnameen", "nameen", "englishname", "enname"}:
                indexes.setdefault("name_en", idx)
            elif key in _FORM_CONTINUITY_HEADER_ALIASES:
                indexes.setdefault("form_continuity", idx)
            elif key in {"entityattributes", "attributes", "实体属性"}:
                indexes.setdefault("entity_attributes", idx)
        if indexes:
            break
    return indexes


def parse_subject_index_whitelist(subject_index_text: Any) -> Dict[str, Any]:
    """Parse Subject Index into per-bucket name sets and canonical rows."""
    raw = str(subject_index_text or "").replace("\r\n", "\n")
    lines = raw.splitlines()
    header_indexes = _detect_subject_index_header_indexes(lines)
    by_bucket: Dict[str, Dict[str, str]] = {
        "characters": {},
        "props": {},
        "environments": {},
        "covers": {},
        "posters": {},
    }
    all_keys: Dict[str, str] = {}
    rows: List[Dict[str, str]] = []

    for line in lines:
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
        type_idx = header_indexes.get("subject_type", 1)
        name_idx = header_indexes.get("name", 2)
        name_en_idx = header_indexes.get("name_en", 3)
        if type_idx >= len(parts) or name_idx >= len(parts):
            continue
        bucket = _bucket_from_subject_type(parts[type_idx])
        if not bucket:
            continue
        name_zh = _normalize_display_name(parts[name_idx])
        name_en = _normalize_display_name(parts[name_en_idx]) if name_en_idx < len(parts) else ""
        if not name_zh and not name_en:
            continue
        continuity_idx = header_indexes.get("form_continuity")
        if continuity_idx is None and len(parts) >= 9:
            continuity_idx = 8
        form_continuity = ""
        if continuity_idx is not None and continuity_idx < len(parts):
            form_continuity = str(parts[continuity_idx] or "").strip()
        if _is_empty_form_continuity(form_continuity):
            attrs_idx = header_indexes.get("entity_attributes", 6 if len(parts) >= 7 else -1)
            if attrs_idx >= 0 and attrs_idx < len(parts):
                form_continuity = _extract_form_continuity_from_attributes(parts[attrs_idx])
        row = {
            "subject_no": str(parts[header_indexes.get("subject_no", 0)] or "").strip(),
            "bucket": bucket,
            "name": name_zh,
            "name_en": name_en,
            "form_continuity": form_continuity,
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


def _is_derived_environment_name(name: Any) -> bool:
    display = _normalize_display_name(name)
    return bool(_DERIVED_ENV_NAME_RE.match(display) or _DERIVED_ENV_NAME_EN_RE.match(display))


def _is_derived_to_main_environment_collapse(src: Any, dst: Any) -> bool:
    """True when a derived ENV ({N}度…) would be rewritten to a bare main ENV."""
    src_name = _normalize_display_name(src)
    dst_name = _normalize_display_name(dst)
    if not src_name or not dst_name or src_name == dst_name:
        return False
    return _is_derived_environment_name(src_name) and not _is_derived_environment_name(dst_name)


def _split_extra_derived_environment_names(value: Any) -> List[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item or "").strip() for item in value if str(item or "").strip()]
    text = str(value or "").strip()
    if not text:
        return []
    return [part.strip() for part in _SCENE_SUBJECT_SEPARATOR_RE.split(text) if part.strip()]


def _format_zh_en_name(name_zh: Any, name_en: Any = "") -> str:
    zh = _normalize_display_name(name_zh)
    en = _normalize_display_name(name_en)
    if zh and en and subject_compare_key(zh) != subject_compare_key(en):
        return f"{zh} / {en}"
    return zh or en


def _lookup_form_continuity(
    *,
    name_zh: Any,
    name_en: Any = "",
    form_continuity_by_name: Optional[Dict[str, str]] = None,
) -> str:
    mapping = form_continuity_by_name or {}
    if not mapping:
        return ""
    for candidate in (name_zh, name_en):
        display = _normalize_display_name(candidate)
        key = subject_compare_key(display)
        if key and mapping.get(key):
            return str(mapping.get(key) or "").strip()
    return ""


def parse_form_continuity_map(subject_index_text: Any) -> Dict[str, str]:
    """Map compare-key(name zh/en) → form_continuity for CHAR/PROP rows."""
    mapping: Dict[str, str] = {}
    whitelist = parse_subject_index_whitelist(subject_index_text)
    for row in list(whitelist.get("rows") or []):
        bucket = str(row.get("bucket") or "")
        if bucket not in {"characters", "props"}:
            continue
        continuity = str(row.get("form_continuity") or "").strip()
        if _is_empty_form_continuity(continuity):
            continuity = "无"
        for candidate in (row.get("name"), row.get("name_en")):
            key = subject_compare_key(candidate)
            if key:
                mapping[key] = continuity
    return mapping


def format_entity_rows_for_orchestration(
    rows: Iterable[Any],
    extra_derived_environment_names: Any = "",
    form_continuity_by_name: Optional[Dict[str, str]] = None,
) -> str:
    """Format CHAR/PROP (all) + derived ENV names as 中文 / 英文 pairs.

    When CHAR/PROP continuity is available, append a 【服化道连续性】 block
    paired with the Chinese (or English) asset name for Stage 2.2 injection.
    """
    characters: List[str] = []
    props: List[str] = []
    environments: List[str] = []
    continuities: List[str] = []
    seen_characters: Set[str] = set()
    seen_props: Set[str] = set()
    seen_environments: Set[str] = set()
    seen_continuity: Set[str] = set()
    has_real_continuity = False

    def _push(bucket: str, name_zh: Any, name_en: Any = "", form_continuity: Any = "") -> None:
        nonlocal has_real_continuity
        zh = _normalize_display_name(name_zh)
        en = _normalize_display_name(name_en)
        display = _format_zh_en_name(zh, en)
        if not display or _is_placeholder_name(zh or en):
            return
        if bucket == "environments" and not (
            _is_derived_environment_name(zh) or _is_derived_environment_name(en)
        ):
            return
        key = subject_compare_key(zh or en)
        if not key:
            return
        if bucket == "characters":
            if key in seen_characters:
                return
            seen_characters.add(key)
            characters.append(display)
        elif bucket == "props":
            if key in seen_props:
                return
            seen_props.add(key)
            props.append(display)
        elif bucket == "environments":
            if key in seen_environments:
                return
            seen_environments.add(key)
            environments.append(display)
            return
        else:
            return
        if bucket not in {"characters", "props"}:
            return
        continuity = str(form_continuity or "").strip()
        if _is_empty_form_continuity(continuity):
            continuity = _lookup_form_continuity(
                name_zh=zh,
                name_en=en,
                form_continuity_by_name=form_continuity_by_name,
            )
        if not _is_empty_form_continuity(continuity):
            has_real_continuity = True
        if _is_empty_form_continuity(continuity):
            continuity = "无"
        label = zh or en
        cont_key = subject_compare_key(label)
        if cont_key and cont_key not in seen_continuity:
            seen_continuity.add(cont_key)
            continuities.append(f"{label}｜{continuity}")

    for raw in rows or []:
        if isinstance(raw, dict):
            bucket = str(raw.get("bucket") or _bucket_from_subject_type(raw.get("type") or raw.get("subject_type")) or "")
            name_zh = raw.get("name") or raw.get("name_zh") or ""
            name_en = raw.get("name_en") or ""
            form_continuity = raw.get("form_continuity") or ""
        else:
            bucket = _bucket_from_subject_type(getattr(raw, "type", None))
            name_zh = getattr(raw, "name", None) or ""
            name_en = getattr(raw, "name_en", None) or ""
            form_continuity = getattr(raw, "form_continuity", None) or ""
            if not form_continuity:
                custom = getattr(raw, "custom_attributes", None)
                if isinstance(custom, dict):
                    form_continuity = custom.get("form_continuity") or ""
        _push(bucket, name_zh, name_en, form_continuity)
    for extra_name in _split_extra_derived_environment_names(extra_derived_environment_names):
        _push("environments", extra_name, "")

    lines: List[str] = []
    if characters:
        lines.append("CHAR: " + "，".join(characters))
    if props:
        lines.append("PROP: " + "，".join(props))
    if environments:
        lines.append("ENV: " + "，".join(environments))
    if has_real_continuity and continuities:
        lines.append("【服化道连续性】")
        lines.extend(continuities)
    return "\n".join(lines)


def collect_orchestration_entity_rows(
    db: Session,
    *,
    project_id: Any = None,
    episode_id: Any = None,
) -> List[Entity]:
    """Load asset-table entities for Stage 2.2 name injection."""
    if db is None or not project_id:
        return []
    filters = [
        Entity.project_id == int(project_id),
        _active_entity_clause(),
    ]
    if episode_id:
        filters.append(or_(Entity.episode_id == int(episode_id), Entity.episode_id.is_(None)))
    return (
        db.query(Entity)
        .filter(*filters)
        .order_by(Entity.id.asc())
        .all()
    )


def format_entity_table_names_for_orchestration(
    db: Session,
    *,
    project_id: Any = None,
    episode_id: Any = None,
    extra_derived_environment_names: Any = "",
    subject_index_text: Any = "",
) -> str:
    """Return CHAR/PROP + derived ENV 中文/英文 names from the asset table.

    Overlay CHAR/PROP `form_continuity` from persisted Subject Index when present.
    """
    return format_entity_rows_for_orchestration(
        collect_orchestration_entity_rows(db, project_id=project_id, episode_id=episode_id),
        extra_derived_environment_names=extra_derived_environment_names,
        form_continuity_by_name=parse_form_continuity_map(subject_index_text),
    )


def format_subject_index_names_for_orchestration(
    subject_index_text: Any,
    extra_derived_environment_names: Any = "",
) -> str:
    """Legacy Index-text formatter. Stage 2.2 now uses the asset table."""
    whitelist = parse_subject_index_whitelist(subject_index_text)
    rows = [
        {
            "bucket": str(row.get("bucket") or ""),
            "name": str(row.get("name") or ""),
            "name_en": str(row.get("name_en") or ""),
            "form_continuity": str(row.get("form_continuity") or ""),
        }
        for row in list(whitelist.get("rows") or [])
    ]
    return format_entity_rows_for_orchestration(
        rows,
        extra_derived_environment_names=extra_derived_environment_names,
        form_continuity_by_name=parse_form_continuity_map(subject_index_text),
    )


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


def parse_entity_rows_whitelist(
    rows: Iterable[Any],
    extra_derived_environment_names: Any = "",
    *,
    environments_derived_only: bool = True,
) -> Dict[str, Any]:
    """Parse asset-library rows into the same whitelist shape as Subject Index."""
    by_bucket: Dict[str, Dict[str, str]] = {
        "characters": {},
        "props": {},
        "environments": {},
        "covers": {},
        "posters": {},
    }
    all_keys: Dict[str, str] = {}
    parsed_rows: List[Dict[str, str]] = []

    def _add(bucket: str, name_zh: Any, name_en: Any = "", subject_no: str = "") -> None:
        zh = _normalize_display_name(name_zh)
        en = _normalize_display_name(name_en)
        if not zh and not en:
            return
        if _is_placeholder_name(zh or en):
            return
        if bucket == "environments" and environments_derived_only:
            if not (_is_derived_environment_name(zh) or _is_derived_environment_name(en)):
                return
        row = {
            "subject_no": str(subject_no or "").strip(),
            "bucket": bucket,
            "name": zh,
            "name_en": en,
        }
        parsed_rows.append(row)
        for candidate in (zh, en):
            key = subject_compare_key(candidate)
            if not key:
                continue
            by_bucket[bucket][key] = candidate
            all_keys[key] = candidate
            if bucket == "covers":
                by_bucket["posters"][key] = candidate

    for raw in rows or []:
        if isinstance(raw, dict):
            bucket = str(
                raw.get("bucket")
                or _bucket_from_subject_type(raw.get("type") or raw.get("subject_type"))
                or ""
            )
            name_zh = raw.get("name") or raw.get("name_zh") or ""
            name_en = raw.get("name_en") or ""
            subject_no = str(raw.get("subject_no") or raw.get("id") or "").strip()
        else:
            bucket = _bucket_from_subject_type(getattr(raw, "type", None))
            name_zh = getattr(raw, "name", None) or ""
            name_en = getattr(raw, "name_en", None) or ""
            subject_no = str(getattr(raw, "id", "") or "").strip()
        if bucket:
            _add(bucket, name_zh, name_en, subject_no)
    for extra_name in _split_extra_derived_environment_names(extra_derived_environment_names):
        _add("environments", extra_name, "")

    return {
        "rows": parsed_rows,
        "by_bucket": by_bucket,
        "all_keys": all_keys,
        "compact_table": _format_subject_index_compact(parsed_rows),
    }


def _merge_name_maps(*maps: Optional[Dict[str, str]]) -> Dict[str, str]:
    merged: Dict[str, str] = {}
    for item in maps:
        if item:
            merged.update(item)
    return merged


def build_scene_name_align_whitelist(
    subject_index_text: Any,
    asset_rows: Any = None,
    extra_derived_environment_names: Any = "",
) -> Dict[str, Any]:
    """CHAR/PROP = Index ∪ asset library; ENV = asset-library derived names only."""
    index = parse_subject_index_whitelist(subject_index_text)
    assets = parse_entity_rows_whitelist(
        asset_rows or [],
        extra_derived_environment_names,
        environments_derived_only=True,
    )
    index_by = index.get("by_bucket") or {}
    asset_by = assets.get("by_bucket") or {}
    by_bucket = {
        "characters": _merge_name_maps(index_by.get("characters"), asset_by.get("characters")),
        "props": _merge_name_maps(index_by.get("props"), asset_by.get("props")),
        "environments": dict(asset_by.get("environments") or {}),
        "covers": _merge_name_maps(index_by.get("covers"), asset_by.get("covers")),
        "posters": _merge_name_maps(index_by.get("posters"), asset_by.get("posters")),
    }
    rows = [row for row in list(index.get("rows") or []) if str(row.get("bucket") or "") != "environments"]
    rows.extend(list(assets.get("rows") or []))
    all_keys: Dict[str, str] = {}
    for bucket_map in by_bucket.values():
        all_keys.update(bucket_map)
    return {
        "rows": rows,
        "by_bucket": by_bucket,
        "all_keys": all_keys,
        "index": index,
        "assets": assets,
        "compact_index": index.get("compact_table") or "",
        "compact_assets": assets.get("compact_table") or "",
    }


def _whitelist_has_name_sources(whitelist: Dict[str, Any]) -> bool:
    if whitelist.get("rows"):
        return True
    index_rows = ((whitelist.get("index") or {}).get("rows") or []) if isinstance(whitelist.get("index"), dict) else []
    asset_rows = ((whitelist.get("assets") or {}).get("rows") or []) if isinstance(whitelist.get("assets"), dict) else []
    return bool(index_rows or asset_rows)


def split_scene_subject_field(cell_value: Any) -> List[str]:
    """Split Environment Name / Linked Characters / Key Props into display names.

    Typed tokens (`CHAR:[…]` / `ENV:[…]` / `PROP:[…]`) are atomic. Writers must use
    Chinese comma `，`, but readers also accept `/` `／` `|` `、` and other list marks.
    """
    text = str(cell_value or "").strip()
    if not text or _is_placeholder_name(text):
        return []

    tokens: List[str] = []
    seen: Set[str] = set()

    def _push(raw: Any) -> None:
        display = _normalize_display_name(raw)
        key = subject_compare_key(display)
        if display and key and key not in seen and not _is_placeholder_name(display):
            seen.add(key)
            tokens.append(display)

    for match in _TYPED_TOKEN_RE.finditer(text):
        _push(match.group("body"))

    remainder = _TYPED_TOKEN_RE.sub(" ", text)
    for part in _SCENE_SUBJECT_SEPARATOR_RE.split(remainder):
        _push(part)
    return tokens


def _split_cell_tokens(cell_value: Any) -> List[str]:
    return split_scene_subject_field(cell_value)


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
    asset_rows: Any = None,
    extra_derived_environment_names: Any = "",
    whitelist: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    """Return CHAR:/ENV:/PROP: names missing from Index (CHAR/PROP) or asset library (ENV)."""
    whitelist = whitelist or build_scene_name_align_whitelist(
        subject_index_text,
        asset_rows=asset_rows,
        extra_derived_environment_names=extra_derived_environment_names,
    )
    if not _whitelist_has_name_sources(whitelist):
        return []

    env_map = (whitelist.get("by_bucket") or {}).get("environments") or {}
    mismatches: List[Dict[str, str]] = []
    seen: Set[str] = set()
    for match in _TYPED_TOKEN_RE.finditer(str(scene_markdown or "")):
        bucket = _bucket_from_typed_prefix(match.group("prefix"))
        display = _normalize_display_name(match.group("body"))
        if not bucket or not display or _is_placeholder_name(display):
            continue
        # ENV 差额只对资产库。库里还没有衍生环境时，不要拿 Index 主环境去“对齐”。
        if bucket == "environments" and not env_map:
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
    asset_rows: Any = None,
    extra_derived_environment_names: Any = "",
) -> List[Dict[str, str]]:
    """Return mismatched names from table columns and all typed tokens in Beats/body."""
    whitelist = build_scene_name_align_whitelist(
        subject_index_text,
        asset_rows=asset_rows,
        extra_derived_environment_names=extra_derived_environment_names,
    )
    if not _whitelist_has_name_sources(whitelist):
        return []
    env_map = (whitelist.get("by_bucket") or {}).get("environments") or {}

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
                    if bucket == "environments" and not env_map:
                        continue
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

    for item in collect_typed_token_name_mismatches(
        text,
        subject_index_text,
        asset_rows=asset_rows,
        extra_derived_environment_names=extra_derived_environment_names,
        whitelist=whitelist,
    ):
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


def _llm_config_with_action(llm_config: Dict[str, Any], action_name: str) -> Dict[str, Any]:
    """Copy config so name-align logs do not reuse the parent 场景编排 action label."""
    cfg = dict(llm_config or {})
    inner = dict(cfg.get("config") or {}) if isinstance(cfg.get("config"), dict) else {}
    label = str(action_name or "").strip()
    if label:
        inner["__resolved_action"] = label
    cfg["config"] = inner
    return cfg


async def _call_name_align_llm(
    *,
    llm_config: Dict[str, Any],
    system_prompt: str,
    user_prompt: str,
    context: str,
    action_name: str = "",
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
            _llm_config_with_action(llm_config, action_name or "实体名对齐"),
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
    parts = _SCENE_SUBJECT_SEPARATOR_KEEP_RE.split(masked)
    remap = {src: dst for src, dst in ordered}
    rebuilt: List[str] = []
    for part in parts:
        if not part or _SCENE_SUBJECT_SEPARATOR_RE.fullmatch(part or ""):
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
            and not _is_derived_to_main_environment_collapse(r.get("from"), r.get("to"))
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
        if bucket == "environments" and (
            _is_derived_to_main_environment_collapse(from_name, to_name)
            or _is_derived_to_main_environment_collapse(from_name_en, to_name_en)
        ):
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
    action_name: str = "",
    asset_rows: Any = None,
    extra_derived_environment_names: Any = "",
    db: Any = None,
    project_id: Any = None,
    episode_id: Any = None,
) -> Dict[str, Any]:
    """Remap off-whitelist scene names. CHAR/PROP use Index∪资产库; ENV uses 资产库 only."""
    if asset_rows is None and db is not None and project_id:
        asset_rows = collect_orchestration_entity_rows(
            db,
            project_id=project_id,
            episode_id=episode_id,
        )
    whitelist = build_scene_name_align_whitelist(
        subject_index_text,
        asset_rows=asset_rows,
        extra_derived_environment_names=extra_derived_environment_names,
    )
    mismatches = collect_scene_table_name_mismatches(
        scene_markdown,
        subject_index_text,
        asset_rows=asset_rows,
        extra_derived_environment_names=extra_derived_environment_names,
    )
    if not mismatches:
        return {
            "text": scene_markdown,
            "changed": False,
            "mismatch_count": 0,
            "applied_count": 0,
            "mismatches": [],
            "replacements": [],
        }

    index_compact = whitelist.get("compact_index") or subject_index_text
    asset_compact = whitelist.get("compact_assets") or "(none)"
    system_prompt = (
        "You are a strict entity-name aligner for film scene tables.\n"
        "CHAR/PROP: map incorrect names onto Subject Index first; if absent there, "
        "use the asset-library CHAR/PROP names.\n"
        "ENV / Environment Name: Subject Index no longer lists derived environments. "
        "Map only onto asset-library derived environment names (`{N}度…` / `{N}度…_{状态}`).\n"
        "Return ONE JSON object only. No markdown fences, no explanation.\n"
        "Schema:\n"
        '{"replacements":[{"field":"Environment Name|Linked Characters|Key Props|CHAR:[]|ENV:[]|PROP:[]",'
        '"from":"<exact incorrect name>","to":"<exact whitelist name>"}]}\n'
        "Rules:\n"
        "- CHAR/PROP `to` MUST be character-identical to a Subject Index subject_name_zh "
        "(preferred) or an asset-library CHAR/PROP name.\n"
        "- ENV / Environment Name `to` MUST be character-identical to an asset-library "
        "derived environment name. Never use a bare main-environment name from Subject Index.\n"
        "- Prefer the closest semantic match within the correct type.\n"
        "- Do not invent names absent from the type-appropriate whitelist.\n"
        "- If no confident match exists, omit that item.\n"
        "- Remap only entity names; do not rewrite Beat prose wording beyond the name string."
    )
    user_prompt = (
        "# Subject Index (CHAR / PROP; main environments are NOT ENV targets)\n"
        f"{index_compact}\n\n"
        "# Asset library (authoritative for ENV; also CHAR/PROP delta)\n"
        f"{asset_compact}\n\n"
        "# Names not found in the type-appropriate whitelist\n"
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
        action_name=action_name or "实体名对齐 · 场景表",
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
        if bucket == "environments" and _is_derived_to_main_environment_collapse(src, dst):
            continue
        if not _name_in_whitelist(dst, whitelist=whitelist, bucket=bucket):
            continue
        validated.append({"field": field, "from": src, "to": dst})

    aligned = apply_scene_table_name_replacements(scene_markdown, validated)
    remaining = collect_scene_table_name_mismatches(
        aligned,
        subject_index_text,
        asset_rows=asset_rows,
        extra_derived_environment_names=extra_derived_environment_names,
    )
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
    action_name: str = "",
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
        "- Environment rows that already use a derived name (`{N}度…`) MUST stay derived. "
        "Never remap them to a bare main-environment name.\n"
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
        action_name=action_name or "实体名对齐 · 资产设计",
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
        if bucket == "environments" and (
            _is_derived_to_main_environment_collapse(from_name, to_name)
            or _is_derived_to_main_environment_collapse(from_name_en, to_name_en)
        ):
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
            if src and dst and src != dst and not _is_derived_to_main_environment_collapse(src, dst):
                pairs.append((src, dst))
    pairs = sorted(set(pairs), key=lambda p: len(p[0]), reverse=True)
    for src, dst in pairs:
        if src in out:
            out = out.replace(src, dst)
    return out
