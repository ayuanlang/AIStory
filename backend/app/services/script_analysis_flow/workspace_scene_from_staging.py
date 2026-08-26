# -*- coding: utf-8 -*-
"""Build workspace Scene rows from staging LLM output (no Stage 2.2 node)."""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.services.scene_no_utils import _canonicalize_scene_no, _find_active_scene_by_scene_no
from app.services.script_analysis_flow.derived_env_ingest import (
    extract_derived_environment_names_from_scene_text,
)
from app.services.script_analysis_flow.scene_cast import (
    extract_legacy_scene_cast_lines,
    extract_scene_cast_block,
    scene_cast_token_names,
)

logger = logging.getLogger("api_logger")

SCENE_TABLE_HEADERS = [
    "Episode ID",
    "Scene ID",
    "Scene No.",
    "Scene Name",
    "Equivalent Duration",
    "Core Scene Info",
    "Adapted Script Excerpt",
    "Environment Name",
    "Environment Relation",
    "Base Environment Reference",
    "Environment Delta",
    "Entry State",
    "Exit State",
    "Linked Characters",
    "Key Props",
]

_CHAR_TOKEN_PATTERN = re.compile(r"CHAR\s*:\s*\[@([^\[\]]+)\]", re.IGNORECASE)
_PROP_TOKEN_PATTERN = re.compile(r"PROP\s*:\s*\[([^\[\]]+)\]", re.IGNORECASE)
_PLOT_STAGE_PATTERN = re.compile(r"(闪回|倒叙|梦境|想象|正常叙事)")
_EPISODE_ID_PATTERN = re.compile(r"^(EP\d+)", re.IGNORECASE)


def _clean(value: object) -> str:
    return str(value or "").strip()


def _join_unique(values: List[str]) -> str:
    seen = set()
    out: List[str] = []
    for raw in values:
        text = _clean(raw)
        if not text or text in {"无", "None", "none", "N/A"}:
            continue
        if text in seen:
            continue
        seen.add(text)
        out.append(text)
    return "，".join(out)


def _sanitize_cell(value: object, *, scene_name: bool = False) -> str:
    text = _clean(value).replace("\r\n", "<br>").replace("\r", "<br>").replace("\n", "<br>")
    replacement = "·" if scene_name else "／"
    return text.replace("\\|", replacement).replace("|", replacement).replace("｜", replacement)


def infer_plot_stage(scene_text: str) -> str:
    match = _PLOT_STAGE_PATTERN.search(str(scene_text or ""))
    return match.group(1) if match else "正常叙事"


def infer_episode_id(scene_id: str) -> str:
    match = _EPISODE_ID_PATTERN.match(_clean(scene_id))
    if match:
        return match.group(1).upper()
    return "EP01"


def collect_character_tokens(scene_id: str, scene_text: str) -> List[str]:
    names: List[str] = []
    seen = set()

    def _add(name: str) -> None:
        cleaned = _clean(name)
        if not cleaned or cleaned in seen:
            return
        seen.add(cleaned)
        names.append(cleaned)

    cast = extract_scene_cast_block(scene_text, scene_id) or extract_legacy_scene_cast_lines(scene_text)
    for name in scene_cast_token_names(cast).get("characters") or []:
        _add(name)
    for match in _CHAR_TOKEN_PATTERN.finditer(str(scene_text or "")):
        _add(match.group(1))
    return names


def collect_prop_tokens(scene_id: str, scene_text: str) -> List[str]:
    names: List[str] = []
    seen = set()

    def _add(name: str) -> None:
        cleaned = _clean(name)
        if not cleaned or cleaned in seen:
            return
        seen.add(cleaned)
        names.append(cleaned)

    cast = extract_scene_cast_block(scene_text, scene_id) or extract_legacy_scene_cast_lines(scene_text)
    for name in scene_cast_token_names(cast).get("props") or []:
        _add(name)
    for match in _PROP_TOKEN_PATTERN.finditer(str(scene_text or "")):
        _add(match.group(1))
    return names


def _format_char_list(names: List[str]) -> str:
    return _join_unique([f"CHAR:[@{name}]" for name in names])


def _format_prop_list(names: List[str]) -> str:
    return _join_unique([f"PROP:[{name}]" for name in names])


def _format_env_list(names_csv: str) -> str:
    names = [part.strip() for part in re.split(r"[,，;；、]+", str(names_csv or "")) if part.strip()]
    return _join_unique([f"ENV:[{name}]" for name in names])


