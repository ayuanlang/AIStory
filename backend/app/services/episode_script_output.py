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


_PAGE_KEEP_HEADING = (
    r"核心重点|核心内容纲要|本集卖点|本集实体定位台账|场景列表|场景进入|剧情一句话|结尾钩子|紧急回收"
)
_LEDGER_STOP = (
    r"全局角色|本集场景环境名清单|身份定位|核心重点|核心内容纲要|本集卖点|"
    r"场景列表|剧情连贯自检|分集开局规划|写后核销|娱乐化段子|"
    r"核心卖点（制作指导）|AI 视频研判|预告片框架规划落点"
)
_LEDGER_HEADING_RE = re.compile(
    rf"(?ms)^(?P<head>(?:#{{1,6}}\s*|[-*]\s*\*{{0,2}})本集实体定位台账\b[^\n]*)\n"
    rf"(?P<body>[\s\S]*?)"
    rf"(?=^(?:#{{1,6}}\s*|[-*]\s*\*{{0,2}})(?:{_LEDGER_STOP})"
    rf"|\[EPISODE_SCRIPT_|\[SCENES_BLOCK_START\]|\Z)",
)
_PAGE_DROP_HEADING = (
    r"-?1\)\s*类型执行摘要|类型执行摘要|剧情连贯自检|娱乐化段子|桥段凝聚汇总|"
    r"分集开局规划|写后核销总表|框架核销清单|大纲逐字分析台账|"
    r"核心卖点（制作指导）|AI 视频研判|预告片框架规划落点|"
    r"全局角色·道具特性状态表|全局角色特性状态表|全局道具特性状态表"
)
_ENTITY_ROW_RE = re.compile(
    r"(?<![A-Za-z])(?P<kind>CHAR|PROP|ENV)\|(?P<name>[^|\n]+)(?:\||$)"
)
_TRAIT_HEAD_RE = re.compile(
    r"^\s*(?:#{1,6}\s*|[-*]\s*\*{0,2})全局(?:角色[·・]道具特性状态表|角色特性状态表|道具特性状态表)\b"
)
_TRAIT_ROW_RE = re.compile(r"(?<![A-Za-z])(?:CHAR|PROP)特质\|")
_LEDGER_HEAD_LINE_RE = re.compile(
    r"^\s*(?:#{1,6}\s*|[-*]\s*\*{0,2})本集实体定位台账\b"
)
_CATEGORY_ONLY_RE = re.compile(
    r"^\s*[-*]\s*\*{0,2}(?P<cat>角色|道具|环境)\*{0,2}\s*[：:]\s*$"
)
_HARD_BREAK_RE = re.compile(
    r"^(?:#{1,6}\s+\S|\[(?:SCENES_BLOCK_|SCENE_|ENV_BLOCK_|BEAT_|EMERGENCY_RECOVERY_|EPISODE_SCRIPT_))"
)
_APPLIED_LINE_RE = re.compile(r"Applied Entities\s*全覆盖")
_PLACEHOLDER_NAMES = {"名(en)", "名（en）", "名(english)", "名"}

_BRIDGE_BLOCK_RE = re.compile(
    r"(?:━{6,}\s*)?\[\s*BRIDGE_BLOCK_START\s*\][\s\S]*?\[\s*BRIDGE_BLOCK_END\s*\](?:\s*━{6,})?",
    flags=re.IGNORECASE,
)


