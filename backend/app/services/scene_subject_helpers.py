# -*- coding: utf-8 -*-
"""Scene subject inventory / markdown parse / subjects JSON helpers."""
from __future__ import annotations

import html
import json
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from app.core.entity_token import subject_compare_key, subject_compare_key_variants
from app.core.prompt_injection import wrap_injection_section
from app.models.all_models import Entity, Episode
from app.services.llm_markdown_sanitize import sanitize_subject_index_text
from app.services.project_episode_utils import _resolve_episode_sort_number
from app.services.script_analysis_flow import (
    _reconcile_scene_table_row_cells,
    _split_scene_table_cells,
)
from app.services.soft_delete import _active_entity_clause, _active_episode_clause

logger = logging.getLogger("api_logger")

def _build_project_subject_inventory(
    db: Session,
    project_id: int,
    limit_per_type: int = 120,
    episode_id: Optional[int] = None,
) -> Dict[str, List[Dict[str, str]]]:
    """Build subject inventory for prompt-time reuse and recognition.

    When episode_id is provided, inventory is scoped to that episode only.
    """
    inventory: Dict[str, List[Dict[str, str]]] = {
        "characters": [], "covers": [],
        "props": [],
        "environments": [],
        "posters": [],
    }

    entities_query = db.query(Entity).filter(
        Entity.project_id == int(project_id),
        _active_entity_clause(),
    )
    if episode_id is not None:
        entities_query = entities_query.filter(Entity.episode_id == int(episode_id))
    entities = entities_query.order_by(Entity.id.asc()).all()
    seen_keys = set()

    for ent in entities:
        normalized_type = _normalize_subject_entity_type(getattr(ent, "type", None))
        bucket = (
            "characters" if normalized_type == "character"
            else "props" if normalized_type == "prop"
            else "environments" if normalized_type == "environment"
            else "covers"
        )

        name = str(getattr(ent, "name", None) or "").strip()
        name_en = str(getattr(ent, "name_en", None) or "").strip()
        canonical_name = name or name_en
        if not canonical_name:
            continue

        key = f"{bucket}:{canonical_name.lower()}"
        if key in seen_keys:
            continue
        if len(inventory[bucket]) >= limit_per_type:
            continue
        seen_keys.add(key)

        if bucket == "characters":
            subject_ref = f"CHAR:[@{canonical_name}]"
        elif bucket == "props":
            subject_ref = f"PROP:[{canonical_name}]"
        else:
            subject_ref = f"ENV:[{canonical_name}]"

        anchor_description = str(getattr(ent, "anchor_description", None) or "").strip()

        narrative_hint = str(getattr(ent, "description", None) or "").strip()

        inventory[bucket].append({
            "id": str(getattr(ent, "id", "") or "").strip(),
            "name": canonical_name,
            "name_en": name_en,
            "subject_ref": subject_ref,
            "anchor_description": anchor_description,
            "description": narrative_hint,
            "type": normalized_type or bucket[:-1],
        })

    return inventory


def _format_project_subject_inventory_block(inventory: Dict[str, List[Dict[str, str]]]) -> str:
    type_names = {
        "characters": "角色",
        "props": "道具",
        "environments": "场景",
        "covers": "封面",
        "posters": "海报"
    }

    def _format_bucket(bucket_name: str) -> str:
        items = inventory.get(bucket_name) or []
        if not items:
            return f"{bucket_name}: (none)"

        type_cn = type_names.get(bucket_name, bucket_name)
        lines: List[str] = [f"{bucket_name} ({len(items)}):"]
        for item in items:
            bits: List[str] = []
            bits.append(f"资产实体类型={type_cn}")
            
            name = str(item.get("name") or "").strip()
            if name:
                bits.append(f"实体中文名={name}")
                
            name_en = str(item.get("name_en") or "").strip()
            if name_en:
                bits.append(f"实体英文名={name_en}")
                
            archetype = str(item.get("archetype") or "").strip()
            if archetype:
                bits.append(f"archetype={archetype}")
                
            lines.append(f"  - {' | '.join(bits)}")
        return "\n".join(lines)

    inventory_body = (
        "Existing Entity Inventory By Category:\n"
        f"{_format_bucket('characters')}\n"
        f"{_format_bucket('props')}\n"
        f"{_format_bucket('environments')}"
    )
    return (
        "[Project Existing Subject Index]\n"
        f"{wrap_injection_section('项目既有Subject Index', inventory_body)}"
    )


