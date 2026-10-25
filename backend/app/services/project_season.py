# -*- coding: utf-8 -*-
"""Inject the project season into framework, prefill, and episode scripts."""
from __future__ import annotations

import re
from typing import Any, Dict

_SEASON_KEYS = (
    "season_occurrence",
    "season",
    "发生季节",
    "Season",
    "Season Occurrence",
)

_LOCKED = {
    "春": "春",
    "夏": "夏",
    "秋": "秋",
    "冬": "冬",
    "spring": "春",
    "summer": "夏",
    "autumn": "秋",
    "fall": "秋",
    "winter": "冬",
}

_OPEN_YEAR = {"全年", "allseasons", "allseason"}
_OPEN_FREE = {"不限制", "不限", "nolimit", "unlimited", "none", "n/a", "na"}

_NESTED_KEYS = ("basic_information", "e_global_info", "story_generator_global_input")


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _flatten_sources(sources: tuple) -> list:
    blobs = []
    for source in sources:
        if isinstance(source, str):
            text = source.strip()
            if text:
                return [{"season_occurrence": text}]
            continue
        if not isinstance(source, dict):
            continue
        blobs.append(source)
        for key in _NESTED_KEYS:
            nested = source.get(key)
            if isinstance(nested, dict):
                blobs.append(nested)
    return blobs


def pick_season_occurrence(*sources: Any) -> str:
    """First non-empty season. An explicit string wins over saved project info."""
    for source in sources:
        if isinstance(source, str) and source.strip():
            return source.strip()
    for blob in _flatten_sources(sources):
        for key in _SEASON_KEYS:
            text = _text(blob.get(key))
            if text:
                return text
    return ""


def _head(raw: str) -> str:
    text = _text(raw)
    head = re.split(r"[／/]", text, maxsplit=1)[0].strip().lower()
    head = re.sub(r"\s+", "", head)
    if head.endswith("季") and len(head) > 1:
        head = head[:-1]
    if head.endswith("天") and head[:-1] in _LOCKED:
        head = head[:-1]
    return head


def classify_project_season(raw: str) -> Dict[str, str]:
    """tier is locked, year, or open. locked carries 春|夏|秋|冬."""
    text = _text(raw)
    head = _head(text)
    if head in _LOCKED:
        return {"raw": text, "tier": "locked", "season": _LOCKED[head]}
    if head in _OPEN_YEAR:
        return {"raw": text, "tier": "year", "season": ""}
    if head in _OPEN_FREE or not text:
        return {"raw": text, "tier": "open", "season": ""}
    found = []
    for token, season in _LOCKED.items():
        if token in head and season not in found:
            found.append(season)
    if len(found) == 1:
        return {"raw": text, "tier": "locked", "season": found[0]}
    if len(found) > 1:
        return {"raw": text, "tier": "year", "season": ""}
    return {"raw": text, "tier": "open", "season": ""}


def format_project_season_prompt(*sources: Any) -> str:
    """User-prompt block. Callers prepend it; the story prompts apply 档=."""
    info = classify_project_season(pick_season_occurrence(*sources))
    if info["tier"] == "locked":
        apply = (
            f"档=已锁｜开篇季={info['season']}。"
            "项目信息里的这一季是故事开始的季节，不是全剧每一集都锁死的季节。"
            "时间还停在开篇这一段，时间节点、预填、分集和场头用这一季。"
            "情节里的时间已经走到下一季，季节按春、夏、秋、冬、再回春顺着变，写跨季=是，并写过了多久。"
            "没有写出这段时间过去，不得无故换季。"
            "换季只改季节。不写景致、衣着，也不写道具外形和环境实体的陈设、材质、光色。"
            "闪回回到开篇那一段，仍用开篇季。"
        )
    elif info["tier"] == "year":
        apply = (
            "档=全年。"
            "故事可以跨季，但每一次换季必须在情节里写明过了多久，并写跨季=是。"
            "没有写出时间流逝，就沿用开篇那一季，不得无故换季。"
            "换季只改季节。不写景致、衣着，也不写道具外形和环境实体细节。"
        )
    else:
        shown = info["raw"] or "空"
        apply = (
            f"档=未锁｜原值={shown}。"
            "情节已经写了季节，就用情节那一季。"
            "大纲或预填已锁的一季继续沿用。剧情时间走到下一季，季节顺着变。"
            "两边都没有，才按情节锁春、夏、秋、冬里的一季，并标继承=推断。"
            "换季只改季节。不写景致、衣着，也不写道具外形和环境实体细节。"
        )
    return (
        "【项目季节 — 必须应用】\n"
        "本块是项目信息，位于注入链最上游：项目信息 → 剧本结构化预填 → 剧本框架 → 剧本生成。\n"
        "本块的季节是故事开始的季节。剧情时间还在开篇，就用它。剧情时间走到了后面的季节，顺着换成那一季。不要用开篇季盖住已经写明的换季。剧本框架、分集大纲、剧本生成不写景致、衣着、道具外形、环境实体细节。\n"
        f"发生季节={info['raw'] or '空'}\n"
        f"{apply}\n"
        "气候按情节另锁。季节不改昼夜。\n"
    )