def _strip_legacy_analysis_sections(text: str) -> str:
    """Drop 类型执行摘要 / 剧情连贯自检 from unmarked legacy drafts."""
    source = str(text or "").strip()
    if not source:
        return ""

    source = re.sub(
        rf"(?ms)^(?:#{{1,6}}\s*)?-?1\)\s*类型执行摘要\b[\s\S]*?(?=^(?:#{{1,6}}\s*)?(?:{_PAGE_KEEP_HEADING})|\[SCENES_BLOCK_START\]|\[EPISODE_SCRIPT_OUTPUT_START\])",
        "",
        source,
    )
    source = re.sub(
        rf"(?ms)^(?:#{{1,6}}\s*)?类型执行摘要\b[\s\S]*?(?=^(?:#{{1,6}}\s*)?(?:{_PAGE_KEEP_HEADING})|\[SCENES_BLOCK_START\])",
        "",
        source,
    )
    source = re.sub(
        rf"(?ms)^(?:#{{1,6}}\s*)?剧情连贯自检\b[\s\S]*?(?=^(?:#{{1,6}}\s*)?(?:剧情一句话|结尾钩子|紧急回收)|\[EMERGENCY_RECOVERY_BLOCK_START\]|\[BRIDGE_BLOCK_START\]|\Z)",
        "",
        source,
    )
    return re.sub(r"\n{3,}", "\n\n", source).strip()


def extract_entity_position_ledger(text: str) -> str:
    """Pull 本集实体定位台账 from THINKING or unmarked drafts."""
    source = str(text or "")
    if not source.strip() or "本集实体定位台账" not in source:
        return ""
    match = _LEDGER_HEADING_RE.search(source)
    if not match:
        return ""
    body = str(match.group("body") or "").strip()
    if not body:
        return ""
    return f"## 本集实体定位台账\n{body}".strip()


def _entity_row_key(kind: str, name: str) -> str:
    compact = re.sub(r"\s+", "", str(name or "")).casefold()
    return f"{kind}|{compact}"


def _is_placeholder_entity(name: str) -> bool:
    return re.sub(r"\s+", "", str(name or "")).casefold() in _PLACEHOLDER_NAMES


def _is_hard_break(line: str) -> bool:
    return bool(_HARD_BREAK_RE.match(line.strip()))


def dedupe_entity_position_ledger(page: str) -> str:
    """Keep one ledger on the script page, and one row per character, prop, and place.

    Thinking also asks for the same ledger plus a trait table. Models often paste
    both into OUTPUT, so the same prop shows up as ``PROP|`` and again as ``PROP特质|``.
    """
    source = str(page or "")
    has_ledger = "本集实体定位台账" in source
    has_trait_table = bool(_TRAIT_HEAD_RE.search(source))
    if not source.strip() or (not has_ledger and not has_trait_table):
        return source.strip()

    real_kinds: set[str] = set()
    for line in source.splitlines():
        if _TRAIT_ROW_RE.search(line):
            continue
        for match in _ENTITY_ROW_RE.finditer(line):
            if not _is_placeholder_entity(match.group("name")):
                real_kinds.add(match.group("kind"))

    seen_ledger_head = False
    seen_keys: set[str] = set()
    seen_applied = False
    seen_category: set[str] = set()
    in_trait = False
    skip_extra_ledger = False
    in_ledger = False
    kept: list[str] = []

    for line in source.splitlines():
        if skip_extra_ledger:
            if _is_hard_break(line) and not _LEDGER_HEAD_LINE_RE.match(line):
                skip_extra_ledger = False
            else:
                continue

        if in_trait:
            real_entity = _ENTITY_ROW_RE.search(line) and not _TRAIT_ROW_RE.search(line)
            if _is_hard_break(line) or _LEDGER_HEAD_LINE_RE.match(line) or real_entity:
                in_trait = False
            else:
                continue

        if _TRAIT_HEAD_RE.match(line):
            in_trait = True
            continue
        if _TRAIT_ROW_RE.search(line):
            continue

        if _LEDGER_HEAD_LINE_RE.match(line):
            if seen_ledger_head:
                # Still inside the first ledger: merge later rows so a real prop
                # written only in the second copy is kept. After scenes, drop the copy.
                if in_ledger:
                    continue
                skip_extra_ledger = True
                continue
            seen_ledger_head = True
            in_ledger = True
            kept.append("## 本集实体定位台账")
            continue

        if _is_hard_break(line):
            in_ledger = False

        if in_ledger:
            if _APPLIED_LINE_RE.search(line):
                if seen_applied:
                    continue
                seen_applied = True
                kept.append(line)
                continue
            category = _CATEGORY_ONLY_RE.match(line)
            if category:
                label = category.group("cat")
                if label in seen_category:
                    continue
                seen_category.add(label)
                kept.append(line)
                continue
            match = _ENTITY_ROW_RE.search(line)
            if match and not _TRAIT_ROW_RE.search(line):
                kind = match.group("kind")
                if _is_placeholder_entity(match.group("name")) and kind in real_kinds:
                    continue
                key = _entity_row_key(kind, match.group("name"))
                if key in seen_keys:
                    continue
                seen_keys.add(key)

        kept.append(line)

    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()