_PRIOR_ENTITY_DESIGN_TYPES = frozenset({"character", "prop", "environment"})


def _normalize_prior_entity_design_type(raw_type: Any) -> str:
    """Normalize entity/subject type for prior-prompt reuse; posters/covers excluded."""
    t = str(raw_type or "").strip().lower()
    t = re.sub(r"[\s_\-]+", "", t)
    if t in {"character", "characters", "char", "人物", "角色"}:
        return "character"
    if t in {"prop", "props", "item", "items", "道具", "物件"}:
        return "prop"
    if t in {"environment", "environments", "env", "scene", "scenes", "场景", "环境"}:
        return "environment"
    return ""


def _parse_subject_index_entries_for_prior_prompts(
    subject_index_text: Any,
    allowed_types: Optional[set] = None,
) -> List[Dict[str, str]]:
    """Extract (type, name_zh, name_en) rows from Subject Index for prior-prompt lookup."""
    text = sanitize_subject_index_text(subject_index_text)
    if not text:
        return []

    allowed = {
        _normalize_prior_entity_design_type(item)
        for item in (allowed_types or _PRIOR_ENTITY_DESIGN_TYPES)
    }
    allowed = {item for item in allowed if item in _PRIOR_ENTITY_DESIGN_TYPES}
    if not allowed:
        return []

    entries: List[Dict[str, str]] = []
    seen_keys: set = set()

    def _push(entity_type: str, name_zh: str, name_en: str = "") -> None:
        normalized_type = _normalize_prior_entity_design_type(entity_type)
        if normalized_type not in allowed:
            return
        zh = str(name_zh or "").strip()
        en = str(name_en or "").strip()
        canonical = zh or en
        if not canonical:
            return
        compare_key = subject_compare_key(canonical)
        if not compare_key:
            return
        dedupe_key = f"{normalized_type}:{compare_key}"
        if dedupe_key in seen_keys:
            return
        seen_keys.add(dedupe_key)
        entries.append({
            "type": normalized_type,
            "name_zh": zh,
            "name_en": en,
            "name": canonical,
        })

    for raw_line in str(text).splitlines():
        line = str(raw_line or "").replace("\ufeff", "").strip()
        if not line:
            continue
        line = re.sub(r"^\s*>\s*", "", line)
        line = re.sub(r"^\s*[-*+]\s+", "", line).strip()

        key_value_type_match = re.search(r"\bsubject_type\s*=\s*([^|`\n]+)", line, flags=re.IGNORECASE)
        if key_value_type_match:
            name_zh_match = re.search(r"\bsubject_name_(?:zh|exact)\s*=\s*([^|`\n]+)", line, flags=re.IGNORECASE)
            name_en_match = re.search(r"\bsubject_name_en\s*=\s*([^|`\n]+)", line, flags=re.IGNORECASE)
            if name_zh_match or name_en_match:
                _push(
                    key_value_type_match.group(1),
                    (name_zh_match.group(1) if name_zh_match else ""),
                    (name_en_match.group(1) if name_en_match else ""),
                )
                continue

        normalized_line = line.strip("|").strip()
        parts = [p.strip() for p in normalized_line.split("|")]
        if len(parts) >= 4 and re.match(r"^S\d+\b", normalized_line, flags=re.IGNORECASE):
            _push(parts[1], parts[2], parts[3] if len(parts) > 3 else "")

    return entries


