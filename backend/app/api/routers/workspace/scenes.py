# -*- coding: utf-8 -*-
"""Workspace section routes — symbols pulled from shared module."""
from __future__ import annotations

from app.api.routers.workspace import shared as _shared

# Attach routes onto the same APIRouter instance and reuse helpers.
router = _shared.router
globals().update({k: v for k, v in vars(_shared).items() if k not in {"__name__", "__file__", "__package__", "__loader__", "__spec__", "__doc__", "__builtins__"}})


# --- Scenes ---

from app.schemas.scene import (  # noqa: E402,F401
    SceneBatchUpsertRequest,
    SceneCreate,
    SceneOut,
    ScenePurgeRequest,
    SceneRegenerateRequest,
)

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

    entities_query = db.query(Entity).filter(Entity.project_id == int(project_id))
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
    episode_row = db.query(Episode).filter(Episode.id == episode_id_int).first()
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

        scene_no_idx = _find_idx(headers, ["Scene No", "场次", "场次号"])
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


@router.get("/episodes/{episode_id}/scenes", response_model=List[SceneOut])
def read_scenes(
    episode_id: int,
    scene_code: Optional[str] = None,
    keyword: Optional[str] = None,
    skip: int = 0,
    limit: int = 300,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Ownership check
    episode = db.query(Episode).filter(Episode.id == episode_id, _active_episode_clause()).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
        
    _require_project_access(db, episode.project_id, current_user)
        
    query = db.query(Scene).filter(Scene.episode_id == episode_id, _active_scene_clause())
    if scene_code:
        token = f"%{scene_code.strip()}%"
        query = query.filter(Scene.scene_no.ilike(token))
    if keyword:
        token = f"%{keyword.strip()}%"
        query = query.filter(
            or_(
                Scene.scene_name.ilike(token),
                Scene.environment_name.ilike(token),
                Scene.linked_characters.ilike(token),
                Scene.key_props.ilike(token),
            )
        )
    safe_skip = max(int(skip or 0), 0)
    safe_limit = max(1, min(int(limit or 300), 500))
    rows = _sort_scenes_by_scene_no(query.all())
    return rows[safe_skip:safe_skip + safe_limit]

@router.post("/episodes/{episode_id}/scenes", response_model=SceneOut)
def create_scene(
    episode_id: int,
    scene: SceneCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    scene_api_started_perf = time.perf_counter()
    episode = db.query(Episode).filter(Episode.id == episode_id, _active_episode_clause()).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
        
    _require_project_access(db, episode.project_id, current_user)

    canonical_scene_no = _canonicalize_scene_no(
        getattr(scene, "scene_no", None),
        scene_id=getattr(scene, "scene_id", None) if hasattr(scene, "scene_id") else None,
    )
    if not canonical_scene_no:
        raise HTTPException(status_code=422, detail="SCENE_NO_REQUIRED")

    existing_scene = _find_active_scene_by_scene_no(
        db,
        episode_id=episode_id,
        scene_no=canonical_scene_no,
    )
    if existing_scene:
        # Import control: scene_no already present — abandon overwrite, return existing.
        # Also heal legacy alias rows (EP01_SC03) onto the canonical number ("3").
        if str(existing_scene.scene_no or "").strip() != canonical_scene_no:
            existing_scene.scene_no = canonical_scene_no
            db.add(existing_scene)
            db.commit()
            db.refresh(existing_scene)
        elapsed_ms = int((time.perf_counter() - scene_api_started_perf) * 1000)
        logger.info(
            "[SceneImportAPI] skip-existing | episode_id=%s | project_id=%s | scene_id=%s | scene_no=%s | elapsed_ms=%s",
            episode_id,
            episode.project_id,
            existing_scene.id,
            str(existing_scene.scene_no or "").strip(),
            elapsed_ms,
        )
        return existing_scene

    logger.info(
        "[SceneImportAPI] create-new start | episode_id=%s | project_id=%s | scene_no=%s | scene_name=%s",
        episode_id,
        episode.project_id,
        canonical_scene_no,
        str(scene.scene_name or "").strip(),
    )
    db_scene = Scene(
        episode_id=episode_id,
        scene_no=canonical_scene_no,
        original_script_text=scene.original_script_text,
        scene_name=scene.scene_name,
        equivalent_duration=scene.equivalent_duration,
        core_scene_info=scene.core_scene_info,
        environment_name=scene.environment_name,
        linked_characters=scene.linked_characters,
        key_props=scene.key_props
    )
    db.add(db_scene)
    try:
        _recompute_and_persist_project_cost_estimation(db, int(episode.project_id))
    except Exception as cost_exc:
        logger.warning("create_scene cost recompute skipped | project_id=%s err=%s", episode.project_id, cost_exc)
    try:
        db.commit()
    except Exception as commit_exc:
        db.rollback()
        raced = _find_active_scene_by_scene_no(
            db,
            episode_id=episode_id,
            scene_no=canonical_scene_no,
        )
        if raced is not None:
            logger.info(
                "[SceneImportAPI] create-new unique-race | episode_id=%s | project_id=%s | scene_id=%s | scene_no=%s | err=%s",
                episode_id,
                episode.project_id,
                raced.id,
                canonical_scene_no,
                commit_exc,
            )
            return raced
        raise
    db.refresh(db_scene)
    elapsed_ms = int((time.perf_counter() - scene_api_started_perf) * 1000)
    logger.info(
        "[SceneImportAPI] create-new done | episode_id=%s | project_id=%s | scene_id=%s | scene_no=%s | elapsed_ms=%s",
        episode_id,
        episode.project_id,
        db_scene.id,
        str(db_scene.scene_no or "").strip(),
        elapsed_ms,
    )
    return db_scene

@router.post("/episodes/{episode_id}/scenes/batch_upsert", response_model=Dict[str, Any])
def batch_upsert_scenes(
    episode_id: int,
    request: SceneBatchUpsertRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    started_perf = time.perf_counter()
    episode = db.query(Episode).filter(Episode.id == episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user)

    input_scenes = list(request.scenes or [])
    if not input_scenes:
        return {
            "status": "ok",
            "episode_id": int(episode_id),
            "project_id": int(episode.project_id),
            "processed": 0,
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "elapsed_ms": int((time.perf_counter() - started_perf) * 1000),
            "scenes": [],
        }

    # Canonicalize + dedupe scene_no within the same import payload (keep first).
    # EP01_SC03 / 03 / 3 collapse to the same key so one episode cannot create aliases.
    deduped_input: List[Any] = []
    seen_input_scene_nos: set = set()
    for item in input_scenes:
        raw_scene_no = str(getattr(item, "scene_no", "") or "").strip()
        scene_no = _canonicalize_scene_no(raw_scene_no)
        if not scene_no:
            deduped_input.append(item)
            continue
        if hasattr(item, "scene_no"):
            item.scene_no = scene_no
        if scene_no in seen_input_scene_nos:
            logger.warning(
                "[SceneImportAPI] batch_upsert skip duplicate scene_no in payload | episode_id=%s scene_no=%s raw=%s",
                episode_id,
                scene_no,
                raw_scene_no,
            )
            continue
        seen_input_scene_nos.add(scene_no)
        deduped_input.append(item)
    input_scenes = deduped_input

    skip_existing = bool(getattr(request, "skip_existing", True))

    lookup_keys: List[str] = []
    for item in input_scenes:
        lookup_keys.extend(_scene_no_lookup_keys(getattr(item, "scene_no", None)))
    lookup_keys = list(dict.fromkeys(lookup_keys))
    existing_rows = (
        db.query(Scene)
        .filter(
            Scene.episode_id == int(episode_id),
            Scene.scene_no.in_(lookup_keys),
            _active_scene_clause(),
        )
        .all()
    ) if lookup_keys else []
    # Collapse active alias/duplicate rows onto one canonical scene_no; keep newest id.
    existing_by_no: Dict[str, Any] = {}
    duplicate_scene_ids: List[int] = []
    for row in existing_rows:
        canonical = _canonicalize_scene_no(getattr(row, "scene_no", None))
        if not canonical:
            continue
        if str(row.scene_no or "").strip() != canonical:
            row.scene_no = canonical
        prev = existing_by_no.get(canonical)
        if prev is None:
            existing_by_no[canonical] = row
            continue
        keep = row if int(getattr(row, "id", 0) or 0) >= int(getattr(prev, "id", 0) or 0) else prev
        drop = prev if keep is row else row
        existing_by_no[canonical] = keep
        duplicate_scene_ids.append(int(drop.id))
    if duplicate_scene_ids:
        now = now_bj_iso()
        db.query(Scene).filter(Scene.id.in_(duplicate_scene_ids)).update(
            {Scene.is_deleted: True, Scene.deleted_at: now},
            synchronize_session=False,
        )
        logger.info(
            "[SceneImportAPI] soft_deleted duplicate active scenes count=%s episode_id=%s",
            len(duplicate_scene_ids),
            episode_id,
        )

    created = 0
    updated = 0
    skipped = 0
    touched_scene_nos: List[str] = []

    for item in input_scenes:
        scene_no = _canonicalize_scene_no(getattr(item, "scene_no", None))
        if not scene_no:
            skipped += 1
            continue
        touched_scene_nos.append(scene_no)
        existing = existing_by_no.get(scene_no)
        if existing is not None:
            if str(existing.scene_no or "").strip() != scene_no:
                existing.scene_no = scene_no
            if skip_existing:
                skipped += 1
                continue
            existing.scene_name = item.scene_name
            existing.original_script_text = item.original_script_text
            existing.equivalent_duration = item.equivalent_duration
            existing.core_scene_info = item.core_scene_info
            existing.environment_name = item.environment_name
            existing.linked_characters = item.linked_characters
            existing.key_props = item.key_props
            updated += 1
            continue

        soft_deleted = (
            db.query(Scene)
            .filter(
                Scene.episode_id == int(episode_id),
                Scene.scene_no.in_(_scene_no_lookup_keys(scene_no)),
                Scene.is_deleted.is_(True),
            )
            .order_by(Scene.id.desc())
            .first()
        )
        if soft_deleted is not None:
            soft_deleted.is_deleted = False
            soft_deleted.deleted_at = None
            soft_deleted.scene_no = scene_no
            soft_deleted.scene_name = item.scene_name
            soft_deleted.original_script_text = item.original_script_text
            soft_deleted.equivalent_duration = item.equivalent_duration
            soft_deleted.core_scene_info = item.core_scene_info
            soft_deleted.environment_name = item.environment_name
            soft_deleted.linked_characters = item.linked_characters
            soft_deleted.key_props = item.key_props
            existing_by_no[scene_no] = soft_deleted
            updated += 1
            continue

        row = Scene(
            episode_id=int(episode_id),
            scene_no=scene_no,
            original_script_text=item.original_script_text,
            scene_name=item.scene_name,
            equivalent_duration=item.equivalent_duration,
            core_scene_info=item.core_scene_info,
            environment_name=item.environment_name,
            linked_characters=item.linked_characters,
            key_props=item.key_props,
        )
        db.add(row)
        existing_by_no[scene_no] = row
        created += 1

    if bool(request.recompute_cost):
        try:
            _recompute_and_persist_project_cost_estimation(db, int(episode.project_id))
        except Exception as cost_exc:
            logger.warning("batch_upsert_scenes cost recompute skipped | project_id=%s err=%s", episode.project_id, cost_exc)

    try:
        db.commit()
    except Exception as commit_exc:
        db.rollback()
        logger.error(
            "[SceneImportAPI] batch_upsert commit failed | episode_id=%s | project_id=%s | err=%s",
            episode_id,
            episode.project_id,
            commit_exc,
        )
        raise HTTPException(status_code=409, detail="SCENE_NO_UNIQUE_CONFLICT") from commit_exc

    result_scenes: List[Dict[str, Any]] = []
    unique_touched = list(dict.fromkeys([s for s in touched_scene_nos if s]))
    if unique_touched:
        refreshed = (
            db.query(Scene)
            .filter(
                Scene.episode_id == int(episode_id),
                Scene.scene_no.in_(unique_touched),
                _active_scene_clause(),
            )
            .all()
        )
        refreshed_by_no = {str(row.scene_no or "").strip(): row for row in refreshed}
        for scene_no in unique_touched:
            row = refreshed_by_no.get(scene_no)
            if row is None:
                continue
            result_scenes.append({
                "id": int(row.id),
                "scene_no": str(row.scene_no or ""),
                "scene_name": str(row.scene_name or ""),
            })

    elapsed_ms = int((time.perf_counter() - started_perf) * 1000)
    logger.info(
        "[SceneImportAPI] batch_upsert done | episode_id=%s | project_id=%s | processed=%s | created=%s | updated=%s | skipped=%s | elapsed_ms=%s",
        episode_id,
        episode.project_id,
        len(input_scenes),
        created,
        updated,
        skipped,
        elapsed_ms,
    )
    return {
        "status": "ok",
        "episode_id": int(episode_id),
        "project_id": int(episode.project_id),
        "processed": int(len(input_scenes)),
        "created": int(created),
        "updated": int(updated),
        "skipped": int(skipped),
        "elapsed_ms": elapsed_ms,
        "scenes": result_scenes,
    }

@router.put("/scenes/{scene_id}", response_model=SceneOut)
def update_scene(
    scene_id: int,
    scene_in: SceneCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not db_scene:
        raise HTTPException(status_code=404, detail="Scene not found")
        
    # Ownership
    episode = db.query(Episode).filter(Episode.id == db_scene.episode_id).first()
    _require_project_access(db, episode.project_id, current_user)

    update_data = scene_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_scene, field, value)
        
    db.add(db_scene)
    try:
        _recompute_and_persist_project_cost_estimation(db, int(episode.project_id))
    except Exception as cost_exc:
        logger.warning("update_scene cost recompute skipped | project_id=%s err=%s", episode.project_id, cost_exc)
    db.commit()
    db.refresh(db_scene)
    return db_scene


@router.post("/episodes/{episode_id}/scenes/purge", response_model=Dict[str, Any])
def purge_episode_scenes(
    episode_id: int,
    request: ScenePurgeRequest = ScenePurgeRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    episode = db.query(Episode).filter(Episode.id == int(episode_id), _active_episode_clause()).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")
    _require_project_access(db, episode.project_id, current_user, owner_only=True)

    deleted_scenes = _hard_purge_episode_scenes(db, int(episode_id))
    removed_progress = 0
    if bool(getattr(request, "clear_progress", True)):
        removed_progress = _purge_episode_scene_progress(
            db,
            project_id=int(episode.project_id),
            episode_id=int(episode_id),
        )

    try:
        _recompute_and_persist_project_cost_estimation(db, int(episode.project_id))
    except Exception as cost_exc:
        logger.warning("purge_episode_scenes cost recompute skipped | project_id=%s err=%s", episode.project_id, cost_exc)

    db.commit()
    return {
        "status": "ok",
        "episode_id": int(episode_id),
        "project_id": int(episode.project_id),
        "deleted_scenes": deleted_scenes,
        "removed_progress_units": removed_progress,
    }


@router.delete("/scenes/{scene_id}", status_code=200)
def delete_scene(
    scene_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_scene = db.query(Scene).filter(Scene.id == scene_id, _active_scene_clause()).first()
    if not db_scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    episode = db.query(Episode).filter(Episode.id == db_scene.episode_id, _active_episode_clause()).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    _require_project_access(db, episode.project_id, current_user, owner_only=True)

    if _is_soft_deleted(db_scene):
        return {"status": "deleted", "batch_id": None}

    now = now_bj_iso()
    scene_label = str(db_scene.scene_name or db_scene.scene_no or f"Scene {scene_id}")
    batch_id = _start_deletion_batch(
        db,
        user_id=current_user.id,
        project_id=int(episode.project_id),
        episode_id=int(episode.id),
        action_type="scene",
        label=scene_label,
    )
    _soft_delete_scenes(db, scene_id=scene_id, now=now, batch_id=batch_id)
    _finalize_deletion_batch(db, batch_id)
    try:
        _recompute_and_persist_project_cost_estimation(db, int(episode.project_id))
    except Exception as cost_exc:
        logger.warning("delete_scene cost recompute skipped | project_id=%s err=%s", episode.project_id, cost_exc)
    db.commit()
    return {"status": "deleted", "batch_id": batch_id}


@router.post("/scenes/{scene_id}/regenerate", response_model=Dict[str, Any])
async def regenerate_scene(
    scene_id: int,
    req: SceneRegenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    async_mode: str = Query("0"),
):
    if async_mode == "1":
        tid = _submit_async(regenerate_scene, user_id=current_user.id,
                            kind="regenerate_scene", scene_id=scene_id, req=req, async_mode="0")
        return JSONResponse({"task_id": tid, "async": True})
    db_scene = db.query(Scene).filter(Scene.id == scene_id).first()
    if not db_scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    episode = db.query(Episode).filter(Episode.id == db_scene.episode_id).first()
    if not episode:
        raise HTTPException(status_code=404, detail="Episode not found")

    project = _require_project_access(db, episode.project_id, current_user, owner_only=True)

    user_requirements = str(req.user_requirements or "").strip()
    if not user_requirements:
        raise HTTPException(status_code=400, detail="user_requirements is required")

    safe_max_scenes = max(1, min(int(req.max_scenes or 4), 8))
    entity_only_mode = bool(req.entity_only_mode)

    system_instruction = ""
    if req.system_prompt:
        system_instruction = str(req.system_prompt)
    else:
        prompt_filename = str(req.prompt_file or "scene_regenerate.txt").strip() or "scene_regenerate.txt"
        try:
            system_instruction = _resolve_prompt_text(prompt_filename)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"Prompt file '{prompt_filename}' not found.")

    project_global_info = project.global_info if isinstance(project.global_info, dict) else {}
    project_title_str = str(project.title or "")
    episode_title_str = str(episode.title or "")

    def _project_info_str(key: str) -> str:
        value = project_global_info.get(key)
        if value is None:
            return ""
        if isinstance(value, list):
            return ", ".join([str(v or "").strip() for v in value if str(v or "").strip()])
        return str(value or "").strip()

    project_context_lines = [
        f"Project Title: {project_title_str}",
        f"Episode Title: {episode_title_str}",
    ]
    for key, label in (
        ("script_title", "Script Title"),
        ("series_episode", "Series Episode"),
        ("type", "Type"),
        ("base_positioning", "Base Positioning"),
        ("language", "Language"),
        ("Global_Style", "Global Style"),
        ("tone", "Tone"),
        ("lighting", "Lighting"),
        ("borrowed_films", "Borrowed Films"),
    ):
        value = _project_info_str(key)
        if value:
            project_context_lines.append(f"{label}: {value}")

    project_context_block = "\n".join(project_context_lines)

    scene_subject_seed_lines = [
        f"Environment Name Seed: {str(db_scene.environment_name or '').strip() or '(empty)'}",
        f"Linked Characters Seed: {str(db_scene.linked_characters or '').strip() or '(empty)'}",
        f"Key Props Seed: {str(db_scene.key_props or '').strip() or '(empty)'}",
    ]
    scene_subject_seeds_block = "\n".join(scene_subject_seed_lines)
    original_script_grounding = str(db_scene.original_script_text or "").strip()
    original_script_grounding_block = original_script_grounding or "(empty)"

    if entity_only_mode:
        regen_injection = (
            "\n\n"
            "[Regeneration Mode Injection]\n"
            "You are in SCENE ENTITY SUPPLEMENT MODE for one existing scene row.\n"
            "Primary objective: supplement the missing entities required by this scene according to [User Requirements] with highest priority.\n"
            "You MUST use project context + existing subject inventory + current scene content + original script grounding together as the extraction and verification basis.\n"
            "You MUST use Original Script Text as the ground-truth reference to verify whether linked characters are missing, and whether core scene information has major omissions or obvious visual-guidance errors.\n"
            "You MAY ignore minor wording differences that do not materially affect story meaning, staging, or visual guidance.\n"
            "If Original Script Text reveals materially missing characters, core actions, location anchors, or visual-guidance facts, you MUST repair the current scene row patch in markdown instead of only patching entity fields.\n"
            "You MUST follow scene_analysis subject extraction principles: reuse existing subjects first, only add truly missing subjects, and keep naming stable.\n"
            "scene_analysis.txt is the final authority for all subject/entity prompt rules. scene_regenerate.txt must be interpreted to stay aligned with scene_analysis.txt, and if any runtime summary conflicts, scene_analysis.txt wins.\n"
            "You MUST follow the full Chinese subject-sync rules defined in scene_regenerate.txt; if any shorter runtime summary conflicts with those file rules, the file rules win.\n"
            "You MUST complete hidden required entities when an action physically depends on a source object, carrier, receiver, or container; for example, pouring implies a source container, and taking a tissue implies a tissue source container.\n"
            "You MUST keep concrete scene-visible object coverage explicit; do not collapse tables, cups, doors, windows, lamps, phones, keyboards, and similar visible objects into vague generic categories.\n"
            "You MUST NOT merge two readable outfits or two readable identity states into one character item; if two states are needed, output two separate character entities with dependency logic.\n"
            "You MUST apply clothing hint recognition: touching, adjusting, lifting, fastening, or straightening a distinctive garment/accessory counts as evidence that the corresponding outfit state already exists and may require a separate character entity.\n"
            "You MUST preserve project language rules from the prompt file: do not force dialogue, visible text, labels, or screen text into English unless the project language actually requires English.\n"
            "Character generation prompts must preserve full-body framing with shoes visible as the asset baseline.\n"
            "Environment generation prompts must remain clean-plate, no-human prompts: no over-shoulder wording, no shoulder silhouettes, no human reflections, no human shadows, no role labels, and no CHAR references inside environment prompts.\n"
            "Output must be import-first and parser-safe: do NOT output explanations, bullets, validation notes, or code fences.\n"
            "The final output must contain exactly 2 parts only: first exactly 1 markdown scene row patch table, then exactly 1 SUBJECTS_JSON object.\n"
            "SUBJECTS_JSON must be exactly one valid JSON object with top-level keys characters, props, environments, covers, and all keys must always exist even when empty.\n"
            "For each entity item, use only the field contract defined by scene_regenerate.txt and scene_analysis.txt; if an identifier is included, only subject_no may appear as an extra import field.\n"
            "Missing optional strings must use empty string, missing arrays must use empty array, and you must not output null, undefined, metadata wrappers, or parser-hint fields.\n"
            "Return exactly 1 scene row patch in markdown table format plus one SUBJECTS_JSON object for missing entities only.\n"
            "In entity-only mode, scene/shots are not replaced; the row patch may update scene_name / equivalent_duration / core_scene_info / original_script_text / environment_name / linked_characters / key_props when needed to reflect corrected scene grounding and supplemented entities."
        )
    else:
        regen_injection = (
            "\n\n"
            "[Regeneration Mode Injection]\n"
            "You are in FULL SCENE REGENERATION MODE for one existing scene row.\n"
            "Primary objective: regenerate the scene according to [User Requirements] while also supplementing any newly required entities.\n"
            "You MUST use project context + existing subject inventory + current scene content + original script grounding together as the generation basis.\n"
            "You MUST use Original Script Text as the ground-truth reference to verify whether linked characters are missing, and whether core scene information has major omissions or obvious visual-guidance errors.\n"
            "You MAY ignore minor wording differences that do not materially affect story meaning, staging, or visual guidance.\n"
            "You MUST follow scene_analysis subject extraction principles: reuse existing subjects first, only add truly missing subjects, and keep naming stable.\n"
            "scene_analysis.txt is the final authority for all subject/entity prompt rules. scene_regenerate.txt must be interpreted to stay aligned with scene_analysis.txt, and if any runtime summary conflicts, scene_analysis.txt wins.\n"
            "You MUST follow the full Chinese subject-sync rules defined in scene_regenerate.txt; if any shorter runtime summary conflicts with those file rules, the file rules win.\n"
            "You MUST complete hidden required entities when an action physically depends on a source object, carrier, receiver, or container; for example, pouring implies a source container, and taking a tissue implies a tissue source container.\n"
            "You MUST keep concrete scene-visible object coverage explicit; do not collapse tables, cups, doors, windows, lamps, phones, keyboards, and similar visible objects into vague generic categories.\n"
            "You MUST NOT merge two readable outfits or two readable identity states into one character item; if two states are needed, output two separate character entities with dependency logic.\n"
            "You MUST apply clothing hint recognition: touching, adjusting, lifting, fastening, or straightening a distinctive garment/accessory counts as evidence that the corresponding outfit state already exists and may require a separate character entity.\n"
            "You MUST preserve project language rules from the prompt file: do not force dialogue, visible text, labels, or screen text into English unless the project language actually requires English.\n"
            "Character generation prompts must preserve full-body framing with shoes visible as the asset baseline.\n"
            "Environment generation prompts must remain clean-plate, no-human prompts: no over-shoulder wording, no shoulder silhouettes, no human reflections, no human shadows, no role labels, and no CHAR references inside environment prompts.\n"
            "Output must be import-first and parser-safe: do NOT output explanations, bullets, validation notes, or code fences.\n"
            "The final output must contain exactly 2 parts only: markdown scene row patch table(s) first, then exactly 1 SUBJECTS_JSON object.\n"
            "SUBJECTS_JSON must be exactly one valid JSON object with top-level keys characters, props, environments, covers, and all keys must always exist even when empty.\n"
            "For each entity item, use only the field contract defined by scene_regenerate.txt and scene_analysis.txt; if an identifier is included, only subject_no may appear as an extra import field.\n"
            "Missing optional strings must use empty string, missing arrays must use empty array, and you must not output null, undefined, metadata wrappers, or parser-hint fields.\n"
            f"Return 1 to {safe_max_scenes} regenerated scene rows in markdown table format plus one SUBJECTS_JSON object for missing entities only."
        )
    system_instruction = f"{system_instruction}{regen_injection}"

    scene_snapshot = (
        f"| Episode ID | Scene ID | Scene No. | Scene Name | Equivalent Duration | Core Scene Info | Original Script Text | Environment Name | Linked Characters | Key Props |\n"
        f"| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
        f"| EP{int(episode.id):02d} | EP{int(episode.id):02d}_SCXX | {db_scene.scene_no or ''} | {db_scene.scene_name or ''} | {db_scene.equivalent_duration or ''} | {(db_scene.core_scene_info or '').replace(chr(10), '<br>')} | {(db_scene.original_script_text or '').replace(chr(10), '<br>')} | {db_scene.environment_name or ''} | {db_scene.linked_characters or ''} | {db_scene.key_props or ''} |"
    )

    existing_subject_inventory = _build_project_subject_inventory(
        db,
        int(project.id),
        episode_id=int(episode.id),
    )
    existing_subjects_block = _format_project_subject_inventory_block(existing_subject_inventory)

    existing_subjects_system_guard = (
        "\n\n"
        "[Existing Entity Reuse Guard - High Priority]\n"
        "The following entities already exist in the current episode scope and are dependency baselines.\n"
        "You MUST treat them as immutable references: do NOT rewrite, rename, redefine, or replace these entities.\n"
        "Do NOT output them as newly generated entities in SUBJECTS_JSON.\n"
        "SUBJECTS_JSON must include only truly missing entities.\n"
        f"{existing_subjects_block}"
    )
    system_instruction = f"{system_instruction}{existing_subjects_system_guard}"

    logger.info(
        "[regenerate_scene] entity injection scene_id=%s project_id=%s counts: characters=%s props=%s environments=%s covers=%s",
        scene_id,
        project.id,
        len(existing_subject_inventory.get("characters") or []),
        len(existing_subject_inventory.get("props") or []),
        len(existing_subject_inventory.get("environments") or []),
    )

    mode_specific_task_lines = (
        "- This task is mainly for supplementing missing entities of the current scene, not rewriting the whole scene.\n"
        "- However, you MUST also use Original Script Text to verify missing characters and major core scene info / visual-guidance omissions or obvious errors.\n"
        "- If such omissions or obvious errors exist, repair them in the single current-scene row patch markdown while keeping the scene identity stable.\n"
        "- Return a single current-scene row patch only; do not split into multiple rows in entity supplement mode.\n"
    ) if entity_only_mode else (
        f"- Regenerate this scene into 1 to {safe_max_scenes} scene rows when needed by user requirements.\n"
        "- Use Original Script Text to verify missing characters and major core scene info / visual-guidance omissions or obvious errors before finalizing the regenerated row(s).\n"
        "- Supplement any newly required entities at the same time.\n"
    )

    mode_specific_output_line = (
        "1) One scene markdown table row patch for the current scene (importable by scene parser).\n"
        if entity_only_mode else
        "1) Scene markdown table rows (importable by scene parser).\n"
    )

    current_scene_section = wrap_injection_section(
        "当前场景",
        "Current Scene (Markdown Row):\n" + scene_snapshot,
    )
    original_script_section = wrap_injection_section(
        "原始剧本依据",
        "[Original Script Grounding]\n" + original_script_grounding_block,
    )
    scene_subject_seeds_section = wrap_injection_section(
        "场景Subject种子",
        "[Current Scene Subject Seeds]\n" + scene_subject_seeds_block,
    )
    user_supplement_section = wrap_injection_section(
        "用户补充要求",
        "[User Supplement Requirements]\n" + user_requirements,
    )

    user_prompt = (
        f"{wrap_injection_section('项目信息', project_context_block)}\n\n"
        f"Source Scene Database ID: {db_scene.id}\n\n"
        f"{current_scene_section}\n\n"
        f"{original_script_section}\n\n"
        f"{scene_subject_seeds_section}\n\n"
        f"{existing_subjects_block}\n\n"
        f"{user_supplement_section}\n\n"
        "Task Instructions:\n"
        "- Use Project Context + Current Scene + Original Script Grounding + Current Scene Subject Seeds + System-level Subjects Inventory together.\n"
        "- Original Script Grounding is the primary truth source for checking whether the current scene is missing characters, missing key actions, missing location anchors, or has major core scene info / visual-guidance errors.\n"
        "- You may ignore minor wording differences that do not affect plot understanding or visual staging.\n"
        "- Follow scene_analysis extraction principles for characters / props / environments / covers.\n"
        "- scene_analysis.txt is the final authority for subject/entity prompt rules; interpret scene_regenerate.txt and runtime instructions so they stay aligned with scene_analysis.txt.\n"
        "- Follow the full Chinese subject-sync rules in scene_regenerate.txt; if this runtime summary is shorter, the file rules still apply in full.\n"
        "- Prioritize User Supplement Requirements over the old scene wording when deciding what is missing.\n"
        f"{mode_specific_task_lines}"
        "- Treat System-level Subjects Inventory as authoritative dependency baselines already available in project DB.\n"
        "- Existing entities are immutable references: MUST NOT be rewritten, renamed, redefined, or replaced.\n"
        "- Reuse subject_ref tokens and keep anchor semantics consistent for recognition continuity.\n"
        "- They can be referenced/reused directly, but MUST NOT be regenerated as new entities.\n"
        "- MUST supplement complete missing subjects required by the current scene from scene content + user requirements, and return JSON with keys: characters, props, environments, covers.\n"
        "- Subject extraction MUST NOT depend on whether the subject already has an image or image_url. Even subjects with no image asset yet MUST still be extracted and returned when they are required by the scene.\n"
        "- Every returned subject item must include import-usable names and description: name + name_en + description_cn are mandatory content fields. Missing image assets are allowed; missing names/descriptions are not.\n"
        "- Hidden required entities must be completed when the action semantics require them; do not omit source containers, receivers, or scene-required support objects merely because they were implicit in the text.\n"
        "- Keep scene-visible concrete object coverage explicit; if a table, cup, door, window, lamp, phone, keyboard, or similar object matters to the scene, account for it specifically rather than replacing it with a vague category label.\n"
        "- Never combine two readable wardrobe or identity states into one character JSON item.\n"
        "- Clothing hint recognition is mandatory: touching, adjusting, lifting, fastening, or straightening a distinctive garment/accessory counts as evidence for that outfit state and may require a separate character entity.\n"
        "- Preserve the project language rules from the prompt file; do not convert visible language content to English unless the project language actually requires English.\n"
        "- Character prompts must remain full-body with shoes visible.\n"
        "- Environment prompts must stay no-human and clean-plate: no OTS shoulder wording, no human residue, no role labels, and no CHAR references.\n"
        "- SUBJECTS_JSON must contain ONLY missing/new entities that are not already listed in System-level Subjects Inventory.\n"
        "- Keep existing subject names stable; do not duplicate existing names in SUBJECTS_JSON.\n"
        "- If no missing entity exists for a category, return an empty array for that category.\n\n"
        "- Output must be parser-safe and directly importable: no explanations, no bullets outside the requested structure, no code fences, no metadata wrapper objects.\n"
        "- SUBJECTS_JSON top-level keys must be exactly characters, props, environments, covers, and all keys must always exist.\n"
        "- Each entity item may use only the prompt-defined import fields; if an identifier is included, only subject_no may be added as an extra import field.\n"
        "- Missing optional strings must use empty string, missing arrays must use empty array, and null/undefined are forbidden.\n\n"
        "Required Output Format:\n"
        f"{mode_specific_output_line}"
        "2) SUBJECTS_JSON: one valid JSON object only, with complete import-ready fields (same semantics as system subjects import):\n"
        "{\n"
        "  \"characters\": [{\"name\": \"...\", \"name_en\": \"...\", \"description_cn\": \"...\", \"gender\": \"...\", \"role\": \"...\", \"archetype\": \"...\", \"appearance_cn\": \"...\", \"clothing\": \"...\", \"action_characteristics\": \"...\", \"generation_prompt_cn\": \"...\", \"generation_prompt_en\": \"...\", \"negative_prompt_en\": \"...\", \"anchor_description\": \"...\", \"visual_dependencies\": [], \"dependency_strategy\": {\"type\": \"...\", \"logic\": \"...\"}}],\n"
        "  \"props\": [{\"name\": \"...\", \"name_en\": \"...\", \"description_cn\": \"...\", \"generation_prompt_cn\": \"...\", \"generation_prompt_en\": \"...\", \"negative_prompt_en\": \"...\", \"anchor_description\": \"...\", \"visual_dependencies\": [], \"dependency_strategy\": {\"type\": \"...\", \"logic\": \"...\"}}],\n"
        "  \"environments\": [{\"name\": \"...\", \"name_en\": \"...\", \"atmosphere\": \"...\", \"visual_params\": \"...\", \"description_cn\": \"...\", \"generation_prompt_cn\": \"...\", \"generation_prompt_en\": \"...\", \"negative_prompt_en\": \"...\", \"anchor_description\": \"...\", \"visual_dependencies\": [], \"dependency_strategy\": {\"type\": \"...\", \"logic\": \"...\"}}]\n"
        "}\n"
        "Image/image_url fields are NOT required for extraction and may be omitted. Name and description fields are mandatory for each entity item. Missing other optional fields should use empty string / empty array / empty object.\n"
        "No prose outside these two parts."
    )

    logger.info(
        "[regenerate_scene] prompt injection markers scene_id=%s has_existing_block_in_user_prompt=%s has_existing_guard_in_system_prompt=%s",
        scene_id,
        "System-level Subjects Inventory" in user_prompt,
        "[Existing Entity Reuse Guard - High Priority]" in system_instruction,
    )

    current_user_id = current_user.id
    episode_id = episode.id
    project_id = project.id

    old_scene_no = str(db_scene.scene_no or db_scene.id)
    fallback_original_script = str(db_scene.original_script_text or "").strip()
    fallback_scene_name = db_scene.scene_name
    fallback_duration = db_scene.equivalent_duration
    fallback_core_info = db_scene.core_scene_info
    fallback_env_name = db_scene.environment_name
    fallback_linked_chars = db_scene.linked_characters
    fallback_key_props = db_scene.key_props

    llm_config = agent_service.get_active_llm_config(current_user_id)
    llm_config = _inject_project_creativity_temperature(
        llm_config,
        project.global_info,
        context="regenerate_scene",
    )
    provider = llm_config.get("provider") if llm_config else None
    model = llm_config.get("model") if llm_config else None
    billing_service.check_balance(db, current_user_id, "llm_chat", provider, model)

    _release_db_connection(db, "regenerate_scene_llm_call")
    resp = await llm_service.generate_content_with_fallback(user_prompt, system_instruction, llm_config)
    raw = str((resp or {}).get("content") or "").strip()
    if not raw:
        raise HTTPException(status_code=502, detail="LLM returned empty content")

    cleaned = sanitize_llm_markdown_output(raw)
    parsed_rows = _parse_scene_rows_from_markdown(cleaned)
    if not parsed_rows and not entity_only_mode:
        raise HTTPException(status_code=502, detail="Failed to parse regenerated scene markdown table")

    subjects_json = _extract_subjects_json_from_text(raw)
    if not any(len(subjects_json.get(k) or []) > 0 for k in ("characters", "props", "environments", "covers", "posters")):
        subjects_json = _extract_subjects_json_from_text(cleaned)

    parsed_rows = parsed_rows[:safe_max_scenes]

    created_scenes: List[Scene] = []
    try:
        if entity_only_mode:
            preferred_row = parsed_rows[0] if parsed_rows else {}
            if not isinstance(preferred_row, dict):
                preferred_row = {}

            db_scene = db.query(Scene).filter(Scene.id == scene_id).first()
            if db_scene:
                db_scene.scene_name = str(preferred_row.get("scene_name") or "").strip() or fallback_scene_name
                db_scene.original_script_text = str(preferred_row.get("original_script_text") or "").strip() or fallback_original_script
                db_scene.equivalent_duration = str(preferred_row.get("equivalent_duration") or "").strip() or fallback_duration
                db_scene.core_scene_info = str(preferred_row.get("core_scene_info") or "").strip() or fallback_core_info
                db_scene.environment_name = str(preferred_row.get("environment_name") or "").strip() or fallback_env_name
                db_scene.linked_characters = str(preferred_row.get("linked_characters") or "").strip() or fallback_linked_chars
                db_scene.key_props = str(preferred_row.get("key_props") or "").strip() or fallback_key_props
    
                db.add(db_scene)
                db.commit()
                created_scenes = [db_scene]
        else:
            _soft_delete_scenes(db, scene_id=scene_id)

            total_new = len(parsed_rows)
            for idx, row in enumerate(parsed_rows, start=1):
                if total_new > 1:
                    next_scene_no = f"{old_scene_no}.{idx}"
                else:
                    next_scene_no = str(row.get("scene_no") or "").strip() or old_scene_no

                original_script_text = str(row.get("original_script_text") or "").strip() or fallback_original_script
                if not original_script_text:
                    original_script_text = f"Scene regenerated from {old_scene_no}"

                new_scene = Scene(
                    episode_id=episode_id,
                    scene_no=next_scene_no,
                    scene_name=str(row.get("scene_name") or "").strip() or fallback_scene_name,
                    original_script_text=original_script_text,
                    equivalent_duration=str(row.get("equivalent_duration") or "").strip() or fallback_duration,
                    core_scene_info=str(row.get("core_scene_info") or "").strip() or fallback_core_info,
                    environment_name=str(row.get("environment_name") or "").strip() or fallback_env_name,
                    linked_characters=str(row.get("linked_characters") or "").strip() or fallback_linked_chars,
                    key_props=str(row.get("key_props") or "").strip() or fallback_key_props,
                )
                db.add(new_scene)
                created_scenes.append(new_scene)

            db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to replace scene: {str(e)}")

    for item in created_scenes:
        db.refresh(item)

    usage = (resp or {}).get("usage") if isinstance(resp, dict) else None
    details: Dict[str, Any] = {
        "item": "scene_regenerate",
        "source_scene_id": scene_id,
        "generated_scene_count": len(created_scenes),
    }
    if isinstance(usage, dict):
        details.update(usage)
        if "prompt_tokens" in details and "input_tokens" not in details:
            details["input_tokens"] = details.get("prompt_tokens", 0)
        if "completion_tokens" in details and "output_tokens" not in details:
            details["output_tokens"] = details.get("completion_tokens", 0)
    billing_service.deduct_credits(db, current_user_id, "llm_chat", provider, model, details)

    return {
        "replaced_scene_id": scene_id,
        "episode_id": episode_id,
        "project_id": project_id,
        "entity_only_mode": entity_only_mode,
        "scene_changes_applied": not entity_only_mode,
        "generated_scene_count": len(created_scenes),
        "raw_markdown": cleaned,
        "subjects_json": subjects_json,
        "subjects_json_count": {
            "characters": len(subjects_json.get("characters") or []),
            "props": len(subjects_json.get("props") or []),
            "environments": len(subjects_json.get("environments") or []),
            "covers": len(subjects_json.get("covers") or []),
            "posters": len(subjects_json.get("posters") or []),
        },
        "scenes": [
            {
                "id": s.id,
                "scene_no": s.scene_no,
                "scene_name": s.scene_name,
                "equivalent_duration": s.equivalent_duration,
                "core_scene_info": s.core_scene_info,
                "original_script_text": s.original_script_text,
                "environment_name": s.environment_name,
                "linked_characters": s.linked_characters,
                "key_props": s.key_props,
            }
            for s in created_scenes
        ],
    }

