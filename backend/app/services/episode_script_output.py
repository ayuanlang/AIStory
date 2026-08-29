# -*- coding: utf-8 -*-
"""Cut official episode-script deliverable away from analysis / thinking."""
from __future__ import annotations

import re
from typing import Any, Dict

EPISODE_SCRIPT_THINKING_START = "[EPISODE_SCRIPT_THINKING_START]"
EPISODE_SCRIPT_THINKING_END = "[EPISODE_SCRIPT_THINKING_END]"
EPISODE_SCRIPT_OUTPUT_START = "[EPISODE_SCRIPT_OUTPUT_START]"
EPISODE_SCRIPT_OUTPUT_END = "[EPISODE_SCRIPT_OUTPUT_END]"


def _marker_re(kind: str, edge: str) -> re.Pattern[str]:
    return re.compile(rf"\[\s*EPISODE_SCRIPT_{kind}_{edge}\s*\]", flags=re.IGNORECASE)


def extract_episode_script_output_between_markers(text: str) -> Dict[str, Any]:
    """If both OUTPUT_START and OUTPUT_END exist, return the longest inner slice."""
    source = str(text or "")
    start_re = _marker_re("OUTPUT", "START")
    end_re = _marker_re("OUTPUT", "END")
    has_start = bool(start_re.search(source))
    has_end = bool(end_re.search(source))
    if not (has_start and has_end):
        return {
            "found": False,
            "content": "",
            "has_start": has_start,
            "has_end": has_end,
        }

    best_inner = ""
    best_len = -1
    pos = 0
    while True:
        start_match = start_re.search(source, pos)
        if not start_match:
            break
        end_match = end_re.search(source, start_match.end())
        if not end_match:
            break
        inner = source[start_match.end() : end_match.start()].strip()
        if len(inner) > best_len:
            best_len = len(inner)
            best_inner = inner
        pos = end_match.end()

    return {
        "found": best_len >= 0,
        "content": best_inner,
        "has_start": True,
        "has_end": True,
    }


def strip_episode_script_thinking_blocks(text: str) -> str:
    source = str(text or "")
    if not source:
        return ""
    pattern = re.compile(
        r"\[\s*EPISODE_SCRIPT_THINKING_START\s*\][\s\S]*?\[\s*EPISODE_SCRIPT_THINKING_END\s*\]",
        flags=re.IGNORECASE,
    )
    cleaned = pattern.sub("", source)
    orphan = re.search(r"\[\s*EPISODE_SCRIPT_THINKING_START\s*\]", cleaned, flags=re.IGNORECASE)
    if orphan:
        next_output = re.search(
            r"\[\s*EPISODE_SCRIPT_OUTPUT_START\s*\]",
            cleaned[orphan.start() :],
            flags=re.IGNORECASE,
        )
        if next_output:
            cut_at = orphan.start() + next_output.start()
            cleaned = cleaned[: orphan.start()] + cleaned[cut_at:]
        else:
            cleaned = cleaned[: orphan.start()] + cleaned[orphan.end() :]
    cleaned = _marker_re("OUTPUT", "START").sub("", cleaned)
    cleaned = _marker_re("OUTPUT", "END").sub("", cleaned)
    cleaned = _marker_re("THINKING", "END").sub("", cleaned)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def _strip_legacy_analysis_sections(text: str) -> str:
    """Drop 类型执行摘要 / 剧情连贯自检 from unmarked legacy drafts."""
    source = str(text or "").strip()
    if not source:
        return ""

    source = re.sub(
        r"(?ms)^(?:#{1,6}\s*)?-?1\)\s*类型执行摘要\b[\s\S]*?(?=^(?:#{1,6}\s*)?(?:核心内容纲要|本集卖点|娱乐化段子|场景列表|剧情一句话)|\[SCENES_BLOCK_START\]|\[EPISODE_SCRIPT_OUTPUT_START\])",
        "",
        source,
    )
    source = re.sub(
        r"(?ms)^(?:#{1,6}\s*)?类型执行摘要\b[\s\S]*?(?=^(?:#{1,6}\s*)?(?:核心内容纲要|本集卖点|娱乐化段子|场景列表|剧情一句话)|\[SCENES_BLOCK_START\])",
        "",
        source,
    )
    source = re.sub(
        r"(?ms)^(?:#{1,6}\s*)?剧情连贯自检\b[\s\S]*?(?=^(?:#{1,6}\s*)?(?:剧情一句话|结尾钩子)|\[EMERGENCY_RECOVERY_BLOCK_START\]|\[BRIDGE_BLOCK_START\]|\Z)",
        "",
        source,
    )
    return re.sub(r"\n{3,}", "\n\n", source).strip()


def extract_official_episode_script(text: str) -> str:
    """Return the official script body for display / persist / heading parse.

    Prefer `[EPISODE_SCRIPT_OUTPUT_START]…[EPISODE_SCRIPT_OUTPUT_END]`.
    Fall back to stripping thinking + legacy analysis sections so title,
    核心内容纲要, 卖点, scenes, logline, and hooks stay intact.
    """
    source = str(text or "")
    if not source.strip():
        return ""

    marked = extract_episode_script_output_between_markers(source)
    if marked.get("found") and str(marked.get("content") or "").strip():
        return str(marked.get("content") or "").strip()

    cleaned = strip_episode_script_thinking_blocks(source)
    cleaned = _strip_legacy_analysis_sections(cleaned)
    return cleaned.strip() or source.strip()


def is_acceptable_episode_script_markdown(text: str) -> bool:
    """Pass when both official OUTPUT markers exist, or official extract has H1 + scenes."""
    marked = extract_episode_script_output_between_markers(text)
    if marked.get("found") and str(marked.get("content") or "").strip():
        return True
    official = extract_official_episode_script(text)
    if len(official) < 200:
        return False
    has_h1 = bool(re.search(r"(?m)^#\s+\S+", official))
    has_scenes = bool(re.search(r"\[SCENES_BLOCK_START\]", official, flags=re.IGNORECASE))
    return has_h1 and has_scenes