def _build_prior_entity_generation_prompts_block(
    db: Session,
    project_id: int,
    subject_index_text: Any,
    allowed_types: Optional[set] = None,
    episode_id: Optional[int] = None,
) -> str:
    """Look up same-type/same-name entities in the current episode and inject generation_prompt_cn.

    Injection is strictly episode-scoped: entities from other episodes are never included.
    Poster/cover entities are never included.
    """
    try:
        project_id_int = int(project_id)
    except Exception:
        return ""
    if project_id_int <= 0:
        return ""
    try:
        episode_id_int = int(episode_id) if episode_id is not None else 0
    except Exception:
        episode_id_int = 0
    if episode_id_int <= 0:
        logger.info(
            "[analyze_scene] prior entity prompts skipped: episode_id required project_id=%s",
            project_id_int,
        )
        return ""

    subject_entries = _parse_subject_index_entries_for_prior_prompts(
        subject_index_text,
        allowed_types=allowed_types,
    )
    if not subject_entries:
        return ""

    entities = (
        db.query(Entity)
        .filter(
            Entity.project_id == project_id_int,
            Entity.episode_id == episode_id_int,
            _active_entity_clause(),
        )
        .all()
    )
    if not entities:
        return ""

    episode_by_id: Dict[int, Episode] = {}
    episode_row = (
        db.query(Episode)
        .filter(Episode.id == episode_id_int, _active_episode_clause())
        .first()
    )
    if episode_row is not None:
        episode_by_id[episode_id_int] = episode_row

    def _entity_episode_sort_tuple(ent: Entity) -> Tuple[int, int, int]:
        """Prefer newer entity id when multiple same-name matches exist in-episode."""
        entity_id = int(getattr(ent, "id", 0) or 0)
        return (1, entity_id, entity_id)

    # Index project entities by type + compare-key for O(1) name matching.
    entities_by_type_key: Dict[str, List[Entity]] = {}
    for ent in entities:
        normalized_type = _normalize_prior_entity_design_type(getattr(ent, "type", None))
        if normalized_type not in _PRIOR_ENTITY_DESIGN_TYPES:
            continue
        if not str(getattr(ent, "generation_prompt_cn", None) or "").strip():
            continue
        alias_keys: set = set()
        for alias in (getattr(ent, "name", None), getattr(ent, "name_en", None)):
            alias_keys.update(subject_compare_key_variants(alias))
        for key in alias_keys:
            if not key:
                continue
            bucket_key = f"{normalized_type}:{key}"
            entities_by_type_key.setdefault(bucket_key, []).append(ent)

    prompt_lines: List[str] = []
    seen_refs: set = set()
    for entry in subject_entries:
        entity_type = entry.get("type") or ""
        candidate_keys: set = set()
        for alias in (entry.get("name_zh"), entry.get("name_en"), entry.get("name")):
            candidate_keys.update(subject_compare_key_variants(alias))
        matched: List[Entity] = []
        seen_entity_ids: set = set()
        for key in candidate_keys:
            if not key:
                continue
            for ent in entities_by_type_key.get(f"{entity_type}:{key}", []):
                ent_id = int(getattr(ent, "id", 0) or 0)
                if ent_id in seen_entity_ids:
                    continue
                seen_entity_ids.add(ent_id)
                matched.append(ent)
        if not matched:
            continue
        best = max(matched, key=_entity_episode_sort_tuple)
        prompt_cn = re.sub(r"\s+", " ", str(getattr(best, "generation_prompt_cn", None) or "")).strip()
        if not prompt_cn:
            continue

        canonical_name = str(
            entry.get("name")
            or getattr(best, "name", None)
            or getattr(best, "name_en", None)
            or ""
        ).strip()
        if not canonical_name:
            continue
        if entity_type == "character":
            subject_ref = f"CHAR:[@{canonical_name}]"
        elif entity_type == "prop":
            subject_ref = f"PROP:[{canonical_name}]"
        else:
            subject_ref = f"ENV:[{canonical_name}]"
        if subject_ref in seen_refs:
            continue
        seen_refs.add(subject_ref)

        ep_id = getattr(best, "episode_id", None)
        try:
            ep_id_int = int(ep_id) if ep_id is not None else 0
        except Exception:
            ep_id_int = 0
        episode = episode_by_id.get(ep_id_int) if ep_id_int else None
        episode_number = _resolve_episode_sort_number(episode) if episode else None
        episode_label = (
            f"EP{int(episode_number):02d}"
            if episode_number is not None
            else (f"episode_id={ep_id_int}" if ep_id_int > 0 else "episode=project")
        )
        prompt_lines.append(
            f"- {subject_ref} | source={episode_label} | entity_id={getattr(best, 'id', '')} | generation_prompt_cn={prompt_cn}"
        )

    if not prompt_lines:
        return ""

    body = (
        "# Prior Entity Image Prompts (Design Baseline)\n"
        "The following Chinese image-generation prompts come from existing same-type / same-name "
        "entities already stored in THIS episode only. Entities from other episodes are never injected. "
        "Poster/cover entities are excluded.\n"
        "\n"
        "## Mandatory reuse rules (read carefully)\n"
        "1) **Stable / identity attributes MUST follow the injected prior prompt** as the authoritative "
        "visual reference. Evolve from it; do not invent a conflicting redesign.\n"
        "   - Character: facial bone structure, facial features, skin undertone, body proportions, "
        "silhouette, race/ethnicity cues, and other appearance-identity anchors. Even for aging, injury, "
        "or state variants, evolve from the prior appearance description (same person continuity).\n"
        "   - Prop: core form, structure, material family, distinctive markings, and recognition anchors.\n"
        "   - Environment: spatial identity, key fixed fixtures, layout anchors, and recognisable "
        "architectural/set DNA.\n"
        "2) **Variable attributes are NOT constrained by the prior prompt** and may be redesigned freely "
        "to match the current Subject Index / episode story needs.\n"
        "   - Character: clothing, hairstyle (when story allows change), makeup look, temporary accessories, "
        "and other outfit/grooming choices.\n"
        "   - Prop: transient state overlays that do not rewrite core identity (unless Subject Index "
        "explicitly requires a new identity form).\n"
        "   - Environment: lighting mood, temporary dressing, and ephemeral atmosphere overlays that do "
        "not rewrite the space's fixed identity.\n"
        "3) Prefer continuity of recognition: a viewer who saw the prior entity should still recognise "
        "this entity after the allowed variable changes.\n"
        + "\n".join(prompt_lines)
        + "\n"
    )
    logger.info(
        "[analyze_scene] built prior entity generation prompts project_id=%s episode_id=%s subjects=%s matched=%s",
        project_id_int,
        episode_id_int,
        len(subject_entries),
        len(prompt_lines),
    )
    return wrap_injection_section("既有实体中文生图提示词", body)


