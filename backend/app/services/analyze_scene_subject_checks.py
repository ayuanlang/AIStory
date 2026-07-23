# -*- coding: utf-8 -*-
"""Subject Index / subjects.json consistency helpers for analyze_scene."""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.core.entity_token import normalize_entity_token
from app.services.llm_markdown_sanitize import sanitize_subject_index_text

logger = logging.getLogger("api_logger")

def _normalize_subject_name(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"^(?:CHAR|PROP|ENV|VEFX|SFX)\s*:\s*", "", text, flags=re.IGNORECASE)
    text = text.strip()
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1].strip()
    text = text.lstrip("@").strip()
    text = re.sub(
        r"[A-Za-z0-9]+(?:[_-][A-Za-z0-9]+)+",
        lambda match: re.sub(r"[_-]+", " ", match.group(0)),
        text,
    )
    text = re.sub(r"\s+", " ", text)
    return text

def _normalize_subject_compare_key(value: Any) -> str:
    stable = _normalize_subject_name(value)
    if not stable:
        return ""
    # Insert spaces for camelCase/PascalCase boundaries before compact compare.
    stable = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", stable)
    stable = normalize_entity_token(stable)
    # Treat spaces/underscores/hyphens as equivalent for EN names.
    stable = re.sub(r"[\s_\-]+", "", stable)
    # Remove remaining punctuation/noise while keeping CJK/letters/digits.
    stable = re.sub(r"[^\w\u4e00-\u9fff]", "", stable)
    return stable

def _extract_subjects_from_analysis_text(text: str) -> List[str]:
    raw = str(text or "")
    if not raw:
        return []
    patterns = [
        re.compile(r"CHAR\s*:\s*\[@([^\]]+)\]", re.IGNORECASE),
        re.compile(r"PROP\s*:\s*\[([^\]]+)\]", re.IGNORECASE),
        re.compile(r"ENV\s*:\s*\[([^\]]+)\]", re.IGNORECASE),
        re.compile(r"VEFX\s*:\s*\[([^\]]+)\]", re.IGNORECASE),
        re.compile(r"SFX\s*:\s*\[([^\]]+)\]", re.IGNORECASE),
    ]
    found: List[str] = []
    seen = set()
    for pattern in patterns:
        for m in pattern.finditer(raw):
            normalized = _normalize_subject_name(m.group(1))
            key = _normalize_subject_compare_key(normalized)
            if normalized and key not in seen:
                seen.add(key)
                found.append(normalized)
    return found

def _extract_entities_from_json_candidates(text: str) -> Dict[str, List[Dict[str, Any]]]:
    payload: Dict[str, List[Dict[str, Any]]] = {
        "characters": [], "covers": [],
        "props": [],
        "environments": [],
        "posters": [],
    }
    raw = str(text or "")
    if not raw:
        return payload

    candidates: List[str] = []
    fence_re = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
    for m in fence_re.finditer(raw):
        candidate = str(m.group(1) or "").strip()
        if candidate:
            candidates.append(candidate)

    trimmed = raw.strip()
    if trimmed.startswith("{") and trimmed.endswith("}"):
        candidates.append(trimmed)

    seen_candidate = set()
    for candidate in candidates:
        key = candidate[:2000]
        if key in seen_candidate:
            continue
        seen_candidate.add(key)
        try:
            obj = json.loads(candidate)
        except Exception:
            continue
        parsed_objects: List[Dict[str, Any]] = []
        if isinstance(obj, list):
            grouped = {"characters": [], "props": [], "environments": [], "covers": [], "posters": []}
            for item in obj:
                if not isinstance(item, dict):
                    continue

                has_bucket_keys = any(k in item for k in ("characters", "props", "environments", "covers", "posters"))
                wrapped_payload = item.get("entities") or item.get("subjects") or item.get("payload")
                if has_bucket_keys:
                    parsed_objects.append(item)
                    continue
                if isinstance(wrapped_payload, dict):
                    parsed_objects.append(wrapped_payload)
                    continue

                t = str(item.get("type") or item.get("subject_type") or item.get("entity_type") or "").strip().lower()
                if t in {"character", "characters", "char", "role", "roles", "人物", "角色"}: grouped["characters"].append(item)
                elif t in {"prop", "props", "item", "items", "道具", "物件"}: grouped["props"].append(item)
                elif t in {"environment", "environments", "env", "scene", "场景", "环境"}: grouped["environments"].append(item)
                elif t in {"poster", "posters", "cover", "covers", "海报", "封面"}: grouped["covers"].append(item)

            if any(len(grouped.get(k) or []) > 0 for k in ("characters", "props", "environments", "covers", "posters")):
                parsed_objects.append(grouped)
        elif isinstance(obj, dict):
            parsed_objects.append(obj)

        for parsed_obj in parsed_objects:
            if not isinstance(parsed_obj, dict):
                continue
            for section in ("characters", "props", "environments", "covers", "posters"):
                items = parsed_obj.get(section)
                if section == "covers" and not items and "posters" in parsed_obj:
                    items = parsed_obj.get("posters")
                if isinstance(items, list):
                    payload[section].extend([x for x in items if isinstance(x, dict)])

    return payload

