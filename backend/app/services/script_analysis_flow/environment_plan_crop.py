# -*- coding: utf-8 -*-
"""Crop environment-plan text before it is injected into a later node.

The plan itself stays complete. Copies are trimmed by who reads them:
- 依据 is planning reasoning and is not injected further.
- Shape, size, direction and distance stay for staging and asset design.
- Lighting stays for asset design. Staging and global orchestration do not get it.
- Standing anchors (挂靠锚点, 戏用标识, 空镜) stay for staging. Asset design does not get them.
"""
from __future__ import annotations

import re

_SPLIT = re.compile(r"[｜|]")
_BASIS_KEYS = {"依据"}
_LIGHT_LINE_KEYS = {"色光规划"}
_LIGHT_INNER_KEYS = {
    "全局对标片",
    "全局色调",
    "全局光线",
    "本块对标片",
    "主冷暖",
    "主色",
    "辅色",
    "点缀",
    "过渡",
    "调色机制",
    "光质",
    "光色倾向",
    "依据",
}
_PROFILES_DROP_LIGHT = {"staging", "orchestration"}
# Staging uses these to place people. Asset design does not.
_ASSET_ONLY_DROP_KEYS = {
    "挂靠锚点",
    "锚点落",
    "醒目光",
    "识别",
    "戏用标识",
    "站位承载",
    "参照物",
    "空镜",
}


def _field_key(part: str) -> str:
    head = str(part or "").strip()
    if "=" not in head:
        return ""
    return head.split("=", 1)[0].strip()


def _crop_line(line: str, *, drop_light: bool, drop_keys: set) -> str:
    if drop_keys and "【空镜规划】" in line:
        return ""
    parts = _SPLIT.split(line)
    if len(parts) == 1 and not _field_key(parts[0]):
        return line
    kept = []
    dropping_light = False
    for part in parts:
        key = _field_key(part)
        if dropping_light:
            if key in _LIGHT_INNER_KEYS or key in _LIGHT_LINE_KEYS:
                continue
            dropping_light = False
        if drop_light and key in _LIGHT_LINE_KEYS:
            dropping_light = True
            continue
        if key in _BASIS_KEYS or key in drop_keys:
            continue
        if drop_light and key == "光色倾向":
            continue
        kept.append(part.strip())
    return "｜".join(piece for piece in kept if piece)


def crop_environment_plan_text(text: str, profile: str) -> str:
    """Return a downstream copy. Unknown profiles return the text unchanged."""
    source = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    if not source.strip():
        return ""
    kind = str(profile or "").strip().lower()
    if kind not in {"asset", "staging", "orchestration"}:
        return source.strip()
    drop_light = kind in _PROFILES_DROP_LIGHT
    drop_keys = _ASSET_ONLY_DROP_KEYS if kind == "asset" else set()
    lines = [
        _crop_line(line, drop_light=drop_light, drop_keys=drop_keys)
        for line in source.split("\n")
    ]
    cropped = "\n".join(line for line in lines if line.strip())
    return re.sub(r"\n{3,}", "\n\n", cropped).strip()