def _normalize_scene_header(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = re.sub(r"[*_`]+", "", text)
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[\.:\-_/\\|]+", "", text)
    return text


def _clean_scene_table_cell(value: Any) -> str:
    text = str(value or "")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = text.replace("\\|", "|")
    return html.unescape(text).strip()


def _parse_scene_rows_from_markdown(markdown_text: str) -> List[Dict[str, str]]:
    if not markdown_text:
        return []

    lines = [line.rstrip("\n\r") for line in str(markdown_text).splitlines()]
    if not lines:
        return []

    def _split_row(line: str) -> List[str]:
        return _split_scene_table_cells(line)

    def _reconcile_row(cols: List[str], headers: List[str]) -> List[str]:
        return _reconcile_scene_table_row_cells(cols, headers)

    def _find_idx(headers: List[str], aliases: List[str]) -> int:
        normalized_headers = [_normalize_scene_header(h) for h in headers]
        normalized_aliases = [_normalize_scene_header(a) for a in aliases]
        for idx, h in enumerate(normalized_headers):
            for alias in normalized_aliases:
                if alias and (h == alias or alias in h):
                    return idx
        return -1

    fallback_scene_headers = [
        "Episode ID",
        "Scene ID",
        "Scene No",
        "Scene Name",
        "Equivalent Duration",
        "Core Scene Info",
        "Original Script Text",
        "Environment Name",
        "Environment Relation",
        "Base Environment Reference",
        "Environment Delta",
        "Entry State",
        "Exit State",
        "Linked Characters",
        "Key Props",
    ]

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue

        headers = _split_row(stripped)
        j = i + 1

        # Fallback for headerless tables: separator + data rows only.
        if re.fullmatch(r"[\|\s:\-]+", stripped or ""):
            first_data_idx = -1
            first_data_cols: List[str] = []
            for k in range(i + 1, len(lines)):
                candidate = lines[k].strip()
                if not candidate:
                    continue
                if not candidate.startswith("|"):
                    break
                if re.fullmatch(r"[\|\s:\-]+", candidate or ""):
                    continue
                first_data_cols = _split_row(candidate)
                first_data_idx = k
                break

            if first_data_idx < 0 or not first_data_cols:
                continue

            needed = len(first_data_cols)
            headers = list(fallback_scene_headers[:needed])
            if needed > len(headers):
                headers.extend([f"Column {idx}" for idx in range(len(headers) + 1, needed + 1)])
            j = first_data_idx

        if len(headers) < 4:
            continue

        scene_no_idx = _find_idx(headers, ["Scene No", "场次", "场次号", "场次序号"])
        scene_id_idx = _find_idx(headers, ["Scene ID", "场景ID", "场景编号"])
        core_idx = _find_idx(headers, ["Core Scene Info", "核心场景信息", "Core Goal"])
        original_idx = _find_idx(headers, ["Original Script Text", "原始剧本文本", "Description", "Adapted Script Text", "改编剧本", "改编剧本文本"])

        if core_idx < 0 and original_idx < 0:
            continue

        if j == i + 1 and j < len(lines):
            separator = lines[j].strip()
            if separator.startswith("|") and re.fullmatch(r"[\|\s:\-]+", separator or ""):
                j += 1

        parsed_rows: List[Dict[str, str]] = []

        scene_name_idx = _find_idx(headers, ["Scene Name", "场景名称", "场景名", "Title"])
        duration_idx = _find_idx(headers, ["Equivalent Duration", "Duration", "时长"])
        env_name_idx = _find_idx(headers, ["Environment Name", "环境名称", "环境锚点"])
        linked_chars_idx = _find_idx(headers, ["Linked Characters", "关联角色", "角色"])
        key_props_idx = _find_idx(headers, ["Key Props", "关键道具", "道具"])

        while j < len(lines):
            row_line = lines[j].strip()
            if not row_line.startswith("|"):
                break
            if re.fullmatch(r"[\|\s:\-]+", row_line or ""):
                j += 1
                continue

            cols = _reconcile_row(_split_row(row_line), headers)
            if not cols:
                j += 1
                continue

            def _get(idx: int) -> str:
                return _clean_scene_table_cell(cols[idx]) if idx >= 0 and idx < len(cols) else ""

            row_payload = {
                "scene_id": _get(scene_id_idx),
                "scene_no": _get(scene_no_idx),
                "scene_name": _get(scene_name_idx),
                "equivalent_duration": _get(duration_idx),
                "core_scene_info": _get(core_idx),
                "original_script_text": _get(original_idx),
                "environment_name": _get(env_name_idx),
                "linked_characters": _get(linked_chars_idx),
                "key_props": _get(key_props_idx),
            }

            if any(str(v or "").strip() for v in row_payload.values()):
                parsed_rows.append(row_payload)

            j += 1

        if parsed_rows:
            return parsed_rows

    return []


def _normalize_subject_entity_type(raw_type: Any) -> str:
    text = str(raw_type or "").strip().lower()
    if text in {"character", "characters", "char", "人物", "角色"}:
        return "character"
    if text in {"prop", "props", "道具", "物件"}:
        return "prop"
    if text in {"environment", "environments", "env", "场景", "环境"}:
        return "environment"
    if text in {"cover", "covers", "poster", "posters", "cover_poster", "封面", "封面海报"}:
        return "cover"
    return "character"


def _collect_llm_json_text_candidates(raw_text: str) -> List[str]:
    text = str(raw_text or "").strip()
    if not text:
        return []

    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE).strip()
    candidates: List[str] = []
    seen: set = set()

    def _push(value: str) -> None:
        candidate = str(value or "").strip()
        if not candidate or candidate in seen:
            return
        seen.add(candidate)
        candidates.append(candidate)

    fence_re = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
    for match in fence_re.finditer(text):
        _push(match.group(1))

    open_fence_re = re.compile(r"```(?:json)?\s*([\s\S]*)$", re.IGNORECASE)
    open_match = open_fence_re.search(text)
    if open_match:
        _push(open_match.group(1))

    if text.startswith("{") or text.startswith("["):
        _push(text)

    entity_key_re = re.compile(r'"(?:characters|props|environments|covers|posters)"\s*:\s*[\[{]', re.IGNORECASE)
    key_match = entity_key_re.search(text)
    if key_match:
        obj_start = text.rfind("{", 0, key_match.start())
        if obj_start >= 0:
            depth = 0
            in_str = False
            escape = False
            for i in range(obj_start, len(text)):
                ch = text[i]
                if in_str:
                    if escape:
                        escape = False
                        continue
                    if ch == "\\":
                        escape = True
                        continue
                    if ch == '"':
                        in_str = False
                    continue
                if ch == '"':
                    in_str = True
                    continue
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        _push(text[obj_start:i + 1])
                        break

    reasoning_prefix_re = re.compile(
        r"^\s*(?:i will|let me|let's|analysis|reasoning|thought process|"
        r"分析|思路|推理|下面|我将|我认为|接下来|我先|我会|现在|首先)\b",
        flags=re.IGNORECASE,
    )
    lines = text.splitlines()
    while lines and not str(lines[0] or "").strip():
        lines.pop(0)
    while lines and reasoning_prefix_re.match(str(lines[0] or "")):
        first_line = str(lines[0] or "").strip()
        if first_line.startswith("{") or first_line.startswith("[") or first_line.startswith("```") or entity_key_re.search(first_line):
            break
        lines.pop(0)
    trimmed_reasoning = "\n".join(lines).strip()
    if trimmed_reasoning and trimmed_reasoning != text:
        if trimmed_reasoning.startswith("{") or trimmed_reasoning.startswith("["):
            _push(trimmed_reasoning)
        key_match = entity_key_re.search(trimmed_reasoning)
        if key_match:
            obj_start = trimmed_reasoning.rfind("{", 0, key_match.start())
            if obj_start >= 0:
                depth = 0
                in_str = False
                escape = False
                for i in range(obj_start, len(trimmed_reasoning)):
                    ch = trimmed_reasoning[i]
                    if in_str:
                        if escape:
                            escape = False
                            continue
                        if ch == "\\":
                            escape = True
                            continue
                        if ch == '"':
                            in_str = False
                        continue
                    if ch == '"':
                        in_str = True
                        continue
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0:
                            _push(trimmed_reasoning[obj_start:i + 1])
                            break

    return candidates