def _detect_subject_consistency_warnings(text: str, parsed_entities: Dict[str, Any] = None) -> Dict[str, Any]:
    markdown_subjects = _extract_subjects_from_analysis_text(text)
    entities_payload = parsed_entities if parsed_entities is not None else _extract_entities_from_json_candidates(text)

    json_subjects: List[str] = []
    for section in ("characters", "props", "environments", "covers", "posters"):
        for item in entities_payload.get(section, []):
            for raw_name in (item.get("name"), item.get("name_en")):
                normalized = _normalize_subject_name(raw_name or "")
                if normalized:
                    json_subjects.append(normalized)

    markdown_set = {}
    for s in markdown_subjects:
        key = _normalize_subject_compare_key(s)
        if key and key not in markdown_set:
            markdown_set[key] = s

    json_set = {}
    for s in json_subjects:
        key = _normalize_subject_compare_key(s)
        if key and key not in json_set:
            json_set[key] = s

    missing = [display for key, display in markdown_set.items() if key not in json_set]

    warning_codes: List[str] = []
    warnings: List[str] = []
    if len(markdown_set) > 0 and len(json_set) == 0:
        warning_codes.append("ANALYSIS_SUBJECTS_UNVERIFIED")
        warnings.append("Subject consistency warning: could not be fully verified from JSON sections; continue loading and review manually.")
    elif len(missing) > 0:
        warning_codes.append("ANALYSIS_SUBJECTS_INCOMPLETE")
        warnings.append(
            "Subject consistency warning: some subjects found in scene text are missing in entity JSON. "
            + f"Missing: {', '.join(missing[:20])}"
        )

    return {
        "markdown_subject_count": len(markdown_set),
        "json_subject_count": len(json_set),
        "missing_subjects": missing,
        "warning_codes": warning_codes,
        "warnings": warnings,
    }