def _beat_excerpt(beats_text: str, limit: int = 80) -> str:
    from app.services.script_analysis_flow import strip_beat_transition_notes_from_script

    cleaned = strip_beat_transition_notes_from_script(beats_text)
    cleaned = re.sub(r"`?\[BEAT_(?:START|END)(?::[^\]]+)?\]`?", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return ""
    return cleaned[:limit]


def build_workspace_scene_payload_from_staging(
    *,
    scene_id: str,
    scene_order: Optional[int] = None,
    staging_text: str,
) -> Dict[str, Any]:
    from app.services.script_analysis_flow import (
        extract_beat_blocks_from_scene_text,
        extract_scene_name_value_from_scene_text,
        strip_beat_transition_notes_from_script,
    )

    scene_id_text = _clean(scene_id)
    source = _clean(staging_text)
    scene_no = _canonicalize_scene_no(scene_order, scene_id=scene_id_text) or (
        str(int(scene_order)) if scene_order else ""
    )
    scene_name = extract_scene_name_value_from_scene_text(source)
    beats = strip_beat_transition_notes_from_script(extract_beat_blocks_from_scene_text(source))
    derived_envs = extract_derived_environment_names_from_scene_text(source)
    char_names = collect_character_tokens(scene_id_text, source)
    prop_names = collect_prop_tokens(scene_id_text, source)
    appearing = _join_unique(
        [
            _format_char_list(char_names),
            _format_env_list(derived_envs),
            _format_prop_list(prop_names),
        ]
    )
    plot_stage = infer_plot_stage(scene_name or source)
    core_scene_info = (
        f"- **{{剧情阶段}}**: {plot_stage}\n"
        f"- **{{Beats}}**:\n{beats}\n"
        f"- **{{登场实体}}**: {appearing or 'None'}"
    ).strip()
    return {
        "scene_id": scene_id_text,
        "episode_id_label": infer_episode_id(scene_id_text),
        "scene_no": scene_no,
        "scene_name": scene_name or None,
        "original_script_text": _beat_excerpt(beats),
        "equivalent_duration": None,
        "core_scene_info": core_scene_info or None,
        "environment_name": derived_envs or None,
        "linked_characters": _format_char_list(char_names) or None,
        "key_props": _format_prop_list(prop_names) or None,
    }


def build_scene_table_markdown_from_staging(
    *,
    scene_id: str,
    scene_order: Optional[int] = None,
    staging_text: str,
    payload: Optional[Dict[str, Any]] = None,
) -> str:
    row = payload or build_workspace_scene_payload_from_staging(
        scene_id=scene_id,
        scene_order=scene_order,
        staging_text=staging_text,
    )
    cells = [
        _sanitize_cell(row.get("episode_id_label")),
        _sanitize_cell(row.get("scene_id") or scene_id),
        _sanitize_cell(row.get("scene_no") or scene_order or ""),
        _sanitize_cell(row.get("scene_name") or "None", scene_name=True),
        _sanitize_cell(row.get("equivalent_duration") or "None"),
        _sanitize_cell(row.get("core_scene_info")),
        _sanitize_cell(row.get("original_script_text") or "None"),
        _sanitize_cell(row.get("environment_name") or "无"),
        "None",
        "None",
        "None",
        "None",
        "None",
        _sanitize_cell(row.get("linked_characters") or "None"),
        _sanitize_cell(row.get("key_props") or "None"),
    ]
    header_line = "| " + " | ".join(SCENE_TABLE_HEADERS) + " |"
    separator_line = "| " + " | ".join(":---" for _ in SCENE_TABLE_HEADERS) + " |"
    row_line = "| " + " | ".join(cells) + " |"
    title = _sanitize_cell(row.get("scene_name") or scene_id or "Scene", scene_name=True)
    return f"### Part 1: Scenes Table\n\n#### {title}\n\n{header_line}\n{separator_line}\n{row_line}".strip()


def upsert_workspace_scene_from_staging(
    db: Session,
    *,
    episode_id: int,
    scene_id: str,
    staging_text: str,
    scene_order: Optional[int] = None,
) -> Dict[str, Any]:
    from app.models.all_models import Scene

    payload = build_workspace_scene_payload_from_staging(
        scene_id=scene_id,
        scene_order=scene_order,
        staging_text=staging_text,
    )
    scene_no = _clean(payload.get("scene_no"))
    if not scene_no:
        return {"ok": False, "reason": "scene_no_required", "created": 0, "updated": 0}

    existing = _find_active_scene_by_scene_no(
        db,
        episode_id=int(episode_id),
        scene_no=scene_no,
        scene_id=scene_id,
    )
    fields = {
        "scene_no": scene_no,
        "scene_name": payload.get("scene_name"),
        "original_script_text": payload.get("original_script_text") or "",
        "equivalent_duration": payload.get("equivalent_duration"),
        "core_scene_info": payload.get("core_scene_info"),
        "environment_name": payload.get("environment_name"),
        "linked_characters": payload.get("linked_characters"),
        "key_props": payload.get("key_props"),
    }
    markdown = build_scene_table_markdown_from_staging(
        scene_id=scene_id,
        scene_order=scene_order,
        staging_text=staging_text,
        payload=payload,
    )
    if existing is not None:
        for key, value in fields.items():
            setattr(existing, key, value)
        db.add(existing)
        return {
            "ok": True,
            "reason": "updated",
            "created": 0,
            "updated": 1,
            "scene_no": scene_no,
            "workspace_scene_id": int(getattr(existing, "id", 0) or 0) or None,
            "markdown": markdown,
        }

    scene = Scene(episode_id=int(episode_id), **fields)
    db.add(scene)
    db.flush()
    return {
        "ok": True,
        "reason": "created",
        "created": 1,
        "updated": 0,
        "scene_no": scene_no,
        "workspace_scene_id": int(getattr(scene, "id", 0) or 0) or None,
        "markdown": markdown,
    }


def collect_staging_import_result(
    *,
    scene_id: str,
    scene_order: Optional[int],
    staging_text: str,
    upsert_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    markdown = str((upsert_result or {}).get("markdown") or "").strip()
    if not markdown:
        markdown = build_scene_table_markdown_from_staging(
            scene_id=scene_id,
            scene_order=scene_order,
            staging_text=staging_text,
        )
    return {
        "scene_id": scene_id,
        "scene_order": scene_order,
        "markdown": markdown,
        "workspace_import": upsert_result or {},
    }
