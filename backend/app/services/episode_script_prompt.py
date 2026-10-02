# -*- coding: utf-8 -*-
"""Prompt-block helpers for episode-script generation."""
from __future__ import annotations

from typing import Optional


def build_episode_generation_guidance_prompt_block(guidance: Optional[str]) -> str:
    """Build the high-priority user-prompt block for this-episode writing guidance.

    Empty / whitespace-only input yields an empty string so callers can prepend safely.
    """
    text = str(guidance or "").strip()
    if not text:
        return ""
    return (
        "【本集生成指导 / Episode Generation Guidance — HIGHEST PRIORITY】\n"
        "The following is the user's explicit high-priority writing brief for THIS episode only.\n"
        "You MUST fulfill it in the episode script. It outranks Extra Notes, optional flavor, and default stylistic preferences.\n"
        "It MUST NOT violate hard format contracts, previous-episode handoff, character-canon identity, or safety constraints.\n"
        "If a request conflicts with those hard constraints, keep the hard constraint and fulfill the rest of the guidance.\n\n"
        f"{text}\n\n"
    )


def build_trailer_generation_prompt_block() -> str:
    """Highest-priority brief when this call writes a trailer, not a series episode."""
    return (
        "【预告片生成 / Trailer — HIGHEST PRIORITY】\n"
        "This call writes ONE trailer. It is not series episode 1 and not a compressed episode.\n"
        "Story-circle completeness, previous-episode handoff, and next-episode setup do not apply.\n"
        "Draw the picture from two sources only:\n"
        "1) 娱乐时间 = Save the Cat Fun and Games / 游戏时间 / 节拍08. This is the body. "
        "At least three entertainment beats: who does what, why it is fun to watch, and the visible result.\n"
        "2) 核心看点 = Audience Hook, TOP anchors, iconic lines, 四美, and spectacle already in the global framework. "
        "Each highlight used here must be seen or heard in the trailer, not only named in the selling-point list.\n"
        "Shape: open on the most arresting fun-and-games image; cut the entertainment beats; "
        "end by showing one side of the crisis and withholding the answer. Do not play the finale, "
        "do not reveal a hidden villain, and do not retell all 15 beats in order.\n"
        "The first non-empty OUTPUT line MUST be: # 预告-{short title}\n"
        "Keep the formal script blocks, but 卖点 are the highlights this trailer actually shows, "
        "and 重要情节 must say what is shown and what is deliberately withheld.\n\n"
    )


def resolve_episode_generation_guidance_for_prompt(
    *,
    single_episode_mode: bool,
    request_guidance: Optional[str] = None,
    persisted_guidance: Optional[str] = None,
) -> str:
    """Inject this-episode guidance only for single-episode generation."""
    if not single_episode_mode:
        return ""
    text = str(request_guidance or "").strip() or str(persisted_guidance or "").strip()
    return build_episode_generation_guidance_prompt_block(text)
