# -*- coding: utf-8 -*-
"""Blocks the shot reads from the node that locked them, not from the beat body."""
from __future__ import annotations

import re
from typing import List, Sequence

from app.core.prompt_injection import wrap_injection_section

_SCENE_START_RE = re.compile(r"`?\[SCENE_START:([^\s\]]+)\]`?", re.IGNORECASE)
_SCENE_SLICE_RE = re.compile(
    r"`?\[SCENE_START:{sid}\]`?(?P<body>.*?)`?\[SCENE_END:",
    re.IGNORECASE | re.DOTALL,
)
_BEAT_START_RE = re.compile(r"`?\[BEAT_START:([^\s\]]+)\]`?", re.IGNORECASE)
_BEAT_END_RE = re.compile(r"`?\[BEAT_END:", re.IGNORECASE)
_GUIDANCE_RE = re.compile(r"【\s*改编指导\s*】[^\n\r]*")
_STC_RE = re.compile(r"救猫咪拍\s*=\s*([^｜|\s：:\n\r]+)")
_HEADER_RE = re.compile(r"^【([^】]+)】")

_JOIN_HEADERS = ("场景衔接", "闪回分档")
_FIELD_HEADERS = ("卖点综合", "情绪峰谷综合", "叙事综合")

_PREFACE = (
    "这些块在锁定时已经写完，分镜只读这一份，不从建置正文里再找。"
    "【场景衔接】和【闪回分档】来自全局统筹。"
    "【卖点综合】【情绪峰谷综合】【叙事综合】以及每拍【改编指导】来自文戏；"
    "有武戏稿时用武戏稿里的同名行。"
    "首尾镜切法、艺术转入和艺术转出只读【场景衔接】。"
    "没有【闪回分档】或分档不是同场短闪回、同场闪切时，不把换场收成蒙太奇；"
    "拍上的蒙太奇链仍以拍正文为准。"
    "场结果和同拍角色、道具的句序只读这三行综合。"
    "运镜和光影只读该拍【改编指导】，含救猫咪拍。"
    "抄建置时跳过拍内的【改编指导】行，不写入 Video。"
)


def slice_scene_body(script: str, scene_id: str) -> str:
    """One scene body. A single-scene draft without a matching id is returned whole."""
    text = str(script or "").strip()
    sid = str(scene_id or "").strip()
    if not text:
        return ""
    if sid:
        match = re.search(
            _SCENE_SLICE_RE.pattern.format(sid=re.escape(sid)),
            text,
            flags=_SCENE_SLICE_RE.flags,
        )
        if match:
            return str(match.group("body") or "").strip()
    starts = [item.strip() for item in _SCENE_START_RE.findall(text) if item.strip()]
    if sid and starts and sid.lower() not in {item.lower() for item in starts}:
        return ""
    if len(starts) <= 1:
        return text
    return ""


def extract_named_blocks(text: str, names: Sequence[str]) -> List[str]:
    """Each 【name】 block runs until the next heading or marker."""
    wanted = set(names)
    lines = str(text or "").replace("\r\n", "\n").split("\n")
    blocks: List[str] = []
    index = 0
    while index < len(lines):
        header = _HEADER_RE.match(lines[index].strip())
        if not header or header.group(1) not in wanted:
            index += 1
            continue
        chunk = [lines[index].strip()]
        index += 1
        while index < len(lines):
            stripped = lines[index].strip()
            if not stripped:
                index += 1
                continue
            if stripped.startswith("【") or stripped.startswith("[") or stripped.startswith("────"):
                break
            chunk.append(stripped)
            index += 1
        body = "\n".join(chunk).strip()
        if body:
            blocks.append(body)
    return blocks


def extract_guidance_by_beat(text: str) -> List[str]:
    """One 【改编指导】 line per beat, with 救猫咪拍 taken from that beat's title."""
    source = str(text or "")
    starts = list(_BEAT_START_RE.finditer(source))
    rows: List[str] = []
    for index, start in enumerate(starts):
        beat_id = str(start.group(1) or "").strip()
        next_at = starts[index + 1].start() if index + 1 < len(starts) else len(source)
        end = _BEAT_END_RE.search(source, start.end())
        stop = end.start() if end and end.start() <= next_at else next_at
        chunk = source[start.start() : stop]
        guidance = _GUIDANCE_RE.search(chunk)
        if not guidance:
            continue
        line = re.sub(r"\s+", " ", guidance.group(0)).strip()
        if "救猫咪拍" not in line:
            stc = _STC_RE.search(chunk)
            if stc and stc.group(1).strip():
                line = line.replace("【改编指导】", f"【改编指导】救猫咪拍={stc.group(1).strip()}｜", 1)
        rows.append(f"Beat{beat_id}｜{line}")
    return rows


def _first_blocks(primary: str, fallback: str, names: Sequence[str]) -> List[str]:
    found = extract_named_blocks(primary, names)
    if found:
        return found
    return extract_named_blocks(fallback, names)


def compose_shot_locked_body(
    *,
    split_text: str,
    beat_source_text: str,
    scene_id: str,
) -> str:
    split_body = slice_scene_body(split_text, scene_id)
    beat_body = slice_scene_body(beat_source_text, scene_id)
    parts: List[str] = []
    join = _first_blocks(split_body, beat_body, _JOIN_HEADERS)
    fields = _first_blocks(beat_body, split_body, _FIELD_HEADERS)
    guidance = extract_guidance_by_beat(beat_body)
    if join:
        parts.append("\n".join(join))
    if fields:
        parts.append("\n".join(fields))
    if guidance:
        parts.append("\n".join(guidance))
    if not parts:
        return ""
    return _PREFACE + "\n\n" + "\n\n".join(parts)


def shot_locked_has_guidance(body: str) -> bool:
    return "【改编指导】" in str(body or "")


def strip_guidance_lines(text: str) -> str:
    """Drop拍内改编指导 so the shot copies 建置 without that row."""
    cleaned = _GUIDANCE_RE.sub("", str(text or ""))
    return re.sub(r"\n{3,}", "\n\n", cleaned)


def format_shot_locked_injection(body: str) -> str:
    text = str(body or "").strip()
    if not text:
        return ""
    return wrap_injection_section("分镜锁定", text)


def _beat_source_text(steps: dict) -> str:
    combat = str((steps or {}).get("combat") or "").strip()
    drama = str((steps or {}).get("drama") or "").strip()
    if combat and ("【卖点综合】" in combat or "【改编指导】" in combat):
        return combat
    return drama or combat


def load_shot_locked_body(db, episode_id: int, scene_id: str) -> str:
    from app.services.script_analysis_flow.analyze_scene_stages import (
        load_scene_subskill_results_map,
        load_stage1_output_text,
        lookup_persisted_scene_subskill_steps,
    )

    sid = str(scene_id or "").strip()
    eid = int(episode_id or 0)
    if eid <= 0 or not sid:
        return ""
    split_text = load_stage1_output_text(db, eid, "scene_split")
    if not split_text:
        split_text = load_stage1_output_text(db, eid, "adapted_script")
    steps = lookup_persisted_scene_subskill_steps(
        load_scene_subskill_results_map(db, eid),
        sid,
    )
    return compose_shot_locked_body(
        split_text=split_text,
        beat_source_text=_beat_source_text(steps),
        scene_id=sid,
    )