def _detect_prompt_template_syntax_warnings(text: str, syntax_rules: Dict[str, Any]) -> Dict[str, Any]:
    entities_payload = _extract_entities_from_json_candidates(text)
    warning_codes: List[str] = []
    warnings: List[str] = []
    mismatches: List[Dict[str, Any]] = []

    def _missing_text_field(value: Any) -> bool:
        return not str(value or "").strip()

    def _missing_present_field(field_name: str, item: Dict[str, Any]) -> bool:
        if field_name not in item:
            return True
        value = item.get(field_name)
        if field_name == "visual_dependencies":
            return not isinstance(value, list)
        if field_name == "dependency_strategy":
            return not isinstance(value, dict)
        return value is None

    section_aliases = {
        "characters": ["characters"],
        "props": ["props"],
        "environments": ["environments"],
        "posters": ["posters", "covers"],
    }

    for section, payload_keys in section_aliases.items():
        rules = syntax_rules.get(section) if isinstance(syntax_rules, dict) else None
        if not isinstance(rules, dict):
            continue
        required_text_fields = [str(x).strip() for x in (rules.get("required_text_fields") or []) if str(x).strip()]
        required_present_fields = [str(x).strip() for x in (rules.get("required_present_fields") or []) if str(x).strip()]
        dependency_strategy_required_keys = [str(x).strip() for x in (rules.get("dependency_strategy_required_keys") or []) if str(x).strip()]

        items: Any = []
        for payload_key in payload_keys:
            candidate_items = entities_payload.get(payload_key)
            if isinstance(candidate_items, list):
                items = candidate_items
                break
        if not isinstance(items, list):
            continue

        for item in items:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("name_en") or "").strip() or "(unnamed)"
            missing_text_fields = [field for field in required_text_fields if _missing_text_field(item.get(field))]
            missing_present_fields = [field for field in required_present_fields if _missing_present_field(field, item)]

            missing_dependency_strategy_keys: List[str] = []
            dependency_strategy = item.get("dependency_strategy")
            if isinstance(dependency_strategy, dict):
                missing_dependency_strategy_keys = [
                    field for field in dependency_strategy_required_keys
                    if _missing_text_field(dependency_strategy.get(field))
                ]

            if missing_text_fields or missing_present_fields or missing_dependency_strategy_keys:
                mismatches.append({
                    "section": section,
                    "name": name,
                    "missing_text_fields": missing_text_fields,
                    "missing_present_fields": missing_present_fields,
                    "missing_dependency_strategy_keys": missing_dependency_strategy_keys,
                })

    if mismatches:
        warning_codes.append("ANALYSIS_PROMPT_TEMPLATE_MISMATCH")
        preview = mismatches[:8]
        summary = "; ".join([
            f"{it.get('section')}:{it.get('name')}"
            for it in preview
        ])
        warnings.append(
            "Entity design schema warning: some assets are missing required fields or have empty prompt/schema values. "
            f"Examples: {summary}"
        )

    return {
        "checked_sections": ["characters", "props", "environments", "covers", "posters"],
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "warning_codes": warning_codes,
        "warnings": warnings,
    }

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

def _extract_expected_subjects_from_subject_index(text: str) -> Dict[str, Any]:
    expected: Dict[str, Dict[str, str]] = {
        "characters": {},
        "props": {},
        "environments": {},
        "covers": {},
        "posters": {},
    }
    raw = sanitize_subject_index_text(text)
    if not raw:
        return {"expected": expected, "total": 0}

    # Supports rows like:
    # S001 | prop | 中文名 | English Name | ...
    for line in raw.splitlines():
        stripped = str(line or "").replace("\ufeff", "").strip()
        stripped = re.sub(r"^\s*>\s*", "", stripped)
        stripped = re.sub(r"^\s*[-*+]\s+", "", stripped).strip()
        if not stripped:
            continue
        if not re.match(r"^\|?\s*S\d+\s*\|", stripped, flags=re.IGNORECASE):
            continue
        normalized_line = stripped.strip("|").strip()
        parts = [p.strip() for p in normalized_line.split("|")]
        if len(parts) < 4:
            continue

        bucket = _bucket_from_subject_type(parts[1])
        if not bucket:
            continue

        display_name = _normalize_subject_name(parts[2])
        name_en = _normalize_subject_name(parts[3]) if len(parts) > 3 else ""

        for candidate in (display_name, name_en):
            key = _normalize_subject_compare_key(candidate)
            if key and key not in expected[bucket]:
                expected[bucket][key] = candidate

    total = sum(len(v) for v in expected.values())
    return {"expected": expected, "total": total}