def inject_entity_position_ledger(official: str, source: str) -> str:
    """Keep the ledger on the script page; insert after 核心重点 when missing."""
    page = str(official or "").strip()
    if not page:
        return extract_entity_position_ledger(source)
    if re.search(r"本集实体定位台账", page):
        return page
    ledger = extract_entity_position_ledger(source)
    if not ledger:
        return page
    core = re.search(
        r"(?ms)^##\s*核心重点\b.*?(?=^##\s+|\[SCENES_BLOCK_START\])",
        page,
    )
    if core:
        return f"{page[:core.end()].rstrip()}\n\n{ledger}\n\n{page[core.end():].lstrip()}".strip()
    heading = re.search(r"(?m)^#\s+\S+.*$", page)
    if heading:
        return f"{page[:heading.end()]}\n\n{ledger}\n\n{page[heading.end():].lstrip()}".strip()
    return f"{ledger}\n\n{page}".strip()


def trim_episode_script_for_page(text: str) -> str:
    """Keep only script-page payload for scene_split / 分场.

    Keeps: title, 核心重点 (or legacy 纲要/卖点), 本集实体定位台账, scenes + beats, handoff, emergency recovery.
    Drops: entertainment ledger, BRIDGE / 桥段凝聚汇总, leftover process sections.
    """
    source = str(text or "").strip()
    if not source:
        return ""

    source = _BRIDGE_BLOCK_RE.sub("", source)
    source = re.sub(
        rf"(?ms)^(?:#{{1,6}}\s*)?(?:{_PAGE_DROP_HEADING})[\s\S]*?(?=^(?:#{{1,6}}\s*)?(?:{_PAGE_KEEP_HEADING})|\[SCENES_BLOCK_START\]|\[EMERGENCY_RECOVERY_BLOCK_START\]|\Z)",
        "",
        source,
    )
    return re.sub(r"\n{3,}", "\n\n", source).strip()


def extract_official_episode_script(text: str) -> str:
    """Return the official script body for display / persist / heading parse.

    Prefer `[EPISODE_SCRIPT_OUTPUT_START]…[EPISODE_SCRIPT_OUTPUT_END]`.
    Fall back to stripping thinking + legacy analysis sections so title,
    核心重点, scenes, logline, and emergency recovery stay intact.
    Always trim process-analysis leftovers before persist / 剧本页.
    """
    source = str(text or "")
    if not source.strip():
        return ""

    marked = extract_episode_script_output_between_markers(source)
    if marked.get("found") and str(marked.get("content") or "").strip():
        cleaned = _strip_legacy_analysis_sections(str(marked.get("content") or ""))
        cleaned = trim_episode_script_for_page(cleaned)
        cleaned = inject_entity_position_ledger(cleaned, source) or cleaned
        return dedupe_entity_position_ledger(cleaned) or cleaned

    cleaned = strip_episode_script_thinking_blocks(source)
    cleaned = _strip_legacy_analysis_sections(cleaned)
    cleaned = trim_episode_script_for_page(cleaned)
    cleaned = inject_entity_position_ledger(cleaned, source) or cleaned
    cleaned = dedupe_entity_position_ledger(cleaned)
    return cleaned.strip() or dedupe_entity_position_ledger(source).strip()


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