def _extract_subjects_json_from_text(raw_text: str) -> Dict[str, Any]:
    payload: Dict[str, List[Dict[str, Any]]] = {
        "characters": [], "covers": [],
        "props": [],
        "environments": [],
        "posters": [],
    }
    text = str(raw_text or "").strip()
    if not text:
        return payload

    candidates: List[str] = []
    for candidate in _collect_llm_json_text_candidates(text):
        candidates.append(candidate)

    fence_re = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
    for m in fence_re.finditer(text):
        candidate = str(m.group(1) or "").strip()
        if candidate:
            candidates.append(candidate)

    if text.startswith("{") or text.startswith("["):
        candidates.append(text)

    def _extract_balanced_json_objects(source: str, max_count: int = 24) -> List[str]:
        objects: List[str] = []
        depth = 0
        in_str = False
        escape = False
        obj_start = -1
        for i, ch in enumerate(source):
            if in_str:
                if escape:
                    escape = False
                    continue
                if ch == "\\":
                    escape = True
                    continue
                if ch == '"':
                    in_str = False
                continue

            if ch == '"':
                in_str = True
                continue

            if ch == "{":
                if depth == 0:
                    obj_start = i
                depth += 1
                continue

            if ch == "}":
                if depth <= 0:
                    continue
                depth -= 1
                if depth == 0 and obj_start >= 0:
                    candidate = source[obj_start:i + 1].strip()
                    if candidate:
                        objects.append(candidate)
                        if len(objects) >= max_count:
                            break
                    obj_start = -1

        return objects

    def _build_section_only_candidate(source: str, section: str) -> Optional[str]:
        section_key = str(section or "").strip()
        if not section_key:
            return None
        key_re = re.compile(rf'"{re.escape(section_key)}"\s*:\s*\[', re.IGNORECASE)
        m = key_re.search(source)
        if not m:
            return None

        start_bracket = source.find("[", m.start())
        if start_bracket < 0:
            return None

        depth = 0
        in_str = False
        escape = False
        end_bracket = -1
        for i in range(start_bracket, len(source)):
            ch = source[i]
            if in_str:
                if escape:
                    escape = False
                    continue
                if ch == "\\":
                    escape = True
                    continue
                if ch == '"':
                    in_str = False
                continue

            if ch == '"':
                in_str = True
                continue
            if ch == "[":
                depth += 1
                continue
            if ch == "]":
                depth -= 1
                if depth == 0:
                    end_bracket = i
                    break

        if end_bracket < 0:
            return None

        array_text = source[start_bracket:end_bracket + 1].strip()
        if not array_text:
            return None

        skeleton: Dict[str, Any] = {
            "characters": [],
            "props": [],
            "environments": [],
            "covers": [],
            "posters": [],
        }
        try:
            parsed_array = json.loads(array_text, strict=False)
            if isinstance(parsed_array, list):
                skeleton[section_key] = parsed_array
                # Keep both aliases synchronized to reduce downstream miss.
                if section_key == "covers":
                    skeleton["posters"] = parsed_array
                elif section_key == "posters":
                    skeleton["covers"] = parsed_array
                return json.dumps(skeleton, ensure_ascii=False)
        except Exception:
            return None
        return None

    def _extract_object_after_label(source: str, label: str) -> Optional[str]:
        lower = source.lower()
        idx = lower.find(label.lower())
        if idx < 0:
            return None
        obj_start = source.find("{", idx)
        if obj_start < 0:
            return None

        depth = 0
        in_str = False
        escape = False
        for i in range(obj_start, len(source)):
            ch = source[i]
            if in_str:
                if escape:
                    escape = False
                    continue
                if ch == "\\":
                    escape = True
                    continue
                if ch == '"':
                    in_str = False
                continue

            if ch == '"':
                in_str = True
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return source[obj_start:i + 1]
        return None

    def _extract_object_near_key(source: str, key_name: str) -> Optional[str]:
        lower = source.lower()
        needle = f'"{key_name.lower()}"'
        start_pos = 0
        while True:
            idx = lower.find(needle, start_pos)
            if idx < 0:
                return None
            obj_start = source.rfind("{", 0, idx)
            if obj_start < 0:
                start_pos = idx + 1
                continue

            depth = 0
            in_str = False
            escape = False
            for i in range(obj_start, len(source)):
                ch = source[i]
                if in_str:
                    if escape:
                        escape = False
                        continue
                    if ch == "\\":
                        escape = True
                        continue
                    if ch == '"':
                        in_str = False
                    continue

                if ch == '"':
                    in_str = True
                    continue
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        return source[obj_start:i + 1]

            start_pos = idx + 1

    for key_name in ("characters", "props", "environments", "covers", "posters"):
        key_object = _extract_object_near_key(text, key_name)
        if key_object:
            candidates.append(key_object)

    labeled_object = _extract_object_after_label(text, "SUBJECTS_JSON")
    if labeled_object:
        candidates.append(labeled_object)

    for candidate in _extract_balanced_json_objects(text):
        lower = candidate.lower()
        if any(token in lower for token in ('"characters"', '"props"', '"environments"', '"covers"', '"posters"')):
            candidates.append(candidate)

    for section_name in ("characters", "props", "environments", "covers", "posters"):
        section_candidate = _build_section_only_candidate(text, section_name)
        if section_candidate:
            candidates.append(section_candidate)

    def _pick_text(*values: Any) -> str:
        for value in values:
            candidate = str(value or "").strip()
            if candidate:
                return candidate
        return ""

    def _normalize_item(section: str, item: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(item)
        normalized["name"] = _pick_text(
            item.get("name"),
            item.get("subject_name_exact"),
            item.get("subject_name"),
            item.get("name_zh"),
            item.get("display_name"),
            item.get("name_en"),
        )
        normalized["name_en"] = _pick_text(
            item.get("name_en"),
            item.get("english_name"),
            item.get("en_name"),
        )
        normalized["base_name_en"] = _pick_text(
            item.get("base_name_en"),
        )

        if section == "characters":
            description_cn = _pick_text(
                item.get("description_cn"),
                item.get("description"),
                item.get("narrative_description"),
                item.get("appearance_cn"),
            )
            if not description_cn:
                description_cn = "；".join(
                    value for value in [
                        _pick_text(item.get("appearance_cn")),
                        _pick_text(item.get("clothing")),
                        _pick_text(item.get("action_characteristics")),
                    ] if value
                )
            normalized["description_cn"] = description_cn
        elif section in ("props", "environments", "covers", "posters"):
            normalized["description_cn"] = _pick_text(
                item.get("description_cn"),
                item.get("description"),
                item.get("narrative_description"),
            )

        return normalized

    dedup_keys = set()
    for candidate in candidates:
        dedup_key = candidate[:2000]
        if dedup_key in dedup_keys:
            continue
        dedup_keys.add(dedup_key)

        try:
            # Fix trailing commas before loads
            cleaned_candidate = re.sub(r",\s*([\]}])", r"\1", candidate)
            parsed = json.loads(cleaned_candidate, strict=False)
        except Exception:
            continue

        parsed_objects = []
        if isinstance(parsed, list):
            grouped = {"characters": [], "props": [], "environments": [], "covers": [], "posters": []}
            for item in parsed:
                if not isinstance(item, dict):
                    continue

                # Support array-wrapped payloads, e.g. [{"characters": [...]}]
                has_bucket_keys = any(k in item for k in ("characters", "props", "environments", "covers", "posters"))
                wrapped_payload = item.get("entities") or item.get("subjects") or item.get("payload")
                if has_bucket_keys:
                    parsed_objects.append(item)
                    continue
                if isinstance(wrapped_payload, dict):
                    parsed_objects.append(wrapped_payload)
                    continue

                # Flat typed-array fallback, e.g. [{"type":"character", ...}, ...]
                t = str(item.get("type") or item.get("subject_type") or item.get("entity_type") or "").strip().lower()
                if t in {"character", "characters", "char", "role", "roles", "人物", "角色"}:
                    grouped["characters"].append(item)
                elif t in {"prop", "props", "item", "items", "道具", "物件"}:
                    grouped["props"].append(item)
                elif t in {"environment", "environments", "env", "scene", "场景", "环境"}:
                    grouped["environments"].append(item)
                elif t in {"poster", "posters", "cover", "covers", "海报", "封面"}:
                    grouped["covers"].append(item)

            if any(len(grouped.get(k) or []) > 0 for k in ("characters", "props", "environments", "covers", "posters")):
                parsed_objects.append(grouped)
        elif isinstance(parsed, dict):
            parsed_objects.append(parsed)

        for obj in parsed_objects:
            if not isinstance(obj, dict):
                continue
                
            for wrapper_key in ("entities", "subjects", "payload"):
                if wrapper_key in obj and isinstance(obj[wrapper_key], dict):
                    obj = obj[wrapper_key]
                    break
                    
            for section in ("characters", "props", "environments", "covers", "posters"):
                items = obj.get(section)
                if section == "covers" and not items and "posters" in obj:
                    items = obj.get("posters")
                if not isinstance(items, list):
                    continue
                normalized_items = []
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    normalized = _normalize_item(section, item)
                    if not normalized.get("name") and not normalized.get("subject_no"):
                        continue
                    normalized_items.append(normalized)
                payload[section].extend(normalized_items)

    # Merge all candidates first, then deduplicate to avoid losing entities when
    # early candidates are partial/incomplete.
    for section in ("characters", "props", "environments", "covers", "posters"):
        seen_item_keys = set()
        deduped_items: List[Dict[str, Any]] = []
        for item in payload.get(section) or []:
            if not isinstance(item, dict):
                continue
            item_key = "|".join([
                str(item.get("subject_no") or "").strip().lower(),
                str(item.get("name") or "").strip().lower(),
                str(item.get("name_en") or "").strip().lower(),
                section,
            ])
            if item_key in seen_item_keys:
                continue
            seen_item_keys.add(item_key)
            deduped_items.append(item)
        payload[section] = deduped_items

    cover_poster_items: List[Dict[str, Any]] = []
    cover_poster_seen: set = set()
    for item in (payload.get("covers") or []) + (payload.get("posters") or []):
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
        payload["covers"] = cover_poster_items
        payload["posters"] = cover_poster_items

    return payload