def _extract_subject_index_records(source_text: str) -> List[Dict[str, str]]:
    records: List[Dict[str, str]] = []
    raw = sanitize_subject_index_text(source_text)
    if not raw:
        return records

    for line in raw.splitlines():
        stripped = str(line or "").replace("\ufeff", "").strip()
        stripped = re.sub(r"^\s*>\s*", "", stripped)
        stripped = re.sub(r"^\s*[-*+]\s+", "", stripped).strip()
        if not stripped:
            continue
        if not re.match(r"^\|?\s*S\d+\s*\|", stripped, flags=re.IGNORECASE):
            continue

        normalized_line = stripped.strip("|").strip()
        parts = [p.strip() for p in normalized_line.split("|")]
        if len(parts) < 4:
            continue

        bucket = _bucket_from_subject_type(parts[1])
        if not bucket:
            continue

        subject_no = str(parts[0] or "").strip()
        name = str(parts[2] or "").strip()
        name_en = str(parts[3] or "").strip()
        base_entity = ""
        dependency_reference = ""
        if len(parts) >= 8:
            base_entity = str(parts[4] or "").strip()
            dependency_reference = str(parts[5] or "").strip()
        elif len(parts) >= 5:
            dependency_reference = str(parts[4] or "").strip()
        if not subject_no or (not name and not name_en):
            continue

        records.append({
            "subject_no": subject_no,
            "bucket": bucket,
            "name": name,
            "name_en": name_en,
            "base_entity": base_entity,
            "dependency_reference": dependency_reference,
        })

    return records

def _build_subject_placeholder(record: Dict[str, str]) -> Dict[str, Any]:
    bucket = str(record.get("bucket") or "")
    subject_no = str(record.get("subject_no") or "").strip()
    name = str(record.get("name") or "").strip()
    name_en = str(record.get("name_en") or "").strip()
    base_entity = str(record.get("base_entity") or "").strip()
    dependency_reference = str(record.get("dependency_reference") or "").strip()
    is_derived = bool(
        base_entity
        and base_entity.lower() not in {"none", "null", "n/a", "na", "-", "无"}
    )
    resolved_base_name_en = dependency_reference if is_derived else name_en

    base_obj: Dict[str, Any] = {
        "subject_no": subject_no,
        "name": name,
        "name_en": name_en,
        "base_name_en": resolved_base_name_en,
        "description_cn": "",
        "visual_dependencies": [],
        "dependency_strategy": {
            "type": "Type A" if is_derived else "Original",
            "logic": (
                f"Recovered from Subject Index; derived from base entity {base_entity}."
                if is_derived
                else "Recovered from Subject Index because the LLM output missed this entity."
            ),
        },
    }

    if bucket == "characters":
        base_obj.update({
            "gender": "",
            "role": "",
            "archetype": "",
            "appearance_cn": "",
            "clothing": "",
            "action_characteristics": "",
            "generation_prompt_cn": "",
            "generation_prompt_en": "",
            "negative_prompt_en": "",
            "anchor_description": "",
        })
    elif bucket == "props":
        base_obj.update({
            "type": "",
            "generation_prompt_cn": "",
            "generation_prompt_en": "",
            "negative_prompt_en": "",
            "anchor_description": "",
        })
    elif bucket in {"environments", "covers", "posters"}:
        base_obj.update({
            "atmosphere": "",
            "visual_params": "",
            "generation_prompt_cn": "",
            "generation_prompt_en": "",
            "negative_prompt_en": "",
            "anchor_description": "",
        })

    return base_obj

