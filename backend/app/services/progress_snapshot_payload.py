# -*- coding: utf-8 -*-
"""Progress snapshots stay small. Node edit drafts load on click."""
from __future__ import annotations

import re
from typing import Any, Dict

_SCENE_NAME_RE = re.compile(r"【\s*场景名称\s*】\s*([^\r\n]+)")
_STAGING_MARK_RE = re.compile(r"【\s*建置\s*】")
_ACTION_MARK_RE = re.compile(r"【\s*入戏\s*】")
_EDIT_BODY_META_KEYS = ("scene_block",)


def scene_name_from_text(text: Any) -> str:
    match = _SCENE_NAME_RE.search(str(text or ""))
    if not match:
        return ""
    return str(match.group(1) or "").strip()[:80]


def text_has_derived_env_signals(text: Any) -> bool:
    src = str(text or "")
    return (
        "[DERIVED_ENV" in src.upper()
        or "【本场衍生环境名】" in src
        or "────【衍生环境】────" in src
    )


def staging_import_ready(scene_block: Any, called: Any) -> bool:
    text = str(scene_block or "")
    if not _STAGING_MARK_RE.search(text) or not _ACTION_MARK_RE.search(text):
        return False
    called_list = [str(item or "").strip() for item in called] if isinstance(called, list) else []
    if called_list and "staging" not in called_list:
        return False
    return True


def slim_runtime_meta(meta: Any, *, node_name: Any = "", status: Any = "") -> Dict[str, Any]:
    """Drop the scene manuscript. Keep the flags the matrix needs before a click."""
    source = dict(meta) if isinstance(meta, dict) else {}
    block = str(source.get("scene_block") or "")
    slim = {key: value for key, value in source.items() if key not in _EDIT_BODY_META_KEYS}
    slim["has_scene_block"] = bool(block.strip())
    if not block.strip():
        return slim
    slim["scene_block_chars"] = len(block)
    if text_has_derived_env_signals(block):
        slim["has_derived_env_signals"] = True
    name = scene_name_from_text(block)
    if name and not str(slim.get("scene_name") or "").strip():
        slim["scene_name"] = name
    if (
        str(node_name or "").strip() == "scene_subskill_scene"
        and str(status or "").strip().lower() == "success"
        and staging_import_ready(block, source.get("called_subskills"))
    ):
        slim["has_staging_import_body"] = True
    return slim


def slim_scene_unit(unit: Any) -> Dict[str, Any]:
    row = dict(unit) if isinstance(unit, dict) else {}
    markdown = str(row.pop("scene_markdown", "") or "")
    row["has_scene_markdown"] = bool(markdown.strip())
    if not markdown.strip():
        return row
    row["scene_markdown_chars"] = len(markdown)
    name = scene_name_from_text(markdown)
    if name and not str(row.get("scene_name") or "").strip():
        row["scene_name"] = name
    return row