def _reconcile_subjects_json_with_subject_index(source_text: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized: Dict[str, List[Dict[str, Any]]] = {
        "characters": [x for x in (payload.get("characters") or []) if isinstance(x, dict)],
        "props": [x for x in (payload.get("props") or []) if isinstance(x, dict)],
        "environments": [x for x in (payload.get("environments") or []) if isinstance(x, dict)],
        "covers": [x for x in ((payload.get("covers") or payload.get("posters") or [])) if isinstance(x, dict)],
    }

    records = _extract_subject_index_records(source_text)
    if not records:
        merged_covers = normalized.get("covers") or []
        if merged_covers:
            normalized["posters"] = list(merged_covers)
        return {
            "subjects_json": normalized,
            "meta": {
                "expected_total": 0,
                "corrected_bucket_moves": 0,
                "filled_missing": 0,
                "name_aligned": 0,
                "remaining_missing": 0,
                "missing_samples": [],
                "notes": ["subject_index_not_found_or_unparseable"],
            },
            "warning_codes": [],
            "warnings": [],
        }

    item_refs: List[Dict[str, Any]] = []
    for bucket in ("characters", "props", "environments", "covers", "posters"):
        for idx, item in enumerate(normalized.get(bucket) or []):
            item_refs.append({"bucket": bucket, "index": idx, "item": item})

    used_item_indexes: set = set()
    corrected_bucket_moves = 0
    filled_missing = 0
    name_aligned = 0
    remaining_missing = 0
    missing_samples: List[str] = []

    reconciled: Dict[str, List[Dict[str, Any]]] = {
        "characters": [],
        "props": [],
        "environments": [],
        "covers": [],
        "posters": [],
    }

    def _find_match(record: Dict[str, str]) -> Optional[Dict[str, Any]]:
        rec_no = str(record.get("subject_no") or "").strip().lower()
        rec_name_key = _normalize_subject_compare_key(record.get("name") or "")
        rec_name_en_key = _normalize_subject_compare_key(record.get("name_en") or "")
        expected_keys = {k for k in (rec_name_key, rec_name_en_key) if k}

        # Highest priority: subject_no exact match.
        for i, ref in enumerate(item_refs):
            if i in used_item_indexes:
                continue
            item = ref.get("item") or {}
            item_no = str(item.get("subject_no") or "").strip().lower()
            if rec_no and item_no and item_no == rec_no:
                return {"ref_idx": i, "ref": ref, "matched_by": "subject_no"}

        # Fallback: name/name_en normalized match.
        if expected_keys:
            for i, ref in enumerate(item_refs):
                if i in used_item_indexes:
                    continue
                item = ref.get("item") or {}
                item_keys = {
                    _normalize_subject_compare_key(item.get("name") or ""),
                    _normalize_subject_compare_key(item.get("name_en") or ""),
                }
                item_keys = {k for k in item_keys if k}
                if item_keys & expected_keys:
                    return {"ref_idx": i, "ref": ref, "matched_by": "name"}
        return None

    for record in records:
        target_bucket = str(record.get("bucket") or "")
        if target_bucket not in reconciled:
            continue

        match = _find_match(record)
        if not match:
            sample_name = str(record.get("name") or record.get("name_en") or record.get("subject_no") or "").strip()
            if sample_name and len(missing_samples) < 12:
                missing_samples.append(sample_name)
            continue

        ref_idx = int(match.get("ref_idx"))
        used_item_indexes.add(ref_idx)

        ref = match.get("ref") or {}
        source_bucket = str(ref.get("bucket") or "")
        item = dict(ref.get("item") or {})

        if source_bucket != target_bucket:
            corrected_bucket_moves += 1

        expected_subject_no = str(record.get("subject_no") or "").strip()
        expected_name = str(record.get("name") or "").strip()
        expected_name_en = str(record.get("name_en") or "").strip()

        if expected_subject_no and str(item.get("subject_no") or "").strip() != expected_subject_no:
            item["subject_no"] = expected_subject_no
            name_aligned += 1

        if expected_name and str(item.get("name") or "").strip() != expected_name:
            item["name"] = expected_name
            name_aligned += 1

        if expected_name_en and str(item.get("name_en") or "").strip() != expected_name_en:
            item["name_en"] = expected_name_en
            name_aligned += 1

        expected_base_entity = str(record.get("base_entity") or "").strip()
        expected_dependency = str(record.get("dependency_reference") or "").strip()
        is_derived = bool(
            expected_base_entity
            and expected_base_entity.lower() not in {"none", "null", "n/a", "na", "-", "无"}
        )
        if is_derived and expected_dependency and not str(item.get("base_name_en") or "").strip():
            item["base_name_en"] = expected_dependency
        elif expected_name_en and not str(item.get("base_name_en") or "").strip():
            item["base_name_en"] = expected_name_en

        reconciled[target_bucket].append(item)

    # Keep unmatched generated items so data is not silently dropped.
    for i, ref in enumerate(item_refs):
        if i in used_item_indexes:
            continue
        bucket = str(ref.get("bucket") or "")
        item = ref.get("item")
        if bucket in reconciled and isinstance(item, dict):
            reconciled[bucket].append(item)

    expected_total = len(records)
    reconciled_subject_keys = _collect_subject_keys_by_bucket(reconciled)
    expected_by_bucket: Dict[str, set] = {"characters": set(), "props": set(), "environments": set(), "covers": set(), "posters": set()}
    subject_index_identity_keys: set = set()
    for record in records:
        bucket = str(record.get("bucket") or "")
        if bucket not in expected_by_bucket:
            continue
        for candidate in (record.get("name"), record.get("name_en")):
            key = _normalize_subject_compare_key(candidate)
            if key:
                expected_by_bucket[bucket].add(key)
                subject_index_identity_keys.add(key)

    missing_base_references: List[str] = []
    for record in records:
        dependency_reference = str(record.get("dependency_reference") or "").strip()
        base_entity = str(record.get("base_entity") or "").strip()
        derived_name = str(record.get("name") or record.get("name_en") or record.get("subject_no") or "").strip() or "(unnamed)"
        if dependency_reference and dependency_reference.lower() not in {"none", "null", "n/a", "na", "-", "无"}:
            dep_key = _normalize_subject_compare_key(dependency_reference)
            if dep_key and dep_key not in subject_index_identity_keys:
                missing_base_references.append(f"{derived_name} -> {dependency_reference}")
        if base_entity and base_entity.lower() not in {"none", "null", "n/a", "na", "-", "无"}:
            base_key = _normalize_subject_compare_key(base_entity)
            if base_key and base_key not in subject_index_identity_keys:
                missing_base_references.append(f"{derived_name} -> base_entity:{base_entity}")

    for bucket in ("characters", "props", "environments", "covers", "posters"):
        actual_keys = set((reconciled_subject_keys.get(bucket) or {}).keys())
        for key in expected_by_bucket.get(bucket) or set():
            if key not in actual_keys:
                remaining_missing += 1

    warning_codes: List[str] = []
    warnings: List[str] = []
    if corrected_bucket_moves > 0:
        warning_codes.append("ANALYSIS_SUBJECT_INDEX_BUCKET_CORRECTED")
        warnings.append(
            f"Subject Index alignment applied: moved {corrected_bucket_moves} entities to their canonical buckets."
        )
    if filled_missing > 0:
        warning_codes.append("ANALYSIS_SUBJECT_INDEX_MISSING_FILLED")
        msg = f"Subject Index alignment applied: auto-filled {filled_missing} missing entities from Subject Index"
        if missing_samples:
            msg += f" (examples: {', '.join(missing_samples[:8])})"
        warnings.append(msg + ".")
    if name_aligned > 0:
        warning_codes.append("ANALYSIS_SUBJECT_INDEX_NAME_ALIGNED")
        warnings.append(
            f"Subject Index alignment applied: normalized {name_aligned} subject_no/name/name_en fields to Subject Index values."
        )
    if remaining_missing > 0:
        warning_codes.append("ANALYSIS_SUBJECT_INDEX_REMAINING_GAP")
        warnings.append(
            f"Subject Index alignment warning: {remaining_missing} expected entities are still missing after reconciliation."
        )
    if missing_base_references:
        warning_codes.append("ANALYSIS_SUBJECT_INDEX_BASE_MISSING")
        warnings.append(
            "Subject Index base-version warning: some derived entities reference a base name that does not exist in Subject Index. "
            + f"Examples: {', '.join(missing_base_references[:8])}"
        )

    cover_poster_items: List[Dict[str, Any]] = []
    cover_poster_seen: set = set()
    for item in (reconciled.get("covers") or []) + (reconciled.get("posters") or []):
        if not isinstance(item, dict):
            continue
        item_key = "|".join([
            str(item.get("subject_no") or "").strip().lower(),
            str(item.get("name") or "").strip().lower(),
            str(item.get("name_en") or "").strip().lower(),
        ])
        if item_key in cover_poster_seen:
            continue
        cover_poster_seen.add(item_key)
        cover_poster_items.append(item)
    if cover_poster_items:
        reconciled["covers"] = cover_poster_items
        reconciled["posters"] = cover_poster_items

    return {
        "subjects_json": reconciled,
        "meta": {
            "expected_total": expected_total,
            "corrected_bucket_moves": corrected_bucket_moves,
            "filled_missing": filled_missing,
            "name_aligned": name_aligned,
            "remaining_missing": remaining_missing,
            "missing_samples": missing_samples,
            "missing_base_references": missing_base_references[:20],
            "notes": [
                "subject_index_is_source_of_truth_for_bucket_routing",
                "subject_index_is_source_of_truth_for_subject_identity",
            ],
        },
        "warning_codes": warning_codes,
        "warnings": warnings,
    }

def _detect_subject_index_coverage_warnings(source_text: str, subjects_payload: Dict[str, Any]) -> Dict[str, Any]:
    expected_meta = _extract_expected_subjects_from_subject_index(source_text)
    expected = expected_meta.get("expected") or {}
    expected_total = int(expected_meta.get("total") or 0)

    if expected_total <= 0:
        return {
            "expected_total": 0,
            "expected_by_bucket": {
                "characters": 0,
                "props": 0,
                "environments": 0,
                "covers": 0,
                "posters": 0,
            },
            "missing_total": 0,
            "missing_by_bucket": {
                "characters": [], "props": [], "environments": [], "covers": [], "posters": [], "posters": []
            },
            "warning_codes": [],
            "warnings": [],
        }

    generated_keys: Dict[str, set] = {
        "characters": set(),
        "props": set(),
        "environments": set(),
        "covers": set(),
    }

    for bucket in ("characters", "props", "environments", "covers", "posters"):
        for item in (subjects_payload.get(bucket) or []):
            if not isinstance(item, dict):
                continue
            for raw_name in (item.get("name"), item.get("name_en")):
                key = _normalize_subject_compare_key(raw_name)
                if key:
                    generated_keys[bucket].add(key)

    missing_by_bucket: Dict[str, List[str]] = {
        "characters": [],
        "props": [],
        "environments": [],
        "covers": [],
        "posters": [],
    }
    for bucket in ("characters", "props", "environments", "covers", "posters"):
        expected_bucket = expected.get(bucket) or {}
        for key, display in expected_bucket.items():
            if key not in generated_keys[bucket]:
                missing_by_bucket[bucket].append(display)

    missing_total = sum(len(v) for v in missing_by_bucket.values())
    warning_codes: List[str] = []
    warnings: List[str] = []

    if missing_total > 0:
        warning_codes.append("ANALYSIS_SUBJECT_INDEX_COVERAGE_INCOMPLETE")
        parts: List[str] = []
        if missing_by_bucket["characters"]:
            parts.append(f"characters缺失{len(missing_by_bucket['characters'])}项")
        if missing_by_bucket["props"]:
            parts.append(f"props缺失{len(missing_by_bucket['props'])}项")
        if missing_by_bucket["environments"]:
            parts.append(f"environments缺失{len(missing_by_bucket['environments'])}项")
        if missing_by_bucket["covers"] or missing_by_bucket["posters"]:
            parts.append(f"posters/covers缺失{len(missing_by_bucket['covers']) + len(missing_by_bucket['posters'])}项")

        preview_items = (
            missing_by_bucket["props"][:5]
            + missing_by_bucket["characters"][:5]
            + missing_by_bucket["environments"][:5]
            + missing_by_bucket["covers"][:5]
            + missing_by_bucket["posters"][:5]
        )
        preview = ", ".join([str(x or "").strip() for x in preview_items if str(x or "").strip()])
        warnings.append(
            "Subject Index coverage warning: "
            + "；".join(parts)
            + (f"。示例缺失: {preview}" if preview else "")
        )

    return {
        "expected_total": expected_total,
        "expected_by_bucket": {
            "characters": len(expected.get("characters") or {}),
            "props": len(expected.get("props") or {}),
            "environments": len(expected.get("environments") or {}),
            "covers": len(expected.get("covers") or {}),
            "posters": len(expected.get("posters") or {}),
        },
        "missing_total": missing_total,
        "missing_by_bucket": missing_by_bucket,
        "warning_codes": warning_codes,
        "warnings": warnings,
    }

def _collect_subject_keys_by_bucket(payload: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    collected: Dict[str, Dict[str, str]] = {
        "characters": {},
        "props": {},
        "environments": {},
        "covers": {},
        "posters": {},
    }
    for bucket in ("characters", "props", "environments", "covers", "posters"):
        for item in (payload.get(bucket) or []):
            if not isinstance(item, dict):
                continue
            for raw_name in (item.get("name"), item.get("name_en")):
                display = _normalize_subject_name(raw_name)
                key = _normalize_subject_compare_key(display)
                if key and key not in collected[bucket]:
                    collected[bucket][key] = display or str(raw_name or "").strip()
    return collected

def _detect_subjects_json_extraction_gap(raw_text: str, selected_payload: Dict[str, Any]) -> Dict[str, Any]:
    # Aggregate all JSON candidates in raw output; this helps diagnose parser-selection loss.
    aggregated_payload = _extract_entities_from_json_candidates(raw_text)
    selected_keys = _collect_subject_keys_by_bucket(selected_payload)
    aggregated_keys = _collect_subject_keys_by_bucket(aggregated_payload)

    missing_in_selected_by_bucket: Dict[str, List[str]] = {
        "characters": [],
        "props": [],
        "environments": [],
        "covers": [],
        "posters": [],
    }
    for bucket in ("characters", "props", "environments", "covers", "posters"):
        for key, display in (aggregated_keys.get(bucket) or {}).items():
            if key not in (selected_keys.get(bucket) or {}):
                missing_in_selected_by_bucket[bucket].append(display)

    missing_total = sum(len(v) for v in missing_in_selected_by_bucket.values())
    warnings: List[str] = []
    warning_codes: List[str] = []
    diagnosis: List[str] = []

    if missing_total > 0:
        warning_codes.append("ANALYSIS_SUBJECTS_JSON_EXTRACT_PARTIAL")
        warning_text_parts: List[str] = []
        for bucket in ("characters", "props", "environments", "covers", "posters"):
            count = len(missing_in_selected_by_bucket.get(bucket) or [])
            if count > 0:
                warning_text_parts.append(f"{bucket}差异{count}项")
        sample = (
            (missing_in_selected_by_bucket.get("props") or [])[:6]
            + (missing_in_selected_by_bucket.get("characters") or [])[:6]
            + (missing_in_selected_by_bucket.get("environments") or [])[:6]
        )
        warnings.append(
            "Subjects JSON extraction warning: 当前返回的 subjects_json 可能只命中了部分 JSON 候选。"
            + ("；" + "，".join(warning_text_parts) if warning_text_parts else "")
            + (f"。示例: {', '.join(sample)}" if sample else "")
        )
        diagnosis.append("raw_output_contains_more_subjects_than_selected_subjects_json")

    return {
        "selected_counts": {
            "characters": len(selected_keys.get("characters") or {}),
            "props": len(selected_keys.get("props") or {}),
            "environments": len(selected_keys.get("environments") or {}),
            "covers": len(selected_keys.get("covers") or {}),
            "posters": len(selected_keys.get("posters") or {}),
        },
        "aggregated_counts": {
            "characters": len(aggregated_keys.get("characters") or {}),
            "props": len(aggregated_keys.get("props") or {}),
            "environments": len(aggregated_keys.get("environments") or {}),
            "covers": len(aggregated_keys.get("covers") or {}),
            "posters": len(aggregated_keys.get("posters") or {}),
        },
        "missing_in_selected_by_bucket": missing_in_selected_by_bucket,
        "missing_total": missing_total,
        "warning_codes": warning_codes,
        "warnings": warnings,
        "diagnosis": diagnosis,
    }


def _format_subject_ref(name: str, normalized_type: str) -> str:
    """Canonical CHAR/PROP/ENV/COVER subject-ref token for reuse-asset prompts."""
    clean_name = _normalize_subject_name(name)
    if not clean_name:
        return ""
    if normalized_type == "character":
        return f"CHAR:[@{clean_name}]"
    if normalized_type == "prop":
        return f"PROP:[{clean_name}]"
    if normalized_type == "environment":
        return f"ENV:[{clean_name}]"
    if normalized_type == "cover":
        return f"COVER:[{clean_name}]"
    return f"SUBJECT:[{clean_name}]"

